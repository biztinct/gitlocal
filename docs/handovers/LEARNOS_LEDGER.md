# LEARNOS program — shared conventions & gotcha ledger

Program: next-gen Learning OS (Tours + Coach + Lessons v-next, DB-independent) + AI companion.
Plan of record: `~/.claude/plans/i-did-not-complete-lively-kernighan.md` (Option C, B-platform-first).
Cycle: Fable designs handover → Opus implements → independent review subagent verifies (never
trust implementer QA) → Fable rules → commit → next phase.

**Inherits ALL rules from `docs/handovers/PBLEARN_LEDGER.md`** (generated-files-never-hand-edited,
"a KPI tile is a query — read the method not the caption", "a convention broken three times is a
missing test", contract checker discipline, anchor registry discipline). Read that file first.

## Program-specific rules

1. **Honest zeros.** No surface may ever show fabricated numbers on a real (non-demo) DB. Sample
   data is allowed ONLY when `pb_demo` is installed, and must be visibly labelled. An empty tenant
   shows zeros + a helpful empty state, never fiction. (Root incident: `hr_analytics_dashboard.py`
   `_compute_dashboard_stats` sample_data dict leaked into abm.payobook.com's dashboard through the
   `pb_dashboard.py:78-85` fallback.)
2. **Content never in the DB** (from Phase 1 on). Learning content ships as static generated
   JS/JSON assets. The only learning DB tables are progress/event/confidence/consent/question +
   the 8 tenant fact slots.
3. **Privacy rails are copy-paste, not re-invention.** Any LLM egress uses pb_learn's tested
   vocabulary: scrub-before-egress (`learn_intent.py:731`), corpus-is-our-own-content,
   flag-off-by-default, refuse-rather-than-guess, badge composed answers, action-whitelist
   envelope (`payroll_ai_engine.py:356-405`). Never inherit PayAI's unscrubbed paths
   (`payroll_ai_engine.py:243`, `payroll_ai_pulse.py:196,211`).
4. **Every phase validates on TWO worlds:** the apex demo (data-rich) AND an empty tenant
   (abm or a scratch clone of `payobook_template`). A feature that only works with data is a bug.
5. **Deploy ritual** per memory `payobook-deploy`: rsync → stop → detached `-u` unit with sentinel
   → check EXIT + log → start → Chrome-MCP verify live. Apex DB is `payobook`; template and every
   tenant DB get the same `-u` so future clones stay clean. Backup before schema-touching deploys.
6. **Commit per feature** with explicit file staging; reviewer-focused message; no push unless asked.
7. Language register (Phase 2 onward): short sentences, one idea each, ~grade-6 EN; VI updated in
   the same author-source edit, never machine-shipped without review.

## Gotchas hit during this program

- (2026-08-15, Phase 0 design) `pb_dashboard` `vnd()` hardcodes `₫` for every company; the
  Company-overview card hardcodes `ring(100)`; "Good afternoon" is hardcoded regardless of time.
  All three are honesty/localization bugs in the same family as the sample-data leak.
- (Phase 0, SHIPPED + reviewed) **A fresh tenant is never at zero headcount** — the golden
  template ships the admin's `hr_employee` id 1 (renamed per tenant); provisioning does NOT
  create it. Any "is this tenant empty" predicate must use contracts+slips+configs, never
  headcount.
- (Phase 0) Raw `cr.execute` behind `except Exception` MUST wrap in `cr.savepoint()` or a failed
  statement poisons the request transaction (InFailedSqlTransaction) and "zeros" never render.
  `pb_dashboard.py:56-77` still has the latent form (binding non-goal there; fix on next touch).
- (Phase 0, PRODUCT TICKET) The home-dashboard money KPIs require a line coded literally `GROSS`
  and categories `INSCO`/`COMP`. Apex company 2's formula-converted payslips have neither → 0₫
  shown for real payroll. The old fake fallback masked this. Nothing distinguishes
  "0 because empty" from "0 because codes don't match" — needs a real fix later.
- (Phase 0, polish backlog) Empty tenants still draw red `ring(0)` on Latest-pay-run + Formula
  cards (Phase 3 will replace this area). Tenant clones inherit the template's USD currency —
  pb_tenants backlog: set company currency from country at provisioning.
- (Phase 0, recurring #5) An absent-token grep-check gets defeated by the COMMENT explaining the
  removal — never restate banned literals in prose near them.
- (Phase 0) Two post-review fixes (savepoint wrapper, template-ships-admin-employee comment) are
  committed locally but NOT yet deployed — they ride the Phase 1-family deploy.
- (Phase 0, D1-convention ruling) Fable ruling: `_demo_world` via sudo'd `ir.module.module`
  state='installed' is ACCEPTED as the standard demo-world probe for non-pb_learn modules
  (more precise than model-presence through to-remove/to-upgrade states); pb_learn-internal
  code keeps the model-presence idiom.
- (Phase 1a) **A parity proof compares EMITTER to EMITTER over the same input, never new
  output to a committed old artifact** — the committed generated XMLs were STALE at HEAD
  (--check had not been run before the last content commit). `parity_check.py` executes the
  old generator out of git. **The pre-1a rev for `--rev` is `6add0cc2`** (last commit with the
  XML-emitting generator).
- (Phase 1a) Before deleting a model, grep the whole repo for `Many2one('<model>'` — a KEPT
  table pointing at a dropped one owes a pre-migration (learn_progress/learn_event did;
  `migrations/19.0.9.0.0/pre-migrate.py` carries keys before the tables go).
- (Phase 1a) An ORM `@api.constrains` deleted with its model must MOVE (to the generator/
  contract checks), not disappear — three mission/quiz invariants now assert over the emitted
  content, checked once per product instead of once per DB.
- (Phase 1a) Absent-token grep family, 6th occurrence: `open(` is a substring of `gate_open(`.
  Pin the tokens a reader would actually write (`file_open(`, `json.load`), never generic verbs.
- (Phase 1a) When a refactor would leave a contract checker with nothing to see, change the
  refactor, not the checker (learn.content stayed an AbstractModel so the model-scope corpus
  check stays honest). AbstractModel + orm.call is the established cockpit pattern (13 already).
- (Phase 1a) `content.version` hashes CONTENT ONLY — it no longer covers tenant-slot edits or
  company (the old `_bundle_version` did). Tokens ride bootstrap live, so nothing breaks; do
  not use `version` as a "anything the learner sees changed" digest.
- (Phase 1a) `_ambiguous_words`/`_contested_models` lost their ormcache with the records —
  fine at today's corpus size; re-cache (plain module dict keyed by content sha) if ask()
  latency ever matters.
- (Phase 1a, operational) Learning content refreshes on WORKER RESTART only (lru_cache over
  file_open) — every content redeploy must restart the service; the JSON is served
  unauthenticated by design (scanned clean: authored content + practice fixtures only).
- (Phase 1b) **A SAFETY RULE THAT HAS A DEFAULT IS A DECISION NOBODY MADE.** The first
  draft of the scenario emitter inferred `guard` from a verb list — compute, submit,
  approve… — which is the Phase-D deny-list mistake with different words: it protects
  against the verbs somebody thought of. The shipped rule is that `guard` is MANDATORY on
  every click step, true or false, and the verb list only refuses a `guard: false` that is
  obviously wrong. Write the PROPERTY (an author must decide), then test the examples
  against it.
- (Phase 1b) **"The engine will not do X" is worth nothing next to "the engine CANNOT do
  X", and the difference is testable.** The overlay has exactly ONE `.click()`, in one
  function, whose first statement re-asks the guard and the mode — and
  `test_scenario::test_02` parses the file and asserts that every `.click()` is inside that
  function. A branch-level guard is a guard checked once; both negative controls (moving the
  press out, removing the re-ask) were executed and each fails a contract check AND a test.
- (Phase 1b) **`check_contract.region()` could not scope to an ES-class method, and it
  failed OPEN.** `\n};` only ends a top-level object literal, so `within: "_enterStep"` ran
  to end-of-file and an `absent` check caught a call three methods away; worse, the probe
  order made the bare NAME a fallback, so the region started at the file's header paragraph
  and every `contains` expectation read as missing. Fixed with two JS-only stop patterns and
  a `\n    async NAME(` / `\n    NAME(` probe before the bare name. **A `within` that
  silently scopes to the wrong region is the most expensive kind of green.**
- (Phase 1b) **Deleting a module is a MANIFEST change in every module that depends on it.**
  `pb_payroll_ai_insights` still declared the retired module in `depends`; Odoo refuses to
  install a module whose dependency is missing, so the deletion and that one line are
  inseparable — the phase's "touch only the mapping" boundary could not be honoured
  literally. `test_retirement::test_02` now walks every `__manifest__.py` in the repo.
- (Phase 1b) **A registry's `foreign` block can outlive the module it names.** Five anchors
  were listed as SHARED with the retired module; with it gone the claim is about nobody, so
  the entries were dropped and `SHARED_WITH_PB_COACH` deleted rather than renamed. The
  wildcard exemptions (`fs-*`) stay, because pb_formula_studio is still there. Same ruling
  as Phase C review round 2: a set whose name has drifted from its contents is one nobody
  can reason about.
- (Phase 1b) **A `show_me` fragment must be a step KEY, never an index.** `scenario:x#3`
  keeps opening something after a walkthrough gains a step in the middle — just not the step
  the author meant, which is the kind of breakage nobody reports because the button still
  works. The generator refuses a fragment that names no step (exit 7).
- (Phase 1b) **The `state.lang` re-render bug has a THIRD site, found by looking rather than
  by being bitten.** The scenario overlay is a second component reading the non-reactive
  `RT.lang`; the fix is the same one journey.js and coach.js already carry — a reactive
  `lang` on the service, written by the Coach's toggle and read in `bodyHTML`. Any new
  surface in this module needs the same two lines.
- (Phase 1b) **A walkthrough that ends by vanishing reads as a crash.** `finish()` keeps the
  overlay `active` with `done` set and swaps in a closing card; `stop()` is what tears it
  down, and it logs `scenario_abandon` only when `done` was false — otherwise every
  completed run would also count as one somebody walked out of.
- (Phase 1b, committed) `docs/tutorial_poc/author/tools/replay_tests.py` — the ad-hoc
  harness from the Phase C review, now a tool. 43 source-level assertions execute on every
  verification pass; anything touching `self.env` reports SKIP, never a pass.
- (Phase 1a, deploy gate) The retargeted Odoo test suite and the pre-migration have NEVER
  executed — the Phase-1-family deploy MUST rehearse `-u pb_learn` on a staging clone of a
  real DB first and watch the pre-migrate log ("carried N … row(s)"; a dropped-rows WARNING
  means learner data loss).
