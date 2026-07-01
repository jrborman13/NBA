# scripts/

Backfill pipeline. See `../RUNBOOK.md` for the execution plan and `../ENDPOINTS_TO_SCRAPE.md`
for endpoint params.

| File | Role |
|---|---|
| `ingest.py` | Orchestrator. Runs tiers in order: dimensions → 1 → 2 → 3 → pbp. CLI: `--start`, `--end`, `--tier`. |
| `nba_session.py` | `patch_nba_session()` routes nba_api through a `curl_cffi` Chrome-impersonation session (beats Akamai). `safe_call()` wraps endpoints with retry + exponential backoff. |
| `supabase_io.py` | `upsert()` (idempotent, batched), `rows_from_df()` (identity cols + JSONB `stats`), `already_done()`/`log()` (resume via `ingestion_log`), `get_game_ids()`/`get_rostered_player_ids()`. |

## Setup
```bash
pip install -r ../requirements.txt        # or: pip install --break-system-packages -r ../requirements.txt
cp ../.env.example ../.env                 # fill SUPABASE_URL + SUPABASE_SERVICE_KEY
psql "$SUPABASE_DB_URL" -f ../schema.sql   # or run schema.sql via the Supabase SQL editor / MCP
```

## Run
```bash
python ingest.py --start 2005-06 --end 2025-26            # full backfill
python ingest.py --start 2024-25 --end 2024-25 --tier 1   # one tier / season while iterating
python ingest.py --start 2024-25 --end 2024-25 --tier pbp # play-by-play only
```

## Dry-run validation (run before any real backfill)
`dry_run_validate.py` calls every endpoint `ingest.py` uses for one season (no Supabase writes)
and asserts each mapped SOURCE column exists in the live frame. Use it to confirm a season is
runnable before committing to a full pull:
```bash
python dry_run_validate.py --season 2024-25            # RS + Playoffs (default)
python dry_run_validate.py --season 2018-19 --skip-pbp # spot-check an older season
```
Exit 0 = all maps valid. Last full run (2024-25, nba_api 1.11.4): **48 OK, 0 problems.**

## Notes / verify-before-trust
- Column-name maps in `ingest.py` were validated live against 2024-25 (RS + Playoffs). The JSONB
  `stats` payload preserves the raw row regardless, so a wrong typed-column map never loses data.
  Verified OK: `PlayerIndex` (PERSON_ID), `LeagueStandings` (TeamID), on/off frame order
  (idx 1=OFF, 2=ON; `VS_PLAYER_ID`), `PlayerDashPtPass` (frames = PassesMade/PassesReceived),
  `PlayByPlayV3` (camelCase).
- **Fixed during validation (were broken):**
  - `nba_session.patch_nba_session()` imported `NBAStatsHTTP`, which no longer exists in
    nba_api 1.11.x — it now injects curl_cffi via `NBAHTTP.set_session()`.
  - `ScheduleLeagueV2` columns are camelCase/nested (`gameDate`, `homeTeam_teamId`,
    `awayTeam_teamId`) — not `GAME_DATE`/`HOME_TEAM_ID`/`AWAY_TEAM_ID`.
  - `TeamGameLogs` / `PlayerGameLogs` now reject empty MeasureType and `'None'` OpponentTeamID
    (`{"MeasureType":["Invalid parameters"]}`); both calls pass `measure_type=...="Base"` and
    `opp_team_id_nullable=0`.
- **Known caveat (not a column-map bug):** `PlayerIndex(season=<past>)` returns a broken
  ~140-row subset (missing stars); only the *current* season returns the full ~570 roster. Seed
  the `players` dimension from `player_season_stats` PLAYER_IDs, not PlayerIndex alone.
- Pre-~2013 seasons lack tracking (`LeagueDashPtStats`, `PlayerDashPtPass`); pre-~2016 may lack
  PBP V3 (falls back to V2). These log `status='empty'` and continue.
- Passing + on/off + play-by-play are the long poles. Run them last; they resume per-entity/game
  from `ingestion_log`.
