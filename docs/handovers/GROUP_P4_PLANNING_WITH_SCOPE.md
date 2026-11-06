# GROUP Phase 4 — "Planning with scope": the Decision Room for a plant, a scheme, a company or the group

Read `docs/handovers/GROUP_LEDGER.md` FIRST and fully (rules, rulings G1–G9, gotchas
GR1–GR24 — GR24: the payobook admin password on file no longer works; validate with a
temporary account created via `odoo-bin shell` and archive it after), then the P1–P3
phase-log entries and code (`pb_group`: `pb.group`, `pb.division`, `pb.fx.convert_many`;
`pb_scheme_map`: `hr.employee.pb_paid_by_id`, `pb.scheme.map.resolve_many`; `pb_explorer`:
`pb.fact.emp` with `config_id`, `division_id`, `currency_id`, `person_id`, `fte`), then
`docs/handovers/WFPLAN_LEDGER.md` + `WFPLAN_P1..P3` and the live module `pb_decision_room`
19.0.3.0.0 (models/pb_decision_room.py `_build_baseline`, `pb_decision_assumptions.py`,
`pb_decision_plan.py`, static/src/js/decision_engine.js, decision_room.js), then Part F of
`docs/design/group-blueprint.html`.

## 0. What you are building, in one paragraph

The Decision Room today plans one company with one set of Vietnamese rules. This phase
gives it **scope**: a chip at the top of the stage that reads "Retail scheme · Vietnam" and
switches between the group, a country, a company, a division or a payroll scheme, changing
the roster, the rules and every number in one motion. Rules stop being Vietnam-only: a
**rule set per country** ships for the eight countries the payroll engine knows, is picked
by the company's country, and can be overridden per scheme, so Singapore stops inheriting
Vietnam's contribution cap. A **group view** draws each entity's line in its own money and
the group total in the board's currency through `pb.fx`, refusing to add what it cannot
convert. Plans remember their scope, so "Retail 2027" and "Logistics 2027" sit side by
side. Once a pay run closes, the stage draws the **actual** over the plan for that month.
A plan can be **proposed and approved** with a version kept, ready for the Pay Review to be
born from it in P6. An **exact-cost** lane runs a plan's people through their own scheme's
rules as a background job and reports the difference from the fast estimate. Nothing
writes to payroll.

## 1. Scope and binding non-goals

Deliverables:
1. `pb_decision_room` 19.0.4.0.0: scope model on plans/assumptions, `pb.decision.ruleset`
   with eight country defaults, scope-aware baseline, group view, plan-vs-actual, approval
   + versions, exact-cost job, engine changes, UI, tests, `vi_VN.po` update.
2. `pb_import_kit` bump only for missing icons. ⌘K rows 3360 ("Plan the group"), 3370
   ("Plans awaiting approval").
3. Deployed p9clone → payobook → abm → payobook_template; Chrome walks; commits; ledger;
   report.

Non-goals (do NOT build):
- No work segments, no person identity (P5): FTE stays 1.0 per person, but the roster
  carries `fte` and the engine multiplies by it so P5 is a data change.
- No Pay Review (P6). No writes to `hr.*`, payslips, the scheme map or facts.
- No new rate source, no accounting, no stored converted amounts (rule 7).
- No new `pb.sidebar.item`.

## 2. Design (the bar, the hero, the copy)

