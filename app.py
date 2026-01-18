import math
from dataclasses import dataclass
from datetime import datetime, date, timedelta
import pytz
import requests
import streamlit as st
import streamlit.components.v1 as components
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

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
.block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1150px; }
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
.fishynw-footer{
  margin-top: 30px;
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
# States + normalization
# ----------------------------
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri",
    "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "DC": "District of Columbia",
}
STATE_NAME_TO_CODE = {v.upper(): k for k, v in US_STATES.items()}


def normalize_state(state_input: str) -> str | None:
    s = (state_input or "").strip().upper()
    if not s:
        return None
    if len(s) == 2 and s in US_STATES:
        return s
    if s in STATE_NAME_TO_CODE:
        return STATE_NAME_TO_CODE[s]
    return None


# ----------------------------
# Helpers
# ----------------------------
def clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))


def minutes_of_day(dt: datetime, tz: pytz.BaseTzInfo) -> int:
    local = dt.astimezone(tz)
    return local.hour * 60 + local.minute


def gaussian_peak(x: float, mu: float, sigma: float) -> float:
    """Unit gaussian peak."""
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)


def phase_label(phase: float) -> str:
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
    d_new = min(abs(phase - 0.0), abs(phase - 1.0))
    d_full = abs(phase - 0.5)
    d = min(d_new, d_full)  # 0..0.25-ish
    return 1.15 - (d / 0.25) * 0.20  # 1.15 down to 0.95


# ----------------------------
# Geocoding (Open-Meteo city-only query + filter)
# ----------------------------
def geocode_city_state(city: str, state_input: str) -> dict:
    state_code = normalize_state(state_input)
    if not state_code:
        raise ValueError("Enter a valid US state (example: ID, WA, OR) or full state name (Idaho).")
    if not city or not city.strip():
        raise ValueError("Enter a city name.")

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city.strip(), "count": 25, "language": "en", "format": "json"}
    r = requests.get(url, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()
    results = data.get("results") or []
    if not results:
        raise ValueError("No cities found with that name.")

    us_results = [x for x in results if (x.get("country_code") or "").upper() == "US"]
    if not us_results:
        raise ValueError("No US matches found for that city.")

    desired_state = US_STATES[state_code].upper()

    best = None
    for x in us_results:
        admin1 = (x.get("admin1") or "").upper()
        if admin1 == desired_state:
            best = x
            break
    if best is None:
        for x in us_results:
            admin1 = (x.get("admin1") or "").upper()
            if desired_state in admin1:
                best = x
                break
    if best is None:
        best = us_results[0]

    place = ", ".join([p for p in [best.get("name"), best.get("admin1"), best.get("country")] if p])
    return {"lat": float(best["latitude"]), "lon": float(best["longitude"]), "place": place}


# ----------------------------
# Astronomy
# ----------------------------
def get_sun_times(local_date: date, lat: float, lon: float, tz: pytz.BaseTzInfo) -> dict:
    loc = LocationInfo(name="Here", region="US", timezone=str(tz), latitude=lat, longitude=lon)
    s = sun(loc.observer, date=local_date, tzinfo=tz)
    return {"sunrise": s.get("sunrise"), "sunset": s.get("sunset")}


def get_moon_times_and_phase(local_date: date, lat: float, lon: float, tz: pytz.BaseTzInfo) -> dict:
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)

    local_midnight = tz.localize(datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0))
    obs.date = ephem.Date(local_midnight.astimezone(pytz.utc))
    moon = ephem.Moon()

    moonrise = None
    moonset = None
    try:
        mr = obs.next_rising(moon)
        moonrise = ephem.Date(mr).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except Exception:
        pass
    try:
        ms = obs.next_setting(moon)
        moonset = ephem.Date(ms).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except Exception:
        pass

    # Phase 0..1 using lunation fraction between previous & next new moon around local noon
    phase01 = 0.0
    illum_frac = None
    try:
        local_noon = tz.localize(datetime(local_date.year, local_date.month, local_date.day, 12, 0, 0))
        now_utc = ephem.Date(local_noon.astimezone(pytz.utc))
        prev_new = ephem.previous_new_moon(now_utc)
        next_new = ephem.next_new_moon(now_utc)
        phase01 = float((now_utc - prev_new) / (next_new - prev_new))
    except Exception:
        phase01 = 0.0

    try:
        obs2 = ephem.Observer()
        obs2.lat = str(lat)
        obs2.lon = str(lon)
        obs2.date = ephem.Date(
            tz.localize(datetime(local_date.year, local_date.month, local_date.day, 12, 0, 0)).astimezone(pytz.utc)
        )
        moon.compute(obs2)
        illum_frac = float(moon.phase) / 100.0
    except Exception:
        illum_frac = None

    return {"moonrise": moonrise, "moonset": moonset, "phase01": phase01, "illum_frac": illum_frac}


