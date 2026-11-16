# Rize Vietnam workbook refresh — 16 November 2026

Applied the clear differences in the owner's new Vietnam workbook to **rize**
on **Payobook19v2**, serving **https://rize.payobook.com**. This was a client-data
update. No addon code, schema, service settings or other tenant data changed.
Unrelated local working-tree changes were preserved.

## Upgrade coordination

Work paused at the owner's request while another session upgraded the server.
The earlier rehearsals rolled back; no employee updates were committed before
resumption. Before continuing, checks found no pending module changes or active
upgrade process. The service restarted at 19:50 Sydney time on 16 November,
module loading completed successfully, and the Rize login page returned HTTP 200.
The live data was re-read and a new database backup taken after that upgrade.

## Applied changes

Reviewed 133 Vietnam rows against the previous supplied workbook and current
production data. Changed 38 employee records:

- Applied 36 revised, unique global employee numbers to `employee_id`.
- Preserved every existing country/payroll code in `barcode`; populated the
  corresponding Vietnam ID field for 37 records. One global number already
  matched, so only its Vietnam ID field needed population.
- Resolved one reporting manager using the corrected email and matching name.
  Coach, leave, expense and attendance approvers were preserved.
- Applied one clarified work location.

The new status, probation-result and contract-date entries already matched the
saved records. Previously authorised contract-response dates were preserved;
unchanged master dates did not overwrite those decisions. Blank or placeholder
cells did not erase saved information. No new employees, contracts, departments,
payslips or payroll payments were created.

Five revised global-ID values are each duplicated across two source employees;
those revisions remain unapplied. A historical rehire identity remains open.
The new `Sheet4` has two unlabelled numeric columns: its meaning was not supplied,
so none of its values was imported. The dependent-detail sheet was unchanged.

## Verification

A rollback rehearsal passed before the production transaction was committed.
A separate fresh session verified 798 employee field values across all 38 changed
records, including the manager and global numbers. Thirteen protected tables
retained identical hashes, including contracts, compensation components,
payslips, payroll inputs, leave, departments and bank approval records.

One existing settlement automatically refreshed its related employee-code label
and write metadata. Every other settlement field, including all financial and
calculation values, was verified unchanged. The related-field behaviour was
identified during rehearsal and explicitly checked rather than treating the
whole settlement table as unchanged.

October, November and December payroll eligibility was unchanged in all four
countries. November remains Vietnam 69, India 29, Singapore 2 and Indonesia 106.
Bank approval RD00288 remains pending; no bank approval was performed.

## Report and permanent evidence

The existing private HTML report now carries the 16 November date and concise
tables of outstanding actions only. The resolved manager question was removed.
The duplicate ID questions and unlabelled sheet question were added. Completed
records remain omitted. HTML structure and links passed validation.

Local report, private and excluded from this commit:
`RIZE/Updated Data/Rize - Data update and client confirmations - 14Nov2026.html`.

Permanent evidence:
`Payobook19v2:/odoo/archives/rize-vn-update-20261116/`.
The archive retains the supplied workbook, reviewed plan, executed maintenance
script, rehearsal, committed before/after receipt, fresh verification, report
and two database backups. The post-upgrade pre-update backup is
`rize-after-upgrade-before-update.dump`. Rize backups do not expire automatically.
Source SHA-256:
`c8e6f5ecca6214c4b6faa88b6d45ee0c13c110af6c520ea58c27e578331cf7b1`.

Chrome screen verification was attempted, but the computer-use guard blocked
interaction because another user/session was changing Chrome. No UI verification
is claimed for this follow-up. Database verification and report validation
completed successfully. No PNG or screenshot files were generated.
