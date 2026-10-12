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
| H11 | 2026-10-12 | `hr.employee` has NO `bank_account_id` on this build: the bank lives on the Many2many `bank_account_ids` (relation `employee_bank_account_rel`, `groups=hr.group_hr_user`). | Home reads the relation name/columns from the field metadata and counts in SQL (`_home_bank_link`, `_home_bank_count`); falls back to `bank_account_id` if a build has it. |
| H12 | 2026-10-12 | Inbox cards for leave carry `process_key='leave'` but `area='time'` — an area shared with overtime, timesheet, correction and unlock. | `leave_to_approve` counts cards by `process_key == 'leave'`, not by area. |
| H13 | 2026-10-12 | Settlement "to check" is not a state: it is the stored boolean `hr.full.final.settlement.pb_to_check` (draft/returned with no compute issue). | One `search_count` on `pb_to_check = True` for the companies; 0 when the field is absent. |
| H14 | 2026-10-12 | The payroll officer group has no read access to `hr.contract`, so the People section raises AccessError for such a reader. | Section falls back to `None` (card hidden); AccessError is logged at debug, other errors at warning with a trace. P3 may decide to show the employee-only figures. |
| H15 | 2026-10-12 | `learn.runtime.next_best()` returns `{}` unless its feature flag is on (p0clone: off), and it carries no title or minutes. | `learn` is `None` then; title/minutes come from `learn.content.station(key)` (`name`, `duration_min`) or `mission(key)`. |
| H16 | 2026-10-12 | `pb.hiring.interview.feedback_late` is a non-stored Integer compute (number of late write-ups per interview). | Bounded scan: last 42 days, ≤ 500 interviews, states scheduled/done, summed in Python. |
| H17 | 2026-10-12 | `assertLogs` captures nothing for a module logger under the platform's test logging, although the line prints. | Patch the module's `_logger.info` with `wraps=` and assert on its calls. |
| H18 | 2026-10-12 | A pay run's state cannot be written in a test (pb_payruns C18.24 guard). | Test fixtures set it with one `UPDATE hr_payslip_run` after `flush_all()`, then `invalidate_all()`. |
| H19 | 2026-10-12 | Returning `get_dashboard_data()['activation']` from Home would pay the old line-table KPI (2.1 s on payobook). | The checklist block moved unchanged into `pb.dashboard._activation(employees, contracts, runs, optional)`; both payloads call it (test 12). All activation source tests still pin pb_dashboard.py. |
| H20 | 2026-10-12 | `p0clone` holds no payroll at all (0 runs, 0 payslips, 3 employees). | Every P1 test seeds its own rows and asserts on deltas; clone timing (≈35 ms) says nothing about payobook scale (H10). |
| H21 | 2026-10-12 | A pay run may be in another currency than the company's (rize: two schemes, two currencies). | Home money sums only runs whose `pb_currency_id` is empty or the company currency; others still count in `runs` / `people`. Open question for P2. |
| H22 | 2026-10-12 | pb_home_hub's source tests pin pb_dashboard: exact `depends` list, one `!props.embedded` line naming the suppressed class, `this.openInsights()` exactly twice in the template, the hand-written `pb_back` keys = hub_nav's, and no `@pb_hub/` import. They read files from the PARENT of pb_home_hub's path, and one walks every `pb_*` module there — so they cannot run on the clone with two modules staged. | P2 updated them (depends + `pb_import_kit`, class `pbd-top`, the two Insights doors = hero button + month figures) and ran them as a local twin; they run for real at deploy. |
| H23 | 2026-10-12 | The handover's `openHub` import from `@pb_hub/js/hub_nav` would make pb_dashboard depend on the hub family (pb_hub → pb_wf_kit) without declaring it; pb_home_hub's test forbids `@pb_hub/`. | Home keeps the hand-written door (`door()` + `backDoor()`), the same `pb_back` shape, pinned by pb_home_hub's verbatim-keys test. Lens keys: `pb_lens`, Mission Control `pb_shell_lens`. |
| H24 | 2026-10-12 | A substring check for the dial call (`ring(`) also matches `toLocaleString(` / `String(`. | Absence checks on that token use a word boundary (`\bring\(`), built by concatenation. |
| H25 | 2026-10-12 | `test_p9` forbids the text `(s)` anywhere in the JS — an arrow parameter `(s) =>` trips it. | Name arrow parameters `st`, `seg`… never a lone `s` in brackets. |
| H26 | 2026-10-12 | SVG presentation attributes (`fill="var(--x)"`) do not take CSS variables reliably. | Chart and sparkline colours are set by CSS classes (`.pbd-col.is-sel`, `.pbd-spark-line`), never by attribute. |
| H27 | 2026-10-12 | No local Odoo, but the vendored `web/static/lib/owl/owl.js` + jsdom renders the real template and script offline (imports rewritten to a deps object; `_t` stubbed). The global npm cache is root-owned: install with `--cache <scratch>`. | Used in P2 to render 7 payload shapes (rich, empty clone, no money, activation embedded, month focus, load failure, stage None) with zero errors before the clone run. Reuse for P3. |
| H28 | 2026-10-12 | With no payday known the headline already reads "October payroll is at step 1 of 5"; the sentence's "October is at step 1 of 5." then repeated it. | The sentence drops its lead when the headline is the step form. |
| H29 | 2026-10-12 | While `activation.show` the checklist replaces sections 3–5, so only `dash-hero` exists on a tenant with no pay run; the Learn "Welcome — Home and Pulse" lesson also still describes the old strip and KPI band. | P3 rewrites that lesson's words (and decides what its steps point at on a brand-new tenant). |
| H30 | 2026-10-12 | The detached test recipe's `echo EXIT=$? >> /tmp/h1test.log` writes nothing: the log is owned by `odoo` and root may not append to another user's file in sticky `/tmp` (`fs.protected_regular`). The `.done` sentinel still appears. | Read the result from the `odoo.tests.result: 0 failed, 0 error(s)` line, or write EXIT to a root-owned file (`/tmp/h2test.exit`). |
| H31 | 2026-10-12 | Payobook walk: Home said "3,003 people have no bank account". Nobody on payobook has a row in `employee_bank_account_rel`; the account lives on the employee itself (`hr.employee.account_number`, pb_hr_payroll_formula — 4,500 of 4,547 have one), which is what the People screen counts. | `_home_bank_link` = linked bank record OR a non-empty stored `account_number`. Any "has a bank account" test in this product reads both. |
| H32 | 2026-10-12 | Payobook walk: June read 8,879 people paid for 4,486 people — a mid-month advance run and the end-month run (plus demo duplicates) pay the same people, and summing `pb_employee_count` counts them twice. | Months count DISTINCT employees per `date_end` month over the window's payslips (`_home_month_people`, one statement on the payslip_run_id index). Money still sums every run (advance + balance = what was paid). |
| H33 | 2026-10-12 | Payobook walk: the hero said "The It run" — `pb_division_label` title-cases the key `it`. The Pay Runs board names a division from the scheme name (brand and cycle stripped). | `_home_division` = scheme name without "Payobook" and before "—", falling back to the label. |
| H34 | 2026-10-12 | A mid-build P2 copy of pb_dashboard/pb_import_kit reached the live server at 13:24–13:31 (all 4 DBs upgraded to pb_dashboard 2.0.0) — some session deployed from a working tree that held this program's uncommitted files. | Before any deploy, dry-run `rsync -anc` against the live module and read the list: files you did not change mean someone else deployed. Never deploy from a working tree with another stream's uncommitted files in the same module. |
| H35 | 2026-10-12 | A clone test stage dir chowned to `odoo` cannot be re-synced by the ssh user ("failed to set times"). | Restage into a fresh dir (`rm -rf` then `mkdir`) for every run. |
