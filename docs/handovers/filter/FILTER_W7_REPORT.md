# FILTER wave 7 — report (Time, trips, leave, claims)

Branch `worktree-agent-a83036f4654f18720`, rebased onto `19.1` @ `15049168f`
(W1/W2/W4 merged, kit 1.2.0). Builder: Opus. Tested on the shared preview
(`pbf_preview`, a copy of payobook), held as `w7` 07:27–07:50 UTC, released.
Nothing touched the live addons, the live databases or `/opt/deploy-notes.md`.

**Summary: all four screens converted and passing T1–T22 (n.a. where marked)
and W7-T1…T4 on the preview.** Testing found three defects, fixed and retested
(leave-type chip showed a record number; a doubled "Waiting on me" chip; cramped
lanes inside Expenses) plus one translation-merge trap (F31).

| Screen | Result |
|---|---|
| Business Trips (`pb_business_trip`, standalone + Expenses › Trips) | PASS |
| Time Off › Approval queue (`pb_timeoff`) | PASS (after the label fix) |
| Attendance Control › Corrections (`pb_attendance_flow`, standalone + Time hub › Exceptions) | PASS |
| Expenses › Claims (`pb_expenses_hub`) | PASS |

Modules for the live deploy — every one gains a dependency on `pb_filter_kit`,
so `-u` on every DB where it is installed (not looks-only):

