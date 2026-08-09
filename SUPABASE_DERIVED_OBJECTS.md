# Supabase Derived Objects — Possession Engine, Splits & Player Hexagon

**Project:** "NBA App" (`qhrgekcowkgwcaaqyqvv`, Postgres 17, `us-east-2`).
**Purpose:** Authoritative reference for everything built on top of `play_by_play` /
`shot_event` / `pbp_lineup_stint` in this work stream. Keep this current so Claude Code CLT
has the deployed state. Companion docs: `SUPABASE_DATA_CATALOG.md` (raw schema),
`SUPABASE_POSSESSION_AND_HEXAGON.md` (design), `sql/` (DDL files).

Scope of all objects below: **seasons `2013-14` → `2025-26`** (backfilled via
`backfill_hexagon_seasons`; core engine supports 2005-06+), `season_type IN ('Regular Season','Playoffs','Play In')`.

---

## 0. TL;DR object map

| Object | Type | Grain | Refresh |
|---|---|---|---|
| `possession` | table | 1 row / offensive possession (~1.29M) | `refresh_possessions(season)` |
| `v_team_bonus_splits` / `_chance_` / `_transition_` | view | team-season (offense) | live |
| `v_team_*_splits_def` (×3) | view | team-season (defense) | live |
| `player_oncourt_poss` | table | player × team × season | `refresh_player_oncourt_poss(season)` |
| `player_oncourt_shot` | table | player × team × season | `refresh_player_oncourt_shot(season)` |
| `player_oncourt_shot_def` | table | player × team × season | `refresh_player_oncourt_shot_def(season)` |
| `v_player_onoff_context` | view | player × team × season | live |
| `v_player_shot_onoff_context` | view | player × team × season | live |
| `v_player_finishing/shooting/playmaking/defending/rebounding/gravity` | view | player × season | live |
| `player_axis_metrics` | table | player × season (~390/season) | `refresh_player_axis_metrics(season)` |
| `v_player_hexagon` | view | (pool × player × season) | live (percentiles over `player_axis_metrics`) |

All refreshes run nightly inside **`refresh_show_rollups()`** (pg_cron `refresh-show-rollups`, 11:45 UTC), for the **current season only**, after the existing matview refreshes.

---

## 1. Possession engine — `possession`

One row per offensive possession derived from `play_by_play`. **A possession ends** on a made FG,
a made final FT, a turnover, or a defensive rebound; **offensive rebounds (player OR team) extend
it**. Built by `refresh_possessions(p_season)` (idempotent DELETE+INSERT). DDL: `sql/possession_engine.sql`.

Key columns: `game_id, poss_idx, season, season_type, period, off_team_id, def_team_id,
start/end_elapsed_sec, duration_sec, points, first_chance_pts, second_chance_pts, had_oreb,
n_player_oreb, end_reason, start_reason, is_transition, opp_in_bonus`.

**Derivation specifics (validated against live data):**
- `team_id=0` rows (team rebounds/TOs) are resolved to a real team via the description nickname.
- Points come from a reconstructed running score (scores ~26% populated → carry forward); technical FTs excluded.
- **Bonus** (`opp_in_bonus`): per-period penalty-counting fouls (`Shooting, Personal, Loose Ball,
  Personal Take, Away From Play, Transition Take, Clear Path, Flagrant 1/2`); threshold = 5th foul
  (4th in OT), or 2nd foul inside the last 2:00.
- **Transition** (`is_transition`): possession started off a live DREB/turnover AND first action
  within 7s of the *prior* possession's end (the moment the ball was gained).
- **Second chance** (`had_oreb`): possession contained any offensive rebound incl. team rebounds.
  `n_player_oreb` is player-only (ties to box OREB).

**Validation (2025-26 RS):** possessions 99.6/team/game vs official 100.7 (~1%); player OREB
27,939 vs box 27,989; bonus-state 99.4% precision; transition rate 19.2% vs Synergy 18.5%.
Full suite: `sql/possession_engine_validation.sql`.

---

## 2. Team splits (offense + defense)

Offensive (group by `off_team_id`): `v_team_bonus_splits`, `v_team_chance_splits`,
`v_team_transition_splits`. Defensive (group by `def_team_id`, = what a team ALLOWS):
`v_team_bonus_splits_def`, `v_team_chance_splits_def`, `v_team_transition_splits_def`.
ORtg/DRtg = points per 100. DDL: `sql/hexagon_and_splits.sql`.

Example (Wolves 2025-26): bonus ORtg 123.5 vs non-bonus 115.2; transition 1.20 PPP vs halfcourt 1.14.

---

## 3. Player on/off context

**Attribution:** "on floor" = the player's own `pbp_lineup_stint` covers the event time.
`pbp_lineup_stint.in/out_elapsed_sec` are GAME-cumulative seconds (NOT within-period as the data
catalog states) — same scale as `possession`/`shot_event.elapsed_sec`. Internal check:
`sum(off_poss_on)` / `sum(shots_on)` over a team's players = exactly **5.000 × team poss / FGA**.

- `player_oncourt_poss` — offensive & defensive possessions on floor, with points / second-chance /
  transition / bonus counts. → `v_player_onoff_context` (ORtg/DRtg/net on-off, second-chance &
  transition rate on/off, "off" = team total − on).
- `player_oncourt_shot` — team offensive shot context on floor (rim FGA, expected & actual eFG;
  expected eFG = league zone-eFG baseline). → `v_player_shot_onoff_context` (rim-freq, expected-eFG,
  actual-eFG on/off).
- `player_oncourt_shot_def` — opponent shots faced while on defense (rim makes/attempts, eFG). Feeds
  the Defending axis (opp rim FG% / eFG suppression on/off).

DDL: `sql/hexagon_and_splits.sql` (poss + offensive shot), `sql/hexagon_axes.sql` (defensive shot).

