# FS-10 — Form builder fix batch: R27 labels on My Payobook, phone width, lesson wording, locked-list gap

**Status: BUILT, NOT LIVE.** Branch `fs-10` from `origin/19.1` @ `e69bebcc4` (FS-7 live). No deploy, no
server change (only read-only counts, §1). Go-live is batched later on the owner's word.
Round 2 applies the architect's FS-10 decisions: (1) lock a box only while something on that database
really reads it, name the reader, show a hidden box again the moment it becomes used; (2) My Profile
and "Marital status" follow the administrator's label (smallest hook inside those pages).

Read: `FORMSTUDIO_LEDGER.md` (R1–R28), `FS7_HANDOVER.md`, `FS_DEPLOY_HANDOVER.md` (non-negotiables);
`FS7_REPORT.md`, `FS_FOLLOWUP1_REPORT.md`, `FS_DEPLOY_REPORT.md` gotchas.

## 0. Go-live module list (exact)

| Module | Version | Why |
|---|---|---|
| `pb_form_studio` | 19.0.1.3.0 → **19.0.1.4.0** | R27 label on the My Payobook field list; "really used" engine (`_pbfs_std_readers` / `_pbfs_std_used` cached / `_pbfs_std_readers_changed` shared helper / notice); phone sheet + pinned bar (JS, XML, SCSS); vi/id |
| `pb_form_studio_people` | 19.0.1.3.0 → **19.0.1.4.0** | employee readers (formula bindings incl. `tax.*`, pay data files); My Payobook note names the reader; upgrade step `migrations/19.0.1.4.0/end-fs10_unhide_formula_read.py` |
| `pb_form_studio_contracts` | 19.0.1.2.0 → **19.0.1.3.0** | contract readers; upgrade step `migrations/19.0.1.3.0/end-fs10_unhide_formula_read.py` |
| `pb_form_studio_reach` | 19.0.1.1.0 → **19.0.1.2.0** | the readers' SAVE POINTS (`models/std_readers.py`); R27 note; fills the My Profile / My details label hook (`controllers/portal.py` `_ess_field_labels`); tests |
| `pb_me_portal` | 19.0.3.8.0 → **19.0.3.8.1** | label hook on My Profile (architect-authorised, lines in §2) |
| `pb_me_details` | 19.0.1.0.1 → **19.0.1.0.2** | label hook on "Marital status" (lines in §2) |
| `pb_learn` | 19.0.20.8.9 → **19.0.20.8.10** | lesson L42 wording + practice copy (static assets) |

`-u pb_form_studio,pb_form_studio_people,pb_form_studio_contracts,pb_form_studio_reach,pb_me_portal,
pb_me_details,pb_learn` (one command). `pb_form_studio_lists` unchanged. JS/SCSS changed → purge
`/web/assets/%` per database + restart. `pb_me_portal` / `pb_me_details` are shipped by other streams:
check the deploy notes for an open START on them first. Not edited: `pb_lifecycle/`, `pb_pack_*`, any
standard addon, `pb_explorer` (FS-8), `pb_employee_form_tidy` / side-panel bank files (FS-9). No file
shared with `fs-8` / `fs-9`.

## 1. Item 4 — "Place of Birth" says a pay formula reads it, yet could be hidden

### Why (verified facts, file:line at `e69bebcc4`)
| # | Fact | Where |
|---|---|---|
| F1 | The My Payobook note "A pay formula reads it, so only HR changes it." was given to every field of the formula **catalogue** (fields a formula CAN be bound to) | `pb_form_studio_people/models/form_studio.py:177-202, 258` |
| F2 | The hide lock used only **live bindings** of this database | `pb_form_studio_people/models/standard_fields.py` `_pbfs_people_formula_used` (before) |
| F3 | So Place of Birth (a catalogue field nobody had bound on that database) carried "a pay formula reads it" and could be hidden | — |
| F4 | The live check also missed formulas bound through a tax source (`tax.*`, `pb_me_tax`) | `pb_me_tax/models/formula_sources.py:34-45` |
| F5 | Locks were worked out with two searches on every form open (no cache) | `standard_fields.py` (before) |

