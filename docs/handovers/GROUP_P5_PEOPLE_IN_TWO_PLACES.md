# GROUP Phase 5 — "People in two places": one person, work segments, day-based pay, two payment patterns

Read `docs/handovers/GROUP_LEDGER.md` FIRST and fully (rules — rule 8 becomes "nothing
changes for anyone without a segment"; rulings G1–G9, especially **G8** the configurable
split-pay policy; plumbing; gotchas GR1–GR32), then the P1–P4 phase-log entries and code
(`pb_group`, `pb_scheme_map`, `pb_explorer` facts, `pb_decision_room` 19.0.4.0.0), then
Part E of `docs/design/group-blueprint.html` and the "People" table in Part A, then the
verified findings in `docs/design/one-group-many-payrolls.html` (the split-worker section
and its engineer fold), and the WFPLAN ledger for credentials (GR24/WF15: temporary
validator accounts, archived after).

## 0. What you are building, in one paragraph

Today a person is one employee record in one company with one contract and one scheme;
nothing can say "twenty days in Vietnam Retail, ten days in Singapore Logistics", and a
mid-month joiner is paid a full month. This phase adds two ideas and makes payroll read
them. A **person** is one identity across companies, so headcount counts human beings.
A **work segment** is the days a person spends in an entity, division and scheme, with a
full-time equivalent; a whole month is the implicit standing segment, and a segment is
only ever written for the exceptions: a mid-month joiner or leaver, a transfer, a
secondment, a split month. Payroll reads segments: under **"each entity pays its own
days"** the home payslip is reduced to its days and the host entity pays its own days
under its own scheme and currency; under **"home pays, host is charged"** the home
payslip stays whole and an internal cost transfer moves the host's share into the reports.
The pattern is a group setting with a per-segment override (G8). Headcount, full-time
equivalents and cost follow the days everywhere: facts, Explorer, Decision Room. An
**Assignments** screen on the person shows the month as a strip of days, lets you drag the
host days, and previews both payslips in their own currencies before anything is saved.
For everyone without a segment, every payslip is byte-identical to today (test-enforced
re-run parity on a closed month).

## 1. Scope and binding non-goals

Deliverables:
1. `pb_workseg` 19.0.1.0.0: `pb.person`, `pb.work.segment`, `pb.cost.transfer`, the
   group policy field, the payroll hook, the pay-run population change for host
   employments, the facts columns feed (person, fte, transfers), the Assignments screen,
   the "Same person?" merge review, ⌘K rows 3380–3390, tests, `vi_VN.po`.
2. Bumps: `pb_group` (policy field + Group screen card "How split months are paid"),
   `pb_hr_payroll_formula` (one guarded hook in `_get_formula_input_values` + a
   `proration_basis='segment'` journal row), `pb_payrun_wizard` (host employments in the
   population; "Split" chip; two-slip preview), `pb_explorer` (builder reads
   `pb.person`/segment fte/transfers into the existing columns; two new measures), `pb_decision_room`
   (fte from segments; a "Split people" note), `pb_scheme_map` (resolver rung 1 = segment).
3. Deployed p9clone (with the parity rehearsal) → payobook → abm → payobook_template;
   Chrome walks; commits; ledger; report.

Non-goals (do NOT build):
- No accounting posting of cost transfers (owner ruling: no accounting link); they are
  report lines and an export.
- No automatic creation of host employments without a person pressing "Create the
  employment in <company>" and seeing what will be created.
- No change to any payslip for a person without a segment (rule 8, P5 form).
- Joiner/leaver proration by days is **shipped OFF** behind a company switch
  ("Prorate joiners and leavers by days"), because it changes existing customers'
  numbers; the switch is on the Group screen per company with a plain warning.
- No Pay Review (P6). No new `pb.sidebar.item`.

