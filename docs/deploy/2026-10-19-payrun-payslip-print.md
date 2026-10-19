# Payslip printing from the full pay run

The Rize Vietnam run 1591 had 63 computed draft payslips, but its full form
provided no payslip print button. The Print menu contained only payroll summary
reports. The legacy country batch printer also filters drafts out, so approving
or confirming the run would have been required to use that separate route.

Pay Runs `19.0.3.0.5` adds a visible **Print Payslips** button. It downloads one
PDF of the run's computed, non-cancelled slips in any review/approval stage,
without changing the run or slip states. Uncomputed slips are skipped; empty or
entirely uncomputed batches explain that amounts must be computed first.
Printing uses the existing formula-aware report and each slip's own saved
amounts/configured document, with the native report as the fallback when the
formula engine is absent. No approval, payroll amount or access rule changes.

Five new regression tests cover draft/state neutrality, correct payslip IDs
when the caller's active record is a pay run, cancelled/uncomputed exclusions,
waiting/approved slips, useful empty-run errors, imported layouts and saved
amount rendering. All five pass against the staged code. The existing 96
Pay Runs tests passed on that same implementation; the final combined suite
and deployed Chrome/PDF checks will be recorded after rollout.

Deployment scope: latest combined custom addon state on Payobook19v2, including
concurrent payroll preview changes, with database upgrades and deployed tests
on payobook, payobook_template, abm, p0clone and rize. Full content hashes,
installed module versions, cron activation and business rows are checked.

The deployed Chrome check exposed a second failure: the server's distribution
wkhtmltopdf build uses unpatched Qt and refuses multiple HTML input documents.
The first rollout's single-slip and HTML tests did not exercise that engine
limitation. Pay Runs `19.0.3.0.6` joins the batch report bodies into one HTML
input, retaining the report's head/assets and an explicit page break before
each following slip. This is scoped to this button's payslip reports; the
original record IDs remain available to the existing PDF processing. A sixth
regression renders an actual two-slip PDF with the installed engine, instead
of relying only on HTML or report-action assertions. All six staged tests pass.
