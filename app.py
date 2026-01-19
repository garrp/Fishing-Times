# app.py
# FishyNW.com - Fishing Tools
# Version 1.6 (logo left, dynamic title right, solid sidebar)

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
  --sidebar: #041412;
  --card: #0B2A26;
  --border: rgba(248,248,232,0.18);
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
  padding-top: 1.2rem;
  padding-bottom: 2.5rem;
  max-width: 900px;
}

section[data-testid="stSidebar"] {
  background-color: var(--sidebar) !important;
  width: 320px;
  border-right: 1px solid var(--border);
}

section[data-testid="stSidebar"] > div {
  background-color: var(--sidebar) !important;
}

.small {
  color: var(--muted);
  font-size: 0.95rem;
}

/* Header */
.header {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
}

.header-logo img {
  max-width: 130px;
  width: 100%;
}

.header-title {
  margin-left: 20px;
  font-size: 1.6rem;
  font-weight: 800;
}

/* Cards */
.card {
  border: 1px solid var(--border);
  background-color: var(--card);
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

/* Buttons */
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

/* Tips */
.tip-h {
  font-weight: 800;
  margin-top: 10px;
}

.bul {
  margin-top: 8px;
}

.bul li {
  margin-bottom: 6px;
}

/* Badge */
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

/* Footer */
.footer {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  text-align: center;
  font-size: 0.95rem;
  opacity: 0.8;
}
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Helpers (unchanged)
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


def trolling_depth(speed_mph, weight_oz, line_out_ft, line_type, line_test_lb):
    if speed_mph <= 0 or weight_oz <= 0 or line_out_ft <= 0 or line_test_lb <= 0:
        return None

    type_drag = {"Braid": 1.0, "Fluorocarbon": 1.12, "Monofilament": 1.2}[line_type]
    test_ratio = line_test_lb / 20.0
    test_drag = test_ratio ** 0.35
    total_drag = type_drag * test_drag
    depth = 0.135 * (weight_oz / (total_drag * (speed_mph ** 1.35))) * line_out_ft
    return round(depth, 1)


def c_to_f(c):
    return (c * 9.0 / 5.0) + 32.0


def temp_rating(temp_f, lo, hi):
    if lo <= temp_f <= hi:
        return "Best"
    if (lo - 5) <= temp_f < lo or hi < temp_f <= (hi + 5):
        return "Fair"
    return "Low"


def temp_targets(temp_f):
    t = temp_f
    items = []

    def add(name, lo, hi, note):
        rating = temp_rating(t, lo, hi)
        items.append((name, rating, note))

    add("Trout (rainbow/brown)", 45, 65, "Cool water. Better early and in shade.")
    add("Kokanee", 42, 55, "Cool water. Often deeper when surface warms.")
    add("Chinook salmon", 44, 58, "Cool water. Often deeper.")
    add("Lake trout", 42, 55, "Cold water. Deep structure.")
    add("Smallmouth bass", 60, 75, "Rocks, points, wind.")
    add("Largemouth bass", 65, 80, "Weeds and shallow cover.")
    add("Walleye", 55, 70, "Low light windows.")
    add("Panfish", 60, 80, "Shallows and cover.")
    add("Catfish", 65, 85, "Evening and night.")

    rank = {"Best": 0, "Fair": 1, "Low": 2}
    items.sort(key=lambda x: rank[x[1]])
    return items


def species_tip_db():
    return {
        "Kokanee": {
            "temp_f": (42, 55),
            "Top": ["Not a topwater fish."],
            "Mid": ["Dodger plus hoochie or spinner."],
            "Bottom": ["Fish above marks."],
            "Quick": ["Speed control matters."]
        },
        "Smallmouth bass": {
            "temp_f": (60, 75),
            "Top": ["Poppers early and late."],
            "Mid": ["Swimbaits and jerkbaits."],
            "Bottom": ["Ned rig and tube."],
            "Quick": ["Follow wind."]
        }
    }


def render_species_tips(name, db):
    info = db.get(name)
    if not info:
        st.warning("No tips found.")
        return

    lo, hi = info["temp_f"]

    st.markdown(
        "<div class='card'><div class='card-title'>Species</div>"
        "<div class='card-value'>" + name + "</div></div>",
        unsafe_allow_html=True,
    )

    temp_f = st.number_input("Water temp (F)", value=58.0, step=0.5)
    rating = temp_rating(temp_f, lo, hi)

    st.markdown(
        "<div class='card'><div class='card-title'>Most active range</div>"
        "<div class='card-value'>" + str(lo) + " to " + str(hi) + " F</div>"
        "<span class='badge'>" + rating + "</span></div>",
        unsafe_allow_html=True,
    )

    for section in ["Top", "Mid", "Bottom", "Quick"]:
        st.markdown("<div class='tip-h'>" + section + "</div>", unsafe_allow_html=True)
        st.markdown(
            "<ul class='bul'>" +
            "".join(["<li>" + x + "</li>" for x in info[section]]) +
            "</ul>",
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
        [
            "Best fishing times",
            "Trolling depth calculator",
            "Water temperature targeting",
            "Species tips",
        ],
        label_visibility="collapsed",
    )

    if tool == "Best fishing times":
        st.divider()
        mode = st.radio("Location", ["Current location", "Place name"])
        if mode == "Current location":
            if st.button("Use current location", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = get_location()
        else:
            place = st.text_input("Place name")
            if st.button("Use place", use_container_width=True):
                st.session_state["lat"], st.session_state["lon"] = geocode_place(place)

        st.divider()
        selected_day = st.date_input("Date", value=date.today())

# -------------------------------------------------
# Header (logo left, dynamic title right)
# -------------------------------------------------
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

# -------------------------------------------------
# Main content
# -------------------------------------------------
if tool == "Best fishing times":
    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    if lat and lon:
        times = best_times(lat, lon, selected_day)
        if times:
            m0, m1 = times["morning"]
            e0, e1 = times["evening"]

            st.markdown(
                "<div class='card'><div class='card-title'>Morning window</div>"
                "<div class='card-value'>" +
                m0.strftime("%I:%M %p").lstrip("0") + " - " +
                m1.strftime("%I:%M %p").lstrip("0") +
                "</div></div>",
                unsafe_allow_html=True,
            )

            st.markdown(
                "<div class='card'><div class='card-title'>Evening window</div>"
                "<div class='card-value'>" +
                e0.strftime("%I:%M %p").lstrip("0") + " - " +
                e1.strftime("%I:%M %p").lstrip("0") +
                "</div></div>",
                unsafe_allow_html=True,
            )

elif tool == "Trolling depth calculator":
    st.markdown("### Enter trolling details")
    speed = st.number_input("Speed (mph)", value=1.3, step=0.1)
    weight = st.number_input("Weight (oz)", value=2.0, step=0.5)
    line_out = st.number_input("Line out (ft)", value=100.0, step=5.0)
    line_type = st.radio("Line type", ["Braid", "Fluorocarbon", "Monofilament"])
    line_test = st.selectbox("Line test (lb)", [6, 8, 10, 12, 15, 20, 25, 30], index=5)

    depth = trolling_depth(speed, weight, line_out, line_type, line_test)
    if depth:
        st.markdown(
            "<div class='card'><div class='card-title'>Estimated depth</div>"
            "<div class='card-value'>" + str(depth) + " ft</div></div>",
            unsafe_allow_html=True,
        )

elif tool == "Water temperature targeting":
    temp_f = st.number_input("Water temp (F)", value=58.0, step=0.5)
    targets = temp_targets(temp_f)

    for name, rating, note in targets:
        st.markdown(
            "<div class='card'><div class='card-title'>" + name + "</div>"
            "<div class='card-value'>" + rating + "</div>"
            "<div class='small'>" + note + "</div></div>",
            unsafe_allow_html=True,
        )

else:
    db = species_tip_db()
    species = st.selectbox("Species", sorted(db.keys()))
    render_species_tips(species, db)

# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown(
    "<div class='footer'><strong>FishyNW.com</strong><br>"
    "Independent Northwest fishing tools</div>",
    unsafe_allow_html=True,
)