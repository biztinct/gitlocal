# FS-10 — Form builder fix batch: R27 labels on My Payobook, phone width, lesson wording, locked-list gap

**Status: BUILT, NOT LIVE.** Branch `fs-10` from `origin/19.1` @ `e69bebcc4` (FS-7 live). No deploy, no
server touched. Go-live is batched later on the owner's word.

Read: `FORMSTUDIO_LEDGER.md` (R1–R28), `FS7_HANDOVER.md`, `FS_DEPLOY_HANDOVER.md` (non-negotiables);
`FS7_REPORT.md`, `FS_FOLLOWUP1_REPORT.md`, `FS_DEPLOY_REPORT.md` gotchas.

## 0. Go-live module list (exact)

| Module | Version | Why |
|---|---|---|
| `pb_form_studio` | 19.0.1.3.0 → **19.0.1.4.0** | R27 label on the My Payobook field list; phone sheet / pinned bar (JS, XML, SCSS); `_pbfs_std_unhide_locked`; 2 msgids (vi/id) |
| `pb_form_studio_people` | 19.0.1.3.0 → **19.0.1.4.0** | locked list = formula catalogue (`_pbfs_people_pay_reads`); upgrade step `migrations/19.0.1.4.0/end-fs10_unhide_formula_read.py` |
| `pb_form_studio_contracts` | 19.0.1.2.0 → **19.0.1.3.0** | same rule on the contract; upgrade step `migrations/19.0.1.3.0/end-fs10_unhide_formula_read.py` |
| `pb_form_studio_reach` | 19.0.1.1.0 → **19.0.1.2.0** | R27 in the "field withdrawn" note; new tests |
| `pb_learn` | 19.0.20.8.9 → **19.0.20.8.10** | lesson L42 wording + practice copy (static assets: purge `/web/assets/%` + restart) |

`-u` order: `pb_form_studio, pb_form_studio_people, pb_form_studio_contracts, pb_form_studio_reach,
pb_learn` (one command is fine). `pb_form_studio_lists` unchanged. JS/SCSS changed → asset purge per
database. Not edited: `pb_me_portal`, `pb_me_details`, `pb_lifecycle/`, `pb_pack_*`, any standard addon,
`pb_explorer` (FS-8), `pb_employee_form_tidy` / side-panel bank files (FS-9). No file shared with
`fs-8` / `fs-9`.

## 1. Item 4 — "Place of Birth" says a pay formula reads it, yet could be hidden

### Why (verified facts, file:line at `e69bebcc4`)
| # | Fact | Where |
|---|---|---|
| F1 | The My Payobook lock ("A pay formula reads it, so only HR changes it.") uses the formula **catalogue**: every field a formula can be bound to | `pb_form_studio_people/models/form_studio.py:177-202` (`_pbfs_people_formula_names`), used at :258 |
| F2 | The hide lock used only **live bindings** (`employee.<field>` keys of this database) — FS-7 deviation 4 | `pb_form_studio_people/models/standard_fields.py` `_pbfs_people_formula_used` (before) |
| F3 | So a catalogue field nobody had bound yet (Place of Birth on every database) carried the note AND could be hidden. Same split on the contract: `CONTRACT_FIELDS` partly locked by hand, Location / Cost center / Signed on left free | `pb_hr_payroll_formula/models/application_domain_sources.py:19-48`; `pb_form_studio_contracts/models/standard_fields.py:16-24` (before) |
| F4 | Second, smaller gap: a formula bound through a tax source (`tax.in_pan_number` …, `pb_me_tax`) was not seen by the live check (only `employee.%` keys) | `pb_me_tax/models/formula_sources.py:34-45` |

### Fix (general, not just this field)
* `_pbfs_people_pay_reads()` — ONE answer: catalogue (F1) + live `employee.*` / related / **`tax.*`**
  bindings + pay data file targets. The hide lock uses it; the My Payobook lock already used the
  catalogue, so the two can no longer disagree (test L2 checks every field).
* Contract: `_pbfs_contract_formula_used()` adds `CONTRACT_FIELDS` (same rule).
* Renaming stays allowed (R23). Blood type / Religion stay free (payroll never reads them,
  `PAYROLL_EXCLUDED_FIELDS`).
* Upgrade step (both hosts): a hide rule saved on a now-locked field is cleared, own label kept, one
  history line each, count in the log. The screens already ignored such rules (FS-7: a locked field is
  never hidden), so nothing on screen moves. **Expected on every live database: 0** (FS-7 went live
  today under an owner hold; nobody has hidden a field). Local proof: 3 seeded → 3 cleared, then 0.
