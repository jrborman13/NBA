-- WNBA possession engine -- DRAFT, NOT APPLIED.
--
-- A port of its sibling `possession_engine.sql` onto the `wnba` schema, which
-- holds the WNBA play-by-play (2,693,392 rows / 6,668 games / 1997-2026).
--
-- Drafted in the WNBA repo (docs/wnba-possession-engine/) and copied here
-- because THIS repo owns the shared project's schema. Keep the two in sync, or
-- better, treat this copy as the source of truth -- the sibling file is already
-- stale against production, which is the failure this copy exists to avoid.
--
-- Validation queries: wnba_possession_engine_validation.sql, alongside.
--
-- Ported from the LIVE `public.refresh_possessions` (read out of pg_proc on
-- 2026-08-15), NOT from the checked-in NBA file -- that file is stale: it is
-- missing the `set_config('statement_timeout','0')` fix added 2026-08-09 after
-- the nightly cron had failed 44 consecutive nights on a statement timeout
-- thrown by this INSERT. The fix is carried over below.
--
-- WHAT CHANGES FROM THE NBA VERSION, and why. Each was measured, not assumed:
--
--   1. Schema: public.* -> wnba.*. WNBA play-by-play already exists at
--      wnba.play_by_play (2,693,392 rows / 6,668 games / seasons 1997-2025).
--      There is no wnba.possession; this creates it.
--
--   2. Period length: 720/2880 -> 600/2400. WNBA regulation is 10 minutes, not
--      12. Verified against wnba.play_by_play season 2025: periods 1-4 show a
--      maximum clock of 10 minutes, periods 5-6 show 5 minutes. OT stays 300s.
--
--   3. Nickname fallback made null-safe. The engine resolves team rebounds and
--      team turnovers -- rows where the feed leaves team_id 0 or NULL -- by
--      matching the team NICKNAME inside the event description. In wnba.teams
--      all 13 rows have nickname NULL (and city and abbreviation NULL too);
--      only full_name is populated. Left as-is, '%'||NULL||'%' makes the ILIKE
--      NULL, every one of those events resolves to no team, and the possession
--      splitter silently mis-attributes them.
--
--      This is NOT a rounding-error case: in season 2025, 11,953 of 126,330
--      events (9.46%) need this fallback, and 5,488 of them are Rebounds or
--      Turnovers -- precisely the events that set `end_reason`, which is what
--      `is_transition` keys off. Getting this wrong would not error; it would
--      quietly produce plausible, wrong transition rates.
--
--      Fix below: prefer a real nickname, fall back to the last word of
--      full_name. Verified against the actual descriptions, which are exactly
--      '<NICKNAME> Rebound' -- 'MERCURY Rebound', 'Aces Rebound', 'VALKYRIES
--      Rebound' (case varies; ILIKE covers it). Every current and 2026 WNBA
--      nickname is a single word, so last-word is exact. No team list is
--      hardcoded. Run 02_validation.sql after loading: it fails loudly if any
--      team's nickname does not resolve.
--
--   4. season_type: wnba.play_by_play carries only 'Regular Season' and
--      'Playoffs' (measured). The wider IN list is kept so the filter does not
--      silently drop a value the ingest starts emitting later. Note the NBA
--      side has a latent bug here -- the ingest writes 'Play-In' with a hyphen
--      while some filters test 'Play In' without -- so both spellings are
--      listed rather than one.
--
-- WHAT DOES NOT CHANGE, and why it is safe:
--
--   * The event grammar. wnba.play_by_play uses the identical action_type
--     vocabulary the engine expects (Made Shot, Missed Shot, Rebound, Free
--     Throw, Turnover, Foul) and the identical ISO clock format -- the regex
--     'PT(\d+)M([\d.]+)S' matched 60,000 of 60,000 sampled rows.
--
--   * The 7-second transition threshold. It is a delta between two events in
--     the same period, so the period-length constant cancels out of it. But see
--     the calibration warning in README.md: the NBA threshold was tuned against
--     Synergy, and WNBA has no Synergy feed to tune against.
--
-- THE BONUS RULE WAS WRONG IN THE FIRST DRAFT. NOW MEASURED AND FIXED.
-- The first version carried the NBA's thresholds (5th team foul in regulation,
-- 4th in OT) and flagged them as the one rule with no measurement behind them.
-- They were checked on 2026-08-16 against pbpstats and they were wrong: the
-- WNBA enters the bonus on the 4th team foul, one earlier than the NBA. Left
-- as drafted it under-counted bonus possessions by 48.6%. Numbers on pen_entry
-- below.
--
-- Worth stating plainly: the flagged rule was the one that broke. The other
-- five spokes reconciled. Possessions came within 1.1% of pbpstats and points
-- within 0.8%, so the splitter itself was right from the start -- it was only
-- the inherited rule constant that did not transfer between leagues.

