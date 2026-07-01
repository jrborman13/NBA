-- ============================================================================
-- hexagon_and_splits.sql  —  DEPLOYED to "NBA App" (qhrgekcowkgwcaaqyqvv)
-- ----------------------------------------------------------------------------
-- Builds on possession_engine.sql. Adds:
--   1. Defensive split views (what each team ALLOWS)
--   2. player_oncourt_poss      — player on/off POSSESSION context (table + fn)
--   3. player_oncourt_shot      — player on/off SHOT context (table + fn)
--   4. v_player_onoff_context / v_player_shot_onoff_context
--   5. v_player_finishing / v_player_rebounding / v_player_gravity  (hexagon axes)
--
-- LINEUP ATTRIBUTION (validated)
--   pbp_lineup_stint.in/out_elapsed_sec are GAME-cumulative seconds (NOT
--   within-period as the data catalog states) — same scale as possession and
--   shot_event elapsed_sec. "On floor" = the player's own stint covers the event
--   time (possession midpoint / shot time). Internal checks: sum(off_poss_on) and
--   sum(shots_on) over a team's players = EXACTLY 5.000 x team possessions / FGA.
--   Validation signal: shot-diet gravity leaderboard tops out at Jokic, Towns,
--   Wembanyama, LeBron, Cam Johnson — the expected offensive hubs/spacers.
--   NOTE: existing mv_player_onoff appears to have poss_on/poss_off swapped
--   (bench > starters); this build does not rely on it.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. Defensive team splits (group by def_team_id) = what a team ALLOWS.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_team_bonus_splits_def AS
SELECT season, season_type, def_team_id AS team_id,
  count(*) AS possessions_faced,
  count(*) FILTER (WHERE opp_in_bonus)     AS poss_bonus,
  count(*) FILTER (WHERE NOT opp_in_bonus) AS poss_nonbonus,
  round(avg((opp_in_bonus)::int), 4)       AS bonus_poss_rate_allowed,
  round(100.0*sum(points) FILTER (WHERE opp_in_bonus)     / nullif(count(*) FILTER (WHERE opp_in_bonus),0), 1)     AS drtg_bonus,
  round(100.0*sum(points) FILTER (WHERE NOT opp_in_bonus) / nullif(count(*) FILTER (WHERE NOT opp_in_bonus),0), 1) AS drtg_nonbonus
FROM public.possession GROUP BY season, season_type, def_team_id;

CREATE OR REPLACE VIEW public.v_team_chance_splits_def AS
SELECT season, season_type, def_team_id AS team_id,
  count(*) AS possessions_faced,
  count(*) FILTER (WHERE had_oreb)   AS second_chance_poss_allowed,
  round(avg((had_oreb)::int), 4)     AS second_chance_rate_allowed,
  sum(second_chance_pts)             AS second_chance_pts_allowed,
  round(sum(second_chance_pts)::numeric / nullif(count(*) FILTER (WHERE had_oreb),0), 3) AS second_chance_ppp_allowed,
  round(sum(second_chance_pts)::numeric / nullif(count(DISTINCT game_id),0), 2)          AS second_chance_pts_allowed_per_game
FROM public.possession GROUP BY season, season_type, def_team_id;

CREATE OR REPLACE VIEW public.v_team_transition_splits_def AS
SELECT season, season_type, def_team_id AS team_id,
  count(*) AS possessions_faced,
  count(*) FILTER (WHERE is_transition)     AS poss_transition_allowed,
  count(*) FILTER (WHERE NOT is_transition) AS poss_halfcourt_allowed,
  round(avg((is_transition)::int), 4)       AS transition_rate_allowed,
  round(avg(points) FILTER (WHERE is_transition), 3)     AS transition_ppp_allowed,
  round(avg(points) FILTER (WHERE NOT is_transition), 3) AS halfcourt_ppp_allowed
FROM public.possession GROUP BY season, season_type, def_team_id;

