-- ============================================================================
-- hexagon_axes.sql  —  DEPLOYED to "NBA App" (qhrgekcowkgwcaaqyqvv)
-- ----------------------------------------------------------------------------
-- Completes the six-axis player hexagon. Builds on possession_engine.sql and
-- hexagon_and_splits.sql (Finishing / Rebounding / Gravity already there).
-- Adds: Shooting, Playmaking, Defending axes + the assembled v_player_hexagon.
--
-- VALIDATION (2025-26 RS, face validity of final hexagon 0-100 scores)
--   Jokic   — gravity 99, playmaking 84, finishing 80 (complete hub)
--   Gobert  — rebounding 94, finishing 70, defending 66; SHOOTING 1, gravity 15
--   Curry   — shooting 70, gravity 79, rebounding 15
--   SGA     — playmaking 97, shooting 83, defending 71, rebounding 17
--   Wembanyama tops blocks (5.15/100, +9.1 DRtg swing); Jokic tops shot-diet gravity.
--
-- DATA GAPS surfaced (and worked around)
--   • play_by_play.assist_person_id is NULL warehouse-wide (assister only in the
--     description text). Dropped the assisted-high-value playmaking metric and the
--     assisted/unassisted "self-creation" idea cannot be built without name-parsing.
--   • No tracking-defense feed (no deflections / defended-FG%). Defending is a
--     PROXY axis: blocks/steals (weighted 2x) + DRtg on/off swing + opponent rim
--     FG% / eFG suppression on/off (lineup-confounded, weighted lightly).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- SHOOTING — jump-shot making over expectation, ATB3/C3, spot-up/off-screen, C&S/pull-up.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_player_shooting AS
WITH zb AS (
  SELECT season, season_type, shot_zone,
    avg(CASE WHEN shot_result='Made' AND shot_value=3 THEN 1.5 WHEN shot_result='Made' THEN 1.0 ELSE 0 END) AS lg_zone_efg
  FROM public.shot_event GROUP BY 1,2,3
),
se AS (
  SELECT s.season, s.season_type, s.shooter_id AS player_id,
    count(*) FILTER (WHERE s.shot_zone NOT IN ('Restricted Area','Backcourt')) AS jump_fga,
    round(avg(CASE WHEN s.shot_result='Made' AND s.shot_value=3 THEN 1.5 WHEN s.shot_result='Made' THEN 1.0 ELSE 0 END)
          FILTER (WHERE s.shot_zone NOT IN ('Restricted Area','Backcourt')),4) AS jump_efg,
    round(avg(zb.lg_zone_efg) FILTER (WHERE s.shot_zone NOT IN ('Restricted Area','Backcourt')),4) AS jump_efg_exp,
    round(avg((s.shot_result='Made')::int) FILTER (WHERE s.shot_zone='Above-the-Break 3'),4) AS atb3_pct,
    round(avg((s.shot_result='Made')::int) FILTER (WHERE s.shot_zone IN ('Left Corner 3','Right Corner 3')),4) AS c3_pct,
    round(avg((s.shot_value=3)::int),4) AS three_rate
  FROM public.shot_event s JOIN zb USING (season, season_type, shot_zone)
  GROUP BY 1,2,3
),
syn AS (
  -- Part C: spotup_ppp floored at >=50 spot-up possessions (else NULL) so low-volume rim-runners
  -- whose Shooting axis was carried by a handful of spot-ups drop out of that percentile pool.
  SELECT season, season_type, entity_id AS player_id,
    CASE WHEN sum((stats->>'POSS')::numeric) FILTER (WHERE play_type='Spotup') >= 50
         THEN round(sum((stats->>'PPP')::numeric*(stats->>'POSS')::numeric) FILTER (WHERE play_type='Spotup')
              / nullif(sum((stats->>'POSS')::numeric) FILTER (WHERE play_type='Spotup'),0),3) END AS spotup_ppp,
    round(sum((stats->>'PPP')::numeric*(stats->>'POSS')::numeric) FILTER (WHERE play_type='OffScreen')
          / nullif(sum((stats->>'POSS')::numeric) FILTER (WHERE play_type='OffScreen'),0),3) AS offscreen_ppp
  FROM public.synergy_playtypes
  WHERE entity_type='P' AND type_grouping='offensive' AND play_type IN ('Spotup','OffScreen')
  GROUP BY 1,2,3
),
cs AS (
  SELECT season, season_type, player_id,
    round(sum((stats->>'CATCH_SHOOT_EFG_PCT')::numeric*(stats->>'CATCH_SHOOT_FGA')::numeric)/nullif(sum((stats->>'CATCH_SHOOT_FGA')::numeric),0),4) AS cs_efg,
    round(sum((stats->>'CATCH_SHOOT_FGA')::numeric),2) AS cs_fga_pg
  FROM public.pt_tracking_player WHERE pt_measure_type='CatchShoot' GROUP BY 1,2,3
),
pu AS (
  SELECT season, season_type, player_id,
    round(sum((stats->>'PULL_UP_EFG_PCT')::numeric*(stats->>'PULL_UP_FGA')::numeric)/nullif(sum((stats->>'PULL_UP_FGA')::numeric),0),4) AS pu_efg
  FROM public.pt_tracking_player WHERE pt_measure_type='PullUpShot' GROUP BY 1,2,3
)
SELECT se.season, se.season_type, se.player_id,
  se.jump_fga, se.jump_efg, se.jump_efg_exp, round(se.jump_efg - se.jump_efg_exp,4) AS shotmaking_over_exp,
  se.atb3_pct, se.c3_pct, se.three_rate,
  syn.spotup_ppp, syn.offscreen_ppp, cs.cs_efg, cs.cs_fga_pg, pu.pu_efg
