# app.py
# FishyNW.com - Fishing Tools
# Version 1.7.8
# ASCII ONLY. No Unicode. No smart quotes. No special dashes.

from datetime import datetime, timedelta, date
import uuid
import requests
import streamlit as st
import streamlit.components.v1 as components

APP_VERSION = "1.7.8"

LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-transparent-with-letters-e1755409608978.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.7.8",
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
# Sidebar auto-hide (best effort)
# -------------------------------------------------
if "collapse_sidebar" not in st.session_state:
    st.session_state["collapse_sidebar"] = False

def request_sidebar_collapse():
    st.session_state["collapse_sidebar"] = True

def run_sidebar_collapse_if_needed():
    if not st.session_state.get("collapse_sidebar"):
        return

    components.html(
        """
<script>
(function() {
  function clickCollapse() {
    try {
      var btn =
        parent.document.querySelector('button[title="Collapse sidebar"]') ||
        parent.document.querySelector('button[aria-label="Collapse sidebar"]') ||
        parent.document.querySelector('[data-testid="stSidebarCollapseButton"] button') ||
        parent.document.querySelector('[data-testid="collapsedControl"] button');

      if (btn) { btn.click(); }
    } catch (e) {}
  }
  setTimeout(clickCollapse, 80);
})();
</script>
""",
        height=0,
    )
    st.session_state["collapse_sidebar"] = False

# -------------------------------------------------
# Styles (neutral + light green buttons with contrast)
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

/* Lists */
.tip-h { font-weight: 800; margin-top: 10px; }
.bul { margin-top: 8px; }
.bul li { margin-bottom: 6px; }

