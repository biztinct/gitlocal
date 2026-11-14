# WORKFLOW-2 · Phase 6a report — the closeout's remaining area items

Builder: Claude (Opus implementation agent), 14 November 2026. Handover: `WF2_P6A_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (G84–G90 added, P6a row marked). Closeout: `WF2_CLOSEOUT.md` §3 updated in place.

## 0. In plain words (for the owner)

| Closeout item | What happened |
|---|---|
| 2. Repeat for each line, more areas | **Time off: each day of a request** and **business trips: each cost line** are live. **Pay runs: not built** — a pay run is not something a workflow can be built on today (it carries no company), so a repeat over its payslips could never be reached. **Equipment handovers and joiner equipment: nothing to repeat** — a handover is one item, and the joining checklist has no equipment lines (a laptop is one step that raises one request). |
| 3. "Sent back" emails for trips and equipment | Live. The employee gets one email with the reason and a button, in their own language. Approvals' own "Sent back to you" stops for them, exactly as for expenses and time off. |
| 4. More reminder timetables | **Training due dates** declared (the person before and after the due date; the manager and the HR lead once late, from Training's own settings). **Time off balance** reminders were already listed since P5a and have no date on a record to compare with. **Pay review** and **asset returns** have no reminder at all — nothing to declare. |
| 5. Drop the old "run as" columns | Done: the four unused columns and the two rule mentions are gone (five database dumps taken first). |
| 6. Time off "sent back" | **Not built — options below for you.** There is no honest way to make every screen say "Sent back" and let the employee fix and resend the same request without touching Time off's status. |
| 7. Line details read again | Live. A receipt changed after the checks started shows its new amount when the next step on it opens; the history keeps "was … at the start". A receipt that was removed closes its own steps with a note and the count drops by one. |
| 12. Translation leftovers | Live: Hiring's own stage names and meanings in Indonesian; "Other request" statuses in Vietnamese and Indonesian; the approval route sentence in Studio now says "only when What this kind of time off asks for is one of Approved by the manager, Approved by both" instead of the code word "validation_type", and is translated; the rest of the employee expense claim pages in Indonesian (113 phrases). |

**Decision for you (item 6):** see §7. Nothing else needs a decision.

## 1. Commits, versions

| Commit | What |
|---|---|
| `7f36e1148` | Drop `execution_user_id` (rules first, guarded pre-migration), `pb_lifecycle` 19.0.1.20.0 |
| `b228170eb` | Repeat for each line: time off days (`pb_timeoff/models/workflow_lines.py`), trip costs (`pb_business_trip/models/workflow_lines.py`); line details read again (`workflow_repeat.py` `_repeat_refresh_line`, `_repeat_line_gone`, `_repeat_line_now`); tests l1–l3, t1, x1 |
| `355fcfde2` | D28 for trips and equipment (`trip_messages.py`, `asset_request_messages.py`, one noupdate template each); `pb_business_trip` 19.0.1.4.0, `pb_assets` 19.0.1.3.0; tests e1–e10 + trip lines door |
| `2de815fd3` | D31 next areas: training timetable (`pb_training/models/workflow_timetable.py`); Studio's window also covers reminders after the date (`after_days`); test tt |
| `03aa91c7e` | Translation leftovers: route words (`pb_lifecycle/models/workflow_route_words.py`), "Other request" statuses (`biz_approval_workflow` .po + `pb_lifecycle` 1.20.0 post-migrate), Hiring stages in Indonesian (`pb_hiring` 19.0.2.23.7 + seed), claim pages in Indonesian; tests r1, o1 |
| `d4fb7036e` | Local browser fixture and checks (`tools/workflow_studio/ui_fixture_p6a.py`, `chrome_test_p6a.cjs`), screenshots `p6a_screens/` |
| (docs commit) | This report, closeout §3, ledger |

Every commit carries its own Vietnamese and Indonesian `.po` entries (three markers; appended or merged, never re-exported; no `.pot` exists in these modules). Not pushed.

Versions: `pb_lifecycle` **19.0.1.20.0**, `pb_business_trip` **19.0.1.4.0**, `pb_assets` **19.0.1.3.0**, `pb_hiring` **19.0.2.23.7**. Not bumped (method-only or translation files, G29): `pb_timeoff` 19.0.1.10.0, `pb_training` 19.0.1.14.0, `pb_me_expense` 19.0.1.2.0, `biz_approval_workflow` 19.0.1.7.1 (translation files only; code untouched), `pb_approval_config` untouched. No workbench file changed → cache keys stay `wf2-p5c`.

## 2. Per item

### 2.1 Repeat for each line (closeout item 2)

| Area | Model found | Built? | Line | Person on the line |
|---|---|---|---|---|
| Pay run → payslips | `hr.payslip.run.slip_ids` | **No** | — | — |
| Time off → days | `hr.leave` (dates + the employee's working schedule) | yes, key `days` | "Mon 16 Nov", values date, hours | no (the request's own "person this is about" already exists) |
| Business trips → legs | **no leg model exists**; a trip has one destination. Its lines are `pb.business.trip.line` (estimated costs) | yes, key `costs` (deviation 1) | "Hotel · 10 Nov", values description, date, category, amount, has a receipt | no |
| Asset handover → items | `pb.asset.assignment` is one row per item; a request has one handover (`assignment_id`) | no lines exist — skipped | — | — |
| Joiner checklist → equipment | `pb.journey.case.task_ids`; equipment is one step (`automation_key='asset_laptop'`) raising one `pb.asset.request` | no lines exist — skipped | — | — |

- **Pay runs (not built):** `hr.payslip.run` has no `company_id`, and Studio's record-type list (`workflow_studio._models`) only offers models with one, so no workflow can be built on a pay run on any live database (checked: no `company_id` column on payobook). The P3b pay run contract is real but unreachable. A payslips door was written and tested, then **left out** (it could never run). Making pay runs a workflow record type needs a company on a pay run (a `pb_payruns` schema change, another programme's module) — owner decision, see §7.
- **Time off days** are counted the way the request's own length is counted: `_list_work_time_per_day` on the employee's (or request's, or company's) schedule, the request's own absence left out, public holidays only when the kind of time off counts them; no schedule → every calendar day. Capped by Studio's own 200 with the shipped sentence.
- **Trip costs** declare nothing but `lines` (no stages, actions or values), so everything else Studio shows for a trip is discovered exactly as before.
- Read only, through the area's door (`sudo()` read, as the receipts door), no writes; R2 unchanged (no approval or status write inside a repeat — the shipped refusals apply).

### 2.2 Line details read again (closeout item 7)

`pb.workflow.run._advance` of a line run first calls `_repeat_refresh_line` — only when the line has a step not started yet (a step may open now) and not on the line's very first walk (`_pb_wf_line_fresh`, its details were read a moment ago). It reads the one line through the area's new optional door `_workflow_line(key, id)` (fallback: scan `_workflow_lines`), updates `line_values`, the line label and the `line.*` facts, and logs one history line "Line details read again: Amount is now 99 (was 10 at the start)." — the start value is taken from the repeat's own snapshot (`answers['_lines']`), so a second change still names the start value. A line no longer on the record: its open steps are skipped with "This receipt is no longer on the record, so its steps were closed.", the line ends (cancelled), the repeat's snapshot and count drop by one and the other lines are renumbered ("receipt 2 of 2"); the walk carries on. If the record or door cannot be read, the start details stay and nothing fails. Only area sources are re-read (list answers and teams are the run's own data).

### 2.3 "Sent back" emails for trips and equipment (closeout item 3, D28)

Cloned from `pb_timeoff/models/leave_messages.py`: `_approval_return` override (email only when the request really turned round to draft), `_approval_requester_notice = ('returned',)` (approved/turned down stay the engine's — these areas have no email of their own for them), `_approval_area_tells_requester` (no address → the engine keeps its copy). Button: trip → `/my/trips/<id>` for an employee-home login (the trip page, `pb_me_trip`, installed on all five), the record for staff; equipment → `/my/requests` for an employee-home login (equipment requests are listed there; `/my/assets` lists handovers only), the record for staff. Language: the employee's login, else their contact, else the company. Templates: `pb_business_trip.mail_template_trip_returned`, `pb_assets.mail_template_asset_request_returned`, noupdate, styled exactly as the time-off/expense ones, vi + id stored translations.

### 2.4 Reminder timetables (closeout item 4, D31)

| Area | Declared? | What it says | Read from |
|---|---|---|---|
| Training (assignment due date) | yes | "3 days and 1 day before a course is due, and on the day, the person gets a reminder email; while it is late, every 3 days." / "When a course is 2 days late, the person's manager is told, then once a week." / "When a course is 5 days late, the HR lead is told, then once a week." (each with "can be … (the reminders are switched off here)" when off) | `pb_training.reminders`, `.manager_escalate_days`, `.hr_escalate_days`; the 3 / 1 / 0 and every-3-days are fixed in the chase itself (no setting exists) |
| Time off balance (carry-forward) | already since P5a | the static row "Once a month, as the carry-forward date comes round…" and the schedule Review warning | — (no date on a record: the cut-off is one company setting, so the per-step window warning cannot apply) |
| Pay review cycle | no | no pay review reminder exists (`pb.pay.review` has only "New pay starts on"; pb_pay's jobs are a nightly recompute and letter printing) | — |
| Asset returns | no | no expected-return date, no job, no setting in `pb_assets` | — |

Studio: `_starts_in_window` now also understands `after_days` (a reminder that keeps going after the date while the thing is open). A row without it behaves exactly as before (P5c test s2 still passes).

### 2.5 `execution_user_id` dropped (closeout item 5)

Before the deploy, on all five databases: only the two rules named it (`My workflow runs`, `My workflow history`); 0 stored filters, 0 views, 0 window actions, 0 server-action codes; 0 workflow runs exist. Repo: no code, view, rule, test or tool names it after the change (the only remaining mentions are this report, the ledger and the docstring of the migration). The pre-migration rewrites the two stored rule domains first, then drops the four columns (guarded; idempotent). `save_draft` still accepts and ignores a retired keyword from an older screen (`**_retired`). Proven on a local copy before anything else (`am_wf2p6a_mig`) and by test x1.

### 2.6 Time off "sent back" (closeout item 6) — not built, options in §7

Facts: a sent-back request is refused by `HrLeaveApproval._approval_return` (`action_refuse()`), nothing on the request marks it as sent back (only the chatter note and the approval request's `return_note`), and the label comes from five different places (employee home `/my/requests` states dict, My Leave `_leave_state_label`, staff cockpit card, the standard form / list / board status, the cockpit's "Refused" saved view). Stock Odoo 19 lets only officers move a refused request back to waiting; an employee cannot resend the same request. So "every surface says Sent back, and the employee fixes and resends the same request" is not possible add-only: the standard screens show the status field itself, and resending the same request is a status change under balance rules. Per D35 nothing was built.

### 2.7 Translation leftovers (closeout item 12)

- **Hiring stages:** the 17 product stages are rows made by the seed (no xmlid), so a `.po` cannot reach them; the translation is the stored value. Indonesian names and meanings (`ID_NAMES` / `ID_MEANINGS` in `pb_hiring/models/journey.py`) are written by the seed and by the 2.23.7 post-migrate, only where a row still carries the product's English and no Indonesian of its own (a client's words are never touched; company-added stages are theirs). Vietnamese was already there on all five.
- **"Other request" statuses:** six labels, vi + id, in `biz_approval_workflow`'s `.po` (three existing vi entries got the extra occurrence, the rest appended); stored labels written by `pb_lifecycle` 1.20.0's post-migrate from that `.po` where missing (`biz_approval_workflow` not upgraded, G29). Checked first: no uncommitted work of another session in that module, no open deploy.
- **Route sentence:** see §0; `biz_approval_workflow` code untouched (inheritance from `pb_lifecycle`, G76). The Matrix screens and the stored route summary are unchanged.
- **Claim pages:** 113 Indonesian entries (`pb_me_expense/i18n/id_ID.po`), all employee claim page templates and their code strings that had Vietnamese but no Indonesian.
- Activity history already written stays as written (stored text) — no work.

## 3. Tests

Local database `am_wf2p6a` (clone of `am_wf2p5b`: vi + id installed; Training and the employee trip pages installed for this phase).

| Suite | Before | After |
|---|---|---|
| Studio (`run_suite.py`) | 152/152 | **160/160** (+8) |
| P6a area tests (trips e1–e5 + lines, equipment e6–e10) | — | **11/11** |
| Approval suites + touched areas, all test modules (§3.1) | 766 compared | **identical** (+11 new, all pass) |
| Message suites (`pb_me_expense`, `pb_timeoff`: P5a + P2b) | 29/29 (P5a/P5b) | **29/29** |

New Studio tests: l1 (pay runs are not a workflow record type — records why payslips were not built), l2 (time off days: counted as the request's own length, labelled, "day 1 of N", single-line door, other keys empty), l3 (equipment requests / joining checklists: "has no lines a workflow can repeat for", plain words), t1 (line re-read: changed → current amount + "was 10 at the start" once; unchanged → nothing logged; removed → steps closed with a plain note, count 3 → 2, siblings renumbered, the repeat finishes with 2/2), tt (training timetable from its settings, after-date warning for the manager, none before the manager is told, none when switched off, jobs unchanged), x1 (columns, fields and rule mentions gone; old keyword accepted; a participant still reads their run), r1 (route words: English identical to Approvals' helpers for four routes without a condition, through the engine too; Approvals itself still prints `validation_type`; Studio's sentence uses the area's words; vi/id differ), o1 ("Other request" statuses and Hiring stages translated).

Area tests: e1 trip sent back → one email, reason, button, record link, destination, no "Odoo", engine copy gone, a retry sends nothing, sent in again and back again → a second email; e2 employee-home login → `/my/trips/<id>`; e3 no address → engine keeps it; e4 switch off → engine copy back, email still goes; e5 Vietnamese and Indonesian subjects; e6–e10 the same for equipment (`/my/requests`); trip lines door.

### 3.1 Approval and area suites, before and after

Every test module of `biz_approval_workflow`, `pb_approval_config`, `pb_business_trip`, `pb_assets`, `pb_timeoff` and `pb_hiring`, run in a shell that rolls back: the **pre-phase code** (a worktree at `20f75a8de` on `am_wf2p6a_base`) and **this phase** (`am_wf2p6a`), side by side. 766 tests ran in both and **every one has the same result** (biz_approval_workflow 67 ok / 2 errors; pb_approval_config 125 ok / the known 4 failures; pb_business_trip 5 ok / 8 errors; pb_assets 10 ok; pb_timeoff 89 ok / 7 errors; pb_hiring 436 ok / 8 failures / 3 errors / 2 skipped — all pre-existing, incl. `test_stage_seed_and_next_stage`, which fails identically before). The 11 new trip/equipment tests pass. Both runs then stopped at the same `pb_hiring` test: `partner_autocomplete` opens a second connection that waits on the test's own lock (a local self-deadlock, identical before and after, not this phase); the last four `pb_hiring` files and `pb_me_expense`'s other files were therefore not reached locally — `pb_me_expense`'s message suites were run separately (29/29 with time off's).

## 4. Browser proofs (local)

`tools/workflow_studio/ui_fixture_p6a.py` + `chrome_test_p6a.cjs` on `am_wf2p6a_ui` (Playwright, Chrome headless; screenshots looked at, in `p6a_screens/`). **P6A_BROWSER_OK, console clean.**

| # | Screen | Result |
|---|---|---|
| 1 | Approvals inbox, the checker: heading "Find cover for the day · … · 5 to do, one for each line · Do all in turn", cards "Find cover for the day · Mon 30 Nov" … with "day 1 of 5" | `p6a_1_inbox_days.png` (a local welcome-tour pop-up sits over the top bar) |
| 2 | Workbench, Journey: "For each day" step ("Days on this time off request · together"), the dashed frame with the "For each day" chip, the side panel "Repeat for: Days" and the live sample "… has 5 days: Mon 30 Nov, Tue 1 Dec, Wed 2 Dec, Thu 3 Dec …and 1 more." | `p6a_2_workbench_each_day.png` |
| 3 | Trip sent back, Vietnamese, as queued: subject, heading, "Chuyến công tác của bạn đến Hà Nội …", reason box "Lý do được nêu", button "Mở chuyến công tác của bạn" | `p6a_3_vi_sent_back_email.png` |
| 4 | Equipment sent back, Indonesian, as queued: "Permintaan Anda untuk Laptop telah dikembalikan kepada Anda.", "Alasan yang diberikan", "Buka permintaan Anda" | `p6a_3_id_sent_back_email.png` |

Time off "sent back": nothing built, so no screen (§2.6).

## 5. Deploy evidence

Risky tier (column drop). Notes file read right before START (last entries: UPDATES P5e DONE 21:21, our housekeeping DONE 23:21; no open START); exactly one service process; `flock`; launched with no "odoo-bin" in the ssh command (G62 — the first launch attempt stopped itself at the process check because my ssh command contained the word; nothing changed, no note written). START **00:37 UTC**, DONE **00:46 UTC** — 536 s, **465 s down**. Script: P5b's, adapted (`/tmp/wf2-p6a-20261114T003708Z/wf2p6a_deploy.sh`).

- **Before:** the eight server trees hashed equal to the repo at `20f75a8de` (nobody else's work overwritten). Live checks for `execution_user_id` on all five: only the two rules; 0 stored filters, views, window actions, server-action codes; 0 workflow runs.
- **Dumps first**, service still running: `/odoo/backups/wf2-p6a-20261114T003708Z/{payobook,payobook_template,p0clone,rize,sudima}.dump` (69 / 18 / 18 / 32 / 19 MB). Tree backups `*-before.tgz` in the same folder.
- Parse gate on the staged files and again in the addons folder: 17 files, 0 failures. Clean staging from `git archive 03aa91c7e` → service stopped → scoped `rsync -a --delete` per module → `-u pb_lifecycle,pb_timeoff,pb_me_expense,pb_business_trip,pb_assets --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (exit 0 each) → on p0clone: **Studio suite 160/160, area tests 16/16** (trips + equipment + time off P5a) → sudima last (exit 0) → no job newly switched on anywhere → probe ×5 → asset signal + purge ×5 → service started → sites 200.
- **Trees after** = repo at `03aa91c7e` for all eight modules. **`latest_version`** ×5: pb_lifecycle 19.0.1.20.0, pb_business_trip 19.0.1.4.0, pb_assets 19.0.1.3.0, pb_hiring 19.0.2.23.7; pb_timeoff 19.0.1.10.0, pb_training 19.0.1.14.0, pb_me_expense 19.0.1.2.0, biz_approval_workflow 19.0.1.7.1 unchanged.
- **Jobs:** active id lists identical before/after on all five (51 / 32 / 40 / 83 / 82); sudima's Studio job **off**.
- **Sent nothing:** emails / outgoing / Approvals outbox / to-dos identical on all five (payobook 3,135 / 0 / 161 / 391; template 0 / 0 / 0 / 0; p0clone 34 / 17 / 8 / 9; rize 861 / 0 / 124 / 89; sudima 18 / 0 / 6 / 4). rize messages +4 = the upgrade's job-name notes (G64), nobody notified.
- **Probe ×5:** run-as columns 0, rules/views/filters naming it 0; lines declared: time off `days`, trips `costs`, claims `receipts`, pay runs none; both templates present with en / vi / id subjects; trips and equipment own "returned"; 3 training rows; "Other request" statuses in vi and id; Hiring stages 17 / 17 Indonesian names / 17 Indonesian meanings; 0 workflows switched on, 0 live runs; route words active.
- One service process after start; 0 ERROR/CRITICAL in the five upgrade logs and in the service log since the start. Workbench files unchanged → no cache-key bump.
- Evidence: `/tmp/wf2-p6a-20261114T003708Z/` (steps, gate, upgrade logs, suites, probe, job and queue snapshots, versions, hashes, warm, processes).

