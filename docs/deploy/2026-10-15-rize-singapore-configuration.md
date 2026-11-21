# Singapore payroll configuration installed in Rize

Installed the previously tested payobook configuration 613 into **rize** on
15 October 2026, as requested by the owner. Target company: **Rize Farms**.

- Configuration **3948**, **Rize Singapore Payroll**, code
  `RIZE_SINGAPORE_PAYROLL`, country SG, currency SGD, regular cycle.
- Remains **draft**, matching the reviewed source. No employees are assigned;
  October 2026 template workspace resolves to zero eligible employees. Activation
  and population assignment are still required before a live payroll run.
- 41 components: 25 inputs, 13 formulas and three SDL parameters. Reviewed
  pay roles, subtotal flags, value kinds, source bindings and nine employee/bank
  mappings were preserved. CPF and self-help remain reviewed monthly inputs;
  salary retains the client's net-before-proration calculation.
- SDL edition `RIZESGSDL`, version 2026-08, remains draft. All three statutory
  links align. No statutory approval or client approval matrix was copied.
- Both original reviewed workbooks are attached to the destination configuration.
  Their SHA-256 hashes match the 14 October demo report exactly.

## Installation and validation

Committed installer: `tools/install_rize_singapore_config.py`, final functional
commit **ae63b7a7d** (preceding scope/mapping fixes included). The installer uses
the current deployed ORM and Studio APIs, remaps categories by code/name/company,
and copies no source database foreign keys into the tenant. It defaults to a
read-only plan and commits only after destination validation passes. Aborted
pre-commit attempts were rolled back; only configuration 3948 was installed.

The latest branch state was rechecked before the installation and at closeout.
Concurrent PayAI, portal, mail and other session changes were preserved. This is
a Rize-only configuration deployment: no application modules or shared addon
files were changed, downgraded or reinstalled, and no other database received
the Singapore configuration.

Destination validation:

- Eight stored scenarios passed; zero failed or pending.
- 104 formula output comparisons match within 0.0000001 SGD. Every scenario
  reconciles cash earnings less applied deductions to net pay.
- All reviewed treatment/type fields match the demo source. Zero unresolved
  treatment decisions or type conflicts; all statutory bindings align.
- Formula health: zero errors, six existing warnings and 17 hints, matching
  the source. Warnings concern hidden/full-month and unused reporting references,
  including the explicitly zero ordinary-month income tax line.
- Chrome, signed in as the Rize administrator: selected Singapore in Templates,
  verified SGD, download controls and the draft/population guard; opened the
  Singapore card and reran **Run all tests**. All eight scenarios showed passed,
  with all 13 formulas asserted. Browser error log was empty.
- Business record counts were unchanged: 107 employees, 102 contracts,
  97 payslips and two payslip runs. No salary or payroll payment was changed.
- No test screenshots/PNGs or temporary workbook downloads were generated.

Backup and receipt on SSH `Payobook19v2`:
`/odoo/backups/rize-singapore-config-20261015/` contains a pre-install custom-format
Rize dump, the exact installer and installation log. The service stayed active;
no restart or outage was necessary.

Open Payroll configurations in Rize and select **Rize Singapore Payroll**.
The tested live Studio URL is
`https://rize.payobook.com/bizapp/pb_formula_studio/action-1103/action-742`;
the configuration selector identifies the current scheme.