FROM se
LEFT JOIN syn USING (season, season_type, player_id)
LEFT JOIN cs  USING (season, season_type, player_id)
LEFT JOIN pu  USING (season, season_type, player_id);

-- ----------------------------------------------------------------------------
-- PLAYMAKING — AST% + drive/pass tracking. (assisted-high-value dropped: no assist id)
-- ----------------------------------------------------------------------------
DROP VIEW IF EXISTS public.v_player_playmaking;
CREATE VIEW public.v_player_playmaking AS
WITH adv AS (
  SELECT season, season_type, player_id,
    (stats->>'AST_PCT')::numeric AS ast_pct, (stats->>'AST_TO')::numeric AS ast_to, (stats->>'AST_RATIO')::numeric AS ast_ratio
  FROM public.player_season_stats WHERE measure_type='Advanced' AND per_mode='PerGame'
),
pass AS (
  SELECT season, season_type, player_id,
    round(sum((stats->>'POTENTIAL_AST')::numeric*(stats->>'GP')::numeric)/nullif(sum((stats->>'GP')::numeric),0),2) AS potential_ast,
    round(sum((stats->>'AST_POINTS_CREATED')::numeric*(stats->>'GP')::numeric)/nullif(sum((stats->>'GP')::numeric),0),2) AS ast_pts_created,
    round(sum((stats->>'SECONDARY_AST')::numeric*(stats->>'GP')::numeric)/nullif(sum((stats->>'GP')::numeric),0),2) AS secondary_ast
  FROM public.pt_tracking_player WHERE pt_measure_type='Passing' GROUP BY 1,2,3
),
drv AS (
  SELECT season, season_type, player_id,
    round(sum((stats->>'DRIVE_AST')::numeric*(stats->>'GP')::numeric)/nullif(sum((stats->>'GP')::numeric),0),2) AS drive_ast
  FROM public.pt_tracking_player WHERE pt_measure_type='Drives' GROUP BY 1,2,3
)
SELECT adv.season, adv.season_type, adv.player_id, adv.ast_pct, adv.ast_to, adv.ast_ratio,
  pass.potential_ast, pass.ast_pts_created, pass.secondary_ast, drv.drive_ast
FROM adv LEFT JOIN pass USING (season, season_type, player_id) LEFT JOIN drv USING (season, season_type, player_id);

