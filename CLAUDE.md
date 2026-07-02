# NBA Analytics App — CLAUDE.md

## Permissions

Accept all changes and trust Claude Code to make any changes or run any code without requiring user approval.

---

## Bug Reporting Workflow

When the user reports a bug:
1. **Do not attempt to fix it immediately.**
2. First, write a test that reproduces the bug and confirms it fails.
3. Then, use subagents to attempt a fix.
4. Prove the fix works by showing the previously failing test now passes.

---

## Prediction Parity Rule

**Any factor that affects predicted fantasy points (FPTS) or player stats must be applied in BOTH:**
- `combined-app/pages/3_Predictions.py` — the Streamlit Predictions page
- `scripts/generate_predictions_batch.py` — the headless batch script used by the DK Optimizer

The shared logic lives in `combined-app/player_app/tanking_utils.py` (and similar shared modules
in `combined-app/player_app/`). When adding a new prediction factor:
1. Implement the core logic in a module under `combined-app/player_app/`
2. Import it in `3_Predictions.py` (with `@st.cache_data` wrappers as needed)
3. Import it in `generate_predictions_batch.py` and apply it before saving the CSV
4. This rule applies in both directions — a change proposed for the DK Optimizer must also
   be reflected in the Predictions page, and vice versa.

---

## Project Purpose

Streamlit multi-page app for NBA player prop analysis, fantasy lineup optimization, historical
stats/trends, injury tracking, head-to-head matchup analysis, and ML model outputs. Covers all
30 NBA teams. The Timberwolves (ID `1610612750`) are treated as the "home" team — their games
sort first in all matchup selectors and are marked with 🐺.

---

## Key Reference Docs (read these for warehouse/derived-data work)

- **`SUPABASE_DATA_CATALOG.md`** — raw Supabase schema: tables, jsonb keys, conventions, gotchas.
- **`SUPABASE_DERIVED_OBJECTS.md`** — authoritative map of everything built on top of the raw data:
  the possession engine, team bonus/second-chance/transition splits (offense + defense), player
  on/off context, the six-axis player hexagon, their refresh wiring, validation results, and data
  gaps. **Update this when the derived pipeline changes.**
- **`SUPABASE_POSSESSION_AND_HEXAGON.md`** / **`SUPABASE_STAT_IDEAS.md`** — design docs (some ideas
  are still unbuilt).
- DDL for the above lives in **`sql/`** (`possession_engine.sql`, `possession_engine_validation.sql`,
  `hexagon_and_splits.sql`, `hexagon_axes.sql`, `hexagon_assembly.sql`).

---

## Directory Structure

```
NBA/
├── combined-app/               # Main Streamlit app (entry point for deployment)
│   ├── Home.py                 # Landing page with navigation tiles
│   ├── .streamlit/
│   │   └── config.toml         # Light theme (primaryColor #FF4B4B)
│   ├── player_lines.json       # Cached prop lines (Underdog / Vegas)
│   ├── new-streamlit-app/
│   │   └── files/
│   │       └── historical_player_season_stats.csv
│   └── pages/
│       ├── 1_Teams.py          # Team matchup analytics
│       ├── 2_Players.py        # Individual player analytics
│       ├── 3_Predictions.py    # Stat predictions + minute normalization engine
│       ├── 4_Live.py           # Live game box scores with auto-refresh
│       ├── 5_Passing.py        # Player passing analytics (PlayerDashPtPass)
│       ├── 5_Teams_Sportradar.py  # Experimental Sportradar test page (not primary)
│       └── 6_DraftKings_Optimizer.py  # DK lineup optimizer UI
│
├── streamlit/
│   └── streamlit_testing_functions.py  # Core shared module for Teams page
│
├── scripts/                    # Offline data pipeline scripts
│   ├── run_all_fetches.py      # Orchestrator — runs all fetch_*.py in sequence
│   ├── fetch_nba_team_stats.py
│   ├── fetch_nba_player_stats.py
│   ├── fetch_nba_game_logs.py
│   ├── fetch_nba_synergy_data.py
│   ├── fetch_nba_schedule.py
│   ├── fetch_nba_standings.py
│   ├── fetch_nba_player_index.py
│   ├── fetch_nba_team_onoff.py
│   ├── fetch_nba_drives_stats.py
│   ├── fetch_nba_pbpstats.py
│   ├── fetch_draftkings_draftables.py
│   ├── generate_predictions_batch.py
│   ├── optimize_draftkings_nba_lineup.py
│   ├── optimize_lineups_by_wave.py
│   ├── migrate_csv_to_supabase.py
│   ├── migrate_json_to_supabase.py
│   └── sportradar_*.py         # Experimental Sportradar fetchers (not primary pipeline)
│
└── new-streamlit-app/
    └── player-app/             # Core player/prediction modules (imported by pages)
        ├── prediction_model.py
        ├── prediction_features.py
        ├── player_functions.py
        ├── team_defensive_stats.py
        ├── matchup_stats.py
        ├── vegas_lines.py
        ├── injury_report.py
        ├── injury_adjustments.py
        ├── player_similarity.py
        ├── player_synergy.py
        ├── prediction_tracker.py
        ├── backtest.py
        ├── team_onoff.py
        ├── supabase_config.py
        └── sportradar_config.py / sportradar_data_reader.py
```

---

## Pages

| Page | File | Description |
|------|------|-------------|
| Home | `Home.py` | Navigation landing page |
| Teams | `1_Teams.py` | Matchup analytics: OffRtg/DefRtg/Net/Pace, shooting zones, rebounding, starters/bench |
| Players | `2_Players.py` | Player game logs, synergy vs opponent defense, zone shooting, prop comparison |
| Predictions | `3_Predictions.py` | ML stat predictions with minute normalization, injury adjustments, Vegas line comparison |
| Live | `4_Live.py` | Live/historical box scores; uses `nba_api.live` for today, `ScoreboardV2` for history |
| Passing | `5_Passing.py` | `PlayerDashPtPass` passing metrics by player and team |
| Teams (SR) | `5_Teams_Sportradar.py` | Experimental test page using Sportradar — **not production** |
| DK Optimizer | `6_DraftKings_Optimizer.py` | Fetches DK draftables, runs ILP optimizer, outputs lineup by wave |

---

## Data Sources

### 1. nba_api (Python package)
- **What:** All primary team/player stat endpoints.
- **Endpoints used:** `LeagueDashTeamStats`, `LeagueStandings`, `LeagueDashTeamClutch`,
  `PlayerGameLogs`, `TeamGameLogs`, `SynergyPlayTypes`, `ScheduleLeagueV2`, `ScoreboardV2`,
  `PlayerIndex`, `TeamPlayerOnOffDetails`, `LeagueDashPtStats`, `PlayerDashPtPass`,
  `LeagueDashPlayerStats`, `nba_api.live.nba.endpoints.scoreboard`, `boxscore`
