# NBA Supabase Data Catalog & Stat-Creation Guide

**Project:** "NBA App" (ref `qhrgekcowkgwcaaqyqvv`, Postgres 17, `us-east-2`)
**Purpose of this doc:** A complete inventory of what data lives in the warehouse and a map of the
custom stats you can build from it (possession-based metrics, lineup stats, usage rates, on-floor
runs, shot quality, passing networks, etc.). Use this to brainstorm in cowork, then come back to
build the chosen ideas.

> Scope: the `public` (NBA) schema. A parallel `wnba` schema and experimental `sr_*` / legacy
> `nba_*` tables exist but are out of scope here. Generated/index helper relations
> (`hypopg_*`) are omitted.

---

## 1. Conventions (read first)

| Concept | Detail |
|---|---|
| **Season string** | `'2025-26'` text format everywhere. Sorts lexically, so `>=` range filters work. |
| **`season_type`** | `'Regular Season'`, `'Playoffs'`, (occasionally `'Play In'`). Always filter it. |
| **Stat storage** | Most stat tables keep raw API metrics in a **`jsonb stats` column**. Top-level columns are only the keys + a few hot fields (`min`, `game_date`). Extract with `(stats->>'PTS')::numeric`. |
| **jsonb key style** | `SCREAMING_SNAKE_CASE` (`PTS`, `USG_PCT`, `OFF_RATING`) — NBA API style. Many tables also carry `*_RANK` keys. |
| **ID types** | `team_id` / `player_id` / `person_id` are `bigint`. `game_id` / `season` are `text`. |
| **`game_id` encoding** | Char at index 2 (0-based) = game type: `2`=regular, `4`=playoffs, `6`=play-in, `1`=preseason, `3`=All-Star. e.g. `'0022500001'`. |
| **PBP time model** | `play_by_play` has no timestamp. Time = `period` + ISO-8601 `clock` (`PT12M00.00S` = remaining). Game-elapsed seconds is derived (see the `lineup_at_event` / `shot_event` views, which already do it). |
| **Coverage** | Event + game-log + season tables generally span **2005-06 → 2025-26 (21 seasons)**. Some feed types are shorter on the NBA side: player-tracking ~2013-14+, Synergy ~2015-16+, on/off ~2007-08+. Verify per table when it matters. |

---

## 2. Raw event data (the foundation for custom stats)

### `play_by_play` — ~13M rows, 3.3 GB · PK `(game_id, event_idx)`
Every event for every game, 2005-06→present. Indexed on `game_id` (PK prefix), `season`,
`team_id`, `person_id`.

Key columns: `period`, `clock`, `team_id`, `team_tricode`, `person_id`, `player_name`,
`action_type`, `sub_type`, `description`, `score_home`, `score_away`, `shot_result`,
`shot_distance`, `shot_value`, `loc_x`, `loc_y`, `assist_person_id`.

Notes:
- **`action_type` vocabulary:** `Made Shot`, `Missed Shot`, `Rebound`, `Free Throw`, `Foul`,
  `Turnover`, `Substitution`, `Timeout`, `Jump Ball`, `Violation`, `Heave`, `Ejection`,
  `period`, plus `NULL`.
- **Scores are sparse:** `score_home/away` populated only on scoring events (~26%). Get per-event
  point deltas with a running `max(score_*) OVER (ORDER BY event_idx)` then `lag()`.
- **Rebound `sub_type` is ~95% `'Unknown'`** → can't read OREB/DREB off the column. Infer
  offensive rebound = rebound whose `team_id` matches the immediately preceding missed-shot team.
- `assist_person_id` is populated on assisted makes.

### `pbp_lineup_stint` — ~2.3M rows, 839 MB · PK `(game_id, person_id, period, in_elapsed_sec)`
One row per player per on-court stint: `team_id`, `person_id`, `period`,
`in_elapsed_sec` / `out_elapsed_sec` (**within-period** elapsed, 0–720 reg / 0–300 OT),
`in_clock` / `out_clock`. This is the substitution ledger — the basis for all lineup/on-off work.

