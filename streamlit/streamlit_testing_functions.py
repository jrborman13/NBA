import nba_api.stats.endpoints
import requests
import json
import pandas as pd
import nba_api
import streamlit as st
import os
import sys

# Add path to import prediction_features
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'new-streamlit-app', 'player-app'))
try:
    import prediction_features as pf
except ImportError:
    pf = None

current_season = '2025-26'
season_type = 'Regular Season'
# opponent_id = 1610612760

# ============================================================
# CACHED TEAM STATS FUNCTIONS
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_team_advanced_stats(season: str = current_season, last_n_games: int = None):
    """Get team advanced stats"""
    # Fetch from API
    try:
        params = {
            'league_id_nullable': '00',
            'measure_type_detailed_defense': 'Advanced',
            'pace_adjust': 'N',
            'per_mode_detailed': 'PerGame',
            'season': season,
            'season_type_all_star': season_type
        }
        if last_n_games:
            params['last_n_games'] = last_n_games
        
        df = nba_api.stats.endpoints.LeagueDashTeamStats(**params).get_data_frames()[0]
        
        # Add ranking columns
        df['OFF_RATING_RANK'] = df['OFF_RATING'].rank(ascending=False, method='first').astype(int)
        df['DEF_RATING_RANK'] = df['DEF_RATING'].rank(ascending=True, method='first').astype(int)
        df['NET_RATING_RANK'] = df['NET_RATING'].rank(ascending=False, method='first').astype(int)
        df['PACE_RANK'] = df['PACE'].rank(ascending=False, method='first').astype(int)
        df['AST_PCT_RANK'] = df['AST_PCT'].rank(ascending=False, method='first').astype(int)
        df['TM_TOV_PCT_RANK'] = df['TM_TOV_PCT'].rank(ascending=True, method='first').astype(int)
        df['AST_TO_RANK'] = df['AST_TO'].rank(ascending=False, method='first').astype(int)
        df['DREB_PCT_RANK'] = df['DREB_PCT'].rank(ascending=False, method='first').astype(int)
        df['OREB_PCT_RANK'] = df['OREB_PCT'].rank(ascending=False, method='first').astype(int)
        df['REB_PCT_RANK'] = df['REB_PCT'].rank(ascending=False, method='first').astype(int)
        
        return df
    except Exception as e:
        print(f"Error fetching team advanced stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_team_misc_stats(season: str = current_season, last_n_games: int = None):
    """Get team misc stats"""
    # Fetch from API
    try:
        params = {
            'league_id_nullable': '00',
            'measure_type_detailed_defense': 'Misc',
            'pace_adjust': 'N',
            'per_mode_detailed': 'PerGame',
            'season': season,
            'season_type_all_star': season_type
        }
        if last_n_games:
            params['last_n_games'] = last_n_games
        
        df = nba_api.stats.endpoints.LeagueDashTeamStats(**params).get_data_frames()[0]
        
        # Add differentials and rankings
        df['PTS_PAINT_DIFF'] = df['PTS_PAINT'] - df['OPP_PTS_PAINT']
        df['PTS_PAINT_DIFF_RANK'] = df['PTS_PAINT_DIFF'].rank(ascending=False, method='first')
        df['PTS_2ND_CHANCE_DIFF'] = df['PTS_2ND_CHANCE'] - df['OPP_PTS_2ND_CHANCE']
        df['PTS_2ND_CHANCE_DIFF_RANK'] = df['PTS_2ND_CHANCE_DIFF'].rank(ascending=False, method='first')
        df['PTS_FB_DIFF'] = df['PTS_FB'] - df['OPP_PTS_FB']
        df['PTS_FB_DIFF_RANK'] = df['PTS_FB_DIFF'].rank(ascending=False, method='first')
        df['PTS_OFF_TOV_DIFF'] = df['PTS_OFF_TOV'] - df['OPP_PTS_OFF_TOV']
        df['PTS_OFF_TOV_DIFF_RANK'] = df['PTS_OFF_TOV_DIFF'].rank(ascending=False, method='first')
        
        df['PTS_PAINT_RANK'] = df['PTS_PAINT'].rank(ascending=False, method='first').astype(int)
        df['OPP_PTS_PAINT_RANK'] = df['OPP_PTS_PAINT'].rank(ascending=True, method='first').astype(int)
        df['PTS_2ND_CHANCE_RANK'] = df['PTS_2ND_CHANCE'].rank(ascending=False, method='first').astype(int)
        df['OPP_PTS_2ND_CHANCE_RANK'] = df['OPP_PTS_2ND_CHANCE'].rank(ascending=True, method='first').astype(int)
        df['PTS_FB_RANK'] = df['PTS_FB'].rank(ascending=False, method='first').astype(int)
        df['OPP_PTS_FB_RANK'] = df['OPP_PTS_FB'].rank(ascending=True, method='first').astype(int)
        df['PTS_OFF_TOV_RANK'] = df['PTS_OFF_TOV'].rank(ascending=False, method='first').astype(int)
        df['OPP_PTS_OFF_TOV_RANK'] = df['OPP_PTS_OFF_TOV'].rank(ascending=True, method='first').astype(int)
        
        return df
    except Exception as e:
        print(f"Error fetching team misc stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_team_traditional_stats(season: str = current_season, last_n_games: int = None, group_quantity: str = None):
    """Get team traditional stats"""
    # Fetch from API
    try:
        params = {
            'league_id_nullable': '00',
            'measure_type_detailed_defense': 'Base',
            'pace_adjust': 'N',
            'per_mode_detailed': 'PerGame',
            'season': season,
            'season_type_all_star': season_type
        }
        if last_n_games:
            params['last_n_games'] = last_n_games
        if group_quantity:
            params['starter_bench_nullable'] = group_quantity
        
        df = nba_api.stats.endpoints.LeagueDashTeamStats(**params).get_data_frames()[0]
        
        # Add ranking columns
        df['AST_RANK'] = df['AST'].rank(ascending=False, method='first').astype(int)
        df['TOV_RANK'] = df['TOV'].rank(ascending=True, method='first').astype(int)
        if group_quantity:  # Starters/Bench
            df['PTS_RANK'] = df['PTS'].rank(ascending=False, method='first').astype(int)
        
        return df
    except Exception as e:
        print(f"Error fetching team traditional stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_team_four_factors_stats(season: str = current_season, last_n_games: int = None):
    """Get team four factors stats"""
    # Fetch from API
    try:
        params = {
            'league_id_nullable': '00',
            'measure_type_detailed_defense': 'Four Factors',
            'pace_adjust': 'N',
            'per_mode_detailed': 'PerGame',
            'season': season,
            'season_type_all_star': season_type
        }
        if last_n_games:
            params['last_n_games'] = last_n_games
        
        df = nba_api.stats.endpoints.LeagueDashTeamStats(**params).get_data_frames()[0]
        
        # Add ranking columns
        df['OPP_TOV_PCT_RANK'] = df['OPP_TOV_PCT'].rank(ascending=False, method='first').astype(int)
        
        return df
    except Exception as e:
        print(f"Error fetching team four factors stats: {e}")
        return pd.DataFrame()


#ADVANCED DATA LOADING
##SEASON
print("[DEBUG] Loading team advanced stats (module level)...")
data_adv_season = get_cached_team_advanced_stats()
print(f"[DEBUG] Team advanced stats loaded: {len(data_adv_season)} rows")

# Add missing ranking columns for Core Stats
data_adv_season['OFF_RATING_RANK'] = data_adv_season['OFF_RATING'].rank(ascending=False, method='first').astype(int)
data_adv_season['DEF_RATING_RANK'] = data_adv_season['DEF_RATING'].rank(ascending=True, method='first').astype(int)
data_adv_season['NET_RATING_RANK'] = data_adv_season['NET_RATING'].rank(ascending=False, method='first').astype(int)
data_adv_season['PACE_RANK'] = data_adv_season['PACE'].rank(ascending=False, method='first').astype(int)
data_adv_season['AST_PCT_RANK'] = data_adv_season['AST_PCT'].rank(ascending=False, method='first').astype(int)
data_adv_season['TM_TOV_PCT_RANK'] = data_adv_season['TM_TOV_PCT'].rank(ascending=True, method='first').astype(int)
data_adv_season['AST_TO_RANK'] = data_adv_season['AST_TO'].rank(ascending=False, method='first').astype(int)
data_adv_season['DREB_PCT_RANK'] = data_adv_season['DREB_PCT'].rank(ascending=False, method='first').astype(int)
data_adv_season['OREB_PCT_RANK'] = data_adv_season['OREB_PCT'].rank(ascending=False, method='first').astype(int)
data_adv_season['REB_PCT_RANK'] = data_adv_season['REB_PCT'].rank(ascending=False, method='first').astype(int)
##LAST 5 GAMES
data_adv_L5 = get_cached_team_advanced_stats(last_n_games=5)

#MISC DATA LOADING
##SEASON
data_misc_season = get_cached_team_misc_stats()
##LAST 5 GAMES
data_misc_L5 = get_cached_team_misc_stats(last_n_games=5)

#LOAD TRADITIONAL DATA
## SEASON
data_trad_season = get_cached_team_traditional_stats()
## LAST 5
data_trad_L5 = get_cached_team_traditional_stats(last_n_games=5)
## SEASON - STARTERS
data_trad_season_starters = get_cached_team_traditional_stats(group_quantity='Starters')
## LAST 5 - STARTERS
data_trad_L5_starters = get_cached_team_traditional_stats(last_n_games=5, group_quantity='Starters')
## SEASON - BENCH
data_trad_season_bench = get_cached_team_traditional_stats(group_quantity='Bench')
## LAST 5 - BENCH
data_trad_L5_bench = get_cached_team_traditional_stats(last_n_games=5, group_quantity='Bench')

#LOAD FOUR FACTORS DATA
##SEASON
data_4F_season = get_cached_team_four_factors_stats()
## LAST 5 GAMES
data_4F_L5 = get_cached_team_four_factors_stats(last_n_games=5)

#Key base variables
wolves_id = data_adv_season.loc[data_adv_season['TEAM_NAME'] == 'Minnesota Timberwolves', 'TEAM_ID'].values[0]
# wolves_id = '1610612750'
logo_link = f'https://cdn.nba.com/logos/nba/{wolves_id}/primary/L/logo.svg'
timberwolves = 'Minnesota Timberwolves'
nba_logo = 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/leagues/500/nba.png?w=100&h=100&transparent=true'

# Function to get standings with clutch data
# Removed @st.cache_data - using Supabase cache instead
@st.cache_data(ttl=3600, show_spinner=False)
def get_standings_with_clutch(season='2025-26'):
    """
    Fetch NBA standings and merge with team clutch records.
    Clutch is defined as last 5 minutes of game with score within 5 points.
    
    Args:
        season: Season string (e.g., '2025-26')
    
    Returns:
        DataFrame with standings data including a 'Clutch' column (W-L format)
    """
    # Fetch from API
    try:
        # Fetch regular standings
        standings_df = nba_api.stats.endpoints.LeagueStandings(
            league_id='00', 
            season=season, 
            season_type='Regular Season'
        ).get_data_frames()[0]
        
        # Fetch team clutch stats
        try:
            clutch_df = nba_api.stats.endpoints.LeagueDashTeamClutch(
                league_id_nullable='00',
                season=season,
                season_type_all_star='Regular Season',
                clutch_time='Last 5 Minutes',
                point_diff=5,  # Within 5 points
                ahead_behind='Ahead or Behind'
            ).get_data_frames()[0]
            
            # Merge clutch data with standings on TEAM_ID
            # Standings uses 'TeamID', clutch uses 'TEAM_ID'
            standings_df = standings_df.merge(
                clutch_df[['TEAM_ID', 'W', 'L']],
                left_on='TeamID',
                right_on='TEAM_ID',
                how='left'
            )
            
            # Create Clutch column formatted as "W-L"
            standings_df['Clutch'] = standings_df.apply(
                lambda row: f"{int(row['W'])}-{int(row['L'])}" 
                if pd.notna(row['W']) and pd.notna(row['L']) 
                else "N/A",
                axis=1
            )
            
            # Drop the temporary merge columns
            standings_df = standings_df.drop(columns=['TEAM_ID', 'W', 'L'], errors='ignore')
            
        except Exception as e:
            # If clutch data fetch fails, just add empty Clutch column
            standings_df['Clutch'] = "N/A"
        
        return standings_df
        
    except Exception as e:
        # If standings fetch fails, return empty DataFrame
        return pd.DataFrame()

#Load in the current NBA standings
standings = get_standings_with_clutch(current_season)

# Function to get today's matchups
def get_todays_matchups():
    """Fetch today's NBA matchups and return as list of dictionaries"""
    try:
        from nba_api.live.nba.endpoints import scoreboard
        games = scoreboard.ScoreBoard()
        games_json = json.loads(games.get_json())
        todays_games = games_json['scoreboard']['games']

        matchups = []
        for game in todays_games:
            away_team_id = game['awayTeam']['teamId']
            home_team_id = game['homeTeam']['teamId']
            game_id = game['gameId']
            game_time = game.get('gameTimeUTC', '')
            
            # Get team names
            try:
                away_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_team_id, 'TEAM_NAME'].values[0]
                home_name = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_team_id, 'TEAM_NAME'].values[0]
            except:
                away_name = game['awayTeam'].get('teamName', 'Unknown')
                home_name = game['homeTeam'].get('teamName', 'Unknown')
            
            matchups.append({
                'game_id': game_id,
                'away_team_id': away_team_id,
                'home_team_id': home_team_id,
                'away_team_name': away_name,
                'home_team_name': home_name,
                'game_time': game_time,
                'is_wolves_game': (away_team_id == wolves_id or home_team_id == wolves_id)
            })
        
        # Sort by game time, with Wolves games first
        matchups.sort(key=lambda x: (not x['is_wolves_game'], x['game_time']))
        
        return matchups
    except Exception as e:
        print(f"Error fetching matchups: {e}")
        return []

# Get today's matchups
todays_matchups = get_todays_matchups()

# Global variable to store selected matchup (can be set by Streamlit app before stats calculation)
# Check if streamlit session state exists and has matchup_override
_selected_matchup_override = None
try:
    import streamlit as st
    if hasattr(st, 'session_state') and 'matchup_override' in st.session_state:
        _selected_matchup_override = st.session_state['matchup_override']
except:
    pass

def set_matchup_override(matchup):
    """Set matchup override before stats are calculated"""
    global _selected_matchup_override
    _selected_matchup_override = matchup

# Function to update selected matchup
def update_selected_matchup(matchup):
    """Update module-level variables based on selected matchup"""
    global game_id, away_id, home_id, away_logo_link, home_logo_link, game_title, home_or_away
    
    if matchup:
        game_id = matchup['game_id']
        away_id = matchup['away_team_id']
        home_id = matchup['home_team_id']
        
        if away_id == wolves_id:
            home_or_away = 'Away'
            away_logo_link = f'https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg'
            home_logo_link = f'https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg'
            game_title = f'Minnesota Timberwolves at {matchup["home_team_name"]}'
        elif home_id == wolves_id:
            home_or_away = 'Home'
            away_logo_link = f'https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg'
            home_logo_link = f'https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg'
            game_title = f'{matchup["away_team_name"]} at Minnesota Timberwolves'
        else:
            home_or_away = None
            away_logo_link = f'https://cdn.nba.com/logos/nba/{away_id}/primary/L/logo.svg'
            home_logo_link = f'https://cdn.nba.com/logos/nba/{home_id}/primary/L/logo.svg'
            game_title = f'{matchup["away_team_name"]} at {matchup["home_team_name"]}'
    else:
        game_id = None
        home_or_away = None
        home_id = None
        home_logo_link = None
        away_id = None
        away_logo_link = None
        game_title = "No game today"

# Default to first matchup (which will be Wolves game if available, otherwise first by time)
# Use override if set, otherwise use first matchup
selected_matchup = None
if _selected_matchup_override is not None:
    selected_matchup = _selected_matchup_override
elif todays_matchups:
    selected_matchup = todays_matchups[0]  # Default to first (Wolves game if available)

if selected_matchup:
    update_selected_matchup(selected_matchup)
else:
    update_selected_matchup(None)

# Helper function to safely get values from DataFrame
def safe_get_value(df, team_id, column, default=None, id_column=None):
    """Safely get a value from DataFrame, returning default if not found
    
    Args:
        df: DataFrame to search
        team_id: Team ID to search for
        column: Column name to retrieve
        default: Default value if not found
        id_column: ID column name (auto-detects 'TEAM_ID' or 'TeamID' if None)
    """
    if team_id is None:
        return default
    
    # Auto-detect ID column name
    if id_column is None:
        if 'TEAM_ID' in df.columns:
            id_column = 'TEAM_ID'
        elif 'TeamID' in df.columns:
            id_column = 'TeamID'
        else:
            # Try to find any column that might be the ID column
            id_candidates = [col for col in df.columns if 'id' in col.lower() or 'team' in col.lower()]
            if id_candidates:
                id_column = id_candidates[0]
            else:
                return default
    
    if id_column not in df.columns or column not in df.columns:
        return default
    
    filtered = df.loc[df[id_column] == team_id, column]
    if len(filtered) > 0:
        return filtered.values[0]
    return default

# Only calculate stats if we have valid team IDs
if away_id is not None and home_id is not None:
#Record and Seed
## Away Team
    away_team_record = safe_get_value(standings, away_id, 'Record', id_column='TeamID')
    away_team_seed = safe_get_value(standings, away_id, 'PlayoffRank', id_column='TeamID')
    away_team_division_seed = safe_get_value(standings, away_id, 'DivisionRank', id_column='TeamID')
    
## Home Team
    home_team_record = safe_get_value(standings, home_id, 'Record', id_column='TeamID')
    home_team_seed = safe_get_value(standings, home_id, 'PlayoffRank', id_column='TeamID')
    home_team_division_seed = safe_get_value(standings, home_id, 'DivisionRank', id_column='TeamID')

#Offensive Ratings
## Away Team
    away_team_ortg = safe_get_value(data_adv_season, away_id, 'OFF_RATING', 0)
    away_team_ortg_rank = safe_get_value(data_adv_season, away_id, 'OFF_RATING_RANK', 0)
    l5_away_team_ortg = safe_get_value(data_adv_L5, away_id, 'OFF_RATING', 0)
    l5_away_team_ortg_rank = safe_get_value(data_adv_L5, away_id, 'OFF_RATING_RANK', 0)
##League Average
    la_ortg = round(data_adv_season['OFF_RATING'].mean(), 1)
    l5_la_ortg = round(data_adv_L5['OFF_RATING'].mean(), 1)
## Home Team
    home_team_ortg = safe_get_value(data_adv_season, home_id, 'OFF_RATING', 0)
    home_team_ortg_rank = safe_get_value(data_adv_season, home_id, 'OFF_RATING_RANK', 0)
    l5_home_team_ortg = safe_get_value(data_adv_L5, home_id, 'OFF_RATING', 0)
    l5_home_team_ortg_rank = safe_get_value(data_adv_L5, home_id, 'OFF_RATING_RANK', 0)

#Defensive Ratings
## Away Team
    away_team_drtg = safe_get_value(data_adv_season, away_id, 'DEF_RATING', 0)
    away_team_drtg_rank = safe_get_value(data_adv_season, away_id, 'DEF_RATING_RANK', 0)
    l5_away_team_drtg = safe_get_value(data_adv_L5, away_id, 'DEF_RATING', 0)
    l5_away_team_drtg_rank = safe_get_value(data_adv_L5, away_id, 'DEF_RATING_RANK', 0)
##League Average
    la_drtg = round(data_adv_season['DEF_RATING'].mean(), 1)
    l5_la_drtg = round(data_adv_L5['DEF_RATING'].mean(), 1)
## Home Team
    home_team_drtg = safe_get_value(data_adv_season, home_id, 'DEF_RATING', 0)
    home_team_drtg_rank = safe_get_value(data_adv_season, home_id, 'DEF_RATING_RANK', 0)
    l5_home_team_drtg = safe_get_value(data_adv_L5, home_id, 'DEF_RATING', 0)
    l5_home_team_drtg_rank = safe_get_value(data_adv_L5, home_id, 'DEF_RATING_RANK', 0)

#Net Ratings
## Away Team
    away_team_net = safe_get_value(data_adv_season, away_id, 'NET_RATING', 0)
    away_team_net_rank = safe_get_value(data_adv_season, away_id, 'NET_RATING_RANK', 0)
    l5_away_team_net = safe_get_value(data_adv_L5, away_id, 'NET_RATING', 0)
    l5_away_team_net_rank = safe_get_value(data_adv_L5, away_id, 'NET_RATING_RANK', 0)
##League Average
    la_net = 0
    l5_la_net = 0
## Home Team
    home_team_net = safe_get_value(data_adv_season, home_id, 'NET_RATING', 0)
    home_team_net_rank = safe_get_value(data_adv_season, home_id, 'NET_RATING_RANK', 0)
    l5_home_team_net = safe_get_value(data_adv_L5, home_id, 'NET_RATING', 0)
    l5_home_team_net_rank = safe_get_value(data_adv_L5, home_id, 'NET_RATING_RANK', 0)

#REBOUND PERCENTAGES

#DREB%
## Away Team
    away_team_dreb = safe_get_value(data_adv_season, away_id, 'DREB_PCT', 0)
    away_team_dreb_rank = safe_get_value(data_adv_season, away_id, 'DREB_PCT_RANK', 0)
    l5_away_team_dreb = safe_get_value(data_adv_L5, away_id, 'DREB_PCT', 0)
    l5_away_team_dreb_rank = safe_get_value(data_adv_L5, away_id, 'DREB_PCT_RANK', 0)
## League Average
    la_dreb = round(data_adv_season['DREB_PCT'].mean(), 3)
    l5_la_dreb = round(data_adv_L5['DREB_PCT'].mean(), 3)
## Home Team
    home_team_dreb = safe_get_value(data_adv_season, home_id, 'DREB_PCT', 0)
    home_team_dreb_rank = safe_get_value(data_adv_season, home_id, 'DREB_PCT_RANK', 0)
    l5_home_team_dreb = safe_get_value(data_adv_L5, home_id, 'DREB_PCT', 0)
    l5_home_team_dreb_rank = safe_get_value(data_adv_L5, home_id, 'DREB_PCT_RANK', 0)

#OREB%
## Away Team
    away_team_oreb = safe_get_value(data_adv_season, away_id, 'OREB_PCT', 0)
    away_team_oreb_rank = safe_get_value(data_adv_season, away_id, 'OREB_PCT_RANK', 0)
    l5_away_team_oreb = safe_get_value(data_adv_L5, away_id, 'OREB_PCT', 0)
    l5_away_team_oreb_rank = safe_get_value(data_adv_L5, away_id, 'OREB_PCT_RANK', 0)
## League Average
    la_oreb = round(data_adv_season['OREB_PCT'].mean(), 3)
    l5_la_oreb = round(data_adv_L5['OREB_PCT'].mean(), 3)
## Home Team
    home_team_oreb = safe_get_value(data_adv_season, home_id, 'OREB_PCT', 0)
    home_team_oreb_rank = safe_get_value(data_adv_season, home_id, 'OREB_PCT_RANK', 0)
    l5_home_team_oreb = safe_get_value(data_adv_L5, home_id, 'OREB_PCT', 0)
    l5_home_team_oreb_rank = safe_get_value(data_adv_L5, home_id, 'OREB_PCT_RANK', 0)

#REB%
## Away Team
    away_team_reb = safe_get_value(data_adv_season, away_id, 'REB_PCT', 0)
    away_team_reb_rank = safe_get_value(data_adv_season, away_id, 'REB_PCT_RANK', 0)
    l5_away_team_reb = safe_get_value(data_adv_L5, away_id, 'REB_PCT', 0)
    l5_away_team_reb_rank = safe_get_value(data_adv_L5, away_id, 'REB_PCT_RANK', 0)
## League Average
    la_reb = round(data_adv_season['REB_PCT'].mean(), 3)
    l5_la_reb = round(data_adv_L5['REB_PCT'].mean(), 3)
## Home Team
    home_team_reb = safe_get_value(data_adv_season, home_id, 'REB_PCT', 0)
    home_team_reb_rank = safe_get_value(data_adv_season, home_id, 'REB_PCT_RANK', 0)
    l5_home_team_reb = safe_get_value(data_adv_L5, home_id, 'REB_PCT', 0)
    l5_home_team_reb_rank = safe_get_value(data_adv_L5, home_id, 'REB_PCT_RANK', 0)
else:
    # Set default values when no game is found
    away_team_record = None
    away_team_seed = None
    away_team_division_seed = None
    home_team_record = None
    home_team_seed = None
    home_team_division_seed = None
    away_team_ortg = 0
    away_team_ortg_rank = 0
    l5_away_team_ortg = 0
    l5_away_team_ortg_rank = 0
    la_ortg = 0
    l5_la_ortg = 0
    home_team_ortg = 0
    home_team_ortg_rank = 0
    l5_home_team_ortg = 0
    l5_home_team_ortg_rank = 0
    
    #Defensive Ratings
    ## Away Team
    away_team_drtg = 0
    away_team_drtg_rank = 0
    l5_away_team_drtg = 0
    l5_away_team_drtg_rank = 0
    ##League Average
    la_drtg = round(data_adv_season['DEF_RATING'].mean(), 1)
    l5_la_drtg = round(data_adv_L5['DEF_RATING'].mean(), 1)
    ## Home Team
    home_team_drtg = 0
    home_team_drtg_rank = 0
    l5_home_team_drtg = 0
    l5_home_team_drtg_rank = 0
    
    #Net Ratings
    ## Away Team
    away_team_net = 0
    away_team_net_rank = 0
    l5_away_team_net = 0
    l5_away_team_net_rank = 0
    ##League Average
    la_net = 0
    l5_la_net = 0
    ## Home Team
    home_team_net = 0
    home_team_net_rank = 0
    l5_home_team_net = 0
    l5_home_team_net_rank = 0
    
    #REBOUND PERCENTAGES
    
    #DREB%
    ## Away Team
    away_team_dreb = 0
    away_team_dreb_rank = 0
    l5_away_team_dreb = 0
    l5_away_team_dreb_rank = 0
    ## League Average
    la_dreb = round(data_adv_season['DREB_PCT'].mean(), 3)
    l5_la_dreb = round(data_adv_L5['DREB_PCT'].mean(), 3)
    ## Home Team
    home_team_dreb = 0
    home_team_dreb_rank = 0
    l5_home_team_dreb = 0
    l5_home_team_dreb_rank = 0
    
    #OREB%
    ## Away Team
    away_team_oreb = 0
    away_team_oreb_rank = 0
    l5_away_team_oreb = 0
    l5_away_team_oreb_rank = 0
    ## League Average
    la_oreb = round(data_adv_season['OREB_PCT'].mean(), 3)
    l5_la_oreb = round(data_adv_L5['OREB_PCT'].mean(), 3)
    ## Home Team
    home_team_oreb = 0
    home_team_oreb_rank = 0
    l5_home_team_oreb = 0
    l5_home_team_oreb_rank = 0
    
    #REB%
    ## Away Team
    away_team_reb = 0
    away_team_reb_rank = 0
    l5_away_team_reb = 0
    l5_away_team_reb_rank = 0
    ## League Average
    la_reb = round(data_adv_season['REB_PCT'].mean(), 3)
    l5_la_reb = round(data_adv_L5['REB_PCT'].mean(), 3)
    ## Home Team
    home_team_reb = 0
    home_team_reb_rank = 0
    l5_home_team_reb = 0
    l5_home_team_reb_rank = 0
    
    # Initialize all other stats used by the app to defaults
    away_team_pitp_off = 0
    away_team_pitp_off_rank = 0
    l5_away_team_pitp_off = 0
    l5_away_team_pitp_off_rank = 0
    home_team_pitp_off = 0
    home_team_pitp_off_rank = 0
    l5_home_team_pitp_off = 0
    l5_home_team_pitp_off_rank = 0
    away_team_pitp_def = 0
    away_team_pitp_def_rank = 0
    l5_away_team_pitp_def = 0
    l5_away_team_pitp_def_rank = 0
    home_team_pitp_def = 0
    home_team_pitp_def_rank = 0
    l5_home_team_pitp_def = 0
    l5_home_team_pitp_def_rank = 0
    away_team_2c_off = 0
    away_team_2c_off_rank = 0
    l5_away_team_2c_off = 0
    l5_away_team_2c_off_rank = 0
    home_team_2c_off = 0
    home_team_2c_off_rank = 0
    l5_home_team_2c_off = 0
    l5_home_team_2c_off_rank = 0
    away_team_2c_def = 0
    away_team_2c_def_rank = 0
    l5_away_team_2c_def = 0
    l5_away_team_2c_def_rank = 0
    home_team_2c_def = 0
    home_team_2c_def_rank = 0
    l5_home_team_2c_def = 0
    l5_home_team_2c_def_rank = 0
    away_team_fb_off = 0
    away_team_fb_off_rank = 0
    l5_away_team_fb_off = 0
    l5_away_team_fb_off_rank = 0
    home_team_fb_off = 0
    home_team_fb_off_rank = 0
    l5_home_team_fb_off = 0
    l5_home_team_fb_off_rank = 0
    away_team_fb_def = 0
    away_team_fb_def_rank = 0
    l5_away_team_fb_def = 0
    l5_away_team_fb_def_rank = 0
    home_team_fb_def = 0
    home_team_fb_def_rank = 0
    l5_home_team_fb_def = 0
    l5_home_team_fb_def_rank = 0
    away_team_pace = 0
    away_team_pace_rank = 0
    l5_away_team_pace = 0
    l5_away_team_pace_rank = 0
    away_team_ast = 0
    away_team_ast_rank = 0
    l5_away_team_ast = 0
    l5_away_team_ast_rank = 0
    away_team_ast_pct = 0
    away_team_ast_pct_rank = 0
    l5_away_team_ast_pct = 0
    l5_away_team_ast_pct_rank = 0
    away_team_tov = 0
    away_team_tov_rank = 0
    l5_away_team_tov = 0
    l5_away_team_tov_rank = 0
    away_team_tov_pct = 0
    away_team_tov_pct_rank = 0
    l5_away_team_tov_pct = 0
    l5_away_team_tov_pct_rank = 0
    away_team_pts_off_tov = 0
    away_team_pts_off_tov_rank = 0
    l5_away_team_pts_off_tov = 0
    l5_away_team_pts_off_tov_rank = 0
    home_team_opp_pts_off_tov = 0
    home_team_opp_pts_off_tov_rank = 0
    l5_home_team_opp_pts_off_tov = 0
    l5_home_team_opp_pts_off_tov_rank = 0
    away_team_ast_tov = 0
    away_team_ast_tov_rank = 0
    l5_away_team_ast_tov = 0
    l5_away_team_ast_tov_rank = 0
    away_team_starters_scoring = 0
    away_team_starters_scoring_rank = 0
    l5_away_team_starters_scoring = 0
    l5_away_team_starters_scoring_rank = 0
    away_team_bench_scoring = 0
    away_team_bench_scoring_rank = 0
    l5_away_team_bench_scoring = 0
    l5_away_team_bench_scoring_rank = 0
    away_team_opp_tov_pct = 0
    away_team_opp_tov_pct_rank = 0
    l5_away_team_opp_tov_pct = 0
    l5_away_team_opp_tov_pct_rank = 0

#POINTS IN THE PAINT
# Only calculate if we have valid team IDs
if away_id is not None and home_id is not None:
#OFFENSE
## Away Team
        away_team_pitp_off = safe_get_value(data_misc_season, away_id, 'PTS_PAINT', 0)
        away_team_pitp_off_rank = safe_get_value(data_misc_season, away_id, 'PTS_PAINT_RANK', 0)
        l5_away_team_pitp_off = safe_get_value(data_misc_L5, away_id, 'PTS_PAINT', 0)
        l5_away_team_pitp_off_rank = safe_get_value(data_misc_L5, away_id, 'PTS_PAINT_RANK', 0)
## League Average
        la_pitp_off = round(data_misc_season['PTS_PAINT'].mean(), 1)
        l5_la_pitp_off = round(data_misc_L5['PTS_PAINT'].mean(), 1)
## Home Team
        home_team_pitp_off = safe_get_value(data_misc_season, home_id, 'PTS_PAINT', 0)
        home_team_pitp_off_rank = safe_get_value(data_misc_season, home_id, 'PTS_PAINT_RANK', 0)
        l5_home_team_pitp_off = safe_get_value(data_misc_L5, home_id, 'PTS_PAINT', 0)
        l5_home_team_pitp_off_rank = safe_get_value(data_misc_L5, home_id, 'PTS_PAINT_RANK', 0)

#DEFENSE
## Away Team
        away_team_pitp_def = safe_get_value(data_misc_season, away_id, 'OPP_PTS_PAINT', 0)
        away_team_pitp_def_rank = safe_get_value(data_misc_season, away_id, 'OPP_PTS_PAINT_RANK', 0)
        l5_away_team_pitp_def = safe_get_value(data_misc_L5, away_id, 'OPP_PTS_PAINT', 0)
        l5_away_team_pitp_def_rank = safe_get_value(data_misc_L5, away_id, 'OPP_PTS_PAINT_RANK', 0)
## League Average
        la_pitp_def = round(data_misc_season['OPP_PTS_PAINT'].mean(), 1)
        l5_la_pitp_def = round(data_misc_L5['OPP_PTS_PAINT'].mean(), 1)
## Home Team
        home_team_pitp_def = safe_get_value(data_misc_season, home_id, 'OPP_PTS_PAINT', 0)
        home_team_pitp_def_rank = safe_get_value(data_misc_season, home_id, 'OPP_PTS_PAINT_RANK', 0)
        l5_home_team_pitp_def = safe_get_value(data_misc_L5, home_id, 'OPP_PTS_PAINT', 0)
        l5_home_team_pitp_def_rank = safe_get_value(data_misc_L5, home_id, 'OPP_PTS_PAINT_RANK', 0)

#DIFFERENCE
## Away Team
        away_team_pitp_diff = round(safe_get_value(data_misc_season, away_id, 'PTS_PAINT_DIFF', 0), 1)
        away_team_pitp_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_PAINT_DIFF_RANK'].values[0])
        l5_away_team_pitp_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_PAINT_DIFF'].values[0], 1)
        l5_away_team_pitp_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_PAINT_DIFF_RANK'].values[0])
## League Average
        la_pitp_diff = round(data_misc_season['PTS_PAINT_DIFF'].mean(), 1)
        l5_la_pitp_diff = round(data_misc_L5['PTS_PAINT_DIFF'].mean(), 1)
## Home Team
        home_team_pitp_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_PAINT_DIFF'].values[0], 1)
        home_team_pitp_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_PAINT_DIFF_RANK'].values[0])
        l5_home_team_pitp_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_PAINT_DIFF'].values[0], 1)
        l5_home_team_pitp_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_PAINT_DIFF_RANK'].values[0])
else:
    # Set default values when team IDs are not available
    away_team_pitp_off = 0
    away_team_pitp_off_rank = 0
    l5_away_team_pitp_off = 0
    l5_away_team_pitp_off_rank = 0
    home_team_pitp_off = 0
    home_team_pitp_off_rank = 0
    l5_home_team_pitp_off = 0
    l5_home_team_pitp_off_rank = 0
    away_team_pitp_def = 0
    away_team_pitp_def_rank = 0
    l5_away_team_pitp_def = 0
    l5_away_team_pitp_def_rank = 0
    home_team_pitp_def = 0
    home_team_pitp_def_rank = 0
    l5_home_team_pitp_def = 0
    l5_home_team_pitp_def_rank = 0
    away_team_pitp_diff = 0
    away_team_pitp_diff_rank = 0
    l5_away_team_pitp_diff = 0
    l5_away_team_pitp_diff_rank = 0
    home_team_pitp_diff = 0
    home_team_pitp_diff_rank = 0
    l5_home_team_pitp_diff = 0
    l5_home_team_pitp_diff_rank = 0
    la_pitp_off = 0
    l5_la_pitp_off = 0
    la_pitp_def = 0
    l5_la_pitp_def = 0
    la_pitp_diff = 0
    l5_la_pitp_diff = 0

#2ND CHANCE POINTS
# Only calculate if we have valid team IDs
if away_id is not None and home_id is not None:
#OFFENSE
## Away Team
    away_team_2c_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE'].values[0]
    away_team_2c_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_RANK'].values[0]
    l5_away_team_2c_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE'].values[0]
    l5_away_team_2c_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_RANK'].values[0]
##League Average
    la_2c_off = round(data_misc_season['PTS_2ND_CHANCE'].mean(), 1)
    l5_la_2c_off = round(data_misc_L5['PTS_2ND_CHANCE'].mean(), 1)
## Home Team
    home_team_2c_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE'].values[0]
    home_team_2c_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_RANK'].values[0]
    l5_home_team_2c_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE'].values[0]
    l5_home_team_2c_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_RANK'].values[0]

#DEFENSE
## Away Team
    away_team_2c_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_2ND_CHANCE'].values[0]
    away_team_2c_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
    l5_away_team_2c_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_2ND_CHANCE'].values[0]
    l5_away_team_2c_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
##League Average
    la_2c_def = round(data_misc_season['OPP_PTS_2ND_CHANCE'].mean(), 1)
    l5_la_2c_def = round(data_misc_L5['OPP_PTS_2ND_CHANCE'].mean(), 1)
## Home Team
    home_team_2c_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_2ND_CHANCE'].values[0]
    home_team_2c_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]
    l5_home_team_2c_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_2ND_CHANCE'].values[0]
    l5_home_team_2c_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_2ND_CHANCE_RANK'].values[0]

