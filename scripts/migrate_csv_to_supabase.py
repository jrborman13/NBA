"""
Migration script to migrate predictions_log.csv to Supabase predictions table.
"""

import pandas as pd
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add parent directory to path to import supabase_config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'new-streamlit-app', 'player-app'))

from supabase_config import get_supabase_service_client, is_supabase_configured

load_dotenv()

PREDICTIONS_FILE = "predictions_log.csv"


def migrate_predictions_csv():
    """
    Migrate predictions from CSV file to Supabase.
    """
    if not is_supabase_configured():
        print("ERROR: Supabase not configured. Please set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables.")
        return False
    
    # Check if CSV file exists
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'new-streamlit-app', 'player-app', PREDICTIONS_FILE)
    if not os.path.exists(csv_path):
        print(f"INFO: CSV file not found at {csv_path}. Nothing to migrate.")
        return True
    
    print(f"Reading predictions from {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
        print(f"Found {len(df)} prediction records to migrate.")
    except Exception as e:
        print(f"ERROR: Failed to read CSV file: {e}")
        return False
    
    if len(df) == 0:
        print("INFO: CSV file is empty. Nothing to migrate.")
        return True
    
    # Get Supabase client
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Failed to initialize Supabase client.")
        return False
    
    # Prepare data for insertion
    records = []
    for _, row in df.iterrows():
        record = {
            'timestamp': row.get('timestamp', datetime.now().isoformat()),
            'player_id': str(row.get('player_id', '')),
            'player_name': str(row.get('player_name', '')),
            'opponent_abbr': str(row.get('opponent_abbr', '')),
            'game_date': str(row.get('game_date', '')),
            'stat': str(row.get('stat', '')),
            'prediction': float(row.get('prediction', 0)),
            'vegas_line': float(row['vegas_line']) if pd.notna(row.get('vegas_line')) else None,
            'actual': float(row['actual']) if pd.notna(row.get('actual')) else None,
            'is_home': bool(row.get('is_home', False)),
            'days_rest': int(row.get('days_rest', 0)),
            'confidence': str(row.get('confidence', 'medium')),
            'season_avg': float(row.get('season_avg', 0)),
            'l5_avg': float(row.get('l5_avg', 0)),
            'l10_avg': float(row.get('l10_avg', 0)),
            'vs_opponent_avg': float(row['vs_opponent_avg']) if pd.notna(row.get('vs_opponent_avg')) else None,
            'opp_def_rating': float(row.get('opp_def_rating', 110)),
            'opp_pace': float(row.get('opp_pace', 100)),
            'usage_rate': float(row.get('usage_rate', 20)),
        }
        records.append(record)
    
    # Insert in batches
    batch_size = 100
    total_inserted = 0
    
    print(f"Inserting {len(records)} records in batches of {batch_size}...")
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            result = supabase.table('predictions').insert(batch).execute()
            total_inserted += len(batch)
            print(f"Inserted batch {i // batch_size + 1}: {len(batch)} records (Total: {total_inserted}/{len(records)})")
        except Exception as e:
            print(f"ERROR: Failed to insert batch {i // batch_size + 1}: {e}")
            # Try inserting individually to identify problematic records
            for record in batch:
                try:
                    supabase.table('predictions').insert(record).execute()
                    total_inserted += 1
                except Exception as e2:
                    print(f"  Failed to insert record: {record.get('player_name', 'Unknown')} - {record.get('stat', 'Unknown')}: {e2}")
    
    print(f"\nMigration complete! Inserted {total_inserted} out of {len(records)} records.")
    
    # Verify migration
    try:
        count_result = supabase.table('predictions').select('id', count='exact').execute()
        total_in_db = count_result.count if hasattr(count_result, 'count') else len(count_result.data)
        print(f"Total records in database: {total_in_db}")
    except Exception as e:
        print(f"Warning: Could not verify migration: {e}")
    
    return total_inserted == len(records)


if __name__ == "__main__":
    print("=" * 60)
    print("Predictions CSV to Supabase Migration")
    print("=" * 60)
    
    success = migrate_predictions_csv()
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration completed with errors. Please review the output above.")
        sys.exit(1)

