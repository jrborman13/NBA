"""
Test for assign_position_slots bug:
  When guard-eligible dual-position players (SG/SF, PG/SF, SG/PF) are greedily assigned
  to SF/PF/F slots before G slot is filled, the G slot ends up with no eligible players.

  This was triggered by stacking 3+ ATL Hawks players that included SG/SF type players.

  The test creates a minimal 8-player lineup that reproduces the crash, then verifies
  the fix produces a valid lineup with the G slot filled by a guard.
"""

import sys
import os
import pytest
import pandas as pd

# Add the scripts directory to path so we can import the optimizer
sys.path.insert(0, os.path.dirname(__file__))

from optimize_draftkings_nba_lineup import assign_position_slots


def _make_player(name, position_str, fpts, salary=5000):
    """Build a minimal player dict matching what assign_position_slots expects."""
    pos = position_str.upper()
    is_pg = "PG" in pos
    is_sg = "SG" in pos
    is_sf = "SF" in pos
    is_pf = "PF" in pos
    is_c = "C" in pos or "PF/C" in pos
    return {
        "Player": name,
        "position": position_str,
        "Salary": salary,
        "FPTS": fpts,
        "is_pg": is_pg,
        "is_sg": is_sg,
        "is_sf": is_sf,
        "is_pf": is_pf,
        "is_c": is_c,
        "is_g": is_pg or is_sg,
        "is_f": is_sf or is_pf,
        "is_util": True,
    }


def _make_lineup(*players):
    return pd.DataFrame(list(players))


# ---------------------------------------------------------------------------
# Reproducing test — must FAIL (raise ValueError) before the fix
# ---------------------------------------------------------------------------

def test_guard_consumed_by_sf_slot_raises():
    """
    Lineup where two dual-position SG/SF guards are the highest-FPTS SF-eligible
    players.  After the fix, the greedy algorithm must preserve at least one guard
    for the G slot instead of consuming both guards in SF/F slots.

    8 players:
      Player_PG       PG       FPTS=40
      Player_SG       SG       FPTS=38   <- true guard
      Player_SG_SF_A  SG/SF    FPTS=35   <- guard who is also SF-eligible
      Player_SG_SF_B  SG/SF    FPTS=30   <- guard who is also SF-eligible
      Player_SF       SF       FPTS=25   <- true SF forward
      Player_PF       PF       FPTS=22
      Player_PFC      PF/C     FPTS=20
      Player_PF2      PF       FPTS=18

    After the fix, the SF and F slots must be filled by non-guard players where
    possible (Player_SF for SF, a PF player for F), leaving a guard-eligible
    player available for the G slot.
    """
    lineup = _make_lineup(
        _make_player("Player_PG",      "PG",    fpts=40),
        _make_player("Player_SG",      "SG",    fpts=38),
        _make_player("Player_SG_SF_A", "SG/SF", fpts=35),
        _make_player("Player_SG_SF_B", "SG/SF", fpts=30),
        _make_player("Player_SF",      "SF",    fpts=25),
        _make_player("Player_PF",      "PF",    fpts=22),
        _make_player("Player_PFC",     "PF/C",  fpts=20),
        _make_player("Player_PF2",     "PF",    fpts=18),
    )

    result = assign_position_slots(lineup)

    assert len(result) == 8, "Must have exactly 8 players"
    slots = result["Slot"].tolist()
    expected_slots = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}
    assert set(slots) == expected_slots, f"Expected all 8 slots, got: {slots}"

    # G slot must be filled by a guard-eligible player
    g_player = result[result["Slot"] == "G"].iloc[0]
    assert g_player["is_g"], (
        f"G slot must be guard-eligible, but got {g_player['Player']} ({g_player['position']})"
    )


# ---------------------------------------------------------------------------
# Correctness test — must PASS after the fix
# ---------------------------------------------------------------------------

