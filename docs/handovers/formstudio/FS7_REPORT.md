# FS-7 — Standard fields: hide and rename per Country of Work (R23) + the left-column filter (R24)

Status: **LIVE ×5 (2026-11-20 06:00–06:03 UTC, 152 s down)** — see §9. The go-live retry found its
15 quiet minutes and stopped the service at 06:00:14 UTC; the owner's HOLD (Rize testing all day)
reached this session only after the run had finished. Nothing was half-done: all five databases
upgraded, verified, service up, DONE line written. No demo change on payobook.com was made (hold).
Branch `fs-7`, rebased on `origin/fs-followup-1` = `48a80cb14` (follow-up 1 + 1b + 1c/R22, the
code the follow-up go-live ships), which itself sits on `origin/19.1`.
Handover: `FS7_HANDOVER.md` (main checkout). Coordinator rulings during the build:
* **R24** (owner): a filter on the left column of the Form builder and on the Field library.
* **R24 clarification** (owner, with a screenshot): the filter is first of all on **Add existing**
  (sticky search, A–Z, type filter); the **Standard fields** tab gets the same search; do NOT build a
  second "Standard boxes" list — the R23 hide / rename / Country of Work controls go INTO the
  existing "Standard fields" tab and the Field library; the screen word is "Standard fields".

## 1. Verified facts (file:line at `48a80cb14` unless said)

| # | Fact | Where |
|---|---|---|
| F1 | Core relabels fields in `_get_view` on the combined arch, and caches the result with the screen designs | `odoo/addons/base/models/res_currency.py:322-343`; `ir_ui_view.py:3064-3091` (`_get_view_cache`, cache `templates`) |
| F2 | TIDY-E applies its by-country rules the same way (combined form, `_get_view`), so an absent box matches nothing | `pb_employee_form_tidy/models/hr_employee.py` `_get_view`; `models/form_rules.py` `FORM_RULES` |
| F3 | The web client keeps every form design on disk (`orm.cache({type:"disk"})`, table = method name `get_views`) and forgets it on `rpcBus.trigger("CLEAR-CACHES", "get_views")` | core `web/static/src/views/view_service.js:98`, `core/network/rpc.js:85-104`, `rpc_cache.js:96` |
| F4 | The side panel's rows carry the field name as `key`; Personal / Job / Pay & tax come from `_e360_details` | `pb_employee_vault/models/employee_details.py:242-285`, `_SPEC` :35-181 |
| F5 | The contract panel's terms, its write list, judgement and save all come from `_cd_terms` | `pb_contracts/models/pb_contract_360.py:633-653`, `_cd_writable_map` :1316 |
| F6 | The People / Contracts table headings, column picker and Excel headings all come from `_pbf_columns` | `pb_filter_kit/models/filter_mixin.py:94, 650-680`; `pb_form_studio_lists/models/people_lists.py`, `contract_lists.py` |
| F7 | A pay formula's employee/contract input is `hr.formula.rule.application_source_key` = `employee.<field>` / `contract.<field>` (+ related keys whose first hop is the field) | `pb_hr_payroll_formula/models/application_domain_sources.py:19-55, 145` |
| F8 | The R14 "Standard fields" tab existed only in the employee bridge (template + patch), listing the placeable standard fields with My Payobook ticks | `pb_form_studio_people/static/src/xml/people_form_patches.xml:118-145` (before) |
| F9 | "Add existing" listed every placeable field not on the screen, unsorted | `pb_form_studio/static/src/js/studio_overlay.js` `hiddenFields` (before) |
| F10 | OWL templates have no `Boolean()` — `ctx.Boolean is not a function` (found in the walk) | gotcha FS7-1 |

## 2. What was built

### Engine `pb_form_studio` 19.0.1.2.0 → **19.0.1.3.0**
* `pb.form.field.meta`: `std_hidden`, `std_country_ids`, `std_labels` (Json `{lang: label}` — not a
  translated field, which would show the English label to Vietnamese readers until someone typed
  one; the spec asks for "vi/id fall back to built-in until set").
