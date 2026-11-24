# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P4 — step 5 Holidays, step 6 Time clocks, step 7 Check and go live
(handover §4, cases 1-17; case 18 is the suite run itself), plus the P3
carry-over (a): a moved automatic roster row gets its new day's type.
"""

import logging
import time as timer
from datetime import date, timedelta
from unittest.mock import patch

import pytz

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.pb_attendance_policy.models.policy import _CALC_TOKEN

TZ = 'Asia/Ho_Chi_Minh'
_logger = logging.getLogger(__name__)


class GoLiveFixture:
    """The go-live company, its people, working weeks and rules — shared with
    the P5a tests (`test_p5a.py`)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vn = cls.env.ref('base.vn')
        cls.company = cls.env['res.company'].create({'name': 'Go live company', 'country_id': cls.vn.id})
        cls.company.resource_calendar_id.tz = TZ
        cls.other = cls.env['res.company'].create({'name': 'Other go live company', 'country_id': cls.vn.id})
        cls.other.resource_calendar_id.tz = TZ
        # an attendance manager WITHOUT time-off or HR rights (handover case 2)
        cls.manager = new_test_user(
            cls.env, login='wfs4_manager', groups='base.group_user,hr_attendance.group_hr_attendance_manager',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id, cls.other.id])], tz=TZ)
        cls.officer = new_test_user(
            cls.env, login='wfs4_officer', groups='hr_attendance.group_hr_attendance_officer',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])], tz=TZ)
        Shift = cls.env['hr.shift.template']
        cls.day = Shift.create({'name': 'Live day', 'code': 'LVD', 'start_hour': 7.5, 'end_hour': 16.5,
                                'break_duration': 1.0, 'company_id': cls.company.id})
        cls.night = Shift.create({'name': 'Live night', 'code': 'LVN', 'start_hour': 19.5, 'end_hour': 4.5,
                                  'break_duration': 1.0, 'is_overnight': True, 'shift_type': 'night',
                                  'company_id': cls.company.id})
        cls.other_day = Shift.create({'name': 'Other day', 'code': 'OTD', 'start_hour': 8.0, 'end_hour': 17.0,
                                      'break_duration': 1.0, 'company_id': cls.other.id})
        today = fields.Date.context_today(cls.env['pb.workforce.setup'].with_user(cls.manager))
        cls.monday = today - timedelta(days=today.weekday())
        cls.five = cls._pattern('Live five days', {k: cls.day for k in range(5)})
        cls.six = cls._pattern('Live six days', {k: cls.day for k in range(6)})
        cls.nights = cls._pattern('Live nights', {k: cls.night for k in range(7)}, work_on_holidays=True)
        Emp = cls.env['hr.employee']
        cls.people = Emp.create([{'name': 'Live %02d' % i, 'company_id': cls.company.id, 'tz': TZ,
                                  'pb_attendance_category': 'worker'} for i in range(40)])
        Member = cls.env['pb.shift.pattern.member']
        for i, emp in enumerate(cls.people):
            pat = cls.five if i < 20 else cls.six if i < 32 else cls.nights
            Member.create({'pattern_id': pat.id, 'team_id': pat.team_ids[:1].id, 'employee_id': emp.id})
        cls.free = Emp.create({'name': 'Zed Noweek', 'company_id': cls.company.id, 'tz': TZ})
        cls.foreign = Emp.create({'name': 'Foreign live person', 'company_id': cls.other.id, 'tz': TZ})
        cls.policy = cls._active_rules(cls.company, cls.day)

    @classmethod
    def _pattern(cls, name, slots, company=None, work_on_holidays=False):
        company = company or cls.company
        rec = cls.env['pb.shift.pattern'].create({
            'name': name, 'company_id': company.id, 'start_date': cls.monday, 'cycle_days': 7,
            'work_on_holidays': work_on_holidays,
            'slot_ids': [(0, 0, {'day_index': k, 'template_id': t.id}) for k, t in slots.items()]})
        cls.env['pb.shift.pattern.team'].create({'pattern_id': rec.id, 'name': 'Team A',
                                                 'sequence': 10, 'offset_days': 0})
        return rec

    @classmethod
    def _active_rules(cls, company, shift):
        policy = cls.env['pb.attendance.policy'].create({
            'name': 'Live rules', 'company_id': company.id, 'tz': TZ,
            'shift_ids': [Command.create({'template_id': shift.id, 'normal_end_offset': 9.0,
                                          'break_start_offset': 4.0, 'break_hours': 1.0})],
            'band_ids': [Command.create({'category': c, 'minimum': 0, 'open_ended': True, 'hours': 0,
                                         'confirmed': True}) for c in ('worker', 'manager')]})
        policy.action_activate()
        return policy

    # ------------------------------------------------------------ helpers
    def facade(self, user=None, company=None):
        self.env.flush_all()
        self.env.invalidate_all()
        return self.env['pb.workforce.setup'].with_user(user or self.manager).with_context(
            allowed_company_ids=[(company or self.company).id])

    def today(self):
        return fields.Date.context_today(self.facade())

    def local_days(self, row):
        zone = pytz.timezone(TZ)
        lo = pytz.utc.localize(row.date_from).astimezone(zone).date()
        hi = pytz.utc.localize(row.date_to).astimezone(zone).date()
        return lo, hi

    def days_off(self, company=None):
        return self.env['resource.calendar.leaves'].search([
            ('company_id', '=', (company or self.company).id), ('resource_id', '=', False)])

    def roster(self, emp, day, shift=None, company=None, **extra):
        shift = shift or self.day
        Grid = self.env['hr.shift.planning.grid']
        start, end = Grid._pb_shift_window(shift, day, Grid._pb_shift_tzname(emp))
        vals = dict({'employee_id': emp.id, 'shift_template_id': shift.id, 'date': day,
                     'start_datetime': start, 'end_datetime': end, 'state': 'draft',
                     'company_id': (company or self.company).id}, **extra)
        return self.env['hr.shift.planning'].create(vals)

    def snapshot(self):
        self.env.flush_all()
        out = {}
        for table in ('hr_shift_planning', 'pb_shift_pattern', 'pb_shift_pattern_member', 'res_company',
                      'resource_calendar_leaves', 'pb_workforce_setup_run'):
            self.env.cr.execute('SELECT count(*), max(write_date), max(id) FROM %s' % table)
            out[table] = self.env.cr.fetchone()
        return out

    def publish(self, weeks=4, user=None):
        f = self.facade(user)
        start = f.go_live_start(weeks)
        for i in range(len(start['weeks'])):
            res = self.facade(user).go_live_week(start['run_id'], i)
            self.assertTrue(res['ok'], res)
        return start, self.facade(user).go_live_finish(start['run_id'])

    def window(self, weeks=4):
        today = self.today()
        return today, self.monday + timedelta(days=7 * weeks - 1)