def test_guard_preserved_for_g_slot():
    """
    Same lineup as above.  After the fix, assign_position_slots must return a
    valid lineup where:
      - Exactly 8 players are assigned
      - All 8 DK slots are filled (PG, SG, SF, PF, C, G, F, UTIL)
      - The G slot contains a guard-eligible player (is_pg or is_sg)
      - No slot is assigned a player who is ineligible for it
    """
    lineup = _make_lineup(
        _make_player("Player_PG",      "PG",    fpts=40),
        _make_player("Player_SG",      "SG",    fpts=38),
        _make_player("Player_SG_SF_A", "SG/SF", fpts=35),
        _make_player("Player_SG_SF_B", "SG/SF", fpts=30),
        _make_player("Player_SF",      "SF",    fpts=25),
        _make_player("Player_PF",      "PF",    fpts=22),
        _make_player("Player_PFC",     "PF/C",  fpts=20),
        _make_player("Player_PF2",     "PF",    fpts=18),
    )

    result = assign_position_slots(lineup)

    assert len(result) == 8, "Must have exactly 8 players"
    slots = result["Slot"].tolist()
    expected_slots = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}
    assert set(slots) == expected_slots, f"Expected all 8 slots, got: {slots}"

    # G slot must be filled by a guard
    g_player = result[result["Slot"] == "G"].iloc[0]
    assert g_player["is_g"], (
        f"G slot must be guard-eligible, but got {g_player['Player']} ({g_player['position']})"
    )

    # PG slot must be PG-eligible
    pg_player = result[result["Slot"] == "PG"].iloc[0]
    assert pg_player["is_pg"], f"PG slot player {pg_player['Player']} is not PG-eligible"

    # SG slot must be SG-eligible
    sg_player = result[result["Slot"] == "SG"].iloc[0]
    assert sg_player["is_sg"], f"SG slot player {sg_player['Player']} is not SG-eligible"

    # SF slot must be SF-eligible
    sf_player = result[result["Slot"] == "SF"].iloc[0]
    assert sf_player["is_sf"], f"SF slot player {sf_player['Player']} is not SF-eligible"

    # PF slot must be PF-eligible
    pf_player = result[result["Slot"] == "PF"].iloc[0]
    assert pf_player["is_pf"], f"PF slot player {pf_player['Player']} is not PF-eligible"

    # C slot must be C-eligible
    c_player = result[result["Slot"] == "C"].iloc[0]
    assert c_player["is_c"], f"C slot player {c_player['Player']} is not C-eligible"

    # F slot must be F-eligible (SF or PF)
    f_player = result[result["Slot"] == "F"].iloc[0]
    assert f_player["is_f"], f"F slot player {f_player['Player']} is not F-eligible"


def test_stack_with_sg_sf_players_no_crash():
    """
    Simulates a realistic 3-team ATL stack scenario with SG/SF dual-position players.
    3 ATL players: PG (Trae Young type), SG/SF, SF/PF
    5 non-ATL: SG, SF, PF, PF/C, PG/SG

    The lineup must be assigned without crashing.
    """
    lineup = _make_lineup(
        _make_player("ATL_PG",     "PG",    fpts=44),   # Trae Young type
        _make_player("ATL_SG_SF",  "SG/SF", fpts=32),   # Dyson Daniels type
        _make_player("ATL_SF_PF",  "SF/PF", fpts=28),   # Jalen Johnson type
        _make_player("NonATL_PG_SG", "PG/SG", fpts=36),
        _make_player("NonATL_SG",  "SG",    fpts=30),
        _make_player("NonATL_PF",  "PF",    fpts=24),
        _make_player("NonATL_C",   "C",     fpts=22),
        _make_player("NonATL_PF2", "PF",    fpts=19),
    )

    result = assign_position_slots(lineup)

    slots = result["Slot"].tolist()
    expected_slots = {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}
    assert set(slots) == expected_slots, f"Expected all 8 slots, got: {slots}"

    g_player = result[result["Slot"] == "G"].iloc[0]
    assert g_player["is_g"], (
        f"G slot must be guard-eligible, but got {g_player['Player']} ({g_player['position']})"
    )


def test_pfc_consumed_by_c_slot_leaves_f_with_only_guards():
    """
    Regression: When the highest-FPTS C-eligible player is a PF/C (also F-eligible),
    the C slot greedily consumes it, leaving the F slot with only guard-eligible
    players. With only 1 guard remaining at that point, _pick_non_guard_first raises.

    Scenario:
      Player_PG      PG       FPTS=40  (guard)
      Player_SG      SG       FPTS=38  (guard)
      Player_SG_SF_A SG/SF    FPTS=35  (guard; only SF-eligible → consumed by SF slot)
      Player_SG_SF_B SG/SF    FPTS=30  (guard; the last remaining guard)
      Player_PF      PF       FPTS=22  (non-guard forward; consumed by PF slot)
      Player_PFC     PF/C     FPTS=28  (non-guard, F-eligible AND C-eligible; high FPTS
                                        causes it to be greedily taken for C slot)
      Player_C1      C        FPTS=20  (C-only, non-F-eligible)
      Player_C2      C        FPTS=18  (C-only, non-F-eligible)

    After PG→SG→SF(SG_SF_A, uses guard)→PF→C(PFC, greedy):
      Remaining: [SG_SF_B(guard/is_f), C1(is_f=False), C2(is_f=False)]
      eligible_f = [SG_SF_B] only  →  all guards, remaining_guards=1  →  crash.

    After the fix (C slot prefers C-only):
      C slot → Player_C1. Remaining: [SG_SF_B, PFC, C2]
      F slot → PFC (non-guard, is_f=True). G slot → SG_SF_B. UTIL → C2.
    """
    lineup = _make_lineup(
        _make_player("Player_PG",      "PG",    fpts=40),
        _make_player("Player_SG",      "SG",    fpts=38),
        _make_player("Player_SG_SF_A", "SG/SF", fpts=35),
        _make_player("Player_SG_SF_B", "SG/SF", fpts=30),
        _make_player("Player_PF",      "PF",    fpts=22),
        _make_player("Player_PFC",     "PF/C",  fpts=28),  # high FPTS → greedy C trap
        _make_player("Player_C1",      "C",     fpts=20),
        _make_player("Player_C2",      "C",     fpts=18),
    )

    result = assign_position_slots(lineup)

    assert len(result) == 8
    assert set(result["Slot"].tolist()) == {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}

    g_player = result[result["Slot"] == "G"].iloc[0]
    assert g_player["is_g"], f"G slot must be guard-eligible: {g_player['Player']}"

    f_player = result[result["Slot"] == "F"].iloc[0]
    assert f_player["is_f"], f"F slot must be F-eligible: {f_player['Player']}"

    c_player = result[result["Slot"] == "C"].iloc[0]
    assert c_player["is_c"], f"C slot must be C-eligible: {c_player['Player']}"


