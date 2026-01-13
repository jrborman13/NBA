#!/usr/bin/env python3
"""
Fetch NBA Schedule from Sportradar API and Store in Supabase
Fetches league schedule and stores in sr_schedule table.
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
    SPORTRADAR_NBA_BASE_URL, SPORTRADAR_NBA_VERSION, SPORTRADAR_NBA_API_KEY,
    get_sportradar_nba_url, SPORTRADAR_NBA_BASE_URL_US, SPORTRADAR_ACCESS_LEVEL, SPORTRADAR_LANGUAGE
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

def fetch_and_store_schedule(date=None):
    """
    Fetch schedule from Sportradar NBA API and store in Supabase.
    
    Args:
        date: Optional datetime.date object to fetch schedule for specific date.
              If None, fetches for today.
    """
    session_id = "debug-session"
    run_id = "run1"
    
    if date is None:
        date = datetime.now(UTC).date()
    
    print(f"[{datetime.now()}] Starting Sportradar schedule fetch for date {date}")
    
    # #region agent log
    debug_log(session_id, run_id, "A", "sportradar_fetch_schedule.py:fetch_and_store_schedule", 
              "Function entry", {"date": str(date), "api_version": SPORTRADAR_NBA_VERSION})
    # #endregion
    
    if not is_sportradar_configured():
        print("ERROR: Sportradar API keys not configured. Set SPORTRADAR_NBA_API_KEY in .env")
        return False
    
    # #region agent log
    debug_log(session_id, run_id, "D", "sportradar_fetch_schedule.py:fetch_and_store_schedule",
              "API configuration check", {"configured": True, "api_key_length": len(SPORTRADAR_NBA_API_KEY) if SPORTRADAR_NBA_API_KEY else 0})
    # #endregion
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    try:
        print(f"Fetching schedule from Sportradar NBA API for {date}...")
        
        # Use the working format: games/{year}/{month}/{day}/schedule.json
        year = date.year
        month = date.month
        day = date.day
        
        endpoint = f"games/{year}/{month:02d}/{day:02d}/schedule.json"
        
        # #region agent log
        debug_log(session_id, run_id, "C", "sportradar_fetch_schedule.py:fetch_and_store_schedule",
                  "Before API call", {"endpoint": endpoint, "date": str(date), "year": year, "month": month, "day": day})
        # #endregion
        
        # Use header-based authentication with .com domain
        response_data = fetch_sportradar_nba(endpoint, use_headers=True)
        
        # #region agent log
        debug_log(session_id, run_id, "SUCCESS", "sportradar_fetch_schedule.py:fetch_and_store_schedule",
                  "After successful API call", {"endpoint": endpoint, "has_games": "games" in response_data})
        # #endregion
        
        # Sportradar returns games in 'games' array
        if 'games' not in response_data:
            print("  No games found in response")
            return False
        
        games = response_data['games']
        
        if len(games) == 0:
            print(f"  No games scheduled for {date}")
            return True  # Not an error, just no games
        
        print(f"  ✓ Found {len(games)} games for {date}")
        
        # Convert to list of dicts for JSON storage
        # Keep original Sportradar structure for now (can transform later)
        data = games
        
        # Store with date as key for date-specific schedules
        # Also store with season for full season queries
        season_year = CURRENT_SEASON.split('-')[0]
        
        # Upsert by date (if we want to track by date) or by season
        # For now, we'll store by season and append/update games
        supabase.table('sr_schedule').upsert({
            'season': CURRENT_SEASON,
            'data': data,
            'updated_at': datetime.now(UTC).isoformat()
        }, on_conflict='season').execute()
        
        print(f"  ✓ Stored {len(games)} schedule records")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fetch_and_store_schedule()
    sys.exit(0 if success else 1)

