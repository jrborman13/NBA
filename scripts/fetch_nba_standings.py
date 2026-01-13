#!/usr/bin/env python3
"""
Fetch NBA Standings with Clutch Records and Store in Supabase
Fetches standings and merges with clutch records, stores in nba_standings table.
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

def fetch_and_store_standings():
    """Fetch standings with clutch records and store in Supabase"""
    print(f"[{datetime.now()}] Starting standings fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    try:
        print("Fetching regular standings...")
        standings_df = endpoints.LeagueStandings(
            league_id='00',
            season=CURRENT_SEASON,
            season_type=SEASON_TYPE
        ).get_data_frames()[0]
        
        print("Fetching clutch team stats...")
        clutch_df = endpoints.LeagueDashTeamClutch(
            league_id_nullable='00',
            season=CURRENT_SEASON,
            season_type_all_star=SEASON_TYPE,
            per_mode_detailed='Totals',
            clutch_time='Last 5 Minutes',
            ahead_behind='Ahead or Behind',
            point_diff=5
        ).get_data_frames()[0]
        
        # Merge clutch data with standings
        standings_with_clutch = standings_df.merge(
            clutch_df[['TEAM_ID', 'W', 'L']],
            left_on='TeamID',
            right_on='TEAM_ID',
            how='left'
        )
        
        # Create Clutch column formatted as "W-L"
        standings_with_clutch['CLUTCH_RECORD'] = standings_with_clutch.apply(
            lambda row: f"{int(row['W'])}-{int(row['L'])}" 
            if pd.notna(row['W']) and pd.notna(row['L']) 
            else "0-0",
            axis=1
        )
        
        # Drop temporary merge columns
        standings_with_clutch = standings_with_clutch.drop(columns=['TEAM_ID', 'W', 'L'], errors='ignore')
        
        if len(standings_with_clutch) == 0:
            print("  No standings data returned")
            return False
        
        data = standings_with_clutch.to_dict('records')
        
        supabase.table('nba_standings').upsert({
            'season': CURRENT_SEASON,
            'data': data,
            'updated_at': datetime.now(UTC).isoformat()
        }, on_conflict='season').execute()
        
        print(f"  ✓ Stored {len(standings_with_clutch)} team standings")
        return True
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = fetch_and_store_standings()
    sys.exit(0 if success else 1)

