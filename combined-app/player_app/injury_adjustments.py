"""
Injury Adjustments Module
Functions to calculate prediction adjustments when players are out.
"""

from typing import Dict, List, Optional
import pandas as pd


def calculate_minutes_redistribution(
    teammates_out: List[str],
    player_minutes: float,
    player_minutes_map: Dict[int, float],
    player_position: Optional[str] = None,
    teammates_positions_map: Optional[Dict[int, str]] = None
) -> float:
    """
    Calculate how many extra minutes a player might get when teammates are out.
    Redistribution is based on role matching AND position matching:
    - Stars/starters get minutes from stars/starters
    - Role players get minutes from role players
    - Guards get more minutes when guards are out
    - Forwards get more minutes when forwards are out
    - Centers get more minutes when centers are out
    
    Args:
        teammates_out: List of teammate player IDs who are out
        player_minutes: Current player's average minutes
        player_minutes_map: Dict of player_id -> average minutes
        player_position: Current player's position (e.g., 'PG', 'SG', 'SF', 'PF', 'C')
        teammates_positions_map: Dict of player_id -> position for injured players
    
    Returns:
        Extra minutes the player might receive
    """
    if not teammates_out:
        return 0.0
    
    # Helper function to get position group
    def get_position_group(pos: str) -> str:
        """Map position to group: G, F, or C"""
        if not pos:
            return 'F'  # Default
        pos_upper = pos.upper().strip()
        if pos_upper in ['PG', 'SG', 'G', 'G-F']:
            return 'G'
        elif pos_upper in ['C', 'C-F']:
            return 'C'
        else:  # SF, PF, F, F-G, F-C
            return 'F'
    
    # Get current player's position group
    player_pos_group = get_position_group(player_position) if player_position else 'F'
    
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
    
    # Calculate total minutes from players who are out, grouped by role AND position
    star_minutes_out = {'G': 0, 'F': 0, 'C': 0}
    starter_minutes_out = {'G': 0, 'F': 0, 'C': 0}
    rotation_minutes_out = {'G': 0, 'F': 0, 'C': 0}
    bench_minutes_out = {'G': 0, 'F': 0, 'C': 0}
    deep_bench_minutes_out = {'G': 0, 'F': 0, 'C': 0}
    
    for out_player in teammates_out:
        out_mins = player_minutes_map.get(int(out_player), 0)
        if out_mins == 0:
            continue
        
        # Get injured player's position group
        out_pos = teammates_positions_map.get(int(out_player), 'F') if teammates_positions_map else 'F'
        out_pos_group = get_position_group(out_pos)
        
        # Categorize by role
        if out_mins >= 32:
            star_minutes_out[out_pos_group] += out_mins
        elif out_mins >= 28:
            starter_minutes_out[out_pos_group] += out_mins
        elif out_mins >= 22:
            rotation_minutes_out[out_pos_group] += out_mins
        elif out_mins >= 15:
            bench_minutes_out[out_pos_group] += out_mins
        else:
            deep_bench_minutes_out[out_pos_group] += out_mins
    
    # Position-based multipliers
    # Same position gets full value, adjacent positions get partial value
    position_multipliers = {
        'G': {'G': 1.0, 'F': 0.3, 'C': 0.1},  # Guards: full from guards, some from forwards, little from centers
        'F': {'G': 0.3, 'F': 1.0, 'C': 0.4},  # Forwards: full from forwards, some from guards/centers
        'C': {'G': 0.1, 'F': 0.4, 'C': 1.0}   # Centers: full from centers, some from forwards, little from guards
    }
    
    pos_mult = position_multipliers[player_pos_group]
    
    # Total missing minutes across all injured players (used for dynamic caps)
    total_missing = sum(
        sum(d.values()) for d in [
            star_minutes_out, starter_minutes_out, rotation_minutes_out,
            bench_minutes_out, deep_bench_minutes_out
        ]
    )
    # Heavy-absence flag: when 60+ minutes are missing, everyone up the chain
    # absorbs more because the team is genuinely shorthanded
    heavy_absence = total_missing >= 60

    # Redistribute based on role matching with position weighting
    extra_minutes = 0.0
    max_boost = 0

    if player_role == "star":
        for pos_group in ['G', 'F', 'C']:
            if star_minutes_out[pos_group] > 0:
                extra_minutes += star_minutes_out[pos_group] * 0.25 * pos_mult[pos_group]
                max_boost = 8
            if starter_minutes_out[pos_group] > 0:
                extra_minutes += starter_minutes_out[pos_group] * 0.20 * pos_mult[pos_group]
                max_boost = max(max_boost, 7)

    elif player_role == "starter":
        max_boost = 7
        for pos_group in ['G', 'F', 'C']:
            if star_minutes_out[pos_group] > 0:
                extra_minutes += star_minutes_out[pos_group] * 0.20 * pos_mult[pos_group]
            if starter_minutes_out[pos_group] > 0:
                extra_minutes += starter_minutes_out[pos_group] * 0.18 * pos_mult[pos_group]
                max_boost = max(max_boost, 7)

    elif player_role == "rotation":
        for pos_group in ['G', 'F', 'C']:
            if rotation_minutes_out[pos_group] > 0:
                extra_minutes += rotation_minutes_out[pos_group] * 0.35 * pos_mult[pos_group]
                max_boost = 8
            if bench_minutes_out[pos_group] > 0:
                extra_minutes += bench_minutes_out[pos_group] * 0.25 * pos_mult[pos_group]
                max_boost = max(max_boost, 8)
            # Rotation guys are the primary beneficiaries when starters sit
            if starter_minutes_out[pos_group] > 0:
                frac = 0.18 if heavy_absence else 0.10
                extra_minutes += starter_minutes_out[pos_group] * frac * pos_mult[pos_group]
                max_boost = max(max_boost, 10)
            if star_minutes_out[pos_group] > 0:
                frac = 0.12 if heavy_absence else 0.06
                extra_minutes += star_minutes_out[pos_group] * frac * pos_mult[pos_group]
                max_boost = max(max_boost, 10)

    elif player_role == "bench":
        max_boost = 8
        for pos_group in ['G', 'F', 'C']:
            if bench_minutes_out[pos_group] > 0:
                extra_minutes += bench_minutes_out[pos_group] * 0.30 * pos_mult[pos_group]
            if deep_bench_minutes_out[pos_group] > 0:
                extra_minutes += deep_bench_minutes_out[pos_group] * 0.20 * pos_mult[pos_group]
                max_boost = max(max_boost, 8)
            # Bench absorbs from rotation and higher when shorthanded
            if rotation_minutes_out[pos_group] > 0:
                frac = 0.25 if heavy_absence else 0.15
                extra_minutes += rotation_minutes_out[pos_group] * frac * pos_mult[pos_group]
                max_boost = max(max_boost, 10)
            if starter_minutes_out[pos_group] > 0:
                frac = 0.12 if heavy_absence else 0.05
                extra_minutes += starter_minutes_out[pos_group] * frac * pos_mult[pos_group]
                max_boost = max(max_boost, 12)
            if star_minutes_out[pos_group] > 0 and heavy_absence:
                extra_minutes += star_minutes_out[pos_group] * 0.08 * pos_mult[pos_group]
                max_boost = max(max_boost, 12)

    else:  # deep_bench
        for pos_group in ['G', 'F', 'C']:
            if deep_bench_minutes_out[pos_group] > 0:
                extra_minutes += deep_bench_minutes_out[pos_group] * 0.25 * pos_mult[pos_group]
                max_boost = 10
            if bench_minutes_out[pos_group] > 0:
                extra_minutes += bench_minutes_out[pos_group] * 0.20 * pos_mult[pos_group]
                max_boost = max(max_boost, 10)
            # Deep bench becomes rotation when team is gutted
            if rotation_minutes_out[pos_group] > 0:
                frac = 0.18 if heavy_absence else 0.08
                extra_minutes += rotation_minutes_out[pos_group] * frac * pos_mult[pos_group]
                max_boost = max(max_boost, 12)
            if starter_minutes_out[pos_group] > 0 and heavy_absence:
                extra_minutes += starter_minutes_out[pos_group] * 0.10 * pos_mult[pos_group]
                max_boost = max(max_boost, 14)
            if star_minutes_out[pos_group] > 0 and heavy_absence:
                extra_minutes += star_minutes_out[pos_group] * 0.06 * pos_mult[pos_group]
                max_boost = max(max_boost, 14)

    # Apply the cap
    if max_boost > 0:
        extra_minutes = min(extra_minutes, max_boost)

    return round(extra_minutes, 1)


