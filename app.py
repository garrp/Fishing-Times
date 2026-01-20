# app.py
# FishyNW.com - Fishing Tools
# Version 1.7.7
# ASCII ONLY. No Unicode. No smart quotes. No special dashes.

from datetime import datetime, timedelta, date
import requests
import streamlit as st
import streamlit.components.v1 as components

APP_VERSION = "1.7.7"

LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-transparent-with-letters-e1755409608978.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.7.7",
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
# Styles (neutral, no branded colors)
# -------------------------------------------------
st.markdown(
    """
<style>
.block-container {
  padding-top: 1.15rem;
  padding-bottom: 3.25rem;
  max-width: 720px;
}
section[data-testid="stSidebar"] { width: 320px; }

/* Header */
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
  margin-bottom: 6px;
}
.header-logo {
  flex: 0 1 auto;
  max-width: 70%;
}
.header-logo img {
  width: 100%;
  height: auto;
  max-width: 260px;
  display: block;
}
@media (max-width: 520px) {
  .header-logo img { max-width: 70vw; }
}
.header-title {
  text-align: right;
  font-weight: 800;
  font-size: 1.15rem;
  line-height: 1.25rem;
}
.small { opacity: 0.82; font-size: 0.95rem; }

/* Sidebar logo */
.sb-logo {
  text-align: center;
  margin-top: 6px;
  margin-bottom: 10px;
}
.sb-logo img {
  width: 100%;
  max-width: 220px;
  height: auto;
  display: inline-block;
}

/* Cards */
.card {
  border-radius: 18px;
  padding: 16px;
  margin-top: 14px;
  border: 1px solid rgba(0,0,0,0.14);
  background: rgba(0,0,0,0.03);
}
.card-title { font-size: 1rem; opacity: 0.92; }
.card-value { font-size: 1.6rem; font-weight: 800; }
.compact-card { margin-top: 8px !important; padding: 14px 16px !important; }

/* Lists */
.tip-h { font-weight: 800; margin-top: 10px; }
.bul { margin-top: 8px; }
.bul li { margin-bottom: 6px; }

/* Badge */
.badge {
  display: inline-block;
  padding: 6px 10px;
  border-radius: 999px;
  margin: 6px 6px 0 0;
  font-weight: 800;
  font-size: 0.92rem;
  border: 1px solid rgba(0,0,0,0.14);
  background: rgba(0,0,0,0.03);
}

/* Footer */
.footer {
  margin-top: 34px;
  padding-top: 18px;
  border-top: 1px solid rgba(0,0,0,0.14);
  text-align: center;
  font-size: 0.95rem;
  opacity: 0.90;
}

/* Home */
.home-center { text-align: center; margin-top: 18px; }
.home-center .header-logo { max-width: 100%; margin: 0 auto; }
.home-center .header-logo img { max-width: 92vw; }
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
    return {
        "Kokanee": {
            "temp_f": (42, 55),
            "Top": ["Usually not a topwater fish. Focus mid-water columns."],
            "Mid": [
                "Troll dodger plus small hoochie or spinner behind it.",
                "Run scent and tune speed until you get a steady rod thump.",
                "If marks are mid column, match depth with weights or a downrigger."
            ],
            "Bottom": ["Not a bottom target. If they are deep, still fish just above them."],
            "Quick": [
                "Speed is everything. Small changes can turn on the bite.",
                "If you see fish at 35 ft, set gear at about 30 to 33 ft."
            ],
        },
        "Rainbow trout": {
            "temp_f": (45, 65),
            "Top": [
                "When they are up, cast small spinners, spoons, or floating minnows.",
                "Early morning wind lanes can be strong."
            ],
            "Mid": [
                "Troll small spoons or spinners at 1.2 to 1.8 mph.",
                "Use longer leads if the water is clear."
            ],
            "Bottom": ["Still fish bait just off bottom near structure or drop-offs."],
            "Quick": [
                "If bites stop, change lure color or adjust speed slightly.",
                "Follow food and temperature changes."
            ],
        },
        "Lake trout": {
            "temp_f": (42, 55),
            "Top": ["Rare topwater. Most action is deep."],
            "Mid": [
                "If bait is suspended, troll big spoons or tubes through the marks.",
                "Wide turns often trigger strikes."
            ],
            "Bottom": [
                "Work structure: humps, points, deep breaks.",
                "Jig heavy tubes or blade baits on bottom, then lift and drop."
            ],
            "Quick": [
                "Often tight to bottom. Fish within a few feet of it.",
                "When you find one, stay on that contour."
            ],
        },
        "Chinook salmon": {
            "temp_f": (44, 58),
            "Top": ["Occasional surface activity, but most are deeper in summer."],
            "Mid": [
                "Troll flasher plus hoochie or spoon.",
                "Adjust leader length until action looks right.",
                "Make long straight passes with gentle S turns."
            ],
            "Bottom": ["If hugging bottom, run just above them to avoid snagging."],
            "Quick": [
                "Speed and depth control are the game.",
                "Repeat the depth and speed that got your bite."
            ],
        },
        "Smallmouth bass": {
            "temp_f": (60, 75),
            "Top": [
                "Walking baits, poppers early and late.",
                "Wind on points can make topwater fire."
            ],
            "Mid": [
                "Swimbaits, jerkbaits, finesse plastics around rocks and shade.",
                "Slow down on cold fronts."
            ],
            "Bottom": [
                "Ned rig, tube, drop shot on rock and breaks.",
                "If you feel rock and gravel, you are in the zone."
            ],
            "Quick": [
                "Follow wind. It pushes bait and turns on feeding.",
                "After a miss, throw a Ned or drop shot back."
            ],
        },
        "Largemouth bass": {
            "temp_f": (65, 80),
            "Top": [
                "Frog, buzz bait, popper around weeds and shade lines.",
                "Target calm pockets in vegetation."
            ],
            "Mid": [
                "Swim jig or paddletail along weed edges.",
                "Flip soft plastics into holes and let it fall."
            ],
            "Bottom": [
                "Texas rig and jig in thick cover and along drop-offs.",
                "Slow down when pressured."
            ],
            "Quick": [
                "Shade is a magnet: docks, reeds, mats.",
                "Dirty water: go louder and bigger."
            ],
        },
        "Walleye": {
            "temp_f": (55, 70),
            "Top": ["Not common topwater, but they can come shallow at night."],
            "Mid": [
                "Troll crankbaits along breaks at dusk and dawn.",
                "If suspended, match that depth and keep moving."
            ],
            "Bottom": [
                "Jig and crawler or blade bait near bottom.",
                "Bottom bouncer with harness on edges."
            ],
            "Quick": [
                "Low light is best: early, late, cloudy.",
                "Stay on transitions: flats to deep breaks."
            ],
        },
        "Perch": {
            "temp_f": (55, 75),
            "Top": ["Not a true topwater bite. You can catch them shallow though."],
            "Mid": [
                "Small jigs tipped with bait, slowly swum through schools.",
                "If you find one, there are usually more."
            ],
            "Bottom": [
                "Vertical jig small baits on bottom.",
                "Use light line and small hooks."
            ],
            "Quick": [
                "Soft bottom near weeds can be good.",
                "When you mark a school, hold position and pick them off."
            ],
        },
        "Bluegill": {
            "temp_f": (65, 80),
            "Top": ["Tiny poppers can work in summer near shade and cover."],
            "Mid": ["Small jigs under a float with slow retrieves and pauses."],
            "Bottom": ["Tiny jigs and bait near the base of weeds. Downsize when picky."],
            "Quick": ["Beds: fish edges gently. Light line and small hooks matter."],
        },
        "Channel catfish": {
            "temp_f": (65, 85),
            "Top": ["Not topwater. Focus bottom and current edges."],
            "Mid": ["Suspend bait only if you know they are cruising. Bottom is usually best."],
            "Bottom": [
                "Soak bait on scent trails: cut bait, worms, stink bait.",
                "Target holes, outside bends, slow water near current.",
                "Reset to fresh bait if it goes quiet."
            ],
            "Quick": ["Evening and night are prime. Let them load the rod before setting hook."],
        },
        "Trout (general)": {
            "temp_f": (45, 65),
            "Top": ["Cast small spoons and spinners when you see surface activity."],
            "Mid": ["Troll spinners and small spoons at steady speed. Longer leads in clear water."],
            "Bottom": ["Slip sinker and keep bait just off bottom. Slow down if bites are short."],
            "Quick": ["Match hatch. Cloud cover and chop can help."],
        },
    }

def render_species_tips(name, db):
    info = db.get(name)
    if not info:
        st.warning("No tips found.")
        return

    lo, hi = info.get("temp_f", (None, None))

    st.markdown(
        "<div class='card'>"
        "<div class='card-title'>Species</div>"
        "<div class='card-value'>" + name + "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if lo is not None and hi is not None:
        st.markdown(
            "<div class='card'>"
            "<div class='card-title'>Most active water temperature range</div>"
            "<div class='card-value'>" + str(lo) + " to " + str(hi) + " F</div>"
            "<div style='margin-top:10px;'><span class='badge'>Range only</span></div>"
            "</div>",
            unsafe_allow_html=True,
        )

    def section(title, items):
        st.markdown("<div class='tip-h'>" + title + "</div>", unsafe_allow_html=True)
        st.markdown("<ul class='bul'>" + "".join(["<li>" + x + "</li>" for x in items]) + "</ul>", unsafe_allow_html=True)

    section("Topwater", info.get("Top", ["No tips available."]))
    section("Mid water", info.get("Mid", ["No tips available."]))
    section("Bottom", info.get("Bottom", ["No tips available."]))
    section("Quick tips", info.get("Quick", ["No tips available."]))

def phone_speedometer_widget():
    html = """
    <div id="wrap" style="padding:12px;border:1px solid rgba(0,0,0,0.14);border-radius:18px;background:rgba(0,0,0,0.03);">
      <style>
        #wrap { --dial: 112px; --mph: 34px; --gap: 12px; }
        @media (min-width: 720px) { #wrap { --dial: 160px; --mph: 44px; --gap: 16px; } }
        .row { display:flex; align-items:center; gap: var(--gap); }
        .dial {
          width: var(--dial);
          height: var(--dial);
          border-radius: 999px;
          border: 2px solid rgba(0,0,0,0.18);
          display:flex;
          align-items:center;
          justify-content:center;
        }
        .mph { font-size: var(--mph); font-weight: 800; line-height: 1.0; color: inherit; }
      </style>

      <div style="font-weight:800;font-size:18px;margin-bottom:6px;">Speedometer</div>
      <div id="status" style="opacity:0.88;margin-bottom:8px;">Allow location permission...</div>

      <div class="row">
        <div class="dial">
          <div style="text-align:center;">
            <div id="mph" class="mph">--</div>
            <div style="opacity:0.85;">mph</div>
          </div>
        </div>

        <div style="flex:1;">
          <div id="acc" style="opacity:0.82;">Accuracy: --</div>
          <div style="opacity:0.80;margin-top:6px;">If mph is --, start moving and wait a few seconds.</div>
        </div>
      </div>
    </div>

    <script>
      function setText(id, txt){ var el=document.getElementById(id); if(el) el.textContent = txt; }

      if (!navigator.geolocation) {
        setText("status", "Geolocation not supported on this device/browser.");
      } else {
        navigator.geolocation.watchPosition(
          function(pos) {
            var spd = pos.coords.speed;
            var acc = pos.coords.accuracy;

            setText("acc", "Accuracy: " + Math.round(acc) + " m");

            if (spd === null || spd === undefined) {
              setText("mph", "--");
              setText("status", "GPS lock... keep moving.");
              return;
            }

            var mph = spd * 2.236936;
            setText("mph", mph.toFixed(1));
            setText("status", "GPS speed (live)");
          },
          function(err) { setText("status", "Location error: " + err.message); },
          { enableHighAccuracy: true, maximumAge: 500, timeout: 15000 }
        );
      }
    </script>
    """
    components.html(html, height=240)

def render_header(title, centered=False):
    if centered:
        st.markdown(
            "<div class='home-center'>"
            "<div class='header-logo'><img src='" + LOGO_URL + "'></div>"
            "<div class='small' style='margin-top:10px;'>Use the menu to open Best fishing times.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        "<div class='header-row'>"
        "<div class='header-logo'><img src='" + LOGO_URL + "'></div>"
        "<div class='header-title'>" + title + "</div>"
        "</div>"
        "<div class='small' style='text-align:left;'>Independent Northwest fishing tools</div>",
        unsafe_allow_html=True,
    )

# -------------------------------------------------
# Session defaults
# -------------------------------------------------
if "tool" not in st.session_state:
    st.session_state["tool"] = "Home"
if "lat" not in st.session_state:
    st.session_state["lat"] = None
if "lon" not in st.session_state:
    st.session_state["lon"] = None
if "best_go" not in st.session_state:
    st.session_state["best_go"] = False

PAGE_TITLES = {
    "Home": "",
    "Best fishing times": "Best Fishing Times",
    "Trolling depth calculator": "Trolling Depth Calculator",
    "Water temperature targeting": "Water Temperature Targeting",
    "Species tips": "Species Tips",
    "Speedometer": "Speedometer",
}

# -------------------------------------------------
# Sidebar navigation (with centered logo at top)
# -------------------------------------------------
with st.sidebar:
    st.markdown(
        "<div class='sb-logo'><img src='" + LOGO_URL + "'></div>",
        unsafe_allow_html=True,
    )

    st.caption("Version " + APP_VERSION)

    if st.button("Best fishing times", use_container_width=True, key="nav_best_times"):
        st.session_state["tool"] = "Best fishing times"
        st.session_state["lat"], st.session_state["lon"] = get_location()
        st.session_state["best_go"] = False

    if st.button("Trolling depth calculator", use_container_width=True, key="nav_depth"):
        st.session_state["tool"] = "Trolling depth calculator"

    if st.button("Water temperature targeting", use_container_width=True, key="nav_temp"):
        st.session_state["tool"] = "Water temperature targeting"

    if st.button("Species tips", use_container_width=True, key="nav_species"):
        st.session_state["tool"] = "Species tips"

    if st.button("Speedometer", use_container_width=True, key="nav_speed"):
        st.session_state["tool"] = "Speedometer"

tool = st.session_state["tool"]

# -------------------------------------------------
# Home page: logo only (fits screen)
# -------------------------------------------------
if tool == "Home":
    render_header("", centered=True)
    st.stop()

# -------------------------------------------------
# Header (all other pages)
# -------------------------------------------------
render_header(PAGE_TITLES.get(tool, ""))

# -------------------------------------------------
# Main content
# -------------------------------------------------
if tool == "Best fishing times":
    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    st.markdown("### Location")

    # Side-by-side latitude and longitude (always)
    c0, c1 = st.columns(2)
    with c0:
        lat_in = st.text_input("Latitude (optional)", value=("" if lat is None else str(lat)), key="manual_lat")
    with c1:
        lon_in = st.text_input("Longitude (optional)", value=("" if lon is None else str(lon)), key="manual_lon")

    use_manual = False
    try:
        if lat_in.strip() != "" and lon_in.strip() != "":
            lat_m = float(lat_in.strip())
            lon_m = float(lon_in.strip())
            if -90.0 <= lat_m <= 90.0 and -180.0 <= lon_m <= 180.0:
                lat, lon = lat_m, lon_m
                use_manual = True
            else:
                st.warning("Latitude must be -90 to 90. Longitude must be -180 to 180.")
    except Exception:
        st.warning("Latitude and longitude must be numbers.")

    st.markdown("<div class='small'>Leave blank to use your current location.</div>", unsafe_allow_html=True)

    if st.button("Display Best Fishing Times", use_container_width=True, key="go_best_times"):
        st.session_state["best_go"] = True
        if not use_manual:
            st.session_state["lat"], st.session_state["lon"] = get_location()
        else:
            st.session_state["lat"], st.session_state["lon"] = lat, lon

    if st.session_state.get("best_go"):
        lat = st.session_state.get("lat")
        lon = st.session_state.get("lon")

        st.markdown("### Date range")
        d0, d1 = st.columns(2)
        with d0:
            start_day = st.date_input("Start date", value=date.today(), key="range_start")
        with d1:
            end_day = st.date_input("End date", value=date.today(), key="range_end")

        st.markdown("<div class='small'>Select a start and end date. Results will show for each day in the range.</div>", unsafe_allow_html=True)

        if end_day < start_day:
            st.warning("End date must be the same as or after start date.")
        elif lat is None or lon is None:
            st.info("Enter latitude and longitude, or tap the button again to use current location.")
        else:
            day_list = []
            cur = start_day
            while cur <= end_day:
                day_list.append(cur)
                if len(day_list) >= 14:
                    break
                cur = cur + timedelta(days=1)

            if len(day_list) == 14 and end_day > day_list[-1]:
                st.info("Showing first 14 days only. Shorten the range to see more detail.")

            for d in day_list:
                st.markdown("## " + d.strftime("%A") + " - " + d.strftime("%b %d, %Y"))

                times = best_times(lat, lon, d)
                if not times:
                    st.warning("Unable to calculate fishing times for this day.")
                    continue

                m0, m1 = times["morning"]
                e0, e1 = times["evening"]

                st.markdown(
                    "<div class='card compact-card'><div class='card-title'>Morning window</div>"
                    "<div class='card-value'>" +
                    m0.strftime("%I:%M %p").lstrip("0") +
                    " - " +
                    m1.strftime("%I:%M %p").lstrip("0") +
                    "</div></div>",
                    unsafe_allow_html=True,
                )

                st.markdown(
                    "<div class='card compact-card'><div class='card-title'>Evening window</div>"
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
                        "<div class='card compact-card'><div class='card-title'>" + h +
                        "</div><div class='card-value'>" +
                        str(wind.get(h, "--")) + " mph</div></div>",
                        unsafe_allow_html=True,
                    )
    else:
        st.markdown("<div class='small'>Tap the button to show date range and results.</div>", unsafe_allow_html=True)

elif tool == "Trolling depth calculator":
    st.markdown("### Trolling depth calculator")
    st.markdown("<div class='small'>Location not required.</div>", unsafe_allow_html=True)

    speed = st.number_input("Speed (mph)", 0.0, value=1.3, step=0.1)
    weight = st.number_input("Weight (oz)", 0.0, value=2.0, step=0.5)
    line_out = st.number_input("Line out (feet)", 0.0, value=100.0, step=5.0)

    col1, col2 = st.columns(2)
    with col1:
        line_type = st.radio("Line type", ["Braid", "Fluorocarbon", "Monofilament"])
    with col2:
        line_test = st.selectbox("Line test (lb)", [6, 8, 10, 12, 15, 20, 25, 30, 40, 50], index=3)

    depth = trolling_depth(speed, weight, line_out, line_type, line_test)

    st.markdown(
        "<div class='card'><div class='card-title'>Estimated depth</div>"
        "<div class='card-value'>" +
        (str(depth) if depth is not None else "--") + " ft</div>"
        "<div class='small' style='margin-top:8px;'>Heavier line runs shallower. Current and lure drag also affect results.</div>"
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

elif tool == "Species tips":
    st.markdown("### Species tips")
    st.markdown("<div class='small'>Pick a species and get tips plus its best activity temperature range.</div>", unsafe_allow_html=True)

    db = species_tip_db()
    species_list = sorted(list(db.keys()))
    species = st.selectbox("Species", species_list)

    render_species_tips(species, db)

else:
    st.markdown("### Speedometer")
    st.markdown("<div class='small'>GPS speed from your phone browser. Works best once GPS has a lock and you are moving.</div>", unsafe_allow_html=True)
    phone_speedometer_widget()

# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown(
    "<div class='footer'><strong>FishyNW.com</strong><br>"
    "Independent Northwest fishing tools</div>",
    unsafe_allow_html=True,
)
