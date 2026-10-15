# -*- coding: utf-8 -*-
"""ONECHAT OC3 — the voice seam on a real database (handover §6.6, §6.7,
§11 3.2 and 3.3). The offline twin is
`pb_payai_actions/tests/offline/test_onechat_oc3.py`.

* 3.2 `rpc_transcribe_voice(audio, lang=None, mime=None)`: 'vi' passes
  language='vi' and the Vietnamese hint; None passes NO language at all; a
  format outside the table is refused with a plain sentence and never
  reaches the service; the hint has no decision verb in either language;
* 3.3 the provider logs counts, never the words;
* the voice status carries `switch_on` / `provider_ready` (the More menu's
  "Use my voice") and the tap-to-talk copy.

No speech service is reached: `_speech_provider` is patched, and the provider
test gives the OpenAI provider a fake client.
"""
import logging
from unittest.mock import patch

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payroll_ai_insights.ai_providers.openai_provider import OpenAIProvider
from odoo.addons.pb_payroll_ai_insights.models import payroll_ai_conversation as conv_mod
from odoo.addons.pb_payroll_ai_insights.models.payroll_ai_consent import VOICE_FLAG

AUDIO = 'dm9pY2UtYnl0ZXM='          # base64 of b"voice-bytes"
DECISION_WORDS = ('approve', 'send back', 'turn down', 'reject', 'go ahead', 'confirm',
                  'duyệt', 'gửi lại', 'từ chối', 'tiến hành', 'đồng ý')


class _Speech:
    def __init__(self):
        self.calls = []

    def transcribe_audio(self, audio_bytes, **kw):
        self.calls.append(kw)
        return 'how do I run payroll'


@tagged('post_install', '-at_install', 'onechat')
class TestOneChatVoice(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'OC3 Voice', 'login': 'oc3.voice@test.invalid',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])]})

    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param(VOICE_FLAG, 'True')
        self.speech = _Speech()
        Conv = type(self.env['payroll.ai.conversation'])
        p = patch.object(Conv, '_speech_provider', lambda self_: self.speech)
        p.start()
        self.addCleanup(p.stop)
        self.Conv = self.env['payroll.ai.conversation'].with_user(self.user)

    def _agree(self):
        self.env['payroll.ai.consent'].with_user(self.user).set_voice(True)

    # ---------------------------------------------------------------- 3.2
    def test_3_2_language_only_when_asked(self):
        self._agree()
        self.assertEqual(self.Conv.rpc_transcribe_voice(AUDIO, lang='vi', mime='audio/webm'),
                         {'text': 'how do I run payroll'})
        kw = self.speech.calls[-1]
        self.assertEqual((kw['language'], kw['prompt'], kw['filename']),
                         ('vi', conv_mod.VOICE_VOCAB['vi'], 'voice.webm'))
        self.Conv.rpc_transcribe_voice(AUDIO)
        self.assertNotIn('language', self.speech.calls[-1], 'auto-detect must omit the argument')
        self.Conv.rpc_transcribe_voice(AUDIO, lang='xx')
        self.assertNotIn('language', self.speech.calls[-1])

    def test_3_2_formats(self):
        self._agree()
        for mime, name in (('audio/webm;codecs=opus', 'voice.webm'), ('audio/mp4', 'voice.mp4'),
                           ('audio/ogg', 'voice.ogg')):
            self.Conv.rpc_transcribe_voice(AUDIO, mime=mime)
            self.assertEqual(self.speech.calls[-1]['filename'], name)
        n = len(self.speech.calls)
        out = self.Conv.rpc_transcribe_voice(AUDIO, mime='text/html')
        self.assertEqual(out, {'error': 'This kind of recording cannot be used here. Please try typing.'})
        self.assertEqual(len(self.speech.calls), n)

    def test_3_2_the_hint_is_nouns_only(self):
        for hint in conv_mod.VOICE_VOCAB.values():
            for word in DECISION_WORDS:
                self.assertNotIn(word, hint.lower())
        # Never a person: no employee name of this database is in it.
        names = self.env['hr.employee'].sudo().search([], limit=200).mapped('name')
        for hint in conv_mod.VOICE_VOCAB.values():
            for name in names:
                if name and len(name) > 3:
                    self.assertNotIn(name, hint)

    def test_3_1_gates_unchanged(self):
        out = self.Conv.rpc_transcribe_voice(AUDIO)
        self.assertEqual(out, {'error': 'Voice input needs your agreement first.'})
        self.env['ir.config_parameter'].sudo().set_param(VOICE_FLAG, False)
        out = self.Conv.rpc_transcribe_voice(AUDIO)
        self.assertEqual(out, {'error': 'Voice input is switched off for this database.'})
        self.assertFalse(self.speech.calls)

    def test_voice_status(self):
        status = self.Conv.rpc_voice_status()
        self.assertTrue(status['ask'] and status['switch_on'] and status['provider_ready'])
        # Owner ruling 2026-10-15: no consent card, so no card copy is sent.
        for gone in ('consent_title', 'consent_body', 'consent_yes', 'consent_no'):
            self.assertNotIn(gone, status['copy'])
        self.assertEqual(status['copy']['tap_hint'], 'Tap to speak')
        self.env['payroll.ai.consent'].with_user(self.user).set_voice(False)
        status = self.Conv.rpc_voice_status()
        self.assertFalse(status['available'] or status['ask'])
        # "Use my voice" can still bring it back: the switch and the service are there.
        self.assertTrue(status['switch_on'] and status['provider_ready'])
        # Q5: a past yes is kept as it is — no new consent field, no re-ask.
        self.env['payroll.ai.consent'].with_user(self.user).set_voice(True)
        self.assertNotIn('copy_version', self.env['payroll.ai.consent']._fields)
        self.assertTrue(self.Conv.rpc_voice_status()['available'])

    # ---------------------------------------------------------------- 3.3
    def test_3_3_the_provider_logs_counts_only(self):
        said = 'Give Lan Nguyen a meal allowance of 500,000'
        calls = []

        class _Tr:
            def create(self, **kw):
                calls.append(kw)
                return type('R', (), {'text': said})()

        client = type('C', (), {'audio': type('A', (), {'transcriptions': _Tr()})()})()
        prov = OpenAIProvider.__new__(OpenAIProvider)
        with patch.object(OpenAIProvider, '_get_client', lambda self_: client):
            with self.assertLogs('odoo.addons.pb_payroll_ai_insights.ai_providers.openai_provider',
                                 level=logging.DEBUG) as cap:
                self.assertEqual(prov.transcribe_audio(b'x' * 99), said)
        joined = '\n'.join(cap.output)
        for piece in ('Lan', 'Nguyen', '500,000'):
            self.assertNotIn(piece, joined)
        self.assertIn('99 bytes', joined)
        self.assertNotIn('language', calls[-1])
