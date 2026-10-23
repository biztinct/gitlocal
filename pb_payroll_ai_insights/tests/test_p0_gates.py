# -*- coding: utf-8 -*-
"""PAYAI P0 — three small rails in the assistant.

1. Pulse alerts are read with the reader's rights, not the detector's sudo.
2. The Anthropic provider keeps every system turn (product prompt + screen note).
3. The chat never picks a document-OCR engine as its configuration.
"""
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.pb_payroll_ai_insights.tests.common import payai_group_ids


class _FakeMessages:
    def __init__(self, sink):
        self.sink = sink

    def create(self, **kw):
        self.sink.append(kw)

        class _Block:
            type = 'text'
            text = '{"response": "ok"}'

        class _Resp:
            content = [_Block()]
        return _Resp()


class _FakeClient:
    def __init__(self, sink):
        self.messages = _FakeMessages(sink)


@tagged('post_install', '-at_install')
class TestP0Gates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        # Both hold PayAI (a role since 2026-10-20): what differs between them
        # is the payslip right the pulse test is about.
        payai = payai_group_ids(cls.env)
        cls.plain = Users.create({
            'name': 'P0 plain user', 'login': 'p0.plain@test.invalid',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id] + payai)]})
        cls.manager = Users.create({
            'name': 'P0 payroll manager', 'login': 'p0.manager@test.invalid',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('om_hr_payroll.group_hr_payroll_manager').id] + payai)]})

    # ------------------------------------------------------------ 1. pulse
    def test_pulse_alerts_follow_the_readers_payslip_right(self):
        Pulse = self.env['payroll.ai.pulse']
        Pulse.create({'name': 'P0 probe alert', 'severity': 'critical',
                      'category': 'cost', 'summary': 'Retail +40%',
                      'state': 'new'})
        for user in (self.plain, self.manager):
            may_read = self.env['hr.payslip'].with_user(user).has_access('read')
            got = Pulse.with_user(user).rpc_get_active_alerts()
            if may_read:
                self.assertTrue(any(a['name'] == 'P0 probe alert' for a in got),
                                '%s may read payslips but saw no alert' % user.login)
            else:
                self.assertEqual(got, [], '%s may not read payslips but saw alerts'
                                 % user.login)
        # the manager is the positive branch; make sure it was exercised
        self.assertTrue(self.env['hr.payslip'].with_user(self.manager)
                        .has_access('read'))

    # -------------------------------------------------------- 2. anthropic
    def test_anthropic_keeps_every_system_turn(self):
        from odoo.addons.pb_payroll_ai_insights.ai_providers.anthropic_provider \
            import AnthropicProvider
        sink = []
        provider = AnthropicProvider({'api_key': 'x', 'model_name': 'm'})
        provider._client = _FakeClient(sink)
        provider.generate_chat([
            {'role': 'system', 'content': 'PRODUCT FACTS'},
            {'role': 'system', 'content': 'The user is on Pay › Runs'},
            {'role': 'user', 'content': 'hi'},
        ])
        self.assertEqual(len(sink), 1)
        self.assertIn('PRODUCT FACTS', sink[0]['system'])
        self.assertIn('Pay › Runs', sink[0]['system'])
        self.assertEqual([m['role'] for m in sink[0]['messages']], ['user'])

    # ----------------------------------------------------------- 3. config
    def test_chat_config_never_picks_the_ocr_engine(self):
        Cfg = self.env['payroll.ai.config']
        Cfg.search([]).write({'is_active': False})
        ocr = Cfg.create({'provider_type': 'tesseract',
                          'purpose': 'doc_ocr', 'is_active': True,
                          'company_id': self.env.company.id})
        self.assertNotEqual(Cfg.get_active_config(), ocr)
        chat = Cfg.create({'provider_type': 'openai',
                           'purpose': 'insights', 'is_active': True,
                           'api_key': 'k', 'company_id': self.env.company.id})
        self.assertEqual(Cfg.get_active_config(), chat)
