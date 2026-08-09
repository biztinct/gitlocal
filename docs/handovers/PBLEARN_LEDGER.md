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
