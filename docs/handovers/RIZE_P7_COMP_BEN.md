# RIZE P7 — pb_comp_ben: the money gaps

Read FIRST: `docs/handovers/RIZE_LEDGER.md` + phase-log P0–P6 (code wins). Design doc:
`docs/design/rize-hrms-blueprint.html` §08. This phase closes the four payroll gaps:
employee compensation view, incentives + letters, payroll calendar/cut-offs, benefits page
— plus the finance-pack step. The payroll ENGINE and its 3-tier approval are untouched.

## Scope
ONE new module `pb_comp_ben` (depends: pb_lifecycle (letters), pb_me_portal,
om_hr_payroll — check what pb_payruns exposes before depending on it):
1. `pb.employee.comp` versioned package snapshots → portal `/my/compensation`.
2. `pb.incentive` ledger — approval chain, incentive letter, feed into the next pay run
   through the EXISTING "This run only" one-off lane.
3. `pb.payroll.calendar` — per-country cut-off + pay-day with reminder cron; **Payroll
   calendar lens** + **Incentives lens** on the Pay Run hub.
4. `pb.benefit.plan` / `pb.benefit.enrollment` → benefits section on `/my/compensation`
   (provider links; true SSO later).
5. Finance pack: on run final approval, bundle bank file + run summary and email/attach
   (config-gated).

### Binding NON-goals
- NO GL/journal posting changes (`post_payslip_gl` stays as is). NO new approval tiers on
  runs. NO touching formula engine, payslip computation, or bank-file layouts.
- RnR cash feed is P8 (it will call the service you build here — design it reusable).

## Verified plumbing facts (do NOT re-derive)
- **"This run only" one-off lane (R1)**: `hr.payroll.import.batch` with `one_time` flag —
  wizard forces `auto_create_employees=False, auto_create_contracts=False`
  (`pb_payrun_wizard/models/pb_payrun_wizard.py:1091-1160`); UI toggle in
  `pb_payrun_wizard/static/src/js/payrun_wizard.js:36-63`. The feed service builds such a
  batch programmatically: one row per approved incentive (employee, component code,
  amount) targeted at a run period. READ the batch model's expected columns/file shape
  first (`pb_hr_payroll_formula/models/payroll_import_batch.py`) — the cleanest path may
  be generating an in-memory XLSX for `action_load_file` or using its lower-level row API
  if one exists; pick after reading, document the choice.
- Component code for incentives: the run's formula config must KNOW the code or the line
  lands uncategorised (ledger fact: uncategorised → OTH → excluded from stored net). Ship
  config param `pb_comp_ben.incentive_code` default 'INCENTV' + a check that warns (in the
  feed wizard) when the target run's config lacks the code — with a plain-English
  explanation of what to add in the Mapping screen. Do NOT auto-edit formula configs.
- Pay-run chain facts: states draft→level0→level1→level2→done
  (`pb_payruns/models/hr_payslip_run.py:74-90`, tier map `:25-29`); run has NO company_id
  (getattr guard); totals `pb_total_net`>0 display rule. Final approval = transition to
  'done' — hook the finance pack by inheriting the done-transition method in pb_payruns'
  model (find the exact method: `done_payslip_run()` at `:550-596`) ADDITIVELY (super
  first, then pack; failure of the pack must NEVER block the approval — own try/except,
  chatter note on failure).
- Bank file generation: `pb_pay_delivery` `pb.bank.file.layout` + export wizard
  (`models/bank_export_wizard.py:92-260`) — call its builder for the pack; if no layout
  configured for the company → skip with honest note (its own refusal pattern
  `:224-232`).
- ESS pay surfaces today: `/my/payslips`, `/my/taxsheet`
  (`pb_me_portal/controllers/portal.py:285-393`); clone patterns + `_prepare_home_portal_values`.
