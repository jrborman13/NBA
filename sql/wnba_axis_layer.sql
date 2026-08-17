-- WNBA hexagon axis layer -- the chain above wnba.possession.
--
-- Depends on 01_wnba_possession_engine.sql being applied and both seasons
-- refreshed. Apply after that, and after the NBA repo's ingest has run
-- `--tier 1` for the season (team_season_stats, Advanced) -- without it the
-- `adv` join finds nothing and the whole chain returns zero rows.
--
-- TWO DELIBERATE DIVERGENCES FROM THE NBA VERSION. Both are load-bearing.
--
-- 1. NO MATERIALIZED TABLE -- *** THIS ARGUMENT WAS WRONG. SUPERSEDED BY 04. ***
--    Measured after applying: the hexagon read took 8,577 ms and timed out
--    through PostgREST. The reasoning below sized the chain on possessions
--    (~110k) when it actually scans all 2.69M play-by-play rows via
--    shot_event. Apply 04_wnba_axis_materialize.sql; it moves this
--    computation to v_team_axis_metrics_src and adds the table + refresh.
--    Left below unedited so the mistake is legible.
--
-- 1. (original, wrong) NO MATERIALIZED `team_axis_metrics` TABLE, AND NO REFRESH FUNCTION.
--    The NBA materializes because its source is 13M play-by-play rows and 3.3M
--    possessions; recomputing on read is not viable there. The WNBA side is
--    ~110k possessions for a season -- roughly 30x smaller -- so this is a
--    plain view chain that is always current.
--
--    That removes an entire class of failure rather than trading one for
--    another: the NBA hexagon silently served stale numbers for 44 consecutive
--    nights because the refresh that fed it had died and nothing noticed. A
--    view cannot go stale. If the read cost ever becomes a problem, materialise
--    then -- but do not add a refresh step before it is needed.
--
-- 2. NULL SUB-METRICS ARE DROPPED BEFORE RANKING (the `WHERE raw_value IS NOT
--    NULL` in v_team_axis_long). This is REQUIRED for the WNBA and is not a
--    style choice.
--
--    v_team_hexagon computes sum(pctile*weight)/sum(weight) over a join to
--    team_axis_weights. The WNBA has no player-tracking feed, so seven
--    sub-metrics have no source at all: cs_efg, pu_efg, open_rate (perimeter
--    off), three_stop (perimeter def), rim_stop (rim def), and contest_pct on
--    both rebounding sides. Left in, each would carry its weight into the
--    DENOMINATOR while contributing nothing to the numerator, quietly dragging
--    every affected axis toward zero -- a team would look bad at perimeter
--    offence because the league does not track catch-and-shoot, which is the
--    absent-value-rendered-as-plausible failure in its purest form.
--
--    Dropped instead, so each axis is a weighted mean over the sub-metrics that
--    actually exist. What survives per axis:
--
--      transition     ppp(2) + rate(1)            3/3   full
--      second_chance  ppp(2) + rate(1)            3/3   full
--      bonus          rate(2) + rtg(1)            3/3   full
--      rim      off   freq(1) + pct(2)            3/3   full
--      rim      def   freq(1) + pct(2)            3/4.5 no rim_stop
--      perimeter def  freq(1) + pct(2)            3/4   no three_stop
--      perimeter off  freq(1) + pct(2)            3/6   no cs_efg/pu_efg/open_rate
--      rebounding     reb_pct(1)                  1/2   no contest_pct
--
--    All six axes still compute, but perimeter-off and rebounding rest on half
--    their intended evidence. That is a real degradation and it should be said
--    on the surface, not hidden behind a number that looks like the NBA's.
--
-- team_axis_weights is NOT copied into the wnba schema -- this reads
-- public.team_axis_weights directly, so both leagues' hexagons stay defined by
-- one set of weights. Changing the shape of the chart for one league only would
-- almost certainly be a mistake, and duplicating the table is how that starts.

