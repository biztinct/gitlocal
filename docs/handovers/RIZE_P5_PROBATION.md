# RIZE P5 — pb_probation: the probation engine

Read FIRST: `docs/handovers/RIZE_LEDGER.md` + phase-log entries P0–P4 (code wins; reconcile
by reading it). Design doc: `docs/design/rize-hrms-blueprint.html` §06.

## Scope
ONE new module `pb_probation` (depends: pb_lifecycle, pb_onboarding; uses pb_contracts
facts, pb_offboarding for fail-path):
1. Per-country probation policy → auto trial-end date on the contract (in-place write is
   ALLOWED here — ruling D1 carve-out).
2. `probation_state` on every employee (in probation / passed / extended / failed / n-a)
   + install backfill.
3. The evaluation machine: auto-trigger at lead time, peer nomination (3–5), peer feedback
   via P0 token forms, deadline alerts + 1-day extension, consolidated report, manager 1:1,
   verdict pass/extend/fail with letters and status updates.
4. Role-based training gate (the "Agronomist" requirement, fully configurable).
5. **Probation lens** on the Lifecycle hub.
6. Probation card on `/my/journey` (additive).

### Binding NON-goals
- No PIP (P6). No conversion evaluations yet (P10 reuses this engine via the `kind` field —
  ship the field, not the flow). No Zoho outbound (probation truth stays here, D8).
- Do NOT create new contracts or touch wage data; the ONLY contract write is
  `trial_date_end` (D1 carve-out).

## Verified plumbing facts (do NOT re-derive)
- `hr.contract.trial_date_end` exists and is surfaced in the contract drawer
  (`pb_contracts/models/pb_contract_360.py:76`); write in place.
- Employee current contract: follow how `pb_people`/`pb_contracts` resolve it (read the
  code); joining date = `first_contract_date` fallback chain (`pb_people/models/pb_people.py:22-30`).
- P0 gives: `pb.feedback.request` (token forms, window, extend), `pb.employee.checkin`
  (kind probation), letters (`probation_pass/extend/fail` seeded templates), reminder cron
  to extend, journey cases (probation CAN be a case_type but the review machine below is
  its own model — link case optional).
- P3 gives: buddy eligibility currently reads trial_date_end directly — AFTER this phase
  it should read `probation_state`; make that switch here via a small additive inherit in
  pb_probation (do not edit pb_onboarding source; override the eligibility helper).
  Also: 30-60-90 checkins already exist (P3) — consume their notes/red flags in the
  consolidated report.
- Performance rating: `wfp_performance_rating` on hr.employee
  (`pb_hr_workforce_planning/models/hr_employee_wfp.py:10-40`, HR-gated, 1–5). On PASS
  write it from the average peer rating (rounded, clamp 1–5) — probe the field exists
  (`'wfp_performance_rating' in env['hr.employee']._fields`) since pb_hr_workforce_planning
  may not be a dependency; write via sudo-with-check or skip with a log. Do NOT touch
  `pb_performance_rating` (demo duplicate).
- Alerts canon: P0 reminder cron (inherit to add probation nudges) — 15-day + 5-day HR
  reminders before trial end, pending-nomination and pending-feedback alerts, and the
  "2 hours before deadline" alert (run the cron hourly? NO — add a SECOND lightweight
  hourly cron just for the deadline-day alerts, idempotent-stamped).
- Palette ranges used so far: per ledger phase log (P0 2100s … P4 2400s) → use 2500s.

## Architecture

### Models
**`pb.probation.policy`** — country_id (unique-ish per company), duration_months Integer
default 2, evaluation_lead_days default 21, feedback_window_days default 3,
extension_grace_days default 1, default_extension_months default 1, company_id, active.
Seed: VN 2 months, IN 3, SG 3, ID 3 (adjustable).

**hr.employee extension** — `pb_probation_state` Selection
`[('in_probation','In probation'),('passed','Passed'),('extended','Extended'),
('failed','Not passed'),('na','Not applicable')]` default computed at create (has future
trial end → in_probation else passed), tracked, HR-writable. INSTALL BACKFILL
(post_init_hook + migration per ledger gotcha): trial_date_end in future → in_probation;
past or unset → passed; contractors/interns (employee_type set to those) → na.
Onboarding case open (inherit) → if policy exists and contract present, set
trial_date_end = join date + duration (only if unset), state in_probation.

**`pb.probation.review`** — mail.thread. employee_id required, kind Selection
`[('probation','Probation'),('conversion','Conversion')]` default probation (P10 reuses),
round Integer default 1, trial_end Date (snapshot), manager_user_id (from employee
parent), state Selection
`[('scheduled','Scheduled'),('nomination','Peers being chosen'),
('feedback','Feedback running'),('consolidation','Consolidating'),
('one_on_one','Manager 1:1'),('verdict','Awaiting decision'),('closed','Closed')]`,
nominee_ids m2m hr.employee (constraint 3–5 at confirm), feedback_request_ids o2m-ish
(link by review_id added on pb.feedback.request via inherit — additive field
`probation_review_id`), feedback_deadline Date, consolidated_html Html (generated:
per-question averages + every comment + 30-60-90 check-in notes + red flags),
one_on_one_checkin_id, verdict Selection pass/extend/fail, strengths Text,
improvements Text, extension_months Integer, avg_rating Float, company_id.
Flow methods (each guarded, chattered):
- `action_start_nomination()` → email manager (deep link to the lens dialog).
- `action_confirm_nominees()` → create+send peer feedback requests (P0, kind
  probation_peer, seeded question set: 4 ratings + 2 comments aligned to policy wording),
  deadline = today + policy window; state feedback.
