# RIZE P10 — pb_contract_lifecycle: contracts & interns decided on time

Read FIRST: `docs/handovers/RIZE_LEDGER.md` (ruling D1!) + phase-log P0–P9 (code wins).
Design doc: `docs/design/rize-hrms-blueprint.html` §12.

## Scope
ONE new module `pb_contract_lifecycle` (depends: pb_lifecycle, pb_probation,
pb_people_advanced):
1. First-class intern/contractor typing (adopt standard `employee_type`, seed an Intern
   contract type, migrate the fragile analytics string-match).
2. `pb.contract.review` — the two-month-early decision workflow: terminate / extend /
   convert, with escalating reminders.
3. Extension requests (reason + manager approval window) → NEW linked contract (D1).
4. Conversion to full-time → probation-style evaluation (P5 engine, kind 'conversion').
5. **Contracts & interns lens** on the Lifecycle hub.

### Binding NON-goals
- No edits to the contract drawer (pb_contracts) source; no wage/structure logic; no
  vendor/agency billing (that was scoped out of the blueprint's Payobook side — the
  contract DB here is EMPLOYEE contracts/interns, not supplier contracts).

## Verified plumbing facts (do NOT re-derive)
- Contract lifecycle exists: `pb_contracts/models/pb_contracts.py:11-20` (STATE_LABEL,
  NEXT action map, LIFECYCLE verbs); 30-day expiry KPI `:51-53`; per-row days_to_expiry
  `:81,89`.
- Renewal prefill canon: `pb_people_advanced/models/people_wizards.py:110-124`
  `get_defaults(renew_from=...)` copies wage/struct/calendar — the extension flow builds
  the NEW contract through this (or its underlying create), copying terms, new dates,
  closing the old contract at its end date. Ruling D1: extension/conversion = NEW linked
  contract; NEVER in-place date_end stretch.
- Typing: standard `hr.employee.employee_type` selection exists and is UNUSED by custom
  code (`hr/models/hr_employee_base.py:64`); `hr.contract.type` seed rows are only
  Employee/Worker/Subcontractor (`om_hr_payroll/data/hr_contract_type.xml`) — ADD 'Intern'
  (+ 'Fixed-term contractor' if absent) via THIS module's data.
- Fragile string-match to migrate: `pb_hr_payroll_analytics/models/hr_analytics_headcount.py:156-158`
  counts contractors via `'contractor' in contract.type_id.name.lower()` — replace with
  employee_type-based counting via a SMALL patch in that module (additive-safe: keep the
  string-match as fallback when employee_type unset). This is the one edit outside the
  new module; stage it separately.
- P5 review engine: `pb.probation.review` with `kind` field ('conversion' reserved for
  us) — entry method per P5 report. Conversion flow creates kind='conversion' review;
  on PASS → run the conversion (new permanent contract via prefill, employee_type →
  'employee', congratulation letter); on FAIL → decision back to HR (no auto-exit).
- Journey engine for reminders/escalations (P0 cron inherit) + letters.
- Backfill: employees whose contract type/name contains intern/contractor → set
  employee_type accordingly (log counts; never override an explicitly set value).
- Lens registry pb_lifecycle_lenses (P0 report). Palette 3000s.

## Architecture

### Models
**`pb.contract.review`** — mail.thread. contract_id required, employee_id related stored,
end_date related snapshot, lead_days Integer (from config
`pb_contract_lifecycle.lead_days` default 60), trigger_date computed (end − lead),
state Selection `[('upcoming','Waiting'),('decide','Decision needed'),
('extension','Extension requested'),('conversion','Evaluation running'),
('done','Decided'),('lapsed','Ended undecided')]`, decision Selection
terminate/extend/convert, decided_by/at, new_contract_id, review_id (P5, for
conversion), escalation stamps, company_id.
Daily cron: contracts with an end date within lead_days and no open review → create
(state decide) + notify HR + manager (both), listing the three options in plain English.
Escalation: undecided with < lead/2 days → escalate to lifecycle managers; < 7 days →
daily nag. Idempotent stamps.

**Extension flow** — `pb.contract.extension` TransientModel-ish? NO — model with trail:
review_id, reason Text (HR captures the offline reason), months Integer, approval via
biz.approval.chain.mixin (manager step within a window: `approve_by` Date = today +
config days default 5; overdue → escalate); on approval → build the NEW contract
(prefill from old: same wage/struct/calendar, date_start = old end +1 day, date_end =
+months), old contract left to end naturally (its own state flow), review done
(decision extend, new_contract_id), letter optional (extension letter via P0 'custom'
template seeded here), employee notified.

