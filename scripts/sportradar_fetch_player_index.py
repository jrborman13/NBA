#!/usr/bin/env python3
"""
Fetch NBA Player Index from Sportradar API and Store in Supabase
Fetches player index/roster data and stores in sr_player_index table.
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

def fetch_and_store_player_index():
    """Fetch player index from Sportradar NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting Sportradar player index fetch for season {CURRENT_SEASON}")
    
    if not is_sportradar_configured():
        print("ERROR: Sportradar API keys not configured. Set SPORTRADAR_NBA_API_KEY in .env")
        return False
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    session_id = "debug-session"
    run_id = "run1"
    
    try:
        print("Fetching player index from Sportradar NBA API...")
        
        season_year = CURRENT_SEASON.split('-')[0]
        endpoint = f"seasons/{season_year}/players"
        
        # #region agent log
        debug_log(session_id, run_id, "A", "sportradar_fetch_player_index.py:fetch_and_store_player_index",
                  "Before API call", {"endpoint": endpoint})
        # #endregion
        
        # Use .us domain with access level (correct format)
        url = get_sportradar_nba_url(endpoint, use_us_domain=True, include_access_level=True)
        print(f"[SPORTRADAR] Fetching URL: {url[:100]}...")
        response = requests.get(url, timeout=30)
        
        # #region agent log
        debug_log(session_id, run_id, "A", "sportradar_fetch_player_index.py:fetch_and_store_player_index",
                  "After API call", {"status_code": response.status_code, "response_length": len(response.text)})
        # #endregion
        
        if response.status_code == 429:
            retry_delay = 2
            print(f"  ✗ Rate limit (429), waiting {retry_delay} seconds...")
            time.sleep(retry_delay)
            response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            print(f"  ✗ Error response status: {response.status_code}")
            print(f"  ✗ Error response text: {response.text[:500]}")
            response.raise_for_status()
        
        response_data = response.json()
        
        # Extract player data
        if isinstance(response_data, list):
            data = response_data
        elif isinstance(response_data, dict):
            data = response_data.get('players', response_data.get('data', []))
        else:
            data = []
        
        if len(data) == 0:
            print("  No player index data returned")
            return False
        
        supabase.table('sr_player_index').upsert({
            'season': CURRENT_SEASON,
            'data': data,
            'updated_at': datetime.now(UTC).isoformat()
        }, on_conflict='season').execute()
        
        # #region agent log
        debug_log(session_id, run_id, "A", "sportradar_fetch_player_index.py:fetch_and_store_player_index",
                  "After storing data", {"data_count": len(data)})
        # #endregion
        
        print(f"  ✓ Stored {len(data)} player records")
        return True
        
    except Exception as e:
        error_msg = str(e)
        status_code = None
        if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
            status_code = e.response.status_code
        
        # #region agent log
        debug_log(session_id, run_id, "A", "sportradar_fetch_player_index.py:fetch_and_store_player_index",
                  "Error fetching", {"error": error_msg[:200], "status_code": status_code})
        # #endregion
        
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fetch_and_store_player_index()
    sys.exit(0 if success else 1)

