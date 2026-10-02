# RUNSRC Phase C — "From this pay run" is a source you can wire

**Read `docs/handovers/RUNSRC_LEDGER.md` first**, §0 (binding rules) and all of
§1, plus any **RS<n>** gotchas Phases A and B appended to §2. Everything there
is verified with file:line — **do not re-derive it.**

Phase B is merged before this phase starts. Its six codes, its
`default_standard_work_days`, and its `pb_std_work_days` fields on the run and
the batch are **inherited facts**; read
`docs/handovers/RUNSRC_PB_THE_RUN_ANSWERS.md` and
`pb_hr_payroll_formula/models/pay_period.py` rather than re-deciding any of it.

---

## 1. What the owner asked for, and why Phase B alone does not deliver it

> "how to map fields like Start and End date of payslip, Standard working days
> etc from the payrun wizard when it runs … Can you show mapping for that as
> well"

Phase B made the run **answer** six things. But `fill_period_inputs`
(`pay_period.py:165`) writes a value only when the component's **CODE** is one
of `PERIOD_CODES`. On the live Vietnamese scheme the standard-working-days
component is not coded `STDDAYS` — it is coded in the customer's own language.
Phase B therefore cannot reach it, and never will, because renaming a live
component's code rewrites every formula that references it.

**So the run's values are useless to a real scheme until a person can draw a
wire from them.** That wire is this phase.

## 2. Scope

**C1 — a component can declare that the pay run answers it.** A new per-rule
declaration, one of the six codes, honoured by both resolvers.

**C2 — the mapping board grows a "From this pay run" lane** whose six cards
carry the live value for the period on screen, drawable and erasable like any
other wire.

**C3 — the client-side vocabulary learns `period`.** Phase B proved the
server writes `src='period'` correctly and that the chip a user sees still
reads **"No source"**, because `source_vocab.js` never learned the kind. Every
wire C2 lets somebody draw would render as "No source" without this. Three
lines, one file — see §4.5. This also fixes `PAYMONTH`, which has been
mislabelled on every board since the period became a source.

## 3. Binding non-goals — read these twice

* **Do NOT add a fourth `kind` to `hr.formula.rule.source`.**
  `formula_rule_source.py:53-59` says in terms: *"The same three values as
  `source_binding`, and there must never be a fourth: these are the kinds a RUN
  can be asked to read, and a run carries at most two payloads."* That reasoning
  holds. The run's own period is not a payload the run carries; it is a fact
  about the run. §4.1 gives the shape that respects this.
* **Do not change `_SOURCE_RANK`'s existing order** (J-D5 forbids moving a
  rung). You append one position at the end; you move nothing.
* **Do not touch `PERIOD_CODES`, `period_values`, `default_standard_work_days`
  or `fill_period_inputs`' signature.** Phase B settled them and the bare-
  `python3` battery imports that module.
* **Do not touch `_raw_data_from_row`** (ledger §1.1).
* Transformations are **Phase D**, not this phase. Leave
  `api_transformation_rule.py` alone.
* No migration. No data written to any existing record on upgrade.

## 4. Architecture — the exact seams

### 4.1 C1, the declaration — clone the contract component, not the source row

`formula_rule_source.py:30-34` names the precedent explicitly:

> "THE CONTRACT COMPONENT IS DELIBERATELY NOT A ROW HERE. It has no key, it is
> a boolean … It joins the ranked list only in
> `hr.formula.rule.declared_sources()`, always last."

Do exactly that, with a Selection instead of a Boolean, because there are six
answers rather than one.

On `hr.formula.rule` (`pb_hr_payroll_formula/models/formula_rule.py`, beside
`is_contract_component` at `:630`):

```python
period_key = fields.Selection([
    ('PAYMONTH',  'Pay month'),
    ('PAYYEAR',   'Pay year'),
    ('PAYDAYS',   'Days in the period'),
    ('STDDAYS',   'Standard working days'),
    ('STARTDAY',  'Day the period starts'),
    ('ENDDAY',    'Day the period ends'),
], string='Answered by the pay run', ...)
```

Build the Selection **from `pay_period.PERIOD_CODES`** so a seventh code can
never exist in one place and not the other — but keep the labels here, because
`pay_period` is stdlib-only and must not import `_`.

Then:

