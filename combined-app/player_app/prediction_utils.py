"""
Prediction Utilities Module
Helper functions for player stat predictions.
Kept separate from main codebase for modularity.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# Current season configuration
CURRENT_SEASON = "2024-25"
LEAGUE_ID = "00"


def calculate_days_rest(game_dates: List[str], target_date: str) -> int:
    """
    Calculate days of rest before a game.
    
    Args:
        game_dates: List of game dates (YYYY-MM-DD format) sorted descending
        target_date: The date of the upcoming game
    
    Returns:
        Number of days since last game (0 = back-to-back, 1 = one day rest, etc.)
    """
    if not game_dates:
        return 3  # Default to well-rested if no games found
    
    target = pd.to_datetime(target_date).date()
    
    for game_date in game_dates:
        game = pd.to_datetime(game_date).date()
        if game < target:
            return (target - game).days
    
    return 3  # Default if no previous games found


def is_back_to_back(days_rest: int) -> bool:
    """Check if game is a back-to-back (played yesterday)"""
    return days_rest == 1


def calculate_trend(values: List[float], window: int = 5) -> float:
    """
    Calculate trend direction from recent values.
    
    Returns:
        Positive = trending up, Negative = trending down, 0 = stable
    """
    if len(values) < window:
        return 0.0
    
    recent = values[:window]
    older = values[window:window*2] if len(values) >= window*2 else values[window:]
    
    if not older:
        return 0.0
    
    recent_avg = np.mean(recent)
    older_avg = np.mean(older)
    
    if older_avg == 0:
        return 0.0
    
    return round((recent_avg - older_avg) / older_avg * 100, 1)


def calculate_consistency(values: List[float]) -> float:
    """
    Calculate consistency score (lower std dev = more consistent).
    
    Returns:
        Coefficient of variation (std/mean) as percentage
    """
    if not values or len(values) < 3:
        return 0.0
    
    mean = np.mean(values)
    if mean == 0:
        return 0.0
    
    std = np.std(values)
    return round(std / mean * 100, 1)


def calculate_over_rate(values: List[float], threshold: float) -> float:
    """
    Calculate how often a player goes over a threshold.
    
    Args:
        values: List of stat values
        threshold: The line/threshold to compare against
    
    Returns:
        Percentage of games over the threshold
    """
    if not values:
        return 0.0
    
    over_count = sum(1 for v in values if v > threshold)
    return round(over_count / len(values) * 100, 1)


def weighted_average(values: List[float], decay: float = 0.9) -> float:
    """
    Calculate exponentially weighted average (more recent = higher weight).
    
    Args:
        values: List of values (most recent first)
        decay: Weight decay factor (0.9 means each older game is 90% of previous weight)
    
    Returns:
        Weighted average
    """
    if not values:
        return 0.0
    
    weights = [decay ** i for i in range(len(values))]
    weighted_sum = sum(v * w for v, w in zip(values, weights))
    weight_total = sum(weights)
    
    return round(weighted_sum / weight_total, 1) if weight_total > 0 else 0.0


def normalize_stat(value: float, league_avg: float, league_std: float) -> float:
    """
    Normalize a stat relative to league average (z-score).
    
    Returns:
        Z-score (0 = average, positive = above average)
    """
    if league_std == 0:
        return 0.0
    return round((value - league_avg) / league_std, 2)


def calculate_matchup_adjustment(
    player_avg: float,
    opp_def_rating: float,
    league_avg_def_rating: float
) -> float:
    """
    Adjust player average based on opponent defensive strength.
    
    Args:
        player_avg: Player's average for the stat
        opp_def_rating: Opponent's defensive rating (points allowed per 100 poss)
        league_avg_def_rating: League average defensive rating
    
    Returns:
        Adjusted prediction
    """
    if league_avg_def_rating == 0:
        return player_avg
    
    # Higher def rating = worse defense = boost prediction
    adjustment_factor = opp_def_rating / league_avg_def_rating
    return round(player_avg * adjustment_factor, 1)


def calculate_pace_adjustment(
    player_avg: float,
    opp_pace: float,
    league_avg_pace: float
) -> float:
    """
    Adjust player average based on opponent pace.
    
    Args:
        player_avg: Player's average for the stat
        opp_pace: Opponent's pace (possessions per game)
        league_avg_pace: League average pace
    
    Returns:
        Adjusted prediction
    """
    if league_avg_pace == 0:
        return player_avg
    
    # Higher pace = more possessions = more stat opportunities
    adjustment_factor = opp_pace / league_avg_pace
    return round(player_avg * adjustment_factor, 1)


def get_home_away_split(
    home_avg: float,
    away_avg: float,
    is_home: bool
) -> float:
    """
    Get the appropriate split based on home/away status.
    """
    return home_avg if is_home else away_avg


def calculate_rest_adjustment(days_rest: int) -> float:
    """
    Calculate adjustment factor based on rest.
    
    Returns:
        Multiplier (1.0 = no adjustment)
    """
    if days_rest == 1:  # Back-to-back
        return 0.95  # 5% reduction
    elif days_rest == 2:  # One day rest
        return 1.0  # Normal
    elif days_rest >= 3:  # Well rested
        return 1.02  # Slight boost
    else:
        return 1.0


def combine_predictions(
    predictions: Dict[str, float],
    weights: Optional[Dict[str, float]] = None
) -> float:
    """
    Combine multiple prediction methods with weights.
    
    Args:
        predictions: Dict of method_name -> predicted_value
        weights: Optional dict of method_name -> weight (defaults to equal)
    
    Returns:
        Weighted combined prediction
    """
    if not predictions:
        return 0.0
    
    if weights is None:
        weights = {k: 1.0 for k in predictions.keys()}
    
    weighted_sum = sum(predictions[k] * weights.get(k, 1.0) for k in predictions)
    weight_total = sum(weights.get(k, 1.0) for k in predictions)
    
    return round(weighted_sum / weight_total, 1) if weight_total > 0 else 0.0


def format_prediction_output(
    stat_name: str,
    prediction: float,
    confidence: str,
    factors: Dict[str, str]
) -> Dict:
    """
    Format prediction output for display.
    """
    return {
        'stat': stat_name,
        'prediction': prediction,
        'confidence': confidence,
        'factors': factors
    }

