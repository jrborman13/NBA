"""
Team On/Off Court Module
Functions to fetch and process team player on/off court statistics from NBA API.
"""

import pandas as pd
import numpy as np
import streamlit as st
import nba_api.stats.endpoints as endpoints
import time
from typing import Dict, Optional, Tuple
from requests.exceptions import ReadTimeout, RequestException

try:
    import supabase_cache as scache
except ImportError:
    scache = None

# Current season configuration
CURRENT_SEASON = "2025-26"
LEAGUE_ID = "00"

# Minimum minutes threshold for meaningful on/off data
MIN_MINUTES_THRESHOLD = 100


# Removed @st.cache_data - using Supabase cache instead
def get_team_onoff_summary(team_id: int, season: str = CURRENT_SEASON, 
                           max_retries: int = 3, timeout: int = 60) -> pd.DataFrame:
    """
    Fetch team player on/off court summary data from NBA API.
    Uses Supabase cache when available.
    
    Args:
        team_id: Team ID (integer)
        season: Season string (defaults to CURRENT_SEASON)
        max_retries: Number of retry attempts
        timeout: Request timeout in seconds
    
    Returns:
        DataFrame with on/off court data for all players on the team, or empty DataFrame on error
    """
    # Try database first (populated by scheduled Edge Functions)
    try:
        import supabase_data_reader as db_reader
        if db_reader is not None:
            db_data = db_reader.get_team_onoff_from_db(season, team_id)
            if db_data is not None and len(db_data) > 0:
                print(f"[DB READ] Team on/off data from database for team {team_id}: {len(db_data)} players")
                return db_data
    except Exception as e:
        print(f"Error reading team on/off from database: {e}, falling back to API")
        db_reader = None
    
    # Try Supabase cache as fallback
    cache_key = f"team_onoff_{team_id}"
    if scache is not None:
        try:
            cached_data = scache.get_cached_bulk_data(cache_key, season, ttl_hours=1)
            if cached_data is not None:
                return cached_data
        except Exception as e:
            print(f"Error fetching cached on/off data: {e}, falling back to API call")
    
    # Database and cache miss - fetch from API (safety net)
    for attempt in range(max_retries):
        try:
            endpoint = endpoints.TeamPlayerOnOffDetails(
                team_id=team_id,
                season=season,
                season_type_all_star='Regular Season',
                per_mode_detailed='Totals',
                measure_type_detailed_defense='Advanced',  # Use Advanced to get rating columns
                league_id_nullable='00',
                timeout=timeout
            )
            
            # Get all dataframes from the endpoint
            data_frames = endpoint.get_data_frames()
            
            # Index 0: OverallTeamPlayerOnOffDetails (team-level, not player-level)
            # Index 1: PlayersOffCourtTeamPlayerOnOffDetails (player stats when OFF court)
            # Index 2: PlayersOnCourtTeamPlayerOnOffDetails (player stats when ON court)
            
            if len(data_frames) < 3:
                return pd.DataFrame()
            
            players_off_court_df = data_frames[1].copy()  # PlayersOffCourtTeamPlayerOnOffDetails
            players_on_court_df = data_frames[2].copy()  # PlayersOnCourtTeamPlayerOnOffDetails
            
            if len(players_off_court_df) == 0 or len(players_on_court_df) == 0:
                return pd.DataFrame()
            
            # Merge on VS_PLAYER_ID (the player ID column)
            # First, prepare columns for merging - rename columns with suffixes
            on_cols = {col: f"{col}_ON_COURT" for col in players_on_court_df.columns 
                      if col not in ['VS_PLAYER_ID', 'VS_PLAYER_NAME', 'TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME', 'COURT_STATUS']}
            off_cols = {col: f"{col}_OFF_COURT" for col in players_off_court_df.columns 
                       if col not in ['VS_PLAYER_ID', 'VS_PLAYER_NAME', 'TEAM_ID', 'TEAM_ABBREVIATION', 'TEAM_NAME', 'COURT_STATUS']}
            
            # Rename columns
            players_on_court_df = players_on_court_df.rename(columns=on_cols)
            players_off_court_df = players_off_court_df.rename(columns=off_cols)
            
            # Merge on VS_PLAYER_ID
            merged_df = pd.merge(
                players_on_court_df,
                players_off_court_df,
                on='VS_PLAYER_ID',
                how='inner',
                suffixes=('', '_y')
            )
            
            # Clean up duplicate columns from merge
            if 'VS_PLAYER_NAME_y' in merged_df.columns:
                merged_df = merged_df.drop(columns=['VS_PLAYER_NAME_y'])
            if 'TEAM_ID_y' in merged_df.columns:
                merged_df = merged_df.drop(columns=['TEAM_ID_y'])
            if 'TEAM_ABBREVIATION_y' in merged_df.columns:
                merged_df = merged_df.drop(columns=['TEAM_ABBREVIATION_y'])
            if 'TEAM_NAME_y' in merged_df.columns:
                merged_df = merged_df.drop(columns=['TEAM_NAME_y'])
            
            # Rename VS_PLAYER_ID to PLAYER_ID for consistency
            if 'VS_PLAYER_ID' in merged_df.columns:
                merged_df = merged_df.rename(columns={'VS_PLAYER_ID': 'PLAYER_ID'})
            
            # Store in Supabase cache
            if scache is not None and len(merged_df) > 0:
                try:
                    scache.set_cached_bulk_data(cache_key, season, merged_df, ttl_hours=1)
                except Exception as e:
                    print(f"Error storing on/off data in cache: {e}")
            
            if len(merged_df) > 0:
                return merged_df
            else:
                return pd.DataFrame()
                
        except (ReadTimeout, RequestException) as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
                continue
            else:
                print(f"Error fetching team on/off data for team {team_id}: {str(e)}")
                return pd.DataFrame()
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                time.sleep(wait_time)
                continue
            else:
                print(f"Unexpected error fetching team on/off data for team {team_id}: {str(e)}")
                return pd.DataFrame()
    
    return pd.DataFrame()


