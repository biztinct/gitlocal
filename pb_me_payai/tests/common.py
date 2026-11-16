# -*- coding: utf-8 -*-
"""Shared fixtures for the S6-B PayAI tests. No real AI call is ever made:
`pb.policy.answer._send` is replaced in every test that asks, and the AI
account row is a local provider kind that needs no key (no key, real or
fake, is written anywhere)."""
import base64
import json

PASSWORD = 'wdgap-s6b-payai-2026'

HANDBOOK = """DEMO Staff handbook
1. Annual leave
Everyone gets 12 days of annual leave each calendar year. Up to 5 unused days carry over to the next year.
2. Wedding leave
When you get married you get 3 days of paid wedding leave. Tell HR two weeks before.
3. Overtime
Overtime must be agreed by your manager before you work it. It is paid at the rate in your contract.
"""


def make_world(cls, prefix, password=None, switch_on=True, config=True):
    env = cls.env
    company = env.company
    Users = env['res.users'].with_context(no_reset_password=True)

    def user(login, name, groups):
        vals = {'name': name, 'login': login, 'email': '%s@example.com' % login,
                'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
                'group_ids': [(6, 0, [env.ref(g).id for g in groups])]}
        if password:
            vals['password'] = password
        return Users.create(vals)

    cls.company = company
    cls.dept = env['hr.department'].create({'name': 'DEMO S6B Warehouse',
                                            'company_id': company.id})
    cls.dept_other = env['hr.department'].create({'name': 'DEMO S6B Shop',
                                                  'company_id': company.id})
    cls.share = user('%s_share' % prefix, 'Trần Thị DEMO Lụa', ['base.group_portal'])
    cls.manager = env['hr.employee'].create({'name': 'Phạm Văn DEMO Quang',
                                             'company_id': company.id})
    cls.emp = env['hr.employee'].create({
        'name': 'Trần Thị DEMO Lụa', 'user_id': cls.share.id, 'company_id': company.id,
        'department_id': cls.dept.id, 'parent_id': cls.manager.id,
        'job_title': 'DEMO Forklift driver', 'work_email': 'demo.lua.s6b@example.com',
        'mobile_phone': '+84 912 345 678'})
    cls.hr = user('%s_hr' % prefix, 'DEMO S6B HR Officer', ['base.group_user', 'hr.group_hr_user'])
    cls.hr_manager = user('%s_hrm' % prefix, 'DEMO S6B HR Manager',
                          ['base.group_user', 'hr.group_hr_manager'])
    cls.plain = user('%s_plain' % prefix, 'DEMO S6B Plain', ['base.group_user'])
    # A company of its own for the tests: no other AI account row of this
    # database can answer for it.
    company.sudo().write({'pb_policy_ai_on': switch_on,
                          'pb_policy_ai_person_day': 10,
                          'pb_policy_ai_company_day': 200})
    Cfg = env['payroll.ai.config'].sudo()
    Cfg.search([('company_id', '=', company.id)]).write({'is_active': False})
    cls.config = Cfg.create({'provider_type': 'ollama', 'purpose': 'policy_answers',
                             'model_name': 'demo-local', 'company_id': company.id,
                             'is_active': True}) if config else Cfg.browse()
    cls.doc = env['pb.policy.document'].sudo().create({
        'name': 'DEMO Staff handbook', 'filename': 'handbook.txt',
        'file': base64.b64encode(HANDBOOK.encode()), 'company_id': company.id,
        'published': True})
    cls.Answer = env['pb.policy.answer']
    return cls


class FakeProvider:
    """Records the exact messages and answers like a provider would."""

    def __init__(self, reply=None, error=None):
        self.calls = []
        self.reply = reply if reply is not None else json.dumps(
            {'answer': 'You get 3 days of paid wedding leave.', 'used': [1]})
        self.error = error

    def __call__(self, model, config, messages):
        self.calls.append({'config': config, 'messages': messages})
        if self.error:
            raise self.error
        return self.reply


def stub(env, fake):
    """Replace THE one egress point for the duration of a `with` block."""
    from unittest.mock import patch
    cls = type(env['pb.policy.answer'])
    return patch.object(cls, '_send', new=lambda self, config, messages: fake(self, config, messages))