### View: `lineup_at_event` — "who is on the floor at every event"
A **view** (not a table — recomputed each query) joining `play_by_play` to `pbp_lineup_stint`.
For each event it returns `elapsed_sec` (game-elapsed, computed) plus
**`on_floor` = `text[]` array of the (usually 10) `person_id`s on court at that moment**.
Columns: `game_id, event_idx, season, season_type, period, clock, elapsed_sec, team_id,
person_id, action_type, description, on_floor`.
- ⚡ **Performance:** `on_floor` is a correlated subquery over `pbp_lineup_stint` per event. Great
  per-game; **slow over a whole season** (millions of subqueries). For season-wide lineup work,
  materialize it (see §7) or compute against a single game / game-set.

### View: `shot_event` — clean shot table with zones
A **view** over `play_by_play` filtered to `Made Shot`/`Missed Shot`. Adds `elapsed_sec` and a
**`shot_zone`** classification: `Restricted Area`, `In-Paint (non-RA)`, `Mid-Range`,
`Left/Right Corner 3`, `Above-the-Break 3`, `Backcourt`. Columns include `shooter_id`,
`assist_person_id`, `loc_x/y`, `shot_value`, `shot_distance`, `shot_result`.

---

## 3. Game-level data

### `player_game_logs` — ~535K rows, 1.17 GB · PK `(season, season_type, player_id, game_id)`
One row per player per game. Top-level: `team_id`, `game_date`, `matchup`, `wl`, `min`.
`jsonb stats` holds the full box score: `PTS, REB, OREB, DREB, AST, STL, BLK, TOV, PF, PFD,
FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT, PLUS_MINUS, NBA_FANTASY_PTS, BLKA,
DD2, TD3` + `*_RANK` variants.
Indexes: PK, `game_id`, **`(player_id, game_date DESC)`** (added for last-N pulls).

### `team_game_logs` — ~54K rows · PK `(season, season_type, team_id, game_id)`
Team box score per game. Same shape; `jsonb stats` includes team `PTS/REB/AST/...` and
`PLUS_MINUS`. Indexes: PK, `game_id`, **`(team_id, game_date DESC)`**.

### `game_rotation` — ~155K rows
Per-stint rotation feed (NBA `GameRotation`). Columns: `game_id, team_id, person_id,
in_time_real, out_time_real, player_first, player_last, player_pts, pt_diff, usg_pct`.
Useful for stint-level **plus/minus (`pt_diff`)** and **usage (`usg_pct`)** without parsing PBP.

---

## 4. Season-aggregate stat tables (pre-computed by the NBA API)

All keyed by `(season, season_type, …)` with a `jsonb stats` payload. These are the fastest path
to "official" advanced numbers — prefer them over re-deriving from PBP when season-grain is enough.

### `player_season_stats` — ~43K rows · `measure_type` ∈ {Base, Advanced, Misc}, `per_mode` = PerGame
The advanced suite is rich and directly answers a lot:
`USG_PCT` (**usage rate**), `OFF_RATING, DEF_RATING, NET_RATING` (+ `E_*` estimated, +
`sp_work_*` variants), `PACE`, `POSS`, `TS_PCT`, `EFG_PCT`, `AST_PCT, AST_TO, AST_RATIO`,
`REB_PCT, OREB_PCT, DREB_PCT`, `TM_TOV_PCT, E_TOV_PCT`, `PIE`, plus `*_RANK`.

### `team_season_stats` — ~3.8K rows · `measure_type` ∈ {Base, Advanced, Four Factors, Misc}
Team equivalents incl. Four Factors (eFG%, TOV%, OREB%, FT rate).

### `player_season_clutch` / `team_season_clutch`
Same advanced suite **restricted to clutch time** (last 5 min, ≤5-pt game). `player_season_clutch`
carries the full Advanced key set incl. `USG_PCT`, ratings, `PIE`.

