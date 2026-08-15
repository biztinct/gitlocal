# LEARNOS Phase 3 — First-run activation journey (DRAFT until Phase 2 merges; build on top of it)

Read both ledgers + accepted 1a/1b/2 reports. Scope: pb_dashboard (checklist), pb_learn
(welcome moment + any new chrome keys via author source), pb_tenants (one small provisioning
fix). No deploy, no commit.

## Why
A brand-new tenant admin should land on a dashboard that walks them from nothing to their
first real payroll — the Stripe-style activation checklist — with each step launching the
matching scenario mode (Watch → open → Try → Do). This replaces Phase 0's interim setup panel.

## Design (binding)

### The checklist (pb_dashboard)
Replaces the Phase 0 `.pbd-setup` panel when the tenant is empty OR partially set up; fully
disappears once activation is complete.

Items (key, completion predicate — all server-side in `get_dashboard_data`, cheap counts,
every learn read behind `'learn.progress' in env` registry guards so pb_dashboard keeps NO
hard pb_learn dependency):
1. `meet` — "Meet Payobook (2-minute tour)" → Watch `sc_welcome`.
   Done when: learn.progress own-row `scenario:sc_welcome` state=done (guard: if pb_learn
   absent, hide this item).
2. `employee` — "Add your first employee" → open `pb_people.action_pb_people`.
   Done when: active hr.employee count > 1 (the template admin row doesn't count — ledger).
3. `import` — "Bring in your payroll Excel" → open `pb_import.action_pb_import`.
   Done when: hr.contract count > 0 OR an import batch record exists (resolve the pb_import
   model name in code; use registry guard).
4. `practice` — "Run a practice payroll (nothing is real)" → Journey deep-link
   `{scenario: 'sc_payrun', mode: 'try'}`.
   Done when: learn.progress `scenario:sc_payrun` done (any mode).
5. `real` — "Run your first real payroll" → Do-mode `sc_payrun` (service start via the
   coach/scenario deep-link action with mode 'do').
   Done when: hr.payslip.run count > 0.

Visibility rule: show the checklist when `payslip runs == 0` (activation incomplete);
otherwise never. Items render with state (todo/done), done items get the check animation
(CSS only, no libraries, no emoji; Lucide check icon). The FIRST incomplete item is visually
"next" (rail accent + button primary; others ghost). Completed-all is unreachable while
visible (item 5 completion hides the panel) — no celebration screen needed here; the Do-mode
completion card is the celebration.

KPI cards below stay (honest zeros); ALSO fix the Phase-0 leftover: Latest-pay-run and
Formula cards render an em-dash placeholder instead of red `ring(0)` when their counts are
zero (same `t-if` idiom as the Company-overview ring).

### The welcome moment (pb_learn)
Extend `static/src/coach/first_login.js`: on first backend login (existing once-per-login_date
machinery + localStorage), if the DB is NOT the demo world, show a small centred welcome card
(reuse coach card visual language, T()/tx() strings authored in data.js I18N): "Welcome to
Payobook — want the 2-minute tour?" [Watch the tour → sc_welcome watch] [Later]. Never shown
again after either choice (localStorage key). Demo world keeps its existing behaviour
untouched. New chrome keys go through the author source + generator (Phase 2 register rules
apply to their copy — write them novice-simple, EN+VI).

### Provisioning currency fix (pb_tenants)
`_step_configure` (pb_tenants/models/service.py:464-494): after renaming company id 1, set
`currency_id` from the tenant's country (`res.country.currency_id`) when provided; log it in
the provisioning trail. Fixes "$0" on VN tenants. Guard: only if the country has a currency
and it differs. (Template stays USD; clones get the right money sign from day one.)

## Non-goals (binding)
- No changes to scenario engine, content models, analytics. No AI. No new DB models/fields.
- The checklist NEVER shows fabricated numbers or fake progress; every predicate is a real
  count with a registry guard. pb_dashboard keeps no hard dependency on pb_learn/pb_import.
- Do not touch abm/acme live state.

## Tests (numbered)
1. py_compile / node --check / XML parse all changed files; generator + --check + contract +
   jargon lint green (new chrome keys obey the register).
2. Server logic: extend/author unit tests (runnable at deploy) for the five predicates —
   notably employee>1 excludes the admin row, and every pb_learn/pb_import read is
   registry-guarded (simulate absence by env-without-model checks in test).
3. Grep-proofs: no `ring(0)` path reachable on empty (structural: the two new t-ifs); no
   hard import of pb_learn/pb_import names in pb_dashboard python beyond guarded strings.
4. pb_tenants: unit-style test of the currency mapping decision function (pure), + note that
   the live provisioning path is deploy-verified only.
5. Report: screenshot-script list for the deploy-time Chrome pass (empty template clone:
   checklist renders, next-item accent, each button opens the right surface; after faking
   item completion via SQL/learn.progress the states flip; apex: checklist absent).

## Report back
Per-file summary; predicate implementations verbatim; the welcome-card copy EN+VI; deviations;
ledger candidates.

## Kickoff
"Implement docs/handovers/LEARNOS_PHASE3_HANDOVER.md exactly. Read it and both ledgers first.
Local-only; no deploy, no commit; leave the tree for review."
