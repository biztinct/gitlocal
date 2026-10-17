# MAPFIX Phase A — Readable short codes + orphan-safe rename of every existing code

> **STATUS: BUILT, DEPLOYED AND VERIFIED — live on abm · acme · payobook · payobook_template
> (2026-08-23).** pb_hr_payroll_formula 19.0.1.69.0 · pb_formula_studio 19.0.1.115.0.
> abm 64/99 renamed · payobook 152/1360 renamed + 5 contract components moved alongside ·
> 0 refused · 0 withdrawn · 0 orphans · compute-neutrality diff EMPTY (19 real payslips + a
> synthetic fingerprint of all 19 configurations) · 32/32 live tests on abm · batteries green.
> Deviations and outcomes are recorded in `MAPFIX_LEDGER.md` (MF1–MF10).

Read `docs/handovers/MAPFIX_LEDGER.md` FIRST (owner decisions MF-A1/A2, verified facts, inherited
COLROLES rules incl. CR6 chmod + psql version check, CR20 websocket-hang, CR33 RPC password).
Also read `docs/FORMULA_ENGINE_CONVENTIONS.md` C5 and C13 — they contradict each other and this
phase resolves it.

## Scope

1. One shared code generator producing readable ≤12-char codes (MF-A1), used by every import path.
2. `rename_component` extended to be orphan-safe + batched.
3. A migration that renames every existing code on all 4 DBs (MF-A2), atomically and verifiably.
4. A shape constraint on `hr.formula.rule.code`, after fixing the live violators.
5. Fix C5 in the conventions doc; fix the underscore-emitting legacy generator.

**Binding non-goals**: NO mapping-canvas work (Phase B). NO error-dialog work (Phase C). Do NOT
change what any formula COMPUTES — only the identifiers it computes under.

## Build spec

### A1. `build_component_code()` — one generator to replace four

New module `pb_hr_payroll_formula/models/component_code.py` (pure Python, stdlib only, so the
batteries and tests can import it without Odoo). Public API:

```python
NOISE_WORDS = {'constant', 'const', 'total', 'amount', 'value', 'column', 'col',
               'cho', 'cua', 'va', 'theo', 'cac', 'nhan'}   # tune with care, see A1.5
MAX_LEN = 12
MIN_LEN = 6          # hard floor — below this a code drops out of the fuzzy header fallback
def build_component_code(label, existing_codes=(), reserved=()) -> str
```

Algorithm (deterministic, documented in the docstring):
1. `strip_accents(label)` — **reuse** `column_role_classifier.strip_accents` (:207-214); it already
   handles `đ`, which NFD does not decompose. Import it, do not re-implement.
2. Tokenise on non-alphanumerics. Preserve tokens that are ALL-CAPS acronyms (`HQCV`, `SI`, `KBT`)
   and numeric tokens (`10.5%` → `105`) verbatim.
3. Drop leading noise words ONLY when something meaningful survives (never return empty).
4. Budget `MAX_LEN` across the surviving tokens: give the first token more characters, later tokens
   fewer, acronyms/numbers always kept whole. Aim for a readable prefix per word, not initials.
   The owner-approved targets are the acceptance test (A1 test 1) — tune the budget until they pass:
   - `Chi trả phép năm chưa sử dụng` → `CHIPHEPNAM`
   - `Tỷ lệ % tạm ứng thưởng HQCV` → `TYLETUHQCV`
   - `Constant SI-HI-IU Total 10.5%` → `SIHIIUTOT105`
   - `Employee Status` → `EMPSTATUS`
   Exact equality on all four is NOT required if the spirit holds (readable, ≤12, distinct); if you
   deviate, record the actual outputs in the report so the owner can see them.
5. Pad to `MIN_LEN` if shorter (repeat/extend from the source letters, never with `X` padding if
   real letters remain).
