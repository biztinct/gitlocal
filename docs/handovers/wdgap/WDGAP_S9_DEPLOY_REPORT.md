# WDGAP Step 9 — deploy report (merge S9-A, S9-B, S9-C + S5-F; live ×5; verify)

Merge-deploy-verify agent, 2026-11-16 (UTC). Handover `WDGAP_S9_DEPLOY_HANDOVER.md` (method of the
S5 and S8 deploy handovers), plus the coordinator's scope addition: merge `origin/wdgap-s5f`
(e59d8e1ef, Step 5 follow-ups) after S9-C, one go-live for both.

**Result: merged, pushed to `19.1` at `46426eb93`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima). `pb_review_forms`, `pb_conduct`, `pb_people_reports`,
`pb_voice` installed ×5; `pb_me_portal`, `pb_goals`, `pb_leave_setup`, `pb_time_pay`, `pb_retro`,
`biz_debrand` upgraded ×5; `pb_hub` tree copied (test file only). **312 s down** (14:23:27–14:28:39).
abm, pbf_preview, recruit_connect untouched; the Codex release (pb_people, pb_employee_vault,
pb_scheme_map, pb_tenants; 683c341f6, not on 19.1) untouched. Nothing held back.

## 0. Order

At the start the Step 8 go-live had an open START (13:05); merge and all local testing ran in parallel.
Step 8 DONE at 13:29 and `origin/19.1` moved to `38e1b524e` (S8 deploy report); merged it in (docs only,
no conflict). Before stopping the service: no open START by anyone; signed-in activity on rize/payobook
in the last 15 minutes: **none** (checked at 14:23 by the go-live script).

## 1. Merge

Branch `wdgap-s9-merge` from `origin/19.1` @ `c24630ccc`:

| Order | What | Result |
|---|---|---|
| 1 | `wdgap-s9a` (32dc38b4b) `--no-ff` | no conflict |
| 2 | `wdgap-s9b` (c248734c8) **squash** → `a07561fd2` | no conflict; WIP commits kept out of 19.1; the final S9-B report has no password line (checked) |
| 3 | `wdgap-s9c` (68e7ed1f8) `--no-ff` | no conflict |
| 4 | `4ca9bec84` — the sanctioned employee-home edit | see below |
| 5 | `1f3a6ee67` — seam tests M1–M3 | |
| 6 | `origin/19.1` (38e1b524e, Step 8 live) | no conflict |
| 7 | `wdgap-s5f` (e59d8e1ef) `--no-ff` | no conflict |
| 8 | `288629815` — seam tests M4–M5; `46426eb93` — handover copies + ledger | |

**The one `pb_me_portal` edit (C-3, RV4)** — `pb_me_portal/models/pb_me_home.py`:
`_TILE_ROWS` + `('/my/letters', 'me', 'file-text', 'indigo', {})` after `/my/expenses` (lines 105–107)
and `('/my/review', 'growth', 'clipboard-list', 'indigo', {})` right after `/my/goals` (lines 124–126);
`_TILE_WORDS` + `/my/review` (title "My review", text "Your end-of-year review, both sides") and
`/my/letters` ("Letters HR has sent you") (lines 169–171); pinned test `tests/test_me_home.py` test 02:
the Me-strip order gains `/my/letters`, My review follows My goals (lines 64–77); vi/id entries for the
three words; version 19.0.3.7.0 → **19.0.3.8.0**. The S9-A "home entry" (piece 0) went into
`pb_review_forms/views/portal_templates.xml` (`portal_my_home_review`, shown only while the person has a
review on a form) with its .pot/vi/id entries; `pb_review_forms` 19.0.1.0.0 → **19.0.1.0.1**.

