# UPDATES — Phase 3b report (new employees from a sheet, drafts, "since the last pay run")

Implemented, tested, deployed and checked live on 2026-11-11/12 by the Opus implementation agent
against `UPDATES_P3B_HANDOVER.md` and `UPDATES_LEDGER.md`.

**Shipped:** `pb_updates` 19.0.1.5.0 only (it now also depends on `pb_people_advanced`, installed
on all five databases). No other module changed: `pb_records`, `pb_people_advanced`,
`pb_payrun_wizard`, `pb_hr_payroll_formula`, `pb_scheme_map` untouched — every seam is an override
inside `pb_updates` (the new-hire hook, the preparation workspace, the Review-pay-data template).

R0 below was written BEFORE the deploy, as the handover asks.

## R0. Rollback note (written before deploying)

- **Files:** the previous `pb_updates` tree is kept on the server in
  `/odoo/backups/updates-p3b-<TS>/pb_updates.prev` (git `9ead02446`, P3a). Restore = scoped
  `rsync -a --delete` of that tree into `/odoo/odoo-server/addons/pb_updates/`, `-u pb_updates` on
  the five databases, asset signal + purge + version bump, restart.
- **Data:** five dumps `/odoo/backups/updates-p3b-<TS>/<db>.pre-updates-p3b.dump`, taken before the
  service stops.
- **What a files-only rollback leaves behind:** one new table `pb_updates_joiner`, five new columns
  on `pb_updates_batch` (`state`, `draft_columns`, `draft_choices`, `draft_saved_at`, `draft_step`)
  and two record rules (`rule_pb_updates_batch_draft_owner`, `rule_pb_updates_joiner_company`). An
  old registry ignores the columns and the table; the draft rule references a column the old
  registry does not know, so after a files-only rollback **delete that rule** (or restore the
  dumps). Drafts (`state='draft'` batches) would then show as empty Past updates — delete them
  first (`DELETE FROM pb_updates_batch WHERE state='draft'`, attachments with them).
