# FORM STUDIO follow-up 1 — Learn lesson, Payroll tab tidy, tab names; R18, R19, R22 — go-live report

Builder + deployer, 2026-11-19/20 (UTC). Branch `fs-followup-1` from `origin/19.1` @ `94e65d35b`;
deployed commit **`48a80cb14`** (pushed). Method and rules: `FS_DEPLOY_HANDOVER.md` (main checkout)
unchanged; scripts `/tmp/fu1_*.sh` on the server (copies in the agent scratchpad `fsf1/srv/`).

**Result: LIVE on all five databases** (payobook, payobook_template, p0clone, rize, sudima), ONE
go-live, **387 s down** (01:22:06–01:28:33 UTC, 2026-11-20). Deploy notes START 22:59, NOTE 00:14 (R22
added), DONE 01:33 UTC. Nothing held back. abm, pbf_preview, recruit_connect untouched; no Codex module
touched (Codex shipped `pb_employee_vault` / `pb_settings` at 00:03–00:12 — no overlap; merged into
this branch before the push). Rize "Fill Country of Work" NOT pressed (R20).

## 0. Scope as delivered
| # | Item | Where | State |
|---|---|---|---|
| 1 | Learn lesson L42 "Add your own fields" (held back at the go-live) | `pb_learn` 19.0.20.8.9, `pb_form_studio_reach`, `pb_payroll_ai_insights` 19.0.3.13.1, authoring source `docs/tutorial_poc/author/` | LIVE ×5 |
| 2 | Full details › Payroll tab: hide "Contract Type" and "Pay Category" | `pb_employee_form_tidy` 19.0.1.2.0 | LIVE ×5 |
| 3 | Tab names "Employment profile" / "Payroll facts" in vi + id | `pb_employee_form_tidy` 19.0.1.2.0 | LIVE ×5 |
| R18 | Custom fields for every company on employee AND contract screens | `pb_form_studio` 19.0.1.2.0 (engine + migration) | LIVE ×5 |
| R19 | Six more standard boxes may be ticked for My Payobook (nothing ticked) | `pb_form_studio` (writes-through), `pb_form_studio_people` | LIVE ×5 (nothing ticked) |
| R20 | Rize's people with no Country of Work: private list only | `outputs/rize-country-of-work-2026-11-20/` (never committed) | done, 3 people, Fill NOT pressed |
| R22 | "Form builder" button on Full details and the full contract form | `pb_form_studio_people` 19.0.1.2.0, `pb_form_studio_contracts` 19.0.1.1.0 | LIVE ×5 |

R18/R19 were built by a sub-builder on `fs-followup-1b` (report `FS_FOLLOWUP1B_REPORT.md`, same folder)
and R22 on `fs-followup-1c` (`FS_FOLLOWUP1C_REPORT.md`); both fast-forwarded into `fs-followup-1`
and shipped in the SAME go-live (one downtime) after their own suites and a rehearsal passed.

## 1. Item 1 — why Learn's own checks failed, and the fixes
The go-live's seven Learn failures (FS_DEPLOY_REPORT §2) were all real, all the lesson's wiring:

| Learn check | Cause | Fix |
|---|---|---|
| `test_refresh_paths.test_02` (every station 5–10 steps) | L42 had 3 steps | 5 steps: title line, the four numbers, record-type chips + Search fields, one row (Used by, countries), the "cannot take custom fields" line |
| (not a test, the real gap) a lesson runs over the PRACTICE COPY (`engine/screens.js`, `shellHTML`) | no practice copy of the Field library: the lesson drew an empty page | `screens.js formbuilder()` + `PRACTICE.formbuilder` (4 DEMO-style fields: Uniform size, Locker number, Site days used by 1, Parking bay on the contract) + Settings › System › "Form builder" card in the practice menu |
| `test_coach.test_14` (Coach cannot detect `formbuilder`) | screen had no leaf, place or tag | `gen_learn_data.py SCREEN_ACTION_TAGS['formbuilder'] = 'pb_form_library'` |
| `test_refresh_paths.test_05` (Ask whitelist) | PayAI's `_KNOWN_LESSONS` lacked L42 | `pb_payroll_ai_insights/models/payroll_ai_engine.py`: whitelist + lesson list + match rule + one Settings › Form builder line |
| `test_anchor_registry.test_01` (anchors "not in" learn_anchors.xml) | the lint only read literal `data-coach="…"`; the reach module lays anchors with a t-inherit `<attribute name="data-coach">` — the ledger's required from-outside way | **check was incomplete, not wrong-headed**: `emits()` and the stray scan (test_05) also read the t-inherit attribute form; same in `check_contract.py` (`INHERITED_ANCHOR_RE`). Anchors `fb-filters` and `fb-foot` added; `contract.json` item `formbuilder-lesson-anchors` pins the five attributes, the template classes and the quoted words |
| `test_learnrev_lesson_door.test_01` (content screens 56) | a new screen | pin moved to 57 with a comment (the screen has its own station; the exception list is unchanged) |
| `test_learnrev_p3.test_h` / `p5.test_h` (library node suite: 43 stations) | a new station | node pin moved to 44 (same as the ORG CHART precedent) |

