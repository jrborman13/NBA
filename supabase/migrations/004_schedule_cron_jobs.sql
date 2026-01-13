-- Schedule pg_cron Jobs for Daily NBA Data Fetching
-- Jobs run daily at 6 AM EST (11 AM UTC)

-- Enable pg_cron extension (if not already enabled)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule job to fetch team stats
-- Runs daily at 11:00 UTC (6:00 AM EST)
SELECT cron.schedule(
    'fetch-nba-team-stats',
    '0 11 * * *',  -- Daily at 11:00 UTC
    'SELECT fetch_nba_team_stats()'
);

-- Schedule job to fetch player stats
SELECT cron.schedule(
    'fetch-nba-player-stats',
    '0 11 * * *',  -- Daily at 11:00 UTC
    'SELECT fetch_nba_player_stats()'
);

-- Schedule job to fetch game logs (staggered by 5 minutes to avoid rate limits)
SELECT cron.schedule(
    'fetch-nba-game-logs',
    '5 11 * * *',  -- Daily at 11:05 UTC
    'SELECT fetch_nba_game_logs()'
);

-- Schedule job to fetch synergy data (staggered by 10 minutes)
SELECT cron.schedule(
    'fetch-nba-synergy-data',
    '10 11 * * *',  -- Daily at 11:10 UTC
    'SELECT fetch_nba_synergy_data()'
);

-- Schedule job to fetch schedule (staggered by 15 minutes)
SELECT cron.schedule(
    'fetch-nba-schedule',
    '15 11 * * *',  -- Daily at 11:15 UTC
    'SELECT fetch_nba_schedule()'
);

-- Schedule job to fetch standings (staggered by 20 minutes)
SELECT cron.schedule(
    'fetch-nba-standings',
    '20 11 * * *',  -- Daily at 11:20 UTC
    'SELECT fetch_nba_standings()'
);

-- Schedule job to fetch player index (staggered by 25 minutes)
SELECT cron.schedule(
    'fetch-nba-player-index',
    '25 11 * * *',  -- Daily at 11:25 UTC
    'SELECT fetch_nba_player_index()'
);

-- Schedule job to fetch team on/off data (staggered by 30 minutes)
-- Note: This may need to fetch for all 30 teams, so it's scheduled later
SELECT cron.schedule(
    'fetch-nba-team-onoff',
    '30 11 * * *',  -- Daily at 11:30 UTC
    'SELECT fetch_nba_team_onoff()'
);

-- Schedule job to fetch drives stats (staggered by 35 minutes)
SELECT cron.schedule(
    'fetch-nba-drives-stats',
    '35 11 * * *',  -- Daily at 11:35 UTC
    'SELECT fetch_nba_drives_stats()'
);

-- Schedule job to fetch pbpstats (staggered by 40 minutes)
SELECT cron.schedule(
    'fetch-nba-pbpstats',
    '40 11 * * *',  -- Daily at 11:40 UTC
    'SELECT fetch_nba_pbpstats()'
);

-- View all scheduled jobs (for verification)
-- SELECT * FROM cron.job;

-- To unschedule a job (if needed):
-- SELECT cron.unschedule('fetch-nba-team-stats');

