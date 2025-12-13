import nba_api.stats.endpoints
import requests
import json
import pandas as pd
import nba_api
import altair as alt
import streamlit as st
from datetime import datetime
from datetime import datetime, date
import os

current_season = '2025-26'
league_id = '00'  # NBA league ID

# Get players dataframe from PlayerIndex endpoint
def get_players_dataframe():
    """Get players dataframe from PlayerIndex endpoint for the current season"""
    try:
        # Try lowercase parameter names first (most common)
        player_index = nba_api.stats.endpoints.PlayerIndex(
            league_id=league_id,
            season=current_season
        )
        players_df = player_index.get_data_frames()[0]
        if len(players_df) > 0 and 'PERSON_ID' in players_df.columns:
            return players_df
    except Exception as e:
        pass
    
    try:
        # Try nullable parameter names
        player_index = nba_api.stats.endpoints.PlayerIndex(
            league_id_nullable=league_id,
            season_nullable=current_season
        )
        players_df = player_index.get_data_frames()[0]
        if len(players_df) > 0 and 'PERSON_ID' in players_df.columns:
            return players_df
    except Exception as e:
        pass
    
    try:
        # Try capitalized parameter names
        player_index = nba_api.stats.endpoints.PlayerIndex(
            LeagueID=league_id,
            Season=current_season
        )
        players_df = player_index.get_data_frames()[0]
        if len(players_df) > 0 and 'PERSON_ID' in players_df.columns:
            return players_df
    except Exception as e:
        pass
    
    # Return empty dataframe if all attempts fail
    return pd.DataFrame()

# Get list of players from PlayerIndex endpoint
def get_player_list():
    """Get list of NBA player IDs for the current season"""
    players_df = get_players_dataframe()
    if len(players_df) > 0:
        return players_df['PERSON_ID'].astype(str).tolist()
    else:
        # Fallback to some default player IDs if API fails
        return ['1630162', '203999', '1629027']  # Anthony Edwards, Nikola Jokic, Trae Young

# Get player IDs list (will be cached in Streamlit app if needed)
try:
    player_ids = get_player_list()
except:
    player_ids = ['1630162', '203999', '1629027']  # Fallback

# Default selected player (first in list)
default_player_id = player_ids[0] if player_ids else '1630162'
selected_player_id = default_player_id


def get_player_name(player_id, players_df=None):
    """
    Get player name for a given player_id using the players dataframe.
    Used for display in selectbox.
    """
    # If players_df is not provided, get it
    if players_df is None:
        players_df = get_players_dataframe()
    
    try:
        # Convert player_id to int for matching
        player_id_int = int(player_id)
        
        # Find the player in the dataframe
        player_row = players_df[players_df['PERSON_ID'] == player_id_int]
        
        if len(player_row) > 0:
            # Get first name and last name, combine them
            first_name = player_row['PLAYER_FIRST_NAME'].iloc[0]
            last_name = player_row['PLAYER_LAST_NAME'].iloc[0]
            return f"{first_name} {last_name}"
        else:
            return f"Player {player_id}"
    except Exception as e:
        return f"Player {player_id}"


def get_player_options():
    """
    Get list of (player_id, player_name) tuples for selectbox.
    """
    return [(pid, get_player_name(pid)) for pid in player_ids]

def format_season(number):
    """
    Given a number from 0 to 25, return a string with the correct ordinal suffix.
    E.g., 1 -> '1st season', 2 -> '2nd season', 3 -> '3rd season', 4 -> '4th season', etc.
    """
    if number < 0 or number > 25:
        raise ValueError("Number must be between 0 and 25.")

    if 11 <= number % 100 <= 13:
        suffix = 'th'
    else:
        last_digit = number % 10
        if last_digit == 1:
            suffix = 'st'
        elif last_digit == 2:
            suffix = 'nd'
        elif last_digit == 3:
            suffix = 'rd'
        else:
            suffix = 'th'

    return f"{number}{suffix} Season"


