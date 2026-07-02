-- ============================================================================
-- hexagon_weights.sql  —  DEPLOYED to "NBA App" (qhrgekcowkgwcaaqyqvv)
-- ----------------------------------------------------------------------------
-- Config-driven weighting for the player hexagon. Supersedes the inline weights
-- that used to live in v_player_hexagon (see hexagon_assembly.sql).
--
-- LAYERS
--   player_axis_metrics      raw sub-metrics per player/season (materialized; unchanged)
--   v_player_axis_pctile     0-100 percentile of each sub-metric within pool/season
--                            (NO weights applied — so re-weighting is a pure recompute)
--   hexagon_weights          editable per-sub-metric weights (axis, sub_metric, weight)
--   v_player_hexagon         weighted mean of percentiles per axis (reads hexagon_weights)
--
-- To re-tune grades: UPDATE hexagon_weights SET weight=... WHERE axis=.. AND sub_metric=..;
--   (instant, all seasons, no re-backfill). The Streamlit page (7_Hexagon.py) also lets you
--   edit weights live in-session via a data_editor seeded from this table.
-- Adding/removing a SUB-METRIC still requires editing player_axis_metrics +
--   refresh_player_axis_metrics and re-running the per-season backfill.
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.hexagon_weights (
  axis text NOT NULL, sub_metric text NOT NULL, weight numeric NOT NULL DEFAULT 1,
  PRIMARY KEY (axis, sub_metric)
);
INSERT INTO public.hexagon_weights (axis, sub_metric, weight) VALUES
  -- finishing re-tuned 2026-07-01 via the weight backtest: team_rim_freq_lift dropped to 0 (noisy on/off).
  ('finishing','rim_rate',1), ('finishing','rim_fg_pct_over_league',2), ('finishing','team_rim_freq_lift',0),
  -- Shooting split made REAL 2026-06-30 (Part C): real catch-&-shoot / pull-up eFG are primary;
  -- the noisy shotmaking_over_exp is floored (jump_fga>=150) and reduced 2->1; spotup_ppp is
  -- floored (>=50 spot-up poss, inside v_player_shooting); the redundant unfloored atb3_pct was
  -- DROPPED (cs_efg covers catch-&-shoot 3 quality with a volume floor). Mirrors the Defending recipe.
  ('shooting','cs_efg',2), ('shooting','pu_efg',1.5),
  ('shooting','shotmaking_over_exp',1), ('shooting','spotup_ppp',1),
  -- playmaking re-tuned 2026-07-01 via the weight backtest: lead on ast_pts_created; ast_pct + drive_ast dropped to 0.
  ('playmaking','ast_pct',0), ('playmaking','ast_pts_created',1), ('playmaking','drive_ast',0),
  -- Defending axis made REAL 2026-06-30 (Part C): direct tracking metrics replace the BLK/STL/on-off
  -- proxy. blk/stl kept at reduced weight; drtg_swing dropped. (def_* sub-metrics added to
  -- player_axis_metrics + v_player_axis_pctile + v_player_hexagon below.)
  ('defending','blk_per100',1), ('defending','stl_per100',1),
  ('defending','def_rim_stop',2), ('defending','def_pm_stop',1.5),
  ('defending','contested2_per36',1), ('defending','deflections_per36',1.5),
  -- Rebounding contested% made REAL 2026-06-30 (Part C): contested_reb_per36 (REB_CONTEST) +
  -- reb_chance_pct (REB/REB_CHANCES conversion) add a toughness/conversion dimension over raw rates.
  ('rebounding','oreb_pct',1.5), ('rebounding','dreb_pct',1.5), ('rebounding','sc_rate_on_minus_off',1),
  ('rebounding','contested_reb_per36',1), ('rebounding','reb_chance_pct',1),
  ('gravity','shot_diet_gravity_efg',2), ('gravity','off_rating_lift',1), ('gravity','rim_freq_lift',1)