#DIFFERENCE
## Away Team
    away_team_2c_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
    away_team_2c_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
    l5_away_team_2c_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
    l5_away_team_2c_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
## League Average
    la_2c_diff = round(data_misc_season['PTS_2ND_CHANCE_DIFF'].mean(), 1)
    l5_la_2c_diff = round(data_misc_L5['PTS_2ND_CHANCE_DIFF'].mean(), 1)
## Home Team
    home_team_2c_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
    home_team_2c_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])
    l5_home_team_2c_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_DIFF'].values[0], 1)
    l5_home_team_2c_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_2ND_CHANCE_DIFF_RANK'].values[0])

    #FAST BREAK POINTS

    #OFFENSE
    ## Away Team
    away_team_fb_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_FB'].values[0]
    away_team_fb_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_FB_RANK'].values[0]
    l5_away_team_fb_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_FB'].values[0]
    l5_away_team_fb_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_FB_RANK'].values[0]
    ##League Average
    la_fb_off = round(data_misc_season['PTS_FB'].mean(), 1)
    l5_la_fb_off = round(data_misc_L5['PTS_FB'].mean(), 1)
    ## Home Team
    home_team_fb_off = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_FB'].values[0]
    home_team_fb_off_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_FB_RANK'].values[0]
    l5_home_team_fb_off = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_FB'].values[0]
    l5_home_team_fb_off_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_FB_RANK'].values[0]

    #DEFENSE
    ## Away Team
    away_team_fb_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_FB'].values[0]
    away_team_fb_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_FB_RANK'].values[0]
    l5_away_team_fb_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_FB'].values[0]
    l5_away_team_fb_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_FB_RANK'].values[0]
    ##League Average
    la_fb_def = round(data_misc_season['OPP_PTS_FB'].mean(), 1)
    l5_la_fb_def = round(data_misc_L5['OPP_PTS_FB'].mean(), 1)
    ## Home Team
    home_team_fb_def = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_FB'].values[0]
    home_team_fb_def_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_FB_RANK'].values[0]
    l5_home_team_fb_def = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_FB'].values[0]
    l5_home_team_fb_def_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_FB_RANK'].values[0]

    #DIFFERENCE
    ## Away Team
    away_team_fb_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_FB_DIFF'].values[0], 1)
    away_team_fb_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_FB_DIFF_RANK'].values[0])
    l5_away_team_fb_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_FB_DIFF'].values[0], 1)
    l5_away_team_fb_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_FB_DIFF_RANK'].values[0])
    ## League Average
    la_fb_diff = round(data_misc_season['PTS_FB_DIFF'].mean(), 1)
    l5_la_fb_diff = round(data_misc_L5['PTS_FB_DIFF'].mean(), 1)
    ## Home Team
    home_team_fb_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_FB_DIFF'].values[0], 1)
    home_team_fb_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_FB_DIFF_RANK'].values[0])
    l5_home_team_fb_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_FB_DIFF'].values[0], 1)
    l5_home_team_fb_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_FB_DIFF_RANK'].values[0])

    #PLAYMAKING STATS

    #PACE
    ## Away Team
    away_team_pace = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'PACE'].values[0]
    away_team_pace_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'PACE_RANK'].values[0]
    l5_away_team_pace = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'PACE'].values[0]
    l5_away_team_pace_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'PACE_RANK'].values[0]

    ## League Average
    la_pace = round(data_adv_season['PACE'].mean(), 1)
    l5_la_pace = round(data_adv_L5['PACE'].mean(), 1)

    ## Home Team
    home_team_pace = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'PACE'].values[0]
    home_team_pace_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'PACE_RANK'].values[0]
    l5_home_team_pace = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'PACE'].values[0]
    l5_home_team_pace_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'PACE_RANK'].values[0]

    #ASSISTS
    ## Away Team
    away_team_ast = data_trad_season.loc[data_trad_season['TEAM_ID'] == away_id, 'AST'].values[0]
    away_team_ast_rank = data_trad_season.loc[data_trad_season['TEAM_ID'] == away_id, 'AST_RANK'].values[0]
    l5_away_team_ast = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == away_id, 'AST'].values[0]
    l5_away_team_ast_rank = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == away_id, 'AST_RANK'].values[0]

    ## League Average
    la_ast = round(data_trad_season['AST'].mean(), 1)
    l5_la_ast = round(data_trad_L5['AST'].mean(), 1)

    ## Home Team
    home_team_ast = data_trad_season.loc[data_trad_season['TEAM_ID'] == home_id, 'AST'].values[0]
    home_team_ast_rank = data_trad_season.loc[data_trad_season['TEAM_ID'] == home_id, 'AST_RANK'].values[0]
    l5_home_team_ast = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == home_id, 'AST'].values[0]
    l5_home_team_ast_rank = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == home_id, 'AST_RANK'].values[0]

    #ASSIST PERCENTAGE
    ## Away Team
    away_team_ast_pct = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'AST_PCT'].values[0]
    away_team_ast_pct_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'AST_PCT_RANK'].values[0]
    l5_away_team_ast_pct = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'AST_PCT'].values[0]
    l5_away_team_ast_pct_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'AST_PCT_RANK'].values[0]

    ## League Average
    la_ast_pct = round(data_adv_season['AST_PCT'].mean(), 3)
    l5_la_ast_pct = round(data_adv_L5['AST_PCT'].mean(), 3)

    ## Home Team
    home_team_ast_pct = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'AST_PCT'].values[0]
    home_team_ast_pct_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'AST_PCT_RANK'].values[0]
    l5_home_team_ast_pct = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'AST_PCT'].values[0]
    l5_home_team_ast_pct_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'AST_PCT_RANK'].values[0]

    #TURNOVERS
    ## Away Team
    away_team_tov = data_trad_season.loc[data_trad_season['TEAM_ID'] == away_id, 'TOV'].values[0]
    away_team_tov_rank = data_trad_season.loc[data_trad_season['TEAM_ID'] == away_id, 'TOV_RANK'].values[0]
    l5_away_team_tov = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == away_id, 'TOV'].values[0]
    l5_away_team_tov_rank = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == away_id, 'TOV_RANK'].values[0]

    ## League Average
    la_tov = round(data_trad_season['TOV'].mean(), 1)
    l5_la_tov = round(data_trad_L5['TOV'].mean(), 1)

    ## Home Team
    home_team_tov = data_trad_season.loc[data_trad_season['TEAM_ID'] == home_id, 'TOV'].values[0]
    home_team_tov_rank = data_trad_season.loc[data_trad_season['TEAM_ID'] == home_id, 'TOV_RANK'].values[0]
    l5_home_team_tov = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == home_id, 'TOV'].values[0]
    l5_home_team_tov_rank = data_trad_L5.loc[data_trad_L5['TEAM_ID'] == home_id, 'TOV_RANK'].values[0]

    #TURNOVER PERCENTAGE
    ## Away Team
    away_team_tov_pct = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'TM_TOV_PCT'].values[0]
    away_team_tov_pct_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'TM_TOV_PCT_RANK'].values[0]
    l5_away_team_tov_pct = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'TM_TOV_PCT'].values[0]
    l5_away_team_tov_pct_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'TM_TOV_PCT_RANK'].values[0]

    ## League Average
    la_tov_pct = round(data_adv_season['TM_TOV_PCT'].mean(), 3)
    # print(la_tov_pct)
    l5_la_tov_pct = round(data_adv_L5['TM_TOV_PCT'].mean(), 3)

    ## Home Team
    home_team_tov_pct = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'TM_TOV_PCT'].values[0]
    home_team_tov_pct_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'TM_TOV_PCT_RANK'].values[0]
    l5_home_team_tov_pct = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'TM_TOV_PCT'].values[0]
    l5_home_team_tov_pct_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'TM_TOV_PCT_RANK'].values[0]

    #OPP. TURNOVER PERCENTAGE
    ## Away Team
    away_team_opp_tov_pct = data_4F_season.loc[data_4F_season['TEAM_ID'] == away_id, 'OPP_TOV_PCT'].values[0]
    away_team_opp_tov_pct_rank = data_4F_season.loc[data_4F_season['TEAM_ID'] == away_id, 'OPP_TOV_PCT_RANK'].values[0]
    l5_away_team_opp_tov_pct = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == away_id, 'OPP_TOV_PCT'].values[0]
    l5_away_team_opp_tov_pct_rank = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == away_id, 'OPP_TOV_PCT_RANK'].values[0]

    ## League Average
    la_opp_tov_pct = round(data_4F_season['OPP_TOV_PCT'].mean(), 3)
    l5_la_opp_tov_pct = round(data_4F_L5['OPP_TOV_PCT'].mean(), 3)

    ## Home Team
    home_team_opp_tov_pct = data_4F_season.loc[data_4F_season['TEAM_ID'] == home_id, 'OPP_TOV_PCT'].values[0]
    home_team_opp_tov_pct_rank = data_4F_season.loc[data_4F_season['TEAM_ID'] == home_id, 'OPP_TOV_PCT_RANK'].values[0]
    l5_home_team_opp_tov_pct = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == home_id, 'OPP_TOV_PCT'].values[0]
    l5_home_team_opp_tov_pct_rank = data_4F_L5.loc[data_4F_L5['TEAM_ID'] == home_id, 'OPP_TOV_PCT_RANK'].values[0]

    #AST/TOV RATIO
    ## Away Team
    away_team_ast_tov = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'AST_TO'].values[0]
    away_team_ast_tov_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == away_id, 'AST_TO_RANK'].values[0]
    l5_away_team_ast_tov = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'AST_TO'].values[0]
    l5_away_team_ast_tov_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == away_id, 'AST_TO_RANK'].values[0]

    ## League Average
    la_ast_tov = round(data_adv_season['AST_TO'].mean(), 2)
    l5_la_ast_tov = round(data_adv_L5['AST_TO'].mean(), 2)

    ## Home Team
    home_team_ast_tov = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'AST_TO'].values[0]
    home_team_ast_tov_rank = data_adv_season.loc[data_adv_season['TEAM_ID'] == home_id, 'AST_TO_RANK'].values[0]
    l5_home_team_ast_tov = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'AST_TO'].values[0]
    l5_home_team_ast_tov_rank = data_adv_L5.loc[data_adv_L5['TEAM_ID'] == home_id, 'AST_TO_RANK'].values[0]

    #POINTS OFF TURNOVERS

    #OFFENSE
    ## Away Team
    away_team_pts_off_tov = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_OFF_TOV'].values[0]
    away_team_pts_off_tov_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_OFF_TOV_RANK'].values[0]
    l5_away_team_pts_off_tov = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_OFF_TOV'].values[0]
    l5_away_team_pts_off_tov_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_OFF_TOV_RANK'].values[0]
    ##League Average
    la_pts_off_tov = round(data_misc_season['PTS_OFF_TOV'].mean(), 1)
    l5_la_pts_off_tov = round(data_misc_L5['PTS_OFF_TOV'].mean(), 1)
    ## Home Team
    home_team_pts_off_tov = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_OFF_TOV'].values[0]
    home_team_pts_off_tov_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_OFF_TOV_RANK'].values[0]
    l5_home_team_pts_off_tov = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_OFF_TOV'].values[0]
    l5_home_team_pts_off_tov_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_OFF_TOV_RANK'].values[0]

    #DEFENSE
    ## Away Team
    away_team_opp_pts_off_tov = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_OFF_TOV'].values[0]
    away_team_opp_pts_off_tov_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    l5_away_team_opp_pts_off_tov = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_OFF_TOV'].values[0]
    l5_away_team_opp_pts_off_tov_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    ##League Average
    la_opp_pts_off_tov = round(data_misc_season['OPP_PTS_OFF_TOV'].mean(), 1)
    l5_la_opp_pts_off_tov = round(data_misc_L5['OPP_PTS_OFF_TOV'].mean(), 1)
    ## Home Team
    home_team_opp_pts_off_tov = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_OFF_TOV'].values[0]
    home_team_opp_pts_off_tov_rank = data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]
    l5_home_team_opp_pts_off_tov = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_OFF_TOV'].values[0]
    l5_home_team_opp_pts_off_tov_rank = data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'OPP_PTS_OFF_TOV_RANK'].values[0]

    #DIFFERENCE
    ## Away Team
    away_team_pts_off_tov_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    away_team_pts_off_tov_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == away_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    l5_away_team_pts_off_tov_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    l5_away_team_pts_off_tov_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == away_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    ## League Average
    la_pts_off_tov_diff = round(data_misc_season['PTS_OFF_TOV_DIFF'].mean(), 1)
    l5_la_pts_off_tov_diff = round(data_misc_L5['PTS_OFF_TOV_DIFF'].mean(), 1)
    ## Home Team
    home_team_pts_off_tov_diff = round(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    home_team_pts_off_tov_diff_rank = int(data_misc_season.loc[data_misc_season['TEAM_ID'] == home_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])
    l5_home_team_pts_off_tov_diff = round(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_OFF_TOV_DIFF'].values[0], 1)
    l5_home_team_pts_off_tov_diff_rank = int(data_misc_L5.loc[data_misc_L5['TEAM_ID'] == home_id, 'PTS_OFF_TOV_DIFF_RANK'].values[0])

    #STARTERS AND BENCH SCORING

    ## STARTERS
    ### Away Team
    away_team_starters_scoring = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == away_id, 'PTS'].values[0]
    away_team_starters_scoring_rank = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == away_id, 'PTS_RANK'].values[0]
    l5_away_team_starters_scoring = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == away_id, 'PTS'].values[0]
    l5_away_team_starters_scoring_rank = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == away_id, 'PTS_RANK'].values[0]

    ### League Average
    la_starters_scoring = round(data_trad_season_starters['PTS'].mean(), 1)
    l5_la_starters_scoring = round(data_trad_L5_starters['PTS'].mean(), 1)

    ### Home Team
    home_team_starters_scoring = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == home_id, 'PTS'].values[0]
    home_team_starters_scoring_rank = data_trad_season_starters.loc[data_trad_season_starters['TEAM_ID'] == home_id, 'PTS_RANK'].values[0]
    l5_home_team_starters_scoring = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == home_id, 'PTS'].values[0]
    l5_home_team_starters_scoring_rank = data_trad_L5_starters.loc[data_trad_L5_starters['TEAM_ID'] == home_id, 'PTS_RANK'].values[0]

    ## BENCH
    ### Away Team
    away_team_bench_scoring = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == away_id, 'PTS'].values[0]
    away_team_bench_scoring_rank = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == away_id, 'PTS_RANK'].values[0]
    l5_away_team_bench_scoring = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == away_id, 'PTS'].values[0]
    l5_away_team_bench_scoring_rank = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == away_id, 'PTS_RANK'].values[0]

    ### League Average
    la_bench_scoring = round(data_trad_season_bench['PTS'].mean(), 1)
    l5_la_bench_scoring = round(data_trad_L5_bench['PTS'].mean(), 1)

    ### Home Team
    home_team_bench_scoring = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == home_id, 'PTS'].values[0]
    home_team_bench_scoring_rank = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == home_id, 'PTS_RANK'].values[0]
    l5_home_team_bench_scoring = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == home_id, 'PTS'].values[0]
    l5_home_team_bench_scoring_rank = data_trad_L5_bench.loc[data_trad_L5_bench['TEAM_ID'] == home_id, 'PTS_RANK'].values[0]
