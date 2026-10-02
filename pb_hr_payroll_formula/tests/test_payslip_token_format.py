# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""How a component's value is FORMATTED on a printed payslip.

Found live on the reference tenant 2026-09-04. Two components declared
"Quantity (hours, days)" on the Treatment screen printed as ``₫62`` and
``₫151`` in the Hours column of a real employee payslip. The renderer read
only ``number_format`` — an older per-column display flag that still defaults
to 'currency' — and never looked at ``value_kind``, which is the setting the
owner actually sets and the one that says what the value IS.

The rule these tests pin: value_kind decides, and money keeps its existing
output untouched.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPayslipTokenFormat(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Config = cls.env['hr.formula.config']
        cls.config = cls.Config.create({
            'name': 'Token format probe', 'code': 'TOKEN_FMT',
            'country_code': 'VN', 'state': 'draft',
        })

    def _rule(self, code, **vals):
        base = {'config_id': self.config.id, 'name': code, 'code': code}
        base.update(vals)
        return self.env['hr.formula.rule'].create(base)

    def _fmt(self, rule, value, currency='₫'):
        return self.Config._payslip_token_value(rule, value, currency)

    # ------------------------------------------------------- the live defect
    def test_01_a_quantity_never_prints_a_currency_symbol(self):
        """The exact shape of the live defect: hours declared as a Quantity,
        with number_format left at its 'currency' default."""
        hours = self._rule('QTYHOURS', value_kind='quantity',
                           number_format='currency')
        self.assertEqual(self._fmt(hours, 62), '62')
        self.assertEqual(self._fmt(hours, 151), '151')
        self.assertEqual(self._fmt(hours, 7.5), '7.5',
                         "a half day of hours must survive the formatting")
        self.assertNotIn('₫', self._fmt(hours, 62))

    # ------------------------------------------------- money is not touched
    def test_02_money_keeps_exactly_what_it_printed_before(self):
        pay = self._rule('MONEYPAY', value_kind='money', number_format='currency')
        self.assertEqual(self._fmt(pay, 19500000), '₫19,500,000')
        self.assertEqual(self._fmt(pay, -2092500), '−₫2,092,500',
                         "a deduction keeps its minus sign in front of the symbol")
        self.assertEqual(self._fmt(pay, 0), '₫0')

    def test_03_money_still_defers_to_number_format(self):
        """value_kind 'money' is deliberately absent from the override map, so
        a money component whose column was formatted otherwise is unchanged."""
        plain = self._rule('MONEYPLAIN', value_kind='money', number_format='number')
        self.assertEqual(self._fmt(plain, 1234.5), '1,234.5')
        whole = self._rule('MONEYINT', value_kind='money', number_format='integer')
        self.assertEqual(self._fmt(whole, 1234.5), '1,234')

    # ------------------------------------------------------ the other kinds
    def test_04_every_non_money_kind_drops_the_currency(self):
        for kind in ('quantity', 'decimal', 'integer', 'rate',
                     'identifier', 'text', 'date', 'boolean'):
            rule = self._rule('KIND%s' % kind.upper()[:7], value_kind=kind,
                              number_format='currency')
            self.assertNotIn('₫', self._fmt(rule, 12),
                             "%s is not an amount and must not print a "
                             "currency symbol" % kind)

    def test_05_a_rate_prints_as_a_percentage(self):
        rate = self._rule('RATEPCT', value_kind='rate', number_format='currency')
        self.assertEqual(self._fmt(rate, 0.105), '10.5%')

    def test_06_a_whole_number_kind_has_no_decimals(self):
        whole = self._rule('WHOLENUM', value_kind='integer', number_format='currency')
        self.assertEqual(self._fmt(whole, 3.0), '3')

    # ------------------------------------------------------------- no value
    def test_07_a_missing_value_is_a_dash_whatever_the_kind(self):
        hours = self._rule('QTYNONE', value_kind='quantity')
        self.assertEqual(self._fmt(hours, None), '—',
                         "a component with no value on this slip must not "
                         "print as zero — that is a different statement")
