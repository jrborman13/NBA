"""
Without Player Stats Module

Computes a player's historical stat averages in games where specific teammates were absent.
Used to provide empirical "without X" multipliers for injury adjustments instead of relying
solely on generic role-based formulas.

Algorithm:
  1. Pull the target player's season game logs from the pre-fetched bulk DataFrame.
  2. Pull all GAME_IDs in which the absent player(s) appeared.
  3. The set of target-player games *not* in those GAME_IDs represents games played
     without the absent teammate(s).
  4. Compute per-stat averages and express them as multipliers relative to season average.
  5. If the combined sample (all absent players out simultaneously) is too small,
     fall back to the individual absent player with the largest "without" sample.
"""

from typing import Dict, List, Optional
import pandas as pd

# Stats carried through the pipeline
_STATS = ['PTS', 'REB', 'AST', 'STL', 'BLK', 'FG3M', 'FTM', 'MIN']

# Minimum games required to trust historical data; fewer than this → return None
DEFAULT_MIN_GAMES = 3

# Hard caps on the multiplier to prevent extreme predictions
_MULT_LOW_CAP = 0.70   # player can't be capped below 70% of season avg
_MULT_HIGH_CAP = 1.60  # player can't exceed 160% of season avg


def get_without_player_stats(
    player_id: str,
    absent_player_ids: List[str],
    bulk_game_logs: pd.DataFrame,
    min_games: int = DEFAULT_MIN_GAMES,
) -> Optional[Dict]:
    """
    Return empirical stat multipliers for *player_id* in games where all
    *absent_player_ids* were missing from the lineup.

    Args:
        player_id:          Target player's NBA ID (string).
        absent_player_ids:  IDs of teammates who are out tonight.
        bulk_game_logs:     Full-season game log DataFrame from
                            prediction_features.get_bulk_player_game_logs().
        min_games:          Minimum "without" games needed to use this data.

    Returns:
        Dict with keys:
            multipliers     – {stat: float} — ratio of without-X avg to season avg,
                              capped to [0.70, 1.60]
            without_x_avgs  – raw per-stat averages in "without X" games
            season_avgs     – raw per-stat season averages (all games)
            sample_size     – number of "without X" games found
            total_games     – total games in player's season log
            method          – 'combined' | 'single:<absent_id>'
        or None if there is insufficient data to be useful.
    """
    if not absent_player_ids or bulk_game_logs is None or len(bulk_game_logs) == 0:
        return None

    try:
        player_id_int = int(player_id)
    except (ValueError, TypeError):
        return None

    # ── Target player's season log ──────────────────────────────────────────
    player_logs = bulk_game_logs[bulk_game_logs['PLAYER_ID'] == player_id_int].copy()
    if len(player_logs) < min_games:
        return None

    season_avgs = _compute_stat_avgs(player_logs)

    # ── Primary: all absent players simultaneously ──────────────────────────
    combined_absent_game_ids = _get_absent_game_ids(absent_player_ids, bulk_game_logs)
    without_all_logs = player_logs[~player_logs['GAME_ID'].isin(combined_absent_game_ids)]

    if len(without_all_logs) >= min_games:
        without_x_avgs = _compute_stat_avgs(without_all_logs)
        return {
            'multipliers': _compute_multipliers(without_x_avgs, season_avgs),
            'without_x_avgs': without_x_avgs,
            'season_avgs': season_avgs,
            'sample_size': len(without_all_logs),
            'total_games': len(player_logs),
            'method': 'combined',
        }

    # ── Fallback: best individual absent player ─────────────────────────────
    # Pick the absent player whose individual absence yields the most "without" games
    # for the target player.  If multiple absent players have enough games, prefer
    # the one with the largest sample (most signal).
    best_result: Optional[Dict] = None
    best_sample = 0

    for absent_id in absent_player_ids:
        absent_game_ids = _get_absent_game_ids([absent_id], bulk_game_logs)
        without_one_logs = player_logs[~player_logs['GAME_ID'].isin(absent_game_ids)]
        n = len(without_one_logs)
        if n >= min_games and n > best_sample:
            best_sample = n
            without_x_avgs = _compute_stat_avgs(without_one_logs)
            best_result = {
                'multipliers': _compute_multipliers(without_x_avgs, season_avgs),
                'without_x_avgs': without_x_avgs,
                'season_avgs': season_avgs,
                'sample_size': n,
                'total_games': len(player_logs),
                'method': f'single:{absent_id}',
            }

    return best_result  # None if no absent player has enough games


# ─── Private helpers ────────────────────────────────────────────────────────

def _get_absent_game_ids(absent_player_ids: List[str], bulk_game_logs: pd.DataFrame) -> set:
    """Return GAME_IDs in which any of the absent players appeared."""
    absent_game_ids: set = set()
    for absent_id in absent_player_ids:
        try:
            absent_id_int = int(absent_id)
        except (ValueError, TypeError):
            continue
        absent_logs = bulk_game_logs[bulk_game_logs['PLAYER_ID'] == absent_id_int]
        absent_game_ids.update(absent_logs['GAME_ID'].tolist())
    return absent_game_ids


def _compute_stat_avgs(logs: pd.DataFrame) -> Dict[str, float]:
    """Mean of each tracked stat across the provided game logs."""
    avgs: Dict[str, float] = {}
    for stat in _STATS:
        if stat in logs.columns and len(logs) > 0:
            avgs[stat] = float(logs[stat].mean())
    return avgs


def _compute_multipliers(without_x_avgs: Dict[str, float], season_avgs: Dict[str, float]) -> Dict[str, float]:
    """
    Ratio of without-X average to season average for each stat.
    Capped to [_MULT_LOW_CAP, _MULT_HIGH_CAP] to prevent extreme values.
    Only computed when the season average is large enough to be meaningful.
    """
    multipliers: Dict[str, float] = {}
    for stat in _STATS:
        season_val = season_avgs.get(stat, 0.0)
        without_val = without_x_avgs.get(stat, 0.0)
        if season_val > 0.5:
            raw = without_val / season_val
            multipliers[stat] = max(_MULT_LOW_CAP, min(_MULT_HIGH_CAP, raw))
        else:
            multipliers[stat] = 1.0
    return multipliers
