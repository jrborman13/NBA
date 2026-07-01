-- =====================================================================
-- Seed: league_constants — apron-era seasons (2023-24 onward).
-- Figures verified against official NBA / Hoops Rumors announcements
-- (June 2026). Bi-annual = 3.32% of the Salary Cap.
-- Pre-2023-24 seasons can be added later for core cap/tax validation
-- (aprons null). Idempotent upsert.
-- =====================================================================

insert into league_constants
  (season, salary_cap, tax_level, first_apron, second_apron, min_team_salary,
   nontax_mle, tax_mle, room_mle, biannual, apron_era, is_estimated, source, source_url, effective_date, notes)
values
  ('2023-24', 136021000, 165294000, 172346000, 182794000, 122418000,
    12405000, 5000000, 7723000, 4516000, true, false,
    'NBA official / Hoops Rumors', 'https://pr.nba.com/nba-salary-cap-for-2023-24-season-set-at-136-021-million',
    '2023-07-01', 'First apron-era season.'),

  ('2024-25', 140588000, 170814000, 178132000, 188931000, 126529000,
    12822000, 5168000, 8006000, 4668000, true, false,
    'NBA official / Hoops Rumors', 'https://pr.nba.com/2024-25-nba-season-salary-cap',
    '2024-07-01', 'Bi-annual computed as 3.32% of cap; confirm exact published value.'),

  ('2025-26', 154647000, 187895000, 195945000, 207824000, 139182000,
    14104000, 5685000, 8781000, 5134000, true, false,
    'NBA official / Hoops Rumors', 'https://pr.nba.com/nba-salary-cap-2025-26-season',
    '2025-07-01', 'Cap grew the max 10% over 2024-25.')

on conflict (season) do update set
  salary_cap = excluded.salary_cap,
  tax_level = excluded.tax_level,
  first_apron = excluded.first_apron,
  second_apron = excluded.second_apron,
  min_team_salary = excluded.min_team_salary,
  nontax_mle = excluded.nontax_mle,
  tax_mle = excluded.tax_mle,
  room_mle = excluded.room_mle,
  biannual = excluded.biannual,
  apron_era = excluded.apron_era,
  is_estimated = excluded.is_estimated,
  source = excluded.source,
  source_url = excluded.source_url,
  effective_date = excluded.effective_date,
  notes = excluded.notes,
  updated_at = now();
