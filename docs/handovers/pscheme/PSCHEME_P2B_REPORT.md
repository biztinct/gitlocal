# PSCHEME P2b — report: job change, upload sheets, hiring offer and pay-data-file joiners follow the person's pay scheme

Implementation engineer, 26 Nov 2026. Worktree `gitlocal-worktrees/pscheme-p2b`, branch `pscheme-p2b` (from
`59e68e10e`). Local only: nothing pushed, no live server or database. Engineering document: real technical names on
purpose; no client data.

## 1. Result

**GO for P3** — every numbered test passes, all six walks pass with a clean console, and the before/after suites
differ only by this phase's new tests and the deliberate updates listed in §4 (counts in §4.2).

Commits on `pscheme-p2b` (oldest first):

| Commit | What |
|---|---|
| `3bf021f4e` | Shared seams in `pb_scheme_map` (ADDED file): usual scheme, company move, take-back, R6 words; Add employee shares the usual scheme |
| `4d2d91abf` | A — job change moves Country of work and the pay scheme from its start date |
| `6e83a89d9` | B — Updates: a new employee's own pay scheme; pay scheme changes of people already here |
| `c143df58b` | C — hiring offer default follows the offer's Country of work |
| `4374ab70c` | D — pay-data-file joiners get the file's scheme; the review names people with another own scheme |
| `d74645de1` | vi_VN + id_ID for every new string; whole-sentence screen strings; retired msgids removed |
| `10d7260ba` | B — walk fixes: review headline for a sheet of pay schemes only; how such a change is changed back |
| `3b4c34627` | Ledger gotchas PS-b1 … PS-b8 |
| (this file) | report |

## 2. What changed on screen (screen words)

**A — Change job.**
- "Team and place" now also holds **Country of work** (Unchanged / the countries).
- Picking a new Country of work, or a new company, opens a **Pay scheme** chooser right under it: cards of that
  country's pay schemes in the company they will work in, the usual one pre-filled ("usual for this country"), a
  "Keep <their pay scheme>" card (not offered on a company move — a move to another company needs one of its pay
  schemes), the mid-month advance switch when the scheme has one paired advance (a small chooser when several),
  arrow keys move between cards. No scheme for that country: "No pay scheme for Malaysia in DEMO Farms yet. Add one in
  Mapping first."
- A team-only move shows the person's scheme with a "Change pay scheme" link, and the impact panel says once:
  "Their pay scheme stays <scheme>. Change it here if this move changes who pays them."
- The impact panel lists Country of work and Pay scheme before → after, and when the start date is not a 1st:
  "<old> still pays November 2026. <new> starts with the next pay run."
- The change's page and the board row name "Country of work, Pay scheme". On approval (or on its day for a dated
  change) Country of work and the person's own pay scheme are written from the start date; "Take it back" restores
  both exactly, and refuses in a sentence when somebody changed the pay scheme since.