**Rollback:** stop; extract each `*-before.tgz` over its module folder (scoped); `-u pb_lifecycle,pb_timeoff,pb_me_expense,pb_business_trip,pb_assets` on the five; start. The old code re-creates the four `execution_user_id` columns empty (nothing read them); the dumps hold every database as it was at 00:37 UTC. The new stored translations (templates, stage words, status labels) stay and are harmless.

Nothing created, switched on, started, approved, moved, granted or sent on any live site. ABM untouched. No mail server touched (D29).

## 6. R1 audit — every visible change to shipped screens

- **English output unchanged** everywhere except the one plain-words fix: the approval route sentence in Studio's "Already happens" for a route with a condition ("…, only when What this kind of time off asks for is one of Approved by the manager, Approved by both" — was "…, only when validation_type is one of manager, both"). Proven byte-identical for routes without a condition (r1); the whole Studio suite, incl. P5b's English golden file (p1), passes.
- **Studio editor:** "Repeat for each…" on a time-off or trip workflow now offers "Days" / "Costs" (was: "has no lines a workflow can repeat for"). Nothing else in the editor changed (no workbench file touched).
- **Already happens:** training assignments list three reminder rows; date-based training workflows may get the shipped "already reminds people on its own timetable" warning.
- **Tasks, inbox, strip, progress** for lines: unchanged wording; a line's label and values may now update when a step opens; a removed line shows as stopped with its note.
- **Messages:** two new emails (trip / equipment sent back); Approvals' own "Sent back to you" stops for those two areas for the person who sent it in (when they have an address and the switch is on).
- **Languages:** Vietnamese/Indonesian readers see translated Hiring stage names (id), "Other request" statuses, route chips and sentence, the employee claim pages (id).

