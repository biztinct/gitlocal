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
| 2026-10-14 | pb_me_portal → 19.0.2.1.0, pb_import_kit → 19.0.1.22.0 | MEHOME: the employee home (/my) redesign — greeting + sentence, Pay / Leave / This week cards, Needs you, grouped tiles with icons, Inter on the portal, VI (`docs/handovers/mehome/`). Normal tier: upgraded on payobook, asset purge + version bump done. No new stored field. | Owner's walk on payobook.com; then the batch (rize, payobook_template, abm — abm jobs off after) |
