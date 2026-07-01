-- ============================================================================
-- team_hexagon_axes_draft.sql  —  DRAFT / NOT YET DEPLOYED
-- ----------------------------------------------------------------------------
-- First build step for the Team Hexagon (SUPABASE_DERIVED_OBJECTS.md §8).
-- Produces raw offense + defense sub-metrics per team-season for the six
-- overlaid spokes (Rim, Perimeter, Transition, Second chance, Bonus, Rebounding).
--
-- Status: read-only exploration. Nothing here is on the nightly cron and no
--         production object is created until reviewed. When approved, this
--         becomes `v_team_axis_metrics` (materialize if the live shot_event
--         scan is too slow at backfill scale — same reason §4 materializes
--         player_axis_metrics).
--
-- Validated 2026-06-28 (2025-26 Regular Season):
--   * shot_event offense FGA/3PA tie to box (avg abs diff 1.9 / 1.7 per team-
--     season = per-game rounding only); derived 3P% matches official to 0.00.
--   * defender mapping conserves shots: sum(off shots) = sum(def shots) = 219,159.
--   * OREB%/DREB% pulled directly from official Advanced.
--   * transition / second-chance / bonus inherit the validated possession engine.
--
-- Conventions reused:
--   * rim = shot_zone 'Restricted Area'; 3 = shot_value 3.
--   * defender for a shot = the other team in that game, via possession pairs.
--   * defense metrics are RAW here (not yet inverted); inversion + 0-100
--     percentiling happens downstream in v_team_axis_pctile so outward = good.
-- ============================================================================

CREATE OR REPLACE VIEW v_team_axis_metrics AS
WITH go AS (   -- per-game team -> opponent (defender) map, from the possession engine
  SELECT DISTINCT season, season_type, game_id,
         off_team_id AS team_id, def_team_id AS opp
  FROM possession
),
shots AS (     -- every FG attempt tagged with both its shooting team and its defender
  SELECT s.season, s.season_type, s.team_id AS off_team_id, g.opp AS def_team_id,
         s.shot_zone, s.shot_value, s.shot_result
  FROM shot_event s
  JOIN go g
    ON g.game_id = s.game_id AND g.team_id = s.team_id
   AND g.season = s.season   AND g.season_type = s.season_type
),
off_shots AS (
  SELECT season, season_type, off_team_id AS team_id,
    count(*)                                                                 AS fga,
    count(*) FILTER (WHERE shot_zone='Restricted Area')                      AS rim_fga,
    count(*) FILTER (WHERE shot_zone='Restricted Area' AND shot_result='Made') AS rim_fgm,
    count(*) FILTER (WHERE shot_value=3)                                     AS fg3a,
    count(*) FILTER (WHERE shot_value=3 AND shot_result='Made')             AS fg3m
  FROM shots GROUP BY season, season_type, off_team_id
),
def_shots AS (
  SELECT season, season_type, def_team_id AS team_id,
    count(*)                                                                 AS fga,
    count(*) FILTER (WHERE shot_zone='Restricted Area')                      AS rim_fga,
    count(*) FILTER (WHERE shot_zone='Restricted Area' AND shot_result='Made') AS rim_fgm,
    count(*) FILTER (WHERE shot_value=3)                                     AS fg3a,
    count(*) FILTER (WHERE shot_value=3 AND shot_result='Made')             AS fg3m
  FROM shots GROUP BY season, season_type, def_team_id
),
adv AS (       -- official Advanced: rebounding spokes + validation ratings
  SELECT season, season_type, team_id, team_name,
    (stats->>'OREB_PCT')::numeric   AS oreb_pct,
    (stats->>'DREB_PCT')::numeric   AS dreb_pct,
    (stats->>'OFF_RATING')::numeric AS off_rtg,
    (stats->>'DEF_RATING')::numeric AS def_rtg
  FROM team_season_stats
  WHERE measure_type='Advanced'
)
SELECT
  a.season, a.season_type, a.team_id, a.team_name,
  -- ---- OFFENSE (solid shape) ----
  round(100.0 * o.rim_fga / NULLIF(o.fga,0), 1)            AS o_rim_freq,
  round(100.0 * o.rim_fgm / NULLIF(o.rim_fga,0), 1)        AS o_rim_pct,
  round(100.0 * o.fg3a   / NULLIF(o.fga,0), 1)             AS o_3_freq,
  round(100.0 * o.fg3m   / NULLIF(o.fg3a,0), 1)            AS o_3pct,
  tr.transition_ppp                                        AS o_trans_ppp,
  tr.transition_rate                                       AS o_trans_rate,
  ch.second_chance_ppp                                     AS o_2nd_ppp,
  ch.second_chance_rate                                    AS o_2nd_rate,
  bo.bonus_poss_rate                                       AS o_bonus_rate,
  bo.ortg_bonus                                            AS o_bonus_ortg,
  a.oreb_pct                                               AS o_oreb_pct,
  -- ---- DEFENSE / ALLOWED (dashed shape; raw, not yet inverted) ----
  round(100.0 * d.rim_fga / NULLIF(d.fga,0), 1)           AS d_rim_freq,
  round(100.0 * d.rim_fgm / NULLIF(d.rim_fga,0), 1)       AS d_rim_pct,
  round(100.0 * d.fg3a   / NULLIF(d.fga,0), 1)            AS d_3_freq,
  round(100.0 * d.fg3m   / NULLIF(d.fg3a,0), 1)           AS d_3pct,
  trd.transition_ppp_allowed                              AS d_trans_ppp,
  trd.transition_rate_allowed                             AS d_trans_rate,
  chd.second_chance_ppp_allowed                           AS d_2nd_ppp,
  chd.second_chance_rate_allowed                          AS d_2nd_rate,
  bod.bonus_poss_rate_allowed                             AS d_bonus_rate,
  bod.drtg_bonus                                          AS d_bonus_drtg,
  a.dreb_pct                                              AS d_dreb_pct,
  -- ---- validation handles (not spokes) ----
  a.off_rtg, a.def_rtg
