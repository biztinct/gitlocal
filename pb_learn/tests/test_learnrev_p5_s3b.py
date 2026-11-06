# -*- coding: utf-8 -*-
"""LEARNREV P5a S3 - right-now providers, group b.

Records Desk: `pb.records.desk.learn_right_now` lists changes waiting to be
applied (waiting for the asker's decision, sent back, waiting for someone else)
or one `ok` item. The Employees screen has no provider.
"""
import inspect
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

ITEM_KEYS = {'key', 'count', 'severity', 'text', 'action'}


@tagged('post_install', '-at_install', 'learnrev')
class TestRecordsRightNow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Apply = cls.env['pb.records.apply']
        cls.hr_group = cls.env.ref('hr.group_hr_user')
        cls.user = cls.env['res.users'].create({
            'name': 'LR P5 Records Asker', 'login': 'lr_p5_records_asker',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.hr_group.id])],
        })
        cls.other = cls.env['res.users'].create({
            'name': 'LR P5 Records Other', 'login': 'lr_p5_records_other',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.hr_group.id])],
        })

    def _apply(self, name, state, user):
        return self.Apply.sudo().create({
            'name': name, 'state': state, 'user_id': user.id,
            'company_id': self.env.company.id,
        })

    def _items(self, user=None):
        desk = self.env['pb.records.desk'].with_user(user or self.user)
        return desk.learn_right_now()

    def test_01_empty_gives_one_ok_item(self):
        items = self._items()
        self.assertEqual([i['key'] for i in items], ['ok'])
        self.assertTrue(ITEM_KEYS <= set(items[0]))
        self.assertEqual(items[0]['severity'], 'ok')
        self.assertEqual(items[0]['count'], 0)
        self.assertTrue(items[0]['text']['en'] and items[0]['text']['vi'])

    def test_02_my_pending_change_is_listed(self):
        self._apply('RDLR0001', 'pending', self.user)
        self._apply('RDLR0002', 'pending', self.other)
        items = self._items()
        self.assertEqual([i['key'] for i in items], ['waiting_mine'])
        item = items[0]
        self.assertTrue(ITEM_KEYS <= set(item))
        self.assertEqual(item['count'], 1)
        self.assertEqual(item['severity'], 'info')
        self.assertEqual(item['names'], ['RDLR0001'])
        self.assertIn('RDLR0001', item['text']['en'])
        self.assertIn('RDLR0001', item['text']['vi'])

    def test_03_sent_back_comes_before_waiting(self):
        self._apply('RDLR0003', 'pending', self.user)
        self._apply('RDLR0004', 'returned', self.user)
        self._apply('RDLR0005', 'applied', self.user)
        items = self._items()
        self.assertEqual([i['key'] for i in items], ['sent_back', 'waiting_mine'])
        self.assertEqual(items[0]['severity'], 'warn')
        self.assertEqual(items[0]['names'], ['RDLR0004'])
        self.assertEqual(items[1]['count'], 1)

    def test_04_waiting_for_my_decision_comes_first(self):
        theirs = self._apply('RDLR0006', 'pending', self.other)
        theirs.seat_user_ids = [(4, self.user.id)]
        self._apply('RDLR0007', 'pending', self.user)
        # No approval route exists on a bare fixture row, so stand in for the
        # engine's "an open seat on the current step is mine" answer.
        with patch.object(type(self.env['pb.records.desk']),
                          '_learn_open_seat', return_value=True):
            items = self._items()
        self.assertEqual([i['key'] for i in items], ['awaiting_me', 'waiting_mine'])
        self.assertEqual(items[0]['severity'], 'warn')
        self.assertEqual(items[0]['count'], 1)
        self.assertEqual(items[0]['names'], ['RDLR0006'])
        # Without an open seat the change is not mine to decide.
        with patch.object(type(self.env['pb.records.desk']),
                          '_learn_open_seat', return_value=False):
            items = self._items()
        self.assertEqual([i['key'] for i in items], ['waiting_mine'])

    def test_05_open_action_only_when_the_door_exists(self):
        self._apply('RDLR0008', 'returned', self.user)
        action = self._items()[0]['action']
        if self.env.ref('pb_records.action_pb_records_desk', raise_if_not_found=False):
            self.assertEqual(action['kind'], 'open')
            self.assertEqual(action['xmlid'], 'pb_records.action_pb_records_desk')
        else:
            self.assertIsNone(action)

    def test_06_no_desk_access_is_an_access_error(self):
        nobody = self.env['res.users'].create({
            'name': 'LR P5 Records Nobody', 'login': 'lr_p5_records_nobody',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        with self.assertRaises(AccessError):
            self.env['pb.records.desk'].with_user(nobody).learn_right_now()

    def test_07_provider_never_elevates(self):
        from odoo.addons.pb_records.models import records_learn
        self.assertNotIn('sudo(', inspect.getsource(records_learn))
