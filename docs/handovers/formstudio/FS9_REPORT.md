# FS-9 — Bank on the employee side panel; Home reads the approved account (report)

**Status: BUILT, NOT LIVE.** Branch `fs-9` from `origin/19.1` @ `e69bebcc4`. Nothing deployed;
the live server was only read (read-only SQL, counts only). Facts: `FS9_FACTS.md` (same folder).

## 1. What was built

| # | Ask | Built | Where |
|---|---|---|---|
| 1 | Side panel "Bank" block on the APPROVED account | Pay & tax › **Bank**: bank name, account holder, account number as `•••• 1234` (the last four digits are the only digits that leave the server), status chip **Approved / Waiting for approval / None**; a waiting change says "Change waiting for approval", the new account's last four digits, what is paid meanwhile, and **Open the request** (the Approvals inbox opened on that request when the reader may read it, else Bank Verification for the payroll team, else no button); "In another person's name: <holder>" with BL4's own **Mark as seen** (or, once seen, "Marked as seen by <who> on <date>. Payment is not changed by this."); when the two stores disagree, "The Vietnamese bank file has a different account: •••• nnnn"; "None" offers **Open Bank Verification** to the payroll team | new bridge module `pb_employee_bank_panel` (`models/bank_panel.py`, `static/src/{js,xml,scss}/bank_panel.*`) |
| 1 | Same gate, screen AND direct call | the block is in the panel payload only for the panel's own readers (`_vault_is_hr`: HR, payroll team, administrators); `pb.people.pb_bank_panel` (the refresh after Mark as seen) refuses anybody else; Mark as seen is BL4's `pb_other_name_mark_seen` with its own gate | same |
| 1 | No second seen-mechanism | the block calls `hr.employee.pb_other_name_mark_seen` (S2-C): who/when on the employee + one trail line. The header chip (S2-C) and the block follow each other through the bus (`PB_OTHER_NAME_SEEN`) — press either, both update | `bank_panel.js` (patches `Employee360Drawer` and `PbOtherNameChip`) |
| 2 | Home reads the approved account, one shared helper | `pb.dashboard._home_bank_link` → `p.employee_id IN (<sub-select of hr.employee._pb_bank_domain()>)` — the exact domain behind `pb_bank_on_record` (Payroll-ready). Home's "N people have no bank account" (Pay step + run note) | `pb_employee_bank_panel/models/home_bank.py` |
| 2 | Every other reader found | full page bank badge now names the approved account's bank (`get_employee_detail.statutory.bank_name`) | `pb_employee_form_tidy/models/pb_people.py` (`_pb_bank_on_record_facts`, beside the helper) |
| 3 | Old Bank box off the screens | `bank_name` → `REMOVE` in TIDY-E's `FORM_RULES` (Full details); the side panel's old Bank group is replaced (no old row anywhere). Column and values untouched; an import/save still writes it. The Form builder's standard-box list drops it automatically (the engine skips product-removed boxes) | `pb_employee_form_tidy/models/form_rules.py`, `tests/data/form_box_verdicts.csv` |
| A | Joining checklist "Bank account" on the same rule | done = approved account (`pb_bank_on_record`); a change waiting for approval (`_pb_waiting_changes`) counts as done in "Record complete %" and is shown apart as **"Sent, waiting for HR: Bank account"** — staff New joiners board (card line + drawer) and My Payobook › My Journey (a card under "Still to fill in"); missing only when neither. Every other line unchanged (pb_onboarding's own `PROFILE_FIELDS` loop, bank line swapped) | `pb_employee_bank_panel/models/joining_checklist.py`, `static/src/xml/onboarding_board.xml`, `views/portal_templates.xml` — no edit of `pb_onboarding` or `pb_me_portal` |
| B | Demo data agree (payobook demo only) | `pb_demo` 19.0.1.16.0: upgrade step `ensure_demo_bank_accounts_agree` — the demo person's bank ACCOUNT takes the Vietnamese bank-file number where they differ (SQL on the account row: no message, no approval, nothing deleted; idempotent). Generator: `ensure_demo_bank_accounts` gives a demo person with no account ONE account with the same number, bank and holder, then the agree step — a regenerated world carries one number per person | `pb_demo/models/demo_employees.py`, `pb_demo/migrations/19.0.1.16.0/post-migrate.py` |
| C | Mapping no longer offers the old boxes | `_ec_right_items`, `ec_model_fields`, `ec_search_fields` drop `hr.employee.bank_name` / `account_number`; `employee_mapping_create` refuses a new mapping into them ("No longer shown — use Bank account. Send bank details to the Bank lane instead."); a SAVED mapping keeps working unchanged (still writable, wire and card still drawn) and only there the card says **"No longer shown — use Bank account"** | `pb_employee_bank_panel/models/mapping_retired.py` |

**Every place changed:** side panel Pay & tax › Bank; Home "people have no bank account"
(Pay step and run note); employee full page bank badge; Full details (Bank box hidden);
joining checklist (staff board + My Journey); Mapping destination lists and the create guard;
the demo world's bank numbers (payobook only).
**Found and NOT changed:** the `has_bank` fact on new-hire and new-contract approval proposals
(approval rules are a non-goal); Home's Payday "N banks" (already reads only approved
accounts). Details and file:line in `FS9_FACTS.md` §2 and §9.

