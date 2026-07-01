-- ============================================================================
-- possession_engine_validation.sql
-- Acceptance tests for possession (see possession_engine.sql).
-- Run AFTER creating possession. Observed values are from 2025-26 Regular
-- Season at build time (2026-06-26). Re-run after each refresh; investigate any
-- check that drifts materially.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- A. POSSESSION COUNT vs official NBA possessions (team_season_stats.POSS)
--    Tolerance: within ~2%. Possession count is the foundation — if this drifts,
--    every downstream split is suspect.
--    OBSERVED: derived 99.60 / team / game  vs  official ~100.74  (~1.1% low)
-- ---------------------------------------------------------------------------
SELECT
  round(count(*)::numeric / count(DISTINCT game_id) / 2, 2) AS derived_poss_per_team_per_game
FROM public.possession
WHERE season='2025-26' AND season_type='Regular Season';

SELECT round(avg((stats->>'POSS')::numeric) / 82, 2) AS official_poss_per_team_per_game
FROM public.team_season_stats
WHERE season='2025-26' AND season_type='Regular Season'
  AND measure_type='Advanced' AND per_mode='PerGame';   -- POSS stored as season total

-- ---------------------------------------------------------------------------
-- B. PER-GAME PARITY — the two teams must have ~equal possessions every game.
--    OBSERVED (0022500001): 109 vs 111 (diff 2, well within tolerance).
--    Flag any game with |diff| > 3.
-- ---------------------------------------------------------------------------
SELECT game_id,
  max(poss) - min(poss) AS poss_diff
FROM (
  SELECT game_id, off_team_id, count(*) poss
  FROM public.possession
  WHERE season='2025-26' AND season_type='Regular Season'
  GROUP BY game_id, off_team_id
) q
GROUP BY game_id
HAVING max(poss) - min(poss) > 3
ORDER BY poss_diff DESC;
-- Expect: few or no rows. (Genuine blowouts/garbage time can produce small diffs.)

-- ---------------------------------------------------------------------------
-- C. PLAYER OREB vs box score (team_game_logs.OREB)
--    n_player_oreb counts player offensive rebounds only (team rebounds excluded)
--    so it must reconcile to the official box OREB.
--    OBSERVED: derived 27,991 vs box 27,989  (2 / ~28k = 99.99%)
-- ---------------------------------------------------------------------------
SELECT
  (SELECT sum(n_player_oreb) FROM public.possession
     WHERE season='2025-26' AND season_type='Regular Season') AS derived_player_oreb,
  (SELECT sum((stats->>'OREB')::numeric) FROM public.team_game_logs
     WHERE season='2025-26' AND season_type='Regular Season') AS box_oreb;

