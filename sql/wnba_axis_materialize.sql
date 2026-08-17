-- WNBA hexagon axis layer -- CORRECTION to 03. Apply on top of it.
--
-- 03 built the axis chain as pure views and argued, in its own header, that
-- the WNBA did not need the materialised table the NBA uses. That argument was
-- wrong, and it was wrong because it was sized against the wrong number.
--
-- MEASURED 2026-08-16, after 03 was applied:
--
--   select * from wnba.v_team_hexagon where season='2026' ...   8,577 ms
--   the same read through PostgREST                             HTTP 500,
--                                                               statement timeout
--
-- The reasoning error: I sized it on possessions (~110k rows for 2026) and
-- concluded the WNBA was ~30x smaller than the NBA. But the chain does not
-- read possessions to build the rim and perimeter spokes -- it reads
-- shot_event, which is a view over ALL of wnba.play_by_play: 2,693,392 rows
-- across 29 seasons. The plan confirms it:
--
--   Parallel Seq Scan on play_by_play   rows=448,232 x2 workers
--     Rows Removed by Filter: 953,652
--   CTE Scan on shots ... Rows Removed by Filter: 41,855
--
-- The `shots` CTE is referenced twice (off_shots and def_shots), so Postgres
-- materialises it for EVERY season before the caller's season predicate can
-- apply. Pushing the season filter in by hand still costs 1,585 ms for that
-- CTE alone, before any of the percentile work -- so this is not fixable by
-- indexing or restructuring. The NBA materialises for a real reason.
--
-- WHAT THIS CHANGES. v_team_axis_metrics stops computing and starts reading a
-- table; the computation moves to v_team_axis_metrics_src, matching the NBA's
-- naming. Everything above it (v_team_axis_long / _pctile / v_team_hexagon)
-- is untouched and keeps working, because it only ever referenced
-- v_team_axis_metrics.
--
-- THE COST, STATED PLAINLY. A materialised table can go stale, and that is not
-- hypothetical here: the NBA hexagon served stale numbers for 44 consecutive
-- nights because the refresh feeding it had died and nothing noticed. 03
-- claimed a view chain avoided that failure mode, and it did -- it just could
-- not meet the latency the page needs. So the failure mode is back, and it
-- has to be managed rather than designed away. The full nightly chain is now:
--
--   1. NBA repo:  LEAGUE=wnba python ingest.py --start 2026 --end 2026 --tier pbp
--   2.            select wnba.refresh_possessions('2026');
--   3.            select wnba.refresh_team_axis_metrics('2026');
--
-- NONE of that is automated today. Step 1 lives in the NBA repo's ingest,
-- steps 2 and 3 are hand-run. Until it is wired up, the WNBA hexagon is a
-- snapshot, not a live surface -- and it will silently keep rendering
-- whatever was last refreshed. Do not ship it to the site without either
-- automating this or surfacing the refresh date on the page.

