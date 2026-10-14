# -*- coding: utf-8 -*-
"""ONECHAT OC3 — the server halves of voice, EXECUTED offline (no odoo-bin, PA10).

    python3 pb_payai_actions/tests/offline/test_onechat_oc3.py

The real `payroll.ai.conversation` voice seam, the real OpenAI provider's
transcription call and the real PayAI runner / router run over `odoo_stub`;
the speech service, the consent row and the task row are fakes the test sets.
The same assertions run against records on the clone in
`pb_payroll_ai_insights/tests/test_onechat_voice.py` and
`pb_payai_actions/tests/test_onechat_voice.py`.

Numbers in the test names are the handover's §11 OC3 cases; Q6 is the owner's
decision 2026-10-14 (a spoken plan naming a person or an amount always needs
a tap).
"""
import importlib.util
import inspect
import json
import logging
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import router_env as R  # noqa: E402
from odoo_stub import REPO, load_addon_models, load_file, package  # noqa: E402

RUNNER = R.PAYAI.runner
ACTIONS = R.PAYAI.registry.ACTIONS
I18N = sys.modules['odoo.addons.pb_payai_actions.payai.i18n']

load_addon_models('pb_payroll_ai_insights', ['payroll_ai_consent', 'payroll_ai_conversation'])
CONV_MOD = sys.modules['odoo.addons.pb_payroll_ai_insights.models.payroll_ai_conversation']

DECISION_WORDS = ('approve', 'send back', 'send it back', 'turn down', 'reject', 'decline',
                  'go ahead', 'confirm', 'duyệt', 'gửi lại', 'từ chối', 'tiến hành', 'đồng ý')


# ------------------------------------------------------------ the voice seam
class _Consent:
    def __init__(self, state='granted'):
        self.state = state

    def voice_state(self):
        return self.state

    def voice_granted(self):
        return self.state == 'granted'


class _Speech:
    def __init__(self, text='how do I run payroll'):
        self.text = text
        self.calls = []

    def transcribe_audio(self, audio_bytes, **kw):
        self.calls.append(kw)
        return self.text


