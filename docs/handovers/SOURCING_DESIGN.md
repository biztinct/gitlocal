# SOURCING — where every value comes from, and one run that can use both

**Design document. Owner-approved brief:** `~/.claude/plans/i-want-you-to-giggly-hummingbird.md` (sections A–D
are required OUTCOMES; the mechanisms sketched there are the prior investigation's reading, and this
document owns the design). Companion ledger: `docs/handovers/SOURCING_LEDGER.md`.

Predecessor programmes whose rules still bind: `COLROLES_LEDGER.md` (CR1–CR33),
`MAPFIX_LEDGER.md` (MF1–MF41), `docs/FORMULA_ENGINE_CONVENTIONS.md` (the converter contract).

Module versions at programme start: **pb_hr_payroll_formula 19.0.1.72.0 · pb_formula_studio
19.0.1.126.0 · pb_integrations 19.0.1.10.0 · om_hr_payroll 19.0.1.0.2 (never touched — CR1).**

---

## 0. Verification of the handed-down facts

All nine were re-checked against the code and the live databases before any design was drawn.
**All nine hold.** Six gained a material refinement; two of those change the design.

| # | Claim | Verdict |
|---|---|---|
| 1 | Connector mappings gated on `source_type == 'connector'`; no `action_load_from_connector`; data-store loader raises unless `api_data_store` | **HOLDS** — `payroll_import_batch.py:2696`; the only `action_load_*` is `action_load_from_data_store` (`:512`) raising at `:521-522`. Gate is doubly closed: it also needs `mapping.target_rule_id`, which is NULL on all 8. |
| 2 | `target_rule_id` has no `ondelete`; `target_rule_code` is a stored related that kept its value; abm shows 8 severed | **HOLDS** (`integration_field_mapping.py:82-87`, `:94-98`). Refined: abm has **15** severed-and-still-named mappings, of which **exactly 8** are the transformation-rule outputs. See §7. |
| 3 | `import_mapping_create` writes one Char and ignores `config_id`/`batch_id` | **HOLDS** — `pb_formula_studio.py:4942-4953`; body is `rule.write({'data_source_field': col})`. |
| 4 | Resolver computes `resolved_source` + the matched key, logs it for two hardcoded names, discards it | **HOLDS** — `payroll_import_batch.py:2764-2845` / `:2847-2873`; hardcoded names are `laborcontractsalary` and `collaborate`. Refined: `resolved_source` is computed on **every** component, but `matched_key` is only *captured* for `collaborate` — the key is returned by `lookup_raw_value_with_key` on every path and simply thrown away. Capturing it is free. |
| 5 | Both loaders `unlink()` before writing | **HOLDS** — `:446-447` (Excel) and `:571-572` (data store). |
| 6 | `data_source` is untrustworthy; no line of the payroll pipeline reads it | **HOLDS** (`formula_rule.py:135-147`). Refined: it *is* written by both import wizards and read by `multisheet_import_wizard.py:3037,3057` for a **wizard preview**, and appears in 4 view files. It cannot simply be deleted. See §5.3. |
| 7 | `pb_formula_studio.py:298-335` is the component serializer and emits neither `data_source` nor `data_source_field` | **HOLDS** — verified field-by-field. |
| 8 | API board's right column filters to `column_type == 'input'`, silently | **HOLDS** — `pb_formula_studio.py:4397`. Refined: the **import** board does the same at `:4895-4896`. Both need the seal treatment. |
| 9 | `_trace_cells` reads four sources but caps at 4 | **HOLDS** — `api_transformation_rule.py:858-884`; `if len(cells) >= 4: break`. Refined: it is a **per-row** trace (resolves values against `row`), so the uncapped static extractor is a *sibling*, not a widening. See §8.1. |

### Two facts discovered here that the brief did not have, and that change the design

**F-a. The repair matcher sketched in the brief does not work, and is dangerous.** Forward-mapping the
remembered code through `component_code.build_component_code` was run against all 15 real abm codes:
it resolves **6/15** (only the ones an exact match already gets), it **misses both examples the brief
names** — `NUMBEROFDEPENDENTS` → `NUMBEROFDEPE` while the live code is `NOOFDEPENDEN`;
`ACTUALWORKINGHOURSINCLUDINGPAIDLEAVE` → `ACTUALWORKIN` while the live code is `ACTUWORKHOUR` — and
it **collides**: `…INCLUDINGPAIDLEAVE` and `…EXCLUDINGPAIDLEAVE` both produce `ACTUALWORKIN`, and
`OTNIGHTSHIFTWEEKDAY` and `OTNIGHTSHIFTWEEKENDDAY` both produce `OTNIGHTSHIFT`. Silently wiring
weekday overtime into the weekend-night component is a wrong payslip. Replaced — see §7.3.

**F-b. `hr.formula.rule.version` is an exact rename ledger and nobody knew.** `reason='rename'` rows
(64 on abm) carry a `snapshot_json` holding the **pre-rename `code`** and the `rule_id`. Matching
remembered codes against it resolves 9 of the 15 exactly; the other 6 were never renamed and an exact
code match gets them. **Tiers 0+1 together = 15/15 on abm with zero heuristics and zero ambiguity.**

---

## 1. The shape of the design in one paragraph

Three additions, each strictly in front of code that is not touched. **Provenance** is a second JSON
blob written beside `formula_input_values`, populated from a dict the resolver already fills and
currently discards. **Binding** is an explicit two-field declaration on the component — which side,
which key — and it is consulted in a branch that is *entered only when a binding exists*, in front of
today's candidate ladder, which is left byte-for-byte alone. **Top-up** is a second raw blob on the
import line rather than a merge into the first, so a single-source run's primary blob is bit-identical
to today's and the neutrality gate is satisfied by construction rather than by testing. Everything the
UI shows is derived from those three; nothing is displayed that is not persisted.

