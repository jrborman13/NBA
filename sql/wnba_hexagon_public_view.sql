-- WNBA hexagon -- the one object the website reads. Apply after 04.
--
-- WHY A PROXY VIEW IN `public` RATHER THAN READING THE `wnba` SCHEMA.
--
-- `read.ts` resolves a logical name from the league registry and issues a bare
-- `client().from(name)`, which PostgREST answers from `public`. Every WNBA
-- entry in that registry is therefore a `wnba_*` name in `public` --
-- wnba_team_season_stats, wnba_player_game_logs, wnba_schedule_rows, and so on.
-- This keeps the hexagon on that same rail.
--
-- The alternative works and was tested: PostgREST does serve the wnba schema
-- directly via `Accept-Profile: wnba` (measured, HTTP 200). It was not used,
-- because it would make the hexagon the ONLY WNBA table read through a
-- different mechanism than all the others, for no gain.
--
-- THE TRAP THIS AVOIDS, WHICH IS THE REAL REASON THE FILE EXISTS.
-- `public.v_team_hexagon` already exists -- it is the NBA's -- and it answers
-- the anon key with HTTP 200. So registering the obvious-looking
-- `team_hexagon: "v_team_hexagon"` would have pointed the WNBA team page at
-- the NBA's hexagon. It would not have errored: the WNBA read filters
-- season='2026' and the NBA's seasons are '2025-26', so it returns zero rows
-- and renders an empty chart. A silent empty where a real chart belongs, from
-- a name that looks right -- the failure this repo keeps producing.

CREATE OR REPLACE VIEW public.wnba_team_hexagon AS
  SELECT season, season_type, team_id, team_name,
         o_rim, o_perimeter, o_transition, o_second_chance, o_bonus, o_rebounding,
         d_rim, d_perimeter, d_transition, d_second_chance, d_bonus, d_rebounding
  FROM wnba.v_team_hexagon;

-- SELECT only. The neighbouring public tables carry Supabase's default blanket
-- grants (INSERT/UPDATE/DELETE included), which is meaningless on a view over a
-- view and worth not copying.
GRANT SELECT ON public.wnba_team_hexagon TO anon, authenticated, service_role;

-- Verify, as the site's own credential rather than as the owner:
--   select count(*) from public.wnba_team_hexagon where season='2026';   -- 15