class TestTranscribe(unittest.TestCase):
    """3.2 — `rpc_transcribe_voice(audio, lang=None, mime=None)`."""

    def setUp(self):
        self.env = R.make_env('P', lang='en_US')
        self.env.extra.pop('payroll.ai.conversation')
        self.env.extra['ir.config_parameter'].set_param('payai.voice_enabled', 'True')
        self.env.extra['payroll.ai.consent'] = _Consent('granted')
        self.Conv = self.env['payroll.ai.conversation']
        self.speech = _Speech()
        test = self
        self.patch = R.Patch(self.Conv, _speech_provider=lambda self_: test.speech)
        self.patch.__enter__()

    def tearDown(self):
        self.patch.__exit__(None, None, None)

    AUDIO = 'dm9pY2UtYnl0ZXM='          # base64 of b"voice-bytes"

    def test_3_2_language_only_when_asked(self):
        out = self.Conv.rpc_transcribe_voice(self.AUDIO, lang='vi', mime='audio/webm')
        self.assertEqual(out, {'text': 'how do I run payroll'})
        kw = self.speech.calls[-1]
        self.assertEqual(kw['language'], 'vi')
        self.assertEqual(kw['prompt'], CONV_MOD.VOICE_VOCAB['vi'])
        self.assertEqual(kw['filename'], 'voice.webm')
        # Auto-detect: NO language argument at all — never language=None.
        self.Conv.rpc_transcribe_voice(self.AUDIO)
        kw = self.speech.calls[-1]
        self.assertNotIn('language', kw)
        self.assertEqual(kw['prompt'], CONV_MOD.VOICE_VOCAB['en'], 'the hint follows the reader')
        # A language outside the two is auto-detect, not passed through.
        self.Conv.rpc_transcribe_voice(self.AUDIO, lang='fr')
        self.assertNotIn('language', self.speech.calls[-1])
        self.Conv.rpc_transcribe_voice(self.AUDIO, lang='en')
        self.assertEqual(self.speech.calls[-1]['language'], 'en')
        # A Vietnamese reader with no language asked: the Vietnamese hint.
        env_vi = R.make_env('P', lang='vi_VN')
        env_vi.extra.pop('payroll.ai.conversation')
        env_vi.extra['ir.config_parameter'].set_param('payai.voice_enabled', 'True')
        env_vi.extra['payroll.ai.consent'] = _Consent('granted')
        Conv_vi = env_vi['payroll.ai.conversation']
        with R.Patch(Conv_vi, _speech_provider=lambda self_: self.speech):
            Conv_vi.rpc_transcribe_voice(self.AUDIO)
        self.assertEqual(self.speech.calls[-1]['prompt'], CONV_MOD.VOICE_VOCAB['vi'])
        self.assertNotIn('language', self.speech.calls[-1])

    def test_3_2_the_format_names_the_file(self):
        for mime, name in (('audio/webm;codecs=opus', 'voice.webm'), ('audio/webm', 'voice.webm'),
                           ('audio/mp4', 'voice.mp4'), ('AUDIO/OGG; codecs=opus', 'voice.ogg'),
                           (None, 'voice.webm')):
            self.Conv.rpc_transcribe_voice(self.AUDIO, mime=mime)
            self.assertEqual(self.speech.calls[-1]['filename'], name, mime)
        n = len(self.speech.calls)
        for bad in ('text/html', 'audio/webm/../../x', 'video/mp4', '../voice.exe'):
            out = self.Conv.rpc_transcribe_voice(self.AUDIO, mime=bad)
            self.assertEqual(out, {'error': 'This kind of recording cannot be used here. '
                                            'Please try typing.'}, bad)
        self.assertEqual(len(self.speech.calls), n, 'a refused format reached the service')

    def test_3_2_the_hint_is_nouns_only(self):
        for lang, hint in CONV_MOD.VOICE_VOCAB.items():
            low = hint.lower()
            for word in DECISION_WORDS:
                self.assertNotIn(word, low, (lang, word))
        self.assertEqual(set(CONV_MOD.VOICE_VOCAB), {'en', 'vi'})

    def test_3_1_still_double_gated_and_never_sends(self):
        params = list(inspect.signature(CONV_MOD.PayrollAIConversation.rpc_transcribe_voice).parameters)
        self.assertEqual(params, ['self', 'audio_base64', 'lang', 'mime'])
        self.env.extra['payroll.ai.consent'].state = 'declined'
        out = self.Conv.rpc_transcribe_voice(self.AUDIO)
        self.assertIn('error', out)
        self.env.extra['ir.config_parameter'].set_param('payai.voice_enabled', False)
        out = self.Conv.rpc_transcribe_voice(self.AUDIO)
        self.assertEqual(out, {'error': 'Voice input is switched off for this database.'})
        self.assertFalse(self.speech.calls)

    def test_voice_status_shape(self):
        status = self.Conv.rpc_voice_status()
        self.assertTrue(status['available'])
        self.assertTrue(status['switch_on'] and status['provider_ready'])
        self.assertEqual(status['vocab'], CONV_MOD.VOICE_VOCAB)
        copy = status['copy']
        self.assertTrue(copy['consent_body'].startswith('Tap the microphone and speak.'))
        self.assertIn('Tap Cancel and nothing is sent.', copy['consent_body'])
        self.assertEqual(copy['tap_hint'], 'Tap to speak')
        self.assertNotIn('hold_hint', copy)
        # Declined: no microphone, but the menu can tell voice could be had.
        self.env.extra['payroll.ai.consent'].state = 'declined'
        status = self.Conv.rpc_voice_status()
        self.assertFalse(status['available'] or status['ask'])
        self.assertTrue(status['switch_on'] and status['provider_ready'])
        # Switch off: neither.
        self.env.extra['ir.config_parameter'].set_param('payai.voice_enabled', False)
        status = self.Conv.rpc_voice_status()
        self.assertFalse(status['switch_on'] or status['provider_ready'] or status['available'])

    def test_vietnamese_consent_copy(self):
        env_vi = R.make_env('P', lang='vi_VN')
        env_vi.extra.pop('payroll.ai.conversation')
        env_vi.extra['ir.config_parameter'].set_param('payai.voice_enabled', 'True')
        env_vi.extra['payroll.ai.consent'] = _Consent('unset')
        from odoo_stub import CURRENT_LANG
        CURRENT_LANG['lang'] = 'vi_VN'
        try:
            Conv_vi = env_vi['payroll.ai.conversation']
            with R.Patch(Conv_vi, _speech_provider=lambda self_: self.speech):
                copy = Conv_vi.rpc_voice_status()['copy']
        finally:
            CURRENT_LANG['lang'] = 'en_US'
        body = copy['consent_body'].lower()
        for claim in ('khi bạn bấm dừng, bản ghi âm sẽ được gửi', 'công ty bên ngoài',
                      'không thể bỏ tên riêng', 'nằm chờ trong ô nhập', 'hủy bỏ'):
            self.assertIn(claim, body)
        self.assertEqual(copy['tap_hint'], 'Bấm để nói')


