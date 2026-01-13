-- Sportradar Data Tables Schema
-- Stores Sportradar API data for comparison with NBA API
-- Uses JSONB for flexible data storage
-- Tables prefixed with sr_ to avoid conflicts with existing nba_* tables

-- Table 1: sr_team_stats
-- Stores team stats from Sportradar NBA API
CREATE TABLE IF NOT EXISTS sr_team_stats (
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_sr_team_stats_unique 
ON sr_team_stats(season, measure_type, COALESCE(last_n_games, -1), COALESCE(group_quantity, ''));

-- Indexes for sr_team_stats
CREATE INDEX IF NOT EXISTS idx_sr_team_stats_season ON sr_team_stats(season);
CREATE INDEX IF NOT EXISTS idx_sr_team_stats_measure ON sr_team_stats(measure_type);
CREATE INDEX IF NOT EXISTS idx_sr_team_stats_updated ON sr_team_stats(updated_at DESC);

-- Table 2: sr_player_stats
-- Stores player advanced stats from Sportradar NBA API
CREATE TABLE IF NOT EXISTS sr_player_stats (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    measure_type VARCHAR(50) NOT NULL DEFAULT 'Advanced',
    data JSONB NOT NULL, -- Array of player stat objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season, measure_type)
);

-- Indexes for sr_player_stats
CREATE INDEX IF NOT EXISTS idx_sr_player_stats_season ON sr_player_stats(season);
CREATE INDEX IF NOT EXISTS idx_sr_player_stats_updated ON sr_player_stats(updated_at DESC);

-- Table 3: sr_game_logs
-- Stores player and team game logs from Sportradar NBA API
CREATE TABLE IF NOT EXISTS sr_game_logs (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    log_type VARCHAR(20) NOT NULL, -- 'player' or 'team'
    data JSONB NOT NULL, -- Array of game log objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season, log_type)
);

-- Indexes for sr_game_logs
CREATE INDEX IF NOT EXISTS idx_sr_game_logs_season ON sr_game_logs(season);
CREATE INDEX IF NOT EXISTS idx_sr_game_logs_type ON sr_game_logs(log_type);
CREATE INDEX IF NOT EXISTS idx_sr_game_logs_updated ON sr_game_logs(updated_at DESC);

-- Table 4: sr_synergy_data
-- Stores team and player synergy data from Sportradar Synergy Basketball API
CREATE TABLE IF NOT EXISTS sr_synergy_data (
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

-- Indexes for sr_synergy_data
CREATE INDEX IF NOT EXISTS idx_sr_synergy_season ON sr_synergy_data(season);
CREATE INDEX IF NOT EXISTS idx_sr_synergy_entity ON sr_synergy_data(entity_type);
CREATE INDEX IF NOT EXISTS idx_sr_synergy_playtype ON sr_synergy_data(playtype);
CREATE INDEX IF NOT EXISTS idx_sr_synergy_updated ON sr_synergy_data(updated_at DESC);

-- Table 5: sr_schedule
-- Stores league schedule from Sportradar NBA API
CREATE TABLE IF NOT EXISTS sr_schedule (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    data JSONB NOT NULL, -- Array of game objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season)
);

-- Indexes for sr_schedule
CREATE INDEX IF NOT EXISTS idx_sr_schedule_season ON sr_schedule(season);
CREATE INDEX IF NOT EXISTS idx_sr_schedule_updated ON sr_schedule(updated_at DESC);

-- Table 6: sr_standings
-- Stores standings from Sportradar NBA API
CREATE TABLE IF NOT EXISTS sr_standings (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    data JSONB NOT NULL, -- Array of team standing objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season)
);

-- Indexes for sr_standings
CREATE INDEX IF NOT EXISTS idx_sr_standings_season ON sr_standings(season);
CREATE INDEX IF NOT EXISTS idx_sr_standings_updated ON sr_standings(updated_at DESC);

-- Table 7: sr_player_index
-- Stores player index/roster data from Sportradar NBA API
CREATE TABLE IF NOT EXISTS sr_player_index (
    id BIGSERIAL PRIMARY KEY,
    season VARCHAR(10) NOT NULL,
    data JSONB NOT NULL, -- Array of player objects
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(season)
);

-- Indexes for sr_player_index
CREATE INDEX IF NOT EXISTS idx_sr_player_index_season ON sr_player_index(season);
CREATE INDEX IF NOT EXISTS idx_sr_player_index_updated ON sr_player_index(updated_at DESC);

-- Triggers to automatically update updated_at
-- Note: Assumes update_updated_at_column() function exists (from previous migrations)
CREATE TRIGGER update_sr_team_stats_updated_at BEFORE UPDATE ON sr_team_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sr_player_stats_updated_at BEFORE UPDATE ON sr_player_stats
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sr_game_logs_updated_at BEFORE UPDATE ON sr_game_logs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sr_synergy_data_updated_at BEFORE UPDATE ON sr_synergy_data
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sr_schedule_updated_at BEFORE UPDATE ON sr_schedule
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sr_standings_updated_at BEFORE UPDATE ON sr_standings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sr_player_index_updated_at BEFORE UPDATE ON sr_player_index
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

