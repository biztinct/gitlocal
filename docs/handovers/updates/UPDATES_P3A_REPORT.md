# UPDATES — Phase 3a report (three lanes, bank second check, portal managers, month-only pay file, old import retired)

Implemented, tested, deployed and checked live on 2026-11-11 by the Opus implementation agent
against `UPDATES_P3A_HANDOVER.md` and `UPDATES_LEDGER.md`.

**Shipped** on `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima` (never `abm`,
`pbf_preview`, `recruit_connect_20261023`): `pb_records` 19.0.1.10.0, `pb_updates` 19.0.1.4.0,
`pb_import` 19.0.1.7.1, `pb_import_advanced` 19.0.1.15.4 (upgraded); `pb_hr_payroll_base`,
`pb_demo`, `pb_learn` files only (versions unchanged).

Commits: `964ef4339` (Records Desk lanes + bank second check) · `11f3ffa5f` (Updates screens,
D12, D1, retire doors, demo seam) · `da908defc` (old import retired, exec deleted) · `93596906a`
(demo runs, Learn) · `eef4c978f` (pre-lane waiting changes keep their rules) · `68cfb8a38`
(approved bank changes written with the proposer's rights) · the docs commit carrying this
report, the handover and the ledger.

R0 below was written BEFORE the deploy, as the handover asks.

## R0. Rollback note (written before deploying)

- **Files:** the seven previous module trees are kept on the server in
  `/odoo/backups/updates-p3a-<TS>/{pb_records,pb_updates,pb_import,pb_import_advanced,pb_hr_payroll_base,pb_demo,pb_learn}.prev`
  (every one of them was byte-identical to the pre-phase git commit before the copy — tree hashes
  pb_records 5d4cbeccf270d950, pb_updates c1f9ab1985e0defe, pb_import 96e29672f57afae5,
  pb_import_advanced f2be2b3a73ab326a, pb_hr_payroll_base ef8b2675fbac57e1, pb_demo 161089f1bef3e727,
  pb_learn 8f5bd9080383331d). Restore = per-module scoped `rsync -a --delete` of each `.prev`
  tree, `-u pb_records,pb_updates,pb_import,pb_import_advanced` on the five databases, asset signal +
  purge + version bump, restart.
- **Data:** five dumps `/odoo/backups/updates-p3a-<TS>/<db>.pre-updates-p3a.dump`, taken before the
  service stops.
- **What a files-only rollback leaves behind:** one catalogue row `records_bank` ("Bank details from
  Records and Updates") with one published route per active company, two columns on
  `pb_records_apply` (`lane`, `details_now`) and one on `res_company`
  (`pb_records_sheet_details_now`). An old registry ignores them. A bank-details change still
  WAITING on the `records_bank` route must be cancelled first (Updates or Records → Cancel): the old
  code would not know its route and the request could not be decided. The Import screen's old
  "Import Employees" client action is deleted by the upgrade; a files-only rollback brings the tile
  back only after `-u pb_import_advanced` (the action is re-created from the old data file).
- **No new scheduled job.** Nothing to switch off.
- **Owner-visible switch:** "Personal details from a sheet apply without approval" (Updates home,
  for whoever looks after approvals) can be turned off per company without any rollback.

---

## R1. Tests F1-F21

New file `pb_updates/tests/test_updates_p3a.py` (6 classes, 29 cases) in a company of its own:
proposer (HR officer + payroll officer + records editor), second (HR manager, holds Finance),
lead (holds HR lead); Cat has a self-service (portal) login. Four older tests changed because
they WROTE bank details under "No approval needed" and now need a second person first
(`pb_records/tests/bank_second.py` approves as the seat holder; the assertions are otherwise
unchanged): `test_records_r2_desk` 05a/05b, `test_records_r3_roundtrip` 07, the P2a golden
fixture. `test_updates_p2d` X1 turns the new company switch off (it needs a personal-details
change that waits).

| # | Case | Result |
|---|---|---|
| F1 | `test_F1_three_lanes_default_route` — one file (job title, wage, account + bank name) → three proposals under one named update; personal details applied at once (`details_now`, no request); pay on the `records` route with the HR lead seated; bank on `records_bank` with the second person seated and NOT the proposer; title "Bank details for 1 person"; the second-person note on the request; account not written | PASS |
| F2 | `test_F2_no_approval_needed_keeps_bank_waiting` — records "No approval needed": details and pay applied (2 written), bank pending, account not written | PASS |
| F3 | `test_F3_own_records_route_is_followed` (company publishes its own records route → personal details wait on it) and `test_F3b_the_switch` (only an approvals person may turn it off; off → details wait; on → applied) | PASS |
| F4 | `test_F4_proposer_can_never_approve_bank` — proposer with no seat: refused with "Bank details need a second person. You proposed this change…"; seat moved onto the proposer by an approvals admin: same sentence; inbox `act` path: same; write-time rail sentence; nothing written. `test_F4b_a_change_sent_before_lanes_keeps_its_rules` — a bank change already waiting on the records route before this phase is decided exactly as before (sudima's RD00185) | PASS |
| F5 | `test_F5d_a_finance_approver_without_hr_rights` (found on live p0clone, R4: the approved change is written with the proposer's rights); `test_F5_a_second_person_approves` — written, decision by the second person, proposal by the proposer, change rows, approver sees "•••• 6655"; `test_F5b_…no_approval…fails_closed` — the bank route itself set to "No approval needed": request approved but "could not be carried out" with the sentence, nothing written; `test_F5c_finance_is_the_proposer_falls_back` — a records manager stands in | PASS |
| F6 | `test_F6_nobody_else` — a company with nobody else: request blocked "Waiting for a second person. Nobody else in P3A Lone Co can approve bank details yet — add one in Access.", proposal pending, nothing written; the Apply-step outlook says `nobody` | PASS |
| F7 | `test_F7_dated_bank_needs_the_second_person_first` — future date + "everything waits": bank pending (not scheduled); Start now refused; the job on the day writes the (scheduled) personal details only; second person approves → scheduled; a scheduled bank change with its approval gone is refused on Start now; on the day the job writes it | PASS |
| F8 | `test_F8_undo_and_cancel_per_lane` — Past-updates row lists three lanes; Undo personal details only (job title back, wage kept); Cancel the bank lane only; Undo the whole update puts the rest back | PASS |
| F9 | `test_F9_lane_field_list` — every Master-records card is in exactly one lane; bank cards bank, contract and pay items pay, "Payroll Country" pay, job title and manager details; no "Payment method" field exists on this build (R2) | PASS |
| F10 | `test_F10_records_screen_mixed_proposal` — Records grid AND Records import: job title + wage + account → two proposals (details+pay together on `records`, bank on `records_bank`), no relaxation, proposer not seated; History rows carry the lane | PASS |
| F11 | `test_F11_unmixed_records_proposal_is_unchanged` — job title + wage on the Records screen: one proposal, `records` route, pending, as before; an Updates file with pay only: one proposal, pending. The answer gains two keys (`lanes`, `apply_ids`), nothing else changes; every older Records and Updates suite green (R1 bottom line) | PASS |
| F12 | `TestUpdatesP3aEngineInert` — "Other request" (the engine's reference adapter) through a role route and a manager route, run with the new engine seams and again with all three bypassed: state, seats, decisions, steps and every event line identical; the hooks are absent on other models (`getattr(...) is None`). Not leave/pay run: see deviation 8 | PASS |
| F13 | `test_F13_bank_route_seeded_once_and_never_overwritten` — one workflow per company, the catalogue row "connected", re-seed makes nothing new, an edited route stays bound after a re-seed. Live: R4 | PASS |
| F14 | `TestUpdatesP3aPortalManager` — portal-login person as manager from Updates (by employee code), the Records screen and the employee form: recorded, their login stays portal with the same groups, nobody gets them as time-off approver; `test_F14b_manager_step_falls_back` — a "their manager" approval step on a portal manager stops with "No manager is recorded…", as for a manager with no login. Browser: R3 | PASS |
| F15 | `TestUpdatesP3aMonthOnly` — while serving a person's request: a new pay data file with one_time off and auto-create on is stored month-only; switching it back is refused; a draft made before the rule is made month-only before processing; the guided import's `create_and_load` makes a month-only file; outside a request (a job, a script) nothing changes. Unknown person = the batch's own existing row error ("Not in Payobook yet — a one-time file saves nothing, so this row was not paid"); no employee is created | PASS |
| F16 | Out of suite, `f16_capture.py` (P2d's E1 capture) on a fresh copy of the P2d payobook dump: no-file, pay-file (one-time file through the Run Payroll door) and monthly-template runs, create + recompute — pre-phase code vs new code vs new code with the month-only rule active: **6 of 6 identical in all three** (R1a). Live: a month-only door check on a throwaway copy of live payobook (R5) | PASS |
| F17 | `test_F17_connected_system_lane_stays_lasting` — a pay data file made inside the connected-system lane stays lasting while a request is being served; the record refresh runs with the lane token | PASS |
| F18 | `TestUpdatesP3aRetired` — the wizard refuses to start ("…retired. Use People › Updates…"); the dashboards' buttons open Updates; the guided wrapper's action is gone; the Import tile is "Update employees from a sheet" → Updates; no `exec`/`eval` call left in the wizard's source (AST check) | PASS |
| F19 | Out of suite, `f19.py` on local payobook copies: a Manufacturing end-month demo run (January 2027, 3 people) computed by the demo shortcut — pre-phase code and new code give identical payslip hashes (2f09a65c…, 880da7dc…, 446937f8…); with an approved one-off (INLOAN 1,234,000) the person's slip reads 1,234,000 and the one-off is reserved by that slip; the other two slips unchanged. Existing demo runs are never recomputed by this change (live check of run totals: R4) | PASS |
| F20 | Local isolated tree (G13), all suites of touched and affected modules upgraded together: pb_records 134, pb_updates 128, pb_hr_payroll_formula 799, pb_payrun_wizard 106, pb_payroll_templates 105, pb_import_advanced 43, pb_hr_payroll_base 6 = 1,321 → **3 failed + 1 error of 1,135 counted, all pre-existing**: the three P2d listed (`test_records_r1_one_time` 07b, `test_schemectx_currency` 04, `test_run_input_review` monthly duplicate label) and `test_connector_cockpit` 07b (fails the same on the pre-phase tree, run `base1`). pb_learn 480: the same 17 failures as the pre-phase tree (two new ones found and fixed: the practice copy lost the screen's heading). After the last fix: pb_records 134 + pb_updates 130 green locally (F18's action check needs `pb_import_advanced` upgraded in the same run). **Live p0clone after start, ports 8471/8472: 224/224, 0 ERROR** (the first run found 4 failures = the defect fixed in R4). Speed: R2 | PASS |
| F21 | `.po`: both files read by `PoFileReader`; built from `odoo-bin i18n export -l pot`; pb_updates 52 new entries, pb_records 27 (everything new translated; the 4 left in pb_updates are other modules' model names, the 57 in pb_records the pre-existing field labels); no "Odoo" in any new msgid/msgstr (`grep -c Odoo` = 0 in both files) or new visible string (`test_F21_no_vendor_name`) | PASS |

### R1a. F16 — identical payslips (out of suite)

Fresh copy of the P2d payobook dump (4,575 people), Retail end-month scheme, 12 people, December
2026; each mode's hash covers every payslip's inputs, sources, computed values and lines:

| Mode | Pre-phase code | New code | New code, month-only rule active (as in a person's request) |
|---|---|---|---|
| no-file compute / recompute | 4ecfc38110407470 / same | same | same |
| pay data file (one-time, Run Payroll door) create / recompute | d88c66c183d0edd1 / same | same | same |
| monthly template (902 people) create / recompute | f9755a528c321347 / same | same | same |

**6 of 6 identical in all three runs** (and the same hashes P2d's E1 recorded).

## R2. Timings

Local copy of payobook (4,575 people), uid 2, nothing else running, cold / warm:

| Step (4,575 × 73) | P2d | This phase | Target |
|---|---|---|---|
| Sheet | 19.6 s / 14.7 s | 15.3 s / 10.3 s | ≤ 20 s |
| Read the columns | 5.5 s | 4.6 s | — |
| **Review** | 20.9 s / 16.3 s | **13.2 s / 11.9 s** | ≤ 25 s ✔ |
| Answer | 0 changes, 60,074 same, 1,499 unmatched | 0 changes, 60,078 same (the walk's own changes), 1,499 unmatched | — |

The Apply step asks one more question (`lane_outlook`): under a second on a one-person file.

## R3. Browser walk (local copy of live payobook) and screenshots

My own server on a copy of payobook (port 8495, jobs and mail off), Payobook Vietnam JSC (G22),
console read at every step: **no errors**. Signed in locally as the QA user (proposer) and the
`payobook` login (the seated second person) with local-only passwords. Screenshots in
`outputs/updates-p3a/` (not committed):

1. `01-review-lanes` — "This file will make 5 changes for 1 person", the lane strip (Personal
   details 2 · Pay and contract 1 · Bank details 2, each with its rule), lane tags under every
   column heading, the manager column naming a self-service login (DEMO Tran Thi Binh).
2. `02/13-apply-lane-cards` — "What happens to each part": Personal details · change now; Pay and
   contract · change now; Bank details · "Need a second person: Payobook"; button "Apply 2 and
   send 1 for approval" (first pass `02` showed the cards squeezed into one column — fixed to a
   row of three, `13`).
3. `03-done-lanes` — "Sent, part of it for approval", one line per lane with Done / Waiting.
4. `04-past-updates-lanes-and-switch` — the company switch; the update's three lane lines with
   their own chip, Undo and Cancel.
5. `05-inbox-proposer-no-approve-masked` — the proposer opens the bank request: amber "Bank
   details need a second person: QA Test proposed this change…", account shown "•••• 6789", no
   Approve button; a direct call is refused with the sentence.
6. `06-second-person-approve` — the second person's drawer with Approve; approved → written.
7. `07-records-mixed-toast`, `08-records-history-lanes` — Records screen import of job title +
   wage + account: "Pay and contract: 1 changed · Bank details: waiting for a second person (…)";
   History shows the bank row with its tag.
8. `09-import-tile-updates` — Import screen tile "Update employees from a sheet" → Updates.
9. `10-load-pay-data-month-only`, `11-run-payroll-month-only` — the month-only line with Open
   Updates on both pay-file screens.
10. `12-apply-nobody-else` — (local copy, every other approver switched off for the shot) the bank
    card in amber: "Waiting for a second person. Nobody else in Payobook Vietnam JSC can approve
    bank details yet — add one in Access." (restored afterwards).
11. Portal-login manager: DEMO Tran Thi Binh recorded as manager from the file, her login still
    self-service with the same single group (checked in the database).

Found and fixed on the walk: the lane cards squeezed into one column; a Past-updates row repeating
"Waiting for approval with …" above its lane lines; the Records screen calling a details-only
proposal "Pay and contract" when the file's wage was already set; very long approver lists in the
Records toast (now three names "and N more"); the Done page's lane list centred under a left title.

## R4. Deploy evidence (five databases)

Unit `updates-p3a-20261111T135703Z` under `flock /tmp/payobook-studio-deploy.lock`; START 13:57 /
DONE 14:16 UTC in `/opt/deploy-notes.md`. Evidence `/tmp/updates-p3a-20261111T135703Z/`.

- Dry run first: the seven server trees were byte-identical to the pre-phase commit (R0 hashes);
  staged trees = repo, no untracked files.
- **Backups (tier 3), before the stop**: `/odoo/backups/updates-p3a-20261111T135703Z/` — payobook
  80,279,565 B, payobook_template 27,715,954 B, p0clone 28,040,138 B, rize 41,471,719 B, sudima
  27,707,995 B, plus the seven previous trees. Nightly backups untouched.
- `-u pb_records,pb_updates,pb_import,pb_import_advanced` on all five: EXIT=0, **0 ERROR/CRITICAL**
  in every upgrade log. `pb_hr_payroll_base`, `pb_demo`, `pb_learn`: files only.
- **Active scheduled jobs: identical id lists before and after** — 50, 32, 39, 82, 81; nothing
  re-activated, nothing lost, no new job (checked again after the fix and the suite runs).
- Assets: signal row + `/web/assets/%` purge + `web.assets.version` bump on all five.
- **Downtime 4 min 42 s** (13:58:48–14:03:30: five upgrades, each cascading to ~55 dependents).
  **No test in the stopped window** (G19).
- Sites after start: payobook.com, rize, p0clone, sudima 200; server log since start: 0 ERROR.
- payobook pay-run totals (every run's line count and sum): hash `ecc1827c…` before = after.
- **Live p0clone suites after start (ports 8471/8472)**: first run 220/224 — the four bank-writing
  tests found a real defect: on p0clone the Finance holder (the platform support login) has no
  right to change employee records, so the approval's re-evaluation found nothing to write and the
  change read "carried out" with 0 values. Fixed (`68cfb8a38`: an approved bank change is written
  with the proposer's rights, the writer scheduled changes already use; an empty write now fails
  visibly; test F5d) and shipped as a **files-only restart of pb_records + pb_updates**
  (14:19:49, serving within seconds; START/DONE lines; previous trees kept as `*.fix-prev`).
  **Second run: 224/224, 0 ERROR.**

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_records` latest_version | 19.0.1.10.0 | 19.0.1.10.0 | 19.0.1.10.0 | 19.0.1.10.0 | 19.0.1.10.0 |
| `pb_updates` | 19.0.1.4.0 | 19.0.1.4.0 | 19.0.1.4.0 | 19.0.1.4.0 | 19.0.1.4.0 |
| `pb_import` / `pb_import_advanced` | 19.0.1.7.1 / 19.0.1.15.4 | same | same | same | same |
| bank route (active companies) | 4 of 4 (SG Company archived: none) | 1 | 1 | 1 | 1 |
| old "Import Employees" action | gone | gone | gone | gone | gone |
| changes waiting | 0 | 0 | 0 | 0 | 2 (sudima's own, untouched) |
| active jobs before → after | 50 → 50 | 32 → 32 | 39 → 39 | 82 → 82 | 81 → 81 |

Tree hashes (sha256 of sorted per-file sha256, skipping `__pycache__`, `*.pyc`, `.DS_Store`),
repo = server: `pb_records` b26e94f0d136bb07, `pb_updates` e805b8c96b5adbb1 (after the fix),
`pb_import` 5a5a52524d132d0f, `pb_import_advanced` b07f7928933890df, `pb_hr_payroll_base`
dcde682fb07f659f, `pb_demo` 0a275260fd2fa91d, `pb_learn` 5401e237b2aa081e.

## R5. Live check

**payobook, server-side as the QA user, DEMO people** (rehearsed twice on a local copy; log
`outputs/updates-p3a/live-check-log.txt`, not committed):

1. Before: DEMO Nguyen Van An — job "DEMO Senior Agronomist", no manager, wage 25,000,000, no bank
   account; DEMO Tran Thi Binh's login self-service with one group.
2. One file: job title, manager = DEMO Tran Thi Binh (self-service login — D12), wage +1,000,
   account 9900112233. Outlook: details change now, pay change now, bank "Need a second person:
   Payobook".
3. Applied: RD00180 personal details **applied at once**, RD00181 pay applied (company 5 is "No
   approval needed"), RD00182 bank **waiting on `records_bank`**, seated: `payobook` only (not QA).
   Manager recorded; Binh's login unchanged; no account written.
4. QA approves its own bank change: **refused** — "Bank details need a second person. You proposed
   this change, so somebody else has to approve it."
5. The only seated second person is the `payobook` login, an account whose owner is not clear,
   so (as the handover allows) the bank lane was **cancelled** rather than approved as it.
6. Undo of the update: 3 values back. **After = before — RESTORED.** Bank request cancelled.
7. Browser, look only, an existing session: Updates home with the switch and the update's three
   lane lines (Undone · Undone · Cancelled), console clean (`14-live-payobook-past-updates.jpg`).

**Month-only door check on a throwaway copy of live payobook** (`p3ad1check`, restored WITHOUT the
job and mail-server rows, dropped with `--force` straight after — 0 left): as if a person were
uploading, the guided "Load Pay Data" made a month-only file (one-time, no auto-create); a client
write back to lasting was refused; a direct create with lasting flags came out month-only;
processing it: DEMO Nguyen Van An's row processed, the unknown row "Not in Payobook yet — a
one-time file saves nothing, so this row was not paid"; employees 4,575 → 4,575, contracts
4,534 → 4,534.

Nothing applied on rize or sudima; no user or role created anywhere; sudima's two waiting changes
untouched. Left behind on purpose (audit, D10): one named update "P3a live check - three lanes"
with its file, three proposals (two undone, one cancelled) and their audit rows; chatter tracking
on An.

## R6. The lane field list (handover §4.1)

The lane is read off the card id alone (`records_approval.lane_of`), so any stored plan can be
laned again without the catalogue:

| Lane | Cards |
|---|---|
| **Bank details** | every `b:` card — Account number, Bank name, SWIFT / BIC code, Account holder name |
| **Pay and contract** | every `c:` card (pay items, saved contract components); every `f:hr.contract:` field — Wage, Start Date, End Date, End of Trial Period, Probation start date, Contract signed on, Contract Type, Employee Category, Working Schedule, Department and Location on the contract, Cost center, Currency, Tax Identification Number, Salary denomination, the two Vietnam payroll treatments, SHUI Participation; and two employee fields: **Payroll Country** (decides whose payroll rules apply) and Dependent records count (read-only on the record, so never offered — listed for completeness) |
| **Personal details** | every other employee field — Employee Name, Badge ID, Employee Id, Identification No, Job, Job Title (both), Job level, Position reference, Department, Manager, Coach, Work Email, Work Phone, Work Mobile, Work Location, Location, Working Hours (employee), Birthday, Place of Birth, Gender, Marital Status, Nationality, Employee Type, Date of Joining, Certificate Level, Field of Study, School, Private Email/Phone/Street, Permanent and Temporary Address, Emergency contact fields, Passport and Work permit numbers, Visa status, Social Insurance Number, Vietnam Tax Code, Indonesia NPWP / family card / BPJS numbers, Legal given/family name, Vietnamese Full Name, Blood type, Religion |

"Payment method" (P2c §R9.1's example of the word match): there is no field with that label in
the Master-records catalogue on this build (checked on a local copy of payobook: 81 field and
bank cards + 26 pay items). The old word match (`SALARY_TOKENS`) is kept, unchanged, for
`touches_salary` on existing routes; on the employee side it only ever matched "Payroll
Country", which is now explicitly in the pay lane.

## R7. What each lane does on each database (from the deploy on)

Census read-only on the live server before the deploy. "Records managers" = staff logins with
HR manager, payroll manager or system administrator in that company.

| Database / company | Records route | Personal details from a sheet | Pay and contract | Bank details (a second person) | Before this phase, a bank change from a sheet |
|---|---|---|---|---|---|
| payobook · Your Company, Payobook, Payobook Singapore | shipped default (HR lead + Finance on bank; both ash@biztinct.com) | change at once | HR lead (ash) | Finance (ash); if ash proposed it: look.p4 or qa.test | HR lead + Finance (both ash) |
| payobook · Payobook Vietnam JSC (demo world) | "No approval needed" | change at once | change at once | Finance holder is a self-service login (DEMO Tran Thi Binh), so she is skipped; her backup login `payobook` ("Payobook") is asked; if that login proposed: ash, 78avanda, tuan.quach, look.p4, qa.test, DEMO HR Lead | written at once, nobody asked |
| payobook · SG Company | archived company, no route at all | — | — | gets the route on its first bank change | could not be sent |
| payobook_template · My Company | shipped default (both steps platform.recovery@payobook.com) | change at once | platform.recovery | platform.recovery; **if platform.recovery proposed: nobody — waits with the sentence** | platform.recovery twice |
| p0clone · My Company | same as payobook_template | change at once | platform.recovery | same as template | same |
| rize · Rize Farms | "No approval needed" (owner decision 2026-09-22) | change at once | change at once (as today) | Finance (ash); if ash proposed: debalina@rize.farm, thao@rize.farm, wildan@rize.farm, indo@demo, platform.recovery@payobook.com | **written at once, nobody asked** |
| sudima · Sudima Panels Vietnam | its own route ("Sudima HR approval": hr@sudima.local) | **follows that route (not at once)** | hr@sudima.local | Finance (platform.recovery@payobook.com); if that login proposed: hr@sudima.local or ash | hr@sudima.local (also the usual proposer) |

Plainly, for the owner:
- **rize**: bank changes used to go in at once; now each needs a second person. When ash sends one
  in, debalina, thao, wildan, the `indo@demo` login and the platform support login can approve
  it. The independence-off decision (2026-09-18) is not changed: the bank route is new, and the
  second-person rule is enforced by Updates/Records themselves.
- **payobook_template / p0clone / sudima**: the Finance responsibility is held by the platform
  support login (`platform.recovery@payobook.com`). On template and p0clone it is also the only
  records manager, so a bank change it proposes would wait with "Nobody else … can approve bank
  details yet". New tenants are cloned from payobook_template and start the same way.
- **sudima**: its two waiting changes (RD00185 with bank details, RD00186) were sent on the
  records route before this phase and keep exactly the rules they were sent under (test F4b):
  hr@sudima.local can still approve them. Nothing was applied or touched there.

## R8. The engine seams, and proof they are inert elsewhere

No file of `biz_approval_workflow` changed (no engine upgrade). Two opt-in seams are added by
`pb_records/models/records_engine.py` (an `_inherit` of `biz.approval.engine`):

- `_resolve_step_people` asks `record._approval_step_people(step, people, issue, ctx, company)`
  only when the record's model defines it;
- `decide` asks `record._approval_may_decide(request, user)` before an APPROVE, only when defined.

Only `pb.records.apply` defines them, and only a bank proposal answers differently. Proof: F12
runs "Other request" through a role route and a manager route with the seams and with them
bypassed — identical state, seats, decisions, steps and event lines; every older pb_records,
pb_updates and payroll suite passes unchanged (F20).

D12 adds one more seam in `pb_updates/models/updates_managers.py`: for "their manager" /
"their manager's manager" steps, a self-service login is left out; with nobody left the step
stops with the engine's own "No manager is recorded…" sentence. Inert unless a manager's login
is self-service (F12 manager route identical).

## R9. D12 — where the manager role came from

Not Payobook code: the stock time-off module. `hr_holidays/models/hr_employee.py` makes the new
manager's LOGIN the person's time-off approver when the manager changes (`write` :208-218,
`create` :193-206) and adds that login to "Time Off / Responsible" (:221-227), which implies the
staff "Role / User" — a self-service login cannot be both, so the write was refused. `pb_updates`
now keeps the time-off approver (and the expense approver) as they were, in the same write, when
the new manager's login is self-service; a self-service login sent as time-off approver by the
employee form's own recompute is dropped the same way. Nothing bypasses the portal/staff guard:
the grant is never asked for. (The org chart already did this: `pb_orgchart_write.py`,
FOLLOWERS.)

Other places that assume a staff login:
- **Approvals "their manager" step** — would seat the self-service login; now falls back (R8).
- **My Team** (`pb_me_team`) — works from the reporting line with sudo, so a self-service manager
  sees their team on /my; cannot approve there (no approvals access). Unchanged.
- **Org chart** — already avoids granting rights. Unchanged.
- **Time off** (`pb_timeoff/models/hr_leave_approval.py:257`) and **expenses**
  (`pb_me_expense/models/expense_claim.py:264`) have their own manager fallbacks — the other
  session's modules, not changed; reported.

## R10. D1 — every pay-file door found

| Door | Before | Now |
|---|---|---|
| Import screen "Load pay data" → guided import (`pb_import_wizard.create_and_load`); also the Payroll menu's Load Pay Data and Formula Studio's hand-off into it | no flag set → lasting, creates unknown people | month-only (server) + "This file is used for this pay run only…" with Open Updates; "Create as new employee" replaced by "Nobody matches? Add the employee first…" |
| Import screen "Load From Connected System" (same guided import, data-store source) | lasting | month-only (a person loading a period) |
| Run Payroll screen (`pb.payrun.wizard.attach_spreadsheet`) | already one-time on all five (pb_payroll_templates forces it); base default "update" | month-only enforced by the server too; the step's Records line is now the Updates line |
| Any RPC create/write of a pay data file while serving a person | client could set one_time off / auto-create on | forced month-only on create and on write; a draft made earlier is made month-only before processing |
| Connected-system record refresh (`integration_cron._rd54_writeback_from_store`: schedule, "Refresh records now", Run Payroll's "update records from the feed") | lasting (intended) | unchanged — carries the lane token |
| One-off feed (`pb_comp_ben`), demo proration batch (`pb_demo`) | one-time / never processed | unchanged |
| "Keep for future payrolls" (`pb_payroll_templates`) | through the Records Desk | unchanged (laned like any Records proposal) |

The batch model's lasting-write code is untouched. rize has 9 old lasting pay files (August 2026,
"validated", never processed): if anybody processes one, it is made month-only first.

## R11. The old employee import

- `exec()` of the typed "custom validation code" deleted from
  `pb_hr_payroll_base/wizards/employee_import_wizard.py` (Python only; deviation 4).
- The wizard model stays loadable (TransientModel, 0 rows on all five) but cannot be started:
  create / Import / Preview refuse with "This employee import has been retired. Use People ›
  Updates…". Its views live in the base module and are left in place.
- The country payroll dashboards' "Get Employee Data" / "Import employee data" buttons open
  Updates.
- Import screen tile "Import Employees" → "Update employees from a sheet", opening Updates.
- `pb_import_advanced`: the guided wrapper (`pb.import.employee.wizard`, an AbstractModel — no
  table), its screen and its client action are removed (the action is deleted on upgrade).
- Learn: the practice Import screen's tile and every lesson passage about "Update Payobook" vs
  "This run only" (11 passages, English and Vietnamese) now say the file is for this pay run only
  and lasting changes go through People › Updates. Not changed: `pb_payrun_wizard`'s own field
  guide (`learn_manifest.py`, SHEET_MODES) still describes the base screen's two choices — that
  module was not otherwise touched.

## R12. Deviations, and why

1. **The personal-details relaxation applies to Updates only.** On the Records screen a mixed
   proposal splits into personal details + pay (one proposal, the records route, exactly as
   before) and bank (its own route) — up to two proposals, not three. The switch is "Personal
   details from a **sheet**", D3 is the Updates decision, and a details/pay split on the Records
   screen would only double the approver's work. The bank rule cannot be avoided there (F10).
2. **The switch lives on the Updates home**, shown to whoever looks after approvals, not on the
   Approval Matrix screen, which has no per-process switch surface. It explains itself and is
   disabled when the company's records route is its own.
3. **"Shipped default" is detected by behaviour** (`route_kind`): same steps (kind, who,
   condition, minimum amount), tiers and independence rule as `_records_definition`; titles, due
   dates and reminders ignored. "No approval needed" = a `fast` step or no deciding step.
4. **Files-only for three modules**: `pb_hr_payroll_base` (the `exec` deletion), `pb_demo` (the
   one-off seam) and `pb_learn` (JS/JSON) — versions unchanged, not upgraded (a restart loads
   them). Upgrading `pb_hr_payroll_base` cascades through ~150 modules and re-activates jobs; the
   handover allowed avoiding it.
5. **D1 lives in `pb_updates` and is recognised by "a person's web request"**, not in the payroll
   engine (upgrading `pb_hr_payroll_formula` on five databases for it was not needed). Jobs,
   scripts and test cases (no web request) are untouched — why every pay-run suite is unchanged.
6. **The unknown-person sentence** is the batch's existing one, not the handover's new wording
   (changing it means upgrading the payroll engine).
7. **Bank approver count**: under the shipped records route a bank change needed the HR lead AND
   Finance; it now needs ONE second person (Finance, else a records manager), as the handover's
   bank definition says. Approval is kept everywhere and the proposer can never approve their own
   bank change (the old route allowed it wherever the independence rule was off — rize).
8. **F12 used "Other request"** (the engine's reference adapter) with a role and a manager route,
   not leave and pay run: those fixtures live in modules another session is working in or need a
   whole pay-run world; the reference adapter goes through the same engine paths the seams touch.
9. **Changes already waiting keep their rules** (`_bank_rule_applies`): a bank change sent on the
   records route before this phase is decided as before. Found by the census (sudima RD00185,
   whose only approver is also its proposer).
10. **Self-service logins are never seated on the bank route** — payobook's demo Finance holder is
    one; the engine would have seated her.
11. **A demo one-off replaces the generated demo figure** for the same item (no pay data file to
    ask about; D11 is about the file).
12. **A proposal's content is guarded**: plan, request, lane, proposer, company and scheme can only
    be written by the desk itself (sudo); a client write is refused.
13. **An approved bank change is written with the proposer's rights** (the writer scheduled
    changes already use), not the approver's: the second person may be a Finance approver with no
    right to change employee records (found by the live p0clone suite, R4). An empty write fails
    visibly instead of reading "carried out".

## R13. New gotchas (added to the ledger as G39-G46)

See the ledger. In short: `-u pb_records`/`pb_import` cascades to ~55 installed dependents
(incl. the other session's modules); "a person's web request" tells a person's upload from a
job; a Finance responsibility can be held by a self-service login; an archived company is
skipped by every search; Odoo's `assertRaises` takes no tuple; a test-created company belongs to
its creator and gets its responsibilities seeded from them; Learn practice copies are checked
against the base template's headings; a new approval rule must never change the rules under a
change already waiting (sudima).

## R14. Phase 3b research (from the code)

**1. New joiner from a sheet row.** Reuse `pb.people.onboard.wizard.create_employee(vals)`
(`pb_people_advanced/models/people_wizards.py:57-133`; an AbstractModel, takes a dict). It needs
`name` (else `{'error'}`, :61-63) and reads `job_id`, `department_id`, `country_id`, `job_title`,
`parent_id`, `work_email`, `work_phone` (:85-100), `account_number` + `bank_name` (:106-113, errors
swallowed), and `with_contract` + `wage`, `date_start`, `date_end`, `struct_id`,
`structure_type_id`, `resource_calendar_id`, `activate` (:118-128). It does not set `barcode` or
the clock code (follow-up write; `barcode` unique DB-wide `hr/models/hr_employee.py:242-245`; clock
code unique per company `pb_clock/models/hr_employee.py:11-32`). Gate `require_hr`
(`newhire_approval.py:37-51`). **New-hire approval**: unless `pb_newhire_approved_write` is in the
context it calls `pb.newhire.proposal.propose('employee', …)` (`people_wizards.py:64-84`, process
`newhire`, `newhire_approval.py:34,59`) → `engine.submit` (`biz_approval_workflow/models/proposal.py:256-296`).
Pending → returns `employee_id=0, pending=True, reference` (nothing created; the sheet row must keep
the reference); "No approval needed" → created in the same call through the approved apply
(`newhire_approval.py:108-115`); no route → `UserError`. Employee and contract are one proposal.
Contract: `pb.people.contract.wizard.create_contract` (`people_wizards.py:159-213`): wage
(missing → 0, :191), start (default today), calendar (company's), `state='open'` only with
`activate`; overlap rail `hr_contract/models/hr_contract.py:114-127`; errors returned, not raised.
**"Pay scheme" column**: `pb.scheme.map.resolve_many` (`pb_scheme_map/models/pb_scheme_map.py:338-457`)
resolves by: a confirmed work segment naming a scheme → the person's DEPARTMENT, then its parents
(map rows `hr.formula.scheme.assignment`, `department_id`) → the department chain's division →
a rule-domain row → the company's only active scheme → none (`RUNGS` :67). It never keys on job or
team directly; the department comes from the open contract, else the employee. So a "Pay scheme"
column cannot be set on the person: it has to be checked against (or used to pick) a department
that already resolves to that scheme; after creating, `resolve_many([id], cycle)` must return the
column's scheme, else the row is refused (creating a map row would re-map a whole department).

**2. A draft that survives closing the browser.** `pb.updates.batch` (`pb_updates/models/updates_batch.py:35-58`
+ `kind`/`period_month` in `updates_oneoff.py:618-625`) already holds name, company, user, date,
filename and the file (`attachment_id`, the `ir.attachment` pattern of `apply`,
`updates_desk.py:896-905`). Missing: a stored state (`draft`; today the state is derived from the
applies and an apply-less batch reads "Applied", `_batch_state` `updates_desk.py:917-954`), a JSON
for the column choice (what `_clean_columns` reads, :205), a JSON for the on-screen fixes and
choices (`changes`, `start_date`, `hold_scope`, `stats`), history/Past-updates filters that skip
drafts (`get_history` :1044-1050), and a way to discard one (unlink is system-only today,
`security/ir.model.access.csv`). Record rules: company only (`updates_rules.xml:10-14`); a draft
needs a per-user rule (`['|', ('state','!=','draft'), ('user_id','=',user.id)]`).
`pb.updates.layout` is a per-company column memory and should not hold drafts.

**3. "What changed since the last finished pay run", per person.** Last finished run per person:
`hr.payslip` grouped by employee, `state='done'`, `date_to:max` (the `paid_since` query,
`pb_updates/models/updates_dates.py:328-360`; no `paid` state on this build,
`om_hr_payroll/models/hr_payslip.py:53-60`). Hook: `hr.payroll.preparation._workspace`
(`pb_hr_payroll_formula/models/payroll_preparation.py:353-430`), extended the way
`pb_records/models/records_payrun.py:33-34,85-93` adds `scheduled_changes`. Sources:
(a) written values — `pb.records.change` (`pb_records_change.py:67-93`; no company column, filter
through `apply_id.company_id`): `employee_id=E, apply_id.applied, (effective_date > last[E] or
create_date > last[E])`, decide whether undone ones show; (b) one-offs — `pb.updates.oneoff`
(`updates_oneoff.py:118-179`): `employee_id in P, company, period_month = run month, state in
(pending, approved, reserved)`; (c) scheduled changes — `pb.records.apply` `state='scheduled',
start_date <= period end` (add a company filter, `records_payrun.py:42-56` has none), matched per
person through `plan()`; (d) pay-item history `hr.contract.advantage.change`
(`contract_component_change.py:6-75`): by `effective_date`/`changed_at` after `last[E]` — but a
Records write also writes one of these (`change_source='manual'`), so de-duplicate against (a) by
person, code and date, or show (d) only for other sources.

## R15. Needs an owner decision / owner action

1. **Who approves bank details on the template and its clones.** On payobook_template, p0clone and
   sudima the Finance responsibility is held by the platform support login
   (`platform.recovery@payobook.com`); on template and p0clone it is the only one who could ever
   approve a bank change, and a bank change it proposes itself waits with "nobody else". New
   tenants start from the template. Decide who should hold Finance there (and per new tenant).
2. **rize**: bank changes from a sheet or the Records screen now need a second person; when ash
   proposes, the people who can approve are debalina, thao, wildan, the `indo@demo` login and the
   platform support login. Is `indo@demo` (and the platform login) somebody who should approve
   rize's bank details? (Nothing was changed on rize's people or roles.)
3. **payobook demo world**: its Finance holder is a self-service login (DEMO Tran Thi Binh), so the
   bank second person is her backup, the `payobook` login. If demos should show a named finance
   person approving, give Finance to a staff demo login.
4. **Bank approvals need one person now where the shipped route asked two** (HR lead + Finance) —
   deviation 7. Say if bank changes should need both.
5. Live check left one more entry in payobook's Past updates ("P3a live check - three lanes",
   undone/cancelled; D10).
