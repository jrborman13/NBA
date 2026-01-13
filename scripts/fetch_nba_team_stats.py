#!/usr/bin/env python3
"""
Fetch NBA Team Stats and Store in Supabase
Fetches team stats (advanced, misc, traditional, four factors) and stores in nba_team_stats table.
Run this script daily via cron to keep data up to date.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))

import pandas as pd
import nba_api.stats.endpoints as endpoints
from supabase_config import get_supabase_service_client
from datetime import datetime, UTC
import json

CURRENT_SEASON = '2025-26'
SEASON_TYPE = 'Regular Season'

def fetch_and_store_team_stats():
    """Fetch team stats from NBA API and store in Supabase"""
    print(f"[{datetime.now()}] Starting team stats fetch for season {CURRENT_SEASON}")
    
    # Get Supabase service client (needs write access)
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client. Check SUPABASE_URL and SUPABASE_SERVICE_KEY.")
        return False
    
    # Only fetch combinations that are actually used in the application
    # Reduces API calls from 24 to 12 (50% reduction)
    required_combinations = [
        # Advanced: 2 combinations (no Starters/Bench)
        ('Advanced', None, None),
        ('Advanced', 5, None),
        # Misc: 2 combinations (no Starters/Bench)
        ('Misc', None, None),
        ('Misc', 5, None),
        # Traditional: 6 combinations (all used)
        ('Traditional', None, None),
        ('Traditional', 5, None),
        ('Traditional', None, 'Starters'),
        ('Traditional', 5, 'Starters'),
        ('Traditional', None, 'Bench'),
        ('Traditional', 5, 'Bench'),
        # Four Factors: 2 combinations (no Starters/Bench)
        ('Four Factors', None, None),
        ('Four Factors', 5, None),
    ]
    
    success_count = 0
    error_count = 0
    
    for measure_type, last_n_games, group_quantity in required_combinations:
        try:
            print(f"Fetching {measure_type}, last_n_games={last_n_games}, group={group_quantity}...")
            
            # Build API parameters (matching your existing code)
            # Map measure_type to API parameter value
            api_measure_type = measure_type
            if measure_type == 'Traditional':
                api_measure_type = 'Base'
            elif measure_type == 'Four Factors':
                api_measure_type = 'Four Factors'
            
            params = {
                'league_id_nullable': '00',
                'measure_type_detailed_defense': api_measure_type,
                'pace_adjust': 'N',
                'per_mode_detailed': 'PerGame',
                'season': CURRENT_SEASON,
                'season_type_all_star': SEASON_TYPE
            }
            
            if last_n_games:
                params['last_n_games'] = last_n_games
            
            if group_quantity:
                params['starter_bench_nullable'] = group_quantity
            
            # Fetch from NBA API
            df = endpoints.LeagueDashTeamStats(**params).get_data_frames()[0]
            
            if len(df) == 0:
                print(f"  No data returned for {measure_type}, last_n_games={last_n_games}, group={group_quantity}")
                continue
            
            # Convert DataFrame to list of dicts for JSON storage
            data = df.to_dict('records')
            
            # Manual upsert to handle expression-based unique index
            # Query for existing record using the same logic as the unique index
            query = supabase.table('nba_team_stats').select('id').eq('season', CURRENT_SEASON).eq('measure_type', measure_type)
            
            if last_n_games is not None:
                query = query.eq('last_n_games', last_n_games)
            else:
                query = query.is_('last_n_games', 'null')
            
            if group_quantity is not None:
                query = query.eq('group_quantity', group_quantity)
            else:
                query = query.is_('group_quantity', 'null')
            
            existing = query.execute()
            
            record_data = {
                'season': CURRENT_SEASON,
                'measure_type': measure_type,
                'last_n_games': last_n_games,
                'group_quantity': group_quantity,
                'data': data,
                'updated_at': datetime.now(UTC).isoformat()
            }
            
            if existing.data and len(existing.data) > 0:
                # Update existing record
                record_id = existing.data[0]['id']
                result = supabase.table('nba_team_stats').update(record_data).eq('id', record_id).execute()
            else:
                # Insert new record
                result = supabase.table('nba_team_stats').insert(record_data).execute()
            
            print(f"  ✓ Stored {measure_type}, last_n_games={last_n_games}, group={group_quantity} ({len(df)} teams)")
            success_count += 1
            
            # Small delay to avoid rate limiting
            import time
            time.sleep(0.5)
            
        except Exception as e:
            print(f"  ✗ Error fetching {measure_type}, last_n_games={last_n_games}, group={group_quantity}: {e}")
            error_count += 1
            import traceback
            traceback.print_exc()
    
    print(f"\n[{datetime.now()}] Completed: {success_count} successful, {error_count} errors")
    return error_count == 0

if __name__ == '__main__':
    success = fetch_and_store_team_stats()
    sys.exit(0 if success else 1)