def format_readable_date(dt):
    """
    Takes a datetime object and returns a string in the format 'Month Day, Year'.
    Example: datetime(1996, 9, 23) -> 'September 23, 1996'
    """
    if not isinstance(dt, datetime):
        raise ValueError("Input must be a datetime object.")

    return dt.strftime('%B %d, %Y')


def calculate_age_decimal(birthdate):
    """
    Takes a datetime object representing the birthdate and returns the age as a decimal.
    Example: datetime(1996, 9, 23) -> 28.7 (as of June 2025)
    """
    if not isinstance(birthdate, datetime):
        raise ValueError("Input must be a datetime object.")

    today = date.today()
    delta_days = (today - birthdate.date()).days
    age_years = delta_days / 365.25  # Use 365.25 to account for leap years

    return round(age_years, 1)


def format_percentile(percentile):
    """
    Format percentile rank with appropriate ordinal suffix.
    Example: 1 -> "1st", 2 -> "2nd", 3 -> "3rd", 4 -> "4th", 11 -> "11th", 21 -> "21st"
    """
    if percentile is None or pd.isna(percentile):
        return "N/A"
    
    percentile = int(round(percentile))
    
    # Handle special cases for 11th, 12th, 13th
    if 11 <= percentile % 100 <= 13:
        suffix = 'th'
    else:
        last_digit = percentile % 10
        if last_digit == 1:
            suffix = 'st'
        elif last_digit == 2:
            suffix = 'nd'
        elif last_digit == 3:
            suffix = 'rd'
        else:
            suffix = 'th'
    
    return f"{percentile}{suffix}"


def calculate_percentile_rank(player_value, all_values):
    """
    Calculate percentile rank of a player's stat value compared to all players.
    Returns a value from 0-100 representing the percentile.
    """
    if len(all_values) == 0 or pd.isna(player_value):
        return None
    
    # Remove NaN values
    valid_values = all_values.dropna()
    if len(valid_values) == 0:
        return None
    
    # Calculate percentile rank (0-100 scale where 100 is best)
    percentile = (valid_values < player_value).sum() / len(valid_values) * 100
    return percentile


