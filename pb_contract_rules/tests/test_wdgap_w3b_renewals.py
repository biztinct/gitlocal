# -*- coding: utf-8 -*-
"""WDGAP W3-B (owner rulings RN1, RN2) — renewals. Numbered as in the W3-B
report (§3, RN rows):

N1  Contracts "Renew": the form opens with the old contract's Vietnam kind
    (fixed-term) and the kinds offered never include a trial; the new contract
    carries it; HR changing it on the form wins.
N2  a trial is never carried: an old contract on the trial kind renews as the
    field's own default (open-ended), a trial asked for on the form is not
    written, and the separate Vietnam payroll trial treatment is never copied.
N3  contract decisions board: an extension carries the kind; "Make it
    permanent" still makes an open-ended contract.
N4  the Renew button LINKS the new contract to the old one (from now on); a
    plain new contract and another person's contract get no link.
N5  the fixed-term count now sees a Renew-button renewal (even after a break
    longer than the rule's): count 2, the next extension is past the
    Vietnam rule.
N6  the READ-ONLY check lists an old unlinked renewal (not a linked one),
    says whether the dates already join it, how many people would show the
    red warning if linked — and writes nothing; the tool runs it read-only.
"""
import os
import re
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_people_advanced.models.newhire_approval import (
    NEWHIRE_PROCESS_KEY, NEWHIRE_WRITE,
)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextmanager
def spy_writes():
    seen = []
    real = Cursor.execute

    def execute(self, query, params=None, log_exceptions=True):
        text = str(query.code if hasattr(query, 'code') else query).lower()
        if re.match(r'\s*(insert|update|delete)\b', text):
            seen.append(text[:120])
        return real(self, query, params, log_exceptions)

    with patch.object(Cursor, 'execute', execute):
        yield seen


