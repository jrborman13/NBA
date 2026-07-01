-- ============================================================================
-- possession_engine.sql  —  DEPLOYED to "NBA App" (qhrgekcowkgwcaaqyqvv)
-- ----------------------------------------------------------------------------
-- Builds public.possession: one row per offensive possession, derived from
-- play_by_play. Companion design doc: SUPABASE_POSSESSION_AND_HEXAGON.md (Part A).
-- Validation queries: possession_engine_validation.sql.
--
-- IMPLEMENTATION NOTE — table, not matview.
--   A single CREATE MATERIALIZED VIEW over 5 seasons exceeds the statement
--   timeout (the per-event window-function walk is heavy). So this is a real
--   TABLE populated season-by-season by refresh_possessions(season): each call
--   fits comfortably, and it gives cheap incremental refresh (current season
--   only) instead of a full 5-season rebuild every night.
--
-- POSSESSION DEFINITION
--   Control until score / turnover / opponent gains the ball. OFFENSIVE REBOUNDS
--   EXTEND the possession. TEAM offensive rebounds (team_id=0, ball retained)
--   ALSO extend it and flag second-chance (had_oreb). n_player_oreb stays
--   player-only so it reconciles to the box score.
--
-- VALIDATION (2025-26 RS, live table)
--   • Possessions: 99.60 / team / game vs official POSS 100.74  (~1.1%)
--   • Player OREB: 27,939 vs box 27,989  (99.8%)
--   • Transition rate: 0.192 vs Synergy 0.185
--   • Bonus state: when flagged in-bonus, FTs follow 99.4% of the time
--   • PPP splits sane & stable across all 5 seasons (bonus>nonbonus,
--     transition>halfcourt, second-chance rate ~14%)
--
-- ENCODINGS CONFIRMED FROM LIVE DATA
--   • Missed FT -> 'MISS' in description, NULL score. score_* ~26% populated.
--   • team rebounds / team TOs have team_id=0; team named in description.
--   • penalty-counting fouls: Shooting, Personal, Loose Ball, Personal Take,
--     Away From Play, Transition Take, Clear Path, Flagrant Type 1/2.
-- ============================================================================

DROP MATERIALIZED VIEW IF EXISTS public.mv_possession;

CREATE TABLE IF NOT EXISTS public.possession (
  game_id            text    NOT NULL,
  poss_idx           int     NOT NULL,   -- sequential within game
  season             text    NOT NULL,
  season_type        text    NOT NULL,
  period             int,
  off_team_id        bigint,
  def_team_id        bigint,
  start_elapsed_sec  numeric,            -- game-elapsed seconds (0=tip)
  end_elapsed_sec    numeric,
  duration_sec       numeric,
  points             int,                -- offense points this possession (excl. technical FTs)
  first_chance_pts   int,                -- points before the first offensive rebound
  second_chance_pts  int,                -- points at/after the first offensive rebound
  had_oreb           boolean,            -- possession contained an offensive rebound (player OR team)
  n_player_oreb      int,                -- player offensive rebounds only (ties to box)
  end_reason         text,               -- made_fg | ft | turnover | dreb
  start_reason       text,               -- period | made_basket | dreb | turnover
  is_transition      boolean,            -- off a live DREB/TO, first action within 7s
  opp_in_bonus       boolean,            -- defense had entered the penalty this period
  PRIMARY KEY (game_id, poss_idx)
);

CREATE INDEX IF NOT EXISTS ix_possession_off ON public.possession (season, season_type, off_team_id);
CREATE INDEX IF NOT EXISTS ix_possession_def ON public.possession (season, season_type, def_team_id);