## 2. Design (the bar, the hero, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero moment: **the month strip.** On a person's
"Where they work" tab the month is thirty little day cells; drag across ten of them, pick
Singapore › Logistics › the Logistics scheme in the popover, and beneath the strip two
payslip previews draw themselves — Vietnam, 20 days, ₫…; Singapore, 10 days, S$… — with
the group total beside them and the pattern chip reading "Each entity pays its own days ·
group default". Switch the chip to "Home pays, host is charged" and the second preview
folds into a transfer line: "₫4.2M charged to Payobook Singapore". Nothing is saved until
"Confirm". Second hero: **"Same person?"** — the merge review lists pairs of employee
records that look like one human (same national ID, or same email, or same name and
birthday) with the evidence, and one press joins them into a person, counted once from
then on. Copy: "Person", "Employment", "Where they work", "Segment", "Home", "Host",
"Each entity pays its own days", "Home pays, host is charged", "Charged to / from",
"Full-time equivalent". Never "FTE" alone on first use, never "proration factor",
"segment_share". Zero dead-ends (§8). Keyboard: day cells arrow-navigable, Shift+arrow
extends the selection, Enter opens the popover, Esc closes (WF4).

## 3. Server design

### 3.1 `pb.person`
`name`, `national_id`, `tax_id`, `birthday`, `email`, `home_employee_id` (the standing
employment; default the oldest active employment), `employee_ids` (One2many via
`hr.employee.pb_person_id`), `company_ids` (computed), `active`, `note`; `mail.thread`.
Bootstrap on install (post_init_hook + migration for `-u`): one person per active
employee; `merge(person_ids)` keeps the oldest, re-points employees, segments, facts;
`suggest_merges(company_ids)` → pairs with evidence and a score (national ID match = 1.0,
email = 0.9, name+birthday = 0.7). Headcount everywhere = distinct `pb.person`.
`hr.employee.pb_person_id` (index) — the only new column on `hr.employee`.