Generator: `gen_learn_data.py` writes clean, `--check` clean; **`pb_learn/i18n/vi_VN.po` unchanged**
(md5 before = after; the generator now merges). `test_step_shape.py` 0 failed. `check_contract.py`:
2 failures, both known (`c1-cockpit-anchors` pe-filters, `govt-reports-coming-soon-is-an-install`).
Also found: `origin/19.1` carried L42 in `data.js` while `learn_content.json` did not (the hold-back
reverted only the generated file) — `--check` was red on 19.1; now consistent.

## 2. Item 2 — Payroll tab
`pb_employee_form_tidy/models/form_rules.py`: `contract_type_id` and `structure_type_id` are `REMOVE`
(screen only — the same mechanism as the 31 TIDY-E boxes); the committed verdict table follows.
Each box occurs once in the combined form (Payroll tab only), so nothing else moves. Fields, values and
readers untouched.

## 3. Item 3 — tab names
`hr_employee._pb_tidy_tab_names` (called from the existing `_get_view`): a page still carrying the
English words "Employment profile" / "Payroll facts" gets this module's words — vi "Hồ sơ việc làm" /
"Dữ kiện tính lương", id "Profil kepegawaian" / "Data penggajian" (`.po` code terms with the three
markers). Why not an xpath view: "Payroll facts" belongs to `pb_payroll_mapping_vn`, installed on rize
only, so a view would fail to install elsewhere; the owners' modules are shipped by other streams.
**"A translation fix is two fixes"**: here there is no stored copy to fix — these words are code
terms read from the module's `.po` at run time; checked on every live database through the same
view-render call (§6). An owner translation, if one is ever added, wins (the English words are then
gone). "Tham gia BHXH" untouched. Not in scope, seen: under Indonesian, "Payroll Info", "Insurance (BH)"
and "Tax & Dependents" tabs are English too; the contract form's "Payroll facts" page (rize) likewise.

## 4. Tests (local, scoped)
- `fsf1_*` databases = `upd_p6_t_tpl` brought to the branch tree (-u of every stale custom module,
  -i of the Form builder modules). All local databases dropped at the end.
- Final combined run (`-u` of the shipped modules; tags `/pb_form_studio,/pb_form_studio_people,
  /pb_form_studio_contracts,/pb_form_studio_lists,/pb_form_studio_reach,/pb_form_native_look,
  /pb_employee_form_tidy,/pb_learn,/pb_payroll_ai_insights`): **700 tests, 5 failed + 1 error = the
  known set**: Learn baseline 5 (stray anchors list of other modules, composer 03b, guide truth 02 /
  02b, learnrev p4 c1 — "Tax returns" column) and PayAI `test_egress.test_04e` (the voice consent card
  the owner removed, ruling 2026-10-15). The seven L42 failures are gone.
- `pb_employee_form_tidy` 48/48 incl. new `tests/test_followup1.py`: F1 both boxes hidden for VN, ID,
  IN, SG and no country, still in the form, visible before; F1b a save keeps their values; F2 tab names
  vi/id on the real form; F2b both names on a drawn form, English unchanged. `pb_form_native_look` 8/8.
