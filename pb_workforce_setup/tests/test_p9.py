# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P9 — a disabled PC clock in step 6 / step 7 (handover tests 4).

1. step 6 shows a disabled PC as 'disabled' (not sending, not "needs
   attention", not left to finish, not waiting for IT), whatever it reported
   last; "Enable" is offered to a manager only;
2. "Enable" from step 6 is the connector's own action as the caller: refused
   for an officer and for an administrator without clock rights, touches only
   that connector, leaves the attendance tick alone;
3. step 6's green text and step 7's clock line treat a disabled clock as
   sending nothing.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .test_golive import GoLiveFixture, TZ


@tagged('post_install', '-at_install', 'wfsetup', 'wfsetup_p9')
class TestP9Disabled(GoLiveFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_only = new_test_user(
            cls.env, login='wfs9_admin', groups='base.group_user,base.group_system',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])], tz=TZ)

    def _connector(self, name, company=None, **status):
        conn = self.env['pb.clock.connector'].sudo().create({
            'name': name, 'company_id': (company or self.company).id, 'source_group': name, 'tz': TZ})
        if status:
            conn.sudo().write(status)
        return conn

    def _rows(self, user=None, now=None):
        return {r['name']: r for r in self.facade(user)._clock_rows(now)}

    def _step(self):
        return {s['key']: s for s in self.facade().load()['steps']}['clocks']

    def test_01_disabled_row(self):
        now = fields.Datetime.now().replace(microsecond=0)
        self._connector('Sending PC', state='connected', publish_punches=True, last_contact=now - timedelta(minutes=5))
        self._connector('Off PC', state='disabled', publish_punches=True, last_contact=now - timedelta(minutes=5))
        # disabled wins over an old problem and over "not heard from"
        self._connector('Off broken PC', state='disabled', last_error='HTTP 500', last_contact=now - timedelta(days=4))
        rows = self._rows(now=now)
        self.assertEqual({n: r['state'] for n, r in rows.items()},
                         {'Sending PC': 'ok', 'Off PC': 'disabled', 'Off broken PC': 'disabled'})
        self.assertFalse(rows['Off broken PC']['problem'])
        self.assertEqual({n for n, r in rows.items() if r['can_enable']}, {'Off PC', 'Off broken PC'})
        self.assertFalse([r for r in rows.values() if r['state'] == 'disabled' and r['can_switch']])
        # an officer sees the same state, never the button
        self.assertFalse([r for r in self._rows(self.officer, now).values() if r['can_enable']])
        data = self.facade().clocks()
        self.assertEqual((data['sending'], data['delivering'], data['later']), (1, 1, 0))
        counts = self.facade()._clock_counts()
        self.assertEqual((counts['stuck'], counts['disabled'], counts['live']), (0, 2, 1))
        # the order: disabled after the working ones
        self.assertEqual([r['name'] for r in data['clocks']], ['Sending PC', 'Off broken PC', 'Off PC'])

    def test_02_enable_from_step_6(self):
        now = fields.Datetime.now().replace(microsecond=0)
        conn = self._connector('Off PC', state='disabled', last_contact=now - timedelta(minutes=5))
        other = self._connector('Other off PC', state='disabled')
        theirs = self._connector('Their PC', company=self.other, state='disabled')
        with self.assertRaises(AccessError):
            self.facade(self.officer).clock_enable(conn.id)
        with self.assertRaises(AccessError):
            self.facade(self.admin_only).clock_enable(conn.id)
        self.assertEqual(conn.state, 'disabled')
        with self.assertRaisesRegex(UserError, 'no longer there'):
            self.facade().clock_enable(theirs.id)
        res = self.facade().clock_enable(conn.id)
        self.env.invalidate_all()
        self.assertEqual((conn.state, other.state, theirs.state), ('connected', 'disabled', 'disabled'))
        self.assertFalse(conn.publish_punches, 'the attendance tick is untouched')
        self.assertEqual((res['row']['state'], res['row']['can_enable']), ('held', False))
        self.assertIn('Off PC', res['summary'])
        self.assertTrue(any('Enabled.' in (m.body or '') for m in conn.message_ids))
        # again: harmless
        self.assertEqual(self.facade().clock_enable(conn.id)['row']['state'], 'held')

    def test_03_step_6_and_7_texts(self):
        now = fields.Datetime.now().replace(microsecond=0)
        conn = self._connector('Off PC', state='disabled', publish_punches=True, last_contact=now - timedelta(minutes=5))
        step = self._step()
        self.assertEqual((step['state'], step['text']), ('todo', 'Check and confirm'))
        self.facade().confirm_clocks()
        self.assertEqual(self._step()['text'], '1 clock disabled')
        item = {s['key']: s for s in self.facade().live_check(1)['steps']}['clocks']
        self.assertIn('No clock is sending clock-ins yet', item['text'])
        self.assertFalse(item['blocking'])
        self.assertFalse(self.facade().live_check(1, with_plan=False)['clocks_sending'])
        # enabled again (same tick, heard recently): sending, the step says so
        conn.sudo().write({'state': 'connected'})
        self.assertEqual(self._step()['text'], 'All connected')
        self.assertTrue(self.facade().live_check(1, with_plan=False)['clocks_sending'])
