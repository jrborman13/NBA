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
import matchup_stats as ms


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
        # Use game_logs from features dict (already cached) instead of re-fetching
        game_logs = player_features.get('game_logs', pd.DataFrame())
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
        
        # Matchup-specific adjustment (PTS_PAINT, PTS_FB, PTS_2ND_CHANCE)
        matchup_data = player_features.get('matchup', {})
        matchup_adjustments = matchup_data.get('matchup_adjustments', {})
        
        if stat == 'PTS':
            # Apply overall matchup factor for points
            overall_factor = matchup_adjustments.get('overall_pts_factor', 1.0)
            if overall_factor != 1.0:
                # Apply a moderate portion of the matchup adjustment (50%)
                matchup_adjustment = 1.0 + 0.5 * (overall_factor - 1.0)
                adjusted_prediction *= matchup_adjustment
                
                player_breakdown = matchup_data.get('player_scoring_breakdown', {})
                opp_vuln = matchup_data.get('opponent_vulnerabilities', {})
                
                if overall_factor > 1.0:
                    factors['matchup'] = (
                        f"Favorable matchup (+{round((overall_factor-1)*100, 1)}%): "
                        f"Paint {player_breakdown.get('pts_paint', 0)} vs opp allows {opp_vuln.get('opp_pts_paint_allowed', 0)}"
                    )
                else:
                    factors['matchup'] = (
                        f"Tough matchup ({round((overall_factor-1)*100, 1)}%): "
                        f"Paint {player_breakdown.get('pts_paint', 0)} vs opp allows {opp_vuln.get('opp_pts_paint_allowed', 0)}"
                    )
        
        # FT Rate adjustment for FTM predictions
        # If opponent allows more FT attempts (higher FT Rate), player likely to get more FTM
        if stat == 'FTM':
            # Get opponent's FT Rate allowed (need to load from team_defensive_stats)
            player_ft_rate = player_features.get('player_ft_rate', 25.0)
            # Assume league average FT Rate is around 25%
            league_avg_ft_rate = 25.0
            
            # If player has higher than average FT Rate, they get to the line more
            player_ft_rate_factor = player_ft_rate / league_avg_ft_rate if league_avg_ft_rate > 0 else 1.0
            
            # Apply a moderate adjustment based on player's tendency to get to the line
            ft_adjustment = 0.8 + 0.2 * player_ft_rate_factor
            adjusted_prediction *= ft_adjustment
            factors['ft_rate'] = f"Player FT Rate: {player_ft_rate}% (league avg ~{league_avg_ft_rate}%)"
        
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
        FPTS uses Underdog formula: PTS*1 + REB*1.2 + AST*1.5 + STL*3 + BLK*3 - TOV*1
        """
        # Predict individual stats first (including TOV for fantasy calculation)
        stats_to_predict = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M', 'FTM', 'TOV']
        
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
        
        # Calculate RA (Rebounds + Assists) from the sum of REB + AST predictions
        ra_value = round(reb_pred + ast_pred, 1)
        
        # Determine RA confidence (use the lowest confidence of the two components)
        ra_min_confidence = min(
            confidence_levels[predictions['REB'].confidence],
            confidence_levels[predictions['AST'].confidence]
        )
        ra_confidence = {3: 'high', 2: 'medium', 1: 'low'}[ra_min_confidence]
        
        # Create RA prediction
        predictions['RA'] = Prediction(
            stat='RA',
            value=ra_value,
            confidence=ra_confidence,
            breakdown={
                'REB': reb_pred,
                'AST': ast_pred,
                'season_avg': predictions['REB'].breakdown.get('season_avg', 0) + 
                             predictions['AST'].breakdown.get('season_avg', 0),
            },
            factors={
                'calculation': f"REB ({reb_pred}) + AST ({ast_pred})"
            }
        )
        
        # Calculate FPTS (Fantasy Points) using Underdog formula:
        # PTS*1 + REB*1.2 + AST*1.5 + STL*3 + BLK*3 - TOV*1
        stl_pred = predictions['STL'].value
        blk_pred = predictions['BLK'].value
        tov_pred = predictions['TOV'].value
        
        fpts_value = round(
            pts_pred * 1.0 +
            reb_pred * 1.2 +
            ast_pred * 1.5 +
            stl_pred * 3.0 +
            blk_pred * 3.0 -
            tov_pred * 1.0,
            1
        )
        
        # Determine FPTS confidence (use the lowest confidence of all components)
        fpts_min_confidence = min(
            confidence_levels[predictions['PTS'].confidence],
            confidence_levels[predictions['REB'].confidence],
            confidence_levels[predictions['AST'].confidence],
            confidence_levels[predictions['STL'].confidence],
            confidence_levels[predictions['BLK'].confidence],
            confidence_levels[predictions['TOV'].confidence]
        )
        fpts_confidence = {3: 'high', 2: 'medium', 1: 'low'}[fpts_min_confidence]
        
        # Create FPTS prediction
        predictions['FPTS'] = Prediction(
            stat='FPTS',
            value=fpts_value,
            confidence=fpts_confidence,
            breakdown={
                'PTS': pts_pred,
                'REB': reb_pred,
                'AST': ast_pred,
                'STL': stl_pred,
                'BLK': blk_pred,
                'TOV': tov_pred,
            },
            factors={
                'calculation': f"PTS({pts_pred})×1 + REB({reb_pred})×1.2 + AST({ast_pred})×1.5 + STL({stl_pred})×3 + BLK({blk_pred})×3 - TOV({tov_pred})×1"
            }
        )
        
        return predictions


def generate_prediction(
    player_id: str,
    player_team_id: int,
    opponent_team_id: int,
    opponent_abbr: str,
    game_date: str,
    is_home: bool
) -> Dict[str, Prediction]:
    """
    Main entry point for generating predictions.
    
    Args:
        player_id: NBA API player ID
        player_team_id: Player's team ID (for rest calculation)
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
        player_team_id=player_team_id,
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