-- ---------------------------------------------------------------------------
-- 1. shot_event -- rim and perimeter frequencies/accuracy
-- ---------------------------------------------------------------------------
-- Same as public.shot_event except the period arithmetic (600/2400, not
-- 720/2880). elapsed_sec is not read by anything downstream of here, but a
-- wrong clock in a view named shot_event is a trap for the next reader.
--
-- The shot_zone constants are NBA court geometry and are deliberately kept:
-- the two zones the hexagon actually uses are 'Restricted Area'
-- (shot_distance <= 4, identical in both leagues) and shot_value = 3, which
-- comes from the feed. The corner-3 boundary at |loc_x| >= 220 is NOT WNBA
-- accurate -- the WNBA arc is shorter -- but nothing in the team axis layer
-- reads the corner/above-break split, so it is left alone rather than guessed
-- at. Do not build a player hexagon on that column without fixing it first.
-- assist_person_id is an explicit NULL, not an omission. It is the ONLY column
-- public.play_by_play has that wnba.play_by_play does not (22 vs 21) -- the
-- ingest's pbp id_map never wrote it for either league, so it reached the NBA
-- table by some other route. Nothing in the team axis layer reads it, but the
-- column is kept so wnba.shot_event stays shape-compatible with
-- public.shot_event; a view that is silently one column narrower is a trap for
-- whoever writes cross-league code against it later.
CREATE OR REPLACE VIEW wnba.shot_event AS
  SELECT game_id, event_idx, season, season_type, period, clock, team_id,
    person_id AS shooter_id, NULL::bigint AS assist_person_id,
    loc_x, loc_y, shot_value,
    shot_distance, shot_result, description,
    CASE WHEN clock ~ 'PT(\d+)M([\d.]+)S'
         THEN (CASE WHEN period <= 4 THEN (period-1)*600 ELSE 2400 + (period-5)*300 END
             + CASE WHEN period <= 4 THEN 600 ELSE 300 END)::numeric
             - ((substring(clock,'PT(\d+)M')::integer * 60)::numeric
                + substring(clock,'M([\d.]+)S')::numeric)
         ELSE NULL::numeric END AS elapsed_sec,
    CASE
      WHEN loc_x IS NULL OR shot_value IS NULL THEN NULL::text
      WHEN shot_distance > 40 THEN 'Backcourt'
      WHEN shot_value = 3 AND abs(loc_x) >= 220 AND loc_y::numeric <= 92.5
        THEN CASE WHEN loc_x < 0 THEN 'Left Corner 3' ELSE 'Right Corner 3' END
      WHEN shot_value = 3 THEN 'Above-the-Break 3'
      WHEN shot_distance <= 4 THEN 'Restricted Area'
      WHEN abs(loc_x) <= 80 AND loc_y <= 190 THEN 'In-Paint (non-RA)'
      ELSE 'Mid-Range'
    END AS shot_zone
  FROM wnba.play_by_play
  WHERE action_type IN ('Made Shot','Missed Shot');

-- ---------------------------------------------------------------------------
-- 2. v_team_axis_metrics -- the 35-column wide row, per team per season
-- ---------------------------------------------------------------------------
-- Ported from public.v_team_axis_metrics_src. The six tracking CTEs of the NBA
-- version (cst/put/rbt/sqt/dft_rim/dft_three) are omitted rather than left as
-- empty LEFT JOINs: wnba.pt_tracking_team is 0 rows and the other three
-- pt_* tables have no wnba counterpart at all. Their columns are selected as
-- explicit NULLs so the shape still matches the NBA view exactly, and so the
-- NULL filter in the next view can drop them.
CREATE OR REPLACE VIEW wnba.v_team_axis_metrics AS
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
  tr.transition_ppp        AS o_trans_ppp,
  tr.transition_rate       AS o_trans_rate,
  ch.second_chance_ppp     AS o_2nd_ppp,
  ch.second_chance_rate    AS o_2nd_rate,
  bo.bonus_poss_rate       AS o_bonus_rate,
  bo.ortg_bonus            AS o_bonus_ortg,
  a.oreb_pct               AS o_oreb_pct,
  round(100.0 * d.rim_fga::numeric / NULLIF(d.fga,0)::numeric, 1)     AS d_rim_freq,
  round(100.0 * d.rim_fgm::numeric / NULLIF(d.rim_fga,0)::numeric, 1) AS d_rim_pct,
  round(100.0 * d.fg3a::numeric / NULLIF(d.fga,0)::numeric, 1)        AS d_3_freq,
  round(100.0 * d.fg3m::numeric / NULLIF(d.fg3a,0)::numeric, 1)       AS d_3pct,
  trd.transition_ppp_allowed        AS d_trans_ppp,
  trd.transition_rate_allowed       AS d_trans_rate,
  chd.second_chance_ppp_allowed     AS d_2nd_ppp,
  chd.second_chance_rate_allowed    AS d_2nd_rate,
  bod.bonus_poss_rate_allowed       AS d_bonus_rate,
  bod.drtg_bonus                    AS d_bonus_drtg,
  a.dreb_pct                        AS d_dreb_pct,
  a.off_rtg, a.def_rtg,
  -- No WNBA player-tracking feed. Explicit NULLs, dropped downstream.
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
-- 3. v_team_axis_long -- unpivot, WITH THE NULL FILTER (divergence 2)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW wnba.v_team_axis_long AS
  SELECT m.season, m.season_type, m.team_id, m.team_name,
    x.axis, x.side, x.sub_metric, x.raw_value,
    CASE
      WHEN x.sub_metric = ANY (ARRAY['rim_stop','three_stop']) THEN true
      WHEN x.side = 'off' THEN true
      WHEN x.axis = 'rebounding' THEN true
      ELSE false
    END AS higher_is_good
  FROM wnba.v_team_axis_metrics m
  CROSS JOIN LATERAL (VALUES
    ('rim','off','freq',m.o_rim_freq), ('rim','off','pct',m.o_rim_pct),
    ('perimeter','off','freq',m.o_3_freq), ('perimeter','off','pct',m.o_3pct),
    ('transition','off','rate',m.o_trans_rate), ('transition','off','ppp',m.o_trans_ppp),
    ('second_chance','off','rate',m.o_2nd_rate), ('second_chance','off','ppp',m.o_2nd_ppp),
    ('bonus','off','rate',m.o_bonus_rate), ('bonus','off','rtg',m.o_bonus_ortg),
    ('rebounding','off','reb_pct',m.o_oreb_pct),
    ('rim','def','freq',m.d_rim_freq), ('rim','def','pct',m.d_rim_pct),
    ('perimeter','def','freq',m.d_3_freq), ('perimeter','def','pct',m.d_3pct),
    ('transition','def','rate',m.d_trans_rate), ('transition','def','ppp',m.d_trans_ppp),
    ('second_chance','def','rate',m.d_2nd_rate), ('second_chance','def','ppp',m.d_2nd_ppp),
    ('bonus','def','rate',m.d_bonus_rate), ('bonus','def','rtg',m.d_bonus_drtg),
    ('rebounding','def','reb_pct',m.d_dreb_pct),
    ('perimeter','off','cs_efg',m.o_cs_efg), ('perimeter','off','pu_efg',m.o_pu_efg),
    ('perimeter','off','open_rate',m.o_open_rate),
    ('rebounding','off','contest_pct',m.o_oreb_contest),
    ('rebounding','def','contest_pct',m.d_dreb_contest),
    ('rim','def','rim_stop',m.d_rim_stop),
    ('perimeter','def','three_stop',m.d_three_stop)
  ) x(axis, side, sub_metric, raw_value)
  -- THE DIVERGENCE. Without this a sub-metric the WNBA cannot measure still
  -- carries its weight into v_team_hexagon's denominator and drags the axis
  -- down. See the header.
  WHERE x.raw_value IS NOT NULL;

