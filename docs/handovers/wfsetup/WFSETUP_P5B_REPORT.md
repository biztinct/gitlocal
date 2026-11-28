# WFSETUP P5b — merge, rehearsal, go-live on sudima + payobook, verification (report)

Deploy agent, 24 Nov 2026 (UTC; 25 Nov morning Sydney). Handover `WFSETUP_P5B_DEPLOY_HANDOVER.md`.
Engineering receipt: real technical names on purpose. No credentials in this file.

**Result: GO. Merged and pushed to `19.1` (`b6350b505` merge, `acde1ac17` scripts = the deployed commit),
LIVE on all five databases, 551 s of downtime (19:38:45–19:47:56 UTC).** `pb_workforce_setup` 19.0.1.4.1 is
installed on exactly **sudima + payobook** (owner ruling R2); `pb_hr_workforce` 19.0.4.25.0 and
`pb_workforce_workspace` 19.0.1.1.1 are upgraded on all five. Nothing failed; nothing restored. No rules
confirmed and no roster published on any live database. abm untouched.

## 1. Timeline (UTC, 24 Nov 2026)

| Time | Step |
|---|---|
| 17:01 | Read `/opt/deploy-notes.md`: every START closed (last: Codex Workforce Workspace VERIFIED 10:27). Lock file present but empty and free (03:14, stale) |
| ~18:50 | Release worktree from `origin/19.1` @ `8067b4834` (unchanged since the `wfsetup` base — fast-forward situation, merged `--no-ff`): `b6350b505`; `git diff wfsetup HEAD` empty. Scripts `docs/handovers/wfsetup/p5b/` (clones of `docstudio/w2/`) committed `acde1ac17`; secret scan clean; pushed `8067b4834..acde1ac17` |
| 18:59–19:02 | Prep: staged = commit; `pb_attendance_policy` live tree = commit; previous trees saved; PO gate (setup 790 entries vi/id, workspace 154 vi/id: 0 empty, 0 vendor word); dependency closure (103 modules) installed everywhere except `pb_attendance_policy` on payobook / payobook_template / p0clone / rize (expected); dumps ×5 + file-folder hard links; counts + job snapshots |
| 19:02–19:24 | Rehearsal on hidden copy `wfs_rh_sudima` (§3) — passed; copy, file folder, service, login dropped 19:24 |
| 19:25–19:36 | Extra install-only rehearsal on hidden copy `wfs_rh_payobook` (first install of the rules module there) — passed; dropped 19:35 |
| 19:36 | START line; no signed-in activity on rize/payobook/sudima for 15 min (first try) |
| 19:36–19:38 | Fresh dumps ×5; notes re-read (no HOLD, no open START) |
| 19:38:45 | Service stopped; per-module scoped rsync; addons = staged |
| 19:39–19:47 | Upgrades, one database at a time (§4) |
| 19:47:56 | Service up; five sites warmed (200); DONE line 19:48; lock file removed |
| 19:49–19:57 | Verification (§5), live walks (§6), NOTE line 19:57 |

Downtime **551 s**. Backups `/odoo/backups/wfsetup-p5b-20261124T1900Z/` (prep dumps, go-live dumps, file-folder
hard links, `previous-trees.tgz`). Evidence `/tmp/wfsetup-20261124T1900Z/` on the server.

| Database | Prep dump | Go-live dump (right before the stop) |
|---|---|---|
| payobook | 82,859,054 B | 82,862,186 B |
| payobook_template | 31,864,241 B | 31,866,454 B |
| p0clone | 32,396,152 B | 32,398,725 B |
| rize | 46,343,725 B | 46,347,006 B |
| sudima | 37,743,743 B | 37,746,423 B |

## 2. Merge and tests

- `origin/19.1` had not moved since the `wfsetup` base `8067b4834`, so the merged tree is byte-identical to the
  `wfsetup` tip that P5c tested (101 tests green) and P5a tested (124 tests green). **Choice:** no second local run
  (Mac disk 97 % full); the suites were run instead on the server rehearsal copy of sudima, on the merged code
  and real data (below).
