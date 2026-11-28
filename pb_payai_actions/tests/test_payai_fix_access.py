# -*- coding: utf-8 -*-
"""PAYAI FIX-1b — OWNER RULING 2026-10-13: PayAI never reaches Settings ›
Access and delegations (FIX1_HANDOVER.md §FIX-1b, points 1–5), and P3:sec-4:
Red is refused when the asker's Approvals screen is hidden or locked for them
in Access and delegations.

Fixtures are the P1 doors/people and the P3 Red world, reached through their
modules (PA56; their own tests are switched off at the bottom — they run in
P1 / P3). Every gate is judged for an explicit user (PA12), no AI provider is
reached except the recording fake, fixtures in 2031 (PA40).
"""
import ast
import json
import os
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import tagged

from odoo.addons.pb_payai_actions.payai import actions_red, gate, runner
from odoo.addons.pb_payai_actions.payai.registry import ACTIONS
from odoo.addons.pb_payai_actions.tests import test_payai_p1 as p1
from odoo.addons.pb_payai_actions.tests import test_payai_p3 as p3

#: Every ⌘K row into the Access home, as the modules register them (ids and
#: their actions — the browser sends both since FIX-1b).
ACCESS_ROWS = [
    {'id': 'va_access', 'label': 'Access & delegation', 'sublabel': 'Admin',
     'groups': ['base.group_user'], 'target': {'xmlid': 'biz_access.action_pb_access_board'}},
    {'id': 'va_delegate', 'label': 'Hand my access to somebody', 'sublabel': 'Access',
     'groups': ['base.group_user'], 'target': {'xmlid': 'biz_access.action_pb_access_board'}},
    {'id': 'va_history', 'label': 'Access history', 'sublabel': 'Admin', 'groups': [],
     'target': {'xmlid': 'biz_access.action_pb_access_delegation'}},
    {'id': 'va_roles', 'label': 'Roles', 'sublabel': 'Admin', 'groups': [],
     'target': {'xmlid': 'biz_access.action_pb_role_profile'}},
    {'id': 'va_screens', 'label': 'The left menu', 'sublabel': 'Access', 'groups': [],
     'target': {'xmlid': 'biz_access.action_pb_access_board', 'lens': 'screens'}},
    {'id': 'approval_people', 'label': 'People & backups', 'sublabel': 'Approvals',
     'groups': [], 'target': {'xmlid': 'pb_approval_config.action_pb_approval_matrix',
                              'focus': 'people'}},
    {'id': 'learn.station.access', 'label': 'Access and delegation',
     'sublabel': 'Lesson · 5 min · how to', 'groups': [], 'kind': 'learn',
     'target': {'xmlid': 'pb_learn.action_learn_hub', 'lens': 'lessons',
                'focus': 'station:access'}},
    {'id': 'learn.scenario.sc_access', 'label': 'Access, and handing it over',
     'sublabel': 'Walkthrough · how to', 'groups': [], 'kind': 'learn',
     'target': {'xmlid': 'pb_learn.action_learn_hub', 'lens': 'lessons',
                'focus': 'scenario:sc_access:watch'}},
    # A row a module might add one day under a new id: caught by where it leads.
    {'id': 'some_new_access_row', 'label': 'Who can do what', 'sublabel': 'Admin',
     'groups': [], 'target': {'tag': 'pb_access_board', 'lens': 'people'}},
]
OPEN_ROWS = [
    {'id': 'payhub_runs', 'label': 'Pay Runs', 'sublabel': 'Pay Run', 'groups': [],
     'kind': 'lens', 'target': {'xmlid': 'pb_payhub.action_pb_pay_hub', 'lens': 'runs'}},
    {'id': 'approval_matrix', 'label': 'Approval Matrix', 'sublabel': 'Settings',
     'groups': [], 'target': {'xmlid': 'pb_approval_config.action_pb_approval_matrix'}},
    {'id': 'learn.station.payruns', 'label': 'Runs', 'sublabel': 'Lesson', 'groups': [],
     'kind': 'learn', 'target': {'xmlid': 'pb_learn.action_learn_hub',
                                 'focus': 'station:payruns'}},
]
NEVER_TEXT = 'PayAI does not open or change access. Go to Settings › Access and delegations yourself.'
ASK_ADMIN = 'Ask your administrator to change this under Settings › Access and delegations.'
#: Methods of the Access home and the approval hand-overs that change access.
ACCESS_WRITE_METHODS = frozenset((
    'action_activate', 'action_revoke', 'archive_role', 'copy_roles', 'create_role',
    'create_user', 'delegate', 'grant', 'grant_many', 'reorder_screens',
    'reseed_catalogue', 'restore_role_version', 'revoke', 'role_version_draft',
    'set_screen_flags', 'set_screen_roles', 'update_role', 'set_delegation',
    'end_delegation', 'run_auto_revert', 'cron_auto_revert', 'set_holder',
))
#: Access models whose writes the dynamic check watches (`res.users` is left
#: out: signing in and sessions write it on their own).
WATCHED_MODELS = ('pb.access.request', 'pb.access.delegation', 'pb.role.profile',
                  'pb.role.ability', 'pb.role.assignment', 'pb.role.change',
                  'biz.approval.delegation', 'res.groups', 'pb.sidebar.item',
                  'pb.sidebar.section')


def _doors_on(card):
    """Every door id and hub a card offers."""
    out = []
    for act in card.get('actions') or []:
        out.append((act.get('door_id') or '', json.dumps(act.get('hub') or {})))
    return out


