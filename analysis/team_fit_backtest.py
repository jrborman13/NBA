"""
Team-fit BACKTEST harness — the referee for all later fit work.

This module contains NO fit-scoring logic. It only *grades* fit scores. A "fit score" is any
callable ``fit_score(player_id, from_season, to_team) -> float | None`` that ranks how well a
player fits a team. The harness measures whether such a score predicts what actually happened
after real team changes, relative to two baselines.

Pieces (each maps to a success criterion):
  1. COHORT      — players who changed primary team between consecutive seasons with >=500 on-court
                   offensive possessions in both seasons. SQL view ``v_team_fit_cohort``.
  2. OUTCOMES    — post-move deltas: on/off net (mv_player_onoff.net_swing) and TS%
                   (v_player_usage_efficiency.ts_pct), with age + prior-season minutes as controls.
                   SQL view ``v_team_fit_outcomes``.
  3. REPORT      — ``score_report(fit_score, ...)``: Spearman rank correlation of the score vs the
                   outcome, the partial correlation controlling for age + prior minutes, and the
                   LIFT vs two baselines.
  4. BASELINES   — (a) good player x good team = player prior on/off net x to-team prior NetRtg;
                   (b) style-similarity-only = cosine of player vs to-team offensive play-type mix.
                   ``print_the_bar()`` runs the report on both and prints the numbers every later
                   fit score must beat.

Data sources are all tables / matviews / scalar-jsonb views — NONE scan ``shot_event`` — so no
materialization was required (unlike the hexagons). Run directly:  ``python analysis/team_fit_backtest.py``
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, pearsonr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "combined-app" / "player_app"))

# Offensive Synergy play-types, fixed order = the style fingerprint dimensions.
PLAYTYPES = ["Cut", "Handoff", "Isolation", "Misc", "OffRebound", "OffScreen",
             "Postup", "PRBallHandler", "PRRollman", "Spotup", "Transition"]

# on/off coverage is 2021-22+, so these are the only seasons the backtest can use. Fail loud if any
# expected from-season is missing from the cohort (guards against silent upstream data gaps).
EXPECTED_FROM_SEASONS = {"2021-22", "2022-23", "2023-24", "2024-25"}


def _client():
    from supabase_config import get_supabase_client
    c = get_supabase_client()
    if c is None:
        raise RuntimeError("Supabase not configured (SUPABASE_URL / SUPABASE_KEY in repo-root .env)")
    return c


def _page(client, table, select="*", filters=None):
    """Pull every row of a view/table past PostgREST's 1000-row cap."""
    out, start = [], 0
    while True:
        q = client.table(table).select(select)
        for col, val in (filters or {}):
            q = q.eq(col, val)
        data = q.range(start, start + 999).execute().data
        if not data:
            break
        out.extend(data)
        if len(data) < 1000:
            break
        start += 1000
    return out


