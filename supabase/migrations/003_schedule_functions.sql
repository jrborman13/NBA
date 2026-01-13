-- PostgreSQL Functions to Call Supabase Edge Functions
-- These functions will be scheduled via pg_cron to fetch NBA data daily

-- Enable required extensions
-- Note: pg_net is available in Supabase, http extension may not be
-- We'll use pg_net for HTTP requests
CREATE EXTENSION IF NOT EXISTS pg_net;

-- Function to get Supabase project URL from environment
-- Note: This will need to be set via Supabase dashboard or environment variable
-- For now, we'll use a placeholder that should be replaced with actual project URLi'

-- Function to call Edge Function for fetching team stats
CREATE OR REPLACE FUNCTION fetch_nba_team_stats()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    -- Call Edge Function via HTTP POST using pg_net
    -- Note: pg_net.http_post is asynchronous, status will be logged by Edge Function
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-team-stats',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching player stats
CREATE OR REPLACE FUNCTION fetch_nba_player_stats()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-player-stats',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching game logs
CREATE OR REPLACE FUNCTION fetch_nba_game_logs()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-game-logs',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching synergy data
CREATE OR REPLACE FUNCTION fetch_nba_synergy_data()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-synergy-data',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching schedule
CREATE OR REPLACE FUNCTION fetch_nba_schedule()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-schedule',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching standings
CREATE OR REPLACE FUNCTION fetch_nba_standings()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-standings',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching player index
CREATE OR REPLACE FUNCTION fetch_nba_player_index()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-player-index',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching team on/off data
CREATE OR REPLACE FUNCTION fetch_nba_team_onoff()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-team-onoff',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching drives stats
CREATE OR REPLACE FUNCTION fetch_nba_drives_stats()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-drives-stats',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to call Edge Function for fetching pbpstats
CREATE OR REPLACE FUNCTION fetch_nba_pbpstats()
RETURNS void AS $$
DECLARE
    project_url TEXT := 'https://qhrgekcowkgwcaaqyqvv.supabase.co';
    service_key TEXT := 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFocmdla2Nvd2tnd2NhYXF5cXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2Nzg0Mzg2OSwiZXhwIjoyMDgzNDE5ODY5fQ.jrM19hhfH_QSVulW9GRbRossYE9cZQ006l7s2YaBt-o'; -- Replace with your actual service role key
BEGIN
    PERFORM net.http_post(
        url := project_url || '/functions/v1/fetch-pbpstats',
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'Authorization', 'Bearer ' || service_key
        ),
        body := '{}'::jsonb
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