-- ----------------------------------------------------------------------------
-- 2. player_oncourt_poss — on-court possession aggregates per (player, team, season).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.player_oncourt_poss (
  person_id bigint NOT NULL, team_id bigint NOT NULL, season text NOT NULL, season_type text NOT NULL,
  off_poss_on int, off_pts_on int, off_sc_on int, off_trans_on int, off_bonus_on int,
  def_poss_on int, def_pts_on int, def_sc_on int, def_trans_on int,
  PRIMARY KEY (person_id, team_id, season, season_type)
);
CREATE INDEX IF NOT EXISTS ix_poc_season ON public.player_oncourt_poss (season, season_type);

CREATE OR REPLACE FUNCTION public.refresh_player_oncourt_poss(p_season text)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  DELETE FROM public.player_oncourt_poss WHERE season = p_season;
  INSERT INTO public.player_oncourt_poss
  WITH off_ctx AS (
    SELECT s.person_id, s.team_id, p.season, p.season_type,
      count(*) off_poss_on, sum(p.points) off_pts_on,
      count(*) FILTER (WHERE p.had_oreb) off_sc_on,
      count(*) FILTER (WHERE p.is_transition) off_trans_on,
      count(*) FILTER (WHERE p.opp_in_bonus) off_bonus_on
    FROM public.possession p
    JOIN public.pbp_lineup_stint s ON s.game_id=p.game_id AND s.team_id=p.off_team_id
     AND s.in_elapsed_sec <= (p.start_elapsed_sec+p.end_elapsed_sec)/2.0
     AND s.out_elapsed_sec >  (p.start_elapsed_sec+p.end_elapsed_sec)/2.0
    WHERE p.season=p_season GROUP BY 1,2,3,4
  ),
  def_ctx AS (
    SELECT s.person_id, s.team_id, p.season, p.season_type,
      count(*) def_poss_on, sum(p.points) def_pts_on,
      count(*) FILTER (WHERE p.had_oreb) def_sc_on,
      count(*) FILTER (WHERE p.is_transition) def_trans_on
    FROM public.possession p
    JOIN public.pbp_lineup_stint s ON s.game_id=p.game_id AND s.team_id=p.def_team_id
     AND s.in_elapsed_sec <= (p.start_elapsed_sec+p.end_elapsed_sec)/2.0
     AND s.out_elapsed_sec >  (p.start_elapsed_sec+p.end_elapsed_sec)/2.0
    WHERE p.season=p_season GROUP BY 1,2,3,4
  )
  SELECT coalesce(o.person_id,d.person_id), coalesce(o.team_id,d.team_id),
         coalesce(o.season,d.season), coalesce(o.season_type,d.season_type),
         o.off_poss_on,o.off_pts_on,o.off_sc_on,o.off_trans_on,o.off_bonus_on,
         d.def_poss_on,d.def_pts_on,d.def_sc_on,d.def_trans_on
  FROM off_ctx o FULL JOIN def_ctx d USING (person_id, team_id, season, season_type);
  GET DIAGNOSTICS n = ROW_COUNT; RETURN n;
END $$;

-- ----------------------------------------------------------------------------
-- 3. player_oncourt_shot — team shot context while each player is on floor.
--    eFG points: made 3 = 1.5, made 2 = 1.0, miss = 0. Expected eFG per shot =
--    league average eFG for that shot_zone (shot-diet difficulty).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.player_oncourt_shot (
  person_id bigint NOT NULL, team_id bigint NOT NULL, season text NOT NULL, season_type text NOT NULL,
  shots_on int, rim_on int, exp_efg_sum_on numeric, act_efg_sum_on numeric,
  PRIMARY KEY (person_id, team_id, season, season_type)
);
CREATE INDEX IF NOT EXISTS ix_pos_season ON public.player_oncourt_shot (season, season_type);

