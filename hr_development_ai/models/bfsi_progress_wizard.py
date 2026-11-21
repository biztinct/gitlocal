# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class BFSIActionPlanProgressWizard(models.TransientModel):
    _name = 'bfsi.action.plan.progress.wizard'
    _description = 'Action Plan Progress Report Wizard'

    action_plan_id = fields.Many2one(
        'bfsi.action.plan',
        string='Action Plan',
        required=True,
        readonly=True,
    )
    employee_notes = fields.Text(
        string='Progress Notes',
        help='Describe what progress you have made',
    )
    item_ids = fields.Many2many(
        'bfsi.action.plan.item',
        string='Action Items',
        compute='_compute_item_ids',
    )

    @api.depends('action_plan_id')
    def _compute_item_ids(self):
        for wiz in self:
            wiz.item_ids = wiz.action_plan_id.item_ids

    def action_submit_progress(self):
        """Submit the progress report"""
        self.ensure_one()
        plan = self.action_plan_id

        if self.employee_notes:
            plan.employee_notes = (plan.employee_notes or '') + \
                f"\n\n[{fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}]\n{self.employee_notes}"

        plan.last_update_date = fields.Datetime.now()

        # Auto-transition state
        if plan.state == 'committed':
            plan.state = 'in_progress'

        if plan.progress_percentage >= 100:
            plan.state = 'completed'
            plan.completion_date = fields.Date.today()

        return {'type': 'ir.actions.act_window_close'}
