# LEARNOS Phase 1b — Scenario engine: Watch / Try / Do

Read `docs/handovers/LEARNOS_LEDGER.md` + `docs/handovers/PBLEARN_LEDGER.md` + the accepted
Phase 1a report first. Scope: pb_learn + author tools (+ deletion of pb_coach from the repo;
live uninstall happens at the phase-family deploy). No copy polish (Phase 2 owns language).

## Phase 1a seam facts (build on these — do not re-derive)
- Content plane: `pb_learn/static/content/learn_content.json` (generated; sections chrome/
  stations/missions/glossary/intents/screens/columns/global_suggest/version). Client loads via
  `content_loader.js` `loadContent()` (memoized fetch); server via AbstractModel `learn.content`
  (file-backed, lru_cache). Add a `scenarios` section through a new generator builder in
  `gen_learn_data.py` (mirror the existing `content_*` builders + `Bi.p` bilingual leaves);
  extend `parity_check.py`'s section list only if it asserts section names.
- Runtime RPC: `learn.runtime.bootstrap()` — `visible_stations`, `screens_runtime`
  (matchers + own_tag/own_xmlid + next_step), tokens, progress, confidence, user,
  collect_questions, content_version. Use `screens_runtime` matchers for the Coach drawer's
  "Show me how" current-screen scenario list.
- Progress: `learn.progress.key` is a plain Char with `_declared()` validating keys against the
  content plane — scenario keys (`scenario:<key>`) MUST be added to `_declared()`'s accepted
  set, or record() will refuse them.
- live_check lives on `learn.live` now. Mission runner unchanged.
- Contract checker has a `json-content` kind; add scenario checks with it.

## Why
One authored scenario should teach three ways: **Watch** it happen on the real screens,
**Try** it on the practice replica, **Do** it live with the engine waiting before anything
real is written. This replaces pb_coach's six tours and unifies the launcher.

## Design (binding)

### Scenario schema (authored in data.js as `SCENARIOS`, emitted into learn_content.json)
```js
{
  key: "sc_payrun",             // stable id
  icon, line,                    // reuse station vocabulary
  name: B("Run a pay run", "…"), tagline: B(…),
  modes: ["watch", "try", "do"], // which modes this scenario supports
  entry: { nav: "pb_payruns.action_pb_payruns_kanban", screen: "runpayroll" },
    // nav = real-screen action (Watch/Do); screen = replica screen key (Try)
  steps: [ {
    key, anchor,                 // data-coach key — SAME vocabulary in all three modes
    nav,                         // optional mid-scenario navigation (xmlid | client tag)
    screen,                      // optional replica screen switch (Try)
    say:   { kicker:B, title:B, body:B, tip:B },   // the card
    act:   "observe" | "click" | "input",           // what happens at this step
    value: B?,                   // for input steps: what to type (replica only)
    guard: true?,                // LIVE-WRITE GUARD — see mode matrix
    timeout: ms?,                // anchor wait deadline (default 9000)
  } ]
}
```

### Mode behaviour matrix (the heart of the engine)
| step.act | Watch (real screens, autoplay ok) | Try (replica, learner drives) | Do (real screens, learner drives) |
|---|---|---|---|
| observe | spotlight + card, Next/autoplay dwell | same | same |
| click | synthesize el.click() after dwell (pb_coach `_autoplayClick` pattern) | learner must click the anchored replica control; wrong click → gentle nudge toast + ring on the right one; right click → advance | learner clicks the REAL control (click-through, one-shot capture listener); engine never synthesizes |
| click + guard | DO NOT click. Card explains what WOULD happen; step becomes observe | replica click is safe → normal click step | hard stop: card says "You press it — I'll wait." Engine attaches the capture listener but NEVER auto-clicks, NEVER times out into advancing |
| input | show the value being "typed" (animated text into card, not the real field) | learner types into the replica input; value checked loosely (trim/case-fold); mismatch → hint showing expected | not allowed in Do (author error, generator validation rejects input steps without guard-free replica context in do-mode scenarios) |

`guard: true` is REQUIRED (generator-enforced) on any step whose real-screen click submits,
computes, confirms, approves, deletes, or sends anything. Ledger rule: "if in doubt, guard."

### Engine implementation
- New `pb_learn/static/src/scenario/scenario_service.js` + `scenario_overlay.js` + `.scss/.xml`:
  merge of the two existing halves — pb_coach's per-frame rAF tracking loop, `_waitFor` polling
  (9000ms/120ms), click-through one-shot capture listeners, Esc/←/→ keys, missing-anchor
  centred-card degradation (verified in pb_coach/static/src/js/coach_overlay.js:138-162,
  :175-205, :220-224, :284-323, :375-380) — with spotlight.js's card/hole rendering + placement
  (pb_learn/static/src/engine/spotlight.js:100-188) and pb_learn visual language (`.lrn-*`).
  Registered as service `learn.scenario`; overlay in main_components. All copy through
  `T()`/`tx()` chrome keys (new keys authored in data.js I18N).
