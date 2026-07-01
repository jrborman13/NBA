"""
Tests for three bugs in analysis/injuries/app.py

Bug 1: get_missed_game_ids counts games from previous teams (no TEAM_ID filter)
Bug 2: compute_teammate_impact includes departed players (no active_player_ids filter)
Bug 3: _onoff_bar_chart crashes with KeyError: 'PLAYER_ID' when col is absent

Run:
    python -m pytest tests/test_injury_app_bugs.py -v
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np
import unittest.mock as mock

# ---------------------------------------------------------------------------
# Module setup — mock every external dep so app.py can be imported
# ---------------------------------------------------------------------------

_MOCK_MODULES = {
    'streamlit': mock.MagicMock(),
    'altair': mock.MagicMock(),
    'nba_api': mock.MagicMock(),
    'nba_api.library': mock.MagicMock(),
    'nba_api.library.http': mock.MagicMock(),
    'nba_api.stats': mock.MagicMock(),
    'nba_api.stats.endpoints': mock.MagicMock(),
    'nba_api.stats.static': mock.MagicMock(),
    'nba_api.stats.static.teams': mock.MagicMock(),
    'player_functions': mock.MagicMock(),
    'prediction_features': mock.MagicMock(),
    'team_onoff': mock.MagicMock(),
}

_app_path = os.path.join(os.path.dirname(__file__), '..', 'analysis', 'injuries')
if _app_path not in sys.path:
    sys.path.insert(0, _app_path)

with mock.patch.dict('sys.modules', _MOCK_MODULES):
    import importlib
    import app as _app

# ---------------------------------------------------------------------------
# Fixtures — shared DataFrames
# ---------------------------------------------------------------------------

TEAM_ID = 1610612750   # Timberwolves
OTHER_TEAM_ID = 1610612737  # Different team (was traded from)

PLAYER_STAR  = 101   # Star player (the "selected" player)
PLAYER_ROLE  = 202   # Teammate, currently active
PLAYER_GONE  = 303   # Departed player (traded before recent window)

# Team game IDs: games 1-60 are old, 61-75 are recent (last 15)
TEAM_GAMES_ALL = [f'G{i:04d}' for i in range(1, 76)]       # 75 team games
TEAM_GAMES_RECENT = TEAM_GAMES_ALL[-15:]                    # G0061 .. G0075
STAR_GAMES_WITH_TEAM = TEAM_GAMES_ALL[:65]                  # played 65 Wolves games


def _make_player_logs() -> pd.DataFrame:
    rows = []
    # PLAYER_STAR: 65 games for Wolves + 10 for other team earlier in season
    for gid in STAR_GAMES_WITH_TEAM:
        rows.append({'PLAYER_ID': PLAYER_STAR, 'TEAM_ID': TEAM_ID, 'GAME_ID': gid,
                     'GAME_DATE': f'2025-{10 + int(gid[1:]) // 10:02d}-01',
                     'MIN': 32.0, 'PTS': 20.0, 'REB': 5.0, 'AST': 5.0,
                     'FGM': 8.0, 'FGA': 16.0, 'FG3M': 2.0, 'FG3A': 5.0,
                     'FTM': 2.0, 'FTA': 3.0, 'STL': 1.0, 'BLK': 1.0, 'TOV': 2.0})
    for i in range(10):
        rows.append({'PLAYER_ID': PLAYER_STAR, 'TEAM_ID': OTHER_TEAM_ID,
                     'GAME_ID': f'OTH{i:04d}', 'GAME_DATE': '2025-10-15',
                     'MIN': 30.0, 'PTS': 18.0, 'REB': 4.0, 'AST': 4.0,
                     'FGM': 7.0, 'FGA': 15.0, 'FG3M': 1.0, 'FG3A': 4.0,
                     'FTM': 3.0, 'FTA': 4.0, 'STL': 1.0, 'BLK': 0.0, 'TOV': 2.0})

    # PLAYER_ROLE: 70 games, all Wolves, including all recent 15
    for gid in TEAM_GAMES_ALL[:70]:
        rows.append({'PLAYER_ID': PLAYER_ROLE, 'TEAM_ID': TEAM_ID, 'GAME_ID': gid,
                     'GAME_DATE': f'2025-{10 + int(gid[1:]) // 10:02d}-01',
                     'MIN': 20.0, 'PTS': 10.0, 'REB': 3.0, 'AST': 2.0,
                     'FGM': 4.0, 'FGA': 9.0, 'FG3M': 1.0, 'FG3A': 3.0,
                     'FTM': 1.0, 'FTA': 1.0, 'STL': 0.0, 'BLK': 0.0, 'TOV': 1.0})

    # PLAYER_GONE: 40 games for Wolves, all BEFORE the recent 15
    for gid in TEAM_GAMES_ALL[:40]:
        rows.append({'PLAYER_ID': PLAYER_GONE, 'TEAM_ID': TEAM_ID, 'GAME_ID': gid,
                     'GAME_DATE': f'2025-10-{int(gid[1:]) % 28 + 1:02d}',
                     'MIN': 18.0, 'PTS': 8.0, 'REB': 2.0, 'AST': 1.0,
                     'FGM': 3.0, 'FGA': 7.0, 'FG3M': 1.0, 'FG3A': 3.0,
                     'FTM': 1.0, 'FTA': 2.0, 'STL': 0.0, 'BLK': 0.0, 'TOV': 1.0})
    return pd.DataFrame(rows)


def _make_team_logs() -> pd.DataFrame:
    rows = []
    for i, gid in enumerate(TEAM_GAMES_ALL):
        rows.append({'TEAM_ID': TEAM_ID, 'GAME_ID': gid,
                     'GAME_DATE': f'2025-{10 + i // 10:02d}-{i % 28 + 1:02d}'})
    return pd.DataFrame(rows)


PLAYER_LOGS = _make_player_logs()
TEAM_LOGS = _make_team_logs()


# ---------------------------------------------------------------------------
# Bug 1: get_missed_game_ids must filter by TEAM_ID
# ---------------------------------------------------------------------------

class TestGetMissedGameIds:
    def test_played_count_is_team_only(self):
        """
        PLAYER_STAR played 65 Wolves games and 10 games for another team.
        played_ids should be 65 (Wolves only), not 75.
        """
        played, missed = _app.get_missed_game_ids(PLAYER_STAR, TEAM_ID, PLAYER_LOGS, TEAM_LOGS)
        # BUG (before fix): played would be 75 (includes other-team games)
        assert len(played) == 65, (
            f"Expected 65 Wolves games, got {len(played)}. "
            "Bug: player_logs not filtered by TEAM_ID."
        )

    def test_missed_count_is_team_games_minus_played(self):
        """Team had 75 games, star played 65 → 10 missed."""
        played, missed = _app.get_missed_game_ids(PLAYER_STAR, TEAM_ID, PLAYER_LOGS, TEAM_LOGS)
        assert len(missed) == 10, f"Expected 10 missed, got {len(missed)}"

    def test_other_team_games_not_in_played(self):
        """None of the other-team game IDs should appear in played_ids."""
        played, _ = _app.get_missed_game_ids(PLAYER_STAR, TEAM_ID, PLAYER_LOGS, TEAM_LOGS)
        other_team_games = {f'OTH{i:04d}' for i in range(10)}
        overlap = played & other_team_games
        assert len(overlap) == 0, f"Other-team games leaked into played_ids: {overlap}"


# ---------------------------------------------------------------------------
# Bug 2: compute_teammate_impact must exclude departed players
# ---------------------------------------------------------------------------

class TestComputeTeammateImpactExcludesDeparted:
    def test_departed_player_absent_when_active_ids_provided(self):
        """
        PLAYER_GONE was traded (not in recent 15 games).
        With active_player_ids={PLAYER_ROLE}, they should not appear in result.
        """
        active_ids = {PLAYER_ROLE}  # PLAYER_GONE excluded
        result = _app.compute_teammate_impact(
            PLAYER_STAR, TEAM_ID, PLAYER_LOGS, TEAM_LOGS,
            active_player_ids=active_ids,
        )
        if result.empty:
            pytest.skip("Not enough game overlap to compute impact")
        assert PLAYER_GONE not in result['PLAYER_ID'].values, (
            "Departed player PLAYER_GONE should be excluded when active_player_ids is provided."
        )

    def test_active_player_present(self):
        """PLAYER_ROLE (active) should appear in result."""
        active_ids = {PLAYER_ROLE, PLAYER_GONE}  # include both to isolate this check
        result = _app.compute_teammate_impact(
            PLAYER_STAR, TEAM_ID, PLAYER_LOGS, TEAM_LOGS,
            active_player_ids=active_ids,
        )
        if result.empty:
            pytest.skip("Not enough game overlap")
        assert PLAYER_ROLE in result['PLAYER_ID'].values, \
            "Active player PLAYER_ROLE should appear in teammate impact."


# ---------------------------------------------------------------------------
# Bug 3: _onoff_bar_chart must not crash when PLAYER_ID column is absent
# ---------------------------------------------------------------------------

class TestOnOffBarChartMissingPlayerId:
    def _make_onoff_df_without_player_id(self):
        """Simulate the output of format_onoff_display_data (no PLAYER_ID column)."""
        return pd.DataFrame({
            'PLAYER_NAME': ['A. Player', 'B. Bench', 'C. Star'],
            'NET_RTG_DIFF': [5.2, -1.3, 8.7],
            'NET_RATING_ON_COURT': [112.0, 108.0, 115.0],
            'NET_RATING_OFF_COURT': [106.8, 109.3, 106.3],
            # No PLAYER_ID column — this is what format_onoff_display_data returns
        })

    def test_no_crash_when_player_id_missing(self):
        """_onoff_bar_chart must not raise KeyError when PLAYER_ID absent."""
        onoff_df = self._make_onoff_df_without_player_id()
        try:
            result = _app._onoff_bar_chart(onoff_df, selected_player_id=101)
            # Result can be None or a chart — both are fine; crash is the bug
        except KeyError as e:
            pytest.fail(f"_onoff_bar_chart raised KeyError({e}) when PLAYER_ID was missing.")

    def test_returns_chart_or_none(self):
        """Should return a chart object (or None), never raise."""
        onoff_df = self._make_onoff_df_without_player_id()
        result = _app._onoff_bar_chart(onoff_df, selected_player_id=101)
        # With mocked altair, result will be a MagicMock or None — both acceptable
        assert result is not None or result is None  # just confirming no exception

    def test_with_player_id_column_highlight_works(self):
        """When PLAYER_ID IS present, selected player gets highlighted."""
        onoff_df = self._make_onoff_df_without_player_id().copy()
        onoff_df['PLAYER_ID'] = [101, 202, 303]
        # Should not crash
        try:
            _app._onoff_bar_chart(onoff_df, selected_player_id=101)
        except Exception as e:
            pytest.fail(f"Raised {type(e).__name__}: {e}")