**Import check (item 3 / C):** no saved Mapping row points at the old boxes on any of the five
sites (0/0/0/0/0); the Add employee wizard has no bank input; only the demo generator writes
them. Nothing had to be stopped.

`origin/19.1` re-fetched for the follow-on: still `e69bebcc4` (FS-7 already in it), so no rebase.

## 2. Versions and go-live module list

| Module | Before | After | Go-live |
|---|---|---|---|
| `pb_employee_bank_panel` | — | **19.0.1.0.0 (new)** | `-i pb_employee_bank_panel` |
| `pb_employee_form_tidy` | 19.0.1.2.0 | **19.0.1.3.0** | `-u pb_employee_form_tidy` |
| `pb_demo` | 19.0.1.15.0 | **19.0.1.16.0** | `-u pb_demo` on **payobook only** (it is installed nowhere else) |
| `pb_dashboard` | 19.0.2.3.1 | unchanged | none (one test widened, file only) |

Dependencies of the new module, installed ×5 today: `pb_employee_form_tidy`,
`pb_employee_vault`, `pb_pay_delivery`, `pb_dashboard`, `pb_onboarding`, `pb_formula_studio`.
Tier: **normal** on four sites (no new column — `pb_profile_waiting` is computed when read —,
no data, one QWeb view; JS/SCSS/XML → asset purge + restart); **normal + data step** on
payobook (the demo agreement). Sites: payobook, payobook_template, p0clone, rize, sudima (never
abm). Commands: `-u pb_employee_form_tidy -i pb_employee_bank_panel` ×5, plus `-u pb_demo` on
payobook.

Not edited: `pb_people`, `pb_employee_vault`, `pb_pay_delivery`, `pb_bank_ocr`, `pb_onboarding`,
`pb_formula_studio`, `pb_lifecycle/`, `pb_pack_*`, `pb_me_portal`, any standard addon, any
approval rule, bank file, payment list, layout or Payroll-ready maths.

## 3. Tests

Local copy `fs_9_base` = `fs_8_base` (19.1 state) + the four Form builder modules upgraded to
the tree (FS-7). Tags scoped.

| Run | Tree | Tests | Failed | Errors |
|---|---|---|---|---|
| Baseline `-u pb_employee_form_tidy,pb_dashboard,pb_employee_vault,pb_form_studio_people,pb_people,pb_pay_delivery`, tags of the same six | pristine `git archive origin/19.1` | 352 (dashboard 88, tidy 48, vault 38, people-builder 33, pay delivery 145; pb_people has none) | 0 | 0 |
| Follow-on baseline: fresh `fs_9_base` (+ `pb_demo` installed), `-u` the six + `pb_onboarding,pb_formula_studio,pb_demo`, tags of those eight | pristine `origin/19.1` | 1,046 (formula studio 627, pay delivery 145, dashboard 88, demo 52, tidy 48, vault 38, people-builder 33, onboarding 15) | 7 | 1 |
| Follow-on final, same + `-i pb_employee_bank_panel`, + its tag | `fs-9` | 1,075 (+ bank panel 25, demo 56) | 8 → **7** after one test fix | 1 |
| Final, same `-u` + `-i pb_employee_bank_panel`, tags of the six + `/pb_employee_bank_panel` | `fs-9` | 365 (the same 352 + the new module's 13, from 11 test methods; the runner's own summary line: 279 vs 268 at baseline) | 0 | 0 |

Numbered handover tests:

