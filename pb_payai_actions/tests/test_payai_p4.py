# -*- coding: utf-8 -*-
"""PAYAI P4 — the P3 live-walk fixes P4-W1/W2, then Vietnamese, the
Approvals deep link and the close-out checks: numbered tests 1–10 of
P4_HANDOVER.md.

Same rules as P1–P3: every gate is judged for an explicit user (PA12), no AI
provider is reached (the phrase table carries every sentence), fixtures use
2031 so a shared clone's own runs never collide (PA40).
"""
import json
from unittest.mock import patch

from odoo.tests.common import tagged

from odoo.addons.pb_payai_actions.payai.actions_amber import UpdatePayData
from odoo.addons.pb_payai_actions.tests.test_payai_p3 import _P3Case


@tagged('post_install', '-at_install', 'payai')
class TestPayaiP4Walk(_P3Case):
    """P4-W1/W2 — the pay-value refusal Fable met on the P3 walk."""

    def _no_pay_values(self):
        if 'pb.records.desk' not in self.env:
            self.skipTest('Records Desk not installed.')
        if 'pb.scheme.map' in self.env:
            p = patch.object(self.registry['pb.scheme.map'], 'resolve',
                             lambda self_, employee, cycle_type='any', on_date=None: {
                                 'config_id': self.retail_end.id, 'config_name': '',
                                 'rung': 'test', 'via': ''})
            p.start()
            self.addCleanup(p.stop)
        # The walk's data: the scheme has no Records value the person may change.
        p = patch.object(UpdatePayData, '_cards', lambda self_, ctx, config_id: {})
        p.start()
        self.addCleanup(p.stop)
        return self._user('P4 Records', [self.env.ref('hr.group_hr_user').id,
                                         self.g_officer, self.g_pay_user])

    def test_w1_one_records_door_only(self):
        hr_user = self._no_pay_values()
        card, _s = self._send(hr_user, 'Give Payai Linh Nguyen a Payai Lunch stipend of 500,000')
        self.assertEqual(card['kind'], 'blocked', card)
        doors = [a for a in card['actions'] if a.get('door_id') == 'peoplehub_records']
        self.assertEqual(len(doors), 1, card['actions'])
        labels = [a.get('label') for a in card['actions']]
        self.assertEqual(len(labels), len(set(labels)), "a button is drawn twice: %r" % labels)

    def test_w2_says_why_and_offers_what_can_you_do(self):
        hr_user = self._no_pay_values()
        card, _s = self._send(hr_user, 'Give Payai Linh Nguyen a Payai Lunch stipend of 500,000')
        text = ' '.join(n['text'] for n in card['notes'])
        readable = self.retail_end.with_user(hr_user).has_access('read')
        if readable:
            self.assertIn('Nothing on Payai Retail End-Month can be changed from here yet', text)
        else:
            self.assertIn("Nothing on this person's scheme can be changed from here yet", text)
        self.assertNotIn('has no pay value that can be changed here', text)
        self.assertIn('What can you do?', [c['label'] for c in card['chips']])
        self.assertNotIn('Odoo', json.dumps(card))
