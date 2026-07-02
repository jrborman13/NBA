"""
Weight-search harness for the hexagon axes. Imports the referee (hexagon_weight_backtest) — does
NOT modify it. For each axis: grid-searches {sub_metric: weight} on the TRAIN seasons (partial
Spearman vs the frozen outcome), evaluates the TRAIN-best on the held-out TEST seasons, and prints
it against the three baselines. Also prints top-15 leaderboards for the face-validity gate.

No test-season peeking: the winning weighting is chosen on TRAIN only; TEST is reported once.
Run:  venv311/bin/python analysis/hexagon_weight_search.py [axis]
"""
from __future__ import annotations
import sys
from itertools import product
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
import hexagon_weight_backtest as ref

AXES = ("finishing", "shooting", "playmaking", "defending", "rebounding", "gravity")
GRID = (0, 1, 2)          # relative weights per sub-metric (0 = drop). scale-invariant → 0/1/2 is plenty.
LB_SEASON = "2024-25"     # recent, complete season for leaderboards


def _names(client):
    out = {}
    for r in ref._page(client, "v_player_usage_efficiency", "player_id,player_name"):
        out[r["player_id"]] = r["player_name"]
    return out


def search_axis(axis, data, train=ref.DEFAULT_TRAIN, test=ref.DEFAULT_TEST, grid=GRID):
    """Grid-search integer weights over the axis universe on TRAIN partial; return best + baselines."""
    universe = data["axis_submetrics"].get(axis, ref.AXIS_SUBMETRICS_FALLBACK[axis])
    # fail loud if a universe sub-metric isn't a real grade column
    sample = next(iter(data["grades"].values()))
    missing = [s for s in universe if s not in sample]
    if missing:
        raise RuntimeError(f"FAIL LOUD: axis {axis} universe cols missing from grades: {missing}")

    best = None
    combos = 0
    for combo in product(grid, repeat=len(universe)):
        if not any(combo):
            continue
        w = {sm: c for sm, c in zip(universe, combo) if c}
        combos += 1
        r = ref.grade_weights(axis, w, data=data, seasons=train)
        score = r["partial"]
        if score is None or not np.isfinite(score):
            continue
        if best is None or score > best["train_partial"]:
            best = {"weights": w, "train_partial": score, "train_n": r["n"]}
    # evaluate TRAIN-best on TEST
    te = ref.grade_weights(axis, best["weights"], data=data, seasons=test)
    best.update(test_partial=te["partial"], test_spearman=te["spearman"], test_p=te["partial_p"], test_n=te["n"])
    return best, combos


def leaderboard(axis, weights, data, season=LB_SEASON, names=None, top=15):
    rows = []
    for (pid, s), row in data["grades"].items():
        if s != season:
            continue
        g = ref._axis_grade(row, weights)
        if g is not None:
            rows.append((g, pid, row.get("off_poss_on")))
    rows.sort(reverse=True)
    out = []
    for g, pid, op in rows[:top]:
        out.append(f"{(names or {}).get(pid, pid)} ({int(g)})")
    return out


def report(axis, data, names):
    test = ref.DEFAULT_TEST
    subs = data["axis_submetrics"].get(axis, ref.AXIS_SUBMETRICS_FALLBACK[axis])
    cur = data["current_weights"].get(axis, ref._equal_weights(subs))
    cur_r = ref.grade_weights(axis, cur, data=data, seasons=test)
    eq_r = ref.grade_weights(axis, ref._equal_weights(subs), data=data, seasons=test)
    bs = ref.best_single(axis, data, seasons=test)
    best, combos = search_axis(axis, data)

    print("\n" + "=" * 84)
    print(f"AXIS {axis.upper()}  outcome={cur_r['outcome']}  temporal={cur_r['temporal']}  "
          f"(searched {combos} weightings on TRAIN)")
    print(f"  current_weights : TEST partial {cur_r['partial']:+.3f}  (n={cur_r['n']})  {cur}")
    print(f"  equal_weight    : TEST partial {eq_r['partial']:+.3f}")
    print(f"  best_single     : TEST partial {bs['partial']:+.3f}  ({bs['label']})")
    print(f"  TRAIN-best      : TRAIN partial {best['train_partial']:+.3f} -> TEST partial "
          f"{best['test_partial']:+.3f}  (p={best['test_p']:.3f}, n={best['test_n']})")
    print(f"      weights = {best['weights']}")
    lift_cur = best["test_partial"] - cur_r["partial"]
    lift_eq = best["test_partial"] - eq_r["partial"]
    beats = (lift_cur > 0) and (lift_eq > 0)
    print(f"  lift vs current {lift_cur:+.3f} | vs equal {lift_eq:+.3f}  -> {'BEATS BOTH' if beats else 'does NOT beat both'}")
    print(f"  leaderboard {LB_SEASON} BEFORE (current): {leaderboard(axis, cur, data, names=names)}")
    print(f"  leaderboard {LB_SEASON} AFTER  (TRAIN-best): {leaderboard(axis, best['weights'], data, names=names)}")
    return {"current": cur_r, "equal": eq_r, "best_single": bs, "search": best, "cur_w": cur, "beats": beats}