else:
    # Default values are already set at module level (lines 851-926)
    # No need to set them again here
    pass

@st.cache_data(ttl=21600, show_spinner=False)
def get_cached_pbpstats_totals(data_type: str = "Team", season: str = current_season):
    """Get pbpstats totals data"""
    # Fetch from API
    try:
        url = "https://api.pbpstats.com/get-totals/nba"
        params = {
            "Season": season,
            "SeasonType": season_type,
            "Type": data_type
        }
        response = requests.get(url, params=params, timeout=30)
        response_json = response.json()
        
        league_stats_dict = response_json.get("single_row_table_data", {})
        team_stats_dict = response_json.get("multi_row_table_data", [])
        team_stats_df = pd.DataFrame(team_stats_dict)
        
        return {
            "league_stats": league_stats_dict,
            "team_stats": team_stats_df
        }
    except Exception as e:
        print(f"Error fetching pbpstats data: {e}")
        return {"league_stats": {}, "team_stats": pd.DataFrame()}

# Load pbpstats data using cached functions
pbp_totals_data = get_cached_pbpstats_totals("Team")
league_stats_dict = pbp_totals_data.get("league_stats", {})
team_stats_dict = pbp_totals_data.get("team_stats", pd.DataFrame())

pbp_opp_totals_data = get_cached_pbpstats_totals("Opponent")
opp_league_stats_dict = pbp_opp_totals_data.get("league_stats", {})
opp_team_stats_dict = pbp_opp_totals_data.get("team_stats", pd.DataFrame())

