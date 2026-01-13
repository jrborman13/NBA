#!/usr/bin/env python3
"""
Test script for Sportradar API implementation
Tests schedule fetch and game logs fetch with new header-based authentication.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'new-streamlit-app' / 'player-app'))

from datetime import datetime, UTC, timedelta
from sportradar_config import fetch_sportradar_nba, is_sportradar_configured
from supabase_config import get_supabase_service_client
from sportradar_data_reader import get_schedule_from_db

CURRENT_SEASON = '2025-26'

def test_schedule_fetch():
    """Test fetching schedule for a specific date"""
    print("=" * 60)
    print("TEST 1: Schedule Fetch")
    print("=" * 60)
    
    if not is_sportradar_configured():
        print("✗ ERROR: Sportradar API keys not configured")
        return False
    
    # Test with a known date (2025-01-06 from your example)
    test_date = datetime(2025, 1, 6).date()
    print(f"\nTesting schedule fetch for {test_date}...")
    
    try:
        # Use the working endpoint format
        year = test_date.year
        month = test_date.month
        day = test_date.day
        endpoint = f"games/{year}/{month:02d}/{day:02d}/schedule.json"
        
        print(f"Endpoint: {endpoint}")
        print("Using header-based authentication...")
        
        response_data = fetch_sportradar_nba(endpoint, use_headers=True)
        
        if 'games' in response_data:
            games = response_data['games']
            print(f"✓ Success! Found {len(games)} games")
            
            if len(games) > 0:
                print("\nFirst game sample:")
                first_game = games[0]
                print(f"  Game ID: {first_game.get('id', 'N/A')}")
                print(f"  Scheduled: {first_game.get('scheduled', 'N/A')}")
                print(f"  Status: {first_game.get('status', 'N/A')}")
                if 'home' in first_game:
                    print(f"  Home: {first_game['home'].get('name', 'N/A')}")
                if 'away' in first_game:
                    print(f"  Away: {first_game['away'].get('name', 'N/A')}")
            
            return True
        else:
            print("✗ No 'games' key in response")
            print(f"Response keys: {list(response_data.keys())}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_boxscore_fetch():
    """Test fetching box score for a specific game"""
    print("\n" + "=" * 60)
    print("TEST 2: Box Score Fetch")
    print("=" * 60)
    
    if not is_sportradar_configured():
        print("✗ ERROR: Sportradar API keys not configured")
        return False
    
    # First, try to get a game ID from the schedule
    print("\nReading schedule from Supabase...")
    schedule_df = get_schedule_from_db(CURRENT_SEASON)
    
    if schedule_df is None or len(schedule_df) == 0:
        print("✗ No schedule found. Please run sportradar_fetch_schedule.py first.")
        return False
    
    print(f"✓ Found {len(schedule_df)} games in schedule")
    
    # Try to find a completed game
    test_game_id = None
    for idx, game_row in schedule_df.iterrows():
        game = game_row.to_dict() if isinstance(game_row, pd.Series) else game_row
        game_status = str(game.get('status', '')).lower()
        game_id = game.get('id', '')
        
        if game_status in ['closed', 'complete', 'completed', 'final'] and game_id:
            test_game_id = game_id
            print(f"\nFound completed game: {game_id}")
            print(f"  Status: {game.get('status', 'N/A')}")
            print(f"  Scheduled: {game.get('scheduled', 'N/A')}")
            break
    
    if not test_game_id:
        print("✗ No completed games found in schedule")
        print("  Note: You may need to wait for games to complete or use a different date range")
        return False
    
    try:
        endpoint = f"games/{test_game_id}/boxscore.json"
        print(f"\nFetching box score for game {test_game_id}...")
        print(f"Endpoint: {endpoint}")
        print("Using header-based authentication...")
        
        boxscore_data = fetch_sportradar_nba(endpoint, use_headers=True)
        
        if 'game' in boxscore_data:
            game = boxscore_data['game']
            print(f"✓ Success! Box score retrieved")
            print(f"\nGame Info:")
            print(f"  Game ID: {game.get('id', 'N/A')}")
            print(f"  Scheduled: {game.get('scheduled', 'N/A')}")
            print(f"  Status: {game.get('status', 'N/A')}")
            
            if 'home' in game:
                home = game['home']
                print(f"\n  Home Team: {home.get('name', 'N/A')}")
                if 'players' in home:
                    print(f"    Players: {len(home['players'])}")
                if 'statistics' in home:
                    stats = home['statistics']
                    print(f"    Points: {stats.get('points', 'N/A')}")
            
            if 'away' in game:
                away = game['away']
                print(f"\n  Away Team: {away.get('name', 'N/A')}")
                if 'players' in away:
                    print(f"    Players: {len(away['players'])}")
                if 'statistics' in away:
                    stats = away['statistics']
                    print(f"    Points: {stats.get('points', 'N/A')}")
            
            return True
        else:
            print("✗ No 'game' key in response")
            print(f"Response keys: {list(boxscore_data.keys())}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_schedule_storage():
    """Test storing schedule in Supabase"""
    print("\n" + "=" * 60)
    print("TEST 3: Schedule Storage")
    print("=" * 60)
    
    from scripts.sportradar_fetch_schedule import fetch_and_store_schedule
    
    # Test with today's date
    today = datetime.now(UTC).date()
    print(f"\nTesting schedule fetch and storage for {today}...")
    
    try:
        success = fetch_and_store_schedule(date=today)
        if success:
            print("✓ Schedule stored successfully")
            
            # Verify it's in the database
            schedule_df = get_schedule_from_db(CURRENT_SEASON)
            if schedule_df is not None and len(schedule_df) > 0:
                print(f"✓ Verified: {len(schedule_df)} games in database")
                return True
            else:
                print("✗ Schedule not found in database after storage")
                return False
        else:
            print("✗ Schedule fetch/storage failed")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_game_logs_fetch():
    """Test fetching game logs"""
    print("\n" + "=" * 60)
    print("TEST 4: Game Logs Fetch")
    print("=" * 60)
    
    from scripts.sportradar_fetch_game_logs import fetch_and_store_game_logs
    
    print("\nTesting game logs fetch...")
    print("(This will read schedule, filter completed games, and fetch box scores)")
    
    try:
        success = fetch_and_store_game_logs()
        if success:
            print("✓ Game logs fetched and stored successfully")
            
            # Verify it's in the database
            supabase = get_supabase_service_client()
            if supabase:
                result = supabase.table('sr_game_logs').select('*').eq('season', CURRENT_SEASON).execute()
                if result.data:
                    print(f"\n✓ Verified: Found {len(result.data)} log entries in database")
                    for entry in result.data:
                        log_type = entry.get('log_type', 'unknown')
                        data = entry.get('data', [])
                        print(f"  - {log_type}: {len(data)} records")
                    return True
                else:
                    print("✗ No game logs found in database")
                    return False
            else:
                print("✗ Could not connect to Supabase")
                return False
        else:
            print("✗ Game logs fetch failed")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import pandas as pd
    
    print("\n" + "=" * 60)
    print("SPORTRADAR API IMPLEMENTATION TEST SUITE")
    print("=" * 60)
    
    results = []
    
    # Test 1: Schedule fetch
    results.append(("Schedule Fetch", test_schedule_fetch()))
    
    # Test 2: Box score fetch
    results.append(("Box Score Fetch", test_boxscore_fetch()))
    
    # Test 3: Schedule storage
    results.append(("Schedule Storage", test_schedule_storage()))
    
    # Test 4: Game logs fetch (optional - may fail if no completed games)
    try:
        results.append(("Game Logs Fetch", test_game_logs_fetch()))
    except Exception as e:
        print(f"\n⚠ Game Logs test skipped due to error: {e}")
        results.append(("Game Logs Fetch", False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n⚠ {total - passed} test(s) failed")
        sys.exit(1)

