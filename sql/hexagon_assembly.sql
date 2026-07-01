-- ============================================================================
-- hexagon_assembly.sql  —  DEPLOYED to "NBA App" (qhrgekcowkgwcaaqyqvv)
-- ----------------------------------------------------------------------------
-- Materializes the 18 raw hexagon sub-metrics into player_axis_metrics (per
-- season, via 6 sequential steps), then v_player_hexagon computes 0-100
-- percentile axis scores live from that small table for two pools (all / position).
--
-- WHY MATERIALIZED: the shot-scanning axis views (finishing/shooting/defending)
-- read shot_event, a VIEW recomputed over all play_by_play, so joining six of
-- them live times out. Each refresh step scans at most 1-2 of them for one season.
--
-- POOLS: 'all' = vs all qualified players (>=1000 on-court off poss);
--        'position' = vs role group. pos_group is a ROLE PROXY (NBA position is
--        sparse): dreb_pct>=0.18 -> C, ast_pct>=0.15 -> G, else F.
-- WEIGHTS: see axis means below (e.g. Defending weights BLK/STL 2x vs DRtg swing).
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.player_axis_metrics (
  season text NOT NULL, season_type text NOT NULL, player_id bigint NOT NULL,
  pos_group text, off_poss_on int,
  rim_rate numeric, rim_fg_pct_over_league numeric, team_rim_freq_lift numeric,
  shotmaking_over_exp numeric, atb3_pct numeric, spotup_ppp numeric,
  ast_pct numeric, ast_pts_created numeric, drive_ast numeric,
  blk_per100 numeric, stl_per100 numeric, drtg_swing numeric,
  oreb_pct numeric, dreb_pct numeric, sc_rate_on_minus_off numeric,
  shot_diet_gravity_efg numeric, off_rating_lift numeric, rim_freq_lift numeric,
  PRIMARY KEY (season, season_type, player_id)
);
CREATE INDEX IF NOT EXISTS ix_pam_season ON public.player_axis_metrics (season, season_type);

CREATE OR REPLACE FUNCTION public.refresh_player_axis_metrics(p_season text)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  PERFORM set_config('statement_timeout','0',true);  -- effective under pg_cron; for API use prefix `SET statement_timeout=0;`
  DELETE FROM public.player_axis_metrics WHERE season = p_season;

  INSERT INTO public.player_axis_metrics
    (season, season_type, player_id, off_poss_on, shot_diet_gravity_efg, off_rating_lift, rim_freq_lift)
  SELECT g.season, g.season_type, g.player_id, g.off_poss_on, g.shot_diet_gravity_efg, g.off_rating_lift, g.rim_freq_lift
  FROM public.v_player_gravity g WHERE g.season=p_season AND g.off_poss_on >= 1000;

  UPDATE public.player_axis_metrics t SET rim_rate=f.rim_rate, rim_fg_pct_over_league=f.rim_fg_pct_over_league, team_rim_freq_lift=f.team_rim_freq_lift
    FROM public.v_player_finishing f WHERE t.season=p_season AND f.season=t.season AND f.season_type=t.season_type AND f.player_id=t.player_id;
  UPDATE public.player_axis_metrics t SET shotmaking_over_exp=s.shotmaking_over_exp, atb3_pct=s.atb3_pct, spotup_ppp=s.spotup_ppp
    FROM public.v_player_shooting s WHERE t.season=p_season AND s.season=t.season AND s.season_type=t.season_type AND s.player_id=t.player_id;
  UPDATE public.player_axis_metrics t SET ast_pct=p.ast_pct, ast_pts_created=p.ast_pts_created, drive_ast=p.drive_ast
    FROM public.v_player_playmaking p WHERE t.season=p_season AND p.season=t.season AND p.season_type=t.season_type AND p.player_id=t.player_id;
  UPDATE public.player_axis_metrics t SET blk_per100=d.blk_per100, stl_per100=d.stl_per100, drtg_swing=d.drtg_swing
    FROM public.v_player_defending d WHERE t.season=p_season AND d.season=t.season AND d.season_type=t.season_type AND d.player_id=t.player_id;
  UPDATE public.player_axis_metrics t SET oreb_pct=r.oreb_pct, dreb_pct=r.dreb_pct, sc_rate_on_minus_off=r.sc_rate_on_minus_off
    FROM public.v_player_rebounding r WHERE t.season=p_season AND r.season=t.season AND r.season_type=t.season_type AND r.player_id=t.player_id;

  UPDATE public.player_axis_metrics SET pos_group =
    CASE WHEN dreb_pct >= 0.18 THEN 'C' WHEN ast_pct >= 0.15 THEN 'G' ELSE 'F' END
  WHERE season=p_season;

  GET DIAGNOSTICS n = ROW_COUNT; RETURN n;
END $$;

-- Initial population: run each season individually with the timeout disabled.
--   SET statement_timeout=0; SELECT public.refresh_player_axis_metrics('2025-26');  -- repeat per season

