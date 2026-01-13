"""
Player Synergy Module
Functions to fetch and analyze player offensive playtype performance 
and opponent defensive playtype performance for prediction models.
"""

import pandas as pd
import numpy as np
import streamlit as st
import nba_api.stats.endpoints as endpoints
import time
from typing import Dict, Optional, List
from requests.exceptions import ReadTimeout, RequestException

# Current season configuration
CURRENT_SEASON = "2025-26"
LEAGUE_ID = "00"

# All synergy playtypes
SYNERGY_PLAYTYPES = ['Cut', 'Handoff', 'Isolation', 'Misc', 'OffScreen', 'Postup', 
                     'PRBallHandler', 'PRRollman', 'OffRebound', 'Spotup', 'Transition']


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_synergy_data(player_id: str, playtype: str, season: str = CURRENT_SEASON, 
                           max_retries: int = 3, timeout: int = 60) -> pd.DataFrame:
    """
    Fetch synergy data for a specific player and playtype.
    
    Args:
        player_id: Player ID (string)
        playtype: Play type (e.g., 'Cut', 'Handoff', 'Isolation', etc.)
        season: Season string (defaults to CURRENT_SEASON)
        max_retries: Number of retry attempts
        timeout: Request timeout in seconds
    
    Returns:
        DataFrame with synergy data for the player, or empty DataFrame on error
    """
    for attempt in range(max_retries):
        try:
            synergy_data = endpoints.SynergyPlayTypes(
                league_id=LEAGUE_ID,
                per_mode_simple='Totals',
                season=season,
                season_type_all_star='Regular Season',
                player_or_team_abbreviation='P',  # 'P' for player
                type_grouping_nullable='offensive',
                play_type_nullable=playtype,
                timeout=timeout
            ).get_data_frames()[0]
            
            # Filter for the specific player
            if len(synergy_data) > 0 and 'PLAYER_ID' in synergy_data.columns:
                player_data = synergy_data[synergy_data['PLAYER_ID'] == int(player_id)]
                return player_data
            else:
                return pd.DataFrame()
                
        except (ReadTimeout, RequestException) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
                continue
            else:
                print(f"Error fetching player synergy data for player {player_id}, playtype {playtype}: {str(e)}")
                return pd.DataFrame()
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
                continue
            else:
                print(f"Unexpected error fetching player synergy data for player {player_id}, playtype {playtype}: {str(e)}")
                return pd.DataFrame()
    
    return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_players_offensive_synergy_bulk(season: str = CURRENT_SEASON) -> Dict[str, pd.DataFrame]:
    """
    Fetch ALL players' offensive synergy data for ALL playtypes in bulk.
    Makes only 11 API calls total (one per playtype) instead of 11 per player.
    This is much more efficient when predicting for multiple players.
    
    Args:
        season: Season string (defaults to CURRENT_SEASON)
    
    Returns:
        Dictionary: {playtype: df_with_all_players}
    """
    result = {}
    total_requests = len(SYNERGY_PLAYTYPES)
    current_request = 0
    
    for playtype in SYNERGY_PLAYTYPES:
        current_request += 1
        
        for attempt in range(3):
            try:
                synergy_data = endpoints.SynergyPlayTypes(
                    league_id=LEAGUE_ID,
                    per_mode_simple='Totals',
                    season=season,
                    season_type_all_star='Regular Season',
                    player_or_team_abbreviation='P',  # 'P' for player
                    type_grouping_nullable='offensive',
                    play_type_nullable=playtype,
                    timeout=60
                ).get_data_frames()[0]
                
                result[playtype] = synergy_data
                break
                
            except (ReadTimeout, RequestException) as e:
                if attempt < 2:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Error fetching bulk offensive synergy for playtype {playtype}: {str(e)}")
                    result[playtype] = pd.DataFrame()
                    break
            except Exception as e:
                if attempt < 2:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Unexpected error fetching bulk offensive synergy for playtype {playtype}: {str(e)}")
                    result[playtype] = pd.DataFrame()
                    break
        
        # Add delay between requests to avoid rate limiting (except for last request)
        if current_request < total_requests:
            time.sleep(1.5)
    
    return result


