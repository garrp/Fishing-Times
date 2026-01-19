# app.py
# Fishing Northwest — Best Fishing Times by Location
# BY Company Edition v2.2
# Mobile-first, rounded UI
# Location ONLY required for fishing times (hidden for calculators)

import math
from datetime import datetime, timedelta, date
import requests
import streamlit as st

APP_VERSION = "2.2 BY Company Edition"

# -------------------------------------------------
# Page config + mobile-first styling
# -------------------------------------------------
st.set_page_config(
    page_title="Best Fishing Times | Fishing Northwest",
    page_icon="🎣",
    layout="centered",
)

st.markdown(
    """
<style>
.block-container {
  padding-top: 0.4rem;
  padding-bottom: 1.2rem;
  max-width: 640px;
}
section[data-testid="stSidebar"] { width: 320px !important; }

h1, h2, h3 { letter-spacing: 0.2px; }
.small-muted { color: rgba(255,255,255,0.65); font-size: 0.95rem; }

.fn-card {
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.035);
  border-radius: 22px;
  padding: 14px 16px;
  margin: 10px 0;
}
.fn-title { font-size: 1rem; opacity: 0.85; }
.fn-value { font-size: 1.55rem; font-weight: 750; }
.fn-sub { font-size: 0.92rem; opacity: 0.7; }

button, .stButton button { border-radius: 16px !important; }

.fn-footer { margin-top: 18px; opacity: 0.55; font-size: 0.95rem; }
</style>
""",
    unsafe_allow_html=True,
)

UA_HEADERS = {
    "User-Agent": "FishingNorthwest-App/2.2",
    "Accept": "application/json",
}

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def safe_get_json(url: str, timeout: int = 12):
    r = requests.get(url, headers=UA_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def ip_geolocate():
    try:
        data = safe_get_json("https://ipinfo.io/json", timeout=8)
        loc = data.get("loc")
        if not loc:
            return None, None
        lat, lon = loc.split(",")
        return float(lat), float(lon)
    except Exception:
        return None, None


def geocode_place(place: str):
    try:
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={requests.utils.quote(place)}&count=1&format=json"
        )
        data = safe_get_json(url, timeout=10)
        r = data.get("results", [])
        if not r:
            return None, None
        return r[0]["latitude"], r[0]["longitude"]
    except Exception:
        return None, None


def get_sun_times(lat, lon, day):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={day}&end_date={day}"
        "&daily=sunrise,sunset&timezone=auto"
    )
    try:
        d = safe_get_json(url)
        sr = d["daily"]["sunrise"][0]
        ss = d["daily"]["sunset"][0]
        return datetime.fromisoformat(sr), datetime.fromisoformat(ss)
    except Exception:
        return None, None


def get_wind(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=wind_speed_10m&wind_speed_unit=mph&timezone=auto"
    )
    try:
        d = safe_get_json(url)
        out = {}
        for t, s in zip(d["hourly"]["time"], d["hourly"]["wind_speed_10m"]):
            k = datetime.fromisoformat(t).strftime("%H:00")
            out.setdefault(k, round(s, 1))
        return out
    except Exception:
        return {}


def moon_phase(day):
    y, m, d = day.year, day.month, day.day
    if m < 3:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6 * (m + 1)) + d + b - 1524.5
    return ((jd - 2451550.1) % 29.53) / 29.53


def best_times(lat, lon, day):
    sr, ss = get_sun_times(lat, lon, day)
    if not sr or not ss:
        return None
    phase = moon_phase(day)
    note = "Normal conditions."
    if phase < 0.08 or phase > 0.92:
        note = "Near New Moon — often strong bite windows."
    elif abs(phase - 0.5) < 0.08:
        note = "Near Full Moon — often strong bite windows."
    return {
        "morning": (sr - timedelta(hours=1), sr + timedelta(hours=1)),
        "evening": (ss - timedelta(hours=1), ss + timedelta(hours=1)),
        "note": note,
    }


