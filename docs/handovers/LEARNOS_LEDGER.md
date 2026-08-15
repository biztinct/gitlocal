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
- (Phase 1 deploy, DONE 2026-08-15) Family deployed to all 4 DBs EXIT=0; learner keys
  carried; pb_coach uninstalled everywhere (it was installed on ALL 4 — the "template
  excluded it" memory claim was WRONG); orphan learn_* tables remain (inert, rollback path);
  two-world Chrome validation PASSED end-to-end after two mid-run fixes (a814dde5).
- (Phase 1 validation) **`t-out` renders a plain string as TEXT — every OWL raw-HTML surface
  owes a `markup()` wrapper.** scenario_overlay + live_mission shipped without it: cards
  painted their own escaped source and had NO working buttons. Any new t-out needs the
  markup() getter pattern (coach/journey/scenario/live all conform now).
- (Phase 1 validation) **Bind keydown on `document`, never `window`** — Odoo's hotkey
  service stops propagation before window-bubble, so a window listener is silently dead.
  Candidate contract check: no `window.addEventListener("keydown"` in pb_learn.
- (Phase 1 validation, URGENT PRODUCT FIX 2026-08-15) **A DB `latest_version` AHEAD of the
  disk manifest is a silent rollback `-u` will never repair.** Live pb_payrun_wizard disk was
  19.0.1.0.0 (approval-tier bypass bug) while DBs recorded 19.0.1.1.1 — a stale rsync had
  reverted the Phase-L fix. Restored + `-u pb_payruns` (landed the 2 withheld kanban-view
  anchors) on all 4 DBs. Deploy ritual gains a step: version-diff EVERY pb_* manifest on
  disk vs `ir_module_module.latest_version` before finishing.
- (Phase 1 validation → Phase 4 scope) Corpus gap: no intent answers "How do I run payroll";
  screenless ask() weak-matches wrong-topic intents and badges them "Grounded in" — a badged
  wrong answer is worse than a miss. Both are Phase 4 scope items.
- (Phase 1 validation) A golden-template clone cannot exercise the missing-module Journey
  branch (it has everything installed) — that path needs a deliberately-lean tenant to test.
- (Phase 2 review) **"Escape at the substitution point" was the WRONG seam when most call
  sites already escape** — tokenValue() escaping double-escaped ~407 esc(tx()) sites
  ("Trần & Sons" → "&amp;amp;"). The trust boundary belongs at the RAW-insertion helper
  (gtx), not inside tx(). A spec bug: the handover's own wording produced it.
- (Phase 2 review) **A glossary gate must check BOTH directions.** term→entry-exists was
  gated; alias→wraps-only-what-it-means was not, so bare aliases ("kỳ" inside "bất kỳ",
  "đang chờ", "run") hung wrong-topic hovercards on 100+ bodies. Rule: single-word aliases
  forbidden unless allowlisted with a reason; glossify the corpus at generate time as a lint.
- (Phase 2 review, ruled) `cấp` (not `vòng`) is the tier word in VI everywhere; DEMO_RETAIL_MID
  deletion from glossary.configCode ACCEPTED (shape+real END codes retained; MID taught in
  whichconfig); the 17-28-word warning band did NOT shrink (23.8% vs 24.2%) — only the >28
  tail was removed; honest follow-up target, not a claim of overall simplification.
- (Phase 2 review → Phase 4 scope) Composer corpus: glossary grew past _CORPUS_CAP (12k) and
  is appended last — new terms never reach the composer. Fix ordering/cap in Phase 4.
- (Phase 2 fix round) **A claimed clean sweep is not one until a gate says so** — the
  vòng→cấp sweep left one tier-sense survivor and one blind-replace nonsense string, both
  caught only by re-review. `jargon.py` now has `VI_RESTRICTED` (a VI term legal only inside
  listed compounds) with an executed negative control; extend it instead of trusting seds.
- (Phase 2) Display term ≠ match phrase (`matchTerm: {vi: false}` — "Nháp" is the right
  label and the wrong matcher). Vietnamese is written in syllables: single-word VI aliases
  are presumed wrong (BARE_ALIASES allowlist, reason required). Escaping is a property of
  the POSITION, not the value — the one raw-insertion wrapper is `gtx()`, and "are all raw
  positions covered" is the grep for `${tx(`/`${T(` returning nothing.
- (Phase 3 review, BLOCKER fixed) **A currency change is refused by Odoo once journal items
  exist** — bundling `currency_id` into the provisioning rename write turns that refusal into
  a configure-step abort. It now has its OWN write, guarded by `_existing_accounting()` (the
  chart_template.py idiom), and swallows its own failure with a logged skip. DEPLOY CHECK:
  `select count(*) from account_move_line` on payobook_template — non-zero means tenant
  currencies stay USD (logged), zero means the fix applies cleanly.
- (Phase 3 review, fixed) The AST registry-guard must match `self.env[...]`/`x.env[...]` AND
  treat non-constant subscripts as unguarded-unknown — the Name-only version was defeated by
  the two most ordinary Odoo idioms. Reusable form: `_guarded_env_reads` in
  pb_dashboard/tests/test_activation.py.
- (Phase 3 review, fixed) **"Is this the demo WORLD" is a database fact = a search over
  res.company; `env.company` is the ACTIVE company, a session fact** — the session probe
  welcomed an apex admin switched to company 2 as a new tenant. `learn.live.world_is_demo()`
  now counts companies by the declared name.
- (Phase 3) Checklist rules: a step whose predicate lives in a missing module is HIDDEN, not
  shown forever-unticked; `'show': not runs` is source-pinned (a True slip would ship the
  checklist to every veteran tenant); `hr.payslip.run` has NO company_id in this codebase —
  any per-company runs domain raises. Replay harness is now addon-generic; a setUp that
  breaks for any reason other than NeedsDB reports FAIL, never SKIP. 7th
  absent-token-in-own-prose occurrence (test_welcome test_10 `min(`) — strip comments first.
- (Phase 2+3 deploy, DONE 2026-08-15) LIVE on all 4 DBs: 198 staging tests 0-fail, 12/12
  Chrome checks (checklist lifecycle, welcome card, hovercards, VI, world_is_demo company-2
  proof). **2nd silent-rollback caught by the version-diff gate: pb_sidebar disk was stale
  (collapse/pin dead on live; a future -u would have DELETED sidebar entries)** — restored
  from git + -u'd. Gate stays. A code change WITHOUT a version bump is invisible to that
  gate — bump on every deployable change.
- (Phase 2+3 deploy) **"document, not window" is necessary but NOT sufficient for keydown:
  Odoo's hotkey service stops propagation at document-bubble, so the listener must be
  CAPTURE phase** — the welcome card's Escape was silently dead in real Chrome while
  synthetic dispatch worked. And a transient layer that closes on a key SWALLOWS that key
  (stopPropagation), else one Escape closes the hovercard and exits the lesson. Both fixed
  post-deploy (ride next family deploy).
- (Phase 2+3 deploy) `post_install` tests run ONLY for modules named in the same `-u` —
  a test-tag run must name every module under test. `fs.protected_regular=2` blocks the
  root-append /tmp sentinel pattern — use /var/log/<dir> owned dirs. `{en,vi}` is a SHAPE,
  not a meaning: any walker that assumes prose must prove what it skipped (test_04c pattern).
- (Deploy backlog, out of LEARNOS scope) Local-ahead-never-deployed modules: pb_demo 1.5.0,
  pb_pay_delivery 1.0.2, pb_demo_portal, pb_website. Pre-existing UI bug: Timecards empty
  state renders literal `_t("With hours only")`.
- (Phase 4) **The first provider call is the one nobody audits** — every redaction control
  sat in the handler while `_classify_intent` sent the raw question one call earlier. Audit
  the CALL ORDER, not the handler. A guard applied to one tier of a scale and not its
  neighbour is not applied (ambiguous filter now covers both overlap tiers). A tie at the
  acceptance boundary is a coin toss wearing a badge — tie-at-floor is a miss.
- (Phase 4) **Fixing a dead provider call is switching ON an egress path** — payroll_ai_report's
  two get_provider_instance sites stay dead, pinned by an exact-count test, until Phase 6
  pairs the repair with redaction. Redaction residuals are STATED in ai_redaction.py's
  module docstring (history prior-turn names, raw current-message on 3 paths, dict keys,
  bare 7-8 digit amounts, mixed-diacritic partials) — an unstated residual is a lie of
  omission.
- (Phase 4) A structural check that greps literals or offsets survives a conditional
  wrapper — fail-open is worse than absent. The AST-parent walk (test_explain::test_02a:
  refuse any If/IfExp/BoolOp ancestor naming the flag) is the reusable form. A probe that
  would pass anyway is a line, not a test: every must-miss probe carries the score it
  reaches with its rule disabled, verified by executing the control.
- (Phase 4) global_suggest overflow is now generator exit 9 naming the casualty. 9th
  absent-token occurrence (docstring naming get_provider_instance). pb_learn manifest
  19.0.10.0.0 (new transient model). PRODUCT TICKET: Pay Runs kanban still offers Bank
  file + Email where the cockpit offers Pay & Deliver.
- (Phase 2, accepted nits for later touch) live_mission.js still `esc(tx())` on step.detail
  (no glossary cards, literal <b> tags there); glossify idempotence guard keys on the
  literal `data-gloss=`; gloss_scan payload ignores matchTerm (over-fails only); the 17-28
  word warning band is unchanged (~24%) — only the >28 tail was removed.
