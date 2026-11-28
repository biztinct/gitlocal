# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP PR-D T6 — approved trip days and per-diem are paid once a month.

They reach a payslip in a Regular run (or in no run at all), exactly as
before; a Top-up's or an Extra run's payslip is left alone. Before this, a
Top-up for the same month paid the per-diem a second time.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTripBridgeRunKinds(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['hr.payslip.run']
        cls.has_kind = 'pb_run_kind' in cls.Run._fields
        cls.company = cls.env.company
        cls.vnd = cls.env.ref('base.VND', raise_if_not_found=False) \
            or cls.company.currency_id
        cls.emp = cls.env['hr.employee'].create({
            'name': 'Trip Kind Payroll', 'company_id': cls.company.id})
        cls.d_from = date(2026, 6, 1)
        cls.d_to = date(2026, 6, 30)
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'ZZPRDTRIP', 'code': 'ZZPRDTRIP', 'country_code': 'VN',
            'company_id': cls.company.id})
        for code in ('TRIPDAYS', 'PERDIEM', 'WAGE'):
            cls.env['hr.formula.rule'].create({
                'config_id': cls.config.id, 'name': code, 'code': code,
                'column_type': 'input'})
        policy = cls.env['pb.trip.policy'].create({
            'name': 'PRD payroll', 'per_diem_rate': 200000.0,
            'currency_id': cls.vnd.id, 'per_diem_channel': 'payroll'})
        trip = cls.env['pb.business.trip'].create({
            'employee_id': cls.emp.id, 'date_from': date(2026, 6, 10),
            'date_to': date(2026, 6, 12), 'purpose': 'x',
            'per_diem_rate': 200000.0, 'policy_id': policy.id,
            'currency_id': cls.vnd.id, 'company_id': cls.company.id})
        # Approved directly: the trip's own approval chain is not what is
        # under test (and needs a route set up on a bare test database).
        cls.env.flush_all()
        cls.env.cr.execute("UPDATE pb_business_trip SET state = 'approved' "
                           "WHERE id = %s", (trip.id,))
        trip.invalidate_recordset()

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
        self.assertEqual(alone['TRIPDAYS'], 3)                  # golden (R1)
        self.assertAlmostEqual(alone['PERDIEM'], 600000.0)
        self.assertEqual(regular['TRIPDAYS'], alone['TRIPDAYS'])
        self.assertEqual(regular['PERDIEM'], alone['PERDIEM'])

    def test_t6_an_extra_run_is_not_fed(self):
        values = self._slip('extra')._get_formula_input_values(self.config)
        self.assertFalse(values.get('TRIPDAYS'))
        self.assertFalse(values.get('PERDIEM'))
        self.assertIn('WAGE', values)

    def test_t6_a_topup_is_no_longer_fed(self):
        """BEHAVIOUR CHANGE (WDGAP PR-D): a Top-up used to receive the
        month's per-diem again; it now receives none."""
        values = self._slip('topup')._get_formula_input_values(self.config)
        self.assertFalse(values.get('TRIPDAYS'))
        self.assertFalse(values.get('PERDIEM'))
