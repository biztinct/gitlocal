# UPDATES — Phase 2b handover: pay items by pay scheme, CLEAR, contract tie

Read first: `UPDATES_LEDGER.md` (rules, decisions D1–D8, facts U1–U16, gotchas G1–G19),
then `UPDATES_P2A_REPORT.md` §R3 and §R7. Visual reference:
`docs/design/updates-desk-prototype.html` (the match screen's "Goes to" list grouped by pay
scheme, and the greyed "Not in their scheme" cell on the review grid).

**Design mandate (owner, verbatim): "extreme WOW, intuitive, out-of-this-world experience,
best in class".** Indigo design system (`#5A4BB0`), white cards, Lucide icons through
`@pb_import_kit/js/import_icons` (never emoji, no gradients), one solid primary button per bar.

**White-label rule:** the word "Odoo" never appears in any user-visible string (labels,
tooltips, toasts, errors, `string=`, `help=`, exported sheet text, `.po` msgstr). Technical
identifiers stay as they are. **Plain words on screen:** "pay scheme", "pay item" — never a
model name, card id or rule code in a sentence a user reads.

## 1. Scope

1. **Updates knows each person's pay scheme** and judges every pay-item cell against it
   (decision D5, as corrected in the ledger: the scheme comes from the scheme map, not from
   a contract field).
2. **The pay-item list is complete**: every pay item of every pay scheme in the user's
   companies is offered, not only the ones that already have a line on some contract.
3. **CLEAR**: an explicit way to empty a value from a file (decision D6).
4. **One definition of "this person's contract"** for the sheet and for the check (ledger G16).

Versions: `pb_updates` `19.0.1.0.1` → `19.0.1.1.0`; `pb_records` `19.0.1.8.5` → `19.0.1.8.6`.

## 2. Binding non-goals

- No dates, no "starts from", no future-dated changes, no one-offs (P2c).
- No approval split, no new joiners, no "Pay scheme" column for joiners, no drafts (P3).
- **The Records screen behaves exactly as today.** Its grid, its own import and its Master
  records catalogue do not change. Everything scheme-aware and CLEAR is switched on only by
  `pb.updates.desk` (keyword arguments / an Updates-only catalogue). The only `pb_records`
  behaviour change allowed is item 4 (contract tie), plus opt-in seams.
- No change to `pb.scheme.map`. Read it; never write it.
- G17 (a typed manager name that matches nobody proposes a new employee) is an open owner
  question — leave it as it is.
- No cross-request cache. Review speed on 4,575 × 73 stays ≤ 25 s (A-level proof below).
- Do not touch `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff`,
  `docs/handovers/workflow2`.

## 3. Verified plumbing facts (do not re-derive)

- `pb.scheme.map.resolve_many(employee_ids, cycle_type='any', on_date=None)`
  (`pb_scheme_map/models/pb_scheme_map.py:339`) → `{emp_id: {'config_id', 'config_name',
  'rung', 'via'}}` in a handful of queries for thousands of people; nobody found =
  `_blank()` (`:290`): `config_id` 0, `rung` 'none', `via` "No scheme covers this person
  yet." `via` is already a translated plain sentence fragment ("from Bread's team map").
  The pay run calls it at `pb_payrun_wizard/…/pb_payrun_wizard.py:321`. Cycle words:
  `CYCLE_WORDS` in `formula_scheme_assignment.py`.
- A scheme's pay items = `pb.records.desk._component_rules(config_id)`
  (`pb_records/models/pb_records_desk.py:227`): `hr.formula.rule` rows with
  `is_contract_component` or `is_text_component`, card id `c:<CODE>` (`:367-396`).
- Master records (`config_id = 0`) builds `c:` cards only from templates that already have a
  contract line (`pb_records/models/master_records.py:66-87`) and returns no component rules
  (`:57`). A `c:` card needs either `_rule` or `_template` for `_write_cell`
  (`pb_records_desk.py:1593-1594`: `card.get('_template') or
  probe._get_or_create_advantage_template(card['_rule'], {})`).
- The catalogue row for a pay item is global, keyed by rule code (U11).
- `_coerce` (`pb_records_desk.py:1208`): `''` is already an explicit clear for `f:` fields;
  for a `c:` amount `None`/`''` coerces to `0.0` (`:1228`); text component → `''`.
