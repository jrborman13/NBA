#!/usr/bin/env python3
"""
Compare Sportradar API and NBA API Data
Fetches same data from both APIs and compares structures, fields, and values.
Generates mapping documentation.
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))

import pandas as pd
import json
from datetime import datetime
from supabase_config import get_supabase_service_client

CURRENT_SEASON = '2025-26'

def compare_schedules():
    """Compare schedule data from both APIs"""
    print("\n" + "="*60)
    print("COMPARING SCHEDULES")
    print("="*60)
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return
    
    # Fetch NBA API schedule
    try:
        nba_result = supabase.table('nba_schedule').select('data').eq('season', CURRENT_SEASON).execute()
        nba_data = nba_result.data[0]['data'] if nba_result.data else []
        print(f"NBA API: {len(nba_data)} games")
    except Exception as e:
        print(f"Error fetching NBA schedule: {e}")
        nba_data = []
    
    # Fetch Sportradar schedule
    try:
        sr_result = supabase.table('sr_schedule').select('data').eq('season', CURRENT_SEASON).execute()
        sr_data = sr_result.data[0]['data'] if sr_result.data else []
        print(f"Sportradar API: {len(sr_data)} games")
    except Exception as e:
        print(f"Error fetching Sportradar schedule: {e}")
        sr_data = []
    
    # Compare structures
    if nba_data and sr_data:
        print("\nNBA API sample fields:", list(nba_data[0].keys())[:10] if nba_data else [])
        print("Sportradar API sample fields:", list(sr_data[0].keys())[:10] if sr_data else [])
        
        # Field mapping suggestions
        print("\nField Mapping Suggestions:")
        nba_fields = set(nba_data[0].keys()) if nba_data else set()
        sr_fields = set(sr_data[0].keys()) if sr_data else set()
        
        common_fields = nba_fields & sr_fields
        print(f"  Common fields: {len(common_fields)}")
        print(f"  NBA-only fields: {len(nba_fields - sr_fields)}")
        print(f"  Sportradar-only fields: {len(sr_fields - nba_fields)}")


def compare_synergy():
    """Compare synergy data from both APIs"""
    print("\n" + "="*60)
    print("COMPARING SYNERGY DATA")
    print("="*60)
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return
    
    # Fetch NBA API synergy (team offensive)
    try:
        nba_result = supabase.table('nba_synergy_data').select('data').eq('season', CURRENT_SEASON).eq('entity_type', 'team').eq('playtype', 'Isolation').eq('type_grouping', 'offensive').execute()
        nba_data = nba_result.data[0]['data'] if nba_result.data else []
        print(f"NBA API: {len(nba_data)} team records")
    except Exception as e:
        print(f"Error fetching NBA synergy: {e}")
        nba_data = []
    
    # Fetch Sportradar synergy
    try:
        sr_result = supabase.table('sr_synergy_data').select('data').eq('season', CURRENT_SEASON).eq('entity_type', 'team').eq('playtype', 'Isolation').eq('type_grouping', 'offensive').execute()
        sr_data = sr_result.data[0]['data'] if sr_result.data else []
        print(f"Sportradar API: {len(sr_data)} team records")
    except Exception as e:
        print(f"Error fetching Sportradar synergy: {e}")
        sr_data = []
    
    # Compare structures
    if nba_data and sr_data:
        print("\nNBA API sample fields:", list(nba_data[0].keys())[:10] if nba_data else [])
        print("Sportradar API sample fields:", list(sr_data[0].keys())[:10] if sr_data else [])


def compare_game_logs():
    """Compare game logs from both APIs"""
    print("\n" + "="*60)
    print("COMPARING GAME LOGS")
    print("="*60)
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return
    
    # Fetch NBA API player game logs
    try:
        nba_result = supabase.table('nba_game_logs').select('data').eq('season', CURRENT_SEASON).eq('log_type', 'player').execute()
        nba_data = nba_result.data[0]['data'] if nba_result.data else []
        print(f"NBA API: {len(nba_data)} player game logs")
    except Exception as e:
        print(f"Error fetching NBA game logs: {e}")
        nba_data = []
    
    # Fetch Sportradar game logs
    try:
        sr_result = supabase.table('sr_game_logs').select('data').eq('season', CURRENT_SEASON).eq('log_type', 'player').execute()
        sr_data = sr_result.data[0]['data'] if sr_result.data else []
        print(f"Sportradar API: {len(sr_data)} player game logs")
    except Exception as e:
        print(f"Error fetching Sportradar game logs: {e}")
        sr_data = []
    
    # Compare structures
    if nba_data and sr_data:
        print("\nNBA API sample fields:", list(nba_data[0].keys())[:10] if nba_data else [])
        print("Sportradar API sample fields:", list(sr_data[0].keys())[:10] if sr_data else [])


def generate_mapping_doc():
    """Generate mapping documentation"""
    print("\n" + "="*60)
    print("GENERATING MAPPING DOCUMENTATION")
    print("="*60)
    
    doc_path = project_root / 'docs' / 'sportradar_mapping.md'
    doc_path.parent.mkdir(exist_ok=True)
    
    with open(doc_path, 'w') as f:
        f.write("# Sportradar API to NBA API Mapping\n\n")
        f.write(f"Generated: {datetime.now()}\n\n")
        f.write("## Overview\n\n")
        f.write("This document maps Sportradar API fields to NBA API fields.\n\n")
        f.write("## Data Sources\n\n")
        f.write("- **NBA API**: Official NBA stats API\n")
        f.write("- **Sportradar API**: Third-party sports data API\n\n")
        f.write("## Field Mappings\n\n")
        f.write("### Schedule\n")
        f.write("| NBA API Field | Sportradar Field | Notes |\n")
        f.write("|---------------|------------------|-------|\n")
        f.write("| TBD | TBD | To be populated after data comparison |\n\n")
        f.write("### Synergy Data\n")
        f.write("| NBA API Field | Sportradar Field | Notes |\n")
        f.write("|---------------|------------------|-------|\n")
        f.write("| TBD | TBD | To be populated after data comparison |\n\n")
        f.write("### Game Logs\n")
        f.write("| NBA API Field | Sportradar Field | Notes |\n")
        f.write("|---------------|------------------|-------|\n")
        f.write("| TBD | TBD | To be populated after data comparison |\n\n")
        f.write("## Missing Features\n\n")
        f.write("- Clutch stats: May need custom calculation\n")
        f.write("- On/Off court data: May not be available\n")
        f.write("- Drives stats: May need to calculate from play-by-play\n\n")
    
    print(f"  ✓ Mapping documentation created at: {doc_path}")


def main():
    """Run all comparisons"""
    print(f"[{datetime.now()}] Starting API comparison for season {CURRENT_SEASON}")
    
    compare_schedules()
    compare_synergy()
    compare_game_logs()
    generate_mapping_doc()
    
    print(f"\n[{datetime.now()}] Comparison complete")
    print("\nNote: Run this script after fetching data from both APIs to populate mapping documentation.")

if __name__ == '__main__':
    main()