Versions after the merge: pb_me_portal 19.0.3.8.0, pb_goals 19.0.1.5.1 (S9-A), pb_review_forms
19.0.1.0.1, pb_conduct 19.0.1.0.0, pb_people_reports 19.0.1.0.0, pb_voice 19.0.1.1.0 (VC1),
pb_leave_setup 19.0.1.1.0, pb_time_pay 19.0.1.1.0, pb_retro 19.0.1.2.0, biz_debrand 19.0.2.11.0, pb_hub
unchanged (S5-F D3).

### 1.1 Static gates (merged diff vs `origin/19.1`, 161 files)
py_compile 89: 0 failures. XML 22: 0. `node --check` on all changed JS: ok. PO gate (`PoFileReader`)
22 `.po`/`.pot`: 0 failures, 0 msgstr naming the vendor; again on the server's reader for the 20 `.po`
of the staged trees: all parse. Vendor word on added user-visible lines: **0** (flagged lines are
`.po` headers, comments, `<odoo noupdate>` roots and tests). Product name in `biz_*`: none. No Sass
`min()/max()` with mixed units (S9C-2).

### 1.2 Seams (new tests `pb_review_forms/tests/test_wdgap_s9_merge_seams.py`, tag `wdgap_s9m`) — all pass

| # | Seam | Result |
|---|---|---|
| c / M1 | Employee home: the three "Needs you" hooks stack (each calls `super()`) | the employee gets "Give your own view for your review", "A short survey is waiting" and "2 letters from HR to read" together; the letter row's words contain none of warning / disciplinary / conduct / dismissal / hearing; a colleague gets only the survey row; the whole home payload builds with My review, Letters from HR and Surveys in the tile list. (Step 6 is not on 19.1 yet — its hooks are not in this stack.) |
| d / M2 | Privacy matrix as payroll officer, payroll manager, general HR, lifecycle user, un-named administrator, line manager, another employee, the employee | conduct case, note, file, letter, letter PDF: **nobody** of the eight; conduct board refused to all eight; the conduct letter's copy in documents: only the employee. Finished review document and PDF: only the employee; PDF on the review record, answers, overall comment record: none of the eight; the overall comment on the review row: the employee and their manager. Review HR reads all of it; the named conduct HR reads the case. Survey answer store: refused to all eight AND to survey HR; it has no link to anything but the round. People reports: general HR and the administrator yes; payroll officer, payroll manager, lifecycle user, manager, employees no. |
| e / M3 | A conduct letter copy and a review PDF on the same person | payroll officer/manager: only the ordinary document; review HR: ordinary + review, not the letter; named conduct HR: ordinary + letter, not the review; general HR: ordinary only; the employee: all three; separate document kinds. |
| f | Small groups hidden incl. Excel and subtraction | the builders' engines re-run on the merged tree: pb_people_reports 32 (incl. the brute-force attacker T70 and the Excel test T90), pb_voice 59 (R03–R07, V01–V06) — all pass |
| g | Goal year without a form reads exactly as today | S9-A golden tests (test_11 ×3 incl. the pay review's "Read scores from Goals" dry run) — pass on the merged tree |
| h | PDFs that could not print locally | rendered on the rize rehearsal copy (§2): finished review 205 KB and conduct invitation 225 KB, real PDFs, plain words, no software name; both closed to a payroll officer |
| S5-F a / M5 | Late-minutes page beside the Step 9 tiles | `get_my_overtime` keeps every key + `late`; the late page answers; home payload has My review, Letters from HR, Surveys, Overtime and the three Needs-you rows together |
| S5-F b / M4 | Report preview title | finished review → "Review", conduct letter → "Invitation to a meeting", payslip → "Payslip - <person>"; never the platform's name, never the neutral fallback |
| S5-F c | `pb_hub` shortcut test | `TestPaletteRowsFollowTheirTabs.test_every_tab_row_carries_its_tabs_gate` now **passes** (run B) |

### 1.3 Combined local runs (Mac, ONE database `wdgap_s9m_t` = copy of `upd_p6_t_tpl`, port 8971)

| Run | What | Result |
|---|---|---|
| A (S9 only) | `-i` the four new modules, `-u` every module behind the tree + pb_hub, pb_people_hub, pb_talent_hub, pb_settings, pb_me_portal, pb_me_team, pb_goals, pb_employee_vault; suites of all of them + `pb_pay:TestQf4GoalScores` | **625 tests, 7 failed, 2 errors = the union of the recorded baselines**: pb_me_portal ×5 (test_05_grid E, test_01_profile E, test_06_font, test_12_vi_po, test_t1_7), pb_people_hub ×2 (contracts action, lens order), pb_hub ×2 (kit above twenty; the Step 5 shortcut test S8M-5). `TestMeHomeSource.test_01_registry_covers_every_tile` passes (the tile edit). New: pb_review_forms 67 (42 + seams), pb_conduct 44, pb_people_reports 32, pb_voice 59 — all pass. |
| B (after 19.1 + S5-F) | same database: `-i pb_loans,pb_fund_payments,pb_retro,pb_leave_setup,pb_time_pay,pb_shift_patterns`, `-u biz_debrand,pb_hub,pb_review_forms` + behind; suites pb_leave_setup, pb_time_pay, pb_retro, biz_debrand, pb_hub, pb_me_portal + seams | **367 tests, 6 failed, 2 errors = baselines**: pb_me_portal ×5, pb_hub kit-above-twenty, biz_debrand ×2 (`test_01_no_product_name…`, `test_09_the_scrub…` — S5-F's recorded base2 set). The shortcut test now passes. pb_leave_setup 60, pb_time_pay 72, pb_retro 71 — all pass. |

Database and its file folder dropped at the end; no other builder's database touched.

## 2. Rehearsal (server, rize copy) — PASSED in 4 min 28 s

Evidence `/tmp/wdgap-s9-20261116T141645Z/`; backups `/odoo/backups/wdgap-s9-20261116T141645Z/`
(payobook 80.5 MB, payobook_template 29.4, p0clone 29.8, rize 43.0, sudima 29.7; each read back with
`pg_restore -l`) **+ each database's file folder** (hard-linked copy: payobook 10,181 files,
payobook_template 582, p0clone 176, rize 1,245, sudima 1,206) + the previous trees. Staged =
`git archive 46426eb93`, 11 trees hash-checked = commit. Copy hidden from the live job runner while
restoring; jobs and mail servers off; dropped with `--force` after.

| Check | Result |
|---|---|
| Install + upgrade | EXIT 0 in 71 s; **0 ERROR**, 0 Traceback; the 4 warnings naming our modules are pb_goals' existing "two fields have the same label" notices |
| Payslips old vs new (S5-F touches back pay) | runs 2110 + 2115 (scheme India, 54 payslips, 1,296 lines): **0 differing payslips**, run totals identical, figures add up before and after; the one payslip of 2115 that refuses, refuses identically |
| Counts (mails, to-dos, followers, users, group memberships, employees, documents + hash, goal years/sheets/reviews, HR letters, payslips, lines, line total, contracts, back-pay entries 0, re-works 0, late decisions, leave kinds + switched-on state) | **identical** after install and at the end |
| New rows | only seeds: 7 conduct reasons, 6 letter wordings, 15 library questions, 2 private document kinds ("Performance review", "Private HR letters"); 0 forms, cases, letters, rounds, invites, answers; nobody named |
| Document access per login | every payroll / HR / lifecycle login on rize (5): **identical** before and after (rize holds 1 employee document) |
| PDFs (seam h) | a throwaway DEMO world on the copy: finished review filed under "Performance review" (private) and a conduct invitation filed under "Private HR letters" — both real PDFs; a payroll officer can read neither; 0 emails queued |
| Report titles | review "Review", conduct letter "Invitation to a meeting", payslip "Payslip - Phạm Phát Đạt" |
| New jobs, run once by hand | "Review forms: share finished reviews on their day" → 0; "Employee surveys: close, remind, tidy" → nothing to do |

## 3. Read-only live checks (14:0x UTC, before the START)

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Open START | none (last: S8 DONE 13:29 + notes) | | | | |
| Server | disk 27 GB free of 77; memory 2.0 GB available; one service process; lock free | | | | |
| Live trees of the 11 = `origin/19.1` | yes (4 new absent) | | | | |
| Jobs total / active | 108 / 55 (156 OFF) | 96 / 37 | 96 / 45 | 96 / 88 | 96 / 87 |
| Every dependency of the 4 new modules installed | yes | yes | yes | yes | yes |
| Outgoing mail server active | 1 | 0 | 0 | 0 | 0 |
| Back-pay entries / re-works | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

### Nightly backups and the file folder (handover §2)
**Yes, with one gap.** The nightly job (`/etc/cron.d/payobook-nightly-backup` → `/odoo/ops/nightly_backup.py`,
19:30 UTC) copies each database AND its file folder (`/odoo/nightly-backups/<db>/<date>/filestore`, hard
links; the `OK` marker says `"filestore": true`) — for **payobook, payobook_template, p0clone and rize
only. sudima is not in the nightly backup at all** (`/etc/payobook/nightly-backup.json`). Not changed here
(owner item). Note for surveys: because the nightly copy is hard links, a closed survey's sealed answers
stay in the nightly copies for their retention (7 days; rize 30) — reachable only with access to the
server's disk (ledger S9M-2).

## 4. Go live — risky sequence

START 14:16, DONE 14:29 UTC. Per database (order payobook_template, p0clone, sudima, rize, payobook):
`-u biz_debrand,pb_goals,pb_leave_setup,pb_me_portal,pb_retro,pb_time_pay -i
pb_review_forms,pb_conduct,pb_people_reports,pb_voice`; signal row + bundle purge +
`web.assets.version` = `wdgap-s9-20261116T141645Z`. Each upgrade ~57–65 s, EXIT 0.

### Versions before → after (all five)

| Module | Before | After |
|---|---|---|
| pb_me_portal | 19.0.3.7.0 | 19.0.3.8.0 |
| pb_goals | 19.0.1.5.0 | 19.0.1.5.1 |
| pb_leave_setup | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_time_pay | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_retro | 19.0.1.1.0 | 19.0.1.2.0 |
| biz_debrand | 19.0.2.10.0 | 19.0.2.11.0 |
| pb_hub | 19.0.1.13.2 | 19.0.1.13.2 (test file) |
| pb_review_forms | — | 19.0.1.0.1 (new) |
| pb_conduct | — | 19.0.1.0.0 (new) |
| pb_people_reports | — | 19.0.1.0.0 (new) |
| pb_voice | — | 19.0.1.1.0 (new) |

### Verification
- **Trees**: all 11 server trees byte-identical to `46426eb93`. **Versions**: manifest = `latest_version` ×5, 0 mismatches.
- **Jobs**: exactly 2 new per database, both daily and quiet — "Employee surveys: close, remind, tidy"
  (161 on payobook, 97 elsewhere) and "Review forms: share finished reviews on their day" (162 / 98, 16:45
  UTC). No job changed, lost or re-activated (none to switch back off). Active 57/39/47/90/89. Job 156 on
  payobook still OFF.
- **Data** (before = after ×5): the full count list of §2, incl. 0 back-pay entries and 0 re-works.
- **Silent install** ×5: only the seeds; 0 forms, cases, letters, rounds, answers; **nobody named for
  conduct cases on any site**.
- Server log since start: 0 ERROR/CRITICAL/Traceback (also after all checks below). One service process.
  Sites 200 ×5. Lock released.

## 5. Checks on the real system (look-only)

As QA Test (uid 6672) inside the server's own shell, read-only, rolled back (no password used, S5M-4):
- **Review forms**: QA is not one of the people who run reviews → "Review forms are set up by the HR
  team." As the demo HR lead (`demo.hr@example.com`): the screen opens on the goal year with **no form**
  (five steps offered); 0 forms in the database.
- **Conduct**: nobody named → the board refuses QA ("Conduct cases are seen only by the people HR names
  for them…"); 0 cases.
- **People reports** (People › Insights): opens for QA (HR); "Headcount and turnover" with **15 hidden
  cells** for small groups.
- **Voice**: opens; 0 surveys; 15 library questions offered.
- **A demo employee's home** (Bùi Hữu Khang): Needs-you rows are only his usual ones — **no letter row**.
  "My review" is not shown: no review form is in use on payobook, and the entry appears only to someone
  with a review on a form (by design, ledger S9M-3).
- **Existing payslip print** (payslip 144281): renders; page title "Payslip - Bùi Hữu Khang"; PDF 152 KB.
  **Existing employee document** (174, Degree / Certificate): still opens for QA.

Browser (owner's signed-in session, my own tab, nothing pressed that saves): Talent › Voice — "Employee
voice … No survey yet", library and "New survey" offered; Conduct — "Only for the people HR names" (even
for the main administrator); Review forms — "No form yet. Fill in the five steps…". Console: no errors.

Other four sites (server shell, read-only): the survey board, People reports (hidden cells: template 6,
p0clone 2, rize 252, sudima 64), review forms (0) and Kinds of leave (other-country kinds now folded away:
67, 67, 60, 67) all answer; nobody named for conduct; survey email off on all four.

## 6. Held / left off / follow-ups

- Nothing held back.
- **sudima has no nightly backup** (database or files) — owner item; this deploy's own dumps cover it.
- Not done on purpose: starting a survey, naming anyone for conduct, putting a review form in use, or
  applying ready-made leave kinds on a live site (look only).
- The People reports tab could not be opened by address in the browser (it is a tab inside People ›
  Insights); its figures were checked through the server instead.

## 7. Questions for the owner (plain words)

**People reports and conduct cases (S9-B)**
1. **Small companies will see "Hidden" a lot.** Groups under 5 people are hidden, and so are figures
   that could be worked out by subtraction. On Rize today the headcount report hides 252 small figures.
   Keep the rule at 5, or allow a softer one for HR (for example under 3)?
2. **No month-by-month headcount line.** A monthly line would let anyone work out a one-person change.
   The report shows the start and end of the year and joiners/leavers by quarter. Keep it that way?
3. **Country notes for hearings and warnings start empty.** Should we get Vietnam and Indonesia notes
   written after a legal check, or will each customer's HR write their own?
4. **Second sign-off and appeal.** Today the named HR person records the decision alone. Do you want a
   second signature (for example Head of HR) before a warning or dismissal is final, and a formal
   "appeal" step after the employee replies?
5. **Administrators are out until named.** A system or tenant administrator does not see conduct cases
   until someone names them on the Access screen (they can name themselves; it is recorded). Keep that?

**Step 5 follow-ups (S5-F)**
6. **Late minutes page**: employees see each counted or excused late arrival / early leave. The
   manager's note on an excuse is not shown. Should employees see that note?
7. **A leaver's back pay that does not fit**: if a leaver owes money and their final payslip cannot take a
   whole month without going below zero, that month is left for HR to settle by hand. Right, or should the
   final payslip take part of the month?

**Backups and surveys (found in this deploy)**
8. **sudima is not in the nightly backup.** Add it (database and files, same 7 days as the others)?
9. **Survey privacy and backups**: after a survey closes, its sealed answers are destroyed on the live
   system but stay in the nightly backup copies for 7 days (Rize 30). Only someone with access to the
   server's disk could reach them. Acceptable, or should closing a survey also clear them from the
   nightly copies?

## 8. New gotchas (ledger)
S9M-1 (nightly backup covers four databases, not sudima), S9M-2 (hard-linked nightly copies keep a
closed survey's sealed files for the retention period), S9M-3 ("My review" appears only with a review on
a form — look-only checks cannot see it on a site with none). The builders' rows S9A-1..5, S9B-1..6,
S9C-1..6 are in the ledger too.
