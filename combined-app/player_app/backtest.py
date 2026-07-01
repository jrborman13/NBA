"""
Backtest Module
Test prediction model against historical game results.
"""

import pandas as pd
import numpy as np
import streamlit as st
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import nba_api.stats.endpoints as endpoints

# Import prediction modules
import prediction_model as pm
import prediction_features as pf


# Constants
CURRENT_SEASON = "2025-26"
STATS_TO_BACKTEST = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M', 'FTM', 'TOV']

# Player Type Thresholds
ULTRA_ELITE_PPG_THRESHOLD = 27.0  # Matches regression tier
STAR_PPG_THRESHOLD = 18.0
STARTER_PPG_MIN = 12.0
STARTER_MIN_THRESHOLD = 25.0
STAR_MIN_THRESHOLD = 32.0


def categorize_player(ppg: float, mpg: float) -> str:
    """
    Categorize player based on PPG and MPG.
    
    Categories:
    - Ultra-elite: PPG >= 27 (matches regression tier)
    - Star: PPG > 18 OR Minutes >= 32
    - Starter: 12 <= PPG <= 18 AND Minutes >= 25
    - Role Player: PPG < 12 OR Minutes < 25
    """
    if ppg >= ULTRA_ELITE_PPG_THRESHOLD:
        return "Ultra-elite"
    elif ppg > STAR_PPG_THRESHOLD or mpg >= STAR_MIN_THRESHOLD:
        return "Star"
    elif ppg >= STARTER_PPG_MIN and mpg >= STARTER_MIN_THRESHOLD:
        return "Starter"
    else:
        return "Role Player"


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_season_averages(player_id: str, season: str = CURRENT_SEASON) -> Dict:
    """
    Get player's season averages (PPG, MPG) for categorization.
    """
    try:
        stats = endpoints.PlayerCareerStats(
            player_id=player_id,
            per_mode36='PerGame'
        ).get_data_frames()[0]
        
        # Get current season stats
        current = stats[stats['SEASON_ID'] == season]
        if len(current) > 0:
            return {
                'ppg': current['PTS'].iloc[0],
                'mpg': current['MIN'].iloc[0]
            }
        
        # Fallback to most recent season
        if len(stats) > 0:
            return {
                'ppg': stats['PTS'].iloc[-1],
                'mpg': stats['MIN'].iloc[-1]
            }
        
        return {'ppg': 0.0, 'mpg': 0.0}
    except Exception as e:
        print(f"Error fetching season averages for {player_id}: {e}")
        return {'ppg': 0.0, 'mpg': 0.0}


@dataclass
class BacktestResult:
    """Result of a single prediction vs actual comparison"""
    player_id: str
    player_name: str
    game_date: str
    opponent_abbr: str
    stat: str
    predicted: float
    actual: float
    error: float  # predicted - actual
    abs_error: float
    pct_error: float  # abs_error / actual * 100 (if actual > 0)
    confidence: str
    is_home: bool
    player_type: str = "Unknown"  # 'Star', 'Starter', 'Role Player'
    player_ppg: float = 0.0
    player_mpg: float = 0.0
    regression_tier: str = "Unknown"  # 'Ultra-elite', 'Elite scorer', 'Star', 'Starter', 'Role player'


@dataclass 
class BacktestSummary:
    """Aggregated backtest metrics for a stat"""
    stat: str
    n_predictions: int
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Square Error
    bias: float  # Mean Error (positive = over-predicting)
    within_10_pct: float  # % of predictions within 10% of actual
    within_20_pct: float  # % of predictions within 20% of actual
    within_3_pts: float  # % of predictions within 3 points of actual


def get_team_abbr_from_matchup(matchup: str, is_home: bool) -> str:
    """
    Extract opponent abbreviation from matchup string.
    Matchup format: 'MIA vs. NYK' (home) or 'MIA @ NYK' (away)
    """
    if ' vs. ' in matchup:
        # Home game: opponent is after 'vs. '
        return matchup.split(' vs. ')[1]
    elif ' @ ' in matchup:
        # Away game: opponent is after '@ '
        return matchup.split(' @ ')[1]
    return 'UNK'