- R18/R19 (sub-builder): 93 baseline → 112, 0 failed. R22 (sub-builder): 118 → 126, 0 failed.
- Browser (local, administrator): the lesson opens from its deep link, "Step 1 of 5" … "Step 5 of 5",
  each step spotlights its anchor on the practice copy (breadcrumb Settings › System › Form builder);
  the real Field library carries `fb-head`, `fb-kpis`, `fb-foot` (and `fb-filters`, `fb-table` once a
  field exists); console clean.

## 5. Before anything, rehearsals
- Deploy notes: no open START from another deployer. Server manifests of the 7 modules = `origin/19.1`
  (live trees hashed = the `git archive` of 19.1); nothing newer on the server. vi/id active ×5;
  `pb_payroll_mapping_vn` on rize only.
- Backups ×5 (dumps read back + file folders + previous trees): first at 22:59 UTC
  (`/odoo/backups/fsfu1-20261119T225914Z/`), re-taken at 00:14 after R22 joined
  (`/odoo/backups/fsfu1-20261120T001417Z/`).
- **Hidden rize copy** (jobs + mail off, dropped): upgrade 76 s, 0 ERROR; data identical except
  messages +4 (empty upgrade notes on 2 jobs + 2 server actions); **runs 2113 SG, 2114 ID, 2115 IN, 2116
  VN: 211 payslips / 6,914 lines old vs new, 31 computed, 180 refused identically, 0 differing**; the
  two boxes shown 2 → 0 for VN/ID/IN/SG/no country with the stored values' checksum unchanged; tab
  names vi/id; lesson 5 steps / 44 stations; R18 "nothing to fold". Repeated with R22 (80 s, same).
- **Hidden payobook copy** (four companies, the two DEMO fields): upgrade 87 s, data identical, R18
  "2 layouts for 2 screens, nothing to fold", same probe results.

## 6. Go live ×5 and verification
- Quiet check: rize had signed-in activity until 01:05 (six tries from 00:20, one every 10 min; part
  of it my own look at payobook.com at 00:31 before the go-live — avoid that next time); stop 01:22:06.
- `rsync` 7 trees (scoped `--delete`), per database (template, p0clone, sudima, rize, payobook)
  `-u pb_employee_form_tidy,pb_form_studio,pb_form_studio_contracts,pb_form_studio_people,
  pb_form_studio_reach,pb_learn,pb_payroll_ai_insights`: 72 / 67 / 67 / 71 / 82 s, all EXIT 0, 0 ERROR;
  asset purge + signal + `web.assets.version = fsfu1-20261120T001417Z`. Start 01:28:33; sites 200.

| Module | Before | After |
|---|---|---|
| pb_employee_form_tidy | 19.0.1.1.0 | 19.0.1.2.0 |
| pb_form_studio | 19.0.1.1.0 | 19.0.1.2.0 (R18 end-migration: nothing to fold ×5) |
| pb_form_studio_contracts | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_form_studio_people | 19.0.1.0.0 | 19.0.1.2.0 |
| pb_form_studio_reach | 19.0.1.0.0 | 19.0.1.1.0 |
| pb_learn | 19.0.20.8.8 | 19.0.20.8.9 |
| pb_payroll_ai_insights | 19.0.3.13.0 | 19.0.3.13.1 |

**Verification:** 7 trees = commit; manifest = `latest_version` on all 35 rows; jobs = snapshot ×5
(111/58, 99/40, 99/48, 99/91, 100/91), none re-activated, payobook job 156 OFF, no new job; data
before = after ×5 except rize messages +4 (as rehearsed); server log since the stop 0 ERROR,
0 Traceback, 0 asset errors; one service process.

**Live probes ×5** (view-render as the administrator, read-only, rolled back; counts only):

| Site | Contract Type / Pay Category shown (per Country of Work present) | stored values | "Employment profile" vi / id | "Payroll facts" vi / id | Lesson | R19 ticks | R22 button (admin / HR manager not admin) |
|---|---|---|---|---|---|---|---|
| payobook | VN 0 | 20 / 8,706 set, checksum unchanged | Hồ sơ việc làm / Profil kepegawaian | not installed | 5 steps, 44 stations | 0 | yes / **no** |
| payobook_template | none 0 | 0 / 3 | same | not installed | same | 0 | yes / (no such user) |
| p0clone | none 0 | 0 / 23 | same | not installed | same | 0 | yes / (no such user) |
| rize | VN, ID, IN, SG, none: 0 each | 0 / 328, checksum unchanged | same | Dữ kiện tính lương / Data penggajian | same | 0 | yes / (no such user) |
| sudima | VN 0 | 0 / 653 | same | not installed | same | 0 | the platform user there is not an administrator → no; HR manager → **no** |

