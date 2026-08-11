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

### Run B2 (the demo live track)

- **`check` was already taken, and taking it twice would have shipped the
  debrief in English.** `learn.mission._mission_dict` has had a `check` key
  since Phase A — the debrief CHECKLIST, a list of prose. Adding the live
  step's predicate key under the same name would have forced `check` into
  `_RAW_KEYS` to survive the bilingual zip, and the checklist would have gone
  with it. The FIELD is `check` (as the handover specifies); the serialised key
  is **`check_key`**. Same class of bug as ledger §5.146, one level deeper, and
  it is the second time this exact shape has bitten.
- **A live mission cannot live inside the Journey.** Its first step navigates to
  the product, which unmounts the Journey client action and everything it was
  holding. The runner is therefore a separate component mounted through the SAME
  `WebClient` patch as the Coach (`coach_patch.js/.xml`), with `LiveState`
  (localStorage-backed) as the handover between them. Anything Phase C adds that
  must outlive a `doAction` belongs there too.
- **The predicate registry must not assign the division it reads.**
  `_my_division` was written to call `_pb_ensure_demo_division()` — convenient,
  and it would have put a field write inside a 10-second poll loop and cost
  `learn_live.py` the one property that makes it auditable. Assignment lives in
  pb_demo (signup, and lazily in `demo_payrun.get_defaults`); the predicate just
  reports `_NO_DIVISION`, whose note is exactly the instruction that causes one.
- **`contract.json::live-surfaces-are-read-only` is an `absent` check, so its
  tokens must be greppable without false positives.** `_compute` matches
  `june_run_computed`; `write` matches "written". The pinned tokens are
  `.create(` `.write(` `.unlink(` `cr.execute` `action_` `_do_` — punctuation
  included, deliberately.
- **The demo world is identified by COMPANY NAME.** There is no `is_demo` on
  `res.company`; `pb_demo/models/demo_catalog.py:25` is the only declaration of
  `'Payobook Vietnam JSC'`. The gate checks group membership AND that name, and
  `contract.json::demo-divisions-and-group` pins the string.
- **`hr.payslip.run.pb_division` is empty until the run has payslips.** It is a
  stored compute over the first slip's formula config
  (hr_payslip_run.py:106-125), so a run that exists but has not computed cannot
  be found by division at all. `june_run_computed` therefore counts slips as
  well as matching the division — matching alone would report "not yet" forever
  on a run that was sitting right there.
- **Round-robin counts ASSIGNMENTS, not group members.** One indexed search on
  `pb_demo_division != False`, so the lazy back-fill of an older demo user and a
  fresh signup take the identical path — one rule, one behaviour, and no
  dependency on how this Odoo build flattens `group_ids`.
- **The scss min()/max()+calc() trap caught this module a second time**, in the
  file whose own comment warned about it. `min(var(--w), calc(100vw - 32px))`
  is the same hazard as the inline form; the fix is TWO custom properties and no
  CSS `min()` at all.
- **Chrome strings were audited both directions and three were dropped.**
  `liveVerified`, `liveResume` and `liveObserveOnly` shipped as records nothing
  rendered. Dead configuration is dead configuration whether it is a tenant slot
  or a UI label — 110 declared, 109 read by the JS, the rest being `lines.*` and
  `brand`.

### Phase B review fixes

- **THE BIG ONE: `vietnam.insurance.policy` DOES NOT PRICE A PAYSLIP.** Phase B
  shipped, confidently, that "every payslip in every division reads these
  numbers" and that a rate change "re-prices every future payslip". False.
  Grep the rate fields and every reader is a DISPLAY, an ANALYTIC or a REPORT:
  the Statutory cockpit (pb_statutory.py:54-76), the contribution analytics
  (hr_formula_config_analytics_vietnam.py:49-76), the employee cost estimate
  (hr_employee_vietnam.py:235-259) and the insurance analytics wizard.
  `hr.formula.config.vn_insurance_policy_id` and
  `hr.employee.vn_insurance_policy_id` are plain Many2ones with no compute
  behind them.
  What prices the BHYT line is a **parameter constant on the division's formula
  configuration** — `EEHI = 0.015` (demo_catalog.py:62), charged by
  `HIEMP = -ROUND(MIN(BASIC,CAPLO)*EEHI)` (:107).
  The rewrite frames it as the product actually behaves: the policy is what the
  company DECLARES, the configuration is what CHARGES, and the Statutory
  screen's real job is **reconciliation**. That is better teaching than the
  false version — L6's trace became "check the declared rate against the
  charged one", and m4's anomaly became "the declaration that changed nothing".
  `contract.json::statutory-declares-config-prices` pins both halves.
- **The fixture had the same coupling and now models the truth.** `VN_RATES`
  is declared once; `POLICY` (the declared record) and `CONFIG_PARAMS` (the
  pricing constants) both read it, and `payslip()` reads CONFIG_PARAMS. Same
  numbers, two sources — which is what a correctly run company looks like and
  what makes the trace a check a learner can perform. Mai's canonical vector is
  unchanged to the đồng.
- **The cockpit's selection rule is narrower than it reads.**
  `search([('company_id','in',co_ids), ('active','=',True)], order='effective_date desc', limit=1)`
  — it does **not** consult `end_date` and it does **not** compare the date to
  today, so a future-dated policy is displayed the moment it is saved. Content
  that taught "end-date the outgoing policy" was teaching an affordance that
  does not exist (the new-policy wizard has no end-date field at all). m4's
  effective-date judgement now rests on the honest ground: the date is the
  legal record, immediate is still wrong because it declares a start the
  company cannot evidence and because the screen starts showing next month's
  rates to everyone reviewing an open run.
- **PRODUCT BUG CANDIDATE — do not fix from pb_learn.** `pb_statutory`'s policy
  and tax rosters search `[]` with no `active_test=False`
  (pb_statutory.py:149,161), so ARCHIVED records never appear even though the
  card renders an `active` badge that could say "Archived". The roster is
  therefore live declarations only, not a history. L6 step 5 now says that.
  Raise separately against pb_statutory.
- **A capstone predicate must be scoped to the CREATOR.** `june_run_computed`
  matched on is_demo + June + division — and the demo generator seeds exactly
  such a run for every division before anybody signs up, so step one ticked
  itself green off somebody else's record. `('create_uid','=',env.uid)` closes
  it; mL1's brief now says which run is being watched and why the seeded one is
  ignored. The class of bug: a predicate that describes a STATE rather than an
  ACT will pass on a state somebody else produced.
- **A whitelist entry with no reader is a read path nobody asked for.** Three
  live-value keys shipped implemented and unconsumed; `flagged_count` reached
  into `pb.payslip.review._slip_totals` — another cockpit's raw SQL — to define
  a word this module does not own. Removed. They come back with the content
  that needs them, in the same commit.
- **`learn.live.values()` is now gated in full**, like the predicates. Live
  values are demo-world-only in Phase B; everywhere else `render()` falls back
  to the authored sentence, which is the designed behaviour and is why both
  live sites ship a fallback that reads correctly without the live figure.
- **Gate on `env.company.name` only.** The union over `company_ids` made the
  refusal text false: a user who merely HAS the demo company in their list
  while working in another would have passed, with a different company's screen
  in front of them.
- **`_contested_models` is `ormcache`d**, because `_matchers` runs once per
  screen and it walked every screen — one bundle build was a quadratic sweep of
  the sidebar. `learn.screen` now clears the registry cache on write, mirroring
  `learn.station._invalidate_learn_bundle`.
- **localStorage keys need the db and the uid.** `pbLearnLive` alone hands one
  browser profile's second session the other's half-finished capstone, pointing
  at a run it cannot see.
- **Left as-is, deliberately:** the round-robin division assignment has a
  benign signup race (two simultaneous signups can share a division — the
  capstone still works, and the alternative is a lock on a cosmetic property);
  `get_defaults` re-sorts the remaining five divisions alphabetically rather
  than preserving catalogue order (cosmetic).

### Phase B VI audit fixes

