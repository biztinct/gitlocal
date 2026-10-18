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
latest combined repository code will be deployed to `rize`, `payobook`,
`payobook_template`, `abm` and `p0clone`; no Vietnam client records are copied.

Pre-deployment validation: 94 targeted Odoo tests passed against the staged module
on Rize, covering the input-only list and counts, legacy mappings, mutation guards,
journey guardrails, mapping defects and record sources. Python syntax and
`git diff --check` passed.

Deployed test results and the Chrome end-to-end check will be recorded here after
the rollout. Deployment includes database and addon backups, module version
verification, and full-row hashes of nine business/configuration tables in every
target database.
