"""
Migration script to migrate player_lines.json to Supabase vegas_lines table.
"""

import json
import os
import sys
from dotenv import load_dotenv

# Add parent directory to path to import supabase_config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'new-streamlit-app', 'player-app'))

from supabase_config import get_supabase_service_client, is_supabase_configured

load_dotenv()

LINES_FILE = "player_lines.json"


def migrate_vegas_lines_json():
    """
    Migrate vegas lines from JSON file to Supabase.
    """
    if not is_supabase_configured():
        print("ERROR: Supabase not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.")
        return False
    
    # Check if JSON file exists
    json_path = os.path.join(os.path.dirname(__file__), '..', 'new-streamlit-app', 'player-app', LINES_FILE)
    if not os.path.exists(json_path):
        print(f"INFO: JSON file not found at {json_path}. Nothing to migrate.")
        return True
    
    print(f"Reading vegas lines from {json_path}...")
    try:
        with open(json_path, 'r') as f:
            lines_data = json.load(f)
        print(f"Found {len(lines_data)} player-date combinations to migrate.")
    except Exception as e:
        print(f"ERROR: Failed to read JSON file: {e}")
        return False
    
    if len(lines_data) == 0:
        print("INFO: JSON file is empty. Nothing to migrate.")
        return True
    
    # Get Supabase client
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Failed to initialize Supabase client.")
        return False
    
    # Prepare data for insertion
    records = []
    total_lines = 0
    
    for key, player_lines in lines_data.items():
        # Key format: "player_id_game_date"
        parts = key.split('_')
        if len(parts) < 2:
            print(f"Warning: Invalid key format '{key}', skipping...")
            continue
        
        player_id = parts[0]
        game_date = '_'.join(parts[1:])  # Handle dates that might have underscores
        
        if not isinstance(player_lines, dict):
            print(f"Warning: Invalid data format for key '{key}', skipping...")
            continue
        
        for stat, line_data in player_lines.items():
            if not isinstance(line_data, dict):
                continue
            
            record = {
                'player_id': str(player_id),
                'game_date': str(game_date),
                'stat': str(stat),
                'line': float(line_data.get('line', 0)),
                'over_odds': int(line_data.get('over_odds', -110)),
                'under_odds': int(line_data.get('under_odds', -110)),
                'source': str(line_data.get('source', 'manual')),
            }
            records.append(record)
            total_lines += 1
    
    print(f"Prepared {total_lines} line records to insert.")
    
    if len(records) == 0:
        print("INFO: No valid records found. Nothing to migrate.")
        return True
    
    # Insert in batches (using upsert to handle duplicates)
    batch_size = 100
    total_inserted = 0
    
    print(f"Inserting {len(records)} records in batches of {batch_size}...")
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            # Use upsert to handle potential duplicates
            result = supabase.table('vegas_lines').upsert(batch, on_conflict='player_id,game_date,stat').execute()
            total_inserted += len(batch)
            print(f"Upserted batch {i // batch_size + 1}: {len(batch)} records (Total: {total_inserted}/{len(records)})")
        except Exception as e:
            print(f"ERROR: Failed to upsert batch {i // batch_size + 1}: {e}")
            # Try inserting individually to identify problematic records
            for record in batch:
                try:
                    supabase.table('vegas_lines').upsert(record, on_conflict='player_id,game_date,stat').execute()
                    total_inserted += 1
                except Exception as e2:
                    print(f"  Failed to upsert record: {record.get('player_id', 'Unknown')} - {record.get('stat', 'Unknown')}: {e2}")
    
    print(f"\nMigration complete! Upserted {total_inserted} out of {len(records)} records.")
    
    # Verify migration
    try:
        count_result = supabase.table('vegas_lines').select('id', count='exact').execute()
        total_in_db = count_result.count if hasattr(count_result, 'count') else len(count_result.data)
        print(f"Total records in database: {total_in_db}")
    except Exception as e:
        print(f"Warning: Could not verify migration: {e}")
    
    return total_inserted == len(records)


if __name__ == "__main__":
    print("=" * 60)
    print("Vegas Lines JSON to Supabase Migration")
    print("=" * 60)
    
    success = migrate_vegas_lines_json()
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration completed with errors. Please review the output above.")
        sys.exit(1)