> **`mv_player_onoff` ON/OFF swap — FIXED at the root.** The loader `historical-database/scripts/ingest.py`
> assigned the NBA `TeamPlayerOnOffDetails` result sets backwards (`frame[1]` is OnCourt, `[2]` is
> OffCourt — it stored them reversed). Fix applied in three parts: (1) `ingest.py` line ~281 corrected
> to `((1,"ON"),(2,"OFF"))`; (2) the existing `team_player_onoff` rows were un-swapped in place (atomic
> 3-step label flip); (3) `mv_player_onoff` rebuilt with the **natural** mapping (`ON`→`_on`). Verified:
> `min_on` matches box minutes exactly (Gobert 2380/2379, Edwards 2137/2135, Conley 991/994) and
> starters > backups in `poss_on`. **The same swap existed in all three loaders and is now fixed
> everywhere:** `ingest.py` (→ `team_player_onoff`, the matview source — un-swapped in place),
> `scripts/fetch_nba_team_onoff.py` and the edge function `fetch-team-onoff` (both → legacy
> `nba_team_onoff`; edge function corrected and **redeployed v2**). Note: `nba_team_onoff` is currently
> **empty** (its NBA fetch can't reach stats.nba.com from the Supabase edge runtime), so that swap was
> harmless in practice — the code is now correct so any future population will be right. This build's
> hexagon does not depend on `mv_player_onoff` either way.

---

## 4. Hexagon — six axes

Raw per-player metric views (live): `v_player_finishing, v_player_shooting, v_player_playmaking,
v_player_defending, v_player_rebounding, v_player_gravity`. DDL: `sql/hexagon_and_splits.sql`
(fin/reb/grav) + `sql/hexagon_axes.sql` (shoot/play/def).

| Axis | Core sub-metrics (weight) |
|---|---|
| Finishing | rim FG% over league (2×), rim rate (1×) — **team rim-freq on/off dropped 2026-07-01 (backtest)** |
| Shooting | catch-&-shoot eFG (2×), pull-up eFG (1.5×), shotmaking-over-expected (1×, floored), spot-up PPP (1×, floored) — **split REAL as of 2026-06-30 (Part C)**; ATB3% dropped |
| Playmaking | assist points created (1×) — **AST% + drive assists dropped 2026-07-01 (backtest); ast_pts_created is the impact signal** |
| Defending | rim-stop = normal−actual rim FG% allowed (2×), −PCT_PLUSMINUS overall FG suppression (1.5×), deflections/36 (1.5×), contested-2PT/36 (1×), BLK/100 (1×), STL/100 (1×) — **REAL as of 2026-06-30 (Part C)** |
| Rebounding | OREB% (1.5×), DREB% (1.5×), second-chance rate on/off, contested-reb/36 (1×), reb-chance conversion (1×) — **contested% added 2026-06-30 (Part C)** |
| Gravity | **2025-26+: NBA tracking gravity (2×), ORtg lift (1×)** — pre-2025-26 keeps shot-diet gravity = expected-eFG on/off (2×), ORtg lift, rim-freq lift. **REAL as of 2026-08-09** |

**Gravity axis is now REAL** (2026-08-09), and it is the first axis with **season-scoped weights**.

*Why:* against NBA's own tracking measure (`stats.nba.com/stats/gravityleaders`, defensive attention
from per-frame defender positioning), the old axis correlated **+0.009** — no relationship at all.
The league's #1/#2 gravity players graded 44 and 27, because `shot_diet_gravity_efg` (2×) and
`rim_freq_lift` (1×) are shot-*location* proxies that read perimeter gravity as absence.

*Chain:* `fetch_gravity_tracking.py` → **`player_gravity_tracking`** → `refresh_player_axis_metrics`
populates `tracking_gravity` + 4 splits (`grav_onball_perim`, `grav_offball_perim`, `grav_onball_int`,
`grav_offball_int`, all weight 0 = breakdown) → **`v_player_gravity_pctile`** → `v_player_axis_pctile`
(now a thin wrapper over `v_player_axis_pctile_core` + the gravity percentiles, so all sub-metric
percentiles stay under one name) → `v_player_hexagon`.

*Season scoping:* `hexagon_weights.season_from` (sentinel `'0000-00'` = from the beginning), PK
`(axis, sub_metric, season_from)`; `v_player_hexagon` picks the most specific applicable row via
`JOIN LATERAL … ORDER BY season_from DESC LIMIT 1`. Required because the assembly renormalizes over
non-NULL weights — dropping the proxies outright would have applied to all 13 seasons. **Coverage is
2025-26 forward only; the endpoint has no history.** Verified bit-identical: **0 of 8,892 pre-2025-26
rows changed**.

*Untracked players:* 145 of 379 qualified players are absent from the tracking feed (Giannis, Embiid).
`shot_diet_gravity_efg_fb` / `rim_freq_lift_fb` are non-NULL **only** when `tracking_gravity` IS NULL,
so those players score on the exact pre-2025-26 formula while covered players score on tracking —
never a blend of the two. Without this they renormalized onto `off_rating_lift` alone and hit 97–99.

⚠️ Gravity is **not comparable across the 2024-25 → 2025-26 boundary**; the backtest judges gravity
temporally N→N+1, so that pair is apples-to-oranges.

⚠️ The gravity percentile columns use `rank()/count(col)` rather than the `percent_rank()` pattern used
by their siblings, which leaves NULLs in the denominator and caps sparse metrics below 100 (`cs_efg`
maxes at 90.2, `floater_fg` at 92.3 — pre-existing, not fixed here). With `tracking_gravity` NULL for
145 of 379, the old pattern would have graded the top of the axis at ~62.

