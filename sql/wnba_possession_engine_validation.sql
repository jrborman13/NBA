-- WNBA possession engine -- validation. Run AFTER 01 and after a refresh.
--
-- The point of this file: the possession splitter can be wrong without erroring.
-- It will happily emit a plausible transition rate built from mis-attributed
-- rebounds. Every check below is written to FAIL LOUDLY rather than return a
-- comforting number, and most of them reconcile against an oracle outside this
-- database.
--
-- THE ORACLE. pbpstats serves WNBA team totals at
--   https://api.pbpstats.com/get-totals/wnba?Season=2026&SeasonType=Regular%20Season&Type=Team
-- and those totals include the possession-level denominators:
--   OffPoss, DefPoss, TotalPoss, SecondChanceOffPoss, SecondChancePoints,
--   PenaltyOffPoss, PenaltyDefPoss, PenaltyPoints, PenaltyOffPossPct
-- (227 fields, 15 teams -- measured 2026-08-15).
--
-- That gives an independent check on FOUR of the six spokes' inputs: total
-- possessions, second-chance possessions and points, and bonus/penalty
-- possessions. If those reconcile, the splitter is cutting possessions in the
-- right places, which is the main thing transition depends on too.
--
-- WHAT HAS NO ORACLE: transition itself. pbpstats serves ZERO transition fields
-- for the WNBA, and its StartType parameter is silently ignored -- measured on
-- BOTH leagues, where StartType=Transition returned byte-identical totals to
-- the unfiltered call (WNBA OffPoss 2538 both ways; NBA 8197 both ways). So a
-- request that looks filtered is not. Do not "verify" transition that way.
-- The NBA threshold of 7 seconds was tuned against Synergy, and the WNBA has no
-- Synergy feed, so the transition spoke is the one number here that ships on
-- inherited judgement rather than measurement. Say so on the surface if it
-- ships before it is calibrated.

-- ---------------------------------------------------------------------------
-- CHECK 1 -- nickname resolution. Must return ZERO rows.
-- If a team's nickname does not resolve, ~9.5% of its events lose their team
-- and the possession splitter mis-attributes them, silently.
-- ---------------------------------------------------------------------------
SELECT t.team_id, t.full_name,
       coalesce(nullif(btrim(t.nickname),''),
                (regexp_match(t.full_name,'(\S+)$'))[1]) AS resolved_nickname,
       'nickname did not resolve, or never appears in this team''s PBP' AS problem
FROM wnba.teams t
WHERE coalesce(nullif(btrim(t.nickname),''),
               (regexp_match(t.full_name,'(\S+)$'))[1]) IS NULL
   OR NOT EXISTS (
     SELECT 1 FROM wnba.play_by_play p
     WHERE p.description ILIKE '%'||coalesce(nullif(btrim(t.nickname),''),
                                             (regexp_match(t.full_name,'(\S+)$'))[1])||'%'
     LIMIT 1
   );

-- ---------------------------------------------------------------------------
-- CHECK 2 -- unattributed possessions. Must return ZERO rows.
-- The builder drops rows WHERE off_team_id IS NULL; this proves nothing large
-- was dropped, by comparing possessions per game against a sane floor.
-- WNBA games run ~160-200 total possessions; anything under 120 means events
-- were lost, not that the game was slow.
-- ---------------------------------------------------------------------------
SELECT game_id, count(*) AS possessions
FROM wnba.possession
WHERE season = :'season'
GROUP BY game_id
HAVING count(*) < 120
ORDER BY count(*);

-- ---------------------------------------------------------------------------
-- CHECK 3 -- period math. Must return ZERO rows.
-- Catches the 720-vs-600 error directly: with 10-minute quarters no regulation
-- possession can start past 2400s, and no possession may have negative
-- duration. If the NBA constant survived the port, this lights up.
-- ---------------------------------------------------------------------------
SELECT game_id, poss_idx, period, start_elapsed_sec, end_elapsed_sec, duration_sec
FROM wnba.possession
WHERE season = :'season'
  AND (duration_sec < 0
    OR (period <= 4 AND start_elapsed_sec > 2400)
    OR (period  = 1 AND start_elapsed_sec > 600))
LIMIT 50;