CREATE OR REPLACE FUNCTION public.refresh_player_oncourt_shot(p_season text)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  DELETE FROM public.player_oncourt_shot WHERE season = p_season;
  INSERT INTO public.player_oncourt_shot
  WITH sh AS (
    SELECT se.game_id, se.season, se.season_type, se.team_id, se.elapsed_sec, se.shot_zone,
      (se.shot_zone='Restricted Area') AS is_rim,
      CASE WHEN se.shot_result='Made' AND se.shot_value=3 THEN 1.5
           WHEN se.shot_result='Made' THEN 1.0 ELSE 0 END AS efg_pts
    FROM public.shot_event se WHERE se.season = p_season
  ),
  zb AS (SELECT season, season_type, shot_zone, avg(efg_pts) AS lg_zone_efg FROM sh GROUP BY 1,2,3),
  shz AS (SELECT sh.*, zb.lg_zone_efg FROM sh JOIN zb USING (season, season_type, shot_zone))
  SELECT s.person_id, s.team_id, shz.season, shz.season_type,
    count(*) shots_on, count(*) FILTER (WHERE shz.is_rim) rim_on,
    sum(shz.lg_zone_efg) exp_efg_sum_on, sum(shz.efg_pts) act_efg_sum_on
  FROM shz
  JOIN public.pbp_lineup_stint s ON s.game_id=shz.game_id AND s.team_id=shz.team_id
   AND s.in_elapsed_sec <= shz.elapsed_sec AND s.out_elapsed_sec > shz.elapsed_sec
  GROUP BY s.person_id, s.team_id, shz.season, shz.season_type;
  GET DIAGNOSTICS n = ROW_COUNT; RETURN n;
END $$;

-- Initial population (all five seasons; each call fits under the statement timeout).
SELECT public.refresh_player_oncourt_poss(s) FROM (VALUES ('2021-22'),('2022-23'),('2023-24'),('2024-25'),('2025-26')) v(s);
SELECT public.refresh_player_oncourt_shot(s) FROM (VALUES ('2021-22'),('2022-23'),('2023-24'),('2024-25'),('2025-26')) v(s);

