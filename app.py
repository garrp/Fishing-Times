# app.py
# FishyNW.com — Best Fishing Times & Trolling Tools
# Brand-correct edition v2.6 (official logo)
# Mobile-first, clean spacing, no blog input

import math
from datetime import datetime, timedelta, date
import requests
import streamlit as st

APP_VERSION = "2.6 FishyNW Brand Edition"

LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-Transparent.png"

UA_HEADERS = {
    "User-Agent": f"FishyNW-App/{APP_VERSION}",
    "Accept": "application/json",
}

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="FishyNW.com | Best Fishing Times",
    page_icon="🎣",
    layout="centered",
)

# -------------------------------------------------
# Styling (matched to FishyNW vibe)
# -------------------------------------------------
st.markdown(
    """
<style>
.block-container {
  padding-top: 1.4rem;
  padding-bottom: 2.4rem;
  max-width: 720px;
}

section[data-testid="stSidebar"] { width: 320px !important; }

.small-muted {
  color: rgba(255,255,255,0.70);
  font-size: 0.95rem;
}

/* Logo block */
.fnw-logo {
  display: flex;
  justify-content: center;
  margin-bottom: 18px;
}
.fnw-logo img {
  max-width: 260px;
  width: 70%;
  height: auto;
}

/* Cards */
.fn-card {
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.04);
  border-radius: 22px;
  padding: 16px 18px;
  margin: 14px 0;
}

.fn-title {
  font-size: 1rem;
  opacity: 0.85;
}

.fn-value {
  font-size: 1.6rem;
  font-weight: 900;
}

.fn-sub {
  font-size: 0.92rem;
  opacity: 0.7;
  margin-top: 6px;
}

/* Inputs & buttons */
button, .stButton button {
  border-radius: 16px !important;
  padding: 0.7rem 1rem !important;
}

/* Footer */
.fnw-footer {
  margin-top: 44px;
  padding-top: 20px;
  border-top: 1px solid rgba(255,255,255,0.15);
  text-align: center;
}
.fnw-footer-title {
  font-weight: 900;
  font-size: 1.05rem;
}
.fnw-footer-sub {
  font-size: 0.95rem;
  opacity: 0.7;
  margin-top: 4px;
}
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def safe_get_json(url: str, timeout: int = 12):
    r = requests.get(url, headers=UA_HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def ip_geolocate():
    try:
        d = safe_get_json("https://ipinfo.io/json", timeout=8)
        loc = d.get("loc")
        if not loc:
            return None, None
        lat, lon = loc.split(",")
        return float(lat), float(lon)
    except Exception:
        return None, None


def geocode_place(place):
    try:
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={requests.utils.quote(place)}&count=1&format=json"
        )
        d = safe_get_json(url, timeout=10)
        r = d.get("results", [])
        if not r:
            return None, None
        return r[0]["latitude"], r[0]["longitude"]
    except Exception:
        return None, None


def sun_times(lat, lon, day):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={day}&end_date={day}"
        "&daily=sunrise,sunset&timezone=auto"
    )
    try:
        d = safe_get_json(url)
        return (
            datetime.fromisoformat(d["daily"]["sunrise"][0]),
            datetime.fromisoformat(d["daily"]["sunset"][0]),
        )
    except Exception:
        return None, None


def wind_by_hour(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=wind_speed_10m&wind_speed_unit=mph&timezone=auto"
    )
    try:
        d = safe_get_json(url)
        out = {}
        for t, s in zip(d["hourly"]["time"], d["hourly"]["wind_speed_10m"]):
            out.setdefault(datetime.fromisoformat(t).strftime("%H:00"), round(s, 1))
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
    sr, ss = sun_times(lat, lon, day)
    if not sr or not ss:
        return None
    phase = moon_phase(day)
    note = "Simple, no-fluff planning window."
    if phase < 0.08 or phase > 0.92:
        note = "Near New Moon — often a strong bite window."
    elif abs(phase - 0.5) < 0.08:
        note = "Near Full Moon — often a strong bite window."
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
# Logo header (main column)
# -------------------------------------------------
st.markdown(
    f"""
<div class="fnw-logo">
  <img src="{LOGO_URL}" alt="FishyNW logo">
</div>
<div class="small-muted" style="text-align:center;">
  Northwest fishing tools • Built from firsthand experience
</div>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Sidebar navigation
# -------------------------------------------------
with st.sidebar:
    st.markdown("### FishyNW Tools")
    st.caption(APP_VERSION)

    page = st.radio(
        "Tool",
        ["Best fishing times", "Trolling depth calculator"],
        label_visibility="collapsed",
    )

    if page == "Best fishing times":
        st.divider()
        mode = st.radio("Location", ["Current location", "Place name"], label_visibility="collapsed")

        if mode == "Current location":
            if st.button("Use current location", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = ip_geolocate()
        else:
            place = st.text_input(
                "Place name",
                placeholder="Example: Fernan Lake",
                label_visibility="collapsed",
            )
            if st.button("Use place name", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = geocode_place(place)

        st.divider()
        selected_day = st.date_input("Date", value=date.today(), label_visibility="collapsed")

# -------------------------------------------------
# Main pages
# -------------------------------------------------
if page == "Best fishing times":
    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    if lat is None or lon is None:
        st.info("Select a location in the side menu to generate fishing times.")
    else:
        t = best_times(lat, lon, selected_day)
        if not t:
            st.warning("Could not generate fishing times.")
        else:
            m0, m1 = t["morning"]
            e0, e1 = t["evening"]

            st.markdown(
                f"""
<div class="fn-card">
  <div class="fn-title">Morning window</div>
  <div class="fn-value">{m0.strftime('%I:%M %p').lstrip('0')} – {m1.strftime('%I:%M %p').lstrip('0')}</div>
</div>
<div class="fn-card">
  <div class="fn-title">Evening window</div>
  <div class="fn-value">{e0.strftime('%I:%M %p').lstrip('0')} – {e1.strftime('%I:%M %p').lstrip('0')}</div>
</div>
<div class="small-muted">{t["note"]}</div>
""",
                unsafe_allow_html=True,
            )

            st.markdown("### Wind (mph)")
            wind = wind_by_hour(lat, lon)
            for h in ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]:
                st.markdown(
                    f"""
<div class="fn-card">
  <div class="fn-title">{h}</div>
  <div class="fn-value">{wind.get(h, "—")} mph</div>
</div>
""",
                    unsafe_allow_html=True,
                )

else:
    st.markdown("### Trolling depth calculator")
    st.markdown('<div class="small-muted">Quick depth estimate for kayak or boat trolling.</div>', unsafe_allow_html=True)

    speed = st.number_input("Trolling speed (mph)", 0.0, value=1.5, step=0.1)
    weight = st.number_input("Weight (oz)", 0.0, value=8.0, step=0.5)
    line_out = st.number_input("Line out (feet)", 0.0, value=120.0, step=5.0)
    line_type = st.radio("Line type", ["Braid", "Fluorocarbon", "Monofilament"], horizontal=True)

    depth = trolling_depth(speed, weight, line_out, line_type)

    st.markdown(
        f"""
<div class="fn-card">
  <div class="fn-title">Estimated depth</div>
  <div class="fn-value">{depth if depth is not None else "—"} ft</div>
  <div class="fn-sub">Rule of thumb. Current, lure drag, and rod angle affect results.</div>
</div>
""",
        unsafe_allow_html=True,
    )

# -------------------------------------------------
# Footer (brand-only, clear)
# -------------------------------------------------
st.markdown(
    """
<div class="fnw-footer">
  <div class="fnw-footer-title">FishyNW.com</div>
  <div class="fnw-footer-sub">Independent Northwest fishing tools • Built for real trips</div>
</div>
""",
    unsafe_allow_html=True,
)