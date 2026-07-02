"""
Hexagon-weight BACKTEST harness — the referee for all hexagon re-weighting work.

Sibling of ``analysis/team_fit_backtest.py``. This module contains NO weight-tuning logic. It only
*grades* a proposed weighting for a hexagon axis. A "weighting" is a dict ``{sub_metric: weight}``.
The harness measures whether the resulting axis grade (weighted mean of that axis's sub-metric
percentiles, exactly how ``v_player_hexagon`` builds it) predicts that player's real on-court
impact IN THAT DOMAIN, out of sample, relative to baselines.

WHY THIS EXISTS
---------------
Today the hexagon weights in ``hexagon_weights`` are justified by face validity (Wemby tops
Defending, Jokic tops Gravity) — not by any measured notion of impact. This referee turns
"capture impact better" into a number the CLI /goal loop can optimize.

THE ONE RULE THAT MAKES IT HONEST — no leakage
----------------------------------------------
Each axis is graded against a FROZEN outcome that is deliberately NOT one of its sub-metrics, and
the two overlap-prone axes are graded TEMPORALLY (grade in season N -> outcome in season N+1) so a
metric that rhymes with the outcome still has to generalize across seasons. When the CLI is allowed
to add/drop sub-metrics, the outcome column must never be admitted into the candidate pool.

DATA WINDOW
-----------
The impact outcomes come from the possession engine (``v_player_onoff_context``,
``v_player_shot_onoff_context``, ``player_oncourt_shot``), which only covers 2021-22+. So the
referee can only VALIDATE on 2021-22+ even though the grades (``v_player_axis_pctile``) exist
2013-14+. The weights it produces still apply to all seasons (``hexagon_weights`` is global config).

FROZEN PER-AXIS OUTCOMES (all internal, all on-court)
-----------------------------------------------------
  defending   -> DRtg swing (drtg_off - drtg_on): opponent pts/100 suppressed when on court.
                 Independent of blk/stl/rim_stop/deflections/contested2. CONTEMPORANEOUS. clean.
  rebounding  -> TWO-WAY (reb_two_way): per-season z(defensive 2nd-chance suppression,
                 sc_rate_allowed_off-on) + z(offensive OREB-rate on/off lift). Offensive side =
                 team OREB rate with player on vs off (possession_lineup + possession.had_oreb,
                 off_n=5 lineups). Independent of oreb%/dreb%/contested_reb/reb_chance/sc_rate(off).
                 CONTEMPORANEOUS. clean (both sides covered).
  playmaking  -> team shot-making over expectation lift, on vs off:
                 (act_efg_on - exp_efg_on) - (act_efg_off - exp_efg_off). Teammates convert above
                 shot-location expectation when the player is on = good setups/passing. Independent
                 of ast%/ast_pts_created/drive_ast. CONTEMPORANEOUS. mostly clean.
  gravity     -> team shot-location quality lift (exp_efg_on - exp_efg_off). EQUALS its own
                 sub-metric shot_diet_gravity_efg -> graded TEMPORALLY (N -> N+1). overlap-prone.
  finishing   -> player's OWN rim (Restricted Area) scoring value per shot: avg(efg_pts -
                 league_rim_efg) over the player's rim shots (>=50/season). Same domain as
                 rim_fg_pct_over_league -> graded TEMPORALLY (N -> N+1, a persistence test). rim-only.
  shooting    -> player's OWN jump-shot scoring value per shot (Mid-Range + all 3s; excludes
                 floaters + backcourt; >=50 jumpers/season): avg(efg_pts - league_zone_efg).
                 TEMPORAL. Jump-shooting is genuinely noisy year to year -> expect a modest ceiling.

Finishing and shooting now have DISTINCT rim-vs-jumper outcomes built from shot_event.shooter_id
split by zone (staging tables hex_shot_own_stage / hex_oreb_stage; see REBUILD_SQL). The old shared
team-on-court scoring_value outcome is retired.

Run directly:  ``python analysis/hexagon_weight_backtest.py``
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, pearsonr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "combined-app" / "player_app"))

# Impact outcomes are possession-engine derived -> 2021-22+ only. Fail loud if any is missing.
OUTCOME_SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
# Default temporal train/test split (pre-registered — override in the loop, but report the default).
DEFAULT_TRAIN = ("2021-22", "2022-23", "2023-24")
DEFAULT_TEST = ("2024-25", "2025-26")
SEASON_TYPE = "Regular Season"
MIN_OFF_POSS = 1000  # matches the pool='all' minutes qualifier

# Which sub-metrics (columns in v_player_axis_pctile) belong to each axis by default. Loaded live
# from hexagon_weights at runtime so this stays in sync; this literal is only the fallback / the
# universe the CLI may add to or drop from.
AXIS_SUBMETRICS_FALLBACK = {
    "finishing": ["rim_rate", "rim_fg_pct_over_league", "team_rim_freq_lift"],
    "shooting": ["cs_efg", "pu_efg", "shotmaking_over_exp", "spotup_ppp", "atb3_pct"],
    "playmaking": ["ast_pct", "ast_pts_created", "drive_ast"],
    "defending": ["def_rim_stop", "def_pm_stop", "deflections_per36", "contested2_per36",
                  "blk_per100", "stl_per100", "drtg_swing"],
    "rebounding": ["oreb_pct", "dreb_pct", "sc_rate_on_minus_off", "contested_reb_per36",
                   "reb_chance_pct"],
    "gravity": ["shot_diet_gravity_efg", "off_rating_lift", "rim_freq_lift"],
}

# axis -> (outcome_key, temporal?). outcome_key = a column in the hex_weight_outcomes snapshot.
AXIS_OUTCOME = {
    "defending": ("def_drtg_swing", False),
    "rebounding": ("reb_two_way", False),      # z(def 2nd-chance supp) + z(off OREB on/off lift)
    "playmaking": ("play_setup_lift", False),
    "gravity": ("grav_shotqual_lift", True),   # outcome == its own sub-metric -> temporal
    "finishing": ("fin_rim_value", True),      # player OWN rim scoring value -> temporal
    "shooting": ("shoot_jump_value", True),    # player OWN jumper scoring value -> temporal
}

# The frozen outcomes are pre-aggregated per (player_id, season) into the hex_weight_outcomes
# snapshot TABLE (plus two staging tables). Reason: the live on/off + shot_event views are too slow
# to paginate under the PostgREST statement timeout (57014) — same reason team_fit_outcomes was
# materialized. Outcomes DO NOT depend on the hexagon weights, so weight-tuning never invalidates
# them; rebuild only when the possession engine adds a season. Run the whole block via the Supabase
# MCP / a statement_timeout=0 session (per-season shot_event + possession_lineup scans each fit).
REBUILD_SQL = r"""
SET statement_timeout = 0;
-- 1. STAGING: player-OWN shots split rim vs jumper (from shot_event.shooter_id), per season.
DROP TABLE IF EXISTS hex_shot_own_stage;
CREATE TABLE hex_shot_own_stage (
  player_id bigint, season text, rim_shots int, rim_val_sum numeric,
  jump_shots int, jump_val_sum numeric, PRIMARY KEY (player_id, season));
