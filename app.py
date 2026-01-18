import math
from datetime import datetime, date, timedelta
import pytz
import requests
import streamlit as st
import streamlit.components.v1 as components

# External libs (see requirements.txt below)
from astral import LocationInfo
from astral.sun import sun
import ephem


# ----------------------------
# Page setup
# ----------------------------
st.set_page_config(
    page_title="FishyNW Fishing Times",
    page_icon="🎣",
    layout="wide",
)

# ----------------------------
# Styling
# ----------------------------
st.markdown(
    """
<style>
/* overall */
.block-container { padding-top: 1.4rem; padding-bottom: 2.5rem; max-width: 1100px; }
.fishynw-card {
  border: 1px solid rgba(255,255,255,.10);
  border-radius: 18px;
  padding: 16px 16px 14px;
  background: rgba(17,26,46,.55);
}
.muted { color: rgba(235,240,255,.70); }
.pill {
  display:inline-flex; align-items:center; gap:8px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.12);
  background: rgba(10,16,30,.45);
  font-size: 12px;
}
.kpi {
  border: 1px solid rgba(255,255,255,.10);
  border-radius: 18px;
  padding: 12px;
  background: rgba(10,16,30,.35);
}
.time-item{
  border: 1px solid rgba(255,255,255,.10);
  border-radius: 18px;
  padding: 12px;
  background: rgba(10,16,30,.35);
  margin-bottom: 10px;
}
.badge{
  display:inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.12);
  background: rgba(255,255,255,.06);
  font-size: 12px;
}
.good { border-color: rgba(108,255,154,.35) !important; }
.okay { border-color: rgba(59,212,255,.35) !important; }
.warn { border-color: rgba(255,93,93,.35) !important; }

.fishynw-footer{
  margin-top: 32px;
  padding: 18px 12px 22px;
  border-top: 1px solid rgba(255,255,255,.10);
  text-align:center;
}
.fishynw-footer a{ text-decoration:none; }
</style>
""",
    unsafe_allow_html=True,
)


# ----------------------------
# Utils
# ----------------------------
def fmt_time(dt: datetime | None, tz: pytz.BaseTzInfo) -> str:
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    return dt.astimezone(tz).strftime("%-I:%M %p")


def window_text(center: datetime | None, minutes: int, tz: pytz.BaseTzInfo) -> str:
    if center is None:
        return "—"
    start = center - timedelta(minutes=minutes)
    end = center + timedelta(minutes=minutes)
    return f"{fmt_time(start, tz)} – {fmt_time(end, tz)}"


def clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


def phase_label(phase: float) -> str:
    # phase in [0..1): 0=new, 0.25=first quarter, 0.5=full, 0.75=last quarter
    def near(x, eps=0.03):
        return abs(phase - x) <= eps or abs((phase + 1) - x) <= eps

    if near(0.0) or near(1.0):
        return "New"
    if near(0.25):
        return "First Quarter"
    if near(0.5):
        return "Full"
    if near(0.75):
        return "Last Quarter"
    if phase < 0.25:
        return "Waxing Crescent"
    if phase < 0.5:
        return "Waxing Gibbous"
    if phase < 0.75:
        return "Waning Gibbous"
    return "Waning Crescent"


def phase_boost(phase: float) -> float:
    # Favor new/full slightly
    d_new = min(abs(phase - 0.0), abs(phase - 1.0))
    d_full = abs(phase - 0.5)
    d = min(d_new, d_full)  # 0..0.25-ish
    return 1.15 - (d / 0.25) * 0.20  # 1.15 down to 0.95


def bucket(score: int) -> tuple[str, str]:
    if score >= 82:
        return ("Hot", "good")
    if score >= 68:
        return ("Good", "okay")
    return ("Tough", "warn")


def score_from_inputs(phase: float, has_moonrise_set: bool) -> int:
    base = 70.0
    base *= phase_boost(phase)
    if not has_moonrise_set:
        base *= 0.95
    return int(round(clamp(base, 0, 100)))


