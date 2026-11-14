# -*- coding: utf-8 -*-
"""WDGAP QF1 — "Approve selected" in the one Approvals inbox (cases 1-9).

The rule under test: approving several at once can never do what one press of
Approve by the same person could not. Every case calls the facade as a named
person and then reads the engine's own records (decisions, seats, states).
"""
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.biz_approval_workflow.models.process import (
    BULK_DEFAULT_KEYS, BULK_SEEDED_PARAM)

from .common import MatrixCase


@tagged('post_install', '-at_install', 'wdgap_qf1')
class TestWdgapQf1Bulk(MatrixCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # the "Other request" process stands in for a kind that allows
        # several at once (leave, overtime, …); it is not a money process
        cls.process.sudo().write({'money': False, 'bulk_ok': True})
        cls.money_process = cls.env['biz.approval.process'].sudo().create({
            'key': 'wdgap_qf1_money', 'name': 'QF1 money out', 'area': 'money',
            'money': True})

    def setUp(self):
        super().setUp()
        held = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id', '=', self.role_approver.id), ('active', '=', True)])
        held.write({'user_id': self.fin.id})
        self.held = held

    # ------------------------------------------------------------ helpers
    def _inbox(self, person):
        return self.Inbox.with_user(person).with_company(self.company)

    def _req(self, made):
        return self.env['biz.approval.request'].sudo().browse(
            made['request_id'])

    def _card(self, person, request):
        return self._inbox(person)._card(request)

    def _decisions(self, requests):
        return self.env['biz.approval.decision'].sudo().search_count(
            [('request_id', 'in', requests.ids)])

    def _shape(self, request):
        request.invalidate_recordset()
        return (request.state,
                [(s.sequence, s.status) for s in request.step_ids.sorted('sequence')],
                sorted((seat.status, seat.acting_user_id.id)
                       for seat in request.step_ids.seat_ids))

    # ------------------------------------------------------------- case 1
    def test_01_card_says_who_can_be_approved_together(self):
        mine = self._req(self.ask(name='Leave for Ana'))
        card = self._card(self.fin, mine)
        self.assertTrue(card['mine'])
        self.assertTrue(card['can_bulk'])
        self.assertEqual(card['bulk_why'], '')
        self.assertEqual(card['lock_revision'], mine.lock_revision)

        # not my turn: Hana holds no seat on it
        theirs = self._card(self.hr, mine)
        self.assertFalse(theirs['can_bulk'])
        self.assertTrue(theirs['bulk_why'])

        # money leaves the company with it
        money = self._req(self.ask(name='Money one'))
        money.write({'process_id': self.money_process.id})
        card = self._card(self.fin, money)
        self.assertTrue(card['mine'])
        self.assertFalse(card['can_bulk'])
        self.assertIn('Money', card['bulk_why'])

        # its kind is approved one at a time
        self.process.sudo().bulk_ok = False
        card = self._card(self.fin, mine)
        self.assertFalse(card['can_bulk'])
        self.assertIn('one at a time', card['bulk_why'])
        self.process.sudo().bulk_ok = True

        # stuck: nobody holds the seat
        self.held.write({'active': False})
        stuck = self._req(self.ask(name='Stuck one'))
        self.assertEqual(stuck.state, 'blocked')
        card = self._card(self.fin, stuck)
        self.assertFalse(card['can_bulk'])
        self.assertIn('stuck', card['bulk_why'])

        # I sent it in, and the route keeps deciders independent
        self.held.write({'active': True, 'user_id': self.asker.id})
        own = self._req(self.ask(name='My own'))
        card = self._card(self.asker, own)
        self.assertTrue(card['mine'])
        self.assertFalse(card['can_bulk'])
        self.assertIn('part of this one', card['bulk_why'])

    # ------------------------------------------------------------- case 2
    def test_02_a_money_process_cannot_be_approved_several_at_once(self):
        with self.assertRaises(ValidationError):
            self.money_process.write({'bulk_ok': True})
        with self.assertRaises(ValidationError):
            self.env['biz.approval.process'].sudo().create({
                'key': 'wdgap_qf1_money2', 'name': 'x', 'money': True,
                'bulk_ok': True})
        # and the default never lands on a money row
        row = self.env['biz.approval.process'].sudo().create({
            'key': 'wdgap_qf1_m3', 'name': 'y', 'money': True})
        self.assertFalse(row.bulk_ok)

    # ------------------------------------------------------------- case 3
    def test_03_defaults_are_set_once_and_a_choice_survives(self):
        Process = self.env['biz.approval.process'].sudo()
        on = Process.search([('key', 'in', sorted(BULK_DEFAULT_KEYS))])
        self.assertTrue(on, 'none of the default kinds is installed')
        self.assertTrue(all(on.mapped('bulk_ok')),
                        'off: %s' % on.filtered(lambda p: not p.bulk_ok).mapped('key'))
        off_keys = ['payrun', 'bankfile', 'release', 'records', 'resign',
                    'verdict', 'newhire', 'contract', 'paychange',
                    'bankchange', 'scheme', 'roles', 'expense',
                    'hiring_request', 'hiring_offer']
        off = Process.search([('key', 'in', off_keys)])
        self.assertTrue(off)
        self.assertFalse(any(off.mapped('bulk_ok')),
                         'on: %s' % off.filtered('bulk_ok').mapped('key'))
        self.assertFalse(any(Process.search([('money', '=', True)]).mapped(
            'bulk_ok')))

        # the existing rows were given the default once (the marker)
        self.assertTrue(self.env['ir.config_parameter'].sudo().get_param(
            BULK_SEEDED_PARAM))

        # a customer turns leave OFF; a second upgrade keeps their choice
        leave = Process.search([('key', '=', 'leave')], limit=1)
        self.assertTrue(leave)
        leave.bulk_ok = False
        self.assertEqual(Process._seed_bulk_defaults(), [])
        self._run_migration()
        leave.invalidate_recordset()
        self.assertFalse(leave.bulk_ok)

        # a kind not on the list is born off; one on the list (a module
        # installed afterwards) is born on, unless it is a money process
        late = Process.create({'key': 'wdgap_qf1_probe', 'name': 'z'})
        self.assertFalse(late.bulk_ok)
        with patch('odoo.addons.biz_approval_workflow.models.process.'
                   'BULK_DEFAULT_KEYS',
                   frozenset({'wdgap_qf1_born', 'wdgap_qf1_born2'})):
            born = Process.create({'key': 'wdgap_qf1_born', 'name': 'Born'})
            chosen = Process.create({'key': 'wdgap_qf1_born2', 'name': 'B2',
                                     'bulk_ok': False})
        self.assertTrue(born.bulk_ok)
        self.assertFalse(chosen.bulk_ok)

    def _run_migration(self):
        import importlib.util
        import os
        import odoo.addons.biz_approval_workflow as mod
        path = os.path.join(os.path.dirname(mod.__file__), 'migrations',
                            '19.0.1.8.0', 'post-bulk_ok_defaults.py')
        spec = importlib.util.spec_from_file_location('qf1_mig', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '19.0.1.7.1')

    # ------------------------------------------------------------- case 4
    def test_04_bulk_moves_each_request_exactly_as_single_decides_do(self):
        single = [self._req(self.ask(name='Single %s' % n)) for n in range(3)]
        bulk = [self._req(self.ask(name='Bulk %s' % n)) for n in range(3)]
        inbox = self._inbox(self.fin)
        for request in single:
            step = request.step_ids.filtered(lambda s: s.status == 'active')
            inbox.decide(request.id, step.key, 'approve')
        answer = inbox.decide_many([r.id for r in bulk],
                                   {str(r.id): r.lock_revision for r in bulk})
        self.assertEqual(answer['done'], 3, answer)
        self.assertEqual(answer['failed'], 0)
        self.assertTrue(all(row['ok'] and row['title'] for row in answer['results']))
        for one, other in zip(single, bulk):
            self.assertEqual(self._shape(one), self._shape(other))
        decisions = self.env['biz.approval.decision'].sudo().search(
            [('request_id', 'in', [r.id for r in bulk])])
        self.assertEqual(len(decisions), 3)
        self.assertEqual(decisions.mapped('user_id'), self.fin,
                         'decided as somebody else')
        self.assertFalse(decisions.filtered('exception_grant_id'))
        self.assertTrue(all(d.idempotency_key for d in decisions))

    # ------------------------------------------------------------- case 5
    def test_05_a_mixed_batch_approves_only_what_may_be_approved(self):
        good = self._req(self.ask(name='Good one'))
        money = self._req(self.ask(name='Money one'))
        money.write({'process_id': self.money_process.id})
        done = self._req(self.ask(name='Done already'))
        step = done.step_ids.filtered(lambda s: s.status == 'active')
        self._inbox(self.fin).decide(done.id, step.key, 'approve')
        # somebody else's turn: the seat is Hana's, and Fred cannot read it
        self.held.write({'user_id': self.hr.id})
        other = self._req(self.ask(name='Not mine'))
        self.held.write({'user_id': self.fin.id})

        everyone = good | money | done | other
        before = {r.id: self._shape(r) for r in everyone}
        counted = self._decisions(everyone)
        answer = self._inbox(self.fin).decide_many(everyone.ids)
        rows = {row['id']: row for row in answer['results']}
        self.assertEqual(answer['done'], 1)
        self.assertEqual(answer['failed'], 3)
        self.assertTrue(rows[good.id]['ok'])
        for bad in (money, done, other):
            self.assertFalse(rows[bad.id]['ok'])
            self.assertTrue(rows[bad.id]['error'], bad.title)
            self.assertNotIn('biz.approval', rows[bad.id]['error'])
            self.assertEqual(self._shape(bad), before[bad.id])
        self.assertIn('Money', rows[money.id]['error'])
        self.assertIn('no longer waiting', rows[done.id]['error'])
        self.assertEqual(self._decisions(everyone), counted + 1)

    # ------------------------------------------------------------- case 6
    def test_06_a_request_somebody_else_is_deciding_fails_alone(self):
        rows = [self._req(self.ask(name='Lock %s' % n)) for n in range(3)]
        held_id = rows[1].id
        Engine = type(self.env['biz.approval.engine'])
        real_lock = Engine._lock

        def busy(engine, request):
            if request.id == held_id:
                # what NOWAIT does when another person holds the row: the
                # statement fails inside the transaction, and the engine says
                # so in a sentence
                try:
                    with mute_logger('odoo.sql_db'):
                        engine.env.cr.execute('SELECT 1 / 0')
                except Exception:  # noqa: BLE001
                    raise UserError("Someone else is deciding this right now. "
                                    "Give it a moment and try again.") from None
            return real_lock(engine, request)

        with patch.object(Engine, '_lock', busy):
            answer = self._inbox(self.fin).decide_many([r.id for r in rows])
        by_id = {row['id']: row for row in answer['results']}
        self.assertEqual(answer['done'], 2)
        self.assertFalse(by_id[held_id]['ok'])
        self.assertIn('Someone else', by_id[held_id]['error'])
        rows[1].invalidate_recordset()
        self.assertEqual(rows[1].state, 'pending')
        for request in (rows[0], rows[2]):
            request.invalidate_recordset()
            self.assertIn(request.state, ('approved', 'applied'))

    # ------------------------------------------------------------- case 7
    def test_07_the_same_press_twice_approves_nothing_new(self):
        rows = [self._req(self.ask(name='Twice %s' % n)) for n in range(3)]
        seen = {str(r.id): r.lock_revision for r in rows}
        inbox = self._inbox(self.fin)
        first = inbox.decide_many([r.id for r in rows], seen)
        self.assertEqual(first['done'], 3)
        counted = self._decisions(self.env['biz.approval.request'].browse(
            [r.id for r in rows]))
        second = inbox.decide_many([r.id for r in rows], seen)
        self.assertEqual(second['done'], 0)
        third = inbox.decide_many([r.id for r in rows])
        self.assertEqual(third['done'], 0)
        self.assertEqual(self._decisions(self.env['biz.approval.request'].browse(
            [r.id for r in rows])), counted)
        # the same id twice in one call is decided once
        dup = self._req(self.ask(name='Dup'))
        answer = inbox.decide_many([dup.id, dup.id, str(dup.id)])
        self.assertEqual(len(answer['results']), 1)
        self.assertEqual(self._decisions(dup), 1)

    def test_07b_a_card_that_changed_since_it_was_read_is_not_approved(self):
        request = self._req(self.ask(name='Changed'))
        stale = request.lock_revision - 1
        answer = self._inbox(self.fin).decide_many(
            [request.id], {str(request.id): stale})
        self.assertEqual(answer['done'], 0)
        self.assertIn('changed', answer['results'][0]['error'])
        self.assertEqual(self._decisions(request), 0)

    # ------------------------------------------------------------- case 8
    def test_08_limits_and_a_person_with_no_seat(self):
        with self.assertRaises(UserError):
            self._inbox(self.fin).decide_many(list(range(1, 53)))
        with self.assertRaises(UserError):
            self._inbox(self.fin).decide_many('1,2,3')
        rows = [self._req(self.ask(name='Theirs %s' % n)) for n in range(2)]
        for person in (self.hr, self.asker):
            answer = self._inbox(person).decide_many([r.id for r in rows])
            self.assertEqual(answer['done'], 0, person.name)
            self.assertTrue(all(row['error'] for row in answer['results']))
        everyone = self.env['biz.approval.request'].browse([r.id for r in rows])
        self.assertEqual(self._decisions(everyone), 0)
        for request in rows:
            request.invalidate_recordset()
            self.assertEqual(request.state, 'pending')

    # ------------------------------------------------------------- case 9
    def test_09_my_turn_is_counted_fresh_after_the_press(self):
        rows = [self._req(self.ask(name='Count %s' % n)) for n in range(3)]
        inbox = self._inbox(self.fin)
        before = set(inbox._my_turn_ids())
        self.assertTrue({r.id for r in rows} <= before)
        inbox.decide_many([r.id for r in rows[:2]])
        after = set(inbox._my_turn_ids())
        self.assertNotIn(rows[0].id, after)
        self.assertNotIn(rows[1].id, after)
        self.assertIn(rows[2].id, after)
