import io
import requests
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, date, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

APP_VERSION = "1.0"
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
# Cached API call
# -----------------------------
@st.cache_data(ttl=1800)
def fetch_weather(lat: float, lon: float, day: date):
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
    return datetime(
        target_day.year,
        target_day.month,
        target_day.day,
        dt_obj.hour,
        dt_obj.minute,
        0,
    )


def compute_fishing_windows(sunrise: datetime, sunset: datetime, target_day: date):
    dawn_start = sunrise - timedelta(hours=1)
    dawn_end = sunrise + timedelta(hours=1, minutes=30)

    midday_start = sunrise.replace(hour=11, minute=0)
    midday_end = sunrise.replace(hour=13, minute=0)

    dusk_start = sunset - timedelta(hours=1, minutes=30)
    dusk_end = sunset + timedelta(minutes=45)

    windows = [
        ("Early", dawn_start, dawn_end, 0.80),
        ("Midday", midday_start, midday_end, 0.55),
        ("Evening", dusk_start, dusk_end, 0.85),
    ]

    fixed = []
    for label, s_dt, e_dt, w in windows:
        fixed.append(
            (
                label,
                clamp_dt_to_day(s_dt, target_day),
                clamp_dt_to_day(e_dt, target_day),
                w,
            )
        )
    return fixed


def wind_every_n_hours(times, speeds, dirs, target_day, step_hours):
    step_hours = max(1, int(step_hours))
    out = []
    for i in range(0, len(times), step_hours):
        t = parse_iso_dt(times[i])
        if t.date() == target_day:
            out.append((t, float(speeds[i]), wind_dir_to_text(float(dirs[i]))))
    return out


def make_fishing_graph(target_day, windows):
    start = datetime(target_day.year, target_day.month, target_day.day, 0, 0)
    end = start + timedelta(days=1)

    fig, ax = plt.subplots(figsize=(10, 2.6), dpi=160)
    ax.plot([start, end], [0, 0])

    for _, s_dt, e_dt, w in windows:
        ax.axvspan(s_dt, e_dt, alpha=max(0.10, min(0.38, w * 0.38)))

    ax.set_ylim(-1, 1)
    ax.set_yticks([])
    ax.set_title("Best Fishing Times")
    ax.set_xlabel("Time")

    fig.autofmt_xdate()
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf


# -----------------------------
# UI
# -----------------------------
st.set_page_config(page_title="Best fishing times by location", layout="centered")

# Two spaces from top margin
st.markdown(
    """
    <style>
    .block-container { padding-top: 2.5rem; }
    .stButton>button {
        background-color: #1f4fd8;
        color: white;
        font-weight: 700;
        border-radius: 8px;
        border: 0px;
        padding: 0.55rem 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
logo = safe_read_logo(LOGO_FILENAME)
if logo:
    col1, col2 = st.columns([1, 5])
    with col1:
        st.image(logo, width=120)
    with col2:
        st.markdown(
            """
            <h2 style="margin:0;">Best fishing times by location</h2>
            <p style="margin-top:0.4rem; color:#6c757d;">
            To use this app, click on the side menu bar to enter your location and generate the best fishing times.
            </p>
            """,
            unsafe_allow_html=True,
        )
else:
    st.markdown("## Best fishing times by location")
    st.caption(
        "To use this app, click on the side menu bar to enter your location and generate the best fishing times."
    )

st.divider()

# Sidebar
with st.sidebar:
    st.markdown("### Controls")
    target_date = st.date_input("Day", date.today())
    lat = st.number_input("Latitude", value=47.6777, format="%.6f")
    lon = st.number_input("Longitude", value=-116.7805, format="%.6f")
    submitted = st.button("Get fishing outlook", use_container_width=True)

if not submitted:
    st.stop()

st.markdown("### Location")
st.write(f"Lat {lat:.4f}, Lon {lon:.4f}")

# Weather fetch
wx = fetch_weather(lat, lon, target_date)
fallback = wx is None

if fallback:
    st.info("Live weather unavailable. Using calm-wind fallback.")

if fallback:
    times = [
        datetime(target_date.year, target_date.month, target_date.day, h).isoformat()
        for h in range(24)
    ]
    speeds = [3.0] * 24
    dirs = [180.0] * 24
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

windows = compute_fishing_windows(sunrise, sunset, target_date)

st.markdown("### Best Fishing Times")
st.image(make_fishing_graph(target_date, windows), use_container_width=True)

for label, s_dt, e_dt, _ in windows:
    st.write(f"• {label}: {s_dt.strftime('%-I:%M %p')} – {e_dt.strftime('%-I:%M %p')}")

st.markdown("### Wind (every 2 hours)")
for t, mph, d in wind_every_n_hours(times, speeds, dirs, target_date, 2):
    st.write(f"• {t.strftime('%-I:%M %p')}: {mph:.0f} mph ({d})")

st.caption("Fishing Northwest")