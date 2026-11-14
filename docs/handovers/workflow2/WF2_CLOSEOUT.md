# WORKFLOW-2 — programme closeout

11–12 November 2026. Designer: Claude (Fable). Builders: Opus implementation agents, one per phase, same session. Rulings, decisions and gotchas: `WF2_LEDGER.md`. Every phase has a handover and a report in this folder (index in §7).

## 0. In plain words (for the owner)

**What the programme delivered.** Workflow Studio was a separate drawing tool that ran its own tasks next to everything else. It is now one central place that works *with* the rest of Payobook instead of beside it:

| Phase | What changed, in screen words |
|---|---|
| P1 | Workflows run on their own, like the system's other automations — no special "workflow user". An approval step waits for the area's own approval instead of forcing it. |
| P2 | Expenses, Time off and Hiring tell the Studio what they already do on their own. The Studio lists that under **Already happens** and warns before you add a step that would do it a second time. You can add **your own stages** ("counts as Approved") without programming. |
| P3a | **By stage** view, one **Stages** screen, "Gets here when…" on every view, the record's progress strip, drag by touch. |
| P3b | Task buttons ("Looks fine" / "Paper receipt missing"), eight new step kinds (move to a stage, send back, update the record, make a letter or announcement, tell someone in the app, ask someone to confirm, start another workflow, stop), the manager's manager, Hiring "Add a stage". |
| P4a | **Workflow tasks are in the Approvals inbox** (one list). Late tasks are chased by the same reminders, pass-ups and backups as approvals. Teams. Employees on the employee home and people with **no login (an email link)** can take part. |
| P4b | Progress shows on the record's own screen and on the employee home; "Move to…"; **Where time goes**; "The candidate" as a participant; who is told when a late task's person has no manager; the dock's task line. |
| P2b | Approvers are told **once** (by Approvals) and employees are told by their area — no more double messages. Kill switch: system setting `biz_approval.single_notice` (0 = old behaviour). |
| P5a | **Start on a schedule**; pay managers not involved no longer get a to-do per step; each area emails the employee when a request is **sent back**. |
| P5c | **Repeat for each line** (each receipt, each list answer, each team member — "receipt 2 of 3", "Do all in turn"); "Around a date"; contracts, trial periods and documents declare their own reminders; the look-only right **See everyone's approvals** (given to Debalina on rize, D32). |
| P5b | **Vietnamese and Indonesian** for everything people see outside the Studio editor (task pages, employee home, link pages and the link email, record strip, Approvals tasks, reminders, sent-back emails, status words) and for the Studio's server messages. Reminders and the link email go out in the reader's language. |

**Try first:** (1) Approvals inbox → the **Tasks** group (a workflow with "Repeat for each…" on an expense claim shows one card per receipt and "Do all in turn"). (2) Sign in as an employee with Vietnamese or Indonesian as their language → **My tasks** on the employee home. (3) Workflow Studio → More possibilities → **Repeat for each…**, and Start → **On a schedule** (read only; do not switch anything on).

## 1. What is live (12 Nov 2026, all five sites: payobook, payobook_template, p0clone, rize, sudima; never abm)

| Module | Version | Last changed in |
|---|---|---|
| `pb_lifecycle` (Workflow Studio) | **19.0.1.19.0** | P5b |
| `pb_timeoff` | 19.0.1.10.0 | P5a code, P5b translations |
| `pb_me_expense` | 19.0.1.2.0 | P5c code, P5b translations |
| `pb_hiring` | 19.0.2.23.6 | P4b code, P5b translations |
| `pb_payruns` | 19.0.3.5.0 | P3b contract, P5b translations |
| `pb_contract_lifecycle` / `pb_probation` / `pb_employee_vault` | 19.0.1.3.2 / 19.0.1.5.0 / 19.0.1.5.0 | P5c timetables, P5b translations |
| `pb_goals` / `pb_offboarding` | 19.0.1.4.0 / 19.0.1.5.0 | P5a emails, P5b language |
| `pb_me_portal` / `pb_mission` | 19.0.3.5.3 / 19.0.1.13.1 | P2b/P4b words, P5b translations |
| `biz_approval_workflow` | 19.0.1.7.1 | P2b (`single_notice.py`); P5b only translation files |
| `pb_approval_config` | owned by the UPDATES session (19.0.1.8.0) | not touched by WORKFLOW-2 code after P4a (deviation P5c-1) |

