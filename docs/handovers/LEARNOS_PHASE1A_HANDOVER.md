# LEARNOS Phase 1a — Static content plane (content leaves the database)

Read `docs/handovers/LEARNOS_LEDGER.md` + `docs/handovers/PBLEARN_LEDGER.md` first.
Scope: pb_learn + docs/tutorial_poc/author only. Do NOT touch pb_dashboard, pb_hr_payroll_analytics
(another phase owns them), pb_coach, pb_demo, PayAI. NO deploy in this phase — local build +
local verification only; deploy happens after Phase 1b. Do not commit.

## Why
Learning content must be identical on an empty tenant, the demo, and the apex, with zero DB
dependency and zero corruption risk. Today content ships as generated `pb_learn/data/*.xml`
records. This phase makes the SAME author pipeline emit one static bilingual JSON asset, makes
the client and the server ask()-resolver read it, and deletes the content models.

## Verified plumbing facts — do NOT re-derive (all verified 2026-08-15)

### Server payloads today
- `learn.station.get_bundle()` (`pb_learn/models/learn_station.py:282-321`): returns
  `{stations[] (with lessons/steps/lines/quizzes nested), missions[], glossary[], chrome{},
  version, tokens{}, progress{}, confidence{}, user{}}`. Bilingual packing: `_content_tree()`
  read twice (en_US / vi_VN) and zipped by `_zip_bilingual` (`learn_station.py:20-72`), string
  leaves → `{en,vi}` unless key ∈ `_RAW_KEYS` (:20-42); chrome zipped by `_zip_prose` (:67-72).
  Cached `@tools.ormcache()` on `_content_bundle` (:227). Runtime-only keys:
  `stations[].visible/missing` (from `_visible_sidebar_item_ids()` :262-280), `tokens`
  (learn.tenant.override `resolved_tokens()`), `progress`, `confidence`, `user`, `version`.
- `learn.intent.coach_bundle()` (`learn_intent.py:934-978`): `{screens[], global_suggest[],
  tokens, chrome, collect_questions}`. Runtime-dependent parts: `action_tags/action_xmlids/
  models` from `_matchers()` :349-374 (reads live sidebar leaves), `own_tag/own_xmlid` from
  `_primary()`, `_contested_models()` :290-327, `next_step` via `_next_step_live()` :264-274
  ({{live:*}} resolution). Static parts: key, name, blurb, suggest, global_suggest.
- `learn.intent.ask(question, screen_key|null, lang)` (`learn_intent.py:642-699`): hit shape
  `{matched, key, label:P, simpler, blocks[], capability, show_me[], practice_key, source_kind?}`;
  zero-blocks hit downgraded to miss (:680); capability gate :543-588 reads real payroll groups
  (MUST stay server-side); composer :811 (flag-gated, corpus `_corpus()` :773-808 reads learn.*
  tables, cap 12000); scrub `_scrub` :731; resolver ambiguity `_ambiguous_words()`.

### Client RPC inventory (complete, grep-verified)
1. `learn.station.get_bundle []` — journey.js:153, live_mission.js:85
2. `learn.intent.coach_bundle []` — coach.js:92, live_mission.js:89
3. `learn.intent.ask [q, screen, lang]` — coach.js:216
4. `learn.progress.record [key, values]` — journey.js:229, live_mission.js:200
5. `learn.event.log [kind] + kwargs` — journey.js:238, coach.js:333
6. `learn.confidence.award [key, recovered]` — journey.js:1138, live_mission.js:202
7. `learn.mission.live_check [mission, step]` — live_mission.js:151 (10s poll)
8-11. `learn.consent.questions_state/should_ask_questions/set_questions`, `learn.question.record` — coach.js
Content-bearing calls are ONLY #1 #2 #3. Everything else is learner-state and stays untouched.
- journey.js consumes the bundle at `_loadBundle()` :151-170 (sets RT.tokens :158, RT.chrome :159,
  this.progress, this.visible Set :161, lang :165-168). coach.js at :92-94. live_mission.js :85-89.
- `tx()` in `engine/runtime.js:60-66` is the single choke point interpolating `{{slot}}` tokens;
  `T(key)` :70-73 reads `RT.chrome`, falls back to the key itself.

### Generator (docs/tutorial_poc/author/tools/gen_learn_data.py, 979 lines)
- `dump()` :877 shells `node tools/dump_content.js` (loads practice-data.js then data.js in a VM,
  emits one JSON tree). `main()` :884 builds `files{}` → validates → writes; `--check` exits 1 on drift.
- ALL record emission flows through `Xml.rec(model, xmlid, [(field, value),…])` :268-284 — single
  sink, 22 call sites. EN goes to rec(); VI goes to the parallel `Trans.add(model, field, xmlid,
  en, vi)` :126 (joined by ref tuple :132; dedup + conflict check :139-141). So at every emission
  site the generator HOLDS BOTH LANGUAGES — emit `{en,vi}` pairs by construction.
