import io
import math
import time
import requests
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, date, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# -----------------------------
# FishyNW Fishing Times (Streamlit)
# - One day only
# - Wind every 4 hours (text bullets)
# - Static graph image
# - User inputs (location, date, species, manual lat/lon)
# - Resilient network calls (cache + retry + longer timeouts)
# -----------------------------

APP_TITLE = "FishyNW Fishing Times"
LOGO_FILENAME = "FishyNW-logo.png"


def safe_read_logo(path: str):
    try:
        return open(path, "rb").read()
    except Exception:
        return None


def make_session():
    session = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


SESSION = make_session()


@st.cache_data(ttl=86400)
def geocode_city(city: str):
    """
    Geocode using Open-Meteo Geocoding API (no key).
    Cached for 24 hours. Retries on transient failures.
    Returns (label, lat, lon) or (None, None, None).
    """
    if not city or not city.strip():
        return None, None, None

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city.strip(),
        "count": 1,
        "language": "en",
        "format": "json",
    }

    # Longer timeout helps on Streamlit Cloud/mobile
    r = SESSION.get(url, params=params, timeout=(8, 25))
    if r.status_code != 200:
        return None, None, None

    data = r.json()
    results = data.get("results") or []
    if not results:
        return None, None, None

    top = results[0]
    name = top.get("name")
    admin1 = top.get("admin1")
    country = top.get("country")
    label = ", ".join([x for x in [name, admin1, country] if x])
    return label, float(top["latitude"]), float(top["longitude"])


@st.cache_data(ttl=1800)
def fetch_weather(lat: float, lon: float, day: date):
    """
    Fetch hourly weather for one day from Open-Meteo.
    Cached for 30 minutes to avoid rate limits and reduce calls.
    Retries on transient failures.
    """
    start = day.isoformat()
    end = (day + timedelta(days=1)).isoformat()

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wind_speed_10m,wind_direction_10m",
        "daily": "sunrise,sunset",
        "timezone": "auto",
        "start_date": start,
        "end_date": end,
        "wind_speed_unit": "mph",
    }

    r = SESSION.get(url, params=params, timeout=(8, 25))
    r.raise_for_status()
    return r.json()


def parse_iso_dt(s: str):
    return datetime.fromisoformat(s)


def wind_dir_to_text(deg: float):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ix = int((deg + 22.5) // 45) % 8
    return dirs[ix]


def compute_fishing_windows(sunrise: datetime, sunset: datetime):
    """
    Simple, dependable windows (not solunar):
    - Dawn: sunrise - 1:00 to sunrise + 1:30
    - Midday: 11:00 to 1:00 (local)
    - Dusk: sunset - 1:30 to sunset + 0:45
    """
    dawn_start = sunrise - timedelta(hours=1)
    dawn_end = sunrise + timedelta(hours=1, minutes=30)

    midday_start = sunrise.replace(hour=11, minute=0)
    midday_end = sunrise.replace(hour=13, minute=0)

    dusk_start = sunset - timedelta(hours=1, minutes=30)
    dusk_end = sunset + timedelta(minutes=45)

    return [
        ("Early", dawn_start, dawn_end),
        ("Midday", midday_start, midday_end),
        ("Evening", dusk_start, dusk_end),
    ]


def pick_wind_every_4_hours(times, speeds, dirs):
    picked = []
    for i in range(0, len(times), 4):
        t = parse_iso_dt(times[i])
        picked.append((t, float(speeds[i]), float(dirs[i])))
    return picked


def make_wind_chart(times, speeds, title):
    x = [parse_iso_dt(t) for t in times]
    y = [float(v) for v in speeds]

    fig = plt.figure(figsize=(10, 3.2), dpi=160)
    ax = fig.add_subplot(111)
    ax.plot(x, y)
    ax.set_title(title)
    ax.set_ylabel("Wind (mph)")
    ax.set_xlabel("Time")
    fig.autofmt_xdate()

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title=APP_TITLE, layout="centered")

logo_bytes = safe_read_logo(LOGO_FILENAME)
if logo_bytes:
    st.image(logo_bytes, use_container_width=True)

st.title(APP_TITLE)
st.caption("One-day fishing outlook with wind text every 4 hours. Static chart image.")