- Suites on `wfs_rh_sudima` (`-u pb_workforce_setup,pb_workforce_workspace,pb_attendance_policy,pb_shift_patterns
  --test-tags` the same four): `pb_attendance_policy` 10, `pb_shift_patterns` 29, `pb_workforce_setup` 105,
  `pb_workforce_workspace` 16 — **1 failed, 1 error, both not code faults**:
  - `TestP5aPlan.test_05_admin_menu_flag`: the test assumes `base.user_admin` (uid 2) is a Settings
    administrator; on sudima uid 2 is `hr@sudima.local` without Settings rights (checked in the database).
    Data assumption of the test. (Ledger WS43.)
  - `TestSetupStatic.test_s2_every_icon_exists`: reads `../pb_import_kit` next to the staged tree (ledger WS36).

## 3. Rehearsal on a hidden copy of sudima

Copy restored from the prep dump as a template database (invisible to the live job runner and web front),
jobs and mail servers off at once (0 / 0), 680 employees = live. Staged trees first in a separate addons path.

| Check | Result |
|---|---|
| `-i pb_workforce_setup -u pb_hr_workforce,pb_workforce_workspace` | exit 0, **89 s**, 0 ERROR, 0 Traceback |
| Data, restored vs installed | identical (roster, working weeks, shifts, rates, overtime requests, days off, employees…); only new record rules (+2), new columns/tables |
| Jobs | cascade re-activated 28 (all were off on the copy) — the go-live snapshot repair handles this; no new job on sudima |
| Throwaway manager (attendance manager + HR user), server timings | `people()` 0.36 s, 678 rows; 3 working weeks; 8 shifts; 6 clocks; rule set draft; `live_plan()` **23.6 s** |
| Step 3 in the browser (tunnel to a separate service on the copy) | 678 people painted **3.7 s** after a full page load (warm); search "BÙI" 27 ms; team CNC → "Tick all" = 24 people ticked in 0.2 s |
| Step 2 | the three working weeks shown as editable weeks (511 + 4 + 2 = 517 people) |
| Step 6 | six clocks (2 sending, 4 "quiet since 23/24 Nov") |
| Step 5 (copy only) | 2027 → "Add them all": 10 Vietnam holidays added (working days 313 → 304) |
| Step 4 (copy only) | worker "1 to 9 minutes late" line already read 0 hours; **Confirm → "Rules confirmed for 678 people."** in 1.5 s; rule set 2 active; 678 people on it (27 without a group became Worker). All 12,384 roster rows already pointed at this rule set before Confirm, so none needed re-pointing; 0 skipped |
| Step 7 plan | step shown 2.0 s, plan ready **23.5 s** later; 4 weeks = 11,354 shifts for 517 people (9,805 already planned + 1,549 new) — consistent with the 12,384 existing drafts (19 Nov–16 Dec) |
| Publish 2 weeks (copy only) | strip "2 weeks · 517 people · 5,162 shifts" → first progress ("Publishing…") **2.3 s**, finished **13.6 s**. Database: 5,162 published, 517 people, 25 Nov–5 Dec (6 Dec is a Sunday off), **0 duplicates per person/day**, all on the active rule set, 0 mails queued ("No emails were sent: email is switched off here") |
| Publish 6 weeks (copy only, the heavy path that MAKES shifts) | 11,867 shifts (4,643 already planned + 7,224 new; 517 days left out = 1 Jan 2027 holiday) → first progress **1.1 s**, first week ticked 2.4 s, finished **36.9 s**. Database after: 17,546 published (= 517 test day + 5,162 + 11,867), 0 duplicates. Local reference at 700 people: first progress 2.7 s, total 68–77 s |
| Calculation job, run once by hand (copy only) | yesterday's 517 shifts published and pointed at the active rule set, then `_cron_policy_calculate()`: **ran in 21.2 s, 0 errors, 0 attendance made** — every shift: "A first and last punch are required." Reason: sudima has **0 clock-ins stored** (0 `pb_clock_punch`, 0 `hr_attendance`); all six connectors have `publish_punches = False` (live, checked) — data stays in 71,063 connector events. Not a code fault; see §8 |
| Other companies | sudima has one company; nothing else written |
| Vietnamese | throwaway login in vi_VN: Workforce tabs "Tổng quan · Lịch làm việc · Bảng công · Thêm · Thiết lập lực lượng lao động", sub-tabs "Tổng quan nhà máy / Hôm nay", numbers "2.062" |
| Service log of the copy | 0 ERROR |
| Clean-up | copy dropped (`dropdb --force`), its file folder, the rehearsal service unit, its confs and the login file removed; 0 `wfs_rh%` databases left |