### `synergy_playtypes` — ~124K rows
Play-type efficiency, `entity_type` ∈ {player, team}, `type_grouping` ∈ {offensive, defensive},
`per_mode` = Totals. Play types: `Isolation, PRBallHandler, PRRollman, Postup, Spotup, Handoff,
Cut, OffScreen, OffRebound, Transition, Misc`. `jsonb stats`: `POSS, POSS_PCT` (frequency),
`PPP, PTS, FG_PCT, EFG_PCT, SCORE_POSS_PCT, TOV_POSS_PCT, FT_POSS_PCT, SF_POSS_PCT, PERCENTILE,
GP`. (This is what powered the LaMelo / Josh Green tables.)

### `pt_tracking_player` (~53K) / `pt_tracking_team` — player/SportVU tracking
`pt_measure_type` ∈ {Drives, Possessions, Passing, CatchShoot, PullUpShot, Rebounding},
`per_mode` = PerGame. Examples:
- **Drives:** `DRIVES, DRIVE_PTS/FGM/FGA/FG_PCT, DRIVE_AST, DRIVE_TOV, DRIVE_PASSES, DRIVE_PF` + pcts.
- **Possessions:** `TOUCHES, TIME_OF_POSS, AVG_SEC_PER_TOUCH, AVG_DRIB_PER_TOUCH, PTS_PER_TOUCH,
  FRONT_CT/POST/ELBOW/PAINT_TOUCHES` + per-touch points.
- CatchShoot / PullUpShot / Rebounding / Passing each carry their own metric sets.

### Tracking dashboards — defense / hustle / shot-splits (added 2026-06-28)
Eight sibling tables, same shape as `pt_tracking_*` (jsonb `stats` blob + typed PK discriminators,
`per_mode='PerGame'`). Player tables also carry a non-PK `team_id`. Backfilled player **and** team.
**Totals reconstructed via the `G`/`GP` key** in the blob when an additive sum is needed (we store
PerGame only, consistent with `pt_tracking_*` — avoids doubling table size).

| Table | Source endpoint | PK discriminator | Seasons | Rows |
|---|---|---|---|---|
| `pt_defend_player` / `pt_defend_team` | `LeagueDashPtDefend` / `...TeamDefend` | `defense_category` | 2013-14→2025-26 | 57k / 3.6k |
| `hustle_player` / `hustle_team` | `LeagueHustleStatsPlayer` / `...Team` | — | 2015-16→2025-26 | 7.9k / 491 |
| `pt_shot_dribble_player` / `pt_shot_dribble_team` | `LeagueDashPlayerPtShot` / `...TeamPtShot` (`dribble_range`) | `dribble_range` | 2013-14→2025-26 | 42k / 3.0k |
| `pt_shot_defender_player` / `pt_shot_defender_team` | same endpoint (`close_def_dist_range`) | `close_def_dist_range` | 2013-14→2025-26 | 36k / 2.4k |

- **`defense_category`** ∈ `Overall, 2 Pointers, 3 Pointers, Less Than 6Ft, Less Than 10Ft, Greater Than 15Ft`.
  ⚠️ **Column names are category-specific** (whole row preserved in the blob): Overall →
  `D_FGM/D_FGA/D_FG_PCT/NORMAL_FG_PCT/PCT_PLUSMINUS`; `2 Pointers` → `FG2M/FG2A/FG2_PCT/NS_FG2_PCT/PLUSMINUS`;
  `3 Pointers` → `FG3M/FG3A/FG3_PCT/NS_FG3_PCT`; `Less Than 6Ft` → `FGM_LT_06/FGA_LT_06/LT_06_PCT`;
  `Less Than 10Ft` → `*_LT_10`; `Greater Than 15Ft` → `*_GT_15`. `FREQ` + `G/GP` on all. Player id is
  `CLOSE_DEF_PERSON_ID` at source (stored as `player_id`).