def get_player_offensive_synergy_from_bulk(
    player_id: str,
    bulk_synergy: Dict[str, pd.DataFrame]
) -> Dict[str, pd.DataFrame]:
    """
    Extract a single player's offensive synergy data from bulk results.
    
    Args:
        player_id: Player ID (string)
        bulk_synergy: Dictionary from get_all_players_offensive_synergy_bulk()
    
    Returns:
        Dictionary: {playtype: df} for the specific player
    """
    result = {}
    player_id_int = int(player_id)
    
    for playtype, df in bulk_synergy.items():
        if df is not None and len(df) > 0 and 'PLAYER_ID' in df.columns:
            player_data = df[df['PLAYER_ID'] == player_id_int].copy()
            result[playtype] = player_data
        else:
            result[playtype] = pd.DataFrame()
    
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_player_offensive_synergy(player_id: str, season: str = CURRENT_SEASON) -> Dict[str, pd.DataFrame]:
    """
    Fetch all offensive synergy data for a player (all 11 playtypes).
    
    Args:
        player_id: Player ID (string)
        season: Season string (defaults to CURRENT_SEASON)
    
    Returns:
        Dictionary: {playtype: df}
    """
    result = {}
    total_requests = len(SYNERGY_PLAYTYPES)
    current_request = 0
    
    for playtype in SYNERGY_PLAYTYPES:
        current_request += 1
        df = get_player_synergy_data(player_id, playtype, season)
        result[playtype] = df
        
        # Add delay between requests to avoid rate limiting (except for last request)
        if current_request < total_requests:
            time.sleep(1.5)
    
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def get_opponent_defensive_synergy(team_id: int, season: str = CURRENT_SEASON) -> Dict[str, pd.DataFrame]:
    """
    Fetch all defensive synergy data for an opponent team (all 11 playtypes).
    
    Args:
        team_id: Team ID (integer)
        season: Season string (defaults to CURRENT_SEASON)
    
    Returns:
        Dictionary: {playtype: df}
    """
    result = {}
    total_requests = len(SYNERGY_PLAYTYPES)
    current_request = 0
    
    for playtype in SYNERGY_PLAYTYPES:
        current_request += 1
        
        # Fetch team defensive synergy data
        for attempt in range(3):
            try:
                synergy_data = endpoints.SynergyPlayTypes(
                    league_id=LEAGUE_ID,
                    per_mode_simple='Totals',
                    season=season,
                    season_type_all_star='Regular Season',
                    player_or_team_abbreviation='T',  # 'T' for team
                    type_grouping_nullable='defensive',
                    play_type_nullable=playtype,
                    timeout=60
                ).get_data_frames()[0]
                
                # Filter for the specific team
                if len(synergy_data) > 0 and 'TEAM_ID' in synergy_data.columns:
                    team_data = synergy_data[synergy_data['TEAM_ID'] == team_id]
                    result[playtype] = team_data
                else:
                    result[playtype] = pd.DataFrame()
                break
                
            except (ReadTimeout, RequestException) as e:
                if attempt < 2:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Error fetching opponent defensive synergy for team {team_id}, playtype {playtype}: {str(e)}")
                    result[playtype] = pd.DataFrame()
                    break
            except Exception as e:
                if attempt < 2:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"Unexpected error fetching opponent defensive synergy for team {team_id}, playtype {playtype}: {str(e)}")
                    result[playtype] = pd.DataFrame()
                    break
        
        # Add delay between requests to avoid rate limiting (except for last request)
        if current_request < total_requests:
            time.sleep(1.5)
    
    return result