**Extra rehearsal, payobook copy (install only):** exit 0 in **110 s**, 0 ERROR; one new job (164, the rules
module's 15-minute calculation job); data identical except what a first install of the rules module must move:
new employee columns (employee checksum over the whole row), +1 server action (the job's), +2 creation notes.

## 4. Go-live

Order payobook_template → p0clone → sudima → rize → payobook; staged = commit `acde1ac17`.

| Database | Command | Exit / time / ERROR | Versions after | Jobs active before → after |
|---|---|---|---|---|
| payobook_template | `-u pb_hr_workforce,pb_workforce_workspace` | 0 / 88 s / 0 | hr_workforce 19.0.4.25.0, workspace 19.0.1.1.1 | 40 → 40 (84, 85, 86, 91 re-activated by the cascade, switched back off) |
| p0clone | same | 0 / 81 s / 0 | same | 48 → 48 |
| sudima | `-i pb_workforce_setup -u pb_hr_workforce,pb_workforce_workspace` | 0 / 83 s / 0 | + setup 19.0.1.4.1, rules 19.0.1.0.0 | 91 → 91 |
| rize | `-u pb_hr_workforce,pb_workforce_workspace` | 0 / 85 s / 0 | hr_workforce 19.0.4.25.0, workspace 19.0.1.1.1 | 91 → 91 |
| payobook | `-i pb_workforce_setup -u pb_hr_workforce,pb_workforce_workspace` | 0 / 102 s / 0 | + setup 19.0.1.4.1, rules 19.0.1.0.0 (new) | 58 → 59 (new job 164; job 156 still off) |

Asset purge + `orm_signaling_assets` + `web.assets.version = wfsetup-p5b-20261124T1900Z` on each database.

## 5. Verification

| Check | Result |
|---|---|
| Trees | all 4 server trees = commit (hash of sorted file md5s, skipping `__pycache__`, `*.pyc`, `.DS_Store`) |
| Versions | manifest = `latest_version` for every installed module on all five (14 ok rows; setup + rules modules "not installed" on payobook_template, p0clone, rize, as intended) |
| Setup module installed on | **payobook, sudima** only |
| Jobs vs prep snapshot | payobook 111 → 112 rows, 58 → 59 active (the one new job: 164 "Attendance policies: calculate published shifts", every 15 min — finds nothing until a rule set is confirmed); the other four identical |
| Data right before the stop vs installed | payobook_template, p0clone, sudima identical; rize messages +6 (tracking notes on 3 jobs + 3 server actions, as in earlier deploys); payobook messages +2 (creation notes of the new job + its server action), +1 server action, employee whole-row checksum (new columns of the rules module) — as rehearsed |
| Roster, working weeks, shifts, overtime rates, overtime requests (with their rate row), days off, rule sets, mail queue: prep → now | identical ×5 (payobook: new empty rule-set tables) |
| Compiled code | setup screen in the bundle on payobook + sudima; translated, trimmed workspace code on all five |
| Server log since the stop | 0 ERROR / CRITICAL, 0 Traceback, 0 asset errors; one service process; five sites 200 |

## 6. Live walks (Chrome)

**payobook.com, QA login** (Settings administrator + attendance manager; company "Payobook Vietnam JSC"):
- Settings › HR › "Workforce setup" card → Open → studio in 0.4 s, "Back to Settings" chip.
- All seven steps open: 1 "No shifts yet" with starters; 2 "Add a shift first"; 3 4,553 people (1.6 s); 4 rules
  (0 people on a rule — the rules module is new here); 5 calendar, 2026 holidays offered; 6 one clock "Waiting for
  IT"; 7 checklist.
- **Harmless edit + undo:** the handover's "rename a working week" and "give a working week" are impossible here
  (this company has no shifts and no working weeks). **Choice:** the step 3 bulk "Late rule" instead — ticked 3
  people → Worker → "Apply to 3" (1.8 s, "3 people set to the Worker late rule.") → **Undo**. Database: all three
  back to empty (only their change stamp moved). **Finding:** after Undo the table kept showing "Worker" until the
  page was reloaded — display only.
- Workforce menu: payobook's companies all use the **classic** Workforce menu (grouped menu switched off on every
  payobook company), so the four tabs do not show there by design; the classic menu opens unchanged. Not switched.
- Console: no errors, no warnings.

**sudima.payobook.com, read-only:** the earlier QA login 2501 (attendance manager) switched on with a fresh
password for the walk and off again with another random password afterwards.
- Studio, step 3: 678 people painted 3.9 s after a full page load; rail "8 shifts ready / 3 working weeks ready /
  161 people have no working week".
- Steps 1, 2, 4, 5, 6 open in ~0.1 s each (eight shifts; three working weeks; 651 Worker / 0 Manager, rules not
  confirmed; 2026 holidays not set; six clocks, four quiet since 23–24 Nov).
- Step 7: plan ready in 25.5 s: 4 weeks = 11,354 shifts for 517 people; "1 thing above still needs you before you can
  publish" (rules not confirmed). Nothing pressed.
- Workforce: **Overview · Roster · Timesheets · More · "Workforce setup"**; Shifts & patterns / Rules & calendars /
  Connections gone. A first-sign-in "Welcome to Payobook" tour card appeared and was left alone.
- Console: no errors, no warnings. Roster, rules, days off, working weeks re-checked after the walk: unchanged.
- Screenshots: inline only — the browser tool refuses to write files outside its own folders (as WS12).

## 7. Decisions I made (unsure → what I chose)

1. Local re-run of the suites skipped (identical tree, disk); ran them on the sudima copy instead (§2).
2. Added an install-only rehearsal on a payobook copy (first install of the rules module + a 4,582-person
   database) — not asked for, cheap insurance.
3. Calculation job: "0 attendance" accepted as a pass of the job itself (no errors on 517 shifts); the cause is
   sudima's clocks not sending clock-ins, not the release. Reported instead of improvising with fake punches.
4. Overtime rate fix (P3 report §7 item 1) shipped as designed: rate rows are the same on all five databases, so for
   people of Vietnamese nationality in company 1 a public-holiday overtime request created from now on uses the
   Vietnam row, 300 %, instead of the "Default" 250 %. Existing requests keep their rate (payobook: 24, others 0 —
   checksums identical before/after).
5. payobook edit: late rule + Undo instead of the working-week edits (no working week exists there).
6. payobook menu: not switched to the grouped menu (would have been a second change to demo settings).
7. sudima walk login: re-used Codex's disabled QA login 2501 rather than creating a new user.
8. Peers: this agent has no way to list other live sessions; coordination was through the deploy notes, the lock
   and the 15-minute quiet check (as the DOCSTUDIO W2 deploy did).

## 8. What the owner should look at first

1. **Sudima's time clocks send nothing into pay.** All six clock connections have "send clock-ins" switched off;
   sudima holds 0 clock-ins and 0 attendance records. Confirming the rules and publishing the roster will not make
   any paid hours until clock-ins are switched on. Four of the six clock PCs have also been quiet since 23–24 Nov.
   (The step 7 finish card says "Clock-ins now turn into paid hours" — not true on sudima today.)
2. **Sudima has no public holidays for 2026** (and none for 2027): step 5 offers 12 for 2026 with one click.
3. Rules on sudima are still a draft (nothing confirmed, as the handover requires); 161 of 678 people have no
   working week; step 7 needs ~25 s to work out the plan on the server (~2× the local machine).
4. Holiday overtime for Vietnamese nationals: 300 % from now on (§7.4) — the legal rate, but a change.
5. Small fault: after Undo of a "Late rule" change in step 3 the table keeps showing the new rule until reload.
6. Not mine, found on the server: database `_test_sudima_policy_20261119` (192 MB, 0 jobs, 3 logins on; name not a
   valid web address) and file folders `p3ad1check`, `p4copy_payobook`, `p5copy_payobook` without databases.

## 9. Left for later

- `pb_workforce_setup` on rize, payobook_template, p0clone: row in `docs/deploy/PENDING.md` (when the owner says).
  Those three already run the new workspace + overtime code; installing will also install the rules module there.
- The two test assumptions (WS36, WS43) could be made data-independent.
- Re-read §8.1 with the owner before anyone presses Confirm on sudima.