### Fix — architect ruling: lock only what is REALLY read on that database
* **Always locked (unchanged FS-7 hard list):** required to save, name, company, Country of Work,
  wage and contract/pay set-up, org/approval routing, logins, statutory boxes, tax, bank.
* **Locked only while really used:** a pay scheme component bound to the field (`employee.<f>`,
  related source, `tax.*`; `contract.<f>`) in a scheme that is not archived, or a pay data file column
  that fills it. Reason names it: **"Used by pay formula: <scheme>"** / **"Filled by pay data file:
  <scheme>"** (two names, then "and n more").
* Other readers checked: bank layouts read only account / holder / bank / employee code / name / work
  email (`pb_pay_delivery/models/bank_file_layout.py:36-58`, `bank_export_wizard.py:157`,
  `pb_pay_delivery.py:402`) — all always locked; government form lines map PAY ITEMS, not fields
  (`pb_form_lines/models/form_map.py:53-75`), so a field reaches a form only through a pay item, which
  the formula check sees; statutory readers are code (always-locked list); approval routing follows
  department / manager / job / company (always locked). Not covered: conditions inside Workflow Studio
  workflows (`pb_lifecycle`, may not be edited or depended on) — a follow-up if wanted.
* **My Payobook note now tells the truth:** really used → "Used by pay formula: <scheme> Only HR
  changes it."; only in the catalogue → "A pay formula can read it, so only HR changes it." (still not
  employee-changeable, but hideable). Test L2 walks every field.
* **Cached per database** (`_pbfs_std_used`, `templates` cache, key = record type + language): no
  reader query on a form open (test L7).
* **Later use → shown again at that moment** (`_pbfs_std_readers_changed`, ONE helper, called from the
  save points in `pb_form_studio_reach/models/std_readers.py`: component create / write of its source,
  scheme, kind / delete; scheme archived or restored / deleted; pay data file column create / write of
  its target / delete). It clears the cache (the registry tells every worker), and if a hidden field
  is now used: rule cleared (own label kept), one history line, one notice to the tenant
  administrators — "<box> is shown again because the pay formula <scheme> now uses it." — in the inbox
  of administrators who read notices in the app, and as a pop-up for those online (nobody is e-mailed:
  tenant e-mail is off on purpose), and every open Form builder is told (bus). Nothing hidden → only
  the cache is cleared.
* **Upgrade step** (both hosts): clears only rules on fields that are really used (local: School,
  bound by a seeded scheme → cleared; Place of Birth hidden, nothing reads it → kept).
* Direct call refused (two-worker run): `update_standard(..., {std_hidden: True})` → "Used by pay
  formula: DEMO FS10 Workers study_field (Vietnam) It cannot be hidden."

### Per site — how many of the 23 boxes are really used (read-only counts, live, 2026-11-20)
Read-only SELECTs (`BEGIN READ ONLY … ROLLBACK`), field names and counts only.

| Site | Really used (of 23) | Which | Hidden standard fields now |
|---|---|---|---|
| payobook | **0** | — | 0 |
| payobook_template | **0** | — | 0 |
| p0clone | **0** | — | 0 |
| rize | **22** | every one except Permanent address: 19 employee boxes read by 2–8 scheme components each AND filled by 1–4 pay data file columns; contract Location, Cost center (3 components, 2 columns), Signed on (8 / 4) | 0 |
| sudima | **0** | — | 0 |

So on rize those 22 boxes are locked (with the scheme named) the moment this goes live; everywhere
else all 23 stay hideable. Upgrade step expected count: **0 on every site** (nothing hidden).

## 2. Item 1 — R27: My Payobook shows the administrator's label

* Engine `_pbfs_portal_fields` (the ONE list every Form builder surface on My Payobook reads): own label
  in the reader's language; none in that language → built-in; Reset → built-in.
* Reaches: My details › Company details card, Change company details form, the waiting change (My
  requests title, approver rows), the "no longer takes changes to …" note.
