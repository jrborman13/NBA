import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'new-streamlit-app', 'player-app'))

import streamlit as st
import player_functions as pf
import team_defensive_stats as tds
import prediction_model as pm
import prediction_features as pf_features
import matchup_stats as ms
import vegas_lines as vl
import prediction_tracker as pt
import injury_adjustments as inj
import backtest as bt
import injury_report as ir
import pandas as pd
import nba_api.stats.endpoints
from datetime import datetime, date
import math

st.set_page_config(layout="wide")
st.title("NBA Player Data")

# Cache players dataframe to avoid repeated API calls
@st.cache_data
def get_cached_players_dataframe():
    """Cache players dataframe from PlayerIndex endpoint"""
    return pf.get_players_dataframe()

@st.cache_data
def get_cached_player_list():
    """Cache player list from PlayerIndex endpoint"""
    return pf.get_player_list()

@st.cache_data
def get_player_name_map(player_ids_list, players_df):
    """Cache player names using the players dataframe"""
    return {pid: pf.get_player_name(pid, players_df) for pid in player_ids_list}

# Cache team defensive shooting data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_shooting_data():
    """Cache team shooting data from pbpstats API"""
    try:
        team_stats, opp_team_stats = tds.load_shooting_data()
        return team_stats, opp_team_stats, None
    except Exception as e:
        return None, None, str(e)

# Cache player shooting data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_player_shooting_data():
    """Cache player shooting data from pbpstats API"""
    try:
        player_stats = tds.load_player_shooting_data()
        return player_stats, None
    except Exception as e:
        return None, str(e)

# Function to fetch matchups for a given date
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_matchups_for_date(selected_date):
    """Fetch NBA matchups for a given date from the API"""
    try:
        league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
            league_id='00',
            season='2025-26'
        ).get_data_frames()[0]
        
        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        league_schedule['matchup'] = league_schedule['awayTeam_teamTricode'] + ' @ ' + league_schedule['homeTeam_teamTricode']
        
        # Compare date parts only to handle datetime objects with time components
        date_games = league_schedule[
            league_schedule['dateGame'].dt.date == selected_date
        ]
        
        if len(date_games) > 0:
            matchups = []
            for _, row in date_games.iterrows():
                matchup_str = row['matchup']
                away_team = row['awayTeam_teamTricode']
                home_team = row['homeTeam_teamTricode']
                away_team_id = row['awayTeam_teamId']
                home_team_id = row['homeTeam_teamId']
                matchups.append({
                    'matchup': matchup_str,
                    'away_team': away_team,
                    'home_team': home_team,
                    'away_team_id': away_team_id,
                    'home_team_id': home_team_id
                })
            return matchups, None  # Return matchups and error (None)
        else:
            return [], None  # No games on this date
    except Exception as e:
        return [], str(e)  # Return empty list and error message

# Get cached players dataframe and player list
players_df = get_cached_players_dataframe()