**Conversion flow** — on choosing convert: create P5 review kind='conversion' (its
nomination/feedback/verdict machine runs as probation does); listen on its verdict
(extension hook per P5 report — or a method the P5 wizard calls): PASS → new PERMANENT
contract (prefill, no end date), employee_type 'employee', congrats letter, review done
(decision convert); FAIL → review back to 'decide' with a note (HR chooses terminate or
extend explicitly).

**Terminate decision** → guidance panel: opens a P4 offboarding case anchored at the
contract end date (explicit button, idempotent), review done.

### Typing
- Data: Intern contract type; backfill server action + post_init (per ledger hook gotcha,
  migration too) setting employee_type from contract-type names (intern→intern,
  contractor/subcontractor→contractor); the analytics patch (fallback-safe) in
  pb_hr_payroll_analytics.
- The onboarding arrival path (P1 whitelist) may carry Zoho employee types — extend P1's
  normaliser mapping via inherit IF the field arrives (probe; document).

### Contracts & interns lens (Lifecycle hub, palette 3000s)
Facade `pb.contractlife` get_board(): rows = employees with end-dated contracts + all
interns/contractors {employee, type chip (intern/contractor/fixed-term), start, end,
days left (red < lead/2), review state, decision chip, manager}; kpis (ending in 60
days, decisions overdue, evaluations running, converted this year); facets (type,
month, department, state). Row → decision drawer: contract summary (read-only pulls of
wage-free terms — dates/job/dept only, no money on this board), the three decision
buttons with plain-English consequence copy, extension form inline, conversion progress
link, decision history. ⌘K deep links ("Contracts ending soon", "Decisions needed").

## Safety rails
- NEVER write date_end/wage on an existing contract (D1); the ONLY writes to old
  contracts are their natural state transitions.
- New-contract creation copies terms verbatim except dates — show a confirm summary
  first (wage shown THERE is fine — it's the wizard, not the board).
- Analytics patch: additive, fallback-kept, staged as its own commit.
- Test on disposable test employees + test contracts; do NOT create reviews for real
  demo population en masse — cron scoped correctly will only pick genuinely-ending
  contracts; verify the demo world doesn't have thousands ending soon BEFORE enabling
  the cron (if it does, add a config kill-switch default ON but log-only for the first
  run, then enable after reviewing counts — document).
T-cases below assume this check.
- Deploy `-i pb_contract_lifecycle -u pb_hr_payroll_analytics`.

## Numbered test cases
T1. Deploy clean; Intern contract type exists; backfill counts logged and sane.
T2. Cron dry-run/count check documented; create a test contract ending in 45 days →
    review auto-created (decide), HR + manager mails queued; rerun → no dupe.
T3. Lens board: the test row shows days-left, type chips right; drawer shows the three
    options with consequence copy; light+dark screenshots.
T4. Extend: reason + 6 months → manager approval (stepper) → NEW contract created
    (start = old end +1, correct copied terms — verify wage/struct/calendar equal),
    old contract untouched (dates unchanged), review done, letter + employee mail
    queued; D1 compliance shown explicitly (old contract's date_end unchanged in DB).
T5. Approval window: leave a second extension pending past approve_by → escalation mail
    once.
T6. Convert: triggers a P5 kind='conversion' review; run its flow quickly (nominate 3,
    submit forms, 1:1, PASS) → permanent contract created (no end date), employee_type
    'employee', congrats letter; review done.
T7. Conversion FAIL path → review back to decide with note; nothing auto-created.
T8. Terminate → button opens P4 offboarding case anchored at contract end; idempotent.
T9. Analytics: contractor count now driven by employee_type (set a test employee's type
    → count moves; unset-type fallback still string-matches — verify both).
T10. Intern arriving via P1 payload with a type field → employee_type mapped (or probe
    documented as absent).
T11. Lapsed guard: a review left undecided past end date → state lapsed + HR alert.
T12. White-label grep zero; plain English (the decision drawer copy especially).
T13. Regressions: contract drawer (pb_contracts) untouched and working; P5 probation
    flow unaffected; P4 fine.
T14. Clean up; report cron scoping counts + kill-switch state.

## Deliverables / report back
Commits (module + analytics patch separate), per-test results, deploy EXIT, deviations,
gotchas, the conversion hook wiring with P5, lens/palette ids, backfill counts.
