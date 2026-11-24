# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P3 — step 4 "Late and overtime rules", the live pay example and
automatic holiday / rest-day marking (handover §4, cases 1-19).

Case 20 (the existing suites) is the run itself; the rate pin test proper
lives in pb_hr_workforce (tests/test_ot_config_resolution.py).
"""

import logging
import time as timer
from datetime import datetime, time, timedelta

import pytz

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from odoo.addons.pb_attendance_policy.engine import calculate
from odoo.addons.pb_attendance_policy.models.policy import _CALC_TOKEN

TZ = 'Asia/Ho_Chi_Minh'
GAP = "The late lines must follow on from each other with no gap."
ADVANCED = "This company uses more than one set of rules. Open the advanced rules screen."
WORKER = [{'from': 1, 'to': 9, 'hours': 0.0}, {'from': 10, 'to': 29, 'hours': 0.5},
          {'from': 30, 'to': None, 'hours': 1.0}]
MANAGER = [{'from': 1, 'to': 29, 'hours': 0.0}, {'from': 30, 'to': None, 'hours': 0.5}]
_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'wfsetup')
class TestSetupRules(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vn = cls.env.ref('base.vn')
        cls.company = cls.env['res.company'].create({'name': 'Rules test company', 'country_id': cls.vn.id})
        cls.company.resource_calendar_id.tz = TZ
        cls.other = cls.env['res.company'].create({'name': 'Other rules company', 'country_id': cls.vn.id})
        both = [(6, 0, [cls.company.id, cls.other.id])]
        cls.manager = new_test_user(
            cls.env, login='wfs3_manager',
            groups='hr_attendance.group_hr_attendance_manager,hr.group_hr_manager',
            company_id=cls.company.id, company_ids=both, tz=TZ)
        cls.att_only = new_test_user(
            cls.env, login='wfs3_att_only', groups='base.group_user,hr_attendance.group_hr_attendance_manager',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])], tz=TZ)
        cls.officer = new_test_user(
            cls.env, login='wfs3_officer', groups='hr_attendance.group_hr_attendance_officer',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])], tz=TZ)
        Shift = cls.env['hr.shift.template']
        cls.day = Shift.create({'name': 'Rules day', 'code': 'RLD', 'start_hour': 7.5, 'end_hour': 16.5,
                                'break_duration': 1.0, 'company_id': cls.company.id})
        cls.night = Shift.create({'name': 'Rules night', 'code': 'RLN', 'start_hour': 19.5, 'end_hour': 4.5,
                                  'break_duration': 1.0, 'is_overnight': True, 'shift_type': 'night',
                                  'company_id': cls.company.id})
        cls.spare = Shift.create({'name': 'Rules spare', 'code': 'RLS', 'start_hour': 9.0, 'end_hour': 13.0,
                                  'break_duration': 0.0, 'company_id': cls.company.id})
        today = fields.Date.context_today(cls.env['pb.workforce.setup'].with_user(cls.manager))
        cls.monday = today - timedelta(days=today.weekday())
        cls.week5 = cls._pattern('Rules five days', {k: cls.day for k in range(5)})
        cls.nights = cls._pattern('Rules nights', {k: cls.night for k in range(7)})
        Emp = cls.env['hr.employee']
        cls.worker = Emp.create({'name': 'Anh Worker', 'company_id': cls.company.id, 'tz': TZ,
                                 'pb_attendance_category': 'worker'})
        cls.boss = Emp.create({'name': 'Binh Manager', 'company_id': cls.company.id, 'tz': TZ,
                               'pb_attendance_category': 'manager'})
        cls.nighty = Emp.create({'name': 'Chi Night', 'company_id': cls.company.id, 'tz': TZ,
                                 'pb_attendance_category': 'worker'})
        cls.loose = Emp.create({'name': 'Dung Nogroup', 'company_id': cls.company.id, 'tz': TZ})
        cls.free = Emp.create({'name': 'Em Noweek', 'company_id': cls.company.id, 'tz': TZ,
                               'pb_attendance_category': 'worker'})
        for emp, pat in ((cls.worker, cls.week5), (cls.boss, cls.week5), (cls.loose, cls.week5),
                         (cls.nighty, cls.nights)):
            cls.env['pb.shift.pattern.member'].create({
                'pattern_id': pat.id, 'team_id': pat.team_ids[:1].id, 'employee_id': emp.id})
        cls.foreign = Emp.create({'name': 'Foreign rules person', 'company_id': cls.other.id, 'tz': TZ})

    @classmethod
    def _pattern(cls, name, slots):
        rec = cls.env['pb.shift.pattern'].create({
            'name': name, 'company_id': cls.company.id, 'start_date': cls.monday, 'cycle_days': 7,
            'slot_ids': [(0, 0, {'day_index': k, 'template_id': t.id}) for k, t in slots.items()]})
        cls.env['pb.shift.pattern.team'].create({'pattern_id': rec.id, 'name': 'Team A',
                                                 'sequence': 10, 'offset_days': 0})
        return rec

    # ------------------------------------------------------------ helpers
    def facade(self, user=None):
        self.env.flush_all()
        self.env.invalidate_all()
        return self.env['pb.workforce.setup'].with_user(user or self.manager).with_context(
            allowed_company_ids=[self.company.id])

    def today(self):
        return fields.Date.context_today(self.facade())

    def policies(self, state=None):
        domain = [('company_id', '=', self.company.id)]
        if state:
            domain.append(('state', '=', state))
        return self.env['pb.attendance.policy'].search(domain)

    def bands(self, policy, group):
        return [(b.minimum, None if b.open_ended else b.maximum, b.hours)
                for b in policy.band_ids.filtered(lambda b: b.category == group).sorted('minimum')]

    def save(self, **vals):
        return self.facade().save_rules(vals)

    def row(self, emp, day, shift=None, **extra):
        shift = shift or self.day
        Grid = self.env['hr.shift.planning.grid']
        start, end = Grid._pb_shift_window(shift, day, Grid._pb_shift_tzname(emp))
        vals = dict({'employee_id': emp.id, 'shift_template_id': shift.id, 'date': day,
                     'start_datetime': start, 'end_datetime': end, 'state': 'draft',
                     'company_id': self.company.id}, **extra)
        return self.env['hr.shift.planning'].create(vals)

    def holiday(self, day, name='Rules holiday'):
        zone = pytz.timezone(TZ)
        lo = zone.localize(datetime.combine(day, time.min)).astimezone(pytz.utc).replace(tzinfo=None)
        hi = zone.localize(datetime.combine(day, time(23, 59, 59))).astimezone(pytz.utc).replace(tzinfo=None)
        # on the company's working calendar, created then written as the
        # holidays screen does it (`pb.holidays._create_row`: the stock create
        # shifts the times into the acting user's time zone)
        far = timedelta(days=36500)
        row = self.env['resource.calendar.leaves'].create({
            'name': name, 'resource_id': False, 'calendar_id': self.company.resource_calendar_id.id,
            'time_type': 'leave', 'date_from': lo + far, 'date_to': hi + far})
        row.write({'date_from': lo, 'date_to': hi})
        return row

    def make_active(self, name):
        Policy = self.env['pb.attendance.policy']
        p = Policy.create({
            'name': name, 'company_id': self.company.id, 'tz': TZ,
            'shift_ids': [Command.create({'template_id': self.day.id, 'normal_end_offset': 9.0,
                                          'break_start_offset': 4.0, 'break_hours': 1.0})],
            'band_ids': [Command.create({'category': c, 'minimum': 0, 'open_ended': True, 'hours': 0,
                                         'confirmed': True}) for c in ('worker', 'manager')]})
        p.action_activate()
        return p

    def snapshot(self):
        self.env.flush_all()
        out = {}
        for table in ('pb_attendance_policy', 'pb_attendance_policy_band', 'pb_attendance_policy_shift',
                      'hr_shift_planning', 'hr_attendance', 'hr_overtime_config', 'hr_employee'):
            self.env.cr.execute('SELECT count(*), max(write_date), max(id) FROM %s' % table)
            out[table] = self.env.cr.fetchone()
        return out

    # ------------------------------------------------------------ 1
    def test_01_defaults_then_first_save_creates_one_draft(self):
        before = self.snapshot()
        data = self.facade().rules()
        self.assertEqual(self.snapshot(), before, 'rules() wrote something')
        self.assertEqual(data['state'], 'new')
        self.assertTrue(data['can_edit'])
        self.assertEqual(data['late']['worker'], WORKER)
        self.assertEqual(data['late']['manager'], MANAGER)
        self.assertEqual(set(data['rates']), {'normal', 'rest_day', 'holiday', 'night'})
        self.assertEqual(data['night'], {'on': False, 'from': '22:00', 'to': '06:00'})
        self.assertFalse(self.policies())
        lines = {l['shift_id']: l for l in data['shifts']}
        self.assertEqual([l['shift_id'] for l in data['shifts']][:2], [self.day.id, self.night.id],
                         'shifts used in a working week come first')
        self.assertEqual((lines[self.day.id]['break_start'], lines[self.day.id]['overtime_from']),
                         ('11:30', '16:30'), 'default: break in the middle, overtime from the end')
        self.assertFalse(lines[self.spare.id]['in_weeks'])
        self.assertIn('approval', data)
        out = self.save(clock={'before': 1.5})
        self.assertEqual(out['state'], 'draft')
        drafts = self.policies('draft')
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts.tz, TZ)
        self.assertEqual(drafts.capture_before, 1.5)
        self.assertEqual(set(drafts.shift_ids.mapped('template_id').ids), {self.day.id, self.night.id},
                         'a line for every shift used in a working week')
        self.save(clock={'after': 3})
        self.assertEqual(len(self.policies()), 1, 'the second save edits the same draft')

    # ------------------------------------------------------------ 2
    def test_02_late_lines_round_trip(self):
        out = self.save(late={'worker': WORKER, 'manager': MANAGER})
        policy = self.policies('draft')
        self.assertEqual(self.bands(policy, 'worker'),
                         [(0.0, 1.0, 0.0), (1.0, 10.0, 0.0), (10.0, 30.0, 0.5), (30.0, None, 1.0)])
        self.assertEqual(self.bands(policy, 'manager'), [(0.0, 1.0, 0.0), (1.0, 30.0, 0.0), (30.0, None, 0.5)])
        self.assertEqual(out['late']['worker'], WORKER)
        self.assertEqual(self.facade().rules()['late']['worker'], WORKER)
        # a `to` on the last line is dropped: it is always "or more"
        self.save(late={'worker': [{'from': 1, 'to': 9, 'hours': 0}, {'from': 10, 'to': 50, 'hours': 2}]})
        self.assertEqual(self.bands(policy, 'worker'), [(0.0, 1.0, 0.0), (1.0, 10.0, 0.0), (10.0, None, 2.0)])
        self.assertFalse(any(policy.band_ids.mapped('confirmed')), 'only Confirm confirms')

    # ------------------------------------------------------------ 3
    def test_03_gap_or_overlap_refused_nothing_saved(self):
        self.save(late={'worker': WORKER})
        policy = self.policies('draft')
        before = self.bands(policy, 'worker')
        for lines in ([{'from': 1, 'to': 9, 'hours': 0}, {'from': 11, 'to': None, 'hours': 1}],
                      [{'from': 1, 'to': 9, 'hours': 0}, {'from': 9, 'to': None, 'hours': 1}],
                      [{'from': 1, 'to': None, 'hours': 0}, {'from': 5, 'to': None, 'hours': 1}]):
            with self.assertRaises(UserError) as caught:
                self.save(late={'worker': lines})
            self.assertEqual(caught.exception.args[0], GAP)
            self.assertEqual(self.bands(policy, 'worker'), before)
        with self.assertRaises(UserError):
            self.save(late={'worker': [{'from': 1, 'to': None, 'hours': 0.3}]})     # not a quarter hour
        with self.assertRaises(UserError):
            self.save(late={'worker': [{'from': 0, 'to': None, 'hours': 1}]})
        self.assertEqual(self.bands(policy, 'worker'), before)

    # ------------------------------------------------------------ 4
    def test_04_shift_lines_clock_times(self):
        self.save(shifts=[{'shift_id': self.day.id, 'break_start': '11:30', 'overtime_from': '16:30'},
                          {'shift_id': self.night.id, 'break_start': '23:30', 'overtime_from': '04:30'}])
        rules = {r.template_id.id: r for r in self.policies('draft').shift_ids}
        self.assertEqual((rules[self.day.id].break_start_offset, rules[self.day.id].normal_end_offset), (4.0, 9.0))
        self.assertEqual((rules[self.night.id].break_start_offset, rules[self.night.id].normal_end_offset),
                         (4.0, 9.0))
        self.assertEqual(rules[self.night.id].break_hours, 1.0)
        self.save(shifts=[{'shift_id': self.day.id, 'break_start': '12:00', 'overtime_from': '15:30'}])
        self.assertEqual((rules[self.day.id].break_start_offset, rules[self.day.id].normal_end_offset), (4.5, 8.0))
        lines = {l['shift_id']: l for l in self.facade().rules()['shifts']}
        self.assertEqual((lines[self.day.id]['break_start'], lines[self.day.id]['overtime_from']), ('12:00', '15:30'))
        self.assertEqual(lines[self.night.id]['overtime_from'], '04:30')
        for bad in ('18:00', '07:30', '06:00'):
            with self.assertRaises(UserError) as caught:
                self.save(shifts=[{'shift_id': self.day.id, 'break_start': '12:00', 'overtime_from': bad}])
            self.assertEqual(caught.exception.args[0],
                             "Overtime must start after the shift starts and no later than it ends.")
        with self.assertRaises(UserError):
            self.save(shifts=[{'shift_id': self.day.id, 'break_start': '16:00', 'overtime_from': '16:30'}])
        self.assertEqual(rules[self.day.id].normal_end_offset, 8.0, 'a refusal saves nothing')
        # the spare shift (in no working week) gets a line only once touched
        self.assertNotIn(self.spare.id, rules)
        self.save(shifts=[{'shift_id': self.spare.id, 'break_start': '11:00', 'overtime_from': '12:00',
                           'touched': True}])
        spare = self.policies('draft').shift_ids.filtered(lambda r: r.template_id == self.spare)
        self.assertEqual(spare.normal_end_offset, 3.0)

    # ------------------------------------------------------------ 5
    def test_05_step1_break_resyncs_draft_only(self):
        active = self.make_active('Rules in use')
        self.facade().change_rules()
        draft = self.policies('draft')
        self.assertEqual(len(draft), 1)
        line = draft.shift_ids.filtered(lambda r: r.template_id == self.day)
        self.assertEqual(line.break_hours, 1.0)
        self.facade().save_shift({'name': 'Rules day', 'start': '07:30', 'end': '16:30', 'break_minutes': 30},
                                 self.day.id)
        self.env.invalidate_all()
        self.assertEqual(line.break_hours, 0.5)
        self.assertEqual(active.shift_ids.break_hours, 1.0, 'the rules in use never change')
        # a shorter shift pulls times that no longer fit back inside it
        self.facade().save_shift({'name': 'Rules day', 'start': '07:30', 'end': '13:30', 'break_minutes': 30},
                                 self.day.id)
        self.env.invalidate_all()
        self.assertEqual(line.normal_end_offset, 6.0)
        self.assertLessEqual(line.break_start_offset + line.break_hours, 6.0)

    # ------------------------------------------------------------ 6
    def test_06_rates_pick_and_save(self):
        Config = self.env['hr.overtime.config']
        Config.search([]).write({'active': False})
        glob = Config.create({'name': 'Global holiday', 'overtime_type': 'holiday', 'rate_multiplier': 2.5,
                              'company_id': False, 'country_id': False})
        mine = Config.create({'name': 'Mine holiday', 'overtime_type': 'holiday', 'rate_multiplier': 3.0,
                              'company_id': self.company.id, 'country_id': self.vn.id})
        theirs = Config.create({'name': 'Their holiday', 'overtime_type': 'holiday', 'rate_multiplier': 4.0,
                                'company_id': self.other.id, 'country_id': self.vn.id})
        rest = Config.create({'name': 'Global rest', 'overtime_type': 'weekend', 'rate_multiplier': 2.0,
                              'company_id': False, 'country_id': False})
        rates = self.facade().rules()['rates']
        self.assertEqual(rates['holiday'], 300, 'the company row wins over the global one (pin)')
        self.assertEqual(rates['rest_day'], 200)
        before = self.snapshot()['hr_overtime_config']
        self.save(rates={'holiday': 320, 'rest_day': 210, 'night': 35, 'normal': 150})
        self.assertEqual(self.snapshot()['hr_overtime_config'], before,
                         'a rate change waits on the draft: nothing in use changes before Confirm')
        self.assertEqual(self.facade().rules()['rates']['holiday'], 320, 'the screen shows the waiting value')
        self.assertTrue(self.facade().rules()['rates_pending'])
        self.assertEqual(self.facade().pay_example(self.worker.id, 0, 0, None, 'holiday')['rate_percent'], 320)
        res = self.facade().confirm_rules()
        self.assertFalse(res['problems'], res['problems'])
        self.env.invalidate_all()
        self.assertEqual(mine.rate_multiplier, 3.2)
        self.assertEqual((glob.rate_multiplier, theirs.rate_multiplier, rest.rate_multiplier), (2.5, 4.0, 2.0),
                         'a shared row or another company\'s row is never changed')
        own_rest = Config.search([('overtime_type', '=', 'weekend'), ('company_id', '=', self.company.id)])
        self.assertEqual(len(own_rest), 1)
        self.assertEqual((own_rest.rate_multiplier, own_rest.country_id.id), (2.1, False))
        rates = self.facade().rules()['rates']
        self.assertEqual((rates['holiday'], rates['rest_day'], rates['night'], rates['normal']), (320, 210, 35, 150))
        night = Config.search([('overtime_type', '=', 'night'), ('company_id', '=', self.company.id)])
        self.assertAlmostEqual(night.rate_multiplier, 1.35)
        # what a person without a nationality actually gets: the company row too
        req = self.env['hr.overtime.request'].create({
            'employee_id': self.free.id, 'company_id': self.company.id, 'date': self.monday,
            'overtime_type': 'holiday', 'planned_hours': 1, 'reason': 'rate check'})
        self.assertEqual(req.rate_multiplier, 3.2)
        self.assertFalse(self.facade().rules()['rates_pending'])
        # a new version: rate edits wait; Discard leaves the rates in use alone
        self.facade().change_rules()
        self.save(rates={'holiday': 400})
        self.env.invalidate_all()
        self.assertEqual(mine.rate_multiplier, 3.2)
        self.facade().discard_rules()
        self.env.invalidate_all()
        self.assertEqual(mine.rate_multiplier, 3.2)
        self.assertEqual(self.facade().rules()['rates']['holiday'], 320)
        self.facade().change_rules()
        with self.assertRaises(UserError):
            self.save(rates={'normal': 90})

    # ------------------------------------------------------------ 7
    def test_07_confirm_points_everyone(self):
        today = self.today()
        future = self.row(self.worker, today + timedelta(days=7))
        future2 = self.row(self.loose, today + timedelta(days=8))
        past = self.row(self.worker, today - timedelta(days=7))
        calculated = self.row(self.boss, today + timedelta(days=9))
        calculated.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_calculation_status': 'Preview'})
        self.assertFalse((future | future2 | past | calculated).mapped('pb_policy_id'))
        self.save(late={'worker': WORKER, 'manager': MANAGER})
        res = self.facade().confirm_rules()
        self.assertFalse(res['problems'], res['problems'])
        policy = self.policies('active')
        self.assertEqual(len(policy), 1)
        self.assertTrue(all(policy.band_ids.mapped('confirmed')))
        people = self.env['hr.employee'].search([('company_id', '=', self.company.id)])
        self.assertEqual(res['people'], len(people))
        self.assertEqual(set(people.mapped('pb_attendance_policy_id').ids), {policy.id})
        self.assertEqual(self.loose.pb_attendance_category, 'worker', 'no group -> Worker')
        self.assertEqual(self.boss.pb_attendance_category, 'manager', 'a group is kept')
        self.assertFalse(self.foreign.pb_attendance_policy_id, 'another company is untouched')
        self.env.invalidate_all()
        self.assertEqual((future | future2).mapped('pb_policy_id'), policy)
        self.assertEqual(res['rows_updated'], 2)
        self.assertFalse(past.pb_policy_id)
        self.assertFalse(calculated.pb_policy_id)
        self.assertEqual(self.facade().rules()['state'], 'active')
        steps = {s['key']: s for s in self.facade().load()['steps']}
        self.assertEqual(steps['rules']['state'], 'done')
        self.assertIn('Rules confirmed for', res['summary'])

    # ------------------------------------------------------------ 8
    def test_08_confirm_refusal_rolls_back(self):
        self.save(late={'worker': WORKER, 'manager': []})
        policy = self.policies('draft')
        before = self.snapshot()
        res = self.facade().confirm_rules()
        self.assertEqual(res['problems'], ["Managers have no late lines yet."])
        self.assertEqual(self.snapshot(), before, 'nothing else changed')
        self.env.invalidate_all()
        self.assertEqual(policy.state, 'draft')
        self.assertFalse(any(policy.band_ids.mapped('confirmed')))
        self.assertFalse(self.worker.pb_attendance_policy_id)

    # ------------------------------------------------------------ 9
    def test_09_revision_flow(self):
        future = self.row(self.worker, self.today() + timedelta(days=7))
        self.save(late={'worker': WORKER, 'manager': MANAGER})
        self.facade().confirm_rules()
        first = self.policies('active')
        with self.assertRaises(UserError):
            self.save(late={'worker': WORKER})              # in use: read-only
        data = self.facade().change_rules()
        self.assertEqual(data['state'], 'revision')
        self.assertTrue(data['can_edit'])
        draft = self.policies('draft')
        self.assertEqual(len(draft), 1)
        new_lines = [{'from': 1, 'to': 4, 'hours': 0}, {'from': 5, 'to': None, 'hours': 2}]
        self.save(late={'worker': new_lines})
        self.assertEqual(self.bands(first, 'worker'),
                         [(0.0, 1.0, 0.0), (1.0, 10.0, 0.0), (10.0, 30.0, 0.5), (30.0, None, 1.0)],
                         'the rules in use are untouched while editing')
        self.assertEqual(self.facade().rules()['late']['worker'], new_lines)
        steps = {s['key']: s for s in self.facade().load()['steps']}
        self.assertEqual(steps['rules']['state'], 'warn')
        res = self.facade().confirm_rules()
        self.assertFalse(res['problems'])
        self.assertTrue(res['retired'])
        self.env.invalidate_all()
        self.assertEqual(first.state, 'retired')
        self.assertEqual(draft.state, 'active')
        self.assertEqual(self.worker.pb_attendance_policy_id, draft)
        self.assertEqual(future.pb_policy_id, draft)
        # Change, then Discard: the draft goes, the rules in use stay
        self.facade().change_rules()
        third = self.policies('draft')
        self.assertTrue(third)
        data = self.facade().discard_rules()
        self.assertEqual(data['state'], 'active')
        self.assertFalse(third.exists())
        self.assertEqual(draft.state, 'active')
        self.assertEqual(self.facade().load()['steps'][3]['state'], 'done')

    # ------------------------------------------------------------ 10
    def test_10_two_rule_sets_is_advanced(self):
        self.make_active('Rules A')
        self.make_active('Rules B')
        data = self.facade().rules()
        self.assertEqual(data['state'], 'advanced')
        self.assertFalse(data['can_edit'])
        self.assertIn(ADVANCED, data['problems'])
        f = self.facade()
        for call in (lambda: f.save_rules({'clock': {'before': 1}}), f.confirm_rules,
                     f.change_rules, f.discard_rules):
            with self.assertRaises(UserError) as caught:
                call()
            self.assertEqual(caught.exception.args[0], ADVANCED)
        # people on different rule sets is advanced too
        self.env['pb.attendance.policy'].search([('company_id', '=', self.company.id)]).filtered(
            lambda p: p.name == 'Rules B').action_retire()
        self.assertEqual(self.facade().rules()['state'], 'active')
        a = self.policies('active')
        b = self.env['pb.attendance.policy'].search([('name', '=', 'Rules B')])
        self.worker.pb_attendance_policy_id = a
        self.boss.pb_attendance_policy_id = b
        self.assertEqual(self.facade().rules()['state'], 'advanced')

    # ------------------------------------------------------------ 11
    def test_11_officer_reads_only(self):
        f = self.facade(self.officer)
        data = f.rules()
        self.assertFalse(data['can_edit'])
        example = f.pay_example(self.worker.id, 0, 0, None)
        self.assertIn('error', example)
        for call in (lambda: f.save_rules({'clock': {'before': 1}}), f.confirm_rules, f.remark_days,
                     f.change_rules, f.discard_rules):
            with self.assertRaises(AccessError):
                call()

    # ------------------------------------------------------------ 12
    def hand(self, emp_day, shift, normal_end, brk_start, brk, lines, group, in_m, out_m,
             kind='weekday', night=None):
        """The engine called by hand, exactly as facts D.3 describes."""
        zone = pytz.timezone(TZ)
        start = zone.localize(datetime.combine(emp_day, time.min) + timedelta(hours=shift.start_hour))
        span = (shift.end_hour - shift.start_hour) + (24 if shift.is_overnight else 0)
        end = start + timedelta(hours=span)
        bands = []
        for g, ls in lines.items():
            bands.append({'category': g, 'minimum': 0, 'maximum': ls[0]['from'], 'hours': 0, 'confirmed': True})
            for l in ls:
                bands.append({'category': g, 'minimum': l['from'],
                              'maximum': None if l['to'] is None else l['to'] + 1,
                              'hours': l['hours'], 'confirmed': True})
        nights = []
        if night:
            for offset in (-1, 0, 1, 2):
                midnight = datetime.combine(start.date() + timedelta(days=offset), time.min)
                a = midnight + timedelta(hours=night[0])
                b = midnight + timedelta(hours=night[1], days=1 if night[1] < night[0] else 0)
                nights.append((zone.localize(a), zone.localize(b)))
        return calculate([start + timedelta(minutes=in_m), end + timedelta(minutes=out_m)], start,
                         start + timedelta(hours=normal_end),
                         end, [(start + timedelta(hours=brk_start), start + timedelta(hours=brk_start + brk))],
                         bands, group, kind, nights)

    def same(self, got, want):
        self.assertFalse(got['error'], got.get('error'))
        for mine, theirs in (('normal_hours', 'normal_hours'), ('overtime_hours', 'overtime_hours'),
                             ('taken_off_hours', 'penalty_hours'), ('worked_hours', 'worked_hours'),
                             ('night_hours', 'night_hours')):
            self.assertAlmostEqual(got[mine], want[theirs], places=4, msg=mine)
        self.assertEqual(got['late_minutes'], int(want['late_minutes']))

    def test_12_pay_example_is_the_engine(self):
        self.save(late={'worker': WORKER, 'manager': MANAGER},
                  shifts=[{'shift_id': self.day.id, 'break_start': '11:30', 'overtime_from': '16:30'},
                          {'shift_id': self.night.id, 'break_start': '23:30', 'overtime_from': '04:30'}],
                  night={'on': True, 'from': '22:00', 'to': '06:00'})
        lines = {'worker': WORKER, 'manager': MANAGER}
        f = self.facade()
        day = self.monday
        cases = [
            (self.worker, 0, 0, 'weekday'), (self.worker, 12, 0, 'weekday'), (self.boss, 12, 0, 'weekday'),
            (self.worker, 45, 0, 'weekday'), (self.worker, 0, 60, 'weekday'), (self.worker, 0, -60, 'weekday'),
            (self.worker, -10, 0, 'weekday'), (self.worker, 0, 30, 'weekend'), (self.worker, 5, 0, 'holiday'),
        ]
        for emp, in_m, out_m, kind in cases:
            got = f.pay_example(emp.id, in_m, out_m, None, {'weekend': 'rest_day'}.get(kind, kind))
            want = self.hand(day, self.day, 9.0, 4.0, 1.0, lines, emp.pb_attendance_category, in_m, out_m, kind,
                             night=(22.0, 6.0))
            self.same(got, want)
        # absolute anchors, so the comparison above is not trivially equal
        on_time = f.pay_example(self.worker.id, 0, 0)
        self.assertEqual((on_time['worked_hours'], on_time['normal_hours'], on_time['overtime_hours']), (8.0, 8.0, 0.0))
        self.assertEqual((on_time['clock_in'], on_time['clock_out']), ('07:30', '16:30'))
        late = f.pay_example(self.worker.id, 12, 60)
        self.assertEqual((late['late_minutes'], late['taken_off_hours'], late['overtime_hours']), (12, 0.5, 1.0))
        self.assertEqual(f.pay_example(self.boss.id, 12, 0)['taken_off_hours'], 0.0, 'manager line 1-29: nothing')
        self.assertEqual(f.pay_example(self.worker.id, 45, 0)['taken_off_hours'], 1.0)
        early = f.pay_example(self.worker.id, -10, 0)
        self.assertEqual((early['worked_hours'], early['early_minutes']), (8.0, 10), 'early arrival is not paid')
        rest = f.pay_example(self.worker.id, 0, 0, None, 'rest_day')
        self.assertEqual((rest['normal_hours'], rest['overtime_hours'], rest['day_kind']), (0.0, 8.0, 'rest_day'))
        # overnight shift, night extra on
        got = f.pay_example(self.nighty.id, 0, 0)
        want = self.hand(day, self.night, 9.0, 4.0, 1.0, lines, 'worker', 0, 0, night=(22.0, 6.0))
        self.same(got, want)
        self.assertEqual(got['night_hours'], 5.5)
        self.assertEqual(got['shift_name'], 'Rules night')

    # ------------------------------------------------------------ 13
    def test_13_unsaved_values_used_nothing_written(self):
        self.save(late={'worker': WORKER, 'manager': MANAGER})
        f = self.facade()
        stored = f.rules()
        screen = dict(stored)
        screen['late'] = {'worker': [{'from': 1, 'to': 9, 'hours': 0}, {'from': 10, 'to': None, 'hours': 2}],
                          'manager': MANAGER}
        screen['shifts'] = [dict(l, overtime_from='15:30') if l['shift_id'] == self.day.id else l
                            for l in stored['shifts']]
        before = self.snapshot()
        got = f.pay_example(self.worker.id, 12, 0, screen)
        self.assertEqual(self.snapshot(), before, 'the pay example wrote something')
        self.assertEqual(got['taken_off_hours'], 2.0, 'the unsaved late line is used')
        self.assertEqual(got['overtime_hours'], 1.0, 'the unsaved overtime time is used')
        plain = f.pay_example(self.worker.id, 12, 0)
        self.assertEqual((plain['taken_off_hours'], plain['overtime_hours']), (0.5, 0.0))
        self.assertEqual(self.snapshot(), before)

    # ------------------------------------------------------------ 14
    def test_14_example_dead_ends_are_sentences(self):
        f = self.facade()
        res = f.pay_example(self.free.id, 0, 0, f.rules())
        self.assertIn('has no working week yet', res['error'])
        res = f.pay_example(self.loose.id, 0, 0, f.rules())
        self.assertIn('has no late rule yet', res['error'])
        # stored rules without a line for this person's shift
        self.env['pb.attendance.policy'].create({'name': 'Bare rules', 'company_id': self.company.id, 'tz': TZ})
        res = f.pay_example(self.worker.id, 0, 0)
        self.assertIn('has no overtime time yet', res['error'])
        self.assertEqual(f.pay_example(999999, 0, 0)['error'], "This person is no longer here. Pick someone else.")
        # an engine refusal is a sentence too, never the raw text
        res = f.pay_example(self.worker.id, 0, -600, f.rules())
        self.assertTrue(res['error'])
        self.assertNotIn('band', res['error'])
        self.assertNotIn('punch', res['error'].lower())
        # a clock-out outside the clock window is ignored by the real job: the
        # example says so instead of counting it
        res = f.pay_example(self.worker.id, 0, 180, f.rules())
        self.assertIn('outside the 2 hours', res['error'])
        self.assertEqual(res['fix'], 'rules')

    # ------------------------------------------------------------ 15
    def test_15_day_type_marked_on_create(self):
        mon = self.monday + timedelta(days=14)
        hol = mon + timedelta(days=1)
        self.holiday(hol)
        normal = self.row(self.worker, mon)
        holiday = self.row(self.worker, hol)
        rest = self.row(self.worker, mon + timedelta(days=5))             # Saturday: off in the week
        chosen = self.row(self.worker, mon + timedelta(days=2), pb_day_kind='holiday')
        chosen2 = self.row(self.worker, mon + timedelta(days=3), pb_day_kind='weekday')
        self.assertEqual((normal.pb_day_kind, normal.pb_day_kind_manual), ('weekday', False))
        self.assertEqual((holiday.pb_day_kind, holiday.pb_day_kind_manual), ('holiday', False))
        self.assertEqual((rest.pb_day_kind, rest.pb_day_kind_manual), ('weekend', False))
        self.assertEqual((chosen.pb_day_kind, chosen.pb_day_kind_manual), ('holiday', True))
        self.assertEqual((chosen2.pb_day_kind, chosen2.pb_day_kind_manual), ('weekday', True))
        # a person with no working week: their working calendar decides
        cal = self.company.resource_calendar_id
        sunday = mon + timedelta(days=6)
        self.assertFalse(cal.attendance_ids.filtered(lambda a: a.dayofweek == '6'))
        self.assertEqual(self.row(self.free, sunday).pb_day_kind, 'weekend')
        self.assertEqual(self.row(self.free, mon).pb_day_kind, 'weekday')
        # the working-week engine's rows are marked too (one batch)
        self.holiday(self.monday + timedelta(days=22), 'Engine holiday')
        self.env['pb.shift.patterns'].with_user(self.att_only).with_context(
            allowed_company_ids=[self.company.id]).make_drafts(
                [self.nights.id], fields.Date.to_string(self.monday + timedelta(days=21)), 1)
        made = self.env['hr.shift.planning'].search([('employee_id', '=', self.nighty.id),
                                                     ('date', '>=', self.monday + timedelta(days=21))])
        self.assertTrue(made)
        self.assertFalse(made.filtered(lambda r: r.pb_day_kind == 'weekend'), 'every night is a working day')

    # ------------------------------------------------------------ 16
    def test_16_manual_kept_auto_follows_holidays(self):
        day = self.today() + timedelta(days=7 - self.today().weekday() + 1)      # next Tuesday
        manual = self.row(self.worker, day)
        auto = self.row(self.boss, day)
        self.assertEqual((manual.pb_day_kind, auto.pb_day_kind), ('weekday', 'weekday'))
        manual.with_user(self.manager).write({'pb_day_kind': 'weekend'})
        self.assertTrue(manual.pb_day_kind_manual)
        self.holiday(day)
        res = self.facade().remark_days()
        self.assertEqual(res['changed']['holiday'], 1)
        self.env.invalidate_all()
        self.assertEqual(manual.pb_day_kind, 'weekend', 'set by hand: never re-marked')
        self.assertEqual((auto.pb_day_kind, auto.pb_day_kind_manual), ('holiday', False))
        again = self.facade().remark_days()
        self.assertEqual(sum(again['changed'].values()), 0)
        self.assertIn('already right', again['summary'])

    # ------------------------------------------------------------ 17
    def test_17_remark_skips_calculated_rows(self):
        day = self.today() + timedelta(days=7 - self.today().weekday() + 2)      # next Wednesday
        status = self.row(self.worker, day)
        status.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_calculation_status': 'Preview'})
        linked = self.row(self.boss, day)
        att = self.env['hr.attendance'].create({'employee_id': self.boss.id,
                                                'check_in': linked.start_datetime,
                                                'check_out': linked.end_datetime})
        linked.with_context(_attendance_calc=_CALC_TOKEN).write({'pb_attendance_id': att.id})
        plain = self.row(self.loose, day)
        self.holiday(day)
        res = self.facade().remark_days()
        self.env.invalidate_all()
        self.assertEqual(plain.pb_day_kind, 'holiday')
        self.assertEqual((status.pb_day_kind, linked.pb_day_kind), ('weekday', 'weekday'))
        self.assertEqual(res['changed']['holiday'], 1)

    # ------------------------------------------------------------ 18
    def test_18_batch_create_stays_fast(self):
        emps = self.env['hr.employee'].create([{'name': 'Batch %03d' % i, 'company_id': self.company.id,
                                                'tz': TZ} for i in range(100)])
        members = self.env['pb.shift.pattern.member'].create([{
            'pattern_id': self.week5.id, 'team_id': self.week5.team_ids[:1].id, 'employee_id': e.id}
            for e in emps[:60]])
        self.assertEqual(len(members), 60)
        start = self.monday + timedelta(days=28)
        self.holiday(start + timedelta(days=1))
        Grid = self.env['hr.shift.planning.grid']
        windows = {}

        def vals(n_days):
            out = []
            for emp in emps:
                for i in range(n_days):
                    d = start + timedelta(days=i)
                    if d not in windows:
                        windows[d] = Grid._pb_shift_window(self.day, d, TZ)
                    s, e = windows[d]
                    out.append({'employee_id': emp.id, 'shift_template_id': self.day.id, 'date': d,
                                'start_datetime': s, 'end_datetime': e, 'state': 'draft',
                                'company_id': self.company.id})
            return out

        Shift = self.env['hr.shift.planning']
        pairs_small = [(v['employee_id'], v['date']) for v in vals(3)]
        pairs_big = [(v['employee_id'], v['date']) for v in vals(30)]
        self.env.invalidate_all()
        q0 = self.env.cr.sql_log_count
        Shift._pb_day_kinds(pairs_small)
        q_small = self.env.cr.sql_log_count - q0
        self.env.invalidate_all()
        q0 = self.env.cr.sql_log_count
        t0 = timer.perf_counter()
        kinds = Shift._pb_day_kinds(pairs_big)
        t_mark = timer.perf_counter() - t0
        q_big = self.env.cr.sql_log_count - q0
        self.assertEqual(len(kinds), 3000)
        self.assertLessEqual(q_big, q_small + 6, 'queries must not grow per row (%s vs %s)' % (q_big, q_small))
        rows = vals(30)
        t0 = timer.perf_counter()
        q0 = self.env.cr.sql_log_count
        made = Shift.with_context(tracking_disable=True, mail_create_nolog=True).create(rows)
        self.env.flush_all()
        t_create = timer.perf_counter() - t0
        q_create = self.env.cr.sql_log_count - q0
        self.assertEqual(len(made), 3000)
        _logger.info('WFSETUP P3 case 18: marking 3,000 rows %.3f s, %s queries (300 rows: %s queries); '
                     'create of 3,000 rows %.2f s, %s queries', t_mark, q_big, q_small, t_create, q_create)
        self.assertLess(t_mark, 5.0)
        self.assertLess(t_create, 120.0)
        hol = made.filtered(lambda r: r.date == start + timedelta(days=1))
        self.assertEqual(set(hol.mapped('pb_day_kind')), {'holiday'})
        sat = made.filtered(lambda r: r.date.weekday() == 5 and r.employee_id in members.employee_id)
        self.assertEqual(set(sat.mapped('pb_day_kind')), {'weekend'})

    # ------------------------------------------------------------ 19
    def test_19_new_people_join_the_rules(self):
        Emp = self.env['hr.employee']
        none = Emp.create({'name': 'Joiner none', 'company_id': self.company.id})
        self.assertFalse(none.pb_attendance_policy_id)
        a = self.make_active('Rules one')
        one = Emp.create([{'name': 'Joiner one', 'company_id': self.company.id},
                          {'name': 'Joiner boss', 'company_id': self.company.id,
                           'pb_attendance_category': 'manager'}])
        self.assertEqual(one.mapped('pb_attendance_policy_id'), a)
        self.assertEqual(one.mapped('pb_attendance_category'), ['worker', 'manager'])
        elsewhere = Emp.create({'name': 'Joiner elsewhere', 'company_id': self.other.id})
        self.assertFalse(elsewhere.pb_attendance_policy_id)
        self.make_active('Rules two')
        two = Emp.create({'name': 'Joiner two', 'company_id': self.company.id})
        self.assertFalse(two.pb_attendance_policy_id)
        self.assertFalse(two.pb_attendance_category)