/* -------------------------------------------------
   Global button styling (light green, high contrast)
------------------------------------------------- */
button[kind="primary"],
button,
div.stButton > button {
  background-color: #8fd19e !important;
  color: #0b2e13 !important;
  border: 1px solid #6fbf87 !important;
  font-weight: 700 !important;
  border-radius: 10px !important;
}
button[kind="primary"]:hover,
button:hover,
div.stButton > button:hover {
  background-color: #7cc78f !important;
  color: #08210f !important;
}
button:active,
div.stButton > button:active {
  background-color: #6bbb83 !important;
  color: #04160a !important;
}
button:disabled,
div.stButton > button:disabled {
  background-color: #cfe8d6 !important;
  color: #6b6b6b !important;
  border-color: #b6d6c1 !important;
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

# -------------------------------------------------
# Analytics consent banner (session-only)
# -------------------------------------------------
def analytics_consent_required():
    return "analytics_consent" not in st.session_state

def analytics_allowed():
    return st.session_state.get("analytics_consent") == "accepted"

def render_analytics_consent_banner():
    st.markdown(
        """
<div class="card" style="margin-top:8px;">
  <div style="font-weight:800;font-size:1.05rem;margin-bottom:6px;">Analytics notice</div>
  <div style="opacity:0.88;">
    This app can send anonymous usage analytics to help improve the tools and performance.
    No personal information is collected.  I only goof with usage data.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Accept analytics", use_container_width=True, key="consent_accept"):
            st.session_state["analytics_consent"] = "accepted"
            st.rerun()
    with c2:
        if st.button("Decline analytics", use_container_width=True, key="consent_decline"):
            st.session_state["analytics_consent"] = "declined"
            st.rerun()

# -------------------------------------------------
# GA4 (server-side) analytics - Streamlit Community Cloud safe
# Uses GA4 Measurement Protocol
# -------------------------------------------------
def ga_get_client_id():
    if "ga_client_id" not in st.session_state:
        st.session_state["ga_client_id"] = str(uuid.uuid4())
    return st.session_state["ga_client_id"]

def ga_send_event(event_name, params=None, debug=False):
    try:
        enabled = bool(st.secrets.get("GA_ENABLED", True))
        if (not enabled) or (not analytics_allowed()):
            return

        mid = str(st.secrets.get("GA_MEASUREMENT_ID", "")).strip()
        secret = str(st.secrets.get("GA_API_SECRET", "")).strip()
        if not mid or not secret:
            return

        if params is None:
            params = {}

        payload = {
            "client_id": ga_get_client_id(),
            "events": [
                {
                    "name": str(event_name),
                    "params": params,
                }
            ],
        }

        base = "https://www.google-analytics.com"
        path = "/debug/mp/collect" if debug else "/mp/collect"
        url = base + path + "?measurement_id=" + mid + "&api_secret=" + secret

        requests.post(url, json=payload, timeout=3)
    except Exception:
        return

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

def inject_wiggle_button(button_text, delay_ms=5000):
    safe_text = button_text.replace("\\", "\\\\").replace('"', '\\"')
    components.html(
        """
<script>
(function() {
  var targetText = "%s";
  var delay = %d;

  function addWiggle(btn) {
    try {
      if (btn.getAttribute("data-wiggle") === "1") return;
      btn.setAttribute("data-wiggle", "1");

      var styleId = "wiggle-style";
      if (!document.getElementById(styleId)) {
        var st = document.createElement("style");
        st.id = styleId;
        st.textContent =
          "@keyframes wiggle{0%%{transform:rotate(0deg)}15%%{transform:rotate(-3deg)}30%%{transform:rotate(3deg)}45%%{transform:rotate(-2deg)}60%%{transform:rotate(2deg)}75%%{transform:rotate(-1deg)}100%%{transform:rotate(0deg)}}" +
          ".wiggle{animation:wiggle 0.55s ease-in-out 0s 3; transform-origin:center;}";
        document.head.appendChild(st);
      }

      btn.classList.remove("wiggle");
      void btn.offsetWidth;
      btn.classList.add("wiggle");
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
    if (btn) { addWiggle(btn); return; }

    var tries = 0;
    var iv = setInterval(function() {
      tries += 1;
      var b = findButton();
      if (b) {
        clearInterval(iv);
        addWiggle(b);
      }
      if (tries >= 20) clearInterval(iv);
    }, 250);
  }, delay);
})();
</script>
""" % (safe_text, int(delay_ms)),
        height=0,
    )

# -------------------------------------------------
# Species tips database (depth-aware) + baits + rigs
# Depths: allowed values among ["Top", "Mid", "Bottom"]
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
            "<div class='small' style='margin-top:10px;'>Use the menu to open a tool.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        "<div class='header-row'>"
        "<div class='header-logo'><img src='" + LOGO_URL + "'></div>"
        "<div class='header-title'>" + title + "</div>"
        "</div>",
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

# -------------------------------------------------
# Consent gate (must happen before analytics events)
# -------------------------------------------------
if analytics_consent_required():
    render_analytics_consent_banner()
    st.stop()

# -------------------------------------------------
# Analytics: app_open once per session (only after consent)
# -------------------------------------------------
if "ga_open_sent" not in st.session_state:
    st.session_state["ga_open_sent"] = True
    ga_send_event("app_open", {"app_version": APP_VERSION}, debug=False)

PAGE_TITLES = {
    "Home": "",
    "Best fishing times": "Best Fishing Times",
    "Wind forecast": "Wind Forecast",
    "Trolling depth calculator": "Trolling Depth Calculator",
    "Species tips": "Species Tips",
    "Speedometer": "Speedometer",
}

# -------------------------------------------------
# Sidebar navigation (with centered logo at top)
# -------------------------------------------------
with st.sidebar:
    st.markdown("<div class='sb-logo'><img src='" + LOGO_URL + "'></div>", unsafe_allow_html=True)
    st.caption("Version " + APP_VERSION)

    if st.button("Best fishing times", use_container_width=True, key="nav_best_times"):
        st.session_state["tool"] = "Best fishing times"
        st.session_state["lat"], st.session_state["lon"] = get_location()
        st.session_state["best_go"] = False
        request_sidebar_collapse()

    if st.button("Wind forecast", use_container_width=True, key="nav_wind"):
        st.session_state["tool"] = "Wind forecast"
        st.session_state["lat"], st.session_state["lon"] = get_location()
        request_sidebar_collapse()

    if st.button("Trolling depth calculator", use_container_width=True, key="nav_depth"):
        st.session_state["tool"] = "Trolling depth calculator"
        request_sidebar_collapse()

    if st.button("Species tips", use_container_width=True, key="nav_species"):
        st.session_state["tool"] = "Species tips"
        request_sidebar_collapse()

    if st.button("Speedometer", use_container_width=True, key="nav_speed"):
        st.session_state["tool"] = "Speedometer"
        request_sidebar_collapse()

# Run the collapse after the sidebar has rendered
run_sidebar_collapse_if_needed()

tool = st.session_state["tool"]

# -------------------------------------------------
# Analytics: tool_open when tool changes
# -------------------------------------------------
if "ga_last_tool" not in st.session_state:
    st.session_state["ga_last_tool"] = None

if tool != st.session_state["ga_last_tool"]:
    st.session_state["ga_last_tool"] = tool
    ga_send_event("tool_open", {"tool": tool, "app_version": APP_VERSION}, debug=False)

# -------------------------------------------------
# Home page
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

    # Numeric-only inputs + explicit checkbox so "optional" is real
    use_manual = st.checkbox("Use manual latitude and longitude", value=False, key="use_manual_best")

    c0, c1 = st.columns(2)
    with c0:
        lat_in = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=(float(lat) if lat is not None else 0.0),
            step=0.0001,
            format="%.6f",
            key="manual_lat_num",
        )
    with c1:
        lon_in = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=(float(lon) if lon is not None else 0.0),
            step=0.0001,
            format="%.6f",
            key="manual_lon_num",
        )

    st.markdown("<div class='small'>If manual is off, the app uses your current location.</div>", unsafe_allow_html=True)

    inject_wiggle_button("Display Best Fishing Times", 5000)

    if st.button("Display Best Fishing Times", use_container_width=True, key="go_best_times"):
        ga_send_event("action", {"name": "display_best_times", "tool": "Best fishing times"}, debug=False)
        st.session_state["best_go"] = True

        if use_manual:
            st.session_state["lat"], st.session_state["lon"] = float(lat_in), float(lon_in)
        else:
            st.session_state["lat"], st.session_state["lon"] = get_location()

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
            st.info("Turn on manual and enter lat/lon, or tap the button again to use current location.")
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

elif tool == "Wind forecast":
    st.markdown("### Wind forecast")
    st.markdown("<div class='small'>Current and future hourly winds from your location or manual lat/lon.</div>", unsafe_allow_html=True)

    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    st.markdown("### Location")

    use_manual = st.checkbox("Use manual latitude and longitude", value=False, key="use_manual_wind")

    c0, c1 = st.columns(2)
    with c0:
        lat_in = st.number_input(
            "Latitude",
            min_value=-90.0,
            max_value=90.0,
            value=(float(lat) if lat is not None else 0.0),
            step=0.0001,
            format="%.6f",
            key="wind_lat_num",
        )
    with c1:
        lon_in = st.number_input(
            "Longitude",
            min_value=-180.0,
            max_value=180.0,
            value=(float(lon) if lon is not None else 0.0),
            step=0.0001,
            format="%.6f",
            key="wind_lon_num",
        )

    st.markdown("<div class='small'>If manual is off, the app uses your current location.</div>", unsafe_allow_html=True)

    inject_wiggle_button("Display winds", 5000)

    if st.button("Display winds", use_container_width=True, key="go_winds"):
        ga_send_event("action", {"name": "display_winds", "tool": "Wind forecast"}, debug=False)
        if use_manual:
            st.session_state["lat"], st.session_state["lon"] = float(lat_in), float(lon_in)
        else:
            st.session_state["lat"], st.session_state["lon"] = get_location()

    lat = st.session_state.get("lat")
    lon = st.session_state.get("lon")

    if lat is None or lon is None:
        st.info("Tap Display winds. If manual is on, enter lat/lon first.")
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

elif tool == "Species tips":
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

else:
    st.markdown("### Speedometer")
    st.markdown("<div class='small'>GPS speed from your phone browser. Works best once GPS has a lock and you are moving.</div>", unsafe_allow_html=True)
    phone_speedometer_widget()

# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown(
    "<div class='footer'><strong>FishyNW.com</strong><br>"
    "&copy; 2026 FishyNW. All rights reserved."
    "</div>",
    unsafe_allow_html=True,
)