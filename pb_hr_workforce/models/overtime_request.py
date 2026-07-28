# Part of Payobook. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

# C18.24/76: the workflow fields feed payroll (OTHRS*/BONHRS), so they are
# SEALED at the ORM — field-level readonly blocks nothing at call_kw. Only the
# sanctioned writers (the actions below and the sudo'd grid/facade paths) carry
# the module-level object() identity token; a client context can never equal it.
_OT_CHAIN_KEY = 'pb_ot_chain_write'
_OT_CHAIN_TOKEN = object()
_OT_SEALED_FIELDS = {'state', 'approved_hours', 'bonus_hours'}

# Who may DECIDE a submitted request (approve/refuse): the attendance
# officer/manager tier, or the employee's own line manager (no group needed —
# the trip/correction precedent). Never the employee themself.
_OT_DECIDER_GROUPS = ('hr_attendance.group_hr_attendance_manager',
                      'hr_attendance.group_hr_attendance_officer')


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
    # period allowance — never blocked, never dropped (adults). Sealed at the
    # ORM together with state/approved_hours (see _ot_seal_ok — review K-F1:
    # readonly alone is UI-only); its sanctioned writers are the grid save
    # (_save_ot, sudo), the approve-time recompute and the refuse zero-out
    # below. It feeds the BONHRS payroll input (bridge), NEVER the OTHRS* /
    # allowance counters (rail 2, C18.55b).
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

    # ------------------------------------------------------------ the seal
    def _ot_seal_ok(self):
        return (self.env.context.get(_OT_CHAIN_KEY) is _OT_CHAIN_TOKEN
                or self.env.su or self.env.user._is_admin())

    def _ot_chain(self):
        """The recordset the sanctioned writers use (carries the sentinel)."""
        return self.with_context(**{_OT_CHAIN_KEY: _OT_CHAIN_TOKEN})

    @api.model_create_multi
    def create(self, vals_list):
        # a request is born draft with a zero split; only sanctioned writers
        # (the sudo'd grid save) may seed workflow values
        if not self._ot_seal_ok():
            for vals in vals_list:
                for f in _OT_SEALED_FIELDS.intersection(vals):
                    vals.pop(f)
        return super().create(vals_list)

    def write(self, vals):
        if not self._ot_seal_ok():
            forged = _OT_SEALED_FIELDS.intersection(vals)
            if forged:
                raise AccessError(_(
                    "Overtime state and hours feed payroll and can only change "
                    "through the overtime actions, not directly: %s.",
                    ', '.join(sorted(forged))))
        return super().write(vals)

    def _ot_can_decide(self):
        """May the current user approve/refuse THIS submitted request?

        The attendance officer/manager tier or the employee's own line manager —
        and never the employee themself (self-approval feeds their own payslip).
        Facades (desk/grid/team) gate themselves and act as the real user, so a
        raw call_kw hits exactly this same wall.
        """
        self.ensure_one()
        u = self.env.user
        if self.env.su or u._is_admin():
            return True
        # auth-only dereference under sudo (the correction precedent): asking
        # "who is this user to this record" must answer False, not explode with
        # an AccessError, for someone with no OT access at all
        rec = self.sudo()
        if rec.employee_id.user_id and rec.employee_id.user_id == u:
            return False
        if rec.manager_id and rec.manager_id.user_id == u:
            return True
        for g in _OT_DECIDER_GROUPS:
            try:
                if u.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    def _ot_require_decide(self):
        for rec in self:
            if not rec._ot_can_decide():
                if rec.sudo().employee_id.user_id == self.env.user:
                    raise AccessError(_(
                        "You cannot approve or refuse your own overtime (%s).",
                        rec.name))
                raise AccessError(_(
                    "Deciding an overtime request needs the attendance "
                    "officer/manager role or line management of %s.",
                    rec.employee_id.name))

    # ------------------------------------------------------------- actions
    def action_submit(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec._ot_chain().write({'state': 'submitted'})
            if rec.manager_id and rec.manager_id.user_id:
                rec.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=rec.manager_id.user_id.id,
                    summary=_('Overtime Request to Approve: %s') % rec.name,
                )

    def action_approve(self):
        Ceil = self.env['pb.ot.ceiling']
        todo = self.filtered(lambda r: r.state == 'submitted')
        todo._ot_require_decide()
        for rec in todo:
            # Recompute the split AUTHORITATIVELY at approval (rail 4): other
            # requests may have been approved since the grid saved this draft, so
            # the allowance can have shrunk. Exclude this record's own id (it is
            # 'submitted', so already counted by _allowance). The entered figure
            # is actual_hours (grid/form), falling back to planned_hours.
            entry = rec.actual_hours or rec.planned_hours or 0.0
            approved, bonus = Ceil._split(rec.employee_id, rec.date, entry,
                                          exclude_ids=[rec.id])
            # Note: bonus_hours is written here (a sanctioned writer) — it is NOT
            # in the young-worker @api.constrains trigger set; pb_young_worker
            # re-runs its minor gate in its own action_approve override, so a
            # legacy minor row still cannot be approved (review K-F7).
            rec._ot_chain().write({
                'state': 'approved',
                'approved_hours': approved,
                'bonus_hours': bonus,
            })
            rec.activity_feedback(['mail.mail_activity_data_todo'])

    def action_refuse(self):
        todo = self.filtered(lambda r: r.state == 'submitted')
        todo._ot_require_decide()
        # the zero-out keeps refused rows out of every payroll stream — a
        # sanctioned writer like the approve recompute (C18.55b)
        todo._ot_chain().write({
            'state': 'refused',
            'approved_hours': 0,
            'bonus_hours': 0,
        })

    def action_reset_draft(self):
        for rec in self.filtered(lambda r: r.state in ('submitted', 'refused')):
            # the requester may pull back their own submission; deciders may too
            if not (rec._ot_can_decide()
                    or (rec.employee_id.user_id and rec.employee_id.user_id == self.env.user)
                    or rec.create_uid == self.env.user):
                raise AccessError(_(
                    "Only the requester or an overtime decider can reset %s "
                    "to draft.", rec.name))
            rec._ot_chain().write({'state': 'draft'})
