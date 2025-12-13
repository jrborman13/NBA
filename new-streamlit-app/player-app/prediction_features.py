"""
Prediction Features Module
Functions to gather features for player stat predictions.
Kept separate from main codebase for modularity.
"""

import pandas as pd
import numpy as np
import nba_api.stats.endpoints as endpoints
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date
import prediction_utils as utils

# Current season configuration
CURRENT_SEASON = "2024-25"
LEAGUE_ID = "00"


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


def get_player_rolling_averages(game_logs: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """
    Calculate rolling averages from game logs.
    
    Returns:
        Dict with L3, L5, L10, Season averages for key stats
    """
    stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M', 'FTM', 'MIN', 'TOV']
    result = {}
    
    for window, label in [(3, 'L3'), (5, 'L5'), (10, 'L10'), (len(game_logs), 'Season')]:
        subset = game_logs.head(window)
        if len(subset) > 0:
            result[label] = {stat: round(subset[stat].mean(), 1) for stat in stats if stat in subset.columns}
            # Add PRA
            if all(s in subset.columns for s in ['PTS', 'REB', 'AST']):
                result[label]['PRA'] = round(subset['PTS'].mean() + subset['REB'].mean() + subset['AST'].mean(), 1)
    
    return result


def get_player_home_away_splits(game_logs: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """
    Calculate home vs away splits.
    
    Returns:
        Dict with 'home' and 'away' averages
    """
    stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'MIN']
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
    stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'MIN', 'FG3M']
    
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
    
    return result


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


def calculate_days_rest(game_logs: pd.DataFrame, game_date: str) -> int:
    """
    Calculate days of rest before a game.
    """
    if 'GAME_DATE' not in game_logs.columns or len(game_logs) == 0:
        return 3  # Default
    
    game_dates = game_logs['GAME_DATE'].dt.strftime('%Y-%m-%d').tolist()
    return utils.calculate_days_rest(game_dates, game_date)


def get_all_prediction_features(
    player_id: str,
    opponent_team_id: int,
    opponent_abbr: str,
    game_date: str,
    is_home: bool
) -> Dict:
    """
    Gather all features needed for prediction.
    
    Args:
        player_id: NBA API player ID
        opponent_team_id: Opponent's team ID
        opponent_abbr: Opponent's team abbreviation (e.g., 'LAL')
        game_date: Date of the game (YYYY-MM-DD)
        is_home: Whether player's team is playing at home
    
    Returns:
        Dict with all prediction features
    """
    features = {}
    
    # Get player game logs
    game_logs = get_player_game_logs(player_id)
    
    # Player rolling averages
    features['rolling_avgs'] = get_player_rolling_averages(game_logs)
    
    # Home/Away splits
    features['home_away_splits'] = get_player_home_away_splits(game_logs)
    features['is_home'] = is_home
    
    # Historical vs opponent
    features['vs_opponent'] = get_player_vs_opponent_history(game_logs, opponent_abbr)
    
    # Rest days
    features['days_rest'] = calculate_days_rest(game_logs, game_date)
    features['is_back_to_back'] = utils.is_back_to_back(features['days_rest'])
    
    # Opponent stats
    features['opponent'] = {
        'team_id': opponent_team_id,
        'abbr': opponent_abbr,
        'pace': get_team_pace(opponent_team_id),
        'def_rating': get_team_defensive_rating(opponent_team_id),
        'def_rating_L5': get_team_defensive_rating_last_n(opponent_team_id, 5),
    }
    
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
        }
    else:
        features['stat_trends'] = {'PTS': 0.0, 'REB': 0.0, 'AST': 0.0}
    
    # Consistency scores
    if len(game_logs) >= 5:
        features['consistency'] = {
            'PTS': utils.calculate_consistency(game_logs['PTS'].tolist()),
            'REB': utils.calculate_consistency(game_logs['REB'].tolist()),
            'AST': utils.calculate_consistency(game_logs['AST'].tolist()),
        }
    else:
        features['consistency'] = {'PTS': 0.0, 'REB': 0.0, 'AST': 0.0}
    
    return features