team_stats = pd.DataFrame(team_stats_dict) if isinstance(team_stats_dict, pd.DataFrame) else pd.DataFrame()
opp_team_stats = pd.DataFrame(opp_team_stats_dict)


# PRE-WORK FOR SHOOTING STATS -- TEAM
## MAKE TEAM ID A NUMBER
## ALL RANKS SHOULD BE ASCENDING=FALSE
team_stats['TeamId'] = team_stats['TeamId'].astype(int)
## FG%
team_stats['FGM'] = team_stats['FG2M'] + team_stats['FG3M']
team_stats['FGA'] = team_stats['FG2A'] + team_stats['FG3A']
team_stats['FGM_PG'] = round((team_stats['FG2M'] + team_stats['FG3M'])/team_stats['GamesPlayed'], 1)
team_stats['FGM_RANK'] = team_stats['FGM_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FGA_PG'] = round((team_stats['FG2A'] + team_stats['FG3A'])/team_stats['GamesPlayed'], 1)
team_stats['FGA_RANK'] = team_stats['FGA_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FG%'] = round(team_stats['FGM']/team_stats['FGA'], 3)
team_stats['FG%_RANK'] = team_stats['FG%'].rank(ascending=False, method='first').astype(int)

## 2PT%
team_stats['FG2M_PG'] = round(team_stats['FG2M']/team_stats['GamesPlayed'], 1)
team_stats['FG2M_RANK'] = team_stats['FG2M_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FG2A_PG'] = round(team_stats['FG2A']/team_stats['GamesPlayed'], 1)
team_stats['FG2A_RANK'] = team_stats['FG2A_PG'].rank(ascending=False, method='first').astype(int)
team_stats['2PT%'] = round(team_stats['FG2M']/team_stats['FG2A'], 3)
team_stats['2PT%_RANK'] = team_stats['Fg2Pct'].rank(ascending=False, method='first').astype(int)
team_stats['2PT_RATE'] = round(team_stats['FG2A']/team_stats['FGA'], 3)
team_stats['2PT_RATE_RANK'] = team_stats['2PT_RATE'].rank(ascending=False, method='first').astype(int)

## 3PT%
team_stats['FG3M_PG'] = round(team_stats['FG3M']/team_stats['GamesPlayed'], 1)
team_stats['FG3M_RANK'] = team_stats['FG3M_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FG3A_PG'] = round(team_stats['FG3A']/team_stats['GamesPlayed'], 1)
team_stats['FG3A_RANK'] = team_stats['FG3A_PG'].rank(ascending=False, method='first').astype(int)
team_stats['3PT%'] = round(team_stats['FG3M']/team_stats['FG3A'], 3)
team_stats['3PT%_RANK'] = team_stats['Fg3Pct'].rank(ascending=False, method='first').astype(int)
team_stats['3PT_RATE'] = round(team_stats['FG3A']/team_stats['FGA'], 3)
team_stats['3PT_RATE_RANK'] = team_stats['3PT_RATE'].rank(ascending=False, method='first').astype(int)

## FT%
team_stats['FTM'] = team_stats['FtPoints']
team_stats['FTM_PG'] = round(team_stats['FTM']/team_stats['GamesPlayed'], 1)
team_stats['FTM_RANK'] = team_stats['FTM_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FTA_PG'] = round(team_stats['FTA']/team_stats['GamesPlayed'], 1)
team_stats['FTA_RANK'] = team_stats['FTA_PG'].rank(ascending=False, method='first').astype(int)
team_stats['FT%'] = round(team_stats['FTM']/team_stats['FTA'], 3)
team_stats['FT%_RANK'] = team_stats['FT%'].rank(ascending=False, method='first').astype(int)
team_stats['FT_RATE'] = round(team_stats['FTA']/team_stats['FGA'], 3)
team_stats['FT_RATE_RANK'] = team_stats['FT_RATE'].rank(ascending=False, method='first').astype(int)

## RIM
team_stats['RIM_FREQ_RANK'] = team_stats['AtRimFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['RIM_FG%_RANK'] = team_stats['AtRimAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)

## SMR
team_stats['SMR_FREQ_RANK'] = team_stats['ShortMidRangeFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['SMR_FG%_RANK'] = team_stats['ShortMidRangeAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)

## LMR
team_stats['LMR_FREQ_RANK'] = team_stats['LongMidRangeFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['LMR_FG%_RANK'] = team_stats['LongMidRangeAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)

