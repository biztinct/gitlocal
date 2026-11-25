# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WFSETUP P6 — honest clocks (handover §3 tests 1-3).

1. step 6 gives the three states (sending / connected but switched off /
   not heard from) and is green only with a sending clock or the manager's
   confirmation;
2. "Switch clock-ins on" is the connector's own write, refused without clock
   rights, and touches only that connector;
3. the step 7 checklist and the finish payload carry the "no clock sending"
   variant when no clock sends.
"""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user, tagged

from .test_golive import GoLiveFixture, TZ


@tagged('post_install', '-at_install', 'wfsetup')
class TestP6Clocks(GoLiveFixture, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Settings administrator WITHOUT attendance-manager rights: passes the
        # studio's edit gate, but the clock's own write rule refuses him
        cls.admin_only = new_test_user(
            cls.env, login='wfs6_admin', groups='base.group_user,base.group_system',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])], tz=TZ)

    def _connector(self, name, company=None, **status):
        conn = self.env['pb.clock.connector'].sudo().create({
            'name': name, 'company_id': (company or self.company).id, 'source_group': name, 'tz': TZ})
        if status:
            conn.sudo().write(status)
        return conn

    def _step(self, user=None):
        return {s['key']: s for s in self.facade(user).load()['steps']}['clocks']

    def _rows(self, now=None):
        return {r['name']: r for r in self.facade()._clock_rows(now)}

    # ------------------------------------------------------------ 1
    def test_01_three_states(self):
        now = fields.Datetime.now().replace(microsecond=0)
        self._connector('Sending PC', state='connected', publish_punches=True,
                        last_contact=now - timedelta(minutes=20))
        self._connector('Held PC', state='connected', publish_punches=False,
                        last_contact=now - timedelta(minutes=20))
        self._connector('Silent PC', state='connected', publish_punches=False,
                        last_contact=now - timedelta(days=2))
        # a slow PC (every 4 hours): pb_clock waits 3 intervals before "overdue"
        self._connector('Slow PC', state='connected', publish_punches=True, interval_minutes=240,
                        last_contact=now - timedelta(hours=10))
        rows = self._rows(now)
        self.assertEqual({n: r['state'] for n, r in rows.items()},
                         {'Sending PC': 'ok', 'Held PC': 'held', 'Silent PC': 'quiet', 'Slow PC': 'ok'})
        self.assertEqual({n: r['sending'] for n, r in rows.items()},
                         {'Sending PC': True, 'Held PC': False, 'Silent PC': False, 'Slow PC': True})
        # the switch is offered on connected PCs that are off, to a manager only
        self.assertEqual({n for n, r in rows.items() if r['can_switch']}, {'Held PC', 'Silent PC'})
        data = self.facade().clocks()
        self.assertEqual((data['sending'], data['delivering'], data['later']), (2, 3, 2))
        self.assertTrue(data['can_switch'])
        off = self.facade(self.officer).clocks()
        self.assertFalse(off['can_switch'])
        self.assertFalse([r for r in off['clocks'] if r['can_switch']])
        # a machine: 180 s, pb_clock's own "connected" chip; no switch
        machine = self.env['pb.clock.device'].sudo().create({
            'name': 'Push machine', 'serial': 'WFS6-001', 'company_id': self.company.id, 'kind': 'terminal',
            'state': 'allowed'})
        machine.sudo().write({'allowed_at': now - timedelta(days=3), 'last_seen_at': now - timedelta(seconds=60)})
        self.assertEqual(self._rows(now)['Push machine']['state'], 'ok')
        machine.sudo().write({'last_seen_at': now - timedelta(minutes=10)})
        row = self._rows(now)['Push machine']
        self.assertEqual((row['state'], row['switch'], row['can_switch']), ('quiet', False, False))

    def test_02_step_green_only_when_sending_or_confirmed(self):
        now = fields.Datetime.now().replace(microsecond=0)
        held = self._connector('Held PC', state='connected', last_contact=now - timedelta(minutes=5))
        self._connector('Silent PC', state='connected', last_contact=now - timedelta(days=2))
        step = self._step()
        self.assertNotEqual(step['state'], 'done', 'connected but switched off is never green')
        self.assertEqual((step['state'], step['text']), ('warn', 'Clock-ins switched off'))
        # one sending clock -> green
        held.sudo().write({'publish_punches': True})
        step = self._step()
        self.assertEqual((step['state'], step['text']), ('done', '1 clock sending clock-ins'))
        # switched off again, but the manager confirms the step -> green (the escape stays)
        held.sudo().write({'publish_punches': False})
        self.assertNotEqual(self._step()['state'], 'done')
        res = self.facade().confirm_clocks()
        self.assertEqual(res['later'], 2)
        self.assertEqual(self._step()['state'], 'done')

    def test_03_no_clock_at_all(self):
        step = self._step()
        self.assertEqual((step['state'], step['text']), ('todo', 'Check and confirm'))
        self.facade().confirm_clocks()
        self.assertEqual(self._step()['text'], 'Confirmed without a clock')

    # ------------------------------------------------------------ 2
    def test_04_switch_on(self):
        now = fields.Datetime.now().replace(microsecond=0)
        conn = self._connector('Held PC', state='connected', last_contact=now - timedelta(minutes=5))
        other = self._connector('Other held PC', state='connected', last_contact=now - timedelta(minutes=5))
        theirs = self._connector('Their PC', company=self.other, state='connected', last_contact=now)
        # refused: officer (studio gate) and an administrator without clock rights
        # (the connector's own write rule) — nothing written either time
        with self.assertRaises(AccessError):
            self.facade(self.officer).clock_switch_on(conn.id)
        with self.assertRaises(AccessError):
            self.facade(self.admin_only).clock_switch_on(conn.id)
        self.assertFalse(self.facade(self.admin_only).clocks()['can_switch'])
        self.assertFalse(conn.publish_punches)
        # another company's clock: not there for this company
        with self.assertRaisesRegex(UserError, 'no longer there'):
            self.facade().clock_switch_on(theirs.id)
        self.assertFalse(theirs.publish_punches)
        # the manager: only this connector, and the tracked change is his
        res = self.facade().clock_switch_on(conn.id)
        self.env.invalidate_all()
        self.assertTrue(conn.publish_punches)
        self.assertFalse(other.publish_punches)
        self.assertFalse(theirs.publish_punches)
        self.assertEqual((res['row']['state'], res['row']['sending'], res['row']['can_switch']), ('ok', True, False))
        self.assertIn('Held PC', res['summary'])
        self.assertEqual(conn.write_uid, self.manager, 'written as the manager, not as the superuser')
        # again: harmless
        self.assertTrue(self.facade().clock_switch_on(conn.id)['row']['sending'])

    # ------------------------------------------------------------ 3
    def test_05_finish_and_checklist_variants(self):
        def clocks_item(data):
            return {s['key']: s for s in data['steps']}['clocks']

        # no clock sending: amber item (never blocking) and the finish variant
        data = self.facade().live_check(1)
        item = clocks_item(data)
        self.assertFalse(item['ok'])
        self.assertFalse(item['blocking'])
        self.assertIn('No clock is sending clock-ins yet', item['text'])
        self.assertFalse(data['clocks_sending'])
        self.assertTrue(data['can_publish'], 'a roster may go live before its clocks are on')
        # the manager confirmed the step: still no clock sends -> still amber
        self.facade().confirm_clocks()
        self.assertIn('No clock is sending', clocks_item(self.facade().live_check(1))['text'])
        _start, finish = self.publish(1)
        self.assertIs(finish['clocks_sending'], False)
        # a clock is heard from: the paid-hours line comes back
        now = fields.Datetime.now().replace(microsecond=0)
        conn = self._connector('Sending PC', state='connected', publish_punches=True,
                               last_contact=now - timedelta(minutes=5))
        data = self.facade().live_check(1, with_plan=False)
        self.assertTrue(data['clocks_sending'])
        self.assertNotIn('No clock is sending', clocks_item(data)['text'])
        _start, finish = self.publish(1)
        self.assertIs(finish['clocks_sending'], True)
        # switched off but heard from: its records still reach the rules
        conn.sudo().write({'publish_punches': False})
        self.assertTrue(self.facade().live_check(1, with_plan=False)['clocks_sending'])
