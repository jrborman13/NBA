"""
Team Defensive Stats Module
Provides functions to fetch and display team defensive shooting metrics.
"""

import requests
import pandas as pd

# Current season configuration
current_season = "2025-26"
season_type = "Regular Season"

def load_shooting_data():
    """Load team shooting data from pbpstats API"""
    # Team offense shooting stats
    team_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season={current_season}&SeasonType={season_type.replace(' ', '+')}&Type=Team"
    team_offense_response = requests.get(team_offense_url)
    team_stats = pd.DataFrame(team_offense_response.json()['multi_row_table_data'])
    
    # Team defense (opponent) shooting stats - what teams ALLOW
    opp_offense_url = f"https://api.pbpstats.com/get-totals/nba?Season={current_season}&SeasonType={season_type.replace(' ', '+')}&Type=Opponent"
    opp_offense_response = requests.get(opp_offense_url)
    opp_team_stats = pd.DataFrame(opp_offense_response.json()['multi_row_table_data'])
    
    # Convert TeamId to int to match NBA API team IDs
    team_stats['TeamId'] = team_stats['TeamId'].astype(int)
    opp_team_stats['TeamId'] = opp_team_stats['TeamId'].astype(int)
    
    # Calculate per game values
    for df in [team_stats, opp_team_stats]:
        # Total FG (2PT + 3PT)
        df['FGM'] = df['FG2M'] + df['FG3M']
        df['FGA'] = df['FG2A'] + df['FG3A']
        df['FG%'] = df['FGM'] / df['FGA']
        
        # Per game values
        df['FGM_PG'] = round(df['FGM'] / df['GamesPlayed'], 1)
        df['FGA_PG'] = round(df['FGA'] / df['GamesPlayed'], 1)
        df['FG2M_PG'] = round(df['FG2M'] / df['GamesPlayed'], 1)
        df['FG2A_PG'] = round(df['FG2A'] / df['GamesPlayed'], 1)
        df['FG3M_PG'] = round(df['FG3M'] / df['GamesPlayed'], 1)
        df['FG3A_PG'] = round(df['FG3A'] / df['GamesPlayed'], 1)
        df['FTM'] = df['FtPoints']  # FtPoints = FTM since each FT is 1 point
        df['FTM_PG'] = round(df['FTM'] / df['GamesPlayed'], 1)
        df['FTA_PG'] = round(df['FTA'] / df['GamesPlayed'], 1)
        
        # Percentages
        df['2PT%'] = df['FG2M'] / df['FG2A']
        df['3PT%'] = df['FG3M'] / df['FG3A']
        df['FT%'] = df['FTM'] / df['FTA']
        
        # Free Throw Rate = FTA / FGA (how often they get to the line per field goal attempt)
        df['FT_RATE'] = df['FTA'] / df['FGA']
        
        # Add ranking columns (lower rank = better defense, meaning opponents score less)
        df['FGM_RANK'] = df['FGM_PG'].rank(ascending=True, method='first').astype(int)
        df['FGA_RANK'] = df['FGA_PG'].rank(ascending=True, method='first').astype(int)
        df['FG%_RANK'] = df['FG%'].rank(ascending=True, method='first').astype(int)
        df['FG2M_RANK'] = df['FG2M_PG'].rank(ascending=True, method='first').astype(int)
        df['FG2A_RANK'] = df['FG2A_PG'].rank(ascending=True, method='first').astype(int)
        df['2PT%_RANK'] = df['2PT%'].rank(ascending=True, method='first').astype(int)
        df['FG3M_RANK'] = df['FG3M_PG'].rank(ascending=True, method='first').astype(int)
        df['FG3A_RANK'] = df['FG3A_PG'].rank(ascending=True, method='first').astype(int)
        df['3PT%_RANK'] = df['3PT%'].rank(ascending=True, method='first').astype(int)
        df['FTM_RANK'] = df['FTM_PG'].rank(ascending=True, method='first').astype(int)
        df['FTA_RANK'] = df['FTA_PG'].rank(ascending=True, method='first').astype(int)
        df['FT%_RANK'] = df['FT%'].rank(ascending=True, method='first').astype(int)
        df['FT_RATE_RANK'] = df['FT_RATE'].rank(ascending=True, method='first').astype(int)  # Lower = better defense (less FT allowed)
        
        # Zone shooting rankings
        df['RIM_FREQ_RANK'] = df['AtRimFrequency'].rank(ascending=False, method='first').astype(int)
        df['RIM_FG%_RANK'] = df['AtRimAccuracy'].rank(ascending=True, method='first').astype(int)  # Lower allowed = better defense
        df['SMR_FREQ_RANK'] = df['ShortMidRangeFrequency'].rank(ascending=False, method='first').astype(int)
        df['SMR_FG%_RANK'] = df['ShortMidRangeAccuracy'].rank(ascending=True, method='first').astype(int)
        df['LMR_FREQ_RANK'] = df['LongMidRangeFrequency'].rank(ascending=False, method='first').astype(int)
        df['LMR_FG%_RANK'] = df['LongMidRangeAccuracy'].rank(ascending=True, method='first').astype(int)
        df['C3_FREQ_RANK'] = df['Corner3Frequency'].rank(ascending=False, method='first').astype(int)
        df['C3_FG%_RANK'] = df['Corner3Accuracy'].rank(ascending=True, method='first').astype(int)
        df['ATB3_FREQ_RANK'] = df['Arc3Frequency'].rank(ascending=False, method='first').astype(int)
        df['ATB3_FG%_RANK'] = df['Arc3Accuracy'].rank(ascending=True, method='first').astype(int)
    
    return team_stats, opp_team_stats


