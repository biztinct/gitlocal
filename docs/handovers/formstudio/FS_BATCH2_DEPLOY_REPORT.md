# FORM STUDIO Batch 2 — merge, seams, rehearsal, go-live ×5 (FS-8, FS-9, FS-10)

Merge + go-live deployer, 2026-11-20 (UTC). Handover `FS_BATCH2_DEPLOY_HANDOVER.md` (main checkout),
method of `FS_DEPLOY_HANDOVER.md` and the FS-7 scripts (cloned into `/tmp/fb2_*` on the server; copies in
the agent scratchpad `fb2/srv/`).

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima) at
`ab0f02a41` (`origin/fs-batch2`), **452 s down** (09:13:57–09:21:29 UTC). Deploy notes START 08:41,
DONE 09:23 UTC. First try found the 15 quiet minutes (no signed-in activity on rize/payobook since
08:57), the notes had no HOLD line and no other open START, the shared lock was free.
**WORKFLOW-2 P6b/P6c NOT included**: `origin/wf2-p6` did not exist when the three FS branches were
merged and tested (checked twice); the coordinator's note that it was ready arrived during the go-live —
as instructed, not redone; it ships separately. abm untouched. Nothing held back from FS-8/9/10.

## 1. Merge (`fs-batch2` from `origin/19.1` @ `e69bebcc4`)
`--no-ff` merges in order fs-10, fs-9, fs-8 — **no conflicts, no file touched by two branches** (each
report's "no file shared" claim confirmed by `git diff --name-only`). One version raise per module
(checked). PO files: `pb_learn/i18n/vi_VN.po` identical to 19.1 (not in the diff — the Learn generator
did not wipe it).

| Module | Live before | After | Go-live |
|---|---|---|---|
| pb_explorer | 19.0.2.7.0 | 19.0.2.8.0 | -u ×5 |
| pb_form_studio_explorer | — | 19.0.1.0.0 | -i ×5 |
| pb_employee_bank_panel | — | 19.0.1.0.0 | -i ×5 |
| pb_employee_form_tidy | 19.0.1.2.0 | 19.0.1.3.0 | -u ×5 |
| pb_form_studio | 19.0.1.3.0 | 19.0.1.4.0 | -u ×5 |
| pb_form_studio_people | 19.0.1.3.0 | 19.0.1.4.0 | -u ×5 |
| pb_form_studio_contracts | 19.0.1.2.0 | 19.0.1.3.0 | -u ×5 |
| pb_form_studio_reach | 19.0.1.1.0 | 19.0.1.2.0 | -u ×5 |
| pb_me_portal | 19.0.3.8.0 | 19.0.3.8.1 | -u ×5 (label hook lines only) |
| pb_me_details | 19.0.1.0.1 | 19.0.1.0.2 | -u ×5 (label hook line only) |
| pb_learn | 19.0.20.8.9 | 19.0.20.8.10 | -u ×5 |
| pb_demo | 19.0.1.15.0 | 19.0.1.16.0 | -u payobook only (installed nowhere else) |
| pb_dashboard | 19.0.2.3.1 | same | files only (one test widened) |

Before: all 13 live trees = `origin/19.1` (hash), nothing newer on the server; every dependency of the
two new modules installed ×5.

## 2. Seams on the merged tree
Local `fb2_base` = `wf2p6_base` + the Form builder modules, TIDY-E, My details, tax, demo module and
native look installed with the `origin/19.1` code. Two copies: baseline (19.1 code, `-u` of the 15
touched/related modules) and merged (`-u` the same + `-i` the two new modules); `--test-tags` of those
modules (+ pay delivery, onboarding, native look). Local databases dropped after.

| Run | Tests | Failed + errors |
|---|---|---|
| Baseline 19.1 | 1,036 | 15 + 4 |
| Merged | **1,087** (+51: bank panel 25, reports bridge 16, demo +4, people +10, reach +11, contracts +1) | 15 + 4 — **the identical set** |

The common set is pre-existing and identical to FS-10's recorded baseline: Learn ×12 (anchor registry
05, composer 03b, guide truth 02/02b/03, learnrev p4 c1, reachability 02/03/04/07), My Payobook home
cards / source ×5, profile change flow, portal-only doors ×2, people `test_13` (no hourly-cost module on
this base).

