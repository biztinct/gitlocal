# FS-6 — employee and contract "advanced form" pages in the current look: report

Branch `fs-6` (from `origin/tidy-e` @ `883055489`, so the restyle is of the CLEANED
employee form). New module `pb_form_native_look` 19.0.1.0.0. `pb_theme`: one comment
only (no version raise needed). `biz_theme` (the engine): **not edited**. No edit in
pb_people, pb_employee_vault, pb_contracts, pb_lifecycle, pb_pack_*, pb_me_portal,
pb_employee_form_tidy or any country module. Built against `FS_HOSTS_HANDOVER.md`
§FS-6 + both addenda, `FORMSTUDIO_LEDGER.md`, `FS_HOST_FACTS.md`,
`FIELD_AUDIT_FACTS.md`, `FIELD_TIDY_HANDOVER.md`, `TIDY_E_REPORT.md`, design §1.1, and
the coordinator's addendum of 2026-11-20 (three pre-existing oddities, §4).

Result: **the full restyle is shipped; nothing stays stock** except what the engine
keeps stock everywhere by design (dialogs, sub-list rows).

## 1. Verified facts (file:line at `883055489`)

| Fact | Where |
|---|---|
| The opt-out: `vu-form-native` added to both forms at priority 99 | `pb_theme/views/vu_native_forms.xml:10-19` (employee), `:21-31` (contract); its comment pointed at the wrong path (fixed, now `biz_theme/...`) |
| The engine returns the stock template when the arch root has `vu-form-native` | `biz_theme/static/src/js/vu_form_compiler.js:134-137` |
| Engine on/off at render: `vuFormEnabled` (never in dialogs, kill-switch `pb_theme.vu_form_engine` / localStorage) | `biz_theme/static/src/js/vu_form_renderer.js:42-71` |
| x2many sub-views and settings forms always stock | `vu_form_compiler.js:118-123` |
| **The arch `class` of a `<form>` lands on the `.o_form_view` root, NOT on `.o_form_renderer`** (core `form_controller.js:707-716`; the renderer only gets `props.class`) | probe on the local copy: `o_form_view o_hr_employee_form_view pb-nl pb-nl-emp …` |
| Core notebook header: `.o_notebook_headers` scrolls, the `ul.nav` is `flex-nowrap` | `web/static/src/core/notebook/notebook.xml:6-7`, `notebook.scss:12` |
| Engine tab track: `width: max-content; max-width: 100%`, never wraps | `biz_theme/static/src/scss/vu_form_engine.scss:715-724` |
| Engine sub-list box: `overflow: hidden` (kills the list's own sideways scroll) | `vu_form_engine.scss:765-768` |
| Employee name has an inline `font-size: min(4vw, 2.6rem)` | core `hr/views/hr_employee_views.xml:122-123` |

### Why the opt-out was added (history)
`git log` of `pb_theme/views/vu_native_forms.xml`: one commit, `a0b982a95` (2026-06-19,
"Add Payobook Statutory Cockpit…"), six hours after the engine itself arrived
(`b023bde28`, ported from health19 already tuned for `hr.employee` — e.g. the
"presence row orphaned after its avatar joined the hero" rule). No ledger note; the
only reason on record is the file's comment: the forms' "own carefully-built layout
(avatar hero, multi-column identity, smart buttons) fights the generic hero/card skin".
I took the opt-out off locally (no fixes) and looked (`fs6/shots/engine_unfixed_*`),
dumped every field/label/button/tab, and found exactly what "fights" means today:

| # | Cause found with the engine on and no fixes | Seen |
|---|---|---|
| C1 | **Tabs cut off.** The pill track is at most the page wide and never wraps; the employee page has up to 12 tabs → "Payroll facts" cut at 1440 px; on a phone 3 of 12 tabs in sight (the rest only by an invisible sideways scroll). | `engine_unfixed_01_employee_vn_work.png` |
| C2 | **Oversized, mostly empty header.** The employee name keeps its inline 2.6rem, the four contact lines stack under it, the photo shrinks to 56 px → a ~290 px tall header card. Contract: an empty heading (hidden company line) leaves a blank band. | same + `engine_unfixed_…contract…` |
| C3 | **Phone too cramped.** Header card + tab card + section card + page padding left ~110 px for an input. | `engine_unfixed_10_contract_vn_phone.png` |
| C4 | **Sub-list columns unreachable.** The engine's rounded list box (`overflow: hidden`) removes the list's sideways scroll: on a phone the contract components list showed 2 of 8 columns and the rest could not be reached. | same |

Nothing was LOST in the dump with the engine on (§3: same fields, labels, buttons,
tabs, read-only and required states, 0 console errors) — the causes are about what can
be seen and reached, not about data. So the fix is styling, not structure.

## 2. What was built

`pb_form_native_look` (depends `pb_theme`, `hr`, `hr_contract`, `om_hr_payroll`,
`pb_hr_payroll_formula` — all installed on every database):

| File | What |
|---|---|
| `views/native_look_views.xml` | Two views, priority 100 (after pb_theme's 99): one `attributes` spec on `/form` each — `remove="vu-form-native" add="pb-nl pb-nl-emp"` / `pb-nl-con`. Nothing else (test 03 enforces it). |
| `static/src/scss/native_look.scss` | Scoped to `.o_form_view.pb-nl .o_form_renderer.vu-form` (only these two forms, only while the engine is on). C1: track wraps (`fit-content`, box radius) on wider screens; on a phone one row that scrolls sideways with snap, scrollbar hidden. C2: name at header size (`clamp(20px, 1.6vw+8px, 28px)` via a custom property — see gotcha FS6-1), contact lines in two columns, Country of Work on its own line with a short box, photo 76 px, empty contract heading closed. C3: one card level on a phone (tab body not a card, tighter card padding, cards never wider than the screen). C4: sub-lists scroll sideways again. Reduced-motion respected. Lucide only (engine icons), Payobook tokens only. |
| `views/employee_form_fixes.xml` + `i18n/vi_VN.po`, `i18n/id_ID.po` | The coordinator's three fixes (§4). |
| `tests/test_native_look.py` | 6 tests (§3). |

Kept stock on purpose (engine design, unchanged): dialogs opened from these forms,
x2many rows/sub-forms, the settings-style forms. The control-panel smart buttons
get the engine's card style (already app-wide).

Rollback: uninstall `pb_form_native_look` → both pages are back to the old look (the
pb_theme opt-out is still there underneath), the three labels/rows back as before.
Nothing to undo in data (proved, §3.2).

Self-review against the design mandate: hero moment = the header card (photo, name,
contact lines, Country of Work) instead of a bare sheet; zero dead ends = every tab in
sight / reachable on every width, the Payroll tab now says where the contract's dates
and wage are instead of "Not Employed / 0"; motion = the engine's card fade-in, tab
transitions, all off under reduced-motion; Lucide only; Payobook tokens only; phone
works (one card level, sideways tab and list scroll). Not done (out of scope, look
only): no new keyboard/bulk features.

## 3. Tests

Local copy of the ~150 MB template `upd_p6_t_tpl` upgraded to this tree (48 behind
modules `-u`; `pb_me_tax`, `pb_employee_form_tidy`, `pb_payroll_mapping_vn`,
`pb_contract_rules`, `pb_org_structure` installed so every page other modules inject
is present: Tax details, Payroll facts, Insurance (BH), Tax & Dependents, Employment
profile, Payroll Info, bank note…). Seed (DEMO only): companies VN/ID/IN/SG + the
template's US company; one employee + one running contract per Country of Work
(VN, ID, IN, SG, none); four logins: administrator, HR manager (+contract manager),
payroll manager, HR user; a **dummy "Company details" page** on both forms built
exactly like FS-1's native-view sync output (`//notebook` inside, page
`pbfs_company_details`, a titled group, two real `x_pbfs_demo_*` manual fields).

**The dump** (`fs6/tools/`: `cdp.mjs` drives headless Chrome over CDP, no
dependencies; `formdump.js` runs in the page): per login × record, every field
(name, visible, read-only, required, shown value), label, button (incl. the
smart-button "More" drawer and the status bar), section title, sub-list (row count),
alert/widget, and every tab — clicking each tab and dumping its body. "Visible" =
`checkVisibility()` + has a box, so a field hidden by CSS counts as gone.
4 logins × (5 employees + 5 contracts) = **40 dumps** per state.

| # | Test | Result |
|---|---|---|
| 1 | Baseline (opt-out, stock look) vs after (new look): `fs6/dump_diff_baseline_vs_after.txt` | **40 / 40 identical** in structure (every field, label, button, tab, visible / read-only / required). One VALUE differed in 10 contract dumps: "service days" 230 → 231 — the dumps ran either side of midnight (a day counter). Stability check: baseline repeated → identical. With the addendum fixes: see §4 (the only differences are the intended ones). Country-of-Work hiding from TIDY-E: identical per country (it is in the dump: VN 298 rows, ID/IN 276, SG 272, none 266 for the administrator, same after). Server side, `get_views` per role is byte-identical except the root class (test 02). |
| 2 | Create / edit / save / discard on both forms, through the screen | see §3.1 |
| 3 | Every tab opened without a console error | 40 dumps × every tab: **0 errors** (exceptions, console errors, log errors) before and after. Asset bundle compiles with 0 errors (checked after every restart — see gotcha FS6-2). |
| 4 | Phone width (390 px, emulated) | `after_09_employee_vn_phone.png`, `after_10_contract_vn_phone.png`: every tab reachable by sideways scroll (12 tabs, track 1,238 px in a 258 px box), inputs ~260 px wide (was ~110 px with the unfixed engine), contract components list scrolls (765 px table in a 224 px box). Desktop 1440 and 1024: 0 tabs outside the track (probe). |
| 5 | Screenshots before / after | `fs6/shots/before_*.png` / `after_*.png` (employee VN Work, Insurance (BH), no-country Company details as HR manager, contract VN, both on a phone) + `engine_unfixed_*` (the causes) + `fix_*` (§4) |
| 6 | Other native forms unchanged | see §3.2 |
| 7 | Touched suites = baseline | `pb_form_native_look` 6/6 pass; `pb_employee_form_tidy` 0 failures with and without the module; `biz_debrand` same 3 pre-existing failures with and without (database-manager page names the vendor site, scrub source text, demo sign-up mail template — none in this module). Baseline db `fs_6_bl` (no module) vs `fs_6_t`: 3 failed of 91 vs 3 failed of 95 (+4 = this module's tests then; 6 after the addendum). |
| 8 | No "Odoo" newly visible | grep of every new user-visible string (manifest name/summary/description, the note, two labels, vi/id msgstr): 0 (only the `<odoo>` XML root tags). PO gate (`PoFileReader`): vi_VN 3 rows, id_ID 3 rows, 0 empty, 0 brand word. |

### 3.1 Create / edit / save / discard (test 2)
Through the screen (headless Chrome, administrator, new look on, `fs6/tools/mk_crud_plan.py`),
each read back from the server:

| Case | Result |
|---|---|
| Employee: type a job title → Save | saved ("DEMO FS6 title" on the server), form not dirty, no invalid box, 0 console errors |
| Employee: change it → Discard | screen and server both keep the saved value |
| Employee: New → type a name → Save | created (`/hr.employee/5163`), name in the header card |
| Contract: wage 23,456 → Save | saved (23456 on the server) |
| Contract: wage 99,999 → Discard | screen shows 23,456.00, server 23456 |
| Contract: New → name, pick employee from the dropdown, wage → Save | created (`/hr.contract/2672`) |

Chatter: present and visible in all 40 dumps before and after (row `C`); status bar
buttons and state (contract), header buttons and the versions timeline (employee),
and the smart buttons incl. the "More" drawer are in the dump and identical.

### 3.2 Other native forms (test 6)
Five other engine forms — company, department, contact, user, time-off type — dumped
and photographed with the module installed, then the module UNINSTALLED and the same
again: dumps 5 / 5 identical; screenshots identical except one 52 × 52 px square at the
bottom right (the "Ask PayAI" button's pulse animation). The module's styles are all
behind `.pb-nl` and touch nothing else.

**Rollback proved:** after the uninstall the employee and contract pages were back in
the stock look (`vu=false`) and the administrator dumps equal the baseline, except
data my test 2 had just written (a résumé line and the record's link / star buttons on
the two records edited).

## 4. Coordinator addendum — three oddities on the employee page (pre-existing)

| # | What the screen showed | Cause | What I did |
|---|---|---|---|
| 1 | Payroll tab: "Contract: Not Employed", "Wage: 0" while the header shows the wage and "In Contract Since" | The Payroll tab is the platform's own "Contract Overview": `contract_date_start` / `contract_date_end` / `wage` of the employee's **version** record (`hr.version`, core `hr/views/hr_employee_views.xml` Payroll page). Payobook keeps contracts in `hr.contract` (FS_HOST_FACTS §F), so the version's contract boxes are always empty; the header ("In Contract Since", "Current contract salary") and Work tab "Current Contract" read `hr.contract`. | **Hid the misleading rows** (both labels and the two rows, which also hold the version's "new contract" button) and put one quiet line in their place: "The contract's dates and wage are kept on the contract itself: open it from Current Contract on the Work tab." The fields stay in the form (values load and save exactly as before — test 06); no stored value changed. Pointing the boxes at `hr.contract` would need new fields on the employee — not done. |
| 2 | "Tham gia BHXH" in Vietnamese on the English screen | The field's own label is Vietnamese (`pb_hr_payroll_formula/models/hr_employee.py:34`), and its vi translation is wrong too: "Tham gia bệnh" ("takes part in sickness", `pb_hr_payroll_formula/i18n/vi_VN.po:12182-12183`). | On this page: English label "Social insurance (BHXH)", vi "Tham gia BHXH", id "Asuransi sosial Vietnam (BHXH)" — from this module's view + .po, loaded on install into the view's stored translations. The FIELD's own label is untouched (other screens — Mapping cards, sheet headings — keep "Tham gia BHXH"; hand-made files matched by heading keep matching). Merge-time task for whoever owns pb_hr_payroll_formula: the field label + its vi msgstr (needs `.po` AND the stored value, i.e. a version raise with a migration or a `--i18n-overwrite` load). |
| 3 | "Employee Id" reads "Nhân viên" in Vietnamese | `om_hr_payroll/models/hr_employee.py:13` re-declares hr's `employee_id` on `hr.employee` as a text box "Employee Id"; the field row keeps hr's xmlid `hr.field_hr_employee__employee_id`, so hr's vi translation of "Employee" ("Nhân viên", core `hr/i18n/vi.po:2276`) is applied to it. | On this page: "Employee ID", vi "Mã nhân viên", id "ID karyawan". Field definition untouched. |

Before / after: `fs6/shots/fix_before_*.png` / `fix_after_*.png` (Payroll tab en + vi,
Payroll Info tab en, Work tab vi).

Dump with look + fixes vs baseline (`fs6/dump_diff_baseline_vs_after_with_fixes.txt`,
values ignored): **all 20 contract dumps identical; the 20 employee dumps differ ONLY
by the intended rows**:

| Change | Dumps |
|---|---|
| label "Employee Id" → "Employee ID" (Work tab) | 20 / 20 employee dumps |
| Payroll tab: label "Contract" + its box (`contract_date_start`), label "Wage" + its box, the version "new contract" button — gone | 10 (administrator + HR manager: the only roles that see the Payroll tab) |
| label "Tham gia BHXH" → "Social insurance (BHXH)" (Payroll Info) | 4 (the Vietnam employee, every role — the box is Vietnam-only since TIDY-E) |

(In this run the HR-user login's session dropped after 4 of its 10 records — "no
form"; its 10 records were re-run on their own and those are the ones compared. Both
summaries are in `fs6/`.)

## 5. Version raises / deploy notes (do NOT deploy from here — notes for the deployer)

- New module: `pb_form_native_look` 19.0.1.0.0 → `-i` on payobook, payobook_template,
  p0clone, rize, sudima (never abm). Dependencies all installed everywhere; check
  `state='installed'` first. It must be installed AFTER `pb_employee_form_tidy` is live
  (this branch contains TIDY-E; merge order tidy-e → fs-6).
- `pb_theme`: comment only — no `-u` needed for it.
- JS/SCSS: purge `/web/assets/%` per database, restart.
- Translations: a fresh `-i` loads vi/id. A LATER change to these msgstr needs a
  version raise + migration or an overwrite load (ledger LOOK rule).
- Look check after go-live: one employee per Country of Work + one contract, desktop and
  phone; the tab bar wraps (no tab cut off); Payroll tab shows the blue line instead of
  Contract / Wage.
- Kill switches if anything looks wrong: uninstall the module (full rollback) or the
  existing engine switch `pb_theme.vu_form_engine = off` (all forms).

## 6. Merge-time notes / risks

- FS-2 / FS-3 "Company details" native page: rendered as a normal tab + carded section
  (dummy page proved it, `after_05_…companydetails.png`, incl. for an HR manager). No
  dependency either way.
- The engine bug C4 (sub-list `overflow: hidden`) affects EVERY engine form, not only
  these two; I fixed it only inside my scope. Suggested one-line engine change for the
  `biz_theme` owner: in `vu_form_engine.scss:768` `overflow: hidden` → `overflow-x: auto`
  (check five forms with sub-lists after).
- C1 (tab track never wraps) likewise affects any engine form with many tabs; same
  suggestion (`vu_form_engine.scss:715-724`: `flex-wrap: wrap` on wide screens).
- The view `employee_form_fixes.xml` anchors on `//page[@name='payroll_information']`
  (core hr), `//field[@name='tham_gia_bhxh']`, and `parent_id`'s following
  `employee_id` (om_hr_payroll) — if any of those moves, the install fails loudly
  (no silent miss).

## 7. Gotchas (for the ledger)

- FS6-1: libsass (the asset compiler) cannot do `clamp(20px, 1.6vw + 8px, 28px)` —
  "Incompatible units: 'px' and 'vw'" — and drops the WHOLE backend style bundle (every
  screen unstyled, "A css error occured, using an old style"), while the browser
  console shows nothing. Put such values in a custom property with `calc()` inside.
  After any SCSS change grep the server log for `assetsbundle: Error`.
- FS6-2: the `class` of a `<form>` arch is on `.o_form_view`, not `.o_form_renderer` —
  scope as `.o_form_view.<class> .o_form_renderer.vu-form`.
- FS6-3: headless Chrome over CDP needs no library on this Mac: Node 24 has a global
  `WebSocket` + `fetch` (`fs6/tools/cdp.mjs`); `*.localhost` resolves, so each builder
  can use its own host name and its own profile folder (no shared cookies).
- FS6-4: the worktree guard refuses shell lines that mention "eval" (even a mode name
  in arguments) — name such modes something else.
- FS6-5: hr.employee's `employee_id` is core hr's field re-declared as text by
  om_hr_payroll; the field row keeps hr's xmlid, so hr's translations of "Employee"
  land on "Employee Id". Fix labels of re-declared fields on the view, not the field.
- FS6-6: the "Tham gia BHXH" vi msgstr in pb_hr_payroll_formula is wrong ("Tham gia
  bệnh"); left for that module's owner (§4).

Local databases `fs_6_base`, `fs_6_t`, `fs_6_bl` and their file folders were dropped
at the end.

## 8. Owner questions (plain)

1. On the Payroll tab the boxes "Contract Type" and "Pay Category" also come from the
   same empty record as the old Contract / Wage rows (Pay Category says "Employee" for
   everybody). Do you want those two hidden too, so the Payroll tab only shows what is
   really used (Employee Type, Trial period, Working Hours)?
2. "Tham gia BHXH" is still the box's name on the Mapping screen and in the Updates
   sheets (only this page now says "Social insurance (BHXH)"). Should it be renamed
   everywhere? Files your clients made by hand with the old heading would then need
   the column picked once.
3. Some tab names on the employee page still show in English on the Vietnamese
   screen ("Employment profile", "Payroll facts"). Do you want those translated in a
   small follow-up?
