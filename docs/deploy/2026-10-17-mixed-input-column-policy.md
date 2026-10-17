# Generated sequence and mixed input column policy

The owner approved hiding Sl No while retaining Employee ID, Reporting Manager
and Monthly fixed/basic salary as spreadsheet inputs. A single seed value must
not cause an otherwise generated serial sequence to appear as a payroll input.

The XLSX inspector now recognizes an exact generated sequence: one numeric seed
of 1 followed exclusively by contiguous formulas referencing the preceding row
in the same column and adding 1. Such a column follows the existing calculated
source exclusion, including aliases, suggestions, the Add column shortcut and
the direct mapping endpoint. There is no name or percentage heuristic. Multiple
entered values, another seed, gaps, different references and other arithmetic
retain the existing mixed/input classification.

Other mixed columns remain available. Their detail hint explains the number of
entered values and formula cells, and a separate collapsed Input data checks
section reports blanks and Excel error cells with up to ten cell addresses.
Counts use populated rows under actual headings, ignoring formatting-only rows
and headingless global parameters. They cover the whole selected file, including
inactive employees; blanks are not automatically treated as required-field
failures. Error checks identify Excel error values and literal error formulas
such as =#N/A; the inspector does not evaluate workbook formulas.

For the supplied Vietnam HC file, Sl No is hidden with the 17 formula-only
columns. The remaining three mixed inputs have these whole-file counts across
127 populated rows: Employee ID 22 blanks / six errors; Reporting Manager 35
blanks / zero errors; Monthly fixed/basic salary 16 blanks / zero errors. The
board has 120 source cards, 93 existing mappings, and 93 ordinary payroll inputs
plus three collapsed constants. The 20 calculated payroll destinations remain
excluded. No stored mapping, payroll configuration, employee, contract, salary
or workbook value is rewritten.

Deployment scope is the complete latest committed pb_formula_studio module on
Payobook19v2, serving payobook, rize, payobook_template, abm, p0clone and
lrp4clone. Recheck the branch and shared live module under the deployment lock,
preserve concurrent work, refresh assets on all six databases and restart the
shared service. No schema or module-data upgrade is required.

Before deployment, four isolated XLSX tests passed, including strict sequence
recognition, negative cases, real mixed values, error coordinates and blank-row
counting. Node checks for constants and blocked source aliases passed. Python
and XML syntax and SCSS compilation passed. Rollback-only staged Odoo checks
passed both source regressions and constant conversion; the real Vietnam board
preserved all 93 mappings and all 30 stored payroll scenarios passed.

## Deployed verification

Implementation **a3b63a544** was deployed from the latest combined branch 19.1
under `/tmp/payobook-studio-deploy.lock`. The live module differed in exactly
the five expected module files; the complete committed module was synchronized
and verified byte for byte. The shared odoo-server service was restarted and is
active. Assets were refreshed on **payobook, rize, payobook_template, abm,
p0clone and lrp4clone**, version `20261017-mixed-input-policy-a3b63a544`.
Module versions, business record counts and active cron counts were preserved.
No schema or module-data upgrade was run. Unrelated workbook deletions and
untracked Singapore/Vietnam output directories were left untouched.

Both deployed source regressions and constant conversion passed on every one
of the six databases. Fixtures were rolled back. The Rize checks confirmed
18 excluded source columns, 120 remaining cards, three retained mixed inputs,
the exact whole-file data-check counts above, 93 unchanged mappings and 96
destination payload cards (93 ordinary inputs plus three collapsed constants).
Sl No, Age and their bare, sheet and letter aliases were refused by the mapping
endpoint. Rule definitions, source bindings and configuration values were
unchanged; all 30 stored Vietnam payroll scenarios passed. Configuration 4639
remains Draft with no live assignments; Rize business counts remain 107
employees, 102 contracts, 183 payslips, four runs and 4,234 advantage rows.

Chrome loaded the deployed assets and verified the 18-column notice, absence
of Sl No/Age/Annual Gross salary cards, presence of all three approved input
columns, 93 ordinary payroll targets and collapsed Constants (3). Searching
Sl No returned no source card or Add column shortcut. The separate Input data
checks section was initially collapsed, expanded correctly and displayed the
six Employee ID error coordinates and the whole-file/optional-blank explanation.
Both searches were cleared and the review panel left open on the Vietnam Draft
tab. Browser warning/error logs were empty. No mapping was drawn or removed.
The visual check used an in-memory screenshot; no PNG or screenshot files were
created or retained by this test run.

Protected backup and source/asset/test receipts:
`Payobook19v2:/odoo/backups/mixed-input-policy-20261017-a3b63a544/`.