* Direct call refused (browser walk): `update_standard('hr.employee','place_of_birth',{std_hidden:true})`
  → "A pay formula reads it, so pay depends on this field. It cannot be hidden."

### Every field whose status changes (local copy of the live state; same code on every database)
Employee: 82 → **102 locked** of 148 (66 → 46 hideable). Contract: 29 → **32 locked** of 34.

| Record | Field (as on screen) | Tab | Field code |
|---|---|---|---|
| Employee | Certificate Level | Personal | `certificate` |
| Employee | Contact (emergency) | Personal | `emergency_contact` |
| Employee | Phone (emergency) | Personal | `emergency_phone` |
| Employee | Email (private) | Personal | `private_email` |
| Employee | Phone (private) | Personal | `private_phone` |
| Employee | Field of Study | Personal | `study_field` |
| Employee | Place of Birth | Personal | `place_of_birth` |
| Employee | Work Phone | Top of the page | `work_phone` |
| Employee | Indonesia family card number | Employment profile | `pb_family_card_number` |
| Employee | Job level | Employment profile | `pb_job_level` |
| Employee | Legal given name / Legal family name | Employment profile | `pb_legal_first_name`, `pb_legal_last_name` |
| Employee | Permanent address | Employment profile | `pb_permanent_address` |
| Employee | Visa status | Employment profile | `pb_visa_status` |
| Employee | Emergency contact name / phone, Relationship | Side panel: Personal | `vietnam_emergency_contact_*` (3) |
| Employee | School | Side panel: Personal | `study_school` |
| Employee | Temporary address | Side panel: Personal | `vietnam_temporary_address` |
| Employee | Work permit number | Side panel: Personal | `vietnam_work_permit_number` |
| Contract | Location | Salary Information | `location` |
| Contract | Cost center | Salary Information | `costcenter` |
| Contract | Contract signed on | Below the tabs | `pb_signed_date` |

Reason shown for all of them: "A pay formula reads it, so pay depends on this field." Still free on the
contract: HR Responsible, Notes (R28 said five — see owner question 1).

## 2. Item 1 — R27: My Payobook shows the administrator's label

* Engine `_pbfs_portal_fields` (`pb_form_studio/models/form_studio.py`, the ONE list every My Payobook
  surface of the Form builder reads): a renamed standard field carries the own label in the reader's
  language; no label in that language → built-in; Reset → built-in again.
* Reaches: My details › **Company details** card, **Change company details** form, the waiting change
  (**My requests** title and the approver's rows — `portal_request.py` reads the same list), and the
  "no longer takes changes to …" note (`portal_request.py` `PbFormFieldMetaPortalWatch.write`).
* Hint under the label boxes now says: "Mapping, Updates sheets and pay data files keep the built-in
  name. My Payobook shows your label for the fields you show there." (overlay + Field library; vi/id).
* Browser (390 px, employee login): renamed Place of Birth → "DEMO Born in" (en), "DEMO Sinh tại" (vi):
  card read "DEMO Born in" in English and "DEMO Sinh tại" on `/vi/my/details`; after Reset "Place of
  Birth"; console clean.

### STOPPED part (needs a hook — owner/architect question 2)
My Payobook also shows some standard fields on pages the Form builder does not draw, with the words
written into their templates and no hook that can carry a label:
* `pb_me_portal` **My Profile** (`views/portal_templates.xml` `portal_my_profile`, the `pbme-kv` rows
  and the change form): Work Email, Work Phone, Private Phone, Private Email, Address, Emergency
  Contact, Emergency Phone. `_profile_card` (controllers/portal.py:174) carries values only.
* `pb_me_details` **My details** card: "Marital status" (`views/portal_templates.xml:102`).

Smallest hook (not built): `_profile_card` returns `'labels': {}` (1 line), and each of those `<span>`s
becomes `<span t-out="profile['labels'].get('work_email')">Work Email</span>` (QWeb shows the body when
the value is empty, so nothing changes and the existing translations stay until a label is filled);
same for `person['labels']` in `pb_me_details._pbmd_overview`. `pb_form_studio_reach` would then fill
`labels` from `_pbfs_std_rules('hr.employee')` in its existing controller subclass. An xpath from
outside was rejected: it must locate those rows by position (no names on them), so an edit to the
template would either break the upgrade of `pb_me_portal` or put a label on the wrong row.

## 3. Item 2 — Form builder at phone width (≈390 px)

* One-column layout (≤ 1100 px, the stylesheet's existing breakpoint): tapping a field (screen tile,
  Standard fields list, Add existing, a new type) opens its settings as a **sheet at the bottom of the
  screen** (max 72 % of the height, its own scroll, grab handle, **Done**). Nothing picked → no empty
  panel at the bottom of the page.
* The studio bar (**Publish**, **Discard**, **close**) is **pinned at the top** of the overlay; the
  left column's sticky filter sits just under it (height measured by the overlay, the bar may wrap).
  ≤ 760 px: one line — Discard is icon-only (name kept for screen readers / hover), the "n changes"
  text shortens with "…".
* The page can still be scrolled clear of the sheet (bottom padding while it is open).
* Desktop unchanged: the new head row is `display: contents` and Done is hidden above 1100 px
  (desktop walk: same three columns, same panel).
* Walk at 390×844: Standard fields → Religion: sheet top 236 px, bar 0–53 px, filter at 53 px; pick
  "Hidden for everyone" in the sheet → "1 change…", Done, Publish reachable (top 8 px) → publish
  sheet lists "Religion: hidden for everyone"; New field → Text: sheet opens on "Custom field";
  scrolled to the very bottom the close button is still at top 11 px; page width 390 (no sideways
  scroll); Field library 390 wide, its Edit sheet fits (16–828 px); console: only 404s for app icons
  of modules not installed (pre-existing).
* Escape does not reach the overlay's window listener on this build (something above stops it; the
  same is true of the existing Escape on the publish sheet) — Done is the way out. Not changed.

