# -*- coding: utf-8 -*-
"""WDGAP S2-C ruling BL4 — accounts in another person's name.

1. A COMPANY SETTING (Settings › Payroll › Bank layouts): an account whose
   holder is another person's name is either left out of a bank-layout file
   ("Leave out of the bank file", the default = ruling BL1) or paid by it
   ("Pay by file": in the file, still flagged on the payment list and counted
   apart on Pay & deliver and for the approver). It applies to the
   payment-list bank layouts (ID / IN / SG and copies) ONLY — never to the
   Vietnamese bank file nor to the general payment list. Each change is one
   trail line (who, when, old → new). A file already prepared keeps its bytes:
   the setting is read when a file is prepared, never afterwards.

2. A FLAG ON THE EMPLOYEE for HR: "This bank account is in another person's
   name: <holder>", with "Mark as seen" (who and when kept, one trail line, no
   account number). The SAME name test as the payment list
   (`pb.payment.list._pb_name_band` → 'other'), on the APPROVED account only
   (`bank_account_ids[:1]`; a change waiting for approval is not judged). The
   flag returns when the account, its number or its holder name changes —
   the "seen" stamp is a hash of those three, never the number itself.
   Marking seen changes nothing about payment: the company setting alone
   decides. Computed when read — nothing is written to any employee at install.
"""

import hashlib

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

#: who may see the flag and mark it seen: HR and the payroll team
FLAG_GROUPS = ('hr.group_hr_user', 'om_hr_payroll.group_hr_payroll_user')
FLAG_GROUPS_ATTR = ','.join(FLAG_GROUPS)
POLICY = [('leave_out', 'Leave out of the bank file'),
          ('pay', 'Pay by file')]


def _alnum(text):
    return ''.join(ch for ch in str(text or '') if ch.isalnum()).upper()


class ResCompanyOtherName(models.Model):
    _inherit = 'res.company'

    pb_other_name_policy = fields.Selection(
        POLICY, string="Accounts in another person's name",
        default='leave_out',
        help="For the bank layouts of the payment list (not the Vietnamese bank "
             "file): leave such accounts out of the bank file, or pay them by "
             "file. Either way the payment list flags them.")


class PbBankLayoutStudioOtherName(models.AbstractModel):
    _inherit = 'pb.bank.layout.studio'

    @api.model
    def _policy_payload(self):
        company = self.env.company
        labels = dict(self.env['res.company']._fields['pb_other_name_policy']
                      ._description_selection(self.env))
        return {
            'value': company.sudo().pb_other_name_policy or 'leave_out',
            'company': company.name,
            'choices': [{'key': k, 'label': labels.get(k, k)} for k, _l in POLICY],
        }

    @api.model
    def get_board(self):
        board = super().get_board()
        board['other_name'] = self._policy_payload()
        return board

    @api.model
    def set_other_name_policy(self, value):
        """The company setting — payroll manager only; one trail line."""
        self._require()
        if value not in dict(POLICY):
            raise UserError(_("Choose how accounts in another person's name are paid."))
        company = self.env.company.sudo()
        old = company.pb_other_name_policy or 'leave_out'
        if old != value:
            labels = dict(company._fields['pb_other_name_policy']
                          ._description_selection(self.env))
            company.write({'pb_other_name_policy': value})
            self.env['pb.money.approval.mixin'].audit(
                company, 'pb_other_name_policy',
                _("Accounts in another person's name"),
                labels.get(old, old), labels.get(value, value))
        return self._policy_payload()


class HrEmployeeOtherName(models.Model):
    _inherit = 'hr.employee'

    pb_other_name_seen_key = fields.Char(groups=FLAG_GROUPS_ATTR, copy=False)
    pb_other_name_seen_by = fields.Many2one(
        'res.users', string='Marked as seen by', groups=FLAG_GROUPS_ATTR,
        copy=False, readonly=True)
    pb_other_name_seen_on = fields.Datetime(
        string='Marked as seen on', groups=FLAG_GROUPS_ATTR, copy=False,
        readonly=True)
    pb_other_name_show = fields.Boolean(
        compute='_compute_pb_other_name', groups=FLAG_GROUPS_ATTR)
    pb_other_name_holder = fields.Char(
        string='Account holder', compute='_compute_pb_other_name',
        groups=FLAG_GROUPS_ATTR)

    # ------------------------------------------------------------ reading
    def _pb_other_name_account(self):
        """The APPROVED account (the one every reader pays), under sudo."""
        self.ensure_one()
        emp = self.sudo()
        return emp.bank_account_ids[:1] if 'bank_account_ids' in emp._fields \
            else emp.env['res.partner.bank']

    @staticmethod
    def _pb_other_name_key(account):
        holder = (account.acc_holder_name or '').strip().lower()
        raw = '%s|%s|%s' % (account.id, _alnum(account.acc_number), holder)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _pb_other_name_facts(self):
        """(show, holder, key) — the payment list's own name test."""
        self.ensure_one()
        account = self._pb_other_name_account()
        holder = (account.acc_holder_name or '').strip() if account else ''
        if not account or not (account.acc_number or '').strip() or not holder:
            return False, '', ''
        band = self.env['pb.payment.list']._pb_name_band(holder, self.sudo().name or '')
        if band != 'other':
            return False, '', ''
        key = self._pb_other_name_key(account)
        if self.sudo().pb_other_name_seen_key == key:
            return False, holder, key
        return True, holder, key

    def _compute_pb_other_name(self):
        for emp in self:
            show, holder, _key = emp._pb_other_name_facts() if emp.id else (False, '', '')
            emp.pb_other_name_show = show
            emp.pb_other_name_holder = holder if show else ''

    @api.model
    def _pb_other_name_gate(self):
        user = self.env.user
        if user._is_admin() or any(user.has_group(g) for g in FLAG_GROUPS):
            return
        raise AccessError(_("Only HR and the payroll team see this."))

    @api.model
    def pb_other_name_state(self, employee_id):
        """For the side panel chip: shown or not, the holder's name, who
        marked it seen. Never the account number."""
        self._pb_other_name_gate()
        emp = self.browse(int(employee_id or 0)).exists()
        if not emp:
            return {'show': False}
        emp.check_access('read')
        show, holder, _key = emp._pb_other_name_facts()
        sudo = emp.sudo()
        return {
            'show': show,
            'holder': holder if show else '',
            'seen_by': sudo.pb_other_name_seen_by.name or '',
            'seen_on': fields.Datetime.to_string(sudo.pb_other_name_seen_on) or '',
        }

    # ------------------------------------------------------------ marking
    def action_pb_other_name_seen(self):
        """Hide the notice for THIS account and holder; who and when kept.
        Changes nothing about payment (the company setting decides)."""
        self._pb_other_name_gate()
        self.check_access('read')
        for emp in self:
            show, _holder, key = emp._pb_other_name_facts()
            if not key:
                continue
            emp.sudo().write({'pb_other_name_seen_key': key,
                              'pb_other_name_seen_by': self.env.uid,
                              'pb_other_name_seen_on': fields.Datetime.now()})
            self.env['pb.money.approval.mixin'].audit(
                emp, 'pb_other_name_seen',
                _("Bank account in another person's name"),
                '', _("Marked as seen by %s. Payment is not changed by this.", self.env.user.name))
        return True

    @api.model
    def pb_other_name_mark_seen(self, employee_id):
        emp = self.browse(int(employee_id or 0)).exists()
        if not emp:
            raise UserError(_("That employee no longer exists."))
        emp.action_pb_other_name_seen()
        return self.pb_other_name_state(emp.id)
