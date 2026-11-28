# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for Phase E — Young Worker Rules (§6 cases 1–10).

The live gates BLOCK creating violating data (that's the point), so historical
breaches for check_period are seeded with the rule momentarily deactivated.
"""

from datetime import datetime, date, time, timedelta
from unittest.mock import patch

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

    def test_05b_over_cap_week_stays_reducible(self):
        """Review fix F2 — an already-over-cap week (historic, pre-rule) must be
        walkable DOWN through the grid: only a positive delta is gated."""
        Grid = self.env['hr.attendance.weekentry'].with_user(self.officer)
        for i in range(5):
            self._att(self.emp17, self.monday + timedelta(days=i), 7.0)
        sat = self.monday + timedelta(days=5)
        # seed the breach with the gate off: Sat 10 h → week 45 h (cap 40)
        self.rule.active = False
        self._att(self.emp17, sat, 10.0)
        self.rule.active = True
        data = Grid.get_week_entries(self.monday.isoformat())
        row = next(r for r in data['rows'] if r['id'] == self.emp17.id)
        token = row['cells'][sat.isoformat()]['measures']['reg']['token']
        # reducing Sat 10 → 8 leaves the week over cap (43 h) but MUST commit
        res = Grid.save_week_entries({'cells': [{
            'rowId': self.emp17.id, 'dayISO': sat.isoformat(),
            'measure': 'reg', 'value': 8.0, 'token': token}]})
        self.assertTrue(res['results'][0]['ok'],
                        "a corrective reduction may never be week_cap-blocked")
        # while a further INCREASE on the over-cap week is still refused
        data2 = Grid.get_week_entries(self.monday.isoformat())
        row2 = next(r for r in data2['rows'] if r['id'] == self.emp17.id)
        token2 = row2['cells'][sat.isoformat()]['measures']['reg']['token']
        res2 = Grid.save_week_entries({'cells': [{
            'rowId': self.emp17.id, 'dayISO': sat.isoformat(),
            'measure': 'reg', 'value': 8.4, 'token': token2}]})
        self.assertFalse(res2['results'][0]['ok'])
        self.assertEqual(res2['results'][0]['error'], 'week_cap')

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
        # a company created after install is auto-seeded (never silently ungated)
        co_b = self.env['res.company'].create({'name': 'CoB'})
        Rule = self.env['pb.young.worker.rule'].sudo().with_context(active_test=False)
        seeded = Rule.search([('company_id', '=', co_b.id)])
        self.assertTrue(seeded, "a new company must get the VN default rule")
        # re-seeding respects a deliberate opt-out: deactivate → seed creates nothing
        seeded.write({'active': False})
        self.assertFalse(Rule._seed_vn_defaults(co_b))
        # per-company isolation: with its rule deactivated, CoB has no gates
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

    # ------------------------------------------- §6.9 the payroll advisory paths
    #
    # WHAT THIS USED TO ASSERT, AND WHY IT WAS WRONG (P7 WP-1).
    #
    # `test_09_payroll_wrapper_is_mro_outer` asserted
    # `mro.index(pb_young_worker) < mro.index(pb_demo)` — "we sit outside the
    # demo module, so our super() wraps its division path". Two things were
    # wrong with it. The measured order is the OPPOSITE
    # (`pb_demo -> pb_close -> pb_young_worker -> pb_payrun_wizard`: none of the
    # four declares a dependency on another, so their relative order is Odoo's
    # `(depth, name)` accident, and pb_demo happens to load last). And the test
    # could not fail on the machines that ran it, because the whole assertion
    # sat behind `if demo is not None` and CI databases install pb_young_worker
    # without pb_demo — a green test asserting a false thing about a
    # configuration it never saw.
    #
    # What actually makes the advisory reach a payroll run is TWO different
    # mechanisms, and this asserts both of them instead:
    #   * the GENERIC (salary-structure) path calls super, so the classic
    #     append-after-super seam fires — proven end to end, not by index;
    #   * the DEMO division path never calls super, so pb_demo calls the
    #     product's hooks explicitly (`_pb_demo_advisories`, P4). The dependency
    #     direction is deliberate: a production module must not depend on the
    #     demo module to be correct.
    # An MRO INDEX proves neither of them, and would keep passing if both
    # broke.
    def test_09_the_advisory_is_registered_on_both_payroll_seams(self):
        """Registration, on the real registry — the precondition for the seam.

        Asserted as "some class in the wizard's MRO that belongs to this module
        defines this method", which is what "the wrapper is installed" means.
        Position in that list is deliberately NOT asserted: it is an accident of
        load order that nothing declares and nothing needs.
        """
        mro = type(self.env['pb.payrun.wizard']).mro()
        mine = [c for c in mro
                if 'pb_young_worker' in getattr(c, '__module__', '')]
        self.assertTrue(mine, 'the young-worker payrun wrapper is not installed')
        for seam in ('create_and_compute', 'compute_batch'):
            self.assertTrue(
                any(seam in vars(c) for c in mine),
                'the young-worker advisory does not wrap %s' % seam)

    def test_09b_the_generic_path_appends_after_super(self):
        """The append-after-super seam, end to end through `compute_batch`.

        The payload carries a minor with a week over the cap and no running
        contract, so the BASE implementation appends its own row first and the
        wrapper appends after it. Both must be present: an advisory that
        replaces the run's own exceptions instead of adding to them would pass
        any test that only looked for a young-worker row.
        """
        for i in range(6):
            self._att(self.emp17, self.monday + timedelta(days=i), 7.0)
        Wiz = self.env['pb.payrun.wizard'].sudo()
        out = Wiz.compute_batch({
            'run_id': False, 'name': 'P7 advisory probe',
            'date_start': self.monday.isoformat(),
            'date_end': (self.monday + timedelta(days=6)).isoformat(),
            'emp_ids': [self.emp17.id, self.emp_adult.id],
        })
        self.assertIn('exceptions', out)
        whys = [r['why'] for r in out['exceptions']]
        self.assertTrue(
            any(w.startswith('Young worker:') for w in whys),
            'the advisory never reached the generic path: %s' % whys)
        self.assertTrue(
            any('No running contract' in w for w in whys),
            "the run's own exceptions were lost — the wrapper replaced the "
            'list instead of appending to it: %s' % whys)

    def test_09c_the_demo_division_path_reaches_us_by_explicit_hook(self):
        """The demo path, asserted through the MECHANISM rather than the source.

        `pb_demo` short-circuits `compute_batch` / `create_and_compute` for a
        division run and returns without calling super, so no wrapper below it
        ever runs. P4's answer was for the DEMO to call the product's advisory
        hooks by name. This calls that hook exactly as the division path does
        and asserts our rows come out of it — which is the only thing that would
        still be true after somebody renames `_yw_append_exceptions`.
        """
        Wiz = self.env['pb.payrun.wizard'].sudo()
        hook = getattr(Wiz, '_pb_demo_advisories', None)
        if hook is None:
            self.skipTest('pb_demo is not installed on this database')
        for i in range(6):
            self._att(self.emp17, self.monday + timedelta(days=i), 7.0)
        seeded = [{'emp': 'Someone', 'why': 'No running contract'}]
        hook(seeded, [self.emp17.id],
             self.monday.isoformat(),
             (self.monday + timedelta(days=6)).isoformat())
        self.assertEqual(seeded[0]['why'], 'No running contract',
                         'the demo hook must append, never rebuild')
        self.assertTrue(
            any(r['why'].startswith('Young worker:') for r in seeded),
            'the demo division path shows no young-worker warning: %s' % seeded)

    def test_09d_the_advisory_can_never_break_a_payroll_run(self):
        """The cardinal rule for anything riding this seam. The failure is
        INJECTED rather than imagined: a bad week of data must cost a warning,
        never the run."""
        Wiz = self.env['pb.payrun.wizard'].sudo()
        payload = {
            'run_id': False, 'name': 'P7 advisory probe',
            'date_start': self.monday.isoformat(),
            'date_end': (self.monday + timedelta(days=6)).isoformat(),
            'emp_ids': [self.emp17.id],
        }
        with patch.object(type(Wiz), '_yw_append_exceptions',
                          side_effect=RuntimeError('advisory exploded')):
            try:
                out = Wiz.compute_batch(payload)
            except RuntimeError:
                self.fail('the young-worker advisory raised into a payroll run')
        self.assertIsInstance(out, dict)
        self.assertIn('exceptions', out)

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
