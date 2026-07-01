# Ingestion Runbook — NBA Historical Database

Execution plan for the backfill. Read alongside `ENDPOINTS_TO_SCRAPE.md` (what to pull) and
`schema.sql` (where it lands). Apply `schema.sql` to Supabase first.

## Order of operations
Run strictly top-to-bottom — later tiers depend on earlier ones for join keys / game enumeration.

1. **Dimensions**
   - `teams` ← `nba_api.stats.static.teams` (no API call).
   - `players` ← `PlayerIndex` looped over every season; upsert by `PLAYER_ID`, keep latest bio.
2. **Tier 1 — season aggregates** (loop `season × season_type`, RS + Playoffs)
   - `LeagueDashTeamStats` × measure ∈ {Base, Advanced, Misc, Four Factors} → `team_season_stats`
   - `LeagueDashPlayerStats` × measure ∈ {Base, Advanced, Misc} → `player_season_stats`
   - `LeagueStandings` (RS only) → `team_standings`
3. **Tier 2 — clutch / tracking / playtype / on-off / passing** (loop `season × season_type`)
   - `LeagueDashTeamClutch`, `LeagueDashPlayerClutch`
   - `LeagueDashPtStats` × `pt_measure_type` × {Player, Team}
   - `SynergyPlayTypes` × play_type × {offensive, defensive} × {P, T}
   - `TeamPlayerOnOffDetails` per team_id
   - `PlayerDashPtPass` per player_id (drive off rostered players from `player_season_stats`)
4. **Tier 3 — schedule + game logs** (loop `season × season_type`)
   - `ScheduleLeagueV2` → `schedule` (parse `game_type` = GAME_ID[2])
   - `TeamGameLogs` → `team_game_logs`
   - `PlayerGameLogs` → `player_game_logs`
5. **Tier 3.5 — play-by-play** (run last; longest)
   - Enumerate `GAME_ID`s from `schedule` where game_type ∈ {2,4,6}.
   - `PlayByPlayV3` per game (V2 fallback) → `play_by_play`.
   - Log each game in `ingestion_log`; resume by skipping games already logged `status='ok'`.

## Operating discipline
- **Both season types** for every endpoint except standings.
- **Idempotent:** every write is an upsert on the table PK. Safe to re-run.
- **Resume, don't restart:** check `ingestion_log` before each unit of work; skip `ok`, retry `error`.
- **Rate-limit:** `time.sleep(0.5)`+ between calls, exponential backoff on failure. `timeout=90`.
- **Akamai 403 → curl_cffi:** patch `nba_api` to use a `curl_cffi` Chrome-impersonation session
  before assuming an endpoint is dead.
- **Historical gaps (measured 2005-06→2024-25 via `scripts/endpoint_cutoffs.py`):**
  - **Tracking** (`LeagueDashPtStats`, `PlayerDashPtPass`): data starts **2013-14**. 2012-13 and
    earlier return empty.
  - **Synergy** (`SynergyPlayTypes`): data starts **2012-13**. 2011-12 and earlier return empty.
  - **PlayByPlayV3:** available all the way back to **2005-06** — the old "pre-2016 needs V2"
    assumption did not hold in testing; V2 fallback is rarely/never needed in this range.
  - Everything else (team/player Base+Advanced+Misc+Four Factors, clutch, standings, on/off,
    schedule, team/player game logs) returns for **every** season back to 2005-06.
  Catch empty/errored frames, log `status='empty'`, continue — never assume a column exists.
- **Empty-body throttling:** heavy endpoints (esp. `PlayerGameLogs`, ~26k rows) intermittently
  return an empty body (`Expecting value: line 1 column 1`) when a session has run many sequential
  calls. It is NOT a data gap — a fresh session / longer backoff succeeds. On repeated empties for
  a season that neighbors succeed in, retry with a new session rather than logging `empty`.

## Suggested layout
```
historical-database/
├── schema.sql              # apply once to Supabase
├── ENDPOINTS_TO_SCRAPE.md  # endpoint reference
├── RUNBOOK.md              # this file
└── scripts/
    ├── ingest.py           # orchestrator (skeleton provided)
    ├── nba_session.py      # nba_api + curl_cffi session/headers + retry
    └── supabase_io.py      # upsert helpers + ingestion_log
```

## Run
```bash
# full backfill, all seasons, both season types
python scripts/ingest.py --start 2005-06 --end 2025-26

# a single tier or season while iterating
python scripts/ingest.py --start 2024-25 --end 2024-25 --tier 1
python scripts/ingest.py --start 2024-25 --end 2024-25 --tier pbp

# smoke-test / chunk the long per-entity + per-game passes
python scripts/ingest.py --start 2024-25 --end 2024-25 --tier 2 --max-entities 3   # 3 teams/players
python scripts/ingest.py --start 2024-25 --end 2024-25 --tier pbp --max-games 50    # first 50 games
```

## Write-layer notes (validated end-to-end on 2024-25, 2026-06-09)
- `rows_from_df`/`_clean` (supabase_io.py) sanitize the whole payload: NaN/Inf -> None, integral
  floats -> int (pandas widens INT cols to float when NaN present), "" -> NULL (PBP scores),
  Timestamps/dates -> ISO. Without these every write fails — they are not optional.
- **Per-team grain:** `SynergyPlayTypes` and `PlayerDashPtPass` return one row PER TEAM for traded
  players, so `synergy_playtypes` and `player_passing` PKs include `team_id`. `LeagueDashPlayerStats`
  / clutch / pt-tracking do NOT (one combined row, last team).
- **PBP key:** `actionNumber` is NOT unique within a game (linked events share it) — `play_by_play`
  is keyed on a per-game `event_idx`.
- Tier 1, Tier 2 (clutch/pt/synergy/on-off/passing), Tier 3, and PBP all check `ingestion_log`
  before each unit, so a crashed backfill resumes instead of re-fetching.

## Verification (do after each tier)
- Row counts per table by `season, season_type` look sane (no zero-row seasons unexpectedly).
- Every stats table joins cleanly on `TEAM_ID` / `PLAYER_ID` to the dimension tables.
- No PK duplicates (the upsert guarantees this — spot-check anyway).
- `play_by_play`: every `schedule` game with type ∈ {2,4,6} has events OR an `ingestion_log` row
  explaining why not.