FROM adv a
JOIN off_shots o  USING (season, season_type, team_id)
JOIN def_shots d  USING (season, season_type, team_id)
JOIN v_team_transition_splits      tr  USING (season, season_type, team_id)
JOIN v_team_transition_splits_def  trd USING (season, season_type, team_id)
JOIN v_team_chance_splits          ch  USING (season, season_type, team_id)
JOIN v_team_chance_splits_def      chd USING (season, season_type, team_id)
JOIN v_team_bonus_splits           bo  USING (season, season_type, team_id)
JOIN v_team_bonus_splits_def       bod USING (season, season_type, team_id);

-- ============================================================================
-- VALIDATION (run ad hoc; do not deploy). Confirms shot_event ties to the box
-- and the defender mapping conserves shots, for a given season.
-- ============================================================================
-- WITH go AS (SELECT DISTINCT game_id, off_team_id team_id, def_team_id opp FROM possession
--             WHERE season='2025-26' AND season_type='Regular Season'),
-- se_off AS (SELECT team_id, count(*) fga, count(*) FILTER (WHERE shot_value=3) fg3a,
--                   count(*) FILTER (WHERE shot_value=3 AND shot_result='Made') fg3m
--            FROM shot_event WHERE season='2025-26' AND season_type='Regular Season' GROUP BY team_id),
-- se_def AS (SELECT g.opp team_id, count(*) fga FROM shot_event s
--            JOIN go g ON g.game_id=s.game_id AND g.team_id=s.team_id
--            WHERE s.season='2025-26' AND s.season_type='Regular Season' GROUP BY g.opp),
-- box AS (SELECT team_id, gp, (stats->>'FGA')::numeric*gp box_fga,
--                (stats->>'FG3A')::numeric*gp box_fg3a, (stats->>'FG3_PCT')::numeric*100 box_fg3pct
--         FROM team_season_stats WHERE season='2025-26' AND season_type='Regular Season' AND measure_type='Base')
-- SELECT round(avg(abs(o.fga-b.box_fga)),1) avg_abs_fga_diff,
--        round(avg(abs(o.fg3a-b.box_fg3a)),1) avg_abs_fg3a_diff,
--        round(avg(abs(round(100.0*o.fg3m/NULLIF(o.fg3a,0),1)-b.box_fg3pct)),2) avg_abs_fg3pct_diff,
--        (SELECT sum(fga) FROM se_off) total_off, (SELECT sum(fga) FROM se_def) total_def
-- FROM se_off o JOIN box b USING (team_id);

