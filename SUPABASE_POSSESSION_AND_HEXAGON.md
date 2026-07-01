# Possession Engine + Player Hexagon — Design Spec

**Companion to** `SUPABASE_STAT_IDEAS.md` and `SUPABASE_DATA_CATALOG.md`.
**Status:** design + build plan, vocabularies verified against live `play_by_play` (season `2025-26`).
This doc covers two builds Jack requested:

1. **A canonical possession definition** derived from PBP, with three splits on top: bonus vs
   non-bonus ORtg, first-chance vs second-chance, transition vs halfcourt (rate + PPP each).
2. **A six-axis player hexagon** (Finishing, Shooting, Playmaking, Defending, Rebounding, Gravity).

The possession engine is the foundation; several hexagon axes consume it.

---

# PART A — Defining a Possession

## A.1 What a possession is (the rule we'll use)

A **possession** = one team's continuous control of the ball until they score, turn it over, or
the opponent gains control. This is the Dean Oliver / standard definition, and critically:
**offensive rebounds extend the same possession — they do not start a new one.** That single
rule is what makes first-chance vs second-chance possible.

A possession **ends** on exactly one of:

| End reason | Detected by |
|---|---|
| Made field goal | `action_type='Made Shot'` (the and-1 FT that follows belongs to this possession) |
| Made final free throw of a trip | last `Free Throw N of N` that is **made**, excluding `Technical`/`Flagrant` FTs |
| Turnover | `action_type='Turnover'` (includes `Offensive Foul Turnover` — so offensive fouls are handled here, not double-counted from the `Foul` event) |
| Defensive rebound | `action_type='Rebound'` whose `team_id` ≠ the team that missed the preceding shot/FT |
| End of period | `action_type='period'` boundary / `Heave` at buzzer |

A possession **continues** (no new possession) on:
- **Offensive rebound** — `Rebound` whose `team_id` == the missing team (the catalog's inference
  rule; `sub_type` is ~95% `'Unknown'` so we must infer by sequence). This flips the possession
  into its **second-chance** segment.
- **Missed non-final FT** followed by an offensive rebound.
- **And-1 free throw** after a made shot (possession already ended on the make; FT points append).
- **Shooting foul before the shot / non-shooting defensive foul** that doesn't change control.

### Free-throw handling (verified subtypes)
From the live data, FT subtypes are `Free Throw 1 of 2`, `2 of 2`, `1 of 1`, `1 of 3 … 3 of 3`,
plus `Free Throw Technical` and `Free Throw Flagrant/Clear Path …`. Rules:
- **Technical FTs do not change possession** — exclude entirely from possession segmentation and
  from the `0.44×FTA` possession estimate.
- **Flagrant FTs** are followed by the fouled team *retaining* possession — they end a trip but
  the next possession is the same team; handle by not closing the possession on flagrant FTs.
- A normal trip ends the possession on the **made last FT**; if the last FT is **missed**, control
  is live → OREB continues the possession, DREB ends it.

## A.2 The deliverable: a `possession` table (materialized)

One row per possession. This is the new foundational matview (build once, reuse everywhere):

```
possession(
  game_id, season, season_type, period,
  poss_idx,                      -- sequential within game
  off_team_id, def_team_id,
  start_elapsed_sec, end_elapsed_sec, duration_sec,
  start_reason,                  -- dreb | turnover | made_fg | period | jumpball
  end_reason,                    -- made_fg | ft | turnover | dreb | period
  points,                        -- points the offense scored this possession (incl. FTs)
  had_oreb           boolean,    -- possession contained ≥1 offensive rebound
  first_chance_pts,              -- points before the first OREB
  second_chance_pts,             -- points after an OREB
  opp_in_bonus       boolean,    -- defense was in the penalty when this possession ran
  is_transition      boolean,    -- offense's first action < 7s after gaining control
  on_floor_off       text[],     -- 5 offensive person_ids  (from lineup_at_event)
  on_floor_def       text[]      -- 5 defensive person_ids
)
```

Points come from reconstructing the running score (`max(score_*) OVER (ORDER BY event_idx)` then
`lag()` — scores are only ~26% populated, per the catalog). `on_floor_*` come from joining
`lineup_at_event`; including them here means bonus-ORtg, transition splits, etc. can all be sliced
by lineup or on/off without re-deriving.

