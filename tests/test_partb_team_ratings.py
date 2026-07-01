"""
Part B Medium — per-game team ratings view (powers #1 rolling NetRtg and #10 rest splits).
Key gate (per SUPABASE_STAT_IDEAS.md): season-aggregated derived rating must reconcile with the
official team_season_stats Advanced NET_RATING — else the custom-window version isn't trustworthy.
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEASON, STYPE = "2024-25", "Regular Season"
WOLVES = 1610612750

REST_BUCKETS = {"opener", "B2B (0 days rest)", "1 day rest", "2+ days rest"}


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
def test_season_rating_reconciles_with_official():
    """Aggregate one team's per-game ratings to the full season; net rating must match the official
    team_season_stats NET_RATING within ~2.0 (the 0.44-FTA possession estimate's tolerance)."""
    c = _client()
    rows = (c.table("v_team_game_ratings")
            .select("pts_for,pts_against,off_poss,def_poss")
            .eq("team_id", WOLVES).eq("season", SEASON).eq("season_type", STYPE).execute().data)
    assert len(rows) > 70, f"expected a full season of games, got {len(rows)}"
    off = 100 * sum(r["pts_for"] for r in rows) / sum(r["off_poss"] for r in rows)
    deff = 100 * sum(r["pts_against"] for r in rows) / sum(r["def_poss"] for r in rows)
    derived_net = off - deff

    adv = (c.table("player_season_stats")  # team net via team_season_stats Advanced
           .select("stats").limit(1).execute())  # placeholder guard if table empty
    off_row = (c.table("team_season_stats").select("stats")
               .eq("season", SEASON).eq("season_type", STYPE).eq("team_id", WOLVES)
               .eq("measure_type", "Advanced").execute().data)
    assert off_row, "no official Advanced row for the team"
    official_net = float(off_row[0]["stats"]["NET_RATING"])
    assert abs(derived_net - official_net) < 2.0, \
        f"derived net {derived_net:.1f} vs official {official_net:.1f} (diff {derived_net-official_net:.1f})"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_rest_buckets_valid():
    c = _client()
    rows = (c.table("v_team_game_ratings").select("rest_bucket,gap_days")
            .eq("season", SEASON).eq("season_type", STYPE).limit(800).execute().data)
    assert rows, "no rows"
    buckets = {r["rest_bucket"] for r in rows}
    assert buckets <= REST_BUCKETS, f"unexpected rest bucket: {buckets - REST_BUCKETS}"
    assert "B2B (0 days rest)" in buckets, "no back-to-backs detected"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_rolling_function_returns_window():
    c = _client()
    r = c.rpc("team_rolling_rating",
              {"p_team": WOLVES, "p_season": SEASON, "p_n": 10, "p_season_type": STYPE}).execute().data
    assert r and r[0]["games"] == 10, f"expected 10-game window, got {r}"
    assert r[0]["net_rtg"] is not None
