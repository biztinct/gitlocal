# -*- coding: utf-8 -*-
"""WDGAP S8-B — fixed-term contract rules (`pb_contract_rules`).

CR1  the two starting rows, editable, numbers never below zero.
CR2  counting in a row: renewal link, a short break, a long break, a
     permanent contract, a trial agreement, earlier contracts typed in.
CR3  Vietnam: a 3rd fixed-term contract → red warning on "Extend", never a
     block; "Make it permanent" has no warning.
CR4  Indonesia: more than 60 months in a row → warning; within → none.
CR5  asking for the extension past the rule: allowed, reason still required,
     written down; the sign-off route gets the fact and the detail says so.
CR6  the decision drawer carries "Fixed-term contract N in a row".
CR7  Updates catalogue gains the two earlier-contract fields; HR-only fields.
CR8  no rule for the country: silent.
CR9  a company's own rule wins over the shared one.
"""
from datetime import date

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'wdgap_s8b')
class TestContractRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vn = cls.env.ref('base.vn')
        cls.idn = cls.env.ref('base.id')
        cls.company = cls.env['res.company'].create(
            {'name': 'S8B Rules VN', 'country_id': cls.vn.id})
        cls.company_id = cls.env['res.company'].create(
            {'name': 'S8B Rules ID', 'country_id': cls.idn.id})
        cls.env.user.company_ids = [(4, cls.company.id), (4, cls.company_id.id)]
        cls.env = cls.env(context=dict(
            cls.env.context, allowed_company_ids=[cls.company.id, cls.company_id.id],
            tracking_disable=True, mail_notrack=True))
        cls.Rule = cls.env['pb.contract.rule']
        cls._seq = 0

    def _emp(self, company=None, **kw):
        type(self)._seq += 1
        company = company or self.company
        vals = {'name': 'S8B Rules %s' % self._seq, 'company_id': company.id,
                'address_id': company.partner_id.id}
        vals.update(kw)
        return self.env['hr.employee'].with_context(
            allowed_company_ids=[company.id]).create(vals)

    def _contract(self, emp, start, end, prev=None, state='open', **kw):
        type(self)._seq += 1
        vals = {'name': 'S8B c %s' % self._seq, 'employee_id': emp.id,
                'wage': 1000.0, 'date_start': start, 'date_end': end,
                'state': state, 'company_id': emp.company_id.id}
        if prev is not None:
            vals['pb_renewed_from_id'] = prev.id
        vals.update(kw)
        return self.env['hr.contract'].with_context(
            allowed_company_ids=[emp.company_id.id]).create(vals)

    # ================================================================ CR1
    def test_cr01_rows(self):
        vn = self.env.ref('pb_contract_rules.rule_vn')
        idr = self.env.ref('pb_contract_rules.rule_id')
        self.assertEqual((vn.max_in_row, vn.max_months_each), (2, 36))
        self.assertEqual(idr.max_months_total, 60)
        self.assertIn('adviser', vn.source_note)
        self.assertIn('adviser', idr.source_note)
        with self.assertRaises(ValidationError):
            vn.write({'max_in_row': -1})

    # ================================================================ CR2
    def test_cr02_counting(self):
        emp = self._emp()
        c1 = self._contract(emp, date(2022, 1, 1), date(2022, 12, 31), state='close')
        c2 = self._contract(emp, date(2023, 1, 1), date(2023, 12, 31), prev=c1,
                            state='close')
        c3 = self._contract(emp, date(2024, 1, 20), date(2025, 1, 19), state='open')
        info = self.Rule.chain(c3)
        self.assertEqual(info['in_system'], 3, "link + a 19-day break both count")
        # a long break starts a new row
        emp2 = self._emp()
        self._contract(emp2, date(2022, 1, 1), date(2022, 6, 30), state='close')
        d2 = self._contract(emp2, date(2023, 1, 1), date(2023, 12, 31))
        self.assertEqual(self.Rule.chain(d2)['in_system'], 1)
        # a trial agreement does not count
        emp4 = self._emp()
        trial = self._contract(emp4, date(2023, 1, 1), date(2023, 2, 28), state='close')
        if 'vietnam_contract_type' in trial._fields:
            trial.vietnam_contract_type = 'probation'
        elif 'pb_payroll_contract_type' in trial._fields:
            trial.pb_payroll_contract_type = 'probation'
        f4 = self._contract(emp4, date(2023, 3, 1), date(2024, 2, 29))
        self.assertEqual(self.Rule.chain(f4)['in_system'], 1)
        # earlier contracts typed on the person are added
        emp.sudo().write({'pb_fixed_term_before': 2, 'pb_fixed_term_months_before': 24})
        info = self.Rule.chain(c3)
        self.assertEqual(info['count'], 5)
        self.assertGreater(info['months'], 24)

    # ================================================================ CR3
    def test_cr03_vietnam_third_contract_warns_never_blocks(self):
        emp = self._emp()
        c1 = self._contract(emp, date(2024, 1, 1), date(2024, 12, 31), state='close')
        c2 = self._contract(emp, date(2025, 1, 1), date(2026, 12, 31), prev=c1)
        review = self.env['pb.contract.review'].open_for(c2)
        preview = review.decision_preview('extend', months=12)
        self.assertIn('limit', preview)
        self.assertTrue(preview['limit']['over'])
        self.assertEqual(preview['limit']['count_after'], 3)
        self.assertIn('number 3 in a row', preview['limit']['sentence'])
        self.assertFalse(preview['blocked'], "never blocked (ruling J3)")
        self.assertNotIn('limit', review.decision_preview('convert'))
        # only the first renewal: no warning
        emp_b = self._emp()
        only = self._contract(emp_b, date(2025, 1, 1), date(2026, 12, 31))
        review_b = self.env['pb.contract.review'].open_for(only)
        self.assertNotIn('limit', review_b.decision_preview('extend', months=12))
        # one contract longer than 36 months
        self.assertTrue(review_b.decision_preview('extend', months=40)['limit']['over'])

    # ================================================================ CR4
    def test_cr04_indonesia_five_years(self):
        emp = self._emp(company=self.company_id)
        c1 = self._contract(emp, date(2022, 1, 1), date(2023, 12, 31), state='close')
        c2 = self._contract(emp, date(2024, 1, 1), date(2025, 12, 31), prev=c1)
        review = self.env['pb.contract.review'].open_for(c2)
        self.assertNotIn('limit', review.decision_preview('extend', months=12))
        preview = review.decision_preview('extend', months=24)
        self.assertTrue(preview['limit']['over'])
        self.assertIn('60 months', preview['limit']['sentence'])

    # ================================================================ CR5
    def test_cr05_request_past_the_rule(self):
        emp = self._emp()
        c1 = self._contract(emp, date(2024, 1, 1), date(2024, 12, 31), state='close')
        c2 = self._contract(emp, date(2025, 1, 1), date(2026, 12, 31), prev=c1)
        review = self.env['pb.contract.review'].open_for(c2)
        with self.assertRaises(UserError):
            review.action_request_extension(reason='  ', months=12)
        result = review.action_request_extension(
            reason='The project runs to the end of next year', months=12)
        self.assertTrue(result.get('extension_id'), "not blocked")
        extension = self.env['pb.contract.extension'].browse(result['extension_id'])
        self.assertTrue(extension._chain_facts()['past_fixed_term_rule']['value'])
        self.assertIn('past_fixed_term_rule', extension._chain_fact_specs())
        detail = extension._approval_detail(False)
        self.assertTrue(any(c['label'] == 'Fixed-term rule' for c in detail['chips']))
        bodies = ' '.join(review.message_ids.mapped('body'))
        self.assertIn('past the fixed-term rule', bodies)

    # ================================================================ CR6
    def test_cr06_drawer_line(self):
        emp = self._emp()
        c1 = self._contract(emp, date(2024, 1, 1), date(2024, 12, 31), state='close')
        c2 = self._contract(emp, date(2025, 1, 1), date(2026, 12, 31), prev=c1)
        drawer = self.env['pb.contractlife'].get_contract(c2.id)
        self.assertEqual(drawer['fixed_term']['count'], 2)
        self.assertEqual(drawer['fixed_term']['tone'], 'rose')
        self.assertIn('permanent', drawer['fixed_term']['next'])

    # ================================================================ CR7
    def test_cr07_updates_catalogue_and_rights(self):
        fields_by_model = self.env['pb.records.desk']._master_fields()
        self.assertIn('pb_fixed_term_before', fields_by_model['hr.employee'])
        self.assertIn('pb_fixed_term_months_before', fields_by_model['hr.employee'])
        self.assertIn('parent_id', fields_by_model['hr.employee'], "super() kept")
        field = self.env['hr.employee']._fields['pb_fixed_term_before']
        self.assertEqual(field.groups, 'hr.group_hr_user')

    # ================================================================ CR8
    def test_cr08_no_rule_is_silent(self):
        fr = self.env['res.company'].create(
            {'name': 'S8B Rules FR', 'country_id': self.env.ref('base.fr').id})
        self.env.user.company_ids = [(4, fr.id)]
        emp = self._emp(company=fr)
        c = self._contract(emp, date(2025, 1, 1), date(2025, 12, 31))
        self.assertFalse(self.Rule.check_extension(c, 12)['over'])
        self.assertEqual(self.Rule.summary(c).get('tone'), '')

    # ================================================================ CR9
    def test_cr09_company_rule_wins(self):
        own = self.Rule.create({'name': 'S8B house rule', 'country_id': self.vn.id,
                                'company_id': self.company.id, 'max_in_row': 1})
        emp = self._emp()
        self.assertEqual(self.Rule.rule_for(emp), own)
        c = self._contract(emp, date(2025, 1, 1), date(2025, 12, 31))
        self.assertTrue(self.Rule.check_extension(c, 6)['over'])