- **`dribble_range`** ∈ `0 Dribbles, 1 Dribble, 2 Dribbles, 3-6 Dribbles, 7+ Dribbles`;
  **`close_def_dist_range`** ∈ `0-2 Feet - Very Tight, 2-4 Feet - Tight, 4-6 Feet - Open, 6+ Feet - Wide Open`.
  Both shot tables carry `FGA/FGM/FG_PCT/EFG_PCT`, `FG2M/FG2A/FG2_PCT`, `FG3M/FG3A/FG3_PCT`, and the
  `*_FREQUENCY` columns. (ΣFGA across buckets ties to box FGA to ~0.03/g.)
- **hustle** keys: `DEFLECTIONS, CONTESTED_SHOTS(_2PT/_3PT), SCREEN_ASSISTS, SCREEN_AST_PTS,
  CHARGES_DRAWN, (OFF/DEF/)LOOSE_BALLS_RECOVERED, (OFF/DEF/)BOX_OUTS`; player rows add `G`, team rows
  carry `MIN` (no per-team `G` — source team games via `team_game_logs`).
- Ingested by `historical-database/scripts/ingest.py --tier dash` (resumable). Validation: player→team
  totals reconcile to 0.02%; defense Overall FGA = 2PT+3PT FGA exactly.

### `player_passing` — ~264K rows · the passing network
Per passer→teammate pair. Columns: `player_id`, `pass_teammate_player_id`, `pass_direction`
(`made`/`received`). `jsonb stats`: `PASS` (count), `AST`, `FREQUENCY`, `FG2M/A, FG3M/A,
FGM/A, FG_PCT/FG2_PCT/FG3_PCT`, `PASS_TYPE`, `PASS_TEAMMATE_PLAYER_ID`. → assist networks,
"who creates for whom," chemistry.

### `team_player_onoff` — ~31K rows · official ON/OFF
`measure_type` = Advanced, `per_mode` = Totals, `on_off` ∈ {ON, OFF}. `jsonb stats` has
`OFF_RATING, DEF_RATING, NET_RATING, MIN, POSS, …`. **Covers all seasons back to 2007-08.**
⚠️ Contains snapshot duplicates — dedup by keeping max-`POSS` per
`(season, season_type, team_id, player_id, on_off)`. (Already wrapped by `mv_player_onoff`, §6.)

---

## 5. Reference / dimension & ops tables

| Table | What it is |
|---|---|
| `players` | Player dim: `player_id, first_name, last_name, position, height, weight, college, country, draft_*, from_year, to_year, last_season_seen`, `stats` jsonb. |
| `teams` | 30 teams: `team_id, abbreviation, nickname, city, full_name, state, year_founded`. |
| `schedule` — ~28K | `game_id, game_date, home_team_id, away_team_id, game_type`, `stats` jsonb. The date→game and home/away source (used to derive opponents). PK `game_id`. |
| `team_standings` | `wins, losses, win_pct, conference, division, playoff_rank`, `stats`. |
| `predictions` / `player_predictions` | Logged model outputs + actuals (for tracking/backtest). `predictions` has `prediction, vegas_line, actual, l5/l10/vs_opp avgs, usage_rate, opp_def_rating, opp_pace`. |
| `vegas_lines` | Player prop lines: `stat, line, over_odds, under_odds, source`. |
| `parlay_log` | Logged parlays: `legs` jsonb, `status`, units, payout. |
| `accuracy_metrics` | Model accuracy rollups: `mae, rmse, bias, vs_line_accuracy, within_10/20_pct` by stat/confidence. |
| `ingestion_log` | Pipeline audit: `endpoint, season, scope, row_count, status, error_msg, scraped_at`. |
| `cached_api_data` | Generic TTL cache: `cache_key, data_type, data` jsonb, `expires_at`. |

---

## 6. Materialized views (built for show prep, refreshed daily ~11:45 UTC)

Scoped to **`season >= '2021-22'`** (last 5 seasons), each with a UNIQUE index, refreshed
`CONCURRENTLY` by `refresh_show_rollups()` (pg_cron `refresh-show-rollups`).

