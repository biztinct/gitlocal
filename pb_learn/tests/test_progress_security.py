# -*- coding: utf-8 -*-
"""Learner state is real data about a person. It is scoped like it."""
import os

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestProgressSecurity(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.alice = Users.create({
            'name': 'Alice Learner', 'login': 'learn_alice_test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.bob = Users.create({
            'name': 'Bob Learner', 'login': 'learn_bob_test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })
        cls.station = cls.env['learn.station'].sudo().search([], limit=1)

    def test_01_a_learner_records_their_own_progress(self):
        env = self.env(user=self.alice)
        env['learn.progress'].record(self.station.key, {'state': 'in_progress', 'step_index': 3})
        mine = env['learn.progress'].my_progress()
        self.assertEqual(mine[self.station.key]['step_index'], 3)

    def test_02_one_learner_cannot_see_anothers(self):
        self.env(user=self.alice)['learn.progress'].record(
            self.station.key, {'state': 'done'})
        seen = self.env(user=self.bob)['learn.progress'].search(
            [('user_id', '=', self.alice.id)])
        self.assertFalse(seen, "Bob can read Alice's learning progress")
        self.assertEqual(self.env(user=self.bob)['learn.progress'].my_progress(), {})

    def test_03_the_event_log_is_append_only(self):
        env = self.env(user=self.alice)
        env['learn.event'].log('journey_open', station_key=self.station.key)
        row = env['learn.event'].search([('user_id', '=', self.alice.id)], limit=1)
        self.assertTrue(row)
        with self.assertRaises(AccessError):
            row.write({'detail': 'rewritten'})
        with self.assertRaises(AccessError):
            row.unlink()

    def test_04_unknown_event_kinds_are_dropped_not_raised(self):
        """A stale browser tab emitting a retired event name must never break
        the lesson someone is in the middle of."""
        env = self.env(user=self.alice)
        before = env['learn.event'].search_count([('user_id', '=', self.alice.id)])
        self.assertFalse(env['learn.event'].log('not_a_real_kind'))
        after = env['learn.event'].search_count([('user_id', '=', self.alice.id)])
        self.assertEqual(before, after)

    def test_05_events_carry_no_free_text(self):
        """The log must not be able to become a shadow store of pay data.

        An event row that can hold free text eventually holds an employee's
        name and their net pay, and then a measurement table is a payroll
        record with none of a payroll record's access rules.
        """
        env = self.env(user=self.alice)
        env['learn.event'].log('quiz_answer', station_key=self.station.key,
                               detail='x' * 500)
        row = env['learn.event'].search(
            [('user_id', '=', self.alice.id), ('kind', '=', 'quiz_answer')], limit=1)
        self.assertLessEqual(len(row.detail or ''), 64)
        text_fields = [
            n for n, f in env['learn.event']._fields.items()
            if f.type in ('text', 'html')
        ]
        self.assertFalse(text_fields,
                         "learn.event has an unbounded text field: %s" % text_fields)

    def test_06_a_coach_miss_never_logs_the_question(self):
        """The privacy rule, asserted against the source that would break it.

        health_learn logs the first 40 characters of an unanswered question. On
        a payroll help box that is "why is Nguyễn Thị Mai's net only 4m" — a
        named employee and their pay — landing in a table with no retention
        policy and no way for that person to know it is there. pb_learn
        deliberately diverges: the miss is logged with the intent key or an
        empty string, so the per-screen miss RATE survives (screen is logged on
        every event) and the question text never leaves the browser.

        Checked against the source because the behaviour lives in JS: the
        server cannot observe what the frontend chose not to send.
        """
        path = os.path.join(get_module_path('pb_learn'),
                            'static/src/coach/coach.js')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        call = src.split('this._log(answer.matched')[1].split(';')[0]
        for banned in ('q.slice', 'question', 'this.state.question'):
            self.assertNotIn(banned, call,
                             "the coach_miss log carries the learner's question: %s" % call)