INSERT INTO hex_shot_own_stage
WITH sh AS (
  SELECT shooter_id AS player_id, season, shot_zone,
    CASE WHEN shot_result='Made' AND shot_value=3 THEN 1.5 WHEN shot_result='Made' THEN 1.0 ELSE 0 END AS efg_pts
  FROM shot_event
  WHERE season >= '2021-22' AND season_type='Regular Season' AND shooter_id IS NOT NULL
),
zb AS (SELECT season, shot_zone, avg(efg_pts) lg FROM sh GROUP BY 1,2)
SELECT sh.player_id, sh.season,
  count(*) FILTER (WHERE shot_zone='Restricted Area') AS rim_shots,
  sum(efg_pts - zb.lg) FILTER (WHERE shot_zone='Restricted Area') AS rim_val_sum,
  count(*) FILTER (WHERE shot_zone IN ('Mid-Range','Above-the-Break 3','Left Corner 3','Right Corner 3')) AS jump_shots,
  sum(efg_pts - zb.lg) FILTER (WHERE shot_zone IN ('Mid-Range','Above-the-Break 3','Left Corner 3','Right Corner 3')) AS jump_val_sum
FROM sh JOIN zb USING (season, shot_zone) GROUP BY 1,2;

-- 2. STAGING: offensive-rebound on-court counts per (player, team, season), full off lineups only.
DROP TABLE IF EXISTS hex_oreb_stage;
CREATE TABLE hex_oreb_stage (
  player_id bigint, team_id bigint, season text, on_poss int, on_oreb int,
  PRIMARY KEY (player_id, team_id, season));
