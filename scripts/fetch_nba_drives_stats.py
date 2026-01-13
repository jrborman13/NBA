#!/usr/bin/env python3
"""
Fetch NBA Drives Stats and Store in Supabase
Fetches player and team drives statistics and stores in nba_drives_stats table.
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
import time

CURRENT_SEASON = '2025-26'
SEASON_TYPE = 'Regular Season'

def fetch_and_store_drives_stats():
    """Fetch drives stats from NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting drives stats fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    success_count = 0
    error_count = 0
    
    entity_types = ['player', 'team']
    player_or_team_map = {'player': 'P', 'team': 'T'}
    
    for entity_type in entity_types:
        try:
            print(f"Fetching {entity_type} drives stats...")
            
            df = endpoints.LeagueDashPtStats(
                league_id_nullable='00',
                season=CURRENT_SEASON,
                season_type_all_star=SEASON_TYPE,
                per_mode_simple='Totals',
                player_or_team_abbreviation=player_or_team_map[entity_type]
            ).get_data_frames()[0]
            
            if len(df) == 0:
                print(f"  No data for {entity_type}")
                error_count += 1
                continue
            
            data = df.to_dict('records')
            
            supabase.table('nba_drives_stats').upsert({
                'season': CURRENT_SEASON,
                'entity_type': entity_type,
                'data': data,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,entity_type').execute()
            
            print(f"  ✓ Stored {entity_type} drives stats ({len(df)} records)")
            success_count += 1
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"  ✗ Error fetching {entity_type} drives stats: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_drives_stats()
    sys.exit(0 if success else 1)