- Contract components for the comp bootstrap: wage on current contract +
  `hr.contract.advantage.template` typed values
  (`pb_hr_payroll_formula/models/contract_advantage_typed.py:26`) + the component change
  ledger `hr.contract.advantage.change`
  (`pb_hr_payroll_formula/models/contract_component_change.py:5-68`). NO CTC model exists
  anywhere — pb.employee.comp is new truth, bootstrapped from these.
- Letters: P0 engine ('incentive' template seeded). Auto-steps: P3's `automation_key`
  mechanism if a journey tie-in is wanted — NOT needed here; incentives are their own flow.
- Cut-off adjacent: `pb.wf.lock` day locks are ATTENDANCE cut-offs (`pb_close`) —
  unrelated, leave alone.
- Pay Run hub: find its lens registry/soft-extension mechanism in `pb_payhub` (it mounts
  eight cockpits; check whether it consumes a registry like People hub — if NOT, add lenses
  by the same soft-registry pattern P0 used, extending pb_payhub's lens list via ONE
  minimal additive edit and document it). Palette 2700s.

## Architecture

### Models
**`pb.employee.comp`** — mail.thread. employee_id required index, effective_date Date,
state draft/active/superseded (activating one supersedes the previous active), annual_total
Monetary computed (sum of line annualised), currency_id (company), line_ids, note,
company_id. `action_bootstrap()` (also a board bulk action): build lines from current
contract wage (+advantages) — monthly wage → 'Base salary' line, each advantage → line;
editable after. `action_activate()`.
**`pb.employee.comp.line`** — comp_id, name, kind Selection
`[('earning','Pay'),('statutory','Statutory contribution'),('benefit','Benefit'),
('perquisite','Perk'),('bonus','Variable')]`, amount Monetary, period Selection
monthly/yearly/one_time, annual_amount computed, sequence, note.

**`pb.incentive`** — mail.thread + biz.approval.chain.mixin. employee_id, kind Selection
`[('bonus','Bonus'),('incentive','Incentive'),('spot','Spot award')]`, amount Monetary +
currency (company), period_month Date (month it should pay in), reason, letter_id
(pb.hr.letter), state (mixin) + fulfilment Selection
`[('approved','Approved'),('letter','Letter sent'),('queued','Queued for pay run'),
('paid','Paid')]`, feed_batch_ref Char, run_id m2o hr.payslip.run readonly, company_id,
source Selection manual/rnr (P8 sets rnr).
On approval: generate + send the incentive letter (config-gated send), fulfilment
approved→letter.

**Feed service** — `pb.oneoff.feed` AbstractModel: `queue_for_run(incentive_ids, run)` or
periodic `feed_period(month, company)`: groups approved incentives for the month, builds
the one-time import batch (per the plumbing decision above) with rows
(employee identifier, incentive_code, amount), links batch ref + run, flips queued;
`mark_paid_for_run(run)` called from the run-done inherit → queued incentives of that
run → paid. Reusable: P8 calls `queue` with source='rnr' records. A "Queue this month"
button on the Incentives lens shows a PREVIEW (who, how much, which run/period, config
code check) before doing anything.

**`pb.payroll.calendar`** — company_id, country_id optional, month Date (first of month),
cutoff_date, pay_date, reminder_offset_days Char (csv, default '5,2,0'), state
upcoming/closed, notes. Generator action "Build next 12 months" from a pattern
(cutoff day-of-month, pay day-of-month). Reminder cron (clone vault pattern): at each
offset before cutoff → mail HR managers ("inputs close in N days") + on cutoff day →
"cut-off today"; idempotent per (calendar, offset).

**`pb.benefit.plan`** — name, provider_name, provider_url Char, country_id, kind Selection
`[('health','Health insurance'),('life','Life insurance'),('wellness','Wellness'),
('other','Other')]`, coverage_html, active, company_id.
**`pb.benefit.enrollment`** — plan_id, employee_id, member_ref Char, start/end Dates,
dependants_json Text (name+relation rows), state active/ended, company_id.