def process_onoff_data(onoff_df: pd.DataFrame, min_minutes: int = MIN_MINUTES_THRESHOLD) -> pd.DataFrame:
    """
    Process raw on/off court data to extract key metrics and calculate differentials.
    
    Args:
        onoff_df: Raw DataFrame from get_team_onoff_summary()
        min_minutes: Minimum minutes on court to include player (default: 100)
    
    Returns:
        Processed DataFrame with calculated metrics and differentials
    """
    if onoff_df is None or len(onoff_df) == 0:
        return pd.DataFrame()
    
    # Create a copy to avoid modifying original
    df = onoff_df.copy()
    
    # Find column names (handle different naming conventions)
    # Minutes columns
    min_on_col = None
    min_off_col = None
    for col in df.columns:
        col_upper = col.upper()
        if 'MIN' in col_upper and ('ON' in col_upper or 'ONCOURT' in col_upper):
            min_on_col = col
        elif 'MIN' in col_upper and ('OFF' in col_upper or 'OFFCOURT' in col_upper):
            min_off_col = col
    
    # Filter players with meaningful minutes
    if min_on_col:
        df = df[df[min_on_col] >= min_minutes].copy()
    
    # Net Rating columns
    net_on_col = None
    net_off_col = None
    for col in df.columns:
        col_upper = col.upper()
        if ('NET' in col_upper or 'NETRTG' in col_upper) and ('ON' in col_upper or 'ONCOURT' in col_upper):
            net_on_col = col
        elif ('NET' in col_upper or 'NETRTG' in col_upper) and ('OFF' in col_upper or 'OFFCOURT' in col_upper):
            net_off_col = col
    
    # Offensive Rating columns
    off_on_col = None
    off_off_col = None
    for col in df.columns:
        col_upper = col.upper()
        if ('OFF' in col_upper or 'OFFRTG' in col_upper) and ('ON' in col_upper or 'ONCOURT' in col_upper) and 'RATING' in col_upper:
            off_on_col = col
        elif ('OFF' in col_upper or 'OFFRTG' in col_upper) and ('OFF' in col_upper or 'OFFCOURT' in col_upper) and 'RATING' in col_upper:
            off_off_col = col
    
    # Defensive Rating columns
    def_on_col = None
    def_off_col = None
    for col in df.columns:
        col_upper = col.upper()
        if ('DEF' in col_upper or 'DEFRTG' in col_upper) and ('ON' in col_upper or 'ONCOURT' in col_upper) and 'RATING' in col_upper:
            def_on_col = col
        elif ('DEF' in col_upper or 'DEFRTG' in col_upper) and ('OFF' in col_upper or 'OFFCOURT' in col_upper) and 'RATING' in col_upper:
            def_off_col = col
    
    # Plus/Minus columns
    pm_on_col = None
    pm_off_col = None
    for col in df.columns:
        col_upper = col.upper()
        if ('PLUS' in col_upper or 'PM' in col_upper) and ('ON' in col_upper or 'ONCOURT' in col_upper):
            pm_on_col = col
        elif ('PLUS' in col_upper or 'PM' in col_upper) and ('OFF' in col_upper or 'OFFCOURT' in col_upper):
            pm_off_col = col
    
    # Calculate differentials
    if net_on_col and net_off_col:
        df['NET_RTG_DIFF'] = df[net_on_col] - df[net_off_col]
        # Store original column names for display
        df['NET_RATING_ON_COURT'] = df[net_on_col]
        df['NET_RATING_OFF_COURT'] = df[net_off_col]
    
    if off_on_col and off_off_col:
        df['OFF_RTG_DIFF'] = df[off_on_col] - df[off_off_col]
        df['OFF_RATING_ON_COURT'] = df[off_on_col]
        df['OFF_RATING_OFF_COURT'] = df[off_off_col]
    
    if def_on_col and def_off_col:
        # For defensive rating, calculate as OFF - ON (positive = better defense when on)
        df['DEF_RTG_DIFF'] = df[def_off_col] - df[def_on_col]
        df['DEF_RATING_ON_COURT'] = df[def_on_col]
        df['DEF_RATING_OFF_COURT'] = df[def_off_col]
    
    if pm_on_col and pm_off_col:
        df['PLUS_MINUS_DIFF'] = df[pm_on_col] - df[pm_off_col]
        df['PLUS_MINUS_ON_COURT'] = df[pm_on_col]
        df['PLUS_MINUS_OFF_COURT'] = df[pm_off_col]
    
    # Store minutes columns with standard names
    if min_on_col:
        df['MIN_ON_COURT'] = df[min_on_col]
    if min_off_col:
        df['MIN_OFF_COURT'] = df[min_off_col]
    
    return df