**B — Updates.**
- New-employee rows: the "Pay scheme" column is the person's own pay scheme. Empty → the only/usual scheme of the
  row's Country of work ("The only pay scheme for Vietnam." / "The usual pay scheme for Indonesia."); a scheme of
  another country → a red line naming the reason and the allowed schemes, with a "Pick the pay scheme…" dropdown in
  the row; a country with several schemes and no usual one asks the same way. The row is added only once it is
  settled. A "Mid-month advance" column (empty = the scheme's own advance, "No" = none, or a name).
- The blank new-employee sheet gains Country of work, and "Mid-month advance" only where the company has advances;
  its Read me explains the column (the old "a check only" sentence is gone).
- People already here: a "Pay scheme" cell that differs from their pay scheme shows in the person cell as
  "Pay scheme: <old> → <new> · from <date>" with the R6 sentence when the date is not a 1st, and "Leave this one out";
  an unchanged cell shows the scheme in grey and changes nothing; a scheme of the wrong country is red with the
  reason. A row that changes Country of work suggests "Change it to <new country's scheme>" — nothing happens unless
  that is pressed.
- A sheet with only a pay scheme column works ("This file changes 1 person's pay scheme."). The Apply step has a
  "Pay scheme" card ("Changed at once. No approval needed." / "One request per pay scheme, for a payroll manager to
  approve" / the refusal sentence), the button reads "Change 1 pay scheme" / "Send 1 pay scheme change for
  approval", and Done lists each scheme with its people and date (Waiting / Done).
- The "Goes to" list names the column "Pay scheme" (was "Pay scheme (a check for new employees)") with "Mid-month
  advance" beside it; the kind column reads "Their pay scheme".

**C — Hiring offer.** "Build from a total" opens on the offer's Country of work's usual pay scheme (a Vietnamese
hire in an Indonesian team: the Vietnamese scheme), the same answer Add employee gives.

**D — Pay data file.** A person the file creates gets the file's scheme as their own from the period's first day.
The import review and the batch page say, quietly and only when it applies: "1 person in this file has another pay
scheme of their own: Made Prasetya. They are not changed."

Hero moments: (A) pick a new Country of work and watch the scheme card pre-fill and the impact panel write the
before → after and the one-payslip-a-month sentence; (B) a red joiner row fixed from its own dropdown, turning to
"Will be added" in place.

## 3. Deviations (each with its reason)

1. **Scheduled job changes write the rows on their day** (PS-b4). T3 requires "nothing until the cron day", so the
   person panel shows "Job change from <date>" rather than "Changes to <scheme> on <date>" until then. W1 was walked
   with a past date (15 Nov) so the panel line could be seen.
2. **Lasting-sheet pay scheme changes go through `person_set`** (ledger R9 route: a payroll manager approves, or
   saved at once) — not through the Records Desk lanes the rest of the sheet uses. The handover said "through the
   sheet's own approval path"; R9 is binding, so the Mapping route is used. Consequence: these changes are changed
   back from the person's record, not by Undo in Past updates; the Apply step says so. A sheet with only pay scheme
   changes leaves no "Past updates" entry (nothing for the desk to file).
3. **Source of lasting-sheet rows is `import`** (label "Pay data file", a P1 line in `pb_scheme_map` this stream may
   not edit). P3: rename the label to "From a file" or add a source.
4. **A joiner row with no Country of work and no pay scheme cell writes no row** — they fall back to the team (R2),
   as the old sheet did; the blank sheet now carries Country of work so new sheets avoid this.
5. **The scheme chooser in Change job is inside "Team and place"**, opened by country / company / a link — not a
   fourth section (keeps the three steps).
6. **`_most_paid` moved to `pb.scheme.map`**; Add employee's `_most_paid` delegates to it (one body, P1 tests
   unchanged).
7. **Walks used RPC/shell for two clicks**: approving the W4 second-approver request (P1 walked that inbox), and
   seeding W5's offer and W6's batch (their screens were walked; the data was made by script).

No ledger §1/§2 decision was left un-honoured.

## 4. Tests

### 4.1 Numbered tests

| # | Test | Result |
|---|---|---|
| T1 | `pb_job_change/tests/test_pscheme_p2b.TestJobChangePayScheme.test_t1_country_and_scheme_from_today` | pass |
| T2 | `test_t2_the_15th_old_scheme_pays_that_month` | pass |
| T3 | `test_t3_scheduled_nothing_until_the_day` | pass |
| T4 | `test_t4_company_move_ends_the_old_company_first` | pass |
| T5 | `test_t5_take_it_back_exactly` (incl. refusal after a hand change) | pass |
| T6 | `test_t6_team_only_touches_no_row` + `test_job_change.test_jc12_paid_by_what_if_is_read_only` (extended) | pass |
| T7 | `test_t7_what_if_reads_the_person_first`, `test_t7b_choices_follow_the_new_country` | pass |
| T8 | `pb_updates/tests/test_pscheme_p2b.TestUpdatesPersonScheme.test_t8*` (default one / usual / asks / wrong country / dropdown / apply from first day / run population / advance on-off / waiting hire) | pass |
| T9 | `test_updates_p3b.test_H6_pay_scheme_column` updated deliberately (§4.3); `test_updates_p2b` fixtures: no change needed (§4.3) | pass |
| T10 | `test_t10_existing_people_change_from_the_row_date`, `test_t10b_second_approver_lane`, `test_t10c_country_change_suggests_never_applies`, `test_t10d_wrong_country_in_a_lasting_row` | pass |
| T11 | `test_t11_readers_name_each_persons_own_scheme` (`_people_schemes`, pay-item verdict, year-to-date `_ty_months_of`) | pass |
| T12 | `pb_pay_package/tests/test_pscheme_p2b.TestOfferFollowsCountry` (4 branches + company country, equals Add employee) | pass |
| T13 | `pb_scheme_map/tests/test_pscheme_p2b.TestPschemeP2bSeams.test_t13_*` (file joiner, advance file, other own scheme named, wizard + cockpit payloads) | pass |
| T14 | job change `test_t14_rights`, Updates `test_t14_rights` (portal refused, no write access on rows) | pass |
| T15 | static scan of the phase diff (132 literals/template texts) + every new msgid (86): no "Odoo", rung, config, cycle; 0 "Odoo" in new msgstr; every new msgid in vi_VN and id_ID; `msgfmt -c` passes except the known pre-existing duplicate in `pb_hr_payroll_formula/i18n/vi_VN.po` (P1 T29 note) | pass |
| T16 | `test_static_contract.test_t12_the_ladder_edit_is_guarded`, `test_t16_formula_module_reaches_the_map_by_probe_only`; P1's tests in the after suite | pass |

### 4.2 Suites before / after

Tags `/pb_scheme_map,/pb_new_hire,/pb_payrun_wizard,/pb_hr_payroll_formula,/pb_employee_vault,/pb_contracts,/pb_updates,
/pb_job_change,/pb_loans,/pb_retro,/pb_expense_payroll,/pb_pay,/pb_me_tax,/pb_decision_room,/pb_pay_package,
/pb_import_wizard,/pb_import_batch` on two copies of `ps2b_base` (`ps_base` upgraded to P1 HEAD + `pb_pay_package`
installed). "Before" = a `git archive` of `59e68e10e` as the addons path.

- **before**: 1,817 tests, 8 failed + 6 errors.
- **after**: 1,844 tests (+27 new: job change 9, Updates 10, scheme map 6, offer 2), 8 failed + 7 errors.
- The one extra error was mine: `test_jc12` (extended in this phase) created a scheme without a country (the column
  is required). Fixed in the last commit; `/pb_job_change` re-run on the after copy: **31 / 31 pass**.
- Apart from that, **the failing tests are the same on both sides** — the pre-existing, environmental set P1 listed
  (`TestS5fLeaverBackpay` F01–F09, the two duplicate-key fixtures, `TestCd1Contract360.test_01`,
  `TestDecisionRoomStaticContract.test_t14`, `TestRd49SyncCost` 02ab / 02i, `TestRecordsR1OneTime.test_07b`,
  `TestS2dTaxFlow.test_t9`, `TestT3bLetterToken.test_t3b_9`, `TestVietnameseIsComplete.test_t4c`). Nothing fails
  only after; nothing fails only before.
- P1's own tests (`test_person_scheme`, `TestSchemeMap`, static contract, `pb_new_hire` P8 / new hire / payslip
  example — Add employee now reads the shared usual scheme) all pass in the after suite.