- `import_peek` skips blank cells (U3); `pb.updates.desk.review` reshapes the peek
  (`pb_updates/models/updates_desk.py:341-470`) and `apply` re-sends the kept changes to
  `desk.apply_changes(0, …)`, which re-evaluates server-side.
- Contract choice: the sheet uses `_io_contracts` (`pb_records/models/pb_records_io.py:207`,
  highest id on a start-date tie); evaluation uses `probe._get_latest_contract`
  (`pb_records_desk.py:749, 1399, 1789, 1975`, lowest id on a tie). The pay run's batch uses
  `_get_latest_contract` (`payroll_import_batch.py:1639`).
- `pb_updates` depends on `web`, `pb_records`, `pb_people_hub`, `pb_import_kit`; it does
  **not** depend on `pb_scheme_map`.

## 4. Item 1 + 2 — pay items by pay scheme

### 4.1 Where the scheme knowledge lives

A new small helper on `pb.updates.desk` (new file `pb_updates/models/updates_schemes.py`):

- `_scheme_items(desk)` → `{config_id: {'name', 'codes': set(CODE)}}` for every scheme
  the desk's `_configs(0)`/`_config_domain()` lets this user see, from
  `desk._component_rules(config_id)`; one search for all schemes, not one per scheme.
- `_people_schemes(emp_ids)` → `{emp_id: {'ids': set(config_id), 'name', 'via'}}`.
  A person can be paid under more than one scheme (monthly + an off-cycle scheme), so
  resolve with `cycle_type='any'` AND once per cycle type that the scheme map actually has
  rows for, and union the `config_id`s. `name`/`via` come from the `'any'` answer (or the
  first non-blank one). `ids` empty = nobody could say which scheme pays them.
- If `'pb.scheme.map' not in self.env` (module absent): every person has empty `ids`.
  Check on the five databases whether `pb_scheme_map` is installed everywhere; if it is,
  add it to `pb_updates` `depends` and drop the soft check; if not, keep the soft check and
  say so in the report.

### 4.2 The verdict for one pay-item cell

For a matched person and a `c:<CODE>` column, **before** the desk's verdict is shown:

| Person's schemes | Code in any of them? | Result |
|---|---|---|
| known | yes | the desk's verdict, unchanged |
| known | no | new status `off_scheme`: greyed, never sent, never counted as a problem |
| unknown (`ids` empty) | — | the desk's verdict, unchanged, plus a quiet flag `no_scheme` on the ROW (not the cell) |

`off_scheme` cell payload: `{'status': 'off_scheme', 'old': …, 'new': <file text>,
'value': …, 'why': "<Name> is paid under <scheme name> (<via>), which has no <pay item>."}`.
Exception: when the person ALREADY has a line for that code on their contract (a value was
kept there earlier), it is not `off_scheme` — the desk's verdict stands, because the value
is real and visible on their contract today.

Enforce it twice: in `review`/`recheck` (what the screen shows) and in `apply` (filter the
changes again server-side with the same helper before `desk.apply_changes`; a change dropped
there is reported in the answer as skipped, never silently lost and never an error).

### 4.3 The complete pay-item catalogue (Updates only)

`pb.updates.desk._catalogue` today relabels `desk.get_fields(0)`. Give the desk an opt-in
seam so Updates can ask for Master records **plus every pay item of every visible scheme**:
e.g. a context key or keyword read in `MasterRecords._cards` (`master_records.py:64`) that,
when set, also adds a `c:<CODE>` card (with `_rule`) for each `_component_rules` row of each
visible scheme whose code is not already a card. First rule by id wins for label and
text/amount kind, the same tie-break the desk uses. The Records screen never sets the key,
so its catalogue is byte-identical to today (test B10). The same key must be in force for
`import_peek`, `preview_changes` and `apply_changes` calls made by Updates, or a column
matched to a new card would be dropped by `_whitelist`.

Each pay-item row in the Updates catalogue gains `schemes: [{id, name}]`.

### 4.4 Screens

- **Match columns — "Goes to" list.** Pay items are grouped by pay scheme, as the prototype
  shows: one group per scheme for items that belong to one scheme, and a group "Used by
  several pay schemes" (each item once, with the scheme names as its small second line).
  Groups for schemes that pay nobody in THIS file sort last under a divider "Other pay
  schemes". `read_columns` therefore returns, alongside what it returns today, the schemes
  present in the file with head-counts (resolve the matched people once). One quiet line
  under the list header: "Each person's pay scheme is worked out for you, the same way a
  pay run does it." Search inside the list must still work across groups.
