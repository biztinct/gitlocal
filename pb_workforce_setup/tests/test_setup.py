# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P1 — the Workforce setup facade (handover §4, cases 1-17)."""

from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install', 'wfsetup')
class TestWorkforceSetup(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Setup test company'})
        cls.other = cls.env['res.company'].create({'name': 'Other setup company'})
        cls.manager = new_test_user(
            cls.env, login='wfsetup_test_manager',
            groups='hr_attendance.group_hr_attendance_manager,hr.group_hr_manager',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id, cls.other.id])])
        cls.officer = new_test_user(
            cls.env, login='wfsetup_test_officer',
            groups='hr_attendance.group_hr_attendance_officer', company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])])
        cls.basic = new_test_user(
            cls.env, login='wfsetup_test_basic', groups='base.group_user',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])])
        Shift = cls.env['hr.shift.template']
        cls.day = Shift.create({'name': 'Setup day', 'code': 'SUD', 'start_hour': 7.5,
                                'end_hour': 16.5, 'break_duration': 1, 'color': 1,
                                'company_id': cls.company.id})
        cls.night = Shift.create({'name': 'Setup night', 'code': 'SUN', 'start_hour': 19.5,
                                  'end_hour': 4.5, 'break_duration': 1, 'is_overnight': True,
                                  'shift_type': 'night', 'company_id': cls.company.id})
        cls.foreign = Shift.create({'name': 'Other company day', 'code': 'OCD', 'start_hour': 8,
                                    'end_hour': 17, 'company_id': cls.other.id})
        cls.emp_a = cls.env['hr.employee'].create({'name': 'Setup Anna', 'company_id': cls.company.id})
        cls.emp_b = cls.env['hr.employee'].create({'name': 'Setup Binh', 'company_id': cls.company.id})
        cls.emp_c = cls.env['hr.employee'].create({'name': 'Setup Chi', 'company_id': cls.company.id})

    # ------------------------------------------------------------ helpers
    def facade(self, user=None, companies=None):
        self.env.flush_all()
        self.env.invalidate_all()
        return self.env['pb.workforce.setup'].with_user(user or self.manager).with_context(
            allowed_company_ids=companies or [self.company.id])

    def today(self):
        return fields.Date.context_today(self.facade())

    def monday(self):
        today = self.today()
        return today - timedelta(days=today.weekday())

    def pattern(self, name, cycle=7, start=None, slots=None, company=None, offsets=(0,)):
        rec = self.env['pb.shift.pattern'].create({
            'name': name, 'company_id': (company or self.company).id,
            'start_date': start or self.monday(), 'cycle_days': cycle,
            'slot_ids': [(0, 0, {'day_index': k, 'template_id': t.id}) for k, t in (slots or {}).items()],
        })
        for i, off in enumerate(offsets):
            self.env['pb.shift.pattern.team'].create({
                'pattern_id': rec.id, 'name': 'Team %s' % 'ABCDEFGH'[i],
                'sequence': (i + 1) * 10, 'offset_days': off})
        return rec

    def member(self, pattern, emp, team=None, date_from=False, date_to=False):
        return self.env['pb.shift.pattern.member'].create({
            'pattern_id': pattern.id, 'team_id': (team or pattern.team_ids[:1]).id,
            'employee_id': emp.id, 'date_from': date_from, 'date_to': date_to})

    def grid(self, week):
        """Monday-start week: days 0-4 = shift, weekend off."""
        return [week.id] * 5 + [False, False]

    # ------------------------------------------------------------ 1
    def test_01_load_gates_and_steps(self):
        with self.assertRaises(AccessError):
            self.facade(self.basic).load()
        self.assertFalse(self.facade(self.officer).load()['can_edit'])
        data = self.facade().load()
        self.assertTrue(data['can_edit'])
        self.assertEqual([s['key'] for s in data['steps']],
                         ['shifts', 'weeks', 'people', 'rules', 'holidays', 'clocks', 'live'])
        self.assertEqual(data['company']['id'], self.company.id)
        self.assertEqual([c['name'] for c in data['colors']],
                         ['indigo', 'teal', 'amber', 'blue', 'rose', 'green'])
        for step in data['steps']:
            self.assertIn(step['state'], ('done', 'warn', 'todo'))
            self.assertTrue(step['text'])

    # ------------------------------------------------------------ 2
    def test_02_create_overnight_shift(self):
        row = self.facade().save_shift({'name': 'Late night', 'start': '22:00', 'end': '06:00',
                                        'break_minutes': 30, 'color': 'blue'})
        rec = self.env['hr.shift.template'].browse(row['id'])
        self.assertTrue(rec.is_overnight)
        self.assertAlmostEqual(rec.break_duration, 0.5)
        self.assertEqual(rec.company_id, self.company)
        self.assertTrue(rec.code)
        self.assertEqual(rec.shift_type, 'night')
        self.assertEqual(rec.color, 3)
        self.assertEqual(row['paid_minutes'], 450)
        self.assertEqual((row['start'], row['end'], row['color'], row['overnight']),
                         ('22:00', '06:00', 'blue', True))

    # ------------------------------------------------------------ 3
    def test_03_codes_never_collide(self):
        self.env['hr.shift.template'].create({'name': 'Shared nights', 'code': 'ND', 'start_hour': 22,
                                              'end_hour': 6, 'is_overnight': True,
                                              'shift_type': 'night', 'company_id': False})
        f = self.facade()
        one = f.save_shift({'name': 'Factory day', 'start': '07:00', 'end': '15:00'})
        two = f.save_shift({'name': 'Front desk', 'start': '09:00', 'end': '17:00'})
        three = f.save_shift({'name': 'Night duty', 'start': '22:00', 'end': '06:00'})
        self.assertEqual(one['code'], 'FD')
        self.assertEqual(two['code'], 'FD-2')
        self.assertEqual(three['code'], 'ND-2')

    # ------------------------------------------------------------ 4
    def test_04_shift_refusals(self):
        f = self.facade()
        with self.assertRaisesRegex(UserError, 'Give the shift a name'):
            f.save_shift({'name': '  ', 'start': '08:00', 'end': '17:00'})
        with self.assertRaisesRegex(UserError, 'A shift needs a start and an end that differ.'):
            f.save_shift({'name': 'Same', 'start': '08:00', 'end': '08:00'})
        with self.assertRaisesRegex(UserError, 'The break is longer than the shift.'):
            f.save_shift({'name': 'Short', 'start': '08:00', 'end': '09:00', 'break_minutes': 60})
        with self.assertRaises(UserError):
            f.save_shift({'name': 'Negative', 'start': '08:00', 'end': '09:00', 'break_minutes': -5})

    # ------------------------------------------------------------ 5
    def test_05_officer_cannot_write(self):
        week = self.pattern('Officer week', slots={0: self.day})
        f = self.facade(self.officer)
        calls = [
            lambda: f.save_shift({'name': 'X', 'start': '08:00', 'end': '17:00'}),
            lambda: f.copy_shift(self.day.id),
            lambda: f.remove_shift(self.day.id),
            lambda: f.save_week({'name': 'X', 'weeks': [[False] * 7]}),
            lambda: f.remove_week(week.id),
        ]
        for call in calls:
            with self.assertRaises(AccessError):
                call()

    # ------------------------------------------------------------ 6
    def test_06_overnight_follows_the_times(self):
        f = self.facade()
        row = f.save_shift({'name': 'Flip', 'start': '08:00', 'end': '17:00'})
        rec = self.env['hr.shift.template'].browse(row['id'])
        self.assertFalse(rec.is_overnight)
        f.save_shift({'name': 'Flip', 'start': '20:00', 'end': '04:00'}, row['id'])
        rec.invalidate_recordset()
        self.assertTrue(rec.is_overnight)
        self.assertEqual(rec.shift_type, 'morning', 'the type is derived once, on create')
        f.save_shift({'name': 'Flip', 'start': '08:00', 'end': '17:00'}, row['id'])
        rec.invalidate_recordset()
        self.assertFalse(rec.is_overnight)

    # ------------------------------------------------------------ 7
    def test_07_remove_shift(self):
        f = self.facade()
        unused = f.save_shift({'name': 'Unused', 'start': '08:00', 'end': '12:00'})
        self.assertEqual(f.remove_shift(unused['id']), {'archived': False})
        self.assertFalse(self.env['hr.shift.template'].with_context(active_test=False)
                         .browse(unused['id']).exists())

        used = f.save_shift({'name': 'Used', 'start': '08:00', 'end': '12:00'})
        self.pattern('Uses it', slots={0: self.env['hr.shift.template'].browse(used['id'])})
        with self.assertRaisesRegex(UserError, 'used in 1 working week'):
            self.facade().remove_shift(used['id'])

        rostered = f.save_shift({'name': 'Rostered', 'start': '08:00', 'end': '12:00'})
        day = self.today()
        self.env['hr.shift.planning'].create({
            'employee_id': self.emp_a.id, 'shift_template_id': rostered['id'], 'date': day,
            'start_datetime': datetime.combine(day, datetime.min.time()) + timedelta(hours=8),
            'end_datetime': datetime.combine(day, datetime.min.time()) + timedelta(hours=12),
            'company_id': self.company.id})
        self.assertEqual(self.facade().remove_shift(rostered['id']), {'archived': True})
        rec = self.env['hr.shift.template'].with_context(active_test=False).browse(rostered['id'])
        self.assertTrue(rec.exists())
        self.assertFalse(rec.active)

    # ------------------------------------------------------------ 8
    def test_08_copy_shift(self):
        row = self.facade().copy_shift(self.night.id)
        rec = self.env['hr.shift.template'].browse(row['id'])
        self.assertEqual(rec.name, 'Setup night (copy)')
        self.assertNotEqual(rec.code, self.night.code)
        self.assertEqual((rec.start_hour, rec.end_hour, rec.break_duration, rec.color),
                         (self.night.start_hour, self.night.end_hour,
                          self.night.break_duration, self.night.color))
        self.assertTrue(rec.is_overnight)
        self.assertEqual(rec.company_id, self.company)

    # ------------------------------------------------------------ 9
    def test_09_week_shapes(self):
        one = self.pattern('One week', 7, slots={0: self.day, 4: self.day})
        two = self.pattern('Two weeks', 14, slots={0: self.day, 7: self.night})
        five = self.pattern('Five days', 5, slots={0: self.day})
        tuesday = self.pattern('Tuesday start', 7, start=self.monday() + timedelta(days=1),
                               slots={0: self.day})
        rows = {r['id']: r for r in self.facade().load()['weeks']}
        self.assertEqual(rows[one.id]['weeks'], [[self.day.id, False, False, False, self.day.id, False, False]])
        self.assertTrue(rows[one.id]['editable'])
        self.assertEqual(len(rows[two.id]['weeks']), 2)
        self.assertEqual(rows[two.id]['weeks'][1][0], self.night.id)
        self.assertTrue(rows[two.id]['editable'])
        for rec in (five, tuesday):
            self.assertFalse(rows[rec.id]['editable'])
            self.assertEqual(rows[rec.id]['reason'], 'This rotation does not follow whole weeks.')
        # the Tuesday-start week still displays under the right weekday
        self.assertEqual(rows[tuesday.id]['weeks'][0][1], self.day.id)
        self.assertEqual(rows[five.id]['days'], [self.day.id, False, False, False, False])
        with self.assertRaisesRegex(UserError, 'whole weeks'):
            self.facade().save_week({'name': 'Tuesday start', 'weeks': [[False] * 7]}, tuesday.id)

    # ------------------------------------------------------------ 10
    def test_10_create_week(self):
        row = self.facade().save_week({'name': 'Office week', 'weeks': [self.grid(self.day)]})
        rec = self.env['pb.shift.pattern'].browse(row['id'])
        self.assertEqual(rec.start_date, self.monday())
        self.assertEqual(rec.start_date.weekday(), 0)
        self.assertEqual(rec.cycle_days, 7)
        self.assertEqual(rec.company_id, self.company)
        self.assertEqual(len(rec.team_ids), 1)
        self.assertEqual(rec.team_ids.offset_days, 0)
        self.assertEqual({s.day_index: s.template_id.id for s in rec.slot_ids if s.template_id},
                         {0: self.day.id, 1: self.day.id, 2: self.day.id, 3: self.day.id, 4: self.day.id})
        self.assertFalse(rec.slot_ids.filtered(lambda s: s.day_index in (5, 6) and s.template_id))
        self.assertEqual(row['weeks'], [self.grid(self.day)])
        self.assertEqual(row['minutes_per_week'], [5 * 480])

    # ------------------------------------------------------------ 11
    def test_11_edit_keeps_teams_and_people(self):
        rec = self.pattern('Rotation', 14, slots={k: self.day for k in range(5)}, offsets=(0, 7))
        team_a, team_b = rec.team_ids
        members = self.member(rec, self.emp_a, team_a) | self.member(rec, self.emp_b, team_b) \
            | self.member(rec, self.emp_c, team_a)
        untouched = rec.slot_ids.filtered(lambda s: s.day_index == 1)
        team_ids, member_ids = rec.team_ids.ids, members.ids
        weeks = [self.grid(self.day), [False] * 7]
        weeks[0][0] = self.night.id
        weeks[1][2] = self.night.id
        self.facade().save_week({'name': 'Rotation', 'weeks': weeks}, rec.id)
        rec.invalidate_recordset()
        self.assertEqual(sorted(rec.team_ids.ids), sorted(team_ids))
        self.assertEqual(sorted(rec.member_ids.ids), sorted(member_ids))
        self.assertTrue(untouched.exists(), 'an unchanged day keeps its row')
        slots = {s.day_index: s.template_id.id for s in rec.slot_ids if s.template_id}
        self.assertEqual(slots[0], self.night.id)
        self.assertEqual(slots[9], self.night.id)
        self.assertEqual(slots[1], self.day.id)

    # ------------------------------------------------------------ 12
    def test_12_shrink(self):
        rec = self.pattern('Shrink me', 14, slots={0: self.day, 8: self.night})
        self.facade().save_week({'name': 'Shrink me', 'weeks': [self.grid(self.day)]}, rec.id)
        rec.invalidate_recordset()
        self.assertEqual(rec.cycle_days, 7)
        self.assertFalse(rec.slot_ids.filtered(lambda s: s.day_index >= 7))

        locked = self.pattern('Locked', 14, slots={0: self.day, 8: self.night}, offsets=(0, 7))
        before = sorted((s.day_index, s.template_id.id) for s in locked.slot_ids)
        with self.assertRaisesRegex(UserError, 'A team in this working week starts in a later week'):
            self.facade().save_week({'name': 'Locked', 'weeks': [self.grid(self.day)]}, locked.id)
        locked.invalidate_recordset()
        self.assertEqual(locked.cycle_days, 14)
        self.assertEqual(sorted((s.day_index, s.template_id.id) for s in locked.slot_ids), before)

    # ------------------------------------------------------------ 13
    def test_13_week_refusals(self):
        f = self.facade()
        with self.assertRaisesRegex(UserError, 'not available in this company'):
            f.save_week({'name': 'Foreign', 'weeks': [self.grid(self.foreign)]})
        with self.assertRaisesRegex(UserError, '1 to 8 weeks'):
            f.save_week({'name': 'Too long', 'weeks': [[False] * 7] * 9})
        with self.assertRaisesRegex(UserError, 'name'):
            f.save_week({'name': '', 'weeks': [[False] * 7]})

    # ------------------------------------------------------------ 14
    def test_14_remove_week(self):
        busy = self.pattern('Busy', slots={0: self.day})
        self.member(busy, self.emp_a)
        with self.assertRaisesRegex(UserError, '1 person works this week'):
            self.facade().remove_week(busy.id)
        self.assertTrue(busy.active)
        past = self.pattern('Past', slots={0: self.day})
        self.member(past, self.emp_b, date_from=self.today() - timedelta(days=30),
                    date_to=self.today() - timedelta(days=1))
        self.assertEqual(self.facade().remove_week(past.id), {'archived': True})
        past.invalidate_recordset()
        self.assertFalse(past.active)

    # ------------------------------------------------------------ 15
    def test_15_company_isolation(self):
        theirs = self.pattern('Their week', slots={0: self.foreign}, company=self.other)
        both = [self.company.id, self.other.id]
        data = self.facade(companies=both).load()
        self.assertNotIn(self.foreign.id, [s['id'] for s in data['shifts']])
        self.assertNotIn(theirs.id, [w['id'] for w in data['weeks']])
        self.assertIn(self.day.id, [s['id'] for s in data['shifts']])
        mine = self.pattern('My week', slots={0: self.day})
        data_b = self.facade(companies=[self.other.id, self.company.id]).load()
        self.assertIn(theirs.id, [w['id'] for w in data_b['weeks']])
        self.assertNotIn(mine.id, [w['id'] for w in data_b['weeks']])
        self.assertNotIn(self.day.id, [s['id'] for s in data_b['shifts']])
        with self.assertRaises(UserError):
            self.facade(companies=both).save_week({'name': 'X', 'weeks': [[False] * 7]}, theirs.id)
        with self.assertRaises(UserError):
            self.facade(companies=both).save_shift(
                {'name': 'X', 'start': '08:00', 'end': '17:00'}, self.foreign.id)

    # ------------------------------------------------------------ 16
    def test_16_people_status_counts_dates(self):
        week = self.pattern('Status week', slots={0: self.day})
        self.member(week, self.emp_a)
        before = self.facade().load()['steps'][2]
        self.member(week, self.emp_b, date_to=self.today() - timedelta(days=1))
        self.member(week, self.emp_c, date_from=self.today() + timedelta(days=1))
        after = self.facade().load()['steps'][2]
        self.assertEqual(after['state'], 'warn')
        self.assertEqual(after['missing'], before['missing'],
                         'a past and a future member both still have no working week today')
        self.assertGreaterEqual(after['missing'], 2)
        self.assertIn('have no working week', after['text'])

    # ------------------------------------------------------------ 17
    def test_17_person_week(self):
        slots = {k: self.day for k in range(5)}
        slots.update({7 + k: self.night for k in range(5)})
        rota = self.pattern('Day night rota', 14, slots=slots, offsets=(0, 7))
        team_b = rota.team_ids[1]
        self.member(rota, self.emp_b, team_b)
        week = self.facade().person_week(self.emp_b.id)
        self.assertEqual(week['week_name'], 'Day night rota')
        self.assertEqual(week['week_no'], 2)
        self.assertEqual([d['shift_id'] for d in week['days']], [self.night.id] * 5 + [False, False])
        self.assertEqual(week['days'][0]['start'], '19:30')

        self.member(rota, self.emp_c, rota.team_ids[0], date_from=self.today() - timedelta(days=60),
                    date_to=self.today() - timedelta(days=8))
        gone = self.facade().person_week(self.emp_c.id)
        self.assertFalse(gone['week_name'])
        self.assertEqual([d['shift_id'] for d in gone['days']], [False] * 7)

        # the default person is somebody who HAS a working week
        default = self.facade().person_week()
        self.assertEqual(default['id'], self.emp_b.id)
        people = {p['id']: p for p in self.facade().find_people('Setup')}
        self.assertTrue(people[self.emp_b.id]['has_week'])
        self.assertFalse(people[self.emp_c.id]['has_week'])
