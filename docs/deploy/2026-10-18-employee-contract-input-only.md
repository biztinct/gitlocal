# Employee and contract mappings: inputs only

The Employee & Contract board included calculated payroll results under All and
counted them in its category pills. It now exposes only input components in its
left column, counts and wires, including when Payroll is revealed. Formula and
fixed-value definitions remain unchanged. Existing legacy mappings are retained
in storage but cannot restore an ineligible card or wire.

The creation endpoint rejects formula and fixed-value sources before any employee,
contract, bank or contract-component mapping is changed. This also protects calls
from a browser tab opened before deployment.

`pb_formula_studio` is version `19.0.1.202.6`. No data migration is required. The
latest combined repository code is deployed to `rize`, `payobook`,
`payobook_template`, `abm` and `p0clone`; no Vietnam client records are copied.

Pre-deployment validation: 94 targeted Odoo tests passed against the staged module
on Rize, covering the input-only list and counts, legacy mappings, mutation guards,
journey guardrails, mapping defects and record sources. Python syntax and
`git diff --check` passed.

Implementation commit `c13745ee1` synchronized 149 modules / 4,901 application
files. Formula Studio is upgraded on all five databases, the service is active,
and the deployment-status check reports nothing pending. Protected database and
addon backups, manifests and receipts are retained at
`/odoo/backups/vn-record-filter-code-20261018-215009/`. Full-row hashes of nine
business/configuration tables matched in every database before service restart.
The final comparison against those backups found only `write_date` timestamp
refreshes on Payobook employees and Rize component definitions. All other fields
and row identities are unchanged; the audit timestamps are preserved and recorded
separately in the final receipt.

Deployed validation passes **94 tests on each database, 470 total**, with zero
failures or errors. Live Rize checks verify all 138 inputs are available when
Payroll is revealed, all 42 formula and 5 fixed-value components are excluded,
and all 47 non-input sources are refused by the creation endpoint. All 185
definitions and the existing 106 storage mappings remain intact. Payroll's
category count is 34 inputs rather than 81 total definitions.

Chrome end-to-end validation passes All (138), Mapped (106), Unmapped (32), and
search. Searching BHXH finds only the participation input; searching the exact
`BHXH (SI) 8%` result finds zero cards. The restored All view shows 138 input
cards and no sealed/formula cards. Browser warning/error logs are empty.
Screenshots were inspected in memory; no test PNG files were written. Temporary
staging is removed after the evidence is copied into the protected backup.