-- ---------------------------------------------------------------------------
-- 1. Move the computation to _src (same body 03 gave v_team_axis_metrics)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW wnba.v_team_axis_metrics_src AS
WITH go AS (
  SELECT DISTINCT season, season_type, game_id,
         off_team_id AS team_id, def_team_id AS opp
  FROM wnba.possession
), shots AS (
  SELECT s.season, s.season_type, s.team_id AS off_team_id, g.opp AS def_team_id,
         s.shot_zone, s.shot_value, s.shot_result
  FROM wnba.shot_event s
  JOIN go g ON g.game_id = s.game_id AND g.team_id = s.team_id
           AND g.season = s.season AND g.season_type = s.season_type
), off_shots AS (
  SELECT season, season_type, off_team_id AS team_id,
    count(*) AS fga,
    count(*) FILTER (WHERE shot_zone = 'Restricted Area') AS rim_fga,
    count(*) FILTER (WHERE shot_zone = 'Restricted Area' AND shot_result = 'Made') AS rim_fgm,
    count(*) FILTER (WHERE shot_value = 3) AS fg3a,
    count(*) FILTER (WHERE shot_value = 3 AND shot_result = 'Made') AS fg3m
  FROM shots GROUP BY 1,2,3
), def_shots AS (
  SELECT season, season_type, def_team_id AS team_id,
    count(*) AS fga,
    count(*) FILTER (WHERE shot_zone = 'Restricted Area') AS rim_fga,
    count(*) FILTER (WHERE shot_zone = 'Restricted Area' AND shot_result = 'Made') AS rim_fgm,
    count(*) FILTER (WHERE shot_value = 3) AS fg3a,
    count(*) FILTER (WHERE shot_value = 3 AND shot_result = 'Made') AS fg3m
  FROM shots GROUP BY 1,2,3
), adv AS (
  SELECT season, season_type, team_id, team_name,
    (stats ->> 'OREB_PCT')::numeric   AS oreb_pct,
    (stats ->> 'DREB_PCT')::numeric   AS dreb_pct,
    (stats ->> 'OFF_RATING')::numeric AS off_rtg,
    (stats ->> 'DEF_RATING')::numeric AS def_rtg
  FROM wnba.team_season_stats
  WHERE measure_type = 'Advanced'
)
SELECT a.season, a.season_type, a.team_id, a.team_name,
  round(100.0 * o.rim_fga::numeric / NULLIF(o.fga,0)::numeric, 1)     AS o_rim_freq,
  round(100.0 * o.rim_fgm::numeric / NULLIF(o.rim_fga,0)::numeric, 1) AS o_rim_pct,
  round(100.0 * o.fg3a::numeric / NULLIF(o.fga,0)::numeric, 1)        AS o_3_freq,
  round(100.0 * o.fg3m::numeric / NULLIF(o.fg3a,0)::numeric, 1)       AS o_3pct,
  tr.transition_ppp AS o_trans_ppp, tr.transition_rate AS o_trans_rate,
  ch.second_chance_ppp AS o_2nd_ppp, ch.second_chance_rate AS o_2nd_rate,
  bo.bonus_poss_rate AS o_bonus_rate, bo.ortg_bonus AS o_bonus_ortg,
  a.oreb_pct AS o_oreb_pct,
  round(100.0 * d.rim_fga::numeric / NULLIF(d.fga,0)::numeric, 1)     AS d_rim_freq,
  round(100.0 * d.rim_fgm::numeric / NULLIF(d.rim_fga,0)::numeric, 1) AS d_rim_pct,
  round(100.0 * d.fg3a::numeric / NULLIF(d.fga,0)::numeric, 1)        AS d_3_freq,
  round(100.0 * d.fg3m::numeric / NULLIF(d.fg3a,0)::numeric, 1)       AS d_3pct,
  trd.transition_ppp_allowed AS d_trans_ppp, trd.transition_rate_allowed AS d_trans_rate,
  chd.second_chance_ppp_allowed AS d_2nd_ppp, chd.second_chance_rate_allowed AS d_2nd_rate,
  bod.bonus_poss_rate_allowed AS d_bonus_rate, bod.drtg_bonus AS d_bonus_drtg,
  a.dreb_pct AS d_dreb_pct,
  a.off_rtg, a.def_rtg,
  NULL::numeric AS o_cs_efg,
  NULL::numeric AS o_pu_efg,
  NULL::numeric AS o_open_rate,
  NULL::numeric AS o_oreb_contest,
  NULL::numeric AS d_dreb_contest,
  NULL::numeric AS d_rim_stop,
  NULL::numeric AS d_three_stop
FROM adv a
  JOIN off_shots o USING (season, season_type, team_id)
  JOIN def_shots d USING (season, season_type, team_id)
  JOIN wnba.v_team_transition_splits     tr  USING (season, season_type, team_id)
  JOIN wnba.v_team_transition_splits_def trd USING (season, season_type, team_id)
  JOIN wnba.v_team_chance_splits         ch  USING (season, season_type, team_id)
  JOIN wnba.v_team_chance_splits_def     chd USING (season, season_type, team_id)
  JOIN wnba.v_team_bonus_splits          bo  USING (season, season_type, team_id)
  JOIN wnba.v_team_bonus_splits_def      bod USING (season, season_type, team_id);

-- ---------------------------------------------------------------------------
-- 2. The materialised table -- shape taken FROM the view so types cannot drift
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wnba.team_axis_metrics AS
  SELECT * FROM wnba.v_team_axis_metrics_src WITH NO DATA;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'wnba.team_axis_metrics'::regclass AND contype = 'p'
  ) THEN
    ALTER TABLE wnba.team_axis_metrics
      ADD CONSTRAINT team_axis_metrics_pkey PRIMARY KEY (season, season_type, team_id);
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 3. v_team_axis_metrics now READS the table (columns match by construction)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW wnba.v_team_axis_metrics AS
  SELECT * FROM wnba.team_axis_metrics;

-- ---------------------------------------------------------------------------
-- 4. The refresh
-- ---------------------------------------------------------------------------
-- statement_timeout 0 for the same reason the possession engine sets it: the
-- source scan is the thing that blew the default in the first place, and the
-- NBA's equivalent function died nightly for six weeks without it.
CREATE OR REPLACE FUNCTION wnba.refresh_team_axis_metrics(p_season text)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  PERFORM set_config('statement_timeout','0',true);
  DELETE FROM wnba.team_axis_metrics WHERE season = p_season;
  INSERT INTO wnba.team_axis_metrics
    SELECT * FROM wnba.v_team_axis_metrics_src WHERE season = p_season;
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

-- Build both seasons:
--   select wnba.refresh_team_axis_metrics('2025');   -- expect 21 (13 RS + 8 PO)
--   select wnba.refresh_team_axis_metrics('2026');   -- expect 15
