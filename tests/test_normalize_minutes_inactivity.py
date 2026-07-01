"""
Tests for normalize_team_minutes inactivity filtering.

Covers two regression scenarios:
  1. Two-way / fringe players who had ≤5 NBA games and have been
     inactive > 14 days should be zeroed out even when their season-average
     MPG ≥ 22 (e.g. Zyon Pullin, Thomas Sorber).
  2. Veterans dropped from the rotation who have been inactive for 21+ days
     and whose season-average MPG is < 30 should be zeroed out even though
     they are not in the injury report (e.g. Mike Conley).
"""

import sys
import os
from datetime import date, timedelta

import pandas as pd
import pytest

# Allow importing from combined-app/pages without a full streamlit environment.
# We import the function under test by exec'ing just the function definition.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'combined-app', 'pages'))

# ---------------------------------------------------------------------------
# Extract normalize_team_minutes without importing the full Streamlit page
# ---------------------------------------------------------------------------
_PAGE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'combined-app', 'pages', '3_Predictions.py'
)

def _load_normalize_fn():
    """
    Parse normalize_team_minutes out of 3_Predictions.py without executing
    the rest of the Streamlit page (which would call st.*, API calls, etc.).
    """
    import ast, types, textwrap

    with open(_PAGE_PATH, 'r') as fh:
        source = fh.read()

    tree = ast.parse(source)

    # Find the normalize_team_minutes FunctionDef node
    target_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'normalize_team_minutes':
            target_node = node
            break

    assert target_node is not None, "normalize_team_minutes not found in 3_Predictions.py"

    # Re-serialize just that function
    fn_source = ast.unparse(target_node)

    # Provide the minimal globals the function uses
    globs = {
        'pd': pd,
        'timedelta': timedelta,
        '__builtins__': __builtins__,
    }
    exec(compile(fn_source, _PAGE_PATH, 'exec'), globs)
    return globs['normalize_team_minutes']


normalize_team_minutes = _load_normalize_fn()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GAME_DATE = '2026-03-15'
GAME_DATE_DT = pd.to_datetime(GAME_DATE)


