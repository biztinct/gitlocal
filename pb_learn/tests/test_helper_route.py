# -*- coding: utf-8 -*-
"""ONECHAT OC1 — the helper's router, base layer (handover §4, §11 OC1).

`learn.helper.route(text, screen_key, lang, session_id)` decides where one
sentence goes and NOTHING else: it writes no row, logs no question, calls no
model (only the flag-gated guide composer may, and only where PayAI cannot
answer). This file pins the B column of the routing corpus — pb_learn's own
behaviour, with every PayAI hook switched back to the base one — and the
resolver seams the router reads (`probe`, `answer_for`, `practice_probe`,
the Access boundary, the Explain offer).

The P column runs in pb_payai_actions (`test_onechat_router.py`); both read
`data/onechat_route_corpus.json`, whose values were observed offline by
`pb_payai_actions/tests/offline/test_onechat_oc1.py` and reviewed.
"""
import inspect
import json
import os
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_learn.models import learn_helper as helper_mod
from odoo.addons.pb_learn.models import learn_intent as intent_mod

from .common import load_content

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS = ('_payai_available', '_voice_offered', '_can_act', '_looks_like_question',
         '_command_key', '_go_ahead_words', '_route_payai_state', '_waiting_plan',
         '_route_command', '_capability_route', '_tap_note')


def corpus():
    with open(os.path.join(HERE, 'data', 'onechat_route_corpus.json'), encoding='utf-8') as fh:
        return json.load(fh)['rows']


def summary(r):
    """The comparable shape of one route (the corpus keys)."""
    out = {'route': r['route'], 'why': r['why']}
    if 'ask_only' in r:
        out['ask_only'] = r['ask_only']
    a = r.get('answer')
    if a and a.get('matched'):
        out['answer'] = a.get('key')
    p = r.get('practice')
    if p:
        out['practice'] = ('%s:%s' % (p['key'], p['mode'])) if p.get('key') else (
            'chips:' + ','.join(c['key'] for c in p.get('chips', []))
            + (':sandbox_first' if p.get('sandbox_first') else ''))
    if r.get('note'):
        out['note'] = r['note'].get('key')
    if r.get('extra_chips'):
        out['extra_chips'] = [c.get('key') or c['route'] for c in r['extra_chips']]
    if r.get('choices'):
        out['choices'] = [c['route'] for c in r['choices']]
    if r.get('fallback_key'):
        out['fallback_key'] = r['fallback_key']
    return out


def compare(case, mode, rows, run):
    """Assert every row of one column; collect the failures in one message."""
    failures = []
    for row in rows:
        want = row.get(mode)
        if want is None:
            continue
        got = run(row)
        if got is None:
            continue
        summ = summary(got)
        for key, value in want.items():
            if summ.get(key) != value:
                failures.append('%s %r on %s [%s]: %s=%r, want %r (got %s)' % (
                    mode, row['text'], row['screen'], row.get('state'), key,
                    summ.get(key), value, summ))
        for key in ('ask_only', 'answer', 'practice', 'note', 'extra_chips', 'choices',
                    'fallback_key'):
            if key in summ and key not in want:
                failures.append('%s %r: unexpected %s=%r' % (mode, row['text'], key, summ[key]))
    case.assertFalse(failures, '\n'.join(failures))


class _Recorder:
    """A provider that records composer calls."""

    def __init__(self):
        self.calls = []

    def is_available(self):
        return True

    def generate_text(self, prompt, **kw):
        self.calls.append(prompt)
        return 'NO_ANSWER'

    def _boom(self, *a, **k):
        self.calls.append(a)
        raise AssertionError('the router called a model')

    generate_chat = generate_tools = _boom


