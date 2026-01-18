# app.py
# FishyNW Fishing Times (Streamlit)
# Fresh start: device geolocation (mobile/desktop) + manual fallback + sunrise/sunset bite windows
#
# Install:
#   pip install streamlit astral timezonefinder
#
# Run:
#   streamlit run app.py

import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta, date

from astral import LocationInfo
from astral.sun import sun
from timezonefinder import TimezoneFinder


# -------------------------
# Page + basic styling
# -------------------------
st.set_page_config(page_title="FishyNW Fishing Times", page_icon="🎣", layout="centered")

st.markdown(
    """
    <style>
      .block-container { max-width: 760px; padding-top: 1.1rem; padding-bottom: 2rem; }
      @media (max-width: 600px){
        .block-container { padding-top: 0.6rem; }
        h1 { font-size: 1.6rem !important; }
      }
      .fishy-card {
        border: 1px solid rgba(0,0,0,0.10);
        border-radius: 18px;
        padding: 14px 14px;
        background: rgba(255,255,255,0.85);
      }
      .fishy-muted { color: rgba(0,0,0,0.62); font-size: 0.95rem; }
      .fishy-title { font-weight: 800; font-size: 1.05rem; margin-bottom: 6px; }
      .fishy-big { font-weight: 900; font-size: 1.25rem; }
      .fishy-row { display:flex; gap:10px; flex-wrap:wrap; margin: 8px 0 6px; }
      .fishy-pill {
        border: 1px solid rgba(0,0,0,0.12);
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 0.9rem;
        background: rgba(255,255,255,0.9);
      }
      .fishy-cta {
        padding: 12px 16px;
        border-radius: 16px;
        border: 1px solid #ddd;
        background: white;
        cursor: pointer;
        font-weight: 800;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## 🎣 FishyNW Fishing Times")
st.markdown('<div class="fishy-muted">Best windows using your device location + sunrise/sunset.</div>', unsafe_allow_html=True)
st.write("")


# -------------------------
# Helper: safe time format
# -------------------------
def fmt(t: datetime) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def window(center: datetime, before_min: int, after_min: int):
    return (center - timedelta(minutes=before_min), center + timedelta(minutes=after_min))


# -------------------------
# 1) Device geolocation (browser prompt)
# -------------------------
geo = components.html(
    """
    <div style="font-family: system-ui; font-size: 14px; display:flex; align-items:center; gap:12px; flex-wrap:wrap;">
      <button id="btn" class="fishy-cta">📍 Use my device location</button>
      <span id="status" style="color:#666; line-height:1.2;"></span>
    </div>

    <script>
      const statusEl = document.getElementById("status");
      const btn = document.getElementById("btn");

      function sendToStreamlit(payload) {
        window.parent.postMessage(
          { isStreamlitMessage: true, type: "streamlit:setComponentValue", value: payload },
          "*"
        );
      }

      btn.addEventListener("click", () => {
        statusEl.textContent = "Requesting location…";

        if (!navigator.geolocation) {
          statusEl.textContent = "Geolocation not supported.";
          sendToStreamlit({ ok: false, error: "Geolocation not supported" });
          return;
        }

        navigator.geolocation.getCurrentPosition(
          (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const acc = pos.coords.accuracy;
            statusEl.textContent = `Got it: ${lat.toFixed(5)}, ${lon.toFixed(5)} (±${Math.round(acc)}m)`;
            sendToStreamlit({ ok: true, lat: lat, lon: lon, acc_m: acc });
          },
          (err) => {
            statusEl.textContent = "Location blocked/unavailable. Use manual input below.";
            sendToStreamlit({ ok: false, error: err.message || "Location error" });
          },
          { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
        );
      });
    </script>
    """,
    height=70,
    key="geo_component",
)

# -------------------------
# 2) Manual fallback
# -------------------------
with st.expander("Manual location (if blocked)"):
    c1, c2 = st.columns(2)
    with c1:
        manual_lat = st.number_input("Latitude", value=47.677700, format="%.6f")
    with c2:
        manual_lon = st.number_input("Longitude", value=-116.780500, format="%.6f")
    use_manual = st.button("Use manual coordinates", type="primary")


# -------------------------
# Choose coordinates
# -------------------------
lat = lon = None
acc_m = None

if isinstance(geo, dict) and geo.get("ok"):
    lat, lon = float(geo["lat"]), float(geo["lon"])
    acc_m = geo.get("acc_m")
elif use_manual:
    lat, lon = float(manual_lat), float(manual_lon)

if lat is None or lon is None:
    st.info("Tap **📍 Use my device location**. If it’s blocked, open **Manual location**.")
    st.stop()

st.markdown(
    f"""
    <div class="fishy-row">
      <div class="fishy-pill"><b>Lat</b> {lat:.5f}</div>
      <div class="fishy-pill"><b>Lon</b> {lon:.5f}</div>
      <div class="fishy-pill"><b>Accuracy</b> {"±"+str(int(acc_m))+"m" if acc_m else "—"}</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# -------------------------
# Timezone + sun times
# -------------------------
tf = TimezoneFinder()
tz_name = tf.timezone_at(lat=lat, lng=lon) or "UTC"

loc = LocationInfo(name="You", region="Here", timezone=tz_name, latitude=lat, longitude=lon)

st.write("")
day = st.date_input("Date", value=date.today())

s = sun(loc.observer, date=day, tzinfo=loc.timezone)
sunrise = s["sunrise"]
sunset = s["sunset"]

# Simple, understandable bite windows
am_start, am_end = window(sunrise, before_min=60, after_min=90)
pm_start, pm_end = window(sunset, before_min=90, after_min=60)


# -------------------------
# UI output
# -------------------------
st.markdown("### Today’s Fishing Windows")

col1, col2 = st.columns(2, gap="medium")

with col1:
    st.markdown(
        f"""
        <div class="fishy-card">
          <div class="fishy-title">Morning bite</div>
          <div class="fishy-muted">Around sunrise</div>
          <div style="height:10px;"></div>

          <div class="fishy-muted">Sunrise</div>
          <div class="fishy-big">{fmt(sunrise)}</div>

          <div style="height:10px;"></div>
          <div class="fishy-muted">Best window</div>
          <div class="fishy-big">{fmt(am_start)} – {fmt(am_end)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        f"""
        <div class="fishy-card">
          <div class="fishy-title">Evening bite</div>
          <div class="fishy-muted">Around sunset</div>
          <div style="height:10px;"></div>

          <div class="fishy-muted">Sunset</div>
          <div class="fishy-big">{fmt(sunset)}</div>

          <div style="height:10px;"></div>
          <div class="fishy-muted">Best window</div>
          <div class="fishy-big">{fmt(pm_start)} – {fmt(pm_end)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.caption(f"Timezone: {tz_name}")


# -------------------------
# Footer / branding
# -------------------------
st.markdown("---")
st.markdown("**FishyNW** • Fish the Northwest • 🎥 + 🎣")
st.markdown("fishynw.com")