* `models/form_standard.py` (new, `_inherit='pb.form.studio'`):
  * **ONE locked hook** `_pbfs_standard_locked(model)` → `{field: {'reason', 'label'}}` (engine: every
    field that must be filled in to save, model AND form; hosts add the rest, §3).
  * Catalogue `_pbfs_std_catalogue(model)`: every box of the record's native forms (combined form,
    read through `_get_view` without the R23 rule), under its **on-screen label in the reader's
    language**, grouped by the tab it sits on ("Top of the page", each tab, "Below the tabs"), plus
    side-panel-only boxes (hosts' `_pbfs_std_panel_boxes`), cached with the screen designs.
  * `_pbfs_std_rules(model)` — THE rules every screen applies (locked fields never come back hidden).
  * `_pbfs_std_apply_arch(arch, model, country_field)` — hosts call it from `_get_view`: own label on
    the field and its `<label for>`, `invisible` joined with the product's rule (`(old) or (new)`),
    a card (group / tab) whose every box is hidden is hidden with them; sub-lists never touched.
  * `update_standard(model, name, vals)` — administrator only; refuses in screen words; one history
    line; clears the screen-design cache (every worker follows) and tells open screens (bus) when
    called from the Field library (FSD-1). Publish routes standard fields to it (no pay-run guard:
    no column is added or dropped) and clears / notifies ONCE at the end.
  * Audit line when an upgrade removes a field that had a rule (`ir.model.fields.unlink` +
    `_pbfs_std_sweep`).
  * `render` hides a placed standard field where its rule hides it; `get_studio` / `library` carry
    every standard field with its rule (`stdbox`).
* Overlay: **one "Standard fields" tab for every record type** (moved from the employee bridge, its
  My Payobook behaviour kept), grouped by tab, with the R23 panel: **On screen** (Shown / Hidden for
  everyone / Hidden in some countries + country picker, "(not used there)" against countries where
  the product already hides it, the product's own rule spelled out), **Label** per language with the
  built-in label as placeholder and **Reset**, the lock reason greyed. Field library: standard rows
  beside own fields, an Edit sheet with the same controls, a one-click "back to how the product shows
  it" (undo), two KPI tiles (Standard fields hidden / renamed).
* **R24**: search box (accent-insensitive: "bang ca" finds "Bang cá nhân", "blóod" finds "Blood
  type"), count "n of N", clear (x), "No field matches" + Clear the filter, `/` focuses the search,
  Esc clears it; client-side only (no server call per keystroke).
  * **Add existing**: sticky at the top, list sorted A–Z, type chips All / Text / Number / Date /
    Choice / Yes-No / Link.
  * **Standard fields** tab: chips All / Hidden / Renamed / On My Payobook (employee only) +
    "Country of Work" picker (fields that show for that country).
  * **Field library**: chips All / Own fields / Standard fields / Hidden / On My Payobook + record
    type + "Country of Work" picker.
* `form_studio_service.js`: every browser forgets its stored form designs when anybody publishes
  (bus), so "Full details" shows the change on its next open without a page reload.

### Hosts
* `pb_form_studio_people` 19.0.1.2.0 (R22) → **19.0.1.3.0**: employee locked list
  (`models/standard_fields.py`), side panel follows the rule (`_e360_details`), every employee form
  follows it (`hr.employee._get_view`), side-panel-only boxes from `_SPEC`, TIDY-E's rule surfaced.
  The R14 tab code left this module (now in the engine).
* `pb_form_studio_contracts` 19.0.1.1.0 (R22) → **19.0.1.2.0**: contract locked list, contract panel
  terms (`_cd_terms` — so a hidden term also leaves the panel's save list), full contract form
  (`hr.contract._get_view`), panel-only terms from `_TERMS`.
* `pb_form_studio_lists` 19.0.1.0.0 → **19.0.1.1.0**: People / Contracts table headings, picker and
  Excel headings follow the label; a field hidden for everyone leaves the picker; cells unchanged.

Not edited: any standard addon, `pb_lifecycle/`, `pb_pack_*`, `pb_me_portal`, `pb_people`,
`pb_employee_vault`, `pb_contracts`, `pb_filter_kit`, `pb_employee_form_tidy` (reached from outside).

## 3. The locked list (cannot be hidden; the label can change unless marked)

Worked out live per database (formula and pay-data use) — counts on the local copy: **employee 82
of 148 locked (66 free), contract 29 of 34 locked (5 free)**. The screen shows the reason as below.

| Why (as the screen says) | Employee fields (as on screen) |
|---|---|
| It names the person on every payslip and file. **Label locked too.** | Employee Name |
| Pay rules, statutory files and the fields each person sees follow this field. **Label locked too.** | Company, Country of Work |
| It must be filled in to save the record, so it always stays on screen. | Employee Type, HR Responsible, Home-Work Distance unit, Marital Status, Timezone |
| Pay or statutory files depend on this field. | Wage, Hourly Cost, Working Hours, Current Contract, Current contract from / until, First contract, Date of Joining, Trial period, Departure Date / Reason / Additional Information, Overtime Ruleset, Absence policy family |
| Approvals, access and the pay set-up follow this field. | Department, Job Position, Job Title, Manager, Work Address, Work Location |
| Logins, approvals and the time clock follow this field. | User, Work Email, Employee ID, PIN Code, RFID/Badge Number, Clock number, Time Off / Expense / Attendance approvers |
| Government forms and statutory files print this field. | Birthday, Gender, Nationality (Country), Identification No, Passport No, Work Permit No, SSN No, Social insurance number, the home address boxes, Dependents |
| Tax and social insurance files depend on this field. | Personal tax code, Indonesia NPWP number, Residency Status, Subject to PIT |
| Bank files depend on this field. | Bank, Bank Accounts, Account holder, Bank name / branch / account number |
| Pay or statutory files of that country depend on this field. | the Vietnamese insurance / tax / payroll-facts boxes, Indonesian BPJS and PTKP, Indian PAN / UAN / ESI / regime, Singapore residency and SHG fund, Insurance Code, Social insurance (BHXH) |
| A pay formula reads it / A pay data file fills it, so pay depends on this field. | any field this database's pay set-up reads (live check) — e.g. on rize several Payroll facts and Indonesian boxes |

| Why | Contract fields |
|---|---|
| It names the contract on every payslip and file. **Label locked too.** | Contract Reference, Company (+ Country of Work) |
| It says whose contract this is. | Employee |
| It must be filled in to save the record … | Contract Start Date, Employee Category, Wage, Working Schedule |
| Pay or statutory files depend on this field. | Contract End Date, Status, Salary Structure / Type, Scheduled Pay, Pay band, Where the pay sits in the band, Salary Journal, Trial ends, Probation start date, Contract Type, Contract Components, Employment status, TU / SHUI participation, No of dependents, Tax number, Salary denomination, the two Vietnam payroll treatments, analytic split |
| Approvals, access and the pay set-up follow this field. | Department, Job Position |

Free to hide/rename on the local copy: employee — Blood type, Religion, Job level, Visa No / status,
Legal given/family/legal name, Place / Country of Birth, Spouse boxes, Field of Study, School,
Certificate Level, Tags, Coach, Buddy, HR business partner, the weekday work places, Additional
Note, Emergency contact, Work Phone / Mobile, private email/phone, Indonesia family card, Safety
training group, Internal Committee member, More than six years in the sector, Overtime Status, Fire
Prevention Officer, Performance rating, … (66); contract — HR Responsible, Location, Cost center,
Notes, Contract signed on.

## 4. Where labels deliberately do NOT change
Mapping, the Updates sheets, pay data files and their review, pay formulas and the formula
catalogue, reports (Insights), government forms, My Payobook (incl. My details), the history lines
and audit — they keep the built-in name: their names are contracts with files customers already
hold. Nothing is written on the field itself. The contract cockpit page shows no standard labels
(its chips are values), so nothing to rename there. Table CELLS are unchanged; only headings,
the picker and Excel headings follow.

## 5. Tests (numbered) — `pb_form_studio_people/tests/test_fs7_standard.py`, `pb_form_studio_contracts/tests/test_fs7_standard.py` (tag `fs7`) + scripts

| # | Case | Result |
|---|---|---|
| 1 | Hide Blood type for everyone → gone from Full details (every occurrence), side panel; not a table column / not in the picker; value unchanged; field label unchanged (Mapping/formulas read the field); form as the modules draw it unchanged; history line | PASS (test_01; browser walk) |
| 2 | Hide Job level for India → hidden for an India employee, shown for Vietnam, on Full details and the side panel; the "Position" card left empty for India is hidden too; value kept | PASS (test_02; walk: India's Employment profile shows no empty Position card) |
| 3 | Rename "HR Responsible" (contract) → contract panel, full contract form (field + label), Contracts table heading, Excel heading in English; vi/id keep the built-in until typed; Reset restores; People heading follows a renamed Department | PASS (contracts test_03, test_03b; employee test_03; walk via the Field library Edit sheet) |
| 4 | Locked: wage, bank, Country of Work, name, company, birthday, ID no, manager, user (employee) and wage, dates, structure, person, status, schedule, department (contract) → Hide greyed with the reason; direct call refused; label of name / company / Country of Work refused, label of wage allowed; every field required to save is locked; a field locked AFTER it was hidden is shown again everywhere and can only be shown more | PASS (test_04, test_04b, contracts test_04; walk: RPC refusal "It must be filled in to save the record… It cannot be hidden.") |
| 5 | TIDY-E rule (Indonesia-only family card) for a Vietnam employee: hidden by the product; admin hides it for Vietnam too → still hidden (expression `(product) or (admin)`); hidden for Indonesia too → hidden everywhere; "Shown" again never shows it outside Indonesia; the panel says "Not used in other countries" and marks "(not used there)" | PASS (test_05; walk) |
| 6 | HR manager (not administrator): Form builder, Field library, update_standard, publish → refused; they see the result | PASS (test_06) |
| 7 | Silent install: 0 rule rows; markup before/after **byte-identical** for the employee + contract forms (en, vi) and the side panel / contract panel of 3 employees + 3 contracts (VN, ID, IN) and both table column sets — follow-up code (1c) vs this branch after `-u` | PASS (test_07 + `t7.sh`: 13 of 13 SAME, re-run after the rebase) |
| 8 | Payslips recomputed identical after hiding 5 and renaming 5 | see §9 (rize-copy rehearsal) |
| 9 | `-u hr,pb_contracts,pb_employee_form_tidy` on a copy with 3 hidden + 2 renamed: rules kept (5 rows), Blood type still hidden, both labels still shown, panels / terms / columns identical; the only form differences come from the core views' own refresh (attendance button, resume list context), not from the rules | PASS (`t9.sh`, upgrade 175–204 s, 0 ERROR; re-run after the rebase) |
| 10 | Draft changes nothing; Publish → history (one line per field + the publish line) → undo (publish back / Field library undo) → history keeps both; **two workers** both see a change and its undo without restart (12/12 answers from 2 worker processes each time) | PASS (test_10; `t10.sh`: 0/12 → 12/12 → 0/12, workers 2) |
| 11 | vi/id PO gate (all four modules: every new msgid translated), no "Odoo" in any new string / template / .po msgstr; console clean (one pre-existing manifest-icon warning); 390 px: overlay one column, sticky filter, no sideways page scroll (scrollWidth 390), Field library no sideways page scroll (table scrolls in its own box) | PASS (people/contracts/engine PO tests; walk) |
| 12 | Publish of 5 hides + 5 renames < 2 s; no column added (hr_employee column count equal) | PASS locally (test_12; walk publish 0.37 s incl. screen); Rize size in §9 |
| 13 | **R24 filter** — Add existing: "blóod" → 1 of 81 (Blood type); "pass" + Date chip → 1 (Passport Expiration Date); "zzzz" → "No field matches"; clear (x) → 81 fields, focus back in the box; Esc clears and the Form builder stays open; "/" focuses the search; list A–Z. Standard fields tab: chips Hidden (2), Renamed (1), On My Payobook (0); Country of Work India → 120 of 150 (Vietnamese/Indonesian boxes and India-hidden Job level gone), Vietnam → 143 of 150; "grade" + Vietnam → 1; clear → 150. In Vietnamese: "bang ca" → "Bang cá nhân". Field library: "respons" → 2, "hr résponsible" → 2, Hidden → 2, Own fields → 0 with the empty state, Standard fields 182, India → 152, India + "grade" → 0, clear → 182, "/" focuses | PASS (walk, desktop 1440 + phone 390) |

Suites (touched modules + TIDY-E + native look, `--test-tags`), fresh copy of `fsf1_base`
upgraded: see §5a. Baseline at the follow-up (1c report): 126 tests in the five Form builder suites,
0 failed.

### 5a. Suite runs (`--test-tags` of the seven modules, fresh copy of `fsf1_base`, `-u` of all seven)
* First full run: 2 failed — test 12 (a 10-field Publish took 6.9 s under load: the screen-design
  cache was cleared per field, FS7-5, fixed) and the people PO test (export artifacts, FS7-6, fixed).
* Before the rebase, after the fixes: **167 tests, 0 failed, 0 errors**.
* After the rebase on `48a80cb14` (R22 included): **175 tests, 0 failed, 0 errors** — engine 41,
  contracts 30, lists 13, people 33, reach 48, TIDY-E 48, native look 8 (15 of them new, FS-7).
* Final, on `origin/19.1` `8b33b7e0b` (follow-up 1 live + Codex merge) with the tab names, R25 and
  R26, on a local copy brought to the live state first: **178 tests, 0 failed, 0 errors** (reach 51
  = 48 + 3 new). Tests 7 and 9 re-run on that tree: 13/13 SAME; rules kept after `-u hr,
  pb_contracts, pb_employee_form_tidy` (175 s), the only form differences again core's own.
* Browser (local copy at the live state): R25 — Spouse Legal Name: "Employee can change it" greyed,
  "Changed through My details › Family"; R26 — Blood type: "Saves at once" greyed, title and note
  "Sensitive detail — HR always approves", HR approves selected; console clean.

## 5b. Addition (coordinator, 2026-11-20): tab names still English in Vietnamese / Indonesian

Found on the five live databases by reading the stored screen designs (read-only, `fs7_tabs.sh`):

| Tab (screen) | Owner | vi before | id before | Words now (vi / id) |
|---|---|---|---|---|
| Payroll Info (Full details) | pb_hr_payroll_formula | ok | **English** | Thông tin tiền lương / Info Penggajian |
| Insurance (BH) (Full details) | pb_hr_payroll_vietnam | ok | **English** | Bảo hiểm (BH) / Asuransi (BH) |
| Tax & Dependents (Full details) | pb_hr_payroll_vietnam | ok | **English** | Thuế & Người phụ thuộc / Pajak & Tanggungan |
| Payroll facts (full contract form, rize only) | pb_payroll_mapping_vn | **English** | **English** | Dữ kiện tính lương / Data penggajian |
| Employment profile, Payroll facts (Full details) | pb_employee_vault, pb_payroll_mapping_vn | shown translated since FU1 (code terms), stored copy missing | same | stored copy written with FU1's words |

Two fixes, as the ledger asks: (1) **.po** — code terms in `pb_form_studio_people` (employee) and
`pb_form_studio_contracts` (contract), applied in `_get_view` only while a tab still reads the English
words (FU1-4 seam: owners are not installed everywhere; an owner translation wins); (2) **stored
value** — `fs7_tabfix.py` writes the missing languages into the owning screen designs on every
database at go-live (only a language that is missing or still English; an existing translation is
never changed; a second run writes nothing — proved locally: 5 written, then 0). "Tham gia BHXH" (a
box, not a tab) untouched.

## 5c. Owner rulings R25 / R26 (2026-11-20), shipped with FS-7

* **R25** — Spouse Legal Name and Spouse Birthdate go back to HR: they may still be shown on My
  Payobook, but "Employee can change it" is greyed with "Changed through My details › Family" and
  refused on the server (`pb_form_studio_people` `PORTAL_SPOUSE` in `_pbfs_portal_locked`).
* **R26** — Blood type and Religion stay changeable by the employee, but **HR always approves**:
  a new engine hook `_pbfs_portal_sensitive(model)` (`{field: reason}`; the employee host lists the
  two in `PORTAL_SENSITIVE` — add a name there to make more fields sensitive). "Saves at once" is
  greyed with "Sensitive detail — HR always approves" (Form builder panel and both Field library
  sheets) and refused on the server by `update_portal`, by Publish, and by `portal_apply` without an
  approver (every saved-at-once path); a mode stored before the ruling is read as "HR approves".
* Upgrade step `pb_form_studio_people/migrations/19.0.1.3.0/end-r25_r26_portal.py`: unticks a spouse
  box left changeable and sets a sensitive box left "Saves at once" back to "HR approves", one
  history line each, counts in the log; idempotent.
* Ticks found before the go-live (read-only, ×5): **0 rows on every database** (payobook,
  payobook_template, p0clone, rize, sudima: no spouse / blood type / religion tick at all) — nothing
  to untick.
* Tests (`pb_form_studio_reach/tests/test_r19_boxes.py`, tree shipped as files only — no version
  change): R19's B1–B8 adapted (spouse now in the closed list; "saves at once" only for the two
  distance boxes) + `test_r25_spouse_back_to_hr` (screen data, direct call, forged My Payobook post),
  `test_r26_sensitive_always_hr` (screen data, direct call, Publish, saved-at-once write refused;
  the employee's blood-type change lands in the approver's inbox, value unchanged until approved,
  approval writes it), `test_r25_r26_saved_ticks_corrected_on_upgrade`.

## 6. Deviations (stated, not silent)
1. **`_get_view` instead of extending the generated inherited view** (`_pbfs_sync_native_view`).
   Reason: a generated `xpath` per box can go dead when an upgrade removes a box — and Odoo does
   not apply custom views while it upgrades, so the dead xpath would only break the form AFTER the
   upgrade (rail "must not break the form"). Working on the combined form (core precedent F1, the
   TIDY-E precedent F2) handles every occurrence of a box and its `<label for>`, can never go dead,
   and follows FSD-1 (every change clears the screen-design cache itself). The generated "Company
   details" page is untouched.
2. Labels stored as `{lang: text}` (Json), not a translated field — see §2.
3. No separate "Standard boxes" list: the controls live in the existing "Standard fields" tab and the
   Field library (owner clarification). The tab moved from the employee bridge into the engine so
   the contract has it too; its My Payobook behaviour is unchanged.
4. Locked list: TIDY-E's one-country boxes are locked only when statutory (§3); the training facts,
   the family card and the two Vietnamese demo flags stay hideable unless the database's pay set-up
   reads them — otherwise rule 6 (test 5) could never apply. Formula catalogue fields are locked
   only when a pay formula or pay data file of THAT database uses them (Job level is hideable on a
   database where nothing reads it).
5. Hidden for some countries in a table: the column stays (other rows show it); only a field hidden
   for everyone leaves the picker (spec: "header label + picker only").

## 7. Gotchas (ledger rows)
* FS7-1 OWL templates cannot call `Boolean()` / `Number()` / `String()` (`ctx.Boolean is not a
  function`) — use `!!x` or a component method.
* FS7-2 A component getter named like a `t-foreach` loop variable (`get lang()` vs `t-as="lang"`)
  silently wins over the loop value — every language label read "English". Never name a getter
  like a loop variable.
* FS7-3 The web client keeps form designs on disk; after a server-side view change the FIRST load
  is the old design. Trigger `rpcBus.trigger("CLEAR-CACHES", "get_views")` (done on publish, through
  the bus for every browser).
* FS7-4 Two `_get_view` overrides on the same model run in an order you do not choose (here TIDY-E
  and the R23 rule): never rely on the other's output; ask its rule table instead (`removed`).
* FS7-5 `clear_cache('templates')` per field inside one Publish made a 10-field publish take ~7 s
  under load (each field re-scanned the forms in three languages): clear once at the end.
* FS7-6 `odoo-bin i18n export` picks tuple items next to `_()` calls as msgids (`('ssnid',)`) and
  writes "Odoo Server" in the .pot header: strip both before committing.

## 8. Owner questions (plain)
* Contracts have only five standard fields you could hide today (HR Responsible, Location, Cost
  center, Notes, Contract signed on); everything else feeds pay or the contract approval. Is that
  what you expected, or do you want some of the pay boxes to be hideable on screen for countries
  that never use them (they would still be paid on)?
* Renaming changes the screens, the People/Contracts table headings and the Excel heading, but NOT
  Mapping, the Updates sheets, pay data files or My Payobook. Should My Payobook follow your own
  label too (one more step), or keep the built-in name the employee already knows?

## 9. Go-live (rize-copy rehearsal + ×5)

Deploy method exactly as `FS_DEPLOY_HANDOVER.md` (scripts cloned from the FS go-live: `fs7_prep.sh`,
`fs7_rehearse.sh`, `fs7_golive.sh` + `fs7_tries.sh`, `fs7_verify.sh`; read-only helpers
`fs7_probe.py`, `fs7_tabs.sh`, `fs7_ticks.sh`; `fs7_tabfix.py`, `fs7_rules.py` on the copy only).
Deployed commit `d9afe27a1` (origin/fs-7 = origin/19.1 `8b33b7e0b` + FS-7). START line
02:13 UTC; no other deployer's START open; shared lock free.

**Prep** (`/odoo/backups/fs7-20261120T021306Z`): five dumps read back (payobook 84 MB,
payobook_template 31 MB, p0clone 32 MB, rize 46 MB, sudima 35 MB), file folders linked, previous
trees saved; staged trees = commit, live trees = origin/19.1 for all five modules.

**Rehearsal on a hidden rize copy** (jobs and mail off; dropped after):
* upgrade 17 s, 0 ERROR, 0 Traceback; data counts restored vs upgraded **identical**;
* silent: 0 rule rows, the employee and contract forms **byte-identical** old code vs new (same
  hash), 168 standard fields listed on the employee;
* **test 8** — runs 2113–2116, 211 payslips / 6,914 lines: old vs new **0 differing**; old vs after
  hiding 5 and renaming 5 standard fields **0 differing** (180 payslips refused identically both
  times, as in every earlier rehearsal: closed payslips are not recomputed);
* **test 12 at Rize size** — Publish of 5 hides + 5 renames **0.56 s**; no column added (208 → 208);
  the employee form then builds in 0.41 s;
* tab names: 9 stored translations written (Indonesian for Payroll Info, Insurance (BH), Tax &
  Dependents; both languages for Employment profile and the two Payroll facts tabs), 3 kept;
  still English afterwards: 0.

**Waiting for the window**: tries every 10 min from 02:37 UTC — refused while Codex held the shared
lock (02:28–03:21, 04:37–) and while rize had signed-in activity (Rize testers); the 23rd check at
05:58 found rize and payobook quiet since 05:43.

**Go live ×5** (`fs7_golive.sh`, order payobook_template, p0clone, sudima, rize, payobook):
* service stopped 06:00:14, started 06:02:46 — **152 s down**; addons = staged for all five trees;
* `-u pb_form_studio, pb_form_studio_people, pb_form_studio_contracts, pb_form_studio_lists`: 17–19 s
  each, all exit 0, 0 ERROR; `pb_form_studio_reach` files only (tests);
* verification (`fs7_verify.sh`): 5 trees = commit; manifest = installed version on every database
  (25 rows); jobs = snapshot ×5 (none re-activated); data counts before the stop = after ×5;
  **silent ×5**: 0 screen rules, employee and contract forms identical to the modules' own;
  R25/R26 upgrade step: 0 unticked, 0 set back (no tick existed) ×5; tab names written into the
  stored screen designs (5 per database, 9 on rize), **0 still English** ×5; server log since the
  stop: 2 lines = a websocket presence update cut by the stop, 0 asset errors, 0 upgrade errors;
  all five sites 200;
* not done because of the owner hold: the payobook.com check that renames one demo-safe box and
  hides one (§ handover "Deploy"). Nothing was changed on any customer database by us.

Backups: `/odoo/backups/fs7-20261120T021306Z/` (five dumps + file folders + previous trees).
Rollback is never by module version; if ever needed, the screen rules are switched off by
"Shown" / "Reset" in the Form builder (no data was changed).

Deployed commit `d9afe27a1`; `fs-7` then merged with the newer `origin/19.1` (Codex commits in
biz_access, pb_dashboard, pb_me_team, pb_settings, ops/tools only — none of the five shipped trees
changed, so tests 7–9 needed no re-run) and pushed; `origin/19.1` fast-forwarded to it.