**Validation (do this before trusting any split):** sum possessions per team per game and
reconcile against the catalog estimator `Poss ≈ FGA + 0.44·FTA − OREB + TOV` (from
`team_game_logs.stats`) and against season-grain `team_season_stats.POSS`. The two teams in a game
should have possession counts within ~1 of each other. If the event-walk doesn't tie out, the
splits built on it aren't trustworthy.

## A.3 Split 1 — Bonus vs non-bonus ORtg

**Deriving bonus state (verified foul vocabulary).** Maintain a per-team, per-period running count
of **penalty-counting fouls**. From the live `sub_type` list, the fouls that count toward the team
penalty are: `Shooting`, `Personal`, `Loose Ball`, `Personal Take`, `Away From Play`,
`Transition Take`, `Clear Path`, `Flagrant Type 1`, `Flagrant Type 2`. **Excluded** (do not count):
`Offensive`, `Offensive Charge` (offensive fouls never count toward the team penalty), every
`Technical` variant, `Defense 3 Second` (it's a technical), `Flopping`, and `Bench`.

A team's opponent is **in the bonus** for a possession when, at the time the possession runs, the
defending team has reached the penalty threshold **in that period**:
- Regulation: **5th** penalty-counting team foul.
- Overtime: **4th**.
- Last 2:00 of any period: the **2nd** team foul of the period triggers it even if 5/4 isn't
  reached. *(This last-2-minute edge is the one to validate hardest.)*
- Counts reset each period.

**The metric.** Tag every possession with `opp_in_bonus`, then:
`ORtg_bonus = 100 × Σ points (opp_in_bonus) / Σ possessions (opp_in_bonus)` vs the same for
non-bonus. Report at team-season grain and, because `on_floor_off` is on the row, by lineup too.

**Self-debate.** *Value:* high — "this offense is +12 per 100 in the bonus" is a real,
rarely-quantified edge, and bonus rate itself flags teams that attack downhill. *Risk:* the
last-2-minute rule is fiddly and getting it wrong biases late-quarter possessions. *Mitigation —
a clean empirical check:* a **non-shooting defensive foul** flagged `in_bonus` must be followed by
**2 free throws**; one flagged `not in_bonus` must be followed by an **inbound, no FTs**. We can
measure the violation rate of that invariant directly and tune the threshold logic until it's near
zero. That validation is only possible because the FT subtypes (`1 of 2` vs none) are in the data.
**Kept** with that invariant as the acceptance test.

## A.4 Split 2 — First-chance vs second-chance

Because OREBs extend (not restart) a possession, every possession is `first-chance` up to its
first OREB and `second-chance` after. Outputs:
- **Second-chance rate** = share of possessions with `had_oreb = true`.
- **First-chance PPP** = `Σ first_chance_pts / total possessions`.
- **Second-chance PPP** = `Σ second_chance_pts / count(had_oreb)` — value *per extension*.
- Team identity read: high second-chance rate × high second-chance PPP = elite OREB team.

**Self-debate.** *Value:* offensive rebounding's *value* (not just the count the box already has)
is genuinely under-covered and swings playoff games. *Risk:* OREB is inferred, not labeled
(`sub_type` 95% `'Unknown'`). *Mitigation:* validate inferred OREB counts per game against
`player_game_logs`/`team_game_logs` `OREB` totals — they must match. **Kept**; the OREB-inference
step is a shared helper (also used by hexagon Rebounding/Gravity).

## A.5 Split 3 — Transition vs halfcourt (rate + PPP)

**Definition.** A possession is **transition** when it starts from a live-ball change (DREB,
steal/turnover, or made-basket inbound) **and** the offense's first scoring action (shot, drawn
shooting foul, or turnover) occurs **< 7 seconds** after gaining control. Everything else is
**halfcourt**. The 7s threshold is configurable. Then `PPP_transition` vs `PPP_halfcourt` and the
share of possessions in each.

**Two build routes (use both):**
- **Cheap / official baseline:** `synergy_playtypes` already has a `Transition` play type with
  `POSS`, `PPP`, `POSS_PCT` at team and player grain — Light, no PBP. Use it for the headline and
  as the cross-check.
