import sys
import os
from pathlib import Path

# Add paths for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'scripts'))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))

import streamlit as st
import pandas as pd
from datetime import date, datetime
import pytz
import glob
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

# Import DraftKings functions
from fetch_draftkings_draftables import fetch_direct, fetch_via_zenrows, extract_player_data
from optimize_lineups_by_wave import get_matchups_with_times, group_games_by_wave, optimize_lineups_by_wave, combine_predictions_for_waves, optimize_combined_waves
from generate_predictions_batch import generate_predictions_for_date, get_matchups_for_date
from optimize_draftkings_nba_lineup import load_draftables, format_lineup_output, calculate_boom_bust_probabilities, merge_draftables_with_predictions, add_position_flags

# Import prediction functions
import player_functions as pf
import prediction_model as pm
import injury_report as ir

st.set_page_config(
    page_title="DraftKings Optimizer",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 DraftKings Lineup Optimizer")

# Initialize session state
if 'draftables_df' not in st.session_state:
    st.session_state.draftables_df = None
if 'draftgroup_id' not in st.session_state:
    st.session_state.draftgroup_id = None
if 'optimized_lineups' not in st.session_state:
    st.session_state.optimized_lineups = {}

# Sidebar settings
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Draftgroup ID input
    draftgroup_id_input = st.text_input(
        "DraftKings Draftgroup ID",
        value=str(st.session_state.draftgroup_id) if st.session_state.draftgroup_id else "",
        help="Enter the DraftKings draftgroup ID (e.g., 140610)"
    )
    
    # Date picker
    selected_date = st.date_input(
        "Game Date",
        value=date.today(),
        help="Select the date for the games you want to optimize"
    )
    
    # Max salary
    max_salary = st.number_input(
        "Max Salary",
        min_value=40000,
        max_value=60000,
        value=50000,
        step=1000,
        help="Maximum total salary for the lineup"
    )
    
    # Include injured players toggle
    include_injured = st.checkbox(
        "Include Injured Players",
        value=False,
        help="Include players marked as OUT or DOUBTFUL in predictions"
    )
    
    st.markdown("---")
    
    # Clear cache button
    if st.button("🗑️ Clear Cache", width='stretch'):
        st.cache_data.clear()
        st.session_state.draftables_df = None
        st.session_state.draftgroup_id = None
        st.session_state.optimized_lineups = {}
        st.success("Cache cleared!")
        st.rerun()

# Main content area
# Section 1: Draftables
st.header("📋 DraftKings Draftables")

if draftgroup_id_input:
    try:
        draftgroup_id = int(draftgroup_id_input)
            
        # Check if we need to fetch new draftables
        if (st.session_state.draftgroup_id != draftgroup_id or 
            st.session_state.draftables_df is None):
            
            if st.button("🔍 Fetch Draftables", type="primary", width='stretch'):
                try:
                    with st.spinner("Fetching draftables from DraftKings API..."):
                        # Try direct fetch first
                        data = fetch_direct(draftgroup_id)
                    
                        # If direct fails, try ZenRows fallback
                        if data is None:
                            st.info("Direct fetch failed, trying ZenRows proxy...")
                            data = fetch_via_zenrows(draftgroup_id)
                        
                        if data is None:
                            st.error("❌ Failed to fetch draftables from both direct API and ZenRows proxy.")
                            st.info("💡 Tips: Check that the draftgroup ID is correct and try again. If the issue persists, ensure ZENROWS_API_KEY is set if using the proxy.")
                        elif 'draftables' not in data:
                            st.error(f"❌ Response does not contain 'draftables' array.")
                            st.code(f"Response keys: {list(data.keys())}")
                        else:
                            draftables = data['draftables']
                            if not isinstance(draftables, list):
                                st.error(f"❌ Draftables is not a list (type: {type(draftables)})")
                            elif len(draftables) == 0:
                                st.error("❌ Draftables array is empty")
                            else:
                                try:
                                    # Extract and process
                                    df = extract_player_data(draftables)
                                    
                                    # Validate required columns
                                    required_cols = ['displayName', 'salary', 'position']
                                    missing_cols = [col for col in required_cols if col not in df.columns]
                                    if missing_cols:
                                        st.error(f"❌ Missing required columns: {missing_cols}")
                                    else:
                                        # Remove duplicates
                                        original_count = len(df)
                                        df = df.drop_duplicates(subset=['displayName'], keep='first')
                                        duplicates_removed = original_count - len(df)
                                        
                                        # Validate salary data
                                        if df['salary'].isna().any():
                                            st.warning(f"⚠️ Warning: {df['salary'].isna().sum()} player(s) have missing salary data")
                                        
                                        # Store in session state
                                        st.session_state.draftables_df = df
                                        st.session_state.draftgroup_id = draftgroup_id
                                        
                                        st.success(f"✅ Loaded {len(df)} players (removed {duplicates_removed} duplicates)")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Error processing draftables data: {e}")
                                    import traceback
                                    st.code(traceback.format_exc())
                except Exception as e:
                    st.error(f"❌ Unexpected error fetching draftables: {e}")
                    import traceback
                    st.code(traceback.format_exc())
        else:
            # Show current draftables info - full width
            df = st.session_state.draftables_df
            st.success(f"✅ Draftables loaded: {len(df)} players")
            
            # Salary range and position distribution
            if 'salary' in df.columns:
                st.metric("Salary Range", f"${df['salary'].min():,.0f} - ${df['salary'].max():,.0f}")
            
            # Position distribution - compact display with larger font
            if 'position' in df.columns:
                st.markdown("### Position Distribution")
                position_counts = df['position'].value_counts().head(10)
                # Display with pipe separator
                pos_text = " | ".join([f"{pos}: {count}" for pos, count in position_counts.items()])
                st.markdown(f"**{pos_text}**")
            
    except ValueError:
        st.warning("⚠️ Please enter a valid draftgroup ID (numbers only)")
else:
    st.info("👆 Enter a DraftKings draftgroup ID above to fetch draftables")

# Section 2: Schedule and Wave Selection
st.markdown("---")
st.header("📅 Schedule & Tip-Off Waves")

# Initialize variables
matchups = []
waves = {}
selected_waves = []
existing_predictions = {}

# Get matchups for selected date
@st.cache_data(ttl=3600)
def get_cached_matchups(selected_date):
    return get_matchups_with_times(selected_date)

if st.session_state.draftables_df is None:
    st.warning("⚠️ Please fetch draftables first before selecting games")
else:
    matchups = get_cached_matchups(selected_date)
    
    if len(matchups) == 0:
        st.info(f"ℹ️ No games scheduled for {selected_date.strftime('%Y-%m-%d')}")
    else:
        # Group games by tip-off wave
        ct_tz = pytz.timezone('US/Central')
        waves_dict = defaultdict(list)
        
        for matchup in matchups:
            game_datetime = matchup['game_datetime']
            game_time_ct = game_datetime.astimezone(ct_tz)
            
            # Format wave time string
            hour_12 = game_time_ct.hour % 12
            if hour_12 == 0:
                hour_12 = 12
            am_pm = "AM" if game_time_ct.hour < 12 else "PM"
            minutes = game_time_ct.minute
            wave_time_str = f"{hour_12}:{minutes:02d} {am_pm} CT"
            
            waves_dict[wave_time_str].append(matchup)
        
        waves = dict(waves_dict)
        
        # Display waves and allow selection
        st.subheader("Select Tip-Off Waves")
        
        wave_options = sorted(waves.keys())
        selected_waves = st.multiselect(
            "Tip-Off Times",
            options=wave_options,
            default=wave_options,  # Select all by default
            help="Select which tip-off waves to optimize lineups for"
        )
        
        # Show games for selected waves
        if selected_waves:
            st.markdown("**Games in selected waves:**")
            for wave_time in sorted(selected_waves):
                games_in_wave = waves[wave_time]
                with st.expander(f"{wave_time} ({len(games_in_wave)} game(s))"):
                    for matchup in games_in_wave:
                        st.text(f"  • {matchup['matchup']}")
        else:
            st.warning("⚠️ Please select at least one tip-off wave")

# Section 3: Predictions
st.markdown("---")
st.header("📊 Predictions")

downloads_dir = os.path.expanduser("~/Downloads")
game_date_str = selected_date.strftime('%Y-%m-%d')

if st.session_state.draftables_df is None or len(matchups) == 0:
    st.info("ℹ️ Fetch draftables and select a date with games to continue")
else:
    # Check for existing prediction files
    pattern = os.path.join(downloads_dir, f"predicted_statlines_*_{game_date_str}.csv")
    existing_prediction_files = glob.glob(pattern)
    
    # Map matchups to prediction files
    existing_predictions = {}
    for matchup in matchups:
        prediction_file = os.path.join(
            downloads_dir,
            f"predicted_statlines_{matchup['away_team']}_vs_{matchup['home_team']}_{game_date_str}.csv"
        )
        if os.path.exists(prediction_file):
            existing_predictions[matchup['matchup']] = prediction_file
    
    # Create tabs for Predictions and Injury Report
    pred_tab, injury_tab = st.tabs(["📊 Predictions", "🏥 Injury Report"])
    
    with pred_tab:
        # Show prediction status
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if len(existing_predictions) == len(matchups):
                st.success(f"✅ Predictions available for all {len(matchups)} game(s)")
            elif len(existing_predictions) > 0:
                st.warning(f"⚠️ Predictions available for {len(existing_predictions)}/{len(matchups)} game(s)")
            else:
                st.info(f"ℹ️ No predictions found. Will generate for {len(matchups)} game(s)")
        
        with col2:
            if len(existing_predictions) < len(matchups):
                if st.button("🔄 Generate Predictions", type="primary", width='stretch'):
                    try:
                        with st.spinner("Generating predictions for all games..."):
                            exclude_injured = not include_injured
                            output_files = generate_predictions_for_date(
                                selected_date,
                                output_dir=downloads_dir,
                                exclude_injured=exclude_injured,
                                optimize_lineups=False  # We'll optimize separately
                            )
                            
                            if len(output_files) > 0:
                                st.success(f"✅ Generated {len(output_files)} prediction file(s)")
                                st.rerun()
                            else:
                                st.error("❌ No prediction files were generated. Check the console for errors.")
                    except Exception as e:
                        st.error(f"❌ Error generating predictions: {e}")
                        import traceback
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())
                        st.info("💡 Tips: Ensure you have internet connectivity and that the NBA API is accessible.")
    
    with injury_tab:
        st.markdown("### Injury Report for Games")
        
        try:
            # Load player data for injury matching
            @st.cache_data(ttl=1800, show_spinner="Loading player data...")
            def load_injury_player_data():
                return pf.get_players_dataframe()
            
            players_df_injury = load_injury_player_data()
            
            # Fetch injury report
            @st.cache_data(ttl=600, show_spinner="Fetching injury report...")
            def fetch_injury_data():
                return ir.fetch_injuries_for_date(selected_date)
            
            injury_df, injury_status = fetch_injury_data()
            
            if injury_df is not None and len(injury_df) > 0:
                st.success(f"✅ {injury_status}")
                
                # Show injuries for each matchup
                for matchup in matchups:
                    away_team = matchup['away_team']
                    home_team = matchup['home_team']
                    matchup_str = matchup['matchup']
                    
                    # Format tip time
                    game_datetime = matchup.get('game_datetime')
                    if game_datetime:
                        ct_tz = pytz.timezone('US/Central')
                        if game_datetime.tzinfo is None:
                            # Assume UTC if no timezone
                            game_datetime = pytz.UTC.localize(game_datetime)
                        game_time_ct = game_datetime.astimezone(ct_tz)
                        hour_12 = game_time_ct.hour % 12
                        if hour_12 == 0:
                            hour_12 = 12
                        am_pm = "AM" if game_time_ct.hour < 12 else "PM"
                        minutes = game_time_ct.minute
                        tip_time_str = f"{hour_12}:{minutes:02d} {am_pm} CT"
                        matchup_with_time = f"{matchup_str} | {tip_time_str}"
                    else:
                        matchup_with_time = matchup_str
                    
                    st.markdown(f"#### {matchup_with_time}")
                    
                    # Get injuries for this matchup
                    matchup_injuries = ir.get_injuries_for_matchup(
                        injury_df, away_team, home_team, players_df_injury
                    )
                    
                    away_injuries = matchup_injuries.get('away', [])
                    home_injuries = matchup_injuries.get('home', [])
                    
                    if len(away_injuries) == 0 and len(home_injuries) == 0:
                        st.info(f"No injuries reported for {matchup_str}")
                    else:
                        # Helper function to format player name from "Last, First" to "First Last"
                        def format_player_name(name):
                            if not name or name == 'Unknown':
                                return name
                            # Check if name is in "Last, First" format
                            if ',' in name:
                                parts = name.split(',', 1)
                                if len(parts) == 2:
                                    last_name = parts[0].strip()
                                    first_name = parts[1].strip()
                                    return f"{first_name} {last_name}"
                            # If not in "Last, First" format, return as is
                            return name
                        
                        # Display away team injuries
                        if len(away_injuries) > 0:
                            st.markdown(f"**{away_team}:**")
                            away_data = []
                            for injury in away_injuries:
                                player_name = injury.get('player_name', 'Unknown')
                                away_data.append({
                                    'Player': format_player_name(player_name),
                                    'Status': injury.get('status', 'Unknown'),
                                    'Reason': injury.get('reason', 'N/A')
                                })
                            away_df = pd.DataFrame(away_data)
                            st.dataframe(away_df, width='stretch', hide_index=True)
                        
                        # Display home team injuries
                        if len(home_injuries) > 0:
                            st.markdown(f"**{home_team}:**")
                            home_data = []
                            for injury in home_injuries:
                                player_name = injury.get('player_name', 'Unknown')
                                home_data.append({
                                    'Player': format_player_name(player_name),
                                    'Status': injury.get('status', 'Unknown'),
                                    'Reason': injury.get('reason', 'N/A')
                                })
                            home_df = pd.DataFrame(home_data)
                            st.dataframe(home_df, width='stretch', hide_index=True)
                        
                        st.markdown("---")
            else:
                st.warning(f"⚠️ {injury_status}")
                st.info("💡 Injury reports are typically available closer to game time. Try again later.")
        except Exception as e:
            st.error(f"❌ Error fetching injury report: {e}")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())