- **People already added from a sheet stay** (a person is never removed by a rollback). New-hire
  requests sent from a sheet and still waiting are ordinary requests of the existing new-hire route:
  approving one after a rollback still creates the person (the onboarding module's own apply), but
  the rest of that row (pay items, bank) is no longer sent — the `pb.updates.joiner` row keeps it.
- **No new scheduled job.** Nothing to switch off.
- **No switch to flip:** nothing is on by default. Adding new employees is a per-file choice the
  person makes on the review; a file nobody switches it on for behaves exactly as before.

---

## R1. Tests H1-H16

New file `pb_updates/tests/test_updates_p3b.py` — 21 tests in four classes, on the P3a fixture
(own company, proposer / second / lead; Ann, Bob, Cat with contracts) plus three teams: Kitchen
(paid under "P3B Monthly", pay item P3BX), Dining ("P3B Daily") and Garden (no scheme; two active
schemes, so no "only scheme" fallback). New test people are named "DEMO …".

| # | Case | Result |
|---|---|---|
| H1 | `test_H1_toggle_off_is_today` — a file with an existing person and an unknown one, no add-as-new: the unknown row is "matches nobody" with no new key (`scheme` absent without the column), apply answers exactly as before (no `joiners` key), nobody created, no joiner rows; `joiners=[]` is the same call | PASS |
| H2 | `test_H2_no_approval_route` — new-hire route "No approval needed": the wizard's `create_employee` is called (spied) WITHOUT the approved-write key; person in Kitchen, code P3BN01 written, one contract (wage 15,000,000, start 1 Dec 2026), joiner `created` with its applied proposal; the pay item goes through the pay lane of the same update (the new person is in its plan); bank `pending`, second person seated, proposer not seated, account not written | PASS |
| H3 | `test_H3_approval_route_then_hook` — HR-lead route: nothing created, joiner `waiting` with `NEW…` reference; the lead approves → person exists, joiner `created`, values sent (`cells_done`), code written, pay and bank lanes filed under the SAME update and proposed by the proposer (bank pending). `test_H3b_turned_down` — rejected → joiner `turned_down`, nobody created. `test_H3c_apply_now_when_the_follow_up_failed` — the follow-up made to fail: the hire stands, joiner `needs_attention` "Hired. … still to apply", listed on the home with Apply now; Apply now sends them, `created` | PASS |
| H4 | `test_H4_duplicates_refused` — existing code (archived Cat), name + team (Ann), archived name + team (Cat, "(archived)"), twice in the file (both rows), a request already waiting ("already waiting for approval (NEW…)"), an existing work email (Bob): each refused with its sentence, nothing addable; apply refused, counts unchanged | PASS |
| H5 | `test_H5_unknowns_bad_date_bad_wage` — unknown team, unknown job, unknown manager ("Nobody is called…"), "next week", 2029, "-5", "abc": each cell refused with its sentence; apply refused; employees, contracts, departments and jobs unchanged | PASS |
| H6 | `test_H6_pay_scheme_column` — Kitchen + "P3B Monthly" addable; Kitchen + "P3B Daily" refused "P3B Kitchen is paid under P3B Monthly, not P3B Daily. Change the team or the pay scheme column."; Garden (no scheme) + anything addable with "No pay scheme covers P3B Garden yet…"; two added; scheme-map rows before = after; the "Pay scheme" heading reads as the check (and is remembered) | PASS |
| H7 | `test_H7_no_wage_no_contract` — no wage column: addable, `no_contract`; the person is created with no contract | PASS |
| H8 | `test_H8_more_than_200` — 201 new rows: `judge_joiners` and `apply` refuse "…At most 200 can be added from one file…", nothing created. `test_H8b_copies_do_not_count_towards_200` — 199 new + 5 copies of Ann: allowed, the 5 refused as copies (G50) | PASS |
| H9 | `test_H9_undo_keeps_new_people` — one update changes Ann's job title and adds a person: Undo puts Ann back, the new person stays (exists, active); Past updates still lists the joiner | PASS |
| H10 | `test_H10_no_back_door` — `pb_newhire_approved_write` is a guarded key and the web door drops it from an Updates call (`scrub_params`); called with the key in the context anyway, apply still sends a REQUEST (nobody created); a client cannot create a `pb.updates.joiner` row (AccessError); the Updates source never creates an employee or contract row itself | PASS |
| H11 | `test_H11_draft_private_and_continued` — saved with file, columns, fixes and the matched map; a second save merges and keeps the same record; listed for its owner only (another user's list, search and open find nothing); open returns the same file, fixes and step; a person archived meanwhile makes his row "matches nobody" on the re-read and the saved map names him (the screen's notice — browser R3) | PASS |
| H12 | `test_H12_draft_becomes_the_update` — a draft is never in Past updates or counted; applying it returns the SAME batch id, now `sent`, renamed, ONE attachment; no draft left; Discard removes the record and its file; someone else's draft: refused for an HR user, allowed for a records manager; a non-draft batch without parts still reads "Applied". `test_H12b_oneoff_draft_kind` — a one-off sheet saves as a one-off draft with its month | PASS |
| H13 | `test_H13_five_sources` — on a preparation (Ann/Bob/Cat paid to 31 Oct, Dan never paid, contract from 5 Nov): written changes (pay item once — the contract-history copy de-duplicated — wage under "contract", "by P3A Proposer"), bank masked "•••• 6655" (neither number shown), an undone change hidden, a change before the last pay run hidden, a one-off for November, a scheduled change inside the period, contract pay-item history from an import, "New: DEMO P3B Dan…"; line "Since the last pay run: 4 people have changes (…1 new)". `test_H13b_never_paid_since_contract_start` | PASS |
| H14 | `test_H14_nothing_to_show_adds_no_key` — with nothing to show the workspace answer has exactly the keys it had before this phase (`since_last_run` absent); with one change it appears. Speed: R2 | PASS |
| H15 | Every older suite, all touched/extended modules upgraded together on an isolated HEAD tree (G13): pb_hr_payroll_formula 799, pb_payroll_templates 105, pb_payrun_wizard 106, pb_records 134, pb_updates 158 → **1,120 counted, 3 failed — the same three pre-existing failures P2d and P3a recorded** (`test_records_r1_one_time` 07b, `test_schemectx_currency` 04, `test_run_input_review` monthly duplicate label). pb_approval_config (the new-hire matrix tests) 9/9. Final pb_updates after the last fixes: 159, only F18 fails when `pb_import_advanced` is not upgraded in the same run (P3a's documented note). **Live p0clone after start, ports 8471/8472: pb_updates 159/159, 0 failed.** Review 4,575 × 73: R2 | PASS |
| H16 | `.po`: built from `odoo-bin i18n export -l pot` (G2/G6); 197 new entries, all translated except four other modules' model names (as in P3a); `PoFileReader` reads 886 entries; `grep -c Odoo` = 0 in the `.po`; `test_H16_no_vendor_name_in_new_strings` scans the new files; split template sentences rewritten as whole sentences first (`More drafts (%s)`, `From “%s”`) | PASS |
| — | `test_blank_new_employee_sheet` — headings only (Employee code, Name, Work email, the new-employee columns, the scheme's pay items, "Pay scheme" last), a "Read me" sheet, no vendor name in the file name; filled in and read back it is a Payobook sheet (no matching step) with the check column placed | PASS |

## R2. Timings

Local copy of live payobook (4,575 people), same machine.

| What | Result | Budget |
|---|---|---|
| Lasting sheet 4,575 × 73 | 16.5 s / 10.9 s (cold / warm) | ≤ 20 s |
| Read the columns | 4.6 s / 4.4 s | — |
| **Review 4,575 × 73** | **13.1 s / 11.8 s**; 0 changes, 60,120 same, 1,499 match nobody (namesakes, as before) | ≤ 25 s ✔ |
| Judge as new employees: 1 row / 200 rows | 1.0 s / 1.9 s | — |
| Judge the 1,499 namesake rows of a full sheet | 6.1 s, all refused as copies, none counted towards 200 (was 67 s and a wrongful 200 refusal before G50) | — |
| **"Since the last pay run" on 4,551 people** | **0.29–0.59 s** added (three runs) | ≤ 1.5 s ✔ |
| Same on live payobook, an existing demo run (520 people), read only | 0.12 s | — |

## R3. Browser walk (local copy of live payobook) and screenshots

My own server on a copy of payobook (port 8596, jobs and mail off), Payobook Vietnam JSC (G22),
console read at every step. Signed in locally as the QA user (proposer) and the `payobook` login
(the HR lead of a new-hire route published on the copy for the walk) with local-only passwords.
Screenshots in `outputs/updates-p3b/` (not committed):

1. `01-start-blank-new-employee-sheet` — Start, Lasting changes: the third way in, "Blank sheet for
   new employees", pay items of a chosen scheme, Download.
2. `02-home-draft-after-reload` — the browser reloaded after a file was read: "Continue where you
   left off · p3b-walk-new-people.csv · Lasting changes · Stopped at: Match columns · saved 1 minute
   ago", Continue / Discard.
3. `03-match-pay-scheme-check` — continued at Match; Team → Department and the contract start date
   matched by hand; "Pay scheme" → "Pay scheme (a check for new employees)", "Checks new
   employees"; "Draft saved at 02:17" under the stepper.
4. `04-review-choice-off` — "This file will make 1 change for 1 person. 5 rows need your
   attention."; the choice card "Add these 5 people as new employees" (off); "Nobody is created
   from a file unless you switch on adding new employees above."
5. `05-review-new-employees-on`, `06-review-grid-new-employees` — switched on: "It also adds 2 new
   employees"; the namesake row stays below with "To add … the row needs a team and a contract
   start date"; the grid's "New employees" group (user-plus) above "Already here": DEMO Lan Pham
   "Will be added" with her scheme; DEMO Minh Tran "Needs a fix first" (red team cell); DEMO Quang
   Vo "No contract yet: no wage in the file"; DEMO Thu Nguyen's unknown team red; the meal pay item
   greyed for Lan (not in the Retail scheme — G23, by design).
6. `07-fix-team-scheme-mismatch`, `08-fixed-team-will-be-added` — Minh's team cell: "Logistics /
   Dispatch is paid under Payobook Logistics — End-Month Payroll, … not Payobook Retail — End-Month
   Payroll. Change the team or the pay scheme column."; typed "Retail / E-commerce" → green tick,
   "3 will be added".
7. Closed → "Kept as a draft…" toast; home: "Stopped at: Review changes · saved just now".
   **Bùi Công Hùng archived on the copy**, Continue → `09-draft-continued-notice`: "Continued from
   your draft, read again against today's records. • Since this draft was saved, Bùi Công Hùng
   (row 2) is no longer on record or no longer matches that row. The row now matches nobody."; the
   toggle and Minh's team fix were put back ("3 new employees").
8. `10-apply-new-employees-card` — fourth card "New employees · 3 new employees · Added now, each
   with a first contract. No approval needed."; amber "Adding a new employee cannot be undone
   here…"; button "Add 3 new employees".
9. `11-done-three-added` — "3 new employees added", one line each ("Added, starts 12/01/2026").
   Database: the draft batch (id 12) became the update (state sent, ONE attachment); codes
   P3BW01-03 written; Lan and Minh with contracts 12,000,000 / 11,000,000; Quang no contract.
10. `12-past-updates-new-employees` — Past updates: the three people with "Added", the
    not-undoable note.
11. HR-lead route published for the walk: `13-apply-new-hire-request-card` ("One new-hire request
    each, to Payobook", "Send 1 new-hire request"), `14-done-request-sent` ("1 new-hire request
    sent", "Waiting for approval (NEW00005) with Payobook"), `15-home-new-employees-waiting`.
12. Second person: `16-second-person-approves-new-hire` — the approvals inbox drawer "Add DEMO Hoa
    Le to the payroll" (the onboarding module's own screen) → Approve. Database: the joiner row
    `created`, values sent, one contract.
13. `17-review-pay-data-since-line`, `18-since-last-run-panel`, `19-since-panel-filter-one-off` —
    Run Payroll → Retail end-month (application data switched on for the scheme on the copy only)
    → Review pay data: "Since the last pay run: 2 people have changes (1 pay, 2 one-off) · Show
    them"; the side panel with search, chips "All 2 · pay 1 · one-off 2", one block per person,
    "For your information. Nothing here changes a figure or stops the pay run.", "Download as a
    sheet"; the one-off chip filters.

Found and fixed on the walk: a template calling `String()` blanked the screen (G47); the panel's
xpath on a dynamic class (G48); "Don't add" sat inline on a short row; the choice card counted
refused rows; "Applying 0 changes…" while only sending requests; the Done icon showed a tick for
requests only; Past updates' line did not say "3 new employees"; two draft saves raced (G51);
the since-last-run names came out blank on an in-memory preparation (G52); bank NAMES were masked
along with account numbers; contract history repeated an undone Records change.

## R4. Deploy evidence (five databases)

Unit `updates-p3b-20261111T155339Z` under `flock /tmp/payobook-studio-deploy.lock` (free; the other
session's last deploy line was P3a's own at 14:20); START 15:53 / DONE lines in
`/opt/deploy-notes.md`. Evidence `/tmp/updates-p3b-20261111T155339Z/`.

- Dry run first: the server's `pb_updates` tree was byte-identical to the pre-phase commit
  (tree hash 02bfe8c30f4c36d7 = git `9ead02446`); the staged tree = repo `cac39aad1`
  (8936cd5cc3465122). Only `pb_updates` deployed; no standard addon, no other module.
- **Backups (tier 3), before the stop**: `/odoo/backups/updates-p3b-20261111T155339Z/` — payobook
  80,464,096 B, payobook_template 27,723,783 B, p0clone 28,047,580 B, rize 41,482,098 B, sudima
  27,710,968 B (`*.pre-updates-p3b.dump`), plus `pb_updates.prev`. Nightly backups untouched.
- `-u pb_updates` on all five: EXIT=0, **0 ERROR/CRITICAL** in every upgrade log.
- **Active scheduled jobs: identical id lists before and after** — 50, 32, 39, 82, 81; nothing
  re-activated, nothing lost, no new job.
- Assets: signal row + `/web/assets/%` purge + `web.assets.version` bump on all five.
- **Downtime 1 min 29 s** (service stopped 15:55:10, listening again 15:56:39). **No test in the
  stopped window** (G19).
- Sites after start: payobook.com, p0clone, rize, sudima 200. Server log since start: 0 ERROR.
- payobook pay-run totals (every run's line count and sum): hash `ecc1827c…` before = after.
- Employees, contracts, Updates batches and outgoing-mail counts before = after on all five
  (payobook 4,575 / 4,534 / 8 / 610; template 3 / 0 / 0 / 0; p0clone 14 / 7 / 0 / 34; rize 258 /
  247 / 0 / 830; sudima 653 / 650 / 0 / 18).
- **Live p0clone suite after start (ports 8471/8472): pb_updates 159/159, 0 failed.**

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_updates` latest_version | 19.0.1.5.0 | 19.0.1.5.0 | 19.0.1.5.0 | 19.0.1.5.0 | 19.0.1.5.0 |
| table `pb_updates_joiner` | yes | yes | yes | yes | yes |
| new record rules | 2 | 2 | 2 | 2 | 2 |
| existing updates read `sent` | 8 of 8 | — | — | — | — |
| active jobs before → after | 50 → 50 | 32 → 32 | 39 → 39 | 82 → 82 | 81 → 81 |

Tree hash (sha256 of sorted per-file sha256, skipping `__pycache__`, `*.pyc`, `.DS_Store`), repo =
server: `pb_updates` 8936cd5cc3465122.

## R5. Live checks

**payobook, server-side as the QA user** (rehearsed on the local copy first; log
`outputs/updates-p3b/live-check-log.txt`, not committed). Net zero:

1. Before: employees 4,575, contracts 4,534, named updates 8, drafts 0, new-employee rows 0.
2. A draft saved (file, columns, step "review"), listed for QA, opened (same file and step), not in
   Past updates, discarded; drafts after: none.
3. A file with one unknown row and the add-as-new choice OFF: the review shows "Nobody here matches
   nobody.p3b.live@example.invalid." exactly as before (no new key); Apply answers "There is
   nothing to apply: no value in this file would change anything." — nothing created.
4. "Since the last pay run", read only on an in-memory preparation for the latest demo run
   (Payobook Logistics — End-Month Payroll · October 2026, 520 people): 0.12 s, "Since the last pay
   run: 7 people have changes (7 new)".
5. After = before — **RESTORED**. Browser, look only, an existing session:
   `20-live-payobook-start-blank-sheet` — Updates home and Start with the blank new-employee sheet,
   console clean.

**The new-employee WRITE, on a throwaway copy of live payobook** (`p3bjcheck`, dumped WITHOUT the
job, job-trigger and mail-server rows: 0 jobs, 0 mail servers; dropped with `--force` straight
after, its file folder removed; 0 left): as the QA user, company Payobook Vietnam JSC ("No
approval needed"), a file of three new rows with a "Pay scheme" column:
- DEMO P3b Copy One (Retail / E-commerce, Payobook Retail — End-Month Payroll): added through
  `create_employee` — reference NEW00002, code P3BC01, contract 10,000,000 from 1 Dec 2026 (open);
  `pb.scheme.map.resolve_many` on the new person answers **Payobook Retail — End-Month Payroll,
  "from Retail's team map"** — the department check and the pay run's own resolver agree;
- DEMO P3b Copy Two (Logistics / Dispatch + Retail scheme): refused "Logistics / Dispatch is paid
  under Payobook Logistics — End-Month Payroll, Payobook Logistics — Mid-Month Advance, not Payobook
  Retail — End-Month Payroll. Change the team or the pay scheme column.";
- DEMO P3b Copy Three (Retail / Nowhere): refused "No department is called 'Retail / Nowhere'…";
- employees 4,575 → 4,576, contracts 4,534 → 4,535; Undo of that update: "Nothing in this update
  can be undone." and the person stays.

Nothing applied on rize or sudima; no user, role or person created anywhere live.

## R6. The hook, and why (handover §3.3)

**Built: the hook**, with Apply now as the fallback. `pb.newhire.proposal._approval_apply` is the
clean seam: the engine calls it when the hire is approved, the onboarding module's own apply runs
first (`super()`), and only then does `PbNewHireProposalUpdates` (in `pb_updates`) look for
waiting `pb.updates.joiner` rows of that request. It reads the new person from the request's own
result, writes the employee code, and sends the row's other values through the lanes of the SAME
named update **as the person who sent the file** (`with_user(proposer)`, the proposer's company), in
a savepoint. Nothing in `pb_people_advanced` changed. If the follow-up fails (a value refused as a
whole, rights gone), the hire still stands, the row reads "Hired. N values from the sheet are still
to apply: <why>" on the update and on the home, and **Apply now** sends them again — read against
today's record — as the person pressing. Turned down / sent back mark the row; nothing else
happens. A request approved before this module was upgraded is caught on reading (`_joiner_sync`).

## R7. What adding new employees does on each database (census 2026-11-11)

| Database / company | New-hire route | A sheet's new people |
|---|---|---|
| payobook · Payobook Vietnam JSC (demo world) | "No approval needed" | added at once, each with a first contract |
| payobook · Your Company, Payobook, Payobook Singapore | "New people and first contracts" (HR lead) | one request each to the HR lead |
| payobook_template · My Company | HR lead | one request each |
| p0clone · My Company | HR lead | one request each |
| rize · Rize Farms | **"No approval needed"** | **added at once** |
| sudima · Sudima Panels Vietnam | HR lead | one request each |

Nothing is on by default anywhere: it happens only for a file whose sender switches it on. On rize,
a person in HR who switches it on adds people straight away (owner item R11.1). Adding people needs
the HR role (the onboarding wizard's own gate); a payroll officer without it sees the choice
refused with "Adding new employees is for HR…".

## R8. "Since the last pay run" — which run screens show it

Only the application-data pay run's "Review pay data" worksheet has a preparation surface (the same
one that shows P2c's scheduled-changes notice), so that is where the line and panel are. **Only rize
runs application-data pay runs today**; payobook, payobook_template, p0clone and sudima run with or
without a pay data file, and the Run Payroll screen of those modes has no preparation surface —
reported, not invented (handover §5). The walk switched application data on for one scheme of the
local copy to show it.

## R9. Research for P4 (from the code)

**1. Attendance and timesheets today.**
- Attendance file import, one row per day: `pb.attendance.import.wizard`
  (`pb_attendance_flow/wizards/attendance_import.py:44`), opened from the Attendance screen
  (`pb_attendance_flow/views/attendance_flow_action.xml:3`, cockpit `import_parse/validate/commit`
  `pb_attendance_flow/models/attendance_cockpit.py:603-624`). Columns employee, date, check_in,
  check_out (`:33`, check_out optional `:256`); person found by badge ID or name only (`:190-208`);
  writes `hr.attendance` with `pb_entry_source='import'`, skips overlaps (`:375-386`); cap 2,000
  rows. Hours = check_out − check_in; no OT column.
- Clock punches: `pb_clock` extends the same wizard with `mode='punches'`
  (`pb_clock/wizards/attendance_import.py:92-110`): a machine `attlog.dat`, the attendance program's
  daily sheet (`source='mitaco_export'`, `:552`) or any table with a clock number and a date/time
  (`:47-61`), cap 20,000; rows go to the punch ledger (`_ingest`, `:178`). Machines push to
  `/iclock` (`pb_clock/controllers/iclock.py:67`).
- What `pb_clock` expects: ledger `pb.clock.punch` (`pb_clock/models/clock_punch.py:65`),
  append-only except matching fields (`:52`): `user_code`, `punch_local`, `punch_utc`, `direction`,
  `source`, `state` (`:33-49`, `:70-98`); `dedup_key` = sha1(company, device or 'upload', user code,
  local time to the second) with a UNIQUE constraint (`:57-61`, `:100`). The clock number is
  `hr.employee.pb_clock_code`, unique per company (`pb_clock/models/hr_employee.py:11`, `:17-31`);
  matching clock number → badge → ID number (`pb_clock/models/clock_pairing.py:230-246`); pairing
  writes `hr.attendance` first-in/last-out with `pb_entry_source='device'`
  (`clock_pairing.py:1-31`, `pb_clock/models/hr_attendance.py:17`).
- Other doors: the week grid (`pb_hr_workforce/models/hr_attendance.py:16`; its OT becomes
  `hr.overtime.request`, `attendance_weekentry.py:593`), self-service (`pb_ess_workforce/models/hr_attendance.py:27`),
  and the connected-system pull (`pb_hr_payroll_formula/wizards/integration_sync_wizard.py:47` →
  `hr.api.data.store`, `integration_connector.py:1609-1626`) which nothing turns into attendance.
- Timesheet approval: `pb.timesheet.packet`, one per person per week
  (`pb_timesheet_approval/models/timesheet_packet.py:62`), states draft/pending/approved/returned/
  rejected (`:41-47`), a snapshot of `reg_hours`, `ot_*_hours`, `bonus_hours`, `days_with_hours`
  and a `source_hash` (`:89-107`); approver = the person's manager, skip level = manager's manager
  (`:554-568`), through the shared engine (`:63`). Pay reads only APPROVED weeks whose Monday falls
  in the period (`:802-819`); company switches `pb_timesheet_payroll` (on) and
  `pb_timesheet_block_run` (off) (`res_company.py:22-35`), warnings/blocks at `payrun_wizard.py:29`, `:69`.
- What a pay run reads for time: `hr.payslip._get_formula_input_values`
  (`pb_hr_payroll_formula/models/hr_payslip_formula.py:609`), `WD_x`/`HOURS_x` from worked-days
  lines (`:746-757`); approved OT requests (`pb_workforce_payroll_bridge/models/hr_payslip.py:28`,
  code map `:9`); approved packets override REGHRS, TOTHRS, WORKDAYS, OT and BONHRS
  (`pb_timesheet_approval/models/hr_payslip.py:42-46`, `:69-114`); application data with
  `payroll_basis='timesheet'` (`application_payroll_source.py:204`) reads
  `period.regular_work_hours/days` and `period.ot.<kind>.approved_hours` (`:324-336`) checked
  against packets and attendance (`:541-575`, `:604`, unapproved attendance flagged `:558`); hours
  can also come as pay-data-file columns or `hr.payroll.period.input` rows.

**2. Leave balances and opening balances.**
- Balances are the standard `hr.leave.allocation` only; the Time Off screen
  (`pb_timeoff/views/pb_timeoff_action.xml:4`) computes validated allocations − validated leave
  (`pb_timeoff/models/pb_timeoff.py:298-338`). No custom balance table; accrual plans unused.
- Policy layer: `pb.leave.policy.edition` (`pb_timeoff/models/rize_policy.py:71`, `carry_cap` `:87`)
  writes `pb.leave.policy.posting` rows (`:649`) of kind annual/carry/opening (`:658`) with
  `opening_carried_days`, `opening_taken_days`, `cutover_date` (`:661-663`), unique `posting_key`
  (`:671`); each posting creates an approved allocation (`_create_posting` `:348-365`), frozen
  afterwards (`:695-719`).
- **Opening balance today: one person and one leave type at a time** —
  `post_opening_balance(employee, leave_type, cutover_date, available_days, carried_days,
  taken_year_to_date, review_reference)` (`rize_policy.py:367-394`; refuses when allocations
  overlap the cutover `:384-388`; only `available_days` becomes allocation days), through the
  wizard `pb.leave.policy.operation` operation 'opening' (`:1107-1146`) on "Entitlement and Exit
  Operations" (`pb_timeoff/views/rize_policy_views.xml:35-37`). No bulk file import, although two
  sentences already say "Import reviewed opening balances" (`:291`, `:423`). January rollover:
  `pb.leave.policy.year.opening` (`pb_timeoff/models/policy_year_opening.py:11`, job `:93-121`,
  refuses mid-year joiners `:43-44`). Payroll reads `leave.annual/sick.balance` and entitlement
  (`application_domain_sources.py:72-75` → `_pb_policy_payroll_metrics`, `rize_policy.py:821`).
  (`pb_timeoff` is the other session's module — a P4 leave sheet would have to call its methods,
  not change them.)

**3. Year-to-date pay figures for a mid-year start.**
- **No store exists**: no ytd / year-to-date / previous-employer / prior-income model or field in
  `om_hr_payroll`, `pb_hr_payroll_formula` or the country modules; the only previous-employer data
  are two text fields (`pb_hr_payroll_vietnam/models/hr_employee_vietnam.py:68-69`).
- What is computed instead: a `history.ytd.<CODE>` source for every money/quantity component
  (`pb_hr_payroll_formula/models/application_domain_sources.py:187-193`) —
  `_application_history_value` (`:476-517`) sums `formula_computed_values[code]` of DONE payslips of
  the same scheme from the later of 1 January and `date_of_joining` (`:482-484`; field
  `pb_hr_payroll_formula/models/hr_employee.py:31`), so a mid-year joiner's earlier income is left
  out by design; with no payslips it answers `posted_history_or_opening_balances_missing`
  (`:492-493`) — an "opening balance" it has nowhere to read from. Legacy: `payslip.sum(code, from,
  to)` over done lines (`om_hr_payroll/models/hr_payslip.py:574-583`).
- What formulas read: Indonesia PPh21 and Malaysia PCB packs annualise this month × 12
  (`pb_pack_id/data/config_template_id.xml:18`, `pb_pack_my/data/config_template_my.xml:18`),
  Singapore the same (`pb_hr_payroll_singapore/models/hr_payslip_singapore.py:128`); Malaysia's
  `pcb_tax` sums PCB lines (`hr_payslip_malaysia.py:55-64`). None reads prior income.
- Existing hooks: `pb_blueprint`'s per-component `<CODE>YTD` input ("already exempt this year",
  `recipe_schema.py:117-123`, `:182`; `recipe_compiler.py:443-446`); the December / leaving-month
  reminder to "fill in the year-to-date figures" (`application_payroll_source.py:880`,
  `payroll_preparation.py:311-344`, `:375`). Today such a figure can only arrive as an ordinary
  input column (pay data file or `hr.payroll.period.input`).
- So for P4: a YTD sheet needs a new store (per person × year × component, "opening balance")
  that `_application_history_value` adds to its sum — a change inside the payroll engine.

## R10. Deviations, and why

1. **One feature commit** for the three parts (`cac39aad1`): they share the Updates screen files
   (desk controller, review grid, template, styles, `.po`), so per-feature commits would each have
   been half a screen. The docs commit is separate.
2. **The employee code goes to the badge field** (`barcode`, the code the Updates sheet reads
   first), written right after the person exists (the new-hire call takes no code); a code
   somebody already has is refused by the record itself and the person stays, with a note. **No
   clock number is written**: the clock module reads the employee code when the clock number is
   blank (its own help text).
3. **The team's scheme check asks three of the map's rungs** — the team map (deepest team first),
   the team's division, the company's only scheme — for every kind of run. A work segment names a
   person and a map rule reads a person's record, so neither can be asked before the person exists:
   a team covered only by a rule reads "no pay scheme yet" (allowed with the note). On the payobook
   copy the check and `resolve_many` on the new person agreed (R5).
4. **A shared name alone is never a copy.** Copies are code, work email or name + team (archived
   people included); those rows, and rows without a name / team / start date, are refused before
   any cell is judged and do not count towards the 200 (G50). Without this, a full sheet of payobook
   (1,499 namesake rows) could never use the choice.
5. **The contract starts "in force"**, as "Add employee" does by default (`activate`).
6. **The rest of a new person's row is judged as far as it can be without a record** (numbers,
   choices, dates, bank) and judged again by the Records Desk when sent; contract fields without a
   wage are refused ("No contract yet…"). Pay items not in the team's scheme are greyed (D5).
7. **All or none under "No approval needed"**: anything refused after people were created raises,
   so the people go back too (one transaction). Values the desk refuses one by one are reported, as
   for existing people.
8. **"New" in the pay-run panel** = never paid, and first contract start (or the day the record was
   made) after the scheme's last finished payslip.
9. **Drafts are saved for people who can apply** (viewers can only read named updates); the screen
   saves the matched-people map once, at Review, so the continue notice can name people archived
   since. The panel's "Download as a sheet" is a CSV built in the browser.
10. **The new-employee write was checked on a throwaway copy only** (handover §7); live payobook
    got the draft, the choice-off file and the read-only panel payload.

## R11. Needs an owner decision / owner action

1. **rize adds new people from a sheet at once.** Its new-hire route is "No approval needed"
   (payobook's demo company too). Nothing happens unless someone in HR switches the choice on for a
   file — but then the people are on the payroll straight away. Decide whether rize's new hires
   should go to an HR lead first.
2. **Whoever approves new-hire requests needs the contract right.** The last approver makes the
   person and the contract as themselves; without "contract manager" the person is created but the
   contract is not ("The contract could not be made…", shown on the row) — existing behaviour of
   "Add employee" too. On payobook_template, p0clone and sudima the HR lead is the platform support
   login or hr@sudima.local; worth checking they hold it.
3. **Existing, not this phase:** the "Review pay data" worksheet took ~90 s to open for 902 demo
   people on the local copy, and a second open while the first was loading answered with a
   duplicate-key error ("payroll_preparation_open_scope"). Worth its own look.
4. P4 inputs (R9): leave opening balances can only be set one person at a time today; there is no
   store for year-to-date pay figures — a YTD sheet needs a change inside the payroll engine.
5. Live checks left nothing behind on payobook (the draft was discarded; the choice-off file
   changed nothing).

## R12. New gotchas (ledger G47-G53)

A template calling a JS global blanks the screen; a template xpath cannot match a dynamic class;
the new-hire approver needs the contract right; namesake rows and the 200 cap; racing draft saves;
`new()` preparations and record ids; int-keyed `dict(**…)`.