## C3
team_stats['C3_FREQ_RANK'] = team_stats['Corner3Frequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['C3_FG%_RANK'] = team_stats['Corner3Accuracy'].fillna(0).rank(ascending=False, method='first').astype(int)

## ATB3
team_stats['ATB3_FREQ_RANK'] = team_stats['Arc3Frequency'].fillna(0).rank(ascending=False, method='first').astype(int)
team_stats['ATB3_FG%_RANK'] = team_stats['Arc3Accuracy'].fillna(0).rank(ascending=False, method='first').astype(int)


# PRE-WORK FOR SHOOTING STATS -- OPPONENT
## MAKE TEAM ID A NUMBER
## ALL RANKS SHOULD BE ASCENDING=TRUE
opp_team_stats['TeamId'] = opp_team_stats['TeamId'].astype(int)
## FG%
opp_team_stats['FGM'] = opp_team_stats['FG2M'] + opp_team_stats['FG3M']
opp_team_stats['FGA'] = opp_team_stats['FG2A'] + opp_team_stats['FG3A']
opp_team_stats['FGM_PG'] = round((opp_team_stats['FG2M'] + opp_team_stats['FG3M'])/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FGM_RANK'] = opp_team_stats['FGM_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FGA_PG'] = round((opp_team_stats['FG2A'] + opp_team_stats['FG3A'])/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FGA_RANK'] = opp_team_stats['FGA_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FG%'] = round(opp_team_stats['FGM']/opp_team_stats['FGA'], 3)
opp_team_stats['FG%_RANK'] = opp_team_stats['FG%'].rank(ascending=True, method='first').astype(int)

## 2PT%
opp_team_stats['FG2M_PG'] = round(opp_team_stats['FG2M']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FG2M_RANK'] = opp_team_stats['FG2M_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FG2A_PG'] = round(opp_team_stats['FG2A']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FG2A_RANK'] = opp_team_stats['FG2A_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['2PT%'] = round(opp_team_stats['FG2M']/opp_team_stats['FG2A'], 3)
opp_team_stats['2PT%_RANK'] = opp_team_stats['Fg2Pct'].rank(ascending=True, method='first').astype(int)
opp_team_stats['2PT_RATE'] = round(opp_team_stats['FG2A']/opp_team_stats['FGA'], 3)
opp_team_stats['2PT_RATE_RANK'] = opp_team_stats['2PT_RATE'].rank(ascending=True, method='first').astype(int)

## 3PT%
opp_team_stats['FG3M_PG'] = round(opp_team_stats['FG3M']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FG3M_RANK'] = opp_team_stats['FG3M_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FG3A_PG'] = round(opp_team_stats['FG3A']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FG3A_RANK'] = opp_team_stats['FG3A_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['3PT%'] = round(opp_team_stats['FG3M']/opp_team_stats['FG3A'], 3)
opp_team_stats['3PT%_RANK'] = opp_team_stats['Fg3Pct'].rank(ascending=True, method='first').astype(int)
opp_team_stats['3PT_RATE'] = round(opp_team_stats['FG3A']/opp_team_stats['FGA'], 3)
opp_team_stats['3PT_RATE_RANK'] = opp_team_stats['3PT_RATE'].rank(ascending=True, method='first').astype(int)

## FT%
opp_team_stats['FTM'] = opp_team_stats['FtPoints']
opp_team_stats['FTM_PG'] = round(opp_team_stats['FTM']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FTM_RANK'] = opp_team_stats['FTM_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FTA_PG'] = round(opp_team_stats['FTA']/opp_team_stats['GamesPlayed'], 1)
opp_team_stats['FTA_RANK'] = opp_team_stats['FTA_PG'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FT%'] = round(opp_team_stats['FTM']/opp_team_stats['FTA'], 3)
opp_team_stats['FT%_RANK'] = opp_team_stats['FT%'].rank(ascending=True, method='first').astype(int)
opp_team_stats['FT_RATE'] = round(opp_team_stats['FTA']/opp_team_stats['FGA'], 3)
opp_team_stats['FT_RATE_RANK'] = opp_team_stats['FT_RATE'].rank(ascending=True, method='first').astype(int)

## RIM
opp_team_stats['RIM_FREQ_RANK'] = opp_team_stats['AtRimFrequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['RIM_FG%_RANK'] = opp_team_stats['AtRimAccuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

## SMR
opp_team_stats['SMR_FREQ_RANK'] = opp_team_stats['ShortMidRangeFrequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['SMR_FG%_RANK'] = opp_team_stats['ShortMidRangeAccuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

## LMR
opp_team_stats['LMR_FREQ_RANK'] = opp_team_stats['LongMidRangeFrequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['LMR_FG%_RANK'] = opp_team_stats['LongMidRangeAccuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

## C3
opp_team_stats['C3_FREQ_RANK'] = opp_team_stats['Corner3Frequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['C3_FG%_RANK'] = opp_team_stats['Corner3Accuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

## ATB3
opp_team_stats['ATB3_FREQ_RANK'] = opp_team_stats['Arc3Frequency'].fillna(0).rank(ascending=True, method='first').astype(int)
opp_team_stats['ATB3_FG%_RANK'] = opp_team_stats['Arc3Accuracy'].fillna(0).rank(ascending=True, method='first').astype(int)

# PRE-WORK FOR SHOOTING STATS -- DIFFERENTIAL
## MAKE TEAM ID A NUMBER
## ALL RANKS SHOULD BE ASCENDING=TRUE

#Get a list of all team abbreviations
pbp_team_list = team_stats.sort_values('Name', ascending=True)['Name'].tolist()

shooting_columns_to_extract = ['TeamId', 'Name',
                               'FGM_PG', 'FGA_PG', 'FG%',
                               'FG2M_PG', 'FG2A_PG', '2PT%',
                               'FG3M_PG', 'FG3A_PG', '3PT%',
                               'FTM_PG', 'FTA_PG', 'FT%',
                               'AtRimFrequency', 'AtRimAccuracy',
                               'ShortMidRangeFrequency', 'ShortMidRangeAccuracy',
                               'LongMidRangeFrequency', 'LongMidRangeAccuracy',
                               'Corner3Frequency', 'Corner3Accuracy',
                               'Arc3Frequency', 'Arc3Accuracy'
                               ]

# Ensure data is reset and aligned
team_stats_diff = team_stats[shooting_columns_to_extract].reset_index(drop=True)
opp_team_stats_diff = opp_team_stats[shooting_columns_to_extract].reset_index(drop=True)

team_stats_col_num = team_stats_diff.shape[1]
shooting_team_stats_diff = pd.DataFrame()

def create_shooting_diff(team):
    func_df = pd.DataFrame()  # Initialize once per function call

    if team not in team_stats_diff['Name'].values:  # Prevent KeyError
        print(f"Warning: {team} not found in team_stats_diff")
        return pd.DataFrame()  # Return empty DF if team is missing

    for col_counter in range(team_stats_col_num):
        column_name = shooting_columns_to_extract[col_counter]

        # Ensure the column exists
        if column_name not in team_stats_diff.columns or column_name not in opp_team_stats_diff.columns:
            print(f"Warning: {column_name} not found in columns")
            continue  # Skip missing columns

        # Get team and opponent stats safely
        team_stat_values = team_stats_diff.loc[team_stats_diff['Name'] == team, column_name].values
        opp_stat_values = opp_team_stats_diff.loc[opp_team_stats_diff['Name'] == team, column_name].values

        if len(team_stat_values) == 0 or len(opp_stat_values) == 0:
            print(f"Warning: Missing data for team {team} in column {column_name}")
            continue  # Skip if data is missing

        team_stat = team_stat_values[0]
        opp_stat = opp_stat_values[0]

        # Compute final stat difference
        if col_counter > 1:
            final_stat = team_stat - opp_stat
            func_df[column_name] = [final_stat]  # Store as list for DataFrame consistency
        else:
            func_df[column_name] = [team_stat]  # Store team_stat as list

    return func_df  # Return full row, not an empty DataFrame

# Apply function across teams
shooting_diff_results = pd.concat([create_shooting_diff(team) for team in pbp_team_list], ignore_index=True)

#SHOOTING DIFFERENTIAL RANKS
shooting_diff_results['FGM_RANK'] = shooting_diff_results['FGA_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FGA_RANK'] = shooting_diff_results['FGA_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG%_RANK'] = shooting_diff_results['FG%'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG2M_RANK'] = shooting_diff_results['FG2M_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG2A_RANK'] = shooting_diff_results['FG2A_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['2PT%_RANK'] = shooting_diff_results['2PT%'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG3M_RANK'] = shooting_diff_results['FG3M_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FG3A_RANK'] = shooting_diff_results['FG3A_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['3PT%_RANK'] = shooting_diff_results['3PT%'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FTM_RANK'] = shooting_diff_results['FTM_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FTA_RANK'] = shooting_diff_results['FTA_PG'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['FT%_RANK'] = shooting_diff_results['FT%'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['RIM_FREQ_RANK'] = shooting_diff_results['AtRimFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['RIM_FG%_RANK'] = shooting_diff_results['AtRimAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['SMR_FREQ_RANK'] = shooting_diff_results['ShortMidRangeFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['SMR_FG%_RANK'] = shooting_diff_results['ShortMidRangeAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['LMR_FREQ_RANK'] = shooting_diff_results['LongMidRangeFrequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['LMR_FG%_RANK'] = shooting_diff_results['LongMidRangeAccuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['C3_FREQ_RANK'] = shooting_diff_results['Corner3Frequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['C3_FG%_RANK'] = shooting_diff_results['Corner3Accuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['ATB3_FREQ_RANK'] = shooting_diff_results['Arc3Frequency'].fillna(0).rank(ascending=False, method='first').astype(int)
shooting_diff_results['ATB3_FG%_RANK'] = shooting_diff_results['Arc3Accuracy'].fillna(0).rank(ascending=False, method='first').astype(int)
## HOME TEAM SHOOTING STATS

# Overall Field Goals
# home_team_bench_scoring = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == home_id, 'PTS'].values[0]
## FGM
home_team_fgm = team_stats.loc[team_stats['TeamId'] == home_id, 'FGM_PG'].values[0]
home_team_fgm_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FGM_RANK'].values[0]
home_team_opp_fgm = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FGM_PG'].values[0]
home_team_opp_fgm_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FGM_RANK'].values[0]
home_team_diff_fgm = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FGM_PG'].values[0], 1)
home_team_diff_fgm_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FGM_RANK'].values[0]
## FGA
home_team_fga = team_stats.loc[team_stats['TeamId'] == home_id, 'FGA_PG'].values[0]
home_team_fga_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FGA_RANK'].values[0]
home_team_opp_fga = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FGA_PG'].values[0]
home_team_opp_fga_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FGA_RANK'].values[0]
home_team_diff_fga = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FGA_PG'].values[0], 1)
home_team_diff_fga_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FGA_RANK'].values[0]
## FG%
home_team_fg_pct = team_stats.loc[team_stats['TeamId'] == home_id, 'FG%'].values[0]
home_team_fg_pct_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG%_RANK'].values[0]
home_team_opp_fg_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG%'].values[0]
home_team_opp_fg_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG%_RANK'].values[0]
home_team_diff_fg_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG%'].values[0]
home_team_diff_fg_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG%_RANK'].values[0]
# Overall 2-Point Shooting
## 2PT
home_team_2pt = team_stats.loc[team_stats['TeamId'] == home_id, 'FG2M_PG'].values[0]
home_team_2pt_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG2M_RANK'].values[0]
home_team_opp_2pt = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG2M_PG'].values[0]
home_team_opp_2pt_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG2M_RANK'].values[0]
home_team_diff_2pt = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG2M_PG'].values[0], 1)
home_team_diff_2pt_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG2M_RANK'].values[0]
## 2PA
home_team_2pa = team_stats.loc[team_stats['TeamId'] == home_id, 'FG2A_PG'].values[0]
home_team_2pa_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG2A_RANK'].values[0]
home_team_opp_2pa = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG2A_PG'].values[0]
home_team_opp_2pa_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG2A_RANK'].values[0]
home_team_diff_2pa = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG2A_PG'].values[0], 1)
home_team_diff_2pa_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG2A_RANK'].values[0]
## 2PT%
home_team_2pt_pct = team_stats.loc[team_stats['TeamId'] == home_id, '2PT%'].values[0]
home_team_2pt_pct_rank = team_stats.loc[team_stats['TeamId'] == home_id, '2PT%_RANK'].values[0]
home_team_opp_2pt_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, '2PT%'].values[0]
home_team_opp_2pt_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, '2PT%_RANK'].values[0]
home_team_diff_2pt_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, '2PT%'].values[0]
home_team_diff_2pt_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, '2PT%_RANK'].values[0]
# Overall 3-Point Shooting
## 3PT
home_team_3pt = team_stats.loc[team_stats['TeamId'] == home_id, 'FG3M_PG'].values[0]
home_team_3pt_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG3M_RANK'].values[0]
home_team_opp_3pt = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG3M_PG'].values[0]
home_team_opp_3pt_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG3M_RANK'].values[0]
home_team_diff_3pt = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG3M_PG'].values[0], 1)
home_team_diff_3pt_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG3M_RANK'].values[0]
## 3PA
home_team_3pa = team_stats.loc[team_stats['TeamId'] == home_id, 'FG3A_PG'].values[0]
home_team_3pa_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FG3A_RANK'].values[0]
home_team_opp_3pa = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG3A_PG'].values[0]
home_team_opp_3pa_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FG3A_RANK'].values[0]
home_team_diff_3pa = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG3A_PG'].values[0], 1)
home_team_diff_3pa_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FG3A_RANK'].values[0]
## 3PT%
home_team_3pt_pct = team_stats.loc[team_stats['TeamId'] == home_id, '3PT%'].values[0]
home_team_3pt_pct_rank = team_stats.loc[team_stats['TeamId'] == home_id, '3PT%_RANK'].values[0]
home_team_opp_3pt_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, '3PT%'].values[0]
home_team_opp_3pt_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, '3PT%_RANK'].values[0]
home_team_diff_3pt_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, '3PT%'].values[0]
home_team_diff_3pt_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, '3PT%_RANK'].values[0]
# Overall Free Throw Shooting
## FTM
home_team_ftm = team_stats.loc[team_stats['TeamId'] == home_id, 'FTM_PG'].values[0]
home_team_ftm_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FTM_RANK'].values[0]
home_team_opp_ftm = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FTM_PG'].values[0]
home_team_opp_ftm_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FTM_RANK'].values[0]
home_team_diff_ftm = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FTM_PG'].values[0], 1)
home_team_diff_ftm_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FTM_RANK'].values[0]
## FTA
home_team_fta = team_stats.loc[team_stats['TeamId'] == home_id, 'FTA_PG'].values[0]
home_team_fta_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FTA_RANK'].values[0]
home_team_opp_fta = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FTA_PG'].values[0]
home_team_opp_fta_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FTA_RANK'].values[0]
home_team_diff_fta = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FTA_PG'].values[0], 1)
home_team_diff_fta_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FTA_RANK'].values[0]
## FT%
home_team_ft_pct = team_stats.loc[team_stats['TeamId'] == home_id, 'FT%'].values[0]
home_team_ft_pct_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'FT%_RANK'].values[0]
home_team_opp_ft_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FT%'].values[0]
home_team_opp_ft_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'FT%_RANK'].values[0]
home_team_diff_ft_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FT%'].values[0]
home_team_diff_ft_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'FT%_RANK'].values[0]
# RIM
## Rim Frequency
home_team_rim_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'AtRimFrequency'].values[0]
home_team_rim_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'RIM_FREQ_RANK'].values[0]
home_team_opp_rim_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'AtRimFrequency'].values[0]
home_team_opp_rim_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'RIM_FREQ_RANK'].values[0]
home_team_diff_rim_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'AtRimFrequency'].values[0]
home_team_diff_rim_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'RIM_FREQ_RANK'].values[0]
## Rim Accuracy
home_team_rim_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'AtRimAccuracy'].values[0]
home_team_rim_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'RIM_FG%_RANK'].values[0]
home_team_opp_rim_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'AtRimAccuracy'].values[0]
home_team_opp_rim_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'RIM_FG%_RANK'].values[0]
home_team_diff_rim_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'AtRimAccuracy'].values[0]
home_team_diff_rim_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'RIM_FG%_RANK'].values[0]

# Short Mid-Range Shooting
## SMR Frequency
home_team_smr_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'ShortMidRangeFrequency'].values[0]
home_team_smr_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'SMR_FREQ_RANK'].values[0]
home_team_opp_smr_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'ShortMidRangeFrequency'].values[0]
home_team_opp_smr_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'SMR_FREQ_RANK'].values[0]
home_team_diff_smr_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'ShortMidRangeFrequency'].values[0]
home_team_diff_smr_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'SMR_FREQ_RANK'].values[0]
## SMR Accuracy
home_team_smr_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'ShortMidRangeAccuracy'].values[0]
home_team_smr_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'SMR_FG%_RANK'].values[0]
home_team_opp_smr_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'ShortMidRangeAccuracy'].values[0]
home_team_opp_smr_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'SMR_FG%_RANK'].values[0]
home_team_diff_smr_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'ShortMidRangeAccuracy'].values[0]
home_team_diff_smr_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'SMR_FG%_RANK'].values[0]

# Long Mid-Range Shooting
## LMR Frequency
home_team_lmr_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'LongMidRangeFrequency'].values[0]
home_team_lmr_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'LMR_FREQ_RANK'].values[0]
home_team_opp_lmr_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'LongMidRangeFrequency'].values[0]
home_team_opp_lmr_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'LMR_FREQ_RANK'].values[0]
home_team_diff_lmr_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'LongMidRangeFrequency'].values[0]
home_team_diff_lmr_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'LMR_FREQ_RANK'].values[0]
## LMR Accuracy
home_team_lmr_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'LongMidRangeAccuracy'].values[0]
home_team_lmr_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'LMR_FG%_RANK'].values[0]
home_team_opp_lmr_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'LongMidRangeAccuracy'].values[0]
home_team_opp_lmr_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'LMR_FG%_RANK'].values[0]
home_team_diff_lmr_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'LongMidRangeAccuracy'].values[0]
home_team_diff_lmr_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'LMR_FG%_RANK'].values[0]
# Corner 3-Point Shooting
## C3 Frequency
home_team_c3_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'Corner3Frequency'].values[0]
home_team_c3_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'C3_FREQ_RANK'].values[0]
home_team_opp_c3_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'Corner3Frequency'].values[0]
home_team_opp_c3_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'C3_FREQ_RANK'].values[0]
home_team_diff_c3_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'Corner3Frequency'].values[0]
home_team_diff_c3_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'C3_FREQ_RANK'].values[0]
## C3 Accuracy
home_team_c3_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'Corner3Accuracy'].values[0]
home_team_c3_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'C3_FG%_RANK'].values[0]
home_team_opp_c3_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'Corner3Accuracy'].values[0]
home_team_opp_c3_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'C3_FG%_RANK'].values[0]
home_team_diff_c3_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'Corner3Accuracy'].values[0]
home_team_diff_c3_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'C3_FG%_RANK'].values[0]
# Above the Break 3-Point Shooting
## ATB3 Frequency
home_team_atb3_freq = team_stats.loc[team_stats['TeamId'] == home_id, 'Arc3Frequency'].values[0]
home_team_atb3_freq_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'ATB3_FREQ_RANK'].values[0]
home_team_opp_atb3_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'Arc3Frequency'].values[0]
home_team_opp_atb3_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'ATB3_FREQ_RANK'].values[0]
home_team_diff_atb3_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'Arc3Frequency'].values[0]
home_team_diff_atb3_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'ATB3_FREQ_RANK'].values[0]
## ATB3 Accuracy
home_team_atb3_acc = team_stats.loc[team_stats['TeamId'] == home_id, 'Arc3Accuracy'].values[0]
home_team_atb3_acc_rank = team_stats.loc[team_stats['TeamId'] == home_id, 'ATB3_FG%_RANK'].values[0]
home_team_opp_atb3_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'Arc3Accuracy'].values[0]
home_team_opp_atb3_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == home_id, 'ATB3_FG%_RANK'].values[0]
home_team_diff_atb3_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'Arc3Accuracy'].values[0]
home_team_diff_atb3_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == home_id, 'ATB3_FG%_RANK'].values[0]

## AWAY TEAM SHOOTING STATS

# Overall Field Goals
# away_team_bench_scoring = data_trad_season_bench.loc[data_trad_season_bench['TEAM_ID'] == away_id, 'PTS'].values[0]
## FGM
away_team_fgm = team_stats.loc[team_stats['TeamId'] == away_id, 'FGM_PG'].values[0]
away_team_fgm_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FGM_RANK'].values[0]
away_team_opp_fgm = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FGM_PG'].values[0]
away_team_opp_fgm_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FGM_RANK'].values[0]
away_team_diff_fgm = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FGM_PG'].values[0], 1)
away_team_diff_fgm_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FGM_RANK'].values[0]
## FGA
away_team_fga = team_stats.loc[team_stats['TeamId'] == away_id, 'FGA_PG'].values[0]
away_team_fga_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FGA_RANK'].values[0]
away_team_opp_fga = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FGA_PG'].values[0]
away_team_opp_fga_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FGA_RANK'].values[0]
away_team_diff_fga = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FGA_PG'].values[0], 1)
away_team_diff_fga_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FGA_RANK'].values[0]
## FG%
away_team_fg_pct = team_stats.loc[team_stats['TeamId'] == away_id, 'FG%'].values[0]
away_team_fg_pct_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG%_RANK'].values[0]
away_team_opp_fg_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG%'].values[0]
away_team_opp_fg_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG%_RANK'].values[0]
away_team_diff_fg_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG%'].values[0]
away_team_diff_fg_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG%_RANK'].values[0]
# Overall 2-Point Shooting
## 2PT
away_team_2pt = team_stats.loc[team_stats['TeamId'] == away_id, 'FG2M_PG'].values[0]
away_team_2pt_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG2M_RANK'].values[0]
away_team_opp_2pt = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG2M_PG'].values[0]
away_team_opp_2pt_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG2M_RANK'].values[0]
away_team_diff_2pt = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG2M_PG'].values[0], 1)
away_team_diff_2pt_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG2M_RANK'].values[0]
## 2PA
away_team_2pa = team_stats.loc[team_stats['TeamId'] == away_id, 'FG2A_PG'].values[0]
away_team_2pa_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG2A_RANK'].values[0]
away_team_opp_2pa = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG2A_PG'].values[0]
away_team_opp_2pa_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG2A_RANK'].values[0]
away_team_diff_2pa = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG2A_PG'].values[0], 1)
away_team_diff_2pa_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG2A_RANK'].values[0]
## 2PT%
away_team_2pt_pct = team_stats.loc[team_stats['TeamId'] == away_id, '2PT%'].values[0]
away_team_2pt_pct_rank = team_stats.loc[team_stats['TeamId'] == away_id, '2PT%_RANK'].values[0]
away_team_opp_2pt_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, '2PT%'].values[0]
away_team_opp_2pt_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, '2PT%_RANK'].values[0]
away_team_diff_2pt_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, '2PT%'].values[0]
away_team_diff_2pt_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, '2PT%_RANK'].values[0]
# Overall 3-Point Shooting
## 3PT
away_team_3pt = team_stats.loc[team_stats['TeamId'] == away_id, 'FG3M_PG'].values[0]
away_team_3pt_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG3M_RANK'].values[0]
away_team_opp_3pt = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG3M_PG'].values[0]
away_team_opp_3pt_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG3M_RANK'].values[0]
away_team_diff_3pt = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG3M_PG'].values[0], 1)
away_team_diff_3pt_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG3M_RANK'].values[0]
## 3PA
away_team_3pa = team_stats.loc[team_stats['TeamId'] == away_id, 'FG3A_PG'].values[0]
away_team_3pa_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FG3A_RANK'].values[0]
away_team_opp_3pa = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG3A_PG'].values[0]
away_team_opp_3pa_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FG3A_RANK'].values[0]
away_team_diff_3pa = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG3A_PG'].values[0], 1)
away_team_diff_3pa_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FG3A_RANK'].values[0]
## 3PT%
away_team_3pt_pct = team_stats.loc[team_stats['TeamId'] == away_id, '3PT%'].values[0]
away_team_3pt_pct_rank = team_stats.loc[team_stats['TeamId'] == away_id, '3PT%_RANK'].values[0]
away_team_opp_3pt_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, '3PT%'].values[0]
away_team_opp_3pt_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, '3PT%_RANK'].values[0]
away_team_diff_3pt_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, '3PT%'].values[0]
away_team_diff_3pt_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, '3PT%_RANK'].values[0]
# Overall Free Throw Shooting
## FTM
away_team_ftm = team_stats.loc[team_stats['TeamId'] == away_id, 'FTM_PG'].values[0]
away_team_ftm_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FTM_RANK'].values[0]
away_team_opp_ftm = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FTM_PG'].values[0]
away_team_opp_ftm_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FTM_RANK'].values[0]
away_team_diff_ftm = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FTM_PG'].values[0], 1)
away_team_diff_ftm_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FTM_RANK'].values[0]
## FTA
away_team_fta = team_stats.loc[team_stats['TeamId'] == away_id, 'FTA_PG'].values[0]
away_team_fta_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FTA_RANK'].values[0]
away_team_opp_fta = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FTA_PG'].values[0]
away_team_opp_fta_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FTA_RANK'].values[0]
away_team_diff_fta = round(shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FTA_PG'].values[0], 1)
away_team_diff_fta_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FTA_RANK'].values[0]
## FT%
away_team_ft_pct = team_stats.loc[team_stats['TeamId'] == away_id, 'FT%'].values[0]
away_team_ft_pct_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'FT%_RANK'].values[0]
away_team_opp_ft_pct = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FT%'].values[0]
away_team_opp_ft_pct_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'FT%_RANK'].values[0]
away_team_diff_ft_pct = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FT%'].values[0]
away_team_diff_ft_pct_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'FT%_RANK'].values[0]
# RIM
## Rim Frequency
away_team_rim_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'AtRimFrequency'].values[0]
away_team_rim_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'RIM_FREQ_RANK'].values[0]
away_team_opp_rim_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'AtRimFrequency'].values[0]
away_team_opp_rim_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'RIM_FREQ_RANK'].values[0]
away_team_diff_rim_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'AtRimFrequency'].values[0]
away_team_diff_rim_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'RIM_FREQ_RANK'].values[0]
## Rim Accuracy
away_team_rim_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'AtRimAccuracy'].values[0]
away_team_rim_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'RIM_FG%_RANK'].values[0]
away_team_opp_rim_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'AtRimAccuracy'].values[0]
away_team_opp_rim_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'RIM_FG%_RANK'].values[0]
away_team_diff_rim_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'AtRimAccuracy'].values[0]
away_team_diff_rim_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'RIM_FG%_RANK'].values[0]