# Section 4: Boom/Bust Analysis
st.markdown("---")
st.header("📊 Boom/Bust Analysis")

if (st.session_state.draftables_df is None or 
    len(matchups) == 0 or 
    len(existing_predictions) == 0):
    st.info("ℹ️ Fetch draftables, select games, and ensure predictions are available to view boom/bust analysis")
else:
    # Combine predictions from selected waves
    if selected_waves:
        try:
            combined_predictions_df, team_abbreviations = combine_predictions_for_waves(
                matchups, selected_waves, downloads_dir, selected_date
            )
            
            if len(combined_predictions_df) > 0:
                # Merge with draftables to get salaries
                draftables_df = st.session_state.draftables_df.copy()
                
                # Ensure normalized columns exist (required by merge_draftables_with_predictions)
                if 'displayName_normalized' not in draftables_df.columns:
                    from optimize_draftkings_nba_lineup import normalize_player_name
                    draftables_df['displayName_normalized'] = draftables_df['displayName'].apply(normalize_player_name)
                
                # Ensure predictions have normalized column
                if 'Player_normalized' not in combined_predictions_df.columns:
                    from optimize_draftkings_nba_lineup import normalize_player_name
                    combined_predictions_df['Player_normalized'] = combined_predictions_df['Player'].apply(normalize_player_name)
                
                merged_df = merge_draftables_with_predictions(draftables_df, combined_predictions_df)
                
                # Filter to selected teams
                if 'Team' in merged_df.columns:
                    merged_df = merged_df[merged_df['Team'].isin(team_abbreviations)].copy()
                
                if len(merged_df) > 0:
                    # Calculate boom/bust scores
                    merged_df = calculate_boom_bust_probabilities(merged_df)
                    
                    # Create two columns for boom and bust tables
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("🚀 Boom Candidates")
                        
                        # Filter boom candidates
                        boom_df = merged_df.copy()
                        
                        # Filters
                        boom_min_salary = st.slider(
                            "Min Salary",
                            min_value=3000,
                            max_value=10000,
                            value=3000,
                            step=500,
                            key="boom_min_salary"
                        )
                        boom_max_salary = st.slider(
                            "Max Salary",
                            min_value=3000,
                            max_value=10000,
                            value=10000,
                            step=500,
                            key="boom_max_salary"
                        )
                        boom_max_score = float(boom_df['Boom_Score'].max()) if len(boom_df) > 0 and 'Boom_Score' in boom_df.columns else 10.0
                        boom_min_score = st.slider(
                            "Min Boom Score",
                            min_value=0.0,
                            max_value=boom_max_score,
                            value=0.0,
                            step=0.5,
                            key="boom_min_score"
                        )
                        
                        # Apply filters
                        if 'Boom_Score' in boom_df.columns:
                            boom_df = boom_df[
                                (boom_df['salary'] >= boom_min_salary) &
                                (boom_df['salary'] <= boom_max_salary) &
                                (boom_df['Boom_Score'] >= boom_min_score)
                            ].copy()
                            
                            # Sort by boom score descending
                            boom_df = boom_df.sort_values('Boom_Score', ascending=False)
                        else:
                            boom_df = boom_df[
                                (boom_df['salary'] >= boom_min_salary) &
                                (boom_df['salary'] <= boom_max_salary)
                            ].copy()
                        
                        # Select columns to display
                        display_cols = ['Player', 'Team', 'salary', 'FPTS', 'FPTS_Ceiling', 'Boom_Score', 'Boom_Probability']
                        available_cols = [col for col in display_cols if col in boom_df.columns]
                        boom_display = boom_df[available_cols].copy()
                        
                        # Rename columns for display
                        rename_map = {}
                        if 'salary' in boom_display.columns:
                            rename_map['salary'] = 'Salary'
                        if 'FPTS_Ceiling' in boom_display.columns:
                            rename_map['FPTS_Ceiling'] = 'Ceiling FPTS'
                        if rename_map:
                            boom_display = boom_display.rename(columns=rename_map)
                        
                        # Format numbers
                        if 'Salary' in boom_display.columns:
                            boom_display['Salary'] = boom_display['Salary'].apply(lambda x: f"${x:,.0f}")
                        if 'FPTS' in boom_display.columns:
                            boom_display['FPTS'] = boom_display['FPTS'].apply(lambda x: f"{x:.1f}")
                        if 'Ceiling FPTS' in boom_display.columns:
                            boom_display['Ceiling FPTS'] = boom_display['Ceiling FPTS'].apply(lambda x: f"{x:.1f}")
                        if 'Boom_Score' in boom_display.columns:
                            boom_display['Boom_Score'] = boom_display['Boom_Score'].apply(lambda x: f"{x:.2f}")
                        if 'Boom_Probability' in boom_display.columns:
                            boom_display['Boom_Probability'] = boom_display['Boom_Probability'].apply(lambda x: f"{x:.1f}%")
                        
                        # Highlight top boom candidates
                        if len(boom_display) > 0:
                            st.dataframe(boom_display.head(20), use_container_width=True, hide_index=True)
                            st.caption(f"Showing top {min(20, len(boom_display))} boom candidates")
                        else:
                            st.info("No players match the boom filters")
                    
                    with col2:
                        st.subheader("💥 Bust Candidates")
                        
                        # Filter bust candidates
                        bust_df = merged_df.copy()
                        
                        # Filters
                        bust_min_salary = st.slider(
                            "Min Salary",
                            min_value=3000,
                            max_value=10000,
                            value=3000,
                            step=500,
                            key="bust_min_salary"
                        )
                        bust_max_salary = st.slider(
                            "Max Salary",
                            min_value=3000,
                            max_value=10000,
                            value=10000,
                            step=500,
                            key="bust_max_salary"
                        )
                        bust_max_score = float(bust_df['Bust_Score'].max()) if len(bust_df) > 0 and 'Bust_Score' in bust_df.columns else 10.0
                        bust_min_score = st.slider(
                            "Min Bust Score",
                            min_value=0.0,
                            max_value=bust_max_score,
                            value=0.0,
                            step=0.5,
                            key="bust_min_score"
                        )
                        
                        # Apply filters
                        if 'Bust_Score' in bust_df.columns:
                            bust_df = bust_df[
                                (bust_df['salary'] >= bust_min_salary) &
                                (bust_df['salary'] <= bust_max_salary) &
                                (bust_df['Bust_Score'] >= bust_min_score)
                            ].copy()
                            
                            # Sort by bust score descending
                            bust_df = bust_df.sort_values('Bust_Score', ascending=False)
                        else:
                            bust_df = bust_df[
                                (bust_df['salary'] >= bust_min_salary) &
                                (bust_df['salary'] <= bust_max_salary)
                            ].copy()
                        
                        # Select columns to display
                        display_cols = ['Player', 'Team', 'salary', 'FPTS', 'FPTS_Floor', 'Bust_Score', 'Bust_Probability']
                        available_cols = [col for col in display_cols if col in bust_df.columns]
                        bust_display = bust_df[available_cols].copy()
                        
                        # Rename columns for display
                        rename_map = {}
                        if 'salary' in bust_display.columns:
                            rename_map['salary'] = 'Salary'
                        if 'FPTS_Floor' in bust_display.columns:
                            rename_map['FPTS_Floor'] = 'Floor FPTS'
                        if rename_map:
                            bust_display = bust_display.rename(columns=rename_map)
                        
                        # Format numbers
                        if 'Salary' in bust_display.columns:
                            bust_display['Salary'] = bust_display['Salary'].apply(lambda x: f"${x:,.0f}")
                        if 'FPTS' in bust_display.columns:
                            bust_display['FPTS'] = bust_display['FPTS'].apply(lambda x: f"{x:.1f}")
                        if 'Floor FPTS' in bust_display.columns:
                            bust_display['Floor FPTS'] = bust_display['Floor FPTS'].apply(lambda x: f"{x:.1f}")
                        if 'Bust_Score' in bust_display.columns:
                            bust_display['Bust_Score'] = bust_display['Bust_Score'].apply(lambda x: f"{x:.2f}")
                        if 'Bust_Probability' in bust_display.columns:
                            bust_display['Bust_Probability'] = bust_display['Bust_Probability'].apply(lambda x: f"{x:.1f}%")
                        
                        # Display bust candidates
                        if len(bust_display) > 0:
                            st.dataframe(bust_display.head(20), width='stretch', hide_index=True)
                            st.caption(f"Showing top {min(20, len(bust_display))} bust candidates")
                        else:
                            st.info("No players match the bust filters")
            else:
                st.info("ℹ️ No predictions available for selected waves")
        except Exception as e:
            st.error(f"❌ Error calculating boom/bust analysis: {e}")
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())

