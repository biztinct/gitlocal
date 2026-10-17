# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P2 — T1: the three rate paths of ``hr.contract._pb_hourly_rate()``.

The cost column in the Schedule strip is only as trustworthy as this function,
and its whole value is that it is boring: one documented formula, one documented
fallback, and a zero instead of an exception. Each path is pinned here, plus the
two properties that matter more than any single number:

  * it NEVER raises — a half-filled contract is a rendering problem, not a
    crash;
  * it never writes (W12) — the whole helper is display math.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPbHourlyRate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.calendar = cls.env['resource.calendar'].create({
            'name': 'P2 rate calendar',
            'company_id': cls.company.id,
            'hours_per_day': 8.0,
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'P2 Rate Probe',
            'company_id': cls.company.id,
            'resource_calendar_id': cls.calendar.id,
        })

    def _contract(self, **vals):
        base = {
            'name': 'P2 rate contract',
            'employee_id': self.employee.id,
            'date_start': '2026-01-01',
            'wage': 22000.0,
            'state': 'draft',
            'company_id': self.company.id,
            'resource_calendar_id': self.calendar.id,
        }
        base.update(vals)
        return self.env['hr.contract'].create(base)

    def _structure(self, days, hours):
        Struct = self.env['hr.payroll.structure']
        if not ({'working_days_per_month', 'working_hours_per_day'}
                <= set(Struct._fields)):
            self.skipTest('pb_hr_payroll_base is not installed — no structure '
                          'denominators to test the primary path with')
        vals = {'name': 'P2 rate structure',
                'code': 'P2RATE%s%s' % (int(days), int(hours * 10)),
                'company_id': self.company.id,
                'working_days_per_month': days,
                'working_hours_per_day': hours}
        return Struct.create(vals)

    # ------------------------------------------------------- path 1: struct
    def test_rate_comes_from_the_salary_structure_when_it_can(self):
        """22 000 / (22 days × 8 h) = 125.0 — the documented primary path."""
        struct = self._structure(22.0, 8.0)
        contract = self._contract(struct_id=struct.id)
        self.assertAlmostEqual(contract._pb_monthly_hours(), 176.0, places=6)
        self.assertAlmostEqual(contract._pb_hourly_rate(), 125.0, places=6)

    def test_a_non_default_structure_moves_the_rate(self):
        """The point of reading the structure is that it is not always 8×22."""
        struct = self._structure(20.0, 7.5)          # 150 h
        contract = self._contract(struct_id=struct.id, wage=15000.0)
        self.assertAlmostEqual(contract._pb_monthly_hours(), 150.0, places=6)
        self.assertAlmostEqual(contract._pb_hourly_rate(), 100.0, places=6)

    # ----------------------------------------------------- path 2: calendar
    def test_rate_falls_back_to_the_calendar_when_there_is_no_structure(self):
        """hours_per_week × 52 / 12. A 40 h week is 173.333 h a month."""
        self.calendar.write({'hours_per_week': 40.0})
        contract = self._contract(wage=17333.333333)
        # no struct_id at all -> the fallback is the only path available
        self.assertFalse(contract.struct_id)
        self.assertAlmostEqual(contract._pb_monthly_hours(),
                               40.0 * 52.0 / 12.0, places=6)
        self.assertAlmostEqual(contract._pb_hourly_rate(), 100.0, places=3)

    def test_an_empty_structure_also_falls_through_to_the_calendar(self):
        """A structure that exists but carries no denominators is not a
        structure path — it must not divide by zero, it must fall through."""
        struct = self._structure(0.0, 0.0)
        self.calendar.write({'hours_per_week': 40.0})
        contract = self._contract(struct_id=struct.id, wage=17333.333333)
        self.assertAlmostEqual(contract._pb_monthly_hours(),
                               40.0 * 52.0 / 12.0, places=6)
        self.assertAlmostEqual(contract._pb_hourly_rate(), 100.0, places=3)

    # --------------------------------------------------------- path 3: zero
    def test_no_wage_is_zero_and_not_an_exception(self):
        contract = self._contract(wage=0.0)
        self.assertEqual(contract._pb_hourly_rate(), 0.0)

    def test_no_denominator_anywhere_is_zero_and_not_an_exception(self):
        """No structure denominators, no calendar hours → 0.0, silently. The
        strip footnotes the person; it does not print a confident wrong total."""
        self.calendar.write({'hours_per_week': 0.0})
        contract = self._contract()
        contract.resource_calendar_id = False
        self.employee.resource_calendar_id = False
        self.assertEqual(contract._pb_monthly_hours(), 0.0)
        self.assertEqual(contract._pb_hourly_rate(), 0.0)

    def test_a_negative_wage_is_not_a_negative_rate(self):
        contract = self._contract(wage=-100.0)
        self.assertEqual(contract._pb_hourly_rate(), 0.0)

    # ------------------------------------------------------------ W12 rails
    def test_the_rate_helper_is_display_math_only(self):
        """No write, no create, no unlink anywhere in the helper's file — it is
        a READ helper and a later phase must not quietly make it something
        else."""
        import os

        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('pb_schedule'), 'models',
                            'hr_contract.py')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        for needle in ('.write(', '.create(', '.unlink(', 'sudo('):
            self.assertNotIn(
                needle, body,
                'the rate helper must stay pure display math (W12): found %s'
                % needle)

    def test_it_uses_the_documented_wage_override_point(self):
        """`_get_contract_wage()` and not a raw `.wage` read: a country module
        that pays on another field must be respected, not bypassed."""
        import os

        from odoo.modules.module import get_module_path
        path = os.path.join(get_module_path('pb_schedule'), 'models',
                            'hr_contract.py')
        with open(path, encoding='utf-8') as fh:
            body = fh.read()
        self.assertIn('_get_contract_wage()', body)
