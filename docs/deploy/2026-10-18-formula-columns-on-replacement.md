# Calculated Excel columns remain excluded after file replacement

Formula-only Excel columns were already hidden, but a newly saved copy of the
Vietnam master lost its reviewed physical-column metadata. The generic reader
could then mistake numbered heading guides or unkeyed footer values for input
values, and confuse repeated currency/`Others` headings. Replacing identical
worksheet data with a different ZIP comment reproduced 40 hidden columns becoming
28 and exposed Total monthly income and Assessable income.

Every fresh/replacement XLSX now receives physical column positions and resolved
merged headings. Numbered heading guides are excluded from detection. Employee
rows determine whether footer literals belong to a calculation; missing/error
input checks retain all rows. Exact, unambiguous calculated schema names also
exclude pasted output values. Duplicate heading aliases follow the loader's
actual last-occurrence value instead of pointing to a neighboring input.

Saved files, replacement files and loaded batch files share the same catalogue
and formula classification. All/search/mapping status filters, suggestions,
wires, Journey and the mapping creation endpoint use the resulting exclusion.
A failed formula inspection refuses mapping instead of exposing unknown columns.
The approved mixed Employee ID, basic salary and Reporting Manager inputs remain
eligible and retain data checks. Constants keep their existing collapsed section.

`pb_formula_studio` is version `19.0.1.202.7`; no data migration is required.
The deployment scope is the latest combined code on `rize`, `payobook`,
`payobook_template`, `abm` and `p0clone`. Vietnam business data remains only in
Rize. The user's currently selected consolidated workbook is preserved.

Pre-deployment validation: 166 targeted Odoo tests passed against the staged module
(Excel on-ramp, clean mapping lists, loaded batch columns, employee mapping guards and Journey), including
fresh upload, identical replacement, newly saved replacement, duplicate headings,
merged currency headings, pasted outputs, alias guards and mixed inputs. A
rollback-only check using the real ten-sheet Vietnam calculation master returned
52 hidden columns before and after a newly saved replacement, with identical
visible fields. Python syntax and `git diff --check` passed.

Implementation commit `c83ac7828` synchronized the latest combined 149 modules /
4,901 application files. Formula Studio is upgraded on all five databases and
the deployment-status check reports nothing pending. Protected database/addon
backups and manifests are retained at
`/odoo/backups/vn-formula-upload-code-20261018-230715/`. Nine business/configuration
table hashes matched in all databases before restart.

Deployed validation passes 166 tests per database, 830 total, with no failures or
errors. The real-master replacement probe also passes against deployed code and
rolls back. Chrome verifies first upload, changed-byte Replace file, All/Mapped/
Unmapped, formula-name search and reloading the saved replacement. Both calculated
fixture columns remain hidden, including the pasted-zero output; the three input
columns remain available. Browser warning/error logs are empty. The isolated Rize
test configuration was removed. Screenshots were inspected in memory and no test
PNG files were written.
