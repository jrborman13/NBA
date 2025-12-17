import streamlit as st

st.set_page_config(
    page_title="NBA Data App",
    page_icon="🏀",
    layout="wide"
)

st.title("🏀 NBA Data App")
st.markdown("---")

st.markdown("""
Welcome to the NBA Data App! This application provides comprehensive NBA analytics 
across two main areas:

### 📊 Teams
View team matchup data including:
- Core stats (Offensive/Defensive ratings, Net rating, Pace)
- Shooting stats (FG%, 3PT%, Zone shooting)
- Rebounding and playmaking metrics
- Season and Last 5 game comparisons

### 👤 Players  
View individual player data including:
- Season averages and rolling averages
- Game logs with performance vs season average
- Zone matchup analysis vs opponent defense
- Stat predictions with injury adjustments
- Vegas line comparisons

---

**Select a page from the sidebar to get started!**
""")

# Add some visual elements
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <a href="/Teams" style="text-decoration: none;">
        <div style="background: linear-gradient(135deg, #1d428a 0%, #c8102e 100%); 
                    padding: 20px; border-radius: 10px; text-align: center; cursor: pointer;">
            <h2 style="color: white; margin: 0;">Teams</h2>
            <p style="color: white; margin: 10px 0 0 0;">Matchup & Team Analytics</p>
        </div>
    </a>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <a href="/Players" style="text-decoration: none;">
        <div style="background: linear-gradient(135deg, #c8102e 0%, #1d428a 100%); 
                    padding: 20px; border-radius: 10px; text-align: center; cursor: pointer;">
            <h2 style="color: white; margin: 0;">Players</h2>
            <p style="color: white; margin: 10px 0 0 0;">Individual Stats & Predictions</p>
        </div>
    </a>
    """, unsafe_allow_html=True)

st.markdown("---")
st.caption("Data sourced from NBA API and pbpstats.com")