* **`_SOURCE_RANK`** (`formula_rule.py:258`) and `_config_kind_rank()`
  (`:277`): append `'pay_run'` **after** `'contract_component'`. Last. See §5.
* **`declared_sources()`** (`:342`): splice
  `{'kind': 'pay_run', 'key': self.period_key, 'origin': 'user'}` in at its
  rank position, exactly as the contract component is spliced at `:382-387`.
  This method is "the single definition of precedence" and both the resolver
  and every board read it — so getting it right here is most of the phase.
* **`set_source_binding(kind, key, origin=)` / `clear_source_binding(kind)`**:
  route `kind == 'pay_run'` to write / clear `period_key` instead of creating a
  `hr.formula.rule.source` row. ONE entry point keeps every existing caller,
  chip and board working unchanged. Refuse a `key` that is not in
  `PERIOD_CODES`.

### 4.2 C1, the two resolvers

Both already call `fill_period_inputs` last:

* `hr_payslip_formula.py:812-816`
* `payroll_import_batch.py:4628-4632` (line numbers as Phase B left them —
  re-grep, do not trust these)

`fill_period_inputs` matches on code. A wired component's code is not its
period key, so you need one more step, **in the same place, immediately before
that call**: for every rule that has a `period_key` and is still unresolved,
write `period_values(...)[rule.period_key]` into `values[rule.code]`.

Preserve every property Phase B's docstring claims:

* only when the component is **unresolved** — a wire never beats a column;
* never invents a key that is not already in `values`;
* never raises;
* provenance `src='period'`, `via=PERIOD_VIA`, so the existing source chips and
  `_SOURCE_LABELS['period'] = "Pay period"` light up with no display work.

Prefer one shared helper over two copies. If the two resolvers' shapes make
that genuinely ugly, duplicate it and say so in the report — but look first.

### 4.3 C2, the board lane

`pb_formula_studio/models/pb_formula_studio.py`:

* `import_mapping_data(config_id, batch_id)` at `:8549` builds `left` / `right`
  / `wires`. **Phase A changed this file — every line number in §4.3 is from
  before that landed. Re-grep each one; do not trust them.** Phase B already
  saw `_import_left_columns` move from `:8551` to `:8667`.
* The component column is built by `_mc_right_column` (`:1115`); a card's
  `srcKind` / `srcNote` / `srcKinds` come from `_source_block` (`:1176`) →
  `_declared_source` (`:1102`) → `_source_label` (`:798`). That chain is what
  makes a drawn wire show "Pay period" on the component card, and it reads
  `declared_sources()`, so §4.1 feeds it with no extra work.
* The spreadsheet lane ids are `'c:' + key` (`:8620`, `:8637`). Use a distinct
  prefix for these: **`'p:' + CODE`**. A collision with a column called
  `p:STDDAYS` is not possible; a collision with `c:` would be.
* `import_mapping_create(config_id, batch_id, column, target_rule_id, resolve)`
  at `:8733` is the wire-draw endpoint. It already strips a `'c:'` prefix at
  `:8760`. Teach it `'p:'` → `set_source_binding('pay_run', code,
  origin='board')`. Keep `_can_edit()`, `_mc_refuse_sealed`, and the
  wrong-type-in/refusal-out rail at `:8758-8764`.
* `import_mapping_delete(rule_id)` at `:8789` must also clear `period_key`.
  Read its comment at `:8794-8803` — it is about exactly this class of bug:
  a delete that takes the wire off the board while the component keeps reading.

**The six cards must show the run's real numbers.** The lane is worthless if it
says "Standard working days" with no value. When a `batch_id` is on screen, use
that batch's `date_from` / `date_to` / `_pb_standard_work_days()`; call
`period_values(...)` once and put each answer on its card as the sublabel, the
same `e.g. <value>` shape the file lane uses. **August 2026 must read
`e.g. 21`** on the card — that is the number the owner will check.

When there is no batch, fall back to the scheme's own most recent run, and if
there is none, show the code's meaning without a value rather than a zero.

### 4.4 The lane trap — CONFIRMED REAL by Phase B, fix it first

I suspected this; Phase B's §7 confirmed it. `_config_kind_rank()` builds from
the scheme's **enabled lanes**, and a kind that belongs to no lane is dropped.
The mapping lives in `pb_hr_payroll_formula/models/formula_config.py:405`:

