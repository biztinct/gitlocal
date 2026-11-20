# -*- coding: utf-8 -*-
"""FS-9 — Home's "people have no bank account" reads the approved account.

`pb.dashboard._home_bank_link` (`pb_dashboard/models/home_data.py`) counted a
person as having a bank account when a bank account was linked OR the old
free-text Account Number box was filled. The old box is not what anybody is
paid into; Payroll-ready stopped reading it in TIDY-E. Home now asks the SAME
question with the SAME domain: `hr.employee._pb_bank_domain()`, the one rule
behind `pb_bank_on_record` (a linked bank account, or the Vietnamese bank
file's account — both written only after approval).

The fragment is a sub-select of that domain (records under sudo, archived
people included — `_search_pb_bank_on_record` does the same), so the one
statement of `_home_no_bank` stays one statement.
"""

from odoo import api, models
from odoo.tools import SQL


class PbDashboardHomeBank(models.AbstractModel):
    _inherit = 'pb.dashboard'

    @api.model
    def _home_bank_link(self):
        Employee = self.env['hr.employee']
        if not hasattr(Employee, '_pb_bank_domain'):
            return super()._home_bank_link()
        query = Employee.sudo().with_context(active_test=False)._search(
            Employee._pb_bank_domain())
        return SQL('(p.employee_id IN %s)', query.subselect())
