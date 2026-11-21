# FS-2 — Employee record (`pb_form_studio_people`) — report

Branch `fs-2` (from `origin/fs-1` @ 87ede1a76). New module `pb_form_studio_people`
**19.0.1.0.0**. No existing module was edited. Not deployed. Local database `fs_2_t` (copy of
`upd_p6_t_tpl`, `-i pb_form_lines,pb_form_studio -u all`; dropped at the end).

## 1. Verified facts (re-checked at fs-1 head; line numbers at origin/19.1 = fs-1)

| # | Fact | Where |
|---|---|---|
| F1 | Country of Work = `hr.employee.payroll_country`, a Selection of country CODES (VN/ID/IN/SG/MY + TH/KH/PH). The host contract wants a path to a `res.country` and a direct many2one for the native page → bridged by a non-stored compute `pbfs_country_of_work_id` (no column). | `pb_hr_payroll_base/models/hr_payroll_structure_base.py:266`; `pb_hr_payroll_formula/models/employee_work_timezone.py:70`; FIELD_AUDIT_FACTS §6 |
| F2 | The side panel slides in with `transform: translateX(...)` → a `position: fixed` child is trapped in the panel box. The Studio overlay is therefore mounted through the overlay service, not inside the panel template. | `pb_employee_vault/static/src/scss/employee_vault.scss:35-44` |
| F3 | The panel closes on Escape from a window CAPTURE listener, i.e. before any editor sees the key. The patch ignores Escape while the Studio is open or when the key comes from a grid editor/picker. | `pb_employee_vault/static/src/js/employee_360.js:43, 167` |
| F4 | `get_employee_detail` is also the panel's `profile`; it has no gate of its own (ORM read only). The new key `form_sections` is added only for the panel's HR gate (`_vault_is_hr`). | `pb_people/models/pb_people.py:487`; `pb_employee_vault/models/pb_people_360.py:28-43, 102` |
| F5 | `hr.group_hr_user` alone cannot open the panel's payload (contract reads need the contract role); the realistic HR role is the payroll officer (implies HR + contracts). | `om_hr_payroll/security/*.xml` `group_hr_payroll_user` |
| F6 | No realistic group reads employees without writing them; "look-only" happens through access rules. Test 4 builds one (write-only rule). | `hr/security/ir.model.access.csv:4-5` |
| F7 | Filter kit hides a section whose field holds one value or none; custom filters follow that rule. Section key = field name, so a saved view naming it is found by the engine's `_pbfs_refs_saved_views`. | `pb_filter_kit/models/filter_mixin.py:457-476`; engine `form_studio.py:970` |
| F8 | A publish run from `odoo shell` does not signal the registry to a running server (signals are sent at the end of a request) — the screen shows the layout but not the new fields until the server restarts. Real publishes go through RPC and do signal. | core `odoo/orm/registry.py` (signal_changes) |

## 2. What was built (`pb_form_studio_people/`)

Server
- `models/form_studio.py` — host `employee_detail` on `hr.employee` (never `hr.version`):
  locked sections = the panel's tabs (Profile, Personal, Job, Pay & tax, Documents, Timeline),
  open sections "Company details" (default), "More about the job", "More about the person";
  `country_field` / `country_view_field` = `pbfs_country_of_work_id`; `std_fields: []`
  (R8: standard boxes stay where the panel draws them). R14: `portal: True`,
  `standard_fields` (the KEEP rows of tidy-e's verdict table, minus lists/pictures/summaries,
  filtered by type at run time), `_pbfs_portal_hidden` (wage, hourly cost, every money field incl.
  custom), `_pbfs_portal_locked` (Already on My details when `pb_me_details` /
  `pb_me_portal` are installed; Country of Work; tax numbers/status; bank; contract terms;
  every formula input — `EMPLOYEE_FIELDS` + related hops + `pb_me_tax` tax sources + custom
  fields marked "Use in pay formulas"; company/team/manager/job; login/access), one plain reason
  each. `render` refuses non-HR for this host. The Full details page is registered just in time
  (`_pbfs_resync_native` override) → install stays silent; the engine writes the page on publish.
