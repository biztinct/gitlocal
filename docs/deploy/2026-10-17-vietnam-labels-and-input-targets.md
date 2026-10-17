# Vietnam source labels and spreadsheet input destinations

The owner could not recognize payroll component names against the supplied VN
HC spreadsheet. Source-derived display labels now retain the Excel wording and
case, with whitespace normalized. The three ID visibility qualifiers are
omitted: Position ID, Employee ID, Country-Based Employee ID. The second use of
column X is labelled Legal entity Date of Joining (employee), distinguishing it
from the contract-start destination without hiding its source terminology.
65 source-derived rules are covered; 62 labels differ from the current Draft.
Component codes, source keys and formula references stay fixed.

The Spreadsheet columns → Scheme board now offers input components only on its
right side, using the existing `wirable_only` catalogue option. Calculated and
constant components remain in the configuration, full catalogue and Journey.
The existing server-side `_mc_refuse_sealed` guard continues to reject a link to
a formula or constant, including requests from an old browser bundle. The
regression checks both rejection without source writes and a successful input
mapping. No model/schema, asset or module-data upgrade is needed.

The HC Annual Gross salary(Fixed+var), Monthly Gross salary(Fixed+var), annual
variable targets and CTC remain unmapped references. Displaying a spreadsheet
heading on the left does not require creating a payroll input for it. These
figures can support separate reconciliation; they must not become automatic
monthly pay alongside the salary and actual-payment components.

## Deployment scope and preservation

Shared application target: Payobook19v2, complete latest committed
`pb_formula_studio` tree at `/odoo/odoo-server/addons/pb_formula_studio`, serving
payobook, rize, payobook_template, abm, p0clone and lrp4clone. Restart the shared
service to reload Python. Recheck branch and server differences under the
existing deployment lock; preserve concurrent changes.

Tenant configuration/artifact target: rize only, Draft configuration 4639,
`RIZE_VIETNAM_HC_202610`. `tools/align_rize_vietnam_labels.py` snapshots all
stored noncomputed rule fields other than name, source rows, destination rows,
configuration state, old VN rules and business counts. It asserts equality
before committing the labels and replacement attachments 30900/30901. It does
not apply the original blueprint's destination flags over the owner's edits.

The two delivery workbooks retain the approved 70-person roster (68 Active,
2 Notice Period), ten remaining review decisions and blank monthly pay inputs.
Only names and identity headings change. The four affected table headers are
synchronized with native Excel table metadata. New local copies are placed in
`outputs/rize-vn-labels-20261017/` to preserve the owner's open earlier files.

The owner has edited identity destinations since the original proposal:
Employee ID (D) currently targets native Employee Id, while Country-Based
Employee ID (E) is a contract text component. This task preserves that choice.
Before any record import, review the match key: source E was unique across all
127 people; D had duplicated/missing/error values. The 70-person workbook is
still a review artifact, not authorization for record imports or activation.

## Validation

Local Python/Node syntax checks and `git diff --check` must pass. Workbook QA
compares every cell and verifies panes, validations, sheet states, table names,
ranges, styles and header metadata; only 103 review-label cells and five monthly
heading/instruction cells differ. Visual previews verify readable labels.

The tenant dry run passed all 30 stored payroll scenarios, joined 70 unique
review IDs through the deployed parser and preserved 107 employees, 102
contracts, 183 payslips, four runs and 4,234 contract advantage rows. Deployment
and Chrome results are recorded after the production checks. Test-generated
PNG files are removed before completion.
