# Indonesia payroll template and country statutory mapping — 14 October 2026

Implementation through commit `c4ddf82b2` on branch `19.1`. The client August
2026 snapshot is preserved. Detailed calculation and mapping contracts are in
`docs/design/COUNTRY_TAX_WORKBOOK_MAPPING.md`.

## Delivered workbook and review configuration

`outputs/id-payroll-20261014/Rize_Indonesia_Payroll_Formula_Template_Aug2026.xlsx`
contains the Payroll calculation sheet and Tax Map metadata. It declares the
employee header at row 29, 75 employee columns, 36 formulas per employee and
292 mapped statutory constants. Six fictional examples replace client data.
The 122 temporary numerical reconciliation rows were cleared before export.
Workbook SHA-256: `e5ada1dcb437a1f5ab1a3aea0a25799e95f500803a79c103f9bfd90c2cd979d9`.

Payobook demo review configuration: `602`, `RIZE_ID_202608_REVIEW`,
**Rize Indonesia · August 2026 (import review)**, Payobook Vietnam JSC,
country Indonesia, currency IDR, draft. Six source editions are drafts:
IDPARAMS, IDTERA, IDTERB, IDTERC, IDANNUAL and IDSEVERANCE, version 2026-08.
There are 134 bands and 24 statutory parameters. No real employees or pay runs
were created. Actual employee/source mappings and statutory publication belong
to the normal payroll setup and approval workflow.

Annual final-period full-net contract gross-up requires an agreed client
policy. That unobserved case explicitly returns a review message in this
August template. Qualifying severance uses official reference bands; the
source workbook has no nonzero severance control.

## Deployment

Current environment: SSH `Payobook19v2`, Odoo 19, shared addons at
`/odoo/odoo-server/addons`. Upgraded **payobook, rize, payobook_template, abm
and p0clone**. Versions:

- pb_hr_payroll_formula: 19.0.1.148.9
- pb_statutory: 19.0.1.4.1
- pb_formula_studio: 19.0.1.201.11

Backups of all five databases were created at `/odoo/backups/idtax-20261014`.
The stored operand-usage migration refreshes derived formula metadata without
changing employee inputs or formula values. Existing scheduled-job states
were restored; retired ABM retains zero active jobs. The service was restarted.
Server module directories were updated individually. Standard Odoo addons were
not replaced. Concurrent biz_mail_debrand work was preserved and excluded from
this session's commits. Installed custom code was compared against the combined
working tree, including that concurrent work.

## Verification

- All 122 source take-home-pay values agree exactly. One copied tax allowance,
  and consequently gross, tax and deductions for the same source row, differ
  by Rp1 with no take-home-pay difference.
- 366 TER boundary cases and four changed-input recalculation checks passed
  during artifact creation. No formula errors remain in the delivered examples.
- All 216 formula outputs (six examples × 36) match cached Excel results when
  evaluated by the deployed application. All 292 bindings align with database
  source values.
- 16 deployed Odoo regression tests passed: country isolation, import identity
  and idempotence, precision, published immutability, date/version selection,
  reviewed refresh/history, activation guards, structure/method changes,
  nested text comparisons, typed preview and genuine text-arithmetic linting.
- 23 existing plain-Python operand/type-classifier tests passed.
- Chrome completed Upload → worksheet/column selection → order → component
  review → Execute Import → category review. It excluded Tax Map and detected
  Payroll header row 29. All six visible sample tests passed. The schema's
  health panel reports **0 errors, 0 warnings, 15 hints**; hints cover unused or
  unmapped profile fields and repeated formula patterns.
- Chrome verified Indonesia's six source editions, country isolation from
  Vietnam slabs, cell mappings, percentage displays and literal PTKP preview.
  Example 2 shows M/2 and Rp90,000,000 take-home pay.

The handover audit passed module-version and country/schema RPC checks on all
five databases. All 4,279 tracked/custom working-tree files across 134 installed
custom modules match the shared server code, including concurrent work.
`tools/deploy_status.py` reports nothing pending. The service is active and ABM
has zero active jobs. All eight testing PNGs, temporary decrypted workbook and
numerical source controls were removed. The original encrypted workbook remains
unchanged.
