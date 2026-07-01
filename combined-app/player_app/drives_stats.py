"""
Drives Stats Module
Fetches and processes player and team drives tracking data from NBA API.
Used for FTM, PTS, and AST prediction adjustments.
"""

import pandas as pd
import streamlit as st
import nba_api.stats.endpoints as endpoints
from typing import Dict, Optional, Tuple

# Current season configuration
CURRENT_SEASON = "2025-26"


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_all_player_drives_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Fetch drives tracking data for all players.
    
    Returns DataFrame with columns:
    - PLAYER_ID, PLAYER_NAME, TEAM_ABBREVIATION
    - DRIVES: Drives per game
    - DRIVE_FGM, DRIVE_FGA, DRIVE_FG_PCT: Field goals from drives
    - DRIVE_FTM, DRIVE_FTA, DRIVE_FT_PCT: Free throws from drives
    - DRIVE_PTS, DRIVE_PTS_PCT: Points from drives
    - DRIVE_AST, DRIVE_AST_PCT: Assists from drives
    - DRIVE_TOV, DRIVE_TOV_PCT: Turnovers from drives
    """
    # Fetch from API
    try:
        drives_df = endpoints.LeagueDashPtStats(
            season=season,
            per_mode_simple='PerGame',
            pt_measure_type='Drives',
            player_or_team='Player'
        ).get_data_frames()[0]
        
        return drives_df
    except Exception as e:
        print(f"Error fetching player drives stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_all_team_drives_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Fetch team-level drives tracking data (offensive).
    Can be used to understand league averages and compare opponents.
    
    Returns DataFrame with columns:
    - TEAM_ID, TEAM_ABBREVIATION, TEAM_NAME
    - DRIVES: Drives per game (offensive)
    - DRIVE_FTM, DRIVE_FTA: Free throws from drives
    - DRIVE_AST: Assists from drives
    - DRIVE_PTS: Points from drives
    """
    # Fetch from API
    try:
        drives_df = endpoints.LeagueDashPtStats(
            season=season,
            per_mode_simple='PerGame',
            pt_measure_type='Drives',
            player_or_team='Team'
        ).get_data_frames()[0]
        
        # Add ranks for each key metric
        drives_df['DRIVES_RANK'] = drives_df['DRIVES'].rank(ascending=False, method='first').astype(int)
        drives_df['DRIVE_FTA_RANK'] = drives_df['DRIVE_FTA'].rank(ascending=False, method='first').astype(int)
        drives_df['DRIVE_AST_RANK'] = drives_df['DRIVE_AST'].rank(ascending=False, method='first').astype(int)
        drives_df['DRIVE_PTS_RANK'] = drives_df['DRIVE_PTS'].rank(ascending=False, method='first').astype(int)
        
        return drives_df
    except Exception as e:
        print(f"Error fetching team drives stats: {e}")
        return pd.DataFrame()


def get_player_drives_stats(player_id: str, drives_df: Optional[pd.DataFrame] = None) -> Dict:
    """
    Get drives stats for a specific player.
    
    Args:
        player_id: NBA API player ID
        drives_df: Optional pre-loaded drives DataFrame
        
    Returns:
        Dict with drives statistics
    """
    if drives_df is None:
        drives_df = get_all_player_drives_stats()
    
    if len(drives_df) == 0:
        return _get_default_player_drives()
    
    player_row = drives_df[drives_df['PLAYER_ID'] == int(player_id)]
    
    if len(player_row) == 0:
        return _get_default_player_drives()
    
    row = player_row.iloc[0]
    
    # Calculate league averages for context
    league_avg_drives = drives_df['DRIVES'].mean()
    league_avg_drive_fta = drives_df['DRIVE_FTA'].mean()
    league_avg_drive_ast = drives_df['DRIVE_AST'].mean()
    
    return {
        'drives_per_game': round(row['DRIVES'], 1),
        'drive_fgm': round(row['DRIVE_FGM'], 1),
        'drive_fga': round(row['DRIVE_FGA'], 1),
        'drive_fg_pct': round(row['DRIVE_FG_PCT'] * 100, 1),
        'drive_ftm': round(row['DRIVE_FTM'], 1),
        'drive_fta': round(row['DRIVE_FTA'], 1),
        'drive_ft_pct': round(row['DRIVE_FT_PCT'] * 100, 1) if row['DRIVE_FTA'] > 0 else 0.0,
        'drive_pts': round(row['DRIVE_PTS'], 1),
        'drive_pts_pct': round(row['DRIVE_PTS_PCT'] * 100, 1),  # % of points from drives
        'drive_ast': round(row['DRIVE_AST'], 1),
        'drive_ast_pct': round(row['DRIVE_AST_PCT'] * 100, 1),  # % of drives that become assists
        'drive_tov': round(row['DRIVE_TOV'], 1),
        'drive_tov_pct': round(row['DRIVE_TOV_PCT'] * 100, 1),
        # League context
        'league_avg_drives': round(league_avg_drives, 1),
        'league_avg_drive_fta': round(league_avg_drive_fta, 1),
        'league_avg_drive_ast': round(league_avg_drive_ast, 1),
        # Player vs league
        'drives_vs_league': round(row['DRIVES'] / league_avg_drives, 2) if league_avg_drives > 0 else 1.0,
        'drive_fta_vs_league': round(row['DRIVE_FTA'] / league_avg_drive_fta, 2) if league_avg_drive_fta > 0 else 1.0,
        'drive_ast_vs_league': round(row['DRIVE_AST'] / league_avg_drive_ast, 2) if league_avg_drive_ast > 0 else 1.0,
    }


