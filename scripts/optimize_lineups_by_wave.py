#!/usr/bin/env python3
"""
Optimize DraftKings Lineups by Tip-Off Wave
Groups games by tip-off time and generates optimized lineups for each wave.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import nba_api.stats.endpoints as endpoints
from datetime import datetime, date, timedelta
import argparse
import glob
from collections import defaultdict
import pytz
from typing import List, Dict

# Import optimizer
sys.path.insert(0, str(Path(__file__).parent))
from optimize_draftkings_nba_lineup import (
    load_draftables, load_predictions, merge_draftables_with_predictions,
    add_position_flags, optimize_lineup, optimize_multiple_lineups, format_lineup_output, normalize_player_name
)


def get_matchups_with_times(selected_date: date, season: str = '2025-26'):
    """
    Fetch NBA matchups with game times for a given date.
    
    Args:
        selected_date: Date to get games for
        season: NBA season (default '2025-26')
        
    Returns:
        List of matchup dicts with game info including tip-off time
    """
    try:
        league_schedule = endpoints.ScheduleLeagueV2(
            league_id='00',
            season=season
        ).get_data_frames()[0]
        
        league_schedule['dateGame'] = pd.to_datetime(league_schedule['gameDate'])
        league_schedule['matchup'] = league_schedule['awayTeam_teamTricode'] + ' @ ' + league_schedule['homeTeam_teamTricode']
        
        # Compare date parts only
        date_games = league_schedule[
            league_schedule['dateGame'].dt.date == selected_date
        ]
        
        if len(date_games) == 0:
            return []
        
        matchups = []
        for _, row in date_games.iterrows():
            # Extract game time from gameDateTimeUTC (which includes actual tip-off time)
            # Use gameDateTimeUTC as it has the correct tip-off time in UTC
            game_datetime = pd.to_datetime(row['gameDateTimeUTC'])
            # Ensure timezone-aware datetime
            if game_datetime.tzinfo is None:
                game_datetime = pytz.UTC.localize(game_datetime.to_pydatetime())
            else:
                game_datetime = game_datetime.to_pydatetime()
            
            matchups.append({
                'matchup': row['matchup'],
                'away_team': row['awayTeam_teamTricode'],
                'home_team': row['homeTeam_teamTricode'],
                'away_team_id': int(row['awayTeam_teamId']),
                'home_team_id': int(row['homeTeam_teamId']),
                'game_date': selected_date.strftime('%Y-%m-%d'),
                'game_datetime': game_datetime
            })
        
        return matchups
    except Exception as e:
        print(f"Error fetching schedule: {e}")
        return []


def group_games_by_wave(matchups, predictions_dir):
    """
    Group games by tip-off time wave and find corresponding prediction files.
    
    Args:
        matchups: List of matchup dicts with game_datetime
        predictions_dir: Directory containing prediction CSV files
        
    Returns:
        Dict mapping wave_time_str -> list of (matchup, prediction_file_path)
    """
    # Convert game times to Central Time for grouping
    try:
        ct_tz = pytz.timezone('US/Central')
    except:
        try:
            ct_tz = pytz.timezone('America/Chicago')
        except:
            # Fallback: use UTC offset
            ct_tz = pytz.timezone('UTC')
    
    waves = defaultdict(list)
    
    for matchup in matchups:
        game_datetime = matchup['game_datetime']
        
        # Handle timezone conversion
        if isinstance(game_datetime, pd.Timestamp):
            if game_datetime.tzinfo is None:
                # NBA API typically returns UTC times
                game_datetime = pytz.UTC.localize(game_datetime.to_pydatetime())
            else:
                game_datetime = game_datetime.to_pydatetime()
        
        if isinstance(game_datetime, datetime):
            if game_datetime.tzinfo is None:
                game_datetime = pytz.UTC.localize(game_datetime)
        else:
            # Try to parse as string
            try:
                game_datetime = pd.to_datetime(game_datetime)
                if game_datetime.tzinfo is None:
                    game_datetime = pytz.UTC.localize(game_datetime.to_pydatetime())
                else:
                    game_datetime = game_datetime.to_pydatetime()
            except:
                print(f"Warning: Could not parse game time for {matchup['matchup']}")
                continue
        
        # Convert to Central Time
        game_time_ct = game_datetime.astimezone(ct_tz)
        
        # Use exact tip-off time for wave grouping (no rounding)
        # Format wave time string (e.g., "6:00 PM CT", "6:15 PM CT", "7:30 PM CT")
        hour_12 = game_time_ct.hour % 12
        if hour_12 == 0:
            hour_12 = 12
        am_pm = "AM" if game_time_ct.hour < 12 else "PM"
        minutes = game_time_ct.minute
        wave_time_str = f"{hour_12}:{minutes:02d} {am_pm} CT"
        
        # Find corresponding prediction file
        prediction_file = os.path.join(
            predictions_dir,
            f"predicted_statlines_{matchup['away_team']}_vs_{matchup['home_team']}_{matchup['game_date']}.csv"
        )
        
        if os.path.exists(prediction_file):
            waves[wave_time_str].append((matchup, prediction_file))
        else:
            print(f"Warning: Prediction file not found for {matchup['matchup']}: {prediction_file}")
    
    return waves


def combine_predictions_for_wave(prediction_files):
    """
    Combine multiple prediction CSV files into one DataFrame.
    
    Args:
        prediction_files: List of paths to prediction CSV files
        
    Returns:
        Combined DataFrame with normalized Player names
    """
    all_predictions = []
    
    for file_path in prediction_files:
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
            continue
        
        try:
            df = pd.read_csv(file_path)
            all_predictions.append(df)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue
    
    if len(all_predictions) == 0:
        return pd.DataFrame()
    
    combined_df = pd.concat(all_predictions, ignore_index=True)
    
    # Remove duplicates based on Player name (in case same player appears in multiple games)
    combined_df = combined_df.drop_duplicates(subset=['Player'], keep='first')
    
    # Add normalized Player name column (required by merge_draftables_with_predictions)
    if 'Player' in combined_df.columns and 'Player_normalized' not in combined_df.columns:
        combined_df['Player_normalized'] = combined_df['Player'].apply(normalize_player_name)
    
    return combined_df


def combine_predictions_for_waves(matchups: List[Dict], selected_wave_times: List[str], predictions_dir: str, game_date: date):
    """
    Combine prediction files from multiple waves into a single DataFrame.
    Also returns the set of team abbreviations for filtering draftables.
    
    Args:
        matchups: List of matchup dicts with game_datetime
        selected_wave_times: List of wave time strings to include (e.g., ["6:00 PM CT", "7:30 PM CT"])
        predictions_dir: Directory containing prediction CSV files
        game_date: Game date for filename matching
        
    Returns:
        Tuple of (combined_df, team_abbreviations_set)
    """
    import pytz
    
    ct_tz = pytz.timezone('US/Central')
    game_date_str = game_date.strftime('%Y-%m-%d')
    
    # Find matchups in selected waves
    selected_matchups = []
    team_abbreviations = set()
    
    for matchup in matchups:
        game_datetime = matchup['game_datetime']
        game_time_ct = game_datetime.astimezone(ct_tz)
        
        # Format wave time string
        hour_12 = game_time_ct.hour % 12
        if hour_12 == 0:
            hour_12 = 12
        am_pm = "AM" if game_time_ct.hour < 12 else "PM"
        minutes = game_time_ct.minute
        wave_time_str = f"{hour_12}:{minutes:02d} {am_pm} CT"
        
        if wave_time_str in selected_wave_times:
            selected_matchups.append(matchup)
            team_abbreviations.add(matchup['away_team'])
            team_abbreviations.add(matchup['home_team'])
    
    # Collect prediction files for selected matchups with matchup info
    prediction_files_with_matchups = []
    for matchup in selected_matchups:
        prediction_file = os.path.join(
            predictions_dir,
            f"predicted_statlines_{matchup['away_team']}_vs_{matchup['home_team']}_{game_date_str}.csv"
        )
        if os.path.exists(prediction_file):
            # Format tip time
            game_time_ct = matchup['game_datetime'].astimezone(ct_tz)
            hour_12 = game_time_ct.hour % 12
            if hour_12 == 0:
                hour_12 = 12
            am_pm = "AM" if game_time_ct.hour < 12 else "PM"
            minutes = game_time_ct.minute
            tip_time = f"{hour_12}:{minutes:02d} {am_pm} CT"
            opponent = f"{matchup['away_team']} @ {matchup['home_team']}"
            
            prediction_files_with_matchups.append({
                'file': prediction_file,
                'tip_time': tip_time,
                'opponent': opponent,
                'away_team': matchup['away_team'],
                'home_team': matchup['home_team']
            })
    
    # Combine predictions and add matchup info
    all_predictions = []
    for item in prediction_files_with_matchups:
        try:
            df = pd.read_csv(item['file'])
            # Add matchup info columns
            df['Tip_Time'] = item['tip_time']
            df['Opponent'] = item['opponent']
            # Add opponent team based on player's team
            df['Opponent_Team'] = df['Team'].apply(
                lambda team: item['home_team'] if team == item['away_team'] else item['away_team']
            )
            all_predictions.append(df)
        except Exception as e:
            print(f"Error reading {item['file']}: {e}")
            continue
    
    if len(all_predictions) == 0:
        return pd.DataFrame(), team_abbreviations
    
    combined_df = pd.concat(all_predictions, ignore_index=True)
    
    # Remove duplicates based on Player name (in case same player appears in multiple games)
    combined_df = combined_df.drop_duplicates(subset=['Player'], keep='first')
    
    # Add normalized Player name column (required by merge_draftables_with_predictions)
    if 'Player' in combined_df.columns and 'Player_normalized' not in combined_df.columns:
        combined_df['Player_normalized'] = combined_df['Player'].apply(normalize_player_name)
    
    # Filter predictions to only include players from selected teams
    if len(combined_df) > 0 and 'Team' in combined_df.columns:
        combined_df = combined_df[combined_df['Team'].isin(team_abbreviations)].copy()
    
    return combined_df, team_abbreviations


def optimize_combined_waves(game_date: date, draftables_path: str, selected_wave_times: List[str], 
                           predictions_dir: str = None, output_dir: str = None, max_salary: int = 50000):
    """
    Optimize lineups using players from all selected waves combined.
    
    Args:
        game_date: Date to optimize for
        draftables_path: Path to draftables CSV file
        selected_wave_times: List of wave time strings (e.g., ["6:00 PM CT", "7:30 PM CT"])
        predictions_dir: Directory containing prediction CSV files (default: ~/Downloads)
        output_dir: Directory to save optimized lineups (default: ~/Downloads)
        max_salary: Maximum salary cap (default: 50000)
        
    Returns:
        List of optimized lineup DataFrames
    """
    if predictions_dir is None:
        predictions_dir = os.path.expanduser("~/Downloads")
    if output_dir is None:
        output_dir = os.path.expanduser("~/Downloads")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Get matchups
    matchups = get_matchups_with_times(game_date)
    
    if len(matchups) == 0:
        print(f"No games found for {game_date.strftime('%Y-%m-%d')}")
        return []
    
    # Combine predictions from selected waves
    combined_predictions_df, team_abbreviations = combine_predictions_for_waves(
        matchups, selected_wave_times, predictions_dir, game_date
    )
    
    if len(combined_predictions_df) == 0:
        print(f"No predictions found for selected waves")
        return []
    
    print(f"Combined {len(combined_predictions_df)} players from {len(selected_wave_times)} wave(s)")
    print(f"Teams included: {', '.join(sorted(team_abbreviations))}")
    
    # Load draftables
    draftables_df = load_draftables(draftables_path)
    
    # Filter draftables by team (match players via predictions)
    # We'll filter after merging, since draftables don't have team info directly
    merged_df = merge_draftables_with_predictions(draftables_df, combined_predictions_df)
    
    # Filter to only include players from selected teams
    if 'Team' in merged_df.columns:
        merged_df = merged_df[merged_df['Team'].isin(team_abbreviations)].copy()
    
    if len(merged_df) == 0:
        print(f"No players matched after filtering by teams")
        return []
    
    # Add position flags
    merged_df = add_position_flags(merged_df)
    
    # Check if we have enough players
    players_with_preds = merged_df[merged_df['FPTS'] > 0]
    if len(players_with_preds) < 8:
        print(f"Warning: Only {len(players_with_preds)} players have predictions. May not be able to fill lineup.")
        return []
    
    # Optimize multiple lineups (5 unique lineups)
    try:
        lineup_dfs = optimize_multiple_lineups(merged_df, max_salary=max_salary, num_lineups=5, max_overlap=3)
        return lineup_dfs
    except Exception as e:
        print(f"Error optimizing lineups: {e}")
        import traceback
        traceback.print_exc()
        return []


def optimize_lineups_by_wave(game_date: date, draftables_path: str, predictions_dir: str = None, output_dir: str = None, 
                              tipoff_time_filter: str = None):
    """
    Optimize DraftKings lineups grouped by tip-off time waves.
    
    Args:
        game_date: Date to optimize for
        draftables_path: Path to draftables CSV file
        predictions_dir: Directory containing prediction CSV files (default: ~/Downloads)
        output_dir: Directory to save optimized lineups (default: ~/Downloads)
        tipoff_time_filter: Optional filter for specific tip-off time (e.g., "6:00 PM CT"). If None, optimizes all waves.
        
    Returns:
        List of output file paths
    """
    if predictions_dir is None:
        predictions_dir = os.path.expanduser("~/Downloads")
    if output_dir is None:
        output_dir = os.path.expanduser("~/Downloads")
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"=" * 60)
    print(f"Optimizing DraftKings Lineups by Tip-Off Wave")
    print(f"Date: {game_date.strftime('%Y-%m-%d')}")
    print(f"=" * 60)
    
    # Get matchups with game times
    print(f"\nFetching schedule...")
    matchups = get_matchups_with_times(game_date)
    
    if len(matchups) == 0:
        print(f"No games found for {game_date.strftime('%Y-%m-%d')}")
        return []
    
    print(f"Found {len(matchups)} game(s)")
    
    # Group games by tip-off wave
    print(f"\nGrouping games by tip-off time...")
    waves = group_games_by_wave(matchups, predictions_dir)
    
    if len(waves) == 0:
        print(f"No prediction files found in {predictions_dir}")
        return []
    
    print(f"Found {len(waves)} wave(s):")
    for wave_time, games in sorted(waves.items()):
        print(f"  {wave_time}: {len(games)} game(s)")
        for matchup, _ in games:
            print(f"    - {matchup['matchup']}")
    
    # Filter waves by tip-off time if specified
    if tipoff_time_filter:
        tipoff_time_filter = tipoff_time_filter.strip()
        if tipoff_time_filter in waves:
            print(f"\nFiltering to tip-off time: {tipoff_time_filter}")
            waves = {tipoff_time_filter: waves[tipoff_time_filter]}
        else:
            print(f"\n⚠ Warning: Tip-off time '{tipoff_time_filter}' not found.")
            print(f"Available times: {', '.join(sorted(waves.keys()))}")
            return []
    
    # Load draftables
    print(f"\nLoading draftables...")
    draftables_df = load_draftables(draftables_path)
    
    output_files = []
    
    # Optimize lineup for each wave
    for wave_time, games_in_wave in sorted(waves.items()):
        print(f"\n{'=' * 60}")
        print(f"Wave: {wave_time}")
        print(f"{'=' * 60}")
        
        prediction_files = [pred_file for _, pred_file in games_in_wave]
        
        # Combine predictions for all games in this wave
        print(f"Combining predictions from {len(prediction_files)} game(s)...")
        combined_predictions_df = combine_predictions_for_wave(prediction_files)
        
        if len(combined_predictions_df) == 0:
            print(f"Warning: No predictions found for {wave_time} wave")
            continue
        
        print(f"  Total players: {len(combined_predictions_df)}")
        
        # Merge with draftables
        print(f"Merging with draftables...")
        merged_df = merge_draftables_with_predictions(draftables_df, combined_predictions_df)
        
        if len(merged_df) == 0:
            print(f"Warning: No players matched for {wave_time} wave")
            continue
        
        # Add position flags
        print(f"Adding position eligibility flags...")
        merged_df = add_position_flags(merged_df)
        
        # Check if we have enough players with predictions
        players_with_preds = merged_df[merged_df['FPTS'] > 0]
        print(f"Players with predictions: {len(players_with_preds)}")
        
        if len(players_with_preds) < 8:
            print(f"Warning: Only {len(players_with_preds)} players have predictions. May not be able to fill lineup.")
            continue
        
        # Optimize lineup
        print(f"Optimizing lineup...")
        try:
            selected_df = optimize_lineup(merged_df, max_salary=50000)
            
            # Format output
            formatted_df = format_lineup_output(selected_df)
            
            # Save to CSV
            wave_time_safe = wave_time.replace(':', '').replace(' ', '_')
            output_filename = f"optimized_lineup_{wave_time_safe}_{game_date.strftime('%Y%m%d')}.csv"
            output_path = os.path.join(output_dir, output_filename)
            formatted_df.to_csv(output_path, index=False)
            
            # Calculate summary
            total_salary = selected_df['Salary'].sum()
            total_fpts = selected_df['FPTS'].sum()
            salary_remaining = 50000 - total_salary
            
            print(f"\n✓ Optimized lineup saved to: {output_path}")
            print(f"  Total Salary: ${total_salary:,} / $50,000")
            print(f"  Salary Remaining: ${salary_remaining:,}")
            print(f"  Total FPTS: {total_fpts:.2f}")
            print(f"  Average FPTS per Player: {total_fpts / len(selected_df):.2f}")
            
            output_files.append(output_path)
            
        except Exception as e:
            print(f"\n✗ Error optimizing lineup for {wave_time}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n{'=' * 60}")
    print(f"Summary")
    print(f"{'=' * 60}")
    print(f"Waves processed: {len(waves)}")
    print(f"Lineups created: {len(output_files)}")
    print(f"\nOutput files:")
    for f in output_files:
        print(f"  - {f}")
    
    return output_files


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Optimize DraftKings lineups grouped by tip-off time waves',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Optimize lineups for today's games (default)
  python optimize_lineups_by_wave.py --draftables ~/Downloads/draftkings_draftables_140610.csv
  
  # Optimize for a specific date
  python optimize_lineups_by_wave.py --draftables draftables.csv --date 2025-01-15
  
  # Optimize for a specific tip-off time only
  python optimize_lineups_by_wave.py --draftables draftables.csv --tipoff-time "6:00 PM CT"
  
  # Custom directories
  python optimize_lineups_by_wave.py \\
      --draftables draftables.csv \\
      --predictions-dir ~/Downloads \\
      --output-dir ~/Downloads/lineups
        """
    )
    parser.add_argument(
        '--draftables',
        type=str,
        required=True,
        help='Path to draftables CSV file (from fetch_draftkings_draftables.py)'
    )
    parser.add_argument(
        '--date',
        type=str,
        default=None,
        help='Date to optimize for (YYYY-MM-DD format). Defaults to today if not specified.'
    )
    parser.add_argument(
        '--predictions-dir',
        type=str,
        default=None,
        help='Directory containing prediction CSV files (default: ~/Downloads)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Directory to save optimized lineups (default: ~/Downloads)'
    )
    parser.add_argument(
        '--season',
        type=str,
        default='2025-26',
        help='NBA season (default: 2025-26)'
    )
    parser.add_argument(
        '--tipoff-time',
        type=str,
        default=None,
        help='Filter to specific tip-off time (e.g., "6:00 PM CT", "7:30 PM CT"). If not specified, optimizes all waves.'
    )
    
    args = parser.parse_args()
    
    # Parse date (default to today if not provided)
    if args.date is None:
        game_date = date.today()
        print(f"Using today's date: {game_date.strftime('%Y-%m-%d')}")
    else:
        try:
            game_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD format.")
            sys.exit(1)
    
    # Optimize lineups
    try:
        output_files = optimize_lineups_by_wave(
            game_date,
            args.draftables,
            args.predictions_dir,
            args.output_dir,
            args.tipoff_time
        )
        
        if len(output_files) == 0:
            print("\nNo lineups generated.")
            sys.exit(1)
        else:
            print(f"\n✓ Successfully generated {len(output_files)} optimized lineup(s)")
            sys.exit(0)
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
