# FS-15 — Standard fields: change the country rule on screen, bring back removed fields, country picker

Builder, tester, self-reviewer and deployer, 2026-11-21 (UTC). Handover `FS15_HANDOVER.md` (main checkout,
untracked). Branch `fs-15` from `origin/19.1` @ `d70eec477`.

**Result:** **LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima; abm
untouched) at code commit `1ec98ca0c`, **200 s down** (07:29:09–07:32:29 UTC). Deploy notes: START 06:44, DONE
07:32, NOTE 07:36. Tries 1–4 waited for 15 quiet minutes (Rize in use 06:20–07:02 UTC); no other deployer's
START open. Silent: nothing changed on any screen (§5); no setting made on any live site.

## 1. Verified facts (do not re-derive)
* TIDY-E's table `pb_employee_form_tidy/models/form_rules.py` `FORM_RULES`: 35 `REMOVE`, 42 one-country (VN 29,
  ID 5, IN 5, SG 3). Applied in `hr.employee._get_view` (tidy) — now through `_pb_tidy_rules()`.
* FS-7 rows on the live sites before FS-15: **0** (`std_hidden` 0, hidden-in countries 0, own labels 0 on all
  five) — the read-time translation of FS-7 rows (§2) changes nothing anywhere today.
* Countries of Work a person can have = the choices of `hr.employee.payroll_country` (VN, ID, IN, SG, MY + TH,
  KH, PH). The People filter's figures = active people of the reader's companies grouped by that box
  (`pb_people._pbf_base_domain`), "Not recorded" = empty.
* The legacy Insurance (BH) / Tax & Dependents groups sit under `invisible="vn_uses_payroll_profile"`
  (true for HR viewing a Vietnam employee, FIELD_AUDIT_FACTS §3): a removed box inside them would never be
  drawn for the people it belongs to — hence "stays off" for those (§3).
* The side panel never applied TIDY-E's rule; its country groups are fixed by `pb_employee_vault`
  (`_SPEC` gates VN / ID / IN / SG). The 16 boxes that can come back have no side-panel place.
* The My Payobook page builder has no "add a country" box (only a Country of Work filter `<select>`), so the
  new picker is used in the four places of the Form builder only.

## 2. What was built (ruling R31)
Modules: `pb_form_studio` 19.0.1.5.1 → **19.0.1.6.0**, `pb_form_studio_people` 19.0.1.5.0 → **19.0.1.6.0**,
`pb_employee_form_tidy` 19.0.1.3.1 → **19.0.1.4.0**, `pb_learn` one replica word (files only, version
unchanged). Never touched: `pb_lifecycle/`, `pb_pack_*`, `pb_me_portal`, standard addons, `pb_form_studio_portal`.

* **"Shown for" — one control** (Studio settings column and Field library Edit sheet): All countries | Only
  these Countries of Work [chips] | Hidden for everyone; a "Built-in setting: Only Vietnam" line, the badge
  "Built-in setting" / "Changed", **Reset to built-in**. Removing the last country = Hidden for everyone.
  Stored on the settings row: `std_show` ('all' | 'only' | 'none'; empty = built-in), `std_show_country_ids`,
  `std_show_unset` (people with no Country of Work see it too). A choice equal to the built-in setting is
  stored as "built-in" (no row change).
* **Where it is applied:** boxes with a built-in country rule → TIDY-E's `_get_view` reads the administrator's
  setting through `pb.form.studio._pbfs_std_tidy_overrides` (one ISO code, or a set of codes; sections open
  wherever one of their boxes shows); every other box → the engine's `_pbfs_std_apply_arch` (as FS-7). Side
  panel, contract panel, Company details grids and table columns read `_pbfs_std_rules` (same helper, new
  shape `{all, only, unset, show, builtin, label}`).