* **My Profile and "Marital status" (architect-authorised hook, smallest edit):**
  * `pb_me_portal/controllers/portal.py:66-72` — new `_ess_field_labels(emp)` → `{}` (the one helper;
    empty = built-in words); `:194` — `_profile_card` adds `'labels': self._ess_field_labels(emp)`.
  * `pb_me_portal/views/portal_templates.xml:696-702` (the seven My Profile rows) and `:713, 715, 717,
    719, 721` (the five change-form labels): `<span>Work Phone</span>` →
    `<span t-out="profile['labels'].get('work_phone')">Work Phone</span>` — QWeb prints the body when the
    value is empty, so the built-in words and their translations are untouched.
  * `pb_me_details/controllers/portal.py:123` — `person['labels'] = self._ess_field_labels(emp)`;
    `pb_me_details/views/portal_templates.xml:102` — the "Marital status" `<dt>` the same way.
  * `pb_form_studio_reach/controllers/portal.py` `_ess_field_labels` fills it from
    `_pbfs_std_rules('hr.employee')` (reader's language). Nothing else changed in those pages (the
    marital change FORM keeps its own label — not asked).
* Browser (390 px, employee): Work Phone renamed "DEMO Office line" → My Profile row reads it, others
  unchanged; Marital Status renamed "DEMO Family status" → My details line reads it; earlier walk: Place
  of Birth "DEMO Born in" / "DEMO Sinh tại" on `/vi/my/details`, Reset → built-in.

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

### Numbered (new) — all PASS on the branch
| # | Case | Where |
|---|---|---|
| L1 | Place of Birth free while nothing reads it; a live scheme component bound to it → locked, reason "Used by pay formula: <scheme>"; hide refused by direct call (all / by country) and by Publish; rename allowed; scheme archived → free again; value untouched | `pb_form_studio_people/tests/test_fs10_locked.py` |
| L2 | Every field whose My Payobook note says "Used by …" is locked; a field a formula merely could read says "can read" and stays free | same |
| L3 | A component bound through `tax.*` locks its employee field | same |
| L4 | **Later use:** a hidden field is shown again at the save of a component that reads it — rule cleared, own label kept, one history line, ONE notice ("… is shown again because the pay formula … now uses it"), a second save sends nothing more | same |
| L5 | A pay data file column locks the field it fills ("Filled by pay data file: <scheme>"); column deleted → free | same |
| L6 | Upgrade step clears only really used fields; free fields keep their rule; second run nothing | same |
| L7 | Cached: no reader query on repeated form opens; the save clears the cache, next read sees the lock | same |
| L8 | Blood type / Religion stay hideable | same |
| C4c | Contract: Location / Cost center / Signed on / HR Responsible / Notes free while unused; `contract.location` bound → locked with the scheme named, renamable; scheme archived → free | `pb_form_studio_contracts/tests/test_fs7_standard.py` |
| R1/R4 | Own label on the Company details card and the change form; Reset → built-in (HTTP, portal login) | `pb_form_studio_reach/tests/test_fs10_r27.py` |
| R2 | Reader's language: vi typed → vi; id not typed → built-in; request label in vi | same |
| R3 | Waiting change named by the own label (My requests title, approver rows) | same |
| R5 / R6 | Silent: nothing renamed → built-in; custom field label unchanged | same |
| R7 | **My Profile** row and **"Marital status"** follow the own label; other rows keep their words; Reset → built-in (HTTP) | same |
| P | **Three payslips** (two schemes, two people; one formula reads Place of Birth) recomputed **identical** after hiding 5 free fields, renaming 5, after a later formula save showed a hidden field again, and after the upgrade step on both record types (real employee screen) | same |
FS-7 tests moved off fields whose state depends on use: test 2 / 4b / 12 use Visa No; test 5 picks the
first free one-country box.

### Two workers (`t_workers.sh` / `workers.py`, local server `--workers=2`, JSON-RPC, fresh connection per call)
Field of Study hidden → **12/12** form reads hidden on both workers; a pay scheme component reading it
saved through RPC (the save point) → **0/12** hidden, answered by both worker processes; hiding it again
refused: "Used by pay formula: DEMO FS10 Workers study_field (Vietnam) It cannot be hidden." History
line written; the notice went as a pop-up only (that administrator reads notices by e-mail — no mail is
sent by design; L4 proves the inbox notice).

