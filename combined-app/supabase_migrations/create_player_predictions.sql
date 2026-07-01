-- Run in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- Stores normalized per-player stat predictions for each game date.
-- Used as a cross-page cache: Predictions page and DraftKings Optimizer both
-- read from / write to this table to avoid re-running the expensive model.

CREATE TABLE IF NOT EXISTS player_predictions (
    game_date      DATE        NOT NULL,
    player_id      TEXT        NOT NULL,
    player_name    TEXT        NOT NULL,
    team           TEXT        NOT NULL,
    opponent       TEXT        NOT NULL,
    game           TEXT        NOT NULL,   -- e.g. "BOS @ LAL"
    is_home        BOOLEAN,
    proj_min       NUMERIC(5,1),
    pts            NUMERIC(6,2),
    reb            NUMERIC(6,2),
    ast            NUMERIC(6,2),
    stl            NUMERIC(6,2),
    blk            NUMERIC(6,2),
    tov            NUMERIC(6,2),
    fg3m           NUMERIC(6,2),
    ftm            NUMERIC(6,2),
    pra            NUMERIC(6,2),
    ra             NUMERIC(6,2),
    fpts           NUMERIC(8,2),
    fpts_ceiling   NUMERIC(8,2),
    fpts_floor     NUMERIC(8,2),
    fpts_median    NUMERIC(8,2),
    fpts_stddev    NUMERIC(8,2),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_date, player_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS player_predictions_game_date_idx ON player_predictions (game_date);
CREATE INDEX IF NOT EXISTS player_predictions_team_idx      ON player_predictions (game_date, team);
