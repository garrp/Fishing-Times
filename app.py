# app.py
# FishyNW.com - Best Fishing Times, Trolling Depth, and Water Temp Targeting
# Version 1.2

from datetime import datetime, timedelta, date
import requests
import streamlit as st

APP_VERSION = "1.2"
LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-Transparent.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.2",
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
.tag {
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.16);
  background: rgba(255,255,255,0.04);
  margin: 6px 6px 0 0;
  font-weight: 700;
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


def c_to_f(c):
    return (c * 9.0 / 5.0) + 32.0


def f_to_c(f):
    return (f - 32.0) * 5.0 / 9.0


def temp_targets(temp_f):
    # PNW-leaning targets. These are rule-of-thumb ranges.
    # Returns a sorted list of (species, rating, notes)
    t = temp_f

    items = []

    def add(name, lo, hi, note):
        if t < lo - 5 or t > hi + 5:
            rating = "Low"
        elif lo <= t <= hi:
            rating = "Best"
        else:
            rating = "Fair"
        items.append((name, rating, note))

    add("Trout (rainbow/brown)", 45, 65, "Better in cool water. Focus mornings and shade when warmer.")
    add("Kokanee", 42, 55, "Cool water. Often deeper when surface warms.")
    add("Chinook salmon", 44, 58, "Cool water. Often deeper and near current.")
    add("Lake trout", 42, 55, "Cold water. Usually deeper structure.")
    add("Smallmouth bass", 60, 75, "Warmer water. Rocks, points, wind-blown banks.")
    add("Largemouth bass", 65, 80, "Warm water. Weeds, pads, shallow cover.")
    add("Walleye", 55, 70, "Mid temps. Low light windows are strong.")
    add("Panfish (perch/bluegill)", 60, 80, "Warm water. Shallows and cover.")
    add("Catfish (channel)", 65, 85, "Warm water. Evening and night bites.")

    # Prioritize Best, then Fair, then Low
    rank = {"Best": 0, "Fair": 1, "Low": 2}
    items.sort(key=lambda x: rank[x[1]])
    return items

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
        ["Best fishing times", "Trolling depth calculator", "Water temperature targeting"],
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
    st.markdown("### Water temperature targeting")
    st.markdown("<div class='small'>Enter water temperature and get target species suggestions.</div>", unsafe_allow_html=True)

    unit = st.radio("Units", ["F", "C"], horizontal=True)

    if unit == "F":
        temp_f = st.number_input("Water temp (F)", value=58.0, step=0.5)
    else:
        temp_c = st.number_input("Water temp (C)", value=14.5, step=0.5)
        temp_f = c_to_f(temp_c)

    st.markdown(
        "<div class='card'><div class='card-title'>Water temperature</div>"
        "<div class='card-value'>" + str(round(temp_f, 1)) + " F</div></div>",
        unsafe_allow_html=True,
    )

    targets = temp_targets(temp_f)

    # Show top group first
    best = [x for x in targets if x[1] == "Best"]
    fair = [x for x in targets if x[1] == "Fair"]
    low = [x for x in targets if x[1] == "Low"]

    if best:
        st.markdown("#### Best targets")
        for name, rating, note in best:
            st.markdown(
                "<div class='card'>"
                "<div class='card-title'>" + name + "</div>"
                "<div class='card-value'>" + rating + "</div>"
                "<div class='small' style='margin-top:8px;'>" + note + "</div>"
                "</div>",
                unsafe_allow_html=True,
            )

    if fair:
        st.markdown("#### Fair targets")
        for name, rating, note in fair:
            st.markdown(
                "<div class='card'>"
                "<div class='card-title'>" + name + "</div>"
                "<div class='card-value'>" + rating + "</div>"
                "<div class='small' style='margin-top:8px;'>" + note + "</div>"
                "</div>",
                unsafe_allow_html=True,
            )

    if low and not best:
        st.markdown("#### Low targets")
        for name, rating, note in low[:4]:
            st.markdown(
                "<div class='card'>"
                "<div class='card-title'>" + name + "</div>"
                "<div class='card-value'>" + rating + "</div>"
                "<div class='small' style='margin-top:8px;'>" + note + "</div>"
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