-- ----------------------------------------------------------------------------
-- DEFENDING — defensive shot context table + proxy axis view.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.player_oncourt_shot_def (
  person_id bigint NOT NULL, team_id bigint NOT NULL, season text NOT NULL, season_type text NOT NULL,
  shots_faced_on int, rim_faced_on int, rim_made_faced_on int,
  exp_efg_faced_sum_on numeric, act_efg_faced_sum_on numeric,
  PRIMARY KEY (person_id, team_id, season, season_type)
);
CREATE INDEX IF NOT EXISTS ix_posd_season ON public.player_oncourt_shot_def (season, season_type);

CREATE OR REPLACE FUNCTION public.refresh_player_oncourt_shot_def(p_season text)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  DELETE FROM public.player_oncourt_shot_def WHERE season = p_season;
  INSERT INTO public.player_oncourt_shot_def
  WITH sd AS (
    SELECT se.game_id, se.season, se.season_type, se.elapsed_sec, se.shot_zone,
      CASE WHEN se.team_id=sch.home_team_id THEN sch.away_team_id ELSE sch.home_team_id END AS def_team_id,
      (se.shot_zone='Restricted Area') AS is_rim, (se.shot_result='Made')::int AS made,
      CASE WHEN se.shot_result='Made' AND se.shot_value=3 THEN 1.5 WHEN se.shot_result='Made' THEN 1.0 ELSE 0 END AS efg_pts
    FROM public.shot_event se JOIN public.schedule sch ON sch.game_id=se.game_id WHERE se.season=p_season
  ),
  zb AS (SELECT season, season_type, shot_zone, avg(efg_pts) AS lg_zone_efg FROM sd GROUP BY 1,2,3),
  sdz AS (SELECT sd.*, zb.lg_zone_efg FROM sd JOIN zb USING (season, season_type, shot_zone))
  SELECT s.person_id, s.team_id, sdz.season, sdz.season_type,
    count(*), count(*) FILTER (WHERE sdz.is_rim), count(*) FILTER (WHERE sdz.is_rim AND sdz.made=1),
    sum(sdz.lg_zone_efg), sum(sdz.efg_pts)
  FROM sdz JOIN public.pbp_lineup_stint s ON s.game_id=sdz.game_id AND s.team_id=sdz.def_team_id
   AND s.in_elapsed_sec <= sdz.elapsed_sec AND s.out_elapsed_sec > sdz.elapsed_sec
  GROUP BY s.person_id, s.team_id, sdz.season, sdz.season_type;
  GET DIAGNOSTICS n = ROW_COUNT; RETURN n;
END $$;

SELECT public.refresh_player_oncourt_shot_def(s) FROM (VALUES ('2021-22'),('2022-23'),('2023-24'),('2024-25'),('2025-26')) v(s);