@tagged('post_install', '-at_install', 'onechat')
class TestHelperRouteBase(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Helper = self.env['learn.helper']
        self.Intent = self.env['learn.intent']
        HelperCls = type(self.Helper)
        base = helper_mod.LearnHelper
        # Every hook back to pb_learn's own (the "B" database), and the Access
        # reach fixed so the corpus does not depend on who runs it.
        for name in HOOKS:
            p = patch.object(HelperCls, name, base.__dict__[name])
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(type(self.Intent), '_access_visible', lambda self_: True)
        p.start()
        self.addCleanup(p.stop)
        # The composer OFF unless a test turns it on: a clone may carry the
        # tenant's own setting, and a composed answer would be a model call.
        self.env['ir.config_parameter'].sudo().set_param(intent_mod.COMPOSE_FLAG, False)

    # ------------------------------------------------------------- 1.1
    def test_1_1_the_B_column(self):
        compare(self, 'B', corpus(),
                lambda row: self.Helper.route(row['text'], row['screen'], 'en', None))

    # ------------------------------------------------------------- 1.2
    def test_1_2_route_writes_nothing(self):
        models = [m for m in ('payroll.ai.message', 'payai.task', 'learn.question',
                              'learn.event', 'learn.progress') if m in self.env]
        before = {m: self.env[m].sudo().search_count([]) for m in models}
        for row in corpus():
            self.Helper.route(row['text'], row['screen'], 'en', None)
        self.env.flush_all()
        after = {m: self.env[m].sudo().search_count([]) for m in models}
        self.assertEqual(before, after)

    # ------------------------------------------------------------- 1.3 / 1.4
    def test_1_3_no_model_call_with_the_composer_off(self):
        provider = _Recorder()
        with patch.object(type(self.Intent), '_provider', lambda self_: provider):
            for row in corpus():
                self.Helper.route(row['text'], row['screen'], 'en', None)
        self.assertEqual(provider.calls, [])

    def test_1_4_the_composer_never_runs_for_an_order_data_or_practise(self):
        provider = _Recorder()
        self.env['ir.config_parameter'].sudo().set_param(intent_mod.COMPOSE_FLAG, 'True')
        with patch.object(type(self.Intent), '_provider', lambda self_: provider):
            for text in ('run June payroll for Retail', 'please process June salaries',
                         'show me headcount by department', 'let me practise running payroll',
                         'open the runs board', 'thanks'):
                self.Helper.route(text, 'payruns', 'en', None)
            self.assertEqual(provider.calls, [])
            out = self.Helper.route('how do I change the office wifi password', 'payslips',
                                    'en', None)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(out['route'], 'miss')

    # ------------------------------------------------------------- 1.9
    def test_1_9_probe(self):
        hit = self.Intent.probe('what is BHXH', 'payruns')
        self.assertEqual((hit['key'], hit['kind'], hit['scope']), ('bhxh', 'exact', 'any'))
        hit = self.Intent.probe('approve', 'payruns')
        self.assertEqual((hit['kind'], hit['on_screen'], hit['score']), ('reverse', True, 85))
        hit = self.Intent.probe('how do I pay less BHXH', 'payruns')
        self.assertEqual((hit['key'], hit['source']), ('compliance', 'advice'))
        self.assertIsNone(self.Intent.probe('what is the company holiday policy'))
        for intent in self.env['learn.content'].intents():
            for q in ('how do i approve', 'run payroll', 'what is bhxh'):
                kind, base = self.Intent._score_kind(q, intent)
                bonus = intent_mod._ON_SCREEN_BONUS \
                    if base and self.Intent._on_screen(intent, 'payruns') else 0
                self.assertEqual(self.Intent._score(q, intent, 'payruns'), base + bonus)

    # ------------------------------------------------------------- 1.10
    def test_1_10_the_miss_payload_keeps_three_keys(self):
        res = self.Intent.ask('how do I change the office wifi password', 'payslips')
        self.assertEqual(set(res), {'matched', 'capability', 'suggest'})
        out = self.Helper.route('how do I change the office wifi password', 'payslips', 'en')
        self.assertEqual(set(out['answer']), {'matched', 'capability', 'suggest'})

    # ------------------------------------------------------------- 1.11
    def test_1_11_answer_for_is_what_ask_returns(self):
        checked = 0
        for intent in self.env['learn.content'].intents():
            label = intent['label']['en'] if isinstance(intent['label'], dict) else intent['label']
            screen = None if intent['screens'] == '*' else intent['screens'].split(',')[0]
            asked = self.Intent.ask(label, screen)
            if not asked.get('matched') or asked.get('key') != intent['key']:
                continue
            self.assertEqual(self.Intent.answer_for(intent['key'], screen), asked, intent['key'])
            checked += 1
            if checked == 10:
                break
        self.assertEqual(checked, 10)
        self.assertEqual(set(self.Intent.answer_for('no_such_intent', 'payruns')),
                         {'matched', 'capability', 'suggest'})

    # ------------------------------------------------------------- 1.12
    def test_1_12_practice_phrases_and_triggers(self):
        for sc in load_content()['scenarios']:
            if sc.get('retired'):
                continue
            phrases = sc.get('phrases') or []
            vi = [p for p in phrases if helper_mod.has_marks(p)]
            folded = {intent_mod._norm(p) for p in vi}
            plain = [p for p in phrases if not helper_mod.has_marks(p)
                     and intent_mod._norm(p) in folded]
            en = [p for p in phrases if not helper_mod.has_marks(p)
                  and intent_mod._norm(p) not in folded]
            for bag, name in ((en, 'en'), (vi, 'vi'), (plain, 'vi without marks')):
                self.assertGreaterEqual(len(bag), 3, '%s: %s %s' % (sc['key'], name, bag))
        for text in ('try again', 'Làm thủ tục nghỉ việc cho Lan', 'làm thủ công',
                     'nhân viên mới đang tập làm quen',
                     'Practice of paying overtime twice must stop'):
            self.assertEqual(helper_mod.practise_trigger(text), (None, ''), text)
            self.assertNotEqual(self.Helper.route(text, 'payruns', 'en')['why'], 'practise')
        for text in ('show me the tour', 'start the tour', 'open the practice company'):
            self.assertEqual(self.Helper.route(text, 'payruns', 'en')['route'], 'practice', text)
        self.assertEqual(self.Intent.practice_probe('approve overtime')['key'], 'sc_wftime')
        out = self.Helper.route('how do I get off the practice company?', 'payruns', 'en')
        self.assertNotIn('key', out.get('practice') or {})

    # ------------------------------------------------------------- 1.13
    def test_1_13_explain_offers_a_try_where_one_exists(self):
        tree = load_content()
        want = {'payruns': ('sc_welcome', 'sc_payslips'),
                'runpayroll': ('sc_welcome', 'sc_payrun'),
                'formula': ('sc_welcome', 'sc_formula'),
                'approvals': ('sc_welcome', ''), 'dashboard': ('sc_welcome', '')}
        for screen, pair in want.items():
            self.assertEqual(intent_mod.explain_scenario_offer(tree, screen), pair, screen)

    # ------------------------------------------------------------- 1.20
    def test_1_20_route_takes_no_voice(self):
        for fn in (helper_mod.LearnHelper.route, type(self.Helper).route):
            params = list(inspect.signature(fn).parameters)
            self.assertEqual(params, ['self', 'text', 'screen_key', 'lang', 'session_id'])

    # ------------------------------------------------------------- 1.22
    def test_1_22_the_access_boundary(self):
        with patch.object(type(self.Intent), '_access_visible', lambda self_: False):
            out = self.Helper.route('delegate my access', 'payruns', 'en')
            blob = json.dumps(out)
            self.assertEqual(out['route'], 'miss')
            for needle in ('sc_access', 'ac-handover', '"delegate"'):
                self.assertNotIn(needle, blob)
            self.assertFalse(self.Intent.answer_for('delegate', 'payruns')['matched'])
            floor = self.Intent.explain_screen('access')
            self.assertEqual((floor.get('watch'), floor.get('try')), ('', ''))
        out = self.Helper.route('delegate my access', 'payruns', 'en')
        self.assertEqual(out['answer']['watch'], 'sc_access')

    # ------------------------------------------------------- OC1 review
    def test_review_go_ahead_with_punctuation_and_small_talk(self):
        # Base: no plan can wait; "go ahead?" is the cannot-act note, and a
        # yes / thanks with a filler word is small talk — no model call.
        out = self.Helper.route('go ahead?', 'payruns', 'en')
        self.assertEqual((out['why'], out['note']['key']), ('nothing_waiting', 'cannotActHere'))
        for text in ('ok thanks', 'great, thanks', 'yes please', 'ok cảm ơn', 'vâng ạ',
                     'dạ vâng'):
            out = self.Helper.route(text, 'payruns', 'en')
            self.assertEqual((out['route'], out['why']), ('note', 'smalltalk'), text)

    # ------------------------------------------------------------- 1.23
    def test_1_23_small_talk(self):
        provider = _Recorder()
        with patch.object(type(self.Intent), '_provider', lambda self_: provider):
            for text in ('thanks', 'hi', 'ok', 'uh', 'ờ', 'cảm ơn', 'xin chào'):
                out = self.Helper.route(text, 'payruns', 'en')
                self.assertEqual((out['route'], out['why']), ('note', 'smalltalk'), text)
                self.assertTrue(out['note']['en'] and out['note']['vi'])
        self.assertEqual(provider.calls, [])

    # ------------------------------------------------------- chrome
    def test_router_sentences_ship_in_both_languages(self):
        chrome = load_content()['chrome']
        for key in ('nothingWaiting', 'nothingToCancel', 'cannotActHere', 'typeWordOnCard',
                    'tapCancel', 'smalltalk', 'noPayai', 'hereIsHow', 'hereIsHowOrPrepare',
                    'doItForMe', 'askPayData', 'explainHowInstead', 'doItNow', 'howItWorks',
                    'whichMeant', 'doOrHow', 'watchOnlyNote', 'capTitle', 'capExplain',
                    'capAnswer', 'capData', 'capAct', 'capPractise', 'capVoice'):
            pair = chrome.get(key)
            self.assertTrue(pair and pair['en'] and pair['vi'], key)
            self.assertNotIn('odoo', (pair['en'] + pair['vi']).lower(), key)


@tagged('post_install', '-at_install', 'onechat')
class TestAccessBoundaryRealUsers(TransactionCase):
    """1.22 with the REAL predicate (OC1 review blocker, ledger OC30): no
    patch on `_access_visible`. The Settings cog is restricted, so somebody
    outside the access team sees it LOCKED on their own left menu — and must
    not be offered the Access walkthrough, a Show me into it or the
    `delegate` answer. Somebody the cog opens for is offered all three."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.item = cls.env.ref(intent_mod.ACCESS_SIDEBAR_KEY, raise_if_not_found=False)
        team = cls.env.ref('biz_access.group_access_manager', raise_if_not_found=False) \
            or cls.env.ref('base.group_system')
        base = cls.env.ref('base.group_user').id
        if cls.item:
            # The live shape (pb_vendor_access): the access team only, shown
            # locked to everybody else.
            cls.item.sudo().write({'groups_id': [(6, 0, [team.id])], 'restricted': True})
            # A demo database may padlock whole blocks of the menu; this test
            # is about the entry, so its block is open.
            cls.item.sudo().section_id.write({'restricted': False})
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.outsider = Users.create({'name': 'OC Outsider', 'login': 'oc_outsider',
                                     'group_ids': [(6, 0, [base])]})
        cls.team_member = Users.create({'name': 'OC Access team', 'login': 'oc_access_team',
                                        'group_ids': [(6, 0, [base, team.id])]})

    def setUp(self):
        super().setUp()
        if not self.item:
            self.skipTest('no Settings entry on this database')
        HelperCls = type(self.env['learn.helper'])
        for name in HOOKS:
            p = patch.object(HelperCls, name, helper_mod.LearnHelper.__dict__[name])
            p.start()
            self.addCleanup(p.stop)
        self.env['ir.config_parameter'].sudo().set_param(intent_mod.COMPOSE_FLAG, False)

    def test_outside_the_access_team(self):
        Sidebar = self.env['pb.sidebar.item']
        self.assertEqual(Sidebar.visibility_for(self.outsider)['items'][self.item.id], 'locked')
        Intent = self.env['learn.intent'].with_user(self.outsider)
        self.assertFalse(Intent._access_visible())
        Helper = self.env['learn.helper'].with_user(self.outsider)
        self.assertFalse(Helper._offerable('sc_access'))
        for screen in ('payruns', 'approvals', None):
            out = Helper.route('delegate my access', screen, 'en')
            blob = json.dumps(out)
            self.assertEqual(out['route'], 'miss', screen)
            for needle in ('sc_access', 'ac-handover', '"delegate"'):
                self.assertNotIn(needle, blob, screen)
        self.assertFalse(Intent.answer_for('delegate', 'payruns')['matched'])
        floor = Intent.explain_screen('access')
        self.assertEqual((floor.get('watch'), floor.get('try')), ('', ''))

    def test_on_the_access_team(self):
        Sidebar = self.env['pb.sidebar.item']
        self.assertEqual(Sidebar.visibility_for(self.team_member)['items'][self.item.id], 'on')
        self.assertTrue(self.env['learn.intent'].with_user(self.team_member)._access_visible())
        out = self.env['learn.helper'].with_user(self.team_member).route(
            'delegate my access', 'payruns', 'en')
        self.assertEqual(out['answer']['watch'], 'sc_access')
