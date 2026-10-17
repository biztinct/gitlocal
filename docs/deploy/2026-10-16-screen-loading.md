# Settings → Formula Engine loading — 16 October 2026

The submenu calculated the company's default payroll, fetched its workspace
data and then hid it behind the configuration picker. On Rize the default was
the 367-column Indonesia scheme. This shared entry path affected every database
with a default scheme; the cost depended on the size of that scheme.

Menu entry now reads the picker directly. A chosen configuration, explicit
configuration link or creation flow still loads its required workspace. Closing
the initial picker loads the default workspace; a failed first selection returns
to the picker so the user can retry.

The shared formula evaluator also repeatedly scanned the entire rule recordset
for every dependency. Indexed lookups and a FIFO queue replace those scans,
preserving column-letter precedence, first matching column, unknown-reference
handling and the existing cycle fallback. No calculation semantics changed.

Implementation: `3c204362f`. Test isolation and precedence regression:
`e6816bc29`. Versions: `pb_formula_studio` **19.0.1.201.14** and
`pb_hr_payroll_formula` **19.0.1.148.10**.

## Deployment and checks

Both modules were upgraded on **payobook, rize, payobook_template, abm and
p0clone**, using the shared `/odoo/odoo-server/addons` on **Payobook19v2**.
The latest combined runtime tree was rechecked before rollout and after the
concurrent documentation commit `2c45eb2da`: all **4,734 custom files across
146 modules** match. Standard addons were not overwritten. Other sessions'
documentation, client files and workbook deletions were excluded from these
commits. Assets were refreshed on each database; the service is active and
`tools/deploy_status.py` reports nothing pending.

- **48 database checks per target, 240 total**, all passing: typed inputs,
  formula evaluation, real-person previews and preview write isolation.
- **33 active configurations** across Rize, payobook and ABM have exactly the
  same calculation order and complete Studio payload before and after the
  evaluator change. The clone and golden template have no configurations.
- **7 standalone dependency regressions** pass, including forward references,
  letter/code collisions, cycles and a field-read budget for large schemes.
- **8 deployed Chrome HOOT loading regressions** pass at
  `/web/tests?filter=config_loading` on Rize.
- Chrome's live **Settings → Formula Engine** path shows all four Rize cards
  in **1.014 seconds**, with no visible centre logo and no hidden workspace
  calculation. The picker RPC takes **0.386 seconds**. Opening Indonesia shows
  its live preview and the same take-home value, with zero console errors.
- Indonesia's measured server payload time falls from **3.369 to 1.954 seconds**.
  Payobook's matching large configuration falls from **3.358 to 1.848 seconds**
  in the direct before/after comparison. These are measured server durations,
  not guarantees about every browser or network.

An existing no-scheme preview test initially picked up Rize's default scheme.
Its fixture now explicitly supplies the resolver's no-scheme result. The final
48-test run passes on all five databases. Upgrade tests run on an isolated
loopback port with a database filter.

Employee, contract, aggregate wage, configuration and payslip totals match the
pre-upgrade snapshots on every target. Original scheduled-job activation was
restored: payobook 37, Rize 69, clone 26; template and retired ABM remain at zero.

Database dumps, previous addon files, manifests, original cron flags, logs,
final receipt and browser/comparison evidence are retained with restricted
permissions at `/odoo/backups/screen-loading-20261016-3c204362f`.
Task staging and scratch files were removed. No test screenshot or PNG file
was written; pre-existing assets and screenshots were untouched.