| Seam | Evidence | Result |
|---|---|---|
| 1 Payslips + files | FS-10 test P (three payslips, two schemes, identical after hide/rename/later use/upgrade step); pay delivery suite 145/145 incl. the Vietnamese bank file and payment list golden tests (bytes); rize copy: 211 payslips identical (§3) | PASS |
| 2 Silent upgrade | FS-9 test 8 (checksums), FS-8 test 10, FS-10 silent snapshot; on the three copies and live: no rule, no tick, no new job, no mail, no approval; FS-10 un-hide step **0** everywhere | PASS |
| 3 FS-9 bank block | bank panel tests 1–7 (approved / waiting / none / other name + Mark as seen, gate, masked digits), A1–A5 checklist, C1–C3 Mapping; Home test 6 | PASS |
| 4 Demo step guard | refused on rize and sudima copies (the step does not exist there, no demo marker); payobook copy: second run 0 | PASS |
| 5 FS-8 | bridge tests 1–11 (split, filter, visibility by direct call, delete-with-warning, Excel names); rize copy: five shipped reports identical old vs new | PASS |
| 6 FS-10 | L1–L8, C4c, R1–R7; Learn suite = baseline (lesson passes Learn's checks); phone width on payobook.com (§5) | PASS |
| 7 FS-7 still works | `test_fs7_standard` (people + contracts) incl. hide/rename; R24 filter on screen (§5) | PASS |
| 8 Workflow | not included | — |
| 9 Words | PO gate (platform reader): vi/id every new string, 0 empty in the touched modules except `pb_explorer` id (546 of 551 empty — pre-existing, FS-8 limit: only its 4 new sentences are Indonesian); 0 vendor word in any msgstr; added lines grep: vendor word only in tests; console clean (§5) | PASS |

## 3. Rehearsal on hidden copies (jobs + mail off; `dropdb --force` after)
Backups first (`/odoo/backups/fb2-20261120T084137Z/`: five dumps read back — payobook 84 MB, template
31 MB, p0clone 32 MB, rize 45 MB, sudima 35 MB — file folders linked, previous trees saved).

| Copy | Upgrade | Data | Checks |
|---|---|---|---|
| rize | 71 s, 0 ERROR, 0 Traceback | identical except messages (upgrade notes) | **211 payslips / 6,914 lines, 0 differing** (31 computed, 180 refused identically — as every earlier rehearsal); **five reports identical** (Cost Explorer, Workforce Movement, Cost per Head, Tax & Deductions, Statutory Ledger); joining checklist "Bank account" missing 230 → 36; 22 of 23 boxes locked before and after; un-hide step 0; demo step refused |
| sudima | 66 s, 0 ERROR | identical | checklist 651 → 9; un-hide 0; demo step refused |
| payobook | 87 s, 0 ERROR | identical except bank account numbers | demo step **4,498** aligned, account count 4,507 unchanged, 0 messages / approvals / mails added; second run 0; checklist 81 → 81 |

The upgrade switched on 22 jobs on the rize/sudima copies and 6 on payobook (all were off on the copies):
these are jobs that are ON live — the live snapshot comparison (§4) showed none re-activated.

## 4. Go live ×5 and verification
Order payobook_template, p0clone, sudima, rize, payobook; one command each
(`-u pb_explorer,pb_employee_form_tidy,pb_form_studio,pb_form_studio_people,pb_form_studio_contracts,
pb_form_studio_reach,pb_me_portal,pb_me_details,pb_learn -i pb_employee_bank_panel,pb_form_studio_explorer`,
+ `pb_demo` on payobook): 75 / 68 / 68 / 74 / 84 s, all EXIT 0, 0 ERROR. Asset purge + signal +
`web.assets.version = fb2-20261120T084137Z` per database. Start 09:21:29; five sites 200.

- 13 trees = commit; manifest = `latest_version` on every installed row ×5 (pb_demo installed on payobook only).
- Jobs = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91), none re-activated, no new job; payobook job 156 OFF.
- Data before the stop = after ×5, except: payobook bank account numbers (demo step) and rize messages +6
  (upgrade notes on jobs/server actions, as in every FS go-live).
