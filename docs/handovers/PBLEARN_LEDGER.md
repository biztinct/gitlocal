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