**payobook.com in the browser** (administrator session, nothing saved): employee Full details — tabs
listed, Payroll tab has Employee Type and Working Hours but no Contract Type / Pay Category; "Form
builder" button in the top bar opens the Form builder over the page ("No changes yet"), closed. Full
contract form of a contract in the SECOND company (R18): "Company details" tab shows "DEMO Parking bay"
(layout made in another company); the panel's own call for that contract with only the second company
also returns the field; "Form builder" button opens the contract Form builder, closed without changes.
Field library: 2 rows, all five lesson anchors present. Lesson L42 opens at "Step 1 of 5" with all
five anchors on its practice copy. Console: no errors. **Not done in a browser:** the button's absence
for an HR manager who is not an administrator (no such login used; proved by the server gate above and
the sub-builder's local walk); Vietnamese/Indonesian tab names seen through the server's view-render,
not a browser in those languages.

## 7. R18 / R19 / R20 / R22 summary (plain words; details in the 1b / 1c reports)
- R18: a custom field now shows in every company on both the employee and the contract screens (one
  screen design for the whole site). Country of Work limits and "who can see it" are unchanged. On
  payobook.com the two DEMO fields now show in all four demo companies.
- R19: six more boxes can be ticked for My Payobook — Spouse Legal Name, Spouse Birthdate, Home-Work
  Distance and its unit, Blood type, Religion (default "HR approves"). Nothing is ticked anywhere.
  Address and emergency contact stay closed: My details already changes those same boxes, so opening
  them would give two ways to change one box (the owner's own condition). Full table in
  `FS_FOLLOWUP1B_REPORT.md` §2.
- R20: Rize has 3 active people with no Country of Work; private list (name, number, company,
  department, contract yes/no, login yes/no) at
  `/Users/adity/Documents/GitHub/gitlocal/outputs/rize-country-of-work-2026-11-20/rize_no_country_of_work.xlsx`
  (never committed). Nothing pressed.
- R22: "Form builder" button on Full details and the full contract form, administrators only; after
  Publish the page redraws by itself (can take a few seconds).

## 7b. Owner questions (plain words)
1. Spouse name and birthday can now be offered on My Payobook, but My details › Family already lets an
   employee add a husband or wife. Do you want both, or only Family?
2. Blood type and religion are sensitive (they never reach a payslip). Fine to offer them for ticking?
3. Indonesian readers still see "Payroll Info", "Insurance (BH)" and "Tax & Dependents" in English on
   Full details, and the contract form's "Payroll facts" tab on Rize is English in both languages.
   Translate those too?

## 8. Gotchas → ledger
- FU1-1 A lesson runs over the PRACTICE COPY, never the real screen: a new station needs a replica
  (`screens.js`), practice data and a place in the practice menu, or its spotlight lands on nothing —
  the anchor lint alone does not catch it.
- FU1-2 The anchor lint and `check_contract.py` now accept `<attribute name="data-coach">x</attribute>`
  (bridge modules laying anchors from outside); a literal-only grep misses them.
- FU1-3 The hold-back reverted only the generated `learn_content.json`, leaving `data.js` ahead:
  `gen_learn_data.py --check` was red on 19.1. Hold back the authoring source too.
- FU1-4 A tab label owned by a module not installed everywhere: rename/translate it in `_get_view`
  (code terms), never with an xpath view.
- FU1-5 `test -f` on a root-only evidence folder from the ubuntu login is always false: poll with sudo.
- FU1-6 Layouts are ONE per screen for the whole site since R18; FSD-4 is obsolete.
- FU1-7 Do not open payobook.com or rize in a browser while waiting for the quiet window: your own
  requests count as signed-in activity.

(The main-checkout `FORMSTUDIO_LEDGER.md` could not be edited from this isolated worktree: please
copy FU1-1..7 into its Gotchas and add a phase row "FU1 — LIVE x5 2026-11-20".)
