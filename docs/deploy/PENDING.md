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
| 2026-10-12 | biz_theme → 2.0.3, biz_debrand → 2.8.2, pb_theme → 2.1.2, pb_sidebar → 3.2.3, pb_tenants → 2.3.2 | The loading language (docs/LOADING_LANGUAGE.md): accent top line + sidebar mark beat on every load, "Rise" mark in the centre only after 2.5 s, first-open splash, `.biz-skel` blocks; per-database logo (Branding › "Loading screen logo", brand-name text on white-label, Payobook seeded only where the brand is Payobook); sidebar badge = brand initial. Already on **rize** (all but pb_tenants) | payobook_template, abm |
| 2026-10-11 | pb_formula_studio → 1.201.9 | Spotlight on the Cards view: unrelated rows fade, All / Related toggle, teal/pink/indigo lines, type dots, icon actions, Feeds from / Goes into (+ VI translations); 1.201.9 = skeleton instead of the spinner while loading (already on rize) | payobook_template, abm |
| 2026-10-11 | pb_learn → 20.3.0 | Practice Formula Studio follows Spotlight (row colours, toggle, Feeds from / Goes into); lesson wording updated | rize, payobook_template, abm |
| 2026-10-12 | pb_hub → 1.11.0, pb_audit → 1.4.0 | PAYAI P1: palette service exposes `entries()`/`run(id)` + "Ask PayAI to…" row; Audit console gains the PayAI source. JS/Python only — no stored field, can wait. `pb_payai_actions` (new) is installed on payobook ONLY by owner decision (tenants' switches stay off until asked). `pb_payroll_ai_insights` 3.12.0 adds a stored field → upgraded on every DB in the same deploy (wave 2). | rize, payobook_template, abm |
| 2026-10-12 | pb_payai_actions → 2.0.0 | PAYAI P2 (Amber): PayAI prepares run payroll / send for approval / change pay data / send payslips / prepare a filing; plan card → Do it → progress → result → 10-min undo. New stored field `hr.payslip.run.pb_prepared_via` + `payai.task` state `cancelled`. Deploy (Fable; builders do not deploy): payobook only, `-u pb_payai_actions,pb_payrun_wizard,pb_settings,pb_learn` in one upgrade, then `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` + restart. Installed on payobook ONLY (owner decision), so PA23 does not bite — nothing to upgrade elsewhere. | — (payobook only by design) |
| 2026-10-12 | pb_payrun_wizard → 1.32.0, pb_settings → 1.9.1, pb_learn → 20.4.1 (was 20.3.1; 20.4.0 went live first, see next row) | PAYAI P2: read-only `plan_preview` + shared run driver JS + prefill (wizard); Settings hub names its breadcrumb "Settings" (JS); helper drawer banner now says PayAI shows a plan first (JSON content, EN + VI). Upgraded on payobook together with pb_payai_actions (row above). No stored field — tenants can wait. JS changed → `DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%'` + restart after the upgrade. | rize, payobook_template, abm |
| 2026-10-12 | pb_learn → 20.4.0, pb_demo_portal → 1.6.0 | Demo users land on Home (opens on Pulse), not Learn: the sign-in jump to the Learning journey is removed (JS); sign-up start page = Home hub; migration moved all 357 demo-group users from Dashboard/none to Home (rollback list `/odoo/backups/2026-10-12-home-landing/`). Shipped from HEAD + this change only — the uncommitted 20.3.1 content edit was NOT deployed. pb_demo_portal is payobook-only. | pb_learn: rize, payobook_template, abm |
| 2026-10-12 | pb_dashboard → 2.2.3, pb_learn → 20.5.1 | New Home (HOME P1–P3, + Vietnamese-style money, dates and chart labels): one data call, hero + needs-you + 12-month chart that picks the month + steps + coming up + People / pay runs / Hiring cards + Keep learning + Pay schemes, VI words; Home lesson rewritten for the new screen. The other DBs already run the shared code (2.0.0 reached them mid-build) — only the version, views, translations and Learn content wait | rize, payobook_template, abm |