def _make_logs(player_id: int, game_dates: list[str], mpg: float = 24.0) -> pd.DataFrame:
    """Build a minimal bulk_game_logs fragment for a single player."""
    rows = []
    for i, gd in enumerate(game_dates):
        rows.append({
            'PLAYER_ID': player_id,
            'GAME_DATE': pd.to_datetime(gd),
            'MIN': mpg,
            'GAME_ID': f'002{i:07d}',
            'TEAM_ID': 1610612750,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=['PLAYER_ID', 'GAME_DATE', 'MIN', 'GAME_ID', 'TEAM_ID']
    )


def _base_statlines(players: list[dict]) -> list[dict]:
    """
    Build a minimal statlines_list.  Each entry in `players` should have:
      player_id, is_away, MIN (season avg projected minutes).
    All stats default to 0.
    """
    result = []
    for p in players:
        result.append({
            'player_id': str(p['player_id']),
            'Player': p.get('name', f"Player_{p['player_id']}"),
            'Team': 'MIN',
            'MIN': p.get('MIN', 20.0),
            '_original_season_minutes': p.get('MIN', 20.0),
            'PTS': p.get('PTS', 15.0),
            'REB': p.get('REB', 4.0),
            'AST': p.get('AST', 3.0),
            'STL': 1.0,
            'BLK': 0.5,
            'TOV': 1.5,
            'FG3M': 1.0,
            'FTM': 2.0,
            'PRA': 22.0,
            'RA': 7.0,
            'FPTS': 28.0,
            'is_away': p.get('is_away', True),
        })
    return result


# ---------------------------------------------------------------------------
# Scenario 1 – Two-way / fringe player (≤5 games, inactive 14+ days)
# ---------------------------------------------------------------------------

class TestTwoWayPlayerFiltering:
    """
    A two-way player played 2 NBA games in October, averaged 24 MPG during
    those games (season avg = 24 → role_baseline = 24 ≥ 22).
    Their last game was 90 days before the prediction date.
    They have no injury designation.
    Expected: MIN should be 0 after normalization.
    """

    TWO_WAY_ID = 9999901
    TWO_WAY_MPG = 24.0  # High enough to bypass the old `< 22` check

    def _build_logs(self):
        # Two games in October (~150 days before mid-March)
        game_dates = [
            (GAME_DATE_DT - timedelta(days=150)).strftime('%Y-%m-%d'),
            (GAME_DATE_DT - timedelta(days=145)).strftime('%Y-%m-%d'),
        ]
        regular_players = []
        for pid in range(1, 10):
            for offset in range(5):
                regular_players.append({
                    'PLAYER_ID': pid,
                    'GAME_DATE': GAME_DATE_DT - timedelta(days=offset * 3),
                    'MIN': 28.0,
                    'GAME_ID': f'00200{pid}{offset}',
                    'TEAM_ID': 1610612750,
                })
        two_way_logs = _make_logs(self.TWO_WAY_ID, game_dates, mpg=self.TWO_WAY_MPG)
        return pd.concat([pd.DataFrame(regular_players), two_way_logs], ignore_index=True)

    def _build_statlines(self):
        players = []
        for pid in range(1, 10):
            players.append({'player_id': pid, 'is_away': True, 'MIN': 26.0})
        players.append({
            'player_id': self.TWO_WAY_ID,
            'is_away': True,
            'MIN': self.TWO_WAY_MPG,
            'name': 'Zyon Pullin',
        })
        return _base_statlines(players)

    def test_two_way_player_gets_zeroed_pre_fix(self):
        """
        This test FAILS before the fix: the two-way player retains minutes
        because role_baseline (24) >= 22, bypassing the old inactivity check.
        """
        statlines = self._build_statlines()
        bulk_logs = self._build_logs()

        normalize_team_minutes(
            statlines,
            out_player_ids=set(),
            bulk_game_logs=bulk_logs,
            game_date=GAME_DATE,
        )

        two_way = next(s for s in statlines if s['player_id'] == str(self.TWO_WAY_ID))
        assert two_way['MIN'] == 0.0, (
            f"Two-way player should have MIN=0 after normalization, "
            f"got {two_way['MIN']:.1f}"
        )


# ---------------------------------------------------------------------------
# Scenario 2 – Veteran out of rotation (inactive 21+ days, role_baseline 22-29)
# ---------------------------------------------------------------------------

class TestVeteranOutOfRotation:
    """
    A veteran played 40 games earlier this season averaging 22 MPG.
    Their last game was 25 days before the prediction date.
    No injury designation.
    Expected: MIN should be 0 after normalization.
    """

    VETERAN_ID = 9999902
    VETERAN_MPG = 22.0  # season average ≥ 22, so old < 22 check passes him through

    def _build_logs(self):
        # 40 games spread across the season, most recent 25 days ago
        rows = []
        for i in range(40):
            rows.append({
                'PLAYER_ID': self.VETERAN_ID,
                'GAME_DATE': GAME_DATE_DT - timedelta(days=25 + i * 3),
                'MIN': self.VETERAN_MPG,
                'GAME_ID': f'002vet{i:04d}',
                'TEAM_ID': 1610612750,
            })
        # Regular rotation players — recent games
        for pid in range(1, 10):
            for offset in range(5):
                rows.append({
                    'PLAYER_ID': pid,
                    'GAME_DATE': GAME_DATE_DT - timedelta(days=offset * 3),
                    'MIN': 28.0,
                    'GAME_ID': f'00200{pid}{offset}',
                    'TEAM_ID': 1610612750,
                })
        return pd.DataFrame(rows)

    def _build_statlines(self):
        players = []
        for pid in range(1, 10):
            players.append({'player_id': pid, 'is_away': True, 'MIN': 26.0})
        players.append({
            'player_id': self.VETERAN_ID,
            'is_away': True,
            'MIN': self.VETERAN_MPG,
            'name': 'Mike Conley',
        })
        return _base_statlines(players)

    def test_veteran_out_of_rotation_gets_zeroed_pre_fix(self):
        """
        This test FAILS before the fix: the veteran retains minutes because
        role_baseline (22) >= 22 bypasses the old 14-day inactivity check,
        and there is no 21-day extended check yet.
        """
        statlines = self._build_statlines()
        bulk_logs = self._build_logs()

        normalize_team_minutes(
            statlines,
            out_player_ids=set(),
            bulk_game_logs=bulk_logs,
            game_date=GAME_DATE,
        )

        veteran = next(s for s in statlines if s['player_id'] == str(self.VETERAN_ID))
        assert veteran['MIN'] == 0.0, (
            f"Veteran out of rotation should have MIN=0 after normalization, "
            f"got {veteran['MIN']:.1f}"
        )


# ---------------------------------------------------------------------------
# Sanity checks – fixes must not break legitimate players
# ---------------------------------------------------------------------------

class TestLegitimatePlayersUnaffected:
    """
    Verify the new filters don't accidentally zero out players who should play.
    """

    def _nine_player_logs(self, recent_days=3):
        rows = []
        for pid in range(1, 10):
            rows.append({
                'PLAYER_ID': pid,
                'GAME_DATE': GAME_DATE_DT - timedelta(days=recent_days),
                'MIN': 28.0,
                'GAME_ID': f'002test{pid}',
                'TEAM_ID': 1610612750,
            })
        return pd.DataFrame(rows)

    def test_active_rotation_player_keeps_minutes(self):
        """A rotation player who played 3 days ago must keep minutes."""
        statlines = _base_statlines([
            {'player_id': pid, 'is_away': True, 'MIN': 25.0}
            for pid in range(1, 10)
        ])
        normalize_team_minutes(
            statlines,
            out_player_ids=set(),
            bulk_game_logs=self._nine_player_logs(recent_days=3),
            game_date=GAME_DATE,
        )
        for s in statlines:
            assert s['MIN'] > 0, f"Active player {s['player_id']} lost minutes unexpectedly"

    def test_star_inactive_20_days_keeps_minutes(self):
        """
        A franchise star (35 MPG avg) who missed 20 days should NOT be zeroed —
        they are likely managing load or returning from injury.
        """
        STAR_ID = 8888801
        rows = []
        # Star last played 20 days ago
        rows.append({
            'PLAYER_ID': STAR_ID,
            'GAME_DATE': GAME_DATE_DT - timedelta(days=20),
            'MIN': 36.0,
            'GAME_ID': '002star001',
            'TEAM_ID': 1610612750,
        })
        # 8 other active rotation players
        for pid in range(1, 9):
            rows.append({
                'PLAYER_ID': pid,
                'GAME_DATE': GAME_DATE_DT - timedelta(days=3),
                'MIN': 26.0,
                'GAME_ID': f'002reg{pid}',
                'TEAM_ID': 1610612750,
            })
        bulk_logs = pd.DataFrame(rows)

        statlines = _base_statlines(
            [{'player_id': STAR_ID, 'is_away': True, 'MIN': 35.0}]
            + [{'player_id': pid, 'is_away': True, 'MIN': 26.0} for pid in range(1, 9)]
        )
        normalize_team_minutes(
            statlines,
            out_player_ids=set(),
            bulk_game_logs=bulk_logs,
            game_date=GAME_DATE,
        )
        star = next(s for s in statlines if s['player_id'] == str(STAR_ID))
        assert star['MIN'] > 0, "Franchise star inactive 20 days should keep projected minutes"
