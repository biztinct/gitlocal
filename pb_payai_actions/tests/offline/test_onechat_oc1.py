# -*- coding: utf-8 -*-
"""ONECHAT OC1 — the server router, EXECUTED offline (no odoo-bin, PA10).

    python3 pb_payai_actions/tests/offline/test_onechat_oc1.py

The real source of the three `learn.helper` layers, `learn.intent`,
`learn.content`, PayAI's phrase table / runner / gate, the conversation
model and the engine's command-path switch runs over `odoo_stub`. What needs
a table (a plan waiting, a reason question open, a conversation row) is set
by the test — the same assertions run against records on the clone in
`pb_learn/tests/test_helper_route.py`, `pb_payroll_ai_insights/tests/
test_onechat_conversation.py` and `pb_payai_actions/tests/test_onechat_router.py`.

Numbers in the test names are the handover's §11 OC1 cases.
"""
import inspect
import json
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import router_env as R  # noqa: E402
from odoo_stub import REPO, load_addon_models, load_file  # noqa: E402

H = R.LEARN['learn_helper']
INTENT = R.LEARN['learn_intent']
RUNNER = R.PAYAI.runner
REGISTRY_MOD = R.PAYAI.registry


def _read(*parts):
    with open(os.path.join(REPO, *parts), encoding='utf-8') as fh:
        return fh.read()


CORPUS = json.loads(_read('pb_learn', 'tests', 'data', 'onechat_route_corpus.json'))['rows']
GEN_DIR = os.path.join(REPO, 'docs', 'tutorial_poc', 'author', 'tools')


# ------------------------------------------------------------ the state
class _Task:
    def __init__(self, tier='prepare', action_key='run_payroll'):
        self.tier = tier
        self.action_key = action_key
        self.id = 7

    def __bool__(self):
        return True


class _Conv:
    id = 41

    def __bool__(self):
        return True


class _Ctx:
    conversation = _Conv()


def _state_patches(helper, state, env):
    """Patch the P layer's two table reads for a conversation `state`."""
    task = None
    if state in ('plan_amber', 'plan_amber_voice'):
        task = _Task('prepare', 'run_payroll')
    elif state == 'plan_red':
        task = _Task('decide', 'approve_item')
    if state == 'plan_amber_voice':
        env.company.payai_voice_go_ahead = True
        env.extra['payroll.ai.conversation'].voice = True
    patches = {
        '_payai_ctx': lambda self, sid=None: _Ctx(),
        '_planned_task': lambda self, ctx: task,
    }
    return R.Patch(helper, **patches)


class _OpenQuestion:
    """runner._open_question → a question open (reason_open) or None."""

    def __init__(self, open_):
        self.open_ = open_

    def __enter__(self):
        self.saved = RUNNER._open_question
        RUNNER._open_question = (lambda ctx: ('task', {}, None, None)) if self.open_ \
            else (lambda ctx: None)

    def __exit__(self, *exc):
        RUNNER._open_question = self.saved


def _summ(r):
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


def route(mode, text, screen='payruns', state=None, env=None, **env_kw):
    env = env or R.make_env(mode, **env_kw)
    helper = R.helper(env)
    if mode == 'B':
        with R.Patch(helper, **R.base_hooks()):
            return helper.route(text, screen), env
    with _state_patches(helper, state, env), _OpenQuestion(state == 'reason_open'):
        return helper.route(text, screen), env


