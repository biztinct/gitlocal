# -*- coding: utf-8 -*-
"""ONECHAT OC2 (handover §5.5) — the helper's language pill decides the
language PayAI answers in.

The one chat sends the pill as `context.lang` on every send; none of the
prompt templates said which language to answer in, so a person reading the
drawer in Vietnamese got whatever the model guessed from the question. Every
system prompt now ends with one line when `env.lang` is Vietnamese, and only
then — English stays the default the templates were written for.
"""
from odoo.tests import TransactionCase, tagged

from ..models.payroll_ai_engine import (
    ONBOARDING_SYSTEM_PROMPT,
    PAYAI_SYSTEM_PROMPT,
    VI_ANSWER_LINE,
)


@tagged('post_install', '-at_install', 'onechat')
class TestOneChatAnswerLanguage(TransactionCase):

    def _vi_engine(self):
        # `env.lang` only keeps a language this database has switched on.
        if not self.env['res.lang'].search([('code', '=', 'vi_VN')], limit=1):
            self.skipTest('Vietnamese is not switched on in this database')
        return self.env['payroll.ai.engine'].with_context(lang='vi_VN')

    def test_01_vietnamese_readers_are_answered_in_vietnamese(self):
        engine = self._vi_engine()
        self.assertTrue(str(engine.env.lang).startswith('vi'))
        for template in (PAYAI_SYSTEM_PROMPT, ONBOARDING_SYSTEM_PROMPT):
            prompt = engine._system_prompt(template)
            self.assertTrue(prompt.endswith(VI_ANSWER_LINE))
            self.assertIn('Answer in Vietnamese', prompt)

    def test_02_english_readers_get_the_prompt_as_written(self):
        engine = self.env['payroll.ai.engine'].with_context(lang='en_US')
        for template in (PAYAI_SYSTEM_PROMPT, ONBOARDING_SYSTEM_PROMPT):
            self.assertNotIn('Answer in Vietnamese', engine._system_prompt(template))

    def test_03_the_line_keeps_json_answers_parseable(self):
        """The data path asks for JSON; the line must not ask for its keys
        to be translated."""
        self.assertIn('keep JSON keys', VI_ANSWER_LINE)
        self.assertNotRegex(VI_ANSWER_LINE, r'(?i)odoo')