# ----------------------------
# Geocoding (City/State) via Open-Meteo
# ----------------------------
def geocode_city_state(city: str, state_code: str) -> dict:
    q = f"{city}, {state_code}, USA"
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": q, "count": 5, "language": "en", "format": "json"}
    r = requests.get(url, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        raise ValueError("No matches found for that City/State.")

    # Prefer US results if present
    best = results[0]
    for item in results:
        if (item.get("country_code") or "").upper() == "US":
            best = item
            break

    place = ", ".join([p for p in [best.get("name"), best.get("admin1"), best.get("country")] if p])
    return {"lat": float(best["latitude"]), "lon": float(best["longitude"]), "place": place}


# ----------------------------
# Sun + Moon calculations
# ----------------------------
def get_sun_times(local_date: date, lat: float, lon: float, tz: pytz.BaseTzInfo) -> dict:
    loc = LocationInfo(name="Here", region="US", timezone=str(tz), latitude=lat, longitude=lon)
    s = sun(loc.observer, date=local_date, tzinfo=tz)
    return {"sunrise": s.get("sunrise"), "sunset": s.get("sunset")}


def get_moon_times(local_date: date, lat: float, lon: float, tz: pytz.BaseTzInfo) -> dict:
    """
    Moonrise/moonset via PyEphem. Times returned in local timezone when possible.
    """
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    # Set observer date to local midnight converted to UTC because PyEphem expects UTC-ish
    local_midnight = tz.localize(datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0))
    obs.date = ephem.Date(local_midnight.astimezone(pytz.utc))

    moon = ephem.Moon()

    moonrise = None
    moonset = None
    try:
        mr = obs.next_rising(moon)
        moonrise = ephem.Date(mr).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except Exception:
        moonrise = None

    try:
        ms = obs.next_setting(moon)
        moonset = ephem.Date(ms).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except Exception:
        moonset = None

    # Moon phase (0..1) from ephem: moon.phase is illumination percentage (0..100)
    # For a proper 0..1 phase (new->full->new), we estimate using ephem.Moon().phase + elongation sign.
    # We'll produce:
    # - illumination fraction (0..1) from moon.phase
    # - "phase" 0..1 using moon.elong and moon.earth_distance? Not ideal.
    # We'll instead compute phase based on days since known new moon using ephem.next_new_moon.
    # That yields a stable 0..1 mapping.
    try:
        # Use the local date noon to avoid DST boundary weirdness
        local_noon = tz.localize(datetime(local_date.year, local_date.month, local_date.day, 12, 0, 0))
        now_utc = ephem.Date(local_noon.astimezone(pytz.utc))
        prev_new = ephem.previous_new_moon(now_utc)
        next_new = ephem.next_new_moon(now_utc)
        lunation = (now_utc - prev_new) / (next_new - prev_new)  # 0..1
        phase01 = float(lunation)
    except Exception:
        phase01 = 0.0

    # illumination fraction at local noon
    try:
        obs2 = ephem.Observer()
        obs2.lat = str(lat)
        obs2.lon = str(lon)
        obs2.date = ephem.Date(tz.localize(datetime(local_date.year, local_date.month, local_date.day, 12, 0, 0)).astimezone(pytz.utc))
        moon.compute(obs2)
        illum_frac = float(moon.phase) / 100.0
    except Exception:
        illum_frac = None

    return {"moonrise": moonrise, "moonset": moonset, "phase01": phase01, "illum_frac": illum_frac}


def find_moon_extrema(local_date: date, lat: float, lon: float, tz: pytz.BaseTzInfo) -> dict:
    """
    Approx moon overhead/underfoot by sampling moon altitude across the day (every 5 minutes).
    """
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    moon = ephem.Moon()

    local_start = tz.localize(datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0))
    # sample every 5 minutes
    step = timedelta(minutes=5)
    samples = int((24 * 60) / 5)

    best_max_alt = -1e9
    best_min_alt = 1e9
    best_max_time = None
    best_min_time = None

    t = local_start
    for _ in range(samples + 1):
        obs.date = ephem.Date(t.astimezone(pytz.utc))
        moon.compute(obs)
        alt = float(moon.alt)  # radians
        if alt > best_max_alt:
            best_max_alt = alt
            best_max_time = t
        if alt < best_min_alt:
            best_min_alt = alt
            best_min_time = t
        t += step

    return {"overhead": best_max_time, "underfoot": best_min_time}


# ----------------------------
# GPS geolocation (browser -> Streamlit)
# ----------------------------
def geolocation_component(height: int = 0):
    """
    Uses browser geolocation and posts coords back to Streamlit via query params.
    """
    html = f"""
    <script>
      const send = (lat, lon) => {{
        const url = new URL(window.parent.location);
        url.searchParams.set("lat", lat);
        url.searchParams.set("lon", lon);
        window.parent.history.replaceState({{}}, "", url.toString());
        window.parent.postMessage({{type: "fishynw_geo", lat, lon}}, "*");
      }};

      const err = (msg) => {{
        const url = new URL(window.parent.location);
        url.searchParams.set("geo_error", msg);
        window.parent.history.replaceState({{}}, "", url.toString());
        window.parent.postMessage({{type: "fishynw_geo_error", msg}}, "*");
      }};

      if (!navigator.geolocation) {{
        err("Geolocation not supported in this browser.");
      }} else {{
        navigator.geolocation.getCurrentPosition(
          (pos) => send(pos.coords.latitude, pos.coords.longitude),
          (e) => err(e.message || "Unable to get location."),
          {{ enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }}
        );
      }}
    </script>
    """
    components.html(html, height=height)


