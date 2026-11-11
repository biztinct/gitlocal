# UPDATES — Phase 1 handover: the front door

Read first: `docs/handovers/updates/UPDATES_LEDGER.md` (decisions, standing rules, verified
plumbing facts U1–U12 — **do not re-derive them**), then open
`docs/design/updates-desk-prototype.html` in a browser: it is the visual and interaction
reference for every screen below.

## 1. Goal

A payroll or HR officer opens **People › Updates**, downloads a sheet that already holds
today's values (or drops a file of their own with their own headings), matches the columns
once, sees every change as before → after in a person × column grid, fixes problems on
screen, names the update and applies it. The update appears in a history list with the
original file kept, and can be undone.

All evaluation, writing, audit, approval routing and undo are done by the existing
`pb.records.desk`. Phase 1 writes **no** new write path.

## 2. Scope

1. `pb_records` — two additive seams (§4.1). Version `19.0.1.8.3` → `19.0.1.8.4`.
2. New module `pb_updates` `19.0.1.0.0` — server facade, two stored models, OWL client
   action, People hub lens, vi_VN translation, tests.

## 3. Binding non-goals (later phases — do not build, do not stub with dead buttons)

- "Starts from" dates, future-dated changes, pay history entries, `CLEAR` (P2).
- Scheme-aware component offering and greyed "not in their pay scheme" cells (P2). Phase 1
  runs in Master records mode (`config_id = 0`, fact U1) and offers exactly the cards the
  desk offers there.
- One-off pay items into a pay month (P2).
- Splitting an update into person / pay / bank applies, bank second check (P3).
- New joiners; an unmatched row is bound by hand or skipped, never created (P3).
- Saved drafts (P3). Pay run changes of any kind (P3). Retiring any existing importer (P3).
- "Paste from a spreadsheet" start tile (later). Show two start tiles, not three.
- No change to `_write_cell`, `_evaluate`, `_coerce`, `_io_match`, the approval adapter or
  any Records Desk screen. Existing `pb_records` tests must pass unchanged.
- Do not touch `pb_lifecycle`, `pb_hiring`, `pb_me_expense`, `pb_timeoff` (another session).

## 4. Architecture

### 4.1 Seams in `pb_records/models/pb_records_io.py` (additive)

**(a) `import_peek(..., columns=None)`** — new optional keyword. When `columns` is given it
replaces the result of `_io_columns` (U4):

```python
columns = {'used': {"3": "f:hr.employee:job_title", ...},   # 1-based column index → card id
           'identity': {'code': 1, 'name': 2, 'email': 0}}  # 0 / missing = not present
```

- Keys arrive as strings over JSON-RPC: coerce to `int`.
- A card id not in `self._cards(config_id)` is dropped into `ignored` (by heading), never raised.
- The same card id on two columns: the first wins, the second is ignored.
- Everything after that line is the existing body, unchanged.
- Also add to the success return: `'matched': [{'row': offset, 'emp_id': id, 'method': m}]`
  in file order, so a grid can show rows in the file's order with its row numbers. Existing
  callers ignore the extra key.
- Extract the parse prologue (guard → read → drop blank rows → header checks,
  `pb_records_io.py:733-762`) into `_io_open(file_b64, filename)` returning
  `(refusal_dict_or_None, header, rows, comments, meta, name)` and call it from both
  `import_peek` and (b). Same sentences, same order.

**(b) `import_columns(config_id=0, file_b64='', filename='')`** — reads only. Returns

```python
{'ok': True, 'filename': name, 'rows': <data row count>,
 'columns': [{'idx': 1, 'head': 'NIK', 'samples': ['ID-0102', 'ID-0118', 'ID-0125'],
              'field_id': '', 'identity': 'code', 'how': 'identity'}, ...]}
```

`how` ∈ `'id'` (header comment or `_payobook` sheet), `'label'`, `'identity'`, `''` (unplaced).
Samples: first three non-blank values of the column through `_io_text`. Blank headings are
omitted. Failure contract identical to `import_peek`: `{'ok': False, 'msg': …}`.
To know *which* of the five ways placed a column, either extend `_io_columns` with an
optional fourth return (keep the 3-tuple for existing callers — e.g. a `with_how=False`
kwarg) or derive it afterwards; do not change its placement order.

