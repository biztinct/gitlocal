import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.addons.pb_pay_builder.tests.common import make_scheme


@tagged('post_install', '-at_install', 'paybuilder', 'paybuilder_offer')
class TestOfferBuilder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'DEMO Offer Office', 'country_id': cls.env.ref('base.vn').id,
                                                    'currency_id': cls.env.ref('base.VND').id})
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.company.ids))
        cls.rules = make_scheme(cls.env, cls.company, 'WAGE')
        cls.recruiter = new_test_user(cls.env, login='demo_offer_builder', groups='base.group_user,pb_hiring.group_hiring_user',
                                      company_id=cls.company.id, company_ids=[(6, 0, cls.company.ids)])
        team = cls.env['hr.department'].create({'name': 'DEMO Offer Team', 'company_id': cls.company.id})
        app = cls.env['hr.applicant'].create({'partner_name': 'DEMO Offer Person', 'company_id': cls.company.id})
        req = cls.env['pb.hiring.requisition'].create({'title': 'DEMO Role', 'department_id': team.id, 'company_id': cls.company.id,
            'headcount': 1, 'budget_cost': 1, 'requirements': 'DEMO', 'state': 'open', 'request_state': 'agreed',
            'selected_applicant_id': app.id, 'recruiter_id': cls.recruiter.id})
        cls.offer = cls.env['pb.hiring.offer'].create({'requisition_id': req.id, 'applicant_id': app.id,
            'currency_id': cls.rules.currency_id.id, 'job_title': 'DEMO Analyst', 'start_date': fields.Date.today() + timedelta(days=30)})
        cls.api = cls.env['pb.pay.builder'].with_user(cls.recruiter)
        cls.ref = {'offer_id': cls.offer.id, 'scheme_id': cls.rules.id}
        cls.values = {'wage': 30000000, 'PHONE': 500000, 'DEP': 0}

    def test_43_offer_gate(self):
        self.assertTrue(self.api.work_out('offer', self.ref, self.values)['ok'])
        with patch.object(type(self.env['pb.hiring']), '_is_hiring_reader', return_value=False):
            refused = self.api.work_out('offer', self.ref, self.values)
            self.assertFalse(refused['ok'])
            self.assertIn("figures are with the hiring team", refused['reason'])
        self.offer.state = 'hr_ok'
        self.assertFalse(self.api.work_out('offer', self.ref, self.values)['ok'])
        self.assertFalse(self.api.work_back('offer', self.ref, self.values, {}, 1000)['ok'])

    def test_44_monthly_lines_and_values(self):
        bonus = self.env['pb.hiring.offer.line'].create({'offer_id': self.offer.id, 'name': 'DEMO Bonus',
                                                       'kind': 'bonus', 'period': 'yearly', 'amount': 17000})
        for phone in (125000, 500000):
            self.api.offer_builder_use(self.offer.id, self.rules.id, dict(self.values, PHONE=phone))
        lines = self.offer.line_ids.filtered('pb_from_total')
        wanted = self.api.work_out('offer', self.ref, self.values)
        earn = next(s['lines'] for s in wanted['sections'] if s['key'] == 'earn')
        self.assertEqual(len(lines), sum(1 for r in earn if r['amount'] > 0))
        self.assertTrue(bonus.exists())
        self.assertEqual(lines.filtered('pb_item_wage').amount, 30000000)
        self.assertEqual(lines.filtered(lambda line: line.pb_item_code == 'PHONE').amount, 500000)
        self.assertEqual(json.loads(self.offer.pbpb_values), self.values)
        self.assertEqual(self.offer.pbpb_gross, wanted['totals']['gross'])
        self.assertEqual(self.offer.pbpb_net, wanted['totals']['net'])

    def test_45_currency(self):
        self.offer.currency_id = self.env.ref('base.USD')
        out = self.api.work_out('offer', self.ref, self.values)
        self.assertFalse(out['ok'])
        self.assertIn('Change the offer\'s money or pick another scheme.', out['reason'])

    def test_46_letter(self):
        self.api.offer_builder_use(self.offer.id, self.rules.id, self.values)
        def letters():
            result = [str(self.offer._lines_table())]
            if hasattr(self.offer, '_pbds_offer_values'):
                result.append(self.offer._pbds_offer_values('en_US')['lines'])
            return result
        for letter in letters():
            self.assertIn('<table', letter)
            self.assertIn('Take-home after the usual deductions', letter)
        self.api.offer_builder_letter(self.offer.id, False)
        for letter in letters():
            self.assertNotIn('<table', letter)
            self.assertNotIn('Take-home', letter)
            self.assertIn('Gross pay of', letter)
