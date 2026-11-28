# WFSETUP P7 — Workforce setup studio on rize, payobook_template, p0clone (report)

Deploy agent, 24 Nov 2026 (UTC; 25 Nov morning Sydney). Handover `WFSETUP_P7_ROLLOUT_HANDOVER.md`. Owner
instruction 2026-11-25: "roll out the changes you have done in Sudima to all other databases as well."
Engineering receipt: real technical names on purpose. No credentials in this file.

**Result: GO. LIVE on all five databases, 89 s of downtime (stop 22:39:57, service listening 22:41:26 UTC).**
`-i pb_workforce_setup` (19.0.1.5.0, pulls in `pb_attendance_policy` 19.0.1.0.0) on payobook_template → p0clone →
rize, each exit 0, 0 ERROR. No module files copied: all 69 custom modules of the studio's dependency closure were
already byte-identical to `origin/19.1` (`55e53b1bd`). Nothing confirmed, published or saved on any live database.
sudima and payobook untouched. abm untouched. Peer copy `zz_wfs_p8_20261125` untouched.

## 1. Timeline (UTC, 24 Nov 2026)

| Time | Step |
|---|---|
| 21:53 | Notes read: every START closed, no HOLD, no lock file |
| 21:57–21:58 | Prep 1: tree check **failed** on `pb_clock` (same version, different hash) → stopped, investigated (§5.1) |
| 21:59–22:00 | Prep 2 (hash skips `releases/*.zip`): 69/69 trees = commit; states + job snapshots ×5; dumps rize 46.4 MB, payobook_template 31.9 MB, p0clone 32.4 MB; rize file folder linked |
| 22:01–22:08 | Rehearsal on hidden copy `wfs_rh7_rize` (§2), copy, file folder, service and login dropped 22:08 |
| 22:08 | START line |
| 22:09–22:36 | Tries 1–9 refused: signed-in activity (sudima until 21:59, then payobook.com Bank layout screens until 22:21) |
| 22:39:17 | Try 10: quiet since 22:24; fresh dumps ×3 (rize kept in `/odoo/archives/rize-wfsetup-p7-20261124T2157Z/`) |
| 22:39:57 | Service stopped |
| 22:40:10–22:41:17 | Installs (§3) |
| 22:41:26 | Service up; five sites 200 |
| 23:10 | DONE line (the session that launched the go-live had exited; the server unit had finished cleanly at 22:41:41 — §5.4); lock removed |
| 23:11–23:20 | Verification (§4), live walks (§6), NOTE line |

Backups `/odoo/backups/wfsetup-p7-20261124T2157Z/`; evidence `/tmp/wfsetup-p7-20261124T2157Z/` on the server.
Scripts `docs/handovers/wfsetup/p7/` (clones of `p5b/` and `p6/`).

## 2. Rehearsal on a hidden copy of rize

Copy restored from the prep dump as a template database (invisible to the live job runner and web), jobs and
mail servers off at once (0 / 0), 313 employees = live. Live addons path (no file ships).

| Check | Result |
|---|---|
| `-i pb_workforce_setup` | exit 0, **25 s**, 0 ERROR, 0 Traceback (275 WARNING = the usual registry warnings) |
| Modules newly installed | exactly `pb_attendance_policy`, `pb_workforce_setup` (no auto-install pulled in) |
| Data restored vs installed | identical (roster, working weeks, shifts, overtime rates + requests, days off, leaves + allocations, payslips + lines, contracts, bank, mail queue, attendance…); moved only: +2 creation notes, +1 server action (the job), employee whole-row checksum (two new empty columns; identical without them), +5 record rules, new tables |
| Jobs | one new job (id 100, "Attendance policies: calculate published shifts", every 15 min); nothing re-activated |
| Rules | 0 rule sets, 0 people on one, 0 roster rows on one |
| Calculation job run once by hand | 0.00 s, picks 0 rows; attendance / roster / overtime unchanged |
| Throwaway manager (server) | `people()` 0.35 s, 231 rows = 231 active people; `rules()` state new; `clocks()` 0 clocks; `live_plan()` 0.06 s |
| Menu | Workforce screen shows the classic rail (Today, Schedule, Time, Overtime, Approvals, Close, Holidays, Patterns, Field, Insights) — not the four grouped tabs. Raw menu tree +2 rows under Workforce › Configuration (§5.3) |
| Old doors | old "Set up Workforce" action → studio; Settings › HR › "Set up Workforce" → Open → studio with "Back to Settings"; steps 1–7 render |
| Console | studio clean; 3 errors on the Pay runs home page = the throwaway user had no payroll rights (server log: access refused on pay run batches) |
| Clean-up | copy (`dropdb --force`), file folder, rehearsal service, confs, login file removed; 0 `wfs_rh7%` left |

