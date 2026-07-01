"""
Part B Phase-1 (Light) derived views — intent tests. Validate against the official season tables
they derive from. Skip cleanly if Supabase creds/network are unavailable.

  v_player_usage_efficiency  (#9 usage-efficiency quadrant, season grain)
  v_team_playtype_profile    (#11 matchup-exploit finder source)
  v_passing_connections      (#6 passing-network connection strength)
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEASON, STYPE = "2024-25", "Regular Season"


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
def test_usage_efficiency_quadrant_logic():
    """Every 'star' row must actually be high-usage AND high-efficiency (encodes the quadrant rule,
    so the test fails if the thresholds/labels drift)."""
    c = _client()
    rows = (c.table("v_player_usage_efficiency").select("usg_pct,ts_pct,quadrant")
            .eq("season", SEASON).eq("season_type", STYPE).execute().data)
    assert rows, "no rows from v_player_usage_efficiency"
    for r in rows:
        if r["quadrant"] and r["quadrant"].startswith("star"):
            assert r["usg_pct"] >= 0.25 and r["ts_pct"] >= 0.58, f"mislabeled star: {r}"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_team_playtype_profile_has_both_groupings():
    """Each team must expose both offensive and defensive play-type rows (the finder joins them)."""
    c = _client()
    rows = (c.table("v_team_playtype_profile").select("team_id,type_grouping,play_type,ppp")
            .eq("season", SEASON).eq("season_type", STYPE).execute().data)
    assert rows, "no rows from v_team_playtype_profile"
    groupings = {r["type_grouping"] for r in rows}
    assert {"offensive", "defensive"} <= groupings, f"missing a grouping: {groupings}"
    assert all(r["ppp"] is not None for r in rows[:50]), "null PPP leaked into profile"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_passing_connection_lift_is_consistent():
    """fg_pct_lift must equal off-pass FG% minus the receiver's baseline FG% (the chemistry signal),
    wherever a baseline exists."""
    c = _client()
    rows = (c.table("v_passing_connections")
            .select("receiver_fg_pct_off_pass,receiver_base_fg_pct,fg_pct_lift,passes")
            .eq("season", SEASON).eq("season_type", STYPE).limit(500).execute().data)
    assert rows, "no rows from v_passing_connections"
    checked = 0
    for r in rows:
        if r["receiver_base_fg_pct"] is not None and r["receiver_fg_pct_off_pass"] is not None:
            assert abs(r["fg_pct_lift"] - (r["receiver_fg_pct_off_pass"] - r["receiver_base_fg_pct"])) < 1e-6
            checked += 1
    assert checked > 0, "no connections had a receiver baseline to check"