@tagged('post_install', '-at_install', 'wdgap_w3b')
class TestW3bRenewals(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vn = cls.env.ref('base.vn')
        cls.company = cls.env['res.company'].create(
            {'name': 'W3B Renewals VN', 'country_id': cls.vn.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id],
            tracking_disable=True, mail_notrack=True))
        # the decision board's renewal goes through the new-hire route
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
            cls.company, NEWHIRE_PROCESS_KEY)
        cls.Rule = cls.env['pb.contract.rule']
        cls.Wizard = cls.env['pb.people.contract.wizard'].with_context(
            **{NEWHIRE_WRITE: True})
        cls.has_kind = 'vietnam_contract_type' in cls.env['hr.contract']._fields
        cls._seq = 0

    def _emp(self):
        type(self)._seq += 1
        return self.env['hr.employee'].create({
            'name': 'W3B Renewal %s' % self._seq, 'company_id': self.company.id,
            'address_id': self.company.partner_id.id})

    def _contract(self, emp, start, end, state='open', **kw):
        type(self)._seq += 1
        vals = {'name': 'W3B c %s' % self._seq, 'employee_id': emp.id,
                'wage': 9_000_000.0, 'date_start': start, 'date_end': end,
                'state': state, 'company_id': self.company.id}
        vals.update(kw)
        return self.env['hr.contract'].create(vals)

    def _renew(self, old, start, end=None, **form):
        d = self.Wizard.get_defaults(old.employee_id.id, old.id)
        vals = {'employee_id': old.employee_id.id, 'wage': old.wage,
                'date_start': str(start),
                'struct_id': d['prefill'].get('struct_id') or d.get('default_struct'),
                'renew_from': old.id}
        if end:
            vals['date_end'] = str(end)
        vals.update(form)
        res = self.Wizard.create_contract(vals)
        self.assertFalse(res.get('error'), res)
        return self.env['hr.contract'].browse(res['contract_id']), d

    def _need_kind(self):
        if not self.has_kind:
            self.skipTest('the Vietnam contract kind is not installed here')

    # ================================================================ N1
    def test_n1_renew_carries_the_kind_and_hr_can_change_it(self):
        self._need_kind()
        emp = self._emp()
        old = self._contract(emp, date(2025, 1, 1), date(2025, 12, 31),
                             vietnam_contract_type='definite')
        new, d = self._renew(old, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(d['prefill']['vn_kind'], 'definite')
        self.assertTrue(d['prefill']['vn_kind_show'], "a Vietnam company shows the box")
        self.assertEqual([k['key'] for k in d['vn_kinds']],
                         ['definite', 'indefinite', 'seasonal'], "never a trial")
        self.assertEqual(new.vietnam_contract_type, 'definite')
        # HR picks another kind on the form
        emp2 = self._emp()
        old2 = self._contract(emp2, date(2025, 1, 1), date(2025, 12, 31),
                              vietnam_contract_type='definite')
        new2, _d = self._renew(old2, date(2026, 1, 1), date(2026, 12, 31),
                               vn_kind='seasonal')
        self.assertEqual(new2.vietnam_contract_type, 'seasonal')
        self.assertEqual(old2.vietnam_contract_type, 'definite', "the old one is untouched")

    # ================================================================ N2
    def test_n2_a_trial_is_never_carried(self):
        self._need_kind()
        emp = self._emp()
        vals = {'vietnam_contract_type': 'probation'}
        if 'pb_payroll_contract_type' in self.env['hr.contract']._fields:
            vals['pb_payroll_contract_type'] = 'probation'
        trial = self._contract(emp, date(2025, 1, 1), date(2025, 2, 28), **vals)
        new, d = self._renew(trial, date(2025, 3, 1), date(2026, 2, 28))
        self.assertEqual(d['prefill']['vn_kind'], '')
        self.assertEqual(new.vietnam_contract_type, 'indefinite', "the field's own default")
        if 'pb_payroll_contract_type' in new._fields:
            self.assertFalse(new.pb_payroll_contract_type, "the trial treatment is never copied")
        # a trial typed on the form is not written either
        emp2 = self._emp()
        old2 = self._contract(emp2, date(2025, 1, 1), date(2025, 12, 31),
                              vietnam_contract_type='definite')
        new2, _d = self._renew(old2, date(2026, 1, 1), date(2026, 12, 31),
                               vn_kind='probation')
        self.assertNotEqual(new2.vietnam_contract_type, 'probation')

    # ================================================================ N3
    def test_n3_board_extension_and_make_it_permanent(self):
        self._need_kind()
        emp = self._emp()
        old = self._contract(emp, date(2025, 1, 1), date(2025, 12, 31),
                             vietnam_contract_type='definite')
        review = self.env['pb.contract.review'].create(
            {'contract_id': old.id, 'company_id': self.company.id})
        ext = review._build_new_contract(date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(ext.vietnam_contract_type, 'definite', "an extension carries it")
        self.assertEqual(ext.pb_renewed_from_id, old)
        emp2 = self._emp()
        old2 = self._contract(emp2, date(2025, 1, 1), date(2025, 12, 31),
                              vietnam_contract_type='definite')
        review2 = self.env['pb.contract.review'].create(
            {'contract_id': old2.id, 'company_id': self.company.id})
        perm = review2._build_new_contract(date(2026, 1, 1), False)
        self.assertFalse(perm.date_end)
        self.assertEqual(perm.vietnam_contract_type, 'indefinite',
                         "Make it permanent stays open-ended")

    # ================================================================ N4
    def test_n4_the_renew_button_links_from_now_on(self):
        emp = self._emp()
        old = self._contract(emp, date(2025, 1, 1), date(2025, 12, 31))
        new, _d = self._renew(old, date(2026, 1, 1), date(2026, 12, 31))
        self.assertEqual(new.pb_renewed_from_id, old)
        self.assertIn(new, old.pb_renewal_ids)
        # a plain new contract: no link
        res = self.Wizard.create_contract({
            'employee_id': self._emp().id, 'wage': 1.0, 'date_start': '2026-01-01'})
        self.assertFalse(self.env['hr.contract'].browse(res['contract_id']).pb_renewed_from_id)
        # somebody else's contract never becomes the link
        other = self._emp()
        res = self.Wizard.create_contract({
            'employee_id': other.id, 'wage': 1.0, 'date_start': '2026-01-01',
            'renew_from': old.id})
        self.assertFalse(self.env['hr.contract'].browse(res['contract_id']).pb_renewed_from_id)

    # ================================================================ N5
    def test_n5_fixed_term_count_sees_a_button_renewal(self):
        emp = self._emp()
        old = self._contract(emp, date(2024, 1, 1), date(2024, 12, 31), state='close')
        # renewed with the button after a 59-day break (longer than the rule's 30)
        new, _d = self._renew(old, date(2025, 3, 1), date(2026, 2, 28))
        info = self.Rule.chain(new)
        self.assertEqual(info['in_system'], 2, "the link joins them")
        check = self.Rule.check_extension(new, 12)
        self.assertTrue(check['over'])
        self.assertEqual(check['count_after'], 3)
        # the same dates WITHOUT a link (how such a renewal looked before): 1
        emp2 = self._emp()
        self._contract(emp2, date(2024, 1, 1), date(2024, 12, 31), state='close')
        loose = self._contract(emp2, date(2025, 3, 1), date(2026, 2, 28))
        self.assertEqual(self.Rule.chain(loose)['in_system'], 1)

    # ================================================================ N6
    def test_n6_read_only_check(self):
        # an old unlinked renewal after a 59-day break (beyond the rule's gap)
        emp = self._emp()
        a1 = self._contract(emp, date(2024, 1, 1), date(2024, 12, 31), state='close')
        a2 = self._contract(emp, date(2025, 3, 1), date(2026, 2, 28))
        # an old unlinked renewal the next day (the dates already join it)
        emp_b = self._emp()
        b1 = self._contract(emp_b, date(2025, 1, 1), date(2025, 6, 30), state='close')
        b2 = self._contract(emp_b, date(2025, 7, 1), date(2026, 6, 30))
        # a linked renewal is not listed
        emp_c = self._emp()
        c1 = self._contract(emp_c, date(2025, 1, 1), date(2025, 6, 30), state='close')
        self._contract(emp_c, date(2025, 7, 1), date(2026, 6, 30), pb_renewed_from_id=c1.id)
        self.env.flush_all()
        with spy_writes() as seen:
            report = self.Rule.renew_link_report(window_days=90, months=12)
        self.assertEqual(seen, [], "the check writes nothing")
        mine = [r for r in report['pairs'] if r['employee_id'] in (emp | emp_b | emp_c).ids]
        by_emp = {r['employee_id']: r for r in mine}
        self.assertEqual(set(by_emp), {emp.id, emp_b.id})
        self.assertEqual(by_emp[emp.id]['gap_days'], 59)
        self.assertFalse(by_emp[emp.id]['counted_by_dates'])
        self.assertEqual(by_emp[emp_b.id]['gap_days'], 0)
        self.assertTrue(by_emp[emp_b.id]['counted_by_dates'])
        self.assertIn(emp.name, report['newly_warned'],
                      "linked, the 59-day renewal would be number 3 on the next extension")
        self.assertNotIn(emp_b.name, report['newly_warned'],
                         "the dates already join it, so the warning is already there")
        self.assertGreaterEqual(report['warning_if_linked'], report['warning_now'])
        # nothing was linked by the check
        self.assertFalse(a2.pb_renewed_from_id)
        self.assertFalse(b2.pb_renewed_from_id)
        self.assertTrue(a1 and b1)
        # the tool runs it in a read-only transaction and rolls back
        with open(os.path.join(HERE, 'tools', 'renew_button_links_check.py')) as handle:
            tool = handle.read()
        self.assertIn('SET TRANSACTION READ ONLY', tool)
        self.assertIn('renew_link_report', tool)
        self.assertIn('rollback', tool)
