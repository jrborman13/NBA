"""
Part B #5 — self-creation index (assisted vs unassisted), no assist_person_id needed: a made FG is
assisted iff its description carries "(... N AST)". Gate: on-ball creators self-create far more than
play-finishers, and made_fg reconciles to box FGM.
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEASON, STYPE = "2024-25", "Regular Season"
LUKA = 1629029       # on-ball creator -> high unassisted rate
GOBERT = 203497      # rim-running finisher -> low unassisted rate


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


def _row(c, pid):
    r = (c.table("v_player_self_creation").select("made_fg,unassisted_rate")
         .eq("season", SEASON).eq("season_type", STYPE).eq("player_id", pid).execute().data)
    assert r, f"no self-creation row for {pid}"
    return r[0]


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_creator_self_creates_more_than_finisher():
    c = _client()
    luka = float(_row(c, LUKA)["unassisted_rate"])
    gobert = float(_row(c, GOBERT)["unassisted_rate"])
    # creator self-creates most makes; rim-running finisher self-creates few (some putbacks/post-ups
    # push a center to ~0.3, so the meaningful signal is the large GAP, not an absolute finisher floor)
    assert luka > 0.45, f"Luka unassisted rate unexpectedly low: {luka}"
    assert gobert < 0.35, f"Gobert unassisted rate unexpectedly high: {gobert}"
    assert luka > gobert + 0.3, f"creator/finisher gap too small: {luka} vs {gobert}"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_made_fg_reconciles_to_box():
    c = _client()
    made = int(_row(c, LUKA)["made_fg"])
    box = (c.table("player_game_logs").select("stats")
           .eq("season", SEASON).eq("season_type", STYPE).eq("player_id", LUKA).execute().data)
    box_fgm = sum(int(g["stats"]["FGM"]) for g in box)
    assert abs(made - box_fgm) <= max(5, 0.02 * box_fgm), f"made_fg {made} vs box FGM {box_fgm}"