def extract_playtype_metrics(df: pd.DataFrame, playtype: str) -> Dict:
    """
    Extract key metrics from a synergy dataframe.
    
    Args:
        df: Synergy dataframe (player or team)
        playtype: Play type name
    
    Returns:
        Dictionary with metrics: PPP, POSS_PCT, EFG_PCT, SCORE_POSS_PCT, PTS, POSS
    """
    if df is None or len(df) == 0:
        return {
            'playtype': playtype,
            'PPP': 0.0,
            'POSS_PCT': 0.0,
            'EFG_PCT': 0.0,
            'SCORE_POSS_PCT': 0.0,
            'PTS': 0.0,
            'POSS': 0.0
        }
    
    row = df.iloc[0] if len(df) > 0 else None
    if row is None:
        return {
            'playtype': playtype,
            'PPP': 0.0,
            'POSS_PCT': 0.0,
            'EFG_PCT': 0.0,
            'SCORE_POSS_PCT': 0.0,
            'PTS': 0.0,
            'POSS': 0.0
        }
    
    # Extract metrics
    ppp = row.get('PPP', 0.0)
    poss_pct = row.get('POSS_PCT', 0.0)
    efg_pct_raw = row.get('EFG_PCT', 0.0)
    efg_pct = float(efg_pct_raw) * 100 if efg_pct_raw < 1 else float(efg_pct_raw)
    score_poss_pct_raw = row.get('SCORE_POSS_PCT', 0.0)
    score_poss_pct = float(score_poss_pct_raw) * 100 if score_poss_pct_raw < 1 else float(score_poss_pct_raw)
    pts = row.get('PTS', 0.0)
    poss = row.get('POSS', 0.0)
    
    return {
        'playtype': playtype,
        'PPP': float(ppp) if ppp else 0.0,
        'POSS_PCT': float(poss_pct) if poss_pct else 0.0,
        'EFG_PCT': float(efg_pct) if efg_pct else 0.0,
        'SCORE_POSS_PCT': float(score_poss_pct) if score_poss_pct else 0.0,
        'PTS': float(pts) if pts else 0.0,
        'POSS': float(poss) if poss else 0.0
    }


def get_league_playtype_averages(season: str = CURRENT_SEASON) -> Dict[str, Dict]:
    """
    Get league average metrics for each playtype.
    This is a simplified version - could be enhanced to fetch actual league averages.
    
    Returns:
        Dictionary: {playtype: {PPP: avg, POSS_PCT: avg, ...}}
    """
    # For now, return empty dict - league averages can be calculated from bulk data if needed
    # This is a placeholder that can be enhanced later
    return {}


def calculate_playtype_matchup_factors(
    player_synergy: Dict[str, pd.DataFrame],
    opp_defense: Dict[str, pd.DataFrame],
    league_avgs: Optional[Dict] = None
) -> Dict[str, Dict]:
    """
    Calculate matchup factors by comparing player offensive playtypes vs opponent defensive playtypes.
    
    Args:
        player_synergy: Dict of {playtype: df} for player offensive data
        opp_defense: Dict of {playtype: df} for opponent defensive data
        league_avgs: Optional league averages (currently unused but available for future enhancement)
    
    Returns:
        Dictionary: {playtype: {factor: float, weight: float, ...}}
    """
    matchup_factors = {}
    
    for playtype in SYNERGY_PLAYTYPES:
        player_df = player_synergy.get(playtype, pd.DataFrame())
        opp_df = opp_defense.get(playtype, pd.DataFrame())
        
        player_metrics = extract_playtype_metrics(player_df, playtype)
        opp_metrics = extract_playtype_metrics(opp_df, playtype)
        
        # Skip if player has no data or very low usage (< 2%)
        if player_metrics['POSS_PCT'] < 0.02:
            continue
        
        # Calculate matchup factor
        # Factor > 1.0 = favorable matchup (player PPP > opponent PPP allowed)
        # Factor < 1.0 = unfavorable matchup
        player_ppp = player_metrics['PPP']
        opp_ppp_allowed = opp_metrics['PPP']
        
        if opp_ppp_allowed > 0 and player_ppp > 0:
            # Calculate factor: how much better/worse is player vs opponent's average allowed
            # If player PPP = 1.2 and opponent allows 1.0 PPP, factor = 1.2 (favorable)
            # If player PPP = 0.8 and opponent allows 1.0 PPP, factor = 0.8 (unfavorable)
            matchup_factor = player_ppp / opp_ppp_allowed
        else:
            # Default to neutral if data is missing
            matchup_factor = 1.0
        
        # Weight by player's usage frequency (POSS_PCT)
        weight = player_metrics['POSS_PCT']
        
        matchup_factors[playtype] = {
            'factor': matchup_factor,
            'weight': weight,
            'player_ppp': player_ppp,
            'opp_ppp_allowed': opp_ppp_allowed,
            'player_efg_pct': player_metrics['EFG_PCT'],
            'opp_efg_pct_allowed': opp_metrics['EFG_PCT'],
            'player_score_poss_pct': player_metrics['SCORE_POSS_PCT'],
            'opp_score_poss_pct_allowed': opp_metrics['SCORE_POSS_PCT']
        }
    
    return matchup_factors


