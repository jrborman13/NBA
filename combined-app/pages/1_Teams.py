import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'streamlit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'new-streamlit-app', 'player-app'))

import streamlit as st
import streamlit_testing_functions as functions
import player_functions as pf_players
import injury_report as ir
import datetime
from datetime import date
import time
import nba_api.stats.endpoints
import prediction_features as pf
import team_onoff as toff

import altair as alt
import pandas as pd
import streamlit as st

# Clear all caches
# st.cache_data.clear()

st.set_page_config(layout="wide")
st.title("NBA Matchup Data App")

# Add sidebar with cache clear button
with st.sidebar:
    st.markdown("### Cache Management")
    if st.button("🗑️ Clear All Cache", width='stretch'):
        st.cache_data.clear()
        st.success("✅ Cache cleared successfully!")
        st.rerun()
    st.markdown("---")  # Separator

# Function to fetch matchups for a given date (same as Players page)
@st.cache_data(ttl=21600, show_spinner=False)
def get_matchups_for_date(selected_date):
    """Fetch NBA matchups for a given date from the API"""
    season = '2025-26'
    
    # Fetch from API
    try:
        league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
            league_id='00',
            season=season
        ).get_data_frames()[0]
    except Exception as e:
        return [], f"Error fetching schedule: {str(e)}"
    
    try:
        
        # Convert game date column to datetime
        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        
        # Compare date parts only to handle datetime objects with time components
        date_games = league_schedule[
            league_schedule['dateGame'].dt.date == selected_date
        ]
        
        if len(date_games) > 0:
            matchups = []
            wolves_id = 1610612750  # Timberwolves team ID
            
            for _, row in date_games.iterrows():
                away_team_id = row['awayTeam_teamId']
                home_team_id = row['homeTeam_teamId']
                
                # Get team abbreviations
                away_abbr = row.get('awayTeam_teamTricode', '')
                home_abbr = row.get('homeTeam_teamTricode', '')
                
                # Get team names
                away_name = row.get('awayTeam_teamName', f"Team {away_team_id}")
                home_name = row.get('homeTeam_teamName', f"Team {home_team_id}")
                
                matchups.append({
                    'game_id': row.get('gameId', ''),
                    'away_team_id': away_team_id,
                    'home_team_id': home_team_id,
                    'away_team_name': away_name,
                    'home_team_name': home_name,
                    'away_team': away_abbr,
                    'home_team': home_abbr,
                    'game_time': row.get('gameDate', ''),
                    'is_wolves_game': (away_team_id == wolves_id or home_team_id == wolves_id)
                })
            
            # Sort by game time, with Wolves games first
            matchups.sort(key=lambda x: (not x['is_wolves_game'], str(x['game_time'])))
            return matchups, None
        else:
            return [], f"No games found for {selected_date}"
    except Exception as e:
        return [], f"Error fetching schedule: {str(e)}"

# Date and Matchup selector
st.markdown("### Select Matchup")

col_date, col_matchup = st.columns([1, 3])

with col_date:
    # Date selector - default to today
    selected_date = st.date_input(
        "Select Date:",
        value=date.today(),
        key="teams_matchup_date"
    )

with col_matchup:
    # Get matchups for selected date
    matchups_for_date, matchup_error = get_matchups_for_date(selected_date)
    
    # Show error if API call failed
    if matchup_error:
        st.warning(f"⚠️ {matchup_error}")
        matchups_for_date = []

if matchups_for_date:
    # Create matchup options for dropdown
    matchup_options = []
    for matchup in matchups_for_date:
        matchup_str = f"{matchup['away_team_name']} @ {matchup['home_team_name']}"
        if matchup['is_wolves_game']:
            matchup_str += " 🐺"
        matchup_options.append(matchup_str)
    
    # Default to first option (Wolves game if available, otherwise first by time)
    default_idx = 0
    
    selected_matchup_str = st.selectbox(
        "Choose Matchup:",
        options=matchup_options,
        index=default_idx,
        help="Select a matchup from scheduled games. Timberwolves games are marked with 🐺"
    )
    
    # Find the selected matchup
    selected_matchup = matchups_for_date[matchup_options.index(selected_matchup_str)]
    
    # Store in session state to track changes
    matchup_changed = ('selected_matchup' not in st.session_state or 
                      st.session_state.get('selected_matchup', {}).get('game_id') != selected_matchup.get('game_id'))
    
    if matchup_changed:
        st.session_state['selected_matchup'] = selected_matchup
        st.session_state['matchup_override'] = selected_matchup
    
    # Update matchup variables without reloading
    if 'matchup_override' in st.session_state:
        functions.set_matchup_override(st.session_state['matchup_override'])
        functions.update_selected_matchup(st.session_state['matchup_override'])
else:
    st.info(f"ℹ️ No games scheduled for {selected_date.strftime('%B %d, %Y')}.")
    selected_matchup = None
    if 'selected_matchup' in st.session_state:
        del st.session_state['selected_matchup']

