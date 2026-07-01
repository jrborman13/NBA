# Team-Fit System — Discussion Brief

**Purpose of this doc:** hand off to Claude Cowork to brainstorm and design a system that finds
**team fits** — matching players to teams (and teams to players) by *hexagon profile* and *overall
playstyle*. The author isn't committed to an approach yet and wants to discuss paths forward. This
brief gives the current state, the data we already have, the core conceptual challenge, and 5
candidate approaches with trade-offs.

Project: NBA analytics app (Streamlit + Supabase warehouse, Postgres). Supabase project ref
`qhrgekcowkgwcaaqyqvv` ("NBA App"). Authoritative architecture docs in the repo:
`CLAUDE.md`, `SUPABASE_DERIVED_OBJECTS.md`, `SUPABASE_DATA_CATALOG.md`.

---

## 1. The goal (what we want to build)

A system that answers questions like:
- *"Which teams would player X fit best?"* (player → team) — for free agency / trade targets.
- *"Given team Y's identity and needs, which available players fit?"* (team → player).
- *"Why is it a fit?"* — an explanation in terms of need-gaps, stylistic complement, and role.

"Fit" is intentionally fuzzy right now. Part of the discussion is **defining what fit means**
(need-filling vs. stylistic similarity vs. lineup complementarity vs. projected on-court impact).
See §3 and §5.

---

## 2. Current state — what's already built

Two **hexagons** are deployed and validated, each a 6-spoke 0–100 percentile radar.

### 2a. Player hexagon (`v_player_hexagon`)
Six **skill** axes, percentiled vs the league (or vs position). Seasons 2013-14 → 2025-26.
Qualifier: `off_poss_on >= 1000`. Pools: `all` and `position`.

| Axis | Meaning (primary sub-metrics) |
|---|---|
| Finishing | rim FG% over league, rim rate, team rim-freq on/off |
| Shooting | catch-&-shoot eFG, pull-up eFG, shot-making over expected, spot-up PPP *(volume-floored)* |
| Playmaking | AST%, assist points created, drive assists |
| Defending | rim-stop (normal−actual FG% allowed), FG suppression, deflections/36, contested-2PT/36, BLK/STL |
| Rebounding | OREB%, DREB%, contested-reb/36, reb-chance conversion, 2nd-chance on/off |
| Gravity | shot-diet gravity (expected-eFG on/off), ORtg lift, rim-freq lift |

Backing objects: `player_axis_metrics` (materialized raw sub-metrics) → `v_player_axis_pctile`
(0–100) → `hexagon_weights` (editable weights) → `v_player_hexagon`. Streamlit: `7_Hexagon.py`.

### 2b. Team hexagon (`v_team_hexagon`)
Six **phase-of-play** spokes, each rendered **twice** (offense solid / defense dashed), oriented so
outward = good. 13 seasons × {Regular Season, Playoffs}. Just materialized into `team_axis_metrics`
for speed.

| Spoke | Offense (`o_*`) | Defense (`d_*`) |
|---|---|---|
| Rim | rim rate × rim FG%, rim-stop | opp rim rate/FG% allowed, rim-stop |
| Perimeter | 3-rate × 3P%, C&S/pull-up eFG, open-shot rate | opp 3-rate/3P% allowed, perimeter stop |
| Transition | transition rate × PPP | transition allowed |
| Second chance | 2nd-chance rate × PPP | 2nd-chance allowed |
| Bonus | bonus-possession rate × ORtg | bonus allowed |
| Rebounding | OREB% + contested% | DREB% + contested% |

Backing objects: `team_axis_metrics` (table) → `v_team_axis_long` → `v_team_axis_pctile` →
`v_team_hexagon`; weights in `team_axis_weights`. Streamlit: `8_Team_Hexagon.py`.

### 2c. ⚠️ Key structural fact: the two hexagons are on DIFFERENT axes
The player hexagon measures **skills** (finishing, shooting, playmaking, defending, rebounding,
gravity). The team hexagon measures **phases of play** (rim, perimeter, transition, second chance,
bonus, rebounding) split offense/defense. They do **not** line up spoke-for-spoke, so "fit" cannot
be a naive overlay of one radar on the other. Bridging these two coordinate systems is the central
design problem (see §3).

---

