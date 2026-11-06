# CLEANMAP P1 — the Spreadsheet board's left list obeys FROM

**Status: DESIGNED, NOT STARTED.** Read `CLEANMAP_LEDGER.md` first — including
its "DO NOT START" section. Anchors below were true at `cdefe5439`,
`pb_formula_studio 19.0.1.196.0`; re-verify by symbol name.

## 1. The owner's report (2026-09-19, rize.payobook.com)

> FROM says "Rize Vietnam Payroll · August 2026 — pay data" but shows 180
> fields. It never had so many. And I still see Salary|A, A, Salary|B, B
> although you fixed that. I want to see only what corresponds to the FROM
> value at the top left.

Screenshot facts: FROM = a pay run, "180 fields"; cards `Salary|A` (e.g. RIZ002),
`A` (e.g. RIZ002), `Salary|B`, `B` (e.g. Nguyễn Anh Đào), `Salary|C`…; file strip
says "43 columns"; 42 mapped + 1 suggested.

## 2. Root cause (verified in code — do not re-derive)

Two independent defects that multiply.

**2a. The left list is a union, and FROM only fills one lane of it (CM2).**
`pb.formula.studio._import_left_columns` (`models/pb_formula_studio.py` ~8773)
always emits, in order:

1. the scheme's stored template file — `_import_sample_columns(config)`, the
   `preferred` entries;
2. the FROM batch's columns — `_column_alias_fold(cols)`;
3. "Already used by this scheme" — every `source_binding == 'excel'` key;
4. "From this scheme's history" — every `data_source_field`;
5. `_pay_run_lane(batch, config)` — the six period codes.

A `seen` set dedupes by exact key only, so `Mã nhân viên (Code)` from lane 1 and
`Salary|Mã nhân viên (Code)` from lane 2 are both drawn.

**2b. The alias fold does not understand a multi-sheet pay run (CM1).**
`_load_multisheet_data` (`pb_hr_payroll_formula/models/payroll_import_batch.py`
~1096, the `base_row[...]` block) stores FOUR names per column, in this order:
every `heading` + `Sheet|heading` first, then per column `Sheet|A` + `A`.
`_column_alias_fold` walks positionally expecting `heading, A, heading, B…`
(the single-sheet `_raw_data_from_row` shape), so on this shape it folds almost
nothing. `tests/test_runsrc_left_columns.py::test_05_multisheet_dict_rows_are_untouched`
pins that on purpose — RUNSRC A left it as a known gap. Rize's workbook is
multi-sheet. 43 × 4 = 172, + 6 period cards + stragglers ≈ 180.

Note the writer itself clobbers a heading literally named like an in-range
column letter on this shape (`base_row[col_letter] = value` overwrites), and
skips blank headings entirely (`if not col_letter or not header_value: continue`).
So on the multi-sheet shape a letter-shaped key whose column index is below the
sheet's heading count is ALWAYS an alias. That makes the fold decidable.

## 3. Scope

1. **FROM governs the left list.** Exactly one file source is on screen at a
   time — the one named in FROM.
2. **A fold that understands both storage shapes**: one card per real column.
3. **Every wire keeps a card** (CM3) by re-pointing through an alias map; one
   small honest lane for bindings this file does not contain.
4. **The template file becomes a FROM entry**, so it stays reachable now that it
   is no longer always-on.
5. The "N fields" count under FROM equals the cards on screen.
6. EN + VI strings.

### Binding non-goals

* **No change to what is stored.** `raw_data_json`, `_raw_data_from_row`,
  `_load_multisheet_data`, `source_binding_key`, `import_sample_columns_json`:
  untouched. Aliases stay stored, stay resolvable, stay typeable in the search
  box ("Use "…" as a spreadsheet column"). Pay-neutral by construction: this is
  a display-path change only; the phase writes no row (MF37 diff must be empty).
* No change to the resolver, to `import_mapping_create/delete`, to suggestion
  scoring, or to the right-hand column.
