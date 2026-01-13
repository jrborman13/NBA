#!/usr/bin/env python3
"""
Fetch pbpstats.com Data and Store in Supabase
Fetches team and opponent stats from pbpstats.com API and stores in nba_pbpstats table.
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))

import pandas as pd
import requests
from supabase_config import get_supabase_service_client
from datetime import datetime, UTC
import time

CURRENT_SEASON = '2025-26'
SEASON_TYPE = 'Regular Season'

def fetch_and_store_pbpstats():
    """Fetch pbpstats data and store in Supabase"""
    print(f"[{datetime.now()}] Starting pbpstats fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    success_count = 0
    error_count = 0
    
    stat_types = ['team', 'opponent']
    
    for stat_type in stat_types:
        try:
            print(f"Fetching {stat_type} stats from pbpstats...")
            
            url = 'https://api.pbpstats.com/get-totals/nba'
            params = {
                'Season': CURRENT_SEASON,
                'SeasonType': SEASON_TYPE,
                'Type': 'Team' if stat_type == 'team' else 'Opponent'
            }
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            api_data = response.json()
            stats_data = api_data.get('multi_row_table_data', [])
            
            if len(stats_data) == 0:
                print(f"  No data for {stat_type}")
                error_count += 1
                continue
            
            supabase.table('nba_pbpstats').upsert({
                'season': CURRENT_SEASON,
                'stat_type': stat_type,
                'data': stats_data,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,stat_type').execute()
            
            print(f"  ✓ Stored {stat_type} stats ({len(stats_data)} teams)")
            success_count += 1
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"  ✗ Error fetching {stat_type} stats: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_pbpstats()
    sys.exit(0 if success else 1)

