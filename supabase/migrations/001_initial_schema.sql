-- Initial Schema for NBA Predictions App
-- Creates tables for predictions, vegas lines, cached API data, and accuracy metrics

-- Table 1: predictions
-- Replaces predictions_log.csv
CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    player_id VARCHAR(20) NOT NULL,
    player_name VARCHAR(100) NOT NULL,
    opponent_abbr VARCHAR(10) NOT NULL,
    game_date DATE NOT NULL,
    stat VARCHAR(10) NOT NULL,
    prediction DECIMAL(10, 2) NOT NULL,
    vegas_line DECIMAL(10, 2),
    actual DECIMAL(10, 2),
    is_home BOOLEAN NOT NULL,
    days_rest INTEGER NOT NULL,
    confidence VARCHAR(20) NOT NULL,
    -- Features
    season_avg DECIMAL(10, 2) NOT NULL,
    l5_avg DECIMAL(10, 2) NOT NULL,
    l10_avg DECIMAL(10, 2) NOT NULL,
    vs_opponent_avg DECIMAL(10, 2),
    opp_def_rating DECIMAL(10, 2) NOT NULL,
    opp_pace DECIMAL(10, 2) NOT NULL,
    usage_rate DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for predictions table
CREATE INDEX IF NOT EXISTS idx_predictions_player_date ON predictions(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_predictions_stat ON predictions(stat);
CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions(timestamp DESC);

-- Table 2: vegas_lines
-- Replaces player_lines.json
CREATE TABLE IF NOT EXISTS vegas_lines (
    id BIGSERIAL PRIMARY KEY,
    player_id VARCHAR(20) NOT NULL,
    game_date DATE NOT NULL,
    stat VARCHAR(10) NOT NULL,
    line DECIMAL(10, 2) NOT NULL,
    over_odds INTEGER NOT NULL DEFAULT -110,
    under_odds INTEGER NOT NULL DEFAULT -110,
    source VARCHAR(50) NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(player_id, game_date, stat)
);

-- Indexes for vegas_lines table
CREATE INDEX IF NOT EXISTS idx_vegas_lines_player_date ON vegas_lines(player_id, game_date);

-- Table 3: cached_api_data
-- Stores bulk API responses for caching
CREATE TABLE IF NOT EXISTS cached_api_data (
    id BIGSERIAL PRIMARY KEY,
    cache_key VARCHAR(255) NOT NULL UNIQUE,
    data_type VARCHAR(50) NOT NULL, -- 'synergy', 'game_logs', 'advanced_stats', 'drives_stats'
    season VARCHAR(10) NOT NULL,
    data JSONB NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for cached_api_data table
CREATE INDEX IF NOT EXISTS idx_cached_api_data_key ON cached_api_data(cache_key);
CREATE INDEX IF NOT EXISTS idx_cached_api_data_type_season ON cached_api_data(data_type, season);
CREATE INDEX IF NOT EXISTS idx_cached_api_data_expires ON cached_api_data(expires_at);

-- Table 4: accuracy_metrics (Optional)
-- Store pre-calculated accuracy metrics
CREATE TABLE IF NOT EXISTS accuracy_metrics (
    id BIGSERIAL PRIMARY KEY,
    stat VARCHAR(10) NOT NULL,
    confidence VARCHAR(20),
    metric_type VARCHAR(50) NOT NULL, -- 'by_stat', 'by_confidence'
    count INTEGER NOT NULL,
    mae DECIMAL(10, 2),
    rmse DECIMAL(10, 2),
    bias DECIMAL(10, 2),
    vs_line_accuracy DECIMAL(5, 2),
    within_10_pct DECIMAL(5, 2),
    within_20_pct DECIMAL(5, 2),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(stat, confidence, metric_type)
);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to automatically update updated_at
CREATE TRIGGER update_predictions_updated_at BEFORE UPDATE ON predictions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_vegas_lines_updated_at BEFORE UPDATE ON vegas_lines
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cached_api_data_updated_at BEFORE UPDATE ON cached_api_data
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