CREATE OR REPLACE VIEW public.v_player_defending AS
WITH base AS (
  SELECT season, season_type, player_id,
    (stats->>'STL')::numeric*(stats->>'GP')::numeric AS stl_tot,
    (stats->>'BLK')::numeric*(stats->>'GP')::numeric AS blk_tot
  FROM public.player_season_stats WHERE measure_type='Base' AND per_mode='PerGame'
),
poc AS (SELECT person_id AS player_id, season, season_type, sum(def_poss_on) AS def_poss FROM public.player_oncourt_poss GROUP BY 1,2,3),
onoff AS (
  SELECT DISTINCT ON (person_id, season, season_type) person_id AS player_id, season, season_type, round(drtg_off - drtg_on,1) AS drtg_swing
  FROM public.v_player_onoff_context ORDER BY person_id, season, season_type, off_poss_on DESC
),
sd AS (
  SELECT se.season, se.season_type,
    CASE WHEN se.team_id=sch.home_team_id THEN sch.away_team_id ELSE sch.home_team_id END AS team_id,
    (se.shot_zone='Restricted Area') AS is_rim, (se.shot_result='Made')::int AS made,
    CASE WHEN se.shot_result='Made' AND se.shot_value=3 THEN 1.5 WHEN se.shot_result='Made' THEN 1.0 ELSE 0 END AS efg_pts
  FROM public.shot_event se JOIN public.schedule sch ON sch.game_id=se.game_id
),
td AS (
  SELECT season, season_type, team_id, count(*) AS t_faced, count(*) FILTER (WHERE is_rim) AS t_rim_faced,
    count(*) FILTER (WHERE is_rim AND made=1) AS t_rim_made, sum(efg_pts) AS t_act_efg
  FROM sd GROUP BY 1,2,3
),
dsc AS (SELECT DISTINCT ON (person_id, season, season_type) * FROM public.player_oncourt_shot_def ORDER BY person_id, season, season_type, shots_faced_on DESC)
SELECT b.season, b.season_type, b.player_id,
  round(100.0*b.stl_tot/nullif(poc.def_poss,0),2) AS stl_per100,
  round(100.0*b.blk_tot/nullif(poc.def_poss,0),2) AS blk_per100,
  onoff.drtg_swing,
  round(dsc.rim_made_faced_on::numeric/nullif(dsc.rim_faced_on,0),4) AS opp_rim_fg_on,
  round((td.t_rim_made-dsc.rim_made_faced_on)::numeric/nullif(td.t_rim_faced-dsc.rim_faced_on,0),4) AS opp_rim_fg_off,
  round((td.t_rim_made-dsc.rim_made_faced_on)::numeric/nullif(td.t_rim_faced-dsc.rim_faced_on,0)
        - dsc.rim_made_faced_on::numeric/nullif(dsc.rim_faced_on,0),4) AS rim_protection,
  round(dsc.act_efg_faced_sum_on/nullif(dsc.shots_faced_on,0),4) AS opp_efg_on,
  round((td.t_act_efg-dsc.act_efg_faced_sum_on)/nullif(td.t_faced-dsc.shots_faced_on,0),4) AS opp_efg_off,
  round((td.t_act_efg-dsc.act_efg_faced_sum_on)/nullif(td.t_faced-dsc.shots_faced_on,0)
        - dsc.act_efg_faced_sum_on/nullif(dsc.shots_faced_on,0),4) AS efg_suppression
FROM base b
LEFT JOIN poc   ON poc.player_id=b.player_id AND poc.season=b.season AND poc.season_type=b.season_type
LEFT JOIN onoff ON onoff.player_id=b.player_id AND onoff.season=b.season AND onoff.season_type=b.season_type
LEFT JOIN dsc   ON dsc.person_id=b.player_id AND dsc.season=b.season AND dsc.season_type=b.season_type
LEFT JOIN td    ON td.team_id=dsc.team_id AND td.season=b.season AND td.season_type=b.season_type;

-- ----------------------------------------------------------------------------
-- ASSEMBLY — v_player_hexagon. 6 axes, each = mean of sub-metric percentiles
-- (0-100) vs all minutes-qualified players (>= 1000 on-court off possessions).
-- Defending weights blocks/steals 2x vs the noisier DRtg swing.
-- See the deployed view definition (create_player_hexagon migration) — reproduced
-- in the DB; the percentile machinery is ~18 percent_rank() windows + axis means.
-- ----------------------------------------------------------------------------
-- (full v_player_hexagon body lives in the applied migration; query it directly)

-- Part C (2026-06-30) — Shooting split + Rebounding contested% added to the materialized
-- player_axis_metrics via refresh_player_axis_metrics (see the deployed function / sql/hexagon_weights.sql):
--   SHOOTING:   cs_efg, pu_efg = catch-&-shoot / pull-up eFG from pt_tracking_player
--               (CatchShoot / PullUpShot), volume-floored at 1.0 FGA/g. shotmaking_over_exp now
--               floored at jump_fga>=150; spotup_ppp floored at >=50 poss (above); atb3_pct dropped.
--   REBOUNDING: contested_reb_per36 (REB_CONTEST) + reb_chance_pct (REB/REB_CHANCES) from
--               pt_tracking_player Rebounding (added to v_player_rebounding; see hexagon_and_splits.sql).
--
-- Daily refresh: refresh_show_rollups() also runs refresh_player_oncourt_shot_def(v_season).
-- All axis/hexagon views read live.
--
-- REMAINING POLISH (optional): per-position percentile pool (add position to the
-- percent_rank PARTITION) for a "vs position" hexagon alongside "vs all"; per-axis
-- weight tuning; min-sample shading in the UI.
-- ============================================================================
