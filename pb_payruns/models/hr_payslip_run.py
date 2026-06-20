# -*- coding: utf-8 -*-
from odoo import api, fields, models

# Salary-category code buckets (mirror pb_hr_workforce payroll_report).
NET_CODES = ('NET',)
GROSS_CODES = ('GROSS',)
DED_CODES = ('DED', 'DEDUCTION', 'COMP')


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    # Always show the full pipeline as columns (even empty HR/GM stages),
    # like the old board — native kanban hides empty selection groups otherwise.
    state = fields.Selection(group_expand='_pb_group_expand_state')

    @api.model
    def _pb_group_expand_state(self, values, domain):
        return ['draft', 'level1', 'level2', 'done']

    pb_employee_count = fields.Integer(
        string='Employees', compute='_compute_pb_totals')
    pb_total_net = fields.Monetary(
        string='Total Net', compute='_compute_pb_totals',
        currency_field='pb_currency_id')
    pb_total_gross = fields.Monetary(
        string='Total Gross', compute='_compute_pb_totals',
        currency_field='pb_currency_id')
    pb_total_deductions = fields.Monetary(
        string='Total Deductions', compute='_compute_pb_totals',
        currency_field='pb_currency_id')
    pb_currency_id = fields.Many2one(
        'res.currency', compute='_compute_pb_totals')

    @api.depends('slip_ids', 'slip_ids.line_ids', 'slip_ids.line_ids.total',
                 'slip_ids.state')
    def _compute_pb_totals(self):
        for run in self:
            slips = run.slip_ids.filtered(lambda s: s.state != 'cancel')
            net = gross = ded = 0.0
            for line in slips.mapped('line_ids'):
                code = line.category_id.code
                if code in NET_CODES:
                    net += line.total
                elif code in GROSS_CODES:
                    gross += line.total
                elif code in DED_CODES:
                    ded += line.total
            run.pb_employee_count = len(slips)
            run.pb_total_net = net
            run.pb_total_gross = gross
            run.pb_total_deductions = abs(ded)
            company = getattr(run, 'company_id', False) or self.env.company
            run.pb_currency_id = company.currency_id or self.env.company.currency_id

    # ---- context-aware permission flags for kanban card buttons ----
    pb_can_submit = fields.Boolean(compute='_compute_pb_perms')
    pb_can_approve_hr = fields.Boolean(compute='_compute_pb_perms')
    pb_can_approve_gm = fields.Boolean(compute='_compute_pb_perms')
    pb_can_reject = fields.Boolean(compute='_compute_pb_perms')
    pb_is_done = fields.Boolean(compute='_compute_pb_perms')
    pb_awaiting_me = fields.Boolean(
        compute='_compute_pb_awaiting_me', search='_search_pb_awaiting_me')

    def _pb_user_roles(self):
        u = self.env.user
        officer = (u.has_group('pb_hr_payroll_base.group_payroll_base_officer')
                   or u.has_group('pb_hr_payroll_base.group_payroll_base_manager')
                   or u.has_group('pb_hr_payroll_base.group_payroll_super_admin'))
        manager = (u.has_group('pb_hr_payroll_base.group_payroll_base_manager')
                   or u.has_group('pb_hr_payroll_base.group_payroll_super_admin'))
        final = (u.has_group('pb_hr_payroll_base.group_payroll_final_approver')
                 or u.has_group('pb_hr_payroll_base.group_payroll_super_admin'))
        return officer, manager, final

    @api.depends_context('uid')
    @api.depends('state')
    def _compute_pb_perms(self):
        officer, manager, final = self._pb_user_roles()
        for run in self:
            st = run.state
            run.pb_can_submit = st == 'draft' and officer
            run.pb_can_approve_hr = st == 'level1' and manager
            run.pb_can_approve_gm = st == 'level2' and final
            run.pb_can_reject = st in ('draft', 'level1', 'level2') and (officer or manager or final)
            run.pb_is_done = st == 'done'

    @api.depends_context('uid')
    @api.depends('state')
    def _compute_pb_awaiting_me(self):
        officer, manager, final = self._pb_user_roles()
        for run in self:
            run.pb_awaiting_me = ((run.state == 'level1' and manager)
                                  or (run.state == 'level2' and final))

    def _search_pb_awaiting_me(self, operator, value):
        _officer, manager, final = self._pb_user_roles()
        states = []
        if manager:
            states.append('level1')
        if final:
            states.append('level2')
        positive = (operator in ('=', '!=') and bool(value)) == (operator == '=')
        match = [('state', 'in', states)] if states else [('id', '=', 0)]
        return match if positive else (['!'] + match)
