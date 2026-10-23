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
* Import identity matching first honours the explicitly mapped destination
  field after the connector's immutable source reference. A government-ID
  value on another employee cannot override a unique mapped employee ID.
  Two collision regressions preserve both destination priority and the
  existing connector/source identity checks.
  The previous setup's Government ID values that exactly equal their own
  original payroll code are cleared through Records Desk where the reviewed
  master provides no Government ID. Real government identifiers are preserved;
  payroll aliases remain in the dedicated information component.

Validation before deployment: 182 deployed-database regression cases passed
against staged code; 27 client scenarios and 378 exact calculation comparisons
passed. Record import dry-run verified 35 master profiles, including eight
inactive profiles, and 27 historical-payroll employees. No business record
changes were committed by these dry runs.

Versions: `om_hr_payroll` 19.0.1.8.3, `pb_hr_payroll_base` 19.0.1.4.1,
`pb_payrun_wizard` 19.0.1.32.7, `pb_payroll_templates` 19.0.1.2.16,
`pb_hr_payroll_formula` 19.0.1.149.3. Shared code targets are payobook,
payobook_template, abm, p0clone and rize. Client data and new configuration are
restricted to rize. Final deployment, Chrome workflow and reconciliation
receipts are recorded below.

Completed client setup and historical Draft
------------------------------------------

The new Rize configuration is 6382, `RIZE_INDIA_CLIENT_MASTER_2026`, named
Rize India Payroll Client Master 2026. It is Active; the earlier configuration
3941 is archived. Its consolidated source contains 35 people and 114 input
columns, with 114 spreadsheet bindings, 32 native record mappings and 59
relational contract component definitions. All formula outputs are excluded
from input and record mappings. The monthly workbook has four Time fields,
19 adjustment fields and a protected Employee records sheet; 87 configured
record fields accompany the pinned identity columns.

Records Desk RD00243 applied 628 reviewed values across 35 master profiles.
Eight inactive source people have archived profiles and Draft contracts.
RD00255 subsequently cleared 23 audited payroll-code placeholders from native
Government ID; actual government identifiers were preserved. Master employee
codes and names are authoritative, including the six reviewed code shifts and
the reviewed name correction. Original payroll codes remain dedicated
information aliases. The ambiguous stipend person remains pending and has no
new employee, contract or test payslip.

The owner confirmed that the August leaver's contract remains ended until
a rehire date is supplied. August retains valid historical pay and leave
encashment. August's dated population is 27; September and October are 26.
No speculative rehire was created.

Chrome's normal upload, monthly review, Compute with file, scoped Clean and
Run, exception review and Open Payroll flow produced Draft run 1996 with 27
unique employees. The disposable earlier Draft was replaced. Run 1996 is
labelled `Rize India · August 2026 TEST · Client comparison`; every payslip is
Draft. The importer matched all 27 identities correctly, including the two
previously affected by secondary Government ID collisions. It created no
employee or contract records. All 621 uploaded monthly values and all 378
source result controls match exactly. Totals in INR:

* Gross: 8,572,060
* Deductions: 2,272,657
* Net: 6,299,403
* Employer PF: 84,848
* Approved TDS input: 1,989,203

All 27 configured calculation scenarios pass; no payslip has formula errors.
The seven review notices are six unclosed workforce weeks and their summary,
which are informational for this historical Draft. No approval, payment,
accounting posting or payslip delivery was performed.

A fresh September download contains 26 people, 23 blank monthly inputs,
protected Employee records and a very-hidden issued receipt. August inputs
were not carried into September. Full hashes of employee, contract, contract
component, bank and dependent tables are identical before and after monthly
import/computation. The source workbooks are unchanged. The delivered filled
workbook preserves the native issued receipt, identity tokens and protection;
only the 621 numeric monthly cells differ from its original download.

Rize's other 92 employee core profiles and 82 contracts were preserved, as
were company country and currency. The four other databases have no India
client configuration or client-data import. Their 13 audited business tables
are unchanged, except for 21 employee write timestamps in payobook; comparison
against the initial backup confirms no employee business fields, identities,
new rows or removed rows changed there.

Code rollout backup: `/odoo/backups/rize-india-payrun-code-20261019-141501`.
The rollout updated the pending formula module in all five databases, preserved
business table hashes during deployment and restarted the service successfully.
Final verification covers all 149 custom modules and 4,907 repository files,
including concurrent work. Installed versions match and the service is active.

Deployed baseline regressions passed 248 cases per database across all five
targets. Final template/identity integration checks passed 99 cases each in
rize, payobook, payobook_template and abm. The broader final P0 suite passed
261 cases, including the 13 identity cases. All final results have zero failures
and zero errors. Concurrent test sessions initially caused P0 deadlocks; the
final clean rerun held an exclusive shared deployment/test lock. Nine focused
JavaScript preview cases passed. Chrome additionally verified dated counts,
normal keyboard custom-name entry, upload/review and Draft computation.

The combined application state includes identity-test isolation commit
`b8179d8db`. Final repository HEAD is linked by the completion commit and
verified against the same deployed application bytes. Private per-employee reconciliation evidence
and the user-facing workbooks remain outside Git. All six task-generated PNG
previews were removed; the final Chrome proof is a JPEG.
