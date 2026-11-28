# WORKFLOW-2 · Phase 3a report — the screens (stages, "already happens", By stage)

Builder: Claude (Opus implementation agent), 11 November 2026. Handover: `WF2_P3A_HANDOVER.md`. Ledger: `WF2_LEDGER.md` (gotchas G17–G27 added, P3a row closed).

## 1. Commits and versions

| Commit | What |
|---|---|
| `3294e7ec1` | Keep candidate stages in Hiring, quiet the no-approval lane, say who may move a record next (backend touches + tests B1–B4) |
| `a0c0ddd16` | Show each workflow stage for what it is, add By stage and one Stages screen, drag by touch (the screens) |
| `85b1d928d` | Let Undo also put a moved stage of yours back where it counted (follow-up found in self-review; static only) |
| (docs commit) | This report and the ledger |

Not pushed. Versions: `pb_lifecycle` **19.0.1.12.0**, `pb_hiring` **19.0.2.23.4**. Workbench cache keys: `wf2-p3a` in `a0c0ddd16`, **`wf2-p3a2`** after `85b1d928d` — both the iframe `v=` (`static/src/js/workflow_studio.js:18`) and every tag in `static/workflow/index.html` (G11).

Files:

- Backend: `pb_hiring/models/workflow_contract.py` (`own_stage_rows`), `pb_lifecycle/models/workflow_contract.py` (contract/metadata carry the flag; fast-lane route returns only the route row), `workflow_stage.py` (`_refuse_own_rows`, `_may_move` shared by `move_record_stage` and the new `_next_move`, `record_stage.next_move`), `workflow_studio.py` (`scope_summary` on `get_workflow` and `save_draft`), tests B1–B4.
- Workbench: new `static/workflow/stages.js` (section descriptor, "already happens", sentence, By stage, Stages sheet, record track, Review group, realign after Undo), new `static/workflow/drag.js` (pointer drag), and edits to `app.js`, `actions.js`, `graph.js`, `conditions.js`, `record-context.js`, `icons.js` (19 Lucide-style icons), `style.css` (one appended block), `index.html`, `static/src/js/workflow_studio.js`.
- Tools: `tools/workflow_studio/chrome_test_p3a.cjs` (new, U2–U8, real mouse via Playwright, local databases only), `chrome_test.cjs` (two lines updated for the changed "You are here" pill and the Stages sheet; not re-run, it needs its own fixture database).

## 2. Tests

### Backend