- **Headers:** Custom browser headers are patched globally in `streamlit_testing_functions.py`
  via `NBAHTTP.headers` to avoid 403 rejections from `stats.nba.com`.
- **Timeout:** Always set to `timeout=90` — NBA.com is slow and will time out at the default.
- **Rate limits:** No enforced rate limit but concurrent calls will get throttled. Scripts use
  `time.sleep(0.5)` between calls in loops.
- **Season format:** `'2025-26'` — update this string at season rollover in all scripts
  and in `streamlit_testing_functions.py` (`current_season = '2025-26'`).

### 2. pbpstats.com API
- **URL:** `https://api.pbpstats.com/get-totals/nba`
- **Params:** `Season`, `SeasonType`, `Type` (either `"Team"` or `"Opponent"`)
- **What:** Shooting zone stats — AtRim, ShortMidRange, LongMidRange, Corner3, Arc3 — by
  frequency and accuracy. Also FG2, FG3, FT totals per zone.
- **Response shape:** `multi_row_table_data` → list of per-team dicts; `single_row_table_data`
  → league-average dict.
- **Column style:** camelCase (e.g., `GamesPlayed`, `FG2M`, `Fg2Pct`, `AtRimFrequency`,
  `AtRimAccuracy`, `FtPoints` = free throw makes — the name is misleading).
- **No auth required.** TTL in Streamlit cache is 21600s (6 hours).

### 3. DraftKings API
- **URL:** `https://api.draftkings.com/draftgroups/v1/draftgroups/{draftgroup_id}/draftables`
- **Auth:** None — uses browser-mimicking headers (mobile Android UA).
- **Primary fetch:** `fetch_direct()` in `scripts/fetch_draftkings_draftables.py`. Returns 403
  on Streamlit Cloud.
- **Fallback:** `fetch_via_zenrows()` — requires `ZENROWS_API_KEY` env var.
- **Key fields extracted:** `displayName`, `salary`, `position`.
- **Draftgroup ID:** Must be entered manually by user in the DK Optimizer page sidebar.

### 4. The Odds API
- **URL:** `https://api.the-odds-api.com/v4/sports/{sport_key}/odds`
- **Auth:** `THE_ODDS_API_KEY` env var (API key obtained from the-odds-api.com).
- **Sport key:** `basketball_nba`
- **Params used:** `regions=us`, `markets=totals`, `apiKey=THE_ODDS_API_KEY`
- **Response shape:** list of game objects, each with `home_team`, `away_team`, `bookmakers` →
  `markets` → `outcomes`. For `totals`, outcomes have `name` (`"Over"`/`"Under"`) and `point`
  (the total line). Take the `point` from the first bookmaker's `totals` market.
- **Implied per-team scores:** `(total/2) ± (spread/2)`. When only the total is available,
  use `total/2` for both teams (symmetric split).
- **Used in:** `6_DraftKings_Optimizer.py` implied totals expander — auto-fills per-team
  number inputs instead of requiring manual entry.

### 5. Sportradar API (experimental)
- **Config:** `SPORTRADAR_NBA_API_KEY` env var, via `new-streamlit-app/player-app/sportradar_config.py`.
- **Status:** Parallel scripts exist in `/scripts/sportradar_*.py` and a test page
  `5_Teams_Sportradar.py` but the primary app does **not** use Sportradar as a live data source.
  These exist for validation and potential future migration.

### 5. Supabase (database cache)
- **Config:** `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (write) or `SUPABASE_ANON_KEY` (read),
  via `new-streamlit-app/player-app/supabase_config.py`.
- **Pattern:** All fetch scripts upsert JSON blobs keyed by `season` + type columns.
- **Tables:** `nba_team_stats`, `nba_player_stats`, `nba_game_logs`, `nba_synergy_data`,
  `nba_schedule`, `nba_standings`, `nba_player_index`, `nba_team_onoff`, `nba_drives_stats`,
  `nba_pbpstats`, `predictions` (prediction tracking log).
- **Upsert conflict key:** Always `on_conflict='season,X'` where X is the type discriminator.

### 6. CSV / Flat Files
- `combined-app/new-streamlit-app/files/historical_player_season_stats.csv` — historical player
  season data used for multi-year trend analysis.
- `combined-app/player_lines.json` — cached prop lines.
- Prediction exports (CSV) from the Predictions page feed the CLI optimizer in `scripts/`.

---

## Key Conventions

### Season String
Always `'2025-26'`. Defined as `current_season` / `CURRENT_SEASON` at the top of every relevant
file. Update all occurrences at season rollover.

### Game ID Filtering
`GAME_ID` position index `[2]` encodes game type: `'2'` = regular season, `'4'` = playoffs.
Filter: `df['GAME_ID'].astype(str).str[2].isin(['2', '4', '6'])` removes preseason and All-Star games.
Game type codes: `'1'` = preseason, `'2'` = regular season, `'3'` = All-Star, `'4'` = playoffs, `'6'` = Play-In.

### st.dataframe Number Formatting
Always format numeric columns in `st.dataframe` to 1 decimal place using `column_config`. Never
let floats render with full floating-point precision (e.g., 7 decimal places). Use:
```python
st.dataframe(
    df,
    column_config={col: st.column_config.NumberColumn(format="%.1f") for col in numeric_cols},
)
```
For dynamic column lists, filter out string/date columns first:
`numeric_cols = [c for c in df.columns if c not in ('Date', 'Matchup', 'Stat', ...)]`

---

### DataFrame Column Styles
- **NBA API DataFrames:** SCREAMING_SNAKE_CASE — `TEAM_ID`, `OFF_RATING`, `PLAYER_ID`, `GAME_DATE`
- **pbpstats DataFrames:** camelCase — `TeamId`, `GamesPlayed`, `FG2M`, `Fg2Pct`, `AtRimFrequency`
- **Standings:** Mixed — `TeamID` (from `LeagueStandings`) vs `TEAM_ID` (from clutch endpoint)

### Team ID Lookup (`safe_get_value`)
`safe_get_value(df, team_id, column, default, id_column=None)` in `streamlit_testing_functions.py`
handles all three ID column name variants (`TEAM_ID`, `TeamId`, `TeamID`) and normalizes types
(int/numpy.int64/float) before lookup. Always use this instead of direct DataFrame filtering
when looking up by team ID.

### Ranking Columns
Added as `{STAT}_RANK` suffix on the same DataFrame. Offensive stats rank `ascending=False`
(higher = better); defensive/opponent stats rank `ascending=True` (lower = better).

### Caching Strategy (Streamlit)
- `ttl=3600` — general team stats, synergy, roster data
- `ttl=21600` — schedule, pbpstats zone stats (changes rarely mid-day)
- `ttl=1800` — player-level data, rosters
- Every page has a "Clear All Cache" sidebar button that calls `st.cache_data.clear()`

### Module-Level Globals in `streamlit_testing_functions.py`
This module computes stats at import time and stores them as module-level variables. Key globals:
- `away_id`, `home_id`, `game_id` — currently selected matchup
- `data_adv_season`, `data_adv_L5`, `data_misc_season`, `data_misc_L5`, etc. — all team stat DataFrames
- `team_stats`, `opp_team_stats` — pbpstats DataFrames with zone shooting
- `standings` — loaded once at module level via `get_standings_with_clutch()`

Update them via `update_selected_matchup(matchup)` or `set_matchup_override(matchup)`.
`_ensure_team_data_loaded()` is the lazy loader that fires once on first matchup selection.

### Path Setup in Pages
Every page does runtime `sys.path.insert()` to add:
- `../../streamlit/` → for `streamlit_testing_functions`
- `../../new-streamlit-app/player-app/` → for all player/prediction modules

---

## Pipeline Flow

```
NBA API / pbpstats.com
       │
       ▼