@tagged('post_install', '-at_install', 'payai')
class TestPayaiFixAccess(p1.TestPayaiP1):

    def _session_with(self, user, rows):
        Conv = self.env['payroll.ai.conversation'].with_user(user)
        session = Conv.create({'name': 'PayAI FIX-1b test', 'user_id': user.id})
        Conv.rpc_register_doors(session.id, rows)
        return session

    def _ctx(self, user, session):
        engine = self.env['payroll.ai.engine'].with_user(user)
        return runner.Ctx(engine, {'conversation_id': session.id})

    def _assert_no_access_door(self, card):
        blob = json.dumps(card, ensure_ascii=False)
        for door_id, hub in _doors_on(card):
            self.assertFalse(gate.door_denied(door_id), (door_id, card))
            self.assertFalse(gate.target_denied(json.loads(hub)), (hub, card))
        for rid in gate.ACCESS_DOORS:
            self.assertNotIn('"%s"' % rid, blob)
        for xmlid in gate.ACCESS_XMLIDS | gate.ACCESS_TAGS:
            self.assertNotIn(xmlid, blob)
        self.assertNotIn('Open Access and delegations', blob)

    def _assert_never(self, out, text):
        card = out['card']
        self.assertEqual((card['kind'], card['tier']), ('refused', 'never'), (text, card))
        self.assertEqual(card['actions'], [], (text, card))
        self.assertIn(NEVER_TEXT, json.dumps(card, ensure_ascii=False), text)
        self.assertNotEqual(card.get('state'), 'planned')
        self._assert_no_access_door(card)
        task = self.env['payai.task'].sudo().browse(card['task_id'])
        self.assertEqual(task.state, 'refused', text)

    # ======================================================== 1 — no door
    def test_fb01_denied_doors_are_never_stored_or_held(self):
        session = self._session_with(self.officer, ACCESS_ROWS + OPEN_ROWS)
        stored = {r['id'] for r in session.sudo().payai_doors()}
        self.assertEqual(stored, {r['id'] for r in OPEN_ROWS})
        # A row stored before the deny-list existed (written straight in) is
        # dropped when read, and the person's context never holds it.
        session.sudo().write({'payai_doors_json': json.dumps(ACCESS_ROWS + OPEN_ROWS)})
        self.assertEqual({r['id'] for r in session.sudo().payai_doors()}, stored)
        ctx = self._ctx(self.officer, session)
        self.assertEqual({r['id'] for r in ctx.doors}, stored)
        for row in ACCESS_ROWS:
            self.assertFalse(ctx.has_door(row['id']), row['id'])
            self.assertIsNone(ctx.door_row(row['id']), row['id'])
        # The approval matrix itself, a run lesson and the runs board stay.
        self.assertTrue(ctx.has_door('approval_matrix'))
        self.assertTrue(ctx.has_door('learn.station.payruns'))
        # No Action names a denied door as its own.
        for key, action in ACTIONS.items():
            self.assertFalse(gate.door_denied(action.door_id or ''), key)

    def test_fb02_open_screen_for_each_denied_door_is_refused_without_a_door(self):
        with self._no_provider():
            for text in ('Open access and delegation', 'Open Access & delegation',
                         'Open roles', 'Open access history', 'Open the left menu',
                         'Open people & backups', 'Hand my access to somebody',
                         'Open the access and delegation lesson', 'Go to permissions',
                         'Open delegations', 'Open hand-overs'):
                session = self._session_with(self.officer, ACCESS_ROWS + OPEN_ROWS)
                out, _s = self._send(self.officer, text, session)
                self._assert_never(out, text)

    def test_fb03_the_models_door_names_are_refused_too(self):
        """The model routes a sentence the phrase table does not read to
        `open_screen` with a screen named in access words: the same card."""
        for i, door in enumerate(('Access & delegation', 'Hand my access to somebody',
                                  'The left menu', 'Roles', 'phân quyền')):
            sink = []
            fake = p1._FakeProvider(sink, tool={'tool_name': 'open_screen',
                                                'arguments': {'door': door}})
            session = self._session_with(self.officer, ACCESS_ROWS + OPEN_ROWS)
            # A sentence no phrase reads, different each time (the routing
            # cache answers a repeated one without asking the model).
            with self._provider(fake):
                out, _s = self._send(self.officer, 'I am looking for admin page number %d'
                                     % (2031 + i), session)
            self.assertTrue(sink, 'the tools call was not reached')
            self._assert_never(out, door)

    def test_fb04_a_denied_door_pinned_or_chosen_is_refused(self):
        session = self._session_with(self.officer, ACCESS_ROWS + OPEN_ROWS)
        ctx = self._ctx(self.officer, session)
        for row in ACCESS_ROWS:
            pinned = {'door': {'status': 'resolved', 'value': row['id'], 'label': row['label'],
                               'origin': 'said', 'candidates': []}}
            card = runner.run(ctx, 'open_screen', {}, 'x', pinned=pinned)
            self.assertEqual(card['kind'], 'refused', (row['id'], card))
            self.assertEqual(card['actions'], [], card)
            self._assert_no_access_door(card)
        # A chip value the server never offered is refused (P1 test 4's rule).
        with self._no_provider():
            out, session = self._send(self.officer, 'Open approvals')
            with self.assertRaises(AccessError):
                self._send(self.officer, 'x', session, resolve={
                    'task_id': out['card']['task_id'], 'slot': 'door', 'value': 'va_roles'})

    # ================================================ 2 — refusal cards
    def test_fb05_no_refusal_card_offers_access(self):
        session = self._session_with(self.plain, ACCESS_ROWS + OPEN_ROWS)
        with self._no_provider():
            out, _s = self._send(self.plain, 'Show the June 2031 run', session)
        card = out['card']
        self.assertEqual(card['kind'], 'refused', card)
        self.assertIn(ASK_ADMIN, json.dumps(card, ensure_ascii=False))
        self.assertEqual([a for a in card['actions'] if a.get('id') == 'door'], [])
        self._assert_no_access_door(card)
        # Every refusal of every Action, for every reason, even for a person
        # whose conversation once stored the Access rows.
        session = self._session_with(self.officer, ACCESS_ROWS + OPEN_ROWS)
        session.sudo().write({'payai_doors_json': json.dumps(ACCESS_ROWS + OPEN_ROWS)})
        ctx = self._ctx(self.officer, session)
        for key, action in ACTIONS.items():
            for reason in ('no_right', 'screen_off', 'tier_off', 'never'):
                card = runner._refusal_card(ctx, action, reason)
                self._assert_no_access_door(card)
                if reason in ('no_right', 'screen_off'):
                    self.assertIn(ASK_ADMIN, json.dumps(card, ensure_ascii=False), key)
                    self.assertEqual(card['actions'], [], (key, reason))

    def test_fb06_scrub_card_everywhere_a_card_leaves(self):
        card = {'kind': 'done', 'actions': [
            {'id': 'door', 'door_id': 'va_access', 'label': 'x'},
            {'id': 'door', 'door_id': 'homehub_approvals', 'label': 'y',
             'hub': {'xmlid': 'biz_access.action_pb_access_board'}},
            {'id': 'door', 'door_id': 'payhub_runs', 'label': 'z',
             'hub': {'tag': 'pb_pay_hub', 'lens': 'runs'}},
            {'id': 'learn', 'scenario': 'sc_access'},
            {'id': 'learn', 'scenario': 'sc_payslips'}],
            'chips': [{'value': 'va_delegate', 'label': 'a'}, {'value': 7, 'label': 'b'}]}
        out = runner.envelope(json.loads(json.dumps(card)))['card']
        self.assertEqual([a.get('door_id') or a.get('scenario') for a in out['actions']],
                         ['payhub_runs', 'sc_payslips'])
        self.assertEqual([c['label'] for c in out['chips']], ['b'])
        # A card stored in the history before FIX-1b is drawn without it.
        session = self._session_with(self.officer, OPEN_ROWS)
        msg = self.env['payroll.ai.message'].sudo().create({
            'conversation_id': session.id, 'role': 'assistant', 'content': 'x',
            'card': json.dumps(card)})
        drawn = msg.with_user(self.officer)._card_dict()
        self.assertEqual([a.get('door_id') or a.get('scenario') for a in drawn['actions']],
                         ['payhub_runs', 'sc_payslips'])

    # ================================================ 3 — the never card
    def test_fb07_access_orders_get_the_never_card_en_and_vi(self):
        sentences = (
            'open access and delegations', "change Lan's role",
            'Give Lan the payroll manager role', 'remove admin rights from Lan',
            'lend my role to Lan', 'hand over my approvals to Lan',
            "Approve Lan's access request", 'please open access and delegations',
            'mở phân quyền', 'mo phan quyen', 'đổi vai trò của Lan', 'cấp quyền cho Lan',
            'thu hồi quyền của Lan', 'uỷ quyền cho Minh', 'bàn giao quyền của tôi cho Lan',
            'quyền truy cập', 'duyệt yêu cầu truy cập của Lan')
        with self._no_provider():
            for text in sentences:
                out, _s = self._send(self.officer, text)
                self._assert_never(out, text)
                task = self.env['payai.task'].sudo().browse(out['card']['task_id'])
                self.assertEqual(task.action_key, 'never_access', text)
        # Look-alikes stay what they were.
        for text, key in (('Open the Runs board', 'open_screen'),
                          ('open handover items', 'open_screen'),
                          ('Open hiring roles', 'open_screen'),
                          ('Approve the June 2031 Payai Retail run', 'approve_item'),
                          ('Send the June run back because Lan has no access to the bank file',
                           'send_back_item'),
                          ('duyệt yêu cầu của Quyên', 'approve_item')):
            from odoo.addons.pb_payai_actions.payai import registry
            self.assertEqual((registry.match(text) or ('',))[0], key, text)
        # Never offered to the model, never listed under "What can you do?".
        from odoo.addons.pb_payai_actions.payai import registry
        self.assertNotIn('never_access', {t['name'] for t in registry.tools_schema(
            self.env, self.officer)})
        now, soon = registry.describe(self.env, self.officer)
        self.assertNotIn('never_access', {r['key'] for r in now + soon})

    # ===================== 3b — second pass: what the first table got wrong
    def test_fb11_plain_hand_over_and_change_orders_get_the_never_card(self):
        """FIX-1b second pass: plain "lend / change access" orders the first
        table let through to the model (EN + VI, marks typed)."""
        from odoo.addons.pb_payai_actions.payai import registry
        sentences = (
            'cho Lan mượn quyền', 'cho Lan mượn quyền duyệt', 'đổi quyền của Lan',
            'sửa quyền của Lan', 'xóa quyền của Lan', 'gỡ quyền của Lan',
            'cấp cho Lan quyền quản lý', 'chuyển quyền duyệt cho Lan',
            'thêm Lan vào nhóm quản lý lương', 'mở quyền cho Lan', 'xem quyền của Lan',
            'ĐỔI QUYỀN CỦA LAN', 'để Lan duyệt thay tôi', 'giao việc duyệt cho Lan',
            'đặt Lan làm người dự phòng', 'gỡ Lan khỏi nhóm quyền',
            "give my approvals to Lan while I'm away", 'pass my approvals to Lan',
            'transfer my approvals to Lan', 'let Lan approve on my behalf',
            'handover my approvals to Lan', 'make Lan admin', 'grant admin to Lan',
            'set Lan as my backup', 'give Lan my access', 'add Minh as an approver',
            'delegate the June run to Lan', "approve Lan's request for access",
            'approve the role change request')
        for text in sentences:
            self.assertEqual((registry.match(text) or ('',))[0], 'never_access', text)
        with self._no_provider():
            for text in ('cho Lan mượn quyền', "give my approvals to Lan while I'm away",
                         'make Lan admin', 'thêm Lan vào nhóm quản lý lương'):
                out, _s = self._send(self.officer, text)
                self._assert_never(out, text)

    def test_fb12_ordinary_orders_keep_their_action(self):
        """FIX-1b second pass (regression): Hiring's "role", a trip's
        delegation, a leaver's hand-over, a building pass, a reason after a
        comma and a team called Access are NOT orders about access."""
        from odoo.addons.pb_payai_actions.payai import registry
        for text, key in (
                ('approve the Sales Manager role', 'approve_item'),
                ('send back the Sales Manager role request', 'send_back_item'),
                ('reject the Payroll Officer role', 'reject_item'),
                ('duyệt vai trò Trưởng phòng kinh doanh', 'approve_item'),
                ('open a role', 'open_screen'),
                ('Open a role and ask for its request', 'open_screen'),
                ('show me how to open a role', None),
                ('approve the trip for the Japan delegation', 'approve_item'),
                ('approve the exit hand-over for Lan', 'approve_item'),
                ('approve the hand-over of the laptop', 'approve_item'),
                ('approve the handover checklist for Lan', 'approve_item'),
                ("send back Lan's exit handover", 'send_back_item'),
                ('approve the access card request', 'approve_item'),
                ('send back the June run, the roles are wrong', 'send_back_item'),
                ('reject the overtime request, Lan has no rights to overtime', 'reject_item'),
                ('show the run for the access team', 'run_status'),
                ('chuyển phiếu lương cho Quyền', 'send_payslips'),
                ('xóa phiếu lương của Quyền', 'never_destructive'),
                ('duyệt yêu cầu của Quyên', 'approve_item'),
                ('thêm Lan vào nhóm ca đêm', None)):
            got = registry.match(text)
            self.assertEqual(got and got[0], key, text)
        # Not a hand-over: a singular approval, a run let go ahead.
        for text in ('give my approval to the June run', 'let the June run go ahead',
                     'let me approve the June run', 'set the June run as draft'):
            self.assertNotEqual((registry.match(text) or ('',))[0], 'never_access', text)
        # A capital "Quyên" is a name — the order stands on its other words.
        self.assertEqual(registry.match('đổi vai trò của Quyên')[0], 'never_access')
        # The question path still answers "how do I …".
        self.assertIsNone(registry.match("How do I give someone my access while I'm away?"))

    def test_fb13_a_screen_named_open_a_role_is_hiring(self):
        """FIX-1b second pass (regression): the model's open_screen call for
        the Hiring lesson "Open a role and ask for its request" is a door,
        not the access refusal; a screen named in access words still is."""
        self.assertFalse(gate.names_access('Open a role'))
        self.assertFalse(gate.names_access('a role'))
        self.assertFalse(gate.names_access('Open a role and ask for its request'))
        self.assertFalse(gate.names_access('exit hand-over'))
        self.assertFalse(gate.names_access('access card'))
        for name in ('Roles', 'Access and delegations', 'Hand-overs', "Lan's role",
                     'People & backups', 'phân quyền'):
            self.assertTrue(gate.names_access(name), name)
        hiring = {'id': 'learn.scenario.sc_hiring', 'label': 'Open a role and ask for its request',
                  'sublabel': 'Walkthrough · how to', 'groups': [], 'kind': 'learn',
                  'target': {'xmlid': 'pb_learn.action_learn_hub', 'lens': 'lessons',
                             'focus': 'scenario:sc_hiring:watch'}}
        sink = []
        fake = p1._FakeProvider(sink, tool={'tool_name': 'open_screen',
                                            'arguments': {'door': 'Open a role'}})
        session = self._session_with(self.officer, ACCESS_ROWS + OPEN_ROWS + [hiring])
        with self._provider(fake):
            out, _s = self._send(self.officer, 'I want the hiring walkthrough number 2031',
                                 session)
        self.assertTrue(sink, 'the tools call was not reached')
        blob = json.dumps(out, ensure_ascii=False)
        self.assertNotIn(NEVER_TEXT, blob)
        self.assertNotEqual(out['card'].get('tier'), 'never', out)
        if out['card'].get('task_id'):
            task = self.env['payai.task'].sudo().browse(out['card']['task_id'])
            self.assertEqual(task.action_key, 'open_screen', out)
        self._assert_no_access_door(out['card'])

    def test_fb14_the_access_lesson_focus_is_denied(self):
        hub = {'xmlid': 'pb_learn.action_learn_hub', 'lens': 'lessons'}
        self.assertTrue(gate.target_denied(dict(hub, focus='lesson:L23')))
        self.assertFalse(gate.target_denied(dict(hub, focus='lesson:L1')))
        self.assertTrue(gate.door_denied({'id': 'x', 'target': dict(hub, focus='lesson:L23')}))
        card = {'actions': [{'id': 'learn', 'lesson': 'L23'},
                            {'id': 'learn', 'scenario': 'sc_payslips'},
                            {'type': 'open_lesson', 'lesson': 'L23'},
                            {'hub': dict(hub, focus='lesson:L23')}]}
        gate.scrub_card(card)
        self.assertEqual(card['actions'], [{'id': 'learn', 'scenario': 'sc_payslips'}])

    def test_fb15_the_answer_path_never_offers_the_access_lesson(self):
        """FIX-1b second pass: "How do I give someone my access while I'm
        away?" is a question — PayAI's answer path runs, and its "Show me"
        button must not open the Access walkthrough (it walks the live
        Access home) or the Access lesson, whoever offered it: the model,
        or the Learn helper's own resolver."""
        from odoo.addons.pb_payai_actions.payai import registry
        engine = self.env['payroll.ai.engine'].with_user(self.officer)
        # The rule sits where the answer leaves process_message, not in the
        # whitelist envelope (pb_payroll_ai_insights owns that, and its own
        # tests assert every whitelisted key survives it).
        drop = engine._drop_access_learn
        self.assertIsNone(drop({'action': {
            'type': 'open_walkthrough', 'walkthrough': 'sc_access', 'label': 'Show me'}})['action'])
        self.assertIsNone(drop({'action': {'type': 'open_lesson', 'lesson': 'L23'}})['action'])
        self.assertEqual(drop({'action': {
            'type': 'open_walkthrough', 'walkthrough': 'sc_payrun'}})['action']['walkthrough'],
            'sc_payrun')
        self.assertEqual(drop({'action': {'type': 'open_lesson', 'lesson': 'L1'}})['action']['lesson'],
                         'L1')
        Engine = self.registry['payroll.ai.engine']

        def access_handoff(self_, message):
            return (self_._sanitize_action({'type': 'open_walkthrough',
                                            'walkthrough': 'sc_access', 'label': 'Show me'})
                    or self_._sanitize_action({'type': 'open_lesson', 'lesson': 'L23',
                                               'label': 'Show me'}))
        questions = ("How do I give someone my access while I'm away?",
                     'How can I hand my access to Lan while I am on leave?',
                     'How do I lend my approvals to a colleague?',
                     'How do I give Minh my access during my holiday?')
        offers = ({'type': 'open_walkthrough', 'walkthrough': 'sc_access'},
                  {'type': 'open_lesson', 'lesson': 'L23'})
        i = 0
        for intent in ('onboarding', 'payroll_knowledge', 'general'):
            for offer in offers:
                text = questions[i % len(questions)] + ' (%d)' % (2031 + i)
                i += 1
                self.assertIsNone(registry.match(text), text)
                fake = p1._FakeProvider([], intent=intent, answer=json.dumps(
                    {'response': 'Settings has a screen for that.', 'action': offer}))
                # The real resolver first (whatever this database's Learn
                # knows), then one forced to name the Access lesson.
                for forced in (False, True):
                    with self._provider(fake):
                        if forced:
                            with patch.object(Engine, '_content_handoff', access_handoff):
                                out, _s = self._send(self.officer, text)
                        else:
                            out, _s = self._send(self.officer, text)
                    self.assertFalse(out.get('action'), (intent, offer, forced, out))
                    self.assertNotIn('sc_access', json.dumps(out))
                    self.assertNotIn('"L23"', json.dumps(out))
        # Not a blanket filter: another lesson's button still comes through.
        fake = p1._FakeProvider([], intent='onboarding', answer=json.dumps(
            {'response': 'The Runs board.', 'action': {'type': 'open_walkthrough',
                                                       'walkthrough': 'sc_payrun'}}))
        with self._provider(fake):
            out, _s = self._send(self.officer, 'How do I run payroll for June 2031?')
        self.assertEqual((out.get('action') or {}).get('walkthrough'), 'sc_payrun', out)

    # ================================== 4 — PayAI never writes access
    def _payai_sources(self):
        from odoo.modules.module import get_module_path
        root = get_module_path('pb_payai_actions')
        for folder in ('payai', 'models'):
            path = os.path.join(root, folder)
            for name in sorted(os.listdir(path)):
                if name.endswith('.py'):
                    yield os.path.join(folder, name), os.path.join(path, name)

    def test_fb08_static_no_action_writes_an_access_model(self):
        """Point 4, statically: no PayAI file calls an Access write method,
        and no model name of the Access home appears in PayAI's code outside
        the deny-list itself (gate.py) — except `res.users` as the comodel of
        the task's own "Asked by" field."""
        offenders = []
        for rel, path in self._payai_sources():
            with open(path, encoding='utf-8') as fh:
                tree = ast.parse(fh.read(), path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                        and node.func.attr in ACCESS_WRITE_METHODS:
                    offenders.append('%s:%s calls %s()' % (rel, node.lineno, node.func.attr))
                if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                        and node.value in gate.ACCESS_MODELS and rel != 'payai/gate.py':
                    if rel == 'models/payai_task.py' and node.value == 'res.users':
                        continue
                    offenders.append('%s:%s names %s' % (rel, node.lineno, node.value))
        self.assertEqual(offenders, [])

    def test_fb09_dynamic_no_access_model_is_written(self):
        """Point 4, while PayAI runs: every Access model's create / write /
        unlink is watched through a battery of orders (opening, changing,
        lending, deciding access) — none is called."""
        calls = []
        patches = []
        for model in WATCHED_MODELS:
            if model not in self.env:
                continue
            cls = self.registry[model]
            for meth in ('create', 'write', 'unlink'):
                real = getattr(cls, meth)

                def spy(self_, *a, _real=real, _m=model, _n=meth, **k):
                    calls.append((_m, _n))
                    return _real(self_, *a, **k)
                patches.append(patch.object(cls, meth, spy))
        session = self._session_with(self.officer, ACCESS_ROWS + OPEN_ROWS)
        for p in patches:
            p.start()
        try:
            with self._no_provider():
                for text in ('open access and delegations', "change Lan's role",
                             'Give Lan the payroll manager role', 'lend my role to Lan',
                             'mở phân quyền', 'Approve Lan\'s access request',
                             'Open the Runs board', 'What can you do?'):
                    self._send(self.officer, text, session)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(calls, [])

    # ============================ 5 — reading the rules stays (the gate)
    def test_fb10_reading_the_menu_rules_still_gates(self):
        status = ACTIONS['run_status']
        self.assertEqual(gate.allowed(self.env, self.officer, status), (True, ''))
        item = gate.screen_item(self.env, status)
        self.assertTrue(item)
        Item = self.registry['pb.sidebar.item']
        real = Item.visibility_for

        def hidden(self_, user):
            out = real(self_, user)
            out['items'][item.id] = 'hidden'
            return out
        with patch.object(Item, 'visibility_for', hidden):
            self.assertEqual(gate.allowed(self.env, self.officer, status),
                             (False, 'screen_off'))


    # ======================= 3c — third pass: everyday wordings, look-alikes
    def test_fb16_everyday_role_and_delegation_orders_get_the_never_card(self):
        """FIX-1b third pass: plain role / delegation / screen-lock orders
        (EN + VI, typos, Title Case) the second table sent to the model or
        to open_screen."""
        from odoo.addons.pb_payai_actions.payai import registry
        sentences = (
            'make Lan a payroll manager', 'make Lan payroll manager',
            'promote Lan to payroll manager', 'add Lan to the payroll managers',
            'remove Minh from payroll managers', 'Lan should be a payroll manager',
            'create a delegation for Lan', 'start a hand-over to Lan', 'new delegation for Lan',
            'route my approvals to Lan', 'redirect my approvals to Lan',
            'send my approvals to Lan', 'reroute approvals to Lan', 'take back my approvals',
            'I want Lan to approve on my behalf', 'Lan will approve instead of me',
            "I'm away next week, Lan covers my approvals", 'cover for me Lan',
            'Lan needs access to payroll', 'Lan needs admin rights',
            'change who approves payroll', 'replace the approver with Lan',
            'lock the Payslips screen for Lan', 'hide Payslips from Lan',
            'show Lan the payslips screen', 'let Lan see payslips',
            'open users', 'open the approval matrix people tab', 'open user roles',
            'give lan acess', "change Lan's rol", 'open acess', 'opne access and delegations',
            'open rolse', 'open permision',
            'approve the request to make Lan payroll manager',
            'cho Lan quyền duyệt', 'cho Lan làm quản lý lương', 'nhờ Lan duyệt thay',
            'Lan duyệt thay tôi tuần sau', 'Minh sẽ duyệt thay tôi', 'đổi menu bên trái',
            'khóa màn hình phiếu lương cho Lan', 'ẩn màn hình bảng lương với Lan',
            'mở người dùng', 'mở menu bên trái', 'mở nhóm người dùng', 'mở bàn giao',
            'Đổi Quyền Của Lan', 'Cấp Quyền Cho Lan', 'nâng Lan lên quản trị',
            # Choosing who approves a run is the approval hand-over's business
            # ("change who approves payroll"), not a pay change.
            'chọn Lan làm người duyệt bảng lương tháng 6')
        for text in sentences:
            self.assertEqual((registry.match(text) or ('',))[0], 'never_access', text)
        with self._no_provider():
            for text in ('make Lan a payroll manager', 'open users', 'mở người dùng',
                         'Đổi Quyền Của Lan', 'redirect my approvals to Lan'):
                out, _s = self._send(self.officer, text)
                self._assert_never(out, text)

    def test_fb17_payroll_orders_named_admin_role_access_keep_their_action(self):
        """FIX-1b third pass (regression): a pay item or a team named
        "admin", "role" or "access", a right in law, leave entitlement,
        benefits ("quyền lợi"), a volume ("quyển"), a job's role and a
        person let see their own payslip are NOT orders about access."""
        from odoo.addons.pb_payai_actions.payai import registry
        for text, key in (
                ('Give Lan an admin allowance of 500,000 from July', 'update_pay_data'),
                ('Set the admin allowance of Lan to 600,000', 'update_pay_data'),
                ('Give Lan a role allowance of 500,000 from July', 'update_pay_data'),
                ('Set the role allowance of An Nguyen to 600,000', 'update_pay_data'),
                ('Give Lan an access allowance of 500,000', 'update_pay_data'),
                ('Give the admin team an allowance of 500,000', 'update_pay_data'),
                ('Cho Lan phụ cấp vai trò 500.000 từ tháng 7', 'update_pay_data'),
                ("remove the admin fee from Lan's payslip", 'never_destructive'),
                ('show the role allowance', 'open_screen'),
                ("show me Lan's role in the June run", 'run_status'),
                ('open the Sales Manager role', 'open_screen'),
                ('show the Sales Manager role', 'open_screen'),
                ('mở quyền lợi nhân viên', 'open_screen'),
                ('mở vai trò công việc', 'open_screen'),
                ('xóa phiếu lương của Quyền', 'never_destructive'),
                ('Xóa Phiếu Lương Của Quyền', 'never_destructive')):
            got = registry.match(text)
            self.assertEqual(got and got[0], key, text)
        for text in (
                'add the admin fee to the June run', 'set the admin fee to 50k',
                'give the admin team a bonus', "change Lan's department to admin",
                'move Lan to admin', 'let Lan see her payslip',
                'let employees see their payslips', 'let Lan cover the night shift',
                'let Minh cover for Lan', 'let Lan stand in for Minh on the night shift',
                'give Lan permission to work overtime', "show Lan's leave rights",
                'show my role', 'show open roles', 'make Lan the owner of the June run',
                'set Lan as the owner of the run', 'make Lan team owner',
                'promote Lan to senior accountant', 'Lan needs a payslip for June',
                'Lan wants to see her payslip', 'lock the June run', 'unlock the June run',
                'hide zero lines from the payslip', 'take back the June bonus',
                'send my payslip to Lan', 'I want Lan to get a bonus',
                'xem quyền lợi bảo hiểm của Lan', 'kiểm tra quyền lợi của Lan',
                'thêm quyền lợi cho Lan', 'xem quyền nghỉ phép năm',
                'bàn giao quyển sổ lương cho Lan', 'xem vai trò của Lan trong dự án',
                'đổi vai trò trong đợt tuyển', 'ẩn dòng bằng 0 khỏi phiếu lương',
                'khóa bảng lương tháng 6', 'Chuyển Phiếu Lương Cho Quyền'):
            self.assertNotEqual((registry.match(text) or ('',))[0], 'never_access', text)
        # The model's screen name: a look-alike is a door, the access words
        # still refuse.
        for name in ('the role allowance', 'the Sales Manager role', 'admin fee',
                     'my leave rights', 'quyền lợi nhân viên', 'vai trò công việc'):
            self.assertFalse(gate.names_access(name), name)
        for name in ("Lan's role", 'Roles', 'acess', 'approval matrix people',
                     'menu bên trái', 'nhóm người dùng'):
            self.assertTrue(gate.names_access(name), name)

    def test_fb18_a_look_alike_is_a_pay_change_plan_not_the_refusal(self):
        """FIX-1b third pass: end to end, "admin allowance" is planned as a
        pay change (or asked about), never answered with the access card."""
        with self._no_provider():
            out, _s = self._send(self.officer, 'Give Lan an admin allowance of 500,000 from July')
        blob = json.dumps(out, ensure_ascii=False)
        self.assertNotIn(NEVER_TEXT, blob)
        if out['card'].get('task_id'):
            task = self.env['payai.task'].sudo().browse(out['card']['task_id'])
            self.assertEqual(task.action_key, 'update_pay_data', out)

    # ===================== 3d — fourth pass: what the third table let through
    def test_fb19_lens_names_groups_able_to_see_as_and_role_questions(self):
        """FIX-1b fourth pass: the Access home's own lens names ("Screens",
        "user management", the people passport), a group of the app's roles,
        "needs to be able to approve", a stand-in after a reason, "see it
        as …" and "what roles does … have" get the never card — and the
        model's open_screen call naming one of those lenses is refused."""
        from odoo.addons.pb_payai_actions.payai import registry
        sentences = (
            'put Lan in the payroll managers group', 'put Lan in the admin group',
            'move Minh into the approvers group',
            'Lan needs to be able to approve payroll',
            'Lan should be allowed to approve the June run',
            'Minh needs to be able to see the Runs screen',
            'I need Lan to be able to sign off payroll',
            "I'm going on leave, Lan will approve for me",
            "I'm away next week so Lan will approve for me", 'Lan will approve for me',
            "Lan will sign off while I'm away",
            'see it as Lan', 'view as Lan', 'View as Lan Nguyen', 'see the app as Minh',
            'log in as Lan', 'impersonate Lan',
            'what roles does Lan have', 'which permissions does Lan have',
            'What roles does Lan have?', 'what access does Lan have',
            'what screens can Lan open', 'what can Lan see',
            'open the Screens lens', 'open the screens tab', 'open user management',
            'open the people passport for Lan',
            'approve the request from Lan for the payroll manager role',
            "reject Lan's request to become a payroll officer",
            'approve the request from Lan for admin rights',
            # FIX-1b fifth pass: the same orders in Vietnamese ("Xem như" is
            # the Access home's own "See it as").
            'thêm Lan vào nhóm quản lý lương', 'thêm Lan vào nhóm người duyệt',
            'cho Lan quyền duyệt', 'nhờ Lan duyệt thay tôi', 'ủy quyền cho Lan',
            'xem như Lan', 'xem như người khác', 'xem với tư cách Lan', 'đăng nhập như Lan')
        for text in sentences:
            self.assertEqual((registry.match(text) or ('',))[0], 'never_access', text)
        # The model's screen name: the Access home's lenses, whole.
        for name in ('Screens lens', 'Screens', 'user management', 'Users', 'the Users list',
                     'Navigation', 'Passports', 'people passport', 'Who can open each screen',
                     'See it as somebody else'):
            self.assertTrue(gate.names_access(name), name)
        with self._no_provider():
            for text in ('put Lan in the payroll managers group', 'view as Lan',
                         'open the Screens lens', 'what roles does Lan have'):
                out, _s = self._send(self.officer, text)
                self._assert_never(out, text)
        # The model's open_screen call naming a lens (clone of fb03).
        for i, door in enumerate(('Screens lens', 'user management', 'Users', 'Navigation')):
            sink = []
            fake = p1._FakeProvider(sink, tool={'tool_name': 'open_screen',
                                                'arguments': {'door': door}})
            session = self._session_with(self.officer, ACCESS_ROWS + OPEN_ROWS)
            with self._provider(fake):
                out, _s = self._send(self.officer, 'I am hunting for a page number %d'
                                     % (2041 + i), session)
            self.assertTrue(sink, 'the tools call was not reached')
            self._assert_never(out, door)

    def test_fb20_fourth_pass_look_alikes_keep_their_action(self):
        """FIX-1b fourth pass (regression): a note OF the approver, a team or
        a run somebody is put in, a format to view something as, an
        employee's passport (an identity document), a person who must be
        able to work, the People hub and "What can you do?" are not orders
        about access."""
        from odoo.addons.pb_payai_actions.payai import registry
        self.assertIsNone(registry.match('change the approver note'))
        for text in (
                'change the approver note', 'remove the approver comment',
                'change the approver name on the report', 'replace the backup file',
                'put Lan on the night shift', 'put Lan in the June run',
                'put Lan in the sales team', 'put Lan in the payroll team', 'move Lan to admin',
                'get Lan into the Retail scheme', 'Lan needs to be paid by Friday',
                'Lan needs to be able to see her payslip', 'Lan needs to be able to work overtime',
                'Lan will send the payslips for me', 'Lan will be paid for me',
                "I'm going on leave, remind me to approve the June run",
                'view as list', 'see it as a percentage', 'show it as PDF',
                'view the June run as a table', 'show me the payslips as cards',
                'what allowances does Lan have', 'which payslips does Lan have',
                'what can you do', 'What can you do?', 'what can I do', 'what roles are open',
                "show Lan's passport", 'open people', 'open the people screen',
                'open the payslips screen', 'log in to the bank',
                # FIX-1b fifth pass: "consider it done", a format, a team.
                'xem như đã duyệt', 'xem như xong', 'xem như bảng',
                'đăng nhập như thường lệ', 'thêm Lan vào nhóm kế toán'):
            self.assertNotEqual((registry.match(text) or ('',))[0], 'never_access', text)
        for text, key in (('replace the approver with Lan', 'never_access'),
                          ('change my backup to Lan', 'never_access'),
                          ('change the approver', 'never_access'),
                          ('reject the Payroll Officer role', 'reject_item'),
                          ('approve the request from Lan for overtime', 'approve_item'),
                          ('approve the request from Lan for the June bonus', 'approve_item')):
            got = registry.match(text)
            self.assertEqual(got and got[0], key, text)
        for name in ('People', 'Payslips', 'the payslips screen', 'Employees', 'passport',
                     'Approval Matrix', 'Pay Runs', 'Settings', 'user guide'):
            self.assertFalse(gate.names_access(name), name)

    def test_fb21_sixth_pass_see_as_needs_a_person(self):
        """FIX-1b sixth pass (regression): "see it as …" / "xem như …" stand
        only on a person — the words for somebody else, or a name with its
        capital. A pay item, a format, a period or a state after "as" /
        "như" keeps what it did before FIX-1b (a run's status, a screen, or
        a model reply); so do "change the backup to Monday", a question
        about rights under a contract, a role name that is part of a bonus
        or a department, "Lan, approve this for me" and a team named "nhóm
        quản lý"."""
        from odoo.addons.pb_payai_actions.payai import registry
        for text, key in (
                ('xem như lương tháng 6', 'run_status'), ('xem như tiền lương', 'run_status'),
                ('xem như lương thực nhận', 'run_status'),
                ('mở như phiếu lương', 'open_screen'), ('mở như hợp đồng', 'open_screen'),
                ('open it as spreadsheet', 'open_screen'), ('open this as Word', 'open_screen'),
                ('open as payslips', 'open_screen'), ('open it as June payslips', 'open_screen')):
            got = registry.match(text)
            self.assertEqual(got and got[0], key, text)
        for text in (
                'xem như hoàn thành', 'xem như nghỉ phép', 'xem như tăng ca', 'xem như nhân viên',
                'xem như quản lý', 'xem như Lan đã nghỉ', 'xem như hai ngày',
                'xem nhu hoan thanh', 'xem nhu nghi phep', 'xem nhu tang ca',
                'show it as VND', 'view it as USD', 'show it as net pay', 'see it as net',
                'show this as overtime', 'show everything as summary', 'view as monthly',
                'check it as paid', 'show this as zero', 'view it as cost centre',
                'view as department', 'preview as payslip', 'view as payslips',
                "check this as Lan's payslip", 'show it as one line',
                'change the backup to Monday', 'what rights does Lan have under the contract',
                'what access does Lan have to the building',
                "include Lan in the payroll managers' bonus",
                'put Lan in the HR managers bonus pool', 'put Lan in the HR managers department',
                'Lan, approve this for me',
                'thêm Lan vào nhóm quản lý dự án', 'gỡ Lan khỏi nhóm quản lý dự án',
                'thêm khoản thưởng vào nhóm quản lý', 'thêm phụ cấp cho Lan vào nhóm quản lý'):
            self.assertNotEqual((registry.match(text) or ('',))[0], 'never_access', text)
        # The person-shaped ones are still the never card.
        for text in ('see it as Lan', 'view as Lan', 'View as Lan Nguyen', 'see the app as Minh',
                     'see it as someone else', 'view as another user', 'change my backup to Lan',
                     'what access does Lan have in payroll', 'put Lan in the payroll managers',
                     'xem như Lan', 'xem như người khác', 'xem như người dùng khác',
                     'thêm Lan vào nhóm quản lý lương', 'thêm Lan vào nhóm quản trị'):
            self.assertEqual((registry.match(text) or ('',))[0], 'never_access', text)

    def test_fb22_seventh_pass_labels_with_capitals_and_orders_before_a_stand_in(self):
        """FIX-1b seventh pass (regression): a screen label copied with its
        capitals after "as" / "như" (a state, a pay item, a period, a way
        to lay a screen out, a country) is not a person; "open / check /
        show … as …" is a screen, a status or a format; an order before
        "…, Lan will sign off for me" stays the order; a joining word ("so",
        "and", "then") is not a person; "sign the contract for me" is a
        document. Each keeps what it did before FIX-1b."""
        from odoo.addons.pb_payai_actions.payai import registry
        for text, key in (
                ('open it as Approved', 'open_screen'), ('open as Net Pay', 'open_screen'),
                ('open it as Net Pay', 'open_screen'), ('open this as Summary', 'open_screen'),
                ('open as Summary', 'open_screen'),
                ('xem như Lương Gộp', 'run_status'), ('xem như Lương Cơ Bản', 'run_status'),
                ('xem như Đợt Lương', 'run_status'), ('mở như Phiếu Lương', 'open_screen'),
                ('approve the June run so Lan can sign off for me', 'approve_item'),
                ('approve the June run, Lan will sign off for me', 'approve_item'),
                ('approve the June run and Lan will sign off for me', 'approve_item'),
                ('approve the June run, then Lan signs off for me', 'approve_item'),
                ('approve the June run and then Minh will sign off for us', 'approve_item'),
                ('reject the June run so Lan can approve for me', 'reject_item'),
                ('send back the June run so Lan can approve for me', 'send_back_item'),
                ('show the June run so Lan can approve for me', 'run_status'),
                ("approve Lan's payslip so she can sign for me", 'approve_item'),
                ('approve the June run, Lan covers my approvals', 'approve_item'),
                ('approve the June run for me', 'approve_item')):
            got = registry.match(text)
            self.assertEqual(got and got[0], key, text)
        for text in (
                'show it as Approved', 'check it as Approved', 'view as Paid',
                'see it as Confirmed', 'view it as Posted', 'view as Basic', 'show it as Bonus',
                'view as Overtime', 'show it as Net', 'view as Gross', 'view as Gross Pay',
                'view as Net Pay', 'see it as Gross Pay', 'view as Monthly', 'view as Weekly',
                'view as Quarterly', 'view as Yearly', 'view as Annual', 'view as Summary',
                'view as Detailed', 'view as Compact', 'show as Summary', 'check as Summary',
                'view as Company', 'view it as Vietnam', 'see it as Malaysia', 'view as Thailand',
                'view as Singapore', 'view as Indonesia', 'see it as Hanoi', 'view as Retail',
                'xem như Phiếu Lương', 'xem như Thưởng', 'xem như Phụ Cấp', 'xem như Thuế',
                'xem như Bảo Hiểm', 'xem như Nhân Viên', 'xem như Hợp Đồng', 'xem như Chi Phí',
                'xem như Thực Nhận', 'xem như Tổng', 'xem như Nháp', 'xem như Việt Nam',
                'xem như Hà Nội', 'xem với tư cách Nhân Viên',
                'Lan will sign the contract for me', 'Minh will sign the payslips for me',
                'so approve the June run for me', 'ok so approve the June run for me',
                'and approve the June run for me', 'then approve the June run for me',
                "I'm away, so approve the June run for me", "it's late, so approve it for me"):
            self.assertNotEqual((registry.match(text) or ('',))[0], 'never_access', text)
        # Still the never card: a person (also a given name that is a word —
        # Long, Loan, Chi, Nam), the app seen as somebody, somebody else, and
        # a stand-in after the asker's own news.
        for text in ('see it as Lan', 'view as Lan', 'View as Lan Nguyen', 'see the app as Minh',
                     'view as Long', 'view as Loan', 'open the app as Minh',
                     'show it as someone else', 'open it as another user',
                     'xem như Lan', 'xem như người khác', 'mở như người khác',
                     'đăng nhập như Lan', 'xem với tư cách Lan', 'xem như Chi', 'xem như Nam',
                     'xem như Lan Anh',
                     "I'm going on leave, Lan will approve for me",
                     "I'm away next week so Lan will approve for me",
                     "while I'm away, Lan will approve for me",
                     "I'll be on leave so Minh will sign off for me",
                     "I'm away next week, Lan covers my approvals",
                     'so Lan will approve for me', 'Lan will sign for me',
                     'Lan will sign off for me', 'Lan will approve for me'):
            self.assertEqual((registry.match(text) or ('',))[0], 'never_access', text)


@tagged('post_install', '-at_install', 'payai')
class TestPayaiFixAccessRed(p3.TestPayaiP3Red):
    """P3:sec-4 on real Access data: the Approvals inbox is the Approvals tab
    of Home (`pb_home_hub.item_home` — the retired `pb_sidebar.item_approvals`
    is inactive and opened the payroll cockpit). Whatever the Access home
    puts on that entry or its block — a role, a permission, a padlock —
    refuses Red, and the inbox is never asked to decide."""

    def _spy_decide(self):
        Inbox = self.registry['pb.approval.inbox']
        calls = []
        real = Inbox.decide

        def spy(self_, *a, **k):
            calls.append(a)
            return real(self_, *a, **k)
        return patch.object(Inbox, 'decide', spy), calls

    def _red_sentences(self):
        return ('Approve the June 2031 Payai Retail run',
                'Send the June 2031 Payai Retail run back because the overtime is missing',
                'Turn down the June 2031 Payai Retail run because it was paid twice')

    def _assert_refused_screen(self, card, text):
        self.assertEqual(card['kind'], 'refused', (text, card))
        self.assertEqual(self._task(card).error, 'screen_off', text)
        blob = json.dumps(card, ensure_ascii=False)
        self.assertIn('Settings › Access and delegations', blob)
        self.assertNotIn('Open Access and delegations', blob)
        for act in card.get('actions') or []:
            self.assertFalse(gate.action_denied(act), act)

    def _role(self):
        """A role made the way the Access home makes one, and its holder mark
        (what a person who holds — or is lent — the role carries)."""
        stamp = 'fix1b2031'
        group = self.env['res.groups'].sudo().create({'name': 'Payai FIX-1b approvals 2031'})
        ability = self.env['pb.role.ability'].sudo().create({
            'technical_key': 'payai-fix1b-%s' % stamp, 'name': 'Payai FIX-1b decide %s' % stamp,
            'description': 'Made for this test only.', 'area': 'system',
            'group_ids': [(6, 0, group.ids)]})
        role = self.env['pb.role.profile'].sudo().create({
            'name': 'Payai FIX-1b approver %s' % stamp, 'description': 'Made for this test only.',
            'area': 'system', 'ability_ids': [(6, 0, ability.ids)]})
        role._ensure_membership_group()
        return role, role.sudo().membership_group_id

    def test_fs01_home_gated_by_a_role_refuses_red(self):
        if 'role_ids' not in self.env['pb.sidebar.item']._fields:
            self.skipTest('No role lane on the left menu here.')
        self._two_steps()
        run, request = self._submitted()
        action = ACTIONS['approve_item']
        item = gate.screen_item(self.env, action)
        self.assertEqual(item, self.env.ref('pb_home_hub.item_home'))
        role, mark = self._role()
        item.sudo().write({'role_ids': [(6, 0, role.ids)]})
        self.env.invalidate_all()
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'hidden')
        spy, calls = self._spy_decide()
        with spy:
            for text in self._red_sentences():
                card, _s = self._send(self.approver, text)
                self._assert_refused_screen(card, text)
        self.assertFalse(calls)
        self.assertFalse(self._decisions(request))
        # The role is lent to them (a lent role arrives as the role's own
        # holder mark): the same rule opens it again.
        self.approver.sudo().write({'group_ids': [(4, mark.id)]})
        self.env.invalidate_all()
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'on')

    def test_fs02_a_locked_block_of_the_menu_refuses_red(self):
        self._two_steps()
        run, request = self._submitted()
        action = ACTIONS['reject_item']
        item = gate.screen_item(self.env, action)
        item.sudo().section_id.write({'restricted': True})
        self.env.invalidate_all()
        self.assertEqual(gate.screen_state(self.env, self.approver, action), 'locked')
        spy, calls = self._spy_decide()
        with spy:
            for text in self._red_sentences():
                card, _s = self._send(self.approver, text)
                self._assert_refused_screen(card, text)
        self.assertFalse(calls)
        self.assertFalse(self._decisions(request))

    def test_fs03_a_permission_on_home_refuses_red_and_remind(self):
        """The entry's own permission (test_12 covers Do it); here Remind on
        a not-yours card is refused too, nothing sent."""
        self._two_steps()
        run, request = self._submitted()
        card, session = self._plan_approve(self.lan)
        self.assertEqual(card['title'], 'This is not waiting for you', card)
        self._lock_home(gate.screen_item(self.env, ACTIONS['approve_item']))
        before = self.env['biz.approval.outbox'].sudo().search_count(
            [('request_id', '=', request.id), ('kind', '=', 'reminder')])
        chip = card['chips'][0]
        out = self._send(self.lan, chip['label'], session, resolve={
            'task_id': card['task_id'], 'slot': card['chip_slot'], 'value': chip['value'],
            'action': card['chip_action']})[0]
        self.assertEqual(out['kind'], 'refused', out)
        self.assertNotIn('Open Access and delegations', json.dumps(out))
        self.assertEqual(self.env['biz.approval.outbox'].sudo().search_count(
            [('request_id', '=', request.id), ('kind', '=', 'reminder')]), before)

    def test_fs04_an_access_request_is_never_decided_or_chased(self):
        """Approving an access request gives a role: never through PayAI —
        not offered, not planned, not decided at Do it, nobody reminded."""
        self._two_steps()
        run, request = self._submitted()
        # What the request is about decides it (read-only checks).
        self.assertFalse(gate.access_request(self.env, request))
        self.assertTrue(gate.access_request(self.env, request, 'roles'))
        # The request's model, set the way an access request carries it (in
        # SQL: the engine guards its own columns), then put back.
        self.env.flush_all()
        own = request.res_model
        self.env.cr.execute("UPDATE biz_approval_request SET res_model = %s WHERE id = %s",
                            ('pb.access.request', request.id))
        request.invalidate_recordset()
        self.assertTrue(gate.access_request(self.env, request))
        self.env.cr.execute("UPDATE biz_approval_request SET res_model = %s WHERE id = %s",
                            (own, request.id))
        request.invalidate_recordset()
        self.assertFalse(gate.access_request(self.env, request))
        # A plan made before, then the request is one about access: refused
        # at Do it, never decided.
        card, _s = self._plan_approve()
        self.assertEqual(card['kind'], 'plan', card)
        real = gate.access_request

        def about_access(env, req, process_key=None):
            return req.id == request.id or real(env, req, process_key)
        spy, calls = self._spy_decide()
        with patch.object(gate, 'access_request', about_access), spy:
            out = self._confirm(self.approver, card, word='APPROVE')
            self.assertNotEqual(out.get('state'), 'done', out)
            self.assertIn('does not decide or chase requests about access',
                          json.dumps(out, ensure_ascii=False))
            # Not offered: the sentence finds nothing PayAI may decide.
            for text in self._red_sentences():
                card2, _s = self._send(self.approver, text)
                self.assertNotEqual(card2['kind'], 'plan', (text, card2))
                self.assertNotEqual(card2.get('state'), 'planned', card2)
            # The plan itself, asked directly on the id.
            ctx = runner.Ctx(self.env['payroll.ai.engine'].with_user(self.approver), {})
            plan = ACTIONS['approve_item'].plan(ctx, {'item': {'value': request.id,
                                                               'origin': 'said'}})
            self.assertEqual((plan.get('kind'), plan.get('tier')), ('refused', 'never'), plan)
            self.assertEqual(plan['actions'], [])
        self.assertFalse(calls)
        self.assertFalse(self._decisions(request))
        # Remind on someone else's access request: refused, nothing sent.
        card3, session = self._plan_approve(self.lan)
        self.assertEqual(card3['title'], 'This is not waiting for you', card3)
        chip = card3['chips'][0]
        with patch.object(gate, 'access_request', about_access):
            out = self._send(self.lan, chip['label'], session, resolve={
                'task_id': card3['task_id'], 'slot': card3['chip_slot'],
                'value': chip['value'], 'action': card3['chip_action']})[0]
        self.assertEqual(out['kind'], 'refused', out)
        self.assertFalse(self.env['biz.approval.outbox'].sudo().search(
            [('request_id', '=', request.id), ('kind', '=', 'reminder')]))
        self.assertTrue(actions_red.ACCESS_REQUEST_TEXT)


# The P1 / P3 tests run once, in P1 / P3 — not again under these classes (PA56).
for _base, _cls in ((p1.TestPayaiP1, TestPayaiFixAccess), (p3.TestPayaiP3Red, TestPayaiFixAccessRed)):
    for _name in dir(_base):
        if (_name.startswith('test_') and callable(getattr(_base, _name))
                and _name not in _cls.__dict__):
            setattr(_cls, _name, None)
