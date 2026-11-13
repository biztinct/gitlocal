# Payroll configuration switching

Implementation: `6b7121c42`, pb_formula_studio **19.0.1.201.13**.

The configuration gallery dismissed itself before the requested payroll's RPCs
completed. Opening Indonesia therefore exposed the previously loaded Vietnam
configuration. Chrome reproduced this with the Vietnam header visible and no
loading view immediately after selecting Indonesia.

The existing loading view now covers a switch until the new configuration,
dependency graph and problem data are ready. Refreshing the same configuration
after a save keeps the workspace visible. A failed initial data request restores
the previous view. Explicit configuration links load their target first rather
than loading the company default first. Read-only arrival flags are applied
before that initial load. Scroll listeners rebind when the loading view replaces
the panel elements, preserving dependency-arrow updates.

## Verification and deployment

- Three loading regression tests pass locally and in the deployed Chrome HOOT
  runner at `/web/tests?filter=config_loading`: pending cross-country switch,
  failed connection recovery and same-configuration refresh.
- Chrome verified Vietnam to Indonesia, Indonesia to India and India to
  Indonesia (using the card and Open button). During Indonesia loading, eight
  consecutive DOM observations showed the loading view with no previous header.
  The completed view shows Rize Indonesia Payroll, ID, Currency Rp and Draft.
- After switching, both side panels scrolled 934 px; their control headers stayed
  at 160.5 px and dependency arrows remained visible.
- Upgraded **payobook, rize, payobook_template, abm and p0clone** on
  `Payobook19v2`, shared `/odoo/odoo-server/addons`. The latest combined code
  includes the preceding pb_payai_actions 19.0.4.2.0 commit; its remaining
  p0clone upgrade was included. Concurrent biz_mail_debrand work was preserved
  and excluded from this change's commits.
- All 4,656 deployed custom files match the combined local working tree.
  `tools/deploy_status.py` reports nothing pending across all five databases.
  The service is active. Existing cron states were restored; ABM has zero
  active scheduled jobs.
- Database dumps, prior studio files and cron states are retained under
  `/odoo/backups/payroll-opening-20261014`.
- No test PNG or screenshot files were written. Temporary deployment files were
  removed after verification.

## Changing Indonesia's Draft status

The Draft badge in the guided setup is a label. Click the top-left
**Rize Indonesia Payroll** return button to reach the component studio. The
top-right primary button advances **Start testing → Validate → Activate**.
Review the sample checks in Test before activation. Formula errors or circular
references prevent activation. Configuration 3943 has neither and remains
Draft; this fix does not change its payroll lifecycle state or statutory editions.