### 4.3 Deliberate updates to existing tests

- `pb_updates/tests/test_updates_p3b.py::test_H6_pay_scheme_column`:
  - row 3 (Kitchen, "P3B Daily") was refused with "P3B Kitchen is paid under P3B Monthly, not P3B Daily…" → now
    addable, scheme "P3B Daily", team cell ok (R1: the column is the person's own scheme);
  - row 4 (Garden, "P3B Daily") had the note "No pay scheme covers P3B Garden" → now scheme "P3B Daily", no note;
  - `joiners_added` 2 → 3; new assertion: the three people's own rows (scheme, 1 Dec 2026, `import`).
- `pb_job_change/tests/test_job_change.py::test_jc12_paid_by_what_if_is_read_only`: added — a person with their own
  pay scheme moving team: `changes_scheme` False, `scheme_after` = their own, the "stays" sentence, no row written.
- `pb_updates/tests/test_updates_p2b.py` (team-line fixtures, FACTS §10.1): unchanged and passing — nobody there has
  rows, so `_people_schemes` answers as before; the per-person case is T11.

## 5. Walks (local `ps2b_w`, Claude-in-Chrome, console read every walk)

| # | What I did and saw | Result |
|---|---|---|
| W1 | Payroll manager, Change job › Made Prasetya (own "Indonesia large scheme") › Transfer › Country of work Vietnam → the Pay scheme card "Vietnam monthly staff · usual for this country · VND" pre-filled; impact: Country of work Indonesia → Vietnam, Pay scheme → Vietnam monthly staff, "Indonesia large scheme still pays November 2026. Vietnam monthly staff starts with the next pay run." Start 15 Nov 2026 → Send → "Done" (fast lane). Rows: large scheme until 14 Nov, Vietnam from 15 Nov (`job_change`). Side panel: chip "Paid by Vietnam monthly staff", Pay and tax "Their own pay scheme since 15 Nov 2026", History (2). Take it back → rows and Country of work exactly as before. | pass |
| W2 | Company → DEMO PS2B Second Co: chooser "No pay scheme for Indonesia in DEMO PS2B Second Co yet. Add one in Mapping first." and the problem "Pick the pay scheme that pays Made Prasetya at DEMO PS2B Second Co. A move to another company needs one of its pay schemes."; no Keep card. Country of work Vietnam → "DEMO Second Vietnam monthly" pre-filled; sent → old row ended 25 Nov, new row 26 Nov in the second company; taken back → restored. | pass |
| W3 | Updates › Upload your own file (3 joiners): Ayu (Indonesia, empty) → "Indonesia monthly staff · The usual pay scheme for Indonesia."; Binh (Vietnam) → "The only pay scheme for Vietnam."; Dewi (Indonesia, "Vietnam monthly staff") → red "…is a pay scheme for Vietnam, but DEMO Dewi Kusuma works in Indonesia. Pick one of: Indonesia large scheme, Indonesia monthly staff." + dropdown → picked → "Will be added". Added → rows from 15 Dec / 1 Dec, `import`. | pass |
| W4 | Sheet with only Name, Pay scheme, Start date: Made → "Pay scheme Indonesia large scheme → Indonesia monthly staff from 15 Jan 2027" + R6 sentence; Dian (unchanged) grey. Apply card "Changed at once. No approval needed." → "Change 1 pay scheme" → Done "1 pay scheme changed". Second lane (route switched on, HR officer): card "One request per pay scheme, for a payroll manager to approve" → "Sent for approval" / Waiting → approved by the payroll manager → Dian's row from 15 Jan 2027. | pass (after the headline fix: it first said "There is nothing to change") |
| W5 | Hiring › DEMO Field Supervisor Vietnam (team Indonesia Operation, country Vietnam) › Offer › Build from a total → "Vietnam monthly staff (Vietnam)" | pass |
| W6 | Batch page of a December file for "Indonesia monthly staff" with Made (own other scheme) and a new person → "1 person in this file has another pay scheme of their own: Made Prasetya. They are not changed."; the new person's row from 1 Dec (`import`). | pass |
| vi/id | Vietnamese: every new JS string through `_t` and the server sentences (`preview`, `scheme_options` with `lang`) read Vietnamese ("Chương trình lương chuyển từ … từ 15 thg 12 2026.", "… vẫn trả lương tháng 12 2026…"); Indonesian "stays" sentence checked the same way. The browser's own page translation was on in the walk tab (PS-b6), so vi was verified at the source rather than by screenshot. | pass |
| Console | errors only, every walk | clean |

## 6. Design bar self-score (out of 10)

| | Score | Why |
|---|---|---|
| Hero moment | 8 | The card pre-fills and the impact panel writes before → after and the R6 sentence live; minus: no motion on the panel rows themselves. |
| Zero dead-ends | 9 | Every refusal names its fix (company needs a scheme, wrong country lists the allowed ones, no scheme → Mapping); minus: the lasting sheet's pay scheme change has no Undo in Past updates (said on screen). |
| Plain language | 8 | Screen words throughout; minus: pre-existing "Pay scheme" msgid in `pb_job_change` vi reads "Bảng lương"/"Chính sách lương" (not this phase's "chương trình lương"), and country names stay English in vi. |
| Motion | 8 | Chooser and sheet lines enter with a short rise; card press and switch slide; reduced motion respected. |
| Keyboard | 8 | Arrow keys move the scheme card, Enter/Space safe; the joiner dropdown is a native select. |

## 7. Every file touched in `pb_scheme_map` (for the merge with P2a)

- `pb_scheme_map/__manifest__.py` — version 19.0.2.6.0 → 19.0.2.6.1 (P2a bumps too: take the higher, re-bump in P3)
- `pb_scheme_map/models/__init__.py` — one import line added at the end (`pb_person_scheme_tools`)
- `pb_scheme_map/models/pb_person_scheme_tools.py` — NEW
- `pb_scheme_map/tests/__init__.py` — one import line added (`test_pscheme_p2b`)
- `pb_scheme_map/tests/test_pscheme_p2b.py` — NEW
- `pb_scheme_map/i18n/vi_VN.po`, `id_ID.po`, `pb_scheme_map.pot` — 2 entries appended at the end

No line phase 1 wrote was edited. Other files this stream changed that P2a may also touch: `pb_hr_payroll_formula/
__manifest__.py` (version) and its `i18n/*.po` (2 entries appended), `payroll_import_batch.py` (P2a owns
`contract_fill_in.py` only).

## 8. Lesson and help sentences now untrue (for P3)

- No lesson in `pb_learn` covers the Change job pay scheme, the Updates pay scheme column, the offer default or the
  pay-data-file line (searched content, anchors, replicas). P1's §8 list stands.
- The Updates blank sheet's own Read me was rewritten in this phase.

## 9. Versions, ids, rights, strings

| Module | Version |
|---|---|
| `pb_scheme_map` | 19.0.2.6.1 |
| `pb_new_hire` | 19.0.1.8.1 |
| `pb_job_change` | 19.0.1.1.0 (new fields) |
| `pb_updates` | 19.0.1.9.0 (new fields on `pb.updates.joiner`) |
| `pb_pay_package` | 19.0.1.1.1 |
| `pb_hr_payroll_formula` | 19.0.1.175.0 |
| `pb_import_wizard` | 19.0.1.4.2 |
| `pb_import_batch` | 19.0.2.2.3 |

New fields: `pb.job.change.new_payroll_country / new_scheme_id / new_advance_scheme_id`;
`pb.updates.joiner.scheme_id / advance_scheme_id`. New xml ids, groups, access rows: none (nobody gains write on
`pb.person.scheme`; every row is written under sudo behind the existing gates). New RPCs:
`pb.job.change.board.scheme_options`, `pb.updates.desk.scheme_outlook`; `apply(..., schemes=)`.

New msgids (all in vi_VN and id_ID): pb_scheme_map 2, pb_job_change 30, pb_updates 52, pb_hr_payroll_formula 2.
Retired: pb_updates 5, pb_job_change 1.

## 10. Gotchas and questions

Ledger §4 now has PS-b1 … PS-b8.

Local state: databases `ps2b_base`, `ps2b_b` (before), `ps2b_a` (after), `ps2b_dev`, `ps2b_w` (walk world: users
`ps2b.pay` / `ps2b.hr`, password local only, in the scratch seed). The walk server is stopped.

Questions for the product owner (plain words):
1. **A pay scheme changed from an update sheet** is changed back from the person's record, not with Undo in Past
   updates (it goes to the payroll manager like every pay scheme change). Is that acceptable, or should Undo in Past
   updates also put pay schemes back?
2. **A dated job change** (starting next month) changes the person's pay scheme on its start date, together with
   everything else in it. Until then the person's record says "Job change from <date>", not yet "Changes to <scheme>
   on <date>". Is that enough, or should the record show the coming pay scheme as soon as the job change is approved?
