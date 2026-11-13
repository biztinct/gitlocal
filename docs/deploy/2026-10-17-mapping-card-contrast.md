# Selected mapping card detail contrast

Fixed the owner-reported unreadable expanded spreadsheet card in Rize Mapping.
The purple selected state already made its label white, but compact details,
the expand chevron and detail links/warning icon kept colours intended for a
light card. These elements now use white in the selected state, with a visible
divider. The chevron uses purple on its white hover/focus background.

Implementation commit: **5893e6687**. Five SCSS lines only, scoped to selected
compact mapping cards. No mapping, formula, payroll or record data was changed.
Normal-card and tooltip styles are preserved.

## Deployment

The latest committed `pb_formula_studio` tree was staged from branch 19.1 and
compared against the shared server path. Exactly `static/src/scss/mapping.scss`
differed. The complete combined module snapshot was synchronized under the
deployment lock to `/odoo/odoo-server/addons/pb_formula_studio` on Payobook19v2.
After deployment, its tree matches the staged snapshot with no differences.
Concurrent changes and unrelated local workbook deletions were preserved.

Backend asset caches were refreshed and asset signaling/version updated on all
six installed databases: **payobook, rize, payobook_template, abm, p0clone and
lrp4clone**. Asset version: `20261017-mapping-contrast-5893e6687`. This SCSS-only
deployment required no module/schema upgrade or service restart.

## Verification

- Staged SCSS compiles successfully with the server's Sass compiler.
- Chrome reproduced the exact Vietnam HC Employee ID card before deployment:
  foreground `rgb(100,116,139)` on `rgb(90,75,176)`, contrast **1.44:1**.
- After a fresh page load and reselecting the Vietnam HC spreadsheet mapping,
  its expanded selected card has white detail text and chevron on the same
  purple background, contrast **6.84:1**. Both detail lines were measured and
  visually inspected. The divider is white at 45% opacity.
- Collapse and reopen work. The hovered chevron is purple on white, also
  **6.84:1**. Deselecting restores the original light-card and muted-text styles.
  No wires were created, accepted or removed during testing.
- The served Rize backend CSS contains the deployed selected-detail rule.
  Service remains active; Rize and Payobook login endpoints return HTTP 200.
- Employee, contract, payslip, run and active-cron counts match before/after
  asset refresh on all six databases. Existing module versions were preserved.
- No test PNG/screenshot files were retained. Pre-existing images and user
  screenshots were untouched.

Protected source backup and per-database refresh receipts:
`Payobook19v2:/odoo/backups/mapping-contrast-20261017-5893e6687/`.