- **Custom / per-game:** derive from the `possession` table using `start_reason` +
  `duration`-to-first-action. More flexible (our own threshold, per-game, by lineup) but
  approximate.

**Self-debate.** *Value:* pace-of-attack and where points come from is a core team-identity lens
and a strong pre-show angle. *Risk:* our PBP transition definition won't exactly equal Synergy's
tracked one. *Mitigation:* reconcile our derived transition share against `synergy_playtypes`
`POSS_PCT` for `Transition` per team; tune the second-threshold until they're close, then trust the
per-game version. **Kept.**

---

# PART B — The Player Hexagon

Six axes, each scored **0–100 as a percentile** within a peer pool (minutes-qualified players for
the season; toggle "vs position" using `players.position`). Each axis = a weighted blend of
sub-metric percentiles. A minutes/GP floor is mandatory to kill small-sample noise.

> **Build phasing.** **V1 (Light, ship first):** everything sourced from season tables +
> `shot_event` + `synergy_playtypes` + `player_passing` — no lineup work. **V2 (Heavy):** the
> on/off "context" sub-metrics (rim freq on/off, second-chance rate on/off, opponent rim FG%
> on/off, shot-diet gravity), which need the `lineup_at_event` materialization and the `possession`
> table from Part A. V1 already gives a full, defensible hexagon; V2 deepens it.

## B.1 Finishing
| Sub-metric | Source | Phase |
|---|---|---|
| Rim FGA rate (share of FGA in Restricted Area) | `shot_event` (`shot_zone='Restricted Area'`) | V1 |
| Rim FG% | `shot_event` | V1 |
| Finishing over expectation (rim FG% − league/position rim FG%) | `shot_event` + league rim baseline | V1 |
| Team rim frequency, player on vs off | `possession`/`lineup_at_event` + `shot_event` | V2 |

*Note:* consider folding In-Paint (non-RA) at a lower weight; pure RA is the cleanest "finishing."

## B.2 Shooting
| Sub-metric | Source | Phase |
|---|---|---|
| Shot-making over expectation (jump-shot eFG − zone-expected eFG) | `shot_event`, non-rim zones (idea #4) | V1 |
| Off-screen + spot-up Synergy score | `synergy_playtypes` (`OffScreen`,`Spotup` PPP/percentile) | V1 |
| ATB3% and C3% | `shot_event` (`Above-the-Break 3`, `Left/Right Corner 3`) | V1 |
| Jump-shot volume (non-rim FGA, and C&S vs pull-up mix) | `shot_event` + `pt_tracking` (`CatchShoot`,`PullUpShot`) | V1 |

Volume is included so a 42% low-volume shooter doesn't outrank a 38% high-volume floor-spacer;
weight % by attempts.

## B.3 Playmaking
| Sub-metric | Source | Phase |
|---|---|---|
| AST, AST% | `player_season_stats` Advanced (`AST_PCT`, `AST_RATIO`, `AST_TO`) | V1 |
| Created high-value attempts (assists into rim or corner-3) | `shot_event` (`assist_person_id` = player AND `shot_zone` ∈ {RA, Corner 3}) | V1 |
| Drive-and-kick creation | `pt_tracking` `Drives` (`DRIVE_AST`, `DRIVE_PASSES`) | V1 |
| Connection breadth / who they create for | `player_passing` (passer→teammate `AST`, FG% off pass) | V1 |

The "high-value created attempts" metric is the differentiator — `shot_event` carries
`assist_person_id` *and* zone, so we can credit a passer specifically for rim/corner-3 looks
(the shots worth the most), not just raw assists.

## B.4 Defending  ⚠️ (most constrained axis — read this)
**Gap surfaced from introspection:** the warehouse has **no tracking-defense feed.**
`pt_tracking_player` exposes only CatchShoot, Drives, Passing, Possessions, PullUpShot, Rebounding.
So **deflections and defended-FG% (dFG%) are NOT available.** We can't build them from this data;
we substitute proxies and label the axis as such.

| Sub-metric (available) | Source | Phase |
|---|---|---|
| STL% | derive: STL ÷ opponent possessions (the `possession` table gives opp poss directly) | V1*/V2 |
| BLK% | derive: BLK ÷ opponent 2PA on floor | V1*/V2 |
| Defensive on/off (team DEF_RATING swing) | `mv_player_onoff` (`DEF_RATING` ON−OFF) | V1 |
| Opponent rim FG% when player on vs off (rim-protection proxy for dFG%) | `shot_event` + lineup on/off | V2 |

\* STL%/BLK% aren't guaranteed as pre-computed keys in `player_season_stats` (the catalog lists
USG/ratings/REB%/AST%/TOV%/PIE but not STL_PCT/BLK_PCT), so plan to **derive** them — which the
possession engine makes exact (we have true opponent possessions). **Honest framing:** this axis is
a steals/blocks + on/off-impact composite, *not* a measured on-ball-defense rating. Say so on air.

