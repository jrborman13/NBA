-- ============================================================================
-- NBA Historical Database — Supabase (Postgres) schema
-- Target: season-by-season stats (Regular Season + Playoffs) + full play-by-play.
-- Design: typed identity/key columns + JSONB `stats` payload for the metric long tail
--         (survives measure-type differences and missing columns in older seasons).
-- Columns mirror nba_api SCREAMING_SNAKE_CASE; SEASON + SEASON_TYPE are first-class.
-- All tables upsert on their PRIMARY KEY so re-runs are idempotent.
-- ============================================================================

-- Convention: SEASON text 'YYYY-YY'. SEASON_TYPE in ('Regular Season','Playoffs').
-- Scrape every endpoint twice: once per season_type. PBP covers game types 2/4/6.

-- ---------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
    team_id        BIGINT PRIMARY KEY,
    abbreviation   TEXT,
    nickname       TEXT,
    city           TEXT,
    full_name      TEXT,
    state          TEXT,
    year_founded   INT
);

-- Built from PlayerIndex looped over seasons; keep the latest bio, track last season seen.
CREATE TABLE IF NOT EXISTS players (
    player_id          BIGINT PRIMARY KEY,
    first_name         TEXT,
    last_name          TEXT,
    player_slug        TEXT,
    position           TEXT,
    height             TEXT,
    weight             TEXT,
    college            TEXT,
    country            TEXT,
    draft_year         INT,
    draft_round        INT,
    draft_number       INT,
    from_year          INT,
    to_year            INT,
    last_season_seen   TEXT,
    stats              JSONB
);

-- Completes `players` from player_season_stats (PlayerIndex is thin for past seasons).
-- Insert-only (ON CONFLICT DO NOTHING) so PlayerIndex bio is preserved. Called by the `seed`
-- tier in ingest.py after Tier 1. Returns the number of newly inserted players.
CREATE OR REPLACE FUNCTION seed_players_from_stats()
RETURNS integer
LANGUAGE sql
AS $$
  WITH ins AS (
    INSERT INTO players (player_id, first_name, last_name, last_season_seen, stats)
    SELECT DISTINCT ON (player_id)
           player_id,
           split_part(player_name, ' ', 1),
           nullif(trim(substr(player_name, length(split_part(player_name, ' ', 1)) + 1)), ''),
           season,
           jsonb_build_object('PLAYER_NAME', player_name, 'source', 'player_season_stats')
    FROM player_season_stats
    WHERE player_name IS NOT NULL
    ORDER BY player_id, season DESC
    ON CONFLICT (player_id) DO NOTHING
    RETURNING 1
  )
  SELECT count(*)::int FROM ins;
$$;

-- ---------------------------------------------------------------------------
-- Tier 1 — season aggregates
-- ---------------------------------------------------------------------------
-- LeagueDashTeamStats — one row per team / season / season_type / measure_type.
CREATE TABLE IF NOT EXISTS team_season_stats (
    season         TEXT   NOT NULL,
    season_type    TEXT   NOT NULL,
    team_id        BIGINT NOT NULL REFERENCES teams(team_id),
    measure_type   TEXT   NOT NULL,         -- Base | Advanced | Misc | Four Factors
    per_mode       TEXT   NOT NULL DEFAULT 'PerGame',
    team_name      TEXT,
    gp             INT,
    min            NUMERIC,
    stats          JSONB  NOT NULL,         -- full nba_api row
    PRIMARY KEY (season, season_type, team_id, measure_type, per_mode)
);
CREATE INDEX IF NOT EXISTS ix_team_season_stats_season ON team_season_stats (season, season_type);
CREATE INDEX IF NOT EXISTS ix_team_season_stats_team   ON team_season_stats (team_id);