INSERT INTO hex_oreb_stage
SELECT u.player_id, pl.off_team_id AS team_id, pl.season,
  count(*) AS on_poss, count(*) FILTER (WHERE p.had_oreb) AS on_oreb
FROM possession_lineup pl
JOIN possession p ON p.game_id=pl.game_id AND p.poss_idx=pl.poss_idx
CROSS JOIN LATERAL unnest(pl.off_players) AS u(player_id)
WHERE pl.season >= '2021-22' AND pl.season_type='Regular Season' AND pl.off_n=5
GROUP BY u.player_id, pl.off_team_id, pl.season;

-- 3. ASSEMBLE the outcomes.
DROP TABLE IF EXISTS hex_weight_outcomes;
CREATE TABLE hex_weight_outcomes AS
WITH onoff AS (
  SELECT person_id AS player_id, season,
    SUM((drtg_off-drtg_on)*off_poss_on)/NULLIF(SUM(off_poss_on),0)                       AS def_drtg_swing,
    SUM((sc_rate_allowed_off-sc_rate_allowed_on)*off_poss_on)/NULLIF(SUM(off_poss_on),0) AS reb_sc_allowed_supp
  FROM v_player_onoff_context
  WHERE season_type='Regular Season' AND season>='2021-22'
    AND drtg_off IS NOT NULL AND drtg_on IS NOT NULL
  GROUP BY 1,2
),
shot AS (
  SELECT person_id AS player_id, season,
    SUM(((act_efg_on-exp_efg_on)-(act_efg_off-exp_efg_off))*shots_on)/NULLIF(SUM(shots_on),0) AS play_setup_lift,
    SUM((exp_efg_on-exp_efg_off)*shots_on)/NULLIF(SUM(shots_on),0)                            AS grav_shotqual_lift
  FROM v_player_shot_onoff_context
  WHERE season_type='Regular Season' AND season>='2021-22'
    AND act_efg_on IS NOT NULL AND exp_efg_on IS NOT NULL AND act_efg_off IS NOT NULL AND exp_efg_off IS NOT NULL
  GROUP BY 1,2
),
own AS (
  SELECT player_id, season,
    CASE WHEN rim_shots  >= 50 THEN rim_val_sum  / rim_shots  END AS fin_rim_value,
    CASE WHEN jump_shots >= 50 THEN jump_val_sum / jump_shots END AS shoot_jump_value
  FROM hex_shot_own_stage
),
team_tot AS (
  SELECT off_team_id AS team_id, season, count(*)::numeric t_poss,
    count(*) FILTER (WHERE had_oreb)::numeric t_oreb
  FROM possession WHERE season_type='Regular Season' AND season>='2021-22' GROUP BY 1,2
),
oreb_pt AS (
  SELECT s.player_id, s.season, s.on_poss,
    (s.on_oreb::numeric/NULLIF(s.on_poss,0))
    - ((t.t_oreb - s.on_oreb)/NULLIF(t.t_poss - s.on_poss,0)) AS lift
  FROM hex_oreb_stage s JOIN team_tot t USING (team_id, season) WHERE s.on_poss >= 200
),
oreb AS (
  SELECT player_id, season, SUM(lift*on_poss)/NULLIF(SUM(on_poss),0) AS reb_oreb_lift
  FROM oreb_pt GROUP BY 1,2
),
merged AS (
  SELECT player_id, season, onoff.def_drtg_swing, onoff.reb_sc_allowed_supp,
    shot.play_setup_lift, shot.grav_shotqual_lift,
    own.fin_rim_value, own.shoot_jump_value, oreb.reb_oreb_lift
  FROM onoff FULL JOIN shot USING (player_id, season)
             FULL JOIN own  USING (player_id, season)
             FULL JOIN oreb USING (player_id, season)
)
SELECT *,
  ( (reb_sc_allowed_supp - avg(reb_sc_allowed_supp) OVER (PARTITION BY season))
      / NULLIF(stddev_samp(reb_sc_allowed_supp) OVER (PARTITION BY season),0)
  + (reb_oreb_lift - avg(reb_oreb_lift) OVER (PARTITION BY season))
      / NULLIF(stddev_samp(reb_oreb_lift) OVER (PARTITION BY season),0) ) AS reb_two_way
