# UPDATES — Phase 2c report (start dates, scheduled changes, Cancel, employee look-ups)

Implemented, tested, deployed and checked live on 2026-11-11 by the Opus implementation
agent, against `UPDATES_P2C_HANDOVER.md` and `UPDATES_LEDGER.md`.

**Shipped:** `pb_records` 19.0.1.9.0 and `pb_updates` 19.0.1.2.0, plus one static template line in
`pb_payrun_wizard` (version 19.0.1.43.0 unchanged), live on `payobook`, `payobook_template`,
`p0clone`, `rize`, `sudima`. Never `abm`, `pbf_preview`, `recruit_connect_20261023`.

Commits: `5bdec279a` (Records Desk: dates, job, Start now, Cancel, look-ups, pay-run notice) ·
`b24ff1308` (Updates screens and server) · the docs commit carrying this report, the handover
and the ledger.

R0 below was written BEFORE the deploy, as the handover asks; `<TS>` = `20261111T072003Z`.

## R0. Rollback note (written before deploying)

- **Files:** the previous module trees are kept on the server in
  `/odoo/backups/updates-p2c-<TS>/{pb_records,pb_updates,pb_payrun_wizard}.prev`; in git they are
  the parent of `5bdec279a` (`54c5c78c1`). Restore = per-module scoped `rsync -a --delete` of
  the `.prev` tree, `-u pb_records,pb_updates` on the five databases, asset purge + signal.
- **Data:** five dumps `/odoo/backups/updates-p2c-<TS>/<db>.pre-updates-p2c.dump` taken
  before the service stops.
- **Files-only rollback is safe** while no change is `scheduled` or `cancelled`: the new
  columns (`start_date`, `hold_scope`, `started_by_*`, `cancelled_*`, `start_fail_*`,
  `pb_records_change.effective_date`) are additive. If any row is `scheduled`/`cancelled`,
  either cancel/flip them first or restore the dumps (an old registry has no such state).
- **The new job** ("Records: start scheduled changes", `pb_records.ir_cron_records_start_scheduled`)
  can be switched off by itself on any database without touching anything else.


---

## R1. Tests C1-C21

New files: `pb_records/tests/test_records_p2c_dates.py` (22 tests: `TestRecordsP2cDates` 17,
`TestRecordsP2cRoute` 3 with a real approval route, `TestRecordsP2cPayrun` 2) and
`pb_updates/tests/test_updates_p2c.py` (13 tests). Both run in a company of their own in Ho Chi
Minh City (UTC+7) with a frozen clock (`pb.records.apply._records_now`, today = 11 Nov 2026).