-- LeagueDashPlayerStats — one row per player / season / season_type / measure_type.
CREATE TABLE IF NOT EXISTS player_season_stats (
    season         TEXT   NOT NULL,
    season_type    TEXT   NOT NULL,
    player_id      BIGINT NOT NULL,
    measure_type   TEXT   NOT NULL,         -- Base | Advanced | Misc
    per_mode       TEXT   NOT NULL DEFAULT 'PerGame',
    team_id        BIGINT,
    player_name    TEXT,
    gp             INT,
    min            NUMERIC,
    stats          JSONB  NOT NULL,
    PRIMARY KEY (season, season_type, player_id, measure_type, per_mode)
);
CREATE INDEX IF NOT EXISTS ix_player_season_stats_season ON player_season_stats (season, season_type);
CREATE INDEX IF NOT EXISTS ix_player_season_stats_player ON player_season_stats (player_id);
CREATE INDEX IF NOT EXISTS ix_player_season_stats_team   ON player_season_stats (team_id);

-- LeagueStandings (regular season). Playoffs has no standings; load season_type='Regular Season' only.
CREATE TABLE IF NOT EXISTS team_standings (
    season         TEXT   NOT NULL,
    team_id        BIGINT NOT NULL REFERENCES teams(team_id),
    conference     TEXT,
    division       TEXT,
    wins           INT,
    losses         INT,
    win_pct        NUMERIC,
    playoff_rank   INT,
    stats          JSONB,
    PRIMARY KEY (season, team_id)
);

-- ---------------------------------------------------------------------------
-- Tier 2 — clutch, tracking, playtype, on/off, passing
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS team_season_clutch (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    team_id BIGINT NOT NULL REFERENCES teams(team_id),
    per_mode TEXT NOT NULL DEFAULT 'PerGame',
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, team_id, per_mode)
);

CREATE TABLE IF NOT EXISTS player_season_clutch (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    player_id BIGINT NOT NULL, team_id BIGINT,
    per_mode TEXT NOT NULL DEFAULT 'PerGame',
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, player_id, per_mode)
);

-- LeagueDashPtStats — player_or_team controls grain; loop pt_measure_type (Drives, Passing, etc.).
CREATE TABLE IF NOT EXISTS pt_tracking_player (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    player_id BIGINT NOT NULL, team_id BIGINT,
    pt_measure_type TEXT NOT NULL, per_mode TEXT NOT NULL DEFAULT 'PerGame',
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, player_id, pt_measure_type, per_mode)
);

CREATE TABLE IF NOT EXISTS pt_tracking_team (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    team_id BIGINT NOT NULL REFERENCES teams(team_id),
    pt_measure_type TEXT NOT NULL, per_mode TEXT NOT NULL DEFAULT 'PerGame',
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, team_id, pt_measure_type, per_mode)
);

-- SynergyPlayTypes — entity = 'P' or 'T'; loop play_type and type_grouping (offensive/defensive).
-- NOTE: returns one row per player PER TEAM — traded players appear once per team, so team_id
-- is part of the PK (==entity_id for team rows). This also preserves per-team play-type splits.
CREATE TABLE IF NOT EXISTS synergy_playtypes (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,              -- 'P' player | 'T' team
    entity_id BIGINT NOT NULL,              -- player_id or team_id
    team_id BIGINT NOT NULL,                -- player's team (==entity_id for team rows)
    play_type TEXT NOT NULL,
    type_grouping TEXT NOT NULL,            -- offensive | defensive
    per_mode TEXT NOT NULL DEFAULT 'Totals',
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, entity_type, entity_id, team_id, play_type, type_grouping)
);

-- TeamPlayerOnOffDetails — on/off splits per team. on_off in ('ON','OFF').
CREATE TABLE IF NOT EXISTS team_player_onoff (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    team_id BIGINT NOT NULL REFERENCES teams(team_id),
    player_id BIGINT NOT NULL,
    on_off TEXT NOT NULL,
    measure_type TEXT NOT NULL DEFAULT 'Advanced',
    per_mode TEXT NOT NULL DEFAULT 'Totals',
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, team_id, player_id, on_off)
);