## 4. Item 3 — lesson "Add your own fields" (L42)

* Wording no longer quotes numbers or fields the demo does not have. Step 2 names the six numbers
  without values ("yours will differ; grey = zero"); step 3 names the real filter bar (Find a field,
  All / Own fields / Standard fields / Hidden / On My Payobook, record types, Any Country of Work) and
  uses DEMO Parking bay / DEMO Shirt size; step 4 uses the DEMO Shirt size row and explains the lock on
  standard fields; the quiz asks about "one of your own fields". Still 5 steps.
* Practice copy caught up with the screen FS-7 changed (`pb_learn/static/src/engine/screens.js`
  `formbuilder()`, `practice-data.js` → `fixture.js`): title line, six numbers, one filter bar, own rows
  (DEMO Shirt size, DEMO Parking bay — the payobook demo's kept fields) then three standard rows (two
  locked).
* `contract.json` pin `formbuilder-lesson-anchors` was already red on 19.1 (FS-7 renamed "Search
  fields" and a class) — fixed to the current words + the new ones the lesson quotes.
  `check_contract.py`: 2 failures left, both known since FU1 (`c1-cockpit-anchors`,
  `govt-reports-coming-soon-is-an-install`).
* `gen_learn_data.py` written + `--check` clean; jargon lint clean (one long sentence split);
  `test_step_shape.py` 0 failed; **`pb_learn/i18n/vi_VN.po` unchanged** (md5 before = after).
* Browser (390 px): Help › Form builder › Full lesson · 5 min → all five anchors present, steps 1–5
  and the understanding check reached; console clean.

## 5. Tests

### Numbered (new)
| # | Case | Where | Result |
|---|---|---|---|
| L1 | Place of Birth locked with the pay reason; hide refused by direct call (all / by country) and by Publish; rename allowed; value untouched | `pb_form_studio_people/tests/test_fs10_locked.py` | PASS |
| L2 | No field says "a pay formula reads it" on My Payobook yet can be hidden; every catalogue field on screen is locked | same | PASS |
| L3 | A formula bound through `tax.*` locks its employee field | same | PASS |
| L4 | Upgrade step: clears the hide of a now-locked field, keeps its label, one history line, leaves free fields alone, second run nothing | same | PASS |
| L5 | Blood type / Religion stay hideable | same | PASS |
| C4c | Contract: every catalogue field locked (Location, Cost center, Signed on included), renamable; HR Responsible / Notes free | `pb_form_studio_contracts/tests/test_fs7_standard.py` | PASS |
| R1/R4 | Own label on the Company details card and the change form; Reset → built-in (HTTP, portal login) | `pb_form_studio_reach/tests/test_fs10_r27.py` | PASS |
| R2 | Reader's language: vi typed → vi; id not typed → built-in; request label in vi | same | PASS |
| R3 | Waiting change named by the own label (My requests title, approver rows) | same | PASS |
| R5 | Silent: nothing renamed → built-in labels | same | PASS |
| R6 | Custom field label unchanged | same | PASS |
| P | **Three payslips** (two schemes, two people; one formula bound to Place of Birth) recomputed **identical** after hiding 5 free standard fields, renaming 5, and after the upgrade step on both record types | same | PASS |
FS-7 tests moved off fields that are locked now: test 2 / 4b / 12 use Visa No instead of Job level;
test 5 picks the first still-free one-country box (Safety training group / Internal Committee member)
instead of the Indonesian family card.

### Silent upgrade (local copy, old code → new code, `snap.py` before/after)
Seeded with the OLD code first: Blood type hidden, Place of Birth hidden, School hidden for Vietnam,
Department renamed "DEMO Team", Work Mobile ticked for My Payobook, contract Location hidden.
After `-u`: employee + contract forms (en, vi), side panel, People table columns, My Payobook field list
and the rules compared:
* identical: table columns, My Payobook list, Blood type still hidden, "DEMO Team" label kept, Work
  Mobile tick kept;
* changed ONLY where intended: Place of Birth (form + its label + side panel) and contract Location
  shown again, School's Vietnam rule cleared — the three rules the upgrade step cleared (log:
  employee 2, contract 1).
