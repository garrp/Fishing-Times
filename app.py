import io
import requests
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, date, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

APP_VERSION = "1.0"
APP_TITLE = f"FishyNW Fishing Times v{APP_VERSION}"
LOGO_FILENAME = "FishyNW-logo.png"


# -----------------------------
# Network session with retries
# -----------------------------
def make_session():
    s = requests.Session()
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


SESSION = make_session()


def safe_read_logo(path: str):
    try:
        return open(path, "rb").read()
    except Exception:
        return None


# -----------------------------
# Cached API calls (safe)
# -----------------------------
@st.cache_data(ttl=86400)
def geocode_city(city: str):
    """
    Open-Meteo geocoding (no key). Cached 24h.
    Returns (label, lat, lon) or (None, None, None).
    """
    if not city or not city.strip():
        return None, None, None

    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city.strip(), "count": 1, "language": "en", "format": "json"}

    try:
        r = SESSION.get(url, params=params, timeout=(8, 25))
        if r.status_code != 200:
            return None, None, None

        data = r.json()
        results = data.get("results") or []
        if not results:
            return None, None, None

        top = results[0]
        label = ", ".join(
            [x for x in [top.get("name"), top.get("admin1"), top.get("country")] if x]
        )
        return label, float(top["latitude"]), float(top["longitude"])
    except Exception:
        return None, None, None


@st.cache_data(ttl=1800)
def fetch_weather(lat: float, lon: float, day: date):
    """
    Open-Meteo forecast (no key). Cached 30m.
    Returns JSON with hourly wind speed + direction, plus sunrise/sunset.
    Returns None on failure.
    """
    start = day.isoformat()
    end = (day + timedelta(days=1)).isoformat()

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wind_speed_10m,wind_direction_10m",
        "daily": "sunrise,sunset",
        "timezone": "auto",
        "start_date": start,
        "end_date": end,
        "wind_speed_unit": "mph",
    }

    try:
        r = SESSION.get(url, params=params, timeout=(8, 25))
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


# -----------------------------
# Helpers
# -----------------------------
def parse_iso_dt(s: str):
    return datetime.fromisoformat(s)


def wind_dir_to_text(deg: float):
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ix = int((deg + 22.5) // 45) % 8
    return dirs[ix]


def clamp_dt_to_day(dt_obj: datetime, target_day: date):
    """Force dt to have the same date as target_day while preserving time."""
    return datetime(
        year=target_day.year,
        month=target_day.month,
        day=target_day.day,
        hour=dt_obj.hour,
        minute=dt_obj.minute,
        second=0,
    )


def compute_fishing_windows(sunrise: datetime, sunset: datetime, target_day: date, species: str):
    """
    Returns a list of windows: (label, start_dt, end_dt, weight)
    weight is a rough "goodness" score (for graph shading)
    """
    dawn_start = sunrise - timedelta(hours=1)
    dawn_end = sunrise + timedelta(hours=1, minutes=30)

    midday_start = sunrise.replace(hour=11, minute=0)
    midday_end = sunrise.replace(hour=13, minute=0)

    dusk_start = sunset - timedelta(hours=1, minutes=30)
    dusk_end = sunset + timedelta(minutes=45)

    windows = [
        ("Early", dawn_start, dawn_end, 0.75),
        ("Midday", midday_start, midday_end, 0.55),
        ("Evening", dusk_start, dusk_end, 0.80),
    ]

    s = (species or "").strip().lower()

    if s in ["kokanee", "rainbow trout", "chinook", "lake trout", "trout"]:
        windows = [
            ("Early (best)", dawn_start, dawn_end, 0.90),
            ("Midday", midday_start, midday_end, 0.45),
            ("Evening (best)", dusk_start, dusk_end, 0.90),
        ]
    elif s in ["walleye"]:
        windows = [
            ("Early", dawn_start, dawn_end, 0.70),
            ("Midday", midday_start, midday_end, 0.35),
            ("Evening (best)", dusk_start, dusk_end, 0.90),
        ]
    elif s in ["smallmouth bass", "largemouth bass", "bass"]:
        windows = [
            ("Early (best)", dawn_start, dawn_end, 0.85),
            ("Midday", midday_start, midday_end, 0.60),
            ("Evening (best)", dusk_start, dusk_end, 0.85),
        ]
    elif s in ["catfish", "channel catfish", "bullhead"]:
        windows = [
            ("Early", dawn_start, dawn_end, 0.45),
            ("Midday", midday_start, midday_end, 0.50),
            ("Evening (best)", dusk_start, dusk_end, 0.90),
        ]

    fixed = []
    for label, start_dt, end_dt, weight in windows:
        if start_dt.date() != target_day:
            start_dt = clamp_dt_to_day(start_dt, target_day)
        if end_dt.date() != target_day:
            end_dt = clamp_dt_to_day(end_dt, target_day)
        fixed.append((label, start_dt, end_dt, weight))
    return fixed


def wind_every_n_hours(times, speeds, dirs, target_day: date, step_hours: int):
    """
    Pick entries every N hours and keep only target_day.
    Returns list of (datetime, mph, dir_text)
    """
    step = max(1, int(step_hours))
    out = []
    for i in range(0, len(times), step):
        t = parse_iso_dt(times[i])
        if t.date() == target_day:
            out.append((t, float(speeds[i]), wind_dir_to_text(float(dirs[i]))))
    return out


def make_fishing_graph(target_day: date, windows):
    start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0)
    end = start + timedelta(days=1)

    fig = plt.figure(figsize=(10, 2.6), dpi=160)
    ax = fig.add_subplot(111)

    ax.plot([start, end], [0, 0])

    for _, s_dt, e_dt, weight in windows:
        ax.axvspan(s_dt, e_dt, alpha=max(0.08, min(0.35, weight * 0.35)))

    ax.set_ylim(-1, 1)
    ax.set_yticks([])
    ax.set_title("Best Fishing Times (shaded)")
    ax.set_xlabel("Time")

    fig.autofmt_xdate()

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


