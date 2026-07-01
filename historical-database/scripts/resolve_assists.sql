-- ============================================================================
-- Resolve assist_person_id on play_by_play from the V3 description text.
-- Run AFTER the play_by_play (V3) scrape completes. Pure DB transform, no API.
--
-- V3 keeps only the shooter as person_id; the assister is in the description, e.g.
--   "Tatum 27' 3PT Pullup Jump Shot (3 PTS) (White 1 AST)"
--   "Arroyo 19' Jump Shot (2 PTS) (R. Wallace 1 AST)"   <- disambiguated when a last name
--                                                           is shared by 2 players in the game
-- Strategy (measured ~99.7% resolved, 0 ambiguous on a 300-game sample):
--   1. extract the assist name token before " <n> AST)"
--   2. roster = players who appear in that game's player_game_logs (catches assist-only players,
--      not just those who acted in play_by_play)
--   3. match on unaccented last name; if the text is "X. Lastname", also require first initial = X
-- Unmatched (~0.3%: mononyms like "Yao", odd spellings) stay NULL.
-- ============================================================================

ALTER TABLE play_by_play ADD COLUMN IF NOT EXISTS assist_person_id BIGINT;
CREATE INDEX IF NOT EXISTS ix_pbp_assist ON play_by_play (assist_person_id);

WITH assisted AS (
    SELECT game_id, event_idx,
           trim(unaccent(substring(description FROM '\(([^()0-9]+) [0-9]+ AST\)'))) AS raw_name
    FROM play_by_play
    WHERE description ~ '[0-9]+ AST\)'
),
parsed AS (  -- split optional "X. " first-initial prefix off the last name
    SELECT game_id, event_idx,
           CASE WHEN raw_name ~ '^[A-Za-z]\. '
                THEN lower(substring(raw_name FROM '^[A-Za-z]\. (.+)$'))
                ELSE lower(raw_name) END                                  AS last_ln,
           CASE WHEN raw_name ~ '^[A-Za-z]\. '
                THEN lower(substring(raw_name FROM '^([A-Za-z])\.'))
                ELSE NULL END                                            AS first_init
    FROM assisted
    WHERE raw_name IS NOT NULL AND raw_name <> ''
),
roster AS (  -- every player who appeared in the game (full roster, incl. assist-only players)
    SELECT DISTINCT pgl.game_id, pgl.player_id,
           lower(unaccent(p.last_name)) AS ln,
           lower(left(p.first_name, 1)) AS fi
    FROM player_game_logs pgl
    JOIN players p ON p.player_id = pgl.player_id
),
resolved AS (
    SELECT pa.game_id, pa.event_idx, r.player_id,
           count(*) OVER (PARTITION BY pa.game_id, pa.event_idx) AS n
    FROM parsed pa
    JOIN roster r ON r.game_id = pa.game_id AND r.ln = pa.last_ln
                 AND (pa.first_init IS NULL OR r.fi = pa.first_init)
)
UPDATE play_by_play pbp
SET assist_person_id = resolved.player_id
FROM resolved
WHERE pbp.game_id = resolved.game_id
  AND pbp.event_idx = resolved.event_idx
  AND resolved.n = 1;        -- only set when the match is unambiguous

-- Quick coverage check after running:
-- SELECT count(*) assists, count(assist_person_id) resolved,
--        round(100.0*count(assist_person_id)/count(*),1) pct
-- FROM play_by_play WHERE description ~ '[0-9]+ AST\)';