def get_opponent_team_id(opponent_abbr: str) -> Optional[int]:
    """Get team ID from abbreviation"""
    team_abbr_to_id = {
        'ATL': 1610612737, 'BOS': 1610612738, 'BKN': 1610612751, 'CHA': 1610612766,
        'CHI': 1610612741, 'CLE': 1610612739, 'DAL': 1610612742, 'DEN': 1610612743,
        'DET': 1610612765, 'GSW': 1610612744, 'HOU': 1610612745, 'IND': 1610612754,
        'LAC': 1610612746, 'LAL': 1610612747, 'MEM': 1610612763, 'MIA': 1610612748,
        'MIL': 1610612749, 'MIN': 1610612750, 'NOP': 1610612740, 'NYK': 1610612752,
        'OKC': 1610612760, 'ORL': 1610612753, 'PHI': 1610612755, 'PHX': 1610612756,
        'POR': 1610612757, 'SAC': 1610612758, 'SAS': 1610612759, 'TOR': 1610612761,
        'UTA': 1610612762, 'WAS': 1610612764
    }
    return team_abbr_to_id.get(opponent_abbr)


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_game_logs_for_backtest(player_id: str, season: str = CURRENT_SEASON) -> pd.DataFrame:
    """
    Get player's game logs for backtesting.
    """
    try:
        game_logs = endpoints.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star='Regular Season'
        ).get_data_frames()[0]
        
        game_logs['GAME_DATE'] = pd.to_datetime(game_logs['GAME_DATE'])
        game_logs = game_logs.sort_values('GAME_DATE', ascending=True)
        
        return game_logs
    except Exception as e:
        print(f"Error fetching game logs for player {player_id}: {e}")
        return pd.DataFrame()


def run_single_game_backtest(
    player_id: str,
    player_name: str,
    player_team_id: int,
    game_row: pd.Series,
    player_type: str = "Unknown",
    player_ppg: float = 0.0,
    player_mpg: float = 0.0,
    stats: List[str] = STATS_TO_BACKTEST
) -> List[BacktestResult]:
    """
    Run prediction for a single historical game and compare to actual.
    """
    results = []
    
    # Parse game info - handle different column names
    try:
        if isinstance(game_row.get('GAME_DATE'), str):
            game_date = game_row['GAME_DATE']
        else:
            game_date = game_row['GAME_DATE'].strftime('%Y-%m-%d')
    except:
        game_date = str(game_row.get('GAME_DATE', ''))
    
    # Get matchup - try different column names
    matchup = game_row.get('MATCHUP', game_row.get('Matchup', ''))
    if not matchup:
        print(f"Warning: No MATCHUP column found. Available columns: {game_row.index.tolist()}")
        return results
    
    is_home = ' vs. ' in str(matchup)
    opponent_abbr = get_team_abbr_from_matchup(str(matchup), is_home)
    opponent_team_id = get_opponent_team_id(opponent_abbr)
    
    if opponent_team_id is None:
        return results
    
    try:
        # Generate predictions using the model
        predictions = pm.generate_prediction(
            player_id=player_id,
            player_team_id=player_team_id,
            opponent_team_id=opponent_team_id,
            opponent_abbr=opponent_abbr,
            game_date=game_date,
            is_home=is_home
        )
        
        # Compare each stat
        for stat in stats:
            if stat not in predictions:
                continue
                
            pred = predictions[stat]
            actual = game_row.get(stat, 0)
            
            if pd.isna(actual):
                actual = 0
            
            error = pred.value - actual
            abs_error = abs(error)
            pct_error = (abs_error / actual * 100) if actual > 0 else 0
            
            # Get regression tier from prediction factors
            regression_tier = pred.factors.get('regression_tier', 'Unknown') if pred.factors else 'Unknown'
            
            results.append(BacktestResult(
                player_id=player_id,
                player_name=player_name,
                game_date=game_date,
                opponent_abbr=opponent_abbr,
                stat=stat,
                predicted=round(pred.value, 1),
                actual=actual,
                error=round(error, 1),
                abs_error=round(abs_error, 1),
                pct_error=round(pct_error, 1),
                confidence=pred.confidence,
                is_home=is_home,
                player_type=player_type,
                player_ppg=player_ppg,
                player_mpg=player_mpg,
                regression_tier=regression_tier
            ))
            
    except Exception as e:
        print(f"Error generating prediction for {player_name} on {game_date}: {e}")
    
    return results


