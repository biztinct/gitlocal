# LEARNREV P4 — lessons and walkthroughs beside the real screen (handover for Opus)

Program: `docs/handovers/learnrev/LEARNREV_PROGRAM.md` (standing rules verbatim there). Ledger: `LEARNREV_LEDGER.md`
(all rows; LR28 corrects the program doc: the generator MERGES vi_VN.po now, it no longer wipes it). Design page:
`docs/design/learn_revamp/LEARN_REVAMP_DESIGN.html` ("Walkthrough steps, before and after" and Option C's Understand
section). Gaps closed here: G3, G5, G17, G18, G19, G22, G23, G27, G29. P2 built the Guide panel (`P2_REPORT.md`),
P3 the Library (`P3_REPORT.md`); P1 the manifests the lessons now read from.

Work in the git worktree you are given (branch `learnrev-p4` from the 19.1 tip). No deploy in this phase.

## 0. Design bar (verbatim, binding)
"Extreme WOW, intuitive, out-of-this-world experience, best in class." Measured against Trailhead's checked
challenges and Apple's one-idea-per-tip, never a slide deck. **Hero moment:** on the real Component treatment board,
press Understand › "Start the lesson" in the Guide: the spotlight lands on the real "Pay role" header, and the panel
says **Look at** the amber cell on Loan Installment · **It means** the formulas could not tell whether it reaches
net pay · **It affects** run totals, the payslip and the bank file · **Press** the cell and choose Taken off net pay.
Nothing covers what it explains; one rail; no full screen. On the demo company, "Try" waits for you to actually do
it and checks the record, then moves on. **Zero dead ends:** a screen you cannot open plays on the practice copy with
a one-line note; a slow screen says "still loading" with Retry, never "no access"; a step whose control is not on
screen says what it is and moves on. Plain screen words, never the word "Odoo", EN+VI, Lucide only, motion with
purpose. Score every bullet 1–5 in the report.