def get_player_data(player_id, players_df=None):
    """
    Get all player data for a given player_id.
    Returns a dictionary with all player information, stats, and chart.
    
    Args:
        player_id: Player ID as string
        players_df: Optional players dataframe from PlayerIndex (if None, will fetch it)
    """
    # Get players dataframe if not provided
    if players_df is None:
        players_df = get_players_dataframe()
    
    # Validate that players_df has the required columns
    if players_df is None or len(players_df) == 0:
        raise ValueError("Players dataframe is empty. Please check PlayerIndex API connection.")
    
    if 'PERSON_ID' not in players_df.columns:
        raise ValueError(f"Players dataframe missing 'PERSON_ID' column. Available columns: {list(players_df.columns)}")
    
    # Get player info from PlayerIndex dataframe
    player_id_int = int(player_id)
    player_row = players_df[players_df['PERSON_ID'] == player_id_int]
    
    if len(player_row) == 0:
        raise ValueError(f"Player {player_id} not found in PlayerIndex")
    
    player_info_name = f"{player_row['PLAYER_FIRST_NAME'].iloc[0]} {player_row['PLAYER_LAST_NAME'].iloc[0]}"
    player_info_team_city = player_row['TEAM_CITY'].iloc[0]
    player_info_team_name = player_row['TEAM_NAME'].iloc[0]
    player_info_team = f'{player_info_team_city} {player_info_team_name}'
    player_info_number = player_row['JERSEY_NUMBER'].iloc[0]
    player_team_id = str(player_row['TEAM_ID'].iloc[0])
    player_team_abbrev = player_row['TEAM_ABBREVIATION'].iloc[0]
    player_info_height = player_row['HEIGHT'].iloc[0]
    player_info_weight = player_row['WEIGHT'].iloc[0]
    player_info_position = player_row['POSITION'].iloc[0]

    # Get game logs for all players (cached at module level)
    game_logs_ex = nba_api.stats.endpoints.PlayerGameLogs(
        season_nullable=current_season,
        league_id_nullable=league_id
    ).get_data_frames()[0]

    # Get player stats
    player_stats = nba_api.stats.endpoints.LeagueDashPlayerStats(
        season=current_season,
        league_id_nullable=league_id,
        per_mode_detailed='PerGame',
        season_type_all_star='Regular Season'
    ).get_data_frames()

    player_stats_per_game = player_stats[0]
    filtered_player_stats = player_stats_per_game[player_stats_per_game['PLAYER_ID'] == int(player_id)].reset_index(drop=True)

    # NBA team colors (primary colors)
    nba_teams_colors = pd.DataFrame([
        {'team_id': '1610612737', 'team_name': 'Atlanta Hawks', 'color': '#E03A3E'},
        {'team_id': '1610612738', 'team_name': 'Boston Celtics', 'color': '#007A33'},
        {'team_id': '1610612751', 'team_name': 'Brooklyn Nets', 'color': '#000000'},
        {'team_id': '1610612766', 'team_name': 'Charlotte Hornets', 'color': '#1D1160'},
        {'team_id': '1610612741', 'team_name': 'Chicago Bulls', 'color': '#CE1141'},
        {'team_id': '1610612739', 'team_name': 'Cleveland Cavaliers', 'color': '#860038'},
        {'team_id': '1610612742', 'team_name': 'Dallas Mavericks', 'color': '#00538C'},
        {'team_id': '1610612743', 'team_name': 'Denver Nuggets', 'color': '#0E2240'},
        {'team_id': '1610612765', 'team_name': 'Detroit Pistons', 'color': '#C8102E'},
        {'team_id': '1610612744', 'team_name': 'Golden State Warriors', 'color': '#1D428A'},
        {'team_id': '1610612745', 'team_name': 'Houston Rockets', 'color': '#CE1141'},
        {'team_id': '1610612754', 'team_name': 'Indiana Pacers', 'color': '#002D62'},
        {'team_id': '1610612746', 'team_name': 'LA Clippers', 'color': '#C8102E'},
        {'team_id': '1610612747', 'team_name': 'Los Angeles Lakers', 'color': '#552583'},
        {'team_id': '1610612763', 'team_name': 'Memphis Grizzlies', 'color': '#5D76A9'},
        {'team_id': '1610612748', 'team_name': 'Miami Heat', 'color': '#98002E'},
        {'team_id': '1610612749', 'team_name': 'Milwaukee Bucks', 'color': '#00471B'},
        {'team_id': '1610612750', 'team_name': 'Minnesota Timberwolves', 'color': '#0C2340'},
        {'team_id': '1610612740', 'team_name': 'New Orleans Pelicans', 'color': '#0C2340'},
        {'team_id': '1610612752', 'team_name': 'New York Knicks', 'color': '#006BB6'},
        {'team_id': '1610612760', 'team_name': 'Oklahoma City Thunder', 'color': '#007AC1'},
        {'team_id': '1610612753', 'team_name': 'Orlando Magic', 'color': '#0077C0'},
        {'team_id': '1610612755', 'team_name': 'Philadelphia 76ers', 'color': '#006BB6'},
        {'team_id': '1610612756', 'team_name': 'Phoenix Suns', 'color': '#1D1160'},
        {'team_id': '1610612757', 'team_name': 'Portland Trail Blazers', 'color': '#E03A3E'},
        {'team_id': '1610612758', 'team_name': 'Sacramento Kings', 'color': '#5A2D81'},
        {'team_id': '1610612759', 'team_name': 'San Antonio Spurs', 'color': '#C4CED4'},
        {'team_id': '1610612761', 'team_name': 'Toronto Raptors', 'color': '#CE1141'},
        {'team_id': '1610612762', 'team_name': 'Utah Jazz', 'color': '#002B5C'},
        {'team_id': '1610612764', 'team_name': 'Washington Wizards', 'color': '#002B5C'}
    ])

    # Try to get team color, use default if not found
    team_color_match = nba_teams_colors[nba_teams_colors['team_id'] == player_team_id]
    if not team_color_match.empty:
        team_color = team_color_match['color'].iloc[0]
    else:
        team_color = '#000000'  # Default black if team not found

    # Get game logs for this specific player
    player_game_logs = game_logs_ex.loc[game_logs_ex['PLAYER_ID'] == int(player_id)].copy()
    
    # Filter out preseason games (GAME_ID format: 0022500191, 3rd character indicates game type)
    # '0' = preseason, '2' = regular season, '4' = playoffs
    # Keep regular season ('2') and playoffs ('4')
    if len(player_game_logs) > 0:
        player_game_logs = player_game_logs[
            player_game_logs['GAME_ID'].astype(str).str[2].isin(['2', '4'])
        ].copy()
    
    # Calculate averages table (last 3, 5, 10 games, and season)
    averages_df = None
    if len(player_game_logs) > 0:
        # Sort by date descending (most recent first) for averages calculation
        player_game_logs_desc = player_game_logs.sort_values(by='GAME_DATE', ascending=False).copy()
        
        # Helper function to calculate averages for a given number of games
        def calculate_averages(games_subset, label):
            if len(games_subset) == 0:
                return None
            
            # Calculate totals for percentages
            total_fg2m = (games_subset['FGM'] - games_subset['FG3M']).sum()
            total_fg2a = (games_subset['FGA'] - games_subset['FG3A']).sum()
            total_fg3m = games_subset['FG3M'].sum()
            total_fg3a = games_subset['FG3A'].sum()
            total_ftm = games_subset['FTM'].sum()
            total_fta = games_subset['FTA'].sum()
            
            # Calculate percentages from totals
            fg2_pct = round((total_fg2m / total_fg2a * 100), 1) if total_fg2a > 0 else 0.0
            fg3_pct = round((total_fg3m / total_fg3a * 100), 1) if total_fg3a > 0 else 0.0
            ft_pct = round((total_ftm / total_fta * 100), 1) if total_fta > 0 else 0.0
            
            # Calculate PRA (Points + Rebounds + Assists)
            pts_avg = round(games_subset['PTS'].mean(), 1)
            reb_avg = round(games_subset['REB'].mean(), 1)
            ast_avg = round(games_subset['AST'].mean(), 1)
            pra_avg = round(pts_avg + reb_avg + ast_avg, 1)
            
            return {
                'Period': label,
                'MIN': round(games_subset['MIN'].mean(), 1),
                'PTS': pts_avg,
                'REB': reb_avg,
                'AST': ast_avg,
                'PRA': pra_avg,
                'STL': round(games_subset['STL'].mean(), 1),
                'BLK': round(games_subset['BLK'].mean(), 1),
                'TOV': round(games_subset['TOV'].mean(), 1),
                '2PM': round((games_subset['FGM'] - games_subset['FG3M']).mean(), 1),
                '2PA': round((games_subset['FGA'] - games_subset['FG3A']).mean(), 1),
                '2P%': f"{fg2_pct:.1f}%",
                '3PM': round(games_subset['FG3M'].mean(), 1),
                '3PA': round(games_subset['FG3A'].mean(), 1),
                '3P%': f"{fg3_pct:.1f}%",
                'FTM': round(games_subset['FTM'].mean(), 1),
                'FTA': round(games_subset['FTA'].mean(), 1),
                'FT%': f"{ft_pct:.1f}%",
            }
        
        # Calculate averages for different periods
        rows = []
        
        # Last 3 games
        if len(player_game_logs_desc) >= 3:
            rows.append(calculate_averages(player_game_logs_desc.head(3), 'Last 3 Games'))
        elif len(player_game_logs_desc) > 0:
            rows.append(calculate_averages(player_game_logs_desc, f'Last {len(player_game_logs_desc)} Games'))
        
        # Last 5 games
        if len(player_game_logs_desc) >= 5:
            rows.append(calculate_averages(player_game_logs_desc.head(5), 'Last 5 Games'))
        elif len(player_game_logs_desc) > 0:
            rows.append(calculate_averages(player_game_logs_desc, f'Last {len(player_game_logs_desc)} Games'))
        
        # Last 10 games
        if len(player_game_logs_desc) >= 10:
            rows.append(calculate_averages(player_game_logs_desc.head(10), 'Last 10 Games'))
        elif len(player_game_logs_desc) > 0:
            rows.append(calculate_averages(player_game_logs_desc, f'Last {len(player_game_logs_desc)} Games'))
        
        # Season stats (all games)
        rows.append(calculate_averages(player_game_logs_desc, 'Season'))
        
        # Create dataframe
        if rows:
            averages_df = pd.DataFrame(rows)
    
    # Format recent game logs for display (most recent 10 games)
    recent_games_df = None
    if len(player_game_logs) > 0:
        # Sort all games chronologically (oldest to newest) to assign season game numbers
        player_game_logs_sorted = player_game_logs.sort_values(by='GAME_DATE', ascending=True).copy()
        player_game_logs_sorted['season_game_num'] = range(1, len(player_game_logs_sorted) + 1)
        
        # Now get most recent 10 games (sorted descending by date)
        player_game_logs_recent = player_game_logs.sort_values(by='GAME_DATE', ascending=False).head(10).copy()
        
        # Merge with season game numbers
        recent_games = player_game_logs_recent.merge(
            player_game_logs_sorted[['GAME_ID', 'season_game_num']],
            on='GAME_ID',
            how='left'
        )
        
        # Format game date
        recent_games['GAME_DATE_FORMATTED'] = pd.to_datetime(recent_games['GAME_DATE']).dt.strftime('%m/%d/%Y')
        
        # Extract opponent from MATCHUP (format: "LAL @ PHX" or "LAL vs. PHX")
        def extract_opponent(matchup):
            if pd.isna(matchup):
                return 'N/A'
            # MATCHUP format: "TEAM @ OPP" or "TEAM vs. OPP"
            # Split and get the opponent (last part)
            parts = str(matchup).split()
            if len(parts) >= 3:
                # Get opponent abbreviation (last part)
                return parts[-1]
            elif len(parts) == 2:
                # Handle case like "LAL @PHX" (no space)
                return parts[1].replace('@', '').replace('vs.', '')
            return matchup
        
        recent_games['OPPONENT'] = recent_games['MATCHUP'].apply(extract_opponent)
        
        # Use season_game_num as the game number
        recent_games['game_num'] = recent_games['season_game_num']
        
        # Calculate 2-pointers made, attempted, and percentage
        recent_games['FG2M'] = recent_games['FGM'] - recent_games['FG3M']
        recent_games['FG2A'] = recent_games['FGA'] - recent_games['FG3A']
        # Calculate 2P% with division by zero handling
        recent_games['FG2_PCT'] = recent_games.apply(
            lambda row: round(row['FG2M'] / row['FG2A'] * 100, 1) if row['FG2A'] > 0 else 0.0,
            axis=1
        )
        
        # Format percentages as strings with %
        recent_games['FG2_PCT_STR'] = recent_games['FG2_PCT'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "0.0%")
        recent_games['FG3_PCT_STR'] = (recent_games['FG3_PCT'] * 100).round(1).apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "0.0%")
        recent_games['FT_PCT_STR'] = (recent_games['FT_PCT'] * 100).round(1).apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "0.0%")
        
        # Round minutes to nearest whole number
        recent_games['MIN_ROUNDED'] = recent_games['MIN'].round().astype(int)
        
        # Calculate PRA (Points + Rebounds + Assists) for each game
        recent_games['PRA'] = recent_games['PTS'] + recent_games['REB'] + recent_games['AST']
        
        # Select and rename columns for display (REB before AST, PRA after AST)
        recent_games_df = recent_games[[
            'game_num', 'GAME_DATE_FORMATTED', 'OPPONENT', 'MIN_ROUNDED', 'PTS', 'REB', 'AST', 'PRA',
            'STL', 'BLK', 'TOV', 'FG2M', 'FG2A', 'FG2_PCT_STR', 
            'FG3M', 'FG3A', 'FG3_PCT_STR', 'FTM', 'FTA', 'FT_PCT_STR'
        ]].copy()
        
        # Rename columns for display
        recent_games_df.columns = [
            'Game', 'Date', 'Opponent', 'MIN', 'PTS', 'REB', 'AST', 'PRA',
            'STL', 'BLK', 'TOV', '2PM', '2PA', '2P%', 
            '3PM', '3PA', '3P%', 'FTM', 'FTA', 'FT%'
        ]
        
        # Reset index
        recent_games_df = recent_games_df.reset_index(drop=True)
    
    # Sort game logs ascending for chart (oldest to newest) - already filtered and sorted above
    if len(player_game_logs) > 0:
        player_game_logs = player_game_logs.sort_values(by='GAME_DATE', ascending=True)
    
    # Handle empty game logs
    if len(player_game_logs) == 0:
        # Create empty chart with message if no game logs
        empty_df = pd.DataFrame({'game_num': [1], 'PTS': [0]})
        final_chart = alt.Chart(empty_df).mark_text(
            text='No games played this season',
            fontSize=16,
            color='gray'
        ).encode(
            x=alt.value(300),
            y=alt.value(250)
        ).properties(
            title="Points per Game with 5-Game Moving Average",
            width=600,
            height=500
        )
    else:
        player_game_logs = player_game_logs.assign(game_num=range(1, len(player_game_logs) + 1))
        # Calculate 5-game moving average
        player_game_logs['PTS_MA'] = player_game_logs['PTS'].rolling(window=5, min_periods=1).mean()

        # Create the base chart for actual points
        pts_chart = alt.Chart(player_game_logs).mark_line(color='#f76517').encode(
            x='game_num:Q',
            y='PTS:Q',
            tooltip=['game_num', 'PTS']
        ).properties(
            title="Points per Game with 5-Game Moving Average",
            width=600,
            height=500
        )

        # Create the moving average line
        ma_chart = alt.Chart(player_game_logs).mark_line(color='#175aaa').encode(
            x='game_num:Q',
            y='PTS_MA:Q',
            tooltip=['game_num', 'PTS_MA']
        )

        # Combine both charts
        final_chart = pts_chart + ma_chart

    # NBA headshot and logo URLs
    headshot = f'https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png'
    logo = f'https://cdn.nba.com/logos/nba/{player_team_id}/primary/L/logo.svg'

    # Player stats - handle case where player has no stats
    if len(filtered_player_stats) == 0:
        # Default to 0.0 if no stats available
        player_pts_pg = 0.0
        player_reb_pg = 0.0
        player_ast_pg = 0.0
        player_pra_pg = 0.0
        player_stl_pg = 0.0
        player_blk_pg = 0.0
        # Set percentile ranks to None
        pts_percentile = None
        reb_percentile = None
        ast_percentile = None
        pra_percentile = None
        stl_percentile = None
        blk_percentile = None
    else:
        player_pts_pg = float(filtered_player_stats['PTS'].iloc[0])
        player_reb_pg = float(filtered_player_stats['REB'].iloc[0])
        player_ast_pg = float(filtered_player_stats['AST'].iloc[0])
        player_pra_pg = player_pts_pg + player_reb_pg + player_ast_pg
        player_stl_pg = float(filtered_player_stats['STL'].iloc[0])
        player_blk_pg = float(filtered_player_stats['BLK'].iloc[0])
        
        # Calculate PRA for all players for percentile calculation
        player_stats_per_game['PRA'] = player_stats_per_game['PTS'] + player_stats_per_game['REB'] + player_stats_per_game['AST']
        
        # Calculate percentile ranks for each stat
        pts_percentile = calculate_percentile_rank(player_pts_pg, player_stats_per_game['PTS'])
        reb_percentile = calculate_percentile_rank(player_reb_pg, player_stats_per_game['REB'])
        ast_percentile = calculate_percentile_rank(player_ast_pg, player_stats_per_game['AST'])
        pra_percentile = calculate_percentile_rank(player_pra_pg, player_stats_per_game['PRA'])
        stl_percentile = calculate_percentile_rank(player_stl_pg, player_stats_per_game['STL'])
        blk_percentile = calculate_percentile_rank(player_blk_pg, player_stats_per_game['BLK'])

    # Return all data as a dictionary
    return {
        'player_info_name': player_info_name,
        'player_info_team': player_info_team,
        'player_info_number': player_info_number,
        'player_info_position': player_info_position,
        'player_info_height': player_info_height,
        'player_info_weight': player_info_weight,
        'team_color': team_color,
        'headshot': headshot,
        'logo': logo,
        'final_chart': final_chart,
        'player_pts_pg': player_pts_pg,
        'player_reb_pg': player_reb_pg,
        'player_ast_pg': player_ast_pg,
        'player_pra_pg': player_pra_pg,
        'player_stl_pg': player_stl_pg,
        'player_blk_pg': player_blk_pg,
        'pts_percentile': pts_percentile,
        'reb_percentile': reb_percentile,
        'ast_percentile': ast_percentile,
        'pra_percentile': pra_percentile,
        'stl_percentile': stl_percentile,
        'blk_percentile': blk_percentile,
        'recent_games_df': recent_games_df,
        'averages_df': averages_df,
    }


