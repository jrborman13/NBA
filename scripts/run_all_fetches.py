#!/usr/bin/env python3
"""
Run All NBA Data Fetches
Runs all fetch scripts in sequence with proper error handling.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

scripts_dir = Path(__file__).parent
scripts = [
    'fetch_nba_team_stats.py',
    'fetch_nba_player_stats.py',
    'fetch_nba_game_logs.py',
    'fetch_nba_synergy_data.py',
    'fetch_nba_schedule.py',
    'fetch_nba_standings.py',
    'fetch_nba_player_index.py',
    'fetch_nba_team_onoff.py',
    'fetch_nba_drives_stats.py',
    'fetch_nba_pbpstats.py'
]

def run_all():
    """Run all fetch scripts"""
    print(f"[{datetime.now()}] Starting all NBA data fetches...\n")
    
    results = {}
    
    for script in scripts:
        script_path = scripts_dir / script
        if not script_path.exists():
            print(f"⚠️  Script not found: {script}")
            results[script] = False
            continue
        
        print(f"\n{'='*60}")
        print(f"Running {script}...")
        print(f"{'='*60}")
        
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(scripts_dir),
                capture_output=False,
                text=True
            )
            results[script] = result.returncode == 0
        except Exception as e:
            print(f"✗ Error running {script}: {e}")
            results[script] = False
    
    print(f"\n{'='*60}")
    print(f"[{datetime.now()}] All fetches completed")
    print(f"{'='*60}")
    
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)
    
    print(f"\nResults: {success_count}/{total_count} successful")
    
    for script, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {script}")
    
    return success_count == total_count

if __name__ == '__main__':
    success = run_all()
    sys.exit(0 if success else 1)

