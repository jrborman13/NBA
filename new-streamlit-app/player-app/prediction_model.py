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
        
        # Cap hot player effect: weighted average cannot exceed season average by more than 15%
        if season_avg > 0 and weighted_avg > season_avg * 1.15:
            weighted_avg = season_avg * 1.15
        
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
        
        # Apply regression factor to reduce over-prediction bias
        # This accounts for natural regression to the mean
        regression_factor = 0.96  # 4% reduction to account for natural regression
        base_prediction *= regression_factor
        
        # 5. Apply adjustments
        adjusted_prediction = base_prediction
        
        # Opponent defensive adjustment
        opp_stats = player_features.get('opponent', {})
        league_avg = player_features.get('league_avg', {})
        
        opp_def_rating = opp_stats.get('def_rating', 110.0)
        league_def_rating = league_avg.get('def_rating', 110.0)
        
        if stat in ['PTS', 'PRA']:  # Only adjust scoring stats
            def_adjustment = opp_def_rating / league_def_rating
            # Cap defensive adjustments at ±10% to prevent extreme swings
            def_adjustment = max(0.90, min(1.10, def_adjustment))
            adjusted_prediction *= def_adjustment
            factors['defense'] = f"Opp DEF RTG {opp_def_rating} vs league avg {league_def_rating}"
        
        # Matchup-specific adjustment (PTS_PAINT, PTS_FB, PTS_2ND_CHANCE)
        matchup_data = player_features.get('matchup', {})
        matchup_adjustments = matchup_data.get('matchup_adjustments', {})
        
        # Check if player is a 3-point specialist (for stronger matchup adjustments)
        season_fg3m_check = rolling_avgs.get('Season', {}).get('FG3M', 0.0)
        season_ppg_check = rolling_avgs.get('Season', {}).get('PTS', 0.0)
        pts_from_3s_check = season_fg3m_check * 3.0
        pct_pts_from_3s_check = (pts_from_3s_check / season_ppg_check * 100) if season_ppg_check > 0 else 0.0
        is_3pt_specialist_check = pct_pts_from_3s_check >= 50.0
        
        if stat == 'PTS':
            # Apply overall matchup factor for points
            overall_factor = matchup_adjustments.get('overall_pts_factor', 1.0)
            if overall_factor != 1.0:
                # 3-point specialists get stronger matchup adjustments (40% vs 30%)
                # They're more matchup-dependent - weak 3PT defense = huge games
                matchup_weight = 0.40 if is_3pt_specialist_check else 0.30
                raw_matchup_adjustment = 1.0 + matchup_weight * (overall_factor - 1.0)
                
                # Cap matchup adjustment - higher for 3-point specialists
                if is_3pt_specialist_check:
                    max_matchup_adj = 1.20  # Allow up to 20% boost for 3PT specialists
                    min_matchup_adj = 0.80  # Allow down to 20% reduction
                else:
                    max_matchup_adj = 1.15  # Standard 15% cap
                    min_matchup_adj = 0.85
                
                if raw_matchup_adjustment > max_matchup_adj:
                    matchup_adjustment = max_matchup_adj
                elif raw_matchup_adjustment < min_matchup_adj:
                    matchup_adjustment = min_matchup_adj
                else:
                    matchup_adjustment = raw_matchup_adjustment
                
                adjusted_prediction *= matchup_adjustment
                
                player_breakdown = matchup_data.get('player_scoring_breakdown', {})
                opp_vuln = matchup_data.get('opponent_vulnerabilities', {})
                
                if matchup_adjustment > 1.0:
                    factors['matchup'] = (
                        f"Favorable matchup (+{round((matchup_adjustment-1)*100, 1)}%): "
                        f"Paint {player_breakdown.get('pts_paint', 0)} vs opp allows {opp_vuln.get('opp_pts_paint_allowed', 0)}"
                    )
                else:
                    factors['matchup'] = (
                        f"Tough matchup ({round((matchup_adjustment-1)*100, 1)}%): "
                        f"Paint {player_breakdown.get('pts_paint', 0)} vs opp allows {opp_vuln.get('opp_pts_paint_allowed', 0)}"
                    )
        
        # Synergy playtype adjustments
        synergy_data = player_features.get('synergy', {})
        stat_adjustments = synergy_data.get('stat_adjustments', {})
        
        if stat_adjustments:
            # Apply synergy adjustments for relevant stats
            synergy_weight = 0.25  # Weight synergy adjustments at 25% (similar to matchup weight)
            
            if stat == 'PTS' and 'PTS' in stat_adjustments:
                synergy_factor = stat_adjustments['PTS']
                # Cap synergy adjustment similar to matchup caps
                synergy_factor = max(0.85, min(1.15, synergy_factor))
                # Apply weighted adjustment
                synergy_adjustment = 1.0 + synergy_weight * (synergy_factor - 1.0)
                adjusted_prediction *= synergy_adjustment
                factors['synergy'] = f"Playtype matchup: {round((synergy_factor-1)*100, 1)}% (weighted {round((synergy_adjustment-1)*100, 1)}%)"
            
            elif stat == 'AST' and 'AST' in stat_adjustments:
                synergy_factor = stat_adjustments['AST']
                synergy_factor = max(0.85, min(1.15, synergy_factor))
                synergy_adjustment = 1.0 + synergy_weight * (synergy_factor - 1.0)
                adjusted_prediction *= synergy_adjustment
                factors['synergy'] = f"Playtype matchup: {round((synergy_factor-1)*100, 1)}% (weighted {round((synergy_adjustment-1)*100, 1)}%)"
            
            elif stat == 'REB' and 'REB' in stat_adjustments:
                synergy_factor = stat_adjustments['REB']
                synergy_factor = max(0.90, min(1.10, synergy_factor))  # Smaller cap for rebounds
                synergy_adjustment = 1.0 + synergy_weight * (synergy_factor - 1.0)
                adjusted_prediction *= synergy_adjustment
                factors['synergy'] = f"Playtype matchup: {round((synergy_factor-1)*100, 1)}% (weighted {round((synergy_adjustment-1)*100, 1)}%)"
            
            elif stat == 'FG3M' and 'FG3M' in stat_adjustments:
                synergy_factor = stat_adjustments['FG3M']
                synergy_factor = max(0.80, min(1.20, synergy_factor))  # Larger cap for 3PM (more variable)
                synergy_adjustment = 1.0 + synergy_weight * (synergy_factor - 1.0)
                adjusted_prediction *= synergy_adjustment
                factors['synergy'] = f"Playtype matchup: {round((synergy_factor-1)*100, 1)}% (weighted {round((synergy_adjustment-1)*100, 1)}%)"
        
        # FT Rate adjustment for FTM predictions (with drives integration)
        # FT Rate = FTA / FGA (how often a player/team gets to the line per field goal attempt)
        if stat == 'FTM':
            # Get opponent's FT Rate allowed (from team_defensive_stats)
            opp_ft_rate_allowed = opp_stats.get('ft_rate_allowed', 25.0)
            league_avg_ft_rate = player_features.get('league_avg_ft_rate', 25.0)
            player_ft_rate = player_features.get('player_ft_rate', 25.0)
            
            # Get drives data for FTM adjustment
            drives_adj = player_features.get('drives_adjustments', {})
            drives_data = player_features.get('drives', {})
            ftm_drive_factor = drives_adj.get('ftm_drive_factor', 1.0)
            drive_description = drives_adj.get('drive_description', 'Average driver')
            drives_vs_league = drives_adj.get('drives_vs_league', 1.0)
            drive_fta_pg = drives_data.get('drive_fta', 1.0)
            drive_tier = drives_adj.get('drive_tier', 'average')
            
            # 1. Opponent FT Rate adjustment
            # If opponent allows higher FT Rate than league avg, player will get more FTM
            opp_ft_rate_factor = opp_ft_rate_allowed / league_avg_ft_rate if league_avg_ft_rate > 0 else 1.0
            
            # 2. Player's own tendency to get to the line
            player_ft_rate_factor = player_ft_rate / league_avg_ft_rate if league_avg_ft_rate > 0 else 1.0
            
            # 3. Drives factor - weighting based on how player gets to the line
            # High drivers: opponent FT Rate matters more (they attack the paint)
            # Low drivers: their FTM is less predictable, reduce overall adjustment
            if drive_tier in ['elite', 'high']:
                # High driver - opponent FT Rate matters more
                opp_weight = 0.70
                player_weight = 0.30
            elif drive_tier == 'average':
                # Normal - balanced weighting
                opp_weight = 0.60
                player_weight = 0.40
            elif drive_tier == 'low':
                # Low driver - reduce overall FT rate influence
                opp_weight = 0.55
                player_weight = 0.45
            else:  # very_low
                # Non-driver (stretch bigs, shooters) - FTs come from different sources
                # These players' FTM is highly variable, weight toward baseline more
                opp_weight = 0.50
                player_weight = 0.50
            
            combined_ft_factor = opp_weight * opp_ft_rate_factor + player_weight * player_ft_rate_factor
            
            # Apply adjustment (moderate impact - scale to ~0.85 to 1.15 range)
            # Then apply drives factor (reduces for low drivers, amplifies for high)
            ft_adjustment = 0.70 + 0.30 * combined_ft_factor
            ft_adjustment *= ftm_drive_factor  # Reduce for non-drivers, amplify for elite drivers
            adjusted_prediction *= ft_adjustment
            
            opp_ft_rate_rank = opp_stats.get('ft_rate_allowed_rank', 15)
            rank_description = "gives up FTs" if opp_ft_rate_rank <= 10 else ("avg" if opp_ft_rate_rank <= 20 else "limits FTs")
            factors['ft_rate'] = f"Opp FT Rate: {opp_ft_rate_allowed}% (Rank {opp_ft_rate_rank}, {rank_description})"
            factors['drives_ftm'] = f"{drive_description} ({drives_vs_league:.1f}x league avg drives, {drive_fta_pg:.1f} drive FTA/g)"
        
        # AST adjustment based on drives (drive-and-kick playmaking)
        if stat == 'AST':
            drives_adj = player_features.get('drives_adjustments', {})
            ast_drive_factor = drives_adj.get('ast_drive_factor', 1.0)
            ast_description = drives_adj.get('ast_description', 'Average')
            drive_ast_vs_league = drives_adj.get('drive_ast_vs_league', 1.0)
            
            if ast_drive_factor != 1.0:
                adjusted_prediction *= ast_drive_factor
                factors['drives_ast'] = f"{ast_description} ({drive_ast_vs_league:.1f}x league avg drive AST)"
        
        # Pace adjustment
        opp_pace = opp_stats.get('pace', 100.0)
        league_pace = league_avg.get('pace', 100.0)
        
        pace_adjustment = opp_pace / league_pace
        adjusted_prediction *= pace_adjustment
        factors['pace'] = f"Opp PACE {opp_pace} vs league avg {league_pace}"
        
        # Positional defense adjustment (DISABLED - was causing double-counting)
        # Keeping the code for potential future use with actual position-specific API data
        # if stat in ['PTS', 'PRA']:
        #     pos_defense = player_features.get('positional_defense', {})
        #     pos_factor = pos_defense.get('factor', 1.0)
        #     # ... adjustment logic ...
        
        # Similar players vs opponent adjustment
        # Apply this adjustment with moderate weight (10-20% influence)
        # More weight when player has few games vs opponent themselves
        similar_players_data = player_features.get('similar_players', {})
        vs_opp_games = vs_opp.get('games_played', 0)
        
        if similar_players_data.get('confidence') != 'low' and similar_players_data.get('sample_size', 0) > 0:
            # REDUCED base weights for more conservative similar players adjustments
            base_weight = 0.0
            if vs_opp_games == 0:
                # No games vs opponent - use similar players moderately (15% instead of 20%)
                base_weight = 0.15
            elif vs_opp_games == 1:
                # Only 1 game - use similar players lightly (10% instead of 15%)
                base_weight = 0.10
            else:
                # 2+ games - use similar players very lightly (5% instead of 10%)
                base_weight = 0.05
            
            # Reduce weight further if confidence is medium (indicates low-minute similar players)
            confidence = similar_players_data.get('confidence', 'low')
            if confidence == 'medium':
                similar_weight = base_weight * 0.7  # Reduce by 30%
            elif confidence == 'low':
                similar_weight = base_weight * 0.5  # Reduce by 50%
            else:
                similar_weight = base_weight
            
            # Apply adjustment based on stat with CAPS
            if stat == 'PTS':
                sim_adjustment_factor = similar_players_data.get('pts_adjustment_factor', 1.0)
                if sim_adjustment_factor != 1.0:
                    # Cap the raw adjustment factor at ±12% before applying weight (reduced from ±20%)
                    capped_sim_factor = max(0.88, min(1.12, sim_adjustment_factor))
                    
                    # Blend: (1 - weight) * current + weight * similar_players_adjustment
                    similar_adjustment = 1.0 + similar_weight * (capped_sim_factor - 1.0)
                    adjusted_prediction *= similar_adjustment
                    
                    sample_size = similar_players_data.get('sample_size', 0)
                    confidence = similar_players_data.get('confidence', 'low')
                    factors['similar_players'] = (
                        f"Similar players vs opponent: {round((capped_sim_factor-1)*100, 1)}% "
                        f"({sample_size} players, {confidence} confidence)"
                    )
            elif stat == 'REB':
                sim_adjustment_factor = similar_players_data.get('reb_adjustment_factor', 1.0)
                if sim_adjustment_factor != 1.0:
                    # Cap at ±12% (reduced from ±20%)
                    capped_sim_factor = max(0.88, min(1.12, sim_adjustment_factor))
                    similar_adjustment = 1.0 + similar_weight * (capped_sim_factor - 1.0)
                    adjusted_prediction *= similar_adjustment
                    
                    sample_size = similar_players_data.get('sample_size', 0)
                    confidence = similar_players_data.get('confidence', 'low')
                    factors['similar_players'] = (
                        f"Similar players vs opponent: {round((capped_sim_factor-1)*100, 1)}% "
                        f"({sample_size} players, {confidence} confidence)"
                    )
            elif stat == 'AST':
                sim_adjustment_factor = similar_players_data.get('ast_adjustment_factor', 1.0)
                if sim_adjustment_factor != 1.0:
                    # Cap at ±12% (reduced from ±20%)
                    capped_sim_factor = max(0.88, min(1.12, sim_adjustment_factor))
                    similar_adjustment = 1.0 + similar_weight * (capped_sim_factor - 1.0)
                    adjusted_prediction *= similar_adjustment
                    
                    sample_size = similar_players_data.get('sample_size', 0)
                    confidence = similar_players_data.get('confidence', 'low')
                    factors['similar_players'] = (
                        f"Similar players vs opponent: {round((capped_sim_factor-1)*100, 1)}% "
                        f"({sample_size} players, {confidence} confidence)"
                    )
            
            # Defensive game-planning adjustment (based on similar players)
            # If similar players consistently struggle vs this opponent, opponent may game-plan
            if stat == 'PTS' and similar_players_data.get('confidence') in ['high', 'medium']:
                sim_sample_size = similar_players_data.get('sample_size', 0)
                if sim_sample_size >= 3:  # Need meaningful sample
                    pts_adjustment = similar_players_data.get('pts_adjustment_factor', 1.0)
                    
                    # If similar players perform significantly worse vs opponent (< 0.85x), 
                    # opponent may be game-planning against this player type
                    if pts_adjustment < 0.85:
                        # Apply defensive game-planning penalty
                        # More penalty if sample is larger and adjustment is more negative
                        gameplan_penalty = min(0.08, (0.85 - pts_adjustment) * 0.3)  # Max 8% penalty
                        gameplan_factor = 1.0 - gameplan_penalty
                        adjusted_prediction *= gameplan_factor
                        
                        factors['defensive_gameplan'] = (
                            f"Opponent game-planning vs similar players: "
                            f"-{round(gameplan_penalty*100, 1)}% "
                            f"(similar players avg {round((pts_adjustment-1)*100, 1)}% vs opponent)"
                        )
        
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
        # Cap location_factor to prevent extreme home/away swings
        if location_avg > 0 and season_avg > 0:
            location_factor = location_avg / season_avg
            # Cap location_factor at ±16.7% to limit final adjustment to ±5%
            # Formula: adjustment = 0.7 + 0.3 * location_factor
            # For ±5% cap: location_factor between 0.833 and 1.167
            location_factor = max(0.833, min(1.167, location_factor))
            adjusted_prediction *= (0.7 + 0.3 * location_factor)
        
        # Minutes scaling adjustment (if projected_minutes provided)
        projected_minutes = player_features.get('projected_minutes')
        avg_minutes = rolling_avgs.get('Season', {}).get('MIN', 0.0)
        
        # Fatigue factor - reduce predictions for players with high recent minutes
        # This accounts for cumulative fatigue, not just rest days
        # Calculate this BEFORE minutes scaling so we use season average
        # Ultra-elite players are exempt - they can handle high minutes without fatigue penalty
        recent_minutes = rolling_avgs.get('L5', {}).get('MIN', avg_minutes if avg_minutes > 0 else 25.0)
        season_ppg_for_fatigue = player_features.get('season_ppg', rolling_avgs.get('Season', {}).get('PTS', 0.0))
        if season_ppg_for_fatigue == 0:
            season_ppg_for_fatigue = rolling_avgs.get('Season', {}).get('PTS', 0.0)
        
        # Only apply fatigue penalty to non-ultra-elite players
        if season_ppg_for_fatigue < 27 and avg_minutes > 0 and recent_minutes > avg_minutes * 1.15:  # Playing 15%+ more than season avg
            # High recent minutes = fatigue penalty
            minutes_over_avg = recent_minutes - avg_minutes
            fatigue_penalty = min(0.05, minutes_over_avg / 100.0)  # Max 5% penalty
            fatigue_factor = 1.0 - fatigue_penalty
            adjusted_prediction *= fatigue_factor
            
            if fatigue_factor < 1.0:
                factors['fatigue'] = f"High recent minutes ({recent_minutes:.1f} vs {avg_minutes:.1f} avg): -{round(fatigue_penalty*100, 1)}%"
        
        if projected_minutes is not None and avg_minutes > 0 and projected_minutes != avg_minutes:
            minutes_ratio = projected_minutes / avg_minutes
            
            # Most stats scale linearly with minutes
            if stat in ['PTS', 'REB', 'AST', 'STL', 'BLK']:
                adjusted_prediction *= minutes_ratio
            # Shooting stats scale slightly less (usage may not increase proportionally)
            elif stat in ['FG3M', 'FTM']:
                adjusted_prediction *= (1 + 0.9 * (minutes_ratio - 1))
            # TOV scales slightly more (more minutes = more touches = more turnovers)
            elif stat == 'TOV':
                adjusted_prediction *= (1 + 1.1 * (minutes_ratio - 1))
            else:
                adjusted_prediction *= minutes_ratio
            
            factors['minutes_scaling'] = (
                f"Scaled from {avg_minutes:.1f} to {projected_minutes:.1f} MPG "
                f"({round((minutes_ratio - 1) * 100, 1):+.1f}%)"
            )
        
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
        
        # Star regression adjustment (POSITION-SPECIFIC)
        # Ultra-elite (27+ PPG): No regression - consistently dominant (Giannis, etc.)
        # Bigs (C) are more predictable - apply regression to reduce over-prediction
        # Guards (PG/SG) have higher variance/ceiling games - no regression needed
        if stat in ['PTS', 'PRA']:
            # Use SEASON average for tier determination (more stable than rolling)
            season_ppg = player_features.get('season_ppg', rolling_avgs.get('Season', {}).get('PTS', 0.0))
            if season_ppg == 0:
                season_ppg = rolling_avgs.get('Season', {}).get('PTS', 0.0)
            player_position = player_features.get('player_position', 'F')
            
            # ULTRA-ELITE TIER: 27+ PPG players get NO regression
            # These players consistently dominate and regression hurts accuracy
            if season_ppg >= 27:
                factors['star_regression'] = f"Ultra-elite ({season_ppg:.1f} season PPG) - no regression (consistently dominant)"
                factors['regression_tier'] = 'Ultra-elite'
            else:
                # Determine position group
                position_upper = player_position.upper() if player_position else 'F'
                is_guard = any(pos in position_upper for pos in ['G', 'PG', 'SG'])
                is_center = 'C' in position_upper and 'SG' not in position_upper
                is_forward = any(pos in position_upper for pos in ['F', 'PF', 'SF']) and not is_center
                
                # Position-specific regression factors
                # Guards: No regression (they have higher variance, ceiling games)
                # Forwards: Moderate regression
                # Centers: Full regression (most predictable)
                if is_guard:
                    position_regression_mult = 0.0  # No regression for guards
                    position_label = "Guard"
                elif is_center:
                    position_regression_mult = 1.0  # Full regression for centers
                    position_label = "Center"
                else:
                    position_regression_mult = 0.5  # Half regression for forwards
                    position_label = "Forward"
                
                # Base regression by PPG tier (using season_ppg)
                if season_ppg >= 25:
                    base_regression = 0.06  # 6% base
                    tier_label = "Elite scorer"
                elif season_ppg >= 20:
                    base_regression = 0.04  # 4% base
                    tier_label = "Star"
                elif season_ppg >= 15:
                    base_regression = 0.02  # 2% base
                    tier_label = "Starter"
                else:
                    base_regression = 0.0
                    tier_label = "Role player"
                
                # Apply position-specific regression
                actual_regression = base_regression * position_regression_mult
                star_factor = 1.0 - actual_regression
                
                if actual_regression > 0:
                    factors['star_regression'] = f"{tier_label} {position_label} ({season_ppg:.1f} season PPG) - adjustment (-{actual_regression*100:.1f}%)"
                    factors['regression_tier'] = tier_label
                    adjusted_prediction *= star_factor
                elif season_ppg >= 15 and is_guard:
                    factors['star_regression'] = f"{tier_label} Guard ({season_ppg:.1f} season PPG) - no regression (high variance position)"
                    factors['regression_tier'] = f"{tier_label} (Guard)"
                else:
                    factors['regression_tier'] = tier_label
        
        # Cap total combined adjustments to prevent extreme predictions
        # Ultra-elite players (27+ PPG) and 3-point specialists get higher cap to allow for variance/ceiling games
        # Other players get standard cap to prevent over-prediction
        season_ppg = player_features.get('season_ppg', rolling_avgs.get('Season', {}).get('PTS', 0.0))
        if season_ppg == 0:
            season_ppg = rolling_avgs.get('Season', {}).get('PTS', 0.0)
        
        # Identify 3-point specialists (players who get 50%+ of points from 3s)
        # 3-point specialists have inherently high variance - their production depends heavily on shot-making
        season_fg3m = rolling_avgs.get('Season', {}).get('FG3M', 0.0)
        pts_from_3s = season_fg3m * 3.0  # Each 3-pointer = 3 points
        pct_pts_from_3s = (pts_from_3s / season_ppg * 100) if season_ppg > 0 else 0.0
        is_3pt_specialist = pct_pts_from_3s >= 50.0  # 50%+ of points from 3s
        
        if season_ppg >= 27:  # Ultra-elite players
            # Higher cap for ultra-elite players who can have huge variance games
            max_total_multiplier = 1.40  # Allow up to 40% boost
            min_total_multiplier = 0.70  # Allow down to 30% reduction
        elif is_3pt_specialist:  # 3-point specialists (high variance)
            # Higher cap for 3-point specialists who can have huge variance games
            # They can go 0-10 from 3 (2 points) or 7-10 from 3 (23 points) - need variance allowance
            max_total_multiplier = 1.35  # Allow up to 35% boost
            min_total_multiplier = 0.70  # Allow down to 30% reduction
        else:
            # Standard cap for other players
            max_total_multiplier = 1.25  # Max 25% boost
            min_total_multiplier = 0.75  # Max 25% reduction
        
        if adjusted_prediction > base_prediction * max_total_multiplier:
            adjusted_prediction = base_prediction * max_total_multiplier
            cap_pct = round((max_total_multiplier - 1) * 100)
            if is_3pt_specialist:
                factors['capped'] = f"Total adjustments capped at +{cap_pct}% (3PT specialist - high variance)"
            else:
                factors['capped'] = f"Total adjustments capped at +{cap_pct}%"
        elif adjusted_prediction < base_prediction * min_total_multiplier:
            adjusted_prediction = base_prediction * min_total_multiplier
            cap_pct = round((1 - min_total_multiplier) * 100)
            if is_3pt_specialist:
                factors['capped'] = f"Total adjustments capped at -{cap_pct}% (3PT specialist - high variance)"
            else:
                factors['capped'] = f"Total adjustments capped at -{cap_pct}%"
        
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
        import time
        predict_start = time.time()
        
        # Predict individual stats first (including TOV for fantasy calculation)
        stats_to_predict = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M', 'FTM', 'TOV']
        
        predictions = {}
        stat_times = {}
        for stat in stats_to_predict:
            stat_start = time.time()
            predictions[stat] = self.predict_stat(stat, player_features)
            stat_times[stat] = time.time() - stat_start
        
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
        
        predict_total_time = time.time() - predict_start
        
        return predictions