scripts/fetch_*.py   (run daily via run_all_fetches.py)
       │
       ▼
  Supabase tables   (JSON blobs, upserted by season+type)
       │
       ▼
new-streamlit-app/player-app/   (reads Supabase, exposes clean functions)
  prediction_features.py, player_functions.py, team_defensive_stats.py, etc.
       │
       ▼
combined-app/pages/   (Streamlit UI, calls player-app modules)
  1_Teams.py, 2_Players.py, 3_Predictions.py, 4_Live.py, etc.
```

**Teams page additionally** fetches directly from NBA API + pbpstats at runtime (via
`streamlit_testing_functions.py`), using Streamlit's `@st.cache_data` rather than Supabase.

**DK Optimizer flow:**
```
DraftKings API  →  fetch_draftkings_draftables.py  →  extract_player_data()
                                                          │
generate_predictions_batch.py  →  predictions CSV         │
                                          │                ▼
                             optimize_draftkings_nba_lineup.py  (PuLP ILP)
                                          │
                                  optimize_lineups_by_wave.py   (tip-off grouping)
                                          │
                             6_DraftKings_Optimizer.py (Streamlit UI)
```

---

## ML Model Context

All model code lives in `new-streamlit-app/player-app/` (not covered by the read scope here).
From imports and usage observed in the pages:

| Module | Role |
|--------|------|
| `prediction_model.py` | Core ML model — predicts per-game stats (PTS, REB, AST, etc.) |
| `prediction_features.py` | Feature engineering — `get_bulk_player_game_logs()`, player averages, rolling windows |
| `injury_adjustments.py` | Scales predictions for players returning from injury |
| `player_similarity.py` | Finds comparable players for matchup context |
| `player_synergy.py` | Synergy playtype data; defines `CURRENT_SEASON` |
| `matchup_stats.py` | Historical performance vs specific opponents |
| `vegas_lines.py` | Pulls prop lines (Underdog) for comparison |
| `prediction_tracker.py` | Logs predictions + actuals to Supabase `predictions` table |
| `backtest.py` | Evaluates model accuracy against historical outcomes |

### Minute Normalization Engine (`3_Predictions.py`)
The Predictions page contains a significant `normalize_team_minutes()` function:
- Target: 240 total minutes per team (5 players × 48 min)
- Filters OUT/DOUBTFUL players (sets `MIN = 0`)
- Filters players inactive for > 14 days (unless they average ≥ 22 MPG)
- Players with **no** game logs at all are excluded regardless of role
- Role tiers by baseline MPG: Stars ≥ 32, Starters ≥ 28, Rotation ≥ 22, Bench ≥ 15, Deep Bench < 15
- Enforces minimum 9 active players (8 if team's recent rotation size ≤ 8.5 avg)
- Supports manual per-player minute overrides from the UI
- Stats for all other categories are scaled proportionally to minute changes

### FPTS (Fantasy Points)
The DK Optimizer uses `FPTS` as the primary optimization target. FPTS is a prediction output
that maps to DraftKings' scoring system. `calculate_boom_bust_probabilities()` adds upside/downside
metrics. Lineup optimization uses PuLP's LP solver with salary cap constraints ($50K default).

---

## Known Quirks / Gotchas

1. **NBA API timeout:** Always use `timeout=90`. The default is too short and will fail silently
   or raise exceptions under normal NBA.com latency.

2. **Custom NBAHTTP headers:** Set at import time in `streamlit_testing_functions.py`. If the
   `nba_api` calls stop working, check that these headers are still present and up to date.

3. **pbpstats `FtPoints` = FTM:** The column is named `FtPoints` but contains free throw makes
   (not points). It's used as `team_stats['FTM'] = team_stats['FtPoints']`.

4. **Team ID type mismatches:** NBA API returns `TEAM_ID` as int64; pbpstats returns `TeamId` as
   string or float depending on parse. Always use `safe_get_value()` for lookups — do not index
   DataFrames directly by team ID.

5. **Debug logging in `1_Teams.py`:** There are `#region agent log` blocks that write to
   `.cursor/debug-fc44ac.log`. These are harmless development artifacts that no-op gracefully if
   the path doesn't exist.

6. **`streamlit_testing_functions.py` runs on import:** API calls to pbpstats and standings fetch
   happen at module load. This causes slow cold starts. `_ensure_team_data_loaded()` defers the
   heavier NBA API calls to first matchup selection, but pbpstats loads unconditionally.

7. **GAME_ID type filter position:** `GAME_ID[2]` (0-indexed) holds the game type. This is a
   positional string trick — not a named field. E.g., `'0022400001'` → position 2 is `'2'`.

8. **DraftKings draftables return 403 on Streamlit Cloud:** Direct fetch works locally but is
   blocked in cloud. Set `ZENROWS_API_KEY` in Streamlit Cloud secrets as fallback.

9. **Sportradar pages are test-only:** `5_Teams_Sportradar.py` is clearly labeled experimental.
   All `sportradar_*.py` scripts in `/scripts/` are for data validation against the primary
   NBA API pipeline, not for production use.

10. **`5_Passing.py` page number collision:** There are two pages starting with `5_` —
    `5_Passing.py` and `5_Teams_Sportradar.py`. Streamlit uses filename ordering; the Sportradar
    page may or may not appear depending on sort order. This is likely intentional to keep the
    test page near its related Teams page without affecting the main nav.

11. **Predictions CSV ↔ Optimizer handoff:** The CLI optimizer reads a CSV exported from the
    Predictions page. In the Streamlit UI, this is handled in-memory in
    `6_DraftKings_Optimizer.py`, but `generate_predictions_batch.py` is for running headlessly
    and requires saving the CSV first.