| # | Test | Where | Result |
|---|---|---|---|
| 1 | approved account shown masked: bank, holder, `•••• 2222`, no whole number and no 5+ leading digits anywhere in the panel payload, old box not read, one Bank group; Vietnamese-bank-file-only person; two stores disagree note; full page badge names the approved bank, never the old box | `test_1_approved_account_shown_masked`, `test_1b_vietnamese_bank_file_account` | PASS |
| 2 | waiting change: alone → "Waiting for approval" + new last 4 + a door; beside an approved account → still Approved + the change; equals the payment list's own rule for every person; refused → none; a reader who can open neither screen gets no door | `test_2_change_waiting_for_approval`, `test_2b_door_follows_the_reader` | PASS |
| 3 | none: "None", nothing shown, Bank Verification offered to the payroll team only; the old box alone is not an account; the Payroll-ready helper agrees | `test_3_no_account` | PASS |
| 4 | another person's name: shown, Mark as seen refused for a line manager and a portal user, done by HR → who/when kept, one trail line without digits, block says "Marked as seen by … on …", chip answer agrees, account unchanged | `test_4_another_persons_name_and_mark_as_seen` | PASS |
| 5 | line manager and portal: panel refused, `pb_bank_panel` refused, details reached directly carry no Bank block; HR and payroll still see it | `test_5_no_bank_visibility_no_block` | PASS |
| 6 | Home "no bank account" for a run of 5 people = the Payroll-ready helper's count (2: the waiting person and the old-box-only person) | `test_6_home_figure_equals_the_payroll_ready_helper`; `pb_dashboard` `test_02c` widened (see §5) | PASS |
| 7 | old Bank box: no old row on the panel; REMOVE rule; not visible on any Full details tab; value still in the database; a form save keeps it; the Mapping still offers both boxes; a write to it still stores and still is not an account | `test_7_old_bank_box_off_the_screens_value_kept` + browser | PASS |
| 8 | silent install: the module's field records are only on the two abstract screen models (no table, no column), it ships no records; **checksums**: md5 + count of `hr_employee`, `res_partner_bank`, `employee_bank_account_rel`, `res_bank`, `pb_bank_change_request`, `biz_approval_request`, `biz_approval_process`, `biz_audit_entry`, `hr_contract`, `hr_payslip`, `hr_payslip_line`, `hr_payslip_import_mapping`, `mail_message` count — identical before/after `-u pb_employee_form_tidy -i pb_employee_bank_panel` on two copies (empty base; DEMO seed of 7 people, 3 accounts, 2 waiting changes, 7 payslips) | `test_8_silent_install`; `checksums.sql` | PASS |
| 9 | payslips and a bank file byte-identical | nothing in this phase touches payslips, bank files or the payment list (no override there); the pay delivery suite run WITH the module installed includes the S2-C / IDB1 golden tests (Vietnamese bank file bytes, general payment list CSV + Excel, both settings of BL4) — all pass | PASS (by golden) |
| A | checklist: approved → done; waiting → not missing, counted, "Sent, waiting for HR: Bank account"; refused → missing again (percentage drops); old box alone → missing; the same rule as the panel for every person; the My Journey view and the board row carry the waiting line | `test_followon.py` `test_a1..a5` + browser (New joiners board: "Sent, waiting for HR: Bank account" on the card and in the drawer) | PASS |
| B | demo: the account takes the bank-file number, bank + holder kept; real person, account shared with a real person, agreeing person untouched; bank-file fields unchanged; no account deleted, no message, no approval request; second run 0; generator makes ONE matching account per demo person and calls both steps after the bank-file copy | `pb_demo/tests/test_fs9_demo_bank_agree.py` `test_b1_b2_b3`, `test_b4` + copy proof below | PASS |
| C | old boxes absent from the catalogue, the model list and search; a new mapping into them refused (no row written), the Bank lane still accepted; a saved mapping keeps its wire, row unchanged, still writable, its card says "No longer shown — use Bank account", the other old box not shown | `test_followon.py` `test_c1..c3` | PASS |
| 10 | vi/id: 35 + 35 entries, every new string, PO parse gate (platform reader) 0 empty, 0 vendor word; vendor word in no file of the module; browser: Vietnamese panel fully translated, Indonesian status from the server ("Tidak ada"); console: no errors or warnings; 390 px: no sideways scroll (scrollWidth 390, block 330 px) | `test_10_vi_and_id_entries_and_no_vendor_word` + browser | PASS |

