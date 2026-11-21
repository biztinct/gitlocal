# -*- coding: utf-8 -*-
"""TIDY-E item 2 (owner ruling R12) — "Payroll-ready" reads the APPROVED bank
account.

`pb_people` counted a person as having bank details when the old free-text
"Account Number" box on the employee form was filled
(`pb_people/models/pb_people.py` `_roster_kpis`, `_pbf_spec`, `_roster_row`,
`get_employee_detail`). Nothing pays from that box and on rize nobody had
filled it while 194 people had an approved account — so the People list
called everyone "missing bank". Every place that asked is reached here by
`_inherit` (no edit of pb_people): the same domains, with the bank half
replaced by `hr.employee.pb_bank_on_record` (below).
"""

from odoo import api, fields, models

BANK = ('pb_bank_on_record', '=', True)
NO_BANK = ('pb_bank_on_record', '=', False)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    pb_bank_on_record = fields.Boolean(
        string='Approved bank account on record',
        compute='_compute_pb_bank_on_record', search='_search_pb_bank_on_record',
        help="An approved bank account is on record: the employee's bank account "
             "(a change still waiting for approval does not count), or the "
             "Vietnamese bank file's account.")

    @api.model
    def _pb_bank_domain(self):
        """Domain of people with an approved bank account on record.

        The same notion the payment list and the bank layouts use
        (`pb_pay_delivery/models/payment_list.py` `_pb_build_rows`: the first of
        `bank_account_ids`, written only after approval since WDGAP S6-A). The
        Vietnamese bank file's own store (`vietnam_bank_account_number`, also
        written only on approval — `pb_bank_ocr` two stores) counts as well, so
        nobody paid by that file drops out of the figure. A change still
        waiting for approval lives on its own record and is in neither store.
        """
        parts = []
        if 'bank_account_ids' in self._fields:
            parts.append([('bank_account_ids', '!=', False)])
        if 'vietnam_bank_account_number' in self._fields:
            parts.append([('vietnam_bank_account_number', 'not in', (False, ''))])
        if not parts:
            return [('id', '=', 0)]
        domain = parts[0]
        for extra in parts[1:]:
            domain = ['|'] + domain + extra
        return domain

    def _compute_pb_bank_on_record(self):
        has_accounts = 'bank_account_ids' in self._fields
        has_vn_file = 'vietnam_bank_account_number' in self._fields
        for employee in self:
            person = employee.sudo()
            employee.pb_bank_on_record = bool(
                (has_accounts and person.bank_account_ids)
                or (has_vn_file and (person.vietnam_bank_account_number or '').strip()))

    def _search_pb_bank_on_record(self, operator, value):
        if operator not in ('=', '!='):
            return NotImplemented
        positive = (operator == '=') == bool(value)
        ids = self.sudo().with_context(active_test=False)._search(self._pb_bank_domain())
        return [('id', 'in' if positive else 'not in', ids)]

    def _pb_bank_on_record_facts(self):
        """FS-9 — WHICH approved account `pb_bank_on_record` found, as facts a
        screen may show: never the whole number, only its last four digits.

        Same two stores and the same order as the helper above (and as the
        payment list, `_pb_build_rows`, and the "another person's name" flag,
        `_pb_other_name_account`): the employee's FIRST bank account, else the
        Vietnamese bank file's account. Read under sudo, for one person.

        Returns ``{'on_record', 'store' ('account' | 'vn_file' | ''), 'bank',
        'holder', 'last4', 'vn_file_last4'}`` — ``vn_file_last4`` is set only
        when the Vietnamese bank file holds a DIFFERENT number from the
        account shown (the two stores disagree; S6-A lists such people for the
        owner and changes nothing).
        """
        self.ensure_one()
        person = self.sudo()
        out = {'on_record': bool(person.pb_bank_on_record), 'store': '', 'bank': '',
               'holder': '', 'last4': '', 'vn_file_last4': ''}
        vn_number = ''
        if 'vietnam_bank_account_number' in person._fields:
            vn_number = (person.vietnam_bank_account_number or '').strip()
        account = person.bank_account_ids[:1] if 'bank_account_ids' in person._fields \
            else person.env['res.partner.bank']
        if account:
            out.update(store='account', bank=(account.bank_id.name or '').strip(),
                       holder=(account.acc_holder_name or '').strip(),
                       last4=_last4(account.acc_number))
            if vn_number and _digits(vn_number) != _digits(account.acc_number):
                out['vn_file_last4'] = _last4(vn_number)
        elif vn_number:
            out.update(store='vn_file',
                       bank=(getattr(person, 'vietnam_bank_name', '') or '').strip(),
                       holder=(getattr(person, 'vietnam_bank_account_name', '') or '').strip(),
                       last4=_last4(vn_number))
        return out


