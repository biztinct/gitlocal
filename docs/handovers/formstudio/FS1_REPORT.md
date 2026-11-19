# FS-1 — Form builder engine (`pb_form_studio`) — report

Branch `fs-1` (from `origin/19.1` @ ef422ae4a). New module `pb_form_studio` **19.0.1.1.0**
(19.0.1.0.0 = first delivery; 19.0.1.1.0 = follow-up R14 "fields on My Payobook" + bounded
pay-run signal, §13). No existing module was edited. Not deployed. Local databases dropped.

## 1. Verified facts (origin/19.1 @ ef422ae4a; core = ~/odoo19/odoo)

| # | Fact | Where |
|---|---|---|
| V1 | **`ir.model.fields.groups` is NOT applied to manual fields** on this build: core marks the column "CLEANME unimplemented field (empty table)" and `_instanciate_attrs` never reads it. Design §2.3 ("materialise vis to `ir.model.fields.groups`") would restrict nothing. | core `odoo/addons/base/models/ir_model.py:562`, `_instanciate_attrs` :1293-1362 |
| V2 | `_all_manual_field_data` is `SELECT * FROM ir_model_fields WHERE state='manual'`, so any column added to `ir_model_fields` reaches `_instanciate_attrs` in `field_data`. | `ir_model.py:1276-1287` |
| V3 | Field access: `_has_field_access(field, op)` checks `field.groups` (overridable per model); `fields_get` drops the field, `read([...])` / `search_read` / `web_search_read` / a domain on it / `write` raise `AccessError`, `read()` with no list skips it. | `odoo/orm/models.py:3375-3435` |
| V4 | create / write / unlink of manual fields run `_setup_models__` (+ `init_models`); `_setup_models__` sets `registry_invalidated`, signalled after commit, other workers reload on their next request. Core refuses a type change and refuses to drop a field a view still names. | `ir_model.py:1028-1069, 1071-1160, 988-1025, 963-974`; `odoo/orm/registry.py:408-433, 1137-1167` |
| V5 | Labels/help are translated jsonb; `get_field_string` serves the user's language. Writing with `lang` context stores a translation. | `ir_model.py:1368-1407` |
| V6 | Removing a choice from a manual selection sets the records holding it to empty (`set null`). The engine refuses to remove a choice still in use instead. | `ir_model.py:1757-1830` |
| V7 | No pay-run "computing" state or lock: run states draft/level1/level2/done/cancel; compute is browser-driven chunks (`prepare_run` → `compute_batch`), nothing marks "in progress". Practice runs have `state='computing'`. | `om_hr_payroll/models/hr_payslip.py:971-977`; `pb_payrun_wizard/models/pb_payrun_wizard.py:1557, 1667`; `pb_hr_payroll_formula/models/shadow_run.py:52, 243`; FS_HOST_FACTS §E |
| V8 | `hr.payslip.import.mapping.target_field_id` is `ondelete='cascade'` — deleting a field silently deletes its pay-data import mappings. | `pb_hr_payroll_formula/models/payslip_import_mapping.py:56-63`; FS_HOST_FACTS §F |
| V9 | Settings hub soft registry is the string `"pb_settings_category"`; the server gate `resolve_gates` answers on the descriptor's `groups`. Registering by the string needs no dependency on `pb_settings`. | `pb_settings/static/src/js/settings_hub.js:135, 271`; `pb_settings/models/pb_settings.py:109-167` |
| V10 | `CdEditor` / `CdPicker` (cloned, not imported). | `pb_contracts/static/src/js/contract_360.js:112-293, 305-437`; `pb_contracts/static/src/xml/contract_360.xml:33-115` |
| V11 | Kit `ic()` makes a NEW markup per call (flicker trap on redraw) and lacks several glyphs; tokens are `--pbim-*` on any `.pbim` root. | `pb_import_kit/static/src/js/import_icons.js:374-387`; `pb_import_kit/static/src/scss/import_kit.scss:55-56` |
| V12 | Bus: `bus.bus._sendone(partner, type, payload)` + `bus_service.subscribe/unsubscribe`. | `biz_access/models/role_assignments.py:177-179`; core `bus/static/src/services/bus_service.js:215-234` |
| V13 | `.pbfs` CSS class prefix is TAKEN by `pb_formula_studio` (Formula Studio). The Form builder's classes use **`.pbfb`**. | `pb_formula_studio/static/src/scss/*.scss` |
| V14 | `biz.audit.entry` has a retention clean-up that would delete the values file of a deleted field; the engine keeps its own append-only `pb.form.audit`. | `biz_audit_trail/models/biz_audit_entry.py:88-114` |
| V15 | `res.users` `_inherits` `res.partner`, `hr.employee` `_inherits` `hr.version`: a field on the parent reaches the child. The engine refuses any model another model `_inherits`. | registry `_inherits` |

