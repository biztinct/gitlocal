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