def find_moon_extrema(local_date: date, lat: float, lon: float, tz: pytz.BaseTzInfo) -> dict:
    obs = ephem.Observer()
    obs.lat = str(lat)
    obs.lon = str(lon)
    moon = ephem.Moon()

    local_start = tz.localize(datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0))
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
        alt = float(moon.alt)
        if alt > best_max_alt:
            best_max_alt = alt
            best_max_time = t
        if alt < best_min_alt:
            best_min_alt = alt
            best_min_time = t
        t += step

    return {"overhead": best_max_time, "underfoot": best_min_time}


# ----------------------------
# Browser location component (runs only when button pressed)
# ----------------------------
def geolocation_component(height: int = 0):
    html = """
    <script>
      const send = (lat, lon) => {
        const url = new URL(window.parent.location);
        url.searchParams.set("lat", lat);
        url.searchParams.set("lon", lon);
        url.searchParams.delete("geo_error");
        window.parent.history.replaceState({}, "", url.toString());
        window.parent.postMessage({type: "fishynw_geo", lat, lon}, "*");
      };

      const err = (msg) => {
        const url = new URL(window.parent.location);
        url.searchParams.set("geo_error", msg);
        window.parent.history.replaceState({}, "", url.toString());
        window.parent.postMessage({type: "fishynw_geo_error", msg}, "*");
      };

      if (!navigator.geolocation) {
        err("Geolocation not supported in this browser.");
      } else {
        navigator.geolocation.getCurrentPosition(
          (pos) => send(pos.coords.latitude, pos.coords.longitude),
          (e) => err(e.message || "Unable to get location."),
          { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
        );
      }
    </script>
    """
    components.html(html, height=height)


# ----------------------------
# Bite curve model
# ----------------------------
@dataclass
class Events:
    sunrise: datetime | None
    sunset: datetime | None
    moonrise: datetime | None
    moonset: datetime | None
    overhead: datetime | None
    underfoot: datetime | None
    phase01: float
    illum_frac: float | None


