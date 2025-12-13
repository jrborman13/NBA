"""
Prediction Tracker Module
System to log predictions and track accuracy over time.
Data can be used to train ML models.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from datetime import datetime, date
import json
import os
import csv

# File paths
PREDICTIONS_FILE = "predictions_log.csv"
ACCURACY_SUMMARY_FILE = "accuracy_summary.json"


@dataclass
class PredictionRecord:
    """Record of a single prediction"""
    timestamp: str
    player_id: str
    player_name: str
    opponent_abbr: str
    game_date: str
    stat: str
    prediction: float
    vegas_line: Optional[float]
    actual: Optional[float]
    is_home: bool
    days_rest: int
    confidence: str
    # Features used
    season_avg: float
    l5_avg: float
    l10_avg: float
    vs_opponent_avg: Optional[float]
    opp_def_rating: float
    opp_pace: float
    usage_rate: float


def log_prediction(record: PredictionRecord):
    """
    Log a prediction to the CSV file.
    """
    file_exists = os.path.exists(PREDICTIONS_FILE)
    
    with open(PREDICTIONS_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=asdict(record).keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(asdict(record))


def log_predictions_batch(records: List[PredictionRecord]):
    """
    Log multiple predictions at once.
    """
    for record in records:
        log_prediction(record)


def update_actual_result(
    player_id: str,
    game_date: str,
    stat: str,
    actual_value: float
):
    """
    Update a prediction record with the actual result.
    """
    if not os.path.exists(PREDICTIONS_FILE):
        return False
    
    df = pd.read_csv(PREDICTIONS_FILE)
    
    mask = (
        (df['player_id'] == player_id) &
        (df['game_date'] == game_date) &
        (df['stat'] == stat)
    )
    
    if mask.any():
        df.loc[mask, 'actual'] = actual_value
        df.to_csv(PREDICTIONS_FILE, index=False)
        return True
    
    return False


def get_predictions_dataframe() -> pd.DataFrame:
    """
    Load all predictions as a DataFrame.
    """
    if os.path.exists(PREDICTIONS_FILE):
        return pd.read_csv(PREDICTIONS_FILE)
    return pd.DataFrame()


def calculate_accuracy_metrics(df: pd.DataFrame = None) -> Dict:
    """
    Calculate accuracy metrics for predictions.
    
    Returns:
        Dict with accuracy metrics by stat
    """
    if df is None:
        df = get_predictions_dataframe()
    
    if len(df) == 0 or 'actual' not in df.columns:
        return {}
    
    # Filter to records with actual results
    df_with_actuals = df[df['actual'].notna()].copy()
    
    if len(df_with_actuals) == 0:
        return {}
    
    metrics = {}
    
    for stat in df_with_actuals['stat'].unique():
        stat_df = df_with_actuals[df_with_actuals['stat'] == stat]
        
        if len(stat_df) == 0:
            continue
        
        predictions = stat_df['prediction'].values
        actuals = stat_df['actual'].values
        lines = stat_df['vegas_line'].values
        
        # Mean Absolute Error
        mae = np.mean(np.abs(predictions - actuals))
        
        # Root Mean Square Error
        rmse = np.sqrt(np.mean((predictions - actuals) ** 2))
        
        # Mean Error (bias - positive = over-predicting)
        bias = np.mean(predictions - actuals)
        
        # Over/Under accuracy (vs actual)
        correct_direction = np.sum(
            ((predictions > actuals) & (actuals > 0)) |
            ((predictions < actuals) & (actuals > 0))
        )
        
        # Hit rate vs Vegas line (if available)
        valid_lines = ~np.isnan(lines)
        if valid_lines.any():
            over_wins = np.sum(
                (actuals[valid_lines] > lines[valid_lines]) & 
                (predictions[valid_lines] > lines[valid_lines])
            )
            under_wins = np.sum(
                (actuals[valid_lines] < lines[valid_lines]) & 
                (predictions[valid_lines] < lines[valid_lines])
            )
            total_with_lines = valid_lines.sum()
            vs_line_accuracy = (over_wins + under_wins) / total_with_lines * 100 if total_with_lines > 0 else 0
        else:
            vs_line_accuracy = None
        
        # Within X% accuracy
        within_10_pct = np.mean(np.abs(predictions - actuals) / actuals * 100 <= 10) * 100
        within_20_pct = np.mean(np.abs(predictions - actuals) / actuals * 100 <= 20) * 100
        
        metrics[stat] = {
            'count': len(stat_df),
            'mae': round(mae, 2),
            'rmse': round(rmse, 2),
            'bias': round(bias, 2),
            'vs_line_accuracy': round(vs_line_accuracy, 1) if vs_line_accuracy else None,
            'within_10_pct': round(within_10_pct, 1),
            'within_20_pct': round(within_20_pct, 1),
        }
    
    return metrics


def calculate_accuracy_by_confidence(df: pd.DataFrame = None) -> Dict:
    """
    Calculate accuracy broken down by confidence level.
    """
    if df is None:
        df = get_predictions_dataframe()
    
    df_with_actuals = df[df['actual'].notna()].copy()
    
    if len(df_with_actuals) == 0:
        return {}
    
    results = {}
    
    for confidence in ['high', 'medium', 'low']:
        conf_df = df_with_actuals[df_with_actuals['confidence'] == confidence]
        
        if len(conf_df) == 0:
            continue
        
        predictions = conf_df['prediction'].values
        actuals = conf_df['actual'].values
        
        mae = np.mean(np.abs(predictions - actuals))
        within_10_pct = np.mean(np.abs(predictions - actuals) / actuals * 100 <= 10) * 100
        
        results[confidence] = {
            'count': len(conf_df),
            'mae': round(mae, 2),
            'within_10_pct': round(within_10_pct, 1),
        }
    
    return results


def get_recent_predictions(n: int = 50) -> pd.DataFrame:
    """
    Get most recent predictions.
    """
    df = get_predictions_dataframe()
    if len(df) == 0:
        return df
    
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df.nlargest(n, 'timestamp')


def get_player_prediction_history(player_id: str) -> pd.DataFrame:
    """
    Get prediction history for a specific player.
    """
    df = get_predictions_dataframe()
    return df[df['player_id'] == player_id]


def save_accuracy_summary():
    """
    Calculate and save accuracy summary to JSON.
    """
    metrics = calculate_accuracy_metrics()
    by_confidence = calculate_accuracy_by_confidence()
    
    summary = {
        'last_updated': datetime.now().isoformat(),
        'by_stat': metrics,
        'by_confidence': by_confidence,
    }
    
    with open(ACCURACY_SUMMARY_FILE, 'w') as f:
        json.dump(summary, f, indent=2)


def get_accuracy_summary() -> Dict:
    """
    Load accuracy summary from file.
    """
    if os.path.exists(ACCURACY_SUMMARY_FILE):
        with open(ACCURACY_SUMMARY_FILE, 'r') as f:
            return json.load(f)
    return {}


def export_for_ml_training() -> pd.DataFrame:
    """
    Export prediction data in format suitable for ML training.
    
    Returns:
        DataFrame with features and targets
    """
    df = get_predictions_dataframe()
    
    if len(df) == 0 or 'actual' not in df.columns:
        return pd.DataFrame()
    
    # Filter to records with actual results
    df_ml = df[df['actual'].notna()].copy()
    
    # Feature columns
    feature_cols = [
        'season_avg', 'l5_avg', 'l10_avg', 'vs_opponent_avg',
        'opp_def_rating', 'opp_pace', 'usage_rate',
        'is_home', 'days_rest'
    ]
    
    # Convert boolean to int
    df_ml['is_home'] = df_ml['is_home'].astype(int)
    
    # Fill missing vs_opponent_avg with season_avg
    df_ml['vs_opponent_avg'] = df_ml['vs_opponent_avg'].fillna(df_ml['season_avg'])
    
    return df_ml[['stat', 'actual'] + feature_cols]


def create_prediction_record_from_dict(
    player_id: str,
    player_name: str,
    opponent_abbr: str,
    game_date: str,
    stat: str,
    prediction_dict: Dict,
    features_dict: Dict,
    vegas_line: Optional[float] = None
) -> PredictionRecord:
    """
    Create a PredictionRecord from prediction and features dictionaries.
    """
    rolling_avgs = features_dict.get('rolling_avgs', {})
    
    return PredictionRecord(
        timestamp=datetime.now().isoformat(),
        player_id=player_id,
        player_name=player_name,
        opponent_abbr=opponent_abbr,
        game_date=game_date,
        stat=stat,
        prediction=prediction_dict.value,
        vegas_line=vegas_line,
        actual=None,
        is_home=features_dict.get('is_home', True),
        days_rest=features_dict.get('days_rest', 2),
        confidence=prediction_dict.confidence,
        season_avg=rolling_avgs.get('Season', {}).get(stat, 0.0),
        l5_avg=rolling_avgs.get('L5', {}).get(stat, 0.0),
        l10_avg=rolling_avgs.get('L10', {}).get(stat, 0.0),
        vs_opponent_avg=features_dict.get('vs_opponent', {}).get(stat),
        opp_def_rating=features_dict.get('opponent', {}).get('def_rating', 110.0),
        opp_pace=features_dict.get('opponent', {}).get('pace', 100.0),
        usage_rate=features_dict.get('usage_rate', 20.0),
    )

