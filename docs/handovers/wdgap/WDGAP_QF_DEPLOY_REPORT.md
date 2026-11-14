# WDGAP QF — deploy report (merge QF1–QF5, live ×5, verify)

Merge-deploy-verify agent, 2026-11-14. Handover `WDGAP_QF_DEPLOY_HANDOVER.md`.
**Result: merged, pushed to `19.1` at `d3fba29ea`, LIVE on all five databases** (payobook,
payobook_template, p0clone, rize, sudima). ABM and every other database untouched.

## 1. Merge

Branch `wdgap-qf-merge` from `origin/19.1` @ `1065e98bf`; `origin/wdgap-qf1` … `qf5` merged one
at a time with `--no-ff`. The 18 modules are disjoint: **the only conflict was
`docs/handovers/wdgap/WDGAP_LEDGER.md`** (add/add in each merge after the first). Resolved as
the union: QF1's copy as the base, D1–D6 kept, each phase-map row from its own branch, all 31
gotcha rows kept (QF1 5, QF2 7, QF3 7, QF4 5, QF5 7). QF1, QF4 and QF5 had each numbered their
rows from W1, so ids are now phase-prefixed (`QF1-W1`, `QF4-W1`, `QF5-W1` …, note added in the
ledger); QF2's two-column "gotcha | fix" rows were folded into one cell. No code, `.po` or
`.pot` conflict.

Static gates on the merged tree (160 changed files vs `origin/19.1`): all 91 changed Python
files compile; 15 XML files parse; 22 `.po`/`.pot` parse with 0 msgstr naming the vendor. Three
placeholder differences in `pb_comp_ben/i18n/vi_VN.po` (`%(day)s %(month)s` → `%(day)s/%(num)s`
and two siblings) are **already on `origin/19.1`** and deliberate (the code passes `num`). The
vendor-name grep of added lines outside docs gives 19 hits, all technical (imports, `<odoo>`
roots, `/odoo` paths, comments, tests asserting the name is ABSENT). Two test-only fixture
passwords appear in new test files (`Qf5-…`, `wdgap-qf3-portal-probe-…`): local test logins,
not real credentials.

### 1.1 Combined local tests

Fresh copies of `upd_p6_t_tpl`, `-u` the 18 modules + `pb_updates`, `pb_clock` (UPDATES G97),
own ports, jobs off, `--log-level=info`; each copy dropped right after.

| Run | Result |
|---|---|
| The five phases' new tests together (`wdgap_qf1..5`) | **118 tests, 0 failed, 0 errors** (QF1 21, QF2 12, QF3 24, QF4 40, QF5 21). 9 ERROR log lines, exactly the deliberate ones the reports name (QF2 3, QF4 6) |
| Full suites of all 18 modules (`/biz_approval_workflow,…,/biz_access`) | **2,088 tests, 18 failed, 14 errors.** 31 of the 32 are in the five reports' baselines (list below). **One was new**: `biz_access` `TestNoProductNameInTheGenericLayer.test_no_markup_string_names_a_product` |
| `/biz_access` again after the fix | **260 tests, 0 failed, 0 errors** |

The new failure: QF5 put the product name into `biz_access` (the product-agnostic layer) — the
hint "…My Payobook logins are not included yet." in `access_board.xml`. Fixed in commit
`d3fba29ea`: "Employee self-service logins are not included yet." (Vietnamese updated; version
unchanged — 19.0.1.13.0 had not shipped). Ledger row QFM-1.