FROM merged;
ALTER TABLE hex_weight_outcomes ADD PRIMARY KEY (player_id, season);
GRANT SELECT ON hex_weight_outcomes TO anon, authenticated;
"""
# reb_sc_allowed_supp + reb_oreb_lift are the two rebounding components; reb_two_way is the graded
# outcome. All are read; AXIS_OUTCOME picks which one grades each axis.
OUTCOME_COLS = ("def_drtg_swing", "reb_sc_allowed_supp", "reb_oreb_lift", "reb_two_way",
                "play_setup_lift", "grav_shotqual_lift", "fin_rim_value", "shoot_jump_value")


# ---------------------------------------------------------------------------
def _client():
    from supabase_config import get_supabase_client
    c = get_supabase_client()
    if c is None:
        raise RuntimeError("Supabase not configured (SUPABASE_URL / SUPABASE_KEY in repo-root .env)")
    return c


def _page(client, table, select="*", eqs=None):
    """Pull every row past PostgREST's 1000-row cap. eqs = list of (col, val)."""
    out, start = [], 0
    while True:
        q = client.table(table).select(select)
        for col, val in (eqs or []):
            q = q.eq(col, val)
        data = q.range(start, start + 999).execute().data
        if not data:
            break
        out.extend(data)
        if len(data) < 1000:
            break
        start += 1000
    return out


def _next_season(s):
    """'2021-22' -> '2022-23'."""
    start = int(s[:4])
    return f"{start + 1}-{str(start + 2)[-2:]}"


def _f(x):
    return None if x is None else float(x)


# ---------------------------------------------------------------------------
# Load grades (percentiles) and the six frozen outcomes
# ---------------------------------------------------------------------------
def load_axis_submetrics(client):
    """axis -> ordered list of its sub-metrics, live from hexagon_weights (fallback if empty)."""
    rows = _page(client, "hexagon_weights", "axis,sub_metric,weight")
    if not rows:
        return {k: list(v) for k, v in AXIS_SUBMETRICS_FALLBACK.items()}
    out: dict = {}
    for r in rows:
        out.setdefault(r["axis"], []).append(r["sub_metric"])
    return out


def load_current_weights(client):
    """axis -> {sub_metric: weight} exactly as live today (the primary bar to beat)."""
    rows = _page(client, "hexagon_weights", "axis,sub_metric,weight")
    out: dict = {}
    for r in rows:
        out.setdefault(r["axis"], {})[r["sub_metric"]] = float(r["weight"])
    return out


def load_pctiles(client):
    """pool='all', Regular Season percentile rows keyed (player_id, season). Value = full row."""
    rows = _page(client, "v_player_axis_pctile", eqs=[("pool", "all"), ("season_type", SEASON_TYPE)])
    grades: dict = {}
    for r in rows:
        if r["season"] not in OUTCOME_SEASONS and _next_season(r["season"]) not in OUTCOME_SEASONS:
            continue  # keep only grade-seasons that can be joined to an outcome season
        if r.get("off_poss_on") is None or float(r["off_poss_on"]) < MIN_OFF_POSS:
            continue
        grades[(r["player_id"], r["season"])] = r
    if not grades:
        raise RuntimeError("FAIL LOUD: no pool='all' percentile rows loaded — v_player_axis_pctile empty?")
    return grades