- Server log since the stop: 4,027 lines, 0 ERROR, 0 Traceback, 0 asset errors; one service process.
  Upgrade logs carry FS10-3's expected "inconsistent compute" warnings with stacks (not failures).
- Stored-value translation fixes: none listed by the FS-8/9/10 reports — nothing to write.

| Site | FS-10 un-hide step | 23 boxes locked (really used) | Standard fields hidden / renamed | Custom fields | Joining checklist "Bank account" still to fill in (active people) | "Sent, waiting for HR" |
|---|---|---|---|---|---|---|
| payobook | 0 | 0 | 0 / 0 | 6 (the demo's) | 81 → 81 (with a checklist: 11 → 11) | 0 |
| payobook_template | 0 | 0 | 0 / 0 | 0 | 1 → 1 | 0 |
| p0clone | 0 | 0 | 0 / 0 | 0 | 12 → 12 | 0 |
| rize | 0 | **22** | 0 / 0 | 0 | **230 → 36** | 0 |
| sudima | 0 | 0 | 0 / 0 | 0 | **651 → 9** | 0 |

payobook demo step (live): **4,498 demo bank accounts now carry the bank-file number**, 0 deleted
(4,507 before and after), 0 approvals, 0 mails, 0 messages. Lock totals (employee / contract) live:
payobook 97/163, 29/34; template + p0clone 95/162, 29/34; rize 121/167, 32/47 (contract locks fell
45 → 32: only really-used boxes stay locked); sudima 95/164, 29/34.

## 5. Checks on payobook.com (signed-in administrator session) and the other four sites
The browser window could not be widened (500 px) — so every check below is at near-phone width.

| Check | Result |
|---|---|
| Side panel › Pay & tax › Bank | "Bank / Approved / bank name / •••• last four / Account holder"; sample of 60 demo people: 52 Approved, 8 None, **0 "different account" notes** (the demo step worked), 0 waiting, 0 whole numbers anywhere in the payload; the old Account Number box gone |
| Home figure | November: no "people have no bank account" line (0 → 0, as FS-9 predicted) |
| Reports split by "DEMO Shirt size" | offered under "Your own fields" ("Employee · as it is today"); Total cost and People split into Not filled in / L / M; the split total equals the by-company total to the unit; Excel built: `payobook_people_by_demo_shirt_size_2026-11-20.xlsx`, 3 rows |
| Form builder at phone width | pinned bar (Publish / close), sticky "Find a field" + chips, tapping Religion opens the bottom sheet with Done; page width 500 = window (no sideways scroll); closed without changes |
| My Payobook label | Work Phone renamed "DEMO Office line" → My Profile showed it; Reset → built-in "Work Phone" again; 0 standard-field rules left |
| Lesson "Add your own fields" | new wording live; Full lesson runs to "Step 5 of 5" on the practice copy |
| Console | no errors (People + panel, Form builder, Help/lesson) |
| Vendor word | not on any page opened |

Other four sites (server side as each site's administrator, rolled back; nobody signed in as a customer):
bank panel opens for every active person checked (template 1 None; p0clone 12 None; rize 194 Approved /
36 None; sudima 397 Approved / 3 None of a 400 sample), 0 whole numbers; reports schema opens (no own
fields offered — none exist there); Field library opens; employee page opens. Sudima's platform login
is not an administrator there (known), so its check ran as Sudima's own administrator.

## 6. Notes / gotchas
- FB2-1 Pre-creating the copy's log file as root (`: > file`) made it unwritable for the service user, so the
  rehearsal's upgrade logs went to the `.out` capture instead (errors were counted there: 0). Never
  pre-create a log file the service user must write.
- FB2-2 The deploy-notes check before the stop is now a script step (HOLD line or another deployer's open
  START after our START → refuse), run twice: before the counts and right before `service stop`.
- WORKFLOW-2 P6b/P6c: ready after this batch had passed its seams; not merged here (coordinator's rule).

## 7. Owner questions
None new. The builders' questions were already answered: boxes used only in workflow conditions stay
hideable; the "shown again" notice is a pop-up/inbox note only where tenant e-mail is off; money split by a
contract field is slower at demo size (accepted).
