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
# Cached API calls (safe)
# -----------------------------
@st.cache_data(ttl=86400)
def geocode_city(city: str):
    """
    Open-Meteo geocoding (no key). Cached 24h.
    Returns (label, lat, lon) or (None, None, None).
    """
    if not city or not city.strip():
        return None, None, None

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city.strip(), "count": 1, "language": "en", "format": "json"}

    try:
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
    except Exception:
        return None, None, None


@st.cache_data(ttl=1800)
def fetch_weather(lat: float, lon: float, day: date):
    """
    Open-Meteo forecast (no key). Cached 30m.
    Returns JSON with hourly wind speed + direction, or None on failure.
    """
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

    try:
        r = SESSION.get(url, params=params, timeout=(8, 25))
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


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
    """
    Picks entries every 4 hours and keeps only the selected day.
    Returns list of (datetime, mph, dir_deg).
    """
    out = []
    for i in range(0, len(times), 4):
        t = parse_iso_dt(times[i])
        if t.date() == target_day:
            out.append((t, float(speeds[i]), float(dirs[i])))
    return out


def make_wind_chart(times, speeds, title: str):
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
# UI
# -----------------------------
st.set_page_config(page_title=APP_TITLE, layout="centered")

logo = safe_read_logo(LOGO_FILENAME)
if logo:
    st.image(logo, use_container_width=True)

st.title(APP_TITLE)
st.caption("One day only. Wind shown every 4 hours with direction and mph.")

with st.form("inputs"):
    col1, col2 = st.columns(2)
    with col1:
        city = st.text_input("City / place name", "Coeur d'Alene, ID")
        manual = st.checkbox("Use manual lat/lon")
    with col2:
        target_date = st.date_input("Date", date.today())
        show_chart = st.checkbox("Show wind chart image", value=True)

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
    if lat is None or lon is None:
        st.warning("City lookup failed or timed out. Try again or switch to manual lat/lon.")
        st.stop()

st.markdown("### Location")
st.write(f"{place_label} (lat {lat:.4f}, lon {lon:.4f})")

# Fetch weather (graceful failure)
wx = fetch_weather(lat, lon, target_date)
if wx is None:
    st.warning(
        "Weather service is temporarily unavailable or rate-limited. "
        "Please try again in a minute."
    )
    st.stop()

hourly = wx.get("hourly") or {}
times = hourly.get("time") or []
speeds = hourly.get("wind_speed_10m") or []
dirs = hourly.get("wind_direction_10m") or []

if not times or not speeds or not dirs:
    st.warning("No wind data returned for this location/date.")
    st.stop()

# Wind bullets (every 4 hours)
st.markdown("### Wind (every 4 hours)")
picked = pick_wind_every_4_hours(times, speeds, dirs, target_date)

if not picked:
    # fallback: show first few entries
    for i in range(min(6, len(times))):
        ttxt = parse_iso_dt(times[i]).strftime("%-I:%M %p")
        st.write(f"• {ttxt}: {float(speeds[i]):.0f} mph ({wind_dir_to_text(float(dirs[i]))})")
else:
    for t, mph, ddeg in picked:
        st.write(f"• {t.strftime('%-I:%M %p')}: {mph:.0f} mph ({wind_dir_to_text(ddeg)})")

# Optional chart image
if show_chart:
    st.markdown("### Wind chart (image)")
    chart_buf = make_wind_chart(times, speeds, f"Wind speed (mph) - {place_label}")
    st.image(chart_buf, use_container_width=True)

st.caption("FishyNW • simple • one-day • wind every 4 hours")