def build_bite_curve(local_date: date, tz: pytz.BaseTzInfo, events: Events):
    """
    Build a 0–100 bite index across the day using gaussian peaks around key events.
    """
    # centers in minutes since midnight
    centers = []
    weights = []

    def add_event(dt: datetime | None, w: float):
        if dt is None:
            return
        centers.append(minutes_of_day(dt, tz))
        weights.append(w)

    # Major centers (stronger, wider)
    add_event(events.overhead, 1.00)
    add_event(events.underfoot, 1.00)

    # Minor centers (medium)
    add_event(events.moonrise, 0.65)
    add_event(events.moonset, 0.65)

    # Sunrise/sunset bonus (medium)
    add_event(events.sunrise, 0.55)
    add_event(events.sunset, 0.55)

    # If nothing available, return flat-ish baseline
    if not centers:
        xs = []
        ys = []
        t0 = tz.localize(datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0))
        for m in range(0, 24 * 60):
            xs.append(t0 + timedelta(minutes=m))
            ys.append(30.0)
        return xs, ys

    # Shape controls
    sigma_major = 95.0   # minutes (wider)
    sigma_minor = 55.0   # minutes
    sigma_sun   = 50.0   # minutes

    # Determine which center came from what, to select sigma
    # We'll approximate by matching dt references:
    event_sigmas = {}
    if events.overhead:  event_sigmas[minutes_of_day(events.overhead, tz)] = sigma_major
    if events.underfoot: event_sigmas[minutes_of_day(events.underfoot, tz)] = sigma_major
    if events.moonrise:  event_sigmas[minutes_of_day(events.moonrise, tz)] = sigma_minor
    if events.moonset:   event_sigmas[minutes_of_day(events.moonset, tz)] = sigma_minor
    if events.sunrise:   event_sigmas[minutes_of_day(events.sunrise, tz)] = sigma_sun
    if events.sunset:    event_sigmas[minutes_of_day(events.sunset, tz)] = sigma_sun

    # Moon phase boost
    phase_mult = phase_boost(events.phase01)

    xs = []
    ys = []

    t0 = tz.localize(datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0))

    for m in range(0, 24 * 60):
        val = 22.0  # baseline

        for c, w in zip(centers, weights):
            sig = event_sigmas.get(c, 60.0)
            # Handle wraparound near midnight: choose the smaller circular distance
            d = min(abs(m - c), 1440 - abs(m - c))
            val += (w * 55.0) * gaussian_peak(d, 0.0, sig)

        val *= phase_mult
        val = clamp(val, 0, 100)

        xs.append(t0 + timedelta(minutes=m))
        ys.append(val)

    return xs, ys


def top_windows(xs, ys, tz: pytz.BaseTzInfo, k=3, min_separation_minutes=120):
    """
    Find top-k peak times with minimum separation.
    Returns list of (time, score).
    """
    peaks = []
    used = []

    # simple peak scan
    for i in range(1, len(ys) - 1):
        if ys[i] >= ys[i - 1] and ys[i] >= ys[i + 1]:
            peaks.append((ys[i], xs[i]))

    peaks.sort(reverse=True, key=lambda x: x[0])

    chosen = []
    for score, t in peaks:
        if len(chosen) >= k:
            break
        ok = True
        for _, ct in chosen:
            dt_min = abs((t - ct).total_seconds()) / 60.0
            if dt_min < min_separation_minutes:
                ok = False
                break
        if ok:
            chosen.append((t, float(score)))

    return chosen


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
        Bite index graph built from moon and sun events (solunar-style).
      </div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# Timezone (keep as your chosen default)
tz = pytz.timezone("America/Los_Angeles")

# Session state
if "lat" not in st.session_state:
    st.session_state.lat = None
if "lon" not in st.session_state:
    st.session_state.lon = None
if "place" not in st.session_state:
    st.session_state.place = None

# Query params for browser location
qp = st.query_params
q_lat = qp.get("lat", None)
q_lon = qp.get("lon", None)
geo_error = qp.get("geo_error", None)

if geo_error:
    st.error(f"Location error: {geo_error}")

if q_lat and q_lon:
    try:
        st.session_state.lat = float(q_lat)
        st.session_state.lon = float(q_lon)
        st.session_state.place = "Device location"
    except Exception:
        pass


# ----------------------------
# Controls
# ----------------------------
st.write("")
colA, colB = st.columns([1.2, 0.8], gap="large")

with colA:
    st.markdown('<div class="fishynw-card">', unsafe_allow_html=True)

    today = datetime.now(tz).date()
    chosen_date = st.date_input("Date", value=today)

    method = st.selectbox("Location method", ["Use device location", "City + State"])

    if method == "Use device location":
        if st.button("Get location", type="primary"):
            geolocation_component()
    else:
        c1, c2, c3 = st.columns([1.0, 0.55, 0.65])
        with c1:
            city = st.text_input("City", placeholder="Coeur d'Alene")
        with c2:
            state_input = st.text_input("State", placeholder="ID", max_chars=20)
        with c3:
            st.write("")
            st.write("")
            if st.button("Find", type="primary"):
                try:
                    loc = geocode_city_state(city.strip(), state_input.strip())
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

    run = st.button("Generate bite graph")

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
  <div style="font-size:16px; font-weight:700; margin-bottom:6px;">Graph meaning</div>
  <div class="muted" style="font-size:13px; line-height:1.55;">
    The line shows a bite index (0–100) across the day. Peaks are influenced by:
    <ul style="margin:8px 0 0; padding-left:18px;">
      <li>Moon overhead and underfoot</li>
      <li>Moonrise and moonset</li>
      <li>Sunrise and sunset</li>
      <li>Moon phase weighting</li>
    </ul>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ----------------------------