Tests: Studio suite **152** (local 152/152; on p0clone at deploy, see `WF2_P5B_REPORT.md` §4); area message suites 55/55 local; area reminder suites 26/26 (P5c); approval suites 198 with the same 4 pre-existing failures (§5).

Switches and jobs:
- Undo for "told once" (P2b): system setting **`biz_approval.single_notice`** — `0` brings back every area's own approver message.
- **Sudima's Workflow Studio job is off** by owner choice (D11) — Studio does nothing on sudima until it is switched on.
- **Approvals' message job is off on payobook and payobook_template** (owner's demo-mail ruling, D33/G56) — queued Approvals notices there are never delivered.
- No outgoing mail on rize, sudima, p0clone — **on purpose (D29)**; people there see in-app notices and to-dos only.
- Access change on rize, 12 Nov 11:24 UTC: role **"See everyone's approvals"** (`pb.role.profile` 462, the one look-only ability) given to **debalina@rize.farm** (D32). Undo: remove the role from her on the Access screen.

## 2. Owner decisions (D1–D34)

| # | Decision | Where it lives |
|---|---|---|
| D1 | Workflow tasks go into the Approvals inbox; "My tasks" retired as a separate list | `pb_lifecycle/models/workflow_inbox.py`, `static/src/{js,xml}/workflow_inbox*` (P4a) |
| D2 | Late work uses Approvals' reminder → pass-up → backup | `workflow_people.py` `_chase_late` via `biz.approval.engine._escalate_extra` (P4a) |
| D3 | Hiring keeps its own automations; Studio shows them as "already happens" | `pb_hiring/models/workflow_contract.py` (P2) |
| D4 | Studio's form builder is the general one | `workflow_definition.py` forms (P1–P4a) |
| D5 | Approvers told once when a route is live | `biz_approval_workflow/models/single_notice.py` + each area (P2b) |
| D6 | Requester told by the area, gaps filled (expense approved/refused/paid) | `pb_me_expense/models/expense_messages.py` and areas (P2b) |
| D7 | New-joiner preparation split by date; buddy carried over | `pb_hiring/models/joining_p6.py` (P2b) |
| D8 | Reuse announcements, letters, one-step sign-offs, checklist steps | `workflow_steps.py` creators (P3b) |
| D9 | sudima joins the deploy set; two old copies never touched (since deleted by owner) | deploy scripts |
| D10 | Candidate stages are added through Hiring | `pb_hiring/models/stage_add.py` (P3b) |
| D11 | Sudima worker job stays off | every deploy script |
| D12 | Each area keeps its own status words in Studio | `workflow_contract.py` per area |
| D13 | Stage target time feeds Approvals' reminders and "Where time goes" | `workflow_people.py` `_chase_late_stages`, `workflow_time.py` (P4a/P4b) |
| D14 | A workflow may add a Hiring tag (not stars) | `pb_hiring` tag door (P4a) |
| D15 | Keep both: one-person in-app notice and announcement | `workflow_steps.py` (P3b) |
| D16 | Studio's "Ask someone to confirm" is the general one, with a no-login link | `workflow_people.py`, `controllers/token_pages.py` (P4a) |
| D17 | Hiring set-up gets "Add a stage" / "Remove" | `pb_hiring/models/stage_add.py`, `static/src/*/hiring_setup.*` (P4a) |
| D18 | "The candidate" as a participant, by email link | `pb_hiring` + `workflow_reach.py` (P4b) |
| D19 | A named Approvals role per workflow when a late task has no manager | `workflow_reach.py` `_pass_up_people` (P4b) |
| D20 | Dock: one line with the task count | `pb_mission/static/src/xml/pb_dock.xml` (P4b) |
| D21 | Checklist links stay until checklists move; workflow notices in their own card | `workflow_home.py` (P4b) |
| D22 | Four status wordings | `pb_me_expense`, `pb_timeoff` (incl. `views/hr_leave_kanban_words.xml`), `pb_me_portal` (P2b/P5a) |
| D23 | Claim page strip only when it adds something | `workflow_strip.py` `_wf_page_strip` (P2b) |
| D24 | Candidate with no email → recruiter gets a task | `workflow_reach.py` (P4b/P5a) |
| D25 | Task owner without "view progress" still sees the stage track | `workflow_strip.py` (P4b) |
| D26 | Other pay managers stop getting the per-step to-do | `pb_pay/models/pay_single_notice.py` (P5a) |
| D27 | Contract extension overdue email to HR kept | `pb_contract_lifecycle` (unchanged) |
| D28 | Each area emails "sent back" | `pb_me_expense`, `pb_timeoff`, `pb_goals`, `pb_offboarding` templates (P5a) |
| D29 | No outgoing mail on rize/sudima/p0clone — on purpose | (nothing to change) |
| D30 | "Around a date" shortcut to "At a record date" | `static/workflow/schedule.js` (P5c) |
| D31 | Contracts, trial periods, documents declare their reminders | `*/models/workflow_timetable.py` (P5c) |
| D32 | Debalina sees Everyone through a new narrow right | `pb_lifecycle/security/approvals_see_everyone.xml`, `workflow_inbox.py` `_can_org` (P5c); granted on rize 12 Nov |
| D33 | Approvals message job stays off on payobook/template; time off "sent back" stays a refusal underneath; repeat as its own phase | ledger |
| D34 | 25 lines per click; narrow right also widens "All I can see"; editor translation out of P5b | ledger |

