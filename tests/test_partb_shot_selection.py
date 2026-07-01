"""
Part B #4 — shot-selection vs shot-making (zone-based expected eFG gap).
Gate: a team's actual eFG (from shot_event zones) must reconcile with the official
team_season_stats Advanced EFG_PCT; the league zone baseline must rank rim > mid-range.
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEASON, STYPE = "2024-25", "Regular Season"
WOLVES = 1610612750


def _client():
    sys.path.insert(0, str(REPO / "combined-app" / "player_app"))
    try:
        from supabase_config import get_supabase_client
    except Exception as e:  # pragma: no cover
        pytest.skip(f"supabase client unavailable: {e}")
    c = get_supabase_client()
    if c is None:
        pytest.skip("Supabase not configured")
    return c


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_actual_efg_reconciles_with_official():
    c = _client()
    row = (c.table("v_team_shot_selection").select("actual_efg,expected_efg,shotmaking_gap")
           .eq("season", SEASON).eq("season_type", STYPE).eq("team_id", WOLVES).execute().data)
    assert row, "no shot-selection row for the team"
    actual = float(row[0]["actual_efg"])
    official = (c.table("team_season_stats").select("stats")
                .eq("season", SEASON).eq("season_type", STYPE).eq("team_id", WOLVES)
                .eq("measure_type", "Advanced").execute().data)
    assert official, "no official Advanced row"
    off_efg = float(official[0]["stats"]["EFG_PCT"])
    assert abs(actual - off_efg) < 0.01, f"derived eFG {actual:.3f} vs official {off_efg:.3f}"
    # gap must be internally consistent: actual - expected
    assert abs(float(row[0]["shotmaking_gap"]) - (actual - float(row[0]["expected_efg"]))) < 1e-3


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_league_zone_baseline_rim_over_midrange():
    c = _client()
    rows = (c.table("mv_league_zone_efg").select("shot_zone,league_efg")
            .eq("season", SEASON).eq("season_type", STYPE).execute().data)
    z = {r["shot_zone"]: float(r["league_efg"]) for r in rows}
    assert "Restricted Area" in z and "Mid-Range" in z, f"zones present: {list(z)}"
    assert z["Restricted Area"] > z["Mid-Range"], f"rim {z['Restricted Area']} !> midrange {z['Mid-Range']}"
