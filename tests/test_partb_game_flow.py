"""
Part B #8 — scoring-run & game-volatility profile (per game, from reconstructed running score).
Gate: the reconstructed final score must equal the box (team_game_logs PTS); runs/lead-changes sane.
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
def test_reconstructed_final_score_matches_box():
    c = _client()
    gid = (c.table("team_game_logs").select("game_id")
           .eq("season", SEASON).eq("season_type", STYPE).eq("team_id", WOLVES)
           .limit(1).execute().data[0]["game_id"])
    both = c.table("team_game_logs").select("stats").eq("game_id", gid).execute().data
    box_total = sum(int(r["stats"]["PTS"]) for r in both)

    flow = c.rpc("game_flow", {"p_game_id": gid}).execute().data
    assert flow, f"no game_flow row for {gid}"
    f = flow[0]
    assert f["final_home"] + f["final_away"] == box_total, \
        f"reconstructed {f['final_home']}+{f['final_away']} != box {box_total}"
    # a real NBA game has at least one run and non-negative lead changes
    assert f["largest_home_run"] > 0 and f["largest_away_run"] > 0
    assert f["lead_changes"] is not None and f["lead_changes"] >= 0
    assert f["secs_home_led"] is not None and f["secs_away_led"] is not None
