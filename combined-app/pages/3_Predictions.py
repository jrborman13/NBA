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


def normalize_team_minutes(statlines_list, target_minutes=240.0, out_player_ids=None, bulk_game_logs=None, game_date=None, manual_adjustments=None):
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
        manual_adjustments: Dict of player_id -> adjusted minutes for manually adjusted players (optional)
    
    Returns:
        Updated statlines_list with normalized minutes and scaled stats
    """
    # Separate by team
    away_statlines = [s for s in statlines_list if s['is_away']]
    home_statlines = [s for s in statlines_list if not s['is_away']]
    
    def check_team_rotation_size(team_id, bulk_game_logs, game_date):
        """Check if team consistently plays 8 players in recent games"""
        if bulk_game_logs is None or len(bulk_game_logs) == 0:
            return False
        
        try:
            # Get team's last 10 games before game_date
            team_games = bulk_game_logs[bulk_game_logs['TEAM_ID'] == team_id]
            if len(team_games) == 0:
                return False
            
            game_date_dt = pd.to_datetime(game_date)
            team_games = team_games[pd.to_datetime(team_games['GAME_DATE']) < game_date_dt]
            team_games = team_games.sort_values('GAME_DATE', ascending=False).head(10)
            
            if len(team_games) == 0:
                return False
            
            # Count players with 7+ minutes per game
            rotation_sizes = []
            for game_id in team_games['GAME_ID'].unique():
                game_logs = team_games[team_games['GAME_ID'] == game_id]
                players_7plus = len(game_logs[game_logs['MIN'] >= 7])
                rotation_sizes.append(players_7plus)
            
            avg_rotation = sum(rotation_sizes) / len(rotation_sizes) if rotation_sizes else 10
            return avg_rotation <= 8.5
        except Exception:
            return False
    
    def normalize_team(team_statlines, is_away_team):
        if not team_statlines:
            return
        
        # Check if manual adjustments sum to 240 for this team
        # Use CURRENT minutes for all players (manual adjustments have already been applied)
        if manual_adjustments:
            current_total = 0.0
            for statline in team_statlines:
                # Use current minutes (manual adjustments already applied)
                current_total += statline.get('MIN', 0)
            
            # If current minutes sum to exactly 240, skip normalization entirely
            if abs(current_total - target_minutes) < 0.01:
                # All minutes are locked - don't normalize
                # Still store original_min for consistency
                for statline in team_statlines:
                    statline['_original_min'] = statline['MIN']
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
        # Initialize active_player_ids outside the try block so it's available for sort_key
        active_player_ids = set()
        if bulk_game_logs is not None and len(bulk_game_logs) > 0 and game_date:
            try:
                game_date_dt = pd.to_datetime(game_date)
                # Check if player has played in last 14 days
                cutoff_date = game_date_dt - timedelta(days=14)
                
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
                        # Mark them as excluded so they won't be added back later
                        statline['_excluded_no_games'] = True
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
            
            # Boost priority for players who have played recently (last 14 days)
            # This helps prioritize Post (10 games) over Horford (4 games)
            player_id_str = statline.get('player_id')
            recent_activity_boost = 0
            if player_id_str in active_player_ids:
                # Players who have played in last 14 days get a boost
                recent_activity_boost = 5  # Small boost to break ties
            
            return (role_priority + recent_activity_boost, current_min)
        
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
        
        # ENFORCE MINIMUM 9 PLAYERS (or 8 if team consistently plays 8)
        # Get team_id from bulk_game_logs by looking up any player
        team_id = None
        consistently_plays_8 = False
        if bulk_game_logs is not None and len(bulk_game_logs) > 0:
            try:
                # Try to get team_id from any player in team_statlines (active or inactive)
                for statline in team_statlines:
                    player_id_str = statline.get('player_id')
                    if player_id_str:
                        try:
                            player_id_int = int(player_id_str)
                            player_logs = bulk_game_logs[bulk_game_logs['PLAYER_ID'] == player_id_int]
                            if len(player_logs) > 0:
                                team_id = int(player_logs['TEAM_ID'].iloc[0])
                                # Check if team consistently plays 8 players
                                if game_date:
                                    consistently_plays_8 = check_team_rotation_size(team_id, bulk_game_logs, game_date)
                                break
                        except Exception:
                            continue
            except Exception:
                pass
        
        # Default to 9 players minimum, unless team consistently plays 8
        min_players_required = 8 if consistently_plays_8 else 9
        
        # CRITICAL: Always enforce minimum - check current count and add players if needed
        current_active_count = len([s for s in team_statlines if s.get('MIN', 0) > 0.01])
        if current_active_count < min_players_required:
            # Need to add more players - get players with 0 minutes, sorted by priority
            # EXCLUDE players who have no regular season games
            inactive_players = [s for s in team_statlines if s.get('MIN', 0) <= 0.01 and not s.get('_excluded_no_games', False)]
            # Sort by role priority (same as before)
            inactive_players.sort(key=sort_key, reverse=True)
            
            # Add players until we have min_players_required
            players_needed = min_players_required - current_active_count
            for i in range(min(players_needed, len(inactive_players))):
                statline = inactive_players[i]
                # Give them a small initial minutes allocation (will be normalized later)
                statline['MIN'] = 5.0
        
        # Double-check: If we still have fewer than 9 and team doesn't consistently play 8, force to 9
        current_active_count = len([s for s in team_statlines if s.get('MIN', 0) > 0.01])
        if current_active_count < 9 and not consistently_plays_8:
            # EXCLUDE players who have no regular season games
            inactive_players = [s for s in team_statlines if s.get('MIN', 0) <= 0.01 and not s.get('_excluded_no_games', False)]
            if inactive_players:
                inactive_players.sort(key=sort_key, reverse=True)
                players_needed = 9 - current_active_count
                for i in range(min(players_needed, len(inactive_players))):
                    statline = inactive_players[i]
                    statline['MIN'] = 5.0
        
        # Recreate active_players list after adding players
        active_players = [s for s in team_statlines if s.get('MIN', 0) > 0.01]
        
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
        
        # Step 1: Scale proportionally to target, but PROTECT manually adjusted players
        if manual_adjustments:
            # Separate manually adjusted players from others
            manual_player_ids = set(str(k) for k in manual_adjustments.keys())
            manual_players = [s for s in team_statlines_for_norm if str(s.get('player_id')) in manual_player_ids]
            other_players = [s for s in team_statlines_for_norm if str(s.get('player_id')) not in manual_player_ids]
            
            # IMPORTANT: Use manual_adjustments dict values, not statline MIN (which might be outdated)
            # Update manual players' MIN from manual_adjustments dict
            for statline in manual_players:
                player_id_str = str(statline.get('player_id'))
                if player_id_str in manual_adjustments:
                    old_min = statline.get('MIN', 0)
                    new_min = manual_adjustments[player_id_str]
                    statline['MIN'] = new_min
            
            # IMPORTANT: Exclude manually adjusted players who are set to 0 minutes
            # They should not get any minutes redistributed to them
            manual_players_active = [s for s in manual_players if s.get('MIN', 0) > 0.01]
            
            # Calculate minutes from manual players (these are fixed)
            manual_total = sum(s['MIN'] for s in manual_players_active)
            
            # Calculate remaining minutes to distribute
            remaining_for_others = target_minutes - manual_total
            
            # Ensure manually adjusted players set to 0 stay at 0
            for statline in manual_players:
                if statline.get('MIN', 0) <= 0.01:
                    statline['MIN'] = 0.0
            
            
            # Scale only non-manual players
            if other_players and remaining_for_others > 0:
                other_total = sum(s['MIN'] for s in other_players)
                if other_total > 0:
                    scale_factor = remaining_for_others / other_total
                    for statline in other_players:
                        statline['MIN'] *= scale_factor
            elif other_players and remaining_for_others <= 0:
                # Set all other players to 0 if manual adjustments exceed target
                for statline in other_players:
                    statline['MIN'] = 0.0
        else:
            # Original behavior: scale everyone proportionally
            scale_factor = target_minutes / total_minutes
            for statline in team_statlines_for_norm:
                statline['MIN'] *= scale_factor
        
        # Step 2: Apply role-based floors and targets
        # Stars (>=32 MPG baseline) should get closer to their baseline (33-38 range)
        # Starters (28-31 MPG baseline) should get closer to their baseline (28-35 range)
        # BUT: Don't override manual adjustments (skip ALL manual adjustments, not just 0)
        for statline in stars:
            # Skip if this player is manually adjusted (protect ALL manual adjustments)
            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                continue  # Skip ALL manual adjustments, not just 0
            baseline = statline['_role_baseline_min']
            # Stars: target their baseline, but ensure minimum 32 MPG
            target_min = max(32.0, baseline * 0.85)  # At least 85% of baseline, minimum 32
            if statline['MIN'] < target_min:
                statline['MIN'] = target_min
        
        for statline in starters:
            # Skip if this player is manually adjusted (protect ALL manual adjustments)
            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                continue  # Skip ALL manual adjustments, not just 0
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
                        # Skip if this player is manually adjusted
                        if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                            continue  # Protect manual adjustments
                        statline['MIN'] *= scale_down_lower
            else:
                # Need to scale down everyone, but less aggressively for stars/starters
                # Scale stars/starters by 95%, others by 100%
                # BUT: Protect manual adjustments
                for statline in stars + starters:
                    # Skip if this player is manually adjusted
                    if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                        continue  # Protect manual adjustments
                    statline['MIN'] *= 0.95  # Only reduce by 5%
                
                # Recalculate and scale others more
                remaining_excess = target_minutes - sum(s['MIN'] for s in team_statlines_for_norm)
                if remaining_excess < 0:
                    scale_down = target_minutes / sum(s['MIN'] for s in team_statlines_for_norm)
                    for statline in rotation + bench + deep_bench:
                        # Skip if this player is manually adjusted
                        if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                            continue  # Protect manual adjustments
                        statline['MIN'] *= scale_down
        
        # Step 4: Apply role-based caps
        # BUT: Don't override manual adjustments (protect ALL manual adjustments from caps)
        for statline in stars:
            # Skip if this player is manually adjusted (check both string and int keys)
            player_id_str = str(statline.get('player_id'))
            is_manual = False
            if manual_adjustments:
                if player_id_str in manual_adjustments:
                    is_manual = True
                elif int(player_id_str) in manual_adjustments:
                    is_manual = True
            
            if is_manual:
                continue  # Protect manual adjustments from caps
            if statline['MIN'] > 40.0:
                statline['MIN'] = 40.0
        for statline in starters:
            # Skip if this player is manually adjusted
            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                continue  # Protect manual adjustments from caps
            if statline['MIN'] > 38.0:
                statline['MIN'] = 38.0
        for statline in rotation:
            # Skip if this player is manually adjusted
            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                continue  # Protect manual adjustments from caps
            if statline['MIN'] > 32.0:
                statline['MIN'] = 32.0
        for statline in bench:
            # Skip if this player is manually adjusted
            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                continue  # Protect manual adjustments from caps
            if statline['MIN'] > 25.0:
                statline['MIN'] = 25.0
        for statline in deep_bench:
            # Skip if this player is manually adjusted
            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                continue  # Protect manual adjustments from caps
            if statline['MIN'] > 12.0:
                statline['MIN'] = 12.0
        
        # Step 5: Distribute remaining minutes if under target
        capped_total = sum(s['MIN'] for s in team_statlines_for_norm)
        remaining_minutes = target_minutes - capped_total
        
        # Track minutes from injured players by role (for role-based redistribution)
        injured_minutes_by_role = {
            'star': 0,
            'starter': 0,
            'rotation': 0,
            'bench': 0,
            'deep_bench': 0
        }
        
        if out_player_ids:
            for statline in team_statlines:
                if statline.get('player_id') in out_player_ids:
                    baseline = statline.get('_role_baseline_min', 0)
                    original_min = statline.get('_original_min', statline.get('MIN', 0))
                    if baseline >= 32:
                        injured_minutes_by_role['star'] += original_min
                    elif baseline >= 28:
                        injured_minutes_by_role['starter'] += original_min
                    elif baseline >= 22:
                        injured_minutes_by_role['rotation'] += original_min
                    elif baseline >= 15:
                        injured_minutes_by_role['bench'] += original_min
                    else:
                        injured_minutes_by_role['deep_bench'] += original_min
        
        if remaining_minutes > 0.01:
            # First, distribute minutes from injured players to matching roles
            distributed = 0.0
            
            # Map role names to groups
            role_to_group = {
                'star': stars,
                'starter': starters,
                'rotation': rotation,
                'bench': bench,
                'deep_bench': deep_bench
            }
            
            # Distribute injured minutes primarily to matching roles
            for role_name, injured_mins in injured_minutes_by_role.items():
                if injured_mins > 0.01 and abs(remaining_minutes - distributed) > 0.01:
                    matching_group = role_to_group.get(role_name)
                    if matching_group:
                        # Get available players in matching role who aren't at cap (excluding manual adjustments)
                        available_players = []
                        for statline in matching_group:
                            # Skip if this player is manually adjusted
                            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                                continue  # Protect manual adjustments
                            baseline = statline['_role_baseline_min']
                            cap = 40.0 if baseline >= 32 else (38.0 if baseline >= 28 else (32.0 if baseline >= 22 else (25.0 if baseline >= 15 else 12.0)))
                            if statline['MIN'] < cap - 0.01:
                                available_players.append(statline)
                        
                        if available_players:
                            # Distribute injured minutes to matching role (up to the amount available)
                            # available_players already excludes manual adjustments
                            available_players_filtered = available_players
                            
                            mins_to_distribute = min(injured_mins, remaining_minutes - distributed)
                            group_total = sum(s['MIN'] for s in available_players_filtered)
                            if group_total > 0:
                                for statline in available_players_filtered:
                                    # Skip if this player is manually adjusted
                                    if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                                        continue  # Protect manual adjustments
                                    baseline = statline['_role_baseline_min']
                                    cap = 40.0 if baseline >= 32 else (38.0 if baseline >= 28 else (32.0 if baseline >= 22 else (25.0 if baseline >= 15 else 12.0)))
                                    additional = mins_to_distribute * (statline['MIN'] / group_total)
                                    old_min = statline['MIN']
                                    statline['MIN'] = min(statline['MIN'] + additional, cap)
                                    actual_added = statline['MIN'] - old_min
                                    distributed += actual_added
            
            # If there are still remaining minutes, distribute to higher-role players (fallback)
            if abs(remaining_minutes - distributed) > 0.01:
                for group in priority_groups:
                    if abs(remaining_minutes - distributed) < 0.01:
                        break
                    
                    # Get players in this group who aren't at their cap (excluding manual adjustments)
                    available_players = []
                    for statline in group:
                        # Skip if this player is manually adjusted
                        if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                            continue  # Protect manual adjustments
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
                            # Skip if this player is manually adjusted (double-check)
                            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                                continue  # Protect manual adjustments
                            baseline = statline['_role_baseline_min']
                            cap = 40.0 if baseline >= 32 else (38.0 if baseline >= 28 else (32.0 if baseline >= 22 else (25.0 if baseline >= 15 else 12.0)))
                            additional = group_remaining * (statline['MIN'] / group_total)
                            old_min = statline['MIN']
                            statline['MIN'] = min(statline['MIN'] + additional, cap)
                            actual_added = statline['MIN'] - old_min
                            distributed += actual_added
        
        # Step 6: Final safety check - ensure exact total
        # Protect stars/starters from being scaled down too much
        # BUT: Protect ALL manual adjustments from any scaling
        final_total = sum(s['MIN'] for s in team_statlines_for_norm)
        if abs(final_total - target_minutes) > 0.01:
            # Final proportional scaling, but protect stars/starters AND manual adjustments
            if final_total > target_minutes:
                # Over target - scale down, but protect stars/starters AND manual adjustments
                excess = final_total - target_minutes
                # Calculate totals excluding manual adjustments
                lower_role_total = 0.0
                for statline in rotation + bench + deep_bench:
                    # Skip if this player is manually adjusted
                    if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                        continue  # Protect manual adjustments
                    lower_role_total += statline['MIN']
                
                if lower_role_total >= excess:
                    scale_down = (lower_role_total - excess) / lower_role_total if lower_role_total > 0 else 1.0
                    for statline in rotation + bench + deep_bench:
                        # Skip if this player is manually adjusted
                        if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                            continue  # Protect manual adjustments
                        statline['MIN'] *= scale_down
                else:
                    # Need to scale everyone, but less for stars/starters AND protect manual adjustments
                    # Calculate totals excluding manual adjustments
                    non_manual_total = 0.0
                    for statline in team_statlines_for_norm:
                        if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                            continue  # Exclude manual adjustments from total
                        non_manual_total += statline['MIN']
                    
                    manual_total = final_total - non_manual_total
                    remaining_target = target_minutes - manual_total
                    
                    if non_manual_total > 0 and remaining_target > 0:
                        scale_factor = remaining_target / non_manual_total
                        for statline in stars + starters:
                            # Skip if this player is manually adjusted
                            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                                continue  # Protect manual adjustments
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
                        # Calculate other_total excluding manual adjustments
                        other_total = 0.0
                        for statline in rotation + bench + deep_bench:
                            # Skip if this player is manually adjusted
                            if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                                continue  # Protect manual adjustments
                            other_total += statline['MIN']
                        
                        if other_total > 0:
                            scale_others = (other_total + remaining) / other_total
                            for statline in rotation + bench + deep_bench:
                                # Skip if this player is manually adjusted
                                if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                                    continue  # Protect manual adjustments
                                statline['MIN'] *= scale_others
            else:
                # Under target - scale up proportionally
                # BUT: Protect manual adjustments
                # Calculate totals excluding manual adjustments
                non_manual_total = 0.0
                for statline in team_statlines_for_norm:
                    if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                        continue  # Exclude manual adjustments from total
                    non_manual_total += statline['MIN']
                
                manual_total = final_total - non_manual_total
                remaining_target = target_minutes - manual_total
                
                if non_manual_total > 0 and remaining_target > 0:
                    final_scale = remaining_target / non_manual_total
                    for statline in team_statlines_for_norm:
                        # Skip if this player is manually adjusted
                        if manual_adjustments and str(statline.get('player_id')) in manual_adjustments:
                            continue  # Protect manual adjustments
                        statline['MIN'] *= final_scale
                        # Reapply caps after scaling (but manual adjustments already skipped)
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
        
        # Step 8: Absolute final check - guarantee minimum 9 players (or 8 if team plays 8) and exactly 240 minutes
        # This is a safety net to catch any edge cases
        final_check_active = [s for s in team_statlines if s.get('MIN', 0) > 0.01]
        final_check_total = sum(s['MIN'] for s in final_check_active)
        
        # CRITICAL: Ensure minimum 9 players (or 8 if team consistently plays 8)
        # Check team_id again to determine minimum
        team_id_final = None
        consistently_plays_8_final = False
        if bulk_game_logs is not None and len(bulk_game_logs) > 0:
            try:
                for statline in team_statlines:
                    player_id_str = statline.get('player_id')
                    if player_id_str:
                        try:
                            player_id_int = int(player_id_str)
                            player_logs = bulk_game_logs[bulk_game_logs['PLAYER_ID'] == player_id_int]
                            if len(player_logs) > 0:
                                team_id_final = int(player_logs['TEAM_ID'].iloc[0])
                                if game_date:
                                    consistently_plays_8_final = check_team_rotation_size(team_id_final, bulk_game_logs, game_date)
                                break
                        except Exception:
                            continue
            except Exception:
                pass
        
        min_players_final = 8 if consistently_plays_8_final else 9
        
        # If we have fewer than minimum, add players back
        if len(final_check_active) < min_players_final:
            inactive_players = [s for s in team_statlines if s.get('MIN', 0) <= 0.01]
            if inactive_players:
                inactive_players.sort(key=sort_key, reverse=True)
                players_needed = min_players_final - len(final_check_active)
                for i in range(min(players_needed, len(inactive_players))):
                    statline = inactive_players[i]
                    # Give them a small allocation that will be normalized
                    statline['MIN'] = 5.0
                # Recalculate active players
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
st.title("Predictions")

# Add sidebar with cache clear button
with st.sidebar:
    st.markdown("### Cache Management")
    if st.button("🗑️ Clear All Cache", width='stretch'):
        st.cache_data.clear()
        st.success("✅ Cache cleared successfully!")
        st.rerun()
    st.markdown("---")  # Separator


# Cache players dataframe to avoid repeated API calls
@st.cache_data
def get_cached_players_dataframe():
    """Cache players dataframe from PlayerIndex endpoint"""
    result = pf.get_players_dataframe()
    return result

@st.cache_data
def get_cached_player_list():
    """Cache player list from PlayerIndex endpoint"""
    result = pf.get_player_list()
    return result

@st.cache_data
def get_player_name_map(player_ids_list, players_df):
    """Cache player names using the players dataframe"""
    result = {pid: pf.get_player_name(pid, players_df) for pid in player_ids_list}
    return result

@st.cache_data
def get_cached_player_stats():
    """Get player stats including average minutes for sorting"""
    try:
        import nba_api.stats.endpoints as endpoints
        player_stats = endpoints.LeagueDashPlayerStats(
            season=pf_features.CURRENT_SEASON,
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
player_minutes_map = get_cached_player_stats()

# Cached function to fetch injury report for a specific date
@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def get_cached_injury_report_for_date(selected_date):
    """Fetch and cache injury report for a specific date"""
    try:
        # Always use today's date for injury reports (PDF includes tomorrow's games too)
        injury_df, status_msg = ir.fetch_injuries_for_date(report_date=date.today())
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
            


# Fetch injury report for the selected date
injury_report_df, injury_report_url, injury_load_error = get_cached_injury_report_for_date(selected_date)

# Clear processed matchups cache when date changes (so injuries get re-processed)
if 'last_injury_date_predictions' not in st.session_state or st.session_state.last_injury_date_predictions != selected_date:
    st.session_state.last_injury_date_predictions = selected_date
    st.session_state.processed_matchups_predictions = {}  # Clear cached matchup injury data

# Check if matchup is selected
if selected_matchup_str and selected_matchup_str != "All Players" and selected_matchup_str != "All Matchups":
    selected_matchup = next((m for m in matchups if m['matchup'] == selected_matchup_str), None)
    
    if selected_matchup:
        matchup_away_team_id = selected_matchup['away_team_id']
        matchup_home_team_id = selected_matchup['home_team_id']
        matchup_away_team_abbr = selected_matchup['away_team']
        matchup_home_team_abbr = selected_matchup['home_team']
        
        # Filter players for this matchup
        if 'TEAM_ID' in players_df.columns:
            selected_team_ids = [matchup_away_team_id, matchup_home_team_id]
            players_df_team_ids = players_df['TEAM_ID'].astype(int)
            filtered_players_df = players_df[players_df_team_ids.isin(selected_team_ids)].copy()
            filtered_player_ids_list = filtered_players_df['PERSON_ID'].astype(str).tolist()
        else:
            filtered_player_ids_list = player_ids_list.copy()
        
        # Show matchup info
        st.info(f"📊 Generating predictions for: {matchup_away_team_abbr} @ {matchup_home_team_abbr}")
        
        # === INJURY REPORT SECTION ===
        st.markdown("---")
        with st.expander("🏥 **Injury Report** - Official NBA injury data", expanded=True):
            st.caption("Players marked OUT/Doubtful are auto-selected below")
            
            # Use the pre-fetched injury data from initial load
            # Create a matchup-specific key for session state
            matchup_key = f"predictions_{matchup_away_team_abbr}@{matchup_home_team_abbr}"
            
            # Initialize session state for this matchup if needed
            if 'processed_matchups_predictions' not in st.session_state:
                st.session_state.processed_matchups_predictions = {}
        
            # Process injuries for this matchup (only once per matchup)
            if matchup_key not in st.session_state.processed_matchups_predictions:
                away_out = []
                home_out = []
                all_matchup_injuries = {'away': [], 'home': []}
                questionable_probable = {'away': [], 'home': []}
                has_injuries = False
                if injury_report_df is not None:
                    try:
                        df_len = len(injury_report_df)
                        has_injuries = df_len > 0
                    except Exception as e:
                        has_injuries = False
                if has_injuries:
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
                st.session_state.processed_matchups_predictions[matchup_key] = {
                    'away_out': away_out,
                    'home_out': home_out,
                    'all_matchup_injuries': all_matchup_injuries,
                    'questionable_probable': questionable_probable
                }
            
            # Get the processed data for this matchup
            matchup_data = st.session_state.processed_matchups_predictions[matchup_key]
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
        
        # === SELECT PLAYERS OUT SECTION ===
        # Get players from both teams for the injury selection
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
                key=f"predictions_away_injuries_{matchup_key}",
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
                key=f"predictions_home_injuries_{matchup_key}",
                label_visibility="collapsed"
            )
        
        # Store selections in session state for use by Best Value Plays
        predictions_injuries_key = f"predictions_injuries_{matchup_key}"
        st.session_state[predictions_injuries_key] = {
            'away_out': away_players_out,
            'home_out': home_players_out
        }

        
        # === BEST VALUE PLAYS SECTION ===
        # BEST VALUE PLAYS SECTION
        # ============================================================
        game_date_str_bvp = selected_date.strftime('%Y-%m-%d')
        game_cache_key_bvp = f"{game_date_str_bvp}_{matchup_away_team_abbr}_{matchup_home_team_abbr}"
        
        # Initialize session state for game-level prediction cache
        if 'predictions_game_cache' not in st.session_state:
            st.session_state.predictions_game_cache = {}
        
        with st.expander("🎯 **Best Value Plays** - Find edges across the entire game", expanded=True):
            st.caption("Generate predictions for all players and compare against Underdog lines to find the best value plays")
            
            # Check if we have cached predictions for this game
            cached_game_predictions = st.session_state.predictions_game_cache.get(game_cache_key_bvp)
            
            # If no cached predictions, check for CSV file from DraftKings Optimizer
            if cached_game_predictions is None:
                downloads_dir = os.path.expanduser("~/Downloads")
                csv_file = os.path.join(
                    downloads_dir,
                    f"predicted_statlines_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv"
                )
                
                if os.path.exists(csv_file):
                    try:
                        # Load CSV file
                        csv_df = pd.read_csv(csv_file)
                        
                        # Convert CSV to predictions format
                        loaded_predictions = {}
                        for _, row in csv_df.iterrows():
                            player_name = row.get('Player', '')
                            team_abbr = row.get('Team', '')
                            
                            # Find player ID by matching name
                            player_match = players_df[
                                (players_df['PLAYER_FIRST_NAME'] + ' ' + players_df['PLAYER_LAST_NAME'] == player_name) |
                                (players_df['PLAYER_FIRST_NAME'] + ' ' + players_df['PLAYER_LAST_NAME'].str.replace(' ', '') == player_name)
                            ]
                            
                            if len(player_match) > 0:
                                player_id = str(player_match['PERSON_ID'].iloc[0])
                                
                                # Determine if home or away
                                is_home = team_abbr == matchup_home_team_abbr
                                opponent_abbr = matchup_home_team_abbr if not is_home else matchup_away_team_abbr
                                
                                # Create Prediction objects from CSV values
                                predictions_dict = {}
                                
                                # Create Prediction objects for each stat
                                stats_to_load = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']
                                for stat in stats_to_load:
                                    if stat in row and pd.notna(row[stat]):
                                        value = float(row[stat])
                                        predictions_dict[stat] = pm.Prediction(
                                            stat=stat,
                                            value=value,
                                            confidence='medium',  # Default confidence for loaded predictions
                                            breakdown={},
                                            factors={'source': 'CSV file'}
                                        )
                                
                                # Add ceiling/floor if available
                                ceiling_floor = {}
                                if 'FPTS_Ceiling' in row and pd.notna(row['FPTS_Ceiling']):
                                    ceiling_floor['ceiling'] = float(row['FPTS_Ceiling'])
                                if 'FPTS_Floor' in row and pd.notna(row['FPTS_Floor']):
                                    ceiling_floor['floor'] = float(row['FPTS_Floor'])
                                if 'FPTS_Median' in row and pd.notna(row['FPTS_Median']):
                                    ceiling_floor['median'] = float(row['FPTS_Median'])
                                if 'FPTS_Variance' in row and pd.notna(row['FPTS_Variance']):
                                    ceiling_floor['variance'] = float(row['FPTS_Variance'])
                                if 'FPTS_StdDev' in row and pd.notna(row['FPTS_StdDev']):
                                    ceiling_floor['std_dev'] = float(row['FPTS_StdDev'])
                                
                                loaded_predictions[player_id] = {
                                    'predictions': predictions_dict,
                                    'player_name': player_name,
                                    'opponent_abbr': opponent_abbr,
                                    'is_home': is_home,
                                    'team_abbr': team_abbr,
                                    'ceiling_floor': ceiling_floor if ceiling_floor else None
                                }
                        
                        if len(loaded_predictions) > 0:
                            # Cache the loaded predictions
                            st.session_state.predictions_game_cache[game_cache_key_bvp] = loaded_predictions
                            cached_game_predictions = loaded_predictions
                            st.info(f"📂 Loaded {len(loaded_predictions)} predictions from CSV file")
                    except Exception as e:
                        # If loading fails, just continue without cached predictions
                        st.warning(f"⚠️ Could not load predictions from CSV: {e}")
                        cached_game_predictions = None
            
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
                    
                    # Get list of players who are OUT or DOUBTFUL from stored selections
                    predictions_injuries_key = f"predictions_injuries_{matchup_key}"
                    stored_injuries = st.session_state.get(predictions_injuries_key, {'away_out': [], 'home_out': []})
                    out_player_ids = set(stored_injuries.get('away_out', []) + stored_injuries.get('home_out', []))
                    
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
                    import time
                    gen_start = time.time()
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
                    gen_total_time = time.time() - gen_start
                    
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
                        # Clear cached predictions (including CSV-loaded ones)
                        if game_cache_key_bvp in st.session_state.predictions_game_cache:
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
                
                # Build lists of out players by team ONCE from stored selections
                predictions_injuries_key = f"predictions_injuries_{matchup_key}"
                stored_injuries = st.session_state.get(predictions_injuries_key, {'away_out': [], 'home_out': []})
                away_out = stored_injuries.get('away_out', [])
                home_out = stored_injuries.get('home_out', [])
                out_player_ids = set(away_out + home_out)
                
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
                            game_date=game_date_str_bvp,
                            manual_adjustments=None
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
                    
                    # Store original MIN values BEFORE normalization for comparison
                    # This ensures we can detect when user resets to original vs when normalization matches manual adjustment
                    original_mins_key = f"{game_cache_key_bvp}_original_mins"
                    if original_mins_key not in st.session_state:
                        # Store original MIN values (before any normalization or manual adjustments)
                        st.session_state[original_mins_key] = {statline['player_id']: statline['MIN'] for statline in statlines_list}
                    
                    # Get bulk game logs for recent activity check
                    bulk_game_logs = pf_features.get_bulk_player_game_logs()
                    
                    # Normalize minutes and scale stats using helper function
                    normalize_team_minutes(
                        statlines_list, 
                        target_minutes=240.0,
                        out_player_ids=out_player_ids,  # Pass the set of OUT/DOUBTFUL players
                        bulk_game_logs=bulk_game_logs,  # Pass bulk game logs
                        game_date=game_date_str_bvp,  # Pass game date for recent activity check
                        manual_adjustments=None
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
                    
                    # Get original MIN values key (should already be stored before normalization)
                    original_mins_key = f"{game_cache_key_bvp}_original_mins"
                    
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
                                
                                # Allow up to 48 minutes (max possible in a game)
                                # Use current_min but clamp to valid range to avoid errors
                                clamped_value = max(0.0, min(48.0, float(current_min)))
                                
                                new_min = st.number_input(
                                    f"{statline['Player']}",
                                    min_value=0.0,
                                    max_value=48.0,
                                    value=clamped_value,
                                    step=0.5,
                                    key=player_key,
                                    format="%.1f"
                                )
                                
                                # Store manual adjustment in session state (but don't apply until button click)
                                # Compare against ORIGINAL MIN (before manual adjustments), not normalized MIN
                                original_min = st.session_state.get(original_mins_key, {}).get(player_id_str, statline['MIN'])
                                if abs(new_min - original_min) > 0.01:
                                    st.session_state[manual_adjustments_key][player_id_str] = new_min
                                elif player_id_str in st.session_state[manual_adjustments_key] and abs(new_min - original_min) <= 0.01:
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
                                
                                # Allow up to 48 minutes (max possible in a game)
                                # Use current_min but clamp to valid range to avoid errors
                                clamped_value = max(0.0, min(48.0, float(current_min)))
                                
                                new_min = st.number_input(
                                    f"{statline['Player']}",
                                    min_value=0.0,
                                    max_value=48.0,
                                    value=clamped_value,
                                    step=0.5,
                                    key=player_key,
                                    format="%.1f"
                                )
                                
                                # Store manual adjustment in session state (but don't apply until button click)
                                # Compare against ORIGINAL MIN (before manual adjustments), not normalized MIN
                                original_min = st.session_state.get(original_mins_key, {}).get(player_id_str, statline['MIN'])
                                if abs(new_min - original_min) > 0.01:
                                    st.session_state[manual_adjustments_key][player_id_str] = new_min
                                elif player_id_str in st.session_state[manual_adjustments_key] and abs(new_min - original_min) <= 0.01:
                                    # If user resets to original value, remove from manual adjustments
                                    del st.session_state[manual_adjustments_key][player_id_str]
                        
                        # Show preview of manual adjustments if any exist
                        if st.session_state[manual_adjustments_key]:
                            st.info(f"ℹ️ {len(st.session_state[manual_adjustments_key])} player(s) have manual minute adjustments. Click 'Recalculate' to apply.")
                        
                        # Apply manual adjustments and recalculate button
                        if st.button("🔄 Recalculate Stats & Value Plays", key="recalc_stats"):
                            # Clear best_plays cache so it recalculates with new minutes
                            cached_best_plays_key = f"{game_cache_key_bvp}_best_plays"
                            if cached_best_plays_key in st.session_state:
                                del st.session_state[cached_best_plays_key]
                            
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
                            
                            # Manual adjustments were already applied to statlines_list_copy above (lines 2550-2554)
                            # Now we just need to scale stats for manually adjusted players based on their new minutes
                            manual_adjustments = st.session_state[manual_adjustments_key]
                            for statline in statlines_list:
                                player_id_str = statline['player_id']
                                if player_id_str in manual_adjustments:
                                    # Ensure MIN matches manual adjustment exactly (protect from any modifications)
                                    new_minutes = manual_adjustments[player_id_str]
                                    statline['MIN'] = new_minutes  # Force exact value from manual_adjustments dict
                                    
                                    # Scale stats for manually adjusted players
                                    old_minutes = statline.get('_original_min', statline.get('MIN', 0))
                                    
                                    # If new minutes is 0 or very small, set all stats to 0
                                    if new_minutes <= 0.01:
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
                                    elif old_minutes > 0.01:
                                        # Use base stats if available, otherwise use current stats
                                        base_stats = statline.get('_base_stats', {})
                                        if base_stats and len(base_stats) > 0:
                                            # Scale from base stats
                                            scale_factor = new_minutes / old_minutes
                                            statline['PTS'] = base_stats.get('PTS', 0.0) * scale_factor
                                            statline['REB'] = base_stats.get('REB', 0.0) * scale_factor
                                            statline['AST'] = base_stats.get('AST', 0.0) * scale_factor
                                            statline['STL'] = base_stats.get('STL', 0.0) * scale_factor
                                            statline['BLK'] = base_stats.get('BLK', 0.0) * scale_factor
                                            statline['TOV'] = base_stats.get('TOV', 0.0) * scale_factor
                                            statline['FG3M'] = base_stats.get('FG3M', 0.0) * scale_factor
                                            statline['FTM'] = base_stats.get('FTM', 0.0) * scale_factor
                                        else:
                                            # Fallback to current stats if base stats not available
                                            scale_factor = new_minutes / old_minutes
                                            statline['PTS'] = statline.get('PTS', 0.0) * scale_factor
                                            statline['REB'] = statline.get('REB', 0.0) * scale_factor
                                            statline['AST'] = statline.get('AST', 0.0) * scale_factor
                                            statline['STL'] = statline.get('STL', 0.0) * scale_factor
                                            statline['BLK'] = statline.get('BLK', 0.0) * scale_factor
                                            statline['TOV'] = statline.get('TOV', 0.0) * scale_factor
                                            statline['FG3M'] = statline.get('FG3M', 0.0) * scale_factor
                                            statline['FTM'] = statline.get('FTM', 0.0) * scale_factor
                                        
                                        # Recalculate derived stats
                                        statline['PRA'] = statline['PTS'] + statline['REB'] + statline['AST']
                                        statline['RA'] = statline['REB'] + statline['AST']
                                        statline['FPTS'] = (
                                            statline['PTS'] + 
                                            statline['REB'] * 1.2 + 
                                            statline['AST'] * 1.5 + 
                                            statline['STL'] * 3 + 
                                            statline['BLK'] * 3 - 
                                            statline['TOV']
                                        )
                                    else:
                                        # Player was at 0 minutes, but now has non-zero minutes
                                        if new_minutes > 0.01:
                                            base_stats = statline.get('_base_stats', {})
                                            if base_stats and len(base_stats) > 0 and not all(v == 0.0 for v in base_stats.values()):
                                                # Use base_stats and scale to new_minutes
                                                # Get scaling baseline (same logic as normalize_team_minutes)
                                                scaling_baseline = statline.get('_injury_adjusted_minutes')
                                                if scaling_baseline is None or scaling_baseline <= 0:
                                                    scaling_baseline = statline.get('_original_season_minutes')
                                                if scaling_baseline is None or scaling_baseline <= 0:
                                                    scaling_baseline = 25.0  # Default baseline
                                                
                                                scale_factor = new_minutes / scaling_baseline
                                                statline['PTS'] = base_stats.get('PTS', 0.0) * scale_factor
                                                statline['REB'] = base_stats.get('REB', 0.0) * scale_factor
                                                statline['AST'] = base_stats.get('AST', 0.0) * scale_factor
                                                statline['STL'] = base_stats.get('STL', 0.0) * scale_factor
                                                statline['BLK'] = base_stats.get('BLK', 0.0) * scale_factor
                                                statline['TOV'] = base_stats.get('TOV', 0.0) * scale_factor
                                                statline['FG3M'] = base_stats.get('FG3M', 0.0) * scale_factor
                                                statline['FTM'] = base_stats.get('FTM', 0.0) * scale_factor
                                                
                                                # Recalculate derived stats
                                                statline['PRA'] = statline['PTS'] + statline['REB'] + statline['AST']
                                                statline['RA'] = statline['REB'] + statline['AST']
                                                statline['FPTS'] = (
                                                    statline['PTS'] + 
                                                    statline['REB'] * 1.2 + 
                                                    statline['AST'] * 1.5 + 
                                                    statline['STL'] * 3 + 
                                                    statline['BLK'] * 3 - 
                                                    statline['TOV']
                                                )
                                            else:
                                                # No base stats available, set to 0
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
                            
                            # Check if manual adjustments sum to 240 for each team
                            # If so, skip normalization entirely and lock all minutes
                            skip_normalization = False
                            if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                                manual_adjustments_check = st.session_state[manual_adjustments_key]
                                
                                # Calculate totals for each team using manual adjustments if they exist, otherwise use current MIN
                                away_total = 0.0
                                home_total = 0.0
                                away_manual_count = 0
                                home_manual_count = 0
                                
                                for statline in statlines_list:
                                    player_id_str = statline.get('player_id')
                                    # Use manual adjustment if exists, otherwise use current MIN from statline
                                    if player_id_str in manual_adjustments_check:
                                        current_min = manual_adjustments_check[player_id_str]
                                        if statline.get('is_away', False):
                                            away_manual_count += 1
                                        else:
                                            home_manual_count += 1
                                    else:
                                        current_min = statline.get('MIN', 0)
                                    
                                    if statline.get('is_away', False):
                                        away_total += current_min
                                    else:
                                        home_total += current_min
                                
                                # If both teams sum to exactly 240, skip normalization entirely
                                if abs(away_total - 240.0) < 0.01 and abs(home_total - 240.0) < 0.01:
                                    skip_normalization = True
                            
                            if not skip_normalization:
                                # Normalize minutes to 240 per team (but protect manual adjustments)
                                normalize_team_minutes(
                                    statlines_list, 
                                    target_minutes=240.0,
                                    out_player_ids=out_player_ids_recalc,
                                    bulk_game_logs=bulk_game_logs,
                                    game_date=game_date_str_bvp,
                                    manual_adjustments=st.session_state[manual_adjustments_key] if manual_adjustments_key in st.session_state else None
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
                            
                            # Recalculate Value Plays with updated normalized_predictions
                            
                            best_plays = pm.find_best_value_plays(
                                all_predictions=normalized_predictions,
                                all_props=cached_game_props,
                                min_edge_pct=float(min_edge),
                                confidence_filter=confidence_options if confidence_options else ['high', 'medium', 'low'],
                                stat_filter=stat_options if stat_options else ['PTS', 'REB', 'AST', 'PRA'],
                                injury_adjustments_map=None
                            )
                            
                            # CRITICAL: Reapply manual adjustments AFTER normalization to ensure they're preserved
                            # Normalization might have modified manual adjustment values, so restore them
                            manual_adjustments_reapplied = False
                            if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                                for statline in statlines_list:
                                    player_id_str = statline.get('player_id')
                                    if player_id_str in st.session_state[manual_adjustments_key]:
                                        manual_min = st.session_state[manual_adjustments_key][player_id_str]
                                        old_statline_min = statline.get('MIN', 0)
                                        
                                        # Only reapply if different (normalization might have changed it)
                                        if abs(manual_min - old_statline_min) > 0.01:
                                            statline['MIN'] = manual_min  # Force exact manual adjustment value
                                            manual_adjustments_reapplied = True
                                            
                                            # Recalculate stats for this player based on new minutes
                                            # Use CURRENT normalized stats and minutes (not base_stats) for accurate scaling
                                            old_minutes = old_statline_min  # Current normalized minutes before manual adjustment
                                            new_minutes = manual_min
                                            
                                            if new_minutes > 0.01 and old_minutes > 0.01:
                                                # Scale from CURRENT normalized stats (which already account for normalization)
                                                # This ensures stats scale correctly relative to the current normalized state
                                                scale_factor = new_minutes / old_minutes
                                                statline['PTS'] = statline.get('PTS', 0.0) * scale_factor
                                                statline['REB'] = statline.get('REB', 0.0) * scale_factor
                                                statline['AST'] = statline.get('AST', 0.0) * scale_factor
                                                statline['STL'] = statline.get('STL', 0.0) * scale_factor
                                                statline['BLK'] = statline.get('BLK', 0.0) * scale_factor
                                                statline['TOV'] = statline.get('TOV', 0.0) * scale_factor
                                                statline['FG3M'] = statline.get('FG3M', 0.0) * scale_factor
                                                statline['FTM'] = statline.get('FTM', 0.0) * scale_factor
                                                
                                                # Recalculate derived stats
                                                statline['PRA'] = statline['PTS'] + statline['REB'] + statline['AST']
                                                statline['RA'] = statline['REB'] + statline['AST']
                                                statline['FPTS'] = (
                                                    statline['PTS'] + 
                                                    statline['REB'] * 1.2 + 
                                                    statline['AST'] * 1.5 + 
                                                    statline['STL'] * 3 + 
                                                    statline['BLK'] * 3 - 
                                                    statline['TOV']
                                                )
                            
                            # If manual adjustments were reapplied, rebuild normalized_predictions and recalculate value plays
                            if manual_adjustments_reapplied:
                                # Rebuild normalized_predictions with updated statlines
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
                                
                                # Recalculate value plays with updated normalized_predictions
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
                    
                    # Filter out players with 0 minutes before displaying
                    statlines_list_filtered = [s for s in statlines_list if s.get('MIN', 0) > 0.01]
                    
                    # Sort: away team first (minutes descending), then home team (minutes descending)
                    statlines_list_filtered.sort(key=lambda x: (not x['is_away'], -x['MIN']))
                    
                    # Create DataFrame from filtered list
                    statlines_df = pd.DataFrame(statlines_list_filtered)
                    display_statlines_df = statlines_df[['Player', 'Team', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']].copy()
                    
                    # Format numbers
                    for col in ['MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']:
                        display_statlines_df[col] = display_statlines_df[col].apply(lambda x: f"{x:.1f}")
                    
                    st.dataframe(display_statlines_df, width='stretch', hide_index=True)
                    
                    # Download button for Predicted Statlines (also filtered)
                    csv_statlines = statlines_df[['Player', 'Team', 'MIN', 'PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM', 'PRA', 'FPTS']].copy()
                    csv_statlines_str = csv_statlines.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Predicted Statlines CSV",
                        data=csv_statlines_str,
                        file_name=f"predicted_statlines_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                        mime="text/csv",
                        key="download_statlines"
                    )
                    
                    # Download button for Manual Adjustments
                    manual_adjustments_key = f"{game_cache_key_bvp}_manual_minutes"
                    if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                        manual_adjustments = st.session_state[manual_adjustments_key]
                        statlines_list_for_export = st.session_state.get(normalized_statlines_key, statlines_list)
                        
                        # Create DataFrame with manual adjustments
                        manual_adjustments_data = []
                        for statline in statlines_list_for_export:
                            player_id_str = statline.get('player_id')
                            player_name = statline.get('Player', 'Unknown')
                            team = statline.get('Team', 'Unknown')
                            original_min = statline.get('_original_min', statline.get('MIN', 0))
                            current_min = statline.get('MIN', 0)
                            
                            if player_id_str in manual_adjustments:
                                adjusted_min = manual_adjustments[player_id_str]
                                difference = adjusted_min - original_min
                            else:
                                adjusted_min = original_min
                                difference = 0.0
                            
                            manual_adjustments_data.append({
                                'Player': player_name,
                                'Team': team,
                                'Original_Minutes': original_min,
                                'Manually_Adjusted_Minutes': adjusted_min,
                                'Difference': difference,
                                'Current_Projected_Minutes': current_min
                            })
                        
                        if manual_adjustments_data:
                            manual_adjustments_df = pd.DataFrame(manual_adjustments_data)
                            # Sort by team, then by current minutes descending
                            manual_adjustments_df = manual_adjustments_df.sort_values(['Team', 'Current_Projected_Minutes'], ascending=[True, False])
                            
                            csv_manual_adjustments = manual_adjustments_df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download Manual Minute Adjustments CSV",
                                data=csv_manual_adjustments,
                                file_name=f"manual_adjustments_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                                mime="text/csv",
                                key="download_manual_adjustments"
                            )
                    
                    # Debug output for manual adjustments (always visible)
                    if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                        manual_adjustments = st.session_state[manual_adjustments_key]
                        statlines_list_debug = st.session_state.get(normalized_statlines_key, [])
                        cached_game_predictions_debug = st.session_state.predictions_game_cache.get(game_cache_key_bvp)
                        
                        with st.expander("🔍 Debug: Manual Adjustments Details", expanded=True):
                            st.write("### Players with Manual Minute Adjustments")
                            for statline in statlines_list_debug:
                                player_id_str = statline.get('player_id')
                                if player_id_str in manual_adjustments:
                                    player_name = statline.get('Player', 'Unknown')
                                    old_min = statline.get('_original_min', statline.get('MIN', 0))
                                    new_min = manual_adjustments[player_id_str]
                                    
                                    base_stats = statline.get('_base_stats', {})
                                    scaling_baseline = statline.get('_injury_adjusted_minutes')
                                    if scaling_baseline is None or scaling_baseline <= 0:
                                        scaling_baseline = statline.get('_original_season_minutes')
                                    if scaling_baseline is None or scaling_baseline <= 0:
                                        scaling_baseline = 25.0
                                    
                                    st.write(f"**{player_name}** (ID: {player_id_str})")
                                    st.write(f"- Minutes: {old_min:.1f} → {new_min:.1f}")
                                    st.write(f"- Base stats exist: {bool(base_stats and len(base_stats) > 0)}")
                                    if base_stats and len(base_stats) > 0:
                                        st.write(f"- Base stats: PTS={base_stats.get('PTS', 0):.1f}, REB={base_stats.get('REB', 0):.1f}, AST={base_stats.get('AST', 0):.1f}, STL={base_stats.get('STL', 0):.1f}, BLK={base_stats.get('BLK', 0):.1f}, TOV={base_stats.get('TOV', 0):.1f}")
                                    st.write(f"- Scaling baseline: {scaling_baseline:.1f}")
                                    if old_min > 0.01:
                                        st.write(f"- Scale factor: {new_min / old_min:.3f}")
                                    elif base_stats and len(base_stats) > 0 and not all(v == 0.0 for v in base_stats.values()):
                                        st.write(f"- Scale factor (0→nonzero): {new_min / scaling_baseline:.3f}")
                                    
                                    # Show current stats
                                    st.write(f"- Current stats: PTS={statline.get('PTS', 0):.1f}, REB={statline.get('REB', 0):.1f}, AST={statline.get('AST', 0):.1f}, STL={statline.get('STL', 0):.1f}, BLK={statline.get('BLK', 0):.1f}, TOV={statline.get('TOV', 0):.1f}, FPTS={statline.get('FPTS', 0):.1f}")
                                    
                                    # Check if player exists in cached predictions
                                    player_in_cache = False
                                    if cached_game_predictions_debug:
                                        try:
                                            player_id_int = int(player_id_str)
                                            player_in_cache = player_id_int in cached_game_predictions_debug
                                        except:
                                            pass
                                    st.write(f"- Player in cached predictions: {player_in_cache}")
                                    st.write("---")
                    
                    # Value Plays section after manual adjustments
                    # Only show if manual adjustments exist or predictions have been recalculated
                    if manual_adjustments_key in st.session_state and st.session_state[manual_adjustments_key]:
                        # Reload statlines_list from session state to ensure we have the latest version with manual adjustments applied
                        statlines_list_updated = st.session_state.get(normalized_statlines_key, statlines_list)
                        
                        # Check if we have cached game props and predictions
                        cached_game_props_updated = st.session_state.odds_game_cache.get(game_cache_key_bvp)
                        cached_game_predictions_updated = st.session_state.predictions_game_cache.get(game_cache_key_bvp)
                        
                        if cached_game_props_updated is not None and cached_game_predictions_updated is not None:
                            # Build normalized predictions dict from current statlines (includes manual adjustments)
                            updated_normalized_predictions = {}
                            for statline in statlines_list_updated:
                                player_id_str = statline['player_id']
                                # Only include players with minutes > 0
                                if statline.get('MIN', 0) > 0.01:
                                    if player_id_str not in updated_normalized_predictions:
                                        updated_normalized_predictions[player_id_str] = {
                                            'predictions': {},
                                            'player_name': statline['Player'],
                                            'team_abbr': statline['Team']
                                        }
                                    
                                    from prediction_model import Prediction
                                    updated_normalized_predictions[player_id_str]['predictions']['PTS'] = Prediction(
                                        stat='PTS', value=statline['PTS'], confidence='high',
                                        breakdown={'normalized': statline['PTS']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['REB'] = Prediction(
                                        stat='REB', value=statline['REB'], confidence='high',
                                        breakdown={'normalized': statline['REB']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['AST'] = Prediction(
                                        stat='AST', value=statline['AST'], confidence='high',
                                        breakdown={'normalized': statline['AST']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['STL'] = Prediction(
                                        stat='STL', value=statline['STL'], confidence='high',
                                        breakdown={'normalized': statline['STL']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['BLK'] = Prediction(
                                        stat='BLK', value=statline['BLK'], confidence='high',
                                        breakdown={'normalized': statline['BLK']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['TOV'] = Prediction(
                                        stat='TOV', value=statline['TOV'], confidence='high',
                                        breakdown={'normalized': statline['TOV']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['FG3M'] = Prediction(
                                        stat='FG3M', value=statline['FG3M'], confidence='high',
                                        breakdown={'normalized': statline['FG3M']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['FTM'] = Prediction(
                                        stat='FTM', value=statline['FTM'], confidence='high',
                                        breakdown={'normalized': statline['FTM']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['PRA'] = Prediction(
                                        stat='PRA', value=statline['PRA'], confidence='high',
                                        breakdown={'normalized': statline['PRA']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['RA'] = Prediction(
                                        stat='RA', value=statline['RA'], confidence='high',
                                        breakdown={'normalized': statline['RA']}, factors={'source': 'normalized_statline'}
                                    )
                                    updated_normalized_predictions[player_id_str]['predictions']['FPTS'] = Prediction(
                                        stat='FPTS', value=statline['FPTS'], confidence='high',
                                        breakdown={'normalized': statline['FPTS']}, factors={'source': 'normalized_statline'}
                                    )
                            
                            # Get filter values from session state (same as original Value Plays section)
                            min_edge_updated = st.session_state.get('bvp_min_edge', 5)
                            confidence_options_updated = st.session_state.get('bvp_confidence', ['high', 'medium'])
                            stat_options_updated = st.session_state.get('bvp_stats', ['PTS', 'REB', 'AST', 'PRA', 'RA', 'FG3M', 'FTM', 'FPTS'])
                            
                            # Find best value plays using updated predictions
                            updated_best_plays = pm.find_best_value_plays(
                                all_predictions=updated_normalized_predictions,
                                all_props=cached_game_props_updated,
                                min_edge_pct=float(min_edge_updated),
                                confidence_filter=confidence_options_updated if confidence_options_updated else ['high', 'medium', 'low'],
                                stat_filter=stat_options_updated if stat_options_updated else ['PTS', 'REB', 'AST', 'PRA'],
                                injury_adjustments_map=None  # Already normalized, no additional adjustments
                            )
                            
                            # Display updated value plays
                            with st.expander("🎯 **Value Plays (After Manual Adjustments)**", expanded=True):
                                if updated_best_plays:
                                    st.markdown(f"### 🏆 Top {min(len(updated_best_plays), 20)} Value Plays")
                                    
                                    # Sort by absolute edge % descending before taking top 20
                                    sorted_plays = sorted(updated_best_plays, key=lambda x: abs(x['edge_pct']), reverse=True)
                                    
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
                                    def style_lean_updated(row):
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
                                    
                                    styled_plays = display_df.style.apply(style_lean_updated, axis=1)
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
                                        label="📥 Download Value Plays CSV (After Adjustments)",
                                        data=csv_value_plays,
                                        file_name=f"value_plays_updated_{matchup_away_team_abbr}_vs_{matchup_home_team_abbr}_{game_date_str_bvp}.csv",
                                        mime="text/csv",
                                        key="download_value_plays_updated"
                                    )
                                    
                                    # Summary stats
                                    overs = len([p for p in updated_best_plays if 'Over' in p['lean']])
                                    unders = len([p for p in updated_best_plays if 'Under' in p['lean']])
                                    st.caption(f"📈 {overs} Over plays | 📉 {unders} Under plays | Total: {len(updated_best_plays)} plays found")
                                else:
                                    st.info("No plays found matching your filters. Try lowering the minimum edge % or expanding filters.")
                    
                    # Calculate team totals
                    st.markdown("---")
                    st.markdown("### 🏀 Predicted Final Score")
                    
                    # Aggregate points by team (use full statlines_list, not filtered, for accurate totals)
                    statlines_df_full = pd.DataFrame(statlines_list)
                    away_total_pts = statlines_df_full[statlines_df_full['is_away'] == True]['PTS'].sum()
                    home_total_pts = statlines_df_full[statlines_df_full['is_away'] == False]['PTS'].sum()
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
                            predicted_spread_home_perspective = home_total_pts - away_total_pts
                            
                            # Determine which team is favored and calculate spread from favored team's perspective
                            if game_lines_spread < 0:
                                # Home is favored (negative line, e.g., -5.5)
                                favored_team = matchup_home_team_abbr
                                underdog_team = matchup_away_team_abbr
                                
                                if predicted_spread_home_perspective >= 0:
                                    # Home won or tied - spread is negative from favored perspective
                                    predicted_spread_from_favored = -predicted_spread_home_perspective
                                else:
                                    # Home lost (underdog won) - spread is negative from favored perspective
                                    predicted_spread_from_favored = predicted_spread_home_perspective
                                
                                line_from_favored = game_lines_spread  # Already negative (e.g., -5.5)
                                
                                # Determine covering team
                                if predicted_spread_home_perspective >= abs(game_lines_spread):
                                    # Home covers: won by enough
                                    covering_team = favored_team
                                    covering_margin = predicted_spread_home_perspective - abs(game_lines_spread)
                                else:
                                    # Underdog covers: home didn't win by enough or lost
                                    covering_team = underdog_team
                                    if predicted_spread_home_perspective < 0:
                                        # Home lost - underdog covers by line + margin
                                        covering_margin = abs(game_lines_spread) + abs(predicted_spread_home_perspective)
                                    else:
                                        # Home won but didn't cover
                                        covering_margin = abs(game_lines_spread) - predicted_spread_home_perspective
                            else:
                                # Away is favored (positive line, e.g., +5.5)
                                favored_team = matchup_away_team_abbr
                                underdog_team = matchup_home_team_abbr
                                predicted_spread_away_perspective = away_total_pts - home_total_pts
                                
                                if predicted_spread_away_perspective >= 0:
                                    # Away won or tied - spread is negative from favored perspective
                                    predicted_spread_from_favored = -predicted_spread_away_perspective
                                else:
                                    # Away lost (underdog won) - spread is negative from favored perspective
                                    predicted_spread_from_favored = predicted_spread_away_perspective
                                
                                line_from_favored = -abs(game_lines_spread)  # Convert to negative (e.g., -5.5)
                                
                                # Determine covering team
                                if predicted_spread_away_perspective >= abs(game_lines_spread):
                                    # Away covers: won by enough
                                    covering_team = favored_team
                                    covering_margin = predicted_spread_away_perspective - abs(game_lines_spread)
                                else:
                                    # Underdog covers: away didn't win by enough or lost
                                    covering_team = underdog_team
                                    if predicted_spread_away_perspective < 0:
                                        # Away lost - underdog covers by line + margin
                                        covering_margin = abs(game_lines_spread) + abs(predicted_spread_away_perspective)
                                    else:
                                        # Away won but didn't cover
                                        covering_margin = abs(game_lines_spread) - predicted_spread_away_perspective
                            
                            # Format: Show predicted spread from winning team's perspective if underdog wins, otherwise from favored team's perspective
                            if covering_team != favored_team and predicted_spread_from_favored < 0:
                                # Underdog won - show from underdog's perspective
                                # Underdog was +abs(line), won by abs(margin), so spread is +abs(line) + abs(margin)
                                underdog_spread = abs(line_from_favored) + abs(predicted_spread_from_favored)
                                underdog_line = abs(line_from_favored)
                                comparison_lines.append(f"**Spread**: {covering_team} +{underdog_spread:.1f} vs Line +{underdog_line:.1f} ({covering_team} +{abs(predicted_spread_from_favored):.1f}, **{covering_team} covers**)")
                            else:
                                # Favored team covers or won - show from favored team's perspective
                                comparison_lines.append(f"**Spread**: {favored_team} {predicted_spread_from_favored:+.1f} vs Line {line_from_favored:+.1f} ({covering_team} +{covering_margin:.1f}, **{covering_team} covers**)")
                        
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
        st.warning("⚠️ Please select a matchup to generate predictions.")
else:
    st.info("ℹ️ Please select a matchup from the dropdown above to generate predictions.")