def generate_predictions_for_game(
    player_ids: List[str],
    player_names: Dict[str, str],
    player_team_ids: Dict[str, int],
    away_team_id: int,
    home_team_id: int,
    away_team_abbr: str,
    home_team_abbr: str,
    game_date: str,
    progress_callback=None
) -> Dict[str, Dict[str, Prediction]]:
    """
    Generate predictions for ALL players in a game.
    Used for batch processing and game-level caching.
    
    Args:
        player_ids: List of player IDs to generate predictions for
        player_names: Dict of player_id -> player_name
        player_team_ids: Dict of player_id -> team_id
        away_team_id: Away team ID
        home_team_id: Home team ID
        away_team_abbr: Away team abbreviation
        home_team_abbr: Home team abbreviation
        game_date: Game date (YYYY-MM-DD)
        progress_callback: Optional callback(current, total, player_name) for progress updates
    
    Returns:
        Dict of player_id -> Dict of stat -> Prediction
    """
    all_predictions = {}
    total = len(player_ids)
    
    for idx, player_id in enumerate(player_ids):
        player_name = player_names.get(player_id, f"Player {player_id}")
        player_team_id = player_team_ids.get(player_id)
        
        if not player_team_id:
            continue
        
        # Determine opponent and home/away status
        if int(player_team_id) == int(away_team_id):
            opponent_team_id = home_team_id
            opponent_abbr = home_team_abbr
            is_home = False
        elif int(player_team_id) == int(home_team_id):
            opponent_team_id = away_team_id
            opponent_abbr = away_team_abbr
            is_home = True
        else:
            continue  # Player not in this matchup
        
        # Update progress
        if progress_callback:
            progress_callback(idx + 1, total, player_name)
        
        try:
            # Generate predictions for this player
            predictions = generate_prediction(
                player_id=player_id,
                player_team_id=int(player_team_id),
                opponent_team_id=int(opponent_team_id),
                opponent_abbr=opponent_abbr,
                game_date=game_date,
                is_home=is_home
            )
            
            all_predictions[player_id] = {
                'predictions': predictions,
                'player_name': player_name,
                'opponent_abbr': opponent_abbr,
                'is_home': is_home,
                'team_abbr': home_team_abbr if is_home else away_team_abbr
            }
        except Exception as e:
            # Log error but continue with other players
            print(f"Error generating predictions for {player_name}: {e}")
            continue
    
    return all_predictions


