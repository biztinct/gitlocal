# -*- coding: utf-8 -*-
"""The one hook that keeps "who leads this function" true.

A budget row stores its function and that function's head, because a record rule
needs a plain indexed column to compare against. `@api.depends` cannot express
"any ancestor's manager", so the honest way to keep a stored answer correct is to
recompute it at the moment the answer changes — when a department is re-parented
or given a new manager.

Everything else about `hr.department` is left alone. This module adds no field to
it, no view and no rule.
"""

import logging

from odoo import models

_logger = logging.getLogger(__name__)

#: The two columns that can move a budget row's function or its head.
WATCHED = ('parent_id', 'manager_id')


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    def write(self, vals):
        res = super().write(vals)
        if not any(k in vals for k in WATCHED):
            return res
        # The whole subtree, not just these departments: re-parenting a branch
        # moves the function of everything under it.
        try:
            self._pb_budget_refresh_subtree()
        except Exception as e:                 # noqa: BLE001
            # A department edit must never fail because a budget row could not
            # be re-stamped; the nightly top-up puts it right.
            _logger.warning('pb_budget: could not restamp budget functions: %s', e)
        return res

    def _pb_budget_refresh_subtree(self):
        Budget = self.env['wfp.budget.actual'].sudo()
        depts = self.search([('id', 'child_of', self.ids)])
        rows = Budget.search([('department_id', 'in', depts.ids)])
        if not rows:
            return 0
        for name in ('pb_function_id', 'pb_function_head_user_id'):
            self.env.add_to_compute(Budget._fields[name], rows)
        rows.flush_recordset()
        return len(rows)
