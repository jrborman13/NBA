import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'streamlit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'new-streamlit-app', 'player-app'))

import streamlit as st
import streamlit_testing_functions as functions
import injury_report as ir
import datetime
from datetime import date
import nba_api.stats.endpoints

import altair as alt
import pandas as pd
import streamlit as st

# Clear all caches
# st.cache_data.clear()

st.set_page_config(layout="wide")
st.title("NBA Matchup Data App")

# Function to fetch matchups for a given date (same as Players page)
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_matchups_for_date(selected_date):
    """Fetch NBA matchups for a given date from the API"""
    try:
        league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
            league_id='00',
            season='2025-26'
        ).get_data_frames()[0]
        
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
        players_df = functions.get_players_dataframe()
        game_logs_df = functions.get_all_player_game_logs()
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
                    for m in away_advantages[:5]:  # Top 5 per team
                        arrow = "🟢" if m['rank_diff'] >= 15 else "🟡" if m['rank_diff'] >= 10 else "⚪"
                        st.markdown(f"{arrow} **{m['stat_name']}**: {m['off_team']} OFF #{m['off_rank']} vs {m['def_team']} DEF #{m['def_rank']} (+{m['rank_diff']})")
                else:
                    st.caption("No significant advantages found")
            
            with mismatch_cols[1]:
                st.markdown(f"**{home_abbr} Advantages**")
                if home_advantages:
                    for m in home_advantages[:5]:  # Top 5 per team
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
    
    # Tab selector (Core Stats, Shooting, and Rosters)
    tab = st.radio("Select Tab", ('Core Stats', 'Shooting', 'Rosters'))

    stat_font_size = 20
    rank_font_size = 16
    border = 1
    padding = 8
    border_radius = 5
    title_header_background_color = 'f9f9f9'
    body_header_background_color = 'f9f9f9'
    body_background_color = 'white'

    if tab == 'Core Stats':

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

    elif tab == 'Shooting':

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

    elif tab == 'Rosters':
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
        
        # ============================================================
        # INJURY REPORT SECTION
        # ============================================================
        st.markdown("### Injury Report")
        
        # Load player data first (needed for injury matching)
        @st.cache_data(ttl=1800, show_spinner="Loading player data...")
        def load_roster_data():
            players_df = functions.get_players_dataframe()
            game_logs_df = functions.get_all_player_game_logs()
            return players_df, game_logs_df
        
        players_df, game_logs_df = load_roster_data()
        
        # Fetch injury report
        @st.cache_data(ttl=600, show_spinner="Fetching injury report...")
        def fetch_injury_data():
            return ir.fetch_injuries_for_date()
        
        injury_df, injury_status = fetch_injury_data()
        
        # Get injuries for this matchup
        if injury_df is not None and len(injury_df) > 0:
            matchup_injuries = ir.get_injuries_for_matchup(
                injury_df, away_team_abbr, home_team_abbr, players_df
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
        
        st.divider()
        
        # ============================================================
        # PLAYER AVERAGES SECTION
        # ============================================================
        st.markdown("### Player Averages")
        
        # Period selector
        period_options = ["Last 10 Games", "Last 5 Games", "Last 3 Games", "All Games"]
        selected_period = st.selectbox(
            "Select Period:",
            options=period_options,
            index=0,  # Default to Last 10 Games
            help="Choose the time period for calculating player averages"
        )
        
        # Map period to num_games
        period_map = {
            "Last 10 Games": 10,
            "Last 5 Games": 5,
            "Last 3 Games": 3,
            "All Games": None
        }
        num_games = period_map[selected_period]
        
        if len(players_df) == 0 or len(game_logs_df) == 0:
            st.warning("Unable to load player data. Please try again.")
        else:
            # Column config for dataframes - use specific pixel widths for tighter columns
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
                "FGA": st.column_config.NumberColumn("FGA", format="%.1f", width=50),
                "FG%": st.column_config.NumberColumn("FG%", format="%.1f%%", width=55),
                "3PM": st.column_config.NumberColumn("3PM", format="%.1f", width=50),
                "3PA": st.column_config.NumberColumn("3PA", format="%.1f", width=50),
                "3P%": st.column_config.NumberColumn("3P%", format="%.1f%%", width=55),
                "FTM": st.column_config.NumberColumn("FTM", format="%.1f", width=50),
                "FTA": st.column_config.NumberColumn("FTA", format="%.1f", width=50),
                "FT%": st.column_config.NumberColumn("FT%", format="%.1f%%", width=55),
            }
            
            # Display columns (exclude hidden _player_id)
            display_columns = ['headshot', 'Player', 'Pos', 'GP', 'MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', 'FGM', 'FGA', 'FG%', '3PM', '3PA', '3P%', 'FTM', 'FTA', 'FT%']
            
            # Away Team
            st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 15px; margin: 20px 0 10px 0;">
                    <img src="https://cdn.nba.com/logos/nba/{away_team_id}/primary/L/logo.svg" style="height: 60px; width: auto;">
                    <span style="font-size: 24px; font-weight: bold;">{away_team_name}</span>
                </div>
            """, unsafe_allow_html=True)
            
            away_roster_df = functions.get_team_roster_stats(away_team_id, players_df, game_logs_df, num_games)
            
            if len(away_roster_df) > 0:
                # Filter to display columns only
                away_display_df = away_roster_df[[col for col in display_columns if col in away_roster_df.columns]]
                st.dataframe(
                    away_display_df,
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
            
            home_roster_df = functions.get_team_roster_stats(home_team_id, players_df, game_logs_df, num_games)
            
            if len(home_roster_df) > 0:
                # Filter to display columns only
                home_display_df = home_roster_df[[col for col in display_columns if col in home_roster_df.columns]]
                st.dataframe(
                    home_display_df,
                    column_config=column_config,
                    hide_index=True,
                    width='stretch',
                    height=min(600, 50 * len(home_display_df) + 38)
                )
            else:
                st.info(f"No player data available for {home_team_name}")