# Only show tabs and content if a matchup is selected
if selected_matchup:
    # ============================================================
    # MATCHUP SUMMARY SECTION
    # ============================================================
    
    # Load player data for matchup summary (reuse cache from Rosters tab)
    @st.cache_data(ttl=1800, show_spinner="Loading player data...")
    def load_summary_data():
        # Use player_functions.get_players_dataframe (same as other pages)
        players_df = pf_players.get_players_dataframe()
        
        # Use prediction_features.get_bulk_player_game_logs (uses Supabase cache)
        # This is the same function that streamlit_testing_functions.get_all_player_game_logs uses internally
        game_logs_df = pf.get_bulk_player_game_logs()
        
        return players_df, game_logs_df
    
    summary_players_df, summary_game_logs_df = load_summary_data()
    
    # Get team info
    away_team_name = selected_matchup['away_team_name']
    home_team_name = selected_matchup['home_team_name']
    away_team_id = selected_matchup['away_team_id']
    home_team_id = selected_matchup['home_team_id']
    
    # Get tricodes directly from matchup (from API)
    away_abbr = selected_matchup.get('away_team', '')
    home_abbr = selected_matchup.get('home_team', '')
    
    # Fallback to mapping if tricodes not available
    if not away_abbr or not home_abbr:
        team_name_to_abbr = {
            'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
            'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
            'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
            'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
            'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
            'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
            'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
            'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
            'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
            'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'
        }
        if not away_abbr:
            away_abbr = team_name_to_abbr.get(away_team_name, away_team_name.split()[-1][:3].upper())
        if not home_abbr:
            home_abbr = team_name_to_abbr.get(home_team_name, home_team_name.split()[-1][:3].upper())
    
    # Fetch injury report for matchup summary
    @st.cache_data(ttl=600, show_spinner=False)
    def fetch_summary_injuries():
        return ir.fetch_injuries_for_date()
    
    summary_injury_df, _ = fetch_summary_injuries()
    
    # Get injuries for this matchup
    summary_away_injuries = []
    summary_home_injuries = []
    if summary_injury_df is not None and len(summary_injury_df) > 0:
        matchup_injuries = ir.get_injuries_for_matchup(
            summary_injury_df, away_abbr, home_abbr, summary_players_df
        )
        summary_away_injuries = matchup_injuries.get('away', [])
        summary_home_injuries = matchup_injuries.get('home', [])
    
    # Generate matchup summary
    matchup_summary = functions.generate_matchup_summary(
        away_id=away_team_id,
        home_id=home_team_id,
        away_name=away_team_name,
        home_name=home_team_name,
        away_abbr=away_abbr,
        home_abbr=home_abbr,
        players_df=summary_players_df,
        game_logs_df=summary_game_logs_df,
        away_injuries=summary_away_injuries,
        home_injuries=summary_home_injuries
    )
    
    # Display matchup summary in an expander
    with st.expander("📊 **Matchup Summary**", expanded=True):
        
        # === BIGGEST MISMATCHES ===
        st.markdown("#### 🔥 Biggest Stat Mismatches")
        
        if matchup_summary['mismatches']:
            mismatch_cols = st.columns(2)
            
            # Split mismatches by team advantage (using abbreviations now)
            away_advantages = [m for m in matchup_summary['mismatches'] if m['team_with_advantage'] == away_abbr]
            home_advantages = [m for m in matchup_summary['mismatches'] if m['team_with_advantage'] == home_abbr]
            
            with mismatch_cols[0]:
                st.markdown(f"**{away_abbr} Advantages**")
                if away_advantages:
                    for m in away_advantages:  # Show all advantages (no limit)
                        arrow = "🟢" if m['rank_diff'] >= 15 else "🟡" if m['rank_diff'] >= 10 else "⚪"
                        st.markdown(f"{arrow} **{m['stat_name']}**: {m['off_team']} OFF #{m['off_rank']} vs {m['def_team']} DEF #{m['def_rank']} (+{m['rank_diff']})")
                else:
                    st.caption("No significant advantages found")
            
            with mismatch_cols[1]:
                st.markdown(f"**{home_abbr} Advantages**")
                if home_advantages:
                    for m in home_advantages:  # Show all advantages (no limit)
                        arrow = "🟢" if m['rank_diff'] >= 15 else "🟡" if m['rank_diff'] >= 10 else "⚪"
                        st.markdown(f"{arrow} **{m['stat_name']}**: {m['off_team']} OFF #{m['off_rank']} vs {m['def_team']} DEF #{m['def_rank']} (+{m['rank_diff']})")
                else:
                    st.caption("No significant advantages found")
        else:
            st.caption("No mismatches data available")
        
        st.divider()
        
        # === HOT PLAYERS ===
        st.markdown("#### 📈 Hot Players (20%+ Above Season Avg in L5)")
        
        hot_cols = st.columns(2)
        
        with hot_cols[0]:
            st.markdown(f"**{away_abbr}**")
            if matchup_summary['hot_players']['away']:
                for p in matchup_summary['hot_players']['away'][:5]:
                    hot_stat = p['hot_stats'][0]
                    pct = int(hot_stat['pct_change'] * 100)
                    st.markdown(f"🔥 **{p['player_name']}**: {hot_stat['l5']:.1f} {hot_stat['stat']} L5 (+{pct}% vs {hot_stat['season']:.1f} season)")
            else:
                st.caption("No hot players found")
        
        with hot_cols[1]:
            st.markdown(f"**{home_abbr}**")
            if matchup_summary['hot_players']['home']:
                for p in matchup_summary['hot_players']['home'][:5]:
                    hot_stat = p['hot_stats'][0]
                    pct = int(hot_stat['pct_change'] * 100)
                    st.markdown(f"🔥 **{p['player_name']}**: {hot_stat['l5']:.1f} {hot_stat['stat']} L5 (+{pct}% vs {hot_stat['season']:.1f} season)")
            else:
                st.caption("No hot players found")
        
        st.divider()
        
        # === COLD PLAYERS ===
        st.markdown("#### 🥶 Cold Players (20%+ Below Season Avg in L5)")
        
        cold_cols = st.columns(2)
        
        with cold_cols[0]:
            st.markdown(f"**{away_abbr}**")
            if matchup_summary['cold_players']['away']:
                for p in matchup_summary['cold_players']['away'][:5]:
                    cold_stat = p['cold_stats'][0]
                    pct = int(abs(cold_stat['pct_change']) * 100)
                    st.markdown(f"🥶 **{p['player_name']}**: {cold_stat['l5']:.1f} {cold_stat['stat']} L5 (-{pct}% vs {cold_stat['season']:.1f} season)")
            else:
                st.caption("No cold players found")
        
        with cold_cols[1]:
            st.markdown(f"**{home_abbr}**")
            if matchup_summary['cold_players']['home']:
                for p in matchup_summary['cold_players']['home'][:5]:
                    cold_stat = p['cold_stats'][0]
                    pct = int(abs(cold_stat['pct_change']) * 100)
                    st.markdown(f"🥶 **{p['player_name']}**: {cold_stat['l5']:.1f} {cold_stat['stat']} L5 (-{pct}% vs {cold_stat['season']:.1f} season)")
            else:
                st.caption("No cold players found")
        
        st.divider()
        
        # === NEW PLAYERS (Emerging Roles) ===
        st.markdown("#### 🆕 Emerging Roles (25%+ Minutes Increase in L5)")
        
        new_cols = st.columns(2)
        
        with new_cols[0]:
            st.markdown(f"**{away_abbr}**")
            if matchup_summary['new_players']['away']:
                for p in matchup_summary['new_players']['away'][:5]:
                    pct = int(p['pct_increase'] * 100)
                    st.markdown(f"⬆️ **{p['player_name']}**: {p['l5_min']:.1f} MIN L5 (+{pct}% vs {p['season_min']:.1f} season) | {p['l5_pts']:.1f}/{p['l5_reb']:.1f}/{p['l5_ast']:.1f}")
            else:
                st.caption("No emerging players found")
        
        with new_cols[1]:
            st.markdown(f"**{home_abbr}**")
            if matchup_summary['new_players']['home']:
                for p in matchup_summary['new_players']['home'][:5]:
                    pct = int(p['pct_increase'] * 100)
                    st.markdown(f"⬆️ **{p['player_name']}**: {p['l5_min']:.1f} MIN L5 (+{pct}% vs {p['season_min']:.1f} season) | {p['l5_pts']:.1f}/{p['l5_reb']:.1f}/{p['l5_ast']:.1f}")
            else:
                st.caption("No emerging players found")
        
        st.divider()
        
        # === KEY INJURIES ===
        st.markdown("#### 🏥 Key Injuries (MIN ≥15 or PRA ≥15 | Questionable/Doubtful/Out)")
        
        inj_cols = st.columns(2)
        
        # Helper for status color
        def get_status_badge(status):
            status_lower = status.lower() if status else ''
            if 'out' in status_lower:
                return "🔴"
            elif 'doubtful' in status_lower:
                return "🟠"
            elif 'questionable' in status_lower:
                return "🟡"
            elif 'probable' in status_lower:
                return "🟢"
            else:
                return "⚪"
        
        with inj_cols[0]:
            st.markdown(f"**{away_abbr}**")
            if matchup_summary['key_injuries']['away']:
                for inj in matchup_summary['key_injuries']['away']:
                    badge = get_status_badge(inj.get('status', ''))
                    player_name = ir.format_player_name(inj.get('player_name', 'Unknown'))
                    status = inj.get('status', 'Unknown')
                    games_missed = inj.get('games_missed', '?')
                    avg_min = inj.get('avg_min', 0)
                    avg_pra = inj.get('avg_pra', 0)
                    reason = ir.format_injury_reason(inj.get('reason', ''))
                    st.markdown(f"{badge} **{player_name}** ({status} - {games_missed}) | {avg_min:.1f} MIN, {avg_pra:.1f} PRA | {reason}")
            else:
                st.caption("No key injuries")
        
        with inj_cols[1]:
            st.markdown(f"**{home_abbr}**")
            if matchup_summary['key_injuries']['home']:
                for inj in matchup_summary['key_injuries']['home']:
                    badge = get_status_badge(inj.get('status', ''))
                    player_name = ir.format_player_name(inj.get('player_name', 'Unknown'))
                    status = inj.get('status', 'Unknown')
                    games_missed = inj.get('games_missed', '?')
                    avg_min = inj.get('avg_min', 0)
                    avg_pra = inj.get('avg_pra', 0)
                    reason = ir.format_injury_reason(inj.get('reason', ''))
                    st.markdown(f"{badge} **{player_name}** ({status} - {games_missed}) | {avg_min:.1f} MIN, {avg_pra:.1f} PRA | {reason}")
            else:
                st.caption("No key injuries")
    
    st.markdown("---")
    
    # ============================================================
    # NBA STANDINGS SECTION
    # ============================================================
    st.markdown("### 🏀 NBA Standings")
    
    # Get standings data
    try:
        standings_df = functions.standings.copy()
        
        if standings_df is not None and len(standings_df) > 0 and 'Conference' in standings_df.columns:
            # Split by conference
            west_standings = standings_df[standings_df['Conference'] == 'West'].copy()
            east_standings = standings_df[standings_df['Conference'] == 'East'].copy()
            
            # Sort by playoff rank
            west_standings = west_standings.sort_values('PlayoffRank')
            east_standings = east_standings.sort_values('PlayoffRank')
            
            # Prepare display columns (excluding WINS/LOSSES as they're in Record)
            display_cols = ['PlayoffRank', 'TeamCity', 'TeamName', 'Record', 'WinPCT']
            
            # Add Clutch column if available
            if 'Clutch' in standings_df.columns:
                display_cols.append('Clutch')
            
            # Add additional columns if available
            additional_cols = ['ConferenceGamesBack', 'L10', 'HOME', 'ROAD', 'vsWest', 'vsEast']
            for col in additional_cols:
                if col in standings_df.columns:
                    display_cols.append(col)
            
            # Check for Last 5 games column (might be named differently)
            last5_cols = ['L5', 'Last5', 'Last5Games']
            last5_col = None
            for col in last5_cols:
                if col in standings_df.columns:
                    last5_col = col
                    display_cols.append(col)
                    break
            
            # Create two columns
            standings_cols = st.columns(2)
            
            with standings_cols[0]:
                st.markdown("#### Western Conference")
                # Create display DataFrame
                west_display = west_standings[display_cols].copy()
                west_display['Team'] = west_display['TeamCity'] + ' ' + west_display['TeamName']
                
                # Format WinPCT as percentage
                if 'WinPCT' in west_display.columns:
                    west_display['Win %'] = west_display['WinPCT'].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")
                    west_display = west_display.drop(columns=['WinPCT'])
                
                # Format and rename Games Back
                if 'ConferenceGamesBack' in west_display.columns:
                    west_display['GB'] = west_display['ConferenceGamesBack'].apply(
                        lambda x: f"{x:.1f}" if pd.notna(x) and x != 0 else ("—" if pd.notna(x) else "N/A")
                    )
                    west_display = west_display.drop(columns=['ConferenceGamesBack'])
                
                # Rename columns for better display
                if 'PlayoffRank' in west_display.columns:
                    west_display = west_display.rename(columns={'PlayoffRank': 'Seed'})
                if 'L10' in west_display.columns:
                    west_display = west_display.rename(columns={'L10': 'Last 10'})
                if last5_col and last5_col in west_display.columns:
                    west_display = west_display.rename(columns={last5_col: 'Last 5'})
                if 'HOME' in west_display.columns:
                    west_display = west_display.rename(columns={'HOME': 'Home'})
                if 'ROAD' in west_display.columns:
                    west_display = west_display.rename(columns={'ROAD': 'Road'})
                if 'vsWest' in west_display.columns:
                    west_display = west_display.rename(columns={'vsWest': 'vs West'})
                if 'vsEast' in west_display.columns:
                    west_display = west_display.rename(columns={'vsEast': 'vs East'})
                
                # Build column list for display
                display_order = ['Seed', 'Team', 'Record', 'Win %']
                if 'GB' in west_display.columns:
                    display_order.append('GB')
                if 'Last 5' in west_display.columns:
                    display_order.append('Last 5')
                if 'Last 10' in west_display.columns:
                    display_order.append('Last 10')
                if 'Clutch' in west_display.columns:
                    display_order.append('Clutch')
                if 'Home' in west_display.columns:
                    display_order.append('Home')
                if 'Road' in west_display.columns:
                    display_order.append('Road')
                if 'vs West' in west_display.columns:
                    display_order.append('vs West')
                if 'vs East' in west_display.columns:
                    display_order.append('vs East')
                
                west_display = west_display[display_order]
                
                # Highlight function for away/home teams
                def highlight_selected_teams_west(row):
                    row_idx = row.name
                    if row_idx in west_standings.index:
                        team_id = west_standings.loc[row_idx, 'TeamID']
                        if team_id == away_team_id or team_id == home_team_id:
                            return ['background-color: #e8f4f8'] * len(west_display.columns)
                    return [''] * len(west_display.columns)
                
                styled_west = west_display.style.apply(highlight_selected_teams_west, axis=1)
                st.dataframe(styled_west, width='stretch', hide_index=True)
            
            with standings_cols[1]:
                st.markdown("#### Eastern Conference")
                # Create display DataFrame
                east_display = east_standings[display_cols].copy()
                east_display['Team'] = east_display['TeamCity'] + ' ' + east_display['TeamName']
                
                # Format WinPCT as percentage
                if 'WinPCT' in east_display.columns:
                    east_display['Win %'] = east_display['WinPCT'].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")
                    east_display = east_display.drop(columns=['WinPCT'])
                
                # Format and rename Games Back
                if 'ConferenceGamesBack' in east_display.columns:
                    east_display['GB'] = east_display['ConferenceGamesBack'].apply(
                        lambda x: f"{x:.1f}" if pd.notna(x) and x != 0 else ("—" if pd.notna(x) else "N/A")
                    )
                    east_display = east_display.drop(columns=['ConferenceGamesBack'])
                
                # Rename columns for better display
                if 'PlayoffRank' in east_display.columns:
                    east_display = east_display.rename(columns={'PlayoffRank': 'Seed'})
                if 'L10' in east_display.columns:
                    east_display = east_display.rename(columns={'L10': 'Last 10'})
                if last5_col and last5_col in east_display.columns:
                    east_display = east_display.rename(columns={last5_col: 'Last 5'})
                if 'HOME' in east_display.columns:
                    east_display = east_display.rename(columns={'HOME': 'Home'})
                if 'ROAD' in east_display.columns:
                    east_display = east_display.rename(columns={'ROAD': 'Road'})
                if 'vsWest' in east_display.columns:
                    east_display = east_display.rename(columns={'vsWest': 'vs West'})
                if 'vsEast' in east_display.columns:
                    east_display = east_display.rename(columns={'vsEast': 'vs East'})
                
                # Build column list for display
                display_order = ['Seed', 'Team', 'Record', 'Win %']
                if 'GB' in east_display.columns:
                    display_order.append('GB')
                if 'Last 5' in east_display.columns:
                    display_order.append('Last 5')
                if 'Last 10' in east_display.columns:
                    display_order.append('Last 10')
                if 'Clutch' in east_display.columns:
                    display_order.append('Clutch')
                if 'Home' in east_display.columns:
                    display_order.append('Home')
                if 'Road' in east_display.columns:
                    display_order.append('Road')
                if 'vs West' in east_display.columns:
                    display_order.append('vs West')
                if 'vs East' in east_display.columns:
                    display_order.append('vs East')
                
                east_display = east_display[display_order]
                
                # Highlight function for away/home teams
                def highlight_selected_teams_east(row):
                    row_idx = row.name
                    if row_idx in east_standings.index:
                        team_id = east_standings.loc[row_idx, 'TeamID']
                        if team_id == away_team_id or team_id == home_team_id:
                            return ['background-color: #e8f4f8'] * len(east_display.columns)
                    return [''] * len(east_display.columns)
                
                styled_east = east_display.style.apply(highlight_selected_teams_east, axis=1)
                st.dataframe(styled_east, width='stretch', hide_index=True)
        else:
            st.warning("Standings data not available.")
    except Exception as e:
        st.warning(f"Unable to load standings: {str(e)}")
    
    # ============================================================
    # LAST 10 GAMES SECTION
    # ============================================================
    st.markdown("### 📊 Last 10 Games")
    
    @st.cache_data(ttl=1800, show_spinner=False)
    def get_game_scores(game_id, team_id):
        """Get opponent score and team ID from box score"""
        try:
            from nba_api.stats.endpoints import BoxScoreSummaryV2
            box_score = BoxScoreSummaryV2(game_id=game_id)
            line_score = box_score.get_data_frames()[1]  # LineScore is the second dataframe
            
            if len(line_score) >= 2:
                # Find the opponent's score and team ID (the team that's not the current team)
                for _, row in line_score.iterrows():
                    if row['TEAM_ID'] != team_id:
                        return int(row['PTS']), int(row['TEAM_ID'])
            return None, None
        except Exception as e:
            print(f"Error getting box score for game {game_id}: {e}")
            return None, None
    
    @st.cache_data(ttl=1800, show_spinner=False)
    def get_team_last_10_games(team_id, season=None):
        """Get team's last 10 games formatted for display"""
        try:
            # Use current season from prediction_features if not specified
            if season is None:
                season = pf.CURRENT_SEASON
            
            team_logs = pf.get_team_game_logs(team_id, season)
            
            # If no logs found, try alternative seasons
            if len(team_logs) == 0:
                # Try 2024-25 season (current actual NBA season)
                if season != "2024-25":
                    team_logs = pf.get_team_game_logs(team_id, "2024-25")
                    if len(team_logs) > 0:
                        season = "2024-25"
                
                # If still empty, try 2023-24 as fallback
                if len(team_logs) == 0 and season != "2023-24":
                    team_logs = pf.get_team_game_logs(team_id, "2023-24")
                    if len(team_logs) > 0:
                        season = "2023-24"
                
                if len(team_logs) == 0:
                    # Return empty DataFrame - error will be shown in UI
                    return pd.DataFrame()
            
            # Get last 10 games
            last_10 = team_logs.head(10).copy()
            
            # Team abbreviation to ID mapping
            abbr_to_id = {
                'ATL': 1610612737, 'BOS': 1610612738, 'BKN': 1610612751, 'CHA': 1610612766,
                'CHI': 1610612741, 'CLE': 1610612739, 'DAL': 1610612742, 'DEN': 1610612743,
                'DET': 1610612765, 'GSW': 1610612744, 'HOU': 1610612745, 'IND': 1610612754,
                'LAC': 1610612746, 'LAL': 1610612747, 'MEM': 1610612763, 'MIA': 1610612748,
                'MIL': 1610612749, 'MIN': 1610612750, 'NOP': 1610612740, 'NYK': 1610612752,
                'OKC': 1610612760, 'ORL': 1610612753, 'PHI': 1610612755, 'PHX': 1610612756,
                'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'TOR': 1610612761,
                'UTA': 1610612762, 'WAS': 1610612764
            }
            
            # Format the data
            display_data = []
            for _, game in last_10.iterrows():
                # Get outcome (W/L)
                outcome = game.get('WL', 'N/A')
                
                # Get opponent from MATCHUP (format: "Team @ OPP" or "Team vs OPP")
                matchup = game.get('MATCHUP', '')
                opponent_abbr = matchup.split()[-1] if matchup else 'N/A'
                
                # Determine Home/Away from MATCHUP
                if '@' in matchup:
                    home_away = 'A'
                elif 'vs' in matchup.lower():
                    home_away = 'H'
                else:
                    home_away = 'N/A'
                
                # Get final score using PLUS_MINUS
                team_score = int(game.get('PTS', 0))
                plus_minus = game.get('PLUS_MINUS', 0)
                
                # Calculate opponent score: PTS - PLUS_MINUS = opponent score
                if pd.notna(plus_minus):
                    opp_score = int(team_score - plus_minus)
                    final_score = f"{team_score}-{opp_score}"
                else:
                    final_score = f"{team_score}"
                
                # Get opponent team ID from abbreviation mapping for logo
                opp_team_id = abbr_to_id.get(opponent_abbr) if opponent_abbr != 'N/A' else None
                
                # Get opponent logo URL
                if opp_team_id:
                    opp_logo_url = f"https://cdn.nba.com/logos/nba/{opp_team_id}/primary/L/logo.svg"
                else:
                    opp_logo_url = ""
                
                # Calculate shooting percentages
                fgm = game.get('FGM', 0)
                fga = game.get('FGA', 0)
                fg_pct = (fgm / fga * 100) if fga > 0 else 0.0
                
                fg2m = fgm - game.get('FG3M', 0)
                fg2a = fga - game.get('FG3A', 0)
                fg2_pct = (fg2m / fg2a * 100) if fg2a > 0 else 0.0
                
                fg3m = game.get('FG3M', 0)
                fg3a = game.get('FG3A', 0)
                fg3_pct = (fg3m / fg3a * 100) if fg3a > 0 else 0.0
                
                # Get other stats
                reb = game.get('REB', 0)
                ast = game.get('AST', 0)
                tov = game.get('TOV', 0)
                stl = game.get('STL', 0)
                blk = game.get('BLK', 0)
                
                # Format date
                game_date = pd.to_datetime(game.get('GAME_DATE', ''))
                date_str = game_date.strftime('%m/%d') if pd.notna(game_date) else 'N/A'
                
                display_data.append({
                    'Opponent': opp_logo_url,  # Logo URL for display
                    'H/A': home_away,
                    'Date': date_str,
                    'Outcome': outcome,
                    'Final Score': final_score,
                    'FG%': f"{fg_pct:.1f}",
                    '2PT%': f"{fg2_pct:.1f}",
                    '3PT%': f"{fg3_pct:.1f}",
                    'REB': int(reb),
                    'AST': int(ast),
                    'TO': int(tov),
                    'STL': int(stl),
                    'BLK': int(blk)
                })
            
            return pd.DataFrame(display_data)
        except Exception as e:
            st.error(f"Error getting team game logs for team {team_id}: {str(e)}")
            print(f"Error getting team game logs: {e}")
            return pd.DataFrame()
    
    # ============================================================
    # SYNERGY DATA FETCHING FUNCTIONS
    # ============================================================
    
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_team_synergy_data(team_id, playtype, type_grouping, season=None, max_retries=3, timeout=60):
        """
        Fetch synergy data for a specific team, playtype, and type_grouping.
        
        Args:
            team_id: Team ID
            playtype: Play type (e.g., 'Cut', 'Handoff', 'Isolation', etc.)
            type_grouping: 'offensive' or 'defensive'
            season: Season string (defaults to CURRENT_SEASON)
            max_retries: Number of retry attempts
            timeout: Request timeout in seconds
        
        Returns:
            DataFrame with synergy data for the team, or empty DataFrame on error
        """
        if season is None:
            season = pf.CURRENT_SEASON
        
        # Fetch from API
        synergy_data = None
        for attempt in range(max_retries):
            try:
                synergy_data = nba_api.stats.endpoints.SynergyPlayTypes(
                    league_id='00',
                    per_mode_simple='Totals',
                    season=season,
                    season_type_all_star='Regular Season',
                    player_or_team_abbreviation='T',
                    type_grouping_nullable=type_grouping,
                    play_type_nullable=playtype,
                    timeout=timeout
                ).get_data_frames()[0]
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Error fetching synergy data for team {team_id}, playtype {playtype}, type {type_grouping}: {str(e)}")
                    return pd.DataFrame(), False
        
        # Filter for the specific team
        if synergy_data is not None and len(synergy_data) > 0 and 'TEAM_ID' in synergy_data.columns:
            team_data = synergy_data[synergy_data['TEAM_ID'] == team_id]
            return team_data, False  # Return cache status
        else:
            return pd.DataFrame(), False
    
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_bulk_all_team_synergy_data(season=None):
        """
        Fetch ALL teams' synergy data for ALL playtypes/type_groupings in bulk.
        Makes only 22 API calls total (11 playtypes × 2 sides) instead of 22 per team.
        
        Args:
            season: Season string (defaults to CURRENT_SEASON)
        
        Returns:
            Dictionary: {playtype: {type_grouping: df_with_all_teams}}
        """
        if season is None:
            season = pf.CURRENT_SEASON
        
        synergy_playtypes = ['Cut', 'Handoff', 'Isolation', 'Misc', 'OffScreen', 'Postup', 
                            'PRBallHandler', 'PRRollman', 'OffRebound', 'Spotup', 'Transition']
        synergy_sides = ['offensive', 'defensive']
        
        # Fetch from API
        result = {}
        total_requests = len(synergy_playtypes) * len(synergy_sides)
        current_request = 0
        
        for playtype in synergy_playtypes:
            result[playtype] = {}
            for side in synergy_sides:
                current_request += 1
                
                # API call
                synergy_data = None
                for attempt in range(3):
                    try:
                        synergy_data = nba_api.stats.endpoints.SynergyPlayTypes(
                            league_id='00',
                            per_mode_simple='Totals',
                            season=season,
                            season_type_all_star='Regular Season',
                            player_or_team_abbreviation='T',
                            type_grouping_nullable=side,
                            play_type_nullable=playtype,
                            timeout=60
                        ).get_data_frames()[0]
                        break
                    except Exception as e:
                        if attempt < 2:
                            wait_time = (attempt + 1) * 2
                            time.sleep(wait_time)
                            continue
                        else:
                            print(f"Error fetching synergy data for playtype {playtype}, type {side}: {str(e)}")
                            synergy_data = pd.DataFrame()
                            break
                
                result[playtype][side] = synergy_data if synergy_data is not None else pd.DataFrame()
                
                # Add delay between API calls to avoid rate limiting
                if current_request < total_requests:
                    time.sleep(1.5)
        
        return result
    
    # Removed @st.cache_data - using Supabase cache instead
    def get_all_team_synergy_data(team_id, season=None):
        """
        Fetch all synergy data for a team (all playtypes × offensive/defensive).
        Uses bulk fetch and filters for the specific team.
        
        Args:
            team_id: Team ID
            season: Season string (defaults to CURRENT_SEASON)
        
        Returns:
            Dictionary: {playtype: {'offensive': df, 'defensive': df}}
        """
        import time
        import json
        from pathlib import Path
        
        start_time = time.time()
        
        if season is None:
            season = pf.CURRENT_SEASON
        
        # Get bulk data (cached)
        bulk_start = time.time()
        bulk_data = get_bulk_all_team_synergy_data(season)
        bulk_time = time.time() - bulk_start
        
        # Filter for specific team
        filter_start = time.time()
        result = {}
        synergy_playtypes = ['Cut', 'Handoff', 'Isolation', 'Misc', 'OffScreen', 'Postup', 
                            'PRBallHandler', 'PRRollman', 'OffRebound', 'Spotup', 'Transition']
        synergy_sides = ['offensive', 'defensive']
        
        for playtype in synergy_playtypes:
            result[playtype] = {}
            for side in synergy_sides:
                if playtype in bulk_data and side in bulk_data[playtype]:
                    team_df = bulk_data[playtype][side]
                    if len(team_df) > 0 and 'TEAM_ID' in team_df.columns:
                        team_data = team_df[team_df['TEAM_ID'] == team_id].copy()
                        result[playtype][side] = team_data
                    else:
                        result[playtype][side] = pd.DataFrame()
                else:
                    result[playtype][side] = pd.DataFrame()
        
        filter_time = time.time() - filter_start
        total_time = time.time() - start_time
        
        print(f"[TIMING] get_all_team_synergy_data: bulk={bulk_time*1000:.1f}ms, filter={filter_time*1000:.1f}ms, total={total_time*1000:.1f}ms")
        
        return result
    
    def build_synergy_matchup_dataframes(away_team_id, home_team_id, season=None):
        """
        Build 4 separate dataframes showing synergy data for each team's offense and defense.
        
        Args:
            away_team_id: Away team ID
            home_team_id: Home team ID
            season: Season string (defaults to CURRENT_SEASON)
        
        Returns:
            Tuple of 4 DataFrames: (away_offense_df, away_defense_df, home_offense_df, home_defense_df)
        """
        import time
        import json
        from pathlib import Path
        
        build_start = time.time()
        
        if season is None:
            season = pf.CURRENT_SEASON
        
        # Fetch synergy data for both teams
        away_start = time.time()
        away_synergy = get_all_team_synergy_data(away_team_id, season)
        away_time = time.time() - away_start
        
        home_start = time.time()
        home_synergy = get_all_team_synergy_data(home_team_id, season)
        home_time = time.time() - home_start
        
        synergy_playtypes = ['Cut', 'Handoff', 'Isolation', 'Misc', 'OffScreen', 'Postup', 
                            'PRBallHandler', 'PRRollman', 'OffRebound', 'Spotup', 'Transition']
        
        # Helper function to extract metrics from synergy dataframe
        def extract_metrics(df, playtype):
            if df is None or len(df) == 0:
                return {
                    'Playtype': playtype,
                    'PPP': 0.0,
                    'Percentile': 0.0,
                    'Rank': 30,
                    'Freq Rank': 30,
                    'Freq': 0.0,
                    'eFG%': 0.0,
                    'Score %': 0.0
                }
            
            row = df.iloc[0] if len(df) > 0 else None
            if row is None:
                return {
                    'Playtype': playtype,
                    'PPP': 0.0,
                    'Percentile': 0.0,
                    'Rank': 30,
                    'Freq Rank': 30,
                    'Freq': 0.0,
                    'eFG%': 0.0,
                    'Score %': 0.0
                }
            
            # Extract metrics using actual API column names
            ppp = row.get('PPP', 0.0)
            
            # PERCENTILE ranges from 0.0 to 1.0 (higher is better)
            # For offense: higher PPP = better → higher percentile → rank 1
            # For defense: lower PPP = better → higher percentile → rank 1
            # The API's percentile calculation already accounts for context (offense vs defense)
            percentile = row.get('PERCENTILE', 0.0)
            
            # Rank calculation: percentile 1.0 = rank 1 (best), percentile 0.0 = rank 30 (worst)
            # Formula: (1.0 - percentile) * 30 + 1, rounded to nearest integer
            # This works for both offense and defense because percentile reflects "better performance":
            # - Offense: rank 1 = highest PPP = highest percentile
            # - Defense: rank 1 = lowest PPP = highest percentile
            rank = round((1.0 - float(percentile)) * 30 + 1) if percentile else 30
            
            # EFG_PCT (Effective Field Goal Percentage) - might be decimal (0-1) or percentage (0-100)
            efg_pct_raw = row.get('EFG_PCT', 0.0)
            efg_pct = float(efg_pct_raw) * 100 if efg_pct_raw < 1 else float(efg_pct_raw)
            
            # POSS_PCT (Possession Percentage / Frequency) - might be decimal (0-1) or percentage (0-100)
            poss_pct_raw = row.get('POSS_PCT', 0.0)
            poss_pct = float(poss_pct_raw) * 100 if poss_pct_raw < 1 else float(poss_pct_raw)
            
            # SCORE_POSS_PCT (Scoring Possession Percentage) - might be decimal (0-1) or percentage (0-100)
            score_poss_pct_raw = row.get('SCORE_POSS_PCT', 0.0)
            score_poss_pct = float(score_poss_pct_raw) * 100 if score_poss_pct_raw < 1 else float(score_poss_pct_raw)
            
            return {
                'Playtype': playtype,
                'PPP': float(ppp) if ppp else 0.0,
                'Rank': int(rank),
                'Percentile': float(percentile) if percentile else 0.0,
                'Freq Rank': 30,  # Placeholder, will be calculated later
                'Freq': float(poss_pct) if poss_pct else 0.0,
                'eFG%': float(efg_pct) if efg_pct else 0.0,
                'Score %': float(score_poss_pct) if score_poss_pct else 0.0
            }
        
        # Build away team offense dataframe
        away_offense_data = []
        for playtype in synergy_playtypes:
            df = away_synergy.get(playtype, {}).get('offensive')
            away_offense_data.append(extract_metrics(df, playtype))
        away_offense_df = pd.DataFrame(away_offense_data)
        # Ensure column order: Playtype, PPP, Rank, Percentile, Freq Rank, Freq, eFG%, Score %
        if len(away_offense_df) > 0:
            col_order = ['Playtype', 'PPP', 'Rank', 'Percentile', 'Freq Rank', 'Freq', 'eFG%', 'Score %']
            away_offense_df = away_offense_df[[col for col in col_order if col in away_offense_df.columns]]
        
        # Build away team defense dataframe
        away_defense_data = []
        for playtype in synergy_playtypes:
            df = away_synergy.get(playtype, {}).get('defensive')
            metrics = extract_metrics(df, playtype)
            # Keep original column names (no "Allowed" suffix)
            away_defense_data.append(metrics)
        away_defense_df = pd.DataFrame(away_defense_data)
        # Ensure column order: Playtype, PPP, Rank, Percentile, Freq Rank, Freq, eFG%, Score %
        if len(away_defense_df) > 0:
            col_order = ['Playtype', 'PPP', 'Rank', 'Percentile', 'Freq Rank', 'Freq', 'eFG%', 'Score %']
            away_defense_df = away_defense_df[[col for col in col_order if col in away_defense_df.columns]]
        
        # Build home team offense dataframe
        home_offense_data = []
        for playtype in synergy_playtypes:
            df = home_synergy.get(playtype, {}).get('offensive')
            home_offense_data.append(extract_metrics(df, playtype))
        home_offense_df = pd.DataFrame(home_offense_data)
        # Ensure column order: Playtype, PPP, Rank, Percentile, Freq Rank, Freq, eFG%, Score %
        if len(home_offense_df) > 0:
            col_order = ['Playtype', 'PPP', 'Rank', 'Percentile', 'Freq Rank', 'Freq', 'eFG%', 'Score %']
            home_offense_df = home_offense_df[[col for col in col_order if col in home_offense_df.columns]]
        
        # Build home team defense dataframe
        home_defense_data = []
        for playtype in synergy_playtypes:
            df = home_synergy.get(playtype, {}).get('defensive')
            metrics = extract_metrics(df, playtype)
            # Keep original column names (no "Allowed" suffix)
            home_defense_data.append(metrics)
        home_defense_df = pd.DataFrame(home_defense_data)
        # Ensure column order: Playtype, PPP, Rank, Percentile, Freq Rank, Freq, eFG%, Score %
        if len(home_defense_df) > 0:
            col_order = ['Playtype', 'PPP', 'Rank', 'Percentile', 'Freq Rank', 'Freq', 'eFG%', 'Score %']
            home_defense_df = home_defense_df[[col for col in col_order if col in home_defense_df.columns]]
        
        # Calculate frequency ranks for all playtypes using bulk data
        # Get bulk data to calculate ranks across all teams
        bulk_data = get_bulk_all_team_synergy_data(season)
        
        # Helper function to calculate frequency rank for a team's playtype/side
        def calculate_freq_rank(team_id, playtype, side, bulk_data):
            """Calculate frequency rank (1-30) where 1 = highest frequency (closest to 1), 30 = lowest (closest to 0)"""
            if playtype not in bulk_data or side not in bulk_data[playtype]:
                return 30
            
            team_df = bulk_data[playtype][side]
            if len(team_df) == 0 or 'TEAM_ID' not in team_df.columns or 'POSS_PCT' not in team_df.columns:
                return 30
            
            # Get all teams' POSS_PCT values
            poss_pct_values = team_df[['TEAM_ID', 'POSS_PCT']].copy()
            poss_pct_values['POSS_PCT'] = poss_pct_values['POSS_PCT'].apply(
                lambda x: float(x) * 100 if float(x) < 1 else float(x)
            )
            
            # Sort descending (highest POSS_PCT = rank 1)
            poss_pct_values = poss_pct_values.sort_values('POSS_PCT', ascending=False).reset_index(drop=True)
            
            # Assign ranks (1 = highest frequency, 30 = lowest)
            poss_pct_values['Freq Rank'] = range(1, len(poss_pct_values) + 1)
            
            # Find the rank for the specific team
            team_row = poss_pct_values[poss_pct_values['TEAM_ID'] == team_id]
            if len(team_row) > 0:
                return int(team_row.iloc[0]['Freq Rank'])
            else:
                return 30
        
        # Update frequency ranks for all dataframes
        if len(away_offense_df) > 0:
            for idx, row in away_offense_df.iterrows():
                playtype = row['Playtype']
                freq_rank = calculate_freq_rank(away_team_id, playtype, 'offensive', bulk_data)
                away_offense_df.at[idx, 'Freq Rank'] = freq_rank
        
        if len(away_defense_df) > 0:
            for idx, row in away_defense_df.iterrows():
                playtype = row['Playtype']
                freq_rank = calculate_freq_rank(away_team_id, playtype, 'defensive', bulk_data)
                away_defense_df.at[idx, 'Freq Rank'] = freq_rank
        
        if len(home_offense_df) > 0:
            for idx, row in home_offense_df.iterrows():
                playtype = row['Playtype']
                freq_rank = calculate_freq_rank(home_team_id, playtype, 'offensive', bulk_data)
                home_offense_df.at[idx, 'Freq Rank'] = freq_rank
        
        if len(home_defense_df) > 0:
            for idx, row in home_defense_df.iterrows():
                playtype = row['Playtype']
                freq_rank = calculate_freq_rank(home_team_id, playtype, 'defensive', bulk_data)
                home_defense_df.at[idx, 'Freq Rank'] = freq_rank
        
        build_time = time.time() - build_start
        
        print(f"[TIMING] build_synergy_matchup_dataframes: away={away_time*1000:.1f}ms, home={home_time*1000:.1f}ms, build={build_time*1000:.1f}ms, total={build_time*1000:.1f}ms")
        
        return away_offense_df, away_defense_df, home_offense_df, home_defense_df
    
    # Get last 10 games for both teams
    try:
        away_last_10 = get_team_last_10_games(away_team_id)
        home_last_10 = get_team_last_10_games(home_team_id)
    except Exception as e:
        st.error(f"Error fetching game logs: {str(e)}")
        away_last_10 = pd.DataFrame()
        home_last_10 = pd.DataFrame()
    
    # Debug output (can be removed later)
    with st.expander("🔍 Debug Info (Click to expand)", expanded=False):
        st.write(f"Away Team ID: {away_team_id}, Home Team ID: {home_team_id}")
        st.write(f"Config Season: {pf.CURRENT_SEASON}")
        
        # Test the API call directly with multiple seasons
        seasons_to_try = [pf.CURRENT_SEASON, "2024-25", "2023-24"]
        for test_season in seasons_to_try:
            try:
                test_logs_away = pf.get_team_game_logs(away_team_id, test_season)
                test_logs_home = pf.get_team_game_logs(home_team_id, test_season)
                st.write(f"**Season {test_season}:**")
                st.write(f"  - Away team logs: {len(test_logs_away)}")
                st.write(f"  - Home team logs: {len(test_logs_home)}")
                if len(test_logs_away) > 0:
                    st.write(f"  - Away columns: {test_logs_away.columns.tolist()[:5]}...")
                if len(test_logs_home) > 0:
                    st.write(f"  - Home columns: {test_logs_home.columns.tolist()[:5]}...")
            except Exception as e:
                st.write(f"  - Error with {test_season}: {str(e)}")
    
    # Create two columns for display
    game_logs_cols = st.columns(2)
    
    # Helper function to style game logs dataframe
    def style_game_logs(df):
        """Apply conditional row highlighting based on Outcome"""
        def highlight_row(row):
            if row['Outcome'] == 'W':
                return ['background-color: #d4edda'] * len(row)  # Light green
            elif row['Outcome'] == 'L':
                return ['background-color: #f8d7da'] * len(row)  # Light red
            else:
                return [''] * len(row)
        
        if len(df) > 0 and 'Outcome' in df.columns:
            return df.style.apply(highlight_row, axis=1)
        return df
    
    # Column configuration for game logs dataframe
    game_logs_column_config = {
        "Opponent": st.column_config.ImageColumn("Opp", width=60),
        "H/A": st.column_config.TextColumn("H/A", width=50),
        "Date": st.column_config.TextColumn("Date", width=70),
        "Outcome": st.column_config.TextColumn("Outcome", width=70),
        "Final Score": st.column_config.TextColumn("Score", width=80),
        "FG%": st.column_config.TextColumn("FG%", width=60),
        "2PT%": st.column_config.TextColumn("2PT%", width=60),
        "3PT%": st.column_config.TextColumn("3PT%", width=60),
        "REB": st.column_config.NumberColumn("REB", format="%d", width=50),
        "AST": st.column_config.NumberColumn("AST", format="%d", width=50),
        "TO": st.column_config.NumberColumn("TO", format="%d", width=50),
        "STL": st.column_config.NumberColumn("STL", format="%d", width=50),
        "BLK": st.column_config.NumberColumn("BLK", format="%d", width=50),
    }
    
    with game_logs_cols[0]:
        st.markdown(f"#### {away_abbr}")
        if len(away_last_10) > 0:
            styled_df = style_game_logs(away_last_10)
            st.dataframe(
                styled_df,
                width='stretch',
                hide_index=True,
                column_config=game_logs_column_config
            )
        else:
            st.caption("No game logs available")
            st.info(f"Team ID: {away_team_id}, Season: {pf.CURRENT_SEASON}")
    
    with game_logs_cols[1]:
        st.markdown(f"#### {home_abbr}")
        if len(home_last_10) > 0:
            styled_df = style_game_logs(home_last_10)
            st.dataframe(
                styled_df,
                width='stretch',
                hide_index=True,
                column_config=game_logs_column_config
            )
        else:
            st.caption("No game logs available")
            st.info(f"Team ID: {home_team_id}, Season: {pf.CURRENT_SEASON}")
    
    st.markdown("---")
    
    # ============================================================
    # SYNERGY PLAYTYPE MATCHUPS SECTION
    # ============================================================
    st.markdown("### 🎯 Synergy Playtype Matchups")
    
    try:
        # Build synergy dataframes
        with st.spinner("Loading synergy data..."):
            away_offense_df, away_defense_df, home_offense_df, home_defense_df = build_synergy_matchup_dataframes(
                away_team_id, home_team_id, pf.CURRENT_SEASON
            )
        
        # Helper function to style offense rows based on rank (green for 1st, red for 30th)
        def style_synergy_offense(row):
            """Apply background color based on rank: green (1st) to red (30th)"""
            styles = [''] * len(row)
            
            # Get rank value
            rank = row.get('Rank', 30)
            try:
                rank = float(rank)
                if pd.isna(rank) or rank == 0 or rank < 1:
                    rank = 30
                elif rank > 30:
                    rank = 30
            except (ValueError, TypeError):
                rank = 30
            
            # Normalize rank to 0-1 scale (1st = 0.0, 30th = 1.0)
            normalized = (rank - 1) / 29.0 if rank > 1 else 0.0
            
            # Color gradient: Green (rank 1) -> Yellow (neutral) -> Red (rank 30)
            if normalized < 0.5:
                # Green to Yellow (best to neutral)
                r = int(255 * (normalized * 2))  # 0 -> 255
                g = 255
                b = 100
            else:
                # Yellow to Red (neutral to worst)
                r = 255
                g = int(255 * (1 - (normalized - 0.5) * 2))  # 255 -> 0
                b = 100
            
            # Apply background color with rgba and 0.3 opacity
            bg_color = f'background-color: rgba({r}, {g}, {b}, 0.3);'
            for i in range(len(styles)):
                styles[i] = bg_color
            
            return styles
        
        # Helper function to style defense rows based on rank (green for 1st, red for 30th)
        def style_synergy_defense(row):
            """Apply background color based on rank: green (rank 1 = best defense) to red (rank 30 = worst defense)"""
            styles = [''] * len(row)
            
            # Get rank value (rank 1 = best defense/lowest PPP, rank 30 = worst defense/highest PPP)
            rank = row.get('Rank', 30)
            try:
                rank = float(rank)
                if pd.isna(rank) or rank == 0 or rank < 1:
                    rank = 30
                elif rank > 30:
                    rank = 30
            except (ValueError, TypeError):
                rank = 30
            
            # Normalize rank to 0-1 scale (1st = 0.0, 30th = 1.0)
            normalized = (rank - 1) / 29.0 if rank > 1 else 0.0
            
            # Color gradient: Green (rank 1) -> Yellow (neutral) -> Red (rank 30)
            if normalized < 0.5:
                # Green to Yellow (best to neutral)
                r = int(255 * (normalized * 2))  # 0 -> 255
                g = 255
                b = 100
            else:
                # Yellow to Red (neutral to worst)
                r = 255
                g = int(255 * (1 - (normalized - 0.5) * 2))  # 255 -> 0
                b = 100
            
            # Apply background color with rgba and 0.3 opacity
            bg_color = f'background-color: rgba({r}, {g}, {b}, 0.3);'
            for i in range(len(styles)):
                styles[i] = bg_color
            
            return styles
        
        # Column configuration for synergy dataframes
        synergy_column_config = {
            "Playtype": st.column_config.TextColumn("Playtype", width=120),
            "PPP": st.column_config.NumberColumn("PPP", format="%.2f", width=80),
            "Rank": st.column_config.NumberColumn("Rank", format="%d", width=70),
            "Percentile": st.column_config.NumberColumn("Percentile", format="%.3f", width=100),
            "Freq Rank": st.column_config.NumberColumn("Freq Rank", format="%d", width=90),
            "Freq": st.column_config.NumberColumn("Freq", format="%.1f%%", width=80),
            "eFG%": st.column_config.NumberColumn("eFG%", format="%.1f%%", width=80),
            "Score %": st.column_config.NumberColumn("Score %", format="%.1f%%", width=100),
        }
        
        # Apply styling to all dataframes (offense and defense both use rank)
        styled_away_offense = away_offense_df.style.apply(style_synergy_offense, axis=1) if len(away_offense_df) > 0 else None
        styled_away_defense = away_defense_df.style.apply(style_synergy_defense, axis=1) if len(away_defense_df) > 0 else None
        styled_home_offense = home_offense_df.style.apply(style_synergy_offense, axis=1) if len(home_offense_df) > 0 else None
        styled_home_defense = home_defense_df.style.apply(style_synergy_defense, axis=1) if len(home_defense_df) > 0 else None
        
        # Create two columns for 2x2 layout
        synergy_cols = st.columns(2)
        
        # Left column, top: Away Offense
        with synergy_cols[0]:
            st.markdown(f"#### {away_abbr} Offense")
            if styled_away_offense is not None:
                st.dataframe(
                    styled_away_offense,
                    width='stretch',
                    hide_index=True,
                    column_config=synergy_column_config
                )
            else:
                st.caption("No offensive synergy data available")
        
        # Right column, top: Home Defense
        with synergy_cols[1]:
            st.markdown(f"#### {home_abbr} Defense")
            if styled_home_defense is not None:
                st.dataframe(
                    styled_home_defense,
                    width='stretch',
                    hide_index=True,
                    column_config=synergy_column_config
                )
            else:
                st.caption("No defensive synergy data available")
        
        st.markdown("")  # Spacing between rows
        
        # Create new columns for bottom row
        synergy_cols_bottom = st.columns(2)
        
        # Left column, bottom: Away Defense
        with synergy_cols_bottom[0]:
            st.markdown(f"#### {away_abbr} Defense")
            if styled_away_defense is not None:
                st.dataframe(
                    styled_away_defense,
                    width='stretch',
                    hide_index=True,
                    column_config=synergy_column_config
                )
            else:
                st.caption("No defensive synergy data available")
        
        # Right column, bottom: Home Offense
        with synergy_cols_bottom[1]:
            st.markdown(f"#### {home_abbr} Offense")
            if styled_home_offense is not None:
                st.dataframe(
                    styled_home_offense,
                    width='stretch',
                    hide_index=True,
                    column_config=synergy_column_config
                )
            else:
                st.caption("No offensive synergy data available")
    
    except Exception as e:
        st.error(f"Error loading synergy data: {str(e)}")
        st.info("Synergy data may not be available for the current season. Trying fallback season...")
        try:
            # Try fallback season
            with st.spinner("Loading synergy data (fallback season)..."):
                away_offense_df, away_defense_df, home_offense_df, home_defense_df = build_synergy_matchup_dataframes(
                    away_team_id, home_team_id, "2024-25"
                )
            
            # Helper function to style offense rows based on rank (green for 1st, red for 30th)
            def style_synergy_offense(row):
                """Apply background color based on rank: green (1st) to red (30th)"""
                styles = [''] * len(row)
                
                # Get rank value
                rank = row.get('Rank', 30)
                try:
                    rank = float(rank)
                    if pd.isna(rank) or rank == 0 or rank < 1:
                        rank = 30
                    elif rank > 30:
                        rank = 30
                except (ValueError, TypeError):
                    rank = 30
                
                # Normalize rank to 0-1 scale (1st = 0.0, 30th = 1.0)
                normalized = (rank - 1) / 29.0 if rank > 1 else 0.0
                
                # Color gradient: Green (rank 1) -> Yellow (neutral) -> Red (rank 30)
                if normalized < 0.5:
                    # Green to Yellow (best to neutral)
                    r = int(255 * (normalized * 2))  # 0 -> 255
                    g = 255
                    b = 100
                else:
                    # Yellow to Red (neutral to worst)
                    r = 255
                    g = int(255 * (1 - (normalized - 0.5) * 2))  # 255 -> 0
                    b = 100
                
                # Apply background color with rgba and 0.3 opacity
                bg_color = f'background-color: rgba({r}, {g}, {b}, 0.3);'
                for i in range(len(styles)):
                    styles[i] = bg_color
                
                return styles
            
            # Helper function to style defense rows based on rank (green for 1st, red for 30th)
            def style_synergy_defense(row):
                """Apply background color based on rank: green (rank 1 = best defense) to red (rank 30 = worst defense)"""
                styles = [''] * len(row)
                
                # Get rank value (rank 1 = best defense/lowest PPP, rank 30 = worst defense/highest PPP)
                rank = row.get('Rank', 30)
                try:
                    rank = float(rank)
                    if pd.isna(rank) or rank == 0 or rank < 1:
                        rank = 30
                    elif rank > 30:
                        rank = 30
                except (ValueError, TypeError):
                    rank = 30
                
                # Normalize rank to 0-1 scale (1st = 0.0, 30th = 1.0)
                normalized = (rank - 1) / 29.0 if rank > 1 else 0.0
                
                # Color gradient: Green (rank 1) -> Yellow (neutral) -> Red (rank 30)
                if normalized < 0.5:
                    # Green to Yellow (best to neutral)
                    r = int(255 * (normalized * 2))  # 0 -> 255
                    g = 255
                    b = 100
                else:
                    # Yellow to Red (neutral to worst)
                    r = 255
                    g = int(255 * (1 - (normalized - 0.5) * 2))  # 255 -> 0
                    b = 100
                
                # Apply background color with rgba and 0.3 opacity
                bg_color = f'background-color: rgba({r}, {g}, {b}, 0.3);'
                for i in range(len(styles)):
                    styles[i] = bg_color
                
                return styles
            
            # Column configuration for synergy dataframes
            synergy_column_config = {
                "Playtype": st.column_config.TextColumn("Playtype", width=120),
                "PPP": st.column_config.NumberColumn("PPP", format="%.2f", width=80),
                "Rank": st.column_config.NumberColumn("Rank", format="%d", width=70),
                "Percentile": st.column_config.NumberColumn("Percentile", format="%.3f", width=100),
                "Freq Rank": st.column_config.NumberColumn("Freq Rank", format="%d", width=90),
                "Freq": st.column_config.NumberColumn("Freq", format="%.1f%%", width=80),
                "eFG%": st.column_config.NumberColumn("eFG%", format="%.1f%%", width=80),
                "Score %": st.column_config.NumberColumn("Score %", format="%.1f%%", width=100),
            }
            
            # Apply styling to all dataframes (offense and defense both use rank)
            styled_away_offense = away_offense_df.style.apply(style_synergy_offense, axis=1) if len(away_offense_df) > 0 else None
            styled_away_defense = away_defense_df.style.apply(style_synergy_defense, axis=1) if len(away_defense_df) > 0 else None
            styled_home_offense = home_offense_df.style.apply(style_synergy_offense, axis=1) if len(home_offense_df) > 0 else None
            styled_home_defense = home_defense_df.style.apply(style_synergy_defense, axis=1) if len(home_defense_df) > 0 else None
            
            # Create two columns for 2x2 layout
            synergy_cols = st.columns(2)
            
            # Left column, top: Away Offense
            with synergy_cols[0]:
                st.markdown(f"#### {away_abbr} Offense")
                if styled_away_offense is not None:
                    st.dataframe(styled_away_offense, width='stretch', hide_index=True, column_config=synergy_column_config)
                else:
                    st.caption("No offensive synergy data available")
            
            # Right column, top: Home Defense
            with synergy_cols[1]:
                st.markdown(f"#### {home_abbr} Defense")
                if styled_home_defense is not None:
                    st.dataframe(styled_home_defense, width='stretch', hide_index=True, column_config=synergy_column_config)
                else:
                    st.caption("No defensive synergy data available")
            
            st.markdown("")  # Spacing between rows
            
            # Create new columns for bottom row
            synergy_cols_bottom = st.columns(2)
            
            # Left column, bottom: Away Defense
            with synergy_cols_bottom[0]:
                st.markdown(f"#### {away_abbr} Defense")
                if styled_away_defense is not None:
                    st.dataframe(styled_away_defense, width='stretch', hide_index=True, column_config=synergy_column_config)
                else:
                    st.caption("No defensive synergy data available")
            
            # Right column, bottom: Home Offense
            with synergy_cols_bottom[1]:
                st.markdown(f"#### {home_abbr} Offense")
                if styled_home_offense is not None:
                    st.dataframe(styled_home_offense, width='stretch', hide_index=True, column_config=synergy_column_config)
                else:
                    st.caption("No offensive synergy data available")
        except Exception as e2:
            st.error(f"Error loading synergy data (fallback also failed): {str(e2)}")
            st.info("Synergy data is currently unavailable. Please try again later.")
    
    # ============================================================
    # QUARTER-BY-QUARTER RATINGS SECTION
    # ============================================================
    st.markdown("### 📊 Quarter-by-Quarter Ratings")
    
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_quarter_ratings(season: str = '2025-26', period: int = None):
        """Fetch team ratings for a specific quarter/period"""
        try:
            params = {
                'league_id_nullable': '00',
                'measure_type_detailed_defense': 'Advanced',
                'pace_adjust': 'N',
                'per_mode_detailed': 'PerGame',
                'season': season,
                'season_type_all_star': 'Regular Season'
            }
            if period:
                params['period'] = period
            
            df = nba_api.stats.endpoints.LeagueDashTeamStats(**params).get_data_frames()[0]
            
            # Add ranking columns
            df['OFF_RATING_RANK'] = df['OFF_RATING'].rank(ascending=False, method='first').astype(int)
            df['DEF_RATING_RANK'] = df['DEF_RATING'].rank(ascending=True, method='first').astype(int)
            df['NET_RATING_RANK'] = df['NET_RATING'].rank(ascending=False, method='first').astype(int)
            
            return df
        except Exception as e:
            print(f"Error fetching quarter {period} ratings: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    try:
        # Fetch ratings for each quarter
        with st.spinner("Loading quarter-by-quarter ratings..."):
            q1_ratings = get_quarter_ratings(period=1)
            q2_ratings = get_quarter_ratings(period=2)
            q3_ratings = get_quarter_ratings(period=3)
            q4_ratings = get_quarter_ratings(period=4)
        
        # Helper function to get team rating
        def get_team_rating(df, team_id, rating_type):
            """Get rating value for a team"""
            if df.empty or team_id is None:
                return None, None
            team_data = df[df['TEAM_ID'] == team_id]
            if len(team_data) == 0:
                return None, None
            rating_col = rating_type
            rank_col = f"{rating_type}_RANK"
            rating_val = team_data[rating_col].values[0] if rating_col in team_data.columns else None
            rank_val = team_data[rank_col].values[0] if rank_col in team_data.columns else None
            return rating_val, rank_val
        
        # Build dataframes for away and home teams
        # Columns: Q1, Q2, Q3, Q4
        # Rows: ORTG, ORTG RANK, DRTG, DRTG RANK, NET, NET RANK
        
        # Format values - ensure proper types
        def fmt_val(val):
            """Round rating values to 1 decimal place"""
            if val is None:
                return None
            try:
                return round(float(val), 1)
            except (ValueError, TypeError):
                return None
        
        def fmt_rank(val):
            """Convert rank values to integers"""
            if val is None:
                return None
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return None
        
        # Initialize data lists
        away_rows = []
        home_rows = []
        
        metrics = ['ORTG', 'ORTG RANK', 'DRTG', 'DRTG RANK', 'NET', 'NET RANK']
        
        # Collect data for each quarter
        away_q1_data = []
        away_q2_data = []
        away_q3_data = []
        away_q4_data = []
        
        home_q1_data = []
        home_q2_data = []
        home_q3_data = []
        home_q4_data = []
        
        for q_num, q_df in [(1, q1_ratings), (2, q2_ratings), (3, q3_ratings), (4, q4_ratings)]:
            # Away team
            away_ortg, away_ortg_rank = get_team_rating(q_df, away_team_id, 'OFF_RATING')
            away_drtg, away_drtg_rank = get_team_rating(q_df, away_team_id, 'DEF_RATING')
            away_net, away_net_rank = get_team_rating(q_df, away_team_id, 'NET_RATING')
            
            # Home team
            home_ortg, home_ortg_rank = get_team_rating(q_df, home_team_id, 'OFF_RATING')
            home_drtg, home_drtg_rank = get_team_rating(q_df, home_team_id, 'DEF_RATING')
            home_net, home_net_rank = get_team_rating(q_df, home_team_id, 'NET_RATING')
            
            # Store quarter data
            if q_num == 1:
                away_q1_data = [fmt_val(away_ortg), fmt_rank(away_ortg_rank), fmt_val(away_drtg), fmt_rank(away_drtg_rank), fmt_val(away_net), fmt_rank(away_net_rank)]
                home_q1_data = [fmt_val(home_ortg), fmt_rank(home_ortg_rank), fmt_val(home_drtg), fmt_rank(home_drtg_rank), fmt_val(home_net), fmt_rank(home_net_rank)]
            elif q_num == 2:
                away_q2_data = [fmt_val(away_ortg), fmt_rank(away_ortg_rank), fmt_val(away_drtg), fmt_rank(away_drtg_rank), fmt_val(away_net), fmt_rank(away_net_rank)]
                home_q2_data = [fmt_val(home_ortg), fmt_rank(home_ortg_rank), fmt_val(home_drtg), fmt_rank(home_drtg_rank), fmt_val(home_net), fmt_rank(home_net_rank)]
            elif q_num == 3:
                away_q3_data = [fmt_val(away_ortg), fmt_rank(away_ortg_rank), fmt_val(away_drtg), fmt_rank(away_drtg_rank), fmt_val(away_net), fmt_rank(away_net_rank)]
                home_q3_data = [fmt_val(home_ortg), fmt_rank(home_ortg_rank), fmt_val(home_drtg), fmt_rank(home_drtg_rank), fmt_val(home_net), fmt_rank(home_net_rank)]
            elif q_num == 4:
                away_q4_data = [fmt_val(away_ortg), fmt_rank(away_ortg_rank), fmt_val(away_drtg), fmt_rank(away_drtg_rank), fmt_val(away_net), fmt_rank(away_net_rank)]
                home_q4_data = [fmt_val(home_ortg), fmt_rank(home_ortg_rank), fmt_val(home_drtg), fmt_rank(home_drtg_rank), fmt_val(home_net), fmt_rank(home_net_rank)]
        
        # Build dataframes row by row
        away_rows = []
        home_rows = []
        
        for i, metric in enumerate(metrics):
            away_rows.append({
                'Metric': metric,
                'Q1': away_q1_data[i] if i < len(away_q1_data) else None,
                'Q2': away_q2_data[i] if i < len(away_q2_data) else None,
                'Q3': away_q3_data[i] if i < len(away_q3_data) else None,
                'Q4': away_q4_data[i] if i < len(away_q4_data) else None
            })
            home_rows.append({
                'Metric': metric,
                'Q1': home_q1_data[i] if i < len(home_q1_data) else None,
                'Q2': home_q2_data[i] if i < len(home_q2_data) else None,
                'Q3': home_q3_data[i] if i < len(home_q3_data) else None,
                'Q4': home_q4_data[i] if i < len(home_q4_data) else None
            })
        
        # Create dataframes
        away_quarter_df = pd.DataFrame(away_rows)
        home_quarter_df = pd.DataFrame(home_rows)
        
        # Format dataframes: ratings to 1 decimal, ranks to integers
        def format_dataframe_for_display(df):
            """Format dataframe: ratings to 1 decimal, ranks to integers"""
            df_formatted = df.copy()
            for idx, row in df_formatted.iterrows():
                metric = row['Metric']
                if 'RANK' in metric:
                    # Convert rank columns to integers (store as int, pandas will handle display)
                    for col in ['Q1', 'Q2', 'Q3', 'Q4']:
                        val = row[col]
                        if val is not None:
                            try:
                                # Store as integer - pandas will convert to float in mixed column
                                # but we'll format for display
                                int_val = int(float(val))
                                df_formatted.at[idx, col] = int_val
                            except (ValueError, TypeError):
                                pass
                else:
                    # Ensure rating columns are rounded to 1 decimal
                    for col in ['Q1', 'Q2', 'Q3', 'Q4']:
                        val = row[col]
                        if val is not None:
                            try:
                                df_formatted.at[idx, col] = round(float(val), 1)
                            except (ValueError, TypeError):
                                pass
            return df_formatted
        
        # Format dataframes before styling
        away_quarter_df = format_dataframe_for_display(away_quarter_df)
        home_quarter_df = format_dataframe_for_display(home_quarter_df)
        
        # Helper function to get color for a rank value (same as synergy tables)
        def get_rank_color(rank):
            """Get background color based on rank (1-30 scale, same as synergy tables)"""
            try:
                rank_val = float(rank)
                if pd.isna(rank_val) or rank_val == 0 or rank_val < 1:
                    rank_val = 30
                elif rank_val > 30:
                    rank_val = 30
            except (ValueError, TypeError):
                rank_val = 30
            
            # Normalize rank to 0-1 scale (1st = 0.0, 30th = 1.0)
            normalized = (rank_val - 1) / 29.0 if rank_val > 1 else 0.0
            
            # Color gradient: Green (rank 1) -> Yellow (neutral) -> Red (rank 30)
            if normalized < 0.5:
                # Green to Yellow (best to neutral)
                r = int(255 * (normalized * 2))  # 0 -> 255
                g = 255
                b = 100
            else:
                # Yellow to Red (neutral to worst)
                r = 255
                g = int(255 * (1 - (normalized - 0.5) * 2))  # 255 -> 0
                b = 100
            
            return f'background-color: rgba({r}, {g}, {b}, 0.3);'
        
        # Function to style columns based on NET RANK values
        def style_quarter_columns(df):
            """Style columns based on NET RANK row values"""
            # Find the NET RANK row
            net_rank_row_idx = None
            for idx, row in df.iterrows():
                if row['Metric'] == 'NET RANK':
                    net_rank_row_idx = idx
                    break
            
            if net_rank_row_idx is None:
                return df.style  # No styling if NET RANK row not found
            
            # Get NET RANK values for each quarter (handle string values)
            net_ranks = {}
            for col in ['Q1', 'Q2', 'Q3', 'Q4']:
                rank_val = df.at[net_rank_row_idx, col]
                # Convert string to number if needed
                try:
                    if isinstance(rank_val, str):
                        rank_val = float(rank_val)
                    else:
                        rank_val = float(rank_val)
                except (ValueError, TypeError):
                    rank_val = 30  # Default to worst rank
                net_ranks[col] = rank_val
            
            # Create styling function that applies column colors
            def style_by_column(series):
                """Apply column color based on NET RANK"""
                col_name = series.name
                if col_name in net_ranks:
                    rank = net_ranks[col_name]
                    bg_color = get_rank_color(rank)
                    # Return the same color for all cells in this column
                    return [bg_color] * len(series)
                return [''] * len(series)
            
            # Apply column-based styling
            styled_df = df.style.apply(style_by_column, axis=0, subset=['Q1', 'Q2', 'Q3', 'Q4'])
            
            return styled_df
        
        # Format values as strings for display: ratings to 1 decimal, ranks as integers
        def format_cell_value(val, is_rank=False):
            """Format cell value for display"""
            if val is None or pd.isna(val):
                return ""
            try:
                if is_rank:
                    return str(int(float(val)))
                else:
                    return f"{float(val):.1f}"
            except (ValueError, TypeError):
                return str(val) if val is not None else ""
        
        # Create formatted display dataframes (strings) but keep numeric for styling
        away_display_df = away_quarter_df.copy()
        home_display_df = home_quarter_df.copy()
        
        for idx, row in away_display_df.iterrows():
            metric = row['Metric']
            is_rank = 'RANK' in metric
            for col in ['Q1', 'Q2', 'Q3', 'Q4']:
                val = row[col]
                away_display_df.at[idx, col] = format_cell_value(val, is_rank)
        
        for idx, row in home_display_df.iterrows():
            metric = row['Metric']
            is_rank = 'RANK' in metric
            for col in ['Q1', 'Q2', 'Q3', 'Q4']:
                val = row[col]
                home_display_df.at[idx, col] = format_cell_value(val, is_rank)
        
        # Apply column-based styling based on NET RANK values
        styled_away_quarter = style_quarter_columns(away_display_df) if len(away_display_df) > 0 else None
        styled_home_quarter = style_quarter_columns(home_display_df) if len(home_display_df) > 0 else None
        
        # Column configuration - use TextColumn for formatted string values
        quarter_column_config = {
            "Metric": st.column_config.TextColumn("Metric", width=120),
            "Q1": st.column_config.TextColumn("Q1", width=80),
            "Q2": st.column_config.TextColumn("Q2", width=80),
            "Q3": st.column_config.TextColumn("Q3", width=80),
            "Q4": st.column_config.TextColumn("Q4", width=80),
        }
        
        # Create two columns for side-by-side display
        quarter_cols = st.columns(2)
        
        # Left column: Away team
        with quarter_cols[0]:
            st.markdown(f"#### {away_abbr}")
            if styled_away_quarter is not None:
                st.dataframe(
                    styled_away_quarter,
                    width='stretch',
                    hide_index=True,
                    column_config=quarter_column_config
                )
            else:
                st.caption("No quarter-by-quarter ratings data available")
        
        # Right column: Home team
        with quarter_cols[1]:
            st.markdown(f"#### {home_abbr}")
            if styled_home_quarter is not None:
                st.dataframe(
                    styled_home_quarter,
                    width='stretch',
                    hide_index=True,
                    column_config=quarter_column_config
                )
            else:
                st.caption("No quarter-by-quarter ratings data available")
    
    except Exception as e:
        st.error(f"Error loading quarter-by-quarter ratings: {str(e)}")
        st.info("Quarter-by-quarter ratings may not be available. Please try again later.")
    
    st.markdown("---")
    
    # Tab selector (Core Stats, Shooting, Rosters, Injury Report)
    tab1, tab2, tab3, tab4 = st.tabs(["Core Stats", "Shooting", "Rosters", "Injury Report"])

    stat_font_size = 20
    rank_font_size = 16
    border = 1
    padding = 8
    border_radius = 5
    title_header_background_color = 'f9f9f9'
    body_header_background_color = 'f9f9f9'
    body_background_color = 'white'

    with tab1:

        # Create the HTML for the header
        header_html = f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: {padding}px; border: 1px solid black; background-color: #{body_header_background_color}; font-family: Arial, sans-serif;">
          <!-- Away Team Logo -->
          <a href="{functions.away_logo_link}" style="display: inline-block;">
            <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 150px; width: auto;" />
          </a>
        
          <!-- Team Names -->
          <div style="display: flex; flex-direction: column; align-items: center; flex-grow: 1; text-align: center;">
            <span style="font-size: 30px; font-weight: bold;">{functions.game_title}</span>
          </div>
        
          <!-- Home Team Logo -->
          <a href="{functions.home_logo_link}" style="display: inline-block;">
            <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 150px; width: auto;" />
          </a>
        </div>
        <br>
        """
        # Render the HTML in Streamlit
        st.markdown(header_html, unsafe_allow_html=True)

        # Create the HTML table with column spanners
        html_table_2 = f"""
    <table style="width:75%; border: {border}px solid black; border-collapse: collapse; text-align: center; table-layout: fixed;">
      <colgroup>
        <col style="width: 25%;">  <!-- Metric -->
        <col style="width: 14.5%;">  <!-- Away Season -->
        <col style="width: 14.5%;">  <!-- Away Last 5 -->
        <col style="width: 17%;">  <!-- League Average -->
        <col style="width: 14.5%;">  <!-- Home Season -->
        <col style="width: 14.5%;">  <!-- Home Last 5 -->
      </colgroup>
      <thead>
        <!-- First sticky row -->
        <tr>
          <th style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;"></th>
          <th colspan="2" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 100px; width: auto;"/>
          </th>
          <th colspan="1" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{functions.nba_logo}" alt="NBA Team Logo" style="height: 100px; width: auto;"/>
          </th>
          <th colspan="2" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
              <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 100px; width: auto;"/>
          </th>
        </tr>
        <!-- Second sticky row -->
        <tr>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Metric</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Season</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Last 5</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">League Average</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Season</th>
          <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;">Last 5</th>
        </tr>
      </thead>
      <tbody>
      <tr>
        <td style="border: {border}px solid black;">Offensive Rating</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ortg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_ortg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_ortg}</strong></p>
        </td>
         <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ortg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_ortg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_ortg_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Defensive Rating</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_drtg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_drtg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_drtg}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_drtg_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_drtg}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_drtg_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Net Rating</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_net_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_net_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_net}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_net_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_net}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_net_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Offensive Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_oreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_oreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_oreb*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_oreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_oreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_oreb_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Defensive Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_dreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_dreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_dreb*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_dreb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_dreb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_dreb_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Rebound %</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_reb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_reb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_reb*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_reb_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: {border_radius}px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_reb*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_reb_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pitp_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pitp_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pitp_off}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pitp_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pitp_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pitp_off_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pitp_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pitp_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pitp_def}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pitp_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pitp_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pitp_def_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points in the Paint - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pitp_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pitp_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pitp_diff}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pitp_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pitp_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pitp_diff_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2c_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_2c_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_2c_off}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2c_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_2c_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_2c_off_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2c_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_2c_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_2c_def}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2c_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_2c_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_2c_def_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">2nd Chance Points - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2c_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_2c_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_2c_diff}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2c_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_2c_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_2c_diff_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Offense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fb_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_fb_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_fb_off}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fb_off_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_fb_off}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_fb_off_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Defense</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fb_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_fb_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_fb_def}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fb_def_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_fb_def}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_fb_def_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Fast Break Points - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fb_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_fb_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_fb_diff}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fb_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_fb_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_fb_diff_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Pace</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pace_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pace_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pace}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pace_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pace}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pace_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assists</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ast_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_ast_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_ast}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ast_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_ast}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_ast_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assist Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ast_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_ast_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_ast_pct*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ast_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_ast_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_ast_pct_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_tov}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_tov_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Turnover Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_tov_pct*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_tov_pct_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Opp. Turnover Percentage</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_away_team_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_opp_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{round(functions.l5_la_opp_tov_pct*100, 3)}%</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_tov_pct_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.l5_home_team_opp_tov_pct*100, 3)}%</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_opp_tov_pct_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Assist-to-Turnover Ratio</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ast_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_ast_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_ast_tov}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ast_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_ast_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_ast_tov_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points off Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pts_off_tov}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pts_off_tov_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Opp. Points off Turnovers</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_opp_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_opp_pts_off_tov}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_pts_off_tov_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_opp_pts_off_tov}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_opp_pts_off_tov_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Points off Turnovers - Differential</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_pts_off_tov_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_pts_off_tov_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_pts_off_tov_diff}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_pts_off_tov_diff_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_pts_off_tov_diff}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_pts_off_tov_diff_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Starters Scoring</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_starters_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_starters_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_starters_scoring}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_starters_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_starters_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_starters_scoring_rank}</strong></p>
        </td>
      </tr>
      <tr>
        <td style="border: {border}px solid black;">Bench Scoring</td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_bench_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_away_team_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_away_team_bench_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">L5: <strong>{functions.l5_la_bench_scoring}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_bench_scoring_rank}</strong></p>
        </td>
        <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.l5_home_team_bench_scoring}</strong></p>
                <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.l5_home_team_bench_scoring_rank}</strong></p>
        </td>
      </tr>  
      </tbody>
    </table>
        """

        # Render the table in Streamlit
        st.markdown(html_table_2, unsafe_allow_html=True)

    with tab2:

        # Create the HTML for the header
        header_html_shooting = f"""
        <div style="display: flex; align-items: center; justify-content: space-between; padding: {padding}px; border: 1px solid black; background-color: #{body_header_background_color}; font-family: Arial, sans-serif;">
          <!-- Away Team Logo -->
          <a href="{functions.away_logo_link}" style="display: inline-block;">
            <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 150px; width: auto;" />
          </a>

          <!-- Team Names -->
          <div style="display: flex; flex-direction: column; align-items: center; flex-grow: 1; text-align: center;">
            <span style="font-size: 30px; font-weight: bold;">{functions.game_title}</span>
          </div>

          <!-- Home Team Logo -->
          <a href="{functions.home_logo_link}" style="display: inline-block;">
            <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 150px; width: auto;" />
          </a>
        </div>
        <br>
        """
        # Render the HTML in Streamlit
        st.markdown(header_html_shooting, unsafe_allow_html=True)

        html_table_shooting = f"""
        <table style="width:100%; border: {border}px solid black; border-collapse: collapse; text-align: center; table-layout: fixed;">
          <colgroup>
            <col style="width: 16.05%;">  <!-- Metric (130px / 810px * 100%) -->
            <col style="width: 12.35%;">  <!-- Away Team (100px / 810px * 100%) -->
            <col style="width: 12.35%;">  <!-- Away Opponent (100px / 810px * 100%) -->
            <col style="width: 12.35%;">  <!-- Away Difference (100px / 810px * 100%) -->
            <col style="width: 9.88%;">  <!-- League Average (80px / 810px * 100%) -->
            <col style="width: 12.35%;">  <!-- Home Team (100px / 810px * 100%) -->
            <col style="width: 12.35%;">  <!-- Home Opponent (100px / 810px * 100%) -->
            <col style="width: 12.32%;">  <!-- Home Difference (100px / 810px * 100%, rounded) -->
          </colgroup>
          <thead>
            <!-- First sticky row -->
                <tr>
                  <th style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: middle; box-shadow: 0px 2px 0px 0px black;"></th>
                  <th colspan="3" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
                      <img src="{functions.away_logo_link}" alt="Away Team Logo" style="height: 100px; width: auto;"/>
                  </th>
                  <th colspan="1" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
                      <img src="{functions.nba_logo}" alt="NBA Team Logo" style="height: 100px; width: auto;"/>
                  </th>
                  <th colspan="3" style="border: 1px solid black; background-color: #{body_header_background_color}; position: sticky; top: 0; z-index: 3; height: 175px; text-align: bottom; vertical-align: bottom; box-shadow: 0px 2px 0px 0px black;">
                      <img src="{functions.home_logo_link}" alt="Home Team Logo" style="height: 100px; width: auto;"/>
                  </th>
                </tr>
                <!-- Second sticky row -->
                <tr>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 130px">Metric</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px;">Team</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Opponent</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Difference</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 80px">League Average</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Team</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Opponent</th>
                  <th style="border: 1px solid black; position: sticky; top: 175px; z-index: 2; background-color: #{body_header_background_color}; text-align: center; vertical-align: middle; box-shadow: 0px 2px 0px 0px black; width: 100px">Difference</th>
                </tr>
          </thead>
          <tbody>
            <tr>
                <td style="border: {border}px solid black;">Field Goals Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fgm_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_fgm_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_fgm_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fgm}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fgm_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_fgm_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_fgm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_fgm_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fga_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_fga_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_fga_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fga}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fga_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_fga_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_fga}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_fga_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fg_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_fg_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_fg_pct_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_fg_pct*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fg_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_fg_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_fg_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_fg_pct_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goals Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2pt_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_2pt_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_2pt_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2pt}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2pt_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_2pt_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_2pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_2pt_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2pa_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_2pa_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_2pa_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_2pa}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2pa_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_2pa_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_2pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_2pa_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">2PT Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_2pt_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_2pt_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_2pt_pct_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_2pt_pct*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_2pt_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_2pt_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_2pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_2pt_pct_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goals Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_3pt_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_3pt_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_3pt_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_3pt}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_3pt_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_3pt_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_3pt}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_3pt_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goals Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_3pa_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_3pa_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_3pa_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_3pa}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_3pa_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_3pa_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_3pa}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_3pa_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">3PT Field Goal Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_3pt_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_3pt_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_3pt_pct_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_3pt_pct*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_3pt_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_3pt_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_3pt_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_3pt_pct_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throws Made</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ftm_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_ftm_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_ftm_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_ftm}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ftm_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_ftm_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_ftm}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_ftm_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throws Attempted</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_fta_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_opp_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_fta_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.away_team_diff_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_fta_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.la_fta}</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_fta_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_opp_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_fta_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{functions.home_team_diff_fta}</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_fta_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Free Throw Percentage</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_ft_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_ft_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_ft_pct_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_ft_pct*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_ft_pct_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_ft_pct_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_ft_pct*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_ft_pct_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Rim Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_rim_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_rim_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_rim_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_rim_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_rim_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_rim_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_rim_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_rim_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Rim Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_rim_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_rim_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_rim_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_rim_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_rim_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_rim_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_rim_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_rim_acc_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Short Mid-Range Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_smr_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_smr_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_smr_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_smr_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_smr_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_smr_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_smr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_smr_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Short Mid-Range Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_smr_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_smr_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_smr_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_smr_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_smr_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_smr_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_smr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_smr_acc_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Long Mid-Range Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_lmr_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_lmr_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_lmr_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_lmr_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_lmr_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_lmr_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_lmr_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_lmr_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Long Mid-Range Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_lmr_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_lmr_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_lmr_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_lmr_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_lmr_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_lmr_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_lmr_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_lmr_acc_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Above the Break 3 Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_atb3_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_atb3_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_atb3_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_atb3_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_atb3_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_atb3_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_atb3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_atb3_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Above the Break 3 Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_atb3_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_atb3_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_atb3_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_atb3_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_atb3_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_atb3_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_atb3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_atb3_acc_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Corner 3 Frequency</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_c3_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_c3_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_c3_freq_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_c3_freq*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_c3_freq_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_c3_freq_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_c3_freq*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_c3_freq_rank}</strong></p>
                </td>
            </tr>
            <tr>
                <td style="border: {border}px solid black;">Corner 3 Accuracy</td>
                <!-- Away -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_c3_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_opp_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_opp_c3_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.away_team_diff_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.away_team_diff_c3_acc_rank}</strong></p>
                </td>
                <!-- League Average -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.la_c3_acc*100, 1)}%</strong></p>
                </td>
                <!-- Home -->
                    <!-- Team -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_c3_acc_rank}</strong></p>
                </td>
                    <!-- Opponent -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_opp_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_opp_c3_acc_rank}</strong></p>
                </td>
                    <!-- Difference -->
                <td style="text-align: center; border: {border}px solid black; padding: {padding}px; border-radius: 5px; background-color: #{body_background_color};">
                        <p style="font-size: {stat_font_size}px; margin: 0;"><strong>{round(functions.home_team_diff_c3_acc*100, 1)}%</strong></p>
                        <p style="font-size: {rank_font_size}px; margin: 0;">Rank: <strong>{functions.home_team_diff_c3_acc_rank}</strong></p>
                </td>
            </tr>
          </tbody>
        </table>
        """

        # Render the table in Streamlit
        st.markdown(html_table_shooting, unsafe_allow_html=True)

    with tab3:
        # ============================================================
        # ROSTERS TAB - Player averages for both teams
        # ============================================================
        
        # Get team info for injury report
        away_team_name = selected_matchup['away_team_name']
        home_team_name = selected_matchup['home_team_name']
        away_team_id = selected_matchup['away_team_id']
        home_team_id = selected_matchup['home_team_id']
        
        # Get tricodes directly from matchup (from API) - same as Matchup Summary
        away_team_abbr = selected_matchup.get('away_team', '')
        home_team_abbr = selected_matchup.get('home_team', '')
        
        # Fallback to mapping if tricodes not available
        if not away_team_abbr or not home_team_abbr:
            team_name_to_abbr = {
                'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
                'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
                'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
                'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
                'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
                'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
                'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
                'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
                'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
                'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'
            }
            if not away_team_abbr:
                away_team_abbr = team_name_to_abbr.get(away_team_name, away_team_name.split()[-1][:3].upper())
            if not home_team_abbr:
                home_team_abbr = team_name_to_abbr.get(home_team_name, home_team_name.split()[-1][:3].upper())
        
        # Load player data first (needed for On/Off Court Summary and Player Averages)
        @st.cache_data(ttl=1800, show_spinner="Loading player data...")
        def load_roster_data():
            players_df = functions.get_players_dataframe()
            game_logs_df = functions.get_all_player_game_logs()
            return players_df, game_logs_df
        
        players_df, game_logs_df = load_roster_data()
        
        # ============================================================
        # ON/OFF COURT SUMMARY SECTION
        # ============================================================
        st.markdown("### On/Off Court Summary")
        
        try:
            
            # Fetch on/off court data for both teams
            away_onoff_data = toff.get_team_onoff_formatted(
                team_id=int(away_team_id),
                season='2025-26',
                players_df=players_df,
                min_minutes=100
            )
            
            home_onoff_data = toff.get_team_onoff_formatted(
                team_id=int(home_team_id),
                season='2025-26',
                players_df=players_df,
                min_minutes=100
            )
            
            if len(away_onoff_data) > 0 or len(home_onoff_data) > 0:
                # Helper function to create column config (shared for both teams)
                def create_onoff_column_config(df):
                    column_config = {}
                    
                    # Add headshot column if present
                    if 'headshot' in df.columns:
                        column_config['headshot'] = st.column_config.ImageColumn("", width=50)
                    
                    # Add player name column
                    if 'PLAYER_NAME' in df.columns:
                        column_config['PLAYER_NAME'] = st.column_config.TextColumn("Player", width=150)
                    
                    # Add minutes columns
                    if 'MIN_ON_COURT' in df.columns:
                        column_config['MIN_ON_COURT'] = st.column_config.NumberColumn("MIN ON", format="%.0f", width=70)
                    if 'MIN_OFF_COURT' in df.columns:
                        column_config['MIN_OFF_COURT'] = st.column_config.NumberColumn("MIN OFF", format="%.0f", width=70)
                    
                    # Add Net Rating columns
                    if 'NET_RATING_ON_COURT' in df.columns:
                        column_config['NET_RATING_ON_COURT'] = st.column_config.NumberColumn("NET ON", format="%.1f", width=70)
                    if 'NET_RATING_OFF_COURT' in df.columns:
                        column_config['NET_RATING_OFF_COURT'] = st.column_config.NumberColumn("NET OFF", format="%.1f", width=70)
                    if 'NET_RTG_DIFF' in df.columns:
                        column_config['NET_RTG_DIFF'] = st.column_config.NumberColumn("NET DIFF", format="%.1f", width=80)
                    
                    # Add Offensive Rating columns
                    if 'OFF_RATING_ON_COURT' in df.columns:
                        column_config['OFF_RATING_ON_COURT'] = st.column_config.NumberColumn("OFF ON", format="%.1f", width=70)
                    if 'OFF_RATING_OFF_COURT' in df.columns:
                        column_config['OFF_RATING_OFF_COURT'] = st.column_config.NumberColumn("OFF OFF", format="%.1f", width=70)
                    if 'OFF_RTG_DIFF' in df.columns:
                        column_config['OFF_RTG_DIFF'] = st.column_config.NumberColumn("OFF DIFF", format="%.1f", width=80)
                    
                    # Add Defensive Rating columns
                    if 'DEF_RATING_ON_COURT' in df.columns:
                        column_config['DEF_RATING_ON_COURT'] = st.column_config.NumberColumn("DEF ON", format="%.1f", width=70)
                    if 'DEF_RATING_OFF_COURT' in df.columns:
                        column_config['DEF_RATING_OFF_COURT'] = st.column_config.NumberColumn("DEF OFF", format="%.1f", width=70)
                    if 'DEF_RTG_DIFF' in df.columns:
                        column_config['DEF_RTG_DIFF'] = st.column_config.NumberColumn("DEF DIFF", format="%.1f", width=80)
                    
                    return column_config
                
                # Away Team (stacked first)
                st.markdown(f"**{away_team_name}**")
                if len(away_onoff_data) > 0:
                    column_config = create_onoff_column_config(away_onoff_data)
                    st.dataframe(
                        away_onoff_data,
                        column_config=column_config,
                        hide_index=True,
                        width='stretch'
                    )
                else:
                    st.info("No on/off court data available")
                
                st.divider()
                
                # Home Team (stacked second)
                st.markdown(f"**{home_team_name}**")
                if len(home_onoff_data) > 0:
                    column_config = create_onoff_column_config(home_onoff_data)
                    st.dataframe(
                        home_onoff_data,
                        column_config=column_config,
                        hide_index=True,
                        width='stretch'
                    )
                else:
                    st.info("No on/off court data available")
            else:
                st.info("On/off court data is currently unavailable. Please try again later.")
        
        except Exception as e:
            st.warning(f"⚠️ Could not fetch on/off court data: {str(e)}")
        
        st.divider()
        
        # ============================================================
        # PLAYER AVERAGES SECTION
        # ============================================================
        st.markdown("### Player Averages")
        
        # Map period to num_games (shared)
        period_map = {
            "Last 10 Games": 10,
            "Last 5 Games": 5,
            "Last 3 Games": 3,
            "All Games": None
        }
        
        # Column config for dataframes - use specific pixel widths for tighter columns (shared)
        column_config = {
                "headshot": st.column_config.ImageColumn("", width=85),  # Specific width for headshot
                "Player": st.column_config.TextColumn("Player", width=140),
                "Pos": st.column_config.TextColumn("Pos", width=50),
                "GP": st.column_config.NumberColumn("GP", format="%d", width=45),
                "MIN": st.column_config.NumberColumn("MIN", format="%.1f", width=50),
                "PTS": st.column_config.NumberColumn("PTS", format="%.1f", width=50),
                "REB": st.column_config.NumberColumn("REB", format="%.1f", width=50),
                "AST": st.column_config.NumberColumn("AST", format="%.1f", width=50),
                "PRA": st.column_config.NumberColumn("PRA", format="%.1f", width=50),
                "STL": st.column_config.NumberColumn("STL", format="%.1f", width=50),
                "BLK": st.column_config.NumberColumn("BLK", format="%.1f", width=50),
                "TOV": st.column_config.NumberColumn("TOV", format="%.1f", width=50),
                "FGM": st.column_config.NumberColumn("FGM", format="%.1f", width=50),
                "FPTS": st.column_config.NumberColumn("FPTS", format="%.1f", width=50),
                "FGA": st.column_config.NumberColumn("FGA", format="%.1f", width=50),
                "FG%": st.column_config.NumberColumn("FG%", format="%.1f%%", width=55),
                "3PM": st.column_config.NumberColumn("3PM", format="%.1f", width=50),
                "3PA": st.column_config.NumberColumn("3PA", format="%.1f", width=50),
                "3P%": st.column_config.NumberColumn("3P%", format="%.1f%%", width=55),
                "FTM": st.column_config.NumberColumn("FTM", format="%.1f", width=50),
                "FTA": st.column_config.NumberColumn("FTA", format="%.1f", width=50),
                "FT%": st.column_config.NumberColumn("FT%", format="%.1f%%", width=55),
            }
            
        # Display columns (exclude hidden _player_id) (shared)
        display_columns = ['headshot', 'Player', 'Pos', 'GP', 'MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', 'FGM', 'FPTS', 'FGA', 'FG%', '3PM', '3PA', '3P%', 'FTM', 'FTA', 'FT%']
        
        # Function to calculate individual player season averages (shared)
        def calculate_player_season_averages(roster_df, game_logs_df, per_mode='PerGame'):
                """
                Calculate full-season averages for each player in the roster.
                
                Args:
                    roster_df: DataFrame with player stats (must have '_player_id' column)
                    game_logs_df: DataFrame with all player game logs
                    per_mode: 'PerGame' for averages or 'Totals' for totals
                
                Returns:
                    Dictionary mapping player_id to their season averages: {player_id: {col: value, ...}}
                """
                player_season_averages = {}
                
                # Get all unique player IDs from roster
                if '_player_id' not in roster_df.columns:
                    return player_season_averages
                
                numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FGM', 'FGA', 'FG3M', 'FG3A', 'FTM', 'FTA']
                pct_cols = ['FG%', '3P%', 'FT%']
                
                for _, row in roster_df.iterrows():
                    player_id = row['_player_id']
                    
                    # Get all games for this player (full season)
                    player_logs = game_logs_df[game_logs_df['PLAYER_ID'] == player_id].copy()
                    
                    if len(player_logs) == 0:
                        continue
                    
                    # Calculate season averages/totals
                    season_avg = {}
                    
                    if per_mode == 'Totals':
                        # Calculate totals
                        for col in numeric_cols:
                            if col in player_logs.columns:
                                season_avg[col] = player_logs[col].sum()
                        
                        # Calculate percentages from totals
                        if 'FGM' in player_logs.columns and 'FGA' in player_logs.columns:
                            total_fgm = player_logs['FGM'].sum()
                            total_fga = player_logs['FGA'].sum()
                            season_avg['FG%'] = (total_fgm / total_fga * 100) if total_fga > 0 else 0.0
                        
                        if 'FG3M' in player_logs.columns and 'FG3A' in player_logs.columns:
                            total_fg3m = player_logs['FG3M'].sum()
                            total_fg3a = player_logs['FG3A'].sum()
                            season_avg['3P%'] = (total_fg3m / total_fg3a * 100) if total_fg3a > 0 else 0.0
                        
                        if 'FTM' in player_logs.columns and 'FTA' in player_logs.columns:
                            total_ftm = player_logs['FTM'].sum()
                            total_fta = player_logs['FTA'].sum()
                            season_avg['FT%'] = (total_ftm / total_fta * 100) if total_fta > 0 else 0.0
                        
                        # Calculate PRA (totals)
                        pts = season_avg.get('PTS', 0)
                        reb = season_avg.get('REB', 0)
                        ast = season_avg.get('AST', 0)
                        season_avg['PRA'] = pts + reb + ast
                        
                        # Calculate FPTS (totals)
                        fpts = (pts + reb * 1.2 + ast * 1.5 + 
                               season_avg.get('STL', 0) * 3 + 
                               season_avg.get('BLK', 0) * 3 - 
                               season_avg.get('TOV', 0))
                        season_avg['FPTS'] = fpts
                        
                        # Map column names
                        season_avg['3PM'] = season_avg.get('FG3M', 0)
                        season_avg['3PA'] = season_avg.get('FG3A', 0)
                    else:
                        # Calculate averages (PerGame)
                        for col in numeric_cols:
                            if col in player_logs.columns:
                                season_avg[col] = player_logs[col].mean()
                        
                        # Calculate percentages from totals
                        if 'FGM' in player_logs.columns and 'FGA' in player_logs.columns:
                            total_fgm = player_logs['FGM'].sum()
                            total_fga = player_logs['FGA'].sum()
                            season_avg['FG%'] = (total_fgm / total_fga * 100) if total_fga > 0 else 0.0
                        
                        if 'FG3M' in player_logs.columns and 'FG3A' in player_logs.columns:
                            total_fg3m = player_logs['FG3M'].sum()
                            total_fg3a = player_logs['FG3A'].sum()
                            season_avg['3P%'] = (total_fg3m / total_fg3a * 100) if total_fg3a > 0 else 0.0
                        
                        if 'FTM' in player_logs.columns and 'FTA' in player_logs.columns:
                            total_ftm = player_logs['FTM'].sum()
                            total_fta = player_logs['FTA'].sum()
                            season_avg['FT%'] = (total_ftm / total_fta * 100) if total_fta > 0 else 0.0
                        
                        # Calculate PRA (averages)
                        pts = season_avg.get('PTS', 0)
                        reb = season_avg.get('REB', 0)
                        ast = season_avg.get('AST', 0)
                        season_avg['PRA'] = pts + reb + ast
                        
                        # Calculate FPTS (averages)
                        fpts = (pts + reb * 1.2 + ast * 1.5 + 
                               season_avg.get('STL', 0) * 3 + 
                               season_avg.get('BLK', 0) * 3 - 
                               season_avg.get('TOV', 0))
                        season_avg['FPTS'] = fpts
                        
                        # Map column names
                        season_avg['3PM'] = season_avg.get('FG3M', 0)
                        season_avg['3PA'] = season_avg.get('FG3A', 0)
                    
                    player_season_averages[player_id] = season_avg
                
                return player_season_averages
        
        # Function to style player averages based on individual season averages (shared)
        def style_player_averages_heatmap(df, player_season_averages_dict):
                """Apply heatmap colors to player averages: light red (below avg) → gray (at avg) → light green (above avg)
                
                Args:
                    df: DataFrame with player stats (must have '_player_id' column)
                    player_season_averages_dict: Dictionary mapping player_id to their season averages
                """
                def style_row(row):
                    styles = [''] * len(row)
                    
                    # Get player ID from row
                    if '_player_id' not in row.index:
                        return styles
                    
                    player_id = row['_player_id']
                    
                    # Get this player's season averages
                    if player_id not in player_season_averages_dict:
                        return styles  # No season data for this player
                    
                    season_avg = player_season_averages_dict[player_id]
                    
                    # Columns to skip (non-numeric or identifiers)
                    skip_cols = ['headshot', 'Player', 'Pos', 'GP', '_player_id']
                    
                    # Numeric columns to style
                    numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', 'FGM', 'FPTS', 'FGA', '3PM', '3PA', 'FTM', 'FTA']
                    
                    # Percentage columns to style
                    pct_cols = ['FG%', '3P%', 'FT%']
                    
                    for i, col in enumerate(df.columns):
                        if col in skip_cols:
                            continue
                        
                        if col in numeric_cols:
                            try:
                                # Handle string values that might be formatted
                                current_val_str = str(row[col]).replace(',', '')
                                current_val = float(current_val_str)
                                
                                # Get season average for this column
                                season_val = season_avg.get(col, None)
                                if season_val is None:
                                    continue
                                
                                season_val = float(season_val)
                                
                                if current_val > season_val:
                                    # Green gradient - better than season average
                                    diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                                    intensity = min(diff_pct / 20, 1.0)  # Cap at 20% difference for max intensity
                                    green_intensity = int(200 + (55 * intensity))
                                    styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                                elif current_val < season_val:
                                    # Red gradient - worse than season average
                                    diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                                    intensity = min(diff_pct / 20, 1.0)
                                    red_intensity = int(200 + (55 * intensity))
                                    styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                                else:
                                    # Gray - same as season average
                                    styles[i] = 'background-color: rgb(240, 240, 240);'
                            except (ValueError, TypeError, KeyError):
                                pass
                        elif col in pct_cols:
                            try:
                                # Extract percentage value
                                current_str = str(row[col]).replace('%', '')
                                current_val = float(current_str)
                                
                                # Get season average for this column
                                season_val = season_avg.get(col, None)
                                if season_val is None:
                                    continue
                                
                                season_val = float(season_val)
                                
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
                            except (ValueError, TypeError, KeyError):
                                pass
                    
                    return styles
                
                return df.style.apply(style_row, axis=1)
        
        # Create tabs for Traditional and Clutch
        tab_traditional, tab_clutch = st.tabs(["Traditional", "Clutch"])
        
        with tab_traditional:
            # Period selector - default to "Last 10 Games"
            period_options = ["Last 10 Games", "Last 5 Games", "Last 3 Games", "All Games"]
            selected_period = st.selectbox(
                "Select Period:",
                options=period_options,
                index=0,  # Last 10 Games
                key="traditional_period",
                help="Choose the time period for calculating player averages"
            )
            num_games = period_map[selected_period]
            
            # Totals toggle - default to False (averages)
            show_totals = st.toggle(
                "Show Totals",
                value=False,
                key="traditional_totals",
                help="Toggle between Per Game and Total stats"
            )
            per_mode_str = 'Totals' if show_totals else 'PerGame'
            
            # Check data availability for Traditional scope
            data_available = len(players_df) > 0 and len(game_logs_df) > 0
            
            if not data_available:
                st.warning("Unable to load player data. Please try again.")
            else:
                # Away Team
                st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 15px; margin: 20px 0 10px 0;">
                        <img src="https://cdn.nba.com/logos/nba/{away_team_id}/primary/L/logo.svg" style="height: 60px; width: auto;">
                        <span style="font-size: 24px; font-weight: bold;">{away_team_name}</span>
                    </div>
                """, unsafe_allow_html=True)
                
                away_roster_df = functions.get_team_roster_stats(away_team_id, players_df, game_logs_df, num_games, per_mode=per_mode_str)
                
                if len(away_roster_df) > 0:
                    # Filter to display columns only
                    away_display_df = away_roster_df[[col for col in display_columns if col in away_roster_df.columns]].copy()
                    
                    # Calculate individual player season averages for styling
                    away_player_season_averages = calculate_player_season_averages(away_roster_df, game_logs_df, per_mode=per_mode_str)
                    
                    # Apply styling
                    styled_away_df = style_player_averages_heatmap(away_display_df, away_player_season_averages)
                    
                    st.dataframe(
                        styled_away_df,
                        column_config=column_config,
                        hide_index=True,
                        width='stretch',
                        height=min(600, 50 * len(away_display_df) + 38)
                    )
                else:
                    st.info(f"No player data available for {away_team_name}")
                
                st.divider()
                
                # Home Team
                st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 15px; margin: 20px 0 10px 0;">
                        <img src="https://cdn.nba.com/logos/nba/{home_team_id}/primary/L/logo.svg" style="height: 60px; width: auto;">
                        <span style="font-size: 24px; font-weight: bold;">{home_team_name}</span>
                    </div>
                """, unsafe_allow_html=True)
                
                home_roster_df = functions.get_team_roster_stats(home_team_id, players_df, game_logs_df, num_games, per_mode=per_mode_str)
                
                if len(home_roster_df) > 0:
                    # Filter to display columns only
                    home_display_df = home_roster_df[[col for col in display_columns if col in home_roster_df.columns]].copy()
                    
                    # Calculate individual player season averages for styling
                    home_player_season_averages = calculate_player_season_averages(home_roster_df, game_logs_df, per_mode=per_mode_str)
                    
                    # Apply styling
                    styled_home_df = style_player_averages_heatmap(home_display_df, home_player_season_averages)
                    
                    st.dataframe(
                        styled_home_df,
                        column_config=column_config,
                        hide_index=True,
                        width='stretch',
                        height=min(600, 50 * len(home_display_df) + 38)
                    )
                else:
                    st.info(f"No player data available for {home_team_name}")
        
        with tab_clutch:
            # Period selector - default to "All Games"
            period_options = ["Last 10 Games", "Last 5 Games", "Last 3 Games", "All Games"]
            selected_period = st.selectbox(
                "Select Period:",
                options=period_options,
                index=3,  # All Games
                key="clutch_period",
                help="Choose the time period for calculating player averages"
            )
            num_games = period_map[selected_period]
            
            # Totals toggle - default to True (totals)
            show_totals = st.toggle(
                "Show Totals",
                value=True,
                key="clutch_totals",
                help="Toggle between Per Game and Total stats"
            )
            per_mode_str = 'Totals' if show_totals else 'PerGame'
            
            # Check data availability for Clutch scope
            data_available = len(players_df) > 0
            
            if not data_available:
                st.warning("Unable to load player data. Please try again.")
            else:
                # Initialize session state cache for clutch data if not exists
                if 'clutch_data_cache' not in st.session_state:
                    st.session_state.clutch_data_cache = {}
                
                cache_key = f"player_clutch_{per_mode_str}"
                season_str = '2025-26'
                
                # Check session state first (fastest)
                if cache_key in st.session_state.clutch_data_cache:
                    clutch_data_all_players = st.session_state.clutch_data_cache[cache_key]
                else:
                    # Fetch from API
                    try:
                        clutch_data_all_players = nba_api.stats.endpoints.LeagueDashPlayerClutch(
                            season=season_str,
                            season_type_all_star='Regular Season',
                            per_mode_detailed=per_mode_str,
                            clutch_time='Last 5 Minutes',
                            ahead_behind='Ahead or Behind',
                            point_diff=5
                        ).get_data_frames()[0]
                    except Exception as e:
                        print(f"Error fetching clutch stats: {e}")
                        clutch_data_all_players = pd.DataFrame()
                    
                    # Store in session state for fast access on subsequent toggles
                    st.session_state.clutch_data_cache[cache_key] = clutch_data_all_players
                
                # Process data for each team
                if clutch_data_all_players is not None and len(clutch_data_all_players) > 0:
                    # Away Team
                    st.markdown(f"""
                        <div style="display: flex; align-items: center; gap: 15px; margin: 20px 0 10px 0;">
                            <img src="https://cdn.nba.com/logos/nba/{away_team_id}/primary/L/logo.svg" style="height: 60px; width: auto;">
                            <span style="font-size: 24px; font-weight: bold;">{away_team_name}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Filter clutch data to away team
                    away_clutch_data = clutch_data_all_players[clutch_data_all_players['TEAM_ID'].astype(int) == away_team_id].copy()
                    away_roster_df = functions.process_clutch_data_to_roster(away_clutch_data, players_df, away_team_id)
                    
                    if away_roster_df is not None and len(away_roster_df) > 0:
                        # Filter to display columns only
                        away_display_df = away_roster_df[[col for col in display_columns if col in away_roster_df.columns]].copy()
                        
                        # For Clutch scope, we'll need to fetch clutch season averages differently
                        # For now, use empty dict (will be handled in styling function)
                        away_player_season_averages = {}
                        # TODO: Implement clutch season averages calculation if needed
                        
                        # Apply styling
                        styled_away_df = style_player_averages_heatmap(away_display_df, away_player_season_averages)
                        
                        st.dataframe(
                            styled_away_df,
                            column_config=column_config,
                            hide_index=True,
                            width='stretch',
                            height=min(600, 50 * len(away_display_df) + 38)
                        )
                    else:
                        st.info(f"No player data available for {away_team_name}")
                    
                    st.divider()
                    
                    # Home Team
                    st.markdown(f"""
                        <div style="display: flex; align-items: center; gap: 15px; margin: 20px 0 10px 0;">
                            <img src="https://cdn.nba.com/logos/nba/{home_team_id}/primary/L/logo.svg" style="height: 60px; width: auto;">
                            <span style="font-size: 24px; font-weight: bold;">{home_team_name}</span>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Filter clutch data to home team
                    home_clutch_data = clutch_data_all_players[clutch_data_all_players['TEAM_ID'].astype(int) == home_team_id].copy()
                    home_roster_df = functions.process_clutch_data_to_roster(home_clutch_data, players_df, home_team_id)
                    
                    if home_roster_df is not None and len(home_roster_df) > 0:
                        # Filter to display columns only
                        home_display_df = home_roster_df[[col for col in display_columns if col in home_roster_df.columns]].copy()
                        
                        # For Clutch scope, we'll need to fetch clutch season averages differently
                        # For now, use empty dict (will be handled in styling function)
                        home_player_season_averages = {}
                        # TODO: Implement clutch season averages calculation if needed
                        
                        # Apply styling
                        styled_home_df = style_player_averages_heatmap(home_display_df, home_player_season_averages)
                        
                        st.dataframe(
                            styled_home_df,
                            column_config=column_config,
                            hide_index=True,
                            width='stretch',
                            height=min(600, 50 * len(home_display_df) + 38)
                        )
                    else:
                        st.info(f"No player data available for {home_team_name}")
                else:
                    st.warning("Unable to load clutch data. Please try again.")
    
    with tab4:
        # ============================================================
        # INJURY REPORT TAB
        # ============================================================
        
        # Get team info
        away_team_name = selected_matchup['away_team_name']
        home_team_name = selected_matchup['home_team_name']
        away_team_id = selected_matchup['away_team_id']
        home_team_id = selected_matchup['home_team_id']
        
        # Get tricodes directly from matchup (from API) - same as Matchup Summary
        away_team_abbr = selected_matchup.get('away_team', '')
        home_team_abbr = selected_matchup.get('home_team', '')
        
        # Fallback to mapping if tricodes not available
        if not away_team_abbr or not home_team_abbr:
            team_name_to_abbr = {
                'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
                'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
                'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
                'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
                'LA Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
                'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
                'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
                'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
                'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
                'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'
            }
            if not away_team_abbr:
                away_team_abbr = team_name_to_abbr.get(away_team_name, away_team_name.split()[-1][:3].upper())
            if not home_team_abbr:
                home_team_abbr = team_name_to_abbr.get(home_team_name, home_team_name.split()[-1][:3].upper())
        
        st.markdown("### Injury Report")
        
        # Load player data first (needed for injury matching)
        @st.cache_data(ttl=1800, show_spinner="Loading player data...")
        def load_injury_player_data():
            players_df = functions.get_players_dataframe()
            return players_df
        
        players_df_injury = load_injury_player_data()
        
        # Fetch injury report
        @st.cache_data(ttl=600, show_spinner="Fetching injury report...")
        def fetch_injury_data():
            return ir.fetch_injuries_for_date()
        
        injury_df, injury_status = fetch_injury_data()
        
        # Get injuries for this matchup
        if injury_df is not None and len(injury_df) > 0:
            matchup_injuries = ir.get_injuries_for_matchup(
                injury_df, away_team_abbr, home_team_abbr, players_df_injury
            )
            
            # Create two columns for away/home injuries
            inj_col1, inj_col2 = st.columns(2)
            
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
            
            # Sort injuries by status
            sorted_away_injuries = sorted(matchup_injuries['away'], key=lambda x: get_status_order(x.get('status', '')))
            sorted_home_injuries = sorted(matchup_injuries['home'], key=lambda x: get_status_order(x.get('status', '')))
            
            with inj_col1:
                st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                        <img src="https://cdn.nba.com/logos/nba/{away_team_id}/primary/L/logo.svg" style="height: 40px; width: auto;">
                        <span style="font-size: 18px; font-weight: bold;">{away_team_name}</span>
                    </div>
                """, unsafe_allow_html=True)
                
                if sorted_away_injuries:
                    for inj in sorted_away_injuries:
                        status = inj['status']
                        status_color = get_status_color(status)
                        formatted_name = ir.format_player_name(inj['player_name'])
                        formatted_reason = ir.format_injury_reason(inj.get('reason', ''))
                        player_id = inj.get('player_id', '')
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
                st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                        <img src="https://cdn.nba.com/logos/nba/{home_team_id}/primary/L/logo.svg" style="height: 40px; width: auto;">
                        <span style="font-size: 18px; font-weight: bold;">{home_team_name}</span>
                    </div>
                """, unsafe_allow_html=True)
                
                if sorted_home_injuries:
                    for inj in sorted_home_injuries:
                        status = inj['status']
                        status_color = get_status_color(status)
                        formatted_name = ir.format_player_name(inj['player_name'])
                        formatted_reason = ir.format_injury_reason(inj.get('reason', ''))
                        player_id = inj.get('player_id', '')
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
        else:
            st.warning(f"⚠️ Could not fetch injury report: {injury_status}")
    