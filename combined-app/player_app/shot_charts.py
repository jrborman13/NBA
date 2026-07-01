"""
Shot Chart Visualization Module
Provides functions to fetch and visualize NBA shot chart data for players and teams.
Version: 1.2 - Fixed heatmap overlay, zone definitions, and spacing issues
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle, Rectangle, Arc, Polygon
import streamlit as st
import nba_api.stats.endpoints as endpoints
from typing import Optional, Tuple, Dict, List
from datetime import datetime, date

# Current season constant
CURRENT_SEASON = "2025-26"


def draw_court(ax=None, color='black', lw=2, outer_lines=False):
    """
    Draw a basketball court on the given matplotlib axes.
    NBA API coordinates: LOC_X and LOC_Y are in inches, with basket at (0, 0).
    Court extends: X from -250 to 250 inches (~-21 to 21 feet), Y from -47.5 to 522.5 inches (~-4 to 43.5 feet)
    
    Args:
        ax: Matplotlib axes object. If None, uses current axes.
        color: Color of the court lines
        lw: Line width
        outer_lines: Whether to draw outer court lines
    
    Returns:
        Matplotlib axes object
    """
    if ax is None:
        ax = plt.gca()
    
    # Convert feet to inches for NBA API coordinate system
    # NBA court: 94 feet long (1128 inches), 50 feet wide (600 inches)
    # Basket at (0, 0), court extends in positive Y direction
    # X: -300 to 300 inches (~-25 to 25 feet)
    # Y: -47.5 to 1080.5 inches (~-4 to 90 feet) for full court, but we'll show half court
    
    # Half court dimensions (in inches)
    court_length = 564  # Half court: 47 feet = 564 inches
    court_width = 600   # 50 feet = 600 inches
    basket_to_baseline = 564  # 47 feet
    
    # Outer court lines (half court view)
    if outer_lines:
        # Baseline
        ax.plot([-court_width/2, court_width/2], [0, 0], color=color, lw=lw)
        # Sidelines
        ax.plot([-court_width/2, -court_width/2], [0, basket_to_baseline], color=color, lw=lw)
        ax.plot([court_width/2, court_width/2], [0, basket_to_baseline], color=color, lw=lw)
        # Top of half court
        ax.plot([-court_width/2, court_width/2], [basket_to_baseline, basket_to_baseline], color=color, lw=lw)
    
    # Free throw line (15 feet = 180 inches from basket)
    ft_line_dist = 180  # 15 feet from basket
    ft_line_width = 192  # 16 feet = 192 inches
    ax.plot([-ft_line_width/2, ft_line_width/2], [ft_line_dist, ft_line_dist], color=color, lw=lw)
    
    # Free throw circle (radius 6 feet = 72 inches, centered on free throw line)
    ft_circle = Circle((0, ft_line_dist), 72, linewidth=lw, color=color, fill=False)
    ax.add_patch(ft_circle)
    
    # Restricted area (radius 4 feet = 48 inches)
    restricted = Circle((0, 0), 48, linewidth=lw, color=color, fill=False)
    ax.add_patch(restricted)
    
    # Paint (rectangular area, 16 feet = 192 inches wide, extends from basket to free throw line)
    paint_width = 192  # 16 feet
    paint_length = 180  # 15 feet from basket to free throw line
    paint = Rectangle((-paint_width/2, 0), paint_width, paint_length, 
                     linewidth=lw, color=color, fill=False)
    ax.add_patch(paint)
    
    # 3-point line
    # Top of arc: 23 feet 9 inches = 23.75 feet = 285 inches from basket
    # Corners: 22 feet = 264 inches from basket
    # Corner lines are 3 feet (36 inches) from the sideline
    three_pt_radius_top = 285  # 23.75 feet = 285 inches (top of arc)
    three_pt_radius_corner = 264  # 22 feet = 264 inches (corners)
    corner_line_offset = 36  # 3 feet = 36 inches from sideline
    
    # Find where the main arc (285") intersects with the corner transition line
    # The corner line is at x = ±(court_width/2 - corner_line_offset) = ±(300 - 36) = ±264 inches
    corner_line_x = court_width / 2 - corner_line_offset  # 264 inches from center
    
    # Find the y-coordinate where the main arc intersects the corner line
    # Using: x^2 + y^2 = r^2, so y = sqrt(r^2 - x^2)
    arc_y_at_corner_line = np.sqrt(max(0, three_pt_radius_top**2 - corner_line_x**2))
    
    # Calculate the angle where the arc meets the corner line (in degrees)
    # For right side: angle = arctan2(y, x) where x > 0, y > 0 gives angle 0-90
    # For left side: angle = 180 - arctan2(y, x) gives angle 90-180
    if corner_line_x > 0 and arc_y_at_corner_line > 0:
        # Right side angle (0 to 90 degrees) - measured from positive x-axis
        right_angle = np.degrees(np.arctan2(arc_y_at_corner_line, corner_line_x))
        # Left side angle (90 to 180 degrees) - symmetric about y-axis
        left_angle = 180 - right_angle
    else:
        right_angle = 0
        left_angle = 180
    
    # Draw the main 3-point arc (only the top portion, above the free throw line)
    # matplotlib Arc draws counterclockwise from theta1 to theta2
    # To draw the top arc from left to right, we need theta1 < theta2
    # But left_angle > right_angle, so we need to go the long way or adjust
    # Actually, we want the arc that goes through the top (90°), so:
    # Go from right_angle up to 90°, then from 90° to left_angle
    # Or equivalently, draw from right_angle to left_angle, but matplotlib will take the shorter path
    # To force the top path, we can draw from right_angle to left_angle + 360, or use two arcs
    
    # Draw arc from right corner to top (90 degrees)
    if right_angle < 90:
        arc_right = Arc((0, 0), three_pt_radius_top*2, three_pt_radius_top*2,
                       theta1=right_angle, theta2=90,
                       linewidth=lw, color=color)
        ax.add_patch(arc_right)
    
    # Draw arc from top (90 degrees) to left corner
    if left_angle > 90:
        arc_left = Arc((0, 0), three_pt_radius_top*2, three_pt_radius_top*2,
                      theta1=90, theta2=left_angle,
                      linewidth=lw, color=color)
        ax.add_patch(arc_left)
    
    # Draw corner 3-point lines (straight lines from baseline, 3 feet from sideline)
    # These extend from the baseline (y=0) up to where they meet the main arc
    corner_line_start_x = corner_line_x  # 264 inches from center (left side)
    corner_line_end_x = corner_line_x
    corner_line_start_y = 0  # Baseline
    corner_line_end_y = arc_y_at_corner_line  # Where it meets the arc
    
    # Left corner line
    ax.plot([-corner_line_end_x, -corner_line_end_x], 
            [corner_line_start_y, corner_line_end_y], color=color, lw=lw)
    # Right corner line
    ax.plot([corner_line_end_x, corner_line_end_x], 
            [corner_line_start_y, corner_line_end_y], color=color, lw=lw)
    
    # Backboard (6 feet = 72 inches wide, 4 feet = 48 inches from baseline)
    backboard_width = 72
    backboard_dist = 48
    ax.plot([-backboard_width/2, backboard_width/2], [-backboard_dist, -backboard_dist], 
            color=color, lw=lw*2)
    
    # Rim (18 inches diameter, radius = 9 inches)
    rim = Circle((0, 0), 9, linewidth=lw, color=color, fill=False)
    ax.add_patch(rim)
    
    # Set axis limits (in inches, matching NBA API coordinate system)
    # Adjust limits to show full court properly
    ax.set_xlim(-320, 320)  # Slightly wider than court width (600/2 = 300)
    ax.set_ylim(-50, 580)  # Show baseline to just past free throw line
    ax.set_aspect('equal')
    ax.axis('off')
    
    return ax


@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_player_shot_data(player_id: str, season: str = CURRENT_SEASON, 
                        season_type: str = 'Regular Season',
                        game_id: Optional[str] = None,
                        team_id: Optional[int] = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Fetch shot chart data for a player.
    
    Args:
        player_id: Player ID as string
        season: Season string (e.g., '2024-25')
        season_type: Season type ('Regular Season', 'Playoffs', etc.)
        game_id: Optional game ID for single game shot chart
    
    Returns:
        Tuple of (DataFrame with shot data, list of debug messages)
    """
    debug_messages = []
    
    # Convert player_id to int
    try:
        player_id_int = int(player_id)
    except (ValueError, TypeError):
        debug_messages.append(f"Invalid player_id: {player_id}")
        return pd.DataFrame(), debug_messages
    
    # Try multiple seasons if the requested season has no data
    seasons_to_try = [season]
    if season == "2025-26":
        seasons_to_try.extend(["2024-25", "2023-24"])
    elif season == "2024-25":
        seasons_to_try.append("2023-24")
    
    for try_season in seasons_to_try:
        try:
            if game_id:
                # Single game shot chart
                # Use player's team_id if provided, otherwise use 0 (all teams)
                team_id_to_use = team_id if team_id is not None else 0
                shot_data = endpoints.ShotChartDetail(
                    team_id=team_id_to_use,
                    player_id=player_id_int,
                    season_nullable=try_season,
                    season_type_all_star=season_type,
                    game_id_nullable=game_id
                )
            else:
                # Season shot chart
                # Use player's team_id if provided, otherwise use 0 (all teams)
                team_id_to_use = team_id if team_id is not None else 0
                shot_data = endpoints.ShotChartDetail(
                    team_id=team_id_to_use,
                    player_id=player_id_int,
                    season_nullable=try_season,
                    season_type_all_star=season_type
                )
            
            shot_df = shot_data.get_data_frames()[0]
            
            # Debug: Collect column names and sample data to understand API response
            if len(shot_df) > 0:
                debug_messages.append(f"\n=== DEBUG: Shot Data for player {player_id_int}, season {try_season} ===")
                debug_messages.append(f"Total shots returned: {len(shot_df)}")
                debug_messages.append(f"Columns: {list(shot_df.columns)}")
                
                # Check for shot outcome columns (case-insensitive)
                outcome_cols = [col for col in shot_df.columns if any(x in col.upper() for x in ['MADE', 'MISS', 'SHOT', 'FLAG'])]
                debug_messages.append(f"Shot outcome columns: {outcome_cols}")
                
                # Check for shot_made_flag in various cases
                shot_made_col = None
                for col in shot_df.columns:
                    if col.upper() in ['SHOT_MADE_FLAG', 'SHOT_MADE', 'SHOTMADE_FLAG']:
                        shot_made_col = col
                        break
                
                if shot_made_col:
                    value_counts = shot_df[shot_made_col].value_counts().to_dict()
                    debug_messages.append(f"{shot_made_col} value counts: {value_counts}")
                    made_count = pd.to_numeric(shot_df[shot_made_col], errors='coerce').fillna(0).sum()
                    total_count = len(shot_df)
                    debug_messages.append(f"Made shots: {made_count}, Total: {total_count}, Made %: {made_count/total_count*100:.1f}%")
                    
                    # Check SHOT_ATTEMPTED_FLAG if it exists
                    if 'SHOT_ATTEMPTED_FLAG' in shot_df.columns:
                        attempted_counts = shot_df['SHOT_ATTEMPTED_FLAG'].value_counts().to_dict()
                        debug_messages.append(f"SHOT_ATTEMPTED_FLAG value counts: {attempted_counts}")
                    
                    # Show sample rows with both flags
                    if len(shot_df) > 0:
                        sample_cols = ['SHOT_MADE_FLAG', 'SHOT_ATTEMPTED_FLAG', 'LOC_X', 'LOC_Y', 'SHOT_DISTANCE', 'EVENT_TYPE']
                        available_cols = [c for c in sample_cols if c in shot_df.columns]
                        debug_messages.append(f"Sample rows (first 5):")
                        for idx in range(min(5, len(shot_df))):
                            row_data = {k: shot_df.iloc[idx][k] for k in available_cols}
                            debug_messages.append(f"  Row {idx}: {row_data}")
                else:
                    debug_messages.append("WARNING: No shot_made_flag column found!")
                    if len(shot_df) > 0:
                        sample_cols = [k for k in shot_df.iloc[0].to_dict().keys() if 'SHOT' in k.upper() or 'MADE' in k.upper() or k in ['LOC_X', 'LOC_Y']]
                        debug_messages.append(f"Sample row (relevant cols): {str({k: v for k, v in shot_df.iloc[0].to_dict().items() if k in sample_cols})}")
                debug_messages.append("=" * 60)
            
            # Check if we got actual shot data
            if len(shot_df) > 0 and 'LOC_X' in shot_df.columns:
                return shot_df, debug_messages
            elif len(shot_df) == 0 and try_season != seasons_to_try[-1]:
                # Try next season if this one has no data
                continue
            else:
                return shot_df, debug_messages
                
        except Exception as e:
            debug_messages.append(f"Error fetching shot data for player {player_id_int}, season {try_season}: {e}")
            if try_season == seasons_to_try[-1]:
                # Last season attempt failed
                return pd.DataFrame(), debug_messages
            # Continue to next season
            continue
    
    return pd.DataFrame(), debug_messages


