# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Workforce P2 — T4/T5: edit-time warnings and refuse-on-paste.

Two PARITY assertions carry most of the weight here, because a warning that
disagrees with the rule it is warning about is worse than no warning:

  * `young_worker_night` must fire exactly when `pb_young_worker`'s
    ValidationError fires. The test proves both halves on the same data — the
    warning says `block`, AND the create really is refused — and skips
    gracefully when the module is not installed;
  * `ot_ceiling` must use the SAME 90% threshold as the Overtime Desk's
    red-pulse KPI (`ot_desk.py`:184: `used >= 0.9 * cap`), through the same
    supported payload (`get_ot_ceilings`) rather than the private
    `pb.ot.ceiling` helpers.

Everything runs inside the TransactionCase rollback: nothing survives on the
live database.
"""

from datetime import date, timedelta

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestScheduleWarnings(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Grid = cls.env['hr.shift.planning.grid']
        cls.company = cls.env.company
        cls.dept = cls.env['hr.department'].create({
            'name': 'P2 Warn Dept', 'company_id': cls.company.id})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'P2 Warn Probe', 'department_id': cls.dept.id,
            'company_id': cls.company.id})
        cls.day_t = cls.env['hr.shift.template'].create({
            'name': 'P2 Warn Day', 'code': 'P2WD', 'shift_type': 'morning',
            'start_hour': 8.0, 'end_hour': 16.0, 'break_duration': 0.0,
            'company_id': cls.company.id})
        cls.late_t = cls.env['hr.shift.template'].create({
            'name': 'P2 Warn Late', 'code': 'P2WL', 'shift_type': 'afternoon',
            'start_hour': 14.0, 'end_hour': 22.0, 'break_duration': 0.0,
            'company_id': cls.company.id})
        cls.night_t = cls.env['hr.shift.template'].create({
            'name': 'P2 Warn Night', 'code': 'P2WN', 'shift_type': 'night',
            'start_hour': 22.0, 'end_hour': 6.0, 'break_duration': 0.0,
            'is_overnight': True, 'company_id': cls.company.id})
        cls.week = date(2026, 3, 2)
        cls.day = cls.week + timedelta(days=1)

    # ------------------------------------------------------------ helpers
    def _shift(self, emp, day, tmpl, state='published'):
        start, end = self.Grid._pb_shift_window(tmpl, day)
        rec = self.env['hr.shift.planning'].create({
            'employee_id': emp.id, 'shift_template_id': tmpl.id, 'date': day,
            'start_datetime': start, 'end_datetime': end})
        if state != 'draft':
            rec.state = state
        return rec

    def _check(self, emp=None, day=None, tmpl=None, **kw):
        return self.Grid.check_shift(
            (emp or self.emp).id, (day or self.day).isoformat(),
            (tmpl or self.day_t).id, **kw)

    def _codes(self, res):
        return {w['code'] for w in res['warnings']}

    # ---------------------------------------------------------- clean day
    def test_a_clean_shift_produces_no_warnings(self):
        res = self._check()
        self.assertEqual(res['warnings'], [])
        self.assertFalse(res['blocked'])

    # ------------------------------------------------------------ overlap
    def test_an_overlapping_shift_warns(self):
        self._shift(self.emp, self.day, self.day_t)
        res = self._check(tmpl=self.day_t)
        self.assertIn('overlap', self._codes(res))
        self.assertFalse(res['blocked'], 'an overlap is a warning, not a block')

    def test_a_non_overlapping_second_shift_does_not_warn(self):
        """08:00-16:00 then 14:00-22:00 overlaps; 08:00-16:00 alone does not
        conflict with a 22:00 night."""
        self._shift(self.emp, self.day, self.day_t)
        self.assertIn('overlap', self._codes(self._check(tmpl=self.late_t)))
        self.assertNotIn('overlap', self._codes(self._check(tmpl=self.night_t)))

    def test_excluding_a_shift_removes_its_own_overlap(self):
        """Editing an existing shift must not report a conflict with itself."""
        shift = self._shift(self.emp, self.day, self.day_t)
        self.assertIn('overlap', self._codes(self._check(tmpl=self.day_t)))
        res = self._check(tmpl=self.day_t, exclude_shift_id=shift.id)
        self.assertNotIn('overlap', self._codes(res))

    def test_a_cancelled_shift_does_not_conflict(self):
        shift = self._shift(self.emp, self.day, self.day_t)
        shift.state = 'cancelled'
        self.assertNotIn('overlap', self._codes(self._check(tmpl=self.day_t)))

    # -------------------------------------------------------------- leave
    def _leave_type(self):
        """A leave type that needs NO allocation.

        `hr.leave.type.requires_allocation` defaults to True, and this database
        has plenty of such types — `search([], limit=1)` reliably returns one,
        and then `hr.leave.create` raises "You do not have any allocation for
        this time off type". Seeding an allocation would drag the whole
        accrual/validation machine into a roster test; a no-allocation type is
        the same fixture with none of it.
        """
        ltype = self.env['hr.leave.type'].sudo().search(
            [('requires_allocation', '=', False)], limit=1)
        if not ltype:
            ltype = self.env['hr.leave.type'].sudo().create({
                'name': 'P2 Probe Leave', 'requires_allocation': False})
        return ltype

    def _leave(self, state):
        ltype = self._leave_type()
        lv = self.env['hr.leave'].sudo().create({
            'name': 'P2 warn leave', 'employee_id': self.emp.id,
            'holiday_status_id': ltype.id,
            'request_date_from': self.day, 'request_date_to': self.day})
        lv.sudo().write({'state': state})
        return lv

    def test_approved_leave_warns(self):
        self._leave('validate')
        res = self._check()
        self.assertIn('leave_approved', self._codes(res))
        self.assertEqual(
            [w['severity'] for w in res['warnings'] if w['code'] == 'leave_approved'],
            ['warn'])

    def test_a_pending_leave_request_is_info_not_a_warning(self):
        """Refusing a paste on a request nobody has approved yet would make the
        button useless in any team with open requests."""
        self._leave('confirm')
        res = self._check()
        self.assertIn('leave_pending', self._codes(res))
        self.assertEqual(
            [w['severity'] for w in res['warnings'] if w['code'] == 'leave_pending'],
            ['info'])

    # ------------------------------------------------- young worker parity
    def test_the_young_worker_block_matches_the_server_constraint(self):
        if 'pb.young.worker' not in self.env:
            self.skipTest('pb_young_worker is not installed')
        Eng = self.env['pb.young.worker'].sudo()
        if not Eng._has_any_rule():
            self.skipTest('no young-worker rule configured on this database')

        minor = self.env['hr.employee'].create({
            'name': 'P2 Minor Probe', 'department_id': self.dept.id,
            'company_id': self.company.id,
            'birthday': date.today() - timedelta(days=365 * 16 + 30)})
        band = Eng.get_band(minor, self.day)
        if not (band and band.night_blocked):
            self.skipTest('the configured bands do not block night work at 16')
        rule = Eng._rule_for_company(minor.company_id)
        if not (rule and Eng._shift_hits_night(
                self.night_t, rule.night_from, rule.night_to)):
            self.skipTest('the seeded night template does not hit the window')

        res = self._check(emp=minor, tmpl=self.night_t)
        self.assertTrue(res['blocked'], 'the warning must say block')
        self.assertIn('young_worker_night', self._codes(res))

        # …and the server really does refuse it — the two halves of parity
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self._shift(minor, self.day, self.night_t, state='draft')

        # a DAY shift for the same minor is neither blocked nor refused
        self.assertFalse(self._check(emp=minor, tmpl=self.day_t)['blocked'])

    def test_the_probe_degrades_to_silence_without_the_module(self):
        """§3.1: pb_young_worker is NOT a dependency. Absent module, absent
        warning — never an exception."""
        res = self.Grid._pb_young_worker_block(
            self.emp, self.day, self.night_t)
        if 'pb.young.worker' not in self.env:
            self.assertIsNone(res, 'absent module must mean absent warning')
        else:
            # an adult with no band: silence, and above all no exception
            self.assertIsNone(res)

    # -------------------------------------------------- OT ceiling parity
    def test_the_ceiling_warning_uses_the_same_90_percent_as_the_ot_desk(self):
        ceilings = self.Grid._pb_ceilings([self.emp.id], self.day)
        cap = (ceilings.get(self.emp.id) or {}).get('cap_month') or 0.0
        if not cap:
            self.skipTest('no monthly OT cap configured on this database')

        Req = self.env['hr.overtime.request'].sudo()
        # 90% of the cap, dated inside the reference month
        month_day = self.day.replace(day=1) + timedelta(days=5)
        try:
            with self.env.cr.savepoint():
                Req.create({
                    'employee_id': self.emp.id,
                    'date': month_day,
                    'approved_hours': cap * 0.9,
                    'actual_hours': cap * 0.9,
                    'state': 'approved',
                })
        except Exception:
            self.skipTest('hr.overtime.request needs fields this test does not '
                          'know about on this database')

        res = self._check()
        self.assertIn('ot_ceiling', self._codes(res),
                      'at exactly 90% the desk pulses, so the roster warns')
        self.assertFalse(res['blocked'],
                         'ceilings are ADVISORY by design — overflow becomes '
                         'bonus hours, so this may never block')

    # ------------------------------------------------------------ check_day
    def test_check_day_hoists_the_template_independent_warnings(self):
        self._leave('validate')
        res = self.Grid.check_day(
            self.emp.id, self.day.isoformat(),
            [self.day_t.id, self.late_t.id, self.night_t.id])
        codes = {w['code'] for w in res['context']}
        self.assertIn('leave_approved', codes,
                      'a leave warning belongs at the top, stated once')
        for warns in res['by_template'].values():
            self.assertNotIn('leave_approved', {w['code'] for w in warns},
                             'and not repeated on every tile')

    def test_check_day_marks_the_conflicting_template_only(self):
        self._shift(self.emp, self.day, self.day_t)
        res = self.Grid.check_day(
            self.emp.id, self.day.isoformat(),
            [self.day_t.id, self.night_t.id])
        self.assertIn('overlap',
                      {w['code'] for w in res['by_template'][str(self.day_t.id)]})
        self.assertEqual(res['by_template'][str(self.night_t.id)], [])

    # ==================================================== T5: copy week
    def test_copy_week_lands_the_clean_ones_and_refuses_the_rest(self):
        clean = self.env['hr.employee'].create({
            'name': 'P2 Copy Clean', 'department_id': self.dept.id,
            'company_id': self.company.id})
        on_leave = self.env['hr.employee'].create({
            'name': 'P2 Copy OnLeave', 'department_id': self.dept.id,
            'company_id': self.company.id})
        busy = self.env['hr.employee'].create({
            'name': 'P2 Copy Busy', 'department_id': self.dept.id,
            'company_id': self.company.id})

        target_week = self.week + timedelta(days=7)
        target_day = self.day + timedelta(days=7)

        # source: three identical shifts on the same Tuesday
        for emp in (clean, on_leave, busy):
            self._shift(emp, self.day, self.day_t)
        # …and two reasons to refuse in the TARGET week
        ltype = self._leave_type()
        lv = self.env['hr.leave'].sudo().create({
            'name': 'P2 copy leave', 'employee_id': on_leave.id,
            'holiday_status_id': ltype.id,
            'request_date_from': target_day, 'request_date_to': target_day})
        lv.sudo().write({'state': 'validate'})
        self._shift(busy, target_day, self.day_t)

        before = self.env['hr.shift.planning'].search_count([
            ('date', '=', target_day)])
        res = self.Grid.copy_week_checked(
            self.week.isoformat(), target_week.isoformat(), self.dept.id, 7)

        self.assertEqual(res['created'], 1, 'only the clean target may land')
        self.assertEqual(len(res['skipped']), 2)
        skipped = {s['employee_name']: s for s in res['skipped']}
        self.assertIn('P2 Copy OnLeave', skipped)
        self.assertIn('P2 Copy Busy', skipped)
        self.assertTrue(skipped['P2 Copy OnLeave']['reasons'],
                        'a skip report with no reason is not a report')
        self.assertEqual(res['considered'], 3)

        after = self.env['hr.shift.planning'].search_count([
            ('date', '=', target_day)])
        self.assertEqual(after, before + 1)

        landed = self.env['hr.shift.planning'].search([
            ('employee_id', '=', clean.id), ('date', '=', target_day)])
        self.assertEqual(landed.state, 'draft',
                         'a copy is a proposal, never a published commitment')

    def test_copying_twice_does_not_duplicate(self):
        """The legacy loop happily pasted a second identical shift onto the
        same person; the in-flight window list is what stops it."""
        emp = self.env['hr.employee'].create({
            'name': 'P2 Copy Twice', 'department_id': self.dept.id,
            'company_id': self.company.id})
        self._shift(emp, self.day, self.day_t)
        target_week = self.week + timedelta(days=7)
        first = self.Grid.copy_week_checked(
            self.week.isoformat(), target_week.isoformat(), self.dept.id, 7)
        self.assertEqual(first['created'], 1)
        second = self.Grid.copy_week_checked(
            self.week.isoformat(), target_week.isoformat(), self.dept.id, 7)
        self.assertEqual(second['created'], 0)
        self.assertEqual(len(second['skipped']), 1)

    def test_two_source_shifts_for_one_person_do_not_both_land_on_a_clash(self):
        """A paste must be self-consistent: the shift created a moment ago is a
        conflict for the next one in the same loop."""
        emp = self.env['hr.employee'].create({
            'name': 'P2 Copy Self', 'department_id': self.dept.id,
            'company_id': self.company.id})
        # two overlapping source shifts (08-16 and 14-22) on the same day
        self._shift(emp, self.day, self.day_t)
        self._shift(emp, self.day, self.late_t)
        target_week = self.week + timedelta(days=7)
        res = self.Grid.copy_week_checked(
            self.week.isoformat(), target_week.isoformat(), self.dept.id, 7)
        self.assertEqual(res['created'], 1)
        self.assertEqual(len(res['skipped']), 1)

    def test_an_empty_source_span_reports_nothing_rather_than_failing(self):
        empty = self.week + timedelta(days=364)
        res = self.Grid.copy_week_checked(
            empty.isoformat(), (empty + timedelta(days=7)).isoformat(),
            self.dept.id, 7)
        self.assertEqual((res['created'], res['skipped'], res['considered']),
                         (0, [], 0))
