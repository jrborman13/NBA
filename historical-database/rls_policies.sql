-- ============================================================================
-- Row Level Security (RLS) policies — DRAFT for review
-- ============================================================================
-- Supabase flagged: RLS is disabled on every table, so anyone with the ANON key can
-- read AND write every row. This file locks the data down WITHOUT breaking anything.
--
-- Key facts that make this safe:
--   * The historical-database ingestion (scripts/) connects with SUPABASE_SERVICE_KEY.
--     The service_role BYPASSES RLS entirely — so enabling RLS never blocks ingestion.
--   * The Streamlit app connects with SUPABASE_KEY (anon) and both READS and WRITES
--     some tables (predictions, parlay_log, player_predictions, vegas_lines,
--     cached_api_data, ...). Making those anon read-only WOULD break the app — so they
--     are intentionally left for you to decide (Part B).
--
-- Model: anon/authenticated may SELECT (read) the reference data; only service_role may
-- write (it bypasses RLS, so no write policy is needed). Absence of an INSERT/UPDATE/DELETE
-- policy under RLS = those commands are denied for anon.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- PART A — Historical-database tables  (SAFE TO APPLY)
-- Written only by scripts/ via the service key; read by future FastAPI/website/app.
-- Enable RLS + anon read-only on the 16 data tables.
-- ----------------------------------------------------------------------------
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'teams','players','team_season_stats','player_season_stats','team_standings',
    'team_season_clutch','player_season_clutch','pt_tracking_player','pt_tracking_team',
    'synergy_playtypes','team_player_onoff','player_passing','schedule',
    'team_game_logs','player_game_logs','play_by_play'
  ] LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', t || '_anon_read', t);
    EXECUTE format(
      $p$CREATE POLICY %I ON public.%I FOR SELECT TO anon, authenticated USING (true)$p$,
      t || '_anon_read', t);
  END LOOP;
END $$;

-- ingestion_log is internal ops metadata — enable RLS with NO anon policy, so only the
-- service_role can read/write it (anon gets nothing). Remove this if you want it public-read.
ALTER TABLE public.ingestion_log ENABLE ROW LEVEL SECURITY;


-- ----------------------------------------------------------------------------
-- PART B — Existing app tables  (DO NOT BLANKET-APPLY — decide first)
-- ----------------------------------------------------------------------------
-- B1. App-WRITE tables (the Streamlit app writes these with the ANON key). Making them
--     anon read-only BREAKS the app. Options:
--       (recommended) move these writes to the service key in the app, THEN apply the
--       Part-A pattern (anon read-only) to them; or
--       leave RLS off, or add permissive anon write policies (no real security gain).
--     Verify the exact set against the app before deciding. Known app-write tables:
--       predictions, player_predictions, parlay_log, vegas_lines, cached_api_data,
--       accuracy_metrics, wnba_predictions
--
-- B2. Fetch-pipeline tables (nba_*, sr_*, wnba_* stats). These are populated by the
--     scripts/fetch_*.py pipeline. IF those scripts use the service key (verify), they are
--     read-only-anon-safe and you can apply the Part-A pattern to them too:
--       nba_team_stats, nba_player_stats, nba_game_logs, nba_synergy_data, nba_schedule,
--       nba_standings, nba_player_index, nba_team_onoff, nba_drives_stats, nba_pbpstats,
--       sr_team_stats, sr_player_stats, sr_game_logs, sr_synergy_data, sr_schedule,
--       sr_standings, sr_player_index,
--       wnba_team_stats, wnba_player_stats, wnba_game_logs, wnba_schedule, wnba_standings,
--       wnba_player_index, wnba_pbpstats, wnba_team_onoff, wnba_pbpstats_players
--
-- Template to make a verified-service-written table anon read-only:
--   ALTER TABLE public.<table> ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY <table>_anon_read ON public.<table>
--     FOR SELECT TO anon, authenticated USING (true);
-- ============================================================================
