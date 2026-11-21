# HOME P2 — report (the new Home front end)

Builder: Opus, 2026-10-12. Commits: `5b08f1fb1` (kit icons + Inter), `7e14eb2e7` (months `foreign_runs`),
`3cad5084e` (front end), `063be62a0` (tests), plus this report + ledger rows H22–H30. Not pushed, not deployed.

## What shipped
- `pb_dashboard/static/src/{js,xml,scss}/pb_dashboard.*` rewritten on `get_home_data()` (one call): top line,
  hero (state headline, sentence with inline links, five-node journey, ONE solid primary that names the act +
  "Open pay runs" outline + "Insights" ghost, "<Month> so far" card with progress bar and 12-month net sparkline),
  needs-you chips + "All N approvals" tail (or the grey "Nothing needs you right now · next: payday …"), the
  12-month column chart that is the month picker (click / ← → / Home / End / Escape, tooltip with full figures,
  hollow in-progress column at the latest month's height with the prepared share inside, "Latest" / "In
  progress" / "Tet" labels, segmented Net / Gross / Deductions / Employer cost / People), the month panel (pill,
  facts, four figures with sparklines + neutral deltas + 520 ms count-up, stacked Net | Deductions | Employer
  cost bar with the Gross bracket and legend), "<Month>, step by step" and "Coming up". `<!-- P3: cards -->`
  placeholder left.
- Activation checklist markup byte-for-byte (test 5 compares it to the pre-P2 block); while `activation.show`
  the hero shrinks to the greeting and the checklist takes the page.
