import math
from datetime import datetime, date, timedelta
import pytz
import requests
import streamlit as st
import streamlit.components.v1 as components
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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
.block-container { max-width: 1150px; padding-top: 1.2rem; }
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
}
.footer { margin-top:28px; text-align:center; font-size:12px; color:#9fb2d9; }
.footer a { color:#6fd3ff; text-decoration:none; }
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

def to_datetime(minutes, base_date, tz):
    return tz.localize(datetime(
        base_date.year,
        base_date.month,
        base_date.day,
        int(minutes // 60),
        int(minutes % 60)
    ))

# ----------------------------
# Geocoding
# ----------------------------
US_STATES = {
    "ID":"Idaho","WA":"Washington","OR":"Oregon","MT":"Montana","CA":"California"
}

def geocode_city_state(city, state):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city, "count": 20}, timeout=10)
    r.raise_for_status()
    results = r.json().get("results", [])

    if not results:
        raise ValueError("City not found")

    for r in results:
        if r.get("country_code") == "US" and state.upper() in (r.get("admin1","").upper()):
            return r["latitude"], r["longitude"], f"{r['name']}, {r['admin1']}"

    r = results[0]
    return r["latitude"], r["longitude"], r["name"]

# ----------------------------
# Astronomy
# ----------------------------
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
    except: pass
    try:
        moonset = ephem.Date(obs.next_setting(moon)).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except: pass

    # Moon overhead / underfoot (sampled)
    best_hi = (-999, None)
    best_lo = (999, None)
    t = tz.localize(datetime(day.year, day.month, day.day))
    for _ in range(288):  # every 5 min
        obs.date = t.astimezone(pytz.utc)
        moon.compute(obs)
        alt = float(moon.alt)
        if alt > best_hi[0]: best_hi = (alt, t)
        if alt < best_lo[0]: best_lo = (alt, t)
        t += timedelta(minutes=5)

    return {
        "sunrise": s["sunrise"],
        "sunset": s["sunset"],
        "moonrise": moonrise,
        "moonset": moonset,
        "overhead": best_hi[1],
        "underfoot": best_lo[1],
    }

# ----------------------------
# Bite curve (PURE FLOAT MATH)
# ----------------------------
def build_bite_curve(day, tz, events):
    centers = []
    weights = []

    def add(dt, w):
        if dt:
            centers.append(minutes_since_midnight(dt, tz))
            weights.append(w)

    add(events["overhead"], 1.0)
    add(events["underfoot"], 1.0)
    add(events["moonrise"], 0.6)
    add(events["moonset"], 0.6)
    add(events["sunrise"], 0.5)
    add(events["sunset"], 0.5)

    xs = []
    ys = []

    for m in range(1440):
        val = 25
        for c, w in zip(centers, weights):
            d = min(abs(m - c), 1440 - abs(m - c))
            sigma = 90 if w >= 1 else 55
            val += w * 60 * gaussian(d, 0, sigma)
        ys.append(clamp(val, 0, 100))
        xs.append(to_datetime(m, day, tz))

    return xs, ys

# ----------------------------
# Header
# ----------------------------
st.markdown("""
<div class="fishynw-card">
  <h2>🎣 FishyNW Fishing Times</h2>
  <div class="muted">Visual bite index based on moon and sun timing</div>
</div>
""", unsafe_allow_html=True)

tz = pytz.timezone("America/Los_Angeles")
today = datetime.now(tz).date()

# ----------------------------
# Controls
# ----------------------------
with st.container():
    st.markdown('<div class="fishynw-card">', unsafe_allow_html=True)
    day = st.date_input("Date", value=today)

    city = st.text_input("City", "Coeur d'Alene")
    state = st.text_input("State", "ID")

    if st.button("Generate Graph"):
        try:
            lat, lon, place = geocode_city_state(city, state)
            events = get_events(day, lat, lon, tz)
            xs, ys = build_bite_curve(day, tz, events)

            fig, ax = plt.subplots(figsize=(11, 4.8))
            ax.plot(xs, ys, linewidth=2)
            ax.set_ylim(0, 100)
            ax.set_ylabel("Bite Index")
            ax.set_title(f"Bite Index • {place}")

            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p"))
            ax.grid(alpha=0.25)

            st.pyplot(fig)

        except Exception as e:
            st.error(str(e))

    st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# Footer
# ----------------------------
st.markdown("""
<div class="footer">
  🎣 <b>FishyNW</b> • <a href="https://fishynw.com" target="_blank">fishynw.com</a><br>
  Pacific Northwest Fishing • #adventure
</div>
""", unsafe_allow_html=True)