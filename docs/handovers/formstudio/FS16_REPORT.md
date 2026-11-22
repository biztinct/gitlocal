# FS-16 — New hire writes bank details to the right place; dead fields leave the builder and the product

Builder, tester, self-reviewer and deployer, 2026-11-21/22 (UTC). Handover `FS16_HANDOVER.md` (main checkout,
untracked). Branch `fs-16` from `origin/19.1`; held by the owner at first ("BUILT, HELD" instructions), released
2026-11-21 22:00 UTC (RELEASE line in the deploy notes); rebased on `origin/19.1` @ `ba9320440` (Codex "Premium
Org Chart", which touched `pb_form_studio_people` — version conflict resolved to 19.0.1.8.1, its changes kept), then merged
`origin/19.1` @ `fb1e86add` (Codex "Org Hierarchy", 23:32–23:34 UTC, assets of `pb_form_studio_people` only) — no force-push.

**Result:** **LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima; abm untouched) at code commit
`7cb8fb591`, **479 s down** (00:08:30–00:16:29 UTC, 2026-11-22). Deploy notes: START 2026-11-21 23:56, DONE 00:16, NOTE
00:20. Try 1 (23:56) waited (Rize in use until 23:45); try 2 (00:08) went live. No other deployer's START open; the
Codex lock file of 22:16 was stale (its run VERIFIED 22:23, then a further Codex run 23:32–23:34 closed DONE) and is
removed. Nothing changed on any screen except the three FS-16 changes (§5).

## 1. Verified facts (do not re-derive)
* The new-hire screen (People › Add employee, `pb_people_advanced` `OnboardWizard`) had **no bank inputs at all**:
  `account_number` / `bank_name` sat in the form state as `""` and `create_employee` wrote them to the two old
  boxes inside a bare `except: pass`. So today nothing typed on screen ever reached them — the defect was the
  door itself (any caller passing bank values wrote to boxes nothing reads). Updates joiners
  (`pb_updates/models/updates_joiners.py` `CONSUMED`) never pass bank keys to the call.
* `pb_people_advanced` does not depend on `pb_bank_ocr`; the bridge is probed (`'pb.bank.change.request' in env`).
* The approval engine counts a record's `create_uid` as one of its makers (`chain_shim._chain_context`
  `maker_uids`) and refuses a maker's approve ("You were part of preparing…"). A bank change created inside an
  approved new-hire request would otherwise be "made" by whoever approved the hire.
* Under "No approval needed" for new hires, `create_employee` returned no `applied` flag, so the screen said
  "Nobody has been added to the payroll yet" over a person who had just been added (found on the walk; fixed).
* Re-proof of the 15 fields (read-only, `fs16/fs16_reproof.sql`: every text/varchar/json column of every table,
  every foreign key to the field rows, the 9 stored columns' non-empty values), run twice (2026-11-21 21:58 and
  in prep 22:48–22:50 UTC) on payobook, payobook_template, p0clone, rize, sudima: **0 values, 0 mentions outside
  the module's own view (`view_employee_form_vietnam_insurance`, 3 languages) and the field rows themselves,
  0 saved filters, 0 rows pointing at the field rows** (employees 4,582 / 3 / 14 / 312 / 653). No field kept.
* `hr.formula.config.vn_tax_table_id` is a different model's field of the same name — untouched.

## 2. What was built
Modules: `pb_people_advanced` 19.0.1.1.5 → **19.0.1.2.0**, `pb_bank_ocr` 19.0.1.6.0 → **19.0.1.6.1**,
`pb_form_studio_people` 19.0.1.8.0 → **19.0.1.8.1**, `pb_hr_payroll_vietnam` 19.0.1.2.4 → **19.0.1.2.5**,
`pb_employee_form_tidy` 19.0.1.4.0 → **19.0.1.4.1**, `pb_employee_bank_panel` 19.0.1.1.0 → **19.0.1.1.1**.
Never touched: `pb_lifecycle/`, `pb_pack_*`, `pb_me_portal`, standard addons, `pb_people`, `pb_employee_vault`,
`pb_form_studio` (engine).

