# LEARNREV P0 — six quick fixes to the live help (handover for Opus)

Program: `docs/handovers/learnrev/LEARNREV_PROGRAM.md` (standing rules verbatim there — design bar, white-label,
plain English, commits, deploy). Ledger: `LEARNREV_LEDGER.md` (LR-R1…R7, LR1–LR5). Evidence for every fix is on the
owner-approved design page `docs/design/learn_revamp/LEARN_REVAMP_DESIGN.html` (gap ids G2, G4, G16, G21, G24, G33).

## Scope
Six small, independent fixes. No redesign, no new content, no new strings beyond those named. Each fix: code + a
test where the layer allows one + the browser check listed. Then a normal-tier deploy to payobook first and the other
DBs, one browser walk, feature commits, `P0_REPORT.md`.

**Binding non-goals:** do not touch the router (`learn_helper.py`), intents, content JSON, the Journey page, the
scenario engine, PayAI tiers/gates. Do not regenerate learn content. Do not change any stored data.

## The six fixes (facts verified 2026-10-17 — do not re-derive)

### F1 · Chat opens at the latest message (G4, LR-R3)
- Drawer renders only while open (`pb_learn/static/src/coach/coach.xml:46`); with PayAI present it mounts
  `AiInsightChatEmbedded` fresh on every open (`coach.xml:100-103`), so `scrollTop` starts at 0.
- `pb_payroll_ai_insights/static/src/components/ai_insight_chat/ai_insight_chat.js`: `_scrollToBottom(force)`
  (:2638-2649) is called only from `_pushMessage` (:2183-2190), `_routeAndDispatch` (:2400, :2411), send (:924, :986)
  and `pb_payai_actions/static/src/js/chat_patch.js:674,733`. `onMounted` (:2026-2036) and `_onMountLoad`
  (:2053-2071) never scroll. `_noteScreen` (:2248-2265) pushes a context card only when the screen changed, which is
  why the FIRST open on a new screen looks right and a reopen on the same screen sits at 0 (measured live: 0 of 7,099).
- Fix: in `onMounted`, after `_historyReady` resolves (and after the restored `PAGE.turns` render), call
  `this._scrollToBottom(true)`. Keep `awayFromBottom` semantics. Guide-only stream (no PayAI): `coach.js toggle()`
  (:491-501) → after open, `setTimeout(() => this._scrollFallback(), 80)` (`_scrollFallback` :1189-1196).
- Browser check B1: open the drawer on Component treatment, close, reopen → the last message is visible, no scroll
  needed; "Jump to latest" pill not shown.

### F2 · "Open the lesson" opens THIS screen's lesson (G2, LR-R2)
- `coach.js openLesson()` (:1451-1455) calls `openLearn(this.action, "")`; `openLearn` (`engine/places.js:258-267`)
  → `openHub({xmlid:"pb_learn.action_learn_hub", lens:"lessons", focus})`; the Journey applies `lesson:<key>` /
  `station:<key>` / `scenario:<key>:<mode>` on arrival (`journey.js:2082-2161`). Precedents that pass a key:
  `openSuggested` (`coach.js:1718-1724`, `station:${key}`) and PayAI `open_lesson` (`ai_insight_chat.js:1076-1102`,
  `lesson:${action.lesson}`). Current screen key = `this.state.screen` (`coach.js:430-442`); stations are in
  `this.state.stations` (`coach.js:303`).
- Fix: `openLesson()` resolves the target in this order: (1) a station whose `key === this.state.screen`
  → `station:<key>` (outline view, with its Full lesson button); (2) else a station whose `lessons` include the answer's
  `watch`/`show_me` key if the button is on an answer card; (3) else `""` AND the drawer says so in a note
  ("No lesson for this screen yet. Opening the lesson map.") — never a silent landing at the top. Hubs (`hub_*` keys)
  take path 3.
- Test T2 (Python, `pb_learn/tests/`): for every content screen key with a matching station, the client-side rule is
  mirrored: assert `station_by_key[screen.key]` exists for all 54 content screens (list the exceptions explicitly in the
  test with a comment). Browser check B2: on Component treatment ask "explain this screen" → Open the lesson → the
  Journey shows the "Component treatment" outline (title visible), not "Your journey".

### F3 · ⌘K lesson rows register without the warning (G16, LR1)
- `pb_learn/static/src/hub/learn_palette.js:96-99` runs `loadContent().then(registerLessonRows)` at module load;
  `registerLessonRows` (:40) evaluates `_t("Learn")` etc. before translations are loaded → console warning
  "pb_learn: lesson rows not added to the search … Cannot translate string" on EVERY page load (seen live today).
  `coach.js:314` calls it again after content load and that call succeeds, so rows do appear eventually.
- Fix: defer the module-level call until translations are ready (find the Odoo 19 seam in this repo's vendored
  `web/static/src/core/l10n/translation.js` — `translationIsReady` or equivalent; if none fits, drop the module-level
  call and keep the coach call, documenting why in a comment). Zero warnings on load.
- Browser check B3: reload the Learning page and Component treatment → console has no "lesson rows not added" line;
  ⌘K "Component treatment" shows the Lesson row.

### F4 · "calculated" lane gets a label (G21, LR2)
- `pb_formula_studio/static/src/js/component_treatment.js:26-33` LANE_LABELS keys: feed, excel, contract_component,
  formula, record, constant. Server lanes (`pb_hr_payroll_formula/models/formula_config.py:2346-2361
  _value_kind_lane`): `calculated`, `constant`, `feed`, `contract_component`, `excel`. `laneLabel()` (:104-106) falls
  back to the raw key → the board prints "calculated".