CREATE OR REPLACE VIEW public.v_player_hexagon AS
WITH mm AS (
  SELECT 'all'::text AS pool, 'ALL'::text AS bucket, m.* FROM public.player_axis_metrics m
  UNION ALL
  SELECT 'position', pos_group, m.* FROM public.player_axis_metrics m WHERE pos_group IN ('G','F','C')
),
pr AS (
  SELECT pool, season, season_type, player_id, off_poss_on, pos_group,
    CASE WHEN rim_rate IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY rim_rate) END AS p_rim_rate,
    CASE WHEN rim_fg_pct_over_league IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY rim_fg_pct_over_league) END AS p_rim_oe,
    CASE WHEN team_rim_freq_lift IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY team_rim_freq_lift) END AS p_rim_lift,
    CASE WHEN shotmaking_over_exp IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY shotmaking_over_exp) END AS p_make_oe,
    CASE WHEN atb3_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY atb3_pct) END AS p_atb3,
    CASE WHEN spotup_ppp IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY spotup_ppp) END AS p_spotup,
    CASE WHEN ast_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY ast_pct) END AS p_astpct,
    CASE WHEN ast_pts_created IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY ast_pts_created) END AS p_astpts,
    CASE WHEN drive_ast IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY drive_ast) END AS p_driveast,
    CASE WHEN blk_per100 IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY blk_per100) END AS p_blk,
    CASE WHEN stl_per100 IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY stl_per100) END AS p_stl,
    CASE WHEN drtg_swing IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY drtg_swing) END AS p_drtg,
    CASE WHEN oreb_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY oreb_pct) END AS p_oreb,
    CASE WHEN dreb_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY dreb_pct) END AS p_dreb,
    CASE WHEN sc_rate_on_minus_off IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY sc_rate_on_minus_off) END AS p_scon,
    CASE WHEN shot_diet_gravity_efg IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY shot_diet_gravity_efg) END AS p_grav,
    CASE WHEN off_rating_lift IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY off_rating_lift) END AS p_ortglift,
    CASE WHEN rim_freq_lift IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY rim_freq_lift) END AS p_rimfreqlift
  FROM mm
),
ax AS (
  SELECT pool, season, season_type, player_id, off_poss_on, pos_group,
    (1*coalesce(p_rim_rate,0)+2*coalesce(p_rim_oe,0)+1*coalesce(p_rim_lift,0))/nullif(1*(p_rim_rate IS NOT NULL)::int+2*(p_rim_oe IS NOT NULL)::int+1*(p_rim_lift IS NOT NULL)::int,0) AS a_fin,
    (2*coalesce(p_make_oe,0)+1*coalesce(p_atb3,0)+1*coalesce(p_spotup,0))/nullif(2*(p_make_oe IS NOT NULL)::int+1*(p_atb3 IS NOT NULL)::int+1*(p_spotup IS NOT NULL)::int,0) AS a_shoot,
    (2*coalesce(p_astpct,0)+1.5*coalesce(p_astpts,0)+1*coalesce(p_driveast,0))/nullif(2*(p_astpct IS NOT NULL)::int+1.5*(p_astpts IS NOT NULL)::int+1*(p_driveast IS NOT NULL)::int,0) AS a_play,
    (2*coalesce(p_blk,0)+2*coalesce(p_stl,0)+1*coalesce(p_drtg,0))/nullif(2*(p_blk IS NOT NULL)::int+2*(p_stl IS NOT NULL)::int+1*(p_drtg IS NOT NULL)::int,0) AS a_def,
    (1.5*coalesce(p_oreb,0)+1.5*coalesce(p_dreb,0)+1*coalesce(p_scon,0))/nullif(1.5*(p_oreb IS NOT NULL)::int+1.5*(p_dreb IS NOT NULL)::int+1*(p_scon IS NOT NULL)::int,0) AS a_reb,
    (2*coalesce(p_grav,0)+1*coalesce(p_ortglift,0)+1*coalesce(p_rimfreqlift,0))/nullif(2*(p_grav IS NOT NULL)::int+1*(p_ortglift IS NOT NULL)::int+1*(p_rimfreqlift IS NOT NULL)::int,0) AS a_grav
  FROM pr
)
SELECT pool, season, season_type, player_id, pos_group, off_poss_on,
  round(100*a_fin)::int AS finishing, round(100*a_shoot)::int AS shooting,
  round(100*a_play)::int AS playmaking, round(100*a_def)::int AS defending,
  round(100*a_reb)::int AS rebounding, round(100*a_grav)::int AS gravity
FROM ax;

-- Streamlit page: combined-app/pages/7_Hexagon.py (reads v_player_hexagon + player_axis_metrics).
-- Daily refresh wired in refresh_show_rollups(): PERFORM refresh_player_axis_metrics(v_season);
-- Anon read access: GRANT SELECT ON v_player_hexagon, player_axis_metrics, ... TO anon, authenticated;
