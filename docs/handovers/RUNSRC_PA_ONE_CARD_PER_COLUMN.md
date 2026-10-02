# RUNSRC Phase A — one card per column, and no invented 85%

**Read `docs/handovers/RUNSRC_LEDGER.md` first**, §0 (binding rules) and §1.1,
§1.2, §1.3 (the verified facts). Everything there is verified with file:line —
**do not re-derive it.**

---

## 1. What the owner saw

On the live Vietnamese board (**Spreadsheet columns → Scheme**, scheme
*Rize Vietnam Payroll*, source *Payroll August 2026 — pay data*), the left
column says **18 fields** for a file of about nine columns, and the cards read:

```
Employee code
A
Employee name
B
Standard working days
…
```

and the canvas is strung with orange **85%** suggestion wires that are not
real matches.

## 2. Scope

Two defects, both in `pb_formula_studio`, both display/suggestion only.

**A1 — one card per real column.** The loaded-batch lane of the Spreadsheet
board must show the same one-card-per-column that the dropped-file lane
already shows.

**A2 — a bare column letter must never generate a suggestion.** Raise the
fuzzy-match floor so a one- or two-character key cannot substring-match a
component code at 0.85.

## 3. Binding non-goals

* **Do not touch `_raw_data_from_row`** (`payroll_import_batch.py:488`) or any
  other writer of the letter aliases. Ledger §1.1 — that is load-bearing, and
  narrowing it has already caused a silent underpayment once.
* **Do not clear, rewrite or migrate `column_letter` / `forced_column_letter`
  on any rule.** Nothing in this phase writes to `hr.formula.rule`.
* **Do not change any resolver**, the import pipeline, or anything that can
  alter a computed number. This phase must be provably pay-neutral.
* **Do not change the right-hand column.** The small `A` / `B` / `C` badge on a
  component card is the component's own expected column and is correct.
* No new model, no new field, no migration.

## 4. Architecture — the exact seams

### 4.1 A1, where the cards come from

`pb_formula_studio/models/pb_formula_studio.py`

* `:8196` `_import_batch_columns(batch)` returns
  `list(json.loads(line.raw_data_json).keys())` from the batch's **first**
  import line — both spellings of every column, in insertion order.
* `:8480` `cols = self._import_batch_columns(batch)`.
* `:8551` `_import_left_columns(batch, cols, input_rules, config=None)`; its
  inner `add(key, group, sublabel, meta)` at `:8571` dedupes on `key` only.
* `:8580-8589` the dropped-file lane, which already filters on
  `col.get('preferred')` and attaches `sample` / `sheet` / `letter` meta.
* **`:8591-8593` is the defect** — `for c in cols: add(c, file_lane)`.

**Precedent to clone**: `peek_source_columns`
(`pb_hr_payroll_formula/models/payroll_import_batch.py:507-585`), in
particular the `best.setdefault(header, …)` / `preferred` pass at `:576-584`
and the `header` vs `letter` classification at `:556-570`. Clone its *rule*,
not its code — it has a parsed `headers` list and a batch does not.

### 4.2 A1, the algorithm you must implement

You only have the ordered keys of the stored dict. Reconstruct what
`_raw_data_from_row` did, walking a column counter:

```
col = 0
for each key k in order:
    if k is a bare letter (fullmatch [A-Z]{1,3})
       and k == index_to_letter(col - 1)        # the alias of the column just emitted
       and the previous emitted header != k:    # a column genuinely HEADED "A"
        mark k as an alias; continue
    emit k as the preferred card for column col
    col += 1
```

`ColumnManager.index_to_letter` lives at
`pb_hr_payroll_formula/formula_engine/column_manager.py:21` and is re-exported
as a module-level `index_to_letter` at `:316`.

Edge cases that MUST be handled — each is a numbered test below:

* **A file whose heading genuinely is `A`.** `_raw_data_from_row` does not add
  a second `A` (`if col_letter not in raw_data`), so that key is a real column
  and keeps its card.
* **A blank heading.** The column's only key is its letter; it must keep its
  card, because there is nothing else to call it.
* **Multisheet / dict rows.** `_raw_data_from_row` returns `dict(row)`
  untouched when the row is already a dict — no aliases at all. Filtering must
  be a no-op there.
* **Sheet-qualified keys** (`SEVL|Basic Salary`, and `SEVL|A`). Strip the
  `sheet|` prefix before the letter test, exactly as `peek_source_columns`
  does at `:556-559`.
* **A component actually bound to a letter key.** If any input rule has
  `source_binding == 'excel'` with `source_binding_key == 'A'`, or
  `data_source_field == 'A'`, that card must still exist — lanes 3 and 4 of
  `_import_left_columns` (`:8594-8598`) re-add it and `seen` keeps it single.
  **Verify this rather than assume it**: a wire whose `leftId` has no card is
  the exact shape of the MAPFIX-D canvas crash.

### 4.3 A1, what a kept card should say

Give the batch lane the same quality as the dropped-file lane: where the
stored row has a value for that column, show `e.g. <value>` as the sublabel,
and carry `meta.letter`. Reuse `_sample_text`
(`payroll_import_batch.py:587`) — it is already "one cell as a person would
read it", never a repr, never a float tail. Do not write a second formatter.

### 4.4 A2, the suggestion floor

`pb_formula_studio/models/pb_formula_studio.py:8503-8523`. Today:

```python
elif rc and (rc in cn or cn in rc):
    x = 0.85
elif rn and (cn == rn or rn in cn or cn in rn):
    x = 0.8
```

