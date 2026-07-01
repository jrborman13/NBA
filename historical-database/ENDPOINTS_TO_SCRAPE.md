# Historical Scrape Spec — nba_api Endpoints → Supabase

Source of truth for the endpoints this project ingests. Derived from the live calls in
`NBA/combined-app/` and `NBA/streamlit/`. Feed this file to Claude Code CLI as the scrape plan.

## Global rules
- **Season range:** backfill `2005-06` → `2025-26` (precedent: `combined-app/player_app/build_historical_stats.py`).
  Season string format `'YYYY-YY'`.
- **League:** `league_id='00'`. **Season types:** scrape **both** `'Regular Season'` AND `'Playoffs'` for every
  endpoint below (loop season × season_type). Exception: `LeagueStandings` is regular-season only.
  Store `SEASON_TYPE` on every row.
- **Akamai:** if a call 403s, route through `curl_cffi` Chrome impersonation. Always `timeout=90`.
- **Rate-limit:** `time.sleep(0.5)`+ between calls; retry/backoff on failure. Don't parallelize hard.
- **Storage:** normalized tables keyed by **canonical ID + SEASON**, columns in nba_api SCREAMING_SNAKE_CASE.
  Add `SEASON` (and `SEASON_TYPE`) as first-class columns on every row. Upsert on the keys below so re-runs are idempotent.

---

## Tier 1 — season aggregates (start here; cheapest, highest reuse)

| Endpoint | Key params | Grain → table | Upsert key |
|---|---|---|---|
| `LeagueDashTeamStats` | `measure_type_detailed_defense` ∈ {`Base`,`Advanced`,`Misc`,`Four Factors`}, `per_mode_detailed='PerGame'` | team-season → `team_season_stats` (one col-set per measure type, or one table per measure) | `SEASON, SEASON_TYPE, TEAM_ID, MEASURE_TYPE` |
| `LeagueDashPlayerStats` | `measure_type_detailed_defense` ∈ {`Base`,`Advanced`,`Misc`}, `per_mode_detailed='PerGame'`, `season_type_all_star='Regular Season'` | player-season → `player_season_stats` | `SEASON, SEASON_TYPE, PLAYER_ID, MEASURE_TYPE` |
| `LeagueStandings` | `league_id='00'`, `season_type='Regular Season'` | team-season → `team_standings` | `SEASON, TEAM_ID` |
| `PlayerIndex` | `season`, `league_id='00'` | player dimension (bio/headshot/position) → `players` | `PLAYER_ID` (track `SEASON` last-seen) |

`PlayerIndex` is the player dimension table; `teams` dimension can be built from `nba_api.stats.static.teams`.

## Tier 2 — clutch, tracking, playtype (per season)

| Endpoint | Key params | Grain → table | Upsert key |
|---|---|---|---|
| `LeagueDashTeamClutch` | advanced measure, clutch defaults | team-season → `team_season_clutch` | `SEASON, TEAM_ID` |
| `LeagueDashPlayerClutch` | `per_mode_detailed='PerGame'` | player-season → `player_season_clutch` | `SEASON, PLAYER_ID` |
| `LeagueDashPtStats` | `pt_measure_type='Drives'`, `player_or_team` ∈ {`Player`,`Team`}, `per_mode_simple='PerGame'` | season → `pt_drives_player` / `pt_drives_team` (other `pt_measure_type` values: Passing, Rebounding, CatchShoot, PullUpShot — add as needed) | `SEASON, {PLAYER_ID|TEAM_ID}, PT_MEASURE_TYPE` |
| `SynergyPlayTypes` | `per_mode_simple='Totals'`, `player_or_team_abbreviation` ∈ {`P`,`T`}, `type_grouping_nullable` ∈ {`offensive`,`defensive`}, `play_type_nullable=<playtype>` | season-playtype → `synergy_playtypes` (loop all play types: Isolation, Transition, PRBallHandler, PRRollman, Postup, Spotup, Handoff, Cut, OffScreen, OffRebound, Misc) | `SEASON, {PLAYER_ID|TEAM_ID}, PLAY_TYPE, TYPE_GROUPING` |
| `TeamPlayerOnOffDetails` | `per_mode_detailed='Totals'`, `measure_type_detailed_defense='Advanced'`, per `team_id` | player-on/off per team-season → `team_player_onoff` (df index 1 = OFF court, index 2 = ON court) | `SEASON, TEAM_ID, PLAYER_ID, ON_OFF` |
| `PlayerDashPtPass` | per `player_id` + `team_id`, per season | passing → `player_passing` | `SEASON, PLAYER_ID, PASS_TEAMMATE_ID` |

## Tier 3 — game-level logs (large; backfill after Tier 1/2)

| Endpoint | Key params | Grain → table | Upsert key |
|---|---|---|---|
| `PlayerGameLogs` | `season_nullable`, optional `team_id_nullable` | player-game → `player_game_logs` | `SEASON, PLAYER_ID, GAME_ID` |
| `TeamGameLogs` | `season_nullable` | team-game → `team_game_logs` | `SEASON, TEAM_ID, GAME_ID` |
| `ScheduleLeagueV2` | `season`, `league_id='00'` | game schedule → `schedule` | `SEASON, GAME_ID` |

`GAME_ID[2]` encodes game type: `1`=preseason, `2`=regular, `3`=all-star, `4`=playoffs, `6`=play-in.
Filter to `['2','4','6']` unless intentionally storing preseason.

## Tier 3.5 — play-by-play (every regular-season & playoff game)

| Endpoint | Key params | Grain → table | Upsert key |
|---|---|---|---|
| `PlayByPlayV3` | per `game_id` (V2 fallback if V3 missing for old seasons) | event → `play_by_play` | `GAME_ID, ACTION_NUMBER` |

Enumerate `GAME_ID`s from the `schedule` table (game_type ∈ {`2`,`4`,`6`}) so coverage is every available
game. Stamp `SEASON`/`SEASON_TYPE` onto each event from the schedule row. This is the highest-volume pull
(~1,200 games/season × ~500 events) — run it last, log progress in `ingestion_log`, and resume on `game_id`.
Pre-2016 seasons may need `PlayByPlayV2` (V3 coverage is thinner); catch and fall back.

## Tier 4 — optional / shot-level (only if a downstream app needs it)
- `ShotChartDetail` (per player/season — high volume) → `shot_chart_detail`, key `SEASON, PLAYER_ID, GAME_ID, GAME_EVENT_ID`
- pbpstats.com zone shooting (NOT nba_api): `https://api.pbpstats.com/get-totals/nba?Season=<s>&SeasonType=Regular+Season&Type=Team|Opponent` → `pbp_zone_shooting`
- Live/box-score endpoints (`ScoreboardV2`, `BoxScoreTraditionalV3`, `BoxScorePlayerTrackV3`, `nba_api.live`) are for in-game use — skip for the historical backfill.

---

## Suggested build order for Claude Code
1. Build `teams` (static) + `players` (`PlayerIndex` looped over seasons) dimensions first — these hold the join keys.
2. Tier 1 season aggregates for all seasons (loop season × measure_type).
3. Tier 2 clutch/tracking/playtype.
4. Tier 3 game logs + schedule.
5. Validate: every stats table has `SEASON`, joins cleanly on `TEAM_ID`/`PLAYER_ID`, no dup (key) rows.

Historical caveat: pre-2013-ish seasons lack tracking endpoints (`LeagueDashPtStats`, `PlayerDashPtPass`) and some
advanced columns. Catch the empty/errored frames and skip — don't assume a column exists.