**A — new hire → bank change path.** Step 1 of Add employee has a "Bank details · Optional" card (Lucide
landmark): Bank (pick from the bank check's own list — `pb.bank.registry`, 67 banks locally — or type),
Account number (live hint: only digits, 6 to 19), Account holder (placeholder = the person's name, used when
empty), and "A second person approves them before anyone is paid into this account." On create:
* direct (or "No approval needed"): the person is created, then `pb.bank.change.request._pb_hold_new_hire`
  (new, `pb_bank_ocr/models/pb_bank_import_hold.py`) makes ONE waiting change through the import/hold door
  (`_pb_hold_from_import`, `Hold('pb.newhire,<id>', 'New hire: <name>', proposer)`), **created as the person who
  typed it**, sent at once on `records_bank` (one second person, BK1); number tidied to digits;
* through the new-hire approval: the bank values ride in the request (the approver's view shows Bank, Account
  holder and the number as `•••• 1234` only); `_apply_employee` strips them, creates the person, then sends the
  bank change proposed by the person who asked for the hire (`proposal.user_id`), never the hire's approver;
* a problem (no number, letters, not 6–19 digits, bank changes not set up, or the bank check refusing) → the
  person is still created, the screen and a note on the employee's record say what to fix ("Add them from the
  employee's side panel (Pay & tax › Bank)"); on the approval route the problem is said at once and the bank
  values are not put in the request; a number already on someone else's record → "kept for HR to look at
  first" with the reason (draft, as imports do);
* result line + toast: **"Bank details sent for approval"** · "Nothing is paid into this account until a second
  person approves it." · reference; never written to the old boxes; nothing in either bank store until approved;
* `has_bank` fact = details were entered; the contract wizard's fact reads the approved account (either store);
* a new hire is a single bank change, never a "batch" notice (`pb_bank_batch_notice._batch_of` skips
  `pb.newhire,` keys); it also shows in Compliance › Bank's "waiting for you" panel as "New hire: <name>";
* fixed on the walk: "Employee added" now shows when the hire applies at once (`applied: True`).

**B — builder list.** `pb_form_studio_people` overrides `_pbfs_std_all` (Studio Standard fields tab + Field
library) to leave out every box in `_pbfs_std_comeback`, and `_pbfs_people_standard_fields` to stop offering
them as placeable boxes. Not listed, not counted, no greyed row; `update_standard` still refuses them (direct
call). The engine module (`pb_form_studio`) is untouched — the change rebases on any engine work.

**C — 15 fields deleted** from `pb_hr_payroll_vietnam/models/hr_employee_vietnam.py` with their computes
(`_compute_insurance_cost`, `_compute_tax_allowance`, `_compute_tax_rate`; the eligible-dependants count kept),
the form pieces that drew them (the "Contribution Summary" group, the "Dependent Tax Allowance" line, the
fields inside the old Insurance / Tax groups), their 15 `FORM_RULES` rows, 15 verdict-table rows, 30 PO entries
(2 trimmed), the FS-15 stay-off lists, and two Vietnam tests that read `vn_monthly_tax_allowance`. Columns were
left to the platform (the upgrade drops them; 9 → 0 locally and on the copies).

**D — old bank boxes**: §4. Fixed now (trivially dead): the new-hire writer and its form state, its approval-row
labels, the contract fact, the joining checklist's dead dependency (`pb_employee_bank_panel`), and the boxes no
longer offered in the Form builder (B). The two fields stay, hidden.

**E** — vi/id: 23 new strings in `pb_people_advanced` (vi + id; the old "Statutory details…" note replaced by
"Tax and insurance details can be completed later on the employee record."), "New hire: %s" in `pb_bank_ocr`.
Learn: no lesson or replica shows the new-hire bank section or the replaced note (the "Add your first employee"
lesson describes the three steps, unchanged) — nothing to update.

## 3. Tests
Local base `fs16_base` = `wf2p6_base` + every module upgraded (`-u all`) + the Form builder stack, `pb_employee_bank_panel`,
`pb_me_details`; brought to `origin/19.1` (the other session's modules upgraded); copies per run; `--test-tags`.

| Run | Result |
|---|---|
| baseline `origin/19.1` @ `ba9320440`: `/pb_people_advanced,/pb_form_studio_people,/pb_employee_form_tidy,/pb_hr_payroll_vietnam,/pb_bank_ocr,/pb_employee_bank_panel` | 197 tests, 2 failed + 4 errors: `TestFs10Locked.test_l3_tax_source_binding`, `TestPeopleHost.test_13…` (known, FS-12..15), `TestBankOcr.test_07/07b/09/15` (known, S6-A) |
| FS-16, same tags | **210 tests, the same 2 + 4, nothing else** (13 new) |
| FS-16 new-hire callers `/pb_people_advanced,/pb_updates:TestUpdatesP3b,/pb_orgchart,/pb_pay_scales` (after the walk fix) | 95 tests, 0 failed |

| # | Test | Evidence | Result |
|---|---|---|---|
| 1 | new hire with bank → employee, ONE waiting bank change, approver sees it, old boxes empty, nothing payable; approve → both stores exactly as a Records Desk change | `test_01` (route `records_bank`, typist never seated, the seat holder's Approvals inbox page lists it, bank file number and accounts empty before; after approval the account + four bank-file fields compared field by field with a Records Desk bank change of the same bank and holder: identical apart from the number typed); rehearsal copies: §5 "change" | PASS |
| 2 | via the new-hire approval → same | `test_02` (request shows `•••• 7888` only, `has_bank` true; after the hire's approval ONE waiting change proposed by the typist, not the approver; approve → both stores) | PASS |
| 3 | bad number → employee created, clear message, no change | `test_03` (`12-34`, `12AB345678`, bank with no number: person created, "not sent: …", note on the record, no change, old boxes empty), `test_03b` (approval route: said at once, nothing in the request); browser: hint under the box, "Employee added" + the warning line and toast | PASS |
| 4 | no bank → no change | `test_04` | PASS |
| 5 | builder list 16 (rize) / 13 (others); direct call for any of the 19 refused | `test_05a–d` (Studio and Field library list no stay-off box, none offered as a placeable box, `update_standard` refuses the 4 that remain; the 15 no longer exist); before → after on the five sites: §5 | PASS |
| 6 | after deleting the 15: Full details + side panel identical for Vietnam staff (copies), `-u` clean ×5, no view error, saved filters open | rehearsal §5 (form compared with the deleted boxes taken out of the old one; side panel byte-identical; 0 saved filters named them); `test_06`; Vietnam suite (`test_employee_payroll_profile`) green | PASS |
| 7 | three payslips identical; social-insurance report and a bank file identical | rehearsal: rize 4 runs / 211 payslips recomputed old vs new; BHXHDSTK01 + TangLaoDong (this and last month) and the bank file of the latest finished runs, old vs new (cells / content hashes) | PASS |
| 8 | silent upgrade: no approval, mail or job | `test_08`; copies and live: bank changes, approval requests, outbox, to-dos, mails, new-hire requests counted before/after the upgrade; jobs = snapshot | PASS |
| 9 | vi/id PO gate, forbidden word, console, 390 px | PO gate locally and on the server (prep): 0 empty, 0 vendor word in 11 files; every new string has vi + id (coverage script); white-label grep of the diff: 0; console clean on Add employee; 390 px by the stylesheet (the bank card stacks to one column under 680 px) | PASS (phone width by CSS) |

## 4. Where the two old bank boxes ("Bank" and "Account Number" on the employee) are still mentioned
Verdicts: **dead** (can never matter — remove when the boxes are deleted), **repoint** (should read the approved
bank account instead), **must stay** (the field itself, its hide/refuse rules, migrations, tests). "Fixed now" =
done in FS-16. Who still WRITES the boxes: (1) the demo generator (payobook demo only), (2) a pay data file whose
mapping was saved before the boxes were retired (0 such mappings on the five sites; new ones are refused),
(3) the platform's own import screen if someone maps a column to them. The new-hire screen no longer does.

| Where (plain words) | Code | What it does | Verdict |
|---|---|---|---|
| The two boxes themselves | `pb_hr_payroll_formula/models/hr_employee.py:48-49` | field definitions (values kept) | must stay (delete in a later phase) |
| Old "Payroll Info" tab of the full employee form | `pb_hr_payroll_formula/views/hr_employee_views.xml:42-43` | draws them; hidden for everyone by TIDY-E | dead (goes with the fields) |
| An old upgrade step | `pb_hr_payroll_formula/migrations/19.0.1.66.0/post-columns_learn_their_role.py:57` | reads old mappings | must stay |
| People list: "Payroll-ready" / "Bank details" filters, roster bank mark, figures, the old employee page's bank line | `pb_people/models/pb_people.py:105,128,193,303,328,332,381,384,386,412,543-544` | reads the old box; every answer is replaced by the approved-account rule (`pb_employee_form_tidy`) where that module is installed (all five sites) | repoint (pb_people is another session's module) |
| Learn guide's note of what "Bank" means | `pb_people/models/learn_manifest.py:18` | names the old box (checked by a Learn test together with the Home figure) | repoint together with the Home figure |
| Home "no bank account" figure (old reader) | `pb_dashboard/models/home_data.py:668-674` | counts the old box; replaced by the approved-account figure where the bank panel is installed (all five) | dead (with the Learn note) |
| Joining checklist "Bank account" line (old reader) | `pb_onboarding/models/hr_employee.py:41,107` | reads the old box; replaced by the approved-account line from `pb_employee_bank_panel` (all five) | repoint |
| Joining checklist (new reader) | `pb_employee_bank_panel/models/joining_checklist.py:30` / `:53` | the line's key / a dead dependency | key must stay; dependency **fixed now** |
| Stop new mappings into the old boxes | `pb_employee_bank_panel/models/mapping_retired.py:22` | refuses them | must stay |
| Side panel's old "Bank" group list | `pb_employee_vault/models/employee_details.py:128-129` | the group is replaced by the approved-account Bank block | dead (vault is another session's module) |
| Form builder: offered boxes / "Bank files depend on this field" note / refuse Show again | `pb_form_studio_people/models/form_studio.py:36`, `standard_fields.py:78,156` | `bank_name` was in the offered list; the note was untrue | **fixed now** (not listed or offered anywhere, B); refuse rule must stay |
| My Payobook page builder's list of boxes a page may show | `pb_form_studio_portal/models/page_builder.py:185` | still offers the old "Bank" box (show-only; no site shows it — rize has one setting row, switched off) | dead → remove next phase |
| My Payobook "employee can never change" list | `pb_form_studio_people/models/form_studio.py:255` | guard | must stay (harmless) |
| Hide rule (TIDY-E) | `pb_employee_form_tidy/models/form_rules.py`, `models/pb_people.py:124,172` | takes the boxes off the form; turns the People filters onto the approved account | must stay while the boxes and pb_people's filters exist |
| Demo generator | `pb_demo/models/demo_employees.py:97-110,271-272` | writes random demo values into the boxes, then copies them to the bank-file fields | repoint when the demo world is next changed (demo data left as is) |
| New-hire screen and its request | `pb_people_advanced/models/people_wizards.py`, `newhire_approval.py`, `onboard_wizard.js` | wrote the boxes; showed the number | **fixed now** (A) |
| Contract request fact "Bank details given" | `pb_people_advanced/models/people_wizards.py` (contract wizard) | read the old box | **fixed now** (reads the approved account) |
| Comments only | `pb_formula_studio` (2 + 2 test/JS comments), `pb_hr_payroll_formula/models/integration_endpoint_field.py:9`, `pb_employee_bank_panel/models/bank_panel.py:7`, `pb_demo/models/demo_employees.py:91` | text | dead |
| Tests of the hide / refuse / keep-the-value rules | `pb_employee_form_tidy` (3 files), `pb_employee_bank_panel` (2 files), `pb_form_studio_people` (2), `pb_form_studio_reach` (1), `pb_dashboard` (1) | assert the rules above | must stay until the boxes are deleted |

Not the old boxes (same words, other things): the bank-file layouts' `account_number` column (reads the
bank-file fields or the approved account), the bank-account "roles" of imports and the Records Desk, the bank
check's own `x_account_number`, Zoho staging fields, the bank export wizard's own fields.

**Before the boxes can be deleted** (later phase): repoint pb_people (12 lines) + its Learn note + the Home
figure together; repoint pb_onboarding's line; drop the vault rows, the page-builder offer, the old view
fields, the demo generator's writes; then delete the fields (re-prove first: payobook demo holds about 4,500
values — demo data, the rule is add-only, so ask the owner before deleting them).

