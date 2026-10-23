# Payroll input changes and future-record decisions

The wizard computes a draft payroll from the workbook, then offers **Review
input changes** on both its computed result and exception-review steps. The
same review opens from **Input changes** on the batch form, the Runs card menu,
and the Runs quick look. A card badge surfaces unresolved changes and record
updates awaiting approval. Closing the wizard or review leaves the saved review
and all undecided cells available to another authorized payroll reviewer.

## Interaction and meaning

The review uses employee rows and input-field columns, Excel letters, frozen
employee names, search, field search, filters, per-cell selection, field-wide
selection, and bounded row rendering. Each mapped cell shows the payroll value
and its captured on-record value. Color always has a corresponding text label:

| Color | Meaning |
| --- | --- |
| Violet | Changed mapped value awaiting a decision |
| Amber | Excel-only input; enter it again for the next payroll |
| Green | Record update applied for future payrolls |
| Blue | Record update awaiting the existing approval route |
| Grey | Explicitly kept specific to this payroll |

Users can select different cells for **This payroll only** and **Keep selected
for future payrolls**. Both choices show a confirmation explaining the effect.
An optional note, actor, time, and update reference remain in the shared history.
Filtering clears selection so a hidden cell cannot accidentally be acted on.
The downloadable Excel review keeps the color coding and includes on-record
values and decisions in cell comments. Its Read me tab explains the comparison.

Excel-only values remain in this payroll's audit context; they do not become
reusable employee or contract fields. The UI explicitly explains the need to
supply them again or have an administrator establish a mapping. Blank workbook
cells never become record-erasure instructions; numeric zero remains a value.
Workbook context and uploaded values that payroll did not use are identified
explicitly.

## Persistence and safety

`pb.payroll.run.input.review` stores one server-owned snapshot per import batch.
It has no direct user ACL. Public facade methods check the actual batch/run,
company, payroll-run authority, and Records Desk permissions. Only explicit
scheme mappings and declared contract components confer update authority.

Wizard spreadsheet attachments use the existing one-time path. They capture
the baseline before processing and leave lasting record changes to the later
decision. Ordinary Import and connected-system processing retain their existing
behavior. Record updates use Records Desk's existing validation, approval,
per-value audit, and Undo machinery. No review action recomputes, approves, or
pays the payroll.

Decisions lock the snapshot and compare its revision. Saving future values
revalidates the mapping, company, employee, contract identity, record values,
and record-edit permission. Changed mappings, a newer contract, conflicting
record edits, duplicate destinations, incomplete computation, and changed
payslip inputs prevent a stale write. Pending, returned, rejected, applied, and
refused record proposals are reflected when the review is reopened. Rejected
payrolls expose their review for reference with decisions disabled.

Older Excel batches can be reviewed retrospectively from their stored payslip
inputs. These reviews explicitly label the comparison as **on record at first
review**; they do not claim to reconstruct an unavailable original before-value.

## Implementation commits

- `c4ab34194`: durable server snapshots, decisions, grid, export, batch doors, tests.
- `6fdd431c1`: declared Excel-binding resolution and context-field coverage.
- `4b60dacbb`: literal Excel text and Records Desk conflict-resolution link.
- `e3730f109`: open batch reviews through the shared dialog lifecycle.
- `2a6709dca`: compact desktop filters and clear hidden selection.
- `7568f1259`: explain unused workbook values without guessing which source won.

The deployment and final validation receipt is recorded in
`docs/deploy/2026-10-16-payroll-input-change-review.md`. Concurrent workbook-upload
changes are preserved separately from these feature commits and included in
the combined application deployment.
