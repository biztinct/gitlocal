# Rize client data refresh — 14 November 2026

Applied the owner's three updated client workbooks to **rize** on
**Payobook19v2**, serving **https://rize.payobook.com**. This was a client-data
operation, including the three new Vietnam employees' payroll enrollment.
No addon code or schema changed. Other tenants' client data was outside scope.
Unrelated working-tree changes were preserved.

## Applied data

- Reconciled 174 of 175 master rows. A historical identity that matches a
  current rehire remains a documented question; the current employment was
  preserved.
- Created six current employee profiles and 47 archived historical profiles.
  Historical profiles without supported agreements did not receive invented
  payroll contracts.
- Created 18 renewal contracts and six new-starter contracts. Activated five
  existing drafts and prepared one future contract for 19 November.
- Applied the owner's explicit treatment of uncertain Vietnam answers:
  use the contract-response dates/salary; end the three overlapping old
  contracts one day before the supplied renewal starts. Exact private values
  are in the client report and permanent audit, not this repository receipt.
- Saved supported profile, leaving-date, compensation and reporting-manager
  corrections. Refreshed 73 displayed job titles and the paying-scheme display
  for six new starters. Three further reporting managers were resolved using
  the supplied email and corroborating name.
- Submitted 20 bank-field changes for eight people through the existing
  second-person route, **RD00288**. These remain pending; no approval route was
  bypassed.

## Verification

Rollback rehearsal passed before committing the production transaction.
Fresh post-commit reads verified 1,138 field values, the three contract overlap
corrections, the future starter's date/salary/state, and the new India annual
compensation inputs. Follow-up checks covered displayed titles, currencies and
manager corrections.

November payroll eligibility:

| Country | Before | After |
| --- | ---: | ---: |
| Vietnam | 47 | 69 |
| India | 26 | 29 |
| Singapore | 2 | 2 |
| Indonesia | 106 | 106 |

Eligibility is not completed payroll or payment approval. The future starter
is not running before 19 November. Existing payslips, payslip lines, pay runs,
monthly inputs, leave, overtime, final settlements and formula configuration
were checked with unchanged hashes across ten business tables. Indonesia
employee and contract snapshots were preserved.

Chrome checks passed through the employee list and individual contract forms:
the running Vietnam renewal and wage, the future Vietnam agreement and wage,
and the new India employee's job title and INR display. The separate
"Contracts ending soon" cockpit returned empty content during navigation;
that cockpit issue was not changed by this task. No screenshot files were
saved or retained.

Shared server manifest versions matched all installed custom modules on
`payobook` (148), `payobook_template` (143), `p0clone` (143), and `rize` (146).
No addon upgrade or service restart was necessary for this data-only release.
ABM and its archive were not touched.

## Remaining items

The report identifies the 23 unanswered Indonesia contract questions, bank
approval RD00288, six new-starter department ambiguities, three India PF-basis
questions, remaining historical/identity questions, two reporting-line
questions, and the allowance classification requiring payroll review. It also
lists the five Vietnam entries already applied for client reconfirmation.

Client report (private, excluded from Git):
`RIZE/Updated Data/Rize - Data update and client confirmations - 14Nov2026.html`.

Permanent production backup and full evidence:
`Payobook19v2:/odoo/archives/rize-client-update-20261114/`.
The directory retains the verified custom-format pre-change database dump,
source archive and hashes, reviewed plan, executed maintenance program,
before/after receipts, and final checks. The Rize backup never expires
automatically.

## Department follow-up and concise report

The owner authorised resolving the six current starters' department assignments
using the supplied names and existing manager/colleague teams. All six were saved
in **rize** on **Payobook19v2**. No departments were created or merged. This was a
data-only operation; no addon deployment, schema upgrade or other tenant data
change was required.

A new permanent pre-change database dump, rollback rehearsal, before/after audit
and fresh-session verification are retained in the same archive under the
`department-fix-*` names and `rize-before-departments-20261114.dump`.
All six department assignments, identities, managers and paying schemes passed
fresh-read verification. Contract dates, wages, October–December payroll
eligibility and hashes of twelve protected tables were unchanged, including
bank approval records and contract compensation components.

Chrome showed the saved OpsX assignment for the Vietnam starter and Product &
Technology for the India starter. The report was refreshed and visually checked
in Chrome. No screenshot files were saved or retained.

At the owner's request, the private HTML now contains concise tables of
outstanding client answers and internal bank approval only. Completed department
assignments, resolved contract-overlap corrections, the supplied Board reporting
line and other records requiring no action are omitted. The previous report is
retained privately as `client-report-before-concise.html`; the current report is
`client-report.html` in the server archive and the same local client-report path.
