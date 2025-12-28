import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'new-streamlit-app', 'player-app'))

import streamlit as st
import player_functions as pf
import team_defensive_stats as tds
import prediction_model as pm
import prediction_features as pf_features
import matchup_stats as ms
import vegas_lines as vl
import prediction_tracker as pt
import injury_adjustments as inj
import backtest as bt
import injury_report as ir
import player_similarity as ps
import pandas as pd
import nba_api.stats.endpoints
from datetime import datetime, date, timedelta
import math
import requests

def normalize_team_minutes(statlines_list, target_minutes=240.0, out_player_ids=None, bulk_game_logs=None, game_date=None):
    """
    Normalize minutes for each team to sum to exactly target_minutes (default 240).
    Scales all stats proportionally based on minutes changes.
    Ensures minutes sum to exactly target_minutes even after capping at 48.
    
    Args:
        statlines_list: List of statline dicts with 'MIN', 'is_away', and stat fields
        target_minutes: Target total minutes per team (default 240)
        out_player_ids: Set of player IDs marked OUT/DOUBTFUL (optional)
        bulk_game_logs: DataFrame with all player game logs for recent activity check (optional)
        game_date: Date of the game (YYYY-MM-DD) for recent activity check (optional)
    
    Returns:
        Updated statlines_list with normalized minutes and scaled stats
    """
    # Separate by team
    away_statlines = [s for s in statlines_list if s['is_away']]
    home_statlines = [s for s in statlines_list if not s['is_away']]
    
    def normalize_team(team_statlines, is_away_team):
        if not team_statlines:
            return
        
        # Store original minutes for scaling
        for statline in team_statlines:
            statline['_original_min'] = statline['MIN']
        
        # Get original season minutes to determine player role
        # Use _original_season_minutes if available, otherwise use _original_min
        # IMPORTANT: Set this BEFORE filtering so we can use it in filter logic
        for statline in team_statlines:
            original_season_min = statline.get('_original_season_minutes')
            if original_season_min is None:
                original_season_min = statline.get('_original_min', statline['MIN'])
            statline['_role_baseline_min'] = original_season_min
        
        # FILTER OUT PLAYERS WHO SHOULDN'T PLAY BEFORE SELECTING TOP 10
        # IMPORTANT: Always modify the original list in place, never create new lists
        # 1. Filter out players marked OUT/DOUBTFUL by setting their minutes to 0
        if out_player_ids:
            for statline in team_statlines:
                if statline.get('player_id') in out_player_ids:
                    statline['MIN'] = 0.0
        
        # 2. Filter out players who haven't played recently (if bulk_game_logs available)
        # Set their minutes to 0 instead of removing them from the list
        if bulk_game_logs is not None and len(bulk_game_logs) > 0 and game_date:
            try:
                game_date_dt = pd.to_datetime(game_date)
                # Check if player has played in last 14 days
                cutoff_date = game_date_dt - timedelta(days=14)
                
                active_player_ids = set()
                players_with_any_games = set()  # Track players who have ANY game logs
                
                for statline in team_statlines:
                    player_id_str = statline.get('player_id')
                    if not player_id_str:
                        continue
                    
                    try:
                        player_id_int = int(player_id_str)
                        # Get ALL player's games (not just recent)
                        all_player_logs = bulk_game_logs[
                            bulk_game_logs['PLAYER_ID'] == player_id_int
                        ]
                        
                        # Track if player has ANY game logs at all
                        if len(all_player_logs) > 0:
                            players_with_any_games.add(player_id_str)
                            
                            # Get player's recent games (last 14 days)
                            player_logs = all_player_logs[
                                pd.to_datetime(all_player_logs['GAME_DATE']) >= cutoff_date
                            ]
                            
                            # If player has played at least 1 game in last 14 days, include them
                            if len(player_logs) > 0:
                                active_player_ids.add(player_id_str)
                    except (ValueError, TypeError):
                        # If we can't parse player_id, skip this check for this player
                        continue
                
                # Set minutes to 0 for inactive players (unless they're stars/starters)
                # CRITICAL FIX: Exclude players who have NEVER played in NBA regardless of role
                for statline in team_statlines:
                    player_id_str = statline.get('player_id')
                    role_baseline = statline.get('_role_baseline_min', statline.get('_original_season_minutes', 0))
                    
                    # If player has NO game logs at all, exclude them regardless of role
                    if player_id_str not in players_with_any_games:
                        statline['MIN'] = 0.0
                    # Only set to 0 if not active AND not a star/starter (existing logic)
                    elif player_id_str not in active_player_ids and role_baseline < 22:
                        statline['MIN'] = 0.0
            except Exception as e:
                # If there's an error checking recent activity, skip this filter
                pass
        
        # Limit to top 10 players per team, prioritizing by role (stars/starters first), then by projected minutes
        # Sort by role priority first (higher role_baseline_min = higher priority), then by current MIN
        def sort_key(statline):
            baseline = statline.get('_role_baseline_min', 0)
            current_min = statline.get('MIN', 0)
            # Return tuple: (role_priority, current_min) where role_priority is inverted (higher = better)
            # Stars (>=32) get priority 100, Starters (>=28) get 80, Rotation (>=22) get 60, Bench (>=15) get 40, Deep Bench get 20
            if baseline >= 32:
                role_priority = 100
            elif baseline >= 28:
                role_priority = 80
            elif baseline >= 22:
                role_priority = 60
            elif baseline >= 15:
                role_priority = 40
            else:
                role_priority = 20
            return (role_priority, current_min)
        
        team_statlines.sort(key=sort_key, reverse=True)
        
        # Enforce strict 10-player limit
        # Keep top 10 players by priority (stars/starters prioritized, but still max 10 total)
        stars_and_starters = [s for s in team_statlines if s.get('_role_baseline_min', 0) >= 28]
        other_players = [s for s in team_statlines if s.get('_role_baseline_min', 0) < 28]
        
        # If we have more than 10 stars/starters, keep only top 10 by priority
        if len(stars_and_starters) > 10:
            stars_and_starters = stars_and_starters[:10]
            # No room for other players
            players_to_keep = stars_and_starters
        else:
            # Keep all stars/starters, then fill remaining slots with other players
            remaining_slots = 10 - len(stars_and_starters)
            players_to_keep = stars_and_starters + other_players[:max(0, remaining_slots)]
        
        # Create set of player IDs to keep for reliable comparison
        # Filter out None values to avoid comparison issues
        players_to_keep_ids = {s.get('player_id') for s in players_to_keep if s.get('player_id') is not None}
        
        # Set minutes to 0 for players not in top 10
        for statline in team_statlines:
            player_id = statline.get('player_id')
            # If player_id is None or not in keep list, set minutes to 0
            if player_id is None or player_id not in players_to_keep_ids:
                statline['MIN'] = 0.0
        
        # CRITICAL: Double-check we have exactly 10 or fewer players with MIN > 0
        # Get all players with MIN > 0
        active_players_check = [s for s in team_statlines if s.get('MIN', 0) > 0.01]
        
        # If we have more than 10, force it down to 10 by keeping only top 10 by minutes
        if len(active_players_check) > 10:
            # Sort by minutes descending
            active_players_check.sort(key=lambda x: x.get('MIN', 0), reverse=True)
            # Set minutes to 0 for players beyond the top 10
            for statline in active_players_check[10:]:
                statline['MIN'] = 0.0
            # Keep only top 10
            active_players_check = active_players_check[:10]
        
        # Filter out players with 0 minutes for normalization (but keep them in the list)
        active_players = [s for s in team_statlines if s.get('MIN', 0) > 0.01]
        
        # Final safety check: ensure we have exactly 10 or fewer active players
        if len(active_players) > 10:
            # If somehow we still have more than 10, keep only top 10 by current minutes
            active_players.sort(key=lambda x: x.get('MIN', 0), reverse=True)
            excess_players = active_players[10:]
            for statline in excess_players:
                statline['MIN'] = 0.0
            active_players = active_players[:10]
        
        if not active_players:
            return
        
        # Use only active players for normalization calculations
        team_statlines_for_norm = active_players
        
        # Categorize players by role based on original season minutes (only active players)
        # Stars: >= 32 MPG, Starters: >= 28 MPG, Rotation: >= 22 MPG, Bench: >= 15 MPG, Deep Bench: < 15 MPG
        stars = [s for s in team_statlines_for_norm if s['_role_baseline_min'] >= 32]
        starters = [s for s in team_statlines_for_norm if 28 <= s['_role_baseline_min'] < 32]
        rotation = [s for s in team_statlines_for_norm if 22 <= s['_role_baseline_min'] < 28]
        bench = [s for s in team_statlines_for_norm if 15 <= s['_role_baseline_min'] < 22]
        deep_bench = [s for s in team_statlines_for_norm if s['_role_baseline_min'] < 15]
        
        # Distribute remaining minutes prioritizing higher-role players
        # Priority order: Stars > Starters > Rotation > Bench > Deep Bench
        priority_groups = [stars, starters, rotation, bench, deep_bench]
        
        # Calculate initial total (use only active players)
        total_minutes = sum(s['MIN'] for s in team_statlines_for_norm)
        
        if total_minutes <= 0:
            return
        
        # Step 1: Scale proportionally to target
        scale_factor = target_minutes / total_minutes
        for statline in team_statlines_for_norm:
            statline['MIN'] *= scale_factor
        
        # Step 2: Apply role-based floors and targets
        # Stars (>=32 MPG baseline) should get closer to their baseline (33-38 range)
        # Starters (28-31 MPG baseline) should get closer to their baseline (28-35 range)
        for statline in stars:
            baseline = statline['_role_baseline_min']
            # Stars: target their baseline, but ensure minimum 32 MPG
            target_min = max(32.0, baseline * 0.85)  # At least 85% of baseline, minimum 32
            if statline['MIN'] < target_min:
                statline['MIN'] = target_min
        
        for statline in starters:
            baseline = statline['_role_baseline_min']
            # Starters: target their baseline, but ensure minimum 26 MPG
            target_min = max(26.0, baseline * 0.85)  # At least 85% of baseline, minimum 26
            if statline['MIN'] < target_min:
                statline['MIN'] = target_min
        
        # Step 3: Check if floors pushed us over target
        total_after_floors = sum(s['MIN'] for s in team_statlines_for_norm)
        if total_after_floors > target_minutes:
            # Scale down, but protect stars/starters more
            # First, try to reduce lower-role players before scaling down stars/starters
            excess = total_after_floors - target_minutes
            
            # Calculate how much we can reduce from lower-role players
            reducible_from_lower = 0.0
            for group in [deep_bench, bench, rotation]:
                for statline in group:
                    current = statline['MIN']
                    # Can reduce up to 50% of their minutes
                    reducible_from_lower += current * 0.5
            
            if reducible_from_lower >= excess:
                # Can cover excess by reducing lower-role players only
                scale_down_lower = 1.0 - (excess / reducible_from_lower)
                for group in [deep_bench, bench, rotation]:
                    for statline in group:
                        statline['MIN'] *= scale_down_lower
            else:
                # Need to scale down everyone, but less aggressively for stars/starters
                # Scale stars/starters by 95%, others by 100%
                for statline in stars + starters:
                    statline['MIN'] *= 0.95  # Only reduce by 5%
                
                # Recalculate and scale others more
                remaining_excess = target_minutes - sum(s['MIN'] for s in team_statlines_for_norm)
                if remaining_excess < 0:
                    scale_down = target_minutes / sum(s['MIN'] for s in team_statlines_for_norm)
                    for statline in rotation + bench + deep_bench:
                        statline['MIN'] *= scale_down
        
        # Step 4: Apply role-based caps
        for statline in stars:
            if statline['MIN'] > 40.0:
                statline['MIN'] = 40.0
        for statline in starters:
            if statline['MIN'] > 38.0:
                statline['MIN'] = 38.0
        for statline in rotation:
            if statline['MIN'] > 32.0:
                statline['MIN'] = 32.0
        for statline in bench:
            if statline['MIN'] > 25.0:
                statline['MIN'] = 25.0
        for statline in deep_bench:
            if statline['MIN'] > 12.0:
                statline['MIN'] = 12.0
        
        # Step 5: Distribute remaining minutes if under target
        capped_total = sum(s['MIN'] for s in team_statlines_for_norm)
        remaining_minutes = target_minutes - capped_total
        
        if remaining_minutes > 0.01:
            # Distribute remaining minutes prioritizing higher-role players
            distributed = 0.0
            for group in priority_groups:
                if abs(remaining_minutes - distributed) < 0.01:
                    break
                
                # Get players in this group who aren't at their cap
                available_players = []
                for statline in group:
                    baseline = statline['_role_baseline_min']
                    cap = 40.0 if baseline >= 32 else (38.0 if baseline >= 28 else (32.0 if baseline >= 22 else (25.0 if baseline >= 15 else 12.0)))
                    if statline['MIN'] < cap - 0.01:
                        available_players.append(statline)
                
                if not available_players:
                    continue
                
                # Distribute proportionally based on current minutes
                group_total = sum(s['MIN'] for s in available_players)
                if group_total > 0:
                    group_remaining = remaining_minutes - distributed
                    for statline in available_players:
                        baseline = statline['_role_baseline_min']
                        cap = 40.0 if baseline >= 32 else (38.0 if baseline >= 28 else (32.0 if baseline >= 22 else (25.0 if baseline >= 15 else 12.0)))
                        additional = group_remaining * (statline['MIN'] / group_total)
                        old_min = statline['MIN']
                        statline['MIN'] = min(statline['MIN'] + additional, cap)
                        actual_added = statline['MIN'] - old_min
                        distributed += actual_added
        
        # Step 6: Final safety check - ensure exact total
        # Protect stars/starters from being scaled down too much
        final_total = sum(s['MIN'] for s in team_statlines_for_norm)
        if abs(final_total - target_minutes) > 0.01:
            # Final proportional scaling, but protect stars/starters
            if final_total > target_minutes:
                # Over target - scale down, but protect stars/starters
                excess = final_total - target_minutes
                # Try to reduce from lower-role players first
                lower_role_total = sum(s['MIN'] for s in rotation + bench + deep_bench)
                if lower_role_total >= excess:
                    scale_down = (lower_role_total - excess) / lower_role_total
                    for statline in rotation + bench + deep_bench:
                        statline['MIN'] *= scale_down
                else:
                    # Need to scale everyone, but less for stars/starters
                    scale_factor = target_minutes / final_total
                    for statline in stars + starters:
                        # Only scale down stars/starters if they're still above their baseline
                        baseline = statline['_role_baseline_min']
                        new_min = statline['MIN'] * scale_factor
                        # Don't go below 90% of baseline for stars/starters
                        min_protected = baseline * 0.90
                        statline['MIN'] = max(new_min, min_protected)
                    
                    # Recalculate and scale others to make up difference
                    current_total = sum(s['MIN'] for s in team_statlines_for_norm)
                    remaining = target_minutes - current_total
                    if abs(remaining) > 0.01:
                        other_total = sum(s['MIN'] for s in rotation + bench + deep_bench)
                        if other_total > 0:
                            scale_others = (other_total + remaining) / other_total
                            for statline in rotation + bench + deep_bench:
                                statline['MIN'] *= scale_others
            else:
                # Under target - scale up proportionally
                final_scale = target_minutes / final_total
                for statline in team_statlines_for_norm:
                    statline['MIN'] *= final_scale
                    # Reapply caps after scaling
                    baseline = statline['_role_baseline_min']
                    if baseline >= 32:
                        statline['MIN'] = min(statline['MIN'], 40.0)
                    elif baseline >= 28:
                        statline['MIN'] = min(statline['MIN'], 38.0)
                    elif baseline >= 22:
                        statline['MIN'] = min(statline['MIN'], 32.0)
                    elif baseline >= 15:
                        statline['MIN'] = min(statline['MIN'], 25.0)
                    else:
                        statline['MIN'] = min(statline['MIN'], 12.0)
        
        # Step 7: Final validation - ensure we have exactly 10 or fewer active players
        # and total equals exactly 240
        # Check ALL statlines in team_statlines to catch any that might have been missed
        final_active = [s for s in team_statlines if s.get('MIN', 0) > 0.01]
        
        if len(final_active) > 10:
            # If somehow we have more than 10, keep only top 10 by minutes
            final_active.sort(key=lambda x: x.get('MIN', 0), reverse=True)
            excess_players = final_active[10:]
            for statline in excess_players:
                statline['MIN'] = 0.0
            # Recalculate total with only top 10
            final_active = final_active[:10]
            final_total = sum(s['MIN'] for s in final_active)
            if abs(final_total - target_minutes) > 0.01 and final_total > 0:
                # Scale to exactly 240
                final_scale = target_minutes / final_total
                for statline in final_active:
                    statline['MIN'] *= final_scale
        else:
            # Ensure total is exactly 240
            final_total = sum(s['MIN'] for s in final_active) if final_active else 0
            if abs(final_total - target_minutes) > 0.01 and final_total > 0:
                final_scale = target_minutes / final_total
                for statline in final_active:
                    statline['MIN'] *= final_scale
        
        # Step 8: Absolute final check - guarantee exactly 10 players and exactly 240 minutes
        # This is a safety net to catch any edge cases
        final_check_active = [s for s in team_statlines if s.get('MIN', 0) > 0.01]
        final_check_total = sum(s['MIN'] for s in final_check_active)
        
        # Force exactly 10 players maximum
        if len(final_check_active) > 10:
            final_check_active.sort(key=lambda x: x.get('MIN', 0), reverse=True)
            for statline in final_check_active[10:]:
                statline['MIN'] = 0.0
            final_check_active = final_check_active[:10]
            final_check_total = sum(s['MIN'] for s in final_check_active)
        
        # Force exactly 240 minutes
        if abs(final_check_total - target_minutes) > 0.01 and final_check_total > 0:
            emergency_scale = target_minutes / final_check_total
            for statline in final_check_active:
                statline['MIN'] *= emergency_scale
        
        # Scale all stats proportionally based on minutes change
        # CRITICAL: Scale BASE stats first (before injury adjustments), then re-apply injury multipliers
        # This prevents double-boosting: normalize → then adjust for injuries (not adjust → normalize)
        # Only scale stats for active players (those with MIN > 0)
        for statline in team_statlines:
            # If player has 0 minutes, set all stats to 0
            if statline['MIN'] == 0 or statline['MIN'] < 0.01:
                statline['PTS'] = 0.0
                statline['REB'] = 0.0
                statline['AST'] = 0.0
                statline['STL'] = 0.0
                statline['BLK'] = 0.0
                statline['TOV'] = 0.0
                statline['FG3M'] = 0.0
                statline['FTM'] = 0.0
                statline['PRA'] = 0.0
                statline['RA'] = 0.0
                statline['FPTS'] = 0.0
                continue
            
            # Get base stats (before injury adjustments) or fall back to current stats
            base_stats = statline.get('_base_stats')
            if base_stats is None:
                # Fallback: use current stats as base (for backwards compatibility)
                base_stats = {
                    'PTS': statline.get('PTS', 0.0),
                    'REB': statline.get('REB', 0.0),
                    'AST': statline.get('AST', 0.0),
                    'STL': statline.get('STL', 0.0),
                    'BLK': statline.get('BLK', 0.0),
                    'TOV': statline.get('TOV', 0.0),
                    'FG3M': statline.get('FG3M', 0.0),
                    'FTM': statline.get('FTM', 0.0)
                }
            
            # Get scaling baseline: use injury-adjusted minutes if available, otherwise original season minutes
            # This prevents over-scaling when injuries boost minutes
            scaling_baseline = statline.get('_injury_adjusted_minutes')
            if scaling_baseline is None or scaling_baseline <= 0:
                scaling_baseline = statline.get('_original_season_minutes')
            if scaling_baseline is None or scaling_baseline <= 0:
                scaling_baseline = statline.get('_original_min', statline['MIN'])
            
            # Step 1: Scale BASE stats based on normalized minutes ratio
            # Use injury-adjusted minutes as baseline to prevent over-scaling
            if scaling_baseline > 0:
                minutes_ratio = statline['MIN'] / scaling_baseline
                # Scale stats at 80% of direct proportion (reduced from 90% to be more conservative)
                # This accounts for diminishing returns when minutes increase
                stat_scaling_factor = 1.0 + (minutes_ratio - 1.0) * 0.8
                
                # Scale base stats
                scaled_pts = base_stats['PTS'] * stat_scaling_factor
                scaled_reb = base_stats['REB'] * stat_scaling_factor
                scaled_ast = base_stats['AST'] * stat_scaling_factor
                scaled_stl = base_stats['STL'] * stat_scaling_factor
                scaled_blk = base_stats['BLK'] * stat_scaling_factor
                scaled_tov = base_stats['TOV'] * stat_scaling_factor
                scaled_fg3m = base_stats['FG3M'] * stat_scaling_factor
                scaled_ftm = base_stats['FTM'] * stat_scaling_factor
            else:
                # No scaling if original minutes are 0 or invalid
                scaled_pts = base_stats['PTS']
                scaled_reb = base_stats['REB']
                scaled_ast = base_stats['AST']
                scaled_stl = base_stats['STL']
                scaled_blk = base_stats['BLK']
                scaled_tov = base_stats['TOV']
                scaled_fg3m = base_stats['FG3M']
                scaled_ftm = base_stats['FTM']
            
            # Step 2: Re-apply injury multipliers to scaled base stats
            injury_multipliers = statline.get('_injury_multipliers')
            if injury_multipliers:
                statline['PTS'] = scaled_pts * injury_multipliers.get('PTS', 1.0)
                statline['REB'] = scaled_reb * injury_multipliers.get('REB', 1.0)
                statline['AST'] = scaled_ast * injury_multipliers.get('AST', 1.0)
                statline['STL'] = scaled_stl * injury_multipliers.get('STL', 1.0)
                statline['BLK'] = scaled_blk * injury_multipliers.get('BLK', 1.0)
                statline['TOV'] = scaled_tov * injury_multipliers.get('TOV', 1.0)
                statline['FG3M'] = scaled_fg3m * injury_multipliers.get('FG3M', 1.0)
                statline['FTM'] = scaled_ftm * injury_multipliers.get('FTM', 1.0)
            else:
                # No injury adjustments, use scaled base stats directly
                statline['PTS'] = scaled_pts
                statline['REB'] = scaled_reb
                statline['AST'] = scaled_ast
                statline['STL'] = scaled_stl
                statline['BLK'] = scaled_blk
                statline['TOV'] = scaled_tov
                statline['FG3M'] = scaled_fg3m
                statline['FTM'] = scaled_ftm
            
            # Recalculate derived stats after scaling and injury adjustments
            statline['PRA'] = statline.get('PTS', 0.0) + statline.get('REB', 0.0) + statline.get('AST', 0.0)
            statline['RA'] = statline.get('REB', 0.0) + statline.get('AST', 0.0)
            # FPTS using Underdog formula: PTS*1 + REB*1.2 + AST*1.5 + STL*3 + BLK*3 - TOV*1
            statline['FPTS'] = (
                statline.get('PTS', 0.0) * 1.0 + 
                statline.get('REB', 0.0) * 1.2 + 
                statline.get('AST', 0.0) * 1.5 + 
                statline.get('STL', 0.0) * 3.0 + 
                statline.get('BLK', 0.0) * 3.0 - 
                statline.get('TOV', 0.0) * 1.0
            )
    
    # Normalize both teams
    normalize_team(away_statlines, True)
    normalize_team(home_statlines, False)
    
    return statlines_list

st.set_page_config(layout="wide")
st.title("NBA Player Data")

# Cache players dataframe to avoid repeated API calls
@st.cache_data
def get_cached_players_dataframe():
    """Cache players dataframe from PlayerIndex endpoint"""
    return pf.get_players_dataframe()

@st.cache_data
def get_cached_player_list():
    """Cache player list from PlayerIndex endpoint"""
    return pf.get_player_list()

