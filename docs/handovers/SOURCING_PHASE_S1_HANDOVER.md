# SOURCING Phase S1 — Provenance becomes real

**Scope:** persist, per payslip per component, where each input value came from — using the
`resolved_source` the resolver already computes and the matched header key it already returns and
throws away. **Strictly additive. Not one number may move.**

Design: `docs/handovers/SOURCING_DESIGN.md` (§0 facts, §2 vocabulary, §3.2 storage, §4.4 translation).
Conventions + deploy ritual: `docs/handovers/SOURCING_LEDGER.md`. COLROLES CR1–CR33 and MAPFIX
MF1–MF41 still bind.

## Binding non-goals for S1

- **No bindings.** `source_binding` is S3. Nothing new is written to `hr.formula.rule`.
- **No UI.** No serializer change, no chip, no board change. S1 is server-side truth only; S4 renders it.
- **No repair, no `ondelete`, no `target_rule_code` change.** That is S2 — and per the coordinator's
  ruling, **no phase may write `target_rule_id` before S2's remembering compute is in place.** S1
  writes nothing to `hr.integration.field.mapping` at all.
- **No widened connector gate.** S2.
- **`data_source` is not touched** (demoted in S3 per O-3; untouched here).

## Verified plumbing — do not re-derive

| Fact | Where |
|---|---|
| `formula_input_values` is `fields.Text` holding JSON | `hr_payslip_formula.py:42-45` |
| **Three** writers of it, all of which must write the sibling | `payroll_import_batch.py:2157`; `hr_payslip_formula.py:108`; `hr_payslip_formula.py:474` |
| Resolver signature (returns a plain dict) | `payroll_import_batch.py:2498` |
| `resolved_source` assigned on all five branches | `:2826-2845` |
| `lookup_raw_value_with_key` returns `(value, key)` on every path; the key is captured **only** when `is_collaborate` | `:2612-2634`; captures at `:2802-2806` and `:2816-2818` |
| Connector-mapping block fills `input_values` before the loop (gate closed today — S2 opens it) | `:2694-2705` |
| Constants added after the loop | `:2885-2887` |
| Proration / retro / carryover **mutate** `input_values` after that | `:2889-2902` |
| People columns dropped before the loop — never enter `input_values`, so they get no provenance | `:2884-2905` region, `is_excluded_people_column` |
| Batch-free producer (no import line): default → contract `wage` → worked days → connector (a `pass`) | `hr_payslip_formula.py:318-369` |
| `_apply_proration` may **add** codes as well as change them | `:2890-2896` |

## Architecture

### 1. A plain-python provenance module — `pb_hr_payroll_formula/models/input_provenance.py`

Deliberately stdlib-only, **no `odoo` import**, exactly as `component_code.py` is, so the regression
battery can exercise it on a bare interpreter (**MF7** — a gate nobody can execute is not a gate).

```python
SOURCES = ('excel', 'feed', 'rule', 'contract_component',
           'employee_field', 'calculated', 'constant', 'none')

def provenance_token(resolved_source, origin='excel'):
    """The resolver's vocabulary -> the product's vocabulary (DESIGN §4.4).
    THE ONLY PLACE THIS TRANSLATION HAPPENS."""

def entry(src, key=None, via='default', fell_back=False, ignored=None, adj=None):
    """Canonical entry shape, keys always in the same order, empties omitted."""
```

Mapping, per DESIGN §4.4: `raw` → `origin` (`excel`/`feed`) · `mapped` → `employee_field` ·
`contract_component` → `contract_component` · `contract_component_default` →
`contract_component` · `default` → `none`. Anything unknown → `none` (never raise inside a payroll run).

`origin` is hardcoded `'excel'` for S1 — a batch has exactly one source until S3 — but the parameter
exists now so S3 adds a caller, not a signature change.

### 2. `via` — the full vocabulary, fixed here

DESIGN §3.2 listed nine; the two producers it under-specified need seven more. **Deviation from the
design doc, stated:** the `via` list is extended to sixteen. `src` (the eight of §2) is untouched.