- Emission targets today: data/learn_{strings,glossary,tenant_slots,stations,lessons,intents,
  screens,columns,missions,sidebar_item}.xml, i18n/vi_VN.po, static/src/engine/fixture.js
  (verbatim concat :833), static/src/anchors.json (surgical `practice` block only :861).
- Validations to preserve: XML well-formedness :909-918 (retarget), Live token/fallback :920-926,
  untranslated check :928-935, conflict check :937-942, SIDEBAR_KEYS/SCREEN_ACTION_TAGS maps :69-109.
- data.js top-level consts: I18N, GLOSSARY, STATIONS (6 lines), MORPHS, LESSONS (L1..L6,LA,LW),
  MISSIONS, MISSION_STEPS, SCREEN_CTX (20), QA (intents), COLUMNS, PRACTICE_ANCHORS, SIDEBAR.

### Manifest (pb_learn/__manifest__.py)
- data list :57-84 (order-significant; intents before screens; sidebar_item after actions).
- assets :86-109 `web.assets_backend` only; `engine/*.js` glob; anchors.json NOT bundled.

## Target architecture

### One generated artifact, two consumers
- Generator emits **`pb_learn/static/content/learn_content.json`**: pretty-printed, sorted-keys,
  banner key `"__generated__"`. Structure:
  `{version: "<sha1[:12] of the tree>", stations[], missions[], glossary[], chrome{},
  screens_static[] (key, sidebar_key, name:P, blurb:P, suggest[], offer/global flags),
  intents[] (full QA corpus: key, phrases[], label:P, simpler:P, blocks[], capability, show_me[],
  practice_key, screens), columns[], strings→ fold into chrome as today}`.
  Every prose leaf is `{en,vi}` BY CONSTRUCTION (both languages are in hand at each emission
  site — see generator facts). Keep `''` for empty-EN leaves (existing convention). RAW keys
  stay raw scalars exactly as `_RAW_KEYS` does today; you are reproducing the CURRENT payload
  shape so the frontend views keep working — divergences must be zero.
- **Client**: new `pb_learn/static/src/content/content_loader.js` — module-level
  `loadContent(): Promise<tree>` doing `fetch('/pb_learn/static/content/learn_content.json')`
  once (memoized). Journey/coach/live_mission compose their old bundle shapes from
  (a) the static tree + (b) ONE new runtime RPC (below), so downstream view code is unchanged
  except `_loadBundle`-style seams.
- **Server**: new AbstractModel `learn.runtime` (`pb_learn/models/learn_runtime.py`) with
  `bootstrap()` returning ONLY the irreducibly-runtime keys:
  `{visible_stations: {key: {visible, missing}}, tokens, progress, confidence, user,
  screens_runtime: {key: {action_tags, action_xmlids, models, own_tag, own_xmlid, next_step:P}},
  collect_questions}`. Reuse the existing implementations by moving/calling the current helper
  methods (`_visible_sidebar_item_ids`, `_matchers`, `_contested_models`, `_primary`,
  `_next_step_live`, progress/confidence reads). These helpers currently read content MODELS for
  the screen list — retarget them to the JSON tree (server-side loader below). Station
  visible/missing needs each station's `sidebar_key`/`kind` — from the JSON.
- **Server-side content access**: `pb_learn/models/learn_content.py` — plain helper (not a model
  or an AbstractModel with no fields, your call) exposing `content_tree()` via
  `odoo.tools.file_open('pb_learn/static/content/learn_content.json')`, parsed once per process
  (functools.lru_cache keyed on file mtime or module version — simplest: lru_cache() and accept
  restart-to-refresh, note it in the file header; the generator always ships with a code deploy).
- **ask() goes file-backed**: rewrite `learn.intent.ask` + resolver + `_corpus` to read the JSON
  tree instead of ORM records. The PUBLIC CONTRACT of ask() (shapes above, including
  zero-blocks→miss downgrade, capability gate, scrub, advice deny-list, composer flag,
  source_kind badging) MUST NOT CHANGE — coach.js is untouched for ask. Port
  `_ambiguous_words()` to compute from the JSON corpus. `learn.mission.live_check`/`learn.live`
  stay as-is except any content-record reads retarget to JSON (missions' check_key/steps come
  from the tree).

### Deletions
- Content models: learn.station, learn.station.mistake, learn.lesson, learn.step,
  learn.step.line, learn.quiz(+option), learn.mission(+step/option/note — KEEP the
  `learn.mission` AbstractModel-hosted `live_check`? No: move `live_check` + `award`-adjacent
  logic: `learn.confidence` is a separate kept model; move `live_check` onto `learn.live` or a
  slim kept `learn.mission.runtime` AbstractModel — pick one, document it, update
  live_mission.js call site accordingly), learn.intent(+phrase/block/step), learn.screen,
  learn.column, learn.string, learn.glossary.term.
  KEEP: learn.progress, learn.event, learn.confidence, learn.consent, learn.question,
  learn.tenant.override, learn.live.