Local `am_wf2p3` (clone of P2's `am_wf2p2`, `-u pb_lifecycle,pb_hiring`): **80 tests, OK** (76 + 4 new), 0 skips. Server, `p0clone`, service stopped: see §4.

| # | Test | Result |
|---|---|---|
| B1 | `test_wf2p3a_b1_candidates_keep_their_stages_in_hiring` — metadata carries `own_stage_rows` for candidates (not for expense claims); `stage_create` refused with exactly "Candidate stages are managed in Hiring."; nothing stored; a reorder of Hiring's own stages still accepted, one carrying a user-made stage refused; headings on a candidate workflow give no binding error | pass |
| B2 | `test_wf2p3a_b2_no_approval_needed_lane_lists_only_the_route` — with a "No approval needed" route Expenses lists one approvals row (stage `submitted`, change, approver, "No approval needed" in the text), no message/reminder rows; a route with people lists change + message + reminder again | pass |
| B3 | `test_wf2p3a_b3_record_stage_says_who_may_move_it_next` (added: needed by §3.5) — `next_move` allowed for the named person, refused with "Only <name> can move this to <stage>." for another reader, `None` before the anchor stage, on a refused claim and for an automatic stage | pass |
| B4 | `test_wf2p3a_b4_workbench_sentence_reads_the_review_filter_words` (added: the sentence reuses P1's filter words) — `get_workflow` "Every record"; `save_draft` returns `_scope_summary` of the saved filters | pass |

### Browser (local server on `am_wf2p3`, Chrome; console clean of workbench errors throughout — the only 500s were the cloned database's missing website logo/favicon images)

| # | Result | Evidence (one line) |
|---|---|---|
| U1 | pass | Sentence read for every trigger: "When an expense claim is started by a person / is created / has ID or Reference changed / is 3 days before its Sent on / reaches its Sent on / has its approval finished, for everyone"; adding one filter in the Start settings → after save "…, for records where ID is 0"; clicking the sentence or Change opens "When it starts" with focus on its first field. |
| U2 | pass | Create dialog on Expense claim shows "Start with the expense claim's own stages" (checked) with the four stage chips; result: Draft / Waiting approval / Approved / Paid, each "Expenses owns this stage", exits note "If an approver says no, it becomes Refused. Steps after that point do not run."; Review "The workflow is ready to publish" (no binding error). Same through the record set-up page. |
| U3 | pass | Waiting approval shows tag, "Gets here when: the employee sends the claim", the route sentence and "Each approver is told…" in Journey, By stage (2 shown + "1 more thing"), Across ("3 things already happen here", expands in place) and Flowchart (lock icon + "3 already happen" chip → popover). Canvas with a parallel group: every card's `left/top` equals `graphLayout()` and all four labels stay 28 px high (layout unchanged). |
| U4 | pass | By stage: add via a "+" slot and via the column's "Add a step"; drag within a column (inside a parallel path), to another column, into a path; invalid drag of a group into its own path → "A group cannot go inside itself." and nothing changed; Undo/Undo/Redo each restore the exact `[order, stages]`; Journey shows the same order. Real mouse (Playwright `dragTo`) passes the same. |
| U5 | pass | "Payment scheduled" after Approved, a person moves it (Administrator), 3 days → row "Your stage · counts as Approved in Expenses", "Target 3 days", toast "“Payment scheduled” added. It counts as Approved in Expenses."; same tag in Journey, By stage, Across and the canvas icon title. Heading added and renamed by keyboard; your stage renamed through Change ("“Payment booked” is saved."); heading moved; moving Approved up → "Expenses’ stages keep their own order." (no change). Moving your stage past Paid → "will now count as Paid", back → "counts as Approved". |
| U6 | pass | New Expense workflow with Prepare / Do the work / Finish → "Use all of them" → Prepare, Do the work, Finish, Draft, Waiting approval, Approved, Paid; Review has no issue. |
| U7 | pass | "Stop using here" on Approved (1 step) → inline "Move its step first." + "Move it to “Waiting approval”" → moved, then removed (one Undo each). "Delete for everyone" on a stage an active, published local workflow waits on → "“P3a uses Payment booked” waits for this stage. Pause that workflow or change its sections first." |
| U8 | pass | New process: sentence "When someone starts P3a equipment request"; sheet "This is your own process, so every stage is yours."; Ordered and Delivered added ("Your stage"); no "owns this stage" / "counts as" anywhere; the form asks "How does a request get here?". |
| U9 | pass | Candidate workflow: sheet intro + banner "Candidate stages are managed in Hiring." with "Open Hiring set-up"; the add form offers only "Just a heading". The link opened Hiring set-up with "Back to Workflow Studio"; back returned to the same workflow, By stage view, Stages sheet open. |
| U10 | pass | Time off workflow with its own stages, email under Approved → Review "Check these: Time off already does this here: the employee is told their time off is approved…"; Publish disabled; "Keep it, it is different" → "Kept on purpose", "The workflow is ready to publish", Publish enabled; published locally ("Version 1"). |
| U11 | pass | Claim at Approved with a run waiting on "Payment booked": sentence "Waiting for Administrator to move this to Payment booked." (30 px, largest text), track Draft ✓ / Waiting approval ✓ / Approved "Here now" / Payment booked "counts as Approved" / Paid, "Can stop at Refused". Administrator sees "Move to Payment booked" → "Moved to Payment booked.", sentence "Waiting for Administrator: Book it.", "In Payment booked since 11 Nov 2026, 11:57 · moved by Administrator". A second reader (Pat Viewer) sees no button and "Only Administrator can move this to Payment booked.". A refused claim: every stage "Stopped", "Refused · here now" in the warning tone. |
| U12 | pass (synthetic touch) | Touch pointer on the card body does not start a drag (page can scroll; card `touch-action: auto`), on the grip it does (`touch-action: none`), with ghost and slot highlight, in Journey, By stage and on the canvas at 80 % zoom — each landed on the intended section. No real touchscreen was available (G23). |
| U13 | pass | Keyboard only: Tab to the sentence, Enter opens Start settings (focus on its first field); Tab to "By stage", Enter (focus stays on it); Tab to Stages, Enter (sheet, focus on Done); Tab to "Add a stage here", Enter (focus in Name), type, Tab + ArrowDown to "Just a heading", Shift+Tab, Enter saves (focus on the new row's Rename); Escape closes; focus back on Stages. |
| U14 | pass | 390 px: no sideways overflow in any of the five views; By stage columns stack (same left edge); sheet 390 × 844, no overflow; views as a 5-column grid. |
| U15 | pass | Employee (no stages): headings only, sheet says "Employee records have no stages of their own, so this workflow groups its steps under headings.", no "Gets here when" lines anywhere, no stage form dead end. "Other request" (discovered): headings plus its six statuses under "Not used yet"; no empty lines. |
| U16 | pass | Reduced motion: sheet and form animations `none`. No emoji or arrow/check/dot glyphs in new code (byte scan); text + aria-labels + titles of 44 screens scanned for Odoo/OdooBot/bind/core/anchor/gate/model names: 0 hits. |

`chrome_test_p3a.cjs` run against `am_wf2p3`: all of U2–U8 PASS, "no page errors" (twice, including after `85b1d928d`).

## 3. Pre-deploy live numbers (read-only, 11 Nov 01:05 UTC)

| DB | enabled workflows | runs running/waiting | user-made stages | active jobs |
|---|---|---|---|---|
| payobook | 0 | 0 | 0 | 49 |
| payobook_template | 0 | 0 | 0 | 31 |
| p0clone | 0 | 0 | 0 | 38 |
| rize | 0 | 0 | 0 | 81 |
| sudima | 0 | 0 | 0 | 80 |

Server trees of `pb_lifecycle` and `pb_hiring` hashed identical to the repo at `e6e9aae2c` before deploy (4493d01c…, 1c20f062…): nobody else's work overwritten. Notes file: last START (P2) had its DONE; no other START in the last 12 hours.

## 4. Deploy evidence

Two deploys, both through the notes file and `flock /tmp/payobook-studio-deploy.lock` (read-only open, G9), no other START open in the last 12 hours.

**Deploy 1 — `a0c0ddd16` (screens + backend), normal tier.** START `2026-11-11 01:06 UTC`, DONE `01:12 UTC` (323 s, 310 s down). Script: P2's, cut down to two modules and no dumps (`wf2p3a_deploy.sh` in the evidence folder). Clean staging from `git archive` → service stopped (no `odoo-bin` left) → scoped `rsync -a --delete` of `pb_lifecycle` and `pb_hiring` (trees before kept as `/odoo/backups/wf2-p3a-20261111T010618Z/*-before.tgz`) → `-u pb_lifecycle,pb_hiring --no-http --max-cron-threads=0` on payobook, payobook_template, p0clone, rize (all exit 0, no ERROR/CRITICAL) → suite on p0clone **80/80** (`WORKFLOW_TEST_RESULT={"tests": 80, "successful": true, "failures": 0, "errors": 0}`) → sudima last (exit 0) → no job newly switched on anywhere → probe on all five → `orm_signaling_assets` + asset purge on all five → service started.

- Probe (system environment, rolled back), all five databases: Expense claim / Time off / Candidate contracts `declared` (5 / 5 / 17 stages); `own_stage_rows` False / False / **True**; "already happens" rows 10 / 14 / 19 (payobook Hiring 7, as in P2: some Hiring built-ins are off there); 0 rows containing the framework's brand name; `_scope_summary` → "Every record"; backend bundle builds. System account "Payobook" (payobook, payobook_template, p0clone, sudima), "Rize" (rize).
- Tree hashes (skip `__pycache__`, `*.pyc`, `.DS_Store`), server = repo at `a0c0ddd16`: `pb_lifecycle` 6a578a0e…3cc4f3, `pb_hiring` b42fc586…7fb26a.
- `latest_version` in all five: pb_lifecycle **19.0.1.12.0**, pb_hiring **19.0.2.23.4**.
- Active job id lists before → after byte-identical: payobook 49, payobook_template 31, p0clone 38, rize 81, sudima 80. Sudima's "Workflow Studio: progress active runs" (id 89) still **off** (D11).
- Warm: payobook.com, p0clone, rize, sudima login pages 200; workbench `index.html?v=wf2-p3a` 200. No ERROR/CRITICAL line after the restart.
- Evidence: `/tmp/wf2-p3a-20261111T010618Z/` (steps, upgrade logs, suite output, probe, job lists, hashes, versions, warm).

**Deploy 2 — `85b1d928d` (static follow-up), looks-only tier.** START/DONE `01:12`/`01:13 UTC`. `pb_lifecycle` tree synced (no upgrade, no data change), asset signal + purge on all five, `systemctl restart` (~20 s). Tree hash server = repo **7c8ed691…f71345**; `index.html`, `stages.js`, `actions.js`, `drag.js` with `?v=wf2-p3a2` 200 on payobook.com, the served `stages.js` contains `realignStages`, `index.html` carries the new key on all 11 tags; job id lists unchanged (49/31/38/81/80). Three ERROR lines at 01:12:31 on **sudima**: its "Base: Auto-vacuum internal data" job was running when the service restarted ("cursor already closed"); not from this change, the job runs again on its schedule (next 08:39 UTC). A correction NOTE line was added to the notes file because the DONE line had said "no ERROR". Evidence `/tmp/wf2-p3a2-…/`.

**Live check on payobook.com (QA login, read only):** the Studio action loads the workbench with `v=wf2-p3a2`; workflow "Test Expense" shows the sentence, five views, By stage (three heading columns + "Add a stage"), the Stages sheet (headings + "Not used yet": Draft … Refused for the discovered Expense record type) and the canvas; nothing saved (draft not dirty, no Undo history); browser console empty. No workflow published, activated or started, no stage created, nothing moved, no mail.

## 5. Deviations from the handover

1. **Two more small backend additions** beyond §3.8, both read-only: `scope_summary` on `get_workflow`/`save_draft` (so the sentence reuses P1's `_scope_summary` instead of a second describer in the browser) and `record_stage.next_move` (the screen cannot know who "may move it" without the server). The permission check is shared (`_may_move`), so the button and the move never disagree. Tests B3, B4.
2. **"Use all of them" inserts the area's own stages only.** Your unused company stages are offered one by one in the same strip; inserting every company stage of every workflow at once seemed surprising.
3. **"Delete for everyone" on a stage with steps here** turns the section into a heading with the same name (keeping the steps) instead of refusing; the confirmation says so.
4. **"When a rule is true" is offered on record workflows only.** The server checks a stage rule against the record's fields; a new process has none to test, so offering it would be a dead end. "Who may move it" hides "Employee's manager" on a new process (the server refuses it there).
5. **By stage shows at most two "already happens" rows per column** plus "n more things", and hides the long detail line (kept in Journey, Across and Review), so steps stay visible at the top of a column.
6. **Exits are shown once** at the end of Journey, By stage and Across and in the sheet, not on the canvas (keeps the canvas clean).
7. **Progress sentence:** when a run stopped because the record reached an exit it says "Stopped: this is now Refused. Steps after that point do not run." rather than "This workflow was cancelled.".
8. **Undo/Redo re-align the company stage list** when a move had re-anchored a stage of yours (G27, commit `85b1d928d`); the handover did not cover this case.
9. **Removed, as the handover allowed:** `recordStagesDialog` (and its "Wait for this", "Add a module action" shortcuts and old rename) and the Workflow sections modal; every path into them is replaced (Stages button, Review "Open Stages", shared rename in the sheet). The `wait` step's "until a rule matches" is unchanged.
10. **U12 touch** was verified with synthetic touch pointer events (no real touchscreen; chrome-devtools `drag` does not drive pointer events, G23). Mouse drag was verified with real input (Playwright).

## 6. R1 audit — everything shipped that changed, however small

- Viewbar: "Sections" button gone (handover); "Stages" gained a flag icon and opens the sheet; "By stage" inserted after Journey (the phone grid is now 5 columns).
- A sentence card sits between the tabs and the viewbar; the builder is 44 px + the card shorter (`calc(100vh - 362px)`), so the page itself never scrolls.
- Journey / Across / Flowchart section titles of *bound* sections show the stage's current name from the company list (same text unless the area renamed it). In Journey a bound section's number circle is grey (area) or filled indigo (yours); headings keep the old tint.
- Journey and Across sections carry the tag / "Gets here when" / already-happens lines under the heading; Flowchart labels carry an icon and a chip on the same line (no layout change, measured).
- Review: glyph icons (!, ✓, ↗, ◷) → SVG; rows top-aligned; errors under "To finish", warnings under "Check these"; "Open sections" → "Open Stages"; a new "Already happens for these records" group; version dates in local time. The shipped "Existing automation to review" and "Also active for these records" banners are unchanged.
- Progress page: the record strip is replaced by the merged track when the server sends `record_stage` (old strip otherwise); legend "✓ Completed" / "● You are here" and the cards' "● You are here" use SVG icons; "Updated", "Started", "Completed", "Continues at" are local times (were raw UTC).
- Drag: HTML5 drag replaced by pointer drag; cards and step-list items no longer carry `draggable`; a mouse drag starts after 6 px; a drop that changes nothing no longer adds an Undo entry. Escape, slot highlight, "Move step" dialog unchanged.
- The toast is now a top-layer popover (visible above dialogs; was hidden behind them, G19).
- Switching view keeps keyboard focus on the view button; the sentence moves focus into Start settings. Leaving the editor closes an open Stages sheet.
- Create workflow (and record set-up) dialogs gain "Start with the …'s own stages", **checked by default** when the record type declares its stages: a new Expense / Time off / Hiring workflow now starts with the record's stages instead of Prepare / Do the work / Finish. Unchecked gives today's three headings.
- `chrome_test.cjs` lines for the old dialog and glyph updated.

## 7. Overlaps found (R2a) — for the owner

1. **Review lists "already happening" things three times** (P1 overlap 1 / G8, now sharper): the shipped "Existing automation to review" banner, the shipped "Also active for these records" banner, and P3a's "Already happens for these records" group (which already includes other workflows' steps and automated rules). Options: (a) keep all three; (b) fold the two banners into the new group, keeping the "I checked these" box beside it; (c) keep the banners only for the activation check. Recommend (b).
2. **"Move to <stage>" on the progress page vs the area's own buttons.** For user-made stages Studio is the owner, so there is no double-up today. When P4 brings progress to the employee home, the same button should appear there and not as a second "approve"-like button on the record form. Note for P4, no decision needed now.
3. **Stage target time** is shown in the sheet only; nothing chases it (D13 says feed the approval reminders in P4). No new chaser was built.
4. **Statuses of record types without a declared contract** (e.g. "Other request": Sent back, Turned down, Withdrawn) are offered as ordinary stages because nothing marks them as exits (G26). Options: (a) declare a contract for "Other request" (recommended, in P3b with the other contracts); (b) hide discovered stages from "Use all of them".

## 8. Self-score against the design bar

| Bar | Score | What is still weak |
|---|---|---|
| Hero moment (open an Expense workflow, see real stages, what already happens, add a stage in three answers) | strong | The Waiting approval column is tall when the approval route has many rows; the sentence card adds height on phones, where the shipped header already leaves little room for the builder. |
| Zero dead-ends | good | Server refusals (delete while used, reorder while records are in a stage) arrive as toasts, not inline beside the row. A user-made stage on a record without stages cannot exist (headings only, said in words). |
| Plain language | good | A filter with no value reads "for records where ID is" (seen live on "Test Expense"; P1's shared describer prints the empty value). Server sentences such as "Gets here when: Administrator presses Move to Payment booked" lack quotes around the button name (server text). "Expenses’ stages" possessive is grammatical but reads oddly to some. |
| Motion | good | Sheet slide-in, card lift, row flash, popover fade; all off under reduced motion. Popover does not follow the canvas when it scrolls (it closes on the next click). |
| Keyboard | good | Every new control reachable; sheet traps focus and returns it. The inspector still has no Escape-to-close (shipped). |

Also weak: no real-device touch test; the prototype's "A record cannot leave until every step here is finished" is not built (it is a step setting, P3b).

## 9. What P3b needs to know

- Step types: `TYPES` and `summary()` in `static/workflow/app.js` (line 6 and `summary`), `makeNode()` in `actions.js` line 1, the palette list in `palette()` (`app.js`), the inspector's per-type blocks in `inspector()` (`app.js`; the owner control is now `ownerControl(path, owner, label, noRecord)`, reusable), validation in `models/workflow_definition.py` (`validate`, `STRUCTURAL`) and module actions from the contract's `actions` (`_actions`). Double-up checks for new effect types go in `workflow_contract.py::_repeat_warnings`.
- Hiring `stage_add` (D10): the sheet's candidate branch is `ownRows()` in `stages.js` (banner in `renderSheet`, heading-only form in `stageForm`/`canRealAt`, save in `saveStageForm`). Replace the heading-only path with a call to Hiring's `stage_add` and refresh the catalogue.
- Section changes go through `renumberSections()`/`insertSection()`/`removeSection()` and company-list order through `syncOrder()`/`realignStages()` in `stages.js` — one place each.
- Drag sources are `[data-drag-id]` (cards) and `[data-drag-type]` (step list); slots `[data-slot]`; the sheet uses `[data-section-drag]`/`[data-section-slot]` (`drag.js`).

## 10. Needs an owner decision / follow-ups

- §7 overlap 1 (Review lists what already happens three times) and overlap 4 (declare a contract for "Other request" so its end statuses are exits).
- "Start with the record's own stages" is **checked by default** for record types that declare their stages (Expenses, Time off, Hiring). Confirm that default, or make it opt-in.
- Local test database `am_wf2p3` is left in place (clone of `am_wf2p2` plus this phase's test workflows, two test claims and a local viewer login); the local server was stopped.