- **RULING: a bilingual dict literal in Python is not a translation.**
  `_B(en, vi)` in learn_live.py and the inline `{'en':…, 'vi':…}` in
  `live_check` were bilingual and still wrong: a Python dict is invisible to
  the .po tooling, so a translator never sees it, a reviewer cannot diff it
  against the rest of the module, and the one surface where the Coach speaks
  from CODE drifts away from the twelve hundred strings that do not. The 17
  static sentences are now `learn.string` records under `live.*`, generated
  from `docs/tutorial_poc/author/data.js` like everything else and read
  server-side in both language contexts by `_note()`.
  **The line to hold:** a SENTENCE is content; choosing which sentence, and
  with which numbers, is code. `%(count)s payslips computed for %(division)s`
  is a record; the interpolation happens in Python, into it. Any future
  server-side message goes the same way.
  One deliberate exception stays a literal: the echo of an UNMAPPED product
  state (`{'en': raw, 'vi': raw}`), because inventing a translation for a raw
  selection key would be inventing a product string.
- **`trình duyệt` is Vietnamese for "web browser".** Used as a noun for "the
  act of submitting" in four content sites it reads as a piece of software. The
  verb phrase `trình phê duyệt` was already correct elsewhere in the module —
  the fix is `việc trình phê duyệt` (the act) and `trình đợt lương lên duyệt`
  (submit the run), which is what the rest of the module already said. Worth a
  ledger line because the wrong form is the SHORTER one and will be reached for
  again.
- **A rate is a decimal and Vietnamese writes decimals with a comma.**
  `'%g' % 17.5` put "17.5%" inside a Vietnamese sentence — the same class of
  leak as printing money without the reader's thousands separator, one
  separator further in. Rate formatting is now language-aware and normalises
  `-0` before formatting. Any future number that reaches a reader needs the
  same two questions asked of it: which separator, and can it be negative zero.
- **TWO CONFIG-CODE WORLDS, both correct — do not "fix" either.** The lessons'
  practice company uses `HOASEN_RETAIL_END`; the demo world uses
  `DEMO_RETAIL_END`. They are different companies, so different prefixes are
  right. What was missing was the sentence saying so: the shape is
  **PREFIX_DIVISION_CYCLE** and the shape is the thing to learn. Stated in the
  glossary, in `whichconfig`, and in L5 where the practice code is first named.
- **Do not write a placeholder as `<DIVISION>`.** Raw angle brackets are eaten
  the moment glossary or answer bodies are rendered as HTML — and they will be.
  Written as `PREFIX_DIVISION_CYCLE` with a concrete example beside it, in both
  languages.
- **n/a from this round, recorded so it is not re-hunted:** the `_fmt` /
  `_money` grouping helpers were deleted with the three unconsumed live keys in
  the previous round, so there is no count-through-a-money-formatter path left.
  The one remaining count is `%(count)s`, a plain integer interpolation.
  `pb_division_label` is a non-translatable Char computed from the division key
  (hr_payslip_run.py:106-125), so it interpolates identically into both
  language templates — noted in the code rather than worked around, because
  translating it here would be inventing a product string.

### Run C1 (Overview / People / Insights / Compliance + the Learn section)

- **`test_07` in test_anchor_registry.py has been FAILING since Run B1, and
  could not be seen.** It asserts `assertIn(key, self.foreign)` for every
  entry in `SHARED_WITH_PB_COACH`, and B1 added the seven `fs-*` — which are
  covered by the WILDCARD entry `"fs-*"`, not by literal keys. A literal
  membership test on a dict whose keys include wildcards reports seven
  perfectly-documented anchors as undeclared. Fixed to call `_is_foreign()`,
  the helper three other assertions in the same file already use. **The class
  of bug: a test written on a machine with no test runner is a test nobody has
  ever seen pass.** Everything in this module that can be mirrored offline now
  is — `docs/tutorial_poc/author/` has no runner either, but the resolver, the
  registry, the screen-matcher passes and the asset guards can all be replayed
  in Python/Node against the same inputs, and doing so is what caught this.
- **A SECTION NAME AND A LEAF NAME CANNOT BOTH BE "Learn".** The handover
  specified the new `pb.sidebar.section` as "Learn" / "Học tập", and the leaf
  inside it has been "Learn" / "Học cùng Payobook" since Phase A. One msgid,
  two msgstrs — the generator's conflict guard refuses it, exactly as it did
  for the chrome key in A2. Resolved the A2 way: the ENGLISH is made distinct.
  The section is **"Learning" / "Học tập"**, which is already a string in this
  module (the chrome key `learn`, the topbar suffix) with precisely the
  Vietnamese the section wants, so the two MERGE into one .po entry rather than
  fighting over it. Deviation from the handover's literal wording, forced by
  the rule the handover itself cites.
- **`gen_sidebar_item` now emits TWO records and the section must come first.**
  `pb.sidebar.section` requires `technical_key` — a section without one does
  not load at all — and the leaf `ref`s the section, so order inside the file
  is load order. The leaf's `section_id` moves from `pb_sidebar.sec_payrun` to
  `pb_learn.sec_learn` on upgrade because the generated data is `noupdate="0"`;
  no migration step is needed, but the leaf DOES move for existing tenants and
  the deploy note says so.
- **The map's reading order is a FRONTEND constant, not the station sequence.**
  The generator numbers stations with one counter running across every line in
  declaration order, so a new line has to be APPENDED to `STATIONS` or every
  station before it is renumbered for no content reason. That makes the storage
  order (payrun, setup, overview, people, insights, compliance) wrong as a
  reading order. `journey.js` now holds `LINE_ORDER` — overview, payrun,
  people, insights, compliance, setup — and any line missing from it is still
  drawn, after the ones that are: a section must never be able to vanish from
  the map because somebody forgot a second file. `LINE_ICON` replaced the
  `lineKey === "daily" ? "zap" : "plug"` ternary, which would have drawn a plug
  beside five of the six headings.
- **`hr.contract` is the third contested model, and the mechanism absorbed it
  without a line of new code.** Employees declares `hr.employee,hr.contract`
  and Contracts declares `hr.contract`, so the model is now a matcher for
  NEITHER — same ruling as `hr.integration.connector` in B1, and the same for
  `hr.payslip.run`, which Pay Runs and Approvals both claim. All three screens
  still resolve exactly by tag or xml-id; what is given up is the bare list
  view of a contract, where "I do not have lessons for this screen" is the
  honest answer. The contested set is now three, and every one of them is a
  pair of leaves that are both RIGHT for the sidebar.
- **`ANCHOR_RE`'s prefix list is now eight longer, and the two-letter prefixes
  are the point.** `pb_people`, `pb_contracts` and `pb_govt_reports` share the
  `ppl-*` CLASS vocabulary in their templates — `ppl-head`, `ppl-kpis`,
  `ppl-roster` are literally the same class names on three different cockpits.
  Anchor KEYS are therefore namespaced per SCREEN (`pe-`, `ct-`, `gr-`), which
  is what stops a lesson pointing at the Employees roster and landing on the
  Contracts one. A prefix missing from `ANCHOR_RE` is not a loud failure — the
  anchor simply stops being linted — so adding it is part of adding a screen.
- **`rep-dash-kpis` was retired rather than kept.** The Dashboard replica now
  draws the REAL `dash-hero` / `dash-runpayroll` / `dash-kpis` / `dash-formula`
  attributes, because LW names them and a lesson step whose anchor is not in
  the DOM renders a centred card instead of a spotlight. `rep-dash-runs`
  stays practice-only and honest: the product's card there is ONE latest-run
  summary and the replica draws three months, because a lesson about the
  monthly loop needs to show a loop.
- **A lesson step may legitimately carry NO anchor.** LW's last step is about
  the Coach launcher, which is mounted by the WebClient and is not part of any
  replica — pointing at it from inside the Journey would be pointing at a
  control the lesson has covered with its own overlay. `Spot.show(null, …)`
  centres the card, which is the right shape for a step whose subject is not on
  the screen. The alternative — adding a `data-coach` to pb_learn's own
  `coach.xml` — would have put a fourth kind into the registry for one step.
- **Every figure on the new replicas is derived from `board`, `recentRuns`,
  `statutory`, `ledgers` or `payslip()`, and the approval lanes are the proof.**
  `PRACTICE.approvals` filters the SAME board rows the Pay Runs replica draws,
  so the July run is at `level0` on three screens and two of the three lanes
  are EMPTY. Drawing them empty is honest — pb_approval renders "No runs here."
  for exactly that state — and it removed the temptation to invent a second
  submitted run with a made-up net. LA's variance material is
  612,480,000 / 596,110,000 / 3,100,000, all three of which already existed.