-- ---------------------------------------------------------------------------
-- D. BONUS STATE invariant (does not depend on possession; re-derives).
--    A non-shooting defensive common foul (Personal / Loose Ball) committed in
--    the penalty must be followed by the fouled team shooting FTs.
--    OBSERVED: when flagged in-bonus, FTs follow 99.4% of the time
--    (penalty_no_ft = 116 of ~18,310). The reverse direction (ft_no_penalty)
--    is inflated by shooting fouls miscoded as 'Personal' — a known confound,
--    not a state-machine error.
-- ---------------------------------------------------------------------------
WITH base AS (
  SELECT game_id, event_idx, period, clock, action_type, sub_type, team_id,
    lead(action_type) OVER w a1, lead(action_type,2) OVER w a2, lead(action_type,3) OVER w a3,
    lead(team_id)    OVER w t1, lead(team_id,2)    OVER w t2, lead(team_id,3)    OVER w t3
  FROM public.play_by_play
  WHERE season='2025-26' AND season_type='Regular Season'
  WINDOW w AS (PARTITION BY game_id ORDER BY event_idx)
),
pf AS (
  SELECT *,
    row_number() OVER (PARTITION BY game_id,period,team_id ORDER BY event_idx) seq,
    ((regexp_match(clock,'PT(\d+)M([\d.]+)S'))[1]::int*60
      + (regexp_match(clock,'PT(\d+)M([\d.]+)S'))[2]::numeric) <= 120 AS in_last2
  FROM base
  WHERE action_type='Foul'
    AND sub_type IN ('Shooting','Personal','Loose Ball','Personal Take','Away From Play',
                     'Transition Take','Clear Path','Flagrant Type 1','Flagrant Type 2')
),
pf2 AS (
  SELECT *, sum((in_last2)::int) OVER (PARTITION BY game_id,period,team_id ORDER BY event_idx) seq_last2
  FROM pf
),
test AS (
  SELECT
    ((period<=4 AND seq>=5) OR (period>=5 AND seq>=4) OR (in_last2 AND seq_last2>=2)) AS penalty,
    ((a1='Free Throw' AND t1<>team_id) OR (a2='Free Throw' AND t2<>team_id)
       OR (a3='Free Throw' AND t3<>team_id)) AS ft_followed
  FROM pf2 WHERE sub_type IN ('Personal','Loose Ball')
)
SELECT count(*) n,
  round(avg((penalty=ft_followed)::int)::numeric,4) AS agreement,
  count(*) FILTER (WHERE penalty AND NOT ft_followed) AS penalty_no_ft,   -- the clean error signal
  count(*) FILTER (WHERE NOT penalty AND ft_followed) AS ft_no_penalty    -- inflated by shooting fouls coded 'Personal'
FROM test;

-- ---------------------------------------------------------------------------
-- E. TRANSITION RATE vs Synergy curated transition frequency.
--    OBSERVED: derived 0.192 vs Synergy team-offensive Transition POSS_PCT 0.185
--    NOTE: entity_type is 'T'/'P' (not 'team'/'player') in synergy_playtypes.
-- ---------------------------------------------------------------------------
SELECT round(avg((is_transition)::int),4) AS derived_transition_rate
FROM public.possession
WHERE season='2025-26' AND season_type='Regular Season';

SELECT round(avg((stats->>'POSS_PCT')::numeric),4) AS synergy_transition_freq
FROM public.synergy_playtypes
WHERE season='2025-26' AND season_type='Regular Season'
  AND entity_type='T' AND type_grouping='offensive' AND play_type='Transition';

-- ---------------------------------------------------------------------------
-- F. POINTS CONSERVATION / attribution
--    Total possession points must equal total game points. Per-team may differ
--    by a couple points due to and-1 / technical-FT edge handling.
--    OBSERVED (0022500001): derived 122/127 vs box 124/125; total 249 = 249.
--    Inter-team gap of 2 (and-1 reassignment). Immaterial for PPP splits;
--    revisit and-1 handling if exact per-team points are ever required.
-- ---------------------------------------------------------------------------
SELECT off_team_id, sum(points) AS derived_pts
FROM public.possession WHERE game_id='0022500001' GROUP BY off_team_id;

SELECT team_id, (stats->>'PTS')::numeric AS box_pts
FROM public.team_game_logs WHERE game_id='0022500001';

-- ---------------------------------------------------------------------------
-- G. SANITY: the three requested splits at league level (eyeball for sane PPP).
--    Bonus PPP should exceed non-bonus PPP (free throws). Second-chance PPP is
--    typically high (putbacks). Transition PPP should exceed halfcourt.
-- ---------------------------------------------------------------------------
SELECT
  round(avg(points) FILTER (WHERE opp_in_bonus),3)        AS bonus_ppp,
  round(avg(points) FILTER (WHERE NOT opp_in_bonus),3)    AS nonbonus_ppp,
  round(avg(points) FILTER (WHERE is_transition),3)       AS transition_ppp,
  round(avg(points) FILTER (WHERE NOT is_transition),3)   AS halfcourt_ppp,
  round(sum(second_chance_pts)::numeric / nullif(count(*) FILTER (WHERE had_oreb),0),3) AS second_chance_ppp,
  round(avg((had_oreb)::int),4)                           AS second_chance_rate
FROM public.possession
WHERE season='2025-26' AND season_type='Regular Season';