def format_onoff_display_data(processed_df: pd.DataFrame, players_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Format processed on/off data for display in Streamlit, including player names and headshots.
    
    Args:
        processed_df: Processed DataFrame from process_onoff_data()
        players_df: Optional DataFrame with player info (from PlayerIndex) for names and headshots
    
    Returns:
        Formatted DataFrame ready for display
    """
    if processed_df is None or len(processed_df) == 0:
        return pd.DataFrame()
    
    df = processed_df.copy()
    
    # Add player names and headshots if players_df is provided
    if players_df is not None and len(players_df) > 0:
        # Merge player info
        if 'PLAYER_ID' in df.columns and 'PERSON_ID' in players_df.columns:
            # Convert IDs to same type for merging
            df['PLAYER_ID_INT'] = df['PLAYER_ID'].astype(int)
            players_df['PERSON_ID_INT'] = players_df['PERSON_ID'].astype(int)
            
            # Merge
            df = df.merge(
                players_df[['PERSON_ID_INT', 'PLAYER_FIRST_NAME', 'PLAYER_LAST_NAME', 'HEADSHOT']],
                left_on='PLAYER_ID_INT',
                right_on='PERSON_ID_INT',
                how='left'
            )
            
            # Create full name
            df['PLAYER_NAME'] = df.apply(
                lambda row: f"{row.get('PLAYER_FIRST_NAME', '')} {row.get('PLAYER_LAST_NAME', '')}".strip()
                if pd.notna(row.get('PLAYER_FIRST_NAME')) else '',
                axis=1
            )
            
            # Rename HEADSHOT to headshot for consistency
            if 'HEADSHOT' in df.columns:
                df['headshot'] = df['HEADSHOT']
    
    # Select and order columns for display
    display_cols = []
    
    # Player info columns
    if 'headshot' in df.columns:
        display_cols.append('headshot')
    if 'PLAYER_NAME' in df.columns:
        display_cols.append('PLAYER_NAME')
    elif 'PLAYER' in df.columns:
        display_cols.append('PLAYER')
    
    # Minutes columns
    if 'MIN_ON_COURT' in df.columns:
        display_cols.append('MIN_ON_COURT')
    if 'MIN_OFF_COURT' in df.columns:
        display_cols.append('MIN_OFF_COURT')
    
    # Net Rating columns
    if 'NET_RATING_ON_COURT' in df.columns:
        display_cols.append('NET_RATING_ON_COURT')
    if 'NET_RATING_OFF_COURT' in df.columns:
        display_cols.append('NET_RATING_OFF_COURT')
    if 'NET_RTG_DIFF' in df.columns:
        display_cols.append('NET_RTG_DIFF')
    
    # Offensive Rating columns
    if 'OFF_RATING_ON_COURT' in df.columns:
        display_cols.append('OFF_RATING_ON_COURT')
    if 'OFF_RATING_OFF_COURT' in df.columns:
        display_cols.append('OFF_RATING_OFF_COURT')
    if 'OFF_RTG_DIFF' in df.columns:
        display_cols.append('OFF_RTG_DIFF')
    
    # Defensive Rating columns
    if 'DEF_RATING_ON_COURT' in df.columns:
        display_cols.append('DEF_RATING_ON_COURT')
    if 'DEF_RATING_OFF_COURT' in df.columns:
        display_cols.append('DEF_RATING_OFF_COURT')
    if 'DEF_RTG_DIFF' in df.columns:
        display_cols.append('DEF_RTG_DIFF')
    
    # Plus/Minus columns
    if 'PLUS_MINUS_ON_COURT' in df.columns:
        display_cols.append('PLUS_MINUS_ON_COURT')
    if 'PLUS_MINUS_OFF_COURT' in df.columns:
        display_cols.append('PLUS_MINUS_OFF_COURT')
    if 'PLUS_MINUS_DIFF' in df.columns:
        display_cols.append('PLUS_MINUS_DIFF')
    
    # Filter to only columns that exist
    display_cols = [col for col in display_cols if col in df.columns]
    
    if len(display_cols) == 0:
        return df  # Return original if no display columns found
    
    result_df = df[display_cols].copy()
    
    # Sort by Net Rating differential (best impact first)
    if 'NET_RTG_DIFF' in result_df.columns:
        result_df = result_df.sort_values('NET_RTG_DIFF', ascending=False)
    
    return result_df


def get_team_onoff_formatted(team_id: int, season: str = CURRENT_SEASON, 
                             players_df: Optional[pd.DataFrame] = None,
                             min_minutes: int = MIN_MINUTES_THRESHOLD) -> pd.DataFrame:
    """
    Convenience function to fetch, process, and format on/off court data.
    
    Args:
        team_id: Team ID (integer)
        season: Season string (defaults to CURRENT_SEASON)
        players_df: Optional DataFrame with player info for names and headshots
        min_minutes: Minimum minutes on court to include player
    
    Returns:
        Formatted DataFrame ready for display
    """
    raw_data = get_team_onoff_summary(team_id, season)
    processed_data = process_onoff_data(raw_data, min_minutes)
    formatted_data = format_onoff_display_data(processed_data, players_df)
    return formatted_data

