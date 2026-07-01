-- =====================================================================
-- Seed: league_constants — 2026-27.
-- Figures as published on SalarySwish (June 2026). PROJECTED: the NBA
-- does not set the official cap until ~early July, so is_estimated=true.
-- Re-run with official numbers once announced. MLE/BAE left null pending
-- confirmation (the page shows a $6,083,000 mid-level remaining for LAL,
-- consistent with the Taxpayer MLE, but confirm before seeding).
-- =====================================================================

insert into league_constants
  (season, salary_cap, tax_level, first_apron, second_apron, min_team_salary,
   nontax_mle, tax_mle, room_mle, biannual, apron_era, is_estimated, source, source_url, effective_date, notes)
values
  ('2026-27', 165472000, 201048000, 209661000, 222372000, 148924800,
    null, null, null, null, true, true,
    'SalarySwish (projected)', 'https://www.salaryswish.com/salary-cap',
    null, 'Projected pre-July 2026; min_team_salary = 90% of cap. Replace with official figures and seed MLE/BAE when announced.')

on conflict (season) do update set
  salary_cap = excluded.salary_cap,
  tax_level = excluded.tax_level,
  first_apron = excluded.first_apron,
  second_apron = excluded.second_apron,
  min_team_salary = excluded.min_team_salary,
  apron_era = excluded.apron_era,
  is_estimated = excluded.is_estimated,
  source = excluded.source,
  source_url = excluded.source_url,
  notes = excluded.notes,
  updated_at = now();