ON CONFLICT (axis, sub_metric) DO NOTHING;
-- NOTE: atb3_pct was seeded historically; Part C removed it from the Shooting axis via
-- DELETE FROM hexagon_weights WHERE axis='shooting' AND sub_metric='atb3_pct';
-- (the sub-metric still appears in v_player_hexagon's lateral but, having no weight row, is ignored.)

-- v_player_axis_pctile: percent_rank() of each sub-metric within (pool, bucket, season),
-- ×100. pos_group bucket = 'ALL' for pool 'all', else G/F/C. NULL sub-metrics stay NULL.
CREATE OR REPLACE VIEW public.v_player_axis_pctile AS
WITH mm AS (
  SELECT 'all'::text AS pool, 'ALL'::text AS bucket, m.* FROM public.player_axis_metrics m
  UNION ALL
  SELECT 'position', pos_group, m.* FROM public.player_axis_metrics m WHERE pos_group IN ('G','F','C')
),
pr AS (
  SELECT pool, season, season_type, player_id, off_poss_on, pos_group,
    CASE WHEN rim_rate IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY rim_rate) END AS rim_rate,
    CASE WHEN rim_fg_pct_over_league IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY rim_fg_pct_over_league) END AS rim_fg_pct_over_league,
    CASE WHEN team_rim_freq_lift IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY team_rim_freq_lift) END AS team_rim_freq_lift,
    CASE WHEN shotmaking_over_exp IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY shotmaking_over_exp) END AS shotmaking_over_exp,
    CASE WHEN atb3_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY atb3_pct) END AS atb3_pct,
    CASE WHEN spotup_ppp IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY spotup_ppp) END AS spotup_ppp,
    CASE WHEN ast_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY ast_pct) END AS ast_pct,
    CASE WHEN ast_pts_created IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY ast_pts_created) END AS ast_pts_created,
    CASE WHEN drive_ast IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY drive_ast) END AS drive_ast,
    CASE WHEN blk_per100 IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY blk_per100) END AS blk_per100,
    CASE WHEN stl_per100 IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY stl_per100) END AS stl_per100,
    CASE WHEN drtg_swing IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY drtg_swing) END AS drtg_swing,
    CASE WHEN oreb_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY oreb_pct) END AS oreb_pct,
    CASE WHEN dreb_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY dreb_pct) END AS dreb_pct,
    CASE WHEN sc_rate_on_minus_off IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY sc_rate_on_minus_off) END AS sc_rate_on_minus_off,
    CASE WHEN shot_diet_gravity_efg IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY shot_diet_gravity_efg) END AS shot_diet_gravity_efg,
    CASE WHEN off_rating_lift IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY off_rating_lift) END AS off_rating_lift,
    CASE WHEN rim_freq_lift IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY rim_freq_lift) END AS rim_freq_lift,
    CASE WHEN def_rim_stop IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY def_rim_stop) END AS def_rim_stop,
    CASE WHEN def_pm_stop IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY def_pm_stop) END AS def_pm_stop,
    CASE WHEN deflections_per36 IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY deflections_per36) END AS deflections_per36,
    CASE WHEN contested2_per36 IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY contested2_per36) END AS contested2_per36,
    CASE WHEN cs_efg IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY cs_efg) END AS cs_efg,
    CASE WHEN pu_efg IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY pu_efg) END AS pu_efg,
    CASE WHEN contested_reb_per36 IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY contested_reb_per36) END AS contested_reb_per36,
    CASE WHEN reb_chance_pct IS NULL THEN NULL ELSE percent_rank() OVER (PARTITION BY pool,bucket,season,season_type ORDER BY reb_chance_pct) END AS reb_chance_pct
  FROM mm
)
SELECT pool, season, season_type, player_id, off_poss_on, pos_group,
  round((100*rim_rate)::numeric,2) rim_rate, round((100*rim_fg_pct_over_league)::numeric,2) rim_fg_pct_over_league, round((100*team_rim_freq_lift)::numeric,2) team_rim_freq_lift,
  round((100*shotmaking_over_exp)::numeric,2) shotmaking_over_exp, round((100*atb3_pct)::numeric,2) atb3_pct, round((100*spotup_ppp)::numeric,2) spotup_ppp,
  round((100*ast_pct)::numeric,2) ast_pct, round((100*ast_pts_created)::numeric,2) ast_pts_created, round((100*drive_ast)::numeric,2) drive_ast,
  round((100*blk_per100)::numeric,2) blk_per100, round((100*stl_per100)::numeric,2) stl_per100, round((100*drtg_swing)::numeric,2) drtg_swing,
  round((100*oreb_pct)::numeric,2) oreb_pct, round((100*dreb_pct)::numeric,2) dreb_pct, round((100*sc_rate_on_minus_off)::numeric,2) sc_rate_on_minus_off,
  round((100*shot_diet_gravity_efg)::numeric,2) shot_diet_gravity_efg, round((100*off_rating_lift)::numeric,2) off_rating_lift, round((100*rim_freq_lift)::numeric,2) rim_freq_lift,
  round((100*def_rim_stop)::numeric,2) def_rim_stop, round((100*def_pm_stop)::numeric,2) def_pm_stop,
  round((100*deflections_per36)::numeric,2) deflections_per36, round((100*contested2_per36)::numeric,2) contested2_per36,
  round((100*cs_efg)::numeric,2) cs_efg, round((100*pu_efg)::numeric,2) pu_efg,
  round((100*contested_reb_per36)::numeric,2) contested_reb_per36, round((100*reb_chance_pct)::numeric,2) reb_chance_pct
