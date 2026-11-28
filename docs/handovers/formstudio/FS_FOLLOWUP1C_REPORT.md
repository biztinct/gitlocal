# FORM STUDIO follow-up 1c — R22 ("Form builder" button on the two full pages)

Builder agent, 2026-11-20. Branch `fs-followup-1c` from `origin/fs-followup-1` @ `aa9e4150f`.
Local only: nothing deployed, the live server not touched. White-label checked: no new
user-visible string names the platform; the two strings used ("Form builder", "Add or move
fields on this screen") reuse the engine's vi/id wording; all touched `.po`/`.pot` parse with
`PoFileReader` (0 empty msgstr, 0 "Odoo").

Commits: `66762847b` R22 · this report.

## 1. Facts found (code at `origin/fs-followup-1`)

| # | Fact | Where |
|---|---|---|
| F1 | "Set up workflow" is drawn by a template extension of `web.FormView`, slot `layout-actions`, gated by `workflowProgress.canDesign`; the state comes from a `FormController` patch | `pb_lifecycle/static/src/xml/workflow_record.xml:4-11`, `pb_lifecycle/static/src/js/workflow_studio.js:55-115` |
| F2 | `layout-actions` is rendered by the control panel at every width (also phones) | Odoo `web/static/src/search/control_panel/control_panel.xml:76` |
| F3 | The wand's gate is `pb.form.studio.can_edit(host_key)` = administrator (`base.group_system`, R2) and a known host; never raises | `pb_form_studio/models/form_studio.py:778-784`, `ADMIN_GROUP` `:40`, `_pbfs_is_admin` `:205` |
| F4 | Opening / saving / publishing the Form builder is refused server-side for anybody else: `get_studio` `:786-787`, `save_draft` `:1309-1310`, `discard_draft` `:1327`, `publish` (→ `create_field` `:921`) all call `_pbfs_check_admin` (`:209`) | `pb_form_studio/models/form_studio.py` |
| F5 | "Full details" opens `hr.employee` with `views: [[false, "form"]]` → the default form = `hr.view_employee_form` (proved in test P4) | `pb_employee_vault/static/src/js/employee_360.js:131-142` |
| F6 | "Advanced form" on the contract page opens `hr.contract` with `views: [[false, "form"]]` → `hr_contract.hr_contract_view_form` (test K4) | `pb_contracts/static/src/js/contract_detail.js:78-80` |
| F7 | Both hosts declare these forms as their `native_views`; the engine re-draws the "Company details" page on publish / delete / country change | `pb_form_studio_people/models/form_studio.py:21,156`, `pb_form_studio_contracts/models/form_studio_host.py:22,59`; engine `form_studio.py:713,1063`, `form_native_view.py` `_pbfs_regenerate` |
| F8 | The panel wand mounts `FormStudioOverlay` through the overlay service (not inside the panel) | `pb_form_studio_people/static/src/js/people_form_patches.js` `pbfsOpenStudio` |
| F9 | The browser caches screen designs (`get_views`, RAM + disk cache, "update once"); a re-drawn page needs `rpcBus` `CLEAR-CACHES "get_views"` before the form is drawn again | Odoo `web/static/src/views/view_service.js:98`, `core/network/rpc.js:85` |

## 2. What changed

- **Employee (`pb_form_studio_people`)** — new `static/src/js/full_form_button.js` +
  `static/src/xml/full_form_button.xml`: a `FormController` patch and a `web.FormView`
  extension that adds `<button class="btn btn-outline-primary ms-2 pbfs-fullbtn">` (Lucide
  wand + "Form builder") inside `layout-actions`, i.e. right after "Set up workflow".
  - Only `hr.employee`, not in a dialog (`env.inDialog`, which also covers x2many sub-forms),
    not in a form without a top bar. Every other form view does no extra request.
  - Gate: `pb.form.studio.pbfs_people_full_form(view_id)` (`models/form_studio.py:276`) —
    `can_edit(HOST)` AND the view is `hr.view_employee_form`. Never raises.
  - Click: saves the record first (as "Set up workflow"), then opens the SAME
    `FormStudioOverlay` for `employee_detail` via the overlay service, previewing this person.
  - After Publish: overlay closes, `CLEAR-CACHES get_views`, `actionService.restore()` of the
    current controller → the form is drawn from the new design. No page reload.
- **Contract (`pb_form_studio_contracts`)** — the twin: `static/src/js/full_form_button.js` +
  `static/src/xml/full_form_button.xml`, gate `fs3_full_form(view_id)`
  (`models/form_studio_host.py:93`) for `hr_contract.hr_contract_view_form`, host `contract`.
- SCSS (both modules, appended): icon gap; below 576 px the label folds away and the wand
  stays (title + aria-label).
- `.po`/`.pot` (both modules): "Form builder" gains the new file reference; new entry
  "Add or move fields on this screen" (vi "Thêm hoặc di chuyển trường trên màn hình này",
  id "Tambah atau pindahkan kolom di layar ini" — the engine's own msgstr).
- Not touched: `pb_lifecycle/`, `pb_form_studio` (engine), `pb_people`, `pb_employee_vault`,
  `pb_contracts`, any standard addon. **No merge risk** in another work stream's module.

## 3. Version raises (one each)

| Module | Before | After |
|---|---|---|
| pb_form_studio_people | 19.0.1.1.0 | 19.0.1.2.0 |
| pb_form_studio_contracts | 19.0.1.0.0 | 19.0.1.1.0 |

## 4. Tests (local, `--test-tags` the six Form builder suites, `-u` of the touched set)

Baseline on an untouched copy of `fsf1_base` (branch code before R22): **118 tests, 0 failed,
0 errors**. After: see §4a — baseline + 8 new.

| # | Test | Result |
|---|---|---|
| P1 | Employee gate: yes for the administrator on Full details only; no for another employee form, the contract form, and False / 0 / None / "abc" / -1 | pass |
| P2 | HR manager + payroll manager, no administrator role: `can_edit` False, gate False; `get_studio`, `save_draft`, `publish` raise AccessError; nothing created | pass |
| P3 | Script + template in `web.assets_backend` (after the panel patch and the engine overlay); extends `web.FormView` slot `layout-actions` (slot present in the standard form); label/aria "Form builder"; outline-primary ms-2 | pass |
| P4 | Default employee form = `hr.view_employee_form`; a publish puts the new field in `get_views` (arch + fields) | pass |
| K1–K4 | The same four for the contract (`fs3_full_form`, `hr_contract.hr_contract_view_form`, contract manager without administrator role) | pass |

### 4a. Totals
Final run on a fresh copy of `fsf1_base` at `66762847b`: **126 tests, 0 failed, 0 errors** =
baseline 118 + 8 new, all passing (an earlier run caught two of the new tests using a field
kind the engine does not take — fixed in the tests before the commit).

## 5. Browser walk (local server, own copy, DEMO records, Chrome)

| Step | Result |
|---|---|
| Administrator (DEMO R22 Administrator) opens DEMO R22 Lan Nguyen's Full details | Top bar: History · Payslip · In Contract Since · **Set up workflow · Form builder** |
| Click "Form builder" | Same overlay as the panel wand (Employee screen, sections, field types) |
| Add a Text field "DEMO R22 Locker" to Company details, Publish for everyone | Overlay closes; page re-draws with a new "Company details" tab holding "DEMO R22 Locker" — **no browser reload** (a marker set on the page survived) |
| Delete "DEMO R22 Locker" from the same button, Publish | Tab gone again, no reload |
| Full contract form of "DEMO R22 Lan 2026" | Top bar: Component Changes · View workflow · **Set up workflow · Form builder**; added "DEMO R22 Bay" → "Company details" tab appears; deleted → gone; no reload |
| Same employee form opened in a dialog | No button in the dialog |
| Phone (390 px, mobile emulation) | Wand-only button beside "Set up workflow", no sideways scroll |
| HR manager without administrator role (DEMO R22 HR Manager) | No button on Full details nor on the contract form; direct calls: gate False, opening the Form builder for either screen refused ("Only the administrator can change forms.") |
| Console | No errors |

Note: after Publish the page takes a few seconds locally before it re-draws (the server
reloads its field list after adding/removing a column); on the live servers publish measured
~0.1–1.1 s (FS deploy report §3).

## 6. Deploy notes

1. Ship trees: `pb_form_studio_people`, `pb_form_studio_contracts` (nothing else changed vs
   `origin/fs-followup-1`; if 1b is not live yet, it ships with its own notes first).
2. Per database: `-u pb_form_studio_people,pb_form_studio_contracts`. No migration, no data.
3. New JS/XML/SCSS → purge `/web/assets/%` attachments per database, restart.
4. Verify: both manifests = `latest_version` (19.0.1.2.0 / 19.0.1.1.0); as an administrator,
   Full details and a full contract form show "Form builder" next to "Set up workflow"; as HR
   (not administrator) it is absent.
5. Nothing to press; nothing created on install.

## 7. Risks

- The button sits in the same slot as "Set up workflow"; if `pb_lifecycle` is not installed on a
  database the button still shows (alone). Order relative to the workflow buttons follows the
  asset order (`pb_lifecycle` loads earlier on all five databases today → Form builder after).
- Clicking the button saves unsaved edits first (same as "Set up workflow"); a record that
  cannot be saved (missing required box) does not open the Form builder — the form shows why.
- Another administrator's publish does NOT reload an open full form (only the person's own
  publish does), so a half-typed form is never thrown away; the next open shows the change.
- No stop-the-go-live risk found.