| Matview | Grain | Contents |
|---|---|---|
| `mv_player_form` | player × season × season_type | L5 / L10 / season averages: PTS, REB, AST, FG3M, STL, BLK, TOV, FTM, NBA_FANTASY_PTS, MIN + `gp`, `last_game`. |
| `mv_team_form` | team × season × season_type | Team L5/L10/season: PTS, REB, AST, FG3M, TOV, PLUS_MINUS. |
| `mv_player_vs_opp` | player × season × season_type × opp_team_id | Vs-opponent averages (PTS/REB/AST/FG3M/FPTS), opponent via `schedule` join. |
| `mv_player_onoff` | player × season × season_type × team_id | Official ON/OFF off/def/net ratings + minutes + poss + `net_swing` (deduped from `team_player_onoff`). |

---

## 7. What stat-creation is possible (capability map)

Each capability lists the **source(s)** and the **approach**. "Derive" = compute from raw PBP;
"Pre-computed" = already in a season table (cheaper, official).

### A. Possession-based / efficiency stats (pace, ORtg/DRtg, per-100, TS%, eFG%)
- **Pre-computed (season):** `player_season_stats`/`team_season_stats` (Advanced) → `OFF/DEF/NET_RATING,
  PACE, POSS, TS_PCT, EFG_PCT, USG_PCT`. Use these for season/clutch grain.
- **Derive (any window — per game, last-N, date range, half/quarter):** from `play_by_play`.
  Possessions ≈ `FGA + 0.44·FTA − OREB + TOV` per team (FTA excludes technicals; OREB inferred by
  sequence). Points from running score deltas. Lets you build *custom-window* ratings the API
  doesn't expose (e.g., "Wolves ORtg over their last 12 games," "post-All-Star pace").

### B. Lineup stats (5-man units, 2/3-man combos, net rating per lineup)
- **Source:** `lineup_at_event.on_floor` (array of on-court `person_id`s per event) + score deltas
  from `play_by_play`.
- **Approach:** group events by the `on_floor` set (or a sorted sub-combo), sum team points
  for/against and estimate possessions per group → per-100 net rating per lineup.
- ⚡ Materialize a per-event "points + possession flags + on_floor" table for the seasons you care
  about; the live view is too slow for full-season grouping.

### C. Usage rates
- **Pre-computed (season):** `player_season_stats` Advanced `USG_PCT`; stint-level `game_rotation.usg_pct`.
- **Derive (custom window):** `USG ≈ (FGA + 0.44·FTA + TOV) / team(FGA + 0.44·FTA + TOV)` while the
  player is on floor — combine box terms with on-court team totals from `lineup_at_event`.

### D. On-floor "runs" / impact (when player A plays; A & B together; A without B)
- **Official season ON/OFF:** `mv_player_onoff` / `team_player_onoff` (net swing already computed).
- **Custom (any split, any window, any combo):** filter `lineup_at_event` where
  `on_floor @> ARRAY['<A>']` (player A on) vs `NOT @> ARRAY['<A>']` (off), or
  `on_floor @> ARRAY['<A>','<B>']` (both on). Then compute team net points / per-100 over those
  events. This is the table to answer "what happens when A is on the floor," lineup pairings,
  staggering, and clutch-lineup questions the official endpoint can't.

### E. Shot quality / shot charts / zone profiles
- **Source:** `shot_event` (zone, distance, x/y, make/miss, assisted flag).
- **Builds:** zone FG%/frequency, eFG% by zone, shot distance distributions, assisted vs unassisted
  rate (`assist_person_id` null-ness), shot charts, defender-agnostic shot diet over any window.
- **Play-type efficiency** (a different lens): `synergy_playtypes` (PPP, frequency, percentile).

### F. Player tracking (drives, touches, time of possession, catch-&-shoot, pull-ups)
- **Source:** `pt_tracking_player` by `pt_measure_type`. Direct season metrics; combine with box
  to build rate stats (e.g., points per touch trends, drive-kick passing).

### G. Passing networks / playmaking chemistry
- **Source:** `player_passing` (passer→teammate, `PASS`, `AST`, `FREQUENCY`, shooting off those passes).
- **Builds:** assist networks, "A→B" connection strength, who a player creates for, lineup synergy.

