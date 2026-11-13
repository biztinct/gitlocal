# UPDATES — Phase 1 report (front door)

Implemented, tested, deployed ×4 and checked live on 2026-11-11 by the Opus implementation
agent, against `UPDATES_P1_HANDOVER.md` and `UPDATES_LEDGER.md`.

**Shipped:** `pb_records` 19.0.1.8.4 (two read-only seams) and new module `pb_updates`
19.0.1.0.1 (People › Updates). Live on `payobook`, `payobook_template`, `p0clone`, `rize`.
Never `abm`; `sudima` and `pbf_preview` untouched (outside the deploy set — see §8).

---

## R1. Tests

### `pb_updates/tests/test_updates.py` — 27 tests, all PASS

Run three times: local clean copy of `am_wf2p2` (27/27), local copy already holding
browser-walk data (27/27), and on the live server against `p0clone` inside both deploys
(26/26 in the first deploy; 27/27 in the follow-up — see R2).

| # | Test | Result |
|---|---|---|
| T1 | `test_T01_peek_without_columns_is_unchanged` — peek with no `columns` equals peek with `columns=None`; exported file changes nothing, identity `code`; `matched` in file order (rows 2,3,4), `sum(cells) == len(changes)` | PASS |
| T2 | `test_T02_columns_map_foreign_headings` — CSV with Indonesian headings; only the mapped column produces changes; nothing written | PASS |
| T3 | `test_T03_unknown_card_is_ignored_by_heading` — unknown card → heading in `columns_ignored`, no exception; only-unknown → `{'ok': False}` sentence | PASS |
| T4 | `test_T04_same_card_on_two_columns_first_wins` | PASS |
| T5 | `test_T05_import_columns_on_a_desk_export` — data columns `how='id'`, three identity columns `how='identity'`, three samples each | PASS |
| T6 | `test_T06_import_columns_on_foreign_headings` — `how=''`, `field_id=''`; a non-spreadsheet is refused in a sentence | PASS |
| T7 | `test_T07_matching_is_remembered` — after one apply: `layout_known`, every column `how='memory'`, "Catatan" remembered as not brought in, `use_count 1`; a different file sharing a heading still finds it | PASS |
| T8 | `test_T08_near_miss_heading_is_a_guess` — "Job Titel" → guess on Job Title; "Zzqx Wibble" unplaced | PASS |
| T8b | `test_T08b_a_heading_that_names_the_person_finds_the_person` — "Employee Name" proposed as *finds the person*, not as a value to write (ledger G5) | PASS |
| T9 | `test_T09_review_payload` — file order + file row numbers (2,3,5 with a blank row 4), old/new/status per cell, blank cell absent, nothing written | PASS |
| T9b | `test_T09b_same_person_twice` — R3 evidence, see R3 | PASS |
| T10 | `test_T10_unmatched_row_is_listed_never_created` — desk sentence, values kept, employee count unchanged; bound-by-hand recheck is `ok` | PASS |
| T11 | `test_T11_apply` — batch, attachment (`res_model`/`res_id`, not public, bytes equal), layout map, apply linked, `source='import'`, note = name, value changed, history row, no payslip touched | PASS |
| T12 | `test_T12_apply_with_nothing_to_change` — no batch left, `nothing: True` + sentence; empty list refused | PASS |
| T13 | `test_T13_blank_name_is_refused` — `''`, spaces, `None`: sentence, nothing written | PASS |
| T14 | `test_T14_undo` — value restored, state `undone`, second undo refused in a sentence, unknown id refused | PASS |
| T15 | `test_T15_undo_keeps_a_value_changed_since` — `skipped_changed_since 1`, their value kept | PASS |
| T16 | `test_T16_viewer_may_review_but_not_apply` — viewer sees home, columns, review (cells refused with the desk's reason); download and apply refused in sentences; nothing written | PASS |
| T16b | `test_T16b_hr_user_applies_and_undoes` — real HR user end to end | PASS |
| T17 | `test_T17_other_company_sees_nothing` — no batches, no layouts, no memory, cannot undo company one's batch | PASS |
| T18 | `test_T18_component_for_a_contract_without_that_line` — R3 evidence, see R3 | PASS |
| — | `test_home_topics_and_download` — topics relabelled, bank = 4 columns, file named "… update sheet <date>.xlsx" | PASS |
| — | `test_payobook_sheet_skips_matching` | PASS |
| — | `test_read_only_fields_are_not_offered_and_not_flagged` (ledger G4) | PASS |
| — | `test_text_equal_to_today_is_never_a_change` (ledger G11, live finding) | PASS |
| — | `test_unreadable_and_headings_only` | PASS |
| — | `test_no_odoo_in_visible_strings` (template + `.po`) | PASS |

### Existing `pb_records` suite — 80 of 81 PASS, 1 pre-existing failure

Local copy of `am_wf2p2` with this phase's `pb_records`: **1 failed of 81**
(`TestRecordsR2Desk.test_01a_get_fields_returns_mapped_and_standard_record_destinations`).
**Pre-existing, not caused by this phase:** the same test run against the untouched HEAD copy
of `pb_records` (`git archive HEAD pb_records`, put first on the addons path) fails with the
identical missing set (`f:hr.contract:date_start`, `…:wage`, `f:hr.employee:name`, `…job_title`,
… nine standard fields). The test still expects a pay scheme's catalogue to carry the master
fields, which commit 2e9777879 ("Separate master records from focused payroll inputs")
deliberately separated. Not fixed here (out of scope; needs a test update by whoever owns
`pb_records`).

### Other gates

- `.po` parse gate (`PoFileReader`, same reader as the server) on `pb_updates/i18n/vi_VN.po`
  (286 rows, 247 code rows reach the screen) and `pb_records/i18n/vi_VN.po` (284 rows): PASS
  locally and on the server. Built from `odoo-bin i18n export -l pot` so every entry carries
  `#. module`, `#. odoo-javascript|odoo-python`, `#: code:addons/…:0`.
- Static check: every JS import resolves to an exported name; every icon name exists in
  `@pb_import_kit/js/import_icons`.
- SCSS compiled with libsass (no `min()`/`max()` mixed units).

## R2. Deploy evidence

Two runs, both under `flock /tmp/payobook-studio-deploy.lock`, logged START/DONE in
`/opt/deploy-notes.md`.

**Run 1 — 02:05–02:08 UTC (risky tier, new install).** Unit `updates-p1-20261111T020532Z`.
- Dumps: `/odoo/backups/updates-p1-20261111T020532Z/{payobook,payobook_template,p0clone,rize}.dump`
  (80 MB / 27 MB / 28 MB / 41 MB) + previous `pb_records` tree.
- Dry run first: only `__manifest__.py`, `i18n/vi_VN.po`, `models/pb_records_io.py` differed, and
  the server's copies of those three were byte-identical to HEAD (nobody else's newer work).
