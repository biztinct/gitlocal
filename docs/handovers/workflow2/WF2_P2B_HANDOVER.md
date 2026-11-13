# WORKFLOW-2 · Phase 2b handover — one message per event, one owner per message

Designer: Claude (Fable), 11 November 2026. Implementer: Opus agent, same session.
Read first: `WF2_LEDGER.md` (R1–R9, D1–D25, conventions §3, gotchas G1–G54 — binding), `EXISTING_BEHAVIOUR_INVENTORY.md` (Part 1 §1.1, §1.2, §1.4, §1.5, §1.6; Part 2 §2.1; Part 3 overlaps 2, 3, 10; Part 4), `WF2_P4B_REPORT.md` (§4 deploy, §6 status words, §9, §11), then this file. Baseline: `pb_lifecycle` 19.0.1.15.0, 122 tests, live ×5.

This phase works **in the areas**, not in Studio's engine. It changes what real people receive on a real client's site (rize). Treat every removal as reversible and prove every one.

Design bar (owner, verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Lucide SVG icons, never emoji.
White-label (binding): "Odoo"/"OdooBot" never in any label, email subject/body, to-do, page or `.po`. Plain English (R8).

## 1. Scope

1. **Approvers are told once (D5).** When an Approval Matrix route is live for a request, only the approval engine tells the approver. Each area's older duplicate to-do/email to the approver is not sent in that case. Areas listed in the inventory overlap 2: pay changes and pay reviews, overtime, contract extensions (email, to-do and their own overdue email), org chart plans, resignations, goals (the switched email), time off (the standard to-do), probation (to-do to the reviewer). When no route is live, today's behaviour is untouched.
2. **Requesters: one message, one owner (D6).** The area owns the message to the person who asked. Where an area already sends "approved / turned down" (time off, goals, goal changes, resignations — verify the list), the approval engine stops sending its own copy for that area. Gaps are filled in the area: **expense claim approved, turned down and paid** (none sent today). Every requester message must reach employee-home logins.
3. **New joiners: split by date (D7).** Hiring's "Before they join" owns everything before the start date; the joining checklist owns day one onward. The buddy chosen in Hiring is carried into the checklist and never asked again; the laptop request is raised from the answer already given in Hiring; a step that Hiring already completed is shown as done-by-Hiring on the checklist, not repeated.
4. **Owner decisions from P4b:** status words (D22), claim page strip only when it adds something (D23), candidate with no email → recruiter task (D24), dock wording under the task line (D25).
5. **Studio's "already happens" stays true:** after the changes, each touched area's `_workflow_effects` (contract) says what now really happens.

### Binding non-goals

- Do not remove or rewrite any message code. Each suppression is a guard around the existing send (`if the engine already tells this person: skip`), so removing the guard restores today's behaviour.
- Do not change approval routes, who approves, the old built-in ladders (inventory overlap 1 is not in scope), or any message when **no** route is live.
- Do not touch Hiring's automations or candidate emails, the letters flow, checklists' self-running steps (other than the D7 items), training/goals chasers (overlap 4 leaves them).
- Do not migrate running joining checklists; D7 applies to checklists started after deploy, and to open ones only where a step has not been done yet and the Hiring answer exists (never undo a done step).
- No new scheduled job. Job lists identical before/after.
- No new email to anyone except the three expense messages. No message is sent by the deploy itself (no backfill: claims approved before the deploy get nothing).
- Version bumps only where data files change; method-only edits load on restart (G29). List reverse dependents before any bump of a widely-depended module and stop if it is `biz_approval_workflow` or `pb_approval_config`.

## 2. Verified plumbing

Use the inventory's file:line references for each area's sends (Part 1 sections named above) — they were verified on 11 Nov at `f68945ecc`+; re-open only the lines you edit, and report any that moved. Engine facts:

- Outbox `biz.approval.outbox` (`biz_approval_workflow/models/outbox.py:46`, kinds :18-28, `_queue` :68 refuses share users :70, `_deliver` :108-122 posts a message + schedules an activity). "Your approval is needed" is queued when a step opens: `engine._activate_next` `engine.py:1039`. Requester results are outbox kinds too (find the exact kinds and where queued; report).
- The engine "never writes to people who sign in as employees on the employee home" (inventory fact 4) — keep it that way; areas own requester messages.
- Whether a route is live is per company and per approval key (data, not code — inventory Part 4). Find the engine's existing "is there a live route / open request for this record" method and use it; do not write a second resolver.
- Employee home: "For you" card and `pb.workflow.notice` (P4a) are for workflow notices only — do **not** reuse them for expense messages. Requester messages reach an employee by email to their work email and show on the request page/My requests (existing surfaces; `pb_me_expense/models/pb_me_home.py:17,48`, `me_expense.py:455-494`).
- Status word sources and the four differing values: `WF2_P4B_REPORT.md` §6 and the tool `tools/workflow_studio/status_words.py`.
- Strip pages list: `HOME_PAGES` in `pb_lifecycle/models/workflow_strip.py`; expense page template `pb_me_expense/views/portal_templates.xml:378` ("With X" :448).
- Candidate participant: `pb_hiring/models/workflow_contract.py` (`participants`, `_workflow_participant`), Studio `workflow_reach.py`; today a candidate without an email stops the step with a plain reason.
- Dock: `pb_mission/static/src/js/pb_dock.js` (task line from P4b; "Nothing is waiting on you" below it).

## 3. Design

### 3.1 One question, asked the same way everywhere (D5)

- Add one helper on the engine (method file in `biz_approval_workflow`, restart-loaded): `tells_approver(record, user=None)` → True when an open request with a live route exists for that record (and, when `user` is given, the engine has queued or will queue a notice to that user for the waiting step). Thin wrapper over the existing lookup.
- A system parameter `biz_approval.single_notice` (default on; read through the helper) is the kill switch: set to `0` and every area behaves exactly as before the phase, no deploy needed. Document it in the report's rollback section. No settings screen for it.
- In each area, wrap the duplicate approver send in `if not engine.tells_approver(record, approver): …`. Where the area's send goes to **more** people than the engine tells (e.g. pay changes to up to 10 people in a group), only the people the engine tells are skipped; report each such case with who still gets what, and list it under Overlaps for the owner if it looks wrong.
- Contract extensions: with a live route, keep exactly one chaser — the engine's (D2); the area's own overdue email is skipped under the same guard.
- Each area's chatter/history line stays (the record still shows what happened); only the notification to the approver is skipped.

### 3.2 Requester messages (D6)

- Engine side: a model may declare `_approval_requester_notice = 'area'` (class attribute, default absent = today's behaviour). When set, the engine does not queue its "approved / turned down / sent back" notice **to the requester** for that model; everything else (approvers, pass-up) unchanged. Set it only on models whose area demonstrably sends each of those results itself; prove per result with a test. "Sent back" must not be lost: if the area has no "sent back" message, leave the engine's for that result (declare per result: a set like `{'approved','refused'}`).
- Expense (pb_me_expense): three new mail templates (approved, turned down with the reason, paid with amount and date), sent once at the status change by the area, to the employee's work email, in the employee's language, with one button to the claim on the employee home (or the staff form for staff logins). Subject lines plain: "Your expense claim was approved". Idempotent (a flag/time per result on the claim so a retry or a re-approval path never sends twice; re-submission after a refusal may send again for the new decision). The claim's contract effects gain these three rows so Studio shows them under "already happens" and warns on a repeat.
- For each other area in overlap 3, produce a table: result × who sends today × who sends after. No area may end with zero messages for a result that had one.

### 3.3 New joiners (D7)

- Read inventory §1.4 "Offer / Before they join" and §1.5. Boundary: start date. On creating a joining checklist for someone who came through Hiring: copy the buddy from Hiring's answer onto the checklist's buddy step and mark it "Chosen in Hiring by … on …" (done, not asked); the laptop step raises the equipment request from the Hiring answer when it exists (else asks as today); "meet the team" is Hiring's — if the checklist template has an equivalent pre-start step, show it as "Handled in Hiring" and do not notify anyone. Day-one invite stays with the checklist. People who did not come through Hiring: unchanged.
- Hiring's list: any item it has that is dated on/after the start date and duplicates a checklist step is shown as "Continues in the joining checklist" with a link, not asked twice.
- Both contracts' effects updated so Studio's "already happens" names the single owner.

### 3.4 P4b decisions

- **D22 status words**: change the four labels at their sources (and their `.po` entries for vi/id where the string is translated — a translation fix is two fixes: the `.po` and any stored value; follow the ledger/po rules); re-run `status_words.py` and attach the after table (zero differing rows expected, or each remaining one explained). Selection labels on shipped models are user-visible everywhere (filters, exports) — list every screen where a word changed (R1 audit).
- **D23**: employee expense claim page shows the strip only when a workflow step or a user-made stage is involved; otherwise only the existing "With X" box. Apply the same rule to every page in `HOME_PAGES`. Staff record screens unchanged.
- **D24**: a step to "The candidate" with no email waits; the candidate's recruiter (Hiring's subject) gets a task through the P4a path ("Add an email for {candidate}", opens the candidate; teams/cover apply; shows in the Approvals inbox Tasks group). When the email appears (checked by the existing worker pass and immediately on the next engine touch), the link is sent once and the helper task closes itself. No recruiter → the role from D19 → the publisher.
- **D25 dock**: when the task line shows, the dock's empty sentence below must not say nothing is waiting; word it so both are true ("No approvals are waiting on you").

## 4. Safety rails

1. **Before any code:** a read-only census on all five live databases → table in the report: per company and approval key, is a route live; counts of the last 30 days of each duplicate message per area (activities/mails by template or summary). This tells the owner exactly what will stop on rize. If the census shows an area where the engine message would **not** reach the approver (e.g. approver is an employee-home login, or the route's outbox is failing), do not guard that area; report it.
2. Never skip a message unless the engine's own notice to that same person is proven for that record (helper returns True only then). When in doubt, send.
3. Kill switch tested both ways.
4. Tests must not send real mail; live deploy sends nothing (no backfill, no test claims on live). On live never create, approve, pay or move anything.
5. No "Odoo" in any new template (render and scan subject + body in en, vi, id).
6. Company isolation; language of the recipient; employee-home logins receive the expense messages (test with a share user).
7. Other sessions: areas such as `pb_records`, `pb_updates`, `pb_payruns` screens are being worked on by others — touch only the lines this phase needs, explicit `git add` paths.
8. Deploy set payobook, payobook_template, p0clone, rize, sudima; never `abm`.

## 5. Test cases

Put area tests in each area's own test folder (clone its existing test style); Studio-side in the Studio suite (`test_wf2p2b_tN_…`).

- T1 helper: live route + open request + notice queued → True; no route → False; closed request → False; kill switch off → False.
- T2..T9 one per area in overlap 2 (pay change/review, overtime, contract extension incl. overdue email, org chart plan, resignation, goals, time off, probation): with a live route the approver gets exactly one notice (the engine's) and the area's history line still exists; without a route the area's message is sent exactly as before (snapshot of activity/mail counts before the phase vs after); kill switch restores the duplicate.
- T10 group case: area notifies N people, engine tells k of them → the other N−k still get the area's message.
- T11 requester ownership: for each declared model/result exactly one message to the requester; "sent back" never lost.
- T12 expense approved / turned down / paid: one mail each to the employee (staff and employee-home login), right language, reason and amount filled, link correct, never twice on retry, none on deploy for old claims; contract effects list them; Studio warns on a repeat email step.
- T13 joiner from Hiring: buddy carried, not asked; laptop request raised from the answer; pre-start step shown as handled; non-Hiring joiner unchanged; an open checklist with the step already done untouched.
- T14 status words: the four labels at every source; `status_words.py` after-table clean; vi/id present.
- T15 claim page: strip absent for a plain waiting claim, present with a workflow step or user-made stage.
- T16 candidate no email: recruiter task created once, link sent when the email is added, helper task closes, fallbacks.
- T17 no banned words in any new/changed string or template.
- Existing suites of every touched area and the approval suites (175, same 4 known failures) before/after.

Browser (local): U1 approver's bell/inbox shows one notice for a pay change with a live route (before/after screenshots); U2 the three expense emails rendered (en + vi) and the claim page; U3 joining checklist for a Hiring joiner; U4 status words on the four screens; U5 employee claim page with and without a strip; U6 recruiter task for a candidate without email → add email → link page; U7 dock sentence; U8 Studio "already happens" for Expense and Time off reads true.

## 6. Deploy and verify

As P4b (`WF2_P4B_REPORT.md` §4): notes file START/DONE "Claude WORKFLOW-2", flock, clean staging, service stopped, scoped per-module rsync with before-tarballs, `-u` only modules whose data changed (templates, labels) — list each with its reverse dependents first — on payobook, payobook_template, p0clone, rize, suites on p0clone, sudima last; job id lists identical; asset purge ×5; restart; warm; hashes + `latest_version` ×5 for every touched module; 0 ERROR lines; mail queue (`mail.mail` outgoing count) identical before/after on every database. Live look read-only (the main loop does the signed-in look if your session is signed out).

Commit per feature (engine helper / each area or a small group of areas / expense messages / joiners / words / Studio items / docs), explicit paths. Do not push.

## 7. Report back (`WF2_P2B_REPORT.md`)

The census table (§4.1) in plain words suitable for the owner; per-area before/after table (who is told what, by whom); rollback (kill switch + guards); commits, versions; tests; deploy evidence; areas you chose **not** to guard and why; deviations; R1 audit (every changed word and every message that no longer arrives, per site); Overlaps found (R2a); gotchas G55+; what P5 needs (new strings to translate, anything left for consolidation); owner decisions needed.
