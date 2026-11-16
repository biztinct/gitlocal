# WDGAP Step 8 — Job changes, contracts and structure (S8-A, S8-B, S8-C side by side)

Read first: `WDGAP_WAVE_RULES.md`, `WDGAP_OWNER_RULINGS_2026-11-15.md` (J1–J6, C-1, C-2,
C-5, C-6), `WDGAP_LEDGER.md`, then `WDGAP_S8_FACTS.md` IN FULL — verified plumbing per
item (path:line), precedents, the lane definitions (§9 "Proposed split", incl. the
"Shared seams inside S8" table — binding) and the collision list (§10). Your lane = your
phase's "Owns / Edits existing / Inherits" block in §9, narrowed by anything below.

Branches `wdgap-s8a` / `wdgap-s8b` / `wdgap-s8c`; db prefixes `wdgap_s8a_` etc.

## S8-A — Pay structure (new `pb_pay_scales`, new `pb_pay_package`) — RISKY

- J4: pay scales per the existing blueprint, stage 1 (grades × steps, effective-dated
  tables) with the design's defaults, plus "new joiners start on the scale" (the
  joiner paths listed in FACTS, by inheritance). NO legal minimum wages, no wage floors,
  no revisions/arrears/step-ups (left for later — list them).
- "Build from a total" for India: from a yearly/monthly total package to the contract's
  pay lines, as a preview the user confirms (clone the W2-C take-home solver pattern;
  read-only until the user presses Apply; Apply writes through the contract's normal
  path with its normal approval). Works for any scheme that has the needed lines;
  says plainly when it cannot.
- Allowed edits of existing files: exactly those in your §9 block (`pb_pay` tab list,
  `pb_contracts` contract drawer files + manifests).
- Nothing changes an existing contract or payslip until a user applies a scale/package.
  Golden: payslips of untouched contracts byte-identical.

## S8-B — A person's working life (new `pb_job_change`, `pb_contract_rules`,
## `pb_agency_staff`) — RISKY

- Guided "Change job": promotion, transfer (company/department/manager/site/schedule)
  and pay change in ONE request with one effective date. J1: ONE approval route for the
  whole change — manager → HR → Finance only when pay is above guidance (new process key
  in the one Approvals inbox; seed it; reuse existing seats). On approval everything is
  applied together on the effective date (future-dated changes apply on the day by a
  quiet, idempotent job) and the trail shows one event. Letters by `selection_add`.
- J2: a past effective date is allowed. Pay amount changes are written through the
  contract amount-change records the Past-month re-work already detects, and the
  finished request shows "This change starts in a month already paid" with a button
  that opens a new Past-month re-work for that person and those months (probe
  `pb_retro`; deep-link only — C-6: you write NO back-pay inputs). Without `pb_retro`:
  a calm note for the pay team.
- C-1 (binding contract): model `pb.job.change` exposes
  `pb_start_for_employee(employee_id, vals=None)` returning the action that opens the
  guided flow prefilled. Document accepted `vals` keys in your report.
- FACTS findings — "pay change writes the wage at once and ignores its start date" and
  "a renewed contract does not carry the old contract's pay lines": inside the NEW
  Change job flow, do it right (dated; pay lines carried). Do NOT edit the existing
  flows' files; report precisely what a fix there would need.
- J3: fixed-term renewal rules for Vietnam and Indonesia as a rule table in
  `pb_contract_rules` (editable by HR, with source notes; not `pb_pack_*`): when the
  limit is reached → red warning, reason required to extend, "Make it permanent" beside
  it. Never blocks. Earlier contracts count per the FACTS reading.
- J5: agency staff = separate light record (name, agency, site, department, manager,
  dates, role, notes, documents), on People as its own lens and on headcount as a
  separate figure; NOT `hr.employee`; structurally cannot enter a pay run, a clock-in
  or a payslip. Rights: HR.

## S8-C — Organisation (new `pb_org_structure`, new `pb_plan_hiring`)

- Job page with levels; cost centres as a proper list (kept in step with the existing
  cost-centre text on contracts — FACTS warns that changing it rewrites PAST payslip
  lines: your design must never rewrite history; dated assignment going forward only);
  "would rehire" mark on exit (patch the exits board by inheritance).
- J6 + C-2: "Pause hiring" per company/department sets `pb_hiring_paused` on `hr.job`;
  it stops NEW hiring requests and adverts with a plain reason; offers already in
  progress continue with a warning banner. Unpause restores.
- Approved Decision Room plan → DRAFT hiring requests (never auto-submitted), with a
  link both ways and no duplicates on re-run.
- C-5: no `pb_explorer` edits; the cost-centre/job-level report column is left for
  later (say so in the report).
- Check in your report: are `pb_hiring`, `pb_vendor_access`, `pb_decision_room`,
  `pb_orgchart` hard dependencies of your modules? Prefer probes so a database without
  one of them is not force-installed.

## Step go-live note (for the deploy agent, later)

One go-live for the step; merge A, B, C; seam tests from FACTS §9 table; S8-A/B touch
wage and pay lines → short rize rehearsal.
