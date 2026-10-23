# SOURCING Phase S3 — bindings, and one run from two sources

**Scope:** an explicit per-component binding (which source, which key); a top-up that merges a second
source into an existing run instead of destroying it; and precedence that honours the binding, falls
back when the bound side is empty, and reports the side it did not use.

Design: `SOURCING_DESIGN.md` §3.1 (bindings), §3.3 (two blobs), §4 (precedence), §5.1 (merge).
Ledger: `SOURCING_LEDGER.md` S1–S11 bind, plus CR1–CR33 and MF1–MF41.

**This is the phase that can break payroll.** Everything below is arranged so that the single-source
path is not merely tested but *structurally incapable* of changing.

## Binding non-goals

- **No UI.** No serializer, no chips, no board changes — S4/S5. S3 is the engine only.
- **No changes to the two primary loaders' behaviour.** They keep unlinking; a primary load is a
  fresh run and must stay one.
- **`data_source_field` is not migrated away** — it remains the highest-priority legacy candidate
  inside the unbound ladder. **`data_source` stays demoted and unread** (O-3).
- **No FK for the binding** (§2) — S2 demonstrated exactly what an FK does when the target goes.

## Standing MRO check — done before designing (coordinator's rule after S1)

Every method whose signature S3 touches, grepped across the whole tree:

| Method | Overrides found |
|---|---|
| `_transform_data_to_formula_inputs` | **none** (only `payroll_import_batch.py:2505`) |
| `get_raw_data` | **none** (only `payroll_import_line.py:121`) |
| `action_load_file` / `action_load_from_data_store` | **none** |
| `_create_payslip` | **none** |

Inheritors of the three models S3 touches, checked for field-name collisions:
`pb_hr_workforce_planning` adds `wfp_category` to `hr.formula.rule`; `pb_demo` adds `is_demo` to
`hr.formula.rule`; `pb_hr_fullandfinal` overrides only `action_process` on the batch. **No collision
with `source_binding*`, `raw_data_topup_json` or `source_origin`, and no override of anything whose
signature changes.**

## Architecture

### 1. Binding — two Chars and a stamp on `hr.formula.rule`

```python
source_binding      = Selection([('excel','Spreadsheet column'),
                                 ('feed','Connected system key'),
                                 ('rule','Rule output')])   # empty = match by name, as before
source_binding_key  = Char
source_binding_origin = Selection([('user',…),('board',…),('import',…),('migration',…)])
source_binding_date = Datetime
source_binding_uid  = Many2one('res.users', ondelete='set null')
```

**The key is a Char, never a foreign key.** A spreadsheet header and a feed key have no record to
point at, and a `rule` binding pointed at `hr.api.transformation.rule` would recreate precisely the
failure S2 spent a phase repairing: `ondelete='set null'` silently forgetting 23 wires. A rule's
durable identity is already its `output_key`. Dangling becomes a computed *observation*
(`binding_dangling`), not data loss.

Constraint: key required when the kind is set; both must be empty unless `column_type == 'input'` —
a calculated component cannot be bound.

### 2. Two raw blobs, not one merged blob

```python
# hr.payroll.import.line
raw_data_topup_json = Text(default='{}')
source_origin = Selection([('primary',…), ('topup',…), ('both',…)], default='primary')
```

The primary blob is **never written by the top-up**. On a single-source run `raw_data_json` is
bit-identical to today's and `raw_data_topup_json` is `{}` — so neutrality is a property of the shape,
not a claim to be tested, and a top-up can never regress a run that already worked. It also keeps the
losing value recoverable for the `ignored` report, which last-writer-wins merging would have
destroyed.

`get_topup_data()` mirrors `get_raw_data()`. Origin of a key is a lookup, not a stored map: primary
blob → the batch's own `source_type`; top-up blob → the top-up's kind.

### 3. Merge, without unlinking

The primary loaders are **not refactored** — their `unlink()` stays, because re-running the primary
*is* a fresh run. Each one's identity-extraction block is extracted verbatim into a small method
(`_identity_from_file_row`, `_identity_from_store_row`) so the top-up shares it rather than growing a
second copy that drifts (MF31). The two loaders extract identity *differently* — the file loader
consults field mappings, the store loader falls back to the external id — and that difference is
preserved rather than unified, because it is real.