**Defending axis is now REAL** (Part C, 2026-06-30): the Part A tracking dashboards provide
`pt_defend_player` (rim D_FG% allowed vs normal, overall PCT_PLUSMINUS) + `hustle_player`
(deflections, contested 2PT). New `player_axis_metrics` cols `def_rim_stop, def_pm_stop,
deflections_per36, contested2_per36` (all stored higher=better); the on/off `drtg_swing` proxy was
dropped, BLK/STL kept at reduced weight. **Before→after (2024-25 pool=all): Gueye/Sharpe/Suggs →
Wembanyama/Jaren Jackson Jr./Caruso/Ausar Thompson/Draymond Green** — DPOY-caliber defenders now top
the axis (Draymond, whom the proxy missed, returns). Populated for all seasons (rim 2013-14+,
hustle 2015-16+); wired into `refresh_player_axis_metrics`.

**Part C complete (2026-06-30).** All three remaining upgrades shipped, each following the Defending
recipe (real tracking metric primary; noisy proxy floored/reduced; before→after face validity):
- **Shooting split** — `cs_efg`/`pu_efg` (catch-&-shoot / pull-up eFG from `pt_tracking_player`
  CatchShoot/PullUpShot, volume-floored at 1.0 FGA/g) are now primary (2× / 1.5×). The noisy
  `shotmaking_over_exp` was floored (jump_fga ≥ 150) and reduced 2→1; `spotup_ppp` floored at ≥ 50
  spot-up poss (inside `v_player_shooting`); the redundant unfloored **`atb3_pct` dropped**. cs/pu
  measure **efficiency**, so efficient specialists (Seth Curry, Kennard, Hauser) top the sub-metrics
  while high-volume pull-up stars (SGA/Luka/Dame) land mid-pack — correct by design.
  **Before→after axis top (2024-25 pool=all):** zero-jumper rim-runners (Dereck Lively II 99, Adem
  Bona 94, Daniel Gafford 93) → real shooters (Harrison Barnes, Ty Jerome, Seth Curry, Durant,
  LaVine, S. Curry, Pritchard, Burks); only two efficient centers linger at a modest 79–80.
- **Rebounding contested%** — `contested_reb_per36` (REB_CONTEST) + `reb_chance_pct`
  (REB/REB_CHANCES conversion) added to `v_player_rebounding` (1× each), a toughness/conversion
  dimension over raw OREB%/DREB%. Contested-reb leaders are battling bigs (Adams, Clingan, Kessler,
  Drummond, Capela); the axis stays big-dominated. (Gobert 92→84: his scheme-inflated DREB% tempered
  by lower contested/conversion — defensible.) No collateral on other axes (a star's
  finishing/playmaking/defending/gravity are byte-identical before/after).
- **Team hexagon** — see §8.7.

**Assembly (config-driven — see `sql/hexagon_weights.sql`):** `player_axis_metrics` (table,
~390 players/season) materializes the ~18 raw sub-metrics via `refresh_player_axis_metrics(season)`
(6 sequential steps — the shot-scanning axis views are too slow to join live). Then:
`v_player_axis_pctile` = 0–100 percentile of each sub-metric (no weights applied) →
`hexagon_weights` (editable `axis, sub_metric, weight` table) → `v_player_hexagon` = weighted mean
of percentiles per axis. **Re-tune grades by `UPDATE hexagon_weights`** (instant, all seasons, no
re-backfill); the Streamlit page also edits weights live in-session. Output: one row per **`pool`**
× player × season.
> ⚠️ **App-side parity:** whenever a sub-metric is added / dropped / re-weighted here, also update
> `AXIS_SUBMETRICS` **and** `RAW_FMT` in `combined-app/player_app/hexagon_viz.py` — that list drives
> both the Players-page 🕸️ Player Hexagon tab's `compute_scores` (must match `v_player_hexagon`, else
> it silently drifts) and the "Raw sub-metrics" display. See CLAUDE.md → *Hexagon Sub-metric Display
> Parity Rule*.
- `pool='all'` — ranked vs all minutes-qualified players (≥ 1000 on-court off. possessions).
- `pool='position'` — ranked vs same position group.
- `pos_group` (G/F/C) is a **role proxy** derived from rebounding/assist profile (the NBA `position`
  column is sparse/missing: `dreb_pct≥0.18→C, ast_pct≥0.15→G, else F`).

