"""
Injury Adjustments Module
Functions to calculate prediction adjustments when players are out.
"""

from typing import Dict, List, Optional
import pandas as pd


def calculate_minutes_redistribution(
    teammates_out: List[str],
    player_minutes: float,
    player_minutes_map: Dict[int, float]
) -> float:
    """
    Calculate how many extra minutes a player might get when teammates are out.
    Redistribution is based on role matching: stars/starters get minutes from stars/starters,
    role players get minutes from role players.
    
    Args:
        teammates_out: List of teammate player IDs who are out
        player_minutes: Current player's average minutes
        player_minutes_map: Dict of player_id -> average minutes
    
    Returns:
        Extra minutes the player might receive
    """
    if not teammates_out:
        return 0.0
    
    # Determine the role of the current player
    if player_minutes >= 32:
        player_role = "star"
    elif player_minutes >= 28:
        player_role = "starter"
    elif player_minutes >= 22:
        player_role = "rotation"
    elif player_minutes >= 15:
        player_role = "bench"
    else:
        player_role = "deep_bench"
    
    # Calculate total minutes from players who are out, grouped by role
    star_minutes_out = 0
    starter_minutes_out = 0
    rotation_minutes_out = 0
    bench_minutes_out = 0
    deep_bench_minutes_out = 0
    
    for out_player in teammates_out:
        out_mins = player_minutes_map.get(int(out_player), 0)
        if out_mins == 0:
            continue
        
        if out_mins >= 32:
            star_minutes_out += out_mins
        elif out_mins >= 28:
            starter_minutes_out += out_mins
        elif out_mins >= 22:
            rotation_minutes_out += out_mins
        elif out_mins >= 15:
            bench_minutes_out += out_mins
        else:
            deep_bench_minutes_out += out_mins
    
    # Redistribute based on role matching
    extra_minutes = 0.0
    max_boost = 0
    
    if player_role == "star":
        # Stars get minutes from stars and starters
        if star_minutes_out > 0:
            extra_minutes += star_minutes_out * 0.16  # Higher % for star-to-star
            max_boost = 6
        if starter_minutes_out > 0:
            extra_minutes += starter_minutes_out * 0.12
            max_boost = max(max_boost, 5) if max_boost > 0 else 5
        
    elif player_role == "starter":
        # Starters get minutes from stars and starters
        if star_minutes_out > 0:
            extra_minutes += star_minutes_out * 0.12
            max_boost = 5
        if starter_minutes_out > 0:
            extra_minutes += starter_minutes_out * 0.11
            max_boost = max(max_boost, 4) if max_boost > 0 else 4
        
    elif player_role == "rotation":
        # Rotation players get minutes from rotation and bench players
        if rotation_minutes_out > 0:
            extra_minutes += rotation_minutes_out * 0.10
            max_boost = 4
        if bench_minutes_out > 0:
            extra_minutes += bench_minutes_out * 0.08
            max_boost = max(max_boost, 4) if max_boost > 0 else 4
        # Can also get some from starters if they're out (backup role)
        if starter_minutes_out > 0:
            extra_minutes += starter_minutes_out * 0.06
            max_boost = max(max_boost, 4) if max_boost > 0 else 4
        
    elif player_role == "bench":
        # Bench players get minutes from bench and deep bench
        if bench_minutes_out > 0:
            extra_minutes += bench_minutes_out * 0.08
            max_boost = 5
        if deep_bench_minutes_out > 0:
            extra_minutes += deep_bench_minutes_out * 0.06
            max_boost = max(max_boost, 5) if max_boost > 0 else 5
        # Can also get some from rotation players
        if rotation_minutes_out > 0:
            extra_minutes += rotation_minutes_out * 0.05
            max_boost = max(max_boost, 5) if max_boost > 0 else 5
        
    else:  # deep_bench
        # Deep bench gets minutes from deep bench and bench
        if deep_bench_minutes_out > 0:
            extra_minutes += deep_bench_minutes_out * 0.06
            max_boost = 6
        if bench_minutes_out > 0:
            extra_minutes += bench_minutes_out * 0.05
            max_boost = max(max_boost, 6) if max_boost > 0 else 6
    
    # Apply the cap if we have any minutes to redistribute
    if max_boost > 0:
        extra_minutes = min(extra_minutes, max_boost)
    
    return round(extra_minutes, 1)


def calculate_usage_boost(
    teammates_out: List[str],
    player_minutes_map: Dict[int, float]
) -> float:
    """
    Calculate usage rate boost when high-usage teammates are out.
    
    Returns:
        Usage multiplier (1.0 = no change, 1.1 = 10% boost)
    """
    if not teammates_out:
        return 1.0
    
    usage_boost = 1.0
    
    for out_player in teammates_out:
        out_mins = player_minutes_map.get(int(out_player), 0)
        
        # Only apply usage boost if player has actual minutes
        # Players with 0 minutes are out of rotation - no usage to redistribute
        if out_mins == 0:
            continue
        
        # Higher minute players = more usage to redistribute
        if out_mins >= 34:  # Star player
            usage_boost += 0.08
        elif out_mins >= 30:  # High-usage starter
            usage_boost += 0.05
        elif out_mins >= 25:  # Starter
            usage_boost += 0.03
        elif out_mins >= 18:  # Rotation
            usage_boost += 0.01
    
    # Cap the total usage boost - REDUCED from 25% to 18%
    return min(usage_boost, 1.18)  # Max 18% usage boost (down from 25%)


