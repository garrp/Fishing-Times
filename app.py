import math
from datetime import datetime, date, timedelta, time

import pandas as pd
import streamlit as st
from astral import LocationInfo
from astral.sun import sun
from astral.moon import moonrise, moonset, phase
from timezonefinder import TimezoneFinder
import pytz

# ================== FISHYNW BRAND SETTINGS ==================
BRAND_NAME = "FishyNW"
BRAND_TAGLINE = "Best Fishing Times • Solunar-style"
BRAND_SITE = "https://fishynw.com"
BRAND_ACCENT = "#2EC4B6"   # teal
BRAND_DARK = "#0B1320"     # near-black navy
BRAND_CARD = "#101B2D"     # card bg
BRAND_TEXT = "#EAF2FF"     # light text
BRAND_MUTED = "#A9B8D3"    # muted text
BRAND_WARN = "#FF9F1C"     # orange
BRAND_GOOD = "#2EC4B6"     # teal
BRAND_BAD = "#FF4D6D"      # red/pink
# Optional: put a logo PNG in the same folder named "fishynw_logo.png"
LOGO_PATH = "fishynw_logo.png"
# ============================================================

# ------------------ helpers ------------------
def minutes_between(a, b):
    return abs((a - b).total_seconds()) / 60.0

def gaussian(minutes, sigma):
    return math.exp(-(minutes ** 2) / (2 * sigma ** 2))

def clamp01(x):
    return max(0.0, min(1.0, x))

def fmt(dt):
    # Windows-friendly fallback if %-I fails
    if not dt:
        return "—"
    try:
        return dt.strftime("%-I:%M %p")
    except Exception:
        return dt.strftime("%I:%M %p").lstrip("0")

# ------------------ core logic ------------------
def best_fishing_times(d: date, lat: float, lon: float):
    tf = TimezoneFinder()
    tzname = tf.timezone_at(lat=lat, lng=lon) or "UTC"
    tz = pytz.timezone(tzname)

    loc = LocationInfo(latitude=lat, longitude=lon, timezone=tzname)

    sun_data = sun(loc.observer, date=d, tzinfo=tz)
    sunrise = sun_data["sunrise"]
    sunset = sun_data["sunset"]

    try:
        mr = moonrise(loc.observer, date=d, tzinfo=tz)
    except Exception:
        mr = None

    try:
        ms = moonset(loc.observer, date=d, tzinfo=tz)
    except Exception:
        ms = None

    moon_phase = phase(d)

    # phase boost (new + full)
    full = 14.8
    new_dist = min(moon_phase, 29.53 - moon_phase)
    full_dist = abs(moon_phase - full)
    phase_weight = clamp01(1 - min(new_dist, full_dist) / 10)

    start = tz.localize(datetime.combine(d, time(0, 0)))
    end = start + timedelta(days=1)

    rows = []
    t = start
    step = timedelta(minutes=30)

    while t < end:
        major = 0.0
        if mr:
            major = max(major, gaussian(minutes_between(t, mr), 60))
        if ms:
            major = max(major, gaussian(minutes_between(t, ms), 60))

        minor = max(
            gaussian(minutes_between(t, sunrise), 45),
            gaussian(minutes_between(t, sunset), 45),
        )

        crep = max(
            gaussian(minutes_between(t, sunrise), 30),
            gaussian(minutes_between(t, sunset), 30),
        )

        score = (0.55 * major + 0.30 * minor + 0.15 * crep)
        score *= (0.85 + 0.15 * phase_weight)

        rows.append({"time": t, "score": score})
        t += step

    df = pd.DataFrame(rows)
    df["score_norm"] = (df["score"] - df["score"].min()) / (
        df["score"].max() - df["score"].min() + 1e-9
    )

    top = df.sort_values("score", ascending=False).head(8)

    meta = {
        "timezone": tzname,
        "sunrise": sunrise,
        "sunset": sunset,
        "moonrise": mr,
        "moonset": ms,
        "moon_phase": moon_phase,
    }
    return df, top, meta

# ------------------ UI / BRAND THEME ------------------
st.set_page_config(
    page_title=f"{BRAND_NAME} • Best Fishing Times",
    page_icon="🎣",
    layout="wide",
)

