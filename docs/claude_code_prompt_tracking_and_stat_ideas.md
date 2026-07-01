# Claude Code task — NBA tracking-dashboard ingestion + remaining stat ideas

> Paste this whole file into Claude Code from the repo root (`NBA/`). It is the spec; follow it
> end to end. Work in phases, validate each phase against official numbers before moving on, and
> **fail loud** — never report a phase "done" if any (endpoint, season) silently returned empty.

You are extending Jack's NBA analytics warehouse (Supabase Postgres `qhrgekcowkgwcaaqyqvv`) and its
Python ingestion pipeline. The goal is to ingest a set of NBA.com tracking dashboards for **both
players and teams**, across all seasons they exist, then build out the still-unbuilt analytical
ideas on top.

---

## 0. Read first (do not skip)

- `CLAUDE.md` — conventions, operational rules, the parity rule, the Daily Change Log format.
- `SUPABASE_DATA_CATALOG.md` — raw schema; **add your new tables here when done.**
- `SUPABASE_DERIVED_OBJECTS.md` — the possession engine, team/player hexagons, splits. Several
  "stat ideas" are already built here; reconcile before rebuilding (see Part B).
- `SUPABASE_STAT_IDEAS.md` — the vetted idea backlog with build sequencing (Part B).
- `historical-database/scripts/ingest.py` — **the loader you are extending.** Note the helpers
  `rows_from_df(...)`, `upsert(table, rows, pk=[...])`, `already_done(...)`, `log(...)`, the
  `THROTTLE` sleep, and the per-season/per-season_type loop. Tracking already lives here.
- `historical-database/scripts/nba_session.py` — **the transport you must reuse:**
  `patch_nba_session()`, `safe_call(EndpointClass, _all_frames=False, timeout=90, **kwargs)`
  (retry/backoff + curl_cffi Chrome impersonation + empty-body session reset), and
  `stats_json_via_zenrows(...)` as the ZenRows fallback. **Do not write new HTTP code.**
- `historical-database/scripts/endpoint_cutoffs.py` — the read-only probe for "earliest season an
  endpoint returns data." Extend and run it FIRST to learn coverage before any backfill.

### Ground truth that changes the scope (verify, then exploit)

The pipeline **already** ingests `LeagueDashPtStats` for Player and Team into `pt_tracking_player`
and `pt_tracking_team`, keyed `(season, season_type, {player_id|team_id}, pt_measure_type, per_mode)`,
looping over a `PT_MEASURES` list (see `ingest.py` ~line 204). **Three of the requested dashboards
are just `LeagueDashPtStats` measure types** — confirm whether `Rebounding`, `CatchShoot`, and
`PullUpShot` are already in `PT_MEASURES`:
- If present and populated → no new ingestion, just confirm coverage and move on.
- If missing → add them to `PT_MEASURES` and backfill. **This is the whole job for those three.**

The genuinely new endpoints (not in `ingest.py` today) are: **defense dash, hustle, shots-by-dribble,
shots-by-closest-defender.**

---

## 1. Bug/Build workflow (per CLAUDE.md)

- Before writing a loader for a new endpoint, **probe it once live** (via `safe_call`) and print the
  returned columns. Endpoint column names drift; build the `id_map`/extraction from what you observe,
  not from this doc. This doc's column lists are a guide, not gospel.
- For each derived stat (Part B), reproduce the intended check as a **failing test first**, then build.
- Make **surgical** changes — extend `ingest.py` and the existing helpers; match their style. Don't
  refactor unrelated code.
- Heavy backfills: prefix a **separate** `SET statement_timeout=0;` statement for SQL, and run
  multi-season ingestion as the existing scripts do (resumable via `already_done`). **Never run two
  heavy backfills concurrently.** If a DB call drops, check `pg_stat_activity` before re-firing.
- When done: update `SUPABASE_DATA_CATALOG.md`, add a dated `CLAUDE.md` Daily Change Log entry, and
  show the validation output.

### Debugging conventions (follow on every error or failed validation)

