# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Profile self-service change request (Sudima Phase I §3).

An employee proposes changes to a SMALL set of personal-contact fields; the
change rides an Employee → HR approval chain; only the approved request writes
the employee master, through ONE audited writer. ESS never writes the master
directly (C18.55e) — the same doctrine as the Phase-D bank-change request, minus
the OCR (this is a clone of that shape).

Rails (C18.24/31):
  * `cur_*` snapshot fields are system-derived — writable only via the module
    `object()` sentinel (a JSON client can inject a context KEY but never this
    Python IDENTITY). `readonly=True` does NOT stop call_kw.
  * The editable field set is a CONFIG whitelist (`pb_me_portal.editable_fields`)
    — a crafted create carrying a non-whitelisted proposed field is stripped.
  * Proposed values freeze to the owner in draft, immutable once decided.
  * `_apply_to_master` writes via `.sudo()` (the fields are hr.group_hr_user-
    scoped) — `sudo()` keeps env.uid, so the Phase-H biz_audit_trail entry
    records the TRUE actor (the approving HR user).
"""

import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_HR_GROUP = 'om_hr_payroll.group_hr_payroll_user'
_HR_CORE_GROUP = 'hr.group_hr_user'
_HR_GROUPS = (_HR_GROUP, _HR_CORE_GROUP, 'om_hr_payroll.group_hr_payroll_manager',
              'hr.group_hr_manager')

_EDITABLE_PARAM = 'pb_me_portal.editable_fields'
_DEFAULT_EDITABLE = 'x_phone,x_private_email,x_address,x_emergency_contact,x_emergency_phone'

# proposed field (x_*) → hr.employee master field. Every target is a STORED
# Char on hr.employee (audits directly — C18.56), hr.group_hr_user-scoped.
_MASTER_FIELDS = {
    'x_phone': 'private_phone',
    'x_private_email': 'private_email',
    'x_address': 'private_street',
    'x_emergency_contact': 'emergency_contact',
    'x_emergency_phone': 'emergency_phone',
}
_PROPOSED_FIELDS = frozenset(_MASTER_FIELDS)

# C18.31: the snapshot is system testimony (the diff basis the approver trusts).
_SYS_TOKEN = object()
_SYS_FIELDS = frozenset({
    'name', 'cur_phone', 'cur_private_email', 'cur_address',
    'cur_emergency_contact', 'cur_emergency_phone',
})
# What the requester may set — frozen to the owner in draft, immutable once decided.
_REVIEW_FIELDS = frozenset(_PROPOSED_FIELDS | {'employee_id', 'note'})


class PbProfileChangeRequest(models.Model):
    _name = 'pb.profile.change.request'
    _description = 'Profile Change Request'
    _inherit = ['mail.thread', 'biz.approval.chain.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, tracking=True, index=True)
    note = fields.Text(string='Note to HR')

    # --- proposed (the employee edits these) ---
    x_phone = fields.Char(string='Private Phone')
    x_private_email = fields.Char(string='Private Email')
    x_address = fields.Char(string='Address')
    x_emergency_contact = fields.Char(string='Emergency Contact')
    x_emergency_phone = fields.Char(string='Emergency Phone')

    # --- snapshot of the master at submit (the diff basis; sentinel-guarded) ---
    cur_phone = fields.Char(string='Current Private Phone', readonly=True)
    cur_private_email = fields.Char(string='Current Private Email', readonly=True)
    cur_address = fields.Char(string='Current Address', readonly=True)
    cur_emergency_contact = fields.Char(string='Current Emergency Contact', readonly=True)
    cur_emergency_phone = fields.Char(string='Current Emergency Phone', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('hr_review', 'HR Review'),
        ('approved', 'Approved'),
        ('refused', 'Refused'),
    ], string='Status', default='draft', tracking=True, index=True, copy=False)

    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company)

    approval_widget_json = fields.Char(compute='_compute_approval_widget')
    can_submit = fields.Boolean(compute='_compute_can')
    can_hr_approve = fields.Boolean(compute='_compute_can')
    can_refuse = fields.Boolean(compute='_compute_can')

    # ------- the chain (Employee → HR → master) -------
    _approval_transitions = {
        ('draft', 'hr_review'): None,          # submit — owner / HR
        ('hr_review', 'approved'): _HR_GROUP,  # HR tier
    }

    # --------------------------------------------------------------- config
    @api.model
    def _editable_fields(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            _EDITABLE_PARAM, _DEFAULT_EDITABLE)
        allowed = {c.strip() for c in (raw or '').split(',') if c.strip()}
        # only ever within the shipped column set (adding a field is config,
        # but never outside what exists)
        return allowed & _PROPOSED_FIELDS

    # ------------------------------------------------------------- computes
    @api.depends('state')
    def _compute_approval_widget(self):
        steps = [
            {'state': 'draft', 'label': _('Request'), 'group_label': _('You')},
            {'state': 'hr_review', 'label': _('HR Review'), 'group_label': _('HR')},
            {'state': 'approved', 'label': _('Applied'), 'group_label': _('System')},
        ]
        for rec in self:
            rec.approval_widget_json = rec._approval_widget_payload(steps) if rec.id else False

    @api.depends('state')
    def _compute_can(self):
        for rec in self:
            s = rec.state
            rec.can_submit = s == 'draft' and rec._approval_can('draft', 'hr_review')
            rec.can_hr_approve = s == 'hr_review' and rec._approval_can('hr_review', 'approved')
            rec.can_refuse = s == 'hr_review' and rec._approval_can_refuse(s)

    # --------------------------------------------------------- authorization
    def _user_in_any(self, xmlids):
        for x in xmlids:
            try:
                if self.env.user.has_group(x):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    def _is_hr(self):
        return self.env.user._is_admin() or self._user_in_any(_HR_GROUPS)

    def _approval_can(self, from_state, to_state):
        """Owner may submit their OWN draft; HR advances HR review."""
        self.ensure_one()
        if self.env.su or self.env.user._is_admin():
            return True
        pair = (from_state, to_state)
        if pair == ('draft', 'hr_review'):
            owner = (self.sudo().employee_id.user_id
                     and self.sudo().employee_id.user_id.id == self.env.uid)
            return bool(owner) or self._is_hr()
        if pair == ('hr_review', 'approved'):
            return self._is_hr()
        return super()._approval_can(from_state, to_state)

    # --------------------------------------------- forgery rails (C18.24/31)
    def _sys_allowed(self):
        return (self.env.su or self.env.user._is_admin()
                or self.env.context.get('profile_sys_write') is _SYS_TOKEN)

    def _sys_write(self, vals):
        return self.with_context(profile_sys_write=_SYS_TOKEN).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        sys_ok = self._sys_allowed()
        editable = self._editable_fields()
        for vals in vals_list:
            if not sys_ok:
                for f in _SYS_FIELDS.intersection(vals):
                    vals.pop(f)
                # strip any proposed field not in the config whitelist
                for f in (_PROPOSED_FIELDS - editable):
                    vals.pop(f, None)
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'pb.profile.change.request') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        if not self._sys_allowed():
            forged = _SYS_FIELDS.intersection(vals)
            if forged:
                raise AccessError(_(
                    "The current-value snapshot of a profile change request is "
                    "system-computed and cannot be edited: %s.",
                    ', '.join(sorted(forged))))
            # strip proposed fields not in the whitelist (defense in depth)
            editable = self._editable_fields()
            for f in (_PROPOSED_FIELDS - editable):
                vals.pop(f, None)
            touched = _REVIEW_FIELDS.intersection(vals)
            if touched:
                is_hr = self._is_hr()
                for rec in self:
                    if rec.state in ('approved', 'refused'):
                        raise AccessError(_(
                            "A decided profile change request is immutable."))
                    if rec.state != 'draft' and not is_hr:
                        raise AccessError(_(
                            "This request is under review — it can no longer "
                            "be edited."))
        return super().write(vals)

    # --------------------------------------------------------- lifecycle
    def _before_approval_transition(self, to_state):
        if to_state == 'hr_review':
            rec = self.sudo()
            rec._snapshot_current()
            if not rec._has_change():
                raise UserError(_(
                    "None of the proposed values differ from your current "
                    "profile — nothing to submit."))

    def _after_approval_transition(self, to_state):
        if to_state == 'approved':
            self._apply_to_master()

    def action_submit(self):
        self.ensure_one()
        return self._advance_state('hr_review')

    def action_hr_approve(self):
        self.ensure_one()
        return self._advance_state('approved')

    # ---------------------------------------------------- diff / snapshot
    def _snapshot_current(self):
        self.ensure_one()
        emp = self.employee_id.sudo()
        self._sys_write({
            'cur_phone': emp.private_phone or '',
            'cur_private_email': emp.private_email or '',
            'cur_address': emp.private_street or '',
            'cur_emergency_contact': emp.emergency_contact or '',
            'cur_emergency_phone': emp.emergency_phone or '',
        })

    def _cur_field(self, x_field):
        return {'x_phone': 'cur_phone', 'x_private_email': 'cur_private_email',
                'x_address': 'cur_address', 'x_emergency_contact': 'cur_emergency_contact',
                'x_emergency_phone': 'cur_emergency_phone'}[x_field]

    def _has_change(self):
        """True if any WHITELISTED proposed value differs from the master."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        for x_field, master in _MASTER_FIELDS.items():
            if x_field not in self._editable_fields():
                continue
            proposed = (self[x_field] or '').strip()
            if not proposed:
                continue  # blank = "leave unchanged"
            if proposed != (emp[master] or ''):
                return True
        return False

    def _diff(self, labels=None):
        """[{field,label,current,proposed,changed}] for the portal preview."""
        self.ensure_one()
        labels = labels or {
            'x_phone': _('Private Phone'),
            'x_private_email': _('Private Email'),
            'x_address': _('Address'),
            'x_emergency_contact': _('Emergency Contact'),
            'x_emergency_phone': _('Emergency Phone'),
        }
        editable = self._editable_fields()
        out = []
        for x_field in _MASTER_FIELDS:
            if x_field not in editable:
                continue
            cur = self[self._cur_field(x_field)] or ''
            proposed = self[x_field] or ''
            out.append({
                'field': x_field, 'label': labels[x_field],
                'current': cur, 'proposed': proposed,
                'changed': bool(proposed.strip()) and proposed != cur,
            })
        return out

    # --------------------------------------------------- the master write
    def _apply_to_master(self):
        """The ONLY path that writes the employee master. sudo() (the target
        fields are HR-scoped) keeps env.uid, so the Phase-H audit trail logs
        the approving HR user as the true actor. Blank proposed = unchanged."""
        self.ensure_one()
        emp = self.employee_id.sudo()
        editable = self._editable_fields()
        new = {}
        for x_field, master in _MASTER_FIELDS.items():
            if x_field not in editable:
                continue
            proposed = (self[x_field] or '').strip()
            if proposed and proposed != (emp[master] or ''):
                new[master] = proposed
        if new:
            emp.write(new)
        self.message_post(body=_("Profile updated from this request."))
        return bool(new)
