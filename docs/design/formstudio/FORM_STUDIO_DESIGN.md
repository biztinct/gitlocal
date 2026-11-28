# Form Studio — engineering design (design stage, 2026-11-01)

Owner-facing report (plain English): https://claude.ai/artifact/3fUhRHoF2HUXk3yQ9NwkT2
Clickable POC: `docs/design/formstudio/FORM_STUDIO_POC.html` (published: https://claude.ai/artifact/DRAZSP2ELgsMxfdeKw6CAq)

Status: **DESIGN ONLY. Nothing built.** This document is the technical companion to the
owner report and the seed for the phase hand-overs. Everything in "Verified plumbing" was
read from the repo on 2026-11-01; re-verify file:line before coding — nothing here is
authoritative once code moves.

## 0. Problem statement

Let a tenant administrator add / edit / delete custom fields on Payobook's **premium**
record screens (OWL cockpits and drawers, not native archs) and add / reorder columns on
premium list screens — Odoo-Studio-like UX on screens that have no `ir.ui.view` arch to
inherit.

## 1. Verified plumbing (do not re-derive)

### 1.1 Rendering engines
- VU Form Engine lives in **`biz_theme`** (not pb_theme): `biz_theme/static/src/js/vu_form_compiler.js`
  (`FormCompiler.compile` patch :116-163; `compileGroup` :165-187 tags every inner group
  `vu-sec` → card), `vu_form_renderer.js` (`VU_EXCLUDED_MODELS` :16-21 = res.config.settings,
  base.module.update, base.language.install, ir.module.module; engine off in dialogs and
  x2many subviews). `pb_theme/views/vu_native_forms.xml` only holds opt-outs and its line-8
  comment points at the wrong path.
- `vu-form-native` opt-outs (stock rendering): **hr.employee** (`vu_native_forms.xml:9-19`),
  **hr.contract** (`:21-31`), `biz.theme`, 7 pb_training authoring forms
  (`pb_training/views/authoring_studio.xml`).
- Consequence: an inherited view adding `<group name="x_pbfs" string="Company details">` to
  any *non*-opted-out native form is carded by VU for free. On hr.employee / hr.contract it
  renders stock.
- No VU list engine. Native lists are stock + CSS (`biz_theme/static/src/scss/backend.scss:754,1484-1490`).

### 1.2 Existing custom-field mechanisms
- **None in our modules**: no `ir.model.fields` creation, no `state='manual'`, no
  `web_studio`, no `fields.Properties` in pb_*/biz_*.
- Stock (vendored hr, so present on the server's newer hr too): `hr.employee.employee_properties`
  (`hr/models/hr_employee.py:216`) with definition on `res.company.employee_properties_definition`
  (`hr/models/res_company.py:11`), already on the native employee form
  (`hr/views/hr_employee_views.xml:152`). Not on hr.contract / hr.version / om_hr_payroll.
  `hr.applicant.applicant_properties` per job.
- Closest in-house precedent for "admin-defined fields": Hiring application-form builder,
  `pb.hiring.form.field` (`pb_hiring/models/forms_p2.py:659`), answers in
  `hr.applicant.pb_form_answers` JSON (`:843`), rendered in the candidate drawer (`:1388`).
  Questionnaire semantics, not record fields — keep separate.

### 1.3 How the premium screens get their fields (all hard-coded unless noted)
| Screen | Source of fields | Write path |
|---|---|---|
| Employee detail (C) `pb_people/static/src/js/employee_detail.js` | dict in `get_employee_detail` (`pb_people/models/pb_people.py:433-497`) | read-only; "Advanced form" door |
| Employee 360 drawer (D) `pb_employee_vault/static/src/js/employee_360.js` | reuses `get_employee_detail` + docs/timeline (`pb_people_360.py:96-121`) | read-only; registries `pb_people_drawer` (`employee_360.js:257`), `pb_employee_360_chips` (`:60-66`) |
| **Contract 360 drawer (D)** `pb_contracts/static/src/js/contract_360.js` | **descriptor** `_TERM_GROUPS` + `_TERMS = [(group, field, label, kind, hint, optional)]` (`pb_contracts/models/pb_contract_360.py:63-115`); `_cd_terms`/`_cd_field_entry` (`:633-736`) emit `{key,label,fields:[{name,label,kind,value,display,required,writable,hint,tone,options?,comodel?}]}` | `save_contract_360` (`:1562`) → `_cd_judge` (`:1176`) whitelist via `_cd_writable_map` + coercion (`:1213-1295`) → `contract.write`; m2o lookups gated by `_M2O_WHITELIST` (`:58-61`); needs `hr_contract.group_hr_contract_manager` (`:252`) |
| Contract detail (C) | dict `get_contract_detail` (`pb_contracts/models/pb_contracts.py:282`) | read-only |
| Records Desk (F) `pb_records/static/src/js/records_desk.js` | "cards" from `hr.payslip.import.mapping` per scheme (`pb_records_desk.py:248-330`); scheme 0 curated `_master_fields` (`master_records.py:12-20`) | `record.write({card['field']: value})` (`:1375-1377`); **column chooser persisted in localStorage** (`records_desk.js:45-46,247-277`) |
| Ledger cockpits (F/D) | generic descriptors (`pb_payrun_ledgers/models/ledger_cockpits.py:283-311,493-535`) drawn by `LedgerCockpit` (`ledger.js:50`) | read-only |
| People roster / Contracts board (F) | card grids, row dicts (`pb_people.py:356-384`, `people.xml:63`, `contracts.xml:51`) | n/a — **no table, no column model** |
| Payruns board (F) | fixed `<th>` table (`pb_payruns/static/src/xml/payruns.xml:198-206`) | n/a |

- Generic renderer by `kind`: `pb_contracts.CdEditor` nine-way switch
  (`pb_contracts/static/src/xml/contract_360.xml:65-112`), section loop `:273`. **This is the
  component to generalise.**
- `pb_filter_kit` (`pb.filter.mixin`, `pb_filter_kit/models/filter_mixin.py:49`, ~30 boards)
  owns filters/sorts/saved views; saved views persist per user / shared in `pb.filter.view`
  (`pb_filter_kit/models/filter_view.py:14-28`). **No column model** — the natural home for one.

### 1.4 Catalogues a new `x_` field must reach
| Consumer | Dynamic today? | Seam |
|---|---|---|
| Mapping Studio destinations | **Yes** — `_ec_right_items` searches `ir.model.fields` (`pb_formula_studio/models/pb_formula_studio.py:10828-10858`), filtered by `_ec_is_mappable` (`:10530-10574`), lanes `_EC_LANES` (`:10251-10282`), fallback lane `:10283` | nothing; appears in "Other employee/contract fields" |
| Mapping-based import (`hr.payslip.import.mapping.target_field_id`) | Yes | nothing |
| **Formula input sources** ("records" lane) | **No** — curated tuples `EMPLOYEE_FIELDS`/`CONTRACT_FIELDS`/`RELATED_FIELDS` (`pb_hr_payroll_formula/models/application_domain_sources.py:16-48`), consumed by `_application_source_catalogue` (`:142`) | append flagged `x_` fields at runtime |
| Records Desk master scheme | No — `_master_fields` | append |
| Explorer | No — `_DIMENSIONS`/`_MEASURES` over `pb.fact` (`pb_explorer/models/pb_explorer.py:66,118-152`), `export_csv` `:2097` | later phase |
| Access Studio field sensitivity | No — `RESOURCES` in `biz_access/models/studio_catalogue.py` | later phase |
| Employee import wizard | No — fixed 13-value Selection (`pb_hr_payroll_base/wizards/employee_import_wizard.py:886-900`) | legacy; leave |

### 1.5 Naming, entry points, gating
- Names taken: Formula Studio, Mapping Studio, Grid Studio, Payslip Studio, Access Studio,
  Theme Studio, Feed Studio. **"Form Studio" / `pb_form_studio` / `FormStudio` are free.**
- Settings hub card: `CATEGORIES` in `pb_settings/static/src/js/settings_hub.js:135`, gated
  server-side by `resolve_gates` (`pb_settings/models/pb_settings.py:108`). Sidebar: all
  `pb_sidebar_data.xml` items are retired; live rail = 13 hubs, lenses registered per module.
- Admin gates: `base.group_system` (`pb_settings/models/pb_settings.py:32`,
  `pb_tenants/models/service.py:273-276`); `pb_hr_payroll_base.group_payroll_super_admin`;
  `biz_access.group_access_manager`.

### 1.6 Screen census (inventory agent, 2026-11-01)
A native+VU 54 · B native stock 11 · C OWL detail 14 · D OWL drawer 31 · E native list 55
(98 archs with `optional=`) · F OWL board/table 88 · G guided wizard 17 · portal ≈38 QWeb pages.
Models spanning most types: hr.employee (F+D+C+B+E+G), hr.contract (F+D+C+B+E+G),
hr.payslip.run (G+F+D+A+E).

## 2. Architecture

### 2.1 Storage decision: manual `ir.model.fields` (recommended) over Properties
| | Manual `x_` fields | `employee_properties` |
|---|---|---|
| Real column, SQL-filterable, group-by, ORM domain | yes | JSONB; partial |
| Visible to Mapping Studio / mapping import automatically | yes (1.4) | no |
| Usable as formula input | yes, via 1.4 seam | would need a JSON accessor in safe_eval context |
| Field-level visibility | `ir.model.fields.groups` works natively | per-definition only |
| Exists on hr.contract / hr.payslip.run | yes | no |
| Cost of create | `ALTER TABLE ADD COLUMN` (fast, brief lock) + registry reload signal | none |
| Available on CE 19 | yes (`state='manual'`, `x_` prefix enforced) | yes |

Recommendation: manual fields. Keep Properties as an explicitly rejected alternative in the
owner report (decision 1).

### 2.2 New module `pb_form_studio` (depends: `pb_import_kit`, `pb_filter_kit`, `biz_access`?, `pb_people`, `pb_contracts` → or make the screen hooks live in those modules and keep the engine dependency-free; **engine must not depend on screens**).

Server (`models/`):
- `pb.form.layout` — `model` (char, indexed), `company_id`, `version` (int), `sections` (Json),
  `published_by`, `published_at`, `draft_json` (per-user drafts: separate `pb.form.layout.draft`
  with `user_id`). One layout per (model, company). Sections JSON:
  `[{id, title, icon, tone, kind:'open'|'locked', fields:[{name, order}]}]`. Only `open`
  sections carry fields; `locked` ids are declared by the screen (see 2.4) and never stored.
- `pb.form.field.meta` — `field_id` (m2o ir.model.fields, ondelete cascade), `vis`
  (`all|hr|admin`, materialised to `ir.model.fields.groups` so ORM enforces it), `list_ok`,
  `formula_ok`, `help_vi`, `label_vi`, `order`. Standard fields get a meta row only when touched.
- `pb.form.studio` (AbstractModel, facade, every method `@api.model`, admin-gated):
  - `get_studio(model)` → `{layout, fields:{name:{label,type,std,locked,reason,vis,...}}, palette_types, can_publish, blockers}`
  - `create_field(model, {type,label,options,comodel,vis,required,...})` → creates
    `ir.model.fields` `state='manual'`, `name=f"x_pbfs_{slug}"`, `model_id`, `ttype`, `selection_ids`,
    `relation`, `store=True`, `copied=False`; `tracking=False`; wraps in a savepoint; refuses
    while a pay run is computing (check `hr.payslip.run` state in progress / the run driver lock).
  - `update_field` (label/help/vis/required/options/list_ok/formula_ok; **never ttype**)
  - `delete_field` → preflight `field_references(name)` across: formula sources, `hr.payslip.import.mapping`,
    import templates, pb.filter.view columns, Explorer specs; returns blockers; otherwise unlink
    (Odoo drops the column).
  - `save_draft(model, sections)` / `publish(model, sections)` → bump version, audit entry
    (`biz.audit.mixin` precedent), bus notify `pb_form_studio/published` so open screens reload.
  - `list_columns_get(board_key)` / `list_columns_save(board_key, cols, scope)` → stored on
    `pb.filter.view` (add `columns` Json) for `scope='me'`; company default on a new
    `pb.list.layout` (board_key, company_id, columns).
- Locked-field registry: a per-model constant `LOCKED = {'hr.employee': {'name':reason,'barcode'...}}`
  extended by other modules via a hook `_pbfs_locked_fields(model)`; payroll-critical names come
  from `pb_hr_payroll_formula` (wage, date_start, date_end, struct_id, bank account ids…).

Client (`static/src/js/`):
- `PbFieldGrid` — generalised `CdEditor`: props `{sections, values, writable, onChange}`; one
  switch on `kind` (char/text/integer/float/monetary/boolean/date/selection/many2one/binary);
  reused read-only (detail pages) and editable (drawers).
- `FormStudioOverlay` — mounts over the host screen; palette (New / Add existing), drop zones,
  props panel, publish sheet, HTML5 DnD; emits layout to the facade. One instance per host via
  a `useFormStudio(model, hostKey)` hook that also renders the toolbar wand button
  (gated on `get_studio().can_edit`).
- `ListStudio` — columns panel for boards exposing a `columnSpec` (see 2.5).
- `FieldLibrary` client action (Settings hub card).

### 2.3 Field visibility
Map `vis` → `ir.model.fields.groups`: `all` = none, `hr` = `hr.group_hr_user`, `admin` =
`base.group_system`. The ORM then hides the field from reads for others (Odoo strips fields
the user can't access from `read`/`fields_get`); screens must tolerate missing keys.
Portal (`/my`) only shows `vis='all'` fields, read-only.

### 2.4 Screen hook contract (the thing each premium screen implements once)
Each host declares `{model, host_key, sections:[{id,title,kind}], values_fn}`; the facade
merges the stored layout with the host's locked section list so a layout can never place a
field in a locked zone. Hosts and seams:
- Employee detail: extend `get_employee_detail` payload with `custom_sections` (from
  `pb.form.studio.render(model='hr.employee', rec)`), render with `PbFieldGrid`.
- Employee 360: same payload; register a drawer tab via `pb_people_drawer` registry if the
  section list grows.
- Contract 360: append custom fields to `_cd_terms` output as an extra group `('custom',
  "Company details")`; extend `_cd_writable_map` with `x_pbfs_*` fields that are `writable`;
  `_M2O_WHITELIST` → allow comodels from the field meta.
- Pay run record (native arch, A): plain inherited view adding `<group name="x_pbfs">` —
  VU cards it; the layout store still drives field order via a small compiler hook if needed.
- Employee / Contract advanced forms (B, stock look): same inherited-view approach; UX debt
  noted (owner decision 4).

### 2.5 Lists
- A board exposes `columnSpec = [{key,label,kind,drawn:bool,pin:bool,default:bool}]` and
  reads `effective columns` = company default → user override. Custom fields with `list_ok`
  are appended to the spec automatically from `ir.model.fields`.
- Roster and Contracts board are card grids → ship a **table mode** (clone Payruns' table) as
  the precondition. Records Desk already has a chooser; migrate its localStorage persistence to
  `pb.filter.view.columns` so "Just me" survives devices.
- Native lists (E): untouched — Odoo's `optional=` already does per-user columns.

### 2.6 Safety rails (engineering form)
- All facade methods: `self.env.user.has_group('base.group_system')` (owner decision 3 may
  widen) + `check_access_rights` on the target model; writes never `sudo()` the record.
- `create_field` refuses while any `hr.payslip.run` is computing; and in a transaction that
  already touched payroll tables.
- `delete_field` is reference-checked (2.2) and requires the typed confirmation client-side;
  server re-checks blockers.
- Layout fallback: unknown section id → fields move to `custom` section; never dropped.
- Audit every publish (who/when/diff) via `biz.audit`-style entry; bus-notify open screens.
- White-label rule: no "Odoo" in any user-visible string, incl. the technical-name helper.
- Design mandate: Payobook tokens, Lucide icons (wand-sparkles for Studio), QuietGlance where
  counts appear; Studio chrome = brand violet over whatever identity the host screen has.

## 3. Phases (proposed hand-overs)
1. **FS-1 Engine** — `pb_form_studio`: models, facade, locked registry, `PbFieldGrid`,
   `FormStudioOverlay` (no host yet; test host = a dev client action). Tests: create/update/
   delete field incl. blockers; vis→groups; publish/draft/version; run-in-progress refusal.
2. **FS-2 Employee** — hooks in `pb_people` + `pb_employee_vault`; Field library card in
   Settings; wand button gating. Chrome-validated.
3. **FS-3 Lists** — table mode for roster; column model in `pb_filter_kit`; ListStudio;
   Columns button for all users; Records Desk persistence migration.
4. **FS-4 Contract** — Contract 360 `_TERMS` extension + writable map; Contract detail/board;
   `formula_ok` fields appended to `application_domain_sources` catalogue; Formula Studio shows
   them in the records lane.
5. **FS-5 Reach** — exports/imports append custom columns; Records master fields; Explorer
   dimensions; Access Studio catalogue; `/my` profile read-only; vi_VN labels; Learn lessons.
6. **FS-6 Pay run + HR boards** — native-arch inherit for `hr.payslip.run` + run drawer; then
   per-board hooks.

## 4. Open decisions (owner) — mirrored in the owner report §8
1. Manual fields (recommended) vs Properties bundle.
2. Employee self-service edit of `vis=all` custom fields (recommend read-only + change request).
3. Studio admin = `base.group_system` only (recommended) vs + payroll super admin.
4. Re-skin Employee/Contract advanced forms (separate job) or leave.
5. Phase order: Lists before Contract (recommended) or the reverse.

## 5. Research notes
- Odoo Studio (Enterprise): wand icon → edit mode over the live view; new fields are
  `ir.model.fields` manual with `x_studio_` prefix; layout changes are inheriting `ir.ui.view`
  records; the whole customisation exports as a module. CE has the engine (manual fields,
  view inheritance) without the UI.
- Salesforce: field defined once (Object Manager), placed per page (Lightning App Builder,
  Dynamic Forms) with field/section visibility rules; standard fields undeletable; hidden
  required fields still block save.
- HubSpot: properties in Settings; per-record-card "Customize properties"; admin default vs
  per-user view; cap 50 per section; custom tabs Enterprise-only.
- Zoho People / BambooHR: form customiser with sections and role permissions; BambooHR is
  criticised for custom fields that don't reach reports — hence FS-5 "Reach" is a phase, not
  a nice-to-have.
- monday/Airtable: the column *is* the field; drag to reorder; types fixed after creation.