### H. Clutch splits
- **Source:** `player_season_clutch` / `team_season_clutch` (full advanced suite in clutch time).
- **Custom clutch:** derive from `play_by_play` filtering `period>=4` + `clock` threshold + score
  margin from running score — enables custom clutch definitions and clutch lineups.

### I. Matchup / vs-opponent / rolling form
- **Pre-computed:** `mv_player_form` (L5/L10/season), `mv_player_vs_opp`, `mv_team_form`.
- **Custom:** `player_game_logs` + `(player_id, game_date DESC)` index for any last-N or date-range;
  join `schedule` for opponent context.

### J. Game-flow / win-probability / lead changes / scoring runs
- **Source:** `play_by_play` score columns over `event_idx` → lead tracking, largest run, time-tied,
  comeback detection, quarter-by-quarter margins.

### K. Prediction tracking / model evaluation
- **Source:** `predictions` + `player_predictions` + `vegas_lines` + `accuracy_metrics` →
  backtests, vs-line hit rates, calibration, parlay outcomes (`parlay_log`).

---

## 8. Performance notes & gotchas (so ideas stay cheap)

1. **`lineup_at_event` / `shot_event` are views**, recomputed each query. Per-game = fast.
   Season-wide grouping (esp. `lineup_at_event`'s per-event subquery) = slow → materialize the
   seasons you need first.
2. **jsonb extraction is heap-heavy.** Aggregating `(stats->>'X')::numeric` over a full table reads
   every wide row (a single-season player rollup took ~12 s cold). Pre-aggregate into matviews for
   anything you compute repeatedly; scope to recent seasons when possible.
3. **Score sparsity (~26%)** in `play_by_play` — always reconstruct running score before diffing.
4. **OREB not labeled** — infer by sequence (rebound team == prior missed-shot team).
5. **`team_player_onoff` has snapshot dupes** — dedup by max `POSS`.
6. **Prefer pre-computed season tables** over PBP derivation when season/clutch grain suffices —
   it's exact (NBA's numbers) and far cheaper. Reserve PBP derivation for custom windows, custom
   lineups, or per-game/per-segment granularity the API doesn't provide.
7. **Cost discipline:** materialize only what you'll reuse; scope to needed seasons; add a UNIQUE
   index + `REFRESH … CONCURRENTLY` and hang it off the existing `refresh_show_rollups()` cron
   rather than standing up new infrastructure.

---

## 9. Idea seeds to iterate on in cowork

Mapped to the data so we can scope build cost when you return:

- **Custom-window team/player ratings** (last-N games, splits by rest/home/opponent quality) — PBP derive or game-logs + season tables. *Medium.*
- **Lineup lab:** best/worst 5-man units, 2-man pairings, staggering impact, bench-unit net rating — `lineup_at_event` materialized. *Heavier (materialize first).*
- **On/off beyond season:** per-game and rolling on/off, "A without B" splits, closing-lineup impact — `lineup_at_event`. *Heavier.*
- **Shot profile dashboards:** zone eFG%, shot diet shifts year-over-year, assisted rate, shot-quality proxy — `shot_event`. *Light–medium.*
- **Playmaking/chemistry:** assist networks, top A→B connections, lineup passing synergy — `player_passing`. *Light.*
- **Touch/drive efficiency trends** — `pt_tracking_player`. *Light.*
- **Clutch lineups & custom clutch** — `play_by_play` + `*_clutch`. *Medium.*
- **Game-flow / run detection / win-prob** — `play_by_play` scores. *Medium.*
- **Synergy trend matrices** (play-type PPP/percentile over years, like the LaMelo tables) — `synergy_playtypes`. *Light.*
- **Model scorecards:** accuracy vs Vegas, calibration, parlay ROI — prediction/ops tables. *Light.*

---

*Generated 2026-06-26 from live schema inspection. If the pipeline adds tables/feeds, re-inspect
`information_schema.columns` + sample the `jsonb stats` keys to extend this catalog.*