def species_note(species: str):
    s = (species or "").strip().lower()
    if s in ["kokanee", "rainbow trout", "chinook", "lake trout", "trout"]:
        return "Trolling usually lines up best with dawn and dusk. Keep passes clean when wind shifts."
    if s in ["walleye"]:
        return "Low light is your friend. Focus the evening window and nearby low-light periods."
    if s in ["smallmouth bass", "largemouth bass", "bass"]:
        return "Early and late are strongest. Wind can help by pushing bait onto banks and points."
    if s in ["catfish", "channel catfish", "bullhead"]:
        return "Evening is typically strongest. Wind matters less than bait placement and scent trail."
    return "Use the shaded windows as a starting point. Adjust based on wind, structure, and marks."


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title=APP_TITLE, layout="centered")

# Header
logo = safe_read_logo(LOGO_FILENAME)
if logo:
    st.image(logo, use_container_width=True)

st.title(APP_TITLE)
st.caption("Version 1.0 • One day only • Best fishing times graph • Wind listed every 2 hours")

# Sidebar inputs (v1.0 layout polish)
with st.sidebar:
    st.subheader("Inputs")

    city = st.text_input("City / place name", "Coeur d'Alene, ID")
    manual = st.checkbox("Use manual lat/lon")
    target_date = st.date_input("Day", date.today())

    species = st.selectbox(
        "Species",
        [
            "Kokanee",
            "Rainbow trout",
            "Walleye",
            "Smallmouth bass",
            "Largemouth bass",
            "Chinook",
            "Lake trout",
            "Catfish",
            "Other",
        ],
        index=0,
    )

    lat = lon = None
    if manual:
        lat = st.number_input("Latitude", value=47.6777, format="%.6f")
        lon = st.number_input("Longitude", value=-116.7805, format="%.6f")

    submitted = st.button("Get fishing outlook", use_container_width=True)

if not submitted:
    st.stop()

# Resolve location
if manual:
    place_label = "Custom location"
    lat, lon = float(lat), float(lon)
else:
    place_label, lat, lon = geocode_city(city)
    if lat is None or lon is None:
        st.warning("City lookup failed or timed out. Try again or switch to manual lat/lon.")
        st.stop()

st.markdown("### Location")
st.write(f"{place_label} (lat {lat:.4f}, lon {lon:.4f})")

# Fetch weather (with graceful fallback)
wx = fetch_weather(lat, lon, target_date)
using_fallback = False

if wx is None:
    using_fallback = True
    st.info(
        "Live weather temporarily unavailable or rate-limited. "
        "Showing estimated fishing windows and calm-wind fallback."
    )

if using_fallback:
    times = [
        datetime(target_date.year, target_date.month, target_date.day, h, 0).isoformat()
        for h in range(0, 24)
    ]
    speeds = [3.0] * 24  # mph
    dirs = [180.0] * 24  # degrees (S)

    sunrise = datetime(target_date.year, target_date.month, target_date.day, 6, 30)
    sunset = datetime(target_date.year, target_date.month, target_date.day, 17, 0)
else:
    hourly = wx.get("hourly") or {}
    daily = wx.get("daily") or {}

    times = hourly.get("time") or []
    speeds = hourly.get("wind_speed_10m") or []
    dirs = hourly.get("wind_direction_10m") or []

    sunrise_list = daily.get("sunrise") or []
    sunset_list = daily.get("sunset") or []

    sunrise = parse_iso_dt(sunrise_list[0]) if sunrise_list else None
    sunset = parse_iso_dt(sunset_list[0]) if sunset_list else None

if not times or not speeds or not dirs:
    st.warning("No wind data available for this location/date.")
    st.stop()

# Best fishing windows
st.markdown("### Best Fishing Times (graph)")
if sunrise and sunset:
    windows = compute_fishing_windows(sunrise, sunset, target_date, species)
else:
    start = datetime(target_date.year, target_date.month, target_date.day, 6, 0, 0)
    mid = datetime(target_date.year, target_date.month, target_date.day, 12, 0, 0)
    eve = datetime(target_date.year, target_date.month, target_date.day, 18, 0, 0)
    windows = [
        ("Early", start, start + timedelta(hours=2), 0.75),
        ("Midday", mid - timedelta(hours=1), mid + timedelta(hours=1), 0.55),
        ("Evening", eve - timedelta(hours=1), eve + timedelta(hours=2), 0.80),
    ]

graph_buf = make_fishing_graph(target_date, windows)
st.image(graph_buf, use_container_width=True)

st.markdown("### Best Windows (list)")
for label, s_dt, e_dt, _ in windows:
    st.write(f"• {label}: {s_dt.strftime('%-I:%M %p')} - {e_dt.strftime('%-I:%M %p')}")

st.markdown("### Species Note")
st.write(f"• {species_note(species)}")

# Winds every 2 hours
st.markdown("### Wind (every 2 hours)")
wind2 = wind_every_n_hours(times, speeds, dirs, target_date, step_hours=2)

if not wind2:
    for i in range(min(12, len(times))):
        ttxt = parse_iso_dt(times[i]).strftime("%-I:%M %p")
        st.write(f"• {ttxt}: {float(speeds[i]):.0f} mph ({wind_dir_to_text(float(dirs[i]))})")
else:
    for t, mph, dtxt in wind2:
        st.write(f"• {t.strftime('%-I:%M %p')}: {mph:.0f} mph ({dtxt})")

st.caption(f"FishyNW • v{APP_VERSION} • one-day • best times graph • wind every 2 hours")