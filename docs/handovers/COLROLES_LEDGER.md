# COLROLES — Column Roles & People-Data Mapping: conventions + gotcha ledger

Program: declutter Formula Studio via a first-class `column_role` on `hr.formula.rule`, typed
(text-capable) contract components, studio-native people/bank mapping, import auto-classification.
Approved plan: `~/.claude/plans/i-want-you-to-giggly-hummingbird.md`. Phases: 1 roles-exist (backend),
2 studio lens, 3 mapping+bank, 4 review polish. Every handover references this file; every phase
appends gotchas here (CR-numbered).

## Standing rules (bind every phase)

- **White-label**: no user-visible string may contain "Odoo" — UI labels, help=, selection labels,
  errors, .po msgstr. Technical identifiers (`from odoo import`, xml ids) untouched.
- **Terse output**: one-line bash where possible; no heredoc dumps of file contents into the chat.
- **Commit per feature**: explicit file staging, reviewer-focused message, do NOT push.
- **Deploy ritual** (proven): rsync modules → `/tmp/stage/` → sudo rsync into
  `/odoo/odoo-server/addons/` → `sudo service odoo-server stop` → detached
  `systemd-run --collect --unit=<u> /bin/bash /tmp/<u>_run.sh` looping
  `odoo-bin -c /etc/odoo-server.conf -d <db> -u <mods> --stop-after-init` over
  **abm acme payobook payobook_template** with `EXIT[$db]=$?` sentinel + `touch /tmp/<u>.done` →
  poll done-file → `service odoo-server start` → `systemctl is-active` + port 8069 bound.
  Never `pkill -f odoo-bin`. Odoo logs to /var/log/odoo/odoo-server.log (binary-ish: grep -a).
- **Migrations**: `migrations/<full-version>/post-<sentence_slug>.py`, WHY / WHAT-IS-NOT-TOUCHED
  docstring, `table_exists` guard (shared addons tree, per-DB schemas), idempotent, only rewrite
  rows still carrying shipped values, log per-DB counts.
- **Asset cache**: any JS/SCSS/XML-asset change ⇒ bump pb_formula_studio manifest version and `-u` it;
  SCSS errors surface only at page load (Chrome-MCP check), never in `-u` output.
- **Live validation**: Chrome MCP against https://payobook.com (apex admin ash@biztinct.com/admin1234,
  Formula Studio action id 1160) and https://abm.payobook.com (action id 742; owner logs in when needed).
- **Version counters at program start**: pb_hr_payroll_formula 19.0.1.65.0 · pb_formula_studio
  19.0.1.107.0 · om_hr_payroll 19.0.1.0.2 (om stays untouched — CR1).

## Locked architecture decisions

- CR-A1 `column_role` selection on hr.formula.rule: payroll(default)/identity/profile/contract/bank/
  reference + `column_role_source` auto|user. Auto-writers must never overwrite source='user'.
- CR-A2 Amount contract components keep role **payroll** (they feed calculation); TEXT contract
  components get role **contract**. `is_contract_component` stays an orthogonal boolean.
- CR-A3 Typed components: `value_type` amount|text on the advantage TEMPLATE, `text_value` on the
  advantage LINE — implemented via `_inherit` **in pb_hr_payroll_formula**, NOT by editing
  om_hr_payroll (avoids `-u om_hr_payroll` reverse-dep cascade across every dependent module on 4
  prod DBs). Views extending the contract form also live in pb_hr_payroll_formula.
- CR-A4 Excel authoring: red header font = contract component with value type INFERRED from samples;
  green header font = explicitly-text component (authoritative); +underline = requires_new_contract
  for both colours. Header-band font only — no clash with green FILL (formula row) or green-font
  constant value cells.
- CR-A5 Classifier = pure-Python module `pb_hr_payroll_formula/models/column_role_classifier.py`
  (module-level lexicons/functions, no model) — importable by wizards, batch, migration, studio RPC.
- CR-A6 Uncertainty bias: unclassifiable columns default to **payroll** (wrong-payroll = clutter;
  wrong-reference = broken pay).
- CR-A7 Behavior neutrality until a human acts: Phase 1 must produce byte-identical batch outputs
  for existing configs; role-based input exclusion ships Phase 3 with a formula_dependencies guard.

## Gotchas discovered (append per phase)

- CR1 (design): `-u om_hr_payroll` re-validates every dependent module (historic broken-`<report>`
  cascade risk) — hence CR-A3 _inherit strategy.
- CR2 (design): `formula_dependencies` is a comma-joined codes Char (formula_rule.py:1217
  `','.join(unique_refs)`); parse with split(',').
- CR3 (design): `mapSuggest`/`mapAcceptAll` (formula_studio.js:4462-4485) hardcode the cycle-mode
  RPC name regardless of `_mapPrefix` — latent bug; MUST be fixed in Phase 3 alongside
  employee_mapping_suggest or accept-all drives the wrong adapter.
- CR4 (design): pb_hr_workforce_planning inherited views xpath-anchor on `component_type` nodes in
  formula_rule list views — never move/rename those nodes; place new Role fields elsewhere.
- CR5 (P1): the colour-import "identifier row" (`identifier_map`, formula_import_wizard.py:765-771 /
  multisheet :2151-2158) holds **payslip section codes** — live abm values are `ITAXABLEINCOMECC`,
  `IINONTAXABLEINCO` — NOT employee identifiers, and it is populated for nearly every column.
  Feeding it to the classifier as `on_identifier_row` would classify the whole workbook as identity.
  The wizards therefore pass `on_identifier_row=False` and hand the band to `band_label` instead;
  the parameter stays in the classifier API for a caller that genuinely has that signal.
- CR6 (P1): `rsync -a` PRESERVES local file modes, and files created on the Mac land 0600 →
  `/odoo/odoo-server/addons/<mod>/__manifest__.py` became root-readable only, the odoo user could
  not read it, and the upgrade logged `manifest not found` + `not installable, skipped` while
  odoo-bin still exited **0** on all four DBs. A green EXIT sentinel is NOT proof of an upgrade.
  Always `sudo chmod -R a+rX` the synced module dirs after the rsync, and verify
  `ir_module_module.latest_version` in psql before believing the deploy.
- CR7 (P1): on hr.employee the payroll code field is `employee_id` (a Char, not a relation) — it is
  what the VPTQ structures map "MSNV" onto. Any identity-field allow-list must include it or the
  employee code itself gets filed as mere profile data.
- CR8 (P1 decision): a **lexicon** hit may never promote a column to `identity` in the migration —
  identity short-circuits `_is_employee_code_rule`, which switches value normalisation from float
  coercion to raw string, and that would break CR-A7 neutrality on an existing config. Only marker
  or field-mapping evidence assigns identity there; a lexicon identity hit is demoted to `profile`.
  The studio `reclassify_roles` RPC has no such restraint (it is an explicit human-triggered act).