class TestCorpus(unittest.TestCase):
    """1.1 — the routing corpus, both columns, EN + VI, several screens."""

    def _column(self, mode):
        failures = []
        for row in CORPUS:
            want = row.get(mode)
            if want is None:
                continue
            got, env = route(mode, row['text'], row['screen'], row.get('state'))
            summ = _summ(got)
            for key, value in want.items():
                if summ.get(key) != value:
                    failures.append('%s %r on %s [%s]: %s=%r, want %r (got %s)' % (
                        mode, row['text'], row['screen'], row.get('state'), key,
                        summ.get(key), value, summ))
            for key in ('ask_only', 'answer', 'practice', 'note', 'extra_chips',
                        'choices', 'fallback_key'):
                if key in summ and key not in want:
                    failures.append('%s %r: unexpected %s=%r' % (mode, row['text'], key, summ[key]))
            self.assertIn(got['route'], H.ROUTES)
            self.assertIn(got['why'], H.WHYS)
            # 1.3 — no row reaches a model.
            if env.provider is not None:
                self.assertEqual(env.provider.calls, [], row['text'])
        self.assertFalse(failures, '\n'.join(failures))

    def test_1_1_P(self):
        self._column('P')

    def test_1_1_B(self):
        self._column('B')

    def test_1_1_the_corpus_covers_the_handover_rows(self):
        texts = {r['text'] for r in CORPUS}
        for must in ('approve the request waiting for me', 'Run payroll?', 'lock the week',
                     'cho tôi thực hành chạy lương', 'Làm thủ tục nghỉ việc cho Lan',
                     'how many payslips are in the June run', 'delegate my access',
                     'Practice of paying overtime twice must stop', 'show me the tour'):
            self.assertIn(must, texts)
        self.assertTrue({r['screen'] for r in CORPUS} >= {'payruns', 'approvals', 'dashboard', None})