st.markdown(
    f"""
<style>
/* --- App background --- */
.stApp {{
  background: radial-gradient(1200px 600px at 15% 10%, rgba(46,196,182,0.18), transparent 60%),
              radial-gradient(900px 500px at 90% 0%, rgba(255,159,28,0.10), transparent 55%),
              {BRAND_DARK};
  color: {BRAND_TEXT};
}}
/* --- Sidebar --- */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, rgba(16,27,45,0.96), rgba(11,19,32,0.96));
  border-right: 1px solid rgba(255,255,255,0.06);
}}
/* --- Typography --- */
h1,h2,h3 {{
  letter-spacing: -0.02em;
}}
/* --- Buttons --- */
.stButton > button {{
  background: {BRAND_ACCENT} !important;
  color: #001219 !important;
  border: 0 !important;
  border-radius: 14px !important;
  padding: 0.65rem 1rem !important;
  font-weight: 700 !important;
}}
.stButton > button:hover {{
  filter: brightness(1.04);
  transform: translateY(-1px);
}}
/* --- Metric cards --- */
div[data-testid="stMetric"] {{
  background: rgba(16,27,45,0.92);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  padding: 14px 14px 10px 14px;
}}
div[data-testid="stMetric"] label {{
  color: {BRAND_MUTED} !important;
}}
/* --- Inputs --- */
input, textarea {{
  border-radius: 12px !important;
}}
/* --- Custom cards --- */
.fishy-card {{
  background: rgba(16,27,45,0.92);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 18px;
  padding: 14px 16px;
  margin: 10px 0;
}}
.fishy-muted {{
  color: {BRAND_MUTED};
}}
.fishy-pill {{
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 700;
  margin-left: 8px;
  background: rgba(46,196,182,0.18);
  border: 1px solid rgba(46,196,182,0.30);
  color: {BRAND_TEXT};
}}
.fishy-score {{
  font-variant-numeric: tabular-nums;
}}
/* --- Footer --- */
.fishy-footer {{
  margin-top: 22px;
  padding-top: 14px;
  border-top: 1px solid rgba(255,255,255,0.08);
  color: {BRAND_MUTED};
  font-size: 0.9rem;
}}
a {{
  color: {BRAND_ACCENT};
  text-decoration: none;
}}
a:hover {{
  text-decoration: underline;
}}
</style>
""",
    unsafe_allow_html=True,
)

# ------------------ Header ------------------
left, right = st.columns([1, 2], vertical_alignment="center")
with left:
    try:
        st.image(LOGO_PATH, use_container_width=True)
    except Exception:
        st.markdown(f"## {BRAND_NAME} 🎣")
with right:
    st.markdown(f"## {BRAND_TAGLINE}")
    st.markdown(
        f"<div class='fishy-muted'>Built for kayak & PNW anglers • Powered by solunar events + twilight overlap</div>",
        unsafe_allow_html=True,
    )

# ------------------ Sidebar controls ------------------
with st.sidebar:
    st.markdown(f"### {BRAND_NAME} Settings")
    st.markdown(f"<div class='fishy-muted'>Pick a spot and date. Get the top bite windows.</div>", unsafe_allow_html=True)

    date_input = st.date_input("Date", value=date.today())
    lat = st.number_input("Latitude", value=47.67, format="%.6f")
    lon = st.number_input("Longitude", value=-116.78, format="%.6f")

    st.markdown(
        "<div class='fishy-muted'>Tip: Google Maps → right-click → “What’s here?”</div>",
        unsafe_allow_html=True,
    )

# ------------------ Main action ------------------
colA, colB, colC = st.columns([1.2, 1, 1], vertical_alignment="center")
with colA:
    run = st.button("Calculate Fishing Times")
with colB:
    show_table = st.toggle("Show top-times table", value=True)
with colC:
    show_curve = st.toggle("Show activity curve", value=True)

if run:
    df, top, meta = best_fishing_times(date_input, lat, lon)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Timezone", meta["timezone"])
    m2.metric("Sunrise", fmt(meta["sunrise"]))
    m3.metric("Sunset", fmt(meta["sunset"]))
    m4.metric("Moonrise", fmt(meta["moonrise"]))
    m5.metric("Moonset", fmt(meta["moonset"]))

    st.markdown("### 🔥 Best Bite Windows (Fishy Score)")
    for _, row in top.iterrows():
        score = float(row["score_norm"])
        pill = "HOT" if score >= 0.85 else ("GOOD" if score >= 0.70 else "OK")
        st.markdown(
            f"""
<div class="fishy-card">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div>
      <span style="font-size:1.1rem; font-weight:800;">{fmt(row['time'])}</span>
      <span class="fishy-pill">{pill}</span>
      <div class="fishy-muted">Local time • 30-minute window centerpoint</div>
    </div>
    <div class="fishy-score" style="font-size:1.4rem; font-weight:900;">
      {score:.2f}
    </div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    if show_table:
        st.markdown("### 📋 Top Times Table")
        table = top.copy()
        table["time_local"] = table["time"].apply(fmt)
        table["fishy_score"] = table["score_norm"].round(3)
        st.dataframe(table[["time_local", "fishy_score"]], use_container_width=True, hide_index=True)

    if show_curve:
        st.markdown("### 📈 Full-Day Activity Curve")
        st.line_chart(df.set_index("time")["score_norm"], height=320)

    st.markdown(
        f"""
<div class="fishy-footer">
  <div><strong>{BRAND_NAME}</strong> • Solunar-style prediction (moonrise/set + sunrise/sunset + twilight overlap).</div>
  <div>Want this embedded on your site? Link: <a href="{BRAND_SITE}" target="_blank">{BRAND_SITE}</a></div>
</div>
""",
        unsafe_allow_html=True,
    )

else:
    st.markdown(
        """
<div class="fishy-card">
  <div style="font-size:1.05rem; font-weight:800;">How this works</div>
  <div class="fishy-muted" style="margin-top:6px;">
    We score the day using solunar-style signals:
    <ul>
      <li><b>Major periods</b>: around <b>moonrise</b> and <b>moonset</b></li>
      <li><b>Minor periods</b>: around <b>sunrise</b> and <b>sunset</b></li>
      <li>Extra love for <b>dawn/dusk overlap</b></li>
      <li>Small nudge for <b>moon phase</b> near new/full</li>
    </ul>
    Hit <b>Calculate Fishing Times</b> to generate your Fishy Score windows.
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
