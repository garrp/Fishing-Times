import math
from datetime import datetime, date, timedelta
import pytz
import requests
import streamlit as st
import matplotlib.pyplot as plt

from astral import LocationInfo
from astral.sun import sun
import ephem


# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(
    page_title="FishyNW Fishing Times",
    layout="wide",
)

# ----------------------------
# Styling
# ----------------------------
st.markdown("""
<style>
.block-container { max-width: 1000px; padding-top: 1.2rem; }
.fishynw-card {
  background: rgba(17,26,46,.55);
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(255,255,255,.10);
}
.muted { color: rgba(235,240,255,.70); }
.footer {
  margin-top: 26px;
  text-align:center;
  font-size:12px;
  color:#9fb2d9;
}
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

def deg_to_compass(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    ix = int((deg / 22.5) + 0.5) % 16
    return dirs[ix]

# ----------------------------
# Geocoding (Open-Meteo)
# ----------------------------
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
# Sun & Moon events
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
    except:
        pass
    try:
        moonset = ephem.Date(obs.next_setting(moon)).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except:
        pass

    best_hi = (-999, None)
    best_lo = (999, None)
    t = tz.localize(datetime(day.year, day.month, day.day))
    for _ in range(288):
        obs.date = t.astimezone(pytz.utc)
        moon.compute(obs)
        alt = float(moon.alt)
        if alt > best_hi[0]:
            best_hi = (alt, t)
        if alt < best_lo[0]:
            best_lo = (alt, t)
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
# Bite curve
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

    x = []
    y = []

    for m in range(1440):
        val = 25
        for c, w in zip(centers, weights):
            d = min(abs(m - c), 1440 - abs(m - c))
            val += w * 60 * gaussian(d, 0, 90)
        x.append(m / 60)
        y.append(clamp(val, 0, 100))

    return x, y

# ----------------------------
# Wind (every 2 hours)
# ----------------------------
def fetch_wind(day, lat, lon, tz_name):
    url = "https://api.open-meteo.com/v1/forecast"
    r = requests.get(url, params={
        "latitude": lat,
        "longitude": lon,
        "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "wind_speed_unit": "mph",
        "timezone": tz_name,
    }, timeout=10)
    r.raise_for_status()
    data = r.json()["hourly"]

    bullets = []
    for i, t in enumerate(data["time"]):
        hour = int(t.split("T")[1][:2])
        if hour % 2 == 0:
            direction = deg_to_compass(data["wind_direction_10m"][i])
            bullets.append(
                f"**{hour % 12 or 12} {'AM' if hour < 12 else 'PM'}**: "
                f"{int(data['wind_speed_10m'][i])} mph {direction}, "
                f"gust {int(data['wind_gusts_10m'][i])} mph"
            )
    return bullets

# ----------------------------
# UI
# ----------------------------
st.markdown('<div class="fishynw-card">', unsafe_allow_html=True)
st.image("FishyNW-logo.png", width=220)
st.markdown("<h2>Fishing Times</h2>", unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

tz = pytz.timezone("America/Los_Angeles")
day = st.date_input("Date", value=datetime.now(tz).date())
city = st.text_input("City", "Coeur d'Alene")
state = st.text_input("State", "ID")

if st.button("Generate"):
    lat, lon, place = geocode_city_state(city, state)

    events = get_events(day, lat, lon, tz)
    x, y = build_bite_curve(day, tz, events)

    # Static graph
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(x, y, linewidth=2)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Time of Day")
    ax.set_ylabel("Bite Index")
    ax.set_title(f"Bite Index • {place}")
    ax.set_xticks(range(0, 25, 2))
    ax.grid(alpha=0.3)

    st.pyplot(fig)

    # Wind bullets
    st.markdown("### Wind (every 2 hours)")
    for line in fetch_wind(day, lat, lon, tz.zone):
        st.markdown(f"- {line}")

# ----------------------------
# Footer
# ----------------------------
st.markdown("""
<div class="footer">
  <b>FishyNW</b> • <a href="https://fishynw.com" target="_blank">fishynw.com</a>
</div>
""", unsafe_allow_html=True)