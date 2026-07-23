# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for Phase E — Young Worker Rules (§6 cases 1–10).

The live gates BLOCK creating violating data (that's the point), so historical
breaches for check_period are seeded with the rule momentarily deactivated.
"""

from datetime import datetime, date, time, timedelta

from dateutil.relativedelta import relativedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestYoungWorker(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Eng = cls.env['pb.young.worker']
        cls.Att = cls.env['hr.attendance']
        Emp = cls.env['hr.employee']

        cls.today = date(2026, 6, 15)  # a Monday-anchored fixed reference
        cls.monday = cls.today - timedelta(days=cls.today.weekday())

        # isolate from the rule the post_init_hook seeded for this company —
        # otherwise it stays active and interferes with the deactivate-to-seed
        # technique below (rolled back with the class).
        cls.env['pb.young.worker.rule'].sudo().search(
            [('company_id', '=', cls.company.id)]).write({'active': False})

        # one active rule for this company with VN bands (mirrors the seed hook)
        cls.rule = cls.env['pb.young.worker.rule'].create({
            'name': 'VN Test', 'company_id': cls.company.id,
            'night_from': 22.0, 'night_to': 6.0,
            'band_ids': [
                (0, 0, {'age_min': 0, 'age_max': 15, 'max_hours_day': 4.0,
                        'max_hours_week': 20.0, 'ot_blocked': True,
                        'night_blocked': True, 'note': 'Under 15'}),
                (0, 0, {'age_min': 15, 'age_max': 18, 'max_hours_day': 8.0,
                        'max_hours_week': 40.0, 'ot_blocked': True,
                        'night_blocked': True, 'note': '15 to under 18'}),
            ],
        })

        def mk(name, years=None):
            vals = {'name': name, 'company_id': cls.company.id, 'tz': 'UTC'}
            if years is not None:
                vals['birthday'] = cls.today - relativedelta(years=years, days=100)
            return Emp.create(vals)

        cls.emp17 = mk('Minor Seventeen', 17)
        cls.emp14 = mk('Minor Fourteen', 14)
        cls.emp_adult = mk('Adult Thirty', 30)
        cls.emp_none = mk('No Birthday')  # no birthday on file
        # exactly-18-on-the-day: turns 18 precisely on cls.today
        cls.emp18 = Emp.create({'name': 'Just Eighteen', 'company_id': cls.company.id,
                                'tz': 'UTC', 'birthday': cls.today - relativedelta(years=18)})

        # OT config so weekday OT chip-measures appear in the grid (for the lock)
        cls.env['hr.overtime.config'].create({
            'name': 'Weekday OT', 'overtime_type': 'weekday', 'rate_multiplier': 1.5,
            'company_id': cls.company.id})

        # an attendance officer (+ HR read, so the base grid's get_ot_ceilings
        # can read employee company/private fields) to drive the grid (§6.5)
        cls.officer = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'YW Officer', 'login': 'yw_officer',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('hr.group_hr_user').id,
                cls.env.ref('hr_attendance.group_hr_attendance_officer').id])]})

        # shift templates
        Tmpl = cls.env['hr.shift.template']
        cls.night_tmpl = Tmpl.create({
            'name': 'Night', 'code': 'NGT', 'start_hour': 21.0, 'end_hour': 5.0,
            'is_overnight': True, 'shift_type': 'night', 'company_id': cls.company.id})
        cls.day_tmpl = Tmpl.create({
            'name': 'Day', 'code': 'DAY', 'start_hour': 6.0, 'end_hour': 14.0,
            'is_overnight': False, 'shift_type': 'morning', 'company_id': cls.company.id})

    # ------------------------------------------------------------- helpers
    def _att(self, emp, d, hours, start_h=3):
        ci = datetime.combine(d, time(start_h, 0))
        return self.Att.create({
            'employee_id': emp.id,
            'check_in': ci, 'check_out': ci + timedelta(hours=hours),
            'pb_entry_source': 'grid',
        })

    # ---------------------------------------------------- §6.1 band resolution
    def test_01_band_resolution(self):
        b14 = self.Eng.get_band(self.emp14, self.today)
        b17 = self.Eng.get_band(self.emp17, self.today)
        self.assertTrue(b14 and b14.age_max == 15)
        self.assertTrue(b17 and b17.age_min == 15 and b17.age_max == 18)
        # 18 exactly on the birthday → no band
        self.assertFalse(self.Eng.get_band(self.emp18, self.today))
        # no birthday → no band, but a no_birthday violation in check_period
        self.assertFalse(self.Eng.get_band(self.emp_none, self.today))
        viols = self.Eng.check_period(self.emp_none, self.today, self.today)
        self.assertTrue(any(v['kind'] == 'no_birthday' for v in viols))

    # ---------------------------------------------------- §6.2 OT gate (hard)
    def test_02_ot_gate_blocks_minor(self):
        with self.assertRaises(ValidationError):
            self.env['hr.overtime.request'].create({
                'employee_id': self.emp17.id, 'date': self.today,
                'overtime_type': 'weekday', 'planned_hours': 2.0,
                'reason': 'x'})
        # an adult is untouched
        req = self.env['hr.overtime.request'].create({
            'employee_id': self.emp_adult.id, 'date': self.today,
            'overtime_type': 'weekday', 'planned_hours': 2.0, 'reason': 'x'})
        self.assertTrue(req.id)

    # ---------------------------------------------------- §6.3 daily cap (hard)
    def test_03_daily_cap(self):
        d = self.monday
        # 17yo cap 8 (+0.5 grace): 8.6 h raises, 8.4 h passes
        with self.assertRaises(ValidationError):
            self._att(self.emp17, d, 8.6)
        self.assertTrue(self._att(self.emp17, d + timedelta(days=1), 8.4).id)
        # 14yo cap 4 (+0.5): blocked past 4.5 h
        with self.assertRaises(ValidationError):
            self._att(self.emp14, d, 4.6)
        self.assertTrue(self._att(self.emp14, d + timedelta(days=1), 4.4).id)

    # ---------------------------------------------------- §6.4 night gate (hard)
    def test_04_night_gate(self):
        def assign(emp, tmpl, d):
            ci = datetime.combine(d, time(21, 0))
            return self.env['hr.shift.planning'].create({
                'employee_id': emp.id, 'shift_template_id': tmpl.id, 'date': d,
                'start_datetime': ci, 'end_datetime': ci + timedelta(hours=8),
                'state': 'published'})
        with self.assertRaises(ValidationError):
            assign(self.emp17, self.night_tmpl, self.today)
        # a day shift for the minor is fine
        self.assertTrue(assign(self.emp17, self.day_tmpl, self.today).id)
        # an adult may work nights
        self.assertTrue(assign(self.emp_adult, self.night_tmpl, self.today).id)
        # overnight-window math
        self.assertTrue(self.Eng._shift_hits_night(self.night_tmpl, 22.0, 6.0))
        self.assertFalse(self.Eng._shift_hits_night(self.day_tmpl, 22.0, 6.0))

    # ---------------------------------------------------- §6.5 weekly cap via grid
    def test_05_weekly_cap_via_grid(self):
        Grid = self.env['hr.attendance.weekentry'].with_user(self.officer)
        # seed Mon–Fri 7 h each = 35 h (each day under the 8.5 daily cap)
        for i in range(5):
            self._att(self.emp17, self.monday + timedelta(days=i), 7.0)
        sat = self.monday + timedelta(days=5)
        # grid flags: is_minor + locked OT measures
        data = Grid.get_week_entries(self.monday.isoformat())
        row = next((r for r in data['rows'] if r['id'] == self.emp17.id), None)
        self.assertTrue(row and row['flags'].get('is_minor'))
        # a weekday cell should carry a locked OT measure
        wk_cell = row['cells'][self.monday.isoformat()]['measures']
        ot_measures = [m for k, m in wk_cell.items() if k != 'reg']
        self.assertTrue(ot_measures and all(not m['editable'] for m in ot_measures))
        # push Saturday REG to 7 h → week would be 42 h → that cell = week_cap
        res = Grid.save_week_entries({'cells': [{
            'rowId': self.emp17.id, 'dayISO': sat.isoformat(),
            'measure': 'reg', 'value': 7.0, 'token': ''}]})
        cell = res['results'][0]
        self.assertFalse(cell['ok'])
        self.assertEqual(cell['error'], 'week_cap')
        # a cell that keeps the week within cap commits (Fri already 7h → set 5h)
        fri = self.monday + timedelta(days=4)
        # Friday has one grid attendance at 7h; token must match
        fdata = Grid.get_week_entries(self.monday.isoformat())
        frow = next(r for r in fdata['rows'] if r['id'] == self.emp17.id)
        ftoken = frow['cells'][fri.isoformat()]['measures']['reg']['token']
        res2 = Grid.save_week_entries({'cells': [{
            'rowId': self.emp17.id, 'dayISO': fri.isoformat(),
            'measure': 'reg', 'value': 5.0, 'token': ftoken}]})
        self.assertTrue(res2['results'][0]['ok'])

    # ---------------------------------------------------- §6.6 check_period feed
    def test_06_check_period(self):
        # week_cap: 6 × 7 h = 42 h (each day passes the daily gate)
        for i in range(6):
            self._att(self.emp17, self.monday + timedelta(days=i), 7.0)
        # historical day_cap / ot / night need the gate off to seed
        self.rule.active = False
        big_day = self.monday + timedelta(days=7)  # next week to isolate
        self._att(self.emp17, big_day, 11.0)
        self.env['hr.overtime.request'].create({
            'employee_id': self.emp17.id, 'date': big_day,
            'overtime_type': 'weekday', 'planned_hours': 2.0, 'reason': 'x'})
        ci = datetime.combine(big_day, time(21, 0))
        self.env['hr.shift.planning'].create({
            'employee_id': self.emp17.id, 'shift_template_id': self.night_tmpl.id,
            'date': big_day, 'start_datetime': ci,
            'end_datetime': ci + timedelta(hours=8), 'state': 'published'})
        self.rule.active = True

        emps = self.emp17 | self.emp_adult | self.emp_none
        viols = self.Eng.check_period(emps, self.monday, big_day)
        kinds = {v['kind'] for v in viols}
        self.assertEqual(kinds, {'week_cap', 'day_cap', 'ot', 'night', 'no_birthday'})
        # adult produces nothing; every hour/ot/night row is the minor's
        self.assertFalse(any(v['employee_id'] == self.emp_adult.id for v in viols))
        # include_no_birthday=False drops the data-quality row
        viols2 = self.Eng.check_period(emps, self.monday, big_day,
                                       include_no_birthday=False)
        self.assertFalse(any(v['kind'] == 'no_birthday' for v in viols2))

    # ---------------------------------------------------- §6.7 payroll advisory
    def test_07_payroll_append_preserves_super(self):
        for i in range(6):
            self._att(self.emp17, self.monday + timedelta(days=i), 7.0)
        Wiz = self.env['pb.payrun.wizard']
        ds, de = self.monday.isoformat(), (self.monday + timedelta(days=6)).isoformat()
        exceptions = [{'emp': 'Someone', 'why': 'No running contract'}]  # super's own
        Wiz._yw_append_exceptions(exceptions, [self.emp17.id, self.emp_adult.id], ds, de)
        # super's row is preserved AND a young-worker row was appended after it
        self.assertEqual(exceptions[0]['why'], 'No running contract')
        yw = [e for e in exceptions if e['why'].startswith('Young worker:')]
        self.assertTrue(yw)
        self.assertTrue(any('week' in e['why'].lower() for e in yw))
        # the wrapper never raises and returns a dict on the base path
        out = Wiz.create_and_compute({'name': 'T', 'date_start': ds, 'date_end': de})
        self.assertIsInstance(out, dict)

    # ---------------------------------------------------- §6.8 config integrity
    def test_08_config_integrity(self):
        # overlapping bands rejected
        with self.assertRaises(ValidationError):
            self.env['pb.young.worker.rule'].create({
                'name': 'Bad', 'company_id': self.company.id,
                'band_ids': [
                    (0, 0, {'age_min': 0, 'age_max': 16, 'max_hours_day': 4,
                            'max_hours_week': 20}),
                    (0, 0, {'age_min': 15, 'age_max': 18, 'max_hours_day': 8,
                            'max_hours_week': 40}),
                ]})
        # age_min >= age_max rejected
        with self.assertRaises(ValidationError):
            self.env['pb.young.worker.rule'].create({
                'name': 'Bad2', 'company_id': self.company.id,
                'band_ids': [(0, 0, {'age_min': 18, 'age_max': 15,
                                     'max_hours_day': 8, 'max_hours_week': 40})]})
        # per-company isolation: a company with no rule = no gates
        co_b = self.env['res.company'].create({'name': 'CoB'})
        emp_b = self.env['hr.employee'].create({
            'name': 'Minor B', 'company_id': co_b.id, 'tz': 'UTC',
            'birthday': self.today - relativedelta(years=16)})
        self.assertFalse(self.Eng.get_band(emp_b, self.today))
        # an OT request for CoB's minor is NOT blocked (no rule there)
        req = self.env['hr.overtime.request'].create({
            'employee_id': emp_b.id, 'date': self.today,
            'overtime_type': 'weekday', 'planned_hours': 2.0, 'reason': 'x',
            'company_id': co_b.id})
        self.assertTrue(req.id)

    # ---------------------------------------------------- §6.9 payroll MRO
    def test_09_payroll_wrapper_is_mro_outer(self):
        """The advisory wrapper must sit OUTSIDE pb_demo in the MRO, or the demo
        division path (which doesn't call super) skips it entirely (§2 ⚠)."""
        mro = type(self.env['pb.payrun.wizard']).mro()
        mods = [getattr(c, '__module__', '') for c in mro]
        yw = next((i for i, m in enumerate(mods) if 'pb_young_worker' in m), None)
        demo = next((i for i, m in enumerate(mods) if 'pb_demo' in m), None)
        self.assertIsNotNone(yw, "pb_young_worker payrun wrapper missing from MRO")
        if demo is not None:
            self.assertLess(
                yw, demo,
                "pb_young_worker must be MRO-outer of pb_demo so super() wraps "
                "the demo division path (add pb_demo to depends if this fails)")

    # ---------------------------------------------------- §6.10 adults untouched
    def test_10_adults_untouched(self):
        # 12 h day for a 30-year-old: no band, no constraint fires
        att = self._att(self.emp_adult, self.today, 12.0)
        self.assertTrue(att.id)
        # night shift, weekday OT — all fine for the adult
        req = self.env['hr.overtime.request'].create({
            'employee_id': self.emp_adult.id, 'date': self.today,
            'overtime_type': 'weekday', 'planned_hours': 4.0, 'reason': 'x'})
        self.assertTrue(req.id)
        self.assertFalse(self.Eng.check_period(self.emp_adult, self.today, self.today))
