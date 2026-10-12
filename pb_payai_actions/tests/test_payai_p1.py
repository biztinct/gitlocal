# -*- coding: utf-8 -*-
"""PAYAI P1 — numbered tests 1–12 of P1_HANDOVER.md.

Every gate is called for an explicit user with that user's own rights
(ledger PA12: the test env is superuser and must never answer for them).
No test reaches a real AI provider: the phrase table needs none, and the
tests that need one get a recording fake.
"""
import json
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payai_actions.payai import gate, registry
from odoo.addons.pb_payai_actions.payai.registry import ACTIONS

GREEN = {'open_screen', 'run_status', 'download_run_excel', 'what_can_you_do'}
AMBER = {'run_payroll', 'submit_run', 'update_pay_data', 'send_payslips', 'filing_prepare'}
RED = {'approve_item', 'send_back_item', 'reject_item'}

DOORS = [
    {'id': 'payhub', 'label': 'Pay Run', 'sublabel': 'Payroll operations', 'group': 'Missions',
     'groups': ['om_hr_payroll.group_hr_payroll_user']},
    {'id': 'payhub_run', 'label': 'Run Payroll', 'sublabel': 'Pay Run', 'group': 'Pay Run',
     'groups': ['om_hr_payroll.group_hr_payroll_user']},
    {'id': 'payhub_runs', 'label': 'Pay Runs', 'sublabel': 'Pay Run', 'group': 'Pay Run',
     'groups': ['om_hr_payroll.group_hr_payroll_user']},
    {'id': 'payhub_payslips', 'label': 'Payslips', 'sublabel': 'Pay Run', 'group': 'Pay Run',
     'groups': ['om_hr_payroll.group_hr_payroll_user']},
    {'id': 'va_access', 'label': 'Access & delegation', 'sublabel': 'Admin', 'group': 'Admin',
     'groups': ['base.group_system']},
    # P2-F1: two lenses with the same name in two places — "open approvals"
    # is a question, never a guess.
    {'id': 'homehub_approvals', 'label': 'Approvals', 'sublabel': 'Home', 'group': '',
     'groups': [], 'kind': 'lens'},
    {'id': 'wf_approvals', 'label': 'Approvals', 'sublabel': 'Mission Control', 'group': '',
     'groups': [], 'kind': 'lens'},
]


class _FakeProvider:
    def __init__(self, sink, tool=None, intent='payroll_knowledge',
                 answer='{"response": "Gross pay is pay before deductions."}'):
        self.sink = sink
        self.tool = tool
        self.intent = intent
        self.answer = answer

    def is_available(self):
        return True

    def generate_tools(self, messages, tools, **kw):
        self.sink.append({'messages': messages, 'tools': tools})
        return self.tool

    def generate_text(self, prompt, **kw):
        return self.intent

    def generate_chat(self, messages, **kw):
        return self.answer

    def _parse_json_response(self, text):
        return json.loads(text)


class _FakeConfig:
    def __init__(self, provider):
        self.provider = provider

    def __bool__(self):
        return True

    def get_provider(self):
        return self.provider


