# app.py
# FishyNW.com - Best Fishing Times, Trolling Depth, Water Temp Targeting, and Species Tips
# Version 1.3

from datetime import datetime, timedelta, date
import requests
import streamlit as st

APP_VERSION = "1.3"
LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-Transparent.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.3",
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
.block-container { padding-top: 1.5rem; padding-bottom: 2.5rem; max-width: 720px; }
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
.footer {
  margin-top: 40px;
  padding-top: 20px;
  border-top: 1px solid rgba(255,255,255,0.15);
  text-align: center;
  font-size: 0.95rem;
  opacity: 0.7;
}
button { border-radius: 14px; }
.tip-h { font-weight: 800; margin-top: 10px; }
.tip-p { opacity: 0.85; line-height: 1.35; }
.bul { margin-top: 8px; }
.bul li { margin-bottom: 6px; }
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


def temp_targets(temp_f):
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

    add("Trout (rainbow/brown)", 45, 65, "Cool water. Better early and in shade when warmer.")
    add("Kokanee", 42, 55, "Cool water. Often deeper when surface warms.")
    add("Chinook salmon", 44, 58, "Cool water. Often deeper and near current.")
    add("Lake trout", 42, 55, "Cold water. Usually deeper structure.")
    add("Smallmouth bass", 60, 75, "Warmer water. Rocks, points, wind-blown banks.")
    add("Largemouth bass", 65, 80, "Warm water. Weeds and shallow cover.")
    add("Walleye", 55, 70, "Mid temps. Low light windows are strong.")
    add("Panfish (perch/bluegill)", 60, 80, "Warm water. Shallows and cover.")
    add("Catfish (channel)", 65, 85, "Warm water. Evening and night bites.")

    rank = {"Best": 0, "Fair": 1, "Low": 2}
    items.sort(key=lambda x: rank[x[1]])
    return items