- Try mode renders the replica via `shellHTML(screen, {guided:true, visible})`
  (engine/screens.js:1184) inside the Journey action (same host as missions today) and adds the
  MISSING interaction bridge: delegated click handler on `[data-coach]`/`[data-nav]` inside the
  replica root that checks the current step's anchor. Replica controls stay inert for anything
  that is not the expected target (nudge, don't punish: "Not that one — try the glowing button").
- Do mode runs on the real webclient (like Watch) but advance-by-real-click only; guard steps
  as per matrix. Autoplay disabled entirely in Try and Do.
- Launcher: scenarios appear (a) in the Journey map as a new card row per line, (b) in the Coach
  drawer under a "Show me how" section listing scenarios for the CURRENT screen (reuse the
  screens_runtime matcher from 1a bootstrap), (c) `show_me` keys in intents may now reference
  `scenario:<key>#<step>` in addition to anchors — extend the show-me handler in coach.js.
- Progress: `learn.progress.record("scenario:<key>", {state, step_index, mode…})` — same kept
  model, key namespaced like missions. Event kinds: scenario_start/step/complete/abandon + mode.

### Tour port + pb_coach retirement
- Port the 6 pb_coach tours (hero_path, tour_formula, tour_payrun, tour_payslips, 2× in
  tour_engine_tools) into SCENARIOS in author data.js — Watch(+Do where meaningful) modes,
  anchors verbatim (they already exist in product templates: dash-hero/dash-kpis/
  dash-runpayroll/dash-formula, pw-*, fs-* ×14, payai-pill…). De-demo-flavour the copy: no
  "your 12 division configs", no June-specific claims outside {{live:*}}-fallback pattern;
  provisional VI alongside EN (Phase 2 audits all copy anyway). hero_path becomes
  `sc_welcome` — the whole-product Watch used by first login and (later) the Phase 3 checklist.
- Delete the pb_coach module from the repo. Keep pb_learn's first_login.js reading the OLD
  localStorage keys (pb_coach_welcomed etc. — verified read-only compat, coach/first_login.js)
  so nobody is double-greeted after the live uninstall. Update pb_learn/tests/test_retirement.py
  to assert the repo state (module gone) instead of the co-existence seams it asserts today.
  PayAI's `_TOUR_TO_LESSON` (payroll_ai_engine.py:373-380) now maps old tour ids → scenario keys
  (or stays lesson-targeted where a lesson is the better landing — decide per entry, document).
- Live uninstall ritual (deploy phase, not this build): documented 2-step from
  PBLEARN_PHASE_C_HANDOVER.md:138-142 — -u the family, verify, THEN uninstall pb_coach module.

### Generator/validation additions
- SCENARIOS emitter → learn_content.json `scenarios[]`; validations: unique keys, every anchor
  present in anchors.json (any kind), guard rule above, modes ⊆ {watch,try,do}, every `screen`
  ∈ the 20 replica screens, every nav xmlid ∈ SCREEN_ACTION_TAGS map or explicitly allowlisted,
  input steps only in try-capable contexts, every B() pair has both languages.
- contract.json: new checks — "guarded-steps-never-autoclick" (grep the engine),
  "scenario-anchors-exist", "watch-mode-never-clicks-guarded".

## Non-goals (binding)
- No copy rewrite beyond porting/de-demo-flavouring the 6 tours. No new replica screens
  (Phase 5). No AI changes (Phase 4). No checklist (Phase 3). No deploy, no commit.

## Tests (numbered — finalize after 1a; expected set)
1. Generator + `--check` + contract checker + parity of untouched sections green.
2. `node --check` all new JS; py_compile all changed py.
3. Generator validation negative tests: a guarded-less compute step, a bogus anchor, an
   unknown screen each FAIL the generator (add author/tools test fixtures).
4. Grep-proofs: repo contains no `pb_coach/` directory; no `pb_coach` references outside
   first_login.js compat comments + handover docs; overlay never calls `.click()` on a guarded
   step (structural: the guard branch has no click call).
5. Anchor audit: every scenario step anchor exists in anchors.json; every foreign anchor listed
   there still exists in the owning module's templates (extend test_anchor_registry).
6. test_retirement.py rewritten and logically green (flag runtime-only assertions for deploy).
7. Report which show_me intents were upgraded to scenario targets.

## Report back
Per-file summary; schema deviations; the six ported scenarios' step counts + guard placements;
PayAI mapping decisions; VI provisional-copy list for Phase 2 audit; ledger candidates.

## Kickoff
"Implement docs/handovers/LEARNOS_PHASE1B_HANDOVER.md exactly. Read it, both ledgers, and the
accepted Phase 1a report first. Local-only; no deploy, no commit; leave the tree for review."
