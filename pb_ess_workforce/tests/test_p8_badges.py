# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""T3's manager half — the ack badge maths and the additive-payload contract."""

import os

from odoo.tests.common import tagged

from .common import EssWorkforceCase


@tagged('post_install', '-at_install')
class TestP8Badges(EssWorkforceCase):

    def _data(self):
        return self.env['hr.shift.planning.grid'].with_user(
            self.env.ref('base.user_admin')).get_schedule_data(
                self.monday.isoformat(), num_days=14)

    def _row(self, data, emp):
        rows = [r for r in data['employees'] if r['id'] == emp.id]
        return rows[0] if rows else None

    # --------------------------------------------------------- badge maths
    def test_a_person_with_nothing_published_gets_no_badge(self):
        """An empty badge on an empty row is noise, and a person with no
        published shift has not failed to confirm anything (W64)."""
        self._shift(self.emp_a, self._future_day())          # draft only
        row = self._row(self._data(), self.emp_a)
        self.assertIsNotNone(row)
        self.assertIsNone(row['ack'])

    def test_the_badge_counts_published_shifts_only(self):
        self._shift(self.emp_a, self._future_day(1), state='published')
        self._shift(self.emp_a, self._future_day(2))          # draft
        row = self._row(self._data(), self.emp_a)
        self.assertEqual(row['ack'], {'acked': 0, 'total': 1, 'all': False})

    def test_a_completed_shift_leaves_the_denominator(self):
        """A shift that has already been worked is past the point where an
        acknowledgment means anything; leaving it in would make history
        permanently red."""
        s = self._shift(self.emp_a, self._future_day(1), state='published')
        s.action_complete()
        row = self._row(self._data(), self.emp_a)
        self.assertIsNone(row['ack'])

    def test_the_badge_goes_green_only_when_the_whole_window_is_confirmed(self):
        a = self._shift(self.emp_a, self._future_day(1), state='published')
        b = self._shift(self.emp_a, self._future_day(2), state='published')
        a._ess_ack('test')
        row = self._row(self._data(), self.emp_a)
        self.assertEqual(row['ack'], {'acked': 1, 'total': 2, 'all': False})
        b._ess_ack('test')
        row = self._row(self._data(), self.emp_a)
        self.assertEqual(row['ack'], {'acked': 2, 'total': 2, 'all': True})

    def test_the_summary_counts_people_not_shifts(self):
        """Asserted as a DELTA, because this suite runs against the live demo
        world and the unfiltered roster is 200 people wide. The first live run
        came back `people: 86` — a true statement about the database and a
        useless one about the feature. What the summary has to get right is
        that two more people with two shifts each, one of them fully confirmed,
        move the four counters by 2 / 1 / 4 / 2."""
        base = self._data()['ack']
        for emp in (self.emp_a, self.emp_b):
            self._shift(emp, self._future_day(1), state='published')
            self._shift(emp, self._future_day(2), state='published')
        for s in self.env['hr.shift.planning'].sudo().search([
                ('employee_id', '=', self.emp_a.id),
                ('state', '=', 'published')]):
            s._ess_ack('test')
        summary = self._data()['ack']
        self.assertTrue(summary['shown'])
        self.assertEqual(summary['people'] - base.get('people', 0), 2)
        self.assertEqual(summary['people_done'] - base.get('people_done', 0), 1)
        self.assertEqual(summary['total'] - base.get('total', 0), 4)
        self.assertEqual(summary['acked'] - base.get('acked', 0), 2)

    def test_one_persons_ack_never_leaks_into_another_persons_badge(self):
        self._shift(self.emp_a, self._future_day(1), state='published')
        b = self._shift(self.emp_b, self._future_day(1), state='published')
        b._ess_ack('test')
        data = self._data()
        self.assertEqual(self._row(data, self.emp_a)['ack']['acked'], 0)
        self.assertEqual(self._row(data, self.emp_b)['ack']['acked'], 1)

    # ------------------------------------------------------- additive-ness
    def test_the_override_is_strictly_additive(self):
        """Every key `pb_schedule` documents is still there with its shape. The
        badge is an instrument bolted onto the read model, not a new read model
        — a phase that quietly changes a payload shape breaks a cockpit nobody
        was looking at."""
        data = self._data()
        for key in ('stats', 'coverage', 'week_start', 'week_end', 'num_days',
                    'days', 'employees', 'open_shifts', 'templates',
                    'conflicts', 'truncated', 'row_cap', 'counts'):
            self.assertIn(key, data, 'get_schedule_data lost %s' % key)
        for key in ('shifts', 'draft', 'published', 'completed', 'open',
                    'conflicts'):
            self.assertIn(key, data['counts'])
        self.assertIn('ack', data)

    def test_a_badge_failure_never_costs_the_roster(self):
        """The decorator is wrapped: an instrument that cannot be computed must
        not take the week down with it."""
        Grid = type(self.env['hr.shift.planning.grid'])
        original = Grid._ess_decorate_ack

        def boom(self, data, week_start_str, num_days):
            raise RuntimeError('read_group exploded')

        Grid._ess_decorate_ack = boom
        try:
            data = self._data()
        finally:
            Grid._ess_decorate_ack = original
        self.assertIn('employees', data)
        self.assertEqual(data['ack'], {'shown': False})

    # ----------------------------------------------------------- the client
    def test_the_cockpit_renders_the_badge_behind_a_presence_guard(self):
        """A source gate, because behaviour cannot distinguish "renders nothing
        because the key is absent" from "renders nothing because it is broken"
        (W79). The template must guard on the key, and the JS must degrade to
        the base publish call for exactly one reason and re-raise everything
        else (W40)."""
        here = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        xml = open(os.path.join(here, 'pb_schedule', 'static', 'src', 'xml',
                                'pb_schedule.xml')).read()
        self.assertIn('t-if="emp.ack"', xml,
                      'the ack badge is not guarded on the payload key')
        js = open(os.path.join(here, 'pb_schedule', 'static', 'src', 'js',
                               'pb_schedule.js')).read()
        self.assertIn('publish_shifts_notified', js)
        self.assertIn('throw missing', js,
                      'the publish fallback swallows every error, not one')
