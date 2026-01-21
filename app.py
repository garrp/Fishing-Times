# app.py
# FishyNW.com - Fishing Tools (Mobile)
# Version 2.0.3
# ASCII ONLY. No Unicode. No smart quotes. No special dashes.

from datetime import datetime, timedelta, date
import requests
import streamlit as st
import streamlit.components.v1 as components

APP_VERSION = "2.0.3"

LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-transparent-with-letters-e1755409608978.png"

HEADERS = {
    "User-Agent": "FishyNW-App-2.0.3",
    "Accept": "application/json",
}

# -------------------------------------------------
# Page config (NO SIDEBAR)
# -------------------------------------------------
st.set_page_config(
    page_title="FishyNW.com | Fishing Tools",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# -------------------------------------------------
# Session defaults
# -------------------------------------------------
if "tool" not in st.session_state:
    st.session_state["tool"] = "Times"

if "lat" not in st.session_state:
    st.session_state["lat"] = None
if "lon" not in st.session_state:
    st.session_state["lon"] = None

# Times tool state
if "times_place" not in st.session_state:
    st.session_state["times_place"] = ""
if "times_matches" not in st.session_state:
    st.session_state["times_matches"] = []
if "times_choice" not in st.session_state:
    st.session_state["times_choice"] = ""
if "times_display" not in st.session_state:
    st.session_state["times_display"] = ""

# Wind tool state
if "wind_place" not in st.session_state:
    st.session_state["wind_place"] = ""
if "wind_matches" not in st.session_state:
    st.session_state["wind_matches"] = []
if "wind_choice" not in st.session_state:
    st.session_state["wind_choice"] = ""
if "wind_display" not in st.session_state:
    st.session_state["wind_display"] = ""

# -------------------------------------------------
# Styles (hide sidebar + mobile app vibe)
# -------------------------------------------------
st.markdown(
    """
<style>
/* Always hide sidebar */
section[data-testid="stSidebar"],
aside[data-testid="stSidebar"],
div[data-testid="stSidebar"],
[data-testid="stSidebar"],
div[data-testid="collapsedControl"],
div[data-testid="stSidebarCollapsedControl"],
button[data-testid="collapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
.stSidebar {
  display: none !important;
  visibility: hidden !important;
  width: 0 !important;
  min-width: 0 !important;
  max-width: 0 !important;
}

/* Main layout */
.block-container {
  padding-top: 0.95rem;
  padding-bottom: 5.25rem; /* room for bottom nav */
  max-width: 760px;
}

/* Header */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 6px;
  margin-bottom: 10px;
}
.app-logo img {
  width: 100%;
  height: auto;
  max-width: 230px;
  display: block;
}
@media (max-width: 520px) {
  .app-logo img { max-width: 64vw; }
}
.app-meta {
  text-align: right;
  font-weight: 800;
  font-size: 1.05rem;
  line-height: 1.2rem;
}
.small { opacity: 0.85; font-size: 0.95rem; }

/* Cards */
.card {
  border-radius: 18px;
  padding: 16px;
  margin-top: 12px;
  border: 1px solid rgba(0,0,0,0.14);
  background: rgba(0,0,0,0.03);
}
.card-title { font-size: 0.98rem; opacity: 0.92; }
.card-value { font-size: 1.55rem; font-weight: 800; }
.compact-card { margin-top: 8px !important; padding: 14px 16px !important; }

/* Lists */
.tip-h { font-weight: 800; margin-top: 10px; }
.bul { margin-top: 8px; }
.bul li { margin-bottom: 6px; }

/* Default buttons: light green, high contrast */
button[kind="primary"],
div.stButton > button,
button {
  background-color: #8fd19e !important;
  color: #0b2e13 !important;
  border: 1px solid #6fbf87 !important;
  font-weight: 800 !important;
  border-radius: 12px !important;
  padding: 0.65rem 0.9rem !important;
}
div.stButton > button:hover,
button:hover {
  background-color: #7cc78f !important;
  color: #08210f !important;
}
div.stButton > button:disabled,
button:disabled {
  background-color: #cfe8d6 !important;
  color: #6b6b6b !important;
  border-color: #b6d6c1 !important;
}

/* Bottom nav bar (fixed) */
.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  background: rgba(255,255,255,0.96);
  border-top: 1px solid rgba(0,0,0,0.14);
  padding: 10px 10px;
}
@media (prefers-color-scheme: dark) {
  .bottom-nav { background: rgba(18,18,18,0.96); }
}
.nav-wrap { max-width: 760px; margin: 0 auto; }
.nav-hint {
  text-align: center;
  font-size: 0.9rem;
  opacity: 0.78;
  margin-top: 2px;
}

/* Make inputs feel bigger on mobile */
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {
  padding-top: 0.6rem !important;
  padding-bottom: 0.6rem !important;
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

def normalize_place_query(s):
    s = "" if s is None else str(s)
    s = " ".join(s.strip().split())
    return s

def inject_button_color_by_text(button_text, bg_hex, fg_hex, border_hex, delay_ms=50):
    # Styles a Streamlit button by exact visible text, using JS (reliable across Streamlit DOM variants).
    safe_text = button_text.replace("\\", "\\\\").replace('"', '\\"')
    components.html(
        """
<script>
(function() {
  var targetText = "%s";
  var delay = %d;
  var bg = "%s";
  var fg = "%s";
  var border = "%s";

  function styleBtn(btn) {
    try {
      btn.style.backgroundColor = bg;
      btn.style.color = fg;
      btn.style.border = "1px solid " + border;
      btn.style.fontWeight = "900";
      btn.style.borderRadius = "12px";
    } catch (e) {}
  }

  function findButton() {
    try {
      var buttons = Array.prototype.slice.call(document.querySelectorAll("button"));
      for (var i = 0; i < buttons.length; i++) {
        var b = buttons[i];
        var t = (b.innerText || "").trim();
        if (t === targetText) return b;
      }
    } catch (e) {}
    return null;
  }

  setTimeout(function() {
    var btn = findButton();
    if (btn) { styleBtn(btn); return; }

    var tries = 0;
    var iv = setInterval(function() {
      tries += 1;
      var b = findButton();
      if (b) {
        clearInterval(iv);
        styleBtn(b);
      }
      if (tries >= 20) clearInterval(iv);
    }, 200);
  }, delay);
})();
</script>
""" % (safe_text, int(delay_ms), bg_hex, fg_hex, border_hex),
        height=0,
    )

# -------------------------------------------------
# Location / Geocoding
# -------------------------------------------------
def get_location():
    # Best-effort IP geolocation (works without browser GPS permission)
    try:
        data = get_json("https://ipinfo.io/json", 6)
        loc = data.get("loc")
        if not loc:
            return None, None
        lat, lon = loc.split(",")
        return float(lat), float(lon)
    except Exception:
        return None, None

def geocode_search(place_name, count=10):
    try:
        q = normalize_place_query(place_name)
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

            display = ", ".join(parts)
            out.append({"label": display, "lat": float(lat), "lon": float(lon)})

        return out
    except Exception:
        return []

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

def best_times(lat, lon, day_obj):
    day_iso = day_obj.isoformat()
    sr, ss = get_sun_times(lat, lon, day_iso)
    if not sr or not ss:
        return None
    return {
        "morning": (sr - timedelta(hours=1), sr + timedelta(hours=1)),
        "evening": (ss - timedelta(hours=1), ss + timedelta(hours=1)),
    }

def get_wind_hours(lat, lon):
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
            out[t] = round(s, 1)
        return out
    except Exception:
        return {}

def split_current_future_winds(wind_by_time, now_local):
    current = []
    future = []
    keys = sorted(list(wind_by_time.keys()))
    for k in keys:
        try:
            dt = datetime.fromisoformat(k)
        except Exception:
            continue
        mph = wind_by_time.get(k)
        label = dt.strftime("%a %b %d, %I %p").replace(" 0", " ").replace(":00", "")
        if dt <= now_local:
            current.append((label, mph))
        else:
            future.append((label, mph))
    current = current[-6:]
    future = future[:12]
    return current, future

def trolling_depth(speed_mph, weight_oz, line_out_ft, line_type, line_test_lb):
    if speed_mph <= 0 or weight_oz <= 0 or line_out_ft <= 0 or line_test_lb <= 0:
        return None

    type_drag = {"Braid": 1.0, "Fluorocarbon": 1.12, "Monofilament": 1.2}[line_type]
    test_ratio = line_test_lb / 20.0
    test_drag = test_ratio ** 0.35
    total_drag = type_drag * test_drag

    depth = 0.135 * (weight_oz / (total_drag * (speed_mph ** 1.35))) * line_out_ft
    return round(depth, 1)

# -------------------------------------------------
# Species tips
# -------------------------------------------------
def species_tip_db():
    return {
        "Kokanee": {
            "temp_f": (42, 55),
            "Depths": ["Mid"],
            "Baits": ["Small hoochies", "Small spinners (wedding ring)", "Corn with scent (where used)"],
            "Rigs": ["Dodger + leader + hoochie/spinner", "Weights or downrigger to match marks"],
            "Mid": [
                "Troll dodger plus small hoochie or spinner behind it.",
                "Run scent and tune speed until you get a steady rod thump.",
                "If marks are mid column, match depth with weights or a downrigger.",
            ],
            "Quick": [
                "Speed is everything. Small changes can turn on the bite.",
                "If you see fish at 35 ft, set gear at about 30 to 33 ft.",
            ],
        },
        "Rainbow trout": {
            "temp_f": (45, 65),
            "Depths": ["Top", "Mid", "Bottom"],
            "Baits": ["Small spoons", "Inline spinners", "Floating minnows", "Worms (where legal)", "PowerBait (where legal)"],
            "Rigs": ["Cast and retrieve", "Trolling with long leads", "Slip sinker bait rig (near bottom)"],
            "Top": [
                "When they are up, cast small spinners, spoons, or floating minnows.",
                "Early morning wind lanes can be strong.",
            ],
            "Mid": [
                "Troll small spoons or spinners at 1.2 to 1.8 mph.",
                "Use longer leads if the water is clear.",
            ],
            "Bottom": [
                "Still fish bait just off bottom near structure or drop-offs.",
                "If snaggy, lift your bait slightly above bottom.",
            ],
            "Quick": [
                "If bites stop, change lure color or adjust speed slightly.",
                "Follow food and temperature changes.",
            ],
        },
        "Lake trout": {
            "temp_f": (42, 55),
            "Depths": ["Mid", "Bottom"],
            "Baits": ["Tube jigs", "Large spoons", "Blade baits", "Swimbaits (deep)"],
            "Rigs": ["Vertical jigging (heavy jig head + tube)", "Deep trolling with weights or downrigger"],
            "Mid": [
                "If bait is suspended, troll big spoons or tubes through the marks.",
                "Wide turns often trigger strikes.",
            ],
            "Bottom": [
                "Work structure: humps, points, deep breaks.",
                "Jig heavy tubes or blade baits on bottom, then lift and drop.",
            ],
            "Quick": [
                "Often tight to bottom. Fish within a few feet of it.",
                "When you find one, stay on that contour.",
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
                "Make long straight passes with gentle S turns.",
            ],
            "Bottom": [
                "If they are hugging bottom, run just above them to avoid snagging.",
                "Use your sonar to stay off bottom and repeat productive passes.",
            ],
            "Quick": [
                "Speed and depth control are the game.",
                "Repeat the depth and speed that got your bite.",
            ],
        },
        "Smallmouth bass": {
            "temp_f": (60, 75),
            "Depths": ["Top", "Mid", "Bottom"],
            "Baits": ["Walking baits", "Poppers", "Jerkbaits", "Swimbaits", "Ned rigs", "Tubes", "Drop shot plastics"],
            "Rigs": ["Ned rig", "Drop shot", "Tube jig"],
            "Top": [
                "Walking baits and poppers early and late.",
                "Wind on points can make topwater fire.",
            ],
            "Mid": [
                "Jerkbaits and swimbaits around rocks and shade.",
                "Slow down on cold fronts.",
            ],
            "Bottom": [
                "Ned rig, tube, drop shot on rock and breaks.",
                "If you feel rock and gravel, you are in the zone.",
            ],
            "Quick": [
                "Follow wind. It pushes bait and turns on feeding.",
                "After a miss, throw a Ned or drop shot back.",
            ],
        },
        "Largemouth bass": {
            "temp_f": (65, 80),
            "Depths": ["Top", "Mid", "Bottom"],
            "Baits": ["Frogs", "Buzzbaits", "Swim jigs", "Texas rig plastics", "Jigs"],
            "Rigs": ["Texas rig", "Swim jig", "Pitching jig"],
            "Top": [
                "Frog and buzzbait around weeds and shade lines.",
                "Target calm pockets in vegetation.",
            ],
            "Mid": [
                "Swim jig or paddletail along weed edges.",
                "Flip soft plastics into holes and let it fall.",
            ],
            "Bottom": [
                "Texas rig and jig in thick cover and along drop-offs.",
                "Slow down when pressured.",
            ],
            "Quick": [
                "Shade is a magnet: docks, reeds, mats.",
                "Dirty water: go louder and bigger.",
            ],
        },
        "Walleye": {
            "temp_f": (55, 70),
            "Depths": ["Mid", "Bottom"],
            "Baits": ["Crankbaits (trolling)", "Jigs with soft plastics", "Jigs with crawler (where used)", "Blade baits"],
            "Rigs": ["Jig and soft plastic", "Bottom bouncer + harness (where used)", "Trolling crankbaits on breaks"],
            "Mid": [
                "Troll crankbaits along breaks at dusk and dawn.",
                "If suspended, match that depth and keep moving.",
            ],
            "Bottom": [
                "Jig near bottom on transitions and edges.",
                "Slow roll a blade bait near bottom when fish are active.",
            ],
            "Quick": [
                "Low light is best: early, late, cloudy.",
                "Stay on transitions: flats to deep breaks.",
            ],
        },
        "Perch": {
            "temp_f": (55, 75),
            "Depths": ["Mid", "Bottom"],
            "Baits": ["Small jigs", "Worm pieces", "Minnow (where allowed)", "Tiny grubs"],
            "Rigs": ["Small jighead + bait", "Dropper loop with small hook (where used)"],
            "Mid": [
                "Small jigs tipped with bait, slowly swum through schools.",
                "If you find one, there are usually more.",
            ],
            "Bottom": [
                "Vertical jig small baits on bottom.",
                "Use light line and small hooks.",
            ],
            "Quick": [
                "Soft bottom near weeds can be good.",
                "When you mark a school, hold position and pick them off.",
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
                "Downsize until you get consistent bites.",
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
                "Reset to fresh bait if it goes quiet.",
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

def render_species_tips(name, db):
    info = db.get(name)
    if not info:
        st.warning("No tips found.")
        return

    lo, hi = info.get("temp_f", (None, None))
    depths = info.get("Depths", [])
    baits = info.get("Baits", [])
    rigs = info.get("Rigs", [])

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
            "</div>",
            unsafe_allow_html=True,
        )

    if baits:
        st.markdown(
            "<div class='card'>"
            "<div class='card-title'>Popular baits</div>"
            "<ul class='bul'>" + "".join(["<li>" + x + "</li>" for x in baits]) + "</ul>"
            "</div>",
            unsafe_allow_html=True,
        )

    if rigs:
        st.markdown(
            "<div class='card'>"
            "<div class='card-title'>Common rigs</div>"
            "<ul class='bul'>" + "".join(["<li>" + x + "</li>" for x in rigs]) + "</ul>"
            "</div>",
            unsafe_allow_html=True,
        )

    def section(title, key):
        items = info.get(key, [])
        if not items:
            return
        st.markdown("<div class='tip-h'>" + title + "</div>", unsafe_allow_html=True)
        st.markdown(
            "<ul class='bul'>" + "".join(["<li>" + x + "</li>" for x in items]) + "</ul>",
            unsafe_allow_html=True,
        )

    if "Top" in depths:
        section("Topwater", "Top")
    if "Mid" in depths:
        section("Mid water", "Mid")
    if "Bottom" in depths:
        section("Bottom", "Bottom")

    if info.get("Quick"):
        section("Quick tips", "Quick")

# -------------------------------------------------
# Speedometer widget (phone GPS)
# -------------------------------------------------
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

# -------------------------------------------------
# Navigation (BOTTOM ONLY)
# Hide the button for the current page.
# -------------------------------------------------
TOOL_LABELS = [("Times", "Times"), ("Wind", "Wind"), ("Depth", "Depth"), ("Tips", "Tips"), ("Speed", "Speed")]

def set_tool(name):
    st.session_state["tool"] = name

def render_header():
    title_map = {
        "Times": "Best Fishing Times",
        "Wind": "Wind Forecast",
        "Depth": "Trolling Depth",
        "Tips": "Species Tips",
        "Speed": "Speedometer",
    }
    t = title_map.get(st.session_state["tool"], "")
    st.markdown(
        "<div class='app-header'>"
        "<div class='app-logo'><img src='" + LOGO_URL + "'></div>"
        "<div class='app-meta'>" + t + "<div class='small'>v " + APP_VERSION + "</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

def render_bottom_nav(active_tool):
    st.markdown("<div class='bottom-nav'><div class='nav-wrap'>", unsafe_allow_html=True)

    cols = st.columns(5)
    for i, (label, name) in enumerate(TOOL_LABELS):
        with cols[i]:
            if name == active_tool:
                st.markdown(
                    "<div class='small' style='text-align:center; font-weight:900; opacity:0.85; padding-top:10px;'>"
                    + label + "</div>",
                    unsafe_allow_html=True,
                )
            else:
                if st.button(label, use_container_width=True, key="nav_" + label):
                    set_tool(name)
                    st.rerun()

    st.markdown("<div class='nav-hint'>Tap a tool. Current page is not a button.</div>", unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

# -------------------------------------------------
# App shell
# -------------------------------------------------
render_header()
st.markdown("<div class='small'>Enter a place name or ZIP, or leave blank to use your current location.</div>", unsafe_allow_html=True)
st.markdown("")

tool = st.session_state["tool"]

# Light red for the "action" buttons on their own pages
ACTION_BG = "#f4a3a3"
ACTION_FG = "#3b0a0a"
ACTION_BORDER = "#e48f8f"

# -------------------------------------------------
# TIMES
# -------------------------------------------------
if tool == "Times":
    st.markdown("### Location and dates")

    with st.form("times_form", clear_on_submit=False):
        place = st.text_input(
            "Place name (optional)",
            value=st.session_state.get("times_place", ""),
            placeholder="Example: Spokane, WA   or   99201   or   Hauser Lake, Idaho",
        )
        st.session_state["times_place"] = place

        d0, d1 = st.columns(2)
        with d0:
            start_day = st.date_input("Start date", value=date.today(), key="times_start")
        with d1:
            end_day = st.date_input("End date", value=date.today(), key="times_end")

        go = st.form_submit_button("Show Best Fishing Times", use_container_width=True)

    # Color that button light red (only on this page)
    inject_button_color_by_text("Show Best Fishing Times", ACTION_BG, ACTION_FG, ACTION_BORDER, 80)

    if go:
        q = normalize_place_query(place)

        if q:
            matches = geocode_search(q, count=10)
            st.session_state["times_matches"] = matches
            if matches:
                st.session_state["times_choice"] = matches[0]["label"]
                st.session_state["lat"], st.session_state["lon"] = matches[0]["lat"], matches[0]["lon"]
                st.session_state["times_display"] = matches[0]["label"]
            else:
                st.session_state["lat"], st.session_state["lon"] = None, None
                st.session_state["times_display"] = ""
        else:
            st.session_state["times_matches"] = []
            st.session_state["times_choice"] = ""
            st.session_state["lat"], st.session_state["lon"] = get_location()
            st.session_state["times_display"] = ""

    matches = st.session_state.get("times_matches") or []
    if matches:
        labels = [m["label"] for m in matches]
        chosen = st.selectbox("If needed, pick a different match", labels, index=0, key="times_match_pick")
        st.session_state["times_choice"] = chosen
        for m in matches:
            if m["label"] == chosen:
                st.session_state["lat"], st.session_state["lon"] = m["lat"], m["lon"]
                st.session_state["times_display"] = m["label"]
                break

    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")
    display_place = st.session_state.get("times_display", "")

    if display_place:
        st.markdown("<div class='small'><strong>Using:</strong> " + display_place + "</div>", unsafe_allow_html=True)

    if end_day < start_day:
        st.warning("End date must be the same as or after start date.")
    elif lat is None or lon is None:
        if normalize_place_query(st.session_state.get("times_place", "")):
            st.warning("Could not find that place. Try City, State or a ZIP code.")
        else:
            st.warning("Could not detect your location. Try entering a place name or ZIP code.")
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

# -------------------------------------------------
# WIND
# -------------------------------------------------
elif tool == "Wind":
    st.markdown("### Wind forecast")
    st.markdown("<div class='small'>Current and future hourly winds from your location or a place name.</div>", unsafe_allow_html=True)
    st.markdown("")

    with st.form("wind_form", clear_on_submit=False):
        place = st.text_input(
            "Place name (optional)",
            value=st.session_state.get("wind_place", ""),
            placeholder="Example: Los Angeles, CA   or   90001   or   Hayden Lake, Idaho",
        )
        st.session_state["wind_place"] = place
        go = st.form_submit_button("Show Winds", use_container_width=True)

    # Color that button light red (only on this page)
    inject_button_color_by_text("Show Winds", ACTION_BG, ACTION_FG, ACTION_BORDER, 80)

    if go:
        q = normalize_place_query(place)
        if q:
            matches = geocode_search(q, count=10)
            st.session_state["wind_matches"] = matches
            if matches:
                st.session_state["wind_choice"] = matches[0]["label"]
                st.session_state["lat"], st.session_state["lon"] = matches[0]["lat"], matches[0]["lon"]
                st.session_state["wind_display"] = matches[0]["label"]
            else:
                st.session_state["lat"], st.session_state["lon"] = None, None
                st.session_state["wind_display"] = ""
        else:
            st.session_state["wind_matches"] = []
            st.session_state["wind_choice"] = ""
            st.session_state["lat"], st.session_state["lon"] = get_location()
            st.session_state["wind_display"] = ""

    matches = st.session_state.get("wind_matches") or []
    if matches:
        labels = [m["label"] for m in matches]
        chosen = st.selectbox("If needed, pick a different match", labels, index=0, key="wind_match_pick")
        st.session_state["wind_choice"] = chosen
        for m in matches:
            if m["label"] == chosen:
                st.session_state["lat"], st.session_state["lon"] = m["lat"], m["lon"]
                st.session_state["wind_display"] = m["label"]
                break

    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")
    display_place = st.session_state.get("wind_display", "")

    if display_place:
        st.markdown("<div class='small'><strong>Using:</strong> " + display_place + "</div>", unsafe_allow_html=True)

    if lat is None or lon is None:
        if normalize_place_query(st.session_state.get("wind_place", "")):
            st.warning("Could not find that place. Try City, State or a ZIP code.")
        else:
            st.info("Tap Show Winds. If location fails, enter a place name or ZIP code.")
    else:
        wind = get_wind_hours(lat, lon)
        now_local = datetime.now()

        current, future = split_current_future_winds(wind, now_local)

        if current:
            st.markdown("#### Current winds")
            for label, mph in current:
                st.markdown(
                    "<div class='card compact-card'><div class='card-title'>" + label +
                    "</div><div class='card-value'>" + str(mph) + " mph</div></div>",
                    unsafe_allow_html=True,
                )

        if future:
            st.markdown("#### Future winds")
            for label, mph in future:
                st.markdown(
                    "<div class='card compact-card'><div class='card-title'>" + label +
                    "</div><div class='card-value'>" + str(mph) + " mph</div></div>",
                    unsafe_allow_html=True,
                )

# -------------------------------------------------
# DEPTH
# -------------------------------------------------
elif tool == "Depth":
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

# -------------------------------------------------
# TIPS
# -------------------------------------------------
elif tool == "Tips":
    st.markdown("### Species tips")
    st.markdown("<div class='small'>Pick a species and get tips plus its best activity temperature range, popular baits, and common rigs.</div>", unsafe_allow_html=True)

    db = species_tip_db()
    species_list = sorted(list(db.keys()))

    default_species = "Largemouth bass"
    try:
        default_index = species_list.index(default_species)
    except Exception:
        default_index = 0

    species = st.selectbox("Species", species_list, index=default_index)
    render_species_tips(species, db)

# -------------------------------------------------
# SPEED
# -------------------------------------------------
else:
    st.markdown("### Speedometer")
    st.markdown("<div class='small'>GPS speed from your phone browser. Works best once GPS has a lock and you are moving.</div>", unsafe_allow_html=True)
    phone_speedometer_widget()

# -------------------------------------------------
# Bottom navigation + footer
# -------------------------------------------------
render_bottom_nav(tool)

st.markdown(
    "<div style='text-align:center; margin-top:18px; opacity:0.88; font-size:0.95rem;'>"
    "<strong>FishyNW.com</strong><br>"
    "&copy; 2026 FishyNW. All rights reserved."
    "</div>",
    unsafe_allow_html=True,
)