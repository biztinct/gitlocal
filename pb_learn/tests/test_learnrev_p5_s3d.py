# -*- coding: utf-8 -*-
"""LEARNREV P5a S3 - right-now providers, group d.

Approval Matrix (`pb.approval.matrix.learn_right_now`). The Time screen
(`wftime`) has no provider (right_now is None).
"""
import os

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_approval_config.models import matrix_learn


@tagged('post_install', '-at_install', 'learnrev')
class TestLearnrevP5S3d(TransactionCase):

    def _rows(self, *rows):
        """Stand in for the screen's own read, so the fixture is exact."""
        areas = [{'key': 'a', 'name': 'A', 'icon': 'inbox', 'rows': list(rows)}]
        return {'areas': areas, 'attention': {'count': 0, 'rows': []}}

    def _row(self, key, name, status, needs=0, version='', connected=True):
        return {'process_key': key, 'name': name, 'status': status,
                'needs_people': needs, 'version': version,
                'connected': connected}

    def _provider(self, data):
        Matrix = self.env['pb.approval.matrix']
        self.patch(type(Matrix), 'get_matrix',
                   lambda this, company_id=None: data)
        return Matrix.learn_right_now()

    def test_01_needs_people_first(self):
        items = self._provider(self._rows(
            self._row('p1', 'Expense claims', 'needs', needs=2, version='v1'),
            self._row('p2', 'Leave', 'needs', needs=1, version='v3'),
            self._row('p3', 'Hiring', 'draft', version='Draft'),
            self._row('p4', 'Travel', 'live', version='v2')))
        self.assertEqual([i['key'] for i in items], ['needs_people', 'draft'])
        needs = items[0]
        self.assertEqual(needs['count'], 2)
        self.assertEqual(needs['severity'], 'warn')
        self.assertEqual(needs['gaps'], 3)
        self.assertEqual(set(needs['names']), {'Expense claims', 'Leave'})
        self.assertTrue(needs['text']['en'] and needs['text']['vi'])
        self.assertNotIn('odoo', needs['text']['en'].lower())
        self.assertEqual(items[1]['count'], 1)
        self.assertEqual(items[1]['severity'], 'info')
        action = needs['action']
        if action:
            self.assertEqual(action['kind'], 'open')
            self.assertEqual(action['xmlid'],
                             'pb_approval_config.action_pb_approval_matrix')
            self.assertTrue(self.env.ref(action['xmlid'],
                                         raise_if_not_found=False))

    def test_02_draft_without_a_route_is_not_counted(self):
        items = self._provider(self._rows(
            self._row('p1', 'Hiring', 'draft', version=''),
            self._row('p2', 'Soon', 'soon', connected=False)))
        self.assertEqual([i['key'] for i in items], ['ok'])

    def test_03_empty_state_is_one_ok_item(self):
        items = self._provider(self._rows())
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item['key'], 'ok')
        self.assertEqual(item['count'], 0)
        self.assertEqual(item['severity'], 'ok')
        self.assertIsNone(item['action'])
        self.assertTrue(item['text']['en'] and item['text']['vi'])

    def test_04_provider_never_elevates(self):
        with open(matrix_learn.__file__.replace('.pyc', '.py')) as handle:
            self.assertNotIn('sudo(', handle.read())

    def test_05_manifest_points_at_the_provider(self):
        path = os.path.join(os.path.dirname(matrix_learn.__file__), '..',
                            'learn_manifest.py')
        scope = {}
        with open(path) as handle:
            exec(compile(handle.read(), path, 'exec'), scope)
        self.assertEqual(scope['MANIFESTS']['matrix']['right_now'],
                         'pb.approval.matrix.learn_right_now')
        self.assertIn('approvals', scope['MANIFESTS'])
