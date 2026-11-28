# -*- coding: utf-8 -*-
"""LEARNREV P5a S3a - right-now provider for the Statutory cockpit.

The provider reads the cockpit's own data (`get_statutory_data`), so the
cases feed it the three states that function can return and check the items it
builds from each; one case runs it on the real database as a smoke test. No
case writes a statutory record.
"""
import os
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

POLICY = {'name': 'P', 'code': 'P', 'effective': '2026-01-01', 'rows': [],
          'total_employee': 0, 'total_employer': 0, 'total_combined': 0}
TAX = {'name': 'T', 'year': 2026, 'personal_deduction': 0,
       'dependent_deduction': 0, 'slabs': []}


def _data(policy=None, tax=None, country='VN', company='Acme Co'):
    return {'company': company, 'tax_country': country,
            'tax_countries': [('VN', 'Vietnam'), ('ID', 'Indonesia')],
            'policy': policy, 'tax': tax}


@tagged('post_install', '-at_install', 'learnrev')
class TestStatutoryRightNow(TransactionCase):

    def _run(self, payload, args=None):
        Model = self.env['pb.statutory']
        with mock.patch.object(
                type(Model), 'get_statutory_data',
                new=lambda self, country_code=None: payload):
            return Model.learn_right_now(args)

    def _vn_models(self):
        if 'vietnam.insurance.policy' not in self.env:
            self.skipTest('the Vietnam insurance policy table is not installed')

    def test_01_ok_when_both_in_force(self):
        items = self._run(_data(policy=POLICY, tax=TAX))
        self.assertEqual([i['key'] for i in items], ['ok'])
        self.assertEqual(items[0]['severity'], 'ok')
        self.assertEqual(items[0]['count'], 0)
        self.assertIsNone(items[0]['action'])
        self.assertTrue(items[0]['text']['en'] and items[0]['text']['vi'])

    def test_02_no_policy_comes_first(self):
        self._vn_models()
        items = self._run(_data(policy=None, tax=None))
        self.assertEqual([i['key'] for i in items], ['no_policy', 'no_tax_table'])
        for item in items:
            self.assertEqual(item['severity'], 'warn')
            self.assertEqual(item['count'], 1)
            self.assertTrue(item['text']['en'] and item['text']['vi'])
            self.assertNotIn('odoo', (item['text']['en'] + item['text']['vi']).lower())
        self.assertIn('Acme Co', items[0]['text']['en'])
        self.assertIn('Vietnam', items[1]['text']['en'])

    def test_03_only_the_tax_table_missing(self):
        items = self._run(_data(policy=POLICY, tax=None))
        self.assertEqual([i['key'] for i in items], ['no_tax_table'])

    def test_04_only_the_policy_missing(self):
        self._vn_models()
        items = self._run(_data(policy=None, tax=TAX))
        self.assertEqual([i['key'] for i in items], ['no_policy'])

    def test_05_other_country_is_not_asked_for_a_policy(self):
        items = self._run(_data(policy=None, tax=None, country='ID'))
        self.assertEqual([i['key'] for i in items], ['no_tax_table'])
        self.assertIn('Indonesia', items[0]['text']['en'])

    def test_06_action_opens_the_cockpit_when_it_exists(self):
        self._vn_models()
        items = self._run(_data(policy=None, tax=TAX))
        action = items[0]['action']
        if self.env.ref('pb_statutory.action_pb_statutory', raise_if_not_found=False):
            self.assertEqual(action['kind'], 'open')
            self.assertEqual(action['xmlid'], 'pb_statutory.action_pb_statutory')
        else:
            self.assertIsNone(action)

    def test_07_runs_on_the_real_data(self):
        items = self.env['pb.statutory'].learn_right_now()
        self.assertTrue(items)
        for item in items:
            self.assertIn(item['key'], ('ok', 'no_policy', 'no_tax_table'))
            self.assertIn(item['severity'], ('ok', 'warn'))
            self.assertTrue(item['text']['en'] and item['text']['vi'])
        if len(items) > 1:
            self.assertNotIn('ok', [i['key'] for i in items])

    def test_08_provider_never_elevates(self):
        path = os.path.join(ROOT, 'pb_statutory', 'models', 'statutory_learn.py')
        with open(path, encoding='utf-8') as fh:
            source = fh.read()
        self.assertNotIn('sudo(', source)
