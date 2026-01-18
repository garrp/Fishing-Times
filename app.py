import io
import requests
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, date, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

APP_TITLE = "FishyNW Wind (Every 4 Hours)"
LOGO_FILENAME = "FishyNW-logo.png"

# -----------------------------
# Network session with retries
# -----------------------------
def make_session():
    s = requests.Session()
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
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


SESSION = make_session()


def safe_read_logo(path: str):
    try:
        return open(path, "rb").read()
    except Exception:
        return None


# -----------------------------
# Cached API calls
# -----------------------------
@st.cache_data(ttl=86400)
def geocode_city(city: str):
    if not city or not city.strip():
        return None, None, None

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": city.strip(),
        "count": 1,
        "language": "en",
        "format": "json",
    }

    r = SESSION.get(url, params=params, timeout=(8, 25))
    if r.status_code != 200:
        return None, None, None

    data = r.json()
    results = data.get("results") or []
    if not results:
        return None, None, None

    top = results[0]
    label = ", ".join(
        [x for x in [top.get("name"), top.get("admin1"), top.get("country")] if x]
    )
    return label, float(top["latitude"]), float(top["longitude"])


@st.cache_data(ttl=1800)
def fetch_weather(lat: float, lon: float, day: date):
    start = day.isoformat()
    end = (day + timedelta(days=1)).isoformat()

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wind_speed_10m,wind_direction_10m",
        "timezone": "auto",
        "start_date": start,
        "end_date": end,
        "wind_speed_unit": "mph",
    }

    r = SESSION.get(url, params=params, timeout=(8, 25))
    r.raise_for_status()
    return r.json()


# -----------------------------
# Helpers
# -----------------------------
def parse_iso_dt(s: str):
    return datetime.fromisoformat(s)


def wind_dir_to_text(deg: float):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ix = int((deg + 22.5) // 45) % 8
    return dirs[ix]


def pick_wind_every_4_hours(times, speeds, dirs, target_day):
    out = []
    for i in range(0, len(times), 4):
        t = parse_iso_dt(times[i])
        if t.date() == target_day:
            out.append((t, speeds[i], dirs[i]))
    return out


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title=APP_TITLE, layout="centered")

logo = safe_read_logo(LOGO_FILENAME)
if logo:
    st.image(logo, use_container_width=True)

st.title(APP_TITLE)
st.caption("Wind forecast shown every 4 hours with direction and mph.")

with st.form("inputs"):
    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City / place name", "Coeur d'Alene, ID")
        manual = st.checkbox("Use manual lat/lon")
    with col2:
        target_date = st.date_input("Date", date.today())

    lat = lon = None
    if manual:
        c3, c4 = st.columns(2)
        with c3:
            lat = st.number_input("Latitude", value=47.6777, format="%.6f")
        with c4:
            lon = st.number_input("Longitude", value=-116.7805, format="%.6f")

    submitted = st.form_submit_button("Get wind", use_container_width=True)

if not submitted:
    st.stop()

# Resolve location
if manual:
    place_label = "Custom location"
    lat, lon = float(lat), float(lon)
else:
    place_label, lat, lon = geocode_city(city)
    if lat is None:
        st.warning("City lookup failed. Try again or use manual coordinates.")
        st.stop()

st.markdown("### Location")
st.write(f"{place_label} (lat {lat:.4f}, lon {lon:.4f})")

# Fetch weather
wx = fetch_weather(lat, lon, target_date)
hourly = wx.get("hourly", {})
times = hourly.get("time", [])
speeds = hourly.get("wind_speed_10m", [])
dirs = hourly.get("wind_direction_10m", [])

if not times:
    st.error("No wind data returned.")
    st.stop()

# Output
st.markdown("### Wind (every 4 hours)")
picked = pick_wind_every_4_hours(times, speeds, dirs, target_date)

for t, spd, d in picked:
    st.write(
        f"• {t.strftime('%-I:%M %p')}: {spd:.0f} mph ({wind_dir_to_text(d)})"
    )

st.caption("FishyNW • simple • one-day • low API usage")