* **Locked ("Always shown") fields:** may be widened (more countries, All countries); never shown less than the
  built-in setting — the narrowing choices are disabled with "Cannot be hidden. <reason>", built-in countries
  carry a lock on their chip, and the server refuses (direct call and Publish). A narrower rule saved before a
  field became locked is widened back on screen at once and in the stored row at the readers' save point
  (`_pbfs_std_unhide_locked`).
* **FS-7 rows** ("hidden for everyone", "hidden in some countries") read exactly as before: hidden-in H =
  shown for every Country of Work except H, people with no Country of Work included; the next save writes the
  new columns. The FS-7 keys `std_hidden` / `std_country_ids` are still accepted by `update_standard`.
* **Taken off the screens:** the 35 boxes are listed (Studio: last group of the Standard fields tab + chip;
  Field library: chip + "Show again" button), with their on-screen name and the tab they were on. "Show again"
  proposes Vietnam (all except the two general Employment profile boxes, which propose All countries) and is
  drawn in its old place on Full details. 19 are greyed with the reason and refused by the server (§3).
* **Country picker:** opens on focus; "Countries of Work in use" with people (most first, the People filter's
  figures), "No Country of Work" (standard fields only), then "Other countries" by typing (accent-insensitive);
  arrows / Enter / Escape; same component for own and standard fields in the Studio and the Field library.
* **Wording:** chip "Locked" → **"Always shown"** (vi "Luôn hiện", id "Selalu ditampilkan"), reason on hover;
  note "Cannot be hidden. <reason> You can still rename it." (when the label is not locked); legend; Field
  library column; the Learn lesson's Field library replica (lesson text names no old control).
* vi/id: 51 new words in `pb_form_studio` (+6 field/choice names), 4 in `pb_form_studio_people`.

## 3. Taken off the screens — which can come back
| Box (as on screen) | Was on | Can come back? | Proposed | Why |
|---|---|---|---|---|
| Level of Health Compensation, Trade Union Participation, Funeral Fund Participation, Female Excluding Pregnant, OSH Worker Code, Trade Union Fee Code, Basic Overtime Electricity, BD PHSK, Deduction of Funeral Money, Different Subjects, Legal Entity Pays Salary (11) | Payroll Info | **Yes** | Vietnam | old Vietnamese pay inputs, values kept, nothing replaced them |
| Position reference, Emergency contact relationship (2) | Employment profile | **Yes** | All countries | general boxes |
| Enrolled in family health cover, Enrolled in private health cover, Dependants on private health cover (3, rize only) | Payroll facts | **Yes** | Vietnam | Vietnam payroll facts |
| Account Number, Bank (2) | Payroll Info | No | — | the approved bank account under Bank details is the truth (R12, FS-9) |
| Contract Type, Pay Category (2) | Payroll | No | — | the contract holds contract type and pay structure; old record's boxes |
| Employer / Employee Insurance Cost, Total Insurance Contribution, Personal Tax Rate, Monthly Tax Allowance, Dependent Tax Allowance (6) | Insurance (BH), Tax & Dependents | No | — | worked-out figures, never typed, always 0 |
| Foreign Employee Exempt, SI / HI / UI Number and Effective Date, Tax Table, Tax Regime Effective Date (9) | Insurance (BH), Tax & Dependents | No | — | their old section is never drawn for Vietnam staff (replaced by the summary) |

Shown again = Full details only (none of the 16 has a side-panel place); the setting says so on screen.

## 4. Tests
Local base `fs15_base` = `wf2p6_base` + the Form builder stack, `pb_me_tax`, `pb_payroll_mapping_vn`, with the
modules whose code was newer than the base upgraded first (`biz_approval_workflow`, `pb_approval_config`,
`pb_lifecycle`, `pb_timeoff`, `pb_explorer`, `pb_me_portal`, `pb_learn` — without that, 20 setup errors on
both sides hide everything). `--test-tags`.

