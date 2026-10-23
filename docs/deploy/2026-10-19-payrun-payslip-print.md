# Payslip printing from the full pay run

The Rize Vietnam run 1591 had 63 computed draft payslips, but its full form
provided no payslip print button. The Print menu offered payroll summaries.
The legacy country batch printer also excluded drafts. After adding the
button, the live Chrome test exposed a second failure: the server's unpatched
Qt build of wkhtmltopdf rejects multiple HTML input documents.

Pay Runs `19.0.3.0.6` adds **Print Payslips** to the full run. It prints computed,
non-cancelled slips in review/approval stages without changing the run or slip
states. Uncomputed slips are skipped; entirely uncomputed batches explain that
amounts must be computed first. The existing formula report supplies each
slip's own saved amounts and configured document, with the native report as the
fallback when the formula engine is absent. Approval and access rules are
unchanged.

For this button's batch reports, the PDF hook keeps the first document's head
and assets and joins the report bodies into a single HTML input with explicit
page breaks. Original record IDs remain available to the existing PDF
processing. Single slips and unrelated report types retain their existing
rendering path.

Implementation commits: `b5e29b45b` (button/action) and `2b1ff2dcd` (PDF engine).
The combined rollout also preserves the concurrent payroll preview, required
monthly input and isolated test-fixture changes. No unrelated local output
files or workbook deletions were included in these commits.

All **126 deployed tests passed**: the complete 102-test Pay Runs suite on
Rize, and six batch-print regressions on each of Payobook, Payobook Template,
ABM and p0clone. The regressions cover draft/state neutrality, payslip IDs in a
pay-run context, cancelled/uncomputed exclusions, waiting/approved slips,
empty-run messages, imported layouts, saved amounts and actual multi-slip PDF
rendering with the installed engine.

A payroll-staff account resolves all 63 slips, renders the PDF and sees all
63 identities/net-pay cards in the report HTML. Every net amount matches its
saved line, and the aggregate matches the run's net KPI. Chrome's Print
Payslips action downloaded an 11,775,347-byte, 63-page A4 PDF. Its SHA-256 is
identical to the batch PDF inspected visually on pages 1, 2 and 63. The screen,
run and all 63 slips remain Draft; totals are unchanged. Browser download-event
capture timed out, so the completed file in Downloads was verified directly.

The shared deployment target is Payobook19v2, serving payobook,
payobook_template, abm, p0clone and rize from one addons directory. Full initial
database backups and rollout evidence are under
`/odoo/backups/payslip-print-20261019-132953/`. The final PDF correction's code
backup, file manifest and 126-test receipts are under
`/odoo/backups/payslip-print-20261019-135153/`; it references the verified full
database backups. Each rollout checks business-row fingerprints and restores
the original cron activation. The three PDF QA PNGs were deleted, and no
browser screenshots were saved. The downloaded PDF is retained for the user.

An intermediate committed application snapshot was `174c082d8`: 149 custom modules /
4,907 files, including the concurrent dated-coverage label. Its asset-only
follow-up upgraded every target to Pay Run Wizard `19.0.1.32.7`, with the app
remaining online. Receipt: `/odoo/backups/payslip-print-20261019-140230/`.

That online rollout's final Rize fingerprint guard detected concurrent work:
another session computed India run 1975, creating 28 slips and updating the
134 rules of its own configuration 6382. A field-level comparison with the
initial full backup confirms all pre-existing payslips and runs, including the
reported Vietnam run, are unchanged. The changed rules belong exclusively to
India and changed only evaluation metadata/generated salary-rule links. The
concurrent work is preserved; the receipt records the audit exception rather
than claiming identical full-table hashes. Four other targets passed the
strict unchanged checks. Uncommitted work in the other session was preserved locally until its
subsequent combined rollout below.

The final shared runtime rollout is `05e1856fb`, including the concurrent
import-identity fix in Payroll Formula `19.0.1.149.3`, deployed and upgraded on
all five databases. Its complete receipt is under
`/odoo/backups/rize-india-payrun-code-20261019-141501/`. It independently reports
unchanged business rows for its own deployment window.

Combined regression checks found that Import Identity's fixtures reused real
ABM employee names/badges. Commit `b8179d8db` gives them isolated companies and
unique synthetic badges within the app's 18-character alphanumeric constraint.
This changes only tests. The shared test file was deployed without restarting
the app; all 13 identity cases pass on each of the five databases (65 cases).
An overlapping p0clone test run caused a database deadlock; the remaining
checks were rerun serially with no failures or errors. In total, 191 targeted
deployed checks pass: 126 Pay Runs cases and 65 identity cases.

The final independent content/version audit matches all 149 custom modules /
4,907 files against combined commit `b8179d8db`, with zero file differences and
zero installed-version differences on all five databases. The final manifest
and verification are retained with the protected payslip rollout receipts.
Chrome was checked again on the final runtime rollout: its second 63-page PDF
is byte-identical to the visually reviewed batch, with the run still Draft and
its totals unchanged. No QA PNG or browser screenshot files remain.