def get_team_defensive_stats(team_id, opp_team_stats):
    """
    Get defensive stats for a specific team (what they ALLOW opponents to shoot).
    
    Args:
        team_id: NBA API team ID
        opp_team_stats: DataFrame with opponent shooting stats
    
    Returns:
        Dictionary with defensive stats
    """
    stats = {}
    
    team_row = opp_team_stats[opp_team_stats['TeamId'] == team_id]
    if len(team_row) == 0:
        return None
    
    # Get team name/abbreviation
    stats['team_name'] = team_row['Name'].values[0]
    stats['team_abbr'] = team_row['TeamAbbreviation'].values[0]
    
    # Overall FG Defense
    stats['opp_fg_pct'] = round(team_row['FG%'].values[0] * 100, 1)
    stats['opp_fg_pct_rank'] = int(team_row['FG%_RANK'].values[0])
    
    # 2PT Defense
    stats['opp_2pt_pct'] = round(team_row['2PT%'].values[0] * 100, 1)
    stats['opp_2pt_pct_rank'] = int(team_row['2PT%_RANK'].values[0])
    
    # 3PT Defense
    stats['opp_3pt_pct'] = round(team_row['3PT%'].values[0] * 100, 1)
    stats['opp_3pt_pct_rank'] = int(team_row['3PT%_RANK'].values[0])
    
    # FT Defense (fouling)
    stats['opp_ft_pct'] = round(team_row['FT%'].values[0] * 100, 1)
    stats['opp_fta_pg'] = team_row['FTA_PG'].values[0]
    stats['opp_fta_rank'] = int(team_row['FTA_RANK'].values[0])
    stats['opp_ftm_pg'] = team_row['FTM_PG'].values[0]
    
    # Free Throw Rate (FTA/FGA) - how often opponents get to the line
    stats['opp_ft_rate'] = round(team_row['FT_RATE'].values[0] * 100, 1)  # As percentage
    stats['opp_ft_rate_rank'] = int(team_row['FT_RATE_RANK'].values[0])
    
    # Rim Defense
    stats['opp_rim_freq'] = round(team_row['AtRimFrequency'].values[0] * 100, 1)
    stats['opp_rim_freq_rank'] = int(team_row['RIM_FREQ_RANK'].values[0])
    stats['opp_rim_acc'] = round(team_row['AtRimAccuracy'].values[0] * 100, 1)
    stats['opp_rim_acc_rank'] = int(team_row['RIM_FG%_RANK'].values[0])
    
    # Short Mid-Range Defense
    stats['opp_smr_freq'] = round(team_row['ShortMidRangeFrequency'].values[0] * 100, 1)
    stats['opp_smr_freq_rank'] = int(team_row['SMR_FREQ_RANK'].values[0])
    stats['opp_smr_acc'] = round(team_row['ShortMidRangeAccuracy'].values[0] * 100, 1)
    stats['opp_smr_acc_rank'] = int(team_row['SMR_FG%_RANK'].values[0])
    
    # Long Mid-Range Defense
    stats['opp_lmr_freq'] = round(team_row['LongMidRangeFrequency'].values[0] * 100, 1)
    stats['opp_lmr_freq_rank'] = int(team_row['LMR_FREQ_RANK'].values[0])
    stats['opp_lmr_acc'] = round(team_row['LongMidRangeAccuracy'].values[0] * 100, 1)
    stats['opp_lmr_acc_rank'] = int(team_row['LMR_FG%_RANK'].values[0])
    
    # Corner 3 Defense
    stats['opp_c3_freq'] = round(team_row['Corner3Frequency'].values[0] * 100, 1)
    stats['opp_c3_freq_rank'] = int(team_row['C3_FREQ_RANK'].values[0])
    stats['opp_c3_acc'] = round(team_row['Corner3Accuracy'].values[0] * 100, 1)
    stats['opp_c3_acc_rank'] = int(team_row['C3_FG%_RANK'].values[0])
    
    # Above the Break 3 Defense
    stats['opp_atb3_freq'] = round(team_row['Arc3Frequency'].values[0] * 100, 1)
    stats['opp_atb3_freq_rank'] = int(team_row['ATB3_FREQ_RANK'].values[0])
    stats['opp_atb3_acc'] = round(team_row['Arc3Accuracy'].values[0] * 100, 1)
    stats['opp_atb3_acc_rank'] = int(team_row['ATB3_FG%_RANK'].values[0])
    
    return stats


