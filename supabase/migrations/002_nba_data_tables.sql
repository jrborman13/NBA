-- NBA Data Tables Schema
-- Stores NBA API data fetched by scheduled Edge Functions
-- Uses JSONB for flexible data storage

-- Table 1: nba_team_stats
-- Stores team stats (advanced, misc, traditional, four factors)
CREATE TABLE IF NOT EXISTS nba_team_stats (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    measure_type VARCHAR(50) NOT NULL, -- 'Advanced', 'Misc', 'Traditional', 'Four Factors'
    last_n_games INTEGER, -- NULL for season totals, or number like 5, 10, etc.
    group_quantity VARCHAR(50), -- NULL, 'Starters', 'Bench', etc.
    data JSONB NOT NULL, -- Array of team stat objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Unique index with expressions to handle NULL values
CREATE UNIQUE INDEX IF NOT EXISTS idx_nba_team_stats_unique 
ON nba_team_stats(season, measure_type, COALESCE(last_n_games, -1), COALESCE(group_quantity, ''));

-- Indexes for nba_team_stats
CREATE INDEX IF NOT EXISTS idx_nba_team_stats_season ON nba_team_stats(season);
CREATE INDEX IF NOT EXISTS idx_nba_team_stats_measure ON nba_team_stats(measure_type);
CREATE INDEX IF NOT EXISTS idx_nba_team_stats_updated ON nba_team_stats(updated_at DESC);

-- Table 2: nba_player_stats
-- Stores player advanced stats
CREATE TABLE IF NOT EXISTS nba_player_stats (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    measure_type VARCHAR(50) NOT NULL DEFAULT 'Advanced',
    data JSONB NOT NULL, -- Array of player stat objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season, measure_type)
);

-- Indexes for nba_player_stats
CREATE INDEX IF NOT EXISTS idx_nba_player_stats_season ON nba_player_stats(season);
CREATE INDEX IF NOT EXISTS idx_nba_player_stats_updated ON nba_player_stats(updated_at DESC);

-- Table 3: nba_game_logs
-- Stores player and team game logs
CREATE TABLE IF NOT EXISTS nba_game_logs (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    log_type VARCHAR(20) NOT NULL, -- 'player' or 'team'
    data JSONB NOT NULL, -- Array of game log objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season, log_type)
);

-- Indexes for nba_game_logs
CREATE INDEX IF NOT EXISTS idx_nba_game_logs_season ON nba_game_logs(season);
CREATE INDEX IF NOT EXISTS idx_nba_game_logs_type ON nba_game_logs(log_type);
CREATE INDEX IF NOT EXISTS idx_nba_game_logs_updated ON nba_game_logs(updated_at DESC);

-- Table 4: nba_synergy_data
-- Stores team and player synergy data
CREATE TABLE IF NOT EXISTS nba_synergy_data (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    entity_type VARCHAR(20) NOT NULL, -- 'team' or 'player'
    playtype VARCHAR(50) NOT NULL, -- 'Cut', 'Handoff', 'Isolation', etc.
    type_grouping VARCHAR(20) NOT NULL, -- 'offensive' or 'defensive'
    data JSONB NOT NULL, -- Array of synergy stat objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season, entity_type, playtype, type_grouping)
);

-- Indexes for nba_synergy_data
CREATE INDEX IF NOT EXISTS idx_nba_synergy_season ON nba_synergy_data(season);
CREATE INDEX IF NOT EXISTS idx_nba_synergy_entity ON nba_synergy_data(entity_type);
CREATE INDEX IF NOT EXISTS idx_nba_synergy_playtype ON nba_synergy_data(playtype);
CREATE INDEX IF NOT EXISTS idx_nba_synergy_updated ON nba_synergy_data(updated_at DESC);

-- Table 5: nba_schedule
-- Stores league schedule
CREATE TABLE IF NOT EXISTS nba_schedule (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    data JSONB NOT NULL, -- Array of game objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season)
);

