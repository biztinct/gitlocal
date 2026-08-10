# pb_learn — Conventions & Gotcha Ledger

Shared ledger for every pb_learn phase handover. Read this BEFORE the phase handover.
Append new gotchas at the bottom as they are hit; never delete entries.

## Project conventions

- **Design authority:** `docs/tutorial_poc/design_v2.html` (v2, all questions decided).
  Strategy background: `docs/tutorial_poc/DESIGN_SPEC.md`. Do not re-litigate decisions
  recorded there.
- **Port source of truth:** `/Users/adity/Documents/GitHub/health19/addons/health_learn`
  (module) and `/Users/adity/Documents/GitHub/health19/docs/tutorial_crm/tools/`
  (generator + contract checker + dump_content). Port near-verbatim; when in doubt, match
  health_learn's behaviour and note the divergence in your report.
- **Model names stay `learn.*`** (identical to health_learn — the products never share a
  DB; diffability is worth more than a prefix).
- **Anchor attribute is `data-coach`** (NOT health19's `data-a`). The engine reads one
  constant — set it once. 40+ `data-coach` anchors already exist in the repo and must
  keep working untouched.
- **Bilingual rule:** every translatable ships complete EN and VI values. Vietnamese is
  written for a payroll professional (BHXH/BHYT/BHTN, thuế TNCN, giảm trừ gia cảnh...),
  never machine-literal. Match the tone of the existing VI in
  `docs/tutorial_poc/data.js`. Intent match-phrases are deliberately NOT translated —
  EN + VI phrases live in one bag.
- **One user decision per mission step.** Two decisions sharing one modal caused two
  off-by-one bugs in the v1 prototype. Constraint-enforced in `learn.mission.step`.
- **Design system:** indigo `#5A4BB0` system; `--vuf-*` CSS tokens are emitted by
  biz_theme (`biz_theme/static/src/scss/vu_tokens.scss`) — same token family health19
  uses, so health_learn's coach.scss/journey.scss port with minimal edits. Solid colours
  only, Lucide SVG only, no emoji, no gradients.
- **Commits:** feature-scoped, explicit file staging, reviewer-focused messages, end with
  `Co-Authored-By: Claude Opus <noreply@anthropic.com>` (implementer runs) — do not push.

## Verified plumbing facts (do not re-derive)

- **Screen resolution analog:** `pb.sidebar.item` (pb_sidebar/models/pb_sidebar.py)
  carries `action_xmlid`, `action_tag`, `match_action_xmlids`, `match_action_tags`,
  `match_models`, `groups_id`, `active`; public method **`get_sidebar_data()` at
  pb_sidebar.py:63** — the direct analog of the `cms.sidebar.item.get_sidebar_data()`
  call in health_learn's `learn_station._visible_sidebar_item_ids`. learn.screen's
  `sidebar_key` will hold `pb_sidebar.*` xml-ids.
- **Pay Run sidebar leaves** (pb_sidebar/data/pb_sidebar_data.xml): `pb_sidebar.item_run_payroll`,
  `item_pay_runs`, `item_payslips`, `item_import`, `item_full_final`, `item_proration`,
  `item_retro`. Section record: `pb_sidebar.sec_payrun`.
- **Approval chain** (pb_payruns/models/hr_payslip_run.py:73-86): `selection_add`
  inserts `('level0', 'Payroll Officer pending')` before `('level1',)`;
  `_pb_group_expand_state` returns `['draft','level0','level1','level2','done']`.
  Rejection testimony: `pb_reject_note/pb_reject_uid/pb_reject_date` (readonly, :80-82).
- **Groups** (pb_hr_payroll_base/security/payroll_base_security_enhanced.xml):
  `group_payroll_base_officer` (:77), `group_payroll_base_manager` (:84),
  `group_payroll_super_admin` (:91), `group_payroll_final_approver` (:169).
  Demo group: `pb_demo.group_payobook_demo` (pb_demo/security/pb_demo_security.xml:8).
- **Lessons render over the practice replica**, not the live app: health_learn's
  LessonView calls `shellHTML(step.screen)` from `engine/screens.js`
  (journey.js:372,540). Real-product anchors are consumed by the Coach's Show-me
  (`flashRing`) and later by live missions. Do NOT build lesson-time navigation of real
  actions.
- **Coach mounting:** `coach_patch.js` patches `WebClient.components`;
  `coach_patch.xml` xpaths `//MainComponentsContainer position="after"` in
  `web.WebClient`. Screen resolution listens on `ACTION_MANAGER:UI-UPDATED`
  (health_learn coach.js:79) and resolves 3-pass: own tag/xmlid → declared extra
  tags/xmlids → res_model (coach.js:90).
- **Sidebar icon set is FIXED** (pb_sidebar/static/src/js/pb_sidebar.js): only
  home/calendar/users/file/file-text/calculator/layers/shield/percent/trending-up/
  clipboard-check/lock/building/database/compass/settings/circle. Unknown icon names
  render a plain circle. Use `compass` for the Journey leaf (no graduation-cap here).
- **No local odoo-bin exists** on this machine. Unit tests are WRITTEN and must import
  cleanly, but cannot be executed locally. Verification = `python3 -m py_compile` on all
  .py, XML well-formedness, `node tools/dump_content.js`, `python3 tools/gen_learn_data.py --check`,
  `python3 tools/check_contract.py`. Runtime/server validation happens at deploy.

## Known Odoo-19 gotchas that WILL bite this work

- `import { user } from "@web/core/user"` — `user` is not a service in this build.
- After `-u`, web asset bundles can stay stale: if an OWL JS/XML change doesn't appear,
  purge `ir_attachment` assets rows and restart (see memory: asset-cache gotcha). Kanban
  arch XML is DATA (ir.ui.view) — reloaded by `-u <module>`, not by asset purge.
- `offsetParent` is null for `position:fixed` elements — measure with
  `getBoundingClientRect` (health_learn's spotlight already does).
- Odoo 19 search views: group-by `<filter>` goes directly in `<search>`; `<group expand>`
  is invalid.
- `_t()` binds to session language — that is exactly why learn chrome strings are
  `learn.string` records shipped in both languages, not `_t()`.

## Appended during implementation

(implementers: add discoveries here, one bullet each, with file:line)

### Run A1 (port + anchors)

- **`res.groups` has NO `category_id` in this repo — use `privilege_id`.** The
  handover's A1-1 row said "simple `category_id`"; that is Odoo ≤18. Every group
  in `pb_hr_payroll_base/security/payroll_base_security_enhanced.xml:73,79,86,93`
  hangs off a `res.groups.privilege`, and the *privilege* carries `category_id`
  (:11-15). `group_learn_author` therefore takes
  `privilege_id ref="pb_hr_payroll_base.res_groups_privilege_payroll_base"`
  (pb_learn/security/learn_security.xml:11-24). A `category_id` field on
  `res.groups` would fail the data load outright.
- **`health_user_admin` has no Payobook analog.** health_learn gave the tenant
  admin write access to the override slots via its own admin group. The nearest
  honest equivalent is `pb_hr_payroll_base.group_payroll_super_admin` — used in
  `security/ir.model.access.csv:21` and `views/learn_menus.xml:24`.
- **XML comments cannot contain `--`.** A dashed underline inside the header
  comment of `data/learn_screens.xml` made the file non-well-formed. Use `====`
  in XML comment rules; `----` is fine in .py/.js/.scss.
- **`pb_sidebar` REPLACES `//ActionContainer`**
  (pb_sidebar/static/src/xml/webclient_patch.xml:5) — exactly the collision
  health_learn's comment warns about. `coach_patch.xml` therefore xpaths
  `//MainComponentsContainer`, which nothing in this repo touches. Do not move it.
- **Bottom-right is a three-control stack now.** `.payai-floating-pill`
  bottom 24px (pb_payroll_ai_insights/…/ai_insight_chat.scss:96) · `.pbc-launcher`
  bottom 92px (pb_coach/static/src/scss/coach.scss:200) · `.lrn-fab` bottom 160px
  (pb_learn/static/src/coach/coach.scss). CSS only — neither neighbour is
  modified, and demo users deliberately get all three. Note pb_coach *hides*
  itself over `.iw-root` / `.pw-root`; pb_learn does NOT, because those two
  wizards are two of the eight screens the Coach is supposed to be on.
- **The sprite is not optional and the regex scan under-reads it.** Icon names
  reaching `ic()` through a helper argument (`kpiTile("layers", …)`) or out of a
  `learn.station.icon` record are invisible to health_learn's `test_assets`
  scan, and a missing symbol renders as a silent gap. `layers` was already
  missing. Fixed by adding the symbol plus `test_02b`, which reads the icon
  names off the *records*.
- **`pb.sidebar.item.get_sidebar_data()` returns the same shape as the cms one**
  (sections → `items` → `children`, pb_sidebar/models/pb_sidebar.py:106-136), so
  `learn.station._visible_sidebar_item_ids` ports with only the model name
  changed. Confirmed, not assumed.
- **Only 7 of the 8 Phase-A screens have a sidebar leaf.** `importwizard` is a
  flow, not a destination — it is the single legitimate user of
  `learn.screen.action_tags` (`pb_import_wizard`, registered at
  pb_import_wizard/static/src/js/import_wizard.js:160). `test_coach`'s
  "every screen names a leaf" count is 7, not 8.
- **`node --check` on a copy renamed to `.mjs` syntax-checks every engine file
  without an Odoo runtime.** Cheap, and it caught nothing this run only because
  it was run continuously. Worth keeping in the A2 verification list.

### Run A2 (authoring source + generated content)

- **A PAYSLIP's approval chain is FOUR stages, not five.**
  `pb_payslip_review/static/src/js/payslip_review.js:12` —
  `draft → level1 → level2 → done`, with **no level0**; that gate belongs to the
  RUN (`pb_payruns/models/hr_payslip_run.py:73-86`). The A1 replica drew the
  run's five stages on the payslip stepper, which would have sent a learner
  looking for an Officer tier that does not exist on a slip. Found by writing
  the contract check, not by reading the code. `STATUS_LABELS` now carries both
  chains and `contract.json::payslip-state-chain` pins them apart.
- **`gen_learn_data.py`'s repo root is THREE dirnames up, not two.** The
  authoring source lives one directory deeper than health19's
  (`docs/tutorial_poc/author/` vs `docs/tutorial_crm/`). Getting it wrong writes
  the whole module into `docs/` and says nothing; there is now an `assert
  os.path.isdir(ADDON)` immediately after.
- **health_learn never writes `learn.screen.next_step`.** Its `gen_screens`
  collects the value into the .po and omits the FIELD, so the `whatnext` intent
  — the most-asked question on any screen — renders an empty English answer.
  Ours emits it as a real field from an explicit `next` in `SCREEN_CTX`. Worth
  back-porting to health19.
- **gettext allows ONE msgstr per msgid, and the guard earns its place.** The
  chrome key `learn` ("Learn" → "Học") collided with the sidebar leaf's name
  ("Learn" → "Học cùng Payobook"). Resolved by making the chrome value
  contextually distinct ("Learning" / "Học tập") rather than forcing one
  Vietnamese onto two meanings. If a conflict is reported, the fix is almost
  always to make the ENGLISH distinct, not to reconcile the Vietnamese.
- **The generator now REFUSES to write a file when any translatable has no
  Vietnamese** (`Trans.untranslated`, exit code 4). health_learn silently
  emitted an empty msgstr and left `test_bundle::test_06` to catch it on a
  server. Failing at generation is the same check three minutes earlier.
- **A column question only reaches the column glossary when NO intent scores on
  it** — curated intents are tried first, which is correct. "what does need
  review mean" legitimately resolves to the `needreview` intent (topic overlap
  55 + on-screen bonus 25 = 80). Any test of the column fallback has to pick a
  label whose words no intent shares; `gross total` is the one used.
- **Simulating `learn_intent._score` in JS before generating is worth the
  twenty lines.** It proved: no two intents share a phrase, every label
  resolves to its own intent in both languages, and no label trips the
  `_ADVICE_MARKERS` deny list (which runs BEFORE scoring, so a label containing
  one would resolve to `compliance` and make its own suggestion chip dead).
- **`_ADVICE_MARKERS` must be written in NORMALISED form.** `_norm` turns every
  punctuation mark into a space, so a hyphenated marker (`under-declare`) can
  never match. Same trap as the diacritic folding on the Vietnamese entries.
- **The generator owns the `practice` block of anchors.json and nothing else.**
  `product` / `pattern` / `foreign` / `scan` describe real templates in other
  modules and stay hand-curated — generating a claim about someone else's
  template from our own content would let the registry agree with itself while
  disagreeing with the product.

### Run A2 review fixes

- **PRIVACY DIVERGENCE FROM health_learn, deliberate:** `coach_miss` must NOT
  carry the learner's question. health_learn logs `q.slice(0, 40)`
  (health_learn/static/src/coach/coach.js), which on a payroll help box is
  "why is Nguyễn Thị Mai's net only 4m" — a named employee and their pay,
  landing in `learn.event`, a table with no retention policy and no way for
  that person to know it is there. pb_learn sends `answer.key || ""`. The
  signal that is actually used survives: `screen` is logged on every event, so
  miss RATE per screen still drives the next piece of content. Mining the
  questions themselves becomes a Phase D opt-in on its own deletable model.
  Asserted by `test_progress_security::test_06`, which reads coach.js because
  the server cannot observe what the browser chose not to send.
- **A resolved intent can render NOTHING, and used to ship as `matched`.**
  Dynamic intents (`whatpage`, `whatnext`) build their only block from the
  screen record, so on an uncovered screen — or before `next_step` was a real
  field — the drawer showed the intent's heading above an empty card. `ask()`
  now requires `answer['blocks']` before claiming a match; anything else falls
  through to the honest miss, which at least names what it CAN answer.
  Undeclared shipped behaviour in A1/A2; `test_11`/`test_11b` pin it.
- **Do the arithmetic, then write the sentence.** 4,200,000 / 1,100,000 is
  **381.8%**, not 282% — the wrong figure had propagated to 39 sites across
  lessons, missions, intents and the fixture before anyone multiplied it out.
  Ratio framing ("382% of June") is now used everywhere; "up N%" was banned
  because the two framings differ by exactly 100 points and mixing them is how
  the error survived review the first time.
- **Every displayed figure in the fixture is now DERIVED.** `payslip()` in
  practice-data.js is the one rule (10.5% insurance on the registered base,
  11m relief + 4.4m per dependant, 5% first bracket); employees declare only
  inputs. Mai is the test vector and reproduces her canonical numbers exactly.
  Board KPIs, the import score and the ledger totals are getters over their own
  rows — a hand-typed KPI that disagrees with the list beneath it is the exact
  misreading the "In pipeline" column entry warns about.
- **One record, one state, across every replica.** The July run was `draft` on
  the board and `level0` on the Dashboard, with its payslips at `level1` — a
  batch cannot be behind its own slips. Now: run at `level0`, payslips `draft`
  (level0 is a gate on the RUN; a payslip's chain has no such stage), F&B at
  `draft` for the same reason m1's division decision turns on, and
  `In pipeline = 1` follows from the rows rather than being asserted.
  Missions state their own starting point when it differs from the replica's
  "now" — m2 says the Officer has already approved.
- **Tenant-slot defaults must be what the PRODUCT says by default.**
  `gmTierName` shipped "GM approval"; the real board prints "Finance approval"
  (pb_payruns/static/src/js/pipeline_field.js:11). A tenant who never sets the
  slot then reads one word in the lesson and another on their board.
  `contract.json::payrun-pipeline-labels` now pins all five stage labels — and
  note there are TWO legitimate label sets: the model's selection strings
  ("Payroll Officer pending", used by the kanban the replica mirrors) and this
  widget's ("Officer review"). Neither is wrong; they are different surfaces.
- **Money belongs in the fixture as a NUMBER.** Two ledger KPIs shipped as the
  pre-formatted string "8,420,000 ₫" and reached a Vietnamese reader unchanged,
  in a module whose whole point is that figures follow the reader's language.
  Formatting happens in `M()`, once.
- **Proration: print the factor to 4 dp or the money will not multiply out.**
  10,000,000 × 9/22 is 4,090,909.09; "0.41" beside "4,090,000" invited a
  learner to check the tutorial's arithmetic and find it wrong. Huy's 11/22 is
  exactly 0.5000 — one tidy row and one untidy one is what real proration looks
  like.

### Run B1 (Setup section)

- **TWO sidebar leaves claim `hr.integration.connector`** — Import Data
  (pb_sidebar/data/pb_sidebar_data.xml:82) and Integrations (:196). Both
  claims are CORRECT for the sidebar; neither is usable by the Coach, whose
  third pass would then pick whichever screen the search returned first. Fixed
  inside pb_learn: `learn.screen._contested_models()` computes the set of
  models more than one screen's leaf declares and `_matchers()` subtracts it,
  so a contested model is a matcher for NEITHER. Tags and xml-ids still resolve
  both cockpits exactly; what is given up is the bare list view of a connector,
  where "I do not have lessons for this screen" is the honest answer. Found by
  the offline mirror of `test_coach::test_17`, which is why `test_17b` now
  exercises the mechanism rather than the symptom.
- **The engine's `trace` draws NOTHING unless both anchors are in the same
  DOM.** `spotlight.js` Trace.run returns early when either
  `anchorEl(fromKey)` or `anchorEl(toKey)` is null (:40-42), and a lesson step
  renders exactly ONE replica screen (`shellHTML(st.screen)`, journey.js:371).
  A literally cross-screen trace is therefore not expressible. L6's trace runs
  on the statutory replica, whose right-hand column draws the worked example's
  statutory lines from `CASE` — the same rows the payslips replica draws — under
  the practice-only anchor `rep-slipline`. Practice-only is the honest kind: no
  product screen shows a rate and a đồng amount at once.
- **A `pattern` anchor would have failed the AUTHORING lint even though the
  module's own test accepts it.** `check_contract.py::anchor_lint` builds
  `present` from LITERAL `data-coach="…"` attributes plus the registry's
  `practice` block, so a `t-attf-data-coach` prefix is invisible to it. That is
  why the BHYT row did not get its own anchor and the trace starts at
  `st-rates`, the table the rate is printed in. Extend `anchor_lint` before
  declaring the first pattern, not after.
- **`ANCHOR_RE` in check_contract.py is a hard-coded prefix list.** A new screen
  prefix that is not added there is silently NOT LINTED — no failure, just a
  control the content can point at that does not exist. `fs|st|sr|ig` added
  with the Setup screens; adding the prefix is part of adding a screen.
- **Promoting an anchor out of `foreign` needs the TEST updated too.**
  `test_anchor_registry::test_06` refuses to let the registry declare anything a
  `foreign` entry matches, and `fs-*` is a wildcard. The seven anchors L5 names
  are now in `SHARED_WITH_PB_COACH` beside pw-division/pw-compute, and the
  `fs-*` entry says which seven left. pb_learn still adds NOTHING to
  studio.xml — promotion is a claim about a NAME, not an edit to the template.
- **The four Setup leaves have an EMPTY `action_xmlid` and only a tag.** They
  are OWL client actions (pb_sidebar_data.xml:150-199), so `_primary()` returns
  `(tag, None)` and pass 0 of the resolver still ties each screen to itself.
  A map that expected an xml-id would have left all four undetectable.
- **`payslip()` now reads its rates off `POLICY` and its reliefs off `TAX`.**
  Charging the three employee rates separately and summing them is arithmetically
  identical to the old `round(base * 0.105)` for every employee in the fixture
  (verified against all four), and it is what makes L6's trace true rather than
  merely consistent: the 1.5% on the statutory replica and the 180,000 ₫ on
  Mai's slip are now literally the same number, once.
- **The rate-change impact is 57,000 ₫, not 60,000 ₫**, and the difference is
  the lesson. Insurance is deducted BEFORE the reliefs, so the extra 60,000 of
  BHYT also lowers taxable income and PIT falls 3,000 with it. `RATE_CHANGE` in
  practice-data.js is `payslip()` run twice for exactly this reason — the v1
  prototype hand-typed the figure and the arithmetic is the kind that looks
  right when it is wrong.
- **`POLICY_NEXT` and `RATE_CHANGE` are deliberately NOT in the fixture's export
  list.** They are the derivation the authored prose is checked against, not
  something a screen renders; exporting a name no screen imports would put a
  second, unread copy of the rate change in the engine's contract.
- **The .po diff lies about deletions.** Entries are emitted sorted by msgid, so
  an inserted entry shows as `-` on lines that merely moved. Diff the parsed
  msgid→msgstr maps instead: Run B1 changed exactly ONE existing translation
  (the `practice` intent, which had to stop saying "two are playable") and
  altered none of the other 561.

### Deferred by the reviewer (do not treat as missing)

- ~~**`trace` visual has no content yet.**~~ CLOSED in Run B1: L6 step 5
  (`lesson_l6_step_04`) traces `st-rates` → `rep-slipline`.
- **Duplicate sprite ids** in icons.xml — cosmetic, no render impact.
- **`learn.confidence.award` has no server-side proof** in Phase A.
- **pb_sidebar ships no i18n**, so leaf names outside pb_learn are English on a
  Vietnamese session. Separate ticket, not a pb_learn defect.

### Deploy notes

- **`vi_VN` must be an ACTIVE language before `-u pb_learn`.** The .po is loaded
  at install/upgrade only; installing the language afterwards leaves every
  Vietnamese value missing until the module is upgraded again. Activate the
  language first, then install, then verify with one `learn.string` read under
  `with_context(lang='vi_VN')`.
