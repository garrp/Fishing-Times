import math
from datetime import datetime, date, timedelta
from pathlib import Path

import pytz
import requests
import streamlit as st
import matplotlib.pyplot as plt

from astral import LocationInfo
from astral.sun import sun
import ephem


# ============================================================
# App config
# ============================================================
st.set_page_config(page_title="FishyNW", layout="wide")

st.markdown(
    """
<style>
.block-container { max-width: 1100px; padding-top: 1.2rem; }
.fishynw-card {
  background: rgba(17,26,46,.55);
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(255,255,255,.10);
  margin-bottom: 14px;
}
.muted { color: rgba(235,240,255,.70); }
.footer {
  margin-top: 26px;
  text-align:center;
  font-size:12px;
  color:#9fb2d9;
}
.footer a { color:#6fd3ff; text-decoration:none; }
hr { border: none; border-top: 1px solid rgba(255,255,255,.10); margin: 12px 0; }
</style>
""",
    unsafe_allow_html=True,
)

TZ = pytz.timezone("America/Los_Angeles")


# ============================================================
# Shared helpers
# ============================================================
def clamp(x, a, b):
    return max(a, min(b, x))


def gaussian(x, mu, sigma):
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def minutes_since_midnight(dt, tz):
    local = dt.astimezone(tz)
    return local.hour * 60 + local.minute


def deg_to_compass(deg):
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    ix = int((deg / 22.5) + 0.5) % 16
    return dirs[ix]


def show_logo():
    candidates = [
        Path("FishyNW-logo.png"),
        Path("assets/FishyNW-logo.png"),
        Path("images/FishyNW-logo.png"),
    ]
    for p in candidates:
        if p.exists():
            st.image(str(p), width=240)
            return
    st.markdown("<div class='muted'><b>FishyNW</b></div>", unsafe_allow_html=True)


# ============================================================
# BEST FISHING TIMES (keeps: location + date + wind + chart)
# ============================================================
def geocode_city_state(city, state):
    city = (city or "").strip()
    state = (state or "").strip()
    if not city or not state:
        raise ValueError("Enter City and State.")

    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city, "count": 20, "language": "en", "format": "json"}, timeout=10)
    r.raise_for_status()
    results = r.json().get("results", []) or []
    if not results:
        raise ValueError("City not found.")

    state_u = state.upper()
    us = [x for x in results if (x.get("country_code") or "").upper() == "US"]
    if not us:
        raise ValueError("No US matches found.")

    for item in us:
        admin1 = (item.get("admin1") or "").upper()
        if state_u in admin1:
            return float(item["latitude"]), float(item["longitude"]), f"{item['name']}, {item.get('admin1','')}"
    item = us[0]
    return float(item["latitude"]), float(item["longitude"]), f"{item['name']}, {item.get('admin1','')}"


def get_events(day, lat, lon, tz):
    loc = LocationInfo("", "", tz.zone, lat, lon)
    s = sun(loc.observer, date=day, tzinfo=tz)

    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)
    obs.date = tz.localize(datetime(day.year, day.month, day.day)).astimezone(pytz.utc)

    moon = ephem.Moon()
    moonrise = moonset = None
    try:
        moonrise = ephem.Date(obs.next_rising(moon)).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except Exception:
        pass
    try:
        moonset = ephem.Date(obs.next_setting(moon)).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except Exception:
        pass

    best_hi = (-999.0, None)
    best_lo = (999.0, None)
    t = tz.localize(datetime(day.year, day.month, day.day, 0, 0, 0))
    for _ in range(288):  # every 5 minutes
        obs.date = t.astimezone(pytz.utc)
        moon.compute(obs)
        alt = float(moon.alt)
        if alt > best_hi[0]:
            best_hi = (alt, t)
        if alt < best_lo[0]:
            best_lo = (alt, t)
        t += timedelta(minutes=5)

    return {
        "sunrise": s.get("sunrise"),
        "sunset": s.get("sunset"),
        "moonrise": moonrise,
        "moonset": moonset,
        "overhead": best_hi[1],
        "underfoot": best_lo[1],
    }


def build_bite_curve(day, tz, events):
    centers = []
    weights = []

    def add(dt, w):
        if dt:
            centers.append(minutes_since_midnight(dt, tz))
            weights.append(w)

    # Major
    add(events.get("overhead"), 1.0)
    add(events.get("underfoot"), 1.0)
    # Minor
    add(events.get("moonrise"), 0.6)
    add(events.get("moonset"), 0.6)
    # Sun bonus
    add(events.get("sunrise"), 0.5)
    add(events.get("sunset"), 0.5)

    x_hours = []
    y = []
    for m in range(1440):
        val = 25.0
        for c, w in zip(centers, weights):
            d = min(abs(m - c), 1440 - abs(m - c))
            sigma = 90 if w >= 1.0 else 60
            val += w * 60.0 * gaussian(d, 0.0, sigma)
        x_hours.append(m / 60.0)
        y.append(clamp(val, 0, 100))
    return x_hours, y