# ---------------------------------------------------------------------------
# Load the backtest data
# ---------------------------------------------------------------------------
def load_data():
    c = _client()

    # materialized snapshot of v_team_fit_outcomes (the live view is too slow for the PostgREST
    # timeout — see module docstring / SUPABASE_DERIVED_OBJECTS notes). Rebuild with:
    #   CREATE TABLE team_fit_outcomes AS SELECT * FROM v_team_fit_outcomes;  (when seasons update)
    outcomes = _page(c, "team_fit_outcomes")
    if not outcomes:
        raise RuntimeError("team_fit_outcomes returned no rows — backtest table missing? "
                           "Rebuild: CREATE TABLE team_fit_outcomes AS SELECT * FROM v_team_fit_outcomes;")

    have_seasons = {r["from_season"] for r in outcomes}
    missing = EXPECTED_FROM_SEASONS - have_seasons
    if missing:
        raise RuntimeError(f"FAIL LOUD: cohort missing expected from-seasons {sorted(missing)} "
                           f"(have {sorted(have_seasons)}). on/off coverage may have regressed.")

    names = {r["player_id"]: r["player_name"]
             for r in _page(c, "v_player_usage_efficiency", "player_id,player_name")}

    netrtg = {(r["team_id"], r["season"]): r["net_rtg"]
              for r in _page(c, "v_team_netrtg", "team_id,season,season_type,net_rtg")
              if r["season_type"] == "Regular Season" and r["net_rtg"] is not None}

    # offensive play-type POSS per (entity_type, entity_id, season); normalize to frequency here.
    poss: dict = {}
    for r in _page(c, "v_synergy_off_freq",
                   "entity_type,entity_id,season,season_type,play_type,poss"):
        if r["season_type"] != "Regular Season" or r["poss"] is None:
            continue
        key = (r["entity_type"], r["entity_id"], r["season"])
        poss.setdefault(key, {})[r["play_type"]] = float(r["poss"])

    def vector(entity_type, entity_id, season):
        d = poss.get((entity_type, entity_id, season))
        if not d:
            return None
        v = np.array([d.get(pt, 0.0) for pt in PLAYTYPES])
        total = v.sum()
        return None if total == 0 else v / total

    return outcomes, names, netrtg, vector


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def _residualize(rank_target, control_ranks):
    """Regress rank_target on control ranks (+ intercept); return residuals."""
    X = np.column_stack([np.ones_like(rank_target)] + control_ranks)
    beta, *_ = np.linalg.lstsq(X, rank_target, rcond=None)
    return rank_target - X @ beta


