#!/usr/bin/env python3
"""
Fetch NBA Synergy Data and Store in Supabase
Fetches team and player synergy data for all playtypes and stores in nba_synergy_data table.
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

def fetch_and_store_synergy_data():
    """Fetch synergy data from NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting synergy data fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    playtypes = ['Cut', 'Handoff', 'Isolation', 'Misc', 'OffScreen', 'Postup', 
                 'PRBallHandler', 'PRRollman', 'OffRebound', 'Spotup', 'Transition']
    
    success_count = 0
    error_count = 0
    
    # Fetch team synergy (both offensive and defensive)
    print("Fetching team synergy data (offensive + defensive)...")
    for playtype in playtypes:
        for type_grouping in ['offensive', 'defensive']:
            try:
                print(f"Fetching team {playtype} {type_grouping}...")
                
                df = endpoints.SynergyPlayTypes(
                    league_id_nullable='00',
                    season=CURRENT_SEASON,
                    season_type_all_star=SEASON_TYPE,
                    per_mode_simple='Totals',
                    player_or_team_abbreviation='T',
                    playtype_nullable=playtype,
                    type_grouping_nullable=type_grouping
                ).get_data_frames()[0]
                
                if len(df) == 0:
                    print(f"  No data for team {playtype} {type_grouping}")
                    continue
                
                data = df.to_dict('records')
                
                supabase.table('nba_synergy_data').upsert({
                    'season': CURRENT_SEASON,
                    'entity_type': 'team',
                    'playtype': playtype,
                    'type_grouping': type_grouping,
                    'data': data,
                    'updated_at': datetime.now(UTC).isoformat()
                }, on_conflict='season,entity_type,playtype,type_grouping').execute()
                
                print(f"  ✓ Stored team {playtype} {type_grouping} ({len(df)} records)")
                success_count += 1
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"  ✗ Error fetching team {playtype} {type_grouping}: {e}")
                error_count += 1
                import traceback
                traceback.print_exc()
    
    # Fetch player synergy (only offensive - defensive not used in application)
    print("\nFetching player synergy data (offensive only)...")
    for playtype in playtypes:
        try:
            print(f"Fetching player {playtype} offensive...")
            
            df = endpoints.SynergyPlayTypes(
                league_id_nullable='00',
                season=CURRENT_SEASON,
                season_type_all_star=SEASON_TYPE,
                per_mode_simple='Totals',
                player_or_team_abbreviation='P',
                playtype_nullable=playtype,
                type_grouping_nullable='offensive'
            ).get_data_frames()[0]
            
            if len(df) == 0:
                print(f"  No data for player {playtype} offensive")
                continue
            
            data = df.to_dict('records')
            
            supabase.table('nba_synergy_data').upsert({
                'season': CURRENT_SEASON,
                'entity_type': 'player',
                'playtype': playtype,
                'type_grouping': 'offensive',
                'data': data,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,entity_type,playtype,type_grouping').execute()
            
            print(f"  ✓ Stored player {playtype} offensive ({len(df)} records)")
            success_count += 1
            
            time.sleep(0.5)  # Rate limiting
            
        except Exception as e:
            print(f"  ✗ Error fetching player {playtype} offensive: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_synergy_data()
    sys.exit(0 if success else 1)

