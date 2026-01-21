# app.py
# FishyNW.com - Fishing Tools
# Version 1.9.5
# ASCII ONLY. No Unicode. No smart quotes. No special dashes.

from datetime import datetime, timedelta, date
import time
import requests
import streamlit as st
import streamlit.components.v1 as components

APP_VERSION = "1.9.5"

LOGO_URL = "https://fishynw.com/wp-content/uploads/2025/07/FishyNW-Logo-transparent-with-letters-e1755409608978.png"

HEADERS = {
    "User-Agent": "FishyNW-App-1.9.5",
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
# Pages
# -------------------------------------------------
PAGES = ["Home", "Best Times", "Wind", "Depth", "Species", "Speed"]
PAGE_KEYS = {
    "Home": "home",
    "Best Times": "best",
    "Wind": "wind",
    "Depth": "depth",
    "Species": "species",
    "Speed": "speed",
}
KEY_TO_PAGE = {v: k for k, v in PAGE_KEYS.items()}

def get_page_from_url():
    try:
        qp = st.query_params
        p = qp.get("page", "")
        if isinstance(p, list):
            p = p[0] if p else ""
        p = (p or "").strip().lower()
        return KEY_TO_PAGE.get(p, "Home")
    except Exception:
        return "Home"

def set_page_in_url(page_name):
    key = PAGE_KEYS.get(page_name, "home")
    st.query_params["page"] = key

# Session page default from URL (so bottom nav works)
if "page" not in st.session_state:
    st.session_state["page"] = get_page_from_url()
else:
    # If URL changes (clicked bottom nav), sync session
    url_page = get_page_from_url()
    if url_page != st.session_state["page"]:
        st.session_state["page"] = url_page

# -------------------------------------------------
# Location state
# -------------------------------------------------
if "loc_lat" not in st.session_state:
    st.session_state["loc_lat"] = None
if "loc_lon" not in st.session_state:
    st.session_state["loc_lon"] = None
if "loc_label" not in st.session_state:
    st.session_state["loc_label"] = "No location set"

if "do_set_location" not in st.session_state:
    st.session_state["do_set_location"] = False

if "loc_status_msg" not in st.session_state:
    st.session_state["loc_status_msg"] = ""

# -------------------------------------------------
# CSS (sticky top bar + floating bottom nav)
# -------------------------------------------------
st.markdown(
    """
<style>
/* Give the bottom nav room so content never hides behind it */
.block-container {
  max-width: 920px;
  padding-top: 0.75rem;
  padding-bottom: 6.25rem; /* space for bottom nav */
}

/* Sticky top bar */
.topbar {
  position: sticky;
  top: 0;
  z-index: 999;
  padding: 10px 10px 8px 10px;
  margin: -0.75rem -0.5rem 10px -0.5rem;
  border-bottom: 1px solid rgba(0,0,0,0.14);
  background: rgba(255,255,255,0.94);
  backdrop-filter: blur(8px);
}
@media (prefers-color-scheme: dark) {
  .topbar {
    background: rgba(15,15,15,0.88);
    border-bottom: 1px solid rgba(255,255,255,0.16);
  }
}

/* header */
.header {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap: 12px;
  margin-bottom: 6px;
}
.logo img {
  width: 100%;
  max-width: 250px;
  height: auto;
  display:block;
}
@media (max-width: 520px){
  .logo img { max-width: 68vw; }
}
.version {
  font-weight: 900;
  font-size: 0.95rem;
  opacity: 0.85;
  text-align:right;
  white-space: nowrap;
}

.small { opacity: 0.86; font-size: 0.95rem; }
.muted { opacity: 0.78; }

/* Cards */
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
.card-title { font-weight: 900; margin-bottom: 6px; }
.kpi { font-size: 1.7rem; font-weight: 950; line-height: 1.0; }
.kpi-sub { opacity: 0.86; margin-top: 6px; }

/* Buttons (Fishy light green) */
div.stButton > button, button[kind="primary"] {
  background-color: #8fd19e !important;
  color: #0b2e13 !important;
  border: 1px solid #6fbf87 !important;
  font-weight: 950 !important;
  border-radius: 12px !important;
  min-height: 48px !important;
}
div.stButton > button:hover, button[kind="primary"]:hover {
  background-color: #7cc78f !important;
  color: #08210f !important;
}

/* Floating bottom nav (custom HTML) */
.fishy-bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  padding: 10px 10px 12px 10px;
  background: rgba(255,255,255,0.92);
  border-top: 1px solid rgba(0,0,0,0.14);
  backdrop-filter: blur(8px);
}
@media (prefers-color-scheme: dark) {
  .fishy-bottom-nav {
    background: rgba(15,15,15,0.90);
    border-top: 1px solid rgba(255,255,255,0.16);
  }
}
.fishy-bottom-inner {
  max-width: 920px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 8px;
}
@media (max-width: 760px) {
  .fishy-bottom-inner {
    grid-template-columns: repeat(3, 1fr);
    grid-auto-rows: 44px;
  }
}
.navbtn {
  border-radius: 12px;
  padding: 10px 10px;
  font-weight: 900;
  border: 1px solid rgba(0,0,0,0.16);
  background: rgba(0,0,0,0.04);
  color: inherit;
  cursor: pointer;
  width: 100%;
  height: 44px;
}
@media (prefers-color-scheme: dark) {
  .navbtn { border: 1px solid rgba(255,255,255,0.14); background: rgba(255,255,255,0.06); }
}
.navbtn:active { transform: translateY(1px); }

/* Selected state */
.navbtn.sel {
  background: #8fd19e;
  border-color: #6fbf87;
  color: #0b2e13;
}

/* Small labels on tiny screens */
@media (max-width: 380px) {
  .navbtn { font-size: 0.86rem; padding: 8px; }
}
</style>
""",
    unsafe_allow_html=True,
)

# -------------------------------------------------
# Network helpers
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

# -------------------------------------------------
# Location (one-tap only)
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

def set_location(lat, lon, label):
    st.session_state["loc_lat"] = lat
    st.session_state["loc_lon"] = lon
    st.session_state["loc_label"] = label

def location_ready():
    return (st.session_state.get("loc_lat") is not None) and (st.session_state.get("loc_lon") is not None)

def location_label():
    return st.session_state.get("loc_label") or "No location set"

# -------------------------------------------------
# APIs
# -------------------------------------------------
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
        cur_mph = None
        try:
            cur_dt = datetime.fromisoformat(data.get("current", {}).get("time"))
        except Exception:
            cur_dt = None
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

def species_db():
    return {
        "Kokanee": {"temp_f": (42, 55), "Depths": ["Mid"], "Baits": ["Small hoochies", "Small spinners (wedding ring)"], "Rigs": ["Dodger + leader + hoochie/spinner"], "Quick": ["Small speed changes can turn on the bite."]},
        "Rainbow trout": {"temp_f": (45, 65), "Depths": ["Top", "Mid", "Bottom"], "Baits": ["Small spoons", "Inline spinners"], "Rigs": ["Cast and retrieve", "Trolling"], "Quick": ["Change lure color or tweak speed."]},
        "Lake trout": {"temp_f": (42, 55), "Depths": ["Mid", "Bottom"], "Baits": ["Tube jigs", "Large spoons"], "Rigs": ["Vertical jigging", "Deep trolling"], "Quick": ["Fish within a few feet of bottom."]},
        "Chinook salmon": {"temp_f": (44, 58), "Depths": ["Mid", "Bottom"], "Baits": ["Hoochies", "Spoons"], "Rigs": ["Flasher + leader"], "Quick": ["Repeat the depth and speed that got your bite."]},
        "Smallmouth bass": {"temp_f": (60, 75), "Depths": ["Top", "Mid", "Bottom"], "Baits": ["Ned rigs", "Tubes"], "Rigs": ["Ned rig", "Drop shot"], "Quick": ["Follow wind on points."]},
        "Largemouth bass": {"temp_f": (65, 80), "Depths": ["Top", "Mid", "Bottom"], "Baits": ["Frogs", "Texas rig plastics"], "Rigs": ["Texas rig"], "Quick": ["Shade is a magnet."]},
        "Walleye": {"temp_f": (55, 70), "Depths": ["Mid", "Bottom"], "Baits": ["Crankbaits", "Jigs"], "Rigs": ["Jig and soft plastic"], "Quick": ["Low light is best."]},
        "Perch": {"temp_f": (55, 75), "Depths": ["Mid", "Bottom"], "Baits": ["Small jigs"], "Rigs": ["Small jighead + bait"], "Quick": ["Hold position on schools."]},
        "Bluegill": {"temp_f": (65, 80), "Depths": ["Top", "Mid"], "Baits": ["Small jigs"], "Rigs": ["Float + small jig"], "Quick": ["Downsize for bites."]},
        "Channel catfish": {"temp_f": (65, 85), "Depths": ["Bottom"], "Baits": ["Cut bait", "Worms"], "Rigs": ["Slip sinker / Carolina"], "Quick": ["Evening and night are prime."]},
        "Trout (general)": {"temp_f": (45, 65), "Depths": ["Top", "Mid", "Bottom"], "Baits": ["Spoons", "Inline spinners"], "Rigs": ["Cast and retrieve", "Trolling"], "Quick": ["Cloud cover and chop can help."]},
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
        st.markdown("<div class='card'><div class='card-title'>Popular baits</div><ul>" + "".join(["<li>"+x+"</li>" for x in baits]) + "</ul></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='card'><div class='card-title'>Common rigs</div><ul>" + "".join(["<li>"+x+"</li>" for x in rigs]) + "</ul></div>", unsafe_allow_html=True)
    if info.get("Quick"):
        st.markdown("<div class='card'><div class='card-title'>Quick tips</div><ul>" + "".join(["<li>"+x+"</li>" for x in info.get("Quick", [])]) + "</ul></div>", unsafe_allow_html=True)

# -------------------------------------------------
# Sticky top bar
# -------------------------------------------------
st.markdown("<div class='topbar'>", unsafe_allow_html=True)

st.markdown(
    "<div class='header'>"
    "<div class='logo'><img src='" + LOGO_URL + "'></div>"
    "<div class='version'>v" + APP_VERSION + "</div>"
    "</div>",
    unsafe_allow_html=True,
)

top_cols = st.columns([1, 1])
with top_cols[0]:
    if st.button("Set Location", use_container_width=True, key="top_set_location"):
        st.session_state["do_set_location"] = True
        st.rerun()
with top_cols[1]:
    st.markdown(
        "<div class='small muted' style='text-align:right;'>Using: <strong>" +
        location_label() +
        "</strong></div>",
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------
# One-tap location action
# -------------------------------------------------
if st.session_state.get("do_set_location"):
    st.session_state["do_set_location"] = False
    with st.spinner("Setting location..."):
        lat2, lon2 = ip_location()
    if lat2 is None or lon2 is None:
        st.session_state["loc_status_msg"] = "Could not set location. Tap Set Location again."
    else:
        set_location(lat2, lon2, "Approximate location")
        st.session_state["loc_status_msg"] = "Location set."

msg = st.session_state.get("loc_status_msg", "")
if msg:
    if msg == "Location set.":
        st.success(msg)
    else:
        st.warning(msg)
    st.session_state["loc_status_msg"] = ""

# -------------------------------------------------
# Main pages
# -------------------------------------------------
page = st.session_state.get("page", "Home")
set_page_in_url(page)

if page == "Home":
    st.markdown("## Quick start")
    st.markdown("<div class='small'>Tap Set Location once, then use Best Times or Wind.</div>", unsafe_allow_html=True)

    if not location_ready():
        st.markdown(
            "<div class='card'><div class='card-title'>Step 1</div>"
            "<div class='small'>Tap <strong>Set Location</strong> at the top.</div>"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<div class='card'><div class='card-title'>Tools</div>"
        "<div class='small'>Use the bottom navigation to switch tools.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

elif page == "Best Times":
    st.markdown("## Best fishing times")
    st.markdown("<div class='small'>Morning and evening windows around sunrise and sunset.</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='card'><div class='card-title'>Using location</div>"
        "<div class='kpi' style='font-size:1.15rem;'>" + location_label() + "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("### Date range")
    c1, c2 = st.columns(2)
    with c1:
        start_day = st.date_input("Start date", value=date.today(), key="bt_start")
    with c2:
        end_day = st.date_input("End date", value=date.today(), key="bt_end")

    if end_day < start_day:
        st.warning("End date must be the same as or after start date.")
    elif not location_ready():
        st.info("Tap Set Location at the top first.")
    else:
        lat = st.session_state.get("loc_lat")
        lon = st.session_state.get("loc_lon")

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
                    "<div class='card'><div class='card-title'>Morning</div>"
                    "<div class='kpi'>" + m0.strftime("%I:%M %p").lstrip("0") + "</div>"
                    "<div class='kpi-sub'>to " + m1.strftime("%I:%M %p").lstrip("0") + "</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )
            with cB:
                st.markdown(
                    "<div class='card'><div class='card-title'>Evening</div>"
                    "<div class='kpi'>" + e0.strftime("%I:%M %p").lstrip("0") + "</div>"
                    "<div class='kpi-sub'>to " + e1.strftime("%I:%M %p").lstrip("0") + "</div>"
                    "</div>",
                    unsafe_allow_html=True,
                )

elif page == "Wind":
    st.markdown("## Wind")
    st.markdown("<div class='small'>Current wind plus the next few hours.</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='card'><div class='card-title'>Using location</div>"
        "<div class='kpi' style='font-size:1.15rem;'>" + location_label() + "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not location_ready():
        st.info("Tap Set Location at the top first.")
    else:
        lat = st.session_state.get("loc_lat")
        lon = st.session_state.get("loc_lon")

        by_time, cur_dt, cur_mph = winds(lat, lon)
        _, fut_list = split_winds(by_time, cur_dt)

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
    st.markdown("<div class='small'>Pick a species for temps, baits, rigs, and tips.</div>", unsafe_allow_html=True)

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

# -------------------------------------------------
# Floating bottom nav (real buttons, highlight selected)
# Uses URL query string (?page=wind) so it works reliably.
# -------------------------------------------------
def render_bottom_nav(selected_page):
    # Build buttons in HTML. Clicking changes URL query param; Streamlit reruns.
    btns = []
    for name in PAGES:
        key = PAGE_KEYS.get(name, "home")
        sel = " sel" if name == selected_page else ""
        btns.append(
            '<button class="navbtn' + sel + '" onclick="window.location.search=\'?page=' + key + '\'">' +
            name +
            '</button>'
        )

    html = (
        '<div class="fishy-bottom-nav">'
        '  <div class="fishy-bottom-inner">'
        + "".join(btns) +
        '  </div>'
        '</div>'
    )
    components.html(html, height=80)

render_bottom_nav(page)