```python
SOURCE_LANES = ('api', 'excel', 'records')
_LANE_KINDS = {
    'api':     ('feed', 'rule'),
    'excel':   ('excel',),
    'records': ('employee_field', 'contract_field', 'bank_account',
                'contract_component'),
}
```

`'pay_run'` is in none of them, so **without this change every wire this phase
lets somebody draw is silently dropped at resolve time** — the board saves, the
chip appears, and the number never lands. That is the worst possible failure
shape and it is the default one.

The fix is small, and deliberately adds **no new switch**:

* append `'payrun'` to `SOURCE_LANES`, last;
* add `_LANE_KINDS['payrun'] = ('pay_run',)`;
* add **no** `source_payrun_enabled` Boolean. `_source_lane_ok` (`:446`) already
  documents *"Unknown lanes are on"* and returns `True` by default, which is the
  behaviour we want: every run has a period, so there is nothing to switch off.

Then **verify `_source_lane_order()` (`:455`) appends it last on a scheme whose
stored `source_priority` string predates it** — its docstring promises missing
tokens append in default order, and this phase is the first thing to depend on
that promise. Test 6.

`import_mapping_create`'s SC-4 refusal (`:8768-8774`) is the spreadsheet lane's
own switch and is not copied here, for the same reason: there is nothing to
refuse.

### 4.5 C3, the client-side vocabulary

`pb_formula_studio/static/src/js/source_vocab.js` — *"the client-side
vocabulary every surface renders through"*. Three edits:

* `SOURCES` (`:21`) — add `{ key: "period", icon: <a Lucide glyph from the
  kit's `ic()` registry that is distinguishable at 12px with no colour — a
  calendar reads correctly here> }`. Never emoji.
* `srcLabel` (`:52`) — add `period: _t("Pay period")`, matching the server's
  `_SOURCE_LABELS['period']` at `pb_formula_studio.py:798` **word for word**.
  Two spellings of one label is how this went wrong in the first place.
* `READ_KINDS` (`:42`) — add `"period"`. Without it `srcDisagrees` reports a
  false disagreement and the card reads *"Last run used a different source"*
  about a component that is working perfectly.

Labels resolve through `_t()` at call time, never at module scope — the file
says why at `:15-18`. Keep that.

## 5. The ruling: a wire still loses to the file

The run sits **last**, below the contract component. A scheme whose file has a
"Standard working days" column keeps reading the file, even if somebody also
draws the pay-run wire. That is deliberate and matches `pay_period.py:22-26`:
the run replaces the value that was *missing*, never the value somebody stated.

Consequence, and it is the phase's main safety property:

> **Nothing changes on any existing database until a person draws a wire.**

Say so in the report, and prove it with test 10.

## 6. Safety rails

* A component wired to the pay run and **also** to a column is not an error —
  it is the ordinary two-source case J9 exists for. It must not raise, and the
  card must show both chips.
* Never raise from the board or from a resolver. An unreadable period degrades
  to today's behaviour.
* `period_key` on a rule whose scheme was later reconfigured must not break
  `declared_sources()` — that method is called on every board render.
* Deleting nothing: this phase writes no data on upgrade.

## 7. Numbered test cases

Add to `pb_hr_payroll_formula/tests/` and `pb_formula_studio/tests/`. Every
test states its number in the docstring.

1. **The Selection is the six codes.** `period_key`'s values are exactly
   `pay_period.PERIOD_CODES`, in that order.
2. **`declared_sources()` lists it last.** A rule with a feed source, a column
   source, `is_contract_component` and a `period_key` returns four entries with
   `pay_run` last.
3. **`set_source_binding('pay_run', 'STDDAYS')` writes the Selection** and
   creates **no** `hr.formula.rule.source` row.
4. **A bad key is refused.** `set_source_binding('pay_run', 'BANANAS')` writes
   nothing.
5. **`clear_source_binding('pay_run')` empties it**, and
   `import_mapping_delete` does too.
6. **A scheme that has never heard of the pay run still honours the wire.**
   Take an untouched config, wire a component, resolve — the value lands. This
   is the `_config_kind_rank` trap in §4.4.
7. **A wired component with a non-matching code gets the value.** Component
   coded `NGAYCONGCHUAN`, `period_key='STDDAYS'`, period 1–31 Aug 2026 → 21.0.
8. **The file still wins.** Same component, also bound to a column that has a
   value → the column's value, and provenance says the spreadsheet.
