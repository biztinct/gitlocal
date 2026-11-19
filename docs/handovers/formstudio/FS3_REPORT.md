# FS-3 — Form builder on the contract screens (`pb_form_studio_contracts`) — report

**PAUSED (owner pause, 2026-11-19)** — done / next:

- DONE (code, WIP commit on `fs-3`): bridge module `pb_form_studio_contracts` 19.0.1.0.0 —
  host `contract` (locked Terms groups + open "Company details", `copy_custom=True`,
  Country of Work via computed non-stored `hr.contract.pb_country_of_work_id` from
  `employee_id.payroll_country`); side panel `_cd_terms` group built from engine `render`,
  `_cd_coerce_term` via engine `_pbfs_coerce`, `lookup_contract_m2o` for custom link comodels
  (reader's rights), `_cd_propose` widened so custom fields wait for the approver (R9),
  proposal rows in words + comparable snapshot; contract page (`get_contract_detail` → `pbfs`
  + `PbFieldGrid` read mode + wand); full form page via lazy native-view registration;
  renewal carry in `create_contract` (wizard + "Make it permanent"); Contracts board filters;
  JS/XML patches (CdEditor: Yes/No, long text, file; wand; "Add your own fields" card); SCSS;
  test suite (18 cases).
- Local DBs kept for resume: `fs_3_t` (bridge installed), `fs_3_base` (engine only, no
  bridge), `fs_3_bl` (baseline run). Config in the session scratchpad (`fs3/odoo.conf`, port 8733).
- Baseline (no bridge, `/pb_contracts,/pb_people_advanced,/pb_contract_lifecycle,/pb_form_studio`):
  1 failed + 5 errors of 95 — `pb_contracts` test_cd1 test_01 (`fillin` key, pre-existing);
  `pb_form_studio` test_04b/21–24 errors: the engine's busy guard reads `pg_locks` for the WHOLE
  cluster, so another builder's pay-run tests in another database make it refuse (engine bug,
  merge-time task M2: filter `pg_locks.database` to the current database — tenant clones share
  OIDs, so on the live server one tenant's pay run would block the Form builder in every tenant).
- Last test run: 13 of 18 pass. OPEN:
  1. test_02 — on approval the apply re-judges and refuses the custom field ("not something this
     screen can change"): during the apply `render` does not return the field (likely the apply
     runs in a different company/env, so the layout for `self.company` is not found) → fix the
     apply path (e.g. `with_company(contract.company_id)` in `_fs3_render`).
  2. test_04 — the contract manager gets no custom group when a second field name is `_2`
     (registry leftover between tests, or the same company issue) — investigate with the debug
     message now in the test.
  3. test_03b — golden read of all stored fields fails on one column (pick the field list from
     columns that exist); test_03 "Make it permanent" now runs with the company set — recheck.
  4. test_10 — PO files not generated yet (export .pot, write vi/id).
- NEXT: fix 1–4, full suite + touched suites vs baseline, `-u` keep test (8), browser walk
  desktop + phone (11), self-review, finish this report, push, drop the three local DBs.