def run_player_backtest(
    player_id: str,
    player_name: str,
    player_team_id: int,
    n_games: int = 10,
    skip_recent: int = 0
) -> List[BacktestResult]:
    """
    Run backtest for a single player over their last N games.
    
    Args:
        player_id: NBA API player ID
        player_name: Player's name for display
        player_team_id: Player's team ID
        n_games: Number of games to backtest
        skip_recent: Number of most recent games to skip (0 = include all)
    """
    game_logs = get_player_game_logs_for_backtest(player_id)
    
    if len(game_logs) == 0:
        return []
    
    # Get player season averages for categorization
    season_avgs = get_player_season_averages(player_id)
    ppg = season_avgs.get('ppg', 0.0)
    mpg = season_avgs.get('mpg', 0.0)
    player_type = categorize_player(ppg, mpg)
    
    # Sort descending to get most recent first, then apply skip and limit
    game_logs = game_logs.sort_values('GAME_DATE', ascending=False)
    
    if skip_recent > 0:
        game_logs = game_logs.iloc[skip_recent:]
    
    games_to_test = game_logs.head(n_games)
    
    all_results = []
    for _, game_row in games_to_test.iterrows():
        results = run_single_game_backtest(
            player_id=player_id,
            player_name=player_name,
            player_team_id=player_team_id,
            game_row=game_row,
            player_type=player_type,
            player_ppg=ppg,
            player_mpg=mpg
        )
        all_results.extend(results)
    
    return all_results


def calculate_backtest_summary(results: List[BacktestResult]) -> Dict[str, BacktestSummary]:
    """
    Calculate aggregate metrics from backtest results.
    """
    if not results:
        return {}
    
    df = pd.DataFrame([asdict(r) for r in results])
    summaries = {}
    
    for stat in df['stat'].unique():
        stat_df = df[df['stat'] == stat]
        
        if len(stat_df) == 0:
            continue
        
        predictions = stat_df['predicted'].values
        actuals = stat_df['actual'].values
        errors = stat_df['error'].values
        abs_errors = stat_df['abs_error'].values
        
        # Calculate metrics
        mae = np.mean(abs_errors)
        rmse = np.sqrt(np.mean(errors ** 2))
        bias = np.mean(errors)
        
        # Percentage within thresholds
        valid_actuals = actuals > 0
        if valid_actuals.any():
            pct_errors = abs_errors[valid_actuals] / actuals[valid_actuals] * 100
            within_10 = np.mean(pct_errors <= 10) * 100
            within_20 = np.mean(pct_errors <= 20) * 100
        else:
            within_10 = 0
            within_20 = 0
        
        # Within absolute threshold
        within_3 = np.mean(abs_errors <= 3) * 100
        
        summaries[stat] = BacktestSummary(
            stat=stat,
            n_predictions=len(stat_df),
            mae=round(mae, 2),
            rmse=round(rmse, 2),
            bias=round(bias, 2),
            within_10_pct=round(within_10, 1),
            within_20_pct=round(within_20, 1),
            within_3_pts=round(within_3, 1)
        )
    
    return summaries


def calculate_confidence_accuracy(results: List[BacktestResult]) -> Dict[str, Dict]:
    """
    Calculate accuracy broken down by confidence level.
    """
    if not results:
        return {}
    
    df = pd.DataFrame([asdict(r) for r in results])
    
    confidence_metrics = {}
    for conf in ['high', 'medium', 'low']:
        conf_df = df[df['confidence'] == conf]
        
        if len(conf_df) == 0:
            continue
        
        abs_errors = conf_df['abs_error'].values
        actuals = conf_df['actual'].values
        
        mae = np.mean(abs_errors)
        
        valid = actuals > 0
        if valid.any():
            pct_errors = abs_errors[valid] / actuals[valid] * 100
            within_10 = np.mean(pct_errors <= 10) * 100
        else:
            within_10 = 0
        
        confidence_metrics[conf] = {
            'count': len(conf_df),
            'mae': round(mae, 2),
            'within_10_pct': round(within_10, 1)
        }
    
    return confidence_metrics


