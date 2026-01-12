"""
Vegas Lines Module
Functions to handle player prop lines for comparison with predictions.
Integrates with The Odds API for live odds from Underdog Fantasy.
"""

import pandas as pd
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import os
import requests
import pytz
import logging

from supabase_config import get_supabase_client, is_supabase_configured

logger = logging.getLogger(__name__)

# File to store manually entered lines (for backward compatibility)
LINES_FILE = "player_lines.json"

# ============================================================
# THE ODDS API CONFIGURATION
# ============================================================
ODDS_API_KEY = "b1e07a3930c492ee79199a526b2d1c2b"  # Move to env later
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
SPORT = "basketball_nba"
REGION = "us_dfs"
BOOKMAKER = "underdog"

# Map our stat codes to The Odds API market names
STAT_TO_MARKET = {
    'PTS': 'player_points',
    'REB': 'player_rebounds',
    'AST': 'player_assists',
    'PRA': 'player_points_rebounds_assists',
    'RA': 'player_rebounds_assists',  # Rebounds + Assists combo
    'STL': 'player_steals',
    'BLK': 'player_blocks',
    'FG3M': 'player_threes',
    'FTM': 'player_frees_made',  # Made free throws
    'FPTS': 'player_fantasy_points',  # Fantasy points
}

# Reverse mapping: API market name -> our stat code
MARKET_TO_STAT = {v: k for k, v in STAT_TO_MARKET.items()}

# NBA team name mappings (tricode -> full name for matching)
TEAM_TRICODE_TO_NAME = {
    'ATL': 'Atlanta Hawks', 'BOS': 'Boston Celtics', 'BKN': 'Brooklyn Nets',
    'CHA': 'Charlotte Hornets', 'CHI': 'Chicago Bulls', 'CLE': 'Cleveland Cavaliers',
    'DAL': 'Dallas Mavericks', 'DEN': 'Denver Nuggets', 'DET': 'Detroit Pistons',
    'GSW': 'Golden State Warriors', 'HOU': 'Houston Rockets', 'IND': 'Indiana Pacers',
    'LAC': 'Los Angeles Clippers', 'LAL': 'Los Angeles Lakers', 'MEM': 'Memphis Grizzlies',
    'MIA': 'Miami Heat', 'MIL': 'Milwaukee Bucks', 'MIN': 'Minnesota Timberwolves',
    'NOP': 'New Orleans Pelicans', 'NYK': 'New York Knicks', 'OKC': 'Oklahoma City Thunder',
    'ORL': 'Orlando Magic', 'PHI': 'Philadelphia 76ers', 'PHX': 'Phoenix Suns',
    'POR': 'Portland Trail Blazers', 'SAC': 'Sacramento Kings', 'SAS': 'San Antonio Spurs',
    'TOR': 'Toronto Raptors', 'UTA': 'Utah Jazz', 'WAS': 'Washington Wizards'
}


@dataclass
class PropLine:
    """Container for a player prop line"""
    stat: str
    line: float
    over_odds: int  # American odds (e.g., -110)
    under_odds: int
    source: str  # 'manual', 'underdog', etc.


@dataclass
class OddsAPIResponse:
    """Container for API response with credit tracking"""
    success: bool
    data: Optional[Dict]
    error: Optional[str]
    credits_used: int
    credits_remaining: int


# ============================================================
# CORE MANUAL LINE FUNCTIONS (existing)
# ============================================================