-- PlayerDashPtPass — passer→teammate passing rows. Returns rows PER TEAM (traded players),
-- so team_id is in the PK (==entity team for that stint).
CREATE TABLE IF NOT EXISTS player_passing (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    player_id BIGINT NOT NULL,
    team_id BIGINT NOT NULL,
    pass_teammate_player_id BIGINT NOT NULL,
    pass_direction TEXT NOT NULL,           -- 'made' | 'received'
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, player_id, team_id, pass_teammate_player_id, pass_direction)
);

-- ---------------------------------------------------------------------------
-- Tier 3 — schedule + game logs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schedule (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    game_id TEXT NOT NULL,
    game_date DATE,
    home_team_id BIGINT, away_team_id BIGINT,
    game_type CHAR(1),                      -- GAME_ID[2]: 2 reg / 4 playoff / 6 play-in
    stats JSONB,
    PRIMARY KEY (game_id)
);
CREATE INDEX IF NOT EXISTS ix_schedule_season ON schedule (season, season_type);

CREATE TABLE IF NOT EXISTS team_game_logs (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    team_id BIGINT NOT NULL REFERENCES teams(team_id),
    game_id TEXT NOT NULL,
    game_date DATE, matchup TEXT, wl CHAR(1), min NUMERIC,
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, team_id, game_id)
);
CREATE INDEX IF NOT EXISTS ix_team_game_logs_game ON team_game_logs (game_id);

CREATE TABLE IF NOT EXISTS player_game_logs (
    season TEXT NOT NULL, season_type TEXT NOT NULL,
    player_id BIGINT NOT NULL, team_id BIGINT,
    game_id TEXT NOT NULL,
    game_date DATE, matchup TEXT, wl CHAR(1), min NUMERIC,
    stats JSONB NOT NULL,
    PRIMARY KEY (season, season_type, player_id, game_id)
);
CREATE INDEX IF NOT EXISTS ix_player_game_logs_game   ON player_game_logs (game_id);
CREATE INDEX IF NOT EXISTS ix_player_game_logs_player ON player_game_logs (player_id);

-- ---------------------------------------------------------------------------
-- Play-by-play — one row per event, every regular-season & playoff game.
-- Source: PlayByPlayV3 (stats.nba.com) keyed by GAME_ID. Enumerate GAME_IDs from
-- `schedule` (game_type in 2,4,6) so coverage is "every available game".
-- ---------------------------------------------------------------------------
-- NOTE: PlayByPlayV3 actionNumber is NOT unique within a game (linked events — e.g. a
-- turnover and the steal — share it). Key on a per-game chronological event_idx instead;
-- action_number is kept as an informational column.
-- SLIM: no JSONB `stats` here — the per-event payload is ~700 bytes/row and at full coverage
-- (~13.5M events) it blew past the project's disk quota. Typed columns capture everything
-- useful, including shot-chart fields. ~10x smaller (full PBP ~1-2GB vs ~11GB).
CREATE TABLE IF NOT EXISTS play_by_play (
    game_id        TEXT   NOT NULL,
    event_idx      INT    NOT NULL,         -- per-game chronological row position (stable key)
    action_number  INT,                     -- actionNumber / EVENTNUM (NOT unique in V3)
    season         TEXT,
    season_type    TEXT,
    period         INT,
    clock          TEXT,
    team_id        BIGINT,
    team_tricode   TEXT,
    person_id      BIGINT,                  -- acting player, if any
    player_name    TEXT,
    action_type    TEXT,
    sub_type       TEXT,
    description    TEXT,
    score_home     INT,
    score_away     INT,
    shot_result    TEXT,                    -- 'Made' | 'Missed' (shots only)
    shot_distance  INT,
    shot_value     INT,                     -- 2 | 3
    loc_x          INT,                     -- xLegacy (shot chart coords)
    loc_y          INT,                     -- yLegacy
    assist_person_id BIGINT,                -- assister, parsed from description (see resolve_assists.sql)
    PRIMARY KEY (game_id, event_idx)
);