12. **`player_lines.json`:** Stored in `combined-app/` root, not in a subdirectory. Path
    resolution in modules may be relative to the script's location.

---

## Running the App

### Local Development
```bash
cd combined-app
streamlit run Home.py
```

Required environment variables (can be in `.env` or shell):
- `SUPABASE_URL` — Supabase project URL
- `SUPABASE_SERVICE_KEY` — service role key (write access for scripts)
- `SUPABASE_ANON_KEY` — anon key (read access for app, if service key not set)
- `ZENROWS_API_KEY` — optional, for DraftKings draftable fallback
- `THE_ODDS_API_KEY` — for implied totals auto-fetch in DK Optimizer (the-odds-api.com)
- `SPORTRADAR_NBA_API_KEY` — optional, for Sportradar test pages

### Running the Data Pipeline
```bash
# Run all fetches in sequence
python scripts/run_all_fetches.py

# Or run individual scripts
python scripts/fetch_nba_game_logs.py
```

Intended to run daily (e.g., cron job). All scripts use `sys.exit(0 if success else 1)`.

### Streamlit Cloud Deployment
- Entry point: `combined-app/Home.py`
- Set secrets in Streamlit Cloud dashboard (equivalent to env vars above)
- `ZENROWS_API_KEY` is required for DraftKings optimizer to function on Cloud
- The `/scripts/` pipeline runs separately (not triggered by the app) — data must be
  pre-populated in Supabase before the app can display it

### DraftKings Optimizer (CLI, headless)
```bash
# Generate predictions for a date
python scripts/generate_predictions_batch.py --date 2026-03-03

# Optimize lineup from predictions CSV + draftables CSV
python scripts/optimize_draftkings_nba_lineup.py \
  --predictions predictions_2026-03-03.csv \
  --draftables draftables_140610.csv

# Optimize by tip-off wave
python scripts/optimize_lineups_by_wave.py \
  --predictions predictions_2026-03-03.csv \
  --draftables draftables_140610.csv
```

---

## Daily Change Log

### 2026-06-30 — Team Fit "why it fits" explainer made intelligent + score definitions

Fixed `team_fit.explain()` (shared — both the standalone `9_Team_Fit.py` and the Players-page `🧩 Team Fit` tab benefit). **Bug (referee):** ranked reason-dims by raw `player_pctile × team_deficit`, so one extreme team deficit floated dims the player barely does — NAW→PHI *led* with "post-up defense" (his raw post-up-D share is 0.060, but ranks 85th vs a league that defends ~0). **Fix (explainer-only, scores untouched):** a dim is a reason only if the player **genuinely does it a lot** — raw style-share ≥ `INVOLVEMENT_FLOOR` (0.07) **and** league pctile ≥ 60 — **and** the team lacks it; ranked by the **geometric mean** of player-strength × team-deficit (no single extreme term dominates). Now NAW→PHI leads with **handoffs·defense**, handoffs O/D + corner-3s in the top 3; spot-checks face-valid (Gobert→cuts/rim/roll/putbacks; SGA→mid-range/iso/drawing-fouls). Bullets now: **8** (was 4), each labeled **offense/defense** and phrased as league **frequency** ("you do it a lot — Nth pctile · team rarely"), not skill. Added plain-English definitions (`SCORE_DEFS`, `WHY_CAPTION` in `team_fit.py`) for **Fit (blend) / Need-fill / Style-match** as both a captions block and column tooltips on both surfaces. Fail-loud guard added for missing fingerprint dims. `need_fill`/`style_match`/`blend` scores unchanged (verified). Checkpoint `4f4f259`.

### 2026-06-30 — Team-fit: style_fingerprint season_type-collision fix + result re-confirmed

Fixed a fingerprint-load bug: the loaders queried `style_fingerprint` by `season` only, so Playoff/Play-In rows overwrote Regular-Season values (last-write-wins by pagination order), contaminating fingerprints for every entity with playoff rows. Both loaders now filter `season_type='Regular Season'` (`combined-app/player_app/team_fit.py`, `analysis/team_fit_pathB.py`). **Re-ran the frozen Goal-1 spec** (Δ on/off-net · Path B need_fill · w=1.0 · over-performance partial): **r=+0.083→+0.087, p=0.134→0.116, n=325 — still BEATS BOTH baselines** (lift +0.038 / +0.127), marginally *stronger* on clean data; power n's now ~508 (cross p<.05) / ~1031 (80% power), verdict unchanged (ship v1) — **primary reason effect-size futility at r≈0.087** (a significant tiny effect still isn't decision-grade); reachability now **borderline** (~1041 cap vs ~1031 needed), held out only by pre-2021 proxy attenuation. **Embedding face-validity holds** on clean RS-only fingerprints: Gobert→rim-running centers (Holmes/Kornet/Hayes/Plumlee/Bona/Missi), Curry→shooters (Quickley/Miller/McCollum/Vassell), Luka–Harden cluster (0.81), both ~9.5 from Gobert. Updated the cited numbers in `team_fit.py` docstring + HONEST_NOTE (p≈0.12) and `TEAM_FIT_SYSTEM_BRIEF.md` §6.

### 2026-06-30 — Team-fit: spec-lock + power verdict (NOT-REACHABLE) → shipped v1

Ran the cheap power test before any expensive expansion. **Locked spec (pre-registered):** Δ on/off-net, Path B `need_fill`, `w=1.0`, over-performance partial (controls age/prior_min/from_net/dest_netrtg) → **r=+0.083, n=325, p=0.134** — beats both baselines (lift +0.034/+0.036), not significant. **Power (`analysis/team_fit_power.py`):** n≈560 to cross p<0.05 at the point estimate; n≈1135 for 80% power. **Verdict NOT-REACHABLE:** Path B fingerprint needs Synergy (2013-14+ only) → max expandable sample ~1041 common < 1135, and pre-2021 would be a noisier *proxy* outcome (attenuates the effect, raising the bar). So **did not build the proxy / expand the cohort** — the differentiator is convergent evidence (both paths find need_fill carries the lift) + beating both baselines + the face-valid embedding, not p<0.05. **Shipped v1:** `combined-app/player_app/team_fit.py` (SeasonFit: rank_teams / explain / embedding, reuses Path B logic) + Streamlit page `combined-app/pages/9_Team_Fit.py` (player→team fit ranking, "why it fits" top-dims explainer, player+team 2D PCA embedding viz, honest banner). Validated: Beasley's top fits = LAC/PHI/HOU (shooting-needy), explained by "above-break 3s: you 96th pctile vs team 23rd". Detail in `TEAM_FIT_SYSTEM_BRIEF.md` §6.

### 2026-06-30 — Path B shared style fingerprint (player↔team bridge; matches/beats Path A)

