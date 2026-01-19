# app.py
# Fishing Northwest — Best Fishing Times by Location (v1.1 wind fix, still v1.0-style simple)
# Runs on Streamlit Cloud or locally: streamlit run app.py

import math
from datetime import datetime, timedelta, date
import requests
import streamlit as st


APP_VERSION = "1.1"

# ----------------------------
# Page + Brand Styling
# ----------------------------
st.set_page_config(
    page_title="Best Fishing Times by Location | Fishing Northwest",
    page_icon="🎣",
    layout="centered",
)

st.markdown(
    """
<style>
/* overall spacing */
.block-container { padding-top: 0.6rem; padding-bottom: 1.4rem; max-width: 760px; }
h1, h2, h3 { letter-spacing: 0.2px; }
.small-muted { color: rgba(255,255,255,0.65); font-size: 0.95rem; }

/* cards */
.fn-card {
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.03);
  border-radius: 16px;
  padding: 14px 16px;
  margin: 10px 0px;
}
.fn-time { font-size: 1.05rem; opacity: 0.9; margin-bottom: 2px; }
.fn-value { font-size: 1.55rem; font-weight: 700; }

/* footer */
.fn-footer { margin-top: 24px; opacity: 0.55; font-size: 0.95rem; }
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# Helpers
# ----------------------------
UA_HEADERS = {
    "User-Agent": "FishingNorthwest-FishingTimesApp/1.1 (streamlit)",
    "Accept": "application/json",
}


def safe_get_json(url: str, timeout: int = 12):
    r = requests.get(url, headers=UA_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def ip_geolocate():
    """
    Best-effort IP geolocation (no city/state/zip shown in UI).
    May fail on some mobile networks / privacy settings.
    """
    try:
        data = safe_get_json("https://ipinfo.io/json", timeout=8)
        loc = data.get("loc")  # "lat,lon"
        if not loc:
            return None, None
        lat_s, lon_s = loc.split(",")
        return float(lat_s.strip()), float(lon_s.strip())
    except Exception:
        return None, None


def geocode_place_to_latlon(place: str):
    """
    Open-Meteo geocoding. Returns (lat, lon) or (None, None).
    """
    try:
        q = place.strip()
        if not q:
            return None, None
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={requests.utils.quote(q)}&count=1&language=en&format=json"
        )
        data = safe_get_json(url, timeout=10)
        results = data.get("results") or []
        if not results:
            return None, None
        return float(results[0]["latitude"]), float(results[0]["longitude"])
    except Exception:
        return None, None


def get_wind_by_hour(lat: float, lon: float):
    """
    Returns dict like {"00:00": 3.2, "04:00": 6.1, ...} in mph.
    Uses Open-Meteo hourly wind_speed_10m with timezone auto.
    """
    if lat is None or lon is None:
        return {}

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=wind_speed_10m"
        "&wind_speed_unit=mph"
        "&timezone=auto"
    )

    try:
        data = safe_get_json(url, timeout=12)
        times = data["hourly"]["time"]
        speeds = data["hourly"]["wind_speed_10m"]

        wind = {}
        for t, s in zip(times, speeds):
            # t example: "2026-01-18T00:00"
            try:
                dt = datetime.fromisoformat(t)
                key = dt.strftime("%H:00")
                # Keep first value per hour key (should be unique anyway)
                if key not in wind:
                    wind[key] = round(float(s), 1)
            except Exception:
                continue

        return wind
    except Exception:
        return {}


def get_sun_times(lat: float, lon: float, day: date):
    """
    Returns (sunrise_dt, sunset_dt) in local timezone as naive datetimes.
    Open-Meteo daily sunrise/sunset.
    """
    if lat is None or lon is None:
        return None, None

    start = day.isoformat()
    end = day.isoformat()

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start}&end_date={end}"
        "&daily=sunrise,sunset"
        "&timezone=auto"
    )

    try:
        data = safe_get_json(url, timeout=12)
        sunrise_s = (data.get("daily", {}).get("sunrise") or [None])[0]
        sunset_s = (data.get("daily", {}).get("sunset") or [None])[0]
        if not sunrise_s or not sunset_s:
            return None, None
        return datetime.fromisoformat(sunrise_s), datetime.fromisoformat(sunset_s)
    except Exception:
        return None, None


def moon_phase_fraction(day: date):
    """
    Approx moon phase [0..1). 0=new, 0.5=full-ish.
    Simple, good-enough algorithm for an app like this.
    """
    # Convert to days since known new moon (2000-01-06 18:14 UTC ~ JDN 2451550.1)
    # We'll use a lightweight approximation.
    y, m, d = day.year, day.month, day.day
    if m < 3:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    days_since = jd - 2451550.1
    synodic = 29.53058867
    phase = (days_since % synodic) / synodic
    return phase


def format_time(dt: datetime):
    return dt.strftime("%-I:%M %p") if hasattr(dt, "strftime") else "—"


def build_best_fishing_times(lat: float, lon: float, day: date):
    """
    Simple "best fishing times" approach:
    - 1 hr before/after sunrise
    - 1 hr before/after sunset
    - Boost note based on moon phase near new/full
    """
    sunrise, sunset = get_sun_times(lat, lon, day)
    if not sunrise or not sunset:
        return None

    morning_start = sunrise - timedelta(hours=1)
    morning_end = sunrise + timedelta(hours=1)
    evening_start = sunset - timedelta(hours=1)
    evening_end = sunset + timedelta(hours=1)

    phase = moon_phase_fraction(day)
    # closeness to new(0) or full(0.5)
    near_new = min(phase, 1 - phase)
    near_full = abs(phase - 0.5)

    note = "Normal conditions."
    if near_new <= 0.08:
        note = "Moon phase: near New Moon (often strong bite windows)."
    elif near_full <= 0.08:
        note = "Moon phase: near Full Moon (often strong bite windows)."

    return {
        "morning": (morning_start, morning_end),
        "evening": (evening_start, evening_end),
        "note": note,
    }


# ----------------------------
# Header (two spaces from top margin)
# ----------------------------
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("## Best fishing times by location")
st.markdown(
    '<div class="small-muted">To use this app, click on the side menu bar to enter your location and generate the best fishing times.</div>',
    unsafe_allow_html=True,
)

# ----------------------------
# Sidebar Inputs
# ----------------------------
with st.sidebar:
    st.markdown("### Location")
    mode = st.radio(
        "Choose location method",
        ["Use current location (best effort)", "Enter a place name", "Enter latitude & longitude"],
        index=0,
    )

    lat = lon = None

    if mode == "Use current location (best effort)":
        if st.button("Detect my location"):
            lat, lon = ip_geolocate()
            st.session_state["lat"] = lat
            st.session_state["lon"] = lon

        lat = st.session_state.get("lat")
        lon = st.session_state.get("lon")

        if lat is None or lon is None:
            st.caption("Tip: If detection fails, use Place name or Lat/Lon.")

    elif mode == "Enter a place name":
        place = st.text_input("Place name", placeholder="Example: Coeur d'Alene")
        if st.button("Use this place"):
            lat, lon = geocode_place_to_latlon(place)
            st.session_state["lat"] = lat
            st.session_state["lon"] = lon

        lat = st.session_state.get("lat")
        lon = st.session_state.get("lon")

    else:
        lat_in = st.text_input("Latitude", placeholder="47.67")
        lon_in = st.text_input("Longitude", placeholder="-116.78")
        if st.button("Use these coordinates"):
            try:
                lat = float(lat_in.strip())
                lon = float(lon_in.strip())
                st.session_state["lat"] = lat
                st.session_state["lon"] = lon
            except Exception:
                st.warning("Please enter valid numbers for latitude and longitude.")

        lat = st.session_state.get("lat")
        lon = st.session_state.get("lon")

    st.divider()
    st.markdown("### Day")
    selected_day = st.date_input("Select date", value=date.today())

    st.divider()
    show_debug = st.toggle("Show debug", value=False)
    if show_debug:
        st.write("DEBUG lat/lon:", lat, lon)
        st.write("App version:", APP_VERSION)

# ----------------------------
# Main Content
# ----------------------------
if lat is None or lon is None:
    st.info("Enter your location in the side menu to generate fishing times and wind.")
    st.markdown('<div class="fn-footer">Fishing Northwest</div>', unsafe_allow_html=True)
    st.stop()

# Best Fishing Times
times = build_best_fishing_times(lat, lon, selected_day)

if not times:
    st.warning("Could not generate fishing times for that location. Try another method.")
else:
    st.markdown("### Best fishing times")
    morning_start, morning_end = times["morning"]
    evening_start, evening_end = times["evening"]

    st.markdown(
        f"""
<div class="fn-card">
  <div class="fn-time">Morning window</div>
  <div class="fn-value">{format_time(morning_start)} – {format_time(morning_end)}</div>
</div>
<div class="fn-card">
  <div class="fn-time">Evening window</div>
  <div class="fn-value">{format_time(evening_start)} – {format_time(evening_end)}</div>
</div>
<div class="small-muted">{times["note"]}</div>
""",
        unsafe_allow_html=True,
    )

# Wind (every 4 hours)
st.markdown("### Wind (mph)")
wind = get_wind_by_hour(lat, lon)

display_hours = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]
for h in display_hours:
    val = wind.get(h)
    shown = f"{val} mph" if val is not None else "— mph"
    st.markdown(
        f"""
<div class="fn-card">
  <div class="fn-time">{h}</div>
  <div class="fn-value">{shown}</div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown('<div class="fn-footer">Fishing Northwest</div>', unsafe_allow_html=True)