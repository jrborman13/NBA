"""
One-time script to build historical player season stats CSV.
Fetches data from 2005-06 to 2024-25 and saves to new-streamlit-app/files/historical_player_season_stats.csv

Run this script once to build the historical database, then the Streamlit app
will only need to update the current season data.
"""

import nba_api.stats.endpoints
import pandas as pd
import os

league_id = '00'  # NBA league ID

def build_historical_csv(csv_path='new-streamlit-app/files/historical_player_season_stats.csv'):
    """
    Build CSV file with player season stats from 2005-06 to 2024-25.
    Includes all players, one row per player per season.
    
    Args:
        csv_path: Path to the CSV file
    """
    # Generate list of seasons from 2005-06 to 2024-25
    seasons = []
    start_year = 2005
    end_year = 2024
    
    for year in range(start_year, end_year + 1):
        next_year_short = str(year + 1)[2:4]
        seasons.append(f"{year}-{next_year_short}")
    
    print(f"Fetching data for {len(seasons)} seasons (2005-06 to 2024-25)...")
    print("This may take several minutes...")
    
    # Fetch data for all seasons
    all_season_data = []
    
    for i, season in enumerate(seasons, 1):
        try:
            print(f"Fetching {season} ({i}/{len(seasons)})...")
            # Get LeagueDashPlayerStats for this season (all players)
            player_stats = nba_api.stats.endpoints.LeagueDashPlayerStats(
                season=season,
                league_id_nullable=league_id,
                per_mode_detailed='PerGame',
                season_type_all_star='Regular Season'
            ).get_data_frames()[0]
            
            # Add season column
            player_stats['SEASON'] = season
            
            all_season_data.append(player_stats)
            print(f"  ✓ {season} - {len(player_stats)} players")
        except Exception as e:
            print(f"  ✗ Error fetching {season}: {e}")
            continue
    
    if all_season_data:
        print("\nCombining all season data...")
        combined_df = pd.concat(all_season_data, ignore_index=True)
        
        # Remove duplicates (same player, same season) - keep the most recent entry
        if 'PLAYER_ID' in combined_df.columns and 'SEASON' in combined_df.columns:
            combined_df = combined_df.drop_duplicates(subset=['PLAYER_ID', 'SEASON'], keep='last')
        
        # Save to CSV
        combined_df.to_csv(csv_path, index=False)
        print(f"\n✓ Successfully saved {len(combined_df)} rows to {csv_path}")
        print(f"  Seasons: {sorted(combined_df['SEASON'].unique())}")
        print(f"  Players: {combined_df['PLAYER_ID'].nunique()}")
    else:
        print("\n✗ No data was fetched. Please check your connection and try again.")


if __name__ == "__main__":
    # Check if CSV already exists
    csv_path = 'new-streamlit-app/files/historical_player_season_stats.csv'
    
    # Create files directory if it doesn't exist
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    if os.path.exists(csv_path):
        response = input(f"{csv_path} already exists. Overwrite? (y/n): ")
        if response.lower() != 'y':
            print("Cancelled.")
            exit(0)
        print(f"Overwriting {csv_path}...\n")
    
    build_historical_csv(csv_path)
    print("\nDone! You can now run the Streamlit app.")