class TestOrderAndShape(unittest.TestCase):
    def test_1_4_composer_only_where_payai_cannot_answer(self):
        # PayAI available + composer ON: no sentence composes.
        env = R.make_env('P', compose=True)
        provider = _Recorder()
        env.extra['payroll.ai.config'] = R.FakeConfig(provider)
        provider.available = True
        helper = R.helper(env)
        for row in CORPUS:
            if row.get('state'):
                continue
            helper.route(row['text'], row['screen'])
        self.assertEqual(provider.texts, [], 'the composer ran where PayAI answers')
        # PayAI NOT available + composer ON: a command, a data or a practise
        # sentence never composes; a question nobody wrote about does, once.
        env = R.make_env('B', compose=True)
        provider = _Recorder()
        env.extra['payroll.ai.config'] = R.FakeConfig(provider)
        helper = R.helper(env)
        with R.Patch(helper, **R.base_hooks()):
            for text in ('run June payroll for Retail', 'please process June salaries',
                         'show me headcount by department', 'let me practise running payroll',
                         'open the runs board'):
                helper.route(text, 'payruns')
            self.assertEqual(provider.texts, [])
            out = helper.route('how do I change the office wifi password', 'payslips')
        self.assertEqual(len(provider.texts), 1)
        self.assertEqual(out['route'], 'miss')       # NO_ANSWER → the honest miss

    def test_1_5_practise_before_commands(self):
        out, _env = route('P', 'let me practise running payroll')
        self.assertEqual((out['route'], out['practice']['key'], out['practice']['mode']),
                         ('practice', 'sc_payrun', 'try'))

    def test_1_6_an_open_question_takes_everything(self):
        for text in ('Approve the overtime first', 'Practice of paying overtime twice must stop',
                     'explain this screen is wrong', 'yes', 'thanks', 'how do I approve a request'):
            out, _env = route('P', text, state='reason_open')
            self.assertEqual((out['route'], out['why']), ('payai', 'open_question'), text)

    def test_1_7_go_ahead_and_bare_words(self):
        out, _env = route('P', 'go ahead', state='plan_amber')
        self.assertEqual((out['route'], out['why']), ('payai', 'goahead'))
        out, _env = route('P', 'go ahead')
        self.assertEqual(out['note']['en'], 'Nothing is waiting for your go-ahead.')
        out, _env = route('B', 'go ahead')
        self.assertEqual(out['note']['en'], "I can't do things for you here — ask me how instead.")
        out, _env = route('P', 'yes', state='plan_amber')
        self.assertEqual(out['note']['en'], 'Tap Do it to go ahead.')
        self.assertEqual(out['note']['vi'], 'Bấm Thực hiện để tiếp tục.')   # the runner's msgstr
        out, _env = route('P', 'yes', state='plan_amber_voice')
        self.assertEqual(out['note']['en'], 'Tap Do it or say go ahead.')
        self.assertEqual(out['note']['vi'], 'Bấm Thực hiện hoặc nói "tiến hành".')
        # Switch on but no microphone for this person → the tap wording.
        env = R.make_env('P', voice_go_ahead=True, voice=False)
        out, _env = route('P', 'yes', state='plan_amber', env=env)
        self.assertEqual(out['note']['en'], 'Tap Do it to go ahead.')
        out, _env = route('P', 'yes', state='plan_red')
        self.assertEqual(out['note']['en'], 'Type APPROVE in the box on the card.')
        self.assertEqual(out['note']['vi'], 'Hãy gõ DUYỆT vào ô trên thẻ.')
        out, _env = route('P', 'cancel', state='plan_amber')
        self.assertEqual(out['note']['en'], 'To stop, tap Cancel on the plan card.')

    def test_1_8_look_off_is_never_a_command(self):
        out, _env = route('P', 'approve the request waiting for me', look=False)
        self.assertNotEqual((out['route'], out['why']), ('payai', 'command'))
        self.assertEqual(out['route'], 'guide')
        self.assertEqual(out['answer']['key'], 'approve')
        out, _env = route('P', 'go ahead', state='plan_amber', look=False)
        self.assertEqual(out['why'], 'nothing_waiting')

    def test_1_20_route_takes_no_voice(self):
        for fn in (H.LearnHelper.route,
                   type(R.helper(R.make_env('P'))).route):
            params = [p.lower() for p in inspect.signature(fn).parameters]
            self.assertEqual(params, ['self', 'text', 'screen_key', 'lang', 'session_id'])
            self.assertFalse([p for p in params if 'voice' in p or 'spoken' in p
                              or 'speech' in p or 'audio' in p])

    def test_1_23_small_talk_never_reaches_a_model(self):
        for text in ('thanks', 'hi', 'ok', 'uh', 'ờ', 'cảm ơn', 'xin chào', 'hello there',
                     'thank you so much'):
            out, env = route('P', text)
            self.assertEqual((out['route'], out['why']), ('note', 'smalltalk'), text)
            self.assertTrue(out['suggest'], text)
            self.assertEqual(env.provider.calls, [])

    def test_shapes(self):
        q = H.is_question
        for text in ('can I approve the June run?', 'where do I approve requests?',
                     'could I run payroll now?', 'which button approves the run?',
                     'tôi có thể duyệt đợt lương tháng 6 không', 'Đã gửi phiếu lương chưa',
                     'chạy lương thế nào', 'Is Lan on the practice company?'):
            self.assertTrue(q(text), text)
        for text in ('can you run June payroll for Retail?', 'please approve this run',
                     'could you send the payslips?', 'run payroll', 'will you approve it?'):
            self.assertFalse(q(text), text)
        for text in ('show me how to run payroll', 'show me the steps to run payroll',
                     'cho tôi xem cách chạy lương', 'hướng dẫn tôi chạy lương',
                     'chỉ tôi cách duyệt', 'how do I compare two pay runs'):
            self.assertEqual(H.howto_kind(text), 'proc', text)
        self.assertEqual(H.howto_kind('what is BHXH'), 'def')
        self.assertIsNone(H.howto_kind('approve what is waiting for me'))
        self.assertTrue(H.data_signal('how many employees do we have'))
        self.assertTrue(H.data_signal('show me net pay for June'))
        self.assertFalse(H.data_signal('what is net pay'))
        self.assertFalse(H.data_signal('show me how to approve the June run'))
        self.assertFalse(H.data_signal('how many payslips should there be'))
        self.assertTrue(H.figure_ref('how much back pay is owed to Lan'))
        self.assertFalse(H.figure_ref('How do I approve a request?'))
        self.assertEqual(H.order_task("I'd like to run June payroll for Retail"),
                         ('run payroll', 'en'))
        self.assertEqual(H.order_task('giúp tôi chạy lương tháng 6 cho Retail'),
                         ('chay luong', 'vi'))


class _Recorder:
    """A provider that records composer calls and always says NO_ANSWER."""
    available = False

    def __init__(self):
        self.texts = []

    def is_available(self):
        return self.available

    def generate_text(self, prompt, **kw):
        self.texts.append(prompt)
        return 'NO_ANSWER'

    def generate_chat(self, *a, **k):
        raise AssertionError('chat')

    generate_tools = generate_chat


