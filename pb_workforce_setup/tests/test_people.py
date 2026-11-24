# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P2 — step 3 "Who works what" (handover §4, cases 1-16).

Case 17 (static gates) lives in test_static.py. Extra cases at the end:
the right panel's default person, and the roster create guard that lets an
attendance manager without HR rights make roster rows once the late-rule
module is installed.
"""

import logging
import time
from datetime import date, datetime, timedelta

import pytz

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

TZ = 'Asia/Ho_Chi_Minh'
_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'wfsetup')
class TestSetupPeople(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'People test company'})
        cls.other = cls.env['res.company'].create({'name': 'Other people company'})
        both = [(6, 0, [cls.company.id, cls.other.id])]
        cls.manager = new_test_user(
            cls.env, login='wfs2_manager',
            groups='hr_attendance.group_hr_attendance_manager,hr.group_hr_manager',
            company_id=cls.company.id, company_ids=both)
        cls.manager2 = new_test_user(
            cls.env, login='wfs2_manager2',
            groups='hr_attendance.group_hr_attendance_manager,hr.group_hr_manager',
            company_id=cls.company.id, company_ids=both)
        # an attendance manager WITHOUT HR rights (the late rule field is HR-only)
        cls.att_only = new_test_user(
            cls.env, login='wfs2_att_only', groups='base.group_user,hr_attendance.group_hr_attendance_manager',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])])
        cls.officer = new_test_user(
            cls.env, login='wfs2_officer', groups='hr_attendance.group_hr_attendance_officer',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])])
        cls.basic = new_test_user(
            cls.env, login='wfs2_basic', groups='base.group_user',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])])
        Shift = cls.env['hr.shift.template']
        cls.day = Shift.create({'name': 'People day', 'code': 'PPD', 'start_hour': 7.5,
                                'end_hour': 16.5, 'break_duration': 1, 'company_id': cls.company.id})
        cls.night = Shift.create({'name': 'People night', 'code': 'PPN', 'start_hour': 22.0,
                                  'end_hour': 6.0, 'break_duration': 0.5, 'is_overnight': True,
                                  'shift_type': 'night', 'company_id': cls.company.id})
        Dept = cls.env['hr.department']
        cls.sanding = Dept.create({'name': 'Sanding', 'company_id': cls.company.id})
        cls.packing = Dept.create({'name': 'Packing', 'company_id': cls.company.id})
        cls.emps = cls.env['hr.employee'].create([{
            'name': 'People %02d' % i, 'company_id': cls.company.id, 'tz': TZ,
            'department_id': (cls.sanding if i < 6 else cls.packing).id,
        } for i in range(10)])
        cls.foreign = cls.env['hr.employee'].create({'name': 'People foreign', 'company_id': cls.other.id})
        cls.gone = cls.env['hr.employee'].create({'name': 'People archived', 'company_id': cls.company.id,
                                                  'active': False})

    # ------------------------------------------------------------ helpers
    def facade(self, user=None):
        self.env.flush_all()
        self.env.invalidate_all()
        user = user or self.manager
        return self.env['pb.workforce.setup'].with_user(user).with_context(
            allowed_company_ids=[self.company.id])

    def today(self):
        return fields.Date.context_today(self.facade())

    def monday(self, day=None):
        day = day or self.today()
        return day - timedelta(days=day.weekday())

    def pattern(self, name, cycle=7, slots=None, offsets=(0,), start=None):
        rec = self.env['pb.shift.pattern'].create({
            'name': name, 'company_id': self.company.id, 'start_date': start or self.monday(),
            'cycle_days': cycle,
            'slot_ids': [(0, 0, {'day_index': k, 'template_id': t.id}) for k, t in (slots or {}).items()],
        })
        for i, off in enumerate(offsets):
            self.env['pb.shift.pattern.team'].create({
                'pattern_id': rec.id, 'name': 'Team %s' % 'ABCDEFGH'[i],
                'sequence': (i + 1) * 10, 'offset_days': off})
        return rec

    def week5(self, name='Five days'):
        return self.pattern(name, 7, {k: self.day for k in range(5)})

    def member(self, pattern, emp, date_from=False, date_to=False, team=None):
        return self.env['pb.shift.pattern.member'].create({
            'pattern_id': pattern.id, 'team_id': (team or pattern.team_ids[:1]).id,
            'employee_id': emp.id, 'date_from': date_from, 'date_to': date_to})

    def rows(self, user=None):
        return {r['id']: r for r in self.facade(user).people()['rows']}

    def snapshot(self):
        """Counts and newest write of every table a bulk action may touch."""
        self.env.flush_all()
        cr = self.env.cr
        out = {}
        for table in ('pb_shift_pattern_member', 'pb_shift_pattern_team', 'hr_shift_planning',
                      'pb_workforce_setup_undo'):
            cr.execute('SELECT count(*), max(write_date), max(id) FROM %s' % table)
            out[table] = cr.fetchone()
        cr.execute("SELECT max(write_date) FROM hr_employee")
        out['hr_employee'] = cr.fetchone()
        return out

    def members_of(self, emp):
        return self.env['pb.shift.pattern.member'].search([('employee_id', '=', emp.id)])

    def state_of(self, emps):
        """(pattern, team, from, to) per member row of these people, sorted."""
        self.env.invalidate_all()
        return sorted((m.employee_id.id, m.pattern_id.id, m.team_id.id, m.date_from, m.date_to)
                      for m in self.env['pb.shift.pattern.member'].search(
                          [('employee_id', 'in', emps.ids)]))

    def assign(self, emps, week, day, start_week=0, mode='replace', user=None):
        """Case 8 inside every assign case: the preview writes nothing and its
        numbers are what apply then does."""
        f = self.facade(user)
        before = self.snapshot()
        args = (emps.ids, week.id, fields.Date.to_string(day), start_week, mode)
        preview = f.assign_week_preview(*args)
        self.assertEqual(self.snapshot(), before, 'the preview wrote something')
        self.assertFalse(preview['problems'], preview['problems'])
        res = self.facade(user).assign_week(*args)
        self.assertEqual(res['moved'], preview['will_move'])
        self.assertEqual(res['already'], preview['already'])
        self.assertEqual(res['kept'], preview['kept'])
        return preview, res

    def next_weekday(self, weekday, weeks_ahead=1):
        d = self.monday() + timedelta(days=7 * weeks_ahead + weekday)
        return d

    # ------------------------------------------------------------ 1
    def test_01_people_gate_and_shape(self):
        with self.assertRaises(AccessError):
            self.facade(self.basic).people()
        data = self.facade(self.officer).people()
        ids = {r['id'] for r in data['rows']}
        self.assertTrue(set(self.emps.ids) <= ids)
        self.assertNotIn(self.foreign.id, ids)
        self.assertNotIn(self.gone.id, ids)
        self.assertEqual(data['total'], len(data['rows']))
        row = next(r for r in data['rows'] if r['id'] == self.emps[0].id)
        self.assertEqual(set(row), {'id', 'name', 'number', 'initials', 'department_id', 'department',
                                    'site', 'group', 'week_id', 'week_name', 'team_name', 'week_no',
                                    'week_from', 'week_now', 'week_days', 'also_on', 'oneoff'})
        # first and last word that start with a letter ("People 00" -> "PE")
        self.assertEqual(row['initials'], 'PE')
        self.assertEqual(self.env['pb.workforce.setup']._initials('Nguyễn Văn An'), 'NA')
        self.assertEqual(self.env['pb.workforce.setup']._initials('Bùi Đức Tuấn 222'), 'BT')
        self.assertEqual(row['department'], 'Sanding')
        self.assertEqual(len(row['week_days']), 7)
        teams = {t['id']: t for t in data['teams']}
        self.assertEqual((teams[self.sanding.id]['total'], teams[self.sanding.id]['with_week']), (6, 0))
        self.assertEqual(teams[self.packing.id]['name'], 'Packing')
        self.assertEqual(data['without_week'], len(data['rows']))
        self.assertFalse(data['capped'])
        # the clock number is HR-only on the employee: sudo behind the gate
        self.emps[1].sudo().pb_clock_code = 'C-77'
        self.assertEqual(self.rows(self.officer)[self.emps[1].id]['number'], 'C-77')

    # ------------------------------------------------------------ 2
    def test_02_row_week_resolution(self):
        x, y = self.week5('Week X'), self.pattern('Week Y', 7, {5: self.night})
        a, b, c, d = self.emps[:4]
        self.member(x, a)
        next_month = (self.today().replace(day=1) + timedelta(days=32)).replace(day=1)
        self.member(x, b, date_from=next_month)
        self.member(x, c, date_from=self.today() - timedelta(days=40),
                    date_to=self.today() - timedelta(days=1))
        self.member(x, d)
        self.member(y, d)
        rows = self.rows()
        self.assertEqual((rows[a.id]['week_id'], rows[a.id]['week_now']), (x.id, True))
        self.assertEqual(rows[a.id]['week_days'], [self.day.id] * 5 + [False, False])
        self.assertEqual(rows[b.id]['week_id'], x.id)
        self.assertFalse(rows[b.id]['week_now'])
        self.assertEqual(rows[b.id]['week_from'], fields.Date.to_string(next_month))
        self.assertFalse(rows[c.id]['week_id'])
        self.assertEqual(rows[c.id]['week_days'], [False] * 7)
        self.assertEqual(rows[d.id]['week_id'], x.id, 'covering weeks sort by name')
        self.assertEqual(rows[d.id]['also_on'], ['Week Y'])
        self.assertFalse(rows[a.id]['also_on'])

    # ------------------------------------------------------------ 3
    def test_03_assign_to_people_without_a_week(self):
        week = self.week5()
        people = self.emps[:4]
        before = self.facade().load()['steps'][2]['missing']
        preview, res = self.assign(people, week, self.today())
        self.assertEqual((preview['will_move'], preview['keep_theirs'], preview['already']), (4, 0, 0))
        self.assertEqual(preview['team_name'], 'Team A')
        self.assertFalse(preview['new_team'])
        self.assertEqual(res['moved'], 4)
        self.assertTrue(res['undo_id'])
        self.assertIn('4 people now work', res['summary'])
        for emp in people:
            rows = self.members_of(emp)
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows.pattern_id, rows.team_id, rows.date_from, rows.date_to),
                             (week, week.team_ids[0], self.today(), False))
        after = self.facade().load()['steps'][2]['missing']
        self.assertEqual(after, before - 4, 'the rail count drops')
        self.assertEqual(self.facade().people()['without_week'], after)

    # ------------------------------------------------------------ 4
    def test_04_replace(self):
        x, y = self.week5('Week X'), self.pattern('Week Y', 7, {k: self.night for k in range(4)})
        a, b = self.emps[:2]
        start = (self.today().replace(day=1) + timedelta(days=32)).replace(day=1)
        current = self.member(x, a)
        later = self.member(x, b, date_from=start + timedelta(days=5))
        preview, res = self.assign(a | b, y, start)
        self.assertEqual((preview['will_move'], preview['keep_theirs']), (2, 2))
        self.assertEqual(preview['ends'], [{'week_name': 'Week X', 'people': 2}])
        self.assertEqual(current.date_to, start - timedelta(days=1))
        self.assertFalse(later.exists(), 'a not-yet-started row is removed')
        for emp in (a, b):
            new = self.members_of(emp).filtered(lambda m: m.pattern_id == y)
            self.assertEqual((new.date_from, new.date_to), (start, False))

    # ------------------------------------------------------------ 5
    def test_05_keep(self):
        x, y = self.week5('Week X'), self.pattern('Week Y', 7, {0: self.night})
        a, b, c = self.emps[:3]
        row = self.member(x, a)
        stamp = (row.date_to, row.write_date)
        preview, res = self.assign(a | b | c, y, self.today(), mode='keep')
        self.assertEqual((preview['will_move'], preview['keep_theirs'], preview['kept']), (2, 1, 1))
        self.assertEqual((res['moved'], res['kept']), (2, 1))
        row.invalidate_recordset()
        self.assertEqual((row.date_to, row.write_date), stamp)
        self.assertEqual(self.members_of(a), row)
        self.assertTrue(self.members_of(b).filtered(lambda m: m.pattern_id == y))
        # the same choice with Replace counts all three
        p2 = self.facade().assign_week_preview((a | b | c).ids, y.id, fields.Date.to_string(self.today()), 0, 'replace')
        self.assertEqual(p2['will_move'], 1, 'b and c are already there; only a moves')

    # ------------------------------------------------------------ 6
    def test_06_same_week_again(self):
        week = self.week5()
        self.assign(self.emps[:3], week, self.today())
        rows = self.env['pb.shift.pattern.member'].search([('employee_id', 'in', self.emps[:3].ids)])
        stamp = sorted((m.id, m.write_date) for m in rows)
        before = self.snapshot()
        preview, res = self.assign(self.emps[:3], week, self.today() + timedelta(days=2))
        self.assertEqual((preview['already'], preview['will_move']), (3, 0))
        self.assertEqual((res['already'], res['moved'], res['undo_id']), (3, 0, False))
        self.assertEqual(self.snapshot(), before, 'nothing written')
        rows.invalidate_recordset()
        self.assertEqual(sorted((m.id, m.write_date) for m in rows), stamp)

    # ------------------------------------------------------------ 7
    def test_07_rotation_start_week(self):
        slots = {k: self.day for k in range(5)}
        slots.update({7 + k: self.night for k in range(5)})
        rota = self.pattern('Rota', 14, slots, start=self.monday() - timedelta(days=21))
        wednesday = self.next_weekday(2)
        a, b, c = self.emps[:3]
        preview, res = self.assign(a, rota, wednesday, start_week=1)
        team = self.members_of(a).team_id
        self.assertEqual(rota._pb_cycle_index(self.monday(wednesday), team.offset_days), 7,
                         'week 2 of the rotation on the Monday of that week')
        # proven, not by inspection: every day of that week is week 2's day
        for i in range(7):
            self.assertEqual(rota._pb_cycle_index(self.monday(wednesday) + timedelta(days=i),
                                                  team.offset_days), 7 + i)
        self.assertEqual(preview['new_team'], team != rota.team_ids[0])
        _p, _r = self.assign(b, rota, wednesday, start_week=0)
        team_b = self.members_of(b).team_id
        self.assertEqual(rota._pb_cycle_index(self.monday(wednesday), team_b.offset_days), 0)
        _p, _r = self.assign(c, rota, wednesday, start_week=1)
        self.assertEqual(self.members_of(c).team_id, team, 'the same start point is reused')

        # a 10-day cycle: every later Monday is a new start point; the 9th refuses
        ten = self.pattern('Ten days', 10, {k: self.day for k in range(6)})
        people = self.env['hr.employee'].create([{'name': 'Ten %s' % i, 'company_id': self.company.id}
                                                 for i in range(9)])
        offsets = set()
        for k in range(1, 8):
            self.assign(people[k], ten, self.monday() + timedelta(days=7 * k))
            m = self.members_of(people[k])
            offsets.add(m.team_id.offset_days)
            self.assertEqual(ten._pb_cycle_index(self.monday() + timedelta(days=7 * k), m.team_id.offset_days), 0)
        self.assertEqual(len(ten.team_ids), 8)
        msg = 'This working week already has 8 different start points. Pick another start week.'
        preview = self.facade().assign_week_preview(people[8].ids, ten.id,
                                                    fields.Date.to_string(self.monday() + timedelta(days=56)))
        self.assertEqual(preview['problems'], [msg])
        with self.assertRaisesRegex(UserError, msg):
            self.facade().assign_week(people[8].ids, ten.id, fields.Date.to_string(self.monday() + timedelta(days=56)))

    # ------------------------------------------------------------ 8
    def test_08_preview_equals_apply_mixed(self):
        x, y = self.week5('Week X'), self.week5('Week Y')
        a, b, c, d = self.emps[:4]
        self.member(x, a)
        self.member(y, b)
        for mode in ('keep', 'replace'):
            preview = self.facade().assign_week_preview((a | b | c | d).ids, y.id,
                                                        fields.Date.to_string(self.today()), 0, mode)
            self.assertEqual(preview['already'], 1)
            self.assertEqual(preview['keep_theirs'], 1)
            self.assertEqual(preview['will_move'], 2 if mode == 'keep' else 3)
        preview, res = self.assign(a | b | c | d, y, self.today(), mode='keep')
        self.assertEqual((res['moved'], res['kept'], res['already']), (2, 1, 1))
        # refusals come back as a sentence in the preview, never a write
        before = self.snapshot()
        bad = self.facade().assign_week_preview(a.ids, y.id, fields.Date.to_string(self.today() - timedelta(days=3)))
        self.assertTrue(bad['problems'])
        self.assertEqual(self.snapshot(), before)

    # ------------------------------------------------------------ 9
    def test_09_undo_assign(self):
        # after case 3
        week = self.week5()
        before = self.state_of(self.emps)
        _p, res = self.assign(self.emps[:4], week, self.today())
        self.facade().undo(res['undo_id'])
        self.assertEqual(self.state_of(self.emps), before)
        with self.assertRaisesRegex(UserError, 'no longer be undone'):
            self.facade().undo(res['undo_id'])

        # after case 4 (an ended row and a removed row come back exactly)
        x, y = self.week5('Week X'), self.pattern('Week Y', 7, {0: self.night})
        a, b = self.emps[4:6]
        start = self.today() + timedelta(days=10)
        self.member(x, a, date_to=start + timedelta(days=30))
        self.member(x, b, date_from=start + timedelta(days=3))
        before = self.state_of(a | b)
        _p, res = self.assign(a | b, y, start)
        self.assertNotEqual(self.state_of(a | b), before)
        # another manager cannot use it
        with self.assertRaisesRegex(UserError, 'no longer be undone'):
            self.facade(self.manager2).undo(res['undo_id'])
        self.facade().undo(res['undo_id'])
        after = self.state_of(a | b)
        self.assertEqual([r[0:2] + r[3:] for r in after], [r[0:2] + r[3:] for r in before])

        # after case 7 (a created team goes away)
        slots = {k: self.day for k in range(5)}
        slots.update({7 + k: self.night for k in range(5)})
        rota = self.pattern('Rota', 14, slots)
        teams = rota.team_ids.ids
        c = self.emps[6]
        # week 1 from next week = a start point a week after Team A's -> a new team
        _p, res = self.assign(c, rota, self.next_weekday(2), start_week=0)
        self.assertTrue(_p['new_team'])
        rota.invalidate_recordset()
        self.assertEqual(len(rota.team_ids), 2)
        self.facade().undo(res['undo_id'])
        rota.invalidate_recordset()
        self.assertEqual(rota.team_ids.ids, teams)
        self.assertFalse(self.members_of(c))

        # after a later change it refuses with the sentence and changes nothing
        _p, res = self.assign(self.emps[7:9], week, self.today())
        self.assign(self.emps[7:9], x, self.today() + timedelta(days=7))
        state = self.state_of(self.emps[7:9])
        with self.assertRaisesRegex(UserError, 'Someone changed these people after you. Nothing was undone.'):
            self.facade().undo(res['undo_id'])
        self.assertEqual(self.state_of(self.emps[7:9]), state)

    # ------------------------------------------------------------ one-off helpers
    def oneoff(self, emps, shift, first, last, weekdays, user=None):
        f = self.facade(user)
        before = self.snapshot()
        args = (emps.ids, shift.id, fields.Date.to_string(first), fields.Date.to_string(last), weekdays)
        preview = f.oneoff_preview(*args)
        self.assertEqual(self.snapshot(), before, 'the preview wrote something')
        res = self.facade(user).oneoff_apply(*args)
        self.assertEqual(res['added'], preview['will_add'])
        self.assertEqual(res['replaced'], preview['replace_drafts'])
        return preview, res

    def roster(self, emps, first, last):
        return self.env['hr.shift.planning'].search([
            ('employee_id', 'in', emps.ids), ('date', '>=', first), ('date', '<=', last)])

    def put(self, emp, day, shift=None, state='draft'):
        Grid = self.env['hr.shift.planning.grid']
        shift = shift or self.day
        start, end = Grid._pb_shift_window(shift, day, Grid._pb_shift_tzname(emp))
        return self.env['hr.shift.planning'].create({
            'employee_id': emp.id, 'shift_template_id': shift.id, 'date': day,
            'start_datetime': start, 'end_datetime': end, 'state': state,
            'company_id': self.company.id})

    # ------------------------------------------------------------ 10
    def test_10_oneoff_two_weeks(self):
        first = self.monday() + timedelta(days=7)
        last = first + timedelta(days=13)
        people = self.emps[:3]
        # as an attendance manager WITHOUT HR rights (the roster create guard)
        preview, res = self.oneoff(people, self.day, first, last, [0, 1, 2, 3, 4, 5], user=self.att_only)
        self.assertEqual((preview['days'], preview['people'], preview['will_add']), (12, 3, 36))
        self.assertEqual(res['added'], 36)
        self.assertIn('36 one-off shifts added for 3 people', res['summary'])
        rows = self.roster(people, first, last)
        self.assertEqual(len(rows), 36)
        Grid = self.env['hr.shift.planning.grid']
        for r in rows:
            start, end = Grid._pb_shift_window(self.day, r.date, TZ)
            self.assertEqual((r.start_datetime, r.end_datetime), (start, end))
            self.assertEqual(r.company_id, self.company)
            self.assertFalse(r.pb_pattern_id)
            self.assertEqual(r.state, 'draft')
            self.assertNotEqual(r.date.weekday(), 6)
        # 07:30 in Ho Chi Minh City is 00:30 UTC
        self.assertEqual(rows[0].start_datetime.strftime('%H:%M'), '00:30')
        self.assertEqual(self.rows()[people[0].id]['oneoff'], 12)

    # ------------------------------------------------------------ 11
    def test_11_oneoff_skips_and_replaces(self):
        a, b, c = self.emps[:3]
        first = self.monday() + timedelta(days=7)
        last = first + timedelta(days=2)
        draft = self.put(a, first, self.night)
        published = self.put(b, first, state='published')
        ltype = self.env['hr.leave.type'].sudo().create({'name': 'People leave', 'requires_allocation': False,
                                                         'company_id': self.company.id})
        leave = self.env['hr.leave'].sudo().create({
            'name': 'People leave', 'employee_id': c.id, 'holiday_status_id': ltype.id,
            'request_date_from': first + timedelta(days=1), 'request_date_to': first + timedelta(days=1)})
        leave.sudo().write({'state': 'validate'})
        preview, res = self.oneoff(a | b | c, self.day, first, last, [0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(preview['replace_drafts'], 1)
        self.assertEqual(preview['skipped'], {'published': 1, 'leave_approved': 1})
        self.assertEqual(preview['will_add'], 7)
        self.assertEqual(len(preview['examples']), 2)
        self.assertFalse(draft.exists(), 'the draft is replaced')
        self.assertTrue(published.exists())
        self.assertEqual(self.roster(b, first, first).ids, published.ids)
        self.assertFalse(self.roster(c, first + timedelta(days=1), first + timedelta(days=1)))
        self.assertEqual(self.roster(a, first, first).shift_template_id, self.day)
        # past days
        yesterday = self.today() - timedelta(days=1)
        p = self.facade().oneoff_preview(a.ids, self.day.id, fields.Date.to_string(yesterday - timedelta(days=1)),
                                         fields.Date.to_string(yesterday), list(range(7)))
        self.assertEqual(p['skipped'], {'past': 2})
        self.assertEqual(p['will_add'], 0)
        # more than 62 days
        far = fields.Date.to_string(first + timedelta(days=62))
        p = self.facade().oneoff_preview(a.ids, self.day.id, fields.Date.to_string(first), far, [0])
        self.assertIn('62 days or fewer', p['problems'][0])
        with self.assertRaisesRegex(UserError, '62 days or fewer'):
            self.facade().oneoff_apply(a.ids, self.day.id, fields.Date.to_string(first), far, [0])

    # ------------------------------------------------------------ 12
    def test_12_overnight_last_day(self):
        emp = self.emps[0]
        first = self.monday() + timedelta(days=14)
        last = first + timedelta(days=3)
        self.oneoff(emp, self.night, first, last, list(range(7)))
        rows = self.roster(emp, first, last).sorted('date')
        self.assertEqual(len(rows), 4)
        tz = pytz.timezone(TZ)
        end_local = pytz.utc.localize(rows[-1].end_datetime).astimezone(tz)
        self.assertEqual(rows[-1].date, last)
        self.assertEqual(end_local.date(), last + timedelta(days=1))
        self.assertEqual(end_local.strftime('%H:%M'), '06:00')

    # ------------------------------------------------------------ 13
    def test_13_undo_oneoff(self):
        a, b = self.emps[:2]
        first = self.monday() + timedelta(days=7)
        last = first + timedelta(days=4)
        draft = self.put(a, first + timedelta(days=1), self.night)
        kept = {f: draft[f] for f in ('employee_id', 'shift_template_id', 'date', 'start_datetime',
                                      'end_datetime', 'state', 'company_id')}
        before_b = self.roster(b, first, last).ids
        _p, res = self.oneoff(a | b, self.day, first, last, [0, 1, 2, 3, 4])
        self.assertEqual((res['added'], res['replaced']), (10, 1))
        self.facade().undo(res['undo_id'])
        self.assertEqual(self.roster(b, first, last).ids, before_b)
        back = self.roster(a, first, last)
        self.assertEqual(len(back), 1)
        for name, value in kept.items():
            self.assertEqual(back[name], value, name)
        # a changed row refuses the undo
        _p, res = self.oneoff(a, self.day, first, first, [first.weekday()])
        row = self.roster(a, first, first)
        row.write({'state': 'published'})
        with self.assertRaisesRegex(UserError, 'Nothing was undone'):
            self.facade().undo(res['undo_id'])

    # ------------------------------------------------------------ 14
    def test_14_late_rule_without_hr_rights(self):
        a, b, c = self.emps[:3]
        a.sudo().pb_attendance_category = 'worker'
        f = self.facade(self.att_only)
        p = f.set_late_rule_preview((a | b | c).ids, 'manager')
        self.assertEqual((p['changed'], p['unchanged'], p['policy_set']), (3, 0, 0))
        res = self.facade(self.att_only).set_late_rule((a | b | c).ids, 'manager')
        self.assertEqual(res['changed'], 3)
        self.assertEqual(set((a | b | c).sudo().mapped('pb_attendance_category')), {'manager'})
        self.assertEqual(self.rows(self.att_only)[a.id]['group'], 'manager')
        self.facade(self.att_only).undo(res['undo_id'])
        self.assertEqual(a.sudo().pb_attendance_category, 'worker')
        self.assertFalse(b.sudo().pb_attendance_category)

        # exactly one non-retired late-rule set -> people without one get it
        Policy = self.env['pb.attendance.policy'].with_company(self.company)
        one = Policy.create({'name': 'People rules', 'company_id': self.company.id, 'tz': TZ})
        p = self.facade(self.att_only).set_late_rule_preview((a | b).ids, 'worker')
        self.assertEqual((p['changed'], p['policy_set']), (1, 2))
        res = self.facade(self.att_only).set_late_rule((a | b).ids, 'worker')
        self.assertEqual((a | b).sudo().mapped('pb_attendance_policy_id'), one)
        self.facade(self.att_only).undo(res['undo_id'])
        self.assertFalse((a | b).sudo().mapped('pb_attendance_policy_id'))
        self.assertEqual(b.sudo().pb_attendance_category, False)
        # two of them -> nobody is pointed at one
        Policy.create({'name': 'People rules 2', 'company_id': self.company.id, 'tz': TZ})
        p = self.facade(self.att_only).set_late_rule_preview((a | b).ids, 'worker')
        self.assertEqual(p['policy_set'], 0)
        with self.assertRaises(UserError):
            self.facade().set_late_rule(a.ids, 'boss')

    # ------------------------------------------------------------ 15
    def test_15_officer_writes_and_previews_refused(self):
        week = self.week5()
        f = self.facade(self.officer)
        ids = self.emps[:2].ids
        today = fields.Date.to_string(self.today())
        calls = [
            lambda: f.assign_week_preview(ids, week.id, today),
            lambda: f.assign_week(ids, week.id, today),
            lambda: f.oneoff_preview(ids, self.day.id, today, today, [0, 1, 2, 3, 4, 5, 6]),
            lambda: f.oneoff_apply(ids, self.day.id, today, today, [0, 1, 2, 3, 4, 5, 6]),
            lambda: f.set_late_rule_preview(ids, 'worker'),
            lambda: f.set_late_rule(ids, 'worker'),
            lambda: f.undo(1),
        ]
        for call in calls:
            with self.assertRaises(AccessError):
                call()
        with self.assertRaises(AccessError):
            self.facade(self.basic).people()

    # ------------------------------------------------------------ 16
    def test_16_scale(self):
        depts = self.env['hr.department'].create([{'name': 'Scale %s' % i, 'company_id': self.company.id}
                                                   for i in range(6)])
        emps = self.env['hr.employee'].create([{
            'name': 'Scale %03d' % i, 'company_id': self.company.id,
            'department_id': depts[i % 6].id} for i in range(700)])
        week = self.week5('Scale week')
        rota = self.pattern('Scale rota', 14, {0: self.day, 7: self.night}, offsets=(0, 7))
        M = self.env['pb.shift.pattern.member']
        M.create([{'pattern_id': week.id, 'team_id': week.team_ids.id, 'employee_id': e.id}
                  for e in emps[:300]])
        M.create([{'pattern_id': rota.id, 'team_id': rota.team_ids[i % 2].id, 'employee_id': e.id}
                  for i, e in enumerate(emps[300:500])])
        f = self.facade(self.officer)
        f.people()                       # warm the registry caches once
        self.env.flush_all()
        self.env.invalidate_all()
        count = self.env.cr.sql_log_count
        t0 = time.time()
        data = f.people()
        took = time.time() - t0
        queries = self.env.cr.sql_log_count - count
        _logger.info('WFSETUP case 16: people() %s rows in %.3fs, %s queries', data['total'], took, queries)
        self.assertGreaterEqual(data['total'], 710)
        self.assertLess(took, 2.0, 'people() took %.2fs' % took)
        self.assertLess(queries, 40, 'people() ran %s queries' % queries)
        rows = {r['id']: r for r in data['rows']}
        self.assertEqual(rows[emps[0].id]['week_id'], week.id)
        self.assertIn(rows[emps[301].id]['week_no'], (1, 2))

    # ------------------------------------------------------------ extra: default person
    def test_17b_default_person_is_not_the_administrator(self):
        week = self.week5()
        admin = self.env.ref('base.user_admin')
        boss = self.env['hr.employee'].create({'name': 'Aaa Administrator', 'company_id': self.company.id,
                                               'user_id': admin.id})
        self.member(week, boss)
        self.member(week, self.emps[3])
        default = self.facade().person_week()
        self.assertEqual(default['id'], self.emps[3].id)
        self.assertEqual(self.facade().load()['person']['id'], self.emps[3].id)

    # ------------------------------------------------------------ extra: roster create guard
    def test_17c_pattern_drafts_without_hr_rights(self):
        week = self.week5()
        self.member(week, self.emps[0])
        start = self.monday() + timedelta(days=7)
        report = self.env['pb.shift.patterns'].with_user(self.att_only).with_context(
            allowed_company_ids=[self.company.id]).make_drafts([week.id], fields.Date.to_string(start), 1)
        self.assertEqual(report['created'], 5)
        self.assertFalse(report.get('counts', {}).get('refused'))
