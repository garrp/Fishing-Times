# app.py
# FishingNW.com — Best Fishing Times by Location
# BY Company Edition v2.3 (FishingNW branded)
# Mobile-first, rounded UI
# Location ONLY required for fishing times (hidden for calculators)
# Includes clear footer with FishingNW.com + Blog input box (stored in session)

import math
from datetime import datetime, timedelta, date
import requests
import streamlit as st

APP_VERSION = "2.3 BY Company Edition"

# -------------------------------------------------
# Page config + mobile-first styling (FishingNW)
# -------------------------------------------------
st.set_page_config(
    page_title="FishingNW.com | Best Fishing Times",
    page_icon="🎣",
    layout="centered",
)

st.markdown(
    """
<style>
.block-container {
  padding-top: 0.4rem;
  padding-bottom: 1.2rem;
  max-width: 680px;
}

/* Sidebar width */
section[data-testid="stSidebar"] { width: 320px !important; }

/* Typography */
h1, h2, h3 { letter-spacing: 0.2px; }
.small-muted { color: rgba(255,255,255,0.65); font-size: 0.95rem; line-height: 1.35; }

/* Brand bar */
.fnw-brand {
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.03);
  border-radius: 22px;
  padding: 12px 14px;
  margin: 8px 0 12px 0;
}
.fnw-brand-title {
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: 0.2px;
}
.fnw-brand-sub {
  font-size: 0.95rem;
  opacity: 0.75;
  margin-top: 2px;
}

/* Cards */
.fn-card {
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.035);
  border-radius: 22px;
  padding: 14px 16px;
  margin: 10px 0;
}
.fn-title { font-size: 1rem; opacity: 0.85; }
.fn-value { font-size: 1.55rem; font-weight: 800; }
.fn-sub { font-size: 0.92rem; opacity: 0.7; margin-top: 6px; }

/* Buttons and inputs */
button, .stButton button { border-radius: 16px !important; padding: 0.65rem 0.9rem !important; }
div[data-baseweb="input"] > div,
div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div { border-radius: 16px !important; }
div[role="radiogroup"] label { border-radius: 16px !important; padding: 8px 10px !important; }
hr { margin: 0.6rem 0 !important; opacity: 0.25; }

/* Footer */
.fnw-footer {
  margin-top: 22px;
  border-top: 1px solid rgba(255,255,255,0.14);
  padding-top: 14px;
}
.fnw-footer-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
}
.fnw-footer-title {
  font-weight: 800;
  font-size: 1.05rem;
}
.fnw-footer-sub {
  opacity: 0.7;
  font-size: 0.95rem;
  margin-top: 2px;
}
.fnw-footer-box {
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.03);
  border-radius: 18px;
  padding: 12px 14px;
  margin-top: 10px;
}
</style>
""",
    unsafe_allow_html=True,
)

UA_HEADERS = {
    "User-Agent": "FishingNW-App/2.3",
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
        if not place or not place.strip():
            return None, None
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={requests.utils.quote(place.strip())}&count=1&format=json"
        )
        data = safe_get_json(url, timeout=10)
        r = data.get("results", [])
        if not r:
            return None, None
        return float(r[0]["latitude"]), float(r[0]["longitude"])
    except Exception:
        return None, None


def get_sun_times(lat, lon, day_iso: str):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={day_iso}&end_date={day_iso}"
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
            out.setdefault(k, round(float(s), 1))
        return out
    except Exception:
        return {}


def moon_phase(day: date):
    y, m, d = day.year, day.month, day.day
    if m < 3:
        y -= 1
        m += 12
    a = y // 100
    b = 2 - a + a // 4
    jd = int(365.25 * (y + 4716)) + int(30.6 * (m + 1)) + d + b - 1524.5
    return ((jd - 2451550.1) % 29.53) / 29.53


def best_times(lat, lon, day_obj: date):
    sr, ss = get_sun_times(lat, lon, day_obj.isoformat())
    if not sr or not ss:
        return None
    phase = moon_phase(day_obj)
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
# Brand header
# -------------------------------------------------
st.markdown(
    """
<div class="fnw-brand">
  <div class="fnw-brand-title">FishingNW.com</div>
  <div class="fnw-brand-sub">Best fishing times and trolling tools</div>
</div>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
with st.sidebar:
    st.markdown("### FishingNW.com")
    st.caption(f"BY Company Edition • v{APP_VERSION}")

    page = st.radio(
        "Tool",
        ["Best fishing times", "Trolling depth calculator"],
        label_visibility="collapsed",
    )

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
            if st.session_state.get("lat") is None or st.session_state.get("lon") is None:
                st.caption("If this fails, switch to Place name.")
        else:
            place = st.text_input("Place", placeholder="Example: Fernan Lake", label_visibility="collapsed")
            if st.button("Use place", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = geocode_place(place)

        st.divider()
        st.markdown("#### Date")
        selected_day = st.date_input("Date", value=date.today(), label_visibility="collapsed")

# -------------------------------------------------
# Main routing
# -------------------------------------------------
if page == "Best fishing times":
    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    if lat is None or lon is None:
        st.info("Set your location in the side menu to generate fishing times.")
    else:
        t = best_times(lat, lon, st.session_state.get("selected_day", date.today()))
        # If sidebar date exists, prefer it
        if "selected_day" not in st.session_state:
            # make sure key exists even if sidebar not interacted
            st.session_state["selected_day"] = date.today()
        # Use sidebar-selected date if it was created in this run
        try:
            # selected_day exists only if page==Best fishing times and sidebar ran it
            t = best_times(lat, lon, selected_day)
        except Exception:
            t = best_times(lat, lon, st.session_state["selected_day"])

        if not t:
            st.warning("Could not generate fishing times.")
        else:
            st.markdown("### Best fishing times")
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
  <div class="fn-value">{depth if depth is not None else "—"} ft</div>
  <div class="fn-sub">Rule of thumb estimate. Current and lure drag affect depth.</div>
</div>
""",
        unsafe_allow_html=True,
    )

# -------------------------------------------------
# Clear footer with FishingNW.com + Blog input
# -------------------------------------------------
st.markdown(
    """
<div class="fnw-footer">
  <div class="fnw-footer-row">
    <div>
      <div class="fnw-footer-title">FishingNW.com</div>
      <div class="fnw-footer-sub">Copy and save notes for your blog post</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

blog_note = st.text_area(
    "FishingNW.com blog input",
    placeholder="Paste your blog notes here. Example: Lake, conditions, lures, results, and a short recap.",
    height=140,
)

st.session_state["blog_input"] = blog_note

st.markdown(
    """
<div class="fnw-footer-box">
  <div class="fn-title">Saved</div>
  <div class="fn-sub">Your blog input stays on-screen while the app is running. Copy it anytime.</div>
</div>
""",
    unsafe_allow_html=True,
)