# Get cached player stats (including average minutes) for sorting
@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_cached_player_stats():
    """Get player stats including average minutes for sorting"""
    try:
        import nba_api.stats.endpoints as endpoints
        player_stats = endpoints.LeagueDashPlayerStats(
            season='2025-26',
            league_id_nullable='00',
            per_mode_detailed='PerGame',
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        return player_stats[['PLAYER_ID', 'MIN']].set_index('PLAYER_ID')['MIN'].to_dict()
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        return {}

player_minutes_map = get_cached_player_stats()

# Cached function to fetch injury report for a specific date
@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_cached_injury_report_for_date(selected_date):
    """Fetch and cache injury report for a specific date"""
    try:
        injury_df, status_msg = ir.fetch_injuries_for_date(report_date=selected_date)
        if injury_df is not None and len(injury_df) > 0:
            return injury_df, status_msg, None
        else:
            return pd.DataFrame(), status_msg, "No injuries found"
    except Exception as e:
        return pd.DataFrame(), "", str(e)

# Validate players_df
if players_df is None or len(players_df) == 0:
    st.error("Failed to load players data. Please clear the cache and restart the app.")
    st.stop()

if 'PERSON_ID' not in players_df.columns:
    st.error(f"Players dataframe has incorrect format. Available columns: {list(players_df.columns)}")
    st.error("Please clear the Streamlit cache (☰ → Settings → Clear cache) and restart the app.")
    st.stop()

player_ids_list = get_cached_player_list()
player_name_map = get_player_name_map(player_ids_list, players_df)

# Matchup filter section
col_date, col_matchup = st.columns([0.3, 0.7])

with col_date:
    # Date selector - default to today
    selected_date = st.date_input(
        "Select Date:",
        value=date.today(),
        key="matchup_date"
    )

with col_matchup:
    # Get matchups for selected date
    matchups, matchup_error = get_matchups_for_date(selected_date)
    
    # Show error if API call failed
    if matchup_error:
        st.warning(f"⚠️ Could not fetch matchups: {matchup_error}")
        matchups = []
    
    # Matchup dropdown
    if matchups:
        matchup_options = ["All Matchups"] + [m['matchup'] for m in matchups]
        selected_matchup_str = st.selectbox(
            "Select Matchup:",
            options=matchup_options,
            key="matchup_selector",
            help="Select a matchup to filter players, or 'All Players' to see everyone"
        )
    else:
        selected_matchup_str = "All Players"
        if not matchup_error:  # Only show info if no error (meaning no games on this date)
            st.info("ℹ️ No games scheduled for this date. Showing all players.")

# Fetch injury report for the selected date
# This needs to happen after date selection but before injury section
injury_report_df, injury_report_url, injury_load_error = get_cached_injury_report_for_date(selected_date)

# Clear processed matchups cache when date changes (so injuries get re-processed)
if 'last_injury_date' not in st.session_state or st.session_state.last_injury_date != selected_date:
    st.session_state.last_injury_date = selected_date
    st.session_state.processed_matchups = {}  # Clear cached matchup injury data

# Filter players based on selected matchup
filtered_player_ids_list = player_ids_list.copy()
selected_team_ids = None
matchup_away_team_id = None
matchup_home_team_id = None
matchup_away_team_abbr = None
matchup_home_team_abbr = None

if selected_matchup_str and selected_matchup_str != "All Players" and selected_matchup_str != "All Matchups":
    # Find the selected matchup
    selected_matchup = next((m for m in matchups if m['matchup'] == selected_matchup_str), None)
    
    if selected_matchup:
        # Get team IDs and abbreviations for filtering
        matchup_away_team_id = selected_matchup['away_team_id']
        matchup_home_team_id = selected_matchup['home_team_id']
        matchup_away_team_abbr = selected_matchup['away_team']
        matchup_home_team_abbr = selected_matchup['home_team']
        selected_team_ids = [matchup_away_team_id, matchup_home_team_id]
        
        # Filter players dataframe to only include players from these teams
        if 'TEAM_ID' in players_df.columns:
            # Convert team IDs to match the format in players_df (handle both int and str)
            players_df_team_ids = players_df['TEAM_ID'].astype(int)
            filtered_players_df = players_df[players_df_team_ids.isin(selected_team_ids)].copy()
            
            # Add average minutes column for sorting
            filtered_players_df['AVG_MIN'] = filtered_players_df['PERSON_ID'].apply(
                lambda x: player_minutes_map.get(int(x), 0)
            )
            
            # Sort: Away team first, then Home team; within each team, sort by minutes descending
            away_players = filtered_players_df[filtered_players_df['TEAM_ID'].astype(int) == matchup_away_team_id]
            away_players = away_players.sort_values('AVG_MIN', ascending=False)
            
            home_players = filtered_players_df[filtered_players_df['TEAM_ID'].astype(int) == matchup_home_team_id]
            home_players = home_players.sort_values('AVG_MIN', ascending=False)
            
            # Combine: away team players first, then home team players
            sorted_players_df = pd.concat([away_players, home_players])
            filtered_player_ids_list = sorted_players_df['PERSON_ID'].astype(str).tolist()
            
            # Show info about the matchup
            st.info(f"📊 Showing players from: {selected_matchup['away_team']} @ {selected_matchup['home_team']} (sorted by minutes)")
            
            # ============================================================
            # BEST VALUE PLAYS SECTION
            # ============================================================
            game_date_str_bvp = selected_date.strftime('%Y-%m-%d')
            game_cache_key_bvp = f"{game_date_str_bvp}_{matchup_away_team_abbr}_{matchup_home_team_abbr}"
            
            # Initialize session state for game-level prediction cache
            if 'predictions_game_cache' not in st.session_state:
                st.session_state.predictions_game_cache = {}
            
            with st.expander("🎯 **Best Value Plays** - Find edges across the entire game", expanded=False):
                st.caption("Generate predictions for all players and compare against Underdog lines to find the best value plays")
                
                # Check if we have cached predictions for this game
                cached_game_predictions = st.session_state.predictions_game_cache.get(game_cache_key_bvp)
                
                # Check if we have cached odds for this game
                if 'odds_game_cache' not in st.session_state:
                    st.session_state.odds_game_cache = {}
                cached_game_props = st.session_state.odds_game_cache.get(game_cache_key_bvp)
                
                col_gen, col_status = st.columns([1, 2])
                
                with col_gen:
                    # Only enable generation if we have odds
                    if cached_game_props is None:
                        st.warning("⚠️ Fetch Underdog lines first (scroll down to Predictions tab)")
                        gen_disabled = True
                    elif cached_game_predictions is not None:
                        st.success(f"✅ {len(cached_game_predictions)} players predicted")
                        gen_disabled = True
                    else:
                        gen_disabled = False
                    
                    if st.button("🔮 Generate All Predictions", disabled=gen_disabled, key="gen_all_predictions"):
                        # Get list of players who are OUT or DOUBTFUL from injury report
                        out_player_ids = set()
                        if injury_report_df is not None and len(injury_report_df) > 0:
                            matchup_inj = ir.get_injuries_for_matchup(
                                injury_report_df,
                                matchup_away_team_abbr,
                                matchup_home_team_abbr,
                                players_df
                            )
                            for inj in matchup_inj.get('away', []) + matchup_inj.get('home', []):
                                status_lower = inj.get('status', '').lower()
                                if 'out' in status_lower or 'doubtful' in status_lower:
                                    if inj.get('player_id'):
                                        out_player_ids.add(str(inj['player_id']))
                        
                        # Filter to players with at least some minutes AND not injured
                        players_to_predict = [
                            pid for pid in filtered_player_ids_list 
                            if player_minutes_map.get(int(pid), 0) >= 10  # At least 10 min/game
                            and pid not in out_player_ids  # Skip players who are OUT or DOUBTFUL
                        ]
                        
                        if out_player_ids:
                            st.info(f"⏭️ Skipping {len(out_player_ids)} players who are Out/Doubtful")
                        
                        # Build required data structures
                        player_names_map = {pid: player_name_map.get(pid, f"Player {pid}") for pid in players_to_predict}
                        player_team_ids_map = {}
                        for pid in players_to_predict:
                            player_row = players_df[players_df['PERSON_ID'].astype(str) == pid]
                            if len(player_row) > 0:
                                player_team_ids_map[pid] = int(player_row['TEAM_ID'].iloc[0])
                        
                        progress_bar = st.progress(0, text="Generating predictions...")
                        
                        def update_progress(current, total, player_name):
                            progress_bar.progress(current / total, text=f"({current}/{total}) {player_name}...")
                        
                        # Generate predictions for all players
                        all_predictions = pm.generate_predictions_for_game(
                            player_ids=players_to_predict,
                            player_names=player_names_map,
                            player_team_ids=player_team_ids_map,
                            away_team_id=matchup_away_team_id,
                            home_team_id=matchup_home_team_id,
                            away_team_abbr=matchup_away_team_abbr,
                            home_team_abbr=matchup_home_team_abbr,
                            game_date=game_date_str_bvp,
                            progress_callback=update_progress
                        )
                        
                        progress_bar.empty()
                        
                        # Cache the predictions
                        st.session_state.predictions_game_cache[game_cache_key_bvp] = all_predictions
                        st.success(f"✅ Generated predictions for {len(all_predictions)} players!")
                        st.rerun()
                
                with col_status:
                    if cached_game_predictions is not None and cached_game_props is not None:
                        st.info(f"📊 Predictions: {len(cached_game_predictions)} players | Lines: {len(cached_game_props)} players")
                    
                    # Refresh button
                    if cached_game_predictions is not None:
                        if st.button("🔄 Regenerate Predictions", key="refresh_all_predictions"):
                            del st.session_state.predictions_game_cache[game_cache_key_bvp]
                            st.rerun()
                
                # If we have both predictions and props, show the best value plays
                if cached_game_predictions is not None and cached_game_props is not None:
                    st.markdown("---")
                    
                    # Filters
                    filter_col1, filter_col2, filter_col3 = st.columns(3)
                    
                    with filter_col1:
                        min_edge = st.slider(
                            "Minimum Edge %",
                            min_value=0,
                            max_value=25,
                            value=5,
                            step=1,
                            key="bvp_min_edge"
                        )
                    
                    with filter_col2:
                        confidence_options = st.multiselect(
                            "Confidence Level",
                            options=['high', 'medium', 'low'],
                            default=['high', 'medium'],
                            key="bvp_confidence"
                        )
                    
                    with filter_col3:
                        stat_options = st.multiselect(
                            "Stats",
                            options=['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS'],
                            default=['PTS', 'REB', 'AST', 'PRA', 'RA', 'FPTS'],
                            key="bvp_stats"
                        )
                    
                    # Find best value plays
                    best_plays = pm.find_best_value_plays(
                        all_predictions=cached_game_predictions,
                        all_props=cached_game_props,
                        min_edge_pct=float(min_edge),
                        confidence_filter=confidence_options if confidence_options else ['high', 'medium', 'low'],
                        stat_filter=stat_options if stat_options else ['PTS', 'REB', 'AST', 'PRA']
                    )
                    
                    if best_plays:
                        st.markdown(f"### 🏆 Top {min(len(best_plays), 20)} Value Plays")
                        
                        # Sort by absolute edge descending before taking top 20
                        sorted_plays = sorted(best_plays, key=lambda x: abs(x['edge']), reverse=True)
                        
                        # Create DataFrame for display
                        plays_df = pd.DataFrame(sorted_plays[:20])  # Top 20
                        
                        # Format the display
                        display_df = plays_df[[
                            'player_name', 'team', 'stat', 'prediction', 'line', 
                            'edge', 'edge_pct', 'lean', 'confidence'
                        ]].copy()
                        
                        display_df.columns = [
                            'Player', 'Team', 'Stat', 'Pred', 'Line', 
                            'Edge', 'Edge %', 'Lean', 'Conf'
                        ]
                        
                        # Format columns - all numbers formatted to consistent decimal places
                        display_df['Pred'] = display_df['Pred'].apply(lambda x: f"{x:.1f}")
                        display_df['Line'] = display_df['Line'].apply(lambda x: f"{x:.1f}")
                        display_df['Edge'] = display_df['Edge'].apply(lambda x: f"{abs(x):.1f}")  # Absolute value
                        display_df['Edge %'] = display_df['Edge %'].apply(lambda x: f"{abs(x) / 100:.3f}")
                        display_df['Conf'] = display_df['Conf'].str.capitalize()
                        
                        # Style function for lean column
                        def style_lean_bvp(row):
                            styles = [''] * len(row)
                            lean_idx = display_df.columns.get_loc('Lean')
                            lean_val = row['Lean']
                            
                            if 'Strong Over' in lean_val:
                                styles[lean_idx] = 'background-color: rgba(46, 125, 50, 0.4); font-weight: bold'
                            elif 'Lean Over' in lean_val:
                                styles[lean_idx] = 'background-color: rgba(76, 175, 80, 0.3)'
                            elif 'Strong Under' in lean_val:
                                styles[lean_idx] = 'background-color: rgba(183, 28, 28, 0.4); font-weight: bold'
                            elif 'Lean Under' in lean_val:
                                styles[lean_idx] = 'background-color: rgba(244, 67, 54, 0.3)'
                            
                            # Also color confidence
                            conf_idx = display_df.columns.get_loc('Conf')
                            if row['Conf'] == 'High':
                                styles[conf_idx] = 'background-color: rgba(33, 150, 243, 0.3)'
                            elif row['Conf'] == 'Medium':
                                styles[conf_idx] = 'background-color: rgba(255, 193, 7, 0.3)'
                            
                            return styles
                        
                        styled_plays = display_df.style.apply(style_lean_bvp, axis=1)
                        st.dataframe(styled_plays, width='stretch', hide_index=True)
                        
                        # Summary stats
                        overs = len([p for p in best_plays if 'Over' in p['lean']])
                        unders = len([p for p in best_plays if 'Under' in p['lean']])
                        st.caption(f"📈 {overs} Over plays | 📉 {unders} Under plays | Total: {len(best_plays)} plays found")
                    else:
                        st.info("No plays found matching your filters. Try lowering the minimum edge % or expanding filters.")
                
                elif cached_game_predictions is None and cached_game_props is not None:
                    st.info("👆 Click 'Generate All Predictions' to find value plays")
                elif cached_game_predictions is not None and cached_game_props is None:
                    st.warning("⚠️ Need to fetch Underdog lines first to compare predictions")
            
        else:
            # If TEAM_ID column doesn't exist, try to filter by team abbreviation
            st.warning("⚠️ Could not filter by team ID. Showing all players.")
            filtered_player_ids_list = player_ids_list.copy()

# Set Anthony Edwards (ID: 1630162) as default selected player
default_player_id = '1630162'
default_index = 0
if default_player_id in filtered_player_ids_list:
    default_index = filtered_player_ids_list.index(default_player_id)
elif len(filtered_player_ids_list) > 0:
    # If default player not in filtered list, use first available
    default_index = 0

# Check if there are any players to show
if len(filtered_player_ids_list) == 0:
    st.warning("⚠️ No players found for the selected matchup. Please select a different matchup or date.")
    st.stop()

selected_player_id = st.selectbox(
    "Select Player",
    options=filtered_player_ids_list,
    format_func=lambda x: player_name_map.get(x, f"Player {x}"),
    index=default_index,
    key="player_selector"
)

# Cache player data to avoid repeated API calls
# Version 2: Added PRA and PRA percentile support
@st.cache_data
def get_cached_player_data(player_id, players_df, _cache_version=2):
    """Cache player data to avoid repeated API calls"""
    return pf.get_player_data(player_id, players_df)

# Get player data for selected player (uses PlayerIndex data, no CommonPlayerInfo API call needed)
player_data = get_cached_player_data(selected_player_id, players_df)

with st.container(border=False):
    col1, col2, col3 = st.columns([0.2, 0.2, 0.6], border=1, vertical_alignment='top')
    with col1:
        # st.image(pf.headshot,
        #          width=225)
        st.markdown(f"""
                    <div style="position: relative; display: inline-block; width: 100%; max-width: 230px;">
                        <img src="{player_data['headshot']}" style="width: 100%; height: auto; max-width: 230px; max-height: 175px; object-fit: cover;">
                        <img src="{player_data['logo']}" style="position: absolute; top: -5px; right: -10px; width: 30%; height: auto; max-width: 80px; max-height: 60px; object-fit: contain;">
                    </div>
                """, unsafe_allow_html=True)
    with col2:

        st.subheader(
            f"{player_data['player_info_name']}",
            anchor=False
        )
        # st.badge(
        #     f"**{player_data['player_info_team']} #{player_data['player_info_number']}**",
        #     color='blue'
        # )
        st.markdown(f"""
            <div style="display: inline-block; background-color: {player_data['team_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.875em; font-weight: bold; margin: 0.25rem 0 0.75rem 0;">
                {player_data['player_info_team']} #{player_data['player_info_number']}
            </div>
        """, unsafe_allow_html=True)

        st.write(
            f"**{player_data['player_info_position']}**"
        )
        st.write(
            f"Height: **{player_data['player_info_height']}** | Weight: **{player_data['player_info_weight']} pounds**"
        )

    with col3:
        st.subheader(
            'Season Stats',
            anchor=False
        )
        col5, col6, col7, col8, col9, col10 = st.columns([0.16, 0.16, 0.16, 0.16, 0.16, 0.16], border=0)
        with col5:
            pts_percentile = player_data.get('pts_percentile')
            pts_percentile_str = pf.format_percentile(pts_percentile)
            st.metric(
                label='Points',
                value=player_data['player_pts_pg'],
                delta=f"{pts_percentile_str} %ile" if pts_percentile is not None else None
            )
        with col6:
            reb_percentile = player_data.get('reb_percentile')
            reb_percentile_str = pf.format_percentile(reb_percentile)
            st.metric(
                label='Rebounds',
                value=player_data['player_reb_pg'],
                delta=f"{reb_percentile_str} %ile" if reb_percentile is not None else None
            )
        with col7:
            ast_percentile = player_data.get('ast_percentile')
            ast_percentile_str = pf.format_percentile(ast_percentile)
            st.metric(
                label='Assists',
                value=player_data['player_ast_pg'],
                delta=f"{ast_percentile_str} %ile" if ast_percentile is not None else None
            )
        with col8:
            # Calculate PRA if not in cached data (for backward compatibility)
            if 'player_pra_pg' in player_data:
                player_pra_pg = player_data['player_pra_pg']
            else:
                # Fallback: calculate from existing stats
                player_pra_pg = player_data.get('player_pts_pg', 0.0) + player_data.get('player_reb_pg', 0.0) + player_data.get('player_ast_pg', 0.0)
            
            # Get PRA percentile (should always be available in new cached data)
            pra_percentile = player_data.get('pra_percentile')
            pra_percentile_str = pf.format_percentile(pra_percentile) if pra_percentile is not None else None
            st.metric(
                label='PRA',
                value=f"{player_pra_pg:.1f}",
                delta=f"{pra_percentile_str} %ile" if pra_percentile_str is not None else None
            )
        with col9:
            stl_percentile = player_data.get('stl_percentile')
            stl_percentile_str = pf.format_percentile(stl_percentile)
            st.metric(
                label='Steals',
                value=player_data['player_stl_pg'],
                delta=f"{stl_percentile_str} %ile" if stl_percentile is not None else None
            )
        with col10:
            blk_percentile = player_data.get('blk_percentile')
            blk_percentile_str = pf.format_percentile(blk_percentile)
            st.metric(
                label='Blocks',
                value=player_data['player_blk_pg'],
                delta=f"{blk_percentile_str} %ile" if blk_percentile is not None else None
            )

# with st.container(height=1000, border=True):
#     st.altair_chart(player_data['final_chart'], width='content')

# Create tabs for Current Season, YoY Data, and Predictions
tab1, tab2, tab3 = st.tabs(["Current Season", "YoY Data", "Predictions"])

with tab1:
    # Display averages table with heatmap
    if player_data.get('averages_df') is not None and len(player_data['averages_df']) > 0:
        st.subheader("Averages")
        show_comparison = st.toggle("Show +/- vs Season", value=False, key="show_comparison")
    
        # Create heatmap styling
        averages_df = player_data['averages_df'].copy()
        
        # Ensure all numeric columns are formatted to 1 decimal place
        numeric_cols_to_format = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
        for col in numeric_cols_to_format:
            if col in averages_df.columns:
                averages_df[col] = averages_df[col].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) and str(x) != '' else x)
        
        # Get season row for comparison (last row)
        season_row_idx = len(averages_df) - 1
        season_row = averages_df.iloc[season_row_idx]
        
        # Function to apply heatmap colors
        def style_heatmap(row):
            styles = [''] * len(row)
            
            # Skip Period column (first column) and percentage columns
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            for i, col in enumerate(averages_df.columns):
                if col == 'Period':
                    continue
                
                if col in numeric_cols:
                    try:
                        # Handle string values that might be formatted
                        current_val_str = str(row[col]).replace(',', '')
                        season_val_str = str(season_row[col]).replace(',', '')
                        current_val = float(current_val_str)
                        season_val = float(season_val_str)
                        
                        if current_val > season_val:
                            # Green gradient - better than season
                            diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)  # Cap at 20% difference for max intensity
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < season_val:
                            # Red gradient - worse than season
                            diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            # Gray - same as season
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError):
                        pass
                elif col in pct_cols:
                    try:
                        # Extract percentage value
                        current_str = str(row[col]).replace('%', '')
                        season_str = str(season_row[col]).replace('%', '')
                        current_val = float(current_str)
                        season_val = float(season_str)
                        
                        if current_val > season_val:
                            diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < season_val:
                            diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError):
                        pass
            
            return styles
        
        # Add comparison columns if toggle is on
        if show_comparison:
            # Get season row values
            season_row = averages_df.iloc[-1]
            
            # Create comparison dataframe
            comparison_df = averages_df.copy()
            
            # Add +/- columns for numeric stats
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            # Insert comparison columns after each stat
            new_cols = ['Period']
            for col in averages_df.columns[1:]:  # Skip Period column
                new_cols.append(col)
                if col in numeric_cols:
                    # Add +/- column (already rounded to 1 decimal)
                    comparison_df[f'{col} +/-'] = comparison_df.apply(
                        lambda row: f"{round(float(str(row[col]).replace(',', '')) - float(str(season_row[col]).replace(',', '')), 1):+.1f}" if row.name != season_row_idx else '—',
                        axis=1
                    )
                    new_cols.append(f'{col} +/-')
                elif col in pct_cols:
                    # Add +/- column for percentages
                    comparison_df[f'{col} +/-'] = comparison_df.apply(
                        lambda row: f"{round(float(str(row[col]).replace('%', '')) - float(str(season_row[col]).replace('%', '')), 1):+.1f}%" if row.name != season_row_idx else '—',
                        axis=1
                    )
                    new_cols.append(f'{col} +/-')
            
            # Reorder columns
            comparison_df = comparison_df[new_cols]
            # Update heatmap function to handle comparison columns
            def style_heatmap_with_comparison(row):
                styles = [''] * len(row)
                for i, col in enumerate(comparison_df.columns):
                    if col == 'Period' or '+/-' in col:
                        continue
                    if col in numeric_cols:
                        try:
                            # Handle string values that might be formatted
                            current_val_str = str(row[col]).replace(',', '')
                            season_val_str = str(season_row[col]).replace(',', '')
                            current_val = float(current_val_str)
                            season_val = float(season_val_str)
                            if current_val > season_val:
                                diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                green_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                            elif current_val < season_val:
                                diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                red_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                            else:
                                styles[i] = 'background-color: rgb(240, 240, 240);'
                        except (ValueError, TypeError):
                            pass
                    elif col in pct_cols:
                        try:
                            current_str = str(row[col]).replace('%', '')
                            season_str = str(season_row[col]).replace('%', '')
                            current_val = float(current_str)
                            season_val = float(season_str)
                            if current_val > season_val:
                                diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                green_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                            elif current_val < season_val:
                                diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                red_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                            else:
                                styles[i] = 'background-color: rgb(240, 240, 240);'
                        except (ValueError, TypeError):
                            pass
                return styles
            styled_df = comparison_df.style.apply(style_heatmap_with_comparison, axis=1)
        else:
            styled_df = averages_df.style.apply(style_heatmap, axis=1)
        
        st.dataframe(styled_df, width='stretch', hide_index=True)

        # Display Opponent Defensive Stats (only when a matchup is selected)
        if matchup_away_team_id and matchup_home_team_id:
            # Determine which team is the opponent based on player's team
            player_team_id = player_data.get('team_id')
            if player_team_id:
                player_team_id = int(player_team_id)
                if player_team_id == matchup_away_team_id:
                    opponent_team_id = matchup_home_team_id
                    opponent_label = "Home"
                elif player_team_id == matchup_home_team_id:
                    opponent_team_id = matchup_away_team_id
                    opponent_label = "Away"
                else:
                    opponent_team_id = None
                    opponent_label = None
                
                if opponent_team_id:
                    # Load shooting data
                    team_stats, opp_team_stats, shooting_error = get_cached_shooting_data()
                    
                    if shooting_error:
                        st.warning(f"⚠️ Could not load defensive stats: {shooting_error}")
                    elif opp_team_stats is not None:
                        # Get opponent defensive stats
                        opp_def_stats = tds.get_team_defensive_stats(opponent_team_id, opp_team_stats)
                        
                        if opp_def_stats:
                            st.subheader(f"🛡️ Opponent Defense: {opp_def_stats['team_name']} ({opponent_label})")
                            st.caption("What opponents shoot against this team (lower rank = better defense)")
                            
                            # Create columns for defensive stats
                            def_col1, def_col2, def_col3, def_col4, def_col5 = st.columns(5)
                            
                            with def_col1:
                                rank_color = tds.get_rank_color(opp_def_stats['opp_fg_pct_rank'])
                                st.metric(
                                    label="Opp FG%",
                                    value=f"{opp_def_stats['opp_fg_pct']}%",
                                    delta=f"Rank: {opp_def_stats['opp_fg_pct_rank']}"
                                )
                            
                            with def_col2:
                                st.metric(
                                    label="Opp 2PT%",
                                    value=f"{opp_def_stats['opp_2pt_pct']}%",
                                    delta=f"Rank: {opp_def_stats['opp_2pt_pct_rank']}"
                                )
                            
                            with def_col3:
                                st.metric(
                                    label="Opp 3PT%",
                                    value=f"{opp_def_stats['opp_3pt_pct']}%",
                                    delta=f"Rank: {opp_def_stats['opp_3pt_pct_rank']}"
                                )
                            
                            with def_col4:
                                st.metric(
                                    label="Opp Rim FG%",
                                    value=f"{opp_def_stats['opp_rim_acc']}%",
                                    delta=f"Rank: {opp_def_stats['opp_rim_acc_rank']}"
                                )
                            
                            with def_col5:
                                st.metric(
                                    label="Opp FTA/G",
                                    value=f"{opp_def_stats['opp_fta_pg']}",
                                    delta=f"Rank: {opp_def_stats['opp_fta_rank']}"
                                )
                            
                            # Expandable section for zone shooting details
                            with st.expander("📍 Zone Shooting Defense Details", expanded=True):
                                # Helper function to get background color based on rank
                                # For defensive stats: low rank = good defense (red), high rank = bad defense (green)
                                def get_rank_color(rank, inverse=False):
                                    """
                                    Returns background color based on rank (1-30).
                                    For defensive stats: low rank = good defense = red (bad for player)
                                    high rank = bad defense = green (good for player)
                                    
                                    inverse=True flips the colors (for frequency - high allowed freq is bad defense)
                                    """
                                    try:
                                        rank = int(rank)
                                    except:
                                        return "transparent"
                                    
                                    # Normalize rank to 0-1 scale (1=best, 30=worst)
                                    normalized = (rank - 1) / 29  # 0 = rank 1, 1 = rank 30
                                    
                                    if inverse:
                                        normalized = 1 - normalized
                                    
                                    # Color gradient: Red (good defense) -> Yellow (neutral) -> Green (bad defense)
                                    if normalized < 0.5:
                                        # Red to Yellow (good to neutral defense)
                                        r = 255
                                        g = int(255 * (normalized * 2))  # 0 -> 255
                                        b = 100
                                    else:
                                        # Yellow to Green (neutral to bad defense)
                                        r = int(255 * (1 - (normalized - 0.5) * 2))  # 255 -> 0
                                        g = 255
                                        b = 100
                                    
                                    return f"rgba({r}, {g}, {b}, 0.3)"
                                
                                def styled_stat(label, value, rank, inverse=False):
                                    """Create a styled stat display with colored background based on rank"""
                                    bg_color = get_rank_color(rank, inverse)
                                    return f'''
                                    <div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; margin: 4px 0;">
                                        <span style="font-size: 14px;">{label}: <strong>{value}</strong></span>
                                        <span style="font-size: 12px; color: #666;"> (#{rank})</span>
                                    </div>
                                    '''
                                
                                zone_col1, zone_col2, zone_col3, zone_col4, zone_col5 = st.columns(5)
                                
                                with zone_col1:
                                    st.markdown("**At Rim**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_rim_freq']}%", opp_def_stats['opp_rim_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_rim_acc']}%", opp_def_stats['opp_rim_acc_rank']), unsafe_allow_html=True)
                                
                                with zone_col2:
                                    st.markdown("**Short Mid-Range**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_smr_freq']}%", opp_def_stats['opp_smr_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_smr_acc']}%", opp_def_stats['opp_smr_acc_rank']), unsafe_allow_html=True)
                                
                                with zone_col3:
                                    st.markdown("**Long Mid-Range**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_lmr_freq']}%", opp_def_stats['opp_lmr_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_lmr_acc']}%", opp_def_stats['opp_lmr_acc_rank']), unsafe_allow_html=True)
                                
                                with zone_col4:
                                    st.markdown("**Corner 3**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_c3_freq']}%", opp_def_stats['opp_c3_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_c3_acc']}%", opp_def_stats['opp_c3_acc_rank']), unsafe_allow_html=True)
                                
                                with zone_col5:
                                    st.markdown("**Above Break 3**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_atb3_freq']}%", opp_def_stats['opp_atb3_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_atb3_acc']}%", opp_def_stats['opp_atb3_acc_rank']), unsafe_allow_html=True)
                                
                                # Add legend
                                st.markdown("""
                                <div style="margin-top: 10px; padding: 8px; background-color: #f0f0f0; border-radius: 5px; font-size: 12px;">
                                    <strong>Legend:</strong> 
                                    <span style="background-color: rgba(255, 100, 100, 0.3); padding: 2px 8px; border-radius: 3px;">🔴 Good Defense (tough matchup)</span>
                                    <span style="background-color: rgba(255, 255, 100, 0.3); padding: 2px 8px; border-radius: 3px; margin-left: 10px;">🟡 Average</span>
                                    <span style="background-color: rgba(100, 255, 100, 0.3); padding: 2px 8px; border-radius: 3px; margin-left: 10px;">🟢 Bad Defense (favorable matchup)</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            # Zone Matchup Analysis - Player vs Opponent
                            st.subheader("🎯 Zone Matchup Analysis")
                            st.caption("Color based on opponent defensive FG% rank: 🔴 Rank 1-10 (tough defense) → 🟡 Rank 11-20 (average) → 🟢 Rank 21-30 (weak defense)")
                            
                            # Load player shooting data
                            player_shooting_df, player_shooting_error = get_cached_player_shooting_data()
                            
                            if player_shooting_error:
                                st.warning(f"⚠️ Could not load player shooting data: {player_shooting_error}")
                            elif player_shooting_df is not None:
                                # Get player zone shooting stats
                                player_zones = tds.get_player_zone_shooting(selected_player_id, player_shooting_df)
                                
                                if player_zones:
                                    # Compare player zones to opponent defense
                                    zone_comparisons = tds.compare_player_vs_opponent_zones(player_zones, opp_def_stats)
                                    
                                    if zone_comparisons:
                                        # Display zone matchup cards
                                        matchup_cols = st.columns(5)
                                        zone_keys = ['rim', 'smr', 'lmr', 'c3', 'atb3']
                                        
                                        for i, zone_key in enumerate(zone_keys):
                                            zone_data = zone_comparisons[zone_key]
                                            # Use rank-based coloring instead of difference-based
                                            bg_color = tds.get_matchup_color_by_rank(zone_data['opp_acc_rank'])
                                            
                                            with matchup_cols[i]:
                                                # Create a styled card using markdown
                                                diff_sign = "+" if zone_data['difference'] >= 0 else ""
                                                st.markdown(f"""
                                                <div style="background-color: {bg_color}; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 8px;">
                                                    <div style="font-weight: bold; font-size: 18px; margin-bottom: 10px;">{zone_data['zone_name']}</div>
                                                    <div style="font-size: 15px; color: #444;">Player: <strong>{zone_data['player_pct']}%</strong></div>
                                                    <div style="font-size: 15px; color: #444;">Opp Allows: <strong>{zone_data['opp_allowed_pct']}%</strong> (#{zone_data['opp_acc_rank']})</div>
                                                    <div style="font-size: 22px; font-weight: bold; margin-top: 10px;">{diff_sign}{zone_data['difference']}%</div>
                                                    <div style="font-size: 13px; color: #666;">Freq: {zone_data['player_freq']}% ({zone_data['player_fga']} FGA)</div>
                                                </div>
                                                """, unsafe_allow_html=True)
                                else:
                                    st.info("Could not load player zone shooting data.")
                            
                            st.divider()

        # Display recent game logs table with pagination
        if player_data.get('recent_games_df') is not None and len(player_data['recent_games_df']) > 0:
            st.subheader("Game Logs")
            
            # Get full game logs (not just recent 10)
            full_game_logs = player_data.get('full_game_logs_df', player_data['recent_games_df'])
            total_games = len(full_game_logs)
            
            # Pagination settings
            games_per_page = 10
            total_pages = math.ceil(total_games / games_per_page)
            
            # Page selector
            col_pagination_left, col_pagination_center, col_pagination_right = st.columns([0.3, 0.4, 0.3])
            
            with col_pagination_center:
                if total_pages > 1:
                    current_page = st.selectbox(
                        f"Page (Total: {total_games} games)",
                        options=list(range(1, total_pages + 1)),
                        format_func=lambda x: f"Page {x} of {total_pages}",
                        key="game_logs_page"
                    )
                else:
                    current_page = 1
                    st.caption(f"Showing all {total_games} games")
            
            # Calculate start and end indices
            start_idx = (current_page - 1) * games_per_page
            end_idx = min(start_idx + games_per_page, total_games)
            
            # Get current page of games
            page_games_df = full_game_logs.iloc[start_idx:end_idx].copy()
            
            show_game_comparison = st.toggle("Show vs Season Avg", value=False, key="show_game_comparison")
            
            # Get season averages for comparison
            if show_game_comparison and player_data.get('averages_df') is not None:
                season_avg = player_data['averages_df'].iloc[-1]  # Last row is season
                
                game_logs_df = page_games_df.copy()
                
                # Add comparison columns
                numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
                pct_cols = ['2P%', '3P%', 'FT%']
                
                # Create new columns list with comparison columns
                new_cols = []
                for col in game_logs_df.columns:
                    new_cols.append(col)
                    if col in numeric_cols:
                        # Add vs Avg column
                        try:
                            season_val = float(season_avg[col])
                            game_logs_df[f'{col} vs Avg'] = game_logs_df[col].apply(
                                lambda x: f"{round(float(x) - season_val, 1):+.1f}" if pd.notna(x) else ''
                            )
                            new_cols.append(f'{col} vs Avg')
                        except (ValueError, KeyError):
                            pass
                    elif col in pct_cols:
                        # Add vs Avg column for percentages
                        try:
                            season_str = str(season_avg[col]).replace('%', '')
                            season_val = float(season_str)
                            game_logs_df[f'{col} vs Avg'] = game_logs_df[col].apply(
                                lambda x: f"{round(float(str(x).replace('%', '')) - season_val, 1):+.1f}%" if pd.notna(x) else ''
                            )
                            new_cols.append(f'{col} vs Avg')
                        except (ValueError, KeyError):
                            pass
                
                game_logs_df = game_logs_df[new_cols]
                st.dataframe(game_logs_df, width='stretch', hide_index=True)
            else:
                st.dataframe(
                    page_games_df,
                    width='stretch',
                    hide_index=True
                )
            
            # Show page info at bottom
            if total_pages > 1:
                st.caption(f"Showing games {start_idx + 1}-{end_idx} of {total_games}")
        else:
            st.info("No game logs available for this player.")
        
        # Section: Performance vs Selected Opponent
        if matchup_away_team_id and matchup_home_team_id and player_data.get('full_game_logs_df') is not None:
            # Determine opponent team abbreviation based on player's team
            player_team_id = player_data.get('team_id')
            opponent_abbr = None
            
            if player_team_id:
                player_team_id = int(player_team_id)
                if player_team_id == matchup_away_team_id:
                    opponent_abbr = matchup_home_team_abbr
                elif player_team_id == matchup_home_team_id:
                    opponent_abbr = matchup_away_team_abbr
            
            if opponent_abbr:
                full_game_logs = player_data['full_game_logs_df']
                
                # Filter games against the opponent
                vs_opponent_games = full_game_logs[full_game_logs['Opponent'] == opponent_abbr].copy()
                
                if len(vs_opponent_games) > 0:
                    st.divider()
                    st.subheader(f"📊 Performance vs {opponent_abbr} (2025-26)")
                    
                    # Calculate averages against opponent
                    numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
                    
                    # Calculate averages
                    vs_opp_avgs = {}
                    for col in numeric_cols:
                        if col in vs_opponent_games.columns:
                            vs_opp_avgs[col] = round(vs_opponent_games[col].astype(float).mean(), 1)
                    
                    # Calculate shooting percentages from totals
                    total_2pm = vs_opponent_games['2PM'].astype(float).sum()
                    total_2pa = vs_opponent_games['2PA'].astype(float).sum()
                    total_3pm = vs_opponent_games['3PM'].astype(float).sum()
                    total_3pa = vs_opponent_games['3PA'].astype(float).sum()
                    total_ftm = vs_opponent_games['FTM'].astype(float).sum()
                    total_fta = vs_opponent_games['FTA'].astype(float).sum()
                    
                    vs_opp_avgs['2P%'] = f"{round(total_2pm / total_2pa * 100, 1)}%" if total_2pa > 0 else "0.0%"
                    vs_opp_avgs['3P%'] = f"{round(total_3pm / total_3pa * 100, 1)}%" if total_3pa > 0 else "0.0%"
                    vs_opp_avgs['FT%'] = f"{round(total_ftm / total_fta * 100, 1)}%" if total_fta > 0 else "0.0%"
                    
                    # Get season averages for comparison (from averages_df)
                    season_avgs = {}
                    averages_df = player_data.get('averages_df')
                    if averages_df is not None and len(averages_df) > 0:
                        # Get the "Season" row from averages_df
                        season_row = averages_df[averages_df['Period'] == 'Season']
                        if len(season_row) > 0:
                            season_row = season_row.iloc[0]
                            for col in ['PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK']:
                                if col in season_row:
                                    try:
                                        season_avgs[col] = float(season_row[col])
                                    except:
                                        pass
                            # Get shooting percentages
                            for pct_col in ['3P%', 'FT%']:
                                if pct_col in season_row:
                                    try:
                                        season_avgs[pct_col] = float(str(season_row[pct_col]).replace('%', ''))
                                    except:
                                        pass
                    
                    # Display averages with delta vs season average
                    st.markdown(f"**Averages vs {opponent_abbr}** ({len(vs_opponent_games)} games) - *Delta shows difference from season avg*")
                    
                    avg_cols = st.columns(8)
                    stat_labels = ['PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', '3P%', 'FT%']
                    
                    for i, stat in enumerate(stat_labels):
                        with avg_cols[i]:
                            if stat in vs_opp_avgs:
                                vs_val = vs_opp_avgs[stat]
                                
                                # Calculate delta if we have season average
                                delta_str = None
                                if stat in season_avgs:
                                    if stat in ['3P%', 'FT%']:
                                        # For percentages, parse the string value
                                        try:
                                            vs_pct = float(str(vs_val).replace('%', ''))
                                            season_pct = season_avgs[stat]
                                            delta = round(vs_pct - season_pct, 1)
                                            delta_str = f"{'+' if delta >= 0 else ''}{delta}%"
                                        except:
                                            pass
                                    else:
                                        # For regular stats
                                        delta = round(vs_val - season_avgs[stat], 1)
                                        delta_str = f"{'+' if delta >= 0 else ''}{delta}"
                                
                                st.metric(label=stat, value=vs_val, delta=delta_str)
                    
                    # Display game logs against opponent
                    st.markdown(f"**Game Logs vs {opponent_abbr}**")
                    st.dataframe(vs_opponent_games, width='stretch', hide_index=True)
                else:
                    st.divider()
                    st.info(f"ℹ️ No games played against {opponent_abbr} this season yet.")

with tab2:
    # YoY Data tab
    st.subheader("Historical Season Stats")
    
    # Get YoY data for all seasons
    @st.cache_data
    def get_cached_yoy_data(player_id, players_df):
        """Cache YoY player data to avoid repeated API calls"""
        return pf.get_player_yoy_data(player_id, players_df)
    
    yoy_data = get_cached_yoy_data(selected_player_id, players_df)
    
    if yoy_data and yoy_data.get('averages_df') is not None and len(yoy_data['averages_df']) > 0:
        show_yoy_comparison = st.toggle("Show +/- vs Current Season", value=False, key="show_yoy_comparison")
        
        # Create heatmap styling for YoY data
        yoy_averages_df = yoy_data['averages_df'].copy()
        
        # Ensure all numeric columns are formatted to 1 decimal place
        numeric_cols_to_format = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
        for col in numeric_cols_to_format:
            if col in yoy_averages_df.columns:
                yoy_averages_df[col] = yoy_averages_df[col].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) and str(x) != '' else x)
        
        # Heatmap comparing each season to current season
        def style_yoy_heatmap(row):
            styles = [''] * len(row)
            
            if not show_yoy_comparison or player_data.get('averages_df') is None:
                return styles
            
            current_season_avg = player_data['averages_df'].iloc[-1]  # Last row is current season
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            for i, col in enumerate(yoy_averages_df.columns):
                if col == 'Period' or '+/-' in col:
                    continue
                
                if col in numeric_cols:
                    try:
                        current_val_str = str(row[col]).replace(',', '')
                        current_season_val_str = str(current_season_avg[col]).replace(',', '')
                        current_val = float(current_val_str)
                        current_season_val = float(current_season_val_str)
                        
                        if current_val > current_season_val:
                            diff_pct = ((current_val - current_season_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < current_season_val:
                            diff_pct = ((current_season_val - current_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError, KeyError):
                        pass
                elif col in pct_cols:
                    try:
                        current_str = str(row[col]).replace('%', '')
                        current_season_str = str(current_season_avg[col]).replace('%', '')
                        current_val = float(current_str)
                        current_season_val = float(current_season_str)
                        
                        if current_val > current_season_val:
                            diff_pct = ((current_val - current_season_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < current_season_val:
                            diff_pct = ((current_season_val - current_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError, KeyError):
                        pass
            
            return styles
        
        # Add comparison columns if toggle is on
        if show_yoy_comparison:
            # Get current season averages for comparison
            if player_data.get('averages_df') is not None:
                current_season_avg = player_data['averages_df'].iloc[-1]  # Last row is current season
                
                # Create comparison dataframe
                yoy_comparison_df = yoy_averages_df.copy()
                
                numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
                pct_cols = ['2P%', '3P%', 'FT%']
                
                # Insert comparison columns after each stat
                new_cols = ['Period']
                for col in yoy_averages_df.columns[1:]:  # Skip Period column
                    new_cols.append(col)
                    if col in numeric_cols:
                        # Add +/- column comparing to current season
                        try:
                            yoy_comparison_df[f'{col} +/-'] = yoy_comparison_df.apply(
                                lambda row: f"{round(float(str(row[col]).replace(',', '')) - float(str(current_season_avg[col]).replace(',', '')), 1):+.1f}" if pd.notna(row[col]) and str(row[col]) != '' else '—',
                                axis=1
                            )
                            new_cols.append(f'{col} +/-')
                        except (KeyError, ValueError):
                            pass
                    elif col in pct_cols:
                        # Add +/- column for percentages
                        try:
                            yoy_comparison_df[f'{col} +/-'] = yoy_comparison_df.apply(
                                lambda row: f"{round(float(str(row[col]).replace('%', '')) - float(str(current_season_avg[col]).replace('%', '')), 1):+.1f}%" if pd.notna(row[col]) and str(row[col]) != '' else '—',
                                axis=1
                            )
                            new_cols.append(f'{col} +/-')
                        except (KeyError, ValueError):
                            pass
                
                # Reorder columns
                yoy_comparison_df = yoy_comparison_df[new_cols]
                styled_yoy_df = yoy_comparison_df.style.apply(style_yoy_heatmap, axis=1)
            else:
                styled_yoy_df = yoy_averages_df.style.apply(style_yoy_heatmap, axis=1)
        else:
            styled_yoy_df = yoy_averages_df.style.apply(style_yoy_heatmap, axis=1)
        
        st.dataframe(styled_yoy_df, width='stretch', hide_index=True)
    else:
        st.info("No historical season stats available for this player.")

with tab3:
    # Predictions tab
    st.subheader("🔮 Stat Predictions")
    
    # Check if a matchup is selected
    if matchup_away_team_id and matchup_home_team_id:
        # Determine opponent based on player's team
        player_team_id = player_data.get('team_id')
        opponent_team_id = None
        opponent_abbr = None
        is_home = None
        
        if player_team_id:
            player_team_id = int(player_team_id)
            if player_team_id == matchup_away_team_id:
                opponent_team_id = matchup_home_team_id
                opponent_abbr = matchup_home_team_abbr
                is_home = False
            elif player_team_id == matchup_home_team_id:
                opponent_team_id = matchup_away_team_id
                opponent_abbr = matchup_away_team_abbr
                is_home = True
        
        if opponent_team_id and opponent_abbr:
            st.info(f"📊 Generating predictions for **{player_data['player_info_name']}** vs **{opponent_abbr}** ({'Home' if is_home else 'Away'})")
            
            # === INJURY REPORT SECTION ===
            st.markdown("---")
            with st.expander("🏥 **Injury Report** - Official NBA injury data", expanded=True):
                st.caption("Players marked OUT/Doubtful are auto-selected below")
                
                # Use the pre-fetched injury data from initial load
                # Create a matchup-specific key for session state
                matchup_key = f"{matchup_away_team_abbr}@{matchup_home_team_abbr}"
                
                # Initialize session state for this matchup if needed
                if 'processed_matchups' not in st.session_state:
                    st.session_state.processed_matchups = {}
                
                # Process injuries for this matchup (only once per matchup)
                if matchup_key not in st.session_state.processed_matchups:
                    away_out = []
                    home_out = []
                    all_matchup_injuries = {'away': [], 'home': []}
                    questionable_probable = {'away': [], 'home': []}
                    
                    if injury_report_df is not None and len(injury_report_df) > 0:
                        # Get injuries for this specific matchup
                        matchup_injuries = ir.get_injuries_for_matchup(
                            injury_report_df,
                            matchup_away_team_abbr,
                            matchup_home_team_abbr,
                            players_df
                        )
                        
                        # Separate OUT/DOUBTFUL from QUESTIONABLE/PROBABLE
                        away_questionable = []
                        for injury_item in matchup_injuries['away']:
                            status_lower = injury_item['status'].lower() if injury_item['status'] else ''
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item['player_id']:
                                    away_out.append(injury_item['player_id'])
                                away_questionable.append(injury_item)
                            elif 'questionable' in status_lower or 'probable' in status_lower:
                                away_questionable.append(injury_item)
                        
                        home_questionable = []
                        for injury_item in matchup_injuries['home']:
                            status_lower = injury_item['status'].lower() if injury_item['status'] else ''
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item['player_id']:
                                    home_out.append(injury_item['player_id'])
                                home_questionable.append(injury_item)
                            elif 'questionable' in status_lower or 'probable' in status_lower:
                                home_questionable.append(injury_item)
                        
                        all_matchup_injuries = matchup_injuries
                        questionable_probable = {'away': away_questionable, 'home': home_questionable}
                    
                    # Store processed data for this matchup
                    st.session_state.processed_matchups[matchup_key] = {
                        'away_out': away_out,
                        'home_out': home_out,
                        'all_matchup_injuries': all_matchup_injuries,
                        'questionable_probable': questionable_probable
                    }
                
                # Get the processed data for this matchup
                matchup_data = st.session_state.processed_matchups[matchup_key]
                fetched_away_out = matchup_data['away_out']
                fetched_home_out = matchup_data['home_out']
                all_matchup_injuries = matchup_data['all_matchup_injuries']
                questionable_probable = matchup_data['questionable_probable']
                
                # Show injury report status
                if injury_report_url:
                    st.info(f"📋 {injury_report_url}")
                elif injury_load_error:
                    st.warning(f"⚠️ Could not load injury report: {injury_load_error}")
                
                # Show all found injuries for this matchup
                all_injuries_away = all_matchup_injuries.get('away', [])
                all_injuries_home = all_matchup_injuries.get('home', [])
                
                if all_injuries_away or all_injuries_home:
                    st.success(f"✅ Found {len(all_injuries_away) + len(all_injuries_home)} injuries for this matchup")
                    
                    # Helper function to get status color
                    def get_status_color(status):
                        status_lower = status.lower() if status else ''
                        if 'out' in status_lower:
                            return '#dc3545'  # Red
                        elif 'doubtful' in status_lower:
                            return '#fd7e14'  # Orange
                        elif 'questionable' in status_lower:
                            return '#ffc107'  # Yellow
                        elif 'probable' in status_lower:
                            return '#28a745'  # Green
                        else:
                            return '#6c757d'  # Gray
                    
                    # Helper function to get status sort order (Probable first, Out last)
                    def get_status_order(status):
                        status_lower = status.lower() if status else ''
                        if 'probable' in status_lower:
                            return 0
                        elif 'questionable' in status_lower:
                            return 1
                        elif 'doubtful' in status_lower:
                            return 2
                        elif 'out' in status_lower:
                            return 3
                        else:
                            return 4
                    
                    # Sort injuries by status (Probable first, Out last)
                    sorted_away_injuries = sorted(all_injuries_away, key=lambda x: get_status_order(x.get('status', '')))
                    sorted_home_injuries = sorted(all_injuries_home, key=lambda x: get_status_order(x.get('status', '')))
                    
                    # Display all injuries for both teams with formatted badges
                    inj_col1, inj_col2 = st.columns(2)
                    
                    with inj_col1:
                        st.markdown(f"**{matchup_away_team_abbr}:**")
                        if sorted_away_injuries:
                            for injury_item in sorted_away_injuries:
                                status = injury_item['status']
                                status_color = get_status_color(status)
                                formatted_name = ir.format_player_name(injury_item['player_name'])
                                formatted_reason = ir.format_injury_reason(injury_item.get('reason', ''))
                                player_id = injury_item.get('player_id', '')
                                headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" if player_id else ""
                                st.markdown(f"""
                                    <div style="display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #eee;">
                                        <img src="{headshot_url}" style="width: 75px; height: 55px; object-fit: cover; border-radius: 4px; background-color: #f0f0f0;" onerror="this.style.display='none'">
                                        <div style="flex: 1;">
                                            <span style="font-weight: bold;">{formatted_name}</span>
                                            <span style="background-color: {status_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px; margin-left: 8px;">{status}</span>
                                            <br><span style="font-size: 13px; color: #666;">{formatted_reason}</span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("No injuries reported")
                    
                    with inj_col2:
                        st.markdown(f"**{matchup_home_team_abbr}:**")
                        if sorted_home_injuries:
                            for injury_item in sorted_home_injuries:
                                status = injury_item['status']
                                status_color = get_status_color(status)
                                formatted_name = ir.format_player_name(injury_item['player_name'])
                                formatted_reason = ir.format_injury_reason(injury_item.get('reason', ''))
                                player_id = injury_item.get('player_id', '')
                                headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" if player_id else ""
                                st.markdown(f"""
                                    <div style="display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #eee;">
                                        <img src="{headshot_url}" style="width: 75px; height: 55px; object-fit: cover; border-radius: 4px; background-color: #f0f0f0;" onerror="this.style.display='none'">
                                        <div style="flex: 1;">
                                            <span style="font-weight: bold;">{formatted_name}</span>
                                            <span style="background-color: {status_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px; margin-left: 8px;">{status}</span>
                                            <br><span style="font-size: 13px; color: #666;">{formatted_reason}</span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.info("No injuries reported")
                    
                    # Show which players are being auto-selected as OUT
                    if fetched_away_out or fetched_home_out:
                        st.caption(f"🔴 Only players marked OUT or Doubtful are auto-selected below")
                else:
                    st.warning(f"⚠️ No injuries found for {matchup_away_team_abbr}@{matchup_home_team_abbr}")
                    
                    # Show debug info
                    with st.expander("🔍 Debug: Show all injuries from report"):
                        if injury_report_df is not None and len(injury_report_df) > 0:
                            st.write("All matchups in report:")
                            unique_matchups = injury_report_df['matchup'].unique()
                            for m in unique_matchups:
                                st.write(f"  • {m}")
                            st.dataframe(injury_report_df, width='stretch')
                        else:
                            st.write("No data available")
                
                st.divider()
                
                # Get players from both teams for the injury selection
                player_team_abbr = matchup_away_team_abbr if is_home == False else matchup_home_team_abbr
                
                # Filter players by team
                away_team_players_df = players_df[players_df['TEAM_ID'].astype(int) == matchup_away_team_id].copy()
                home_team_players_df = players_df[players_df['TEAM_ID'].astype(int) == matchup_home_team_id].copy()
                
                # Add minutes for sorting
                away_team_players_df['AVG_MIN'] = away_team_players_df['PERSON_ID'].apply(
                    lambda x: player_minutes_map.get(int(x), 0)
                )
                home_team_players_df['AVG_MIN'] = home_team_players_df['PERSON_ID'].apply(
                    lambda x: player_minutes_map.get(int(x), 0)
                )
                
                # Sort by minutes and get top players (likely to matter most)
                away_team_players_df = away_team_players_df.sort_values('AVG_MIN', ascending=False)
                home_team_players_df = home_team_players_df.sort_values('AVG_MIN', ascending=False)
                
                # Get player IDs and create name maps
                away_player_ids = away_team_players_df['PERSON_ID'].astype(str).tolist()
                home_player_ids = home_team_players_df['PERSON_ID'].astype(str).tolist()
                
                def format_player_with_mins(pid):
                    name = player_name_map.get(pid, f"Player {pid}")
                    mins = player_minutes_map.get(int(pid), 0)
                    return f"{name} ({mins:.1f} mpg)"
                
                st.markdown("**Select Players Out (adjust manually if needed):**")
                inj_col1, inj_col2 = st.columns(2)
                
                with inj_col1:
                    st.markdown(f"**{matchup_away_team_abbr} Players Out:**")
                    # Use fetched data as default if available
                    default_away_out = [p for p in fetched_away_out if p in away_player_ids]
                    away_players_out = st.multiselect(
                        "Away team injuries",
                        options=away_player_ids,
                        default=default_away_out,
                        format_func=format_player_with_mins,
                        key=f"away_injuries_{matchup_key}",
                        label_visibility="collapsed"
                    )
                
                with inj_col2:
                    st.markdown(f"**{matchup_home_team_abbr} Players Out:**")
                    # Use fetched data as default if available
                    default_home_out = [p for p in fetched_home_out if p in home_player_ids]
                    home_players_out = st.multiselect(
                        "Home team injuries",
                        options=home_player_ids,
                        default=default_home_out,
                        format_func=format_player_with_mins,
                        key=f"home_injuries_{matchup_key}",
                        label_visibility="collapsed"
                    )
                
                # Determine which are teammates vs opponents for the selected player
                if is_home:
                    teammates_out = home_players_out
                    opponents_out = away_players_out
                else:
                    teammates_out = away_players_out
                    opponents_out = home_players_out
                
                # Remove the selected player from teammates_out if somehow selected
                teammates_out = [p for p in teammates_out if p != selected_player_id]
            
            # Calculate injury adjustments if any players are out
            injury_adjustments = None
            if teammates_out or opponents_out:
                injury_adjustments = inj.calculate_injury_adjustments(
                    player_id=selected_player_id,
                    player_team_id=int(player_team_id),
                    opponent_team_id=opponent_team_id,
                    teammates_out=teammates_out,
                    opponents_out=opponents_out,
                    player_minutes_map=player_minutes_map,
                    players_df=players_df
                )
                
                # Show injury impact summary
                if injury_adjustments.get('factors'):
                    st.warning(f"⚠️ **Injury Adjustments:** {' | '.join(injury_adjustments['factors'])}")
            
            # Cache predictions
            @st.cache_data(ttl=1800)  # Cache for 30 minutes
            def get_cached_predictions(player_id, pl_team_id, opp_team_id, opp_abbr, game_dt, home):
                try:
                    return pm.generate_prediction(
                        player_id=player_id,
                        player_team_id=pl_team_id,
                        opponent_team_id=opp_team_id,
                        opponent_abbr=opp_abbr,
                        game_date=game_dt,
                        is_home=home
                    ), None
                except Exception as e:
                    return None, str(e)
            
            # Generate predictions
            game_date_str = selected_date.strftime('%Y-%m-%d')
            predictions, pred_error = get_cached_predictions(
                selected_player_id,
                int(player_team_id),  # Player's team ID for rest calculation
                opponent_team_id, 
                opponent_abbr, 
                game_date_str, 
                is_home
            )
            
            if pred_error:
                st.error(f"⚠️ Could not generate predictions: {pred_error}")
            elif predictions:
                # Apply injury adjustments if any
                adjusted_predictions = {}
                for stat, pred in predictions.items():
                    if injury_adjustments and stat in injury_adjustments:
                        adjusted_value = inj.apply_injury_adjustments(
                            pred.value, stat, injury_adjustments
                        )
                        adjusted_predictions[stat] = adjusted_value
                    else:
                        adjusted_predictions[stat] = pred.value
                
                # Recalculate PRA if individual stats were adjusted
                if injury_adjustments:
                    adjusted_predictions['PRA'] = round(
                        adjusted_predictions.get('PTS', predictions['PTS'].value) +
                        adjusted_predictions.get('REB', predictions['REB'].value) +
                        adjusted_predictions.get('AST', predictions['AST'].value), 1
                    )
                
                # Display main predictions in columns
                has_injury_adj = injury_adjustments and injury_adjustments.get('factors')
                if has_injury_adj:
                    st.markdown("### Predicted Statline (Injury Adjusted)")
                else:
                    st.markdown("### Predicted Statline")
                
                pred_cols = st.columns(10)
                stat_order = ['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS']
                stat_labels = {'PTS': 'Points', 'REB': 'Rebounds', 'AST': 'Assists', 
                              'PRA': 'PRA', 'RA': 'R+A', 'STL': 'Steals', 'BLK': 'Blocks', 
                              'FG3M': '3PM', 'FTM': 'FTM', 'FPTS': 'Fantasy'}
                
                for i, stat in enumerate(stat_order):
                    if stat in predictions:
                        pred = predictions[stat]
                        display_value = adjusted_predictions.get(stat, pred.value)
                        
                        with pred_cols[i]:
                            # Color code by confidence
                            if pred.confidence == 'high':
                                conf_color = '🟢'
                            elif pred.confidence == 'medium':
                                conf_color = '🟡'
                            else:
                                conf_color = '🔴'
                            
                            # Show delta from base prediction if injury adjusted
                            if has_injury_adj and display_value != pred.value:
                                delta_val = round(display_value - pred.value, 1)
                                delta_str = f"{'+' if delta_val >= 0 else ''}{delta_val} (inj)"
                                st.metric(
                                    label=stat_labels.get(stat, stat),
                                    value=display_value,
                                    delta=delta_str
                                )
                            else:
                                st.metric(
                                    label=stat_labels.get(stat, stat),
                                    value=display_value,
                                    delta=f"{conf_color} {pred.confidence}"
                                )
                
                # Prediction breakdown
                with st.expander("📈 Prediction Breakdown"):
                    # Show breakdown for each stat
                    breakdown_cols = st.columns(3)
                    
                    for i, stat in enumerate(['PTS', 'REB', 'AST']):
                        if stat in predictions:
                            pred = predictions[stat]
                            with breakdown_cols[i]:
                                st.markdown(f"**{stat_labels.get(stat, stat)}**")
                                st.write(f"Season Avg: {pred.breakdown.get('season_avg', 'N/A')}")
                                st.write(f"L5 Avg: {pred.breakdown.get('L5_avg', 'N/A')}")
                                st.write(f"Weighted Avg: {pred.breakdown.get('weighted_avg', 'N/A')}")
                                if 'vs_opponent' in pred.breakdown:
                                    st.write(f"vs {opponent_abbr}: {pred.breakdown['vs_opponent']}")
                                st.write(f"**Final: {pred.value}**")
                
                # Factors affecting prediction
                with st.expander("🎯 Factors Considered"):
                    pts_pred = predictions.get('PTS')
                    if pts_pred and pts_pred.factors:
                        for factor, description in pts_pred.factors.items():
                            st.write(f"• **{factor.replace('_', ' ').title()}**: {description}")
                
                # Matchup-specific insights
                with st.expander("🏀 Matchup Analysis", expanded=True):
                    try:
                        # Get matchup features
                        matchup_data = ms.get_matchup_prediction_features(
                            selected_player_id,
                            opponent_team_id
                        )
                        
                        player_breakdown = matchup_data['player_scoring_breakdown']
                        opp_vuln = matchup_data['opponent_vulnerabilities']
                        league_avgs = matchup_data['league_misc_averages']
                        adjustments = matchup_data['matchup_adjustments']
                        
                        # Display matchup insights
                        insight_text = ms.format_matchup_insight(player_breakdown, opp_vuln, adjustments)
                        st.markdown(insight_text)
                        
                        st.markdown("---")
                        
                        # Player scoring breakdown table
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Player Scoring Breakdown (Per Game)**")
                            breakdown_data = pd.DataFrame([
                                {"Category": "Points in Paint", "Player": player_breakdown['pts_paint'], "Player Rank": player_breakdown['pts_paint_rank']},
                                {"Category": "Fast Break Pts", "Player": player_breakdown['pts_fb'], "Player Rank": player_breakdown['pts_fb_rank']},
                                {"Category": "2nd Chance Pts", "Player": player_breakdown['pts_2nd_chance'], "Player Rank": player_breakdown['pts_2nd_chance_rank']},
                                {"Category": "Pts Off TOV", "Player": player_breakdown['pts_off_tov'], "Player Rank": player_breakdown['pts_off_tov_rank']},
                            ])
                            st.dataframe(breakdown_data, hide_index=True, width='stretch')
                        
                        with col2:
                            st.markdown(f"**{opponent_abbr} Defense (What They Allow)**")
                            defense_data = pd.DataFrame([
                                {"Category": "Points in Paint", "Allowed": opp_vuln['opp_pts_paint_allowed'], "Rank": opp_vuln['opp_pts_paint_rank'], "Lg Avg": league_avgs['pts_paint']},
                                {"Category": "Fast Break Pts", "Allowed": opp_vuln['opp_pts_fb_allowed'], "Rank": opp_vuln['opp_pts_fb_rank'], "Lg Avg": league_avgs['pts_fb']},
                                {"Category": "2nd Chance Pts", "Allowed": opp_vuln['opp_pts_2nd_chance_allowed'], "Rank": opp_vuln['opp_pts_2nd_chance_rank'], "Lg Avg": league_avgs['pts_2nd_chance']},
                                {"Category": "Pts Off TOV", "Allowed": opp_vuln['opp_pts_off_tov_allowed'], "Rank": opp_vuln['opp_pts_off_tov_rank'], "Lg Avg": league_avgs['pts_off_tov']},
                            ])
                            st.dataframe(defense_data, hide_index=True, width='stretch')
                        
                        # Matchup adjustments
                        st.markdown("**Matchup-Adjusted Projections**")
                        adj_data = pd.DataFrame([
                            {"Category": "Paint Scoring", "Base": player_breakdown['pts_paint'], "Adjusted": adjustments['pts_paint_adjusted'], "Impact": f"+{round(adjustments['pts_paint_adjusted'] - player_breakdown['pts_paint'], 1)}" if adjustments['pts_paint_adjusted'] > player_breakdown['pts_paint'] else f"{round(adjustments['pts_paint_adjusted'] - player_breakdown['pts_paint'], 1)}"},
                            {"Category": "Fast Break", "Base": player_breakdown['pts_fb'], "Adjusted": adjustments['pts_fb_adjusted'], "Impact": f"+{round(adjustments['pts_fb_adjusted'] - player_breakdown['pts_fb'], 1)}" if adjustments['pts_fb_adjusted'] > player_breakdown['pts_fb'] else f"{round(adjustments['pts_fb_adjusted'] - player_breakdown['pts_fb'], 1)}"},
                            {"Category": "2nd Chance", "Base": player_breakdown['pts_2nd_chance'], "Adjusted": adjustments['pts_2nd_chance_adjusted'], "Impact": f"+{round(adjustments['pts_2nd_chance_adjusted'] - player_breakdown['pts_2nd_chance'], 1)}" if adjustments['pts_2nd_chance_adjusted'] > player_breakdown['pts_2nd_chance'] else f"{round(adjustments['pts_2nd_chance_adjusted'] - player_breakdown['pts_2nd_chance'], 1)}"},
                        ])
                        st.dataframe(adj_data, hide_index=True, width='stretch')
                        
                        overall_factor = adjustments.get('overall_pts_factor', 1.0)
                        if overall_factor != 1.0:
                            factor_pct = round((overall_factor - 1) * 100, 1)
                            if factor_pct > 0:
                                st.success(f"📈 **Overall Matchup Factor: +{factor_pct}%** scoring opportunity in this matchup")
                            else:
                                st.warning(f"📉 **Overall Matchup Factor: {factor_pct}%** tougher matchup expected")
                        else:
                            st.info("📊 **Neutral Matchup**: No significant scoring adjustments")
                            
                    except Exception as e:
                        st.warning(f"Could not load matchup analysis: {e}")
                
                # Comparison table
                st.markdown("### Season Averages vs Prediction")
                
                comparison_data = []
                rolling_avgs = player_data.get('averages_df')
                game_logs = player_data.get('recent_games_df')  # Get game logs for computed stats
                
                if rolling_avgs is not None and len(rolling_avgs) > 0:
                    season_row = rolling_avgs.iloc[-1]  # Season averages
                    
                    # Map prediction stat names to averages_df column names
                    stat_to_col = {'FG3M': '3PM'}  # averages_df uses '3PM', predictions use 'FG3M'
                    
                    # Calculate computed season averages from game logs if available
                    computed_season_avgs = {}
                    if game_logs is not None and len(game_logs) > 0:
                        # R+A (Rebounds + Assists)
                        if 'REB' in game_logs.columns and 'AST' in game_logs.columns:
                            ra_avg = game_logs['REB'].mean() + game_logs['AST'].mean()
                            computed_season_avgs['RA'] = ra_avg
                        
                        # FPTS (Fantasy Points) using Underdog formula: PTS×1 + REB×1.2 + AST×1.5 + STL×3 + BLK×3 - TOV×1
                        fpts_cols = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV']
                        if all(col in game_logs.columns for col in fpts_cols):
                            game_logs_copy = game_logs.copy()
                            game_logs_copy['FPTS'] = (
                                game_logs_copy['PTS'] * 1.0 +
                                game_logs_copy['REB'] * 1.2 +
                                game_logs_copy['AST'] * 1.5 +
                                game_logs_copy['STL'] * 3.0 +
                                game_logs_copy['BLK'] * 3.0 -
                                game_logs_copy['TOV'] * 1.0
                            )
                            computed_season_avgs['FPTS'] = game_logs_copy['FPTS'].mean()
                    
                    for stat in ['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS']:
                        if stat in predictions:
                            pred = predictions[stat]
                            col_name = stat_to_col.get(stat, stat)  # Use mapped name if exists
                            
                            # First check computed averages for RA and FPTS
                            if stat in computed_season_avgs:
                                season_val_float = computed_season_avgs[stat]
                            else:
                                season_val = season_row.get(col_name)
                                try:
                                    season_val_float = float(str(season_val).replace(',', '')) if season_val is not None else None
                                except:
                                    season_val_float = None
                            
                            try:
                                if season_val_float is not None:
                                    diff = round(pred.value - season_val_float, 1)
                                    diff_str = f"+{diff}" if diff >= 0 else str(diff)
                                    season_val_display = round(season_val_float, 1)
                                else:
                                    diff_str = "-"
                                    season_val_display = None
                            except:
                                diff_str = "-"
                                season_val_display = None
                            
                            comparison_data.append({
                                'Stat': stat_labels.get(stat, stat),
                                'Season Avg': season_val_display,
                                'Prediction': round(pred.value, 1),
                                'Diff': diff_str,
                                'Confidence': pred.confidence.capitalize()
                            })
                    
                    if comparison_data:
                        comparison_df = pd.DataFrame(comparison_data)
                        st.dataframe(comparison_df, width='stretch', hide_index=True)
                
                # Vegas Lines Comparison Section
                st.markdown("### 📊 Vegas Lines Comparison")
                
                # Get existing lines for this player/game
                existing_lines = vl.get_player_lines(selected_player_id, game_date_str)
                
                # === UNDERDOG API INTEGRATION ===
                with st.expander("🎰 **Fetch Underdog Lines** (The Odds API)", expanded=True):
                    st.caption("Fetch live player props from Underdog Fantasy via The Odds API")
                    
                    # Initialize session state for API data (GAME-LEVEL CACHE)
                    if 'odds_game_cache' not in st.session_state:
                        st.session_state.odds_game_cache = {}  # game_key -> all_props dict
                    if 'odds_api_credits' not in st.session_state:
                        st.session_state.odds_api_credits = None
                    
                    # Create cache key for this GAME (not player-specific)
                    game_cache_key = f"{game_date_str}_{matchup_away_team_abbr}_{matchup_home_team_abbr}"
                    
                    # Check if we have cached data for this GAME
                    cached_game_props = st.session_state.odds_game_cache.get(game_cache_key)
                    
                    # Get player-specific props from cache if available
                    if cached_game_props is not None:
                        cached_props = vl.get_player_props_from_cached(cached_game_props, player_data['player_info_name'])
                        players_with_props = len(cached_game_props)
                    else:
                        cached_props = None
                        players_with_props = 0
                    
                    # Dry-run preview section
                    col_preview, col_fetch = st.columns([2, 1])
                    
                    with col_preview:
                        if st.button("🔍 Preview Request (Free)", key="preview_odds_request"):
                            with st.spinner("Checking for available events..."):
                                preview = vl.preview_odds_request(
                                    matchup_home_team_abbr,
                                    matchup_away_team_abbr,
                                    game_date_str
                                )
                                
                                if preview.get('error'):
                                    st.error(f"❌ {preview['error']}")
                                    if preview.get('events_on_date'):
                                        st.info(f"Events found on {game_date_str}: {', '.join(preview['events_on_date'])}")
                                else:
                                    st.success(f"✅ Event found: {preview['event_details']['away_team']} @ {preview['event_details']['home_team']}")
                                    
                                    with st.container():
                                        st.markdown("**Request Details (Dry Run)**")
                                        st.code(f"""
Event ID: {preview['event_id']}
Region: {preview['request_info']['region']}
Bookmaker: {preview['request_info']['bookmaker']}
Markets: {', '.join(preview['request_info']['markets_requested'])}
Estimated Cost: {preview['estimated_cost']}
""", language=None)
                    
                    with col_fetch:
                        fetch_disabled = cached_game_props is not None
                        if fetch_disabled:
                            fetch_label = f"✅ Game Cached ({players_with_props} players)"
                        else:
                            fetch_label = "📥 Fetch Lines (1 Credit)"
                        
                        if st.button(fetch_label, key="fetch_odds", disabled=fetch_disabled):
                            with st.spinner("Fetching ALL player props for this game..."):
                                # Fetch ALL props for the game (costs 1 credit)
                                all_props, api_response = vl.fetch_all_props_for_game(
                                    matchup_home_team_abbr,
                                    matchup_away_team_abbr,
                                    game_date_str
                                )
                                
                                if api_response.success:
                                    # Cache at GAME level
                                    st.session_state.odds_game_cache[game_cache_key] = all_props
                                    st.session_state.odds_api_credits = api_response.credits_remaining
                                    
                                    if all_props:
                                        st.success(f"✅ Cached props for {len(all_props)} players! Switch players freely - no additional credits needed.")
                                    else:
                                        st.warning("⚠️ No props found for this game on Underdog")
                                    
                                    st.rerun()
                                else:
                                    st.error(f"❌ API Error: {api_response.error}")
                                    if api_response.credits_remaining is not None:
                                        st.session_state.odds_api_credits = api_response.credits_remaining
                    
                    # Clear cache button
                    if cached_game_props is not None:
                        if st.button("🔄 Refresh Game Lines", key="refresh_odds"):
                            del st.session_state.odds_game_cache[game_cache_key]
                            st.rerun()
                    
                    # Show credit info and cache status
                    if st.session_state.odds_api_credits is not None:
                        st.info(f"💳 API Credits Remaining: **{st.session_state.odds_api_credits}** / 500 (monthly)")
                    
                    if cached_game_props is not None and cached_props:
                        st.success(f"📊 Found {len(cached_props)} props for **{player_data['player_info_name']}** from cached game data")
                    elif cached_game_props is not None and not cached_props:
                        st.warning(f"⚠️ No props available for {player_data['player_info_name']} on Underdog (game data cached)")
                    
                    # Display fetched props
                    if cached_props:
                        st.markdown("**Underdog Lines:**")
                        
                        # Build comparison table with fetched props - USE INJURY-ADJUSTED PREDICTIONS
                        api_comparison_data = []
                        for stat in ['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS']:
                            if stat in predictions and stat in cached_props:
                                pred = predictions[stat]
                                prop = cached_props[stat]
                                # Use injury-adjusted value if available
                                adjusted_value = adjusted_predictions.get(stat, pred.value)
                                comparison = vl.compare_prediction_to_line(adjusted_value, prop.line)
                                
                                api_comparison_data.append({
                                    'Stat': stat_labels.get(stat, stat),
                                    'Prediction': round(adjusted_value, 1),  # Show adjusted prediction
                                    'Underdog Line': round(prop.line, 1),
                                    'Edge': round(comparison['diff'], 1),
                                    'Edge %': round(abs(comparison['diff_pct']) / 100, 3),
                                    'Lean': comparison['lean']
                                })
                                
                                # Also save to existing lines for persistence
                                vl.set_player_line(
                                    selected_player_id,
                                    game_date_str,
                                    stat,
                                    prop.line,
                                    prop.over_odds,
                                    prop.under_odds,
                                    source='underdog'
                                )
                        
                        if api_comparison_data:
                            # Sort by absolute Edge descending
                            api_comparison_data.sort(key=lambda x: abs(x['Edge']), reverse=True)
                            api_df = pd.DataFrame(api_comparison_data)
                            
                            # Style the lean column
                            def style_api_lean(val):
                                if 'Strong Over' in val:
                                    return 'background-color: rgba(46, 125, 50, 0.4); font-weight: bold'
                                elif 'Lean Over' in val:
                                    return 'background-color: rgba(76, 175, 80, 0.3)'
                                elif 'Strong Under' in val:
                                    return 'background-color: rgba(183, 28, 28, 0.4); font-weight: bold'
                                elif 'Lean Under' in val:
                                    return 'background-color: rgba(244, 67, 54, 0.3)'
                                else:
                                    return 'background-color: rgba(158, 158, 158, 0.2)'
                            
                            def style_edge(val):
                                try:
                                    num = float(val) if not isinstance(val, (int, float)) else val
                                    if num >= 1.5:
                                        return 'color: #2E7D32; font-weight: bold'
                                    elif num >= 0.5:
                                        return 'color: #4CAF50'
                                    elif num <= -1.5:
                                        return 'color: #B71C1C; font-weight: bold'
                                    elif num <= -0.5:
                                        return 'color: #F44336'
                                    return ''
                                except:
                                    return ''
                            
                            styled_api_df = api_df.style.applymap(style_api_lean, subset=['Lean']).applymap(style_edge, subset=['Edge'])
                            st.dataframe(styled_api_df, width='stretch', hide_index=True)
                            
                            # Summary callout for best plays
                            strong_plays = [row for row in api_comparison_data if 'Strong' in row['Lean']]
                            if strong_plays:
                                st.markdown("**🎯 Best Plays:**")
                                for play in strong_plays:
                                    direction = "OVER" if "Over" in play['Lean'] else "UNDER"
                                    st.markdown(f"- **{play['Stat']}** {direction} {play['Underdog Line']} (Pred: {play['Prediction']}, Edge: {play['Edge']})")
                        else:
                            st.info("No matching props found between predictions and Underdog lines.")
                    elif cached_props is not None and len(cached_props) == 0:
                        st.warning(f"No Underdog props available for {player_data['player_info_name']} in this game.")
                
                st.markdown("---")
                
                # Log prediction button
                st.markdown("### 📝 Track This Prediction")
                if st.button("📊 Log Prediction for Tracking", key="log_prediction"):
                    try:
                        # Get features for logging
                        player_features = pf_features.get_all_prediction_features(
                            player_id=selected_player_id,
                            opponent_team_id=opponent_team_id,
                            opponent_abbr=opponent_abbr,
                            game_date=game_date_str,
                            is_home=is_home
                        )
                        
                        for stat in ['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS']:
                            if stat in predictions:
                                line_val = existing_lines.get(stat, vl.PropLine(stat, 0, -110, -110, 'manual')).line if stat in existing_lines else None
                                
                                record = pt.create_prediction_record_from_dict(
                                    player_id=selected_player_id,
                                    player_name=player_data['player_info_name'],
                                    opponent_abbr=opponent_abbr,
                                    game_date=game_date_str,
                                    stat=stat,
                                    prediction_dict=predictions[stat],
                                    features_dict=player_features,
                                    vegas_line=line_val if line_val and line_val > 0 else None
                                )
                                pt.log_prediction(record)
                        
                        st.success("✅ Predictions logged! You can update with actual results after the game.")
                    except Exception as e:
                        st.error(f"Error logging prediction: {e}")
                
                # Show accuracy history
                with st.expander("📈 Prediction Accuracy History"):
                    accuracy_metrics = pt.calculate_accuracy_metrics()
                    
                    if accuracy_metrics:
                        st.markdown("**Overall Accuracy by Stat**")
                        
                        acc_data = []
                        for stat, metrics in accuracy_metrics.items():
                            acc_data.append({
                                'Stat': stat,
                                'Predictions': metrics['count'],
                                'MAE': metrics['mae'],
                                'Within 10%': f"{metrics['within_10_pct']}%",
                                'Within 20%': f"{metrics['within_20_pct']}%",
                                'vs Line': f"{metrics['vs_line_accuracy']}%" if metrics['vs_line_accuracy'] else "N/A"
                            })
                        
                        if acc_data:
                            st.dataframe(pd.DataFrame(acc_data), width='stretch', hide_index=True)
                        
                        # By confidence
                        by_conf = pt.calculate_accuracy_by_confidence()
                        if by_conf:
                            st.markdown("**Accuracy by Confidence Level**")
                            conf_data = []
                            for conf, metrics in by_conf.items():
                                conf_data.append({
                                    'Confidence': conf.capitalize(),
                                    'Count': metrics['count'],
                                    'MAE': metrics['mae'],
                                    'Within 10%': f"{metrics['within_10_pct']}%"
                                })
                            st.dataframe(pd.DataFrame(conf_data), width='stretch', hide_index=True)
                    else:
                        st.info("No prediction history yet. Log predictions and update with actual results to track accuracy.")
                
                # Model Backtest Section
                # Initialize backtest session state
                if 'backtest_results' not in st.session_state:
                    st.session_state.backtest_results = None
                if 'backtest_player_id' not in st.session_state:
                    st.session_state.backtest_player_id = None
                
                with st.expander("📊 Model Backtest - Test Prediction Accuracy", expanded=True):
                    st.markdown("Test how well the prediction model performs against actual game results.")
                    
                    # Use form to prevent reruns on slider change
                    with st.form(key="backtest_form"):
                        col_bt1, col_bt2 = st.columns(2)
                        with col_bt1:
                            n_games_backtest = st.slider("Games to test", min_value=3, max_value=20, value=10)
                        with col_bt2:
                            skip_recent = st.slider("Skip most recent games", min_value=0, max_value=5, value=0, 
                                                   help="Skip recent games for true out-of-sample testing")
                        
                        run_backtest = st.form_submit_button("🧪 Run Backtest")
                    
                    # Clear results if player changed
                    if st.session_state.backtest_player_id != selected_player_id:
                        st.session_state.backtest_results = None
                        st.session_state.backtest_player_id = selected_player_id
                    
                    if run_backtest:
                        with st.spinner(f"Testing predictions on last {n_games_backtest} games..."):
                            try:
                                # Run backtest for current player
                                results = bt.run_player_backtest(
                                    player_id=str(selected_player_id),
                                    player_name=player_data['player_info_name'],
                                    player_team_id=int(player_data['team_id']),
                                    n_games=n_games_backtest,
                                    skip_recent=skip_recent
                                )
                                
                                if results:
                                    # Store in session state
                                    st.session_state.backtest_results = {
                                        'results': results,
                                        'summaries': bt.calculate_backtest_summary(results),
                                        'confidence_metrics': bt.calculate_confidence_accuracy(results),
                                        'player_name': player_data['player_info_name']
                                    }
                                else:
                                    st.session_state.backtest_results = None
                                    st.warning("No backtest results generated. Player may not have enough games.")
                            except Exception as e:
                                st.error(f"Backtest error: {str(e)}")
                                st.session_state.backtest_results = None
                    
                    # Display results from session state (persists across reruns)
                    if st.session_state.backtest_results is not None:
                        results = st.session_state.backtest_results['results']
                        summaries = st.session_state.backtest_results['summaries']
                        confidence_metrics = st.session_state.backtest_results['confidence_metrics']
                        player_name_clean = st.session_state.backtest_results['player_name'].replace(' ', '_').replace("'", "")
                        
                        # Display summary
                        st.markdown("### 📈 Accuracy Summary")
                        summary_df = bt.format_summary_for_display(summaries)
                        if len(summary_df) > 0:
                            st.dataframe(summary_df, width='stretch', hide_index=True)
                            st.download_button(
                                label="📥 Download Summary",
                                data=summary_df.to_csv(index=False),
                                file_name=f"{player_name_clean}_Accuracy_Summary.csv",
                                mime="text/csv",
                                key="download_summary"
                            )
                        
                        # Confidence breakdown
                        if confidence_metrics:
                            st.markdown("### 🎯 Accuracy by Confidence Level")
                            conf_rows = []
                            for conf, metrics in confidence_metrics.items():
                                conf_rows.append({
                                    'Confidence': conf.capitalize(),
                                    'Predictions': metrics['count'],
                                    'MAE': metrics['mae'],
                                    'Within 10%': f"{metrics['within_10_pct']}%"
                                })
                            conf_df = pd.DataFrame(conf_rows)
                            st.dataframe(conf_df, width='stretch', hide_index=True)
                            st.download_button(
                                label="📥 Download Confidence",
                                data=conf_df.to_csv(index=False),
                                file_name=f"{player_name_clean}_Accuracy_By_Confidence.csv",
                                mime="text/csv",
                                key="download_confidence"
                            )
                        
                        # Player Type breakdown (for PTS)
                        player_type_metrics = bt.calculate_player_type_accuracy(results, stat='PTS')
                        if player_type_metrics:
                            # Show regression tier used
                            regression_tier = bt.get_regression_tier_from_results(results)
                            tier_emoji = "👑" if regression_tier == "Ultra-elite" else "⭐" if "Elite" in regression_tier else "📊"
                            st.markdown(f"### 👤 Accuracy by Player Type (Points) — {tier_emoji} **Regression Tier: {regression_tier}**")
                            st.caption("Ultra-elite: ≥27 PPG | Star: >18 PPG or ≥32 MPG | Starter: 12-18 PPG & ≥25 MPG | Role Player: <12 PPG or <25 MPG")
                            player_type_df = bt.format_player_type_summary(player_type_metrics)
                            if len(player_type_df) > 0:
                                st.dataframe(player_type_df, width='stretch', hide_index=True)
                                st.download_button(
                                    label="📥 Download Player Type",
                                    data=player_type_df.to_csv(index=False),
                                    file_name=f"{player_name_clean}_Accuracy_By_Player_Type.csv",
                                    mime="text/csv",
                                    key="download_player_type"
                                )
                        
                        # Show individual results
                        st.markdown("### 📋 Individual Predictions vs Actuals")
                        results_df = pd.DataFrame([{
                            'Date': r.game_date,
                            'vs': r.opponent_abbr,
                            'Stat': r.stat,
                            'Pred': r.predicted,
                            'Actual': r.actual,
                            'Error': f"{'+' if r.error > 0 else ''}{r.error}",
                            'Conf': r.confidence.capitalize(),
                            'Type': r.player_type
                        } for r in results])
                        
                        # Filter by stat
                        stat_filter = st.selectbox("Filter by stat", 
                                                   options=['All'] + list(results_df['Stat'].unique()),
                                                   key="backtest_stat_filter")
                        if stat_filter != 'All':
                            filtered_df = results_df[results_df['Stat'] == stat_filter]
                        else:
                            filtered_df = results_df
                        
                        st.dataframe(filtered_df, width='stretch', hide_index=True, height=300)
                        st.download_button(
                            label="📥 Download Predictions",
                            data=results_df.to_csv(index=False),
                            file_name=f"{player_name_clean}_Individual_Predictions.csv",
                            mime="text/csv",
                            key="download_predictions"
                        )
                        
                        # Interpretation
                        if summaries:
                            pts_summary = summaries.get('PTS')
                            if pts_summary:
                                st.markdown("---")
                                st.markdown("**📝 Interpretation:**")
                                bias_text = "over-predicting" if pts_summary.bias > 0 else "under-predicting"
                                st.markdown(f"""
                                - **Points MAE**: {pts_summary.mae} (on average, predictions are off by {pts_summary.mae} points)
                                - **Bias**: {'+' if pts_summary.bias > 0 else ''}{pts_summary.bias} (model is {bias_text})
                                - **Accuracy**: {pts_summary.within_10_pct}% of predictions within 10% of actual
                                """)
            else:
                st.warning("Could not generate predictions. Please try again.")
        else:
            st.warning("⚠️ Could not determine opponent. Please select a valid matchup.")
    else:
        st.info("ℹ️ Select a matchup above to generate predictions for this player.")
        st.markdown("""
        **How predictions work:**
        1. We analyze the player's recent performance (L3, L5, L10, Season)
        2. We adjust for opponent defensive strength and pace
        3. We factor in home/away splits and rest days
        4. We consider historical performance against this opponent
        
        Select a date and matchup above to see predictions!
        """)
