# RIZE Wave 2 — Phase E3: `pb_training` budget claims, analytics, report pack, certificates

E1 and E2 are live. E3 closes Training: the employee's training allowance
and cost claim (invoice + certificate → HR validates → the money rides the
existing one-off pay-run door), the Training lens on Insights with a
weekly / monthly pack by email, and certificates filed in the vault. Bump
`pb_training` to `19.0.1.2.0`; the claim route ⇒ a migration.

Read first: `RIZE_LEDGER.md` (all), `RIZE_W2_HANDOVER.md` A/B/C5, the E1
and E2 handovers' §1 and **their report rows in the ledger's Wave 2 table**,
then this file. Read the E1/E2 code first.

## 0. Scope and non-goals
**In scope:** `pb.training.allowance` (per company, per year, per person
optional override), `pb.training.claim` with uploads and a Matrix route (HR
lead validates), approved claim → a `pb.incentive` row of a new kind
`training` ready for the awards queue (the ONE money door, A2 rule),
`/my/training/claims`, certificates (E-Learning certification PDFs and
uploaded ones) filed into the employee vault, the **Training** lens on the
Insights hub (completion ratio, performance ratio, overdue, by date range,
by department / course / reason) with XLSX, a weekly / monthly report pack
by mail (cron, switch OFF), ⌘K 3960/3970.
**Non-goals:** any new way to write a payslip; editing `pb_comp_ben`,
`pb_employee_vault`, `pb_probation`; e-invoicing.

