#!/usr/bin/env python3
"""
Fetch NBA Player Index and Store in Supabase
Fetches player index/roster data and stores in nba_player_index table.
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

def fetch_and_store_player_index():
    """Fetch player index from NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting player index fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    try:
        print("Fetching player index...")
        df = endpoints.PlayerIndex(
            league_id='00',
            season=CURRENT_SEASON
        ).get_data_frames()[0]
        
        if len(df) == 0:
            print("  No player index data returned")
            return False
        
        data = df.to_dict('records')
        
        supabase.table('nba_player_index').upsert({
            'season': CURRENT_SEASON,
            'data': data,
            'updated_at': datetime.now(UTC).isoformat()
        }, on_conflict='season').execute()
        
        print(f"  ✓ Stored {len(df)} player records")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fetch_and_store_player_index()
    sys.exit(0 if success else 1)