| Run | Result |
|---|---|
| `/pb_form_studio,/pb_form_studio_people,/pb_form_studio_contracts,/pb_employee_form_tidy,/pb_form_studio_lists,/pb_form_studio_reach,/pb_form_studio_portal` | **237 run, 1 failed** = people `test_13` (pre-existing, recorded in FS-12/13/14; also red on `origin/19.1`'s code, run `fs15_bl`) |
| after the last fix: `/pb_form_studio_people,/pb_form_studio_contracts,/pb_employee_form_tidy,/pb_form_studio` | 155 run, the same 1 (`test_13`) |
| baseline `origin/19.1` code (same base, before the env upgrade) | 7 failed + 15 errors, all environment; FS-15 adds none |

FS-7/FS-11 expectations changed with R31 (`pb_form_studio_contracts/tests/test_fs7_standard.py` 2b,
`pb_form_studio_people/tests/test_fs7_standard.py` 05 and 07, `test_fs11_fixed.py` 01c): the same behaviour,
new form of the expression (an FS-7 "hidden in India" is now "shown for every other Country of Work"), and
the "as the modules draw it" read now draws the removed boxes (gotcha FS15-1).

| # | Test | Evidence | Result |
|---|---|---|---|
| 1 | silent upgrade ×5: Full details + side panel identical (3 people per Country of Work per site), FS-7 rules keep their effect | rehearsal §5: forms (en, vi, id, contract) and side panel **byte-identical** old vs new on all five copies (rize: 5 countries incl. "not recorded", 14 people); employee pages identical (sudima: FS14-7 session noise); `test_01`, `test_09` (an FS-7 "hidden in India" reads the same, people with no Country of Work keep it), tidy `test_no_setting_is_the_built_in_table` | PASS |
| 2 | widen a Vietnam-only field to Indonesia → Publish → shown for Indonesia; two workers; Reset | `test_02`, `test_02b` (Publish path); browser (Safety training group: + Indonesia from the drop-down, chip "Indonesia + Vietnam", publish line "shown for: Only Indonesia, Vietnam"); two workers (local `--workers=2`): 12/12 requests old form → change → 12/12 new form → Reset → 12/12 old, requests served by both workers; rehearsal copies payobook + template: VN shown, ID shown, Reset → form hash = first | PASS |
| 3 | locked field: widen OK, narrow/hide refused (screen + direct call) | `test_03` (NPWP widened to Vietnam; none / only Vietnam / FS-7 keys refused, Publish refused; birthday cannot be narrowed), `test_03b` (older narrower rule widened back); screen: choices disabled with "Cannot be hidden. <reason>", built-in country chip locked; rehearsal copies: refused | PASS |
| 4 | Show again a removed field for Vietnam → in its place; greyed ones refuse by direct call; undo | `test_04` (Level of Health Compensation: off → shown for Vietnam on Full details › Payroll Info, listed on the canvas → "back to how the product shows it" = off again), `test_04b` (Account Number, Bank, Contract Type, Pay Category, the worked-out figures refused); browser: Field library "Taken off the screens" → Show again (proposed Vietnam) → Save → Full details of a Vietnam person shows the box; rehearsal copies: shown for VN, not ID; stays-off refused | PASS |
| 5 | picker: opens on focus with in-use countries + counts = People filter, typing finds others, keyboard | `test_05` (counts = the People filter's domain, most first, also in `get_studio` / `library`); rehearsal: rize **ID 126, VN 70, IN 29, SG 2, not recorded 3** (= the owner's People filter), sudima VN 651, payobook VN 4,581; browser: focus opens the list with people counts, "sing" + Enter adds Singapore, × removes | PASS |
| 6 | upgrade of `hr`, `pb_employee_form_tidy`, `pb_form_studio*` with settings in place keeps them | local: two settings (Show again for Vietnam, Vietnam + Indonesia) → `-u hr,pb_employee_form_tidy,pb_form_studio,pb_form_studio_people,pb_form_studio_contracts` (132 modules, 0 ERROR) → both settings and the form's expressions unchanged | PASS |
| 7 | three payslips identical | rize copy: **211 payslips / 6,914 lines old vs new, 0 differing** (31 computed, 180 refused identically) | PASS |
| 8 | non-administrator refused | `test_08` (HR manager: change refused, Form builder refused); FS-7 `test_06` | PASS |
| 9 | vi/id PO gate, forbidden word, console, 390 px | PO gate locally and on the server: pb_form_studio 555/555, people 141/141, tidy 48/48 vi and id, 0 empty, 0 vendor word; added lines: the vendor word only in code; browser console clean (Field library, Full details, Form builder); phone width: the browser window here does not go below its desktop width (as FS-14), the new parts use the existing one-column rules (picker full width, list max 220 px, 40 px lines) | PASS (phone width by CSS, not seen) |

## 5. Rehearsal and go-live
Scripts `docs/handovers/formstudio/fs15/` (clones of `fs14/`; on the server `/tmp/fs15_*`; staging built by
`fs15_stage_local.sh` from the pushed commit). Prep `20261121T060736Z`: staged = commit (4 trees), live =
`origin/19.1` (hash), server PO gate (pb_form_studio 555, people 141, tidy 48, learn 241 rows; 0 empty, 0 vendor
word), dumps ×5 read back (`/odoo/backups/fs15-20261121T060736Z/`: payobook 84 MB, template 31, p0clone 32,
rize 46, sudima 37), file folders linked, job snapshots, read-only probes as the administrator.

**Rehearsal** — hidden copies of all five with the LIVE module set (restored from the dumps), jobs + mail off,
`-u pb_form_studio,pb_form_studio_people,pb_employee_form_tidy` (cascades to every installed Form builder
module and `pb_employee_bank_panel`), dropped after (0 left):

| Copy | Upgrade | Data restored vs upgraded | Full details (en/vi/id + contract) old vs new | Side panel old vs new | Employee pages | Change on the copy |
|---|---|---|---|---|---|---|
| rize | 21 s, 0 ERROR | identical | byte-identical | byte-identical (14 people, 5 groups) | identical | see note |
| p0clone | 18 s, 0 ERROR | identical | byte-identical | byte-identical | (no login) | see note |
| sudima | 18 s, 0 ERROR | identical | byte-identical | byte-identical | differs = FS14-7 session noise | see note |
| payobook | 22 s, 0 ERROR | identical | byte-identical | byte-identical | identical (3) | widen Vietnam-only → +Indonesia: shown VN and ID; locked NPWP widened: shown VN and ID; narrowing refused ×2; Show again for Vietnam: VN yes, ID no; stays-off refused; Reset → form = first hash |
| payobook_template | 18 s, 0 ERROR | identical | byte-identical | byte-identical | (no login) | same as payobook |

Note: on the first three copies the change check ran with a harness bug (it read the form as the plain
administrator, who does not see the HR tabs, then from records without a saved Country of Work); fixed before
payobook (`fs15_probe.py`, commit `a09ad8cd4`); the code under test was the same.

**rize payslips: 211 payslips / 6,914 lines old vs new, 0 differing** (31 computed, 180 refused identically).
Form builder after the upgrade: rize 202 standard fields listed, 35 taken off the screens (16 can come back,
19 stay off), Countries of Work in use **ID 126, VN 70, IN 29, SG 2, not recorded 3**; sudima VN 651;
payobook VN 4,581; p0clone / template only "not recorded" (12 / 1). (The other sites have 32 of the 35: the
Payroll facts boxes exist on rize only.)

**Go-live** (`fs15_tries.sh`, lock taken, notes re-read for HOLD / open START before each try and right before
the stop): try 2 (06:54) made fresh backups ×5 but activity started during them — not stopped; try 5 (07:26):
quiet on rize, payobook, sudima since 07:11 → fresh backups ×5 → 07:29:09 stop → 4 trees rsynced (= staged) →
upgrades template 20 s, p0clone 23, sudima 20, rize 21, payobook 23 — all exit 0, 0 ERROR → asset purge +
`web.assets.version` → 07:32:29 port listening; five sites 200.

| Check (after, `fs15_verify.sh` + `fs15_after.sh`) | Result |
|---|---|
| Trees / versions | 4 trees = commit; manifest = installed ×5 |
| Jobs | = snapshot ×5 (111/58, 99/40, 99/48, 99/91, 100/91); none re-activated; payobook job 156 off |
| Data before the stop vs after | identical ×5 |
| Silent upgrade | 0 "Shown for" settings, 0 older hide rows, 0 labels ×5 |
| Full details (en, vi, id) + contract form, side panel | **identical before/after ×5** |
| Employee pages (My Payobook, My Profile, My details) | payobook 3, rize 3, sudima 1: all 200, 0 failed |
| Administrator /my | payobook, p0clone identical; template, rize, sudima differ = the new `web.assets.version` (as FS-14) |
| Server log since the stop | 2 ERROR = one chat-presence write on rize refused at the stop (as FS-14); 0 asset errors; upgrade logs 0 ERROR; one process |
| payobook.com in the browser (signed-in session) | Field library: chips "Taken off the screens", "Always shown"; own-field country box opens as a drop-down "Vietnam 4,560 people" (the People filter for that user's company), console clean; Cancel — nothing changed (0 settings after) |

The upgrade logs repeat the known warning "Two fields … have the same label: Country of Work" (TIDY-E's label
on two fields, present since TIDY-E; not an error).

## 6. Gotchas (ledger rows)
* FS15-1 The Form builder's "as the modules draw it" read (`pbfs_std_raw`) now also draws the boxes TIDY-E takes
  off the screens — tests that compared it with the live form must ignore `invisible="1"`; the Full details
  fixed lists skip a removed box until it is shown again.
* FS15-2 A Countries-of-Work "hide in" rule needs a universe to become a "show only" one: use the choices of
  `payroll_country`, and keep "people with no Country of Work" as its own flag, or the translation changes who
  sees the box.
* FS15-3 TIDY-E's container rule keeps its old output when no setting exists (two single countries in a
  group → each box decides); only a set of codes from an administrator makes a section open wherever one of
  its boxes shows. Never change the old branch: test 1 (byte-identical forms) depends on it.
* FS15-4 Worktree guard: a command line naming the scratchpad (its path contains "gitlocal") with pipes, loops
  or `&&` is refused — every step in a script file (FS10-1 / FS14-4 again).

## 7. Ledger
**R31** (2026-11-21, architect) The product's country rule and its removed list become DEFAULTS an administrator
changes on screen (Form builder › Standard fields / Field library: "Shown for", Reset to built-in, Show again).
Widening is always allowed (screen only); narrowing or hiding keeps the lock rule; 19 removed boxes stay off
(live source replaced them, worked-out figures, or a section never drawn) — FS15_REPORT §3.
Phase row: FS-15 — LIVE ×5 2026-11-21 07:32 UTC (200 s down); report `FS15_REPORT.md`.

## 8. Not done / owner questions
* Phone width (390 px) was checked by the stylesheet only: this browser window does not narrow below desktop
  width and the app refuses to load inside a frame. The new parts use the existing one-column rules.
* The My Payobook page builder has no "add a country" box, so it was not changed (its Country of Work filter
  stays a plain list).
* The Learn lesson "Add your own fields" names no old control; only its Field library picture said "Locked" —
  now "Always shown".
* Owner question: 19 boxes stay off the screens for good (table §3). If HR still wants, say, the old social
  insurance number box for Vietnam staff, it would need its old section brought back for Vietnam staff, which
  would show the whole old insurance block next to the summary. Keep them off?
