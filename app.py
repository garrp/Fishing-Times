import math
from datetime import datetime, date, timedelta
import pytz
import requests
import streamlit as st
import streamlit.components.v1 as components
import plotly.graph_objects as go

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
.block-container { max-width: 1050px; padding-top: 1.2rem; padding-bottom: 2.0rem; }
.fishynw-card {
  background: rgba(17,26,46,.55);
  border-radius: 18px;
  padding: 16px;
  border: 1px solid rgba(255,255,255,.10);
}
.muted { color: rgba(235,240,255,.70); }
.small { font-size:12px; }
.footer { margin-top: 26px; text-align:center; font-size:12px; color:#9fb2d9; }
.footer a { color:#6fd3ff; text-decoration:none; }
</style>
""",
    unsafe_allow_html=True,
)

# ----------------------------
# Helpers
# ----------------------------
def clamp(x: float, a: float, b: float) -> float:
    return max(a, min(b, x))

def gaussian(x: float, mu: float, sigma: float) -> float:
    return math.exp(-0.5 * ((x - mu) / sigma) ** 2)

def minutes_since_midnight(dt: datetime, tz: pytz.BaseTzInfo) -> int:
    local = dt.astimezone(tz)
    return local.hour * 60 + local.minute

def to_datetime_local_naive(d: date, minute: int) -> datetime:
    # Plotly is happy with naive local datetimes
    return datetime(d.year, d.month, d.day, minute // 60, minute % 60)

def deg_to_compass(deg: float) -> str:
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    ix = int((deg / 22.5) + 0.5) % 16
    return dirs[ix]

# ----------------------------
# Browser location component
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
      };

      const err = (msg) => {
        const url = new URL(window.parent.location);
        url.searchParams.set("geo_error", msg);
        window.parent.history.replaceState({}, "", url.toString());
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
# Geocoding (Open-Meteo)
# ----------------------------
def geocode_city_state(city: str, state: str):
    if not city.strip() or not state.strip():
        raise ValueError("Enter City and State.")

    url = "https://geocoding-api.open-meteo.com/v1/search"
    r = requests.get(
        url,
        params={"name": city.strip(), "count": 25, "language": "en", "format": "json"},
        timeout=12,
    )
    r.raise_for_status()
    results = r.json().get("results") or []
    if not results:
        raise ValueError("City not found.")

    state_u = state.strip().upper()
    us = [x for x in results if (x.get("country_code") or "").upper() == "US"]
    if not us:
        raise ValueError("No US matches found.")

    # Prefer state match
    for x in us:
        admin1 = (x.get("admin1") or "").upper()
        if state_u in admin1:
            return float(x["latitude"]), float(x["longitude"]), f"{x['name']}, {x.get('admin1','')}"
    x = us[0]
    return float(x["latitude"]), float(x["longitude"]), f"{x['name']}, {x.get('admin1','')}"

# ----------------------------
# Sun/Moon events
# ----------------------------
def get_events(day: date, lat: float, lon: float, tz: pytz.BaseTzInfo):
    loc = LocationInfo("", "", tz.zone, lat, lon)
    s = sun(loc.observer, date=day, tzinfo=tz)

    obs = ephem.Observer()
    obs.lat, obs.lon = str(lat), str(lon)

    local_midnight = tz.localize(datetime(day.year, day.month, day.day, 0, 0, 0))
    obs.date = local_midnight.astimezone(pytz.utc)

    moon = ephem.Moon()
    moonrise = moonset = None
    try:
        moonrise = ephem.Date(obs.next_rising(moon)).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except:
        pass
    try:
        moonset = ephem.Date(obs.next_setting(moon)).datetime().replace(tzinfo=pytz.utc).astimezone(tz)
    except:
        pass

    # overhead/underfoot by sampling every 5 minutes
    best_hi_alt = -999.0
    best_lo_alt = 999.0
    best_hi_time = None
    best_lo_time = None

    t = tz.localize(datetime(day.year, day.month, day.day, 0, 0, 0))
    for _ in range(288):  # 24h * 60 / 5
        obs.date = t.astimezone(pytz.utc)
        moon.compute(obs)
        alt = float(moon.alt)
        if alt > best_hi_alt:
            best_hi_alt = alt
            best_hi_time = t
        if alt < best_lo_alt:
            best_lo_alt = alt
            best_lo_time = t
        t += timedelta(minutes=5)

    return {
        "sunrise": s.get("sunrise"),
        "sunset": s.get("sunset"),
        "moonrise": moonrise,
        "moonset": moonset,
        "overhead": best_hi_time,
        "underfoot": best_lo_time,
    }

# ----------------------------
# Wind (Open-Meteo Forecast API)
# ----------------------------
def fetch_wind_for_day(day: date, lat: float, lon: float, tz_name: str):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "timezone": tz_name,
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
        "wind_speed_unit": "mph",
    }
    r = requests.get(url, params=params, timeout=12)
    r.raise_for_status()
    data = r.json()

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    ws = hourly.get("wind_speed_10m") or []
    wd = hourly.get("wind_direction_10m") or []
    wg = hourly.get("wind_gusts_10m") or []

    out = {}
    for t_str, s_mph, d_deg, g_mph in zip(times, ws, wd, wg):
        hh = int(t_str.split("T")[1].split(":")[0])
        out[hh] = {"speed_mph": float(s_mph), "gust_mph": float(g_mph), "dir_deg": float(d_deg)}
    return out

def wind_bullets_every_2h(wind_by_hour: dict):
    bullets = []
    for hh in range(0, 24, 2):
        w = wind_by_hour.get(hh)
        if not w:
            continue
        hour_dt = datetime(2000, 1, 1, hh, 0, 0)  # formatting only
        hour_str = hour_dt.strftime("%-I %p")
        direction = deg_to_compass(w["dir_deg"])
        bullets.append(
            f"**{hour_str}**: {int(round(w['speed_mph']))} mph {direction}, gust {int(round(w['gust_mph']))} mph"
        )
    return bullets

# ----------------------------
# Bite curve (per-minute)
# ----------------------------
def build_bite_curve(day: date, tz: pytz.BaseTzInfo, events: dict):
    centers = []
    weights = []
    sigmas = []

    def add(dt, w, sigma):
        if dt:
            centers.append(minutes_since_midnight(dt, tz))
            weights.append(w)
            sigmas.append(sigma)

    # Major
    add(events.get("overhead"), 1.00, 95)
    add(events.get("underfoot"), 1.00, 95)
    # Minor
    add(events.get("moonrise"), 0.65, 55)
    add(events.get("moonset"), 0.65, 55)
    # Sun bonus
    add(events.get("sunrise"), 0.55, 50)
    add(events.get("sunset"), 0.55, 50)

    x = []
    y = []
    for m in range(1440):
        val = 25.0
        for c, w, sig in zip(centers, weights, sigmas):
            dmin = min(abs(m - c), 1440 - abs(m - c))
            val += w * 60.0 * gaussian(dmin, 0.0, sig)
        x.append(to_datetime_local_naive(day, m))
        y.append(clamp(val, 0, 100))
    return x, y


# ----------------------------
# State
# ----------------------------
if "lat" not in st.session_state:
    st.session_state.lat = None
if "lon" not in st.session_state:
    st.session_state.lon = None
if "place" not in st.session_state:
    st.session_state.place = None

tz = pytz.timezone("America/Los_Angeles")
tz_name = tz.zone

# Capture query params from device location
qp = st.query_params
geo_error = qp.get("geo_error", None)
q_lat = qp.get("lat", None)
q_lon = qp.get("lon", None)

if geo_error:
    st.error(f"Location error: {geo_error}")

if q_lat and q_lon:
    try:
        st.session_state.lat = float(q_lat)
        st.session_state.lon = float(q_lon)
        st.session_state.place = "Device location"
    except:
        pass

# ----------------------------
# UI
# ----------------------------
st.markdown(
    """
<div class="fishynw-card">
  <div style="display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
    <div style="font-size:28px;">🎣</div>
    <div>
      <div style="font-size:20px; font-weight:700;">FishyNW Fishing Times</div>
      <div class="muted" style="font-size:13px;">One-day bite index graph + wind bullets</div>
    </div>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

st.write("")
st.markdown('<div class="fishynw-card">', unsafe_allow_html=True)

day = st.date_input("Date", value=datetime.now(tz).date())

method = st.selectbox("Location method", ["Device location", "City + State"])

if method == "Device location":
    if st.button("Get location", type="primary"):
        geolocation_component()
else:
    city = st.text_input("City", "Coeur d'Alene")
    state = st.text_input("State", "ID")
    if st.button("Find city", type="secondary"):
        try:
            lat, lon, place = geocode_city_state(city, state)
            st.session_state.lat = lat
            st.session_state.lon = lon
            st.session_state.place = place
            st.success(f"Found: {place}")
        except Exception as e:
            st.error(str(e))

loc_text = "Not set"
if st.session_state.lat is not None and st.session_state.lon is not None:
    loc_text = f"{st.session_state.place} ({st.session_state.lat:.4f}, {st.session_state.lon:.4f})"
st.markdown(f'<div class="muted small">Location: {loc_text}</div>', unsafe_allow_html=True)

go_btn = st.button("Generate", type="primary")

st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Output
# ----------------------------
if go_btn:
    if st.session_state.lat is None or st.session_state.lon is None:
        st.error("Set a location first.")
    else:
        try:
            lat = float(st.session_state.lat)
            lon = float(st.session_state.lon)
            place = st.session_state.place or "Location"

            events = get_events(day, lat, lon, tz)
            x, bite = build_bite_curve(day, tz, events)

            wind_by_hour = fetch_wind_for_day(day, lat, lon, tz_name)
            bullets = wind_bullets_every_2h(wind_by_hour)

            # Bite graph only
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=x,
                y=bite,
                mode="lines",
                name="Bite Index",
                hovertemplate="%{x|%I:%M %p}<br>Bite: %{y:.0f}<extra></extra>",
            ))
            fig.update_layout(
                title=f"Bite Index • {place}",
                height=480,
                margin=dict(l=10, r=10, t=45, b=10),
                hovermode="x unified",
                showlegend=False,
                yaxis=dict(title="Bite Index (0–100)", range=[0, 100]),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Wind bullets (every 2 hours)
            st.markdown("**Wind (every 2 hours):**")
            if bullets:
                for line in bullets:
                    st.markdown(f"- {line}")
            else:
                st.write("No wind data available for that day.")

        except Exception as e:
            st.error(str(e))

# ----------------------------
# Footer
# ----------------------------
st.markdown(
    """
<div class="footer">
  🎣 <b>FishyNW</b> • <a href="https://fishynw.com" target="_blank" rel="noopener">fishynw.com</a><br>
  Pacific Northwest Fishing • #adventure
</div>
""",
    unsafe_allow_html=True,
)