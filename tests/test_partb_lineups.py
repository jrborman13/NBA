"""
Part B Heavy (#2 staggering, #7 bench tiers, #3 clutch) — built on possession_lineup.
Validated against the Denver 2024-25 "Jokić bench" story, which is well-documented league-wide.
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEASON, STYPE = "2024-25", "Regular Season"
DEN = 1610612743
JOKIC, MURRAY = 203999, 1627750


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
def test_staggering_both_on_beats_both_off():
    """#2: a real star duo's both-on net rating must beat both-off, and the 4 states partition all
    the team's possessions (reconciliation)."""
    c = _client()
    rows = c.rpc("staggering_splits", {"p_team": DEN, "p_a": JOKIC, "p_b": MURRAY,
                 "p_season": SEASON, "p_season_type": STYPE}).execute().data
    by = {r["state"]: r for r in rows}
    assert "both on" in by and "both off" in by
    assert float(by["both on"]["net_rtg"]) > float(by["both off"]["net_rtg"]) + 10, by
    # reconcile: states cover the team's full offensive-possession count
    total_off = sum(r["off_poss"] for r in rows)
    poss = c.table("possession").select("game_id", count="exact").eq("season", SEASON)\
        .eq("season_type", STYPE).eq("off_team_id", DEN).limit(1).execute()
    assert abs(total_off - poss.count) <= 50, f"staggering off_poss {total_off} vs possessions {poss.count}"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_bench_tiers_monotonic_ish():
    """#7: the full starting five (5 starters) must clearly outrate the all-bench unit (0 starters)."""
    c = _client()
    rows = c.rpc("team_lineup_tiers", {"p_team": DEN, "p_season": SEASON, "p_season_type": STYPE}).execute().data
    by = {r["starters_on"]: r for r in rows}
    assert 5 in by and 0 in by
    assert float(by[5]["net_rtg"]) > float(by[0]["net_rtg"]) + 10, by


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_clutch_volume_and_top_lineup_sane():
    """#3: total clutch possessions land in a believable season band, and the most-used clutch
    lineup includes the team's stars (closing five)."""
    c = _client()
    rows = c.rpc("clutch_lineups", {"p_team": DEN, "p_season": SEASON, "p_season_type": STYPE,
                 "p_secs": 300, "p_margin": 5}).execute().data
    assert rows, "no clutch lineups"
    total = sum(r["off_poss"] + r["def_poss"] for r in rows)
    assert 150 <= total <= 900, f"implausible clutch possession total: {total}"
    top = rows[0]  # ordered by possessions desc
    assert JOKIC in top["lineup"] and MURRAY in top["lineup"], f"stars not in top clutch lineup: {top}"