class TestProbe(unittest.TestCase):
    def setUp(self):
        self.env = R.make_env('B')
        self.Intent = self.env['learn.intent']

    def test_1_9_kinds_and_passes(self):
        hit = self.Intent.probe('what is BHXH', 'payruns')
        self.assertEqual((hit['key'], hit['kind'], hit['scope']), ('bhxh', 'exact', 'any'))
        hit = self.Intent.probe('approve', 'payruns')
        # The on-screen bonus is reported apart from the kind (60 + 25).
        self.assertEqual((hit['key'], hit['kind'], hit['on_screen'], hit['score']),
                         ('approve', 'reverse', True, 85))
        hit = self.Intent.probe('how do I pay less BHXH', 'payruns')
        self.assertEqual((hit['key'], hit['source'], hit['kind']), ('compliance', 'advice', 'exact'))
        # A tie AT the floor is a miss: "what is the company holiday policy"
        # scored 40 against two intents (simulate_resolver's own probe).
        self.assertIsNone(self.Intent.probe('what is the company holiday policy'))
        # `_score` and `_resolve_hook` read the same as before the split.
        for intent in self.env['learn.content'].intents()[:20]:
            kind, base = self.Intent._score_kind('how do i approve', intent)
            bonus = 25 if base and self.Intent._on_screen(intent, 'payruns') else 0
            self.assertEqual(self.Intent._score('how do i approve', intent, 'payruns'),
                             base + bonus)
        self.assertEqual(self.Intent.resolve('how do I approve a request', 'payruns'), 'approve')

    def test_1_10_miss_payload_keys(self):
        res = self.Intent.ask('how do I change the office wifi password', 'payslips')
        self.assertEqual(set(res), {'matched', 'capability', 'suggest'})
        out, _env = route('B', 'how do I change the office wifi password', 'payslips')
        self.assertEqual(set(out['answer']), {'matched', 'capability', 'suggest'})

    def test_1_11_answer_for_equals_ask(self):
        Content = self.env['learn.content']
        checked = 0
        for intent in Content.intents():
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

    def test_1_13_explain_offer(self):
        tree = self.env['learn.content'].tree()
        want = {'payruns': ('sc_welcome', 'sc_payslips'), 'runpayroll': ('sc_welcome', 'sc_payrun'),
                'formula': ('sc_welcome', 'sc_formula'), 'approvals': ('sc_welcome', ''),
                'dashboard': ('sc_welcome', '')}
        for screen, pair in want.items():
            self.assertEqual(INTENT.explain_scenario_offer(tree, screen), pair, screen)