The 31 known failures (all in the baselines of QF1/QF3/QF4 reports; template data, old
untranslated strings, archived admin, Google, hub order): `TestAttendanceFlow` 04/05/07/13;
`TestLeaveRules` ×6; `TestTimeoff` 03/05; `TestInboxFacade.u10`; `TestApprovalStaticContract`
colour; `TestVietnameseIsComplete` u13 (pb_approval_config) and t4c (pb_pay); `TestP7Vietnamese`
z06d/z06e; `TestEgressSeams.test_04e`; `TestP1bSidebar`; `TestP2Sidebar`; pb_hiring
`TestClientReview`, `TestRecruitInterviewsP5.07b`, `TestRecruitJoining.11`,
`TestRecruitPrivacy` 02/02b/08, `TestRecruitPrivacyFiles.02`, `TestRecruitStages.13`,
`TestRegistersP9.08`, `TestTheCover.t7`. QF5's baseline failures (`TestThePeopleList`,
`TestAccountDesk.d9`, `TestAccountType` t2_11/12) passed on this template.

Local disk: the builders' five leftover test databases from today (`qf1_a`, `qf1_full`,
`qf1_basefull`, `qf4_walk`, `qf5_base`, ≈3 GB) were dropped with their filestores; free space
4.9 → 8.3 GB. Other sessions' databases left alone.

Pushed: `1065e98bf..d3fba29ea  19.1` (no force; `origin/19.1` had not moved).

## 2. Read-only checks on live before any change

| Check | payobook | payobook_template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| a. Open START in `/opt/deploy-notes.md` | none (last: WORKFLOW-2 P6a DONE 00:46 UTC) | | | | |
| b. Server | disk 30 GB free of 77; memory 3.8 GB, 2.2 GB available; backups folder 18 GB | | | | |
| c. Scheduled jobs (total / active) | 103 / 51 | 91 / 32 | 91 / 40 | 91 / 83 | 91 / 82 |
| d. Benefit rows still "Covered" with an end date in the past | **0** (2 covered) | 0 (0) | 0 (0) | **0** (4 covered) | 0 (0) |
| e. Outgoing mail server inside the app | **1 active** ("Payobook Outgoing Server", Gmail, port 587) | none | none | none | none |
| f. Kinds of leave by unit: day / half day / hour | 50 / 27 / 3 | 43 / 27 / 3 | 43 / 27 / 3 | 78 / 27 / 3 | 43 / 27 / 3 |
| g. PayAI alerts open (all "new", none acknowledged) | 73 | 3 | 13 | 36 | 10 |
| h. The 18 modules installed | all 18 | all 18 | all 18 | all 18 | all 18 |

- e: `/etc/odoo-server.conf` has **no** `smtp_*` lines; payobook's mail goes only through the
  in-app server record. So on payobook the Explorer's "Send regularly" WILL email; on the four
  others it says email is off (by owner choice).
- f, rize: its 27 half-day kinds are the stock/country ones (ID Annual/Sick/Unpaid Leaves, HK
  ×6, Extra Time Off, Maternity, Training Time Off, Belgian kinds …); hours: Extra Hours,
  Unemployment (Weather/Situational), Unpaid. Rize's own seeded kinds (78 whole-day) stay whole
  days. A Rize employee offered one of those 30 kinds would see the half-day / hours choice.
- g: none of these old alerts has a company, so after deploy they are not shown on Home (checked:
  0 company-stamped alerts on every database; the Home card stays quietly absent until the daily
  PayAI job writes new ones).
- Before the deploy all 18 live module trees were byte-identical to `origin/19.1`, so the change
  shipped is exactly the five phases (+ the one-line fix).

## 3. Go live (risky tier)

Evidence on the server: `/tmp/wdgap-qf-20261114T043929Z/`; backups
`/odoo/backups/wdgap-qf-20261114T043929Z/` (payobook 79.6 MB, payobook_template 28.2,
p0clone 28.6, rize 41.8, sudima 28.7; each checked readable by `pg_restore -l`) + the 18
previous module trees. Lock held by its own unit for the whole window; START 04:39, DONE 04:53 UTC.