Nothing was hidden, renamed or ticked by the upgrade itself.

### 5b. Suites (`--test-tags` of the six touched modules, fresh copy of the live-state database)
Baseline on `origin/19.1` (pristine export of the tree, same database copy, same tags):
**560 tests, 4 failed, 1 error — all `pb_learn`**: `test_anchor_registry.test_05`,
`test_composer.test_03b` (error), `test_guide_truth.test_02`, `test_02b` (govreports replica "Tax
returns"), `test_learnrev_p4.test_c1`. Stats: engine 41, contracts 30, lists 13, people 33, reach 51,
Learn 494.

Branch `fs-10` (fresh copy, `-u` of the six): **572 tests, 4 failed, 1 error — the same five `pb_learn`
tests, same messages (none about the Form builder lesson)**. Stats: engine 41, contracts 31, lists 13,
people 40, reach 61, Learn 494. **Form builder suites: 0 failed.** Failure set = baseline.
Learn's own tools: `gen_learn_data.py --check` clean, `test_step_shape.py` 0 failed,
`check_contract.py` 2 known failures (was 3 on 19.1 — the Form builder pin is fixed).
White-label: no "Odoo" in any new string, template or .po msgstr (engine / people PO tests pass);
no "Payobook" in a `biz_*` module (none touched).

## 6. Gotchas (ledger rows)
* FS10-1 The scratchpad path holds "git" and the worktree guard refuses compound shell lines with it
  (FSD-6 again) — even `mkdir && psql`; keep every step its own command or a script file.
* FS10-2 Two answers to one question: the My Payobook lock and the hide lock each worked out "does a
  pay formula read it" their own way. One helper per question; a test that walks every field and
  compares the two notes.
* FS10-3 An upgrade step that calls `_pbfs_standard_locked` reads the forms (required-on-form check),
  which makes the registry print its "inconsistent compute" UserWarnings with stacks in the log (only
  warnings, 0 ERROR). Expect them in the go-live log; they are not failures.
* FS10-4 On a phone the overlay itself scrolls, so anything `position: sticky; top: 0` inside it
  (the left filter) slides under a sticky studio bar — offset by the bar's measured height.
* FS10-5 Escape keydown never reaches a `window` listener inside the Form builder overlay on this
  build (stopped upstream); do not rely on Escape for a phone control.

## 7. Owner questions (plain words)
1. **Contract boxes you can hide:** with the rule "a pay formula can read it, so it cannot be hidden",
   Location, Cost center and Contract signed on can no longer be hidden (they can still be renamed).
   That leaves two (HR Responsible, Notes) instead of the five you accepted. Keep it strict, or keep
   those three hideable on contracts?
2. **My Profile page and "Marital status":** your own label now shows on My details › Company details
   and in the change requests. The My Profile page (work email, phones, address, emergency contact) and
   the "Marital status" line still show the built-in names, because those pages have their words
   written in. Making them follow needs a small change inside those two pages (about ten lines, no
   look change). Shall we make it?
3. **Employee boxes now locked:** 20 more boxes (list in §1, e.g. Work Phone, private email and
   phone, emergency contact, Place of Birth, School) can only be renamed, not hidden, because a pay
   formula can read them. Is that what you want, or only when a formula really uses them?