## 5. Rehearsal and go-live
Scripts `docs/handovers/formstudio/fs16/` (clones of `fs15/`; on the server `/tmp/fs16_*`; staging built by
`fs16_stage_local.sh` from the pushed commit). Upgrade set: `-u pb_hr_payroll_vietnam, pb_employee_form_tidy,
pb_form_studio_people, pb_people_advanced, pb_bank_ocr, pb_employee_bank_panel` (cascades to every installed
module that depends on the Vietnam payroll module).

**Prep 1** `20261121T224034Z` (staging = `ee9f572de`): staged = commit, live = `origin/19.1` (6 trees, hash),
server PO gate 11 files 0 empty / 0 vendor word, dumps ×5 read back (`/odoo/backups/fs16-20261121T224034Z/`:
payobook 82 MB, template 31, p0clone 32, rize 47, sudima 36), re-proof ×5 clean (§1), job snapshots, probes.

**Rehearsal 1** — hidden copies of all five (LIVE module set, restored from the dumps), jobs + mail off, dropped
after (0 left):

| Copy | Upgrade | Data restored vs upgraded (the 9 dropped columns left out) | Full details (en/vi/id) | Side panel | Employee pages | Files: social insurance + bank file | Columns / field rows after | Change on the copy (new hire with bank) |
|---|---|---|---|---|---|---|---|---|
| rize | 76 s, 0 ERROR | identical except 4 chatter notes on technical records (below) | differs only by `on_change="1"` (below) | byte-identical (14 people, 5 groups) | identical | identical (5 made) | 9 → 0 / 15 → 0 | sent, 1 waiting change on `records_bank`, old boxes empty, stores empty; second person seated, typist not; approved → bank file number + account first |
| p0clone | 70 s, 0 ERROR | identical | same | byte-identical | (no login) | identical (1 made, 3 not made both sides) | 9 → 0 | sent; waits for a second person (p0clone has none but the support login — BK1 behaviour) |
| sudima | 72 s, 0 ERROR | identical | same | byte-identical | differs = FS14-7 session noise (as FS-15) | identical (5 made) | 9 → 0 | sent; approved by the second person → both stores |
| payobook | 84 s, 0 ERROR | identical | same | byte-identical | identical | identical (13 made: bank files of the latest finished runs + the two reports, this and last month) | 9 → 0 | sent; approved → both stores |
| payobook_template | 91 s, 0 ERROR | identical | same | byte-identical | (no login) | identical (1 made) | 9 → 0 | sent; waits for a second person (as p0clone) |

