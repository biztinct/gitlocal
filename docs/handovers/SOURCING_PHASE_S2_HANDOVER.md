# SOURCING Phase S2 — severed mappings, lineage data, widened connector gate

**Scope:** make severing visible and reversible, repair all 23 severed mappings on the two live
databases that have them, give transformation rules a real lineage field, constrain `output_key` on
the way in, and open the connector gate that has been closed since it was written.

Design: `docs/handovers/SOURCING_DESIGN.md` §7 (severed), §8 (lineage), §6 (gate).
Ledger: `docs/handovers/SOURCING_LEDGER.md` — S1–S8 bind, plus CR1–CR33 and MF1–MF41.

## Binding non-goals

- **No bindings** (`source_binding`) — S3. **No UI, no serializer, no chips** — S4/S5.
- **No repair of anything that is not severed.** Severed := `target_rule_id IS NULL` **AND**
  `target_rule_code` non-empty (ledger **S6**). The 185 payobook / 26 abm rows with a NULL FK and no
  remembered code were never wired and are not this phase's business.
- **No renaming of existing `output_key` violators** (owner ruling O-5) — report only.

## Order within the phase — non-negotiable

The remembering compute ships **before** anything writes `target_rule_id`, because the repair itself
writes `target_rule_id`, and under today's stored-related definition that write recomputes the related
and **erases the remembered code the repair depends on**. Ship the compute first and the evidence
survives its own repair. Proven by test 1 below, which severs through the ORM and asserts survival.

## Verified facts — established 2026-08-24, do not re-derive

| Fact | Evidence |
|---|---|
| `target_rule_id` read in **one** payroll place, behind the gate | `payroll_import_batch.py:2724` |
| `target_rule_code` / `target_column_letter` are **stored relateds**; all readers are reads (views + cockpit), no writer | `integration_field_mapping.py:88-99`; `integration_views.xml:258,286-287`; `pb_integrations.py:363,377,426-427` |
| Only inheritor of the mapping model is `pb_demo`, which adds `is_demo` and nothing else — **no MRO collision** | `pb_demo/models/demo_integrations.py:84-86` |
| Rename ledger: `hr.formula.rule.version`, `reason='rename'`, `snapshot_json` holds the **pre-rename** code + `rule_id` | `formula_rule_version.py:17-60`; written via `formula_version_reason='rename'` |
| `_rule_check_key` is the converter contract on a key; `_KEY_RE = ^[A-Z][A-Z0-9]*$` | `pb_integrations/models/rule_composer.py:55, 670-714` |
| `_trace_cells` reads 4 sources, caps at 4, resolves against a **row** | `api_transformation_rule.py:858-884` |
| Underscored placeholder + help | `views/api_transformation_rule_views.xml:59`; `api_transformation_rule.py:312` |

### The live picture (read-only, 2026-08-24)

**`hr.formula.config.connector_id` is empty on every config on both databases.** The scope the design
sketched — "configs whose `connector_id` is the mapping's connector" — finds **zero** candidates and
would return 23 false no-matches. Corrected scope in §2.

| | abm | payobook |
|---|---|---|
| severed | **15** (connector 3, company 1) | **8** (connector 2 "Demo HRIS", company 1) |
| configs | 1 — cfg 14, company 1, 54 inputs | 18 — none in company 1; matches land in cfg 18, **company 2** |
| tier 0 (exact) resolves | 6 | 7 |
| tier 1 (rename ledger) resolves | 9 | 1 |
| tier 2 needed | 0 | 0 |

**All 23 resolve uniquely at tier 0 or tier 1. Tier 2 is never reached — and must not be reordered:**
a SQL dry-run of legacy-label inversion on payobook returns **9** candidates for `EMPCODE`, **9** for
`FULLNAME` and **15** for `BASICSALARY` across its 18 configs. Tier 2 first would have made three
wrong wires. It stays last and refuses on ambiguity.

