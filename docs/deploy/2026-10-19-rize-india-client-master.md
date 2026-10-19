India client payroll rebuild, 19 October 2026
==========================================

The owner requested a new configuration rather than inheriting the existing
India definition. Client sources are the final August payroll XLS and the
India worksheet in the employee-master XLSX. Master IDs and reviewed names
are authoritative; original payroll codes remain reference aliases. The
ambiguous stipend identity remains pending by the owner's final decision.

The metadata definition contains no employee or payroll fixtures. Private
fixtures, import plans, workbooks and reconciliation evidence remain outside
Git. Installers assert database `rize` and default to rollback. Definition
creation verifies that business tables and the previous definition are
unchanged. Master changes use Records Desk's published approval route, with
ordered identity renames to preserve unique badges. The earlier active India
definition is archived for reference when the reviewed new scheme activates.

Configuration: 134 components (114 inputs, 15 formulas, five explicit source
parameters). There are four Time fields, 19 monthly adjustments and a protected
Employee records worksheet. Annual target variable compensation is separate
from actual payouts. Salary TDS, profession tax and employee PF are approved
monthly inputs because the workbook does not supply their calculation. Explicit
signed rounding adjustments preserve the row-formula differences. Historical
PF constants require review for later-period statutory changes.

Generic workflow fixes
---------------------

* Dated payroll populations, monthly templates and previews use actual contract
  overlap. Closed contracts with known end dates remain available for valid
  historical periods. Future hires, expired periods, Draft and cancelled
  contracts are excluded. The native payslip contract resolver follows the
  same rule. Period-free legacy callers retain their existing population.
* Contract currency follows its explicitly selected payroll country, with
  company currency as the fallback. The non-stored currency field changes
  denomination and money precision, never converts or rewrites amounts, and
  does not activate currencies. India wages retain INR cents inside a company
  whose base currency is VND.
* Four older wizard test fixtures now use isolated companies, so tests of the
  native/single-scheme path do not depend on the client database containing no
  other active payroll schemes.
* Both employee-count previews refresh when dates or the selected scheme
  change, including entry from Templates. Scheme coverage carries the same
  dates as eligibility. Automatic month labels follow date changes while
  custom batch names remain intact. Outdated asynchronous replies cannot
  overwrite a newer scope selection. The selected card shows dated coverage
  rather than its all-period count. Nine browser-unit cases cover these paths.
* Required monthly components retain missing values instead of silently
  defaulting to zero. Review highlights them and the server refuses payroll
  computation until supplied. An explicit zero is valid; it does not carry
  forward into the next month. Three transaction cases cover the distinction.

Validation before deployment: 182 deployed-database regression cases passed
against staged code; 27 client scenarios and 378 exact calculation comparisons
passed. Record import dry-run verified 35 master profiles, including eight
inactive profiles, and 27 historical-payroll employees. No business record
changes were committed by these dry runs.

Versions: `om_hr_payroll` 19.0.1.8.3, `pb_hr_payroll_base` 19.0.1.4.1,
`pb_payrun_wizard` 19.0.1.32.7. Shared code targets are payobook,
payobook_template, abm, p0clone and rize. Client data and new configuration are
restricted to rize. Final deployment, Chrome workflow and reconciliation
receipts will be recorded after verification.