class TestPractice(unittest.TestCase):
    def test_1_12_phrases_triggers_and_generator(self):
        env = R.make_env('B')
        for sc in env['learn.content'].scenarios():
            if sc.get('retired'):
                continue
            phrases = sc.get('phrases') or []
            vi = [p for p in phrases if H.has_marks(p)]
            folded = {H._norm(p) for p in vi}
            plain_vi = [p for p in phrases if not H.has_marks(p) and H._norm(p) in folded]
            en = [p for p in phrases if not H.has_marks(p) and H._norm(p) not in folded]
            self.assertGreaterEqual(len(en), 3, (sc['key'], en))
            self.assertGreaterEqual(len(vi), 3, (sc['key'], vi))
            self.assertGreaterEqual(len(plain_vi), 3, (sc['key'], plain_vi))
        wftime = env['learn.content'].scenario('sc_wftime')
        self.assertIn('approve overtime', wftime['phrases'])
        self.assertIn('duyệt tăng ca', wftime['phrases'])
        # Triggers.
        for text in ('try again', 'Làm thủ tục nghỉ việc cho Lan', 'làm thủ công',
                     'nhân viên mới đang tập làm quen', 'Practice of paying overtime twice must stop',
                     'tap lam quen', 'lam thu tuc', 'try it', 'practical guide'):
            self.assertEqual(H.practise_trigger(text), (None, ''), text)
        for text, kind in (('show me the tour', 'tour'), ('start the tour', 'tour'),
                           ('open the practice company', 'company'), ('practice', 'practise'),
                           ('cho tôi thực hành chạy lương', 'practise'), ('làm thử', 'practise'),
                           ('cho toi thuc hanh', 'practise'), ('đi một vòng Payobook', 'tour')):
            self.assertEqual(H.practise_trigger(text)[0], kind, text)
        out, _env = route('P', 'how do I get off the practice company?')
        self.assertNotIn('key', out.get('practice') or {}, 'a question started a practice')
        # The generator refuses a phrase on two scenarios.
        sys.path.insert(0, GEN_DIR)
        import gen_learn_data as gen
        problems, owner = [], {}
        gen._check_scenario_phrases('sc_a', ['Run payroll', 'chạy lương'], owner, problems)
        gen._check_scenario_phrases('sc_b', ['run  payroll!', 'chay luong'], owner, problems)
        self.assertEqual(len(problems), 2, problems)
        self.assertIn('also a phrase of sc_a', problems[0])

    def test_practice_probe(self):
        Intent = R.make_env('B')['learn.intent']
        self.assertEqual(Intent.practice_probe('run payroll')['key'], 'sc_payrun')
        self.assertEqual(Intent.practice_probe('approve overtime')['key'], 'sc_wftime')
        self.assertEqual(Intent.practice_probe('chạy lương')['key'], 'sc_payrun')
        self.assertIsNone(Intent.practice_probe('something random entirely'))


class TestAccess(unittest.TestCase):
    def test_1_22_access_filter(self):
        for mode in ('B', 'P'):
            out, _env = route(mode, 'delegate my access', access_visible=False)
            blob = json.dumps(out)
            self.assertNotIn('sc_access', blob, mode)
            self.assertNotIn('ac-handover', blob, mode)
            self.assertNotIn('"delegate"', blob, mode)
        out, _env = route('B', 'delegate my access', access_visible=False)
        self.assertEqual(out['route'], 'miss')
        out, _env = route('B', 'delegate my access', access_visible=True)
        self.assertEqual(out['answer']['key'], 'delegate')
        self.assertEqual(out['answer']['watch'], 'sc_access')
        env = R.make_env('B', access_visible=False)
        Intent = env['learn.intent']
        self.assertFalse(Intent.answer_for('delegate', 'payruns')['matched'])
        floor = Intent.explain_screen('access')
        self.assertEqual((floor['watch'], floor['try']), ('', ''))
        # The mirror of PayAI's deny-list stays equal to it.
        self.assertEqual(INTENT.ACCESS_LEARN, R.PAYAI.gate.ACCESS_LEARN)
        # The practice router never offers the Access walkthrough either.
        out, _env = route('B', 'let me practise handing over my access', access_visible=False)
        self.assertNotIn('sc_access', json.dumps(out))


