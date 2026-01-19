# app.py
# Fishing Northwest — Best Fishing Times by Location (BY Company Edition) v2.0
# Mobile-first UI: larger tap targets, rounded cards, streamlined layout
# Sections (radio): Best fishing times / Trolling depth calculator
# Location: current (best effort), place name, or lat/lon
# NOTE: No city/state/zip shown in UI.

import math
from datetime import datetime, timedelta, date
import requests
import streamlit as st


APP_VERSION = "2.0 BY Company Edition"

# ----------------------------
# Page + Mobile-first Styling
# ----------------------------
st.set_page_config(
    page_title="Best Fishing Times by Location | Fishing Northwest",
    page_icon="🎣",
    layout="centered",
)

st.markdown(
    """
<style>
/* Mobile-first spacing */
.block-container {
  padding-top: 0.35rem;
  padding-bottom: 1.2rem;
  max-width: 640px;
}

/* Make sidebar a bit more usable on mobile */
section[data-testid="stSidebar"] {
  width: 320px !important;
}

/* Typography */
h1, h2, h3 { letter-spacing: 0.2px; }
.small-muted { color: rgba(255,255,255,0.65); font-size: 0.95rem; line-height: 1.35; }

/* Card style */
.fn-card {
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.035);
  border-radius: 22px;
  padding: 14px 16px;
  margin: 10px 0px;
}
.fn-title { font-size: 1.02rem; opacity: 0.85; margin-bottom: 4px; }
.fn-value { font-size: 1.55rem; font-weight: 750; letter-spacing: 0.2px; }
.fn-sub   { font-size: 0.92rem; opacity: 0.68; margin-top: 6px; }

/* Make buttons/toggles easier to tap */
button[kind="primary"], button[kind="secondary"], .stButton button {
  border-radius: 16px !important;
  padding: 0.65rem 0.9rem !important;
}

/* Inputs rounded */
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div {
  border-radius: 16px !important;
}

/* Radio tiles feel */
div[role="radiogroup"] label {
  border-radius: 16px !important;
  padding: 8px 10px !important;
}

/* Compact hr/divider */
hr { margin: 0.6rem 0 !important; opacity: 0.25; }

/* Footer */
.fn-footer { margin-top: 18px; opacity: 0.55; font-size: 0.95rem; }
</style>
""",
    unsafe_allow_html=True,
)

UA_HEADERS = {
    "User-Agent": "FishingNorthwest-FishingTimesApp/2.0 (BY Company Edition) (streamlit)",
    "Accept": "application/json",
}