## 3. Open items (each with a sized recommendation)

1. **Studio editor screen text is English only.** The workbench (`pb_lifecycle/static/workflow/*.js`, an iframe app of classic scripts) never had a translation mechanism; about **466** distinct phrases (largest: `app.js`, `steps.js`, `people.js`, `stages.js`; `repeat.js` ~29, `schedule.js` ~22). Recommendation: one phase, ~2 days: a tiny `t()` in the workbench reading a JSON dictionary served by a controller from the module's `.po` (`code_translations.get_web_translations('pb_lifecycle', lang)` — entries marked `odoo-javascript` with occurrences on the workbench files); wrap the phrases file by file; English byte-identical by the same golden-file method as P5b p1. Until then a Vietnamese/Indonesian designer sees English editor chrome with translated server messages inside it (e.g. the schedule sentence on Try it out).
2. **[P6a: done in part]** Time off days and business trip costs are live; pay run payslips not built (a pay run cannot carry a workflow, G84); asset handovers and joiner equipment have no lines. Was: **Repeat for more areas** (each through the area's own door, like `pb_me_expense/models/workflow_lines.py`): pay run → payslips first (most useful, safe, capped), then time off → days of a long leave, business trips → legs, asset handover → items, joiner → equipment lines. ~½ day per area incl. tests.
3. **[P6a: done]** Live on all five. Was: **Trips and equipment "sent back" emails** (D28 covered expenses, time off, goal changes, resignations). ~½ day each, same shape as `pb_timeoff` `_pb_tell_sent_back`.
4. **[P6a: done]** Training due dates declared; time off balance already listed (no record date); pay review and asset returns have no reminder. Was: **Remaining areas' reminder timetables** (D31 did contracts, trial periods, documents): time off balance reminders, pay review cycle, learning due dates, asset returns. ~2 h each.
5. **[P6a: done]** Columns and rule mentions gone (five dumps first). Was: **Drop `execution_user_id`** (left since P1): remove the record-rule terms first (G7), then the columns, one migration. ~2 h + a normal-tier deploy.
6. **[P6a: not built — owner decision, `WF2_P6A_REPORT.md` §7]** Was: **Time off "sent back" is a refusal underneath** (D33): the employee sees "sent back", the record is refused/reset. A true "returned" state would touch Time off's status field. Decide only if users find it confusing.
7. **[P6a: done]** A line is read again when its step opens; removed lines close cleanly. Was: **Line details are read once at start** (P5c): a receipt edited after the repeat started keeps its old amount on the line. Option: re-read on each line step (small), or a "Refresh lines" action.
8. **Lines start 25 per click** (D34): the rest within a minute by the worker. Fine at today's sizes.
9. **Never tested on a real phone or touchscreen** (G23): only synthetic touch events. One manual session on an iPhone/Android: the inbox, task page, employee home, Studio drag.
10. **No outgoing mail on rize, sudima, p0clone** — by owner choice (D29). Stated only.
11. **[done 14 Nov by the main loop]** Was: **~18 leftover filestore folders** of long-gone test sites in `/odoo/.local/share/Odoo/filestore` — owner not asked to delete.
12. **[P6a: done]** Hiring stages (id), Other request statuses, route sentence (plain words, translated), claim pages (id); stored history stays as written. Was: **P5b leftovers (translations)**, details in `WF2_P5B_REPORT.md` §8: activity history lines written before a person's language existed stay as written (they are stored text); Hiring's own stage names/descriptions, "Other request" status labels (`biz_approval_workflow` selection) and Approvals' route sentences ("…only when validation_type is one of manager, both" — also an R8 wording gap in `biz_approval_workflow`) are not WORKFLOW-2 strings and stay English in Studio's "Already happens"; Indonesian for the rest of the employee claim page (pre-existing `pb_me_expense` id gap).
13. **The link page opens in the reader's language only when the site offers it** (`/vi/…`, `/id/…` added to the link when the language is one of the website's languages). All five live sites offer English, Vietnamese and Indonesian today (checked 12 Nov). A site that later drops a language shows that page in its default language. Stated only.

