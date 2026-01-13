"""
Test Teams Page using Sportradar API Data
This is a test page to validate Sportradar API integration.
Keeps the same structure as the main Teams page but uses Sportradar data sources.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'streamlit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'new-streamlit-app', 'player-app'))

import streamlit as st
import datetime
from datetime import date
import pandas as pd

try:
    import sportradar_data_reader as sr_db_reader
except ImportError:
    sr_db_reader = None

st.set_page_config(layout="wide")
st.title("NBA Matchup Data App - Sportradar Test")

st.warning("⚠️ This is a test page using Sportradar API data. Compare with the main Teams page to validate data mapping.")

# Add sidebar with info
with st.sidebar:
    st.markdown("### Sportradar API Test")
    st.info("This page uses Sportradar API data stored in `sr_*` tables.")
    st.markdown("---")

# Function to fetch matchups using Sportradar schedule
def get_matchups_for_date_sr(selected_date):
    """Fetch NBA matchups for a given date from Sportradar data"""
    season = '2025-26'
    
    matchups = []
    error = None
    
    if sr_db_reader is None:
        return [], "Sportradar data reader not available"
    
    try:
        schedule_df = sr_db_reader.get_schedule_from_db(season)
        
        if schedule_df is None or len(schedule_df) == 0:
            return [], "No schedule data available from Sportradar"
        
        # Map Sportradar schedule fields to expected format
        # Note: Field names may differ - adjust based on actual API response
        # This is a placeholder mapping
        if 'scheduled' in schedule_df.columns:
            schedule_df['dateGame'] = pd.to_datetime(schedule_df['scheduled'])
        elif 'date' in schedule_df.columns:
            schedule_df['dateGame'] = pd.to_datetime(schedule_df['date'])
        else:
            return [], "Schedule data missing date field"
        
        date_games = schedule_df[
            schedule_df['dateGame'].dt.date == selected_date
        ]
        
        if len(date_games) > 0:
            for _, row in date_games.iterrows():
                # Extract team IDs - adjust field names based on actual API response
                away_team_id = row.get('away', {}).get('id', '') if isinstance(row.get('away'), dict) else row.get('away_team_id', '')
                home_team_id = row.get('home', {}).get('id', '') if isinstance(row.get('home'), dict) else row.get('home_team_id', '')
                
                matchup = {
                    'away_team_id': away_team_id,
                    'home_team_id': home_team_id,
                    'away_team_name': row.get('away', {}).get('name', '') if isinstance(row.get('away'), dict) else row.get('away_team_name', ''),
                    'home_team_name': row.get('home', {}).get('name', '') if isinstance(row.get('home'), dict) else row.get('home_team_name', ''),
                    'game_id': row.get('id', ''),
                    'date': selected_date
                }
                matchups.append(matchup)
        
        return matchups, None
        
    except Exception as e:
        return [], f"Error fetching Sportradar schedule: {str(e)}"

# Date selector
selected_date = st.date_input(
    "Select Game Date",
    value=date.today(),
    min_value=date(2024, 10, 1),
    max_value=date(2026, 6, 30)
)

# Fetch matchups
matchups, error = get_matchups_for_date_sr(selected_date)

if error:
    st.error(f"Error: {error}")
    st.info("Make sure you have run the Sportradar fetch scripts and data is available in Supabase.")
else:
    if len(matchups) == 0:
        st.info(f"No games scheduled for {selected_date}")
    else:
        st.success(f"Found {len(matchups)} game(s) for {selected_date}")
        
        # Display matchups
        for matchup in matchups:
            with st.expander(f"{matchup.get('away_team_name', 'Away')} @ {matchup.get('home_team_name', 'Home')}"):
                st.write(f"**Away Team ID:** {matchup.get('away_team_id', 'N/A')}")
                st.write(f"**Home Team ID:** {matchup.get('home_team_id', 'N/A')}")
                st.write(f"**Game ID:** {matchup.get('game_id', 'N/A')}")

# Standings section
st.markdown("---")
st.markdown("### 🏀 NBA Standings (Sportradar)")

if sr_db_reader:
    try:
        standings_df = sr_db_reader.get_standings_from_db()
        
        if standings_df is not None and len(standings_df) > 0:
            st.success(f"Loaded {len(standings_df)} teams from Sportradar")
            st.dataframe(standings_df.head(10), use_container_width=True)
        else:
            st.warning("No standings data available from Sportradar")
    except Exception as e:
        st.error(f"Error loading standings: {e}")
else:
    st.error("Sportradar data reader not available")

# Schedule section
st.markdown("---")
st.markdown("### 📅 Schedule (Sportradar)")

if sr_db_reader:
    try:
        schedule_df = sr_db_reader.get_schedule_from_db()
        
        if schedule_df is not None and len(schedule_df) > 0:
            st.success(f"Loaded {len(schedule_df)} games from Sportradar")
            st.dataframe(schedule_df.head(10), use_container_width=True)
        else:
            st.warning("No schedule data available from Sportradar")
    except Exception as e:
        st.error(f"Error loading schedule: {e}")
else:
    st.error("Sportradar data reader not available")

# Data comparison section
st.markdown("---")
st.markdown("### 📊 Data Comparison")

st.info("""
**Next Steps:**
1. Run Sportradar fetch scripts to populate `sr_*` tables
2. Compare data structures between NBA API and Sportradar
3. Map fields to match existing app structure
4. Test full functionality with Sportradar data
""")