## 3. Go-live

| Database | Exit / time / ERROR | Versions after | Jobs active (prep → now) |
|---|---|---|---|
| payobook_template | 0 / 22 s / 0 | setup 19.0.1.5.0, rules 19.0.1.0.0 | 40 → 40: new job 100 switched **off**; `pb_tenants.template_active_crons` 74 → 75 ids (100 appended) |
| p0clone | 0 / 14 s / 0 | same | 48 → 49 (new job 100 on) |
| rize | 0 / 16 s / 0 | same | 91 → 92 (new job 100 on) |

Nothing re-activated by the installs. Asset purge + `orm_signaling_assets` + `web.assets.version =
wfsetup-p7-20261124T2157Z` on the three.

## 4. Verification

| Check | Result |
|---|---|
| Trees | 69/69 closure trees = commit `55e53b1bd` |
| Versions | `pb_workforce_setup` 19.0.1.5.0, `pb_attendance_policy` 19.0.1.0.0, `pb_workforce_workspace` 19.0.1.1.1, `pb_hr_workforce` 19.0.4.25.0 installed on **all five**; every closure module manifest = installed ×5 |
| Jobs | payobook 59, sudima 91 unchanged; payobook job 156 still off |
| Data right before the stop vs installed | identical on the three except, as rehearsed: messages +2, server actions +1, employee checksum (new empty columns; identical without them, 313/313, 14/14, 3/3 empty) |
| Roster, working weeks, shifts, rates, overtime requests, days off, leaves, payslips, mail queue: prep → now | identical ×3 |
| Rules on the three | 0 rule sets, 0 people, 0 roster rows on a rule; 0 setup undo rows |
| Compiled code | studio + clock switch + workspace trim in the bundle ×3 |
| Server log since the stop | 0 ERROR from this release; 0 asset errors; one process. 3 ERROR on **sudima** 22:57–22:59 (§5.5, not this release) |
| Sites | 200 ×5 |

## 5. Decisions I made (unsure → what I chose)

1. **Tree check failed once, on `pb_clock`**, and the handover says stop. The only differing file is
   `pb_clock/releases/PayobookAttendanceConnector.zip`: gitignored, built on the server, a known exception in Codex's
   own release tool. All code equal. Since P7 ships no files and `pb_clock` is not upgraded, I treated it as not a
   difference, skipped that file in the hash and continued (ledger WS51).
2. Order payobook_template → p0clone → rize, so the real tenant went last.
3. **Two raw menu rows** appear under Workforce › Configuration on the three (as on sudima and payobook since P5b).
   They are not shown on screen (the shell hides the classic menu sections; the Workforce rail is unchanged), so I
   judged "menu unchanged" met (WS53).
4. Walk logins: rize used the disabled QA login 2583; p0clone the disabled walk login 3277. Each got the needed
   rights (rize: attendance manager; p0clone: Settings + HR user + attendance manager) and a random password for the
   walk only; afterwards exactly those rights removed, password rotated, login off, password file deleted.
5. The launching session ended after the go-live (the server unit had already finished, DONE result, all three exit
   0). The DONE line was therefore written at 23:10 instead of 22:42; nothing was left half-done.
6. Unrelated finding: sudima log 22:57–22:59, three errors opening Hiring set-up (job-board connection password
   cannot be read: decrypt fails in `pb_hiring/services/connection_crypto.py`). Not this release; reported only.
7. payobook_template keeps **40 active jobs**, although the template is meant to have all jobs off. That was already
   so before P7 (P5b: 40 → 40). Not changed.
8. Commit trailer: `Claude Opus 5.5` (the model that did the work), as in P6.

## 6. Live look (look-only)

- **rize** (QA login 2583): Workforce shows the classic rail (Today, Schedule, Time, Time off, Overtime, Approvals,
  Close, Holidays, Patterns, Field, Insights); old "Set up Workforce" link → studio; steps 1–7 render (5 shifts
  ready, 231 people without a working week, rules not set, 261 working days in 2026, no clock yet, checklist);
  Settings › HR › Set up Workforce → Open → studio in 0.3 s with "Back to Settings". Console: no errors, no warnings.
- **p0clone** (walk login 3277): old link → studio, steps 1–7 render, classic Workforce rail. Console clean.
- Afterwards: 0 rule sets, roster unchanged (p0clone's 5 published rows were already there), 0 undo rows.

## 7. Left for later

- `PENDING.md` row removed (batch done).
- The sudima Hiring connection error (§5.6) for whoever owns Hiring.
- WS36 / WS43 test-data assumptions still open (from P5b).
