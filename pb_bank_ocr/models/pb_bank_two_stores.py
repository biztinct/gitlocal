# -*- coding: utf-8 -*-
"""WDGAP S6-A — the two places a person's bank details are kept, kept in step.

WHAT WAS TRUE BEFORE (FACTS §0.1). The pay bank file and the payslip PDF
password read the four `vietnam_bank_*` fields on the employee
(`pb_pay_delivery/models/bank_export_wizard.py` `_row_sources`,
`payslip_delivery.py` `_resolve_password`). The bank-document check wrote
those four fields only. The Updates sheet and the Records screen wrote the
employee's bank ACCOUNTS (`res.partner.bank` through `bank_account_ids`)
only. Nothing copied one to the other, so a bank change approved on the
Updates sheet never reached the bank file — pay went to the old account.

WHAT IS TRUE NOW. An approved change from any of the three doors lands in
both places, and the account it wrote is the one every reader takes first:
  * the bank-document check (staff screen or My Payobook) — `_apply_to_master`
    writes the four fields, then `_pb_mirror_to_accounts` below;
  * the Updates sheet and the Records screen — `pb.records.desk._write_bank`
    writes the account, then the four fields (pb_records).

NOTHING EXISTING IS REWRITTEN. People whose two places already disagree are
listed by `hr.employee.pb_bank_store_check()` — READ-ONLY, for the owner to
decide — and nothing else touches them.
"""

import logging

from odoo import _, api, models

from odoo.addons.pb_hr_payroll_formula.models.bank_account_util import (
    acc_numbers_match, sanitize_acc_number, sanitize_bank_text,
)

from .vn_bank_dictionary import fold

_logger = logging.getLogger(__name__)


def _digits(text):
    return ''.join(ch for ch in (text or '') if ch.isdigit())


def _mask(text):
    """'•••• 6789' — never a whole account number in a report."""
    d = _digits(text) or (text or '')
    return ('•••• ' + d[-4:]) if len(d) > 4 else d


class PbBankChangeRequestTwoStores(models.Model):
    _inherit = 'pb.bank.change.request'

    # ------------------------------------------------- the account mirror
    @api.model
    def _pb_res_bank(self, bank_name, bic=None):
        """A `res.bank` for the name (or BIC), created if genuinely new — the
        same rule the pay data import uses (`_resolve_bank`)."""
        Bank = self.env['res.bank'].sudo()
        bank_name = sanitize_bank_text(bank_name) or ''
        bic = sanitize_bank_text(bic) or ''
        if bank_name:
            found = Bank.search([('name', '=ilike', bank_name)], limit=1)
            if found:
                return found
        if bic:
            found = Bank.search([('bic', '=ilike', bic)], limit=1)
            if found:
                return found
        if not bank_name and not bic:
            return Bank.browse()
        vals = {'name': bank_name or bic}
        if bic:
            vals['bic'] = bic
        return Bank.create(vals)

    def _pb_mirror_to_accounts(self, emp, new):
        """Make the employee's bank accounts say what the four fields now say.

        The account with this number is found (or made) on the employee's
        contact, linked to the employee, and put FIRST, so the Updates sheet,
        the Records screen and anything reading "the employee's account"
        reads this one. Other accounts are left where they are: an import
        never displaces an account, and neither does this.
        """
        self.ensure_one()
        emp = emp.sudo()
        if 'bank_account_ids' not in emp._fields:
            return False
        number, damaged = sanitize_acc_number(
            new.get('vietnam_bank_account_number'))
        if damaged or not number:
            return False
        partner = emp.work_contact_id
        if not partner:
            partner = self.env['res.partner'].sudo().create({
                'name': emp.name or _("Employee"),
                'company_id': emp.company_id.id or False,
                'type': 'private',
                'email': emp.work_email or False,
            })
            emp.work_contact_id = partner.id
        PartnerBank = self.env['res.partner.bank'].sudo().with_context(
            active_test=False)
        existing = PartnerBank.search([('partner_id', '=', partner.id)])
        account = existing.filtered(
            lambda a: acc_numbers_match(a.acc_number, number))[:1]
        bank = self._pb_res_bank(new.get('vietnam_bank_name'),
                                 self.x_swift or None)
        holder = sanitize_bank_text(new.get('vietnam_bank_account_name')) or ''
        if account:
            updates = {}
            if bank and account.bank_id != bank:
                updates['bank_id'] = bank.id
            if holder and account.acc_holder_name != holder:
                updates['acc_holder_name'] = holder
            if 'active' in account._fields and not account.active:
                updates['active'] = True
            if updates:
                account.write(updates)
        else:
            vals = {'acc_number': number, 'partner_id': partner.id}
            if bank:
                vals['bank_id'] = bank.id
            if holder:
                vals['acc_holder_name'] = holder
            if 'company_id' in PartnerBank._fields:
                vals['company_id'] = (emp.company_id or self.env.company).id
            account = PartnerBank.create(vals)
        put_first(emp, account)
        return account

    def _pb_duplicates_in_accounts(self, digits, want_bank):
        """Other employees of THIS company holding the same number as one of
        their bank accounts (same bank, or no bank recorded)."""
        self.ensure_one()
        Emp = self.env['hr.employee'].sudo()
        if not digits or 'bank_account_ids' not in Emp._fields:
            return Emp.browse()
        PartnerBank = self.env['res.partner.bank'].sudo()
        accounts = PartnerBank.search([('sanitized_acc_number', 'ilike', digits)])
        accounts = accounts.filtered(lambda a: _digits(a.acc_number) == digits)
        if not accounts:
            return Emp.browse()
        out = Emp.browse()
        for emp in Emp.search([('bank_account_ids', 'in', accounts.ids),
                               ('id', '!=', self.employee_id.id),
                               ('company_id', '=', self.company_id.id)]):
            for acc in emp.bank_account_ids & accounts:
                name = acc.bank_id.name or ''
                if want_bank and name and want_bank not in fold(name):
                    continue
                out |= emp
                break
        return out