- **`PRACTICE.people.wageBill` IS `statutory.insuranceBase`.** The sum of the
  registered contract bases and the base the contributions are charged on are
  the same 570,000,000 ₫ described twice; declaring it twice would have let the
  People band and the Statutory band disagree about the same company.
- **"Net paid" was already taken.** The Pay Runs board's KPI is "Net paid" →
  "Đã chi"; the Insights headline's own caption in `insights.xml` is "net
  payroll", so the column ships as "Net payroll" / "Lương thực chi". Third time
  the one-msgstr rule has decided a label in this module — the fix is always to
  read what the PRODUCT calls it and use that.
- **`Explorer` is a proper noun and is now in `SAME_IN_BOTH`.** pb_sidebar
  ships the leaf name untranslated and the cockpit prints it untranslated;
  translating it in the Journey would send a learner looking for a leaf that
  says something else. It is the only new string in 296 where EN == VI.
- **Two existing intents were EDITED, not appended: `approve` and `reject` both
  gained `approvals` in their screen list.** Everything else in this run is an
  append — the .po diff is 0 removed, 0 changed, 296 added — and these two are
  the deliberate exception, because the Approvals cockpit is where approving
  now actually happens and a capability-aware answer that is unreachable on the
  screen the action lives on is content nobody can find.

### Run C2 (pb_coach retirement seams)

- **`Registry.add` THROWS on a duplicate key, so "move it verbatim" was not
  available.** `demo_missing_record.js` registers an error handler under the
  name `demoMissingRecordHandler`, and pb_coach keeps its identical copy until
  the deploy-time uninstall. A byte-for-byte copy in pb_demo would not have
  "double-rendered" — `web/static/src/core/registry.js:103-107` raises
  `DuplicatedKeyError` with no `force`, **while the backend bundle is being
  evaluated**, taking every module after it down. The port is verbatim except
  the registration, which is wrapped in `contains()`. `force: true` was
  rejected on purpose: the two copies are the same function, so forcing would
  only let asset load order decide which one is live, silently.
- **An `absent` contract check greps the COMMENTS too, and it caught the new
  one immediately.** `payai-has-no-hard-coach-dependency` pins the absence of
  `useService("pb_coach")` — and the comment explaining why the hook was
  replaced contained the literal. Same trap as
  `live-surfaces-are-read-only` in B2, second occurrence: **a token pinned as
  absent may not appear in the prose that explains it.** The comment now says
  "asking for the coach through the service hook", and adds a line telling the
  next reader not to write the literal.
- **Two source-level tests were greping their own documentation.** The
  first-login test asserted `assertNotIn('lesson:', …)` on a file whose comment
  distinguishes `suggest` from `lesson`; the deep-link test split on
  `_applyDeepLink()`, which matches the CALL SITE first and scoped the
  assertion to the empty gap between the call and the definition. Both now
  assert on the payload (`additionalContext: { lesson`) and split on the
  definition (`_applyDeepLink() {`). **The rule: a source-level assertion must
  be written against a string the CODE has to contain, never one the prose
  might.**
- **`static props = {}` is not "no props", it is "reject the props you are
  given".** The Journey is a client action, so the action manager hands it
  `action`, `actionId`, `className` and `updateActionState`, and a deep link's
  context arrives on `props.action.context`. Phase A declared none, which was
  invisible while nothing read them. `["*"]` — the set belongs to the action
  manager, not to us.
- **`tour_mapping` maps to L5, not L4 — a documented deviation from the
  coordinator's table.** The stated criterion was "the nearest lesson", and the
  mid/end mapping wizard pairs COMPONENTS across two formula configurations,
  which is L5's subject; L4 is about attendance files and the import confidence
  score. Sending somebody asking about component mapping into a lesson about
  timesheets would be the wrong desk. `tour_import` → L4 as specified.
- **The greeting had to be able to READ another module's flags without owning
  them.** pb_coach's hero_path still auto-starts while both are installed, so
  `first_login.js` reads `pb_coach_login_seen` / `pb_coach_welcomed` by their
  literal names and stands down — and records its OWN key so it does not fire
  the moment the hero tour is dismissed. It never writes pb_coach's keys, and
  `test_retirement::test_06` asserts that in both directions. Worst case if
  those names ever move: a demo user greeted twice on one login, while both
  modules are installed, which ends at the uninstall.
- **The successor greeting deliberately does LESS.** pb_coach auto-STARTED a
  spotlight; pb_learn opens the Journey map with a "Start here" pulse on LW and
  stops. `suggest` points, `lesson` opens, and they are two different context
  keys for exactly that reason — a greeting has no business deciding somebody
  has eight minutes right now. The pulse is three breaths and has a
  `prefers-reduced-motion` branch.
- **The launcher offset is a RUNTIME decision, not a deploy-time one.** Three
  controls share the corner while pb_coach is installed and two once it is not,
  and the module cannot know which database it is on. `first_login.js` sets
  `body.pb-coach-absent` from whether the SERVICE exists; the stylesheet keys
  both offsets off it, mobile included. The default stays the three-control
  stack because a gap is a better wrong guess than an overlap.
- **PayAI's action envelope became checkable by becoming a lesson key.** A tour
  id could only ever be compared against a hard-coded tuple in another module's
  registry; a lesson key is a record, so `payai-lesson-keys-are-real` and
  `test_action_envelope::test_09` can now ask whether the button's promise can
  be kept. That is the real argument for the retarget, over and above retiring
  pb_coach.
- **The old envelope is still accepted, and that is not politeness.** A cached
  conversation, a slow provider rollout or a fine-tune that learned the old
  vocabulary would otherwise have every "Show me" silently dropped for as long
  as it lasted. `_sanitize_action` takes both forms and **always emits
  `open_lesson`**, so the frontend has exactly one shape to handle and the
  legacy path never needs pb_coach.

### Phase C review fixes

- **THE BIG ONE: A REJECTION DOES NOT SEND A RUN BACK TO DRAFT. It CANCELS it.**
  `action_payslip_run_cancel` cascades `action_payslip_cancel` over every slip
  and writes the RUN to `'cancel'` (om_hr_payroll/models/hr_payslip.py:1227-1230),
  and that selection value's own label is **"Rejected"** (:975) — so the board
  says rejected while the record says cancelled. Getting a workable draft back
  is `draft_payslip_run`, a DIFFERENT method gated to the Finance/GM tier
  (pb_payruns/models/hr_payslip_run.py:283-298). Phases A and B taught the false
  version in **24 content sites across both languages**, and taught it in the
  places it does most damage: the consequence cards of the two lessons about
  signing for money, and both `undo` mission steps. The corrected frame is that
  rejecting is a way to STOP money moving, not an undo — the officer cannot pick
  the batch back up, and a second person at the {{gmTierName}} tier has to
  reopen it first. `contract.json::rejection-cancels-the-run` pins all three
  halves (the cancel cascade, the tier gate on the reset, and pb_approval's
  reject entry point) so it cannot drift back.
  **Same shape as the Phase B statutory error**: a plausible mechanism nobody
  had executed, propagated confidently across every surface. Both were found by
  reading the product method rather than the product's UI.
- **`STATUS_LABELS` now carries `cancel` on BOTH chains.** The run's and the
  payslip's selections both have it; the fixture had neither, so nothing could
  render the state the content now teaches.
- **THIRD OCCURRENCE of "a source-level assertion greped its own prose."** The
  first-login test asserts that no CODE below the two read-only constants names
  a pb_coach key — and the comment explaining the stale-flag fix names one, as
  it must. The test now strips comments before asserting. **THE RULE, now
  written down: a source-level assertion must be scoped to code. Strip `//` and
  `/* */` first, or assert on a string the code has to contain and the prose
  cannot plausibly repeat.** Prior occurrences: the `absent` contract check in
  B2 and again in C2, and the `lesson:` / `_applyDeepLink()` pair in C2.