# Results: Graph
# ----------------------------
if run:
    if st.session_state.lat is None or st.session_state.lon is None:
        st.error("Set a location first.")
    else:
        lat = float(st.session_state.lat)
        lon = float(st.session_state.lon)

        try:
            sun_times = get_sun_times(chosen_date, lat, lon, tz)
            moon = get_moon_times_and_phase(chosen_date, lat, lon, tz)
            ex = find_moon_extrema(chosen_date, lat, lon, tz)

            ev = Events(
                sunrise=sun_times.get("sunrise"),
                sunset=sun_times.get("sunset"),
                moonrise=moon.get("moonrise"),
                moonset=moon.get("moonset"),
                overhead=ex.get("overhead"),
                underfoot=ex.get("underfoot"),
                phase01=float(moon.get("phase01") or 0.0),
                illum_frac=moon.get("illum_frac"),
            )

            xs, ys = build_bite_curve(chosen_date, tz, ev)

            # Plot
            fig, ax = plt.subplots(figsize=(10.5, 4.5))
            ax.plot(xs, ys, linewidth=2)

            ax.set_ylim(0, 100)
            ax.set_ylabel("Bite Index (0–100)")
            ax.set_title("Bite Index Across the Day")

            ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p"))
            ax.grid(True, alpha=0.25)

            # Shaded bands: Major ±120 mins, Minor ±60 mins
            def shade(dt: datetime | None, mins: int, alpha: float):
                if dt is None:
                    return
                start = dt - timedelta(minutes=mins)
                end = dt + timedelta(minutes=mins)
                ax.axvspan(start, end, alpha=alpha)

            # Major
            shade(ev.overhead, 120, 0.10)
            shade(ev.underfoot, 120, 0.10)
            # Minor
            shade(ev.moonrise, 60, 0.08)
            shade(ev.moonset, 60, 0.08)

            # Markers for key times
            def vline(dt: datetime | None, label: str):
                if dt is None:
                    return
                ax.axvline(dt, linestyle="--", alpha=0.35)
                ax.text(dt, 98, label, rotation=90, va="top", ha="right", fontsize=9, alpha=0.8)

            vline(ev.sunrise, "Sunrise")
            vline(ev.sunset, "Sunset")
            vline(ev.moonrise, "Moonrise")
            vline(ev.moonset, "Moonset")

            st.pyplot(fig, clear_figure=True)

            # Small summary (optional)
            peaks = top_windows(xs, ys, tz, k=3, min_separation_minutes=120)
            phase_name = phase_label(ev.phase01)
            illum_txt = "—" if ev.illum_frac is None else f"{int(round(ev.illum_frac*100))}%"

            st.markdown(
                f"""
<div class="fishynw-card">
  <div style="display:flex; gap:10px; flex-wrap:wrap;">
    <div class="pill">🌙 Moon: <b>{phase_name}</b></div>
    <div class="pill">Illumination: <b>{illum_txt}</b></div>
  </div>
</div>
""",
                unsafe_allow_html=True,
            )

            if peaks:
                st.markdown("**Top windows (peaks):**")
                for t, score in peaks:
                    st.write(f"- {t.strftime('%-I:%M %p')} — {int(round(score))}/100")

        except Exception as e:
            st.error(f"Graph error: {e}")


# ----------------------------
# FishyNW Footer
# ----------------------------
st.markdown(
    """
<div class="fishynw-footer muted">
  🎣 <b>FishyNW</b> •
  <a href="https://fishynw.com" target="_blank" rel="noopener">fishynw.com</a>
  <div style="margin-top:6px; font-size:12px;">
    Pacific Northwest Fishing • #adventure
  </div>
</div>
""",
    unsafe_allow_html=True,
)