def calculate_usage_boost(
    teammates_out: List[str],
    player_minutes_map: Dict[int, float]
) -> float:
    """
    Calculate usage rate boost when high-usage teammates are out.

    The cap scales with total missing minutes: baseline 12% for a single
    absence, up to 30% when 90+ minutes of teammates are missing.

    Returns:
        Usage multiplier (1.0 = no change, 1.1 = 10% boost)
    """
    if not teammates_out:
        return 1.0

    usage_boost = 1.0
    total_missing_mins = 0.0

    for out_player in teammates_out:
        out_mins = player_minutes_map.get(int(out_player), 0)

        # Only apply usage boost if player has actual minutes
        # Players with 0 minutes are out of rotation - no usage to redistribute
        if out_mins == 0:
            continue

        total_missing_mins += out_mins

        # Higher minute players = more usage to redistribute
        if out_mins >= 34:  # Star player
            usage_boost += 0.10
        elif out_mins >= 30:  # High-usage starter
            usage_boost += 0.07
        elif out_mins >= 25:  # Starter
            usage_boost += 0.05
        elif out_mins >= 18:  # Rotation
            usage_boost += 0.02

    # Dynamic cap: 12% baseline, scales to 30% when 90+ total minutes are missing
    # When 3+ rotation players are out the remaining guys see massive usage jumps
    cap = 1.12 + max(0.0, min(0.18, (total_missing_mins - 30) / 60 * 0.18))
    return min(usage_boost, cap)