- **A test written and never executed is not a test.** The reviewer's verdict
  turned on this and it was right: four assertions across three files were
  broken in ways that made them unfalsifiable, and every one of them had shipped
  under a "suite green" claim that had never been run. There is no odoo-bin
  here, so the fix is a REPLAY HARNESS: the real test methods are exec'd against
  a stub `self` carrying the same attributes `setUpClass` builds, with the
  recordset shims backed by the generated XML. **43 assertions across four test
  files now execute on every verification pass, with a tally.** Anything that
  genuinely needs a database reports SKIP rather than passing silently.
- **Two REAL bugs were found by running the tests rather than by writing them:**
  `test_08` (registry) failed on `pw-result` and `st-effective`, because
  **no test in this module counted a mission step's `target` as an anchor
  reference** — m1 and m4 have pointed at those two since Phase A. Both
  `test_04` and the new `test_08` now scan `learn.mission.step.target`.
- **A truthiness test on another module's localStorage key is a permanent
  regression waiting for an uninstall.** `!!ls("pb_coach_login_seen")` stood the
  greeting down correctly while pb_coach was installed — and would have kept
  standing it down FOREVER afterwards, on every browser profile that had ever
  seen the hero tour, with nothing anywhere to point at. The stand-down now
  requires that pb_coach is still INSTALLED (the service) **and** that its flag
  names the CURRENT login. **Rule: a flag owned by a module you are retiring
  must be read with an expiry, because it outlives the module.**
- **`doAction` is async: a synchronous `try/catch` around it catches nothing.**
  Shipped in C2 as the guard for a database without pb_learn — the one state it
  existed for is the one state it did not cover. `.catch()` on the returned
  promise. The general form: in this codebase every service call that looks
  imperative is a promise, and a guard that does not say `await` or `.catch`
  is decoration.
- **A sanitizer that can be made to RAISE is not a sanitizer.** `_sanitize_action`
  is the trust boundary between a language model's JSON and a button in the DOM,
  and two shipped lines could be made to throw rather than refuse: `dict.get`
  with an unhashable key (a list where a string was asked for), and `[:40]` on
  an int. Both now type-check first, and `test_07b`/`test_07c` push sixteen
  hostile shapes through the method with the assertion being that it never
  raises.
- **The client-side `start_tour` branch was unreachable and kept a dependency
  alive.** `_sanitize_action` always emits `open_lesson`, so the browser can
  never receive a tour envelope — the branch existed only to justify the coach
  service lookup that justified the branch. Both removed. Legacy acceptance
  stays server-side, where the LLM's output actually arrives. **PayAI's assets
  now contain zero references to pb_coach, in code or in comments beyond one
  explaining the removal.**
- **Two same-specificity CSS rules: the later one wins, and ordering is not a
  style question.** `body.pb-coach-absent .lrn-fab` was declared after the
  `@media` block, so it silently overrode the phone offset and put the launcher
  back at 92px on a 380px screen. `test_10` now asserts the ORDER, because
  presence was never what was wrong.
- **An undeclared `learn.event` kind is DROPPED, not raised** (`log`, learn_
  progress.py:169-171) — which is correct for a stale browser tab and wrong for
  a signal nobody declared. `lesson_deeplink` was being logged into a hole:
  the one row that measures whether the PayAI retarget was worth doing.
- **AMENDED CONVENTION — reserved anchors.** Phase C1 anchored whole REGIONS of
  seven cockpits in one pass, and 16 of those had no content pointing at them
  yet. The ruling is that they stay: the alternative is a second edit to
  somebody else's template for every lesson written afterwards, and each of
  those is a chance for a tidy-up to delete an attribute nothing over there
  reads. **Anchors may be laid ahead of content where the region is certain to
  be taught, and the registry marks them `reserved: true`.** Applied to all 35
  currently-unreferenced product anchors rather than only C1's 16, because a
  test that exempts some of them and not others exempts nothing;
  `test_08` enforces it in BOTH directions, so the flag has to come off when the
  content arrives.
- **A column label is a lookup key.** "Active configurations" was tidier than
  the product's "Active configs" and therefore unmatchable — `learn.column`
  is looked up BY LABEL. Match the template verbatim, always.
- **PayAI's system prompt was still describing a locked-down demo** ("Import,
  Setup and Admin are locked") while the envelope it produces now offers L4
  (Import) and L6 (Statutory). A prompt that contradicts the actions it can
  emit teaches the model to refuse its own buttons. Rewritten to the real
  sidebar, Learning section included.

### Corrections to earlier Phase C claims (L9/L10)

- **"1,205 translated strings, zero of them English" was one string too strong.**
  `Explorer` is identical in both languages by design — a product name pb_sidebar
  ships untranslated — and is allowlisted in `test_bundle::SAME_IN_BOTH`. The
  honest claim, and the one the test actually makes, is that **no prose** reaches
  a Vietnamese reader in English.
- **Phase C as a whole is no longer a pure append, and the C1 commit's banner
  should not be read as covering it.** C1 alone was: 909 → 1205, 0 removed, 0
  retranslated, 296 added — true when it was written. The review fixes then
  removed 30 msgids and added 32 (the rejection rewrite), so the whole of Phase
  C is **909 → 1207, 21 removed, 319 added, 0 retranslated**.
- **UNDISCLOSED DEVIATION IN C1, recorded now: the Dashboard replica was
  REWRITTEN, not extended.** `SCREENS.dashboard()` gained a hero and a formula
  card, moved to the real `dash-*` anchors and dropped `rep-dash-kpis` — while
  the commit's reviewer-notes listed only three deletions, all in generated
  files, under a zero-deletions framing that read as covering the whole change.
  The rewrite is right (LW names those anchors, and a lesson step whose anchor
  is absent renders a centred card instead of a spotlight) and the review
  accepted it on merit. **The failure was disclosure, not judgement: a
  hand-written asset rewritten inside a content commit has to be named in the
  commit, because the generated-file diff cannot show it.**

### Phase C content-fidelity round (review round 2)

- **A KPI TILE IS A QUERY, AND THE QUERY IS THE TEACHING.** Phase C1 described
  the Dashboard's "Pending approval" as "every sign-off the company is waiting
  on, at every gate". It is `payroll.analytics` rows in state `ready`, falling
  back to `hr.payslip` at `level1`/`level2` (pb_dashboard/models/
  pb_dashboard.py:44-47): **payslips, not runs; HR and Finance only, never the
  Officer gate.** The lesson's understanding check turned on that number, so a
  learner was being taught to read 48 — one ordinary batch — as forty-eight
  runs, and a normal Tuesday as a crisis. The quiz survives as a judgement (the
  Dashboard reports a company state, the Approvals screen counts YOUR queue) but
  every figure in it changed. **RULE: before writing about a tile, read the
  method that fills it. The caption is not the definition.**
- **The Insights board does NOT read the payslips.** It reads the STORED per-run
  roll-ups (`pb_total_net`), plus a `payroll.analytics` snapshots panel — which
  is why it is fast, and why "built from the payslips themselves, so a figure
  here and a figure on a payslip cannot disagree" was both false and the most
  quotable sentence in the station. Worse, `_runs()` has **no state filter**: the
  hero is the latest run in ANY state, so a draft computed an hour ago is the
  headline and the state chip beside it is the only thing that says so. The
  leaderboard is the opposite — it waits for a DONE run. Two different scopes on
  one screen, and the content now teaches the difference instead of averaging it.
- **Teaching a capability AWAY is worse than not teaching it.** `whichtool` said
  no analytics screen explains WHY. The Explorer does, and it is the only one:
  `narrate()` builds an exactly-reconciling variance waterfall with an anomaly
  rail, and `drill()` goes from any cell to the employees behind it — read from
  `hr_payslip_line JOIN hr_payslip` rather than from the fact tables, so the
  drill doubles as the audit trail. The corrected answer is the **lineage**, and
  the lineage is better teaching than the false symmetry it replaces: Insights =
  stored roll-ups + analytics snapshots · Explorer = derived fact tables
  reconciled to payslip lines · Workforce = the attendance and overtime models.
  Three lineages, one payroll — which is what stops somebody comparing two
  numbers that were never the same number.
- **`trình duyệt` came back, and this time it is a TEST.** The ledger's Phase B
  ruling was written down and the shorter, wrong form was still reached for
  twice more — once in a Phase C1 blurb, once in a Phase B string the round-1
  audit had missed. Prose does not stop this; `test_bundle::test_10` does. The
  regex has to be narrow enough to leave `trình phê duyệt` and `trình duyệt web`
  alone, and case-insensitive, because at the start of a sentence the noun is
  capitalised and hardest to see: `(?<!phê )trình\s+duyệt(?!\s+web)`, `re.I`.
  **A convention that has been broken three times is not a convention, it is a
  missing test.**
