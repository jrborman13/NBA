"""
Phase 1 — spec-lock + power analysis + reachability verdict (cheap; no new data).

Pre-registers ONE official test and reports THAT number as the headline (no sweep-best framing):
  outcome   = delta_net (Δ on/off-net from mv_player_onoff)
  score     = Path B need_fill
  w         = 1.0  (where both paths peak)
  controls  = age, prior_min, from_net, dest_netrtg  (the over-performance partial)

Then computes, from the observed point estimate r:
  (a) n to cross p<0.05 at the point estimate (the r becomes significant)
  (b) n for 80% power at alpha=.05 (you'd actually detect r 80% of the time)
and decides whether (b) is reachable from available NBA history, given the HARD cap that Path B's
fingerprint needs Synergy (2013-14+ only).
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
from scipy import stats

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))
import team_fit_backtest as tfb
import team_fit_pathB as pb

# Available movers per transition (player_oncourt_poss, >=500 off-poss both seasons), from SQL.
MOVERS = {  # transition from_season -> movers
    "2013-14": 107, "2014-15": 110, "2015-16": 105, "2016-17": 109, "2017-18": 104,
    "2018-19": 136, "2019-20": 117, "2020-21": 120,                       # pre-2021 (need proxy)
    "2021-22": 106, "2022-23": 114, "2023-24": 93, "2024-25": 99,         # current (official on/off)
}
SYNERGY_FLOOR = "2013-14"   # Path B fingerprint cannot go below this (no Synergy before)


def n_for_p05(r, k):
    """Smallest n at which a partial correlation r (k controls, df=n-2-k) is significant @ .05 two-sided."""
    for n in range(8, 200000):
        df = n - 2 - k
        if df < 1:
            continue
        t = r * np.sqrt(df / (1 - r * r))
        if 2 * stats.t.sf(abs(t), df) < 0.05:
            return n
    return None


def n_for_power(r, k, power=0.80, alpha=0.05):
    """n for given power via Fisher z (+k for partial controls)."""
    z = np.arctanh(abs(r))
    za, zb = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return int(np.ceil(((za + zb) / z) ** 2 + 3 + k))


def main():
    data = tfb.load_data()
    outcomes, names, netrtg, vector = data
    baselines = tfb.make_baselines(outcomes, netrtg, vector)
    for r in outcomes:
        r["dest_netrtg"] = netrtg.get((r["to_team"], r["from_season"]))
    from_seasons = {r["from_season"] for r in outcomes}

    # ---- LOCKED SPEC (frozen before any expansion) ----
    fp = pb.load_fingerprints(from_seasons | {"2024-25"})
    qual = pb.load_qualified_players(from_seasons | {"2024-25"})
    spaces = {s: pb.SeasonSpace(fp, s, qual[s]) for s in from_seasons}
    make_fit = pb.build_fit(outcomes, spaces)
    CONTROLS = ("to_age", "prior_min", "from_net", "dest_netrtg")
    R = tfb.score_report(make_fit(1.0), outcome_col="delta_net", label="LOCKED",
                         data=data, baselines=baselines, controls=CONTROLS, verbose=False)["results"]
    r = R["LOCKED"]["partial"]; p = R["LOCKED"]["partial_p"]; n = R["LOCKED"]["n"]
    bgp, bsim = R["good_player_x_good_team"]["partial"], R["style_similarity_only"]["partial"]
    k = len(CONTROLS)

    print("=" * 78)
    print("PHASE 1 — LOCKED SPEC (pre-registered, the ONE headline number)")
    print("=" * 78)
    print("spec: outcome=delta_net | Path B need_fill | w=1.0 | partial controls "
          "(age, prior_min, from_net, dest_netrtg)")
    print(f"HEADLINE: partial r = {r:+.3f}   p = {p:.3f}   n = {n}")
    print(f"  beats both baselines: good_player_x_good_team={bgp:+.3f} (lift {r-bgp:+.3f}), "
          f"style_similarity_only={bsim:+.3f} (lift {r-bsim:+.3f})")
    print(f"  -> {'BEATS BOTH' if r>bgp and r>bsim else 'does NOT beat both'} baselines; "
          f"not significant (p>={p:.2f}).")

    print("\n" + "=" * 78)
    print("POWER ANALYSIS  (at the observed point estimate r={:+.3f}, k={} controls)".format(r, k))
    print("=" * 78)
    n_a = n_for_p05(r, k)
    n_b = n_for_power(r, k, 0.80)
    print(f"  (a) n to cross p<0.05 at the point estimate : {n_a}")
    print(f"  (b) n for 80% power at alpha=.05            : {n_b}")
    print(f"  current n = {n}")

    print("\n" + "=" * 78)
    print("REACHABILITY  (can we get n_b movers from available history?)")
    print("=" * 78)
    pre = {s: m for s, m in MOVERS.items() if s < "2021-22" and s >= SYNERGY_FLOOR}
    raw_total = sum(MOVERS.values())                      # all transitions incl. current
    pre_total = sum(pre.values())
    retention = n / sum(MOVERS[s] for s in from_seasons)  # current common/raw
    expanded_common = int(raw_total * retention)
    print(f"  retention (common controlled / raw movers, current) = {retention:.2f}")
    print(f"  pre-2021 movers usable for Path B (>= Synergy floor {SYNERGY_FLOOR}): "
          f"{pre_total}  ({', '.join(f'{s}:{m}' for s,m in pre.items())})")
    print(f"  MAX expandable raw movers (Synergy floor {SYNERGY_FLOOR} -> current) = {raw_total}")
    print(f"  -> MAX expandable COMMON n ~= {expanded_common}  (vs {n_b} needed for 80% power)")
    print(f"  HARD CAP: Path B fingerprint needs Synergy, so cannot go below {SYNERGY_FLOOR}.")
    print(f"  NOTE: pre-2021 outcome would be a PROXY (no official on/off) -> attenuates r -> raises")
    print(f"        the real n_b above {n_b}; and ~{pre_total}/{raw_total} of the sample is proxy-based.")

    reachable_80 = expanded_common >= n_b
    print("\n" + "-" * 78)
    print(f"VERDICT (80% power): {'REACHABLE' if reachable_80 else 'NOT-REACHABLE'}")
    if not reachable_80:
        print(f"  Max clean+proxy sample (~{expanded_common}) is BELOW the ~{n_b} needed for 80% power,")
        print(f"  and proxy attenuation pushes the requirement even higher. p<0.05 at the point estimate")
        print(f"  (~{n_a}) is reachable in count, but that is NOT the same as 80% power to OBSERVE it.")
        print(f"  => Do NOT invest in the proxy + cohort expansion to chase significance.")
    else:
        print(f"  Count suffices; the decision now hinges on PROXY QUALITY (Phase 2 gate).")
    print("=" * 78)
    return dict(r=r, p=p, n=n, n_a=n_a, n_b=n_b, expanded_common=expanded_common, reachable=reachable_80)


if __name__ == "__main__":
    main()