## 2. How visibility is enforced (the V1 finding) — and what is and is not protected

- **Fix:** `pb_form_studio` adds one column, `ir_model_fields.pbfs_groups`, and overrides
  `ir.model.fields._instanciate_attrs` (`models/ir_model_fields.py`) to turn it into the field's
  real `groups=` for `x_pbfs_*` fields only. "Who can see it" writes it (`all` → none, `hr` →
  `hr.group_hr_user,base.group_system`, `admin` → `base.group_system`); the write re-runs the
  registry setup, so every worker follows.
- From then on **core enforces it on every path**, so a hidden field's VALUE cannot be read by a
  user who should not see it through: `render` (only fields the caller may read), `fields_for` /
  `values_for`, the native page (core strips the node from the screen design for that user), and
  plain RPC — `read()` skips it, `read([f])`, `search_read`, `web_search_read`, a search on it and
  `write` raise AccessError. Proven by test 21 (and test 2, test 12 after `-u`).
- **Country of Work (R10) is applicability, not secrecy.** `render`, `write_values` (refused),
  `values_for` (blank cell) and the native page (`invisible=` on the host's country field) honour
  it per record. A plain RPC `read` by somebody who may see the field at all still returns the
  value of a record in another country (the ORM has no per-record field rule). Strongest protection
  added: the only write path the engine offers refuses it; `required` applies only where the field
  applies. A per-record read block would need a `read` override on every host model — not done.
- `'everyone'` purpose (self-service, R3) is decided from the setting, not from the caller, so it
  is safe around a sudo record (test 21).
- Risk to note: uninstalling `pb_form_studio` drops `pbfs_groups`; the fields would then show to
  everyone who can open the record. Uninstall is not a supported path.

## 3. What was built

Server (`pb_form_studio/models/`):
- `ir_model_fields.py` — V1 fix above.
- `form_field_meta.py` — `pb.form.field.meta`: `vis`, `is_required`, `list_ok` ("Show in lists"),
  `formula_ok` ("Use in pay formulas"), `country_ids` (R10; empty = all countries), `host_key`.
- `form_layout.py` — `pb.form.layout` (per host + company: version, open sections, published by/at),
  `pb.form.layout.draft` (per administrator: full client draft + `base_version`), `pb.form.audit`
  (append-only; values file attached on delete).
- `form_sample.py` — `pb.form.sample`, the dev host's tiny model (not res.partner, V15).
- `form_native_view.py` — `pb.form.native.view` + the native-page sync (§5 a).
- `form_studio.py` — facade `pb.form.studio` (line numbers at fs-1 head): hooks `_pbfs_hosts` :105,
  `_pbfs_locked_fields` :145, `_pbfs_link_targets` :153, `_pbfs_reference_finders` :166; rails
  `_pbfs_model_forbidden` :192, `_pbfs_busy` :215; layout `_pbfs_effective` :493; Studio
  `can_edit` :553, `get_studio` :561, `create_field` :688, `update_field` :773, `field_references`
  :883, `delete_field` :1022, `save_draft` :1069, `discard_draft` :1087, `publish` :1095; hosts
  `render` :1178, `write_values` :1287, `fields_for` :1346, `_pbfs_values_for` :1389, `values_for`
  :1411, `lookup` :1421, `copy_field_names` :1439, `_pbfs_sync_native_view` :1449; `library`
  :1467, `dev_sample` :1505.
- Field types: text, long text, whole number, decimal, money (needs a `currency_id` on the record
  type, else refused in words), yes/no, date, choice list, link to a record (employee, department,
  job position, company, contact, country — `_pbfs_link_targets`), file. Names `x_pbfs_<ascii
  slug>`, collisions numbered (`x_pbfs_dong_phuc`, `x_pbfs_dong_phuc_2`).
- New fields are created **by Publish** (in the same transaction as the layout), as the POC says;
  `create_field` is also callable directly.

Client (`pb_form_studio/static/src/`, classes `.pbfb-*`, tokens `--pbim-*`, Lucide via cached
`fsIc`):
- `PbFieldGrid` (`field_grid.js/.xml`) — cards per section, read and edit mode; `PbfsEditor` /
  `PbfsPicker` cloned from `CdEditor` / `CdPicker`; locked sections via named slots.
- `FormStudioOverlay` (`studio_overlay.js/.xml`) — studio bar (Discard / Publish / close), palette
  "New field" / "Add existing" (drag, or tap on a phone), HTML5 drag between and within sections,
  locked zones, properties panel (label + other languages, help, type while new, choices, link
  target, who can see it, countries of work, required, show in lists, use in pay formulas, place in
  section, where it appears, filled count, **Used by**, hide, delete with typed name + blockers),
  draft autosave, publish sheet with a plain list of changes, stale-draft sheet, leave sheet.
- `useFormStudio` + `FormStudioWand` (`use_form_studio.js`) — gate, open/close, bus reload.
- `FieldLibrary` (`field_library.js/.xml`, tag `pb_form_library`) — quiet KPI row, filter by record
  type, search, table (field + field code, record type, type + choices, appears in, filled bar, who
  can see, countries, used by), Edit sheet, Delete sheet (blockers or typed confirmation).
- Settings card "Form builder" (`settings_card.js`, group System, `groups: ["base.group_system"]`).
- Dev host (`dev_host.js/.xml`, tag `pb_form_dev_host`, action `pb_form_studio.action_pb_form_dev_host`,
  no menu; developer mode + administrator only).
- `i18n/vi_VN.po`, `i18n/id_ID.po` (323 entries each, from `odoo-bin i18n export`), `pb_form_studio.pot`.

## 4. Tests (numbered) vs baseline

Module suite `/pb_form_studio` (`tests/test_form_studio.py`), FRESH install on a new template copy:
see §4.1 for the run. Cross-module suites that scan every module (`/biz_debrand`, `/pb_hub`,
`/pb_settings`, all three `-u`'d, S8M-1) were run with the new module AND on an `origin/19.1` tree
without it: **identical failure set, 4 of 173, none names a pb_form_studio file** —
`biz_debrand` test_rewrite.test_09 (product_for_env in scrub source), test_unreachable_names.test_01
(pb_demo_portal mail text), `pb_hub` test_palette_lens_gates (4 tabs without a ⌘K row), test_static
(z-index 30 in the hub kit). Pre-existing on origin/19.1.

| # | Case | Result |
|---|---|---|
| 1 | each of the 10 types → real stored column (binary: attachment), label right in en / vi / id via `fields_get`; ASCII slug + numbered collision | PASS (test_01) |
| 2 | update label / help / choices (keys kept, in-use choice not removable) / visibility: all → hr → admin → all; plain staff `read()` skips, `read([f])` and `search_read` raise | PASS (test_02) |
| 3 | type change refused (facade and raw `ir.model.fields.write`); standard fields not editable / deletable | PASS (test_03) |
| 4 | delete with a blocker refused and listed (saved search); wrong confirmation refused; clean delete → column gone, values CSV on the audit entry, layout cleaned; pay-data import mapping blocks (finder patched in, see §7) | PASS (test_04, test_04b) |
| 5 | drafts per administrator; publish bumps version, writes audit, clears own draft; second admin's stale draft: plain message naming who published, nothing changed; overwrite allowed on request; publish creates + places a new field | PASS (test_05, test_05b) |
| 6 | layout fallback: unknown section → custom section; locked section never holds fields; locked field returns home; unknown names dropped; no duplicates | PASS (test_06) |
| 7 | `write_values`: whitelist (standard field refused), coercion (1,204 → 1204; 2.5 refused; bad date; bad choice), nothing written when anything fails, required, ACL (staff cannot write), record rule (other company), hidden field not writable, non-host model refused | PASS (test_07) |
| 8 | refused while a pay run is being worked out — patched signal AND the real one: a draft run's payslip written just now → `create_field` refused in words (also shown on the live copy, rolled back) | PASS (test_08 + shell proof) |
| 9 | forbidden models: res.users, res.groups, ir.*, hr.payslip, hr.payslip.line, res.partner, hr.version; unknown host; link to users | PASS (test_09) |
| 10 | access matrix: HR officer, plain staff, portal refused on all 10 Studio methods; `can_edit` false for them; card gated to `base.group_system`; dev host asks the same gate; portal cannot `render` | PASS (test_10) |
| 11 | multi-worker: 2-worker server; field created in worker 58431, read by **both** workers (12/12 fresh connections saw it), deleted in 58432, gone for all; 2 registry reloads signalled; no restart (`scratchpad multiworker.py`) | PASS |
| 12 | `-u pb_form_studio,pb_import_kit` keeps fields, values (`kept-123`, `77`), meta, layout, the native page, and the `hr` field stays hidden from staff (the host module of the dev host is pb_form_studio itself) | PASS (9/9 checks) |
| 13 | silent install: after a fresh install every engine table is empty, no `x_pbfs_` field, no job / mail template / server action / mail server in the module's data | see §4.1 |
| 14 | caps: label 61 chars, per record type, per section — refused in words | PASS (test_14) |
| 15 | PO gate (vi + id from the export, three markers each) + no "Odoo" in any msgid/msgstr, template text, `_t()` or `_()` literal | PASS (test_15) |
| 16 | browser walk (desktop 1512 px + phone 390 px emulated), console clean | PASS — §6 |
| 20 | R10: field limited to India → shown / writable on an India record; absent from `render` and refused by `write_values` for a Vietnam record and a record with no country; all-countries unchanged; list column exists, cell blank elsewhere; required only where it applies | PASS (test_20) |
| 21 | hidden VALUE never reaches a reader: render, fields_for, values_for, 'everyone' around sudo, `read()`, `read([f])`, `search_read`, `web_search_read`, search on it, write, native page per user | PASS (test_21) |
| 22 | native-view sync: nothing → no view; publish regenerates; layout order; notebook added where the screen has none; `invisible` on the country field; a broken arch never replaces a good one; delete drops the field from the page first; last field removes the page | PASS (test_22) |
| 23 | `copy_field_names`; `copied` per host default (False) and per field (True carried by `copy()`) | PASS (test_23) |
| 24 | "Used by" in `get_studio` and the Field library | PASS (test_24) |
| 25 | R14 flags on custom AND standard fields (standard: settings row, no new field, still not renamable); "can change" ⇒ shown, untick shown ⇒ not changeable; administrator only | PASS (test_25) |
| 26 | refused on the server with the reason: hidden (show), locked (change), money/file (change), standard field not offered, host without a self-service page; panel gets `can_show/can_edit` + reasons | PASS (test_26) |
| 27 | `fields_for(…, 'portal', record=)`: layout order, sections, edit/mode, Country of Work per record, ticked HR/admin-only field still shown, untick = absent, labels in vi | PASS (test_27) |
| 28 | `portal_values`: only ticked fields, nothing else read; an id over the wire needs the caller's own read right | PASS (test_28) |
| 29 | `portal_check`: instant vs approve split; shown-only, required-empty, other country, forged standard / locked / unknown names → errors; unchanged dropped; bad date | PASS (test_29) |
| 30 | `portal_apply`: writes only those fields, returns only those, history line (proposer, approver or "saved at once", old → new); unticked meanwhile → refused, nothing written; an id over the wire needs write right | PASS (test_30) |
| 31 | pay-run signal: another company's run blocks (database-wide, plain sentence); a payslip older than the window stops counting; windows ≤ 15 min | PASS (test_31) |
| 32 | deprecated `'everyone'` alias still answers for fs-5 | PASS (test_32) |
| 33 | Publish routes standard-field ticks (`update_portal`) and new-field ticks (`create_field`) | PASS (test_33) |

### 4.1 Fresh-install run
New copy of `upd_p6_t_tpl` (+ FS1-4 fix), `-i pb_form_studio --test-enable --test-tags
/pb_form_studio`: **20 test methods, 0 failed, 0 errors** (`odoo.tests.stats`: 22 tests incl.
class setup, 61 s). Test 13 counted after the install (tests roll back): `pb_form_field_meta 0,
pb_form_layout 0, pb_form_layout_draft 0, pb_form_audit 0, pb_form_native_view 0, pb_form_sample 0,
x_pbfs fields 0, jobs / mail templates / server actions / mail servers in the module's data 0` →
**PASS**. The same suite also passes on the used walk database (test 13 skips itself there).

## 5. THE HOST CONTRACT (binding for FS-2 … FS-6)

A host is one screen that shows one record type. It never edits `pb_form_studio`.

**1. Register the host** (Python, your bridge module, `_inherit = 'pb.form.studio'`):

```python
class PbFormStudio(models.AbstractModel):
    _inherit = 'pb.form.studio'

    @api.model
    def _pbfs_hosts(self):
        hosts = super()._pbfs_hosts()
        _ = self.env._
        hosts['employee_detail'] = {
            'model': 'hr.employee',                 # fields are created HERE (never hr.version)
            'title': _('Employee'),                 # "Record type" in the Field library
            'icon': 'user',                         # an IC / fsIc key
            'sections': [                           # host order; ids stable forever
                {'id': 'personal', 'title': _('Personal'), 'icon': 'user', 'tone': 'teal', 'kind': 'open'},
                {'id': 'pay', 'title': _('Pay'), 'icon': 'banknote', 'tone': 'green', 'kind': 'locked',
                 'note': _('Drawn by the screen itself. Fields cannot be placed here.')},
                {'id': 'custom', 'title': _('Company details'), 'icon': 'sparkles', 'tone': 'brand', 'kind': 'open'},
            ],
            'default_layout': {'personal': ['name', 'work_email'], 'custom': []},
            'standard_fields': ['name', 'work_email'],  # standard fields offered to the Studio
                                                    # (placement + My Payobook ticks; the
                                                    # FS-1 name `std_fields` is still read)
            'portal': True,                         # R14: this record type has a My Payobook page
            'custom_section': 'custom',             # where lost fields land
            'country_field': 'x_country_of_work_path',   # R10: dotted path to a res.country on the record
            'country_view_field': 'country_id',     # a DIRECT m2o res.country on the model, for native invisible=
            'copy_custom': False,                   # contract host: True (R7) → new fields created copied=True
            'native_views': [],                     # informational; call the sync helper (item 5)
        }
        return hosts

    @api.model
    def _pbfs_locked_fields(self, model):
        out = super()._pbfs_locked_fields(model)
        if model == 'hr.employee':
            out['name'] = self.env._('Prints on every payslip and bank file.')
        return out
```
Optional hooks: `_pbfs_link_targets()` (add `{model: label}` a link field may point at);
`_pbfs_reference_finders()` (append a method name `(model, field_name) -> [{kind, label, count,
names}]`; non-empty = delete blocker and "Used by"); R14 `_pbfs_portal_locked(model)` →
`{field: reason}` (may be shown on My Payobook, never changed there) and
`_pbfs_portal_hidden(model)` → `{field: reason}` (never shown). Both are re-checked on every
read and write, not only when the administrator ticks.

**2. Read** — `pb.form.studio.render(host_key, record_id)` (caller's own rights, never sudo) →
```
{version, can_write, currency,
 sections: [{id, title, icon, tone, kind: 'open'|'locked', note,
             fields: [{name, label, help, kind, type, type_label, custom, std, locked, reason,
                       required, vis, countries, options:[{value,label}], comodel,
                       value, display, writable, url?}]}]}
```
Only fields the caller may read; custom fields only where they apply to the record's Country of
Work; locked sections come back empty (you draw them). Keys may be missing for a reader — tolerate it.

**3. Write** — `pb.form.studio.write_values(model, record_id, {name: value})` → `{ok: True,
values: {name: {value, display}}}` or `{ok: False, error?, errors: {name: text}}`. The ONLY write
path for custom fields. Whitelist = Form-builder fields of that model the caller may write and that
apply to the record's country; coercion per type (numbers accept "1,204"; dates `YYYY-MM-DD`;
choices by value; links by id, readable by the caller; files as base64 or a data URL ≤ 10 MB);
Studio-level required; record written with the caller's rights (ACL + record rules). Nothing is
written if any field fails. Contract host: route the write through your approval path (R9) and call
`write_values` (or replicate its checks) when the approver approves.

**4. Draw + offer the Studio** (OWL):
```js
import { PbFieldGrid } from "@pb_form_studio/js/field_grid";
import { FormStudioOverlay } from "@pb_form_studio/js/studio_overlay";
import { useFormStudio, FormStudioWand } from "@pb_form_studio/js/use_form_studio";

static components = { PbFieldGrid, FormStudioOverlay, FormStudioWand };
setup() {
    this.studio = useFormStudio({ hostKey: "employee_detail",
        recordId: () => this.props.employeeId, onPublished: () => this.reload() });
}
```
```xml
<FormStudioWand studio="studio"/>                       <!-- administrator only; draws nothing otherwise -->
<PbFieldGrid sections="sections" mode="'edit'" model="'hr.employee'" currency="currency"
             staged="state.staged" errors="state.errors" onChange.bind="onChange">
  <t t-set-slot="pay"> …your locked section… </t>      <!-- slot name = locked section id -->
</PbFieldGrid>
<FormStudioOverlay t-if="studio.state.open" t-props="studio.overlayProps"/>
```
`onChange(name, value, display)` stages; your Save calls `write_values`, shows `errors` in place,
then re-renders. `mode="'read'"` (default) for look-only pages. A publish anywhere reaches every open
copy through the bus and calls `onPublished`.

**5. Native screen** — call once from your module (e.g. a `post_init_hook` that only REGISTERS, or
the first time your screen loads as admin): `env['pb.form.studio']._pbfs_sync_native_view(model,
parent_view_xmlid, page_title, host_key)`. `page_title` may be `{lang: text}`. The engine keeps ONE
inherited view (no XML id, survives `-u`) with a notebook page of the published custom sections in
order; field visibility via the field's groups; per-country `invisible=` on `country_view_field`;
regenerated on every publish and before every field delete; removed when no custom field is placed;
validated in a savepoint and the previous arch kept on failure. Returns the view or False.

**6. Lists, exports, formulas** — `fields_for(model, purpose)` with purpose `'list'`
("Show in lists"), `'formula'` ("Use in pay formulas", numeric/date/choice/yes-no only), `'all'`
(custom fields the caller may read). Labels in the caller's language; each item carries
`countries`. Values: Python `_pbfs_values_for(records, purpose)` → `{id: {name: {value,
display}}}` with a blank cell where the field does not apply; RPC `values_for(model, ids,
purpose)` (caller's rights). `'everyone'` is a DEPRECATED alias kept only because branch fs-5
(`pb_form_studio_reach/controllers/portal.py:44,47`) still calls it — R14 replaces it with
`'portal'` (item 9); remove the alias once fs-5 has moved.

**7. Copying** — `copy_field_names(model)` → custom field names to carry on renewal/copy (R7).

**8. Link lookups** — `lookup(model, field_name, term)` → `[{id, label}]` (caller's rights).

**9. My Payobook (R14, replaces R3)** — per field, standard AND custom, three settings on
`pb.form.field.meta`: `portal_show` ("Show on My Payobook"), `portal_edit` ("Employee can change
it"), `portal_mode` (`approve` "HR approves the change", default | `instant` "Saves at once").
A standard field gets a settings row only (no field is made; it cannot be renamed, retyped or
deleted). "Can change" implies "shown"; unticking "shown" clears "can change". The Studio
refuses on the server: a field in `_pbfs_portal_hidden` (show), in `_pbfs_portal_locked` (change),
money / file / non-allowed link / computed or read-only fields (change), standard fields not in
`standard_fields`, record types whose host has no `portal: True`. The properties panel and the
Field library show the two ticks and the mode, greyed with the reason when not allowed.
- `fields_for(model, 'portal', record=rec)` → `[{name, label, help, type, kind, options, comodel,
  section, section_title, edit, mode, required}]` in published layout order (ticked fields not
  placed come last under the custom section); labels in the caller's language; Country of Work
  honoured for `rec`; decided from the ticks — NOT from "who can see it" (a field only HR sees
  can still be shown to its own employee) — so it is safe around a record read with elevated rights.
- `portal_values(model, rec)` → `{name: {value, display}}` for exactly those fields.
- `portal_check(model, rec, vals)` → `{'instant': {name: value}, 'approve': {name: value},
  'errors': {name: text}}` — validated + coerced; anything not changeable for THIS record (not
  ticked, locked, hidden, another country, wrong value, required left empty, forged name) is in
  `errors`: refuse the whole submission when it is not empty. Unchanged values are dropped.
- `portal_apply(model, rec, vals, origin={'proposed_by': uid, 'approved_by': uid|False})` → the
  single write path (saved at once, or after HR approved): re-checks everything (a field unticked
  meanwhile is refused), writes ONLY those fields, adds a history line per field on the record's
  chatter and in the Form builder history ("label: old → new (changed on My Payobook by X,
  approved by Y | saved at once)"), returns `{ok, values}` for those fields only.
- Record argument: a RECORDSET (server code that already decided it is the employee's own) is
  trusted and read with elevated rights; an ID (over the wire) is only accepted if the CALLER may
  read it (`portal_values`, `fields_for`) or write it (`portal_apply`) with their own rights.

**10. "A pay run is being worked out" — the rule.** `create_field` and `delete_field` (and Publish
when it adds or deletes) are refused DATABASE-WIDE while any company's pay run is being worked
out: adding or dropping a column changes a table every company in the database shares, so a run in
one company holds it for all. Message, always: "A pay run is being worked out right now. Try again
in a few minutes." Every signal is bounded in time, so a stale one cannot block for hours: a
transaction writing payslips counts only while it is younger than 10 minutes; a draft run's
payslip written in the last 3 minutes; a practice run left "computing" for at most 15 minutes. The
column change itself waits at most 5 seconds for a lock. Changing labels, ticks, layout or values
is never blocked. Tests that create fields patch `_pbfs_busy` (name is stable).

### What the dev host does that a real host must repeat
1. Register in `_pbfs_hosts` with stable section ids, a custom section, `std_fields`, a
   `country_field` (and `country_view_field` for the native page), and locked fields.
2. `useFormStudio` + `<FormStudioWand/>` in its toolbar + `<FormStudioOverlay t-if t-props/>`.
3. `render` → `<PbFieldGrid>`; locked sections as slots.
4. Stage edits, Save through `write_values`, show `errors` per field, re-render.
5. Reload on `onPublished` (own publish and other people's through the bus).
6. Tolerate missing fields (visibility) and an empty custom section (hide the card).
A real host additionally: calls `_pbfs_sync_native_view` for its "Full details" form; offers
`fields_for(..., 'list')` columns; passes `copy_custom: True` if its records are copied (contracts).

## 6. Browser walk (local `fs1.localhost:8731`, Chrome; phone via device emulation 390×844)
Desktop: dev host → Form builder overlay matches the POC (dark bar, palette, dashed screen, open /
locked zones, properties panel, legend); tap-to-add a choice list, rename, limit to India, publish
sheet → published; India-only field absent on the Vietnam sample record; drag (HTML5 events) to
reorder and move between sections; locked field refused into another section with a plain note;
drop on the locked Pay section ignored; whole-number field edited in the grid (1,207 saved; 2.5
refused in place "Enter a whole number."); Settings › System › "Form builder" card → Field library
(KPIs grey at zero, table, Edit sheet: Vietnamese label + choice rename + Show in lists saved;
Delete: blocker "Saved searches 1 · DEMO uniform search" shown, typed-name delete of another field
done); bus: a publish from another call re-laid the open screen without a page reload.
Phone: grid one column, overlay panels stacked (fixed a squeezed-rows overlap found here), Field
library table scrolls inside its own box; page never scrolls sideways (scrollWidth = 390).
Console: no errors from this module (one pre-existing warning from `AiInsightChat`).
Fixed during the walk: libsass `min()` error, theme painting `<button>` white (ghost buttons),
Bootstrap `.mark` yellow, `.pbfs` prefix collision (→ `.pbfb`), stale "added" line after a rename,
country search ranking, PayAI pill above the overlay.

## 7. Self-review against the spec — deviations (stated, not silent)
- Visibility materialised to `ir_model_fields.pbfs_groups` + `_instanciate_attrs`, NOT
  `ir.model.fields.groups` (V1 — that column does nothing on this build).
- Layout keyed by **host + company** (design said model + company): two screens on one model can
  have different sections.
- Dev host model is `pb.form.sample`, not `res.partner` (V15).
- Audit is the engine's own append-only `pb.form.audit` (V14).
- Pay-run guard (V7, the best existing signals; no edit to any forbidden module): another
  transaction holding write locks on `hr_payslip` / `hr_payslip_line`, OR a draft run's draft/verify
  payslip written in the last 3 minutes, OR a practice run computing; plus the column DDL runs under
  `SET LOCAL lock_timeout = 5s` and turns a timeout into a plain refusal. An in-flight marker set by
  the compute path would need an edit to `pb_payrun_wizard` — not done.
- Delete confirmation = type the field's name (any language), not "DELETE" (works in vi/id).
- test_04b proves the import-mapping blocker path with the finder patched in (making a real mapping
  needs a whole formula configuration); the finder itself is 10 lines reading `target_field_id`.
- `field_references` scans every model's links to `ir.model.fields` on each call; `get_studio` /
  `library` call it per custom field (≈15 queries each). Fine at today's sizes; cache if a record
  type nears the 60-field cap.

## 8. Deploy notes (for the deploy agent — not done here)
- Install `pb_form_studio` on every database (module-sync rule). **Risky tier**: it adds a column to
  the core table `ir_model_fields` (`pbfs_groups`, nullable) — backups first; rehearse on a clone.
- Silent: no field, layout, view content, job or mail is created. Asset purge after install.
- Depends: `base, web, bus, hr, pb_import_kit` (no screen module, no `pb_settings`).
- Local copies of `upd_p6_t_tpl` need `-i pb_form_lines -u pb_govt_reports,pb_compliance_hub`
  first (FS1-4).

## 9. Merge-time tasks
None (new module only). FS-2…FS-6 branch from `origin/fs-1`.

## 10. New gotchas — rows for FORMSTUDIO_LEDGER.md (my worktree cannot write the main checkout; please copy them in)
- FS1-1 `ir.model.fields.groups` is unimplemented — use the engine's `pbfs_groups`.
- FS1-2 `.pbfs` CSS prefix belongs to Formula Studio; Form builder classes are `.pbfb`.
- FS1-3 The theme paints every `<button>` white with a hairline, and Bootstrap's `.mark` is a yellow
  highlight: style buttons as `button.pbfb-btn` with explicit backgrounds; never name a class `mark`;
  libsass evaluates `min(520px, 100%)` itself and fails the whole bundle — use `max-width`.
- FS1-4 `upd_p6_t_tpl` copies: `pb_govt_reports` now depends on `pb_form_lines` (not installed on
  the template) → "inconsistent states" → in a MULTI-WORKER local server each worker's reload
  signals the other: an endless registry ping-pong. Fix on the copy: `-i pb_form_lines -u
  pb_govt_reports,pb_compliance_hub`.
- FS1-5 Local `--workers=2` has no websocket (needs the gevent port behind a proxy): walk the
  browser on a threaded server; use workers only for the registry proof.
- FS1-6 Core refuses to drop a field a view still names: regenerate the Studio page BEFORE unlink.
- FS1-7 Deleting a field silently deletes its pay-data import mappings (cascade) — a blocker.
- FS1-8 `pg_locks` lists locks of EVERY database on the server, and databases copied from one
  template share table oids: a lock check joined to `pg_class` by oid alone sees another
  database's (another tenant's, another builder's) pay run. Always filter `l.database =` the
  current database. Found when the R14 tests were blocked by another builder's local run.

## 11. Owner questions (plain)
- When an administrator limits a field to some countries, people who may see the field at all can
  still look the value up for an employee in another country through the system's data tools (not
  on any screen). Is "hidden on every screen and list, cannot be changed" enough, or must it be
  locked down completely (slower screens, more work)?
- New fields are made the moment you press Publish, and their type can never change. Should the
  publish sheet ask for a second "Yes, make these fields" tick when new fields are in it?

## 13. Follow-up 2026-11-19 evening — R14 "fields on My Payobook" (replaces R3) + bounded pay-run signal

Built exactly to FS_HOSTS_HANDOVER.md "ADDENDUM 2 — Engine — FS-1 builder" (contract in §5 items
1, 6, 9, 10): meta `portal_show` / `portal_edit` / `portal_mode` (rows for standard fields too),
host keys `portal` and `standard_fields` (`std_fields` still read — fs-2 and fs-3 use it), hooks
`_pbfs_portal_locked` / `_pbfs_portal_hidden`, `update_portal`, `fields_for(model, 'portal',
record=)`, `portal_values`, `portal_check`, `portal_apply` (history on the record's chatter and
in the Form builder history), ticks + mode in the properties panel (standard and custom fields,
greyed with the reason) and in the Field library (column "My Payobook" + Edit sheet). Module
19.0.1.1.0.
- **`'everyone'` purpose: KEPT as a deprecated alias** — fs-5 still calls it
  (`pb_form_studio_reach/controllers/portal.py:44,47`). fs-5 should move to `'portal'`; then delete it.
- **Pay-run signal (employee-host question):** kept DATABASE-WIDE (a column change touches a table
  all companies share), one plain sentence, every signal time-bounded (≤ 10 / 3 / 15 minutes) —
  rule in §5 item 10. Found and fixed while doing this: the lock check saw OTHER databases' pay
  runs on the same server (FS1-8) — it now looks at this database only.
- Tests: 9 new (25-33, `tests/test_portal_r14.py`). Full module suite on a new template copy:
  **29 test methods, 0 failed, 0 errors** (33 incl. class set-up). PO regenerated: 347 entries
  each in vi / id; no "Odoo" anywhere (test 15).
- Browser (desktop): standard field "Email" ticked shown + can change + "Saves at once" →
  Publish → saved; "Country of work" shows "Employee can change it" greyed with "Country of Work
  decides which fields apply."; Field library column + Edit sheet with the money field's change
  tick greyed ("Money and files can be shown, not changed by the employee."). Console clean.
  Fixed: two identical change lines when two ticks of one field were touched.
- Commits added on `fs-1` for host branches to merge: see the final message / `git log
  origin/fs-1` after `87ede1a76`.

## 12. Left for later
- Per-record read block for country-limited fields (owner question 1).
- An in-flight marker written by the pay-run compute (needs `pb_payrun_wizard`).
- Caching the reference scan (§7).
- Standard-field relabelling in the Studio (meta has room; not offered in FS-1).