**rize payslips: 4 runs / 211 payslips / 6,914 lines old vs new, 0 differing** (31 computed, 180 refused
identically). Form builder after: rize 183 standard fields, **16 taken off the screens, all can come back, 0 stay
off, 0 stay-off boxes listed** (before: 202 / 35 / 16 / 19 / 4); payobook, template, p0clone, sudima **13** (before
32, of which 19 stay off). Add employee defaults: 67 banks, bank check on.

Follow-up on one more rize copy (`fs16_investigate.sh`): the probe's page visits make 0 messages; the upgrade makes
**4 chatter notes on technical records** (2 on scheduled jobs, 2 on server actions: their tracked fields reset by
the cascade upgrade on a copy whose jobs were all switched off — no email, nobody notified); the employee form
differs old vs new **only by `on_change="1"` dropped from 8 Vietnam boxes** (they fed the deleted worked-out
figures, so the screen no longer asks the server to recompute when they change) — nothing drawn changes.

**Prep 2 / rehearsal 2** `20261121T233458Z` (staging = `7cb8fb591`, after merging Codex's `fb1e86add`, assets of
`pb_form_studio_people` only): staged = commit, live = `origin/19.1` (6 trees), re-proof ×5 clean again (third
time), dumps ×5 (`/odoo/backups/fs16-20261121T233458Z/`). Rehearsal 2 on payobook_template and sudima: upgrade 69 s
each, 0 ERROR, data identical, side panel byte-identical, form = the on_change-only difference, files identical,
columns 9 → 0, new hire with bank → one waiting change (sudima: approved → both stores). Local suites after the
merge: `/pb_people_advanced,/pb_form_studio_people,/pb_orgchart` 159 tests, only the 2 known failures.