- `models/hr_employee.py` — `pbfs_country_of_work_id` (non-stored, `compute_sudo`).
- `models/pb_people.py` — `get_employee_detail` + `form_sections` (HR only, money masked as the
  wage is, open sections only, filled/total, Country of Work name, field count for the admin);
  `pbfs_employee_sections`, `pbfs_save_employee` (HR gate, masked amounts refused, then
  `write_values`); `_pbf_spec` + one filter per custom choice / yes-no / link / date field the
  user may see (`fields_for`), in a "Company details" filter group.

Client (`static/src/`, classes `.pbfp-*`)
- Side panel: wand in the header (administrator only) → Form builder over the panel;
  "Company details" tab (count badge, unsaved dot) with a header card "N of M filled in" + bar,
  `PbFieldGrid` in edit mode, look-only note, one sticky Save bar; every way out (×, scrim,
  Escape, Full details, Contract) asks first while changes are unsaved ("Keep editing / Leave
  without saving / Save and go"); administrator empty state "Add your own fields" (or "Nothing to
  show for this person" with the Country of Work reason). Reloads on any publish (bus).
- Full page: "Company details" panel, look-only, reloads on publish.
- Publish sheet: "A field's type cannot be changed after it is published." when new fields are in
  it (ADDENDUM item 3, via template inheritance of the engine's sheet).
- `i18n/` pot + vi_VN + id_ID (65 entries, all three markers).

## 3. Tests

Module suite `/pb_form_studio_people` (`tests/test_people_host.py`): **12 test methods, 0 failed**
on a fresh install against the merged engine 19.0.1.1.0 (see §3.2).

| # | Case | Result |
|---|---|---|
| 1 | admin adds a field the wand's way (publish with a create) → in the panel tab, the full page and Full details (inside the notebook), labels en/vi/id, page title in 3 languages; field on `hr.employee`, not `hr.version` | PASS test_01 |
| 2 | HR saves once; same value in panel, full page and the record; "1,204" → 1204; required / whole number / unknown choice refused in plain words, nothing written; standard field refused | PASS test_02 |
| 3 | "HR staff" vs "Administrators only": absent from panel, full page, reload RPC, `render`, native page, `fields_get`; `read([f])` raises; save refused; filter not offered | PASS test_03 |
| 4 | look-only reader (write blocked by a rule): `editable` false, save refused; money masked for HR (no number in the payload), refused on save, shown and editable for the payroll manager; line manager / employee / portal: all four RPCs raise, no `form_sections` | PASS test_04 |
| 5 | re-order after publish: new order + version, a bus message to HR, Full details order; move to another open section | PASS test_05 (+ browser: live re-order without reload) |
| 6 | delete: gone from panel, full page, Full details; last field removes the page; Full details still opens | PASS test_06 |
| 7 | `-u pb_people,pb_employee_vault,pb_form_studio_people` keeps fields, values, layout, the native page, who-can-see | see §3.1 |
| 8 | filters: choice / yes-no / link / date sections in the "Company details" group, each filters the list; a text field is not offered; a saved People view using the field blocks the delete | PASS test_08 |
| 8b | R10 per surface: India-only field on panel + full page only for India; native `invisible` on Country of Work; save refused elsewhere; follows a change of the box at once | PASS test_08b |
| 9 | static-contract tests that read the vault's source (`pb_scheme_map`, `pb_workseg`) | see §3.2 |
| 10 | silent install: no meta, layout, native registration, `x_pbfs` field, Studio view, cron/mail/action/rule; `pbfs_country_of_work_id` has no column | PASS test_10 |
| 11 | PO gate (pot parsed, every msgid translated in vi + id, no platform name in msgid/msgstr/templates/`_t`/`_()`/manifest name) | PASS test_11 |
| 12 | browser walk | §4 |
| 13 | R14: host `portal: True`, `standard_fields`; hidden/locked lists incl. a custom formula field and a custom money field; ordinary box and plain custom field not locked | PASS test_13 |
| 13b | R14 against the real engine (§7): forbidden ticks refused on save, greyed with the reason, `fields_for(portal)`, forged `portal_check` refused | PASS test_13b |

The tests run against the real engine (no stub) after the §7 merge.

### 3.1 Test 7 (`-u`) — PASS
Walk database with 9 published fields (incl. one "Administrators only" and one India-only),
values on a person, layout version 4 and the Full details page. A probe (field list, three values,
layout version + sections, native page present and naming every field, each field's who-can-see,
"HR sees the administrators' field" = false) was taken before and after
`-u pb_people,pb_employee_vault,pb_form_studio_people`: **byte-identical**
(scratchpad `fs2/probe_u.py`, `u_before.txt` / `u_after.txt`).

### 3.2 Touched suites vs baseline
| Run | Database | Suites | Result |
|---|---|---|---|
| baseline (before this module) | `fs_2_t` fresh | pb_form_studio 22, pb_employee_vault 25, pb_scheme_map 43, pb_workseg 55 (pb_people has no tests) | 125 tests, 0 failed |
| after, engine 1.0.0 | walk database | same + this module | 14 engine errors + 2 of mine: every engine error = the cross-database pay-run refusal (G1) caused by another builder's run; mine = tests that assumed no other field existed (fixed) |
| **final, engine 1.1.0 merged** | `fs_2_t` rebuilt fresh, `-i pb_form_studio_people` | pb_form_studio 33, pb_employee_vault 25, pb_scheme_map 43, pb_workseg 55, this module 14 | 146 tests, 0 failed, 1 error (test 13b picked a box the engine treats as worked out by the system — test fixed) → this module re-run: **12 of 12 pass** |

Test 9 (the two static-contract suites that read the vault's source): `pb_scheme_map` 43 and
`pb_workseg` 55 pass, same as baseline (same two skips in pb_scheme_map: no demo module, nobody
paid). Test 10 (silent install) ran on the fresh install (not skipped).

## 4. Browser walk (local `localhost:8741`, Chrome; phone via device emulation 390×844)
Desktop as the administrator: panel → "Company details" empty state → Open the Form builder (the
overlay covers the whole screen above the panel, locked tabs and three open sections, as the POC);
fields published; tab with header card, three cards; choice picker floats correctly inside the
sliding panel; "2.5" in a whole-number field → saved refused, red line "Enter a whole number." in
place; "1,204" saved; Escape with unsaved changes → the leave banner, Keep editing, Save →
"Company details saved."; Full details → "Company details" page with the same values; full page
→ "Company details" panel look-only; a re-order published from another call re-laid the open
panel in about 4 s without a reload; a new Yes/No field through the real Publish button → the
publish sheet shows "A field's type cannot be changed after it is published.", the panel showed
the new field at once. As HR (payroll officer): no wand, no "Admin note", the amount reads
"Visible to payroll managers only", fields editable. Phone 390 px: panel 374 px, fields in one
column, page width 390 (no sideways scroll), save bar visible. Console: no errors or warnings
from this module (desktop and phone).
Fixed during the walk: "filled in" counted a "No" and an empty 0 as answers (now: answered only);
a masked amount was painted in money green (now a locked line).

## 5. Self-review against the spec
- Items 1–5 built as specified; addendum items 1–5 honoured (engine paths only; Country of Work;
  publish line; no hidden switch added — the filters need no setting; native page anchored on
  the notebook, independent of TIDY-E boxes).
- Deviation: the filters are offered for every custom field of a filterable type the user may
  see — no per-field "offer as a filter" switch (R13: nothing hidden to switch).
- Deviation: the wand is in the panel header only; the full page is look-only with no wand.
- Money fields: see Follow-up R15/R16 — custom amounts follow their own "who can see it" only.
- `standard_fields` and the two hooks: verified against the real engine (§7, test 13b).

## 6. New gotchas (ledger rows)
- G1 (FS2-1 = engine FS1-8): the engine's "pay run being worked out" lock probe read `pg_locks`
  server-wide; copied databases share table ids, so a pay run in ANOTHER database refused field
  add/delete here (seen locally: another builder's database; 14 engine tests failed on that
  alone in one run). Fixed in the engine follow-up (this database only, time-bounded); not worked
  around in this module.
- G2: a publish from `odoo shell` does not reach a running server's registry (F8) — restart the
  local server after shell-made fields, or publish through RPC.
- G3: the side panel's slide-in transform traps fixed children (F2) — mount overlays through the
  overlay service from any drawer.
- G4: the panel's Escape listener is window-capture (F3) — patches must swallow it for their own
  editors.

## 7. Engine follow-up (ADDENDUM 2) — merged and verified
`origin/fs-1` gained `2ae5dd3a1` (engine 19.0.1.1.0: R14 + this-database-only pay-run signal)
and `d341ed396` (report). Merged into `fs-2` (merge commit on the branch, no conflict). After
the merge the hooks call the engine's `_pbfs_portal_locked` / `_pbfs_portal_hidden` directly,
the busy-probe stub was removed from the tests, and test 13b runs against the real engine:
"never shown" (wage) and "never changed" (Country of Work, department) refused by
`update_portal`; an ordinary box (spouse name) ticked shown + changeable + "Saves at once";
`get_studio` greys the ticks with the reason; `fields_for(..., 'portal', record=)` omits the
wage and marks Country of Work look-only; a forged My Payobook change of Country of Work is
refused by `portal_check`.

Note for the Studio: with `standard_fields` set, the engine also offers those boxes under
"Add existing" (placement and ticks share one list). Superseded by the follow-up below: the
ticks of a standard field are now set from a "Standard fields" list WITHOUT placing it.

## 8. Merge-time tasks
- M1 (optional): move the publish-sheet line into the engine (`pb_form_studio/static/src/xml/
  studio_overlay.xml`, publish sheet `.bd` → after) and drop `pbfpHasNewFields` +
  `pb_form_studio_people.Overlay` from this module.
- M2: FS-3 / FS-4 / FS-5 must use host key `employee_detail` for the employee.
- M3 (optional): move the "Standard fields" list (§11) into the engine's overlay, so every host
  with `portal: True` gets it without its own patch.

## 9. Deploy notes
- Install `pb_form_studio_people` on every database after `pb_form_studio` (normal tier: no
  column, no data; asset purge after). Depends `pb_form_studio, pb_people, pb_employee_vault`.
- Silent: nothing is created until an administrator publishes.

## 10. Owner questions (plain)
Both earlier questions were answered (R15, R16 — see the follow-up). None open.

## 11. Follow-up R15/R16 (2026-11-19 night) — on `fs-2` after the engine merge

**Merge:** latest `origin/fs-1` (`d341ed396`) was already merged (merge commit `2561b5547`);
nothing newer on fs-1 at the time of this follow-up.

**R15 — a custom amount follows its own "who can see it".** `_pbfs_people_payload` masks only
STANDARD amounts (`kind == 'money'` and not custom — e.g. the wage or hourly cost if an
administrator places one on the tab); the extra refusal of amounts in `pbfs_save_employee` is
gone. The panel's own wage masking (Profile tab, `get_employee_360` / `unmask_wage`) is untouched.
Full details never had a mask (unchanged). Test 4 now proves: HR who is not a payroll manager
sees and saves a custom amount (panel, employee page, Full details); an "Administrators only"
amount stays hidden from HR by its own setting; `unmask_wage` is still false for HR.

**R16 — a custom amount may be shown on My Payobook.** `_pbfs_portal_hidden` now lists only
STANDARD money fields (wage, hourly cost, every standard monetary field); custom fields are
skipped. Changing an amount from My Payobook stays impossible — the engine refuses it for every
money field ("Money and files can be shown, not changed by the employee."). Tests 13 / 13b: a
custom amount is not in the hidden list, `update_portal` shows it, refuses "Employee can change
it", and `fields_for(..., 'portal')` lists it; `hourly_cost` and the wage stay hidden.

**Standard fields ticked where they sit (owner: "a tick in front of the field").** Confirmed the
earlier limit: in the engine's panel a standard field's ticks were reached only by placing it on
the Company details tab (then also shown there, look-only). Fixed with a small change in this
module, no engine change: a third tab **"Standard fields"** in the Form builder's left panel
(only for record types with a My Payobook page) lists every standard field with its state
("Shown", "Shown · can change, HR approves / saves at once", or the reason it cannot be shown),
a search box and a count. Picking one opens its settings on the right (the engine's own two
ticks and mode, greyed with the reason) WITHOUT placing it; Publish sends the ticks (engine
`update_portal` via publish). Browser check: "Spouse Birthdate" ticked "Show on My Payobook" from
that list → publish sheet "Spouse Birthdate: My Payobook" → after publish the field is on My
Payobook (`fields_for(..., 'portal')`) and placed in NO section; console clean. Done by
`patch(FormStudioOverlay.prototype)` + template inheritance (the palette's `t-else` becomes
`t-elif="state.pal !== 'std'"`). Merge-time task M3 (optional): move this list into the engine.

**Tests:** `/pb_form_studio, /pb_employee_vault, /pb_form_studio_people` on a rebuilt `fs_2_t`:
**62 tests, 0 failed** (engine 33, vault 25, this module 14 incl. class set-up). PO regenerated:
75 entries, vi + id complete (test 11).