- **Review.**
  - A slim strip above the grid: "Pay schemes in this file" with one chip per scheme and
    its head-count ("Monthly staff · 9"), plus "No pay scheme yet · 2" when any; clicking a
    chip filters the grid to those people (same filter behaviour as the existing status
    filters). Shown only when the file has at least one pay-item column.
  - `off_scheme` cells: grey fill, the file's value in muted text with a small Lucide
    `ban`/`circle-slash` icon, tooltip = the `why` sentence. Not editable on screen. A new
    counter beside the existing ones: "Not in their pay scheme · N" (grey, never red; it is
    not "needs attention"). The primary button's count excludes them.
  - A row whose person has `no_scheme` shows a small amber dot on the person cell with the
    tooltip "No pay scheme covers this person yet. Pay items are still saved on their
    contract." — no blocking.
  - The person cell's existing second line gains the scheme name when the file has a
    pay-item column (muted, truncates with ellipsis; no layout shift when absent).
- **Done screen / Past updates.** The summary line says how many values were skipped as
  not in the person's pay scheme, when > 0.
- **Download sheet** (pay-items topic): columns = the complete catalogue of §4.3 limited to
  the schemes of the people being exported; a cell for a person whose schemes do not have
  that item gets a light grey fill and stays blank. One line on the sheet's existing
  notes/instructions area explains the grey cells and CLEAR. If the exporter has no
  per-cell style hook reachable in < ~40 lines, skip the grey fill, keep the note, and
  report it.

## 5. Item 3 — CLEAR

- A cell whose trimmed text is exactly `CLEAR` (any case), or the translated word
  `_("CLEAR")`, means "empty this value". Only Updates turns it on: add an optional keyword
  to `import_peek` (default off) that turns such a cell into a change with `value = ''`
  instead of skipping it. The Records screen's own import keeps treating `CLEAR` as text.
- Verdicts (verify each against `_coerce`; add the refusal where the desk has none):
  - `f:` text / date / number / selection / named reference: emptied; refused in a sentence
    when the field is required on the record ("<Label> cannot be empty.").
  - `c:` amount: becomes 0, shown as "0" with the old value struck through; `c:` text: emptied.
  - `b:` (bank): refused — "Bank details cannot be removed from a file. Change them on the
    employee record." (bank second check arrives in P3.)
  - Columns that find the person (identity): `CLEAR` there is a row that matches nobody —
    existing unmatched handling, no special case.
- Review shows a cleared cell with the old value struck through and the word "Cleared"
  (Lucide `eraser`), counted with the changes. The P1 "file text equals what is on record"
  guard must not swallow it: clearing an already-empty value is `same`.
- Undo restores the earlier value (existing `undo_apply`; prove it in B8).

## 6. Item 4 — one contract definition (G16)

Make `_io_contracts` pick exactly the contract `_get_latest_contract` picks, including the
tie (same start date → the one evaluation uses). Do not change `_get_latest_contract`: the
pay run reads through it. Keep `_io_contracts` batched (no per-person search).

## 7. Tests (numbered)

Fixtures: reuse the persistent demo schemes (memory note `demo-payroll-test-fixtures`); no
"ZZ" records; no "RIZE" in any demo name.

| # | Case | Expect |
|---|---|---|
| B1 | Two schemes mapped to two teams, item X only in scheme 1; file sets X for a person in each | scheme-1 person `ok`; scheme-2 person `off_scheme` with the sentence naming their scheme; not in `changes` |
| B2 | Scheme-2 person already has a contract line for X | desk's verdict stands (not `off_scheme`) |
| B3 | Person no scheme covers | desk's verdict stands; row flagged `no_scheme` |
| B4 | Person covered by a monthly scheme and an off-cycle scheme; item only in the off-cycle one | `ok` |
| B5 | `apply` called directly with an off-scheme change (bypassing the screen) | change dropped, reported as skipped, nothing written |
| B6 | A scheme's pay item with no contract line anywhere | offered in "Goes to"; a file column matched to it writes a new line for an in-scheme person |
| B7 | `read_columns` | returns schemes present with head-counts; pay items carry `schemes` |
| B8 | CLEAR on a text field, a date, a named reference, a `c:` amount, a `c:` text; apply; undo | emptied / 0; undo restores every earlier value |
| B9 | CLEAR on a required field and on a bank column | refused with the two sentences |
| B10 | Records screen: `get_fields(0)`, `import_peek` of a file containing `CLEAR`, Master catalogue | identical to before this phase (capture before, compare after) |
| B11 | Two contracts with the same start date | sheet and evaluation use the same contract; untouched sheet = 0 changes |
| B12 | `pb.scheme.map` absent (only if the soft check is kept) | no cell is `off_scheme`; nothing breaks |
| B13 | Full suites | `pb_records` 94/94 or more; `pb_updates` 27/27 plus the new ones; P2a golden comparison still identical |
| B14 | Speed, local copy of the large roster, 4,575 × 73 | review ≤ 25 s, sheet ≤ 20 s warm; report the cost of the scheme resolve on its own |
| B15 | `vi_VN.po` parse gate (G2, G6) and a scan of every new user-visible string for the word "Odoo" | clean |