# Sub-metrics that are near-duplicates of an axis's frozen outcome (leakage) — excluded from search.
LEAKAGE = {
    "rebounding": ["sc_rate_on_minus_off"],  # offensive 2nd-chance on/off ≈ outcome's reb_oreb_lift half
}


def explore(axis, data, names, exclude=None, k=6, grid=GRID):
    """Top-K TRAIN weightings (excluding leakage cols) with their TEST partial + leaderboard, so a
    face-valid winner can be picked rather than the single TRAIN-max (which tends to overfit one metric)."""
    exclude = set(exclude or LEAKAGE.get(axis, []))
    universe = [s for s in data["axis_submetrics"].get(axis, ref.AXIS_SUBMETRICS_FALLBACK[axis]) if s not in exclude]
    test = ref.DEFAULT_TEST
    subs_all = data["axis_submetrics"].get(axis, ref.AXIS_SUBMETRICS_FALLBACK[axis])
    cur = data["current_weights"].get(axis, ref._equal_weights(subs_all))
    cur_t = ref.grade_weights(axis, cur, data=data, seasons=test)
    eq_t = ref.grade_weights(axis, ref._equal_weights(subs_all), data=data, seasons=test)

    cands = []
    for combo in product(grid, repeat=len(universe)):
        if not any(combo):
            continue
        w = {sm: c for sm, c in zip(universe, combo) if c}
        tr = ref.grade_weights(axis, w, data=data, seasons=ref.DEFAULT_TRAIN)["partial"]
        if tr is None or not np.isfinite(tr):
            continue
        cands.append((tr, w))
    cands.sort(reverse=True, key=lambda t: t[0])

    print("\n" + "=" * 88)
    print(f"AXIS {axis.upper()}  (excluded leakage: {sorted(exclude) or 'none'})  "
          f"outcome={cur_t['outcome']} temporal={cur_t['temporal']}")
    print(f"  BAR (TEST partial): current {cur_t['partial']:+.3f} | equal {eq_t['partial']:+.3f}")
    print(f"  current leaderboard {LB_SEASON}: {leaderboard(axis, cur, data, names=names)}")
    print(f"  --- top {k} TRAIN weightings -> TEST ---")
    seen = set()
    shown = 0
    for tr, w in cands:
        key = tuple(sorted(w.items()))
        if key in seen:
            continue
        seen.add(key)
        te = ref.grade_weights(axis, w, data=data, seasons=test)
        beats = te["partial"] > cur_t["partial"] and te["partial"] > eq_t["partial"]
        print(f"  train {tr:+.3f} -> TEST {te['partial']:+.3f} (p={te['partial_p']:.3f}) "
              f"{'BEATS' if beats else '     '} {w}")
        print(f"        LB: {leaderboard(axis, w, data, names=names, top=12)}")
        shown += 1
        if shown >= k:
            break


def main():
    data = ref.load_data()
    names = _names(ref._client())
    args = [a for a in sys.argv[1:] if a in AXES]
    mode = "explore" if "--explore" in sys.argv else "report"
    axes = args or list(AXES)
    for axis in axes:
        (explore if mode == "explore" else report)(axis, data, names)


if __name__ == "__main__":
    main()