An exact match (`cn == rc`, 1.0) must keep working for any length — a
component genuinely coded `A` may legitimately match a column keyed `A`.
**Only the substring arms get the floor.** Apply it to the shorter side of the
comparison: require the *contained* string to be at least **4** normalised
characters before a substring match can score. Ledger §1.3 records the
settled floors; 4 is comfortably below the ≥6 fuzzy-header floor and well
above the 1–3 characters a column letter can be.

Once A1 lands, `cols` no longer contains most letters anyway — but A2 is a
separate rail and must be implemented and tested independently, because
`cols` is also the *legacy* lane's input and the search box can still add a
short key by hand.

## 5. Safety rails

* This phase writes nothing to the database. It changes what two read methods
  return. If you find yourself writing a migration, stop.
* `_import_left_columns` must stay tolerant of a malformed
  `raw_data_json` — `_import_batch_columns` already swallows a parse failure
  and returns `[]`; keep that behaviour.
* Never raise from the board. An unexpected key shape must degrade to today's
  behaviour (show the card) rather than blank the lane.
* Confirm nothing else calls `_import_batch_columns`
  (`grep -rn "_import_batch_columns"`). If anything does, leave it on the raw
  list and filter in `_import_left_columns` instead.

## 6. Numbered test cases

Add to `pb_formula_studio/tests/` — extend `test_excel_onramp.py` if it is the
natural home, otherwise a new `test_import_left_columns.py`. Every test states
its number in the docstring.

1. **A 9-column header/letter dict yields 9 cards.** Build a raw dict exactly
   as `_raw_data_from_row` would (`Employee code`, `A`, `Employee name`, `B`,
   …); assert `_import_left_columns` emits 9 cards from the batch lane and
   none of them is a bare letter.
2. **The aliases are still reachable.** Assert the board still reports
   `can_add: True` and that binding a rule to `'A'` puts an `A` card back on
   the board (lane 3) with exactly one card for it.
3. **A genuine `A` heading survives.** Raw dict `{'A': 1, 'B': 2}` built from
   headers `['A', 'B']` — both keep cards.
4. **A blank heading keeps its letter card.** Headers `['Code', '']` → the
   letter key for the blank column keeps its card.
5. **Multisheet dict rows are untouched.** A raw dict with no letter aliases
   returns every key.
6. **Sheet-qualified aliases are stripped.** `SEVL|Employee code` keeps a
   card, `SEVL|A` does not.
7. **Sample values appear.** A kept card carries `e.g. 12,500,000` from
   `_sample_text`, and a column empty in the stored row says so rather than
   showing `False`.
8. **No 85% from a letter.** With a component coded `MANHANVIEN`, a column key
   `A` produces **no** suggestion wire.
9. **A 4-character substring still suggests.** A column `Basic` against a
   component coded `BASICSAL` still scores 0.85 — the floor must not kill real
   matches.
10. **An exact one-letter match still scores 1.0.** Component coded `A`,
    column key `A` → a suggestion at confidence 1.0.
11. **Pay-neutrality.** Compute a payslip on a scheme whose file has letter
    aliases before and after the change and assert every line is identical.
    This phase must not move a single number.
12. **Wire integrity.** For a scheme with bindings, assert every wire's
    `leftId` exists among the returned `left` ids. Run it against a real
    scheme on `payobook` as well as the fixture.

Also run the existing suites for both modules and report the counts:
`pb_formula_studio`, `pb_hr_payroll_formula`.

## 7. Deploy and verify

Per ledger §0.5. Bump `pb_formula_studio`'s manifest version
(currently `19.0.1.192.0`) — nothing else in this phase needs a bump unless
you touch `pb_hr_payroll_formula`, in which case bump that too
(`19.0.1.137.0`).

1. Clean staging dir, rsync, per-module `rsync -a --delete` into
   `/odoo/odoo-server/addons/<module>/`.
2. Upgrade **every** database: `payobook`, `abm`, `acme`,
   `payobook_template`.
3. Hash each module tree both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`)
   and compare manifest version to `ir_module_module.latest_version` per DB,
   normalising the `19.0.` series prefix.
4. JS/SCSS only if you touched assets: delete `/web/assets/%` attachments per
   DB and restart. **Never compile `web.assets_backend` inside a shell** — it
   OOM-kills the box and takes the live sites down.

## 8. Browser validation (mandatory)

Chrome MCP, on `payobook`, the *Rize Vietnam Payroll* scheme, the
**Spreadsheet columns → Scheme** tab, source *Payroll August 2026 — pay data*:

* Card count in the left column now matches the file's real column count, and
  the `FROM … <n>` counter agrees with it.
* No card is a bare letter.
* The suggestion chips that remain are defensible; screenshot the before/after
  counts.
* Console is clean — read it, do not assume.
* Draw one wire and delete it; the canvas does not throw.
* Shots into `docs/runsrc_pa_shots/`.

## 9. Commit

One feature-scoped commit, explicit file staging, reviewer-focused message.
Do **not** push. End the message with:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## 10. Report back

1. Each of the 12 tests, by number, PASS/FAIL, with the evidence.
2. The before/after left-column card count and suggestion count on the live
   Vietnamese board, with screenshots.
3. Confirmation that test 11 (pay-neutrality) was run against real payslips,
   not only a fixture.
4. Per-database version table after deploy.
5. Any new gotcha, written as **RS1**, **RS2**, … ready to paste into
   `RUNSRC_LEDGER.md` §2.
6. Anything in this handover that turned out to be wrong.