- `-i pb_updates -u pb_records` per database: payobook / payobook_template / p0clone / rize all
  EXIT=0; zero ERROR / CRITICAL / Traceback lines in the whole run.
- `p0clone` suite: 0 failed of 26.
- Active scheduled jobs before → after: 49→49, 31→31, 38→38, 81→81 (none newly active).
- Assets: `orm_signaling_assets` row + `/web/assets/%` purge + `web.assets.version` bump per DB.
- Downtime 2 min 13 s. Warm: payobook.com 200, rize.payobook.com 200, p0clone.payobook.com 200.
  No ERROR in `/var/log/odoo/odoo-server.log` after the restart.

**Run 2 — follow-up, `pb_updates` 19.0.1.0.1 (normal tier).** Unit `updates-p1b-20261111T022501Z`.
- Why: the live timing run (R4) found an untouched sheet reading as ~10,000 changes.
- No new dumps (normal tier; Run 1's dumps 20 minutes old). Previous tree kept in
  `/odoo/backups/updates-p1b-20261111T022501Z/pb_updates.prev`.
- `-u pb_updates` per database: all four EXIT=0, zero ERROR lines in the upgrade logs.
- `p0clone` suite: 0 failed of 27. (The test log holds 8 ERROR lines one second AFTER the
  tests finished: live web requests reached the test process while it shut down — ledger G12.)
- Active jobs 49/31/38/81 before and after; assets signalled + purged; down 1 min 50 s;
  sites 200; no ERROR in the server log after the restart.

**Verification after both runs**

| Check | payobook | payobook_template | p0clone | rize |
|---|---|---|---|---|
| `pb_records` latest_version | 19.0.1.8.4 | 19.0.1.8.4 | 19.0.1.8.4 | 19.0.1.8.4 |
| `pb_updates` latest_version | 19.0.1.0.1 | 19.0.1.0.1 | 19.0.1.0.1 | 19.0.1.0.1 |
| state | installed | installed | installed | installed |

Tree hashes (sha256 over the sorted per-file sha256, skipping `__pycache__`, `*.pyc`,
`.DS_Store`), repo = server: `pb_records` 059b88fba97e606d = 059b88fba97e606d; `pb_updates` 809cd39d7cc4d418 = 809cd39d7cc4d418. `abm` database: absent (count 0), not touched.

## R3. What the desk does

**Two file rows for the same person** (`test_T09b_same_person_twice`). The desk judges both
changes independently against today's value (both `ok`), and `apply_changes` writes both in
file order, so **the lower row wins**; both are audited, and Undo restores the original (the
first change's undo is skipped as "changed since", the second's restores the before-value).
Updates keeps both rows in the grid, marks both "In the file twice", shows the upper cell as
"Used further down", and sends only the lower value — the outcome is identical to the desk's,
with one audit row instead of two. For bank columns the desk assembles one account per
person, so it answers once per role, for the last value; Updates attributes that answer to
the lower row.

**T18 — a contract component for a person whose contract has no such line.** The desk **adds
the line**: the cell previews as `ok` from empty (`old=''`), apply creates the
`hr.contract.advantage` row with the amount, and Undo removes the line again (back to
absence, not a saved zero). Not changed.

## R4. Browser walk

**Local (`localhost`, my own throwaway copy, full write walk):**
Home → New update → unreadable file ("That file could not be opened as a spreadsheet…") →
headings-only file ("This file has headings only — fill it in and drop it again.") →
downloaded Payobook sheet with three cells changed (one wage typed as "not a number") → went
straight to Review with "This is a Payobook sheet…" (Match step shown as skipped) → "3 changes
for 3 people. 1 cell needs your attention." → red cell: Enter opened the fix row with the
desk's sentence, typed 7200000 + Enter → cell turned green with a tick, focus returned to it,
sentence became "4 changes for 3 people. Everything checks out." → Apply (name prefilled
"November 2026 update", counts 3 / 4 / 0) → "4 changes are in for 3 people" → Past updates row
with the original file (download 200) → Undo through the confirmation dialog → toast "4 values
are back as they were", row "Undone · Put back on … by Administrator". Then a CSV with
Indonesian headings: nothing auto-matched; Continue refused in both sentences; matched four
columns → review "2 changes for 2 people. 1 row needs your attention." → Find person… typed
"Dewi", Enter → row joined the grid in file order, "Matched by you" → applied → uploaded the
same CSV again: "You have used these headings before, so the matching is remembered", every
column "Remembered from last time" → undone. People hub: Updates tab right after Records; ⌘K
entry registered. Console: no errors at any point.

**Live (`payobook.com`) — read-only:** the browser's existing session (Mitchell Admin, see §8) after both deploys. People › rail
reads Employees · Org chart · Contracts · Records · **Updates** · Pay · Location · Assets ·
Joiners · More; Updates opens inside the hub. Home (empty Past updates state) → New update →
topics 56 / 17 / 4 / 26 with examples, "Everyone you can see (4,554)", bank not pre-picked →
unreadable file and headings-only file give the desk's sentences in the drop zone → a CSV
built in memory with Indonesian headings for three DEMO people (found by name — DEMO people
have no employee code here) plus one ghost row → Match: "None of them is matched yet", matched
three columns, "Catatan" not brought in → Review in 2.3 s: "This file will make 3 changes for
3 people. 1 row needs your attention.", ghost row in the band with "Find person… / Skip this
row", button "Continue without the 1 that needs attention" → **Closed without applying.**
Afterwards on live: 0 named updates, 0 remembered matchings, the three DEMO people's values
unchanged. Console: no errors on any page load or action.

Screenshots in `outputs/updates-p1/` (not committed): `01-home-live.jpg`, `02-start-headings-only-live.jpg`, `03-match-live.jpg`, `04-review-live.jpg`. No live *done* screenshot (nothing applied on live); the done and history screens were checked on the local walk.

**Timing — the largest real file (payobook, 4,575 people × 73 columns, NOT applied):**

| Step | Time |
|---|---|
| Build the sheet (download) | 37.1 s, 572 KB |
| Read the columns | 4.5 s |
| Review (the desk's peek over ~300,000 cells) | 87.3 s, 9.8 MB answer |

The review is slow at this size: it is the desk's `import_peek` / `preview_changes`
evaluating every non-blank cell. Usable (the veil says "Checking 4,575 rows…", the server
limit is 1,200 s), but a full-roster round trip is a coffee-break wait. Suggest for P2: let
the sheet carry only the topics a person picked (already the case) and default to fewer
topics, or have the peek skip cells whose text equals the exported label before evaluating.

**What that timing run found (fixed, deployed as 19.0.1.0.1):** the untouched full sheet came
back as **9,933 "changes"** — Working Hours 3,045, Department 3,025, Working Schedule 3,017,
Manager 423, Coach 423 — plus 1,499 rows matching nobody. Cause, in the desk: a named
reference is resolved by NAME (`_coerce`, `=ilike`, `limit=1`), so (a) where two records share
a name (calendars, namesake people) a *different* record is proposed, and (b) a department's
full path ("Management / Professional Services") finds nothing and is proposed as a NEW
department. Applying that untouched sheet would have re-pointed thousands of people and
created departments. Updates now treats a cell whose text equals what is shown on record
today as "stays the same" and never sends it (server and screen). After the fix: the same untouched 4,575-row sheet reads **0 changes, 60,074 cells staying the same** (review 71.4 s).
The 1,499 unmatched rows are honest: people with no employee code whose name is shared
("2 people called … — add the employee code").

## R5. Self-review

**§3 non-goals — all respected.** No dates, pay history, `CLEAR`, scheme-aware components,
one-off items, split approval, bank second check, new joiners (an unmatched row is bound or
skipped, never created), drafts, pay run changes or importer retirement. Two start tiles,
no paste tile. `_write_cell`, `_evaluate`, `_coerce`, `_io_match`, the approval adapter and
every Records Desk screen are untouched (the diff to `pb_records` is `_io_columns`'
optional fourth return, the new `_io_given_columns`, `_io_open`, `import_columns`, and two
additive keys). `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff` not touched,
staged or deployed.

**§4.5 design bar — honest scores (out of 5):**

| Bullet | Score | Why |
|---|---|---|
| Hero moment | 4 | The review sentence + grid is the centre: before struck through above after, colour by outcome, counts that move as you fix. Not 5: on a 4,500-row file the wait before it appears is long. |
| Zero dead-ends | 4 | Empty history, unreadable file, headings-only, no identity / no value column, unmatched rows, refused cells, no write permission, no export permission, 10,000-row cap, approval pending, write-time refusals, nothing-to-change — all designed with a next step. Not 5: a failed network call during review falls back to a generic sentence. |
| Plain language | 5 | No model names, card ids or codes on screen; every sentence counted in the right number; Vietnamese for all 273 strings. |
| Motion with purpose | 4 | View enter, fix-row open, cell "settles" green after a fix, apply progress, done-icon pop; all off under reduced motion. |
| Keyboard + bulk | 4 | Fixable cells are focusable, Enter opens, Esc closes and returns focus, Enter in the fix input checks, arrow keys + Enter in the person finder; filter chips with counts; "only columns with changes" by default; 150-row pages. Not 5: no "leave out all cells like this" bulk action yet. |
| Best in class | 4 | Matches the patterns in the prototype's research (ready-to-fill sheet, any-layout matching remembered, colour-coded before/after, fix on screen, named history, undo). Undo and the "text equal to today is no change" guard go beyond most. |

## R6. Deviations from the handover, and why

1. **`matched` carries a fourth key `cells`** (how many of `changes` the row produced). The
   grid needs to slice `changes` back into file rows, and the same person on two consecutive
   rows made any other slicing ambiguous. Additive; existing callers ignore it.
2. **`review` reshapes refusals and look-alike changes** — a refused or `ok` cell whose file
   text equals what is shown on record today is "same" and not sent (ledger G4, G11). The
   desk is unchanged; this is the front door refusing to send what the person did not change.
3. **Read-only fields are not offered** in the sheet or the "Goes to" list (they could never be
   changed; ledger G4). Topic counts are therefore 56 / 17 / 4 on payobook rather than 57 / 18.
4. **A heading that reads like the name/code/email field is proposed as "finds the person"**
   (ledger G5), not as a value to write.
5. **`apply` takes an optional `stats` dict** (`rows`, `unmatched`, `left_out`) from the screen
   for the history counts, instead of re-parsing the file a second time on the server. Display
   only; the desk still re-evaluates every change.
6. **`apply` calls the desk first and creates the batch only when an apply exists**, instead
   of creating then deleting it — HR users have no delete right on batches (mirrored ACL), and
   the outcome ("no batch left behind") is the same in one transaction.
7. **ACL adds `pb_records.group_records_editor`** (read/write/create) on both new models: an
   editor may apply through the desk (which creates its apply under sudo), so without this row
   the batch create would refuse them.
8. **`download_sheet` renames the file** to "Payobook update sheet <date>.xlsx" (the desk names
   it after a pay scheme, which a Master-records sheet does not have).
9. **Grid paging and column folding** (150 rows per page; only columns with something
   happening, "Show all N columns" to widen) — needed for a 4,500-row, 70-column file.
10. **Default filter** is "With changes" when the file has more than 300 rows, else "Everyone".
11. **Bank details are not pre-picked** on the start screen, so a sheet sent around carries no
    account numbers unless asked for.
12. **Live browser walk was read-only** — see §8 item 1.

New gotchas → ledger G4–G11.

## R7. What Phase 2 needs to know

**How a person resolves to a pay scheme today.** Not through the contract. `hr.contract.struct_id`
(`om_hr_payroll/models/hr_contract.py:53`) points at a legacy `hr.payroll.structure`, and
`hr.formula.config.structure_id` (`pb_hr_payroll_formula/models/formula_config.py:158`) is
documented as interop only — "a structure alone does not identify a configuration". The live
answer is the scheme map: `pb.scheme.map.resolve_many(employee_ids, cycle_type, on_date)`
(`pb_scheme_map/models/pb_scheme_map.py:339`; single-person `resolve` at `:274`), a ladder of
rungs (segment employments via `pb_workseg`, then department → scheme assignments,
`hr.formula.scheme.assignment`, `pb_hr_payroll_formula/models/formula_scheme_assignment.py:12`,
extended in `pb_scheme_map/models/formula_scheme_assignment.py`), returning
`{config_id, config_name, rung, via}` and never guessing (`rung='none'` + a sentence). The pay
run uses exactly this (`pb_payrun_wizard/models/pb_payrun_wizard.py:321` `_scheme_population`,
called from `_eligible_employees` at `:646`). It is date-aware (`on_date`) and cycle-aware.

**Where a per-person scheme lookup attaches (D5).** In `pb.updates.desk.review`
(`pb_updates/models/updates_desk.py`), right after the matched people are known
(`_people_info`): one `resolve_many` call for all matched ids gives each person's scheme; the
scheme-aware catalogue is then `Desk._cards(config_id)` per scheme present (the desk already
supports scheme mode), and a `c:<CODE>` cell for a person whose scheme lacks that rule becomes
the greyed "not in their pay scheme" status. `read_columns` would offer, besides the Master
catalogue, the component cards of the schemes present in the file (same call, on the
identity column's matches). The writes still go through `apply_changes(0, …)` — the
`c:<CODE>` card is global by code (fact U11).

**Where a "Starts from" date attaches.** (1) As a column role: `_io_given_columns`
(`pb_records/models/pb_records_io.py`) already carries person-finding roles beside value
columns; a `date` role (`'identity': {'starts': idx}` or a separate key) would be read per row
in `import_peek` next to code/name/email and travel on each change. (2) On the write: today
`_write_cell` writes in place, immediately; a dated change needs a pay-history entry model and
a scheduled apply for future dates, which is a NEW write path in the desk (owner decision D2:
one contract + dated history) — `_write_cell` and `apply_changes` are where it lands, so P2 is
the first phase that must change the desk's write side. (3) On screen: a "Starts from" column
in the review grid and a per-update default on the Apply step.

## 8. Needs an owner decision / owner action

1. **The QA login was refused on payobook.com** (user 6672 active, no two-step check, last
   changed 2026-10-27). An agent may not reset it or sign in with a typed password on the
   live host, so the live walk was done read-only through the browser's existing session
   (Mitchell Admin). Nothing was applied on live. **Please reset the QA password** (and update
   the memory note) if live write walks by an agent should continue.
2. **The desk's name look-up for named references is ambiguous** (R4): working hours, schedules,
   departments (full path vs. short name → would create a new department), managers and
   coaches. Updates now guards the "untouched" case, but a *typed* value that names a
   namesake still goes to whichever record the desk finds first, and the Records screen's own
   import has the same exposure. Recommend a desk fix (refuse an ambiguous name; match a
   department on its full path; scope look-ups to the company) as its own small piece of work.
3. **Review speed on a full roster** (87 s for 4,575 × 70). Fine for normal use (a few hundred
   rows, a few columns: about 1 s locally); worth a desk performance pass before P3 makes Updates
   the only door for lasting changes.
4. **`sudima`** (a live tenant outside the deploy set) does not have `pb_updates`. Per the
   tenant module rule it should get it; not done because the deploy set was fixed at four.
5. Pre-existing `pb_records` test failure (R1) needs its expectation updated by the
   `pb_records` owner.