`action_top_up_from_data_store()` / `action_top_up_from_file()`:
- match an incoming row to an existing line on normalised employee code → email → name;
- **match** → write `raw_data_topup_json`, set `source_origin='both'`. `raw_data_json` untouched;
- **no match** → create a line with an empty primary blob and `source_origin='topup'`. An employee
  present in only one source still produces a line, flagged — never silently absent;
- untouched lines keep `source_origin='primary'`;
- re-running a top-up **replaces** its blob rather than accumulating. Merge is keyed, not appended.

### 4. Precedence — the bound branch, in front of an untouched ladder

For one input component, one employee. `B` = the binding. `PRIM`/`TOP` = the two blobs.

```
STEP 1 — ENTERED ONLY IF B IS SET
  side_b := blob whose origin == B.kind      (kind 'rule' reads the feed side)
  side_o := the other blob
  v_b := lookup(side_b, [B.key])
  v_o := lookup(side_o, today's candidates)
  v_b present -> value=v_b, src=B.kind, via='binding'
                 ; if v_o present -> ignored = {src, key, value}
  else v_o present -> value=v_o, src=origin(side_o), via='fallback', fell_back=True
  else -> via_hint='binding_empty', fall through to STEP 3

STEP 2 — UNBOUND. TODAY'S LADDER, UNCHANGED, over PRIM then TOP.
STEP 3 — NOTHING ARRIVED. TODAY'S TAIL, UNCHANGED.
```

**Why a single-source run cannot change**, four independent ways: Step 1 is guarded on `B is set` and
nothing has a binding until a user or the migration creates one; Step 2 is the existing ladder with
`TOP == {}`, i.e. today's code over today's data; Step 3 is untouched; and `input_values` is assigned
from the same `normalize_input_value` call sites. **The `ignored` path is S2's, reused — not a second
implementation.**

### 5. Migration — bind only what is provable

Back-fill `source_binding` per input rule carrying a `data_source_field`, in this order: matches an
active rule `output_key` on the config's connector → `('rule', v)`; matches a connector catalogue path
→ `('feed', v)`; appears in the config's most recent excel batch headers → `('excel', v)`; **otherwise
leave unset.** An unset binding is honest and costs nothing — Step 2 resolves it exactly as today.
Guessing here would put a wrong word on a chip on five screens. `source_binding_origin='migration'`,
per-DB counts logged, `table_exists`-guarded, idempotent, writes only where the binding is empty.

## Numbered test cases

1. **Neutrality A — byte-identity**: recompute all 35 payobook lines; `input_values` and computed
   values byte-identical to the pre-S1 baseline.
2. **Neutrality B — the bound branch is never entered** on a single-source run. Instrumented via a
   counter the resolver increments in Step 1, asserted zero. *Two independent proofs, not one.*
3. Loader-identity extraction is a pure move: `_identity_from_file_row` re-derives the stored
   `employee_code` / `employee_name` / `employee_email` for all 35 existing payobook lines.
4. Binding wins over a name-matched header in the other blob; the loser is recorded as `ignored`.
5. Bound side empty, other side has it → value taken, `fell_back: true`, both keys recorded.
6. Bound side empty and other side empty → `via='binding_empty'`, value = the same default an unbound
   component would have got.
7. Merge: employee in primary only → `source_origin='primary'`, resolves as today.
8. Merge: employee in top-up only → a line exists, `source_origin='topup'`, primary blob `{}`.
9. Merge: employee in both → `source_origin='both'`, both blobs present, primary blob unchanged.
10. Re-running a top-up replaces rather than accumulates.
11. Re-running the **primary** load clears the top-up (a fresh run is a fresh run).
12. `binding_dangling` true for a `rule` binding naming no live rule output.
13. A binding on a calculated component is refused by the constraint.
14. Migration binds only provable cases; leaves the rest unset; counts logged.
15. Three batteries green.

## Deploy + verification

Ledger ritual: rsync → `chmod -R a+rX` (CR6) → park tabs (CR20) → stop → zero pids by PID → detached
`systemd-run` with **`sudo -u odoo`** (MF35) over **abm acme payobook payobook_template** → read the
log not the sentinel (MF9) → start → **`sudo -u postgres psql` verify `latest_version` on all four**
(MF17). Recompute gates run on **payobook** (S7). The database is the oracle (MF37); every live
exercise runs in a rolled-back transaction and is proven by a before/after count.

## Report back

Both neutrality proofs; the end-to-end dual-source run with what each side contributed and what fell
back; tests 1–15; manifest versions; commit hash; deviations; new S-gotchas.