def _get_default_player_drives() -> Dict:
    """Return default drives stats when data is unavailable."""
    return {
        'drives_per_game': 5.0,
        'drive_fgm': 1.5,
        'drive_fga': 3.0,
        'drive_fg_pct': 50.0,
        'drive_ftm': 1.0,
        'drive_fta': 1.3,
        'drive_ft_pct': 75.0,
        'drive_pts': 4.0,
        'drive_pts_pct': 25.0,
        'drive_ast': 0.8,
        'drive_ast_pct': 15.0,
        'drive_tov': 0.5,
        'drive_tov_pct': 10.0,
        'league_avg_drives': 5.0,
        'league_avg_drive_fta': 1.3,
        'league_avg_drive_ast': 0.8,
        'drives_vs_league': 1.0,
        'drive_fta_vs_league': 1.0,
        'drive_ast_vs_league': 1.0,
    }


def get_opponent_drives_defense(opponent_team_id: int, team_drives_df: Optional[pd.DataFrame] = None) -> Dict:
    """
    Get opponent's drives defense rating.
    
    Since there's no direct "drives allowed" stat, we use:
    - Opponent's own drives stats as a proxy (teams that drive well often allow drives)
    - Paint points allowed (already in matchup_stats)
    - FT Rate allowed (already in prediction_features)
    
    This function provides context about opponent's defensive tendencies.
    
    Args:
        opponent_team_id: NBA API team ID
        team_drives_df: Optional pre-loaded team drives DataFrame
        
    Returns:
        Dict with opponent drives defense context
    """
    if team_drives_df is None:
        team_drives_df = get_all_team_drives_stats()
    
    if len(team_drives_df) == 0:
        return _get_default_opp_drives_defense()
    
    opp_row = team_drives_df[team_drives_df['TEAM_ID'] == int(opponent_team_id)]
    
    if len(opp_row) == 0:
        return _get_default_opp_drives_defense()
    
    row = opp_row.iloc[0]
    
    # League averages
    league_avg_drives = team_drives_df['DRIVES'].mean()
    league_avg_drive_fta = team_drives_df['DRIVE_FTA'].mean()
    
    return {
        'opp_drives_pg': round(row['DRIVES'], 1),  # Opponent's offensive drives (context)
        'opp_drives_rank': int(row['DRIVES_RANK']),
        'opp_drive_fta_pg': round(row['DRIVE_FTA'], 1),
        'opp_drive_fta_rank': int(row['DRIVE_FTA_RANK']),
        'league_avg_drives': round(league_avg_drives, 1),
        'league_avg_drive_fta': round(league_avg_drive_fta, 1),
    }


def _get_default_opp_drives_defense() -> Dict:
    """Return default opponent drives defense when data is unavailable."""
    return {
        'opp_drives_pg': 45.0,
        'opp_drives_rank': 15,
        'opp_drive_fta_pg': 6.0,
        'opp_drive_fta_rank': 15,
        'league_avg_drives': 45.0,
        'league_avg_drive_fta': 6.0,
    }


def calculate_drives_adjustment_factors(
    player_drives: Dict,
    opp_ft_rate_allowed: float,
    league_avg_ft_rate: float
) -> Dict:
    """
    Calculate adjustment factors based on drives data.
    
    Returns:
        Dict with adjustment factors for FTM, AST, and context descriptions
    """
    # Player's reliance on drives for FTM
    # If player gets most FTA from drives, opponent FT Rate matters more
    drive_fta_per_game = player_drives.get('drive_fta', 1.0)
    drives_vs_league = player_drives.get('drives_vs_league', 1.0)
    drive_ast_vs_league = player_drives.get('drive_ast_vs_league', 1.0)
    
    # FTM adjustment based on drives volume
    # High-volume drivers benefit more from opponent FT Rate allowed
    # Low-volume drivers (bigs, shooters) get FTs differently - reduce adjustment
    if drives_vs_league >= 1.5:
        ftm_drive_factor = 1.10  # Elite driver - boost FTM adjustment
        drive_description = "Elite driver"
        drive_tier = "elite"
    elif drives_vs_league >= 1.2:
        ftm_drive_factor = 1.05  # Above avg driver
        drive_description = "High-volume driver"
        drive_tier = "high"
    elif drives_vs_league >= 0.8:
        ftm_drive_factor = 1.0   # Average driver
        drive_description = "Average driver"
        drive_tier = "average"
    elif drives_vs_league >= 0.5:
        ftm_drive_factor = 0.92  # Low driver - reduce FTM adjustment
        drive_description = "Low-volume driver"
        drive_tier = "low"
    else:
        ftm_drive_factor = 0.85  # Very low driver (stretch bigs, shooters) - significant reduction
        drive_description = "Non-driver (shooter/stretch big)"
        drive_tier = "very_low"
    
    # AST adjustment based on drive-and-kick tendency
    if drive_ast_vs_league >= 1.5:
        ast_drive_factor = 1.05  # Gets lots of AST from drives
        ast_description = "Elite drive-and-kick"
    elif drive_ast_vs_league >= 1.2:
        ast_drive_factor = 1.03
        ast_description = "Good drive-and-kick"
    else:
        ast_drive_factor = 1.0
        ast_description = "Average drive-and-kick"
    
    return {
        'ftm_drive_factor': ftm_drive_factor,
        'ast_drive_factor': ast_drive_factor,
        'drives_per_game': player_drives.get('drives_per_game', 5.0),
        'drive_fta_per_game': drive_fta_per_game,
        'drives_vs_league': drives_vs_league,
        'drive_ast_vs_league': drive_ast_vs_league,
        'drive_description': drive_description,
        'ast_description': ast_description,
        'drive_tier': drive_tier,
    }