def calculate_injury_adjustments(
    player_id: str,
    player_team_id: int,
    opponent_team_id: int,
    teammates_out: List[str],
    opponents_out: List[str],
    player_minutes_map: Dict[int, float],
    players_df: pd.DataFrame,
    without_player_stats: Optional[Dict] = None,
) -> Dict[str, any]:
    """
    Calculate all injury-related adjustments for a player's prediction.

    When *without_player_stats* is provided (from without_player_stats.py), the
    generic role-based multipliers are blended with empirical "without X" data:
        final = blend_weight * historical + (1 - blend_weight) * generic
    where blend_weight scales from 0.30 (3 games) up to 0.70 (>=7 games).

    Args:
        player_id: The player being predicted
        player_team_id: Player's team ID
        opponent_team_id: Opponent's team ID
        teammates_out: List of teammate player IDs who are out
        opponents_out: List of opponent player IDs who are out
        player_minutes_map: Dict of player_id -> average minutes
        players_df: DataFrame with player info
        without_player_stats: Optional dict from without_player_stats.get_without_player_stats()

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
    
    # Get player position from players_df
    player_position = None
    try:
        player_row = players_df[players_df['PERSON_ID'] == int(player_id)]
        if len(player_row) > 0:
            player_position = player_row['POSITION'].iloc[0]
    except:
        pass
    
    # Build positions map for injured teammates
    teammates_positions_map = {}
    for out_player_id in teammates_out:
        try:
            out_player_row = players_df[players_df['PERSON_ID'] == int(out_player_id)]
            if len(out_player_row) > 0:
                teammates_positions_map[int(out_player_id)] = out_player_row['POSITION'].iloc[0]
        except:
            pass
    
    # === TEAMMATE INJURIES ===
    if teammates_out:
        # Calculate minutes redistribution (now with position awareness)
        extra_minutes = calculate_minutes_redistribution(
            teammates_out, 
            player_mins, 
            player_minutes_map,
            player_position=player_position,
            teammates_positions_map=teammates_positions_map
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

        # Total minutes missing from injured teammates
        total_missing_mins = sum(
            player_minutes_map.get(int(p), 0) for p in teammates_out
        )
        # Dynamic cap uplift: scales from 0 at ≤30 missing mins to +0.15 at 90+
        # When 3 starters are out remaining guys realistically see 20-30% stat jumps
        cap_uplift = max(0.0, min(0.15, (total_missing_mins - 30) / 60 * 0.15))

        # Role-based caps for total injury boost, scaled by missing-minutes severity
        if player_mins >= 32:  # Star - can handle bigger boost
            max_pts_mult = 1.12 + cap_uplift  # 12% base → up to 27%
        elif player_mins >= 28:  # Starter
            max_pts_mult = 1.10 + cap_uplift  # 10% base → up to 25%
        elif player_mins >= 22:  # Rotation
            max_pts_mult = 1.09 + cap_uplift  # 9% base → up to 24%
        elif player_mins >= 15:  # Bench
            max_pts_mult = 1.08 + cap_uplift  # 8% base → up to 23%
        else:  # Deep bench
            max_pts_mult = 1.07 + cap_uplift  # 7% base → up to 22%
        
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

        # === HISTORICAL "WITHOUT X" BLENDING ===
        # If empirical data from without_player_stats.py is available, blend it
        # with the generic multipliers computed above.  More games = more weight
        # placed on the historical data vs the formula.
        if without_player_stats and without_player_stats.get('multipliers'):
            sample_size = without_player_stats.get('sample_size', 0)
            # blend_weight: 0.30 at 3 games → 0.70 at >=7 games
            blend_weight = min(0.70, max(0.30, sample_size / 10.0))
            hist_mults = without_player_stats['multipliers']

            for stat in ('PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M', 'FTM'):
                generic_val = adjustments.get(stat, 1.0)
                historical_val = hist_mults.get(stat, 1.0)
                adjustments[stat] = round(
                    blend_weight * historical_val + (1.0 - blend_weight) * generic_val, 3
                )

            method = without_player_stats.get('method', 'combined')
            label = 'combined absences' if method == 'combined' else 'primary absentee'
            adjustments['factors'].append(
                f"Historical without-X ({sample_size} games, {int(blend_weight * 100)}% weight, {label})"
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

