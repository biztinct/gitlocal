# -*- coding: utf-8 -*-
"""UPDATES P3a — the old employee import is retired.

`employee.import.wizard` (`pb_hr_payroll_base`) created employees,
departments, jobs and a contract each from a file, a Zoho pull or an API
call, and ran a typed "custom validation code" with `exec()`. People ›
Updates replaces it (and P3b adds new joiners from a sheet). Retiring is not
deleting:

  * every door now leads to Updates: the country payroll dashboards' "Get
    Employee Data" / "Import employee data" buttons (`payroll.dashboard`
    methods below) and the Import screen's tile (`pb_import`);
  * the guided wrapper's client action and screen are removed
    (`pb_import_advanced`);
  * the `exec()` is deleted from the wizard itself;
  * the wizard model stays loadable (it is a TransientModel whose views live
    in a base module that is not upgraded for this), but it can no longer be
    started: creating one, or pressing its Import, is refused with a sentence
    pointing to Updates — from a stale bookmark, a form or an RPC call alike.
"""
from odoo import _, api, models
from odoo.exceptions import UserError


def _retired_sentence():
    return _("This employee import has been retired. Use People › Updates to "
             "change many people from one spreadsheet.")


class PayrollDashboardUpdatesDoor(models.Model):
    _inherit = 'payroll.dashboard'

    def _pb_open_updates(self):
        action = self.env.ref('pb_updates.action_pb_updates_desk',
                              raise_if_not_found=False)
        if not action:
            raise UserError(_retired_sentence())
        return action.sudo().read()[0]

    def action_get_employee_data(self):
        return self._pb_open_updates()

    def action_import_employee_data(self):
        return self._pb_open_updates()


class EmployeeImportWizardRetired(models.TransientModel):
    _inherit = 'employee.import.wizard'

    @api.model_create_multi
    def create(self, vals_list):
        raise UserError(_retired_sentence())

    def action_start_import(self):
        raise UserError(_retired_sentence())

    def action_load_preview(self):
        raise UserError(_retired_sentence())
