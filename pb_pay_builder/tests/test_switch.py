from pathlib import Path

import polib
from odoo.tests import TransactionCase, new_test_user, tagged

from .common import make_scheme


@tagged('post_install', '-at_install', 'paybuilder', 'paybuilder_switch')
class TestSwitch(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co = cls.env['res.company'].create({'name': 'DEMO Switch', 'country_id': cls.env.ref('base.vn').id})
        cls.studio = cls.env['pb.formula.studio'].with_company(cls.co)
        cls.builder = cls.studio.env['pb.pay.builder']
        cls.scheme = make_scheme(cls.studio.env, cls.co, 'WAGE')
        cls.other = make_scheme(cls.studio.env, cls.co, 'SIMPLE')
        cls.rule = {rule.code: rule for rule in cls.scheme.rule_ids}
        cls.team = cls.studio.env['hr.department'].create({'name': 'DEMO Switch Team', 'company_id': cls.co.id})
        cls.studio.env['hr.formula.scheme.assignment'].create({'config_id': cls.scheme.id, 'department_id': cls.team.id,
            'company_id': cls.co.id, 'cycle_type': 'any'})
        cls.manager = new_test_user(cls.env, login='demo_switch_manager',
            groups='base.group_user,hr.group_hr_user,pb_hr_payroll_formula.group_formula_manager',
            company_id=cls.co.id, company_ids=[(6, 0, cls.co.ids)])
        cls.reader = new_test_user(cls.env, login='demo_switch_reader',
            groups='base.group_user,pb_hr_payroll_formula.group_formula_user',
            company_id=cls.co.id, company_ids=[(6, 0, cls.co.ids)])

    def contracts(self, count):
        env = self.studio.env
        people = env['hr.employee'].create([{'name': 'DEMO Switch %02d' % i,
            'department_id': self.team.id, 'company_id': self.co.id} for i in range(count)])
        kind = env['hr.contract.type'].search([], limit=1)
        calendar = self.co.resource_calendar_id or env['resource.calendar'].create({'name':'DEMO Switch Hours', 'company_id':self.co.id})
        return env['hr.contract'].with_context(pb_skip_fill_in=True).create([
            {'name': p.name, 'employee_id': p.id, 'date_start': '2020-01-01', 'wage': 1000000,
             'company_id': self.co.id, 'state':'open', 'resource_calendar_id':calendar.id,
             'type_id':kind.id} for p in people])

    def test_35_switch_on_people_without_amount(self):
        contracts = self.contracts(23)
        rule = self.rule['OT']
        env = self.studio.env
        env['pb.person.scheme'].create({'employee_id':contracts[-1].employee_id.id, 'config_id':self.other.id,
                                      'date_from':'2020-01-01','source':'hire'})
        template = env['hr.contract.advantage.template'].template_for_rule(rule)
        env['hr.contract.advantage'].create({'contract_id': contracts[0].id, 'advantage_template_id':template.id,'amount':0})
        a = self.builder.with_user(self.manager).switch_preview(rule.id, True)
        self.assertEqual(a['count'], 21, a)
        self.assertEqual(len(a['names']), 20)
        self.assertNotIn(contracts[0].employee_id.name, a['names'])
        self.assertFalse(rule.is_contract_component)

    def test_36_switch_off_keeps_amount(self):
        contract = self.contracts(2)[0]
        rule = self.rule['LUNCH']
        template = self.studio.env['hr.contract.advantage.template'].template_for_rule(rule)
        line = self.studio.env['hr.contract.advantage'].create({'contract_id':contract.id, 'advantage_template_id':template.id,'amount':0})
        a = self.builder.switch_preview(rule.id, False)
        self.assertEqual(a['count'], 1)
        self.assertTrue(a['warning'])
        self.assertTrue(line.exists())

    def test_37_no_people_no_warning(self):
        a = self.builder.switch_preview(self.rule['OT'].id, True)
        self.assertTrue(a['ok'])
        self.assertFalse(a['warning'])
        self.assertEqual(a['count'], 0)

    def test_38_editor_changes_the_source(self):
        r = self.rule['OT']
        for personal, kind in ((True,'set'), (False,'each')):
            studio = self.studio.with_user(self.manager)
            draft = studio.get_component_edit(r.id)
            draft['is_contract_component'] = personal
            result = studio.save_component(r.id, draft)
            self.assertTrue(result.get('ok'), result)
            self.assertEqual(next(x['kind'] for x in self.scheme._pbpb_layout()['rows'] if x['code']=='OT'),kind)

    def test_39_period_and_main(self):
        studio = self.studio.with_user(self.manager)
        r = self.rule['LUNCH']
        self.assertTrue(studio.save_component(r.id, {'pbpb_period':'year'})['ok'])
        self.assertEqual(studio.get_component_edit(r.id)['pbpb_period'], 'year')
        for code in ('LUNCH', 'PHONE'):
            result=studio.save_config_settings(self.scheme.id, {'pbpb_main_rule_id':self.rule[code].id})
            self.assertTrue(result.get('ok'),result)
            self.assertEqual(self.scheme._pbpb_layout()['head']['code'],code)
        self.assertTrue(studio.save_component(self.rule['PHONE'].id, {'is_contract_component':False})['ok'])
        self.assertFalse(self.scheme.pbpb_main_rule_id)

    def test_40_formula_and_constant(self):
        for code in ('PIT', 'CAP'):
            r = self.rule[code]
            self.assertFalse(self.builder.switch_preview(r.id,True)['ok'])
            self.assertFalse(self.studio.save_component(r.id,{'is_contract_component':True})['ok'])

    def test_41_gate(self):
        r = self.rule['PHONE']
        self.assertFalse(self.builder.with_user(self.reader).switch_preview(r.id,False)['ok'])
        self.assertFalse(self.studio.with_user(self.reader).save_component(r.id,{'is_contract_component':False})['ok'])
        self.assertFalse(self.studio.with_user(self.reader).save_config_settings(self.scheme.id,{'pbpb_main_rule_id':r.id})['ok'])
        manager = self.studio.with_user(self.manager)
        self.assertTrue(self.builder.with_user(self.manager).switch_preview(r.id,False)['ok'])
        settings = manager.get_config_settings(self.scheme.id)
        self.assertIn(r.id, [choice['id'] for choice in settings['pbpb_choices']])
        self.assertFalse(settings['meta']['journals'])

    def test_42_words(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('pb_pay_builder.pot','vi_VN.po','id_ID.po'):
            po=polib.pofile(str(root/'i18n'/name))
            for msg in ('The same for this person every month','It changes each month','Main pay amount','Typed per'):
                self.assertTrue(po.find(msg))
        self.assertIn('Contract component', (root.parent/'pb_formula_studio/i18n/vi_VN.po').read_text())