- `action_extend_deadline()` (once, +1 day per policy grace).
- `action_consolidate()` (auto when all submitted OR deadline passed): build
  consolidated_html, email manager the review link, create the 1:1 checkin (2-day due),
  state one_on_one → verdict after checkin done.
- `action_verdict()` from a guided dialog: writes verdict+strengths+improvements; then:
  PASS → employee passed, congrats letter (P0 template) + mail, write
  wfp_performance_rating (probe), close; EXTEND → trial_date_end += extension_months
  (in-place, D1), employee extended, extend letter listing improvement areas, schedule
  next round review (round+1) at new lead time, close; FAIL → employee failed, fail
  letter, notify HR with "Start exit" action button (opens P4 offboarding case — do NOT
  auto-open), close.

**Training gate** — `pb.training.track`: name, job_ids m2m hr.job, item_ids
(`pb.training.item`: name, description, required Boolean, sequence), active, company_id.
`pb.training.status`: employee_id, item_id, state todo/done, score Float, done_at,
company_id. Auto-created for matching jobs at onboarding-case open (inherit) AND at
review create (idempotent). Verdict PASS is BLOCKED (plain-English UserError listing
items) while required items aren't done. Lens shows the gate chip. Seed one example
track "Agronomist essentials" (3 items) bound to job name match 'Agronomist' if such a
job exists, else seed unbound (active but no jobs) as the example.

### Trigger crons
- Daily (inherit P0 cron or own): employees in_probation/extended whose
  `trial_end − lead_days ≤ today` with no open review → create review (state
  nomination) + manager email; 15-day and 5-day HR reminders (idempotent activities).
- Hourly light cron: reviews in feedback state with deadline today → "2 hours left"
  alert to pending respondents + manager (stamp `deadline_alerted` Boolean).

### Probation lens (Lifecycle hub, soft registry, ⌘K 2500s)
Facade `pb.probation` get_board(): rows = in-probation/extended employees {name, DOJ,
trial end, days left (red <7), review state chip, nominations n, feedback x/y submitted,
training gate ok/pending, 30-60-90 red flags, round}; kpis (in probation, reviews
running, verdicts due, overdue feedback); facets (country, department, state).
Dialogs: nominate peers (manager/HR; eligibility = not the employee, same company;
show department + tenure), consolidated report viewer (rich panel), verdict wizard
(consolidated view → strengths/improvements → verdict + extension months → confirm
shows exactly what will happen in plain English).
Row → employee probation drawer: timeline (DOJ → checkins → review events → trial end).

### Portal (additive)
`/my/journey` probation card via additive controller inherit (P3 route): status chip,
trial end date, days left, "what happens next" copy. Peer feedback pages are P0 token
pages (already styled).

## Safety rails
- Backfill runs ONCE, logged, and NEVER downgrades an explicit existing state.
- No mails to real staff: test with @example.com employees; peers can be demo employees
  but send their feedback requests to example.com overrides (set respondent_email).
- Verdict FAIL never auto-opens exit — explicit HR button only.
- Deploy `-i pb_probation -u pb_lifecycle` only if you added the additive fields there
  (probation_review_id on feedback request lives IN pb_probation via _inherit — no
  pb_lifecycle edit; prefer that).

## Numbered test cases
T1. Deploy clean; backfill ran (spot-check: an old demo employee = passed; a test
    employee with future trial end = in_probation; counts logged).
T2. New onboarding case (P3 flow) for test employee, policy VN → trial_date_end set =
    join + 2 months; lens shows them.
T3. Force the daily trigger with trial_end 20 days out → review auto-created (nomination),
    manager mail queued; re-run → no duplicate.
T4. Nominate 2 peers → blocked (need 3–5, friendly error); nominate 3 → feedback requests
    sent (mail.mail rows), deadline = +3 working-day window per policy.
T5. Submit 2 of 3 peer forms via token pages; deadline-day hourly cron → "2 hours" alert
    queued once; extend deadline (+1 day) works once, refuses twice.
T6. Third form in → auto-consolidation: consolidated_html contains averages + comments +
    a 30-60-90 red-flag note (create one first); manager mail; 1:1 checkin created.
T7. Mark 1:1 done → state verdict; verdict wizard PASS → employee passed, congrats letter
    generated + vault-filed + mail queued; wfp rating written (or skip logged if field
    absent); review closed.
T8. Second test employee: verdict EXTEND +1 month → trial_date_end moved in place,
    state extended, letter lists improvement areas, round-2 review scheduled.
T9. Third: verdict FAIL → state failed, fail letter, HR notification with Start-exit
    action; pressing it opens the P4 offboarding case.
T10. Training gate: bind the seeded track to the test job, leave one required item todo →
    PASS verdict blocked with the item named; complete it → pass proceeds.
T11. Buddy eligibility (P3) now reads probation_state: an in_probation employee is
    excluded as buddy with the right reason chip.
T12. `/my/journey` shows the probation card for the in-probation test user; light+dark
    screenshots of lens + card.
T13. 15-day/5-day HR reminders idempotent (run twice → one activity each).
T14. White-label grep zero; plain English; verdict wizard copy reads like the blueprint.
T15. Regressions: P0–P4 lenses load; an offboarding case still works end to end.
T16. Clean up test data; report param states + anything left.

## Deliverables / report back
Commits, per-test results, deploy EXIT, deviations, ledger gotchas, the review-model API
(P10 conversion reuse: kind field + entry method), lens/palette ids, and the exact
employee-state field name + values (P6/P10 read it).
