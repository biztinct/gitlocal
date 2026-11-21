# -*- coding: utf-8 -*-
"""S6-B item 5 / ruling E5 — PayAI for employees, model level (P1–P14)."""
import base64
import json
import os
import re
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from .common import FakeProvider, make_world, stub


@tagged('post_install', '-at_install', 'wdgap_s6b')
class TestPolicyAnswer(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_world(cls, 'wdgap_s6b_pa')

    def _ask(self, question, fake=None):
        fake = fake or FakeProvider()
        with stub(self.env, fake):
            res = self.Answer.with_user(self.share).sudo().ask(self.emp, question)
        return res, fake

    # P1 — off by default, on a fresh company
    def test_p01_off_by_default(self):
        fresh = self.env['res.company'].create({'name': 'DEMO S6B Fresh Co'})
        self.assertFalse(fresh.pb_policy_ai_on)
        emp = self.env['hr.employee'].create({'name': 'DEMO S6B Fresh', 'company_id': fresh.id})
        self.assertFalse(self.Answer._ready_for(emp))

    # P2 — switched on, but no AI account: HR sees "not set up", employee nothing
    def test_p02_not_set_up(self):
        self.config.write({'is_active': False})
        self.assertFalse(self.Answer._ready_for(self.emp))
        desk = self.env['pb.policy.desk'].with_user(self.hr).get_desk()
        self.assertFalse(desk['ready'])
        res, fake = self._ask('How many days of wedding leave do I get?')
        self.assertEqual(res['state'], 'not_ready')
        self.assertFalse(fake.calls)

    # P3 — another company's AI account is never borrowed
    def test_p03_never_another_companys_account(self):
        other = self.env['res.company'].create({'name': 'DEMO S6B Other Co'})
        self.config.write({'company_id': other.id})
        self.assertFalse(self.Answer._config(self.company))
        self.assertFalse(self.Answer._ready_for(self.emp))

    # P4 — a document-reading engine, or a keyed provider without a key, is
    # not an AI account for answers
    def test_p04_unusable_accounts(self):
        self.config.write({'provider_type': 'tesseract'})
        self.assertFalse(self.Answer._config(self.company))
        self.config.write({'provider_type': 'openai', 'api_key': False})
        self.assertFalse(self.Answer._config(self.company))
        self.config.write({'provider_type': 'ollama', 'purpose': 'insights'})
        self.assertEqual(self.Answer._config(self.company), self.config,
                         'P4: the company\'s own PayAI account is used when it has no separate one')

    # P5 — the file is read into sections at its headings
    def test_p05_sections_and_search(self):
        self.assertGreaterEqual(self.doc.section_count, 3)
        heads = self.doc.section_ids.mapped('heading')
        self.assertIn('2. Wedding leave', heads)
        found = self.Answer._search(self.emp, 'How many days of wedding leave do I get?')
        self.assertTrue(found)
        self.assertEqual(found[0].heading, '2. Wedding leave')
        self.assertFalse(self.Answer._search(self.emp, 'parking space bicycle'))

    # P6 — answered from a policy, and says which one
    def test_p06_answered_with_source(self):
        res, fake = self._ask('How many days of wedding leave do I get?')
        self.assertEqual(res['state'], 'answered')
        self.assertIn('3 days of paid wedding leave', str(res['answer']))
        self.assertEqual(res['sources'][0]['title'], 'DEMO Staff handbook')
        self.assertEqual(res['sources'][0]['section'], '2. Wedding leave')
        self.assertEqual(len(fake.calls), 1)
        log = self.env['pb.policy.question'].sudo().search(
            [('company_id', '=', self.company.id)], limit=1)
        self.assertEqual(log.outcome, 'answered')
        self.assertTrue(log.called_ai)
        self.assertEqual(log.document_ids, self.doc)
        self.assertEqual(log.section_id.heading, '2. Wedding leave')
        self.assertIn('wedding leave', log.question)

    # P7 — not in the files: said so, and the AI account is not even asked
    def test_p07_not_in_the_files(self):
        res, fake = self._ask('Where do I park my bicycle?')
        self.assertEqual(res['state'], 'not_found')
        self.assertFalse(fake.calls, 'P7: no match, no call')
        res, fake = self._ask('How many days of wedding leave?', FakeProvider(reply='NO_ANSWER'))
        self.assertEqual(res['state'], 'not_found')
        self.assertEqual(len(fake.calls), 1)

    # P8 — PRIVACY: only the question (scrubbed) and policy words leave
    def test_p08_egress_only_question_and_excerpts(self):
        question = ('Hi, I am Trần Thị DEMO Lụa, my phone is +84 912 345 678 and my '
                    'email demo.lua.s6b@example.com. Phạm Văn DEMO Quang told me I get '
                    'wedding leave. How many days of wedding leave do I get?')
        res, fake = self._ask(question)
        self.assertEqual(res['state'], 'answered')
        messages = fake.calls[0]['messages']
        self.assertEqual([set(m) for m in messages], [{'role', 'content'}] * 2)
        wire = json.dumps(messages, ensure_ascii=False)
        wire_folded = wire.lower()
        for secret in ('Trần Thị DEMO Lụa', 'Lụa', 'Phạm Văn DEMO Quang',
                       'demo.lua.s6b@example.com', '912 345 678', self.share.login,
                       'DEMO Forklift driver', 'DEMO S6B Warehouse', self.company.name):
            self.assertNotIn(secret.lower(), wire_folded, 'P8: %s left the system' % secret)
        self.assertIn('wedding leave', wire_folded, 'the question itself goes')
        self.assertIn('3 days of paid wedding leave', wire, 'the policy excerpt goes')
        self.assertIn('[person-', wire, 'names were replaced, not dropped')
        self.assertNotIn('employee', [k for m in messages for k in m])

    # P9 — the daily limits, per person and per company
    def test_p09_daily_limits(self):
        self.company.write({'pb_policy_ai_person_day': 2})
        for _n in range(2):
            res, _fake = self._ask('How many days of wedding leave?')
            self.assertEqual(res['state'], 'answered')
        res, fake = self._ask('How many days of wedding leave?')
        self.assertEqual(res['state'], 'limit_person')
        self.assertFalse(fake.calls, 'P9: over the limit, no call')
        self.company.write({'pb_policy_ai_person_day': 50, 'pb_policy_ai_company_day': 2})
        res, fake = self._ask('How many days of wedding leave?')
        self.assertEqual(res['state'], 'limit_company')
        self.assertFalse(fake.calls)

    # P10 — the AI account failing is a calm answer, never an error
    def test_p10_failure_is_calm(self):
        res, _fake = self._ask('How many days of wedding leave?',
                               FakeProvider(error=RuntimeError('down')))
        self.assertEqual(res['state'], 'failed')

    # P11 — no personal figures: no payslip, leave or contract is read
    def test_p11_never_reads_personal_records(self):
        guarded = []
        # (hr.version is not guarded: on this build the person's OWN
        # department is stored there, and the audience check reads it.)
        for model in ('hr.payslip', 'hr.leave', 'hr.leave.allocation',
                      'hr.contract', 'payroll.ai.conversation'):
            if model in self.env:
                guarded.append(patch.object(type(self.env[model]), '_search',
                                            side_effect=AssertionError('read %s' % model)))
        for g in guarded:
            g.start()
        try:
            res, _fake = self._ask('How many days of annual leave do I get each year?')
        finally:
            for g in guarded:
                g.stop()
        self.assertEqual(res['state'], 'answered')
        root = get_module_path('pb_me_payai') + '/models'
        for name in os.listdir(root):
            if name.endswith('.py'):
                with open(os.path.join(root, name), encoding='utf-8') as fh:
                    code = re.sub(r'(?s)""".*?"""', '', fh.read())
                for forbidden in ("env['hr.payslip", "env['hr.leave", 'payroll_ai_engine',
                                  'payroll_data_query', "env['hr.contract"):
                    self.assertNotIn(forbidden, code, '%s uses %s' % (name, forbidden))

    # P12 — department audience
    def test_p12_department_audience(self):
        self.doc.write({'department_ids': [(6, 0, self.dept_other.ids)]})
        self.assertFalse(self.Answer._ready_for(self.emp))
        self.doc.write({'department_ids': [(6, 0, (self.dept | self.dept_other).ids)]})
        self.assertTrue(self.Answer._ready_for(self.emp))

    # P13 — the HR desk: who may do what
    def test_p13_desk_gates(self):
        Desk = self.env['pb.policy.desk']
        with self.assertRaises(AccessError):
            Desk.with_user(self.plain).get_desk()
        with self.assertRaises(AccessError):
            Desk.with_user(self.share).get_desk()
        d = Desk.with_user(self.hr).get_desk()
        self.assertTrue(d['ready'])
        self.assertFalse(d['can_switch'])
        with self.assertRaises(AccessError):
            Desk.with_user(self.hr).set_switch(False)
        up = Desk.with_user(self.hr).upload('DEMO Travel policy', 'travel.txt',
                                            base64.b64encode(b'Travel\nTaxis are paid back with a receipt.').decode())
        self.assertIn('sections', up['note'])
        new = self.env['pb.policy.document'].search([('name', '=', 'DEMO Travel policy')])
        self.assertFalse(new.published, 'P13: a new file is private until published')
        with self.assertRaises(UserError):
            Desk.with_user(self.hr).upload('DEMO Bad', 'virus.exe', 'AAAA')
        d = Desk.with_user(self.hr_manager).set_switch(False)
        self.assertFalse(d['on'])
        Desk.with_user(self.hr_manager).set_limits(3, 30)
        self.assertEqual(self.company.pb_policy_ai_person_day, 3)
        with self.assertRaises(UserError):
            Desk.with_user(self.hr_manager).set_limits(-1, 30)
        self.assertEqual(d['usage']['today']['all'], 0)

    def test_p13b_scan_without_words_cannot_be_published(self):
        Desk = self.env['pb.policy.desk']
        up = Desk.with_user(self.hr).upload('DEMO Scan', 'scan.pdf',
                                            base64.b64encode(b'%PDF-1.4 not really a pdf').decode())
        self.assertIn('No words could be read', up['note'])
        doc = self.env['pb.policy.document'].search([('name', '=', 'DEMO Scan')])
        with self.assertRaises(UserError):
            Desk.with_user(self.hr).set_published(doc.id, True)

    # P15 — the answer door, reached over RPC, only ever answers for yourself
    def test_p15_never_for_somebody_else(self):
        with self.assertRaises(AccessError):
            self.Answer.with_user(self.plain).ask(self.emp, 'How many days of wedding leave?')
        with self.assertRaises(AccessError):
            self.Answer.with_user(self.plain).ask(self.emp.id, 'How many days?')
        fake = FakeProvider()
        with stub(self.env, fake):
            res = self.Answer.with_user(self.share).ask(self.emp.sudo(), 'How many days of wedding leave?')
        self.assertEqual(res['state'], 'answered', 'the session\'s own record is fine')

    # P14 — HR of another company never sees these files
    def test_p14_company_rule(self):
        other = self.env['res.company'].create({'name': 'DEMO S6B Rule Co'})
        hr_other = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'DEMO S6B HR Other', 'login': 'wdgap_s6b_pa_hr_other',
            'company_id': other.id, 'company_ids': [(6, 0, other.ids)],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('hr.group_hr_user').id])]})
        seen = self.env['pb.policy.document'].with_user(hr_other).with_context(
            allowed_company_ids=other.ids).search([])
        self.assertNotIn(self.doc, seen)