When something breaks — a failing test, an empty endpoint, a validation that doesn't tie out, a
dropped connector — work it like this, and narrate each step:
1. **Surface the issue.** State plainly what failed and the exact error / mismatch (don't bury it,
   don't silently retry).
2. **Investigate it thoroughly.** Find the root cause — read the relevant code, inspect the actual
   data/columns, reproduce it — before proposing any fix.
3. **Propose multiple potential solutions.** List more than one plausible fix.
4. **Assess and recommend.** Say which option is the recommended path and why (trade-offs).
5. **Try the recommended fix first**, then fall back to the others in order if it doesn't work.
6. **Repeat until squashed.** Loop steps 1–5 until the issue is fully resolved and the test/validation
   passes — don't move on with a partial or unexplained fix.

---

## PART A — Ingest the dashboards (players AND teams)

For every dashboard: ingest **Player and Team**, **PerGame** (and also **Totals** where a downstream
rate needs it — your call, but be consistent and document it), for **all seasons the endpoint
covers**. Run the extended `endpoint_cutoffs.py` probe first to set per-endpoint season floors
(tracking ≈ 2013-14+, hustle ≈ 2015-16+ — confirm, don't assume). Current season refreshes nightly;
historical seasons are a one-time backfill.

Use the established storage convention: a jsonb `stats` blob per row plus discriminator columns in
the PK, upserted with `on_conflict`. Reuse `pt_tracking_player`/`pt_tracking_team` where the source
is `LeagueDashPtStats`; create new sibling tables (one player + one team each) for the new endpoints,
mirroring that shape. Name tables clearly (suggested below — adjust to match catalog conventions).

### A1. Rebounding — `LeagueDashPtStats` (`pt_measure_type="Rebounding"`)
- Add `Rebounding` to `PT_MEASURES` if absent; lands in `pt_tracking_{player,team}`.
- **Targets:** contested rebounds, rebound chances, rebound chance % — i.e. `REB_CONTEST`,
  `REB_CHANCES`, `REB_CHANCE_PCT` (plus the `OREB_*` / `DREB_*` contest/chance variants and
  `AVG_REB_DIST`). Keep the full blob.

### A2. Pull-Up Shooting — `LeagueDashPtStats` (`pt_measure_type="PullUpShot"`)
- Add to `PT_MEASURES` if absent.
- **Targets:** `PULL_UP_PTS, PULL_UP_FGM, PULL_UP_FGA, PULL_UP_FG_PCT, PULL_UP_FG3M, PULL_UP_FG3A,
  PULL_UP_FG3_PCT, PULL_UP_EFG_PCT`. Derive 2PM/2PA/2P% downstream (`FGM−FG3M`, `FGA−FG3A`).

### A3. Catch & Shoot — `LeagueDashPtStats` (`pt_measure_type="CatchShoot"`)
- Add to `PT_MEASURES` if absent.
- **Targets:** `CATCH_SHOOT_PTS, CATCH_SHOOT_FGM, CATCH_SHOOT_FGA, CATCH_SHOOT_FG_PCT,
  CATCH_SHOOT_FG3M, CATCH_SHOOT_FG3A, CATCH_SHOOT_FG3_PCT, CATCH_SHOOT_EFG_PCT`. Derive 2PT downstream.

### A4. Defense dash — `LeagueDashPtDefend` (player) / `LeagueDashPtTeamDefend` (team)
- Loop the `defense_category_abbreviation` param over **Overall, 3 Pointers, 2 Pointers,
  Less Than 6Ft, Less Than 10Ft, Greater Than 15Ft** (confirm exact accepted strings via a probe).
- **Targets:** `D_FGM, D_FGA, D_FG_PCT` (Defensive FG made/att/%), plus `FREQ`, `NORMAL_FG_PCT`,
  `PCT_PLUSMINUS`. Store `defense_category` as a discriminator column in the PK.
- Suggested tables: `pt_defend_player`, `pt_defend_team`
  PK `(season, season_type, {player_id|team_id}, defense_category, per_mode)`.

### A5. Hustle — `LeagueHustleStatsPlayer` / `LeagueHustleStatsTeam`
- **Targets:** `DEFLECTIONS, SCREEN_ASSISTS, SCREEN_AST_PTS, CONTESTED_SHOTS_2PT,
  CONTESTED_SHOTS_3PT, CONTESTED_SHOTS, LOOSE_BALLS_RECOVERED` (keep `CHARGES_DRAWN`, box-outs too).
- Coverage starts later than tracking (≈2015-16) — confirm with the probe; skip empty seasons cleanly.
- Suggested tables: `hustle_player`, `hustle_team`
  PK `(season, season_type, {player_id|team_id}, per_mode)`.

### A6. Shots by dribbles — `LeagueDashPlayerPtShot` / `LeagueDashTeamPtShot` (`dribble_range_nullable`)
- Loop `dribble_range` over **0 Dribbles, 1 Dribble, 2 Dribbles, 3-6 Dribbles, 7+ Dribbles**
  (confirm exact strings via probe; these map to the URL `DribbleRange` values).
- **Targets:** `PTS?`/`FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, EFG_PCT` and the directly-provided
  `FG2M, FG2A, FG2_PCT` + the `*_FREQUENCY` columns. (2PT is provided here, so use it AND cross-check
  it equals `FGM−FG3M` as a validation.)
- Suggested tables: `pt_shot_dribble_player`, `pt_shot_dribble_team`
  PK `(season, season_type, {player_id|team_id}, dribble_range, per_mode)`.

### A7. Shots by closest defender — `LeagueDashPlayerPtShot` / `LeagueDashTeamPtShot` (`close_def_dist_range_nullable`)
- Loop `close_def_dist_range` over **0-2 Feet - Very Tight, 2-4 Feet - Tight, 4-6 Feet - Open,
  6+ Feet - Wide Open** (confirm exact strings via probe).
- **Targets:** same shot-column set as A6.
- Suggested tables: `pt_shot_defender_player`, `pt_shot_defender_team`
  PK `(season, season_type, {player_id|team_id}, close_def_dist_range, per_mode)`.

### A8. Wire-up & backfill
- Add each new (endpoint, scope) to the `endpoint_cutoffs.py` probe and to `ingest.py`'s resumable
  loop with `already_done(...)`/`log(...)` guards, exactly like the existing tracking block.
- Backfill all covered seasons; ensure the **current season is added to the nightly job** that
  already refreshes the warehouse (find where the nightly fetch/cron lives — `scripts/run_all_fetches.py`
  and/or the pg_cron `refresh_show_rollups()` chain — and extend it, don't stand up new infra).
- Create the Supabase tables via `apply_migration` (additive only; RLS/grants consistent with the
  existing `pt_tracking_*` tables) and document them in `SUPABASE_DATA_CATALOG.md`.

### A9. Validation gates for Part A (must pass, show the numbers)
- **Player→team reconciliation:** team-level totals reconcile to the sum of that team's players
  (where the endpoint is additive, e.g. hustle deflections, contested rebounds).
- **Shot splits sum to the whole:** across A6 dribble buckets, ΣFGA per player ≈ total FGA; same for
  A7 defender buckets. Report avg abs diff per player-season.
- **Defense dash sanity:** a team's `Overall` `D_FGA` is in a believable band vs opponent FGA; the
  2PT+3PT category attempts ≈ Overall attempts.
- **Spot face-validity:** Gobert/Wembanyama top contested-2PT and deflections-adjacent metrics;
  catch-&-shoot leaders are known spot-up shooters; pull-up leaders are on-ball creators.

---

## PART B — Build the remaining stat ideas

Read `SUPABASE_STAT_IDEAS.md` and `SUPABASE_DERIVED_OBJECTS.md` together. **Several ideas are already
built** by the possession engine / hexagons — do not duplicate. First produce a short reconciliation:
for each of the 13 ideas, mark **BUILT / PARTIAL / TODO** with the object that covers it (e.g. #13
second-chance value ≈ `v_team_chance_splits`; transition splits exist; #4 expected-eFG underlies the
hexagon). Then build the TODO/PARTIAL ones, following the doc's own Phase 1→3 sequencing and shared
building blocks. The new Part A feeds unlock some of them directly:
- #5 self-creation & #6 passing network now have a real assist source path: the assister is in
  `play_by_play.description` as `(LastName N AST)` (the `assist_person_id` column is NULL
  warehouse-wide). Parse `(\w[\w.'-]* \d+ AST)` and resolve last name → `player_id` against the two
  rosters in that game; cross-check the running AST count vs the box. Treat surname collisions
  explicitly (fail loud / flag, don't guess).
- #11 matchup-exploit finder is a Synergy join (data already ingested).

For every derived object: scope to needed seasons, materialize anything reused, hang refreshes off
the existing cron, validate against the official season tables (show the check), and update
`SUPABASE_DERIVED_OBJECTS.md` + the Daily Change Log.

---

## PART C — (Optional, propose before building) hexagon upgrades unlocked by Part A

These new feeds fix documented hexagon gaps. **Propose a plan and get my OK before changing any
hexagon object** (the Defending axis is currently a labelled proxy):
- **Defending axis → real:** `LeagueDashPtDefend` `D_FG_PCT`/`PCT_PLUSMINUS` + hustle deflections /
  contested shots replace the BLK/STL/on-off proxy.
- **Shooting axis → sharper:** catch-&-shoot and pull-up splits separate spot-up vs self-created
  shooting.
- **Rebounding axis → sharper:** contested-rebound % and rebound chances add effort context beyond
  raw OREB%/DREB%.
- Team hexagon (`SUPABASE_DERIVED_OBJECTS.md` §8) can gain the same, plus a closest-defender-based
  "shot quality created/allowed" angle.

---

## Conventions & operational rules (must obey)

- Season string is `'2025-26'` text; always filter `season_type`. Tracking covers `Regular Season`,
  `Playoffs`, `Play In` (confirm which the endpoints return).
- nba_api: **always `timeout=90`**, go through `safe_call` (it patches headers + retries + ZenRows
  fallback on throttle). Keep `THROTTLE` sleeps between calls; never hammer concurrently.
- Stats live in jsonb `stats`, keys SCREAMING_SNAKE_CASE; extract as `(stats->>'X')::numeric`.
- Writes use the service-role Supabase client; additive migrations only — do not drop/recreate
  production objects or alter `refresh_show_rollups()` casually.
- **Parity rule:** if any new stat ends up feeding predicted FPTS/stats, apply it in BOTH
  `combined-app/pages/3_Predictions.py` and `scripts/generate_predictions_batch.py`.
- Fail loud. "Completed" is wrong if any (endpoint, season) was skipped silently or any validation
  was bypassed.

## Deliverables
1. Extended `endpoint_cutoffs.py` + a printed coverage matrix for the new endpoints.
2. Extended `ingest.py` (+ any small new modules) with resumable loaders for A1–A7, player & team.
3. Additive Supabase migrations creating the new tables; `SUPABASE_DATA_CATALOG.md` updated.
4. Current-season nightly wired in; historical backfill run and row-counts shown per table/season.
5. Part B: the BUILT/PARTIAL/TODO reconciliation, then the new derived objects with validation.
6. Tests for the derived stats (and the assist parser) that encode intent, shown passing.
7. Daily Change Log entries; `SUPABASE_DERIVED_OBJECTS.md` updated for any derived work.

## Ask me before
- Changing any hexagon object (Part C).
- Any non-additive schema change, or touching `refresh_show_rollups()` structure.
- Choosing Totals-vs-PerGame storage if it materially affects table size or downstream rates.

## Suggested first commands
```bash
# 1) Learn coverage for the new endpoints (read-only, no writes)
python historical-database/scripts/endpoint_cutoffs.py --seasons 2024-25 2018-19 2015-16 2013-14
# 2) Probe one new endpoint's columns live before coding its loader (in a python REPL):
#    from nba_session import patch_nba_session, safe_call; import nba_api.stats.endpoints as ep
#    patch_nba_session(); print(safe_call(ep.LeagueDashPtDefend, season="2024-25",
#        season_type_all_star="Regular Season", defense_category="Overall", per_mode_simple="PerGame").columns.tolist())
```