## 4. Known failing baseline tests (not caused by this programme)

Checked at `23c689fab` (before P2b) and again in P5c; identical before and after every phase.

| Module | Tests | Why |
|---|---|---|
| `pb_me_portal` | 8: `TestMeHomeCards`, `TestMeHomeSource`, `TestPbMePortal`, `TestPortalOnlyDoors` | employee-home fixtures predate the current cards |
| `pb_pay` | 2: `test_t4c` (vi catalogue), `test_t11` (`pb_pay.pot` "says the wrong name") | translation catalogue tests |
| `pb_timeoff` | 6: `TestLeaveRules` | field access on `pb_policy_exception_by` |
| `pb_hiring` | 14 | listed in the P2b run logs (`/Users/adity/odoo19/wf2p2b_hire.log`) |
| approvals (`pb_approval_config` / `biz_approval_workflow`) | 4: `test_the_look_invents_no_colour_and_carries_no_gradient`, `test_u13_the_catalogue_covers_the_whole_exported_template`, `test_z06d_every_p7_block_is_filled_in`, `test_z06e_no_p7_translation_loses_a_placeholder` | look and Vietnamese-catalogue tests |

## 5. Gotcha ledger

`WF2_LEDGER.md` §4, **G1–G83**. The ones to know before touching Studio again: G1 (system env, not sudo), G7 (rules before dropping `execution_user_id`), G11/G17 (two workbench cache keys), G12/G59 (`_()` and locals named `user`), G29 (upgrade cascades), G55 (pre-commit hooks run inside savepoints), G62 (never "odoo-bin" in the launching command), G73 (workbench scripts share one scope), G80 (abilities in data files must be noupdate).

## 6. How to roll back the last phase (P5b)

Trees before P5b: `/odoo/backups/wf2-p5b-20261112T121525Z/<module>-before.tgz` (13 modules). Stop the service, extract each over `/odoo/odoo-server/addons/<module>` (scoped, never `--delete` on the addons root), `-u pb_lifecycle,pb_timeoff,pb_me_expense` on the five databases, start. The stored Vietnamese/Indonesian values (views, templates) stay in the database and are harmless with the older code. The code changes (reader's language for reminders and the link email, goal/resignation sent-back language) go with the trees.

## 7. Where everything is

| Phase | Handover | Report |
|---|---|---|
| P0 | (prompt) | `EXISTING_BEHAVIOUR_INVENTORY.md` |
| P1 | `WF2_P1_HANDOVER.md` | `WF2_P1_REPORT.md` |
| P2 | `WF2_P2_HANDOVER.md` | `WF2_P2_REPORT.md` |
| P2b | `WF2_P2B_HANDOVER.md` | `WF2_P2B_REPORT.md` |
| P3a | `WF2_P3A_HANDOVER.md` | `WF2_P3A_REPORT.md` |
| P3b | `WF2_P3B_HANDOVER.md` | `WF2_P3B_REPORT.md` |
| P4a | `WF2_P4A_HANDOVER.md` | `WF2_P4A_REPORT.md` |
| P4b | `WF2_P4B_HANDOVER.md` | `WF2_P4B_REPORT.md` |
| P5a | `WF2_P5A_HANDOVER.md` | `WF2_P5A_REPORT.md` |
| P5c | `WF2_P5C_HANDOVER.md` | `WF2_P5C_REPORT.md` |
| P5b | `WF2_P5B_HANDOVER.md` | `WF2_P5B_REPORT.md` (+ `p5b_screens/`) |

Design source: `docs/design/workflow-studio/review/` (second-opinion review and prototype). Tools: `tools/workflow_studio/` (suite runners, fixtures, browser scripts, `p5b_language_proof.py`).