**`output_key` violators — payobook only: `NUM_TAX_DEPENDENTS`, `TOTAL_LEAVE_DAYS`, `TENURE_YEARS`,
`NET_SALARY`** (4 of 14). abm 0/8, acme 0/0, payobook_template 0/0. Underscored keys are the hard
half of the converter contract — they survive raw into the eval, raise `NameError` and read 0. Per
O-5: **reported, not renamed, not blocked.**

## Architecture

### 1. Remembering computes (ships first)

`target_rule_code` and `target_column_letter` become `store=True` computes that copy from the FK when
there is one and **keep their stored value when there is not**. A full recompute is then a no-op,
which is what makes the field safe to have as a compute at all.

Reading the field inside its own compute is a recursion, not a read, so the previous value is fetched
**straight from SQL** into a dict first. Records with a `NewId` are skipped (nothing stored yet).

```python
@api.depends('target_rule_id', 'target_rule_id.code')
def _compute_target_rule_code(self):
    stored = self._stored_char('target_rule_code')
    for m in self:
        m.target_rule_code = (m.target_rule_id.code if m.target_rule_id else False) \
                             or stored.get(m.id) or False
```

Plus `is_severed` (stored, `@api.depends('target_rule_id','target_rule_code')`) so the cockpit ledger
can facet on it in S5 without a Python filter.

### 2. The repair matcher — scope, then tiers

**Candidate scope**, widest-first with the narrowest that yields a match winning:

1. input rules of configs whose `connector_id` **is** this mapping's connector — the correct link,
   currently unpopulated everywhere, kept because it is what new data will use;
2. input rules of configs in the **connector's company**;
3. input rules of **any** config in the database, marked `cross_company`.

Scope 3 is what payobook needs (connector company 1, rules in company 2) and it is not a guess: the
codes match exactly and one is confirmed by the rename ledger. It is reported distinctly so a human
sees it.

**Tiers**, in this order, each requiring a **unique** hit or returning `ambiguous`:

| Tier | Verdict | Method |
|---|---|---|
| 0 | `exact` | a candidate rule whose `code` == `target_rule_code` |
| 1 | `renamed` | `hr.formula.rule.version`, `reason='rename'`, `snapshot_json->>'code'` == `target_rule_code`, whose `rule_id` still exists and is a candidate |
| 2 | `legacy_label` | a candidate rule whose `component_code.legacy_component_code(rule.name)` == `target_rule_code` — the pre-MAPFIX generator (`re.sub(r'[^A-Za-z0-9]','',label).upper()[:40]`), inverted |
| 3 | `no_match` / `ambiguous` | write nothing, say so |

`legacy_component_code` goes in `component_code.py` beside the generator it reproduces — plain Python,
so the battery tests it without a database.

**`_severed_verdicts()`** computes the table and writes nothing. **`action_repair_severed()`** calls
it and applies only `exact` / `renamed` / `legacy_label`. Preview is therefore always available even
though the owner has authorised applying directly.

### 3. Lineage data

`_trace_cells(row)` splits: `_consumed_field_names()` returns every field path the rule reads, in
mention order, deduplicated, **uncapped, no row required**; `_trace_cells` calls it and keeps the
display cap of 4. `consumed_field_paths = fields.Json(compute=..., store=True)` depends on
`filter_conditions`, `value_steps`, `builder_mode`, `excel_formula`. The compute must never raise —
the existing bare `except` around `compile_rule_formula` is kept, because a rule with a broken draft
formula must still save.

### 4. `output_key` constraint — create/write only

`@api.constrains('output_key')` on `hr.api.transformation.rule`, delegating to the same checker
`rule_composer._rule_check_key` uses (moved to the model; the composer calls the model, so there is
one rule in one place — MF31). Odoo fires a `constrains` on create, and on write only when a depended
field is in `vals` — so an existing violator still saves unrelated fields, which is exactly O-5's
ruling and the shape of MAPFIX F3. Underscored/`NUM_DEPENDENTS` placeholder and `help` corrected.

