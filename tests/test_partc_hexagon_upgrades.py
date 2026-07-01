"""
Part C hexagon upgrades — regression + archetype tests.

Three upgrades, all following the proven Defending-axis recipe (real tracking metric becomes
primary, noisy proxy reduced/floored):

  1. SHOOTING split   — catch-&-shoot vs pull-up eFG (cs_efg / pu_efg), volume-floored at
     1.0 FGA/g. The noisy shotmaking_over_exp was floored (jump_fga>=150) and reduced 2->1,
     spotup_ppp floored (>=50 spot-up poss), and the redundant unfloored atb3_pct dropped.
     WHY: before, zero-jumper rim-runners (Dereck Lively II 99, Adem Bona 94, Gafford 93) topped
     the Shooting axis on a handful of efficient jumpers. These tests guard that they no longer do
     and that genuine shooters carry the axis. (cs/pu measure EFFICIENCY, so high-VOLUME pull-up
     stars like SGA/Luka land mid-pack — efficient specialists top it; that is correct by design.)

  2. REBOUNDING contested% — contested_reb_per36 (REB_CONTEST) + reb_chance_pct (REB/REB_CHANCES).
     WHY: raw OREB%/DREB% reward volume; contested%/conversion add a toughness dimension. Leaders
     must be battling bigs (Adams/Drummond/Capela), not perimeter players.

  3. TEAM hexagon — same Defending (rim_stop/three_stop from pt_defend_team), Shooting (cs/pu eFG),
     Rebounding (contest_pct) upgrades + shot-quality-created (open_rate from pt_shot_defender_team).
     WHY: the def "stop" metrics are oriented higher=better and must elevate real rim/perimeter
     defenses (BOS/OKC), not invert.

These would all fail against the pre-migration schema (the cs_efg/pu_efg/contested_reb_per36/...
columns and weights did not exist). DB tests skip cleanly without creds/network.

EXPECTED, not a bug: new sub-metrics are NULL before their data floor (tracking 2013-14+); the
hexagon skips NULLs by design. Hexagon qualifier is off_poss_on >= 1000, pool='all'.
"""
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEASON, STYPE = "2024-25", "Regular Season"

# --- player archetypes ---
SETH_CURRY, STEPH_CURRY = 203552, 201939
LIVELY, BONA, GAFFORD = 1641726, 1641737, 1629655          # zero-jumper rim-runners (regression)
GOBERT, JOKIC = 203497, 203999
DRUMMOND, ADAMS, CAPELA = 203083, 203500, 203991           # contested-rebound bigs
# --- teams ---
BOSTON, OKC = 1610612738, 1610612760                        # elite rim/perimeter defenses 2024-25


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


def _pctile_rows(c):
    """All pool='all', minutes-qualified rows from v_player_axis_pctile for the season."""
    rows = (c.table("v_player_axis_pctile")
            .select("player_id,cs_efg,pu_efg,contested_reb_per36,reb_chance_pct")
            .eq("season", SEASON).eq("season_type", STYPE).eq("pool", "all")
            .gte("off_poss_on", 1000).limit(2000).execute().data)
    assert rows, "no rows from v_player_axis_pctile"
    return {r["player_id"]: r for r in rows}


def _hexagon_rows(c):
    rows = (c.table("v_player_hexagon")
            .select("player_id,finishing,shooting,playmaking,defending,rebounding,gravity")
            .eq("season", SEASON).eq("season_type", STYPE).eq("pool", "all")
            .limit(2000).execute().data)
    assert rows, "no rows from v_player_hexagon"
    return {r["player_id"]: r for r in rows}


# ===========================================================================
# Upgrade 1 — Shooting split
# ===========================================================================
@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_shooting_split_columns_exist():
    """cs_efg / pu_efg must be exposed by the pctile view (the split was actually wired)."""
    c = _client()
    px = _pctile_rows(c)
    sample = next(iter(px.values()))
    assert "cs_efg" in sample and "pu_efg" in sample, "C&S / pull-up split not present in v_player_axis_pctile"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_rim_runners_no_longer_top_shooting_axis():
    """Regression: zero-jumper rim-runners (Lively/Bona/Gafford) topped the Shooting axis before the
    floors/reweight. They must not be in the top 10 now (they were #1/#5/#7)."""
    c = _client()
    hexes = _hexagon_rows(c)
    ranked = sorted((r for r in hexes.values() if r["shooting"] is not None),
                    key=lambda r: r["shooting"], reverse=True)
    top10 = {r["player_id"] for r in ranked[:10]}
    offenders = {LIVELY, BONA, GAFFORD} & top10
    assert not offenders, f"non-shooting rim-runners still top the Shooting axis: {offenders}"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_catch_shoot_efficiency_archetype():
    """A genuine high-efficiency catch-&-shoot specialist (Seth Curry) must rank well above median
    in cs_efg — encodes that the metric measures real catch-&-shoot quality."""
    c = _client()
    px = _pctile_rows(c)
    assert SETH_CURRY in px and px[SETH_CURRY]["cs_efg"] is not None, "Seth Curry missing cs_efg"
    assert float(px[SETH_CURRY]["cs_efg"]) >= 65, f"Seth Curry cs_efg pctile too low: {px[SETH_CURRY]['cs_efg']}"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_non_shooting_center_floored_out_of_cs_pu():
    """A rim-running center (Dereck Lively II) takes < 1 catch-&-shoot / pull-up FGA per game, so
    the volume floor must leave his cs_efg AND pu_efg NULL (skipped by the hexagon)."""
    c = _client()
    px = _pctile_rows(c)
    if LIVELY in px:
        assert px[LIVELY]["cs_efg"] is None, "Lively cs_efg should be NULL (below 1.0 FGA/g floor)"
        assert px[LIVELY]["pu_efg"] is None, "Lively pu_efg should be NULL (below 1.0 FGA/g floor)"