with st.form("inputs"):
    st.subheader("Inputs")

    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City / place name", value="Coeur d'Alene, ID")
        manual = st.checkbox("Use manual lat/lon instead of city")
    with col2:
        target_date = st.date_input("Date", value=date.today())
        species = st.selectbox(
            "Target species",
            [
                "Kokanee",
                "Rainbow trout",
                "Walleye",
                "Smallmouth bass",
                "Largemouth bass",
                "Chinook",
                "Lake trout",
                "Catfish",
                "Other",
            ],
            index=0,
        )

    lat = None
    lon = None
    if manual:
        c3, c4 = st.columns(2)
        with c3:
            lat = st.number_input("Latitude", value=47.677700, format="%.6f")
        with c4:
            lon = st.number_input("Longitude", value=-116.780500, format="%.6f")

    show_chart = st.checkbox("Show wind chart image", value=True)
    submitted = st.form_submit_button("Get fishing outlook", use_container_width=True)

if not submitted:
    st.stop()

# Resolve location
place_label = None
if manual:
    place_label = "Custom location"
    lat = float(lat)
    lon = float(lon)
else:
    place_label, lat, lon = geocode_city(city)
    if lat is None or lon is None:
        st.warning(
            "City lookup timed out or returned no results. Switch to manual lat/lon and try again."
        )
        st.stop()

st.markdown("### Location")
st.write(f"{place_label} (lat {lat:.4f}, lon {lon:.4f})")

# Fetch weather
try:
    wx = fetch_weather(lat, lon, target_date)
except Exception as e:
    st.error("Weather lookup failed. Try again in a moment.")
    st.write(str(e))
    st.stop()

hourly = wx.get("hourly") or {}
daily = wx.get("daily") or {}

times = hourly.get("time") or []
wind_speeds = hourly.get("wind_speed_10m") or []
wind_dirs = hourly.get("wind_direction_10m") or []

sunrise_list = daily.get("sunrise") or []
sunset_list = daily.get("sunset") or []

if not times or not wind_speeds or not wind_dirs:
    st.error("No hourly wind data returned for this location/date.")
    st.stop()

sunrise = parse_iso_dt(sunrise_list[0]) if sunrise_list else None
sunset = parse_iso_dt(sunset_list[0]) if sunset_list else None

st.markdown("### Daylight")
if sunrise and sunset:
    st.write(f"Sunrise: {sunrise.strftime('%-I:%M %p')}")
    st.write(f"Sunset: {sunset.strftime('%-I:%M %p')}")
else:
    st.write("Sunrise/sunset unavailable for this request.")

st.markdown("### Best Fishing Windows (simple)")
if sunrise and sunset:
    windows = compute_fishing_windows(sunrise, sunset)
    for label, start_dt, end_dt in windows:
        st.write(
            f"• {label}: {start_dt.strftime('%-I:%M %p')} - {end_dt.strftime('%-I:%M %p')}"
        )
else:
    st.write("• Early: 6:00 AM - 8:00 AM")
    st.write("• Midday: 11:00 AM - 1:00 PM")
    st.write("• Evening: 5:30 PM - 8:00 PM")

st.markdown("### Wind Outlook (every 4 hours)")
picked = pick_wind_every_4_hours(times, wind_speeds, wind_dirs)

picked_same_day = []
for t, spd, d in picked:
    if t.date() == target_date:
        picked_same_day.append((t, spd, d))

if not picked_same_day:
    picked_same_day = picked[:6]

for t, spd, d in picked_same_day:
    d_txt = wind_dir_to_text(d)
    st.write(f"• {t.strftime('%-I:%M %p')}: {spd:.0f} mph ({d_txt})")

st.markdown("### Species Note")
if species in ["Kokanee", "Rainbow trout", "Chinook", "Lake trout"]:
    st.write("• Trolling windows usually line up best with dawn and dusk. Watch wind shifts for cleaner passes.")
elif species in ["Smallmouth bass", "Largemouth bass"]:
    st.write("• Early and late are usually best. If wind picks up, fish wind-blown banks and points.")
elif species == "Walleye":
    st.write("• Low light helps. If wind is steady, focus on edges and current breaks; jig or troll based on mood.")
elif species == "Catfish":
    st.write("• Evening into night is often strongest. Wind matters less than bait placement and scent trail.")
else:
    st.write("• Start at dawn. If action is slow, move with wind and structure until you find bait or marks.")

if show_chart:
    st.markdown("### Wind Chart (image)")
    chart_buf = make_wind_chart(times, wind_speeds, f"Wind speed (mph) - {place_label}")
    st.image(chart_buf, use_container_width=True)

st.caption("FishyNW - one-day outlook. Wind displayed as bullets every 4 hours.")