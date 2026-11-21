# Repository operating instructions

For every code or configuration change:

1. Commit relevant changes, excluding unrelated or concurrent-session work.
2. Re-check the latest branch and deploy the latest combined repository state to every active environment and database in scope, preserving other sessions' changes.
3. Test the deployed version. Include an end-to-end Chrome check for changes to user-facing behavior.
4. Report the commit, deployment targets and test results.
5. Remove every PNG or screenshot created by the current test run. Preserve existing product assets, user images and unrelated files.

Ask for genuinely missing targets, credentials or required test paths.

## Active server scope and retention

- SSH target: `Payobook19v2`. The only deployment addons directory is `/odoo/odoo-server/addons`; preserve standard Odoo addons supplied by the server's own checkout.
- Active databases: `payobook`, `payobook_template`, `p0clone`, `rize`. Upgrade custom modules only where already installed, and verify combined custom-module content and installed versions across all four.
- **ABM is retired by owner instruction. Do not deploy to, recreate, upgrade or provision `abm` or `abm.payobook.com` unless the owner explicitly requests it.** Preserve its permanent database/filestore archive under `/odoo/archives/abm-20261020` and its retired hostname response.
- Rize is production. Exempt `rize` database backups from automatic deletion. Nonproduction database backups have seven-day retention, always preserving the latest usable backup. Permanent retirement archives and final backups never expire automatically.
- Temporary cleanup must preserve active processes, live addon targets, customer workbooks and unknown files. Never blanket-delete `/tmp`.
