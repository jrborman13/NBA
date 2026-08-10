#!/usr/bin/env python3
"""
Generate Predictions Batch Script
Generates predictions for all games on a given date without using Streamlit app.
Exports predictions to CSV format compatible with optimize_draftkings_nba_lineup.py
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))
sys.path.insert(0, str(project_root / 'combined-app' / 'player_app'))

import pandas as pd
import nba_api.stats.endpoints as endpoints
from datetime import datetime, date
import argparse
import glob
from typing import Dict, List
import pytz

# Import prediction functions
import player_functions as pf
import prediction_model as pm
import minutes_normalization          # shared with 3_Predictions.py (Prediction Parity Rule)
import prediction_store               # writes player_predictions, the table the website reads
import injury_report as ir
import tanking_utils as _tu
import injury_adjustments as inj
import without_player_stats as wps

# Import optimizer functions (optional - only if optimizing)
try:
    from optimize_draftkings_nba_lineup import (
        load_draftables, merge_draftables_with_predictions,
        add_position_flags, optimize_lineup, format_lineup_output
    )
    OPTIMIZER_AVAILABLE = True
except ImportError:
    OPTIMIZER_AVAILABLE = False


def get_matchups_for_date(selected_date: date, season: str = '2025-26'):
    """
    Fetch NBA matchups for a given date from the API.
    
    Args:
        selected_date: Date to get games for
        season: NBA season (default '2025-26')
        
    Returns:
        List of matchup dicts with game info
    """
    try:
        league_schedule = endpoints.ScheduleLeagueV2(
            league_id='00',
            season=season
        ).get_data_frames()[0]
        
        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        league_schedule['matchup'] = league_schedule['awayTeam_teamTricode'] + ' @ ' + league_schedule['homeTeam_teamTricode']
        
        # Compare date parts only
        date_games = league_schedule[
            league_schedule['dateGame'].dt.date == selected_date
        ]
        
        if len(date_games) == 0:
            return []
        
        matchups = []
        for _, row in date_games.iterrows():
            # Extract game time from gameDateTimeUTC (which includes actual tip-off time)
            # Use gameDateTimeUTC as it has the correct tip-off time in UTC
            game_datetime = pd.to_datetime(row['gameDateTimeUTC'])
            # Ensure timezone-aware datetime
            if game_datetime.tzinfo is None:
                game_datetime = pytz.UTC.localize(game_datetime.to_pydatetime())
            else:
                game_datetime = game_datetime.to_pydatetime()
            
            matchups.append({
                'matchup': row['matchup'],
                'away_team': row['awayTeam_teamTricode'],
                'home_team': row['homeTeam_teamTricode'],
                'away_team_id': int(row['awayTeam_teamId']),
                'home_team_id': int(row['homeTeam_teamId']),
                'game_date': selected_date.strftime('%Y-%m-%d'),
                'game_datetime': game_datetime  # Keep full datetime for time grouping
            })
        
        return matchups
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return []


def get_team_roster(team_id: int, players_df: pd.DataFrame) -> List[Dict]:
    """
    Get roster for a specific team.
    
    Args:
        team_id: NBA team ID
        players_df: DataFrame from PlayerIndex
        
    Returns:
        List of player dicts with id, name, team_id
    """
    team_players = players_df[players_df['TEAM_ID'].astype(int) == team_id].copy()
    
    if len(team_players) == 0:
        return []
    
    players = []
    for _, row in team_players.iterrows():
        player_name = f"{row.get('PLAYER_FIRST_NAME', '')} {row.get('PLAYER_LAST_NAME', '')}".strip()
        player_id = str(row['PERSON_ID'])
        players.append({
            'id': player_id,
            'name': player_name,
            'team_id': int(team_id)
        })
    
    return players


def get_player_season_avg_minutes(season: str = '2025-26') -> dict:
    """
    Return a dict of player_id (str) → season-average MPG from LeagueDashPlayerStats.
    Used to determine role tier for tanking minute adjustments.
    """
    try:
        df = endpoints.LeagueDashPlayerStats(
            season=season,
            per_mode_simple='PerGame',
            timeout=90,
        ).get_data_frames()[0]
        return {str(int(row['PLAYER_ID'])): float(row['MIN']) for _, row in df.iterrows()}
    except Exception as e:
        print(f"  ⚠ Could not fetch season avg minutes for tanking adjustment: {e}")
        return {}


def _fetch_bulk_game_logs(season: str = '2025-26') -> pd.DataFrame:
    """
    Fetch all player game logs for the season in one API call.
    Used to provide empirical "without X" data for injury adjustments.
    Returns empty DataFrame on failure.
    """
    try:
        from nba_api.stats.endpoints import PlayerGameLogs
        game_logs = PlayerGameLogs(
            season_nullable=season,
            league_id_nullable='00',
        ).get_data_frames()[0]
        if len(game_logs) > 0:
            game_logs = game_logs[
                game_logs['GAME_ID'].astype(str).str[2].isin(['2', '4', '6'])
            ].copy()
            game_logs['GAME_DATE'] = pd.to_datetime(game_logs['GAME_DATE'])
        return game_logs
    except Exception as e:
        print(f"  ⚠ Could not fetch bulk game logs: {e}")
        return pd.DataFrame()


def generate_predictions_for_date(game_date: date, output_dir: str = None, exclude_injured: bool = True,
                                  optimize_lineups: bool = False, draftables_path: str = None, max_salary: int = 50000,
                                  tipoff_time_filter: str = None, upload: bool = False):
    """
    Generate predictions for all games on a given date.
    
    Args:
        game_date: Date to generate predictions for
        output_dir: Directory to save CSV files (default: ~/Downloads)
        exclude_injured: Whether to exclude injured players (OUT/DOUBTFUL) (default: True)
        optimize_lineups: Whether to optimize lineups after generating predictions (default: False)
        draftables_path: Path to draftables CSV (required if optimize_lineups=True)
        max_salary: Maximum salary for optimization (default: 50000)
        
    Returns:
        List of output file paths
    """
    if output_dir is None:
        output_dir = os.path.expanduser("~/Downloads")
    else:
        os.makedirs(output_dir, exist_ok=True)
    
    print(f"=" * 60)
    print(f"Generating Predictions for {game_date.strftime('%Y-%m-%d')}")
    print(f"=" * 60)
    
    # Get matchups for the date
    print(f"\nFetching schedule...")
    matchups = get_matchups_for_date(game_date)
    
    if len(matchups) == 0:
        print(f"No games found for {game_date.strftime('%Y-%m-%d')}")
        return []
    
    print(f"Found {len(matchups)} game(s)")
    
    # Get players dataframe (needed for rosters)
    print(f"\nLoading player data...")
    players_df = pf.get_players_dataframe()
    if players_df is None or len(players_df) == 0:
        raise ValueError("Could not load players dataframe")
    
    print(f"Loaded {len(players_df)} players")

    # Fetch season-average MPG for tanking minute adjustments (fetched once, shared across games)
    print(f"\nFetching season-average minutes for tanking detection...")
    player_avg_minutes = get_player_season_avg_minutes()
    if player_avg_minutes:
        print(f"  ✓ Loaded avg minutes for {len(player_avg_minutes)} players")

    # Fetch all player game logs once — used for "without X" historical stats lookup
    print(f"\nFetching bulk player game logs for injury context...")
    bulk_game_logs = _fetch_bulk_game_logs()
    if bulk_game_logs is not None and len(bulk_game_logs) > 0:
        print(f"  ✓ Loaded {len(bulk_game_logs)} player game log rows")
    else:
        print(f"  ⚠ Could not load bulk game logs — without-X adjustments will be skipped")

    # Fetch standings once for all games (tanking detection)
    print(f"\nFetching standings for tanking detection...")
    tanking_standings_df = _tu.get_standings()
    if tanking_standings_df is not None:
        print(f"  ✓ Loaded standings ({len(tanking_standings_df)} teams)")
    else:
        print(f"  ⚠ Could not load standings — tanking adjustments will be skipped")

    # Fetch spread for the date (cached per matchup by get_game_spread)
    # (called per-game inside the loop)

    # Fetch injury report for the date (if excluding injured players)
    injury_df = None
    if exclude_injured:
        print(f"\nFetching injury report...")
        injury_df, injury_status = ir.fetch_injuries_for_date(game_date, players_df)
        if injury_df is not None and len(injury_df) > 0:
            print(f"✓ Loaded injury report ({len(injury_df)} entries)")
        else:
            print(f"⚠ No injury report found: {injury_status}")
    else:
        print(f"\n⚠ Injury filtering disabled - all players will be included")
    
    output_files = []
    
    # Check for existing prediction files
    existing_files = {}
    if os.path.exists(output_dir):
        pattern = os.path.join(output_dir, f"predicted_statlines_*_{game_date.strftime('%Y-%m-%d')}.csv")
        existing_prediction_files = glob.glob(pattern)
        for file_path in existing_prediction_files:
            # Extract team abbreviations from filename
            filename = os.path.basename(file_path)
            # Format: predicted_statlines_AWAY_vs_HOME_DATE.csv
            parts = filename.replace('predicted_statlines_', '').replace(f"_{game_date.strftime('%Y-%m-%d')}.csv", '').split('_vs_')
            if len(parts) == 2:
                away_team, home_team = parts
                matchup_key = f"{away_team} @ {home_team}"
                existing_files[matchup_key] = file_path
    
    if existing_files:
        print(f"\nFound {len(existing_files)} existing prediction file(s):")
        for matchup_key, file_path in existing_files.items():
            print(f"  ✓ {matchup_key}: {os.path.basename(file_path)}")
    
    # Process each game
    now_utc = datetime.now(pytz.UTC)
    
    for game_idx, matchup in enumerate(matchups, 1):
        print(f"\n{'=' * 60}")
        print(f"Game {game_idx}/{len(matchups)}: {matchup['matchup']}")
        print(f"{'=' * 60}")
        
        away_team_id = matchup['away_team_id']
        home_team_id = matchup['home_team_id']
        away_team_abbr = matchup['away_team']
        home_team_abbr = matchup['home_team']
        game_date_str = matchup['game_date']
        game_datetime = matchup.get('game_datetime')
        
        # Check if game has already started or finished
        if game_datetime is not None:
            # Ensure game_datetime is timezone-aware
            if isinstance(game_datetime, pd.Timestamp):
                if game_datetime.tzinfo is None:
                    game_datetime = pytz.UTC.localize(game_datetime.to_pydatetime())
                else:
                    game_datetime = game_datetime.to_pydatetime()
            
            # Skip games that have already started (tip-off time is in the past)
            if game_datetime < now_utc:
                print(f"⏭️  Game has already started or finished (tip-off: {game_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')})")
                print(f"  Skipping prediction generation for this game.")
                continue
        
        # Check if prediction file already exists
        matchup_key = f"{away_team_abbr} @ {home_team_abbr}"
        if matchup_key in existing_files:
            existing_file = existing_files[matchup_key]
            print(f"✓ Prediction file already exists: {os.path.basename(existing_file)}")
            print(f"  Skipping prediction generation for this game.")
            output_files.append(existing_file)
            continue
        
        # Get rosters for both teams
        print(f"Getting rosters...")
        away_roster = get_team_roster(away_team_id, players_df)
        home_roster = get_team_roster(home_team_id, players_df)
        
        if len(away_roster) == 0 or len(home_roster) == 0:
            print(f"Warning: Could not get rosters for {matchup['matchup']}")
            continue
        
        print(f"  {away_team_abbr}: {len(away_roster)} players")
        print(f"  {home_team_abbr}: {len(home_roster)} players")
        
        # Get injuries for this matchup (if excluding injured players)
        out_player_ids = set()
        if exclude_injured and injury_df is not None and len(injury_df) > 0:
            matchup_injuries = ir.get_injuries_for_matchup(
                injury_df,
                away_team_abbr,
                home_team_abbr,
                players_df
            )
            
            # Filter OUT/DOUBTFUL players
            for injury_item in matchup_injuries.get('away', []) + matchup_injuries.get('home', []):
                status_lower = injury_item.get('status', '').lower() if injury_item.get('status') else ''
                if 'out' in status_lower or 'doubtful' in status_lower:
                    player_id = injury_item.get('player_id')
                    if player_id:
                        out_player_ids.add(str(player_id))
            
            if out_player_ids:
                print(f"\n⚠ Excluding {len(out_player_ids)} injured players (OUT/DOUBTFUL)")
                for pid in out_player_ids:
                    player_name = next((p['name'] for p in away_roster + home_roster if p['id'] == pid), f"Player {pid}")
                    print(f"  - {player_name}")
        
        # Filter out injured players
        healthy_players = [
            p for p in away_roster + home_roster
            if p['id'] not in out_player_ids
        ]
        
        # Prepare player data for prediction function (only healthy players)
        all_player_ids = [p['id'] for p in healthy_players]
        player_names = {p['id']: p['name'] for p in healthy_players}
        player_team_ids = {p['id']: p['team_id'] for p in healthy_players}
        
        if len(all_player_ids) == 0:
            print(f"Warning: No healthy players for {matchup['matchup']}")
            continue
        
        # Generate predictions for all healthy players in the game
        print(f"\nGenerating predictions for {len(all_player_ids)} healthy players...")
        try:
            def progress_callback(current, total, player_name):
                if current % 5 == 0 or current == total:
                    print(f"  Progress: {current}/{total} ({player_name})")
            
            all_predictions = pm.generate_predictions_for_game(
                player_ids=all_player_ids,
                player_names=player_names,
                player_team_ids=player_team_ids,
                away_team_id=away_team_id,
                home_team_id=home_team_id,
                away_team_abbr=away_team_abbr,
                home_team_abbr=home_team_abbr,
                game_date=game_date_str,
                progress_callback=progress_callback
            )
            
            if len(all_predictions) == 0:
                print(f"Warning: No predictions generated for {matchup['matchup']}")
                continue
            
            print(f"\n✓ Generated predictions for {len(all_predictions)} players")
            
            # Convert to DataFrame format matching Predictions page export
            statlines_list = []
            for player_id, player_data in all_predictions.items():
                predictions = player_data.get('predictions', {})
                player_name = player_data.get('player_name', f"Player {player_id}")
                team_abbr = player_data.get('team_abbr', '')
                
                # Extract FPTS prediction
                fpts_pred = predictions.get('FPTS')
                if fpts_pred is None:
                    continue
                
                fpts_value = fpts_pred.value if hasattr(fpts_pred, 'value') else fpts_pred
                
                # Extract ceiling/floor if available
                ceiling_floor = player_data.get('ceiling_floor', {})
                ceiling_fpts = ceiling_floor.get('ceiling', fpts_value * 1.3) if ceiling_floor else fpts_value * 1.3
                floor_fpts = ceiling_floor.get('floor', fpts_value * 0.7) if ceiling_floor else fpts_value * 0.7
                median_fpts = ceiling_floor.get('median', fpts_value) if ceiling_floor else fpts_value
                variance = ceiling_floor.get('variance', 0.0) if ceiling_floor else 0.0
                std_dev = ceiling_floor.get('std_dev', 0.0) if ceiling_floor else 0.0
                
                # Extract other stats for completeness
                pts = predictions.get('PTS')
                pts_value = pts.value if pts and hasattr(pts, 'value') else 0.0
                
                reb = predictions.get('REB')
                reb_value = reb.value if reb and hasattr(reb, 'value') else 0.0
                
                ast = predictions.get('AST')
                ast_value = ast.value if ast and hasattr(ast, 'value') else 0.0
                
                stl = predictions.get('STL')
                stl_value = stl.value if stl and hasattr(stl, 'value') else 0.0
                
                blk = predictions.get('BLK')
                blk_value = blk.value if blk and hasattr(blk, 'value') else 0.0
                
                tov = predictions.get('TOV')
                tov_value = tov.value if tov and hasattr(tov, 'value') else 0.0
                
                fg3m = predictions.get('FG3M')
                fg3m_value = fg3m.value if fg3m and hasattr(fg3m, 'value') else 0.0
                
                ftm = predictions.get('FTM')
                ftm_value = ftm.value if ftm and hasattr(ftm, 'value') else 0.0
                
                # Calculate PRA
                pra_value = pts_value + reb_value + ast_value
                
                statlines_list.append({
                    'Player': player_name,
                    'Team': team_abbr,
                    'player_id': str(player_id),
                    'is_away': team_abbr == away_team_abbr,
                    # Seeded from season-average MPG exactly as 3_Predictions.py does
                    # (`player_minutes_map.get(int(player_id), 25.0)`); normalize_team_minutes
                    # then scales each team to 240. This was hardcoded 0.0 — "minutes not
                    # predicted in batch mode" — which left batch FPTS un-normalized and made
                    # the rows unuploadable, since the uploader skips MIN <= 0.01.
                    'MIN': float(player_avg_minutes.get(str(player_id), 25.0)),
                    'PTS': round(pts_value, 1),
                    'REB': round(reb_value, 1),
                    'AST': round(ast_value, 1),
                    'STL': round(stl_value, 1),
                    'BLK': round(blk_value, 1),
                    'TOV': round(tov_value, 1),
                    'FG3M': round(fg3m_value, 1),
                    'FTM': round(ftm_value, 1),
                    'PRA': round(pra_value, 1),
                    'FPTS': round(fpts_value, 1),
                    'FPTS_Ceiling': round(ceiling_fpts, 1),
                    'FPTS_Floor': round(floor_fpts, 1),
                    'FPTS_Median': round(median_fpts, 1),
                    'FPTS_Variance': round(variance, 2),
                    'FPTS_StdDev': round(std_dev, 2)
                })
            
            # ── Apply injury adjustments (with "without X" historical blending) ──
            # The prediction model has no knowledge of tonight's injury list, so we
            # apply multipliers here — mirroring what 3_Predictions.py does in the UI.
            if out_player_ids and players_df is not None:
                # Build player_id → average-minutes map from season avg data
                inj_minutes_map = {int(pid): float(mins)
                                   for pid, mins in player_avg_minutes.items()}

                # Build name → player_id lookup
                name_to_pid_inj = {p['name']: p['id'] for p in healthy_players}

                # Team membership maps: team_id → set of player_ids on that team
                away_player_ids_set = {p['id'] for p in healthy_players if p['team_id'] == away_team_id}
                home_player_ids_set = {p['id'] for p in healthy_players if p['team_id'] == home_team_id}
                # Also include the out players so teammate lists are correct
                for p in away_roster:
                    if p['id'] in out_player_ids:
                        away_player_ids_set.add(p['id'])
                for p in home_roster:
                    if p['id'] in out_player_ids:
                        home_player_ids_set.add(p['id'])

                inj_adjusted = 0
                for entry in statlines_list:
                    pid = name_to_pid_inj.get(entry['Player'])
                    if pid is None:
                        continue
                    pid_team = player_team_ids.get(pid)
                    if pid_team is None:
                        continue

                    if pid_team == away_team_id:
                        teammates_out_inj = [p for p in out_player_ids if p in away_player_ids_set and p != pid]
                        opponents_out_inj = [p for p in out_player_ids if p in home_player_ids_set]
                        opp_team_id_inj = home_team_id
                    else:
                        teammates_out_inj = [p for p in out_player_ids if p in home_player_ids_set and p != pid]
                        opponents_out_inj = [p for p in out_player_ids if p in away_player_ids_set]
                        opp_team_id_inj = away_team_id

                    if not teammates_out_inj and not opponents_out_inj:
                        continue

                    # Compute "without X" historical multipliers
                    wp_stats = None
                    if teammates_out_inj and bulk_game_logs is not None and len(bulk_game_logs) > 0:
                        try:
                            wp_stats = wps.get_without_player_stats(
                                player_id=pid,
                                absent_player_ids=list(teammates_out_inj),
                                bulk_game_logs=bulk_game_logs,
                            )
                        except Exception:
                            wp_stats = None

                    try:
                        injury_adj = inj.calculate_injury_adjustments(
                            player_id=pid,
                            player_team_id=int(pid_team),
                            opponent_team_id=opp_team_id_inj,
                            teammates_out=list(teammates_out_inj),
                            opponents_out=list(opponents_out_inj),
                            player_minutes_map=inj_minutes_map,
                            players_df=players_df,
                            without_player_stats=wp_stats,
                        )
                    except Exception:
                        continue

                    if not injury_adj.get('factors'):
                        continue

                    stat_cols = {
                        'PTS': 'PTS', 'REB': 'REB', 'AST': 'AST',
                        'STL': 'STL', 'BLK': 'BLK', 'FG3M': 'FG3M', 'FTM': 'FTM',
                    }
                    for stat, col in stat_cols.items():
                        mult = injury_adj.get(stat, 1.0)
                        if col in entry:
                            entry[col] = round(entry[col] * mult, 1)

                    # Recalculate derived columns
                    entry['PRA'] = round(entry['PTS'] + entry['REB'] + entry['AST'], 1)

                    # Recompute FPTS using DK scoring: PTS*1 + REB*1.25 + AST*1.5 + STL*2 + BLK*2 + FG3M*0.5 - TOV*0.5 + FTM*0
                    new_fpts = (entry['PTS'] * 1.0 + entry['REB'] * 1.25 + entry['AST'] * 1.5
                                + entry['STL'] * 2.0 + entry['BLK'] * 2.0 + entry.get('FG3M', 0) * 0.5
                                - entry.get('TOV', 0) * 0.5)
                    fpts_scale = new_fpts / entry['FPTS'] if entry['FPTS'] > 0 else 1.0
                    for col in ('FPTS', 'FPTS_Ceiling', 'FPTS_Floor', 'FPTS_Median'):
                        if col in entry:
                            entry[col] = round(entry[col] * fpts_scale, 1)
                    inj_adjusted += 1

                if inj_adjusted:
                    print(f"  💊 Injury adjustments applied to {inj_adjusted} players "
                          f"({len(out_player_ids)} teammate(s) out)")

            # Apply tanking minute adjustments (scale stats proportionally)
            if tanking_standings_df is not None and player_avg_minutes:
                # Build minimal statlines for tanking detection
                tank_statlines = []
                for entry in statlines_list:
                    player_name = entry['Player']
                    # Find the player_id that maps to this name
                    pid = next(
                        (p['id'] for p in healthy_players if p['name'] == player_name),
                        None
                    )
                    if pid is None:
                        continue
                    baseline_min = player_avg_minutes.get(str(pid), 0.0)
                    if baseline_min <= 0:
                        continue
                    is_away = player_team_ids.get(pid) == away_team_id
                    tank_statlines.append({
                        'player_id': str(pid),
                        'is_away': is_away,
                        '_original_season_minutes': baseline_min,
                        'MIN': baseline_min,
                    })

                if tank_statlines:
                    spread = _tu.get_game_spread(away_team_abbr, home_team_abbr)
                    tank_adj, tank_ctx = _tu.compute_tanking_adjustments(
                        tank_statlines,
                        away_team_id, home_team_id,
                        away_team_abbr, home_team_abbr,
                        standings_df=tanking_standings_df,
                        spread=spread,
                    )
                    if tank_adj:
                        # Build a name → pid lookup for scaling
                        name_to_pid = {p['name']: p['id'] for p in healthy_players}
                        scaled = 0
                        for entry in statlines_list:
                            pid = name_to_pid.get(entry['Player'])
                            if pid is None or str(pid) not in tank_adj:
                                continue
                            baseline_min = player_avg_minutes.get(str(pid), 0.0)
                            adjusted_min = tank_adj[str(pid)]
                            if baseline_min <= 0:
                                continue
                            scale = adjusted_min / baseline_min
                            for col in ('FPTS', 'PTS', 'REB', 'AST', 'STL',
                                        'BLK', 'TOV', 'FG3M', 'FTM', 'PRA',
                                        'FPTS_Ceiling', 'FPTS_Floor',
                                        'FPTS_Median'):
                                if col in entry:
                                    entry[col] = round(entry[col] * scale, 1)
                            scaled += 1

                        away_t = tank_ctx.get('away_tanking')
                        home_t = tank_ctx.get('home_tanking')
                        if away_t or home_t:
                            label = f"{away_team_abbr}={'hard' if away_t == 'hard' else away_t or 'ok'} / {home_team_abbr}={'hard' if home_t == 'hard' else home_t or 'ok'}"
                            mult_pct = int(tank_ctx.get('spread_mult', 0) * 100)
                            print(f"  📉 Tanking adjustments applied ({label}, spread={tank_ctx.get('spread')}, mult={mult_pct}%): {scaled} players scaled")

            # Normalize each team to 240 minutes using the SAME shared function the
            # Predictions page calls (Prediction Parity Rule). Runs after the injury and
            # tanking adjustments above, matching the page's ordering.
            # NOTE: the page passes its tanking deltas in as `manual_adjustments`; this
            # script has already applied tanking to the statlines directly, so passing them
            # again here would double-count.
            minutes_normalization.normalize_team_minutes(
                statlines_list,
                target_minutes=240.0,
                out_player_ids=out_player_ids,
                bulk_game_logs=bulk_game_logs,
                game_date=game_date_str,
            )

            # Create DataFrame
            predictions_df = pd.DataFrame(statlines_list)
            
            # Save to CSV
            output_filename = f"predicted_statlines_{away_team_abbr}_vs_{home_team_abbr}_{game_date_str}.csv"
            output_path = os.path.join(output_dir, output_filename)
            predictions_df.to_csv(output_path, index=False)
            
            print(f"\n✓ Saved predictions to: {output_path}")
            print(f"  Total players: {len(predictions_df)}")
            print(f"  Average FPTS: {predictions_df['FPTS'].mean():.2f}")

            # Headless write to Supabase. Until now the ONLY writer of player_predictions
            # was the Streamlit UI, so the table only held dates somebody happened to open.
            if upload:
                cf_map = {
                    sl['player_id']: {
                        'ceiling':  sl.get('FPTS_Ceiling'),
                        'floor':    sl.get('FPTS_Floor'),
                        'median':   sl.get('FPTS_Median'),
                        'std_dev':  sl.get('FPTS_StdDev'),
                    }
                    for sl in statlines_list if sl.get('player_id')
                }
                ok = prediction_store.upload_game_predictions(
                    game_date_str, away_team_abbr, home_team_abbr, statlines_list, cf_map,
                )
                if ok:
                    uploaded = sum(1 for sl in statlines_list if float(sl.get('MIN', 0)) > 0.01)
                    print(f"  ☁ Uploaded {uploaded} players to Supabase (player_predictions)")
                else:
                    # Fail loud: a silent no-op here is exactly how this table went stale.
                    print("  ✗ Supabase upload FAILED (check SUPABASE_URL / SUPABASE_SERVICE_KEY)")

            output_files.append(output_path)
            
        except Exception as e:
            print(f"\n✗ Error generating predictions for {matchup['matchup']}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Count new vs existing files
    existing_count = sum(1 for f in output_files if f in existing_files.values())
    new_count = len(output_files) - existing_count
    
    print(f"\n{'=' * 60}")
    print(f"Summary")
    print(f"{'=' * 60}")
    print(f"Games processed: {len(matchups)}")
    print(f"Files found (existing): {existing_count}")
    print(f"Files created (new): {new_count}")
    print(f"Total files: {len(output_files)}")
    print(f"\nOutput files:")
    for f in output_files:
        file_type = "(existing)" if f in existing_files.values() else "(new)"
        print(f"  - {f} {file_type}")
    
    # Optimize lineups if requested
    if optimize_lineups:
        if not OPTIMIZER_AVAILABLE:
            print(f"\n⚠ Warning: Optimizer not available. Skipping lineup optimization.")
        elif not draftables_path or not os.path.exists(draftables_path):
            print(f"\n⚠ Warning: Draftables file not found: {draftables_path}")
            print(f"  Skipping lineup optimization.")
        else:
            print(f"\n{'=' * 60}")
            print(f"Optimizing Lineups by Tip-Off Wave")
            print(f"{'=' * 60}")
            
            try:
                # Import the wave optimizer
                optimizer_script_path = Path(__file__).parent / 'optimize_lineups_by_wave.py'
                if optimizer_script_path.exists():
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("optimize_lineups_by_wave", optimizer_script_path)
                    optimize_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(optimize_module)
                    
                    optimized_files = optimize_module.optimize_lineups_by_wave(
                        game_date,
                        draftables_path,
                        predictions_dir=output_dir,
                        output_dir=output_dir,
                        tipoff_time_filter=tipoff_time_filter
                    )
                else:
                    print(f"⚠ Warning: optimize_lineups_by_wave.py not found. Skipping optimization.")
                    optimized_files = []
                
                if optimized_files:
                    print(f"\n✓ Successfully optimized {len(optimized_files)} lineup(s)")
                else:
                    print(f"\n⚠ No optimized lineups generated")
                    
            except Exception as e:
                print(f"\n✗ Error optimizing lineups: {e}")
                import traceback
                traceback.print_exc()
    
    return output_files


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Generate predictions for all NBA games on a given date',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate predictions for today (default)
  python generate_predictions_batch.py
  
  # Generate predictions and optimize lineups automatically
  python generate_predictions_batch.py --optimize --draftables ~/Downloads/draftkings_draftables_140610.csv
  
  # Generate predictions and optimize for a specific tip-off time only
  python generate_predictions_batch.py --optimize --draftables draftables.csv --tipoff-time "6:00 PM CT"
  
  # Generate predictions for a specific date with optimization
  python generate_predictions_batch.py --date 2025-01-15 --optimize --draftables draftables.csv
        """
    )
    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='Date to generate predictions for (YYYY-MM-DD format). Defaults to today if not specified.'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output directory for CSV files (default: current directory)'
    )
    parser.add_argument(
        '--upload',
        action='store_true',
        help='Also upsert predictions into Supabase player_predictions (the table the '
             'website reads). Requires SUPABASE_URL + SUPABASE_SERVICE_KEY. Without this '
             'flag the script only writes CSV, which is why the table previously only held '
             'dates that were opened in the Streamlit UI.'
    )
    parser.add_argument(
        '--season',
        type=str,
        default='2025-26',
        help='NBA season (default: 2025-26)'
    )
    parser.add_argument(
        '--include-injured',
        action='store_true',
        help='Include injured players (OUT/DOUBTFUL) in predictions (default: exclude them)'
    )
    parser.add_argument(
        '--optimize',
        action='store_true',
        help='Automatically optimize lineups after generating predictions (requires --draftables)'
    )
    parser.add_argument(
        '--draftables',
        type=str,
        default=None,
        help='Path to draftables CSV file (required if --optimize is used)'
    )
    parser.add_argument(
        '--max-salary',
        type=int,
        default=50000,
        help='Maximum salary for lineup optimization (default: 50000)'
    )
    parser.add_argument(
        '--tipoff-time',
        type=str,
        default=None,
        help='Filter to specific tip-off time when optimizing (e.g., "6:00 PM CT", "7:30 PM CT"). If not specified, optimizes all waves.'
    )
    
    args = parser.parse_args()
    
    # Parse date (default to today if not provided)
    if args.date is None:
        game_date = date.today()
        print(f"Using today's date: {game_date.strftime('%Y-%m-%d')}")
    else:
        try:
            game_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD format.")
            sys.exit(1)
    
    # Validate optimizer arguments
    if args.optimize and not args.draftables:
        print("Error: --draftables is required when using --optimize")
        sys.exit(1)
    
    if args.optimize and args.draftables and not os.path.exists(args.draftables):
        print(f"Error: Draftables file not found: {args.draftables}")
        sys.exit(1)
    
    # Generate predictions
    try:
        exclude_injured = not args.include_injured
        output_files = generate_predictions_for_date(
            game_date, 
            args.output, 
            exclude_injured=exclude_injured,
            optimize_lineups=args.optimize,
            draftables_path=args.draftables,
            max_salary=args.max_salary,
            tipoff_time_filter=args.tipoff_time,
            upload=args.upload,
        )
        
        if len(output_files) == 0:
            print("\nNo predictions generated.")
            sys.exit(1)
        else:
            print(f"\n✓ Successfully generated {len(output_files)} prediction file(s)")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
