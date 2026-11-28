# WORKFLOW-2 · Phase 3a handover — the screens (stages, "already happens", By stage)

Read first, completely: `WF2_LEDGER.md` (R1–R9, R2a, D1–D13, conventions, gotchas G1–G16), `WF2_P2_REPORT.md` §5 and §7 (the exact JSON this phase renders), and open the clickable prototype `docs/design/workflow-studio/review/second-opinion-poc.html` in a browser — it is the visual and wording reference for everything new in this phase (the "When…" sentence, By stage view, Stages sheet, "Already happens here" rows, "Gets here when…", the record view with one plain sentence). The prototype's own Journey / Flowchart drawings are simplified: **the shipped ones stay as they are** (R1).

Design bar (R9, verbatim): **"extreme WOW, intuitive, out-of-this-world experience, best in class."** Hero moment of this phase: a process owner opens an Expense workflow and, without reading any help, sees the claim's real stages across the screen, what already happens at each, and adds their own stage in three answers. Zero dead-ends: every empty, loading and error state is designed and names its next step. Motion with purpose only. Lucide-style SVG icons from `icons.js` (add to it), never emoji; no character glyphs as icons (replace `!`, `✓`, `↗`, `◷`, `●` used as icons where you touch them). White-label (R7): "Odoo"/"OdooBot" never in a user-visible string. Plain English (R8): no model names, field names or internal words (`bind`, `core`, `anchor`, `gate`) on screen.

## 1. Scope

All in the workbench `pb_lifecycle/static/workflow/` (plain JS + CSS inside the iframe), plus two small backend touches.

