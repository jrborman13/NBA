#!/usr/bin/env python3
"""
Fetch NBA Game Logs from Sportradar API and Store in Supabase
Fetches player and team game logs using Daily Summaries and stores in sr_game_logs table.
"""

import sys
import os
from pathlib import Path
import json

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))

import pandas as pd
from sportradar_config import (
    fetch_sportradar_nba, is_sportradar_configured,
    get_sportradar_nba_url, SPORTRADAR_NBA_BASE_URL, SPORTRADAR_NBA_VERSION, SPORTRADAR_NBA_API_KEY
)
from supabase_config import get_supabase_service_client
from datetime import datetime, UTC, timedelta
import time
import requests
from sportradar_data_reader import get_schedule_from_db

CURRENT_SEASON = '2025-26'
SEASON_TYPE = 'Regular Season'

# Debug logging setup
DEBUG_LOG_PATH = project_root / '.cursor' / 'debug.log'

def debug_log(session_id, run_id, hypothesis_id, location, message, data):
    """Write debug log entry"""
    try:
        log_entry = {
            "sessionId": session_id,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(datetime.now(UTC).timestamp() * 1000)
        }
        with open(DEBUG_LOG_PATH, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception:
        pass  # Silently fail if logging fails

def extract_player_game_logs_from_boxscore(boxscore_data):
    """
    Extract player game logs from Sportradar box score response.
    
    Args:
        boxscore_data: Sportradar API box score response (game data is at root level)
    
    Returns:
        List of player game log dictionaries
    """
    player_logs = []
    
    # Boxscore response has game data at root level, not nested under 'game'
    game = boxscore_data
    game_id = game.get('id', '')
    game_date = game.get('scheduled', '')
    
    # Extract home team player stats
    # Note: Boxscore may have 'leaders' instead of full 'players' list
    # We'll extract from 'leaders' if 'players' is not available
    if 'home' in game:
        home = game['home']
        team_id = home.get('id', '')
        team_abbr = home.get('alias', '')
        
        # Try to get full players list first
        if 'players' in home:
            players = home['players']
        elif 'leaders' in home:
            # Extract from leaders (points, rebounds, assists)
            players = []
            for category in ['points', 'rebounds', 'assists']:
                if category in home['leaders']:
                    players.extend(home['leaders'][category])
            # Deduplicate by player ID
            seen_ids = set()
            unique_players = []
            for player in players:
                player_id = player.get('id', '')
                if player_id and player_id not in seen_ids:
                    seen_ids.add(player_id)
                    unique_players.append(player)
            players = unique_players
        else:
            players = []
        
        for player in players:
            player_log = {
                'GAME_ID': game_id,
                'GAME_DATE': game_date,
                'TEAM_ID': team_id,
                'TEAM_ABBREVIATION': team_abbr,
                'PLAYER_ID': player.get('id', ''),
                'PLAYER_NAME': player.get('full_name', ''),
            }
            
            # Add all statistics fields
            stats = player.get('statistics', {})
            if stats:
                player_log.update(stats)
            
            player_logs.append(player_log)
    
    # Extract away team player stats
    if 'away' in game:
        away = game['away']
        team_id = away.get('id', '')
        team_abbr = away.get('alias', '')
        
        # Try to get full players list first
        if 'players' in away:
            players = away['players']
        elif 'leaders' in away:
            # Extract from leaders (points, rebounds, assists)
            players = []
            for category in ['points', 'rebounds', 'assists']:
                if category in away['leaders']:
                    players.extend(away['leaders'][category])
            # Deduplicate by player ID
            seen_ids = set()
            unique_players = []
            for player in players:
                player_id = player.get('id', '')
                if player_id and player_id not in seen_ids:
                    seen_ids.add(player_id)
                    unique_players.append(player)
            players = unique_players
        else:
            players = []
        
        for player in players:
            player_log = {
                'GAME_ID': game_id,
                'GAME_DATE': game_date,
                'TEAM_ID': team_id,
                'TEAM_ABBREVIATION': team_abbr,
                'PLAYER_ID': player.get('id', ''),
                'PLAYER_NAME': player.get('full_name', ''),
            }
            
            # Add all statistics fields
            stats = player.get('statistics', {})
            if stats:
                player_log.update(stats)
            
            player_logs.append(player_log)
    
    return player_logs


def extract_team_game_logs_from_boxscore(boxscore_data):
    """
    Extract team game logs from Sportradar box score response.
    
    Args:
        boxscore_data: Sportradar API box score response (game data is at root level)
    
    Returns:
        List of team game log dictionaries
    """
    team_logs = []
    
    # Boxscore response has game data at root level, not nested under 'game'
    game = boxscore_data
    game_id = game.get('id', '')
    game_date = game.get('scheduled', '')
    
    # Home team
    if 'home' in game:
        home = game['home']
        home_log = {
            'GAME_ID': game_id,
            'GAME_DATE': game_date,
            'TEAM_ID': home.get('id', ''),
            'TEAM_ABBREVIATION': home.get('alias', ''),
        }
        
        # Add basic team stats (points, etc.)
        # Note: Boxscore may not have full 'statistics' object, but has 'points', 'scoring', etc.
        if 'points' in home:
            home_log['POINTS'] = home['points']
        if 'scoring' in home:
            home_log['SCORING'] = home['scoring']
        if 'remaining_timeouts' in home:
            home_log['REMAINING_TIMEOUTS'] = home['remaining_timeouts']
        
        # Add statistics if available
        stats = home.get('statistics', {})
        if stats:
            home_log.update(stats)
        
        team_logs.append(home_log)
    
    # Away team
    if 'away' in game:
        away = game['away']
        away_log = {
            'GAME_ID': game_id,
            'GAME_DATE': game_date,
            'TEAM_ID': away.get('id', ''),
            'TEAM_ABBREVIATION': away.get('alias', ''),
        }
        
        # Add basic team stats
        if 'points' in away:
            away_log['POINTS'] = away['points']
        if 'scoring' in away:
            away_log['SCORING'] = away['scoring']
        if 'remaining_timeouts' in away:
            away_log['REMAINING_TIMEOUTS'] = away['remaining_timeouts']
        
        # Add statistics if available
        stats = away.get('statistics', {})
        if stats:
            away_log.update(stats)
        
        team_logs.append(away_log)
    
    return team_logs


def fetch_and_store_game_logs():
    """
    Fetch game logs from Sportradar NBA API by fetching box scores for completed games.
    Reads schedule from Supabase, filters for completed games in last 3-7 days,
    fetches box scores, and aggregates into game logs format.
    """
    session_id = "debug-session"
    run_id = "run1"
    
    print(f"[{datetime.now()}] Starting Sportradar game logs fetch for season {CURRENT_SEASON}")
    
    # #region agent log
    debug_log(session_id, run_id, "A", "sportradar_fetch_game_logs.py:fetch_and_store_game_logs",
              "Function entry", {"season": CURRENT_SEASON})
    # #endregion
    
    if not is_sportradar_configured():
        print("ERROR: Sportradar API keys not configured. Set SPORTRADAR_NBA_API_KEY in .env")
        return False
    
    # #region agent log
    debug_log(session_id, run_id, "D", "sportradar_fetch_game_logs.py:fetch_and_store_game_logs",
              "API configuration check", {"configured": True})
    # #endregion
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    success_count = 0
    error_count = 0
    all_player_logs = []
    all_team_logs = []
    
    # Read schedule from Supabase
    print("Reading schedule from Supabase...")
    schedule_df = get_schedule_from_db(CURRENT_SEASON)
    
    if schedule_df is None or len(schedule_df) == 0:
        print("  ✗ No schedule data found. Please run sportradar_fetch_schedule.py first.")
        return False
    
    print(f"  ✓ Found schedule with {len(schedule_df)} games")
    
    # #region agent log
    debug_log(session_id, run_id, "SCHEDULE", "sportradar_fetch_game_logs.py:fetch_and_store_game_logs",
              "Schedule loaded", {"schedule_count": len(schedule_df), "columns": list(schedule_df.columns)})
    # #endregion
    
    # Filter for completed games from last 3-7 days
    # Schedule is already a DataFrame with games as rows
    try:
        # Filter for completed games in last 7 days
        now = datetime.now(UTC)
        cutoff_date = now - timedelta(days=7)
        completed_games = []
        
        # Iterate over DataFrame rows (each row is a game)
        for idx, game_row in schedule_df.iterrows():
            # Get game data - it might be a dict or we need to access columns
            if isinstance(game_row, pd.Series):
                game = game_row.to_dict()
            else:
                game = game_row
            
            # Check game status - completed games typically have status 'closed' or similar
            game_status = str(game.get('status', '')).lower()
            game_date_str = game.get('scheduled', '')
            
            # Parse game date
            try:
                if pd.isna(game_date_str):
                    continue
                    
                if isinstance(game_date_str, str):
                    # Try parsing ISO format date
                    game_date = datetime.fromisoformat(game_date_str.replace('Z', '+00:00'))
                elif isinstance(game_date_str, pd.Timestamp):
                    game_date = game_date_str.to_pydatetime()
                    if game_date.tzinfo is None:
                        game_date = game_date.replace(tzinfo=UTC)
                else:
                    continue
            except Exception as e:
                continue
            
            # Check if game is completed and within date range
            if game_date < cutoff_date:
                continue
            
            # Check if game is completed (status might be 'closed', 'complete', etc.)
            if game_status in ['closed', 'complete', 'completed', 'final']:
                game_id = game.get('id', '')
                if game_id:
                    completed_games.append({
                        'id': game_id,
                        'date': game_date,
                        'status': game_status
                    })
        
        print(f"  ✓ Found {len(completed_games)} completed games in last 7 days")
        
        if len(completed_games) == 0:
            print("  No completed games found in date range")
            return True  # Not an error, just no games
        
        # #region agent log
        debug_log(session_id, run_id, "FILTER", "sportradar_fetch_game_logs.py:fetch_and_store_game_logs",
                  "Filtered completed games", {"completed_count": len(completed_games)})
        # #endregion
        
    except Exception as e:
        print(f"  ✗ Error processing schedule: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Fetch box scores for each completed game
    print(f"Fetching box scores for {len(completed_games)} games...")
    
    for idx, game_info in enumerate(completed_games):
        game_id = game_info['id']
        game_date = game_info['date']
        
        try:
            # Fetch box score using /games/{game_id}/boxscore.json endpoint
            endpoint = f"games/{game_id}/boxscore.json"
            
            # #region agent log
            debug_log(session_id, run_id, f"BOX{idx}", "sportradar_fetch_game_logs.py:fetch_and_store_game_logs",
                      "Before box score API call", {"game_id": game_id, "endpoint": endpoint, "game_date": str(game_date)})
            # #endregion
            
            print(f"  [{idx+1}/{len(completed_games)}] Fetching box score for game {game_id}...")
            
            # Use header-based authentication
            boxscore_data = fetch_sportradar_nba(endpoint, use_headers=True)
            
            # #region agent log
            debug_log(session_id, run_id, f"BOX{idx}", "sportradar_fetch_game_logs.py:fetch_and_store_game_logs",
                      "After box score API call", {"game_id": game_id, "has_game": "game" in boxscore_data})
            # #endregion
            
            # Extract player logs from box score
            player_logs = extract_player_game_logs_from_boxscore(boxscore_data)
            all_player_logs.extend(player_logs)
            
            # Extract team logs from box score
            team_logs = extract_team_game_logs_from_boxscore(boxscore_data)
            all_team_logs.extend(team_logs)
            
            print(f"    ✓ Extracted {len(player_logs)} player logs, {len(team_logs)} team logs")
            
            # Rate limiting - add delay between requests
            if idx < len(completed_games) - 1:
                time.sleep(1)
                
        except Exception as e:
            print(f"    ✗ Error fetching box score for game {game_id}: {e}")
            error_count += 1
            continue
    
    # Store aggregated logs in Supabase
    try:
        if len(all_player_logs) > 0:
            print(f"\nStoring {len(all_player_logs)} player game logs...")
            supabase.table('sr_game_logs').upsert({
                'season': CURRENT_SEASON,
                'log_type': 'player',
                'data': all_player_logs,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,log_type').execute()
            
            print(f"  ✓ Stored {len(all_player_logs)} player game logs")
            success_count += 1
        else:
            print("  No player game logs to store")
            error_count += 1
            
    except Exception as e:
        print(f"  ✗ Error storing player logs: {e}")
        import traceback
        traceback.print_exc()
        error_count += 1
    
    try:
        if len(all_team_logs) > 0:
            print(f"\nStoring {len(all_team_logs)} team game logs...")
            supabase.table('sr_game_logs').upsert({
                'season': CURRENT_SEASON,
                'log_type': 'team',
                'data': all_team_logs,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,log_type').execute()
            
            print(f"  ✓ Stored {len(all_team_logs)} team game logs")
            success_count += 1
        else:
            print("  No team game logs to store")
            error_count += 1
            
    except Exception as e:
        print(f"  ✗ Error storing team logs: {e}")
        import traceback
        traceback.print_exc()
        error_count += 1
    
    # #region agent log
    debug_log(session_id, run_id, "ALL", "sportradar_fetch_game_logs.py:fetch_and_store_game_logs",
              "Function exit", {"success_count": success_count, "error_count": error_count})
    # #endregion
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_game_logs()
    sys.exit(0 if success else 1)