### 4.2 `pb_updates` server

`pb_updates/__manifest__.py`: depends `pb_records`, `pb_people_hub`, `pb_import_kit`, `web`.
Category/author/licence as `pb_records/__manifest__.py`. No "Odoo" in `name`/`summary`.

**`pb.updates.batch`** (stored, `_order = 'id desc'`) — one named update.

| Field | Type | Note |
|---|---|---|
| `name` | Char required | what the user typed, e.g. "November pay changes" |
| `company_id` | M2O res.company, required, default `env.company` | |
| `user_id` | M2O res.users, default `env.user` | |
| `date` | Datetime default now | |
| `filename` | Char | |
| `attachment_id` | M2O ir.attachment, ondelete set null | original file, `res_model='pb.updates.batch'`, `res_id=batch.id` |
| `apply_ids` | O2M `pb.records.apply` via `updates_batch_id` | add `updates_batch_id` (M2O, index, ondelete set null) by `_inherit = 'pb.records.apply'` |
| `rows_total`, `rows_unmatched`, `values_refused` | Integer | what was left out, for honest history |

State is computed on read from the applies (not stored): `pending` if any apply is pending;
`undone` if all are undone; `applied` if all applied; `rejected`/other desk states pass
through with the desk's own `state_label`.

**`pb.updates.layout`** (stored) — remembered column matching, per company.

| Field | Type |
|---|---|
| `company_id` | M2O required |
| `fingerprint` | Char index — `sha1` of the normalised headings joined by `\x1f` |
| `map_json` | Text — `{normalised heading: target}`; target = card id, `identity:code|name|email`, or `ignore` |
| `use_count`, `last_used`, `user_id` | |

`models.Constraint('unique(company_id, fingerprint)', …)` (ledger G1). Normalise with the
same `_norm` the desk imports (`pb_records_io.py`, top of file) so a heading means the same
thing in both modules.

ACL: mirror `pb.records.apply` rows in `pb_records/security/ir.model.access.csv` (HR user,
payroll officer: read/write/create; system: all; `group_records_viewer`: read). Multi-company
record rules on both models (`['|',('company_id','=',False),('company_id','in',company_ids)]`).

**`pb.updates.desk`** (`models.AbstractModel`, RPC facade; every public method starts with
`self.env['pb.records.desk']._check_read()`; `Desk = self.env['pb.records.desk']`).

| Method | Does |
|---|---|
| `get_home()` | `{can_write, can_export, people_count, topics, history}`. `topics` = `Desk.get_fields(0)['groups']` relabelled: employee → "Personal and job details", contract → "Contract", bank → "Bank details", component → "Ongoing pay items"; each with its field ids and count. `history` = `get_history(8)`. |
| `download_sheet(topic_keys, filters=None)` | field ids of the picked topics → `Desk.export_records(0, filters or {}, field_ids, 'data')`; return its answer untouched. |
| `read_columns(file_b64, filename)` | `Desk.import_columns(0, …)`, then for each column with no placement: (1) the company's layouts, newest first — exact fingerprint first, then any layout that knows this normalised heading → `how='memory'`; (2) a guess: `difflib.SequenceMatcher` ratio ≥ 0.86 between the normalised heading and a card label → `how='guess'`. A remembered or guessed card id that is no longer in the catalogue is dropped. Returns the columns plus `fields` (the same grouped catalogue as `get_home`, for the drop-down) and `layout_known` (exact fingerprint hit). |
| `review(file_b64, filename, columns)` | `Desk.import_peek(0, file_b64, filename, columns=columns)` reshaped for the grid (§4.3). Writes nothing. |
| `recheck(changes)` | `Desk.preview_changes(0, changes)` — after an on-screen fix or a hand-bound row. |
| `apply(name, file_b64, filename, columns, changes)` | In one transaction: refuse a blank name; create the batch; store the file as an attachment; upsert the layout (headings → targets, `use_count += 1`); `answer = Desk.apply_changes(0, changes, note=name, source='import')`; link `answer['apply_id']` to the batch when non-zero; if `apply_id` is 0 (nothing to change) delete the batch again and say so. Return the desk's answer plus `batch_id`. The browser's `changes` are trusted no more than the desk trusts them: `apply_changes` re-evaluates (U6). |
| `get_history(limit=20)` | batches of the active companies, each with name, user, date, filename, people, values, state, state label, `with_whom`, `can_undo`. |
| `undo(batch_id)` | for each applied, not-undone apply: `Desk.undo_apply`; sum `restored`, `skipped_changed_since`, `skipped_missing`. Company-scope the batch first. |
| `lookup_people(term)` | passthrough to `Desk.lookup_people`. |