def format_rank(rank, total=30):
    """Format rank with color coding based on how good/bad it is"""
    if rank <= 5:
        return f"🟢 {rank}"  # Top 5 - green (good matchup for offense)
    elif rank <= 10:
        return f"🟡 {rank}"  # 6-10 - yellow
    elif rank >= 26:
        return f"🔴 {rank}"  # Bottom 5 - red (bad matchup for offense)
    elif rank >= 21:
        return f"🟠 {rank}"  # 21-25 - orange
    else:
        return f"⚪ {rank}"  # Middle - neutral


def get_rank_color(rank):
    """Get color for rank display"""
    if rank <= 5:
        return "#4CAF50"  # Green - opponents shoot well (bad defense)
    elif rank <= 10:
        return "#8BC34A"  # Light green
    elif rank >= 26:
        return "#F44336"  # Red - opponents shoot poorly (good defense)
    elif rank >= 21:
        return "#FF9800"  # Orange
    else:
        return "#9E9E9E"  # Gray - neutral


def load_player_shooting_data():
    """Load player shooting data from pbpstats API"""
    player_url = f"https://api.pbpstats.com/get-totals/nba?Season={current_season}&SeasonType={season_type.replace(' ', '+')}&Type=Player"
    player_response = requests.get(player_url)
    player_stats = pd.DataFrame(player_response.json()['multi_row_table_data'])
    
    # Convert EntityId to string for matching with NBA API player IDs
    # pbpstats uses EntityId for player IDs
    player_stats['PlayerId'] = player_stats['EntityId'].astype(str)
    
    return player_stats


def get_player_zone_shooting(player_id, player_stats_df):
    """
    Get zone shooting stats for a specific player.
    
    Args:
        player_id: NBA API player ID (string)
        player_stats_df: DataFrame with player shooting stats from pbpstats
    
    Returns:
        Dictionary with player zone shooting stats, or None if player not found
    """
    # Convert player_id to string for matching
    player_id_str = str(player_id)
    
    player_row = player_stats_df[player_stats_df['PlayerId'] == player_id_str]
    if len(player_row) == 0:
        return None
    
    stats = {}
    
    # Player name
    stats['player_name'] = player_row['Name'].values[0]
    
    # Rim shooting
    stats['rim_acc'] = round(player_row['AtRimAccuracy'].values[0] * 100, 1) if player_row['AtRimAccuracy'].values[0] else 0.0
    stats['rim_freq'] = round(player_row['AtRimFrequency'].values[0] * 100, 1) if player_row['AtRimFrequency'].values[0] else 0.0
    stats['rim_fga'] = int(player_row['AtRimFGA'].values[0]) if player_row['AtRimFGA'].values[0] else 0
    
    # Short Mid-Range shooting
    stats['smr_acc'] = round(player_row['ShortMidRangeAccuracy'].values[0] * 100, 1) if player_row['ShortMidRangeAccuracy'].values[0] else 0.0
    stats['smr_freq'] = round(player_row['ShortMidRangeFrequency'].values[0] * 100, 1) if player_row['ShortMidRangeFrequency'].values[0] else 0.0
    stats['smr_fga'] = int(player_row['ShortMidRangeFGA'].values[0]) if player_row['ShortMidRangeFGA'].values[0] else 0
    
    # Long Mid-Range shooting
    stats['lmr_acc'] = round(player_row['LongMidRangeAccuracy'].values[0] * 100, 1) if player_row['LongMidRangeAccuracy'].values[0] else 0.0
    stats['lmr_freq'] = round(player_row['LongMidRangeFrequency'].values[0] * 100, 1) if player_row['LongMidRangeFrequency'].values[0] else 0.0
    stats['lmr_fga'] = int(player_row['LongMidRangeFGA'].values[0]) if player_row['LongMidRangeFGA'].values[0] else 0
    
    # Corner 3 shooting
    stats['c3_acc'] = round(player_row['Corner3Accuracy'].values[0] * 100, 1) if player_row['Corner3Accuracy'].values[0] else 0.0
    stats['c3_freq'] = round(player_row['Corner3Frequency'].values[0] * 100, 1) if player_row['Corner3Frequency'].values[0] else 0.0
    stats['c3_fga'] = int(player_row['Corner3FGA'].values[0]) if player_row['Corner3FGA'].values[0] else 0
    
    # Above the Break 3 shooting
    stats['atb3_acc'] = round(player_row['Arc3Accuracy'].values[0] * 100, 1) if player_row['Arc3Accuracy'].values[0] else 0.0
    stats['atb3_freq'] = round(player_row['Arc3Frequency'].values[0] * 100, 1) if player_row['Arc3Frequency'].values[0] else 0.0
    stats['atb3_fga'] = int(player_row['Arc3FGA'].values[0]) if player_row['Arc3FGA'].values[0] else 0
    
    return stats


