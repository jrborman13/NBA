#!/usr/bin/env python3
"""
Fetch NBA Team Stats from Sportradar API and Store in Supabase
Fetches team stats and stores in sr_team_stats table.
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
from datetime import datetime, UTC
import time
import requests

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

def fetch_and_store_team_stats():
    """Fetch team stats from Sportradar NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting Sportradar team stats fetch for season {CURRENT_SEASON}")
    
    if not is_sportradar_configured():
        print("ERROR: Sportradar API keys not configured. Set SPORTRADAR_NBA_API_KEY in .env")
        return False
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    # Only fetch combinations that are actually used in the application
    # Reduces API calls from 24 to 12 (50% reduction)
    required_combinations = [
        # Advanced: 2 combinations (no Starters/Bench)
        ('Advanced', None, None),
        ('Advanced', 5, None),
        # Misc: 2 combinations (no Starters/Bench)
        ('Misc', None, None),
        ('Misc', 5, None),
        # Traditional: 6 combinations (all used)
        ('Traditional', None, None),
        ('Traditional', 5, None),
        ('Traditional', None, 'Starters'),
        ('Traditional', 5, 'Starters'),
        ('Traditional', None, 'Bench'),
        ('Traditional', 5, 'Bench'),
        # Four Factors: 2 combinations (no Starters/Bench)
        ('Four Factors', None, None),
        ('Four Factors', 5, None),
    ]
    
    success_count = 0
    error_count = 0
    
    session_id = "debug-session"
    run_id = "run1"
    
    for idx, (measure_type, last_n_games, group_quantity) in enumerate(required_combinations):
        try:
            print(f"Fetching {measure_type}, last_n_games={last_n_games}, group={group_quantity}...")
            
            # Sportradar NBA API Seasonal Statistics endpoint format:
            # /seasons/{season}/teams/statistics
            season_year = CURRENT_SEASON.split('-')[0]
            endpoint = f"seasons/{season_year}/teams/statistics"
            
            # Add query parameters if needed
            params = {}
            if last_n_games:
                params['last_n_games'] = last_n_games
            if group_quantity:
                params['group'] = group_quantity.lower()
            
            # #region agent log
            debug_log(session_id, run_id, f"{chr(65+idx)}", "sportradar_fetch_team_stats.py:fetch_and_store_team_stats",
                      "Before API call", {"endpoint": endpoint, "measure_type": measure_type, "params": params})
            # #endregion
            
            # Use .us domain with access level (correct format)
            url = get_sportradar_nba_url(endpoint, use_us_domain=True, include_access_level=True)
            if params:
                param_str = "&".join([f"{k}={v}" for k, v in params.items()])
                url = f"{url}&{param_str}"
            
            print(f"[SPORTRADAR] Fetching URL: {url[:100]}...")
            response = requests.get(url, timeout=30)
            
            # #region agent log
            debug_log(session_id, run_id, f"{chr(65+idx)}", "sportradar_fetch_team_stats.py:fetch_and_store_team_stats",
                      "After API call", {"status_code": response.status_code, "response_length": len(response.text)})
            # #endregion
            
            if response.status_code == 429:
                retry_delay = min(2 ** idx, 10)
                print(f"  ✗ Rate limit (429), waiting {retry_delay} seconds...")
                time.sleep(retry_delay)
                response = requests.get(url, timeout=30)
            
            if response.status_code != 200:
                print(f"  ✗ Error response status: {response.status_code}")
                print(f"  ✗ Error response text: {response.text[:500]}")
                response.raise_for_status()
            
            response_data = response.json()
            
            # Extract team statistics
            # Structure may vary - adjust based on actual API response
            if isinstance(response_data, list):
                data = response_data
            elif isinstance(response_data, dict):
                data = response_data.get('teams', response_data.get('data', response_data.get('statistics', [])))
            else:
                data = []
            
            if len(data) == 0:
                print(f"  No data returned for {measure_type}, last_n_games={last_n_games}, group={group_quantity}")
                continue
            
            # Manual upsert to handle expression-based unique index
            query = supabase.table('sr_team_stats').select('id').eq('season', CURRENT_SEASON).eq('measure_type', measure_type)
            
            if last_n_games is not None:
                query = query.eq('last_n_games', last_n_games)
            else:
                query = query.is_('last_n_games', 'null')
            
            if group_quantity is not None:
                query = query.eq('group_quantity', group_quantity)
            else:
                query = query.is_('group_quantity', 'null')
            
            existing = query.execute()
            
            record_data = {
                'season': CURRENT_SEASON,
                'measure_type': measure_type,
                'last_n_games': last_n_games,
                'group_quantity': group_quantity,
                'data': data,
                'updated_at': datetime.now(UTC).isoformat()
            }
            
            if existing.data and len(existing.data) > 0:
                record_id = existing.data[0]['id']
                result = supabase.table('sr_team_stats').update(record_data).eq('id', record_id).execute()
            else:
                result = supabase.table('sr_team_stats').insert(record_data).execute()
            
            # #region agent log
            debug_log(session_id, run_id, f"{chr(65+idx)}", "sportradar_fetch_team_stats.py:fetch_and_store_team_stats",
                      "After storing data", {"data_count": len(data), "measure_type": measure_type})
            # #endregion
            
            print(f"  ✓ Stored {measure_type}, last_n_games={last_n_games}, group={group_quantity} ({len(data)} teams)")
            success_count += 1
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            error_msg = str(e)
            status_code = None
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                status_code = e.response.status_code
            
            # #region agent log
            debug_log(session_id, run_id, f"{chr(65+idx)}", "sportradar_fetch_team_stats.py:fetch_and_store_team_stats",
                      "Error fetching", {"error": error_msg[:200], "status_code": status_code, "measure_type": measure_type})
            # #endregion
            
            print(f"  ✗ Error fetching {measure_type}, last_n_games={last_n_games}, group={group_quantity}: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_team_stats()
    sys.exit(0 if success else 1)

