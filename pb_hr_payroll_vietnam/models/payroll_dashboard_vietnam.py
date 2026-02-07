# -*- coding: utf-8 -*-

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


class PayrollDashboardVietnam(models.Model):
    _inherit = ['payroll.dashboard']

    def action_open_import_batch(self):
        """Open payroll import batches in kanban (with create) then fall back to tree/form.

        This wraps the standard pb_hr_payroll_formula action but forces a refresh and
        ensures a kanban view is the first one shown so the New button is immediately
        available.
        """
        action_ref = self.env.ref('pb_hr_payroll_formula.action_payroll_import_batch', raise_if_not_found=False)
        if not action_ref:
            raise UserError(_('Payroll import batches are unavailable. Install pb_hr_payroll_formula to use this feature.'))
        action = action_ref.read()[0]

        kanban_view = self.env.ref('pb_hr_payroll_vietnam.view_payroll_import_batch_kanban_vn', raise_if_not_found=False)
        tree_view = self.env.ref('pb_hr_payroll_formula.view_payroll_import_batch_tree', raise_if_not_found=False)
        form_view = self.env.ref('pb_hr_payroll_formula.view_payroll_import_batch_form', raise_if_not_found=False)

        views = []
        if kanban_view:
            views.append((kanban_view.id, 'kanban'))
        if tree_view:
            views.append((tree_view.id, 'tree'))
        if form_view:
            views.append((form_view.id, 'form'))

        ctx = dict(self.env.context or {})
        # action context might be a string (eval-able) or a dict
        raw_ctx = action.get('context')
        if raw_ctx:
            try:
                parsed_ctx = raw_ctx if isinstance(raw_ctx, dict) else safe_eval(raw_ctx)
                if isinstance(parsed_ctx, dict):
                    ctx.update(parsed_ctx)
            except Exception:
                # fall back quietly if eval fails or context is not a dict
                pass
        ctx.update({
            'create': True,
            'force_refresh': True,   # nudge the client to refresh so the New button shows
            'reload': True,
        })

        action.update({
            'view_mode': 'kanban,tree,form',
            'views': views,
            'target': 'current',
            'context': ctx,
        })
        return action

    def action_open_govt_reports(self):
        """Open government reports selection wizard"""
        return {
            'name': 'Select Government Report',
            'type': 'ir.actions.act_window',
            'res_model': 'pb.govt.report.selector',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_country': 'vietnam'},
        }