The governing principle, and the reason this programme exists: **a value's origin must be a recorded
fact, never an inference.** Every place the old code inferred (`data_source` defaulting to `excel`,
`target_rule_code` surviving by accident, "keys of the last load" labelled *Spreadsheet columns*) is
replaced by something written down at the moment it was true.

---

## 2. The source vocabulary — one set of terms, everywhere

Eight kinds. The **token** is what is stored and what crosses the RPC boundary; the **label** is the
only string a user ever sees. Labels are used identically in the serializer, the rail, the cards, the
Cell Editor, the grid headers, both mapping boards, the cockpit drawers and every toast. No screen
may invent a ninth term or a synonym.

| Token | Label (user-facing) | Meaning | Wirable |
|---|---|---|---|
| `excel` | **Spreadsheet** | A column of the uploaded workbook | yes |
| `feed` | **Connected system** | A key delivered by a connected system's feed | yes |
| `rule` | **Rule output** | A key computed by a transformation rule before payroll sees it | yes |
| `contract_component` | **Contract component** | The amount stored on the employee's contract | no |
| `employee_field` | **Employee record** | A field read off the employee or contract record | no |
| `calculated` | **Calculated** | Computed by this scheme's own formula | no |
| `constant` | **Fixed value** | The same number for everyone | no |
| `none` | **No source** | Nothing feeds it; it falls back to its default | no |

Secondary strings, fixed here so they are not re-invented per surface:

- Sealed-component badge: **"Calculated — needs no source"** (wording precedent: `_ec_left_actions`
  at `pb_formula_studio.py:5608-5615`, *"produced, not imported"*).
- Fallback chip: **"Fell back to <label>"**, tooltip *"Nothing arrived under “<bound key>”, so this
  used <label> “<matched key>” instead."*
- Ignored-side note: **"Also arrived from <label> — not used"**.
- Unbound input: **"No source chosen"**, action **"Create a rule for this"**.
- Bound-but-empty: **"Bound to <label> “<key>” — nothing arrived last run"**.
- Partial feed on a line: **"From the spreadsheet only"** / **"From the connected system only"**.
- Actual-source tooltip: *"Last run: <run name> · matched “<key>”"*.

**Why not the resolver's own vocabulary** (`raw` / `mapped` / `contract_component` /
`contract_component_default` / `default`): `raw` conflates spreadsheet and feed, which is the exact
distinction this programme must surface; `mapped` names an implementation (the
`hr.payslip.import.mapping` board) rather than a source. The resolver's values are kept internally and
translated once, at the single point in §4.4.

**White-label:** none of these strings contains "Odoo", and none may. Technical identifiers
(`from odoo import`, XML ids, `odoo-bin`, module names, log messages, code comments, this document)
keep the real name.

---

## 3. Data model

### 3.1 Binding — `hr.formula.rule`, two fields and a stamp

```python
# pb_hr_payroll_formula/models/formula_rule.py
source_binding = fields.Selection([
    ('excel', 'Spreadsheet column'),
    ('feed', 'Connected system key'),
    ('rule', 'Rule output'),
], string="Source", help="Where this component's value is taken from when a run imports it. "
                         "Leave empty to let the system match it by name, as before.")
source_binding_key   = fields.Char(string="Source key")
source_binding_origin = fields.Selection([
    ('user', 'Chosen by hand'), ('board', 'Drawn on a mapping board'),
    ('import', 'Set during import'), ('migration', 'Inferred on upgrade'),
], string="How it was set")
source_binding_date  = fields.Datetime(string="Bound on")
source_binding_uid   = fields.Many2one('res.users', string="Bound by", ondelete='set null')
```

**Fields on the component, not a separate `hr.component.source.binding` model.** The owner decision is
"per-component binding decides" — exactly one binding per component. A separate model buys a join, an
ACL surface and a second row that can be orphaned; orphaning is the bug this programme exists to fix.

**The key is a Char, never a foreign key — deliberately, and this is the central lesson of fact 2.** A
spreadsheet header and a feed key have no record to point at. A `rule` binding *could* point at
`hr.api.transformation.rule`, and that is precisely how `target_rule_id` came to sever 15 wires in
silence. The durable identity of a rule is already its `output_key` (that is the contract every
consumer reads it by, enforced by `rule_composer._rule_check_key` at `pb_integrations/models/
rule_composer.py:670-700`). Storing the text cannot be nulled by a cascade. Dangling is then a
*computed observation*, not a data loss:

```python
binding_dangling = fields.Boolean(compute='_compute_binding_dangling')  # not stored
# True when source_binding is set and nothing on the relevant side answers to the key:
#   'rule'  -> no active hr.api.transformation.rule on this config's connector has that output_key
#   'feed'  -> the connector's field catalogue has no such path
#   'excel' -> the config's most recent excel batch has no such header   (advisory only)
```

Constraint: `source_binding_key` required when `source_binding` is set; both must be empty when
`column_type != 'input'` (a calculated component cannot be bound — §9.5).

### 3.2 Provenance — `hr.payslip.formula_input_sources`

```python
# pb_hr_payroll_formula/models/hr_payslip_formula.py, beside formula_input_values (:42)
formula_input_sources = fields.Text(string="Input sources", readonly=True,
    help="Where each input value came from on the run that produced this payslip.")
```

`fields.Text` holding JSON, **not** `fields.Json` — it is a sibling of `formula_input_values`, which is
`fields.Text` written with `json.dumps` at `:108`, `:474` and `payroll_import_batch.py:2157`. The two
are always read together; making them different types would guarantee that one caller eventually
`json.loads` the wrong one. Consistency beats elegance on a field that must survive three writers.

