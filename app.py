# app.py
# FishyNW.com - Fishing Tools
# Version 1.6
# ASCII ONLY. NO UNICODE.

from datetime import datetime, timedelta, date
import requests
import streamlit as st

APP_VERSION = "1.6"
LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-Transparent.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.6",
    "Accept": "application/json",
}

# ---------------- Page Config ----------------
st.set_page_config(
    page_title="FishyNW Fishing Tools",
    layout="centered",
)

# ---------------- Styles (ASCII SAFE) ----------------
st.markdown(
"""
<style>
:root {
  --bg: #061a18;
  --sidebar: #041412;
  --card: #0b2a26;
  --border: rgba(248,248,232,0.2);
  --text: #f8f8e8;
  --muted: rgba(248,248,232,0.75);
  --menu: rgba(248,248,232,0.95);
  --primary: #184840;
}

.stApp {
  background-color: var(--bg);
  color: var(--text);
}

.block-container {
  padding-top: 2.5rem;
  max-width: 900px;
}

section[data-testid="stSidebar"] {
  background-color: var(--sidebar) !important;
  border-right: 1px solid var(--border);
  width: 320px;
}

section[data-testid="stSidebar"] * {
  color: var(--menu) !important;
}

.header {
  display: flex;
  align-items: flex-end;
  gap: 20px;
  margin-top: 20px;
  margin-bottom: 12px;
}

.header-logo img {
  max-width: 140px;
  display: block;
}

.header-title {
  font-size: 1.6rem;
  font-weight: 800;
  padding-bottom: 6px;
}

.small {
  color: var(--muted);
  font-size: 0.95rem;
}

.card {
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 16px;
  margin-top: 14px;
}

.card-title {
  opacity: 0.85;
  font-size: 1rem;
}

.card-value {
  font-size: 1.6rem;
  font-weight: 800;
}

button {
  border-radius: 14px;
}

.footer {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  text-align: center;
  opacity: 0.8;
}
</style>
""",
unsafe_allow_html=True,
)

# ---------------- Helpers ----------------
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
        url = "https://geocoding-api.open-meteo.com/v1/search?name=" + name + "&count=1&format=json"
        data = get_json(url)
        res = data.get("results")
        if not res:
            return None, None
        return res[0]["latitude"], res[0]["longitude"]
    except Exception:
        return None, None

def get_sun_times(lat, lon, day):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=" + str(lat) +
        "&longitude=" + str(lon) +
        "&start_date=" + day +
        "&end_date=" + day +
        "&daily=sunrise,sunset&timezone=auto"
    )
    data = get_json(url)
    sr = data["daily"]["sunrise"][0]
    ss = data["daily"]["sunset"][0]
    return datetime.fromisoformat(sr), datetime.fromisoformat(ss)

def best_times(lat, lon, d):
    sr, ss = get_sun_times(lat, lon, d.isoformat())
    return {
        "morning": (sr - timedelta(hours=1), sr + timedelta(hours=1)),
        "evening": (ss - timedelta(hours=1), ss + timedelta(hours=1)),
    }

# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### FishyNW Tools")
    st.caption("Version " + APP_VERSION)

    tool = st.radio(
        "Tool",
        [
            "Best fishing times",
            "Trolling depth calculator",
            "Water temperature targeting",
            "Species tips",
        ],
        label_visibility="collapsed",
    )

    if tool == "Best fishing times":
        mode = st.radio("Location", ["Current location", "Place name"])
        if mode == "Current location":
            if st.button("Use current location"):
                st.session_state["lat"], st.session_state["lon"] = get_location()
        else:
            place = st.text_input("Place name")
            if st.button("Use place"):
                st.session_state["lat"], st.session_state["lon"] = geocode_place(place)

        selected_day = st.date_input("Date", value=date.today())

# ---------------- Header ----------------
PAGE_TITLES = {
    "Best fishing times": "Best Fishing Times",
    "Trolling depth calculator": "Trolling Depth Calculator",
    "Water temperature targeting": "Water Temperature Targeting",
    "Species tips": "Species Tips",
}

st.markdown(
    "<div class='header'>"
    "<div class='header-logo'><img src='" + LOGO_URL + "'></div>"
    "<div class='header-title'>" + PAGE_TITLES.get(tool, "") + "</div>"
    "</div>"
    "<div class='small'>Independent Northwest fishing tools</div>",
    unsafe_allow_html=True,
)

# ---------------- Main Content ----------------
if tool == "Best fishing times":
    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    if not lat or not lon:
        st.info("Select a location from the menu.")
    else:
        times = best_times(lat, lon, selected_day)
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

else:
    st.markdown("<div class='card'>Feature continues here</div>", unsafe_allow_html=True)

# ---------------- Footer ----------------
st.markdown(
    "<div class='footer'><strong>FishyNW.com</strong><br>"
    "Independent Northwest fishing tools</div>",
    unsafe_allow_html=True,
)