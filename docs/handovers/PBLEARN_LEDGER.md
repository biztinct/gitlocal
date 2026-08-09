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
