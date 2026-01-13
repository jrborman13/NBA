#!/usr/bin/env python3
"""
Fetch NBA Game Logs and Store in Supabase
Fetches player and team game logs and stores in nba_game_logs table.
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

def fetch_and_store_game_logs():
    """Fetch game logs from NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting game logs fetch for season {CURRENT_SEASON}")
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return False
    
    success_count = 0
    error_count = 0
    
    # Fetch player game logs (all players in one call)
    try:
        print("Fetching player game logs...")
        df = endpoints.PlayerGameLogs(
            season_nullable=CURRENT_SEASON,
            league_id_nullable='00'
        ).get_data_frames()[0]
        
        # Filter out preseason games (keep regular season '2' and playoffs '4')
        if len(df) > 0:
            df = df[df['GAME_ID'].astype(str).str[2].isin(['2', '4'])].copy()
        
        if len(df) > 0:
            data = df.to_dict('records')
            supabase.table('nba_game_logs').upsert({
                'season': CURRENT_SEASON,
                'log_type': 'player',
                'data': data,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,log_type').execute()
            
            print(f"  ✓ Stored {len(df)} player game logs")
            success_count += 1
        else:
            print("  No player game logs returned")
            error_count += 1
            
    except Exception as e:
        print(f"  ✗ Error fetching player logs: {e}")
        import traceback
        traceback.print_exc()
        error_count += 1
    
    # Fetch team game logs (all teams in one call)
    try:
        print("Fetching team game logs...")
        df = endpoints.TeamGameLogs(
            season_nullable=CURRENT_SEASON,
            season_type_nullable=SEASON_TYPE
        ).get_data_frames()[0]
        
        if len(df) > 0:
            data = df.to_dict('records')
            supabase.table('nba_game_logs').upsert({
                'season': CURRENT_SEASON,
                'log_type': 'team',
                'data': data,
                'updated_at': datetime.now(UTC).isoformat()
            }, on_conflict='season,log_type').execute()
            
            print(f"  ✓ Stored {len(df)} team game logs")
            success_count += 1
        else:
            print("  No team game logs returned")
            error_count += 1
            
    except Exception as e:
        print(f"  ✗ Error fetching team logs: {e}")
        import traceback
        traceback.print_exc()
        error_count += 1
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_game_logs()
    sys.exit(0 if success else 1)