-- GameRotation: each player's on-court stints per game (in/out elapsed times, tenths of a sec).
-- Reconstructs on-court lineups; populated by the `rotation` tier in ingest.py.
CREATE TABLE IF NOT EXISTS game_rotation (
    game_id        TEXT   NOT NULL,
    season         TEXT,
    season_type    TEXT,
    team_id        BIGINT NOT NULL,
    person_id      BIGINT NOT NULL,
    in_time_real   NUMERIC NOT NULL,        -- elapsed game time entered (tenths of sec)
    out_time_real  NUMERIC,                 -- elapsed game time exited
    player_first   TEXT,
    player_last    TEXT,
    player_pts     INT,
    pt_diff        INT,
    usg_pct        NUMERIC,
    PRIMARY KEY (game_id, person_id, in_time_real)
);
CREATE INDEX IF NOT EXISTS ix_game_rotation_game   ON game_rotation (game_id);
CREATE INDEX IF NOT EXISTS ix_game_rotation_person ON game_rotation (person_id);

-- On-court stints reconstructed from play_by_play (substitutions + inferred period starters),
-- the replacement for the Akamai-blocked GameRotation scrape. Built by scripts/build_pbp_lineups.py.
-- Lineup at any moment = stints whose [in_elapsed_sec, out_elapsed_sec) contains the event's
-- game-elapsed seconds. Per-game consistency is logged to ingestion_log (endpoint='PBPLineup').
CREATE TABLE IF NOT EXISTS pbp_lineup_stint (
    game_id         TEXT    NOT NULL,
    season          TEXT,
    season_type     TEXT,
    team_id         BIGINT  NOT NULL,
    person_id       BIGINT  NOT NULL,
    period          INT     NOT NULL,
    in_elapsed_sec  NUMERIC NOT NULL,   -- game-elapsed seconds entered (period start for starters)
    out_elapsed_sec NUMERIC,            -- game-elapsed seconds left (period end if played to end)
    in_clock        TEXT,
    out_clock       TEXT,
    PRIMARY KEY (game_id, person_id, period, in_elapsed_sec)
);
CREATE INDEX IF NOT EXISTS idx_pbp_lineup_stint_game ON pbp_lineup_stint (game_id);
CREATE INDEX IF NOT EXISTS idx_pbp_lineup_stint_lookup
    ON pbp_lineup_stint (game_id, in_elapsed_sec, out_elapsed_sec);

CREATE INDEX IF NOT EXISTS ix_pbp_season ON play_by_play (season, season_type);
CREATE INDEX IF NOT EXISTS ix_pbp_person ON play_by_play (person_id);
CREATE INDEX IF NOT EXISTS ix_pbp_team   ON play_by_play (team_id);

-- ---------------------------------------------------------------------------
-- Ingestion log — track what's been scraped so re-runs can resume/skip.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ingestion_log (
    endpoint      TEXT NOT NULL,
    season        TEXT,
    season_type   TEXT,
    scope         TEXT,                     -- e.g. game_id, measure_type, play_type
    row_count     INT,
    status        TEXT,                     -- ok | empty | error
    error_msg     TEXT,
    scraped_at    TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (endpoint, season, season_type, scope)
);

-- ============================================================================
-- ALTERNATIVE (not used here): fully-typed columns per table.
-- Pros: native SQL on every metric, smaller rows. Cons: 100s of columns, brittle
-- across measure types and pre-2013 seasons missing tracking/advanced fields.
-- If a metric is queried constantly, promote it: add a typed column and backfill
-- from stats->>'COLUMN'. The JSONB payload keeps everything else addressable.
-- ============================================================================