-- ---------------------------------------------------------------------------
-- CHECK 4 -- the pbpstats reconciliation. THIS IS THE IMPORTANT ONE.
-- Paste the pbpstats numbers into the VALUES list and read the diff columns.
-- Fetch them with:
--
--   .venv/bin/python - <<'PY'
--   from curl_cffi import requests as cr
--   r = cr.get("https://api.pbpstats.com/get-totals/wnba",
--              params={"Season":"2026","SeasonType":"Regular Season","Type":"Team"},
--              impersonate="chrome", timeout=60)
--   for t in r.json()["multi_row_table_data"]:
--       print(f"  ('{t['Name']}', {t['OffPoss']}, {t['SecondChanceOffPoss']},"
--             f" {t['SecondChancePoints']}, {t['PenaltyOffPoss']}),")
--   PY
--
-- Tolerance: pbpstats and this engine define a possession slightly differently
-- around and-1s and team-rebound putbacks, so expect small disagreement. Judge
-- it as a PERCENTAGE, not a raw count:
--   under 2%  -- fine, definitional
--   2-5%      -- investigate before shipping the affected spoke
--   over 5%   -- the splitter is wrong; do not ship
-- A team showing 0 where pbpstats shows a real number is never "close" -- that
-- is the absent-value-rendered-as-plausible failure, and it must block.
-- ---------------------------------------------------------------------------
WITH oracle(abbr, off_poss, sc_poss, sc_pts, pen_poss) AS (
  VALUES
    -- ('CON', 2538, 314, 362, 651),   <-- paste real rows here
    ('PASTE_ME', 0, 0, 0, 0)
),
ours AS (
  SELECT t.abbreviation AS abbr,
         c.possessions        AS off_poss,
         c.second_chance_poss AS sc_poss,
         c.second_chance_pts  AS sc_pts,
         b.poss_bonus         AS pen_poss
  FROM wnba.v_team_chance_splits c
  JOIN wnba.v_team_bonus_splits  b USING (season, season_type, team_id)
  JOIN wnba.teams t ON t.team_id = c.team_id
  WHERE c.season = :'season' AND c.season_type = 'Regular Season'
)
SELECT o.abbr,
       ours.off_poss, o.off_poss AS pbp_off_poss,
       round(100.0*(ours.off_poss - o.off_poss)/NULLIF(o.off_poss,0), 2) AS off_poss_pct_diff,
       round(100.0*(ours.sc_poss  - o.sc_poss )/NULLIF(o.sc_poss ,0), 2) AS sc_poss_pct_diff,
       round(100.0*(ours.sc_pts   - o.sc_pts  )/NULLIF(o.sc_pts  ,0), 2) AS sc_pts_pct_diff,
       round(100.0*(ours.pen_poss - o.pen_poss)/NULLIF(o.pen_poss,0), 2) AS bonus_poss_pct_diff
FROM oracle o
LEFT JOIN ours ON ours.abbr = o.abbr
ORDER BY abs(coalesce(round(100.0*(ours.off_poss - o.off_poss)/NULLIF(o.off_poss,0), 2), 999)) DESC;

-- ---------------------------------------------------------------------------
-- CHECK 5 -- transition sanity. No oracle exists, so this is a smell test only.
-- NBA sits near a 0.14-0.16 transition rate with transition PPP clearly above
-- half-court PPP. A WNBA rate at 0 or above 0.40, or transition PPP BELOW
-- half-court PPP, means the 7-second rule or the elapsed-second math is wrong.
-- Passing this does NOT mean the number is calibrated.
-- ---------------------------------------------------------------------------
SELECT t.full_name,
       s.transition_rate, s.transition_ppp, s.halfcourt_ppp,
       CASE WHEN s.transition_rate IS NULL OR s.transition_rate = 0 THEN 'NO TRANSITION FOUND -- rule or clock is broken'
            WHEN s.transition_rate > 0.40                           THEN 'implausibly high'
            WHEN s.transition_ppp <= s.halfcourt_ppp                THEN 'transition should score better than half-court'
            ELSE 'plausible (NOT calibrated)' END AS verdict
FROM wnba.v_team_transition_splits s
JOIN wnba.teams t ON t.team_id = s.team_id
WHERE s.season = :'season' AND s.season_type = 'Regular Season'
ORDER BY s.transition_rate DESC;
