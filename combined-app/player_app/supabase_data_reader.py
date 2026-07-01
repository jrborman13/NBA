"""
Supabase Data Reader Module
Reads NBA data from Supabase database tables (populated by scheduled Edge Functions).
Falls back to API calls if database is empty (safety net).
"""

import pandas as pd
from typing import Optional, Dict, Any, List
import logging

try:
    from supabase_config import get_supabase_client, is_supabase_configured
except ImportError:
    get_supabase_client = None
    is_supabase_configured = lambda: False

logger = logging.getLogger(__name__)

# Current season constant
CURRENT_SEASON = "2025-26"


def get_team_stats_from_db(
    season: str = CURRENT_SEASON,
    measure_type: str = 'Advanced',
    last_n_games: Optional[int] = None,
    group_quantity: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    Read team stats from database.
    
    Args:
        season: Season string (e.g., '2025-26')
        measure_type: 'Advanced', 'Misc', 'Traditional', 'Four Factors'
        last_n_games: Number of games (None for season totals)
        group_quantity: 'Starters', 'Bench', or None
    
    Returns:
        DataFrame with team stats, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        query = supabase.table('nba_team_stats').select('data').eq('season', season).eq('measure_type', measure_type)
        
        if last_n_games is not None:
            query = query.eq('last_n_games', last_n_games)
        else:
            query = query.is_('last_n_games', 'null')
        
        if group_quantity is not None:
            query = query.eq('group_quantity', group_quantity)
        else:
            query = query.is_('group_quantity', 'null')
        
        result = query.execute()
        
        if result.data and len(result.data) > 0:
            data = result.data[0]['data']
            if data:
                df = pd.DataFrame(data)
                print(f"[DB READ] Team stats ({measure_type}) from database: {len(df)} teams")
                return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading team stats from database: {e}")
        return None


def get_player_stats_from_db(season: str = CURRENT_SEASON) -> Optional[pd.DataFrame]:
    """
    Read player stats from database.
    
    Args:
        season: Season string (e.g., '2025-26')
    
    Returns:
        DataFrame with player stats, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        result = supabase.table('nba_player_stats').select('data').eq('season', season).execute()
        
        if result.data and len(result.data) > 0:
            data = result.data[0]['data']
            if data:
                df = pd.DataFrame(data)
                print(f"[DB READ] Player stats from database: {len(df)} players")
                return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading player stats from database: {e}")
        return None


def get_game_logs_from_db(season: str = CURRENT_SEASON, log_type: str = 'player') -> Optional[pd.DataFrame]:
    """
    Read game logs from database.
    
    Args:
        season: Season string (e.g., '2025-26')
        log_type: 'player' or 'team'
    
    Returns:
        DataFrame with game logs, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        result = supabase.table('nba_game_logs').select('data').eq('season', season).eq('log_type', log_type).execute()
        
        if result.data and len(result.data) > 0:
            data = result.data[0]['data']
            if data:
                df = pd.DataFrame(data)
                # Convert GAME_DATE to datetime if present
                if 'GAME_DATE' in df.columns:
                    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'], errors='coerce')
                print(f"[DB READ] {log_type.capitalize()} game logs from database: {len(df)} records")
                return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading game logs from database: {e}")
        return None


def get_synergy_data_from_db(
    season: str = CURRENT_SEASON,
    entity_type: str = 'team',
    playtype: Optional[str] = None,
    type_grouping: Optional[str] = None
) -> Optional[Dict[str, Dict[str, pd.DataFrame]]]:
    """
    Read synergy data from database.
    
    Args:
        season: Season string (e.g., '2025-26')
        entity_type: 'team' or 'player'
        playtype: Specific playtype to fetch (None for all)
        type_grouping: 'offensive' or 'defensive' (None for both)
    
    Returns:
        Dictionary: {playtype: {type_grouping: df}} or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        query = supabase.table('nba_synergy_data').select('*').eq('season', season).eq('entity_type', entity_type)
        
        if playtype:
            query = query.eq('playtype', playtype)
        if type_grouping:
            query = query.eq('type_grouping', type_grouping)
        
        result = query.execute()
        
        if not result.data or len(result.data) == 0:
            return None
        
        # Organize data into nested dictionary structure
        synergy_dict: Dict[str, Dict[str, pd.DataFrame]] = {}
        
        for row in result.data:
            pt = row['playtype']
            tg = row['type_grouping']
            data = row['data']
            
            if pt not in synergy_dict:
                synergy_dict[pt] = {}
            
            if data:
                synergy_dict[pt][tg] = pd.DataFrame(data)
            else:
                synergy_dict[pt][tg] = pd.DataFrame()
        
        print(f"[DB READ] Synergy data ({entity_type}) from database: {len(synergy_dict)} playtypes")
        return synergy_dict
    except Exception as e:
        logger.error(f"Error reading synergy data from database: {e}")
        return None


def get_schedule_from_db(season: str = CURRENT_SEASON) -> Optional[pd.DataFrame]:
    """
    Read schedule from database.
    
    Args:
        season: Season string (e.g., '2025-26')
    
    Returns:
        DataFrame with schedule, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        result = supabase.table('nba_schedule').select('data').eq('season', season).execute()
        
        if result.data and len(result.data) > 0:
            data = result.data[0]['data']
            if data:
                df = pd.DataFrame(data)
                # Convert date columns to datetime if present
                date_cols = [col for col in df.columns if 'DATE' in col.upper() or 'DATE' in col]
                for col in date_cols:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                print(f"[DB READ] Schedule from database: {len(df)} games")
                return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading schedule from database: {e}")
        return None


def get_standings_from_db(season: str = CURRENT_SEASON) -> Optional[pd.DataFrame]:
    """
    Read standings from database.
    
    Args:
        season: Season string (e.g., '2025-26')
    
    Returns:
        DataFrame with standings, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        result = supabase.table('nba_standings').select('data').eq('season', season).execute()
        
        if result.data and len(result.data) > 0:
            data = result.data[0]['data']
            if data:
                df = pd.DataFrame(data)
                print(f"[DB READ] Standings from database: {len(df)} teams")
                return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading standings from database: {e}")
        return None


def get_player_index_from_db(season: str = CURRENT_SEASON) -> Optional[pd.DataFrame]:
    """
    Read player index from database.
    
    Args:
        season: Season string (e.g., '2025-26')
    
    Returns:
        DataFrame with player index, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        result = supabase.table('nba_player_index').select('data').eq('season', season).execute()
        
        if result.data and len(result.data) > 0:
            data = result.data[0]['data']
            if data:
                df = pd.DataFrame(data)
                print(f"[DB READ] Player index from database: {len(df)} players")
                return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading player index from database: {e}")
        return None


def get_team_onoff_from_db(season: str = CURRENT_SEASON, team_id: Optional[int] = None) -> Optional[pd.DataFrame]:
    """
    Read team on/off data from database.
    
    Args:
        season: Season string (e.g., '2025-26')
        team_id: Team ID (None for all teams)
    
    Returns:
        DataFrame with team on/off data, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        query = supabase.table('nba_team_onoff').select('data').eq('season', season)
        
        if team_id is not None:
            query = query.eq('team_id', team_id)
        
        result = query.execute()
        
        if result.data and len(result.data) > 0:
            # If team_id specified, return single team's data
            if team_id is not None:
                data = result.data[0]['data']
                if data:
                    df = pd.DataFrame(data)
                    print(f"[DB READ] Team on/off data from database for team {team_id}: {len(df)} players")
                    return df
            else:
                # Return all teams' data combined
                all_data = []
                for row in result.data:
                    if row['data']:
                        all_data.extend(row['data'])
                if all_data:
                    df = pd.DataFrame(all_data)
                    print(f"[DB READ] Team on/off data from database: {len(df)} records")
                    return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading team on/off data from database: {e}")
        return None


def get_drives_stats_from_db(season: str = CURRENT_SEASON, entity_type: str = 'player') -> Optional[pd.DataFrame]:
    """
    Read drives stats from database.
    
    Args:
        season: Season string (e.g., '2025-26')
        entity_type: 'player' or 'team'
    
    Returns:
        DataFrame with drives stats, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        result = supabase.table('nba_drives_stats').select('data').eq('season', season).eq('entity_type', entity_type).execute()
        
        if result.data and len(result.data) > 0:
            data = result.data[0]['data']
            if data:
                df = pd.DataFrame(data)
                print(f"[DB READ] {entity_type.capitalize()} drives stats from database: {len(df)} records")
                return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading drives stats from database: {e}")
        return None


def get_pbpstats_from_db(season: str = CURRENT_SEASON, stat_type: str = 'team') -> Optional[pd.DataFrame]:
    """
    Read pbpstats data from database.
    
    Args:
        season: Season string (e.g., '2025-26')
        stat_type: 'team' or 'opponent'
    
    Returns:
        DataFrame with pbpstats, or None if not found
    """
    if not is_supabase_configured():
        return None
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        
        result = supabase.table('nba_pbpstats').select('data').eq('season', season).eq('stat_type', stat_type).execute()
        
        if result.data and len(result.data) > 0:
            data = result.data[0]['data']
            if data:
                df = pd.DataFrame(data)
                print(f"[DB READ] pbpstats ({stat_type}) from database: {len(df)} teams")
                return df
        
        return None
    except Exception as e:
        logger.error(f"Error reading pbpstats from database: {e}")
        return None