**The bar (owner's words, verbatim): "extreme WOW, intuitive, out-of-this-world
experience, best in class."** Hero moment: **the scope chip.** Click it and a picker
drops down as a tree — Payobook Group › Vietnam › Payobook Vietnam JSC › Retail › Retail
End-Month payroll — with people counts on every node; pick one and the stage's big number
tweens, the roster's teams re-list, the assumptions card changes its country flag, and the
chip reads the new scope, all inside 300 ms. Second hero: **the group stage** — one line
per company in its own currency beneath a group total in the board's money, the rate badge
from P3 on the total, and a "Not converted" strip when a rate is missing. Third: **actual
over plan** — the months that have closed draw a solid actual line over the dashed plan
with a one-line verdict ("June came in ₫2.1B under plan; overtime was the difference").

Copy: "Plan for" (the chip), "Whole group", "Country", "Company", "Division", "Payroll
scheme", "Rules for Vietnam", "Rules for this scheme", "Propose", "Approve", "Version 3
· approved by …", "Exact cost", "Estimated cost". Never "scope_type", "ruleset",
"config". Zero dead-ends (§8). Keyboard: chip opens with Enter, tree with arrows.

## 3. Server design

### 3.1 Scope
On `pb.decision.plan` and `pb.decision.assumptions`: `scope_kind` Selection
`group|country|company|division|scheme` (default `company`), `scope_ref` (Char id/code),
`scope_label` (Char, stored), `currency_id` (computed: the company's, or the group's
presentation currency for group/country scopes with mixed currencies), `company_ids`
(Many2many, the companies the scope spans). Assumptions become per-scope: one record per
(scope_kind, scope_ref) created on first read; a company-scope record is the P1–P3 one.

### 3.2 `pb.decision.ruleset` (data-shipped, editable)
Fields: `country_code` (Selection VN/SG/ID/IN/MY/TH/KH/PH), `name`, `employer_rate_pct`,
`employee_rate_pct`, `contribution_cap` (in the country's currency; 0 = none),
`allowance_pct`, `ot_multiplier`, `night_uplift_pct`, `work_days`, `recruit_cost_months`,
`severance_months`, `ramp_first_month_pct`, `bonus_month_index`, `bonus_months`,
`pit_ladder` (Json), `note`, `active`; `mail.thread` tracking. Ship VN from the existing
P1 defaults (23.5 / 10.5 / 46,800,000 / 12 / 1.5 / 30 / 22 / 1.0 / 1.5 / 50 / 1 / 1.0 /
ladder) and sensible published statutory defaults for the other seven with a `note`
saying "starting point — confirm with your adviser" (SG: CPF employer 17 / employee 20,
ordinary wage ceiling 6,800 SGD/month, no PIT withholding at source; ID: BPJS employer
≈10.24–11.74 / employee 3, caps per programme; IN: EPF 12/12 on 15,000 basic cap, ESI
3.25/0.75 under 21,000; MY: EPF 13/11, SOCSO 1.75/0.5; TH: SSF 5/5 cap 750 THB/month; KH:
NSSF employer 2.6 + 2, employee 0; PH: SSS/PhilHealth/Pag-IBIG combined employer ≈9.5,
employee ≈4.5 with caps) — encode the CAP per country as one number in local currency
and the RATE as one employer and one employee percentage; the note lists what was
simplified. Resolution order for a scope's effective rules: scheme override → company
assumptions → country ruleset (by the company's country) → VN.

### 3.3 Baseline per scope (`_build_baseline(scope)`)
- company: as today.
- division: departments linked to the `pb.division` as of today (across member
  companies); teams = the division's departments grouped by company; one currency if all
  members share it, else `mixed` (group mode required).
- scheme: employees whose `pb_paid_by_id` (main run) is the scheme; teams = their
  departments; currency = the scheme's company.
- country: member companies of the group in that country; teams = companies.
- group: all member companies; teams = companies; currency = group currency; each team
  carries its own `currency` and the engine computes per company and converts at read
  time via `pb.fx.convert_many` (rule 7: plan JSON stores local amounts only).
Cache per (scope, roster signature) as today; ≤ 800 ms cold on the group scope.

### 3.4 Engine (`decision_engine.js`)
`compute(baseline, rules, state)` runs per company block when the scope spans several
(each block with its own ruleset), returning `{blocks: [{company, currency, rows, year}],
group: {rows, year, converted: bool, unknown: [...]}}` where the group totals are built
by the client from `pb.fx` results fetched with the baseline (rates per month for each
currency pair under the group policy, sent as a small table so conversion stays in the
browser with the same `(value, known)` contract). Every existing single-company path is
unchanged (T1 identity).

### 3.5 Plan vs actual
`get_actuals(scope, year)` → per month `{people, cost, revenue?:null, currency}` from
`pb.fact.emp`/`pb.fact.line` filtered by the scope (company/division/scheme/person),
main runs only; months with closed runs only. The stage draws actual over plan; a verdict
sentence compares cost and people (revenue is typed, so no actual).

### 3.6 Approval and versions
`pb.decision.plan`: `state` draft|proposed|approved|rejected, `approver_group`
(`pb_decision_room.group_decision_manager`), `proposed_by/at`, `decided_by/at`,
`decision_note`, `version_ids` → `pb.decision.plan.version` (name, snapshot Json of state +
goals + summary + scope + rules used, `created_by/at`, `label`). Propose snapshots a
version; Approve marks it and locks the plan (a copy is offered to keep editing); Reject
returns it with the note. Chatter on all of it. Approvers get a Home task
(`mail.activity`) with a link to the plan.

### 3.7 Exact cost (background)
`pb.decision.exact` AbstractModel: `start(plan_id)` enqueues a job (an `ir.cron`-triggered
queue table `pb.decision.exact.job` with state/progress, since no queue module is
assumed); the job groups the scope's people by (scheme, job, base pay rounded to 1,000)
and, for each group, builds input values with the base pay (and the plan's raise
percentage from its month) and evaluates the scheme's rules through the existing formula
engine (`hr.formula.rule.evaluate` as `pb_hr_workforce_planning`'s
`employer_cost_calculator.evaluate_costs` did — port the fixed-point pass and the bucketing
by `value_kind`/`net_role`, ruling G7), multiplies by heads, sums per month; stores
`{months:[...], year, buckets, computed_at, groups, seconds}` on the plan as
`exact_result` Json; the room shows "Exact cost: ₫X · estimate was ₫Y · +2.1%" with a
per-month strip. Target: company 5 full year < 90 s in the job. If the engine call is
unavailable on a DB (no formula rules for the scheme), the result says so.

## 4. Client design
- Scope chip in the stage header (`.dr-scope`), picker drawer with the tree and counts
  (from `get_scopes()`), remembered per user in localStorage (namespaced); URL hash carries
  the scope so a link reproduces it.
- Assumptions dialog: header shows "Rules for <country> · <company>" or "Rules for this
  scheme (overrides Vietnam)"; an "Override for this scheme" switch creates the
  scheme-scope record; a "Reset to country rules" button.
- Group stage: metric tabs unchanged; the chart draws one thin line per company (own
  currency, right axis labels suppressed) plus the group total (bold); tiles show group
  totals with the rate badge; "Not converted" strip with the P3 sentence and a link to the
  rate list; "Each in its own money" switch lists per-company stages stacked.
- Plan vs actual: actual line + verdict; tile "Plan vs actual · June".
- Plans dock: scope column; compare-against limited to same-currency plans unless group
  mode; Propose / Approve / Reject buttons by role; versions drawer; "Plans awaiting
  approval" lens on Home for approvers (`HOME_LENSES` seq 31) — or a chip on the existing
  Decision Room Home lens if a second lens is one too many (decide; say which).
- Exact cost: a button on the dock row → progress chip → result strip.

## 5. Tests (p9clone; numbered)
- T1 **identity**: company scope with no overrides reproduces the P3 numbers exactly for a
  saved plan fixture (engine + facade).
- T2 rulesets: eight rows shipped, VN equals the P1 defaults; resolution order scheme →
  company → country → VN; a SG company gets the SG cap and rates.
- T3 baseline per scope: division roster equals the linked departments' people; scheme
  roster equals `pb_paid_by_id`; group roster equals the members' sum; mixed-currency
  scopes flag `mixed`.
- T4 engine multi-block: per-company blocks use their own rules; group totals built from
  known conversions only; unknown months listed; local amounts only in the plan JSON.
- T5 plan vs actual: months with closed runs return actuals from facts filtered by scope;
  open months absent; the verdict sentence names the larger driver.
- T6 approval: propose snapshots a version; approve locks and offers a copy; reject
  returns with note; non-managers cannot approve (plain sentence); activity created.
- T7 exact cost: on company 5 for one scheme the job finishes < 90 s, result stored, the
  difference vs estimate reported; on a scheme without rules the result explains.
- T8 assumptions per scope: created once per (kind, ref); scheme override + reset work;
  chatter tracks.
- T9 facade timing: group scope cold < 800 ms, warm < 50 ms on payobook.
- T10 no "Odoo"; static contract (bundle, icons, action records, palette rows 3360/3370,
  no rail item); `vi_VN.po` complete for new strings (T37-style test from WFPLAN P3).
- T11 earlier suites green: `/pb_decision_room` (all P1–P3 WFPLAN tests), `/pb_group`,
  `/pb_scheme_map`, `/pb_explorer` (same p9clone baseline drift, no new failures).
Browser (payobook + abm via temporary validators; 1440 + 390; light + dark;
`docs/handovers/group_p4_shots/`):
- B1 Scope chip → tree → pick Retail scheme → stage, roster, rules change; chip reads it;
  reload reproduces via the hash.
- B2 Assumptions dialog shows "Rules for Vietnam"; switch to the Singapore company scope →
  "Rules for Singapore" with the SG cap; override for a scheme; reset.
- B3 Group scope on payobook: per-company lines + group total; VND-only today so no
  badge; on p9clone add one SGD→VND August rate + a scratch SG contract set (or reuse the
  P3 rehearsal recipe) to show the badge and the "Not converted" strip; delete after.
- B4 Plan vs actual: pick 2026, see actual months drawn over the plan with the verdict.
- B5 Save "Retail 2027" (scheme scope) and "Logistics 2027" (division scope); compare in
  the dock; compare-against greys out a plan in another currency.
- B6 Propose → approver sees a Home task → Approve → version 1 in the drawer → plan
  locked → "Keep editing a copy".
- B7 Exact cost on a saved plan → progress → result strip with the difference.
- B8 abm: scope chip shows Company only (one company, one scheme, no group divisions);
  everything reads as before.
- B9 390 px and dark; ⌘K rows.
- B10 Vietnamese user: every new string translated (list survivors as failures).

## 6. Build order
1. Rulesets + scope fields + baseline per scope + T1–T3, T8, T9.
2. Engine blocks + group conversion table + T4; plan-vs-actual + T5.
3. UI: chip/picker, group stage, assumptions header, actual line; B1–B4.
4. Approval/versions + Home lens or chip; exact-cost job; T6, T7; B5–B7.
5. Static/i18n tests, Chrome walks, deploy ritual (backups), verify, commits, ledger
   (GR25+), report.

## 7. Report back (plain-English first)
1. Three sentences: what the scope chip does, what a Singapore company now gets, what
   "actual over plan" shows.
2. T1–T11 / B1–B10 table with evidence; facade and exact-cost timings.
3. Deploy evidence per DB; scratch data cleaned.
4. Deviations; new gotchas; phase log updated; the Home lens-vs-chip decision.
5. Self-score against the bar and the one thing to improve first.
6. Commit list.

## 8. States (zero dead-ends)
No group (chip offers Company only) · a division with people in two currencies (group
mode forced; sentence) · a scheme with nobody paid by it (roster empty; link to the map)
· a country with no member company (absent from the tree) · missing rate in group mode
("Not converted" strip + link) · no closed runs in the year (actual line absent; sentence)
· a plan proposed by its approver (allowed, noted) · approving with unknown conversions
(allowed; the version records "unconverted: …") · exact cost on a scheme without rules ·
exact cost job failure (sentence + retry) · Vietnamese user.
