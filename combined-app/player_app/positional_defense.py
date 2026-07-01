"""
Positional Defense Module
Calculate and cache team defensive performance by position.
This helps adjust predictions based on how teams defend different positions.
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Dict, Optional, Tuple
import nba_api.stats.endpoints as endpoints

# Current season
CURRENT_SEASON = "2025-26"

# Position mappings
POSITION_GROUPS = {
    'G': ['PG', 'SG', 'G', 'G-F'],
    'F': ['SF', 'PF', 'F', 'F-G', 'F-C'],
    'C': ['C', 'C-F']
}

# League average PPG by position (will be calculated dynamically)
LEAGUE_AVG_BY_POSITION = {
    'G': 15.0,  # Guards
    'F': 14.0,  # Forwards
    'C': 12.0   # Centers (fewer, but higher usage ones score more)
}

# Team ID to abbreviation mapping
TEAM_ID_TO_ABBR = {
    1610612737: 'ATL', 1610612738: 'BOS', 1610612751: 'BKN', 1610612766: 'CHA',
    1610612741: 'CHI', 1610612739: 'CLE', 1610612742: 'DAL', 1610612743: 'DEN',
    1610612765: 'DET', 1610612744: 'GSW', 1610612745: 'HOU', 1610612754: 'IND',
    1610612746: 'LAC', 1610612747: 'LAL', 1610612763: 'MEM', 1610612748: 'MIA',
    1610612749: 'MIL', 1610612750: 'MIN', 1610612740: 'NOP', 1610612752: 'NYK',
    1610612760: 'OKC', 1610612753: 'ORL', 1610612755: 'PHI', 1610612756: 'PHX',
    1610612757: 'POR', 1610612758: 'SAC', 1610612759: 'SAS', 1610612761: 'TOR',
    1610612762: 'UTA', 1610612764: 'WAS'
}

ABBR_TO_TEAM_ID = {v: k for k, v in TEAM_ID_TO_ABBR.items()}


def get_position_group(position: str) -> str:
    """
    Map detailed position to position group (G, F, C).
    """
    if not position:
        return 'F'  # Default to Forward if unknown
    
    position = position.upper().strip()
    
    for group, positions in POSITION_GROUPS.items():
        if position in positions:
            return group
    
    # Try partial matching
    if 'G' in position:
        return 'G'
    elif 'C' in position:
        return 'C'
    else:
        return 'F'


@st.cache_data(ttl=3600, show_spinner=False)  # Cache for 1 hour
def get_league_players_with_positions() -> pd.DataFrame:
    """
    Get all players with their positions and team IDs.
    """
    try:
        players = endpoints.LeagueDashPlayerStats(
            season=CURRENT_SEASON,
            season_type_all_star='Regular Season',
            per_mode_detailed='PerGame'
        ).get_data_frames()[0]
        
        return players[['PLAYER_ID', 'PLAYER_NAME', 'TEAM_ID', 'TEAM_ABBREVIATION', 'GP', 'MIN', 'PTS', 'REB', 'AST']]
    except Exception as e:
        print(f"Error fetching league players: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_position(player_id: int) -> str:
    """
    Get a player's position from PlayerIndex.
    """
    try:
        from nba_api.stats.endpoints import CommonPlayerInfo
        info = CommonPlayerInfo(player_id=player_id).get_data_frames()[0]
        if len(info) > 0:
            return info['POSITION'].iloc[0]
        return 'F'
    except:
        return 'F'


@st.cache_data(ttl=7200, show_spinner=False)  # Cache for 2 hours
def calculate_team_defense_by_position() -> Dict[str, Dict[str, Dict]]:
    """
    Calculate how each team defends each position.
    
    Returns:
        Dict[team_abbr][position_group] = {
            'pts_allowed': float,
            'reb_allowed': float,
            'ast_allowed': float,
            'rank': int,
            'vs_league_avg': float  # % above/below league avg
        }
    """
    try:
        # Get player stats by opponent
        # Using opponent splits to see how players perform against each team
        all_team_defense = {}
        
        # For each position group, get top players and their game logs
        position_players = {
            'G': [],  # Guards
            'F': [],  # Forwards  
            'C': []   # Centers
        }
        
        # Get all player stats to categorize by position
        player_stats = endpoints.LeagueDashPlayerStats(
            season=CURRENT_SEASON,
            season_type_all_star='Regular Season',
            per_mode_detailed='PerGame'
        ).get_data_frames()[0]
        
        # Get player positions from PlayerIndex
        player_index = endpoints.PlayerIndex(
            season=CURRENT_SEASON,
            league_id='00'
        ).get_data_frames()[0]
        
        # Merge position info
        player_stats = player_stats.merge(
            player_index[['PERSON_ID', 'POSITION']],
            left_on='PLAYER_ID',
            right_on='PERSON_ID',
            how='left'
        )
        
        # Assign position groups
        player_stats['POS_GROUP'] = player_stats['POSITION'].apply(get_position_group)
        
        # Calculate league averages by position
        league_avgs = {}
        for pos in ['G', 'F', 'C']:
            pos_players = player_stats[player_stats['POS_GROUP'] == pos]
            # Weight by minutes to get meaningful averages
            if len(pos_players) > 0:
                weighted_pts = (pos_players['PTS'] * pos_players['MIN']).sum() / pos_players['MIN'].sum()
                weighted_reb = (pos_players['REB'] * pos_players['MIN']).sum() / pos_players['MIN'].sum()
                weighted_ast = (pos_players['AST'] * pos_players['MIN']).sum() / pos_players['MIN'].sum()
                league_avgs[pos] = {
                    'PTS': round(weighted_pts, 1),
                    'REB': round(weighted_reb, 1),
                    'AST': round(weighted_ast, 1)
                }
            else:
                league_avgs[pos] = {'PTS': 12.0, 'REB': 4.0, 'AST': 3.0}
        
        # Now calculate team defense vs each position
        # Using player tracking defend endpoint for this
        team_pos_defense = {}
        
        for team_id, team_abbr in TEAM_ID_TO_ABBR.items():
            team_pos_defense[team_abbr] = {}
            
            for pos in ['G', 'F', 'C']:
                # Get players of this position
                pos_players = player_stats[player_stats['POS_GROUP'] == pos].copy()
                
                # Calculate what this team allows to this position
                # For now, use overall defensive rating as baseline
                # and adjust based on position matchup data if available
                
                team_pos_defense[team_abbr][pos] = {
                    'pts_allowed': league_avgs[pos]['PTS'],
                    'reb_allowed': league_avgs[pos]['REB'],
                    'ast_allowed': league_avgs[pos]['AST'],
                    'rank': 15,  # Default to middle
                    'vs_league_avg': 0.0
                }
        
        # Get team defensive stats for ranking
        team_def = endpoints.LeagueDashTeamStats(
            season=CURRENT_SEASON,
            season_type_all_star='Regular Season',
            per_mode_detailed='PerGame',
            measure_type_detailed_defense='Opponent',
            league_id_nullable='00'
        ).get_data_frames()[0]
        
        # Rank teams by defensive rating
        team_def['DEF_RANK'] = team_def['OPP_PTS'].rank(ascending=True, method='first').astype(int)
        
        # Update team positional defense based on overall defense
        # Better overall defense = better at all positions (with slight variance)
        for _, row in team_def.iterrows():
            team_id = row['TEAM_ID']
            if team_id not in TEAM_ID_TO_ABBR:
                continue
            team_abbr = TEAM_ID_TO_ABBR[team_id]
            def_rank = row['DEF_RANK']
            opp_pts = row['OPP_PTS']
            
            # Calculate defensive factor (1.0 = league average)
            league_avg_pts = team_def['OPP_PTS'].mean()
            def_factor = opp_pts / league_avg_pts
            
            for pos in ['G', 'F', 'C']:
                base_pts = league_avgs[pos]['PTS']
                adjusted_pts = round(base_pts * def_factor, 1)
                
                team_pos_defense[team_abbr][pos] = {
                    'pts_allowed': adjusted_pts,
                    'reb_allowed': league_avgs[pos]['REB'],
                    'ast_allowed': league_avgs[pos]['AST'],
                    'rank': def_rank,
                    'vs_league_avg': round((def_factor - 1.0) * 100, 1),
                    'def_factor': round(def_factor, 3)
                }
        
        # Re-rank by position
        for pos in ['G', 'F', 'C']:
            # Sort teams by pts_allowed for this position
            sorted_teams = sorted(
                team_pos_defense.items(),
                key=lambda x: x[1][pos]['pts_allowed']
            )
            for rank, (team_abbr, _) in enumerate(sorted_teams, 1):
                team_pos_defense[team_abbr][pos]['rank'] = rank
        
        return {
            'team_defense': team_pos_defense,
            'league_avgs': league_avgs
        }
        
    except Exception as e:
        print(f"Error calculating positional defense: {e}")
        return {'team_defense': {}, 'league_avgs': {}}


def get_positional_defense_adjustment(
    opponent_abbr: str,
    player_position: str
) -> Dict:
    """
    Get defensive adjustment factor for a player based on their position
    and the opponent's defense against that position.
    
    Args:
        opponent_abbr: Opponent team abbreviation (e.g., 'NYK')
        player_position: Player's position (e.g., 'C', 'PG', 'SF')
    
    Returns:
        Dict with adjustment factor and context
    """
    pos_group = get_position_group(player_position)
    
    # Get cached positional defense data
    defense_data = calculate_team_defense_by_position()
    
    if not defense_data or 'team_defense' not in defense_data:
        return {
            'factor': 1.0,
            'rank': 15,
            'vs_league_avg': 0.0,
            'position_group': pos_group,
            'opponent': opponent_abbr,
            'description': 'No positional defense data available'
        }
    
    team_defense = defense_data['team_defense']
    league_avgs = defense_data.get('league_avgs', {})
    
    if opponent_abbr not in team_defense:
        return {
            'factor': 1.0,
            'rank': 15,
            'vs_league_avg': 0.0,
            'position_group': pos_group,
            'opponent': opponent_abbr,
            'description': f'No data for {opponent_abbr}'
        }
    
    pos_defense = team_defense[opponent_abbr].get(pos_group, {})
    
    factor = pos_defense.get('def_factor', 1.0)
    rank = pos_defense.get('rank', 15)
    vs_avg = pos_defense.get('vs_league_avg', 0.0)
    pts_allowed = pos_defense.get('pts_allowed', 0.0)
    
    # Generate description
    if rank <= 5:
        desc = f"Elite {pos_group} defense (Rank {rank})"
    elif rank <= 10:
        desc = f"Good {pos_group} defense (Rank {rank})"
    elif rank <= 20:
        desc = f"Average {pos_group} defense (Rank {rank})"
    elif rank <= 25:
        desc = f"Below average {pos_group} defense (Rank {rank})"
    else:
        desc = f"Weak {pos_group} defense (Rank {rank})"
    
    return {
        'factor': factor,
        'rank': rank,
        'vs_league_avg': vs_avg,
        'pts_allowed': pts_allowed,
        'position_group': pos_group,
        'opponent': opponent_abbr,
        'description': desc,
        'league_avg': league_avgs.get(pos_group, {}).get('PTS', 12.0)
    }


def get_all_positional_defense_rankings() -> pd.DataFrame:
    """
    Get a DataFrame of all teams' positional defense rankings.
    Useful for display/debugging.
    """
    defense_data = calculate_team_defense_by_position()
    
    if not defense_data or 'team_defense' not in defense_data:
        return pd.DataFrame()
    
    rows = []
    for team_abbr, positions in defense_data['team_defense'].items():
        row = {'Team': team_abbr}
        for pos in ['G', 'F', 'C']:
            if pos in positions:
                row[f'{pos}_Rank'] = positions[pos].get('rank', '-')
                row[f'{pos}_Factor'] = positions[pos].get('def_factor', 1.0)
        rows.append(row)
    
    df = pd.DataFrame(rows)
    return df.sort_values('Team')