@st.cache_data
def get_player_name_map(player_ids_list, players_df):
    """Cache player names using the players dataframe"""
    return {pid: pf.get_player_name(pid, players_df) for pid in player_ids_list}

# Cache team defensive shooting data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_shooting_data():
    """Cache team shooting data from pbpstats API"""
    try:
        team_stats, opp_team_stats = tds.load_shooting_data()
        return team_stats, opp_team_stats, None
    except Exception as e:
        return None, None, str(e)

# Cache player shooting data
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_cached_player_shooting_data():
    """Cache player shooting data from pbpstats API"""
    try:
        player_stats = tds.load_player_shooting_data()
        return player_stats, None
    except Exception as e:
        return None, str(e)

# Function to fetch matchups for a given date
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_matchups_for_date(selected_date):
    """Fetch NBA matchups for a given date from the API"""
    try:
        import pytz
        from datetime import datetime
        
        # Get schedule data
        league_schedule = nba_api.stats.endpoints.ScheduleLeagueV2(
            league_id='00',
            season='2025-26'
        ).get_data_frames()[0]
        
        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        league_schedule['matchup'] = league_schedule['awayTeam_teamTricode'] + ' @ ' + league_schedule['homeTeam_teamTricode']
        
        # Compare date parts only to handle datetime objects with time components
        date_games = league_schedule[
            league_schedule['dateGame'].dt.date == selected_date
        ]
        
        if len(date_games) > 0:
            matchups = []
            for _, row in date_games.iterrows():
                matchup_str = row['matchup']
                away_team = row['awayTeam_teamTricode']
                home_team = row['homeTeam_teamTricode']
                away_team_id = row['awayTeam_teamId']
                home_team_id = row['homeTeam_teamId']
                game_id = str(row.get('gameId', ''))
                
                # Try to get game time from gameDate field
                game_time_str = None
                game_date_raw = row.get('gameDate', '')
                
                if pd.notna(game_date_raw) and game_date_raw:
                    try:
                        # Parse the gameDate - it might be in UTC or have time info
                        game_dt = pd.to_datetime(game_date_raw)
                        
                        # Check if it's not just midnight (which means no time info)
                        if game_dt.hour != 0 or game_dt.minute != 0:
                            # Has actual time info - assume UTC
                            if game_dt.tzinfo is None:
                                utc = pytz.UTC
                                game_dt = utc.localize(game_dt)
                            
                            # Convert to Central Time
                            central = pytz.timezone('US/Central')
                            game_dt_ct = game_dt.astimezone(central)
                            
                            # Format as "7 PM CT"
                            hour_12 = game_dt_ct.strftime('%I').lstrip('0') or '12'
                            am_pm = game_dt_ct.strftime('%p')
                            game_time_str = f"{hour_12} {am_pm} CT"
                    except:
                        pass
                
                matchups.append({
                    'matchup': matchup_str,
                    'away_team': away_team,
                    'home_team': home_team,
                    'away_team_id': away_team_id,
                    'home_team_id': home_team_id,
                    'game_time': game_time_str,
                    'game_date': game_date_raw
                })
            return matchups, None  # Return matchups and error (None)
        else:
            return [], None  # No games on this date
    except Exception as e:
        return [], str(e)  # Return empty list and error message

# Get cached players dataframe and player list
players_df = get_cached_players_dataframe()