def build_season_stats_csv(csv_path='new-streamlit-app/files/historical_player_season_stats.csv'):
    """
    Update CSV file with current season data.
    Assumes historical data (2005-06 to 2024-25) already exists from build_historical_stats.py.
    If CSV doesn't exist, it will attempt to fetch all seasons, but it's recommended
    to run build_historical_stats.py first for better performance.
    
    Args:
        csv_path: Path to the CSV file
    """
    # Create files directory if it doesn't exist
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    
    # Check if CSV exists
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found. Attempting to fetch all seasons...")
        print("For better performance, run build_historical_stats.py first to build the historical database.")
        # Fall back to fetching all seasons (slower)
        _build_all_seasons(csv_path)
        return
    
    # Read existing CSV
    existing_df = pd.read_csv(csv_path)
    existing_seasons = existing_df['SEASON'].unique().tolist() if 'SEASON' in existing_df.columns else []
    
    # Always update current season (remove old data and re-fetch)
    if current_season in existing_seasons:
        # Remove current season from existing data so we can update it
        existing_df = existing_df[existing_df['SEASON'] != current_season]
    
    # Fetch current season data
    try:
        print(f"Updating {current_season} season data...")
        player_stats = nba_api.stats.endpoints.LeagueDashPlayerStats(
            season=current_season,
            league_id_nullable=league_id,
            per_mode_detailed='PerGame',
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        
        # Add season column
        player_stats['SEASON'] = current_season
        
        # Combine with existing data
        combined_df = pd.concat([existing_df, player_stats], ignore_index=True)
        
        # Remove duplicates (same player, same season) - keep the most recent entry
        if 'PLAYER_ID' in combined_df.columns and 'SEASON' in combined_df.columns:
            combined_df = combined_df.drop_duplicates(subset=['PLAYER_ID', 'SEASON'], keep='last')
        
        # Save to CSV
        combined_df.to_csv(csv_path, index=False)
        print(f"Updated {csv_path} with {current_season} season data")
    except Exception as e:
        print(f"Error updating {current_season}: {e}")
        # If update fails, save the existing data back
        existing_df.to_csv(csv_path, index=False)


def _build_all_seasons(csv_path='new-streamlit-app/files/historical_player_season_stats.csv'):
    """
    Fallback function to build CSV with all seasons if it doesn't exist.
    This is slower and should only be used if build_historical_stats.py wasn't run.
    """
    # Generate list of seasons from 2005-06 to current season
    seasons = []
    start_year = 2005
    current_year = int(current_season.split('-')[0])
    
    for year in range(start_year, current_year + 1):
        next_year_short = str(year + 1)[2:4]
        seasons.append(f"{year}-{next_year_short}")
    
    # Fetch data for all seasons
    all_season_data = []
    
    for season in seasons:
        try:
            player_stats = nba_api.stats.endpoints.LeagueDashPlayerStats(
                season=season,
                league_id_nullable=league_id,
                per_mode_detailed='PerGame',
                season_type_all_star='Regular Season'
            ).get_data_frames()[0]
            
            player_stats['SEASON'] = season
            all_season_data.append(player_stats)
        except Exception as e:
            print(f"Error fetching data for season {season}: {e}")
            continue
    
    if all_season_data:
        combined_df = pd.concat(all_season_data, ignore_index=True)
        
        if 'PLAYER_ID' in combined_df.columns and 'SEASON' in combined_df.columns:
            combined_df = combined_df.drop_duplicates(subset=['PLAYER_ID', 'SEASON'], keep='last')
        
        combined_df.to_csv(csv_path, index=False)
        print(f"Created {csv_path} with {len(seasons)} season(s)")


def get_player_yoy_data(player_id, players_df=None):
    """
    Get year-over-year player data for a given player_id for all seasons.
    Uses LeagueDashPlayerStats and reads from CSV file for historical data.
    Returns a dictionary with season averages dataframe for all seasons the player has data.
    
    Args:
        player_id: Player ID as string
        players_df: Optional players dataframe from PlayerIndex (if None, will fetch it)
    """
    csv_path = 'new-streamlit-app/files/historical_player_season_stats.csv'
    
    # Build/update CSV if needed
    build_season_stats_csv(csv_path)
    
    # Read from CSV
    if not os.path.exists(csv_path):
        return {'averages_df': None}
    
    season_stats_df = pd.read_csv(csv_path)
    
    # Filter for this player (all seasons)
    player_season_stats = season_stats_df[
        season_stats_df['PLAYER_ID'] == int(player_id)
    ].copy()
    
    if len(player_season_stats) == 0:
        return {'averages_df': None}
    
    # Sort by season (oldest to newest)
    player_season_stats = player_season_stats.sort_values(by='SEASON', ascending=True)
    
    # Create rows for each season
    rows = []
    for _, row in player_season_stats.iterrows():
        # Calculate 2-point stats
        fgm = float(row.get('FGM', 0))
        fga = float(row.get('FGA', 0))
        fg3m = float(row.get('FG3M', 0))
        fg3a = float(row.get('FG3A', 0))
        ftm = float(row.get('FTM', 0))
        fta = float(row.get('FTA', 0))
        
        fg2m = fgm - fg3m
        fg2a = fga - fg3a
        fg2_pct = round((fg2m / fg2a * 100), 1) if fg2a > 0 else 0.0
        fg3_pct = round((fg3m / fg3a * 100), 1) if fg3a > 0 else 0.0
        ft_pct = round((ftm / fta * 100), 1) if fta > 0 else 0.0
        
        # Calculate PRA (Points + Rebounds + Assists)
        pts = round(float(row.get('PTS', 0)), 1)
        reb = round(float(row.get('REB', 0)), 1)
        ast = round(float(row.get('AST', 0)), 1)
        pra = round(pts + reb + ast, 1)
        
        # Create row for this season (REB before AST, PRA after AST)
        season_row = {
            'Period': row.get('SEASON', ''),
            'MIN': round(float(row.get('MIN', 0)), 1),
            'PTS': pts,
            'REB': reb,
            'AST': ast,
            'PRA': pra,
            'STL': round(float(row.get('STL', 0)), 1),
            'BLK': round(float(row.get('BLK', 0)), 1),
            'TOV': round(float(row.get('TOV', 0)), 1),
            '2PM': round(fg2m, 1),
            '2PA': round(fg2a, 1),
            '2P%': f"{fg2_pct:.1f}%",
            '3PM': round(fg3m, 1),
            '3PA': round(fg3a, 1),
            '3P%': f"{fg3_pct:.1f}%",
            'FTM': round(ftm, 1),
            'FTA': round(fta, 1),
            'FT%': f"{ft_pct:.1f}%",
        }
        rows.append(season_row)
    
    averages_df = pd.DataFrame(rows)
    
    return {
        'averages_df': averages_df
    }


# Note: Module-level variables for backward compatibility are no longer initialized
# at import time to avoid errors. The Streamlit app uses get_player_data() directly.
# If you need module-level variables, call get_player_data(default_player_id) when needed.