**Weight backtest referee (`analysis/hexagon_weight_backtest.py`).** The weights are no longer only
face-valid — a train/test referee grades any `{sub_metric: weight}` for an axis against a FROZEN,
independent, on-court **impact** outcome (no leakage; grade in season N, gravity/finishing/shooting
judged temporally vs N+1). Outcomes are pre-aggregated into snapshot tables (built by the module's
`REBUILD_SQL`, 2021-22+): **`hex_weight_outcomes`** (per player-season: `def_drtg_swing`,
`reb_two_way`, `play_setup_lift`, `grav_shotqual_lift`, `fin_rim_value`, `shoot_jump_value`) fed by
**`hex_shot_own_stage`** (player OWN shots split rim vs jumper from `shot_event.shooter_id`) and
**`hex_oreb_stage`** (offensive-rebound on-court counts from `possession_lineup`). Tune on TRAIN
(2021-22..2023-24), judge once on TEST (2024-25..2025-26); ship only if the TEST partial Spearman
beats both current and equal weights AND the leaderboard stays face-valid.
> **Re-tune 2026-07-01 (shipped 2 of 6 axes):** **finishing** dropped `team_rim_freq_lift` (TEST
> partial 0.446→0.500; rim-running bigs on top) and **playmaking** now leads on `ast_pts_created`,
> dropping `ast_pct`+`drive_ast` (0.151→0.196; elite creators — Jokić/CP3 rise). **Kept unchanged
> (nothing cleared the bar face-validly):** *defending* (best alt +0.008 but drops Wembanyama —
> loses rim protection), *gravity* (only pure `shot_diet_gravity_efg`, which is the temporal near-dup
> of its own outcome, and yields a role-player leaderboard), *shooting* (low year-to-year ceiling;
> gain over equal is noise), *rebounding* (the best "improvement" is `sc_rate_on_minus_off`, a
> **near-duplicate of the outcome's offensive OREB half = leakage**; excluding it, no weighting beats
> the baselines — the referee's rebounding grade is compromised, current weights kept + flagged).

**Candidate sub-metric expansion + re-tune 2026-07-02.** Added 13 columns to `player_axis_metrics`
(+ `v_player_axis_pctile` + `v_player_hexagon` lateral): shot-diet volume/rate `rim_att_pg`,
`rim_mk_pg`, `floater_fg`, `atb3_att_pg`, `c3_pct`, `c3_att_pg` (from `shot_event`); `cut_ppp`,
`roll_ppp` (Synergy offensive PPP); `ast_pg`, `blk_pg`, `stl_pg` (box PerGame); `team_efg_lift`
(team eFG on−off, `v_player_shot_onoff_context`); and `opp_shot_quality_forced` (opponent expected-eFG
on vs off, from `player_oncourt_shot_def` + a team-faced `shot_event` scan). All referee-tested
(standalone + in-blend, tune TRAIN / judge TEST). **Shipped 2:**
> - **shooting** `+atb3_att_pg:2` (drop `spotup_ppp`, `shotmaking_over_exp`→2): TEST partial
>   **0.354→0.387**, and it **fixed the long-standing "non-shooting centers on top" face-validity bug**
>   (Jarrett Allen/Zubac → LaVine/Curry/Durant/SGA/Dame). atb3-3 volume identifies real shooters.
> - **defending** `+drtg_swing:1` — a **DELIBERATE** on/off impact include (Jack's call), weight 1;
>   Wemby/JJJ stay #1/#2. `drtg_swing` IS the referee's def outcome ⇒ added to `AXIS_LEAKAGE_EXCLUDE`
>   (referee-excluded, live only). `shot_diet_gravity_efg` (gravity) also excluded for the same reason.
>
> **Classified but NOT weighted:** finishing volume (`rim_att_pg`/`rim_mk_pg` dilute −0.05, `floater_fg`
> +0.009 = noise), `ast_pg` (+0.001, ast_pts_created already best), `team_efg_lift` (gravity TRAIN −0.006),
> `cut_ppp`/`roll_ppp`/`blk_pg`/`stl_pg` (weak) — kept as columns for the star map, weight 0.
> **`opp_shot_quality_forced` = leakage** (near-dup of `def_drtg_swing`; its +0.026 was context, and it
> dropped JJJ / floated Donovan Mitchell) → `AXIS_LEAKAGE_EXCLUDE`, weight 0, not shipped.
> **Deferred:** gravity-derived `corner3_pct_lift`/`team_fta_rate_lift` (heavy stint×event builds,
> gravity outcome already leakage-prone) and assist-dependent `created_2s`/`created_3s`/
> `high_value_assists` (assist resolution covers only 2024-25 → unvalidatable on TRAIN; the multi-season
> resolve is the disk-crash risk). `refresh_player_axis_metrics` wires the shipped `atb3_att_pg` + the
> star-map columns nightly (not the heavy unshipped `opp_shot_quality_forced`).

**Undervalued view `v_player_axis_value_gap`** (2021-22+, read live). Per (player, season, axis):
`grade` (validated hexagon skill), `role_pctile` (percentile of `off_poss_on`), `impact_pctile` (raw
axis impact outcome from `hex_weight_outcomes`), `impact_adj_pctile` (team-rating-residualized), and
**`value_gap = grade − role_pctile`** — high = a **sleeper** (validated skill the rotation under-uses),
NOT team-context-confounded. The v1 `impact − grade` construct was dropped as the ranking signal:
the on/off impact outcomes are team/lineup quantities, and residualizing on team OFF/DEF rating
**empirically removes ~nothing** (the confound is lineup-level, not team-level — RAW and adjusted
defending leaders were identical, both surfacing context beneficiaries like Micic/Shamet). The two
`impact*_pctile` columns are retained for transparency only. Top 2024-25 sleepers face-valid
(Gueye/Nnaji defending; Ingram/Embiid playmaking — skilled, low-minute). Exposed as the "💎 Undervalued"
section on `combined-app/pages/7_Hexagon.py`.

Output columns: `pool, season, season_type, player_id, pos_group, off_poss_on, finishing, shooting,
playmaking, defending, rebounding, gravity`.

**Face validity (2025-26, pool=all):** Jokić gravity 99 / playmaking 90; Gobert rebounding 94 /
shooting 1; Curry shooting 76 / gravity 80 / rebounding 16; SGA playmaking 97. Vs position, Jokić's
playmaking rises (best-passing C) while finishing/rebounding fall toward the center pack.

---

## 5. Streamlit page

`combined-app/pages/7_Hexagon.py` — Plotly `Scatterpolar` radar reading `v_player_hexagon` +
`player_axis_metrics`. Season selector, All-vs-Position toggle, optional 2-player overlay,
raw-sub-metric hover + expander, and a small-sample (< 1500 poss) caveat. Reads via the existing
`player_app/supabase_config.get_supabase_client()` (anon key; SELECT granted to `anon`/`authenticated`
on all objects above).

---

## 6. Refresh / cron

`refresh_show_rollups()` (pg_cron `refresh-show-rollups`, `45 11 * * *`) now runs, after the four
matview refreshes, for the **current season**:
```
PERFORM refresh_possessions(v_season);
PERFORM refresh_player_oncourt_poss(v_season);
PERFORM refresh_player_oncourt_shot(v_season);
PERFORM refresh_player_oncourt_shot_def(v_season);
PERFORM refresh_player_axis_metrics(v_season);
```
All views read live, so they need no refresh.

**Backfilling historical seasons.** The whole derived chain for one season is wrapped in
`refresh_hexagon_season(season)` (possession → 3× oncourt → axis_metrics, in order). For multiple
seasons use the driver procedure, which COMMITs after each so every season is durable independently:
```sql
SET statement_timeout=0;  -- must be its own statement; the chain exceeds the default timeout
CALL public.backfill_hexagon_seasons(ARRAY['2019-20','2018-19','2017-18','2016-17','2015-16','2014-15','2013-14']);
```
Runs ~several minutes per season server-side (the API/connector HTTP call will drop, but it keeps
running and committing). `v_player_hexagon` and the Streamlit page's season dropdown auto-pick-up
each season as it commits. Verify with `SELECT season, count(*) FROM player_axis_metrics GROUP BY 1`.

**Data-feed coverage (how far back is meaningful):** core engine inputs (`play_by_play`,
`pbp_lineup_stint`, `schedule`, `player_season_stats`) go back to **2005-06** and the clock is the
ISO `PT…S` format in all of them. Full hexagon fidelity needs tracking (`pt_tracking`, 2013-14+) and
Synergy (2012-13+); before those, a few Shooting/Playmaking sub-metrics are NULL (the hexagon skips
them, other axes are unaffected). Backfilled to **2013-14** (recommended floor for full fidelity);
extendable to 2005-06 at reduced Shooting/Playmaking detail.

> **Historical backfill completed 2026-06-27.** `player_axis_metrics` now actually covers all 13
> seasons **2013-14 → 2025-26** (348–396 players/season incl. ~18 Playoffs rows/season). The
> 2013-14 → 2019-20 seasons were added via per-season `refresh_hexagon_season()` runs (full seasons
> ~10 min each; the 2019-20 COVID-shortened season ~5 min). Validation (pool='all', RS): gravity
> leaderboards led by Curry/LeBron/Harden/Lillard/Westbrook/KAT/Draymond; defending led by genuine
> rim-protectors/stoppers (Kawhi, Anthony Davis, Draymond, Nerlens Noel, Jonathan Isaac, Robert
> Covington, Giannis, Roberson). No all-null axes. **Correction to the "Synergy 2015-16" assumption:**
> `spotup_ppp` is in fact populated back to **2013-14** (335/348 in 2013-14, 357/376 in 2014-15) —
> Synergy reaches 2013-14 in this warehouse; the ~3–6%/season `spotup_ppp` nulls are low-sample
> players, uniform across every season (not a coverage gap).

---

## 7. Known data gaps / gotchas

1. **`assist_person_id` is NULL warehouse-wide** in `play_by_play`/`shot_event` (assister only in the
   description text). Killed the assisted-high-value playmaking metric and any assisted/unassisted
   "self-creation" split — would need description name-parsing.
2. **No tracking-defense feed** (no deflections / defended-FG%) → Defending is proxy-only.
3. **`pbp_lineup_stint` elapsed is game-cumulative**, not within-period (catalog is wrong). ~8% of
   possessions can't resolve a full 5-man unit (stint gaps); focal-player on/off is robust to this.
4. **NBA `position` is sparse** (139/2242 players) → pos_group is a role proxy from box rates.
5. **Shot-scanning axis views are slow** because `shot_event` is a view recomputed over all
   `play_by_play`; that's why the hexagon is materialized via per-axis steps rather than one join.
6. **ON/OFF label swap — FIXED everywhere.** All three loaders corrected (`ingest.py`,
   `scripts/fetch_nba_team_onoff.py`, edge function `fetch-team-onoff` redeployed v2); `team_player_onoff`
   un-swapped in place; `mv_player_onoff` on natural mapping. Legacy `nba_team_onoff` is empty/unused
   (its loader can't reach NBA from the edge runtime) — code fixed so any future data is correct. See §3.

---

## 8. Team Hexagon

> **Status: DEPLOYED 2026-06-28** (migration `create_team_hexagon_objects`). The full chain
> `v_team_axis_metrics → v_team_axis_long → v_team_axis_pctile → v_team_hexagon` plus the config
> table `team_axis_weights` is live, validated, and granted to `anon`/`authenticated`. All views
> read live (no refresh). **Still to build:** the Streamlit page (`8_Team_Hexagon.py`) and an
> optional nightly materialization if the live `shot_event` scan gets slow at backfill scale.
> The original design rationale is preserved below; §8.4 reflects the as-built objects.

### 8.0 Deployed object map

| Object | Type | Grain | Notes |
|---|---|---|---|
| `v_team_axis_metrics` | view | team × season × season_type (30/season RS) | raw off+def sub-metrics, all six spokes |
| `v_team_axis_long` | view | + axis × side × sub_metric | tidy unpivot; carries `higher_is_good` |
| `team_axis_weights` | table | (axis, sub_metric) → weight | config; re-tune by `UPDATE` (matches `hexagon_weights`: RLS off, anon SELECT) |
| `v_team_axis_pctile` | view | long + `pctile` | 0–100 percentile within season/season_type/side pool, oriented so 100 = good |
| `v_team_hexagon` | view | team × season × season_type | wide: `o_*`/`d_*` for the 6 spokes, 0–100 |

### 8.1 Why the player axes don't port 1:1

The player hexagon leans heavily on **on/off context**, which is meaningless for a team (a team
is always "on"). Mapping each player axis to a team analog:

| Player axis | Team analog | Verdict |
|---|---|---|
| Rebounding | team OREB% / DREB% + second-chance rate | ports cleanly |
| Finishing | team rim rate × rim FG% (`shot_event` zones) | ports cleanly |
| Shooting | team ATB3 rate × 3P%, spot-up PPP | ports cleanly |
| Defending | opp rim FG% / eFG allowed (`shot_event` + `_def` splits) | ports — and improves (no proxy needed; real points-allowed signal) |
| Playmaking | AST% barely separates 30 teams; `assist_person_id` NULL warehouse-wide | **dropped** (weak at team grain) |
| Gravity | on/off effect on teammates' shot quality — no team meaning | **dropped** (no team analog) |

The dimension that *replaces* the collapsed on/off axis is **offense vs. defense**: a team's
identity is two-sided, so every spoke carries a "what you do" (offense) and a "what you allow"
(defense) value.

### 8.2 Framing — overlaid offense/defense on shared spokes

Six phase-of-play spokes. Each renders **twice** on the same axes: offense as a solid shape,
defense as a dashed shape. **Both shapes are oriented so outward = good** (defense percentiles are
inverted — see §8.3), so a great team is large on both and a complete team fills the hexagon. Three
spokes reuse the offense+defense split views from §2; three are team-grain `shot_event` rollups.

| Spoke | Offense (solid) | Defense / allowed (dashed) | Source object | Build status |
|---|---|---|---|---|
| Rim | rim rate × rim FG% | opp rim rate × opp rim FG% | `shot_event` zones | **new view** |
| Perimeter (3) | ATB3 rate × 3P% | opp ATB3 rate × opp 3P% | `shot_event` zones | **new view** |
| Transition | transition PPP | transition PPP allowed | `v_team_transition_splits` / `_def` | **built** |
| Second chance | second-chance rate / PPP | second-chance allowed | `v_team_chance_splits` / `_def` | **built** |
| Bonus / FT pressure | bonus ORtg / FT rate | bonus DRtg / FT rate allowed | `v_team_bonus_splits` / `_def` | **built** |
| Rebounding | OREB% | DREB% (opp OREB% suppressed) | box / `shot_event` | **new (light)** |

### 8.3 Normalization

- **Pool = the 30 teams in that season.** No minutes qualifier, no position pool (the player
  hexagon's `≥1000 poss` qualifier and `pool='all'|'position'` do not apply). Exactly one pool.
- **Percentile each spoke value 0–100 over those 30 teams** (mirrors `v_player_axis_pctile`).
- **Orient so outward = good on BOTH shapes.** For the defense/allowed values, invert before
  percentiling (lower opp rim FG% → higher percentile), matching the existing offensive-vs-defensive
  `_RANK` convention (offense ascending=False, defense ascending=True).

### 8.4 As-built object chain (mirrors §4)

```
v_team_axis_metrics  -- live view, 30 rows/season: raw off+def sub-metrics per spoke.
        │               rim/perimeter = shot_event zone rollups (rim = 'Restricted Area',
        │               3 = shot_value 3); defender mapped via possession game-pairs.
        │               transition/2nd-chance/bonus from the §2 split views; OREB%/DREB%
        ▼               from team_season_stats Advanced.
v_team_axis_long     -- live view: unpivot to (axis, side, sub_metric, raw_value) + higher_is_good.
        │               Rule: offense always higher-is-good; defense lower-is-good EXCEPT
        ▼               rebounding (DREB% higher = good).
v_team_axis_pctile   -- live view: percent_rank()*100 within (season, season_type, side, axis,
        │               sub_metric); defense inverted via -raw_value so 100 = good. Pool = the
        ▼               30 teams in that season+season_type (RS and Playoffs pooled separately).
team_axis_weights ──▶ v_team_hexagon  -- live view: weighted mean of pctiles per axis →
(config; UPDATE to       12 columns/team (o_/d_ × 6 spokes), 0–100. 1 row per team × season.
 re-tune, no rebuild)
```

**Seeded weights** (per axis+sub_metric, applied to both sides — efficiency 2×, volume 1×):
`rim pct 2 / freq 1`, `perimeter pct 2 / freq 1`, `transition ppp 2 / rate 1`,
`second_chance ppp 2 / rate 1`, `bonus rate 2 / rtg 1`, `rebounding reb_pct 1`.

All views read live, so there is **no refresh step** today. If the live `shot_event` scan becomes
slow at full-history scale, materialize `v_team_axis_metrics` into a table with a
`refresh_team_axis_metrics(season)` hung off `refresh_show_rollups()` (same pattern as
`player_axis_metrics` in §4/§6); not needed at current single-season query latency.

### 8.5 Validation (before anything goes on air)

**Validated 2026-06-28 (2025-26 RS).** Shot-derived spokes reconcile to official: `shot_event`
offense FGA/3PA tie to the box (avg abs diff 1.9 / 1.7 per team-season = per-game rounding only),
derived 3P% matches official `FG3_PCT` to 0.00, and the defender mapping conserves every shot
(Σ offense shots = Σ defense shots = 219,159). OREB%/DREB% come straight from official Advanced;
transition/2nd-chance/bonus inherit the validated possession engine (§1). Face validity on
`v_team_hexagon`: best defenses carry the **highest** (outward) dashed spokes — SAS/BOS/OKC top
def_mean; BOS `d_rim` 86 / `d_transition` 90; DEN `d_rebounding` 93 (Jokić); DEN `o_bonus` 97;
Brooklyn near the floor on every spoke.

### 8.6 Decisions & remaining items

**Resolved at build time:**
- **Rim/Perimeter = blended weighted pair** (not a single composite): rate and accuracy are
  separate sub-metrics under one axis, percentiled independently and combined via
  `team_axis_weights` (accuracy 2×, volume 1×) — mirrors the player Finishing axis.
- **Pooling = per `season` + `season_type`.** RS (30 teams) and Playoffs are percentiled in
  separate pools automatically. Default the app to RS; Playoffs is a small, lopsided field.

**Still open / next:**
- **Streamlit surface.** New page `8_Team_Hexagon.py` vs. a tab on `1_Teams.py`; overlay two teams
  for matchup prep (the show's core use case). Read `v_team_hexagon` + `v_team_axis_metrics` (raw
  hover), same anon-client pattern as `7_Hexagon.py`.
- **Spoke correlation to watch.** Rebounding (OREB/DREB) and Second-chance both touch the glass;
  monitor whether they move together enough to feel redundant on the radar, and consider a pace
  spoke if so.
- **Materialization** only if the live `shot_event` scan slows at full-history scale (§8.4).

### 8.7 Part C upgrades (2026-06-30) — Defending / Shooting / Rebounding + shot quality

Migration `partc_team_hexagon_upgrades` carried the three player upgrades to the team objects plus a
closest-defender shot-quality angle. The assembly stayed generic: only **`v_team_axis_metrics`** (7
append-only columns) and **`v_team_axis_long`** (7 unpivot rows + a higher-is-good whitelist) changed;
`v_team_axis_pctile` / `v_team_hexagon` were untouched.

| Spoke·side | New sub-metric | Source | Orientation |
|---|---|---|---|
| perimeter·off | `cs_efg`, `pu_efg` | `pt_tracking_team` CatchShoot / PullUpShot eFG | higher = good |
| perimeter·off | `open_rate` (**shot quality created**) | `pt_shot_defender_team` Σ FGA_FREQUENCY of Open + Wide-Open (4ft+) | higher = good |
| rebounding·off / def | `contest_pct` | `pt_tracking_team` Rebounding OREB_CONTEST_PCT / DREB_CONTEST_PCT | higher = good |
| rim·def | `rim_stop` | `pt_defend_team` Less Than 6Ft: NS_LT_06_PCT − LT_06_PCT | higher = good (whitelisted) |
| perimeter·def | `three_stop` | `pt_defend_team` Greater Than 15Ft: NS_GT_15_PCT − GT_15_PCT | higher = good (whitelisted) |

Weights (`team_axis_weights`): cs_efg 1 / pu_efg 1 / open_rate 1 / three_stop 1 / **rim_stop 1.5** /
contest_pct 1. The def "stop" metrics are oriented higher = better already, so `v_team_axis_long`'s
`higher_is_good` CASE prepends `WHEN sub_metric IN ('rim_stop','three_stop') THEN true` to stop the
pctile from inverting them.

**Shot quality is "created" only.** `pt_shot_defender_team` is the team's OWN shots (reconciles to box
FGA to 0.1), so there is **no team-grain "allowed" feed** — the allowed side would need game-level
closest-defender data the warehouse doesn't ingest. Surfaced rather than faked.

**Validated 2024-25 RS:** 30 teams, all 7 columns populated; `rim_stop` NOT inverted (BOS 100 / OKC
96.6 pctile); top `d_rim`+`d_perimeter` = BOS/OKC/CLE/MIN/HOU (the league's best defenses); `o_cs_efg`
leaders MIL/PHX/LAC/OKC/BOS; `o_open_rate` top OKC 61.6.

### 8.8 Materialized (2026-06-30) — fixes the page timeout

The Streamlit page (`8_Team_Hexagon.py`) was hitting `57014 statement timeout` because every query
(even `get_seasons()`) forced the live `shot_event` scan through the whole chain — and the Part C
LEFT JOINs pushed it over the PostgREST limit. **Base layer is now materialized** (same pattern as
`player_axis_metrics`):
- `v_team_axis_metrics` (the live-computing view) was renamed **`v_team_axis_metrics_src`**.
- **`team_axis_metrics`** — snapshot table (598 rows = 13 seasons × RS+Playoffs), indexed on
  `(season, season_type)`, populated by **`refresh_team_axis_metrics(season)`** (DELETE+INSERT from
  `_src`). One-time backfill done for all 13 seasons.
- `v_team_axis_metrics` is now a thin **`SELECT * FROM team_axis_metrics`** view, so `v_team_axis_long`
  → `v_team_axis_pctile` → `v_team_hexagon` are unchanged in definition but now read the table.
  `get_seasons()` / season pulls dropped from timeout to **~24 ms**.
- Wired into `refresh_show_rollups()` (after `refresh_possessions`, which it depends on) so the
  current season refreshes nightly. Historical seasons are static — re-run `refresh_team_axis_metrics`
  manually only if `_src` logic changes.

---

## 9. Part B stat ideas — reconciliation & incremental build (started 2026-06-29)

Reconciliation of the 13 vetted ideas (`SUPABASE_STAT_IDEAS.md`) vs deployed objects:
**BUILT (2):** #12 shot-diet gravity (`v_player_gravity`/hexagon), #13 second-chance value
(`v_team_chance_splits(_def)`, `possession.second_chance_pts`). **PARTIAL (1):** #4 expected-eFG
machinery exists inside the hexagon (`player_oncourt_shot`, `shotmaking_over_exp`) but no standalone
team selection-vs-making view. **TODO (10):** #1,#2,#3,#5,#6,#7,#8,#9,#10,#11.

### Phase 1 (Light) — built 2026-06-29
| Object | Idea | Source | Notes |
|---|---|---|---|
| `v_player_usage_efficiency` | #9 usage-efficiency quadrant (season) | `player_season_stats` Advanced | `usg_pct`/`ts_pct` + quadrant label (star thresholds usg≥.25 & ts≥.58). Reconciles by construction. |
| `v_team_playtype_profile` + `matchup_exploits(off,def,season,stype)` | #11 matchup-exploit finder | `synergy_playtypes` (entity_type='T') | View exposes offense+defense per play_type; function ranks A-offense vs B-defense by `freq × def_pctile × ppp`. |
| `v_passing_connections` | #6 passing network | `player_passing` (made) + `player_season_stats` Base | passer→receiver `passes/assists/frequency` + **`fg_pct_lift`** = receiver FG% off-pass − receiver baseline (chemistry signal). **Filter by `passes`/`assists` volume — `fg_pct_lift` is noisy on tiny samples.** |

Tests: `tests/test_partb_phase1_views.py` (intent checks vs source tables) — passing. Face validity:
usage stars = Giannis/Embiid/SGA/Luka/Edwards; top passing pipes = Harden→Zubac, Jokić→MPJ,
Lillard→Giannis; OKC-vs-WAS top exploit = spot-up. These views read live — no refresh needed.

### Phase 2 (Medium) — built 2026-06-29
| Object | Idea | Source | Notes |
|---|---|---|---|
| `v_team_game_ratings` + `team_rolling_rating(team,season,n,stype)` | #1 rolling NetRtg & #10 rest splits | `team_game_logs` (self-join for opp poss) | Per team-game pace-adjusted OffRtg/DefRtg/NetRtg (poss = FGA+0.44·FTA−OREB+TOV), `is_home`, `opp_team_id`, `gap_days`, `rest_bucket`. Rolling fn pools possessions over last N (not a mean of rates). |
| `mv_league_zone_efg` (matview) + `v_team_shot_selection` | #4 shot-selection vs shot-making | `shot_event` zones (≥2013-14) | `expected_efg` = shot diet × league zone-eFG baseline; `actual_efg`; `shotmaking_gap`. **Baseline matview** because the live join timed out the API (8s) on a full shot scan — refresh when a season is in progress. Reconciles to official `EFG_PCT` (0.0002). |
| `game_flow(game_id)` function | #8 scoring runs & volatility | `play_by_play` running score | Per-game largest home/away run, max leads, `lead_changes` (tie-safe), `margin_volatility`, secs each team led. **Function (not view)** so it filters to one game before the window funcs (a view scanned 13M rows → timeout). Reconstructed final score = box. Season-aggregate "team identity" would need a matview (deferred). |

Validation (2024-25 RS): season-aggregated NetRtg vs official `team_season_stats` NET_RATING —
**avg abs diff 0.44, corr 0.996** (30 teams). Rest splits monotonic: B2B −1.99 → 2+ days +0.67.
Tests: `tests/test_partb_team_ratings.py` (season reconciliation gate) — passing. Reads live.
Player rest splits = join `player_game_logs` to `v_team_game_ratings` on `(team_id, game_id)`.

### #5 self-creation — built 2026-06-29 (no-write path)
`v_player_self_creation` (player × season): `made_fg`, `unassisted_makes`, `unassisted_rate`
(+3pt/2pt splits). A made FG is assisted iff its `description` carries `"(... N AST)"` — so this
needs **no** `assist_person_id` resolve. Per-player queries use the person index. Validated:
Luka 0.67 unassisted vs Gobert 0.29 (creator vs finisher); `made_fg` reconciles to box FGM.
Test: `tests/test_partb_self_creation.py`.

> **Assist-resolution (`resolve_all_assists`) — DEFERRED after a disk incident.** `resolve_assists.sql`
> already existed; only **2024-25** is resolved (67,289, 97%/98% box). The multi-season in-DB UPDATE
> filled the instance disk (WAL out-of-space → Postgres PANIC + crash recovery; no data loss, only
> 2024-25 committed). Disk since auto-scaled, but a retry ran pathologically slow under the gp3
> resize I/O throttle and was cancelled. **The resumable per-season procedure `public.resolve_all_assists('2013-14')`
> remains** — re-run it off-peak in small batches once I/O has settled. #5 does not need it; #6 is
> already covered by `v_passing_connections`. **Lesson: never run a single large UPDATE on the 3.3 GB
> `play_by_play`; chunk per-season with COMMIT between (WAL recycles).**

### Phase 3 (Heavy) — built 2026-06-30 on `possession_lineup`
**Foundation `possession_lineup`** (table, 3.27M rows = 1 per possession, 2013-14→2025-26): per
possession, the on-court 5-man arrays `off_players` / `def_players` (+ `off_n`/`def_n`), resolved by
joining each possession's `start_elapsed_sec` to `pbp_lineup_stint`. **99.9% resolve a full 10-man
unit** (far better than the §3 ~8% worry). GIN indexes on both arrays for `@>` containment. Built
per-season with COMMIT between (the incident-safe pattern). Refreshed: rebuild current season after
`refresh_possessions` (not yet cron-wired — see below).

| Object | Idea | Notes |
|---|---|---|
| `staggering_splits(team,A,B,season,stype)` | #2 A-without-B | 4 states (both on / A-on-B-off / B-on-A-off / both off) off/def/net. Validated: Denver Jokić+Murray both-on +10.4, Jokić-alone +9.4, Murray-alone −1.7, both-off −13.4. |
| `team_lineup_tiers(team,season,stype)` | #7 bench units | Net rating by # starters on floor (starters = the 5 at the team's first possession each game). Bench unit = tier 0-1. Validated: DEN 5-starters +11.2 → bench-heavy negative. |
| `clutch_lineups(team,season,stype,secs,margin)` | #3 clutch | Per-5-man clutch net rating, custom time+margin (margin via per-game ref-team signed running score). **Always returns the possession N** — clutch 5-man samples are tiny (DEN 514 clutch poss over 403 lineups); filter by N or pool seasons. Top lineup = the closing five. |

Tests: `tests/test_partb_lineups.py` (+ `test_partb_self_creation.py`) — passing.

> **Current-season refresh of `possession_lineup` is NOT yet cron-wired.** It depends on `possession`
> (refreshed by `refresh_show_rollups`). To keep it live, after `refresh_possessions(current_season)`
> add: delete + re-insert that season's `possession_lineup` rows. Deferred (same decision class as the
> other current-season warehouse refreshes).

**🎉 All 13 stat ideas now BUILT** (#1–#11 this work stream + #12, #13 pre-existing). See the per-idea
objects above and in §4/§9. Part C hexagon upgrades approved (defending-real, shooting-split, rebounding-contested,
team) — to build.

---

*Last updated during the possession/hexagon build. Regenerate object lists with
`SELECT table_name FROM information_schema.views WHERE table_schema='public' AND table_name LIKE 'v_player%';`
and `\d+ player_axis_metrics` as the pipeline evolves.*