Browser walk (local `fs_9_walk`, DEMO seed, a local HR + payroll login; screenshots
`fs9_shots/`): Anh — Approved, DEMO Vietcombank, `•••• 2222` (01); Dung — Approved +
"Change waiting for approval", New account `•••• 7888`, **Open the request** → Approvals inbox
opened on that request; Chi — Waiting for approval → **Open the request** → Bank Verification;
Giang and Em (old box filled) — None + Open Bank Verification; Binh — Approved, "Vietnamese
bank file"; Dewi — "In another person's name" (header chip and block) (02) → Mark as seen in the
block → block "Marked as seen by DEMO Walk HR on 2026-11-20…", header chip gone at once (03);
Full details (7 tabs): no Bank / Account Number box, old value nowhere on the page; Home
"3 people in DEMO November 2026 have no bank account" (05); phone 390 px in Vietnamese (06).

**Follow-on suite result.** The 8 baseline failures (pb_formula_studio: journey view ×2, net-pay
candidates, one-mapping-home ×4, run-source board lane) are identical on the branch — none is
about this phase. The one extra failure was this module's own vendor-word scan reading the
`<odoo>` root tag of the new view file (technical, not on screen); fixed, and the module's
tests plus the demo tests re-run: 0 failed, 0 errors.

**B on a copy shaped like payobook** (`fs_9_demo`: 58 demo people + 2 real people, 56 demo and
2 real with two different numbers, made on the pristine code like the 2026-11-18 one-off), then
`-u pb_demo,pb_employee_form_tidy -i pb_employee_bank_panel` on the branch:

| | before | after |
|---|---|---|
| Demo people with two different numbers | 56 | **0** ("56 demo bank accounts now carry the bank file number") |
| Real people with two different numbers | 2 | 2 (untouched) |
| Real people's accounts (md5) | `7ec2e157…` | `7ec2e157…` |
| Bank-file fields of every employee (md5 — all the Vietnamese bank file reads) | `e6d9ea91…` | `e6d9ea91…` |
| Bank accounts (count) | 58 | 58 (nothing deleted or added) |
| Messages / approval requests / trail lines | 751 / 0 / 0 | 751 / 0 / 0 |
| Second run of the step | | 0 |

Why this direction: the Vietnamese bank file reads only the four bank-file fields, which do not
change, so every demo bank file builds byte for byte as before. The payment list reads the
account — but payobook holds **0 stored payment lists, 0 stored bank files, 0 bank export logs**
(read-only), so no existing file changes. Nothing had to be stopped.

**Silent elsewhere:** the bridge stores nothing; on the four sites without `pb_demo` the demo
step does not exist. Checksums before/after `-u pb_employee_form_tidy -i pb_employee_bank_panel`
on a seeded copy: see §3a.

**Payslips and bank file byte-identical (test 9):** nothing in this phase overrides a payslip,
salary rule, formula, bank file, payment list or layout; the pay delivery suite (145 tests,
including the S2-C / IDB1 golden tests of the Vietnamese bank file and the general payment list)
passes with all of it installed, both runs.

Home on the walk copy: before (old rule, SQL) 3 → after (Home screen) 3 — same number,
different people: the Vietnamese-bank-file-only person left the count, the old-box-only person
joined it.

### 3a. Silent install, follow-on code

Seeded copy (`fs_9_walk`: 7 DEMO people, 3 accounts, 2 waiting changes, 7 payslips, pristine
code), then `-u pb_employee_form_tidy -i pb_employee_bank_panel` on the branch: md5 + count of
`hr_employee`, `res_partner_bank`, `employee_bank_account_rel`, `res_bank`,
`pb_bank_change_request`, `biz_approval_request`, `biz_approval_process`, `biz_audit_entry`,
`hr_contract`, `hr_payslip`, `hr_payslip_line`, `hr_payslip_import_mapping` and the
`mail_message` count — **identical**. The only data step is B, on payobook, shown above.

## 4. Home figure before → after per live database (read-only preview)

Home today shows November 2026 runs.

| Site | November 2026 (on Home now) | October | September |
|---|---|---|---|
| payobook | 1 run · **0 → 0** | 7 runs · 2 → 2 | 3 runs · 0 → 0 |
| payobook_template | no run · nothing shown | — | — |
| p0clone | no run · nothing shown | 2 runs · 6 → 6 | 2 runs · 7 → 7 |
| rize | no run · nothing shown | — | 1 run · 0 → 0 |
| sudima | no run · nothing shown | — | — |

No live Home number changes at go-live. What each site's panel will show (active people):
payobook 4,500 Approved / 81 None; payobook_template 1 None; p0clone 12 None; rize 194
Approved / 36 None; sudima 642 Approved (358 of them with a change waiting) / 9 None.

### 4a. Joining checklist "Bank account" before → after (read-only preview, active people)

