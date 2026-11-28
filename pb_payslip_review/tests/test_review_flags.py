# -*- coding: utf-8 -*-
"""LEARN REFRESH step 6 — "Need review" flags a big change in take-home pay.

One shared answer (`hr.payslip.run.pb_review_flags`) read by the Run lens's
Review step and by Pay Run › Payslips. Cases: up, down, a joiner (no previous
payslip), the threshold setting (and 0 = off), zero take-home, another scheme
is not "previous", and the SQL net matches the ORM helper.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReviewFlags(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['hr.payslip.run']
        cls.company = cls.env.company
        Config = cls.env.get('hr.formula.config')
        cls.Config = Config
        cls.net_cat = cls.env['hr.salary.rule.category'].search(
            [('code', '=', 'NET')], limit=1)
        cls.rule = cls.env['hr.salary.rule'].search([], limit=1)
        cls.env['ir.config_parameter'].sudo().set_param(
            'pb_payslip_review.net_change_pct', '30')

    def setUp(self):
        super().setUp()
        if self.Config is None or 'formula_config_id' not in self.env['hr.payslip']._fields:
            self.skipTest('This build has no payroll schemes.')
        if not self.net_cat or not self.rule:
            self.skipTest('No NET category / salary rule in this database.')
        vals = {'name': 'RF Scheme', 'code': 'RFSCHEME', 'company_id': self.company.id}
        if 'country_code' in self.Config._fields:
            vals['country_code'] = 'VN'
        self.scheme = self.Config.create(vals)
        vals2 = dict(vals, name='RF Other', code='RFOTHER')
        self.other = self.Config.create(vals2)
        self.emp = self.env['hr.employee'].create(
            {'name': 'RF Person', 'company_id': self.company.id})
        self.contract = self.env['hr.contract'].create({
            'name': 'RF contract', 'employee_id': self.emp.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id})

    def _slip(self, month, net, config=None, run=None, employee=None):
        emp = employee or self.emp
        start, end = '2026-%02d-01' % month, '2026-%02d-28' % month
        if run is None:
            run = self.Run.create({'name': 'RF %s' % month,
                                   'date_start': start, 'date_end': end})
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'name': 'RF slip %s' % month,
            'contract_id': self.contract.id if emp == self.emp else False,
            'date_from': start, 'date_to': end, 'company_id': self.company.id,
            'payslip_run_id': run.id,
            'formula_config_id': (config or self.scheme).id,
        })
        line = {'slip_id': slip.id, 'name': 'Net pay', 'code': 'NET',
                'amount': net, 'quantity': 1.0, 'rate': 100.0,
                'employee_id': emp.id, 'category_id': self.net_cat.id,
                'salary_rule_id': self.rule.id}
        if 'pay_role' in self.env['hr.payslip.line']._fields:
            line['pay_role'] = 'net'
        self.env['hr.payslip.line'].create(line)
        return slip, run

    def _flag(self, slip, run):
        return run.pb_review_flags()[slip.id]

    def test_01_net_up_is_flagged_with_a_plain_reason(self):
        self._slip(6, 1000.0)
        slip, run = self._slip(7, 1420.0)
        f = self._flag(slip, run)
        self.assertTrue(f['flag'])
        self.assertEqual(f['kind'], 'change')
        self.assertIn('up 42%', f['reason'])
        self.assertIn('June', f['reason'])

    def test_02_net_down_is_flagged(self):
        self._slip(6, 1000.0)
        slip, run = self._slip(7, 500.0)
        f = self._flag(slip, run)
        self.assertTrue(f['flag'])
        self.assertIn('down 50%', f['reason'])

    def test_03_joiner_is_not_flagged(self):
        slip, run = self._slip(7, 1420.0)
        f = self._flag(slip, run)
        self.assertFalse(f['flag'])
        self.assertIsNone(f['prev_net'])

    def test_04_threshold_is_the_setting(self):
        self._slip(6, 1000.0)
        slip, run = self._slip(7, 1200.0)       # +20%
        self.assertFalse(self._flag(slip, run)['flag'])
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_payslip_review.net_change_pct', '10')
        self.assertTrue(self._flag(slip, run)['flag'])
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_payslip_review.net_change_pct', '0')
        self.assertFalse(self._flag(slip, run)['flag'], '0 switches it off')

    def test_05_settings_field_reads_and_writes_the_parameter(self):
        settings = self.env['res.config.settings'].create({})
        self.assertEqual(settings.pb_review_change_pct, 30)
        settings.pb_review_change_pct = 25
        settings.execute()
        self.assertEqual(self.Run.pb_review_change_pct(), 25.0)

    def test_06_zero_take_home_is_flagged(self):
        slip, run = self._slip(7, 0.0)
        f = self._flag(slip, run)
        self.assertTrue(f['flag'])
        self.assertEqual(f['kind'], 'zero')

    def test_07_another_scheme_is_not_previous(self):
        self._slip(6, 1000.0, config=self.other)
        slip, run = self._slip(7, 1420.0)
        self.assertFalse(self._flag(slip, run)['flag'])

    def test_08_net_matches_the_orm_helper(self):
        slip, run = self._slip(7, 1234.0)
        self.assertEqual(self._flag(slip, run)['net'], slip.pb_net_amount())

    def test_09_both_screens_count_the_same(self):
        self._slip(6, 1000.0)
        slip, run = self._slip(7, 2000.0)
        review = self.env['pb.payslip.review'].get_review_data(run.id)
        self.assertEqual(review['totals']['flagged'], 1)
        row = next(s for s in review['slips'] if s['id'] == slip.id)
        self.assertIn('up 100%', row['why'])
        Wizard = self.env.get('pb.payrun.wizard')
        if Wizard is not None:
            summary = Wizard.get_summary(run.id)
            self.assertEqual(summary['flagged'], review['totals']['flagged'])
