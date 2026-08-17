-- WNBA hexagon -- the nightly refresh. Apply after 01 and 04.
--
-- WHY pg_cron AND NOT THE PostgREST RPC.
-- Measured 2026-08-16: POST /rest/v1/rpc/refresh_team_axis_metrics with the
-- service key returns HTTP 500, 57014 "canceling statement due to statement
-- timeout", after 9.7s -- even though the function body already calls
-- set_config('statement_timeout','0',true).
--
-- That set_config does NOT rescue the call, and the reason is worth writing
-- down because it is easy to get wrong twice: statement_timeout is armed when
-- the statement STARTS. Changing it from inside a function that is already
-- running does not disarm the timer for the statement currently executing --
-- it only affects later statements. The NBA side gets this right by accident
-- of shape, because its pg_cron command sets the timeout as a SEPARATE
-- statement before the call:
--
--   SET statement_timeout = '30min'; SELECT public.refresh_show_rollups();
--
-- PostgREST owns its own transaction and will not do that, so the RPC route is
-- closed for anything slow. Keeping the in-function set_config anyway: it is
-- correct for nested statements and costs nothing.
--
-- Filtering the source by season first gets the rebuild to ~3.8s, which would
-- fit today. It is not used as the fix, because that number grows with every
-- game played and the whole design would then be tuned to an HTTP timeout it
-- does not need to care about. A nightly batch job belongs on a connection that
-- allows long statements.
--
-- WHAT THIS DOES NOT COVER. pg_cron cannot do step 1 of the chain -- pulling
-- new play-by-play from stats.wnba.com. Akamai drops datacenter IPs, which is
-- why the whole fetch pipeline lives on the Mac. Step 1 is handled by
-- run_all_fetches.py; this file is steps 2 and 3 only. If step 1 stops running,
-- these two will happily refresh the same games every night and the hexagon
-- will sit still while looking healthy. That is the failure this project has
-- now hit three times, so check_ingest_health is the thing that must catch it,
-- not this.

-- ---------------------------------------------------------------------------
-- 1. The current season, derived rather than hardcoded
-- ---------------------------------------------------------------------------
-- A cron job with '2026' baked in silently stops being correct next May. This
-- reads the season from the data, so rollover needs no edit: whatever season
-- the ingest last wrote play-by-play for is the one refreshed. If the ingest
-- has not run for a new season yet, this correctly keeps refreshing the old
-- one rather than building an empty new one.
CREATE OR REPLACE FUNCTION wnba.current_pbp_season()
RETURNS text LANGUAGE sql STABLE AS $$
  SELECT max(season) FROM wnba.play_by_play;
$$;

-- ---------------------------------------------------------------------------
-- 2. One entry point for the nightly
-- ---------------------------------------------------------------------------
-- Returns a row per step so the cron log says which half moved, rather than a
-- bare integer that could mean either.
CREATE OR REPLACE FUNCTION wnba.refresh_hexagon_current()
RETURNS TABLE(step text, season text, rows_written integer)
LANGUAGE plpgsql AS $$
DECLARE s text;
BEGIN
  PERFORM set_config('statement_timeout','0',true);
  s := wnba.current_pbp_season();
  IF s IS NULL THEN
    RAISE EXCEPTION 'wnba.play_by_play is empty -- refusing to refresh into a void';
  END IF;

  step := 'possessions';        season := s;
  rows_written := wnba.refresh_possessions(s);
  RETURN NEXT;

  step := 'team_axis_metrics';  season := s;
  rows_written := wnba.refresh_team_axis_metrics(s);
  RETURN NEXT;
END $$;

-- ---------------------------------------------------------------------------
-- 3. Schedule it
-- ---------------------------------------------------------------------------
-- 13:30 UTC = 08:30 America/Chicago. The launchd fetch on the Mac runs at
-- 07:00 local and takes a few minutes, and the NBA's own rollup job sits at
-- 11:45 UTC, so this lands clear of both with headroom.
--
-- statement_timeout is SET AS ITS OWN STATEMENT, before the call. That is the
-- entire point of this file -- see the header.
SELECT cron.schedule(
  'refresh-wnba-hexagon',
  '30 13 * * *',
  $cron$SET statement_timeout = '30min'; SELECT * FROM wnba.refresh_hexagon_current();$cron$
);

-- Verify:
--   select jobid, jobname, schedule, active from cron.job order by jobid;
--   select * from wnba.refresh_hexagon_current();   -- run once by hand first
--
-- After a night, confirm it actually ran AND did something:
--   select jobname, status, return_message, start_time, end_time
--   from cron.job_run_details d join cron.job j using (jobid)
--   where j.jobname = 'refresh-wnba-hexagon' order by start_time desc limit 5;