Shape — one entry per component code present in `input_values`:

```jsonc
{
  "BASICSALARY": {
    "src": "excel",              // vocabulary token, §2
    "key": "Basic Salary",       // the header/feed key that ACTUALLY matched, or null
    "via": "binding",            // how it was chosen — see below
    "fell_back": false,
    "ignored": {                 // present ONLY when the unused side carried a value
      "src": "feed", "key": "basic_salary", "value": 12000000
    }
  }
}
```

`via` ∈ `binding` · `binding_empty` · `fallback` · `header` · `column_letter` · `employee_mapping` ·
`contract` · `contract_default` · `default`. It answers *"why this one"* where `src` answers
*"from where"*; the two are never merged, because "Spreadsheet, because you bound it" and "Spreadsheet,
because its name happened to match a header" are the difference between a configured system and a
lucky one.

**Written by all three producers or by none.** There are exactly three writers of
`formula_input_values` and every one must write the sibling in the same `write`/`create`:
`payroll_import_batch.py:2157` (batch run), `hr_payslip_formula.py:474` (recompute from the import
line) and `hr_payslip_formula.py:108` (recompute with no import line, via
`_get_formula_input_values` at `:318`). The third has no batch and no raw data; it emits
`{"CODE": {"src": "contract_component"|"none", "via": "contract"|"default", "key": null}}` so the UI is
never asked to distinguish "no provenance recorded" from "no source". A missing
`formula_input_sources` means *this payslip predates the feature* and the UI says so, rather than
guessing.

### 3.3 Two-source raw data — `hr.payroll.import.line`

```python
raw_data_topup_json = fields.Text(default='{}')     # keys that arrived from the SECOND source
source_origin = fields.Selection([
    ('primary', 'From the primary source only'),
    ('topup',   'From the added source only'),
    ('both',    'From both sources'),
], default='primary')
```

**Two blobs, not one merged blob with an origin map.** The brief sketched `raw_data_origin` alongside
`raw_data`. Two blobs are strictly better here for one reason that outranks tidiness: on a
single-source run `raw_data_json` is then **bit-identical to today's** and `raw_data_topup_json` is
`{}`. The neutrality gate becomes a property of the shape rather than a claim to be tested — and the
top-up can never mutate the primary, so a top-up cannot regress a run that already worked. It also
keeps the "unused side" recoverable for the ignored-value report (§4.3), which a merged blob with
last-writer-wins would have destroyed.

Origin of a key is then a lookup, not a stored map: primary blob → the batch's own `source_type`
(`excel` for a file, `feed` for a data-store load); top-up blob → the top-up's source type. A key
present in both is the `ignored` case.

### 3.4 Mapping durability — `hr.integration.field.mapping`

```python
target_rule_id = fields.Many2one('hr.formula.rule', string='Target Formula Rule',
    domain="[('column_type', '=', 'input')]", ondelete='set null',
    help="Formula rule to receive this value")
    # ondelete is EXPLICIT and it is CORRECT: deleting a pay component must not delete the
    # vendor mapping row that fed it. What was wrong was that severing was SILENT — see
    # `is_severed` and `action_repair_severed` below.

target_rule_code = fields.Char(string='Target Code', compute='_compute_target_rule_code',
                               store=True, readonly=True)
    # WAS a stored related. A stored related blanks when the FK blanks — it survived the
    # 15 severings on abm only because ON DELETE SET NULL fires in SQL and never triggers an
    # ORM recompute. That is luck, and the next ORM write to target_rule_id would spend it.
    # Now it REMEMBERS: it copies the code when there is one and keeps its previous value
    # when there is not, which makes a full recompute a no-op and repair possible by design.

@api.depends('target_rule_id', 'target_rule_id.code')
def _compute_target_rule_code(self):
    for m in self:
        if m.target_rule_id and m.target_rule_id.code:
            m.target_rule_code = m.target_rule_id.code
        # else: leave whatever is there. Never blank a memory.

is_severed = fields.Boolean(compute='_compute_is_severed', store=True,
                            string="Lost its component")
    # target_rule_code set AND target_rule_id empty. Stored so the cockpit ledger can facet on it.
```

`target_column_letter` (also a stored related, `:88-92`) gets the same remembering compute, for the
same reason and in the same commit.

---

## 4. Precedence and fallback — the algorithm, precisely

For one input component, one employee, one run. `PRIM` = primary raw blob, `TOP` = top-up raw blob
(`{}` unless a top-up ran). `origin(PRIM)` and `origin(TOP)` are `excel` or `feed`. Header lookup is
today's `lookup_raw_value_with_key`, unchanged, including its normalisation.