# ----------------------------
# Helpers
# ----------------------------
def safe_get_json(url: str, timeout: int = 12):
    r = requests.get(url, headers=UA_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def ip_geolocate():
    """Best-effort IP geolocation. Returns (lat, lon) or (None, None)."""
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
    """Open-Meteo geocoding. Returns (lat, lon) or (None, None). Does not display resolved place."""
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
    """Returns dict like {"00:00": 3.2, ...} in mph."""
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
            try:
                dt = datetime.fromisoformat(t)
                key = dt.strftime("%H:00")
                if key not in wind:
                    wind[key] = round(float(s), 1)
            except Exception:
                continue
        return wind
    except Exception:
        return {}


def get_sun_times(lat: float, lon: float, day: date):
    """Returns (sunrise_dt, sunset_dt) in local timezone as naive datetimes."""
    if lat is None or lon is None:
        return None, None

    start = day.isoformat()
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={start}&end_date={start}"
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
    """Approx moon phase [0..1). 0=new, 0.5=full-ish."""
    y, m, d = day.year, day.month, day.day
    if m < 3:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    days_since = jd - 2451550.1
    synodic = 29.53058867
    return (days_since % synodic) / synodic


def format_time(dt: datetime):
    try:
        return dt.strftime("%I:%M %p").lstrip("0")
    except Exception:
        return "—"


def build_best_fishing_times(lat: float, lon: float, day: date):
    sunrise, sunset = get_sun_times(lat, lon, day)
    if not sunrise or not sunset:
        return None

    morning_start = sunrise - timedelta(hours=1)
    morning_end = sunrise + timedelta(hours=1)
    evening_start = sunset - timedelta(hours=1)
    evening_end = sunset + timedelta(hours=1)

    phase = moon_phase_fraction(day)
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


def calc_trolling_depth(speed_mph: float, weight_oz: float, line_out_ft: float, line_type: str):
    """
    Flatline trolling depth estimate (rule-of-thumb).
    Depth increases with weight and line out, decreases with speed and drag.
    """
    if speed_mph <= 0 or weight_oz <= 0 or line_out_ft <= 0:
        return None, "Enter positive values."

    drag = {
        "Braid": 1.00,
        "Fluorocarbon": 1.12,
        "Monofilament": 1.20,
    }.get(line_type, 1.10)

    speed_factor = (speed_mph ** 1.35)
    COEF = 0.135
    depth = COEF * (weight_oz / (drag * speed_factor)) * line_out_ft
    depth = max(0.0, min(depth, 250.0))
    return round(depth, 1), "Rule-of-thumb estimate. Current and lure drag will change depth."


# ----------------------------
# Header (tight + mobile)
# ----------------------------
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("## Best fishing times by location")
st.markdown(
    '<div class="small-muted">Open the side menu to set your location and switch tools.</div>',
    unsafe_allow_html=True,
)

# ----------------------------
# Sidebar (streamlined)
# ----------------------------
with st.sidebar:
    st.markdown("### BY Company Edition")
    st.caption(f"Version {APP_VERSION}")

    st.markdown("#### Section")
    page = st.radio(
        "Section",
        ["Best fishing times", "Trolling depth calculator"],
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown("#### Location")
    mode = st.radio(
        "Location method",
        ["Current location (best effort)", "Place name", "Latitude & longitude"],
        index=0,
        label_visibility="collapsed",
    )

    lat = lon = None

    if mode == "Current location (best effort)":
        # One-tap primary action
        if st.button("Detect location", use_container_width=True):
            lat, lon = ip_geolocate()
            st.session_state["lat"] = lat
            st.session_state["lon"] = lon

        lat = st.session_state.get("lat")
        lon = st.session_state.get("lon")

        if lat is None or lon is None:
            st.caption("If this fails, use Place name or Lat/Lon.")

    elif mode == "Place name":
        place = st.text_input("Place name", placeholder="Example: Fernan Lake", label_visibility="collapsed")
        if st.button("Use place", use_container_width=True):
            lat, lon = geocode_place_to_latlon(place)
            st.session_state["lat"] = lat
            st.session_state["lon"] = lon

        lat = st.session_state.get("lat")
        lon = st.session_state.get("lon")

    else:
        c1, c2 = st.columns(2)
        with c1:
            lat_in = st.text_input("Latitude", placeholder="47.67", label_visibility="collapsed")
        with c2:
            lon_in = st.text_input("Longitude", placeholder="-116.78", label_visibility="collapsed")

        if st.button("Use coordinates", use_container_width=True):
            try:
                lat = float(lat_in.strip())
                lon = float(lon_in.strip())
                st.session_state["lat"] = lat
                st.session_state["lon"] = lon
            except Exception:
                st.warning("Enter valid numbers for latitude and longitude.")

        lat = st.session_state.get("lat")
        lon = st.session_state.get("lon")

    st.divider()

    st.markdown("#### Date")
    selected_day = st.date_input("Date", value=date.today(), label_visibility="collapsed")

    st.divider()
    show_debug = st.toggle("Show debug", value=False)
    if show_debug:
        st.write("DEBUG lat/lon:", lat, lon)

# ----------------------------
# Guard
# ----------------------------
if lat is None or lon is None:
    st.info("Set your location in the side menu to continue.")
    st.markdown('<div class="fn-footer">Fishing Northwest</div>', unsafe_allow_html=True)
    st.stop()

# ----------------------------
# Best Fishing Times page
# ----------------------------
if page == "Best fishing times":
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
  <div class="fn-title">Morning window</div>
  <div class="fn-value">{format_time(morning_start)} – {format_time(morning_end)}</div>
</div>
<div class="fn-card">
  <div class="fn-title">Evening window</div>
  <div class="fn-value">{format_time(evening_start)} – {format_time(evening_end)}</div>
</div>
<div class="small-muted">{times["note"]}</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("### Wind (mph)")
    wind = get_wind_by_hour(lat, lon)

    # Mobile-first: two-column grid feel (but still readable)
    hours = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]
    # Build rows of 2 cards
    for i in range(0, len(hours), 2):
        left = hours[i]
        right = hours[i + 1] if i + 1 < len(hours) else None
        c1, c2 = st.columns(2)
        with c1:
            v = wind.get(left)
            shown = f"{v} mph" if v is not None else "— mph"
            st.markdown(
                f"""
<div class="fn-card">
  <div class="fn-title">{left}</div>
  <div class="fn-value">{shown}</div>
</div>
""",
                unsafe_allow_html=True,
            )
        if right:
            with c2:
                v = wind.get(right)
                shown = f"{v} mph" if v is not None else "— mph"
                st.markdown(
                    f"""
<div class="fn-card">
  <div class="fn-title">{right}</div>
  <div class="fn-value">{shown}</div>
</div>
""",
                    unsafe_allow_html=True,
                )
        else:
            with c2:
                st.write("")

# ----------------------------
# Trolling Depth page
# ----------------------------
else:
    st.markdown("### Trolling depth calculator")
    st.markdown(
        '<div class="small-muted">Flatline trolling estimate. Enter your speed, weight, line out, and line type.</div>',
        unsafe_allow_html=True,
    )

    # Mobile-first: stacked inputs (less side-by-side)
    speed_mph = st.number_input("Trolling speed (mph)", min_value=0.0, value=1.5, step=0.1)
    weight_oz = st.number_input("Weight (oz)", min_value=0.0, value=8.0, step=0.5)
    line_out_ft = st.number_input("Line out (feet)", min_value=0.0, value=120.0, step=5.0)
    line_type = st.radio("Line type", ["Braid", "Fluorocarbon", "Monofilament"], index=0, horizontal=True)

    depth, note = calc_trolling_depth(speed_mph, weight_oz, line_out_ft, line_type)

    st.markdown(
        f"""
<div class="fn-card">
  <div class="fn-title">Estimated depth</div>
  <div class="fn-value">{depth if depth is not None else "—"} ft</div>
  <div class="fn-sub">{note}</div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Quick presets")
    st.markdown('<div class="small-muted">Tap one, then tweak line out.</div>', unsafe_allow_html=True)

    p1, p2, p3 = st.columns(3)
    with p1:
        if st.button("Kokanee", use_container_width=True):
            st.session_state["spd"] = 1.3
            st.session_state["wt"] = 6.0
            st.session_state["lt"] = "Braid"
    with p2:
        if st.button("Trout", use_container_width=True):
            st.session_state["spd"] = 1.6
            st.session_state["wt"] = 4.0
            st.session_state["lt"] = "Braid"
    with p3:
        if st.button("Deep", use_container_width=True):
            st.session_state["spd"] = 1.5
            st.session_state["wt"] = 8.0
            st.session_state["lt"] = "Braid"

    if "spd" in st.session_state:
        st.info(
            f"Preset loaded: speed {st.session_state['spd']} mph, weight {st.session_state['wt']} oz, line {st.session_state['lt']}."
        )

st.markdown('<div class="fn-footer">Fishing Northwest</div>', unsafe_allow_html=True)