def calculate_player_type_accuracy(results: List[BacktestResult], stat: str = 'PTS') -> Dict[str, Dict]:
    """
    Calculate accuracy broken down by player type (Star, Starter, Role Player).
    
    Args:
        results: List of backtest results
        stat: Stat to analyze (default: PTS)
    
    Returns:
        Dict with metrics per player type
    """
    if not results:
        return {}
    
    df = pd.DataFrame([asdict(r) for r in results])
    
    # Filter to specific stat
    df = df[df['stat'] == stat]
    
    if len(df) == 0:
        return {}
    
    player_type_metrics = {}
    for ptype in ['Ultra-elite', 'Star', 'Starter', 'Role Player']:
        type_df = df[df['player_type'] == ptype]
        
        if len(type_df) == 0:
            continue
        
        abs_errors = type_df['abs_error'].values
        errors = type_df['error'].values
        actuals = type_df['actual'].values
        
        mae = np.mean(abs_errors)
        rmse = np.sqrt(np.mean(errors ** 2))
        bias = np.mean(errors)
        
        valid = actuals > 0
        if valid.any():
            pct_errors = abs_errors[valid] / actuals[valid] * 100
            within_10 = np.mean(pct_errors <= 10) * 100
            within_20 = np.mean(pct_errors <= 20) * 100
        else:
            within_10 = 0
            within_20 = 0
        
        within_3 = np.mean(abs_errors <= 3) * 100
        
        # Get unique players in this category
        unique_players = type_df['player_name'].nunique()
        
        # Get average PPG and MPG for context
        avg_ppg = type_df['player_ppg'].mean()
        avg_mpg = type_df['player_mpg'].mean()
        
        player_type_metrics[ptype] = {
            'count': len(type_df),
            'unique_players': unique_players,
            'avg_ppg': round(avg_ppg, 1),
            'avg_mpg': round(avg_mpg, 1),
            'mae': round(mae, 2),
            'rmse': round(rmse, 2),
            'bias': round(bias, 2),
            'within_10_pct': round(within_10, 1),
            'within_20_pct': round(within_20, 1),
            'within_3_pts': round(within_3, 1)
        }
    
    return player_type_metrics


def format_player_type_summary(player_type_metrics: Dict[str, Dict]) -> pd.DataFrame:
    """
    Format player type accuracy metrics as a DataFrame for display.
    """
    if not player_type_metrics:
        return pd.DataFrame()
    
    rows = []
    type_order = ['Ultra-elite', 'Star', 'Starter', 'Role Player']
    
    for ptype in type_order:
        if ptype in player_type_metrics:
            m = player_type_metrics[ptype]
            rows.append({
                'Type': ptype,
                'Players': m['unique_players'],
                'Predictions': m['count'],
                'Avg PPG': m['avg_ppg'],
                'Avg MPG': m['avg_mpg'],
                'MAE': m['mae'],
                'Bias': f"{'+' if m['bias'] > 0 else ''}{m['bias']}",
                'Within 10%': f"{m['within_10_pct']}%",
                'Within 3pts': f"{m['within_3_pts']}%"
            })
    
    return pd.DataFrame(rows)


def get_regression_tier_from_results(results: List[BacktestResult]) -> str:
    """
    Get the most common regression tier from backtest results.
    Only looks at PTS predictions since that's where regression applies.
    """
    if not results:
        return "Unknown"
    
    # Filter to PTS predictions only (where regression tier is set)
    pts_results = [r for r in results if r.stat == 'PTS']
    if not pts_results:
        return "Unknown"
    
    # Get the most common tier
    tiers = [r.regression_tier for r in pts_results if r.regression_tier != 'Unknown']
    if not tiers:
        return "Unknown"
    
    # Return most common (should all be the same for single player)
    from collections import Counter
    return Counter(tiers).most_common(1)[0][0]