9. **A wired component that is already resolved by a feed is untouched.**
10. **Pay-neutrality on untouched data.** Compute a real payslip on `payobook`
    before and after, with no wire drawn anywhere — every line identical.
11. **The board offers six cards** with `p:` ids, and the standard-working-days
    card reads `e.g. 21` for an August 2026 batch.
12. **Drawing and erasing round-trips.** `import_mapping_create` with
    `'p:STDDAYS'` then `import_mapping_data` shows an accepted wire; delete and
    it is gone from both the board and the rule.
13. **Wire integrity.** Every wire's `leftId` exists among the returned `left`
    ids — including the new `p:` ones. (Phase A's test 12, extended.)
14. **Two sources, two chips.** A component wired to both a column and the run
    renders both and does not raise.
15. **The chip says "Pay period", not "No source".** C3. Assert
    `srcLabel('period')` is the same string as the server's
    `_SOURCE_LABELS['period']`, and that `READ_KINDS` contains `'period'` so
    `srcDisagrees` is quiet. Then confirm it on screen on `rize`, whose
    `PAYMONTH` components have real payslips — Phase B's shot
    `docs/runsrc_pb_shots/04_studio_paymonth_chip_gap.png` is the "before".
16. **The lane order tolerates an old scheme.** A config whose stored
    `source_priority` predates `'payrun'` still returns it, last, from
    `_source_lane_order()`. (§4.4.)

Also run the full suites for `pb_formula_studio` and `pb_hr_payroll_formula`
and report the counts.

## 8. Deploy and verify

Per ledger §0.5. Bump both manifests from whatever Phases A and B left them at
(`pb_formula_studio` and `pb_hr_payroll_formula`).

1. Clean staging dir; rsync; per-module `rsync -a --delete` into
   `/odoo/odoo-server/addons/<module>/`. **Never** `--delete` into the addons
   directory itself.
2. Upgrade **every** database. Phase B established the real list — **`acme`
   does not exist**; there are six: `payobook`, `abm`, `payobook_template`,
   `rize`, `rztest`, `p9clone`. (The ledger's §0.5 four-database list is stale;
   correct it while you are there.)
3. Hash both sides (skip `__pycache__`, `*.pyc`, `.DS_Store`); compare each
   manifest version to `ir_module_module.latest_version` per DB, normalising
   the `19.0.` prefix.
4. JS/SCSS: delete `/web/assets/%` per DB and restart. **Never compile
   `web.assets_backend` in a shell** — it OOM-kills the box.

The server has dropped SSH mid-command in this session. If a remote step dies
with a broken pipe, re-run it and verify the result rather than assuming it
landed.

## 9. Browser validation (mandatory)

Chrome MCP, **`rize.payobook.com`** — ledger **RS3**, the Vietnamese board is on
the `rize` tenant and payobook has no scheme of that name. Scheme *Rize Vietnam
Payroll* (3938) / *Rize Vietnam* (3921), batch 1113, source *Payroll August
2026 — pay data*:

* The "From this pay run" lane shows six cards with real values; standard
  working days reads 21 for August 2026.
* Draw a wire from **Standard working days** to the scheme's real working-days
  component. It saves, the chip says "Pay period", and it survives a reload.
* Erase it; it goes from both the board and the component.
* Console clean — read it, do not assume.
* Shots into `docs/runsrc_pc_shots/`.

## 10. Commit

One feature-scoped commit, explicit file staging, reviewer-focused message.
Do **not** push. End with:

```
Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
```

## 11. Report back

1. Each of the 16 tests, by number, PASS/FAIL, with evidence.
2. What `_config_kind_rank()` and `_source_lane_order()` actually did with
   `'payrun'` on an untouched scheme (§4.4) — the confirmed trap.
3. Screenshots of the lane, and of a wire drawn, saved and reloaded.
4. Confirmation that test 10 ran against real payslips, not a fixture.
5. Per-database version table after deploy.
6. New gotchas as **RS<n>**, continuing Phase A/B's numbering, ready to paste
   into `RUNSRC_LEDGER.md` §2.
7. Anything in this handover that turned out to be wrong.
8. **For Phase D**: where a transformation rule's evaluation context is
   assembled, and what it would cost to add the run's six numbers beside the
   `period_start` / `period_end` it already resolves at
   `api_transformation_rule.py:1065-1066`.