**Finance pack** — inherit the run-done method (pb_payruns) inside pb_comp_ben:
after super, if config `pb_comp_ben.finance_pack` == '1': generate bank file (layout
lookup; skip note if none), build a one-page run summary PDF (QWeb: totals, headcount,
period, approver trail), attach both to the run record, email to config
`pb_comp_ben.finance_email` if set. Own try/except; never blocks approval. Also call
`mark_paid_for_run(run)`.

### Lenses (Pay Run hub, palette 2700s)
- **Payroll calendar lens**: year strip of months (cutoff/pay chips, state colour), next
  cut-off hero countdown, reminder log, "Build next 12 months" dialog. Facade `pb.paycal`.
- **Incentives lens**: board of incentives {employee, kind chip, amount, month, state,
  letter ✓, run link}; kpis (awaiting approval, to queue this month, queued, paid MTD);
  "New incentive" dialog; "Queue this month" preview→confirm; facets kind/state/month.
  Facade `pb.incentives`.

### Portal `/my/compensation`
Route (clone taxsheet controller shape): my ACTIVE comp snapshot — annual package hero,
line table grouped by kind (Pay / Statutory / Benefits / Perks / Variable) with monthly +
yearly columns; effective date; my benefit enrollments (plan cards with provider link
button "Open provider site"); paid incentives history (letter download); link to
/my/payslips. Empty state when no snapshot: "Your package summary is being prepared."
`/my` counter not needed. Own-record ir.rules for comp + enrollment (read).

## Safety rails
- The feed NEVER creates employees/contracts (one_time flags) and NEVER touches an
  existing run in level1+ — queue only into draft/level0 runs or a fresh batch; the
  preview must state the target run's state.
- Finance pack + letter sending + all reminder mails config-gated, default '0' during
  tests; flip and verify at the end (report final states).
- Use the demo pay world for run interactions (demo runs, demo employees); do NOT approve
  or modify real historical runs — create a fresh test run via the Run Payroll wizard's
  demo path.
- Deploy `-i pb_comp_ben -u pb_payruns` only if pb_payruns needed the lens-registry edit
  (document it).

## Numbered test cases
T1. Deploy clean.
T2. Bootstrap comp for a demo employee → lines from wage+advantages, sensible annual
    total; activate; edit a line; bootstrap again → new draft version, activating
    supersedes.
T3. `/my/compensation` as that employee's login → hero + grouped table + benefits cards
    render; another employee's data unreachable; light+dark screenshots.
T4. Incentive: create (bonus, next month) → approval chain → approved; letter generated,
    vault-filed; with send-gate on, mail queued.
T5. Calendar: build 12 months (cutoff 25th, pay 1st) → strip renders; force reminder cron
    at offset 5 → ONE mail; rerun → idempotent.
T6. Queue this month (demo run in draft): preview lists the incentive + flags the config
    code check result; confirm → one-time batch created + processed into the run; the
    slip for that employee shows the incentive line with code INCENTV (add the code to
    the DEMO config mapping first per its Mapping screen — document the step); incentive
    → queued with run link.
T7. Run the demo run through to done (its normal chain) → incentive flips paid;
    finance-pack (gate '1'): bank file (or honest skip note) + summary PDF attached to
    the run; email to the test finance address queued.
T8. Approval-blocking check: finance pack failure path (temporarily point layout wrong)
    → run STILL reaches done; chatter notes the pack failure.
T9. Benefits: plan + enrollment for test employee → shows on portal with provider button.
T10. Incentives lens + calendar lens render with real data; ⌘K entries; screenshots.
T11. White-label grep zero; plain English (no "batch/config" jargon on portal).
T12. Regressions: /my/payslips + /my/taxsheet untouched; a plain demo run without
    incentives approves exactly as before; P0–P6 lenses load.
T13. Clean up test artefacts (cancel test run per gotcha: set draft first); report
    final config-param states.

## Deliverables / report back
Commits, per-test results, deploy EXIT, deviations, gotchas, the feed-service API for P8
(`queue` signature + source flag), the incentive component-code requirement documented
for the owner report, lens integration mechanism used on pb_payhub, palette ids.
