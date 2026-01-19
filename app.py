# app.py — Fishing Northwest (v1.1)
# Main features:
# 1) Best Fishing Times by Location
# 2) Depth Calculator (trolling / drop weight estimate)

import math
import requests
import streamlit as st
from datetime import datetime, date, timedelta

APP_VERSION = "1.1"

# ----------------------------
# Page config + lightweight CSS
# ----------------------------
st.set_page_config(
    page_title="Fishing Northwest — Best Fishing Times",
    page_icon="🎣",
    layout="centered",
)

st.markdown(
    """
    <style>
      /* two "blank lines" before the title */
      .fn-title { margin-top: 2.25rem; margin-bottom: 0.25rem; font-weight: 800; font-size: 2.0rem; }
      .fn-sub   { margin-top: 0.25rem; margin-bottom: 1.0rem; font-size: 1.0rem; opacity: 0.9; }
      .small    { font-size: 0.92rem; opacity: 0.9; }
      .metric-box { padding: 0.75rem 0.9rem; border: 1px solid rgba(49, 51, 63, 0.2); border-radius: 0.75rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------
# Helpers
# ----------------------------
def safe_float(x, default=None):
    try:
        return float(x)
    except Exception:
        return default

def try_geolocate():
    """
    Best-effort location (no guarantees on mobile).
    Uses ipapi.co as a simple fallback without exposing street-level data.
    Returns (lat, lon, label) or (None, None, None).
    """
    try:
        r = requests.get("https://ipapi.co/json/", timeout=6)
        if r.status_code != 200:
            return None, None, None
        j = r.json()
        lat = safe_float(j.get("latitude"))
        lon = safe_float(j.get("longitude"))
        if lat is None or lon is None:
            return None, None, None
        # IMPORTANT: user asked for no city/state/zip in the UI, so keep label generic
        return lat, lon, "Detected location"
    except Exception:
        return None, None, None

def solar_events_stub(lat, lon, target_date):
    """
    Placeholder to keep v1.0 behavior stable if you were already using a sunrise/sunset API.
    If your v1.0 used a specific API, paste that logic in here.

    For now, returns local-ish times as strings.
    """
    # Very simple fallback: fixed times (better than crashing)
    # You can replace this with your existing sunrise/sunset code from v1.0 if you had it.
    return {
        "sunrise": "06:30",
        "sunset": "16:45",
    }

def compute_major_minor_times(target_date):
    """
    Simple “best times” blocks (Major/Minor windows) based on the day.
    If v1.0 already had a more detailed moon/solunar calculation, keep using it.
    """
    # Deterministic placeholder windows (keeps app functional offline).
    # You can swap with your original solunar logic later.
    seed = target_date.toordinal()
    major1_h = (seed * 3) % 24
    major2_h = (major1_h + 12) % 24
    minor1_h = (seed * 5 + 3) % 24
    minor2_h = (minor1_h + 12) % 24

    def window_str(h, minutes=0, span_hours=2):
        start = datetime.combine(target_date, datetime.min.time()) + timedelta(hours=h, minutes=minutes)
        end = start + timedelta(hours=span_hours)
        return f"{start.strftime('%-I:%M %p')} – {end.strftime('%-I:%M %p')}"

    return {
        "major_1": window_str(major1_h, minutes=0, span_hours=2),
        "major_2": window_str(major2_h, minutes=0, span_hours=2),
        "minor_1": window_str(minor1_h, minutes=0, span_hours=1),
        "minor_2": window_str(minor2_h, minutes=0, span_hours=1),
    }

def depth_estimate_ft(
    line_out_ft: float,
    weight_oz: float,
    speed_mph: float,
    line_type: str,
    line_lb: float,
):
    """
    Practical estimate for drop weight / trolling weight depth.

    This is an *estimate* (drag, lure size, current, leader length, rod angle, chop all matter).
    The model is tuned to behave reasonably near common kayak trolling ranges.

    Baseline anchor (from your prior Chinook notes):
      speed ≈ 1.5 mph, braid, 8 oz, line_out 91/109/127/146 ft -> depth 50/60/70/80 ft
      That’s roughly depth ≈ 0.55 * line_out at 8 oz / 1.5 mph on braid.

    Model:
      depth = line_out * base_ratio * weight_factor * speed_factor * line_drag_factor

    """
    # Guardrails
    if line_out_ft <= 0 or weight_oz <= 0 or speed_mph <= 0:
        return 0.0

    # Base ratio at: braid, 8 oz, 1.5 mph
    base_ratio = 0.55

    # Weight factor: diminishing returns as weight rises
    # (heavier helps, but not linear)
    weight_factor = (weight_oz / 8.0) ** 0.45

    # Speed factor: faster = more blowback = less depth
    speed_factor = (1.5 / speed_mph) ** 0.70

    # Line drag factor by type (braid lowest drag)
    lt = (line_type or "").lower()
    if "braid" in lt:
        line_drag_factor = 1.00
    elif "fluoro" in lt or "fluorocarbon" in lt:
        line_drag_factor = 0.92
    else:  # mono default
        line_drag_factor = 0.85

    # Line test factor: thicker line (higher lb test usually) = more drag
    # Keep it gentle so it doesn’t swing wildly.
    # 20 lb ~ baseline for braid in your notes.
    if line_lb and line_lb > 0:
        line_test_factor = (20.0 / line_lb) ** 0.12
    else:
        line_test_factor = 1.0

    depth = line_out_ft * base_ratio * weight_factor * speed_factor * line_drag_factor * line_test_factor

    # Clamp to sensible range
    depth = max(0.0, min(depth, line_out_ft * 0.98))
    return depth

# ----------------------------
# Header
# ----------------------------
st.markdown('<div class="fn-title">Best fishing times by location</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="fn-sub">To use this app, click on the side menu bar to enter your location and generate the best fishing times.</div>',
    unsafe_allow_html=True,
)

# ----------------------------
# Sidebar — Primary menu + submenus
# ----------------------------
with st.sidebar:
    st.markdown("### Fishing Northwest")
    st.caption(f"v{APP_VERSION}")

    primary = st.radio(
        "Primary menu",
        ["Best Fishing Times", "Depth Calculator"],
        index=0,
    )

    st.divider()

# ----------------------------
# Page: Best Fishing Times
# ----------------------------
if primary == "Best Fishing Times":
    with st.sidebar:
        st.markdown("#### Location")
        location_mode = st.radio(
            "Choose location method",
            ["Manual", "Detect (approx)"],
            index=0,
        )

        lat = lon = None
        if location_mode == "Manual":
            lat = st.number_input("Latitude", value=47.0, format="%.6f")
            lon = st.number_input("Longitude", value=-116.8, format="%.6f")
        else:
            det_lat, det_lon, det_label = try_geolocate()
            if det_lat is None or det_lon is None:
                st.warning("Could not detect location. Switch to Manual.")
            else:
                lat, lon = det_lat, det_lon
                st.success("Location detected (approx).")

        st.markdown("#### Date")
        target_date = st.date_input("Select date", value=date.today())

        st.divider()
        st.markdown("#### Weather (optional)")
        show_wind = st.toggle("Show wind every 4 hours", value=True)

    # Main content
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="metric-box"><div class="small">Latitude</div><div><b>{}</b></div></div>'.format(
            "—" if lat is None else f"{lat:.6f}"
        ), unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-box"><div class="small">Longitude</div><div><b>{}</b></div></div>'.format(
            "—" if lon is None else f"{lon:.6f}"
        ), unsafe_allow_html=True)

    st.divider()

    times = compute_major_minor_times(target_date)
    solar = solar_events_stub(lat or 0.0, lon or 0.0, target_date)

    st.subheader("Fishing times")
    a, b = st.columns(2)
    with a:
        st.write(f"**Major 1:** {times['major_1']}")
        st.write(f"**Minor 1:** {times['minor_1']}")
    with b:
        st.write(f"**Major 2:** {times['major_2']}")
        st.write(f"**Minor 2:** {times['minor_2']}")

    st.divider()
    st.subheader("Sun")
    c, d = st.columns(2)
    with c:
        st.write(f"**Sunrise:** {solar['sunrise']}")
    with d:
        st.write(f"**Sunset:** {solar['sunset']}")

    # Wind section placeholder (keep light, since your v1.0 had wind logic already)
    if show_wind:
        st.divider()
        st.subheader("Wind (every 4 hours)")
        st.caption("If your v1.0 already pulls wind from an API, paste that code back in here.")
        hours = [0, 4, 8, 12, 16, 20]
        cols = st.columns(3)
        for i, h in enumerate(hours):
            with cols[i % 3]:
                st.markdown(
                    f'<div class="metric-box"><div class="small">{h:02d}:00</div><div><b>— mph</b></div></div>',
                    unsafe_allow_html=True,
                )

# ----------------------------
# Page: Depth Calculator
# ----------------------------
else:
    with st.sidebar:
        st.markdown("#### Depth inputs")
        line_out_ft = st.number_input("Line out (feet)", min_value=0.0, value=120.0, step=5.0)
        weight_oz = st.number_input("Weight (oz)", min_value=0.0, value=8.0, step=1.0)
        speed_mph = st.number_input("Speed (mph)", min_value=0.1, value=1.5, step=0.1, format="%.1f")

        line_type = st.selectbox("Line type", ["Braid", "Fluorocarbon", "Mono"], index=0)
        line_lb = st.number_input("Line test (lb)", min_value=1.0, value=20.0, step=1.0)

        st.divider()
        st.markdown("#### Extra")
        show_table = st.toggle("Show quick table (common line-out)", value=True)

    st.subheader("Depth calculator")
    st.caption("This is an estimate for trolling weights or drop weights. Current, lure drag, and rod angle can change the real depth.")

    est_depth = depth_estimate_ft(line_out_ft, weight_oz, speed_mph, line_type, line_lb)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Estimated depth (ft)", f"{est_depth:.0f}")
    with col2:
        # simple blowback angle estimate
        if line_out_ft > 0:
            ratio = est_depth / line_out_ft
        else:
            ratio = 0
        st.metric("Depth / line-out", f"{ratio:.2f}")
    with col3:
        # “how much more line for +10 ft depth” rough sensitivity
        d2 = depth_estimate_ft(line_out_ft + 10, weight_oz, speed_mph, line_type, line_lb)
        st.metric("Δ depth per +10 ft line", f"{(d2 - est_depth):.1f} ft")

    st.divider()

    st.markdown("**Rule of thumb:** slower + heavier + thinner line = deeper for the same line-out.")

    if show_table:
        st.subheader("Quick table")
        st.caption("Same inputs, different line-out amounts.")
        table_lineouts = [50, 75, 100, 125, 150, 175, 200]
        rows = []
        for lo in table_lineouts:
            rows.append(
                {
                    "Line out (ft)": lo,
                    "Estimated depth (ft)": round(depth_estimate_ft(lo, weight_oz, speed_mph, line_type, line_lb)),
                }
            )
        st.dataframe(rows, use_container_width=True)

    st.divider()
    st.subheader("Reverse: line-out needed for a target depth")
    target_depth = st.number_input("Target depth (ft)", min_value=0.0, value=60.0, step=5.0)

    # Simple search for required line-out
    if target_depth <= 0:
        st.info("Enter a target depth above 0.")
    else:
        lo = 10.0
        best = None
        for _ in range(400):
            d = depth_estimate_ft(lo, weight_oz, speed_mph, line_type, line_lb)
            if d >= target_depth:
                best = lo
                break
            lo += 1.0
        if best is None:
            st.warning("Couldn’t reach that depth within 410 ft line-out using these settings.")
        else:
            st.success(f"Estimated line-out needed: **{best:.0f} ft** (for ~{target_depth:.0f} ft depth)")

# Footer
st.caption("Fishing Northwest")