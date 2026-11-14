# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP PR-D T6 — approved overtime is paid once a month, in the regular run.

The bridge used to feed every payslip of the month, whatever run it sat in, so
a Top-up for the same month paid the approved overtime a second time (WDGAP
PR1 facts §A, "Double-pay guard: none"). It now feeds a payslip in a Regular
run — or in no run at all — and leaves a Top-up's or an Extra run's payslip
alone. A Regular run's values are exactly what they always were (R1).
"""

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBridgeRunKinds(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['hr.payslip.run']
        cls.has_kind = 'pb_run_kind' in cls.Run._fields
        cls.company = cls.env.company
        cls.emp = cls.env['hr.employee'].create({
            'name': 'OT Kind Earner', 'company_id': cls.company.id})
        cls.d_from = date(2026, 6, 1)
        cls.d_to = date(2026, 6, 30)
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'ZZPRDOT', 'code': 'ZZPRDOT', 'country_code': 'VN',
            'company_id': cls.company.id})
        for name, code in (('OT weekday', 'OTHRS150'), ('OT weekend', 'OTHRS200'),
                           ('Bonus hours', 'BONHRS'), ('Base wage', 'WAGE')):
            cls.env['hr.formula.rule'].create({
                'config_id': cls.config.id, 'name': name, 'code': code,
                'column_type': 'input'})
        Req = cls.env['hr.overtime.request']
        Req.create({'employee_id': cls.emp.id, 'date': date(2026, 6, 10),
                    'overtime_type': 'weekday', 'planned_hours': 8.0,
                    'approved_hours': 5.0, 'bonus_hours': 3.0, 'reason': 'x',
                    'state': 'approved'})
        Req.create({'employee_id': cls.emp.id, 'date': date(2026, 6, 13),
                    'overtime_type': 'weekend', 'planned_hours': 4.0,
                    'approved_hours': 4.0, 'reason': 'x', 'state': 'approved'})

    def setUp(self):
        super().setUp()
        if not self.has_kind:
            self.skipTest('pb_payruns (the kind of run) is not installed here.')

    def _slip(self, kind=None):
        run = False
        if kind:
            if kind not in dict(self.Run._fields['pb_run_kind'].selection):
                self.skipTest('This build has no %s run.' % kind)
            run = self.Run.create({'name': 'June %s' % kind,
                                   'date_start': self.d_from,
                                   'date_end': self.d_to,
                                   'pb_run_kind': kind})
        return self.env['hr.payslip'].create({
            'employee_id': self.emp.id, 'date_from': self.d_from,
            'date_to': self.d_to, 'payslip_run_id': run.id if run else False})

    def test_t6_a_regular_run_is_fed_exactly_as_before(self):
        alone = self._slip()._get_formula_input_values(self.config)
        regular = self._slip('regular')._get_formula_input_values(self.config)
        # golden (R1): the very numbers the bridge has always produced
        self.assertEqual(alone['OTHRS150'], 5.0)
        self.assertEqual(alone['OTHRS200'], 4.0)
        self.assertEqual(alone['BONHRS'], 3.0)
        for code in ('OTHRS150', 'OTHRS200', 'BONHRS'):
            self.assertEqual(regular[code], alone[code], code)

    def test_t6_an_extra_run_is_not_fed(self):
        values = self._slip('extra')._get_formula_input_values(self.config)
        for code in ('OTHRS150', 'OTHRS200', 'BONHRS'):
            self.assertFalse(values.get(code), code)
        self.assertIn('WAGE', values)

    def test_t6_a_topup_is_no_longer_fed(self):
        """BEHAVIOUR CHANGE (WDGAP PR-D): a Top-up used to receive the
        month's approved overtime again; it now receives none."""
        values = self._slip('topup')._get_formula_input_values(self.config)
        for code in ('OTHRS150', 'OTHRS200', 'BONHRS'):
            self.assertFalse(values.get(code), code)

    def test_t6_provenance_is_only_written_for_what_is_fed(self):
        # The engine records an origin for every declared input; on an
        # Extra run none of them may claim to come from approved overtime.
        prov = {}
        self._slip('extra')._get_formula_input_values(self.config, provenance=prov)
        for code in ('OTHRS150', 'OTHRS200', 'BONHRS'):
            self.assertNotEqual((prov.get(code) or {}).get('via'),
                                'overtime_request', code)
        prov = {}
        self._slip('regular')._get_formula_input_values(self.config, provenance=prov)
        self.assertEqual(prov['OTHRS150']['via'], 'overtime_request')