* No change to the file strip ("…xlsx · 43 columns · Load this file as a pay
  run… · Replace file… · Template").
* No change to the other tabs. The Journey is P2.

## 4. Design

### 4.1 FROM entries (`import_mapping_data`, ~8616)

`contexts` today is every batch, `{'id': int, 'name'}`. Add, at the TOP, when
`_import_sample_meta(config)` is truthy:

```python
{'id': 'sample', 'name': _("%s — template file") % meta['filename'], 'kind': 'sample'}
```

and give every batch entry `'kind': 'batch'`.

* `batch_id == 'sample'` → `batch = Batch.browse()`, `source = 'sample'`.
  `int(batch_id)` today would raise on it — guard BEFORE the cast.
* Default when nothing is asked: unchanged preference ladder (RD60) → a batch;
  if no batch has lines → `'sample'` when a sample exists → else the no-file
  state.
* `context_id` returns `'sample'` or the batch id. Client:
  `mapping_studio.js` ~850 stores `r.context_id` into `state.batchId`; verify
  the FROM `<select>`/menu round-trips a string id (it compares ids — make the
  comparison string-safe, W146's lesson) and that `fields` count + FROM title
  render for the sample entry ("Rize_…xlsx — template file · 43 fields").
* After `import_sample_*` upload / "Replace file…" succeeds, the client
  re-reads with `batch_id='sample'` so the person sees the file they just
  dropped (today's lane-1-first ordering did this implicitly; this keeps it).

### 4.2 Lanes per FROM (`_import_left_columns`)

New keyword `source` in `('batch', 'sample', 'none')`.

| FROM | Lane A (file) | Lane B | Lane C (only when non-empty) |
|---|---|---|---|
| a pay run / load | that batch's columns, folded (4.3); lane title = batch name | From this pay run · ‹Month YYYY› (six) | Mapped, but not in this file |
| template file | sample `preferred` columns (today's lane 1); title = `meta['line']` | From this pay run (scheme's latest period) | Mapped, but not in this file |
| nothing on file at all | — | From this pay run | "Already used by this scheme" + "From this scheme's history" exactly as today |

The third row is today's behaviour minus nothing: a never-uploaded scheme must
still show last month's wires (J2's promise). Rows 1–2 DROP lanes 3 and 4 as
lanes; their wires survive through 4.4.

### 4.3 The fold — `_column_alias_fold(keys)` grows a second shape

Keep the signature and return shape `[{key, letter}]`. Keep the positional walk
byte-for-byte for the single-sheet shape (tests 01–04, 06–12 of
`test_runsrc_left_columns.py` must stay green untouched).

Detect the multi-sheet shape up front: **any key contains `|`** AND the keys are
not positionally interleaved (i.e. the first letter-shaped key appears after at
least two heading keys). For that shape:

1. Split every key into `(sheet, rest)`.
2. Per sheet, `headings[sheet]` = ordered `rest` of sheet-qualified keys whose
   `rest` is not an in-range letter alias (see 3).
3. A key is a **letter alias** when `rest` matches `[A-Z]{1,3}` and
   `letter_to_index(rest) < len(headings_of_its_sheet)` (bare letter keys belong
   to whichever sheet emitted `Sheet|<same letter>` immediately before them).
   Secondary-sheet letters are only emitted sheet-qualified — handle both.
4. A **bare twin** (`heading` with no `|`) is an alias when `Sheet|heading`
   exists for some sheet.
5. Emit one entry per `(sheet, heading)`: `key = "Sheet|heading"` (the spelling
   the resolver tries first on a multi-sheet scheme — same rule as
   `peek_source_columns`' `preferred`, `payroll_import_batch.py` ~652),
   `letter` = that heading's position in its sheet.
6. Anything unexplained is EMITTED. Failure mode = an extra card, never a
   missing column, never an exception (the docstring's existing contract).

Also return the alias map (4.4) — add a sibling
`_column_alias_map(keys) -> {any_spelling: canonical_key}` built in the same
pass, for both shapes, rather than changing the fold's return type.

`test_05` is REWRITTEN, not deleted: it becomes "multi-sheet dict rows fold to
one card per column", and its old assertion moves into the report as a
deliberate reversal with this handover cited.

### 4.4 Every wire keeps a card (CM3)

In `import_mapping_data`, after `left` is built:

```python
canon = alias_map  # from 4.3 for a batch; from the sample's cols for 'sample'
                   # (sample: map every non-preferred col of the same
                   #  (sheet, header|letter) to its preferred key)
for w in wires (kind == 'mapping', leftId startswith 'c:'):
    k = w['leftId'][2:]
    if k in canon: w['leftId'] = 'c:' + canon[k]
    elif 'c:' + k not in left_ids: orphan_keys.append(k)
```

`orphan_keys` → Lane C cards, `group = _("Mapped, but not in this file")`,
`sublabel = _("this file has no such column")`, `meta = {'orphan': True}` so the
SCSS can tint it amber (reuse the board's existing warn tone — no new colour).
This is the truthful version of "Already used by this scheme": it appears only
when it has something to say, and what it says is actionable ("your file lost a
column the scheme reads").

The wire's `ref` (rule id) is unchanged, so delete still cuts the right binding.
Nothing is written: the STORED binding keeps whatever spelling it had.

`shown_cols` (suggestion sources) is already read back off `left` — it shrinks
for free. `wired_cols` must be computed AFTER the re-point, or a column whose
binding used the bare spelling gets a suggestion drawn on top of its own wire.

### 4.5 Copy

* Lane C title: "Mapped, but not in this file" / VI "Đã ghép, nhưng tệp này không có".
* Lane C sublabel: "this file has no such column" / VI "tệp này không có cột này".
* FROM sample entry: "%s — template file" / VI "%s — tệp mẫu".
* No "Odoo" anywhere. No internal words (no "alias", "binding", "batch") on
  screen — "pay run", "file", "column".

## 5. Numbered test cases

Python (`tests/test_cleanmap_left_list.py`, new; fixtures in-memory like
`test_runsrc_left_columns.py`):

1. Multi-sheet shape, 9 columns × 4 names → 9 cards, keys all `Sheet|heading`,
   letters A–I in order.
2. Same input → alias map sends `heading`, `Sheet|A`, `A` to `Sheet|heading`.
3. Two sheets, same heading `Total` on both → two cards, labels re-prefixed by
   `_dedupe_card_labels`.
4. Secondary sheet (qualified-only letters) folds too.
5. Single-sheet shape: output byte-identical to before (run the old 01–04,
   06–12 unchanged — they ARE this test).
6. FROM = batch: no card comes from the sample, from "Already used" or from
   history when every binding resolves to a column of the batch.
7. FROM = batch, one rule bound to `Ghost Column` absent from the file → exactly
   one Lane C card; its wire's `leftId` is that card.
8. A rule bound to the BARE heading of a multi-sheet column → wire re-pointed to
   the `Sheet|heading` card; no Lane C card; no suggestion drawn for that column.
9. `test_12_every_wire_starts_from_a_card` equivalent on both shapes and on
   `source='sample'`.
10. `batch_id='sample'` returns sample columns only + six period cards;
    `context_id == 'sample'`; no exception from the int cast.
11. No file, no batch: lanes "Already used…" and "From this scheme's history"
    still present (J2 regression).
12. `contexts[0]['kind'] == 'sample'` only when a sample exists.
13. Read-only: row counts of `hr_formula_rule`, `hr_formula_rule_source`,
    `hr_payroll_import_line` and a checksum of `source_binding_key` unchanged
    across `import_mapping_data` on every FROM.
14. Six period cards present on every FROM (RUNSRC C2 regression).

Browser (Chrome MCP, rize.payobook.com, Rize Vietnam Payroll, light + dark):

15. FROM = "August 2026 — pay data" → **49 fields** (43 + 6); no card reads
    `A`, `B`, `Salary|A`…; still **42 mapped, 1 suggested**; every wire lands on
    a card; console clean.
16. Switch FROM to the template file → 43 + 6; same 42 wires drawn.
17. "Replace file…" with the same workbook → lands on the template-file FROM.
18. Search box: typing `A` still offers "Use "A" as a spreadsheet column".
19. abm/payobook single-sheet scheme: card count unchanged from before the phase.
20. VI: the three new strings render in Vietnamese.

## 6. Deploy / verify

Module: `pb_formula_studio` only, bump to the next free `19.0.1.x.0`. Ledger
deploy contract verbatim (clean staging, per-module rsync, upgrade ALL
databases, purge `/web/assets/%`, restart, hash + version check per DB). Run the
PO parse gate before upgrading.

## 7. Report back

* The measured card count on rize before/after, per FROM entry.
* The key order actually stored on the rize August batch's first line (first 12
  keys) — confirms or corrects CM1.
* Tests 1–20 PASS/FAIL with output for any failure.
* Any binding that landed in Lane C on a live database (that is an owner debt).
* New ledger entries CM5+.
