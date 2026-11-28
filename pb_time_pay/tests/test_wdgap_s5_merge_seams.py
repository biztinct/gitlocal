# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP S5 merge seams (the three builders could not see each other).

a. S5-B makes its "Time off in lieu" kind without knowing S5-A's new fields:
   with `pb_leave_setup` installed the kind gets S5-A's defaults, is listed on
   the Kinds of leave screen as "Given by HR", and the build-up engine never
   touches it (owner ruling L4: it never builds up, never runs out).
b. S5-A's "balances ignore days that ran out" + S5-B's in-lieu hours: an
   in-lieu balance is never reduced by expiry, however far ahead we look.
c. S5-C's generated drafts + S5-B's overtime suggestions: a pattern shift that
   is still a DRAFT is not the yardstick (the person's working hours are);
   once it is published it is.

Each seam skips itself when the other builder's module is not installed, so
this file is safe on a database that has `pb_time_pay` alone.
"""

from datetime import date, datetime, time, timedelta

from odoo.tests import tagged

from .common import TimePayCase


@tagged('post_install', '-at_install', 'wdgap_s5m')
class TestS5MergeSeams(TimePayCase):

    def _toil(self, day, hours):
        req = self.OT.sudo().create({
            'employee_id': self.shifty.id, 'date': day,
            'overtime_type': 'weekday', 'planned_hours': hours,
            'actual_hours': hours, 'reason': 'S5M', 'company_id': self.company.id})
        req.action_submit()
        req.with_user(self.manager_user)._pb_set_choice('time_off')
        req.with_user(self.manager_user).action_approve()
        self.assertEqual(req.state, 'approved')
        self.assertTrue(req.pb_toil_allocation_id)
        return req

    # ------------------------------------------------------------------ a
    def test_a_in_lieu_kind_with_leave_setup(self):
        Kind = self.env['hr.leave.type']
        if 'pb_ls_earning' not in Kind._fields:
            self.skipTest('pb_leave_setup is not installed')
        req = self._toil(self.mon, 3.0)
        kind = req.pb_toil_allocation_id.holiday_status_id
        self.assertTrue(kind.pb_toil_kind)
        # S5-A's defaults, nothing required was missing
        self.assertEqual(kind.pb_ls_earning, 'none')
        self.assertFalse(kind.pb_ls_take_ahead)
        self.assertFalse(kind.pb_ls_expire_months)
        self.assertFalse(kind.pb_ls_hr_only)
        self.assertFalse(kind.pb_ls_starter_key)
        self.assertFalse(kind.pb_ls_review)
        self.assertFalse(kind._pb_ls_earns())

        # on the Kinds of leave screen, as a tenant HR manager
        hr = self._mk_user('s5m_hr', ['hr.group_hr_manager'])
        page = self.env['pb.leave.setup'].with_user(hr).with_context(
            allowed_company_ids=[self.company.id]).get_kinds_page(
                search=kind.name, limit=200)
        rows = {r['id']: r for r in page['rows']}
        self.assertIn(kind.id, rows, page)
        row = rows[kind.id]
        self.assertEqual(row['earning'], 'none')
        self.assertEqual(row['earning_label'], 'Given by HR')
        self.assertEqual(row['unit_label'], 'Hours')
        self.assertTrue(row['counted'])
        self.assertEqual(row['state'], 'on')
        self.assertFalse(row['pay_open'], 'paid by the company, decided')
        drawer = self.env['pb.leave.setup'].with_user(hr).with_context(
            allowed_company_ids=[self.company.id]).get_kind(kind.id)
        self.assertTrue(drawer, 'the drawer opens on the in-lieu kind')

        # the build-up engine: never builds up, the allocation is untouched
        alloc = req.pb_toil_allocation_id
        before = (alloc.number_of_days, alloc.number_of_hours_display, alloc.date_to)
        Earn = self.env['pb.leave.earning'].sudo()
        self.assertFalse(dict(Earn._run_kind(kind, date.today() + timedelta(days=400))))
        Earn._run(today=date.today() + timedelta(days=400))
        self.assertFalse(Earn.search([('leave_type_id', '=', kind.id)]),
                         'no build-up row for the in-lieu kind')
        alloc.invalidate_recordset()
        self.assertEqual(
            (alloc.number_of_days, alloc.number_of_hours_display, alloc.date_to), before)
        self.assertFalse(alloc.date_to, 'never runs out (L4)')

    # ------------------------------------------------------------------ b
    def test_b_in_lieu_balance_is_never_reduced_by_expiry(self):
        TO = self.env['pb.timeoff']
        if not hasattr(TO, '_pb_expired_parts'):
            self.skipTest('the S5-A expiry rule is not in pb_timeoff')
        req = self._toil(self.mon, 4.0)
        alloc = req.pb_toil_allocation_id
        kind = alloc.holiday_status_id
        key = (self.shifty.id, kind.id)
        for ahead in (0, 400, 365 * 10):
            today = date.today() + timedelta(days=ahead)
            self.assertEqual(
                TO._pb_expired_parts([self.shifty.id], [kind.id], today=today), {},
                'nothing of the in-lieu kind ever runs out (%s days ahead)' % ahead)
            nums = TO._pb_balance_numbers([self.shifty.id], [kind.id], today=today)
            self.assertIn(key, nums)
            self.assertAlmostEqual(nums[key]['allocated'], alloc.number_of_days, places=4)
            self.assertAlmostEqual(nums[key]['balance'], alloc.number_of_days, places=4)
        # a second in-lieu grant adds up, still nothing runs out
        req2 = self._toil(self.tue, 2.0)
        self.assertEqual(req2.pb_toil_allocation_id.holiday_status_id, kind)
        nums = TO._pb_balance_numbers([self.shifty.id], [kind.id],
                                      today=date.today() + timedelta(days=3650))
        self.assertAlmostEqual(
            nums[key]['balance'],
            alloc.number_of_days + req2.pb_toil_allocation_id.number_of_days, places=4)

    # ------------------------------------------------------------------ c
    def test_c_a_draft_pattern_shift_is_not_the_published_shift(self):
        if 'pb.shift.pattern' not in self.env:
            self.skipTest('pb_shift_patterns is not installed')
        early = self.env['hr.shift.template'].sudo().create({
            'name': 'S5M Early', 'code': 'S5MEARLY', 'start_hour': 6.0,
            'end_hour': 14.0, 'break_duration': 0.0, 'is_overnight': False,
            'shift_type': 'morning', 'company_id': self.company.id})
        # A real pattern makes the draft (the engine never fills the past, so
        # it makes it in a future week; the draft is then moved onto the
        # settled past week the Close reads, keeping its state and its mark).
        future = date.today() + timedelta(days=21)
        future -= timedelta(days=future.weekday())
        Board = self.env['pb.shift.patterns'].with_user(self.manager_user).with_context(
            allowed_company_ids=[self.company.id])
        res = Board.save_pattern({
            'name': 'S5M rota', 'department_id': self.dept.id,
            'start_date': (future - timedelta(days=28)).isoformat(),
            'cycle_days': 7,
            'slots': [{'day': d, 'template_id': early.id} for d in range(7)],
            'teams': [{'key': 'a', 'name': 'Team A', 'offset': 0}],
            'members': [{'employee_id': self.shifty.id, 'team_key': 'a'}],
        })
        pattern = self.env['pb.shift.pattern'].browse(res['id'])
        report = Board.make_drafts([pattern.id], future.isoformat(), 1)
        made = self.env['hr.shift.planning'].sudo().search([
            ('pb_pattern_id', '=', pattern.id)], order='date')
        self.assertTrue(made, report)
        self.assertEqual(set(made.mapped('state')), {'draft'}, 'drafts only')
        draft = made[0]
        shift_hours = (draft.end_datetime - draft.start_datetime)
        start = datetime.combine(self.mon, time(0)) + timedelta(
            hours=draft.start_datetime.hour, minutes=draft.start_datetime.minute)
        (made - draft).unlink()
        draft.write({'date': self.mon, 'start_datetime': start,
                     'end_datetime': start + shift_hours})
        self.assertEqual(draft.state, 'draft')
        self.assertEqual(draft.pb_pattern_id, pattern)

        # 06:00-16:00 punched; the draft says 06:00-14:00, working hours 08-16
        self._punch(self.shifty, self.mon, 6, 16)

        def monday():
            rows, late = self._week(self.shifty)
            sugg = [r for r in rows if r['employee_id'] == self.shifty.id
                    and r['date'] == self.mon.isoformat()]
            lates = [r for r in late if r.get('employee_id') == self.shifty.id
                     and r.get('date') == self.mon.isoformat()]
            return sugg, lates

        sugg, _lates = monday()
        self.assertTrue(sugg, 'punched outside the working hours')
        self.assertEqual({r['basis'] for r in sugg}, {'hours'},
                         'a draft pattern shift is not the yardstick')

        draft.action_publish()
        self.assertEqual(draft.state, 'published')
        sugg, _lates = monday()
        self.assertTrue(sugg)
        self.assertEqual({r['basis'] for r in sugg}, {'shift'},
                         'once published, the pattern shift is the yardstick')
        self.assertEqual(sugg[0]['expected'], 8.0)
