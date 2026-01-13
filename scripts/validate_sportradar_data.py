#!/usr/bin/env python3
"""
Validate Sportradar Data Quality
Checks data completeness, validates data types, compares record counts.
Generates validation report.
"""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))

import pandas as pd
from datetime import datetime
from supabase_config import get_supabase_service_client

CURRENT_SEASON = '2025-26'

def validate_table(table_name, season):
    """Validate data in a specific table"""
    supabase = get_supabase_service_client()
    if not supabase:
        return None
    
    try:
        result = supabase.table(table_name).select('*').eq('season', season).execute()
        
        if not result.data:
            return {
                'table': table_name,
                'records': 0,
                'status': 'EMPTY',
                'issues': ['No data found']
            }
        
        total_records = len(result.data)
        issues = []
        
        # Check for null data fields
        null_data_count = sum(1 for r in result.data if not r.get('data'))
        if null_data_count > 0:
            issues.append(f"{null_data_count} records with null data")
        
        # Check updated_at timestamps
        old_records = sum(1 for r in result.data 
                         if pd.to_datetime(r.get('updated_at', '2000-01-01')) < pd.Timestamp.now() - pd.Timedelta(days=7))
        if old_records > 0:
            issues.append(f"{old_records} records older than 7 days")
        
        return {
            'table': table_name,
            'records': total_records,
            'status': 'OK' if not issues else 'WARNING',
            'issues': issues
        }
    except Exception as e:
        return {
            'table': table_name,
            'records': 0,
            'status': 'ERROR',
            'issues': [str(e)]
        }


def compare_record_counts():
    """Compare record counts between NBA API and Sportradar data"""
    print("\n" + "="*60)
    print("RECORD COUNT COMPARISON")
    print("="*60)
    
    tables = [
        ('nba_schedule', 'sr_schedule'),
        ('nba_synergy_data', 'sr_synergy_data'),
        ('nba_game_logs', 'sr_game_logs'),
        ('nba_team_stats', 'sr_team_stats'),
        ('nba_player_stats', 'sr_player_stats'),
        ('nba_standings', 'sr_standings'),
        ('nba_player_index', 'sr_player_index'),
    ]
    
    comparison = []
    
    for nba_table, sr_table in tables:
        nba_result = validate_table(nba_table, CURRENT_SEASON)
        sr_result = validate_table(sr_table, CURRENT_SEASON)
        
        if nba_result and sr_result:
            comparison.append({
                'table': nba_table.replace('nba_', ''),
                'nba_records': nba_result['records'],
                'sr_records': sr_result['records'],
                'difference': sr_result['records'] - nba_result['records'],
                'nba_status': nba_result['status'],
                'sr_status': sr_result['status']
            })
    
    # Print comparison
    print(f"\n{'Table':<20} {'NBA API':<15} {'Sportradar':<15} {'Difference':<15} {'Status':<15}")
    print("-" * 80)
    for comp in comparison:
        status = "✓" if comp['nba_status'] == 'OK' and comp['sr_status'] == 'OK' else "⚠"
        print(f"{comp['table']:<20} {comp['nba_records']:<15} {comp['sr_records']:<15} {comp['difference']:<15} {status:<15}")


def validate_data_types():
    """Validate data types in Sportradar tables"""
    print("\n" + "="*60)
    print("DATA TYPE VALIDATION")
    print("="*60)
    
    supabase = get_supabase_service_client()
    if not supabase:
        print("ERROR: Could not initialize Supabase service client.")
        return
    
    tables = ['sr_schedule', 'sr_synergy_data', 'sr_game_logs', 'sr_team_stats', 
              'sr_player_stats', 'sr_standings', 'sr_player_index']
    
    for table_name in tables:
        try:
            result = supabase.table(table_name).select('data').eq('season', CURRENT_SEASON).limit(1).execute()
            
            if result.data and result.data[0].get('data'):
                data = result.data[0]['data']
                if isinstance(data, list) and len(data) > 0:
                    sample = data[0]
                    print(f"\n{table_name}:")
                    print(f"  Data type: {type(data).__name__}")
                    print(f"  Record count: {len(data)}")
                    print(f"  Sample fields: {list(sample.keys())[:5] if isinstance(sample, dict) else 'N/A'}")
                else:
                    print(f"\n{table_name}: Empty or invalid data structure")
            else:
                print(f"\n{table_name}: No data found")
        except Exception as e:
            print(f"\n{table_name}: Error - {e}")


def generate_validation_report():
    """Generate validation report"""
    print("\n" + "="*60)
    print("GENERATING VALIDATION REPORT")
    print("="*60)
    
    report_path = project_root / 'docs' / 'sportradar_validation_report.md'
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, 'w') as f:
        f.write("# Sportradar Data Validation Report\n\n")
        f.write(f"Generated: {datetime.now()}\n\n")
        f.write("## Summary\n\n")
        f.write("This report validates the quality and completeness of Sportradar API data.\n\n")
        f.write("## Tables Validated\n\n")
        f.write("- sr_schedule\n")
        f.write("- sr_synergy_data\n")
        f.write("- sr_game_logs\n")
        f.write("- sr_team_stats\n")
        f.write("- sr_player_stats\n")
        f.write("- sr_standings\n")
        f.write("- sr_player_index\n\n")
        f.write("## Validation Results\n\n")
        f.write("Run the validation script to populate this section.\n\n")
    
    print(f"  ✓ Validation report created at: {report_path}")


def main():
    """Run all validations"""
    print(f"[{datetime.now()}] Starting Sportradar data validation for season {CURRENT_SEASON}")
    
    compare_record_counts()
    validate_data_types()
    generate_validation_report()
    
    print(f"\n[{datetime.now()}] Validation complete")

if __name__ == '__main__':
    main()