-- ============================================================================
-- Part C (2026-06-30) — DEPLOYED additions (migration partc_team_hexagon_upgrades).
-- Same Defending/Shooting/Rebounding upgrades as the player hexagon + shot-quality-created.
-- v_team_axis_metrics gains 7 columns (append-only); v_team_axis_long gains 7 unpivot rows
-- + a higher_is_good whitelist for the def "stop" metrics; v_team_axis_pctile / v_team_hexagon
-- are generic over the long view and need NO change. New team_axis_weights rows below.
--
--   -- extra CTEs joined LEFT into v_team_axis_metrics (one row per team-season; PerGame):
--   cst       AS (pt_tracking_team CatchShoot → CATCH_SHOOT_EFG_PCT)            -- o_cs_efg
--   put       AS (pt_tracking_team PullUpShot → PULL_UP_EFG_PCT)               -- o_pu_efg
--   rbt       AS (pt_tracking_team Rebounding → OREB_CONTEST_PCT/DREB_CONTEST_PCT) -- o_oreb_contest / d_dreb_contest
--   sqt       AS (pt_shot_defender_team → Σ FGA_FREQUENCY for 4-6ft + 6+ft)    -- o_open_rate (shot quality CREATED)
--   dft_rim   AS (pt_defend_team 'Less Than 6Ft'   → NS_LT_06_PCT - LT_06_PCT) -- d_rim_stop  (higher=better)
--   dft_three AS (pt_defend_team 'Greater Than 15Ft' → NS_GT_15_PCT - GT_15_PCT) -- d_three_stop (higher=better)
--
--   -- appended columns: o_cs_efg, o_pu_efg, o_open_rate, o_oreb_contest,
--   --                    d_dreb_contest, d_rim_stop, d_three_stop
--
--   -- v_team_axis_long new VALUES rows:
--   ('perimeter','off','cs_efg',m.o_cs_efg), ('perimeter','off','pu_efg',m.o_pu_efg),
--   ('perimeter','off','open_rate',m.o_open_rate), ('rebounding','off','contest_pct',m.o_oreb_contest),
--   ('rebounding','def','contest_pct',m.d_dreb_contest), ('rim','def','rim_stop',m.d_rim_stop),
--   ('perimeter','def','three_stop',m.d_three_stop)
--   -- higher_is_good CASE prepends:  WHEN sub_metric IN ('rim_stop','three_stop') THEN true
--
--   INSERT INTO public.team_axis_weights (axis, sub_metric, weight) VALUES
--     ('perimeter','cs_efg',1), ('perimeter','pu_efg',1), ('perimeter','open_rate',1),
--     ('perimeter','three_stop',1), ('rim','rim_stop',1.5), ('rebounding','contest_pct',1);
--
-- SHOT QUALITY — "created" only. pt_shot_defender_team is the team's OWN shots (reconciles to box
-- FGA to 0.1), so there is NO team-grain "allowed" feed; the allowed side would need game-level
-- closest-defender data that is not ingested. Surfaced, not faked.
--
-- Validated 2026-06-30 (2025-26... checked on 2024-25 RS): 30 teams, all 7 cols populated;
-- rim_stop NOT inverted (BOS 100 / OKC 96.6 pctile); top def_mean = BOS/OKC/CLE; o_cs_efg leaders
-- MIL/PHX/LAC/OKC/BOS; o_open_rate top OKC 61.6.
-- ============================================================================
