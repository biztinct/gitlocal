# IA Redesign — Cycle 4: Insights hub + Compliance hub + the filing flow

Program: Option A "Six Missions" (mockup `docs/PAYOBOOK_IA_REDESIGN_OPTIONS.html` — Option A demo, Insights + Compliance hubs; flow-doctrine card 1 is the filing flow spec).
Prior: C1 `pb_hub` kit, C2 `pb_payhub` (embedded-mode pattern), C3 `pb_settings` + one-door (facade-flow pattern `pb.integration.onboarding`, ledger clone `.itg-*`). Read all three handovers in `docs/handovers/ia/` + their W entries. Conventions binding through **W100**.

## ⚠ Production discipline (unchanged, non-negotiable)
The box serves payobook.com in production. W93/W94 (no `--delete` into shared addons; count files, checksum-diff before restart), W68 (never touch a server you didn't start), W75 (headless CDP from per-session profile). Prefer UNVERIFIED over improvisation.

## Scope
1. **Insights hub** — module `pb_insights_hub`, client action tag `pb_insights_hub`: lenses `pulse(activity) · explorer(compass) · workforce(users) · payroll(file-text)` mounting `pb_insights`, `pb_explorer`, `pb_workforce_insights`, and the re-skinned Payroll Report.
2. **Payroll Report re-skin** (`pb_hr_workforce/static/src/js/payroll_report.js` + its CSS): off-system today — FontAwesome, its own `wf-breadcrumb` chrome duplicating the shell breadcrumb (`payroll_report.js:20–32`), own `payroll_report.css`. Re-skin onto the kit: `ic()` icons, pbim tokens, kill the internal breadcrumb, add `embedded` mode. Re-skin ≠ rebuild: keep its data flow and features intact.
3. **Compliance hub** — module `pb_compliance_hub`, tag `pb_compliance_hub`: lenses `filings(file-text) · bank(scan) · young(shield) · audit(scroll-text)` mounting `pb_govt_reports`, `pb_bank_ocr`, `pb_young_worker`, `pb_audit`. Lens gates derived from target ACLs (W95), not copied from rail items.
4. **The filing flow** (flow-doctrine card 1 — the product's worst screen dies): full-screen stepped flow replacing the stock `target:"new"` wizard modal for Government Reports.
5. **C3 hand-backs**: (a) `pb_statutory`'s five legacy VN launch tiles → in-cockpit ledgers with drawers; (b) Formula Studio back chip.
6. **Drive-by bug fix**: `pb_hr_payroll_formula/models/integration_mapping_template.py:114` raises `models.ValidationError`, which does not exist in Odoo 19 → import and raise `odoo.exceptions.ValidationError`. One-line fix + a regression test if a cheap seam exists.

### Binding non-goals
NO rail/sidebar data changes (C5). NO Home hub, NO Dashboard changes (C5). NO Planning changes. Insights' Pulse drill-downs into native employee/leave/OT lists (`pb_insights/static/src/js/insights.js:466–527`) stay as-is this cycle — enumerate them in the report as a polish hand-back, don't fix. Explorer's `openClassic()` legacy legs stay. No rebuild of any analytics cockpit.

## Verified plumbing facts (audit + prior cycles; re-verify lines you edit)
- **Insights cockpits**: `pb_insights` tag `pb_insights` (`insights.js:546`, ~500-line SCSS, pbim); `pb_explorer` tag `pb_explorer_cockpit` (`explorer.js:499`, pbim, self-contained); `pb_workforce_insights` tag `pb_workforce_insights` (`workforce_insights.js:258`, Chart.js board; drills `:218–243` stay).
- **Payroll Report**: client action tag `payroll_report_dashboard` (`pb_hr_workforce/views/shift_planning_grid_views.xml:17–20`), component `payroll_report.js:435`, inline `xml\`\`` templates, FontAwesome classes, own CSS file, `wf-breadcrumb` chrome at `:20–32`.
- **Compliance cockpits**: `pb_govt_reports` tag `pb_govt_reports` (`govt_reports.js:56`, 56-line glue board; every "Generate" opens `target:"new"` on a country wizard `:41–54`; country registry `pb_govt_reports/models/pb_govt_reports.py:37–47` → VN `pb.govt.report.wizard`, SG `cpf.submission.wizard`, TH `social.security.wizard`, KH `nssf.wizard`, MY `epf.wizard`); VN wizard form = ~30 fields, 5 conditional groups (`pb_hr_govt/views/govt_report_wizard_views.xml:6–58`). `pb_bank_ocr` tag `pb_bank_ocr` (`pb_bank_ocr.js:217`, WOW self-contained). `pb_young_worker` tag `pb_young_worker` (`pb_young_worker.js:103`). `pb_audit` tag `pb_audit` (`pb_audit.js:306`; reference drills to native forms stay).
- **Statutory tiles**: `pb_statutory/models/pb_statutory.py:20–31` — 5 legacy `pb_hr_payroll_vietnam` act_windows (`action_vietnam_insurance_policy`, `action_vietnam_tax_table`, `action_vietnam_insurance_analytics`, `action_vietnam_insurance_adjustment`, `action_vietnam_employee_dependent`). C3's `.itg-*` ledger clone in `pb_integrations` is the pattern precedent (payload `columns`/`rows`/`_f`/`_s`/facets; drawer from `pb_wf_kit`, imported not forked; `_section` zero-vs-False fix included).
- **Facade-flow precedent**: C3's `pb.integration.onboarding` — facade writes allow-listed fields, presses the wizard's real buttons, discards returned act_windows, re-reads state; secrets reported as booleans. Clone this shape for the filing flow.
- **Formula Studio**: toolbar/commandLanes pattern; C3 deliberately left it chip-less. Minimal seam now: mount `HubBackChip` (from `@pb_hub/js/hub_nav`) in the Studio toolbar region ONLY when `pb_back` is present in the action context — no other Studio changes.
- **Embedded-mode pattern (C2)**: one suppressed element per template via `t-if="!props.embedded"`, standalone byte-identical, gate-test that counts guards (`pb_payhub/tests` precedent).

## The filing flow (workstream 4, design)
New module or inside `pb_govt_reports` (your call, report it): client action `pb_filing_flow` cloning the pb_import_wizard / C3-onboarding full-page stepped pattern:
- **Step 1 — Choose filing**: cards from the existing country registry (country-aware, like the board today): filing name, country, statutory logo-free icon, description. VN first-class.
- **Step 2 — Scope**: the wizard's real parameters — period/month, company/division, the VN wizard's conditional groups become progressive disclosure (only show what the chosen filing needs). Facade model `pb.filing.flow` drives the REAL wizard model via allow-listed writes + its real buttons (no logic reimplementation, C3 pattern).
- **Step 3 — Generate & deliver**: run the wizard's generate action, surface the produced artifact(s) (file download links / attachment ids), state summary, and a "Generate another" reset.
- **Adapter coverage**: VN (`pb.govt.report.wizard`) MUST be fully adapted. The other four countries: adapt them through the same facade if their wizards follow the same write-fields-press-button shape cheaply; any country you don't adapt keeps its old modal path from the board — enumerate covered/uncovered in the report (partial coverage is acceptable, silent coverage claims are not).
- The `pb_govt_reports` board's "Generate" buttons route to the flow (with the filing preselected) for covered countries; uncovered countries keep the modal. Old wizard actions stay registered.

## Safety rails
- Filing generation on the demo DB: use existing demo fixtures/periods; artifacts are files — verify by download/attachment existence, don't email/submit anything anywhere. If any wizard has a "send/submit to authority" side effect, DO NOT trigger it — generate-only paths; report if you had to stop short.
- Statutory ledgers: read-path only this cycle (grid + drawer); records stay editable via their existing (hidden) native forms — do not build edit UIs.
- Payroll Report re-skin: screenshot before/after; feature parity checklist (filters, totals, export if present) in the report.
- Icons `ic()` only; one accent; no gradients; tabular-nums; whole-sentence toasts (W80); no `window.confirm`; W95 ACL-derived gates for every lens/card you add.
- Demo fixtures reuse; anything you must create → clearly named, archived after evidence, ids reported (C3 precedent).

## Tests (evidence for each)
1. Insights hub via ⌘K preview entry: 4 lenses in order, each mounts, `titleRow:0` embedded, 0 console errors per lens; lens persistence key `pbhub.insights.lens.v1`.
2. Payroll Report: zero `fa fa-` classes in served DOM, internal breadcrumb gone standalone AND embedded, pbim tokens applied (spot-check computed styles), feature parity checklist passes, standalone route unchanged in behavior.
3. Compliance hub via ⌘K: 4 lenses, ACL-derived gating proven with a probe persona lacking audit access (audit lens absent), embedded mounts clean.
4. Filing flow VN end-to-end on demo data: choose a VN filing → scope (progressive disclosure shows only relevant fields) → generate → artifact produced (attachment/download evidenced) → "Generate another" resets. Double-click on Generate → exactly one artifact set.
5. Covered-country enumeration test (like C3's door test): board buttons for covered countries open the flow preselected; uncovered countries still open their old modal; the VN modal is opened by nothing in Payobook (grep gate).
6. Statutory: 5 tiles replaced by in-cockpit ledgers (or a Data section) — rows render from live VN tables, row click = drawer (URL unchanged), ESC/X close, no native `list,form` reachable from the Statutory board (click-test + grep); legacy actions still registered.
7. Formula Studio: arriving from Settings (cog path) shows the back chip which returns to Settings; arriving any other way shows NO chip; Studio's own palette/toolbar unaffected (smoke ⌘K inside Studio).
8. `models.ValidationError` fix: the empty-vendor guard now raises a proper ValidationError (unit or shell-level evidence).
9. Standalone regression: pb_insights, pb_explorer, pb_workforce_insights, pb_govt_reports, pb_bank_ocr, pb_young_worker, pb_audit, pb_statutory all open standalone with their own chrome, behavior unchanged (smoke each).
10. ⌘K matrix re-run (ordinary / Mission Control / Formula Studio / pay hub / settings hub / insights hub / compliance hub) — global yields exactly where it must.
11. Unit tests: prior 94 green + new modules' tests (lens gating from ACLs, filing-flow allow-list, coverage enumeration, statutory descriptors, embedded guard counts) — one combined run, exit 0.
12. Server log clean; zero non-warmup ≥400s across both hubs + filing flow + statutory.

## Self-review (mandatory)
Diff-read everything; verify Payroll Report re-skin didn't drop a feature (walk its handlers); verify the filing facade cannot write outside its allow-list nor trigger submit-like actions; verify statutory drawers respect record rules (C3's W97 scope lesson); verify Studio chip renders nowhere without `pb_back`; re-run affected tests after fixes.

## Commits (per feature, explicit staging, do NOT push; never stage `.claude/settings.json`, `thaco/`, `ABM/`)
Suggested: (1) feat(pb_insights_hub) + embedded modes; (2) refactor(pb_hr_workforce): payroll report on the kit; (3) feat(pb_compliance_hub) + embedded modes; (4) feat(filing flow) + board rewiring; (5) feat(pb_statutory): ledger tiles; (6) fix(pb_hr_payroll_formula): ValidationError import; (7) docs/ledger.

## Report back
- Both hubs' lens/gate tables (ACL-derived, verified).
- Payroll Report parity checklist + before/after screenshots.
- Filing-flow adapter coverage (country → covered/modal-fallback) + step→wizard mapping table.
- Statutory descriptor/field sets.
- Insights Pulse drill enumeration (the polish hand-back list).
- Per-test evidence, commit hashes, deviations, new W entries.
