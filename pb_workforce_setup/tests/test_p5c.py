# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P5c — the working-week engine runs inside each week's publish call.

Proof that the published roster is the same as the P4 implementation (one
engine pass over the whole window in `go_live_start`, still the code path when
somebody is on two working weeks at once): both run on the same fixture, the
old one inside a savepoint that is rolled back, and every row of this company
from today on is compared field by field.
"""

import logging
import time as timer
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_shift_patterns.models.shift_planning import pattern_signature

from .test_golive import TZ, GoLiveFixture

_logger = logging.getLogger(__name__)


class _Undo(Exception):
    pass


@tagged('post_install', '-at_install', 'wfsetup')
class TestP5cWeekByWeek(GoLiveFixture, TransactionCase):

    def _scenario(self):
        """3 working weeks / 40 people / 4 weeks, with: drafts already made
        for weeks 2-3, a company day off (week 2), a hand-edited draft, two
        one-off shifts (one on a pre-made day, one on a day the engine still
        has to fill), a hand-made rest-day shift, a shift published before, a
        draft the working week no longer wants, and — on the week 1 / week 2
        boundary — a stale draft on Monday that overlaps the new Sunday night
        shift (one pass removes it before judging Sunday)."""
        m = self.monday
        Shift = self.env['hr.shift.planning']
        Grid = self.env['hr.shift.planning.grid']
        early = self.env['hr.shift.template'].create({
            'name': 'Live early', 'code': 'LVE', 'start_hour': 3.0, 'end_hour': 11.0,
            'break_duration': 1.0, 'company_id': self.company.id})
        Eng = self.env['pb.shift.pattern.engine'].with_user(self.manager).with_context(
            allowed_company_ids=[self.company.id])
        Eng.apply(self.five | self.six | self.nights, m + timedelta(days=7), m + timedelta(days=20))
        self.facade().add_day_off(fields.Date.to_string(m + timedelta(days=9)))
        # hand-edited draft
        edited = Shift.search([('employee_id', '=', self.people[3].id), ('date', '=', m + timedelta(days=15))])
        self.assertEqual(len(edited), 1)
        s, e = Grid._pb_shift_window(self.night, edited.date, TZ)
        edited.write({'shift_template_id': self.night.id, 'start_datetime': s, 'end_datetime': e})
        # one-offs: night shifts on day-shift days (the day must not be refilled)
        for who, day in ((self.people[4], m + timedelta(days=16)), (self.people[5], m + timedelta(days=22))):
            self.facade().oneoff_apply([who.id], self.night.id, fields.Date.to_string(day),
                                       fields.Date.to_string(day), [0, 1, 2, 3, 4, 5, 6])
        # a hand-made shift on a five-day person's Sunday
        self.roster(self.people[0], m + timedelta(days=13))
        # published before
        Shift.search([('employee_id', '=', self.people[6].id), ('date', '=', m + timedelta(days=8))]).sudo().action_publish()
        # a draft the five-day week no longer wants (a Saturday), untouched
        sat = m + timedelta(days=12)
        s, e = Grid._pb_shift_window(self.day, sat, TZ)
        Shift.create({'employee_id': self.people[1].id, 'shift_template_id': self.day.id, 'date': sat,
                      'start_datetime': s, 'end_datetime': e, 'state': 'draft', 'company_id': self.company.id,
                      'pb_pattern_id': self.five.id,
                      'pb_pattern_sig': pattern_signature(self.people[1].id, self.day.id, sat, s, e)})
        # the boundary: an untouched early draft on week 2's Monday for a night
        # worker overlaps week 1's Sunday night (19:30 to 04:30)
        mon2, night_person = m + timedelta(days=7), self.people[33]
        s, e = Grid._pb_shift_window(early, mon2, TZ)
        Shift.create({'employee_id': night_person.id, 'shift_template_id': early.id, 'date': mon2,
                      'start_datetime': s, 'end_datetime': e, 'state': 'draft', 'company_id': self.company.id,
                      'pb_pattern_id': self.nights.id,
                      'pb_pattern_sig': pattern_signature(night_person.id, early.id, mon2, s, e)})
        # the other company's drafts
        self.roster(self.foreign, self.today(), shift=self.other_day, company=self.other)
        return night_person, early

    def _result(self):
        self.env.flush_all()
        self.env.invalidate_all()
        rows = self.env['hr.shift.planning'].search([('date', '>=', self.today()),
                                                     ('company_id', 'in', (self.company | self.other).ids)])
        out = []
        for r in rows:
            out.append((r.company_id.id, r.employee_id.id, r.date, r.shift_template_id.id, r.start_datetime,
                        r.end_datetime, r.state, r.pb_day_kind, r.pb_day_kind_manual, r.pb_pattern_id.id,
                        r.pb_pattern_sig or '', r.pb_policy_id.id,
                        bool(r.sudo().ack_token) if 'ack_token' in r._fields else None))
        return sorted(out, key=repr)

    def _publish_day_by_day(self, weeks=4):
        """What the screen does: make each day, then publish each week."""
        start = self.facade().go_live_start(weeks)
        for i, wk in enumerate(start['weeks']):
            day = fields.Date.to_date(wk['from'])
            while day <= fields.Date.to_date(wk['to']):
                res = self.facade().go_live_make(start['run_id'], i, fields.Date.to_string(day))
                self.assertTrue(res['ok'], res)
                day += timedelta(days=1)
            res = self.facade().go_live_week(start['run_id'], i)
            self.assertTrue(res['ok'], res)
        return start, self.facade().go_live_finish(start['run_id'])

    def _rolled_back(self, publish):
        """Run a publish, read the result, undo it."""
        try:
            with self.env.cr.savepoint():
                start, finish = publish()
                run = self.env['pb.workforce.setup.run'].browse(start['run_id'])
                out = (self._result(), self._finish(finish), run.per_week, start['made'])
                raise _Undo
        except _Undo:
            pass
        self.env.invalidate_all()
        return out

    @staticmethod
    def _finish(finish):
        return {k: finish[k] for k in ('published', 'people', 'from', 'to', 'made', 'summary', 'no_channel')}

    def test_01_week_by_week_publishes_the_same_roster(self):
        night_person, early = self._scenario()
        Setup = type(self.env['pb.workforce.setup'])
        before = self._result()
        # the P4 path: one engine pass over the window at the start
        with patch.object(Setup, '_live_split_ok', lambda this, *a: False):
            old, old_finish, per_week, made = self._rolled_back(lambda: self.publish(4))
        self.assertFalse(per_week)
        self.assertGreater(made['created'], 0)
        self.assertEqual(self._result(), before, 'the old run was rolled back')
        # P5c, week by week (go_live_week makes its own week)
        new, new_finish, per_week, made = self._rolled_back(lambda: self.publish(4))
        self.assertTrue(per_week)
        self.assertEqual(made, {'created': 0, 'removed': 0, 'skipped': 0}, 'start makes nothing')
        self.assertEqual(len(new), len(old))
        self.assertEqual(new, old, 'week by week: the same rows, field by field')
        self.assertEqual(new_finish, old_finish)
        self.assertEqual(self._result(), before)
        # P5c, day by day, as the screen does it
        start, finish = self._publish_day_by_day(4)
        run = self.env['pb.workforce.setup.run'].browse(start['run_id'])
        self.assertTrue(run.per_week)
        self.assertEqual(run.made_to, run.last)
        self.assertEqual(self._result(), old, 'day by day: the same rows, field by field')
        self.assertEqual(self._finish(finish), old_finish)
        self.assertGreater(finish['made']['removed'], 1, 'the stale drafts were taken away')
        # the boundary case: Sunday night of week 1 was made, the early draft is gone
        Shift = self.env['hr.shift.planning']
        sunday = self.monday + timedelta(days=6)
        self.assertEqual(Shift.search([('employee_id', '=', night_person.id), ('date', '=', sunday)]).mapped(
            'shift_template_id'), self.night)
        self.assertFalse(Shift.search_count([('shift_template_id', '=', early.id)]))

    def test_02_two_working_weeks_at_once_runs_in_one_pass(self):
        """Somebody on two working weeks on the same day: the start runs the
        engine over the whole window (the order of two working weeks cannot
        be kept week by week)."""
        both = self.people[0]
        self.env['pb.shift.pattern.member'].create({
            'pattern_id': self.nights.id, 'team_id': self.nights.team_ids[:1].id, 'employee_id': both.id})
        f = self.facade()
        first, last = self.window(4)
        self.assertFalse(f._live_split_ok(f._live_patterns(), first, last))
        start, finish = self.publish(4)
        self.assertFalse(self.env['pb.workforce.setup.run'].browse(start['run_id']).per_week)
        self.assertGreater(start['made']['created'], 0)
        self.assertGreater(finish['published'], 0)
        # dates that do not meet keep the week-by-week publish
        member = self.nights.member_ids.filtered(lambda x: x.employee_id == both)
        member.write({'date_from': last + timedelta(days=1)})
        self.assertTrue(self.facade()._live_split_ok(self.facade()._live_patterns(), first, last))

    def test_03_failed_make_rolls_back_and_carries_on(self):
        """The engine failing inside a week's call: nothing of that week is
        made or published, earlier weeks stay, Carry on makes and publishes."""
        Setup = type(self.env['pb.workforce.setup'])
        real = Setup._live_make
        start = self.facade().go_live_start(4)
        run_id = start['run_id']
        self.assertTrue(self.facade().go_live_week(run_id, 0)['ok'])

        def broken(this, patterns, first, last, next_day=None):
            real(this, patterns, first, last, next_day)
            from odoo.exceptions import UserError
            raise UserError("The roster is locked for that week")

        with patch.object(Setup, '_live_make', broken):
            res = self.facade().go_live_week(run_id, 1)
        self.assertFalse(res['ok'])
        self.assertIn('locked for that week', res['sentence'])
        wk = start['weeks'][1]
        Shift = self.env['hr.shift.planning']
        self.assertFalse(Shift.search_count([('company_id', '=', self.company.id),
                                             ('date', '>=', wk['from']), ('date', '<=', wk['to'])]),
                         'the failed make left nothing behind')
        run = self.env['pb.workforce.setup.run'].browse(run_id)
        self.assertEqual((run.done, run.made_to, run.failed_index),
                         ([0], fields.Date.to_date(start['weeks'][0]['to']), 1))
        for i in (1, 2, 3):
            self.assertTrue(self.facade().go_live_week(run_id, i)['ok'])
        finish = self.facade().go_live_finish(run_id)
        self.assertEqual(finish['people'], 40)
        self.assertFalse(Shift.search_count([('company_id', '=', self.company.id), ('state', '=', 'draft'),
                                             ('date', '>=', self.today())]))

    def test_04_officer_cannot_make(self):
        from odoo.exceptions import AccessError
        with self.assertRaises(AccessError):
            self.facade(self.officer).go_live_make(1, 0)

    def test_05_scale_700_people_day_by_day(self):
        """The P4 case 17 company, published the way the screen does it: the
        first progress step must come within seconds."""
        emps = self.env['hr.employee'].create([{'name': 'Scale %03d' % i, 'company_id': self.company.id,
                                                'tz': TZ} for i in range(700)])
        pat = self._pattern('Scale six days', {k: self.day for k in range(6)})
        self.env['pb.shift.pattern.member'].create([{
            'pattern_id': pat.id, 'team_id': pat.team_ids[:1].id, 'employee_id': e.id} for e in emps])
        (self.five | self.six | self.nights).write({'active': False})
        self.free.active = False
        self.env.flush_all()
        plan = self.facade().live_check(4)['plan']
        t0 = timer.time()
        start = self.facade().go_live_start(4)
        t_start = timer.time() - t0
        steps, t_first = [], None
        for i, wk in enumerate(start['weeks']):
            day = fields.Date.to_date(wk['from'])
            while day <= fields.Date.to_date(wk['to']):
                t1 = timer.time()
                self.assertTrue(self.facade().go_live_make(start['run_id'], i, fields.Date.to_string(day))['ok'])
                steps.append(round(timer.time() - t1, 2))
                if t_first is None:
                    t_first = timer.time() - t0
                day += timedelta(days=1)
            t1 = timer.time()
            self.assertTrue(self.facade().go_live_week(start['run_id'], i)['ok'])
            steps.append(('publish', round(timer.time() - t1, 2)))
        finish = self.facade().go_live_finish(start['run_id'])
        total = timer.time() - t0
        _logger.info('WFSETUP P5c scale: %s rows for %s people; start %.2f s; first step after %.2f s; '
                     'total %.1f s; steps %s', finish['published'], finish['people'], t_start, t_first, total, steps)
        self.assertEqual(finish['people'], 700)
        self.assertEqual(finish['published'], plan['shifts'])
        self.assertLess(t_start, 5)