**Go-live** (`fs16_tries.sh`, lock taken with `flock`, notes re-read for HOLD / open START before each try and right
before the stop): try 1 23:56 — Rize in use (37 requests up to 23:45), not stopped; try 2 00:08 — quiet on rize,
payobook, sudima since 23:53 → fresh backups ×5 → 00:08:30 stop → 6 trees rsynced (= staged) → upgrades template
71 s, p0clone 73, sudima 74, rize 77, payobook 92 — all exit 0, 0 ERROR → asset purge + `web.assets.version` →
00:16:29 port listening; five sites 200; template job 45 (re-activated by the cascade) switched back off.

| Check (after, `fs16_verify.sh` + `fs16_after.sh` + probes) | Result |
|---|---|
| Trees / versions | 6 trees = commit; manifest = installed ×5 (30/30) |
| Jobs | = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91); payobook job 156 off |
| Data before the stop vs after (the 9 dropped columns left out) | identical ×4; rize +4 chatter notes on technical records (as rehearsed); bank changes, accounts, bank-file fields, approvals, outbox, to-dos, mails, new-hire requests, Form builder rows unchanged ×5 |
| The 15 fields | columns 9 → 0, field rows 15 → 0 ×5 |
| Full details | differs only by `on_change="1"` on 8 Vietnam boxes (after hashes = the rehearsal's) |
| Side panel | identical ×5 |
| Form builder | taken off the screens: rize 35 → **16**, others 32 → **13**; stay-off listed 4 → **0** ×5 |
| Add employee / Approvals inbox | defaults load (67 banks, bank check on) / inbox opens ×5 |
| Employee pages (My Payobook, My Profile, My details) | payobook 3, rize 3, sudima 1: all 200, 0 failed |
| Administrator /my | identical except template, sudima = the new `web.assets.version` (as FS-15) |
| Server log since the stop | 0 ERROR, 0 Traceback, 0 asset errors; upgrade logs 0 ERROR (the Vietnam dashboard's old icon warnings, unchanged file); one process |
| payobook.com in the browser (signed-in session) | Add employee shows the Bank details card; console clean; nothing created |

## 6. Gotchas (ledger rows)
* FS16-1 The approval engine treats a record's creator as one of its makers: anything created inside an
  approval's apply step is "made" by the approver. Create follow-on requests `with_user(<the real proposer>)`.
* FS16-2 `create_employee`'s direct answer must carry `applied: True`, as `create_contract` does — a route that
  applies at once hands the same dict back.
* FS16-3 Deleting fields that a module's own view draws: the employee form's markup changes by exactly those
  nodes; compare old vs new with the deleted nodes (and pieces left empty) taken out of BOTH
  (`fs16_probe.py normalised`).
* FS16-4 The deploy notes' evidence folder is `odoo:750` — poll it with `sudo test -f`, or the poll never ends.
* FS16-5 Codex leaves `/tmp/payobook-studio-deploy.lock` behind after its DONE/VERIFIED lines (22:16 file, its
  run closed 22:23); our go-live uses `flock`, which a left file does not block; the tries script removes the
  file only when nobody holds the lock.

## 7. Ledger
**R32** (2026-11-22, owner) Fields that must stay off the screens are not listed in the Form builder at all; the
15 dead Vietnam employee fields are deleted; the new-hire screen's bank details go through the bank change path
(one second person). Phase row: FS-16 — LIVE ×5 2026-11-22 00:16 UTC (479 s down); report `FS16_REPORT.md`.

## 8. Not done / owner questions
* The old Bank / Account Number boxes are not deleted (handover: a later phase). §4 lists what must change first.
* The demo generator (`pb_demo`, payobook demo only) still writes the old boxes and copies them into the bank-file
  fields; left as is (demo data, not a customer door).
* Phone width (390 px) checked by the stylesheet only (this browser window does not narrow below desktop width,
  as in FS-14/FS-15): the bank card's three boxes stack to one column under 680 px.
