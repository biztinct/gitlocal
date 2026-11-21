# LEARNOS Phase 5 — Practice world: free-roam sandbox + interactive Try flows (DRAFT until Phase 4 merges)

Read both ledgers + accepted reports 1b/2/3/4. Scope: pb_learn + author sources. No deploy,
no commit. Build in chunks (5.1 → 5.4 below), running gates after each chunk and reporting
per chunk.

## Why
All 20 screens already have static replicas (`engine/screens.js`); only the pay-run flow is
truly *drivable*. This phase makes the practice world a place: a free-roam **Practice mode**
anyone can enter from the Journey, plus interactive Try flows for the highest-anxiety jobs
(import, first employee, formula reading), plus the input-step engine work 1b deferred.

## Verified seam facts
- Replica: `SCREENS` map of 20 zero-arg HTML functions, `shellHTML(screen, {guided, visible})`
  (screens.js:1184 area), sidebar `data-nav`, controls `data-coach`, all data from generated
  `fixture.js`. Replica controls are inert outside scenario steps; the Try bridge (journey.js,
  1b) swallows all clicks and only advances on the expected anchor.
- 1b deviation on record: input steps are NOT implemented in Try (card click-through instead);
  the generator accepts `act:"input"` only in try-capable contexts. The 1b matrix behaviour
  (learner types, loose match, mismatch hint) is the contract to build now.
- sc_import / sc_mapping are watch-only wizard tours with no `entry.nav`; on a closed wizard
  they poll 9s per step (rough UX, ledgered).
- Phase-2 debt sweep items (ledger "accepted nits"): live_mission.js step.detail is `esc(tx())`
  (no hovercards, literal <b>); glossify idempotence guard keys on the literal `data-gloss=`;
  `gloss_scan` payload ignores `matchTerm`.

## Scope

### 5.1 Practice mode (free-roam sandbox)
- New Journey view `practice`: `shellHTML` with a NAVIGABLE replica — delegated handler lets
  `data-nav` clicks switch replica screens freely (reuse the scenario bridge's delegation,
  minus the expected-anchor gate). Unmistakable persistent watermark banner (chrome key, both
  languages, register rules): "Practice company — nothing here is real." Exit returns to map.
- Entry points: a "Practice mode" card row on the Journey map + a Coach drawer entry.
- Structural guarantees (tested): in practice view the ONLY orm calls possible are
  progress/event (grep/AST: the practice view handler never reaches `orm.call` outside the
  allowlist); the watermark element is unconditionally rendered by the view builder (a
  template guard, not a state flag).
- Event kinds: practice_open / practice_nav / practice_exit (add to learn.event whitelist).

### 5.2 Input steps for Try (the 1b matrix, for real)
- Engine: on an `act:"input"` step in Try, the anchored replica element must be (or contain)
  a real `<input>`; learner types, Enter/blur checks loosely (trim, casefold, digit-grouping
  tolerant for numbers); mismatch → hint card showing the expected value (`scExpected` chrome
  exists); match → advance. Never advances on click alone.
- Replica: add input-capable elements ONLY where a scenario needs them, declared in
  `practice-data.js` (an `INPUT_ANCHORS` map: anchor → {kind: text|number, get expected from
  the step's `value`}). `screens.js` renders them from that map so the generator, the engine
  and the replica agree from one table.
- Generator: `act:"input"` now REQUIRES the anchor ∈ INPUT_ANCHORS (refusal + negative-control
  fixture); `value:B` mandatory; watch-mode behaviour stays "typed into the card".
- Contract check: input-anchors-exist-in-replica (the INPUT_ANCHORS keys appear in emitted
  practice anchors).

### 5.3 Three new/extended Try flows (each its own chunk-report)
1. **sc_import gains try**: over the `import` + `importwizard` replica screens — pick the
  file (click), see the preview score, fix one flagged cell (INPUT step), accept the mapping,
  land in staging. Extend the importwizard replica minimally from fixture data.
2. **sc_people (new scenario)**: "Add your first employee" on the `employees` replica — open
  the form (replica sub-state), type the name (INPUT), pick a division (click), see the row
  appear. Mirrors activation checklist item 2 so Try-then-Do reads the same.
3. **sc_formula try (extend)**: read-side exploration on the `formula` replica for the anchors
  the replica already draws (1b found 7 of 17) — scope the try-mode steps to those 7 via the
  generator's per-mode screens validation; do NOT rebuild Formula Studio in the replica.
- All copy EN+VI at register, jargon-gated; anchors via generator into anchors.json practice
  block; every flow's guard placements explicit.

### 5.4 Debt sweep (small, mechanical)
- live_mission.js `step.detail`/`instruction`: `esc(tx())` → `gtx()` where bodies are
  authored-HTML (align with journey; markup() discipline; hovercards appear in live missions).
- glossify idempotence guard: key on a marker attribute check via DOM-safe regex on the span
  itself rather than the raw literal (a token value containing `data-gloss=` must not disable
  glossing) + replay assertion.
- `gloss_scan` honours `matchTerm` (one-table honesty; removes the known draft/nháp
  divergence NEW-4).
- sc_import/sc_mapping watch UX: give both an `entry.nav` to the import cockpit action so
  watch mode starts somewhere real; steps whose anchors live inside the (closed) wizard keep
  the centred-card degradation but drop their timeout to 2000ms via the step `timeout` field.

## Non-goals (binding)
- No new DB models/fields; learn.event whitelist extension only. No AI changes. No real-screen
  changes outside pb_learn. Formula Studio replica NOT expanded beyond existing anchors. No
  copy churn outside the new flows + touched strings.

## Tests (numbered)
1. All gates green after EVERY chunk (generator/--check/contract/jargon/resolver/replay/
   scenario rules; node --check; py_compile).
2. Engine negative controls (executed, both runs recorded): (a) input mismatch never advances;
   (b) input step on a non-INPUT_ANCHORS anchor refused by the generator; (c) practice-view
   orm allowlist — adding a `orm.call("learn.intent", ...)` inside the practice handler fails
   the structural test; (d) watermark removal fails its test.
3. Replay additions for: loose-match rules (trim/case/digit grouping), practice nav switching,
   the three flows' step tables (keys/anchors/guards), matchTerm honoring in gloss_scan.
4. Anchor audit green (new practice anchors emitted + referenced).
5. Register/readability: new sections included in the table; zero >28-word sentences.
6. Report per chunk: files, step tables with guards, negative-control outputs, VI list.

## Report back
Per-chunk packages + worktree path; deviations; ledger candidates; deploy-time Chrome script
(practice-mode free-roam on empty tenant; the three Try flows end-to-end; live-mission
hovercards; sc_import watch from the cockpit).

## Kickoff
"Implement docs/handovers/LEARNOS_PHASE5_HANDOVER.md exactly. Read it and both ledgers first.
Worktree only; no deploy, no commit; leave the tree for review."