FROM pr;

-- v_player_hexagon: unpivot the percentiles, join weights, weighted mean per axis (null-skipped).
CREATE OR REPLACE VIEW public.v_player_hexagon AS
WITH px AS (SELECT * FROM public.v_player_axis_pctile),
long AS (
  SELECT px.pool, px.season, px.season_type, px.player_id, px.off_poss_on, px.pos_group, v.axis, v.sub_metric, v.pctile
  FROM px CROSS JOIN LATERAL (VALUES
    ('finishing','rim_rate',px.rim_rate),('finishing','rim_fg_pct_over_league',px.rim_fg_pct_over_league),('finishing','team_rim_freq_lift',px.team_rim_freq_lift),
    ('shooting','shotmaking_over_exp',px.shotmaking_over_exp),('shooting','atb3_pct',px.atb3_pct),('shooting','spotup_ppp',px.spotup_ppp),
    ('shooting','cs_efg',px.cs_efg),('shooting','pu_efg',px.pu_efg),
    ('playmaking','ast_pct',px.ast_pct),('playmaking','ast_pts_created',px.ast_pts_created),('playmaking','drive_ast',px.drive_ast),
    ('defending','blk_per100',px.blk_per100),('defending','stl_per100',px.stl_per100),
    ('defending','def_rim_stop',px.def_rim_stop),('defending','def_pm_stop',px.def_pm_stop),
    ('defending','contested2_per36',px.contested2_per36),('defending','deflections_per36',px.deflections_per36),
    ('rebounding','oreb_pct',px.oreb_pct),('rebounding','dreb_pct',px.dreb_pct),('rebounding','sc_rate_on_minus_off',px.sc_rate_on_minus_off),
    ('rebounding','contested_reb_per36',px.contested_reb_per36),('rebounding','reb_chance_pct',px.reb_chance_pct),
    ('gravity','shot_diet_gravity_efg',px.shot_diet_gravity_efg),('gravity','off_rating_lift',px.off_rating_lift),('gravity','rim_freq_lift',px.rim_freq_lift)
  ) v(axis, sub_metric, pctile)
),
scored AS (
  SELECT l.pool, l.season, l.season_type, l.player_id, l.off_poss_on, l.pos_group, l.axis,
    sum(w.weight * l.pctile) / nullif(sum(w.weight) FILTER (WHERE l.pctile IS NOT NULL),0) AS score
  FROM long l JOIN public.hexagon_weights w ON w.axis=l.axis AND w.sub_metric=l.sub_metric
  GROUP BY l.pool, l.season, l.season_type, l.player_id, l.off_poss_on, l.pos_group, l.axis
)
SELECT pool, season, season_type, player_id, pos_group, off_poss_on,
  round(max(score) FILTER (WHERE axis='finishing'))::int  AS finishing,
  round(max(score) FILTER (WHERE axis='shooting'))::int   AS shooting,
  round(max(score) FILTER (WHERE axis='playmaking'))::int AS playmaking,
  round(max(score) FILTER (WHERE axis='defending'))::int  AS defending,
  round(max(score) FILTER (WHERE axis='rebounding'))::int AS rebounding,
  round(max(score) FILTER (WHERE axis='gravity'))::int    AS gravity
FROM scored
GROUP BY pool, season, season_type, player_id, pos_group, off_poss_on;

GRANT SELECT ON public.hexagon_weights, public.v_player_axis_pctile TO anon, authenticated;

-- NEXT LEVER (normalization): v_player_axis_pctile isolates the normalization step. To switch
-- from percentile to z-score (preserves magnitude/separation), swap percent_rank() for
-- (x - avg(x)) / nullif(stddev_samp(x),0) over the same partition, mapped to 0-100; everything
-- downstream (weights, hexagon) is unchanged.