Test runs on the live box: after the service is started, on free `--http-port` /
`--gevent-port` (G19). Local runs from an isolated snapshot (G13).

## 8. Browser validation (mandatory)

On a local copy, through Chrome MCP with the console read at every step: match screen with a
file that has people from at least two schemes (grouped list, search, the head-count
groups), review (scheme strip filter, greyed cells and tooltip, amber dot, Cleared cells,
counters, button count), apply, done line, Past updates, undo. Screenshots into
`outputs/updates-p2b/` (never committed). Check at 1280 and 1440 widths; nothing in the grid
may shift when the scheme line is present or absent.

## 9. Deploy and live check

Tier 2 (Python + JS/SCSS, no stored-data change) on all five: `payobook`,
`payobook_template`, `p0clone`, `rize`, `sudima`. Never `abm`, `pbf_preview`,
`recruit_connect_20261023`.

1. `/opt/deploy-notes.md`: read, wait on anyone's open START, append START, take the flock
   `/tmp/payobook-studio-deploy.lock`.
2. Clean staging dir; dry-run rsync of `pb_records` and `pb_updates` — only this phase's
   differences may show. Per-module scoped `rsync -a --delete` into
   `/odoo/odoo-server/addons/<module>/`; never `--delete` into the addons root.
3. Stop; upgrade both modules on all five; cron-count snapshot before/after (memory note
   `cron-snapshot-boolean-trap`), switch off anything newly active; asset purge per
   database (`DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'`); start. **Run no
   tests inside the stopped window** (G19). Keep the stop as short as possible.
4. Warm each site with one curl; grep the log; byte-identical hashes for both modules;
   manifest version == `latest_version` on all five.
5. Live check on `payobook`: server-side as the QA user (the same method as P2a — an agent
   does not sign in with a password on a live host): a file with DEMO people from two
   schemes, one in-scheme pay item change, one off-scheme value, one CLEAR on a text field;
   review → apply → Past updates → undo → prove every value is back. Then look-only in the
   browser through the existing session: People › Updates opens, Past updates shows the
   check as undone, console clean. Same look-only check on `sudima`. Never apply anything
   on `rize` or `sudima`. Never delete demo data.
6. Append DONE/FAILED to `/opt/deploy-notes.md`. Commit per feature with explicit paths
   (this handover and the ledger included), credential scan, push `origin 19.1`. The QA
   password appears nowhere in the repo, the report, a commit message or the deploy notes.

Usage-limit rule: on a 429 or at 97 %, commit work in progress with a `PAUSED` note in the
report and stop cleanly.

## 10. Report back — `UPDATES_P2B_REPORT.md`

- B1–B15 with output; timings; screenshots list.
- Deploy evidence for five databases; cron counts; log grep; downtime in minutes.
- The live check, step by step, with proof of restoration.
- Deviations and why; new gotchas added to the ledger.
- For Phase 2c (answer from the code, file:line):
  1. Which pay-run mode each of the five databases' active schemes actually uses
     (application-data, monthly-template pay file, plain pay file) — a table of scheme →
     mode → which one-off store that mode reads (P2a report §R7.4), so P2c can choose ONE
     store to write one-offs into.
  2. Whether `hr.payroll.period.input` rows can be created for a period that has no pay
     run yet, and what a run does on finding approved rows (call chain).
  3. What `pb.records.apply` needs for a "Scheduled" state: the selection at
     `records_approval.py:59`, every place that switches on `state`, the history screens
     that render it, and whether `undo_apply` can cancel an apply that has not been written.
  4. Whether proration / automatic back pay (`formula_config.py:80/:102`) is switched on
     for any scheme on the five databases today.
