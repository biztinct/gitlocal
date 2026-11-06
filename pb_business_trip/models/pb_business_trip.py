# Part of Payobook. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

# Fields frozen once a trip is authorized (safety rail 2). A change requires
# reset-to-draft (legal only from submitted/refused) — never from approved.
_LOCKED_FIELDS = {
    'employee_id', 'destination_city', 'destination_country_id', 'purpose',
    'date_from', 'date_to', 'per_diem_rate', 'policy_id', 'advance_amount',
}

# Approver-tier resolution chains (env.ref fallback — a demo must never
# dead-end because the ideal group isn't installed; safety rail 4).
_FINANCE_GROUPS = ('account.group_account_invoice', 'account.group_account_user',
                   'om_hr_payroll.group_hr_payroll_manager')
_HR_GROUPS = ('om_hr_payroll.group_hr_payroll_manager', 'hr.group_hr_manager')
_MANAGER_GROUPS = ('hr_attendance.group_hr_attendance_officer', 'hr.group_hr_user')


class PbBusinessTrip(models.Model):
    _name = 'pb.business.trip'
    _description = 'Business Trip'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'biz.approval.chain.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, tracking=True,
        default=lambda self: self.env.user.employee_id)
    manager_id = fields.Many2one(
        'hr.employee', string='Manager', related='employee_id.parent_id',
        store=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department', string='Department', related='employee_id.department_id',
        store=True, readonly=True)

    destination_city = fields.Char(string='Destination City')
    destination_country_id = fields.Many2one('res.country', string='Country')
    purpose = fields.Text(string='Purpose', required=True)
    date_from = fields.Date(string='From', required=True, tracking=True)
    date_to = fields.Date(string='To', required=True, tracking=True)
    duration_days = fields.Integer(
        string='Days', compute='_compute_duration', store=True)

    policy_id = fields.Many2one('pb.trip.policy', string='Per-Diem Policy')
    per_diem_rate = fields.Monetary(string='Per-Diem / Day', tracking=True)
    per_diem_total = fields.Monetary(
        string='Per-Diem Total', compute='_compute_money', store=True)
    advance_amount = fields.Monetary(string='Cash Advance', tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id, required=True)

    line_ids = fields.One2many(
        'pb.business.trip.line', 'trip_id', string='Expense Lines',
        copy=True)
    estimated_total = fields.Monetary(
        string='Estimated Total', compute='_compute_money', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('manager_approved', 'Manager Approved'),
        ('finance_approved', 'Finance Approved'),
        ('approved', 'Authorized'),
        ('refused', 'Refused'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, index=True, copy=False)

    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)

    # widget payload for the embedded ApprovalStepper (biz_approval_stepper)
    approval_widget_json = fields.Char(
        compute='_compute_approval_widget', string='Approval Trail')

    # cosmetic per-user button gates (server-side auth is _approval_can)
    can_submit = fields.Boolean(compute='_compute_can')
    can_manager_approve = fields.Boolean(compute='_compute_can')
    can_finance_approve = fields.Boolean(compute='_compute_can')
    can_hr_approve = fields.Boolean(compute='_compute_can')
    can_refuse = fields.Boolean(compute='_compute_can')
    can_reset = fields.Boolean(compute='_compute_can')
    can_cancel = fields.Boolean(compute='_compute_can')

    # ------- the chain: legal transitions (auth is decided in _approval_can) ---
    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'manager_approved'): _MANAGER_GROUPS[0],
        ('manager_approved', 'finance_approved'): _FINANCE_GROUPS[-1],
        ('finance_approved', 'approved'): _HR_GROUPS[0],
    }

    # ------------------------------------------------------------- computes
    @api.depends('date_from', 'date_to')
    def _compute_duration(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to >= rec.date_from:
                rec.duration_days = (rec.date_to - rec.date_from).days + 1
            else:
                rec.duration_days = 0

    @api.depends('per_diem_rate', 'duration_days', 'line_ids.amount')
    def _compute_money(self):
        for rec in self:
            rec.per_diem_total = rec.per_diem_rate * rec.duration_days
            rec.estimated_total = rec.per_diem_total + sum(
                rec.line_ids.mapped('amount'))

    @api.depends('state')
    def _compute_approval_widget(self):
        steps = [
            {'state': 'draft', 'label': _('Request'), 'group_label': _('Employee')},
            {'state': 'submitted', 'label': _('Submitted'), 'group_label': _('Employee')},
            {'state': 'manager_approved', 'label': _('Manager'), 'group_label': _('Line manager')},
            {'state': 'finance_approved', 'label': _('Finance'), 'group_label': _('Finance')},
            {'state': 'approved', 'label': _('Authorized'), 'group_label': _('HR')},
        ]
        for rec in self:
            if rec.id:
                rec.approval_widget_json = rec._approval_widget_payload(steps)
            else:
                rec.approval_widget_json = False

    @api.depends('state', 'manager_id', 'employee_id')
    def _compute_can(self):
        for rec in self:
            s = rec.state
            rec.can_submit = s == 'draft' and rec._approval_can('draft', 'submitted')
            rec.can_manager_approve = s == 'submitted' and rec._approval_can(
                'submitted', 'manager_approved')
            rec.can_finance_approve = s == 'manager_approved' and rec._approval_can(
                'manager_approved', 'finance_approved')
            rec.can_hr_approve = s == 'finance_approved' and rec._approval_can(
                'finance_approved', 'approved')
            rec.can_refuse = s in ('submitted', 'manager_approved',
                                   'finance_approved') and rec._approval_can_refuse(s)
            rec.can_reset = s in ('submitted', 'refused')
            rec.can_cancel = s not in ('cancelled', 'refused')

    def _can_current_user_act(self):
        """Can the current user advance this trip's current pending stage?
        Used by the cockpit's 'awaiting my approval' KPI + per-card affordance."""
        self.ensure_one()
        nexts = {'submitted': 'manager_approved',
                 'manager_approved': 'finance_approved',
                 'finance_approved': 'approved'}
        to = nexts.get(self.state)
        return bool(to and self._approval_can(self.state, to))

    # --------------------------------------------------------- authorization
    def _user_in_any(self, xmlids):
        for x in xmlids:
            try:
                if self.env.user.has_group(x):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    def _approval_can(self, from_state, to_state):
        """Server-side auth for each tier (overrides the mixin's group rule).

        The SPECIFIC line manager passes tier 2 without any group; finance/HR
        tiers resolve their group through an env.ref fallback chain."""
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        user = self.env.user
        # auth-only dereferences run sudo: we are checking WHO the user is
        # (owner / line manager), not exposing employee data — and a plain
        # base.group_user manager may lack hr.employee read (safety rail 4).
        rec = self.sudo()
        pair = (from_state, to_state)
        if pair == ('draft', 'submitted'):
            if rec.employee_id.user_id and rec.employee_id.user_id == user:
                return True
            if rec.create_uid == user:
                return True
            return self._user_in_any(('hr.group_hr_user',))
        if pair == ('submitted', 'manager_approved'):
            if rec.manager_id and rec.manager_id.user_id == user:
                return True
            return self._user_in_any(_MANAGER_GROUPS)
        if pair == ('manager_approved', 'finance_approved'):
            return self._user_in_any(_FINANCE_GROUPS)
        if pair == ('finance_approved', 'approved'):
            return self._user_in_any(_HR_GROUPS)
        return False

    # --------------------------------------------------------- lifecycle hooks
    def _before_approval_transition(self, to_state):
        if to_state == 'submitted':
            self._guard_dates()
            self._guard_trip_overlap()  # hard block

    def action_submit(self):
        self.ensure_one()
        self._advance_state('submitted')
        # soft-warn (NOT block) on an overlapping validated leave — HR decides
        warn = self._leave_overlap_warning()
        if warn:
            self.message_post(body=warn)
        return True

    def action_manager_approve(self):
        self.ensure_one()
        return self._advance_state('manager_approved')

    def action_finance_approve(self):
        self.ensure_one()
        return self._advance_state('finance_approved')

    def action_hr_approve(self):
        self.ensure_one()
        return self._advance_state('approved')

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('submitted', 'refused'):
                raise UserError(_(
                    "A trip can only be reset to draft from Submitted or "
                    "Refused. An authorized trip must be cancelled."))
            frm = rec.state
            rec._chain_state_write('draft')
            rec._log_transition(frm, 'draft', _('Reset to draft'))
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state in ('cancelled', 'refused'):
                raise UserError(_("This trip is already closed."))
            frm = rec.state
            rec._before_cancel()
            rec._chain_state_write('cancelled')
            rec._log_transition(frm, 'cancelled', _('Cancelled'))
        return True

    def _before_cancel(self):
        """Hook for the expense bridge to unlink/guard draft expenses."""
        return

    # --------------------------------------------------------------- guards
    def _guard_dates(self):
        self.ensure_one()
        if not (self.date_from and self.date_to) or self.date_to < self.date_from:
            raise UserError(_("The trip end date must be on or after the start date."))

    def _guard_trip_overlap(self):
        """Hard-block a second trip overlapping an approved/pending one."""
        self.ensure_one()
        clash = self.sudo().search([
            ('id', '!=', self.id),
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ('submitted', 'manager_approved',
                             'finance_approved', 'approved')),
            ('date_from', '<=', self.date_to),
            ('date_to', '>=', self.date_from),
        ], limit=1)
        if clash:
            raise ValidationError(_(
                "This trip overlaps an existing trip (%s, %s → %s).",
                clash.name, clash.date_from, clash.date_to))

    def _leave_overlap_warning(self):
        self.ensure_one()
        Leave = self.env['hr.leave'].sudo()
        # date_to is an inclusive DATE; leaves carry datetimes — compare
        # against the end of that day or a leave starting later on the trip's
        # last day is missed.
        end_dt = fields.Datetime.to_datetime(self.date_to) + timedelta(days=1)
        leaves = Leave.search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ('validate', 'validate1')),
            ('date_from', '<', end_dt),
            ('date_to', '>=', fields.Datetime.to_datetime(self.date_from)),
        ], limit=1)
        if leaves:
            return _(
                "This trip overlaps an approved leave (%s). Submitted anyway — "
                "HR should reconcile the overlap.", leaves.holiday_status_id.name)
        return False

    # ---------------------------------------------------- immutability rail 2
    def write(self, vals):
        # su-only bypass: a context flag here would be forgeable — call_kw
        # merges the CLIENT-supplied context, so any browser could have sent
        # {'trip_bypass_lock': 1} and edited an authorized trip.
        if not self.env.su:
            protected = _LOCKED_FIELDS & set(vals)
            rate_change = 'per_diem_rate' in vals
            for rec in self:
                # The per-diem rate is fixed the moment the trip is submitted:
                # it is the money every downstream tier approves against, so it
                # must NOT drift after the request leaves the owner's hands
                # (safety rail 2 — "editable until submit"). A change requires
                # reset-to-draft (legal only from submitted/refused).
                if rate_change and rec.state != 'draft':
                    raise UserError(_(
                        "The per-diem rate is locked once a trip is submitted. "
                        "Reset it to draft to change the rate."))
                if protected and rec.state == 'approved':
                    raise UserError(_(
                        "An authorized trip is immutable. Cancel it to make "
                        "changes (field: %s).", ', '.join(sorted(protected))))
        return super().write(vals)

    # ---------------------------------------------------- create / defaults
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'pb.business.trip') or _('New')
        return super().create(vals_list)

    # ------------------------------------------------------ policy onchanges
    @api.onchange('destination_country_id', 'destination_city')
    def _onchange_destination(self):
        if self.destination_country_id:
            policy = self.env['pb.trip.policy']._match(
                self.destination_country_id, self.company_id)
            if policy:
                self.policy_id = policy.id

    @api.onchange('policy_id')
    def _onchange_policy(self):
        if self.policy_id:
            self.per_diem_rate = self.policy_id.per_diem_rate
            if self.policy_id.currency_id:
                self.currency_id = self.policy_id.currency_id.id

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("The trip end date cannot precede the start date."))

    # -------------------------------------------- THE integration helper
    @api.model
    def _get_trip_day_map(self, employee_ids, date_from, date_to):
        """{employee_id: set(ISO dates)} of APPROVED trip days in [from, to].

        The single source every presence overlay (timecard, weekly-entry grid,
        workforce dashboard) and the payroll bridge reads. sudo — trip presence
        is system-derived and must be visible regardless of who is looking
        (same one-permission-world rail as C18.17). Underscore-private: the
        sudo search makes this a cross-company enumeration oracle, so it must
        NOT be a call_kw-reachable RPC endpoint — server-side callers only."""
        employee_ids = [int(e) for e in (employee_ids or [])]
        if not employee_ids:
            return {}
        df = fields.Date.to_date(date_from)
        dt = fields.Date.to_date(date_to)
        trips = self.sudo().search([
            ('employee_id', 'in', employee_ids),
            ('state', '=', 'approved'),
            ('date_from', '<=', dt), ('date_to', '>=', df),
        ])
        out = {}
        for t in trips:
            start = max(t.date_from, df)
            end = min(t.date_to, dt)
            days = out.setdefault(t.employee_id.id, set())
            cur = start
            while cur <= end:
                days.add(cur.isoformat())
                cur += timedelta(days=1)
        return out


