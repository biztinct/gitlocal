# FS-3 — Form builder on the contract screens (`pb_form_studio_contracts`) — report

Branch `fs-3` (from `origin/fs-1`; `origin/fs-1` @ d341ed396 merged in at the end — engine
19.0.1.1.0, R14 + this-database-only pay-run signal). New module
`pb_form_studio_contracts` **19.0.1.0.0**. No other module edited. Not deployed. Local
databases `fs_3_t`, `fs_3_base`, `fs_3_bl` dropped at the end.

## 1. Verified facts (file:line at origin/fs-1 = origin/19.1 ef422ae4a for these modules)

| # | Fact | Where |
|---|---|---|
| F1 | The Terms tab, the write whitelist, the judgement, the preview and the save all read `_cd_terms` — one override reaches all of them. | `pb_contracts/models/pb_contract_360.py:633, 1316, 1325, 1711, 1975` |
| F2 | `_cd_propose` holds ONLY `MONEY_TERMS` (module constant) for approval; other terms are written at once. R9 needs custom fields held. | `pb_contract_360.py:1819-1919`; `contract_approval.py:45` |
| F3 | An approved contract change is carried out by the system as **superuser in the main company** (`uid 1`, `env.company` = company 1), not in the contract's company. Layouts are per company, so a plain `render` at apply time found no layout and refused the field. | observed in the test log; apply `contract_approval.py:123-133` |
| F4 | Both renewal paths build the new contract through `pb.people.contract.wizard.create_contract` with `renew_from`: the Renew button and the contract lifecycle's Extend / "Make it permanent" (`_build_new_contract`). It copies an explicit list only — custom fields were not carried. | `pb_people_advanced/models/people_wizards.py:337-421`; `pb_contract_lifecycle/models/contract_review.py:606-666` |
| F5 | Country of Work is `hr.employee.payroll_country`, a **selection of ISO codes**, not a `res.country`; the engine wants a path ending on `res.country`. | `pb_hr_payroll_base/models/hr_payroll_structure_base.py:266`; engine `_pbfs_record_countries` |
| F6 | The full contract form ("Advanced form") is `hr_contract.hr_contract_view_form` (the only primary form). | DB `ir_ui_view` |
| F7 | `assertRaises((A, B))` does not work in Odoo tests (`issubclass` on a tuple); `AccessError` is a `UserError`. | `odoo/tests/common.py:507` |
| F8 | In a test run, a field created and rolled back by one test can linger in the registry of the next (column gone → `UndefinedColumn` on a full `read`, `_2` names). | observed |

## 2. What was built (`pb_form_studio_contracts/`)

- **Host `contract`** (`models/form_studio_host.py`): model `hr.contract`; sections = the panel's
  four Terms groups (locked, "Drawn by the contract screen itself") + open **"Company details"**;
  `copy_custom: True` (R7 — new fields `copied=True`); `portal: False` (R14);
  `country_field` / `country_view_field` = `pb_country_of_work_id`.
- **Country of Work** (`models/hr_contract.py`): `hr.contract.pb_country_of_work_id`, computed,
  **never stored** (no column), `compute_sudo`, from the employee's Payroll Country code → country.
- **Side panel** (`models/contract_drawer.py`): `_cd_terms` appends a "Company details" group built
  ONLY from `pb.form.studio.render` (engine decides visibility + country), rendered in the
  **contract's company** (F3). `_cd_coerce_term` uses the engine's `_pbfs_coerce` and the Form
  builder's "required". `lookup_contract_m2o` also answers comodels of the reader's own custom
  link fields, searched with the **reader's rights** (stock whitelist untouched).
- **Approval (R9)**: `_cd_propose` — when no custom field is in the press it is `super()` untouched;
  when one is, the same body runs with the held set widened to the accepted custom fields; the
  snapshot holds them in a comparable shape (`snap_value`: link = id, date = ISO, file =
  fingerprint). `pb.contract.proposal`: `_live_snapshot` re-reads in the same shape;
  `_proposal_rows` shows the field's label + old → new in words ("A file", "A new file",
  choice labels, names); a field the approver may not see shows as "A field you cannot see".
- **Renewal (R7)** (`models/contract_wizard.py`): `create_contract` `super()` then copies every
  custom value from the old contract to the new one (elevated: carrying is a system rule;
  hidden fields carried too). Never undoes a renewal (savepoint + log).
- **Contract page**: `get_contract_detail` adds key `pbfs` (render sections); patched page draws
  them with `PbFieldGrid` look-only under the lifecycle panel; wand in the top bar.
- **Full form**: "Company details" page via the engine's native-view sync, registered lazily on the
  first publish/delete (`_pbfs_resync_native` override) — install writes nothing.
- **Contracts board filters**: `_pbf_spec` adds choice, yes/no, link and date fields (reader's
  rights via `fields_for`) in a new "Company details" group (`_pbf_groups`).