## 1. Verified facts
- **The money door** (`pb_comp_ben/models/oneoff_feed.py`): `pb.oneoff.feed
  .preview_for_run(run_id, incentive_ids=None, month=None)` (:148),
  `queue_for_run(incentive_ids, run_id, source=None)` (:259 — idempotent,
  SET not add), `mark_paid_for_run(run_id)` (:480), gated on the run being
  draft/officer and its scheme carrying the input component
  `pb_comp_ben.incentive_code` (default `INCENTV`, R72). The feed picks
  `pb.incentive` rows (`incentive.py:39`: `employee_id, kind
  (INCENTIVE_KINDS), amount, currency_id, period_month, state
  (INCENTIVE_STATES draft/submitted/approved/refused)`, fulfilment column;
  `action_approve` :117; its own route is `pay_head` — `incentive_approval.py:95`).
  `INCENTIVE_KINDS` = bonus / incentive / spot (`comp_common.py:88`).
  **Add `('training', 'Training reimbursement')` via `selection_add` on
  `pb.incentive.kind` from `pb_training`** (with `ondelete='set default'`),
  and create the incentive already `approved` when the CLAIM route
  approves — the claim IS the approval (sheet: "HR validates and approves
  reimbursement"); the pay head still queues it into a run from the
  Awards lens exactly like an award, and R81 (award month vs run month)
  applies: `period_month` = the claim's approval month.
- **Vault:** `pb.employee.document` create is gated (`employee_document.py:
  114-135`): system fields need `_vault_sys_write` / superuser; a non-HR
  self-serve create must bind an attachment the caller owns. File
  certificates as the system from the completion path (E2's `done`
  transition) with category by code `CERT` (`document_category_data.xml:19`),
  name "<course> — certificate", `expiry_date` empty; idempotent per
  (employee, course, attempt).
- **Certificate PDF:** `/survey/<int:survey_id>/get_certification` (auth
  user) renders the stock certification report; to FILE it, render the
  same report server-side (`survey.action_survey_user_input_certification`
  or whatever xmlid the route uses — read `survey/controllers/main.py:704-730`)
  as the caller (never `report.sudo()`, R89) and attach.
- **XLSX** precedent `pb_budget/models/budget_export.py:73 _xlsx(board)`;
  monthly mail precedent `pb_rnr/models/digest.py:222 _cron_monthly_digest`
  (a `interval_type` monthly cron that misses its tick — read :228-270 for
  the daily-check-and-stamp shape and the log-only-when-off shape R54).
- **Insights lens:** `INSIGHTS_LENSES`, Budget 20, Hiring 30 (A3) —
  **Training = 40**. Analytics reads are company-scoped and never sudo.
- **Assignment API:** from the E2 report (`state`, `score`, `completed_on`,
  `reason`, `due_date`, `schedule_id`).
- **Actors:** learner ess1.demo (E1/E2), HR = validator, `hr_lead` seat on
  company 5 borrowed and returned (R123), a pay run in draft on company 5
  whose scheme carries `INCENTV` (P7 left runs 791/1396/1525 mutated with
  INCENTV — verify one is still draft/officer; if none, the queue test
  proves `preview_for_run` says why and stops there, D9).

## 2. Models and rules
- **`pb.training.allowance`**: `company_id, year, amount, currency_id`
  (company default) + optional per-employee override rows
  (`employee_id`); the facade answers `allowance_for(employee, year)` =
  override or company row or 0 (then "No training allowance set for
  2026" on the page).
- **`pb.training.claim`**: `employee_id, assignment_id` (optional — an
  approved external course), `course_name, provider, amount, currency_id,
  paid_on, invoice_attachment_id, certificate_attachment_id` (both
  required to submit), `note, state` draft → submitted → approved |
  refused → paid (mirrors the incentive's fulfilment), `incentive_id`,
  `year` (of `paid_on`), `company_id`. Refuses submit when amount >
  remaining allowance (remaining = allowance − approved claims this year)
  unless the HR lead ticks "allow over the allowance" (logged). Route
  `training_claim` = `role_step(_('HR lead'), 'hr_lead')`; facts: amount
  (unit = currency), remaining allowance, course name; revision = amount +
  attachments. `_approval_apply`: create the `pb.incentive` (kind
  `training`, approved, `period_month` = today, note "Training claim
  #N"), link it, mail the employee; all under savepoint legs (R131).
  `paid` when the incentive's fulfilment says paid (a small cron or the
  same `mark_paid_for_run` hook — read how P7 flips awards to Paid on
  final approval, R70, and mirror on the claim).
- **Certificates:** on E2's `done` with a passed test: file the PDF into
  the vault (as above); on a claim approval: file the uploaded certificate.
  `/my/training` course tile: "Certificate" link → the vault document
  (portal already lists vault documents under `/my/documents` —
  `pb_me_portal`; link there).
- **Analytics facade `pb.training.analytics`** (range on `assigned_on`,
  optional department / course / reason): completion ratio (done / all
  non-excused), performance ratio (passed tests / taken; mean score),
  overdue count and mean days overdue, by department, by course, by
  reason; a weekly trend (assigned vs done per ISO week). `export_xlsx`.
  Empty range → sentence (R27).
- **Report pack:** `pb_training.report_pack` **0** (OFF), `report_pack_period`
  weekly|monthly, `report_pack_email` (the training manager's address;
  test value `training.pack@example.com`); daily cron checks the period
  boundary (stamp `report_pack_last`), builds the XLSX + a short HTML
  summary, sends one mail; when OFF logs what it would have sent (R54).
- Screens: `/my/training/claims` (allowance remaining, my claims with
  states, "Claim a course cost" form with two uploads); HR lens "Claims"
  tab (queue, allowance panel per company/year); Insights → Training lens
  (tiles, three tables, trend bars, "Download Excel"); ⌘K
  `training_claims` 3960 ("Training claims"), `training_numbers` 3970
  ("Training numbers", Insights).
- Switches: `pb_training.report_pack` 0, `report_pack_period` monthly,
  `report_pack_email` (test), `pb_training.claim_over_allowance` 0.

## 3. Tests
T1  Unit + gates; migration lays `training_claim` once.
T2  Allowance: company 5, 2026, 5,000,000 ₫; `allowance_for` = that; an
    override 8,000,000 for ess1.demo wins.
T3  Claim as ess1.demo: submit without a certificate → refused with a
    sentence; with both files (pdf) → submitted; HR lead sees it with the
    facts (amount VND, remaining); approve → `pb.incentive` kind
    `training`, approved, linked; employee mailed; remaining allowance
    drops; a second claim over the remaining → refused; with
    `claim_over_allowance=1` → allowed and logged.
T4  Money door: `preview_for_run(run, [incentive])` accepts it on a
    draft run with `INCENTV`; `queue_for_run` puts the amount on the
    payslip line (read the input value); run twice → same value; a run
    without the component → the preview names the scheme (no queue).
    Claim `paid` after the P7 paid-flip (or documented if no such run).
T5  Certificates: pass the E1 test as ess1.demo → a vault document (CERT)
    exists once (repeat the completion → still one); the claim's
    certificate filed on approval; `/my/training` shows the link.
T6  Analytics: seed 6 assignments across 2 departments with mixed states;
    the facade's ratios equal a Python recomputation; department and
    course splits sum to the total; XLSX re-read by openpyxl matches a
    spot value; empty range → sentence.
T7  Report pack: with the switch 0 the cron logs only; with 1 + monthly
    and the stamp cleared → one mail to the test address with the XLSX
    attached; run again the same period → none.
T8  Screens light + dark (`RIZE/w2_e3_*.png`): claims page at 390 px, HR
    Claims tab, Insights Training lens; no console errors.
T9  ⌘K 3960/3970; Insights lens `training` at 40; deploy `19.0.1.2.0`,
    crons active, log clean.
T10 Reverts (seat, groups, passwords), mails cancelled; data stays named
    DEMO (ledger rule 9); the queued payslip value is REPORTED to the owner (a real
    pay run was touched: which run, which person, which amount).

## 4. Report back
As E2, plus the claim → incentive → run chain in words for the closeout,
the vault filing rule, what the pack contains, owner items (allowance
amounts, the pack address and switch, the kind label).

## Demo-data rule (owner, 2026-09-16 — D18, ledger binding rule 9)
Every demo record this phase creates on `payobook` is KEPT for future demos, so it
must NOT carry the customer name ("RIZE"/"Rize") anywhere a viewer can see — names,
subjects, notes, chatter, logins, emails, job/department titles, letter bodies. Name
them starting with **DEMO** ("DEMO Town hall"), logins `demo.<role>@example.com`.
Register every one at creation, in the fixture code:
`seed = self.env.get('pb.demo.seed'); if seed is not None: seed.register(records, label)`
(the guard keeps `pb_demo_seed` optional on tenants). The report carries a "Demo
records" table (model, ids, label) and the register count. Any "named RIZE W2" wording
left in this file is superseded by this section.