# ===========================================================================
# Upgrade 2 — Rebounding contested%
# ===========================================================================
@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_contested_rebound_leaders_are_bigs():
    """contested_reb_per36 must be led by battling bigs, not guards. Drummond & Adams elite (>=85);
    Stephen Curry (guard) well below (<50). Encodes the toughness dimension's intent."""
    c = _client()
    px = _pctile_rows(c)
    for pid, name in ((DRUMMOND, "Drummond"), (ADAMS, "Adams")):
        assert pid in px and px[pid]["contested_reb_per36"] is not None, f"{name} missing contested_reb_per36"
        assert float(px[pid]["contested_reb_per36"]) >= 85, f"{name} contested pctile too low: {px[pid]['contested_reb_per36']}"
    if STEPH_CURRY in px and px[STEPH_CURRY]["contested_reb_per36"] is not None:
        assert float(px[STEPH_CURRY]["contested_reb_per36"]) < 50, "a guard should not lead contested rebounds"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_rebounding_axis_still_big_dominated():
    """Adding contested% must not break face validity: the top of the Rebounding axis stays bigs.
    Every top-5 rebounder must out-rebound a perimeter star (Stephen Curry)."""
    c = _client()
    hexes = _hexagon_rows(c)
    ranked = sorted((r for r in hexes.values() if r["rebounding"] is not None),
                    key=lambda r: r["rebounding"], reverse=True)
    top5 = ranked[:5]
    curry_reb = hexes.get(STEPH_CURRY, {}).get("rebounding")
    if curry_reb is not None:
        assert all(r["rebounding"] > curry_reb for r in top5), "a perimeter player cracked the top-5 rebounders"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_no_collateral_damage_on_unrelated_axes():
    """Upgrades 1 & 2 touch only Shooting and Rebounding. A star's other four axes must remain
    populated and sane (Jokić: finishing/playmaking/gravity elite; defending mid)."""
    c = _client()
    hexes = _hexagon_rows(c)
    assert JOKIC in hexes, "Jokić missing from hexagon"
    j = hexes[JOKIC]
    assert j["gravity"] is not None and j["gravity"] >= 90, "Jokić gravity should stay elite"
    assert j["playmaking"] is not None and j["playmaking"] >= 80, "Jokić playmaking should stay elite"
    assert j["finishing"] is not None and j["finishing"] >= 70, "Jokić finishing should stay high"
    # Gobert remains a non-shooter (NULL Shooting) — the floors did not invent a shooting grade.
    if GOBERT in hexes:
        assert hexes[GOBERT]["shooting"] is None, "Gobert should have NULL Shooting (no qualifying jump volume)"


# ===========================================================================
# Upgrade 3 — Team hexagon
# ===========================================================================
@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_team_weights_seeded():
    """The six new team sub-metric weights must be in team_axis_weights (config-driven, instant
    read — does not scan shot_event)."""
    c = _client()
    rows = c.table("team_axis_weights").select("axis,sub_metric,weight").execute().data
    have = {(r["axis"], r["sub_metric"]) for r in rows}
    need = {("perimeter", "cs_efg"), ("perimeter", "pu_efg"), ("perimeter", "open_rate"),
            ("perimeter", "three_stop"), ("rim", "rim_stop"), ("rebounding", "contest_pct")}
    missing = need - have
    assert not missing, f"team_axis_weights missing Part C rows: {missing}"


@pytest.mark.skipif(os.getenv("SKIP_DB_TESTS") == "1", reason="DB tests disabled")
def test_team_rim_stop_orientation():
    """rim_stop is oriented higher=better and whitelisted in v_team_axis_long, so the pctile must
    NOT invert it: an elite rim defense (Boston/OKC) must land near the top.
    (v_team_axis_pctile scans the live shot_event view; skip if it exceeds the API timeout.)"""
    c = _client()
    try:
        rows = (c.table("v_team_axis_pctile").select("team_id,pctile")
                .eq("season", SEASON).eq("season_type", STYPE)
                .eq("axis", "rim").eq("side", "def").eq("sub_metric", "rim_stop").execute().data)
    except Exception as e:  # pragma: no cover - live shot_event scan can exceed API timeout
        pytest.skip(f"team pctile (live shot_event scan) unavailable: {e}")
    if not rows:
        pytest.skip("rim_stop pctile not returned (team views may be unmaterialized/slow)")
    by_team = {r["team_id"]: float(r["pctile"]) for r in rows}
    assert by_team.get(BOSTON, 0) >= 80 or by_team.get(OKC, 0) >= 80, \
        f"elite rim defenses not near top of rim_stop (BOS={by_team.get(BOSTON)}, OKC={by_team.get(OKC)})"