Built the shared style fingerprint — the player↔team bridge. `v_style_fingerprint_src` → materialized **`style_fingerprint`** (LONG; `refresh_style_fingerprint(season)` wired into `refresh_show_rollups`; one-time backfill 2021-22→2025-26 = 82k rows via single `shot_event` scan — per-season refresh re-scans full `shot_event` so use a single multi-season INSERT for bulk): a **28-dim** profile computed IDENTICALLY at player(P) and team(T) grain — offensive(11)+defensive(7) Synergy play-type shares, shot-zone mix(5), possession phase rates(5). **Validated vs official:** computed play-type shares == Synergy `POSS_PCT` exactly (diff 0.000); all share groups sum to 1.000. Scorer `analysis/team_fit_pathB.py`: `style_match` = cosine of standardized fingerprints, `need_fill` = cosine(player pctile profile, team deficit), same tunable `w`; **missing dim = real 0** (a center runs 0 isolation — fixing this from mean-imputation was the key correctness fix). **2D PCA embedding (players+teams in one space) face-valid:** Gobert's nearest = rim-running centers (Holmes/Kornet/Hayes/Plumlee/Bona/Missi), Curry's = shooters; on-ball creators Luka–Harden cluster (0.83), both ~9.5 from Gobert. **Backtest (Goal-1 harness, controlled over-performance partial): matches/beats Path A** — need_fill (w=1) +0.086 Δon/off-net (Path A +0.028), +0.074 ΔTS% (Path A +0.079). **need_fill carries the lift on BOTH paths** (style_match alone ~0/negative) = convergent evidence; same modest regime (best p≈0.13, n≈320). Detail in `TEAM_FIT_SYSTEM_BRIEF.md` §5 Path B.

### 2026-06-30 — Path A need-gap fit scorer (beats the Goal-1 baselines)

