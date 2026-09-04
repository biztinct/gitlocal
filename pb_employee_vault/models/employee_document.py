# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Employee document vault (Phase H §3).

Per-employee documents in config-driven categories, with expiry tracking and an
HR verification flag. Two safety absolutes:

  * ``verified`` is HR TESTIMONY (C18.31): verified / verified_by / verified_at
    are system-computed and writable only through the HR-gated action_verify()
    (a module-level object() sentinel routes the sanctioned write). A crafted
    call_kw write of any of them raises — readonly=True does NOT stop call_kw.
  * Documents are PII (C18.32): the record rules scope reads to the owner
    (employee) / their company (HR); this model adds no create for plain users
    this phase (HR uploads; ESS upload arrives in Phase I with its own rule).
"""

import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

_HR_GROUP = 'om_hr_payroll.group_hr_payroll_user'
_HR_CORE_GROUP = 'hr.group_hr_user'

# C18.31: verification is HR testimony, not a client-writable field. A JSON-RPC
# client can inject any context KEY but never this Python object() IDENTITY.
_VAULT_SYS_TOKEN = object()
_SYS_FIELDS = frozenset({'verified', 'verified_by', 'verified_at'})

_EXPIRY_PARAM = 'pb_employee_vault.expiry_warn_days'
_DEFAULT_EXPIRY_WARN_DAYS = 30


class PbEmployeeDocumentCategory(models.Model):
    _name = 'pb.employee.document.category'
    _description = 'Employee Document Category'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    requires_expiry = fields.Boolean(
        string='Requires Expiry Date',
        help='Documents in this category must carry an expiry date '
             '(work permits, health checks, IDs).')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class PbEmployeeDocument(models.Model):
    _name = 'pb.employee.document'
    _description = 'Employee Document'
    _order = 'expiry_date asc, id desc'

    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade')
    category_id = fields.Many2one(
        'pb.employee.document.category', string='Category', required=True)
    name = fields.Char(string='Title', required=True)
    attachment_id = fields.Many2one(
        'ir.attachment', string='File', required=True)
    issue_date = fields.Date(string='Issued')
    expiry_date = fields.Date(string='Expires', index=True)
    note = fields.Text(string='Note')

    # --- HR testimony (sentinel-guarded, C18.31) ---
    verified = fields.Boolean(string='Verified', readonly=True, copy=False)
    verified_by = fields.Many2one(
        'res.users', string='Verified By', readonly=True, copy=False)
    verified_at = fields.Datetime(string='Verified At', readonly=True, copy=False)

    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    active = fields.Boolean(default=True)

    # non-stored presentation helper for the drawer chips
    expiry_state = fields.Selection([
        ('none', 'No expiry'), ('valid', 'Valid'),
        ('soon', 'Expiring soon'), ('expired', 'Expired'),
    ], compute='_compute_expiry_state', string='Expiry')

    @api.depends('expiry_date')
    def _compute_expiry_state(self):
        today = fields.Date.today()
        soon = today + timedelta(days=90)
        for rec in self:
            if not rec.expiry_date:
                rec.expiry_state = 'none'
            elif rec.expiry_date < today:
                rec.expiry_state = 'expired'
            elif rec.expiry_date <= soon:
                rec.expiry_state = 'soon'
            else:
                rec.expiry_state = 'valid'

    # -------------------------------------------------------------- gates
    def _is_hr(self):
        u = self.env.user
        return (u.has_group(_HR_GROUP) or u.has_group(_HR_CORE_GROUP)
                or u._is_admin())

    # --------------------------------------------- verification rails (C18.31)
    def _vault_sys_allowed(self):
        return (self.env.su or self.env.user._is_admin()
                or self.env.context.get('vault_sys_write') is _VAULT_SYS_TOKEN)

    def _vault_sys_write(self, vals):
        return self.with_context(vault_sys_write=_VAULT_SYS_TOKEN).write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        if not self._vault_sys_allowed():
            for vals in vals_list:
                for f in _SYS_FIELDS.intersection(vals):
                    vals.pop(f)
        # Review I-M4: a self-served create must bind an attachment the caller
        # OWNS and that no record has claimed — probing a foreign attachment id
        # would otherwise get the victim's file destroyed when this document is
        # later deleted (the unlink cascade runs sudo).
        if not (self._vault_sys_allowed() or self._is_hr()):
            Att = self.env['ir.attachment'].sudo()
            for vals in vals_list:
                att_id = vals.get('attachment_id')
                if not att_id:
                    continue
                att = Att.browse(int(att_id)).exists()
                if (not att or att.create_uid.id != self.env.uid
                        or (att.res_model and att.res_id)):
                    raise AccessError(_(
                        "You can only attach a file you uploaded yourself."))
        return super().create(vals_list)

    def write(self, vals):
        if not self._vault_sys_allowed():
            forged = _SYS_FIELDS.intersection(vals)
            if forged:
                raise AccessError(_(
                    "Document verification is HR testimony and cannot be set "
                    "directly: %s.", ', '.join(sorted(forged))))
        # Review H-M2 (C18.31 spirit): verification testifies to a SPECIFIC
        # file on a specific employee/category. Swapping any of those on a
        # verified document silently voids the testimony — the shield must
        # never say "Verified by A" over a file A never saw.
        content_swap = {'attachment_id', 'category_id', 'employee_id'}.intersection(vals)
        voided = (self.filtered('verified')
                  if content_swap and not self._vault_sys_allowed()
                  else self.browse())
        res = super().write(vals)
        if voided:
            voided._vault_sys_write({
                'verified': False, 'verified_by': False, 'verified_at': False})
        return res

    def action_verify(self):
        """HR marks a document verified — the ONLY path that sets the flag."""
        if not self._is_hr():
            raise AccessError(_("Only HR can verify a document."))
        self._vault_sys_write({
            'verified': True, 'verified_by': self.env.uid,
            'verified_at': fields.Datetime.now()})
        return True

    def action_unverify(self):
        if not self._is_hr():
            raise AccessError(_("Only HR can revoke a document's verification."))
        self._vault_sys_write({
            'verified': False, 'verified_by': False, 'verified_at': False})
        return True

    # --------------------------------------------------------- integrity
    @api.constrains('expiry_date', 'category_id')
    def _check_expiry_required(self):
        for rec in self:
            if rec.category_id.requires_expiry and not rec.expiry_date:
                raise ValidationError(_(
                    "A '%s' document requires an expiry date.",
                    rec.category_id.name))

    def unlink(self):
        # the document owns its attachment — remove it too (safety rail 5). Use
        # sudo: the attachment may have been created by another user (HR upload).
        atts = self.mapped('attachment_id')
        res = super().unlink()
        if atts:
            atts.sudo().unlink()
        return res

    # --------------------------------------------------------- expiry cron
    @api.model
    def _expiry_warn_days(self):
        raw = self.env['ir.config_parameter'].sudo().get_param(
            _EXPIRY_PARAM, _DEFAULT_EXPIRY_WARN_DAYS)
        try:
            days = int(raw)
        except (TypeError, ValueError):
            days = _DEFAULT_EXPIRY_WARN_DAYS
        return days if days > 0 else _DEFAULT_EXPIRY_WARN_DAYS

    def _activity_summary(self):
        self.ensure_one()
        return _("Document expiring: %s", self.name)

    def _expiry_responsible(self, employee):
        """The HR user to nudge — a payroll HR officer in the employee's
        company, else any HR officer, else the admin (never dead-end).

        Members are resolved via the inverse res.users.group_ids M2M
        (res.groups.users is unreliable in Odoo 19 — [[odoo19-payroll-gotchas]])."""
        grp = self.env.ref(_HR_GROUP, raise_if_not_found=False)
        if grp:
            Users = self.env['res.users']
            same_co = Users.search([
                ('group_ids', 'in', grp.id),
                ('company_ids', 'in', employee.company_id.id)], limit=1)
            if same_co:
                return same_co
            any_hr = Users.search([('group_ids', 'in', grp.id)], limit=1)
            if any_hr:
                return any_hr
        return (self.env.ref('base.user_admin', raise_if_not_found=False)
                or self.env.user)

    @api.model
    def _cron_expiry_check(self):
        """Raise ONE HR activity per document nearing/at expiry. Idempotent: an
        existing open activity for the same (employee, document title) is not
        duplicated on the next run."""
        days = self._expiry_warn_days()
        horizon = fields.Date.today() + timedelta(days=days)
        docs = self.sudo().search([
            ('active', '=', True),
            ('expiry_date', '!=', False),
            ('expiry_date', '<=', horizon)])
        act_type = self.env.ref(
            'mail.mail_activity_data_todo', raise_if_not_found=False)
        made = 0
        Activity = self.env['mail.activity'].sudo()
        for doc in docs:
            emp = doc.employee_id
            if not emp:
                continue
            summary = doc._activity_summary()
            existing = Activity.search([
                ('res_model', '=', 'hr.employee'),
                ('res_id', '=', emp.id),
                ('summary', '=', summary)], limit=1)
            if existing:
                continue
            responsible = doc._expiry_responsible(emp)
            try:
                emp.sudo().activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo'
                    if act_type else False,
                    summary=summary,
                    note=_("The document '%s' (%s) expires on %s.",
                           doc.name, doc.category_id.name, doc.expiry_date),
                    user_id=responsible.id,
                    date_deadline=doc.expiry_date)
                made += 1
            except Exception:
                _logger.exception(
                    "pb.employee.document: expiry activity for doc %s", doc.id)
        if made:
            _logger.info("pb.employee.document: raised %s expiry activit(y/ies)",
                         made)
        return made
