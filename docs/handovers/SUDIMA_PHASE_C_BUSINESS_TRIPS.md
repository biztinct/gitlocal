# SUDIMA Phase C — Business Trip Management + Attendance Integration

**Scope items:** Sudima demo requirements **#6 Business Trip Management** and **#7 Business Trip Attendance Integration** (both *Not Built*) — built as ONE travel story.
**Modules:** NEW `biz_approval_chain` (generic engine — also consumed by Phase D) + NEW `pb_business_trip` (core) + NEW glue `pb_trip_payroll_bridge`, `pb_trip_expense_bridge`.
**Ledger:** `docs/FORMULA_ENGINE_CONVENTIONS.md` — **C1, C2, C18 binding** (C18.2 code registry, C18.4 virtual-overlay rule, C18.1 engine/overlay convention).
**Prerequisites:** Phases A & B shipped (sidebar `plane` icon exists; grid `flags` seam exists).

---

## 1. Scope

1. **`biz_approval_chain`**: a small generic approval framework — state-transition mixin + audit log + one OWL approval-stepper widget. Reusable by ANY model in ANY app (Phase D reuses it for bank changes).
2. **Trip lifecycle**: employees (or HR on their behalf) raise a trip request — destination, purpose, timeline, estimated costs, cash advance, attachments — through the 4-tier chain **Employee → Manager → Finance → HR → Authorized**.
3. **Attendance integration (#7, mandatory business rule)**: during an authorized trip the employee is automatically "Business Trip (Present)" — appears in the Timecards view, is excluded from missing-punch/absence exceptions, keeps payroll eligibility. Implemented as a **virtual overlay — NO materialized `hr.attendance` rows** (C18.4).
4. **Money flows**: per-diem and trip days → payroll formula inputs (`TRIPDAYS`, `PERDIEM`); receipted expense lines → draft `hr.expense` records on final approval (accounting scalability).

### Binding non-goals
- **NO materialized attendance records for trip days** — ever (C18.4: double-count via WORK100, fake GPS analytics, cancellation cleanup).
- **NO travel booking / itinerary services** integration.
- **NO expense reimbursement PAYMENT flow** — we create *draft* `hr.expense` records; posting/paying stays in stock expense/accounting.
- **NO per-diem paid from BOTH channels** — `per_diem_channel` on the policy is exclusive (payroll XOR expense).
- **NO generic configurable-chain builder UI** — chains are per-model dicts in code; a visual builder is a later product.
- **Trip core must not depend on payroll or hr_expense** — that's what the two glue modules are for (C18.1).

---

## 2. Verified plumbing facts (do not re-derive)

- ✓ **`pb.approval` is NOT reusable**: AbstractModel hardcoded to `hr.payslip.run` level1/level2 (`pb_approval/models/pb_approval.py:11-17,37-64`). Leave it untouched; its cockpit stays payroll-only.
- ✓ **Audit precedent to clone**: `contract.component.change` (`pb_hr_payroll_formula/models/contract_component_change.py:6-67`) — old/new value, `changed_by` default uid readonly, `changed_at` default now, source selection.
- ✓ **Timecard overlay seam**: `hr.attendance.timecard` is a TransientModel; `get_timecard_data()` (`pb_hr_workforce/models/attendance_timecard.py:14-309`) returns `{days, employees:[{days:{date:{entries:[bars], regular, overtime}}}], ot_legend}` — inheritable; bars carry `bar_type/label/bar_left/bar_width`.
- ✓ **Workforce exception surfaces**: the workforce dashboard computes absence/presence KPIs from `hr.attendance` + `hr.leave` (`pb_hr_workforce/models/workforce_dashboard.py`); Phase B's grid + Timecards show empty days. There is **no dedicated missing-punch model yet** — exclusion = a helper the existing dashboards call (§3.3).
- ✓ **Formula input seam**: override-and-super `_get_formula_input_values` (`pb_hr_payroll_formula/models/hr_payslip_formula.py:277-329`) — same mechanism/rules as Phase B (underscore-free, non-substring; codes `TRIPDAYS`, `PERDIEM` are registered in C18.2).
- ✓ **`hr_expense` is stock and uncustomized** (`hr_expense/__manifest__.py`); an expense needs `product_id`, `employee_id`, `total_amount`, `name`, `date`; attachments via `ir.attachment`.
- ✓ **Leave interplay**: `hr.leave` states `confirm/validate/...` (`hr_holidays/models/hr_leave.py:34-150`) — trip-vs-leave overlap must be checked at submit.
- ✓ **Cockpit/sidebar/theming pattern**: as Phase A §2. Record-form WOW pattern: native `<form>` arch + VU Form Engine skin (memory `payobook-cockpit-pattern` — "WOW record forms = native arch + VU engine, don't rebuild in OWL").
- ✓ Chatter: `mail.thread`/`mail.activity.mixin` available; use `tracking=True` on state.

---

## 3. Architecture

### 3.1 `biz_approval_chain` — generic engine (depends: `base`, `web`, `mail`)

```
biz_approval_chain/
├── models/
│   ├── biz_approval_log.py    biz.approval.step.log
│   └── biz_approval_mixin.py  biz.approval.chain.mixin (AbstractModel)
└── static/src/ js/approval_stepper.js + xml + scss (--bac-* custom props)
```

- **`biz.approval.step.log`**: `res_model` Char index, `res_id` Integer index, `from_state`, `to_state`, `user_id` default uid readonly, `stamp` Datetime default now readonly, `note` Text, `company_id`. ACL: create via mixin (sudo-free — users who may transition may log), read follows a record rule the consumer can extend; no write/unlink for non-admins (append-only).
- **`biz.approval.chain.mixin`** (`_name='biz.approval.chain.mixin'`, inherits nothing): consumers define
  `_approval_transitions = {('draft','submitted'): None, ('submitted','manager_approved'): 'module.group_x', …}` (None = record owner/any user per consumer override of `_approval_can(from, to)`).
  Provides: `_advance_state(to_state, note=False)` — validates the (current, to) pair exists, checks group via `self.env.user.has_group`, calls optional hook `_before_approval_transition(to)` / `_after_approval_transition(to)`, writes `state`, creates the log row; `action_refuse_chain(note)` (any approver group of the CURRENT stage may refuse → `refused`); `get_approval_trail()` → JSON for the stepper.
- **`ApprovalStepper` OWL widget**: props `{steps:[{state,label,group_label}], trail:[{to_state,user,stamp,note}], current}` → vertical stepper with avatars, timestamps, pending-state pulse. Styled via `--bac-*` custom props only (no Payobook dep).

### 3.2 `pb_business_trip` — trip core (depends: `hr`, `mail`, `biz_approval_chain`, `pb_sidebar`, `pb_import_kit`)

**Models**
- **`pb.business.trip`** (`mail.thread`, `biz.approval.chain.mixin`):
  - `name` seq `BT/2026/0001` (ir.sequence), `employee_id` required (default from uid), `manager_id` related employee.parent_id stored, `department_id` related stored
  - `destination_city`, `destination_country_id`, `purpose` Text required, `date_from/date_to` Date required, `duration_days` computed stored (inclusive)
  - `policy_id` m2o `pb.trip.policy` (auto-picked by destination match, overridable), `per_diem_rate` Monetary (default from policy, editable until submit), `per_diem_total` computed (`rate × duration_days`), `advance_amount` Monetary, `currency_id`
  - `line_ids` o2m trip lines, `estimated_total` computed (lines + per-diem)
  - `state` Selection `draft → submitted → manager_approved → finance_approved → approved | refused | cancelled` (tracking)
  - `_approval_transitions`: draft→submitted (owner), submitted→manager_approved (employee's manager OR `hr_attendance.group_hr_attendance_officer` fallback — implement `_approval_can` so the *specific* manager passes even without a group), manager_approved→finance_approved (`account.group_account_invoice` if installed else payroll manager group — resolve with `env.ref(..., raise_if_not_found=False)` fallback chain), finance_approved→approved (`om_hr_payroll.group_hr_payroll_manager` as the HR-admin tier)
  - `attachment_ids` (chatter attachments suffice), `notes`
  - Overlap guards at submit: no overlapping approved/pending trip; warn (not block) on overlapping validated `hr.leave`.
  - `get_trip_day_map(employee_ids, date_from, date_to)` `@api.model` → `{employee_id: set(ISO dates)}` for **approved** trips — THE integration helper every other surface calls.
- **`pb.business.trip.line`**: `trip_id`, `date`, `category_id` m2o, `description`, `amount` Monetary, `receipt_attachment_id` m2o ir.attachment, `expense_id` m2o hr.expense readonly (set by bridge — field DEFINED in the bridge module, not core!).
  ⚠ Correction: since core must not depend on hr_expense, `expense_id` lives in `pb_trip_expense_bridge` via `_inherit='pb.business.trip.line'`.
- **`pb.trip.policy`**: `name`, `country_id`, `city_tier` Selection(optional), `per_diem_rate` Monetary, `currency_id`, `per_diem_channel` Selection `[('payroll','Payroll allowance'),('expense','Expense claim')]` default `payroll`, `company_id`. VN seed data: Tier-1 (HN/HCMC) 200k VND/day, other 150k — `noupdate="1"`.
- **`pb.trip.expense.category`**: `name`, `sequence`; the product mapping field is added by the expense bridge.

**Attendance integration (virtual overlay — C18.4)**
- Inherit `hr.attendance.timecard` in `pb_business_trip` (new file `models/attendance_timecard_trip.py`, dep on `pb_hr_workforce` — add it): post-process `get_timecard_data()` — for each employee-day in `get_trip_day_map`, if the day has no real entries, inject a full-width bar `{bar_type:'trip', label:'Business Trip', is_trip:True}` and add a `trip` entry to `ot_legend` (violet `#7c3aed`); days WITH real entries get a small trip tag on the day row (traveller who also punched).
- Phase B grid: trip days arrive via row `flags.trip_days=[dates]` → cells render a violet "BT" chip and REG cell locks (`editable:false`) — trip presence is system-derived, not hand-entered.
- Workforce dashboard absence/presence KPIs: subtract trip-day employees from "absent today" via the helper (small override in the same file).
- **Payroll worked-days**: nothing — payroll sees trips only via the bridge inputs below. (Configs that pay from WORK100 attendance days are a pre-existing semantic; flag in report-back if the demo config derives base pay from attendance days so we can decide whether TRIPDAYS must be added to its formulas.)

### 3.3 `pb_trip_payroll_bridge` (depends: `pb_business_trip`, `pb_hr_payroll_formula`)
- Override `_get_formula_input_values` (same pattern/registry rules as Phase B §3.3): for input rules `TRIPDAYS` → approved trip days ∩ payslip period (count); `PERDIEM` → Σ (rate × days-in-period) over approved trips **whose policy channel = 'payroll'**. Collision post_init warning for the two codes.

### 3.4 `pb_trip_expense_bridge` (depends: `pb_business_trip`, `hr_expense`)
- Adds `pb.business.trip.line.expense_id` + `hr.expense.pb_trip_id` (m2o, readonly, for traceability + smart button both ways).
- Adds `pb.trip.expense.category.product_id` (m2o product.product, domain expense-ok products; seed a generic "Travel Expense" product data record).
- Hook `_after_approval_transition('approved')` (inherit trip): create one **draft** `hr.expense` per receipted line (name, date, `total_amount`, employee, product from category, copy receipt attachment); if policy channel = `expense`, also one per-diem expense line. Idempotent (skip lines with `expense_id`).
- `action_cancel` guard (inherit): refuse cancelling an approved trip while linked expenses exist unless they are all draft — then unlink/cancel the drafts first (posted expenses block with a clear error).

### 3.5 Cockpit + sidebar
- **Trips cockpit** (tag `pb_trips`, AbstractModel `pb.trips.get_pipeline_data()`): kanban lanes per state with cards; KPIs (open trips, awaiting my approval, days travelled MTD, advance outstanding); "New trip" opens the composer. Clone the `pb_people` module skeleton.
- **Trip form** = native `<form>` arch WOW-structured for the VU engine (oe_title hero with destination + dates, statusbar on `state` driven by chain buttons, grouped cards: Itinerary / Money / Lines, `ApprovalStepper` widget embedded via a `widget="biz_approval_stepper"` field wrapper on a JSON computed field, chatter). Buttons per tier call `_advance_state` (`action_submit`, `action_manager_approve`, …), invisible unless the transition is legal for the user (computed `can_*` booleans).
- Sidebar: item "Business Trips" (icon `plane`, `action_tag='pb_trips'`) — new or existing section per current sidebar layout (put under WORKFORCE, sequence after Weekly Entry).

---

## 4. WOW-UX specification

1. **Pipeline cockpit**: 5 kanban lanes (Draft, Manager, Finance, HR, Authorized) on `--pbim-bg`; cards: destination in title case + country flag-code chip (text chip, no emoji flags), date-range pill, per-diem + advance money chips, employee avatar, aging indicator ("2 d waiting") that turns amber > 3 d. Lane headers show count + total advance exposure. Refused/cancelled collapse into a footer filter.
2. **Trip composer/form**: hero row (employee avatar · "Đà Nẵng · 12–15 Aug · 4 days"); left column cards — Itinerary (destination, purpose, dates with duration auto-chip), Money (per-diem panel that recalculates live as dates/policy change: `4 days × 200,000 ₫ = 800,000 ₫`, advance field with "≤ estimated total" hint), Lines (tabular, drag-drop receipt zone per line, receipt thumbnail); right column — sticky `ApprovalStepper` (4 tiers, avatars, timestamps, pending pulse) + policy card.
3. **Timecard overlay**: violet full-day "Business Trip" bars in the existing Gantt + violet legend chip; in Phase B's grid, violet BT chips with lock tooltip "On authorized trip — attendance is automatic".
4. **Approval moments**: each approver sees a single primary action ("Approve as Finance") + refuse-with-note modal; post-final-approval toast "Trip authorized — attendance will be marked automatically" (this is the #7 demo money-line).

---

## 5. Safety rails

1. **Channel exclusivity is the double-pay guard**: per-diem goes to payroll OR expense, decided by policy at approval time; the bridge tests assert a trip never yields both.
2. **Approved trips are immutable** (dates/rate/lines) — changes require `action_reset_to_draft` which is only legal from `submitted`/`refused`; from approved, only `cancel` (with the expense guard) — and cancelling an approved trip must also drop its virtual attendance (automatic — the overlay reads approved trips only).
3. **Transition auth is server-side** (`_approval_can`) — `can_*` view booleans are cosmetic.
4. **Manager tier**: the employee's actual manager OR HR officer fallback (people leave; a demo must never dead-end an approval).
5. **No sudo() writes** in the chain; the mixin runs as the clicking user so the log is truthful.
6. **Overlap rules**: hard-block overlapping trips; soft-warn on approved leave overlap (HR decides).
7. Multi-company: trips, policies, logs all `company_id`-scoped + record rules.
8. i18n EN/VI for all new strings; money via `Monetary` + trip currency (VND default from company).

---

## 6. Test cases

**Server:**
1. Mixin: illegal transition (draft→finance_approved) raises; legal one writes state + exactly one log row with the acting uid; refuse from any mid-state → `refused` + log.
2. Group gating: employee submits own trip; a random user cannot manager-approve; the employee's manager can (without any special group); finance group required for tier 3; HR manager for tier 4.
3. Full happy path Employee→…→approved: 4 log rows, `get_approval_trail` ordered correctly.
4. Overlap: second trip overlapping an approved one is blocked at submit; overlapping validated leave → warning payload, submit still possible.
5. `get_trip_day_map` returns inclusive date range for approved trips only (draft/refused excluded).
6. Timecard overlay: approved 3-day trip → `get_timecard_data` shows `trip` bars on empty days, legend contains trip entry; a day with a real punch keeps the real bars + tag.
7. Phase B grid payload: trip days arrive in `flags.trip_days`, REG cells locked; `save_week_entries` refuses a REG write on a trip day (server-side).
8. Payroll bridge: config with `TRIPDAYS`/`PERDIEM` inputs → correct count/amount for a trip straddling the period boundary (only in-period days count); channel=`expense` policy → `PERDIEM` contributes 0.
9. Expense bridge: final approval creates one draft `hr.expense` per receipted line with product/amount/attachment; re-running the hook creates nothing (idempotent); channel=`expense` adds the per-diem expense; cancel-with-draft-expenses unlinks them; posted expense blocks cancel.
10. Trip core installs WITHOUT either bridge and without `hr_expense` present in the registry (dependency hygiene).

**Chrome MCP:**
11. Cockpit `/odoo/action-pb_trips`: lanes render; create a trip via the composer (Đà Nẵng, 4 days) — per-diem panel recalculates live while editing dates; submit; card moves lanes as each tier approves (switch users: employee → manager → Mitchell Admin for finance/HR tiers per group setup).
12. Stepper shows avatars + timestamps after each approval; refuse path shows the note.
13. Timecards for the trip week: violet BT bars visible (screenshot); Weekly Entry grid: BT chips + locked cells (screenshot).
14. `hr.expense` list shows the drafts with the trip smart-button linkage.
15. Aging chip: back-date a submitted trip → amber "waiting" indicator.

---

## 7. Deploy & verify

Memory `payobook-deploy` ritual. `-i biz_approval_chain,pb_business_trip,pb_trip_payroll_bridge,pb_trip_expense_bridge -u pb_hr_workforce,pb_sidebar` (workforce gains the overlay file → real `-u`). Never `-u pb_hr_payroll_formula`. Bump versions (C2). Verify §6.11-15 live on the pb_demo VN roster (persistent fixtures — memory `demo-payroll-test-fixtures`). Confirm the payrun wizard still runs clean end-to-end after install (it consumes `_get_formula_input_values`).

---

## 8. Report back

1. Tests 1–15 results + the three screenshots (§6.11 pipeline, §6.13 both overlays).
2. Which finance/HR groups resolved for tiers 3–4 on live (the `env.ref` fallback chain outcome).
3. Whether the demo formula config derives base pay from attendance days (⇒ decision needed on adding TRIPDAYS to its formulas) — see §3.2 payroll note.
4. Deviations (what + why), file list, manifest versions.
5. New gotchas → proposed C18 addendum wording.
6. Confirmation `pb_approval` (payrun cockpit) untouched and payrun wizard end-to-end still green.

---

## Kickoff line (paste into the Opus session)

> Read `docs/handovers/SUDIMA_PHASE_C_BUSINESS_TRIPS.md` and `docs/FORMULA_ENGINE_CONVENTIONS.md` (C1, C2, C18 binding), then implement Phase C exactly as specified: new `biz_approval_chain`, `pb_business_trip`, `pb_trip_payroll_bridge`, `pb_trip_expense_bridge`, the timecard/grid virtual overlay, tests §6, live deploy §7. Report back with the six numbered items in §8. Attendance for trips is a virtual overlay — never create hr.attendance rows for trip days.