- Generated data XMLs for deleted models + their ir.model.access.csv lines + author/content
  views + "Content" menus (`views/learn_content_views.xml`, content parts of learn_menus.xml).
  KEEP: security groups + record rules for kept models, learn_question_cron.xml,
  learn_tenant_slots.xml + override views/menu ("Training wording"), learn_actions.xml,
  learn_sidebar_item.xml (still generated), i18n/ — the .po now only needs entries for kept
  server-emitted strings (refusals etc. in learn_question/learn_intent python `_()` calls);
  the generator DROPS content msgids from the .po (chrome/content ship bilingual in JSON).
- `learn.intent.ask`'s composer corpus cap, flags, scrub: unchanged behaviour, new data source.

### Author-tool updates
- `gen_learn_data.py`: new emitter class (subclass/parallel of `Xml`) that appends records to a
  python tree and renders JSON; `rec()` call sites change to pass `(field, en, vi)` triples (or
  rec() consults Trans by ref — pick the cleaner; prefer explicit triples). Old XML targets for
  deleted models are REMOVED from `files{}`; `--check` covers the JSON.
- `tools/check_contract.py` + `contract.json`: retarget greps/refs that point at
  `pb_learn/data/*.xml` or deleted model code to the JSON/new code paths. Every contract id must
  still be checked or consciously retired with a note in the phase report (list each).
- `tools/simulate_resolver.py`: retarget to the file-backed resolver; must stay green.

## Non-goals (binding)
- No behaviour change visible to a learner (identical Journey/Coach rendering, identical ask()).
- No scenario engine, no Watch/Try/Do (Phase 1b). No copy changes (Phase 2). No pb_coach changes.
- No new pip/npm deps. No deploy, no commit, no server access this phase.

## Tests (numbered — report each)
1. `python3 docs/tutorial_poc/author/tools/gen_learn_data.py` runs clean; `--check` green on rerun.
2. **Parity proof**: write `docs/tutorial_poc/author/tools/parity_check.py` (committed, reusable):
   builds the OLD content payload shape from git-HEAD generated XMLs (parse the XML records
   directly — no Odoo needed) and the NEW one from learn_content.json, and diffs every prose
   leaf (en+vi) and raw scalar for stations/lessons/steps/quizzes/missions/glossary/chrome/
   intents/screens/columns. Zero diffs allowed except a documented allowlist (e.g. ordering).
   Paste the summary line into the report.
3. `python3 docs/tutorial_poc/author/tools/check_contract.py` green; list retargeted/retired ids.
4. `python3 docs/tutorial_poc/author/tools/simulate_resolver.py` green (file-backed).
5. `python3 -m py_compile` every changed/added .py; `node --check` every changed/added .js;
   `python3 -c "import json;json.load(open('pb_learn/static/content/learn_content.json'))"`.
6. Grep-proofs: no `get_bundle`/`coach_bundle` calls remain in JS (replaced by loader+bootstrap);
   no ORM access to any deleted model anywhere in pb_learn python; no `data/learn_stations.xml`
   (etc.) in the manifest; `_RAW_KEYS`/`_zip_bilingual` deleted or reduced to a comment pointing
   at the generator.
7. Unit-test files updated: `pb_learn/tests/` — update test_anchor_registry/test_assets/
   test_composer/test_questions/test_retirement imports+targets so they would run on a server
   (you cannot execute Odoo tests locally; make them import-consistent and logically retargeted,
   flag anything you could not verify without a runtime in the report).
8. Danger scan: `grep -rn "learn\." pb_learn/static | grep orm.call` → only the kept RPCs
   (#3-#11 minus content ones + new `learn.runtime.bootstrap` + relocated live_check).

## Report back
- New/changed/deleted file list with one-line purpose each.
- bootstrap() payload example (real emitted values, abbreviated).
- The live_check relocation decision. The rec()-triples vs Trans-join decision.
- Parity summary (test 2), contract ids retired/retargeted (test 3), anything unverifiable
  without a server runtime (explicit list — the reviewer and the deploy phase pick these up).
- Migration risk notes for `-u pb_learn` on live (model deletion → Odoo drops tables/ir.model
  rows; note anything that needs a pre-uninstall SQL or a two-step).
- Ledger candidates.

## Kickoff
"Implement docs/handovers/LEARNOS_PHASE1A_HANDOVER.md exactly. Read it and both ledgers fully
before writing code. Local-only; no deploy, no commit; leave the tree for review."