def calculate_injury_adjustments(
    player_id: str,
    player_team_id: int,
    opponent_team_id: int,
    teammates_out: List[str],
    opponents_out: List[str],
    player_minutes_map: Dict[int, float],
    players_df: pd.DataFrame
) -> Dict[str, any]:
    """
    Calculate all injury-related adjustments for a player's prediction.
    
    Args:
        player_id: The player being predicted
        player_team_id: Player's team ID
        opponent_team_id: Opponent's team ID
        teammates_out: List of teammate player IDs who are out
        opponents_out: List of opponent player IDs who are out
        player_minutes_map: Dict of player_id -> average minutes
        players_df: DataFrame with player info
    
    Returns:
        Dict with adjustment multipliers and explanations
    """
    adjustments = {
        'PTS': 1.0,
        'REB': 1.0,
        'AST': 1.0,
        'STL': 1.0,
        'BLK': 1.0,
        'FG3M': 1.0,
        'FTM': 1.0,
        'minutes_boost': 0.0,
        'usage_boost': 1.0,
        'factors': []
    }
    
    player_mins = player_minutes_map.get(int(player_id), 25)
    
    # === TEAMMATE INJURIES ===
    if teammates_out:
        # Calculate minutes redistribution
        extra_minutes = calculate_minutes_redistribution(
            teammates_out, player_mins, player_minutes_map
        )
        adjustments['minutes_boost'] = extra_minutes
        
        # Minutes multiplier
        if player_mins > 0:
            minutes_mult = (player_mins + extra_minutes) / player_mins
        else:
            minutes_mult = 1.0
        
        # Usage boost
        usage_mult = calculate_usage_boost(teammates_out, player_minutes_map)
        adjustments['usage_boost'] = usage_mult
        
        # Apply adjustments to stats
        # Scoring stats get both minutes and usage boost
        # BUT cap total boost based on player role to prevent unrealistic predictions
        raw_pts_mult = minutes_mult * usage_mult
        
        
        # Role-based caps for total injury boost (keeps role differences but prevents extremes)
        # REDUCED caps to address over-prediction
        if player_mins >= 32:  # Star - can handle bigger boost
            max_pts_mult = 1.28  # Max 28% boost (down from 35%)
        elif player_mins >= 28:  # Starter
            max_pts_mult = 1.24  # Max 24% boost (down from 30%)
        elif player_mins >= 22:  # Rotation
            max_pts_mult = 1.20  # Max 20% boost (down from 25%)
        elif player_mins >= 15:  # Bench
            max_pts_mult = 1.18  # Max 18% boost (down from 22%)
        else:  # Deep bench
            max_pts_mult = 1.15  # Max 15% boost (down from 20%)
        
        adjustments['PTS'] = min(raw_pts_mult, max_pts_mult)
        adjustments['FG3M'] = min(raw_pts_mult, max_pts_mult)
        adjustments['FTM'] = min(raw_pts_mult, max_pts_mult)
        
        # Rebounds get minutes boost + slight usage boost (with same role-based cap)
        raw_reb_mult = minutes_mult * (1 + (usage_mult - 1) * 0.3)
        adjustments['REB'] = min(raw_reb_mult, max_pts_mult * 0.95)  # Slightly lower cap for rebounds
        
        # Assists: depends on who's out
        # If scorers are out, assists might drop (fewer finishers)
        # If playmakers are out, assists might rise (more ball handling)
        assist_adjustment = minutes_mult * 0.95  # Slight reduction by default
        adjustments['AST'] *= assist_adjustment
        
        # Steals/Blocks get minutes boost only
        adjustments['STL'] *= minutes_mult
        adjustments['BLK'] *= minutes_mult
        
        # Build explanation
        teammate_names = get_player_names(teammates_out, players_df)
        if extra_minutes > 0:
            adjustments['factors'].append(
                f"Teammates out ({', '.join(teammate_names)}): +{extra_minutes:.1f} min, {(usage_mult-1)*100:.0f}% usage boost"
            )
    
    # === OPPONENT INJURIES ===
    if opponents_out:
        # When key opponents are out, matchup might be easier
        opp_minutes_out = sum(
            player_minutes_map.get(int(p), 0) for p in opponents_out
        )
        
        if opp_minutes_out >= 30:  # Significant player(s) out
            # Slight boost to scoring (easier defense)
            adjustments['PTS'] *= 1.03
            adjustments['FG3M'] *= 1.02
            
            opponent_names = get_player_names(opponents_out, players_df)
            adjustments['factors'].append(
                f"Opponents out ({', '.join(opponent_names)}): Easier matchup (+3% scoring)"
            )
    
    return adjustments


def get_player_names(player_ids: List[str], players_df: pd.DataFrame) -> List[str]:
    """Get player names from IDs."""
    names = []
    for pid in player_ids:
        try:
            pid_int = int(pid)
            row = players_df[players_df['PERSON_ID'] == pid_int]
            if len(row) > 0:
                first = row['PLAYER_FIRST_NAME'].iloc[0]
                last = row['PLAYER_LAST_NAME'].iloc[0]
                names.append(f"{first[0]}. {last}")
            else:
                names.append(f"Player {pid}")
        except:
            names.append(f"Player {pid}")
    return names


def apply_injury_adjustments(
    base_prediction: float,
    stat: str,
    injury_adjustments: Dict
) -> float:
    """
    Apply injury adjustments to a base prediction.
    
    Args:
        base_prediction: The original prediction value
        stat: The stat being predicted ('PTS', 'REB', etc.)
        injury_adjustments: Dict from calculate_injury_adjustments()
    
    Returns:
        Adjusted prediction value
    """
    multiplier = injury_adjustments.get(stat, 1.0)
    return round(base_prediction * multiplier, 1)


def format_injury_impact(injury_adjustments: Dict) -> str:
    """Format injury adjustments for display."""
    if not injury_adjustments.get('factors'):
        return "No injury adjustments"
    
    return " | ".join(injury_adjustments['factors'])

