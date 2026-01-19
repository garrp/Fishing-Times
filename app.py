# app.py — FishyNW Version 1.0 (simple + stable)
# One page only: Date + City/State + static bite index graph + wind every 4 hours + FishyNW footer/link

import math
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import requests
import streamlit as st
import matplotlib.pyplot as plt

from astral import LocationInfo
from astral.sun import sun


# =========================
# App config
# =========================
st.set_page_config(page_title="FishyNW Fishing Times", layout="wide")
TZ = pytz.timezone("America/Los_Angeles")

# =========================
# Styling
# =========================
st.markdown(
    """
<style>
.block-container { max-width: 1000px; padding-top: 1.2rem; }
.card {
  background: rgba(17,26,46,.55);
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(255,255,255,.10);
  margin-bottom: 14px;
}
.footer {
  margin-top: 26px;
  text-align:center;
  font-size:12px;
  color:#9fb2d9;
}
.footer a { color:#6fd3ff; text-decoration:none; }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# Helpers
# =========================
def clamp(x, a, b):
    return max(a, min(b, x))

def gaussian(x, mu, sigma):
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)

def show_logo():
    for p in ["FishyNW-logo.png", "assets/FishyNW-logo.png", "images/FishyNW-logo.png"]:
        if Path(p).exists():
            st.image(p, width=220)
            return
    st.markdown("**FishyNW**")

def deg_to_compass(deg):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[int((deg / 22.5) + 0.5) % 16]

def minutes_since_midnight(dt, tz):
    local = dt.astimezone(tz)
    return local.hour * 60 + local.minute

# =========================
# Geocoding
# =========================
def geocode_city_state(city, state):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(url, params={"name": city, "count": 20}, timeout=10)
    r.raise_for_status()

    results = r.json().get("results", [])
    if not results:
        raise ValueError("City not found")

    state_u = state.upper()
    for item in results:
        if (item.get("country_code") == "US") and (state_u in (item.get("admin1", "")).upper()):
            return float(item["latitude"]), float(item["longitude"]), f"{item['name']}, {item['admin1']}"

    item = results[0]
    admin1 = item.get("admin1", "")
    return float(item["latitude"]), float(item["longitude"]), f"{item.get('name','Location')}, {admin1}".strip(", ")

# =========================
# Sun events (Astral only)
# =========================
def get_sun_events(day, lat, lon, tz):
    loc = LocationInfo("", "", tz.zone, lat, lon)
    s = sun(loc.observer, date=day, tzinfo=tz)
    return {"sunrise": s["sunrise"], "sunset": s["sunset"]}

# =========================
# Bite curve (simple v1.0)
# Peaks: sunrise + sunset only
# =========================
def build_bite_curve(day, tz, sunrise_dt, sunset_dt):
    centers = [
        minutes_since_midnight(sunrise_dt, tz),
        minutes_since_midnight(sunset_dt, tz),
    ]

    x, y = [], []
    for m in range(1440):
        val = 25.0
        for c in centers:
            d = min(abs(m - c), 1440 - abs(m - c))
            val += 65.0 * gaussian(d, 0.0, 90.0)
        x.append(m / 60.0)
        y.append(clamp(val, 0, 100))
    return x, y

# =========================
# Wind (every 4 hours)
# =========================
def fetch_wind_4h(day, lat, lon, tz_name):
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
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
        bullets.append(f"**{label}**: {int(round(s))} mph {deg_to_compass(float(d))}, gust {int(round(g))} mph")
    return bullets

# =========================
# UI
# =========================
st.markdown("<div class='card'>", unsafe_allow_html=True)
show_logo()
st.markdown("## Best Fishing Times")
st.markdown("</div>", unsafe_allow_html=True)

day = st.date_input("Date", value=datetime.now(TZ).date())
city = st.text_input("City", "Coeur d'Alene")
state = st.text_input("State", "ID")

if st.button("Generate"):
    try:
        lat, lon, place = geocode_city_state(city, state)
        events = get_sun_events(day, lat, lon, TZ)

        x, y = build_bite_curve(day, TZ, events["sunrise"], events["sunset"])

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(x, y, linewidth=2)
        ax.set_xlim(0, 24)
        ax.set_ylim(0, 100)
        ax.set_xticks(range(0, 25, 4))
        ax.set_xlabel("Time of Day")
        ax.set_ylabel("Bite Index")
        ax.set_title(f"Bite Index • {place}")
        ax.grid(alpha=0.3)
        st.pyplot(fig, clear_figure=True)

        st.markdown("### Wind (every 4 hours)")
        for w in fetch_wind_4h(day, lat, lon, TZ.zone):
            st.markdown(f"- {w}")

    except Exception as e:
        st.error(str(e))

st.markdown(
    """
<div class="footer">
  <b>FishyNW</b> • <a href="https://fishynw.com" target="_blank" rel="noopener">fishynw.com</a>
</div>
""",
    unsafe_allow_html=True,
)