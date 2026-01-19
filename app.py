# app.py
# FishyNW.com - Fishing Tools
# Version 1.6 (ASCII-safe, nuclear clean)

from datetime import datetime, timedelta, date
import requests
import streamlit as st

APP_VERSION = "1.6"
LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-Transparent.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.6",
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
# Styles (STRICT ASCII ONLY)
# -------------------------------------------------
st.markdown(
    """
<style>
:root {
  --bg: #061A18;
  --card: rgba(16,64,56,0.35);
  --border: rgba(248,248,232,0.16);
  --text: #F8F8E8;
  --muted: rgba(248,248,232,0.72);
  --primary: #184840;
  --primary2: #104840;
  --accent: #688858;
}

.stApp {
  background-color: var(--bg);
  color: var(--text);
}

.block-container {
  padding-top: 1.5rem;
  padding-bottom: 2.5rem;
  max-width: 720px;
}

section[data-testid="stSidebar"] {
  width: 320px;
  background: rgba(0,0,0,0.18);
}

.small {
  color: var(--muted);
  font-size: 0.95rem;
}

.logo {
  text-align: center;
  margin-bottom: 18px;
}

.logo img {
  max-width: 260px;
  width: 70%;
}

.card {
  border: 1px solid var(--border);
  background: var(--card);
  border-radius: 18px;
  padding: 16px;
  margin-top: 14px;
}

.card-title {
  font-size: 1rem;
  opacity: 0.85;
}

.card-value {
  font-size: 1.6rem;
  font-weight: 800;
}

.footer {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  text-align: center;
  font-size: 0.95rem;
  opacity: 0.8;
}

button {
  border-radius: 14px;
}

.stButton > button {
  background-color: var(--primary);
  color: var(--text);
  border: 1px solid rgba(248,248,232,0.22);
}

.stButton > button:hover {
  background-color: var(--primary2);
}

.badge {
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(104,136,88,0.16);
  margin: 6px 6px 0 0;
  font-weight: 800;
  font-size: 0.92rem;
}
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


def best_times(lat, lon, day_obj):
    sr, ss = get_sun_times(lat, lon, day_obj.isoformat())
    if not sr or not ss:
        return None
    return {
        "morning": (sr - timedelta(hours=1), sr + timedelta(hours=1)),
        "evening": (ss - timedelta(hours=1), ss + timedelta(hours=1)),
    }


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
        ["Best fishing times"],
        label_visibility="collapsed",
    )

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
# Main
# -------------------------------------------------
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

# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown(
    "<div class='footer'><strong>FishyNW.com</strong><br>"
    "Independent Northwest fishing tools</div>",
    unsafe_allow_html=True,
)