-- ---------------------------------------------------------------------------
-- 1. Table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS wnba.possession (
  game_id            text     NOT NULL,
  poss_idx           integer  NOT NULL,
  season             text,
  season_type        text,
  period             integer,
  off_team_id        bigint,
  def_team_id        bigint,
  start_elapsed_sec  numeric,
  end_elapsed_sec    numeric,
  duration_sec       numeric,
  points             integer,
  first_chance_pts   integer,
  second_chance_pts  integer,
  had_oreb           boolean,
  n_player_oreb      integer,
  end_reason         text,
  start_reason       text,
  is_transition      boolean,
  opp_in_bonus       boolean,
  PRIMARY KEY (game_id, poss_idx)
);

CREATE INDEX IF NOT EXISTS possession_wnba_season_off_idx
  ON wnba.possession (season, season_type, off_team_id);
CREATE INDEX IF NOT EXISTS possession_wnba_season_def_idx
  ON wnba.possession (season, season_type, def_team_id);

-- ---------------------------------------------------------------------------
-- 2. Builder
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION wnba.refresh_possessions(p_season text)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
  -- Do not remove. The per-event window walk exceeds the default timeout; this
  -- is the 2026-08-09 fix for the 44-night cron failure on the NBA side.
  PERFORM set_config('statement_timeout','0',true);
  DELETE FROM wnba.possession WHERE season = p_season;

  INSERT INTO wnba.possession (
    game_id, poss_idx, season, season_type, period, off_team_id, def_team_id,
    start_elapsed_sec, end_elapsed_sec, duration_sec, points, first_chance_pts,
    second_chance_pts, had_oreb, n_player_oreb, end_reason, start_reason,
    is_transition, opp_in_bonus
  )
  WITH base AS (
    SELECT p.game_id, p.season, p.season_type, p.event_idx, p.period, p.clock,
           p.action_type, p.sub_type, p.description, p.shot_value,
           p.team_id AS raw_team, p.score_home, p.score_away,
           s.home_team_id, s.away_team_id,
           -- CHANGED vs NBA: null-safe nickname. See note 3 in the header.
           coalesce(nullif(btrim(th.nickname), ''),
                    (regexp_match(th.full_name, '(\S+)$'))[1]) AS hn,
           coalesce(nullif(btrim(ta.nickname), ''),
                    (regexp_match(ta.full_name, '(\S+)$'))[1]) AS an
    FROM wnba.play_by_play p
    JOIN wnba.schedule s ON s.game_id = p.game_id
    JOIN wnba.teams th   ON th.team_id = s.home_team_id
    JOIN wnba.teams ta   ON ta.team_id = s.away_team_id
    WHERE p.season = p_season
      AND p.season_type IN ('Regular Season','Playoffs','Play In','Play-In')
  ),
  ev AS (
    SELECT *,
      CASE WHEN raw_team IS NOT NULL AND raw_team <> 0 THEN raw_team
           WHEN hn IS NOT NULL AND description ILIKE '%'||hn||'%' THEN home_team_id
           WHEN an IS NOT NULL AND description ILIKE '%'||an||'%' THEN away_team_id END AS team_id,
      ( (regexp_match(clock,'PT(\d+)M([\d.]+)S'))[1]::int * 60
      + (regexp_match(clock,'PT(\d+)M([\d.]+)S'))[2]::numeric ) AS clock_sec,
      (action_type='Missed Shot'
         OR (action_type='Free Throw' AND description ILIKE 'MISS%')) AS is_miss
    FROM base
  ),
  el AS (
    -- CHANGED vs NBA: 600/2400 for 10-minute WNBA quarters, not 720/2880.
    SELECT *,
      CASE WHEN period <= 4 THEN (period-1)*600 + (600 - clock_sec)
           ELSE 2400 + (period-5)*300 + (300 - clock_sec) END AS elapsed_sec
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
  fixed AS (SELECT *, CASE WHEN action_type='Free Throw' AND sub_type='Free Throw 1 of 1' AND lag(action_type) OVER (PARTITION BY game_id ORDER BY event_idx) = 'Made Shot' THEN poss_raw - 1 ELSE poss_raw END AS poss_id FROM assign),
  withc AS (SELECT *, min(elapsed_sec) FILTER (WHERE is_oreb_any) OVER (PARTITION BY game_id, poss_id) AS first_oreb_elapsed FROM fixed),
  pen AS (
    SELECT game_id, period, team_id AS def_team, elapsed_sec, clock_sec,
      row_number() OVER (PARTITION BY game_id, period, team_id ORDER BY event_idx) AS seq,
      sum(CASE WHEN clock_sec <= 120 THEN 1 ELSE 0 END) OVER (PARTITION BY game_id, period, team_id ORDER BY event_idx) AS seq_last2
    FROM withc WHERE is_pen_foul
  ),
  pen_entry AS (
    -- WAS UNVERIFIED; NOW MEASURED. The WNBA enters the bonus a foul EARLIER
    -- than the NBA, so the inherited NBA thresholds were wrong here.
    --
    -- Reconciled against pbpstats PenaltyOffPoss, 2025 Regular Season, all 13
    -- teams (9,616 bonus possessions):
    --
    --   seq >= 5  (the NBA rule, as first drafted)   4,940   -48.6%
    --   seq >= 4                                     8,914    -7.3%
    --   seq >= 3                                    15,063   +56.6%
    --
    -- and on the ranking the hexagon actually renders, mean rank error across
    -- 13 teams fell from 1.69 places at seq>=5 to 0.62 at seq>=4, with the top
    -- two and bottom two exact. 4 it is.
    --
    -- The residual -7.3% is NOT chased further on purpose. It is bracketed --
    -- relaxing the last-two-minutes arm to seq_last2 >= 1 overshoots to +6.2%
    -- -- so the true rule sits between the two, and the remaining gap is
    -- probably which foul sub_types count (that list is still the NBA's).
    -- Tuning past this point fits pbpstats' definition rather than the WNBA
    -- rulebook, which is a different and worse goal.
    SELECT game_id, period, def_team, min(elapsed_sec) AS penalty_elapsed FROM pen
    WHERE (period <= 4 AND seq >= 4) OR (period >= 5 AND seq >= 3) OR (clock_sec <= 120 AND seq_last2 >= 2)
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

-- ---------------------------------------------------------------------------
-- 3. Splits views -- identical to the NBA definitions except FROM wnba.possession
-- ---------------------------------------------------------------------------

CREATE OR REPLACE VIEW wnba.v_team_transition_splits AS
  SELECT season, season_type, off_team_id AS team_id,
    count(*) AS possessions,
    count(*) FILTER (WHERE is_transition) AS poss_transition,
    count(*) FILTER (WHERE NOT is_transition) AS poss_halfcourt,
    round(avg(is_transition::integer), 4) AS transition_rate,
    round(avg(points) FILTER (WHERE is_transition), 3) AS transition_ppp,
    round(avg(points) FILTER (WHERE NOT is_transition), 3) AS halfcourt_ppp
  FROM wnba.possession GROUP BY season, season_type, off_team_id;

CREATE OR REPLACE VIEW wnba.v_team_transition_splits_def AS
  SELECT season, season_type, def_team_id AS team_id,
    count(*) AS possessions_faced,
    count(*) FILTER (WHERE is_transition) AS poss_transition_allowed,
    count(*) FILTER (WHERE NOT is_transition) AS poss_halfcourt_allowed,
    round(avg(is_transition::integer), 4) AS transition_rate_allowed,
    round(avg(points) FILTER (WHERE is_transition), 3) AS transition_ppp_allowed,
    round(avg(points) FILTER (WHERE NOT is_transition), 3) AS halfcourt_ppp_allowed
  FROM wnba.possession GROUP BY season, season_type, def_team_id;

CREATE OR REPLACE VIEW wnba.v_team_chance_splits AS
  SELECT season, season_type, off_team_id AS team_id,
    count(*) AS possessions,
    count(*) FILTER (WHERE had_oreb) AS second_chance_poss,
    round(avg(had_oreb::integer), 4) AS second_chance_rate,
    sum(first_chance_pts) AS first_chance_pts,
    sum(second_chance_pts) AS second_chance_pts,
    round(100.0 * sum(first_chance_pts)::numeric / NULLIF(count(*), 0)::numeric, 1) AS first_chance_ortg,
    round(sum(second_chance_pts)::numeric / NULLIF(count(*) FILTER (WHERE had_oreb), 0)::numeric, 3) AS second_chance_ppp,
    round(sum(second_chance_pts)::numeric / NULLIF(count(DISTINCT game_id), 0)::numeric, 2) AS second_chance_pts_per_game
  FROM wnba.possession GROUP BY season, season_type, off_team_id;

CREATE OR REPLACE VIEW wnba.v_team_chance_splits_def AS
  SELECT season, season_type, def_team_id AS team_id,
    count(*) AS possessions_faced,
    count(*) FILTER (WHERE had_oreb) AS second_chance_poss_allowed,
    round(avg(had_oreb::integer), 4) AS second_chance_rate_allowed,
    sum(second_chance_pts) AS second_chance_pts_allowed,
    round(sum(second_chance_pts)::numeric / NULLIF(count(*) FILTER (WHERE had_oreb), 0)::numeric, 3) AS second_chance_ppp_allowed,
    round(sum(second_chance_pts)::numeric / NULLIF(count(DISTINCT game_id), 0)::numeric, 2) AS second_chance_pts_allowed_per_game
  FROM wnba.possession GROUP BY season, season_type, def_team_id;

CREATE OR REPLACE VIEW wnba.v_team_bonus_splits AS
  SELECT season, season_type, off_team_id AS team_id,
    count(*) AS possessions,
    count(*) FILTER (WHERE opp_in_bonus) AS poss_bonus,
    count(*) FILTER (WHERE NOT opp_in_bonus) AS poss_nonbonus,
    round(avg(opp_in_bonus::integer), 4) AS bonus_poss_rate,
    round(100.0 * sum(points) FILTER (WHERE opp_in_bonus)::numeric / NULLIF(count(*) FILTER (WHERE opp_in_bonus), 0)::numeric, 1) AS ortg_bonus,
    round(100.0 * sum(points) FILTER (WHERE NOT opp_in_bonus)::numeric / NULLIF(count(*) FILTER (WHERE NOT opp_in_bonus), 0)::numeric, 1) AS ortg_nonbonus
  FROM wnba.possession GROUP BY season, season_type, off_team_id;

CREATE OR REPLACE VIEW wnba.v_team_bonus_splits_def AS
  SELECT season, season_type, def_team_id AS team_id,
    count(*) AS possessions_faced,
    count(*) FILTER (WHERE opp_in_bonus) AS poss_bonus,
    count(*) FILTER (WHERE NOT opp_in_bonus) AS poss_nonbonus,
    round(avg(opp_in_bonus::integer), 4) AS bonus_poss_rate_allowed,
    round(100.0 * sum(points) FILTER (WHERE opp_in_bonus)::numeric / NULLIF(count(*) FILTER (WHERE opp_in_bonus), 0)::numeric, 1) AS drtg_bonus,
    round(100.0 * sum(points) FILTER (WHERE NOT opp_in_bonus)::numeric / NULLIF(count(*) FILTER (WHERE NOT opp_in_bonus), 0)::numeric, 1) AS drtg_nonbonus
  FROM wnba.possession GROUP BY season, season_type, def_team_id;

-- Run for one season first and check 02_validation.sql before backfilling:
--   SELECT wnba.refresh_possessions('2025');