def generate_prediction(
    player_id: str,
    player_team_id: int,
    opponent_team_id: int,
    opponent_abbr: str,
    game_date: str,
    is_home: bool,
    bulk_game_logs: pd.DataFrame = None,
    bulk_advanced_stats: pd.DataFrame = None,
    bulk_drives_stats: pd.DataFrame = None,
    bulk_offensive_synergy: Dict[str, pd.DataFrame] = None,
    use_similar_players: bool = False,
    projected_minutes: Optional[float] = None
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
        bulk_game_logs: Optional pre-fetched bulk game logs (for batch processing)
        bulk_advanced_stats: Optional pre-fetched bulk advanced stats (for batch processing)
        bulk_drives_stats: Optional pre-fetched bulk drives stats (for batch processing)
        bulk_offensive_synergy: Optional pre-fetched bulk offensive synergy data (for batch processing)
    
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
        is_home=is_home,
        bulk_game_logs=bulk_game_logs,
        bulk_advanced_stats=bulk_advanced_stats,
        bulk_drives_stats=bulk_drives_stats,
        bulk_offensive_synergy=bulk_offensive_synergy,
        use_similar_players=use_similar_players
    )
    
    # Store player_id and projected_minutes in features for use in prediction
    player_features['player_id'] = player_id
    if projected_minutes is not None:
        player_features['projected_minutes'] = projected_minutes
    
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
        # Use None instead of 'N/A' to avoid Arrow serialization issues
        season_avg = pred.breakdown.get('season_avg')
        l5_avg = pred.breakdown.get('L5_avg')
        vs_opp = pred.breakdown.get('vs_opponent')
        
        rows.append({
            'Stat': stat,
            'Prediction': pred.value,
            'Confidence': pred.confidence.capitalize(),
            'Season Avg': round(season_avg, 1) if season_avg is not None else None,
            'L5 Avg': round(l5_avg, 1) if l5_avg is not None else None,
            'vs Opp': round(vs_opp, 1) if vs_opp is not None else None,
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
    import time
    all_predictions = {}
    total = len(player_ids)
    
    # Track total time
    total_start_time = time.time()
    
    # OPTIMIZATION: Fetch ALL bulk data in a few API calls upfront
    # This replaces 100+ individual API calls with just a handful of bulk calls
    
    bulk_game_logs = features.get_bulk_player_game_logs()
    bulk_game_logs_time = time.time() - bulk_fetch_start
    
    bulk_advanced_start = time.time()
    bulk_advanced_stats = features.get_bulk_player_advanced_stats()
    bulk_advanced_time = time.time() - bulk_advanced_start
    
    # Import drives_stats module for bulk drives data
    import drives_stats as ds
    bulk_drives_start = time.time()
    bulk_drives_stats = ds.get_all_player_drives_stats()
    bulk_drives_time = time.time() - bulk_drives_start
    
    # Fetch bulk offensive synergy data (11 API calls total for all players, all playtypes)
    bulk_synergy_start = time.time()
    bulk_offensive_synergy = features.get_cached_bulk_offensive_synergy()
    bulk_synergy_time = time.time() - bulk_synergy_start
    
    bulk_fetch_total = time.time() - bulk_fetch_start
    
    # Track per-player timing
    player_times = []
    
    for idx, player_id in enumerate(player_ids):
        player_start_time = time.time()
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
            # Generate predictions for this player using bulk data
            # Skip similar players for batch predictions (too slow)
            predictions = generate_prediction(
                player_id=player_id,
                player_team_id=int(player_team_id),
                opponent_team_id=int(opponent_team_id),
                opponent_abbr=opponent_abbr,
                game_date=game_date,
                is_home=is_home,
                bulk_game_logs=bulk_game_logs,
                bulk_advanced_stats=bulk_advanced_stats,
                bulk_drives_stats=bulk_drives_stats,
                bulk_offensive_synergy=bulk_offensive_synergy,
                use_similar_players=False  # Skip for batch to improve performance
            )
            pred_time = time.time() - pred_start
            player_total_time = time.time() - player_start_time
            
            player_times.append(player_total_time)
            
            all_predictions[player_id] = {
                'predictions': predictions,
                'player_name': player_name,
                'opponent_abbr': opponent_abbr,
                'is_home': is_home,
                'team_abbr': home_team_abbr if is_home else away_team_abbr
            }
        except Exception as e:
            # Log error but continue with other players
            player_total_time = time.time() - player_start_time
            print(f"Error generating predictions for {player_name}: {e}")
            continue
    
    total_time = time.time() - total_start_time
    avg_player_time = sum(player_times) / len(player_times) if player_times else 0
    
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
    stat_filter: List[str] = None,
    injury_adjustments_map: Dict[str, Dict] = None
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
        
        # OPTIMIZATION: Pre-calculate all injury-adjusted component values once per player
        # This eliminates redundant calculations in the stat loop
        import injury_adjustments as inj
        adjusted_components = {}
        
        if injury_adjustments_map and player_id in injury_adjustments_map:
            injury_adj = injury_adjustments_map[player_id]
            # Pre-calculate adjusted values for all component stats (including FG3M and FTM)
            for component_stat in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM']:
                if component_stat in predictions:
                    if component_stat in injury_adj:
                        adjusted_components[component_stat] = inj.apply_injury_adjustments(
                            predictions[component_stat].value, component_stat, injury_adj
                        )
                    else:
                        adjusted_components[component_stat] = predictions[component_stat].value
        else:
            # No injury adjustments, use base prediction values
            for component_stat in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'FG3M', 'FTM']:
                if component_stat in predictions:
                    adjusted_components[component_stat] = predictions[component_stat].value
        
        for stat in stat_filter:
            if stat not in predictions or stat not in player_props:
                continue
            
            pred = predictions[stat]
            prop = player_props[stat]
            
            # Apply confidence filter
            if pred.confidence not in confidence_filter:
                continue
            
            # Apply injury adjustments using pre-calculated values
            prediction_value = pred.value
            
            # For composite stats, calculate from pre-calculated adjusted components
            if stat == 'PRA':
                # PRA = PTS + REB + AST
                if all(s in adjusted_components for s in ['PTS', 'REB', 'AST']):
                    prediction_value = adjusted_components['PTS'] + adjusted_components['REB'] + adjusted_components['AST']
            elif stat == 'RA':
                # RA = REB + AST
                if all(s in adjusted_components for s in ['REB', 'AST']):
                    prediction_value = adjusted_components['REB'] + adjusted_components['AST']
            elif stat == 'FPTS':
                # FPTS = PTS*1 + REB*1.2 + AST*1.5 + STL*3 + BLK*3 - TOV*1
                if all(s in adjusted_components for s in ['PTS', 'REB', 'AST', 'STL', 'BLK', 'TOV']):
                    prediction_value = (
                        adjusted_components['PTS'] * 1.0 +
                        adjusted_components['REB'] * 1.2 +
                        adjusted_components['AST'] * 1.5 +
                        adjusted_components['STL'] * 3.0 +
                        adjusted_components['BLK'] * 3.0 -
                        adjusted_components['TOV'] * 1.0
                    )
            elif stat in adjusted_components:
                # For individual component stats, use pre-calculated adjusted value
                prediction_value = adjusted_components[stat]
            elif injury_adjustments_map and player_id in injury_adjustments_map:
                # For other stats that aren't in adjusted_components,
                # apply injury adjustments if available
                injury_adj = injury_adjustments_map[player_id]
                if stat in injury_adj:
                    prediction_value = inj.apply_injury_adjustments(
                        pred.value, stat, injury_adj
                    )
            
            edge, edge_pct, lean = calculate_edge(prediction_value, prop.line)
            
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
                'prediction': prediction_value,  # Use injury-adjusted value
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
    
    # Debug: Check for systematic bias
    if len(plays) > 0:
        over_count = sum(1 for p in plays if 'Over' in p['lean'])
        under_count = sum(1 for p in plays if 'Under' in p['lean'])
        avg_edge = sum(p['edge'] for p in plays) / len(plays)
        
        # Log bias info (can be checked in console)
        if abs(avg_edge) > 1.0:
            print(f"⚠️ Systematic bias detected: Average edge = {avg_edge:.2f} ({over_count} Over, {under_count} Under)")
    
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