# Section 5: Optimization
st.markdown("---")
st.header("⚡ Lineup Optimization")

if (st.session_state.draftables_df is None or 
    len(matchups) == 0 or 
    len(existing_predictions) == 0 or
    not selected_waves):
    st.info("ℹ️ Please ensure draftables are loaded, games are selected, predictions are available, and at least one wave is selected")
else:
    if st.button("🚀 Optimize Lineups", type="primary", width='stretch'):
        if not selected_waves:
            st.error("❌ Please select at least one tip-off wave")
        else:
            try:
                # Prepare draftables path (save to temp location for optimizer)
                draftables_path = os.path.join(downloads_dir, f"draftkings_draftables_{st.session_state.draftgroup_id}.csv")
                
                # Save draftables if not already saved
                if not os.path.exists(draftables_path):
                    try:
                        st.session_state.draftables_df.to_csv(draftables_path, index=False)
                    except Exception as e:
                        st.error(f"❌ Failed to save draftables file: {e}")
                        st.stop()
                
                # Validate draftables file exists
                if not os.path.exists(draftables_path):
                    st.error(f"❌ Draftables file not found: {draftables_path}")
                    st.stop()
                
                # Optimize combined waves (all selected waves together)
                with st.spinner("Optimizing 5 unique lineups using players from all selected waves..."):
                    try:
                        # Use combined wave optimization
                        optimized_lineups = optimize_combined_waves(
                            selected_date,
                            draftables_path,
                            selected_wave_times=selected_waves,
                            predictions_dir=downloads_dir,
                            output_dir=downloads_dir,
                            max_salary=max_salary
                        )
                        
                        if len(optimized_lineups) > 0:
                            # Store results with strategy names
                            strategy_names = ['Max FPTS', 'Max Value', 'Max Ceiling', 'Balanced', 'Punt Strategy']
                            st.session_state.optimized_lineups = {}
                            for idx, lineup_df in enumerate(optimized_lineups):
                                strategy_name = strategy_names[idx] if idx < len(strategy_names) else f"Lineup {idx + 1}"
                                st.session_state.optimized_lineups[strategy_name] = {
                                    'dataframe': lineup_df,
                                    'file_path': None  # Generated in memory
                                }
                            st.success(f"✅ Successfully optimized {len(optimized_lineups)} unique lineup(s) using players from {len(selected_waves)} wave(s)")
                            st.rerun()
                        else:
                            st.error("❌ No optimized lineups generated. Check console for errors.")
                    except ValueError as e:
                        error_msg = str(e)
                        if "infeasible" in error_msg.lower() or "no feasible solution" in error_msg.lower():
                            st.error("❌ No feasible lineup found. Check salary cap and position constraints.")
                        else:
                            st.error(f"❌ Optimization error: {error_msg}")
                    except Exception as e:
                        st.error(f"❌ Unexpected error during optimization: {e}")
                        import traceback
                        with st.expander("Error Details"):
                            st.code(traceback.format_exc())
            except Exception as e:
                st.error(f"❌ Unexpected error during optimization: {e}")
                import traceback
                with st.expander("Error Details"):
                    st.code(traceback.format_exc())