def put_first(emp, account):
    """Link `account` to the employee and make it the one read first.

    `res.partner.bank` is ordered by (sequence, id), and every reader in this
    product takes `bank_account_ids[:1]`. Only this account's sequence moves;
    nothing else of the other accounts changes.
    """
    emp = emp.sudo()
    if account.id not in emp.bank_account_ids.ids:
        emp.bank_account_ids = [(4, account.id)]
    others = emp.bank_account_ids - account
    if others:
        low = min(others.mapped('sequence') or [10])
        if account.sequence >= low or emp.bank_account_ids[:1] != account:
            account.sudo().write({'sequence': low - 1})
    return account


class HrEmployeeBankStores(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def pb_bank_store_check(self, company_ids=None, limit=0):
        """READ-ONLY. Employees whose two bank stores disagree.

        For the deploy agent to run per database (`env['hr.employee']
        .pb_bank_store_check()` in a shell) BEFORE go-live, and for the owner
        to decide what to do with each person. Writes nothing. Account
        numbers are masked to their last four digits.

        Returns ``{'checked': n, 'counts': {...}, 'rows': [...]}`` where each
        row is ``{'employee_id', 'name', 'company', 'status', 'bank_file',
        'accounts', 'first_account', 'in_accounts'}`` and status is one of:

        * ``accounts_only``  — the bank file has no account number, but the
          employee has a bank account: this person is LEFT OUT of the bank
          file today ("invalid account");
        * ``bank_file_only`` — the bank file has a number, the employee has
          no bank account (the Updates sheet shows nothing);
        * ``different``      — both have one and the first account is not the
          bank file's number (``in_accounts`` says whether the bank file's
          number is one of the other accounts).
        """
        Emp = self.sudo().with_context(active_test=False)
        if 'vietnam_bank_account_number' not in Emp._fields \
                or 'bank_account_ids' not in Emp._fields:
            return {'checked': 0, 'counts': {}, 'rows': [],
                    'note': 'one of the two stores is not installed'}
        domain = [('active', 'in', (True, False))]
        if company_ids:
            domain.append(('company_id', 'in', list(company_ids)))
        employees = Emp.search(domain, order='company_id, name, id')
        counts = {'same': 0, 'neither': 0, 'accounts_only': 0,
                  'bank_file_only': 0, 'different': 0}
        rows = []
        for emp in employees:
            file_no = _digits(emp.vietnam_bank_account_number)
            accounts = emp.bank_account_ids
            first = _digits(accounts[:1].acc_number) if accounts else ''
            if not file_no and not accounts:
                counts['neither'] += 1
                continue
            if file_no and first == file_no:
                counts['same'] += 1
                continue
            if not file_no:
                status = 'accounts_only'
            elif not accounts:
                status = 'bank_file_only'
            else:
                status = 'different'
            counts[status] += 1
            rows.append({
                'employee_id': emp.id,
                'name': emp.name or '',
                'active': emp.active,
                'company': emp.company_id.name or '',
                'status': status,
                'bank_file': _mask(emp.vietnam_bank_account_number),
                'first_account': _mask(accounts[:1].acc_number) if accounts else '',
                'accounts': len(accounts),
                'in_accounts': bool(file_no) and any(
                    _digits(a.acc_number) == file_no for a in accounts),
            })
            if limit and len(rows) >= limit:
                break
        return {'checked': len(employees), 'counts': counts, 'rows': rows}