# Short Mid-Range Shooting
## SMR Frequency
away_team_smr_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'ShortMidRangeFrequency'].values[0]
away_team_smr_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'SMR_FREQ_RANK'].values[0]
away_team_opp_smr_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'ShortMidRangeFrequency'].values[0]
away_team_opp_smr_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'SMR_FREQ_RANK'].values[0]
away_team_diff_smr_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'ShortMidRangeFrequency'].values[0]
away_team_diff_smr_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'SMR_FREQ_RANK'].values[0]
## SMR Accuracy
away_team_smr_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'ShortMidRangeAccuracy'].values[0]
away_team_smr_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'SMR_FG%_RANK'].values[0]
away_team_opp_smr_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'ShortMidRangeAccuracy'].values[0]
away_team_opp_smr_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'SMR_FG%_RANK'].values[0]
away_team_diff_smr_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'ShortMidRangeAccuracy'].values[0]
away_team_diff_smr_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'SMR_FG%_RANK'].values[0]

# Long Mid-Range Shooting
## LMR Frequency
away_team_lmr_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'LongMidRangeFrequency'].values[0]
away_team_lmr_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'LMR_FREQ_RANK'].values[0]
away_team_opp_lmr_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'LongMidRangeFrequency'].values[0]
away_team_opp_lmr_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'LMR_FREQ_RANK'].values[0]
away_team_diff_lmr_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'LongMidRangeFrequency'].values[0]
away_team_diff_lmr_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'LMR_FREQ_RANK'].values[0]
## LMR Accuracy
away_team_lmr_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'LongMidRangeAccuracy'].values[0]
away_team_lmr_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'LMR_FG%_RANK'].values[0]
away_team_opp_lmr_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'LongMidRangeAccuracy'].values[0]
away_team_opp_lmr_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'LMR_FG%_RANK'].values[0]
away_team_diff_lmr_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'LongMidRangeAccuracy'].values[0]
away_team_diff_lmr_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'LMR_FG%_RANK'].values[0]
# Corner 3-Point Shooting
## C3 Frequency
away_team_c3_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'Corner3Frequency'].values[0]
away_team_c3_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'C3_FREQ_RANK'].values[0]
away_team_opp_c3_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'Corner3Frequency'].values[0]
away_team_opp_c3_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'C3_FREQ_RANK'].values[0]
away_team_diff_c3_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'Corner3Frequency'].values[0]
away_team_diff_c3_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'C3_FREQ_RANK'].values[0]
## C3 Accuracy
away_team_c3_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'Corner3Accuracy'].values[0]
away_team_c3_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'C3_FG%_RANK'].values[0]
away_team_opp_c3_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'Corner3Accuracy'].values[0]
away_team_opp_c3_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'C3_FG%_RANK'].values[0]
away_team_diff_c3_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'Corner3Accuracy'].values[0]
away_team_diff_c3_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'C3_FG%_RANK'].values[0]
# Above the Break 3-Point Shooting
## ATB3 Frequency
away_team_atb3_freq = team_stats.loc[team_stats['TeamId'] == away_id, 'Arc3Frequency'].values[0]
away_team_atb3_freq_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'ATB3_FREQ_RANK'].values[0]
away_team_opp_atb3_freq = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'Arc3Frequency'].values[0]
away_team_opp_atb3_freq_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'ATB3_FREQ_RANK'].values[0]
away_team_diff_atb3_freq = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'Arc3Frequency'].values[0]
away_team_diff_atb3_freq_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'ATB3_FREQ_RANK'].values[0]
## ATB3 Accuracy
away_team_atb3_acc = team_stats.loc[team_stats['TeamId'] == away_id, 'Arc3Accuracy'].values[0]
away_team_atb3_acc_rank = team_stats.loc[team_stats['TeamId'] == away_id, 'ATB3_FG%_RANK'].values[0]
away_team_opp_atb3_acc = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'Arc3Accuracy'].values[0]
away_team_opp_atb3_acc_rank = opp_team_stats.loc[opp_team_stats['TeamId'] == away_id, 'ATB3_FG%_RANK'].values[0]
away_team_diff_atb3_acc = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'Arc3Accuracy'].values[0]
away_team_diff_atb3_acc_rank = shooting_diff_results.loc[shooting_diff_results['TeamId'] == away_id, 'ATB3_FG%_RANK'].values[0]

## LEAGUE AVERAGE SHOOTING STATS

la_fgm = round(team_stats_diff['FGM_PG'].mean(), 1)
la_fga = round(team_stats_diff['FGA_PG'].mean(), 1)
la_fg_pct = round(team_stats_diff['FG%'].mean(), 3)

la_2pt = round(team_stats_diff['FG2M_PG'].mean(), 1)
la_2pa = round(team_stats_diff['FG2A_PG'].mean(), 1)
la_2pt_pct = round(team_stats_diff['2PT%'].mean(), 3)

la_3pt = round(team_stats_diff['FG3M_PG'].mean(), 1)
la_3pa = round(team_stats_diff['FG3A_PG'].mean(), 1)
la_3pt_pct = round(team_stats_diff['3PT%'].mean(), 3)

la_ftm = round(team_stats_diff['FTM_PG'].mean(), 1)
la_fta = round(team_stats_diff['FTA_PG'].mean(), 1)
la_ft_pct = round(team_stats_diff['FT%'].mean(), 3)

la_rim_freq = round(team_stats_diff['AtRimFrequency'].mean(), 3)
la_rim_acc = round(team_stats_diff['AtRimAccuracy'].mean(), 3)

la_smr_freq = round(team_stats_diff['ShortMidRangeFrequency'].mean(), 3)
la_smr_acc = round(team_stats_diff['ShortMidRangeAccuracy'].mean(), 3)

la_lmr_freq = round(team_stats_diff['LongMidRangeFrequency'].mean(), 3)
la_lmr_acc = round(team_stats_diff['LongMidRangeAccuracy'].mean(), 3)

la_atb3_freq = round(team_stats_diff['Arc3Frequency'].mean(), 3)
la_atb3_acc = round(team_stats_diff['Arc3Accuracy'].mean(), 3)

la_c3_freq = round(team_stats_diff['Corner3Frequency'].mean(), 3)
la_c3_acc = round(team_stats_diff['Corner3Accuracy'].mean(), 3)

# ============================================================
# PLAYER ROSTER FUNCTIONS FOR TEAMS PAGE
# ============================================================

league_id = '00'  # NBA league ID

@st.cache_data(ttl=21600, show_spinner=False)
def get_players_dataframe():
    """Get players dataframe from PlayerIndex endpoint for the current season"""
    # Fetch from API
    try:
        player_index = nba_api.stats.endpoints.PlayerIndex(
            league_id=league_id,
            season=current_season
        )
        players_df = player_index.get_data_frames()[0]
        if len(players_df) > 0 and 'PERSON_ID' in players_df.columns:
            return players_df
    except Exception:
        pass
    
    try:
        player_index = nba_api.stats.endpoints.PlayerIndex(
            league_id_nullable=league_id,
            season_nullable=current_season
        )
        players_df = player_index.get_data_frames()[0]
        if len(players_df) > 0 and 'PERSON_ID' in players_df.columns:
            return players_df
    except Exception:
        pass
    
    return pd.DataFrame()


def get_all_player_game_logs():
    """Get game logs for all players in the current season (uses Supabase cache)"""
    print(f"[DEBUG] get_all_player_game_logs() called - pf is {pf is not None}")
    # Try to use cached version from prediction_features if available
    if pf is not None:
        try:
            print("[DEBUG] Using pf.get_bulk_player_game_logs() for Supabase cache")
            return pf.get_bulk_player_game_logs(season=current_season)
        except Exception as e:
            print(f"Error fetching cached game logs: {e}, falling back to direct API call")
            import traceback
            traceback.print_exc()
    
    # Fallback to direct API call
    try:
        game_logs = nba_api.stats.endpoints.PlayerGameLogs(
            season_nullable=current_season,
            league_id_nullable=league_id
        ).get_data_frames()[0]
        
        # Filter out preseason games (keep regular season '2' and playoffs '4')
        if len(game_logs) > 0:
            game_logs = game_logs[
                game_logs['GAME_ID'].astype(str).str[2].isin(['2', '4'])
            ].copy()
        
        return game_logs
    except Exception as e:
        print(f"Error fetching player game logs: {e}")
        return pd.DataFrame()


def get_team_roster_stats(team_id: int, players_df: pd.DataFrame, game_logs_df: pd.DataFrame, num_games: int = None, per_mode: str = 'PerGame'):
    """
    Get rolling averages or totals for all players on a team.
    
    Args:
        team_id: NBA team ID
        players_df: DataFrame from PlayerIndex
        game_logs_df: DataFrame from PlayerGameLogs
        num_games: Number of recent TEAM games to average (None = all games / season)
        per_mode: 'PerGame' for averages or 'Totals' for totals
    
    Returns:
        DataFrame with player stats
    """
    # Filter players by team
    team_players = players_df[players_df['TEAM_ID'].astype(int) == team_id].copy()
    
    if len(team_players) == 0:
        return pd.DataFrame()
    
    # Get team's game logs to identify team's last N games
    # Player game logs don't have TEAM_ID - need to get team game logs separately
    # Try to get team game logs first (has TEAM_ID column)
    team_logs = None
    try:
        if pf is not None:
            team_game_logs_df = pf.get_bulk_team_game_logs(season=current_season)
            if team_game_logs_df is not None and len(team_game_logs_df) > 0 and 'TEAM_ID' in team_game_logs_df.columns:
                # Filter team game logs for this team
                team_logs = team_game_logs_df[team_game_logs_df['TEAM_ID'].astype(int) == team_id].copy()
    except Exception as e:
        pass
    
    # Fallback: extract game IDs from player game logs for players on this team
    if team_logs is None or len(team_logs) == 0:
        team_player_ids = team_players['PERSON_ID'].tolist()
        team_player_logs = game_logs_df[game_logs_df['PLAYER_ID'].isin(team_player_ids)].copy()
        if len(team_player_logs) > 0:
            # Get unique game IDs and dates from team players' game logs
            team_logs = team_player_logs[['GAME_ID', 'GAME_DATE']].drop_duplicates().copy()
        else:
            team_logs = pd.DataFrame()
    
    if len(team_logs) == 0:
        return pd.DataFrame()
    
    # Get unique team games, sorted by date descending (most recent first)
    team_logs['GAME_DATE'] = pd.to_datetime(team_logs['GAME_DATE'])
    team_logs = team_logs.sort_values(by='GAME_DATE', ascending=False)
    
    # Get unique game IDs for the team's last N games
    if num_games is not None and num_games > 0:
        # Get unique game IDs from the most recent N games
        team_game_ids = team_logs['GAME_ID'].unique()[:num_games]
    else:
        # All team games
        team_game_ids = team_logs['GAME_ID'].unique()
    
    roster_stats = []
    
    for _, player in team_players.iterrows():
        player_id = player['PERSON_ID']
        player_name = f"{player['PLAYER_FIRST_NAME']} {player['PLAYER_LAST_NAME']}"
        position = player.get('POSITION', '')
        
        # Get player's game logs
        player_logs = game_logs_df[game_logs_df['PLAYER_ID'] == player_id].copy()
        
        if len(player_logs) == 0:
            continue
        
        # Filter to only include games from the team's last N games
        player_logs = player_logs[player_logs['GAME_ID'].isin(team_game_ids)].copy()
        
        if len(player_logs) == 0:
            continue
        
        # Sort by date descending (most recent first) for consistency
        player_logs['GAME_DATE'] = pd.to_datetime(player_logs['GAME_DATE'])
        player_logs = player_logs.sort_values(by='GAME_DATE', ascending=False)
        
        if len(player_logs) == 0:
            continue
        
        # Calculate averages or totals based on per_mode
        games_played = len(player_logs)
        
        if per_mode == 'Totals':
            # Calculate totals
            min_val = round(player_logs['MIN'].sum(), 1)
            pts_val = round(player_logs['PTS'].sum(), 1)
            reb_val = round(player_logs['REB'].sum(), 1)
            ast_val = round(player_logs['AST'].sum(), 1)
            pra_val = round(pts_val + reb_val + ast_val, 1)
            stl_val = round(player_logs['STL'].sum(), 1)
            blk_val = round(player_logs['BLK'].sum(), 1)
            tov_val = round(player_logs['TOV'].sum(), 1)
            
            # Field Goal stats
            fgm_val = round(player_logs['FGM'].sum(), 1)
            fga_val = round(player_logs['FGA'].sum(), 1)
            total_fgm = player_logs['FGM'].sum()
            total_fga = player_logs['FGA'].sum()
            fg_pct = round((total_fgm / total_fga * 100), 1) if total_fga > 0 else 0.0
            
            # 3-Point stats
            fg3m_val = round(player_logs['FG3M'].sum(), 1)
            fg3a_val = round(player_logs['FG3A'].sum(), 1)
            total_fg3m = player_logs['FG3M'].sum()
            total_fg3a = player_logs['FG3A'].sum()
            fg3_pct = round((total_fg3m / total_fg3a * 100), 1) if total_fg3a > 0 else 0.0
            
            # Free Throw stats
            ftm_val = round(player_logs['FTM'].sum(), 1)
            fta_val = round(player_logs['FTA'].sum(), 1)
            total_ftm = player_logs['FTM'].sum()
            total_fta = player_logs['FTA'].sum()
            ft_pct = round((total_ftm / total_fta * 100), 1) if total_fta > 0 else 0.0
            
            # Calculate FPTS (fantasy points) - totals
            fpts_val = round(pts_val + reb_val * 1.2 + ast_val * 1.5 + stl_val * 3 + blk_val * 3 - tov_val, 1)
        else:
            # Calculate averages (PerGame)
            min_val = round(player_logs['MIN'].mean(), 1)
            pts_val = round(player_logs['PTS'].mean(), 1)
            reb_val = round(player_logs['REB'].mean(), 1)
            ast_val = round(player_logs['AST'].mean(), 1)
            pra_val = round(pts_val + reb_val + ast_val, 1)
            stl_val = round(player_logs['STL'].mean(), 1)
            blk_val = round(player_logs['BLK'].mean(), 1)
            tov_val = round(player_logs['TOV'].mean(), 1)
            
            # Field Goal stats
            fgm_val = round(player_logs['FGM'].mean(), 1)
            fga_val = round(player_logs['FGA'].mean(), 1)
            total_fgm = player_logs['FGM'].sum()
            total_fga = player_logs['FGA'].sum()
            fg_pct = round((total_fgm / total_fga * 100), 1) if total_fga > 0 else 0.0
            
            # 3-Point stats
            fg3m_val = round(player_logs['FG3M'].mean(), 1)
            fg3a_val = round(player_logs['FG3A'].mean(), 1)
            total_fg3m = player_logs['FG3M'].sum()
            total_fg3a = player_logs['FG3A'].sum()
            fg3_pct = round((total_fg3m / total_fg3a * 100), 1) if total_fg3a > 0 else 0.0
            
            # Free Throw stats
            ftm_val = round(player_logs['FTM'].mean(), 1)
            fta_val = round(player_logs['FTA'].mean(), 1)
            total_ftm = player_logs['FTM'].sum()
            total_fta = player_logs['FTA'].sum()
            ft_pct = round((total_ftm / total_fta * 100), 1) if total_fta > 0 else 0.0
            
            # Calculate FPTS (fantasy points) - averages
            fpts_val = round(pts_val + reb_val * 1.2 + ast_val * 1.5 + stl_val * 3 + blk_val * 3 - tov_val, 1)
        
        # Headshot URL
        headshot_url = f'https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png'
        
        roster_stats.append({
            'headshot': headshot_url,
            'Player': player_name,
            'Pos': position,
            'GP': games_played,
            'MIN': min_val,
            'PTS': pts_val,
            'REB': reb_val,
            'AST': ast_val,
            'PRA': pra_val,
            'STL': stl_val,
            'BLK': blk_val,
            'TOV': tov_val,
            'FGM': fgm_val,
            'FPTS': fpts_val,
            'FGA': fga_val,
            'FG%': fg_pct,
            '3PM': fg3m_val,
            '3PA': fg3a_val,
            '3P%': fg3_pct,
            'FTM': ftm_val,
            'FTA': fta_val,
            'FT%': ft_pct,
            '_player_id': player_id,  # Hidden column for sorting
        })
    
    if not roster_stats:
        return pd.DataFrame()
    
    # Create DataFrame and sort by minutes (descending)
    df = pd.DataFrame(roster_stats)
    df = df.sort_values(by='MIN', ascending=False)
    
    return df