# --------------------------------------------------------- the provider log
class TestProviderLog(unittest.TestCase):
    """3.3 — the provider logs counts, never the words."""

    @classmethod
    def setUpClass(cls):
        base = 'odoo.addons.pb_payroll_ai_insights.ai_providers'
        package(base, os.path.join(REPO, 'pb_payroll_ai_insights', 'ai_providers'))
        load_file(base + '.base_provider',
                  os.path.join(REPO, 'pb_payroll_ai_insights', 'ai_providers', 'base_provider.py'))
        cls.mod = load_file(base + '.openai_provider',
                            os.path.join(REPO, 'pb_payroll_ai_insights', 'ai_providers',
                                         'openai_provider.py'))

    def _provider(self, said):
        calls = []

        class _Resp:
            text = said

        class _Tr:
            def create(self, **kw):
                calls.append(kw)
                return _Resp()

        class _Client:
            audio = type('A', (), {'transcriptions': _Tr()})()

        cls = self.mod.OpenAIProvider
        prov = cls.__new__(cls)
        prov._get_client = lambda: _Client()
        return prov, calls

    def test_3_3_no_transcript_in_the_log(self):
        said = 'Give Lan Nguyen a meal allowance of 500,000'
        prov, calls = self._provider(said)
        logger = logging.getLogger(self.mod.__name__)
        with self.assertLogs(logger, level='DEBUG') as cap:
            out = prov.transcribe_audio(b'x' * 1234)
        self.assertEqual(out, said)
        joined = '\n'.join(cap.output)
        for piece in ('Lan', 'Nguyen', '500,000', 'allowance'):
            self.assertNotIn(piece, joined)
        self.assertIn('1234 bytes', joined)
        self.assertIn('%d characters' % len(said), joined)
        # Auto-detect: no language key; the file name and hint as given.
        self.assertNotIn('language', calls[-1])
        prov.transcribe_audio(b'x', language='vi', filename='voice.mp4', prompt='Payobook')
        self.assertEqual((calls[-1]['language'], calls[-1]['file'].name, calls[-1]['prompt']),
                         ('vi', 'voice.mp4', 'Payobook'))


# --------------------------------------------------------------- Q6 / 3.6-3.8
def _named_people(names=('Vũ Khánh Chi',)):
    return {'status': 'resolved', 'value': {'text': '', 'employee_ids': [11], 'names': list(names)},
            'label': ', '.join(names), 'origin': 'said'}


def _everyone():
    return {'status': 'resolved', 'value': {'text': '', 'employee_ids': [], 'names': []},
            'label': '', 'origin': 'default'}


class _Task:
    def __init__(self, action_key='run_payroll', tier='prepare', data=None, state='planned'):
        self.id = 7
        self.action_key = action_key
        self.tier = tier
        self.state = state
        self.params_json = json.dumps(data or {})
        self.plan_json = '{}'
        self.session_id = False

    def __bool__(self):
        return True


