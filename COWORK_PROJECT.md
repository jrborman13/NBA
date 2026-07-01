# Cowork Project — NBA Analytics App

Paste **Project description** into the project's description field and **Instructions**
into the custom-instructions field. Connect the `NBA/` folder so Claude can read the code and docs.

---

## Project description

A Streamlit multi-page app for NBA analysis — player prop research, fantasy/DFS lineup
optimization, historical trends, injury tracking, head-to-head matchups, and ML model outputs —
backed by a Supabase (Postgres) warehouse with a custom possession engine and a six-axis player
"hexagon." Built and maintained by Jack, who hosts *Locked On Wolves* and goes live within ~10
minutes of every Timberwolves game, so the app's job is to aggregate stats fast for pre- and
post-game show prep. The same warehouse is the foundation for planned WNBA / NFL / PGA tools and
Underdog DFS work. The Timberwolves (team_id `1610612750`) are the "home" team throughout.

---

## Instructions

You are helping Jack build and maintain his NBA analytics app (a Streamlit app on a Supabase
Postgres warehouse). He's a strong Python/SQL data person and a credentialed Wolves media member;
speed matters at game time, but never ship silent errors on live data. He prefers **suggested
options with backups**, and **clarifying questions when you're not confident** — but just proceed
when the path is obvious.

### Read these first (in the connected folder)
- **`CLAUDE.md`** — project conventions, directory map, data sources, gotchas, and a Daily Change
  Log. This is the source of truth for how the app is built; follow it.
- **`SUPABASE_DATA_CATALOG.md`** — raw warehouse schema (tables, jsonb keys, coverage, conventions).
- **`SUPABASE_DERIVED_OBJECTS.md`** — everything built on top of the raw data: the possession
  engine, team bonus/second-chance/transition splits (offense + defense), player on/off context,
  the six-axis hexagon, refresh wiring, validation results, and data gaps. Keep this current when
  the derived pipeline changes.
- **`SUPABASE_POSSESSION_AND_HEXAGON.md`** / **`SUPABASE_STAT_IDEAS.md`** — design docs (many ideas
  still unbuilt). **`sql/`** holds the DDL.

### Stack & where things live
- **App:** `combined-app/` (entry point `combined-app/Home.py`; pages in `combined-app/pages/`).
  Run locally: `cd combined-app && streamlit run Home.py`. Deps in root `requirements.txt`.
- **Warehouse:** Supabase project ref `qhrgekcowkgwcaaqyqvv` (Postgres 17). Use the Supabase MCP.
- **App↔DB:** `combined-app/player_app/supabase_config.py` (`get_supabase_client()` = anon read;
  `get_supabase_service_client()` = service-role write). Env: `SUPABASE_URL`, `SUPABASE_KEY`, optional
  `SUPABASE_SERVICE_KEY`, `THE_ODDS_API_KEY`, `ZENROWS_API_KEY` — in a `.env` at the repo root.
- **Data sources:** `nba_api`, pbpstats.com, DraftKings, The Odds API, Supabase. Historical ingest
  lives in `historical-database/scripts/ingest.py`; nightly fetches run via pg_cron + edge functions.

### Key conventions (see CLAUDE.md for the full list)
- Season string is `'2025-26'` text; update at rollover. Always filter `season_type`.
- Stats live in a `jsonb stats` column — extract with `(stats->>'PTS')::numeric`; keys are
  SCREAMING_SNAKE_CASE. `game_id` char index 2 encodes game type (`2`=reg, `4`=playoffs, `6`=play-in).
- `nba_api` calls use `timeout=90` and patched browser headers. Format `st.dataframe` numerics to
  1 decimal via `column_config`.
- **Prediction parity rule:** any factor affecting predicted FPTS/stats must be applied in BOTH
  `combined-app/pages/3_Predictions.py` and `scripts/generate_predictions_batch.py`.
- **Bug workflow:** reproduce with a failing test first, then fix with subagents, then show the test
  passing. Make surgical changes; match existing style; fail loud.

### The derived warehouse (possession engine + hexagon)
Built on `play_by_play` / `shot_event` / `pbp_lineup_stint`, scoped 2013-14 → 2025-26 (engine
supports 2005-06+). All validated against official numbers (possessions ~1% of official, OREB exact,
etc. — see `SUPABASE_DERIVED_OBJECTS.md`). Refresh chain per season:
`refresh_possessions → refresh_player_oncourt_poss → refresh_player_oncourt_shot →
refresh_player_oncourt_shot_def → refresh_player_axis_metrics`, wrapped by
`refresh_hexagon_season(season)`; backfill many with `CALL backfill_hexagon_seasons(ARRAY[...])`.
The nightly `refresh_show_rollups()` (pg_cron 11:45 UTC) runs these for the current season.
Hexagon grades are **config-driven**: edit `hexagon_weights` (one `UPDATE`, all seasons, no
re-backfill) or use the live editor on the Hexagon page; normalization is isolated in
`v_player_axis_pctile`.

### Operational rules (important — these bite)
- **Long DB ops drop the connector.** Heavy refreshes/backfills exceed the MCP/API statement
  timeout. Prefix a separate `SET statement_timeout=0;` statement, and for multi-season or
  unattended work run it from **pg_cron** (survives client disconnects) rather than a single live
  call. Never run two heavy backfills concurrently. If a call dropped, check `pg_stat_activity`
  before re-firing, and `pg_terminate_backend(pid)` a stuck one.
- `shot_event` is a recomputed view over all of `play_by_play` — joining several shot-scanning
  views live is too slow; that's why the hexagon is materialized into `player_axis_metrics`.
- **Known data gaps:** `assist_person_id` is NULL warehouse-wide (assister only in description text);
  no tracking-defense feed (Defending is a proxy — blocks/steals weighted heaviest); `pos_group` is
  a role proxy (NBA `position` is sparse); pre-2013-14 lacks tracking/Synergy (some Shooting/
  Playmaking sub-metrics null). `mv_player_onoff` had an ON/OFF source swap that is now fixed.

### Working style & guardrails
- Validate derived numbers against the official season tables before trusting them; show the check.
- Prefer materializing for anything reused; scope to needed seasons; hang refreshes off the existing
  cron rather than standing up new infra.
- Don't drop/recreate production objects or modify `refresh_show_rollups` casually; make surgical,
  reversible changes and explain trade-offs.
- When the derived pipeline changes, update `SUPABASE_DERIVED_OBJECTS.md` and add a dated entry to the
  `CLAUDE.md` Daily Change Log so the next session has context.
- Outputs/deliverables go in the connected folder; share files so Jack can open them directly.

### Good first asks for this project
"Add a new derived stat from the possession table," "build/extend a Streamlit page," "backfill the
hexagon to 2005-06," "re-tune the hexagon weights," "investigate a metric that looks off vs official
numbers," "prep a fast post-game stat view for tonight's Wolves game."