@tagged('post_install', '-at_install', 'wfsetup')
class TestGoLive(GoLiveFixture, TransactionCase):

    # ============================================================ 1
    def test_01_holidays_shape_and_working_days(self):
        f = self.facade()
        data = f.holidays(2027)
        self.assertEqual(set(data), {'year', 'today', 'years', 'can_edit', 'has_calendar', 'calendar', 'days',
                                     'rest_weekdays', 'working_days', 'off_count', 'suggestions',
                                     'confirmed', 'confirmed_year', 'nudge'})
        self.assertTrue(data['has_calendar'])
        self.assertTrue(data['can_edit'])
        self.assertEqual(data['days'], [])
        # the most-used working week here is Mon-Sat? (20 on five days, 12 on six, 8 on nights)
        self.assertEqual(data['rest_weekdays'], [5, 6], 'the five-day week has the most people')
        # make the Mon-Sat week the most used one, then pin 2027
        Member = self.env['pb.shift.pattern.member']
        for emp in self.people[:20]:
            Member.search([('employee_id', '=', emp.id)]).write({'date_to': self.today() - timedelta(days=1)})
            Member.create({'pattern_id': self.six.id, 'team_id': self.six.team_ids[:1].id, 'employee_id': emp.id,
                           'date_from': self.today()})
        f = self.facade()
        self.assertEqual(f.holidays(2027)['rest_weekdays'], [6])
        self.assertEqual(f.holidays(2027)['working_days'], 365 - 52, '2027 has 52 Sundays')
        res = f.add_suggested(2027)
        self.assertEqual(res['added'], 10)
        data = self.facade().holidays(2027)
        # 10 public holidays, of which Sun 7 Feb is a rest day anyway -> 9 working days lost
        self.assertEqual(data['working_days'], 365 - 52 - 9)
        self.assertEqual(data['working_days'], 304)
        self.assertEqual(data['off_count'], 10)
        self.assertEqual({d['kind'] for d in data['days']}, {'public'})
        # only this company's rows: a day off of the other company is not listed
        self.facade(company=self.other).add_day_off('2027-03-03')
        self.assertEqual(len(self.facade().holidays(2027)['days']), 10)
        self.assertEqual([d['date'] for d in self.facade(company=self.other).holidays(2027)['days']],
                         ['2027-03-03'])
        # a company without a working calendar: read-only, refused writes
        bare = self.env['res.company'].create({'name': 'No calendar company', 'country_id': self.vn.id})
        bare.resource_calendar_id = False
        self.manager.company_ids = [(4, bare.id)]
        nb = self.facade(company=bare).holidays(2027)
        self.assertFalse(nb['has_calendar'])
        self.assertFalse(nb['can_edit'])
        with self.assertRaisesRegex(UserError, "working calendar first"):
            self.facade(company=bare).add_day_off('2027-03-03')

    # ============================================================ 2
    def test_02_add_day_off_as_attendance_manager(self):
        self.assertFalse(self.manager.has_group('hr_holidays.group_hr_holidays_user'))
        self.assertFalse(self.manager.has_group('hr.group_hr_manager'))
        with self.assertRaises(AccessError):
            self.env['pb.holidays'].with_user(self.manager).add(self.company.id, 'X', '2027-03-04')
        res = self.facade().add_day_off('2027-03-04')
        row = self.env['resource.calendar.leaves'].browse(res['ids'])
        self.assertEqual(len(row), 1)
        self.assertEqual(row.pb_holiday_kind, 'company')
        self.assertEqual(row.calendar_id, self.company.resource_calendar_id)
        self.assertEqual(row.company_id, self.company)
        self.assertFalse(row.resource_id)
        self.assertEqual(self.local_days(row), (date(2027, 3, 4), date(2027, 3, 4)))
        self.assertIn('company day off', res['summary'])
        with self.assertRaisesRegex(UserError, 'already a day off'):
            self.facade().add_day_off('2027-03-04')
        with self.assertRaises(AccessError):
            self.facade(self.officer).add_day_off('2027-03-05')
        # a company this manager may not use is refused (the framework's own company check)
        third = self.env['res.company'].create({'name': 'Not allowed company'})
        with self.assertRaises(AccessError):
            self.env['pb.workforce.setup'].with_user(self.manager).with_context(
                allowed_company_ids=[third.id]).add_day_off('2027-03-05')
        self.assertFalse(self.days_off(third))

    # ============================================================ 3
    def test_03_remove_day_off(self):
        a = self.facade().add_day_off('2027-03-10')['ids'][0]
        b = self.facade().add_day_off('2027-03-11')['ids'][0]
        theirs = self.facade(company=self.other).add_day_off('2027-03-10')['ids'][0]
        res = self.facade().remove_day_off(a)
        self.assertEqual(res['removed'], 1)
        self.assertEqual(res['restore'], [{'date': '2027-03-10', 'date_to': '2027-03-10',
                                           'name': 'Company day off', 'kind': 'company'}])
        self.assertFalse(self.env['resource.calendar.leaves'].browse(a).exists())
        self.assertTrue(self.env['resource.calendar.leaves'].browse(b).exists())
        with self.assertRaisesRegex(UserError, "not on this company's calendar"):
            self.facade().remove_day_off(theirs)
        self.assertTrue(self.env['resource.calendar.leaves'].browse(theirs).exists())
        with self.assertRaises(AccessError):
            self.facade(self.officer).remove_day_off(b)
        # undo of a remove puts the same day back
        back = self.facade().restore_days_off(res['restore'])
        row = self.env['resource.calendar.leaves'].browse(back['ids'])
        self.assertEqual((row.pb_holiday_kind, self.local_days(row)), ('company', (date(2027, 3, 10),) * 2))

    # ============================================================ 4
    def test_04_add_suggested_all_or_nothing(self):
        sugg = self.facade().holidays(2027)['suggestions']
        self.assertEqual((sugg['code'], sugg['year'], sugg['count'], len(sugg['missing'])), ('VN', 2027, 10, 10))
        self.assertIn('lunar calendar', sugg['note'])
        Holidays = type(self.env['pb.holidays'])
        real = Holidays._create_row
        calls = []

        def flaky(this, company, calendar, name, day_from, day_to):
            calls.append(day_from)
            if len(calls) == 4:
                return False                        # "already on the calendar under that name"
            return real(this, company, calendar, name, day_from, day_to)

        before = len(self.days_off())
        with patch.object(Holidays, '_create_row', flaky):
            with self.assertRaisesRegex(UserError, 'Nothing was added'):
                self.facade().add_suggested(2027)
        self.assertEqual(len(self.days_off()), before, 'all or nothing')
        res = self.facade().add_suggested(2027)
        self.assertEqual(res['added'], 10)
        rows = self.env['resource.calendar.leaves'].browse(res['ids'])
        got = sorted(self.local_days(r)[0].isoformat() for r in rows)
        self.assertEqual(got, ['2027-01-01', '2027-02-05', '2027-02-06', '2027-02-07', '2027-02-08', '2027-02-09',
                               '2027-04-16', '2027-04-30', '2027-05-01', '2027-09-02'])
        self.assertEqual(set(rows.mapped('pb_holiday_kind')), {'public'})
        again = self.facade().add_suggested(2027)
        self.assertEqual(again['added'], 0)
        self.assertIn('already on the calendar', again['summary'])
        self.assertFalse(self.facade().holidays(2027)['suggestions']['missing'])
        # 2026 comes from the reference rows pb_timeoff ships (conflicts left out)
        s26 = self.facade().holidays(2026)['suggestions']
        self.assertTrue(s26 and s26['count'] == 12, s26)
        # a country with no list: no card
        fr = self.env['res.company'].create({'name': 'French go live', 'country_id': self.env.ref('base.fr').id})
        self.manager.company_ids = [(4, fr.id)]
        self.assertFalse(self.facade(company=fr).holidays(2027)['suggestions'])
        with self.assertRaises(UserError):
            self.facade(company=fr).add_suggested(2027)

    # ============================================================ 5
    def test_05_holidays_remark_the_roster(self):
        day = self.monday + timedelta(days=15)                   # Tuesday in two weeks
        auto = self.roster(self.people[0], day)
        hand = self.roster(self.people[1], day, pb_day_kind='weekday')
        calc = self.roster(self.people[2], day)
        calc.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_calculation_status': 'Preview'})
        self.assertEqual(auto.pb_day_kind, 'weekday')
        res = self.facade().add_day_off(fields.Date.to_string(day))
        self.assertIn('1 planned shift is now paid as public holiday', res['summary'])
        self.env.invalidate_all()
        self.assertEqual(auto.pb_day_kind, 'holiday')
        self.assertEqual((hand.pb_day_kind, hand.pb_day_kind_manual), ('weekday', True))
        self.assertEqual(calc.pb_day_kind, 'weekday', 'a calculated shift is never re-marked')
        back = self.facade().remove_day_off(res['ids'][0])
        self.assertIn('back to its usual pay', back['summary'])
        self.env.invalidate_all()
        self.assertEqual(auto.pb_day_kind, 'weekday')
        self.assertEqual(hand.pb_day_kind, 'weekday')

    # ============================================================ 6
    def test_06_confirm_holidays(self):
        f = self.facade()
        status = {s['key']: s for s in f.load()['steps']}
        self.assertEqual((status['holidays']['state'], status['holidays']['text']), ('todo', 'Check and confirm'))
        f.add_suggested(2027)
        res = self.facade().confirm_holidays(2027)
        self.assertEqual(self.company.pb_wfs_holidays_year, 2027)
        self.assertIn('10 days off', res['summary'])
        status = {s['key']: s for s in self.facade().load()['steps']}
        self.assertEqual((status['holidays']['state'], status['holidays']['text']), ('done', '10 days off in 2027'))
        self.assertTrue(self.facade().holidays(2027)['confirmed'])
        # confirming an earlier year never moves the mark back
        self.facade().confirm_holidays(2026)
        self.assertEqual(self.company.pb_wfs_holidays_year, 2027)
        with self.assertRaises(AccessError):
            self.facade(self.officer).confirm_holidays(2027)

    # ============================================================ 7
    def _connector(self, name, company=None, **status):
        conn = self.env['pb.clock.connector'].sudo().create({
            'name': name, 'company_id': (company or self.company).id, 'source_group': name, 'tz': TZ})
        if status:
            conn.sudo().write(status)
        return conn

    def test_07_clock_states(self):
        now = fields.Datetime.now().replace(microsecond=0)        # one fixed "now" for every row
        ok = self._connector('Gate A', state='connected', last_contact=now - timedelta(hours=2))
        quiet = self._connector('Gate B', state='connected', last_contact=now - timedelta(hours=30))
        waiting = self._connector('Gate C')
        self._connector('Gate D', state='connected', last_contact=now - timedelta(minutes=5),
                                 last_error=r'C:\Users\clerk\Mitaco\att2000.mdb could not be opened (0x80004005)')
        off = self._connector('Gate E', state='revoked')
        self._connector('Elsewhere', company=self.other, state='connected', last_contact=now)
        machine = self.env['pb.clock.device'].sudo().create({
            'name': 'Push machine', 'serial': 'WFS4-001', 'company_id': self.company.id, 'kind': 'terminal',
            'state': 'allowed', 'location': 'Factory 3'})
        machine.sudo().write({'allowed_at': now - timedelta(days=3), 'last_seen_at': now - timedelta(minutes=1)})
        rows = {r['name']: r for r in self.facade()._clock_rows(now)}
        self.assertNotIn('Elsewhere', rows)
        self.assertEqual({n: r['state'] for n, r in rows.items()},
                         {'Gate A': 'ok', 'Gate B': 'quiet', 'Gate C': 'waiting', 'Gate D': 'attention',
                          'Gate E': 'off', 'Push machine': 'ok'})
        self.assertEqual((rows['Push machine']['kind'], rows['Push machine']['where']), ('machine', 'Factory 3'))
        self.assertEqual(rows['Gate A']['kind'], 'pc')
        problem = rows['Gate D']['problem']
        self.assertTrue(problem)
        for leak in ('mdb', 'Mitaco', 'clerk', '0x8', 'C:'):
            self.assertNotIn(leak, problem)
        data = self.facade().clocks()
        self.assertNotIn('C:\\Users', str(data), 'raw error text never leaves the server')
        self.assertEqual(data['later'], 3)                       # quiet, waiting, attention
        self.assertFalse(data['confirmed'])
        self.assertTrue(rows['Gate A']['last_heard'])
        self.assertTrue(ok and quiet and waiting and off)

    # ============================================================ 8
    def test_08_clock_invite(self):
        conn = self._connector('Invite gate')
        res = self.facade().clock_invite(conn.id)
        token = res['token']
        self.assertGreaterEqual(len(token), 40)
        until = fields.Datetime.to_datetime(res['until'])
        self.assertAlmostEqual((until - fields.Datetime.now()).total_seconds(), 5 * 86400, delta=120)
        Conn = self.env['pb.clock.connector']
        self.assertEqual(Conn._invited(token), conn)
        second = self.facade().clock_invite(conn.id)['token']
        self.assertNotEqual(second, token)
        self.assertFalse(Conn._invited(token), 'the link sent before stops working')
        self.assertEqual(Conn._invited(second), conn)
        with self.assertRaises(AccessError):
            self.facade(self.officer).clock_invite(conn.id)
        theirs = self._connector('Their gate', company=self.other)
        with self.assertRaisesRegex(UserError, 'no longer there'):
            self.facade().clock_invite(theirs.id)
        row = {r['id']: r for r in self.facade().clocks()['clocks'] if r['kind'] == 'pc'}[conn.id]
        self.assertTrue(row['invite_until'])

    # ============================================================ 9
    def test_09_clock_add_and_no_number(self):
        row = self.facade().clock_add('Office door', 'Head office')
        conn = self.env['pb.clock.connector'].browse(row['id'])
        self.assertEqual((conn.state, conn.company_id, conn.tz, conn.source_group),
                         ('new', self.company, TZ, 'Head office'))
        self.assertEqual((row['state'], row['where'], row['kind']), ('waiting', 'Head office', 'pc'))
        with self.assertRaisesRegex(UserError, 'Give the clock a name'):
            self.facade().clock_add('  ')
        with self.assertRaises(AccessError):
            self.facade(self.officer).clock_add('Officer door')
        active = self.env['hr.employee'].search_count([('company_id', '=', self.company.id)])
        self.assertEqual(self.facade().clocks()['no_number'], active)
        self.people[0].sudo().pb_clock_code = '1001'
        self.people[1].sudo().barcode = '2002'
        self.assertEqual(self.facade().clocks()['no_number'], active - 2)

    # ============================================================ 10
    def check(self, **kw):
        return self.facade().live_check(4)

    def blocking(self, data):
        return {s['key'] for s in data['steps'] if s['blocking']}

    def test_10_live_blockers(self):
        data = self.check()
        self.assertEqual(self.blocking(data), set())
        self.assertTrue(data['can_publish'])
        self.assertEqual(data['publish_label'], 'Publish for the 40 who are ready', '1 person has no week')
        amber = {s['key'] for s in data['steps'] if not s['ok']}
        self.assertEqual(amber, {'people', 'holidays', 'clocks'})
        # everyone has a week -> the plain label
        self.free.active = False
        self.assertEqual(self.check()['publish_label'], 'Publish 4 weeks')
        # 1. rules not confirmed
        self.policy.action_retire()
        data = self.check()
        self.assertEqual(self.blocking(data), {'rules'})
        self.assertFalse(data['can_publish'])
        with self.assertRaisesRegex(UserError, 'Confirm the late and overtime rules first'):
            self.facade().go_live_start(4)
        self._active_rules(self.company, self.day)
        # 2. nobody has a working week
        members = self.env['pb.shift.pattern.member'].search([('company_id', '=', self.company.id)])
        members.write({'date_to': self.today() - timedelta(days=1)})
        data = self.check()
        self.assertEqual(self.blocking(data), {'people'})
        self.assertFalse(data['can_publish'])
        self.assertIn('Nobody has a working week yet.', [s['text'] for s in data['steps']])
        members.write({'date_to': False})
        # 3. no shift (this company's and the shared ones archived; the weeks still exist)
        shifts = self.env['hr.shift.template'].search(
            ['|', ('company_id', '=', False), ('company_id', '=', self.company.id)])
        shifts.write({'active': False})
        data = self.check()
        self.assertEqual(self.blocking(data), {'shifts'})
        self.assertFalse(data['can_publish'])
        shifts.write({'active': True})
        # 4. no working week (archived): nobody can have one either
        patterns = self.five | self.six | self.nights
        patterns.write({'active': False})
        data = self.check()
        self.assertIn('weeks', self.blocking(data))
        self.assertFalse(data['can_publish'])
        patterns.write({'active': True})
        self.assertTrue(self.check()['can_publish'])
        # officer: the checklist only
        off = self.facade(self.officer).live_check(4)
        self.assertFalse(off['plan'])
        self.assertFalse(off['can_publish'])
        self.assertEqual(len(off['steps']), 6)

    # ============================================================ 11
    def test_11_live_check_writes_nothing(self):
        before = self.snapshot()
        data = self.check()
        self.assertEqual(self.snapshot(), before, 'live_check wrote something')
        plan = data['plan']
        self.assertGreater(plan['new_shifts'], 0)
        self.assertEqual(plan['people'], 40)
        self.assertEqual(plan['shifts'], plan['new_shifts'] + plan['already_planned'])
        self.assertLessEqual(len(data['sample']['rows']), 6)
        self.assertEqual(len(data['sample']['days']), 7)
        names = {r['name'] for r in data['sample']['rows']}
        self.assertTrue(names & {'Live 00'} and names & {'Live 20'} and names & {'Live 32'},
                        'one person per working week first: %s' % names)

    # ============================================================ 12, 13
    def test_12_13_publish_window(self):
        first, last = self.window(4)
        holiday = self.monday + timedelta(days=9)                 # Wednesday of week 2
        self.facade().add_day_off(fields.Date.to_string(holiday))
        # a one-off on a five-day person's Sunday: a rest day
        sunday = self.monday + timedelta(days=13)
        rest = self.roster(self.people[0], sunday)
        # the other company's drafts in the same window
        theirs = self.roster(self.foreign, first, shift=self.other_day, company=self.other)
        theirs |= self.roster(self.foreign, first + timedelta(days=7), shift=self.other_day, company=self.other)
        plan = self.check()['plan']
        start, finish = self.publish(4)
        self.assertEqual(len(start['weeks']), 4)
        self.assertEqual(start['weeks'][0]['from'], fields.Date.to_string(first))
        self.assertEqual(start['weeks'][-1]['to'], fields.Date.to_string(last))
        Shift = self.env['hr.shift.planning']
        rows = Shift.search([('company_id', '=', self.company.id), ('date', '>=', first), ('date', '<=', last)])
        self.assertFalse(rows.filtered(lambda r: r.state == 'draft'), 'every row in the window is published')
        keys = [(r.employee_id.id, r.date) for r in rows]
        self.assertEqual(len(keys), len(set(keys)), 'each day once')
        self.assertEqual(len(rows), plan['shifts'], 'the confirm panel number is what was published')
        self.assertEqual(finish['published'], len(rows))
        self.assertEqual(finish['people'], 40)
        # every wanted day: the engine's own wanted list, minus holidays for the weeks that skip them
        Eng = self.env['pb.shift.pattern.engine']
        hmap = Eng._pb_holiday_map(self.people, first, last)
        wanted = set()
        for pat in (self.five, self.six, self.nights):
            for (emp_id, iso) in Eng._pb_wanted(pat.sudo(), first, last, first)[0]:
                if pat.work_on_holidays or (emp_id, iso) not in hmap:
                    wanted.add((emp_id, fields.Date.to_date(iso)))
        wanted.add((self.people[0].id, sunday))
        self.assertEqual(set(keys), wanted)
        self.assertTrue(all(r.company_id == self.company for r in rows))
        # holiday / rest-day marks
        on_hol = rows.filtered(lambda r: r.date == holiday)
        self.assertTrue(on_hol and set(on_hol.mapped('pb_day_kind')) == {'holiday'})
        self.assertEqual(set(on_hol.mapped('employee_id')), set(self.people[32:]), 'only the week that works holidays')
        self.assertEqual(rest.pb_day_kind, 'weekend')
        self.assertEqual(rest.state, 'published')
        # acknowledgement tokens were minted by the records' own publish
        self.assertFalse(rows.sudo().filtered(lambda r: not r.ack_token))
        # company live dates
        self.assertEqual(self.company.pb_wfs_live_on, first)
        self.assertEqual(self.company.pb_wfs_live_to, last)
        status = {s['key']: s for s in self.facade().load()['steps']}
        self.assertEqual(status['live']['state'], 'done')
        self.assertIn('Roster published up to', status['live']['text'])
        # 13: the other company is untouched
        self.assertEqual(set(theirs.mapped('state')), {'draft'})
        # notification counts are honest when mail is off
        self.assertFalse(finish['mail_enabled'])
        self.assertEqual(finish['emailed'], 0)
        self.assertEqual(finish['no_channel'], 40)

    # ============================================================ 14
    def test_14_rerun_keeps_edits_and_one_offs(self):
        first, last = self.window(4)
        Eng = self.env['pb.shift.pattern.engine'].with_user(self.manager).with_context(
            allowed_company_ids=[self.company.id])
        Eng.apply(self.five | self.six | self.nights, first, last)
        Shift = self.env['hr.shift.planning']
        target = first + timedelta(days=7)                       # same weekday next week
        while target.weekday() > 4:
            target += timedelta(days=1)
        edited = Shift.search([('employee_id', '=', self.people[3].id), ('date', '=', target)])
        self.assertEqual(len(edited), 1)
        edited.write({'shift_template_id': self.night.id})
        Grid = self.env['hr.shift.planning.grid']
        s, e = Grid._pb_shift_window(self.night, target, TZ)
        edited.write({'start_datetime': s, 'end_datetime': e})
        # a P2 one-off shift for another person on a working day
        who = self.people[4]
        self.facade().oneoff_apply([who.id], self.night.id, fields.Date.to_string(target),
                                   fields.Date.to_string(target), [0, 1, 2, 3, 4, 5, 6])
        oneoff = Shift.search([('employee_id', '=', who.id), ('date', '=', target)])
        self.assertEqual(len(oneoff), 1)
        self.assertFalse(oneoff.pb_pattern_id)
        start, finish = self.publish(4)
        self.env.invalidate_all()
        self.assertEqual((edited.state, edited.shift_template_id), ('published', self.night))
        day_rows = Shift.search([('employee_id', '=', who.id), ('date', '=', target)])
        self.assertEqual(day_rows, oneoff, 'the one-off day is not refilled')
        self.assertEqual(oneoff.state, 'published')
        total = Shift.search_count([('company_id', '=', self.company.id), ('state', '=', 'published')])
        # re-run: nothing new
        start2, finish2 = self.publish(4)
        self.assertEqual(start2['made']['created'], 0)
        self.assertEqual(finish2['published'], 0)
        self.assertIn('already published', finish2['summary'])
        self.assertEqual(Shift.search_count([('company_id', '=', self.company.id), ('state', '=', 'published')]),
                         total)

    # ============================================================ 15
    def test_15_failed_week_carries_on(self):
        Setup = type(self.env['pb.workforce.setup'])
        real = Setup._publish_chunk
        f = self.facade()
        start = f.go_live_start(4)
        run_id = start['run_id']
        week2 = fields.Date.to_date(start['weeks'][1]['from'])

        def broken(this, rows):
            if rows and rows[0].date >= week2:
                raise UserError("The roster is locked for that week")
            return real(this, rows)

        self.assertTrue(self.facade().go_live_week(run_id, 0)['ok'])
        with patch.object(Setup, '_publish_chunk', broken):
            res = self.facade().go_live_week(run_id, 1)
        self.assertFalse(res['ok'])
        self.assertIn('Week 2', res['sentence'])
        self.assertIn('locked for that week', res['sentence'])
        self.assertIn('Carry on', res['sentence'])
        Shift = self.env['hr.shift.planning']
        w1 = Shift.search([('company_id', '=', self.company.id), ('date', '<', week2),
                           ('date', '>=', self.today())])
        w2 = Shift.search([('company_id', '=', self.company.id), ('date', '>=', week2),
                           ('date', '<=', week2 + timedelta(days=6))])
        self.assertTrue(w1 and set(w1.mapped('state')) == {'published'}, 'week 1 stays published')
        self.assertTrue(w2 and set(w2.mapped('state')) == {'draft'}, 'week 2 rolled back whole')
        run = self.env['pb.workforce.setup.run'].browse(run_id)
        self.assertEqual(run.failed_index, 1)
        resume = self.facade().go_live_resume()
        self.assertEqual((resume['run_id'], resume['failed_index'], resume['done']), (run_id, 1, [0]))
        with self.assertRaisesRegex(UserError, 'Week 2 is not published yet'):
            self.facade().go_live_finish(run_id)
        for i in (1, 2, 3):
            self.assertTrue(self.facade().go_live_week(run_id, i)['ok'])
        self.assertEqual(self.facade().go_live_week(run_id, 1)['published'], 0, 'a done week is not redone')
        finish = self.facade().go_live_finish(run_id)
        self.assertGreater(finish['published'], 0)
        self.assertFalse(Shift.search_count([('company_id', '=', self.company.id), ('state', '=', 'draft'),
                                             ('date', '>=', self.today())]))
        self.assertFalse(self.facade().go_live_resume())

    # ============================================================ 16
    def test_16_officer_refused_on_every_write(self):
        conn = self._connector('Officer gate')
        f = self.facade(self.officer)
        calls = [
            lambda: f.add_day_off('2027-03-03'),
            lambda: f.remove_day_off(1),
            lambda: f.remove_days_off([1]),
            lambda: f.restore_days_off([{'date': '2027-03-03'}]),
            lambda: f.add_suggested(2027),
            lambda: f.confirm_holidays(2027),
            lambda: f.clock_invite(conn.id),
            lambda: f.clock_add('X'),
            lambda: f.clock_details(conn.id),
            lambda: f.confirm_clocks(),
            lambda: f.go_live_start(4),
            lambda: f.go_live_week(1, 0),
            lambda: f.go_live_finish(1),
        ]
        for call in calls:
            with self.assertRaises(AccessError):
                call()
        # reads work for an officer
        self.assertTrue(f.holidays(2027)['days'] == [])
        self.assertIn('clocks', f.clocks())
        self.assertFalse(f.go_live_resume())

    # ============================================================ 17
    def test_17_scale_700_people(self):
        emps = self.env['hr.employee'].create([{'name': 'Scale %03d' % i, 'company_id': self.company.id,
                                                'tz': TZ} for i in range(700)])
        pat = self._pattern('Scale six days', {k: self.day for k in range(6)})
        self.env['pb.shift.pattern.member'].create([{
            'pattern_id': pat.id, 'team_id': pat.team_ids[:1].id, 'employee_id': e.id} for e in emps])
        (self.five | self.six | self.nights).write({'active': False})
        self.free.active = False
        self.env.flush_all()
        f = self.facade()
        t0 = timer.time()
        data = f.live_check(4)
        t_check = timer.time() - t0
        self.assertTrue(data['can_publish'], data['steps'])
        t0 = timer.time()
        start = self.facade().go_live_start(4)
        t_start = timer.time() - t0
        timings, queries = [], []
        for i in range(len(start['weeks'])):
            f = self.facade()
            q0 = self.env.cr.sql_log_count
            t0 = timer.time()
            res = f.go_live_week(start['run_id'], i)
            timings.append((round(timer.time() - t0, 2), res['published']))
            queries.append(self.env.cr.sql_log_count - q0)
            self.assertTrue(res['ok'])
        finish = self.facade().go_live_finish(start['run_id'])
        _logger.info('WFSETUP P4 case 17: %s rows for %s people; live_check %.2f s; go_live_start %.2f s '
                     '(made %s); weeks (s, rows) %s; queries per week %s',
                     finish['published'], finish['people'], t_check, t_start, start['made'], timings, queries)
        self.assertEqual(finish['people'], 700)
        self.assertEqual(finish['published'], data['plan']['shifts'])
        for (secs, n), q in zip(timings, queries):
            self.assertLess(secs, 60, 'one week call stays well inside a request')

    # ============================================================ carry-over (a)
    def test_19_moved_row_takes_its_new_day_type(self):
        Shift = self.env['hr.shift.planning']
        monday = self.monday + timedelta(days=21)
        five = self.people[0]                                     # Mon-Fri
        row = self.roster(five, monday)
        self.assertEqual(row.pb_day_kind, 'weekday')
        Grid = self.env['hr.shift.planning.grid']
        sat = monday + timedelta(days=5)
        s, e = Grid._pb_shift_window(self.day, sat, TZ)
        row.with_user(self.manager).write({'date': sat, 'start_datetime': s, 'end_datetime': e})
        self.assertEqual((row.pb_day_kind, row.pb_day_kind_manual), ('weekend', False), 'moved to a day off')
        # another person who works Saturdays
        row.with_user(self.manager).write({'employee_id': self.people[20].id})
        self.assertEqual(row.pb_day_kind, 'weekday')
        # a hand-set row keeps its choice when moved
        hand = self.roster(five, monday, pb_day_kind='weekday')
        hand.write({'date': sat, 'start_datetime': s, 'end_datetime': e})
        self.assertEqual((hand.pb_day_kind, hand.pb_day_kind_manual), ('weekday', True))
        # a calculated row is left alone
        calc = self.roster(five, monday + timedelta(days=1))
        calc.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_calculation_status': 'Preview'})
        sun = monday + timedelta(days=6)
        s, e = Grid._pb_shift_window(self.day, sun, TZ)
        calc.write({'date': sun, 'start_datetime': s, 'end_datetime': e})
        self.assertEqual(calc.pb_day_kind, 'weekday')
        # an explicit day type in the same write wins (and is a choice by hand)
        other = self.roster(five, monday + timedelta(days=2))
        other.write({'date': sun, 'start_datetime': s, 'end_datetime': e, 'pb_day_kind': 'holiday'})
        self.assertEqual((other.pb_day_kind, other.pb_day_kind_manual), ('holiday', True))
        self.assertEqual(Shift.search_count([('id', 'in', (row | hand | calc | other).ids)]), 4)
