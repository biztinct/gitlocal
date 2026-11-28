# -*- coding: utf-8 -*-
"""INBOX-BULK-BANK — bank-detail changes approved several at once, after an
extra confirmation (owner request 2026-11-21). Cases numbered as the
handover's tests 1-7 (8 and 9 run on a copy of a real site and in the
browser).

The rule under test is QF1's, widened by one tier and no further: approving
several at once can never do what one press of Approve by the same person
could not, a kind that pays money out is never one of a batch, and a
bank-detail kind is one of a batch only when the approver confirmed the
extra check.
"""
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.biz_approval_workflow.models.process import (
    BULK_CONFIRM_KEYS, BULK_CONFIRM_SEEDED_PARAM)

from .common import MatrixCase


@tagged('post_install', '-at_install', 'inbox_bulk_bank')
class TestInboxBulkBank(MatrixCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Process = cls.env['biz.approval.process'].sudo()
        # the real bank-detail rows: `bankchange` ships with this module;
        # `records_bank` with the Records desk (made here when it is absent)
        cls.bank = Process._by_key('records_bank') or Process.create({
            'key': 'records_bank', 'name': 'Bank details (test)',
            'area': 'data', 'money': True})
        cls.bank.write({'money': True, 'bulk_ok': False, 'bulk_confirm': True})
        cls.bankchange = Process._by_key('bankchange')
        # a kind that pays money out
        cls.pay = Process.create({'key': 'ibb_fundpay', 'name': 'IBB payment',
                                  'area': 'money', 'money': True})
        # the "Other request" process stands in for an ordinary kind
        cls.process.sudo().write({'money': False, 'bulk_ok': True,
                                  'bulk_confirm': False})

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

    def _req(self, made, process=None):
        request = self.env['biz.approval.request'].sudo().browse(
            made['request_id'])
        if process is not None:
            request.write({'process_id': process.id})
        return request

    def _bank_req(self, name='Bank account'):
        return self._req(self.ask(name=name), self.bank)

    def _decisions(self, requests):
        return self.env['biz.approval.decision'].sudo().search(
            [('request_id', 'in', requests.ids)])

    def _shape(self, request):
        request.invalidate_recordset()
        return (request.state,
                [(s.sequence, s.status) for s in request.step_ids.sorted('sequence')],
                sorted((seat.status, seat.acting_user_id.id)
                       for seat in request.step_ids.seat_ids),
                request.record_ref if 'record_ref' in request._fields else None)

    # ------------------------------------------------------------- case 1
    def test_01_bank_card_tickable_payment_kind_still_refused(self):
        bank = self._bank_req()
        card = self._inbox(self.fin)._card(bank)
        self.assertTrue(card['mine'])
        self.assertTrue(card['can_bulk'], card['bulk_why'])
        self.assertTrue(card['bulk_confirm'])
        self.assertEqual(card['bulk_why'], '')

        # an ordinary kind is tickable and needs no extra check
        plain = self._req(self.ask(name='Leave'))
        card = self._inbox(self.fin)._card(plain)
        self.assertTrue(card['can_bulk'])
        self.assertFalse(card['bulk_confirm'])

        # a kind that pays money out: no tier may be set, and no tick
        with self.assertRaises(ValidationError):
            self.pay.write({'bulk_confirm': True})
        with self.assertRaises(ValidationError):
            self.pay.write({'bulk_ok': True})
        money = self._req(self.ask(name='A payment'), self.pay)
        card = self._inbox(self.fin)._card(money)
        self.assertFalse(card['can_bulk'])
        self.assertFalse(card['bulk_confirm'])
        self.assertIn('Money', card['bulk_why'])
        # ... and the direct call refuses it too, even "confirmed"
        before = self._shape(money)
        answer = self._inbox(self.fin).decide_many([money.id], confirmed=True)
        self.assertEqual(answer['done'], 0)
        self.assertIn('Money', answer['results'][0]['error'])
        self.assertEqual(self._shape(money), before)
        self.assertFalse(self._decisions(money))

        # a row written around the constraint (raw SQL) still does not pass
        self.env.cr.execute(
            "UPDATE biz_approval_process SET bulk_confirm = true WHERE id = %s",
            [self.pay.id])
        self.pay.invalidate_recordset()
        self.assertFalse(self._inbox(self.fin)._needs_confirm(self.pay))
        self.assertFalse(self._inbox(self.fin)._card(money)['can_bulk'])

        # the bank tier switched off: one at a time again
        self.bank.write({'bulk_confirm': False})
        card = self._inbox(self.fin)._card(bank)
        self.assertFalse(card['can_bulk'])
        self.assertIn('Money', card['bulk_why'])
        self.bank.write({'bulk_confirm': True})

    # ------------------------------------------------------------- case 2
    def test_02_the_extra_check_is_required_by_the_server(self):
        rows = [self._bank_req('Bank %s' % n) for n in range(3)]
        everyone = self.env['biz.approval.request'].browse([r.id for r in rows])
        before = {r.id: self._shape(r) for r in rows}
        inbox = self._inbox(self.fin)
        # without `confirmed`: refused, row by row, in a plain sentence
        answer = inbox.decide_many([r.id for r in rows])
        self.assertEqual(answer['done'], 0)
        for row in answer['results']:
            self.assertIn('extra check', row['error'])
        # a truthy non-boolean is not a confirmation either
        answer = inbox.decide_many([r.id for r in rows], confirmed='yes')
        self.assertEqual(answer['done'], 0)
        for request in rows:
            self.assertEqual(self._shape(request), before[request.id])
        self.assertFalse(self._decisions(everyone))

        # the summary the dialog shows: counts only
        summary = inbox.bulk_summary([r.id for r in rows])
        self.assertEqual(summary['count'], 3)
        self.assertEqual(summary['confirm'], 3)
        self.assertEqual(summary['bank'], 3)
        self.assertEqual(summary['kinds'][0]['count'], 3)
        self.assertTrue(summary['kinds'][0]['confirm'])

        # confirmed: approved, and the history says how
        answer = inbox.decide_many([r.id for r in rows], confirmed=True,
                                   batch_size=3)
        self.assertEqual(answer['done'], 3, answer)
        decisions = self._decisions(everyone)
        self.assertEqual(len(decisions), 3)
        for decision in decisions:
            self.assertIn('together with 2 others', decision.reason)
            self.assertIn('extra check', decision.reason)
            self.assertEqual(decision.user_id, self.fin)

    # ------------------------------------------------------------- case 3
    def test_03_select_all_over_a_filter_then_chunks(self):
        rows = [self._bank_req('Many %s' % n) for n in range(120)]
        # one more that is somebody else's turn, and one of another kind
        self.held.write({'user_id': self.hr.id})
        theirs = self._bank_req('Not mine')
        self.held.write({'user_id': self.fin.id})
        plain = self._req(self.ask(name='Plain one'))

        inbox = self._inbox(self.fin)
        kind = {'process': [self.bank.id]}
        picked = inbox.select_all_ids(filters=kind)
        self.assertEqual(picked['count'], 120)
        self.assertFalse(picked['capped'])
        self.assertEqual(picked['confirm'], 120)
        self.assertEqual(set(picked['ids']), {r.id for r in rows})
        self.assertNotIn(theirs.id, picked['ids'])
        self.assertNotIn(plain.id, picked['ids'])
        # without the kind filter, my ordinary request is offered too
        wide = inbox.select_all_ids(filters={'my_turn': ['yes']})
        self.assertIn(plain.id, wide['ids'])
        self.assertNotIn(theirs.id, wide['ids'])

        # one approved alone first: the bulk ones must end up the same
        single, rest = rows[0], rows[1:]
        step = single.step_ids.filtered(lambda s: s.status == 'active')
        inbox.decide(single.id, step.key, 'approve')

        ids = [r.id for r in rest]
        done = 0
        calls = 0
        for start in range(0, len(ids), 50):
            chunk = ids[start:start + 50]
            answer = inbox.decide_many(
                chunk, {str(i): picked['revisions'][str(i)] for i in chunk},
                confirmed=True, batch_size=len(ids))
            done += answer['done']
            calls += 1
            self.assertEqual(answer['failed'], 0, answer)
        self.assertEqual(calls, 3)
        self.assertEqual(done, 119)
        for request in rest:
            self.assertEqual(self._shape(request), self._shape(single))
        # field by field: the bulk decision is the single one plus its note
        one = self._decisions(single)
        other = self._decisions(rest[0])
        for name in ('action', 'step_key', 'user_id', 'acting_for_uid',
                     'exception_grant_id', 'conflict_kind', 'company_id'):
            self.assertEqual(one[name], other[name], name)
        self.assertFalse(one.reason)
        self.assertIn('together with 118 others', other.reason)
        # nothing left to select under that filter
        self.assertEqual(inbox.select_all_ids(filters=kind)['count'], 0)
        # a chunk above the cap is refused as before
        with self.assertRaises(UserError):
            inbox.decide_many(list(range(1, 53)), confirmed=True)

    # ------------------------------------------------------------- case 4
    def test_04_my_own_request_is_never_selected_or_approved(self):
        # Ash holds the seat and also sent it in; the route keeps deciders
        # independent
        self.held.write({'user_id': self.asker.id})
        own = self._bank_req('My own bank')
        card = self._inbox(self.asker)._card(own)
        self.assertTrue(card['mine'])
        self.assertFalse(card['can_bulk'])
        self.assertIn('part of this one', card['bulk_why'])
        picked = self._inbox(self.asker).select_all_ids(filters={})
        self.assertNotIn(own.id, picked['ids'])
        answer = self._inbox(self.asker).decide_many([own.id], confirmed=True)
        self.assertEqual(answer['done'], 0)
        self.assertFalse(self._decisions(own))
        own.invalidate_recordset()
        self.assertEqual(own.state, 'pending')

    # ------------------------------------------------------------- case 5
    def test_05_one_failure_in_a_group_does_not_stop_the_rest(self):
        rows = [self._bank_req('Lock %s' % n) for n in range(5)]
        held_id = rows[2].id
        Engine = type(self.env['biz.approval.engine'])
        real_lock = Engine._lock

        def busy(engine, request):
            if request.id == held_id:
                try:
                    with mute_logger('odoo.sql_db'):
                        engine.env.cr.execute('SELECT 1 / 0')
                except Exception:  # noqa: BLE001
                    raise UserError("Someone else is deciding this right now. "
                                    "Give it a moment and try again.") from None
            return real_lock(engine, request)

        with patch.object(Engine, '_lock', busy):
            answer = self._inbox(self.fin).decide_many(
                [r.id for r in rows], confirmed=True, batch_size=5)
        by_id = {row['id']: row for row in answer['results']}
        self.assertEqual(answer['done'], 4)
        self.assertFalse(by_id[held_id]['ok'])
        self.assertIn('Someone else', by_id[held_id]['error'])
        for request in rows:
            request.invalidate_recordset()
            if request.id == held_id:
                self.assertEqual(request.state, 'pending')
            else:
                self.assertIn(request.state, ('approved', 'applied'))

    # ------------------------------------------------------------- case 6
    def test_06_silent_upgrade_then_the_one_time_tier(self):
        Process = self.env['biz.approval.process'].sudo()
        params = self.env['ir.config_parameter'].sudo()
        # the upgrade of this database ran the step once already
        self.assertTrue(params.get_param(BULK_CONFIRM_SEEDED_PARAM))
        on = Process.search([('key', 'in', sorted(BULK_CONFIRM_KEYS))])
        self.assertTrue(on)
        # nothing else was given the tier
        others = Process.search([('bulk_confirm', '=', True),
                                 ('key', 'not in', sorted(BULK_CONFIRM_KEYS))])
        self.assertFalse(others - self.process, others.mapped('key'))

        # as a fresh upgrade would see it: the column empty, the marker gone
        pending = self._bank_req('Waiting')
        self.env.cr.execute("UPDATE biz_approval_process SET bulk_confirm = false")
        Process.invalidate_model(['bulk_confirm'])
        params.set_param(BULK_CONFIRM_SEEDED_PARAM, '')
        shape = self._shape(pending)
        mails = self.env['mail.mail'].sudo().search_count([])
        jobs = self.env['ir.cron'].sudo().with_context(
            active_test=False).search_read([], ['active'])
        keys = Process._seed_bulk_confirm_defaults()
        self.assertEqual(set(keys), set(on.mapped('key')))
        self.assertTrue(all(on.mapped('bulk_confirm')))
        self.assertEqual(self._shape(pending), shape)
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), mails)
        self.assertEqual(self.env['ir.cron'].sudo().with_context(
            active_test=False).search_read([], ['active']), jobs)
        self.assertFalse(self._decisions(pending))
        # a second run changes nothing; a customer's "off" survives it
        self.bank.write({'bulk_confirm': False})
        self.assertEqual(Process._seed_bulk_confirm_defaults(), [])
        self.bank.invalidate_recordset()
        self.assertFalse(self.bank.bulk_confirm)
        # the migration file itself calls the same step
        import importlib.util
        import os
        import odoo.addons.biz_approval_workflow as mod
        path = os.path.join(os.path.dirname(mod.__file__), 'migrations',
                            '19.0.1.9.0', 'post-bulk_confirm_defaults.py')
        spec = importlib.util.spec_from_file_location('ibb_mig', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '19.0.1.8.0')
        self.bank.invalidate_recordset()
        self.assertFalse(self.bank.bulk_confirm)

    # ------------------------------------------------------------- case 7
    def test_07_the_switch_on_screen(self):
        admin = self._user('ibb_admin', 'Ada Admin',
                           groups=['base.group_user', 'base.group_system'])
        Matrix = self.env['pb.approval.matrix']
        as_admin = Matrix.with_user(admin).with_company(self.company)
        # payload for an ordinary kind: all three answers, editable
        payload = as_admin._bulk_payload(self.process)
        self.assertEqual(payload['allowed'], ['off', 'on', 'confirm'])
        self.assertTrue(payload['can_edit'])
        self.assertEqual(payload['mode'], 'on')
        # off → confirm → on → off, one trail line each
        Event = self.env['biz.approval.event'].sudo()
        seen = Event.search_count([('kind', '=', 'setting_changed')])
        for mode in ('confirm', 'on', 'off'):
            answer = as_admin.set_bulk_mode(self.process.key, mode)
            self.assertEqual(answer['mode'], mode)
        self.process.invalidate_recordset()
        self.assertFalse(self.process.bulk_ok or self.process.bulk_confirm)
        self.assertEqual(Event.search_count([('kind', '=', 'setting_changed')]),
                         seen + 3)
        # the same answer twice writes no second line
        as_admin.set_bulk_mode(self.process.key, 'off')
        self.assertEqual(Event.search_count([('kind', '=', 'setting_changed')]),
                         seen + 3)
        # a bank-detail money kind: only off and the extra-check tier
        payload = as_admin._bulk_payload(self.bank)
        self.assertEqual(payload['allowed'], ['off', 'confirm'])
        self.assertTrue(payload['confirm_only'])
        with self.assertRaises(UserError):
            as_admin.set_bulk_mode(self.bank.key, 'on')
        self.assertEqual(as_admin.set_bulk_mode(self.bank.key, 'off')['mode'], 'off')
        self.assertEqual(as_admin.set_bulk_mode(self.bank.key, 'confirm')['mode'],
                         'confirm')
        # a payment kind: disabled with the reason, every "on" refused
        payload = as_admin._bulk_payload(self.pay)
        self.assertEqual(payload['allowed'], ['off'])
        self.assertFalse(payload['can_edit'])
        self.assertIn('Money', payload['locked'])
        for mode in ('on', 'confirm'):
            with self.assertRaises(UserError):
                as_admin.set_bulk_mode(self.pay.key, mode)
        self.pay.invalidate_recordset()
        self.assertFalse(self.pay.bulk_ok or self.pay.bulk_confirm)
        # somebody who sets approvals up but is not the administrator: sees
        # it, cannot change it
        as_boss = Matrix.with_user(self.boss).with_company(self.company)
        payload = as_boss._bulk_payload(self.process)
        self.assertFalse(payload['can_edit'])
        self.assertFalse(payload['is_admin'])
        with self.assertRaises(AccessError):
            as_boss.set_bulk_mode(self.process.key, 'on')
        with self.assertRaises(AccessError):
            Matrix.with_user(self.fin).set_bulk_mode(self.process.key, 'on')
        # the route editor carries the switch
        workflow = self.seeded_workflow()
        data = as_admin.get_workflow(workflow.id)
        self.assertEqual(data['bulk']['process_key'], self.process.key)
        self.assertIn(data['bulk']['mode'], ('off', 'on', 'confirm'))
        # nothing about the switch is a word of the platform
        for text in (payload['locked'], as_admin._bulk_payload(self.pay)['locked']):
            self.assertNotIn('odoo', (text or '').lower())