| Site | People | "Bank account" still to fill in: before → after | "Sent, waiting for HR" after |
|---|---|---|---|
| payobook | 4,581 (12 with a joining checklist, 11 still open) | 81 → 81 (checklists: 11 → 11) | 0 |
| payobook_template | 1 | 1 → 1 | 0 |
| p0clone | 12 | 12 → 12 | 0 |
| rize | 230 (no joining checklist) | **230 → 36** | 0 |
| sudima | 651 (no joining checklist) | **651 → 9** | 0 (its 358 waiting changes are all beside an approved account) |

### 4b. Demo agreement on payobook (expected at go-live)

4,497 demo bank accounts take their Vietnamese bank-file number (the 2026-11-18 accounts were
made with other random numbers); afterwards 0 demo people show "The Vietnamese bank file has a
different account". Bank-file fields, holders, banks unchanged; 0 stored files exist to change.

## 5. Test file edited outside the new module (test only, no version change)

`pb_dashboard/tests/test_home_data.py` `test_02c_an_account_number_on_the_employee_is_a_bank_account`
pinned the old rule (old box = bank account). It now expects the old rule without the new
module and the approved-account rule with it, so it passes either way.

## 6. Deploy notes (for the go-live, batched later)

1. Read `/opt/deploy-notes.md`; announce. Ship `pb_employee_bank_panel` (new),
   `pb_employee_form_tidy` and `pb_demo` per module to `/odoo/odoo-server/addons/`.
2. Before, per site (read-only): `FS9_FACTS.md` §4 queries + `checksums.sql`-style md5 of
   `hr_employee`, `res_partner_bank`, `employee_bank_account_rel`, `pb_bank_change_request`,
   `biz_approval_request`, `biz_audit_entry`.
3. `-u pb_employee_form_tidy -i pb_employee_bank_panel -d <site> --stop-after-init` ×5; check
   `latest_version` 19.0.1.3.0 / 19.0.1.0.0; on **payobook only** also `-u pb_demo` (→ 19.0.1.16.0;
   log line "pb_demo: N demo bank accounts now carry the bank file number", N ≈ 4,497; never on
   the other four — `pb_demo` is not installed there); purge `/web/assets/%`; restart.
4. After: the same md5 (expect identical on the four sites; on payobook only
   `res_partner_bank` changes, by the demo step — check: 0 demo people with two numbers, real
   people's accounts unchanged, `mail_message` / `biz_approval_request` counts unchanged); Home "no bank account" = §4; side panel on one
   Approved (rize), one with a waiting change (sudima), one None; Full details has no Bank box;
   console clean; New joiners board on payobook shows "Sent, waiting for HR" only where a change
   waits; Mapping no longer lists the old Bank / Account Number boxes.
5. Rollback: uninstall `pb_employee_bank_panel` and `-u` the previous `pb_employee_form_tidy`
   tree — no data to undo on four sites. payobook demo: the step's before-values are not kept
   (demo-only random numbers); restore from the nightly backup if ever needed.

## 7. Gotchas (for the ledger)

- FS9-1 An HR user WITHOUT the payroll role (only `hr.group_hr_user`) can hit "not allowed to
  access Employee Contract" opening the side panel (`pb_people.get_employee_detail` → `_join_date`
  reads `contract_ids`). Pre-existing, seen once in a test; the Bank block itself works for them
  (`pb_bank_panel`). Not changed here.
- FS9-2 `hr.payslip.run` has no `company_id` on this build — fixtures must not pass one.
- FS9-3 `ir.model.fields.modules` is not stored — cannot be searched; use `ir.model.data`
  (module + model `ir.model.fields`) to find a module's fields.
- FS9-4 A module that only `_inherit`s abstract screen models still gets `display_name` / `id`
  field records under its name (export artifacts, FS7-6) — harmless, no column.
- FS9-6 A new test that scans a module's files for the vendor word must allow the `<odoo>` root
  tag of data XML (technical, never on screen).
- FS9-7 `pb_demo`'s generator never made bank accounts; the 4,498 demo accounts on payobook came
  from a one-off (2026-11-18). Anything that reseeds the demo now makes accounts with the
  bank-file number.
- FS9-5 Two places showing one notice (header chip + block) must share a refresh path — here
  the web bus event `PB_OTHER_NAME_SEEN` (`from: panel|chip`) — or one goes stale after a press.

## 8. Owner questions (plain words)

None open. The three questions of the first report were answered by the coordinator's
follow-on (A, B, C above) and are built.
