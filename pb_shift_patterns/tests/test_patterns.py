# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WDGAP S5-C — rotating shift patterns: the numbered tests of the report.

T1  two teams, a two-week day/night cycle, three weeks across a month end
T2  four teams on "4 on, 4 off" (8-day cycle): every day exactly one team on
    days and one on nights, across a month end
T3  approved leave is skipped and reported; a pending request is not
T4  a public holiday is skipped and reported; "Work on public holidays" fills it
T5  making the drafts again makes no second copy
T6  a draft changed by hand is left alone; a published shift is never touched
T7  a changed cycle replaces only the untouched drafts
T8  somebody who leaves the pattern loses their untouched drafts on the next run
T9  a shift the person already has (made by hand) is an overlap: skipped
T10 the young-worker night ban is skipped, never raised (when configured)
T11 the preview writes nothing and says what "Make drafts" then does
T12 overnight shifts end the next morning; days before today are never filled
T13 rights: officers read, only attendance managers change or make drafts;
    portal users get nothing; another company's pattern is "not there"
T14 drafts never reach My Schedule (the employee sees published shifts only)
T15 save: the cycle, teams and people are replaced whole; bad input refused
T16 empty install: nothing created, the board is quiet
T17 the roster card carries the pattern mark
T18 remove drafts: only untouched ones from today on
"""

from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


TZ = 'Asia/Ho_Chi_Minh'


@tagged('post_install', '-at_install', 'wdgap_s5c')
class TestShiftPatterns(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Board = cls.env['pb.shift.patterns']
        cls.Eng = cls.env['pb.shift.pattern.engine']
        cls.Grid = cls.env['hr.shift.planning.grid']
        cls.company = cls.env.company
        cls.dept = cls.env['hr.department'].create({
            'name': 'S5C Rota Dept', 'company_id': cls.company.id})
        cls.day_t = cls.env['hr.shift.template'].create({
            'name': 'S5C Day', 'code': 'S5CD', 'shift_type': 'morning',
            'start_hour': 7.0, 'end_hour': 15.0, 'break_duration': 0.5,
            'company_id': cls.company.id})
        cls.night_t = cls.env['hr.shift.template'].create({
            'name': 'S5C Night', 'code': 'S5CN', 'shift_type': 'night',
            'start_hour': 19.0, 'end_hour': 7.0, 'break_duration': 0.5,
            'is_overnight': True, 'company_id': cls.company.id})
        cls.late_t = cls.env['hr.shift.template'].create({
            'name': 'S5C Late', 'code': 'S5CL', 'shift_type': 'afternoon',
            'start_hour': 11.0, 'end_hour': 19.0, 'break_duration': 0.5,
            'company_id': cls.company.id})
        cls.people = cls.env['hr.employee'].create([{
            'name': 'DEMO S5C Person %02d' % i, 'department_id': cls.dept.id,
            'company_id': cls.company.id, 'tz': TZ,
        } for i in range(8)])

        # A range of three weeks that crosses the end of a month, well in
        # the future so "never fill the past" never bites by accident.
        month = (date.today() + relativedelta(months=2)).replace(day=1)
        anchor = month - timedelta(days=8)
        cls.first = anchor - timedelta(days=anchor.weekday())
        cls.last = cls.first + timedelta(days=20)
        assert cls.first.month != cls.last.month

        cls.manager = new_test_user(
            cls.env, login='s5c_manager', name='S5C Manager',
            groups='base.group_user,hr_attendance.group_hr_attendance_manager',
            company_id=cls.company.id, company_ids=[cls.company.id])
        cls.officer = new_test_user(
            cls.env, login='s5c_officer', name='S5C Officer',
            groups='base.group_user,hr_attendance.group_hr_attendance_officer',
            company_id=cls.company.id, company_ids=[cls.company.id])
        cls.portal = new_test_user(
            cls.env, login='s5c_portal', name='S5C Portal',
            groups='base.group_portal',
            company_id=cls.company.id, company_ids=[cls.company.id])

    # ------------------------------------------------------------ helpers
    def _as(self, user):
        return self.Board.with_user(user).with_context(
            allowed_company_ids=user.company_ids.ids)

    def _save(self, cycle, slots, teams, members, anchor=None, user=None, **extra):
        vals = {
            'name': extra.pop('name', 'S5C pattern'),
            'department_id': self.dept.id,
            'start_date': (anchor or (self.first - timedelta(days=21))).isoformat(),
            'cycle_days': cycle,
            'slots': [{'day': d, 'template_id': t.id} for d, t in slots.items()],
            'teams': [{'key': 'k%s' % i, 'name': 'Team %s' % 'ABCDEFGH'[i], 'offset': o}
                      for i, o in enumerate(teams)],
            'members': [{'employee_id': e.id, 'team_key': 'k%s' % ti}
                        for e, ti in members],
        }
        vals.update(extra)
        res = self._as(user or self.manager).save_pattern(vals)
        return self.env['pb.shift.pattern'].browse(res['id'])

    def _make(self, pattern, weeks=3, first=None, user=None):
        return self._as(user or self.manager).make_drafts(
            [pattern.id], (first or self.first).isoformat(), weeks)

    def _shifts(self, pattern, states=('draft', 'published', 'completed')):
        return self.env['hr.shift.planning'].search([
            ('pb_pattern_id', '=', pattern.id), ('state', 'in', list(states))])

    def _expected(self, pattern, offset, day):
        return pattern._pb_slot_map().get(pattern._pb_cycle_index(day, offset))

    def _two_crew(self, members=None):
        slots = {d: self.day_t for d in range(0, 5)}
        slots.update({d: self.night_t for d in range(7, 12)})
        members = members or [(self.people[0], 0), (self.people[1], 0),
                              (self.people[2], 1), (self.people[3], 1)]
        return self._save(14, slots, [0, 7], members)

    def _leave_type(self):
        ltype = self.env['hr.leave.type'].sudo().search(
            [('requires_allocation', '=', False)], limit=1)
        if not ltype:
            ltype = self.env['hr.leave.type'].sudo().create({
                'name': 'S5C Probe Leave', 'requires_allocation': False})
        return ltype

    def _leave(self, emp, day, state):
        lv = self.env['hr.leave'].sudo().create({
            'name': 'S5C leave', 'employee_id': emp.id,
            'holiday_status_id': self._leave_type().id,
            'request_date_from': day, 'request_date_to': day})
        lv.sudo().write({'state': state})
        return lv

    def _holiday(self, day, name='S5C Founding Day'):
        """A company closure on `day` (local), the century-out create trick
        `pb.holidays` uses so no create-time conversion can shift it."""
        import pytz
        tz = pytz.timezone(TZ)
        lo = tz.localize(datetime.combine(day, datetime.min.time())).astimezone(pytz.UTC)
        hi = tz.localize(datetime.combine(day, datetime.max.time())).astimezone(pytz.UTC)
        lo, hi = lo.replace(tzinfo=None, microsecond=0), hi.replace(tzinfo=None, microsecond=0)
        far = relativedelta(years=100)
        row = self.env['resource.calendar.leaves'].sudo().create({
            'name': name, 'calendar_id': self.company.resource_calendar_id.id,
            'company_id': self.company.id, 'time_type': 'leave',
            'date_from': lo + far, 'date_to': hi + far})
        row.write({'date_from': lo, 'date_to': hi})
        return row

    # ================================================================ T1
    def test_t1_two_teams_swap_days_and_nights_across_a_month_end(self):
        pattern = self._two_crew()
        res = self._make(pattern)
        shifts = self._shifts(pattern)
        # 3 weeks x 5 working days x 4 people
        self.assertEqual(res['created'], 60)
        self.assertEqual(len(shifts), 60)
        self.assertEqual(res['skipped_total'], 0)
        teams = {m.employee_id.id: m.team_id.offset_days for m in pattern.member_ids}
        for s in shifts:
            self.assertEqual(s.state, 'draft')
            self.assertEqual(s.shift_template_id,
                             self._expected(pattern, teams[s.employee_id.id], s.date))
            self.assertTrue(s._pb_pattern_untouched())
        # the two teams are never on the same shift on the same day
        by_day = {}
        for s in shifts:
            by_day.setdefault(s.date, set()).add((teams[s.employee_id.id], s.shift_template_id.id))
        for day, pairs in by_day.items():
            templates_by_team = {}
            for off, tid in pairs:
                templates_by_team.setdefault(off, set()).add(tid)
            if len(templates_by_team) == 2:
                self.assertFalse(templates_by_team[0] & templates_by_team[7], day)
        months = {s.date.month for s in shifts}
        self.assertEqual(len(months), 2, 'the range crosses a month end')
        self.assertEqual(pattern.last_made_to, self.last)

    # ================================================================ T2
    def test_t2_four_teams_four_on_four_off(self):
        slots = {0: self.day_t, 1: self.day_t, 2: self.night_t, 3: self.night_t}
        members = [(self.people[i], i // 2) for i in range(8)]   # 2 people a team
        pattern = self._save(8, slots, [0, 2, 4, 6], members)
        self._make(pattern)
        shifts = self._shifts(pattern)
        for i in range(21):
            day = self.first + timedelta(days=i)
            on_day = shifts.filtered(lambda s: s.date == day)
            self.assertEqual(len(on_day.filtered(lambda s: s.shift_template_id == self.day_t)), 2,
                             '%s: one team (2 people) on days' % day)
            self.assertEqual(len(on_day.filtered(lambda s: s.shift_template_id == self.night_t)), 2,
                             '%s: one team (2 people) on nights' % day)
        # every person works 4 days in every 8: 8 in the first 16 days, and
        # 1 to 4 in the last 5
        for emp in self.people:
            n = len(shifts.filtered(lambda s: s.employee_id == emp))
            self.assertTrue(9 <= n <= 12, '%s worked %s days' % (emp.name, n))
        self.assertEqual({s.date.month for s in shifts},
                         {self.first.month, self.last.month})

    # ================================================================ T3
    def test_t3_approved_leave_is_skipped_and_reported(self):
        pattern = self._two_crew()
        a_day = next(self.first + timedelta(days=i) for i in range(21)
                     if self._expected(pattern, 0, self.first + timedelta(days=i)))
        self._leave(self.people[0], a_day, 'validate')
        self._leave(self.people[1], a_day, 'confirm')
        res = self._make(pattern)
        self.assertEqual(res['created'], 59)
        self.assertEqual(res['counts'].get('leave_approved'), 1)
        row = res['skipped'][0]
        self.assertEqual(row['employee_id'], self.people[0].id)
        self.assertEqual(row['date'], a_day.isoformat())
        self.assertIn('approved leave', row['reasons'][0])
        self.assertTrue(self._shifts(pattern).filtered(
            lambda s: s.employee_id == self.people[1] and s.date == a_day),
            'a pending request does not stop a shift (Copy Week rule)')

    # ================================================================ T4
    def test_t4_public_holiday_is_skipped_unless_worked(self):
        pattern = self._two_crew()
        work_days = [self.first + timedelta(days=i) for i in range(21)
                     if self._expected(pattern, 0, self.first + timedelta(days=i))]
        self._holiday(work_days[2])
        res = self._make(pattern)
        # team A: 2 people, team B is off or on? count both teams on that day
        on_that_day = sum(1 for m in pattern.member_ids
                          if self._expected(pattern, m.team_id.offset_days, work_days[2]))
        self.assertEqual(res['counts'].get('holiday'), on_that_day)
        self.assertEqual(res['created'], 60 - on_that_day)
        self.assertIn('S5C Founding Day', res['skipped'][0]['reasons'][0])
        self.assertFalse(self._shifts(pattern).filtered(lambda s: s.date == work_days[2]))

        pattern.work_on_holidays = True
        res = self._make(pattern)
        self.assertEqual(res['created'], on_that_day)
        self.assertNotIn('holiday', res['counts'])

    # ================================================================ T5
    def test_t5_making_again_never_duplicates(self):
        pattern = self._two_crew()
        self._make(pattern)
        ids = set(self._shifts(pattern).ids)
        res = self._make(pattern)
        self.assertEqual(res['created'], 0)
        self.assertEqual(res['removed'], 0)
        self.assertEqual(res['kept_same'], 60)
        self.assertEqual(set(self._shifts(pattern).ids), ids, 'the very same rows')
        # a wider second run only adds the new week
        res = self._make(pattern, weeks=4)
        self.assertEqual(res['kept_same'], 60)
        self.assertEqual(res['created'], 20)

    # ================================================================ T6
    def test_t6_edited_drafts_and_published_shifts_are_left_alone(self):
        pattern = self._two_crew()
        self._make(pattern)
        shifts = self._shifts(pattern).sorted('date')
        edited, published = shifts[0], shifts[1]
        start, end = self.Grid._pb_shift_window(self.late_t, edited.date, TZ)
        edited.write({'shift_template_id': self.late_t.id,
                      'start_datetime': start, 'end_datetime': end})
        published.action_publish()
        self.assertFalse(edited._pb_pattern_untouched())
        res = self._make(pattern)
        self.assertEqual(res['created'], 0)
        self.assertEqual(res['removed'], 0)
        self.assertEqual(res['kept_published'], 1)
        self.assertEqual(res['kept_edited_total'], 1)
        self.assertEqual(edited.shift_template_id, self.late_t, 'not reverted')
        self.assertEqual(published.state, 'published')
        self.assertEqual(len(self._shifts(pattern)), 60)

    # ================================================================ T7
    def test_t7_changed_cycle_replaces_untouched_drafts_only(self):
        pattern = self._two_crew()
        self._make(pattern)
        keep = self._shifts(pattern).filtered(
            lambda s: s.shift_template_id == self.day_t).sorted('date')[0]
        keep.action_publish()
        # nights become lates
        detail = self._as(self.manager).get_pattern(pattern.id)
        detail['slots'] = [dict(s, template_id=self.late_t.id)
                           if s['template_id'] == self.night_t.id else s
                           for s in detail['slots']]
        self._as(self.manager).save_pattern(detail, pattern.id)
        res = self._make(pattern)
        nights = self._shifts(pattern).filtered(lambda s: s.shift_template_id == self.night_t)
        self.assertEqual(len(nights.filtered(lambda s: s.state == 'draft')), 0)
        self.assertEqual(res['removed'], 30)
        self.assertEqual(res['created'], 30)
        self.assertEqual(keep.exists().state, 'published')
        self.assertEqual(len(self._shifts(pattern)), 60)

    # ================================================================ T8
    def test_t8_leaving_the_pattern_removes_untouched_drafts(self):
        pattern = self._two_crew()
        self._make(pattern)
        detail = self._as(self.manager).get_pattern(pattern.id)
        detail['members'] = [m for m in detail['members']
                             if m['employee_id'] != self.people[3].id]
        self._as(self.manager).save_pattern(detail, pattern.id)
        res = self._make(pattern)
        self.assertEqual(res['removed'], 15)
        self.assertFalse(self._shifts(pattern).filtered(
            lambda s: s.employee_id == self.people[3]))

    # ================================================================ T9
    def test_t9_a_shift_already_there_is_an_overlap(self):
        pattern = self._two_crew()
        day = next(self.first + timedelta(days=i) for i in range(21)
                   if self._expected(pattern, 0, self.first + timedelta(days=i)) == self.day_t)
        start, end = self.Grid._pb_shift_window(self.late_t, day, TZ)
        own = self.env['hr.shift.planning'].create({
            'employee_id': self.people[0].id, 'shift_template_id': self.late_t.id,
            'date': day, 'start_datetime': start, 'end_datetime': end})
        res = self._make(pattern)
        self.assertEqual(res['counts'].get('overlap'), 1)
        self.assertEqual(res['created'], 59)
        self.assertTrue(own.exists())

    # ================================================================ T10
    def test_t10_young_worker_night_is_skipped_not_raised(self):
        if 'pb.young.worker' not in self.env:
            self.skipTest('pb_young_worker is not installed')
        YW = self.env['pb.young.worker'].sudo()
        if not YW._has_any_rule():
            self.skipTest('no young-worker rule on this database')
        minor = self.env['hr.employee'].create({
            'name': 'DEMO S5C Minor', 'company_id': self.company.id, 'tz': TZ,
            'birthday': date.today() - timedelta(days=365 * 16 + 30)})
        band = YW.get_band(minor, self.first)
        rule = YW._rule_for_company(minor.company_id)
        if not (band and band.night_blocked and rule
                and YW._shift_hits_night(self.night_t, rule.night_from, rule.night_to)):
            self.skipTest('the configured rule does not block this night shift')
        pattern = self._two_crew(members=[(minor, 0)])
        res = self._make(pattern)
        # Team A: nights in weeks 1 and 3, days in week 2
        self.assertEqual(res['counts'].get('young_worker_night'), 10)
        self.assertEqual(res['created'], 5)
        self.assertTrue(all(r['severity'] == 'block' for r in res['skipped']))

    # ================================================================ T11
    def test_t11_preview_writes_nothing(self):
        pattern = self._two_crew()
        Shift = self.env['hr.shift.planning']
        before = Shift.search_count([])
        pre = self._as(self.manager).preview([pattern.id], self.first.isoformat(), 3)
        self.assertEqual(Shift.search_count([]), before)
        self.assertFalse(pattern.last_made_to)
        self.assertEqual(pre['created'], 60)
        self.assertFalse(pre['done'])
        res = self._make(pattern)
        self.assertEqual(res['created'], pre['created'])
        self.assertTrue(res['done'])
        self.assertTrue(pre['first_label'] and pre['last_label'])

    # ================================================================ T12
    def test_t12_overnight_and_never_the_past(self):
        pattern = self._two_crew()
        self._make(pattern)
        night = self._shifts(pattern).filtered(lambda s: s.shift_template_id == self.night_t)[:1]
        self.assertTrue(night)
        self.assertGreater(night.end_datetime, night.start_datetime)
        self.assertEqual((night.end_datetime - night.start_datetime), timedelta(hours=12))

        today = fields.Date.context_today(self.env['hr.shift.planning'])
        # a daily pattern this week: nothing before today
        daily = self._save(1, {0: self.day_t}, [0], [(self.people[5], 0)], anchor=today,
                           name='S5C daily')
        res = self._make(daily, weeks=1, first=today)
        made = self._shifts(daily)
        self.assertTrue(all(s.date >= today for s in made))
        self.assertEqual(res['created'], 7 - today.weekday())
        self.assertEqual(res['past'], today.weekday())

    # ================================================================ T13
    def test_t13_rights(self):
        pattern = self._two_crew()
        # officer: reads
        board = self._as(self.officer).get_board()
        self.assertTrue(board['allowed'])
        self.assertFalse(board['can_edit'])
        self.assertEqual(self._as(self.officer).get_pattern(pattern.id)['id'], pattern.id)
        # ...but never changes or makes
        for call in (
                lambda b: b.save_pattern({'name': 'x', 'cycle_days': 7,
                                          'start_date': self.first.isoformat(),
                                          'teams': [{'key': 'a', 'offset': 0}]}),
                lambda b: b.make_drafts([pattern.id], self.first.isoformat(), 1),
                lambda b: b.preview([pattern.id], self.first.isoformat(), 1),
                lambda b: b.archive_pattern(pattern.id),
                lambda b: b.clear_drafts(pattern.id)):
            with self.assertRaises(AccessError):
                call(self._as(self.officer))
        with self.assertRaises(AccessError):
            self.env['pb.shift.pattern'].with_user(self.officer).create({
                'name': 'nope', 'cycle_days': 7, 'start_date': self.first})
        # portal: nothing at all
        self.assertFalse(self._as(self.portal).get_board()['allowed'])
        with self.assertRaises(AccessError):
            self._as(self.portal).get_pattern(pattern.id)
        with self.assertRaises(AccessError):
            self.env['pb.shift.pattern'].with_user(self.portal).search([])
        self.assertEqual(self._as(self.portal).get_page()['rows'], [])
        # another company's pattern is "not there"
        other = self.env['res.company'].create({'name': 'S5C Other Co'})
        foreign = self.env['pb.shift.pattern'].create({
            'name': 'S5C foreign', 'company_id': other.id, 'cycle_days': 7,
            'start_date': self.first})
        self.env.flush_all()
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            self._as(self.manager).get_pattern(foreign.id)
        with self.assertRaises(UserError):
            self._as(self.manager).make_drafts([foreign.id], self.first.isoformat(), 1)
        ids = [r['id'] for r in self._as(self.manager).get_page()['rows']]
        self.assertIn(pattern.id, ids)
        self.assertNotIn(foreign.id, ids)

    # ================================================================ T14
    def test_t14_drafts_never_reach_my_schedule(self):
        if 'pb.ess.workforce' not in self.env:
            self.skipTest('pb_ess_workforce is not installed')
        today = fields.Date.context_today(self.env['hr.shift.planning'])
        monday = today - timedelta(days=today.weekday())
        worker = new_test_user(self.env, login='s5c_worker', name='S5C Worker',
                               groups='base.group_portal',
                               company_id=self.company.id, company_ids=[self.company.id])
        self.people[6].user_id = worker
        pattern = self._save(1, {0: self.day_t}, [0], [(self.people[6], 0)],
                             anchor=monday, name='S5C mine')
        res = self._make(pattern, weeks=2, first=monday)
        self.assertGreater(res['created'], 0)
        data = self.env['pb.ess.workforce'].with_user(worker).get_my_schedule(
            monday.isoformat())
        cards = [c for w in data['weeks'] for d in w['days'] for c in d['shifts']]
        self.assertEqual(cards, [], 'drafts stay with the planner')
        self._shifts(pattern)[:1].action_publish()
        data = self.env['pb.ess.workforce'].with_user(worker).get_my_schedule(
            monday.isoformat())
        cards = [c for w in data['weeks'] for d in w['days'] for c in d['shifts']]
        self.assertEqual(len(cards), 1, 'only once published')

    # ================================================================ T15
    def test_t15_save_replaces_whole_and_refuses_bad_input(self):
        pattern = self._two_crew()
        detail = self._as(self.manager).get_pattern(pattern.id)
        self.assertEqual(len(detail['slots']), 10)
        self.assertEqual(len(detail['teams']), 2)
        self.assertEqual(len(detail['members']), 4)
        # shrinking the cycle drops the slots past its end
        detail['cycle_days'] = 7
        detail['teams'] = [{'key': 'a', 'name': 'Team A', 'offset': 0}]
        detail['members'] = [dict(m, team_key='a') for m in detail['members']]
        self._as(self.manager).save_pattern(detail, pattern.id)
        pattern.invalidate_recordset()
        self.assertEqual(len(pattern.slot_ids), 5)
        self.assertEqual(len(pattern.team_ids), 1)
        self.assertEqual(len(pattern.member_ids), 4)
        bad = [
            dict(detail, name=''),
            dict(detail, cycle_days=0),
            dict(detail, cycle_days=99),
            dict(detail, teams=[]),
            dict(detail, teams=[{'key': 'a', 'offset': 7}]),
            dict(detail, members=detail['members'] + [detail['members'][0]]),
        ]
        for i, vals in enumerate(bad):
            refused = False
            try:                        # assertRaises takes no tuple (W2M-2)
                with self.env.cr.savepoint():
                    self._as(self.manager).save_pattern(vals, pattern.id)
            except (UserError, ValidationError):
                refused = True
            self.assertTrue(refused, 'bad input %s was accepted' % i)
        other = self.env['res.company'].create({'name': 'S5C Other Co 2'})
        stranger = self.env['hr.employee'].create({'name': 'DEMO S5C Stranger',
                                                   'company_id': other.id})
        with self.assertRaises(UserError):
            self._as(self.manager).save_pattern(
                dict(detail, members=[{'employee_id': stranger.id, 'team_key': 'a'}]),
                pattern.id)

    # ================================================================ T17
    def test_t17_the_roster_card_carries_the_mark(self):
        pattern = self._two_crew()
        self._make(pattern)
        # read as the administrator: the roster read needs HR rights on
        # employees a bare attendance manager does not hold (pre-existing)
        data = self.Grid.with_user(self.env.ref('base.user_admin')).get_schedule_data(
            self.first.isoformat(), department_id=self.dept.id)
        cards = [c for row in data['employees'] for cs in row['shifts'].values() for c in cs]
        self.assertTrue(cards)
        self.assertTrue(all(c['pattern'] == 'S5C pattern' for c in cards))

    # ================================================================ T18
    def test_t18_remove_drafts_keeps_edited_and_published(self):
        pattern = self._two_crew()
        self._make(pattern)
        shifts = self._shifts(pattern).sorted('date')
        shifts[0].action_publish()
        shifts[1].note = 'kept'   # a note is not part of the fingerprint
        start, end = self.Grid._pb_shift_window(self.late_t, shifts[2].date, TZ)
        shifts[2].write({'shift_template_id': self.late_t.id,
                         'start_datetime': start, 'end_datetime': end})
        res = self._as(self.manager).clear_drafts(pattern.id)
        self.assertEqual(res['removed'], 58)
        self.assertEqual(res['kept_edited'], 1)
        self.assertEqual(len(self._shifts(pattern)), 2)


@tagged('post_install', '-at_install', 'wdgap_s5c')
class TestEmptyInstall(TransactionCase):
    """T16 — a new module installs with empty boards and nothing switched on."""

    def test_t16_nothing_is_created_and_the_board_is_quiet(self):
        Data = self.env['ir.model.data']
        made = Data.search([('module', '=', 'pb_shift_patterns')])
        self.assertFalse(made.filtered(lambda d: d.model in (
            'ir.cron', 'mail.template', 'pb.shift.pattern', 'hr.shift.planning',
            'hr.shift.template', 'ir.ui.menu')),
            'no job, no email, no demo rows, no menu')
        board = self.env['pb.shift.patterns'].with_user(
            self.env.ref('base.user_admin')).get_board()
        self.assertTrue(board['allowed'])
        mine = self.env['pb.shift.pattern'].search([])
        if not mine:
            self.assertEqual(board['kpis']['patterns'], 0)
            self.assertEqual(board['kpis']['drafts'], 0)
        self.assertFalse(self.env['hr.shift.planning'].search_count(
            [('pb_pattern_id', '!=', False)]) and not mine)
