# Release status — 24 November 2026

Implementation commit: `73726dec8` (on `19.1`, includes the latest DOCSTUDIO W2 repository changes through `705cd8046`).

**Not deployed yet.** The user confirmed that another session is deploying and will tell us when it has finished. Do not take over or interrupt that reservation. The live database, company preferences and installed modules have not been changed by this session.

## Completed checks

- Nine server tests pass (0 failed, 0 errors) on an isolated Sudima copy, `pbqa_workforce_20261124`.
- Backend catalog reads succeeded for all eight libraries using the existing company data.
- Chrome checked all nine navigation routes in the rehearsal checklist without console errors: roster board, roster review, people, overtime definitions, calendars, connectors, attendance/hours, overtime approvals and guided setup.
- Created a test shift through the real form: 07:30–16:30, one-hour break, computed eight hours. This exists only in the QA copy.
- Unsaved edits prompt before switching sections; cancel keeps the original value.
- Pattern cards show weekdays/times/rest; filters start collapsed. Draft creation is disabled until a preview is obtained. The preview retains existing drafts and reports its impact without publishing anything.
- Company navigation was disabled and re-enabled through the setup UI. The previous rail returned when disabled.
- At 390px, page width stayed 390px and the approvals dock collapsed automatically, leaving 647px of canvas height.
- No screenshot files were generated: visual inspection used inline JPEGs only. Pre-existing and concurrent-session images were preserved.

## Resume after user confirms the other deployment is complete

1. Fetch and merge the latest `origin/19.1` into the isolated worktree; preserve concurrent work. Recheck `/opt/deploy-notes.md` and the deployment lock.
2. Refresh the server inventory (`tools/workforce_workspace/inventory.py`) into `/private/tmp/workforce-workspace-ops-20261124/before.json`. Current inventory is **pre-DOCSTUDIO**, so do not deploy from it.
3. Run `prepare_release.py` from the isolated worktree. It refuses unexplained code differences. The existing generated Windows connector ZIP is deliberately retained, not downgraded to the tracked historical archive.
4. Upload the new package, release JSON and deployment script to `/tmp/workforce-workspace-20261124`. Run the guarded deployment only after the reservation closes. It backs up all five databases, preserves Rize permanently, deploys only to `/odoo/odoo-server/addons`, installs the new module in all five (all dependencies already installed), and preserves exact cron states. ABM is excluded.
5. Run `verify_live.py` against all five databases, verify combined module hashes/installed versions again. Enable the workspace in Sudima through its guided setup UI; leave every other company disabled.
6. Complete authenticated Chrome checks of the deployed Sudima workspace, including Settings entry, navigation, policy editor, existing roster/pattern/time screens and connector details. Do not activate the policy or publish inferred rosters.
7. Disable any temporary live QA user. Stop the isolated QA server using its validated PID, remove the QA database/filestore and QA credentials created by this session, and stop the local SSH tunnel. Preserve release evidence and unrelated temporary files.
8. Record final commit, targets and live test results, then report completion.

## Rehearsal resources

- Worktree: `/private/tmp/payobook-workforce-workspace-20261124`
- Server stage: `/tmp/workforce-workspace-20261124`
- Rehearsal logs: `rehearsal2.log`, `browser.log`
- Private temporary QA credential: `qa-login.json` in the server stage; do not print or commit it.
- Rehearsal server binds **127.0.0.1:8876**. Local SSH tunnel is **127.0.0.1:18776**. It serves only the QA database; no public hostname was added.
- Sudima's policy is still draft; all 12,384 roster rows are still draft. Its 651 employee records have no workplace assigned, so the factory overview uses an explicit unassigned card.