- **Rehearsal** on a copy of rize (hidden from the live job runner while restoring, then every
  job and mail server switched off): `-u` of the 18 modules with the new code placed first,
  EXIT=0 in 85 s, 0 ERROR/CRITICAL/Traceback; 107 modules reloaded; versions all new; two new
  jobs appeared; 11 kinds set to "several at once"; two-step/idle settings absent. Sign-in by
  `/web/session/authenticate` on a throwaway login with a random password: uid returned;
  `/bizapp` 200, `/my` 200, `/web/login` 200, `/web/two-step` → straight back (nobody covered),
  no idle value in the session. Copy dropped. (First attempt restored nothing — postgres cannot
  read under `/odoo/backups`; re-run with the dump piped in. Ledger QFM-2.)
- Stage = `git archive` of `d3fba29ea` (hash-checked = commit); per-module scoped
  `rsync -a --delete`; no standard addon touched.
- **Downtime 419 s (≈7 minutes)**: stop 04:45:31, start 04:52:30 UTC. Upgrades in order
  payobook_template 78 s, p0clone 77 s, payobook 94 s, sudima 78 s, rize 82 s — all EXIT=0,
  0 ERROR/CRITICAL/Traceback (warnings are the usual registry noise, same as the rehearsal).
- Per database: signal row + bundle purge + `web.assets.version` = `wdgap-qf-20261114T043929Z`.
- Benefits guard: 0 rows past their end date on every database, so the new benefits job is
  left ON everywhere.
- Sites after start: payobook.com, p0clone, rize, sudima 200; payobook_template 200 (local).

### Versions before → after (same on all five databases)

| Module | Before | After |
|---|---|---|
| biz_approval_workflow | 19.0.1.7.1 | 19.0.1.8.0 |
| pb_approval_config | 19.0.1.8.0 | 19.0.1.9.0 |
| pb_payroll_ai_insights | 19.0.3.12.4 | 19.0.3.13.0 |
| pb_dashboard | 19.0.2.2.8 | 19.0.2.3.0 |
| pb_explorer | 19.0.2.6.0 | 19.0.2.7.0 |
| pb_ess_workforce | 19.0.1.3.2 | 19.0.1.4.0 |
| pb_timeoff | 19.0.1.10.0 | 19.0.1.11.0 |
| pb_me_team | 19.0.1.1.0 | 19.0.1.2.0 |
| pb_attendance_flow | 19.0.1.3.0 | 19.0.1.4.0 |
| pb_today | 19.0.1.5.2 | 19.0.1.6.0 |
| pb_schedule | 19.0.1.9.1 | 19.0.1.10.0 |
| pb_goals | 19.0.1.4.0 | 19.0.1.5.0 |
| pb_pay | 19.0.3.7.0 | 19.0.3.8.0 |
| pb_comp_ben | 19.0.1.7.0 | 19.0.1.8.0 |
| pb_hiring | 19.0.2.23.7 | 19.0.2.23.8 |
| pb_probation | 19.0.1.5.0 | 19.0.1.6.0 |
| pb_offboarding | 19.0.1.5.0 | 19.0.1.6.0 |
| biz_access | 19.0.1.12.1 | 19.0.1.13.0 |

### Verification

