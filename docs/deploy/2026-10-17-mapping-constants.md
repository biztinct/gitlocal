# Optional constant destinations in spreadsheet mapping

Formula components stay hidden from Spreadsheet columns → Scheme. Ordinary
inputs appear first. Constants are available in a separate Constants group at
the bottom, collapsed by default. Opening it displays each name and fixed value;
search and mapped/unmapped filters also apply to the group. Expanding and
collapsing write no configuration data.

Drawing a spreadsheet source to a constant opens the native confirmation dialog.
Confirming "Change to input and map" changes that component to Input, keeps the
previous constant as its default, and creates the source binding atomically.
Cancelling makes no write call. Formulas retain the same component references.
The ordinary mapping API still refuses constants and formulas. The explicit
conversion API checks scheme ownership, current type and the reviewed value;
a failed binding rolls back the conversion. This is an explicit change to the
component's definition, never an import silently overriding a true constant.

The change is shared application code in `pb_formula_studio`. Deployment scope
is Payobook19v2 and all six installed databases: payobook, rize,
payobook_template, abm, p0clone and lrp4clone. Deploy the latest combined module
under the shared lock, preserve concurrent changes, restart Python and refresh
backend assets on all six. No model/schema or module-data upgrade is required.
The Vietnam Draft's three parameters are not converted by deploying this UI.

Validation covers the collapsed group and confirmation/cancel flow in Node,
backend conversion with unchanged dependencies and fallback, explicit zero,
stale values, wrong scheme/type, and rollback after a failed mapping. Chrome
must verify the Vietnam group and complete cancel/confirm mapping on an isolated
review fixture, followed by fixture cleanup. All test PNG files are removed.
Deployment and verification receipts are recorded below after execution.

## Deployment and verification

Implementation commit **af0ef8ae0**, approval-route regression correction
**924d11195**, and explicit Cancel action **e6b62db57** were deployed from the
latest combined branch 19.1. The initial full-module comparison found exactly
seven changed files. They were deployed under
`/tmp/payobook-studio-deploy.lock`; the complete module snapshot matched the
server after synchronization. A shared service restart loaded the backend.
The subsequent UI-only Cancel change refreshed assets without another restart.
Final asset version: `20261017-mapping-constants-e6b62db57` on **payobook, rize,
payobook_template, abm, p0clone and lrp4clone**. Existing module versions,
business counts and active-cron counts were preserved. Service is active and
Rize's login endpoint returned HTTP 200. No schema or module-data upgrade ran.

Four deployed backend regressions passed on every database: the filtered
catalogue and ordinary mapping guard; explicit conversion with missing-value
fallback, supplied values and zero; stale/wrong-scheme/formula rejection and
rollback after a failed binding; and the tenant's actual live-scheme approval
route. Fixtures run in rolled-back transactions. The first conversion fixture
was initially active and correctly met Payobook's live-scheme approval guard;
the successful conversion fixture now explicitly uses Draft and the separate
regression verifies the live approval behavior. No approval bypass was added.

The staged and deployed Rize tests passed all 30 Vietnam payroll scenarios.
Vietnam still has 93 input components, 20 formulas and three unchanged constants,
is Draft and has no assigned live population. Business counts remain
107 employees / 102 contracts / 183 payslips / four runs / 4,234 contract
advantage rows. Tenant configuration values, roles, mappings and source keys
were not edited by deployment or by the Chrome checks.

Node tests exercised the real canvas view getters and Mapping Studio dialog
callback: collapsed/default visibility, expansion order, no-write cancellation,
and explicit conversion including a zero fixed value. Python/JavaScript syntax,
XML parsing, SCSS compilation and diff checks passed. A Hoot DOM regression was
also committed; the actual deployed DOM and user interactions were checked in
Chrome rather than reporting an unexecuted Hoot suite as passed.

Chrome verified Vietnam's 93 ordinary input cards, a Constants (3) button with
`aria-expanded=false`, and no constant-value cards until expansion. Expansion
shows all three names/values beneath the inputs. Formula destinations remain
absent. The user tab is left on Vietnam with constants collapsed.

A disposable Draft configuration 4653 was used for the complete Chrome mapping
flow. Cancel left its factor as Constant 12 with no source rows. Confirm changed
it to Input, default 12, bound to `Salary|Fixture months factor`; its dependency
formula `=A2*B2` stayed unchanged. The deployed parser/evaluator produced 1,000
for salary 100 and uploaded factor 10, and 1,200 when the factor was omitted.
The factor became an ordinary input card with a real wire. The fixture and its
rules were deleted after both evidence checks, and the test tab was closed.
Browser error/warning logs were empty. No test PNG files were retained.

Protected module backups, deployment snapshots, asset refresh receipts,
per-database regressions and fixture evidence:
`Payobook19v2:/odoo/backups/mapping-constants-20261017-af0ef8ae0/`.