# Get cached player stats (including average minutes) for sorting
@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_cached_player_stats():
    """Get player stats including average minutes for sorting"""
    try:
        import nba_api.stats.endpoints as endpoints
        player_stats = endpoints.LeagueDashPlayerStats(
            season='2025-26',
            league_id_nullable='00',
            per_mode_detailed='PerGame',
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        # Convert PLAYER_ID to int for consistent key type
        minutes_dict = {}
        for _, row in player_stats.iterrows():
            player_id = int(row['PLAYER_ID'])
            minutes = float(row['MIN']) if pd.notna(row['MIN']) else 0.0
            minutes_dict[player_id] = minutes
        return minutes_dict
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        return {}

player_minutes_map = get_cached_player_stats()

# Cached function to fetch injury report for a specific date
@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_cached_injury_report_for_date(selected_date):
    """Fetch and cache injury report for a specific date"""
    try:
        injury_df, status_msg = ir.fetch_injuries_for_date(report_date=selected_date)
        if injury_df is not None and len(injury_df) > 0:
            return injury_df, status_msg, None
        else:
            return pd.DataFrame(), status_msg, "No injuries found"
    except Exception as e:
        return pd.DataFrame(), "", str(e)

# Validate players_df
if players_df is None or len(players_df) == 0:
    st.error("Failed to load players data. Please clear the cache and restart the app.")
    st.stop()

if 'PERSON_ID' not in players_df.columns:
    st.error(f"Players dataframe has incorrect format. Available columns: {list(players_df.columns)}")
    st.error("Please clear the Streamlit cache (☰ → Settings → Clear cache) and restart the app.")
    st.stop()

player_ids_list = get_cached_player_list()
player_name_map = get_player_name_map(player_ids_list, players_df)

# Matchup filter section
col_date, col_matchup = st.columns([0.3, 0.7])

with col_date:
    # Date selector - default to today
    selected_date = st.date_input(
        "Select Date:",
        value=date.today(),
        key="matchup_date"
    )

with col_matchup:
    # Get matchups for selected date
    matchups, matchup_error = get_matchups_for_date(selected_date)
    
    # Show error if API call failed
    if matchup_error:
        st.warning(f"⚠️ Could not fetch matchups: {matchup_error}")
        matchups = []
    
    # Matchup dropdown
    if matchups:
        # Format matchup options
        matchup_options = ["All Matchups"]
        for m in matchups:
            matchup_options.append(m['matchup'])
        
        selected_matchup_str = st.selectbox(
            "Select Matchup:",
            options=matchup_options,
            key="matchup_selector",
            help="Select a matchup to filter players, or 'All Matchups' to see everyone"
        )
    else:
        selected_matchup_str = "All Players"
        if not matchup_error:  # Only show info if no error (meaning no games on this date)
            st.info("ℹ️ No games scheduled for this date. Showing all players.")

# Fetch injury report for the selected date
# This needs to happen after date selection but before injury section
injury_report_df, injury_report_url, injury_load_error = get_cached_injury_report_for_date(selected_date)

# Clear processed matchups cache when date changes (so injuries get re-processed)
if 'last_injury_date' not in st.session_state or st.session_state.last_injury_date != selected_date:
    st.session_state.last_injury_date = selected_date
    st.session_state.processed_matchups = {}  # Clear cached matchup injury data

# Filter players based on selected matchup
filtered_player_ids_list = player_ids_list.copy()
selected_team_ids = None
matchup_away_team_id = None
matchup_home_team_id = None
matchup_away_team_abbr = None
matchup_home_team_abbr = None

if selected_matchup_str and selected_matchup_str != "All Players" and selected_matchup_str != "All Matchups":
    # Find the selected matchup
    selected_matchup = next((m for m in matchups if m['matchup'] == selected_matchup_str), None)
    
    if selected_matchup:
        # Get team IDs and abbreviations for filtering
        matchup_away_team_id = selected_matchup['away_team_id']
        matchup_home_team_id = selected_matchup['home_team_id']
        matchup_away_team_abbr = selected_matchup['away_team']
        matchup_home_team_abbr = selected_matchup['home_team']
        selected_team_ids = [matchup_away_team_id, matchup_home_team_id]
        
        # Filter players dataframe to only include players from these teams
        if 'TEAM_ID' in players_df.columns:
            # Convert team IDs to match the format in players_df (handle both int and str)
            players_df_team_ids = players_df['TEAM_ID'].astype(int)
            filtered_players_df = players_df[players_df_team_ids.isin(selected_team_ids)].copy()
            
            # Add average minutes column for sorting
            filtered_players_df['AVG_MIN'] = filtered_players_df['PERSON_ID'].apply(
                lambda x: player_minutes_map.get(int(x), 0)
            )
            
            # Sort: Away team first, then Home team; within each team, sort by minutes descending
            away_players = filtered_players_df[filtered_players_df['TEAM_ID'].astype(int) == matchup_away_team_id]
            away_players = away_players.sort_values('AVG_MIN', ascending=False)
            
            home_players = filtered_players_df[filtered_players_df['TEAM_ID'].astype(int) == matchup_home_team_id]
            home_players = home_players.sort_values('AVG_MIN', ascending=False)
            
            # Combine: away team players first, then home team players
            sorted_players_df = pd.concat([away_players, home_players])
            filtered_player_ids_list = sorted_players_df['PERSON_ID'].astype(str).tolist()
            
            # Show info about the matchup
            st.info(f"📊 Showing players from: {selected_matchup['away_team']} @ {selected_matchup['home_team']} (sorted by minutes)")
            
            # ============================================================
            # BEST VALUE PLAYS SECTION
            # ============================================================
            game_date_str_bvp = selected_date.strftime('%Y-%m-%d')
            game_cache_key_bvp = f"{game_date_str_bvp}_{matchup_away_team_abbr}_{matchup_home_team_abbr}"
            
            # Initialize session state for game-level prediction cache
            if 'predictions_game_cache' not in st.session_state:
                st.session_state.predictions_game_cache = {}
            
            with st.expander("🎯 **Best Value Plays** - Find edges across the entire game", expanded=False):
                st.caption("Generate predictions for all players and compare against Underdog lines to find the best value plays")
                
                # Check if we have cached predictions for this game
                cached_game_predictions = st.session_state.predictions_game_cache.get(game_cache_key_bvp)
                
                # Initialize session state for API data (GAME-LEVEL CACHE)
                if 'odds_game_cache' not in st.session_state:
                    st.session_state.odds_game_cache = {}
                if 'odds_api_credits' not in st.session_state:
                    st.session_state.odds_api_credits = None
                
                # Check if we have cached odds for this game
                cached_game_props = st.session_state.odds_game_cache.get(game_cache_key_bvp)
                
                # === FETCH UNDERDOG LINES SECTION ===
                with st.expander("🎰 **Fetch Underdog Lines** (The Odds API)", expanded=True):
                    st.caption("Fetch live player props from Underdog Fantasy via The Odds API")
                    
                    # Get player count for display
                    if cached_game_props is not None:
                        players_with_props = len(cached_game_props)
                    else:
                        players_with_props = 0
                    
                    # Dry-run preview section
                    col_preview, col_fetch = st.columns([2, 1])
                    
                    with col_preview:
                        if st.button("🔍 Preview Request (Free)", key="preview_odds_request_bvp"):
                            with st.spinner("Checking for available events..."):
                                preview = vl.preview_odds_request(
                                    matchup_home_team_abbr,
                                    matchup_away_team_abbr,
                                    game_date_str_bvp
                                )
                                
                                if preview.get('error'):
                                    st.error(f"❌ {preview['error']}")
                                    if preview.get('events_on_date'):
                                        st.info(f"Events found on {game_date_str_bvp}: {', '.join(preview['events_on_date'])}")
                                else:
                                    st.success(f"✅ Event found: {preview['event_details']['away_team']} @ {preview['event_details']['home_team']}")
                                    
                                    with st.container():
                                        st.markdown("**Request Details (Dry Run)**")
                                        st.code(f"""
Event ID: {preview['event_id']}
Region: {preview['request_info']['region']}
Bookmaker: {preview['request_info']['bookmaker']}
Markets: {', '.join(preview['request_info']['markets_requested'])}
Estimated Cost: {preview['estimated_cost']}
""", language=None)
                    
                    with col_fetch:
                        fetch_disabled = cached_game_props is not None
                        if fetch_disabled:
                            fetch_label = f"✅ Game Cached ({players_with_props} players)"
                        else:
                            fetch_label = "📥 Fetch Lines (1 Credit)"
                        
                        if st.button(fetch_label, key="fetch_odds_bvp", disabled=fetch_disabled):
                            with st.spinner("Fetching ALL player props for this game..."):
                                # Fetch ALL props for the game (costs 1 credit)
                                all_props, api_response = vl.fetch_all_props_for_game(
                                    matchup_home_team_abbr,
                                    matchup_away_team_abbr,
                                    game_date_str_bvp
                                )
                                
                                if api_response.success:
                                    # Cache at GAME level
                                    st.session_state.odds_game_cache[game_cache_key_bvp] = all_props
                                    st.session_state.odds_api_credits = api_response.credits_remaining
                                    
                                    if all_props:
                                        st.success(f"✅ Cached props for {len(all_props)} players! Switch players freely - no additional credits needed.")
                                    else:
                                        st.warning("⚠️ No props found for this game on Underdog")
                                    
                                    st.rerun()
                                else:
                                    # Show detailed error message
                                    error_msg = api_response.error or "Unknown API error"
                                    st.error(f"❌ API Error: {error_msg}")
                                    
                                    # Provide helpful guidance for common errors
                                    if "Invalid API key" in error_msg:
                                        st.info("💡 **Troubleshooting:**\n"
                                               "- Verify your API key in The Odds API dashboard\n"
                                               "- If you just upgraded, try regenerating your API key\n"
                                               "- Wait a few minutes for activation after upgrading\n"
                                               "- Ensure there are no extra spaces in the API key")
                                    
                                    if api_response.credits_remaining is not None:
                                        st.session_state.odds_api_credits = api_response.credits_remaining
                    
                    # Clear cache button
                    if cached_game_props is not None:
                        if st.button("🔄 Refresh Game Lines", key="refresh_odds_bvp"):
                            del st.session_state.odds_game_cache[game_cache_key_bvp]
                            st.session_state.odds_api_credits = None
                            st.rerun()
                    
                    # Show API credits if available
                    if st.session_state.odds_api_credits is not None:
                        st.caption(f"💳 API Credits Remaining: {st.session_state.odds_api_credits}")
                
                # Update cached_game_props after potential fetch
                cached_game_props = st.session_state.odds_game_cache.get(game_cache_key_bvp)
                
                col_gen, col_status = st.columns([1, 2])
                
                with col_gen:
                    # Only enable generation if we have odds
                    if cached_game_props is None:
                        st.warning("⚠️ Fetch Underdog lines above to enable predictions")
                        gen_disabled = True
                    elif cached_game_predictions is not None:
                        st.success(f"✅ {len(cached_game_predictions)} players predicted")
                        gen_disabled = True
                    else:
                        gen_disabled = False
                    
                    if st.button("🔮 Generate All Predictions", disabled=gen_disabled, key="gen_all_predictions"):
                        # Cache injury data in session state to avoid duplicate calls
                        if 'matchup_injuries_cache' not in st.session_state:
                            st.session_state.matchup_injuries_cache = {}
                        
                        matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                        if matchup_inj_key not in st.session_state.matchup_injuries_cache:
                            if injury_report_df is not None and len(injury_report_df) > 0:
                                matchup_inj = ir.get_injuries_for_matchup(
                                    injury_report_df,
                                    matchup_away_team_abbr,
                                    matchup_home_team_abbr,
                                    players_df
                                )
                                st.session_state.matchup_injuries_cache[matchup_inj_key] = matchup_inj
                            else:
                                st.session_state.matchup_injuries_cache[matchup_inj_key] = {'away': [], 'home': []}
                        else:
                            matchup_inj = st.session_state.matchup_injuries_cache[matchup_inj_key]
                        
                        # Get list of players who are OUT or DOUBTFUL from injury report
                        out_player_ids = set()
                        for injury_item in matchup_inj.get('away', []) + matchup_inj.get('home', []):
                            status_lower = injury_item.get('status', '').lower()
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item.get('player_id'):
                                    out_player_ids.add(str(injury_item['player_id']))
                        
                        # Filter to players who are not injured (include all players, even low-minute ones)
                        # This allows the model to predict for deep bench players who might enter rotation due to injuries
                        players_to_predict = [
                            pid for pid in filtered_player_ids_list 
                            if pid not in out_player_ids  # Skip players who are OUT or DOUBTFUL
                        ]
                        
                        if out_player_ids:
                            st.info(f"⏭️ Skipping {len(out_player_ids)} players who are Out/Doubtful")
                        
                        # Build required data structures
                        player_names_map = {pid: player_name_map.get(pid, f"Player {pid}") for pid in players_to_predict}
                        player_team_ids_map = {}
                        for pid in players_to_predict:
                            player_row = players_df[players_df['PERSON_ID'].astype(str) == pid]
                            if len(player_row) > 0:
                                player_team_ids_map[pid] = int(player_row['TEAM_ID'].iloc[0])
                        
                        # Store in session state for later use
                        if 'player_team_ids_map_cache' not in st.session_state:
                            st.session_state.player_team_ids_map_cache = {}
                        st.session_state.player_team_ids_map_cache[game_cache_key_bvp] = player_team_ids_map
                        
                        progress_bar = st.progress(0, text="Generating predictions...")
                        
                        def update_progress(current, total, player_name):
                            progress_bar.progress(current / total, text=f"({current}/{total}) {player_name}...")
                        
                        # Generate predictions for all players
                        all_predictions = pm.generate_predictions_for_game(
                            player_ids=players_to_predict,
                            player_names=player_names_map,
                            player_team_ids=player_team_ids_map,
                            away_team_id=matchup_away_team_id,
                            home_team_id=matchup_home_team_id,
                            away_team_abbr=matchup_away_team_abbr,
                            home_team_abbr=matchup_home_team_abbr,
                            game_date=game_date_str_bvp,
                            progress_callback=update_progress
                        )
                        
                        progress_bar.empty()
                        
                        # Cache the predictions
                        st.session_state.predictions_game_cache[game_cache_key_bvp] = all_predictions
                        st.success(f"✅ Generated predictions for {len(all_predictions)} players!")
                        st.rerun()
                
                with col_status:
                    if cached_game_predictions is not None and cached_game_props is not None:
                        st.info(f"📊 Predictions: {len(cached_game_predictions)} players | Lines: {len(cached_game_props)} players")
                    
                    # Refresh button
                    if cached_game_predictions is not None:
                        if st.button("🔄 Regenerate Predictions", key="refresh_all_predictions"):
                            del st.session_state.predictions_game_cache[game_cache_key_bvp]
                            st.rerun()
                
                # If we have both predictions and props, show the best value plays
                if cached_game_predictions is not None and cached_game_props is not None:
                    st.markdown("---")
                    
                    # Filters
                    filter_col1, filter_col2, filter_col3 = st.columns(3)
                    
                    with filter_col1:
                        min_edge = st.slider(
                            "Minimum Edge %",
                            min_value=0,
                            max_value=25,
                            value=5,
                            step=1,
                            key="bvp_min_edge"
                        )
                    
                    with filter_col2:
                        confidence_options = st.multiselect(
                            "Confidence Level",
                            options=['high', 'medium', 'low'],
                            default=['high', 'medium'],
                            key="bvp_confidence"
                        )
                    
                    with filter_col3:
                        stat_options = st.multiselect(
                            "Stats",
                            options=['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS'],
                            default=['PTS', 'REB', 'AST', 'PRA', 'RA', 'FG3M', 'FTM', 'FPTS'],
                            key="bvp_stats"
                        )
                    
                    # Calculate injury adjustments for all players in batch predictions (optimized)
                    injury_adjustments_map = {}
                    
                    # Get player_team_ids_map from session state or reconstruct it efficiently
                    cached_team_ids_map = st.session_state.get('player_team_ids_map_cache', {}).get(game_cache_key_bvp)
                    if cached_team_ids_map is None:
                        # Reconstruct from players_df efficiently using a lookup dictionary
                        # Create a fast lookup map: player_id -> team_id
                        players_df_id_str = players_df['PERSON_ID'].astype(str)
                        players_df_team_id = players_df['TEAM_ID'].astype(int)
                        player_team_lookup = dict(zip(players_df_id_str, players_df_team_id))
                        
                        cached_team_ids_map = {}
                        for player_id in cached_game_predictions.keys():
                            player_id_str = str(player_id)
                            if player_id_str in player_team_lookup:
                                cached_team_ids_map[player_id_str] = player_team_lookup[player_id_str]
                        
                        # Cache it for future use
                        if 'player_team_ids_map_cache' not in st.session_state:
                            st.session_state.player_team_ids_map_cache = {}
                        st.session_state.player_team_ids_map_cache[game_cache_key_bvp] = cached_team_ids_map
                    
                    # Get injury data from cache (already fetched earlier)
                    matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                    matchup_inj = st.session_state.get('matchup_injuries_cache', {}).get(matchup_inj_key, {'away': [], 'home': []})
                    
                    # Build lists of out players by team ONCE
                    away_out = []
                    home_out = []
                    out_player_ids = set()
                    if injury_report_df is not None and len(injury_report_df) > 0:
                        for injury_item in matchup_inj.get('away', []):
                            status_lower = injury_item.get('status', '').lower()
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item.get('player_id'):
                                    player_id_str = str(injury_item['player_id'])
                                    away_out.append(player_id_str)
                                    out_player_ids.add(player_id_str)
                        for injury_item in matchup_inj.get('home', []):
                            status_lower = injury_item.get('status', '').lower()
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item.get('player_id'):
                                    player_id_str = str(injury_item['player_id'])
                                    home_out.append(player_id_str)
                                    out_player_ids.add(player_id_str)
                        
                        # Calculate injury adjustments for each player (now with efficient lookup)
                        for player_id, player_data in cached_game_predictions.items():
                            player_id_str = str(player_id)
                            player_team_id = cached_team_ids_map.get(player_id_str)
                            
                            if not player_team_id:
                                continue
                            
                            # Determine teammates_out and opponents_out
                            if int(player_team_id) == matchup_away_team_id:
                                teammates_out = [p for p in away_out if p != player_id_str]
                                opponents_out = home_out
                                opp_team_id = matchup_home_team_id
                            elif int(player_team_id) == matchup_home_team_id:
                                teammates_out = [p for p in home_out if p != player_id_str]
                                opponents_out = away_out
                                opp_team_id = matchup_away_team_id
                            else:
                                continue
                            
                            # Only calculate if there are injuries
                            if teammates_out or opponents_out:
                                injury_adj = inj.calculate_injury_adjustments(
                                    player_id=player_id_str,
                                    player_team_id=int(player_team_id),
                                    opponent_team_id=opp_team_id,
                                    teammates_out=teammates_out,
                                    opponents_out=opponents_out,
                                    player_minutes_map=player_minutes_map,
                                    players_df=players_df
                                )
                                if injury_adj.get('factors'):
                                    injury_adjustments_map[player_id_str] = injury_adj
                    
                    # Build normalized statlines FIRST (before Value Plays)
                    # This ensures Value Plays use the same normalized/scaled values as Predicted Statlines
                    normalized_statlines_key = f"{game_cache_key_bvp}_normalized_statlines"
                    
                    # Check if we have manually adjusted statlines in session state
                    if normalized_statlines_key in st.session_state:
                        statlines_list = st.session_state[normalized_statlines_key]
                        
                        # Validate cached statlines: check if they sum to 240 per team
                        # If not, re-normalize them (they might be from before the fix)
                        away_total = sum(s['MIN'] for s in statlines_list if s.get('is_away'))
                        home_total = sum(s['MIN'] for s in statlines_list if not s.get('is_away'))
                        away_active = len([s for s in statlines_list if s.get('is_away') and s.get('MIN', 0) > 0.01])
                        home_active = len([s for s in statlines_list if not s.get('is_away') and s.get('MIN', 0) > 0.01])
                        
                        # If totals are wrong or too many players, re-normalize
                        if (abs(away_total - 240.0) > 0.1 or abs(home_total - 240.0) > 0.1 or 
                            away_active > 10 or home_active > 10):
                            # Re-normalize the cached statlines
                            bulk_game_logs = pf_features.get_bulk_player_game_logs()
                            matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                            matchup_inj = st.session_state.get('matchup_injuries_cache', {}).get(matchup_inj_key, {'away': [], 'home': []})
                            out_player_ids_revalidate = set()
                            for injury_item in matchup_inj.get('away', []) + matchup_inj.get('home', []):
                                status_lower = injury_item.get('status', '').lower()
                                if 'out' in status_lower or 'doubtful' in status_lower:
                                    if injury_item.get('player_id'):
                                        out_player_ids_revalidate.add(str(injury_item['player_id']))
                            
                            normalize_team_minutes(
                                statlines_list,
                                target_minutes=240.0,
                                out_player_ids=out_player_ids_revalidate,
                                bulk_game_logs=bulk_game_logs,
                                game_date=game_date_str_bvp
                            )
                            # Update cache with re-normalized statlines
                            st.session_state[normalized_statlines_key] = statlines_list
                    else:
                        # Build statlines list with injury-adjusted predictions
                        statlines_list = []
                        for player_id, player_data_dict in cached_game_predictions.items():
                            player_id_str = str(player_id)
                            
                            # Get actual predictions dict (nested under 'predictions' key)
                            predictions_dict = player_data_dict.get('predictions', {})
                            
                            # Get player info - use cached name if available, otherwise look up
                            player_name = player_data_dict.get('player_name')
                            if not player_name:
                                player_row = players_df[players_df['PERSON_ID'].astype(str) == player_id_str]
                                if len(player_row) == 0:
                                    continue
                                player_name = f"{player_row['PLAYER_FIRST_NAME'].iloc[0]} {player_row['PLAYER_LAST_NAME'].iloc[0]}"
                            
                            # Get team info from cached data or lookup
                            team_abbr = player_data_dict.get('team_abbr')
                            if not team_abbr:
                                player_row = players_df[players_df['PERSON_ID'].astype(str) == player_id_str]
                                if len(player_row) == 0:
                                    continue
                                player_team_id = int(player_row['TEAM_ID'].iloc[0])
                                is_away = (player_team_id == matchup_away_team_id)
                                team_abbr = matchup_away_team_abbr if is_away else matchup_home_team_abbr
                            else:
                                # Determine is_away from team_abbr
                                is_away = (team_abbr == matchup_away_team_abbr)
                            
                            # Extract base stat predictions
                            def get_pred_value(stat_key):
                                pred_obj = predictions_dict.get(stat_key)
                                if pred_obj and hasattr(pred_obj, 'value'):
                                    return pred_obj.value
                                return 0.0
                            
                            # Get base predictions (before any injury adjustments)
                            base_pts = get_pred_value('PTS')
                            base_reb = get_pred_value('REB')
                            base_ast = get_pred_value('AST')
                            base_stl = get_pred_value('STL')
                            base_blk = get_pred_value('BLK')
                            base_tov = get_pred_value('TOV')
                            base_fg3m = get_pred_value('FG3M')
                            base_ftm = get_pred_value('FTM')
                            
                            minutes = player_minutes_map.get(int(player_id), 25.0)
                            original_season_minutes = minutes  # Store BEFORE injury adjustments
                            
                            # Store base stats and injury adjustments for proper scaling order
                            # We'll apply injury adjustments AFTER normalization scaling
                            injury_adj_multipliers = None
                            injury_adjusted_minutes = minutes  # Track minutes after injury boost
                            if player_id_str in injury_adjustments_map:
                                injury_adj = injury_adjustments_map[player_id_str]
                                # Store injury multipliers for later application
                                injury_adj_multipliers = {
                                    'PTS': injury_adj.get('PTS', 1.0),
                                    'REB': injury_adj.get('REB', 1.0),
                                    'AST': injury_adj.get('AST', 1.0),
                                    'STL': injury_adj.get('STL', 1.0),
                                    'BLK': injury_adj.get('BLK', 1.0),
                                    'TOV': injury_adj.get('TOV', 1.0) if 'TOV' in injury_adj else 1.0,
                                    'FG3M': injury_adj.get('FG3M', 1.0),
                                    'FTM': injury_adj.get('FTM', 1.0),
                                    'minutes_boost': injury_adj.get('minutes_boost', 0.0)
                                }
                                # Add minutes boost for initial normalization
                                minutes += injury_adj.get('minutes_boost', 0.0)
                                injury_adjusted_minutes = minutes  # Store injury-adjusted minutes
                            
                            # For now, use base stats (injury adjustments will be applied after normalization)
                            pts = base_pts
                            reb = base_reb
                            ast = base_ast
                            stl = base_stl
                            blk = base_blk
                            tov = base_tov
                            fg3m = base_fg3m
                            ftm = base_ftm
                            
                            # Calculate derived stats from base stats
                            pra = pts + reb + ast
                            ra = reb + ast
                            # FPTS using Underdog formula: PTS*1 + REB*1.2 + AST*1.5 + STL*3 + BLK*3 - TOV*1
                            fpts = pts * 1.0 + reb * 1.2 + ast * 1.5 + stl * 3.0 + blk * 3.0 - tov * 1.0
                            
                            statline = {
                                'Player': player_name,
                                'Team': team_abbr,
                                'player_id': player_id_str,
                                'MIN': minutes,
                                '_original_season_minutes': original_season_minutes,  # Store for proper scaling
                                '_injury_adjusted_minutes': injury_adjusted_minutes,  # Store injury-adjusted minutes for scaling baseline
                                '_base_stats': {  # Store base stats before injury adjustments
                                    'PTS': base_pts,
                                    'REB': base_reb,
                                    'AST': base_ast,
                                    'STL': base_stl,
                                    'BLK': base_blk,
                                    'TOV': base_tov,
                                    'FG3M': base_fg3m,
                                    'FTM': base_ftm
                                },
                                '_injury_multipliers': injury_adj_multipliers,  # Store for re-application after normalization
                                'PTS': pts,  # Will be updated during normalization
                                'REB': reb,
                                'AST': ast,
                                'STL': stl,
                                'BLK': blk,
                                'TOV': tov,
                                'FG3M': fg3m,
                                'FTM': ftm,
                                'PRA': pra,
                                'RA': ra,
                                'FPTS': fpts,
                                'is_away': is_away
                            }
                            statlines_list.append(statline)
                        
                        # Get bulk game logs for recent activity check
                        bulk_game_logs = pf_features.get_bulk_player_game_logs()
                        
                        # Normalize minutes and scale stats using helper function
                        normalize_team_minutes(
                            statlines_list, 
                            target_minutes=240.0,
                            out_player_ids=out_player_ids,  # Pass the set of OUT/DOUBTFUL players
                            bulk_game_logs=bulk_game_logs,  # Pass bulk game logs
                            game_date=game_date_str_bvp  # Pass game date for recent activity check
                        )
                        
                        # Ensure players with 0 minutes have all stats set to 0
                        for statline in statlines_list:
                            if statline.get('MIN', 0) == 0 or statline.get('MIN', 0) < 0.01:
                                statline['PTS'] = 0.0
                                statline['REB'] = 0.0
                                statline['AST'] = 0.0
                                statline['STL'] = 0.0
                                statline['BLK'] = 0.0
                                statline['TOV'] = 0.0
                                statline['FG3M'] = 0.0
                                statline['FTM'] = 0.0
                                statline['PRA'] = 0.0
                                statline['RA'] = 0.0
                                statline['FPTS'] = 0.0
                        
                        # Store in session state
                        st.session_state[normalized_statlines_key] = statlines_list
                    
                    # Create normalized predictions dict for Value Plays
                    # This ensures Value Plays use the same normalized/scaled values
                    normalized_predictions = {}
                    for statline in statlines_list:
                        player_id_str = statline['player_id']
                        if player_id_str not in normalized_predictions:
                            normalized_predictions[player_id_str] = {
                                'predictions': {},
                                'player_name': statline['Player'],
                                'team_abbr': statline['Team']
                            }
                        
                        # Create Prediction objects with normalized values
                        from prediction_model import Prediction
                        normalized_predictions[player_id_str]['predictions']['PTS'] = Prediction(
                            stat='PTS', value=statline['PTS'], confidence='high',
                            breakdown={'normalized': statline['PTS']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['REB'] = Prediction(
                            stat='REB', value=statline['REB'], confidence='high',
                            breakdown={'normalized': statline['REB']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['AST'] = Prediction(
                            stat='AST', value=statline['AST'], confidence='high',
                            breakdown={'normalized': statline['AST']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['STL'] = Prediction(
                            stat='STL', value=statline['STL'], confidence='high',
                            breakdown={'normalized': statline['STL']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['BLK'] = Prediction(
                            stat='BLK', value=statline['BLK'], confidence='high',
                            breakdown={'normalized': statline['BLK']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['TOV'] = Prediction(
                            stat='TOV', value=statline['TOV'], confidence='high',
                            breakdown={'normalized': statline['TOV']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['FG3M'] = Prediction(
                            stat='FG3M', value=statline['FG3M'], confidence='high',
                            breakdown={'normalized': statline['FG3M']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['FTM'] = Prediction(
                            stat='FTM', value=statline['FTM'], confidence='high',
                            breakdown={'normalized': statline['FTM']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['PRA'] = Prediction(
                            stat='PRA', value=statline['PRA'], confidence='high',
                            breakdown={'normalized': statline['PRA']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['RA'] = Prediction(
                            stat='RA', value=statline['RA'], confidence='high',
                            breakdown={'normalized': statline['RA']}, factors={'source': 'normalized_statline'}
                        )
                        normalized_predictions[player_id_str]['predictions']['FPTS'] = Prediction(
                            stat='FPTS', value=statline['FPTS'], confidence='high',
                            breakdown={'normalized': statline['FPTS']}, factors={'source': 'normalized_statline'}
                        )
                    
                    # Check if we have cached best_plays from manual recalculation
                    cached_best_plays_key = f"{game_cache_key_bvp}_best_plays"
                    if cached_best_plays_key in st.session_state:
                        best_plays = st.session_state[cached_best_plays_key]
                    else:
                        # Find best value plays using NORMALIZED predictions (no additional injury adjustments needed)
                        best_plays = pm.find_best_value_plays(
                            all_predictions=normalized_predictions,
                            all_props=cached_game_props,
                            min_edge_pct=float(min_edge),
                            confidence_filter=confidence_options if confidence_options else ['high', 'medium', 'low'],
                            stat_filter=stat_options if stat_options else ['PTS', 'REB', 'AST', 'PRA'],
                            injury_adjustments_map=None  # Already normalized, no additional adjustments
                        )
                        # Cache for future use
                        st.session_state[cached_best_plays_key] = best_plays
                    
                    # Check for systematic bias
                    if best_plays:
                        over_count = sum(1 for p in best_plays if 'Over' in p['lean'])
                        under_count = sum(1 for p in best_plays if 'Under' in p['lean'])
                        total_count = len(best_plays)
                        
                        if total_count > 0:
                            over_pct = (over_count / total_count) * 100
                            under_pct = (under_count / total_count) * 100
                            avg_edge = sum(p['edge'] for p in best_plays) / total_count
                            
                            # Show bias warning if heavily skewed
                            if over_pct > 80:
                                st.warning(f"⚠️ **Potential Over-Bias**: {over_pct:.1f}% of plays are Over ({over_count}/{total_count}). Average edge: {avg_edge:+.2f}. Model may be systematically over-predicting.")
                            elif under_pct > 80:
                                st.warning(f"⚠️ **Potential Under-Bias**: {under_pct:.1f}% of plays are Under ({under_count}/{total_count}). Average edge: {avg_edge:+.2f}. Model may be systematically under-predicting.")
                            elif abs(avg_edge) > 1.5:
                                st.info(f"ℹ️ **Bias Detected**: Average edge = {avg_edge:+.2f} ({over_count} Over, {under_count} Under). This may indicate systematic prediction bias.")
                    
                    if best_plays:
                        st.markdown(f"### 🏆 Top {min(len(best_plays), 20)} Value Plays")
                        
                        # Sort by absolute edge % descending before taking top 20
                        sorted_plays = sorted(best_plays, key=lambda x: abs(x['edge_pct']), reverse=True)
                        
                        # Create DataFrame for display
                        plays_df = pd.DataFrame(sorted_plays[:20])  # Top 20
                        
                        # Format the display
                        display_df = plays_df[[
                            'player_name', 'team', 'stat', 'prediction', 'line', 
                            'edge', 'edge_pct', 'lean', 'confidence'
                        ]].copy()
                        
                        display_df.columns = [
                            'Player', 'Team', 'Stat', 'Pred', 'Line', 
                            'Edge', 'Edge %', 'Lean', 'Conf'
                        ]
                        
                        # Map stat codes to display names (for Underdog clarity)
                        stat_display_names = {
                            'PTS': 'Points',
                            'REB': 'Rebounds',
                            'AST': 'Assists',
                            'PRA': 'Points + Rebounds + Assists',
                            'RA': 'Rebounds + Assists',
                            'STL': 'Steals',
                            'BLK': 'Blocks',
                            'FG3M': '3-Pointers Made',
                            'FTM': 'Free Throws Made',
                            'FPTS': 'Fantasy Points'
                        }
                        
                        # Apply stat name mapping
                        display_df['Stat'] = display_df['Stat'].map(stat_display_names).fillna(display_df['Stat'])
                        
                        # Format columns - all numbers formatted to consistent decimal places
                        display_df['Pred'] = display_df['Pred'].apply(lambda x: f"{x:.1f}")
                        display_df['Line'] = display_df['Line'].apply(lambda x: f"{x:.1f}")
                        # Keep edge signed (not absolute) so we can see over/under direction
                        display_df['Edge'] = display_df['Edge'].apply(lambda x: f"{x:+.1f}")
                        # Edge % should be absolute for sorting, but we'll display signed
                        display_df['Edge %'] = display_df['Edge %'].apply(lambda x: f"{abs(x) / 100:.3f}")
                        display_df['Conf'] = display_df['Conf'].str.capitalize()
                        
                        # Style function for lean column
                        def style_lean_bvp(row):
                            styles = [''] * len(row)
                            lean_idx = display_df.columns.get_loc('Lean')
                            lean_val = row['Lean']
                            
                            if 'Strong Over' in lean_val:
                                styles[lean_idx] = 'background-color: rgba(46, 125, 50, 0.4); font-weight: bold'
                            elif 'Lean Over' in lean_val:
                                styles[lean_idx] = 'background-color: rgba(76, 175, 80, 0.3)'
                            elif 'Strong Under' in lean_val:
                                styles[lean_idx] = 'background-color: rgba(183, 28, 28, 0.4); font-weight: bold'
                            elif 'Lean Under' in lean_val:
                                styles[lean_idx] = 'background-color: rgba(244, 67, 54, 0.3)'
                            
                            # Also color confidence
                            conf_idx = display_df.columns.get_loc('Conf')
                            if row['Conf'] == 'High':
                                styles[conf_idx] = 'background-color: rgba(33, 150, 243, 0.3)'
                            elif row['Conf'] == 'Medium':
                                styles[conf_idx] = 'background-color: rgba(255, 193, 7, 0.3)'
                            
                            return styles
                        
                        styled_plays = display_df.style.apply(style_lean_bvp, axis=1)
                        st.dataframe(styled_plays, width='stretch', hide_index=True)
                        
                        # Download button for Value Plays
                        value_plays_csv = plays_df[[
                            'player_name', 'team', 'stat', 'prediction', 'line', 
                            'edge', 'edge_pct', 'lean', 'confidence'
                        ]].copy()
                        value_plays_csv.columns = [
                            'Player', 'Team', 'Stat', 'Pred', 'Line', 
                            'Edge', 'Edge %', 'Lean', 'Conf'
                        ]
                        csv_value_plays = value_plays_csv.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Value Plays CSV",
                            data=csv_value_plays,
                            file_name=f"value_plays_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                            mime="text/csv",
                            key="download_value_plays"
                        )
                        
                        # Summary stats
                        overs = len([p for p in best_plays if 'Over' in p['lean']])
                        unders = len([p for p in best_plays if 'Under' in p['lean']])
                        st.caption(f"📈 {overs} Over plays | 📉 {unders} Under plays | Total: {len(best_plays)} plays found")
                        
                        # Show all predicted statlines sorted by team and minutes
                        st.markdown("---")
                        st.markdown("### 📊 All Predicted Statlines")
                        
                        # Use normalized statlines from session state (already calculated above)
                        statlines_list = st.session_state.get(normalized_statlines_key, [])
                        
                        # Manual Minutes Adjustment Interface
                        with st.expander("⚙️ **Manual Minutes Adjustment**", expanded=False):
                            st.caption("Adjust individual player minutes. Stats will be scaled proportionally, and team totals will be normalized to 240 minutes.")
                            
                            # Initialize manual adjustments in session state
                            manual_adjustments_key = f"{game_cache_key_bvp}_manual_minutes"
                            if manual_adjustments_key not in st.session_state:
                                st.session_state[manual_adjustments_key] = {}
                            
                            # Sort statlines for display
                            statlines_list_sorted = sorted(statlines_list, key=lambda x: (not x['is_away'], -x['MIN']))
                            
                            # Create columns for away and home teams
                            adj_col1, adj_col2 = st.columns(2)
                            
                            with adj_col1:
                                st.markdown(f"**{matchup_away_team_abbr}** (Away)")
                                # Calculate total including manual adjustments
                                away_total = 0.0
                                for statline in statlines_list:
                                    if statline['is_away']:
                                        player_id_str = statline['player_id']
                                        # Use manual adjustment if exists, otherwise use original
                                        if player_id_str in st.session_state[manual_adjustments_key]:
                                            away_total += st.session_state[manual_adjustments_key][player_id_str]
                                        else:
                                            away_total += statline['MIN']
                                st.metric("Total Minutes", f"{away_total:.1f}", delta=f"{away_total - 240:.1f}" if abs(away_total - 240) > 0.1 else None)
                                
                                away_statlines = [s for s in statlines_list_sorted if s['is_away']]
                                for statline in away_statlines:
                                    player_id_str = statline['player_id']
                                    player_key = f"min_adj_{player_id_str}"
                                    
                                    # Get current value (manual adjustment stored in session state, or original)
                                    # Only use manual adjustment if it exists in session state
                                    if player_id_str in st.session_state[manual_adjustments_key]:
                                        current_min = st.session_state[manual_adjustments_key][player_id_str]
                                    else:
                                        current_min = statline['MIN']
                                    
                                    new_min = st.number_input(
                                        f"{statline['Player']}",
                                        min_value=0.0,
                                        max_value=40.0,
                                        value=float(current_min),
                                        step=0.5,
                                        key=player_key,
                                        format="%.1f"
                                    )
                                    
                                    # Store manual adjustment in session state (but don't apply until button click)
                                    # Only store if different from original value
                                    if abs(new_min - statline['MIN']) > 0.01:
                                        st.session_state[manual_adjustments_key][player_id_str] = new_min
                                    elif player_id_str in st.session_state[manual_adjustments_key] and abs(new_min - statline['MIN']) <= 0.01:
                                        # If user resets to original value, remove from manual adjustments
                                        del st.session_state[manual_adjustments_key][player_id_str]
                            
                            with adj_col2:
                                st.markdown(f"**{matchup_home_team_abbr}** (Home)")
                                # Calculate total including manual adjustments
                                home_total = 0.0
                                for statline in statlines_list:
                                    if not statline['is_away']:
                                        player_id_str = statline['player_id']
                                        # Use manual adjustment if exists, otherwise use original
                                        if player_id_str in st.session_state[manual_adjustments_key]:
                                            home_total += st.session_state[manual_adjustments_key][player_id_str]
                                        else:
                                            home_total += statline['MIN']
                                st.metric("Total Minutes", f"{home_total:.1f}", delta=f"{home_total - 240:.1f}" if abs(home_total - 240) > 0.1 else None)
                                
                                home_statlines = [s for s in statlines_list_sorted if not s['is_away']]
                                for statline in home_statlines:
                                    player_id_str = statline['player_id']
                                    player_key = f"min_adj_{player_id_str}"
                                    
                                    # Get current value (manual adjustment stored in session state, or original)
                                    # Only use manual adjustment if it exists in session state
                                    if player_id_str in st.session_state[manual_adjustments_key]:
                                        current_min = st.session_state[manual_adjustments_key][player_id_str]
                                    else:
                                        current_min = statline['MIN']
                                    
                                    new_min = st.number_input(
                                        f"{statline['Player']}",
                                        min_value=0.0,
                                        max_value=40.0,
                                        value=float(current_min),
                                        step=0.5,
                                        key=player_key,
                                        format="%.1f"
                                    )
                                    
                                    # Store manual adjustment in session state (but don't apply until button click)
                                    # Only store if different from original value
                                    if abs(new_min - statline['MIN']) > 0.01:
                                        st.session_state[manual_adjustments_key][player_id_str] = new_min
                                    elif player_id_str in st.session_state[manual_adjustments_key] and abs(new_min - statline['MIN']) <= 0.01:
                                        # If user resets to original value, remove from manual adjustments
                                        del st.session_state[manual_adjustments_key][player_id_str]
                            
                            # Show preview of manual adjustments if any exist
                            if st.session_state[manual_adjustments_key]:
                                st.info(f"ℹ️ {len(st.session_state[manual_adjustments_key])} player(s) have manual minute adjustments. Click 'Recalculate' to apply.")
                            
                            # Apply manual adjustments and recalculate button
                            if st.button("🔄 Recalculate Stats & Value Plays", key="recalc_stats"):
                                # Get cached predictions for regenerating base stats
                                cached_game_predictions_recalc = st.session_state.predictions_game_cache.get(game_cache_key_bvp)
                                
                                # Create a copy of statlines_list to avoid modifying the cached version
                                statlines_list_copy = []
                                for statline in statlines_list:
                                    statline_copy = statline.copy()
                                    player_id_str = statline_copy['player_id']
                                    # Apply manual adjustments if they exist
                                    if player_id_str in st.session_state[manual_adjustments_key]:
                                        # Store the pre-manual-adjustment minutes for scaling
                                        statline_copy['_original_min'] = statline_copy['MIN']
                                        statline_copy['MIN'] = st.session_state[manual_adjustments_key][player_id_str]
                                    
                                    # Get new minutes (after manual adjustment)
                                    new_minutes = statline_copy['MIN']
                                    
                                    # Check if player needs base stats regenerated (has > 0 minutes but missing/invalid base_stats)
                                    base_stats = statline_copy.get('_base_stats')
                                    needs_base_stats = False
                                    if new_minutes > 0.01:
                                        if not base_stats:
                                            needs_base_stats = True
                                        elif all(v == 0.0 for v in base_stats.values()):
                                            # Base stats exist but are all zeros (player was initially at 0 minutes)
                                            needs_base_stats = True
                                    
                                    # Regenerate base stats from cached predictions if needed
                                    if needs_base_stats and cached_game_predictions_recalc:
                                        try:
                                            player_id_int = int(player_id_str)
                                            if player_id_int in cached_game_predictions_recalc:
                                                player_data = cached_game_predictions_recalc[player_id_int]
                                                predictions_dict = player_data.get('predictions', {})
                                                
                                                # Extract base predictions using same pattern as initial statline building
                                                def get_pred_value(stat_key):
                                                    pred_obj = predictions_dict.get(stat_key)
                                                    if pred_obj and hasattr(pred_obj, 'value'):
                                                        return pred_obj.value
                                                    return 0.0
                                                
                                                # Regenerate base stats from cached predictions
                                                statline_copy['_base_stats'] = {
                                                    'PTS': get_pred_value('PTS'),
                                                    'REB': get_pred_value('REB'),
                                                    'AST': get_pred_value('AST'),
                                                    'STL': get_pred_value('STL'),
                                                    'BLK': get_pred_value('BLK'),
                                                    'TOV': get_pred_value('TOV'),
                                                    'FG3M': get_pred_value('FG3M'),
                                                    'FTM': get_pred_value('FTM')
                                                }
                                                
                                                # Also set original season minutes if missing
                                                if '_original_season_minutes' not in statline_copy or statline_copy.get('_original_season_minutes', 0) == 0:
                                                    # Get from player_minutes_map or use new_minutes as fallback
                                                    statline_copy['_original_season_minutes'] = player_minutes_map.get(player_id_int, new_minutes)
                                                
                                                # Set injury-adjusted minutes to new_minutes if missing
                                                if '_injury_adjusted_minutes' not in statline_copy:
                                                    statline_copy['_injury_adjusted_minutes'] = new_minutes
                                        except (ValueError, KeyError, AttributeError) as e:
                                            # If regeneration fails, fall back to current stats
                                            if not base_stats:
                                                statline_copy['_base_stats'] = {
                                                    'PTS': statline_copy.get('PTS', 0.0),
                                                    'REB': statline_copy.get('REB', 0.0),
                                                    'AST': statline_copy.get('AST', 0.0),
                                                    'STL': statline_copy.get('STL', 0.0),
                                                    'BLK': statline_copy.get('BLK', 0.0),
                                                    'TOV': statline_copy.get('TOV', 0.0),
                                                    'FG3M': statline_copy.get('FG3M', 0.0),
                                                    'FTM': statline_copy.get('FTM', 0.0)
                                                }
                                    
                                    # Ensure _original_season_minutes is preserved
                                    if '_original_season_minutes' not in statline_copy or statline_copy.get('_original_season_minutes', 0) == 0:
                                        # Fallback: use _original_min if available, otherwise current MIN
                                        statline_copy['_original_season_minutes'] = statline_copy.get('_original_min', statline_copy['MIN'])
                                    
                                    # Ensure base stats exist (fallback if regeneration didn't happen)
                                    if '_base_stats' not in statline_copy:
                                        # If base stats don't exist, create them from current stats (fallback)
                                        statline_copy['_base_stats'] = {
                                            'PTS': statline_copy.get('PTS', 0.0),
                                            'REB': statline_copy.get('REB', 0.0),
                                            'AST': statline_copy.get('AST', 0.0),
                                            'STL': statline_copy.get('STL', 0.0),
                                            'BLK': statline_copy.get('BLK', 0.0),
                                            'TOV': statline_copy.get('TOV', 0.0),
                                            'FG3M': statline_copy.get('FG3M', 0.0),
                                            'FTM': statline_copy.get('FTM', 0.0)
                                        }
                                    # _injury_multipliers should already be preserved from the copy
                                    
                                    # Ensure all required stat fields exist with default values
                                    required_stats = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM']
                                    for stat in required_stats:
                                        if stat not in statline_copy:
                                            statline_copy[stat] = 0.0
                                    
                                    statlines_list_copy.append(statline_copy)
                                
                                # Use the copy for recalculation
                                statlines_list = statlines_list_copy
                                
                                # Get bulk game logs for recent activity check
                                bulk_game_logs = pf_features.get_bulk_player_game_logs()
                                
                                # Get out_player_ids from session state or reconstruct
                                matchup_inj_key = f"{game_cache_key_bvp}_injuries"
                                matchup_inj = st.session_state.get('matchup_injuries_cache', {}).get(matchup_inj_key, {'away': [], 'home': []})
                                out_player_ids_recalc = set()
                                for injury_item in matchup_inj.get('away', []) + matchup_inj.get('home', []):
                                    status_lower = injury_item.get('status', '').lower()
                                    if 'out' in status_lower or 'doubtful' in status_lower:
                                        if injury_item.get('player_id'):
                                            out_player_ids_recalc.add(str(injury_item['player_id']))
                                
                                # Re-normalize minutes to 240 per team
                                normalize_team_minutes(
                                    statlines_list, 
                                    target_minutes=240.0,
                                    out_player_ids=out_player_ids_recalc,
                                    bulk_game_logs=bulk_game_logs,
                                    game_date=game_date_str_bvp
                                )
                                
                                # Ensure players with 0 minutes have all stats set to 0
                                for statline in statlines_list:
                                    if statline.get('MIN', 0) == 0 or statline.get('MIN', 0) < 0.01:
                                        statline['PTS'] = 0.0
                                        statline['REB'] = 0.0
                                        statline['AST'] = 0.0
                                        statline['STL'] = 0.0
                                        statline['BLK'] = 0.0
                                        statline['TOV'] = 0.0
                                        statline['FG3M'] = 0.0
                                        statline['FTM'] = 0.0
                                        statline['PRA'] = 0.0
                                        statline['RA'] = 0.0
                                        statline['FPTS'] = 0.0
                                
                                # Display normalized minutes summary
                                st.success("✅ Minutes normalized to 240 per team. See normalized minutes below:")
                                
                                # Show normalized minutes breakdown
                                norm_col1, norm_col2 = st.columns(2)
                                
                                with norm_col1:
                                    st.markdown(f"**{matchup_away_team_abbr} Normalized Minutes:**")
                                    away_norm_total = 0.0
                                    away_norm_list = []
                                    for statline in statlines_list:
                                        if statline['is_away']:
                                            away_norm_total += statline['MIN']
                                            away_norm_list.append({
                                                'Player': statline['Player'],
                                                'MIN': statline['MIN']
                                            })
                                    # Sort by minutes descending
                                    away_norm_list.sort(key=lambda x: x['MIN'], reverse=True)
                                    for item in away_norm_list:
                                        st.write(f"{item['Player']}: {item['MIN']:.1f}")
                                    st.metric("Total", f"{away_norm_total:.1f}", delta=f"{away_norm_total - 240:.1f}" if abs(away_norm_total - 240) > 0.01 else None)
                                
                                with norm_col2:
                                    st.markdown(f"**{matchup_home_team_abbr} Normalized Minutes:**")
                                    home_norm_total = 0.0
                                    home_norm_list = []
                                    for statline in statlines_list:
                                        if not statline['is_away']:
                                            home_norm_total += statline['MIN']
                                            home_norm_list.append({
                                                'Player': statline['Player'],
                                                'MIN': statline['MIN']
                                            })
                                    # Sort by minutes descending
                                    home_norm_list.sort(key=lambda x: x['MIN'], reverse=True)
                                    for item in home_norm_list:
                                        st.write(f"{item['Player']}: {item['MIN']:.1f}")
                                    st.metric("Total", f"{home_norm_total:.1f}", delta=f"{home_norm_total - 240:.1f}" if abs(home_norm_total - 240) > 0.01 else None)
                                
                                # Update normalized predictions for Value Plays
                                normalized_predictions = {}
                                for statline in statlines_list:
                                    player_id_str = statline['player_id']
                                    if player_id_str not in normalized_predictions:
                                        normalized_predictions[player_id_str] = {
                                            'predictions': {},
                                            'player_name': statline['Player'],
                                            'team_abbr': statline['Team']
                                        }
                                    
                                    from prediction_model import Prediction
                                    normalized_predictions[player_id_str]['predictions']['PTS'] = Prediction(
                                        stat='PTS', value=statline['PTS'], confidence='high',
                                        breakdown={'normalized': statline['PTS']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['REB'] = Prediction(
                                        stat='REB', value=statline['REB'], confidence='high',
                                        breakdown={'normalized': statline['REB']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['AST'] = Prediction(
                                        stat='AST', value=statline['AST'], confidence='high',
                                        breakdown={'normalized': statline['AST']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['STL'] = Prediction(
                                        stat='STL', value=statline['STL'], confidence='high',
                                        breakdown={'normalized': statline['STL']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['BLK'] = Prediction(
                                        stat='BLK', value=statline['BLK'], confidence='high',
                                        breakdown={'normalized': statline['BLK']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['TOV'] = Prediction(
                                        stat='TOV', value=statline['TOV'], confidence='high',
                                        breakdown={'normalized': statline['TOV']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['FG3M'] = Prediction(
                                        stat='FG3M', value=statline['FG3M'], confidence='high',
                                        breakdown={'normalized': statline['FG3M']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['FTM'] = Prediction(
                                        stat='FTM', value=statline['FTM'], confidence='high',
                                        breakdown={'normalized': statline['FTM']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['PRA'] = Prediction(
                                        stat='PRA', value=statline['PRA'], confidence='high',
                                        breakdown={'normalized': statline['PRA']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['RA'] = Prediction(
                                        stat='RA', value=statline['RA'], confidence='high',
                                        breakdown={'normalized': statline['RA']}, factors={'source': 'normalized_statline'}
                                    )
                                    normalized_predictions[player_id_str]['predictions']['FPTS'] = Prediction(
                                        stat='FPTS', value=statline['FPTS'], confidence='high',
                                        breakdown={'normalized': statline['FPTS']}, factors={'source': 'normalized_statline'}
                                    )
                                
                                # Recalculate Value Plays
                                best_plays = pm.find_best_value_plays(
                                    all_predictions=normalized_predictions,
                                    all_props=cached_game_props,
                                    min_edge_pct=float(min_edge),
                                    confidence_filter=confidence_options if confidence_options else ['high', 'medium', 'low'],
                                    stat_filter=stat_options if stat_options else ['PTS', 'REB', 'AST', 'PRA'],
                                    injury_adjustments_map=None
                                )
                                
                                # Update session state
                                st.session_state[normalized_statlines_key] = statlines_list
                                st.session_state[f"{game_cache_key_bvp}_normalized_predictions"] = normalized_predictions
                                st.session_state[f"{game_cache_key_bvp}_best_plays"] = best_plays
                                
                                st.rerun()
                            
                            # Reset button
                            if st.button("🔄 Reset to Original", key="reset_minutes"):
                                st.session_state[manual_adjustments_key] = {}
                                st.rerun()
                        
                        # Sort: away team first (minutes descending), then home team (minutes descending)
                        statlines_list.sort(key=lambda x: (not x['is_away'], -x['MIN']))
                        
                        # Create DataFrame
                        statlines_df = pd.DataFrame(statlines_list)
                        display_statlines_df = statlines_df[['Player', 'Team', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']].copy()
                        
                        # Format numbers
                        for col in ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']:
                            display_statlines_df[col] = display_statlines_df[col].apply(lambda x: f"{x:.1f}")
                        
                        st.dataframe(display_statlines_df, width='stretch', hide_index=True)
                        
                        # Download button for Predicted Statlines
                        csv_statlines = statlines_df[['Player', 'Team', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']].copy()
                        csv_statlines_str = csv_statlines.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Predicted Statlines CSV",
                            data=csv_statlines_str,
                            file_name=f"predicted_statlines_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                            mime="text/csv",
                            key="download_statlines"
                        )
                        
                        # Calculate team totals
                        st.markdown("---")
                        st.markdown("### 🏀 Predicted Final Score")
                        
                        # Aggregate points by team
                        away_total_pts = statlines_df[statlines_df['is_away'] == True]['PTS'].sum()
                        home_total_pts = statlines_df[statlines_df['is_away'] == False]['PTS'].sum()
                        total_score = away_total_pts + home_total_pts
                        
                        # Team-level sanity checks
                        # Typical NBA team totals: 100-130 points per game
                        # If predicted total is way outside this range, show warning
                        if away_total_pts > 140 or home_total_pts > 140:
                            st.warning(f"⚠️ **Unusually High Prediction**: Team totals exceed 140 points. This may indicate over-adjustment from injuries or other factors.")
                        elif total_score > 280:
                            st.warning(f"⚠️ **Unusually High Total**: Combined score ({total_score:.1f}) exceeds typical NBA game totals (200-260). Model may be over-predicting.")
                        
                        # Get game lines (spread and total) from The Odds API
                        game_lines_total = None
                        game_lines_spread = None
                        try:
                            # Get events for the date
                            events, error = vl.get_nba_events(game_date_str_bvp)
                            if not error and events:
                                # Find the matching event
                                event = vl.find_event_for_matchup(events, matchup_home_team_abbr, matchup_away_team_abbr)
                                if event:
                                    event_id = event['id']
                                    
                                    # Fetch odds for game lines (totals and spreads) - FREE, doesn't cost credits
                                    url = f"{vl.ODDS_API_BASE}/sports/{vl.SPORT}/events/{event_id}/odds"
                                    params = {
                                        'apiKey': vl.ODDS_API_KEY,
                                        'regions': 'us',
                                        'bookmakers': 'draftkings',
                                        'markets': 'totals,spreads',
                                        'oddsFormat': 'american',
                                        'dateFormat': 'iso'
                                    }
                                    
                                    response = requests.get(url, params=params, timeout=10)
                                    
                                    if response.status_code == 200:
                                        data = response.json()
                                        
                                        if 'bookmakers' in data and len(data['bookmakers']) > 0:
                                            bookmaker = data['bookmakers'][0]
                                            
                                            if 'markets' in bookmaker:
                                                for market in bookmaker['markets']:
                                                    if market['key'] == 'totals':
                                                        if 'outcomes' in market and len(market['outcomes']) > 0:
                                                            game_lines_total = market['outcomes'][0].get('point', None)
                                                            break
                                                    
                                                    if market['key'] == 'spreads':
                                                        if 'outcomes' in market:
                                                            for outcome in market['outcomes']:
                                                                # Find the home team spread
                                                                if outcome.get('name') == matchup_home_team_abbr:
                                                                    game_lines_spread = outcome.get('point', None)
                                                                    break
                                                            if game_lines_spread is None and len(market['outcomes']) > 0:
                                                                game_lines_spread = market['outcomes'][0].get('point', None)
                        except Exception as e:
                            # Silently fail - game lines are optional
                            pass
                        
                        # Display predicted score
                        score_col1, score_col2, score_col3 = st.columns(3)
                        
                        with score_col1:
                            st.metric(
                                label=f"{matchup_away_team_abbr} (Away)",
                                value=f"{away_total_pts:.1f}",
                                delta=None
                            )
                        
                        with score_col2:
                            st.metric(
                                label=f"{matchup_home_team_abbr} (Home)",
                                value=f"{home_total_pts:.1f}",
                                delta=None
                            )
                        
                        with score_col3:
                            st.metric(
                                label="Total",
                                value=f"{total_score:.1f}",
                                delta=None
                            )
                        
                        # Compare to Vegas lines
                        if game_lines_total is not None or game_lines_spread is not None:
                            st.markdown("**📊 Comparison to Vegas Lines:**")
                            
                            comparison_lines = []
                            
                            if game_lines_total is not None:
                                total_diff = total_score - game_lines_total
                                total_lean = "Over" if total_diff > 0 else "Under"
                                comparison_lines.append(f"**Total**: Predicted {total_score:.1f} vs Line {game_lines_total:.1f} ({total_diff:+.1f}, **{total_lean}**)")
                            
                            if game_lines_spread is not None:
                                # Spread is from home team perspective
                                # If line is -7.5, that means home team is favored by 7.5 (home needs to win by 7.5+)
                                # If line is +7.5, that means away team is favored by 7.5 (home can lose by up to 7.5)
                                predicted_spread = home_total_pts - away_total_pts
                                
                                # Determine which team covers and by how much
                                # If home is favored (negative line):
                                #   - Home covers if predicted_spread >= line (e.g., -5.0 >= -7.5 means home wins by 5, which beats -7.5)
                                #   - Away covers if predicted_spread < line (e.g., -12.5 < -7.5 means home loses by 12.5, away beats spread)
                                # If away is favored (positive line):
                                #   - Away covers if predicted_spread <= line (e.g., 5.0 <= 7.5 means home loses by 5, away beats spread)
                                #   - Home covers if predicted_spread > line (e.g., 10.0 > 7.5 means home wins by 10, home beats spread)
                                
                                if game_lines_spread < 0:
                                    # Home is favored (negative line, e.g., -7.5)
                                    if predicted_spread >= game_lines_spread:
                                        # Home covers: predicted margin >= line (e.g., -5.0 >= -7.5)
                                        covering_team = matchup_home_team_abbr
                                        covering_margin = predicted_spread - game_lines_spread
                                    else:
                                        # Away covers: predicted margin < line (e.g., -12.5 < -7.5)
                                        # Away beats spread by: |predicted_spread| + |line| = how much home underperformed
                                        # Example: MIN favored by 7.5, loses by 12.5 -> NYK beats spread by 12.5 + 7.5 = 20.0
                                        covering_team = matchup_away_team_abbr
                                        covering_margin = abs(predicted_spread) + abs(game_lines_spread)
                                else:
                                    # Away is favored (positive line, e.g., +7.5)
                                    if predicted_spread <= game_lines_spread:
                                        # Away covers: predicted margin <= line (e.g., 5.0 <= 7.5)
                                        # Away beats spread by: line - predicted_spread
                                        covering_team = matchup_away_team_abbr
                                        covering_margin = game_lines_spread - predicted_spread
                                    else:
                                        # Home covers: predicted margin > line (e.g., 10.0 > 7.5)
                                        # Home beats spread by: predicted_spread - line
                                        covering_team = matchup_home_team_abbr
                                        covering_margin = predicted_spread - game_lines_spread
                                
                                # Format: Show predicted spread from home perspective, then which team covers
                                comparison_lines.append(f"**Spread**: Predicted {matchup_home_team_abbr} {predicted_spread:+.1f} vs Line {game_lines_spread:+.1f} ({covering_team} +{covering_margin:.1f}, **{covering_team} covers**)")
                            
                            if comparison_lines:
                                for line in comparison_lines:
                                    st.write(line)
                        else:
                            st.info("ℹ️ Game lines (spread/total) not available. These are fetched from DraftKings via The Odds API.")
                    else:
                        st.info("No plays found matching your filters. Try lowering the minimum edge % or expanding filters.")
                
                elif cached_game_predictions is None and cached_game_props is not None:
                    st.info("👆 Click 'Generate All Predictions' to find value plays")
                elif cached_game_predictions is not None and cached_game_props is None:
                    st.warning("⚠️ Need to fetch Underdog lines first to compare predictions")
            
        else:
            # If TEAM_ID column doesn't exist, try to filter by team abbreviation
            st.warning("⚠️ Could not filter by team ID. Showing all players.")
            filtered_player_ids_list = player_ids_list.copy()

# Set Anthony Edwards (ID: 1630162) as default selected player
default_player_id = '1630162'
default_index = 0
if default_player_id in filtered_player_ids_list:
    default_index = filtered_player_ids_list.index(default_player_id)
elif len(filtered_player_ids_list) > 0:
    # If default player not in filtered list, use first available
    default_index = 0

# Check if there are any players to show
if len(filtered_player_ids_list) == 0:
    st.warning("⚠️ No players found for the selected matchup. Please select a different matchup or date.")
    st.stop()

selected_player_id = st.selectbox(
    "Select Player",
    options=filtered_player_ids_list,
    format_func=lambda x: player_name_map.get(x, f"Player {x}"),
    index=default_index,
    key="player_selector"
)

# Cache player data to avoid repeated API calls
# Version 2: Added PRA and PRA percentile support
@st.cache_data
def get_cached_player_data(player_id, players_df, _cache_version=2):
    """Cache player data to avoid repeated API calls"""
    return pf.get_player_data(player_id, players_df)

# Get player data for selected player (uses PlayerIndex data, no CommonPlayerInfo API call needed)
player_data = get_cached_player_data(selected_player_id, players_df)

with st.container(border=False):
    col1, col2, col3 = st.columns([0.2, 0.2, 0.6], border=1, vertical_alignment='top')
    with col1:
        # st.image(pf.headshot,
        #          width=225)
        st.markdown(f"""
                    <div style="position: relative; display: inline-block; width: 100%; max-width: 230px;">
                        <img src="{player_data['headshot']}" style="width: 100%; height: auto; max-width: 230px; max-height: 175px; object-fit: cover;">
                        <img src="{player_data['logo']}" style="position: absolute; top: -5px; right: -10px; width: 30%; height: auto; max-width: 80px; max-height: 60px; object-fit: contain;">
                    </div>
                """, unsafe_allow_html=True)
    with col2:

        st.subheader(
            f"{player_data['player_info_name']}",
            anchor=False
        )
        # st.badge(
        #     f"**{player_data['player_info_team']} #{player_data['player_info_number']}**",
        #     color='blue'
        # )
        st.markdown(f"""
            <div style="display: inline-block; background-color: {player_data['team_color']}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.875em; font-weight: bold; margin: 0.25rem 0 0.75rem 0;">
                {player_data['player_info_team']} #{player_data['player_info_number']}
            </div>
        """, unsafe_allow_html=True)

        st.write(
            f"**{player_data['player_info_position']}** | **{player_data['player_info_height']}**"
        )
        st.write(
            f"Weight: **{player_data['player_info_weight']} pounds**"
        )

    with col3:
        st.subheader(
            'Season Stats',
            anchor=False
        )
        col5, col6, col7, col8, col9, col10 = st.columns([0.16, 0.16, 0.16, 0.16, 0.16, 0.16], border=0)
        with col5:
            pts_percentile = player_data.get('pts_percentile')
            pts_percentile_str = pf.format_percentile(pts_percentile)
            st.metric(
                label='Points',
                value=player_data['player_pts_pg'],
                delta=f"{pts_percentile_str} %ile" if pts_percentile is not None else None
            )
        with col6:
            reb_percentile = player_data.get('reb_percentile')
            reb_percentile_str = pf.format_percentile(reb_percentile)
            st.metric(
                label='Rebounds',
                value=player_data['player_reb_pg'],
                delta=f"{reb_percentile_str} %ile" if reb_percentile is not None else None
            )
        with col7:
            ast_percentile = player_data.get('ast_percentile')
            ast_percentile_str = pf.format_percentile(ast_percentile)
            st.metric(
                label='Assists',
                value=player_data['player_ast_pg'],
                delta=f"{ast_percentile_str} %ile" if ast_percentile is not None else None
            )
        with col8:
            # Calculate PRA if not in cached data (for backward compatibility)
            if 'player_pra_pg' in player_data:
                player_pra_pg = player_data['player_pra_pg']
            else:
                # Fallback: calculate from existing stats
                player_pra_pg = player_data.get('player_pts_pg', 0.0) + player_data.get('player_reb_pg', 0.0) + player_data.get('player_ast_pg', 0.0)
            
            # Get PRA percentile (should always be available in new cached data)
            pra_percentile = player_data.get('pra_percentile')
            pra_percentile_str = pf.format_percentile(pra_percentile) if pra_percentile is not None else None
            st.metric(
                label='PRA',
                value=f"{player_pra_pg:.1f}",
                delta=f"{pra_percentile_str} %ile" if pra_percentile_str is not None else None
            )
        with col9:
            stl_percentile = player_data.get('stl_percentile')
            stl_percentile_str = pf.format_percentile(stl_percentile)
            st.metric(
                label='Steals',
                value=player_data['player_stl_pg'],
                delta=f"{stl_percentile_str} %ile" if stl_percentile is not None else None
            )
        with col10:
            blk_percentile = player_data.get('blk_percentile')
            blk_percentile_str = pf.format_percentile(blk_percentile)
            st.metric(
                label='Blocks',
                value=player_data['player_blk_pg'],
                delta=f"{blk_percentile_str} %ile" if blk_percentile is not None else None
            )

# with st.container(height=1000, border=True):
#     st.altair_chart(player_data['final_chart'], width='content')

# Create tabs for Current Season, Predictions, and YoY Data
tab1, tab2, tab3 = st.tabs(["Current Season", "Predictions", "YoY Data"])

with tab1:
    # Display averages table with heatmap
    if player_data.get('averages_df') is not None and len(player_data['averages_df']) > 0:
        st.subheader("Averages")
        show_comparison = st.toggle("Show +/- vs Season", value=False, key="show_comparison")
    
        # Create heatmap styling
        averages_df = player_data['averages_df'].copy()
        
        # Ensure all numeric columns are formatted to 1 decimal place
        numeric_cols_to_format = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
        for col in numeric_cols_to_format:
            if col in averages_df.columns:
                averages_df[col] = averages_df[col].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) and str(x) != '' else x)
        
        # Get season row for comparison (last row)
        season_row_idx = len(averages_df) - 1
        season_row = averages_df.iloc[season_row_idx]
        
        # Function to apply heatmap colors
        def style_heatmap(row):
            styles = [''] * len(row)
            
            # Skip Period column (first column) and percentage columns
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            for i, col in enumerate(averages_df.columns):
                if col == 'Period':
                    continue
                
                if col in numeric_cols:
                    try:
                        # Handle string values that might be formatted
                        current_val_str = str(row[col]).replace(',', '')
                        season_val_str = str(season_row[col]).replace(',', '')
                        current_val = float(current_val_str)
                        season_val = float(season_val_str)
                        
                        if current_val > season_val:
                            # Green gradient - better than season
                            diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)  # Cap at 20% difference for max intensity
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < season_val:
                            # Red gradient - worse than season
                            diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            # Gray - same as season
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError):
                        pass
                elif col in pct_cols:
                    try:
                        # Extract percentage value
                        current_str = str(row[col]).replace('%', '')
                        season_str = str(season_row[col]).replace('%', '')
                        current_val = float(current_str)
                        season_val = float(season_str)
                        
                        if current_val > season_val:
                            diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < season_val:
                            diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError):
                        pass
            
            return styles
        
        # Add comparison columns if toggle is on
        if show_comparison:
            # Get season row values
            season_row = averages_df.iloc[-1]
            
            # Create comparison dataframe
            comparison_df = averages_df.copy()
            
            # Add +/- columns for numeric stats
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            # Insert comparison columns after each stat
            new_cols = ['Period']
            for col in averages_df.columns[1:]:  # Skip Period column
                new_cols.append(col)
                if col in numeric_cols:
                    # Add +/- column (already rounded to 1 decimal)
                    comparison_df[f'{col} +/-'] = comparison_df.apply(
                        lambda row: f"{round(float(str(row[col]).replace(',', '')) - float(str(season_row[col]).replace(',', '')), 1):+.1f}" if row.name != season_row_idx else '—',
                        axis=1
                    )
                    new_cols.append(f'{col} +/-')
                elif col in pct_cols:
                    # Add +/- column for percentages
                    comparison_df[f'{col} +/-'] = comparison_df.apply(
                        lambda row: f"{round(float(str(row[col]).replace('%', '')) - float(str(season_row[col]).replace('%', '')), 1):+.1f}%" if row.name != season_row_idx else '—',
                        axis=1
                    )
                    new_cols.append(f'{col} +/-')
            
            # Reorder columns
            comparison_df = comparison_df[new_cols]
            # Update heatmap function to handle comparison columns
            def style_heatmap_with_comparison(row):
                styles = [''] * len(row)
                for i, col in enumerate(comparison_df.columns):
                    if col == 'Period' or '+/-' in col:
                        continue
                    if col in numeric_cols:
                        try:
                            # Handle string values that might be formatted
                            current_val_str = str(row[col]).replace(',', '')
                            season_val_str = str(season_row[col]).replace(',', '')
                            current_val = float(current_val_str)
                            season_val = float(season_val_str)
                            if current_val > season_val:
                                diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                green_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                            elif current_val < season_val:
                                diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                red_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                            else:
                                styles[i] = 'background-color: rgb(240, 240, 240);'
                        except (ValueError, TypeError):
                            pass
                    elif col in pct_cols:
                        try:
                            current_str = str(row[col]).replace('%', '')
                            season_str = str(season_row[col]).replace('%', '')
                            current_val = float(current_str)
                            season_val = float(season_str)
                            if current_val > season_val:
                                diff_pct = ((current_val - season_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                green_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                            elif current_val < season_val:
                                diff_pct = ((season_val - current_val) / season_val * 100) if season_val > 0 else 0
                                intensity = min(diff_pct / 20, 1.0)
                                red_intensity = int(200 + (55 * intensity))
                                styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                            else:
                                styles[i] = 'background-color: rgb(240, 240, 240);'
                        except (ValueError, TypeError):
                            pass
                return styles
            styled_df = comparison_df.style.apply(style_heatmap_with_comparison, axis=1)
        else:
            styled_df = averages_df.style.apply(style_heatmap, axis=1)
        
        st.dataframe(styled_df, width='stretch', hide_index=True)

        # Display Opponent Defensive Stats (only when a matchup is selected)
        if matchup_away_team_id and matchup_home_team_id:
            # Determine which team is the opponent based on player's team
            player_team_id = player_data.get('team_id')
            if player_team_id:
                player_team_id = int(player_team_id)
                if player_team_id == matchup_away_team_id:
                    opponent_team_id = matchup_home_team_id
                    opponent_label = "Home"
                elif player_team_id == matchup_home_team_id:
                    opponent_team_id = matchup_away_team_id
                    opponent_label = "Away"
                else:
                    opponent_team_id = None
                    opponent_label = None
                
                if opponent_team_id:
                    # Load shooting data
                    team_stats, opp_team_stats, shooting_error = get_cached_shooting_data()
                    
                    if shooting_error:
                        st.warning(f"⚠️ Could not load defensive stats: {shooting_error}")
                    elif opp_team_stats is not None:
                        # Get opponent defensive stats
                        opp_def_stats = tds.get_team_defensive_stats(opponent_team_id, opp_team_stats)
                        
                        if opp_def_stats:
                            st.subheader(f"🛡️ Opponent Defense: {opp_def_stats['team_name']} ({opponent_label})")
                            st.caption("What opponents shoot against this team (lower rank = better defense)")
                            
                            # Create columns for defensive stats
                            def_col1, def_col2, def_col3, def_col4, def_col5 = st.columns(5)
                            
                            with def_col1:
                                rank_color = tds.get_rank_color(opp_def_stats['opp_fg_pct_rank'])
                                st.metric(
                                    label="Opp FG%",
                                    value=f"{opp_def_stats['opp_fg_pct']}%",
                                    delta=f"Rank: {opp_def_stats['opp_fg_pct_rank']}"
                                )
                            
                            with def_col2:
                                st.metric(
                                    label="Opp 2PT%",
                                    value=f"{opp_def_stats['opp_2pt_pct']}%",
                                    delta=f"Rank: {opp_def_stats['opp_2pt_pct_rank']}"
                                )
                            
                            with def_col3:
                                st.metric(
                                    label="Opp 3PT%",
                                    value=f"{opp_def_stats['opp_3pt_pct']}%",
                                    delta=f"Rank: {opp_def_stats['opp_3pt_pct_rank']}"
                                )
                            
                            with def_col4:
                                st.metric(
                                    label="Opp Rim FG%",
                                    value=f"{opp_def_stats['opp_rim_acc']}%",
                                    delta=f"Rank: {opp_def_stats['opp_rim_acc_rank']}"
                                )
                            
                            with def_col5:
                                st.metric(
                                    label="Opp FTA/G",
                                    value=f"{opp_def_stats['opp_fta_pg']}",
                                    delta=f"Rank: {opp_def_stats['opp_fta_rank']}"
                                )
                            
                            # Expandable section for zone shooting details
                            with st.expander("📍 Zone Shooting Defense Details", expanded=True):
                                # Helper function to get background color based on rank
                                # For defensive stats: low rank = good defense (red), high rank = bad defense (green)
                                def get_rank_color(rank, inverse=False):
                                    """
                                    Returns background color based on rank (1-30).
                                    For defensive stats: low rank = good defense = red (bad for player)
                                    high rank = bad defense = green (good for player)
                                    
                                    inverse=True flips the colors (for frequency - high allowed freq is bad defense)
                                    """
                                    try:
                                        rank = int(rank)
                                    except:
                                        return "transparent"
                                    
                                    # Normalize rank to 0-1 scale (1=best, 30=worst)
                                    normalized = (rank - 1) / 29  # 0 = rank 1, 1 = rank 30
                                    
                                    if inverse:
                                        normalized = 1 - normalized
                                    
                                    # Color gradient: Red (good defense) -> Yellow (neutral) -> Green (bad defense)
                                    if normalized < 0.5:
                                        # Red to Yellow (good to neutral defense)
                                        r = 255
                                        g = int(255 * (normalized * 2))  # 0 -> 255
                                        b = 100
                                    else:
                                        # Yellow to Green (neutral to bad defense)
                                        r = int(255 * (1 - (normalized - 0.5) * 2))  # 255 -> 0
                                        g = 255
                                        b = 100
                                    
                                    return f"rgba({r}, {g}, {b}, 0.3)"
                                
                                def styled_stat(label, value, rank, inverse=False):
                                    """Create a styled stat display with colored background based on rank"""
                                    bg_color = get_rank_color(rank, inverse)
                                    return f'''
                                    <div style="background-color: {bg_color}; padding: 8px; border-radius: 5px; margin: 4px 0;">
                                        <span style="font-size: 14px;">{label}: <strong>{value}</strong></span>
                                        <span style="font-size: 12px; color: #666;"> (#{rank})</span>
                                    </div>
                                    '''
                                
                                zone_col1, zone_col2, zone_col3, zone_col4, zone_col5 = st.columns(5)
                                
                                with zone_col1:
                                    st.markdown("**At Rim**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_rim_freq']}%", opp_def_stats['opp_rim_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_rim_acc']}%", opp_def_stats['opp_rim_acc_rank']), unsafe_allow_html=True)
                                
                                with zone_col2:
                                    st.markdown("**Short Mid-Range**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_smr_freq']}%", opp_def_stats['opp_smr_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_smr_acc']}%", opp_def_stats['opp_smr_acc_rank']), unsafe_allow_html=True)
                                
                                with zone_col3:
                                    st.markdown("**Long Mid-Range**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_lmr_freq']}%", opp_def_stats['opp_lmr_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_lmr_acc']}%", opp_def_stats['opp_lmr_acc_rank']), unsafe_allow_html=True)
                                
                                with zone_col4:
                                    st.markdown("**Corner 3**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_c3_freq']}%", opp_def_stats['opp_c3_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_c3_acc']}%", opp_def_stats['opp_c3_acc_rank']), unsafe_allow_html=True)
                                
                                with zone_col5:
                                    st.markdown("**Above Break 3**")
                                    st.markdown(styled_stat("Freq", f"{opp_def_stats['opp_atb3_freq']}%", opp_def_stats['opp_atb3_freq_rank']), unsafe_allow_html=True)
                                    st.markdown(styled_stat("FG%", f"{opp_def_stats['opp_atb3_acc']}%", opp_def_stats['opp_atb3_acc_rank']), unsafe_allow_html=True)
                                
                                # Add legend
                                st.markdown("""
                                <div style="margin-top: 10px; padding: 8px; background-color: #f0f0f0; border-radius: 5px; font-size: 12px;">
                                    <strong>Legend:</strong> 
                                    <span style="background-color: rgba(255, 100, 100, 0.3); padding: 2px 8px; border-radius: 3px;">🔴 Good Defense (tough matchup)</span>
                                    <span style="background-color: rgba(255, 255, 100, 0.3); padding: 2px 8px; border-radius: 3px; margin-left: 10px;">🟡 Average</span>
                                    <span style="background-color: rgba(100, 255, 100, 0.3); padding: 2px 8px; border-radius: 3px; margin-left: 10px;">🟢 Bad Defense (favorable matchup)</span>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            # Zone Matchup Analysis - Player vs Opponent
                            st.subheader("🎯 Zone Matchup Analysis")
                            st.caption("Color based on opponent defensive FG% rank: 🔴 Rank 1-10 (tough defense) → 🟡 Rank 11-20 (average) → 🟢 Rank 21-30 (weak defense)")
                            
                            # Load player shooting data
                            player_shooting_df, player_shooting_error = get_cached_player_shooting_data()
                            
                            if player_shooting_error:
                                st.warning(f"⚠️ Could not load player shooting data: {player_shooting_error}")
                            elif player_shooting_df is not None:
                                # Get player zone shooting stats
                                player_zones = tds.get_player_zone_shooting(selected_player_id, player_shooting_df)
                                
                                if player_zones:
                                    # Compare player zones to opponent defense
                                    zone_comparisons = tds.compare_player_vs_opponent_zones(player_zones, opp_def_stats)
                                    
                                    if zone_comparisons:
                                        # Display zone matchup cards
                                        matchup_cols = st.columns(5)
                                        zone_keys = ['rim', 'smr', 'lmr', 'c3', 'atb3']
                                        
                                        for i, zone_key in enumerate(zone_keys):
                                            zone_data = zone_comparisons[zone_key]
                                            # Use rank-based coloring instead of difference-based
                                            bg_color = tds.get_matchup_color_by_rank(zone_data['opp_acc_rank'])
                                            
                                            with matchup_cols[i]:
                                                # Create a styled card using markdown
                                                diff_sign = "+" if zone_data['difference'] >= 0 else ""
                                                st.markdown(f"""
                                                <div style="background-color: {bg_color}; padding: 15px; border-radius: 8px; text-align: center; margin-bottom: 8px;">
                                                    <div style="font-weight: bold; font-size: 18px; margin-bottom: 10px;">{zone_data['zone_name']}</div>
                                                    <div style="font-size: 15px; color: #444;">Player: <strong>{zone_data['player_pct']}%</strong></div>
                                                    <div style="font-size: 15px; color: #444;">Opp Allows: <strong>{zone_data['opp_allowed_pct']}%</strong> (#{zone_data['opp_acc_rank']})</div>
                                                    <div style="font-size: 22px; font-weight: bold; margin-top: 10px;">{diff_sign}{zone_data['difference']}%</div>
                                                    <div style="font-size: 13px; color: #666;">Freq: {zone_data['player_freq']}% ({zone_data['player_fga']} FGA)</div>
                                                </div>
                                                """, unsafe_allow_html=True)
                                else:
                                    st.info("Could not load player zone shooting data.")
                            
                            st.divider()

        # ============================================================
        # SIMILAR PLAYERS SECTION
        # ============================================================
        st.subheader("👥 Similar Players")
        st.caption("Players with similar statistical profiles based on scoring, shooting, playmaking, and play style")
        
        with st.spinner("Finding similar players..."):
            similar_players = ps.get_similar_players(
                player_id=int(selected_player_id),
                n=5,
                min_similarity=0.0,
                exclude_same_team=False
            )
        
        if similar_players:
            # Create columns for player cards
            sim_cols = st.columns(5)
            
            # Team abbreviation to full name mapping
            team_full_names = {
                'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
                'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
                'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
                'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
                'LAC': 'LA Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
                'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
                'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
                'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
                'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
                'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
            }
            
            for i, sim_player in enumerate(similar_players):
                with sim_cols[i]:
                    sim_headshot = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{sim_player['player_id']}.png"
                    similarity_color = "#28a745" if sim_player['similarity'] >= 70 else "#ffc107" if sim_player['similarity'] >= 55 else "#6c757d"
                    
                    # Look up position from players dataframe
                    sim_player_row = players_df[players_df['PERSON_ID'] == sim_player['player_id']]
                    position = sim_player_row['POSITION'].iloc[0] if len(sim_player_row) > 0 else ''
                    
                    # Get team abbreviation and full name
                    team_abbr = sim_player.get('team_abbr', sim_player.get('team', ''))
                    team_full = team_full_names.get(team_abbr, team_abbr)
                    
                    # Get shooting percentages
                    fg_pct = sim_player.get('fg_pct', 0)
                    fg3_pct = sim_player.get('fg3_pct', 0)
                    ft_pct = sim_player.get('ft_pct', 0)
                    
                    st.markdown(f"""
                        <div style="text-align: center; padding: 15px; border: 1px solid #ddd; border-radius: 12px; background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);">
                            <img src="{sim_headshot}" style="width: 225px; height: 170px; object-fit: cover; border-radius: 8px; margin-bottom: 12px;" onerror="this.style.display='none'">
                            <div style="font-weight: bold; font-size: 18px; margin-bottom: 6px;">{sim_player['player_name']}</div>
                            <div style="font-size: 15px; color: #555; margin-bottom: 10px;">{position} | {team_full}</div>
                            <div style="background: {similarity_color}; color: white; padding: 5px 12px; border-radius: 14px; font-size: 16px; font-weight: bold; display: inline-block;">
                                {sim_player['similarity']}% Match
                            </div>
                            <div style="font-size: 16px; color: #333; margin-top: 12px; font-weight: 500;">
                                {sim_player['ppg']} PPG | {sim_player['rpg']} RPG | {sim_player['apg']} APG
                            </div>
                            <div style="font-size: 14px; color: #555; margin-top: 6px;">
                                {fg_pct}% FG | {fg3_pct}% 3PT | {ft_pct}% FT
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            
            # Show what stats are being used
            with st.expander("ℹ️ How similarity is calculated"):
                st.markdown("""
                **Stats included in similarity calculation:**
                - **Per-game stats**: PTS, REB, AST, STL, BLK, TOV, MIN
                - **Shooting volume**: FGM, FGA, 3PM, 3PA, FTM, FTA
                - **Shooting efficiency**: FG%, 3P%, FT%
                - **Shot distribution**: 3PA rate, FTA rate, zone frequencies
                - **Play style**: Drives/game, points in paint, fast break points
                - **Role**: Usage rate
                
                Players are compared using cosine similarity on standardized (z-score normalized) stats.
                Higher similarity % means more similar statistical profile.
                """)
        else:
            st.info("No similar players found. This may happen for players with limited games or unique stat profiles.")
            
            # Debug info in expander
            with st.expander("🔍 Debug Info"):
                try:
                    features_df, feature_cols = ps.build_similarity_features()
                    if features_df.empty:
                        st.warning("Feature DataFrame is empty - data fetching may have failed")
                    else:
                        st.write(f"Total players in database: {len(features_df)}")
                        st.write(f"Features used: {len(feature_cols)}")
                        
                        # Check if selected player is in the data
                        player_in_data = int(selected_player_id) in features_df['PLAYER_ID'].values
                        st.write(f"Selected player in data: {player_in_data}")
                        
                        if player_in_data:
                            player_row = features_df[features_df['PLAYER_ID'] == int(selected_player_id)].iloc[0]
                            st.write(f"Player GP: {player_row.get('GP', 'N/A')}, MIN: {player_row.get('MIN', 'N/A')}")
                except Exception as e:
                    st.error(f"Debug error: {e}")
        
        st.divider()

        # Display recent game logs table with pagination
        if player_data.get('recent_games_df') is not None and len(player_data['recent_games_df']) > 0:
            st.subheader("Game Logs")
            
            # Get full game logs (not just recent 10)
            full_game_logs = player_data.get('full_game_logs_df', player_data['recent_games_df'])
            total_games = len(full_game_logs)
            
            # Pagination settings
            games_per_page = 10
            total_pages = math.ceil(total_games / games_per_page)
            
            # Page selector
            col_pagination_left, col_pagination_center, col_pagination_right = st.columns([0.3, 0.4, 0.3])
            
            with col_pagination_center:
                if total_pages > 1:
                    current_page = st.selectbox(
                        f"Page (Total: {total_games} games)",
                        options=list(range(1, total_pages + 1)),
                        format_func=lambda x: f"Page {x} of {total_pages}",
                        key="game_logs_page"
                    )
                else:
                    current_page = 1
                    st.caption(f"Showing all {total_games} games")
            
            # Calculate start and end indices
            start_idx = (current_page - 1) * games_per_page
            end_idx = min(start_idx + games_per_page, total_games)
            
            # Get current page of games
            page_games_df = full_game_logs.iloc[start_idx:end_idx].copy()
            
            show_game_comparison = st.toggle("Show vs Season Avg", value=False, key="show_game_comparison")
            
            # Get season averages for comparison
            if show_game_comparison and player_data.get('averages_df') is not None:
                season_avg = player_data['averages_df'].iloc[-1]  # Last row is season
                
                game_logs_df = page_games_df.copy()
                
                # Add comparison columns
                numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
                pct_cols = ['2P%', '3P%', 'FT%']
                
                # Create new columns list with comparison columns
                new_cols = []
                for col in game_logs_df.columns:
                    new_cols.append(col)
                    if col in numeric_cols:
                        # Add vs Avg column
                        try:
                            season_val = float(season_avg[col])
                            game_logs_df[f'{col} vs Avg'] = game_logs_df[col].apply(
                                lambda x: f"{round(float(x) - season_val, 1):+.1f}" if pd.notna(x) else ''
                            )
                            new_cols.append(f'{col} vs Avg')
                        except (ValueError, KeyError):
                            pass
                    elif col in pct_cols:
                        # Add vs Avg column for percentages
                        try:
                            season_str = str(season_avg[col]).replace('%', '')
                            season_val = float(season_str)
                            game_logs_df[f'{col} vs Avg'] = game_logs_df[col].apply(
                                lambda x: f"{round(float(str(x).replace('%', '')) - season_val, 1):+.1f}%" if pd.notna(x) else ''
                            )
                            new_cols.append(f'{col} vs Avg')
                        except (ValueError, KeyError):
                            pass
                
                game_logs_df = game_logs_df[new_cols]
                st.dataframe(game_logs_df, width='stretch', hide_index=True)
            else:
                st.dataframe(
                    page_games_df,
                    width='stretch',
                    hide_index=True
                )
            
            # Show page info at bottom
            if total_pages > 1:
                st.caption(f"Showing games {start_idx + 1}-{end_idx} of {total_games}")
        else:
            st.info("No game logs available for this player.")
        
        # Section: Performance vs Selected Opponent
        if matchup_away_team_id and matchup_home_team_id and player_data.get('full_game_logs_df') is not None:
            # Determine opponent team abbreviation based on player's team
            player_team_id = player_data.get('team_id')
            opponent_abbr = None
            
            if player_team_id:
                player_team_id = int(player_team_id)
                if player_team_id == matchup_away_team_id:
                    opponent_abbr = matchup_home_team_abbr
                elif player_team_id == matchup_home_team_id:
                    opponent_abbr = matchup_away_team_abbr
            
            if opponent_abbr:
                full_game_logs = player_data['full_game_logs_df']
                
                # Filter games against the opponent
                vs_opponent_games = full_game_logs[full_game_logs['Opponent'] == opponent_abbr].copy()
                
                if len(vs_opponent_games) > 0:
                    st.divider()
                    st.subheader(f"📊 Performance vs {opponent_abbr} (2025-26)")
                    
                    # Calculate averages against opponent
                    numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
                    
                    # Calculate averages
                    vs_opp_avgs = {}
                    for col in numeric_cols:
                        if col in vs_opponent_games.columns:
                            vs_opp_avgs[col] = round(vs_opponent_games[col].astype(float).mean(), 1)
                    
                    # Calculate shooting percentages from totals
                    total_2pm = vs_opponent_games['2PM'].astype(float).sum()
                    total_2pa = vs_opponent_games['2PA'].astype(float).sum()
                    total_3pm = vs_opponent_games['3PM'].astype(float).sum()
                    total_3pa = vs_opponent_games['3PA'].astype(float).sum()
                    total_ftm = vs_opponent_games['FTM'].astype(float).sum()
                    total_fta = vs_opponent_games['FTA'].astype(float).sum()
                    
                    vs_opp_avgs['2P%'] = f"{round(total_2pm / total_2pa * 100, 1)}%" if total_2pa > 0 else "0.0%"
                    vs_opp_avgs['3P%'] = f"{round(total_3pm / total_3pa * 100, 1)}%" if total_3pa > 0 else "0.0%"
                    vs_opp_avgs['FT%'] = f"{round(total_ftm / total_fta * 100, 1)}%" if total_fta > 0 else "0.0%"
                    
                    # Get season averages for comparison (from averages_df)
                    season_avgs = {}
                    averages_df = player_data.get('averages_df')
                    if averages_df is not None and len(averages_df) > 0:
                        # Get the "Season" row from averages_df
                        season_row = averages_df[averages_df['Period'] == 'Season']
                        if len(season_row) > 0:
                            season_row = season_row.iloc[0]
                            for col in ['PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK']:
                                if col in season_row:
                                    try:
                                        season_avgs[col] = float(season_row[col])
                                    except:
                                        pass
                            # Get shooting percentages
                            for pct_col in ['3P%', 'FT%']:
                                if pct_col in season_row:
                                    try:
                                        season_avgs[pct_col] = float(str(season_row[pct_col]).replace('%', ''))
                                    except:
                                        pass
                    
                    # Display averages with delta vs season average
                    st.markdown(f"**Averages vs {opponent_abbr}** ({len(vs_opponent_games)} games) - *Delta shows difference from season avg*")
                    
                    avg_cols = st.columns(8)
                    stat_labels = ['PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', '3P%', 'FT%']
                    
                    for i, stat in enumerate(stat_labels):
                        with avg_cols[i]:
                            if stat in vs_opp_avgs:
                                vs_val = vs_opp_avgs[stat]
                                
                                # Calculate delta if we have season average
                                delta_str = None
                                if stat in season_avgs:
                                    if stat in ['3P%', 'FT%']:
                                        # For percentages, parse the string value
                                        try:
                                            vs_pct = float(str(vs_val).replace('%', ''))
                                            season_pct = season_avgs[stat]
                                            delta = round(vs_pct - season_pct, 1)
                                            delta_str = f"{'+' if delta >= 0 else ''}{delta}%"
                                        except:
                                            pass
                                    else:
                                        # For regular stats
                                        delta = round(vs_val - season_avgs[stat], 1)
                                        delta_str = f"{'+' if delta >= 0 else ''}{delta}"
                                
                                st.metric(label=stat, value=vs_val, delta=delta_str)
                    
                    # Display game logs against opponent
                    st.markdown(f"**Game Logs vs {opponent_abbr}**")
                    st.dataframe(vs_opponent_games, width='stretch', hide_index=True)
                else:
                    st.divider()
                    st.info(f"ℹ️ No games played against {opponent_abbr} this season yet.")
                
                # ============================================================
                # SIMILAR PLAYERS VS OPPONENT SECTION
                # ============================================================
                # Show this section even if selected player has no games vs opponent
                if similar_players and len(similar_players) > 0:
                        st.divider()
                        st.markdown(f"### 👥 Similar Players vs {opponent_abbr}")
                        st.caption(f"How players with similar profiles performed against {opponent_abbr} this season")
                        
                        # Get game logs for similar players vs this opponent
                        # Use the bulk game logs from prediction_features
                        all_player_game_logs = pf_features.get_bulk_player_game_logs()
                        
                        if all_player_game_logs is not None and len(all_player_game_logs) > 0:
                            # Filter to only show players with 70%+ similarity in game logs section
                            filtered_similar_players = [p for p in similar_players if p['similarity'] >= 70.0]
                            
                            # Exclude similar players who play for the opponent team
                            if opponent_abbr:
                                filtered_similar_players = [
                                    p for p in filtered_similar_players 
                                    if p.get('team_abbr', '').upper() != opponent_abbr.upper()
                                ]
                            
                            # Collect all games from all similar players vs opponent
                            all_similar_games = []
                            for sim_player in filtered_similar_players:
                                sim_id = sim_player['player_id']
                                sim_games = all_player_game_logs[
                                    (all_player_game_logs['PLAYER_ID'] == sim_id) &
                                    (all_player_game_logs['MATCHUP'].str.contains(opponent_abbr, na=False))
                                ]
                                if len(sim_games) > 0:
                                    all_similar_games.append(sim_games)
                            
                            # Calculate aggregate averages across all similar players
                            if len(all_similar_games) > 0:
                                combined_games = pd.concat(all_similar_games, ignore_index=True)
                                
                                # Calculate aggregate averages
                                agg_avg_pts = round(combined_games['PTS'].astype(float).mean(), 1) if 'PTS' in combined_games.columns else 0
                                agg_avg_reb = round(combined_games['REB'].astype(float).mean(), 1) if 'REB' in combined_games.columns else 0
                                agg_avg_ast = round(combined_games['AST'].astype(float).mean(), 1) if 'AST' in combined_games.columns else 0
                                agg_avg_pra = round((combined_games['REB'].astype(float) + combined_games['AST'].astype(float)).mean(), 1) if 'REB' in combined_games.columns and 'AST' in combined_games.columns else 0
                                agg_avg_stl = round(combined_games['STL'].astype(float).mean(), 1) if 'STL' in combined_games.columns else 0
                                agg_avg_blk = round(combined_games['BLK'].astype(float).mean(), 1) if 'BLK' in combined_games.columns else 0
                                
                                # Calculate aggregate shooting percentages
                                agg_3p_pct = 0
                                agg_ft_pct = 0
                                
                                if 'FG3M' in combined_games.columns and 'FG3A' in combined_games.columns:
                                    total_agg_3pm = combined_games['FG3M'].astype(float).sum()
                                    total_agg_3pa = combined_games['FG3A'].astype(float).sum()
                                    agg_3p_pct = round(total_agg_3pm / total_agg_3pa * 100, 1) if total_agg_3pa > 0 else 0
                                
                                if 'FTM' in combined_games.columns and 'FTA' in combined_games.columns:
                                    total_agg_ftm = combined_games['FTM'].astype(float).sum()
                                    total_agg_fta = combined_games['FTA'].astype(float).sum()
                                    agg_ft_pct = round(total_agg_ftm / total_agg_fta * 100, 1) if total_agg_fta > 0 else 0
                                
                                # Display aggregate averages as metric tiles
                                st.markdown(f"**Combined Averages** ({len(combined_games)} games from {len(filtered_similar_players)} similar players)")
                                agg_avg_cols = st.columns(8)
                                agg_stat_labels = ['PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', '3P%', 'FT%']
                                agg_stat_values = [agg_avg_pts, agg_avg_reb, agg_avg_ast, agg_avg_pra, agg_avg_stl, agg_avg_blk, f"{agg_3p_pct}%", f"{agg_ft_pct}%"]
                                
                                for i, (stat, value) in enumerate(zip(agg_stat_labels, agg_stat_values)):
                                    with agg_avg_cols[i]:
                                        st.metric(label=stat, value=value)
                                
                                st.divider()
                            
                            # Track if any games were found
                            games_found = False
                            
                            # Group games by player (individual player sections)
                            for sim_player in filtered_similar_players:
                                sim_id = sim_player['player_id']
                                sim_name = sim_player['player_name']
                                sim_similarity = sim_player['similarity']
                                
                                # Filter game logs for this similar player vs opponent
                                sim_games = all_player_game_logs[
                                    (all_player_game_logs['PLAYER_ID'] == sim_id) &
                                    (all_player_game_logs['MATCHUP'].str.contains(opponent_abbr, na=False))
                                ].copy()
                                
                                if len(sim_games) > 0:
                                    games_found = True
                                    
                                    # Format the dataframe to match player's game logs
                                    sim_games_formatted = sim_games.copy()
                                    
                                    # Round MIN to whole number
                                    if 'MIN' in sim_games_formatted.columns:
                                        sim_games_formatted['MIN'] = sim_games_formatted['MIN'].apply(lambda x: int(round(float(x))) if pd.notna(x) else 0)
                                    
                                    # Format date as MM/DD/YYYY and rename to "Date"
                                    if 'GAME_DATE' in sim_games_formatted.columns:
                                        def format_date_mmddyyyy(date_val):
                                            try:
                                                from datetime import datetime
                                                # Handle both datetime objects and strings
                                                if isinstance(date_val, pd.Timestamp):
                                                    return date_val.strftime('%m/%d/%Y')
                                                elif isinstance(date_val, datetime):
                                                    return date_val.strftime('%m/%d/%Y')
                                                else:
                                                    # Try parsing as string
                                                    date_str = str(date_val)
                                                    # Handle "2025-11-12 00:00:00" format
                                                    if ' ' in date_str:
                                                        date_str = date_str.split(' ')[0]
                                                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                                                    return dt.strftime('%m/%d/%Y')
                                            except Exception as e:
                                                return str(date_val)
                                        sim_games_formatted['Date'] = sim_games_formatted['GAME_DATE'].apply(format_date_mmddyyyy)
                                    
                                    # Rename WL to W/L
                                    if 'WL' in sim_games_formatted.columns:
                                        sim_games_formatted['W/L'] = sim_games_formatted['WL']
                                    
                                    # Calculate PRA (REB + AST)
                                    if 'REB' in sim_games_formatted.columns and 'AST' in sim_games_formatted.columns:
                                        sim_games_formatted['PRA'] = sim_games_formatted['REB'].astype(float) + sim_games_formatted['AST'].astype(float)
                                    
                                    # Calculate 2PM and 2PA (FGM - FG3M, FGA - FG3A)
                                    if 'FGM' in sim_games_formatted.columns and 'FG3M' in sim_games_formatted.columns:
                                        sim_games_formatted['2PM'] = (sim_games_formatted['FGM'].astype(float) - sim_games_formatted['FG3M'].astype(float)).apply(lambda x: int(x) if pd.notna(x) else 0)
                                    if 'FGA' in sim_games_formatted.columns and 'FG3A' in sim_games_formatted.columns:
                                        sim_games_formatted['2PA'] = (sim_games_formatted['FGA'].astype(float) - sim_games_formatted['FG3A'].astype(float)).apply(lambda x: int(x) if pd.notna(x) else 0)
                                    
                                    # Calculate 2P%
                                    if '2PM' in sim_games_formatted.columns and '2PA' in sim_games_formatted.columns:
                                        sim_games_formatted['2P%'] = sim_games_formatted.apply(
                                            lambda row: f"{round(row['2PM'] / row['2PA'] * 100, 1)}%" if pd.notna(row['2PA']) and row['2PA'] > 0 else "0.0%",
                                            axis=1
                                        )
                                    
                                    # Format 3PM and 3PA as integers
                                    if 'FG3M' in sim_games_formatted.columns:
                                        sim_games_formatted['3PM'] = sim_games_formatted['FG3M'].apply(lambda x: int(x) if pd.notna(x) else 0)
                                    if 'FG3A' in sim_games_formatted.columns:
                                        sim_games_formatted['3PA'] = sim_games_formatted['FG3A'].apply(lambda x: int(x) if pd.notna(x) else 0)
                                    
                                    # Format 3P%
                                    if 'FG3_PCT' in sim_games_formatted.columns:
                                        sim_games_formatted['3P%'] = sim_games_formatted['FG3_PCT'].apply(lambda x: f"{round(float(x) * 100, 1)}%" if pd.notna(x) else '0.0%')
                                    
                                    # Format FTM and FTA as integers
                                    if 'FTM' in sim_games_formatted.columns:
                                        sim_games_formatted['FTM'] = sim_games_formatted['FTM'].apply(lambda x: int(x) if pd.notna(x) else 0)
                                    if 'FTA' in sim_games_formatted.columns:
                                        sim_games_formatted['FTA'] = sim_games_formatted['FTA'].apply(lambda x: int(x) if pd.notna(x) else 0)
                                    
                                    # Format FT%
                                    if 'FT_PCT' in sim_games_formatted.columns:
                                        sim_games_formatted['FT%'] = sim_games_formatted['FT_PCT'].apply(lambda x: f"{round(float(x) * 100, 1)}%" if pd.notna(x) else '0.0%')
                                    
                                    # Select columns in the exact order specified
                                    display_cols = ['Date', 'MATCHUP', 'W/L', 'MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '2P%', '3PM', '3PA', '3P%', 'FTM', 'FTA', 'FT%']
                                    
                                    # Filter to only columns that exist
                                    display_cols = [col for col in display_cols if col in sim_games_formatted.columns]
                                    sim_games_display = sim_games_formatted[display_cols].copy()
                                    
                                    # Header with "Similarity" word
                                    st.markdown(f"**Game Logs for {sim_name} ({sim_similarity}% Similarity) vs {opponent_abbr}**")
                                    
                                    # Display dataframe
                                    st.dataframe(sim_games_display, width='stretch', hide_index=True)
                                    
                                    # Calculate averages for this player
                                    sim_avg_pts = round(sim_games['PTS'].astype(float).mean(), 1) if 'PTS' in sim_games.columns else 0
                                    sim_avg_reb = round(sim_games['REB'].astype(float).mean(), 1) if 'REB' in sim_games.columns else 0
                                    sim_avg_ast = round(sim_games['AST'].astype(float).mean(), 1) if 'AST' in sim_games.columns else 0
                                    sim_avg_pra = round((sim_games['REB'].astype(float) + sim_games['AST'].astype(float)).mean(), 1) if 'REB' in sim_games.columns and 'AST' in sim_games.columns else 0
                                    sim_avg_stl = round(sim_games['STL'].astype(float).mean(), 1) if 'STL' in sim_games.columns else 0
                                    sim_avg_blk = round(sim_games['BLK'].astype(float).mean(), 1) if 'BLK' in sim_games.columns else 0
                                    
                                    # Calculate shooting percentages
                                    sim_fg_pct = 0
                                    sim_3p_pct = 0
                                    sim_ft_pct = 0
                                    
                                    if 'FGM' in sim_games.columns and 'FGA' in sim_games.columns:
                                        total_fgm = sim_games['FGM'].astype(float).sum()
                                        total_fga = sim_games['FGA'].astype(float).sum()
                                        sim_fg_pct = round(total_fgm / total_fga * 100, 1) if total_fga > 0 else 0
                                    
                                    if 'FG3M' in sim_games.columns and 'FG3A' in sim_games.columns:
                                        total_3pm = sim_games['FG3M'].astype(float).sum()
                                        total_3pa = sim_games['FG3A'].astype(float).sum()
                                        sim_3p_pct = round(total_3pm / total_3pa * 100, 1) if total_3pa > 0 else 0
                                    
                                    if 'FTM' in sim_games.columns and 'FTA' in sim_games.columns:
                                        total_ftm = sim_games['FTM'].astype(float).sum()
                                        total_fta = sim_games['FTA'].astype(float).sum()
                                        sim_ft_pct = round(total_ftm / total_fta * 100, 1) if total_fta > 0 else 0
                                    
                                    # Get season averages for this similar player (for delta calculation)
                                    sim_season_games = all_player_game_logs[all_player_game_logs['PLAYER_ID'] == sim_id]
                                    sim_season_avg_pts = round(sim_season_games['PTS'].astype(float).mean(), 1) if len(sim_season_games) > 0 and 'PTS' in sim_season_games.columns else 0
                                    sim_season_avg_reb = round(sim_season_games['REB'].astype(float).mean(), 1) if len(sim_season_games) > 0 and 'REB' in sim_season_games.columns else 0
                                    sim_season_avg_ast = round(sim_season_games['AST'].astype(float).mean(), 1) if len(sim_season_games) > 0 and 'AST' in sim_season_games.columns else 0
                                    sim_season_avg_pra = round((sim_season_games['REB'].astype(float) + sim_season_games['AST'].astype(float)).mean(), 1) if len(sim_season_games) > 0 and 'REB' in sim_season_games.columns and 'AST' in sim_season_games.columns else 0
                                    sim_season_avg_stl = round(sim_season_games['STL'].astype(float).mean(), 1) if len(sim_season_games) > 0 and 'STL' in sim_season_games.columns else 0
                                    sim_season_avg_blk = round(sim_season_games['BLK'].astype(float).mean(), 1) if len(sim_season_games) > 0 and 'BLK' in sim_season_games.columns else 0
                                    
                                    # Calculate season shooting percentages
                                    sim_season_3p_pct = 0
                                    sim_season_ft_pct = 0
                                    
                                    if len(sim_season_games) > 0:
                                        if 'FG3M' in sim_season_games.columns and 'FG3A' in sim_season_games.columns:
                                            total_season_3pm = sim_season_games['FG3M'].astype(float).sum()
                                            total_season_3pa = sim_season_games['FG3A'].astype(float).sum()
                                            sim_season_3p_pct = round(total_season_3pm / total_season_3pa * 100, 1) if total_season_3pa > 0 else 0
                                        
                                        if 'FTM' in sim_season_games.columns and 'FTA' in sim_season_games.columns:
                                            total_season_ftm = sim_season_games['FTM'].astype(float).sum()
                                            total_season_fta = sim_season_games['FTA'].astype(float).sum()
                                            sim_season_ft_pct = round(total_season_ftm / total_season_fta * 100, 1) if total_season_fta > 0 else 0
                                    
                                    # Calculate deltas
                                    delta_pts = round(sim_avg_pts - sim_season_avg_pts, 1) if sim_season_avg_pts > 0 else None
                                    delta_reb = round(sim_avg_reb - sim_season_avg_reb, 1) if sim_season_avg_reb > 0 else None
                                    delta_ast = round(sim_avg_ast - sim_season_avg_ast, 1) if sim_season_avg_ast > 0 else None
                                    delta_pra = round(sim_avg_pra - sim_season_avg_pra, 1) if sim_season_avg_pra > 0 else None
                                    delta_stl = round(sim_avg_stl - sim_season_avg_stl, 1) if sim_season_avg_stl > 0 else None
                                    delta_blk = round(sim_avg_blk - sim_season_avg_blk, 1) if sim_season_avg_blk > 0 else None
                                    delta_3p = round(sim_3p_pct - sim_season_3p_pct, 1) if sim_season_3p_pct > 0 else None
                                    delta_ft = round(sim_ft_pct - sim_season_ft_pct, 1) if sim_season_ft_pct > 0 else None
                                    
                                    # Display averages as metric tiles with deltas (matching player's format)
                                    st.markdown(f"**Averages vs {opponent_abbr}** ({len(sim_games)} games) - *Delta shows difference from season avg*")
                                    sim_avg_cols = st.columns(8)
                                    sim_stat_labels = ['PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', '3P%', 'FT%']
                                    sim_stat_values = [sim_avg_pts, sim_avg_reb, sim_avg_ast, sim_avg_pra, sim_avg_stl, sim_avg_blk, f"{sim_3p_pct}%", f"{sim_ft_pct}%"]
                                    sim_stat_deltas = [delta_pts, delta_reb, delta_ast, delta_pra, delta_stl, delta_blk, f"{delta_3p}%" if delta_3p is not None else None, f"{delta_ft}%" if delta_ft is not None else None]
                                    
                                    for i, (stat, value, delta) in enumerate(zip(sim_stat_labels, sim_stat_values, sim_stat_deltas)):
                                        with sim_avg_cols[i]:
                                            st.metric(label=stat, value=value, delta=delta)
                                    
                                    st.divider()
                            
                            # Show message if no games found for any similar players
                            if not games_found:
                                st.info(f"No games found for similar players vs {opponent_abbr} this season.")

with tab2:
    # Predictions tab
    st.subheader("🔮 Stat Predictions")
    
    # Check if a matchup is selected
    if matchup_away_team_id and matchup_home_team_id:
        # Determine opponent based on player's team
        player_team_id = player_data.get('team_id')
        opponent_team_id = None
        opponent_abbr = None
        is_home = None
        
        if player_team_id:
            player_team_id = int(player_team_id)
            if player_team_id == matchup_away_team_id:
                opponent_team_id = matchup_home_team_id
                opponent_abbr = matchup_home_team_abbr
                is_home = False
            elif player_team_id == matchup_home_team_id:
                opponent_team_id = matchup_away_team_id
                opponent_abbr = matchup_away_team_abbr
                is_home = True
        
        if opponent_team_id and opponent_abbr:
            st.info(f"📊 Generating predictions for **{player_data['player_info_name']}** vs **{opponent_abbr}** ({'Home' if is_home else 'Away'})")
            
            # Get game date string
            game_date_str = selected_date.strftime('%Y-%m-%d')
            
            # === INJURY REPORT SECTION ===
            st.markdown("---")
            with st.expander("🏥 **Injury Report** - Official NBA injury data", expanded=True):
                st.caption("Players marked OUT/Doubtful are auto-selected below")
                
                # Use the pre-fetched injury data from initial load
                # Create a matchup-specific key for session state
                matchup_key = f"{matchup_away_team_abbr}@{matchup_home_team_abbr}"
                
                # Initialize session state for this matchup if needed
                if 'processed_matchups' not in st.session_state:
                    st.session_state.processed_matchups = {}
                
                # Process injuries for this matchup (only once per matchup)
                if matchup_key not in st.session_state.processed_matchups:
                    away_out = []
                    home_out = []
                    all_matchup_injuries = {'away': [], 'home': []}
                    questionable_probable = {'away': [], 'home': []}
                    
                    if injury_report_df is not None and len(injury_report_df) > 0:
                        # Get injuries for this specific matchup
                        matchup_injuries = ir.get_injuries_for_matchup(
                            injury_report_df,
                            matchup_away_team_abbr,
                            matchup_home_team_abbr,
                            players_df
                        )
                        
                        # Separate OUT/DOUBTFUL from QUESTIONABLE/PROBABLE
                        away_questionable = []
                        for injury_item in matchup_injuries['away']:
                            status_lower = injury_item['status'].lower() if injury_item['status'] else ''
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item['player_id']:
                                    away_out.append(injury_item['player_id'])
                                away_questionable.append(injury_item)
                            elif 'questionable' in status_lower or 'probable' in status_lower:
                                away_questionable.append(injury_item)
                        
                        home_questionable = []
                        for injury_item in matchup_injuries['home']:
                            status_lower = injury_item['status'].lower() if injury_item['status'] else ''
                            if 'out' in status_lower or 'doubtful' in status_lower:
                                if injury_item['player_id']:
                                    home_out.append(injury_item['player_id'])
                                home_questionable.append(injury_item)
                            elif 'questionable' in status_lower or 'probable' in status_lower:
                                home_questionable.append(injury_item)
                        
                        all_matchup_injuries = matchup_injuries
                        questionable_probable = {'away': away_questionable, 'home': home_questionable}
                    
                    # Store processed data for this matchup
                    st.session_state.processed_matchups[matchup_key] = {
                        'away_out': away_out,
                        'home_out': home_out,
                        'all_matchup_injuries': all_matchup_injuries,
                        'questionable_probable': questionable_probable
                    }
                
                # Get the processed data for this matchup
                matchup_data = st.session_state.processed_matchups[matchup_key]
                fetched_away_out = matchup_data['away_out']
                fetched_home_out = matchup_data['home_out']
                all_matchup_injuries = matchup_data['all_matchup_injuries']
                questionable_probable = matchup_data['questionable_probable']
                
                # Show injury report status
                if injury_report_url:
                    st.info(f"📋 {injury_report_url}")
                elif injury_load_error:
                    st.warning(f"⚠️ Could not load injury report: {injury_load_error}")
                
                # Show all found injuries for this matchup
                all_injuries_away = all_matchup_injuries.get('away', [])
                all_injuries_home = all_matchup_injuries.get('home', [])
                
                if all_injuries_away or all_injuries_home:
                    st.success(f"✅ Found {len(all_injuries_away) + len(all_injuries_home)} injuries for this matchup")
                    
                    # Helper function to get status color
                    def get_status_color(status):
                        status_lower = status.lower() if status else ''
                        if 'out' in status_lower:
                            return '#dc3545'  # Red
                        elif 'doubtful' in status_lower:
                            return '#fd7e14'  # Orange
                        elif 'questionable' in status_lower:
                            return '#ffc107'  # Yellow
                        elif 'probable' in status_lower:
                            return '#28a745'  # Green
                        else:
                            return '#6c757d'  # Gray
                    
                    # Helper function to get status sort order (Probable first, Out last)
                    def get_status_order(status):
                        status_lower = status.lower() if status else ''
                        if 'probable' in status_lower:
                            return 0
                        elif 'questionable' in status_lower:
                            return 1
                        elif 'doubtful' in status_lower:
                            return 2
                        elif 'out' in status_lower:
                            return 3
                        else:
                            return 4
                    
                    # Two-column layout for injuries
                    col_away, col_home = st.columns(2)
                    
                    with col_away:
                        if all_injuries_away:
                            st.markdown(f"### {matchup_away_team_abbr}")
                            sorted_away = sorted(all_injuries_away, key=lambda x: get_status_order(x.get('status', '')))
                            for injury_item in sorted_away:
                                status = injury_item.get('status', 'Unknown')
                                status_color = get_status_color(status)
                                formatted_name = ir.format_player_name(injury_item['player_name'])
                                formatted_reason = ir.format_injury_reason(injury_item.get('reason', ''))
                                player_id = injury_item.get('player_id', '')
                                headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" if player_id else ""
                                st.markdown(f"""
                                    <div style="display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #eee;">
                                        <img src="{headshot_url}" style="width: 75px; height: 55px; object-fit: cover; border-radius: 4px; background-color: #f0f0f0;" onerror="this.style.display='none'">
                                        <div style="flex: 1;">
                                            <span style="font-weight: bold;">{formatted_name}</span>
                                            <span style="background-color: {status_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px; margin-left: 8px;">{status}</span>
                                            <br><span style="font-size: 13px; color: #666;">{formatted_reason}</span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"### {matchup_away_team_abbr}")
                            st.info("No injuries")
                    
                    with col_home:
                        if all_injuries_home:
                            st.markdown(f"### {matchup_home_team_abbr}")
                            sorted_home = sorted(all_injuries_home, key=lambda x: get_status_order(x.get('status', '')))
                            for injury_item in sorted_home:
                                status = injury_item.get('status', 'Unknown')
                                status_color = get_status_color(status)
                                formatted_name = ir.format_player_name(injury_item['player_name'])
                                formatted_reason = ir.format_injury_reason(injury_item.get('reason', ''))
                                player_id = injury_item.get('player_id', '')
                                headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png" if player_id else ""
                                st.markdown(f"""
                                    <div style="display: flex; align-items: center; gap: 12px; padding: 8px 0; border-bottom: 1px solid #eee;">
                                        <img src="{headshot_url}" style="width: 75px; height: 55px; object-fit: cover; border-radius: 4px; background-color: #f0f0f0;" onerror="this.style.display='none'">
                                        <div style="flex: 1;">
                                            <span style="font-weight: bold;">{formatted_name}</span>
                                            <span style="background-color: {status_color}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px; margin-left: 8px;">{status}</span>
                                            <br><span style="font-size: 13px; color: #666;">{formatted_reason}</span>
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"### {matchup_home_team_abbr}")
                            st.info("No injuries")
                else:
                    st.info("No injuries reported")
                
                # Show which players are being auto-selected as OUT
                if fetched_away_out or fetched_home_out:
                    st.caption(f"🔴 Only players marked OUT or Doubtful are auto-selected below")
            
            st.divider()
            
            # Get players from both teams for the injury selection
            player_team_abbr = matchup_away_team_abbr if is_home == False else matchup_home_team_abbr
            
            # Filter players by team
            away_team_players_df = players_df[players_df['TEAM_ID'].astype(int) == matchup_away_team_id].copy()
            home_team_players_df = players_df[players_df['TEAM_ID'].astype(int) == matchup_home_team_id].copy()
            
            # Add minutes for sorting
            away_team_players_df['AVG_MIN'] = away_team_players_df['PERSON_ID'].apply(
                lambda x: player_minutes_map.get(int(x), 0)
            )
            home_team_players_df['AVG_MIN'] = home_team_players_df['PERSON_ID'].apply(
                lambda x: player_minutes_map.get(int(x), 0)
            )
            
            # Sort by minutes and get top players (likely to matter most)
            away_team_players_df = away_team_players_df.sort_values('AVG_MIN', ascending=False).head(15)
            home_team_players_df = home_team_players_df.sort_values('AVG_MIN', ascending=False).head(15)
            
            # Get player IDs and create name maps
            away_player_ids = away_team_players_df['PERSON_ID'].astype(str).tolist()
            home_player_ids = home_team_players_df['PERSON_ID'].astype(str).tolist()
            
            def format_player_with_mins(pid):
                name = player_name_map.get(pid, f"Player {pid}")
                mins = player_minutes_map.get(int(pid), 0)
                return f"{name} ({mins:.1f} mpg)"
            
            st.markdown("**Select Players Out (adjust manually if needed):**")
            inj_col1, inj_col2 = st.columns(2)
            
            with inj_col1:
                st.markdown(f"**{matchup_away_team_abbr} Players Out:**")
                # Use fetched data as default if available
                default_away_out = [p for p in fetched_away_out if p in away_player_ids]
                away_players_out = st.multiselect(
                    "Away team injuries",
                    options=away_player_ids,
                    default=default_away_out,
                    format_func=format_player_with_mins,
                    key=f"away_injuries_tab2_{matchup_key}",
                    label_visibility="collapsed"
                )
            
            with inj_col2:
                st.markdown(f"**{matchup_home_team_abbr} Players Out:**")
                # Use fetched data as default if available
                default_home_out = [p for p in fetched_home_out if p in home_player_ids]
                home_players_out = st.multiselect(
                    "Home team injuries",
                    options=home_player_ids,
                    default=default_home_out,
                    format_func=format_player_with_mins,
                    key=f"home_injuries_tab2_{matchup_key}",
                    label_visibility="collapsed"
                )
            
            # Determine teammates_out and opponents_out for this player
            teammates_out = []
            opponents_out = []
            if player_team_id == matchup_away_team_id:
                teammates_out = away_players_out
                opponents_out = home_players_out
            elif player_team_id == matchup_home_team_id:
                teammates_out = home_players_out
                opponents_out = away_players_out
            
            # Remove the selected player from teammates_out if somehow selected
            teammates_out = [p for p in teammates_out if p != str(selected_player_id)]
            
            # Calculate injury adjustments
            injury_adjustments = inj.calculate_injury_adjustments(
                player_id=str(selected_player_id),
                player_team_id=int(player_team_id),
                opponent_team_id=opponent_team_id,
                teammates_out=teammates_out,
                opponents_out=opponents_out,
                player_minutes_map=player_minutes_map,
                players_df=players_df
            )
            
            # Show injury impact summary
            if injury_adjustments.get('factors'):
                st.warning(f"⚠️ **Injury Adjustments:** {' | '.join(injury_adjustments['factors'])}")
                
                # Add explanation expander
                with st.expander("ℹ️ How Injury Adjustments Work"):
                    st.markdown("""
                    **Teammates Out:**
                    - **Minutes Redistribution**: Based on player role and available minutes from injured teammates
                      - Stars (32+ MPG): Get 18% of available minutes (max +6 min)
                      - Starters (28+ MPG): Get 14% of available minutes (max +5 min)
                      - Rotation (22+ MPG): Get 10% of available minutes (max +5 min)
                      - Bench (15+ MPG): Get 8% of available minutes (max +6 min)
                      - Deep bench (<15 MPG): Get 5% of available minutes (max +8 min)
                    
                    - **Usage Boost**: Based on minutes of injured teammates
                      - Star out (34+ MPG): +8% usage
                      - High-usage starter (30+ MPG): +5% usage
                      - Starter (25+ MPG): +3% usage
                      - Rotation (18+ MPG): +1% usage
                      - Max total usage boost: 25%
                    
                    - **Stat Adjustments**:
                      - Scoring stats (PTS, FG3M, FTM): Get both minutes multiplier AND usage boost
                      - Rebounds: Get minutes multiplier + 30% of usage boost
                      - Assists: Get minutes multiplier but slight reduction (95% multiplier) due to fewer finishers
                      - Steals/Blocks: Get minutes multiplier only
                    
                    **Opponents Out:**
                    - Only applies if 30+ total minutes are out
                    - Scoring boost: +3% to PTS, +2% to FG3M (easier defensive matchup)
                    """)
            
            # Minutes scaling input
            season_minutes = None
            if player_data.get('averages_df') is not None and len(player_data['averages_df']) > 0:
                season_min_row = player_data['averages_df'][player_data['averages_df']['Period'] == 'Season']
                if len(season_min_row) > 0:
                    season_minutes = season_min_row['MIN'].iloc[0]
            
            col_min1, col_min2 = st.columns([0.3, 0.7])
            with col_min1:
                if season_minutes is not None and pd.notna(season_minutes):
                    projected_minutes = st.number_input(
                        "Projected Minutes",
                        min_value=0.0,
                        max_value=40.0,
                        value=float(season_minutes),
                        step=0.5,
                        key="projected_minutes_tab2",
                        help=f"Season Avg: {season_minutes:.1f} MPG. Adjust for minutes restrictions or rotation changes."
                    )
                else:
                    projected_minutes = st.number_input(
                        "Projected Minutes",
                        min_value=0.0,
                        max_value=40.0,
                        value=32.0,
                        step=0.5,
                        key="projected_minutes_tab2",
                        help="Enter projected minutes for this game"
                    )
            
            # Cache predictions (include projected_minutes in cache key)
            @st.cache_data(ttl=1800)  # Cache for 30 minutes
            def get_cached_predictions(player_id, pl_team_id, opp_team_id, opp_abbr, game_dt, home, proj_min, season_min, use_sim):
                try:
                    # Only pass projected_minutes if it differs from season average
                    proj_min_to_use = None
                    if season_min is not None and pd.notna(season_min):
                        if abs(proj_min - float(season_min)) > 0.1:
                            proj_min_to_use = proj_min
                    else:
                        # No season average available, use projected minutes
                        proj_min_to_use = proj_min
                    
                    return pm.generate_prediction(
                        player_id=player_id,
                        player_team_id=pl_team_id,
                        opponent_team_id=opp_team_id,
                        opponent_abbr=opp_abbr,
                        game_date=game_dt,
                        is_home=home,
                        use_similar_players=use_sim,
                        projected_minutes=proj_min_to_use
                    )
                except Exception as e:
                    st.error(f"Error generating predictions: {e}")
                    return None
            
            # Generate predictions
            predictions = get_cached_predictions(
                selected_player_id,
                player_team_id,
                opponent_team_id,
                opponent_abbr,
                game_date_str,
                is_home,
                projected_minutes,
                season_minutes,
                True  # use_similar_players
            )
            
            if predictions is None:
                st.error("Could not generate predictions")
            elif predictions:
                # Check if minutes were adjusted
                has_minutes_adj = False
                if season_minutes is not None and pd.notna(season_minutes):
                    has_minutes_adj = abs(projected_minutes - float(season_minutes)) > 0.1
                
                # Apply injury adjustments if any
                adjusted_predictions = {}
                for stat, pred in predictions.items():
                    if injury_adjustments and stat in injury_adjustments:
                        adjusted_value = inj.apply_injury_adjustments(
                            pred.value, stat, injury_adjustments
                        )
                        adjusted_predictions[stat] = adjusted_value
                    else:
                        adjusted_predictions[stat] = pred.value
                
                # Always recalculate PRA, RA, and FPTS from adjusted values
                adjusted_pts = adjusted_predictions.get('PTS', predictions['PTS'].value)
                adjusted_reb = adjusted_predictions.get('REB', predictions['REB'].value)
                adjusted_ast = adjusted_predictions.get('AST', predictions['AST'].value)
                adjusted_stl = adjusted_predictions.get('STL', predictions['STL'].value)
                adjusted_blk = adjusted_predictions.get('BLK', predictions['BLK'].value)
                adjusted_tov = adjusted_predictions.get('TOV', predictions['TOV'].value)
                
                # Recalculate PRA (Points + Rebounds + Assists)
                adjusted_predictions['PRA'] = round(adjusted_pts + adjusted_reb + adjusted_ast, 1)
                
                # Recalculate RA (Rebounds + Assists)
                adjusted_predictions['RA'] = round(adjusted_reb + adjusted_ast, 1)
                
                # Recalculate FPTS using Underdog formula: PTS*1 + REB*1.2 + AST*1.5 + STL*3 + BLK*3 - TOV*1
                adjusted_predictions['FPTS'] = round(
                    adjusted_pts * 1.0 + 
                    adjusted_reb * 1.2 + 
                    adjusted_ast * 1.5 + 
                    adjusted_stl * 3.0 + 
                    adjusted_blk * 3.0 - 
                    adjusted_tov * 1.0, 
                    1
                )
                
                # Display main predictions in columns
                has_injury_adj = injury_adjustments and injury_adjustments.get('factors')
                header_text = "### Predicted Statline"
                if has_injury_adj:
                    header_text += " (Injury Adjusted)"
                if has_minutes_adj:
                    header_text += f" ({projected_minutes:.1f} MPG)"
                st.markdown(header_text)
                
                pred_cols = st.columns(10)
                stat_order = ['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS']
                stat_labels = {'PTS': 'Points', 'REB': 'Rebounds', 'AST': 'Assists', 
                              'PRA': 'PRA', 'RA': 'R+A', 'STL': 'Steals', 'BLK': 'Blocks', 
                              'FG3M': '3PM', 'FTM': 'FTM', 'FPTS': 'Fantasy'}
                
                for i, stat in enumerate(stat_order):
                    if stat in predictions:
                        pred = predictions[stat]
                        display_value = adjusted_predictions.get(stat, pred.value)
                        
                        with pred_cols[i]:
                            # Color code by confidence
                            if pred.confidence == 'high':
                                conf_color = '🟢'
                            elif pred.confidence == 'medium':
                                conf_color = '🟡'
                            else:
                                conf_color = '🔴'
                            
                            # Show delta from base prediction if injury or minutes adjusted
                            delta_str = None
                            if has_injury_adj and display_value != pred.value:
                                delta_val = round(display_value - pred.value, 1)
                                delta_str = f"{'+' if delta_val >= 0 else ''}{delta_val} (inj)"
                            elif has_minutes_adj:
                                # Show minutes adjustment indicator
                                delta_str = f"{conf_color} {pred.confidence}"
                            
                            st.metric(
                                label=stat_labels.get(stat, stat),
                                value=display_value,
                                delta=delta_str if delta_str else f"{conf_color} {pred.confidence}"
                            )
                
                # Prediction breakdown
                with st.expander("📈 Prediction Breakdown"):
                    # Show breakdown for each stat
                    breakdown_cols = st.columns(3)
                    
                    for i, stat in enumerate(['PTS', 'REB', 'AST']):
                        if stat in predictions:
                            pred = predictions[stat]
                            with breakdown_cols[i]:
                                st.markdown(f"**{stat}**")
                                breakdown = pred.breakdown
                                if breakdown:
                                    # Helper function to format breakdown values
                                    def format_breakdown_val(val):
                                        if val is None or val == 'N/A':
                                            return 'N/A'
                                        try:
                                            return f"{float(val):.1f}"
                                        except (ValueError, TypeError):
                                            return str(val)
                                    
                                    st.write(f"Season Avg: {format_breakdown_val(breakdown.get('season_avg', 'N/A'))}")
                                    st.write(f"L5 Avg: {format_breakdown_val(breakdown.get('L5_avg', 'N/A'))}")
                                    st.write(f"vs Opponent: {format_breakdown_val(breakdown.get('vs_opponent', 'N/A'))}")
                                
                                # Show factors
                                factors = pred.factors
                                if factors:
                                    st.markdown("**Factors:**")
                                    for factor_name, factor_value in factors.items():
                                        if factor_name not in ['regression_tier', 'confidence']:
                                            st.write(f"- {factor_name}: {factor_value}")
                
                # Factors affecting prediction
                with st.expander("🎯 Factors Considered"):
                    # Show factors for PTS, REB, AST
                    for stat in ['PTS', 'REB', 'AST']:
                        pred = predictions.get(stat)
                        if pred and pred.factors:
                            st.markdown(f"**{stat_labels.get(stat, stat)}**")
                            for factor, description in pred.factors.items():
                                # Highlight similar players factor
                                if 'similar' in factor.lower():
                                    st.markdown(f"• **{factor.replace('_', ' ').title()}**: {description} ⭐")
                                else:
                                    st.write(f"• **{factor.replace('_', ' ').title()}**: {description}")
                            st.markdown("---")
                
                # Similar Players Impact Section
                if opponent_team_id and opponent_abbr:
                    # Get similar players vs opponent data
                    all_player_game_logs = pf_features.get_bulk_player_game_logs()
                    if all_player_game_logs is not None and len(all_player_game_logs) > 0:
                        try:
                            similar_players_impact = ps.get_similar_players_vs_opponent(
                                player_id=int(selected_player_id),
                                opponent_team_id=opponent_team_id,
                                game_logs_df=all_player_game_logs,
                                opponent_abbr=opponent_abbr,
                                n_similar=10,
                                min_games_vs_opponent=1
                            )
                            
                            if similar_players_impact.get('sample_size', 0) > 0:
                                with st.expander("⭐ Similar Players Impact", expanded=True):
                                    st.markdown("**How similar players performed against this opponent:**")
                                    
                                    # Display adjustment factors
                                    impact_cols = st.columns(3)
                                    pts_factor = similar_players_impact.get('pts_adjustment_factor', 1.0)
                                    reb_factor = similar_players_impact.get('reb_adjustment_factor', 1.0)
                                    ast_factor = similar_players_impact.get('ast_adjustment_factor', 1.0)
                                    confidence = similar_players_impact.get('confidence', 'low')
                                    sample_size = similar_players_impact.get('sample_size', 0)
                                    total_games = similar_players_impact.get('total_games_analyzed', 0)
                                    
                                    with impact_cols[0]:
                                        pts_change = round((pts_factor - 1.0) * 100, 1)
                                        pts_color = "🟢" if pts_change > 0 else "🔴" if pts_change < 0 else "⚪"
                                        st.metric(
                                            label="Points Adjustment",
                                            value=f"{pts_change:+.1f}%",
                                            delta=f"{pts_color} {pts_factor:.3f}x"
                                        )
                                    
                                    with impact_cols[1]:
                                        reb_change = round((reb_factor - 1.0) * 100, 1)
                                        reb_color = "🟢" if reb_change > 0 else "🔴" if reb_change < 0 else "⚪"
                                        st.metric(
                                            label="Rebounds Adjustment",
                                            value=f"{reb_change:+.1f}%",
                                            delta=f"{reb_color} {reb_factor:.3f}x"
                                        )
                                    
                                    with impact_cols[2]:
                                        ast_change = round((ast_factor - 1.0) * 100, 1)
                                        ast_color = "🟢" if ast_change > 0 else "🔴" if ast_change < 0 else "⚪"
                                        st.metric(
                                            label="Assists Adjustment",
                                            value=f"{ast_change:+.1f}%",
                                            delta=f"{ast_color} {ast_factor:.3f}x"
                                        )
                                    
                                    # Show confidence and sample info
                                    conf_color = "🟢" if confidence == 'high' else "🟡" if confidence == 'medium' else "🔴"
                                    st.caption(f"{conf_color} **Confidence**: {confidence.capitalize()} | **Sample**: {sample_size} similar players, {total_games} total games vs {opponent_abbr}")
                                    
                                    # Show which similar players were used
                                    sim_player_data = similar_players_impact.get('similar_player_data', [])
                                    if sim_player_data:
                                        st.markdown("**Similar Players Analyzed:**")
                                        sim_display_cols = st.columns(min(5, len(sim_player_data)))
                                        for i, sim_data in enumerate(sim_player_data[:5]):
                                            with sim_display_cols[i]:
                                                st.caption(f"**{sim_data.get('player_name', 'Unknown')}** ({sim_data.get('similarity', 0)}%)\n"
                                                          f"{sim_data.get('games_vs_opp', 0)} games\n"
                                                          f"{sim_data.get('pts_diff', 0):+.1f}% vs season")
                        except Exception as e:
                            # Silently fail - similar players data not critical
                            pass
                
                # Matchup-specific insights
                with st.expander("🏀 Matchup Analysis", expanded=True):
                    try:
                        # Get matchup features
                        matchup_data = ms.get_matchup_prediction_features(
                            selected_player_id,
                            opponent_team_id
                        )
                        
                        player_breakdown = matchup_data['player_scoring_breakdown']
                        opp_vuln = matchup_data['opponent_vulnerabilities']
                        league_avgs = matchup_data['league_misc_averages']
                        adjustments = matchup_data['matchup_adjustments']
                        
                        # Display matchup insights
                        insight_text = ms.format_matchup_insight(player_breakdown, opp_vuln, adjustments)
                        st.markdown(insight_text)
                        
                        st.markdown("---")
                        
                        # Player scoring breakdown table
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Player Scoring Breakdown (Per Game)**")
                            breakdown_data = pd.DataFrame([
                                {"Category": "Points in Paint", "Player": player_breakdown['pts_paint'], "Player Rank": player_breakdown['pts_paint_rank']},
                                {"Category": "Fast Break Pts", "Player": player_breakdown['pts_fb'], "Player Rank": player_breakdown['pts_fb_rank']},
                                {"Category": "2nd Chance Pts", "Player": player_breakdown['pts_2nd_chance'], "Player Rank": player_breakdown['pts_2nd_chance_rank']},
                                {"Category": "Pts Off TOV", "Player": player_breakdown['pts_off_tov'], "Player Rank": player_breakdown['pts_off_tov_rank']},
                            ])
                            st.dataframe(breakdown_data, hide_index=True, width='stretch')
                        
                        with col2:
                            st.markdown(f"**{opponent_abbr} Defense (What They Allow)**")
                            defense_data = pd.DataFrame([
                                {"Category": "Points in Paint", "Allowed": opp_vuln['opp_pts_paint_allowed'], "Rank": opp_vuln['opp_pts_paint_rank'], "Lg Avg": league_avgs['pts_paint']},
                                {"Category": "Fast Break Pts", "Allowed": opp_vuln['opp_pts_fb_allowed'], "Rank": opp_vuln['opp_pts_fb_rank'], "Lg Avg": league_avgs['pts_fb']},
                                {"Category": "2nd Chance Pts", "Allowed": opp_vuln['opp_pts_2nd_chance_allowed'], "Rank": opp_vuln['opp_pts_2nd_chance_rank'], "Lg Avg": league_avgs['pts_2nd_chance']},
                                {"Category": "Pts Off TOV", "Allowed": opp_vuln['opp_pts_off_tov_allowed'], "Rank": opp_vuln['opp_pts_off_tov_rank'], "Lg Avg": league_avgs['pts_off_tov']},
                            ])
                            st.dataframe(defense_data, hide_index=True, width='stretch')
                        
                        # Matchup adjustments
                        st.markdown("**Matchup-Adjusted Projections**")
                        adj_data = pd.DataFrame([
                            {"Category": "Paint Scoring", "Base": player_breakdown['pts_paint'], "Adjusted": adjustments['pts_paint_adjusted'], "Impact": f"+{round(adjustments['pts_paint_adjusted'] - player_breakdown['pts_paint'], 1)}" if adjustments['pts_paint_adjusted'] > player_breakdown['pts_paint'] else f"{round(adjustments['pts_paint_adjusted'] - player_breakdown['pts_paint'], 1)}"},
                            {"Category": "Fast Break", "Base": player_breakdown['pts_fb'], "Adjusted": adjustments['pts_fb_adjusted'], "Impact": f"+{round(adjustments['pts_fb_adjusted'] - player_breakdown['pts_fb'], 1)}" if adjustments['pts_fb_adjusted'] > player_breakdown['pts_fb'] else f"{round(adjustments['pts_fb_adjusted'] - player_breakdown['pts_fb'], 1)}"},
                            {"Category": "2nd Chance", "Base": player_breakdown['pts_2nd_chance'], "Adjusted": adjustments['pts_2nd_chance_adjusted'], "Impact": f"+{round(adjustments['pts_2nd_chance_adjusted'] - player_breakdown['pts_2nd_chance'], 1)}" if adjustments['pts_2nd_chance_adjusted'] > player_breakdown['pts_2nd_chance'] else f"{round(adjustments['pts_2nd_chance_adjusted'] - player_breakdown['pts_2nd_chance'], 1)}"},
                        ])
                        st.dataframe(adj_data, hide_index=True, width='stretch')
                        
                        overall_factor = adjustments.get('overall_pts_factor', 1.0)
                        if overall_factor != 1.0:
                            factor_pct = round((overall_factor - 1) * 100, 1)
                            if factor_pct > 0:
                                st.success(f"📈 **Overall Matchup Factor: +{factor_pct}%** scoring opportunity in this matchup")
                            else:
                                st.warning(f"📉 **Overall Matchup Factor: {factor_pct}%** tougher matchup expected")
                        else:
                            st.info("📊 **Neutral Matchup**: No significant scoring adjustments")
                            
                    except Exception as e:
                        st.warning(f"Could not load matchup analysis: {e}")
                
                # Comparison table
                st.markdown("### Season Averages vs Prediction")
                
                comparison_data = []
                rolling_avgs = player_data.get('averages_df')
                game_logs = player_data.get('recent_games_df')  # Get game logs for computed stats
                
                if rolling_avgs is not None and len(rolling_avgs) > 0:
                    season_row = rolling_avgs.iloc[-1]  # Season averages
                    
                    # Map prediction stat names to averages_df column names
                    stat_to_col = {'FG3M': '3PM'}  # averages_df uses '3PM', predictions use 'FG3M'
                    
                    # Calculate computed season averages from game logs if available
                    computed_season_avgs = {}
                    if game_logs is not None and len(game_logs) > 0:
                        # R+A (Rebounds + Assists)
                        if 'REB' in game_logs.columns and 'AST' in game_logs.columns:
                            ra_avg = game_logs['REB'].mean() + game_logs['AST'].mean()
                            computed_season_avgs['RA'] = ra_avg
                        
                        # FPTS (Fantasy Points) using Underdog formula: PTS×1 + REB×1.2 + AST×1.5 + STL×3 + BLK×3 - TOV×1
                        fpts_cols = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV']
                        if all(col in game_logs.columns for col in fpts_cols):
                            game_logs_copy = game_logs.copy()
                            game_logs_copy['FPTS'] = (
                                game_logs_copy['PTS'] * 1.0 +
                                game_logs_copy['REB'] * 1.2 +
                                game_logs_copy['AST'] * 1.5 +
                                game_logs_copy['STL'] * 3.0 +
                                game_logs_copy['BLK'] * 3.0 -
                                game_logs_copy['TOV'] * 1.0
                            )
                            computed_season_avgs['FPTS'] = game_logs_copy['FPTS'].mean()
                    
                    for stat in ['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'FPTS']:
                        if stat in predictions:
                            pred = predictions[stat]
                            col_name = stat_to_col.get(stat, stat)  # Use mapped name if exists
                            
                            # First check computed averages for RA and FPTS
                            if stat in computed_season_avgs:
                                season_val_float = computed_season_avgs[stat]
                            else:
                                season_val = season_row.get(col_name)
                                try:
                                    season_val_float = float(str(season_val).replace(',', '')) if season_val is not None else None
                                except:
                                    season_val_float = None
                            
                            try:
                                if season_val_float is not None:
                                    diff = round(pred.value - season_val_float, 1)
                                    diff_str = f"+{diff}" if diff >= 0 else str(diff)
                                    season_val_display = round(season_val_float, 1)
                                else:
                                    diff_str = "-"
                                    season_val_display = None
                            except:
                                diff_str = "-"
                                season_val_display = None
                            
                            comparison_data.append({
                                'Stat': stat_labels.get(stat, stat),
                                'Season Avg': season_val_display,
                                'Prediction': round(pred.value, 1),
                                'Diff': diff_str,
                                'Confidence': pred.confidence.capitalize()
                            })
                    
                    if comparison_data:
                        comparison_df = pd.DataFrame(comparison_data)
                        st.dataframe(comparison_df, width='stretch', hide_index=True)
                
                # Vegas Lines Comparison Section
                st.markdown("### 📊 Vegas Lines Comparison")
                
                # Get existing lines for this player/game
                existing_lines = vl.get_player_lines(selected_player_id, game_date_str)
                
                # === UNDERDOG API INTEGRATION ===
                with st.expander("🎰 **Fetch Underdog Lines** (The Odds API)", expanded=True):
                    st.caption("Fetch live player props from Underdog Fantasy via The Odds API")
                    
                    # Initialize session state for API data (GAME-LEVEL CACHE)
                    if 'odds_game_cache' not in st.session_state:
                        st.session_state.odds_game_cache = {}  # game_key -> all_props dict
                    if 'odds_api_credits' not in st.session_state:
                        st.session_state.odds_api_credits = None
                    
                    # Create cache key for this GAME (not player-specific)
                    game_cache_key = f"{game_date_str}_{matchup_away_team_abbr}_{matchup_home_team_abbr}"
                    
                    # Check if we have cached data for this GAME
                    cached_game_props = st.session_state.odds_game_cache.get(game_cache_key)
                    
                    # Get player-specific props from cache if available
                    if cached_game_props is not None:
                        cached_props = vl.get_player_props_from_cached(cached_game_props, player_data['player_info_name'])
                        players_with_props = len(cached_game_props)
                    else:
                        cached_props = None
                        players_with_props = 0
                    
                    # Dry-run preview section
                    col_preview, col_fetch = st.columns([2, 1])
                    
                    with col_preview:
                        if st.button("🔍 Preview Request (Free)", key="preview_odds_request"):
                            with st.spinner("Checking for available events..."):
                                preview = vl.preview_odds_request(
                                    matchup_home_team_abbr,
                                    matchup_away_team_abbr,
                                    game_date_str
                                )
                                
                                if preview.get('error'):
                                    st.error(f"❌ {preview['error']}")
                                    if preview.get('events_on_date'):
                                        st.info(f"Events found on {game_date_str}: {', '.join(preview['events_on_date'])}")
                                else:
                                    st.success(f"✅ Event found: {preview['event_details']['away_team']} @ {preview['event_details']['home_team']}")
                                    
                                    with st.container():
                                        st.markdown("**Request Details (Dry Run)**")
                                        st.code(f"""
Event ID: {preview['event_id']}
Region: {preview['request_info']['region']}
Bookmaker: {preview['request_info']['bookmaker']}
Markets: {', '.join(preview['request_info']['markets_requested'])}
Estimated Cost: {preview['estimated_cost']}
""", language=None)
                    
                    with col_fetch:
                        fetch_disabled = cached_game_props is not None
                        if fetch_disabled:
                            fetch_label = f"✅ Game Cached ({players_with_props} players)"
                        else:
                            fetch_label = "📥 Fetch Lines (1 Credit)"
                        
                        if st.button(fetch_label, key="fetch_odds", disabled=fetch_disabled):
                            with st.spinner("Fetching ALL player props for this game..."):
                                # Fetch ALL props for the game (costs 1 credit)
                                all_props, api_response = vl.fetch_all_props_for_game(
                                    matchup_home_team_abbr,
                                    matchup_away_team_abbr,
                                    game_date_str
                                )
                                
                                if api_response.success:
                                    # Cache at GAME level
                                    st.session_state.odds_game_cache[game_cache_key] = all_props
                                    st.session_state.odds_api_credits = api_response.credits_remaining
                                    
                                    if all_props:
                                        st.success(f"✅ Cached props for {len(all_props)} players! Switch players freely - no additional credits needed.")
                                    else:
                                        st.warning("⚠️ No props found for this game on Underdog")
                                    
                                    st.rerun()
                                else:
                                    # Show detailed error message
                                    error_msg = api_response.error or "Unknown API error"
                                    st.error(f"❌ API Error: {error_msg}")
                                    
                                    # Provide helpful guidance for common errors
                                    if "Invalid API key" in error_msg:
                                        st.info("💡 **Troubleshooting:**\n"
                                               "- Verify your API key in The Odds API dashboard\n"
                                               "- If you just upgraded, try regenerating your API key\n"
                                               "- Wait a few minutes for activation after upgrading\n"
                                               "- Ensure there are no extra spaces in the API key")
                                    
                                    if api_response.credits_remaining is not None:
                                        st.session_state.odds_api_credits = api_response.credits_remaining
                    
                    # Clear cache button
                    if cached_game_props is not None:
                        if st.button("🔄 Refresh Game Lines", key="refresh_odds"):
                            del st.session_state.odds_game_cache[game_cache_key]
                            st.rerun()
                    
                    # Show credit info and cache status
                    if st.session_state.odds_api_credits is not None:
                        # Display credits without hardcoded limit (limit varies by subscription tier)
                        st.info(f"💳 API Credits Remaining: **{st.session_state.odds_api_credits}**")
                    
                    if cached_game_props is not None and cached_props:
                        st.success(f"📊 Found {len(cached_props)} props for **{player_data['player_info_name']}** from cached game data")
                    elif cached_game_props is not None and not cached_props:
                        st.warning(f"⚠️ No props available for {player_data['player_info_name']} on Underdog (game data cached)")
                    
                    # Display fetched props
                    if cached_props:
                        st.markdown("**Underdog Lines:**")
                        
                        # Build comparison table with fetched props - USE INJURY-ADJUSTED PREDICTIONS
                        api_comparison_data = []
                        for stat in ['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS']:
                            if stat in predictions and stat in cached_props:
                                pred = predictions[stat]
                                prop = cached_props[stat]
                                # Use injury-adjusted value if available
                                adjusted_value = adjusted_predictions.get(stat, pred.value)
                                comparison = vl.compare_prediction_to_line(adjusted_value, prop.line)
                                
                                api_comparison_data.append({
                                    'Stat': stat_labels.get(stat, stat),
                                    'Prediction': round(adjusted_value, 1),  # Show adjusted prediction
                                    'Underdog Line': round(prop.line, 1),
                                    'Edge': round(comparison['diff'], 1),
                                    'Edge %': round(abs(comparison['diff_pct']) / 100, 3),
                                    'Lean': comparison['lean']
                                })
                                
                                # Also save to existing lines for persistence
                                vl.set_player_line(
                                    selected_player_id,
                                    game_date_str,
                                    stat,
                                    prop.line,
                                    prop.over_odds,
                                    prop.under_odds,
                                    source='underdog'
                                )
                        
                        if api_comparison_data:
                            # Sort by absolute Edge descending
                            api_comparison_data.sort(key=lambda x: abs(x['Edge']), reverse=True)
                            api_df = pd.DataFrame(api_comparison_data)
                            
                            # Style the lean column
                            def style_api_lean(val):
                                if 'Strong Over' in val:
                                    return 'background-color: rgba(46, 125, 50, 0.4); font-weight: bold'
                                elif 'Lean Over' in val:
                                    return 'background-color: rgba(76, 175, 80, 0.3)'
                                elif 'Strong Under' in val:
                                    return 'background-color: rgba(183, 28, 28, 0.4); font-weight: bold'
                                elif 'Lean Under' in val:
                                    return 'background-color: rgba(244, 67, 54, 0.3)'
                                else:
                                    return 'background-color: rgba(158, 158, 158, 0.2)'
                            
                            def style_edge(val):
                                try:
                                    num = float(val) if not isinstance(val, (int, float)) else val
                                    if num >= 1.5:
                                        return 'color: #2E7D32; font-weight: bold'
                                    elif num >= 0.5:
                                        return 'color: #4CAF50'
                                    elif num <= -1.5:
                                        return 'color: #B71C1C; font-weight: bold'
                                    elif num <= -0.5:
                                        return 'color: #F44336'
                                    return ''
                                except:
                                    return ''
                            
                            styled_api_df = api_df.style.applymap(style_api_lean, subset=['Lean']).applymap(style_edge, subset=['Edge'])
                            st.dataframe(styled_api_df, width='stretch', hide_index=True)
                            
                            # Summary callout for best plays
                            strong_plays = [row for row in api_comparison_data if 'Strong' in row['Lean']]
                            if strong_plays:
                                st.markdown("**🎯 Best Plays:**")
                                for play in strong_plays:
                                    direction = "OVER" if "Over" in play['Lean'] else "UNDER"
                                    st.markdown(f"- **{play['Stat']}** {direction} {play['Underdog Line']} (Pred: {play['Prediction']}, Edge: {play['Edge']})")
                        else:
                            st.info("No matching props found between predictions and Underdog lines.")
                    elif cached_props is not None and len(cached_props) == 0:
                        st.warning(f"No Underdog props available for {player_data['player_info_name']} in this game.")
                
                st.markdown("---")
                
                # Model Backtest Section
                # Initialize backtest session state
                if 'backtest_results' not in st.session_state:
                    st.session_state.backtest_results = None
                if 'backtest_player_id' not in st.session_state:
                    st.session_state.backtest_player_id = None
                
                with st.expander("📊 Model Backtest - Test Prediction Accuracy", expanded=True):
                    st.markdown("Test how well the prediction model performs against actual game results.")
                    
                    # Use form to prevent reruns on slider change
                    with st.form(key="backtest_form"):
                        col_bt1, col_bt2 = st.columns(2)
                        with col_bt1:
                            n_games_backtest = st.slider("Games to test", min_value=3, max_value=20, value=10)
                        with col_bt2:
                            skip_recent = st.slider("Skip most recent games", min_value=0, max_value=5, value=0, 
                                                   help="Skip recent games for true out-of-sample testing")
                        
                        run_backtest = st.form_submit_button("🧪 Run Backtest")
                    
                    # Clear results if player changed
                    if st.session_state.backtest_player_id != selected_player_id:
                        st.session_state.backtest_results = None
                        st.session_state.backtest_player_id = selected_player_id
                    
                    if run_backtest:
                        with st.spinner(f"Testing predictions on last {n_games_backtest} games..."):
                            try:
                                # Run backtest for current player
                                results = bt.run_player_backtest(
                                    player_id=str(selected_player_id),
                                    player_name=player_data['player_info_name'],
                                    player_team_id=int(player_data['team_id']),
                                    n_games=n_games_backtest,
                                    skip_recent=skip_recent
                                )
                                
                                if results:
                                    # Store in session state
                                    st.session_state.backtest_results = {
                                        'results': results,
                                        'summaries': bt.calculate_backtest_summary(results),
                                        'confidence_metrics': bt.calculate_confidence_accuracy(results),
                                        'player_name': player_data['player_info_name']
                                    }
                                else:
                                    st.session_state.backtest_results = None
                                    st.warning("No backtest results generated. Player may not have enough games.")
                            except Exception as e:
                                st.error(f"Backtest error: {str(e)}")
                                st.session_state.backtest_results = None
                    
                    # Display results from session state (persists across reruns)
                    if st.session_state.backtest_results is not None:
                        results = st.session_state.backtest_results['results']
                        summaries = st.session_state.backtest_results['summaries']
                        confidence_metrics = st.session_state.backtest_results['confidence_metrics']
                        player_name_clean = st.session_state.backtest_results['player_name'].replace(' ', '_').replace("'", "")
                        
                        # Display summary
                        st.markdown("### 📈 Accuracy Summary")
                        summary_df = bt.format_summary_for_display(summaries)
                        if len(summary_df) > 0:
                            st.dataframe(summary_df, width='stretch', hide_index=True)
                            st.download_button(
                                label="📥 Download Summary",
                                data=summary_df.to_csv(index=False),
                                file_name=f"{player_name_clean}_Accuracy_Summary.csv",
                                mime="text/csv",
                                key="download_summary"
                            )
                        
                        # Confidence breakdown
                        if confidence_metrics:
                            st.markdown("### 🎯 Accuracy by Confidence Level")
                            conf_rows = []
                            for conf, metrics in confidence_metrics.items():
                                conf_rows.append({
                                    'Confidence': conf.capitalize(),
                                    'Predictions': metrics['count'],
                                    'MAE': metrics['mae'],
                                    'Within 10%': f"{metrics['within_10_pct']}%"
                                })
                            conf_df = pd.DataFrame(conf_rows)
                            st.dataframe(conf_df, width='stretch', hide_index=True)
                            st.download_button(
                                label="📥 Download Confidence",
                                data=conf_df.to_csv(index=False),
                                file_name=f"{player_name_clean}_Accuracy_By_Confidence.csv",
                                mime="text/csv",
                                key="download_confidence"
                            )
                        
                        # Player Type breakdown (for PTS)
                        player_type_metrics = bt.calculate_player_type_accuracy(results, stat='PTS')
                        if player_type_metrics:
                            # Show regression tier used
                            regression_tier = bt.get_regression_tier_from_results(results)
                            tier_emoji = "👑" if regression_tier == "Ultra-elite" else "⭐" if "Elite" in regression_tier else "📊"
                            st.markdown(f"### 👤 Accuracy by Player Type (Points) — {tier_emoji} **Regression Tier: {regression_tier}**")
                            st.caption("Ultra-elite: ≥27 PPG | Star: >18 PPG or ≥32 MPG | Starter: 12-18 PPG & ≥25 MPG | Role Player: <12 PPG or <25 MPG")
                            player_type_df = bt.format_player_type_summary(player_type_metrics)
                            if len(player_type_df) > 0:
                                st.dataframe(player_type_df, width='stretch', hide_index=True)
                                st.download_button(
                                    label="📥 Download Player Type",
                                    data=player_type_df.to_csv(index=False),
                                    file_name=f"{player_name_clean}_Accuracy_By_Player_Type.csv",
                                    mime="text/csv",
                                    key="download_player_type"
                                )
                        
                        # Show individual results
                        st.markdown("### 📋 Individual Predictions vs Actuals")
                        results_df = pd.DataFrame([{
                            'Date': r.game_date,
                            'vs': r.opponent_abbr,
                            'Stat': r.stat,
                            'Pred': r.predicted,
                            'Actual': r.actual,
                            'Error': f"{'+' if r.error > 0 else ''}{r.error}",
                            'Conf': r.confidence.capitalize(),
                            'Type': r.player_type
                        } for r in results])
                        
                        # Filter by stat
                        stat_filter = st.selectbox("Filter by stat", 
                                                   options=['All'] + list(results_df['Stat'].unique()),
                                                   key="backtest_stat_filter")
                        if stat_filter != 'All':
                            filtered_df = results_df[results_df['Stat'] == stat_filter]
                        else:
                            filtered_df = results_df
                        
                        st.dataframe(filtered_df, width='stretch', hide_index=True, height=300)
                        st.download_button(
                            label="📥 Download Predictions",
                            data=results_df.to_csv(index=False),
                            file_name=f"{player_name_clean}_Individual_Predictions.csv",
                            mime="text/csv",
                            key="download_predictions"
                        )
                        
                        # Interpretation
                        if summaries:
                            pts_summary = summaries.get('PTS')
                            if pts_summary:
                                st.markdown("---")
                                st.markdown("**📝 Interpretation:**")
                                bias_text = "over-predicting" if pts_summary.bias > 0 else "under-predicting"
                                st.markdown(f"""
                                - **Points MAE**: {pts_summary.mae} (on average, predictions are off by {pts_summary.mae} points)
                                - **Bias**: {'+' if pts_summary.bias > 0 else ''}{pts_summary.bias} (model is {bias_text})
                                - **Accuracy**: {pts_summary.within_10_pct}% of predictions within 10% of actual
                                """)
            else:
                st.info("ℹ️ Select a matchup above to generate predictions for this player.")
                st.markdown("""
                **How predictions work:**
                1. We analyze the player's recent performance (L3, L5, L10, Season)
                2. We adjust for opponent defensive strength and pace
                3. We factor in home/away splits and rest days
                4. We consider historical performance against this opponent
                
                Select a date and matchup above to see predictions!
                """)
        else:
            st.info("ℹ️ Select a matchup above to generate predictions for this player.")
            st.markdown("""
            **How predictions work:**
            1. We analyze the player's recent performance (L3, L5, L10, Season)
            2. We adjust for opponent defensive strength and pace
            3. We factor in home/away splits and rest days
            4. We consider historical performance against this opponent
            
            Select a date and matchup above to see predictions!
            """)

with tab3:
    # YoY Data tab
    st.subheader("Historical Season Stats")
    
    # Get YoY data for all seasons
    @st.cache_data
    def get_cached_yoy_data(player_id, players_df):
        """Cache YoY player data to avoid repeated API calls"""
        return pf.get_player_yoy_data(player_id, players_df)
    
    yoy_data = get_cached_yoy_data(selected_player_id, players_df)
    
    if yoy_data and yoy_data.get('averages_df') is not None and len(yoy_data['averages_df']) > 0:
        show_yoy_comparison = st.toggle("Show +/- vs Current Season", value=False, key="show_yoy_comparison")
        
        # Create heatmap styling for YoY data
        yoy_averages_df = yoy_data['averages_df'].copy()
        
        # Ensure all numeric columns are formatted to 1 decimal place
        numeric_cols_to_format = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
        for col in numeric_cols_to_format:
            if col in yoy_averages_df.columns:
                yoy_averages_df[col] = yoy_averages_df[col].apply(lambda x: f"{float(x):.1f}" if pd.notna(x) and str(x) != '' else x)
        
        # Heatmap comparing each season to current season
        def style_yoy_heatmap(row):
            styles = [''] * len(row)
            
            if not show_yoy_comparison or player_data.get('averages_df') is None:
                return styles
            
            current_season_avg = player_data['averages_df'].iloc[-1]  # Last row is current season
            numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
            pct_cols = ['2P%', '3P%', 'FT%']
            
            for i, col in enumerate(yoy_averages_df.columns):
                if col == 'Period' or '+/-' in col:
                    continue
                
                if col in numeric_cols:
                    try:
                        current_val_str = str(row[col]).replace(',', '')
                        current_season_val_str = str(current_season_avg[col]).replace(',', '')
                        current_val = float(current_val_str)
                        current_season_val = float(current_season_val_str)
                        
                        if current_val > current_season_val:
                            diff_pct = ((current_val - current_season_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < current_season_val:
                            diff_pct = ((current_season_val - current_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError, KeyError):
                        pass
                elif col in pct_cols:
                    try:
                        current_str = str(row[col]).replace('%', '')
                        current_season_str = str(current_season_avg[col]).replace('%', '')
                        current_val = float(current_str)
                        current_season_val = float(current_season_str)
                        
                        if current_val > current_season_val:
                            diff_pct = ((current_val - current_season_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            green_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb(200, {green_intensity}, 200);'
                        elif current_val < current_season_val:
                            diff_pct = ((current_season_val - current_val) / current_season_val * 100) if current_season_val > 0 else 0
                            intensity = min(diff_pct / 20, 1.0)
                            red_intensity = int(200 + (55 * intensity))
                            styles[i] = f'background-color: rgb({red_intensity}, 200, 200);'
                        else:
                            styles[i] = 'background-color: rgb(240, 240, 240);'
                    except (ValueError, TypeError, KeyError):
                        pass
            
            return styles
        
        # Add comparison columns if toggle is on
        if show_yoy_comparison:
            # Get current season averages for comparison
            if player_data.get('averages_df') is not None:
                current_season_avg = player_data['averages_df'].iloc[-1]  # Last row is current season
                
                # Create comparison dataframe
                yoy_comparison_df = yoy_averages_df.copy()
                
                numeric_cols = ['MIN', 'PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'TOV', '2PM', '2PA', '3PM', '3PA', 'FTM', 'FTA']
                pct_cols = ['2P%', '3P%', 'FT%']
                
                # Insert comparison columns after each stat
                new_cols = ['Period']
                for col in yoy_averages_df.columns[1:]:  # Skip Period column
                    new_cols.append(col)
                    if col in numeric_cols:
                        # Add +/- column comparing to current season
                        try:
                            yoy_comparison_df[f'{col} +/-'] = yoy_comparison_df.apply(
                                lambda row: f"{round(float(str(row[col]).replace(',', '')) - float(str(current_season_avg[col]).replace(',', '')), 1):+.1f}" if pd.notna(row[col]) and str(row[col]) != '' else '—',
                                axis=1
                            )
                            new_cols.append(f'{col} +/-')
                        except (KeyError, ValueError):
                            pass
                    elif col in pct_cols:
                        # Add +/- column for percentages
                        try:
                            yoy_comparison_df[f'{col} +/-'] = yoy_comparison_df.apply(
                                lambda row: f"{round(float(str(row[col]).replace('%', '')) - float(str(current_season_avg[col]).replace('%', '')), 1):+.1f}%" if pd.notna(row[col]) and str(row[col]) != '' else '—',
                                axis=1
                            )
                            new_cols.append(f'{col} +/-')
                        except (KeyError, ValueError):
                            pass
                
                # Reorder columns
                yoy_comparison_df = yoy_comparison_df[new_cols]
                styled_yoy_df = yoy_comparison_df.style.apply(style_yoy_heatmap, axis=1)
            else:
                styled_yoy_df = yoy_averages_df.style.apply(style_yoy_heatmap, axis=1)
        else:
            styled_yoy_df = yoy_averages_df.style.apply(style_yoy_heatmap, axis=1)
        
        st.dataframe(styled_yoy_df, width='stretch', hide_index=True)
    else:
        st.info("No historical season stats available for this player.")
