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
| 2026-10-04 | pb_dashboard → 1.6.1 | Home no longer fails for people who cannot read formula test results | abm |
| 2026-10-11 | pb_learn → 20.2.0 | Lesson card's Next works with a real mouse (20.1.2) + Runs lesson, scenarios and practice replica follow the redesigned Pay Run board (20.2.0) | rize, payobook_template, abm |
| 2026-10-11 | pb_formula_studio → 1.201.7 | Offer calculator: values shown by their value type (multipliers, days, rates no longer as ₫); Earnings/Deductions boxes use the payslip's totals rule | rize, payobook_template, abm |
| 2026-10-11 | pb_payruns → 3.0.0 | Pay Run board redesign: This-month hero, lane headers = steps, quick look, bulk submit, delivery rail, list view (+ translations) | rize, payobook_template, abm |
| 2026-10-11 | biz_theme → 2.0.2, pb_theme → 2.1.1, biz_debrand → 2.8.1 | Centre-screen logo loader ("Rise") replaces the bottom-right Loading pill. Per-database logo: Branding › "Loading screen logo" (upload or address); white-labelled databases without one animate the Brand Name as text. biz_theme + biz_debrand already on **rize** too (white-label fix; rize points at its own logo file) | payobook_template, abm (all three); rize (pb_theme only) |
| 2026-10-11 | pb_formula_studio → 1.201.8 | Spotlight on the Cards view: unrelated rows fade, All / Related toggle, teal/pink/indigo lines, type dots, icon actions, Feeds from / Goes into (+ VI translations) | rize, payobook_template, abm |
| 2026-10-11 | pb_learn → 20.3.0 | Practice Formula Studio follows Spotlight (row colours, toggle, Feeds from / Goes into); lesson wording updated | rize, payobook_template, abm |