## 7. Owner decisions needed

1. **Time off "sent back" (item 6).** Today: the email says "sent back" and why; every screen says "Refused"; the employee makes a new request.

   | Option | What changes on screen | Cost | What you lose |
   |---|---|---|---|
   | A. Keep as is | nothing | none | screens say "Refused" for a send-back |
   | B. A "sent back" mark on the request | the employee's own pages and the staff Time off cards say "Sent back" | ½–1 day; one new field in Time off; small changes in the employee pages | the standard time-off form, list and board still say "Refused" |
   | C. "Ask again" on a sent-back request | a button on the employee's request that opens a new request already filled in (same kind, dates, note) | about 1 day | the old request stays refused; a new one is made (balances behave as for any new request) |
   | D. A real "Sent back" status / resend the same request | every screen, and the same request goes back to "Waiting for approval" | 2–3 days and a change to Time off's status and balance rules | needs your explicit go-ahead (D35) |

   Recommended: B + C together if people find "Refused" confusing; otherwise A.
2. **Repeat over payslips** needs pay runs to be something a workflow can be built on (a company on each pay run, in the pay run module). Worth a small phase only if you want workflows on pay runs at all.

## 8. Deviations from the handover

1. **Trips: cost lines, not legs.** No leg model exists anywhere; the handover said "if trips have no leg lines, say so and skip". The trip's own cost lines are the trip's only lines and the exact equivalent of receipts (P5c §9.3 named "legs/expenses"), so they were offered as "Costs". Easy to drop if unwanted (one file).
2. **Pay run payslips not shipped** although written and tested: unreachable (§2.1).
3. **Line re-read happens when a line step may open** (the line's walk), not on every screen read — cheap and the same door; list-answer and team lines are not re-read (they are the run's own data).
4. **Training rows** name the fixed 3 / 1 / 0 days and "every 3 days" as the chase does — there is no setting for them.
5. **Other request statuses** reach the stored labels through `pb_lifecycle`'s post-migrate (the shared module is not upgraded); a later upgrade of `biz_approval_workflow` loads the same words from its `.po`.

## 9. Overlaps found (R2a)

1. **"Days of a time-off request" vs Time off's own per-day logic** — the door reuses the standard per-day working-time reader the request's own length uses; nothing second built.
2. **Trip/equipment sent-back email vs the engine's "Sent back to you"** — one owner per message (D6/D28): the area's email; the engine's stops for that person. No decision needed.
3. **Training reminders vs Studio reminders** — declared, not moved; Studio warns before a repeat (D31). No decision needed.
4. **Route sentence** — Approvals' builder screen already translates its own sentence in the browser (`sentence.js` with `_t`); Studio's server-side copy now does the same. Two builders of one sentence remain (browser and server), as before; listed for the Approvals owners.

## 10. Gotchas (ledger G84–G90)

See `WF2_LEDGER.md`.

## 11. For phase 6b

- No workbench file was touched; cache keys stay `wf2-p5c`. The workbench's own words for the new sources come from the server (`metadata().line_sources`: "Days" / "day", "Costs" / "cost" — translated); the editor chrome around them is still English (6b's job).
- New server strings that the editor shows are already in `pb_lifecycle`'s `.po` (route words, line re-read history lines).
- `repWords` in `repeat.js` lower-cases the area's singular for "For each day" — works for the new sources as is.
