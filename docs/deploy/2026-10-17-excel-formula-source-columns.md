# Exclude calculated Excel source columns from Mapping

The earlier filtering affected payroll destinations only. Excel headings such
as Age remained visible because the source catalogue retained headings and
cached values, without checking the underlying workbook cell types.

The Spreadsheet board now inspects the retained XLSX with formulas intact.
It locates the actual header row using the loader's known headings, scans all
data rows, and classifies columns from cell types. A formula-only column is
hidden, including aliases and orphan cards for previously saved bindings. It
is absent from suggestions and the Add column shortcut; the create endpoint
also refuses it. Existing bindings are preserved, with a count if hidden
columns have saved mappings. The board explains how many calculated columns
were hidden. No payroll parsing, computation, source file or configuration
values are rewritten.

Blank cells are ignored. Columns containing both entered values and formulas
are explicitly Mixed and remain available. There is no percentage threshold or
name-based inference. The owner was asked about mixed-column handling; pending
a different preference, preserve them with the Mixed label. The supplied VN
file contains 17 formula-only columns and four mixed columns: Sl No, Employee
ID, Reporting Manager and Monthly fixed/basic salary. Hiding a whole mixed
salary column because of one formula cell would also hide its entered salary
inputs. Age, Annual Gross salary, Service Period, CTC and the other 17
formula-only columns are excluded.

The same classification reads a selected saved template or an uploaded pay-run
XLSX, including files saved before this deployment. Sheet-qualified aliases
remain distinct. CSV and legacy XLS values do not carry inspectable XLSX cell
types and are not guessed to be formulas. Formula payroll destinations remain
hidden; the optional collapsed Constants group and explicit conversion flow
remain unchanged.

Scope: complete latest committed `pb_formula_studio` tree on Payobook19v2,
serving payobook, rize, payobook_template, abm, p0clone and lrp4clone. No schema,
module-data or tenant configuration migration. Restart Python and refresh assets
on all six databases, checking the branch/server state under the shared lock.
Preserve unrelated workspace changes and existing payroll data. Test PNG files
must not remain after validation.

## Deployment and verification

Implementation **906136573**, deployed with the fixture-schema correction in
**5d7266c99**, came from the latest combined branch 19.1. Under the shared
lock, production differed in exactly seven expected module files, including the
new formula-inspection helper. The full committed module was synchronized and
verified with zero differences. The shared service was restarted; backend
assets were refreshed on **payobook, rize, payobook_template, abm, p0clone and
lrp4clone**, version `20261017-excel-formula-sources-5d7266c99`. Module versions,
business and active-cron counts were unchanged. Service is active; the Rize
login endpoint returned HTTP 200. No schema/module upgrade or configuration
migration ran. Concurrent workspace deletions and untracked outputs were left
untouched.

The deployed source regression passed on all six databases: formula detection
beyond a blank first row, saved-template and uploaded-batch boards, hidden
formula source cards and aliases, preserved legacy bindings without orphan
cards/dangling wires, direct-RPC refusal, and mixed-value input acceptance.
Constant-to-input conversion with its previous default also passed on every
database. Test fixture writes were rolled back.

The real Vietnam board has **121 left cards** (previously 138), **17 hidden
formula-only Excel columns**, four Mixed columns, **93 unchanged mappings**,
and 93 ordinary destinations plus three collapsed constants. Age, Annual Gross
salary and their letter/sheet aliases cannot be mapped. No saved VN mapping was
hidden, removed or changed. Rule definitions, source rows and configuration
values were compared before/after the read and refused-write checks. All
30 stored payroll scenarios passed. Configuration 4639 remains Draft with zero
live assignments and business counts 107 employees / 102 contracts /
183 payslips / four runs / 4,234 contract advantage rows.

Chrome verified the 17-column notice, absence of exact Age and Annual Gross
source cards, absence of the "Use Age" add-column shortcut after searching,
the four Mixed badges, 93 ordinary input destinations and collapsed Constants
(3). Both searches were cleared and the Vietnam tab retained. Browser error and
warning logs were empty. The DOM and visual check used the deployed version.
No mapping was drawn or removed through the UI.

Local checks passed two isolated XLSX tests (section/header rows, blank cells,
late formulas, literal equals-text and same headings on different sheets), the
real JavaScript view/dialog/blocked-alias checks, Python/Node syntax, XML parsing,
SCSS compilation and diff checks. No test-generated PNG files were retained.

Protected backups, deployed source, asset-refresh receipts and per-database
regressions:
`Payobook19v2:/odoo/backups/excel-formula-sources-20261017-5d7266c99/`.
