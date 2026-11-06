# Payslip gross split — 20 October 2026

The owner approved the proposed layout in which gross pay is the whole and
deductions and net pay divide it. The previous strip gave net pay a fixed 38%
width, constrained deductions to 8–60%, and used the remaining width for gross.

## Result

`pb_payslip` 19.0.1.4.0 replaces that strip with a neutral gross heading and
100% label above two segments. Their widths use the actual, unrounded shares
of gross, including zero and sub-1% deductions. Exact amounts and rounded
percentage labels sit outside the segments. Employer contributions retain
their existing separate section. The summary reflows inside narrow dialogs
using its own container width.

Refunds, advances, zero/negative gross, negative net and other adjustments use
explicit calculation rows when they cannot form a normal two-part split.
The statement reads the existing pay-run/report deduction convention to keep
genuine refunds signed while preserving legacy mixed-sign charges. A zero net
line remains authoritative. Differences between gross, deductions and net
retain their sign and currency precision; an unexplained difference is labeled
as an adjustment. Full amounts retain the currency's decimal precision.

These changes read existing payslip lines and render the statement. Payroll
formulas and saved payslip amounts are preserved.

## Deployment

Implementation commit: `8b023e8833fe432bddad2557acda321cb083ac0e`.

The branch and origin were rechecked before deployment. The latest combined
custom-addon snapshot, 149 modules and 4,911 files, was synchronized to
`/odoo/odoo-server/addons` on SSH `Payobook19v2`. Only `pb_payslip` differed.
The module was upgraded on `payobook`, `payobook_template`, `abm`, `p0clone`
and `rize`. Assets were invalidated on each database and the service restarted.
Existing scheduled-job activation states were preserved. The service was
offline for 84 seconds during the upgrades and returned active.

All custom-addon hashes and installed versions match the combined repository
snapshot on all five databases. Deployment checks preserved the existing
business-row hashes, payroll counts, totals and contract wages. Full database
dumps, the previous addon snapshot, manifests and the deployment receipt are
in `/odoo/backups/pay-summary-code-20261020-075419`.

## Validation

- Six local JavaScript tests cover exact segment proportions, zero/tiny/large
  deductions, refunds, advances, negative amounts, reconciliation, cents and
  directional signs. Python and XML parsing and the Git whitespace check pass.
- Deployed `/pb_payslip,/pb_payruns:TestPayBands` tests pass on every database:
  28 per database, 140 total, zero failures and errors. Tests preserve subtotal
  behavior, currency context, mixed-sign historical deductions and classified
  refunds, and add zero-net, prior-payment and fractional-adjustment coverage.
- Sixty before/after database checks of counts, maximum IDs, timestamps and
  financial sums are unchanged after the rollback tests.
- Chrome traversed Rize's run board, existing Singapore run and saved payslip
  dialog. Gross is labeled 100%; a sub-1% deduction has its actual width;
  exact employer-contribution cents remain visible. The summary has no
  horizontal overflow at desktop, 390-pixel and 320-pixel widths.
- Chrome opened an existing Payobook payslip with a mid-month advance and
  zero net pay. The explicit calculation rows reconcile, net remains zero,
  and the proportional bar is absent. Both Chrome tabs report zero console
  errors. Neither payroll computation nor approval was invoked in these UI
  checks.

The first, broad verification query attempted to sort complete payslip-line
JSON rows and exhausted available PostgreSQL temporary disk space. It was
read-only and terminated. The successful rerun used smaller aggregate checks.
The server has approximately 1 GB of free space; storage capacity remains an
operational follow-up outside this presentation change.

Temporary deployment copies of the 149 addons were removed after their hashes
were verified; backups and receipts remain. Test tabs were closed and the
viewport override reset. No test PNG or screenshot files were retained, and
pre-existing assets and unrelated workspace changes were preserved.
