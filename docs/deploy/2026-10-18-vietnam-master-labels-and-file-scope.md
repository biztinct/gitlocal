# Vietnam master headings and selected workbook mappings

The owner requested the original August FINAL v3 payroll headings in the schema,
automatic matching input connections, and removal of old templates' fields from
the selected-file mapping and Journey views. This follow-up targets configuration
4760 (`RIZE_VIETNAM_MASTER_V3`) only in `rize`; shared fixes go to all five
installed databases. The owner has activated the configuration since the prior
installation. This change preserves that state and the payroll population.

## Configuration

`prepare_rize_vietnam_labels.py` reads the unchanged master workbook and produces
`docs/configuration/rize-vietnam-master-labels.json`. It retains Vietnamese and
English words, normalizing whitespace only. Where the workbook repeats a leaf
heading, the merged section or currency supplies the distinguishing suffix.
The existing mapping screens do not switch component names by parsing brackets;
no language-switching logic is added.

The guarded `align_rize_vietnam_master.py` defaults to a complete rollback. Its
Rize-only patch aligns 74 existing component definitions (67 changed names) and
33 input bindings. Codes, column letters, formulas, types, payroll roles, native
record mappings, dependent details, contract amounts and template layouts remain
unchanged. Registered tax dependents stays separate from imported detail count.
The original HC context components and recurring settings are retained.

The selected source catalogue has 74 Salary headings with physical columns and
the employee-row range 9–78. Forty calculated/generated columns are hidden;
34 inputs remain and 33 are connected. Period remains unmapped because the run
supplies its period. Formula results are never mapping targets. The insurance
salary column mixes entered amounts and one formula; its optional Fixed base
input remains explicit and separate from the calculated Insurance salary result.
Phone allowance and USD output columns remain calculated even where the source
uses literal zeroes for inapplicable employees.

## Shared behavior

- Connections shows the selected file's actual columns and wires. It does not
  recreate missing source cards from another template's saved bindings. Other
  scheme inputs and Constants have independent collapsed sections, with search
  revealing matching fields. Input mappings do not invoke constant conversion.
- Journey shows this file's connected components and their saved-record
  destinations. Other workbook inputs are folded away and are not falsely
  reported as deleted sources. Connected feeds, transformations and pay-period
  sources remain visible.
- Re-reading identical workbook bytes preserves reviewed multi-row metadata.
  Replacing the workbook changes the source scope without deleting bindings.
- Multi-sheet imports preserve each physical column before duplicate headings
  can overwrite values. A numbered column guide is skipped, so it does not
  become an employee. Generated monthly-file alias folding also removes any
  wire whose helper source was folded away.

## Validation before deployment

Six isolated XLSX classification tests and the JS mapping/constant checks pass.
The staged Odoo suite passes 132 tests: selected-file Connections and Journey,
real Excel parsing, protected template/records behavior and native dependent
count. The dry-run patch passes all 96 saved payroll scenarios, loader controls
for repeated Others, insurance and currency columns, unchanged records import,
and full-row hashes of nine business/mapping/layout tables. No payroll is run.

The active configuration currently has no assigned payroll population; its
downloads contain zero employees. The earlier 70-person roster is still saved
as a Draft preview and is not activated or assigned by this labeling change.
This follows the owner's current state, rather than silently changing it.

Deployment, final Chrome checks and protected backup receipts are recorded below
after completion.