- **Client** (`static/src/`): `CdEditor` patched with Yes / No (real boolean), long text (textarea,
  Enter = new line), file (dashed drop box, "PDF or image, up to 10 MB"); panel header wand
  (administrator only) + Studio over the panel; tinted "Company details" group, long text full
  width, file "Download" link; administrator-only **"Add your own fields"** card while no field is on
  the contract yet (R13); phone: while the wand shows, wage/wand/close take their own row under
  the name (`:has(.pbfb-wand)` — nobody else's header changes). Lucide icons via the engine's
  cached `fsIc`; tokens only; no gradient.
- **vi / id** PO (`i18n/vi_VN.po`, `id_ID.po`, `.pot`) — 29 entries each, all translated.

## 3. Tests

### 3.1 Numbered cases (`tests/test_fs3_contracts.py`, 16 methods)

| # | Case | Result |
|---|---|---|
| 1 | each of the 10 types added → shown in the panel with the right kind → saved (1,204 / 2.5 / money / Yes / date / choice / link / file) → words in the panel, the page and the full form; bad values refused in place; vi label; required refused in words (1b) | PASS |
| 2 | route published → change waits, location in the same press lands; approver reads "DEMO Uniform size: — → Large", never the field code; approve writes once (2); refuse leaves the old value (2b); link value not falsely "moved" + a real move is named (2c); "No approval needed" → saved at once (2d); a press with no custom field goes through the stock path untouched (2e) | PASS |
| 3 | Renew form, "Make it permanent" and the import's `copy()` all carry text, choice, link, yes/no, money, file and an administrators-only field; nothing written on the old contract (3); golden: with no custom field, a renewal is field-for-field identical with and without the carry (3b) | PASS |
| 4 | contract manager: HR field editable, administrators-only field absent (label + value) from panel, page, full form, filters; RPC `read` raises; forged save refused and not written. Administrator sees both. HR officer without contract rights: the stock panel refuses the contract, nothing leaks. Payroll officer: HR field only if HR staff. Line manager / employee / portal: no panel, RPC read and `render` refused. Country of Work: India-only field absent on the Vietnam contract (panel, page, full form `invisible`), refused on save, present + saved on the India contract, follows the person when their country changes (4b) | PASS |
| 5 | panel keys, header, readiness, components, history identical with a custom field; Terms keys = stock + `pbfs_custom` | PASS |
| 6 | one payslip recomputed identical (lines + totals) after a field is added, edited, deleted | PASS |
| 7 | delete → gone from panel, page, filters, full form; last one gone → page removed, full form opens | PASS |
| 8 | `-u pb_contracts,pb_people_advanced,pb_form_studio,pb_form_studio_contracts` on the walk database: fields (6), `copied` (6), meta, layout + version, full-form page, values, visibility groups — **identical** before/after, 0 errors | PASS (script, §3.3) |
| 9 | silent install: no field, layout, page, view, job, mail, server action; Country of Work helper has no column | PASS on the fresh install (skips itself on the walk database) |
| 10 | PO gate (every msgid translated in vi + id) + no "Odoo" in any msgstr, template, JS or `_()` literal | PASS |
| 11 | browser walk desktop + phone, console clean | PASS (§4) |

Final run after merging origin/fs-1: `-u pb_form_studio,pb_form_studio_contracts --test-tags
/pb_form_studio,/pb_form_studio_contracts` → **0 failed, 0 errors of 45** (engine 33 tests +
bridge 18 incl. class setup).

### 3.2 Touched suites vs baseline (`fs_3_bl` = same database without the bridge)

| Suite | Baseline (no bridge) | With bridge |
|---|---|---|
| pb_contracts (79) | 1 fail: `test_cd1` test_01 (`fillin` key not in the expected set — pre-existing) | same 1 fail, nothing else |
| pb_contract_lifecycle (14) | 0 | 0 |
| pb_people_advanced | no tests | — |
| pb_form_studio (22 → 33 after merge) | 5 errors: "A pay run is being worked out" — the engine read `pg_locks` for the whole database server and another builder's pay-run tests ran in another database | before merge: 2 errors, same cause; **after merge: 0** (engine fix) |

See §3.4 for the post-merge contract-suite rerun.

### 3.3 Test 8 script
`state.sql` (scratchpad) before/after the `-u`: `cmp` identical; `grep ' ERROR '` = 0.

### 3.4 Post-merge rerun of the contract suites
On the WALK database (7 published contract fields): pb_contract_lifecycle 0 failures;
pb_contracts 2 failures — the known `test_01` (`fillin`) and `test_cd1 test_02`, which asserts the
Terms groups are exactly `money, dates, place, rules` and now also sees `pbfs_custom` because
this database HAS published fields. On a database without published contract fields (the run in
§3.2) it passes. Merge task M3 makes the stock test data-independent.

## 4. Browser walk (local `fs_3_t`, port 8733, Chrome; DEMO data only)
Desktop 1512×900: Contracts board clean console → Lan's panel: "Company details" tinted group
(Uniform size, Signed copy received, Special terms, Signed scan, Home country; the India-only PF
number absent; present on Arjun's India contract); Yes/No pair, link picker ("Viet" → Vietnam),
long text textarea (Escape closes the cell, not the panel), file box → "File attached ·
Download" (200, image/png) — Save bar "Save 2 changes" → "2 changes saved."; wand → Form builder
over the panel (locked Terms groups + open Company details); added a **Date** field by tap,
renamed "Medical check", publish sheet → "Published. 1 change is now live for everyone." → the
panel re-drew with it, edited to 01 Dec 2026, full form gained it; contract page shows the
sections look-only (three columns) with the wand in the top bar; full form "Company details"
page (PF number hidden for Vietnam); board filters "Uniform size" / "Home country" → Medium = 1
contract; empty layout → administrator sees the "Add your own fields" card → opens the builder
("Add existing" lists the hidden fields). DEMO HR manager (not administrator): no wand, no card,
6 editable fields; in Vietnamese: "THÔNG TIN CÔNG TY", "Không", "Tải xuống", "Đã đính kèm tệp".
Phone 390×844: page width 390 (no sideways scroll); fixed during the walk: the wand squeezed the
name to one word per line → header wraps while the wand shows; dates now in the panel's own
style; page wand height. Console: no errors or warnings from these screens.
Not walked visually: the approval inbox screen (covered by tests 2–2c).

## 5. Self-review against the spec — deviations (stated, not silent)
- Country of Work for a contract is a **computed, never-stored** `res.country` field on
  `hr.contract` (F5): the engine needs a `res.country` path and a direct many2one for the full
  form. It is a model field (no column, no data) — "silent install" holds.
- `_cd_propose` is re-stated (~50 lines) for presses that carry a custom field; `super()` for all
  others. Merge task M1 below removes the copy.
- Full-form page registration is lazy (on publish/delete), not a `post_init_hook`, so install is
  silent; `-u` keeps it (no XML id).
- The full-form page is ONE view for all companies (engine design); its content follows the
  publishing company's layout. Per-company panel/page layouts are correct (render per contract
  company).
- "HR without contract rights": on this build an HR officer cannot open contracts at all (stock),
  so the "look-only" case applies to readers who can open a contract but not change it (payroll
  officer); both are tested.
- A custom date shows "01 Dec 2026" in the panel (panel style) and the engine's format on the page.
- An approver who may not see a held field: the row reads "A field you cannot see" and, if they
  approve, that one value is refused at apply time (listed in the result) — the rest applies.

## 6. Version raises
`pb_form_studio_contracts` new at 19.0.1.0.0. No other manifest changed by this phase.

## 7. Merge-time tasks
- **M1** (pb_contracts, optional, removes the copy): add a hook to `_cd_propose`
  (`pb_contract_360.py:1839, 1856`) —
  ```python
  @api.model
  def _cd_held_terms(self, term_vals):
      return [k for k in (term_vals or {}) if k in MONEY_TERMS]
  ```
  use it for `money` and `held_terms`, and a `_cd_snapshot_value(contract, key)` returning
  `contract[key]`; then this bridge's `_cd_propose` becomes a 6-line override. Not needed to ship.
- **M2** (engine, cluster-wide pay-run lock probe) — **done on fs-1** (`form_studio.py:360-370`),
  merged here; nothing left.
- **M3** (pb_contracts test, one line): `pb_contracts/tests/test_cd1_contract_360.py:246` —
  compare `[g['key'] for g in payload['terms'] if not g.get('pbfs')]`, so the suite still passes
  on a database where the administrator has published contract fields (it fails there today,
  §3.4; the screen itself is right).
- Merge order: fs-1 (engine) before fs-3. fs-3 touches no file another FS branch owns.

## 8. Deploy notes (for the deploy agent — not done here)
- Install `pb_form_studio_contracts` on every database after `pb_form_studio` (module-sync rule).
  Normal tier: no column on any table (the Country of Work field is not stored), no data.
- Asset purge + restart after install (JS/SCSS).
- Depends: `pb_form_studio`, `pb_contracts`, `pb_people_advanced`.
- Tenants: a field made in `payobook_template` reaches every new tenant (engine note, FS_HOST_FACTS §F).

## 9. New gotchas — rows for FORMSTUDIO_LEDGER.md (please copy in)
- FS3-1 An approved contract change is carried out by the system in the MAIN company's context:
  anything per-company (Form builder layouts) must be read in the record's own company.
- FS3-2 Country of Work is a selection of country CODES (`hr.employee.payroll_country`); the
  engine needs a `res.country` — use a computed, non-stored many2one per host.
- FS3-3 Odoo's `assertRaises` takes one class, not a tuple; `AccessError` is a `UserError`.
- FS3-4 Tests that create Form builder fields leave them in the registry of later tests after the
  rollback: read only real columns, expect `_2` names.
- FS3-5 Chrome walk: the local template's `admin` user is archived and lacks the formula role the
  contract form's component smart button needs ("You don't have access to this yet") — local
  setup only.

## 10. Owner questions (plain)
- A change to one of your own contract fields now waits for the contract approver, like a pay
  change does (your rule R9). A plain change such as a location does NOT wait today. Do you want
  your own fields to wait (as built), or to save at once like a location?
- When a contract is renewed, every one of your own fields is copied to the new contract —
  including a scan of the signed old contract. Is copying files right, or should file fields
  start empty on the new contract?