class TestSpokenNeedsTap(unittest.TestCase):
    """Q6 — the pure rule."""

    def test_names_and_amounts(self):
        run, pay, send = ACTIONS['run_payroll'], ACTIONS['update_pay_data'], ACTIONS['send_payslips']
        rule = RUNNER.spoken_needs_tap
        self.assertTrue(rule(run, {'spoken': True, 'params': {'people': _named_people()}}))
        self.assertFalse(rule(run, {'params': {'people': _named_people()}}), 'typed plans keep voice')
        self.assertFalse(rule(run, {'spoken': True, 'params': {'people': _everyone()}}),
                         'a run for everyone names nobody')
        self.assertFalse(rule(run, {'spoken': True, 'params': {
            'people': {'status': 'resolved', 'value': {'text': 'active only', 'employee_ids': [],
                                                       'names': []}}}}), 'a status is not a name')
        person = {'status': 'resolved', 'value': 11, 'label': 'Lan Nguyen'}
        self.assertTrue(rule(pay, {'spoken': True, 'params': {'person': person}}))
        self.assertTrue(rule(pay, {'spoken': True, 'params': {
            'value': {'status': 'resolved', 'value': 0, 'label': '0'}}}), '0 is an amount too')
        self.assertFalse(rule(send, {'spoken': True, 'params': {
            'run': {'status': 'resolved', 'value': 5, 'label': 'June 2031'}}}))
        self.assertFalse(rule(None, {'spoken': True}))
        self.assertFalse(rule(run, None))

    def test_run_marks_a_spoken_request(self):
        src = inspect.getsource(RUNNER.run)
        self.assertIn("if ctx.voice:", src)
        self.assertIn("data['spoken'] = True", src)


class _Company:
    def __init__(self, voice_go_ahead=True):
        self.payai_voice_go_ahead = voice_go_ahead
        self.id = 1


class TestConfirmByVoice(unittest.TestCase):
    """Q6 + 3.7 — the confirm path refuses `how='voice'` for a spoken plan
    that names a person or an amount, EN and VI; everything else unchanged."""

    def setUp(self):
        self.saved = (RUNNER._own_task, RUNNER._is_latest)
        self.latest = []

        def own(ctx, task_id, lock=False):
            ctx.task = self.task
            return self.task

        def latest(ctx, task, past_answers=False):
            self.latest.append(task.id)
            return False
        RUNNER._own_task = own
        RUNNER._is_latest = latest

    def tearDown(self):
        RUNNER._own_task, RUNNER._is_latest = self.saved

    def _ctx(self, voice_go_ahead=True):
        env = R.S.Fake(company=_Company(voice_go_ahead))
        return R.S.Fake(env=env, user=R.S.Fake(id=2, name='Harness'), voice=True, task=None)

    def _confirm(self, data, lang='en_US', switch=True, action='run_payroll'):
        self.task = _Task(action, data=data)
        token = I18N.set_lang(lang)
        try:
            return RUNNER.confirm(self._ctx(switch), 7, 'voice')
        finally:
            I18N.reset_lang(token)

    def test_q6_en_and_vi(self):
        spoken = {'spoken': True, 'params': {'people': _named_people()}}
        card = self._confirm(spoken)
        self.assertEqual(card['notes'][0]['text'],
                         'Tap Do it — I heard a name or an amount, so I need your tap.')
        self.assertEqual(card['title'], 'Tap Do it to go ahead')
        self.assertTrue(card.get('transient'), 'the plan card keeps its Do it')
        self.assertEqual(self.task.state, 'planned')
        self.assertFalse(self.latest, 'refused before anything else was asked')
        card = self._confirm(spoken, lang='vi_VN')
        self.assertEqual(card['notes'][0]['text'],
                         'Hãy bấm Thực hiện — tôi nghe thấy một cái tên hoặc một số tiền, '
                         'nên cần bạn bấm để xác nhận.')
        # An amount (Change a pay value), EN.
        pay = {'spoken': True, 'params': {'person': {'status': 'resolved', 'value': 11},
                                          'value': {'status': 'resolved', 'value': 500000}}}
        card = self._confirm(pay, action='update_pay_data')
        self.assertIn('I heard a name or an amount', card['notes'][0]['text'])

    def test_q6_does_not_touch_the_other_rules(self):
        # Switch off: the switched-off sentence, as before.
        card = self._confirm({'spoken': True, 'params': {'people': _named_people()}}, switch=False)
        self.assertIn('switched off', card['notes'][0]['text'])
        # A TYPED plan naming a person: Q6 stands aside; the latest-plan rule
        # (unchanged) is what is asked next.
        card = self._confirm({'params': {'people': _named_people()}})
        self.assertEqual(self.latest, [7])
        self.assertIn('not the last thing I showed you', card['notes'][0]['text'])
        # A spoken plan for everyone: also on to the latest-plan rule.
        self.latest.clear()
        self._confirm({'spoken': True, 'params': {'people': _everyone()}})
        self.assertEqual(self.latest, [7])


