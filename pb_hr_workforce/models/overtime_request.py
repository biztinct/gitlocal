# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class OvertimeRequest(models.Model):
    _name = 'hr.overtime.request'
    _description = 'Overtime Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee',
                                   required=True, tracking=True,
                                   default=lambda self: self.env.user.employee_id)
    department_id = fields.Many2one('hr.department', string='Department',
                                    related='employee_id.department_id',
                                    store=True, readonly=True)
    manager_id = fields.Many2one('hr.employee', string='Manager',
                                  related='employee_id.parent_id',
                                  store=True, readonly=True)

    date = fields.Date(string='Date', required=True, tracking=True,
                        default=fields.Date.context_today)
    planned_hours = fields.Float(string='Planned OT Hours', required=True,
                                  tracking=True)
    actual_hours = fields.Float(string='Actual Hours', tracking=True)
    approved_hours = fields.Float(string='Approved Hours', tracking=True)
    # Bonus Hours (Phase K): the portion of an OT entry BEYOND the pb.ot.ceiling
    # period allowance — never blocked, never dropped (adults). readonly=True is
    # a facade/RPC guard (it does NOT block server-side ORM writes); this field
    # has EXACTLY TWO writers — the grid save (_save_ot) and the approve-time
    # recompute (action_approve) — via the ORM. It feeds the BONHRS payroll input
    # (bridge), NEVER the OTHRS* / allowance counters (rail 2, C18.55b).
    bonus_hours = fields.Float(string='Bonus Hours', readonly=True, tracking=True,
                                help='OT hours beyond the ceiling allowance. Paid '
                                     'via the BONHRS input if the config uses it; '
                                     'outside the OT caps by definition.')
    total_hours = fields.Float(string='Total Hours', compute='_compute_total_hours',
                                help='Approved (within cap) + bonus (overflow).')

    overtime_type = fields.Selection([
        ('weekday', 'Weekday'),
        ('weekend', 'Weekend'),
        ('holiday', 'Public Holiday'),
        ('night', 'Night'),
    ], string='Overtime Type', required=True, default='weekday', tracking=True)

    overtime_config_id = fields.Many2one('hr.overtime.config',
                                          string='OT Rule',
                                          compute='_compute_overtime_config',
                                          store=True)
    rate_multiplier = fields.Float(string='Rate',
                                    related='overtime_config_id.rate_multiplier',
                                    store=True)
    rate_display = fields.Char(compute='_compute_rate_display_local')

    reason = fields.Text(string='Reason', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string='Status', default='draft', tracking=True, index=True)

    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)

    @api.depends('employee_id', 'date')
    def _compute_name(self):
        for rec in self:
            emp = rec.employee_id.name or 'New'
            dt = rec.date.strftime('%d/%m/%Y') if rec.date else ''
            rec.name = f'OT/{emp}/{dt}'

    @api.depends('overtime_type', 'company_id')
    def _compute_overtime_config(self):
        Config = self.env['hr.overtime.config']
        for rec in self:
            country = rec.employee_id.country_id
            config = Config.search([
                ('overtime_type', '=', rec.overtime_type),
                '|',
                ('country_id', '=', country.id if country else False),
                ('country_id', '=', False),
                '|',
                ('company_id', '=', rec.company_id.id),
                ('company_id', '=', False),
            ], order='country_id desc, company_id desc', limit=1)
            rec.overtime_config_id = config.id if config else False

    @api.depends('rate_multiplier')
    def _compute_rate_display_local(self):
        for rec in self:
            rec.rate_display = f'{int(rec.rate_multiplier * 100)}%' if rec.rate_multiplier else ''

    @api.depends('approved_hours', 'bonus_hours')
    def _compute_total_hours(self):
        for rec in self:
            rec.total_hours = (rec.approved_hours or 0.0) + (rec.bonus_hours or 0.0)

    def action_submit(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec.state = 'submitted'
            if rec.manager_id and rec.manager_id.user_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=rec.manager_id.user_id.id,
                    summary=_('Overtime Request to Approve: %s') % rec.name,
                )

    def action_approve(self):
        Ceil = self.env['pb.ot.ceiling']
        for rec in self.filtered(lambda r: r.state == 'submitted'):
            # Recompute the split AUTHORITATIVELY at approval (rail 4): other
            # requests may have been approved since the grid saved this draft, so
            # the allowance can have shrunk. Exclude this record's own id (it is
            # 'submitted', so already counted by _allowance). The entered figure
            # is actual_hours (grid/form), falling back to planned_hours.
            entry = rec.actual_hours or rec.planned_hours or 0.0
            approved, bonus = Ceil._split(rec.employee_id, rec.date, entry,
                                          exclude_ids=[rec.id])
            # Note: bonus_hours is written here (a sanctioned writer) — it is NOT
            # in the young-worker @api.constrains trigger set, so approval never
            # trips the minor gate; minors are hard-blocked at submission instead
            # (C18.63), so a minor request can never reach this loop.
            rec.write({
                'state': 'approved',
                'approved_hours': approved,
                'bonus_hours': bonus,
            })
            rec.activity_feedback(['mail.mail_activity_data_todo'])

    def action_refuse(self):
        self.filtered(lambda r: r.state == 'submitted').write({
            'state': 'refused',
            'approved_hours': 0,
            'bonus_hours': 0,
        })

    def action_reset_draft(self):
        self.filtered(lambda r: r.state in ('submitted', 'refused')).write({
            'state': 'draft',
        })