- Fix: add `calculated: _t("Calculated by a formula")`; keep `formula` (used elsewhere). Add the VI msgstr
  ("Tính bằng công thức") to `pb_formula_studio/i18n/vi_VN.po` following the PO rules the OC4 phase used (correct
  `#. module:` and `#:` lines; run the same PO parse gate). Browser check B4: Component treatment → NET / GROSS rows
  show "Calculated by a formula".
- Test T4 (Python, `pb_formula_studio/tests/`): every lane string `_value_kind_lane` can return appears as a key in
  LANE_LABELS (read the JS file as text; a plain regex is fine). This is the LR2 "convention broken → test" rule.

### F5 · PayAI door answer never dead-ends (G24, LR4)
- `pb_payai_actions/payai/resolve.py:931-936 resolve_door()`: when `ctx.doors` is empty it returns
  `missing("I cannot see your list of screens yet. Close and reopen this panel, then ask again.")` (owner saw this on
  Rize). Find where `ctx.doors` is filled (the client sends its ⌘K rows on attach; trace `doors` into the ctx builder).
- Fix: when the client sent no doors, build a server-side catalogue instead (hub tabs + the Learn screens' `open`
  xmlids / action tags — `learn.content` already has `screens[].open` and `action_tags`; reuse whatever list the
  client's rows are built from, server-side). Resolve against it; only if the text matches nothing, answer the normal
  "I could not find that screen" with the top 3 door chips. The sentence "Close and reopen this panel" is deleted (EN
  and VI).
- Test T5 (Python, `pb_payai_actions/tests/`): `resolve_door(ctx_without_doors, "open the pay runs board")` returns a
  door to Pay Run › Runs; the deleted sentence is absent from the module (grep test).

### F6 · "Never reaches <component>" says "net pay" (G33, LR3)
- `pb_hr_payroll_formula/models/formula_net_role.py:1718-1760` builds `net_role_reason` with `net=net_name` (the NET
  component's display name) → on a Vietnamese scheme the English sentence reads "Never reaches Số tiền thực nhận VND…".
  The reason is STORED on the rule at classify time and shown under every Pay role cell on the board.
- Fix (both): (a) at source, `net_name` → `_("net pay")` in every reason sentence (keep `%(via)s`, which names a real
  component on purpose); (b) at read time in `value_kind_board` (`formula_config.py:2383-2476`), replace the scheme's
  NET component name inside a stored reason with `_("net pay")` so existing rows read right without a re-classify.
  Vietnamese msgstr: "lương thực nhận". Browser check B6: Component treatment on the demo scheme → no component name
  inside any reason sentence.
- Test T6 (Python, `pb_hr_payroll_formula/tests/`): classify a tiny config whose NET rule is named "Số tiền thực
  nhận"; every `net_role_reason` contains "net pay" and never the component name; `value_kind_board` rows likewise.

## Tests to run (all green before deploy)
- T2, T4, T5, T6 above + the modules' existing suites: `pb_learn`, `pb_payai_actions`, `pb_formula_studio`
  (`studio_experience`, `TestColumnRoles`), `pb_hr_payroll_formula:TestNetRoleClassifier`. Known baseline failures:
  `pb_payroll_ai_insights test_egress.test_04e` (another session's), `pb_payai_actions` test_07b (cron off), and the
  6 pre-existing `check_contract.py` failures — list any failure you see with its cause, never hide one.
- Run on a clone of payobook on the server (`--http-port=8099 --gevent-port=8098`, drop the clone after,
  `pg_terminate_backend` first), never on the live DB.

## Deploy (normal tier)
Modules: pb_learn, pb_payroll_ai_insights, pb_payai_actions, pb_formula_studio, pb_hr_payroll_formula (bump each
manifest patch version in the ship commit). Stage from `git archive HEAD` of those five only. Coordinate first
(ListAgents → SendMessage; `pgrep -af "odoo-bin.*stop-after-init"` on Payobook19v2; wait if any). Then per DB
(payobook, rize, payobook_template, abm — abm's jobs back OFF afterwards): stop → `~/pb_upgrade.sh <db> <module>` for
each module → asset purge + `web.assets.version` bump + `INSERT INTO orm_signaling_assets DEFAULT VALUES` → start.
Verify: hash-identical trees, `latest_version` per DB, log grep for ERROR, HTTP 200.

## Browser walk (payobook.com, QA Test login)
A headless Chrome is ALREADY running on `127.0.0.1:9555` with a signed-in session (user "QA Test", company
Payobook Vietnam JSC). Driver: `/private/tmp/claude-502/-Users-adity-Documents-GitHub-gitlocal/d3a7939f-6b40-427b-9e7d-c5a89b5a6ab8/scratchpad/walk/drive.mjs`
(`TAB=1 node drive.mjs nav <url>`, `eval <js>`, `shot <png>`, `console`; helpers in `helpers.js`). Only the ACTIVE tab
renders (LR-R6): `curl http://127.0.0.1:9555/json/activate/<id>`. If the session is gone, the credentials are in the
memory note `~/.claude/projects/-Users-adity-Documents-GitHub-gitlocal/memory/payobook-qa-login.md` (never into the
repo). Component treatment: `/bizapp/action-pb_mapping_studio` → `details.pbms-toolmenu` → "Component treatment".
Run B1–B6 and screenshot each; report console errors.

## Report back (`P0_REPORT.md`)
Per fix: what changed (files), test result (name + pass/fail), browser check result (screenshot path), deploy per DB
(version before/after), commit hash. Design-bar self-score. Anything you could not verify, say so plainly. New
gotchas → LR rows in the ledger.
