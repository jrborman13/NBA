import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'streamlit'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'new-streamlit-app', 'player-app'))

import streamlit as st
import pandas as pd
import json
import time
from datetime import date, datetime
from nba_api.live.nba.endpoints import scoreboard, boxscore
from nba_api.stats.endpoints import ScoreboardV2

st.set_page_config(layout="wide", page_title="Live Game Stats", page_icon="🏀")
st.title("🏀 Live Game Stats")

# Add sidebar with cache clear button
with st.sidebar:
    st.markdown("### Cache Management")
    if st.button("🗑️ Clear All Cache", width='stretch'):
        st.cache_data.clear()
        st.success("✅ Cache cleared successfully!")
        st.rerun()
    st.markdown("---")  # Separator

# Add custom CSS styling
st.markdown("""
<style>
    .team-header {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .score-display {
        text-align: center;
        font-size: 48px;
        font-weight: bold;
        margin: 20px 0;
    }
    .quarter-scores {
        font-size: 14px;
        color: #666;
        margin: 10px 0;
    }
    .player-table {
        margin-top: 20px;
    }
    .starter-row {
        background-color: #e8f4f8;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'auto_refresh' not in st.session_state:
    st.session_state['auto_refresh'] = False
if 'last_refresh' not in st.session_state:
    st.session_state['last_refresh'] = None
if 'refresh_interval' not in st.session_state:
    st.session_state['refresh_interval'] = 10  # seconds

# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

@st.cache_data(ttl=60, show_spinner="Fetching games...")
def get_live_games_for_date(selected_date):
    """
    Fetch NBA games for a given date.
    Returns list of games with game_id, away_team, home_team, game_status, game_time.
    """
    try:
        # Use ScoreboardV2 for historical dates, ScoreBoard() for today
        date_str = selected_date.strftime('%Y-%m-%d')
        today = date.today()
        
        if selected_date == today:
            # Use live scoreboard for today
            try:
                games_board = scoreboard.ScoreBoard()
                games_dict = games_board.get_dict()
                games_list = games_dict.get('scoreboard', {}).get('games', [])
            except:
                # Fallback to ScoreboardV2 if live endpoint fails
                games_board = ScoreboardV2(league_id='00', game_date=date_str, day_offset=0)
                games_data = games_board.get_dict()
                games_list = []
                if 'resultSets' in games_data:
                    for rs in games_data['resultSets']:
                        if rs['name'] == 'GameHeader':
                            headers = rs['headers']
                            for row in rs['rowSet']:
                                game_dict = dict(zip(headers, row))
                                games_list.append({
                                    'gameId': game_dict.get('GAME_ID', ''),
                                    'awayTeam': {'teamId': game_dict.get('VISITOR_TEAM_ID', '')},
                                    'homeTeam': {'teamId': game_dict.get('HOME_TEAM_ID', '')},
                                    'gameStatusText': game_dict.get('GAME_STATUS_TEXT', ''),
                                    'gameStatusId': game_dict.get('GAME_STATUS_ID', '')
                                })
        else:
            # Use ScoreboardV2 for historical dates
            games_board = ScoreboardV2(league_id='00', game_date=date_str, day_offset=0)
            games_data = games_board.get_dict()
            games_list = []
            if 'resultSets' in games_data:
                for rs in games_data['resultSets']:
                    if rs['name'] == 'GameHeader':
                        headers = rs['headers']
                        for row in rs['rowSet']:
                            game_dict = dict(zip(headers, row))
                            games_list.append({
                                'gameId': game_dict.get('GAME_ID', ''),
                                'awayTeam': {'teamId': game_dict.get('VISITOR_TEAM_ID', '')},
                                'homeTeam': {'teamId': game_dict.get('HOME_TEAM_ID', '')},
                                'gameStatusText': game_dict.get('GAME_STATUS_TEXT', ''),
                                'gameStatusId': game_dict.get('GAME_STATUS_ID', '')
                            })
        
        # Get team names from schedule
        try:
            from nba_api.stats.endpoints import ScheduleLeagueV2
            schedule = ScheduleLeagueV2(league_id='00', season='2025-26').get_data_frames()[0]
            team_id_to_name = {}
            team_id_to_abbr = {}
            for _, row in schedule.iterrows():
                team_id_to_name[row['awayTeam_teamId']] = row['awayTeam_teamName']
                team_id_to_name[row['homeTeam_teamId']] = row['homeTeam_teamName']
                team_id_to_abbr[row['awayTeam_teamId']] = row['awayTeam_teamTricode']
                team_id_to_abbr[row['homeTeam_teamId']] = row['homeTeam_teamTricode']
        except:
            team_id_to_name = {}
            team_id_to_abbr = {}
        
        # Format games list
        formatted_games = []
        for game in games_list:
            game_id = game.get('gameId', '')
            away_id = game.get('awayTeam', {}).get('teamId', '')
            home_id = game.get('homeTeam', {}).get('teamId', '')
            
            formatted_games.append({
                'game_id': game_id,
                'away_team_id': away_id,
                'home_team_id': home_id,
                'away_team_name': team_id_to_name.get(away_id, f'Team {away_id}'),
                'home_team_name': team_id_to_name.get(home_id, f'Team {home_id}'),
                'away_team_abbr': team_id_to_abbr.get(away_id, ''),
                'home_team_abbr': team_id_to_abbr.get(home_id, ''),
                'game_status': game.get('gameStatusText', ''),
                'game_status_id': game.get('gameStatusId', '')
            })
        
        return formatted_games, None
    except Exception as e:
        return [], f"Error fetching games: {str(e)}"

@st.cache_data(ttl=300, show_spinner="Loading box score...")  # 5 minutes cache
def get_box_score(game_id, game_status=None):
    """
    Fetch live box score for a given game ID.
    Returns structured dictionary with team and player data.
    
    Args:
        game_id: The game ID to fetch
        game_status: Optional game status to determine cache duration
    """
    try:
        box_score_obj = boxscore.BoxScore(game_id)
        box_score_json = json.loads(box_score_obj.get_json())
        game_data = box_score_json.get('game', {})
        
        if not game_data:
            return None, "No game data found"
        
        return game_data, None
    except Exception as e:
        return None, f"Error fetching box score: {str(e)}"

def format_minutes(minutes_str):
    """Convert ISO 8601 duration (PT10M14.00S) to MM:SS format."""
    if not minutes_str or minutes_str == '':
        return '0:00'
    
    try:
        # Remove 'PT' prefix
        minutes_str = minutes_str.replace('PT', '')
        
        # Extract minutes and seconds
        if 'M' in minutes_str:
            parts = minutes_str.split('M')
            mins = int(parts[0])
            secs_str = parts[1].replace('S', '').split('.')[0]
            secs = int(secs_str) if secs_str else 0
        else:
            mins = 0
            secs_str = minutes_str.replace('S', '').split('.')[0]
            secs = int(secs_str) if secs_str else 0
        
        return f"{mins}:{secs:02d}"
    except:
        return minutes_str

def format_player_stats(players_list):
    """
    Extract and format player statistics from box score JSON.
    Returns DataFrame with formatted stats.
    """
    if not players_list:
        return pd.DataFrame()
    
    rows = []
    for player in players_list:
        stats = player.get('statistics', {})
        
        # Calculate shooting percentages
        fg_pct = stats.get('fieldGoalsPercentage', 0) * 100 if stats.get('fieldGoalsPercentage') else 0
        fg3_pct = stats.get('threePointersPercentage', 0) * 100 if stats.get('threePointersPercentage') else 0
        ft_pct = stats.get('freeThrowsPercentage', 0) * 100 if stats.get('freeThrowsPercentage') else 0
        
        # Calculate fantasy points using Underdog formula: PTS*1 + REB*1.2 + AST*1.5 + STL*3 + BLK*3 - TOV*1
        pts = stats.get('points', 0)
        reb = stats.get('reboundsTotal', 0)
        ast = stats.get('assists', 0)
        stl = stats.get('steals', 0)
        blk = stats.get('blocks', 0)
        tov = stats.get('turnovers', 0)
        fpts = round(pts * 1.0 + reb * 1.2 + ast * 1.5 + stl * 3.0 + blk * 3.0 - tov * 1.0, 2)
        
        rows.append({
            'Name': player.get('name', ''),
            'Pos': player.get('position', ''),
            'MIN': format_minutes(stats.get('minutes', '')),
            'PTS': pts,
            'REB': reb,
            'AST': ast,
            'STL': stl,
            'BLK': blk,
            'TOV': tov,
            'FPTS': float(fpts),
            'FGM': stats.get('fieldGoalsMade', 0),
            'FGA': stats.get('fieldGoalsAttempted', 0),
            'FG%': f"{fg_pct:.1f}" if fg_pct > 0 else "0.0",
            '3PM': stats.get('threePointersMade', 0),
            '3PA': stats.get('threePointersAttempted', 0),
            '3P%': f"{fg3_pct:.1f}" if fg3_pct > 0 else "0.0",
            'FTM': stats.get('freeThrowsMade', 0),
            'FTA': stats.get('freeThrowsAttempted', 0),
            'FT%': f"{ft_pct:.1f}" if ft_pct > 0 else "0.0",
            'FB PTS': stats.get('pointsFastBreak', 0),
            'PITP': stats.get('pointsInThePaint', 0),
            '2ND CH': stats.get('pointsSecondChance', 0),
            '+/-': int(stats.get('plusMinusPoints', 0)),
            'Starter': player.get('starter', '0') == '1',
            'OnCourt': player.get('oncourt', '0') == '1',
            'Status': player.get('status', '')
        })
    
    df = pd.DataFrame(rows)
    
    # Format FGM-FGA and 3PM-3PA, FTM-FTA
    if len(df) > 0:
        df['FGM-FGA'] = df['FGM'].astype(str) + '-' + df['FGA'].astype(str)
        df['3PM-3PA'] = df['3PM'].astype(str) + '-' + df['3PA'].astype(str)
        df['FTM-FTA'] = df['FTM'].astype(str) + '-' + df['FTA'].astype(str)
        
        # Ensure FPTS is numeric for sorting
        if 'FPTS' in df.columns:
            df['FPTS'] = pd.to_numeric(df['FPTS'], errors='coerce').fillna(0.0).round(2)
        
        # Sort by fantasy points (descending) before converting to string
        df = df.sort_values('FPTS', ascending=False)
        
        # Format FPTS as string with 2 decimal places for display (after sorting)
        if 'FPTS' in df.columns:
            df['FPTS'] = df['FPTS'].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "0.00")
    
    return df

def calculate_team_totals(players_df):
    """Calculate team totals from player stats DataFrame."""
    if len(players_df) == 0:
        return {}
    
    totals = {
        'PTS': players_df['PTS'].sum(),
        'REB': players_df['REB'].sum(),
        'AST': players_df['AST'].sum(),
        'STL': players_df['STL'].sum(),
        'BLK': players_df['BLK'].sum(),
        'TOV': players_df['TOV'].sum(),
        'FGM': players_df['FGM'].sum(),
        'FGA': players_df['FGA'].sum(),
        '3PM': players_df['3PM'].sum(),
        '3PA': players_df['3PA'].sum(),
        'FTM': players_df['FTM'].sum(),
        'FTA': players_df['FTA'].sum(),
        'FB PTS': players_df.get('FB PTS', pd.Series([0])).sum() if 'FB PTS' in players_df.columns else 0,
        'PITP': players_df.get('PITP', pd.Series([0])).sum() if 'PITP' in players_df.columns else 0,
        '2ND CH': players_df.get('2ND CH', pd.Series([0])).sum() if '2ND CH' in players_df.columns else 0,
    }
    
    # Calculate percentages
    totals['FG%'] = (totals['FGM'] / totals['FGA'] * 100) if totals['FGA'] > 0 else 0
    totals['3P%'] = (totals['3PM'] / totals['3PA'] * 100) if totals['3PA'] > 0 else 0
    totals['FT%'] = (totals['FTM'] / totals['FTA'] * 100) if totals['FTA'] > 0 else 0
    
    totals['FGM-FGA'] = f"{totals['FGM']}-{totals['FGA']}"
    totals['3PM-3PA'] = f"{totals['3PM']}-{totals['3PA']}"
    totals['FTM-FTA'] = f"{totals['FTM']}-{totals['FTA']}"
    
    return totals

def get_stat_delta(away_val, home_val, higher_is_better=True):
    """
    Calculate delta for st.metric to show green/red highlighting.
    Returns the difference (away - home) for higher_is_better=True,
    or (home - away) for higher_is_better=False (like turnovers).
    """
    if higher_is_better:
        return away_val - home_val
    else:
        return home_val - away_val  # For turnovers, lower is better

def calculate_starter_stats(players_df):
    """Calculate starter stats from player stats DataFrame."""
    if len(players_df) == 0 or 'Starter' not in players_df.columns:
        return {}
    
    starter_df = players_df[players_df['Starter']].copy()
    
    if len(starter_df) == 0:
        return {
            'PTS': 0,
            'FGM': 0,
            'FGA': 0,
            'FG%': 0.0,
            '3PM': 0,
            '3PA': 0,
            '3P%': 0.0,
            'FTM': 0,
            'FTA': 0,
            'FT%': 0.0,
            'REB': 0,
            'AST': 0,
            'FB PTS': 0,
            'PITP': 0,
            '2ND CH': 0
        }
    
    starter_totals = {
        'PTS': starter_df['PTS'].sum(),
        'FGM': starter_df['FGM'].sum(),
        'FGA': starter_df['FGA'].sum(),
        '3PM': starter_df['3PM'].sum(),
        '3PA': starter_df['3PA'].sum(),
        'FTM': starter_df['FTM'].sum(),
        'FTA': starter_df['FTA'].sum(),
        'REB': starter_df['REB'].sum(),
        'AST': starter_df['AST'].sum(),
        'FB PTS': starter_df.get('FB PTS', pd.Series([0])).sum() if 'FB PTS' in starter_df.columns else 0,
        'PITP': starter_df.get('PITP', pd.Series([0])).sum() if 'PITP' in starter_df.columns else 0,
        '2ND CH': starter_df.get('2ND CH', pd.Series([0])).sum() if '2ND CH' in starter_df.columns else 0,
    }
    
    # Calculate percentages
    starter_totals['FG%'] = (starter_totals['FGM'] / starter_totals['FGA'] * 100) if starter_totals['FGA'] > 0 else 0
    starter_totals['3P%'] = (starter_totals['3PM'] / starter_totals['3PA'] * 100) if starter_totals['3PA'] > 0 else 0
    starter_totals['FT%'] = (starter_totals['FTM'] / starter_totals['FTA'] * 100) if starter_totals['FTA'] > 0 else 0
    
    starter_totals['FGM-FGA'] = f"{starter_totals['FGM']}-{starter_totals['FGA']}"
    starter_totals['3PM-3PA'] = f"{starter_totals['3PM']}-{starter_totals['3PA']}"
    starter_totals['FTM-FTA'] = f"{starter_totals['FTM']}-{starter_totals['FTA']}"
    
    return starter_totals

def calculate_bench_stats(players_df):
    """Calculate bench stats from player stats DataFrame."""
    if len(players_df) == 0 or 'Starter' not in players_df.columns:
        return {}
    
    bench_df = players_df[~players_df['Starter']].copy()
    
    if len(bench_df) == 0:
        return {
            'PTS': 0,
            'FGM': 0,
            'FGA': 0,
            'FG%': 0.0,
            '3PM': 0,
            '3PA': 0,
            '3P%': 0.0,
            'FTM': 0,
            'FTA': 0,
            'FT%': 0.0,
            'REB': 0,
            'AST': 0,
            'FB PTS': 0,
            'PITP': 0,
            '2ND CH': 0
        }
    
    bench_totals = {
        'PTS': bench_df['PTS'].sum(),
        'FGM': bench_df['FGM'].sum(),
        'FGA': bench_df['FGA'].sum(),
        '3PM': bench_df['3PM'].sum(),
        '3PA': bench_df['3PA'].sum(),
        'FTM': bench_df['FTM'].sum(),
        'FTA': bench_df['FTA'].sum(),
        'REB': bench_df['REB'].sum(),
        'AST': bench_df['AST'].sum(),
        'FB PTS': bench_df.get('FB PTS', pd.Series([0])).sum() if 'FB PTS' in bench_df.columns else 0,
        'PITP': bench_df.get('PITP', pd.Series([0])).sum() if 'PITP' in bench_df.columns else 0,
        '2ND CH': bench_df.get('2ND CH', pd.Series([0])).sum() if '2ND CH' in bench_df.columns else 0,
    }
    
    # Calculate percentages
    bench_totals['FG%'] = (bench_totals['FGM'] / bench_totals['FGA'] * 100) if bench_totals['FGA'] > 0 else 0
    bench_totals['3P%'] = (bench_totals['3PM'] / bench_totals['3PA'] * 100) if bench_totals['3PA'] > 0 else 0
    bench_totals['FT%'] = (bench_totals['FTM'] / bench_totals['FTA'] * 100) if bench_totals['FTA'] > 0 else 0
    
    bench_totals['FGM-FGA'] = f"{bench_totals['FGM']}-{bench_totals['FGA']}"
    bench_totals['3PM-3PA'] = f"{bench_totals['3PM']}-{bench_totals['3PA']}"
    bench_totals['FTM-FTA'] = f"{bench_totals['FTM']}-{bench_totals['FTA']}"
    
    return bench_totals

# =============================================================================
# MAIN UI
# =============================================================================

# Header Section
st.markdown("### Select Game")

col_date, col_game, col_refresh = st.columns([1, 2, 1])

with col_date:
    selected_date = st.date_input(
        "Date:",
        value=date.today(),
        key="live_date"
    )

with col_game:
    games_list, games_error = get_live_games_for_date(selected_date)
    
    if games_error:
        st.warning(f"⚠️ {games_error}")
        games_list = []
    
    if games_list:
        game_options = []
        for game in games_list:
            matchup_str = f"{game['away_team_abbr']} @ {game['home_team_abbr']}"
            status_str = game.get('game_status', '')
            if status_str:
                matchup_str += f" ({status_str})"
            game_options.append(matchup_str)
        
        selected_game_idx = st.selectbox(
            "Game:",
            options=range(len(game_options)),
            format_func=lambda x: game_options[x] if x < len(game_options) else "",
            key="live_game_select"
        )
        
        if selected_game_idx < len(games_list):
            selected_game = games_list[selected_game_idx]
            selected_game_id = selected_game['game_id']
        else:
            selected_game_id = None
            selected_game = None
    else:
        st.info("No games found for this date.")
        selected_game_id = None
        selected_game = None

with col_refresh:
    auto_refresh = st.checkbox(
        "Auto-refresh",
        value=st.session_state['auto_refresh'],
        key="auto_refresh_checkbox",
        help="Automatically refresh box score every 10 seconds"
    )
    st.session_state['auto_refresh'] = auto_refresh
    
    if st.button("🔄 Refresh", key="manual_refresh"):
        st.cache_data.clear()
        st.rerun()

# Display game status
if selected_game:
    game_status = selected_game.get('game_status', '')
    st.markdown(f"**Game Status:** {game_status}")
    
    if st.session_state['last_refresh']:
        last_refresh_time = st.session_state['last_refresh'].strftime("%H:%M:%S")
        st.caption(f"Last updated: {last_refresh_time}")

# Fetch and display box score
if selected_game_id:
    # Check if we have cached data for this game in session state
    cache_key = f'box_score_{selected_game_id}'
    game_status_for_cache = selected_game.get('game_status', '') if selected_game else None
    
    # Use cached data if available and game is final (no need to refresh)
    if cache_key in st.session_state and game_status_for_cache == 'Final':
        game_data = st.session_state[cache_key]
        box_error = None
    else:
        # Fetch from API
        game_data, box_error = get_box_score(selected_game_id, game_status_for_cache)
        
        # Cache in session state if successful
        if game_data and not box_error:
            st.session_state[cache_key] = game_data
    
    if box_error:
        st.error(f"❌ {box_error}")
        if "No game data found" in box_error or "hasn't started" in box_error.lower():
            st.info("This game may not have started yet. Please check back later.")
    elif game_data:
        # Update last refresh time
        st.session_state['last_refresh'] = datetime.now()
        
        # Extract team data
        away_team_data = game_data.get('awayTeam', {})
        home_team_data = game_data.get('homeTeam', {})
        
        away_team_name = away_team_data.get('teamName', selected_game.get('away_team_name', 'Away'))
        home_team_name = home_team_data.get('teamName', selected_game.get('home_team_name', 'Home'))
        away_team_abbr = away_team_data.get('teamTricode', selected_game.get('away_team_abbr', ''))
        home_team_abbr = home_team_data.get('teamTricode', selected_game.get('home_team_abbr', ''))
        
        # Get scores
        away_score = away_team_data.get('score', 0)
        home_score = home_team_data.get('score', 0)
        
        # Get quarter scores
        away_periods = away_team_data.get('periods', [])
        home_periods = home_team_data.get('periods', [])
        
        # Get players
        away_players = away_team_data.get('players', [])
        home_players = home_team_data.get('players', [])
        
        # Format player stats
        away_df = format_player_stats(away_players)
        home_df = format_player_stats(home_players)
        
        # Calculate team totals
        away_totals = calculate_team_totals(away_df)
        home_totals = calculate_team_totals(home_df)
        
        # Get game status details
        game_status_text = game_data.get('gameStatusText', '')
        game_clock = game_data.get('gameClock', '')
        period = game_data.get('period', {})
        period_value = period.get('current', 0) if isinstance(period, dict) else 0
        
        # Calculate starter and bench stats
        away_starter_stats = calculate_starter_stats(away_df)
        home_starter_stats = calculate_starter_stats(home_df)
        away_bench_stats = calculate_bench_stats(away_df)
        home_bench_stats = calculate_bench_stats(home_df)
        
        # Get team-level stats (points off turnovers might be here)
        away_team_stats = away_team_data.get('statistics', {})
        home_team_stats = home_team_data.get('statistics', {})
        
        # Debug: Show available team stats keys
        if isinstance(away_team_stats, dict) and len(away_team_stats) > 0:
            with st.expander("🔍 Debug: Available Team Statistics Keys"):
                st.write("**Away Team Stats Keys:**")
                for key in sorted(away_team_stats.keys()):
                    value = away_team_stats[key]
                    st.write(f"- `{key}`: {value}")
                
                if isinstance(home_team_stats, dict) and len(home_team_stats) > 0:
                    st.write("**Home Team Stats Keys:**")
                    for key in sorted(home_team_stats.keys()):
                        value = home_team_stats[key]
                        st.write(f"- `{key}`: {value}")
        
        # Calculate percentage of points from second chance + points off turnovers
        away_2nd_chance = away_totals.get('2ND CH', 0)
        home_2nd_chance = home_totals.get('2ND CH', 0)
        
        # Try to get points off turnovers from team stats (check multiple possible field names)
        away_pts_off_tov = 0
        home_pts_off_tov = 0
        
        if isinstance(away_team_stats, dict):
            # Try different possible field names
            if 'pointsOffTurnovers' in away_team_stats:
                away_pts_off_tov = away_team_stats['pointsOffTurnovers']
            elif 'pointsOffTurnover' in away_team_stats:
                away_pts_off_tov = away_team_stats['pointsOffTurnover']
            elif 'ptsOffTurnovers' in away_team_stats:
                away_pts_off_tov = away_team_stats['ptsOffTurnovers']
            elif 'ptsOffTurnover' in away_team_stats:
                away_pts_off_tov = away_team_stats['ptsOffTurnover']
            elif 'pointsFromTurnovers' in away_team_stats:
                away_pts_off_tov = away_team_stats['pointsFromTurnovers']
            elif 'pointsFromTurnover' in away_team_stats:
                away_pts_off_tov = away_team_stats['pointsFromTurnover']
        
        if isinstance(home_team_stats, dict):
            if 'pointsOffTurnovers' in home_team_stats:
                home_pts_off_tov = home_team_stats['pointsOffTurnovers']
            elif 'pointsOffTurnover' in home_team_stats:
                home_pts_off_tov = home_team_stats['pointsOffTurnover']
            elif 'ptsOffTurnovers' in home_team_stats:
                home_pts_off_tov = home_team_stats['ptsOffTurnovers']
            elif 'ptsOffTurnover' in home_team_stats:
                home_pts_off_tov = home_team_stats['ptsOffTurnover']
            elif 'pointsFromTurnovers' in home_team_stats:
                home_pts_off_tov = home_team_stats['pointsFromTurnovers']
            elif 'pointsFromTurnover' in home_team_stats:
                home_pts_off_tov = home_team_stats['pointsFromTurnover']
        
        # Calculate percentages
        away_total_pts = away_totals.get('PTS', 0)
        home_total_pts = home_totals.get('PTS', 0)
        
        away_2nd_chance_tov_pct = ((away_2nd_chance + away_pts_off_tov) / away_total_pts * 100) if away_total_pts > 0 else 0
        home_2nd_chance_tov_pct = ((home_2nd_chance + home_pts_off_tov) / home_total_pts * 100) if home_total_pts > 0 else 0
        
        # Display game status prominently
        if game_status_text:
            if game_status_text == 'Final':
                st.markdown(f"### 🏁 {game_status_text}")
            elif period_value > 0:
                st.markdown(f"### Q{period_value} {game_clock if game_clock else ''}")
            else:
                st.markdown(f"### {game_status_text}")
        
        # Split View Layout
        st.markdown("---")
        col_away, col_home = st.columns([1, 1])
        
        # Get team IDs for logos
        away_team_id = selected_game.get('away_team_id', '')
        home_team_id = selected_game.get('home_team_id', '')
        away_logo_url = f"https://cdn.nba.com/logos/nba/{away_team_id}/primary/L/logo.svg" if away_team_id else ""
        home_logo_url = f"https://cdn.nba.com/logos/nba/{home_team_id}/primary/L/logo.svg" if home_team_id else ""
        
        # Away Team Column
        with col_away:
            st.markdown(f"""
                <div style="display: flex; align-items: center; justify-content: center; gap: 15px; margin-bottom: 10px;">
                    <img src="{away_logo_url}" alt="{away_team_name} Logo" style="height: 80px; width: auto;" onerror="this.style.display='none'">
                    <h3 style="margin: 0;">{away_team_abbr} {away_team_name}</h3>
                </div>
            """, unsafe_allow_html=True)
            st.markdown(f"<h1 style='text-align: center; font-size: 48px; margin: 10px 0;'>{away_score}</h1>", unsafe_allow_html=True)
        
        # Home Team Column
        with col_home:
            st.markdown(f"""
                <div style="display: flex; align-items: center; justify-content: center; gap: 15px; margin-bottom: 10px;">
                    <img src="{home_logo_url}" alt="{home_team_name} Logo" style="height: 80px; width: auto;" onerror="this.style.display='none'">
                    <h3 style="margin: 0;">{home_team_abbr} {home_team_name}</h3>
                </div>
            """, unsafe_allow_html=True)
            st.markdown(f"<h1 style='text-align: center; font-size: 48px; margin: 10px 0;'>{home_score}</h1>", unsafe_allow_html=True)
        
        # Quarter Scores (below scores, above leaders)
        if away_periods or home_periods:
            st.markdown("---")
            q_score_cols = st.columns(2)
            
            with q_score_cols[0]:
                st.markdown(f"**{away_team_abbr} Quarter Scores:**")
                if away_periods:
                    q_scores = []
                    for i, period in enumerate(away_periods[:4], 1):  # Q1-Q4
                        score = period.get('score', 0)
                        q_scores.append(f"Q{i}: {score}")
                    if len(away_periods) > 4:  # Overtime periods
                        for i, period in enumerate(away_periods[4:], 5):
                            score = period.get('score', 0)
                            q_scores.append(f"OT{i-4}: {score}")
                    st.markdown(" | ".join(q_scores))
                else:
                    st.markdown("N/A")
            
            with q_score_cols[1]:
                st.markdown(f"**{home_team_abbr} Quarter Scores:**")
                if home_periods:
                    q_scores = []
                    for i, period in enumerate(home_periods[:4], 1):  # Q1-Q4
                        score = period.get('score', 0)
                        q_scores.append(f"Q{i}: {score}")
                    if len(home_periods) > 4:  # Overtime periods
                        for i, period in enumerate(home_periods[4:], 5):
                            score = period.get('score', 0)
                            q_scores.append(f"OT{i-4}: {score}")
                    st.markdown(" | ".join(q_scores))
                else:
                    st.markdown("N/A")
        
        # Game and Team Leaders (below scores)
        if len(away_df) > 0 and len(home_df) > 0:
            st.markdown("---")
            st.markdown("### Game & Team Leaders")
            
            # Combine both teams for game leaders
            all_players_df = pd.concat([away_df, home_df], ignore_index=True)
            
            # Find game leaders
            game_leader_pts = all_players_df.loc[all_players_df['PTS'].idxmax()] if len(all_players_df) > 0 else None
            game_leader_ast = all_players_df.loc[all_players_df['AST'].idxmax()] if len(all_players_df) > 0 else None
            game_leader_reb = all_players_df.loc[all_players_df['REB'].idxmax()] if len(all_players_df) > 0 else None
            game_leader_3pm = all_players_df.loc[all_players_df['3PM'].idxmax()] if len(all_players_df) > 0 else None
            game_leader_fta = all_players_df.loc[all_players_df['FTA'].idxmax()] if len(all_players_df) > 0 else None
            # Convert FPTS to numeric for comparison (it's stored as string with 2 decimals)
            all_players_df['FPTS_numeric'] = pd.to_numeric(all_players_df['FPTS'], errors='coerce').fillna(0.0)
            game_leader_fpts = all_players_df.loc[all_players_df['FPTS_numeric'].idxmax()] if len(all_players_df) > 0 else None
            
            # Find away team leaders
            away_leader_pts = away_df.loc[away_df['PTS'].idxmax()] if len(away_df) > 0 else None
            away_leader_ast = away_df.loc[away_df['AST'].idxmax()] if len(away_df) > 0 else None
            away_leader_reb = away_df.loc[away_df['REB'].idxmax()] if len(away_df) > 0 else None
            away_leader_3pm = away_df.loc[away_df['3PM'].idxmax()] if len(away_df) > 0 else None
            away_leader_fta = away_df.loc[away_df['FTA'].idxmax()] if len(away_df) > 0 else None
            away_df['FPTS_numeric'] = pd.to_numeric(away_df['FPTS'], errors='coerce').fillna(0.0)
            away_leader_fpts = away_df.loc[away_df['FPTS_numeric'].idxmax()] if len(away_df) > 0 else None
            
            # Find home team leaders
            home_leader_pts = home_df.loc[home_df['PTS'].idxmax()] if len(home_df) > 0 else None
            home_leader_ast = home_df.loc[home_df['AST'].idxmax()] if len(home_df) > 0 else None
            home_leader_reb = home_df.loc[home_df['REB'].idxmax()] if len(home_df) > 0 else None
            home_leader_3pm = home_df.loc[home_df['3PM'].idxmax()] if len(home_df) > 0 else None
            home_leader_fta = home_df.loc[home_df['FTA'].idxmax()] if len(home_df) > 0 else None
            home_df['FPTS_numeric'] = pd.to_numeric(home_df['FPTS'], errors='coerce').fillna(0.0)
            home_leader_fpts = home_df.loc[home_df['FPTS_numeric'].idxmax()] if len(home_df) > 0 else None
            
            leader_cols = st.columns(6)
            
            with leader_cols[0]:
                st.markdown("**Points**")
                if game_leader_pts is not None:
                    st.write(f"🏀 **{game_leader_pts['Name']}** ({game_leader_pts['PTS']})")
                if away_leader_pts is not None:
                    st.write(f"{away_team_abbr}: {away_leader_pts['Name']} ({away_leader_pts['PTS']})")
                if home_leader_pts is not None:
                    st.write(f"{home_team_abbr}: {home_leader_pts['Name']} ({home_leader_pts['PTS']})")
            
            with leader_cols[1]:
                st.markdown("**Assists**")
                if game_leader_ast is not None:
                    st.write(f"🏀 **{game_leader_ast['Name']}** ({game_leader_ast['AST']})")
                if away_leader_ast is not None:
                    st.write(f"{away_team_abbr}: {away_leader_ast['Name']} ({away_leader_ast['AST']})")
                if home_leader_ast is not None:
                    st.write(f"{home_team_abbr}: {home_leader_ast['Name']} ({home_leader_ast['AST']})")
            
            with leader_cols[2]:
                st.markdown("**Rebounds**")
                if game_leader_reb is not None:
                    st.write(f"🏀 **{game_leader_reb['Name']}** ({game_leader_reb['REB']})")
                if away_leader_reb is not None:
                    st.write(f"{away_team_abbr}: {away_leader_reb['Name']} ({away_leader_reb['REB']})")
                if home_leader_reb is not None:
                    st.write(f"{home_team_abbr}: {home_leader_reb['Name']} ({home_leader_reb['REB']})")
            
            with leader_cols[3]:
                st.markdown("**3-Pointers Made**")
                if game_leader_3pm is not None:
                    st.write(f"🏀 **{game_leader_3pm['Name']}** ({game_leader_3pm['3PM']})")
                if away_leader_3pm is not None:
                    st.write(f"{away_team_abbr}: {away_leader_3pm['Name']} ({away_leader_3pm['3PM']})")
                if home_leader_3pm is not None:
                    st.write(f"{home_team_abbr}: {home_leader_3pm['Name']} ({home_leader_3pm['3PM']})")
            
            with leader_cols[4]:
                st.markdown("**Free Throw Attempts**")
                if game_leader_fta is not None:
                    st.write(f"🏀 **{game_leader_fta['Name']}** ({game_leader_fta['FTA']})")
                if away_leader_fta is not None:
                    st.write(f"{away_team_abbr}: {away_leader_fta['Name']} ({away_leader_fta['FTA']})")
                if home_leader_fta is not None:
                    st.write(f"{home_team_abbr}: {home_leader_fta['Name']} ({home_leader_fta['FTA']})")
            
            with leader_cols[5]:
                st.markdown("**Fantasy Points**")
                if game_leader_fpts is not None:
                    st.write(f"🏀 **{game_leader_fpts['Name']}** ({game_leader_fpts['FPTS']})")
                if away_leader_fpts is not None:
                    st.write(f"{away_team_abbr}: {away_leader_fpts['Name']} ({away_leader_fpts['FPTS']})")
                if home_leader_fpts is not None:
                    st.write(f"{home_team_abbr}: {home_leader_fpts['Name']} ({home_leader_fpts['FPTS']})")
        
        # Continue with split view columns
        st.markdown("---")
        col_away2, col_home2 = st.columns([1, 1])
        
        # Away Team Column (continued)
        with col_away2:
            # Team Totals
            if away_totals and home_totals:
                st.markdown("**Team Totals**")
                st.markdown(f"**Shooting:** {away_totals['FGM-FGA']} FG | {away_totals['3PM-3PA']} 3PT | {away_totals['FTM-FTA']} FT")
                totals_cols = st.columns(4)
                
                with totals_cols[0]:
                    st.metric("PTS", away_totals['PTS'], 
                             delta=f"{get_stat_delta(away_totals['PTS'], home_totals['PTS']):.1f}",
                             delta_color="normal")
                    st.metric("REB", away_totals['REB'],
                             delta=f"{get_stat_delta(away_totals['REB'], home_totals['REB']):.1f}",
                             delta_color="normal")
                with totals_cols[1]:
                    st.metric("AST", away_totals['AST'],
                             delta=f"{get_stat_delta(away_totals['AST'], home_totals['AST']):.1f}",
                             delta_color="normal")
                    st.metric("TOV", away_totals['TOV'],
                             delta=f"{get_stat_delta(away_totals['TOV'], home_totals['TOV'], higher_is_better=False):.1f}",
                             delta_color="normal")
                with totals_cols[2]:
                    st.metric("BLK", away_totals['BLK'],
                             delta=f"{get_stat_delta(away_totals['BLK'], home_totals['BLK']):.1f}",
                             delta_color="normal")
                    st.metric("STL", away_totals['STL'],
                             delta=f"{get_stat_delta(away_totals['STL'], home_totals['STL']):.1f}",
                             delta_color="normal")
                with totals_cols[3]:
                    st.metric("FG%", f"{away_totals['FG%']:.1f}%",
                             delta=f"{get_stat_delta(away_totals['FG%'], home_totals['FG%']):.1f}%",
                             delta_color="normal")
                    st.metric("3P%", f"{away_totals['3P%']:.1f}%",
                             delta=f"{get_stat_delta(away_totals['3P%'], home_totals['3P%']):.1f}%",
                             delta_color="normal")
                
                # Special Stats Metrics
                if 'FB PTS' in away_totals and 'PITP' in away_totals and '2ND CH' in away_totals:
                    st.markdown("**Special Stats**")
                    special_cols = st.columns(4)
                    with special_cols[0]:
                        st.metric("Paint", away_totals['PITP'],
                                 delta=f"{get_stat_delta(away_totals['PITP'], home_totals.get('PITP', 0)):.1f}",
                                 delta_color="normal")
                    with special_cols[1]:
                        st.metric("2nd Chance", away_totals['2ND CH'],
                                 delta=f"{get_stat_delta(away_totals['2ND CH'], home_totals.get('2ND CH', 0)):.1f}",
                                 delta_color="normal")
                    with special_cols[2]:
                        st.metric("Fast Break", away_totals['FB PTS'],
                                 delta=f"{get_stat_delta(away_totals['FB PTS'], home_totals.get('FB PTS', 0)):.1f}",
                                 delta_color="normal")
                    with special_cols[3]:
                        st.metric("Points Off TOV", away_pts_off_tov,
                                 delta=f"{get_stat_delta(away_pts_off_tov, home_pts_off_tov):.1f}",
                                 delta_color="normal")
                    
                    # Always show the percentage calculation
                    combined_pts = away_2nd_chance + away_pts_off_tov
                    st.markdown(f"**2nd Chance + Points Off TOV:** {combined_pts} ({away_2nd_chance_tov_pct:.1f}% of total points)")
            
            # Starter Stats
            if away_starter_stats and away_starter_stats.get('PTS', 0) > 0 and home_starter_stats:
                st.markdown("---")
                st.markdown("**Starter Stats**")
                # Top row: Points and shooting percentages
                starter_top_cols = st.columns(4)
                with starter_top_cols[0]:
                    st.metric("PTS", away_starter_stats['PTS'],
                             delta=f"{get_stat_delta(away_starter_stats['PTS'], home_starter_stats.get('PTS', 0)):.1f}",
                             delta_color="normal")
                with starter_top_cols[1]:
                    st.metric("FG%", f"{away_starter_stats['FG%']:.1f}%",
                             delta=f"{get_stat_delta(away_starter_stats['FG%'], home_starter_stats.get('FG%', 0)):.1f}%",
                             delta_color="normal")
                with starter_top_cols[2]:
                    st.metric("3P%", f"{away_starter_stats['3P%']:.1f}%",
                             delta=f"{get_stat_delta(away_starter_stats['3P%'], home_starter_stats.get('3P%', 0)):.1f}%",
                             delta_color="normal")
                with starter_top_cols[3]:
                    st.metric("FT%", f"{away_starter_stats['FT%']:.1f}%",
                             delta=f"{get_stat_delta(away_starter_stats['FT%'], home_starter_stats.get('FT%', 0)):.1f}%",
                             delta_color="normal")
                # Bottom row: Assists, Rebounds, Paint, Fast Break
                starter_bottom_cols = st.columns(4)
                with starter_bottom_cols[0]:
                    st.metric("AST", away_starter_stats['AST'],
                             delta=f"{get_stat_delta(away_starter_stats['AST'], home_starter_stats.get('AST', 0)):.1f}",
                             delta_color="normal")
                with starter_bottom_cols[1]:
                    st.metric("REB", away_starter_stats['REB'],
                             delta=f"{get_stat_delta(away_starter_stats['REB'], home_starter_stats.get('REB', 0)):.1f}",
                             delta_color="normal")
                with starter_bottom_cols[2]:
                    st.metric("PITP", away_starter_stats.get('PITP', 0),
                             delta=f"{get_stat_delta(away_starter_stats.get('PITP', 0), home_starter_stats.get('PITP', 0)):.1f}",
                             delta_color="normal")
                with starter_bottom_cols[3]:
                    st.metric("FB PTS", away_starter_stats.get('FB PTS', 0),
                             delta=f"{get_stat_delta(away_starter_stats.get('FB PTS', 0), home_starter_stats.get('FB PTS', 0)):.1f}",
                             delta_color="normal")
                st.markdown(f"**Starter Shooting:** {away_starter_stats['FGM-FGA']} FG | {away_starter_stats['3PM-3PA']} 3PT | {away_starter_stats['FTM-FTA']} FT")
            
            # Bench Stats
            if away_bench_stats and len(away_bench_stats) > 0:
                st.markdown("---")
                st.markdown("**Bench Stats**")
                # Top row: Points and shooting percentages
                bench_top_cols = st.columns(4)
                with bench_top_cols[0]:
                    st.metric("PTS", away_bench_stats.get('PTS', 0),
                             delta=f"{get_stat_delta(away_bench_stats['PTS'], home_bench_stats.get('PTS', 0)):.1f}",
                             delta_color="normal")
                with bench_top_cols[1]:
                    st.metric("FG%", f"{away_bench_stats['FG%']:.1f}%",
                             delta=f"{get_stat_delta(away_bench_stats['FG%'], home_bench_stats.get('FG%', 0)):.1f}%",
                             delta_color="normal")
                with bench_top_cols[2]:
                    st.metric("3P%", f"{away_bench_stats['3P%']:.1f}%",
                             delta=f"{get_stat_delta(away_bench_stats['3P%'], home_bench_stats.get('3P%', 0)):.1f}%",
                             delta_color="normal")
                with bench_top_cols[3]:
                    st.metric("FT%", f"{away_bench_stats['FT%']:.1f}%",
                             delta=f"{get_stat_delta(away_bench_stats['FT%'], home_bench_stats.get('FT%', 0)):.1f}%",
                             delta_color="normal")
                # Bottom row: Assists, Rebounds, Paint, Fast Break
                bench_bottom_cols = st.columns(4)
                with bench_bottom_cols[0]:
                    st.metric("AST", away_bench_stats['AST'],
                             delta=f"{get_stat_delta(away_bench_stats['AST'], home_bench_stats.get('AST', 0)):.1f}",
                             delta_color="normal")
                with bench_bottom_cols[1]:
                    st.metric("REB", away_bench_stats['REB'],
                             delta=f"{get_stat_delta(away_bench_stats['REB'], home_bench_stats.get('REB', 0)):.1f}",
                             delta_color="normal")
                with bench_bottom_cols[2]:
                    st.metric("PITP", away_bench_stats.get('PITP', 0),
                             delta=f"{get_stat_delta(away_bench_stats.get('PITP', 0), home_bench_stats.get('PITP', 0)):.1f}",
                             delta_color="normal")
                with bench_bottom_cols[3]:
                    st.metric("FB PTS", away_bench_stats.get('FB PTS', 0),
                             delta=f"{get_stat_delta(away_bench_stats.get('FB PTS', 0), home_bench_stats.get('FB PTS', 0)):.1f}",
                             delta_color="normal")
                st.markdown(f"**Bench Shooting:** {away_bench_stats.get('FGM-FGA', '0-0')} FG | {away_bench_stats.get('3PM-3PA', '0-0')} 3PT | {away_bench_stats.get('FTM-FTA', '0-0')} FT")
            
            st.markdown("---")
            
            # Player Stats Table
            if len(away_df) > 0:
                st.markdown("**Player Stats**")
                # Select columns to display
                display_cols = ['Name', 'Pos', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FPTS',
                               'FGM-FGA', 'FG%', '3PM-3PA', '3P%', 'FTM-FTA', 'FT%', 
                               'FB PTS', 'PITP', '2ND CH', '+/-']
                
                # Filter to only columns that exist
                display_cols = [col for col in display_cols if col in away_df.columns]
                away_display = away_df[display_cols].copy()
                
                # Style the dataframe
                def highlight_starters(row):
                    if row.get('Starter', False) if 'Starter' in away_df.columns else False:
                        return ['background-color: #e8f4f8'] * len(row)
                    return [''] * len(row)
                
                # Remove helper columns from display
                if 'Starter' in away_display.columns:
                    away_display = away_display.drop(columns=['Starter'])
                if 'OnCourt' in away_display.columns:
                    away_display = away_display.drop(columns=['OnCourt'])
                if 'Status' in away_display.columns:
                    away_display = away_display.drop(columns=['Status'])
                
                # Highlight starters if available
                if 'Starter' in away_df.columns:
                    # Create a styled dataframe
                    def highlight_starters(row):
                        # row is a Series, use its index to look up Starter in original df
                        row_idx = row.name
                        if row_idx in away_df.index and away_df.loc[row_idx, 'Starter']:
                            return ['background-color: #e8f4f8'] * len(away_display.columns)
                        return [''] * len(away_display.columns)
                    
                    styled_away = away_display.style.apply(highlight_starters, axis=1)
                    st.dataframe(styled_away, width='stretch', hide_index=True)
                else:
                    st.dataframe(away_display, width='stretch', hide_index=True)
        
        # Home Team Column (continued)
        with col_home2:
            # Team Totals
            if home_totals and away_totals:
                st.markdown("**Team Totals**")
                st.markdown(f"**Shooting:** {home_totals['FGM-FGA']} FG | {home_totals['3PM-3PA']} 3PT | {home_totals['FTM-FTA']} FT")
                totals_cols = st.columns(4)
                
                with totals_cols[0]:
                    st.metric("PTS", home_totals['PTS'],
                             delta=f"{get_stat_delta(home_totals['PTS'], away_totals['PTS']):.1f}",
                             delta_color="normal")
                    st.metric("REB", home_totals['REB'],
                             delta=f"{get_stat_delta(home_totals['REB'], away_totals['REB']):.1f}",
                             delta_color="normal")
                with totals_cols[1]:
                    st.metric("AST", home_totals['AST'],
                             delta=f"{get_stat_delta(home_totals['AST'], away_totals['AST']):.1f}",
                             delta_color="normal")
                    st.metric("TOV", home_totals['TOV'],
                             delta=f"{get_stat_delta(home_totals['TOV'], away_totals['TOV'], higher_is_better=False):.1f}",
                             delta_color="normal")
                with totals_cols[2]:
                    st.metric("BLK", home_totals['BLK'],
                             delta=f"{get_stat_delta(home_totals['BLK'], away_totals['BLK']):.1f}",
                             delta_color="normal")
                    st.metric("STL", home_totals['STL'],
                             delta=f"{get_stat_delta(home_totals['STL'], away_totals['STL']):.1f}",
                             delta_color="normal")
                with totals_cols[3]:
                    st.metric("FG%", f"{home_totals['FG%']:.1f}%",
                             delta=f"{get_stat_delta(home_totals['FG%'], away_totals['FG%']):.1f}%",
                             delta_color="normal")
                    st.metric("3P%", f"{home_totals['3P%']:.1f}%",
                             delta=f"{get_stat_delta(home_totals['3P%'], away_totals['3P%']):.1f}%",
                             delta_color="normal")
                
                # Special Stats Metrics
                if 'FB PTS' in home_totals and 'PITP' in home_totals and '2ND CH' in home_totals:
                    st.markdown("**Special Stats**")
                    special_cols = st.columns(4)
                    with special_cols[0]:
                        st.metric("Paint", home_totals['PITP'],
                                 delta=f"{get_stat_delta(home_totals['PITP'], away_totals.get('PITP', 0)):.1f}",
                                 delta_color="normal")
                    with special_cols[1]:
                        st.metric("2nd Chance", home_totals['2ND CH'],
                                 delta=f"{get_stat_delta(home_totals['2ND CH'], away_totals.get('2ND CH', 0)):.1f}",
                                 delta_color="normal")
                    with special_cols[2]:
                        st.metric("Fast Break", home_totals['FB PTS'],
                                 delta=f"{get_stat_delta(home_totals['FB PTS'], away_totals.get('FB PTS', 0)):.1f}",
                                 delta_color="normal")
                    with special_cols[3]:
                        st.metric("Points Off TOV", home_pts_off_tov,
                                 delta=f"{get_stat_delta(home_pts_off_tov, away_pts_off_tov):.1f}",
                                 delta_color="normal")
                    
                    # Always show the percentage calculation
                    combined_pts = home_2nd_chance + home_pts_off_tov
                    st.markdown(f"**2nd Chance + Points Off TOV:** {combined_pts} ({home_2nd_chance_tov_pct:.1f}% of total points)")
            
            # Starter Stats
            if home_starter_stats and home_starter_stats.get('PTS', 0) > 0 and away_starter_stats:
                st.markdown("---")
                st.markdown("**Starter Stats**")
                # Top row: Points and shooting percentages
                starter_top_cols = st.columns(4)
                with starter_top_cols[0]:
                    st.metric("PTS", home_starter_stats['PTS'],
                             delta=f"{get_stat_delta(home_starter_stats['PTS'], away_starter_stats.get('PTS', 0)):.1f}",
                             delta_color="normal")
                with starter_top_cols[1]:
                    st.metric("FG%", f"{home_starter_stats['FG%']:.1f}%",
                             delta=f"{get_stat_delta(home_starter_stats['FG%'], away_starter_stats.get('FG%', 0)):.1f}%",
                             delta_color="normal")
                with starter_top_cols[2]:
                    st.metric("3P%", f"{home_starter_stats['3P%']:.1f}%",
                             delta=f"{get_stat_delta(home_starter_stats['3P%'], away_starter_stats.get('3P%', 0)):.1f}%",
                             delta_color="normal")
                with starter_top_cols[3]:
                    st.metric("FT%", f"{home_starter_stats['FT%']:.1f}%",
                             delta=f"{get_stat_delta(home_starter_stats['FT%'], away_starter_stats.get('FT%', 0)):.1f}%",
                             delta_color="normal")
                # Bottom row: Assists, Rebounds, Paint, Fast Break
                starter_bottom_cols = st.columns(4)
                with starter_bottom_cols[0]:
                    st.metric("AST", home_starter_stats['AST'],
                             delta=f"{get_stat_delta(home_starter_stats['AST'], away_starter_stats.get('AST', 0)):.1f}",
                             delta_color="normal")
                with starter_bottom_cols[1]:
                    st.metric("REB", home_starter_stats['REB'],
                             delta=f"{get_stat_delta(home_starter_stats['REB'], away_starter_stats.get('REB', 0)):.1f}",
                             delta_color="normal")
                with starter_bottom_cols[2]:
                    st.metric("PITP", home_starter_stats.get('PITP', 0),
                             delta=f"{get_stat_delta(home_starter_stats.get('PITP', 0), away_starter_stats.get('PITP', 0)):.1f}",
                             delta_color="normal")
                with starter_bottom_cols[3]:
                    st.metric("FB PTS", home_starter_stats.get('FB PTS', 0),
                             delta=f"{get_stat_delta(home_starter_stats.get('FB PTS', 0), away_starter_stats.get('FB PTS', 0)):.1f}",
                             delta_color="normal")
                st.markdown(f"**Starter Shooting:** {home_starter_stats['FGM-FGA']} FG | {home_starter_stats['3PM-3PA']} 3PT | {home_starter_stats['FTM-FTA']} FT")
            
            # Bench Stats
            if home_bench_stats and len(home_bench_stats) > 0:
                st.markdown("---")
                st.markdown("**Bench Stats**")
                # Top row: Points and shooting percentages
                bench_top_cols = st.columns(4)
                with bench_top_cols[0]:
                    st.metric("PTS", home_bench_stats['PTS'],
                             delta=f"{get_stat_delta(home_bench_stats['PTS'], away_bench_stats.get('PTS', 0)):.1f}",
                             delta_color="normal")
                with bench_top_cols[1]:
                    st.metric("FG%", f"{home_bench_stats['FG%']:.1f}%",
                             delta=f"{get_stat_delta(home_bench_stats['FG%'], away_bench_stats.get('FG%', 0)):.1f}%",
                             delta_color="normal")
                with bench_top_cols[2]:
                    st.metric("3P%", f"{home_bench_stats['3P%']:.1f}%",
                             delta=f"{get_stat_delta(home_bench_stats['3P%'], away_bench_stats.get('3P%', 0)):.1f}%",
                             delta_color="normal")
                with bench_top_cols[3]:
                    st.metric("FT%", f"{home_bench_stats['FT%']:.1f}%",
                             delta=f"{get_stat_delta(home_bench_stats['FT%'], away_bench_stats.get('FT%', 0)):.1f}%",
                             delta_color="normal")
                # Bottom row: Assists, Rebounds, Paint, Fast Break
                bench_bottom_cols = st.columns(4)
                with bench_bottom_cols[0]:
                    st.metric("AST", home_bench_stats['AST'],
                             delta=f"{get_stat_delta(home_bench_stats['AST'], away_bench_stats.get('AST', 0)):.1f}",
                             delta_color="normal")
                with bench_bottom_cols[1]:
                    st.metric("REB", home_bench_stats['REB'],
                             delta=f"{get_stat_delta(home_bench_stats['REB'], away_bench_stats.get('REB', 0)):.1f}",
                             delta_color="normal")
                with bench_bottom_cols[2]:
                    st.metric("PITP", home_bench_stats.get('PITP', 0),
                             delta=f"{get_stat_delta(home_bench_stats.get('PITP', 0), away_bench_stats.get('PITP', 0)):.1f}",
                             delta_color="normal")
                with bench_bottom_cols[3]:
                    st.metric("FB PTS", home_bench_stats.get('FB PTS', 0),
                             delta=f"{get_stat_delta(home_bench_stats.get('FB PTS', 0), away_bench_stats.get('FB PTS', 0)):.1f}",
                             delta_color="normal")
                st.markdown(f"**Bench Shooting:** {home_bench_stats['FGM-FGA']} FG | {home_bench_stats['3PM-3PA']} 3PT | {home_bench_stats['FTM-FTA']} FT")
            
            st.markdown("---")
            
            # Player Stats Table
            if len(home_df) > 0:
                st.markdown("**Player Stats**")
                # Select columns to display
                display_cols = ['Name', 'Pos', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FPTS',
                               'FGM-FGA', 'FG%', '3PM-3PA', '3P%', 'FTM-FTA', 'FT%', 
                               'FB PTS', 'PITP', '2ND CH', '+/-']
                
                # Filter to only columns that exist
                display_cols = [col for col in display_cols if col in home_df.columns]
                home_display = home_df[display_cols].copy()
                
                # Remove helper columns from display
                if 'Starter' in home_display.columns:
                    home_display = home_display.drop(columns=['Starter'])
                if 'OnCourt' in home_display.columns:
                    home_display = home_display.drop(columns=['OnCourt'])
                if 'Status' in home_display.columns:
                    home_display = home_display.drop(columns=['Status'])
                
                # Highlight starters if available
                if 'Starter' in home_df.columns:
                    # Create a styled dataframe
                    def highlight_starters(row):
                        # row is a Series, use its index to look up Starter in original df
                        row_idx = row.name
                        if row_idx in home_df.index and home_df.loc[row_idx, 'Starter']:
                            return ['background-color: #e8f4f8'] * len(home_display.columns)
                        return [''] * len(home_display.columns)
                    
                    styled_home = home_display.style.apply(highlight_starters, axis=1)
                    st.dataframe(styled_home, width='stretch', hide_index=True)
                else:
                    st.dataframe(home_display, width='stretch', hide_index=True)
        
        # Auto-refresh logic
        if st.session_state['auto_refresh']:
            if game_status_text == 'Final':
                st.session_state['auto_refresh'] = False
                st.info("Game is final. Auto-refresh disabled.")
            else:
                # Check if enough time has passed since last refresh
                if st.session_state['last_refresh']:
                    elapsed = (datetime.now() - st.session_state['last_refresh']).total_seconds()
                    if elapsed >= st.session_state['refresh_interval']:
                        # Clear cache and rerun
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        remaining = int(st.session_state['refresh_interval'] - elapsed)
                        st.caption(f"🔄 Auto-refresh enabled. Refreshing in {remaining} seconds...")
                else:
                    st.caption("🔄 Auto-refresh enabled. Refreshing...")
                    st.cache_data.clear()
                    st.rerun()
    else:
        st.info("Loading box score...")

else:
    st.info("Please select a game to view live stats.")

