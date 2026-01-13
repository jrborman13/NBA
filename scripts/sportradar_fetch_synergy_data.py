#!/usr/bin/env python3
"""
Fetch NBA Synergy Data from Sportradar Synergy Basketball API and Store in Supabase
Fetches team and player synergy data for all playtypes and stores in sr_synergy_data table.
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
    fetch_sportradar_synergy, is_sportradar_configured,
    get_sportradar_synergy_url, SPORTRADAR_SYNERGY_BASE_URL, SPORTRADAR_SYNERGY_VERSION, SPORTRADAR_SYNERGY_API_KEY
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

# Playtypes matching NBA API (may need adjustment based on Sportradar API)
playtypes = ['Cut', 'Handoff', 'Isolation', 'Misc', 'OffScreen', 'Postup', 
             'PRBallHandler', 'PRRollman', 'OffRebound', 'Spotup', 'Transition']

def fetch_and_store_synergy_data():
    """Fetch synergy data from Sportradar Synergy Basketball API and store in Supabase"""
    print(f"[{datetime.now()}] Starting Sportradar synergy data fetch for season {CURRENT_SEASON}")
    
    if not is_sportradar_configured():
        print("ERROR: Sportradar API keys not configured. Set SPORTRADAR_SYNERGY_API_KEY in .env")
        return False
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    success_count = 0
    error_count = 0
    
    session_id = "debug-session"
    run_id = "run1"
    
    # Fetch team synergy (both offensive and defensive)
    print("Fetching team synergy data (offensive + defensive)...")
    attempt_num = 0
    for playtype in playtypes:
        for type_grouping in ['offensive', 'defensive']:
            attempt_num += 1
            try:
                print(f"Fetching team {playtype} {type_grouping}...")
                
                # Sportradar Synergy API endpoint format:
                # /play-type-stats/team/{season}/{playtype}/{type_grouping}
                endpoint = f"play-type-stats/team/{CURRENT_SEASON}/{playtype}/{type_grouping}"
                
                # #region agent log
                debug_log(session_id, run_id, f"{chr(65+attempt_num)}", "sportradar_fetch_synergy_data.py:fetch_and_store_synergy_data",
                          "Before API call", {"endpoint": endpoint, "playtype": playtype, "type_grouping": type_grouping, "entity_type": "team"})
                # #endregion
                
                # Use Synergy API URL builder (may need .us domain check)
                url = get_sportradar_synergy_url(endpoint)
                print(f"[SPORTRADAR SYNERGY] Fetching URL: {url[:100]}...")
                response = requests.get(url, timeout=30)
                
                # #region agent log
                debug_log(session_id, run_id, f"{chr(65+attempt_num)}", "sportradar_fetch_synergy_data.py:fetch_and_store_synergy_data",
                          "After API call", {"status_code": response.status_code, "response_length": len(response.text)})
                # #endregion
                
                if response.status_code == 429:
                    retry_delay = min(2 ** attempt_num, 10)
                    print(f"  ✗ Rate limit (429), waiting {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    response = requests.get(url, timeout=30)
                
                if response.status_code != 200:
                    print(f"  ✗ Error response status: {response.status_code}")
                    print(f"  ✗ Error response text: {response.text[:500]}")
                    response.raise_for_status()
                
                response_data = response.json()
                
                # Extract data array (structure may vary)
                if isinstance(response_data, list):
                    data = response_data
                elif isinstance(response_data, dict):
                    # Try common keys
                    data = response_data.get('data', response_data.get('teams', response_data.get('results', [])))
                else:
                    data = []
                
                if len(data) == 0:
                    print(f"  No data for team {playtype} {type_grouping}")
                    continue
                
                supabase.table('sr_synergy_data').upsert({
                    'season': CURRENT_SEASON,
                    'entity_type': 'team',
                    'playtype': playtype,
                    'type_grouping': type_grouping,
                    'data': data,
                    'updated_at': datetime.now(UTC).isoformat()
                }, on_conflict='season,entity_type,playtype,type_grouping').execute()
                
                # #region agent log
                debug_log(session_id, run_id, f"{chr(65+attempt_num)}", "sportradar_fetch_synergy_data.py:fetch_and_store_synergy_data",
                          "After storing team data", {"data_count": len(data), "playtype": playtype, "type_grouping": type_grouping})
                # #endregion
                
                print(f"  ✓ Stored team {playtype} {type_grouping} ({len(data)} records)")
                success_count += 1
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                error_msg = str(e)
                status_code = None
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    status_code = e.response.status_code
                
                # #region agent log
                debug_log(session_id, run_id, f"{chr(65+attempt_num)}", "sportradar_fetch_synergy_data.py:fetch_and_store_synergy_data",
                          "Error fetching team", {"error": error_msg[:200], "status_code": status_code, "playtype": playtype, "type_grouping": type_grouping})
                # #endregion
                
                print(f"  ✗ Error fetching team {playtype} {type_grouping}: {e}")
                error_count += 1
                import traceback
                traceback.print_exc()
    
    # Fetch player synergy (only offensive - defensive not used in application)
    print("\nFetching player synergy data (offensive only)...")
    player_attempt_num = 0
    for playtype in playtypes:
        player_attempt_num += 1
        try:
            print(f"Fetching player {playtype} offensive...")
            
            endpoint = f"play-type-stats/player/{CURRENT_SEASON}/{playtype}/offensive"
            
            # #region agent log
            debug_log(session_id, run_id, f"P{chr(65+player_attempt_num)}", "sportradar_fetch_synergy_data.py:fetch_and_store_synergy_data",
                      "Before API call", {"endpoint": endpoint, "playtype": playtype, "entity_type": "player"})
            # #endregion
            
            # Use Synergy API URL builder
            url = get_sportradar_synergy_url(endpoint)
            print(f"[SPORTRADAR SYNERGY] Fetching URL: {url[:100]}...")
            response = requests.get(url, timeout=30)
            
            # #region agent log
            debug_log(session_id, run_id, f"P{chr(65+player_attempt_num)}", "sportradar_fetch_synergy_data.py:fetch_and_store_synergy_data",
                      "After API call", {"status_code": response.status_code, "response_length": len(response.text)})
            # #endregion
            
            if response.status_code == 429:
                retry_delay = min(2 ** player_attempt_num, 10)
                print(f"  ✗ Rate limit (429), waiting {retry_delay} seconds...")
                time.sleep(retry_delay)
                response = requests.get(url, timeout=30)
            
            if response.status_code != 200:
                print(f"  ✗ Error response status: {response.status_code}")
                print(f"  ✗ Error response text: {response.text[:500]}")
                response.raise_for_status()
            
            response_data = response.json()
            
            # Extract data array
            if isinstance(response_data, list):
                data = response_data
            elif isinstance(response_data, dict):
                data = response_data.get('data', response_data.get('players', response_data.get('results', [])))
            else:
                data = []
            
            if len(data) == 0:
                print(f"  No data for player {playtype} offensive")
                continue
            
            supabase.table('sr_synergy_data').upsert({
                'season': CURRENT_SEASON,
                'entity_type': 'player',
                'playtype': playtype,
                'type_grouping': 'offensive',
                'data': data,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,entity_type,playtype,type_grouping').execute()
            
            # #region agent log
            debug_log(session_id, run_id, f"P{chr(65+player_attempt_num)}", "sportradar_fetch_synergy_data.py:fetch_and_store_synergy_data",
                      "After storing player data", {"data_count": len(data), "playtype": playtype})
            # #endregion
            
            print(f"  ✓ Stored player {playtype} offensive ({len(data)} records)")
            success_count += 1
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            error_msg = str(e)
            status_code = None
            if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                status_code = e.response.status_code
            
            # #region agent log
            debug_log(session_id, run_id, f"P{chr(65+player_attempt_num)}", "sportradar_fetch_synergy_data.py:fetch_and_store_synergy_data",
                      "Error fetching player", {"error": error_msg[:200], "status_code": status_code, "playtype": playtype})
            # #endregion
            
            print(f"  ✗ Error fetching player {playtype} offensive: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_synergy_data()
    sys.exit(0 if success else 1)