- **Trees**: all 18 server trees byte-identical to `d3fba29ea`.
- **Versions**: manifest = `latest_version` for all 18 modules on all five (0 mismatches).
- **Jobs**: only the two new jobs added on each database ("send saved Explorer views", hourly;
  "Benefits: end cover after the last day", daily 17:30 UTC), both active; active counts
  51→53, 32→34, 40→42, 83→85, 82→84; nothing lost. On **payobook_template** the upgrade switched
  8 jobs back on that were off (Employee Vault expiry check; Approvals tell/remind; Access close
  leavers' logins; Time clocks pair/watch/re-check; Attendance connectors review) — switched back
  off at once from the snapshot (confirmed off afterwards).
- **Sign-in settings**: `biz_access.two_step_required` and `biz_access.idle_minutes` absent
  (= off) on all five. Not touched.
- QF1: 11 kinds "several at once" + marker set on all five.
- Users (all/active), leave requests, benefit rows and the mail queue identical before/after on
  all five. Server log since start: 0 ERROR/CRITICAL/Traceback. One service process.

## 4. Check on the real system

**Not as the QA login.** The browser was already signed in to payobook.com as the owner's own
account, and this agent may not type a password into a live site. So the walk was look-only in
that session: nothing saved, approved, changed or signed out.

1. **Home**: loads, no error, console clean; the "PayAI noticed" card is quietly absent (no
   company-stamped alerts yet — expected until the daily job runs).
2. **Approvals inbox**: one card is the owner's turn (an experience letter, an allowed kind): it
   has a tick box "Tick to approve it with others"; "Select all on this page that I can approve
   (1)" and the note "Send back and turn down stay one at a time…" show. No money card was the
   owner's turn, so the greyed box could not be seen. Nothing approved (none are DEMO leave
   requests; not done under the owner's name).
3. **Explorer**: "Save view", "Download Excel" and the empty line "Save a view to find it here"
   show. No view saved (it would belong to the owner). The Excel file was built through the same
   server call the button uses and read in the page: header block, "Amounts in VND", one block,
   its own Total, no vendor name. "Send regularly" not opened (needs a saved view).
4. **My Payobook leave form**: not walked (needs a DEMO employee sign-in). The rehearsal opened
   `/my` (200) and the served page script contains the new leave-form code on all four sites.
5. **Pay review** (DEMO Retail pay review · 2026): "Read scores from Goals" shows beside "Paste
   scores"; the preview opened: years "DEMO Goal year 2026 · not closed yet" / "DEMO Goal year
   2025", "1 person has a goals score (0 will change) and 901 have none", the mapping table.
   Closed with Escape; "Use these scores" not pressed.
6. **Access home**: "SIGN-IN RULES — Two-step sign-in is required for: Not required · Sign
   people out when idle: Off". Not changed.
7. **Sign out / in**: not done (it would sign the owner out). Covered by the rehearsal's sign-in
   call and the live checks above.

Other four sites (cheap checks): login page 200 on all; the served page scripts on payobook,
p0clone, rize and sudima all contain "Select all on this page that I can approve", "PayAI
noticed", "Download Excel", "Read scores from Goals", "Two-step sign-in is required for", the
idle watcher and the leave-form preview call.

Observation (small, not changed): the Excel file name reads
`payobook_net_by_department_id_2026-11-14.xlsx` — a field name ("department_id") inside a file
name a user receives. Follow-up for the Explorer.

## 5. Held / left off

- Nothing held. The benefits job is on everywhere (0 rows would end on its first night).
- Both sign-in settings remain OFF on all five.
- Walk steps 2 (approve two), 3 (save/delete a view, schedule drawer), 4, 7 not done for the
  reason in §4.

## 6. Questions for the owner

1. The after-deploy check was done in your own signed-in browser, looking only. Would you like
   me to sign in as the QA test account next time? I can't type its password myself — if you
   sign the browser in as QA first, I can do the full walk (approve two demo leave requests,
   save and delete a view, open "Send regularly").
2. payobook.com sends real email through its Gmail server. Once someone sets up "Send
   regularly" on a saved Explorer view there, those emails will really go out. Is that what you
   want on the demo site?
3. Rize has 30 kinds of leave (mostly Indonesian, Hong Kong and stock kinds) that count in half
   days or hours. If any of them are offered to Rize staff, they will now see "Morning /
   Afternoon" or "From / To" on the leave form. Should those kinds be hidden or switched to whole
   days for Rize?

## 7. New gotchas (ledger)

QFM-1 (product name in `biz_access`), QFM-2 (postgres cannot read `/odoo/backups` → pipe the
dump), QFM-3 (`systemd-run` expands `$$`; `ir_cron.cron_name` is plain text on this build).