-- ---------------------------------------------------------------------------
-- 4. v_team_axis_pctile -- percentile within (season, season_type, side, axis, sub_metric)
-- ---------------------------------------------------------------------------
-- Identical to the NBA version. The partition includes season, and the WNBA
-- season string is '2026' where the NBA's is '2025-26', so WNBA teams rank
-- against WNBA teams even though this reads a different schema anyway.
CREATE OR REPLACE VIEW wnba.v_team_axis_pctile AS
  SELECT season, season_type, team_id, team_name, axis, side, sub_metric,
    raw_value, higher_is_good,
    round((100.0 * percent_rank() OVER (
      PARTITION BY season, season_type, side, axis, sub_metric
      ORDER BY (CASE WHEN higher_is_good THEN raw_value ELSE -raw_value END)
    ))::numeric, 1) AS pctile
  FROM wnba.v_team_axis_long l;

-- ---------------------------------------------------------------------------
-- 5. v_team_hexagon -- the 12 columns the site reads
-- ---------------------------------------------------------------------------
-- Joins public.team_axis_weights on purpose; see the header.
CREATE OR REPLACE VIEW wnba.v_team_hexagon AS
WITH scored AS (
  SELECT p.season, p.season_type, p.team_id, p.team_name, p.side, p.axis,
    round(sum(p.pctile * w.weight) / NULLIF(sum(w.weight), 0::numeric), 1) AS axis_score
  FROM wnba.v_team_axis_pctile p
  JOIN public.team_axis_weights w USING (axis, sub_metric)
  GROUP BY p.season, p.season_type, p.team_id, p.team_name, p.side, p.axis
)
SELECT season, season_type, team_id, team_name,
  max(axis_score) FILTER (WHERE side='off' AND axis='rim')           AS o_rim,
  max(axis_score) FILTER (WHERE side='off' AND axis='perimeter')     AS o_perimeter,
  max(axis_score) FILTER (WHERE side='off' AND axis='transition')    AS o_transition,
  max(axis_score) FILTER (WHERE side='off' AND axis='second_chance') AS o_second_chance,
  max(axis_score) FILTER (WHERE side='off' AND axis='bonus')         AS o_bonus,
  max(axis_score) FILTER (WHERE side='off' AND axis='rebounding')    AS o_rebounding,
  max(axis_score) FILTER (WHERE side='def' AND axis='rim')           AS d_rim,
  max(axis_score) FILTER (WHERE side='def' AND axis='perimeter')     AS d_perimeter,
  max(axis_score) FILTER (WHERE side='def' AND axis='transition')    AS d_transition,
  max(axis_score) FILTER (WHERE side='def' AND axis='second_chance') AS d_second_chance,
  max(axis_score) FILTER (WHERE side='def' AND axis='bonus')         AS d_bonus,
  max(axis_score) FILTER (WHERE side='def' AND axis='rebounding')    AS d_rebounding
FROM scored
GROUP BY season, season_type, team_id, team_name;