`can_undo` = batch has ≥ 1 apply that is applied and not undone, and the user may write
employees or contracts.

### 4.3 The review payload

```python
{'ok': True, 'filename': …,
 'summary': {...the desk's summary...},
 'columns': [{'field_id', 'label', 'group'}],            # in file column order
 'rows': [{'row': 7, 'emp_id': 12, 'name': 'Ayu Pratiwi', 'code': 'ID-0102',
           'cells': {'<field_id>': {'old': '9,200,000', 'new': '9,800,000',
                                    'status': 'ok'|'same'|'refused', 'why': '', 'value': <raw>}}}],
 'unmatched': [{'row', 'code', 'name', 'email', 'why', 'values'}],
 'changes': [...]}                                         # what apply will send back
```

Built from `matched` + `items` (keyed `(emp_id, field_id)`) + `changes`. A matched row's cell
with no item was blank in the file: omit it — the grid shows nothing there.
Two file rows that match the same person: keep both rows in the grid; the desk already
judges the resulting duplicate changes — report what it does (report-back R3).

### 4.4 Client (`pb_updates/static/src/`)

- Client action tag `pb_updates_desk`, action record `pb_updates.action_pb_updates_desk`
  named **Updates** (a named record, not a bare tag — see the comment in
  `pb_records/views/pb_records_action.xml`).
- Bolt onto the People hub as lens `updates`, directly after `records`: clone how
  `pb_records` registers its lens in the `pb_people_hub_lens` category (U10; find the
  registration in `pb_records/static/src/js/records_desk.js`) including its group gate —
  gate on `pb_records.group_records_viewer` plus the same HR / payroll officer groups the
  desk's `_may_read` accepts. Add a ⌘K palette entry the way
  `pb_records/static/src/js/records_palette.js` does.
- One OWL root with a `view` state: `home` → `start` → `match` → `review` → `apply` → `done`.
  Files: `updates_desk.js`, `updates_review.js` (grid), `updates_desk.xml`,
  `updates_desk.scss`. Icons: `import { ic } from "@pb_import_kit/js/import_icons"` (U12);
  add missing Lucide paths to that map only if absent (additive).
- File reading: clone `RdDropZone` behaviour (`pb_records/static/src/js/records_import.js:116-180`)
  — base64 in the browser, `orm.call`. Download: clone how the desk's file menu turns the
  `export_records` answer into a browser download.