def calculate_edge(prediction: float, line: float) -> Tuple[float, float, str]:
    """
    Calculate edge between prediction and line.
    
    Returns:
        Tuple of (edge_value, edge_pct, lean)
    """
    if line == 0:
        return 0.0, 0.0, "N/A"
    
    edge = round(prediction - line, 1)
    edge_pct = round((edge / line) * 100, 1)
    
    if edge >= 1.5:
        lean = "Strong Over"
    elif edge >= 0.5:
        lean = "Lean Over"
    elif edge <= -1.5:
        lean = "Strong Under"
    elif edge <= -0.5:
        lean = "Lean Under"
    else:
        lean = "Push"
    
    return edge, edge_pct, lean


def find_best_value_plays(
    all_predictions: Dict[str, Dict],
    all_props: Dict[str, Dict],
    min_edge_pct: float = 0.0,
    confidence_filter: List[str] = None,
    stat_filter: List[str] = None
) -> List[Dict]:
    """
    Find best value plays by comparing predictions to props.
    
    Args:
        all_predictions: Dict from generate_predictions_for_game()
        all_props: Dict from fetch_all_props_for_game() (player_name_lower -> stat -> PropLine)
        min_edge_pct: Minimum absolute edge % to include
        confidence_filter: List of confidence levels to include (e.g., ['high', 'medium'])
        stat_filter: List of stats to include (e.g., ['PTS', 'REB', 'AST'])
    
    Returns:
        List of play dicts sorted by absolute edge %
    """
    if confidence_filter is None:
        confidence_filter = ['high', 'medium', 'low']
    
    if stat_filter is None:
        stat_filter = ['PTS', 'REB', 'AST', 'PRA', 'RA', 'STL', 'BLK', 'FG3M', 'FTM', 'FPTS']
    
    plays = []
    
    for player_id, player_data in all_predictions.items():
        predictions = player_data.get('predictions', {})
        player_name = player_data.get('player_name', '')
        team_abbr = player_data.get('team_abbr', '')
        opponent_abbr = player_data.get('opponent_abbr', '')
        is_home = player_data.get('is_home', True)
        
        # Find matching props for this player
        player_name_lower = player_name.lower().strip()
        player_props = None
        
        # Try to find props with fuzzy matching
        for prop_name, props in all_props.items():
            # Check if names match
            if _names_match(prop_name, player_name_lower):
                player_props = props
                break
        
        if not player_props:
            continue
        
        for stat in stat_filter:
            if stat not in predictions or stat not in player_props:
                continue
            
            pred = predictions[stat]
            prop = player_props[stat]
            
            # Apply confidence filter
            if pred.confidence not in confidence_filter:
                continue
            
            edge, edge_pct, lean = calculate_edge(pred.value, prop.line)
            
            # Apply minimum edge filter
            if abs(edge_pct) < min_edge_pct:
                continue
            
            plays.append({
                'player_id': player_id,
                'player_name': player_name,
                'team': team_abbr,
                'opponent': opponent_abbr,
                'location': 'Home' if is_home else 'Away',
                'stat': stat,
                'prediction': pred.value,
                'line': prop.line,
                'edge': edge,
                'edge_pct': edge_pct,
                'lean': lean,
                'confidence': pred.confidence,
                'over_odds': getattr(prop, 'over_odds', -110),
                'under_odds': getattr(prop, 'under_odds', -110),
            })
    
    # Sort by absolute edge percentage (descending)
    plays.sort(key=lambda x: abs(x['edge_pct']), reverse=True)
    
    return plays


def _names_match(name1: str, name2: str) -> bool:
    """Check if two player names match (fuzzy matching)."""
    if not name1 or not name2:
        return False
    
    name1 = name1.lower().strip()
    name2 = name2.lower().strip()
    
    # Exact match
    if name1 == name2:
        return True
    
    # One contains the other
    if name1 in name2 or name2 in name1:
        return True
    
    # Check if major parts match
    parts1 = set(name1.replace(',', '').split())
    parts2 = set(name2.replace(',', '').split())
    
    if len(parts1 & parts2) >= 2:
        return True
    
    return False