# Removed @st.cache_data - using Supabase cache instead
def get_team_clutch_stats(team_id: int, season: str = '2025-26', players_df: pd.DataFrame = None, per_mode_detailed: str = 'PerGame'):
    """
    Get clutch statistics for all players on a team.
    Clutch time is defined as last 5 minutes of game with score within 5 points.
    Uses Supabase cache when available.
    
    Args:
        team_id: NBA team ID
        season: Season string (defaults to '2025-26')
        players_df: Optional DataFrame from PlayerIndex (if None, will fetch it)
        per_mode_detailed: 'PerGame' for per game stats or 'Totals' for total stats
    
    Returns:
        DataFrame with player clutch stats formatted similarly to get_team_roster_stats
    """
    # Get players dataframe if not provided
    if players_df is None:
        players_df = get_players_dataframe()
    
    # Filter players by team
    team_players = players_df[players_df['TEAM_ID'].astype(int) == team_id].copy()
    
    if len(team_players) == 0:
        return pd.DataFrame()
    
    # Fetch from API
    try:
        clutch_data = nba_api.stats.endpoints.LeagueDashPlayerClutch(
            season=season,
            season_type_all_star='Regular Season',
            per_mode_detailed=per_mode_detailed,
            clutch_time='Last 5 Minutes',
            ahead_behind='Ahead or Behind',
            point_diff=5
        ).get_data_frames()[0]
    except Exception as e:
        print(f"Error fetching clutch stats: {e}")
        return pd.DataFrame()
    
    # Process data regardless of whether it came from cache or API
    if clutch_data is None or len(clutch_data) == 0:
        return pd.DataFrame()
    
    # Filter to only players on this team
    clutch_data = clutch_data[clutch_data['TEAM_ID'].astype(int) == team_id].copy()
    
    if len(clutch_data) == 0:
        return pd.DataFrame()
    
    roster_stats = []
    
    for _, row in clutch_data.iterrows():
        player_id = int(row['PLAYER_ID'])
        
        # Get player info from players_df
        player_info = team_players[team_players['PERSON_ID'] == player_id]
        if len(player_info) == 0:
            continue
        
        player_name = f"{player_info['PLAYER_FIRST_NAME'].iloc[0]} {player_info['PLAYER_LAST_NAME'].iloc[0]}"
        position = player_info.get('POSITION', '').iloc[0] if 'POSITION' in player_info.columns else ''
        
        # Extract stats from clutch data
        games_played = int(row.get('GP', 0))
        min_avg = round(row.get('MIN', 0.0), 1)
        pts_avg = round(row.get('PTS', 0.0), 1)
        reb_avg = round(row.get('REB', 0.0), 1)
        ast_avg = round(row.get('AST', 0.0), 1)
        pra_avg = round(pts_avg + reb_avg + ast_avg, 1)
        stl_avg = round(row.get('STL', 0.0), 1)
        blk_avg = round(row.get('BLK', 0.0), 1)
        tov_avg = round(row.get('TOV', 0.0), 1)
        
        # Field Goal stats
        fgm_avg = round(row.get('FGM', 0.0), 1)
        fga_avg = round(row.get('FGA', 0.0), 1)
        fg_pct = round(row.get('FG_PCT', 0.0) * 100, 1) if pd.notna(row.get('FG_PCT')) else 0.0
        
        # 3-Point stats
        fg3m_avg = round(row.get('FG3M', 0.0), 1)
        fg3a_avg = round(row.get('FG3A', 0.0), 1)
        fg3_pct = round(row.get('FG3_PCT', 0.0) * 100, 1) if pd.notna(row.get('FG3_PCT')) else 0.0
        
        # Free Throw stats
        ftm_avg = round(row.get('FTM', 0.0), 1)
        fta_avg = round(row.get('FTA', 0.0), 1)
        ft_pct = round(row.get('FT_PCT', 0.0) * 100, 1) if pd.notna(row.get('FT_PCT')) else 0.0
        
        # Calculate FPTS (fantasy points)
        fpts_avg = round(pts_avg + reb_avg * 1.2 + ast_avg * 1.5 + stl_avg * 3 + blk_avg * 3 - tov_avg, 1)
        
        # Headshot URL
        headshot_url = f'https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png'
        
        roster_stats.append({
            'headshot': headshot_url,
            'Player': player_name,
            'Pos': position,
            'GP': games_played,
            'MIN': min_avg,
            'PTS': pts_avg,
            'REB': reb_avg,
            'AST': ast_avg,
            'PRA': pra_avg,
            'STL': stl_avg,
            'BLK': blk_avg,
            'TOV': tov_avg,
            'FGM': fgm_avg,
            'FPTS': fpts_avg,
            'FGA': fga_avg,
            'FG%': fg_pct,
            '3PM': fg3m_avg,
            '3PA': fg3a_avg,
            '3P%': fg3_pct,
            'FTM': ftm_avg,
            'FTA': fta_avg,
            'FT%': ft_pct,
            '_player_id': player_id,  # Hidden column for sorting
        })
    
    if not roster_stats:
        return pd.DataFrame()
    
    # Create DataFrame and sort by minutes (descending)
    df = pd.DataFrame(roster_stats)
    df = df.sort_values(by='MIN', ascending=False)
    
    return df


def process_clutch_data_to_roster(clutch_data: pd.DataFrame, players_df: pd.DataFrame, team_id: int):
    """
    Process clutch data DataFrame into roster format.
    This is a helper function to extract the processing logic from get_team_clutch_stats.
    
    Args:
        clutch_data: DataFrame with clutch stats (already filtered to team)
        players_df: DataFrame with player information
        team_id: Team ID for filtering players
    
    Returns:
        DataFrame with formatted roster stats
    """
    if clutch_data is None or len(clutch_data) == 0:
        return pd.DataFrame()
    
    # Filter players by team
    team_players = players_df[players_df['TEAM_ID'].astype(int) == team_id].copy()
    
    if len(team_players) == 0:
        return pd.DataFrame()
    
    roster_stats = []
    
    for _, row in clutch_data.iterrows():
        player_id = int(row['PLAYER_ID'])
        
        # Get player info from players_df
        player_info = team_players[team_players['PERSON_ID'] == player_id]
        if len(player_info) == 0:
            continue
        
        player_name = f"{player_info['PLAYER_FIRST_NAME'].iloc[0]} {player_info['PLAYER_LAST_NAME'].iloc[0]}"
        position = player_info.get('POSITION', '').iloc[0] if 'POSITION' in player_info.columns else ''
        
        # Extract stats from clutch data
        games_played = int(row.get('GP', 0))
        min_avg = round(row.get('MIN', 0.0), 1)
        pts_avg = round(row.get('PTS', 0.0), 1)
        reb_avg = round(row.get('REB', 0.0), 1)
        ast_avg = round(row.get('AST', 0.0), 1)
        pra_avg = round(pts_avg + reb_avg + ast_avg, 1)
        stl_avg = round(row.get('STL', 0.0), 1)
        blk_avg = round(row.get('BLK', 0.0), 1)
        tov_avg = round(row.get('TOV', 0.0), 1)
        
        # Field Goal stats
        fgm_avg = round(row.get('FGM', 0.0), 1)
        fga_avg = round(row.get('FGA', 0.0), 1)
        fg_pct = round(row.get('FG_PCT', 0.0) * 100, 1) if pd.notna(row.get('FG_PCT')) else 0.0
        
        # 3-Point stats
        fg3m_avg = round(row.get('FG3M', 0.0), 1)
        fg3a_avg = round(row.get('FG3A', 0.0), 1)
        fg3_pct = round(row.get('FG3_PCT', 0.0) * 100, 1) if pd.notna(row.get('FG3_PCT')) else 0.0
        
        # Free Throw stats
        ftm_avg = round(row.get('FTM', 0.0), 1)
        fta_avg = round(row.get('FTA', 0.0), 1)
        ft_pct = round(row.get('FT_PCT', 0.0) * 100, 1) if pd.notna(row.get('FT_PCT')) else 0.0
        
        # Calculate FPTS (fantasy points)
        fpts_avg = round(pts_avg + reb_avg * 1.2 + ast_avg * 1.5 + stl_avg * 3 + blk_avg * 3 - tov_avg, 1)
        
        # Headshot URL
        headshot_url = f'https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png'
        
        roster_stats.append({
            'headshot': headshot_url,
            'Player': player_name,
            'Pos': position,
            'GP': games_played,
            'MIN': min_avg,
            'PTS': pts_avg,
            'REB': reb_avg,
            'AST': ast_avg,
            'PRA': pra_avg,
            'STL': stl_avg,
            'BLK': blk_avg,
            'TOV': tov_avg,
            'FGM': fgm_avg,
            'FPTS': fpts_avg,
            'FGA': fga_avg,
            'FG%': fg_pct,
            '3PM': fg3m_avg,
            '3PA': fg3a_avg,
            '3P%': fg3_pct,
            'FTM': ftm_avg,
            'FTA': fta_avg,
            'FT%': ft_pct,
            '_player_id': player_id,  # Hidden column for sorting
        })
    
    if not roster_stats:
        return pd.DataFrame()
    
    # Create DataFrame and sort by minutes (descending)
    df = pd.DataFrame(roster_stats)
    df = df.sort_values(by='MIN', ascending=False)
    
    return df


# ============================================================
# MATCHUP SUMMARY FUNCTIONS
# ============================================================

def calculate_games_missed(player_id, team_id: int, game_logs_df: pd.DataFrame) -> str:
    """
    Calculate how many team games a player has missed.
    
    Args:
        player_id: The player's NBA ID (can be int or string)
        team_id: The team's NBA ID
        game_logs_df: DataFrame from get_all_player_game_logs()
    
    Returns:
        String like "3 games" or "Season" if no games played
    """
    # Convert player_id to int for comparison
    try:
        player_id_int = int(player_id)
    except (ValueError, TypeError):
        return "Unknown"
    
    # Get player's game logs
    player_logs = game_logs_df[game_logs_df['PLAYER_ID'] == player_id_int]
    
    if len(player_logs) == 0:
        return "Season"  # No games this season
    
    # Get player's last game date
    player_last_game = pd.to_datetime(player_logs['GAME_DATE'].max())
    
    # Get team's games (distinct game dates for any player on that team)
    team_logs = game_logs_df[game_logs_df['TEAM_ID'] == team_id]
    team_game_dates = pd.to_datetime(team_logs['GAME_DATE'].unique())
    
    # Count team games after player's last game
    games_missed = sum(1 for d in team_game_dates if d > player_last_game)
    
    if games_missed == 0:
        return "0"
    elif games_missed == 1:
        return "1 game"
    else:
        return f"{games_missed} games"


def find_hot_players(team_id: int, players_df: pd.DataFrame, game_logs_df: pd.DataFrame, 
                     threshold_pct: float = 0.20, min_l5_games: int = 3) -> list:
    """
    Find players performing significantly above their season average.
    
    Args:
        team_id: Team ID to analyze
        players_df: DataFrame from PlayerIndex
        game_logs_df: DataFrame from PlayerGameLogs
        threshold_pct: Minimum % above season avg to qualify (0.20 = 20%)
        min_l5_games: Minimum games in L5 sample
    
    Returns:
        List of dicts with player info and hot stats
    """
    hot_players = []
    
    # Get season stats for comparison
    season_stats = get_team_roster_stats(team_id, players_df, game_logs_df, num_games=None)
    l5_stats = get_team_roster_stats(team_id, players_df, game_logs_df, num_games=5)
    
    if len(season_stats) == 0 or len(l5_stats) == 0:
        return hot_players
    
    # Join season and L5 stats
    for _, l5_row in l5_stats.iterrows():
        player_name = l5_row['Player']
        
        # Must have at least min_l5_games in L5
        if l5_row['GP'] < min_l5_games:
            continue
        
        # Find season row
        season_row = season_stats[season_stats['Player'] == player_name]
        if len(season_row) == 0:
            continue
        season_row = season_row.iloc[0]
        
        # Skip if season avg is too low (avoid division issues)
        if season_row['PTS'] < 3:
            continue
        
        # Calculate % increase for key stats
        hot_stats = []
        
        for stat in ['PTS', 'REB', 'AST']:
            season_val = season_row[stat]
            l5_val = l5_row[stat]
            
            if season_val > 0:
                pct_change = (l5_val - season_val) / season_val
                if pct_change >= threshold_pct:
                    hot_stats.append({
                        'stat': stat,
                        'season': season_val,
                        'l5': l5_val,
                        'pct_change': pct_change
                    })
        
        if hot_stats:
            # Sort by biggest improvement
            hot_stats.sort(key=lambda x: x['pct_change'], reverse=True)
            hot_players.append({
                'player_name': player_name,
                'player_id': l5_row.get('_player_id'),
                'headshot': l5_row.get('headshot'),
                'hot_stats': hot_stats,
                'best_pct_change': hot_stats[0]['pct_change']
            })
    
    # Sort by biggest improvement
    hot_players.sort(key=lambda x: x['best_pct_change'], reverse=True)
    
    return hot_players