## 1. Scope
- **S1 Step shape.** Lesson steps gain four bilingual fields: `look` (what to look at), `means` (what it means),
  `affects` (what it changes or feeds), `press` (what to press — optional, only on a real anchor). Legacy `body`
  stays allowed for steps not yet rewritten; a step with `look` must have `means` and `affects` (generator gate).
  **Field steps:** a step may carry `field: "<screen>.<manifest field key>"`; the generator then fills `means` from
  the field's one-line help and `affects` from its top three `used_by` labels + `if_changed` (truth by construction),
  leaving `look` and `press` authored. (Generator reads the manifests through a small exporter
  `tools/export_manifests.py` that runs the P1 offline gate's loader; both languages.)
- **S2 Lesson player v2 in the Guide.** When the Guide switch is on, the screen is reachable (`reachable()`,
  `places.js:198-208`) and the step's anchor is a product anchor (not `rep-*`), the lesson plays INSIDE the Guide
  panel's Understand section (docked or floating): the step card (kicker · title · the four lines · tip) replaces the
  section body; the spotlight (`engine/spotlight.js Spot.show`, global `[data-coach]` query) highlights the real
  control; Back / Next / Leave / step meter live at the bottom of the section; ← → keys as today; progress writes
  as today (`learn.progress.record`). Steps whose anchor is `rep-*` (48 of 295, table in the P4 facts) or whose
  screen is not reachable fall back to today's replica player in the Journey, opened at that step, with the note
  "This step shows the practice copy." The lesson's quiz plays in the panel too. Rename the spotlight's fold class
  from `lrn-docked` to `lrn-spot-docked` (`spotlight.js:218, 318`; `journey.scss:970`) — it collides with the Guide
  dock (`coach.js:2093/2095`, `guide.scss:471`, `field_info.js:247`, `scenario_overlay.js:459`).
- **S3 Watch from the Guide keeps the Guide.** `startScenario` (`coach.js:1711-1734`) no longer `close()`s the
  drawer; the overlay card already subtracts the dock (`scenario_overlay.js:446-497`). The Tasks section shows
  "Playing · step N of M" with Stop while a walkthrough runs.
- **S4 Try checked against real state on the demo company.** New server seam `learn.scenario.check(key, step_key)`
  (AbstractModel in pb_learn, no sudo, read-only; generalises `learn.live` predicates, `learn_live.py:192-257`): a
  manifest may declare `checks: {"<scenario>.<step>": "<model>.<method>"}`; the method returns `{ok, note{en,vi}}`.
  Try (demo world only: `bootstrap.demo_world`) then runs on the REAL screen: the person presses, the engine polls
  the check every 3 s (like `live_mission.js:148-155`) and advances on `ok`; the card says what is still missing.
  Implement checks for three scenarios: `sc_treatment` (fix step: the named rule's `net_role` is set and
  `net_role_source == 'user'`; recompute step: `learn_right_now` has no `recompute` item), `sc_payrun` (reuse
  `june_run_computed` / `june_run_submitted`), `sc_records` (one demo employee's bank field changed by the asker —
  scope by `write_uid == env.uid` and `is_demo`). Elsewhere (tenants, or no check declared) Try stays on the replica.
  "Do it" keeps its guard (`_awaitRealClick`) and gains the same checks where declared.
- **S5 Replica truth.** New gate in `guide_truth.py`: for every manifest screen with a replica in `engine/screens.js`,
  each manifest `column` appears in the replica's HTML and each replica table header appears in the manifest or the
  real template (either language). Fix the drift it finds — known: the treatment replica says Group / Subtotal and
  lacks Run signal (`screens.js:1926-1967`). (Generating replicas from definitions is NOT in scope — see §2.)
- **S6 Country-aware statutory.** Steps may carry `variants: {VN: {...}, generic: {...}, ID: {...}, IN: {...},
  SG: {...}}` for `look/means/affects/press/tip`; the client picks by the active company's country
  (`res.company.country_id.code`, sent in `bootstrap` as `country`; the active scheme's `country_code` wins when a
  Mapping/Studio screen is open with a scheme), falling back to `generic`. Rewrite the VN-only steps of L6 (statutory,
  6 steps + quiz), L5 (formula, 6), L3 (payslips, 3), L1 (runpayroll, 2), L31 (1) with a `generic` variant (plain:
  "your country's insurance and tax", "the employee's share", "the tax table") and, where the country pack has the
  term, ID / IN / SG variants using the pack item labels (`pb_pack_id` BPJS JHT/JP/JKK/JKM/Kesehatan, PTKP;
  `pb_pack_in` EPF, ESI, PT, standard deduction; `pb_pack_sg` CPF OW ceiling, EE/ER by age band, SDL). The replica
  statutory screen (`screens.js:1559-1664`) and `active_policy_rates` (`learn_live.py:275-308`) stay VN (they are
  demo fixtures) but the step text no longer assumes them outside VN. The Statutory cockpit's non-VN rendering
  (`pb_statutory.py:116-299`: no policy → "No active insurance policy.", no `st-rates`/`st-effective` anchors) is
  handled by the fallback in S2 (anchor absent → the card explains and moves on, never "no access").
- **S7 Rewrite the lessons of the eight manifest screens** in the new shape, one idea a step, field steps where a
  step is about a column: L9 treatment, L1 runpayroll, L2 payruns, L3 payslips, LA approvals, LW + L35 dashboard /
  Insights › Pulse, L5 formula, L10 mapping (+ any lesson whose station is one of the 8 screens — list them in the
  report). Each rewritten step ≤ 28 English words per sentence (generator gate), EN+VI, no retired labels (gate),
  `press` only where a real anchor exists. Quizzes kept. The remaining 32 lessons keep `body` and still play in the
  panel (S2 handles legacy steps by showing `body` as the "It means" line).
- **S8 Walkthroughs of the same eight screens** (`sc_treatment`, `sc_payrun`, `sc_payslips`, `sc_formula`,
  `sc_mapjourney`, `sc_records`, + approvals/dashboard if a scenario exists) rewritten one field a step in the four-line
  shape (scenario steps gain the same four fields; `body` legacy allowed), with `press` on click steps.
- **S9 Failure wording (G23).** `navigateOnce` timeout (`scenario_service.js:209-244`) → "The screen is still
  loading" + Retry, reserved "You can't open this screen" for `reachable() === false` only; the board's `.pct-empty`
  error class added to `REFUSAL_BOXES` (`scenario_overlay.js:70-82`) so a real refusal ends the walkthrough with its
  reason; "That control is not on this screen right now" keeps its explanation but advances automatically after 4 s
  in Watch.
- **S10 Learn header + pill (P3 leftovers).** The shared Learn bar reads "Learn" (not "Payobook · Learning"); on the
  Library the floating Ask PayAI pill is hidden while the Guide host exists (the Guide's Ask is the entry) — or space
  is reserved per row; pick the former.

## 2. Binding non-goals
No replica generation engine (owner decision stands: tenants use replicas; P4 makes them truthful via the gate, P5
may generate them); no change to PayAI, the router, the Library layout, the manifests' field content (checks and
variants are additive), no new stored fields except none (progress stays `learn.progress`), no sudo, no deploy.
Lessons outside the eight screens are not rewritten in P4 (P5).

## 3. Verified plumbing (do not re-derive)
- Lesson render: `journey.js:909-937 _lessonBody`, `:941-962 _coachCardHTML`, `:1336-1355 _afterPaint`,
  `startLesson` :1942-1956, `next/back/replay/exitLesson` :1958-1996, quiz :965-1006 / :1998-2031, progress
  `_saveProgress` :530-538; keys `_onKey` :1806-1819. Replica shell `screens.js:3216-3292`. Spotlight
  `spotlight.js:138-204` (show), `:257-307` (placement: right → left → below → above, card `min(372, W-32)`),
  `DOCK_BELOW = 900` :101, fold `:218`, hide `:318`.
- Step gating: `content_loader.js:125-160`; server mirror `learn_runtime.py:84-117`; features `:642-676`.
- Generator: lessons `gen_learn_data.py:627-681`, morph lines `:573-598`, scenarios `:1295-1536` (modes, guard,
  input rules), gates table in the P4 facts (jargon `jargon.py:30,55-56,774-945`; 28-word limit), `--check`
  `:1859-1867`, `Trans.merge` `:258-303`.
- Scenario engine: `scenario_service.js:74-81 playableSteps`, `:307-352 begin`, `:193-244 navigate/navigateOnce`;
  overlay `_enterStep` `:339-354`, `_awaitRealClick` `:520-535`, `_watchAutoClick` `:561-580`, `_waitFor`
  `:412-443`, `REFUSAL_BOXES` `:70-82`, placement `:446-497`; Try in Journey `_scenarioClick` `:1405-1453`,
  `_scenarioInputCheck` `:1466-1493`, `input_match.js:83-92`.
- Live checks precedent: `live_mission.js:148-188` (poll + `learn.live.live_check`), `learn_live.py:131-207,
  252-257, 383-427` (predicates, read-only contract, `_my_june_run` scoping by `create_uid`).
- Guide: `coach.js` (P2) Understand/Tasks sections, `_watchStep` `:1958-1973`, `startScenario` `:1711-1734`;
  `learn_guide._doors` `:548-565`.
- Country: `res.company.country_id`, `hr.formula.config.country_code` (`formula_config.py:116-125`); packs
  `pb_pack_id/in/sg/vn` items; Statutory cockpit `pb_statutory.py:116-299`.
- Progress model `learn_progress.py:46-137` (`record` whitelists fields; undeclared keys refused).
- Replica anchors `_replica_anchors()` `gen:1213-1242`; practice-only steps list in the P4 facts (48 steps).
- Replay/offline: `replay_tests.py` baseline 238/3; `BRIDGE_METHODS` lifts `_scenarioClick`, `_scenarioInputCheck`
  by name — keep those method names.

## 4. Tests
- **T1 generator gates**: a `look` step without `means`/`affects` fails; `press` on a `rep-*` or unknown anchor fails;
  a `field:` reference to a non-manifest field fails; variants must carry `generic` when any country variant exists;
  every rewritten lesson passes the 28-word and jargon gates; `--check` up to date after regeneration.
- **T2 node (`pb_learn/tests/js/lesson_panel.test.mjs`)**: the panel player renders the four lines, legacy `body` as
  "It means", kicker/title/tip; `placeFor(step)` decision table (reachable + product anchor → panel; `rep-*` → replica;
  unreachable → replica + note); country pick (`VN`, `ID`, unknown → generic; scheme country wins); the spotlight
  never overlaps its anchor rect (pure placement function with 6 geometries incl. a top-of-page headline).
- **T3 Python** `test_learnrev_p4.py`: `learn.scenario.check` for the three scenarios on the demo fixture (not ok →
  do the change → ok; another user's change does not count); `bootstrap.country`; replica-truth gate 0 errors after
  the treatment replica fix (and fails on a synthetic drift); `REFUSAL_BOXES` includes `.pct-empty` (source test);
  `startScenario` no longer closes the drawer (source test); `lrn-docked` not referenced by spotlight.js.
- **T4** truth gate 0 errors; anchors registry green; P2 117/117 and P3 103/103 node suites still green; PayAI node
  suites green; `replay_tests.py` ≥ 238 pass with no new failure; `check_contract.py` only `grid-hint`.
- Existing pb_learn suite on a dump clone (AI off; LR17/LR26); baselines test_07b, TestCoach.test_11 with AI on.

## 5. Browser checks (clone on 8093, Guide ON, demo world; headless Chrome 9561; QA login via fetch)
B1 Component treatment → Guide › Understand › Start the lesson: step 1 card in the panel, spotlight on the real
header, nothing covering the headline; B2 a field step shows Look at / It means / It affects / Press with the real
"Used by" names; B3 Try `sc_treatment` on the demo scheme: card waits, set Loan Installment's Pay role and Save → the
step advances by itself with the check's note; B4 a `rep-*` step (e.g. L9 step 3) → falls back to the replica player
at that step with the note, Back returns; B5 Watch from the Guide: drawer stays open, overlay card beside the dock;
B6 switch the QA user's company country to ID on the clone (res.company write, restore after) → L6 step 1 shows the ID
variant (BPJS), unknown country → generic; B7 a slow screen (throttle via CDP) → "still loading" + Retry, not "no
access"; B8 Vietnamese for B1–B3; B9 the Library header reads "Learn" and no pill floats over rows; B10 the quiz plays
in the panel and completes the station (progress done); B11 console clean. Screenshots `p4_b*.png`.

## 6. Commits, report
Worktree branch `learnrev-p4`. Commits: (1) generator step shape + field steps + exporter + gates, (2) panel player +
spotlight class rename + fallback, (3) Watch keeps the Guide + failure wording, (4) checks seam + three scenarios,
(5) replica truth gate + treatment replica fix, (6) country variants + statutory lessons, (7) the eight screens'
lessons and walkthroughs rewritten + regeneration, (8) Learn header/pill, (9) tests + report. Explicit paths;
`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; no version bumps; no push. `P4_REPORT.md`: scope table,
the list of rewritten lessons/scenarios with step counts before/after, T1–T4, B1–B11 with screenshots, design-bar
score, LR rows (after LR52 + any P3-deploy rows), open items.