def species_tip_db():
    # All ASCII. Practical PNW-friendly tips.
    return {
        "Kokanee": {
            "Top": [
                "Usually not a topwater fish. Focus mid-water columns."
            ],
            "Mid": [
                "Troll dodger plus small hoochie or spinner behind it.",
                "Run scent and tune speed until you get a steady rod thump.",
                "If marks are mid column, match depth with weights or a downrigger."
            ],
            "Bottom": [
                "Not a bottom target. If they are deep, still fish just above them."
            ],
            "Quick": [
                "Speed is everything. Small changes can turn on the bite.",
                "If you see fish at 35 ft, set gear at about 30 to 33 ft."
            ],
        },
        "Rainbow trout": {
            "Top": [
                "When they are up, cast small spinners, spoons, or floating minnows.",
                "Early morning wind lanes can be money."
            ],
            "Mid": [
                "Troll small spoons, wedding rings, or spinners at 1.2 to 1.8 mph.",
                "Use long leads if the water is clear."
            ],
            "Bottom": [
                "Slow down and run a bottom bouncer or drift a bait rig near structure.",
                "If fishing still, suspend bait just off bottom."
            ],
            "Quick": [
                "If bites stop, change lure color or slow down slightly.",
                "Follow the food: insects, fry, and edges of temperature changes."
            ],
        },
        "Lake trout": {
            "Top": [
                "Rare topwater. Most action is deep."
            ],
            "Mid": [
                "If bait is suspended, troll big spoons or tubes through the marks.",
                "Use steady speed and wide turns to trigger strikes."
            ],
            "Bottom": [
                "Work structure: humps, points, and deep breaks.",
                "Jig heavy tubes or blade baits right on bottom, then lift and drop."
            ],
            "Quick": [
                "They often sit tight to bottom. Fish within a few feet of it.",
                "When you find one, stay on that depth and contour."
            ],
        },
        "Chinook salmon": {
            "Top": [
                "Occasional surface activity, but most are deeper in summer."
            ],
            "Mid": [
                "Troll flasher plus hoochie or spoon.",
                "Adjust leader length until the action looks right.",
                "Make long straight passes with gentle S turns."
            ],
            "Bottom": [
                "If they are hugging bottom, run just above them to avoid snagging."
            ],
            "Quick": [
                "Speed and depth control are the game.",
                "If you get one bite, repeat that line, depth, and speed."
            ],
        },
        "Smallmouth bass": {
            "Top": [
                "Walking baits, poppers, and small buzz baits early and late.",
                "Wind on points can make topwater fire."
            ],
            "Mid": [
                "Swimbaits, jerkbaits, and finesse plastics around rocks and shade.",
                "Slow down on cold fronts and fish suspending baits."
            ],
            "Bottom": [
                "Ned rig, tube, and drop shot on rock piles and breaks.",
                "If you feel gravel and rock, you are in the zone."
            ],
            "Quick": [
                "Follow wind. It pushes bait and turns on feeding.",
                "If you miss one, throw a Ned or drop shot right back."
            ],
        },
        "Largemouth bass": {
            "Top": [
                "Frog, buzz bait, or popper around weeds and shade lines.",
                "Target calm pockets in vegetation."
            ],
            "Mid": [
                "Swim jig or paddletail along weed edges.",
                "Flip soft plastics into holes and let it fall."
            ],
            "Bottom": [
                "Texas rig and jig in thick cover and along drop offs.",
                "Slow and deliberate wins when they are pressured."
            ],
            "Quick": [
                "Shade is a magnet. Docks, reeds, mats.",
                "If the water is dirty, go louder and bigger."
            ],
        },
        "Walleye": {
            "Top": [
                "Not common topwater, but they can come shallow at night."
            ],
            "Mid": [
                "Troll crankbaits along breaks at dusk and dawn.",
                "If they are suspended, match that depth and keep moving."
            ],
            "Bottom": [
                "Jig and crawler, jig and minnow, or a blade bait near bottom.",
                "Slow roll a bottom bouncer with a harness."
            ],
            "Quick": [
                "Low light windows are best: early, late, and cloudy days.",
                "Stay on the edge: flats to deep water transitions."
            ],
        },
        "Perch": {
            "Top": [
                "Not a true topwater bite. You can catch them shallow though."
            ],
            "Mid": [
                "Small jigs tipped with bait, slowly swum through schools.",
                "If you find one, there are usually more."
            ],
            "Bottom": [
                "Vertical jig small baits right on bottom.",
                "Use light line and small hooks."
            ],
            "Quick": [
                "Look for soft bottom near weeds and structure.",
                "When you mark a school, hold position and pick them off."
            ],
        },
        "Bluegill": {
            "Top": [
                "Small poppers or tiny bugs can work in summer.",
                "Fish near cover and shade."
            ],
            "Mid": [
                "Small plastics or jigs under a float.",
                "Slow retrieves and pauses."
            ],
            "Bottom": [
                "Tiny jigs and bait near the base of weeds.",
                "Downsize when they get picky."
            ],
            "Quick": [
                "If you see beds, work the edges and be gentle.",
                "Light line and small hooks matter."
            ],
        },
        "Channel catfish": {
            "Top": [
                "Not topwater. Focus bottom and current edges."
            ],
            "Mid": [
                "Suspend bait if fish are cruising, but bottom is usually best."
            ],
            "Bottom": [
                "Anchor and soak bait on scent trails: cut bait, worms, or stink bait.",
                "Target outside bends, holes, and slow water near current.",
                "Give it time, then reset to fresh scent."
            ],
            "Quick": [
                "Night and evening are prime.",
                "When you get a bite, let them load the rod before setting."
            ],
        },
        "Trout (general)": {
            "Top": [
                "Cast small spoons and spinners when you see surface activity.",
                "Work shorelines early and wind lanes mid day."
            ],
            "Mid": [
                "Troll spinners and small spoons, steady speed.",
                "Longer leads in clear water."
            ],
            "Bottom": [
                "If still fishing, use a slip sinker and keep bait just off bottom.",
                "Slow down if bites are short."
            ],
            "Quick": [
                "Match hatch: insects in spring, fry later.",
                "Cloud cover and chop can help."
            ],
        },
    }


def render_species_tips(name, db):
    info = db.get(name)
    if not info:
        st.warning("No tips found.")
        return

    st.markdown("<div class='card'><div class='card-title'>Species</div><div class='card-value'>" + name + "</div></div>", unsafe_allow_html=True)

    def section(title, items):
        st.markdown("<div class='tip-h'>" + title + "</div>", unsafe_allow_html=True)
        st.markdown("<ul class='bul'>" + "".join(["<li>" + x + "</li>" for x in items]) + "</ul>", unsafe_allow_html=True)

    section("Topwater", info.get("Top", ["No tips available."]))
    section("Mid water", info.get("Mid", ["No tips available."]))
    section("Bottom", info.get("Bottom", ["No tips available."]))
    section("Quick tips", info.get("Quick", ["No tips available."]))

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
        ["Best fishing times", "Trolling depth calculator", "Water temperature targeting", "Species tips"],
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

elif tool == "Water temperature targeting":
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

else:
    st.markdown("### Species tips")
    st.markdown("<div class='small'>Pick a species and get practical tips by water column.</div>", unsafe_allow_html=True)

    db = species_tip_db()
    species_list = sorted(list(db.keys()))
    species = st.selectbox("Species", species_list)

    render_species_tips(species, db)

# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown(
    "<div class='footer'><strong>FishyNW.com</strong><br>"
    "Independent Northwest fishing tools</div>",
    unsafe_allow_html=True,
)