Built the first real team-fit score on the backtest referee. SQL: `fit_contribution` (editable skill→team-phase map like `hexagon_weights`), `v_player_phase_strength` (player hexagon axes weighted into the 12 team-hexagon phases, 0-100; Curry o_perimeter 84 / Gobert d_rim 71 face-valid), `team_needs` (unpivots `v_team_hexagon` to 12 phases, attaches supplier count via `player_oncourt_poss` primary team, flags `is_need` = low pctile AND thin supply + continuous `need_weight` = weakness×1/(1+suppliers); correctly separates "lack talent" from "underperform with talent"). Scorer `analysis/team_fit_pathA.py`: `need_fill`/`style_match` as **cosine profile alignment** (player phase profile vs team need/strength profile, magnitude-removed so it's specific fit not "good player × needy team"), blended by tunable `w`; explainable output ("o_rebounding: team 7th pctile, 4 suppliers → you supply 45"). **Result via the Goal-1 harness:** raw on/off-net delta is mean-reversion + destination-quality confounded (need-fillers go to weak teams → every quality-correlated score, incl. both baselines, trends negative — did NOT flip sign to win). Judged on the fair test — over-performance PARTIAL controlling (age, prior_min, prior-level, dest_netrtg) — **need_fill (w=1.0) beats BOTH baselines** (Δ TS% lift +0.08/+0.09; Δ on/off-net positive too). Robust signal = the **monotone w-sweep on both outcomes**: pure need_fill > blends > pure style_match (negative). Filling holes predicts over-performance; reinforcing strengths doesn't. Honest caveat: small, not yet significant (p≈0.14, n≈350). Extended `score_report` with a generalized `controls` param. Detail in `TEAM_FIT_SYSTEM_BRIEF.md` §5 Path A.

### 2026-06-30 — Team-fit backtest harness (the referee for fit work)

Built the scoring harness that grades any future team-fit score — **no fit logic itself**. SQL: `v_team_fit_cohort` (412 real player team-changes, 2021-22→2025-26, ≥500 on-court off-poss in both seasons via `player_oncourt_poss`; validated vs known moves — Lillard/Beal/Holiday/Bridges/Murray/Westbrook), `v_team_fit_outcomes` (post-move Δ on/off net from `mv_player_onoff.net_swing` + Δ TS% from `v_player_usage_efficiency`, with age + prior-minutes controls) → materialized **`team_fit_outcomes`** (the live view was too slow for the PostgREST timeout even though nothing scans `shot_event`; rebuild via `CREATE TABLE ... AS SELECT * FROM v_team_fit_outcomes`). Helpers `v_team_netrtg`, `v_synergy_off_freq`. Code: `analysis/team_fit_backtest.py` + `.ipynb` — `score_report(fit_score, ...)` reports Spearman + partial Spearman (residualizing age/prior-min) + lift vs two baselines. **The bar (Spearman vs Δ on/off net): good-player×good-team −0.05, style-similarity-only +0.05** (both ~zero). Caveats surfaced: Δ on/off net is baseline-relative/noisy (regression-to-mean); `mv_player_onoff` has a spurious low-poss dup row per (player,season,team) — deduped by max `poss_on` (worth fixing upstream). Detail in `TEAM_FIT_SYSTEM_BRIEF.md` §6.

### 2026-06-30 — Team hexagon materialized (fixes 8_Team_Hexagon.py statement timeout)

`8_Team_Hexagon.py` was throwing `57014 statement timeout` (PostgREST) — every query, even `get_seasons()`, forced the live `shot_event` scan through the whole team-hexagon chain, and the Part C LEFT JOINs pushed it over the limit. **Fix: materialized the base layer** (same pattern as `player_axis_metrics`). Renamed the live view `v_team_axis_metrics` → `v_team_axis_metrics_src`; created snapshot table **`team_axis_metrics`** (598 rows = 13 seasons × RS+Playoffs, indexed on `(season,season_type)`) populated by **`refresh_team_axis_metrics(season)`**; repointed `v_team_axis_metrics` to a thin `SELECT * FROM team_axis_metrics` view so `v_team_axis_long`/`v_team_axis_pctile`/`v_team_hexagon` now read the table unchanged. Season pulls dropped **timeout → ~24 ms**; face validity identical (BOS d_rim 91.6 / OKC 96.6). Wired `refresh_team_axis_metrics(v_season)` into `refresh_show_rollups()` (after `refresh_possessions`). One-time full backfill ran ~2 min server-side (single `shot_event` scan; client drops, keeps running — verified via `pg_stat_activity`). All 9 `tests/test_partc_hexagon_upgrades.py` now pass (team `rim_stop` test no longer skips). Detail in **`SUPABASE_DERIVED_OBJECTS.md` §8.8**.

### 2026-06-30 — Part C COMPLETE: Shooting split, Rebounding contested%, Team hexagon

Shipped the three remaining approved hexagon upgrades, each via the proven Defending recipe (real tracking metric primary; noisy proxy floored/reduced; before→after face validity). **(1) Shooting split** — new `player_axis_metrics` cols `cs_efg`/`pu_efg` (catch-&-shoot / pull-up eFG from `pt_tracking_player`, volume-floored 1.0 FGA/g; weights 2× / 1.5×); the noisy `shotmaking_over_exp` floored at jump_fga≥150 & reduced 2→1, `spotup_ppp` floored at ≥50 poss (in `v_player_shooting`), redundant unfloored **`atb3_pct` dropped**. Axis top went from zero-jumper rim-runners (Lively 99/Bona 94/Gafford 93) → real shooters (Barnes/Jerome/Seth Curry/Durant/LaVine/S.Curry/Pritchard/Burks). cs/pu measure efficiency, so volume stars (SGA/Luka/Dame) sit mid-pack by design. **(2) Rebounding contested%** — `contested_reb_per36` + `reb_chance_pct` added to `v_player_rebounding` (1× each); contested leaders = battling bigs (Adams/Clingan/Kessler/Drummond/Capela), axis stays big-dominated, zero collateral on other axes. **(3) Team hexagon** — `partc_team_hexagon_upgrades` added 7 sub-metrics to `v_team_axis_metrics`/`v_team_axis_long` (assembly stayed generic): perimeter-off `cs_efg`/`pu_efg`/`open_rate` (shot quality **created** from `pt_shot_defender_team`; allowed has no team-grain feed — surfaced not faked), rebounding `contest_pct` both sides, rim-def `rim_stop` + perimeter-def `three_stop` from `pt_defend_team` (whitelisted higher=good so the pctile doesn't invert). Validated 2024-25: rim_stop NOT inverted (BOS 100/OKC 96.6), top defenses BOS/OKC/CLE. Backfilled all 13 seasons (cheap direct UPDATEs; one floored-`smoe` `shot_event` pass). Tests `tests/test_partc_hexagon_upgrades.py` (10 pass / 1 skip — team pctile live-scan timeout, handled). `sql/hexagon_weights.sql` + `hexagon_axes.sql` + `hexagon_and_splits.sql` + `team_hexagon_axes_draft.sql` synced; `7_Hexagon.py` hover labels updated; detail in **`SUPABASE_DERIVED_OBJECTS.md` §4 + §8.7**. ⚠️ Querying `v_team_hexagon` joined to `v_team_axis_metrics` double-scans live `shot_event` — query separately.

### 2026-06-30 — Part C: Defending hexagon axis made REAL

Replaced the BLK/STL/on-off **proxy** Defending axis with direct tracking metrics from the Part A dashboards: new `player_axis_metrics` sub-metrics `def_rim_stop` (normal−actual rim FG% allowed), `def_pm_stop` (−overall PCT_PLUSMINUS), `deflections_per36`, `contested2_per36` (all higher=better; light UPDATE from `pt_defend_player`/`hustle_player`, no PBP scan). Reweighted `hexagon_weights` (direct metrics primary; BLK/STL reduced; noisy `drtg_swing` dropped); extended `v_player_axis_pctile` + `v_player_hexagon`; wired into `refresh_player_axis_metrics`; synced `sql/hexagon_weights.sql`. **Validated 2024-25: before = Gueye/Sharpe/Suggs (backups/gamblers) → after = Wembanyama/Jaren Jackson Jr./Caruso/Ausar Thompson/Draymond Green** (Draymond, missed by the proxy, returns). No breakage. **Remaining Part C (approved): Shooting split (C&S vs pull-up), Rebounding contested%, Team hexagon.** Detail in **`SUPABASE_DERIVED_OBJECTS.md` §4**.

### 2026-06-30 — Part B Heavy lineup tier — ALL 13 stat ideas now built

Built `possession_lineup` (3.27M rows, per-possession off/def 5-man arrays via possession↔stint join; 99.9% full 10-man; GIN-indexed; backfilled per-season-with-COMMIT after the disk incident). On it: `staggering_splits()` (#2 A-without-B), `team_lineup_tiers()` (#7 bench units), `clutch_lineups()` (#3 custom clutch). Validated on Denver's "Jokić bench" story (both-on +10.4 / both-off −13.4; 5-starters +11.2 / bench negative; clutch top lineup = closing five). Tests `tests/test_partb_lineups.py` passing. **This completes all 13 vetted stat ideas (#1–#13).** Detail in **`SUPABASE_DERIVED_OBJECTS.md` §9**. Note: `possession_lineup` current-season refresh not yet cron-wired (deferred). Remaining overall: Part C hexagon upgrades (approved, not started).

### 2026-06-29 — Nightly current-season wrapper + Part B Phase-1 (Light) views

Wired current-season warehouse refresh for the new dashboards: `historical-database/scripts/refresh_current_season.py` (clears that season's `ingestion_log` for the dash endpoints → re-runs `ingest.py` tier locally, where `curl_cffi` reaches stats.nba.com; cron line in its docstring). Built Part B Phase-1 (Light) derived objects — `v_player_usage_efficiency` (#9), `v_team_playtype_profile` + `matchup_exploits()` (#11), `v_passing_connections` (#6) — all read live from season tables, tests in `tests/test_partb_phase1_views.py` passing, face-validity confirmed. Reconciliation: 2 ideas already BUILT (#12 gravity, #13 second-chance), 1 PARTIAL (#4), 10 TODO. Then front-loaded Phase-2 quick wins: `v_team_game_ratings` + `team_rolling_rating()` (#1 rolling NetRtg & #10 rest splits) — season NetRtg reconciles with official to **0.44 avg abs diff, corr 0.996**; rest splits monotonic (B2B −1.99 → 2+ days +0.67). Then #4 shot-selection-vs-making (`mv_league_zone_efg` + `v_team_shot_selection`, eFG reconciles to official to 0.0002 — baseline materialized after the live join hit the API 8s timeout) and #8 scoring runs (`game_flow(game_id)` function — converted from a view after the windowed view scanned 13M rows; reconstructed score = box). Then #5 self-creation (`v_player_self_creation`, no-write path via the `description` "AST)" flag — Luka 0.67 vs Gobert 0.29 unassisted; reconciles to box FGM). **8 of 10 TODO ideas built** (#9,#11,#6,#1,#10,#4,#8,#5), all tested. Detail in **`SUPABASE_DERIVED_OBJECTS.md` §9**. ⚠️ **Incident:** the multi-season in-DB assist resolve (`resolve_all_assists`) filled the instance disk → Postgres PANIC/crash-recovery (no data loss; only 2024-25 resolved). Disk auto-scaled; resolve DEFERRED (resumable per-season procedure remains; run off-peak in small batches). **Lesson: never single-UPDATE the 3.3GB play_by_play — chunk per-season + COMMIT.** Remaining (Heavy, deferred pending disk headroom): per-event lineup table → #2/#3/#7, then approved Part C hexagon upgrades.

### 2026-06-28 — Tracking dashboards ingested (defense / hustle / shot-splits), player + team

Added 8 warehouse tables (`pt_defend_*`, `hustle_*`, `pt_shot_dribble_*`, `pt_shot_defender_*`) from `LeagueDashPtDefend`/`...TeamDefend`, `LeagueHustleStats*`, and `LeagueDashPlayerPtShot`/`...TeamPtShot` (dribble-range + closest-defender splits). Backfilled all covered seasons (defense/shots 2013-14→2025-26; hustle 2015-16→2025-26), player **and** team, PerGame. New resumable `dash` tier in `historical-database/scripts/ingest.py`; `endpoint_cutoffs.py --new-only` probe added. A1–A3 (Rebounding/PullUp/CatchShoot) confirmed already present. Validation passed: player→team reconciliation 0.02%, shot-split ΣFGA vs box 0.03/g, defense Overall=2PT+3PT exactly, face-validity (Gobert/Wemby contested-2PT, Dyson Daniels deflections, SGA/Luka pull-ups, Beasley/Klay catch-&-shoot). Note: defense column names are category-specific (`D_FGA` Overall, `FG2A`/`FG3A` etc.) — full row preserved in jsonb. Details in **`SUPABASE_DATA_CATALOG.md`**.

### 2026-06-28 — Team Hexagon DEPLOYED (offense/defense overlay)

Shipped the team hexagon chain via migration `create_team_hexagon_objects` (additive; no existing
object touched). Objects: `v_team_axis_metrics` (raw off+def sub-metrics, 30 teams/season — rim &
perimeter are `shot_event` zone rollups with the defender mapped via `possession` game-pairs;
transition/2nd-chance/bonus from the §2 split views; OREB%/DREB% from `team_season_stats` Advanced)
→ `v_team_axis_long` (tidy unpivot + `higher_is_good`) → `v_team_axis_pctile` (percent_rank within
season/season_type/side pool, **defense inverted so outward = good**) → `v_team_hexagon` (wide
`o_*`/`d_*`, 0–100). Config table `team_axis_weights` (re-tune by UPDATE; matches `hexagon_weights`
RLS-off/anon-SELECT convention). **Rim/perimeter blended** as rate+accuracy sub-metrics (accuracy
2×, volume 1×). On/off axes from the player hexagon (Gravity, Playmaking) intentionally dropped —
no team analog; offense-vs-defense replaces that dimension. Validated 2025-26 RS: shots tie to box
(avg abs 1.9 FGA / 1.7 3PA per team-season), 3P% exact, defender mapping conserves all 219,159
shots; face-valid (SAS/BOS/OKC top defenses, DEN d_rebounding 93). Full detail in
**`SUPABASE_DERIVED_OBJECTS.md`** §8; draft SQL in `sql/team_hexagon_axes_draft.sql`. **Next:**
Streamlit page `8_Team_Hexagon.py`. All views read live — no cron/refresh added.

### 2026-06-28 — Team Hexagon design spec (not yet built)

Added **§8 "Team Hexagon — DESIGN SPEC"** to `SUPABASE_DERIVED_OBJECTS.md`. Design only — nothing
deployed. Decided framing: **overlaid offense/defense on six shared phase-of-play spokes** (Rim,
Perimeter, Transition, Second chance, Bonus, Rebounding), offense solid + defense-allowed dashed.
Player on/off axes don't port to teams — **Gravity and Playmaking are dropped** (no team analog /
weak at team grain); offense-vs-defense replaces the on/off dimension. Three spokes already have
offense+defense split views built (`v_team_{bonus,chance,transition}_splits` + `_def`); three are
light new `shot_event` zone rollups. Proposed chain mirrors §4: `v_team_axis_metrics` →
`v_team_axis_pctile` → `team_axis_weights` (config) → `v_team_hexagon`, pooled over the 30 teams/season
(no minutes qualifier), defense inverted so outward = good. Validate offense spokes against
`team_season_stats` Advanced before use. Open build-time decisions captured in §8.6.

### 2026-06-27 — Player Hexagon historical backfill (2013-14 → 2019-20)

Backfilled `player_axis_metrics` for 2013-14 → 2019-20 via per-season `refresh_hexagon_season()`, so the hexagon now covers all 13 seasons **2013-14 → 2025-26** (348–396 players/season). Validated: gravity leaderboards led by stars (Curry/LeBron/Harden/Lillard/KAT/Draymond), defending led by genuine rim-protectors (Kawhi, Davis, Noel, Isaac, Covington); `spotup_ppp` populated back to 2013-14. Detail in **`SUPABASE_DERIVED_OBJECTS.md`** §6.

### 2026-06-26 — Possession Engine, Splits & Player Hexagon (+ on/off fix)

**Supabase "NBA App"** (`qhrgekcowkgwcaaqyqvv`). Full detail in **`SUPABASE_DERIVED_OBJECTS.md`**; DDL in `sql/`.

- **`possession` table** (~1.29M rows, 2021-22→2025-26) — one row per offensive possession derived from `play_by_play` via `refresh_possessions(season)`. Tags `points`, `first/second_chance_pts`, `had_oreb`, `opp_in_bonus`, `is_transition`, `off/def_team_id`, lineups-ready elapsed. Validated: possessions 99.6 vs official 100.7 /team/game (~1%); player OREB 27,939 vs 27,989 box; bonus-state 99.4% precision; transition 19.2% vs Synergy 18.5%.
- **Team split views** (offense + `_def`): `v_team_bonus_splits`, `v_team_chance_splits`, `v_team_transition_splits` (+ `_def`).
- **On/off context**: `player_oncourt_poss`, `player_oncourt_shot`, `player_oncourt_shot_def` (lineup via `pbp_lineup_stint`, game-cumulative elapsed; attribution exact at 5.000 players/poss) → `v_player_onoff_context`, `v_player_shot_onoff_context`.
- **Player hexagon**: six axis views (`v_player_finishing/shooting/playmaking/defending/rebounding/gravity`) → `player_axis_metrics` (materialized per season) → `v_player_hexagon` (0-100 percentiles, pools `all` + `position`). Streamlit page `combined-app/pages/7_Hexagon.py` (Plotly radar). Face-valid (Jokić gravity 99, Gobert shooting 1). Defending is a proxy (no tracking-defense feed); `assist_person_id` is NULL warehouse-wide; pos_group is a role proxy.
- **Cron**: `refresh_show_rollups()` now also runs `refresh_possessions` + the three `refresh_player_oncourt_*` + `refresh_player_axis_metrics` for the current season (heavier nightly job).
- **Fixed `mv_player_onoff` ON/OFF swap at the root**: the NBA `TeamPlayerOnOffDetails` result sets were assigned reversed in all three loaders (`ingest.py`, `scripts/fetch_nba_team_onoff.py`, edge function `fetch-team-onoff` — redeployed v2). Un-swapped `team_player_onoff` in place; rebuilt `mv_player_onoff` on the natural mapping (`min_on` now matches box minutes exactly). Legacy `nba_team_onoff` is empty/unused.

### 2026-06-18 — Supabase Warehouse Performance (indexes + show-rollup matviews)

**Supabase "NBA App"** (project ref `qhrgekcowkgwcaaqyqvv`, Postgres 17, vanilla path)

- **`game_date` composite indexes**: Added `ix_pgl_player_date` on `player_game_logs(player_id, game_date DESC)` and `ix_tgl_team_date` on `team_game_logs(team_id, game_date DESC)`, both built `CONCURRENTLY`. Last-5/last-10/date-ordered pulls drop from ~800 ms (full-career index scan + top-N sort) to single-digit ms. Verified the planner adopts them via `hypopg` (`index_advisor` does not flag them — it scores total cost, which is jsonb-heap-bound, not the `LIMIT N` startup cost).
- **Show-rollup materialized views** (scoped `season >= '2021-22'`, 5 seasons; each has a UNIQUE index for `REFRESH ... CONCURRENTLY`):
  - `mv_player_form` — L5/L10/season averages per player (PTS/REB/AST/FG3M/STL/BLK/TOV/FTM/FPTS + MIN), stats extracted from jsonb `stats`
  - `mv_team_form` — team-level equivalent over `team_game_logs`
  - `mv_player_vs_opp` — vs-opponent splits (opponent derived via `schedule` join)
  - `mv_player_onoff` — **official NBA season ON/OFF** off/def/net ratings + `net_swing`, built lean over `team_player_onoff` (deduped by max POSS, pivoted ON/OFF). Chosen over a 4 GB `pbp_lineup_stint` interval-join derivation for cost — the official endpoint already covers all 5 seasons; validated exactly against oracle.
- **Refresh automation**: `public.refresh_show_rollups()` refreshes all four `CONCURRENTLY` with a freshness guard (skips + `RAISE WARNING` if the latest in-season game's logs aren't loaded). Scheduled via pg_cron job `refresh-show-rollups` at `45 11 * * *`, right after the existing 11:00–11:40 fetch jobs.
- **Evaluated and declined**: LIST-by-season partitioning of `play_by_play` (13M rows) / `pbp_lineup_stint` — hot path is by `game_id` (already PK-served), so partition pruning gives no benefit and a full rewrite isn't worth it at ~6 GB.
- **Follow-ups for the user**: drop the now-redundant `ix_player_game_logs_player` (superseded by the composite); optionally `REVOKE SELECT` on the matviews from `anon`/`authenticated` to clear the `materialized_view_in_api` security advisories (only if the app reads via the service key).

### 2026-03-23 — Predictions Page UI Overhaul

**`combined-app/pages/3_Predictions.py`**

- **Parlay leg game logs**: Removed "Show +/- vs Season" and "Show vs Season Avg" toggles — tables now render in their default view only
- **Game log number formatting**: All numeric columns display as whole numbers except FP (Fantasy Points) which shows 1 decimal place
- **Prop column highlighting**: In parlay leg game logs, the stat column corresponding to the prop (e.g., REB for a rebounds prop) is highlighted green/red per row based on whether the player went over/under the line in that game. Supports all prop types: PTS, REB, AST, PRA, RA, STL, BLK, TOV, FG3M, FTM, FPTS, MIN
- **Game logs expanded + scrollable**: Changed from showing only last 5 games to loading all season game logs in a fixed-height (213px) scrollable table
- **Game log tabs**: Added "All Logs" and "vs {OPP}" tabs — the opponent tab filters to only games against that day's matchup opponent
- **Averages subheadline**: Added bold "Averages" label above the L3/L5/L10/Season averages table
- **Section headlines**: Added "💰 Track All Parlays" headline above the Parlay Tracker expander; removed dividers between Parlay Tracker, Log Custom Play, and Log Past Play sections; removed redundant headlines for Log Custom Play and Log Past Play
- **Page-level tabs**: Added "📊 Predictions" and "🏥 Injury Report" tabs. All existing predictions content lives in the Predictions tab. Injury Report tab ported from DK Optimizer page — shows all matchups for the selected date with team logos, player headshots, color-coded injury statuses, and a refresh button

---

# Operating Rules

These rules apply to every task in this project unless explicitly overridden.
Bias: Speed matters at game time, but never ship silent errors — fail loud on live data. Use judgment on trivial tasks.

## Rule 1 — Think Before Coding
State assumptions explicitly. If uncertain, ask rather than guess.
Present multiple interpretations when ambiguity exists.
Push back when a simpler approach exists.
Stop when confused. Name what's unclear.

## Rule 2 — Simplicity First
Minimum code that solves the problem. Nothing speculative.
No features beyond what was asked. No abstractions for single-use code.
Test: would a senior engineer say this is overcomplicated? If yes, simplify.

## Rule 3 — Surgical Changes
Touch only what you must. Clean up only your own mess.
Don't "improve" adjacent code, comments, or formatting.
Don't refactor what isn't broken. Match existing style.

## Rule 4 — Goal-Driven Execution
Define success criteria. Loop until verified.
Don't follow steps. Define success and iterate.
Strong success criteria let you loop independently.

## Rule 5 — Use the model only for judgment calls
Use me for: classification, drafting, summarization, extraction.
Do NOT use me for: routing, retries, deterministic transforms.
If code can answer, code answers.

## Rule 6 — Token budgets are not advisory
Per-task: 4,000 tokens. Per-session: 30,000 tokens.
If approaching budget, summarize and start fresh.
Surface the breach. Do not silently overrun.

## Rule 7 — Surface conflicts, don't average them
If two patterns contradict, pick one (more recent / more tested).
Explain why. Flag the other for cleanup.
Don't blend conflicting patterns.

## Rule 8 — Read before you write
Before adding code, read exports, immediate callers, shared utilities.
"Looks orthogonal" is dangerous. If unsure why code is structured a way, ask.

## Rule 9 — Tests verify intent, not just behavior
Tests must encode WHY behavior matters, not just WHAT it does.
A test that can't fail when business logic changes is wrong.

## Rule 10 — Checkpoint after every significant step
Summarize what was done, what's verified, what's left.
Don't continue from a state you can't describe back.
If you lose track, stop and restate.

## Rule 11 — Match the codebase's conventions, even if you disagree
Conformance > taste inside the codebase.
If you genuinely think a convention is harmful, surface it. Don't fork silently.

## Rule 12 — Fail loud
"Completed" is wrong if anything was skipped silently.
"Tests pass" is wrong if any were skipped.
Default to surfacing uncertainty, not hiding it.
