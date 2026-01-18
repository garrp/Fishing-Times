import math
from datetime import datetime, date, timedelta
import pytz
import requests
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

from astral import LocationInfo
from astral.sun import sun
import ephem


# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(
    page_title="FishyNW Fishing Times",
    page_icon="🎣",
    layout="wide",
)

# ----------------------------
# Styling
# ----------------------------
st.markdown("""
<style>
.block-container { max-width: 1150px; padding-top: 1.2rem; padding-bottom: 2.2rem; }
.fishynw-card {
  background: rgba(17,26,46,.55);
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(255,255,255,.10);
}
.muted { color: rgba(235,240,255,.70); }
.pill {
  display:inline-flex; gap:8px; padding:6px 10px;
  border-radius:999px; font-size:12px;
  border:1px solid rgba(255,255,255,.12);
  background: rgba(10,16,30,.35);
}
.footer { margin-top:28px; text-align:center; font-size:12px; color:#9fb2d9; }
.footer a { color:#6fd3ff; text-decoration:none; }
.small { font-size:12px; }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Helpers
# ----------------------------
def clamp(x, a, b):
    return max(a, min(b, x))

def gaussian(x, mu, sigma):
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)

def minutes_since_midnight(dt, tz):
    local = dt.astimezone(tz)
    return local.hour * 60 + local.minute

def to_datetime_local_naive(day: date, minute: int):
    # naive local datetime (Plotly handles naive fine)
    return datetime(day.year, day.month, day.day, minute // 60, minute % 60)

# ----------------------------
# Geocoding (Open-Meteo)
# ----------------------------
def geocode_city_state(city: str, state: str):
    if not city.strip() or not state.strip():
        raise ValueError("Enter City and State.")

    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city.strip(), "count": 25, "language": "en", "format": "json"}, timeout=12)
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise ValueError("City not found.")

    state_u = state.strip().upper()

    us = [x for x in results if (x.get("country_code") or "").upper() == "US"]
    if not us:
        raise ValueError("No US matches found.")

    # Prefer state match in admin1
    for x in us:
        admin1 = (x.get("admin1") or "").upper()
        if state_u in admin1:
            return float(x["latitude"]), float(x["longitude"]), f"{x['name']}, {x.get('admin1','')}"
    # fallback to first US result
    x = us[0]
    return float(x["latitude"]), float(x["longitude"]), f"{x['name']}, {x.get('admin1','')}"

# ----------------------------
# Astronomy per-day events
# ----------------------------
def get_events(day: date, lat: float, lon: float, tz: pytz.BaseTzInfo):
    loc = LocationInfo("", "", tz.zone, lat, lon)
    s = sun(loc.observer, date=day, tzinfo=tz)

    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)

    # set observer date to local midnight -> UTC
    local_midnight = tz.localize(datetime(day.year, day.month, day.day, 0, 0, 0))
    obs.date = local_midnight.astimezone(pytz.utc)

    moon = ephem.Moon()
    moonrise = moonset = None
    try:
        moonrise = ephem.Date(obs.next_rising(moon)).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except:
        pass
    try:
        moonset = ephem.Date(obs.next_setting(moon)).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except:
        pass

    # overhead/underfoot by sampling every 5 minutes
    best_hi_alt = -999.0
    best_lo_alt = 999.0
    best_hi_time = None
    best_lo_time = None

    t = tz.localize(datetime(day.year, day.month, day.day, 0, 0, 0))
    for _ in range(288):  # 24h * 60 / 5
        obs.date = t.astimezone(pytz.utc)
        moon.compute(obs)
        alt = float(moon.alt)
        if alt > best_hi_alt:
            best_hi_alt = alt
            best_hi_time = t
        if alt < best_lo_alt:
            best_lo_alt = alt
            best_lo_time = t
        t += timedelta(minutes=5)

    return {
        "sunrise": s.get("sunrise"),
        "sunset": s.get("sunset"),
        "moonrise": moonrise,
        "moonset": moonset,
        "overhead": best_hi_time,
        "underfoot": best_lo_time,
    }

# ----------------------------
# Bite curve per day (minute-based)
# ----------------------------
def build_bite_curve_for_day(day: date, tz: pytz.BaseTzInfo, events: dict):
    centers = []
    weights = []
    sigmas = []

    def add(dt, w, sigma):
        if dt:
            centers.append(minutes_since_midnight(dt, tz))
            weights.append(w)
            sigmas.append(sigma)

    # major
    add(events.get("overhead"), 1.00, 95)
    add(events.get("underfoot"), 1.00, 95)
    # minor
    add(events.get("moonrise"), 0.65, 55)
    add(events.get("moonset"), 0.65, 55)
    # sun bonus
    add(events.get("sunrise"), 0.55, 50)
    add(events.get("sunset"), 0.55, 50)

    xs = []
    ys = []

    for m in range(1440):
        val = 25.0  # baseline
        for c, w, sig in zip(centers, weights, sigmas):
            d = min(abs(m - c), 1440 - abs(m - c))
            val += w * 60.0 * gaussian(d, 0.0, sig)
        ys.append(clamp(val, 0, 100))
        xs.append(to_datetime_local_naive(day, m))

    return xs, ys

# ----------------------------
# Multi-day build
# ----------------------------
def build_multi_day_series(start_day: date, days: int, lat: float, lon: float, tz: pytz.BaseTzInfo):
    all_x = []
    all_y = []
    day_slices = []  # (label, start_idx, end_idx)

    idx = 0
    for i in range(days):
        d = start_day + timedelta(days=i)
        ev = get_events(d, lat, lon, tz)
        xs, ys = build_bite_curve_for_day(d, tz, ev)

        all_x.extend(xs)
        all_y.extend(ys)

        day_slices.append((d.strftime("%a %b %-d"), idx, idx + len(xs) - 1))
        idx += len(xs)

    return all_x, all_y, day_slices

# ----------------------------
# UI Header
# ----------------------------
st.markdown("""
<div class="fishynw-card">
  <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
    <div style="font-size:28px;">🎣</div>
    <div>
      <div style="font-size:20px; font-weight:700;">FishyNW Fishing Times</div>
      <div class="muted" style="font-size:13px;">
        Bite index across multiple days (drag to zoom, swipe to explore).
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

tz = pytz.timezone("America/Los_Angeles")

st.write("")
colA, colB = st.columns([1.15, 0.85], gap="large")

with colA:
    st.markdown('<div class="fishynw-card">', unsafe_allow_html=True)

    start_day = st.date_input("Start date", value=datetime.now(tz).date())
    days = st.selectbox("Days to show", [2, 3], index=0)

    city = st.text_input("City", "Coeur d'Alene")
    state = st.text_input("State", "ID")

    st.markdown(
        '<div class="muted small">Tip: If your city exists in multiple states, use the two-letter state code.</div>',
        unsafe_allow_html=True
    )

    go_btn = st.button("Generate multi-day graph", type="primary")

    st.markdown('</div>', unsafe_allow_html=True)

with colB:
    st.markdown(
        """
<div class="fishynw-card">
  <div style="font-size:16px; font-weight:700; margin-bottom:6px;">How to use</div>
  <div class="muted" style="font-size:13px; line-height:1.55;">
    <ul style="margin:0; padding-left:18px;">
      <li>Choose a start date, then 2 or 3 days.</li>
      <li>Use pinch-zoom and drag to inspect peaks.</li>
      <li>Use the day slider below to jump to a specific day.</li>
    </ul>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# ----------------------------
# Graph output
# ----------------------------
if go_btn:
    try:
        lat, lon, place = geocode_city_state(city, state)

        x, y, slices = build_multi_day_series(start_day, days, lat, lon, tz)

        # Day jump slider (indexes into slices)
        if days == 2:
            labels = [slices[0][0], slices[1][0]]
        else:
            labels = [slices[0][0], slices[1][0], slices[2][0]]

        day_idx = st.slider("Jump to day", 0, days - 1, 0, format="%d")
        label, i0, i1 = slices[day_idx]

        # Build plotly figure
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="Bite Index"))

        # Focus view to selected day range by default (still zoomable)
        fig.update_xaxes(range=[x[i0], x[i1]])
        fig.update_yaxes(range=[0, 100], title="Bite Index (0–100)")

        fig.update_layout(
            title=f"Bite Index • {place} • {days} day view",
            margin=dict(l=10, r=10, t=45, b=10),
            height=420,
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(str(e))

# ----------------------------
# Footer
# ----------------------------
st.markdown("""
<div class="footer">
  🎣 <b>FishyNW</b> • <a href="https://fishynw.com" target="_blank" rel="noopener">fishynw.com</a><br>
  Pacific Northwest Fishing • #adventure
</div>
""", unsafe_allow_html=True)