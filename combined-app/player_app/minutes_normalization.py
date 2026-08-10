"""
Minute normalization — shared by the Predictions page and the headless batch script.

Extracted verbatim from combined-app/pages/3_Predictions.py on 2026-08-09.

WHY IT LIVES HERE: the Prediction Parity Rule (NBA/CLAUDE.md) requires any factor
affecting predicted FPTS to be applied in BOTH 3_Predictions.py and
scripts/generate_predictions_batch.py, with the shared logic under player_app/.
Minutes are the single biggest driver of fantasy output, and this function used to
exist only inside the Streamlit page — so batch-mode predictions were never
minute-normalized and did not match the UI. Importing a page is not possible
(module-level Streamlit code executes on import), hence the extraction.

Self-contained: no Streamlit imports, pandas is the only dependency.
"""

import pandas as pd


def normalize_team_minutes(statlines_list, target_minutes=240.0, out_player_ids=None, bulk_game_logs=None, game_date=None, manual_adjustments=None, returning_player_ids=None):
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
        
        # 2. Activity filter + recent-form projection
        #
        # Solution 1: Replace calendar-day cutoffs with team-games-based check.
        #   A player must have 2+ qualifying appearances (8+ min) in the team's
        #   last 8 games to be considered active. This cleanly handles players
        #   who haven't been in the rotation for weeks regardless of calendar dates,
        #   and ignores garbage-time cameos (< 8 min).
        #
        # Solution 2: For active players, project minutes from recent form rather
        #   than anchoring to the season average:
        #   - 5 most-recent games available  →  recent_avg × 0.85 + season_avg × 0.15
        #   - 3–4 most-recent games          →  recent_avg × 0.70 + season_avg × 0.30
        #   - < 3 recent games               →  season_avg (unchanged)
        #
        # Solution 4: After projecting, update _role_baseline_min to the projected
        #   value so that tier assignment (and therefore floors/caps) reflects
        #   current role rather than the stale season average.
        active_player_ids = set()
        if bulk_game_logs is not None and len(bulk_game_logs) > 0 and game_date:
            try:
                game_date_dt = pd.to_datetime(game_date)

                # ── Identify team's last 8 game IDs ──────────────────────────
                team_id_for_filter = None
                for _sl in team_statlines:
                    _pid_str = _sl.get('player_id')
                    if not _pid_str:
                        continue
                    try:
                        _pid_int = int(_pid_str)
                        _p_logs = bulk_game_logs[
                            (bulk_game_logs['PLAYER_ID'] == _pid_int) &
                            (pd.to_datetime(bulk_game_logs['GAME_DATE']) < game_date_dt)
                        ]
                        if len(_p_logs) > 0:
                            team_id_for_filter = int(_p_logs['TEAM_ID'].iloc[0])
                            break
                    except Exception:
                        continue

                last_8_game_ids = set()
                if team_id_for_filter is not None:
                    _t_logs = bulk_game_logs[
                        (bulk_game_logs['TEAM_ID'] == team_id_for_filter) &
                        (pd.to_datetime(bulk_game_logs['GAME_DATE']) < game_date_dt)
                    ]
                    last_8_game_ids = set(
                        _t_logs.sort_values('GAME_DATE', ascending=False)['GAME_ID'].unique()[:8]
                    )

                # ── Per-player: activity check + recent-form projection ───────
                for statline in team_statlines:
                    player_id_str = statline.get('player_id')
                    if not player_id_str:
                        continue
                    try:
                        player_id_int = int(player_id_str)
                        all_player_logs = bulk_game_logs[
                            bulk_game_logs['PLAYER_ID'] == player_id_int
                        ]

                        # No game logs at all this season → exclude
                        if len(all_player_logs) == 0:
                            statline['MIN'] = 0.0
                            statline['_excluded_no_games'] = True
                            continue

                        # Count qualifying appearances (8+ min) in last 8 team games
                        qualifying_count = 0
                        if last_8_game_ids:
                            _in_last_8 = all_player_logs[
                                all_player_logs['GAME_ID'].isin(last_8_game_ids)
                            ]
                            qualifying_count = int((_in_last_8['MIN'] >= 8).sum())

                        # ── Returning-from-absence ramp-up detection ────────
                        # Detect from game logs: find the most recent gap of 5+
                        # team games, then count games played since returning.
                        # Option B ramp tables keyed by (absence_tier, role_tier).
                        _RAMP_B = {
                            # absence 5-10 games
                            'short': {
                                'star':       [0.78, 0.90, 1.00],
                                'starter':    [0.72, 0.85, 0.95],
                                'rotation':   [0.68, 0.80, 0.90],
                                'bench':      [0.60, 0.72, 0.82],
                                'deep_bench': [0.50, 0.58, 0.65],
                            },
                            # absence 11-20 games
                            'medium': {
                                'star':       [0.68, 0.78, 0.88, 0.95, 1.00],
                                'starter':    [0.62, 0.72, 0.82, 0.90, 0.97],
                                'rotation':   [0.55, 0.65, 0.75, 0.85, 0.92],
                                'bench':      [0.48, 0.55, 0.63, 0.70, 0.78],
                                'deep_bench': [0.38, 0.43, 0.50, 0.55, 0.60],
                            },
                            # absence 21+ games
                            'long': {
                                'star':       [0.58, 0.68, 0.78, 0.85, 0.92, 1.00],
                                'starter':    [0.52, 0.62, 0.72, 0.80, 0.87, 0.95],
                                'rotation':   [0.45, 0.55, 0.65, 0.73, 0.82, 0.90],
                                'bench':      [0.38, 0.45, 0.52, 0.58, 0.65, 0.72],
                                'deep_bench': [0.28, 0.33, 0.40, 0.45, 0.50, 0.55],
                            },
                        }

                        def _detect_ramp(player_logs_before_game, team_id, bulk_logs, gd_dt):
                            """Detect if a player is ramping back from an absence.
                            Returns (games_missed, games_back, pre_injury_baseline) or None."""
                            _pl = player_logs_before_game.sort_values('GAME_DATE', ascending=False)
                            if len(_pl) == 0:
                                return None
                            _pl_dates = pd.to_datetime(_pl['GAME_DATE'])

                            # Get all team game dates before game_date
                            if team_id is None:
                                return None
                            _team_dates = (
                                bulk_logs[
                                    (bulk_logs['TEAM_ID'] == team_id) &
                                    (pd.to_datetime(bulk_logs['GAME_DATE']) < gd_dt)
                                ]
                                .drop_duplicates('GAME_ID')
                                .sort_values('GAME_DATE', ascending=False)
                            )
                            _team_game_dates = pd.to_datetime(_team_dates['GAME_DATE']).tolist()
                            if len(_team_game_dates) < 2:
                                return None

                            # Walk backward through player's games to find a gap
                            for i in range(len(_pl) - 1):
                                _cur = _pl_dates.iloc[i]
                                _prev = _pl_dates.iloc[i + 1]
                                # Count team games between these two player appearances
                                _team_between = sum(1 for td in _team_game_dates if _prev < td < _cur)
                                if _team_between >= 5:
                                    # Found a significant gap
                                    _games_missed = _team_between
                                    _games_back = i + 1  # how many games played since return (includes most recent)

                                    # Pre-injury baseline: avg of last 5 qualifying games before the gap
                                    _before_gap = _pl.iloc[i + 1:]  # games at and before the gap start
                                    _qual = _before_gap[_before_gap['MIN'] >= 8].head(5)
                                    # Require at least 3 qualifying games to confirm rotation status
                                    if len(_qual) < 3:
                                        return None
                                    _baseline = float(_qual['MIN'].mean())
                                    # Minimum 18 MPG baseline — below this is fringe rotation, not worth ramping
                                    if _baseline < 18:
                                        return None
                                    # Check post-return minutes: if avg < 10 min since coming back,
                                    # the player isn't actually back in rotation
                                    _post_return = _pl.iloc[:i + 1]  # games since return
                                    if len(_post_return) > 0 and float(_post_return['MIN'].mean()) < 10:
                                        return None
                                    return (_games_missed, _games_back, _baseline)
                            return None

                        _ramp_result = _detect_ramp(
                            all_player_logs[pd.to_datetime(all_player_logs['GAME_DATE']) < game_date_dt],
                            team_id_for_filter, bulk_game_logs, game_date_dt,
                        )

                        # Also check injury report for players returning TODAY (no games back yet)
                        _ret_ids_norm = {str(x) for x in (returning_player_ids or [])}
                        _is_returning_today = str(player_id_str) in _ret_ids_norm if _ret_ids_norm else False

                        if _ramp_result is not None or (_is_returning_today and qualifying_count < 2):
                            if _ramp_result:
                                _games_missed, _games_back, _pre_inj_baseline = _ramp_result
                            else:
                                # Returning today — 0 games back, estimate from logs
                                _games_back = 0
                                _pre_inj = (
                                    all_player_logs[
                                        (all_player_logs['MIN'] >= 8) &
                                        (pd.to_datetime(all_player_logs['GAME_DATE']) < game_date_dt)
                                    ].sort_values('GAME_DATE', ascending=False).head(5)
                                )
                                if len(_pre_inj) > 0:
                                    _pre_inj_baseline = float(_pre_inj['MIN'].mean())
                                    _last_qual_date = pd.to_datetime(_pre_inj.iloc[0]['GAME_DATE'])
                                    if team_id_for_filter is not None:
                                        _games_missed = int(bulk_game_logs[
                                            (bulk_game_logs['TEAM_ID'] == team_id_for_filter) &
                                            (pd.to_datetime(bulk_game_logs['GAME_DATE']) > _last_qual_date) &
                                            (pd.to_datetime(bulk_game_logs['GAME_DATE']) < game_date_dt)
                                        ]['GAME_ID'].nunique())
                                    else:
                                        _games_missed = 10
                                else:
                                    _pre_inj_baseline = statline.get('_role_baseline_min', statline['MIN'])
                                    _games_missed = 15

                            # Only apply ramp if still within the ramp window
                            if _games_missed >= 5:
                                # Determine absence tier
                                if _games_missed <= 10:
                                    _abs_tier = 'short'
                                elif _games_missed <= 20:
                                    _abs_tier = 'medium'
                                else:
                                    _abs_tier = 'long'

                                # Determine role tier from pre-injury baseline
                                if _pre_inj_baseline >= 32:
                                    _role_tier = 'star'
                                elif _pre_inj_baseline >= 28:
                                    _role_tier = 'starter'
                                elif _pre_inj_baseline >= 22:
                                    _role_tier = 'rotation'
                                elif _pre_inj_baseline >= 15:
                                    _role_tier = 'bench'
                                else:
                                    _role_tier = 'deep_bench'

                                _ramp_table = _RAMP_B[_abs_tier][_role_tier]
                                # _games_back is 0-indexed for today's game (returning today)
                                # or 1+ for games already played since return
                                _ramp_idx = _games_back  # game 1 back = index 0, game 2 = index 1, etc.
                                if _ramp_idx < len(_ramp_table):
                                    _restriction = _ramp_table[_ramp_idx]
                                    _projected_return = max(round(_pre_inj_baseline * _restriction, 1), 5.0)
                                    statline['MIN'] = _projected_return
                                    statline['_injury_adjusted_minutes'] = _projected_return
                                    statline['_injury_return_estimate'] = True
                                    statline['_injury_return_games_missed'] = _games_missed
                                    statline['_injury_return_games_back'] = _games_back
                                    statline['_injury_return_baseline'] = round(_pre_inj_baseline, 1)
                                    statline['_injury_return_role'] = _role_tier
                                    statline['_injury_return_ramp_pct'] = round(_restriction * 100)
                                    statline['_role_baseline_min'] = _pre_inj_baseline
                                    active_player_ids.add(player_id_str)
                                    continue
                                # else: past ramp window, fall through to normal handling

                        if qualifying_count < 2:
                            # Not in rotation (includes garbage-time-only cameos)
                            # and not a returning player
                            statline['MIN'] = 0.0
                            statline['_excluded_inactive'] = True
                            continue

                        active_player_ids.add(player_id_str)

                        # ── Recent-form projection (Solution 2) ──────────────
                        season_avg = statline.get('_role_baseline_min', statline['MIN'])
                        recent_5 = (
                            all_player_logs[
                                pd.to_datetime(all_player_logs['GAME_DATE']) < game_date_dt
                            ]
                            .sort_values('GAME_DATE', ascending=False)
                            .head(5)
                        )

                        if len(recent_5) >= 5:
                            recent_avg = float(recent_5['MIN'].mean())
                            projected = round(recent_avg * 0.85 + season_avg * 0.15, 1)
                        elif len(recent_5) >= 3:
                            recent_avg = float(recent_5['MIN'].mean())
                            projected = round(recent_avg * 0.70 + season_avg * 0.30, 1)
                        else:
                            projected = season_avg

                        # Floor: at least 1 min so player stays in the active pool
                        projected = max(projected, 1.0)

                        # Flag meaningful role changes for visibility
                        if projected > season_avg * 1.15 and (projected - season_avg) >= 3.0:
                            statline['_role_change_boosted'] = True

                        statline['MIN'] = projected
                        statline['_injury_adjusted_minutes'] = projected

                        # Solution 4: re-tier by updating _role_baseline_min so that
                        # tier-based floors and caps use the projected role, not the
                        # stale season average (e.g. Hyland at 24 proj → rotation tier,
                        # not bench tier capped at 25).
                        # Skip for injury-return players — their _role_baseline_min is
                        # already set to their pre-injury level above.
                        if not statline.get('_injury_return_estimate'):
                            statline['_role_baseline_min'] = projected

                    except (ValueError, TypeError):
                        continue

            except Exception:
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

            # Large penalty for players excluded by the inactivity filter (e.g., Conley who
            # hasn't played in months). This ensures they lose out to any active player when
            # the minimum-player enforcement slot-fills.
            inactive_penalty = -50 if statline.get('_excluded_inactive') else 0

            return (role_priority + recent_activity_boost + inactive_penalty, current_min)
        
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
            inactive_players = [s for s in team_statlines if s.get('MIN', 0) <= 0.01 and not s.get('_excluded_no_games', False) and not s.get('_excluded_inactive', False)]
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
            inactive_players = [s for s in team_statlines if s.get('MIN', 0) <= 0.01 and not s.get('_excluded_no_games', False) and not s.get('_excluded_inactive', False)]
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

        # Detect returning stars on this team — their teammates need a usage
        # compression discount because the ML model's base predictions reflect
        # the inflated role those teammates had while the stars were out.
        returning_star_mins = sum(
            s.get('_injury_return_baseline', 0)
            for s in team_statlines
            if s.get('_injury_return_estimate') and s.get('_injury_return_baseline', 0) >= 28
        )
        # Usage compression: 0% when no stars returning, up to ~12% when 90+ star
        # minutes are returning (e.g. 3 stars coming back at once).
        # This is the inverse of the usage *boost* teammates got while stars were out.
        if returning_star_mins > 0:
            usage_compression = max(0.88, 1.0 - returning_star_mins / 240 * 0.40)
        else:
            usage_compression = 1.0

        # Total minutes from injured players — used to reduce diminishing-returns
        # penalty when the team is severely shorthanded
        total_injured_mins = sum(injured_minutes_by_role.values())
        # Scaling elasticity: 0.80 baseline, up to 0.95 when 90+ mins are missing.
        # When 3+ guys are out the remaining players produce near-proportionally
        # to their extra minutes — the "diminishing returns" assumption breaks down.
        scaling_elasticity = 0.80 + max(0.0, min(0.15, (total_injured_mins - 30) / 60 * 0.15))

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
                # Scale stats proportionally with diminishing returns.
                # Elasticity is 0.80 baseline, rising toward 0.92 when 90+ team
                # minutes are missing — reduces under-bias in shorthanded games.
                stat_scaling_factor = 1.0 + (minutes_ratio - 1.0) * scaling_elasticity
                
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
            
            # Step 1a: Usage compression for teammates of returning stars.
            # When stars return, their teammates lose touches/usage back to them.
            # The ML base predictions were trained on recent games without the
            # stars, so they're inflated.  Apply inverse-usage discount.
            if usage_compression < 1.0 and not statline.get('_injury_return_estimate'):
                scaled_pts *= usage_compression
                scaled_ast *= usage_compression
                scaled_fg3m *= usage_compression
                scaled_ftm *= usage_compression
                # Rebounds less affected by usage (more about positioning)
                reb_compression = 1.0 - (1.0 - usage_compression) * 0.4
                scaled_reb *= reb_compression
                # STL/BLK not usage-dependent
                # TOV slightly reduced (fewer touches = fewer turnovers)
                scaled_tov *= usage_compression

            # Step 1b: Efficiency discount for players returning from injury.
            # The ramp tables reduce minutes, but returning players are also less
            # efficient per minute (rust, conditioning, timing).  Discount scales
            # with the ramp percentage — earlier in the ramp = bigger discount.
            if statline.get('_injury_return_estimate'):
                ramp_pct = statline.get('_injury_return_ramp_pct', 100) / 100.0  # e.g. 0.58
                games_back = statline.get('_injury_return_games_back', 0)
                games_missed = statline.get('_injury_return_games_missed', 0)
                # Efficiency discount: ranges from ~0.82 (first game, long absence)
                # to 1.0 (fully ramped).  Uses ramp_pct as the anchor — if you're
                # only getting 58% of your minutes, your per-minute efficiency is
                # also dampened, just not as severely.
                # Formula: midpoint between ramp_pct and 1.0, biased toward 1.0
                eff_discount = 0.5 * (1.0 + ramp_pct)  # e.g. 0.58 -> 0.79, 0.78 -> 0.89, 0.92 -> 0.96
                # Floor at 0.80 — even the rustiest star doesn't lose 20%+ per-minute efficiency
                eff_discount = max(0.80, eff_discount)
                scaled_pts *= eff_discount
                scaled_reb *= eff_discount
                scaled_ast *= eff_discount
                scaled_stl *= eff_discount
                scaled_blk *= eff_discount
                scaled_tov *= eff_discount
                scaled_fg3m *= eff_discount
                scaled_ftm *= eff_discount

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
