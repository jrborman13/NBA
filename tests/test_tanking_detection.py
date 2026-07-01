"""
Tests for tanking detection and minute adjustment logic.

Validates:
  - Hard / soft tank classification thresholds
  - Pelicans (pick-incentive team) never flagged as tanking
  - Tanking team: stars/starters get fewer minutes, bench gets more
  - Playoff contender facing tanking team: mild garbage-time reductions for stars, bench gains
  - Both teams tanking: reduced-intensity adjustments at 50%
  - Spread < 8 → no adjustments applied
  - No spread available → adjustments applied at 75%
"""

import sys
import os

import pandas as pd
import pytest

# Import directly from the shared module — no AST parsing needed.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'combined-app', 'player_app'))
from tanking_utils import (
    PICK_INCENTIVE_WIN_TEAM_IDS as PICK_IDS,
    games_back_from_play_in as _games_back_from_play_in,
    detect_tanking as _detect_tanking,
    compute_tanking_adjustments,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_standings(teams: list[dict]) -> pd.DataFrame:
    """
    Build a minimal LeagueStandings DataFrame.
    Each dict: team_id, conf, wins, losses, rank (PlayoffRank within conf).
    """
    rows = []
    for t in teams:
        rows.append({
            'TeamID': t['team_id'],
            'Conference': t['conf'],
            'WINS': t['wins'],
            'LOSSES': t['losses'],
            'PlayoffRank': t['rank'],
        })
    return pd.DataFrame(rows)


def _make_statlines(players: list[dict]) -> list[dict]:
    """
    Minimal statlines. Each dict needs: player_id, is_away, baseline_min.
    """
    result = []
    for p in players:
        bmin = p['baseline_min']
        result.append({
            'player_id': str(p['player_id']),
            'MIN': bmin,
            '_original_season_minutes': bmin,
            'is_away': p.get('is_away', True),
            'Player': p.get('name', f"P{p['player_id']}"),
        })
    return result


# ---------------------------------------------------------------------------
# Standings fixture: 20 teams (10 East, 10 West) with varied records
# ---------------------------------------------------------------------------

def _base_standings():
    """
    West seeds 1–10 with clear separation; an extra tanking team at seed 12.
    East seeds 1–10; Pelicans (pick-incentive) placed at seed 13.
    """
    rows = []
    # West: 10 playoff / play-in teams, then tanking teams
    for rank in range(1, 11):
        w = 50 - (rank - 1) * 2
        rows.append({'team_id': 1000 + rank, 'conf': 'West', 'wins': w,
                     'losses': 82 - 17 - w, 'rank': rank})
    # Tanking team: seed 12 West, 22 wins — hard tank territory
    rows.append({'team_id': 9001, 'conf': 'West', 'wins': 22, 'losses': 43, 'rank': 12})
    # Soft-tank team: seed 11 West, 33 wins (~6 GB from seed 10)
    seed10_w = 50 - 9 * 2  # = 32
    rows.append({'team_id': 9002, 'conf': 'West', 'wins': seed10_w - 6,
                 'losses': 82 - 17 - (seed10_w - 6), 'rank': 11})

    # East: 10 playoff / play-in teams
    for rank in range(1, 11):
        w = 50 - (rank - 1) * 2
        rows.append({'team_id': 2000 + rank, 'conf': 'East', 'wins': w,
                     'losses': 82 - 17 - w, 'rank': rank})
    # Pelicans (pick-incentive): East seed 13, similar record to hard tanker
    rows.append({'team_id': 1610612740, 'conf': 'East', 'wins': 22,
                 'losses': 43, 'rank': 13})

    return _make_standings(rows)


STANDINGS = _base_standings()
SEED10_WEST_ID = 1009
HARD_TANK_ID   = 9001   # 22W, ~10+ GB back
SOFT_TANK_ID   = 9002   # ~6 GB back
PLAYOFF_ID     = 1001   # Top West seed
PELICANS_ID    = 1610612740


# ---------------------------------------------------------------------------
# Tests: _games_back_from_play_in
# ---------------------------------------------------------------------------

class TestGamesBack:
    def test_top_seed_zero_gb(self):
        gb = _games_back_from_play_in(PLAYOFF_ID, STANDINGS)
        assert gb == 0.0

    def test_hard_tanker_large_gb(self):
        gb = _games_back_from_play_in(HARD_TANK_ID, STANDINGS)
        assert gb >= 10, f"Expected ≥10 GB, got {gb}"

    def test_soft_tanker_around_6_gb(self):
        gb = _games_back_from_play_in(SOFT_TANK_ID, STANDINGS)
        assert 4 <= gb <= 9, f"Expected 4–9 GB, got {gb}"


# ---------------------------------------------------------------------------
# Tests: _detect_tanking
# ---------------------------------------------------------------------------

class TestDetectTanking:
    def test_hard_tank(self):
        assert _detect_tanking(HARD_TANK_ID, STANDINGS) == 'hard'

    def test_soft_tank(self):
        assert _detect_tanking(SOFT_TANK_ID, STANDINGS) == 'soft'

    def test_playoff_team_not_tanking(self):
        assert _detect_tanking(PLAYOFF_ID, STANDINGS) is None

    def test_pelicans_never_tanking(self):
        # Even though Pelicans have same record as hard tanker, pick incentive exempts them
        assert _detect_tanking(PELICANS_ID, STANDINGS) is None


# ---------------------------------------------------------------------------
# Tests: compute_tanking_adjustments (minute deltas)
# ---------------------------------------------------------------------------

def _run_adjustments(away_id, home_id, spread, players):
    statlines = _make_statlines(players)
    adj, ctx = compute_tanking_adjustments(
        statlines, away_id, home_id, 'TANK', 'WIN',
        standings_df=STANDINGS, spread=spread,
    )
    return adj, ctx, statlines


class TestTankingMinuteDeltas:
    """Hard-tank away team vs playoff home team, spread = 14 (100% multiplier)."""

    PLAYERS = [
        # Away (tanking): star, starter, rotation, bench
        {'player_id': 1, 'is_away': True,  'baseline_min': 36, 'name': 'Star_tank'},
        {'player_id': 2, 'is_away': True,  'baseline_min': 29, 'name': 'Starter_tank'},
        {'player_id': 3, 'is_away': True,  'baseline_min': 24, 'name': 'Rotation_tank'},
        {'player_id': 4, 'is_away': True,  'baseline_min': 16, 'name': 'Bench_tank'},
        # Home (playoff contender): star, starter, rotation, bench
        {'player_id': 5, 'is_away': False, 'baseline_min': 35, 'name': 'Star_win'},
        {'player_id': 6, 'is_away': False, 'baseline_min': 30, 'name': 'Starter_win'},
        {'player_id': 7, 'is_away': False, 'baseline_min': 23, 'name': 'Rotation_win'},
        {'player_id': 8, 'is_away': False, 'baseline_min': 15, 'name': 'Bench_win'},
    ]

    def _run(self, spread=14):
        return _run_adjustments(HARD_TANK_ID, PLAYOFF_ID, spread, self.PLAYERS)

    def test_star_on_tanking_team_gets_fewer_minutes(self):
        adj, ctx, sl = self._run()
        star = next(s for s in sl if s['player_id'] == '1')
        baseline = star['_original_season_minutes']
        assert '1' in adj, "Star on tanking team should be in adjustments"
        assert adj['1'] < baseline, f"Expected reduced minutes, got {adj['1']} vs baseline {baseline}"

    def test_bench_on_tanking_team_gets_more_minutes(self):
        adj, ctx, sl = self._run()
        bench = next(s for s in sl if s['player_id'] == '4')
        baseline = bench['_original_season_minutes']
        assert '4' in adj, "Bench on tanking team should be in adjustments"
        assert adj['4'] > baseline, f"Expected more minutes for bench, got {adj['4']} vs baseline {baseline}"

    def test_star_on_playoff_team_gets_fewer_minutes_blowout(self):
        adj, ctx, sl = self._run()
        star = next(s for s in sl if s['player_id'] == '5')
        baseline = star['_original_season_minutes']
        assert '5' in adj, "Star on playoff team should be adjusted for blowout"
        assert adj['5'] < baseline

    def test_bench_on_playoff_team_gets_more_minutes_blowout(self):
        adj, ctx, sl = self._run()
        bench = next(s for s in sl if s['player_id'] == '8')
        baseline = bench['_original_season_minutes']
        assert '8' in adj
        assert adj['8'] > baseline

    def test_tight_spread_skips_adjustments(self):
        adj, ctx, _ = self._run(spread=6)
        assert len(adj) == 0, "Tight spread (<8) should produce no adjustments"

    def test_no_spread_applies_at_75_pct(self):
        adj_no_spread, _, _ = _run_adjustments(HARD_TANK_ID, PLAYOFF_ID, None, self.PLAYERS)
        adj_full, _, _ = _run_adjustments(HARD_TANK_ID, PLAYOFF_ID, 14, self.PLAYERS)
        # With no spread (75%), star reduction should be smaller than with 100%
        assert len(adj_no_spread) > 0, "No spread should still produce adjustments"
        # Star (player 1) reduction at 75% < 100%
        reduction_75 = float(next(s for s in self.PLAYERS if s['player_id'] == 1)['baseline_min']) - adj_no_spread['1']
        reduction_100 = float(next(s for s in self.PLAYERS if s['player_id'] == 1)['baseline_min']) - adj_full['1']
        assert reduction_75 < reduction_100


class TestBothTanking:
    """When both teams are tanking, adjustments apply at 50% of tank deltas."""

    PLAYERS = [
        {'player_id': 1, 'is_away': True,  'baseline_min': 35},
        {'player_id': 2, 'is_away': True,  'baseline_min': 16},
        {'player_id': 3, 'is_away': False, 'baseline_min': 35},
        {'player_id': 4, 'is_away': False, 'baseline_min': 16},
    ]

    def test_both_tanking_produces_adjustments(self):
        adj, ctx, _ = _run_adjustments(HARD_TANK_ID, SOFT_TANK_ID, 12, self.PLAYERS)
        assert ctx.get('both_tanking') is True
        assert len(adj) > 0

    def test_both_tanking_smaller_than_one_sided(self):
        # One-sided: hard tanker vs playoff
        adj_one, _, _ = _run_adjustments(HARD_TANK_ID, PLAYOFF_ID, 12, self.PLAYERS)
        # Both tanking
        adj_both, _, _ = _run_adjustments(HARD_TANK_ID, SOFT_TANK_ID, 12, self.PLAYERS)
        # Star reduction should be smaller when both are tanking
        one_red = self.PLAYERS[0]['baseline_min'] - adj_one['1']
        both_red = self.PLAYERS[0]['baseline_min'] - adj_both['1']
        assert both_red < one_red, "Both-tanking star reduction should be smaller than one-sided"
