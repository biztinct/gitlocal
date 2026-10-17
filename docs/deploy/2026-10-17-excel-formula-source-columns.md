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