@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_team_shot_data(team_id: int, season: str = CURRENT_SEASON,
                      season_type: str = 'Regular Season',
                      game_id: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Fetch shot chart data for a team.
    
    Args:
        team_id: Team ID as integer
        season: Season string (e.g., '2024-25')
        season_type: Season type ('Regular Season', 'Playoffs', etc.)
        game_id: Optional game ID for single game shot chart
    
    Returns:
        Tuple of (DataFrame with shot data, list of debug messages)
    """
    debug_messages = []
    
    # Try multiple seasons if the requested season has no data
    seasons_to_try = [season]
    if season == "2025-26":
        seasons_to_try.extend(["2024-25", "2023-24"])
    elif season == "2024-25":
        seasons_to_try.append("2023-24")
    
    for try_season in seasons_to_try:
        try:
            if game_id:
                shot_data = endpoints.ShotChartDetail(
                    team_id=team_id,
                    player_id=0,  # 0 for all players
                    season_nullable=try_season,
                    season_type_all_star=season_type,
                    game_id_nullable=game_id
                )
            else:
                shot_data = endpoints.ShotChartDetail(
                    team_id=team_id,
                    player_id=0,  # 0 for all players
                    season_nullable=try_season,
                    season_type_all_star=season_type
                )
            
            shot_df = shot_data.get_data_frames()[0]
            
            # Debug: Collect column names and sample data to understand API response
            if len(shot_df) > 0:
                debug_messages.append(f"\n=== DEBUG: Team Shot Data for team {team_id}, season {try_season} ===")
                debug_messages.append(f"Total shots returned: {len(shot_df)}")
                debug_messages.append(f"Columns: {list(shot_df.columns)}")
                
                # Check for shot outcome columns (case-insensitive)
                outcome_cols = [col for col in shot_df.columns if any(x in col.upper() for x in ['MADE', 'MISS', 'SHOT', 'FLAG'])]
                debug_messages.append(f"Shot outcome columns: {outcome_cols}")
                
                # Check for shot_made_flag in various cases
                shot_made_col = None
                for col in shot_df.columns:
                    if col.upper() in ['SHOT_MADE_FLAG', 'SHOT_MADE', 'SHOTMADE_FLAG']:
                        shot_made_col = col
                        break
                
                if shot_made_col:
                    value_counts = shot_df[shot_made_col].value_counts().to_dict()
                    debug_messages.append(f"{shot_made_col} value counts: {value_counts}")
                    made_count = pd.to_numeric(shot_df[shot_made_col], errors='coerce').fillna(0).sum()
                    total_count = len(shot_df)
                    debug_messages.append(f"Made shots: {made_count}, Total: {total_count}, Made %: {made_count/total_count*100:.1f}%")
                    
                    # Check SHOT_ATTEMPTED_FLAG if it exists
                    if 'SHOT_ATTEMPTED_FLAG' in shot_df.columns:
                        attempted_counts = shot_df['SHOT_ATTEMPTED_FLAG'].value_counts().to_dict()
                        debug_messages.append(f"SHOT_ATTEMPTED_FLAG value counts: {attempted_counts}")
                    
                    # Show sample rows with both flags
                    if len(shot_df) > 0:
                        sample_cols = ['SHOT_MADE_FLAG', 'SHOT_ATTEMPTED_FLAG', 'LOC_X', 'LOC_Y', 'SHOT_DISTANCE', 'EVENT_TYPE']
                        available_cols = [c for c in sample_cols if c in shot_df.columns]
                        debug_messages.append(f"Sample rows (first 5):")
                        for idx in range(min(5, len(shot_df))):
                            row_data = {k: shot_df.iloc[idx][k] for k in available_cols}
                            debug_messages.append(f"  Row {idx}: {row_data}")
                else:
                    debug_messages.append("WARNING: No shot_made_flag column found!")
                    if len(shot_df) > 0:
                        sample_cols = [k for k in shot_df.iloc[0].to_dict().keys() if 'SHOT' in k.upper() or 'MADE' in k.upper() or k in ['LOC_X', 'LOC_Y']]
                        debug_messages.append(f"Sample row (relevant cols): {str({k: v for k, v in shot_df.iloc[0].to_dict().items() if k in sample_cols})}")
                debug_messages.append("=" * 60)
            
            # Check if we got actual shot data
            if len(shot_df) > 0 and 'LOC_X' in shot_df.columns:
                return shot_df, debug_messages
            elif len(shot_df) == 0 and try_season != seasons_to_try[-1]:
                # Try next season if this one has no data
                continue
            else:
                return shot_df, debug_messages
                
        except Exception as e:
            debug_messages.append(f"Error fetching shot data for team {team_id}, season {try_season}: {e}")
            if try_season == seasons_to_try[-1]:
                # Last season attempt failed
                return pd.DataFrame(), debug_messages
            # Continue to next season
            continue
    
    return pd.DataFrame(), debug_messages


def filter_shots_by_date_range(shot_df: pd.DataFrame, start_date: Optional[date] = None,
                               end_date: Optional[date] = None) -> pd.DataFrame:
    """
    Filter shot data by date range.
    
    Args:
        shot_df: DataFrame with shot data
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
    
    Returns:
        Filtered DataFrame
    """
    if shot_df.empty:
        return shot_df
    
    if 'GAME_DATE' not in shot_df.columns:
        return shot_df
    
    shot_df = shot_df.copy()
    shot_df['GAME_DATE'] = pd.to_datetime(shot_df['GAME_DATE'])
    
    if start_date:
        shot_df = shot_df[shot_df['GAME_DATE'].dt.date >= start_date]
    if end_date:
        shot_df = shot_df[shot_df['GAME_DATE'].dt.date <= end_date]
    
    return shot_df


def filter_shots_by_games(shot_df: pd.DataFrame, game_logs: pd.DataFrame, 
                         last_n_games: int) -> pd.DataFrame:
    """
    Filter shot data to last N games.
    
    Args:
        shot_df: DataFrame with shot data
        game_logs: DataFrame with game logs (sorted by date descending)
        last_n_games: Number of recent games to include
    
    Returns:
        Filtered DataFrame
    """
    if shot_df.empty or game_logs is None or game_logs.empty:
        return shot_df
    
    # Try to match by GAME_ID if available
    if 'GAME_ID' in shot_df.columns and 'GAME_ID' in game_logs.columns:
        # Get last N game IDs
        recent_games = game_logs.head(last_n_games)['GAME_ID'].tolist()
        # Convert to string for matching (GAME_ID might be int or string)
        recent_games_str = [str(g) for g in recent_games]
        shot_df['GAME_ID_STR'] = shot_df['GAME_ID'].astype(str)
        filtered = shot_df[shot_df['GAME_ID_STR'].isin(recent_games_str)]
        filtered = filtered.drop(columns=['GAME_ID_STR'])
        return filtered
    
    # If GAME_ID not available, try matching by date
    if 'GAME_DATE' in shot_df.columns and 'GAME_DATE' in game_logs.columns:
        shot_df['GAME_DATE'] = pd.to_datetime(shot_df['GAME_DATE'])
        game_logs['GAME_DATE'] = pd.to_datetime(game_logs['GAME_DATE'])
        recent_dates = game_logs.head(last_n_games)['GAME_DATE'].dt.date.tolist()
        shot_df['GAME_DATE_ONLY'] = shot_df['GAME_DATE'].dt.date
        filtered = shot_df[shot_df['GAME_DATE_ONLY'].isin(recent_dates)]
        filtered = filtered.drop(columns=['GAME_DATE_ONLY'])
        return filtered
    
    # If no matching columns, return original
    return shot_df


def get_zone_stats(shot_df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Calculate shooting statistics by court zone.
    Uses NBA API coordinate system (inches, basket at (0, 0)).
    
    Args:
        shot_df: DataFrame with shot data including LOC_X, LOC_Y, SHOT_MADE_FLAG
    
    Returns:
        Dictionary with zone statistics
    """
    if shot_df.empty or 'LOC_X' not in shot_df.columns or 'LOC_Y' not in shot_df.columns:
        return {}
    
    shot_df = shot_df.copy()
    
    # Ensure numeric types
    shot_df['LOC_X'] = pd.to_numeric(shot_df['LOC_X'], errors='coerce')
    shot_df['LOC_Y'] = pd.to_numeric(shot_df['LOC_Y'], errors='coerce')
    
    # Handle SHOT_MADE_FLAG - check for various possible column names (case-insensitive)
    # According to NBA API docs, the column is 'shot_made_flag' (lowercase)
    shot_made_col = None
    for col in shot_df.columns:
        if col.upper() in ['SHOT_MADE_FLAG', 'SHOT_MADE', 'SHOTMADE_FLAG']:
            shot_made_col = col
            break
    
    debug_messages = []
    
    if shot_made_col:
        shot_df['SHOT_MADE_FLAG'] = pd.to_numeric(shot_df[shot_made_col], errors='coerce')
        # Fill NaN with 0 (assume miss if not specified)
        shot_df['SHOT_MADE_FLAG'] = shot_df['SHOT_MADE_FLAG'].fillna(0)
        # Ensure values are 0 or 1 (some APIs might use True/False or other values)
        shot_df['SHOT_MADE_FLAG'] = (shot_df['SHOT_MADE_FLAG'] > 0).astype(int)
    else:
        # If column doesn't exist, this is a problem - we need it to calculate stats
        debug_messages.append("WARNING: No shot_made_flag column found in shot data!")
        debug_messages.append(f"Available columns: {list(shot_df.columns)}")
        # Create a default column (but this won't be accurate)
        shot_df['SHOT_MADE_FLAG'] = 0
    
    # Remove invalid shots (only check coordinates, not SHOT_MADE_FLAG since we handle it above)
    shot_df = shot_df.dropna(subset=['LOC_X', 'LOC_Y'])
    
    if shot_df.empty:
        return {}, debug_messages
    
    # Calculate distance from basket (at (0, 0)) in inches for visualization
    shot_df['DISTANCE'] = np.sqrt(shot_df['LOC_X']**2 + shot_df['LOC_Y']**2)
    
    # Use API's SHOT_DISTANCE (in feet) if available, otherwise convert our calculated distance
    if 'SHOT_DISTANCE' in shot_df.columns:
        shot_df['DISTANCE_FEET'] = pd.to_numeric(shot_df['SHOT_DISTANCE'], errors='coerce')
    else:
        shot_df['DISTANCE_FEET'] = shot_df['DISTANCE'] / 12.0  # Convert inches to feet
    
    # Use API's zone columns if available, otherwise calculate zones manually
    # NBA API provides: SHOT_ZONE_BASIC, SHOT_ZONE_AREA, SHOT_ZONE_RANGE
    use_api_zones = 'SHOT_ZONE_BASIC' in shot_df.columns and 'SHOT_ZONE_AREA' in shot_df.columns
    
    if use_api_zones:
        # Use NBA API's pre-calculated zones
        debug_messages.append("Using NBA API zone columns (SHOT_ZONE_BASIC, SHOT_ZONE_AREA)")
        
        # Map API zones to our zone names
        # SHOT_ZONE_BASIC values from API: 'Restricted Area', 'In The Paint (Non-RA)', 'Mid-Range', 'Above the Break 3', 'Left Corner 3', 'Right Corner 3'
        # Note: API uses 'Mid-Range' with hyphen, not 'Mid Range'
        
        zones = {
            'Restricted Area': shot_df['SHOT_ZONE_BASIC'] == 'Restricted Area',
            'Paint (Non-RA)': shot_df['SHOT_ZONE_BASIC'] == 'In The Paint (Non-RA)',
            'Mid-Range': shot_df['SHOT_ZONE_BASIC'] == 'Mid-Range',  # Fixed: API uses hyphen
            'Corner 3': (shot_df['SHOT_ZONE_BASIC'] == 'Left Corner 3') | (shot_df['SHOT_ZONE_BASIC'] == 'Right Corner 3'),
            'Above the Break 3': shot_df['SHOT_ZONE_BASIC'] == 'Above the Break 3'
        }
        
        # Debug: Verify zone mapping
        debug_messages.append(f"Zone mapping verification:")
        for zone_name, zone_mask in zones.items():
            count = zone_mask.sum()
            debug_messages.append(f"  {zone_name}: {count} shots")
    else:
        # Manual zone calculation using distance and coordinates
        debug_messages.append("Calculating zones manually from coordinates")
        
        # Zone definitions using feet (from API SHOT_DISTANCE) or calculated distance
        restricted_radius_feet = 4.0  # 4 feet
        paint_length_feet = 15.0  # 15 feet (free throw line)
        three_pt_radius_feet = 23.75  # 23.75 feet (3-point line at top)
        corner_threshold_feet = 22.0  # 22 feet (corner 3-point line)
        corner_x_threshold_inches = 220.0  # ~22 feet in inches for X coordinate check
        
        zones = {
            'Restricted Area': shot_df['DISTANCE_FEET'] <= restricted_radius_feet,
            'Paint (Non-RA)': (shot_df['DISTANCE_FEET'] > restricted_radius_feet) & 
                              (shot_df['DISTANCE_FEET'] <= paint_length_feet) & 
                              (shot_df['LOC_X'].abs() <= 96),  # Paint is 16 feet = 192 inches wide, so 96 inches from center
            'Mid-Range': (shot_df['DISTANCE_FEET'] > paint_length_feet) & 
                         (shot_df['DISTANCE_FEET'] <= three_pt_radius_feet) & 
                         (shot_df['LOC_X'].abs() <= corner_x_threshold_inches),
            'Corner 3': (shot_df['DISTANCE_FEET'] > paint_length_feet) & 
                       (shot_df['DISTANCE_FEET'] <= three_pt_radius_feet) & 
                       (shot_df['LOC_X'].abs() > corner_x_threshold_inches),
            'Above the Break 3': shot_df['DISTANCE_FEET'] > three_pt_radius_feet
        }
    
    # Debug: Check SHOT_MADE_FLAG distribution and coordinate ranges before zone calculation
    if 'SHOT_MADE_FLAG' in shot_df.columns:
        total_shots = len(shot_df)
        made_shots = shot_df['SHOT_MADE_FLAG'].sum()
        debug_messages.append(f"\n=== DEBUG: Zone Stats Calculation ===")
        debug_messages.append(f"Total shots: {total_shots}, Made: {made_shots}, Missed: {total_shots - made_shots}")
        debug_messages.append(f"SHOT_MADE_FLAG distribution: {shot_df['SHOT_MADE_FLAG'].value_counts().to_dict()}")
        
        # Show SHOT_ATTEMPTED_FLAG distribution if available
        if 'SHOT_ATTEMPTED_FLAG' in shot_df.columns:
            attempted_flag_dist = shot_df['SHOT_ATTEMPTED_FLAG'].value_counts().to_dict()
            debug_messages.append(f"SHOT_ATTEMPTED_FLAG distribution: {attempted_flag_dist}")
            attempted_count = pd.to_numeric(shot_df['SHOT_ATTEMPTED_FLAG'], errors='coerce').fillna(0).sum()
            debug_messages.append(f"Total attempted shots: {attempted_count}")
        
        # Check SHOT_DISTANCE column if it exists (from API - in feet)
        if 'SHOT_DISTANCE' in shot_df.columns:
            api_distances = shot_df['SHOT_DISTANCE'].dropna()
            debug_messages.append(f"API SHOT_DISTANCE (feet) - Min: {api_distances.min():.1f}, Max: {api_distances.max():.1f}, Mean: {api_distances.mean():.1f}")
            debug_messages.append(f"API SHOT_DISTANCE > 23.75 feet (3-pt line): {(api_distances > 23.75).sum()}")
            debug_messages.append(f"API SHOT_DISTANCE > 22 feet (corner 3): {(api_distances > 22).sum()}")
        
        # Check API zone columns
        if 'SHOT_ZONE_BASIC' in shot_df.columns:
            zone_basic_counts = shot_df['SHOT_ZONE_BASIC'].value_counts().to_dict()
            debug_messages.append(f"SHOT_ZONE_BASIC distribution: {zone_basic_counts}")
        if 'SHOT_ZONE_AREA' in shot_df.columns:
            zone_area_counts = shot_df['SHOT_ZONE_AREA'].value_counts().to_dict()
            debug_messages.append(f"SHOT_ZONE_AREA distribution: {zone_area_counts}")
        
        debug_messages.append(f"Coordinate ranges - LOC_X: [{shot_df['LOC_X'].min():.1f}, {shot_df['LOC_X'].max():.1f}], LOC_Y: [{shot_df['LOC_Y'].min():.1f}, {shot_df['LOC_Y'].max():.1f}]")
        debug_messages.append(f"Calculated DISTANCE (inches) - Min: {shot_df['DISTANCE'].min():.1f}, Max: {shot_df['DISTANCE'].max():.1f}, Mean: {shot_df['DISTANCE'].mean():.1f}")
        
        # Distance distribution analysis using feet
        if 'DISTANCE_FEET' in shot_df.columns:
            debug_messages.append(f"Distance distribution (feet, bins):")
            bins_feet = [0, 4, 15, 22, 23.75, 30]
            bin_labels_feet = ['0-4ft (RA)', '4-15ft (Paint)', '15-22ft (Mid)', '22-23.75ft (Corner 3)', '23.75ft+ (ATB 3)']
            for i in range(len(bins_feet)-1):
                count = ((shot_df['DISTANCE_FEET'] > bins_feet[i]) & (shot_df['DISTANCE_FEET'] <= bins_feet[i+1])).sum()
                debug_messages.append(f"  {bin_labels_feet[i]}: {count} shots")
    
    zone_stats = {}
    for zone_name, zone_mask in zones.items():
        zone_shots = shot_df[zone_mask]
        # Count all shots in zone (FGA)
        fga = len(zone_shots)
        if fga > 0:
            # Count made shots (FGM) - SHOT_MADE_FLAG should be 1 for makes, 0 for misses
            # Ensure we're working with numeric values
            if 'SHOT_MADE_FLAG' in zone_shots.columns:
                fgm = pd.to_numeric(zone_shots['SHOT_MADE_FLAG'], errors='coerce').fillna(0).sum()
                # Debug for each zone
                if zone_name in ['Corner 3', 'Above the Break 3']:
                    debug_messages.append(f"{zone_name}: FGA={fga}, FGM={fgm}, Sample SHOT_MADE_FLAG values: {zone_shots['SHOT_MADE_FLAG'].head(10).tolist()}")
            else:
                # If column doesn't exist, assume all are misses (shouldn't happen)
                fgm = 0
                debug_messages.append(f"WARNING: {zone_name} - No SHOT_MADE_FLAG column!")
            fg_pct = (fgm / fga * 100) if fga > 0 else 0.0
            
            zone_stats[zone_name] = {
                'FGM': int(fgm),
                'FGA': int(fga),
                'FG%': round(fg_pct, 1)
            }
        else:
            zone_stats[zone_name] = {
                'FGM': 0,
                'FGA': 0,
                'FG%': 0.0
            }
    
    debug_messages.append("=" * 60)
    return zone_stats, debug_messages


def plot_shot_chart(shot_df: pd.DataFrame, chart_type: str = 'individual',
                   ax=None, title: str = 'Shot Chart') -> plt.Figure:
    """
    Plot shot chart visualization.
    
    Args:
        shot_df: DataFrame with shot data
        chart_type: 'individual' for shot markers, 'heatmap' for density heat map
        ax: Matplotlib axes object (optional)
        title: Chart title
    
    Returns:
        Matplotlib figure object
    """
    if shot_df.empty or 'LOC_X' not in shot_df.columns or 'LOC_Y' not in shot_df.columns:
        # Return empty chart
        fig, ax = plt.subplots(figsize=(10, 10))
        draw_court(ax)
        ax.text(0, 0, 'No shot data available', ha='center', va='center', fontsize=14)
        ax.set_title(title)
        return fig
    
    shot_df = shot_df.copy()
    
    # Ensure numeric types
    shot_df['LOC_X'] = pd.to_numeric(shot_df['LOC_X'], errors='coerce')
    shot_df['LOC_Y'] = pd.to_numeric(shot_df['LOC_Y'], errors='coerce')
    
    # Handle SHOT_MADE_FLAG - check for various possible column names (case-insensitive)
    shot_made_col = None
    for col in shot_df.columns:
        if col.upper() in ['SHOT_MADE_FLAG', 'SHOT_MADE', 'SHOTMADE_FLAG']:
            shot_made_col = col
            break
    
    if shot_made_col:
        shot_df['SHOT_MADE_FLAG'] = pd.to_numeric(shot_df[shot_made_col], errors='coerce')
        shot_df['SHOT_MADE_FLAG'] = shot_df['SHOT_MADE_FLAG'].fillna(0)
        shot_df['SHOT_MADE_FLAG'] = (shot_df['SHOT_MADE_FLAG'] > 0).astype(int)
    else:
        # If column doesn't exist, create it (assume all misses for visualization)
        shot_df['SHOT_MADE_FLAG'] = 0
    
    # Remove invalid shots (only check coordinates, not SHOT_MADE_FLAG)
    shot_df = shot_df.dropna(subset=['LOC_X', 'LOC_Y'])
    
    if shot_df.empty:
        fig, ax = plt.subplots(figsize=(10, 10))
        draw_court(ax)
        ax.text(0, 0, 'No valid shot data', ha='center', va='center', fontsize=14)
        ax.set_title(title)
        return fig
    
    # Create figure if not provided
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 10))
        # Clear any previous plots to ensure fresh figure
        ax.clear()
    else:
        fig = ax.figure
        ax.clear()
    
    # Draw court
    draw_court(ax)
    
    if chart_type == 'individual':
        # Plot individual shots
        # Filter to half court (positive Y) for display
        half_court_shots = shot_df[shot_df['LOC_Y'] >= 0].copy()
        
        if len(half_court_shots) > 0:
            makes = half_court_shots[half_court_shots['SHOT_MADE_FLAG'] == 1]
            misses = half_court_shots[half_court_shots['SHOT_MADE_FLAG'] == 0]
            
            if len(misses) > 0:
                ax.scatter(misses['LOC_X'], misses['LOC_Y'], c='red', s=50, 
                          alpha=0.6, label='Miss', zorder=2)
            if len(makes) > 0:
                ax.scatter(makes['LOC_X'], makes['LOC_Y'], c='green', s=50,
                          alpha=0.6, label='Make', zorder=2)
        
        # Add legend
        ax.legend(loc='upper right', fontsize=10)
        
    elif chart_type == 'heatmap':
        # Create heat map using hexbin for shot frequency
        # Filter to half court only (positive Y)
        half_court_shots = shot_df[shot_df['LOC_Y'] >= 0].copy()
        
        if len(half_court_shots) > 0:
            # Create hexbin plot for shot frequency (in inches)
            # Use a more visible colormap and adjust alpha
            hb = ax.hexbin(half_court_shots['LOC_X'], half_court_shots['LOC_Y'],
                          gridsize=30, cmap='YlOrRd', alpha=0.8, mincnt=1, edgecolors='none')
            
            # Add colorbar for shot frequency
            cbar1 = plt.colorbar(hb, ax=ax, label='Shot Frequency', pad=0.02)
            cbar1.ax.set_position([0.92, 0.15, 0.02, 0.7])  # Position on the right
            
            # Overlay efficiency heat map with lower alpha so hexbin shows through
            # Calculate FG% by bin (using inches)
            x_bins = np.linspace(-300, 300, 26)  # Court width in inches
            y_bins = np.linspace(0, 600, 26)  # Half court length in inches
            
            efficiency_grid = np.zeros((25, 25))
            for i in range(len(x_bins) - 1):
                for j in range(len(y_bins) - 1):
                    x_mask = (half_court_shots['LOC_X'] >= x_bins[i]) & (half_court_shots['LOC_X'] < x_bins[i+1])
                    y_mask = (half_court_shots['LOC_Y'] >= y_bins[j]) & (half_court_shots['LOC_Y'] < y_bins[j+1])
                    bin_shots = half_court_shots[x_mask & y_mask]
                    
                    if len(bin_shots) > 0:
                        fg_pct = bin_shots['SHOT_MADE_FLAG'].mean() * 100
                        efficiency_grid[j, i] = fg_pct
            
            # Plot efficiency as contour with lower alpha
            X, Y = np.meshgrid((x_bins[:-1] + x_bins[1:]) / 2,
                              (y_bins[:-1] + y_bins[1:]) / 2)
            contour = ax.contourf(X, Y, efficiency_grid, levels=10, alpha=0.3, cmap='RdYlGn', zorder=1)
            # Add colorbar for FG% on the left side
            cbar2 = plt.colorbar(contour, ax=ax, label='FG%', pad=0.02)
            cbar2.ax.set_position([0.01, 0.15, 0.02, 0.7])  # Position on the left
    
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Adjust figure padding to prevent cutoff
    fig.tight_layout(pad=1.5)
    
    return fig