def _digits(text):
    return ''.join(ch for ch in str(text or '') if ch.isdigit())


def _last4(number):
    """The last four digits only — never the whole number. A number of four
    digits or fewer shows none of them (it would be the whole number)."""
    digits = _digits(number)
    return digits[-4:] if len(digits) > 4 else ''


def _swap(domain):
    """The same domain with the old box's test replaced by the approved one."""
    out = []
    for term in domain or []:
        if isinstance(term, (list, tuple)) and len(term) == 3 and term[0] == 'account_number':
            positive = (term[1] == '!=') == (term[2] is False or term[2] == '')
            out.append(BANK if positive else NO_BANK)
        else:
            out.append(term)
    return out


class PbPeople(models.AbstractModel):
    _inherit = 'pb.people'

    @api.model
    def _roster_kpis(self):
        res = super()._roster_kpis()
        Emp = self.env['hr.employee']
        emp_dom = res.get('emp_dom') or []
        status_dom = dict(res.get('status_dom') or {})
        if 'notready' in status_dom:
            status_dom['notready'] = _swap(status_dom['notready'])
        res['status_dom'] = status_dom
        kpis = dict(res.get('kpis') or {})
        with_bank = self._safe(lambda: Emp.search_count(emp_dom + [BANK]))
        kpis['with_bank'] = with_bank
        if 'notready' in status_dom:
            kpis['not_ready'] = self._safe(
                lambda: Emp.search_count(emp_dom + status_dom['notready']))
        headcount = kpis.get('headcount') or 0
        # TIDY-E2 (deploy report TE-D3): "Payroll-ready %" is the share that IS
        # payroll-ready (running contract AND approved bank) — the complement of
        # "Not payroll-ready" beside it. It used to be bank ÷ headcount, so a site
        # with all contracts still drafts read 99 % next to 651 not ready.
        not_ready = kpis.get('not_ready') or 0
        kpis['ready_pct'] = round(100 * max(headcount - not_ready, 0) / headcount) \
            if headcount else 0
        # TIDY-E 3b — the "Fill Country of Work" button (HR managers, only
        # while somebody has none).
        kpis['cow_empty'] = self._safe(
            lambda: Emp.search_count(emp_dom + [('payroll_country', '=', False)]))
        kpis['cow_can_fill'] = self.env.user.has_group('hr.group_hr_manager')
        res['kpis'] = kpis
        return res

    def _pbf_spec(self):
        spec = super()._pbf_spec()
        for section in spec:
            if section.get('key') not in ('ready', 'bank'):
                continue
            section['requires'] = [
                'pb_bank_on_record' if p == 'account_number' else p
                for p in (section.get('requires') or [])]
            options = []
            for option in section.get('options') or []:
                option = dict(option)
                if option.get('domain') is not None:
                    option['domain'] = _swap(option['domain'])
                options.append(option)
            section['options'] = options
        return spec

    @api.model
    def _roster_row(self, e, today, month_start, pay_signs=None):
        row = super()._roster_row(e, today, month_start, pay_signs=pay_signs)
        bank = bool(e.pb_bank_on_record)
        row['bank'] = bank
        row['ready'] = bool(e.contract_id and row.get('state') == 'open' and bank)
        return row

    @api.model
    def get_roster_data(self, status=None):
        res = super().get_roster_data(status=status)
        Emp = self.env['hr.employee']
        people = res.get('people') or []
        found = Emp.browse([p['id'] for p in people if p.get('id')])
        bank = {e.id: bool(e.pb_bank_on_record) for e in found}
        for person in people:
            has = bank.get(person.get('id'), False)
            person['bank'] = has
            person['ready'] = bool(person.get('contract_id') and person.get('state') == 'open' and has)
        return res

    @api.model
    def get_employee_detail(self, emp_id):
        res = super().get_employee_detail(emp_id)
        if isinstance(res, dict) and res.get('statutory') is not None:
            e = self.env['hr.employee'].browse(int(emp_id))
            # FS-9: the full page's bank badge names the APPROVED account's
            # bank, not the old free-text Bank box (now off the screens).
            facts = e._pb_bank_on_record_facts()
            res['statutory'] = dict(res['statutory'], bank=facts['on_record'],
                                    bank_name=facts['bank'] if facts['on_record'] else '')
        return res