-- ----------------------------------------------------------------------------
-- 4. On/off context views ("off" = team total minus the player's on-court share).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_player_onoff_context AS
WITH tt AS (
  SELECT season, season_type, off_team_id AS team_id,
    count(*) t_off_poss, sum(points) t_off_pts,
    count(*) FILTER (WHERE had_oreb) t_sc, count(*) FILTER (WHERE is_transition) t_tr
  FROM public.possession GROUP BY 1,2,3
),
td AS (
  SELECT season, season_type, def_team_id AS team_id,
    count(*) t_def_poss, sum(points) t_def_pts, count(*) FILTER (WHERE had_oreb) t_dsc
  FROM public.possession GROUP BY 1,2,3
)
SELECT c.person_id, c.team_id, c.season, c.season_type,
  c.off_poss_on, (tt.t_off_poss - c.off_poss_on) AS off_poss_off,
  round(100.0*c.off_pts_on/nullif(c.off_poss_on,0),1)                              AS ortg_on,
  round(100.0*(tt.t_off_pts-c.off_pts_on)/nullif(tt.t_off_poss-c.off_poss_on,0),1) AS ortg_off,
  round(100.0*c.def_pts_on/nullif(c.def_poss_on,0),1)                              AS drtg_on,
  round(100.0*(td.t_def_pts-c.def_pts_on)/nullif(td.t_def_poss-c.def_poss_on,0),1) AS drtg_off,
  round(100.0*c.off_pts_on/nullif(c.off_poss_on,0) - 100.0*c.def_pts_on/nullif(c.def_poss_on,0),1) AS net_on,
  round(100.0*(tt.t_off_pts-c.off_pts_on)/nullif(tt.t_off_poss-c.off_poss_on,0)
      - 100.0*(td.t_def_pts-c.def_pts_on)/nullif(td.t_def_poss-c.def_poss_on,0),1)                  AS net_off,
  round(c.off_sc_on::numeric/nullif(c.off_poss_on,0),4)                            AS sc_rate_on,
  round((tt.t_sc-c.off_sc_on)::numeric/nullif(tt.t_off_poss-c.off_poss_on,0),4)    AS sc_rate_off,
  round(c.off_trans_on::numeric/nullif(c.off_poss_on,0),4)                         AS trans_rate_on,
  round((tt.t_tr-c.off_trans_on)::numeric/nullif(tt.t_off_poss-c.off_poss_on,0),4) AS trans_rate_off,
  round(c.def_sc_on::numeric/nullif(c.def_poss_on,0),4)                            AS sc_rate_allowed_on,
  round((td.t_dsc-c.def_sc_on)::numeric/nullif(td.t_def_poss-c.def_poss_on,0),4)   AS sc_rate_allowed_off
FROM public.player_oncourt_poss c
JOIN tt USING (season, season_type, team_id)
JOIN td USING (season, season_type, team_id);

CREATE OR REPLACE VIEW public.v_player_shot_onoff_context AS
WITH zb AS (
  SELECT season, season_type, shot_zone,
    avg(CASE WHEN shot_result='Made' AND shot_value=3 THEN 1.5
             WHEN shot_result='Made' THEN 1.0 ELSE 0 END) AS lg_zone_efg
  FROM public.shot_event GROUP BY 1,2,3
),
tt AS (
  SELECT se.season, se.season_type, se.team_id,
    count(*) AS t_shots,
    count(*) FILTER (WHERE se.shot_zone='Restricted Area') AS t_rim,
    sum(zb.lg_zone_efg) AS t_exp_efg,
    sum(CASE WHEN se.shot_result='Made' AND se.shot_value=3 THEN 1.5
             WHEN se.shot_result='Made' THEN 1.0 ELSE 0 END) AS t_act_efg
  FROM public.shot_event se JOIN zb USING (season, season_type, shot_zone)
  GROUP BY 1,2,3
)
SELECT c.person_id, c.team_id, c.season, c.season_type,
  c.shots_on, (tt.t_shots - c.shots_on) AS shots_off,
  round(c.rim_on::numeric/nullif(c.shots_on,0),4)                            AS rim_freq_on,
  round((tt.t_rim - c.rim_on)::numeric/nullif(tt.t_shots-c.shots_on,0),4)    AS rim_freq_off,
  round(c.exp_efg_sum_on/nullif(c.shots_on,0),4)                             AS exp_efg_on,
  round((tt.t_exp_efg - c.exp_efg_sum_on)/nullif(tt.t_shots-c.shots_on,0),4) AS exp_efg_off,
  round(c.act_efg_sum_on/nullif(c.shots_on,0),4)                             AS act_efg_on,
  round((tt.t_act_efg - c.act_efg_sum_on)/nullif(tt.t_shots-c.shots_on,0),4) AS act_efg_off
FROM public.player_oncourt_shot c
JOIN tt USING (season, season_type, team_id);

-- ----------------------------------------------------------------------------
-- 5. Hexagon axis metric views (raw metrics; percentile-normalize at assembly).
-- ----------------------------------------------------------------------------
-- FINISHING — individual rim volume/efficiency + team rim frequency on/off.
CREATE OR REPLACE VIEW public.v_player_finishing AS
WITH lg AS (
  SELECT season, season_type,
    avg((shot_result='Made')::int) FILTER (WHERE shot_zone='Restricted Area') AS lg_rim_pct
  FROM public.shot_event GROUP BY 1,2
),
soc AS (
  SELECT DISTINCT ON (person_id, season, season_type) *
  FROM public.v_player_shot_onoff_context
  ORDER BY person_id, season, season_type, shots_on DESC
),
ind AS (
  SELECT se.season, se.season_type, se.shooter_id AS player_id,
    count(*) AS fga, count(*) FILTER (WHERE shot_zone='Restricted Area') AS rim_fga,
    round(avg((shot_zone='Restricted Area')::int),4) AS rim_rate,
    round(avg((shot_result='Made')::int) FILTER (WHERE shot_zone='Restricted Area'),4) AS rim_fg_pct,
    round(avg((shot_result='Made')::int) FILTER (WHERE shot_zone='Restricted Area') - max(lg.lg_rim_pct),4) AS rim_fg_pct_over_league
  FROM public.shot_event se JOIN lg USING (season, season_type)
  GROUP BY se.season, se.season_type, se.shooter_id
)
SELECT ind.*,
  soc.rim_freq_on AS team_rim_freq_on, soc.rim_freq_off AS team_rim_freq_off,
  round(soc.rim_freq_on - soc.rim_freq_off, 4) AS team_rim_freq_lift
FROM ind
LEFT JOIN soc ON soc.person_id=ind.player_id AND soc.season=ind.season AND soc.season_type=ind.season_type;

-- REBOUNDING — season OREB%/DREB% + second-chance possession rate on/off.
CREATE OR REPLACE VIEW public.v_player_rebounding AS
WITH oc AS (
  SELECT DISTINCT ON (person_id, season, season_type) *
  FROM public.v_player_onoff_context
  ORDER BY person_id, season, season_type, off_poss_on DESC
),
-- Part C: contested% / chance-conversion from SportVU rebounding tracking (GP-weighted across stints).
rb AS (
  SELECT season, season_type, player_id,
    sum((stats->>'REB_CONTEST')::numeric*(stats->>'GP')::numeric) AS reb_contest_tot,
    sum((stats->>'MIN')::numeric*(stats->>'GP')::numeric)         AS min_tot,
    sum((stats->>'REB')::numeric*(stats->>'GP')::numeric)         AS reb_tot,
    sum((stats->>'REB_CHANCES')::numeric*(stats->>'GP')::numeric) AS chance_tot
  FROM public.pt_tracking_player WHERE pt_measure_type='Rebounding' GROUP BY 1,2,3
)
SELECT pss.season, pss.season_type, pss.player_id,
  (pss.stats->>'OREB_PCT')::numeric AS oreb_pct,
  (pss.stats->>'DREB_PCT')::numeric AS dreb_pct,
  oc.sc_rate_on, oc.sc_rate_off, round(oc.sc_rate_on - oc.sc_rate_off, 4) AS sc_rate_on_minus_off,
  oc.sc_rate_allowed_on, oc.sc_rate_allowed_off,
  round(oc.sc_rate_allowed_off - oc.sc_rate_allowed_on, 4) AS sc_allowed_suppression,
  round(rb.reb_contest_tot/nullif(rb.min_tot,0)*36, 2) AS contested_reb_per36,
  round(rb.reb_tot/nullif(rb.chance_tot,0), 4)          AS reb_chance_pct
FROM public.player_season_stats pss
LEFT JOIN oc ON oc.person_id=pss.player_id AND oc.season=pss.season AND oc.season_type=pss.season_type
LEFT JOIN rb ON rb.player_id=pss.player_id AND rb.season=pss.season AND rb.season_type=pss.season_type
WHERE pss.measure_type='Advanced' AND pss.per_mode='PerGame';

-- GRAVITY — shot-diet (expected-eFG) gravity + rim-freq lift + on/off rating lift.
CREATE OR REPLACE VIEW public.v_player_gravity AS
WITH oc AS (
  SELECT DISTINCT ON (person_id, season, season_type) *
  FROM public.v_player_onoff_context
  ORDER BY person_id, season, season_type, off_poss_on DESC
),
soc AS (
  SELECT DISTINCT ON (person_id, season, season_type) *
  FROM public.v_player_shot_onoff_context
  ORDER BY person_id, season, season_type, shots_on DESC
)
SELECT oc.season, oc.season_type, oc.person_id AS player_id, oc.team_id, oc.off_poss_on,
  oc.ortg_on, oc.ortg_off, round(oc.ortg_on - oc.ortg_off, 1) AS off_rating_lift,
  oc.net_on, oc.net_off, round(oc.net_on - oc.net_off, 1)      AS net_lift,
  soc.exp_efg_on, soc.exp_efg_off, round(soc.exp_efg_on - soc.exp_efg_off, 4) AS shot_diet_gravity_efg,
  soc.rim_freq_on, soc.rim_freq_off, round(soc.rim_freq_on - soc.rim_freq_off, 4) AS rim_freq_lift
FROM oc
LEFT JOIN soc ON soc.person_id=oc.person_id AND soc.team_id=oc.team_id
             AND soc.season=oc.season AND soc.season_type=oc.season_type;

-- ----------------------------------------------------------------------------
-- Daily refresh: refresh_show_rollups() also runs (after the matviews):
--   PERFORM public.refresh_possessions(v_season);
--   PERFORM public.refresh_player_oncourt_poss(v_season);
--   PERFORM public.refresh_player_oncourt_shot(v_season);
-- All views above read live, so they need no separate refresh.
--
-- REMAINING for the full 6-axis hexagon: Shooting, Playmaking, Defending axes
-- (Defending is proxy-only — no tracking-defense feed; see the design doc), then
-- the percentile-normalization + radar assembly layer.
-- ============================================================================
