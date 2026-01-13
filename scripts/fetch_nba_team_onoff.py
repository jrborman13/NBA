#!/usr/bin/env python3
"""
Fetch NBA Team On/Off Court Data and Store in Supabase
Fetches team on/off court data for all 30 teams and stores in nba_team_onoff table.
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

# All 30 NBA team IDs
TEAM_IDS = [
    1610612737, 1610612738, 1610612739, 1610612740, 1610612741, 1610612742,
    1610612743, 1610612744, 1610612745, 1610612746, 1610612747, 1610612748,
    1610612749, 1610612750, 1610612751, 1610612752, 1610612753, 1610612754,
    1610612755, 1610612756, 1610612757, 1610612758, 1610612759, 1610612760,
    1610612761, 1610612762, 1610612763, 1610612764, 1610612765, 1610612766
]

def fetch_and_store_team_onoff():
    """Fetch team on/off data for all teams and store in Supabase"""
    print(f"[{datetime.now()}] Starting team on/off data fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    success_count = 0
    error_count = 0
    
    for team_id in TEAM_IDS:
        try:
            print(f"Fetching on/off data for team {team_id}...")
            
            # Fetch on/off data
            result_sets = endpoints.TeamPlayerOnOffDetails(
                team_id_nullable=str(team_id),
                season=CURRENT_SEASON,
                season_type_all_star=SEASON_TYPE,
                per_mode_detailed='Totals',
                measure_type_detailed_defense='Advanced',
                league_id_nullable='00'
            ).get_data_frames()
            
            if len(result_sets) < 3:
                print(f"  Insufficient data for team {team_id}")
                error_count += 1
                continue
            
            # Merge result sets (overall, off court, on court)
            overall_df = result_sets[0]
            off_court_df = result_sets[1]
            on_court_df = result_sets[2]
            
            # Merge on/off data
            merged_df = overall_df.merge(
                off_court_df,
                on='VS_PLAYER_ID',
                how='left',
                suffixes=('', '_OFF_COURT')
            ).merge(
                on_court_df,
                on='VS_PLAYER_ID',
                how='left',
                suffixes=('', '_ON_COURT')
            )
            
            if len(merged_df) == 0:
                print(f"  No data for team {team_id}")
                error_count += 1
                continue
            
            data = merged_df.to_dict('records')
            
            supabase.table('nba_team_onoff').upsert({
                'season': CURRENT_SEASON,
                'team_id': team_id,
                'data': data,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,team_id').execute()
            
            print(f"  ✓ Stored data for team {team_id} ({len(merged_df)} players)")
            success_count += 1
            
            time.sleep(1)  # Rate limiting - 1 second between teams
            
        except Exception as e:
            print(f"  ✗ Error fetching data for team {team_id}: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_team_onoff()
    sys.exit(0 if success else 1)