class TestContract(unittest.TestCase):
    def test_1_19_contract(self):
        res = subprocess.run([sys.executable, os.path.join(GEN_DIR, 'check_contract.py'),
                              '--quiet'], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        contract = json.loads(_read('docs', 'tutorial_poc', 'author', 'contract.json'))
        check = next(c for c in contract['checks'] if c['id'] == 'coach-answers-from-writing-only')
        self.assertIn('pb_learn/models/learn_helper.py', check['files'])

    def test_white_label(self):
        tree = R.make_env('B')['learn.content'].tree()
        keys = [k for k in ('nothingWaiting', 'nothingToCancel', 'cannotActHere', 'typeWordOnCard',
                            'tapCancel', 'smalltalk', 'noPayai', 'hereIsHow', 'hereIsHowOrPrepare',
                            'doItForMe', 'askPayData', 'explainHowInstead', 'doItNow', 'howItWorks',
                            'whichMeant', 'doOrHow', 'watchOnlyNote', 'capTitle', 'capExplain',
                            'capAnswer', 'capData', 'capAct', 'capPractise', 'capVoice')]
        for key in keys:
            pair = tree['chrome'].get(key)
            self.assertTrue(pair and pair['en'] and pair['vi'], key)
            self.assertNotEqual(pair['en'], pair['vi'], key)
            self.assertNotIn('odoo', (pair['en'] + pair['vi']).lower(), key)
        for path in ('pb_learn/models/learn_helper.py', 'pb_payroll_ai_insights/models/learn_helper.py',
                     'pb_payai_actions/models/learn_helper.py'):
            src = _read(path)
            # Only `from odoo …` imports and the module path may name it.
            for line in src.splitlines():
                if 'odoo' in line.lower() and not line.lstrip().startswith(('from odoo', 'import odoo')) \
                        and 'odoo.addons' not in line:
                    self.fail('%s: %s' % (path, line))


# ================================================================ R9 / E2
class TestModelCache(unittest.TestCase):
    """3.9 (fixed in OC1, handover R9) — the tools-call cache never hands a
    real name across a Clear, a conversation or a database."""

    def setUp(self):
        RUNNER._LRU.clear()
        self.calls = []
        test = self

        class Prov:
            def is_available(self):
                return True

            def generate_tools(self, messages, tools):
                test.calls.append(messages[-1]['content'])
                return {'tool_name': 'run_payroll', 'arguments': {'people': '[person-1] only'}}

        self.saved = (RUNNER._provider, REGISTRY_MOD.tools_schema, RUNNER._redact)
        RUNNER._provider = lambda env: Prov()
        REGISTRY_MOD.tools_schema = lambda env, user: [{'name': 'run_payroll'}]
        self.mapping = {'[person-1]': 'Lan Nguyen'}
        RUNNER._redact = lambda ctx, message: ('Run payroll for [person-1] only', dict(self.mapping))

    def tearDown(self):
        RUNNER._provider, REGISTRY_MOD.tools_schema, RUNNER._redact = self.saved
        RUNNER._LRU.clear()

    def _ctx(self, conv_id=41, db='payobook', uid=2):
        class Engine:
            @staticmethod
            def _brand_name():
                return 'Payobook'

        env = R.S.Fake(cr=R.S.Fake(dbname=db))
        return R.S.Fake(env=env, user=R.S.Fake(id=uid), conversation=_C(conv_id),
                        engine=Engine())

    def test_3_9_restored_from_the_current_mapping(self):
        ctx = self._ctx()
        self.assertEqual(RUNNER.ask_model(ctx, 'Run payroll for Lan Nguyen only'),
                         ('run_payroll', {'people': 'Lan Nguyen only'}))
        self.assertEqual(len(self.calls), 1)
        stored = json.dumps(list(RUNNER._LRU.values()))
        self.assertIn('[person-1]', stored)
        self.assertNotIn('Lan', stored)
        # Clear chat → the numbering restarts: the same redacted words now
        # mean another person. The hit restores the CURRENT one.
        self.mapping = {'[person-1]': 'Minh Tran'}
        self.assertEqual(RUNNER.ask_model(ctx, 'Run payroll for Minh Tran only'),
                         ('run_payroll', {'people': 'Minh Tran only'}))
        self.assertEqual(len(self.calls), 1, 'a cache hit called the model')
        # Another conversation, another database: never the same entry.
        RUNNER.ask_model(self._ctx(conv_id=42), 'x')
        RUNNER.ask_model(self._ctx(db='rize'), 'x')
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(len({k[:3] for k in RUNNER._LRU}), 3)


class _C:
    def __init__(self, cid):
        self.id = cid

    def __bool__(self):
        return True


class TestAskOnly(unittest.TestCase):
    """1.21 (offline half) — `ask_only` only ever removes the command path."""

    @classmethod
    def setUpClass(cls):
        import odoo_stub as S

        class _BaseEngine(S.BaseModel):
            _name = 'payroll.ai.engine'

            def process_message(self, message, conversation_history=None, context=None):
                return {'response': 'answer', 'intent': 'payroll_knowledge',
                        'follow_up_questions': []}

            def _conversation(self, context):
                return _C(41)

        if 'odoo.addons.pb_payai_actions.models.payai_engine' not in sys.modules:
            load_addon_models('pb_payai_actions', ['payai_engine'])

    def _engine(self, ask_only, look=True):
        env = R.make_env('P', look=look).with_context(payai_ask_only=ask_only)
        return env['payroll.ai.engine']

    def _run(self, message, ask_only, open_question=False, resolve=None):
        handled = []
        saved = (RUNNER.handle, RUNNER._open_question, RUNNER.Ctx)
        RUNNER.handle = lambda engine, msg, ctx: handled.append(msg) or None
        RUNNER._open_question = (lambda ctx: ('t', {}, None, None)) if open_question else (lambda ctx: None)
        RUNNER.Ctx = lambda engine, context: object()
        try:
            out = self._engine(ask_only).process_message(
                message, [], {'conversation_id': 41, 'payai_resolve': resolve})
        finally:
            RUNNER.handle, RUNNER._open_question, RUNNER.Ctx = saved
        return handled, out

    def test_1_21_ask_only(self):
        handled, out = self._run('can I approve the June run?', True)
        self.assertEqual(handled, [], 'the command path ran for an ask-only question')
        self.assertEqual(out['response'], 'answer')
        self.assertIn('What can you do?', out['follow_up_questions'])
        self.assertEqual(self._run('go ahead', True)[0], ['go ahead'])
        self.assertEqual(self._run('Approve the overtime first', True, open_question=True)[0],
                         ['Approve the overtime first'])
        self.assertEqual(self._run('Cancel', True, resolve={'task_id': 1})[0], ['Cancel'])
        self.assertEqual(self._run('can I approve the June run?', False)[0],
                         ['can I approve the June run?'])
        # The base module's send knows no ask_only.
        conv_src = _read('pb_payroll_ai_insights', 'models', 'payroll_ai_conversation.py')
        self.assertIn('def rpc_send_message(self, message, session_id=None, screen=None, '
                      'resolve=None):', conv_src)


# ===================================================== one conversation
class TestNoteTurn(unittest.TestCase):
    """1.14 (offline half) — the marker door: authored labels only, owner
    checked, every argument validated, no task id ever written."""

    @classmethod
    def setUpClass(cls):
        load_addon_models('pb_payroll_ai_insights',
                          ['payroll_ai_consent', 'payroll_ai_conversation'])
        cls.conv_mod = sys.modules['odoo.addons.pb_payroll_ai_insights.models.payroll_ai_conversation']

    def setUp(self):
        self.env = R.make_env('P', lang='en_US')
        self.env.extra.pop('payroll.ai.conversation')
        self.Conv = self.env['payroll.ai.conversation']
        self.written = []
        test = self

        class Session:
            id = 41
            user_id = test.env.user

            def add_message(self, role, content, chart_config=None, insights=None,
                            intent=None, card=None):
                test.written.append({'role': role, 'content': content, 'intent': intent,
                                     'card': card})
                return R.S.Fake(id=len(test.written))

        self.session = Session()
        self.patch = R.Patch(self.Conv, _own_session=lambda self_, sid=None: test.session)
        self.patch.__enter__()

    def tearDown(self):
        self.patch.__exit__(None, None, None)

    def test_1_14_markers(self):
        out = self.Conv.rpc_note_turn(41, 'guide', 'approve', None, 'payruns')
        self.assertEqual(out['session_id'], 41)
        row = self.written[-1]
        self.assertEqual((row['role'], row['intent']), ('assistant', 'helper_note'))
        self.assertEqual(row['card'], {'kind': 'guide', 'key': 'approve', 'source_kind': '',
                                       'screen_key': 'payruns'})
        self.assertNotIn('task_id', row['card'])
        self.assertTrue(row['content'])
        for args, needle in ((('explain', 'payruns'), ': '), (('practice', 'sc_payrun'), ''),
                             (('composed', None), 'Composed'), (('capability', None), ''),
                             (('note', 'nothingWaiting'), 'Nothing is waiting'),
                             (('smalltalk', 'smalltalk'), 'Happy to help'),
                             (('miss', 'noPayai'), 'assistant service'),
                             (('choose', 'whichMeant'), 'Which did you mean'),
                             (('guide', 'column:pay_runs'), '')):
            self.Conv.rpc_note_turn(41, *args)
            self.assertIn(needle, self.written[-1]['content'], args)
        # The signature has no text: nothing a browser types is ever written.
        params = list(inspect.signature(self.conv_mod.PayrollAIConversation.rpc_note_turn).parameters)
        self.assertEqual(params, ['self', 'session_id', 'kind', 'key', 'source_kind', 'screen_key'])
        # Vietnamese, from the same content.
        env_vi = R.make_env('P', lang='vi_VN')
        env_vi.extra.pop('payroll.ai.conversation')
        Conv_vi = env_vi['payroll.ai.conversation']
        with R.Patch(Conv_vi, _own_session=lambda self_, sid=None: self.session):
            Conv_vi.rpc_note_turn(41, 'note', 'nothingWaiting')
        self.assertEqual(self.written[-1]['content'], 'Không có việc nào đang chờ bạn đồng ý.')

    def test_1_14_refusals(self):
        UserError = sys.modules['odoo.exceptions'].UserError
        before = len(self.written)
        for args in (('nonsense', 'approve'), ('guide', 'no_such_intent'),
                     ('practice', 'sc_mapping'), ('note', 'not_a_chrome_key'),
                     ('guide', 'approve', 'Bad Kind'), ('guide', 'approve', 'x' * 65),
                     ('guide', 'approve', None, 'no_such_screen'),
                     ('guide', 'approve', None, 'payruns; drop'),
                     ('composed', 'something'), ('guide', "approve' or 1=1")):
            with self.assertRaises(UserError, msg=args):
                self.Conv.rpc_note_turn(41, *args)
        self.assertEqual(len(self.written), before, 'a refused note wrote a row')

    def test_own_session(self):
        AccessError = sys.modules['odoo.exceptions'].AccessError
        self.patch.__exit__(None, None, None)
        other = R.S.Fake(id=9, user_id='someone else', __bool__=lambda: True)
        mine = R.S.Fake(id=41, user_id=self.env.user)

        class Browse:
            def __init__(self, rec):
                self.rec = rec

            def exists(self):
                return self.rec

        with R.Patch(self.Conv, browse=lambda self_, i=None: Browse(other)):
            with self.assertRaises(AccessError):
                self.Conv._own_session(9)
        with R.Patch(self.Conv, browse=lambda self_, i=None: Browse(mine)):
            self.assertIs(self.Conv._own_session(41), mine)
        self.patch.__enter__()


# ============================================ the server file, replayed
class TestServerFileReplay(unittest.TestCase):
    """`pb_learn/tests/test_helper_route.py` is a TransactionCase for the
    clone. Its methods need no record of their own, so they are replayed
    here over the stub environment (B shape) — the same source, executed —
    so the file cannot ship with an assertion nobody ever ran."""

    def test_replay_pb_learn_helper_route(self):
        import types
        common = sys.modules.setdefault('odoo.tests.common', types.ModuleType('odoo.tests.common'))
        sys.modules.setdefault('odoo.tests', types.ModuleType('odoo.tests')).common = common

        class _Case(unittest.TestCase):
            def __init__(self, name='runTest'):
                super().__init__(name)
                self.env = R.make_env('B')
                self.env.flush_all = lambda: None

        common.TransactionCase = _Case
        common.tagged = lambda *a, **k: (lambda cls: cls)
        pkg = 'odoo.addons.pb_learn.tests'
        R.S.package(pkg, os.path.join(REPO, 'pb_learn', 'tests'))
        if pkg + '.common' not in sys.modules:
            load_file(pkg + '.common', os.path.join(REPO, 'pb_learn', 'tests', 'common.py'))
        mod = load_file(pkg + '.test_helper_route',
                        os.path.join(REPO, 'pb_learn', 'tests', 'test_helper_route.py'))
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(mod.TestHelperRouteBase)
        result = unittest.TestResult()
        suite.run(result)
        problems = ['%s: %s' % (t, tb.splitlines()[-1]) for t, tb in result.failures + result.errors]
        self.assertFalse(problems, '\n'.join(problems))
        self.assertGreaterEqual(result.testsRun, 13)


if __name__ == '__main__':
    unittest.main(verbosity=1)
