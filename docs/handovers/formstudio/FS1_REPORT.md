PAUSED 2026-11-19 — owner pause. DONE: spec read (FS1 handover, ledger incl. R5–R9,
design, POC, WDGAP rules + ledger gotchas, FS_HOST_FACTS.md); plumbing verified (below);
design of the engine settled (below). NO CODE WRITTEN YET, no local database made, no
server started. NEXT: build `pb_form_studio` per the plan below, including the two queued
coordinator inputs: (1) FS_HOST_FACTS — pay-run guard on the best existing signal
(§E) + DDL `lock_timeout`; import-mapping blocker (§F, `target_field_id` ondelete
cascade); host contract to cover a read-only list/export render and a copy-names helper;
(2) engine helpers (a)–(e) from `FS_HOSTS_HANDOVER.md` (MAIN checkout — skim on resume):
(a) `_pbfs_sync_native_view(model, parent_view_xmlid, page_title)`; (b)
`fields_for(model, purpose)` with purposes 'list' / 'formula' / 'everyone' and the
`list_ok` / `formula_ok` switches in the properties panel; (c) `copy_field_names(model)` +
per-host default for `copied` (contract host True, R7); (d) extensible reference finders
(hook) with the import-mapping finder in the engine; (e) "Used by" in the properties panel
and the Field library. Then tests 1–16, browser walk, this report in full (THE HOST
CONTRACT section), commit + push.

# FS-1 — Form builder engine (`pb_form_studio`) — report (in progress)

## Verified facts (origin/19.1 @ ef422ae4a, core = ~/odoo19/odoo)

| # | Fact | Where |
|---|---|---|
| V1 | **`ir.model.fields.groups` is NOT applied to manual fields** — core marks it "CLEANME unimplemented field (empty table)"; `_instanciate_attrs` never reads groups. Design §2.3 ("materialise vis to `ir.model.fields.groups` so the ORM enforces it") does not work as written. | core `odoo/addons/base/models/ir_model.py:562`, `_instanciate_attrs` :1293-1362 |
| V1-fix | Plan: `_inherit ir.model.fields`, add column `pbfs_groups` (Char); `_all_manual_field_data` is `SELECT *` (:1276-1287) so the row carries it; override `_instanciate_attrs` to set `attrs['groups']` from it. Then `fields_get` / `read` / `_has_field_access` enforce it (core `odoo/orm/models.py:3375,3390,3442`). Changing it = write on ir.model.fields → `_setup_models__` → `registry_invalidated` → signalled to other workers. Risk to report: uninstalling `pb_form_studio` drops the column and the fields lose their visibility limits. | |
| V2 | create / unlink / write of manual fields run `_setup_models__` + `init_models`; `_setup_models__` sets `registry_invalidated` (signalled after commit). Type change refused by core. Unlink drops the column (`_drop_column`). Name must start `x_` (DB constraint). | `ir_model.py:1028-1069`, :988-1025, :1071-1160, :864-897, :659-660; `odoo/orm/registry.py:408-433,1137-1167` |
| V3 | Labels/help per language: `field_description` / `help` are translated jsonb; `get_field_string` / `_get_fields_cached` serve the user's language. Write with `lang` context per active language. | `ir_model.py:1368-1407` |
| V4 | No pay-run "computing" state or lock: run states draft/level1/level2/done/cancel; compute is client-driven chunks `prepare_run` → `compute_batch`, each its own transaction, nothing marks "in progress". | `om_hr_payroll/models/hr_payslip.py:971-977`; `pb_payrun_wizard/models/pb_payrun_wizard.py:1557,1667` |
| V5 | Practice runs do have a state: `hr.formula.shadow.run.state='computing'`. | `pb_hr_payroll_formula/models/shadow_run.py:40,52,243` |
| V6 | Settings hub: soft registry `"pb_settings_category"` (string), server gate `resolve_gates` (groups any-of, `base.group_system` resolves). Precedent registrant `pb_demo_seed/static/src/js/demo_seed_settings.js`. Registering by the string avoids a dependency on `pb_settings`. | `pb_settings/static/src/js/settings_hub.js:135,271`; `pb_settings/models/pb_settings.py:109-167` |
| V7 | `CdEditor` / `CdPicker` to clone. | `pb_contracts/static/src/js/contract_360.js:112-293` (picker), :305-437 (editor); `pb_contracts/static/src/xml/contract_360.xml:33-57,65-115` |
| V8 | Icons: `ic()` in `@pb_import_kit/js/import_icons` makes a NEW markup per call (flicker trap); has `wand` but not wand-sparkles/type/align-left/toggle/unlock/grip-vertical. Plan: own cached icon helper in the module. Tokens: `.pbim` root emits `--pbim-*` vars. | `pb_import_kit/static/src/js/import_icons.js:374-387`; `pb_import_kit/static/src/scss/import_kit.scss:55-56`, `import_tokens.scss:9-94` |
| V9 | Bus: `bus.bus._sendone(partner, type, payload)` + client `bus_service.subscribe(type, cb)`. | `biz_access/models/role_assignments.py:177-179`; `biz_access/static/src/js/access_refresh.js:14` |
| V10 | `hr.employee.currency_id` exists (related company currency, groups hr user) — money fields can use it. | `hr/models/hr_employee.py:213` |
| V11 | Audit: `biz.audit.entry` is per-field change with retention clean-up — would delete the values export. Plan: own append-only `pb.form.audit` (same append-only pattern) carrying the export attachment. | `biz_audit_trail/models/biz_audit_entry.py:37-114` |

## Engine plan (settled, to build on resume)
- Models: `pb.form.field.meta` (field, vis all/hr/admin, required, list_ok, formula_ok,
  std label override); `pb.form.layout` (host_key + company, version, sections Json,
  published by/at); `pb.form.layout.draft` (per user, base_version, full client draft);
  `pb.form.audit` (append-only, values-export attachment); `pb.form.sample` (tiny
  dev-host model — NOT res.partner: res.users `_inherits` res.partner, so a partner field
  would reach users).
- Facade `pb.form.studio`: `get_studio`, `create_field`, `update_field`, `delete_field`
  (+ `field_references`), `save_draft`, `publish` (orchestrates creates/updates/deletes +
  layout, stale-draft refusal unless overwrite, version bump, audit, bus), host methods
  `render`, `write_values`, `fields_for`, `copy_field_names`, `_pbfs_sync_native_view`;
  hooks `_pbfs_hosts`, `_pbfs_locked_fields`, `_pbfs_link_targets`, reference finders.
- Rails: admin gate on every Studio method; refuse models outside hosts, any `ir.*`,
  users/groups/access, payslip/payslip line, accounting, and any model another model
  `_inherits`; busy guard = recent draft/verify payslip writes in a draft run + other
  backends holding write locks on payslip tables + practice runs computing, and DDL under
  `SET LOCAL lock_timeout`; caps 60 / 30 / 60 chars; delete confirm = type the field's
  label; values CSV on the audit entry before the drop.
- Client: `PbFieldGrid` (read/edit), `FormStudioOverlay` + `useFormStudio` + wand
  button, `FieldLibrary` (Settings card "Form builder", system admin only), dev host
  client action (debug + admin, no menu).