def compare_player_vs_opponent_zones(player_zones, opponent_def_stats):
    """
    Compare player zone shooting to opponent zone defense.
    
    Args:
        player_zones: Dictionary from get_player_zone_shooting()
        opponent_def_stats: Dictionary from get_team_defensive_stats()
    
    Returns:
        Dictionary with comparison data for each zone
    """
    if player_zones is None or opponent_def_stats is None:
        return None
    
    comparisons = {}
    
    # Zone definitions: (zone_key, player_stat_key, opp_stat_key, zone_display_name)
    zones = [
        ('rim', 'rim_acc', 'opp_rim_acc', 'At Rim'),
        ('smr', 'smr_acc', 'opp_smr_acc', 'Short Mid-Range'),
        ('lmr', 'lmr_acc', 'opp_lmr_acc', 'Long Mid-Range'),
        ('c3', 'c3_acc', 'opp_c3_acc', 'Corner 3'),
        ('atb3', 'atb3_acc', 'opp_atb3_acc', 'Above Break 3'),
    ]
    
    for zone_key, player_key, opp_key, zone_name in zones:
        player_pct = player_zones.get(player_key, 0.0)
        opp_allowed_pct = opponent_def_stats.get(opp_key, 0.0)
        
        # Calculate difference: positive = opponent allows MORE than player typically shoots (favorable)
        # If opponent allows 65% and player shoots 60%, difference is +5% (good matchup - weak defense)
        # If opponent allows 55% and player shoots 60%, difference is -5% (bad matchup - strong defense)
        difference = round(opp_allowed_pct - player_pct, 1)
        
        # Determine matchup rating
        if difference >= 5:
            rating = "very_favorable"
            color = "#2E7D32"  # Dark green - opponent defense is much weaker than player's usual
        elif difference >= 2:
            rating = "favorable"
            color = "#4CAF50"  # Green
        elif difference >= -2:
            rating = "neutral"
            color = "#9E9E9E"  # Gray
        elif difference >= -5:
            rating = "unfavorable"
            color = "#F44336"  # Red
        else:
            rating = "very_unfavorable"
            color = "#B71C1C"  # Dark red - opponent defense is much stronger than player's usual
        
        comparisons[zone_key] = {
            'zone_name': zone_name,
            'player_pct': player_pct,
            'opp_allowed_pct': opp_allowed_pct,
            'difference': difference,
            'rating': rating,
            'color': color,
            'player_freq': player_zones.get(f'{zone_key}_freq', 0.0),
            'player_fga': player_zones.get(f'{zone_key}_fga', 0),
        }
    
    return comparisons


def get_matchup_color(difference):
    """
    Get background color based on matchup difference.
    Positive difference = opponent allows more than player shoots = favorable (green)
    Negative difference = opponent allows less than player shoots = unfavorable (red)
    """
    if difference >= 5:
        return "rgba(46, 125, 50, 0.3)"  # Dark green - very favorable matchup
    elif difference >= 2:
        return "rgba(76, 175, 80, 0.3)"  # Green - favorable
    elif difference >= -2:
        return "rgba(158, 158, 158, 0.2)"  # Gray - neutral
    elif difference >= -5:
        return "rgba(244, 67, 54, 0.3)"  # Red - unfavorable
    else:
        return "rgba(183, 28, 28, 0.3)"  # Dark red - very unfavorable
