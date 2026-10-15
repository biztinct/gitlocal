# Pending deploys

Owner ruling 2026-10-11: ship every change to **payobook** (payobook.com, the
demo database) first and check it there. The other databases (`rize`,
`payobook_template`, `abm`) are upgraded in ONE batch when the owner says so.

- Add a row here when a change goes to payobook only. Remove it after the batch.
- `python3 tools/deploy_status.py` is the check that this list is complete — it
  compares the repo's version with each database's installed version, so a row
  forgotten here still shows up there.
- One addons directory serves every database: new Python/JS already reaches the
  other databases at the next restart. What waits is the per-database upgrade
  (views, data, translations, new fields). **A change that adds a new stored
  field cannot wait** — the other databases would error until upgraded; upgrade
  them in the same deploy.
- Batch recipe: the "normal" tier in the repo CLAUDE.md deploy contract,
  `-u <modules>` on each remaining database one at a time, asset purge +
  `web.assets.version` bump on each, then `deploy_status.py` must say nothing
  is pending. abm is retired: its upgrade turns its scheduled jobs back on —
  switch them off again after (see memory `abm-tenant-retired`).

| Date | Module → version | What changed | Waiting on |
|---|---|---|---|
| 2026-10-15 | pb_payroll_templates → 19.0.1.0.0 (new) | Approved template workspace: current employee records, two-tab monthly workbook, layout configurator, reviewed patch imports and Pay Run integration. Installed/tested on payobook; 18 server checks and Chrome draft payroll round trip pass. New tables belong to this module only; no new fields on existing models. Install with `-i pb_payroll_templates` on each rollout DB, then purge assets and bump `web.assets.version`. See `2026-10-15-payroll-template-workspace.md`. | Owner review on payobook.com; then install on rize, payobook_template, abm and p0clone |
| 2026-10-15 | pb_me_portal → 19.0.3.1.0, biz_access → 19.0.1.6.0, pb_zoho_bridge → 19.0.1.2.0, pb_demo → (bumped), pb_ess_workforce → 19.0.1.1.0 | TIERS T2 + T2b, portal accounts: every My Payobook page works for an employee login (share user) — sudo after an ownership guard, tokened downloads, own-photo route; Access screen Employee/Staff switch (`pb.access.set_account_type`); joiners' automatic accounts also become `hr.employee.user_id`; demo generator makes employee logins; leave apply + timesheet fix under sudo; fence now also keeps the backend for a hand-given permission (ledger T22). Normal tier: `-u pb_me_portal,biz_access,pb_zoho_bridge,pb_demo,pb_ess_workforce` on payobook, asset purge + version bump. No new stored field. pb_demo is payobook-only (not on tenants). | The batch |
| 2026-10-15 | pb_me_portal → 19.0.2.2.0, pb_me_portal_website → 19.0.1.0.0 (new, auto-install) | TIERS T1, the fence: a plain employee (no role, no reports, no open approval seat) is bounced from `/bizapp`, `/web` and `/` to `/my`; the nine-dots corner shortcut and the "Apps" menu entry are not drawn for them (`docs/handovers/tiers/`). Normal tier: `-u pb_me_portal -i pb_me_portal_website` on payobook, asset purge + version bump. No new stored field. Batch needs the same `-i` on each DB. Live walk done 2026-10-15 (ess2.demo bounced, links gone; admin and ess1 — who has a direct report — keep the backend). | The batch |
| 2026-10-14/15 | pb_me_portal → 19.0.2.1.1, pb_import_kit → 19.0.1.22.0 | MEHOME: the employee home (/my) redesign — greeting + sentence, Pay / Leave / This week cards, Needs you, grouped tiles with icons, Inter on the portal, VI (`docs/handovers/mehome/`). Normal tier: upgraded on payobook, asset purge + version bump done. No new stored field. | Owner's walk on payobook.com; then the batch (rize, payobook_template, abm — abm jobs off after) |
