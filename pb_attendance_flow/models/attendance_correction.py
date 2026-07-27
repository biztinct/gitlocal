# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""hr.attendance.correction — the ONLY way this module mutates a punch (Phase G §3).

A correction request (create / adjust / delete a punch) rides the generic
``biz.approval.chain.mixin``: an employee (or an officer) files it, and it is
approved by an attendance OFFICER or the employee's own LINE MANAGER (parent_id
user, no group needed — the trip precedent). On approval, a SINGLE guarded writer
``_apply()`` performs the mutation under a module-level ``object()`` sentinel
(C18.24) and stamps ``pb_entry_source='correction'``.

The system never invents a punch: nothing here writes ``hr.attendance`` outside
``_apply``, and ``_apply`` runs only after a real human approves the request. A
young-worker breach on apply is caught and lands the request in ``refused`` with
the law message as its reason — never a traceback (test 7).
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .hr_attendance import PB_ATT_CORRECTION_CTX, _CORR_TOKEN

# Approver groups for the officer tier. The employee's own manager also passes,
# via _approval_can. `hr.group_hr_user` is a LAST-RESORT fallback used only when
# the attendance groups are absent from the registry (review G-L12: checked
# unconditionally it silently widened approval to every basic HR user).
_OFFICER_GROUP = 'hr_attendance.group_hr_attendance_officer'
_OFFICER_TIER = ('hr_attendance.group_hr_attendance_officer',
                 'hr_attendance.group_hr_attendance_manager')
_OFFICER_LAST_RESORT = ('hr.group_hr_user',)

# The facts the approver rules on. Once a correction leaves draft they FREEZE —
# an employee could otherwise rewrite the times between submit and approve and
# have the manager unknowingly apply them into payroll worked-days (review
# G-H2, the C18.31 TOCTOU class).
_REVIEW_FIELDS = frozenset({'employee_id', 'date', 'correction_type',
                            'attendance_id', 'new_check_in', 'new_check_out',
                            'reason'})


