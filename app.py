# app.py
# FishyNW.com - Fishing Tools
# Version 1.9.2
# ASCII ONLY. No Unicode. No smart quotes. No special dashes.

from datetime import datetime, timedelta, date
import time
import requests
import streamlit as st
import streamlit.components.v1 as components

APP_VERSION = "1.9.2"

LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-transparent-with-letters-e1755409608978.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.9.2",
    "Accept": "application/json",
}

# -------------------------------------------------
# Page config
# -------------------------------------------------
st.set_page_config(
    page_title="FishyNW.com | Fishing Tools",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------
# State
# -------------------------------------------------
if "page" not in st.session_state:
    st.session_state["page"] = "Home"

# Shared saved location
if "loc_lat" not in st.session_state:
    st.session_state["loc_lat"] = None
if "loc_lon" not in st.session_state:
    st.session_state["loc_lon"] = None
if "loc_label" not in st.session_state:
    st.session_state["loc_label"] = ""

# -------------------------------------------------
# CSS
# -------------------------------------------------
st.markdown(
    """
<style>
.block-container { max-width: 860px; padding-top: 1.05rem; padding-bottom: 4.0rem; }

.small { opacity: 0.86; font-size: 0.95rem; }
.muted { opacity: 0.78; }

.header {
  display:flex; align-items:center; justify-content:space-between;
  gap: 16px; margin-top: 6px; margin-bottom: 10px;
}
.logo img { width: 100%; max-width: 270px; height: auto; display:block; }
@media (max-width: 520px){ .logo img { max-width: 72vw; } }
.version { font-weight: 800; font-size: 0.95rem; opacity: 0.85; text-align:right; }

.card {
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(0,0,0,0.14);
  background: rgba(0,0,0,0.03);
  margin-top: 12px;
}
@media (prefers-color-scheme: dark) {
  .card { border: 1px solid rgba(255,255,255,0.16); background: rgba(255,255,255,0.06); }
}

.card-title { font-weight: 800; margin-bottom: 6px; }
.kpi { font-size: 1.7rem; font-weight: 900; line-height: 1.0; }
.kpi-sub { opacity: 0.86; margin-top: 6px; }

div.stButton > button, button[kind="primary"] {
  background-color: #8fd19e !important;
  color: #0b2e13 !important;
  border: 1px solid #6fbf87 !important;
  font-weight: 900 !important;
  border-radius: 12px !important;
  min-height: 48px !important;
}
div.stButton > button:hover, button[kind="primary"]:hover {
  background-color: #7cc78f !important;
  color: #08210f !important;
}
div.stButton > button:disabled {
  background-color: #cfe8d6 !important;
  color: #6b6b6b !important;
  border-color: #b6d6c1 !important;
}

div[data-baseweb="input"] input,
div[data-baseweb="select"] > div {
  min-height: 46px !important;
}

.footer {
  margin-top: 34px;
  padding-top: 18px;
  border-top: 1px solid rgba(0,0,0,0.14);
  text-align:center;
  font-size: 0.95rem;
  opacity: 0.9;
}
@media (prefers-color-scheme: dark) {
  .footer { border-top: 1px solid rgba(255,255,255,0.16); }
}
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Network helpers (cache + tiny retry)
# -------------------------------------------------
def _get(url, timeout=10):
    last = None
    for _ in range(2):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            time.sleep(0.25)
    raise last

@st.cache_data(ttl=900, show_spinner=False)
def get_json(url, timeout=10):
    return _get(url, timeout=timeout).json()

def norm(s):
    s = "" if s is None else str(s)
    return " ".join(s.strip().split())

# -------------------------------------------------
# Location and APIs
# -------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def ip_location():
    try:
        data = get_json("https://ipinfo.io/json", timeout=6)
        loc = data.get("loc")
        if not loc:
            return None, None
        lat, lon = loc.split(",")
        return float(lat), float(lon)
    except Exception:
        return None, None

@st.cache_data(ttl=86400, show_spinner=False)
def geocode(place_name, count=10):
    try:
        q = norm(place_name)
        if not q:
            return []
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            "?name=" + requests.utils.quote(q) +
            "&count=" + str(int(count)) + "&language=en&format=json"
        )
        data = get_json(url, timeout=8)
        results = data.get("results") or []
        out = []
        for r in results:
            lat = r.get("latitude")
            lon = r.get("longitude")
            if lat is None or lon is None:
                continue
            name = str(r.get("name") or q)
            admin1 = str(r.get("admin1") or "").strip()
            country = str(r.get("country") or "").strip()
            parts = [name]
            if admin1:
                parts.append(admin1)
            if country:
                parts.append(country)
            label = ", ".join(parts)
            out.append({"label": label, "lat": float(lat), "lon": float(lon)})
        return out
    except Exception:
        return []

@st.cache_data(ttl=86400, show_spinner=False)
def sun_times(lat, lon, day_iso):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=" + str(lat) +
        "&longitude=" + str(lon) +
        "&start_date=" + day_iso +
        "&end_date=" + day_iso +
        "&daily=sunrise,sunset&timezone=auto"
    )
    try:
        data = get_json(url, timeout=10)
        sr = data["daily"]["sunrise"][0]
        ss = data["daily"]["sunset"][0]
        return datetime.fromisoformat(sr), datetime.fromisoformat(ss)
    except Exception:
        return None, None

def bite_windows(lat, lon, day_obj):
    sr, ss = sun_times(lat, lon, day_obj.isoformat())
    if not sr or not ss:
        return None
    return {
        "morning": (sr - timedelta(hours=1), sr + timedelta(hours=1)),
        "evening": (ss - timedelta(hours=1), ss + timedelta(hours=1)),
    }

@st.cache_data(ttl=600, show_spinner=False)
def winds(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        "?latitude=" + str(lat) +
        "&longitude=" + str(lon) +
        "&hourly=wind_speed_10m"
        "&wind_speed_unit=mph"
        "&timezone=auto"
        "&current=wind_speed_10m"
    )
    try:
        data = get_json(url, timeout=10)
        by_time = {}
        for t, s in zip(data["hourly"]["time"], data["hourly"]["wind_speed_10m"]):
            by_time[t] = round(float(s), 1)
        cur_dt = None
        try:
            cur_dt = datetime.fromisoformat(data.get("current", {}).get("time"))
        except Exception:
            cur_dt = None
        cur_mph = None
        try:
            cur_mph = round(float(data.get("current", {}).get("wind_speed_10m")), 1)
        except Exception:
            cur_mph = None
        return by_time, cur_dt, cur_mph
    except Exception:
        return {}, None, None

def split_winds(by_time, cur_dt):
    current = []
    future = []
    for k in sorted(by_time.keys()):
        try:
            dt = datetime.fromisoformat(k)
        except Exception:
            continue
        mph = by_time.get(k)
        label = dt.strftime("%a %b %d, %I %p").replace(" 0", " ").replace(":00", "")
        if cur_dt is None:
            future.append((label, mph))
        else:
            if dt <= cur_dt:
                current.append((label, mph))
            else:
                future.append((label, mph))
    return current[-6:], future[:12]

def depth_est(speed_mph, weight_oz, line_out_ft, line_type, line_test_lb):
    if speed_mph <= 0 or weight_oz <= 0 or line_out_ft <= 0 or line_test_lb <= 0:
        return None
    type_drag = {"Braid": 1.0, "Fluorocarbon": 1.12, "Monofilament": 1.2}[line_type]
    test_ratio = line_test_lb / 20.0
    test_drag = test_ratio ** 0.35
    total_drag = type_drag * test_drag
    depth = 0.135 * (weight_oz / (total_drag * (speed_mph ** 1.35))) * line_out_ft
    return round(depth, 1)

def speedometer_widget():
    html = """
    <div style="padding:12px;border:1px solid rgba(0,0,0,0.14);border-radius:18px;background:rgba(0,0,0,0.03);">
      <style>
        .row { display:flex; align-items:center; gap: 14px; }
        .dial {
          width: 150px; height: 150px; border-radius: 999px;
          border: 2px solid rgba(0,0,0,0.18);
          display:flex; align-items:center; justify-content:center;
        }
        @media (max-width: 520px){ .dial { width: 120px; height: 120px; } }
        .mph { font-size: 44px; font-weight: 900; line-height: 1.0; }
        @media (max-width: 520px){ .mph { font-size: 34px; } }
      </style>
      <div style="font-weight:900;font-size:18px;margin-bottom:6px;">Speedometer</div>
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
          <div style="opacity:0.80;margin-top:6px;">Tip: GPS speed reads best while moving steadily.</div>
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
    components.html(html, height=250)

# -------------------------------------------------
# Species tips
# -------------------------------------------------
def species_db():
    return {
        "Kokanee": {
            "temp_f": (42, 55),
            "Depths": ["Mid"],
            "Baits": ["Small hoochies", "Small spinners (wedding ring)", "Corn with scent (where used)"],
            "Rigs": ["Dodger + leader + hoochie/spinner", "Weights or downrigger to match marks"],
            "Mid": [
                "Troll dodger plus small hoochie or spinner behind it.",
                "Run scent and tune speed until you get a steady rod thump.",
                "If marks are mid column, match depth with weights or a downrigger."
            ],
            "Quick": [
                "Speed is everything. Small changes can turn on the bite.",
                "If you see fish at 35 ft, set gear at about 30 to 33 ft."
            ],
        },
        "Rainbow trout": {
            "temp_f": (45, 65),
            "Depths": ["Top", "Mid", "Bottom"],
            "Baits": ["Small spoons", "Inline spinners", "Floating minnows", "Worms (where legal)", "PowerBait (where legal)"],
            "Rigs": ["Cast and retrieve", "Trolling with long leads", "Slip sinker bait rig (near bottom)"],
            "Top": [
                "When they are up, cast small spinners, spoons, or floating minnows.",
                "Early morning wind lanes can be strong."
            ],
            "Mid": [
                "Troll small spoons or spinners at 1.2 to 1.8 mph.",
                "Use longer leads if the water is clear."
            ],
            "Bottom": [
                "Still fish bait just off bottom near structure or drop-offs.",
                "If snaggy, lift your bait slightly above bottom."
            ],
            "Quick": [
                "If bites stop, change lure color or adjust speed slightly.",
                "Follow food and temperature changes."
            ],
        },
        "Lake trout": {
            "temp_f": (42, 55),
            "Depths": ["Mid", "Bottom"],
            "Baits": ["Tube jigs", "Large spoons", "Blade baits", "Swimbaits (deep)"],
            "Rigs": ["Vertical jigging (heavy jig head + tube)", "Deep trolling with weights or downrigger"],
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
            "Depths": ["Mid", "Bottom"],
            "Baits": ["Hoochies", "Spoons", "Spinners", "Cut plug / herring style (where used)"],
            "Rigs": ["Flasher + leader + hoochie/spoon", "Weights or downrigger for depth control"],
            "Mid": [
                "Troll flasher plus hoochie or spoon.",
                "Adjust leader length until action looks right.",
                "Make long straight passes with gentle S turns."
            ],
            "Bottom": [
                "If they are hugging bottom, run just above them to avoid snagging.",
                "Use your sonar to stay off bottom and repeat productive passes."
            ],
            "Quick": [
                "Speed and depth control are the game.",
                "Repeat the depth and speed that got your bite."
            ],
        },
        "Smallmouth bass": {
            "temp_f": (60, 75),
            "Depths": ["Top", "Mid", "Bottom"],
            "Baits": ["Walking baits", "Poppers", "Jerkbaits", "Swimbaits", "Ned rigs", "Tubes", "Drop shot plastics"],
            "Rigs": ["Ned rig", "Drop shot", "Tube jig"],
            "Top": [
                "Walking baits and poppers early and late.",
                "Wind on points can make topwater fire."
            ],
            "Mid": [
                "Jerkbaits and swimbaits around rocks and shade.",
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
            "Depths": ["Top", "Mid", "Bottom"],
            "Baits": ["Frogs", "Buzzbaits", "Swim jigs", "Texas rig plastics", "Jigs"],
            "Rigs": ["Texas rig", "Swim jig", "Pitching jig"],
            "Top": [
                "Frog and buzzbait around weeds and shade lines.",
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
            "Depths": ["Mid", "Bottom"],
            "Baits": ["Crankbaits (trolling)", "Jigs with soft plastics", "Jigs with crawler (where used)", "Blade baits"],
            "Rigs": ["Jig and soft plastic", "Bottom bouncer + harness (where used)", "Trolling crankbaits on breaks"],
            "Mid": [
                "Troll crankbaits along breaks at dusk and dawn.",
                "If suspended, match that depth and keep moving."
            ],
            "Bottom": [
                "Jig near bottom on transitions and edges.",
                "Slow roll a blade bait near bottom when fish are active."
            ],
            "Quick": [
                "Low light is best: early, late, cloudy.",
                "Stay on transitions: flats to deep breaks."
            ],
        },
        "Perch": {
            "temp_f": (55, 75),
            "Depths": ["Mid", "Bottom"],
            "Baits": ["Small jigs", "Worm pieces", "Minnow (where allowed)", "Tiny grubs"],
            "Rigs": ["Small jighead + bait", "Dropper loop with small hook (where used)"],
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
            "Depths": ["Top", "Mid"],
            "Baits": ["Tiny poppers", "Small jigs", "Worm pieces", "Micro plastics"],
            "Rigs": ["Float + small jig/hook", "Ultralight jighead"],
            "Top": ["Tiny poppers can work in summer near shade and cover."],
            "Mid": [
                "Small jigs under a float with slow retrieves and pauses.",
                "Downsize until you get consistent bites."
            ],
            "Quick": ["Beds: fish edges gently. Light line and small hooks matter."],
        },
        "Channel catfish": {
            "temp_f": (65, 85),
            "Depths": ["Bottom"],
            "Baits": ["Cut bait", "Worms", "Stink bait", "Chicken liver (where used)"],
            "Rigs": ["Slip sinker / Carolina rig", "Santee Cooper style (float bait slightly)"],
            "Bottom": [
                "Soak bait on scent trails: cut bait, worms, stink bait.",
                "Target holes, outside bends, slow water near current.",
                "Reset to fresh bait if it goes quiet."
            ],
            "Quick": ["Evening and night are prime. Let them load the rod before setting hook."],
        },
        "Trout (general)": {
            "temp_f": (45, 65),
            "Depths": ["Top", "Mid", "Bottom"],
            "Baits": ["Spoons", "Inline spinners", "Worms (where legal)", "PowerBait (where legal)"],
            "Rigs": ["Cast and retrieve", "Trolling (long leads)", "Slip sinker bait rig"],
            "Top": ["Cast spoons and spinners when you see surface activity."],
            "Mid": ["Troll spinners and small spoons. Longer leads in clear water."],
            "Bottom": ["Slip sinker and keep bait just off bottom. Slow down if bites are short."],
            "Quick": ["Match hatch. Cloud cover and chop can help."],
        },
    }

def render_species(name, info):
    lo, hi = info.get("temp_f", (None, None))
    depths = info.get("Depths", [])
    baits = info.get("Baits", [])
    rigs = info.get("Rigs", [])

    st.markdown(
        "<div class='card'><div class='card-title'>Most active water temp</div>"
        "<div class='kpi'>" + str(lo) + " to " + str(hi) + " F</div>"
        "<div class='kpi-sub'>Depth focus: " + ", ".join(depths) + "</div></div>",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            "<div class='card'><div class='card-title'>Popular baits</div><ul>" +
            "".join(["<li>" + x + "</li>" for x in baits]) + "</ul></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            "<div class='card'><div class='card-title'>Common rigs</div><ul>" +
            "".join(["<li>" + x + "</li>" for x in rigs]) + "</ul></div>",
            unsafe_allow_html=True,
        )

    def section(title, key):
        items = info.get(key, [])
        if not items:
            return
        st.markdown(
            "<div class='card'><div class='card-title'>" + title + "</div><ul>" +
            "".join(["<li>" + x + "</li>" for x in items]) + "</ul></div>",
            unsafe_allow_html=True,
        )

    if "Top" in depths:
        section("Topwater tips", "Top")
    if "Mid" in depths:
        section("Mid water tips", "Mid")
    if "Bottom" in depths:
        section("Bottom tips", "Bottom")
    if info.get("Quick"):
        section("Quick tips", "Quick")

# -------------------------------------------------
# Location panel (key-prefixed so it can appear multiple times safely)
# -------------------------------------------------
def set_location(lat, lon, label):
    st.session_state["loc_lat"] = lat
    st.session_state["loc_lon"] = lon
    st.session_state["loc_label"] = label

def location_status():
    lat = st.session_state.get("loc_lat")
    lon = st.session_state.get("loc_lon")
    label = st.session_state.get("loc_label") or ""
    if lat is None or lon is None:
        return "No location set", None, None
    if label:
        return label, lat, lon
    return "Saved location", lat, lon

def location_panel(prefix):
    label, lat, lon = location_status()

    st.markdown(
        "<div class='card'><div class='card-title'>Location (shared)</div>"
        "<div class='small'>Current: <strong>" + label + "</strong></div>"
        "<div class='small muted' style='margin-top:6px;'>Set once here. Best Times and Wind will use it.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    place_key = prefix + "_place"
    matches_key = prefix + "_matches"

    place = st.text_input(
        "Search by place name or ZIP",
        value=st.session_state.get(place_key, ""),
        placeholder="Example: Hauser Lake, Idaho or 99201 or Spokane, WA",
        key=place_key,
    )

    c1, c2 = st.columns(2)
    with c1:
        do_search = st.button("Search", use_container_width=True, key=prefix + "_search")
    with c2:
        do_auto = st.button("Use my approximate location", use_container_width=True, key=prefix + "_auto")

    matches = st.session_state.get(matches_key, [])

    if do_search:
        matches = geocode(place, count=10) if norm(place) else []
        st.session_state[matches_key] = matches

    if matches:
        labels = [m["label"] for m in matches]
        choice = st.selectbox("Choose a match", labels, index=0, key=prefix + "_choice")
        chosen = None
        for m in matches:
            if m["label"] == choice:
                chosen = m
                break
        if chosen:
            if st.button("Save this location", use_container_width=True, key=prefix + "_save"):
                set_location(chosen["lat"], chosen["lon"], chosen["label"])
                st.success("Saved location: " + chosen["label"])

    if do_auto:
        lat2, lon2 = ip_location()
        if lat2 is None or lon2 is None:
            st.warning("Could not detect your location. Try searching by place name or ZIP.")
        else:
            set_location(lat2, lon2, "Approximate location")
            st.success("Saved approximate location.")

    c3, c4 = st.columns(2)
    with c3:
        if st.button("Clear location", use_container_width=True, key=prefix + "_clear"):
            set_location(None, None, "")
            st.session_state[matches_key] = []
            st.session_state[place_key] = ""
            st.success("Cleared.")
    with c4:
        st.write("")

# -------------------------------------------------
# Navigation
# -------------------------------------------------
PAGES = ["Home", "Best Times", "Wind", "Depth", "Species", "Speed"]

def go(page_name):
    st.session_state["page"] = page_name
    st.rerun()

# -------------------------------------------------
# Header
# -------------------------------------------------
st.markdown(
    "<div class='header'>"
    "<div class='logo'><img src='" + LOGO_URL + "'></div>"
    "<div class='version'>v" + APP_VERSION + "</div>"
    "</div>",
    unsafe_allow_html=True,
)

# Top nav (reliable)
current_page = st.session_state.get("page", "Home")
try:
    nav_index = PAGES.index(current_page)
except Exception:
    nav_index = 0

nav_choice = st.radio(
    "Navigation",
    PAGES,
    index=nav_index,
    horizontal=True,
    label_visibility="collapsed",
)

if nav_choice != current_page:
    st.session_state["page"] = nav_choice
    st.rerun()

page = st.session_state.get("page", "Home")

# -------------------------------------------------
# Pages
# -------------------------------------------------
if page == "Home":
    st.markdown("## Quick start")
    st.markdown("<div class='small'>Set your location once, then use Best Times or Wind.</div>", unsafe_allow_html=True)

    location_panel("home")

    st.markdown("## Tools")
    if st.button("Best Times", use_container_width=True, key="home_btn_best"):
        go("Best Times")
    if st.button("Wind", use_container_width=True, key="home_btn_wind"):
        go("Wind")
    if st.button("Depth", use_container_width=True, key="home_btn_depth"):
        go("Depth")
    if st.button("Species", use_container_width=True, key="home_btn_species"):
        go("Species")
    if st.button("Speed", use_container_width=True, key="home_btn_speed"):
        go("Speed")

    st.markdown(
        "<div class='card'><div class='card-title'>How this app works</div>"
        "<div class='small'><ul>"
        "<li><strong>Best Times</strong> uses sunrise and sunset to show bite windows.</li>"
        "<li><strong>Wind</strong> shows current and upcoming wind speeds.</li>"
        "<li><strong>Depth</strong> estimates trolling depth from speed, weight, and line.</li>"
        "<li><strong>Speed</strong> uses your phone GPS inside the page.</li>"
        "</ul></div></div>",
        unsafe_allow_html=True,
    )

elif page == "Best Times":
    st.markdown("## Best fishing times")
    st.markdown("<div class='small'>Morning and evening windows around sunrise and sunset.</div>", unsafe_allow_html=True)

    label, lat, lon = location_status()
    st.markdown(
        "<div class='card'><div class='card-title'>Using location</div>"
        "<div class='kpi' style='font-size:1.15rem;'>" + label + "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Change location", expanded=False):
        location_panel("bt")

    st.markdown("### Date range")
    c1, c2 = st.columns(2)
    with c1:
        start_day = st.date_input("Start date", value=date.today(), key="bt_start")
    with c2:
        end_day = st.date_input("End date", value=date.today(), key="bt_end")

    if end_day < start_day:
        st.warning("End date must be the same as or after start date.")
    elif lat is None or lon is None:
        st.info("Set a location first (Home) or use the Change location expander.")
    else:
        days = []
        cur = start_day
        while cur <= end_day and len(days) < 14:
            days.append(cur)
            cur += timedelta(days=1)

        if start_day != end_day and len(days) == 14 and end_day > days[-1]:
            st.info("Showing first 14 days only. Shorten the range to see more detail.")

        for d in days:
            w = bite_windows(lat, lon, d)
            st.markdown("### " + d.strftime("%A") + " - " + d.strftime("%b %d, %Y"))
            if not w:
                st.warning("Unable to calculate times for this day.")
                continue

            m0, m1 = w["morning"]
            e0, e1 = w["evening"]

            cA, cB = st.columns(2)
            with cA:
                st.markdown(
                    "<div class='card'><div class='card-title'>Morning window</div>"
                    "<div class='kpi'>" + m0.strftime("%I:%M %p").lstrip("0") + "</div>"
                    "<div class='kpi-sub'>to " + m1.strftime("%I:%M %p").lstrip("0") + "</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            with cB:
                st.markdown(
                    "<div class='card'><div class='card-title'>Evening window</div>"
                    "<div class='kpi'>" + e0.strftime("%I:%M %p").lstrip("0") + "</div>"
                    "<div class='kpi-sub'>to " + e1.strftime("%I:%M %p").lstrip("0") + "</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )

elif page == "Wind":
    st.markdown("## Wind")
    st.markdown("<div class='small'>Current wind plus the next few hours.</div>", unsafe_allow_html=True)

    label, lat, lon = location_status()
    st.markdown(
        "<div class='card'><div class='card-title'>Using location</div>"
        "<div class='kpi' style='font-size:1.15rem;'>" + label + "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Change location", expanded=False):
        location_panel("wind")

    if lat is None or lon is None:
        st.info("Set a location first (Home) or use the Change location expander.")
    else:
        by_time, cur_dt, cur_mph = winds(lat, lon)
        cur_list, fut_list = split_winds(by_time, cur_dt)

        if cur_mph is not None:
            st.markdown(
                "<div class='card'><div class='card-title'>Current wind</div>"
                "<div class='kpi'>" + str(cur_mph) + " mph</div>"
                "</div>",
                unsafe_allow_html=True,
            )

        if fut_list:
            st.markdown("### Next hours")
            for label2, mph in fut_list:
                st.markdown(
                    "<div class='card'><div class='card-title'>" + label2 + "</div>"
                    "<div class='kpi' style='font-size:1.4rem;'>" + str(mph) + " mph</div></div>",
                    unsafe_allow_html=True,
                )

elif page == "Depth":
    st.markdown("## Trolling depth")
    st.markdown("<div class='small'>Change any value and the estimate updates.</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        speed = st.number_input("Speed (mph)", 0.0, value=1.3, step=0.1, key="depth_speed")
    with c2:
        weight = st.number_input("Weight (oz)", 0.0, value=2.0, step=0.5, key="depth_weight")
    with c3:
        line_out = st.number_input("Line out (ft)", 0.0, value=100.0, step=5.0, key="depth_lineout")

    c4, c5 = st.columns(2)
    with c4:
        line_type = st.selectbox("Line type", ["Braid", "Fluorocarbon", "Monofilament"], index=0, key="depth_linetype")
    with c5:
        line_test = st.selectbox("Line test (lb)", [6, 8, 10, 12, 15, 20, 25, 30, 40, 50], index=3, key="depth_linetest")

    d = depth_est(speed, weight, line_out, line_type, line_test)
    if d is None:
        st.markdown("<div class='card'><div class='card-title'>Estimated depth</div><div class='kpi'>--</div></div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='card'><div class='card-title'>Estimated depth</div>"
            "<div class='kpi'>" + str(d) + " ft</div>"
            "<div class='small muted'>Heavier line runs shallower. Lure drag and current change results.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

elif page == "Species":
    st.markdown("## Species tips")
    st.markdown("<div class='small'>Pick a species for temps, baits, rigs, and depth-specific tips.</div>", unsafe_allow_html=True)

    db = species_db()
    names = sorted(list(db.keys()))
    default_species = "Largemouth bass"
    try:
        default_index = names.index(default_species)
    except Exception:
        default_index = 0

    species = st.selectbox("Species", names, index=default_index, key="species_pick")
    info = db.get(species)
    if info:
        render_species(species, info)

elif page == "Speed":
    st.markdown("## Speed")
    st.markdown("<div class='small'>Live GPS speed from your phone browser. Grant location permission.</div>", unsafe_allow_html=True)
    speedometer_widget()

# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown(
    "<div class='footer'><strong>FishyNW.com</strong><br>"
    "&copy; 2026 FishyNW. All rights reserved."
    "</div>",
    unsafe_allow_html=True,
)