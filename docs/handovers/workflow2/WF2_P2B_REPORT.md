# WORKFLOW-2 · Phase 2b report — one message per event, one owner per message

Builder: Claude (Opus implementation agent), 11 November 2026. Handover: `WF2_P2B_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (gotchas G55–G64 added, P2b row closed).

## 0. In plain words (for the owner)

- **What changes for people.** When an approval route is live, the person who has to approve hears it **once** — from Approvals ("Your approval is needed" + a to-do) — instead of also getting the area's own to-do or email. Everybody else the area used to tell (for example the rest of the pay managers, or the HR team on a resignation) still gets the area's message. Employees now get **three new emails about expense claims**: approved, refused (with the reason) and paid (with the amount and the date). Time off reads **"Waiting for approval"** and **"Second approval"** everywhere.
- **What it means today, per site.** Almost nothing stops arriving, because almost none of these requests happen on the live sites (census below). On **payobook** and **payobook_template** nothing changes at all: Approvals' own messages are switched off there, so the old messages are the only ones and they keep going. On **rize** at most one or two to-dos a month would stop being doubled.
- **How to switch it all back.** One setting, no deploy: System parameter `biz_approval.single_notice` = `0`. Every area then sends exactly what it sent before this phase. The expense emails and the wording changes are not behind that switch (they are new, not duplicates); see §3.

## 1. Census before any code (read-only, 11 Nov 08:05–08:20 UTC)

Queries: `scratchpad/census/census.sql`, `census2.sql` (copies on the server `/tmp/wf2p2b_census*.sql`). Nothing was written.

### 1.1 Is an approval route live, and does Approvals actually deliver?

| Site | Companies with a live route for all 11 areas in scope (pay change, pay review, overtime, extension, org plan, resignation, goals, goal change, time off, probation verdict, expense) | Approvals' message job ("tell the people who are waiting") | What that means |
|---|---|---|---|
| payobook | 4 of 4 | **OFF** since 2 Oct (31 notices queued, never sent) | Approvals tells nobody → **nothing is skipped here** |
| payobook_template | 1 of 1 | **OFF** since 15 Oct | same → nothing skipped |
| p0clone | 1 of 1 | on | guards apply |
| rize | 1 of 1 (Rize Farms) | on | guards apply |
| sudima | 1 of 1 | on | guards apply |

Other facts that shaped the design:
- Outbox failures: **0** on every site. No approver seat is held by an employee-home login or an archived login on rize or sudima (p0clone: 3 old expense seats on archived logins — the engine already stops those as "nobody to decide").
- **Email does not leave rize, sudima or p0clone** ("Connection refused"; rize has 830 failed emails, newest today). People there only see in-app to-dos and notifications. Approvals' "your turn" always also puts a to-do on the request, so an approver sees it in the app either way. (Not changed by this phase — reported for the owner, G57.)
- rize: no employee-home logins at all; all 7 staff logins are set to "by email" notifications.

### 1.2 How many duplicate messages happen (last 30 days, and all time)

| Area | payobook | template | p0clone | rize | sudima |
|---|---|---|---|---|---|
| Pay changes / pay reviews | 0 (1 review ever) | 0 | 0 | 0 | 0 |
| Overtime | 0 (24 ever, last Aug) | 0 | 0 | 0 | 0 |
| Contract extensions | 0 (4 ever) | 0 | 0 | 0 (1 ever, Sep) | 0 |
| Org chart plans | 3 (tests 4–5 Nov) | 0 | 0 | 1 (a test, 4 Nov; 1 doubled to-do) | 0 |
| Resignations | 0 (7 ever) | 0 | 0 | 0 | 0 |
| Goal sheets / changes | 0 (18 / 4 ever) | 0 | 0 | 0 | 0 |
| Time off | 0 in 30 days (51 ever) | 0 | 2 | 1 (4 Nov — it never reached Approvals, see G61) | 0 |
| Expense claims | 1 waiting | 0 | 2 waiting | 0 | 0 |

**Rough monthly effect:** rize — 0 to 2 doubled to-dos a month stop (time off, org chart plans) once those requests are used; sudima and the template — 0; payobook — 0 (nothing skipped there, see 1.1); p0clone — the 2 test leaves a month. No area was found where guarding could leave an approver with nothing (the guard only skips a person after it finds Approvals' own "your turn" to that person on the waiting step, and switches itself off where Approvals' job is off).

## 2. What is live — before / after per area

"Route live" = an approval route is bound for the company AND Approvals' message job is on AND `biz_approval.single_notice` is not 0. Without that, every row is exactly as before.

### 2.1 Approvers (D5)

| Area | Who was told before (route live) | After (route live) | History line on the record |
|---|---|---|---|
| Pay change | Approvals "your turn" + to-do "A pay change is waiting for you" to up to 10 people of the rung's group | Approvals to the people the route asks; **the rest of the group still gets the to-do** | unchanged |
| Pay review | same pattern ("A pay review is waiting for you") | same | unchanged |
| Overtime | Approvals + to-do "Overtime Request to Approve" to the line manager | Approvals only, when the route asks the line manager; otherwise the to-do as before | unchanged |
| Contract extension — ask | Approvals + email "extension ask" + to-do to the manager | Approvals only for the people it asks; "Asked. … has until …" stays | unchanged |
| Contract extension — overdue | Approvals reminder/pass-up + the area's one overdue email to HR **and** the manager | the manager is left out of the overdue email (Approvals' reminder is their one chaser); **HR still gets it** | unchanged |
| Org chart plan | Approvals + a to-do per seat (exactly the same people) | Approvals only | "Sent to the HR team for approval." stays |
| Resignation — handed in | Approvals (to the manager first) + email "has handed in their resignation" to the manager and every lifecycle manager | the manager is left out of the email; **the HR team still gets it** | unchanged |
| Goals — sheet sent in | Approvals + courtesy email to the manager (behind its own switch) | Approvals only when the route asks the manager | unchanged |
| Time off | Approvals + the standard "time off to approve" to-do to the leave manager | Approvals only for the people it asks; second approval unchanged (it is created and closed inside the final approval) | unchanged |
| Probation review | to-do "Review probation recommendation" to the HR/CEO reviewer | **not guarded** — see §5 | — |

### 2.2 Requesters (D6) — result × who sends

| Area | Approved | Turned down | Sent back |
|---|---|---|---|
| Time off | before: time off ("has been accepted") + Approvals · **after: time off only** | before: both · **after: time off only** ("has been refused") | Approvals (time off has no sent-back message) — unchanged |
| Goal sheet | before: goals ("locked" email) + Approvals · **after: goals only** | Approvals only (goals sends nothing on a route) — unchanged | Approvals only (on a route the sheet goes back to draft without its email) — unchanged |
| Goal change | before: both · **after: goals only** ("agreed") | before: both · **after: goals only** | Approvals — unchanged |
| Resignation | before: offboarding ("approved" email) + Approvals · **after: offboarding only** | Approvals only (offboarding emails only from its own Refuse button) — unchanged | Approvals — unchanged |
| Expense claim | before: Approvals only, and never to an employee-home login · **after: Expenses email** | before: Approvals only (never to an employee-home login) · **after: Expenses email with the reason** | Approvals — unchanged |
| Expense claim — paid | before: nobody · **after: Expenses email with amount and date** | | |

The engine leaves its copy out only when (a) the area declares that result, (b) the person who sent it in is the person it is about (an HR officer sending in for someone still hears from Approvals), and (c) the area really has somewhere to send it (an email address; offboarding emails switched on). Every requester message reaches an employee-home login: time off posts to the employee's login (email for employee-home logins), goals/offboarding/expenses email the employee's work address.

### 2.3 The three expense emails

Subjects: "Your expense claim was approved / was refused / was paid" (vi: "Đề nghị hoàn chi phí của bạn đã được duyệt / đã bị từ chối / đã được thanh toán"; id: "Klaim pengeluaran Anda telah disetujui / ditolak / telah dibayar"). One indigo button "Open your claim" to `/my/expenses/<id>`. Sent in the employee's language, from the company address (never the approver's). Once per decision (a stamp per result); "Fix and resend" clears the stamps so a new decision is told. Nothing is sent for claims that did not move after the deploy. Previews (en + vi) were rendered and looked at.

### 2.4 Words, strip, candidate, dock, joiners

- **D22 status words** — time off "To Approve" → **Waiting for approval** and "Second Approval" → **Second approval** on the form, lists, filters, exports and Studio; the time-off board "To approve"/"2nd approval" → the same words; My requests (employee home) "Waiting approval" → **Waiting for approval** for time off; the employee claim page "Refused — see why" → **Refused — your turn**. Expense "Approved — being paid" was already right. vi and id labels shipped (time off form vi "Đang chờ duyệt" / "Duyệt cấp 2", id "Menunggu persetujuan" / "Persetujuan kedua").
- **D23** — the employee claim page (every page in `HOME_PAGES`) shows the strip only when a workflow step for a person or a stage the company made is involved; otherwise just the page's own "With X" box. Staff screens unchanged.
- **D24** — a step for "The candidate" with no email no longer stops: it waits, and the recruiter (Hiring's own: the role's recruiter, else the candidate's) gets **"Add an email for Mai Pham"** in the Approvals inbox Tasks group and on their to-do list; it opens the candidate. Cover applies; no recruiter → the workflow's late-task role (a team gets it as a team task) → the publisher. The candidate's own strip says "Waiting for you: add an email for …" with no "Do it now". When the address is on the record, the worker (every minute) sends the link once and the helper task disappears. The task cannot be "answered" on the candidate's behalf.
- **D25** — the dock: when the workflow task line shows, the empty list under it says **"No approvals are waiting on you."** (and no "All clear").
- **D7** — see §5: most of it was already true; one addition (the buddy step says "Chosen in Hiring by … on …").

## 3. Rollback

| What | How | Deploy needed? |
|---|---|---|
| All approver and requester guards (D5, D6 engine side) | System parameter `biz_approval.single_notice` = `0` | no — read on every call |
| A single area | remove its guard (each is a wrapper around the original send; the original lines are unchanged) | yes |
| Expense emails | switch each template off (Settings › Email templates) or revert commit `8c7bf3feb` | no / yes |
| Status words | revert `bfa065fc1` (time off) + upgrade `pb_timeoff`; the old vi/id labels come back from the stock time-off translations only after a translation reload | yes |
| D23 / D24 / D25 | revert `2a1db5694`, `1161bba04` | yes |
| Whole phase | module trees before this deploy: `/odoo/backups/wf2-p2b-20261111T091625Z/*-before.tgz` | yes |

## 4. Commits, versions

| Commit | What |
|---|---|
| `87f45a0d2` | Approvals: `tells_approver` / `notify_unless_told` / `single_notice_flush`, requester declarations, kill switch, T1 + T11 engine tests, `tools/workflow_studio/run_p2b.py` |
| `100648828` | Guards: pay change, pay review, overtime, contract extension (ask + overdue), org chart plan, resignation (handed in); goals manager email; goals / goal change / resignation requester declarations; area tests |
| `bfa065fc1` | Time off: guard on the standard to-do, requester declaration, status words, vi/id, tests |
| `8c7bf3feb` | Expenses: three emails, stamps, Studio "already happens" rows, claim page word, vi/id, tests |
| `2a1db5694` | Studio: D23 strip rule, D24 candidate without email, D25 dock, My requests word, "already happens" follows the declarations, old time-off labels read in history, Studio tests |
| `213ca2f96` | Hiring: buddy step "Chosen in Hiring by … on …" (D7) + test |
| `1161bba04` | Studio: the record strip says an email is needed, no "Do it now" (found in the browser run) |
| `ba1edbe10` | Pay tests: the preparer is an HR officer too (found on p0clone) |
| (docs) | this report, ledger |

Not pushed. Versions: `pb_lifecycle` **19.0.1.16.0**, `pb_timeoff` **19.0.1.9.0**, `pb_me_expense` **19.0.1.1.0**. Unchanged (method / static / translation files only, G29): `biz_approval_workflow` 19.0.1.7.1, `pb_approval_config`, `pb_pay`, `pb_hr_workforce`, `pb_contract_lifecycle`, `pb_orgchart`, `pb_offboarding`, `pb_goals`, `pb_me_portal`, `pb_mission`, `pb_hiring`. Reverse dependents checked before the bumps: `pb_timeoff` → `pb_ess_workforce`, `pb_mission`; `pb_me_expense` → `pb_expenses_hub`; `pb_lifecycle` → its 14 known dependents (as every WF2 phase).

## 5. Areas not guarded, and D7

- **Probation review (not guarded, by design).** The to-do "Review probation recommendation" belongs to probation's own HR-lead → CEO gate, which by its own code bypasses Approvals. Approvals never tells that reviewer, so the to-do is their only message. Guarding it would have changed nothing at best and silenced the reviewer at worst. The verdict proposal path (non-probation kinds) sends no to-do of its own.
- **Requester "sent back"** stays Approvals' everywhere — no area has its own sent-back message (time off's is a "refused" message, which would be misleading). Approvals does not write to employee-home logins, so an employee whose expense claim is sent back is told only by the claim page (unchanged; listed under weak points).
- **D7 joiners — what was already true, what was added.** The joining checklist opens only when Hiring's "Confirm they joined" is pressed (on/after the start date), and Hiring's existing hand-over already ticks the checklist's "Choose their buddy" step with the buddy the manager named (never a second ask) and writes the laptop answers into the laptop step and into the equipment request the checklist raises on opening. The checklist template has no meet-the-team step, and none of Hiring's "Before they join" items is dated on or after the start date. **Added:** the buddy step now says "Chosen in Hiring by {who} on {date}" (new checklists only; never a running one). **Not done:** a "Continues in the joining checklist" link on Hiring's list (no item qualifies today), and Studio contracts for joining checklists (none exist yet; R6 moves checklists into Studio later).

## 6. Tests

### Backend
| Suite | Result |
|---|---|
| This phase's suite (`run_p2b.py`, local `am_wf2p2b`): T1 (10), T2 pay change/review (4), T3 overtime (4), T4 extension incl. overdue (4), T5 org plan (3), T6 resignation (3) + T11, T7 goals (4) + T11 (3), T8 time off (5) + T10 + T11 (3) + T14, T12 expense (8) + T14, T13 joiners (1) | **55 / 55** |
| Studio suite (`run_suite.py`): 122 + T12 Studio warning, T15 strip rule, T16 candidate without email, T17 banned words (P4b T4, T8, P2 T5 updated for the owner's decisions) | **126 / 126** |
| Approval suites (`-u biz_approval_workflow,pb_approval_config`) | 185 (175 + 10 new), **the same 4 known failures** as P4a/P4b (`pb_approval_config` look/translation tests) |
| Area suites `pb_timeoff, pb_me_expense, pb_goals, pb_pay, pb_hr_workforce, pb_orgchart, pb_me_portal, pb_mission, pb_contract_lifecycle, pb_offboarding, pb_expenses_hub` | 728 tests, 16 failing — **byte-identical list on the code before this phase** (pb_me_portal 8, pb_pay 2, pb_timeoff `TestLeaveRules` 6; G60) |
| `pb_hiring` | 528 tests, 14 failing — **identical on the code before this phase** |
| Live, p0clone (deploy) | Studio **126/126**, this phase **55/55** |

T1 kill switch both ways: switch 0 → every guard sends to everyone (T1d/T1e, T2c, T3c, T4c, T5b, T6c, T7c, T8c, T11c, T12b); switch back on → skipped again. Approvals' job off → nothing skipped (T1d, T5c, T8d).

### Browser (local `am_wf2p2b_ui`, screenshots looked at)
| # | Result |
|---|---|
| U1 | pass (in place of a bell screenshot): the routed time-off request in the inbox is "Waiting for P2b UI Recruiter"; the leave has no standard to-do for that person (suite T8a proves the counts) |
| U2 | pass — the refused (en) and paid (vi) emails rendered: reference, title, greeting, sentence, reason box in the brand colour, one button; vi fully translated |
| U3 | not run in a browser (T13 backend: buddy step done with "Chosen in Hiring by DEMO P2b Boss on …", laptop answers in the one equipment request) |
| U4 | pass — time-off form: status bar "Waiting for approval", header pill "WAITING FOR APPROVAL" |
| U5 | not run in a browser (T15 backend: strip present with a person's step, absent once only the end/approval is left, present again with a company stage; staff strip unchanged) |
| U6 | pass — Approvals › Tasks: "Add an email for Mai Pham · Add an email · Candidate confirms details"; clicking opens the candidate form; its strip said "Waiting for you: Confirm your details · Do it now" — **fixed** (`1161bba04`) to "Waiting for you: add an email for Mai Pham", no button; email typed and saved → worker pass → link sent once, helper to-do gone |
| U7 | not run in a browser (template-only change, reviewed) |
| U8 | pass by backend (P2 T5 updated: Expense "already happens" lists the three emails; the route no longer lists its own approved / refused copy for expenses; time-off to-do text says "unless the approval route already asks them") |

Console: no errors on the pages looked at. Noticed, not mine: a floating button labelled "orbLabel" / "orbHint" on every backend page of the local build, and "Pb Policy Rule"-style raw field labels on the time-off form (another session's work).

## 7. Deploy evidence

One normal-tier deploy (three additive columns on expense claims, three mail templates, two selection labels; nothing rewritten) through the notes file and `flock /tmp/payobook-studio-deploy.lock`. No other START was open. Script: `wf2p2b_deploy.sh` (P4b's, adapted; copy in the evidence folder).

- **Before:** the 13 server module trees hashed identical to the repo at `23c689fab` (the commit before this phase) — nobody else's work overwritten.
- **Attempts that changed nothing.** 09:16 and 09:17 stopped at "service did not stop": the script's own "no odoo-bin left" check matched the ssh command that launched it, and the first attempt's `systemctl start` left a second Odoo running outside systemd for about a minute (it only ran scheduled jobs); it was stopped by its process number (G62). 09:18 upgraded the four databases, then **one of this phase's tests failed on p0clone** (the pay test's preparer could not read an employee's full record there), so the script **restored the previous trees and re-upgraded** the four databases by itself (09:24–09:26, FAILED note written; queue counts identical; sudima never touched). The test was fixed (`ba1edbe10`).
- **The deploy (09:27:21–09:34:28 UTC, 427 s, 413 s down):** clean staging from `git archive ba1edbe10` → service stopped → scoped `rsync -a --delete` of the 13 modules (trees before in `/odoo/backups/wf2-p2b-20261111T092721Z/*-before.tgz`) → `-u pb_lifecycle,pb_timeoff,pb_me_expense` on payobook, payobook_template, p0clone, rize (all exit 0, 0 ERROR/CRITICAL) → suites on p0clone: **Studio 126/126, this phase 55/55** → sudima last (exit 0) → no job newly switched on → probe ×5 → asset signal + purge ×5 → service started → sites 200.
- **Tree hashes** server = repo at `ba1edbe10` for all 13 modules. **`latest_version`** in all five: pb_lifecycle 19.0.1.16.0, pb_timeoff 19.0.1.9.0, pb_me_expense 19.0.1.1.0; biz_approval_workflow 19.0.1.7.1, pb_hiring 19.0.2.23.6, pb_mission 19.0.1.13.1 unchanged.
- **The deploy sent nothing.** Before → after (service stopped): emails queued, Approvals' outbox, to-dos — identical on all five (payobook 3,135 / 158 / 391; template 0 / 0 / 0; p0clone 34 (17 waiting) / 8 / 9; rize 830 / 123 / 88; sudima 18 / 6 / 4). rize messages +4: the upgrade's own change notes on two scheduled jobs whose names the upgrade resets and the brand scrub puts back ("Rize: …"); nobody is notified; it happens on every deploy that upgrades the Studio module's dependents (G64).
- **Active job id lists** identical before/after: 50 / 32 / 39 / 82 / 81. Sudima's Studio job still off.
- **Probe ×5:** switch parameter absent (= on); Approvals' message job on for p0clone, rize, sudima (guards on) and **off for payobook and payobook_template (guards off by themselves)**; the three expense templates present; 0 claims stamped (no backfill); requester declarations loaded (time off approved/turned down, expense approved/turned down, goal sheet approved, goal change approved/turned down, resignation approved); claim page word "Refused — your turn".
- **Time-off labels:** English changed by the upgrade; the stored Vietnamese and Indonesian words kept the old ones ("Cần phê duyệt", "Akan Disetujui"), so the two rows were aligned by one SQL update per database to the shipped words (vi "Đang chờ duyệt" / "Duyệt cấp 2", id "Menunggu persetujuan" / "Persetujuan kedua") with a cache signal; output in `leave-label-translations.txt` (G58).
- **Logs:** 0 ERROR/CRITICAL in the five upgrade logs and in the service log after the start.
- **Right after:** another session (UPDATES P2d) started its own deploy at 09:34 and stopped the service at 09:35 for about two minutes (its own planned downtime; not this phase).
- Evidence: `/tmp/wf2-p2b-20261111T092721Z/` on the server (steps, upgrade logs, suites, probe, queue and job snapshots, versions, hashes, warm, label update).

- **Signed-in live look on payobook.com** (read-only, the browser's existing session, after the other session's deploy finished): Approvals opens with its tabs and counts (My turn 0, All I can see 8, Sent back 2, Finished 74, Late 7), console clean; Time off › All Time Off: the status filter reads **"Waiting for approval"**; the kanban cards' corner ribbon still says **"TO APPROVE"** — that ribbon is a word written into the stock time-off card itself, not the status label (left for P5, see weak points).

Nothing published, activated, created, approved, paid, moved or sent. ABM untouched.

## 8. R1 audit — every changed word and every message that no longer arrives

Changed words: time off "To Approve" → "Waiting for approval", "Second Approval" → "Second approval" (form status bar, list column, filters, group-by, exports, Studio, time-off board and its filter); employee home My requests (time off) "Waiting approval" → "Waiting for approval"; employee claim page "Refused — see why" → "Refused — your turn"; dock empty sentence with tasks "No approvals are waiting on you."; candidate strip "Waiting for you: add an email for …"; time-off "already happens" texts (two). New: three expense emails, the "Add an email for …" task, the buddy step line.

Messages that no longer arrive (only where §2's "route live" holds — today p0clone, rize, sudima; never payobook/template): the doubled approver to-dos/emails in §2.1 for the people Approvals asks; Approvals' own approved/turned-down copy for the results in §2.2 when the area tells the same person.

## 9. Overlaps found (R2a)

1. **Two chasers for the HR team on an overdue contract extension.** The manager now has one (Approvals' reminder), but HR still gets the area's overdue email and may also get Approvals' pass-up if the route escalates to HR. Options: (a) keep (now); (b) leave HR out of the area's overdue email when the route names an escalation role; (c) switch the area's overdue job off for routed requests. Recommend (b).
2. **Resignation "handed in" email to HR vs Approvals' second step.** HR gets the area's "handed in" email at once and Approvals' "your turn" when the manager agrees. They say different things (news vs a task), so kept. Options: keep / drop the email for the HR approver only. Recommend keep.
3. **Pay change/review to-dos to the whole group.** Approvals asks the route's people; the area still tells up to 10 others in the group on every rung (as the handover required). Options: keep / tell only the route's people. Recommend asking the owner — this is the biggest remaining source of noise where pay changes are used.
4. **Sent-back messages to employee-home logins.** Neither Approvals nor any area tells an employee-home login that a request was sent back (expense claims, trips, equipment). Options: an area message per area (like the three expense emails) / teach Approvals to email employee-home logins. Recommend the area message for expenses first.

## 10. Gotchas added (ledger G55–G64)

See `WF2_LEDGER.md`.

## 11. What P5 needs

- New strings to translate: ~25 in `expense_messages.py` (vi + id shipped), 8 in `workflow_reach.py` (D24; English only), 2 in `pb_timeoff/workflow_contract.py` (vi + id shipped), dock line (vi shipped), `pb_hiring` "Chosen in Hiring by …" (English only), template names (vi + id shipped).
- Consolidation: §9 overlaps; status words — the three remaining differences are deliberate (employee vs staff words for expense approved/refused and time-off second approval).

## 11b. What is still weak

- The time-off kanban card ribbon still says "TO APPROVE" (a word in the stock card layout, not the status); the Studio-free fix is a small view change in `pb_timeoff` (P5).
- An employee whose request is **sent back** hears it only on the request page (Approvals never writes to employee-home logins; no area has a sent-back message) — §9 item 4.
- HR may get two chasers on an overdue contract extension (§9 item 1); the rest of a pay group still gets the pay to-do (§9 item 3).
- On rize, sudima and p0clone no email leaves the server at all (G57), so the new expense emails will queue there unseen until outgoing mail works.
- D24's "Add an email" task is checked by the minute job; there is no instant re-check when the email is typed (up to a minute's wait).
- U3, U5, U7 were proven by backend tests, not looked at in a browser.

## 12. Owner decisions needed

1. §9 item 3 — should pay changes and pay reviews stop telling the rest of the group when a route is live?
2. §9 item 1 — HR's overdue email on contract extensions.
3. §9 item 4 — who tells an employee that a request was sent back.
4. Email does not leave rize, sudima and p0clone today (G57) — the new expense emails will queue there and not arrive until outgoing mail works. Not changed by this phase.