`binding` · `binding_empty` · `fallback` · `header` · `column_letter` · `employee_mapping` ·
`contract` · `contract_default` · `default` — plus **`connector_mapping`** (the §6 gate's block),
**`constant`**, **`contract_field`** (the batch-free producer's contract `wage`), **`worked_days`**,
**`proration`** / **`retro`** / **`carryover`** (a code *created* by that adjustment — an adjustment
that merely rewrites an existing value does not change `via`, it appends to `adj`). `binding`,
`binding_empty` and `fallback` are declared now but unreachable until S3.

### 3. Out-parameter, not a changed return

```python
def _transform_data_to_formula_inputs(self, raw_data, contract=None, employee=None, provenance=None):
```

`provenance` is a caller-supplied dict the resolver fills; **the return value is unchanged**.
Changing the return to a tuple would break both existing callers and any out-of-tree one, for no gain.
A caller that passes nothing gets exactly today's behaviour on today's signature.

### 4. Adjustments are recorded, not hidden

Proration, retro and mid-cycle carryover mutate `input_values` *after* resolution. A chip that said
"Spreadsheet 'OT Hours'" for a value proration later changed would be a lie. Snapshot before each of
the three calls, diff after, and stamp `adj: ['proration', ...]` on every changed code; a code an
adjustment *created* gets `{src: 'calculated', via: 'proration'}`. The entry still reports where the
value came *from* — `adj` says what happened to it afterwards.

### 5. Storage

`formula_input_sources = fields.Text(readonly=True)` on `hr.payslip`, beside `formula_input_values`.
`Text` + `json.dumps`, matching its sibling (DESIGN §3.2 — the two are always read together).
Absent/empty means *this payslip predates the feature*; S4 must render that as "not recorded", never
as "no source".

## Neutrality — how this is provable, not merely tested

`input_values` is assigned in exactly five places inside the resolver and one outside it. **This phase
adds no assignment to `input_values` and edits none.** Every change is either (a) a write to a
separate dict, (b) a write to a separate field, or (c) removing an `if is_collaborate:` guard around
the *capture* of a key that `lookup_raw_value_with_key` already returned — which cannot affect
`value`. Byte-identity is therefore structural. The test proves it; the architecture guarantees it.

## Files to touch

| File | Change |
|---|---|
| `pb_hr_payroll_formula/models/input_provenance.py` | **new** — plain python |
| `pb_hr_payroll_formula/models/__init__.py` | import it |
| `pb_hr_payroll_formula/models/payroll_import_batch.py` | `provenance=None` param; unconditional key capture; entries on all branches; adjustment post-pass; write the field at `:2157` |
| `pb_hr_payroll_formula/models/hr_payslip_formula.py` | the field; `_get_formula_input_sources`; write at `:108` and `:474` |
| `pb_hr_payroll_formula/tools/provenance_battery.py` | **new** — bare-interpreter tests |
| `pb_hr_payroll_formula/__manifest__.py` | 19.0.1.72.0 → **19.0.1.73.0** |
| `docs/handovers/SOURCING_LEDGER.md` | phase status + any new S-gotcha |

No JS, no SCSS, no OWL XML in S1 — so no asset-bundle risk (MF12), but the manifest bump is still
required for the `-u` to run the field's schema change.

## Numbered test cases

1. `provenance_token` returns the right token for all five `resolved_source` values, both origins, and
   `None`/garbage → `'none'` without raising.
2. `entry()` emits keys in a fixed order and omits `fell_back`/`ignored`/`adj` when empty.
3. A real abm batch recomputed: **`formula_input_values` byte-identical before and after** for every
   payslip.
4. Same recompute: **every `hr.payslip.line` `(code, amount, quantity, rate)` identical.**
5. `formula_input_sources` is present and covers **100%** of the codes in `formula_input_values`.
6. Every entry's `src` is one of the eight; every `via` one of the sixteen.
7. A component resolved from a header carries the **actual matched key**, not the rule code, when the
   two differ (abm has these — e.g. a rule matched by name rather than code).
8. Constants carry `{src: 'constant', via: 'constant'}`.
9. A component with no source carries `{src: 'none', via: 'default'}`.
10. Both regression batteries green; the new provenance battery green on a bare `python3`.
11. The batch-free producer (payslip with no import line) writes a well-formed blob with
    `contract_field` / `worked_days` / `default`.
12. Passing no `provenance=` argument leaves behaviour and return value unchanged.

## Deploy + verification

Ledger ritual: rsync → **`chmod -R a+rX`** (CR6) → park tabs on `about:blank` (CR20) → stop → confirm
zero `odoo-bin` pids by PID → detached `systemd-run` looping **`sudo -u odoo`** odoo-bin (MF35) over
**abm acme payobook payobook_template** → read the result from `/var/log/odoo/odoo-server.log`, not
the sentinel (MF9) → start → **`sudo -u postgres psql` verify `ir_module_module.latest_version` on all
four** (MF17). A green exit is not proof.

Leave abm as found: record `hr_payslip` / `hr_payslip_line` / `hr_formula_rule` /
`hr_integration_field_mapping` counts and checksums before and after; the only sanctioned delta is
`formula_input_sources` going from NULL to populated on payslips deliberately recomputed by test 3.
**The database is the oracle** (MF37).

## Report back

Per-test results 1–12; the neutrality diff (must be empty); files touched; manifest version; commit
hash; deviations from this spec; new S-gotchas.