1. **"When…" sentence** above the view switcher in Build.
2. **Stage headers everywhere**: on Journey, Across, Flowchart and the new By stage view each section shows what it is (the area's own stage with a lock, your stage and what it counts as, or a heading), its "Gets here when…" line, and what already happens there.
3. **By stage** as a fifth view.
4. **One Stages screen** replacing the two buttons "Stages" and "Sections": add your own stage in plain questions, use the record's stages, headings, rename, reorder, remove.
5. **Record progress**: the strip above the run chart shows the merged track with user-made stages and one plain sentence; a person who may move a record sees "Move to …".
6. **Review**: warnings and "already happens" presented clearly (data exists since P2).
7. **Drag that also works by touch**, keeping today's mouse behaviour.
8. Backend: a contract flag so Studio refuses its own stage layer on Hiring candidates (D10); the approval "no approval needed" lane must not list approver messages.

### Binding non-goals

- R1: do not remove or restyle Journey, Across, Flowchart, People, the canvas (dotted background, curved connectors, "+" points, zoom/fit), the left step list, tabs, the template composer, forms, My tasks, Activity. You add to them.
- No new step types and no new step settings (P3b). No inbox merge, reminders or portal work (P4). No translations (P5).
- No changes to `pb_me_expense`, `pb_timeoff`; in `pb_hiring` only the one contract flag in §3.8.
- No new stored fields or models.
- Do not rebuild the workbench in another framework. Follow the file's existing style (state object `S`, `render()`, `data-act` actions, `mutate()` for undoable definition changes, `rpc()`).

## 2. Verified plumbing

- Files: `app.js` (state `S`, `render`, `editor()`, `palette()`, `inspector()`, `reviewPage()`, `progressPage()`, `mutate`, `save`), `graph.js` (`targets(d)` = valid insert positions, `moveStep`, `graphLayout`, `nodeCard`, `drop`, `journey`, `flowchart`, `horizontalJourney`), `actions.js` (`action(name, el)` dispatcher; `addNode`; sections dialog `stageDialog` and actions `stages`, `sections`, `stage-add`, `stage-remove`, `stage-save`; HTML5 drag handlers `dragstart/dragover/drop/dragend` near the end), `record-context.js` (`stageTrail`, `approvalStageNote`, `recordStagesDialog`, record setup page, `stage-rename`, `stage-wait`), `conditions.js` (`filterEditor(tree, path, fields)`), `icons.js` (`svgIcon`), `style.css`.
- Viewbar today (`editor()` in `app.js`): segmented `journey | horizontal (Across) | flow | people`, then buttons `Stages`, `Sections`, `Settings`. `S.view` values are restored by `restoreOrigin` in `actions.js` (list of allowed views there).
- Sections in the definition: `definition.stages[i] = {name, bind?}`; node `stage` = index; main-path nodes in non-decreasing section order; grouped nodes inherit the group's section. `targets(d)` already yields per-section insert positions on the main path; `drop(t)` renders a "+" slot; dropping/clicking uses actions `add-at` and the drag handlers; `moveStep` validates.
- `stage-save` renumbers node sections and `workflow.*` filter values when sections are removed — reuse that logic for every section add/remove/reorder; do not write a second renumbering.
- Data from P2 (shapes in `WF2_P2_REPORT.md` §7): `S.w.metadata.contract`, `S.w.metadata.stage_catalogue` (object with `.stages`), rpc `stage_catalogue(model, workflow_id)`, `existing_behaviour(model, workflow_id)`, `stage_create / stage_update / stage_reorder / stage_delete`, `stage_rename_shared`, `move_record_stage(model, record_id, stage_id)`, `record_stage(model, record_id)`; `progress()` and `record_runs()` carry `record_stage` and `gate`; `review()` returns issues with `severity`, `acknowledged`, `existing`, and `blocking`. Binding: `{"kind":"core","value":"approved"}` / `{"kind":"yours","id":37}`. Binding errors come back with `id: "sections"` and `section: <index>`.
- New-process workflows (`!S.w.source_model`): no core stages; user-made stages belong to the workflow (`model=''`, `workflow_id`).
- P1/P2 already added: matrix "What should this step do?" select, Review warning rows with "Keep it, it is different" (`ack-repeat`), module-action params from the contract, owner "The person this is about". Two cache keys must be bumped when workbench files change: the iframe `v=` in `static/src/js/workflow_studio.js` and the script-tag key in `static/workflow/index.html` (ledger gotcha from P2).
- Local browser testing: P1/P2 reports describe the local server and database (`am_wf2p2` was left in place).

## 3. Design

### 3.1 The sentence

A full-width card above the view switcher: **"When** ⟨an expense claim⟩ ⟨is created⟩**,** ⟨for everyone⟩**"**. Three chips built from `contract.label` (fallback: module label), the trigger kind, and the scope summary (reuse the plain filter summary P1 added — do not write another). Wording per trigger: `manual` "is started by a person", `created` "is created", `changed` "has ⟨field labels⟩ changed", `date` "⟨n units⟩ before/after ⟨date field label⟩", `approval_applied` "has its approval finished". New process: "When ⟨someone⟩ ⟨starts ⟨workflow name⟩⟩". Clicking anywhere on it selects the Start step (opens the existing inspector); a "Change" button does the same. Keyboard reachable.

### 3.2 What each section shows (shared by all views)

One helper builds a section descriptor from `definition.stages[i]`, the catalogue and `existing_behaviour`:

- **Tag**: lock icon + "⟨Area⟩ owns this stage" (bound to the area's stage) · flag icon + "Your stage · counts as ⟨name⟩ in ⟨Area⟩" (your stage; on a new process just "Your stage") · list icon + "Heading" (unbound).
- **Gets here when**: the catalogue's `enters` sentence, lower-cased after the colon. Headings have none.
- **Already happens here**: effects whose `stage` equals the bound key, as quiet grey rows: icon by `kind`, the `text`, the `owner` underneath, and an "Open" link when `settings` is present (use the existing `resource`/`open_resource` return path so the designer comes back to the same workflow, step and view; for `settings.workflow_id` open that workflow). Effects with `stage: null` are not repeated per section; they appear once on Review and in the Stages screen under "Any time".
- A bound section whose stage `exit` list exists: show the exits once under the last stage as a small note line ("If an approver says no, it becomes Refused. Steps after that point do not run."), built from the catalogue's exit stages' `name` and `enters`.

Where it renders:

- **Journey**: under the existing section heading (`.stage-head`): tag + gets-here line, then the grey rows, then the steps as today.
- **By stage**: same content at the top of each column.
- **Across**: tag in the section heading; a single line "⟨n⟩ things already happen here" that expands in place.
- **Flowchart canvas**: keep the canvas clean. The existing `.stage-label` gains the tag icon and, when there is anything, a small chip "⟨n⟩ already happen" that opens a popover listing the rows. Layout heights must not change (no reflow of `graphLayout`).
- Loading: `existing_behaviour` is fetched once per workflow open (and after a stage change); while loading show nothing rather than a spinner per section; on failure show one quiet line "Could not load what already happens here. Try again." with a retry.

### 3.3 By stage view

- Fifth entry in the view switcher, after Journey: label "By stage". `S.view = 'stage'`; add to `restoreOrigin`'s allowed list.
- Columns = sections in order, min width ~250 px, horizontal scroll inside the work area on desktop, stacked on phone width. Column header per §3.2. Cards are the existing `nodeCard`; groups render nested exactly as Journey does (`.path` blocks) — no new group rendering.
- "+" insert positions and drag targets come from the existing `targets(d)` / `drop(t)`, so add, move, validation and Undo behave exactly as in Journey. A trailing "Add a step" button per column inserts at that section's end.
- Empty section: "No steps here yet. Add one, or drag a card in."
- A final dashed column "Add a stage" opens the Stages screen at "add at the end".

### 3.4 Stages screen

One button **Stages** in the viewbar (remove the separate "Sections" button; its job is inside). Opens a right-hand sheet (not the small modal), closable with Escape and a Done button; focus is trapped while open and returns to the button on close.

Content, top to bottom (see the prototype's sheet):

- One intro sentence. Record workflows: "Stages with a lock belong to ⟨Area⟩. You can add your own between them, here, with no set-up by anyone else." New process: "This is your own process, so every stage is yours."
- The list = this workflow's sections in order. Row: number, name, tag (as §3.2), "Gets here when…", step count; for your stages also the target time and, when `count > 0`, "⟨n⟩ records are here now".
- Between rows and at the end: **Add a stage here**. Inline form, three plain questions:
  1. Name.
  2. "What is it?" — **A real stage** (people see it on the record; on a record workflow it sits after ⟨previous area stage⟩ and ⟨Area⟩ still treats the record as ⟨that stage⟩, so its reports and rules keep working) / **Just a heading** (groups steps in this picture only).
  3. For a real stage: "How does a record get here?" — By itself, when the steps before are finished / A person moves it (then "Who may move it": the same owner choices as a task, reuse that control) / When a rule is true (reuse `filterEditor`). Then "Target time in this stage" (none / 1 day / 3 days / 1 week / 2 weeks → `target_hours`).
  Save → real stage: `stage_create`, then insert a section bound to it at that position; heading: insert an unbound section. One Undo step for the definition change (the created stage stays in the company's list, which is fine).
- **Use the record's stages** (record workflows with a declared contract): each of the area's stages not yet used in this workflow is offered in a compact "Not used yet" strip; one click inserts a section bound to it at its correct place. The button "Use all of them" inserts every non-exit stage. Existing unbound sections stay as headings where they are.
- Your stages already in the company's list but not used in this workflow appear in the same strip ("Payment scheduled · your stage").
- Per-row actions. Area stage: no rename unless `renamable` (then the existing shared-rename dialog with its warning, via `stage_rename_shared`); "Open in ⟨Area⟩" using the owners/resource link; "Stop using here" turns it back into… no: removes the section if it has no steps (same rule as today's section removal). Your stage: rename, change how records get here and the target (`stage_update`), move earlier/later, remove from this workflow, and "Delete for everyone" (`stage_delete`; show the server's sentence when refused). Heading: rename, move, remove.
- Moving: earlier/later buttons (keyboard-friendly) and drag by handle. Order rules are the server's (bound sections in catalogue order; headings anywhere); when a move is not allowed say why in plain words before attempting it ("⟨Area⟩'s stages keep their own order."). Moving a your-stage across an area stage calls `stage_reorder` (it changes what the stage counts as — say so: "It will now count as ⟨name⟩."; the server refuses while records are in it).
- Sections with steps cannot be removed: "Move its ⟨n⟩ steps first" with a one-click "Move them to ⟨previous section⟩".
- Hiring candidates (contract flag from §3.8): "Add a stage" offers only "Just a heading", and a line "Candidate stages are managed in Hiring" with "Open Hiring set-up" (existing resource link). No dead end.
- "Any time" block at the bottom: effects with no stage.

Creating a workflow from a record or model with a declared contract (create dialog and record setup page): add a checked-by-default option "Start with ⟨label⟩'s own stages". When checked, after creation replace the three default headings with sections bound to each non-exit area stage (one save). Unchecked: today's three headings.

The existing "Wait for this" shortcut and the old stage dialog content are superseded by placing steps under a bound section; keep the `wait` step's "until a rule matches" as is. Remove `recordStagesDialog` only when every path into it is replaced.

### 3.5 Record progress

On the progress page replace the content of the strip above the chart (`stageTrail`) with the `record_stage` track when present (fall back to the old strip otherwise):

- Steps in a row: `done` (check), `here` (filled, "Here now"), `later`, `passed` (dash icon, tooltip "It went past this stage"), `stopped`. Your stages show a small flag and "counts as ⟨name⟩". Exits listed after the row; the one that is `here` is highlighted in the warning tone.
- One sentence above it, largest text on the page: waiting step → "Waiting for ⟨owner⟩: ⟨step title⟩."; `gate` present → its `reason`; finished/closed → the run status in words; no run → "No workflow has started for this record. It is at ⟨stage⟩."
- When the record's next section is a your-stage entered by a person and the viewer may move it: primary button "Move to ⟨name⟩" → `move_record_stage`, then refresh; on refusal show the server's sentence.
- Times: show local date and time in the viewer's locale wherever you touch them (no raw "UTC" strings).

### 3.6 Review

- Group the page: "To finish" (errors), "Check these" (warnings, each naming what already does it, with "Keep it, it is different" / "Open step"), "Already happens for these records" (existing behaviour grouped by stage name, then "Any time"), then publish/activate as today. A binding error (`id: "sections"`) offers "Open Stages".
- Publish stays disabled while `blocking` is non-empty.

### 3.7 Drag by touch

Replace the HTML5 drag handlers with pointer events (mouse, pen, touch) for cards and for step-list items, keeping every current behaviour: drop only on "+" slots, slot highlight, Escape cancels, invalid moves explain and change nothing, one Undo per move. Add: a ghost of the card under the pointer, auto-scroll of the work area/canvas near its edges, drag starts from the grip on touch (so the page still scrolls) and from anywhere on the card with a mouse after a 6 px threshold. Zoomed canvas must drop on the right slot. Keep the "Move step" dialog as the keyboard path. If any shipped drag behaviour cannot be preserved, stop and report rather than regress it.

### 3.8 Backend touches

- Contract key `'own_stage_rows': True` on `hr.applicant` (in `pb_hiring`'s contract file); `stage_create`/`stage_reorder` refuse a `yours` stage for such a model with "Candidate stages are managed in Hiring." `metadata.contract` passes the flag. (D10; Hiring's own `stage_add` is P3b.)
- `existing_behaviour`: when the bound route is the "no approval needed" lane, return only the route row, not the approver/reminder messages.
- Tests for both in `tests/test_workflow_studio.py`.

## 4. Safety rails

- Normal tier deploy (no stored-data change): no backups needed, but all five databases get `-u pb_lifecycle,pb_hiring` in one window; keep sudima's Studio job off (D11) and its active job count at 80.
- Never publish, activate or start a real workflow on a live database; never move a real record's stage; never create a real stage on a live database (local database only). Never send mail.
- If the phase would need to change a shipped behaviour to fit, stop and report (R1).
- Overlaps you find go under "Overlaps found" (R2a).

## 5. Test cases

Backend: B1 own-stage-rows refusal; B2 no-approval lane effects; full suite still green (76 + new).

Browser, on the local database, each with a clean console (Expense workflow unless stated):

- U1 Sentence reads correctly for each trigger kind and for a scope with one rule; click opens the Start settings.
- U2 Create from an expense claim with "Start with its own stages": four bound sections Draft / Waiting approval / Approved / Paid, exits note shown, Review has no binding error.
- U3 Journey, Across, Flowchart and By stage each show tag, "Gets here when" and already-happens for Waiting approval (route sentence + approver message); canvas layout unchanged (compare card positions before/after for a workflow with a parallel group).
- U4 By stage: add via "+", add via the column button, drag within a column, drag to another column, drag into a path; an invalid move explains; Undo/Redo each; then Journey shows the same order.
- U5 Stages: add a real stage after Approved entered by a person with a 3-day target → appears in all views as "Your stage · counts as Approved"; add a heading; rename both; move the heading; refused move of an area stage explains.
- U6 Stages: "Use all of them" on a workflow with three default headings; headings remain; order valid.
- U7 Stages: remove a section with steps → offered "Move them to …"; delete-for-everyone refused while a published active workflow uses it (local) shows the server sentence.
- U8 New process: every stage yours; add two; no area wording anywhere.
- U9 Hiring candidate workflow: only headings offered; link to Hiring opens and returns to the same workflow and view.
- U10 Leave workflow: adding an email under Approved shows the repeat warning on Review; "Keep it" clears blocking; publish enabled (local).
- U11 Progress page for a claim in a your-stage: track states, sentence, "Move to …" for the right person, refusal sentence for the wrong one; a claim in Refused shows stopped/exits.
- U12 Touch (device emulation): drag a card by its grip to another section in Journey, By stage and on the canvas at 80% zoom; scrolling still works when not on the grip.
- U13 Keyboard only: reach the sentence, switch views, open Stages, add a stage, close with Escape, focus returns.
- U14 Phone width 390 px: By stage stacks, Stages sheet fills the screen, nothing overflows sideways.
- U15 A model with no declared contract (e.g. employee): headings only plus discovered stages if any; no empty "Gets here when" lines; nothing breaks.
- U16 Reduced motion respected; no emoji or glyph icons in anything you touched; no banned words on screen ("Odoo", "bind", "core", "anchor", "gate", model names).

Extend `tools/workflow_studio/chrome_test.cjs` (or add a sibling) so U2–U8 can be re-run; remove any screenshots it creates.

## 6. Deploy and verify

Versions: `pb_lifecycle` → `19.0.1.12.0`, `pb_hiring` patch bump; bump both workbench cache keys. Commit (explicit paths; one commit for the screens, one for the backend touches + tests, one for docs). Do not push. Deploy per ledger §3 to `payobook`, `payobook_template`, `p0clone`, `rize`, `sudima`; suite on `p0clone` with the service stopped; asset signal + purge; start; warm. Verify hashes, versions, job counts (49 / 31 / 38 / 81 / 80), logs, HTTP 200 for the workbench files with the new cache key.

## 7. Report back (`WF2_P3A_REPORT.md`)

Commits and versions; B1–B2 and suite count; U1–U16 each pass/fail with one line of evidence; deploy evidence; deviations with reasons; anything shipped that changed appearance or behaviour, however small (R1 audit); overlaps found; self-score against the design bar (hero moment, zero dead-ends, plain language, motion, keyboard) with what is still weak; new gotchas in the ledger; what P3b needs to know (where step types and inspector sections are defined now).