def get_stat_adjustments_from_playtypes(playtype_factors: Dict[str, Dict]) -> Dict[str, float]:
    """
    Map playtype matchup factors to stat-specific adjustments.
    
    Args:
        playtype_factors: Dictionary from calculate_playtype_matchup_factors()
    
    Returns:
        Dictionary: {stat: adjustment_factor}
    """
    adjustments = {}
    
    # PTS adjustments: Isolation, Spotup, Transition, Postup, PRBallHandler, PRRollman
    pts_playtypes = ['Isolation', 'Spotup', 'Transition', 'Postup', 'PRBallHandler', 'PRRollman']
    pts_factors = []
    pts_weights = []
    
    for playtype in pts_playtypes:
        if playtype in playtype_factors:
            factor_data = playtype_factors[playtype]
            pts_factors.append(factor_data['factor'])
            pts_weights.append(factor_data['weight'])
    
    if pts_factors and sum(pts_weights) > 0:
        # Weighted average of factors
        pts_adjustment = sum(f * w for f, w in zip(pts_factors, pts_weights)) / sum(pts_weights)
        adjustments['PTS'] = pts_adjustment
    else:
        adjustments['PTS'] = 1.0
    
    # AST adjustments: PRBallHandler, Handoff, Transition
    ast_playtypes = ['PRBallHandler', 'Handoff', 'Transition']
    ast_factors = []
    ast_weights = []
    
    for playtype in ast_playtypes:
        if playtype in playtype_factors:
            factor_data = playtype_factors[playtype]
            ast_factors.append(factor_data['factor'])
            ast_weights.append(factor_data['weight'])
    
    if ast_factors and sum(ast_weights) > 0:
        ast_adjustment = sum(f * w for f, w in zip(ast_factors, ast_weights)) / sum(ast_weights)
        adjustments['AST'] = ast_adjustment
    else:
        adjustments['AST'] = 1.0
    
    # REB adjustments: OffRebound, Postup
    reb_playtypes = ['OffRebound', 'Postup']
    reb_factors = []
    reb_weights = []
    
    for playtype in reb_playtypes:
        if playtype in playtype_factors:
            factor_data = playtype_factors[playtype]
            reb_factors.append(factor_data['factor'])
            reb_weights.append(factor_data['weight'])
    
    if reb_factors and sum(reb_weights) > 0:
        reb_adjustment = sum(f * w for f, w in zip(reb_factors, reb_weights)) / sum(reb_weights)
        adjustments['REB'] = reb_adjustment
    else:
        adjustments['REB'] = 1.0
    
    # FG3M adjustments: Spotup, Transition, OffScreen
    fg3m_playtypes = ['Spotup', 'Transition', 'OffScreen']
    fg3m_factors = []
    fg3m_weights = []
    
    for playtype in fg3m_playtypes:
        if playtype in playtype_factors:
            factor_data = playtype_factors[playtype]
            fg3m_factors.append(factor_data['factor'])
            fg3m_weights.append(factor_data['weight'])
    
    if fg3m_factors and sum(fg3m_weights) > 0:
        fg3m_adjustment = sum(f * w for f, w in zip(fg3m_factors, fg3m_weights)) / sum(fg3m_weights)
        adjustments['FG3M'] = fg3m_adjustment
    else:
        adjustments['FG3M'] = 1.0
    
    return adjustments