```
B := (rule.source_binding, rule.source_binding_key)     # or None

── STEP 1 — bound path.  ENTERED ONLY IF B IS SET. ──────────────────────────────
  side_b   := the blob whose origin == B.kind          (for kind 'rule': the blob carrying
                                                        the connector's rule outputs, i.e. the
                                                        feed side)
  side_o   := the other blob (may be empty)
  v_b, k_b := lookup(side_b, [B.key])
  v_o, k_o := lookup(side_o, today's candidate list for this rule)

  if v_b is not empty:
        value := v_b ; src := B.kind ; key := k_b ; via := 'binding'
        if v_o is not empty:  ignored := {src: origin(side_o), key: k_o, value: v_o}
        GOTO DONE
  if v_o is not empty:                                  # owner decision 3 — fall back, but say so
        value := v_o ; src := origin(side_o) ; key := k_o ; via := 'fallback' ; fell_back := true
        GOTO DONE
  via_hint := 'binding_empty'                           # nothing on either side; fall through
  GOTO STEP 3

── STEP 2 — unbound path.  TODAY'S LADDER, UNCHANGED. ───────────────────────────
  Run `_transform_data_to_formula_inputs`'s existing candidate ladder verbatim over
  PRIM then TOP (TOP is empty on a single-source run, so this is today's code over
  today's data):  data_source_field → sheet-prefixed name → sheet-prefixed code →
  name → code → [column letter, suppressed when has_mapping]
  if a value was found:
        src := origin(blob it came from) ; key := the matched header ;
        via := 'header' | 'column_letter'
        GOTO DONE

── STEP 3 — nothing arrived.  TODAY'S LADDER, UNCHANGED. ────────────────────────
  employee/contract mapping  → src 'employee_field',      via 'employee_mapping'
  contract component amount  → src 'contract_component',  via 'contract'
  is_contract_component      → src 'contract_component',  via 'contract_default'
  otherwise rule.default_value→ src 'none',               via via_hint or 'default'

── DONE ─────────────────────────────────────────────────────────────────────────
  input_values[code]         := normalize_input_value(rule, value)        # unchanged
  provenance[code]           := {src, key, via, fell_back, ignored?}      # new, additive
```

### 4.1 Why this is byte-identical on a single-source run

Four independent reasons, each sufficient:

1. Step 1 is guarded on `B is set`. No component has a binding until a user or the §5.2 migration
   creates one, and the migration creates none it cannot prove.
2. Step 2 is the existing ladder, unmodified, and `TOP` is `{}` — so its input is today's input.
3. Step 3 is the existing tail, unmodified.
4. `input_values` is assigned from exactly the same `normalize_input_value(rule, value)` call sites.
   The provenance dict is written to a **different field**.

The acceptance test therefore does not merely observe equality — it can also assert that the bound
branch was never entered, which is the stronger claim.

### 4.2 Fallback

Fallback is automatic and always marked (`fell_back: true`, `via: 'fallback'`), never configurable.
The user chose which side *should* feed the component; they did not choose to have the run produce a
zero when the other side plainly carried the number. The mark is what turns a silent rescue into a
reportable one — the health hint "bound source produced nothing last run" (§9.6) is driven by
`via ∈ {fallback, binding_empty}`.

A binding that finds nothing on **either** side falls through to Step 3 and lands on the contract
component or the default, carrying `via: 'binding_empty'`. The value is exactly what an unbound
component would have got; only the explanation differs.

### 4.3 Both sides present

The binding wins; the loser is written into `ignored` **with its value**. Recording only that it
existed would make the report unactionable — "the feed also sent something" cannot be triaged, "the
feed also sent 12,000,000 and you used 11,500,000" can. This is owner decision 1 ("the unused side is
reported, never silently dropped") taken literally.

### 4.4 The single translation point