-- Indexes for nba_schedule
CREATE INDEX IF NOT EXISTS idx_nba_schedule_season ON nba_schedule(season);
CREATE INDEX IF NOT EXISTS idx_nba_schedule_updated ON nba_schedule(updated_at DESC);

-- Table 6: nba_standings
-- Stores standings with clutch records
CREATE TABLE IF NOT EXISTS nba_standings (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    data JSONB NOT NULL, -- Array of team standing objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season)
);

-- Indexes for nba_standings
CREATE INDEX IF NOT EXISTS idx_nba_standings_season ON nba_standings(season);
CREATE INDEX IF NOT EXISTS idx_nba_standings_updated ON nba_standings(updated_at DESC);

-- Table 7: nba_player_index
-- Stores player index/roster data
CREATE TABLE IF NOT EXISTS nba_player_index (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    data JSONB NOT NULL, -- Array of player objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season)
);

-- Indexes for nba_player_index
CREATE INDEX IF NOT EXISTS idx_nba_player_index_season ON nba_player_index(season);
CREATE INDEX IF NOT EXISTS idx_nba_player_index_updated ON nba_player_index(updated_at DESC);

-- Table 8: nba_team_onoff
-- Stores team on/off court data
CREATE TABLE IF NOT EXISTS nba_team_onoff (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    team_id INTEGER NOT NULL,
    data JSONB NOT NULL, -- Array of player on/off objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season, team_id)
);

-- Indexes for nba_team_onoff
CREATE INDEX IF NOT EXISTS idx_nba_team_onoff_season ON nba_team_onoff(season);
CREATE INDEX IF NOT EXISTS idx_nba_team_onoff_team ON nba_team_onoff(team_id);
CREATE INDEX IF NOT EXISTS idx_nba_team_onoff_updated ON nba_team_onoff(updated_at DESC);

-- Table 9: nba_drives_stats
-- Stores drives statistics
CREATE TABLE IF NOT EXISTS nba_drives_stats (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    entity_type VARCHAR(20) NOT NULL, -- 'player' or 'team'
    data JSONB NOT NULL, -- Array of drives stat objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season, entity_type)
);

-- Indexes for nba_drives_stats
CREATE INDEX IF NOT EXISTS idx_nba_drives_season ON nba_drives_stats(season);
CREATE INDEX IF NOT EXISTS idx_nba_drives_entity ON nba_drives_stats(entity_type);
CREATE INDEX IF NOT EXISTS idx_nba_drives_updated ON nba_drives_stats(updated_at DESC);

-- Table 10: nba_pbpstats
-- Stores pbpstats.com data (team and opponent stats)
CREATE TABLE IF NOT EXISTS nba_pbpstats (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    stat_type VARCHAR(20) NOT NULL, -- 'team' or 'opponent'
    data JSONB NOT NULL, -- Array of pbpstats objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season, stat_type)
);

-- Indexes for nba_pbpstats
CREATE INDEX IF NOT EXISTS idx_nba_pbpstats_season ON nba_pbpstats(season);
CREATE INDEX IF NOT EXISTS idx_nba_pbpstats_type ON nba_pbpstats(stat_type);
CREATE INDEX IF NOT EXISTS idx_nba_pbpstats_updated ON nba_pbpstats(updated_at DESC);

-- Triggers to automatically update updated_at
CREATE TRIGGER update_nba_team_stats_updated_at BEFORE UPDATE ON nba_team_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_player_stats_updated_at BEFORE UPDATE ON nba_player_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_game_logs_updated_at BEFORE UPDATE ON nba_game_logs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_synergy_data_updated_at BEFORE UPDATE ON nba_synergy_data
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_schedule_updated_at BEFORE UPDATE ON nba_schedule
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_standings_updated_at BEFORE UPDATE ON nba_standings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_player_index_updated_at BEFORE UPDATE ON nba_player_index
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_team_onoff_updated_at BEFORE UPDATE ON nba_team_onoff
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_drives_stats_updated_at BEFORE UPDATE ON nba_drives_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_nba_pbpstats_updated_at BEFORE UPDATE ON nba_pbpstats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