## 3. The core conceptual challenge

Three things have to be pinned down before building:

1. **What does "fit" mean?** Candidate definitions (not mutually exclusive):
   - **Need-filling** — the team is weak/thin where the player is strong (marginal value).
   - **Stylistic match** — the player plays the *way* the team plays (pace, shot diet, playtype mix).
   - **Complementarity** — the player makes *teammates/lineups* better (gravity, spacing, passing
     chemistry), not just adds raw production.
   - **Projected impact** — translate the player's box/efficiency into team Y's system and pace, then
     score the delta to the current roster.

2. **The axis bridge.** Player skills ≠ team phases. Two ways to connect them:
   - **(a) Contribution mapping** — hand-define how each player skill feeds each team phase (e.g.,
     Shooting+Gravity → offensive Perimeter; Finishing → offensive Rim; Defending sub-metrics → the
     defensive spokes). Transparent, but hand-tuned.
   - **(b) Shared "style fingerprint"** — compute a *common* feature vector at BOTH player and team
     grain from the same sources (pace, shot-location mix, playtype mix, ball-movement, defensive
     scheme proxies). Then fit lives in one shared space, no mapping needed. (Recommended bridge —
     see §5.)

3. **Ground truth / validation.** How do we know a fit score is *good*? We have multi-season data,
   on/off ratings, and possession-level lineups — so we can backtest: did players who changed teams
   into a high-"fit" situation actually see their on/off impact / efficiency improve? (See §6.)

---

## 4. Data assets we can use (already in the warehouse)

Beyond the two hexagons, the warehouse already has most of what a fit system needs:

