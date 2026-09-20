# -*- coding: utf-8 -*-
"""Renaming a component code without stranding anything that answered to it.

The generator itself is covered without a database in `test_component_code.py`.
What is exercised here is the part that can lose money: `hr.contract.advantage.template`
is global and matched by STRING, so a rename that forgets it mints a SECOND template,
leaves every recorded contract line filed under the old one, and the amounts quietly
read 0 with nothing on screen to say why. Everything below exists to make that
impossible — and to prove that the archive of what was already computed is left
truthful rather than retro-fitted.
"""

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


@tagged('post_install', '-at_install')
class TestCodeRename(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env['hr.formula.rule']
        cls.Template = cls.env['hr.contract.advantage.template']
        # CR19: country_code is required with no default — a bare create dies at
        # INSERT time.
        cls.config = cls.env['hr.formula.config'].create({
            'name': 'MAPFIX rename probe',
            'code': 'MAPFIXRENAME',
            'country_code': 'VN',
            'state': 'active',
        })
        cls.basic = cls._rule('Basic salary', 'BASIC', 10, 'input')
        cls.allow = cls._rule('Housing allowance', 'HOUSINGALLOW', 20, 'input')
        cls.gross = cls._rule('Gross pay', 'GROSSPAY', 30, 'formula', '=A1+B1')

    @classmethod
    def _rule(cls, name, code, sequence, column_type='input', formula=''):
        return cls.env['hr.formula.rule'].create({
            'config_id': cls.config.id,
            'name': name,
            'code': code,
            'column_type': column_type,
            'excel_formula': formula,
            'sequence': sequence,
        })

    def _contract_with_component(self, code, amount=1500.0):
        """A contract carrying a recorded value under `code`.

        CR18: om's `hr.contract.create` seeds one EMPTY advantage line per template
        on every contract, so the line usually already exists — what matters is the
        one carrying a value.
        """
        template = self.Template.create({
            'name': 'Housing allowance', 'code': code,
            'lower_bound': 0.0, 'upper_bound': 0.0, 'default_value': 0.0,
        })
        employee = self.env['hr.employee'].create({'name': 'MAPFIX probe'})
        contract = self.env['hr.contract'].create({
            'name': 'MAPFIX probe contract',
            'employee_id': employee.id,
            'wage': 10000.0,
            'state': 'open',
            'resource_calendar_id': self.env.company.resource_calendar_id.id,
            'type_id': self.env['hr.contract.type'].search([], limit=1).id
            or self.env['hr.contract.type'].create({'name': 'MAPFIX type'}).id,
        })
        line = contract.advantages_ids.filtered(
            lambda a: a.advantage_template_id == template)[:1]
        if not line:
            line = self.env['hr.contract.advantage'].create({
                'contract_id': contract.id, 'advantage_template_id': template.id})
        line.amount = amount
        return template, contract, line

    # 10 -----------------------------------------------------------------
    def test_10_template_follows_the_rename_and_the_value_survives(self):
        template, contract, line = self._contract_with_component('HOUSINGALLOW')
        self.allow.is_contract_component = True

        result = self.allow._rename_code('HOUSEALLOW')
        self.assertTrue(result['ok'], result.get('msg'))
        self.assertTrue(result['renamed_template'])

        self.assertEqual(template.code, 'HOUSEALLOW',
                         'the contract component must follow the column it belongs to')
        self.assertEqual(line.advantage_template_id, template,
                         'the recorded line stays on the same template (it is an FK)')
        line.invalidate_recordset(['advantage_template_code'])
        self.assertEqual(line.advantage_template_code, 'HOUSEALLOW')
        self.assertEqual(line.amount, 1500.0)

        # And the value still reaches the engine under the new name — the thing
        # that actually breaks when a rename goes wrong.
        batch = self.env['hr.payroll.import.batch'].new({
            'formula_config_id': self.config.id,
        })
        advantage_map = batch._get_contract_advantage_map(contract)
        self.assertIn('HOUSEALLOW', advantage_map)
        self.assertNotIn('HOUSINGALLOW', advantage_map)

        self.assertEqual(
            self.Template.search_count([('code', 'in', ('HOUSINGALLOW', 'HOUSEALLOW'))]), 1,
            'exactly one template — a forgotten rename mints a second one')

    # 11 -----------------------------------------------------------------
    def test_11_rename_refuses_to_merge_two_contract_components(self):
        self._contract_with_component('HOUSINGALLOW')
        occupied = self.Template.create({
            'name': 'Something else entirely', 'code': 'HOUSEALLOW',
            'lower_bound': 0.0, 'upper_bound': 0.0, 'default_value': 0.0,
        })

        result = self.allow._rename_code('HOUSEALLOW')
        self.assertFalse(result['ok'])
        self.assertIn('HOUSEALLOW', result['msg'])
        self.assertEqual(self.allow.code, 'HOUSINGALLOW', 'nothing moved')
        self.assertEqual(occupied.name, 'Something else entirely')

    # 11b ----------------------------------------------------------------
    def test_11b_rename_refuses_when_another_structure_shares_the_component(self):
        self._contract_with_component('HOUSINGALLOW')
        other = self.env['hr.formula.config'].create({
            'name': 'MAPFIX sibling', 'code': 'MAPFIXSIB',
            'country_code': 'VN', 'state': 'active',
        })
        self.env['hr.formula.rule'].create({
            'config_id': other.id, 'name': 'Housing allowance',
            'code': 'HOUSINGALLOW', 'column_type': 'input', 'sequence': 10,
        })

        result = self.allow._rename_code('HOUSEALLOW')
        self.assertFalse(result['ok'], 'a shared contract component may not move alone')
        self.assertIn('MAPFIX sibling', result['msg'])

        # …unless every structure carrying it moves together, which is what the
        # upgrade migration does.
        sibling = self.Rule.search([('code', '=', 'HOUSINGALLOW'),
                                    ('config_id', '=', other.id)])
        result = self.allow._rename_code('HOUSEALLOW', siblings_renamed=sibling.ids)
        self.assertTrue(result['ok'], result.get('msg'))
        result = sibling._rename_code('HOUSEALLOW', siblings_renamed=self.allow.ids)
        self.assertTrue(result['ok'], result.get('msg'))
        self.assertEqual(
            self.Template.search_count([('code', '=', 'HOUSEALLOW')]), 1)

    # 12 -----------------------------------------------------------------
    def test_12_payslip_history_keeps_the_code_it_was_computed_under(self):
        _tmpl, contract, _adv = self._contract_with_component('HOUSINGALLOW')
        payslip = self.env['hr.payslip'].create({
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'name': 'MAPFIX history slip',
        })
        payslip.formula_computed_values = '{"HOUSINGALLOW": 1500.0}'
        # A payslip line is not a free-form row: om_hr_payroll refuses one with no
        # contract, and the table itself refuses a null category or salary rule.
        # That rigidity is the archive this test says must not be rewritten.
        category = self.env['hr.salary.rule.category'].search([], limit=1)
        salary_rule = self.env['hr.salary.rule'].create({
            'name': 'Housing allowance (history)', 'code': 'HOUSEHIST',
            'category_id': category.id, 'sequence': 100,
        })
        line = self.env['hr.payslip.line'].create({
            'slip_id': payslip.id, 'name': 'Housing allowance',
            'contract_id': contract.id, 'employee_id': contract.employee_id.id,
            'category_id': category.id, 'salary_rule_id': salary_rule.id,
            'code': 'HOUSINGALLOW', 'amount': 1500.0, 'quantity': 1.0, 'rate': 100.0,
        })

        self.assertTrue(self.allow._rename_code('HOUSEALLOW')['ok'])

        self.assertEqual(line.code, 'HOUSINGALLOW',
                         'a payslip records what was computed, not what things are '
                         'called now')
        self.assertIn('HOUSINGALLOW', payslip.formula_computed_values)
        self.assertNotIn('HOUSEALLOW', payslip.formula_computed_values)

    # 13 -----------------------------------------------------------------
    def test_13_batch_rename_is_all_or_nothing(self):
        if 'pb.formula.studio' not in self.env:
            self.skipTest('Formula Studio is not installed on this database.')
        Studio = self.env['pb.formula.studio']
        before = {r.id: r.code for r in self.config.rule_ids}

        bad = Studio.rename_components(self.config.id, [
            {'rule_id': self.basic.id, 'new_code': 'BASEPAY'},
            {'rule_id': self.allow.id, 'new_code': 'HOUSE_ALLOW'},   # underscore
        ])
        self.assertFalse(bad['ok'])
        self.assertEqual({r.id: r.code for r in self.config.rule_ids}, before,
                         'one bad pair leaves the whole set untouched')

        clash = Studio.rename_components(self.config.id, [
            {'rule_id': self.basic.id, 'new_code': 'SAMENAME'},
            {'rule_id': self.allow.id, 'new_code': 'SAMENAME'},
        ])
        self.assertFalse(clash['ok'])
        self.assertEqual({r.id: r.code for r in self.config.rule_ids}, before)

        onto_a_keeper = Studio.rename_components(self.config.id, [
            {'rule_id': self.basic.id, 'new_code': 'GROSSPAY'},
        ])
        self.assertFalse(onto_a_keeper['ok'])
        self.assertEqual({r.id: r.code for r in self.config.rule_ids}, before)

        good = Studio.rename_components(self.config.id, [
            {'rule_id': self.basic.id, 'new_code': 'BASEPAY'},
            {'rule_id': self.allow.id, 'new_code': 'HOUSEALLOW'},
        ])
        self.assertTrue(good['ok'], good.get('msg'))
        self.assertEqual(good['renamed'], 2)
        self.assertEqual(self.basic.code, 'BASEPAY')
        self.assertEqual(self.allow.code, 'HOUSEALLOW')

    # 13b ----------------------------------------------------------------
    def test_13b_batch_orders_a_chain_and_refuses_a_cycle(self):
        if 'pb.formula.studio' not in self.env:
            self.skipTest('Formula Studio is not installed on this database.')
        Studio = self.env['pb.formula.studio']
        chain = Studio.rename_components(self.config.id, [
            {'rule_id': self.basic.id, 'new_code': 'HOUSINGALLOW'},
            {'rule_id': self.allow.id, 'new_code': 'HOUSEALLOW'},
        ])
        self.assertTrue(chain['ok'], chain.get('msg'))
        self.assertEqual(self.basic.code, 'HOUSINGALLOW')
        self.assertEqual(self.allow.code, 'HOUSEALLOW')

        cycle = Studio.rename_components(self.config.id, [
            {'rule_id': self.basic.id, 'new_code': 'HOUSEALLOW'},
            {'rule_id': self.allow.id, 'new_code': 'HOUSINGALLOW'},
        ])
        self.assertFalse(cycle['ok'])
        self.assertEqual(self.basic.code, 'HOUSINGALLOW', 'nothing moved')

    # 14 -----------------------------------------------------------------
    def test_14_shape_constraint(self):
        with self.assertRaises(ValidationError):
            self._rule('Social insurance', 'SI_EMP', 40)
        with self.assertRaises(ValidationError):
            self.basic.write({'code': 'BASIC PAY'})
        with self.assertRaises(ValidationError):
            self.basic.write({'code': '1BASIC'})
        # Shape only — a substring of another code is legal, because the converter
        # resolves it correctly (maximal munch, conventions C13).
        ok = self._rule('Social insurance', 'SIEMP', 40)
        self.assertEqual(ok.code, 'SIEMP')
        also_ok = self._rule('Social insurance total', 'SIEMPTOTAL', 50)
        self.assertEqual(also_ok.code, 'SIEMPTOTAL')

    # 15 -----------------------------------------------------------------
    def test_15_migration_is_idempotent(self):
        import importlib.util
        import os

        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, 'migrations', '19.0.1.69.0',
                            'post-codes_become_readable.py')
        spec = importlib.util.spec_from_file_location('mapfix_a_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        ugly = self._rule('Chi trả phép năm chưa sử dụng', 'CHITRPHPNMCHASDNG', 60)
        self.assertFalse(migration._conforms(ugly.code))

        proposals = migration._propose(self.config)
        self.assertIn(ugly.id, proposals)
        self.assertNotIn(self.basic.id, proposals,
                         'a code that already reads well is never touched')
        self.assertTrue(len(proposals[ugly.id]) <= 12)

        self.assertTrue(ugly._rename_code(proposals[ugly.id])['ok'])
        second_pass = migration._propose(self.config)
        self.assertEqual(second_pass, {},
                         'a second run of the upgrade must change nothing')

    # 16 -----------------------------------------------------------------
    def test_16_salary_rule_and_sample_vectors_follow(self):
        salary_rule = self.env['hr.salary.rule'].create({
            'name': 'Housing allowance', 'code': 'HOUSINGALLOW',
            'category_id': self.env['hr.salary.rule.category'].search([], limit=1).id,
            'sequence': 100,
        })
        self.allow.salary_rule_id = salary_rule.id
        sample = self.env['hr.formula.sample.data'].create({
            'config_id': self.config.id,
            'name': 'MAPFIX sample',
            'input_values_json': '{"HOUSINGALLOW": 42.0}',
        })

        self.assertTrue(self.allow._rename_code('HOUSEALLOW')['ok'])
        self.assertEqual(salary_rule.code, 'HOUSEALLOW')
        self.assertIn('HOUSEALLOW', sample.input_values_json)
        self.assertNotIn('HOUSINGALLOW', sample.input_values_json)
