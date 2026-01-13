#!/usr/bin/env python3
"""
Fetch NBA Schedule and Store in Supabase
Fetches league schedule and stores in nba_schedule table.
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))

import pandas as pd
import nba_api.stats.endpoints as endpoints
from supabase_config import get_supabase_service_client
from datetime import datetime, UTC

CURRENT_SEASON = '2025-26'

def fetch_and_store_schedule():
    """Fetch schedule from NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting schedule fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    try:
        print("Fetching schedule...")
        df = endpoints.ScheduleLeagueV2(
            league_id='00',
            season=CURRENT_SEASON
        ).get_data_frames()[0]
        
        if len(df) == 0:
            print("  No schedule data returned")
            return False
        
        data = df.to_dict('records')
        
        supabase.table('nba_schedule').upsert({
            'season': CURRENT_SEASON,
            'data': data,
            'updated_at': datetime.now(UTC).isoformat()
        }, on_conflict='season').execute()
        
        print(f"  ✓ Stored {len(df)} schedule records")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fetch_and_store_schedule()
    sys.exit(0 if success else 1)