-- ----------------------------------------------------------------------------
-- refresh_possessions(season): idempotent DELETE + INSERT for one season.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.refresh_possessions(p_season text)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  DELETE FROM public.possession WHERE season = p_season;

  INSERT INTO public.possession (
    game_id, poss_idx, season, season_type, period, off_team_id, def_team_id,
    start_elapsed_sec, end_elapsed_sec, duration_sec, points, first_chance_pts,
    second_chance_pts, had_oreb, n_player_oreb, end_reason, start_reason,
    is_transition, opp_in_bonus
  )
  WITH base AS (
    SELECT p.game_id, p.season, p.season_type, p.event_idx, p.period, p.clock,
           p.action_type, p.sub_type, p.description, p.shot_value,
           p.team_id AS raw_team, p.score_home, p.score_away,
           s.home_team_id, s.away_team_id, th.nickname AS hn, ta.nickname AS an
    FROM public.play_by_play p
    JOIN public.schedule s ON s.game_id = p.game_id
    JOIN public.teams th   ON th.team_id = s.home_team_id
    JOIN public.teams ta   ON ta.team_id = s.away_team_id
    WHERE p.season = p_season
      AND p.season_type IN ('Regular Season','Playoffs','Play In')
  ),
  ev AS (
    SELECT *,
      CASE WHEN raw_team IS NOT NULL AND raw_team <> 0 THEN raw_team
           WHEN description ILIKE '%'||hn||'%' THEN home_team_id
           WHEN description ILIKE '%'||an||'%' THEN away_team_id END AS team_id,
      ( (regexp_match(clock,'PT(\d+)M([\d.]+)S'))[1]::int * 60
      + (regexp_match(clock,'PT(\d+)M([\d.]+)S'))[2]::numeric ) AS clock_sec,
      (action_type='Missed Shot'
         OR (action_type='Free Throw' AND description ILIKE 'MISS%')) AS is_miss
    FROM base
  ),
  el AS (
    SELECT *,
      CASE WHEN period <= 4 THEN (period-1)*720 + (720 - clock_sec)
           ELSE 2880 + (period-5)*300 + (300 - clock_sec) END AS elapsed_sec
    FROM ev
  ),
  mg AS (SELECT *, count(*) FILTER (WHERE is_miss) OVER (PARTITION BY game_id ORDER BY event_idx) AS miss_grp FROM el),
  mt AS (SELECT *, first_value(team_id) OVER (PARTITION BY game_id, miss_grp ORDER BY event_idx) AS last_miss_team FROM mg),
  flags AS (
    SELECT *,
      (action_type='Rebound' AND team_id IS NOT NULL AND team_id = last_miss_team) AS is_oreb_any,
      (action_type='Rebound' AND raw_team IS NOT NULL AND raw_team <> 0 AND raw_team = last_miss_team) AS is_player_oreb,
      CASE WHEN action_type='Made Shot' THEN 1 WHEN action_type='Turnover' THEN 1
           WHEN action_type='Rebound' AND team_id IS NOT NULL AND team_id <> last_miss_team THEN 1
           WHEN action_type='Free Throw' AND sub_type IN ('Free Throw 2 of 2','Free Throw 3 of 3') AND description NOT ILIKE 'MISS%' THEN 1
           ELSE 0 END AS ends_poss,
      CASE WHEN action_type='Rebound' AND team_id <> last_miss_team THEN last_miss_team ELSE team_id END AS off_team,
      CASE WHEN action_type='Made Shot' THEN shot_value
           WHEN action_type='Free Throw' AND description NOT ILIKE 'MISS%' AND sub_type NOT ILIKE '%Technical%' THEN 1
           ELSE 0 END AS pts_event,
      (action_type='Foul' AND sub_type IN ('Shooting','Personal','Loose Ball','Personal Take','Away From Play','Transition Take','Clear Path','Flagrant Type 1','Flagrant Type 2')) AS is_pen_foul
    FROM mt
  ),
  assign AS (SELECT *, coalesce(sum(ends_poss) OVER (PARTITION BY game_id ORDER BY event_idx ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS poss_raw FROM flags),
  -- and-1: a '1 of 1' FT right after a Made Shot belongs to the prior possession
  fixed AS (SELECT *, CASE WHEN action_type='Free Throw' AND sub_type='Free Throw 1 of 1' AND lag(action_type) OVER (PARTITION BY game_id ORDER BY event_idx) = 'Made Shot' THEN poss_raw - 1 ELSE poss_raw END AS poss_id FROM assign),
  -- carry each possession's first-OREB time to its event rows for the 2nd-chance split
  withc AS (SELECT *, min(elapsed_sec) FILTER (WHERE is_oreb_any) OVER (PARTITION BY game_id, poss_id) AS first_oreb_elapsed FROM fixed),
  -- bonus: elapsed at which each (game, period, team) entered the penalty
  pen AS (
    SELECT game_id, period, team_id AS def_team, elapsed_sec, clock_sec,
      row_number() OVER (PARTITION BY game_id, period, team_id ORDER BY event_idx) AS seq,
      sum(CASE WHEN clock_sec <= 120 THEN 1 ELSE 0 END) OVER (PARTITION BY game_id, period, team_id ORDER BY event_idx) AS seq_last2
    FROM withc WHERE is_pen_foul
  ),
  pen_entry AS (
    SELECT game_id, period, def_team, min(elapsed_sec) AS penalty_elapsed FROM pen
    WHERE (period <= 4 AND seq >= 5)            -- 5th team foul in regulation
       OR (period >= 5 AND seq >= 4)            -- 4th in OT
       OR (clock_sec <= 120 AND seq_last2 >= 2) -- 2nd foul inside the last 2:00
    GROUP BY 1,2,3
  ),
  agg AS (
    SELECT game_id, poss_id,
      max(season) AS season, max(season_type) AS season_type, min(period) AS period,
      max(home_team_id) AS home_team_id, max(away_team_id) AS away_team_id,
      (array_agg(off_team ORDER BY event_idx) FILTER (WHERE ends_poss=1))[1] AS off_team_id,
      min(elapsed_sec) AS start_elapsed_sec, max(elapsed_sec) AS end_elapsed_sec,
      sum(pts_event) AS points,
      sum(pts_event) FILTER (WHERE first_oreb_elapsed IS NULL OR elapsed_sec < first_oreb_elapsed) AS first_chance_pts,
      sum(pts_event) FILTER (WHERE first_oreb_elapsed IS NOT NULL AND elapsed_sec >= first_oreb_elapsed) AS second_chance_pts,
      bool_or(is_oreb_any) AS had_oreb,
      count(*) FILTER (WHERE is_player_oreb) AS n_player_oreb,
      min(elapsed_sec) FILTER (WHERE action_type IN ('Made Shot','Missed Shot','Turnover')) AS first_action_elapsed,
      (array_agg(CASE WHEN action_type='Rebound' THEN 'dreb' WHEN action_type='Made Shot' THEN 'made_fg' WHEN action_type='Turnover' THEN 'turnover' WHEN action_type='Free Throw' THEN 'ft' END ORDER BY event_idx) FILTER (WHERE ends_poss=1))[1] AS end_reason
    FROM withc GROUP BY game_id, poss_id
  ),
  final AS (
    SELECT a.*,
      CASE WHEN a.off_team_id = a.home_team_id THEN a.away_team_id ELSE a.home_team_id END AS def_team_id,
      lag(a.end_reason)      OVER (PARTITION BY a.game_id ORDER BY a.poss_id) AS prev_end_reason,
      -- prior possession end = when THIS team gained the ball; transition clock starts here
      lag(a.end_elapsed_sec) OVER (PARTITION BY a.game_id ORDER BY a.poss_id) AS prev_end_elapsed
    FROM agg a
  )
  SELECT f.game_id, f.poss_id, f.season, f.season_type, f.period, f.off_team_id, f.def_team_id,
    f.start_elapsed_sec, f.end_elapsed_sec, (f.end_elapsed_sec - f.start_elapsed_sec),
    f.points, f.first_chance_pts, f.second_chance_pts, f.had_oreb, f.n_player_oreb, f.end_reason,
    CASE WHEN f.poss_id = 0 OR f.prev_end_reason IS NULL THEN 'period'
         WHEN f.prev_end_reason IN ('made_fg','ft') THEN 'made_basket'
         ELSE f.prev_end_reason END,
    (f.prev_end_reason IN ('dreb','turnover') AND (f.first_action_elapsed - f.prev_end_elapsed) <= 7),
    (pe.penalty_elapsed IS NOT NULL AND pe.penalty_elapsed <= f.start_elapsed_sec)
  FROM final f
  LEFT JOIN pen_entry pe ON pe.game_id = f.game_id AND pe.period = f.period AND pe.def_team = f.def_team_id
  WHERE f.off_team_id IS NOT NULL;

  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n;
END $$;

-- ----------------------------------------------------------------------------
-- Initial population (run once; each call fits under the statement timeout).
-- ----------------------------------------------------------------------------
SELECT public.refresh_possessions('2021-22');
SELECT public.refresh_possessions('2022-23');
SELECT public.refresh_possessions('2023-24');
SELECT public.refresh_possessions('2024-25');
SELECT public.refresh_possessions('2025-26');

-- ----------------------------------------------------------------------------
-- Team split views (offensive). ORtg = points per 100 possessions.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.v_team_bonus_splits AS
SELECT season, season_type, off_team_id AS team_id,
  count(*) AS possessions,
  count(*) FILTER (WHERE opp_in_bonus)     AS poss_bonus,
  count(*) FILTER (WHERE NOT opp_in_bonus) AS poss_nonbonus,
  round(avg((opp_in_bonus)::int), 4)       AS bonus_poss_rate,
  round(100.0*sum(points) FILTER (WHERE opp_in_bonus)     / nullif(count(*) FILTER (WHERE opp_in_bonus),0), 1)     AS ortg_bonus,
  round(100.0*sum(points) FILTER (WHERE NOT opp_in_bonus) / nullif(count(*) FILTER (WHERE NOT opp_in_bonus),0), 1) AS ortg_nonbonus
FROM public.possession GROUP BY season, season_type, off_team_id;

CREATE OR REPLACE VIEW public.v_team_chance_splits AS
SELECT season, season_type, off_team_id AS team_id,
  count(*) AS possessions,
  count(*) FILTER (WHERE had_oreb)   AS second_chance_poss,
  round(avg((had_oreb)::int), 4)     AS second_chance_rate,
  sum(first_chance_pts)              AS first_chance_pts,
  sum(second_chance_pts)             AS second_chance_pts,
  round(100.0*sum(first_chance_pts) / nullif(count(*),0), 1)                       AS first_chance_ortg,
  round(sum(second_chance_pts)::numeric / nullif(count(*) FILTER (WHERE had_oreb),0), 3) AS second_chance_ppp,
  round(sum(second_chance_pts)::numeric / nullif(count(DISTINCT game_id),0), 2)    AS second_chance_pts_per_game
FROM public.possession GROUP BY season, season_type, off_team_id;

CREATE OR REPLACE VIEW public.v_team_transition_splits AS
SELECT season, season_type, off_team_id AS team_id,
  count(*) AS possessions,
  count(*) FILTER (WHERE is_transition)     AS poss_transition,
  count(*) FILTER (WHERE NOT is_transition) AS poss_halfcourt,
  round(avg((is_transition)::int), 4)       AS transition_rate,
  round(avg(points) FILTER (WHERE is_transition), 3)     AS transition_ppp,
  round(avg(points) FILTER (WHERE NOT is_transition), 3) AS halfcourt_ppp
FROM public.possession GROUP BY season, season_type, off_team_id;

-- ----------------------------------------------------------------------------
-- Daily refresh: current season is re-derived inside refresh_show_rollups()
-- (pg_cron 'refresh-show-rollups', 11:45 UTC) via:
--     PERFORM public.refresh_possessions(v_season);
-- added after the four CONCURRENT matview refreshes. Assumes play_by_play for
-- the latest games is already loaded (PBP load is not in the visible pg_cron).
-- ----------------------------------------------------------------------------