| Asset | Object(s) | Why it matters for fit |
|---|---|---|
| Playtype mix (player & team) | `synergy_playtypes` (`entity_type` P/T): PnR ball-handler/roll, iso, spot-up, handoff, cut, post-up, off-screen, transition, putbacks | The cleanest **shared style fingerprint** — same playtypes describe a player's diet and a team's diet |
| Team playtype profile + exploit finder | `v_team_playtype_profile`, `matchup_exploits()` | Team offensive/defensive tendencies by playtype |
| On/off impact | `v_player_onoff_context`, `mv_player_onoff` (official ORtg/DRtg on/off, net swing) | Did the player make the team better; basis for impact-validation |
| Gravity / shot-quality on-off | `v_player_shot_onoff_context` | Spacing/complementarity signal |
| 5-man lineup impact | `possession_lineup` (3.3M rows), `staggering_splits()`, `team_lineup_tiers()`, `clutch_lineups()` | Complementarity / who-plays-well-with-whom |
| Passing chemistry | `v_passing_connections` (passer→receiver, FG% lift) | Connection strength / fit with specific teammates |
| Usage & efficiency | `v_player_usage_efficiency` (usg×ts quadrant), `v_player_self_creation` | Role/usage fit (can the team absorb the player's usage?) |
| Shot diet / location | `shot_event` zones, `v_team_shot_selection`, `mv_league_zone_efg` | Shot-location overlap between player and team |
| Pace / transition / 2nd-chance / bonus | `possession`, team split views (`v_team_{bonus,chance,transition}_splits(_def)`) | Tempo + phase tendencies |
| Team form / ratings | `v_team_game_ratings`, `team_rolling_rating()`, `mv_team_form` | Current team strength/trajectory |
| Similar players | `player_similarity.py` module | Existing notion of stylistic neighbors |
| Roster / availability | `nba_player_index`, game logs, injury report modules | Who's actually on which team / available |

**Note on team identity for skills:** the player hexagon's defensive/gravity axes use on/off and
lineup context, which a team doesn't have an analog for — another reason the bridge (§3.2) matters.

---

## 5. Candidate paths forward (for discussion)

Five approaches, roughly increasing in ambition. They compose — e.g., A as v1, then layer C/D.

### Path A — Need-gap matching (rules-based, fast v1)  ✅ BUILT 2026-06-30
> **Objects:** `fit_contribution` (editable skill→phase map), `v_player_phase_strength`,
> `team_needs` (weak pctile × thin supply, with `is_need` flag + continuous `need_weight`).
> **Scorer:** `analysis/team_fit_pathA.py` — `need_fill` and `style_match` as **cosine alignment**
> of the player's phase profile with the team's need / strength profile (magnitude-removed so it's
> SPECIFIC fit, not "good player × needy team"), blended by tunable `w`. Explainable output works.
> **Backtest result (through the Goal-1 harness, judged on the over-performance PARTIAL controlling
> player level + destination quality):** pure **need_fill (w=1.0) beats both baselines** — Δ TS%
> lift **+0.08 / +0.09**, Δ on/off-net positive too. The robust signal is the **monotone w-sweep on
> both outcomes** (need_fill > blends > style_match, which is *negative*): **filling holes predicts
> over-performance; reinforcing strengths does not.** Honest caveat: small effect, not yet
> significant (p≈0.14, n≈350). On *raw* delta nothing wins (incl. baselines) — it's
> mean-reversion/quality-confounded; we judged the residualized over-performance, never flipped sign.


Score each team's hexagon spokes to find **weaknesses** (low percentile) and **thin rotations**
(few players who supply that skill). Map player skills → team phases via a transparent contribution
table (§3.2a). Fit score = Σ (team need on phase) × (player strength feeding that phase).
- **Pros:** shippable in days; fully explainable ("OKC ranks 27th in offensive Rebounding and you're
  92nd-pctile there"); reuses both hexagons directly.
- **Cons:** hand-tuned mapping; ignores diminishing returns, usage conflicts, and complementarity;
  "need" ≠ "value" (a team may be weak somewhere on purpose).
- **Build:** contribution mapping + a `team_needs` view + a scoring function/notebook. No new data.

### Path B — Shared style fingerprint + similarity (the bridge, recommended core)  ✅ BUILT 2026-06-30
> **Objects:** `style_fingerprint` (materialized table + `refresh_style_fingerprint`, cron-wired) from
> `v_style_fingerprint_src` — a **28-dim** profile computed IDENTICALLY at player & team grain:
> offensive(11)+defensive(7) Synergy play-type shares, shot-zone mix(5), possession phase rates(5).
> Validated: computed shares == Synergy's official `POSS_PCT` exactly (diff 0.000).
> **Scorer:** `analysis/team_fit_pathB.py` — `style_match` = cosine of standardized fingerprints;
> `need_fill` = cosine(player percentile profile, team **deficit** profile); same tunable `w`.
> **Embedding (2024-25 PCA, players+teams in one space) — face-valid:** Gobert's nearest are all
> rim-running centers (Holmes/Kornet/Hayes/Plumlee/Bona/Missi), Curry's are shooters; on-ball creators
> **Luka–Harden cluster tightly (0.83)**, both ~9.5 from Gobert (Curry sits apart as a movement shooter).
> **Backtest:** **matches/beats Path A** — need_fill (w=1) **+0.086 on Δ on/off-net** (Path A +0.028),
> **+0.074 on Δ TS%** (Path A +0.079). **need_fill carries the lift on BOTH paths** (style_match alone
> ~0/negative) = convergent evidence. Same modest regime (best p≈0.13, n≈320), but Path B needs NO
> skill→phase mapping and yields the validated shared embedding — the recommended bridge.


Build ONE feature vector computed identically at player and team grain (§3.2b): pace, rim/mid/3
shot mix, playtype shares (from `synergy_playtypes`), ball-movement (passing), transition rate,
defensive scheme proxies. Normalize. Then:
- **Stylistic match** = similarity between a player's fingerprint and a team's fingerprint (or the
  team's *without* the departing player).
- Optionally split into "does the player play like this team" vs "does the player supply what this
  team lacks" (two sub-scores).
- **Pros:** principled bridge; one space for both entities; powers similarity, clustering, and viz
  (2D embedding of players + teams together). Reuses synergy/shot/possession data we already have.
- **Cons:** requires deciding the feature list + weighting; pure similarity rewards *redundancy*
  (fitting in) which is sometimes the opposite of *value* (filling a gap) — needs the need-weighting
  from A to be useful.
- **Build:** a `style_fingerprint` view at both grains + a distance/compatibility function.

### Path C — Complementarity / lineup-fit (uses `possession_lineup`)
Model fit as *projected lineup synergy*: how a player's on/off impact changes with the surrounding
context (a low-gravity rim-runner needs a high-gravity creator; a non-shooter hurts a drive-heavy
team). Use `possession_lineup` + on/off + gravity to learn context-dependent value.
- **Pros:** captures the real basketball question ("will the *fit* unlock value", not just "is it
  similar"); strongest differentiation from public tools.
- **Cons:** hardest; small samples per lineup; needs careful causal framing to avoid confounds.
- **Build:** feature engineering on `possession_lineup`; likely a model, not just SQL.

### Path D — Style-translation / projection model
Translate a player's production into team Y's system: re-weight their shot diet, usage, and pace to
team Y's, project efficiency, and score the marginal upgrade over the current roster slot.
- **Pros:** outputs a tangible "projected line / impact in this system"; intuitive for the user.
- **Cons:** translation assumptions are strong; needs a usage-availability model (can the team give
  the player the touches?).
- **Build:** a projection layer on top of `v_player_usage_efficiency` + team pace/shot-diet.

### Path E — Learned embedding + compatibility model (most ambitious)
Embed players and teams in a shared latent space (matrix factorization / two-tower model) trained on
historical outcomes (on/off impact when players actually joined teams). Fit = learned compatibility.
- **Pros:** can capture nonlinear fit; improves with data.
- **Cons:** needs a labeled training signal (player-moved-to-team → impact delta); heaviest; least
  explainable. Better as a later iteration once A/B exist and we have a validation pipeline.

---

## 6. Validation strategy (applies to any path)

> **STATUS: the backtest harness is BUILT (2026-06-30) — it's the referee for everything below.**
> - SQL: `v_team_fit_cohort` (412 real moves, 2021-22→2025-26, ≥500 off-poss both seasons, validated
>   vs known moves), `v_team_fit_outcomes` → materialized **`team_fit_outcomes`** (Δ on/off net + Δ TS%,
>   with age + prior-minutes controls), helpers `v_team_netrtg` / `v_synergy_off_freq`.
> - Code: `analysis/team_fit_backtest.py` (+ `.ipynb`). `score_report(fit_score, ...)` grades ANY
>   `fit_score(player_id, from_season, to_team)` callable: Spearman + partial Spearman (controls
>   removed) + lift vs two baselines.
> - **The bar (Spearman vs Δ on/off net):** good-player×good-team **−0.05**, style-similarity-only
>   **+0.05** — both ~zero / not significant. A real fit score must clear this by a meaningful margin.
> - **Caveat surfaced:** Δ on/off net is baseline-relative and noisy (punishes regression-to-mean);
>   consider a better outcome target. Δ TS% is cleaner but narrower. See the notebook's notes cell.

> **DECISION (2026-06-30): spec-locked, power-analyzed, NOT expanding — ship v1.**
> **Locked spec (pre-registered, the ONE headline):** outcome = Δ on/off-net, Path B `need_fill`,
> `w=1.0`, over-performance partial (controls age, prior_min, from_net, dest_netrtg), **RS-only
> fingerprints** → **r = +0.087, n = 325, p = 0.116** — beats both baselines (lift +0.038 / +0.127),
> not significant. (Re-confirmed after the `season_type`-collision fix; was +0.083/p=0.134 on the
> contaminated load — the clean result is marginally *stronger*.)
> **Power (`analysis/team_fit_power.py`):** n≈**508** to cross p<0.05 at the point estimate; n≈**1031**
> for 80% power.
> **→ Do NOT expand the cohort to chase significance — the primary reason is effect size, not
> reachability.** Even the best-case expansion buys a *significant* r≈0.087: an effect this small is a
> weak stylistic prior, not a decision-grade predictor. Confirming a tiny effect is real doesn't make
> it big enough to build on, so the expansion effort isn't justified regardless of sample math. This
> reason is assumption-free and holds no matter where the sample cap lands.
> **Secondary (reachability, now borderline):** on the clean RS-only numbers the max expandable sample
> (~**1041** common, floored by Synergy's 2013-14 start) sits *just above* the ~1031 needed for 80%
> power — so raw-sample reachability is no longer the clean "no" it was pre-fix (was 1041 < 1135). The
> only thing keeping it out of reach is that the pre-2021 portion would be a *proxy* outcome whose
> attenuation raises the effective requirement above 1041 — a real but assumption-dependent argument.
> Do not lean the decision on this leg; lean it on effect size above.
> The differentiator is **convergent evidence** (both Path A and Path B independently find `need_fill`
> carries the lift) **+ beating both §6 baselines + the face-valid embedding** — not p<0.05.
>
> **v1 SHIPPED:** `combined-app/player_app/team_fit.py` + Streamlit page `combined-app/pages/9_Team_Fit.py`
> — need-fill-weighted symmetric `fit(player, team)` (w≈0.9) exposing `style_match` / `need_fill` /
> blend, a "why it fits" explainer (top dims the player supplies that the team lacks), and the
> player+team 2D PCA embedding as the viz. UI is framed honestly ("validated to beat baseline;
> directional, not yet statistically decisive").

The differentiator is proving fit scores predict something. Proposed backtest:
- Find players who **changed teams** across seasons (multi-season data is in the warehouse).
- For each, compute their pre-move fit score to the new team using only pre-move data.
- Measure whether high-fit moves correlated with **improved on/off impact / efficiency / role** after
  the move (`mv_player_onoff`, `v_player_usage_efficiency`, box production).
- A fit score with no predictive lift over a naive baseline (e.g., "good player + good team") isn't
  worth shipping. Decide the success metric early.

---

## 7. A suggested starting point (author's lean — open to debate)
1. **Path B fingerprint as the backbone** (the bridge we need anyway), built from `synergy_playtypes`
   + shot zones + pace — computed at both player and team grain.
2. **Layer Path A need-weighting** so the score balances "plays like them" vs "fills a gap" (expose
   both sub-scores so the user can choose the blend).
3. **Stand up the §6 backtest immediately** as the referee, before over-investing.
4. Defer C/D/E until A+B prove directionally useful on the backtest.

This gets an explainable, shippable v1 (need-gap + style similarity, with a 2D player+team map for
visualization) while keeping the door open to the impact/complementarity models.

---

## 8. Open questions for the discussion
1. **Primary direction:** player→team, team→player, or both from one symmetric score?
2. **Fit definition weighting:** how much "plays like the team" vs "fills a need" vs "unlocks
   teammates"? Should it be user-tunable (like `hexagon_weights`)?
3. **Universe of "available" players:** free agents only? all players (hypothetical trades)? How do we
   source availability (cap/contract data isn't in the warehouse — there's a `cba/` folder, unverified)?
4. **Season scope:** single current season, or multi-season blended profiles (more stable, less
   current)?
5. **Role/usage realism:** do we constrain by whether the team can actually give the player the
   minutes/touches, or score pure stylistic fit and let the user judge?
6. **Output form:** ranked list + explanation? a fit matrix (players × teams) heatmap? an overlay of
   player skill-contribution on the team hexagon? a 2D style map?
7. **Validation metric:** what's the success bar in §6 that makes this worth shipping?

---

## 9. Quick reference — how to query what exists
- Supabase project ref: `qhrgekcowkgwcaaqyqvv`. App reads via anon client
  (`combined-app/player_app/supabase_config.get_supabase_client()`); creds in repo-root `.env`.
- Player hexagon: `v_player_hexagon` (filter `pool='all'`, `season`, `season_type`), raw sub-metrics
  in `player_axis_metrics` / `v_player_axis_pctile`.
- Team hexagon: `v_team_hexagon`, raw in `team_axis_metrics` / `v_team_axis_pctile`.
- Playtypes: `synergy_playtypes` (`entity_type` `P`=player, `T`=team; `type_grouping`
  `offensive`/`defensive`; `play_type` ∈ Spotup, PRBallHandler, PRRollman, Isolation, Handoff, Cut,
  Postup, OffScreen, Transition, OffRebound, Misc).
- Lineups: `possession_lineup`; on/off: `mv_player_onoff`, `v_player_onoff_context`.
- Full object map + gotchas: `SUPABASE_DERIVED_OBJECTS.md` (§4 player hexagon, §8 team hexagon, §9
  Part B stat ideas) and `SUPABASE_DATA_CATALOG.md` (raw tables).
- **Performance gotcha:** views over `shot_event` (a view over 13M play-by-play rows) are slow and can
  hit the PostgREST statement timeout — that's why both hexagons are materialized into tables. Any new
  fit objects that scan `shot_event` should be materialized + refreshed nightly the same way.