| Module | Manifest version |
|---|---|
| pb_business_trip | 19.0.1.3.0 |
| pb_timeoff | 19.0.1.8.0 |
| pb_attendance_flow | 19.0.1.2.0 |
| pb_expenses_hub | 19.0.1.2.0 (new `models/` package) |
| pb_learn | 19.0.20.7.1 (rebased over W1's 20.7.0; anchors.json + screens.js) |

`pb_filter_kit` unchanged (19.0.1.2.0).

---

## 1. Per screen

### 1.1 Business Trips — `pb.trips` → `pb.business.trip`, screen `trips`
- Base: the companies being looked at (as before); record rules do the rest. No sudo.
- Sections (✔ shown on the copy, ✖ hidden: one value or none): PIN **Where the trip
  is** ✔ (a `choice` in the board's own words: Draft · With the manager · With
  finance · With HR · Authorized · Refused · Cancelled — F28), PIN **Who is
  travelling** ✔, PIN **Department** ✔; **Who it waits on** ✔ (Me / Somebody else,
  `domain_method`: one search of the trips at a step + the card's own
  `_can_current_user_act`, memoised per request), Leaves on ✔, Back on ✔,
  Per-diem policy ✔, Cash advance ✔ (money), Expected cost ✔ (money), Their
  manager ✔, Country ✖, Company ✖.
- Views: Open trips · Travelling this month (Authorized, leaves before the month
  ends, back after it began) · Awaiting authorisation · With a cash advance ·
  Refused or cancelled.
- Sorts: Latest start first (the old order) · Earliest start first · Waiting
  longest first · Biggest cash advance first · Most expensive first · Newest
  request first. Page: 120 cards for all lanes together, "Show N more".
- Kanban: the five lanes stay and ARE the step section (kit `always: ['step']`),
  so lane counts and the step strip follow every other filter (R1). A lane the
  filters leave out folds to a slim column that still says how many it would hold;
  pressing it adds that step. A lane cut by paging says "+N further down · show
  more". Lane cash advance per state comes from the server for the same filters.
  The refused/cancelled footer is the view (its button opens it).
- Numbers that filter: Open trips, Awaiting my approval, Advance outstanding (each
  = its view's filters, lit when exact). Days travelled stays a plain figure.
- Removed: the unbounded search, the client-side step/"mine" narrowing, the
  "Showing … press a step" line. `get_pipeline_data` unchanged (R4); new
  `get_trips_head` gives the numbers without building every card.
- Embedded in Expenses: no title (W17), panel sticky inside the lens's own scroller.
- Learn: nothing describes this screen's filters (`grep -c "pbtr\|trips" pb_learn/static/src/anchors.json` → 0;
  the hub line "Business trip requests and their approval." is still true).

### 1.2 Time Off › Approval queue — `pb.timeoff` → `hr.leave`, screen `leavequeue`
- Records under sudo exactly where the board already read under sudo:
  `_pbf_records()` passes `_require_officer` first, then `.sudo()`; base = the
  board's company scope + state ∈ waiting / approved / refused. `pbf_layout`
  refuses non-officers (verified: layout refused, page and counts raise).
- **Deviation from the handover:** the base widens from "waiting" to waiting +
  approved + refused, otherwise the views "Approved this month" and "Refused"
  could never hold a row. The first view, Waiting for approval, is today's queue.
- Sections: PIN **Status** (To approve · 2nd approval · Approved · Refused), PIN
  **Leave type**, PIN **Department**; Who is asking, First day, Last day, How many
  days, Asked for afterwards (`pb_backdated`), Papers ✖ on the copy, Company.
  All many2one sections `label_sudo` (F32). **Papers** uses the request's
  `attachment_ids`: `supported_attachment_ids` is computed and not searchable.
- Views: Waiting for approval · Backdated requests · Starting this week (waiting +
  approved) · Approved this month (first day this month) · Refused.
- Sorts: First day soonest (the old order — the lesson's "in date order" stays
  true) · First day latest · Longest first · Newest request first · Name A–Z. 30 a page.
- Layout: the queue takes the full row (a 276px panel cannot sit in half a row);
  the heatmap moves under it, unchanged. Approve / refuse reload the queue page,
  the counts and the numbers line only (new `get_kpis`); heatmap and balances stay.
  `get_board(…, with_queue=False)` from the cockpit; old payload kept for its tests (R4).
- Learn: `coach="'wf-leave-filters'"` (literal kept in an XML comment, F22),
  declared `reserved` in `anchors.json`; the `wftime()` replica draws the filter
  strip under "Approval queue"; `wf-leave-queue` stays on the queue panel.

### 1.3 Attendance Control › Corrections — `pb.attendance.flow` → `hr.attendance.correction`, screen `corrections`
- R5: the exceptions queue (engine rows) keeps its tabs. The corrections pipeline
  converts; read as the reader (record rules), no sudo, no company domain.
- Sections: PIN **Status** (Draft · Waiting for approval · Applied · Refused), PIN
  **Who it is for**, PIN **Department**; Who it waits on (Me / Somebody else — the
  card's own `can_approve`, memoised), Day corrected, When it was applied (This
  week / Before: the approval trail's stamp — no applied-on field), What it
  changes ✖ on the copy, Filed from (exception kinds in the queue's own words) ✖,
  Problem applying it (`apply_error`) ✖, Their manager, Company.
- Views: Waiting for approval · Applied this week · Failed to apply · Mine to review · All.
- Sorts: Newest first · Waiting longest first · Latest day first · Name A–Z. 30 a page.
- Embedded (Time hub › Exceptions): the shared week, department and pinned person
  arrive through `initial` as chips on top of the first view ("Waiting for
  approval" lit with a changed-dot) and follow the context when it changes;
  `loadCorrections` never calls `_changed()` (W21 — verified: request count
  steady, no new rows). The two panels now stack (exceptions, then corrections).
- Learn: nothing describes the corrections' filters (`wf-exceptions` wraps the lens; unchanged).

### 1.4 Expenses › Claims — `pb.expense.claims` → `pb.expense.claim`, screen `claims`
- New facade in `pb_expenses_hub/models/`. Base = the companies; rows as the reader
  (claim record rules); `pbf_layout` and the page refuse anyone without the tab's
  gate (team approver or admin). `total` and `receipt_count` are stored ✔.
- Sections: PIN **Status**, PIN **Who sent it**, PIN **Total** (money); Their
  department, Sent on, Decided on, Paid on, Number of receipts, Company.
- Views: Waiting approval (the old default) · Approved, not yet paid · Paid this
  month · Refused · Sent this month. Sorts: Newest sent first · Waiting longest
  first · Biggest total first · Newest claim first. 60 a page.
- A small table (claim, who + department, sent on, receipts, total, status),
  keyboard-walkable (↑ ↓ Enter); row opens the native claim form in the main
  breadcrumb; back returns with the filters (W7-T4). "New claim" kept in the toolbar.
- The native list/search view stay for the menu's act_window. The static test that
  asserted the native list now asserts the panel (`test_the_claims_tab_is_on_the_filter_panel`).
- Learn: nothing describes this list (hub line "Expense claims people send in…" still true).

---

## 2. Test matrix (preview, Chrome DevTools MCP 1440×900; T21 at 420×860)

Test data on the copy (deleted afterwards, copy back to 9 trips / 4 corrections /
1 claim): 125 trips, 32 corrections, 62 claims, 24 leave requests, spread over
the states by SQL. One REAL demo leave request (Mitchell Admin, 2–4 Feb) was
approved on the copy for W7-T2 and left approved. No saved views left; `pbf:*`
storage cleared; the admin's language set back to English.

| Test | Trips | Leave queue | Corrections | Claims |
|---|---|---|---|---|
| T1 open, counts, first tab, list, console | pass | pass | pass | pass |
| T2 tick → chip, own count stays, others recount | pass | pass | pass | pass |
| T3 OR within section | pass | kit ¹ | kit ¹ | kit ¹ |
| T4 AND across | pass | pass | pass | pass |
| T5 Only | pass | pass (found the label defect, fixed) | kit ¹ | kit ¹ |
| T6 find + Enter + Escape | pass | kit ¹ | kit ¹ | kit ¹ |
| T7 nothing matches | pass | kit ¹ | kit ¹ | kit ¹ |
| T8 date preset + range | pass | pass | n.a. ² | pass |
| T9 number | pass (₫1M or more) | pass (3 or more) | n.a. | n.a. ³ |
| T10 chip / × / clear all | pass | pass | pass | pass |
| T11 search + Escape | pass | kit ¹ | kit ¹ | pass |
| T12 sorts | pass | pass | pass | pass |
| T13 Show N more | pass (120→134) | pass (30→37) | pass (30→36) | pass (60→63) |
| T14 save / rename / share / delete | pass | kit ¹ | kit ¹ | kit ¹ |
| T15 built-in views | pass | pass | pass | pass |
| T16 numbers line | pass (3 figures) | pass | pass | n.a. (no numbers line) |
| T17 hide + reload | pass | kit ¹ | kit ¹ | kit ¹ |
| T18 link → reopen | pass | kit ¹ | kit ¹ | kit ¹ |
| T19 bulk / export | n.a. | n.a. | n.a. | n.a. (decisions in Approvals) |
| T20 empty + way back | pass (filters + search) | pass | pass | pass (filters + search) |
| T21 phone drawer | pass | kit ¹ | kit ¹ | kit ¹ |
| T22 Vietnamese | pass (screen + call) | pass (screen + call) | pass (call) | pass (call) |
| Console errors/warnings | none | none | none | none |

¹ Same kit code path, exercised in full on Trips (as W4 did on Vendors).
² Day-corrected presets counted correctly through the embedded week range chip.
³ Every claim on the copy totals ₫0 except one; the section and its hint render.

Wave tests:
- **W7-T1** Trips: Department → 9 of 134, lanes Draft 2 / Manager 3 / Finance 2 / HR 2,
  Authorized folded 0 — each lane's count equals its cards; a second department → 17. PASS.
- **W7-T2** Leave queue: approve → the request left the page, Status 37→36,
  Approved 37→38, "Waiting for approval" figure 37→36, heatmap unchanged. PASS
  (the view tab numbers stay until the next load — F33, kit gap 1).
- **W7-T3** Time hub › Exceptions with a pinned person: chips "Status Waiting for
  approval", "Who it is for Bùi Bá Tâm", "Day corrected 26 Oct – 1 Nov"; × on the
  person → 9; a week change follows the context (person comes back while still
  pinned — the pin is shared state, cleared by the exceptions chip). PASS.
- **W7-T4** Claims: Refused + one person → open EXP/2026/0003 (native form) → Back
  → same view, same two chips, 1 of 63. PASS.
- Refusals (plain internal user, no HR/expense groups): leave queue refused on
  layout, page and counts; Claims refused on layout and page, counts 0; Trips and
  corrections show only what their record rules allow (0). PASS.
- Trips "Approve as …" could not be exercised on this copy (F36); the reload it
  calls is the one the trip form uses on close (tested).

Speed on the payobook copy (ms, before test data): layout / counts (all sections)
/ page — Trips 50/114/111, Leave queue 30/82/51, Corrections 69/109/49, Claims
47/67/63; `get_trips_head` 11, `get_kpis` 6, `get_board` without the queue 137.

Screenshots (local, Chrome DevTools MCP):
`/Users/adity/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/9210e315-2d9d-4acd-ba15-28e97cb48de6/tool-results/`
`mcp-chrome-blob-1793431996838-ugyvia.jpg` (Trips, folded Authorized lane),
`…1793432359062-lffft7.jpg` (Trips phone drawer), `…1793432428413-yslfls.jpg`
(Trips inside Expenses), `…1793432492954-an33gy.jpg` (Claims),
`…1793432999494-h6ndmp.jpg` (Trips in Vietnamese). Leave queue and corrections
were verified by DOM state (no screenshot taken).

## 3. Deploy evidence (preview rehearsal only — the live deploy is the coordinator's)
- `pbf_preview.sh upgrade pb_filter_kit,pb_business_trip,pb_timeoff,pb_attendance_flow,pb_expenses_hub,pb_learn`:
  EXIT=0, no ERROR/CRITICAL line from this run (the script's `errors=11` counts
  old 02:49 lines in the appended log); then twice more for fixes and
  translations, same result. Versions on the copy: 1.3.0 / 1.8.0 / 1.2.0 / 1.2.0 /
  20.7.1 / kit 1.2.0.
- PO gate (server `PoFileReader`) passed for all four `vi_VN.po`.
- Live: not touched. Cron counts / hashes / per-DB versions: n.a. for builders.

## 4. Kit gaps and design debts
Kit gaps (pb_filter_kit unchanged):
1. **View tab counts do not follow an action** (F33): after approve/refuse the tab
   numbers keep the load-time counts. Ask: recount `views` in `kit.refresh()` (or a
   `kit.refreshViews()`), at least for built-in views.
2. **Labels of a ticked zero-match value are read as the reader even on sudo
   screens** (F32). Ask: `_pbf_label_values` should use `self._pbf_records().env`
   by default.
3. **`initial` cannot say "apply on top of the first view"**: corrections build
   the first view's filters by hand to add the host's week/person.

Design debts:
- Trips' advance and cost sections mix currencies across companies (same as W4's Assets).
- Leave queue base now includes approved and refused requests (needed for two
  views); the queue view is unchanged.
- "Applied this week" relies on the approval trail's stamp (`biz.approval.step.log`),
  which is written without sudo and never fatal: a correction whose trail row
  failed to write would be missing from that view.
- The leave-queue and corrections panels change their boards' layout (stacked, not
  side by side) — the panel needs the width.
- Pre-existing, not fixed: many untranslated older strings in `pb_timeoff`
  (policy, holiday calendar) and `pb_attendance_flow`; demo trips on the copy have
  no approval request (F36).

## 5. Self-score (design bar)

| Screen | Hero moment | Zero dead-ends | Plain language | Motion | Keyboard / bulk |
|---|---|---|---|---|---|
| Trips | lanes follow the panel; out-of-view lanes fold to a slim "+ add" column with their count | skeleton lanes, no-trips, filters, search, failure; lane "+N further down" | lanes in the board's words | lane fade-in, reduced-motion safe | `/`, Enter opens a card, kit keys; no bulk |
| Leave queue | the old queue is the first view, one click to backdated / this week | skeleton, queue clear, filters, search, refusal | yes | skeleton pulse | `/`, kit keys; per-card approve/refuse |
| Corrections | the Time hub's week and person arrive as removable chips | skeleton, none yet, nothing waiting, filters, search, refusal | exception kinds in the queue's words | skeleton pulse | `/`, Enter opens; no bulk |
| Claims | from a native list to a counted, saved-view list | skeleton, none yet, nothing waiting, filters, search, refusal | yes | row fade-in | `/`, ↑ ↓ Enter; no bulk (Approvals decides) |

## 6. Commits (branch `worktree-agent-a83036f4654f18720`)
- `5ec77e9f0` feat(filter): Business Trips on the shared filter panel
- `8fdf2cb46` feat(filter): Leave approval queue on the shared filter panel (+ pb_learn anchor, replica)
- `279eb546a` feat(filter): Attendance corrections on the shared filter panel
- `9e78ab18f` feat(filter): Expenses › Claims on the shared filter panel
- `20c10a787` fix(filter): W7 search hints and the trips step label as translated getters (F29)
- `3c47b304a` fix(filter): W7 fixes found on the preview
- `0769d9230` i18n(filter): Vietnamese for the W7 filter panels
- this report + ledger F31–F36 (docs commit)

Not committed: nothing of the product. Not pushed, not merged.
The pb_learn version in commit `8fdf2cb46`'s message says 20.6.6; after the rebase
over W1 it is 20.7.1.

## 7. New gotchas
Appended to `FILTER_LEDGER.md` §4 as **F31–F36**: shared terms in a multi-module
export; sudo screens label zero-match values as the reader; view tab counts stay
after an action; keeping the preview alive (`setsid nohup … & disown`); the
DevTools MCP's file roots and the clipboard hang; trips on the payobook copy need
no approval.

Process note: the preview `hold` raced at 02:48 (F26) and then waited behind w6
for ~4.5 hours (two `LOCK_TIMEOUT`s) before w7 held it at 07:27.