# Section 5: Results Display
if len(st.session_state.optimized_lineups) > 0:
    st.markdown("---")
    st.header("📈 Optimized Lineups")
    
    # Create tabs for each lineup strategy
    strategy_tabs = st.tabs(list(st.session_state.optimized_lineups.keys()))
    
    for tab_idx, (strategy_name, result) in enumerate(st.session_state.optimized_lineups.items()):
        with strategy_tabs[tab_idx]:
            lineup_df = result['dataframe']
            
            # Strategy descriptions
            strategy_descriptions = {
                'Max FPTS': 'Maximizes total fantasy points (FPTS) without considering salary efficiency.',
                'Max Value': 'Maximizes FPTS per dollar spent, prioritizing players with the best value.',
                'Max Ceiling': 'Maximizes ceiling FPTS potential, targeting players with high upside.',
                'Balanced': 'Balanced approach combining FPTS (60%) and value (40%) for a well-rounded lineup.',
                'Punt Strategy': 'Uses 2-3 high-salary stars (at least 8,000 salary), 2-3 low-salary role players (at most 6,000 salary) with high ceilings, and 2-3 mid-tier players (6,000-8,000 salary) with high ceilings.'
            }
            
            # Display strategy description
            description = strategy_descriptions.get(strategy_name, 'Optimized lineup using selected strategy.')
            st.info(f"💡 **Strategy:** {description}")
            
            # Calculate totals
            if 'Salary' in lineup_df.columns and 'FPTS' in lineup_df.columns:
                # Exclude totals row for calculation
                player_rows = lineup_df[lineup_df['Player'] != 'TOTAL']
                total_salary = player_rows['Salary'].sum()
                total_fpts = player_rows['FPTS'].sum()
                salary_remaining = max_salary - total_salary
                
                # Display metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Salary", f"${total_salary:,}")
                with col2:
                    st.metric("Total FPTS", f"{total_fpts:.2f}")
                with col3:
                    st.metric("Salary Remaining", f"${salary_remaining:,}")
            
            # Display lineup table
            st.markdown(f"### {strategy_name} Lineup")
            
            # Format display dataframe (exclude totals row for display, show separately)
            display_df = lineup_df[lineup_df['Player'] != 'TOTAL'].copy()
            
            # Reorder columns to show Slot, Player, Position, Team, Tip_Time, Opponent, Salary, FPTS
            column_order = ['Slot', 'Player', 'Position', 'Team']
            if 'Tip_Time' in display_df.columns:
                column_order.append('Tip_Time')
            if 'Opponent' in display_df.columns:
                column_order.append('Opponent')
            column_order.extend(['Salary', 'FPTS'])
            
            # Only include columns that exist
            display_cols = [col for col in column_order if col in display_df.columns]
            display_df = display_df[display_cols]
            
            # Format numbers
            if 'Salary' in display_df.columns:
                display_df['Salary'] = display_df['Salary'].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "$0")
            if 'FPTS' in display_df.columns:
                display_df['FPTS'] = display_df['FPTS'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "0.00")
            
            st.dataframe(display_df, width='stretch', hide_index=True)
            
            # Download button
            csv_data = lineup_df.to_csv(index=False)
            strategy_safe = strategy_name.replace(' ', '_').replace('/', '_')
            st.download_button(
                label=f"📥 Download {strategy_name} Lineup CSV",
                data=csv_data,
                file_name=f"optimized_lineup_{strategy_safe}_{selected_date.strftime('%Y%m%d')}.csv",
                mime="text/csv",
                key=f"download_{strategy_safe}_{tab_idx}"
            )
