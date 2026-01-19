# app.py
# FishyNW.com - Best Fishing Times, Trolling Depth, and Speedometer
# Version 1.1

from datetime import datetime, timedelta, date
import math
import requests
import streamlit as st

APP_VERSION = "1.1"
LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-Transparent.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.1",
    "Accept": "application/json",
}

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="FishyNW.com | Fishing Tools",
    layout="centered",
)

# -------------------------------------------------
# Styles (ASCII SAFE)
# -------------------------------------------------
st.markdown(
    """
<style>
.block-container {
  padding-top: 1.5rem;
  padding-bottom: 2.5rem;
  max-width: 720px;
}
section[data-testid="stSidebar"] { width: 320px; }
.small { color: rgba(255,255,255,0.7); font-size: 0.95rem; }
.logo { text-align: center; margin-bottom: 18px; }
.logo img { max-width: 260px; width: 70%; }
.card {
  border: 1px solid rgba(255,255,255,0.15);
  background: rgba(255,255,255,0.04);
  border-radius: 18px;
  padding: 16px;
  margin-top: 14px;
}
.card-title { font-size: 1rem; opacity: 0.85; }
.card-value { font-size: 1.6rem; font-weight: 800; }
.big-value { font-size: 2.2rem; font-weight: 900; letter-spacing: 0.2px; }
.footer {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid rgba(255,255,255,0.15);
  text-align: center;
  font-size: 0.95rem;
  opacity: 0.7;
}
button { border-radius: 14px; }
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def get_json(url, timeout=10):
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.json()


def get_location():
    try:
        data = get_json("https://ipinfo.io/json", 6)
        loc = data.get("loc")
        if not loc:
            return None, None
        lat, lon = loc.split(",")
        return float(lat), float(lon)
    except Exception:
        return None, None


def geocode_place(name):
    try:
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            "?name=" + name + "&count=1&format=json"
        )
        data = get_json(url)
        res = data.get("results")
        if not res:
            return None, None
        return res[0]["latitude"], res[0]["longitude"]
    except Exception:
        return None, None


def get_sun_times(lat, lon, day_iso):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=" + str(lat) +
        "&longitude=" + str(lon) +
        "&start_date=" + day_iso +
        "&end_date=" + day_iso +
        "&daily=sunrise,sunset&timezone=auto"
    )
    try:
        data = get_json(url)
        sr = data["daily"]["sunrise"][0]
        ss = data["daily"]["sunset"][0]
        return datetime.fromisoformat(sr), datetime.fromisoformat(ss)
    except Exception:
        return None, None


def get_wind(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=" + str(lat) +
        "&longitude=" + str(lon) +
        "&hourly=wind_speed_10m&wind_speed_unit=mph&timezone=auto"
    )
    try:
        data = get_json(url)
        out = {}
        for t, s in zip(data["hourly"]["time"], data["hourly"]["wind_speed_10m"]):
            hour = datetime.fromisoformat(t).strftime("%H:00")
            out[hour] = round(s, 1)
        return out
    except Exception:
        return {}
    return {}


def best_times(lat, lon, day_obj):
    day_iso = day_obj.isoformat()
    sr, ss = get_sun_times(lat, lon, day_iso)
    if not sr or not ss:
        return None
    return {
        "morning": (sr - timedelta(hours=1), sr + timedelta(hours=1)),
        "evening": (ss - timedelta(hours=1), ss + timedelta(hours=1)),
    }


def trolling_depth(speed, weight, line_out, line_type):
    if speed <= 0 or weight <= 0 or line_out <= 0:
        return None
    drag = {"Braid": 1.0, "Fluorocarbon": 1.12, "Monofilament": 1.2}[line_type]
    depth = 0.135 * (weight / (drag * (speed ** 1.35))) * line_out
    return round(depth, 1)


def mph_to_fps(mph):
    return mph * 5280.0 / 3600.0


def format_mph(v):
    try:
        return f"{float(v):.2f}"
    except Exception:
        return "--"


# -------------------------------------------------
# Header
# -------------------------------------------------
st.markdown(
    "<div class='logo'><img src='" + LOGO_URL + "'></div>"
    "<div class='small' style='text-align:center;'>Independent Northwest fishing tools</div>",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
with st.sidebar:
    st.markdown("### FishyNW Tools")
    st.caption("Version " + APP_VERSION)

    tool = st.radio(
        "Tool",
        ["Best fishing times", "Trolling depth calculator", "Speedometer"],
        label_visibility="collapsed",
    )

    # Location inputs ONLY when location matters
    if tool == "Best fishing times":
        st.divider()
        mode = st.radio("Location", ["Current location", "Place name"])

        if mode == "Current location":
            if st.button("Use current location", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = get_location()
        else:
            place = st.text_input("Place name", placeholder="Example: Fernan Lake")
            if st.button("Use place", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = geocode_place(place)

        st.divider()
        selected_day = st.date_input("Date", value=date.today())

# -------------------------------------------------
# Main content
# -------------------------------------------------
if tool == "Best fishing times":
    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    if lat is None or lon is None:
        st.info("Select a location from the menu.")
    else:
        times = best_times(lat, lon, selected_day)
        if not times:
            st.warning("Unable to calculate fishing times.")
        else:
            m0, m1 = times["morning"]
            e0, e1 = times["evening"]

            st.markdown(
                "<div class='card'><div class='card-title'>Morning window</div>"
                "<div class='card-value'>" +
                m0.strftime("%I:%M %p").lstrip("0") +
                " - " +
                m1.strftime("%I:%M %p").lstrip("0") +
                "</div></div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                "<div class='card'><div class='card-title'>Evening window</div>"
                "<div class='card-value'>" +
                e0.strftime("%I:%M %p").lstrip("0") +
                " - " +
                e1.strftime("%I:%M %p").lstrip("0") +
                "</div></div>",
                unsafe_allow_html=True,
            )

            st.markdown("### Wind (mph)")
            wind = get_wind(lat, lon)
            for h in ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]:
                st.markdown(
                    "<div class='card'><div class='card-title'>" + h +
                    "</div><div class='card-value'>" +
                    str(wind.get(h, "--")) + " mph</div></div>",
                    unsafe_allow_html=True,
                )

elif tool == "Trolling depth calculator":
    st.markdown("### Trolling depth calculator")
    st.markdown("<div class='small'>Location not required.</div>", unsafe_allow_html=True)

    speed = st.number_input("Speed (mph)", 0.0, value=1.5, step=0.1)
    weight = st.number_input("Weight (oz)", 0.0, value=8.0, step=0.5)
    line_out = st.number_input("Line out (feet)", 0.0, value=120.0, step=5.0)
    line_type = st.radio("Line type", ["Braid", "Fluorocarbon", "Monofilament"], horizontal=True)

    depth = trolling_depth(speed, weight, line_out, line_type)

    st.markdown(
        "<div class='card'><div class='card-title'>Estimated depth</div>"
        "<div class='card-value'>" +
        (str(depth) if depth is not None else "--") + " ft</div>"
        "<div class='small' style='margin-top:8px;'>Rule of thumb. Current and lure drag affect results.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

else:
    st.markdown("### Speedometer")
    st.markdown("<div class='small'>Enter your current speed to display a large readout.</div>", unsafe_allow_html=True)

    speed_mode = st.radio("Mode", ["Manual speed", "Cadence helper"], horizontal=True)

    if speed_mode == "Manual speed":
        spd = st.number_input("Speed (mph)", 0.0, value=1.50, step=0.05)

        st.markdown(
            "<div class='card'>"
            "<div class='card-title'>Current speed</div>"
            "<div class='big-value'>" + format_mph(spd) + " mph</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown(
            "<div class='card'>"
            "<div class='card-title'>Trolling target</div>"
            "<div class='card-value'>1.2 to 1.8 mph</div>"
            "<div class='small' style='margin-top:8px;'>Most trolling stays in this range. Dial it in for your lure and depth.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    else:
        st.markdown("<div class='small'>This helps you hold a steady pace by matching a rhythm.</div>", unsafe_allow_html=True)

        method = st.radio("Drive type", ["Pedal (RPM)", "Paddle (strokes per minute)"], horizontal=True)

        if method == "Pedal (RPM)":
            rpm = st.number_input("Pedal cadence (RPM)", 0.0, value=45.0, step=1.0)
            mph_est = rpm * 0.03
            st.markdown(
                "<div class='card'>"
                "<div class='card-title'>Estimated speed</div>"
                "<div class='big-value'>" + format_mph(mph_est) + " mph</div>"
                "<div class='small' style='margin-top:8px;'>This is a rough estimate. Calibrate it one time using GPS, then keep the same RPM.</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            spm = st.number_input("Strokes per minute", 0.0, value=30.0, step=1.0)
            mph_est = spm * 0.04
            st.markdown(
                "<div class='card'>"
                "<div class='card-title'>Estimated speed</div>"
                "<div class='big-value'>" + format_mph(mph_est) + " mph</div>"
                "<div class='small' style='margin-top:8px;'>Rough estimate. Calibrate once, then keep your rhythm steady.</div>"
                "</div>",
                unsafe_allow_html=True,
            )

# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown(
    "<div class='footer'><strong>FishyNW.com</strong><br>"
    "Independent Northwest fishing tools</div>",
    unsafe_allow_html=True,
)