def load_outcomes(client):
    """Load the frozen, independent, on-court outcomes from the hex_weight_outcomes snapshot table
    (pre-aggregated per player-season; see REBUILD_SQL). Returns {outcome_col: {(player_id, season):
    float}}, higher = better impact. `season` is the season the outcome is MEASURED in — the temporal
    N->N+1 join for gravity/finishing/shooting is applied later in grade_weights()."""
    rows = _page(client, "hex_weight_outcomes")
    if not rows:
        raise RuntimeError("FAIL LOUD: hex_weight_outcomes is empty — rebuild it with REBUILD_SQL.")
    have = {r["season"] for r in rows}
    missing = set(OUTCOME_SEASONS) - have
    if missing:
        raise RuntimeError(f"FAIL LOUD: hex_weight_outcomes missing seasons {sorted(missing)} "
                           f"(have {sorted(have)}). Rebuild after the possession engine updates.")
    out = {col: {} for col in OUTCOME_COLS}
    for r in rows:
        for col in OUTCOME_COLS:
            v = _f(r.get(col))
            if v is not None:
                out[col][(r["player_id"], r["season"])] = v
    for col, d in out.items():
        if not d:
            raise RuntimeError(f"FAIL LOUD: outcome '{col}' has zero rows in hex_weight_outcomes.")
    return out


def load_data():
    c = _client()
    return {
        "axis_submetrics": load_axis_submetrics(c),
        "current_weights": load_current_weights(c),
        "grades": load_pctiles(c),
        "outcomes": load_outcomes(c),
    }


# ---------------------------------------------------------------------------
# Statistics (identical conventions to team_fit_backtest.py)
# ---------------------------------------------------------------------------
def _residualize(rank_target, control_ranks):
    X = np.column_stack([np.ones_like(rank_target)] + control_ranks)
    beta, *_ = np.linalg.lstsq(X, rank_target, rcond=None)
    return rank_target - X @ beta


def partial_spearman(x, y, controls):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ctrl = [np.asarray(c, float) for c in controls]
    mask = np.isfinite(x) & np.isfinite(y)
    for c in ctrl:
        mask &= np.isfinite(c)
    if mask.sum() < 5:
        return float("nan"), float("nan"), int(mask.sum())
    rx, ry = rankdata(x[mask]), rankdata(y[mask])
    rc = [rankdata(c[mask]) for c in ctrl]
    r, p = pearsonr(_residualize(rx, rc), _residualize(ry, rc))
    return r, p, int(mask.sum())


