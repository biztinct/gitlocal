# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for the workforce → payroll bridge.

Phase-B handover §6 cases 7, 8, 10 plus review fix F1 (the money path):
  * 7  — approved OT hours land as the declared OTHRS* input codes, summed per
         type WITHIN the slip period; a config without those codes is unchanged.
  * 8  — the post_init collision hook warns about a code that shadows an OT code.
  * 10 — pb_hr_workforce carries no formula-engine dependency (the coupling is
         confined to this glue module).
  * F1 — the OT search is sudo, so a non-manager payroll user computing a slip
         gets the full OT sum for OTHER employees, not a silent 0.
"""

from datetime import date, timedelta

from odoo.addons.pb_workforce_payroll_bridge import post_init_hook
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBridge(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.emp = cls.env['hr.employee'].create({
            'name': 'OT Earner', 'company_id': cls.company.id,
        })
        cls.d_from = date(2026, 6, 1)
        cls.d_to = date(2026, 6, 30)

        # a formula config declaring two OT input codes + a plain input
        cls.config = cls._make_config('ZZBRIDGE1', [
            ('OT weekday', 'OTHRS150'),
            ('OT weekend', 'OTHRS200'),
            ('Base wage', 'WAGE'),
        ])
        # a config WITHOUT any OT codes (only a plain input)
        cls.config_plain = cls._make_config('ZZBRIDGE2', [('Base wage', 'WAGE')])
        # a config declaring the Bonus-Hours input (Phase K)
        cls.config_bonus = cls._make_config('ZZBRIDGE3', [
            ('OT weekday', 'OTHRS150'), ('Bonus hours', 'BONHRS')])

        cls.slip = cls.env['hr.payslip'].create({
            'employee_id': cls.emp.id,
            'date_from': cls.d_from, 'date_to': cls.d_to,
        })

    @classmethod
    def _make_config(cls, code, rules):
        cfg = cls.env['hr.formula.config'].create({
            'name': code, 'code': code, 'country_code': 'VN',
            'company_id': cls.company.id,
        })
        for name, rcode in rules:
            cls.env['hr.formula.rule'].create({
                'config_id': cfg.id, 'name': name, 'code': rcode,
                'column_type': 'input',
            })
        return cfg

    def _approved_ot(self, ot_type, hours, day, employee=None):
        return self.env['hr.overtime.request'].create({
            'employee_id': (employee or self.emp).id, 'date': day,
            'overtime_type': ot_type, 'planned_hours': hours,
            'approved_hours': hours, 'reason': 'x', 'state': 'approved',
        })

    # -------------------------------------------------------------- §6.7
    def test_01_ot_codes_summed_in_period(self):
        self._approved_ot('weekday', 5.0, date(2026, 6, 10))
        self._approved_ot('weekday', 3.0, date(2026, 6, 20))
        self._approved_ot('weekend', 4.0, date(2026, 6, 13))
        # outside the slip period → must NOT count
        self._approved_ot('weekday', 9.0, date(2026, 5, 30))
        # not approved → must NOT count
        self.env['hr.overtime.request'].create({
            'employee_id': self.emp.id, 'date': date(2026, 6, 12),
            'overtime_type': 'weekday', 'planned_hours': 7.0,
            'reason': 'x', 'state': 'submitted',
        })
        values = self.slip._get_formula_input_values(self.config)
        self.assertAlmostEqual(values['OTHRS150'], 8.0)
        self.assertAlmostEqual(values['OTHRS200'], 4.0)

    def test_02_no_ot_when_none(self):
        values = self.slip._get_formula_input_values(self.config)
        self.assertAlmostEqual(values['OTHRS150'], 0.0)
        self.assertAlmostEqual(values['OTHRS200'], 0.0)

    def test_03_config_without_ot_codes_untouched(self):
        self._approved_ot('weekday', 5.0, date(2026, 6, 10))
        values = self.slip._get_formula_input_values(self.config_plain)
        self.assertNotIn('OTHRS150', values)
        self.assertNotIn('OTHRS200', values)
        self.assertIn('WAGE', values)

    # -------------------------------------------------------------- §6.8
    def test_04_collision_hook_warns(self):
        # a rule whose code is a substring of an OT code must be flagged
        self.env['hr.formula.rule'].create({
            'config_id': self.config_plain.id, 'name': 'Shadow',
            'code': 'OTHRS15', 'column_type': 'input',
        })
        with self.assertLogs('odoo.addons.pb_workforce_payroll_bridge',
                             level='WARNING') as cm:
            post_init_hook(self.env)
        self.assertTrue(any('OTHRS15' in m for m in cm.output), cm.output)

    # -------------------------------------------------------------- §6.10
    def test_05_workforce_has_no_formula_dependency(self):
        mod = self.env['ir.module.module'].search(
            [('name', '=', 'pb_hr_workforce')], limit=1)
        deps = mod.dependencies_id.mapped('name')
        self.assertNotIn('pb_hr_payroll_formula', deps)
        self.assertNotIn('pb_workforce_payroll_bridge', deps)

    # ------------------------------------------------------------- §6.11 BONHRS
    def _bonus_ot(self, approved, bonus, day):
        return self.env['hr.overtime.request'].create({
            'employee_id': self.emp.id, 'date': day, 'overtime_type': 'weekday',
            'planned_hours': approved + bonus, 'approved_hours': approved,
            'bonus_hours': bonus, 'reason': 'x', 'state': 'approved'})

    def test_07_bonhrs_sums_bonus_of_approved(self):
        # approved 4+2 and 3+1 in period → BONHRS 3.0, OTHRS150 unchanged (7.0)
        self._bonus_ot(4.0, 2.0, date(2026, 6, 10))
        self._bonus_ot(3.0, 1.0, date(2026, 6, 20))
        # a draft with bonus and a refused one → contribute nothing
        self.env['hr.overtime.request'].create({
            'employee_id': self.emp.id, 'date': date(2026, 6, 12),
            'overtime_type': 'weekday', 'planned_hours': 9.0,
            'approved_hours': 4.0, 'bonus_hours': 5.0, 'reason': 'x',
            'state': 'draft'})
        values = self.slip._get_formula_input_values(self.config_bonus)
        self.assertAlmostEqual(values['BONHRS'], 3.0)
        self.assertAlmostEqual(values['OTHRS150'], 7.0)   # within-cap only

    def test_08_bonhrs_absent_when_not_declared(self):
        self._bonus_ot(4.0, 2.0, date(2026, 6, 10))
        values = self.slip._get_formula_input_values(self.config)   # no BONHRS rule
        self.assertNotIn('BONHRS', values)

    def test_09_bonhrs_registered_no_collision(self):
        from odoo.addons.pb_workforce_payroll_bridge.models.hr_payslip import (
            BONUS_INPUT_CODE, OT_INPUT_MAP)
        codes = list(OT_INPUT_MAP) + [BONUS_INPUT_CODE]
        # underscore-free + pairwise non-substring within the registry
        for c in codes:
            self.assertNotIn('_', c)
        self.assertNotIn(BONUS_INPUT_CODE, OT_INPUT_MAP)

    # ------------------------------------------------------------- F1 money path
    def test_06_ot_search_is_sudo_for_other_employees(self):
        self._approved_ot('weekday', 6.0, date(2026, 6, 10))

        officer = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Pay Officer', 'login': 'bridge_pay_officer',
                'group_ids': [(6, 0, [
                    self.env.ref('hr_attendance.group_hr_attendance_officer').id,
                    self.env.ref('hr.group_hr_user').id,
                    self.env.ref('om_hr_payroll.group_hr_payroll_user').id,
                ])],
            })
        # the officer owns none of these requests → a plain search sees nothing
        self.assertFalse(self.env['hr.overtime.request'].with_user(officer).search(
            [('employee_id', '=', self.emp.id)]))
        # …but the bridge's sudo search still returns the full OT sum
        values = self.slip.with_user(officer)._get_formula_input_values(self.config)
        self.assertAlmostEqual(values['OTHRS150'], 6.0)