def load_saved_lines() -> Dict:
    """Load previously saved lines from Supabase (or JSON file as fallback)"""
    # Try Supabase first
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            if supabase:
                result = supabase.table('vegas_lines').select('*').execute()
                
                if result.data:
                    # Convert to the old format: {player_id_game_date: {stat: {...}}}
                    lines_dict = {}
                    for row in result.data:
                        key = f"{row['player_id']}_{row['game_date']}"
                        if key not in lines_dict:
                            lines_dict[key] = {}
                        lines_dict[key][row['stat']] = {
                            'line': float(row['line']),
                            'over_odds': int(row['over_odds']),
                            'under_odds': int(row['under_odds']),
                            'source': str(row['source'])
                        }
                    logger.debug(f"Loaded {len(lines_dict)} player-date combinations from Supabase")
                    return lines_dict
        except Exception as e:
            logger.warning(f"Failed to load lines from Supabase: {e}. Falling back to JSON.")
    
    # Fallback to JSON
    if os.path.exists(LINES_FILE):
        try:
            with open(LINES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_lines(lines: Dict):
    """Save lines to Supabase (or JSON file as fallback)"""
    # Try Supabase first
    if is_supabase_configured():
        try:
            supabase = get_supabase_client()
            if supabase:
                records = []
                for key, player_lines in lines.items():
                    # Key format: "player_id_game_date"
                    parts = key.split('_')
                    if len(parts) < 2:
                        continue
                    
                    player_id = parts[0]
                    game_date = '_'.join(parts[1:])
                    
                    if not isinstance(player_lines, dict):
                        continue
                    
                    for stat, line_data in player_lines.items():
                        if not isinstance(line_data, dict):
                            continue
                        
                        record = {
                            'player_id': str(player_id),
                            'game_date': str(game_date),
                            'stat': str(stat),
                            'line': float(line_data.get('line', 0)),
                            'over_odds': int(line_data.get('over_odds', -110)),
                            'under_odds': int(line_data.get('under_odds', -110)),
                            'source': str(line_data.get('source', 'manual')),
                        }
                        records.append(record)
                
                if records:
                    # Upsert in batches
                    batch_size = 100
                    for i in range(0, len(records), batch_size):
                        batch = records[i:i + batch_size]
                        supabase.table('vegas_lines').upsert(
                            batch,
                            on_conflict='player_id,game_date,stat'
                        ).execute()
                    logger.debug(f"Saved {len(records)} lines to Supabase")
                    return
        except Exception as e:
            logger.warning(f"Failed to save lines to Supabase: {e}. Falling back to JSON.")
    
    # Fallback to JSON
    with open(LINES_FILE, 'w') as f:
        json.dump(lines, f, indent=2)


def get_player_lines(
    player_id: str,
    game_date: str,
    source: str = 'manual'
) -> Dict[str, PropLine]:
    """
    Get prop lines for a player.
    
    Args:
        player_id: NBA API player ID
        game_date: Date of the game (YYYY-MM-DD)
        source: Source of lines ('manual', 'api', etc.)
    
    Returns:
        Dict of stat -> PropLine
    """
    saved = load_saved_lines()
    key = f"{player_id}_{game_date}"
    
    if key in saved:
        lines = {}
        for stat, data in saved[key].items():
            lines[stat] = PropLine(
                stat=stat,
                line=data['line'],
                over_odds=data.get('over_odds', -110),
                under_odds=data.get('under_odds', -110),
                source=data.get('source', 'manual')
            )
        return lines
    
    return {}


def set_player_line(
    player_id: str,
    game_date: str,
    stat: str,
    line: float,
    over_odds: int = -110,
    under_odds: int = -110,
    source: str = 'manual'
):
    """
    Set a prop line for a player.
    
    Args:
        player_id: NBA API player ID
        game_date: Date of the game (YYYY-MM-DD)
        stat: Stat type ('PTS', 'REB', 'AST', 'PRA', etc.)
        line: The line value
        over_odds: American odds for over
        under_odds: American odds for under
        source: Source of the line
    """
    saved = load_saved_lines()
    key = f"{player_id}_{game_date}"
    
    if key not in saved:
        saved[key] = {}
    
    saved[key][stat] = {
        'line': line,
        'over_odds': over_odds,
        'under_odds': under_odds,
        'source': source
    }
    
    save_lines(saved)


def compare_prediction_to_line(
    prediction: float,
    line: float
) -> Dict:
    """
    Compare prediction to Vegas line.
    
    Returns:
        Dict with comparison details
    """
    diff = round(prediction - line, 1)
    diff_pct = round((diff / line) * 100, 1) if line > 0 else 0
    
    # Determine lean
    if diff >= 1.5:
        lean = "Strong Over"
        lean_color = "#2E7D32"  # Dark green
    elif diff >= 0.5:
        lean = "Lean Over"
        lean_color = "#4CAF50"  # Green
    elif diff <= -1.5:
        lean = "Strong Under"
        lean_color = "#B71C1C"  # Dark red
    elif diff <= -0.5:
        lean = "Lean Under"
        lean_color = "#F44336"  # Red
    else:
        lean = "Push/Avoid"
        lean_color = "#9E9E9E"  # Gray
    
    return {
        'prediction': prediction,
        'line': line,
        'diff': diff,
        'diff_pct': diff_pct,
        'lean': lean,
        'lean_color': lean_color
    }


def calculate_implied_probability(american_odds: int) -> float:
    """
    Convert American odds to implied probability.
    
    Args:
        american_odds: American odds (e.g., -110, +150)
    
    Returns:
        Implied probability as percentage
    """
    if american_odds < 0:
        return round(abs(american_odds) / (abs(american_odds) + 100) * 100, 1)
    else:
        return round(100 / (american_odds + 100) * 100, 1)


def calculate_ev(
    prediction_prob: float,
    line_odds: int,
    stake: float = 100
) -> float:
    """
    Calculate expected value of a bet.
    
    Args:
        prediction_prob: Our estimated probability of winning (0-1)
        line_odds: American odds
        stake: Bet amount
    
    Returns:
        Expected value (positive = profitable)
    """
    if line_odds < 0:
        profit = stake * (100 / abs(line_odds))
    else:
        profit = stake * (line_odds / 100)
    
    ev = (prediction_prob * profit) - ((1 - prediction_prob) * stake)
    return round(ev, 2)


def get_default_lines() -> Dict[str, float]:
    """
    Get typical line values for common stats.
    Used as placeholders when no lines are available.
    """
    return {
        'PTS': 20.5,
        'REB': 5.5,
        'AST': 4.5,
        'PRA': 30.5,
        'STL': 1.5,
        'BLK': 0.5,
        'FG3M': 2.5,
    }


# ============================================================
# THE ODDS API FUNCTIONS
# ============================================================

def get_nba_events(date_str: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
    """
    Fetch NBA events/games from The Odds API.
    This endpoint is FREE and does not cost credits.
    
    Args:
        date_str: Optional date filter (YYYY-MM-DD). If None, gets all upcoming events.
    
    Returns:
        Tuple of (list of events, error message if any)
    """
    url = f"{ODDS_API_BASE}/sports/{SPORT}/events"
    params = {
        'apiKey': ODDS_API_KEY,
        'dateFormat': 'iso'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            events = response.json()
            
            # Filter by date if provided
            if date_str:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                filtered_events = []
                
                # Get local timezone (default to US/Eastern for NBA games)
                try:
                    local_tz = pytz.timezone('US/Eastern')
                except:
                    local_tz = pytz.UTC
                
                for event in events:
                    # Parse the UTC time from API
                    event_time_utc = datetime.fromisoformat(event['commence_time'].replace('Z', '+00:00'))
                    
                    # Convert to local timezone
                    event_time_local = event_time_utc.astimezone(local_tz)
                    event_date_local = event_time_local.date()
                    
                    if event_date_local == target_date:
                        filtered_events.append(event)
                
                return filtered_events, None
            
            return events, None
        elif response.status_code == 401:
            return [], "Invalid API key"
        elif response.status_code == 429:
            return [], "Rate limit exceeded"
        else:
            return [], f"API error: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return [], "Request timed out"
    except requests.exceptions.RequestException as e:
        return [], f"Request error: {str(e)}"


def find_event_for_matchup(
    events: List[Dict],
    home_team_tricode: str,
    away_team_tricode: str
) -> Optional[Dict]:
    """
    Find the matching event for a given matchup.
    
    Args:
        events: List of events from get_nba_events()
        home_team_tricode: Home team tricode (e.g., 'LAL')
        away_team_tricode: Away team tricode (e.g., 'BOS')
    
    Returns:
        Matching event dict or None
    """
    home_name = TEAM_TRICODE_TO_NAME.get(home_team_tricode, home_team_tricode)
    away_name = TEAM_TRICODE_TO_NAME.get(away_team_tricode, away_team_tricode)
    
    for event in events:
        event_home = event.get('home_team', '')
        event_away = event.get('away_team', '')
        
        # Check if teams match (API uses full names)
        home_match = home_name.lower() in event_home.lower() or event_home.lower() in home_name.lower()
        away_match = away_name.lower() in event_away.lower() or event_away.lower() in away_name.lower()
        
        if home_match and away_match:
            return event
    
    return None


def build_odds_request(
    event_id: str,
    markets: Optional[List[str]] = None,
    dry_run: bool = True
) -> Dict:
    """
    Build the odds request URL and parameters.
    Use dry_run=True to preview without actually making the request.
    
    Args:
        event_id: The event ID from The Odds API
        markets: List of market names. If None, uses all player prop markets.
        dry_run: If True, returns request info without making the call.
    
    Returns:
        Dict with request details (url, params, estimated_cost, etc.)
    """
    if markets is None:
        markets = list(STAT_TO_MARKET.values())
    
    url = f"{ODDS_API_BASE}/sports/{SPORT}/events/{event_id}/odds"
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': REGION,
        'bookmakers': BOOKMAKER,
        'markets': ','.join(markets),
        'oddsFormat': 'american',
        'dateFormat': 'iso'
    }
    
    request_info = {
        'url': url,
        'params': {k: v for k, v in params.items() if k != 'apiKey'},  # Hide API key in preview
        'params_with_key': params,  # Full params for actual request
        'full_url': f"{url}?{'&'.join(f'{k}={v}' for k, v in params.items() if k != 'apiKey')}",
        'markets_requested': markets,
        'region': REGION,
        'bookmaker': BOOKMAKER,
        'estimated_credits': 1,  # Single region + single bookmaker = 1 credit
        'dry_run': dry_run
    }
    
    return request_info


def fetch_player_props(event_id: str, markets: Optional[List[str]] = None) -> OddsAPIResponse:
    """
    Fetch player props for a specific event.
    THIS COSTS CREDITS - approximately 1 credit per request.
    
    Args:
        event_id: The event ID from The Odds API
        markets: List of market names. If None, uses all player prop markets.
    
    Returns:
        OddsAPIResponse with data and credit info
    """
    request_info = build_odds_request(event_id, markets, dry_run=False)
    
    try:
        response = requests.get(
            request_info['url'],
            params=request_info['params_with_key'],
            timeout=15
        )
        
        # Extract credit info from headers
        credits_used = int(float(response.headers.get('x-requests-used', 0)))
        credits_remaining = int(float(response.headers.get('x-requests-remaining', 0)))
        
        if response.status_code == 200:
            return OddsAPIResponse(
                success=True,
                data=response.json(),
                error=None,
                credits_used=credits_used,
                credits_remaining=credits_remaining
            )
        elif response.status_code == 401:
            # Try to get more details from response body
            try:
                error_detail = response.json().get('message', 'Invalid API key')
            except:
                error_detail = "Invalid API key"
            return OddsAPIResponse(
                success=False,
                data=None,
                error=f"Invalid API key: {error_detail}. Please verify your API key in The Odds API dashboard.",
                credits_used=credits_used,
                credits_remaining=credits_remaining
            )
        elif response.status_code == 429:
            return OddsAPIResponse(
                success=False,
                data=None,
                error="Rate limit exceeded or out of credits",
                credits_used=credits_used,
                credits_remaining=credits_remaining
            )
        elif response.status_code == 404:
            return OddsAPIResponse(
                success=False,
                data=None,
                error="Event not found or no odds available",
                credits_used=credits_used,
                credits_remaining=credits_remaining
            )
        else:
            return OddsAPIResponse(
                success=False,
                data=None,
                error=f"API error: {response.status_code} - {response.text}",
                credits_used=credits_used,
                credits_remaining=credits_remaining
            )
            
    except requests.exceptions.Timeout:
        return OddsAPIResponse(
            success=False,
            data=None,
            error="Request timed out",
            credits_used=0,
            credits_remaining=0
        )
    except requests.exceptions.RequestException as e:
        return OddsAPIResponse(
            success=False,
            data=None,
            error=f"Request error: {str(e)}",
            credits_used=0,
            credits_remaining=0
        )


def parse_all_player_props(api_response: Dict) -> Dict[str, Dict[str, PropLine]]:
    """
    Parse Underdog player props for ALL players from API response.
    This allows caching at the game level and filtering per player.
    
    Args:
        api_response: Response data from fetch_player_props()
    
    Returns:
        Dict of player_name (lowercase) -> Dict of stat code -> PropLine
    """
    all_props = {}
    
    if not api_response:
        return all_props
    
    # Handle both single event and list responses
    if isinstance(api_response, list):
        if len(api_response) == 0:
            return all_props
        event_data = api_response[0]
    else:
        event_data = api_response
    
    bookmakers = event_data.get('bookmakers', [])
    
    for bookmaker in bookmakers:
        if bookmaker.get('key') != BOOKMAKER:
            continue
        
        markets = bookmaker.get('markets', [])
        
        for market in markets:
            market_key = market.get('key', '')
            stat_code = MARKET_TO_STAT.get(market_key)
            
            if not stat_code:
                continue
            
            outcomes = market.get('outcomes', [])
            
            # Group outcomes by player name
            # Outcomes typically have 'description' with player name
            player_outcomes_map = {}
            for outcome in outcomes:
                player_desc = outcome.get('description', '')
                if not player_desc:
                    continue
                
                # Use lowercase name as key for consistent matching
                player_key = player_desc.lower().strip()
                if player_key not in player_outcomes_map:
                    player_outcomes_map[player_key] = {
                        'original_name': player_desc,
                        'outcomes': []
                    }
                player_outcomes_map[player_key]['outcomes'].append(outcome)
            
            # Parse each player's props
            for player_key, player_data in player_outcomes_map.items():
                if player_key not in all_props:
                    all_props[player_key] = {}
                
                outcomes_list = player_data['outcomes']
                
                # Get line value and odds
                line_value = None
                over_odds = -110
                under_odds = -110
                
                for outcome in outcomes_list:
                    point = outcome.get('point')
                    if point is not None:
                        line_value = point
                    
                    name = outcome.get('name', '').lower()
                    price = outcome.get('price', -110)
                    
                    if 'over' in name:
                        over_odds = price
                    elif 'under' in name:
                        under_odds = price
                
                if line_value is not None:
                    all_props[player_key][stat_code] = PropLine(
                        stat=stat_code,
                        line=line_value,
                        over_odds=over_odds,
                        under_odds=under_odds,
                        source='underdog'
                    )
    
    return all_props


def get_player_props_from_cached(
    all_props: Dict[str, Dict[str, PropLine]],
    player_name: str
) -> Dict[str, PropLine]:
    """
    Get props for a specific player from cached all-player props.
    
    Args:
        all_props: Result from parse_all_player_props()
        player_name: Player name to search for
    
    Returns:
        Dict of stat code -> PropLine for the player
    """
    if not all_props or not player_name:
        return {}
    
    search_lower = player_name.lower().strip()
    
    # Try exact match first
    if search_lower in all_props:
        return all_props[search_lower]
    
    # Try fuzzy matching
    for player_key, props in all_props.items():
        if _name_matches(player_key, search_lower):
            return props
    
    return {}


def parse_underdog_props(
    api_response: Dict,
    player_name: str
) -> Dict[str, PropLine]:
    """
    Parse Underdog player props from API response for a specific player.
    
    Args:
        api_response: Response data from fetch_player_props()
        player_name: Player name to search for (e.g., "LeBron James")
    
    Returns:
        Dict of stat code -> PropLine
    """
    # Use the new all-player parser and then filter
    all_props = parse_all_player_props(api_response)
    return get_player_props_from_cached(all_props, player_name)


def _name_matches(api_name: str, search_name: str) -> bool:
    """
    Check if player names match (handles variations).
    
    Args:
        api_name: Name from API response
        search_name: Name we're searching for
    
    Returns:
        True if names match
    """
    if not api_name or not search_name:
        return False
    
    api_lower = api_name.lower().strip()
    search_lower = search_name.lower().strip()
    
    # Exact match
    if api_lower == search_lower:
        return True
    
    # Check if one contains the other
    if api_lower in search_lower or search_lower in api_lower:
        return True
    
    # Split and check parts (handles "LeBron James" vs "James, LeBron")
    api_parts = set(api_lower.replace(',', '').split())
    search_parts = set(search_lower.replace(',', '').split())
    
    # If all significant parts match
    if len(api_parts & search_parts) >= 2:
        return True
    
    return False


def get_remaining_credits() -> Tuple[int, Optional[str]]:
    """
    Check remaining API credits by making a free events request.
    
    Returns:
        Tuple of (remaining credits, error message if any)
    """
    url = f"{ODDS_API_BASE}/sports/{SPORT}/events"
    params = {'apiKey': ODDS_API_KEY}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 401:
            try:
                error_detail = response.json().get('message', 'Invalid API key')
            except:
                error_detail = 'Invalid API key'
            return 0, f"Invalid API key: {error_detail}. Please verify your API key in The Odds API dashboard."
        elif response.status_code != 200:
            return 0, f"API error: {response.status_code}"
        
        remaining = int(float(response.headers.get('x-requests-remaining', 0)))
        return remaining, None
    except requests.exceptions.RequestException as e:
        return 0, f"Request error: {str(e)}"
    except Exception as e:
        return 0, str(e)


# ============================================================
# HIGH-LEVEL CONVENIENCE FUNCTIONS
# ============================================================

def fetch_all_props_for_game(
    home_team_tricode: str,
    away_team_tricode: str,
    game_date: str
) -> Tuple[Dict[str, Dict[str, PropLine]], OddsAPIResponse]:
    """
    Fetch ALL player props for a game. Use this for game-level caching.
    Costs 1 credit but returns props for all players in the game.
    
    Args:
        home_team_tricode: Home team tricode
        away_team_tricode: Away team tricode
        game_date: Game date (YYYY-MM-DD)
    
    Returns:
        Tuple of (all_props dict keyed by player name, API response with credit info)
    """
    # Step 1: Get events (free)
    events, error = get_nba_events(game_date)
    if error:
        return {}, OddsAPIResponse(
            success=False, data=None, error=error,
            credits_used=0, credits_remaining=0
        )
    
    # Step 2: Find matching event
    event = find_event_for_matchup(events, home_team_tricode, away_team_tricode)
    if not event:
        return {}, OddsAPIResponse(
            success=False, data=None,
            error=f"No event found for {away_team_tricode} @ {home_team_tricode} on {game_date}",
            credits_used=0, credits_remaining=0
        )
    
    # Step 3: Fetch props (costs credits)
    api_response = fetch_player_props(event['id'])
    
    if not api_response.success:
        return {}, api_response
    
    # Step 4: Parse ALL player props
    all_props = parse_all_player_props(api_response.data)
    
    return all_props, api_response


def get_live_odds_for_player(
    player_name: str,
    home_team_tricode: str,
    away_team_tricode: str,
    game_date: str,
    cached_game_props: Optional[Dict[str, Dict[str, PropLine]]] = None
) -> Tuple[Dict[str, PropLine], OddsAPIResponse]:
    """
    Complete flow to get live odds for a player.
    
    Args:
        player_name: Player's full name
        home_team_tricode: Home team tricode
        away_team_tricode: Away team tricode
        game_date: Game date (YYYY-MM-DD)
        cached_game_props: Optional pre-fetched props for the game (from fetch_all_props_for_game)
    
    Returns:
        Tuple of (props dict, API response with credit info)
    """
    # If cached props provided, use them (no API call needed)
    if cached_game_props is not None:
        props = get_player_props_from_cached(cached_game_props, player_name)
        return props, OddsAPIResponse(
            success=True,
            data={'cached': True, 'player_count': len(cached_game_props)},
            error=None,
            credits_used=0,
            credits_remaining=-1  # Unknown when using cache
        )
    
    # Otherwise, fetch fresh (costs 1 credit)
    all_props, api_response = fetch_all_props_for_game(
        home_team_tricode, away_team_tricode, game_date
    )
    
    if not api_response.success:
        return {}, api_response
    
    # Filter for specific player
    props = get_player_props_from_cached(all_props, player_name)
    
    return props, api_response


def get_all_players_with_props(all_props: Dict[str, Dict[str, PropLine]]) -> List[str]:
    """
    Get list of all player names that have props available.
    
    Args:
        all_props: Result from parse_all_player_props() or fetch_all_props_for_game()
    
    Returns:
        List of player names (as they appear in the API)
    """
    return list(all_props.keys())


def preview_odds_request(
    home_team_tricode: str,
    away_team_tricode: str,
    game_date: str
) -> Dict:
    """
    Preview what the odds request would look like without making it.
    Use this to verify setup before spending credits.
    
    Args:
        home_team_tricode: Home team tricode
        away_team_tricode: Away team tricode
        game_date: Game date (YYYY-MM-DD)
    
    Returns:
        Dict with preview information
    """
    preview = {
        'game': f"{away_team_tricode} @ {home_team_tricode}",
        'date': game_date,
        'event_id': None,
        'event_found': False,
        'request_info': None,
        'error': None,
        'available_markets': list(STAT_TO_MARKET.values()),
        'estimated_cost': '1 credit'
    }
    
    # Get events (free)
    events, error = get_nba_events(game_date)
    if error:
        preview['error'] = error
        return preview
    
    if not events:
        preview['error'] = f"No NBA events found for {game_date}"
        return preview
    
    # Find matching event
    event = find_event_for_matchup(events, home_team_tricode, away_team_tricode)
    if not event:
        preview['error'] = f"No matching event found for {away_team_tricode} @ {home_team_tricode}"
        preview['events_on_date'] = [
            f"{e.get('away_team', 'Unknown')} @ {e.get('home_team', 'Unknown')}"
            for e in events
        ]
        return preview
    
    preview['event_found'] = True
    preview['event_id'] = event['id']
    preview['event_details'] = {
        'id': event['id'],
        'home_team': event.get('home_team'),
        'away_team': event.get('away_team'),
        'commence_time': event.get('commence_time')
    }
    
    # Build request preview
    preview['request_info'] = build_odds_request(event['id'], dry_run=True)
    
    return preview