Screens (copy the prototype's wording; it is already in screen language):

1. **Home** — light-tint hero "Update many people at once" + primary "New update"; two
   tiles ("Download a ready-to-fill sheet", "Upload your own file"); "Past updates" list
   with state chip, people/values counts, who, when, and **Undo** where `can_undo`.
   Empty history: a designed empty state naming what will appear.
2. **Start** — topic toggles (from `get_home().topics`, with field counts), people count,
   "Download the sheet", and the drop zone. No "for whom" filter in P1 beyond everyone the
   user can see (`filters = {}`); say "Everyone you can see (N)".
3. **Match columns** — one row per file column: heading, up to three sample values,
   "Goes to" select grouped by "Finds the person" (Employee code / Employee name / Work
   email), then the catalogue groups, plus "Don't bring this column in"; a chip saying how
   it was matched ("From a Payobook sheet", "Remembered from last time", "Matched by name",
   "Best guess. Please check" with a "Looks right" button, "Not brought in"). Continue is
   refused in a sentence when no column finds the person or no column carries a value.
   If every column is placed by `id` (a Payobook sheet), skip this step straight to Review
   and say so in a line above the grid, with a "Change the matching" link.
4. **Review** — the hero sentence ("This file will make **N changes** for **M people**. K
   cells need your attention." / "Everything checks out."); filter chips with counts
   (Everyone / With changes / Needs attention / Nothing to change); the grid: sticky person
   column, before struck through above the new value, colour by status (change, refused,
   same), legend. A refused cell is clickable: an inline row shows the desk's `why` and
   offers **Type a different value** (input → `recheck` for that one change → cell updates)
   and **Leave this one out**. Unmatched rows sit in their own band above the grid with the
   desk's `why`, a "Find person…" typeahead (`lookup_people`) that binds the row and
   rechecks its values, and "Skip this row". Footer: Back, and **Continue** — enabled when
   at least one change is `ok`; if refused cells or unmatched rows remain, the button reads
   "Continue without the K that need attention" (they are simply not applied; say so).
5. **Apply** — name input (required, prefilled "<Month YYYY> update"), three count rows
   (people, values, left out), the reassurance note about undo, primary "Apply N changes"
   with a busy state; on answer: **Done** — "N changes are in for M people" or, when
   `pending`, "Sent for approval — with <with_whom>" and the route steps; list anything the
   write itself refused (`refused`); "Back to Updates" and "Undo this update" (hidden when pending).

States that must be designed, not left to chance: loading veil with the row count
(`import_probe`), unreadable file (the server's sentence), headings-only file, 10,000-row
truncation notice, no permission to write (grid still reviewable, Apply replaced by a
sentence), no permission to export (download tile explains), narrow widths (grid scrolls
inside its own container; the page never scrolls sideways).

### 4.5 Design bar (binding, owner's words)

**"Extreme WOW, intuitive, out-of-this-world experience, best in class."** Every surface must have:
- a **hero moment** — here: the review grid and its one plain sentence;
- **zero dead-ends**: every state (empty, loading, error, partial, huge) is designed, every
  failure names its reason and its next step;
- **plain-language over code vocabulary** on every label, toast and summary;
- **motion with purpose** (enter/exit, progress, state change) — never decorative jitter;
- **keyboard + bulk ergonomics** where rows are involved (the grid's fixable cells are
  focusable; Enter opens the fix row; Esc closes it);
- measured against the best consumer/SaaS tool in the category, not against stock screens.

Palette: primary indigo `#5A4BB0` (hover `#4A3D96`, soft `#EDEAF8`), white cards, border
`#E2E8F0`, success `#2E7D4F`, info `#2563EB`, warning `#D97706`, error `#DC2668`, neutral
`#64748B`; Lucide icons, **never emoji**, no gradients, one solid primary button per bar,
everything else outline or ghost. Reuse `pb_import_kit` tokens where they exist.

**White-label**: the word "Odoo" must not appear in any user-visible string. **Plain
language**: no model names, card ids or codes in user-visible sentences.

## 5. Safety rails

- No write before Apply; Apply goes only through `Desk.apply_changes` (whitelist, company
  scope, ACL, audit, approval all inherited).
- `pb.updates.desk` never calls `sudo()` on `hr.employee` / `hr.contract` itself.
- The stored attachment is readable only through the batch's ACL (set `res_model`/`res_id`;
  no public URL, no `public=True`).
- `read_columns` and `review` accept the same 10 MB / 10,000-row limits as the desk (they
  call it); do not add a second parser.
- `hr.payslip` is never touched.

## 6. Tests

`pb_updates/tests/test_updates.py` (`TransactionCase`, tagged `post_install`, `-at_install`).
Build fixtures the way `pb_records/tests/test_records_r3_roundtrip.py` does (read it first;
reuse its helpers for making an xlsx/csv in memory).

| # | Case | Expect |
|---|---|---|
| T1 | `import_peek` without `columns` on a desk-exported file | identical result to before the seam (existing R3 tests still green) |
| T2 | `import_peek(columns=…)` on a CSV with foreign headings | changes produced for mapped columns only |
| T3 | `columns` with an unknown card id | that column ignored by heading, no exception |
| T4 | Same card on two columns | first wins |
| T5 | `import_columns` on a desk export | every data column `how='id'`, identity columns `how='identity'`, three samples |
| T6 | `import_columns` on foreign headings | `how=''`, `field_id=''` |
| T7 | `read_columns` after one `apply` with the same headings | `layout_known` true, columns `how='memory'` |
| T8 | `read_columns` with a near-miss heading ("Job Titel") | `how='guess'` on the job title card; a far-off heading stays unplaced |
| T9 | `review` payload | rows in file order with file row numbers; cells carry old/new/status; blank cell absent |
| T10 | Unmatched row | listed with the desk's sentence; never created as an employee |
| T11 | `apply` | batch created, attachment stored, layout upserted, apply linked, employee value changed, answer carries `batch_id` |
| T12 | `apply` with nothing to change | no batch left behind, honest answer |
| T13 | `apply` with a blank name | refused in a sentence, nothing written |
| T14 | `undo` | value restored, batch state `undone`, a second undo is refused in a sentence |
| T15 | `undo` after somebody changed the value since | reported as skipped, their value kept |
| T16 | User with only `group_records_viewer` | may review; apply writes nothing and says why |
| T17 | Second company's user | cannot see the first company's batches or layouts |
| T18 | Component card (`c:<CODE>`) for a person whose contract has no such line | assert and **report** what the desk does (adds the line or refuses) — do not change it |

Also run: the whole existing `pb_records` test suite; a `.po` parse gate on
`pb_updates/i18n/vi_VN.po` (ledger G2); a static check that every JS import path resolves.

## 7. Deploy and verify (tier 3 — new module install)

Follow repo `CLAUDE.md` § Deploy contract exactly. In addition:

1. `ssh Payobook19v2 cat /opt/deploy-notes.md` — if another START has no DONE, wait.
   Append a START line (`sudo tee -a`), take `flock /tmp/payobook-studio-deploy.lock`.
2. Dry-run rsync `pb_records` against the server first: the only differences must be this
   phase's. If the server copy carries someone else's newer work, stop and report.
3. Deploy **only** `pb_records` and `pb_updates`. Back up the four DBs first
   (`pg_dump -Fc` into `/odoo/backups/`).
4. Snapshot active cron counts per DB before; upgrade `pb_records`, install `pb_updates`
   on `payobook`, `payobook_template`, `p0clone`, `rize` (never `abm`) with
   `~/pb_upgrade.sh <db> <module>` or the detached-unit pattern; compare cron counts after
   and switch off anything newly active.
5. Asset purge per DB, start, warm each site with one curl, grep the log for errors.
6. Verify: byte-identical hash of both module trees repo vs server; manifest version ==
   `ir_module_module.latest_version` in all four DBs (normalise the `19.0.` prefix).
7. **Browser validation on `payobook` with Chrome MCP** (QA login — ask the server-side
   notes or memory, never write it to the repo): open People › Updates, read the console
   for errors, then walk: download a sheet → change three cells in it → upload → review →
   apply → see it in Past updates → undo. Then a CSV with made-up headings: match columns,
   apply, upload it again and confirm the matching is remembered. Then one unreadable file
   and one headings-only file. Use existing DEMO people only; undo every change you apply;
   never delete demo data. Screenshots of home, match, review, done into
   `outputs/updates-p1/` (not committed).
8. Append DONE (or FAILED) to `/opt/deploy-notes.md`.
9. Commit with explicit paths only (`pb_records/…`, `pb_updates/…`,
   `docs/handovers/updates/…`, `docs/design/updates-desk-prototype.html`), scan the diff
   for credentials, push `origin 19.1`.

If any step fails: stop, do not improvise on live data, restore from the backup if a
database was left half-upgraded, write what happened in the report.

## 8. Report back — `docs/handovers/updates/UPDATES_P1_REPORT.md`

- R1. Result of every numbered test (T1–T18) and the existing `pb_records` suite, with output.
- R2. Deploy evidence: hashes, versions per DB, cron counts before/after, log grep.
- R3. What the desk does with two file rows for the same person, and with T18.
- R4. Browser walk: what was clicked, console state, screenshots list, anything that felt slow
  (time the review of the largest real file you can make from `rize`-sized data — do not
  apply it).
- R5. Self-review against §3 non-goals and §4.5 design bar — score each bullet honestly.
- R6. Every deviation from this handover and why. Every new gotcha → add a row to the ledger.
- R7. What Phase 2 needs to know: where a "Starts from" date and a per-person scheme lookup
  would attach, and how a contract resolves to its pay scheme today (model + field, file:line).