### Silent upgrade (local copy of the 19.1 state, old code → new code, `snap.py` before / after)
Seeded with the OLD code: Blood type hidden, Place of Birth hidden, School hidden for Vietnam AND a
live scheme reading School, Department renamed "DEMO Team", Work Mobile ticked for My Payobook,
contract Location hidden. After `-u` of the seven modules: employee + contract forms (en, vi), side
panel, People table columns and My Payobook list **byte-identical**; lock counts identical (employee
89 / 155, contract 28 / 33); stored rules identical except School's Vietnam rule, cleared by the
upgrade step (log: employee 1, contract 0) — it was already ignored on screen because a scheme reads
School. Place of Birth, Blood type and contract Location stay hidden (nothing reads them). Nothing was
hidden, renamed or ticked by the upgrade itself.

### 5b. Suites (`--test-tags`)
First round (fresh copy of the earlier base, six modules): baseline `origin/19.1` 560 tests, 4 failed,
1 error (all `pb_learn`); branch 572, the same five. Second round (decisions applied; new local base
built from `wf2p6_base` + the Form builder installed with the 19.1 code — the earlier base was gone):
branch, eight modules: **695 tests**; Form builder suites engine 41, contracts 31, lists 13, people 43,
reach 62 (+ 7 re-run after the payslip test fix, 0 failed) — **all FS-10 tests pass**. Failures, all
present with the 19.1 code on the same base (baseline runs `baseline2.sh` / `baseline3.sh`):
`pb_me_portal` 8 (home cards ×3, home source ×2, profile change flow, portal-only doors ×2 — identical
list before and after the hook), `pb_learn` (anchor registry, composer, guide truth, learnrev p4 as in
round one, plus guide truth 03 and reachability 02/03/04/07 on this base), and people
`test_13` (`hourly_cost` — this base has no hourly-cost module). Learn's own tools: `--check` clean,
`test_step_shape.py` 0 failed, `check_contract.py` 2 known failures.
White-label: no "Odoo" in any new string, template or .po msgstr; no "Payobook" in a `biz_*` module
(none touched).

## 6. Gotchas (ledger rows)
* FS10-1 The scratchpad path holds "git" and the worktree guard refuses compound shell lines with it
  (FSD-6 again) — even `mkdir && psql`; keep every step its own command or a script file.
* FS10-2 Two answers to one question: the My Payobook note and the hide lock each worked out "does a
  pay formula read it" their own way. One cached helper (`_pbfs_std_used`) per question; a test walks
  every field and compares the two notes.
* FS10-6 `ReachCase` (reach tests) patches `_pbfs_hosts` with a copy of the ENGINE's method taken at
  import, so the real employee / contract screens are absent there: a test that needs them must be a
  plain `TransactionCase` (the first payslip test silently skipped for this reason).
* FS10-7 A cache of "what reads this field" must be cleared at the readers' save points, not on a timer:
  `registry.clear_cache('templates')` is what every worker follows (two-worker run: 12/12 → 0/12).
* FS10-3 An upgrade step that calls `_pbfs_standard_locked` reads the forms (required-on-form check),
  which makes the registry print its "inconsistent compute" UserWarnings with stacks in the log (only
  warnings, 0 ERROR). Expect them in the go-live log; they are not failures.
* FS10-4 On a phone the overlay itself scrolls, so anything `position: sticky; top: 0` inside it
  (the left filter) slides under a sticky studio bar — offset by the bar's measured height.
* FS10-5 Escape keydown never reaches a `window` listener inside the Form builder overlay on this
  build (stopped upstream); do not rely on Escape for a phone control.

## 7. Owner questions (plain words)
1. **Workflow Studio conditions:** a box used only inside a workflow's condition (not a pay formula or
   pay data file) can still be hidden from the screens; the workflow keeps reading it. Should those
   count as "really used" too (a follow-up inside the workflow module)?
2. **Notices by e-mail:** the "shown again" notice goes to administrators' in-app inbox and as a
   pop-up; administrators who chose e-mail notifications get only the pop-up and the Form builder
   history (no mail is sent, because tenant e-mail is off on purpose). Fine?
