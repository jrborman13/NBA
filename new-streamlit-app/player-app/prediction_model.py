"""
Prediction Model Module
Baseline prediction model for player stats.
Kept separate from main codebase for modularity.
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
import prediction_utils as utils
import prediction_features as features


@dataclass
class Prediction:
    """Container for a stat prediction"""
    stat: str
    value: float
    confidence: str  # 'high', 'medium', 'low'
    breakdown: Dict[str, float]  # Component predictions
    factors: Dict[str, str]  # Explanations


class PlayerStatPredictor:
    """
    Baseline prediction model for player stats.
    
    Methodology:
    1. Start with weighted rolling average (recent games weighted more)
    2. Apply opponent defensive adjustment
    3. Apply pace adjustment
    4. Apply home/away adjustment
    5. Apply rest adjustment
    6. Factor in historical performance vs opponent
    """
    
    def __init__(self):
        self.weights = {
            'weighted_avg': 0.35,      # Weighted recent performance
            'L5_avg': 0.25,            # Last 5 games average
            'season_avg': 0.20,        # Season average
            'vs_opponent': 0.20,       # Historical vs opponent (if available)
        }
    
    def predict_stat(
        self,
        stat: str,
        player_features: Dict
    ) -> Prediction:
        """
        Generate prediction for a single stat.
        
        Args:
            stat: Stat to predict ('PTS', 'REB', 'AST', 'PRA', etc.)
            player_features: Dict from get_all_prediction_features()
        
        Returns:
            Prediction object with value and breakdown
        """
        breakdown = {}
        factors = {}
        
        rolling_avgs = player_features.get('rolling_avgs', {})
        
        # 1. Get base averages
        season_avg = rolling_avgs.get('Season', {}).get(stat, 0.0)
        l5_avg = rolling_avgs.get('L5', {}).get(stat, season_avg)
        l3_avg = rolling_avgs.get('L3', {}).get(stat, l5_avg)
        
        breakdown['season_avg'] = season_avg
        breakdown['L5_avg'] = l5_avg
        
        # 2. Calculate weighted average (exponential decay)
        # This gives more weight to recent games
        game_logs = features.get_player_game_logs(str(player_features.get('player_id', '')))
        if len(game_logs) > 0 and stat in game_logs.columns:
            recent_values = game_logs[stat].head(10).tolist()
            weighted_avg = utils.weighted_average(recent_values, decay=0.85)
        else:
            weighted_avg = l5_avg
        breakdown['weighted_avg'] = weighted_avg
        
        # 3. Historical vs opponent
        vs_opp = player_features.get('vs_opponent', {})
        vs_opp_avg = vs_opp.get(stat, 0.0)
        vs_opp_games = vs_opp.get('games_played', 0)
        
        if vs_opp_games > 0:
            breakdown['vs_opponent'] = vs_opp_avg
            factors['vs_opponent'] = f"Avg of {vs_opp_avg} in {vs_opp_games} games vs opponent"
        
        # 4. Combine base predictions
        if vs_opp_games >= 2:
            # Use opponent history if enough sample
            base_prediction = (
                self.weights['weighted_avg'] * weighted_avg +
                self.weights['L5_avg'] * l5_avg +
                self.weights['season_avg'] * season_avg +
                self.weights['vs_opponent'] * vs_opp_avg
            )
        else:
            # No opponent history - redistribute weight
            adjusted_weights = {
                'weighted_avg': 0.45,
                'L5_avg': 0.30,
                'season_avg': 0.25,
            }
            base_prediction = (
                adjusted_weights['weighted_avg'] * weighted_avg +
                adjusted_weights['L5_avg'] * l5_avg +
                adjusted_weights['season_avg'] * season_avg
            )
        
        breakdown['base_prediction'] = round(base_prediction, 1)
        
        # 5. Apply adjustments
        adjusted_prediction = base_prediction
        
        # Opponent defensive adjustment
        opp_stats = player_features.get('opponent', {})
        league_avg = player_features.get('league_avg', {})
        
        opp_def_rating = opp_stats.get('def_rating', 110.0)
        league_def_rating = league_avg.get('def_rating', 110.0)
        
        if stat in ['PTS', 'PRA']:  # Only adjust scoring stats
            def_adjustment = opp_def_rating / league_def_rating
            adjusted_prediction *= def_adjustment
            factors['defense'] = f"Opp DEF RTG {opp_def_rating} vs league avg {league_def_rating}"
        
        # Pace adjustment
        opp_pace = opp_stats.get('pace', 100.0)
        league_pace = league_avg.get('pace', 100.0)
        
        pace_adjustment = opp_pace / league_pace
        adjusted_prediction *= pace_adjustment
        factors['pace'] = f"Opp PACE {opp_pace} vs league avg {league_pace}"
        
        # Home/Away adjustment
        is_home = player_features.get('is_home', True)
        home_away_splits = player_features.get('home_away_splits', {})
        
        if is_home:
            location_avg = home_away_splits.get('home', {}).get(stat, season_avg)
            factors['location'] = "Home game"
        else:
            location_avg = home_away_splits.get('away', {}).get(stat, season_avg)
            factors['location'] = "Away game"
        
        # Blend location adjustment (don't overweight)
        if location_avg > 0:
            location_factor = location_avg / season_avg if season_avg > 0 else 1.0
            adjusted_prediction *= (0.7 + 0.3 * location_factor)
        
        # Rest adjustment
        days_rest = player_features.get('days_rest', 2)
        rest_factor = utils.calculate_rest_adjustment(days_rest)
        adjusted_prediction *= rest_factor
        
        if days_rest == 1:
            factors['rest'] = "Back-to-back game (-5%)"
        elif days_rest >= 3:
            factors['rest'] = f"{days_rest} days rest (+2%)"
        else:
            factors['rest'] = f"{days_rest} days rest (normal)"
        
        breakdown['adjusted_prediction'] = round(adjusted_prediction, 1)
        
        # 6. Calculate confidence
        confidence = self._calculate_confidence(stat, player_features)
        
        return Prediction(
            stat=stat,
            value=round(adjusted_prediction, 1),
            confidence=confidence,
            breakdown=breakdown,
            factors=factors
        )
    
    def _calculate_confidence(self, stat: str, player_features: Dict) -> str:
        """
        Calculate confidence level based on data quality.
        """
        confidence_score = 0
        
        # More games = higher confidence
        rolling_avgs = player_features.get('rolling_avgs', {})
        if 'L10' in rolling_avgs:
            confidence_score += 2
        if 'L5' in rolling_avgs:
            confidence_score += 1
        
        # Historical vs opponent adds confidence
        vs_opp = player_features.get('vs_opponent', {})
        if vs_opp.get('games_played', 0) >= 2:
            confidence_score += 2
        elif vs_opp.get('games_played', 0) >= 1:
            confidence_score += 1
        
        # Low consistency = lower confidence
        consistency = player_features.get('consistency', {}).get(stat, 50)
        if consistency < 30:
            confidence_score += 1  # Consistent player
        elif consistency > 50:
            confidence_score -= 1  # Volatile player
        
        # Back-to-back = lower confidence
        if player_features.get('is_back_to_back', False):
            confidence_score -= 1
        
        if confidence_score >= 4:
            return 'high'
        elif confidence_score >= 2:
            return 'medium'
        else:
            return 'low'
    
    def predict_all_stats(self, player_features: Dict) -> Dict[str, Prediction]:
        """
        Generate predictions for all key stats.
        PRA is calculated as the sum of PTS + REB + AST, not predicted independently.
        """
        # Predict individual stats first
        stats_to_predict = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M']
        
        predictions = {}
        for stat in stats_to_predict:
            predictions[stat] = self.predict_stat(stat, player_features)
        
        # Calculate PRA from the sum of PTS + REB + AST predictions
        pts_pred = predictions['PTS'].value
        reb_pred = predictions['REB'].value
        ast_pred = predictions['AST'].value
        pra_value = round(pts_pred + reb_pred + ast_pred, 1)
        
        # Determine PRA confidence (use the lowest confidence of the three components)
        confidence_levels = {'high': 3, 'medium': 2, 'low': 1}
        min_confidence = min(
            confidence_levels[predictions['PTS'].confidence],
            confidence_levels[predictions['REB'].confidence],
            confidence_levels[predictions['AST'].confidence]
        )
        pra_confidence = {3: 'high', 2: 'medium', 1: 'low'}[min_confidence]
        
        # Create PRA prediction
        predictions['PRA'] = Prediction(
            stat='PRA',
            value=pra_value,
            confidence=pra_confidence,
            breakdown={
                'PTS': pts_pred,
                'REB': reb_pred,
                'AST': ast_pred,
                'season_avg': predictions['PTS'].breakdown.get('season_avg', 0) + 
                             predictions['REB'].breakdown.get('season_avg', 0) + 
                             predictions['AST'].breakdown.get('season_avg', 0),
            },
            factors={
                'calculation': f"PTS ({pts_pred}) + REB ({reb_pred}) + AST ({ast_pred})"
            }
        )
        
        return predictions


def generate_prediction(
    player_id: str,
    opponent_team_id: int,
    opponent_abbr: str,
    game_date: str,
    is_home: bool
) -> Dict[str, Prediction]:
    """
    Main entry point for generating predictions.
    
    Args:
        player_id: NBA API player ID
        opponent_team_id: Opponent's team ID
        opponent_abbr: Opponent's team abbreviation (e.g., 'LAL')
        game_date: Date of the game (YYYY-MM-DD)
        is_home: Whether player's team is playing at home
    
    Returns:
        Dict of stat -> Prediction
    """
    # Gather all features
    player_features = features.get_all_prediction_features(
        player_id=player_id,
        opponent_team_id=opponent_team_id,
        opponent_abbr=opponent_abbr,
        game_date=game_date,
        is_home=is_home
    )
    
    # Store player_id in features for use in prediction
    player_features['player_id'] = player_id
    
    # Generate predictions
    predictor = PlayerStatPredictor()
    predictions = predictor.predict_all_stats(player_features)
    
    return predictions


def format_predictions_for_display(predictions: Dict[str, Prediction]) -> pd.DataFrame:
    """
    Format predictions into a DataFrame for display.
    """
    rows = []
    for stat, pred in predictions.items():
        rows.append({
            'Stat': stat,
            'Prediction': pred.value,
            'Confidence': pred.confidence.capitalize(),
            'Season Avg': pred.breakdown.get('season_avg', 'N/A'),
            'L5 Avg': pred.breakdown.get('L5_avg', 'N/A'),
            'vs Opp': pred.breakdown.get('vs_opponent', 'N/A'),
        })
    
    return pd.DataFrame(rows)


def get_prediction_summary(predictions: Dict[str, Prediction]) -> str:
    """
    Generate a text summary of predictions.
    """
    pts = predictions.get('PTS')
    reb = predictions.get('REB')
    ast = predictions.get('AST')
    pra = predictions.get('PRA')
    
    summary = f"**Predicted Line:**\n"
    summary += f"- Points: {pts.value} ({pts.confidence} confidence)\n"
    summary += f"- Rebounds: {reb.value} ({reb.confidence} confidence)\n"
    summary += f"- Assists: {ast.value} ({ast.confidence} confidence)\n"
    summary += f"- PRA: {pra.value} ({pra.confidence} confidence)\n"
    
    return summary

