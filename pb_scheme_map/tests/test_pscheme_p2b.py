# -*- coding: utf-8 -*-
"""PSCHEME P2b — the seams this phase added to the scheme map (an ADDED file,
ledger A15), and the pay data file (D).

T13  a person a pay data file creates gets the file's scheme as their own,
     from the first day of the file's period; a person matched by the file
     whose own scheme is another one is NOT changed and is named in the review
     (quiet at zero); an advance file gives the paired end-of-month scheme and
     the advance
T13b `usual_scheme` order: the team only breaks a tie; `r6_words`
T13c the take-back helper refuses after a later change, restores exactly
T16  the formula module still reaches the map only by a soft probe
"""
import ast
import os
from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@tagged('post_install', '-at_install', 'pscheme', 'pscheme_p2b')
class TestPschemeP2bSeams(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        vnd.active = True
        cls.company = cls.env['res.company'].create({'name': 'DEMO PS2B Map Co',
                                                     'currency_id': vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        Config = cls.env['hr.formula.config']

        def scheme(name, code, cycle, country):
            return Config.create({'name': name, 'code': code, 'cycle_type': cycle,
                                  'country_code': country, 'company_id': cls.company.id,
                                  'state': 'active'})
        cls.vn = scheme('DEMO PS2B Map Vietnam', 'DEMOP2BMVN', 'end_cycle', 'VN')
        cls.vn2 = scheme('DEMO PS2B Map Vietnam two', 'DEMOP2BMV2', 'end_cycle', 'VN')
        cls.vn_adv = scheme('DEMO PS2B Map Vietnam advance', 'DEMOP2BMVA', 'mid_cycle', 'VN')
        Rule = cls.env['hr.formula.rule']
        e = Rule.create({'config_id': cls.vn.id, 'code': 'P2BMADVT', 'name': 'DEMO Advance taken',
                         'column_type': 'input', 'sequence': 1})
        m = Rule.create({'config_id': cls.vn_adv.id, 'code': 'P2BMADV', 'name': 'DEMO Advance',
                         'column_type': 'input', 'sequence': 1})
        cls.env['hr.payroll.cycle.component.mapping'].sudo().create({
            'mid_cycle_config_id': cls.vn_adv.id, 'end_cycle_config_id': cls.vn.id,
            'mid_component_id': m.id, 'end_component_id': e.id})
        cls.team = cls.env['hr.department'].create({'name': 'DEMO PS2B Map team',
                                                    'company_id': cls.company.id})
        cls.Row = cls.env['pb.person.scheme'].sudo()

    def batch(self, config):
        return self.env['hr.payroll.import.batch'].create({
            'name': 'DEMO PS2B file', 'source_type': 'excel',
            'formula_config_id': config.id, 'date_from': '2026-12-01',
            'date_to': '2026-12-31', 'company_id': self.company.id})

    def line(self, batch, code, name, employee=None):
        return self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_code': code, 'employee_name': name,
            'state': 'validated', 'employee_id': employee.id if employee else False})

    # ================================================================= T13
    def test_t13_file_joiner_gets_the_files_scheme(self):
        batch = self.batch(self.vn2)
        person = batch._create_employee(self.line(batch, 'P2BF01', 'DEMO PS2B Filed'))
        rows = self.Row.search([('employee_id', '=', person.id)])
        self.assertEqual([(r.config_id, r.date_from, r.source) for r in rows],
                         [(self.vn2, date(2026, 12, 1), 'import')])
        self.assertEqual(person.payroll_country, 'VN')

    def test_t13_advance_file_gives_main_and_advance(self):
        batch = self.batch(self.vn_adv)
        person = batch._create_employee(self.line(batch, 'P2BF02', 'DEMO PS2B Advanced'))
        rows = self.Row.search([('employee_id', '=', person.id)])
        self.assertEqual(rows.config_id, self.vn | self.vn_adv)

    def test_t13_other_own_scheme_is_named_never_changed(self):
        batch = self.batch(self.vn2)
        theirs = self.env['hr.employee'].create({'name': 'DEMO PS2B Own', 'company_id': self.company.id,
                                                 'payroll_country': 'VN'})
        mine = self.env['hr.employee'].create({'name': 'DEMO PS2B Same', 'company_id': self.company.id,
                                               'payroll_country': 'VN'})
        plain = self.env['hr.employee'].create({'name': 'DEMO PS2B Plain', 'company_id': self.company.id,
                                                'payroll_country': 'VN'})
        self.Row.create({'employee_id': theirs.id, 'config_id': self.vn.id, 'date_from': '2026-01-01'})
        self.Row.create({'employee_id': mine.id, 'config_id': self.vn2.id, 'date_from': '2026-01-01'})
        self.assertEqual(batch.pb_own_scheme_elsewhere()['count'], 0, "quiet at zero")
        for emp in (theirs, mine, plain):
            self.line(batch, 'P2BM%s' % emp.id, emp.name, emp)
        new = batch._create_employee(self.line(batch, 'P2BF03', 'DEMO PS2B New'))
        batch.created_employee_ids = [(4, new.id)]
        out = batch.pb_own_scheme_elsewhere()
        self.assertEqual((out['count'], out['names']), (1, ['DEMO PS2B Own']))
        self.assertEqual(out['line'], "1 person in this file has another pay scheme of their "
                                      "own: DEMO PS2B Own. They are not changed.")
        self.assertEqual(self.Row.search([('employee_id', '=', theirs.id)]).config_id, self.vn,
                         "never changed")
        if 'pb.import.wizard' in self.env:
            summary = self.env['pb.import.wizard'].get_summary(batch.id)
            self.assertEqual(summary['own_elsewhere']['count'], 1)
        if 'pb.import.batch.cockpit' in self.env:
            detail = self.env['pb.import.batch.cockpit'].get_batch_detail(batch.id)
            self.assertEqual(detail['own_elsewhere']['count'], 1)

    # ================================================================ T13b
    def test_t13b_usual_scheme_and_r6(self):
        Map = self.env['pb.scheme.map']
        found = Map.usual_scheme(self.company.id, 'VN', self.team.id)
        self.assertTrue(found['ask'], "two Vietnamese schemes, nobody paid: it asks")
        self.assertEqual(found['config'], self.vn, "the first by name")
        self.env['hr.formula.scheme.assignment'].create({
            'config_id': self.vn2.id, 'department_id': self.team.id, 'cycle_type': 'any',
            'company_id': self.company.id})
        found = Map.usual_scheme(self.company.id, 'VN', self.team.id)
        self.assertEqual((found['config'], found['reason'], found['ask']), (self.vn2, 'ladder', False))
        found = Map.usual_scheme(self.company.id, 'ID', self.team.id)
        self.assertEqual((found['config'], found['reason']), (self.vn2, 'ladder_other'))
        Board = self.env['pb.scheme.board']
        self.assertEqual(Board.r6_words('Old', 'New', '2026-12-15'),
                         'Old still pays December 2026. New starts with the next pay run.')
        self.assertFalse(Board.r6_words('Old', 'New', '2026-12-01'))
        self.assertEqual(Board.advance_default(self.vn), self.vn_adv)
        self.assertFalse(Board.advance_default(self.vn2))

    # ================================================================ T13c
    def test_t13c_take_back_helper(self):
        Board = self.env['pb.scheme.board'].sudo()
        emp = self.env['hr.employee'].create({'name': 'DEMO PS2B Back', 'company_id': self.company.id})
        self.Row.create({'employee_id': emp.id, 'config_id': self.vn.id, 'date_from': '2026-01-01'})
        before = Board._person_rows_state(emp.ids)
        Board.with_context(pb_schememap_approved_write=True)._person_set_write(
            emp, self.vn2, False, date(2026, 12, 1), source='job_change')
        after = Board._person_rows_state(emp.ids)
        self.assertNotEqual(before, after)
        Board._person_rows_restore(before, after, emp.ids)
        self.assertEqual([v[1:] for v in Board._person_rows_state(emp.ids).values()],
                         [v[1:] for v in before.values()])
        # changed since: refused, naming the person
        Board.with_context(pb_schememap_approved_write=True)._person_set_write(
            emp, self.vn2, False, date(2026, 12, 1), source='job_change')
        after = Board._person_rows_state(emp.ids)
        self.Row.search([('employee_id', '=', emp.id)], order='id desc', limit=1).date_to = '2027-06-30'
        with self.assertRaises(UserError) as caught:
            Board._person_rows_restore(before, after, emp.ids)
        self.assertIn('DEMO PS2B Back', str(caught.exception))
        # never from a plain user's door
        with self.assertRaises(UserError):
            self.env['pb.scheme.board'].with_user(self._plain())._person_end_company(
                emp, self.company, date(2027, 1, 1))

    def _plain(self):
        return self.env['res.users'].create({
            'name': 'DEMO PS2B plain', 'login': 'ps2b_plain', 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})

    # ================================================================= T16
    def test_t16_formula_module_reaches_the_map_by_probe_only(self):
        manifest = ast.literal_eval(open(os.path.join(
            ROOT, 'pb_hr_payroll_formula', '__manifest__.py'), encoding='utf-8').read())
        self.assertNotIn('pb_scheme_map', manifest['depends'])
        source = open(os.path.join(ROOT, 'pb_hr_payroll_formula', 'models',
                                   'payroll_import_batch.py'), encoding='utf-8').read()
        self.assertIn("'pb.scheme.board' not in self.env", source)
        self.assertNotIn('pb_scheme_map', source.replace("'pb.scheme.board'", ''))
        for module in ('pb_pay_package', 'pb_import_wizard', 'pb_import_batch'):
            manifest = ast.literal_eval(open(os.path.join(ROOT, module, '__manifest__.py'),
                                             encoding='utf-8').read())
            self.assertNotIn('pb_scheme_map', manifest['depends'], module)