@tagged('post_install', '-at_install', 'payai')
class TestPayaiP1(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'payai_tier_look': True, 'payai_tier_prepare': True,
                           'payai_tier_decide': True})
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g = cls.env.ref
        base = g('base.group_user').id
        cls.officer = Users.create({
            'name': 'PayAI Officer', 'login': 'payai.officer@test.invalid',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [base, g('pb_hr_payroll_base.group_payroll_base_officer').id,
                                  g('om_hr_payroll.group_hr_payroll_user').id])]})
        # Holds the ACL on pay runs (officer tier) but NOT the permission the
        # Pay Run screen asks for: the back door PA-R1 closes.
        cls.backdoor = Users.create({
            'name': 'PayAI Backdoor', 'login': 'payai.backdoor@test.invalid',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [base, g('pb_hr_payroll_base.group_payroll_base_officer').id])]})
        cls.plain = Users.create({
            'name': 'PayAI Plain', 'login': 'payai.plain@test.invalid',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [base])]})
        cls.portal = Users.create({
            'name': 'PayAI Portal', 'login': 'payai.portal@test.invalid',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [g('base.group_portal').id])]})
        cls.manager = Users.create({
            'name': 'PayAI Manager', 'login': 'payai.manager@test.invalid',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [base, g('om_hr_payroll.group_hr_payroll_manager').id,
                                  g('om_hr_payroll.group_hr_payroll_user').id])]})
        Run = cls.env['hr.payslip.run']
        cls.run_draft = Run.create({'name': 'PAYAI Test June 2031 Zebra',
                                    'date_start': '2031-06-01', 'date_end': '2031-06-30'})
        cls.run_done = Run.create({'name': 'PAYAI Test May 2031 Okapi',
                                   'date_start': '2031-05-01', 'date_end': '2031-05-31'})
        # The state seal refuses an ORM write; a test fixture sets it in SQL.
        cls.env.cr.execute("UPDATE hr_payslip_run SET state = 'done' WHERE id = %s",
                           (cls.run_done.id,))
        cls.run_done.invalidate_recordset(['state'])
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Zyxwq Testperson', 'company_id': cls.company.id})

    # -------------------------------------------------------------- helpers
    def _session(self, user):
        Conv = self.env['payroll.ai.conversation'].with_user(user)
        session = Conv.create({'name': 'PayAI P1 test', 'user_id': user.id})
        Conv.rpc_register_doors(session.id, DOORS)
        return session

    def _send(self, user, text, session=None, resolve=None):
        session = session or self._session(user)
        out = self.env['payroll.ai.conversation'].with_user(user).rpc_send_message(
            text, session.id, None, resolve=resolve)
        return out, session

    def _no_provider(self):
        Config = self.registry['payroll.ai.config']
        return patch.object(Config, 'get_active_config',
                            lambda self, *a, **k: self.browse())

    def _provider(self, provider):
        Config = self.registry['payroll.ai.config']
        return patch.object(Config, 'get_active_config',
                            lambda self, *a, **k: _FakeConfig(provider))

    def _tasks(self, user):
        return self.env['payai.task'].sudo().search([('user_id', '=', user.id)])

    # ================================================================ 1
    def test_01_registry_and_tools_schema(self):
        for key, action in ACTIONS.items():
            self.assertTrue(action.key and str(action.title), key)
            self.assertIn(action.tier, registry.TIERS, key)
            if key not in ('open_screen', 'what_can_you_do') and action.tier != 'never':
                self.assertTrue(action.screen_keys, '%s names no screen' % key)
        stubs = {k for k, a in ACTIONS.items() if a.stub}
        # P3: Amber and Red are built; only the never tier is declared-only.
        self.assertFalse((AMBER | RED) & stubs)
        self.assertTrue(RED <= set(ACTIONS))
        for key in RED:
            self.assertEqual(ACTIONS[key].tier, 'decide')
            self.assertTrue(ACTIONS[key].confirm_word)
        tools = registry.tools_schema(self.env, self.officer)
        json.dumps(tools)
        names = {t['name'] for t in tools}
        self.assertTrue(names <= GREEN | AMBER | RED, names)
        self.assertFalse(names & stubs)
        self.assertIn('run_status', names)
        for t in tools:
            schema = t['parameters']
            self.assertEqual(schema['type'], 'object')
            self.assertFalse(schema['additionalProperties'])
            for prop in schema['properties'].values():
                self.assertEqual(prop['type'], 'string')   # words, never ids
            self.assertTrue(set(schema['required']) <= set(schema['properties']))
        # The phrase table never reads a how-to question as an order.
        self.assertIsNone(registry.match('How do I run payroll?'))
        self.assertEqual(registry.match('Run June payroll for Retail')[0], 'run_payroll')
        self.assertEqual(registry.match('Open the Runs board')[0], 'open_screen')
        self.assertEqual(registry.match('Show the June run')[0], 'run_status')
        self.assertEqual(registry.match('What can you do?')[0], 'what_can_you_do')
        self.assertEqual(registry.match('Delete the May run')[0], 'never_destructive')

    # ================================================================ 2
    def test_02_gate_both_halves(self):
        status = ACTIONS['run_status']
        self.assertEqual(gate.allowed(self.env, self.officer, status), (True, ''))
        ok, reason = gate.allowed(self.env, self.plain, status)
        self.assertFalse(ok)
        self.assertEqual(reason, 'no_right')
        self.assertIn('Settings › Access and delegations', gate.refusal_text(status, reason))
        ok, reason = gate.allowed(self.env, self.portal, status)
        self.assertFalse(ok)
        # The back door: the ACL would allow, the Access home does not. An
        # administrator takes the Pay Run screen away from the officer ROLE in
        # Access (the role lane, biz_access); the officer group still holds
        # read on pay runs by ACL.
        item = gate.screen_item(self.env, status)
        self.assertTrue(item, 'no active Pay Run screen on this database')
        if 'role_ids' in item._fields:
            item.sudo().write({'role_ids': [(5, 0, 0)]})
        self.assertTrue(self.env['hr.payslip.run'].with_user(self.backdoor).has_access('read'))
        ok, reason = gate.allowed(self.env, self.backdoor, status)
        self.assertEqual((ok, reason), (False, 'screen_off'))
        # And a screen LOCKED for a person who holds every right refuses too.
        Item = self.registry['pb.sidebar.item']
        real = Item.visibility_for

        def locked(self_, user):
            out = real(self_, user)
            out['items'][item.id] = 'locked'
            return out
        with patch.object(Item, 'visibility_for', locked):
            self.assertEqual(gate.allowed(self.env, self.officer, status),
                             (False, 'screen_off'))
        # Through the chat, the refusal is a card.
        with self._no_provider():
            out, _s = self._send(self.backdoor, 'Show the June 2031 run')
        self.assertEqual(out['card']['kind'], 'refused')
        self.assertEqual(self._tasks(self.backdoor)[:1].state, 'refused')

    # ================================================================ 3
    def test_03_switch_off_falls_back(self):
        self.company.payai_tier_look = False
        sink = []
        with self._provider(_FakeProvider(sink, intent='general',
                                          answer='{"response": "Plain answer."}')):
            out, _s = self._send(self.officer, 'Open the runs board')
        self.assertFalse(out.get('card'))
        self.assertEqual(out['response'], 'Plain answer.')
        self.assertNotIn('What can you do?', out['follow_up_questions'])
        self.assertFalse(sink, 'the tools call ran with the switch off')
        self.assertFalse(self._tasks(self.officer))

    # ================================================================ 4
    def test_04_open_screen_and_clarify(self):
        with self._no_provider():
            out, session = self._send(self.officer, 'Open the runs board')
            card = out['card']
            self.assertEqual(card['kind'], 'done')
            door = [a for a in card['actions'] if a['id'] == 'door']
            self.assertEqual(door[0]['door_id'], 'payhub_runs')
            self.assertTrue(door[0].get('auto'))
            hist = session.with_user(self.officer).get_history()
            self.assertEqual(hist[-1]['card']['kind'], 'done')

            out, session = self._send(self.officer, 'Open approvals', session)
            card = out['card']
            self.assertEqual(card['kind'], 'clarify')
            self.assertTrue(2 <= len(card['chips']) <= 6, card['chips'])
            values = [c['value'] for c in card['chips']]
            self.assertIn('homehub_approvals', values)
            task = self.env['payai.task'].sudo().browse(card['task_id'])
            self.assertEqual(task.state, 'clarify')

            out, session = self._send(
                self.officer, 'Approvals', session,
                resolve={'task_id': card['task_id'], 'slot': card['chip_slot'],
                         'value': 'homehub_approvals'})
        self.assertEqual(out['card']['kind'], 'done')
        self.assertEqual(out['card']['task_id'], task.id)
        self.assertEqual(task.state, 'done')
        params = json.loads(task.params_json)
        self.assertEqual(params['resolved']['door']['origin'], 'chose')
        # A value the server did not offer is refused.
        with self._no_provider():
            out2, _s = self._send(self.officer, 'Open approvals', session)
            with self.assertRaises(AccessError):
                self._send(self.officer, 'x', session, resolve={
                    'task_id': out2['card']['task_id'], 'slot': 'door', 'value': 'va_access'})

    # ================================================================ 5
    def test_05_door_not_held_refused(self):
        with self._no_provider():
            out, _s = self._send(self.officer, 'Open access and delegation')
        self.assertEqual(out['card']['kind'], 'refused')
        self.assertFalse([a for a in out['card']['actions']
                          if a.get('door_id') == 'va_access'])

    # ================================================================ 6
    def test_06_run_status(self):
        with self._no_provider():
            out, _s = self._send(self.officer, 'Show the June 2031 run')
        card = out['card']
        self.assertEqual(card['kind'], 'done', card)
        self.assertEqual(card['title'], self.run_draft.name)
        labels = [t['label'] for t in card['result']]
        self.assertIn('people', labels)
        self.assertIn('net pay', labels)
        door = [a for a in card['actions'] if a['id'] == 'door']
        self.assertEqual(door[0]['hub']['focus'], str(self.run_draft.id))
        with self._no_provider():
            out, _s = self._send(self.plain, 'Show the June 2031 run')
        self.assertEqual(out['card']['kind'], 'refused')
        self.assertNotIn(self.run_draft.name, json.dumps(out['card']))

    # ================================================================ 7
    def test_07_download_excel(self):
        with self._no_provider():
            out, _s = self._send(self.officer, 'Download the June 2031 run')
        self.assertEqual(out['card']['kind'], 'refused')
        self.assertIn('approved', json.dumps(out['card']))
        Run = self.registry['hr.payslip.run']
        with self._no_provider(), patch.object(
                Run, 'action_download_payslip_xlsx',
                lambda self_: {'type': 'ir.actions.act_url',
                               'url': '/web/content/1?download=true', 'target': 'self'}):
            out, _s = self._send(self.officer, 'Download the May 2031 run')
        card = out['card']
        self.assertEqual(card['kind'], 'done', card)
        dl = [a for a in card['actions'] if a['id'] == 'download']
        self.assertTrue(dl[0]['url'].startswith('/web/content/'))

    # ================================================================ 8
    def test_08_expiry_and_owner(self):
        with self._no_provider():
            out, session = self._send(self.officer, 'Open approvals')
            card = out['card']
            task = self.env['payai.task'].sudo().browse(card['task_id'])
            task.write({'expires_at': fields.Datetime.now() - timedelta(minutes=11)})
            out, _s = self._send(self.officer, 'Approvals', session, resolve={
                'task_id': task.id, 'slot': 'door', 'value': 'homehub_approvals'})
            self.assertIn('expired', out['card']['title'])
            self.assertEqual(task.state, 'expired')
            # Somebody else answering the officer's question: refused.
            out, session = self._send(self.officer, 'Open approvals', session)
            with self.assertRaises(AccessError):
                self._send(self.manager, 'Approvals', resolve={
                    'task_id': out['card']['task_id'], 'slot': 'door',
                    'value': 'homehub_approvals'})

    # ================================================================ 9
    def test_09_audit_rows(self):
        with self._no_provider():
            self._send(self.plain, 'Show the June 2031 run for Zyxwq Testperson')
            self._send(self.officer, 'Open the runs board')
        refused = self._tasks(self.plain)
        self.assertEqual(refused[:1].state, 'refused')
        self.assertNotIn('Zyxwq', refused[:1].utterance or '')
        self.assertIn('[person-', refused[:1].utterance or '')
        done = self._tasks(self.officer)
        self.assertEqual(done[:1].state, 'done')
        Task = self.env['payai.task']
        self.assertFalse(Task.with_user(self.plain).search([('id', '=', done[:1].id)]))
        self.assertTrue(Task.with_user(self.manager).search([('id', '=', done[:1].id)]))
        self.assertTrue(Task.with_user(self.manager).search([('id', '=', refused[:1].id)]))
        # Nobody writes the audit by RPC.
        with self.assertRaises(AccessError):
            Task.with_user(self.officer).create({
                'user_id': self.officer.id, 'company_id': self.company.id,
                'action_key': 'open_screen'})
        # The Audit console lists them.
        rows = self.env['pb.audit.console']._fetch_payai({}, 50)
        self.assertTrue(any('Asked PayAI' in r['title'] for r in rows))

    # =============================================================== 10
    def test_10_phrase_table_without_provider(self):
        with self._no_provider():
            out, _s = self._send(self.officer, 'open the runs board')
        self.assertEqual(out['card']['kind'], 'done')

    # =============================================================== 11
    def test_11_tools_call_is_redacted(self):
        sink = []
        with self._provider(_FakeProvider(sink)):
            self._send(self.officer, 'Find the latest payslip of Zyxwq Testperson')
        self.assertTrue(sink, 'the tools call did not run')
        sent = ' '.join(m['content'] for m in sink[0]['messages'])
        self.assertNotIn('Zyxwq', sent)
        self.assertIn('[person-', sent)
        self.assertTrue({t['name'] for t in sink[0]['tools']} <= GREEN | AMBER | RED)

    # =============================================================== 12
    def test_12_question_unchanged_plus_chip(self):
        sink = []
        with self._provider(_FakeProvider(sink)):
            out, _s = self._send(self.officer, 'what is gross pay')
        self.assertFalse(out.get('card'))
        self.assertEqual(out['response'], 'Gross pay is pay before deductions.')
        self.assertIn('What can you do?', out['follow_up_questions'])
        self.assertFalse(sink, 'a how/what-is question went to the tools call')

    # ========================================================== extras
    def test_13_stub_and_never_cards(self):
        with self._no_provider():
            # P3: a Red sentence with nothing waiting for this person: an
            # honest answer and the door, never a plan, never a decision.
            out, _s = self._send(self.officer, 'Approve the June 2031 run')
            card = out['card']
            self.assertIn(card['kind'], ('refused', 'blocked'), card)
            self.assertNotEqual(card.get('state'), 'planned')
            out, _s = self._send(self.plain, 'Run June payroll for Retail')
            self.assertIn('Run payroll right', json.dumps(out['card']))
            out, _s = self._send(self.officer, 'Delete the May run')
            self.assertEqual(out['card']['tier'], 'never')
            out, _s = self._send(self.officer, 'What can you do?')
            groups = out['card']['groups']
            self.assertEqual(groups[0]['tone'], 'ok')
            self.company.payai_tier_prepare = False
            out, _s = self._send(self.officer, 'Run June payroll for Retail')
            self.assertIn('Settings › PayAI can act',
                          json.dumps(out['card'], ensure_ascii=False))