`resolved_source` (`raw`/`mapped`/`contract_component`/`contract_component_default`/`default`) is
mapped to §2 tokens in exactly one function, `_provenance_token(resolved_source, blob_origin, via)`,
living next to the resolver. `raw` → `excel` or `feed` by blob origin; `mapped` → `employee_field`;
`contract_component` and `contract_component_default` → `contract_component` (distinguished by `via`);
`default` → `none`. No other file may perform this translation — a second copy is a second vocabulary
(MF31's lesson: a duplicated predicate is a predicate that will be half-fixed).

---

## 5. Merge semantics, and the migration story

### 5.1 Primary + top-up

`source_type` remains the base source and is not touched. A new action —
**"Also pull from a connected system"** / **"Also pull from a spreadsheet"** — runs the *other*
loader in merge mode.

Both loaders are refactored identically: the body between "parse" and "create lines" becomes
`_ingest_rows(rows, origin, mode)` with `mode ∈ {'replace', 'merge'}`.

- `mode='replace'` is today's path verbatim, `unlink()` included (`:446-447`, `:571-572`). **Primary
  loads never change.** Re-running the primary load discards the top-up too — which is correct and
  must be said in the confirmation text: a fresh primary is a fresh run.
- `mode='merge'` never unlinks. For each incoming row it matches an existing line on the identity
  ladder the loaders already use (normalised employee code → email → name; `_normalize_code`,
  `EXTERNAL_CODE_HEADER_CANDIDATES`), then:
  - **match found** → write `raw_data_topup_json` on that line, set `source_origin='both'`.
    `raw_data_json` is **never** modified. A key present in both blobs is the §4.3 `ignored` case,
    resolved per-component at compute time rather than per-key at load time — which is the whole
    point, because only the binding knows which one is wanted.
  - **no match** → create a new line with an empty `raw_data_json`, the payload in
    `raw_data_topup_json`, and `source_origin='topup'`. **An employee present in only one source
    still produces a line** (owner decision), flagged, and every component resolves through Steps 2–3
    against an empty primary blob exactly as it would for a blank row today.
  - lines the top-up did not mention keep `source_origin='primary'`.

Idempotence: running the same top-up twice replaces `raw_data_topup_json` rather than accumulating.
Merge is keyed, not appended.

### 5.2 Migrating `data_source_field`

`data_source_field` **stays, and stays authoritative inside Step 2** (brief's instruction, and the
right one — it is the highest-priority candidate in a ladder that must not change). It is not deleted
and not moved.

A post-migration back-fills `source_binding` **only where the origin is provable**, per input rule
carrying a non-empty `data_source_field`:

1. value matches the `output_key` of an active `hr.api.transformation.rule` on this config's
   connector → `('rule', value)`.
2. else value matches a path in that connector's field catalogue → `('feed', value)`.
3. else value appears among the headers of the config's most recent `excel` batch →
   `('excel', value)`.
4. else **leave unset.** An unset binding is honest and costs nothing: Step 2 resolves it exactly as
   today. Guessing here would put a wrong word on a chip on five screens.

`source_binding_origin='migration'` on every row it writes, so a later audit can tell an inference
from a decision. Per-DB counts logged (rows examined / bound rule / bound feed / bound excel / left
unset). `table_exists` guarded, idempotent, only writes rows where `source_binding` is still empty.

### 5.3 Demoting `data_source` — and why it is not removed

`data_source` is excluded from the serializer's source block, excluded from every chip, and never
consulted by resolution. Its Cell Editor section (`studio.xml:1354-1372`) is relabelled
**"Manual classification (does not affect import)"** and stays inside the collapsed Advanced
accordion; the new "Where this value comes from" section (§9.3) sits *above* Advanced, expanded.

**Departure from the brief, stated:** the brief says "demoted to a manual override and never treated
as truth", which reads as though it could be dropped. It cannot, and this design keeps it fully
writable. It is written by both import wizards (`formula_import_wizard.py:509,559,1059,1112`;
`multisheet_import_wizard.py:1243-1270,1319,2900,2984,3057`), read by
`multisheet_import_wizard.py:3037,3057` to drive a wizard **preview**, and rendered in four view files.
Removing it is a separate programme with no bearing on where a payslip's numbers come from. It is
demoted, documented as non-authoritative in its `help`, and left alone. Its `help` text is rewritten
to say so — in Odoo-free wording.

---

## 6. Making API mappings fire

`payroll_import_batch.py:2696` becomes:

```python
if config.connector_id and self.source_type in ('connector', 'api_data_store'):
```

with the `if rule.code not in input_values` guard kept, so name-matching remains the fallback and a
mapping can only ever fill a gap, never overwrite a header match.

**Why this is safe, and why it must ship after the repair (§7):**

- `hr.integration.field.mapping.target_rule_id` is read in **exactly one place in the payroll
  pipeline** — this line. Verified: the resolver's other mapping lookup, `mapping_by_rule` at
  `payroll_import_batch.py:2648-2661`, reads a *different model*,
  `hr.payslip.import.mapping` (the employee-field board from MAPFIX). So the gate is the entire blast
  radius.
- The widened branch requires `mapping.target_rule_id` to be set. Before repair, that is NULL on all
  8 rule mappings on abm and on all 8 named ones on payobook — so widening alone changes nothing
  anywhere. After repair, it changes behaviour only on `api_data_store` batches.
- **Every import batch on every one of the four databases is `source_type='excel'` — payobook has 6,
  abm / acme / payobook_template have none — and there is not a single `api_data_store` batch
  anywhere.** Widening is therefore a no-op against all existing data, which is the "config with no
  active mappings must be completely unaffected" gate, proven by data rather than by argument.
  (Corrected during S1: an earlier reading of this attributed the 6 batches to abm. The conclusion is
  unchanged and stronger — see ledger **S7**. Note the consequence: **the payroll data lives on
  payobook, so every recompute-based neutrality gate must run there**, not on abm.)

---

## 7. Severed mappings — the fix, the repair, the audit

### 7.1 What is actually broken

Not `ondelete`. `set null` is the *correct* behaviour: deleting a pay component must not delete the
vendor's mapping row. Three things were wrong, and the design fixes each:

1. Severing was **silent** → `is_severed` (stored, faceted in the cockpit ledger) and a health hint.
2. The remembered code survived by **accident** → `target_rule_code` becomes a remembering compute
   (§3.4), so it survives by design and a full recompute is a no-op.
3. There was **no way back** → `action_repair_severed`.

**Departure from the brief, stated:** the brief frames the missing `ondelete` as the defect. It is
made explicit (with the comment above), but declaring it changes nothing — `set null` was already the
default and already the right answer. The defect is silence, and that is what is fixed.

### 7.2 The live audit (read-only, taken 2026-08-24)

`select count(*) filter (…) from hr_integration_field_mapping`:

| DB | total | `target_rule_id` NULL | **severed (NULL + remembered code)** | active |
|---|---|---|---|---|
| **abm** | 59 | 41 | **15** | 33 |
| **payobook** | 252 | 250 | **8** | 194 |
| acme | 0 | 0 | 0 | 0 |
| payobook_template | 0 | 0 | 0 | 0 |

The brief's "252 mappings, unaudited" resolves to **8 severed**, not 252 — 185 of payobook's active
rows have a NULL target *and no remembered code*, meaning they were never wired to a component at all,
and 57 more are unaccepted `suggested` template guesses. Only **2** mappings in the whole payobook
database have a live `target_rule_id`. On abm the 26 `suggested` rows are likewise never-wired, not
severed. **"Severed" must mean NULL FK *plus* a remembered code**; any other definition would have the
repairer walk 250 rows that were never connected.

abm's 15 break down as **8 transformation-rule outputs** (`OTHRS150`, `OTHRS200`, `OTHRS210`,
`OTHRS270`, `OTHRS300`, `OTHRS390`, `DEPCOUNT`, `WORKEDHRS` — exactly the 8 `output_key`s of the 8
active rules, which is the brief's fact 2 confirmed to the row) and **7 vendor fields**
(`EmployeeID`, `Dateofjoining`, `Full_Name_Vietnamese`, `Employeestatus`, `LocationName`,
`expectedWorkingHours`, `totalWorkedHours`). Same defect, same repair; recommend all 15 (owner
decision O-4, §11).

### 7.3 The repair matcher — a four-tier ladder, never a guess

Candidate scope: the input rules of every `hr.formula.config` whose `connector_id` is the mapping's
connector; if that set is empty, the configs of the connector's company. A tier that finds **more than
one** candidate returns `ambiguous`, never a pick.

| Tier | Method | abm result |
|---|---|---|
| **0 — exact** | a live rule in scope whose `code` == `target_rule_code` | 6/15 |
| **1 — rename ledger** | `hr.formula.rule.version` where `reason='rename'` and `snapshot_json->>'code'` == `target_rule_code`, taking `rule_id` if that rule still exists and is in scope | +9/15 |
| **2 — legacy-code inverse** | for each candidate rule, recompute the code the *old* generator would have produced from its label — `re.sub(r'[^A-Za-z0-9]', '', rule.name).upper()[:40]` — and compare to `target_rule_code`; unique match only | 15/15 standalone |
| **3 — no match** | explicit verdict `no_match`, with the remembered code quoted and the closest three candidates offered for a manual pick | — |

**Tiers 0+1 resolve 15/15 on abm with no heuristic and no ambiguity.** Tier 2 exists because
`hr.formula.rule.version` can be pruned and other databases may have no rename ledger; it was verified
to produce all 15 correct answers by itself, including the misspelled `OT Ngiht shift Holiday` →
`OTNGIHTSHIFTHOLIDAY`, because it *inverts* the lossy transform instead of re-applying it. Both are
pure functions of `(remembered_code, [(rule_id, name, code)])` and are unit-tested without a database.

**Explicitly rejected: `component_code.build_component_code(old_code)`.** Evidence in §0 F-a. Recorded
in the ledger as **S3** so it is not proposed again.

Verdicts are per mapping and always reported: `exact` · `renamed` · `legacy_label` · `ambiguous` ·
`no_match`. `ambiguous` and `no_match` write nothing. `action_repair_severed` is a button on the
mapping list and on the cockpit drawer, runs over a selection, and returns a summary the user can
read before anything else happens — **it is a two-step action: it previews verdicts, then commits.**

### 7.4 Preventing recurrence

`rename_component` (`pb_formula_studio.py:3833-3918`) already rewrites formulas, sample JSON, the
contract advantage template and the salary rule. It gains one more sibling: `hr.formula.rule` deletion
and renaming both leave `target_rule_code` intact by §3.4's compute, and renaming **re-points nothing**
because the FK survives a rename. Deletion is the only severing path, and after this phase it is
visible within one page refresh.

---

## 8. Lineage

### 8.1 Uncapping, without changing the proof rail

`_trace_cells(row)` is a **per-row** trace: it resolves each name against a record and truncates the
value at 60 chars for a narrow rail. The cap of 4 is a display decision living in a data function.
Split:

```python
def _consumed_field_names(self):
    """Every field path this rule reads, in mention order, deduplicated. No row, no cap."""
    # the four sources _trace_cells already reads: filter_conditions['rows'][*]['field'],
    # value_steps[*]['field'], compile_rule_formula(excel_formula)[1] when builder_mode=='excel'

def _trace_cells(self, row):
    # unchanged behaviour: iterate _consumed_field_names(), resolve, truncate, stop at 4
```

```python
consumed_field_paths = fields.Json(compute='_compute_consumed_field_paths', store=True)
@api.depends('filter_conditions', 'value_steps', 'builder_mode', 'excel_formula')
```

`fields.Json` here (unlike §3.2) because this field has exactly one writer and no legacy sibling.
The compute must never raise: `compile_rule_formula` is already wrapped in a bare `except` at
`api_transformation_rule.py:869-871` for the same reason, and the compute keeps that guard — a rule
with a broken draft formula must still save.

### 8.2 Output-key constraint and the underscored placeholder

The converter contract is enforced today only in `rule_composer._rule_check_key`
(`pb_integrations/models/rule_composer.py:670-700`) — i.e. only on the composer lane. It moves to a
model-level `@api.constrains('output_key')` on `hr.api.transformation.rule`, and the composer calls
the model's checker rather than keeping its own copy (MF31: one rule, one place). The backend form's
`placeholder="e.g., NUM_DEPENDENTS"` (`views/api_transformation_rule_views.xml:59`) and the field's
`help` (`api_transformation_rule.py:312`) both suggest an **underscored** key that the constraint will
now refuse; both become `NODEPENDENTS`.

Risk to check before the constraint ships: any existing `output_key` violating it becomes unsavable.
abm's 8 keys (`OTHRS*`, `DEPCOUNT`, `WORKEDHRS`) all pass. The phase must audit all four DBs and
report before adding the constraint; a violator is fixed by rename or the constraint is scoped to
`create` + changed keys.

### 8.3 "Derived here" keeps its provenance across a sync

At `integration_field_mapping.py:515-568` the catalogue merge is `merged.update(live)` — the live layer
wins, and with it `provenance='live'`, which is why a computed key's chip vanishes after a sync. Fixed
as a **post-pass over `merged`**, after the update, rather than by reordering the layers:

```python
computed_keys = {r.output_key for r in active rules on this connector if r.output_key}
for path, item in merged.items():
    if path in computed_keys:
        item['provenance']      = 'computed'
        item['group']           = 'Derived here'
        item['expected_missing'] = False        # a computed key is never "not sent"
```

A post-pass wins regardless of which layer produced the row, which is the property the reordering
approach would not have. `expected_missing=False` is what kills the amber *"not sent — this feed did
not carry this field"* lie on a key the feed was never supposed to carry.

### 8.4 Lineage in place — a third `kind` on the shared popover

Not a fourth popover. `_openMenu` (`mapping_canvas.js:1107-1140`) already takes a `kind` and MAPFIX E1
put a second payload through it for exactly this reason. A `kind: "lineage"` payload renders:

- the rule's `plain_summary`
- **Reads** — `consumed_field_paths`
- **If nothing matches** — the rule's default
- **Feeds** — the components consuming it (bindings with `('rule', output_key)`, plus live
  `target_rule_id` mappings)
- **Open rule** — into the composer

Two constraints that are easy to get wrong and are called out here so they are not:

- **The rule name goes in `label`/`sublabel`, not in a tooltip.** `itemMatches`
  (`mapping_geometry.js:139-149`) searches `label`, `sublabel`, `sample`, `meta.col`, `group`; text
  that lives only in `title=` is unsearchable, and a board with 236 cards is navigated by search.
- **Placement must measure, not estimate** (MF27): `_placeMenu`'s double-`requestAnimationFrame` is
  mandatory for this payload too, because the lineage body is taller than an action list.

---

## 9. UI surfaces

### 9.1 The serializer — one nested object, one round trip

`get_studio_data`'s component serializer (`pb_formula_studio.py:298-335`) gains **one** key:

```jsonc
"source": {
  "declared": {"kind": "excel", "key": "Basic Salary", "label": "Spreadsheet",
               "wirable": true, "dangling": false},
  "actual":   {"kind": "excel", "key": "Basic Salary", "label": "Spreadsheet",
               "via": "binding", "fell_back": false, "ignored": true,
               "run": "March 2026 import", "run_id": 12}
}
```

One nested object rather than five sibling keys, so every render site reads one path and a client that
predates the change degrades to "no source block" instead of showing half a truth (the `column_role`
precedent at `:328-331` — *"the client still guards with `c.column_role || 'payroll'`"*).

`declared` is computed from the binding, and when there is no binding from the component's own nature:
`column_type == 'formula'` → `calculated`; `'constant'` → `constant`; `is_contract_component` →
`contract_component`; an `hr.payslip.import.mapping` destination → `employee_field`; else `none`.
**`data_source` is not consulted.**

`actual` is read from **one** payslip — the most recent `calculation_method='formula'` payslip of this
config that has a `formula_input_sources` blob — loaded once per `get_studio_data` call and indexed by
code. One extra read, not one per component. The tooltip names the run, so "actual" is never mistaken
for "always": *"Last run: March 2026 import · matched “Basic Salary”"*. No blob → `actual` omitted and
the chip shows declared only.

### 9.2 Components rail — a chip per row

Precedent: the role chip at `studio.xml:972-974` (`ol-role r-{{role}}`, an SVG glyph, a `title`). New
`ol-src s-{{kind}}` sibling, same geometry, one glyph per kind (Lucide, per the design mandate — never
emoji). Shown for **every** component including calculated ones, muted for the non-wirable kinds so
the rail reads as "these four are fed, these six are computed" at a glance. Where `declared` and
`actual` disagree, the chip carries a small dot and the tooltip names both.

### 9.3 Cards and Cell Editor

- **Card hero subtitle** (`studio.xml:1038`) — today `'Column X · Input value · Category'`. Becomes
  `'Column X · Input value · from Connected system “overtime_150”'`, and for a rule binding
  `'… · from Rule output “OTHRS150” (Overtime 150%)'`.
- **Cell Editor** — a new `ce-sec` titled **"Where this value comes from"**, placed *above* the
  Advanced accordion and open by default, with two rows: **Declared** (a select over the three
  wirable kinds plus "let the system match by name", and a key field with a datalist of the relevant
  keys) and **Actual** (read-only chip, matched key, run name, and the fallback/ignored notes). The
  existing Data-source block stays inside Advanced under its new "Manual classification" heading
  (§5.3). Promoting the *new* block rather than the old one is the point — the old one is not truth.

### 9.4 Grid column headers

`grid_studio.xml:58-77` — after `<span class="g2-code">`, a `<span class="g2-src s-{{kind}}">` glyph
with a `title`. Header width is already tight; the glyph is a dot-plus-letter, not a word, and the
full sentence lives in the tooltip. **Screenshot the header in its fullest state, not its resting one**
(CR22) — a long code plus the scenario button plus this glyph is the worst case.

### 9.5 Both mapping boards

- **Right column gains a chip.** The API board's *left* items already carry `prov` / `provKind` /
  `note` (`pb_formula_studio.py:4386-4391`), and the canvas already renders them. The right column's
  items (`:4397-4401` API, `:4895-4898` import) gain the **same keys**, so a component already fed
  elsewhere is obvious with almost no client change.
- **Calculated components shown, sealed.** Both boards stop filtering to `column_type == 'input'` and
  instead include `formula` and `constant` with `meta.wirable: false`, `prov: 'calculated'` and the
  badge **"Calculated — needs no source"**. The canvas must refuse to complete a wire onto a
  non-wirable card (a refusal that moves the focus ring, never a silent drop), and `itemActions`
  returns `[]` for them so no menu offers a verb they cannot perform.
- **"Derived here" lane** on the API board's left column, from §8.3.
- **Create inline** — an unbound input's card menu offers **"Create a rule for this"**, launching the
  composer with `output_key` pre-filled from the component's code. The code is already
  converter-legal by MAPFIX Phase A, so `_rule_check_key` will accept it; if a legacy code does not
  pass, the composer opens with the suggested correction rather than a raise.

Two live-board hazards, both already paid for once: a root-level `keydown` handler steals Enter from
buttons inside it (**MF33**) — the sealed cards' refusal path must not become a wire; and a card
appended rather than placed grows a duplicate lane heading (**MF32**) — the "Derived here" lane must
be inserted by lane order via `_ec_place_in_lane`, not appended.

### 9.6 The cockpit closes the loop

`pb_integrations/models/pb_integrations.py`:

- `_detail_rule` (`:608`) gains **"Feeds these components"** — bindings with `('rule', output_key)`
  plus live `target_rule_id` mappings, each linking to the component.
- `_detail_mapping` (`:408`) gains **"Produced by"** when its `source_field` is a rule `output_key`,
  and a **"Lost its component"** row plus the repair button when `is_severed`.
- `_ledger_rule` (`:551`) gains a consumers count column, so a rule feeding nothing is visible in the
  list without opening it.
- **Health hints** (four, each a filtered count with a drill-down): rule output consumed by nobody ·
  severed mapping · input with no source at all (`declared.kind == 'none'`) · bound source that
  produced nothing last run (`actual.via ∈ {fallback, binding_empty}`).

---

## 10. Phase split

Five phases. The order is forced in two places: provenance must exist before any screen can show an
"actual", and severed mappings must be repaired before the connector gate is widened (a widened gate
over severed mappings does nothing; over repaired ones it does what it should).

Every phase: commit with explicit staging, **do not push**; bump the manifest version of every module
touched and `-u` it (an asset change without a version bump serves a stale bundle — MF12); deploy per
the ledger ritual across **abm acme payobook payobook_template** and verify `latest_version` in psql
on all four before believing it (CR6/MF17/MF35).

### S1 — Provenance becomes real
`formula_input_sources` on the payslip; the resolver fills a caller-supplied dict; all three writers
of `formula_input_values` write the sibling; the §4.4 translation function; `_provenance_token` unit
tests for all five `resolved_source` values.
**Gate:** recompute a real abm batch's payslips before and after — `input_values` and every
`hr.payslip.line` **byte-identical**; `formula_input_sources` populated for 100% of codes; both
regression batteries (`excel_semantics_battery`, `import_resolution_battery`) green.

### S2 — Severed mappings, lineage data, and the gate
Remembering `target_rule_code`/`target_column_letter`; explicit `ondelete`; `is_severed`;
`action_repair_severed` (preview → commit) with tiers 0–3; the uncapped `_consumed_field_names` +
stored `consumed_field_paths`; the model-level `output_key` constraint and the two underscored
placeholders; **then** the widened connector gate.
**Gate:** pure-python tests for both matchers (including the four proven collisions, which must return
`ambiguous`); 15/15 correct verdicts on abm and every rule output showing a live consumer afterwards;
payobook's 8 audited and reported, **repaired only on owner authorisation** (O-1); a full recompute of
`target_rule_code` proven to be a no-op; neutrality re-proven — the widened gate changes nothing
because every existing batch on both DBs is `excel`.

### S3 — One run, two sources
`source_binding` + key + stamp; `binding_dangling`; the §5.2 migration; `raw_data_topup_json` and
`source_origin`; `_ingest_rows(rows, origin, mode)` refactor of both loaders; the top-up action; the
Step-1 branch with fallback and ignored-side recording.
**Gate:** single-source neutrality re-proven **and** the bound branch asserted never entered; merge
tests for employee-in-primary-only, employee-in-top-up-only, employee-in-both; binding-wins,
fallback-marked and both-present-ignored each asserted in `formula_input_sources`; re-running the
primary load proven to clear the top-up; migration counts logged per DB with zero guesses.

### S4 — Every screen says where a value comes from
The `source` block in the serializer; rail chip; card subtitle; the Cell Editor's new section and the
demotion of the old one; grid header glyph; right-column chips on both boards.
**Gate:** Chrome MCP on abm showing the chip in the rail, on a card, in the Cell Editor, on a grid
header and on both boards; declared-vs-actual visibly different on at least one component; the same
eight labels on every surface, checked against §2 word for word; zero occurrences of "Odoo" in any
added string; **DB before/after diff proving nothing was written** (MF37 — the database is the oracle,
a `fetch` hook is blind).

### S5 — Lineage in place, sealed components, and the cockpit
The `kind: "lineage"` popover payload; the "Derived here" lane surviving sync with `expected_missing`
never set on a computed key; calculated components shown and sealed on both boards; "Create a rule for
this"; the three cockpit drawer sections and the four health hints.
**Gate:** a lineage popover on abm showing Reads and Feeds for `OTHRS150`; a simulated sync proving the
computed chip survives; a sealed card proven non-wirable including via the Enter path (MF33); the
cockpit sections and every health hint firing on real abm data; abm left as found apart from the
sanctioned repair, proven by DB diff.

---

## 11. Open items needing an owner decision before implementation starts

- **O-1 — payobook repair authorisation.** 8 severed named mappings (`EMPCODE`, `FULLNAME`, `EMAIL`,
  `DEPARTMENT`, `POSITION`, `JONINGDATE`, `BIRTHDAYCOMPANY`, `BASICSALARY`). The brief authorises the
  repair on abm and only an *audit* on payobook. S2 will report verdicts for payobook and stop.
  Repair there needs a yes.
- **O-2 — how to prove "API mappings actually fire" without disturbing abm.** Both live DBs have zero
  `api_data_store` batches, which is what makes the widened gate provably neutral — and also means
  nothing on either DB exercises it. Proposal: prove it on **payobook_template** (0 mappings, 0
  batches, nothing to disturb) plus an Odoo integration test, and leave abm untouched. The alternative
  is a create-then-delete batch on abm, which contradicts "leave abm as found".
- **O-3 — `data_source` stays.** §5.3 demotes it and keeps it writable rather than removing it.
  Confirm that is the intended reading of "demoted to a manual override".
- **O-4 — repair all 15 abm mappings, or only the 8 rule ones?** Recommend all 15: identical defect,
  identical repair, and leaving 7 severed rows behind means the health hint fires forever on rows
  nobody intends to fix.
- **O-5 — `output_key` constraint scope** (§8.2). If any of the four DBs holds a violating key, say
  whether to rename it or to scope the constraint to `create` plus changed keys.
