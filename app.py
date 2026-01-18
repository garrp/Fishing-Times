import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="FishyNW Fishing Times",
    layout="centered"
)

st.title("FishyNW Fishing Times")
st.caption("Simple one-day fishing outlook")

today = datetime.now().strftime("%A, %B %d, %Y")

st.subheader(today)

st.markdown("### Best Fishing Windows")
st.markdown("""
• Early Morning: 6:00 AM – 8:00 AM  
• Midday: 11:30 AM – 1:00 PM  
• Evening: 5:30 PM – 8:00 PM  
""")

st.markdown("### Wind Outlook (Every 4 Hours)")
st.markdown("""
• 6:00 AM: Light breeze  
• 10:00 AM: Moderate wind  
• 2:00 PM: Moderate wind  
• 6:00 PM: Calm  
""")