def find_cold_players(team_id: int, players_df: pd.DataFrame, game_logs_df: pd.DataFrame, 
                      threshold_pct: float = 0.20, min_l5_games: int = 3) -> list:
    """
    Find players performing significantly below their season average.
    
    Args:
        team_id: Team ID to analyze
        players_df: DataFrame from PlayerIndex
        game_logs_df: DataFrame from PlayerGameLogs
        threshold_pct: Minimum % below season avg to qualify (0.20 = 20%)
        min_l5_games: Minimum games in L5 sample
    
    Returns:
        List of dicts with player info and cold stats
    """
    cold_players = []
    
    # Get season stats for comparison
    season_stats = get_team_roster_stats(team_id, players_df, game_logs_df, num_games=None)
    l5_stats = get_team_roster_stats(team_id, players_df, game_logs_df, num_games=5)
    
    if len(season_stats) == 0 or len(l5_stats) == 0:
        return cold_players
    
    for _, l5_row in l5_stats.iterrows():
        player_name = l5_row['Player']
        
        # Must have at least min_l5_games in L5
        if l5_row['GP'] < min_l5_games:
            continue
        
        # Find season row
        season_row = season_stats[season_stats['Player'] == player_name]
        if len(season_row) == 0:
            continue
        season_row = season_row.iloc[0]
        
        # Skip if season avg is too low (avoid division issues and focus on meaningful players)
        if season_row['PTS'] < 8:
            continue
        
        # Calculate % decrease for key stats
        cold_stats = []
        
        for stat in ['PTS', 'REB', 'AST']:
            season_val = season_row[stat]
            l5_val = l5_row[stat]
            
            if season_val > 0:
                pct_change = (l5_val - season_val) / season_val
                # Looking for negative change (below average)
                if pct_change <= -threshold_pct:
                    cold_stats.append({
                        'stat': stat,
                        'season': season_val,
                        'l5': l5_val,
                        'pct_change': pct_change
                    })
        
        if cold_stats:
            # Sort by biggest decline (most negative first)
            cold_stats.sort(key=lambda x: x['pct_change'])
            cold_players.append({
                'player_name': player_name,
                'player_id': l5_row.get('_player_id'),
                'headshot': l5_row.get('headshot'),
                'cold_stats': cold_stats,
                'worst_pct_change': cold_stats[0]['pct_change']
            })
    
    # Sort by biggest decline (most negative first)
    cold_players.sort(key=lambda x: x['worst_pct_change'])
    
    return cold_players


def find_new_players(team_id: int, players_df: pd.DataFrame, game_logs_df: pd.DataFrame,
                     min_increase_pct: float = 0.25, min_season_minutes: float = 7.5) -> list:
    """
    Find players with significant minutes increases (emerging roles).
    
    Args:
        team_id: Team ID to analyze
        players_df: DataFrame from PlayerIndex
        game_logs_df: DataFrame from PlayerGameLogs
        min_increase_pct: Minimum % increase in minutes (0.25 = 25%)
        min_season_minutes: Minimum season avg minutes to qualify
    
    Returns:
        List of dicts with player info and minutes change
    """
    new_players = []
    
    # Get season and L5 stats
    season_stats = get_team_roster_stats(team_id, players_df, game_logs_df, num_games=None)
    l5_stats = get_team_roster_stats(team_id, players_df, game_logs_df, num_games=5)
    
    if len(season_stats) == 0 or len(l5_stats) == 0:
        return new_players
    
    for _, l5_row in l5_stats.iterrows():
        player_name = l5_row['Player']
        
        # Find season row
        season_row = season_stats[season_stats['Player'] == player_name]
        if len(season_row) == 0:
            continue
        season_row = season_row.iloc[0]
        
        season_min = season_row['MIN']
        l5_min = l5_row['MIN']
        
        # Must meet minimum season minutes threshold
        if season_min < min_season_minutes:
            continue
        
        # Calculate % increase
        if season_min > 0:
            pct_increase = (l5_min - season_min) / season_min
            
            if pct_increase >= min_increase_pct:
                new_players.append({
                    'player_name': player_name,
                    'player_id': l5_row.get('_player_id'),
                    'headshot': l5_row.get('headshot'),
                    'season_min': season_min,
                    'l5_min': l5_min,
                    'min_increase': l5_min - season_min,
                    'pct_increase': pct_increase,
                    # Include their L5 production
                    'l5_pts': l5_row['PTS'],
                    'l5_reb': l5_row['REB'],
                    'l5_ast': l5_row['AST']
                })
    
    # Sort by biggest % increase
    new_players.sort(key=lambda x: x['pct_increase'], reverse=True)
    
    return new_players


def calculate_stat_mismatches(away_id: int, home_id: int, away_abbr: str = 'Away', 
                               home_abbr: str = 'Home', top_n: int = 20) -> list:
    """
    Calculate the biggest stat mismatches between teams.
    
    Args:
        away_id: Away team ID
        home_id: Home team ID
        away_abbr: Away team abbreviation (e.g., 'MIN')
        home_abbr: Home team abbreviation (e.g., 'MEM')
        top_n: Number of top mismatches to return
    
    Returns:
        List of dicts with mismatch details, sorted by magnitude
    """
    mismatches = []
    
    # Define stat matchups: (name, off_stat, off_rank_col, def_stat, def_rank_col, off_df, def_df, off_higher_is_better, def_lower_is_better)
    # For single DataFrame stats, pass the same df for both off_df and def_df
    stat_matchups = [
        # Core ratings
        ('Offensive Rating', 'OFF_RATING', 'OFF_RATING_RANK', 'DEF_RATING', 'DEF_RATING_RANK', 
         data_adv_season, data_adv_season, True, True),
        
        # Shooting percentages - from Four Factors
        ('Effective FG%', 'EFG_PCT', None, 'OPP_EFG_PCT', None, data_4F_season, data_4F_season, True, True),
        
        # Rebounding
        ('Offensive Reb %', 'OREB_PCT', 'OREB_PCT_RANK', 'DREB_PCT', 'DREB_PCT_RANK', 
         data_adv_season, data_adv_season, True, True),
        
        # Playmaking
        ('Assist %', 'AST_PCT', 'AST_PCT_RANK', 'AST_PCT', 'AST_PCT_RANK', 
         data_adv_season, data_adv_season, True, True),
        
        # Turnovers
        ('Turnover %', 'TM_TOV_PCT', 'TM_TOV_PCT_RANK', 'OPP_TOV_PCT', 'OPP_TOV_PCT_RANK', 
         data_4F_season, data_4F_season, False, False),
        
        # Pace
        ('Pace', 'PACE', 'PACE_RANK', 'PACE', 'PACE_RANK', data_adv_season, data_adv_season, True, True),
        
        # Paint scoring
        ('Points in Paint', 'PTS_PAINT', 'PTS_PAINT_RANK', 'OPP_PTS_PAINT', 'OPP_PTS_PAINT_RANK',
         data_misc_season, data_misc_season, True, True),
        
        # Second chance
        ('2nd Chance Points', 'PTS_2ND_CHANCE', 'PTS_2ND_CHANCE_RANK', 'OPP_PTS_2ND_CHANCE', 'OPP_PTS_2ND_CHANCE_RANK',
         data_misc_season, data_misc_season, True, True),
        
        # Fast break
        ('Fast Break Points', 'PTS_FB', 'PTS_FB_RANK', 'OPP_PTS_FB', 'OPP_PTS_FB_RANK',
         data_misc_season, data_misc_season, True, True),
        
        # Points off turnovers
        ('Points Off Turnovers', 'PTS_OFF_TOV', 'PTS_OFF_TOV_RANK', 'OPP_PTS_OFF_TOV', 'OPP_PTS_OFF_TOV_RANK',
         data_misc_season, data_misc_season, True, True),
        
        # Free throw rate
        ('Free Throw Rate', 'FTA_RATE', None, 'OPP_FTA_RATE', None, data_4F_season, data_4F_season, True, True),
        
        # Shooting stats - using team_stats for offense and opp_team_stats for defense
        ('Field Goals Made', 'FGM_PG', 'FGM_RANK', 'FGM_PG', 'FGM_RANK',
         team_stats, opp_team_stats, True, True),
        ('Field Goals Attempted', 'FGA_PG', 'FGA_RANK', 'FGA_PG', 'FGA_RANK',
         team_stats, opp_team_stats, True, True),
        ('Field Goal %', 'FG%', 'FG%_RANK', 'FG%', 'FG%_RANK',
         team_stats, opp_team_stats, True, True),
        ('3-Pointers Made', 'FG3M_PG', 'FG3M_RANK', 'FG3M_PG', 'FG3M_RANK',
         team_stats, opp_team_stats, True, True),
        ('3-Pointers Attempted', 'FG3A_PG', 'FG3A_RANK', 'FG3A_PG', 'FG3A_RANK',
         team_stats, opp_team_stats, True, True),
        ('3-Point %', '3PT%', '3PT%_RANK', '3PT%', '3PT%_RANK',
         team_stats, opp_team_stats, True, True),
        ('Free Throws Made', 'FTM_PG', 'FTM_RANK', 'FTM_PG', 'FTM_RANK',
         team_stats, opp_team_stats, True, True),
        ('Free Throws Attempted', 'FTA_PG', 'FTA_RANK', 'FTA_PG', 'FTA_RANK',
         team_stats, opp_team_stats, True, True),
        ('Free Throw %', 'FT%', 'FT%_RANK', 'FT%', 'FT%_RANK',
         team_stats, opp_team_stats, True, True),
    ]
    
    def get_rank_and_value(df, team_id, stat_col, rank_col, use_team_id_col=False):
        """Helper to get stat value and rank
        
        Args:
            df: DataFrame to search
            team_id: Team ID to look up
            stat_col: Column name for the stat value
            rank_col: Column name for the rank (or None to calculate)
            use_team_id_col: If True, use 'TeamId' column instead of 'TEAM_ID'
        """
        id_col = 'TeamId' if use_team_id_col else 'TEAM_ID'
        team_row = df[df[id_col] == team_id]
        if len(team_row) == 0:
            return None, None
        
        value = team_row[stat_col].values[0] if stat_col in team_row.columns else None
        
        if rank_col and rank_col in team_row.columns:
            rank = int(team_row[rank_col].values[0])
        elif value is not None:
            rank = int(df[stat_col].rank(ascending=False, method='first')[team_row.index[0]])
        else:
            rank = None
            
        return value, rank
    
    # Process Away Offense vs Home Defense
    for name, off_stat, off_rank, def_stat, def_rank, off_df, def_df, off_higher_better, def_lower_better in stat_matchups:
        # Determine if we're using TeamId column (for shooting stats) or TEAM_ID (for other stats)
        use_team_id_col = (off_df is team_stats) or (def_df is opp_team_stats)
        
        away_off_val, away_off_rank = get_rank_and_value(off_df, away_id, off_stat, off_rank, use_team_id_col=use_team_id_col)
        home_def_val, home_def_rank = get_rank_and_value(def_df, home_id, def_stat, def_rank, use_team_id_col=use_team_id_col)
        
        if away_off_rank is not None and home_def_rank is not None:
            if def_lower_better:
                rank_diff = home_def_rank - away_off_rank
            else:
                rank_diff = away_off_rank - home_def_rank
            
            mismatches.append({
                'matchup_type': 'away_off_vs_home_def',
                'stat_name': name,
                'team_with_advantage': away_abbr if rank_diff > 0 else home_abbr,
                'off_team': away_abbr,
                'def_team': home_abbr,
                'off_rank': away_off_rank,
                'def_rank': home_def_rank,
                'rank_diff': abs(rank_diff),
                'raw_rank_diff': rank_diff,
                'off_value': away_off_val,
                'def_value': home_def_val
            })
    
    # Process Home Offense vs Away Defense  
    for name, off_stat, off_rank, def_stat, def_rank, off_df, def_df, off_higher_better, def_lower_better in stat_matchups:
        # Determine if we're using TeamId column (for shooting stats) or TEAM_ID (for other stats)
        use_team_id_col = (off_df is team_stats) or (def_df is opp_team_stats)
        
        home_off_val, home_off_rank = get_rank_and_value(off_df, home_id, off_stat, off_rank, use_team_id_col=use_team_id_col)
        away_def_val, away_def_rank = get_rank_and_value(def_df, away_id, def_stat, def_rank, use_team_id_col=use_team_id_col)
        
        if home_off_rank is not None and away_def_rank is not None:
            if def_lower_better:
                rank_diff = away_def_rank - home_off_rank
            else:
                rank_diff = home_off_rank - away_def_rank
                
            mismatches.append({
                'matchup_type': 'home_off_vs_away_def',
                'stat_name': name,
                'team_with_advantage': home_abbr if rank_diff > 0 else away_abbr,
                'off_team': home_abbr,
                'def_team': away_abbr,
                'off_rank': home_off_rank,
                'def_rank': away_def_rank,
                'rank_diff': abs(rank_diff),
                'raw_rank_diff': rank_diff,
                'off_value': home_off_val,
                'def_value': away_def_val
            })
    
    mismatches.sort(key=lambda x: x['rank_diff'], reverse=True)
    
    return mismatches[:top_n]


def get_key_injuries(injuries: list, game_logs_df: pd.DataFrame, team_id: int,
                     min_minutes: float = 15.0, min_pra: float = 15.0,
                     include_statuses: list = None) -> list:
    """
    Filter injuries to only show impactful players who are Questionable, Doubtful, or Out.
    
    Args:
        injuries: List of injury dicts from injury_report
        game_logs_df: DataFrame from get_all_player_game_logs()
        team_id: Team ID
        min_minutes: Minimum season avg minutes to be considered key
        min_pra: Minimum season avg PRA to be considered key
        include_statuses: List of statuses to include (default: Questionable, Doubtful, Out)
    
    Returns:
        List of key injuries with games missed info
    """
    if include_statuses is None:
        include_statuses = ['questionable', 'doubtful', 'out']
    
    key_injuries = []
    
    for inj in injuries:
        player_id = inj.get('player_id')
        if not player_id:
            continue
        
        # Filter by status (exclude Probable)
        status = inj.get('status', '').lower()
        if not any(s in status for s in include_statuses):
            continue
        
        # Convert player_id to int for comparison (injury report returns string)
        try:
            player_id_int = int(player_id)
        except (ValueError, TypeError):
            continue
        
        player_logs = game_logs_df[game_logs_df['PLAYER_ID'] == player_id_int]
        
        if len(player_logs) == 0:
            avg_min = 0
            avg_pra = 0
            games_missed = "Season"
        else:
            avg_min = player_logs['MIN'].mean()
            avg_pra = (player_logs['PTS'] + player_logs['REB'] + player_logs['AST']).mean()
            games_missed = calculate_games_missed(player_id, team_id, game_logs_df)
        
        if avg_min >= min_minutes or avg_pra >= min_pra:
            key_injuries.append({
                **inj,
                'avg_min': round(avg_min, 1),
                'avg_pra': round(avg_pra, 1),
                'games_missed': games_missed
            })
    
    key_injuries.sort(key=lambda x: x['avg_pra'], reverse=True)
    
    return key_injuries


def generate_matchup_summary(away_id: int, home_id: int, away_name: str, home_name: str,
                            away_abbr: str, home_abbr: str,
                            players_df: pd.DataFrame, game_logs_df: pd.DataFrame,
                            away_injuries: list = None, home_injuries: list = None) -> dict:
    """
    Generate a comprehensive matchup summary.
    
    Args:
        away_id: Away team ID
        home_id: Home team ID
        away_name: Away team name
        home_name: Home team name
        away_abbr: Away team abbreviation (e.g., 'MIN')
        home_abbr: Home team abbreviation (e.g., 'MEM')
        players_df: DataFrame from PlayerIndex
        game_logs_df: DataFrame from PlayerGameLogs
        away_injuries: List of away team injuries (optional)
        home_injuries: List of home team injuries (optional)
    
    Returns:
        Dict with all matchup summary data
    """
    summary = {
        'away_name': away_name,
        'home_name': home_name,
        'away_abbr': away_abbr,
        'home_abbr': home_abbr,
        'away_id': away_id,
        'home_id': home_id,
        
        'mismatches': calculate_stat_mismatches(away_id, home_id, away_abbr, home_abbr, top_n=10),
        
        'hot_players': {
            'away': find_hot_players(away_id, players_df, game_logs_df, 
                                     threshold_pct=0.20, min_l5_games=3),
            'home': find_hot_players(home_id, players_df, game_logs_df,
                                     threshold_pct=0.20, min_l5_games=3)
        },
        
        'cold_players': {
            'away': find_cold_players(away_id, players_df, game_logs_df, 
                                      threshold_pct=0.20, min_l5_games=3),
            'home': find_cold_players(home_id, players_df, game_logs_df,
                                      threshold_pct=0.20, min_l5_games=3)
        },
        
        'new_players': {
            'away': find_new_players(away_id, players_df, game_logs_df,
                                     min_increase_pct=0.25, min_season_minutes=7.5),
            'home': find_new_players(home_id, players_df, game_logs_df,
                                     min_increase_pct=0.25, min_season_minutes=7.5)
        },
        
        'key_injuries': {
            'away': get_key_injuries(away_injuries or [], game_logs_df, away_id,
                                     min_minutes=15.0, min_pra=15.0),
            'home': get_key_injuries(home_injuries or [], game_logs_df, home_id,
                                     min_minutes=15.0, min_pra=15.0)
        }
    }
    
    return summary