### 3.2 `pb.work.segment`
`person_id` (required), `home_employee_id` (required, the employment whose month is
reduced), `host_company_id` (required for a split; equals the home company for a transfer
or joiner/leaver segment), `host_employee_id` (optional; required at confirm under
`each_pays` when host ≠ home), `division_id` (optional `pb.division`), `config_id` (the
host scheme; resolved through `pb.scheme.map` when empty), `date_from`, `date_to`
(required, same month — a segment never crosses a month; the screen splits it), `days`
(computed working days in the range from the home employment's calendar, editable),
`month_days` (working days in the month, same calendar), `share` (= days/month_days,
stored), `fte` (default = share; editable for part-time), `pay_policy` Selection
`inherit|each_pays|home_pays` (default inherit → the group's), `effective_policy`
(computed), `kind` Selection `split|transfer|joiner|leaver|parttime`, `state`
draft|confirmed|cancelled, `note`; `mail.thread`. Constraints (plain sentences): the sum
of confirmed shares for a person in a month ≤ 1 unless `kind='parttime'` explicitly
allows; no overlap between confirmed segments of the same person; host employment must
belong to the host company and the same person. Derived joiner/leaver segments are
created by a nightly job only for companies with the switch on, `kind='joiner'|'leaver'`,
never editable, recomputed when the contract dates change.

### 3.3 Policy (G8) on `pb.group`
`split_pay_policy` Selection `each_pays|home_pays` (default `each_pays`), tracked; per
company `prorate_joiners_leavers` Boolean (default False) on `res.company` (in
`pb_workseg`), tracked. Group screen: a card "How split months are paid" with the two
patterns explained in one sentence each, and per-company switches for joiner/leaver
proration with the warning "Turns on day-based pay for people who start or leave
mid-month. Payslips for those people will change from the next run."

### 3.4 The payroll hook (the risky part — keep it small and guarded)
In `pb_hr_payroll_formula/models/hr_payslip_formula.py::_get_formula_input_values`
(or the input-building method the P2 ladder edit sits near), add ONE guarded call:
`if 'pb.work.segment' in self.env: factor, meta = self.env['pb.work.segment'].factor_for(self)`
where `factor_for(payslip)` returns `(1.0, None)` for anyone without a confirmed segment
in the period, else:
- home payslip under `each_pays`: `1 − Σ host shares` (bounded [0,1]);
- host payslip (an employment listed as `host_employee_id`): `Σ its shares`;
- home payslip under `home_pays`: `1.0`, and a `pb.cost.transfer` is (re)written on
  compute: `amount = employer_cost × Σ host shares` per host company, in the home currency,
  with `pb.fx` meta for the group currency (never stored converted — store the local
  amount and the rate meta separately, rule 7);
- joiner/leaver segments: `share` of the month.
The factor applies to the columns the config prorates (`proration_component_ids`) if set,
else to columns whose `net_role`/`value_kind` mark them as basic pay or fixed allowance
(reuse the classification the exact-cost lane derived in P4; cite the helper). Each
prorated column writes an `hr.payroll.proration.line` row with `proration_basis='segment'`
and a `segment_summary` sentence, so the payslip's provenance drawer explains it. Overtime,
one-off inputs and file-supplied values are never prorated. The whole hook is wrapped so
any exception logs and returns `(1.0, None)` — a segment can never break a run.

### 3.5 Pay run
Population for a scheme (P2) gains the host employments whose confirmed segments in the
period resolve to that scheme; a "Split" chip on those rows names the other entity and the
days; the "not covered" list is unchanged. The run summary shows "3 people paid in two
places this month". Preview both payslips for a person: compute in a savepoint, read the
values, roll back (`with self.env.cr.savepoint(): … raise SavepointRollback` pattern — use
`self.env.cr.savepoint()` and an explicit exception caught outside).

### 3.6 Facts and planning
`pb_explorer` builder: `person_id` = `pb_person_id` (fallback employee id), `fte` = the
person's confirmed share for that employment in the period (1.0 default), plus two new
measures `charged_to` / `charged_from` from `pb.cost.transfer` (appended LAST, GR4).
Headcount = distinct persons (already). Explorer gets a "Paid in two places" filter chip.
`pb_decision_room` baseline reads `fte` per employment from segments (default 1.0), and the
stage's people tile says "4,533 people · 4,531.7 full-time".

## 4. Client design
- **Where they work** tab on the Employee 360 drawer (registry seam from P2) and a full
  screen `pb_workseg.action_pb_assignments` (record, tag `pb_assignments`): person header
  (employments as chips, home starred), month picker, the day strip (working days
  highlighted, weekends muted, existing segments coloured by host), drag-select → popover
  (host company › division › scheme, kind, policy chip, days/fte editable), previews
  (two payslip cards or one card + transfer line), Confirm / Cancel, history list.
- "Create the employment in <company>" inside the popover when `each_pays` needs a host
  employment: shows exactly what will be created (employee record, contract with typed
  monthly pay in the host currency, department) and creates on press; never silently.
- **Same person?** screen (`pb_assignments` with `pb_focus: 'merge'`): suggestion cards
  with evidence, Merge / Not the same; bulk "Merge all with a national ID match".
- Pay run: "Split" chip + a "Preview both slips" link per split row.
- Explorer: filter chip; Decision Room: FTE note.

## 5. Tests (p9clone; numbered)
- T1 **parity**: re-run Retail End-Month for a closed month on p9clone into a scratch run
  with `pb_workseg` installed and NO segments → every payslip's net equals the existing
  run's to the digit (902 slips; same recipe as GROUP P2 T10); delete the scratch.
- T2 bootstrap: one person per active employee on install; `merge` re-points everything
  and keeps history; `suggest_merges` ranks national ID > email > name+birthday.
- T3 segment maths: `days`, `month_days`, `share` from the home calendar; month-crossing
  refused with the sentence; overlapping confirmed segments refused; shares > 1 refused
  unless part-time.
- T4 `factor_for`: no segment → (1.0, None); each_pays home 20/30 → 0.667 and host 0.333;
  home_pays → home 1.0 + a transfer of employer_cost × 0.333 in home currency with fx
  meta; joiner segment → share; any exception → (1.0, None) and a logged warning.
- T5 hook: a prorated column writes a `hr.payroll.proration.line` with `basis='segment'`;
  overtime and file-supplied inputs untouched; provenance sentence present.
- T6 two-slip case end to end on p9clone: person with VN home + SG host employment, 20/10
  days, each_pays → two payslips whose prorated basic pay sums to the full basic pay (in
  each currency's own terms); home_pays → one payslip + one transfer; switching the group
  policy flips the outcome on recompute; a per-segment override wins over the group.
- T7 pay-run population includes the host employment for the host scheme; the "Split" chip
  data present; preview-in-savepoint leaves no rows behind.
- T8 facts: `person_id` = person; `fte` = share; `charged_to/from` measures appended last;
  `test_01_aggregate_parity` green; headcount counts a split person once at group level
  and 0.667/0.333 as FTE per company.
- T9 Decision Room baseline FTE sums; identity for companies without segments (T1-style).
- T10 joiner/leaver: switch off → no derived segments, payslips unchanged; switch on →
  segments derived from contract dates, prorated, and removed when the switch goes off.
- T11 no "Odoo"; static contract; palette 3380/3390; `vi_VN.po` complete for new strings.
- T12 earlier suites green (same p9clone baseline drift, no new failures).
Browser (payobook + abm via temporary validators; 1440 + 390; light + dark; Vietnamese
user; `docs/handovers/group_p5_shots/`):
- B1 Where they work: drag 10 days → popover → previews (two cards) → switch chip → one
  card + transfer → Confirm → history row; reload reproduces.
- B2 "Create the employment in Singapore" shows what it will create; creates; the host
  card now previews in S$ (on p9clone with the scratch SG setup; on payobook show the
  prompt only, do not create).
- B3 Same person? on payobook: suggestions (there may be none — then show the empty state
  with its sentence); on p9clone seed two look-alike records and merge them.
- B4 Pay run: the split person's row has the chip; "Preview both slips" opens the two
  previews.
- B5 Explorer: "Paid in two places" chip; a split person counted once at group, fractional
  per company; charged-to measure on p9clone.
- B6 Decision Room people tile shows the full-time figure.
- B7 Group screen: the policy card and the joiner/leaver switches with the warning.
- B8 abm: everything reads as before; no segments; bootstrap created 153 persons.
- B9 390 px, dark, ⌘K rows; B10 Vietnamese user.

## 6. Build order
1. Models + bootstrap + policy + T2, T3 on p9clone.
2. Hook + `factor_for` + transfers + **T1 parity first, then T4–T6**.
3. Pay run + facts + Decision Room + T7–T10.
4. Screens + merge review + static/i18n + T11–T12; Chrome walks.
5. Deploy ritual (backups!) to all DBs; verify; commits; ledger (GR33+); report.

## 7. Report back (plain-English first)
1. Three sentences: what a person is now, what the month strip does, what the two
   patterns produce on a payslip.
2. T1–T12 / B1–B10 table with evidence; the parity proof; timings.
3. Deploy evidence per DB; scratch cleanup; number of persons bootstrapped per DB.
4. Deviations; new gotchas; phase log updated.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.

## 8. States (zero dead-ends)
No group (only transfers and joiner/leaver segments possible; sentence) · host company
outside the group (refused with the sentence) · host has no employment for the person
(the create prompt) · host has no scheme for the division (link to the map) · policy is
home_pays but no rate for the transfer (transfer stored in home currency; badge says
unconverted) · a segment touching a closed run (refused: "June is already paid; add a
correction in July") · a person merged after runs exist (history re-pointed, facts
rebuilt, sentence) · joiner switch turned on mid-year (only future runs change; sentence) ·
the hook fails (payslip computed as today; warning in the run summary, never silent) ·
Vietnamese user.
