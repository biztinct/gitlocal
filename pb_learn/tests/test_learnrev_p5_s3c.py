# -*- coding: utf-8 -*-
"""LEARNREV P5a S3 - right-now providers, group c.

`import` has a provider (rows needing a match). `payreview` has none
(right_now is None), so only its manifest wiring is asserted.
"""
import os
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged


def _batch(id_, name, state, total=0, matched=0, new=0, errors=0):
    return {'id': id_, 'name': name, 'state': state, 'total_lines': total,
            'matched': matched, 'new': new, 'errors': errors}


@tagged('post_install', '-at_install', 'learnrev')
class TestImportRightNow(TransactionCase):

    def _run(self, batches):
        Model = self.env['pb.import']
        with patch.object(type(Model), 'get_import_data',
                          return_value={'batches': batches}):
            return Model.learn_right_now()

    def test_01_empty_state_is_one_ok_item(self):
        items = self._run([])
        self.assertEqual([i['key'] for i in items], ['ok'])
        self.assertEqual(items[0]['severity'], 'ok')
        self.assertEqual(items[0]['count'], 0)
        self.assertTrue(items[0]['text']['en'] and items[0]['text']['vi'])

    def test_02_done_batches_alone_are_ok(self):
        items = self._run([_batch(1, 'B1', 'done', 10, 10, 0, 0)])
        self.assertEqual([i['key'] for i in items], ['ok'])

    def test_03_rows_needing_a_match(self):
        items = self._run([
            _batch(1, 'B1', 'loaded', total=10, matched=6, new=1),
            _batch(2, 'B2', 'matched', total=5, matched=5),
            _batch(3, 'B3', 'draft', total=0),
        ])
        self.assertEqual([i['key'] for i in items], ['needs_match'])
        item = items[0]
        self.assertEqual(item['count'], 3)
        self.assertEqual(item['severity'], 'warn')
        self.assertEqual(item['action'], {
            'kind': 'open_record', 'res_model': 'hr.payroll.import.batch',
            'res_id': 1})

    def test_04_errors_and_ready_follow_in_order(self):
        items = self._run([
            _batch(1, 'B1', 'loaded', total=4, matched=1, errors=2),
            _batch(2, 'B2', 'validated', total=3, matched=3),
            _batch(3, 'B3', 'done', total=3, matched=3, errors=1),
        ])
        self.assertEqual([i['key'] for i in items],
                         ['needs_match', 'has_errors', 'ready_to_commit'])
        by_key = {i['key']: i for i in items}
        self.assertEqual(by_key['needs_match']['count'], 3)
        self.assertEqual(by_key['has_errors']['count'], 2)
        self.assertEqual(by_key['has_errors']['action'],
                         {'kind': 'filter', 'value': 'errors'})
        self.assertEqual(by_key['ready_to_commit']['count'], 1)
        self.assertEqual(by_key['ready_to_commit']['severity'], 'info')
        for item in items:
            self.assertTrue(item['text']['en'] and item['text']['vi'])
            self.assertNotIn('odoo', (item['text']['en'] + item['text']['vi']).lower())

    def test_05_real_call_returns_items(self):
        items = self.env['pb.import'].learn_right_now()
        self.assertTrue(items)
        for item in items:
            for key in ('key', 'count', 'severity', 'text', 'action'):
                self.assertIn(key, item)
            self.assertIn(item['severity'], ('warn', 'info', 'ok'))

    def test_06_no_sudo_in_provider(self):
        path = os.path.join(os.path.dirname(__file__), '..', '..',
                            'pb_import', 'models', 'import_learn.py')
        with open(path, encoding='utf-8') as fh:
            self.assertNotIn('sudo(', fh.read())
