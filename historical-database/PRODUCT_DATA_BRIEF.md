# NBA/WNBA Data Platform — Product Discussion Brief

> **Purpose.** This is a hand-off for ideating what to *build* on top of the data we now have. It
> inventories the data assets, highlights capabilities that are newly possible (and that the current
> Streamlit app can't do), contrasts with the existing app, and ends with open product questions.
> Use it to drive a use-case / product-direction discussion — it is written for that, not as an
> engineering spec.

---

## TL;DR

There are now **two** data systems in this project:

1. **The live Streamlit app pipeline** (existing) — current-season, prediction/DFS-focused. Pulls
   fresh NBA stats into Supabase JSON-blob tables + makes runtime NBA API calls. Powers the app
   pages that exist today (Teams, Players, Predictions, Live, Passing, DK Optimizer).
2. **The historical database** (new, the subject of this brief) — a **normalized, multi-season,
   event-level warehouse** in Supabase covering **21 NBA seasons (2005-06 → 2025-26)** and **29 WNBA
   seasons (1997 → 2025)**, down to **play-by-play, shot coordinates, and reconstructed on-court
   lineups**. This is far deeper than anything the current app uses.

The big unlock: we can now answer **lineup-level** and **possession-level** questions — *who was on
the floor for every event*, *what shot zones a lineup generates*, *on/off splits* — across two
decades of NBA and three of WNBA. The current app has none of this.

---

## The data platform (what's queryable today)

All in **Supabase Postgres**. **`public` schema = NBA**, **`wnba` schema = WNBA** (identical shape).

| Asset | Grain | Coverage | What it enables |
|---|---|---|---|
| `play_by_play` | one row per event | NBA **27,028 games / ~13.5M events**; WNBA 6,668 games | Possession-level anything: shots (w/ x/y coords), assists (resolved to `assist_person_id`), subs, fouls, turnovers, scores |
| **`lineup_at_event`** (view) | event → on-floor 10 | All PBP games | **Who was on the floor at any moment.** On/off, lineup +/-, "while on floor" rates |
| **`pbp_lineup_stint`** | player on-court interval | NBA all 27k (**96.4% clean**), WNBA 6.6k (**90.3%**) | Stint/lineup tables; minutes; the engine behind `lineup_at_event` |
| **`shot_event`** (view) | one row per FGA | All PBP games w/ coords | **Shot zones** (restricted area / paint / mid / L+R corner 3 / above-break 3, heaves flagged) + shooter + assister + on-floor join |
| `game_rotation` | authoritative stints | **2,662 games** (partial) | Ground-truth in/out times + `usg_pct`/`pt_diff` (validation/spot-check set; see limitations) |
| `player_game_logs` / `team_game_logs` | per game | NBA 2005-06+; WNBA 1997+ | Box scores, trends, splits, rolling windows |
| `player_season_stats` / `team_season_stats` | per season (Base/Adv/Misc/Four Factors) | NBA 2005-06+; WNBA 1997+ | Multi-season trends, league context, rankings |
| `standings` (+ clutch) | per team-season | full | Records, clutch splits |
| `team_onoff` | on/off details | full | Player impact on team ratings |
| `synergy` (playtypes), `passing`, `drives` | per player/team | **NBA 2012-13/2013-14+ only** (tracking era) | Playtype efficiency, passing networks, drive stats. **WNBA has none of these.** |
| `players` / `teams` | dimensions | full | Canonical IDs, names, bios |
| `schedule` | per game | full | Matchups, dates |

**Note on accuracy:** `pbp_lineup_stint` lineups are *reconstructed* from PBP substitutions +
inferred starters (not scraped) — ~96% game-level exact for NBA. `game_rotation` is the *authoritative*
NBA source but only ~2,662 games are pulled (NBA throttles bulk access hard; see Limitations). For
almost all product purposes the reconstructed lineups are sufficient; game_rotation is the precision
upgrade for priority subsets.

---

## What's newly possible (and the current app can't do)

The current Streamlit app is **current-season, prediction- and DFS-centric**. The historical DB adds
four capability classes it simply doesn't have:

1. **Lineup-level analytics.** On/off splits, 5-man lineup +/-, "team behavior with player X on vs
   off the floor," lineup shot profiles — for *any* player, *any* season back to 2005-06.
   *(Demonstrated this session: Timberwolves corner-3 attempt rate with Julius Randle on vs off —
   10.86% vs 10.51%, computed from `shot_event` + `pbp_lineup_stint`.)*
2. **Shot-location intelligence.** Every FGA classified into NBA-standard zones from x/y coords,
   joinable to the on-floor lineup. "Shot diet by lineup," "corner-3 rate by player/team/season,"
   "restricted-area frequency vs a given on-court center," shot charts.
3. **Two decades of history.** Multi-season trends, era comparisons, career arcs, franchise
   trajectories — vs the current app's single live season.
4. **A full WNBA parallel.** Same schema, 29 seasons (1997-2025), including play-by-play and
   reconstructed lineups — an entire second product or audience, currently untouched by the app.

---

## The current Streamlit app (for contrast)

Multi-page app focused on **current-season prop analysis + fantasy/DFS**:

| Page | Does |
|---|---|
| Teams | Matchup analytics: OffRtg/DefRtg/Net/Pace, shooting zones, rebounding, starters/bench |
| Players | Game logs, synergy vs opp defense, zone shooting, prop comparison |
| Predictions | ML stat predictions, minute-normalization engine, injury adjustments, Vegas lines |
| Live | Live/historical box scores |
| Passing | Passing metrics |
| DK Optimizer | DraftKings lineup optimization (ILP) |

Strengths: live data, predictions, DFS tooling. **Gaps the historical DB fills:** no multi-season
depth, no lineup-level/on-off analytics, no shot-location-by-lineup, no WNBA, no possession-level
queries. The product question is how much to **extend the current app** vs **build new surfaces**
(historical explorer, lineup lab, WNBA app, a public website) on the richer warehouse.

---

## Use-case seeds (to react to / expand in discussion)

Grouped by theme — these are starting points, not a roadmap:

**Lineup & on/off**
- Player on/off dashboards (team ratings, shot diet, pace with X on vs off)
- 5-man lineup explorer: minutes, +/-, shot profile, best/worst combos
- "Who makes the corner 3 happen" — lineup → shot-zone attribution

**Shot & spatial**
- Shot charts by player/team/season/lineup; zone efficiency vs league baseline
- Shot-diet trends over 20 seasons (the league-wide 3-point/mid-range shift, per team)
- Matchup tendencies: what zones a defense concedes

**Historical / trends**
- Career arcs, franchise trajectories, era comparisons
- "This player's 2025-26 vs their best comparable season"
- Season-over-season team identity shifts

**WNBA**
- A standalone WNBA analytics surface (no equivalent exists in market at this depth)
- Cross-league comparisons where it makes sense

**Extending the existing app**
- Add historical context to the Predictions page (career/seasonal baselines)
- Lineup-aware DFS (stacking by on-floor synergy)
- Player page: add on/off + shot-zone + multi-season trend tabs

---

## Open product questions for the discussion

1. **Audience & surface.** Extend the current (personal DFS/prop) app, or build a *new* surface —
   historical explorer, "lineup lab," a public website (the stated long-term goal: FastAPI + Fly.io)?
2. **NBA-first or NBA+WNBA?** WNBA depth here is genuinely differentiated; is it a feature or its own
   product?
3. **Analytical vs predictive.** The current app leans predictive (ML/DFS). The historical DB leans
   descriptive/analytical (what happened, lineup truth). Which serves the goal more — or both?
4. **Depth vs polish.** We can go very deep (possession-level, lineup matchups). What's the minimum
   compelling slice for v1?
5. **Live vs historical blend.** How should "last night's game" (live pipeline) and "20 years of
   context" (this warehouse) coexist in one experience?

---

## Technical access notes (for grounding feasibility)

- **Supabase Postgres**, project "NBA App". `public` schema = NBA, `wnba` schema = WNBA (same tables/views).
- **IDs:** canonical NBA/WNBA `player_id` / `team_id` everywhere; join on IDs, never names. Timberwolves
  (`1610612750`) are the "home" team in the existing app's conventions.
- **Season format:** NBA `'2025-26'`, WNBA `'2025'`.
- **Key new views:** `lineup_at_event` and `shot_event` — **filter by `game_id`** (the on-floor / zone
  computations are per-game indexed; unfiltered scans over 13.5M events are slow).
  - `shot_event` columns: `shooter_id`, `assist_person_id`, `loc_x/loc_y`, `shot_value`, `shot_zone`
    (`'Restricted Area'|'In-Paint (non-RA)'|'Mid-Range'|'Left/Right Corner 3'|'Above-the-Break 3'|'Backcourt'`),
    `elapsed_sec`, `shot_result`.
  - `pbp_lineup_stint`: `(game_id, team_id, person_id, period, in_elapsed_sec, out_elapsed_sec)` — a
    player is "on the floor" at elapsed-time *t* if a stint has `in_elapsed_sec <= t < out_elapsed_sec`.
- **Per-game lineup quality flag** in `ingestion_log` (`endpoint='PBPLineup'`, status `ok`/`error`) —
  lets you restrict to perfectly-reconstructed games if needed.
- **Tracking caveat:** synergy/passing/drives exist **NBA 2013-14+ only**; **WNBA has none**. Older
  NBA seasons (pre-2010) have slightly lower lineup-reconstruction quality and no shot coords in the
  earliest years — verify coverage before leaning on pre-2010 spatial data.

---

## Known limitations (be honest in scoping)

- **`game_rotation` (authoritative lineups) is only ~2,662 games.** NBA's Akamai bot defense throttles
  bulk access to that endpoint hard — even via rotating residential proxies, the pool gets flagged
  after ~1,500-2,500 requests/day. A full backfill is a ~2-week daily-budget effort (deferred). The
  **reconstructed `pbp_lineup_stint` (all games, ~96%) is the working substitute** and is sufficient
  for nearly all product use.
- **Lineup reconstruction edge cases** (~4% NBA / ~10% WNBA games flagged): rare ambiguous moments and
  quiet starters; flagged games still have balanced data and are filterable.
- **WNBA** has no tracking-era advanced data (synergy/passing/drives) and rougher pre-2005 PBP.
- The **live app pipeline and this warehouse are separate** — combining "today's game" with historical
  context is a product/integration decision, not yet wired.