### 5. The widened gate

`if config.connector_id and self.source_type in ('connector', 'api_data_store'):`

Proof is an integration test on **payobook_template** (0 mappings, 0 batches, nothing to disturb), not
a live behaviour change: there is no `api_data_store` batch on any of the four databases, so the
widened branch is unreachable by existing data.

**Precedence — corrected during implementation (ledger S9).** This spec first claimed the
`if rule.code not in input_values` guard means "a mapping can only fill a gap, never overwrite a
header match". That is backwards, and the live gate test caught it. The mapping block runs BEFORE the
input loop and assigns unconditionally; the loop's guard then SKIPS a code the mapping already filled.
So **an explicit mapping beats a name-matched header**, and the header fills the gaps. That is the
correct way round — it is the owner's "per-component binding decides" — but it was unobservable while
the gate was shut, so it is now stated in the code rather than left to be re-derived. Because a
mapping can now displace a value that genuinely arrived, the displaced value is RECORDED as
`ignored` in provenance (reusing S1's `ignored_side`, until now unreachable) rather than dropped:
the owner's rule is that the unused side is reported, never silently discarded.

**Prediction to verify, not assume:** the post-repair recompute on payobook should be **empty**,
because all 6 payobook batches are `source_type='excel'` and the gate does not open for them. A
non-empty diff means something is wired that I have not understood — stop and report.

## Numbered test cases

1. **Ordering**: sever a mapping through the ORM (`mapping.target_rule_id = False`) and by deleting the
   rule; `target_rule_code` survives both, and `is_severed` becomes True.
2. A full `_compute_target_rule_code` recompute over every mapping is a **no-op** (no value changes).
3. `legacy_component_code` reproduces the pre-MAPFIX generator for all 15 abm labels (pure python).
4. Tier 0/1/2 each resolve in isolation; ties return `ambiguous` and write nothing.
5. The three payobook collision cases (`EMPCODE`, `FULLNAME`, `BASICSALARY`) return `ambiguous` at
   tier 2 — proving the ordering is what protects them.
6. `_severed_verdicts()` writes nothing (DB checksum before/after).
7. Repair on abm: 15/15 applied, every rule output then has a live consumer.
8. Repair on payobook: 8/8 applied, cross-company flagged.
9. `_consumed_field_names()` is uncapped and ordered; `_trace_cells` still caps at 4.
10. `output_key` constraint refuses underscored/lowercase on create and on write-of-that-field;
    **permits** writing an unrelated field on an existing violator.
11. Widened gate: a connector mapping applies on an `api_data_store` batch; an unmapped component
    still name-matches; an explicit mapping BEATS a name-matched header and the displaced value is
    recorded as `ignored`; a config with no active mappings is unaffected; an `excel` batch still
    applies no mappings at all.
12. **Neutrality on payobook**: recompute after repair — expected empty, per the prediction above.
13. Three batteries green.

## Deploy + verification

Ledger ritual: rsync → `chmod -R a+rX` (CR6) → park tabs → stop → zero pids by PID → detached
`systemd-run` with **`sudo -u odoo`** (MF35) over **abm acme payobook payobook_template** → read the
log not the sentinel (MF9) → start → **`sudo -u postgres psql` verify `latest_version` on all four**
(MF17).

**Snapshot before repairing** (coordinator's requirement): dump `id, connector_id, target_rule_id,
target_rule_code, target_column_letter, active_state` for every mapping on abm and payobook to a file
on the server, so any repair is reversible by inspection. The database is the oracle (MF37).

## Report back

The 23-row verdict table (id, remembered code, matched rule, tier, scope); the post-repair recompute
diff on payobook; tests 1–13; manifest versions; commit hash; deviations; new S-gotchas.
