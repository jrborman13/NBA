-- ============================================================================
-- lineup_at_event: map every play_by_play event -> the person_ids on the floor.
-- The keystone for on/off, lineup +/-, "while on the floor" rates.
--
-- SOURCE: pbp_lineup_stint (reconstructed from PBP substitutions + inferred period starters by
-- scripts/build_pbp_lineups.py). This SUPERSEDES the earlier game_rotation-based version --
-- the GameRotation scrape is Akamai-blocked under bulk load, whereas this is derived from PBP we
-- already hold and covers EVERY game with play-by-play (not just the 523 GameRotation reached).
--
-- Time alignment (the one non-trivial bit):
--   play_by_play.clock          = ISO8601 time REMAINING in the period, e.g. 'PT11M48.00S'
--   pbp_lineup_stint.*_elapsed_sec = ELAPSED game time from tip, in SECONDS
--   => convert each event's (period, clock) to elapsed seconds, then find whose stint window
--      [in_elapsed_sec, out_elapsed_sec) contains it. A sub-IN player counts at the sub instant,
--      the sub-OUT player does not (half-open interval).
--   Period lengths: regulation (1-4) = 720s; OT (5+) = 300s.
--
-- ALWAYS filter by game_id: the on_floor subquery is correlated and uses
-- idx_pbp_lineup_stint_lookup; an unfiltered scan over all ~13.5M events is expensive.
--   SELECT * FROM lineup_at_event WHERE game_id = '0022500001' ORDER BY event_idx;
-- ============================================================================

CREATE OR REPLACE VIEW lineup_at_event AS
WITH ev AS (
  SELECT
    game_id, event_idx, season, season_type, period, clock, team_id, person_id,
    action_type, description,
    CASE WHEN clock ~ 'PT(\d+)M([\d.]+)S' THEN
        (CASE WHEN period <= 4 THEN (period - 1) * 720 ELSE 2880 + (period - 5) * 300 END)
      + (CASE WHEN period <= 4 THEN 720 ELSE 300 END)
      - ((substring(clock from 'PT(\d+)M'))::int * 60
         + (substring(clock from 'M([\d.]+)S'))::numeric)
    END AS elapsed_sec
  FROM play_by_play
)
SELECT
  e.game_id, e.event_idx, e.season, e.season_type, e.period, e.clock, e.elapsed_sec,
  e.team_id, e.person_id, e.action_type, e.description,
  (SELECT array_agg(s.person_id ORDER BY s.team_id, s.person_id)
     FROM pbp_lineup_stint s
    WHERE s.game_id = e.game_id
      AND e.elapsed_sec IS NOT NULL
      AND s.in_elapsed_sec <= e.elapsed_sec
      AND s.out_elapsed_sec > e.elapsed_sec) AS on_floor
FROM ev e;

-- USAGE
--   assists while player :pid was on the floor:
--     SELECT count(*) FROM lineup_at_event
--     WHERE game_id = :gid AND assist_person_id IS NOT NULL AND :pid = ANY(on_floor);
--
-- PERFORMANCE: the on_floor subquery recomputes per query -- fine when filtered to a game.
-- For league-wide precompute, materialize it:
--   CREATE TABLE lineup_at_event_mat AS SELECT * FROM lineup_at_event;
--   ALTER TABLE lineup_at_event_mat ADD PRIMARY KEY (game_id, event_idx);
--   CREATE INDEX ON lineup_at_event_mat USING gin (on_floor);   -- fast "= ANY(on_floor)" filters
-- ============================================================================