def create_shot_chart_section(player_id: Optional[str] = None, team_id: Optional[int] = None,
                             season: str = CURRENT_SEASON, season_type: str = 'Regular Season',
                             time_period: str = 'season', last_n_games: Optional[int] = None,
                             start_date: Optional[date] = None, end_date: Optional[date] = None,
                             game_id: Optional[str] = None, chart_type: str = 'individual',
                             game_logs: Optional[pd.DataFrame] = None,
                             player_team_id: Optional[int] = None) -> Tuple[plt.Figure, Dict, List[str]]:
    """
    Create a complete shot chart section with filtering.
    
    Args:
        player_id: Player ID (for player shot chart)
        team_id: Team ID (for team shot chart)
        season: Season string
        season_type: Season type
        time_period: 'season', 'last_n', 'date_range', or 'game'
        last_n_games: Number of games for 'last_n' period
        start_date: Start date for 'date_range'
        end_date: End date for 'date_range'
        game_id: Game ID for 'game' period
        chart_type: 'individual' or 'heatmap'
        game_logs: Game logs DataFrame for filtering by games
        player_team_id: Optional team ID for the player (used for API calls)
    
    Returns:
        Tuple of (matplotlib figure, zone statistics dictionary, debug messages list)
    """
    debug_messages = []
    
    # Fetch shot data
    if player_id:
        # Try with player's team_id if available, otherwise use 0
        result = get_player_shot_data(player_id, season, season_type, game_id, player_team_id)
        # Handle backward compatibility with cached results
        if isinstance(result, tuple) and len(result) == 2:
            shot_df, player_debug = result
        else:
            # Old cached format - just DataFrame
            shot_df = result if isinstance(result, pd.DataFrame) else pd.DataFrame()
            player_debug = []
        debug_messages.extend(player_debug)
        entity_name = f"Player {player_id}"
    elif team_id:
        result = get_team_shot_data(team_id, season, season_type, game_id)
        # Handle backward compatibility with cached results
        if isinstance(result, tuple) and len(result) == 2:
            shot_df, team_debug = result
        else:
            # Old cached format - just DataFrame
            shot_df = result if isinstance(result, pd.DataFrame) else pd.DataFrame()
            team_debug = []
        debug_messages.extend(team_debug)
        entity_name = f"Team {team_id}"
    else:
        return None, {}, []
    
    if shot_df.empty:
        fig, ax = plt.subplots(figsize=(10, 10))
        draw_court(ax)
        ax.text(0, 0, 'No shot data available', ha='center', va='center', fontsize=14)
        return fig, {}, debug_messages
    
    # Apply time period filtering
    if time_period == 'date_range' and start_date and end_date:
        shot_df = filter_shots_by_date_range(shot_df, start_date, end_date)
    elif time_period == 'last_n' and last_n_games and game_logs is not None:
        shot_df = filter_shots_by_games(shot_df, game_logs, last_n_games)
    elif time_period == 'game' and game_id:
        # Already filtered by game_id in API call
        pass
    
    # Calculate zone statistics
    result = get_zone_stats(shot_df)
    # Handle backward compatibility
    if isinstance(result, tuple) and len(result) == 2:
        zone_stats, zone_debug = result
    else:
        # Old format - just dict
        zone_stats = result if isinstance(result, dict) else {}
        zone_debug = []
    debug_messages.extend(zone_debug)
    
    # Create title
    title_parts = [entity_name]
    if time_period == 'last_n' and last_n_games:
        title_parts.append(f"Last {last_n_games} Games")
    elif time_period == 'date_range' and start_date and end_date:
        title_parts.append(f"{start_date} to {end_date}")
    elif time_period == 'game' and game_id:
        title_parts.append(f"Game {game_id}")
    else:
        title_parts.append(f"{season} {season_type}")
    
    title = " - ".join(title_parts)
    
    # Plot shot chart
    fig = plot_shot_chart(shot_df, chart_type=chart_type, title=title)
    
    return fig, zone_stats, debug_messages