- **"Nothing here is a second way of doing anything" was one button too
  absolute.** Two controls on the Dashboard open the legacy
  `pb_hr_payroll_analytics` screen, which has **no sidebar leaf at all** — so it
  is the one door on that screen a learner cannot find their way back to from
  the menu. Naming the exception is more useful than the tidy rule: the rule
  taught them to trust every door, and the exception is the door that surprises
  them.
- **The KPI band has ZERO click handlers.** "Every tile is a link into the screen
  that produced it" was aspirational; the tiles report, and the buttons and run
  rows are the doors. Checked by counting `t-on-click` inside `pbd-kpis` rather
  than by reading the design intent.
- **A REPLICA MUST NOT BE MORE COHERENT THAN THE PRODUCT, and it must not be
  less.** Two failures in one screen: the Insights hero displayed a Retail-only
  total labelled "Net" above a leaderboard summing Retail AND F&B (a board that
  visibly does not add up), and the govreports replica drew `gr-grid` AND
  `gr-empty` at once when the product is a `t-if`/`t-else` on `available` — on
  the one screen whose lesson is about reading an empty state correctly. The
  hero now carries its own scope and state chip; the leaderboard derives from
  the board rows; govreports draws one state, selected by a `selected` index on
  the fixture.
- **The last re-typed literal in the fixture is gone.** F&B's `214300000 / 21`
  appeared in the insights block AND on the board. Everything scoped to "this
  period" now filters `board` on a `cur` flag, so a board row is the single
  place a division's month is stated. What CANNOT be derived — three attendance
  counts and the leave days, because there is no attendance model behind a JS
  fixture — is now labelled **declared input** in a comment beside it. A number
  whose provenance is invisible is the one a learner cannot check.
- **"Coming soon" is an INSTALL question, not a product limit.** `available` is
  `wizard_model in self.env` — the country's own payroll module is not installed
  on this database. Five countries carry catalogues and `cpf.submission.wizard`
  exists in the tree. The old wording ("has not been built yet") turned a
  five-minute conversation with an administrator into a limitation nobody can
  act on.
- **Two tests share one word on the People screen.** `ready_pct` is
  `with_bank / headcount`; the per-ROW tick also requires a running contract. The
  column had been given the row's stricter definition, which makes it possible to
  read 100% payroll-ready off a band while somebody on a draft contract is about
  to be missing from the run — the exact failure the tile exists to warn about.
- **`SHARED_WITH_PB_COACH` had stopped meaning what it says.** `fs-simulate` and
  `dash-runpayroll` are in a product template and named by a lesson, and **no
  tour points at either** — so there is nothing shared about them. Listing them
  made the set mean "promoted" rather than "shared", and a set whose name has
  drifted from its contents is one nobody can reason about at the next
  promotion. `fs-simulate` needed a second, honest name — `PROMOTED_FROM_WILDCARD`
  — because a `foreign` WILDCARD (`fs-*`) still matches it while making no claim
  about that specific anchor; `dash-runpayroll`'s literal `foreign` entry was
  simply dropped.
- **A column label is a lookup key, and so is a sidebar group list.** "Active
  configs" (not "configurations") because `learn.column` matches BY LABEL; and
  `whosees` dropped the final approver because the People leaves carry officer,
  manager and super_admin only. The second one improved the teaching: a final
  approver signs for a total and still does not get the salary roster, which is
  a deliberate separation worth naming.

### Run D1 (PayAI data-egress hardening)

- **THE FINAL APPROVER IS ALREADY A PAYROLL MANAGER, so the handover's "manager
  OR final approver" is one group with extra steps** —
  `group_payroll_final_approver` implies `group_payroll_analytics_manager`
  (payroll_base_security_enhanced.xml:172) which implies
  `group_payroll_base_manager` (:165). Both are named in
  `INDIVIDUAL_SALARY_GROUPS` anyway, because the gate is a statement about WHO
  MAY SEE A NAMED PERSON'S PAY and the two roles are separately meaningful; if
  the implication is ever cut, the gate keeps its meaning instead of silently
  narrowing. **But the same implication makes a pb_learn content claim false:**
  `whosees` says a final approver "signs for a total and still does not get the
  wage roster", and the Employees leaf is gated on officer/manager/super_admin —
  every one of which a final approver HAS by implication. Odoo flattens implied
  groups onto the user, so that leaf IS in their sidebar. Content fix, not a D1
  fix; raise against pb_learn. Same class as the Phase B statutory error and the
  Phase C rejection error: a plausible mechanism nobody executed.
- **A refusal must not be handed to the model to paraphrase.** The obvious
  implementation returns the refusal from `query_for_message` and lets
  `_process_data_query` json.dumps it into the prompt like any other result —
  which spends a token asking a provider to restate our own sentence, lets it
  soften or contradict the one sentence in the flow that has to be exact, and
  puts "this user was refused" plus the question that earned it on the wire to
  an external provider. `access_refused` short-circuits BEFORE the prompt is
  built (payroll_ai_engine.py), and `test_05` asserts the ORDER of the two, not
  merely the presence of the check.
- **A GATE IS NOT A SUBSTITUTION.** Below the individual gate the caller gets
  the aggregate answer — which is a different answer to the question that was
  asked, and saying so is the whole difference between a gate and a quiet swap.
  The note rides on `access_note` and is appended to the narrative in Python,
  in BOTH return paths of `_process_data_query` including the JSON-parse
  fallback: a user whose detail was withheld has to be told so precisely when
  the model's output was malformed, which is not the rare branch.
- **`ir.module.module` under superuser was a privilege escalation for a
  question the registry answers better.** The soft-dependency probe now reads
  `_OPTIONAL_MODULE_MODELS` — model presence in `self.env`, plus a field the
  optional module adds where the model is generic (`account.analytic.line`
  exists without hr_timesheet; `employee_id` on it does not). What the caller
  actually needs is for `self.env[model]` not to raise, which is exactly what
  this tests, and it needs no rights at all.
- **FOURTH OCCURRENCE of "a source-level assertion greps its own prose", caught
  before it shipped this time.** The absent-token test greps the WHOLE of
  `payroll_data_query.py`, comments included — deliberately, because a
  commented-out escalation is a template — so the module docstring cannot
  contain the literal even to explain the rule. It says "the escalation" and
  carries a NOTE TO THE NEXT READER saying why. The test file names the literal
  by concatenation (`'.' + 'sudo' + '('`) so the same scan pointed at the tests
  would not fire on the test that enforces it.
- **A refused HALF must not be merged as an empty one.** `_query_department_data`
  merges salary and headcount; two zeroes in a department table read as "nobody
  works here", which is a different and much worse answer than "you may not see
  this". It returns the refusal instead. `_query_trend_data` is deliberately
  the one `_query_*` with NO guard — it owns no query, and wrapping it would
  only produce a refusal named after the wrong topic; `test_02` asserts that
  exact exception rather than "all of them".
- **A refusal template must never make the topic its grammatical SUBJECT.**
  The first draft capitalised the fragment and read "Individual employee
  salaries **is** outside what your role is allowed to read" — plural topics,
  singular verb, in a sentence whose whole job is to sound like a person. The
  topic is the OBJECT now ("your role is not allowed to read %(topic)s") and
  nothing capitalises it, which also removes the `.upper()` on a Vietnamese
  first letter.
- **PayAI had no i18n directory at all**, so `_()` was decoration. Phase D1 adds
  `pb_payroll_ai_insights/i18n/vi_VN.po` — 18 entries, generated from the AST of
  the source rather than retyped, so a reworded refusal fails generation rather
  than losing its Vietnamese. `test_06` re-derives the literal list from the AST
  on every run and refuses a missing, empty or identical-to-English msgstr;
  `test_06b` ports the `trình duyệt` regex, because that rule now applies to a
  second module.
- **The vi_VN.po is a DEPLOY-ORDER dependency, same as pb_learn's.** The .po is
  loaded at install/upgrade only: activate vi_VN, then `-u
  pb_payroll_ai_insights`, or every refusal reaches a Vietnamese reader in
  English.