def partial_spearman(x, y, controls):
    """Spearman correlation of x vs y after removing the (rank) controls from both. Returns (r, p, n)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ctrl = [np.asarray(c, float) for c in controls]
    mask = np.isfinite(x) & np.isfinite(y)
    for c in ctrl:
        mask &= np.isfinite(c)
    if mask.sum() < 5:
        return float("nan"), float("nan"), int(mask.sum())
    rx, ry = rankdata(x[mask]), rankdata(y[mask])
    rc = [rankdata(c[mask]) for c in ctrl]
    res_x, res_y = _residualize(rx, rc), _residualize(ry, rc)
    r, p = pearsonr(res_x, res_y)
    return r, p, int(mask.sum())


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 5:
        return float("nan"), int(mask.sum())
    r, _ = pearsonr(rankdata(x[mask]), rankdata(y[mask]))
    return r, int(mask.sum())


# ---------------------------------------------------------------------------
# Baselines (the bar). Each is a fit_score(player, from_season, to_team) callable.
# ---------------------------------------------------------------------------
def make_baselines(outcomes, netrtg, vector):
    from_net = {(r["player_id"], r["from_season"], r["to_team"]): r["from_net"] for r in outcomes}

    def good_player_good_team(player, from_season, to_team):
        """(a) player prior on/off net  x  to-team prior NetRtg."""
        pn = from_net.get((player, from_season, to_team))
        tn = netrtg.get((to_team, from_season))
        if pn is None or tn is None:
            return None
        return float(pn) * float(tn)

    def style_similarity(player, from_season, to_team):
        """(b) cosine similarity of player vs to-team offensive play-type mix (pre-move season)."""
        pv = vector("P", player, from_season)
        tv = vector("T", to_team, from_season)
        if pv is None or tv is None:
            return None
        denom = np.linalg.norm(pv) * np.linalg.norm(tv)
        return None if denom == 0 else float(pv @ tv / denom)

    return {"good_player_x_good_team": good_player_good_team, "style_similarity_only": style_similarity}


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------
def score_report(fit_score, outcome_col="delta_net", label="candidate",
                 data=None, baselines=None, controls=("to_age", "prior_min"), verbose=True):
    """Grade ANY fit_score(player, from_season, to_team) callable.

    Reports, on the common set of moves where the candidate + both baselines + the outcome + all
    `controls` are defined: Spearman rank correlation, PARTIAL correlation (controlling the named
    `controls` out of both score and outcome), and the LIFT vs each baseline. Returns a dict.

    `controls` defaults to the Goal-1 set (age, prior minutes). Pass a richer set — e.g.
    ('to_age','prior_min','from_net','dest_netrtg') — to test whether a fit score predicts
    OVER-performance beyond player quality + destination team quality (the baseline expectation).
    """
    if data is None:
        data = load_data()
    outcomes, _names, netrtg, vector = data
    if baselines is None:
        baselines = make_baselines(outcomes, netrtg, vector)

    scorers = {label: fit_score, **baselines}
    rows = []
    for r in outcomes:
        key = (r["player_id"], r["from_season"], r["to_team"])
        s = {name: fn(*key) for name, fn in scorers.items()}
        rows.append((r, s))

    # common evaluation set: outcome present, every control present, every scorer defined
    def ok(r, s):
        return (r[outcome_col] is not None and all(r.get(c) is not None for c in controls)
                and all(v is not None for v in s.values()))
    common = [(r, s) for r, s in rows if ok(r, s)]
    if not common:
        raise RuntimeError("no rows where candidate + baselines + outcome + controls are all defined")

    y = [float(r[outcome_col]) for r, _ in common]
    ctrl = [[float(r[c]) for r, _ in common] for c in controls]

    results = {}
    for name in scorers:
        xs = [float(s[name]) for _, s in common]
        sr, n = spearman(xs, y)
        psr, pp, pn = partial_spearman(xs, y, ctrl)
        results[name] = {"spearman": sr, "partial": psr, "partial_p": pp, "n": pn}

    cand = results[label]
    lift = {bl: cand["spearman"] - results[bl]["spearman"] for bl in baselines}

    if verbose:
        print(f"\n=== score_report: '{label}'  outcome={outcome_col}  n_common={len(common)} ===")
        print(f"{'scorer':<26}{'spearman':>10}{'partial':>10}{'partial_p':>11}")
        for name, m in results.items():
            tag = "  <-- candidate" if name == label else ""
            print(f"{name:<26}{m['spearman']:>10.3f}{m['partial']:>10.3f}{m['partial_p']:>11.3f}{tag}")
        print("lift (candidate spearman - baseline spearman):")
        for bl, lv in lift.items():
            print(f"  vs {bl:<24}{lv:+.3f}")
    return {"results": results, "lift": lift, "n_common": len(common)}


def print_the_bar(data=None):
    """Run the report on both baselines for both outcomes and print THE BAR every later fit score
    must beat. (Each baseline scored as the 'candidate' -> its self-lift is 0 by construction; the
    number that matters is its raw + partial Spearman.)"""
    if data is None:
        data = load_data()
    outcomes, names, netrtg, vector = data
    baselines = make_baselines(outcomes, netrtg, vector)

    n_total = len(outcomes)
    n_valid = sum(1 for r in outcomes if r["delta_net"] is not None)
    trans = {}
    for r in outcomes:
        trans[f"{r['from_season']}->{r['to_season']}"] = trans.get(f"{r['from_season']}->{r['to_season']}", 0) + 1
    print("=" * 74)
    print("TEAM-FIT BACKTEST — THE BAR (baseline numbers every fit score must beat)")
    print("=" * 74)
    print(f"cohort moves: {n_total} ({n_valid} with a non-null on/off-net outcome)")
    print("by transition:", ", ".join(f"{k}:{v}" for k, v in sorted(trans.items())))
    print("controls residualized out of 'partial': to_age, prior_min")
    print("NOTE: 2024-25->2025-26 uses the in-progress current season (>=500 off-poss filter applies).")

    for outcome_col in ("delta_net", "delta_ts"):
        for name, fn in baselines.items():
            score_report(fn, outcome_col=outcome_col, label=name, data=data, baselines=baselines)
    print("\n" + "=" * 74)
    print("Interpretation: a real fit score is worth pursuing only if its Spearman (and especially")
    print("its partial Spearman vs delta_net) clears these baselines by a meaningful margin.")
    print("=" * 74)


if __name__ == "__main__":
    os.environ.setdefault("SKIP_DB_TESTS", "0")
    print_the_bar()