def spearman(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 5:
        return float("nan"), int(mask.sum())
    r, _ = pearsonr(rankdata(x[mask]), rankdata(y[mask]))
    return r, int(mask.sum())


# ---------------------------------------------------------------------------
# The core: grade a weighting for one axis
# ---------------------------------------------------------------------------
def _axis_grade(row, weights):
    """Weighted mean of a row's sub-metric percentiles (skip null pctiles / zero weights).
    Mirrors v_player_hexagon assembly. Returns None if no sub-metric contributes."""
    num = den = 0.0
    for sm, w in weights.items():
        if w == 0:
            continue
        v = row.get(sm)
        if v is None:
            continue
        num += w * float(v)
        den += w
    return None if den == 0 else num / den


def grade_weights(axis, weights, data=None, seasons=DEFAULT_TEST, label=None):
    """Grade a proposed {sub_metric: weight} for `axis` on `seasons`. Returns
    {spearman, partial, partial_p, n, temporal, outcome}.

    For temporal axes the grade in season N is joined to the outcome measured in season N+1.
    Control residualized out of the partial: off_poss_on (role / sample size)."""
    if data is None:
        data = load_data()
    outcome_key, temporal = AXIS_OUTCOME[axis]
    outcome = data["outcomes"][outcome_key]
    grades = data["grades"]

    xs, ys, ctrl = [], [], []
    for (pid, season), row in grades.items():
        if season not in seasons:
            continue
        g = _axis_grade(row, weights)
        if g is None:
            continue
        okey = (pid, _next_season(season) if temporal else season)
        y = outcome.get(okey)
        if y is None:
            continue
        xs.append(g)
        ys.append(y)
        ctrl.append(float(row["off_poss_on"]))

    sr, n = spearman(xs, ys)
    psr, pp, pn = partial_spearman(xs, ys, [ctrl])
    return {"spearman": sr, "partial": psr, "partial_p": pp, "n": n,
            "temporal": temporal, "outcome": outcome_key, "label": label or "candidate"}


def _equal_weights(submetrics):
    return {sm: 1.0 for sm in submetrics}


def best_single(axis, data, seasons=DEFAULT_TEST):
    """Ceiling-ish baseline: the single sub-metric that alone correlates best with the outcome."""
    best = None
    for sm in data["axis_submetrics"].get(axis, AXIS_SUBMETRICS_FALLBACK[axis]):
        r = grade_weights(axis, {sm: 1.0}, data=data, seasons=seasons, label=f"single:{sm}")
        if best is None or (np.isfinite(r["spearman"]) and r["spearman"] > best["spearman"]):
            best = r
    return best


# ---------------------------------------------------------------------------
# The bar
# ---------------------------------------------------------------------------
def axis_report(axis, data=None, train=DEFAULT_TRAIN, test=DEFAULT_TEST, verbose=True):
    """Print the three baselines for one axis on the TEST seasons: current live weights,
    equal-weight, and best-single. These are the numbers a re-weighting must beat."""
    if data is None:
        data = load_data()
    subs = data["axis_submetrics"].get(axis, AXIS_SUBMETRICS_FALLBACK[axis])
    cur = data["current_weights"].get(axis, _equal_weights(subs))

    rows = {
        "current_weights": grade_weights(axis, cur, data=data, seasons=test, label="current_weights"),
        "equal_weight": grade_weights(axis, _equal_weights(subs), data=data, seasons=test, label="equal_weight"),
        "best_single": best_single(axis, data, seasons=test),
    }
    if verbose:
        _, temporal = AXIS_OUTCOME[axis]
        tag = " [TEMPORAL N->N+1]" if temporal else ""
        note = "  (shooting is noisy year-to-year — modest ceiling)" if axis == "shooting" else ""
        print(f"\n--- {axis.upper()}  outcome={rows['current_weights']['outcome']}{tag}{note}")
        print(f"    sub-metrics: {', '.join(subs)}")
        print(f"    {'baseline':<26}{'spearman':>10}{'partial':>10}{'partial_p':>11}{'n':>7}")
        for name, m in rows.items():
            extra = f"  ({m['label']})" if name == "best_single" else ""
            print(f"    {name:<26}{m['spearman']:>10.3f}{m['partial']:>10.3f}{m['partial_p']:>11.3f}{m['n']:>7}{extra}")
    return rows


def print_the_bar(data=None, train=DEFAULT_TRAIN, test=DEFAULT_TEST):
    if data is None:
        data = load_data()
    print("=" * 82)
    print("HEXAGON-WEIGHT BACKTEST — THE BAR (numbers every re-weighting must beat)")
    print("=" * 82)
    print(f"grade pool: 'all' (>= {MIN_OFF_POSS} off-poss), {SEASON_TYPE}")
    print(f"validate window: {OUTCOME_SEASONS}  |  default TRAIN={list(train)}  TEST={list(test)}")
    print("controls residualized out of 'partial': off_poss_on")
    print("outcomes are FROZEN & excluded from candidate sub-metrics (no-leakage rule).")
    print("gravity/finishing/shooting graded TEMPORALLY (grade N -> outcome N+1).")
    for axis in ("finishing", "shooting", "playmaking", "defending", "rebounding", "gravity"):
        axis_report(axis, data=data, train=train, test=test)
    print("\n" + "=" * 82)
    print("Interpretation: a re-weighting is worth shipping for an axis only if its TEST partial")
    print("Spearman clears current_weights AND equal_weight by a margin real for that axis's n —")
    print("and the new leaderboard stays face-valid. Otherwise keep the current weights and say so.")
    print("finishing=rim-only, shooting=jumper-only (own shots, temporal); rebounding=two-way")
    print("(defensive 2nd-chance suppression + offensive OREB on/off lift). shooting has a low ceiling.")
    print("=" * 82)


if __name__ == "__main__":
    os.environ.setdefault("SKIP_DB_TESTS", "0")
    print_the_bar()
