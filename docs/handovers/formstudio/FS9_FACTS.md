# FS-9 — facts pass (bank on the side panel; Home reads the approved account)

Branch `fs-9` from `origin/19.1` @ `e69bebcc4` (FS-7 go-live report; FS-7 is merged into 19.1
and live, so nothing here conflicts with it). Live counts: read-only SQL (`SET
default_transaction_read_only = on`) over ssh `Payobook19v2`, 2026-11-20 06:13–06:50 UTC,
**counts only**. Engineering readers only.

## 1. The "old Bank box"

`hr.employee.bank_name` ("Bank") and `hr.employee.account_number` ("Account Number"),
free-text, no groups — `pb_hr_payroll_formula/models/hr_employee.py:48-49`, on the form at
`pb_hr_payroll_formula/views/hr_employee_views.xml:42-43` (Payroll Info page). TIDY-E took
`account_number` off Full details (`pb_employee_form_tidy/models/form_rules.py`, REMOVE) and
kept `bank_name` because the side panel, the full page and the new-hire wizard still used it
(TIDY_E_REPORT §3). Nothing pays from either box.

## 2. Every reader / writer of the old box (grep at e69bebcc4, `git grep bank_name|account_number`, hr.employee only)

| # | Where | Reads / writes | What it is on screen | FS-9 |
|---|---|---|---|---|
| R1 | `pb_employee_vault/models/employee_details.py:126-134` (`_SPEC` group `bank`) | reads both boxes (+ the four Vietnamese bank-file fields, whole number) | side panel › Pay & tax › Bank | **replaced** (bridge `_e360_details` override) |
| R2 | `pb_dashboard/models/home_data.py:654-680` `_home_bank_link` (used by `_home_no_bank` :696) | reads `account_number` (OR a linked bank account) | Home: "N people have no bank account" (Pay step and the run note) | **moved** to the Payroll-ready rule |
| R3 | `pb_people/models/pb_people.py:543-544` `get_employee_detail` → `statutory.bank_name` | reads `bank_name` | employee full page bank badge (`pb_people/static/src/xml/employee_detail.xml:89`) | **moved** (tidy override) |
| R4 | `pb_people/models/pb_people.py:105,128,193,303,328-386,412,543` | reads `account_number` | People list figures, filters, cards | already moved by TIDY-E (`pb_employee_form_tidy/models/pb_people.py`) |
| R5 | `pb_onboarding/models/hr_employee.py:41,107` `PROFILE_FIELDS` → `profile_complete_pct` / `profile_missing` | reads `account_number` | joining checklist "Record complete (%)" / "Still missing: Bank account" — staff screen (`pb_onboarding/models/pb_onboarding.py:372`) **and My Payobook** (`pb_onboarding/controllers/portal.py:146`) | **not changed** — same field feeds My Payobook (non-goal). Owner question |
| R6 | `pb_people_advanced/models/people_wizards.py:73,352` | reads `account_number` as the `has_bank` fact of the new-hire / new-contract approval proposals | approval facts (routing conditions may read it) | **not changed** — approval rules are a non-goal. Listed |
| W1 | `pb_people_advanced/models/people_wizards.py:107-111` `create_employee` | WRITES both boxes when `vals` carry them | the Add employee wizard — but its screen has **no bank input** (`onboard_wizard.xml:70`: "Statutory details (bank, tax, insurance) can be completed later…"; `onboard_wizard.js:26` sends empty strings) | nothing to stop: no screen fills it |
| W2 | Mapping: any column mapped to the ordinary field `hr.employee.bank_name` / `account_number` (`pb_formula_studio/models/pb_formula_studio.py:10554` `_ec_is_mappable` offers them; comment :5199) | WRITES | pay data file import | **live mapping rows to the old box: 0 on all five** (§4). Keeps working (test 7) |
| W3 | `pb_demo/models/demo_employees.py:159-160` (generator), `:87-115` copies them into the Vietnamese bank file fields | WRITES | demo world only (payobook) | unchanged |
| — | `pb_records` / Updates sheets (`master_records.py:51`), `pb_payroll_mapping_vn/models/vn_profile.py:192`, `payroll_import_batch.py:3007,3564`, `application_domain_sources.py:182` | the **bank-account lane** (`b:` roles → `res.partner.bank` through the approval hold), not the old box | — | none |
| — | `pb_dashboard/models/home_data.py:1268` `_home_bank_count` (Home › Coming up › Payday "N banks") | reads linked bank accounts only — never the old box | — | none (it already reads an approved store) |
| — | `pb_form_studio_people` `STANDARD_FIELDS` (`form_studio.py:36`) lists `bank_name` | the Form builder engine drops any box the product rule REMOVEs (`pb_form_studio/models/form_standard.py:220,311`), and every `*bank*` field is portal-locked (`form_studio.py:254`, `standard_fields.py:122`) | — | follows automatically |

## 3. The helper "Payroll-ready" uses (THE one rule)

`hr.employee.pb_bank_on_record` (computed + searchable) and `_pb_bank_domain()` —
`pb_employee_form_tidy/models/pb_people.py:24-69`: a linked bank account
(`bank_account_ids`, written only after approval since S6-A) OR the Vietnamese bank file's
account (`vietnam_bank_account_number`, written only on approval). Which account: the FIRST
bank account (`bank_account_ids[:1]`, the one the payment list `_pb_build_rows` and the
"another person's name" flag `_pb_other_name_account` read), else the Vietnamese store.
FS-9 adds `_pb_bank_on_record_facts()` beside it (bank, holder, last 4 only).