- Five Learn anchors, once each: hero section, primary button, chart card, four-figure grid, steps card.
- Kit: `fileCheck, layoutGrid, moveRight, chartColumn, triangleAlert, flame` (Lucide paths); Inter variable
  WOFF2 (OFL, 352 KB) in `pb_import_kit/static/fonts/` with `fonts.scss` FIRST in the backend bundle —
  **every screen that already names Inter (biz_theme's base font, `.pbim`, every cockpit) now renders in Inter.**
- Server touch (allowed by the P1 answers): `months[].foreign_runs` (H21) → facts line "1 run in another
  currency is not added".
- Versions: `pb_dashboard 19.0.2.1.0` (depends + `pb_import_kit`), `pb_import_kit 19.0.1.21.0`.

## Tests (bench `p0clone`, `/tmp/h2stage` = pb_dashboard + pb_import_kit, `-u pb_import_kit,pb_dashboard --test-tags /pb_dashboard`)
`pb_dashboard: 74 tests … 0 failed, 0 error(s)`.

| # | Test | Result |
|---|---|---|
| 1 | five `data-coach` anchors exactly once | pass |
| 2 | every `ic()` / `icon()` / table `icon:` name exists in the kit IC map (incl. the six new) | pass |
| 3 | NEEDS = server `NEEDS_ORDER`, STEPS = `STEP_KEYS`, UPCOMING = the five `kind`s, both ways | pass |
| 4 | no platform name, no emoji, no `#4F46E5`, no colour fades in template/JS/SCSS; `#5A4BB0` is the brand | pass |
| 5 | JS calls only `get_home_data`; activation block identical to the pre-P2 fixture | pass |
| 6 | formatter pins: `a >= 1e9 / 1e6 / 1e3`, one space before the unit, `toLocaleString` for full figures | pass |
| 7 | manifests (depends, 19.0.2.1.0, kit ≥ 1.21.0), `fonts.scss` first, WOFF2 present, `@font-face` 100–900 swap | pass |
| + | `foreign_runs`: a run whose money is in another currency adds to `runs` and `foreign_runs`, not to `net` | pass |
| — | adapted: test_06 (no dial call at all, zero `pbd-ring-none`), test_p9 (singular pin moved), P1 `MONTH_KEYS` + `foreign_runs` | pass |
| — | pb_home_hub dashboard pins (depends, top line `pbd-top`, two Insights doors, `pb_back` keys, no `@pb_hub/`) | pass as a local twin only — they cannot run on a two-module stage (H22); they run for real at deploy |
| 8 | browser walk on the clone | **not done**: `free -m` showed 687–692 MB available, under the 700 MB gate. |

Instead of the walk: an offline render with the vendored OWL + jsdom (H27) of the real template and script in 7
payload shapes — rich (prototype-like), empty clone, no money (no pb_payruns), activation embedded,
`month:2026-03` focus, load failure, stage None — zero render errors; ← moved to August with the tooltip,
Escape returned to the latest, the primary opened Pay Run › Runs focused on run 7 with the Home back chip, a
leave chip opened Home › Approvals without a back chip, People measure switched the axis. SCSS compiled with
dart-sass. **No screenshots exist** — Fable's walk after deploy is the first visual check (1440 and 1100 px).

## Design-bar self-score (1–5)
- Hero moment (sentence + chart-as-picker): **4** — built as specified and keyboard-complete; unproven in a real browser.
- Zero dead-ends: **5** — every chip, journey node, step, coming-up row, figure, inline run name and the "does not balance" fact is a door; empty states say what will appear.
- Motion with purpose: **4** — rise, column grow, count-up, one pulse, progress grow; all off under reduced motion (count-up checks it in JS); not yet seen on screen.
- Lucide / locked indigo / no fades / no emoji / one solid primary: **5** — pinned by tests 2 and 4; activation keeps its single primary.
- Best in class overall: **4** — the prototype ported faithfully; real-data polish waits for the walk.

## Modules to upgrade on deploy
`pb_import_kit` (icons + font + version) and `pb_dashboard`; purge `/web/assets/%` per database. pb_home_hub's
test file changed (no version bump needed — tests only).

## Ledger rows added
H22 pb_home_hub pins pb_dashboard · H23 no `openHub` import (hand-written door) · H24 dial-call word boundary ·
H25 `(s)` ban · H26 SVG fills by class · H27 offline OWL harness · H28 headline/sentence repeat · H29 Learn on
an activation tenant · H30 EXIT line never written.

## Deviations (with reasons)
1. **Doors are hand-written** (`door()` + `backDoor()`, the hub_nav `pb_back` shape) instead of importing
   `openHub` — that import needs pb_hub in depends, which the binding non-goal and pb_home_hub's test forbid (H23).
2. **pb_home_hub's test file edited** to the new depends / top-line class / Insights doors (H22).
3. **Headline as two translatable clauses** joined by the `·` separator, not one string; same EN on screen.
4. **Words beyond the table**, each for a state the table did not cover: pills "Not finished" (past month with
   an unfinished run) and "Complete" (stage 5); rose fact "A run does not balance" (→ Pay runs); "Waiting for
   approval" (approve step under way with no named approver); "The X run (N people) is waiting for your
   approval" (no submitter); singulars ("1 day to payday", "1 person", "1 approval"…); "No pay run this
   month"; the Coming-up empty sentence; the "Tet" column label (P1 `note`).
5. **Deltas**: money in percent ("+0.4% vs Aug", |Δ| < 0.5 % → "about the same as"), people absolute
   ("+11 vs Aug", 0 → "about the same as") — the prototype's rule.
6. **Activation mode** keeps one hero element (the anchor appears once) holding only the greeting; the top line
   drops its greeting there so it is not said twice.
7. **The skeleton paints first**: the load is not awaited in `onWillStart`.
8. **Doors chosen**: cut-off → Payroll calendar (pb_comp_ben); payday → Pay Run › Deliver; settlements →
   Lifecycle › Exits; write-ups and interviews → Lifecycle › Hiring; renewals and contract ends → Contracts;
   holiday → Mission Control › Holidays; figures → Insights (the second Insights door pb_home_hub pins).
9. **Run labels**: the hero uses the division label (else the run name); the steps rows use `steps[].run`,
   which P1 fills with the run NAME — the two can differ on screen.
10. **With no payday known** the sentence drops "October is at step N of 5" (the headline already says it, H28),
    so the "step N of 5" link appears only when the headline is the payday form.
11. `dash-kpis` exists only when some month in the 12 has a run (the panel shows its empty sentence otherwise).

## Open questions for P3
- Cards row (People / pay runs / Hiring / Keep learning / Pay schemes) — payload is ready; the runs card would
  also host the per-run "done of slips" the hero leaves out.
- Vietnamese: ~130 new msgids in the JS and template (P3 `.po`); "bn / M / K" units are `_t()` too.
- Learn: the "Welcome — Home and Pulse" lesson still describes the old strip and KPI band; on a tenant with no
  pay run only `dash-hero` exists (H29). `dash-formula` moves to the Pay schemes card.
- Steps rows: show the division label (like the hero) — needs `steps[].run` to carry it, or the browser to look
  it up in `runs`.
- "Email, EN + VI" / "Email in English and Vietnamese" are fixed words from the table, not data; should they read
  the delivery settings?
- Next month's cut-off when this month's has passed (P1 open question still open).
