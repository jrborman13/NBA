#!/usr/bin/env python3
"""
Fetch NBA Player Stats and Store in Supabase
Fetches player advanced stats and stores in nba_player_stats table.
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
SEASON_TYPE = 'Regular Season'

def fetch_and_store_player_stats():
    """Fetch player stats from NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting player stats fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    try:
        print("Fetching player advanced stats...")
        
        # Fetch from NBA API
        df = endpoints.LeagueDashPlayerStats(
            league_id_nullable='00',
            season=CURRENT_SEASON,
            season_type_all_star=SEASON_TYPE,
            measure_type_detailed_defense='Advanced',
            per_mode_detailed='PerGame'
        ).get_data_frames()[0]
        
        if len(df) == 0:
            print("  No data returned")
            return False
        
        # Convert to list of dicts
        data = df.to_dict('records')
        
        # Upsert into Supabase
        supabase.table('nba_player_stats').upsert({
            'season': CURRENT_SEASON,
            'measure_type': 'Advanced',
            'data': data,
            'updated_at': datetime.now(UTC).isoformat()
        }, on_conflict='season,measure_type').execute()
        
        print(f"  ✓ Stored {len(df)} player records")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fetch_and_store_player_stats()
    sys.exit(0 if success else 1)