def fetch_wind_bullets_4h(day, lat, lon, tz_name):
    url = "https://api.open-meteo.com/v1/forecast"
    r = requests.get(
        url,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "wind_speed_unit": "mph",
            "timezone": tz_name,
        },
        timeout=10,
    )
    r.raise_for_status()

    hourly = r.json().get("hourly", {}) or {}
    times = hourly.get("time", []) or []
    ws = hourly.get("wind_speed_10m", []) or []
    wd = hourly.get("wind_direction_10m", []) or []
    wg = hourly.get("wind_gusts_10m", []) or []

    bullets = []
    for t, s, d, g in zip(times, ws, wd, wg):
        hour = int(t.split("T")[1][:2])
        if hour % 4 != 0:
            continue
        label = f"{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}"
        bullets.append(
            f"**{label}**: {int(round(s))} mph {deg_to_compass(float(d))}, gust {int(round(g))} mph"
        )
    return bullets


def page_best_fishing_times():
    st.markdown("<div class='fishynw-card'>", unsafe_allow_html=True)
    show_logo()
    st.markdown("<h2>Best Fishing Times</h2>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>Location + date + bite index graph + wind every four hours.</div>",
                unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        day = st.date_input("Date", value=datetime.now(TZ).date(), key="bft_date")
        city = st.text_input("City", "Coeur d'Alene", key="bft_city")
        state = st.text_input("State", "ID", key="bft_state")

    with c2:
        st.markdown("<div class='fishynw-card'>", unsafe_allow_html=True)
        st.markdown("**What you get**", unsafe_allow_html=True)
        st.markdown("- Static chart image (no dragging/zooming)")
        st.markdown("- Wind bullets every 4 hours")
        st.markdown("- City + State location")
        st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Generate", type="primary", key="bft_go"):
        try:
            lat, lon, place = geocode_city_state(city, state)
            events = get_events(day, lat, lon, TZ)
            x, y = build_bite_curve(day, TZ, events)

            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(x, y, linewidth=2)
            ax.set_xlim(0, 24)
            ax.set_ylim(0, 100)
            ax.set_xlabel("Time of Day")
            ax.set_ylabel("Bite Index")
            ax.set_title(f"Bite Index • {place}")
            ax.set_xticks(range(0, 25, 4))
            ax.grid(alpha=0.3)
            st.pyplot(fig, clear_figure=True)

            st.markdown("### Wind (every 4 hours)")
            bullets = fetch_wind_bullets_4h(day, lat, lon, TZ.zone)
            if bullets:
                for b in bullets:
                    st.markdown(f"- {b}")
            else:
                st.write("No wind data available for that day.")

        except Exception as e:
            st.error(str(e))


# ============================================================
# DEPTH CALCULATOR (separate menu/page/app inside same app.py)
# ============================================================
def line_type_factor(line_type: str) -> float:
    """
    Lower factor = cuts water better = goes deeper for same setup.
    Simple approximation.
    """
    lt = (line_type or "").lower()
    if "braid" in lt:
        return 1.00
    if "fluoro" in lt:
        return 1.12
    if "mono" in lt:
        return 1.25
    return 1.15


def estimate_depth_ft(speed_mph: float, weight_oz: float, line_out_ft: float, line_type: str) -> float:
    """
    Estimate depth from speed + weight + line out + line type.
    This is a consistent fishing calculator (not a physics simulator).
    """
    speed_mph = max(0.1, float(speed_mph))
    weight_oz = max(0.1, float(weight_oz))
    line_out_ft = max(0.0, float(line_out_ft))

    lf = line_type_factor(line_type)

    # Tuned to be reasonable in 0.8–2.5 mph trolling range
    depth_ratio = (0.86 * (weight_oz ** 0.55)) / (speed_mph ** 0.75) / lf
    depth = line_out_ft * clamp(depth_ratio, 0.05, 0.95)
    return max(0.0, depth)


def page_depth_calculator():
    st.markdown("<div class='fishynw-card'>", unsafe_allow_html=True)
    show_logo()
    st.markdown("<h2>Depth Calculator</h2>", unsafe_allow_html=True)
    st.markdown(
        "<div class='muted'>Enter speed, weight, line type, and line out. "
        "The calculator estimates the depth you are running.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1], gap="large")
    with c1:
        speed_mph = st.number_input("Speed (mph)", min_value=0.1, max_value=6.0, value=1.5, step=0.1)
    with c2:
        line_type = st.selectbox("Line type", ["Braid", "Fluorocarbon", "Mono"], index=0)
    with c3:
        weight_oz = st.number_input("Weight (oz)", min_value=0.1, max_value=32.0, value=8.0, step=0.5)
    with c4:
        line_out_ft = st.number_input("Line out (ft)", min_value=0.0, max_value=400.0, value=120.0, step=5.0)

    depth = estimate_depth_ft(speed_mph, weight_oz, line_out_ft, line_type)

    st.markdown("<div class='fishynw-card'>", unsafe_allow_html=True)
    st.markdown("### Result")
    st.markdown(f"**Estimated depth:** {depth:.1f} ft")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='muted'>Estimate only. Real depth depends on lure drag, current, rod angle, "
        "line diameter, and how clean the lure tracks.</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# Sidebar primary menu (this is what you asked for)
# - Tab 1: Current app (location/date/wind/best fishing times)
# - Tab 2: Separate depth calculator app/page
# ============================================================
with st.sidebar:
    st.markdown("## FishyNW")
    menu = st.radio(
        "Primary menu",
        ["Best Fishing Times", "Depth Calculator"],
        index=0,
    )

if menu == "Best Fishing Times":
    page_best_fishing_times()
else:
    page_depth_calculator()

st.markdown(
    """
<div class="footer">
  <b>FishyNW</b> • <a href="https://fishynw.com" target="_blank" rel="noopener">fishynw.com</a>
</div>
""",
    unsafe_allow_html=True,
)