## B.5 Rebounding
| Sub-metric | Source | Phase |
|---|---|---|
| OREB%, DREB% | `player_season_stats` Advanced (`OREB_PCT`,`DREB_PCT`) | V1 |
| Raw OREB/DREB per-100 | box via `player_game_logs` + possessions | V1 |
| Contested rebound share | `pt_tracking` `Rebounding` | V1 |
| Team second-chance possession rate, player on vs off | `possession` (`had_oreb`) + lineup on/off | V2 |

The on/off second-chance rate turns rebounding from an individual count into team *impact* — the
big who actually generates extra possessions for the unit scores higher than one who just collects
uncontested boards.

## B.6 Gravity
| Sub-metric | Source | Phase |
|---|---|---|
| Shot-diet gravity (team expected eFG% on vs off) | `possession`/`lineup_at_event` + `shot_event` zone model (idea #12) | V2 |
| Team corner-3 / rim frequency on vs off (spacing) | lineup on/off + `shot_event` | V2 |
| Teammate FG% off this player's passes vs their baseline | `player_passing` (`FG_PCT` vs receiver baseline) | V1 |

Gravity is mostly V2 by nature (it lives in *teammates'* numbers via on/off). The
`player_passing` teammate-shooting-lift piece is the one V1-available proxy, so the axis can render
in V1 (single sub-metric) and deepen in V2.

## B.7 Scoring & rendering
- **Peer pool:** season + minutes floor (e.g. ≥ X MIN or ≥ N GP). **Compute both pools and let the
  page switch between them:** (1) "vs all qualified" and (2) "vs position" from `players.position`
  (coarse G/F/C — flag mis-slotted players in hover). Precompute both percentile sets per player so
  the toggle is instant.
- **Percentile each sub-metric → weighted mean per axis → 6 axis scores (0–100).**
- **Render:** radar/hexagon (6 vertices). Streamlit: Plotly `Scatterpolar`. Keep raw values in
  hover so the percentile isn't a black box.
- **Guardrails (per CLAUDE.md "fail loud"):** show GP/MIN and, for any on/off or possession-based
  sub-metric, the possession sample behind it. Gray out / flag axes computed on thin samples rather
  than silently drawing a misleadingly confident shape.

---

# Build Order

1. **OREB-inference helper** (rebound team == prior missing team) — shared by A.4, B.5, B.6.
2. **`possession` matview** (Part A) — segment PBP, attach running-score points, OREB flags,
   bonus flag, transition flag, `on_floor_*`. Validate vs `team_season_stats.POSS` and the
   `FGA+0.44·FTA−OREB+TOV` estimator; validate bonus via the FT-count invariant (A.3); validate
   transition share vs Synergy (A.5). **Gate everything downstream on this passing.**
3. **Splits A.3 / A.4 / A.5** as views over `possession` (Light once the matview exists).
4. **Hexagon V1** — season tables + `shot_event` + `synergy_playtypes` + `player_passing`. Ships
   without the lineup materialization.
5. **Hexagon V2** — add the on/off context sub-metrics once the `lineup_at_event` materialization
   (from `SUPABASE_STAT_IDEAS.md` §2) and the `possession` table exist.

**Open question for you:** for the hexagon peer pool, do you want percentiles computed **per
position** (G/F/C — sharper but `players.position` is coarse and some players are mis-slotted) or
**vs all qualified players** (simpler, but bigs will dominate Finishing/Rebounding and guards
Playmaking)? I'd default to "all qualified" with a position toggle, but it's a real modeling choice
and changes how every shape reads.
