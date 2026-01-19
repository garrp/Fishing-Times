# app.py
# Fishing Northwest — Best Fishing Times by Location (BY Company Edition) v2.1
# Mobile-first UI: rounded cards, larger tap targets, streamlined sidebar
# Sections (radio): Best fishing times / Trolling depth calculator
# Location: current (best effort) OR place name (NO latitude/longitude shown anywhere, no debug)

import math
from datetime import datetime, timedelta, date
import requests
import streamlit as st


APP_VERSION = "2.1 BY Company Edition"

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

/* Sidebar width (helps on mobile) */
section[data-testid="stSidebar"] { width: 320px !important; }

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

/* Tap targets */
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

/* Radio */
div[role="radiogroup"] label {
  border-radius: 16px !important;
  padding: 8px 10px !important;
}

hr { margin: 0.6rem 0 !important; opacity: 0.25; }

/* Footer */
.fn-footer { margin-top: 18px; opacity: 0.55; font-size: 0.95rem; }
</style>
""",
    unsafe_allow_html=True,
)

UA_HEADERS = {
    "User-Agent": "FishingNorthwest-FishingTimesApp/2.1 (BY Company Edition) (streamlit)",
    "Accept": "application/json",
}

# ----------------------------
# Helpers
# ----------------------------
def safe_get_json(url: str, timeout: int = 12):
    r = requests.get(url, headers=UA_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def ip_geolocate_latlon():
    """
    Best-effort IP geolocation.
    Internal only — we never display lat/lon anywhere in the UI.
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
    Open-Meteo geocoding. Internal only — we never display resolved place details.
    Returns (lat, lon) or (None, None).
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
    Depth increases with weight + line out; decreases with speed + line drag.
    """
    if speed_mph <= 0 or weight_oz <= 0 or line_out_ft <= 0:
        return None, "Enter positive values."

    drag = {"Braid": 1.00, "Fluorocarbon": 1.12, "Monofilament": 1.20}.get(line_type, 1.10)
    speed_factor = (speed_mph ** 1.35)
    COEF = 0.135
    depth = COEF * (weight_oz / (drag * speed_factor)) * line_out_ft
    depth = max(0.0, min(depth, 250.0))
    return round(depth, 1), "Rule-of-thumb estimate. Current and lure drag will change depth."


# ----------------------------
# Header (mobile tight)
# ----------------------------
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("## Best fishing times by location")
st.markdown(
    '<div class="small-muted">Open the side menu to set your location and switch tools.</div>',
    unsafe_allow_html=True,
)

# ----------------------------
# Sidebar (no lat/lon, no debug)
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
        ["Current location (best effort)", "Place name"],
        index=0,
        label_visibility="collapsed",
    )

    if mode == "Current location (best effort)":
        if st.button("Detect location", use_container_width=True):
            lat, lon = ip_geolocate_latlon()
            st.session_state["lat"] = lat
            st.session_state["lon"] = lon

        if st.session_state.get("lat") is None or st.session_state.get("lon") is None:
            st.caption("If this fails, switch to Place name.")
    else:
        place = st.text_input("Place name", placeholder="Example: Fernan Lake", label_visibility="collapsed")
        if st.button("Use place", use_container_width=True):
            lat, lon = geocode_place_to_latlon(place)
            st.session_state["lat"] = lat
            st.session_state["lon"] = lon

    st.divider()
    st.markdown("#### Date")
    selected_day = st.date_input("Date", value=date.today(), label_visibility="collapsed")

# Internal-only location
lat = st.session_state.get("lat")
lon = st.session_state.get("lon")

# ----------------------------
# Guard
# ----------------------------
if lat is None or lon is None:
    st.info("Set your location in the side menu to continue.")
    st.markdown('<div class="fn-footer">Fishing Northwest</div>', unsafe_allow_html=True)
    st.stop()

# ----------------------------
# Page: Best Fishing Times
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

    hours = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]
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
        with c2:
            if right:
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
                st.write("")

# ----------------------------
# Page: Trolling Depth Calculator
# ----------------------------
else:
    st.markdown("### Trolling depth calculator")
    st.markdown(
        '<div class="small-muted">Flatline trolling estimate. Enter your speed, weight, line out, and line type.</div>',
        unsafe_allow_html=True,
    )

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
            st.session_state["preset"] = {"speed": 1.3, "weight": 6.0, "line_type": "Braid"}
    with p2:
        if st.button("Trout", use_container_width=True):
            st.session_state["preset"] = {"speed": 1.6, "weight": 4.0, "line_type": "Braid"}
    with p3:
        if st.button("Deep", use_container_width=True):
            st.session_state["preset"] = {"speed": 1.5, "weight": 8.0, "line_type": "Braid"}

    if "preset" in st.session_state:
        st.info(
            f"Preset loaded: speed {st.session_state['preset']['speed']} mph, "
            f"weight {st.session_state['preset']['weight']} oz, "
            f"line {st.session_state['preset']['line_type']}."
        )

st.markdown('<div class="fn-footer">Fishing Northwest</div>', unsafe_allow_html=True)