def test_five_guards_with_dual_position_forwards():
    """
    Stress test: 5 guard-eligible players compete for PG/SG/G slots, while dual-position
    forwards (SF/PF, PF/C) create additional competition for the F slot.

    The greedy assignment order (PG→SG→SF→PF→C→F→G→UTIL) is prone to consuming
    dual-position players in the wrong slots. Bipartite matching finds the globally
    optimal valid assignment regardless of order.

    8 players:
      Player_PG      PG      FPTS=44  (pure PG guard)
      Player_SG      SG      FPTS=40  (pure SG guard)
      Player_PG_SG   PG/SG   FPTS=36  (dual PG/SG guard — extra guard for G slot)
      Player_SG_SF   SG/SF   FPTS=32  (guard who is also SF-eligible)
      Player_SF_PF   SF/PF   FPTS=28  (non-guard dual forward)
      Player_PF      PF      FPTS=24  (pure PF)
      Player_PF_C    PF/C    FPTS=20  (forward/center dual)
      Player_C       C       FPTS=16  (pure center)

    A valid assignment exists, e.g.:
      PG→Player_PG, SG→Player_SG, G→Player_PG_SG, SF→Player_SG_SF,
      PF→Player_PF, F→Player_SF_PF, C→Player_PF_C (or Player_C), UTIL→remaining
    """
    lineup = _make_lineup(
        _make_player("Player_PG",    "PG",    fpts=44),
        _make_player("Player_SG",    "SG",    fpts=40),
        _make_player("Player_PG_SG", "PG/SG", fpts=36),
        _make_player("Player_SG_SF", "SG/SF", fpts=32),
        _make_player("Player_SF_PF", "SF/PF", fpts=28),
        _make_player("Player_PF",    "PF",    fpts=24),
        _make_player("Player_PF_C",  "PF/C",  fpts=20),
        _make_player("Player_C",     "C",     fpts=16),
    )

    result = assign_position_slots(lineup)

    assert len(result) == 8
    assert set(result["Slot"].tolist()) == {"PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"}

    g_player = result[result["Slot"] == "G"].iloc[0]
    assert g_player["is_g"], f"G slot must be guard-eligible: {g_player['Player']}"

    f_player = result[result["Slot"] == "F"].iloc[0]
    assert f_player["is_f"], f"F slot must be F-eligible: {f_player['Player']}"

    sf_player = result[result["Slot"] == "SF"].iloc[0]
    assert sf_player["is_sf"], f"SF slot must be SF-eligible: {sf_player['Player']}"

    pf_player = result[result["Slot"] == "PF"].iloc[0]
    assert pf_player["is_pf"], f"PF slot must be PF-eligible: {pf_player['Player']}"

    c_player = result[result["Slot"] == "C"].iloc[0]
    assert c_player["is_c"], f"C slot must be C-eligible: {c_player['Player']}"

    pg_player = result[result["Slot"] == "PG"].iloc[0]
    assert pg_player["is_pg"], f"PG slot must be PG-eligible: {pg_player['Player']}"

    sg_player = result[result["Slot"] == "SG"].iloc[0]
    assert sg_player["is_sg"], f"SG slot must be SG-eligible: {sg_player['Player']}"


if __name__ == "__main__":
    # Quick manual run to confirm which tests pass/fail before/after fix
    import traceback

    tests = [
        ("test_guard_consumed_by_sf_slot_raises (should raise before fix)", test_guard_consumed_by_sf_slot_raises),
        ("test_guard_preserved_for_g_slot (should pass after fix)", test_guard_preserved_for_g_slot),
        ("test_stack_with_sg_sf_players_no_crash (should pass after fix)", test_stack_with_sg_sf_players_no_crash),
        ("test_pfc_consumed_by_c_slot_leaves_f_with_only_guards (new bug)", test_pfc_consumed_by_c_slot_leaves_f_with_only_guards),
        ("test_all_forwards_consumed_before_f_slot (new bug)", test_all_forwards_consumed_before_f_slot),
    ]

    for name, fn in tests:
        try:
            fn()
            print(f"  PASS: {name}")
        except Exception as e:
            print(f"  FAIL: {name}")
            print(f"        {type(e).__name__}: {e}")