- **THE DEMO WORLD KEEPS EVERY PAYROLL PATH AND LOSES THE FOUR OPTIONAL ONES.**
  Read off the rules rather than assumed: `pb_demo/hooks.py:19-40` grants the
  demo group read on hr.employee, hr.contract, hr.payslip, hr.payslip.line and
  their department/job models, and `pb_demo_security.xml:23-42` adds
  `[(1,'=',1)]` rules on the payslip objects. hr.employee's only rule is the
  GLOBAL multi-company one (hr/security/hr_security.xml
  `hr_employee_comp_rule`), and hr.contract's group-scoped rules belong to
  hr_contract groups a demo user does not hold — so only the global
  multi-company rule applies and the demo user sees every contract in their
  company. Salary, headcount, department, overtime, deduction, cost, trend,
  periods, summary and forecast are therefore unchanged for demo users.
  **What changes: attendance, leave, recruitment and timesheets.** pb_demo
  grants NO access to hr.attendance (whose ACL has no `base.group_user` row at
  all — hr_attendance/security/ir.model.access.csv), hr.applicant or
  account.analytic.line, and hr.leave's `base.group_user` row is paired with an
  own-records-only rule that a demo user (who is not an employee) matches
  nothing under. Those four questions used to return the whole company's data
  because of the escalation; they now return a refusal or an empty set, which
  is CORRECT and is also a visible demo regression if those modules are
  installed. The fix belongs in pb_demo — four rows in `_DEMO_ACCESS` plus
  read-all rules — not in a gate that would have to lie to avoid it.
- **Remaining escalation in this module, deliberately out of D1 scope:**
  `payroll_ai_pulse.py:110,173,222,288,321` still runs elevated. It is a CRON
  anomaly scanner, so running as no particular user is defensible — but the
  alerts it produces ARE shown to users, and nothing gates which user sees an
  alert derived from which company's payslips. Raise separately.
  `payroll_ai_config.py`'s escalation reads the provider credentials and is
  correct.

### Run D2 (composer + question mining + three addenda)

- **THE BIG ONE: `get_provider_instance()` IS NOT A METHOD ON
  `payroll.ai.config`, AND FOUR CALL SITES HAVE BEEN CALLING IT.**
  `payroll_ai_config.py:153` defines `get_provider`; nothing defines
  `get_provider_instance`. It is called at `payroll_ai_pulse.py:338`,
  `payroll_ai_conversation.py:212` and `payroll_ai_report.py:260,291` — every
  one inside a `try/except` that swallows the AttributeError, so the failures
  are SILENT and permanent:
  the PDF report's AI narratives never generate, its executive summary always
  prints "Executive summary generation failed.", the Pulse anomaly summaries
  are never written, and voice input always answers "Voice feature requires
  OpenAI provider with Whisper support". Four shipped features that have never
  worked, none of which logs anything. **Product ticket, not fixed here** —
  it is a PayAI behaviour change needing its own verification, and D2 is a
  pb_learn commit. The composer copes by asking for
  `get_provider_instance` first and falling back to `get_provider`, so it works
  today and keeps working the day somebody adds the alias.
  **The class of bug: a soft `except Exception` around a method call turns a
  typo into a feature that is merely always off.**
- **The handover named the model `pb.payroll.ai.config`; it is
  `payroll.ai.config`** (payroll_ai_config.py:14). No `pb.` prefix. Corrected
  silently would have meant a composer that could never find a provider, on a
  path whose designed failure mode is to return None quietly — i.e. it would
  have looked exactly like "no provider configured" forever.
- **`coach-cannot-act` could not survive the composer, and deleting it was the
  wrong fix.** It pinned `def _compose`, `def _provider` and `generate_text` as
  ABSENT from learn_intent.py. Those are now legitimately present, and a check
  that fails for a correct reason teaches the next author to delete checks. It
  is replaced by `coach-answers-from-records-only`, which keeps the part that
  was always load-bearing — no FOREIGN provider registry, no direct provider
  import, no raw SQL — plus two new checks that fence the composer itself.
  **A check that has to change when the design changes should be REWRITTEN to
  the new promise, never removed.**
- **`region()`/`within` is what made the corpus check possible.**
  learn_intent.py legitimately names a product model in prose — `_matchers`
  explains that the Pay Runs leaf is matched by one — so a file-wide `absent`
  check would either fail on a docstring or force the docstring to stop being
  useful. `composer-corpus-reads-learn-content-only` is scoped
  `"within": "_corpus"`. First use of `within` on an `absent` check in this
  project; it works, and it is the right tool whenever the honest scope of a
  promise is one method.
- **THE DENY-LIST HAD A HOLE THAT ONLY THE COMPOSER COULD FALL THROUGH.**
  `resolve()` refuses an advice question by returning the `compliance` intent —
  `'compliance' if self.search_count(...) else None`. On a database where that
  record is missing or deactivated it returns **None**, which falls past
  retrieval, past the column glossary, and (before D2) into the honest miss,
  which was harmless. With a composer at the end of that chain, "how do I pay
  less BHXH" would have reached a language model. `_compose` re-asks
  `_is_advice` as its second statement. **A guard that depends on a RECORD
  existing is not a guard; it is a default.**
  **CORRECTION (D2 review): this bullet used "how do I pay less BHXH" as its
  worked example while `_is_advice` DID NOT CATCH THAT STRING.** The
  re-asking of the guard was real and correct; the guard being re-asked was
  not doing the job the sentence claimed for it. Fixed in the review round —
  see the D2 review entry below. The general lesson survives intact and is
  worth more than the example: **an illustration written from intent rather
  than from execution is a claim, and this ledger's standard is that claims
  get executed before they get written.**