class HrAttendanceCorrection(models.Model):
    _name = 'hr.attendance.correction'
    _description = 'Attendance Correction Request'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'biz.approval.chain.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, tracking=True,
        index=True, default=lambda self: self.env.user.employee_id)
    manager_id = fields.Many2one(
        'hr.employee', string='Manager', related='employee_id.parent_id',
        store=True, readonly=True)
    department_id = fields.Many2one(
        'hr.department', related='employee_id.department_id',
        store=True, readonly=True)
    date = fields.Date(string='Day', required=True, tracking=True, index=True)

    correction_type = fields.Selection([
        ('create', 'Add a punch'),
        ('adjust', 'Adjust a punch'),
        ('delete', 'Remove a punch'),
    ], string='Type', required=True, default='create', tracking=True)
    attendance_id = fields.Many2one(
        'hr.attendance', string='Target Punch', tracking=True,
        help='The existing punch to adjust or remove (required for those types).')
    new_check_in = fields.Datetime(string='New Check-In')
    new_check_out = fields.Datetime(string='New Check-Out')
    reason = fields.Text(string='Reason', required=True, tracking=True)
    # free link back to the feed row that spawned this (missing_punch/late/…)
    exception_kind = fields.Char(string='From Exception', readonly=True)
    # the surfaced refusal reason when an approved apply was blocked (e.g. the
    # young-worker daily cap) — the request lands in 'refused', not a traceback.
    apply_error = fields.Text(string='Apply Error', readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Applied'),
        ('refused', 'Refused'),
    ], string='Status', default='draft', tracking=True, index=True, copy=False)

    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)

    approval_widget_json = fields.Char(
        compute='_compute_approval_widget', string='Approval Trail')
    can_submit = fields.Boolean(compute='_compute_can')
    can_approve = fields.Boolean(compute='_compute_can')
    can_refuse = fields.Boolean(compute='_compute_can')

    _approval_transitions = {
        ('draft', 'submitted'): None,
        ('submitted', 'approved'): _OFFICER_GROUP,
    }

    # ------------------------------------------------------------- computes
    @api.depends('state')
    def _compute_approval_widget(self):
        steps = [
            {'state': 'draft', 'label': _('Filed'), 'group_label': _('Employee')},
            {'state': 'submitted', 'label': _('Submitted'), 'group_label': _('Employee / Officer')},
            {'state': 'approved', 'label': _('Applied'), 'group_label': _('Manager / Officer')},
        ]
        for rec in self:
            rec.approval_widget_json = rec._approval_widget_payload(steps) if rec.id else False

    @api.depends('state', 'employee_id', 'manager_id')
    def _compute_can(self):
        for rec in self:
            s = rec.state
            rec.can_submit = s == 'draft' and rec._approval_can('draft', 'submitted')
            rec.can_approve = s == 'submitted' and rec._approval_can('submitted', 'approved')
            rec.can_refuse = s == 'submitted' and rec._approval_can_refuse(s)

    # --------------------------------------------------------- authorization
    def _user_in_any(self, xmlids):
        for x in xmlids:
            try:
                if self.env.user.has_group(x):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    def _user_in_officer_tier(self):
        """Attendance officer/manager; hr.group_hr_user counts ONLY when the
        attendance groups don't exist on this database (review G-L12)."""
        if self._user_in_any(_OFFICER_TIER):
            return True
        try:
            self.env.ref(_OFFICER_GROUP)
            return False        # the real tier exists — no fallback
        except ValueError:
            return self._user_in_any(_OFFICER_LAST_RESORT)

    def _approval_can(self, from_state, to_state):
        """Officer-tier auth, PLUS the employee's own line manager (no group).

        Safety rail 2: the user who filed the request may never approve their
        own — admin excepted.
        """
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        user = self.env.user
        rec = self.sudo()  # auth-only dereference (who is the user?), rail 4
        pair = (from_state, to_state)
        if pair == ('draft', 'submitted'):
            if rec.employee_id.user_id and rec.employee_id.user_id == user:
                return True
            if rec.create_uid == user:
                return True
            return self._user_in_officer_tier()
        if pair == ('submitted', 'approved'):
            # approver ≠ requester (the person who filed it)
            if rec.create_uid == user or (
                    rec.employee_id.user_id and rec.employee_id.user_id == user):
                return False
            # the specific line manager passes with no group…
            if rec.manager_id and rec.manager_id.user_id == user:
                return True
            # …else any attendance officer / manager
            return self._user_in_officer_tier()
        return False

    # ------------------------------------------------------- the review freeze
    def write(self, vals):
        # Review G-H2 (C18.31 TOCTOU): the facts an approver rules on are
        # immutable once the correction leaves draft. Reset to draft first to
        # amend; state/apply_error stay writable (the chain mixin seals state
        # with its own sentinel).
        if not (self.env.su or self.env.user._is_admin()):
            frozen = _REVIEW_FIELDS.intersection(vals)
            if frozen:
                for rec in self:
                    if rec.state != 'draft':
                        raise AccessError(_(
                            "A %(state)s correction can no longer be edited "
                            "(%(fields)s) — reset it to draft first.",
                            state=rec.state, fields=', '.join(sorted(frozen))))
        return super().write(vals)

    # --------------------------------------------------------- actions
    def action_submit(self):
        for rec in self:
            rec._check_ready_to_submit()
            rec._advance_state('submitted')
        return True

    def _check_ready_to_submit(self):
        """Completeness is enforced at SUBMIT, not create — a draft may be
        filled in incrementally by the composer (pick the target punch, type the
        times) before it is sent for approval."""
        self.ensure_one()
        if self.correction_type in ('adjust', 'delete') and not self.attendance_id:
            raise UserError(_(
                "Choose the punch to %s before submitting.",
                _('adjust') if self.correction_type == 'adjust' else _('remove')))
        if self.correction_type == 'create' and not self.new_check_in:
            raise UserError(_("Enter a check-in time before submitting."))
        if self.correction_type == 'adjust' and not (
                self.new_check_in or self.new_check_out):
            raise UserError(_(
                "Enter the corrected check-in and/or check-out time before "
                "submitting an adjustment."))
        if not (self.reason or '').strip():
            raise UserError(_("A reason is required before submitting."))

    def action_approve(self):
        """Approve → apply. The apply runs in a savepoint FIRST: if it succeeds
        the chain advances to 'approved'; if a guard (young-worker cap, overlap,
        …) refuses it, the request lands in 'refused' with the surfaced reason
        instead of raising (test 7). The single guarded writer is _apply()."""
        for rec in self:
            frm = rec.state
            if frm != 'submitted':
                raise UserError(_("Only a submitted correction can be approved."))
            if not rec._approval_can(frm, 'approved'):
                raise AccessError(_(
                    "You are not allowed to approve this correction."))
            try:
                with self.env.cr.savepoint():
                    rec._apply()
            except (ValidationError, UserError) as e:
                reason = (e.args and e.args[0]) or str(e)
                rec.apply_error = reason
                rec._chain_state_write('refused')
                rec._log_transition(frm, 'refused', reason)
                continue
            rec.apply_error = False
            rec._advance_state('approved')
        return True

    def action_refuse(self, note=False):
        return self.action_refuse_chain(note=note)

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('submitted', 'refused'):
                raise UserError(_(
                    "A correction can be reset to draft only from Submitted or "
                    "Refused."))
            # same discipline as the other transitions (review G-L13): the
            # requester pulls back their own filing, or the officer tier does
            if not (self.env.su or self.env.user._is_admin()
                    or rec.create_uid == self.env.user
                    or (rec.employee_id.user_id
                        and rec.employee_id.user_id == self.env.user)
                    or self._user_in_officer_tier()):
                raise AccessError(_(
                    "Only the requester or an attendance officer can reset "
                    "this correction to draft."))
            frm = rec.state
            rec._chain_state_write('draft')
            rec.apply_error = False
            rec._log_transition(frm, 'draft', _('Reset to draft'))
        return True

    # --------------------------------------------------- THE single writer
    def _apply(self):
        """Create / adjust / delete the punch — the ONLY hr.attendance mutation
        in this module.

        Applying an APPROVED correction is a system action: the approval decision
        (state + audit log) already ran as the real clicking user (truthful log),
        so the mutation itself is sudo'd — a plain line-manager who may approve a
        report's correction has no direct hr.attendance write right. The sentinel
        context still travels with it (and su already opens the device-delete
        guard). The young-worker daily-cap @api.constrains fires under sudo too,
        so a breaching correction still raises here and is caught by the caller."""
        self.ensure_one()
        Att = self.env['hr.attendance'].sudo().with_context(
            **{PB_ATT_CORRECTION_CTX: _CORR_TOKEN})
        emp = self.employee_id
        if self.correction_type == 'create':
            if not self.new_check_in:
                raise UserError(_("A new punch needs a check-in time."))
            Att.create({
                'employee_id': emp.id,
                'check_in': self.new_check_in,
                'check_out': self.new_check_out or False,
                'pb_entry_source': 'correction',
            })
        elif self.correction_type == 'adjust':
            att = self.attendance_id.sudo()
            if not att.exists():
                raise UserError(_("The punch to adjust no longer exists."))
            # only the times the correction actually carries are written — an
            # adjust of the check-in alone must NOT wipe the existing check-out
            # (review G-M6: that reopened the punch and zeroed its hours)
            vals = {'pb_entry_source': 'correction'}
            if self.new_check_in:
                vals['check_in'] = self.new_check_in
            if self.new_check_out:
                vals['check_out'] = self.new_check_out
            att.with_context(**{PB_ATT_CORRECTION_CTX: _CORR_TOKEN}).write(vals)
        elif self.correction_type == 'delete':
            att = self.attendance_id.sudo()
            if att.exists():
                att.with_context(**{PB_ATT_CORRECTION_CTX: _CORR_TOKEN}).unlink()
        return True

    # ------------------------------------------------------------- guards
    @api.constrains('attendance_id', 'employee_id', 'date',
                    'new_check_in', 'new_check_out')
    def _check_coherent(self):
        """Always-valid INTEGRITY checks only (a draft may still be incomplete —
        completeness is enforced at submit, see _check_ready_to_submit)."""
        for rec in self:
            if rec.attendance_id:
                att = rec.attendance_id.sudo()
                if att.employee_id != rec.employee_id:
                    raise ValidationError(_(
                        "The target punch belongs to a different employee."))
                if att.check_in and rec.date and att.check_in.date() != rec.date:
                    raise ValidationError(_(
                        "The target punch is not on the correction's day."))
            if (rec.new_check_in and rec.new_check_out
                    and rec.new_check_out < rec.new_check_in):
                raise ValidationError(_(
                    "The check-out cannot be before the check-in."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hr.attendance.correction') or _('New')
        return super().create(vals_list)
