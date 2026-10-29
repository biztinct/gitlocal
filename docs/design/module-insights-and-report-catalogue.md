# Module Insights and existing report catalogue

The left menu keeps the same workspaces. Each reporting workspace gets one
**Insights** lens with **Overview**, **Explorer** and **Reports** sections. The
central Insights workspace also has a searchable **Reports** catalogue. Reports
open the existing action in its original module, and record-bound PDF actions
remain on their original forms.

| Workspace | Existing report actions linked from Reports | New Explorer source |
| --- | --- | --- |
| People | Workforce Insights, employee records, contracts | `hr.employee` |
| Workforce | Workforce Insights, Time, Time Off | `hr.attendance`, `hr.leave` |
| Payroll | Payroll Report, Salary Components Analytics, Payroll Explorer | Existing `pb.explorer` fact engine |
| Expenses | Expense claims, Business Trips | `pb.expense.claim`, `pb.business.trip` |
| Hiring | Hiring numbers | `pb.hiring.requisition` |
| Talent | Goal numbers, Goal reviews | `pb.goal.set` |
| Learning | Training numbers, Required training, Training assignments | `pb.training.assignment` |

The precise XML IDs are the `REPORTS` entries in
`pb_insights/models/module_insights.py`. The catalogue resolves each action at
read time, so an optional module contributes no broken link. The receiving
action retains its own permissions and export controls. The central catalogue
only lists areas the caller may read.

## Measure contract

Every measure has a named source, a company filter, a date or an explicit
current snapshot, a visible description, and a list of permitted breakdowns.
The server validates the measure, breakdown, time mode and period; it never
accepts a model or field name from the browser. Counts are over the named
records. Learning completion uses assignments given in the period and excludes
approved extensions from its denominator, matching Learning numbers. Claim
amounts are shown only when the selected companies' claims have one currency.

**Active employee records** counts current active `hr.employee` rows. **Employees
with a running contract** counts active employee rows whose current contract is
open. Neither is the Payroll Explorer's **people paid**, which counts people
on actual pay runs. Historical monthly bars are offered only for event dated
measures. Current status and current goal progress are labelled as such, so the
interface does not manufacture a past status from today's value.

The first six month Overview cards and the configurable Explorer use the same
definitions. Chart and table are views of the same returned rows. If more than
24 rows exist, the chart states the overflow and the complete table remains
available. Existing report routes, PDF actions, Excel downloads and saved
links are left in place.