| # | Case | Result |
|---|---|---|
| C1 | `test_C1_no_date_and_today_take_todays_path` — no date and today's date both store NO start date, both `applied` at once, identical audit shape (field, old/new JSON, model), effective date = today on audit rows and component history. P2a golden + every older suite green. Updates: `test_C13c_no_date_is_the_old_call` (no `parts`, the old single call) | PASS |
| C2 | `test_C2_a_past_date_is_written_now_and_recorded_with_it` — written now (2 values), audit rows and component history dated 1 Oct 2026; undo restores, its rows stamped today | PASS |
| C3 | `test_C3_a_future_date_is_held` — `scheduled`, `applied` false, no audit rows, values unchanged, answer `scheduled: True, pending: False`; `test_C3b_bounds` — 2028 refused ("up to a year back or a year ahead"), nothing proposed; 366 days ahead allowed; "soon" refused ("is not a date") | PASS |
| C4 | `TestRecordsP2cRoute.test_C4_approved_then_scheduled` — pending → HR lead approves → `scheduled`, nothing written; on the day the job writes it (as the last approver, because the proposer's login is the inactive system user — the fallback in `_start_user`) | PASS |
| C5 | `test_C5_the_job_writes_it_on_the_day` — before the day: `{}`; on the day `{'started': 1}`, `applied`, `started_by_job`, `started_by_id` = proposer, employee `write_uid` = proposer, effective date 1 Dec 2026 on audit + component history; a second run does nothing | PASS |
| C6 | `test_C6_…ahead_of_utc` — 23:00 30 Nov HCMC: nothing; 00:30 1 Dec HCMC (17:30 UTC 30 Nov): written. `test_C6b_…behind_utc` — company in New York: 22:00 30 Nov NY (03:00 UTC 1 Dec): nothing; 00:30 1 Dec NY: written | PASS |
| C7 | `test_C7_moved_since_sends_it_back_and_tells_the_proposer` — job `{'returned': 1}`, nothing written, block note "…changed by somebody else…", a To-do activity for the proposer on the change's approval request, next run does nothing | PASS |
| C8 | `test_C8_one_failure_never_stops_the_rest` — `_write_plan` made to fail for one of two: `{'failed': 1, 'started': 1}`, the other written, the failed one stays `scheduled` with "Could not be started on …; it will be tried again", one bad day counted once per day, third day → `returned` + activity | PASS |
| C9 | `test_C9_start_now` — written today, effective date today, start date kept, `started_by_job` false, the job later does nothing, a second Start now refused. `test_C9b` — Start now on a conflict answers the sentence and leaves it scheduled | PASS |
| C10 | In suite: `test_C10_locked_by_somebody_else_writes_nothing` (lock held → Start now `busy`, job `{'busy': 1}`, nothing written). **Real two-connection race** (outside the suite, ledger G26; script `c10_race.py` on a throwaway local copy that commits): A = Start now `started`, B = the job while A holds the row `busy`, B after A committed `gone`; **1 change row, state applied — exactly one write** | PASS |
| C11 | `test_C11_cancel_a_scheduled_change` — `cancelled`, cancelled by the proposer, job/approval/Start now write nothing, values unchanged, second cancel refused. `test_C11b_…pending…` — request withdrawn through the engine (`cancelled`), a late approve raises, `_approval_apply` raises, job writes nothing. `test_C11c_who_may_cancel` — an HR user who is not proposer/approver/manager is refused | PASS |
| C12 | `test_C12_undo_on_an_unwritten_change_cancels_it` (scheduled) and `test_C12b_…pending…` — undo answers "Cancelled before anything was changed.", state `cancelled`, NO empty undo row, NO `undone` mark, request withdrawn, never written afterwards | PASS |
| C13 | `test_C13_pay_waits_personal_details_change_today` — job titles written now (own apply), wage + pay item scheduled (own apply), one batch, Past updates "Part applied, part scheduled for …", Coming up lists it; on the day the rest is written. `test_C13b_everything_waits` — one scheduled apply, `hold_scope='all'`, Undo answers "Cancel the scheduled part instead" | PASS |
| C14 | `test_C14_per_row_dates` — 3 dates (past/future/future) → 3 applies in one batch, the past one written now and stamped; start column not listed as "not brought in". `test_C14b_seven_dates_are_refused` — "This file has 7 different start dates. Split it into files of at most 6." | PASS |
| C15 | `test_C15_unreadable_and_far_dates` — "'next week' is not a date. Use a date like 1 Dec 2026." refuses that row's contract value only (job title still ok); 2029 refused with the reach sentence; apply with a 2028 default refused. `test_C15b_date_shapes` (ISO, ISO with time, "1 Dec 2026", month-first in English, day-first in Vietnamese, a bare number refused). `test_C15c` — a real spreadsheet date; "Effective date" guessed as the start column. `test_C15d` — the start column is remembered | PASS |
| C16 | `TestRecordsP2cPayrun.test_C16_…` — scheduled inside the period → one line "4 scheduled changes start on …, inside this pay period. They are not in this pay run unless you start them now." (4 values, 2 people); after the period → not mentioned; cancelled → not mentioned. `test_C16b_…` — a waiting-for-approval proposal keeps exactly "Saved record change is waiting for approval."; a cancelled one is worded as cancelled | PASS |
| C17 | `test_C17_manager_by_code_email_and_name` — code (any case, stray spaces), work email (any case), unique name, coach too; namesakes: Records screen keeps "Pick the right one on the Records screen…", a file gets "2 people are called 'P2C Twin'. Type the employee code or work email of the right one instead."; nobody: "Nobody is called 'Nobody P2C'. Check the spelling, or use their employee code or work email."; employee count unchanged | PASS |
| C18 | In suite: `test_C18_history_shows_scheduled_and_cancelled`. **Before/after capture** on a local copy of payobook (4,575 people; dump 02:06 UTC today), pre-phase code vs new code (`c18.py`): `get_fields(0)`, card count, `get_fields(scheme)`, export cells, export sheets, the Records import's items, grid apply answer and written counts, import apply written counts, the per-value audit trail, undo, history — **13 of 15 identical**; the 2 that differ (`peek`, `import_answer`) differ ONLY in one sentence: a manager typed in the Records screen's own import file whose name two people share now reads "2 people are called 'DEMO Joiner Quyen'. Type the employee code or work email of the right one instead." (§4.5, allowed) | PASS |
| C19 | `test_C19_off_scheme_and_clear_on_a_scheduled_change` — Bob's off-scheme value dropped at proposal; Ann's scheme-only pay item (unknown to the plain Records catalogue) and CLEAR on the contract end date scheduled; on the day the job writes both exactly as proposed (door context reopened), Bob still has no line; undo restores both | PASS |
| C20 | Local isolated tree (G13): **169/169** (`pb_records` 116 = 94 + 22, `pb_updates` 53 = 40 + 13; P2a golden green with the counted D9 rewrite). Live `p0clone` after start, `--http-port 8471`: **169/169, 0 ERROR lines**. Speed: R2 | PASS |
| C21 | `.po`: both files read by `PoFileReader`; entries built from `odoo-bin i18n export -l pot` (G2/G6); `pb_updates` 408/408 translated; `pb_records` every new string translated (56 older field labels untranslated, pre-existing, plus the preparation model's own description); three obsolete entries removed after wording changes; no "Odoo" in any new msgid/msgstr or visible string (cron name "Records: start scheduled changes") | PASS |

## R2. Timings

Local copy of payobook (4,575 people), uid 2, same machine, two runs (cold / warm):

| Step (4,575 × 73) | Pre-phase code | This phase | Target |
|---|---|---|---|
| Sheet | 18.8 s / 12.5 s | 19.3 s / 12.4 s | ≤ 20 s |
| Read the columns | 5.1 s / 5.3 s | 5.3 s / 5.0 s | — |
| Review | 13.9 s / 14.0 s | 14.0 s / 13.8 s | ≤ 25 s ✔ |
| Answer | 0 changes, 60,074 same, 1,499 unmatched | identical | — |

Live check (QA login, 1-row files): each apply/undo/cancel/Start now under a second.

## R3. Browser walk (local copy) and screenshots

Local copy of payobook, my own local server (port 8495), active company Payobook Vietnam JSC
(G22), console read at every step: **no errors**. Screenshots in `outputs/updates-p2c/` (not
committed):

1. `01-match-start-date-column.jpg` — "Effective date" guessed as "Start date for this row"
   ("When it starts", calendar-clock), "Best guess. Please check".
2. `02-review-starts-column-chips.jpg` — "This file will make 5 changes for 3 people. 1 cell
   needs your attention."; pinned Starts column (1 Dec 2026 indigo, 1 Oct 2026 amber with the
   "Pay runs already finished are not recalculated" tooltip, "Not a date" rose); chips "Starts
   later · 1", "Dated in the past · 1"; manager found by work email. Fix row on the refused cell:
   "'next week' is not a date… The value itself is fine: correct the date in your file and upload
   it again, or leave this one out." (no input box — nothing to retype).
   (`02-review-starts-before-offset-fix.jpg` shows the 25 px overlap found and fixed.)
3. `03-apply-when-card.jpg` — "When do these changes start?" Today / Pick a date, the two
   hold choices, live summary "3 values change today · 1 is scheduled for 1 Dec 2026 · 1 is
   recorded as starting 1 Oct 2026", button "Apply and schedule 5 changes"; date bounds
   10 Nov 2025 – 12 Nov 2027.
4. `08-apply-past-date-paid-note.jpg` — two people paid to 31 Oct, default 1 Oct: amber "2 of
   these people have already been paid for a period after this date. Finished pay runs are not
   recalculated, and back pay is not added automatically."; button "Apply 2 changes".
5. `06-done-mixed.jpg` — "2 changes are in for 2 people · 2 values changed today · 2 values
   are scheduled for 15 Dec 2026", the Coming-up note, "Undo what was applied".
6. `04-home-coming-up.jpg`, `05-coming-up-and-past-updates-states.jpg` — Coming up (calendar
   leaf, "Starts in 34 days", Start now, Cancel); Past updates "Scheduled for 4 Jan 2027",
   "Part applied, part scheduled for 15 Dec 2026" with "Undo what was applied" and "Cancel the
   scheduled part", "Cancelled … Nothing was changed.", the started-early and cancelled notes.
7. Start now (confirm dialog, then "… has started. 1 value was changed."), Withdraw (a waiting
   part: "The approval request is withdrawn…"), Cancel ("2 values cancelled before anything
   was changed.").
8. `07-records-history-scheduled-cancelled.jpg` — Records History: "Scheduled for 15 Dec
   2026" with Cancel, "Cancelled" (button "Nothing to undo").
9. The pay data review template is loaded with its new line (checked in the page's template
   registry); the dialog itself needs the application-data pay mode, which payobook does not
   use — its sentence is proven by C16.

Found and fixed on the walk: the pinned column offset (theme is border-box); a row with an
unreadable date counted on screen as "today" while the server gives its personal values the
default date (screen now follows the server); the done screen said "5 changes are waiting"
when only part was; the Start-now dialog's grammar; the withdraw dialog counted the whole
update instead of the waiting part; a person counted twice across parts; "recorded as starting
1 Dec" for a change started early; a cancelled row on the Records screen still read "Undo".

## R4. Deploy evidence (five databases)

Unit `updates-p2c-20261111T072003Z` under `flock /tmp/payobook-studio-deploy.lock`; START 07:20 /
DONE 07:27 UTC in `/opt/deploy-notes.md`. Evidence `/tmp/updates-p2c-20261111T072003Z/`.

- Dry run first: exactly the 28 files of this phase differ (`git diff --name-only 54c5c78c1
  HEAD` = 28); the server's three trees were byte-identical to the pre-phase commit before the
  copy (pb_records 27cf2ad6…, pb_updates 605d5ad3…, pb_payrun_wizard 06831a14…).
- **Backups (tier 3), before the stop**: `/odoo/backups/updates-p2c-20261111T072003Z/` —
  payobook 80,361,450 B, payobook_template 27,598,281 B, p0clone 27,922,228 B, rize 41,562,260 B,
  sudima 28,819,615 B (`*.pre-updates-p2c.dump`), plus the three previous module trees. Nightly
  backups untouched.
- `-u pb_records,pb_updates` on all five: EXIT=0, **0 ERROR/CRITICAL** in every upgrade log.
  9 new columns present on all five. `pb_payrun_wizard`: static template only, no upgrade, assets.
- **Active scheduled jobs: +1 on each and nothing else** — 49→50, 31→32, 38→39, 81→82, 80→81;
  the +1 is "Records: start scheduled changes" (one per database, active, first run 07:24 with
  nothing to do); no job re-activated, none lost.
- Assets: signal row + `/web/assets/%` purge + `web.assets.version` bump on all five.
- **Downtime 1 min 37 s** (07:21:30–07:23:07). **No test in the stopped window** (G19).
- Sites after start: payobook.com, rize, p0clone, sudima 200. Server log since start: 0 ERROR,
  0 Traceback.

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| `pb_records` latest_version | 19.0.1.9.0 | 19.0.1.9.0 | 19.0.1.9.0 | 19.0.1.9.0 | 19.0.1.9.0 |
| `pb_updates` latest_version | 19.0.1.2.0 | 19.0.1.2.0 | 19.0.1.2.0 | 19.0.1.2.0 | 19.0.1.2.0 |
| `pb_payrun_wizard` | 19.0.1.43.0 | 19.0.1.43.0 | 19.0.1.43.0 | 19.0.1.43.0 | 19.0.1.43.0 |
| new job | 1, active | 1, active | 1, active | 1, active | 1, active |
| changes scheduled after the check | 0 | 0 | 0 | 0 | 0 |

Tree hashes (sha256 of sorted per-file sha256, skipping `__pycache__`, `*.pyc`, `.DS_Store`),
repo = server: `pb_records` 395cce71331c3c70, `pb_updates` e70c180c7d627d18,
`pb_payrun_wizard` 24ad51fc6a42a9ef.

## R5. Live check (payobook, server-side as the QA user, DEMO people)

Rehearsed first on a local copy. Log: `outputs/updates-p2c/live-walk-log.txt` (not committed).

1. Before: DEMO Nguyen Van An job "DEMO Senior Agronomist", pay item MCLNGHL 0; DEMO Tran Thi
   Binh job "DEMO Senior Agronomist", MCLNGHL 0. Changes scheduled on payobook: 0.
2. (a) Past date: An MCLNGHL 777,000 from 1 Oct 2026 → applied at once (RD00174), audit and
   component history dated 2026-10-01 → Undo → **restored**.
3. (b) Future date: Binh MCLNGHL 888,000 from 1 Dec 2026 → `scheduled` (RD00176), listed in
   Coming up → job run by hand: `{}`, nothing written → **Cancel** ("Cancelled before anything
   was changed.") → job again: `{}`, nothing written.
4. (c) Future date, everything waits: An job title → `scheduled` (RD00177) → **Start now**:
   written, recorded as starting 11 Nov 2026 (start date 1 Dec kept) → Undo → **restored**.
5. After = before; changes scheduled on payobook: 0 — **RESTORED**.
6. Browser, look only, existing session: payobook People › Updates shows the three entries
   ("Undone · Put back…", "Cancelled · Nothing was changed.") with no Coming-up card; console
   clean (`09-live-payobook-past-updates.jpg`). sudima: Updates opens, "No updates yet", console
   clean (`10-live-sudima-home.jpg`). Nothing applied or scheduled on rize or sudima; sudima's
   two waiting changes untouched.

Left behind on purpose (audit, not data; D10): three named updates (two Undone, one
Cancelled) with their files, the desk's apply/undo rows and per-value audit rows, 2 component
history rows on An's contract (0 → 777,000 → 0), chatter tracking on An. No demo data deleted.

## R6. What the two pay-run preparation sites did before and do now

- **Site 1, `_apply_row` (`pb_hr_payroll_formula/models/payroll_preparation.py:197`, the
  check at `:209-214`).** A preparation correction saved "for future runs" creates a Records
  proposal; while that proposal is not carried out the cell is a blocker "Saved record change
  is waiting for approval." Unchanged for waiting. A preparation never makes a dated proposal,
  so it can never be scheduled. NEW: when that proposal was **cancelled**, the same blocker now
  says "The saved record change was cancelled. Restore the source value, or enter the
  correction again." (override in `pb_records/models/records_payrun.py`).
- **Site 2, `_save_cells` (`:550-553`).** Replacing a correction whose proposal is draft or
  waiting is refused. Unchanged (a cancelled proposal could already be replaced).
- **New notice** (`records_payrun.py`, extends `_workspace`): `scheduled_changes` — one line
  per start date for scheduled changes touching people in the run and starting on or before
  the period's last day; never a blocker; after the period / cancelled / waiting: not mentioned.
  Shown in "Review pay data" by one template line (`pb_payrun_wizard/static/src/xml/payroll_review.xml`).

## R7. Which engine method withdraws a request

`biz.approval.engine.cancel(request, reason)` (`biz_approval_workflow/models/engine.py:1458`):
submitter or approval admin only (called under `sudo()` after the desk's own gate in
`cancel_apply`), open states only, closes seats, then calls the record's
`_approval_withdraw` (`adapter.py:173`), which `pb.records.apply` now implements (state
`cancelled`). No new engine hook was needed. Ledger U19.

## R8. Deviations, and why

1. **Pay-run notice lives in `pb_records`** (extends `hr.payroll.preparation`) rather than a
   file change in `pb_hr_payroll_formula`: a version bump there means `-u` of the payroll engine
   and every module depending on it on five databases, for a sentence. `pb_hr_payroll_formula`
   is unchanged. The one screen line is a static template in `pb_payrun_wizard`, deployed as
   looks-only (version unchanged, assets purged).
2. **Activity on the approval request**, not on the change itself: `pb.records.apply` is not a
   mail document and `mail.activity` needs one (G28); making it one would add chatter rows to
   every change and alter today's path. Quiet (no email).
3. **Start now runs as the person pressing** (their rights, recorded in `started_by_id`); the
   job runs as the proposer (fallback: last approver). A conflict on Start now only answers the
   reason and leaves the change scheduled — a person pressing early never sends someone else's
   change back.
4. **Stricter than asked**: besides the moved-since check, the scheduled write refuses if the
   evaluation would now refuse a planned value or add one nobody planned (`_plan_drift`), or if
   the write itself refuses any row — nothing is kept (today's approval path keeps the rest).
5. **The approvals screen calls a scheduled change's request "carried out"** (the engine marks a
   request applied as soon as `_approval_apply` returns; G29). Records and Updates show
   "Scheduled". Not changed: it is engine-wide.
6. **C10's real race runs outside the suite** (G26), with an in-suite lock test.
7. **P2a golden**: the file is untouched; test A9 applies exactly the D9 rewrite (manager
   "Nobody P2A" → refused) and asserts how many rows it rewrote.
8. **Records screen**: Cancel is offered on scheduled changes (where Undo would have hit the
   defect); waiting-for-approval keeps "See the request". Undo pressed on any unwritten change
   cancels it. Updates adds "Withdraw" for a waiting update (§4.3 allows cancelling pending).
9. **"Records manager"** read as HR manager, payroll manager or system administrator.
10. **Read-me line** is added whenever a manager or coach column is in the sheet, so a sheet
    without pay items now also gets a short "Read me" sheet (the import reads "Records" by name).
11. A row whose own date cannot be read: its contract and pay values are refused; its personal
    values take the default date like any undated row (screen and server agree).

New ledger entries: U19, U20, G25-G30.

## R9. Phase 3 research (from the code)

**1. One proposal's bank changes to a second person, pay changes on the pay route.**
`pb.records.apply` does NOT split: one `apply_changes` → one row → one request
(`pb_records_desk.py` `apply_changes`; whole plan written all-or-none by `_write_plan`).
`touches_bank` (any `b:` card) and `touches_salary` (a token match on field id + label —
`SALARY_TOKENS`, so "Payment method" counts as pay) are whole-proposal facts
(`_plan_touches`; stored `records_approval.py:53-54`, facts in `_approval_context`). Routes are
chosen per company + process + scope (division or company) + kind (`desk`/`import`) by
`engine._resolve_binding` (`engine.py:57-152`); a step's condition is one typed fact test
(`engine._step_included` `:318`, `definition.condition_holds` `definition.py:441-475`). The
default records route already has "Finance when touches_bank" + `independent` + `repeated:
'different'` (`records_approval.py` `_records_definition`) — but Finance then approves the
whole proposal, and "a different person" only moves a seat to a named backup, else it warns
(`_conflict_swap` `engine.py:468-531`, `_repeated_issue` `:565-587`; `decide` does not block a
repeat). One record cannot hold two live requests (`approval_request_id` = latest attempt,
`adapter.py:43-53`; validate refuses pending). **So P3 should split the file into two applies**
(bank `b:*` vs the rest — the same mechanism P2c uses for dates) and give the bank apply its own
process key via `_approval_process_key_for` (precedent `payroll_import_approval.py:58-69`);
enforcing "a different person" strictly needs a small `decide` check.

**2. Creating an employee + first contract from a row.** `hr.contract` is this repo's
`hr_contract` (`hr_contract/models/hr_contract.py:18-21`). Required: name, `date_start`
(default today), `wage` (no default), company (from the employee), working hours (required by
`om_hr_payroll/models/hr_contract.py:64`, default the company's), contract type (required,
defaults to the first type — create fails if none, `:72-74`); no overlapping running contract
(`hr_contract.py:114-143`); component bounds (`om_hr_payroll/models/hr_contract.py:31-43`);
country minimum wage in VN/SG modules; on create the scheme's usual pay items are filled in
(`contract_fill_in.py:432-437`). Employee: name + company (resource, version created by
`hr_employee.py:1341-1356`); unique barcode (`:242-245`); unique clock code per company
(`pb_clock/models/hr_employee.py:17-31`). `pb_people` itself creates nothing: "Add employee"
opens `pb_onboard_wizard` → `pb.people.onboard.wizard.create_employee`
(`pb_people_advanced/models/people_wizards.py:57-133`, new-hire approval first, contract
`:159-213`). **The old employee import** is `employee.import.wizard`
(`pb_hr_payroll_base/wizards/employee_import_wizard.py:17`, action
`pb_hr_payroll_base.action_employee_import_wizard`), opened from the country payroll dashboard
and, guided, from the Import screen's "Import Employees" tile (`pb_import_advanced.action_pb_employee_wizard`,
`pb_import/models/pb_import.py:58-59`, client action `pb_import.action_pb_import`); it creates
employees, departments/jobs by name and a contract each (`:541-658`, `:699-729`). It reads/writes
`employee_number` and a contract `payroll_country_code` that do not exist in this build, so it
likely fails at runtime (not run), and it `exec()`s a user-typed "custom validation code"
(`:509-516`) — a security concern to remove with the retirement.

**3. Where the pay data file writes lasting values.** `hr.payroll.import.batch` in
`pb_hr_payroll_formula/models/payroll_import_batch.py`, switched by `one_time`
(`:298-304`, read `:1572`): when NOT one-time it creates employees for unknown rows
(`_create_employee` `:1739-1820`, needs `auto_create_employees`) and contracts
(`_create_contract` `:1822-1885`), writes employee fields from mappings AND from header
guesses with no mapping (`_update_employee_from_raw_data` `:3599-3694`), contract fields
(`:3729-3762`), mirrored job/department/calendar on both (`:2350-2402`), creates missing
linked records (`_coerce_mapped_value` `:2030-2052`), stamps `pb_source_ref` (`:1309-1324`),
bank accounts/partners/banks (`:3472-3597`), and contract pay-item lines + templates + history
rows, even copying a contract for "requires new contract" items (`_sync_contract_components`
`:5322-5471`, `:5303-5320`). **`one_time=True` already skips all of these** (`:1604-1672`).
`pb_payroll_templates` forces `one_time=True` on every pay-run upload
(`run_input_review.py:329-336`, `templates.py:1130-1147`) and sends "Keep for future payrolls"
through `pb.records.desk.apply_changes` (`run_input_review.py:214-249`). Still able to write
lasting values: the Import screen's "Load Pay Data" (`pb_import.py:47-48`), `pb_payrun_wizard`
without `pb_payroll_templates` (front-end default "update", `payrun_wizard.js:51`), and the
connected-system lane (`integration_cron.py:531`, intentionally lasting). **D1 = force
`one_time` (and both auto-create flags off) on those doors.**

## R10. Needs an owner decision / owner action

1. **Making a portal-login person a manager fails on payobook.** On the walk, setting DEMO Tran
   Thi Binh as someone's manager made the whole "today" part stop ("cannot be at the same time
   in Role / Portal and Role / User"): giving a manager a staff role clashes with her employee
   (portal) login. Existing behaviour (the Records screen does the same); the update then shows
   "Waiting for approval" while the approval is actually done and the write refused. Decide
   whether managers with portal logins should be upgraded, refused with a sentence, or allowed.
2. **The approvals screen says "carried out" for a scheduled change** (G29). Want the engine to
   learn a "scheduled" word? (engine-wide change, all processes.)
3. **When an approved change cannot be written** (any process), Updates/Records keep showing
   "Waiting for approval"; the reason sits on the approval request only. Worth a follow-up so the
   reason reaches the person who sent it.
4. The live check left three more entries in payobook's Past updates (kept per D10).
