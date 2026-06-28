# -*- coding: utf-8 -*-
from odoo import _, api, fields, models

# Salary-category code buckets (mirror pb_hr_workforce payroll_report).
NET_CODES = ('NET',)
GROSS_CODES = ('GROSS',)
DED_CODES = ('DED', 'DEDUCTION', 'COMP')


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    # Index the run FK — every cockpit aggregates payslips per run; without this
    # the SQL roll-ups seq-scan the payslip table as volume grows.
    payslip_run_id = fields.Many2one(index=True)


class HrPayslipLine(models.Model):
    _inherit = 'hr.payslip.line'

    # Index the slip FK — payslip-line aggregations join on this; essential for
    # fast roll-ups as line volume reaches the millions.
    slip_id = fields.Many2one(index=True)


class HrPayslipRun(models.Model):
    _inherit = 'hr.payslip.run'

    # Always show the full pipeline as columns (even empty HR/GM stages),
    # like the old board — native kanban hides empty selection groups otherwise.
    state = fields.Selection(group_expand='_pb_group_expand_state')

    @api.model
    def _pb_group_expand_state(self, values, domain):
        return ['draft', 'level1', 'level2', 'done']

    # STORED: computed once when the run's payslips change, read instantly forever.
    # Aggregating every payslip line at read time does not scale (a 600k-row
    # roll-up spills to disk on a small box and takes seconds per cockpit load).
    pb_employee_count = fields.Integer(
        string='Employees', compute='_compute_pb_totals', store=True)
    pb_total_net = fields.Monetary(
        string='Total Net', compute='_compute_pb_totals',
        currency_field='pb_currency_id', store=True, index=True)
    pb_total_gross = fields.Monetary(
        string='Total Gross', compute='_compute_pb_totals',
        currency_field='pb_currency_id', store=True)
    pb_total_deductions = fields.Monetary(
        string='Total Deductions', compute='_compute_pb_totals',
        currency_field='pb_currency_id', store=True)
    pb_currency_id = fields.Many2one(
        'res.currency', compute='_compute_pb_totals', store=True)

    @api.depends('slip_ids', 'slip_ids.line_ids', 'slip_ids.line_ids.total',
                 'slip_ids.state')
    def _compute_pb_totals(self):
        # Aggregate in SQL — iterating slip_ids.line_ids through the ORM reads
        # hundreds of thousands of records at scale and hangs the kanban.
        default_cur = self.env.company.currency_id
        for run in self:
            run.pb_employee_count = 0
            run.pb_total_net = run.pb_total_gross = run.pb_total_deductions = 0.0
            company = getattr(run, 'company_id', False) or self.env.company
            run.pb_currency_id = company.currency_id or default_cur
        run_ids = [r.id for r in self if r.id]
        if not run_ids:
            return
        cr = self.env.cr
        cr.execute("""
            SELECT p.payslip_run_id, count(*)
            FROM hr_payslip p
            WHERE p.payslip_run_id IN %s AND p.state != 'cancel'
            GROUP BY p.payslip_run_id
        """, (tuple(run_ids),))
        counts = dict(cr.fetchall())
        cr.execute("""
            SELECT p.payslip_run_id, c.code, COALESCE(SUM(pl.total), 0)
            FROM hr_payslip_line pl
            JOIN hr_payslip p ON p.id = pl.slip_id AND p.state != 'cancel'
            JOIN hr_salary_rule_category c ON c.id = pl.category_id
            WHERE p.payslip_run_id IN %s
              AND c.code IN ('NET', 'GROSS', 'DED', 'DEDUCTION', 'COMP')
            GROUP BY p.payslip_run_id, c.code
        """, (tuple(run_ids),))
        agg = {}
        for rid, code, total in cr.fetchall():
            agg.setdefault(rid, {})[code] = total or 0.0
        for run in self:
            d = agg.get(run.id, {})
            run.pb_employee_count = counts.get(run.id, 0)
            run.pb_total_net = d.get('NET', 0.0)
            run.pb_total_gross = d.get('GROSS', 0.0)
            run.pb_total_deductions = abs(d.get('DED', 0.0) + d.get('DEDUCTION', 0.0)
                                          + d.get('COMP', 0.0))

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

    # ---- Pay Salary (post-approval disbursement) — surfaced on Done cards ----
    def _pb_toast(self, message):
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Pay Salary'), 'message': message,
                           'type': 'warning', 'sticky': False}}

    def action_pb_bank_export(self):
        """Open the bank-export wizard pre-scoped to this run."""
        self.ensure_one()
        if 'payroll.bank.export.wizard' not in self.env:
            return self._pb_toast(_('Bank export is not available on this server.'))
        cfg = self.slip_ids.mapped('formula_config_id')[:1]
        ctx = {'default_payslip_run_id': self.id,
               'default_date_from': self.date_start, 'default_date_to': self.date_end}
        if cfg:
            ctx['default_formula_config_id'] = cfg.id
        return {'type': 'ir.actions.act_window', 'name': _('Export Bank File'),
                'res_model': 'payroll.bank.export.wizard', 'view_mode': 'form',
                'target': 'new', 'context': ctx}

    def action_pb_journals(self):
        """Open the period's journal entries for this company."""
        self.ensure_one()
        if 'account.move' not in self.env:
            return self._pb_toast(_('Accounting is not installed.'))
        return {'type': 'ir.actions.act_window', 'name': _('Journal Entries'),
                'res_model': 'account.move', 'view_mode': 'list,form',
                'domain': [('company_id', '=', self.env.company.id),
                           ('date', '>=', self.date_start), ('date', '<=', self.date_end)],
                'context': {'search_default_posted': 1}}

    def action_pb_payments(self):
        """Open the period's payments for this company."""
        self.ensure_one()
        if 'account.payment' not in self.env:
            return self._pb_toast(_('Accounting is not installed.'))
        return {'type': 'ir.actions.act_window', 'name': _('Payments'),
                'res_model': 'account.payment', 'view_mode': 'list,form',
                'domain': [('company_id', '=', self.env.company.id),
                           ('date', '>=', self.date_start), ('date', '<=', self.date_end)]}
