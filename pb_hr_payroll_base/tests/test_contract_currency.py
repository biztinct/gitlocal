"""Explicit country payrolls keep the right denomination and money precision."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install','-at_install')
class TestContractPayrollCurrency(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company=self.env['res.company'].create({'name':'Country wage precision test','currency_id':self.env.ref('base.VND').id})
        self.env=self.env(context=dict(self.env.context,allowed_company_ids=self.company.ids))
        self.person=self.env['hr.employee'].create({'name':'Country wage person','company_id':self.company.id})

    def contract(self,country=False,wage=1234.56):
        return self.env['hr.contract'].create({'name':'Country wage contract','employee_id':self.person.id,
            'company_id':self.company.id,'date_start':'2026-01-01','state':'draft',
            'payroll_country':country,'wage':wage})

    def test_india_wage_keeps_rupee_cents_in_a_dong_company(self):
        contract=self.contract('IN')
        contract.invalidate_recordset(['wage'])
        self.assertEqual(contract.currency_id.name,'INR')
        self.assertAlmostEqual(contract.wage,1234.56,places=2)
        contract.wage=469103.83
        contract.invalidate_recordset(['wage'])
        self.assertAlmostEqual(contract.wage,469103.83,places=2)
        self.assertEqual(self.company.currency_id.name,'VND')

    def test_every_supported_country_uses_its_currency(self):
        for country,currency in [('VN','VND'),('ID','IDR'),('IN','INR'),('SG','SGD'),('MY','MYR')]:
            with self.subTest(country=country):
                self.assertEqual(self.contract(country).currency_id.name,currency)

    def test_unset_country_keeps_company_currency(self):
        self.assertEqual(self.contract().currency_id,self.company.currency_id)

    def test_currency_lookup_does_not_activate_currencies_or_convert_wages(self):
        currency=self.env.ref('base.INR')
        before=currency.active
        contract=self.contract('IN',1000)
        self.assertEqual(contract.currency_id,currency)
        self.assertEqual(currency.active,before)
        contract.payroll_country='SG'
        self.assertEqual(contract.currency_id.name,'SGD')
        self.assertEqual(contract.wage,1000)