class PbBusinessTripLine(models.Model):
    _name = 'pb.business.trip.line'
    _description = 'Business Trip Expense Line'
    _order = 'date, id'

    trip_id = fields.Many2one(
        'pb.business.trip', string='Trip', required=True, ondelete='cascade')
    date = fields.Date(string='Date')
    category_id = fields.Many2one('pb.trip.expense.category', string='Category')
    description = fields.Char(string='Description')
    amount = fields.Monetary(string='Amount')
    currency_id = fields.Many2one(
        related='trip_id.currency_id', string='Currency', store=True, readonly=True)
    receipt_attachment_id = fields.Many2one(
        'ir.attachment', string='Receipt')
    # expense_id lives in pb_trip_expense_bridge (core must not depend on hr_expense)

    # ------------------------------------------------ immutability rail 2
    # Rail 2 freezes "dates/rate/LINES" on an authorized trip; without this
    # guard the trip header is locked but its lines stay fully editable and
    # deletable for the owner. su-only bypass (the expense bridge links
    # expense_id via sudo during the authorization hook).
    def _check_trip_open(self):
        for line in self:
            if line.trip_id.state == 'approved':
                raise UserError(_(
                    "Expense lines of an authorized trip are immutable — "
                    "cancel the trip to make changes."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        if not (self.env.su or self.env.user._is_admin()):
            lines._check_trip_open()
        return lines

    def write(self, vals):
        exempt = self.env.su or self.env.user._is_admin()
        if not exempt:
            self._check_trip_open()
        res = super().write(vals)
        if 'trip_id' in vals and not exempt:
            self._check_trip_open()  # no re-parenting lines INTO a locked trip
        return res

    def unlink(self):
        if not (self.env.su or self.env.user._is_admin()):
            self._check_trip_open()
        return super().unlink()