6. Never start with a digit (prefix `C`). Never contain `_`. Uppercase A-Z0-9 only.
7. Reject candidates equal to any `reserved` value (pass the config's column letters) and dedupe
   against `existing_codes` via the existing `_dedupe_code_c5` semantics (letter suffixes) — move
   that helper into this module and have `multisheet_import_wizard._dedupe_code_c5` delegate, so
   there is one implementation.

**A1.5 — the substring/lexicon trap (do not skip).** Short codes newly risk matching `_group_for`'s
substring lexicon (`pb_formula_studio.py:78-92`: `SI HI UI PIT TAX DED NET GROSS TOTAL`) and
`_is_employee_code_rule`'s markers. A code like `SIHIIUTOT105` legitimately lands in Deductions; a
code like `TAXITIEN` (from "Taxi") would land there WRONGLY. Mitigation: in `_group_for`, prefer
`column_role` (already authoritative after COLROLES) and only fall back to the lexicon — check
whether COLROLES Phase 2 already did this; if it did, just verify. Note any grouping drift in the
report.

Wire the generator into: `multisheet_import_wizard._generate_code` (:3264-3294),
`formula_import_wizard._generate_code_from_label` (:1881-1902), and
`excel_connector._generate_code_from_header` (:944-981 — **currently emits underscores**, a live C5
violation; make it delegate). Keep each call site's signature so callers are untouched.

### A2. `rename_component` — orphan-safe + batch

Extend `pb_formula_studio.rename_component` (:3833-3918). Everything it does today stays. Add, in
the same transaction:
1. **`hr.contract.advantage.template`** — if a template exists whose `code` == old code, rename it
   to the new code (its `hr.contract.advantage` lines follow by FK; `advantage_template_code` is a
   stored related and recomputes). If a template already exists under the NEW code, do not merge —
   abort that rename with a clear message naming both. **This is the single most important addition**
   (ledger: matched by string at `payroll_import_batch.py:3083-3108`).
2. **`hr.salary.rule`** with that code in the same company (`payroll_import_batch._get_or_create_salary_rule`
   creates them by string) — rename if found.
3. **`hr.formula.budget.line.code`**, `hr.formula.boundary` `boundary_key` stamps, shadow
   `component_code`, simulation/comparison `headline_code`, mapping-template `target_code`,
   `hr.formula.sample.data.line.rule_code`/`column_code` — rename where they match, scoped to the
   config where the model allows scoping.
4. **Do NOT touch** historic `hr.payslip.line.code`, `formula_computed_values`/`formula_input_values`
   JSON on existing payslips, or `hr.formula.rule.version.snapshot_json` — those are historical
   records of what was computed under the old code and must stay truthful. Say so in the docstring.
5. New `@api.model rename_components(self, config_id, pairs)` — batch wrapper taking
   `[{rule_id, new_code}, …]`, validating the whole set first (shape, uniqueness, no collision with
   column letters, no pair mapping two rules to one code), then applying each via the single-rename
   path. All-or-nothing: raise before writing anything if any pair is invalid.

### A3. The migration (MF-A2 — the risky one; earn the owner's trust)

`pb_hr_payroll_formula/migrations/19.0.1.69.0/post-codes_become_readable.py` (manifest → 19.0.1.69.0).

- Iterate every `hr.formula.config`. For each, compute proposed codes for ALL its rules with
  `build_component_code`, seeded so the generator sees the config's own column letters as
  `reserved` and its already-assigned new codes as `existing_codes` (stable order: `sequence, id`).
- **Skip a rule entirely** if its current code already satisfies the new shape AND is ≤12 chars
  (idempotency: a second run must change nothing).
- Apply renames through the SAME logic as `rename_components` — but the migration cannot call the
  studio model cleanly at `post-` time if pb_formula_studio isn't loaded; therefore **put the rename
  engine in `pb_hr_payroll_formula`** (e.g. `models/component_code.py` + a small model method on
  `hr.formula.rule`, `_rename_code(new_code)`) and have `pb_formula_studio.rename_component`
  delegate to it. This keeps one implementation and makes the migration self-sufficient.
- **Formula rewriting**: formulas mostly reference column LETTERS, so most renames are metadata-only
  — but where a formula references the old code as a bare token, rewrite it (same regex + the
  `config_letters` guard as `rename_component`). Run the batteries afterwards (below).
- **Report**: log per DB and per config — total rules, renamed count, skipped count, and the
  full old→new list at INFO for the first N configs (cap the log volume). Also log every advantage
  template renamed and every rule where a template collision forced a skip.
- `table_exists` guard; idempotent; never touch a rule whose config is archived? — no, DO include
  archived configs (their codes matter if reactivated) but log them separately.

### A4. Constraint + violator cleanup

- Fix `pb_formula_studio.add_component` (:6904-6907) to use `build_component_code` instead of
  `%s_%s` underscore suffixes.
- Fix demo data `pb_hr_payroll_formula/data/demo_formula_config.xml:80,91,102,113`
  (`SI_EMP`→`SIEMP`, `HI_EMP`→`HIEMP`, `UI_EMP`→`UIEMP`, `TOTAL_DED`→`TOTALDED`) and any formula in
  that file referencing them.
- THEN add `@api.constrains('code')` on `hr.formula.rule` enforcing `^[A-Z][A-Z0-9]*$` (underscore-
  free, no spaces). **Enforce shape only — NOT non-substring** (ledger: substrings are safe; a
  non-substring constraint would reject legitimate sets and contradicts C13). Reuse the message
  style of `formula_config_template._assert_codes_convertible` (:185-212).
- Update `docs/FORMULA_ENGINE_CONVENTIONS.md` C5 (:110-116) to match C13 and reality: underscore-free
  is the hard rule; non-substring is a preference; add the ≥6-char floor and the
  "must not equal a column letter" rule. C5 currently states the opposite of C13 — fix the doc.

## Numbered test cases

Pure Python (`pb_hr_payroll_formula/tests/test_component_code.py`, MUST run and pass locally with
`python3`):
1. The four owner-approved labels → readable ≤12 codes (record actual outputs).
2. Accent folding: no accented input ever loses a letter silently (`ả`→`A`, `đ`→`D`); assert the
   old lossy behaviour is gone for a table of ≥15 VN labels.
3. Invariants over a corpus of ≥60 labels (build it from the real ABM + VPTQ headers found in the
   repo/DB): every code is `^[A-Z][A-Z0-9]*$`, ≤12, ≥6, underscore-free, unique within the batch,
   never equal to a supplied column letter.
4. Determinism: same input list → same output list, twice.
5. Idempotency: feeding generated codes back in as labels leaves them unchanged.
6. Collision pressure: `Constant SI-HI-IU Total 10.5%` and `Constant SI-HI-UI Total 21.5%` produce
   DISTINCT codes (the transposition case from the owner's screenshot).
7. Dedupe uses letter suffixes, never digits-that-truncate, never underscores.

Regression gates (MANDATORY, must exit 0):
8. `python3 pb_hr_payroll_formula/tools/excel_semantics_battery.py`
9. `python3 pb_hr_payroll_formula/tools/import_resolution_battery.py`

Odoo TransactionCase (`tests/test_code_rename.py`, coded for CI + run live per the COLROLES method):
10. `rename_component` renames the matching `hr.contract.advantage.template` and existing
    `hr.contract.advantage` lines still resolve (create a contract with a component, rename, re-read
    the amount through `_transform_data_to_formula_inputs` → same value).
11. Rename aborts cleanly when a template already exists under the new code.
12. Historic `hr.payslip.line.code` and payslip JSON are NOT rewritten (assert old code survives).
13. `rename_components` batch validates all-or-nothing (one bad pair → nothing written).
14. Constraint rejects `SI_EMP`; accepts `SIEMP`.
15. Migration idempotency on a fixture config: run twice, second run reports 0 renames.

## Deploy + live verification

1. Local: tests 1-9 green BEFORE deploying. Do not deploy on a red battery.
2. **Capture before-state**: for each DB, `psql` dump `id, config_id, code` for every
   `hr_formula_rule` plus `id, code` for every `hr_contract_advantage_template`, to
   `/tmp/mapfix_before_<db>.txt`. Also record, for abm config 7 and one payobook config, a computed
   payslip's input_values/line amounts (via the browser RPC) as the compute-neutrality baseline.
3. Deploy per ledger ritual (chmod, sentinel, psql `latest_version` on all 4).
4. **Verify after-state**: same dumps to `/tmp/mapfix_after_<db>.txt`; report counts renamed per DB;
   assert every advantage template whose code changed has a matching rule with the same new code and
   that no template was orphaned (a template code with no rule AND no lines is fine; a template with
   lines and no matching rule is a FAILURE — report it loudly).
5. **Compute neutrality**: recompute the same payslip(s) and diff against the baseline — identical
   amounts. This is the acceptance gate for MF-A2. If it differs, investigate before proceeding.
6. Chrome-MCP on abm (action-742, park other tabs on about:blank first per CR20): components rail
   shows the new short codes; open a contract (Employee → Contracts) and confirm the CONTRACT
   COMPONENTS list shows the shortened codes against the same names and amounts.
7. Commit (feature-scoped, includes the ledger + this handover, no push).

## Report back

Actual generated codes for the four acceptance labels + a sample of 15 real ABM ones (old → new);
battery exit codes; per-DB rename counts; orphan check result; compute-neutrality diff (must be
empty); any grouping drift from A1.5; deviations; MF-numbered gotchas appended to the ledger; files
touched; manifest versions; commit hash.
