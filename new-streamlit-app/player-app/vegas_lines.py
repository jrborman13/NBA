"""
Vegas Lines Module
Functions to handle player prop lines for comparison with predictions.
Can be extended to use live odds APIs (e.g., The Odds API, ESPN, etc.)
"""

import pandas as pd
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import date
import json
import os

# File to store manually entered lines
LINES_FILE = "player_lines.json"


@dataclass
class PropLine:
    """Container for a player prop line"""
    stat: str
    line: float
    over_odds: int  # American odds (e.g., -110)
    under_odds: int
    source: str  # 'manual', 'draftkings', 'fanduel', etc.


def load_saved_lines() -> Dict:
    """Load previously saved lines from file"""
    if os.path.exists(LINES_FILE):
        try:
            with open(LINES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_lines(lines: Dict):
    """Save lines to file"""
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


# Future: API integration placeholder
def fetch_live_odds(
    player_name: str,
    game_date: str,
    api_key: Optional[str] = None
) -> Optional[Dict[str, PropLine]]:
    """
    Placeholder for fetching live odds from an API.
    
    To implement:
    1. Sign up for an odds API (e.g., The Odds API)
    2. Set API key in environment variable
    3. Make API request for player props
    
    Example APIs:
    - The Odds API (https://the-odds-api.com/)
    - ESPN unofficial API
    - Action Network
    """
    # TODO: Implement live odds fetching
    # api_key = os.environ.get('ODDS_API_KEY') or api_key
    # if not api_key:
    #     return None
    #
    # response = requests.get(
    #     f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds",
    #     params={'apiKey': api_key, 'markets': 'player_points,player_rebounds,player_assists'}
    # )
    # ...parse response...
    
    return None  # Not implemented

