# HOME — conventions & gotcha ledger

Every handover in this program references this file. Add a row whenever a new gotcha is hit.
Program doc: `HOME_PROGRAM.md`. Design page: https://claude.ai/artifact/6XeVJQr4AARBDoARVS3FgR
(file copy `docs/design/home-dashboard-prototype.html`).

## Standing rules (bind every phase)
- **H-R1 One pay band.** Every Gross / Deductions / Net / Employer-cost figure on Home comes from the stored
  `hr.payslip.run.pb_total_*` roll-ups (pay_role aware). Never sum `hr_payslip_line` by code or category; never
  read `hr_payslip_line` at all from Home (12.5 s planner scan on payobook).
- **H-R2 No new hard dependency.** `pb_dashboard` keeps `depends = [web, om_hr_payroll, pb_hr_payroll_base]`
  (+ `pb_import_kit` for icons/tokens in P2). Every other model is read through `optional(model, fn)` and listed in
  the test's `OPTIONAL_MODELS`; a stored field that another module adds (`pb_total_net`, `pb_balance_ok`…) is read
  only after `'<field>' in Model._fields`. Absent source ⇒ the section is `None` and the browser hides it.
- **H-R3 The server owns facts, the browser owns words.** Payload items carry keys + numbers + dates
  (`{'key': 'runs_to_approve', 'n': 1}`), never sentences; the OWL component maps keys to `_t()` sentences
  (existing test contract, `tests/test_activation.py` docstring). Exception: names that already exist as data
  (run names, people, division labels).
- **H-R4 Company scope everywhere.** Employees/contracts/payslips by `env.companies.ids`; runs through their
  payslips' companies (PA4 / pb_insights `_runs`). No sudo except where the source facade already does it.
- **H-R5 Quiet-board colour rule.** A count is grey at zero and coloured only when a person must act (amber = waiting
  on someone, rose = problem/late, green = good outcome). Deltas are neutral (arrow only). Never a ring at 100 %.
- **H-R6 Never the same number three times.** Each fact has one owner section (program doc §What Home becomes).
- **H-R7 Plain English, screen words, never "Odoo".** "balance" not "reconcile"; "components" not "rules";
  "pay schemes" not "formula engine"; "interview write-ups" not "feedbacks". Units after the number with a space:
  `53.1 bn đ`, `11.8 M đ`. Sentence case on pills and badges.
- **H-R8 Design bar verbatim (binding).** "Extreme WOW, intuitive, out-of-this-world experience, best in class."
  Hero moment = the hero sentence + the chart that is the month picker. Zero dead-ends. Motion with purpose, all
  under `prefers-reduced-motion`. Lucide, locked indigo `#5A4BB0`, no gradients, no emoji, one solid primary per bar.

## Ledger
| # | Date | Gotcha / fact | How to apply |
|---|---|---|---|
| H1 | 2026-10-12 | `pb_dashboard._period_kpis` sums `pl.code='GROSS'` and categories INSCO/COMP (pre-VALUEKIND) — wrong on ABM-style schemes and 2.1 s per month. Tests `test_p3/test_p4` pin that formula. | P1 builds the new payload from stored run totals; P3 deletes `_period_kpis` and the two tests together. |
| H2 | 2026-10-12 | Three "current month" definitions (dashboard latest-with-payslips, `pb.pay.hub` calendar month, pb_payruns `date_end` month). | Hero/steps = the hub's calendar month; chart months = runs grouped by `date_end` month; the in-progress column = the hub's month. |
| H3 | 2026-10-12 | `hr.payslip.run` has no `company_id`; `search([('company_id',…)])` raises. | Scope runs through `hr_payslip.company_id` with one SQL over the window's run ids (pb_insights `_runs`). |
| H4 | 2026-10-12 | The stored `pb_total_*` / `pb_balance_ok` fields come from `pb_payruns`, which pb_dashboard does not depend on. | Read them only after `'pb_total_net' in Run._fields`; otherwise months are built with people counts only and money is `None`. |
| H5 | 2026-10-12 | `tests/test_activation.py:221-228` (test_05) asserts the substring `pb_import` is absent from depends/imports — it would also reject `pb_import_kit`. | P1 narrows the check to the exact module names `pb_learn` and `pb_import` (word boundary); P2 may then add `pb_import_kit`. |
| H6 | 2026-10-12 | Inter is referenced everywhere but never loaded by a backend asset; the prototype's look depends on Inter 600–800. | P2 decision: ship the WOFF2 files under `pb_import_kit/static/fonts/` with `@font-face` (self-hosted, no CDN — pb_insights/pb_explorer manifests forbid CDNs); if the owner prefers the system font, say so in the report. |
| H7 | 2026-10-12 | `ic()` falls back silently to a tick for an unknown Lucide name. | P2: every icon name used on Home is listed in the handover and checked against `import_icons.js` IC keys in a source test. |
| H8 | 2026-10-12 | The hub mounts `PbDashboard` as a lens with `embedded: true` and passes `arrival.focus` (`pb_focus: 'month:YYYY-MM'`). | Keep both props; `pb_focus` selects the chart month on mount. |
| H9 | 2026-10-12 | Learn tours anchor on `data-coach="dash-hero|dash-runpayroll|dash-period|dash-kpis|dash-formula"`. | P2 keeps all five anchors (hero, the primary button, the chart card, the four figures, the Pay schemes card); P3 updates the lesson words. |
| H10 | 2026-10-12 | No local Odoo: tests run on the server clone (`Payobook19v2`, `p0clone` of `payobook_template`, staged addons path first). The clone is SMALL — it cannot prove payobook-scale timing. | P1 logs `timing_ms` per section; Fable reads it on payobook after deploy (target: whole payload < 400 ms warm). |