# ----------------------------
# Header
# ----------------------------
st.markdown(
    """
<div class="fishynw-card">
  <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
    <div style="font-size:28px;">🎣</div>
    <div>
      <div style="font-size:20px; font-weight:700;">FishyNW Fishing Times</div>
      <div class="muted" style="font-size:13px;">
        Solunar-style bite windows using moon overhead/underfoot + moonrise/set. GPS optional.
      </div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.write("")

# Default timezone (you said America/Los_Angeles)
tz = pytz.timezone("America/Los_Angeles")

# ----------------------------
# Controls
# ----------------------------
colA, colB = st.columns([1.2, 0.8], gap="large")

with colA:
    st.markdown('<div class="fishynw-card">', unsafe_allow_html=True)

    today = datetime.now(tz).date()
    chosen_date = st.date_input("Date", value=today)

    method = st.selectbox("Location method", ["Use device GPS (optional)", "City + State (no GPS)"])

    # Pull coords from URL query params if present
    qp = st.query_params
    q_lat = qp.get("lat", None)
    q_lon = qp.get("lon", None)
    geo_error = qp.get("geo_error", None)

    if "lat" not in st.session_state:
        st.session_state.lat = None
    if "lon" not in st.session_state:
        st.session_state.lon = None
    if "place" not in st.session_state:
        st.session_state.place = None

    if geo_error:
        st.error(f"GPS error: {geo_error}")

    if q_lat and q_lon:
        try:
            st.session_state.lat = float(q_lat)
            st.session_state.lon = float(q_lon)
            st.session_state.place = "Device location"
        except Exception:
            pass

    if method == "Use device GPS (optional)":
        if st.button("Use my location", type="primary"):
            # run browser geolocation script
            geolocation_component()

        st.caption("If you deny GPS, use City + State instead.")

    else:
        c1, c2, c3 = st.columns([1.0, 0.5, 0.6])
        with c1:
            city = st.text_input("City", placeholder="Coeur d'Alene")
        with c2:
            state_code = st.text_input("State", placeholder="ID", max_chars=2)
        with c3:
            st.write("")
            st.write("")
            if st.button("Find", type="primary"):
                try:
                    loc = geocode_city_state(city.strip(), state_code.strip().upper())
                    st.session_state.lat = loc["lat"]
                    st.session_state.lon = loc["lon"]
                    st.session_state.place = loc["place"]
                    st.success(f"Found: {loc['place']}")
                except Exception as e:
                    st.error(str(e))

    # Location pill
    loc_text = "Not set"
    if st.session_state.lat is not None and st.session_state.lon is not None:
        place = st.session_state.place or "Location"
        loc_text = f"{place} ({st.session_state.lat:.4f}, {st.session_state.lon:.4f})"

    st.markdown(
        f"""
<div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:6px;">
  <div class="pill">📍 Location: <b>{loc_text}</b></div>
  <div class="pill">🕒 Timezone: <b>{tz.zone}</b></div>
</div>
""",
        unsafe_allow_html=True,
    )

    run = st.button("Calculate fishing times")

    if st.button("Clear location", type="secondary"):
        st.session_state.lat = None
        st.session_state.lon = None
        st.session_state.place = None
        st.query_params.clear()
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

with colB:
    st.markdown(
        """
<div class="fishynw-card">
  <div style="font-size:16px; font-weight:700; margin-bottom:6px;">How it works</div>
  <div class="muted" style="font-size:13px; line-height:1.55;">
    <ul style="margin:0; padding-left:18px;">
      <li><b>Major</b> periods: moon overhead + underfoot (peak/min altitude, sampled)</li>
      <li><b>Minor</b> periods: moonrise + moonset</li>
      <li><b>Bonus</b> windows: sunrise + sunset</li>
      <li><b>Score</b>: moon-phase weighted (new/full slightly favored)</li>
    </ul>
    <div style="margin-top:10px;">
      This is a practical estimator. Weather, season, water temp, pressure, and species matter.
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

# ----------------------------
# Results
# ----------------------------
if run:
    if st.session_state.lat is None or st.session_state.lon is None:
        st.error("Set a location first (GPS or City/State).")
    else:
        lat = float(st.session_state.lat)
        lon = float(st.session_state.lon)

        try:
            sun_times = get_sun_times(chosen_date, lat, lon, tz)
            moon_times = get_moon_times(chosen_date, lat, lon, tz)
            extrema = find_moon_extrema(chosen_date, lat, lon, tz)

            sunrise = sun_times.get("sunrise")
            sunset = sun_times.get("sunset")

            moonrise = moon_times.get("moonrise")
            moonset = moon_times.get("moonset")

            phase01 = float(moon_times.get("phase01") or 0.0)
            illum_frac = moon_times.get("illum_frac")

            has_moonrise_set = bool(moonrise or moonset)
            score = score_from_inputs(phase01, has_moonrise_set)
            label, cls = bucket(score)

            # KPIs
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(
                    f"""
<div class="kpi {cls}">
  <div class="muted">Overall bite score</div>
  <div style="font-size:26px; font-weight:800;">{score}/100</div>
  <div class="muted" style="font-size:12px;">{label} conditions (moon-weighted)</div>
</div>
""",
                    unsafe_allow_html=True,
                )

            with c2:
                illum_text = "Illumination: —"
                if illum_frac is not None:
                    illum_text = f"Illumination: {int(round(illum_frac * 100))}%"
                st.markdown(
                    f"""
<div class="kpi">
  <div class="muted">Moon phase</div>
  <div style="font-size:22px; font-weight:800;">{phase_label(phase01)}</div>
  <div class="muted" style="font-size:12px;">{illum_text}</div>
</div>
""",
                    unsafe_allow_html=True,
                )

            with c3:
                st.markdown(
                    f"""
<div class="kpi">
  <div class="muted">Sun & Moon</div>
  <div style="font-size:14px; font-weight:700;">🌅 {fmt_time(sunrise, tz)} • 🌇 {fmt_time(sunset, tz)}</div>
  <div class="muted" style="font-size:12px;">
    🌙 Rise: {fmt_time(moonrise, tz)} • Set: {fmt_time(moonset, tz)}
  </div>
</div>
""",
                    unsafe_allow_html=True,
                )

            st.write("")
            st.subheader("Best fishing windows")

            def time_item(title: str, center: datetime | None, mins: int, tag: str, cls2: str):
                st.markdown(
                    f"""
<div class="time-item {cls2}">
  <div style="display:flex; justify-content:space-between; gap:10px; align-items:baseline;">
    <div style="font-size:14px; font-weight:800;">{title}</div>
    <span class="badge">{tag}</span>
  </div>
  <div style="font-size:18px; font-weight:800; margin-top:4px;">
    {window_text(center, mins, tz)}
  </div>
  <div class="muted" style="font-size:12px;">Center: {fmt_time(center, tz)} • Window: ±{mins} min</div>
</div>
""",
                    unsafe_allow_html=True,
                )

            # Major windows ±120
            time_item("Major Period (Moon Overhead)", extrema.get("overhead"), 120, "Major", cls)
            time_item("Major Period (Moon Underfoot)", extrema.get("underfoot"), 120, "Major", cls)

            # Minor windows ±60
            if moonrise:
                time_item("Minor Period (Moonrise)", moonrise, 60, "Minor", "okay")
            if moonset:
                time_item("Minor Period (Moonset)", moonset, 60, "Minor", "okay")

            if not moonrise and not moonset:
                st.warning(
                    "Minor periods unavailable for this date/location (moonrise/set can be undefined at some latitudes/seasons). Major periods still work."
                )

            # Bonus sunrise/sunset ±60
            if sunrise:
                time_item("Bonus: Sunrise Window", sunrise, 60, "Sun", "okay")
            if sunset:
                time_item("Bonus: Sunset Window", sunset, 60, "Sun", "okay")

            st.caption("Tip: Treat these as planning windows. Confirm with wind, pressure, and water temp for your target species.")

        except Exception as e:
            st.error(f"Calculation error: {e}")

# ----------------------------
# FishyNW Footer
# ----------------------------
st.markdown(
    """
<div class="fishynw-footer muted">
  🎣 <b>FishyNW</b> •
  <a href="https://fishynw.com" target="_blank" rel="noopener">fishynw.com</a>
  <div style="margin-top:6px; font-size:12px;">
    Pacific Northwest Fishing • GPS optional • #adventure
  </div>
</div>
""",
    unsafe_allow_html=True,
)