# WORKFLOW-2 · Phase 5c handover — repeat for each line, and three small decisions

Designer: Claude (Fable), 11 November 2026. Implementer: Opus agent, same session.
Read first: `WF2_LEDGER.md` (R1–R9, D1–D33, conventions §3, gotchas G1–G71 — binding); `WF2_P5A_HANDOVER.md` **§3.3, §3.4, §4 rail 3, tests T9–T16 and browser U4–U8, U11** — that design is this phase's spec for "Repeat for each line" and is not repeated here; `WF2_P5A_REPORT.md` (§4 deploy as last done, §9 what remains, §10 overlaps, gotchas G65–G71); `WF2_P3B_REPORT.md` §6; then this file. Baseline: `pb_lifecycle` 19.0.1.17.0, 132 Studio tests, live ×5. Target **19.0.1.18.0**.

Design bar (owner, verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Lucide SVG icons, never emoji. Brand indigo `#5A4BB0`, one solid primary button per bar. Every state designed.
White-label (binding): "Odoo"/"OdooBot" never in anything a person can see or receive. Plain English (R8): never "sub-run", "child", "loop", "iteration", "index" on a screen — "for each receipt", "line 2 of 5".

Order of work (ship what is complete and proven, in this order): §2 small items → §1 repeat. The repeat ships only whole: engine + people surfaces + all three canvases + tests. If it cannot be finished safely, leave it entirely out of the deploy (no step type visible) and report exactly where it stands on a branch-free WIP commit guarded by not registering the step type.

## 1. Repeat for each line

Build exactly `WF2_P5A_HANDOVER.md` §3.3 and §3.4, with these additions from what P5a learned:

- Scheduled workflows (shipped in P5a) may contain a repeat; scheduled each-record fan-out counts parents only.
- The schedule's start-key idempotency pattern (`schedule:<workflow>:<tick>[:<record>]`) is the model for child runs: `line:<parent run>:<step>:<line key>` so a retried worker never starts a line twice.
- Child runs must never be picked up by the scheduled-start scan, the "one automatic workflow per record" check, the record strip switcher, or the default runs table (toggle "Show lines").
- The Flowchart canvas: a workflow **without** a repeat must render pixel-identically to today (prove with a before/after screenshot diff of two shipped drafts). Draw the frame the way the parallel group is drawn; do not refactor layout code.
- Area lines this phase: expense claim receipts only (through `pb_me_expense`'s contract, add-only). Generic sources: each answer of a list question; each person in an Approvals team. Do not invent lines for other areas; list candidates in the report.

Tests: `WF2_P5A_HANDOVER.md` T9–T16 renamed `test_wf2p5c_t1…t8`, plus:
- t9 a repeat inside a scheduled workflow: parents counted once, lines started once across two worker passes.
- t10 send back **inside** a repeat to an earlier step of the same line works and resets only that line; send back to outside is refused.
- t11 a workflow without a repeat: definition, validation and preview output byte-identical to baseline for three shipped fixtures.
Browser: U4–U8 and U11 of the P5a handover, plus the canvas pixel diff.

## 2. Small items

### 2.1 "Around a date on the record" shortcut (D30)
In the schedule picker's "How often" choices add "Around a date"; choosing it switches the workflow's start to the shipped "At a record date" trigger and opens that trigger's own settings in place (and back again if the person picks another schedule kind). One engine. The sentence reads as that trigger already reads. Test: switching both ways leaves a valid definition and loses no filter.

### 2.2 Three reminder timetables declared (D31)
Contract end, probation end, document expiry: each owning area's contract gains `reminder` effects (who is told, when relative to which date, in plain words) read from the area's real settings (not hard-coded numbers where a setting exists — inventory §2.4 and P5a report §10.2 name the jobs). Studio shows them under "already happens" for that record type and Review warns `repeats_existing` when a scheduled or record-date workflow on the same records sends a message/task within the same window to the same kind of person. **The reminders themselves do not change**: add-only contract methods, restart-loaded, no version bump of the areas unless a data file changes. If one of the three has no natural record type contract yet (e.g. employee documents), add a minimal read-only contract (stages optional) and say so. Tests: each declared; warning fires; no reminder job touched (job id lists identical; the areas' own reminder tests still pass).

### 2.3 A narrow right: "See everyone's approvals" (D32)
- Today the inbox's Everyone scope needs one of `ORG_GROUPS` (`pb_approval_config/models/inbox_facade.py:47-49`: approval set-up, HR manager, payroll manager) — all far broader than looking.
- Add one new group "See everyone's approvals" (read-only: the Everyone scope in the Approvals inbox and opening a request to read it; **no** deciding on other people's steps, no set-up, no HR or payroll rights) and add it to `ORG_GROUPS`; record rules/ACL so `biz.approval.request` and its steps are readable company-wide for that group and nothing else changes. Register it in the Access catalogue (`biz_access`) the way other abilities are (find the precedent: `pb_lifecycle/data/workflow_abilities.xml`) with a plain description, so it is granted from the Access screen with an audit row.
- Where the group lives: it needs a data file, i.e. an upgrade of its module. Do **not** bump `biz_approval_workflow`/`pb_approval_config` (G29). Put the group and its rules in the lightest module that already depends on `pb_approval_config` and is upgraded in this deploy anyway (`pb_lifecycle` qualifies) — report the choice. `ORG_GROUPS` gains the xmlid by a restart-loaded edit; guard for the group not existing (`env.ref(..., raise_if_not_found=False)`).
- **Do not grant it to anyone on any live database.** The main loop grants it to one person on rize after the deploy.
- Tests: a user with only this group sees Everyone and can open a request read-only; cannot decide, repair, cancel, or open set-up; other companies' requests stay hidden; with this group a pay manager is treated by D26 as "can see Everyone" (no to-do).

### 2.4 P2b's unproven browser checks
Run and screenshot P2b's U3 (joining checklist for a Hiring joiner: "Chosen in Hiring by …"), U5 (employee claim page with and without a strip), U7 (dock sentence). Fix what they show.

## 3. Binding non-goals and rails

- R1: nothing shipped moves or restyles; R1 audit required. R2: no approval inside a repeat; no status writes; lines read only through the area's door.
- No new scheduled job; job id lists and mail queue counts identical before/after ×5; sudima's Studio job off; no mail server talk (D29).
- No translations (P5b) — but keep every new string translation-ready and list them for P5b.
- Live: never create, enable, start, approve, move, grant or send anything. Never `abm`.
- Approval suites identical before/after (175, same 4 known failures) — this phase touches the inbox facade's group list, so run them.
- Performance: 200 lines in one worker pass within the job's budget; inbox with 200 line tasks grouped; report numbers.

## 4. Deploy and verify

As P5a (`WF2_P5A_REPORT.md` §4): notes file START/DONE "Claude WORKFLOW-2" (re-read immediately before START; another session deploys too), flock, clean staging, service stopped, scoped rsync with before-tarballs, `-u pb_lifecycle` (+ `pb_me_expense` only if its data changed), payobook, payobook_template, p0clone, rize, suites on p0clone, sudima last; identical job lists and mail queues; asset purge ×5; restart; exactly one service process; warm; hashes + `latest_version` ×5; 0 ERROR lines. Cache keys `wf2-p5c`. Confirm on each database that the new group exists and has **zero** users.

Commit per feature, explicit paths. Do not push.

## 5. Report back (`WF2_P5C_REPORT.md`)

Commits, versions; tests; browser proofs incl. the canvas pixel diff; performance numbers; where the new group lives and exactly what it can read; the three reminder timetables as declared (plain words); deploy evidence; deviations; R1 audit; Overlaps found (R2a); self-score vs the design bar; gotchas G72+; **for P5b: every file with WORKFLOW-2 strings lacking vi/id, with counts** (cumulative, all phases), consolidation candidates, and the known-failing baseline tests per module (names) for the closeout; owner decisions needed.