def run_multi_player_backtest(
    players: List[Dict],  # [{'id': '...', 'name': '...', 'team_id': ...}, ...]
    n_games: int = 10,
    skip_recent: int = 0,
    progress_callback=None
) -> Tuple[List[BacktestResult], Dict[str, BacktestSummary]]:
    """
    Run backtest across multiple players.
    
    Args:
        players: List of player dicts with 'id', 'name', 'team_id'
        n_games: Number of games per player to test
        skip_recent: Games to skip (for true out-of-sample testing)
        progress_callback: Optional callback for progress updates
    
    Returns:
        Tuple of (all results, summary by stat)
    """
    all_results = []
    
    for i, player in enumerate(players):
        if progress_callback:
            progress_callback(i + 1, len(players), player['name'])
        
        results = run_player_backtest(
            player_id=player['id'],
            player_name=player['name'],
            player_team_id=player['team_id'],
            n_games=n_games,
            skip_recent=skip_recent
        )
        all_results.extend(results)
    
    summaries = calculate_backtest_summary(all_results)
    
    return all_results, summaries


def format_summary_for_display(summaries: Dict[str, BacktestSummary]) -> pd.DataFrame:
    """
    Format backtest summaries as a DataFrame for display.
    """
    if not summaries:
        return pd.DataFrame()
    
    rows = []
    stat_order = ['PTS', 'REB', 'AST', 'PRA', 'STL', 'BLK', 'FG3M', 'FTM', 'TOV', 'FPTS']
    
    for stat in stat_order:
        if stat in summaries:
            s = summaries[stat]
            rows.append({
                'Stat': stat,
                'N': s.n_predictions,
                'MAE': s.mae,
                'RMSE': s.rmse,
                'Bias': f"{'+' if s.bias > 0 else ''}{s.bias}",
                'Within 10%': f"{s.within_10_pct}%",
                'Within 20%': f"{s.within_20_pct}%",
                'Within 3pts': f"{s.within_3_pts}%"
            })
    
    # Add any remaining stats
    for stat, s in summaries.items():
        if stat not in stat_order:
            rows.append({
                'Stat': stat,
                'N': s.n_predictions,
                'MAE': s.mae,
                'RMSE': s.rmse,
                'Bias': f"{'+' if s.bias > 0 else ''}{s.bias}",
                'Within 10%': f"{s.within_10_pct}%",
                'Within 20%': f"{s.within_20_pct}%",
                'Within 3pts': f"{s.within_3_pts}%"
            })
    
    return pd.DataFrame(rows)


def get_worst_predictions(results: List[BacktestResult], n: int = 10) -> pd.DataFrame:
    """
    Get the N worst predictions by absolute error.
    """
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame([asdict(r) for r in results])
    worst = df.nlargest(n, 'abs_error')[
        ['player_name', 'game_date', 'stat', 'predicted', 'actual', 'error', 'confidence']
    ]
    worst.columns = ['Player', 'Date', 'Stat', 'Pred', 'Actual', 'Error', 'Conf']
    return worst


def get_best_predictions(results: List[BacktestResult], n: int = 10) -> pd.DataFrame:
    """
    Get the N best predictions by absolute error.
    """
    if not results:
        return pd.DataFrame()
    
    df = pd.DataFrame([asdict(r) for r in results])
    best = df.nsmallest(n, 'abs_error')[
        ['player_name', 'game_date', 'stat', 'predicted', 'actual', 'error', 'confidence']
    ]
    best.columns = ['Player', 'Date', 'Stat', 'Pred', 'Actual', 'Error', 'Conf']
    return best


# Quick test function
def quick_backtest(player_id: str, player_name: str, player_team_id: int, n_games: int = 5):
    """
    Quick backtest for a single player - useful for testing.
    """
    print(f"\n{'='*60}")
    print(f"BACKTEST: {player_name}")
    print(f"Testing last {n_games} games")
    print(f"{'='*60}\n")
    
    results = run_player_backtest(
        player_id=player_id,
        player_name=player_name,
        player_team_id=player_team_id,
        n_games=n_games
    )
    
    if not results:
        print("No results generated.")
        return None, None
    
    summaries = calculate_backtest_summary(results)
    
    print("\nSUMMARY BY STAT:")
    print("-" * 60)
    for stat, s in summaries.items():
        print(f"{stat:8} | MAE: {s.mae:5.1f} | Bias: {s.bias:+5.1f} | Within 10%: {s.within_10_pct:5.1f}%")
    
    print("\n\nWORST PREDICTIONS:")
    print("-" * 60)
    worst = get_worst_predictions(results, 5)
    print(worst.to_string(index=False))
    
    return results, summaries