def trolling_depth(speed, weight, line_out, line_type):
    if speed <= 0 or weight <= 0 or line_out <= 0:
        return None
    drag = {"Braid": 1.0, "Fluorocarbon": 1.12, "Monofilament": 1.2}[line_type]
    depth = 0.135 * (weight / (drag * speed**1.35)) * line_out
    return round(min(depth, 250), 1)

# -------------------------------------------------
# Header
# -------------------------------------------------
st.markdown("## Best fishing times by location")
st.markdown(
    '<div class="small-muted">Use the side menu to switch tools.</div>',
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
with st.sidebar:
    st.markdown("### BY Company Edition")
    st.caption(f"v{APP_VERSION}")

    page = st.radio(
        "Tool",
        ["Best fishing times", "Trolling depth calculator"],
        label_visibility="collapsed",
    )

    # Location ONLY when needed
    if page == "Best fishing times":
        st.divider()
        st.markdown("#### Location")

        mode = st.radio(
            "Method",
            ["Current location", "Place name"],
            label_visibility="collapsed",
        )

        if mode == "Current location":
            if st.button("Detect location", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = ip_geolocate()
        else:
            place = st.text_input("Place", placeholder="Example: Fernan Lake", label_visibility="collapsed")
            if st.button("Use place", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = geocode_place(place)

        st.divider()
        st.markdown("#### Date")
        selected_day = st.date_input("Date", value=date.today(), label_visibility="collapsed")

# -------------------------------------------------
# Main content routing
# -------------------------------------------------
if page == "Best fishing times":
    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    if lat is None or lon is None:
        st.info("Set your location in the side menu to continue.")
        st.stop()

    t = best_times(lat, lon, selected_day)
    if not t:
        st.warning("Could not generate fishing times.")
        st.stop()

    st.markdown(
        f"""
<div class="fn-card">
  <div class="fn-title">Morning window</div>
  <div class="fn-value">{t['morning'][0].strftime('%I:%M %p').lstrip('0')} – {t['morning'][1].strftime('%I:%M %p').lstrip('0')}</div>
</div>
<div class="fn-card">
  <div class="fn-title">Evening window</div>
  <div class="fn-value">{t['evening'][0].strftime('%I:%M %p').lstrip('0')} – {t['evening'][1].strftime('%I:%M %p').lstrip('0')}</div>
</div>
<div class="small-muted">{t['note']}</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Wind (mph)")
    wind = get_wind(lat, lon)
    for h in ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]:
        v = wind.get(h, "—")
        st.markdown(
            f"""
<div class="fn-card">
  <div class="fn-title">{h}</div>
  <div class="fn-value">{v} mph</div>
</div>
""",
            unsafe_allow_html=True,
        )

# -------------------------------------------------
# Trolling Depth Calculator (NO LOCATION)
# -------------------------------------------------
else:
    st.markdown("### Trolling depth calculator")
    st.markdown(
        '<div class="small-muted">Flatline trolling estimate. Location not required.</div>',
        unsafe_allow_html=True,
    )

    speed = st.number_input("Trolling speed (mph)", 0.0, value=1.5, step=0.1)
    weight = st.number_input("Weight (oz)", 0.0, value=8.0, step=0.5)
    line_out = st.number_input("Line out (feet)", 0.0, value=120.0, step=5.0)
    line_type = st.radio("Line type", ["Braid", "Fluorocarbon", "Monofilament"], horizontal=True)

    depth = trolling_depth(speed, weight, line_out, line_type)

    st.markdown(
        f"""
<div class="fn-card">
  <div class="fn-title">Estimated depth</div>
  <div class="fn-value">{depth if depth else "—"} ft</div>
  <div class="fn-sub">Rule of thumb estimate. Current and lure drag affect depth.</div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown('<div class="fn-footer">Fishing Northwest</div>', unsafe_allow_html=True)