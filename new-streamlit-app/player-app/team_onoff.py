"""
Team On/Off Court Module
Functions to fetch and process team player on/off court statistics from NBA API.
"""

import pandas as pd
import numpy as np
import streamlit as st
import nba_api.stats.endpoints as endpoints
import time
import json
from typing import Dict, Optional, Tuple
from requests.exceptions import ReadTimeout, RequestException

# Supabase imports removed - using Streamlit cache instead

# Current season configuration
CURRENT_SEASON = "2025-26"
LEAGUE_ID = "00"

# Minimum minutes threshold for meaningful on/off data
MIN_MINUTES_THRESHOLD = 100


@st.cache_data(ttl=3600, show_spinner=False)
def get_team_onoff_summary(team_id: int, season: str = CURRENT_SEASON, 
                           max_retries: int = 3, timeout: int = 60) -> pd.DataFrame:
    """
    Fetch team player on/off court summary data from NBA API.
    
    Args:
        team_id: Team ID (integer)
        season: Season string (defaults to CURRENT_SEASON)
        max_retries: Number of retry attempts
        timeout: Request timeout in seconds
    
    Returns:
        DataFrame with on/off court data for all players on the team, or empty DataFrame on error
    """
    
    # Fetch from API
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
            
            # The NBA API returns dataframes in a specific order, but we need to verify which is which
            # by checking which has higher average minutes (ON_COURT should have more minutes)
            temp_df1 = data_frames[1].copy()
            temp_df2 = data_frames[2].copy()
            
            # Find MIN column in each dataframe
            min_col1 = None
            min_col2 = None
            for col in temp_df1.columns:
                if 'MIN' in col.upper() and 'RANK' not in col.upper():
                    min_col1 = col
                    break
            for col in temp_df2.columns:
                if 'MIN' in col.upper() and 'RANK' not in col.upper():
                    min_col2 = col
                    break
            
            avg_min1 = temp_df1[min_col1].mean() if min_col1 else 0
            avg_min2 = temp_df2[min_col2].mean() if min_col2 else 0
            
            # Assign based on which has higher minutes
            # IMPORTANT: Based on NBA API structure, data_frames[1] is PlayersOffCourt, data_frames[2] is PlayersOnCourt
            # But we verify by checking minutes: ON_COURT should have player's actual minutes (varies by player role)
            # OFF_COURT should have team minutes when player is off (typically higher for role players)
            # However, the API might return them in reverse order, so we check and swap if needed
            # For most role players: MIN_ON_COURT < MIN_OFF_COURT
            # For star players: MIN_ON_COURT > MIN_OFF_COURT
            # Since we can't rely on minutes alone, let's try the opposite assignment
            if avg_min1 > avg_min2:
                # df1 has higher minutes - try assigning as ON_COURT (for stars) or OFF_COURT (for role players)
                # Based on user feedback, let's try: df1 = ON_COURT, df2 = OFF_COURT
                players_on_court_df = temp_df1
                players_off_court_df = temp_df2
            else:
                # df2 has higher minutes - try assigning as ON_COURT
                players_on_court_df = temp_df2
                players_off_court_df = temp_df1
            
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
    # Minutes columns - prioritize exact matches, avoid RANK columns
    min_on_col = None
    min_off_col = None
    
    # First, try exact matches
    if 'MIN_ON_COURT' in df.columns:
        min_on_col = 'MIN_ON_COURT'
    if 'MIN_OFF_COURT' in df.columns:
        min_off_col = 'MIN_OFF_COURT'
    
    # If exact matches not found, search for columns (but exclude RANK columns)
    if not min_on_col:
        for col in df.columns:
            col_upper = col.upper()
            if 'MIN' in col_upper and ('ON' in col_upper or 'ONCOURT' in col_upper) and 'RANK' not in col_upper:
                min_on_col = col
                break
    
    if not min_off_col:
        for col in df.columns:
            col_upper = col.upper()
            if 'MIN' in col_upper and ('OFF' in col_upper or 'OFFCOURT' in col_upper) and 'RANK' not in col_upper:
                min_off_col = col
                break
    
    # Filter players with meaningful minutes
    if min_on_col:
        rows_before_filter = len(df)
        df = df[df[min_on_col] >= min_minutes].copy()
    else:
    
    # Net Rating columns - prioritize exact matches, avoid RANK columns
    net_on_col = None
    net_off_col = None
    
    # First, try exact matches
    if 'NET_RATING_ON_COURT' in df.columns:
        net_on_col = 'NET_RATING_ON_COURT'
    if 'NET_RATING_OFF_COURT' in df.columns:
        net_off_col = 'NET_RATING_OFF_COURT'
    
    # If exact matches not found, search (but exclude RANK columns)
    if not net_on_col:
        for col in df.columns:
            col_upper = col.upper()
            if ('NET' in col_upper or 'NETRTG' in col_upper) and ('ON' in col_upper or 'ONCOURT' in col_upper) and 'RANK' not in col_upper:
                net_on_col = col
                break
    
    if not net_off_col:
        for col in df.columns:
            col_upper = col.upper()
            if ('NET' in col_upper or 'NETRTG' in col_upper) and ('OFF' in col_upper or 'OFFCOURT' in col_upper) and 'RANK' not in col_upper:
                net_off_col = col
                break
    
    # Offensive Rating columns - prioritize exact matches, avoid RANK columns
    off_on_col = None
    off_off_col = None
    
    # First, try exact matches
    if 'OFF_RATING_ON_COURT' in df.columns:
        off_on_col = 'OFF_RATING_ON_COURT'
    if 'OFF_RATING_OFF_COURT' in df.columns:
        off_off_col = 'OFF_RATING_OFF_COURT'
    
    # If exact matches not found, search (but exclude RANK columns)
    if not off_on_col:
        for col in df.columns:
            col_upper = col.upper()
            if ('OFF' in col_upper or 'OFFRTG' in col_upper) and ('ON' in col_upper or 'ONCOURT' in col_upper) and 'RATING' in col_upper and 'RANK' not in col_upper:
                off_on_col = col
                break
    
    if not off_off_col:
        for col in df.columns:
            col_upper = col.upper()
            if ('OFF' in col_upper or 'OFFRTG' in col_upper) and ('OFF' in col_upper or 'OFFCOURT' in col_upper) and 'RATING' in col_upper and 'RANK' not in col_upper:
                off_off_col = col
                break
    
    # Defensive Rating columns - prioritize exact matches, avoid RANK columns
    def_on_col = None
    def_off_col = None
    
    # First, try exact matches
    if 'DEF_RATING_ON_COURT' in df.columns:
        def_on_col = 'DEF_RATING_ON_COURT'
    if 'DEF_RATING_OFF_COURT' in df.columns:
        def_off_col = 'DEF_RATING_OFF_COURT'
    
    # If exact matches not found, search (but exclude RANK columns)
    if not def_on_col:
        for col in df.columns:
            col_upper = col.upper()
            if ('DEF' in col_upper or 'DEFRTG' in col_upper) and ('ON' in col_upper or 'ONCOURT' in col_upper) and 'RATING' in col_upper and 'RANK' not in col_upper:
                def_on_col = col
                break
    
    if not def_off_col:
        for col in df.columns:
            col_upper = col.upper()
            if ('DEF' in col_upper or 'DEFRTG' in col_upper) and ('OFF' in col_upper or 'OFFCOURT' in col_upper) and 'RATING' in col_upper and 'RANK' not in col_upper:
                def_off_col = col
                break
    
    # Plus/Minus columns - prioritize exact matches, avoid RANK columns
    pm_on_col = None
    pm_off_col = None
    
    # First, try exact matches
    if 'PLUS_MINUS_ON_COURT' in df.columns:
        pm_on_col = 'PLUS_MINUS_ON_COURT'
    if 'PLUS_MINUS_OFF_COURT' in df.columns:
        pm_off_col = 'PLUS_MINUS_OFF_COURT'
    
    # If exact matches not found, search (but exclude RANK columns)
    if not pm_on_col:
        for col in df.columns:
            col_upper = col.upper()
            if ('PLUS' in col_upper or 'PM' in col_upper) and ('ON' in col_upper or 'ONCOURT' in col_upper) and 'RANK' not in col_upper:
                pm_on_col = col
                break
    
    if not pm_off_col:
        for col in df.columns:
            col_upper = col.upper()
            if ('PLUS' in col_upper or 'PM' in col_upper) and ('OFF' in col_upper or 'OFFCOURT' in col_upper) and 'RANK' not in col_upper:
                pm_off_col = col
                break
    
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
        # For defensive rating, calculate as ON - OFF (consistent with other metrics)
        # Lower defensive rating is better, so positive diff = better defense when on
        df['DEF_RTG_DIFF'] = df[def_on_col] - df[def_off_col]
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
    try:
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
            
            # Check which columns exist in players_df before selecting
            available_cols = []
            required_cols = ['PERSON_ID_INT', 'PLAYER_FIRST_NAME', 'PLAYER_LAST_NAME', 'HEADSHOT']
            for col in required_cols:
                if col in players_df.columns:
                    available_cols.append(col)
            
            # Merge with only available columns
            if len(available_cols) > 0:
                try:
                    # Double-check all columns exist before selecting - create a copy to avoid any reference issues
                    players_df_copy = players_df.copy()
                    final_cols = [col for col in available_cols if col in players_df_copy.columns]
                    
                    if len(final_cols) > 0:
                        df = df.merge(
                            players_df_copy[final_cols],
                            left_on='PLAYER_ID_INT',
                            right_on='PERSON_ID_INT',
                            how='left'
                        )
                except (KeyError, IndexError, ValueError) as e:
                    # Continue without player info merge if it fails
                    pass
            
            # Create full name if columns exist
            if 'PLAYER_FIRST_NAME' in df.columns and 'PLAYER_LAST_NAME' in df.columns:
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
    
    except Exception as e:
        # Return empty DataFrame on any error
        return pd.DataFrame()


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