"Change waiting": `pb.payment.list._pb_waiting_changes` (`pb_pay_delivery/models/payment_list.py:157`)
— a bank change request in `hr_review` / `finance_review`, or `draft` from an import, or a pending
Updates/Records proposal touching bank details. A waiting change is never paid (IDB1).

## 4. Live counts (active employees, counts only)

| | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Active people | 4,581 | 1 | 12 | 230 | 651 |
| Old Bank box filled | 4,500 | 0 | 0 | 0 | 0 |
| Old Account Number box filled | 4,500 | 0 | 0 | 0 | 0 |
| Approved account (either store) | 4,500 | 0 | 0 | 194 | 642 |
| … of which a linked bank account | 4,498 | 0 | 0 | 194 | 642 |
| … Vietnamese bank file only | 2 | 0 | 0 | 0 | 0 |
| Old box AND approved | 4,500 | 0 | 0 | 0 | 0 |
| Old box only (no approved account) | **0** | 0 | 0 | 0 | 0 |
| Approved only | 0 | 0 | 0 | 194 | 642 |
| Neither | 81 | 1 | 12 | 36 | 9 |
| Bank changes waiting (people) | 0 | 0 | 0 | 0 | 358 |
| Pending Updates/Records bank proposals | 0 | 0 | 0 | 0 | 1 |
| Open approval requests on bank changes | 0 | 0 | 0 | 0 | 358 |
| Accounts marked "seen" (another person's name) | 0 | 0 | 0 | 0 | 0 |
| **Mapping rows into the old box** | **0** | **0** | **0** | **0** | **0** |
| Mapping rows into the bank-account lane | 0 | 0 | 0 | 23 | 0 |

Nobody anywhere has the old box without an approved account, so moving every reader to
the approved account loses nobody. No live import writes the old box → nothing to STOP.

Demo data note (payobook): for 4,497 demo people the Vietnamese bank file number equals the
old box and **differs** from their linked bank account (0 match; nobody has two accounts) —
the demo seeds wrote two different numbers. The new block says so on each panel ("The
Vietnamese bank file has a different account: •••• nnnn"); owner question.

Module state ×5: `pb_employee_form_tidy` 19.0.1.2.0, `pb_employee_vault` 19.0.1.6.4,
`pb_pay_delivery` 19.0.1.9.0, `pb_bank_ocr` 19.0.1.6.0, `pb_dashboard` 19.0.2.3.1,
`pb_form_studio_people` 19.0.1.3.0 — installed on all five, equal to this tree.

## 5. Home "no bank account" before → after (read-only preview, all companies)

Home sums, over the current month's runs, the people in each run with no bank account.

| Month | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| **2026-11 (what Home shows today)** | 1 run · 0 → 0 | no run | no run | no run | no run |
| 2026-10 | 7 runs · 2 → 2 | — | 2 runs · 6 → 6 | — | — |
| 2026-09 | 3 runs · 0 → 0 | — | 2 runs · 7 → 7 | 1 run (63 people) · 0 → 0 | — |

No live figure changes today; the rule changes for the future (an old-box-only person would
now count as "no bank account"; a Vietnamese-bank-file-only person no longer does).

## 6. "Another person's name" (BL4) — reused, not rebuilt

`pb_pay_delivery/models/other_name.py`: test `_pb_other_name_facts` (:121, the payment list's
`_pb_name_band`), RPC `pb_other_name_state` (:150) / `pb_other_name_mark_seen` (:187), action
`action_pb_other_name_seen` (:168) writes `pb_other_name_seen_by/_on/_key` + one
`biz.audit.entry` line; gate `_pb_other_name_gate` (:143) = HR (`hr.group_hr_user`), payroll team
(`om_hr_payroll.group_hr_payroll_user`), administrators. Header chip
`pb_pay_delivery/static/src/js/other_name_chip.js:68` in `pb_employee_360_chips` (S2-C noted
the panel had no hook inside its bank section).

## 7. Who may see bank details today

- Side panel: `pb.people._require_hr` / `_vault_is_hr` (`pb_employee_vault/models/pb_people_360.py:30-45`)
  = payroll team, HR, administrators. Inside it the old Bank group showed the old boxes and
  the Vietnamese bank file's account **in full** (those fields carry no groups).
- `hr.employee.bank_account_ids`: `groups="hr.group_hr_user"` (core).
- Bank change requests: own only for a plain user; payroll team reads all
  (`pb_bank_ocr/security/pb_bank_ocr_security.xml`). Bank Verification screen: HR queue for
  the payroll team (`pb.bank.ocr._is_hr`).
- FS-9 keeps the panel's gate and narrows what it shows (last 4 digits only).

## 8. Seams used (no edit of pb_people, pb_employee_vault, pb_pay_delivery, pb_bank_ocr)

- `pb.people._e360_details` (`employee_details.py:242`), `_inherit` + `super()` (FS_HOST_FACTS A.2).
- `Employee360Drawer` patch + `t-inherit` of `pb_employee_vault.Employee360Drawer` (precedent
  `pb_form_studio_people/static/src/js/people_form_patches.js`).
- `PbOtherNameChip` patch (`@pb_pay_delivery/js/other_name_chip`) — the chip and the block stay
  in step through the bus.
- `pb.dashboard._home_bank_link` `_inherit` + `Query.subselect()` of `_pb_bank_domain()`.
- Approvals inbox door: `pb_approval_config.action_pb_approval_inbox` with
  `context.pb_focus = "request:<id>"` (`pb_approval_config/static/src/js/inbox.js:61,235`;
  the server's `locate_request` picks the pile).
- Full details: `pb_employee_form_tidy` `FORM_RULES` REMOVE (the TIDY-E mechanism).
