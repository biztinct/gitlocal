# -*- coding: utf-8 -*-
""""No approval needed" for many processes in one press, and its undo.

Every case reads the engine's own bindings afterwards rather than trusting the
payload the facade returned: the question is what future requests will follow.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import MatrixCase


@tagged('post_install', '-at_install')
class TestBulkNoApproval(MatrixCase):

    def _bindings(self, scope_key=''):
        return self.env['biz.approval.binding'].search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', self.process.id),
            ('scope_key', '=', scope_key), ('active', '=', True)])

    def _row(self, key='generic'):
        grid = self.as_admin('pb.approval.matrix').get_matrix(self.company.id)
        return next(r for a in grid['areas'] for r in a['rows']
                    if r['process_key'] == key)

    def test_one_press_switches_and_undo_puts_back_exactly(self):
        matrix = self.as_admin('pb.approval.matrix')
        before = self._bindings()
        self.assertEqual(len(before), 1)
        self.assertEqual(self._row()['bulk'], '')

        result = matrix.set_no_approval_bulk(
            ['generic'], self.company.id, reason='Small team')
        self.assertEqual([d['process_key'] for d in result['done']],
                         ['generic'])
        now = self._bindings()
        self.assertEqual(now.workflow_id.name, 'No approval needed')
        self.assertFalse(before.active, 'the old route is ended, not edited')
        row = self._row()
        self.assertTrue(row['fast'])
        self.assertEqual(row['bulk'], 'fast')

        again = matrix.set_no_approval_bulk(['generic'], self.company.id)
        self.assertFalse(again['done'])
        self.assertEqual(again['skipped'][0]['why'], 'Already needs no approval')

        undone = matrix.undo_no_approval_bulk(result['undo'], self.company.id)
        self.assertEqual(undone['restored'], 1)
        self.assertEqual(self._bindings(), before)
        self.assertFalse(self._row()['fast'])

    def test_a_part_with_its_own_route_follows_only_when_asked(self):
        matrix = self.as_admin('pb.approval.matrix')
        own = self.seeded_workflow()
        exception = self.env['biz.approval.binding'].create({
            'company_id': self.company.id, 'process_id': self.process.id,
            'scope_key': 'scheme:4242', 'scope_label': 'Scheme 4242',
            'kind_key': 'any', 'workflow_id': own.id, 'mode': 'follow'})

        preview = matrix.bulk_no_approval_preview(['generic'], self.company.id)
        self.assertEqual(preview['exceptions'], 1)

        kept = matrix.set_no_approval_bulk(
            ['generic'], self.company.id, include_exceptions=False)
        self.assertEqual(exception.workflow_id, own)
        matrix.undo_no_approval_bulk(kept['undo'], self.company.id)

        result = matrix.set_no_approval_bulk(['generic'], self.company.id)
        self.assertEqual(exception.workflow_id.name, 'No approval needed')
        matrix.undo_no_approval_bulk(result['undo'], self.company.id)
        self.assertEqual(exception.workflow_id, own)

    def test_money_out_needs_its_confirmation(self):
        self.process.sudo().money = True
        matrix = self.as_admin('pb.approval.matrix')
        with self.assertRaises(UserError):
            matrix.set_no_approval_bulk(['generic'], self.company.id)
        result = matrix.set_no_approval_bulk(
            ['generic'], self.company.id, confirmations=['money_fast'])
        self.assertTrue(result['done'])

    def test_somebody_who_may_only_draft_cannot_switch_checks_off(self):
        matrix = self.env['pb.approval.matrix'].with_user(
            self.officer).with_company(self.company)
        if matrix._can_publish():
            self.skipTest('the config group also publishes on this build')
        with self.assertRaises(AccessError):
            matrix.set_no_approval_bulk(['generic'], self.company.id)

    def test_an_unknown_or_unconnected_process_is_left_alone(self):
        matrix = self.as_admin('pb.approval.matrix')
        loose = self.env['biz.approval.process'].search([]).filtered(
            lambda p: not p.connected)[:1]
        keys = ['generic', 'no-such-process'] + ([loose.key] if loose else [])
        result = matrix.set_no_approval_bulk(keys, self.company.id)
        self.assertEqual([d['process_key'] for d in result['done']],
                         ['generic'])
        if loose:
            self.assertEqual(result['skipped'][0]['process_key'], loose.key)
