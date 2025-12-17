"""
Prediction Features Module
Functions to gather features for player stat predictions.
Kept separate from main codebase for modularity.
"""

import pandas as pd
import numpy as np
import streamlit as st
import nba_api.stats.endpoints as endpoints
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date
import prediction_utils as utils
import matchup_stats as ms
import positional_defense as pos_def
import team_defensive_stats as tds
import drives_stats as ds

# Current season configuration
CURRENT_SEASON = "2025-26"
LEAGUE_ID = "00"


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_position_from_index(player_id: str) -> str:
    """
    Get player's position from PlayerIndex endpoint.
    """
    try:
        player_index = endpoints.PlayerIndex(
            season=CURRENT_SEASON,
            league_id=LEAGUE_ID
        ).get_data_frames()[0]
        
        player_row = player_index[player_index['PERSON_ID'] == int(player_id)]
        if len(player_row) > 0:
            return player_row['POSITION'].iloc[0]
        return 'F'  # Default
    except Exception as e:
        print(f"Error getting player position: {e}")
        return 'F'


@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_player_game_logs(player_id: str, season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Get player's game logs for the season.
    
    Returns:
        DataFrame with game logs sorted by date descending (most recent first)
    """
    try:
        game_logs = endpoints.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        
        # Sort by date descending
        game_logs['GAME_DATE'] = pd.to_datetime(game_logs['GAME_DATE'])
        game_logs = game_logs.sort_values('GAME_DATE', ascending=False)
        
        return game_logs
    except Exception as e:
        print(f"Error fetching game logs for player {player_id}: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_team_game_logs(team_id: int, season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Get team's game logs for the season (for rest day calculation).
    
    Returns:
        DataFrame with team game logs sorted by date descending (most recent first)
    """
    try:
        team_logs = endpoints.TeamGameLog(
            team_id=team_id,
            season=season,
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        
        # Sort by date descending
        team_logs['GAME_DATE'] = pd.to_datetime(team_logs['GAME_DATE'])
        team_logs = team_logs.sort_values('GAME_DATE', ascending=False)
        
        return team_logs
    except Exception as e:
        print(f"Error fetching game logs for team {team_id}: {e}")
        return pd.DataFrame()


def get_player_rolling_averages(game_logs: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """
    Calculate rolling averages from game logs.
    
    Returns:
        Dict with L3, L5, L10, Season averages for key stats
    """
    stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M', 'FTM', 'FTA', 'MIN', 'TOV']
    result = {}
    
    for window, label in [(3, 'L3'), (5, 'L5'), (10, 'L10'), (len(game_logs), 'Season')]:
        subset = game_logs.head(window)
        if len(subset) > 0:
            result[label] = {stat: round(subset[stat].mean(), 1) for stat in stats if stat in subset.columns}
            # Add PRA
            if all(s in subset.columns for s in ['PTS', 'REB', 'AST']):
                result[label]['PRA'] = round(subset['PTS'].mean() + subset['REB'].mean() + subset['AST'].mean(), 1)
            # Add Free Throw Rate (FTA / FGA)
            if all(s in subset.columns for s in ['FTA', 'FGA']):
                total_fta = subset['FTA'].sum()
                total_fga = subset['FGA'].sum()
                result[label]['FT_RATE'] = round(total_fta / total_fga * 100, 1) if total_fga > 0 else 0.0
    
    return result


def get_player_home_away_splits(game_logs: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """
    Calculate home vs away splits.
    
    Returns:
        Dict with 'home' and 'away' averages
    """
    stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'MIN', 'FTM', 'FG3M']
    result = {'home': {}, 'away': {}}
    
    # MATCHUP format: "TEAM vs. OPP" (home) or "TEAM @ OPP" (away)
    if 'MATCHUP' in game_logs.columns:
        home_games = game_logs[game_logs['MATCHUP'].str.contains('vs.', na=False)]
        away_games = game_logs[game_logs['MATCHUP'].str.contains('@', na=False)]
        
        for stat in stats:
            if stat in game_logs.columns:
                result['home'][stat] = round(home_games[stat].mean(), 1) if len(home_games) > 0 else 0.0
                result['away'][stat] = round(away_games[stat].mean(), 1) if len(away_games) > 0 else 0.0
    
    return result


def get_player_vs_opponent_history(
    game_logs: pd.DataFrame,
    opponent_abbr: str
) -> Dict[str, float]:
    """
    Get player's historical performance against a specific opponent.
    
    Returns:
        Dict with averages against the opponent
    """
    stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'MIN', 'FG3M', 'FTM']
    
    # Check if MATCHUP column exists
    if 'MATCHUP' not in game_logs.columns:
        return {'games_played': 0}
    
    # Filter games against opponent
    vs_opp = game_logs[game_logs['MATCHUP'].str.contains(opponent_abbr, na=False)]
    
    if len(vs_opp) == 0:
        return {'games_played': 0}
    
    result = {'games_played': len(vs_opp)}
    for stat in stats:
        if stat in vs_opp.columns:
            result[stat] = round(vs_opp[stat].mean(), 1)
    
    # Add PRA
    if all(s in vs_opp.columns for s in ['PTS', 'REB', 'AST']):
        result['PRA'] = round(vs_opp['PTS'].mean() + vs_opp['REB'].mean() + vs_opp['AST'].mean(), 1)
    
    # Add FT Rate for vs opponent
    if all(s in vs_opp.columns for s in ['FTA', 'FGA']):
        total_fta = vs_opp['FTA'].sum()
        total_fga = vs_opp['FGA'].sum()
        result['FT_RATE'] = round(total_fta / total_fga * 100, 1) if total_fga > 0 else 0.0
    
    return result


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_team_pace(team_id: int, season: str = CURRENT_SEASON) -> float:
    """
    Get team's pace (possessions per game).
    """
    try:
        team_stats = endpoints.TeamDashboardByGeneralSplits(
            team_id=team_id,
            season=season,
            measure_type_detailed_defense='Advanced',
            per_mode_detailed='PerGame'
        ).get_data_frames()[0]
        
        if 'PACE' in team_stats.columns and len(team_stats) > 0:
            return round(team_stats['PACE'].iloc[0], 1)
    except Exception as e:
        print(f"Error fetching pace for team {team_id}: {e}")
    
    return 100.0  # League average default


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_opponent_ft_rate(opponent_team_id: int) -> Dict[str, float]:
    """
    Get opponent's Free Throw Rate allowed (FTA/FGA).
    Higher FT Rate = opponents get to the line more often against this team.
    
    Returns:
        Dict with opp_ft_rate, opp_ft_rate_rank, league_avg_ft_rate
    """
    try:
        # Load the team defensive stats
        _, opp_team_stats = tds.load_shooting_data()
        
        if opp_team_stats is None:
            return {'opp_ft_rate': 25.0, 'opp_ft_rate_rank': 15, 'league_avg_ft_rate': 25.0}
        
        opp_def_stats = tds.get_team_defensive_stats(opponent_team_id, opp_team_stats)
        
        if opp_def_stats is None:
            return {'opp_ft_rate': 25.0, 'opp_ft_rate_rank': 15, 'league_avg_ft_rate': 25.0}
        
        # Calculate league average FT Rate
        league_avg_ft_rate = opp_team_stats['FT_RATE'].mean() * 100  # Convert to percentage
        
        return {
            'opp_ft_rate': opp_def_stats.get('opp_ft_rate', 25.0),
            'opp_ft_rate_rank': opp_def_stats.get('opp_ft_rate_rank', 15),
            'league_avg_ft_rate': round(league_avg_ft_rate, 1)
        }
    except Exception as e:
        print(f"Error getting opponent FT Rate: {e}")
        return {'opp_ft_rate': 25.0, 'opp_ft_rate_rank': 15, 'league_avg_ft_rate': 25.0}


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_team_defensive_rating(team_id: int, season: str = CURRENT_SEASON) -> float:
    """
    Get team's defensive rating (points allowed per 100 possessions).
    """
    try:
        team_stats = endpoints.TeamDashboardByGeneralSplits(
            team_id=team_id,
            season=season,
            measure_type_detailed_defense='Advanced',
            per_mode_detailed='PerGame'
        ).get_data_frames()[0]
        
        if 'DEF_RATING' in team_stats.columns and len(team_stats) > 0:
            return round(team_stats['DEF_RATING'].iloc[0], 1)
    except Exception as e:
        print(f"Error fetching def rating for team {team_id}: {e}")
    
    return 110.0  # League average default


@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_team_defensive_rating_last_n(
    team_id: int,
    n_games: int = 5,
    season: str = CURRENT_SEASON
) -> float:
    """
    Get team's defensive rating over last N games.
    """
    try:
        team_stats = endpoints.TeamDashboardByLastNGames(
            team_id=team_id,
            season=season,
            measure_type_detailed_defense='Advanced',
            last_n_games=n_games
        ).get_data_frames()[0]
        
        if 'DEF_RATING' in team_stats.columns and len(team_stats) > 0:
            return round(team_stats['DEF_RATING'].iloc[0], 1)
    except Exception as e:
        print(f"Error fetching L{n_games} def rating for team {team_id}: {e}")
    
    return 110.0  # Default


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_league_averages(season: str = CURRENT_SEASON) -> Dict[str, float]:
    """
    Get league average stats for normalization.
    """
    try:
        league_stats = endpoints.LeagueDashTeamStats(
            season=season,
            measure_type_detailed_defense='Advanced',
            per_mode_detailed='PerGame'
        ).get_data_frames()[0]
        
        return {
            'pace': round(league_stats['PACE'].mean(), 1),
            'def_rating': round(league_stats['DEF_RATING'].mean(), 1),
            'off_rating': round(league_stats['OFF_RATING'].mean(), 1),
        }
    except Exception as e:
        print(f"Error fetching league averages: {e}")
        return {'pace': 100.0, 'def_rating': 110.0, 'off_rating': 110.0}


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_player_usage_rate(player_id: str, season: str = CURRENT_SEASON) -> float:
    """
    Get player's usage rate.
    """
    try:
        player_stats = endpoints.LeagueDashPlayerStats(
            season=season,
            measure_type_detailed_defense='Advanced',
            per_mode_detailed='PerGame'
        ).get_data_frames()[0]
        
        player_row = player_stats[player_stats['PLAYER_ID'] == int(player_id)]
        if len(player_row) > 0 and 'USG_PCT' in player_row.columns:
            return round(player_row['USG_PCT'].iloc[0] * 100, 1)
    except Exception as e:
        print(f"Error fetching usage rate for player {player_id}: {e}")
    
    return 20.0  # League average default


def get_player_minutes_trend(game_logs: pd.DataFrame, window: int = 5) -> Dict[str, float]:
    """
    Analyze player's minutes trend.
    """
    if 'MIN' not in game_logs.columns or len(game_logs) < window:
        return {'avg': 0.0, 'trend': 0.0}
    
    recent_mins = game_logs['MIN'].head(window).tolist()
    
    return {
        'avg': round(np.mean(recent_mins), 1),
        'trend': utils.calculate_trend(game_logs['MIN'].tolist(), window)
    }


def calculate_days_rest(team_id: int, game_date: str) -> int:
    """
    Calculate days of rest before a game using team's schedule.
    
    Uses team game logs instead of player game logs since players may miss games.
    
    Args:
        team_id: The player's team ID
        game_date: The date of the upcoming game (YYYY-MM-DD)
    
    Returns:
        Number of days since team's last game (1 = back-to-back)
    """
    try:
        target = pd.to_datetime(game_date).date()
        
        # Get team's game logs (cached)
        team_logs = get_team_game_logs(team_id)
        
        if team_logs.empty or 'GAME_DATE' not in team_logs.columns:
            return 2  # Default to normal rest
        
        # Find the most recent game before the target date
        for _, row in team_logs.iterrows():
            game_dt = row['GAME_DATE'].date()
            if game_dt < target:
                days_rest = (target - game_dt).days
                return days_rest
        
        return 2  # Default if no previous games found
    except Exception as e:
        print(f"Error calculating days rest for team {team_id}: {e}")
        return 2  # Default


def get_all_prediction_features(
    player_id: str,
    player_team_id: int,
    opponent_team_id: int,
    opponent_abbr: str,
    game_date: str,
    is_home: bool
) -> Dict:
    """
    Gather all features needed for prediction.
    
    Args:
        player_id: NBA API player ID
        player_team_id: Player's team ID (for rest calculation)
        opponent_team_id: Opponent's team ID
        opponent_abbr: Opponent's team abbreviation (e.g., 'LAL')
        game_date: Date of the game (YYYY-MM-DD)
        is_home: Whether player's team is playing at home
    
    Returns:
        Dict with all prediction features
    """
    features = {}
    
    # Get player game logs (cached)
    game_logs = get_player_game_logs(player_id)
    
    # Store game_logs in features for reuse in prediction model
    features['game_logs'] = game_logs
    
    # Player rolling averages
    features['rolling_avgs'] = get_player_rolling_averages(game_logs)
    
    # Season PPG for tier determination (stable metric)
    features['season_ppg'] = features['rolling_avgs'].get('Season', {}).get('PTS', 0.0)
    
    # Home/Away splits
    features['home_away_splits'] = get_player_home_away_splits(game_logs)
    features['is_home'] = is_home
    
    # Historical vs opponent
    features['vs_opponent'] = get_player_vs_opponent_history(game_logs, opponent_abbr)
    
    # Rest days (using team schedule for accuracy)
    features['days_rest'] = calculate_days_rest(player_team_id, game_date)
    features['is_back_to_back'] = utils.is_back_to_back(features['days_rest'])
    
    # Opponent stats
    opp_ft_rate_stats = get_opponent_ft_rate(opponent_team_id)
    features['opponent'] = {
        'team_id': opponent_team_id,
        'abbr': opponent_abbr,
        'pace': get_team_pace(opponent_team_id),
        'def_rating': get_team_defensive_rating(opponent_team_id),
        'def_rating_L5': get_team_defensive_rating_last_n(opponent_team_id, 5),
        'ft_rate_allowed': opp_ft_rate_stats.get('opp_ft_rate', 25.0),
        'ft_rate_allowed_rank': opp_ft_rate_stats.get('opp_ft_rate_rank', 15),
    }
    features['league_avg_ft_rate'] = opp_ft_rate_stats.get('league_avg_ft_rate', 25.0)
    
    # League averages for normalization
    features['league_avg'] = get_league_averages()
    
    # Player usage
    features['usage_rate'] = get_player_usage_rate(player_id)
    
    # Minutes trend
    features['minutes_trend'] = get_player_minutes_trend(game_logs)
    
    # Stat trends
    if len(game_logs) >= 5:
        features['stat_trends'] = {
            'PTS': utils.calculate_trend(game_logs['PTS'].tolist()),
            'REB': utils.calculate_trend(game_logs['REB'].tolist()),
            'AST': utils.calculate_trend(game_logs['AST'].tolist()),
            'FTM': utils.calculate_trend(game_logs['FTM'].tolist()) if 'FTM' in game_logs.columns else 0.0,
            'FG3M': utils.calculate_trend(game_logs['FG3M'].tolist()) if 'FG3M' in game_logs.columns else 0.0,
        }
    else:
        features['stat_trends'] = {'PTS': 0.0, 'REB': 0.0, 'AST': 0.0, 'FTM': 0.0, 'FG3M': 0.0}
    
    # Consistency scores
    if len(game_logs) >= 5:
        features['consistency'] = {
            'PTS': utils.calculate_consistency(game_logs['PTS'].tolist()),
            'REB': utils.calculate_consistency(game_logs['REB'].tolist()),
            'AST': utils.calculate_consistency(game_logs['AST'].tolist()),
            'FTM': utils.calculate_consistency(game_logs['FTM'].tolist()) if 'FTM' in game_logs.columns else 0.0,
            'FG3M': utils.calculate_consistency(game_logs['FG3M'].tolist()) if 'FG3M' in game_logs.columns else 0.0,
        }
    else:
        features['consistency'] = {'PTS': 0.0, 'REB': 0.0, 'AST': 0.0, 'FTM': 0.0, 'FG3M': 0.0}
    
    # Player's season FT Rate (for FTM prediction adjustment)
    if len(game_logs) > 0 and all(col in game_logs.columns for col in ['FTA', 'FGA']):
        total_fta = game_logs['FTA'].sum()
        total_fga = game_logs['FGA'].sum()
        features['player_ft_rate'] = round(total_fta / total_fga * 100, 1) if total_fga > 0 else 0.0
    else:
        features['player_ft_rate'] = 25.0  # Default ~25% FT rate
    
    # Matchup-specific stats (PTS_PAINT, PTS_FB, PTS_2ND_CHANCE)
    # This includes player scoring breakdown and opponent defensive vulnerabilities
    try:
        matchup_features = ms.get_matchup_prediction_features(
            player_id=player_id,
            opponent_team_id=opponent_team_id
        )
        features['matchup'] = matchup_features
    except Exception as e:
        print(f"Error fetching matchup features: {e}")
        features['matchup'] = {
            'player_scoring_breakdown': {
                'pts_paint': 0.0, 'pts_fb': 0.0, 'pts_2nd_chance': 0.0, 'pts_off_tov': 0.0
            },
            'opponent_vulnerabilities': {
                'opp_pts_paint_allowed': 48.0, 'opp_pts_fb_allowed': 12.0, 
                'opp_pts_2nd_chance_allowed': 12.0, 'opp_pts_off_tov_allowed': 15.0
            },
            'league_misc_averages': {
                'pts_paint': 48.0, 'pts_fb': 12.0, 'pts_2nd_chance': 12.0, 'pts_off_tov': 15.0
            },
            'matchup_adjustments': {
                'overall_pts_factor': 1.0
            }
        }
    
    # Positional defense adjustment
    try:
        player_position = get_player_position_from_index(player_id)
        features['player_position'] = player_position
        features['positional_defense'] = pos_def.get_positional_defense_adjustment(
            opponent_abbr=opponent_abbr,
            player_position=player_position
        )
    except Exception as e:
        print(f"Error getting positional defense: {e}")
        features['player_position'] = 'F'
        features['positional_defense'] = {
            'factor': 1.0,
            'rank': 15,
            'vs_league_avg': 0.0,
            'position_group': 'F',
            'opponent': opponent_abbr,
            'description': 'Positional defense data unavailable'
        }
    
    # Player drives tracking data (for FTM and AST predictions)
    try:
        features['drives'] = ds.get_player_drives_stats(player_id)
        
        # Calculate drives adjustment factors
        opp_ft_rate = features['opponent'].get('ft_rate_allowed', 25.0)
        league_ft_rate = features.get('league_avg_ft_rate', 25.0)
        features['drives_adjustments'] = ds.calculate_drives_adjustment_factors(
            player_drives=features['drives'],
            opp_ft_rate_allowed=opp_ft_rate,
            league_avg_ft_rate=league_ft_rate
        )
    except Exception as e:
        print(f"Error getting drives stats: {e}")
        features['drives'] = ds._get_default_player_drives()
        features['drives_adjustments'] = {
            'ftm_drive_factor': 1.0,
            'ast_drive_factor': 1.0,
            'drives_per_game': 5.0,
            'drive_fta_per_game': 1.0,
            'drives_vs_league': 1.0,
            'drive_ast_vs_league': 1.0,
            'drive_description': 'Data unavailable',
            'ast_description': 'Data unavailable',
        }
    
    return features