- **A refusal template must not make the topic its subject — and a composed
  answer must not pretend to be bilingual.** `_zip_bilingual(tree, tree)` puts
  the model's one language on both sides. Translating it would be a second
  model call inventing a second chance to be wrong; shipping an empty
  Vietnamese side would blank the drawer for the reader who most needs it. The
  prompt asks for the question's language, `ask()` now takes the COACH's
  language (not the session's — the drawer has its own toggle) to pick which
  language of our own material to send, and the badge says the answer was
  composed. That is the honest version of the compromise, and it is the one
  place in this module where EN and VI are deliberately the same string.
- **The scrub is a REDUCTION, not a guarantee, and saying so is part of
  shipping it.** Six fixture names are scrubbed; the demo world holds
  thousands. What makes the composer safe is that the corpus contains no
  records at all. Both spellings of every name are matched (`_ascii` folds tone
  marks but preserves case) because the unaccented spelling is the one most
  likely to be typed in a hurry. A rate SURVIVES the scrub on purpose:
  "what does 10,5% mean" with the number removed is not a question anybody can
  answer, and 10.5 is not personal data.
- **Order the money rules or the redaction looks like it missed.** The
  currency-marked rule has to run BEFORE the grouped-digits rule; the other way
  round, `12.000.000 ₫` becomes `[amount] ₫` — a stranded currency mark beside
  a placeholder, which reads worse than no redaction.
  **CORRECTION (D2 review): the ordering was right and the REGEX was wrong, so
  the outcome this bullet claimed to have avoided is exactly the outcome that
  shipped.** `_CURRENCY_AMOUNT` ended in `\b`, and `₫` is not a word character,
  so the boundary demanded a word character AFTER the currency mark — which at
  the end of a sentence there never is. The rule failed on its own worked
  example and the grouped-digit rule cleaned up behind it. See the D2 review
  entry below. The bullet is left standing because the ordering point is still
  true; what it must no longer be read as is evidence that the case works.
- **`learn.question` is not a reversal of the Phase A2 ruling, and the
  difference is four properties `learn.event` cannot have.** Ordinary rather
  than append-only, opt-in twice, scrubbed on the way IN even after consent,
  and expiring. The key-only behaviour stays the default forever. Both gates
  are re-asked server-side in `record()` — the browser's checks save a round
  trip and are not the control, because the method is reachable by RPC from
  anything holding a session.
- **Consent is the one piece of learner data an AUTHOR does not get.**
  Progress, events and confidence all have an author read-rule; `learn.consent`
  deliberately does not. Who agreed to be recorded is not a content signal, and
  a list of everyone who declined is one nobody should be able to assemble.
  Authors get read AND unlink on `learn.question` (the table exists to be
  triaged and then emptied) but never write — an author who can edit a recorded
  question can edit it into one nobody asked.
- **The consent prompt makes three promises and a test checks the code keeps
  them.** `test_04d` asserts that the retention window stated in the prompt is
  the same integer as `RETENTION_DAYS`. A prompt that promises 180 days beside
  a cron that keeps rows forever is the worst possible version of this feature,
  and it is the version that survives a refactor unless something compares the
  two.
- **A held question does not survive the drawer closing.** Closing without
  answering the consent card is not a yes, and text kept across a close would
  eventually be stored against a question the person had moved on from.
- **ADDENDUM A — the whosees claim was false and the OLD CHECK PINNED IT.**
  `pb_sidebar/models/pb_sidebar.py:73` filters on `user.all_group_ids`, which
  includes implied groups, and `group_payroll_final_approver` implies
  `group_payroll_analytics_manager` (payroll_base_security_enhanced.xml:172)
  which implies `group_payroll_base_manager` (:165). A final approver
  therefore DOES see the wage roster. `people-leaves-exclude-the-final-approver`
  had pinned only the two leaf records — true, and true of a screen whose
  meaning the check never touched. Replaced by
  `people-leaves-and-the-implication-ladder`, which pins the two implication
  lines and the `all_group_ids` filter as well, so cutting any one of them
  breaks the build. **A contract check that pins the EVIDENCE but not the
  MECHANISM will happily agree with a false claim.** The rewritten content
  teaches the ladder, names the consequence (approving a total and reading
  salaries are not separated, and separating them is work somebody has to do),
  and names who is genuinely excluded: analytics-only readers, base users and
  country-toggle holders.
- **ADDENDUM B — the demo grants went in the HOOK, not in the XML.** An
  `ir.rule` in `pb_demo_security.xml` needs `model_id` to resolve at load
  time, so a database without hr_attendance or hr_holidays would fail to
  install pb_demo outright. `_grant_demo_read_rules` sits beside
  `_grant_demo_access`, which exists for exactly that reason, and both run on
  every upgrade via `_pb_demo_rewire`.
  **Only TWO of the four models need a rule, and the other two would be dead
  configuration.** Read off the shipped rules: `base.group_user` IMPLIES
  `hr_attendance.group_hr_attendance_own_reader`
  (hr_attendance_security.xml:14-16) whose rule is own-records-only (:82), and
  hr_holidays scopes three own-only rules to `base.group_user` — so both narrow
  a demo user and both need widening. `hr.applicant` and
  `account.analytic.line` have every narrowing rule scoped to a group the demo
  user does not hold, leaving only the global company rule, which already gives
  the whole demo company. They get an ACL row and no rule.
- **ADDENDUM C — `payroll_ai_pulse.py` escalation stays, as a ticket.**
  Cron-context escalation is defensible: a scheduled job runs as no particular
  user. The issue is downstream — the alerts it produces are shown to users and
  nothing gates which user sees an alert derived from which company's payslips.

### Phase D review fixes (the program's last round)

- **THE BIG ONE: A DENY-LIST OF PHRASINGS DENIES THE PHRASINGS ITS AUTHOR
  THOUGHT OF.** The reviewer broke `_ADVICE_MARKERS` by rephrasing, five times,
  on the first attempt: `how do I pay less BHXH` (the marker is `pay less
  tax`), `làm sao giảm BHXH` (the marker is `giam dong bhxh`, needing đóng),
  `how do I reduce the BHXH base` (the marker is `reduce bhxh legally`), `how
  do I not pay BHXH for probation staff`, `tips to lower employer
  contributions`. Every one obviously in scope; every one waved through, into
  a composer.
  The fix is a TOKEN PAIR beside the marker list: a statutory subject
  (`bhxh bhyt bhtn pit tncn thue "bao hiem" contribution insurance`) standing
  with a minimisation verb (`less lower reduce cut avoid save skip "not pay"
  giam tranh bot ne "khong dong"`). Neither half is suspicious alone — "what
  does BHXH mean" is the question this system exists for — and their
  CO-OCCURRENCE is what no amount of rewording removes.
  Single words are matched as whole TOKENS, never substrings: `ne` inside
  "net" or `bot` inside "bottom" would have refused half the module.
  **The rule this leaves behind: a safety guard written as a list of examples
  is a list of examples. Write the PROPERTY, then test the examples against
  it.**
- **KNOWN AND ACCEPTED OVER-CAPTURE, disclosed rather than discovered later:**
  "why is my insurance contribution lower this month" pairs `insurance` with
  `lower` and is refused. It is a fair question. The refusal is not a dead end
  — `compliance` explains where the rates live and who owns the policy, which
  is a reasonable answer to it — and on a statutory obligation, over-refusing
  is the direction to err in.
- **`_CURRENCY_AMOUNT` ENDED IN `\b` AND `₫` IS NOT A WORD CHARACTER.** So the
  boundary required a word character to FOLLOW the currency mark, which at the
  end of a sentence there never is: `12.000.000 ₫` scrubbed to `[amount] ₫`.
  The rule failed on the exact input it was written for, and the D2 ledger
  bullet about rule ordering claimed that outcome had been avoided. `(?!\w)`
  is what was meant. **A trailing `\b` after a non-word character is always a
  bug; it reads like a boundary and behaves like a requirement.**
- **THE TEST WAS TOO WEAK TO SEE IT.** `assertIn('[amount]', out)` passes on
  `[amount] ₫`. Every scrub case is now asserted on the WHOLE output string,
  which is the only form that can see a redaction that half-worked. **An
  assertion about a sanitiser must state the exact output, because the failure
  mode of a sanitiser is a partial success.**
- **`+84 912 345 678` walked through the phone rule**, because health_learn's
  pattern demanded a digit IMMEDIATELY after the country code — and the spaced
  international form is the one people paste out of a contact card. One
  optional separator. Unmentioned anywhere in the D2 report, which is its own
  finding: **the three patterns inherited from health_learn were reviewed for
  what they added and not for what they already missed.**
- **`create()` WAS THE BYPASS, AND `record()` WAS NEVER THE CONTROL.** Every
  internal user holds `perm_create` on `learn.question` — they must, the
  learner creates their own row — so calling `create` directly over RPC skipped
  the tenant flag, the learner's consent AND the scrub, all three of which
  lived in `record`. The gates are in `create` now; `record` keeps its copies
  only so the ordinary path refuses QUIETLY (a declined consent is a normal
  state, not an error, and a traceback in the drawer would make it look like
  one). **The rule: put the gate on the ORM method, not on the convenience
  wrapper, and then ask what else can reach the table.**
- **CONSENT COPY MUST NAME THE ATTRIBUTION.** The row carries `user_id` — it
  has to, because the delete-your-own affordance the prompt offers is only
  possible because of it — and the prompt did not say so. A notice that reads
  as though the storage were anonymous while the table names you is the wrong
  kind of reassuring. Both languages now say the stored question carries your
  name and that this is how you find and delete yours. `test_04d` asserts the
  disclosure AND that `user_id` is still required, so the copy and the model
  cannot drift apart.
  **Residual, accepted and disclosed:** an author reading the table can
  enumerate who asked what. That is inherent in attributed storage with a
  delete-own affordance, it is consented to explicitly, and the alternative
  (anonymous rows) removes the learner's ability to find their own. Consent
  itself remains unreadable to authors.
- **The drawer made two RPCs after every answer to discover that a switched-off
  feature was still off.** `collect_questions` rides along with the bundle the
  Coach already fetches, and `_maybeStore` returns before any call. Without it
  the "behaves exactly as Phase C" claim was true of the ANSWER and false of
  the NETWORK. It is a hint, never a control: a stale bundle can only fail
  closed.
- **A BLOCKLIST OF SIX MODEL NAMES HAD THE SAME WEAKNESS AS THE DENY-LIST.**
  `composer-corpus-reads-learn-content-only` was an `absent` check naming six
  product models — protection against the six somebody thought of. Rewritten as
  a new checker kind, `model-scope`: parse the file, find the method, collect
  every `self.env['x.y']` literal inside it, require each to start with an
  allowed prefix, and FAIL if none is found at all (so hiding the reads behind
  a variable breaks the build rather than passing silently). Proved by negative
  control: pointing `_corpus` at a payslip table fails the check with
  `_corpus() reads 'hr.payslip', which is outside learn.` and exit 1.
  **First `model-scope` check in the project; use it wherever the promise is a
  namespace rather than a list.**
- **What the review said we should keep doing:** the fixture-name residual in
  D2 was disclosed in the code, in the ledger and in the report — "a reduction,
  not a guarantee", with the reason the composer is safe anyway stated beside
  it. That is the standard: **name the residual where the mechanism is, not
  only in the report somebody reads once.**

### Product-hardening tickets (raise separately; do NOT fix from pb_learn)

1. **pb_statutory rosters search `[]` with no `active_test=False`**
   (pb_statutory.py:149,161) — archived records never appear even though the
   card renders an `active` badge. Raised in the Phase B review.
2. **Two sidebar leaves claim `hr.integration.connector`**, two claim
   `hr.payslip.run`, two claim `hr.contract` — correct for the sidebar,
   unusable for the Coach, absorbed by `_contested_models`. Raised in B1/C1.
3. **`payroll.ai.pulse` runs elevated and its alerts are ungated** — see
   addendum C above.
4. **`payroll.ai.config.get_provider_instance()` does not exist**, and four
   call sites swallow the AttributeError, silently disabling PDF narratives,
   the executive summary, Pulse summaries and voice input. See the top of Run
   D2. Highest value of the four: the fix is a three-line alias.

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
- **Phase C1 MOVES the Journey leaf in the sidebar.** `-u pb_learn` creates
  `pb_learn.sec_learn` ("Learning", sequence 50, between Compliance and
  Planning) and rewrites `item_learn_journey.section_id` onto it. Existing
  tenants will find the Learn leaf has left the Pay Run section — that is the
  intended change, not a data loss, and nothing in `pb_sidebar` needs touching.
  Verify after the upgrade: the sidebar shows a Learning section with one leaf,
  and the Pay Run section no longer ends with it.
- **The web asset bundle carries the new replicas.** `engine/screens.js` and
  `journey/journey.js` both changed, so if the eight new practice screens do
  not appear after `-u pb_learn`, purge the `ir_attachment` asset rows and
  restart — the standing Odoo-19 gotcha, unchanged.
- **Phase C1 touches eight templates in other modules** (pb_dashboard is read
  only; pb_approval, pb_people, pb_contracts, pb_insights, pb_explorer,
  pb_workforce_insights and pb_govt_reports gained additive `data-coach`
  attributes). Those modules need `-u` as well, or the anchors the Coach's
  Show-me points at are not in the served templates: `-u pb_approval -u
  pb_people -u pb_contracts -u pb_insights -u pb_explorer -u
  pb_workforce_insights -u pb_govt_reports -u pb_learn`.

#### Phase D — what to do at deploy time

```
-u pb_learn -u pb_demo -u pb_payroll_ai_insights
```

1. **`vi_VN` active BEFORE the upgrade**, as always — and note it now matters
   for `pb_payroll_ai_insights` too, which gained its first `i18n/vi_VN.po` in
   D1. Verify one refusal and one consent string under
   `with_context(lang='vi_VN')`.
2. **pb_demo regains four read grants on upgrade.** `_pb_demo_rewire` runs
   `post_init_demo` on every `-u`, so the ACL rows and the two read-all rules
   appear without a manual step. Verify by asking PayAI, as a demo account,
   "how was attendance last month" — it answered nothing between D1 and this
   deploy.
3. **The composer ships OFF and must stay off until somebody decides.**
   `ir.config_parameter` `pb_learn.compose_enabled` — absent is off. To switch
   on: set it to `True` AND configure a PayAI provider. There is no UI for the
   flag on purpose; turning on a path that lets a model write to a learner is
   a decision worth making at the parameter table.
4. **Question mining ships OFF and needs BOTH switches.**
   `pb_learn.collect_questions` = `True`, and then each learner is asked once
   in the drawer. With the parameter false the prompt never appears. The
   retention cron (`pb_learn.cron_learn_question_gc`) is created active and
   runs daily; it deletes nothing until there is something to delete.
5. **Asset bundle:** coach.js and coach.scss both changed, so if the composed
   badge or the consent card do not appear, purge the `ir_attachment` asset
   rows and restart — the standing Odoo-19 gotcha, unchanged.
6. **`ask()` gained a third argument** (`lang`), defaulted, so a stale browser
   tab calling the two-argument form keeps working through the transition.

**F5 — RUN THE DATABASE-BOUND TESTS. This is a deploy-time REQUIREMENT, not a
suggestion.** There is no odoo-bin on the development machine, so the offline
replay harness executes only what can be executed without one; everything else
reports SKIP and has therefore never run anywhere. As of the Phase D review
round that is **4 methods in D1 and 22 in D2** — including every access-control
assertion in the program.

```
odoo-bin -d <db> -u pb_learn,pb_demo,pb_payroll_ai_insights \
         --test-enable --test-tags /pb_learn,/pb_payroll_ai_insights --stop-after-init
```

The files, and what is unverified until they run:

| file | never-executed methods | what they are the only proof of |
|---|---|---|
| `pb_payroll_ai_insights/tests/test_data_access.py` | `test_03`, `test_04`, `test_04b`, `test_04c` | the individual-salary group gate actually gates — that an officer gets the aggregate and a manager gets the list |
| `pb_learn/tests/test_questions.py` | `test_01`–`test_08` (all but `test_04c`, `test_04f`) | both consent gates, the `create()` bypass fix, the record rules, delete-own, author-delete-any, the retention cron |
| `pb_learn/tests/test_composer.py` | `test_03` | a curated intent still beating the composer, with real content loaded |

Two offline passes are known to be VACUOUS rather than meaningful and must be
re-read on the server: `test_composer::test_04d` iterates the intent table,
which is empty offline, so it asserts nothing there. The standalone resolver
simulation covers the same ground against the generated XML (265 phrases, 85
column labels, 35 labels × 2 languages) and is the evidence until the suite
runs.

#### Phase C2 — the pb_coach retirement, in two deploys

**STEP 1, now (this commit). Every module below is coach-INDEPENDENT after it,
and pb_coach keeps working untouched throughout.**

```
-u pb_payroll_ai_insights -u pb_demo -u pb_learn
```

Then verify, with pb_coach still installed:
1. PayAI: ask "how do I run payroll?" → the "Show me" button opens the Journey
   on L1 rather than starting a tour. The pb_coach FAB is still at 92px and the
   Learn launcher is still at 160px — three controls, no overlap.
2. Demo login: exactly ONE disclaimer chip (pb_coach's — pb_demo's stands down
   while the service exists), and exactly ONE first-run greeting.
3. Open a deleted demo record from a stale breadcrumb: still glides back to the
   dashboard, and the backend bundle still evaluates — the duplicate-key guard
   in pb_demo's copy of `demo_missing_record.js` is what is being verified.

**STEP 2, deploy time, as its own follow-up commit — NOT made now.**
1. `pb_payroll_ai_insights/__manifest__.py`: remove `'pb_coach'` from `depends`
   and add `'pb_learn'` in its place. PayAI opens `pb_learn.action_learn_journey`
   by name, and until that line exists the click is guarded in JS with a
   "not installed on this database" notification rather than a traceback.
2. Uninstall `pb_coach` from the database.
3. `-u pb_payroll_ai_insights -u pb_demo -u pb_learn` again, then purge the
   `ir_attachment` asset rows and restart.

Then verify, with pb_coach gone:
1. The corner is TWO controls: PayAI at 24px and the Learn launcher dropped to
   92px (`body.pb-coach-absent`).
2. Demo login: pb_demo now draws the disclaimer chip and sets
   `body.pb-demo-user` itself — the apps menu and the Discuss systray are still
   hidden, which is the CSS contract the class name preserves.
3. pb_learn greets once per login with the Journey map and a "Start here" pulse
   on LW. No spotlight starts by itself.
4. PayAI's chat still constructs: the coach service is looked up optionally, so
   its absence is a `null`, not a throw.

pb_coach's FILES are deliberately not deleted in either step. Retirement here
means nothing depends on it and its jobs have owners; deleting the module is a
separate decision with its own commit.
