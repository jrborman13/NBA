"""
Matchup Stats Module
Provides player-level misc stats (PTS_PAINT, PTS_FB, PTS_2ND_CHANCE) and
opponent defensive stats for matchup-based predictions.
"""

import pandas as pd
import numpy as np
import streamlit as st
import nba_api.stats.endpoints as endpoints
from typing import Dict, Optional, Tuple

# Current season configuration
CURRENT_SEASON = "2025-26"
SEASON_TYPE = "Regular Season"


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_player_misc_stats(season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Get player misc stats including PTS_PAINT, PTS_FB, PTS_2ND_CHANCE.
    
    Uses LeagueDashPlayerStats with measure_type='Misc'.
    
    Returns:
        DataFrame with player misc stats
    """
    try:
        misc_stats = endpoints.LeagueDashPlayerStats(
            measure_type_detailed_defense='Misc',
            per_mode_detailed='PerGame',
            season=season,
            season_type_all_star=SEASON_TYPE
        ).get_data_frames()[0]
        
        # Add rankings (higher is better for scoring stats)
        misc_stats['PTS_PAINT_RANK'] = misc_stats['PTS_PAINT'].rank(ascending=False, method='first').astype(int)
        misc_stats['PTS_FB_RANK'] = misc_stats['PTS_FB'].rank(ascending=False, method='first').astype(int)
        misc_stats['PTS_2ND_CHANCE_RANK'] = misc_stats['PTS_2ND_CHANCE'].rank(ascending=False, method='first').astype(int)
        misc_stats['PTS_OFF_TOV_RANK'] = misc_stats['PTS_OFF_TOV'].rank(ascending=False, method='first').astype(int)
        
        return misc_stats
    except Exception as e:
        print(f"Error fetching player misc stats: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_team_misc_stats(season: str = CURRENT_SEASON) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Get team misc stats (offense and defense) including PITP, FB, 2nd Chance.
    
    Returns:
        Tuple of (team_offense_df, team_defense_df)
        - team_offense_df: What teams SCORE (Points in Paint, Fast Break, 2nd Chance)
        - team_defense_df: What teams ALLOW (Opponent PTS in Paint, FB, 2nd Chance)
    """
    try:
        # Team offensive misc stats
        team_offense = endpoints.LeagueDashTeamStats(
            measure_type_detailed_defense='Misc',
            per_mode_detailed='PerGame',
            season=season,
            season_type_all_star=SEASON_TYPE
        ).get_data_frames()[0]
        
        # Team defensive (opponent) misc stats - what they ALLOW
        team_defense = endpoints.LeagueDashTeamStats(
            measure_type_detailed_defense='Opponent',
            per_mode_detailed='PerGame',
            season=season,
            season_type_all_star=SEASON_TYPE
        ).get_data_frames()[0]
        
        # Add rankings for team offense (higher = better offense)
        team_offense['PTS_PAINT_RANK'] = team_offense['PTS_PAINT'].rank(ascending=False, method='first').astype(int)
        team_offense['PTS_FB_RANK'] = team_offense['PTS_FB'].rank(ascending=False, method='first').astype(int)
        team_offense['PTS_2ND_CHANCE_RANK'] = team_offense['PTS_2ND_CHANCE'].rank(ascending=False, method='first').astype(int)
        team_offense['PTS_OFF_TOV_RANK'] = team_offense['PTS_OFF_TOV'].rank(ascending=False, method='first').astype(int)
        
        # For defensive stats (what teams allow), check what columns exist
        # The Opponent measure type returns opponent stats as OPP_* or just raw stats
        defense_cols = team_defense.columns.tolist()
        
        # Add rankings for team defense (lower = better defense = allows less)
        if 'OPP_PTS_PAINT' in defense_cols:
            team_defense['OPP_PTS_PAINT_RANK'] = team_defense['OPP_PTS_PAINT'].rank(ascending=True, method='first').astype(int)
            team_defense['OPP_PTS_FB_RANK'] = team_defense['OPP_PTS_FB'].rank(ascending=True, method='first').astype(int)
            team_defense['OPP_PTS_2ND_CHANCE_RANK'] = team_defense['OPP_PTS_2ND_CHANCE'].rank(ascending=True, method='first').astype(int)
            team_defense['OPP_PTS_OFF_TOV_RANK'] = team_defense['OPP_PTS_OFF_TOV'].rank(ascending=True, method='first').astype(int)
        elif 'PTS_PAINT' in defense_cols:
            # Some API versions return raw stats without OPP_ prefix
            team_defense['OPP_PTS_PAINT'] = team_defense['PTS_PAINT']
            team_defense['OPP_PTS_FB'] = team_defense['PTS_FB']
            team_defense['OPP_PTS_2ND_CHANCE'] = team_defense['PTS_2ND_CHANCE']
            team_defense['OPP_PTS_OFF_TOV'] = team_defense['PTS_OFF_TOV']
            team_defense['OPP_PTS_PAINT_RANK'] = team_defense['PTS_PAINT'].rank(ascending=True, method='first').astype(int)
            team_defense['OPP_PTS_FB_RANK'] = team_defense['PTS_FB'].rank(ascending=True, method='first').astype(int)
            team_defense['OPP_PTS_2ND_CHANCE_RANK'] = team_defense['PTS_2ND_CHANCE'].rank(ascending=True, method='first').astype(int)
            team_defense['OPP_PTS_OFF_TOV_RANK'] = team_defense['PTS_OFF_TOV'].rank(ascending=True, method='first').astype(int)
        
        return team_offense, team_defense
    except Exception as e:
        print(f"Error fetching team misc stats: {e}")
        return pd.DataFrame(), pd.DataFrame()


def get_player_scoring_breakdown(player_id: str, player_misc_stats: pd.DataFrame = None) -> Dict:
    """
    Get a player's scoring breakdown (paint, fast break, 2nd chance points).
    
    Args:
        player_id: NBA API player ID
        player_misc_stats: Optional pre-loaded misc stats DataFrame
    
    Returns:
        Dict with player's scoring breakdown
    """
    if player_misc_stats is None:
        player_misc_stats = get_player_misc_stats()
    
    if player_misc_stats.empty:
        return {
            'pts_paint': 0.0,
            'pts_paint_rank': 0,
            'pts_fb': 0.0,
            'pts_fb_rank': 0,
            'pts_2nd_chance': 0.0,
            'pts_2nd_chance_rank': 0,
            'pts_off_tov': 0.0,
            'pts_off_tov_rank': 0,
        }
    
    player_row = player_misc_stats[player_misc_stats['PLAYER_ID'] == int(player_id)]
    
    if len(player_row) == 0:
        return {
            'pts_paint': 0.0,
            'pts_paint_rank': 0,
            'pts_fb': 0.0,
            'pts_fb_rank': 0,
            'pts_2nd_chance': 0.0,
            'pts_2nd_chance_rank': 0,
            'pts_off_tov': 0.0,
            'pts_off_tov_rank': 0,
        }
    
    row = player_row.iloc[0]
    
    return {
        'pts_paint': round(float(row.get('PTS_PAINT', 0)), 1),
        'pts_paint_rank': int(row.get('PTS_PAINT_RANK', 0)),
        'pts_fb': round(float(row.get('PTS_FB', 0)), 1),
        'pts_fb_rank': int(row.get('PTS_FB_RANK', 0)),
        'pts_2nd_chance': round(float(row.get('PTS_2ND_CHANCE', 0)), 1),
        'pts_2nd_chance_rank': int(row.get('PTS_2ND_CHANCE_RANK', 0)),
        'pts_off_tov': round(float(row.get('PTS_OFF_TOV', 0)), 1),
        'pts_off_tov_rank': int(row.get('PTS_OFF_TOV_RANK', 0)),
    }


def get_opponent_defensive_vulnerabilities(
    opponent_team_id: int,
    team_defense_stats: pd.DataFrame = None
) -> Dict:
    """
    Get opponent's defensive vulnerabilities (what they allow).
    
    Args:
        opponent_team_id: NBA API team ID
        team_defense_stats: Optional pre-loaded team defense DataFrame
    
    Returns:
        Dict with opponent's defensive stats (higher = worse defense)
    """
    if team_defense_stats is None:
        _, team_defense_stats = get_team_misc_stats()
    
    if team_defense_stats.empty:
        return {
            'opp_pts_paint_allowed': 48.0,  # League average defaults
            'opp_pts_paint_rank': 15,
            'opp_pts_fb_allowed': 12.0,
            'opp_pts_fb_rank': 15,
            'opp_pts_2nd_chance_allowed': 12.0,
            'opp_pts_2nd_chance_rank': 15,
            'opp_pts_off_tov_allowed': 15.0,
            'opp_pts_off_tov_rank': 15,
        }
    
    team_row = team_defense_stats[team_defense_stats['TEAM_ID'] == int(opponent_team_id)]
    
    if len(team_row) == 0:
        return {
            'opp_pts_paint_allowed': 48.0,
            'opp_pts_paint_rank': 15,
            'opp_pts_fb_allowed': 12.0,
            'opp_pts_fb_rank': 15,
            'opp_pts_2nd_chance_allowed': 12.0,
            'opp_pts_2nd_chance_rank': 15,
            'opp_pts_off_tov_allowed': 15.0,
            'opp_pts_off_tov_rank': 15,
        }
    
    row = team_row.iloc[0]
    
    return {
        'opp_pts_paint_allowed': round(float(row.get('OPP_PTS_PAINT', 48.0)), 1),
        'opp_pts_paint_rank': int(row.get('OPP_PTS_PAINT_RANK', 15)),
        'opp_pts_fb_allowed': round(float(row.get('OPP_PTS_FB', 12.0)), 1),
        'opp_pts_fb_rank': int(row.get('OPP_PTS_FB_RANK', 15)),
        'opp_pts_2nd_chance_allowed': round(float(row.get('OPP_PTS_2ND_CHANCE', 12.0)), 1),
        'opp_pts_2nd_chance_rank': int(row.get('OPP_PTS_2ND_CHANCE_RANK', 15)),
        'opp_pts_off_tov_allowed': round(float(row.get('OPP_PTS_OFF_TOV', 15.0)), 1),
        'opp_pts_off_tov_rank': int(row.get('OPP_PTS_OFF_TOV_RANK', 15)),
    }


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_league_misc_averages(season: str = CURRENT_SEASON) -> Dict:
    """
    Get league average misc stats for normalization.
    
    Returns:
        Dict with league averages for misc stats
    """
    try:
        team_offense, team_defense = get_team_misc_stats(season)
        
        if team_offense.empty:
            return {
                'pts_paint': 48.0,
                'pts_fb': 12.0,
                'pts_2nd_chance': 12.0,
                'pts_off_tov': 15.0,
            }
        
        return {
            'pts_paint': round(team_offense['PTS_PAINT'].mean(), 1),
            'pts_fb': round(team_offense['PTS_FB'].mean(), 1),
            'pts_2nd_chance': round(team_offense['PTS_2ND_CHANCE'].mean(), 1),
            'pts_off_tov': round(team_offense['PTS_OFF_TOV'].mean(), 1),
        }
    except Exception as e:
        print(f"Error fetching league misc averages: {e}")
        return {
            'pts_paint': 48.0,
            'pts_fb': 12.0,
            'pts_2nd_chance': 12.0,
            'pts_off_tov': 15.0,
        }


def calculate_matchup_adjustment(
    player_stat: float,
    opponent_allowed: float,
    league_avg: float,
    weight: float = 0.3
) -> float:
    """
    Calculate matchup-based adjustment for a stat.
    
    If opponent allows more than league average, positive adjustment.
    If opponent allows less than league average, negative adjustment.
    
    Args:
        player_stat: Player's average for this stat type
        opponent_allowed: What opponent allows (e.g., PTS_PAINT allowed)
        league_avg: League average for this stat
        weight: How much to weight the adjustment (0.0-1.0)
    
    Returns:
        Adjusted stat value
    """
    if league_avg <= 0:
        return player_stat
    
    # Calculate ratio of opponent allowed vs league average
    # >1.0 = bad defense (allows more)
    # <1.0 = good defense (allows less)
    matchup_ratio = opponent_allowed / league_avg
    
    # Apply adjustment with weight
    # weight=0.3 means 70% player avg, 30% matchup influence
    adjustment = 1.0 + weight * (matchup_ratio - 1.0)
    
    return round(player_stat * adjustment, 1)


def get_matchup_prediction_features(
    player_id: str,
    opponent_team_id: int
) -> Dict:
    """
    Get all matchup-specific features for prediction.
    
    This is the main entry point for getting matchup stats.
    
    Args:
        player_id: NBA API player ID
        opponent_team_id: Opponent's team ID
    
    Returns:
        Dict with all matchup features including:
        - player_scoring_breakdown: Player's misc scoring stats
        - opponent_vulnerabilities: Opponent's defensive weaknesses
        - league_averages: League averages for normalization
        - matchup_adjustments: Pre-calculated matchup adjustments
    """
    # Load all data (cached)
    player_misc_stats = get_player_misc_stats()
    team_offense, team_defense = get_team_misc_stats()
    league_avgs = get_league_misc_averages()
    
    # Get player breakdown
    player_breakdown = get_player_scoring_breakdown(player_id, player_misc_stats)
    
    # Get opponent vulnerabilities
    opp_vulnerabilities = get_opponent_defensive_vulnerabilities(opponent_team_id, team_defense)
    
    # Pre-calculate matchup adjustments
    matchup_adjustments = {
        'pts_paint_adjusted': calculate_matchup_adjustment(
            player_breakdown['pts_paint'],
            opp_vulnerabilities['opp_pts_paint_allowed'],
            league_avgs['pts_paint']
        ),
        'pts_fb_adjusted': calculate_matchup_adjustment(
            player_breakdown['pts_fb'],
            opp_vulnerabilities['opp_pts_fb_allowed'],
            league_avgs['pts_fb']
        ),
        'pts_2nd_chance_adjusted': calculate_matchup_adjustment(
            player_breakdown['pts_2nd_chance'],
            opp_vulnerabilities['opp_pts_2nd_chance_allowed'],
            league_avgs['pts_2nd_chance']
        ),
        'pts_off_tov_adjusted': calculate_matchup_adjustment(
            player_breakdown['pts_off_tov'],
            opp_vulnerabilities['opp_pts_off_tov_allowed'],
            league_avgs['pts_off_tov']
        ),
    }
    
    # Calculate total scoring adjustment factor
    # This can be used to adjust overall PTS prediction
    total_player_misc = (
        player_breakdown['pts_paint'] +
        player_breakdown['pts_fb'] +
        player_breakdown['pts_2nd_chance']
    )
    total_adjusted_misc = (
        matchup_adjustments['pts_paint_adjusted'] +
        matchup_adjustments['pts_fb_adjusted'] +
        matchup_adjustments['pts_2nd_chance_adjusted']
    )
    
    if total_player_misc > 0:
        matchup_adjustments['overall_pts_factor'] = round(total_adjusted_misc / total_player_misc, 3)
    else:
        matchup_adjustments['overall_pts_factor'] = 1.0
    
    return {
        'player_scoring_breakdown': player_breakdown,
        'opponent_vulnerabilities': opp_vulnerabilities,
        'league_misc_averages': league_avgs,
        'matchup_adjustments': matchup_adjustments,
    }


def format_matchup_insight(
    player_breakdown: Dict,
    opp_vulnerabilities: Dict,
    matchup_adjustments: Dict
) -> str:
    """
    Generate human-readable matchup insights.
    
    Returns:
        String with matchup analysis
    """
    insights = []
    
    # Paint scoring insight
    paint_rank_diff = opp_vulnerabilities['opp_pts_paint_rank'] - 15  # vs middle of league
    if paint_rank_diff > 5:
        insights.append(f"🎯 **Paint Advantage**: Opponent allows {opp_vulnerabilities['opp_pts_paint_allowed']} PTS/game in paint (Rank #{opp_vulnerabilities['opp_pts_paint_rank']} worst)")
    elif paint_rank_diff < -5:
        insights.append(f"🛡️ **Paint Tough**: Opponent only allows {opp_vulnerabilities['opp_pts_paint_allowed']} PTS/game in paint (Rank #{opp_vulnerabilities['opp_pts_paint_rank']} best)")
    
    # Fast break insight
    fb_rank_diff = opp_vulnerabilities['opp_pts_fb_rank'] - 15
    if fb_rank_diff > 5:
        insights.append(f"🏃 **Transition Opportunity**: Opponent allows {opp_vulnerabilities['opp_pts_fb_allowed']} fast break PTS/game")
    elif fb_rank_diff < -5:
        insights.append(f"🚫 **Limited Transition**: Opponent limits fast breaks to {opp_vulnerabilities['opp_pts_fb_allowed']} PTS/game")
    
    # 2nd chance insight
    sc_rank_diff = opp_vulnerabilities['opp_pts_2nd_chance_rank'] - 15
    if sc_rank_diff > 5:
        insights.append(f"🔄 **2nd Chance Opportunity**: Opponent allows {opp_vulnerabilities['opp_pts_2nd_chance_allowed']} 2nd chance PTS/game")
    
    # Overall matchup factor
    factor = matchup_adjustments['overall_pts_factor']
    if factor > 1.05:
        insights.append(f"📈 **Overall Matchup Boost**: +{round((factor-1)*100, 1)}% scoring opportunity")
    elif factor < 0.95:
        insights.append(f"📉 **Tough Matchup**: -{round((1-factor)*100, 1)}% scoring expected")
    
    if not insights:
        insights.append("📊 **Neutral Matchup**: No significant advantages or disadvantages")
    
    return "\n".join(insights)

