# Role editing and automatic access updates

The Access board now edits an existing role through the same builder used for new
roles. The native read-only role form has an **Edit role on Access** entry point
using the Access management policy, including application managers without native
role-write ACLs.

An administrator selects screen capabilities, reviews every assigned user's
permission additions, removals and retained access, gives a reason, and saves a
new revision. The save updates the role, assignment projection and immutable
history in one transaction. Concurrent drafts cannot overwrite a newer revision.
Original configuration and published versions can be restored into a draft for
the same review. Existing menu customizations survive upgrades.

## Permission sources

`pb.role.assignment` records permanent role assignments and individual hand-over
sources. The projection retains direct permissions and overlapping roles. Ending
one source cannot remove another source's access. Temporary hand-overs retain an
approved snapshot: role reductions apply, expansions need a new hand-over.
Membership markers carry no ACLs and keep role-gated navigation available to a
pinned borrower. Backend permissions and record rules remain the enforcement
layer. Unresolved optional UI gates fail closed.

Migration adopts documented Access grants and the explicit Demo group membership,
not every user with matching permissions. The owner approved adopting Demo group
members while preserving their other access. Matching permissions are displayed
separately from assignments; holders and "You hold this" reflect assignments.
Subsequent migrations do not consume direct grants added after the initial move.
New tenant-administrator provisioning records its canonical role assignment.

Records capabilities separate read, mapped editing and export. A viewer gets no
native write ACL or export access. An editor may update only the existing mapped
field plan after company, record-rule and approval checks; arbitrary model writes
remain unavailable.

Open sessions receive an access revision event. Idle screens refresh; screens
with input show a persistent refresh action, preserving work in progress.

## Validation

- Isolated clone of `payobook_template`: 334 relevant regression tests passed.
- Final `role_assignment` suite: 20 tests passed after the final corrections.
- Chrome clone checks: native edit entry without native write ACL; search and
  selection; two-user impact review; required reason; additions and reductions
  propagated to both logins; idle observer refreshed; observer input preserved
  with a refresh notice; history, restore into draft and cancel.
- Python compilation, XML parsing, JavaScript syntax and diff whitespace checks.

Deployment scope is `payobook`, `rize`, `payobook_template`, `abm`. The owner
explicitly excluded `p0clone`, which belongs to another active session. Deploy the
latest combined custom runtime trees, while committing only this implementation.
The server's standard Odoo addons must remain untouched. Preserve retired `abm`
cron settings. Backups and before/after migration evidence live in
`/odoo/backups/2026-10-12-access-role-edit-codex`.