class TestReadBackTail(unittest.TestCase):
    """3.8 / Q6 — the plan's read-back never offers "say go ahead" for a
    spoken plan naming a person; it still does for one that names nobody."""

    def _plan(self, data, switch=True):
        test = self

        class _Act:
            key = 'run_payroll'
            tier = 'prepare'
            slots = ACTIONS['run_payroll'].slots

            def plan(self, ctx, params):
                return {'card': {'kind': 'plan'}, 'vals': {}, 'fingerprint': 'f',
                        'speak': 'I will run June 2031 payroll for Retail, 3 people.'}

        class _Savepoint:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        task = _Task(data=data)
        task.sudo = lambda: task
        task.write = lambda vals: None
        task._ttl = lambda: RUNNER.timedelta(minutes=10)
        env = R.S.Fake(company=_Company(switch), cr=R.S.Fake(savepoint=lambda: _Savepoint()))
        ctx = R.S.Fake(env=env, voice=True, user=R.S.Fake(id=2, name='H'), task=task)
        saved = RUNNER._finish
        RUNNER._finish = lambda ctx_, task_, state, card, error='': card
        try:
            token = I18N.set_lang('en_US')
            try:
                return RUNNER._plan(ctx, _Act(), task, data.get('params') or {}, dict(data))
            finally:
                I18N.reset_lang(token)
        finally:
            RUNNER._finish = saved

    def test_tail(self):
        named = self._plan({'spoken': True, 'params': {'people': _named_people()}})
        self.assertTrue(named['speak'].endswith('Tap Do it to go ahead.'), named['speak'])
        nobody = self._plan({'spoken': True, 'params': {'people': _everyone()}})
        self.assertTrue(nobody['speak'].endswith('Tap Do it or say go ahead.'), nobody['speak'])
        off = self._plan({'spoken': True, 'params': {'people': _everyone()}}, switch=False)
        self.assertTrue(off['speak'].endswith('Tap Do it to go ahead.'), off['speak'])


class TestRouterTapNote(unittest.TestCase):
    """The router's "yes" note follows Q6 too: no "or say go ahead" over a
    spoken plan naming a person (the runner would refuse it)."""

    def test_tap_note(self):
        env = R.make_env('P', voice_go_ahead=True)
        helper = R.helper(env)
        spoken = _Task(data={'spoken': True, 'params': {'people': _named_people()}})
        typed = _Task(data={'params': {'people': _named_people()}})

        class _Conv:
            id = 41

        class _PCtx:
            conversation = _Conv()

        for task, says in ((spoken, 'Tap Do it to go ahead.'), (typed, 'Tap Do it or say go ahead.')):
            with R.Patch(helper, _payai_ctx=lambda self_, sid=None: _PCtx(),
                         _planned_task=lambda self_, ctx, t=task: t,
                         _voice_offered=lambda self_: True):
                out = helper.route('yes', 'payruns', 'en', 41)
            self.assertEqual((out['why'], out['note']['en']), ('tap_card', says), task.params_json)


if __name__ == '__main__':
    unittest.main(verbosity=1)
