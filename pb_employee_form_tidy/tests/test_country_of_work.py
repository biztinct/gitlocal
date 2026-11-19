# -*- coding: utf-8 -*-
"""TIDY-E tests 6, 7, 8 — Country of Work from a file, from the Updates sheet,
from the pay set-up; and payslips unchanged.

6  Mapping offers "Country of Work" in the employee lane; a pay data file
   column mapped to it sets it for VN / ID / IN / SG spellings; an unknown
   word is listed for the load result instead of failing; the Updates sheet
   sets it too.
7  "Fill empty Country of Work": preview counts, fills only empties, never
   overwrites, people paid in two countries are left and listed, a second run
   does nothing, HR managers only.
8  a payslip of each country computes the same before and after a save of the
   employee form.
"""

import json

from odoo.exceptions import AccessError
from odoo.tests import Form, TransactionCase, tagged

from . import common


@tagged('post_install', '-at_install', 'tidy_e')
class TestCountryOfWorkFromFiles(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env['res.company'].create({'name': 'DEMO Tidy file company'})
        self.env = self.env(context=dict(self.env.context,
                                        allowed_company_ids=self.company.ids))
        self.config = self.env['hr.formula.config'].create({
            'name': 'DEMO Tidy scheme', 'country_code': 'IN', 'company_id': self.company.id})
        self.batch = self.env['hr.payroll.import.batch'].create({
            'name': 'DEMO Tidy batch', 'source_type': 'excel',
            'formula_config_id': self.config.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'company_id': self.company.id})
        self.rule = self.env['hr.formula.rule'].create({
            'config_id': self.config.id, 'code': 'INCOUNTRY', 'name': 'Country',
            'column_type': 'input', 'value_kind': 'text', 'source_sheet_name': 'Main'})
        self.rule.set_source_binding('excel', 'Main|Country')
        self.field = self.env['ir.model.fields']._get('hr.employee', 'payroll_country')
        self.env['hr.payslip.import.mapping'].create({
            'salary_structure_id': self.config.id, 'component_id': self.rule.id,
            'destination_type': 'field',
            'target_model_id': self.env['ir.model']._get('hr.employee').id,
            'target_field_id': self.field.id})

    def _line(self, employee, word, seq=1):
        return self.env['hr.payroll.import.line'].create({
            'batch_id': self.batch.id, 'sequence': seq, 'employee_id': employee.id,
            'employee_name': employee.name, 'state': 'validated',
            'raw_data_json': json.dumps({'Main|Country': word})})

    def test_06a_mapping_offers_country_of_work_in_the_employee_lane(self):
        Studio = self.env['pb.formula.studio']
        items = {i['id']: i for i in Studio._ec_right_items()}
        card = items.get('f:hr.employee:payroll_country')
        self.assertTrue(card, "Country of Work is not a Mapping destination")
        self.assertEqual(card['label'], 'Country of Work')
        self.assertEqual(card['meta']['lane'], 'job')
        self.assertTrue(card['meta'].get('recommended'))
        self.assertNotEqual(card['meta'].get('mappable'), False)

    def test_06b_the_file_sets_it_for_every_spelling(self):
        cases = {'Vietnam': 'VN', 'VN': 'VN', 'Việt Nam': 'VN', 'viet nam': 'VN',
                 'Indonesia': 'ID', 'ID': 'ID', 'IDN': 'ID',
                 'India': 'IN', 'IN': 'IN', 'Ấn Độ': 'IN',
                 'Singapore': 'SG', 'SG': 'SG', 'Singapura': 'SG'}
        Emp = self.env['hr.employee']
        for n, (word, code) in enumerate(cases.items()):
            emp = Emp.create({'name': 'DEMO file %s' % n, 'company_id': self.company.id})
            line = self._line(emp, word, seq=n + 1)
            updates = self.batch._get_mapping_updates(
                emp, line.get_raw_data(), line=line, employee=emp)
            self.assertEqual(updates.get('payroll_country'), code, word)

    def test_06c_an_unknown_word_is_listed_not_failed(self):
        Emp = self.env['hr.employee']
        emp = Emp.create({'name': 'DEMO file unknown', 'company_id': self.company.id,
                          'payroll_country': 'SG'})
        line = self._line(emp, 'Atlantis', seq=7)
        updates = self.batch._get_mapping_updates(
            emp, line.get_raw_data(), line=line, employee=emp)
        self.assertNotIn('payroll_country', updates)
        rows = self.batch._pb_cow_unknown_rows()
        self.assertEqual([(r['row'], r['value']) for r in rows], [(7, 'Atlantis')])
        sentence = self.batch._pb_cow_sentence(rows)
        self.assertIn('Atlantis', sentence)
        self.assertNotIn('Odoo', sentence)
        self.assertIn('Country of Work left unchanged on row 7', self.batch.processing_log or '')
        self.assertEqual(emp.payroll_country, 'SG')

    def test_06d_the_updates_sheet_sets_it(self):
        Desk = self.env['pb.records.desk']
        field = self.env['hr.employee']._fields['payroll_country']
        self.assertEqual(Desk._selection_key(field, 'Việt Nam'), ('VN', None))
        self.assertEqual(Desk._selection_key(field, 'IDN'), ('ID', None))
        self.assertEqual(Desk._selection_key(field, 'Singapore'), ('SG', None))
        key, why = Desk._selection_key(field, 'Atlantis')
        self.assertIsNone(key)
        self.assertTrue(why)
        cards = Desk._cards(0)
        card = cards.get('f:hr.employee:payroll_country')
        self.assertTrue(card, "Country of Work is not on the Updates / Records sheets")
        self.assertEqual(card['label'], 'Country of Work')
        emp = self.env['hr.employee'].create({'name': 'DEMO sheet', 'company_id': self.company.id})
        probe = self.env['hr.payroll.import.batch']
        coerced, _label, why = Desk._coerce(probe, card, 'Indonesia', emp, emp.contract_id)
        self.assertIsNone(why)
        self.assertEqual(coerced, 'ID')


@tagged('post_install', '-at_install', 'tidy_e')
class TestCountryOfWorkFill(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager, cls.officer = common.make_hr_users(cls.env, 'fill')
        cls.company = cls.env.company
        Emp = cls.env['hr.employee'].sudo()
        Config = cls.env['hr.formula.config'].sudo()
        cls.vn = Config.create({'name': 'DEMO fill VN', 'country_code': 'VN',
                                'company_id': cls.company.id})
        cls.sg = Config.create({'name': 'DEMO fill SG', 'country_code': 'SG',
                                'company_id': cls.company.id})

        def person(name, country=False, paid=None, advance=None, contract=True):
            emp = Emp.create({'name': name, 'company_id': cls.company.id,
                              'payroll_country': country})
            if contract:
                cls.env['hr.contract'].sudo().create({
                    'name': name, 'employee_id': emp.id, 'wage': 100.0, 'state': 'open',
                    'date_start': '2025-01-01', 'company_id': cls.company.id})
            vals = {}
            if 'pb_paid_by_id' in Emp._fields:
                vals['pb_paid_by_id'] = paid.id if paid else False
                if 'pb_paid_by_advance_id' in Emp._fields:
                    vals['pb_paid_by_advance_id'] = advance.id if advance else False
                if 'pb_paid_by_stale' in Emp._fields:
                    vals['pb_paid_by_stale'] = False
            if vals:
                emp.write(vals)
            return emp

        cls.has_map = 'pb_paid_by_id' in Emp._fields
        cls.fill_vn = person('DEMO fill empty VN', paid=cls.vn)
        cls.keep_id = person('DEMO fill already ID', country='ID', paid=cls.vn)
        cls.no_contract = person('DEMO fill no contract', paid=cls.vn, contract=False)
        cls.two = person('DEMO fill two countries', paid=cls.vn, advance=cls.sg)

    def _wizard(self, user=None):
        return self.env['pb.cow.fill.wizard'].with_user(user or self.manager).create({})

    def test_07a_preview_then_fill_only_empties(self):
        if not self.has_map:
            self.skipTest("the scheme map is not installed")
        wizard = self._wizard()
        preview = json.loads(wizard.preview_json)
        self.assertGreaterEqual(preview['fill'].get('VN', 0), 1)
        self.assertIn(self.two.id, [r['id'] for r in preview['two_countries']])
        self.assertIn('no_contract', preview['left'])
        self.assertIn('DEMO fill two countries', wizard.preview_html)
        self.assertNotIn('Odoo', wizard.preview_html)

        res = wizard.action_fill()
        self.assertGreaterEqual(res['total'], 1)
        self.assertEqual(self.fill_vn.payroll_country, 'VN')
        self.assertEqual(self.keep_id.payroll_country, 'ID', "a set Country of Work was overwritten")
        self.assertFalse(self.no_contract.payroll_country)
        self.assertFalse(self.two.payroll_country, "a two-country person was decided by the button")
        log = self.env['pb.cow.fill.log'].sudo().search([], limit=1)
        self.assertEqual(log.user_id, self.manager)
        self.assertEqual(log.filled_count, res['total'])
        self.assertEqual(json.loads(log.by_country).get('VN', 0), res['filled'].get('VN', 0))

        # second run: the same people are not touched again
        again = self._wizard().action_fill()
        self.assertEqual(again['filled'].get('VN', 0), 0)

    def test_07b_never_overwrites_even_when_set_after_the_preview(self):
        if not self.has_map:
            self.skipTest("the scheme map is not installed")
        wizard = self._wizard()
        self.fill_vn.payroll_country = 'SG'           # someone sets it meanwhile
        wizard.action_fill()
        self.assertEqual(self.fill_vn.payroll_country, 'SG')

    def test_07c_hr_managers_only(self):
        with self.assertRaises(AccessError):
            self._wizard(self.officer)
        head = self.env['pb.people'].with_user(self.officer).get_roster_head()
        self.assertFalse(head['kpis']['cow_can_fill'])
        head = self.env['pb.people'].with_user(self.manager).get_roster_head()
        self.assertTrue(head['kpis']['cow_can_fill'])
        self.assertGreaterEqual(head['kpis']['cow_empty'], 3)


@tagged('post_install', '-at_install', 'tidy_e')
class TestPayslipsUnchanged(TransactionCase):
    """Test 8 — a payslip per country computes the same before and after a
    save of the employee form with hidden boxes holding values."""

    def test_08_one_payslip_per_country_is_identical(self):
        manager, _officer = common.make_hr_users(self.env, 'slip')
        category = self.env['hr.salary.rule.category'].search([], limit=1)
        for code in common.COUNTRIES:
            company = self.env['res.company'].create({
                'name': 'DEMO Tidy slip %s' % code,
                'currency_id': self.env.company.currency_id.id})
            manager.sudo().write({'company_ids': [(4, company.id)]})
            env = self.env(context=dict(self.env.context, allowed_company_ids=[company.id]))
            emp = env['hr.employee'].create({
                'name': 'DEMO slip %s' % code, 'company_id': company.id,
                'payroll_country': code})
            contract = env['hr.contract'].create({
                'name': 'DEMO slip %s' % code, 'employee_id': emp.id, 'wage': 12345.0,
                'state': 'open', 'date_start': '2020-01-01', 'company_id': company.id})
            config = env['hr.formula.config'].create({
                'name': 'DEMO slip scheme %s' % code, 'country_code': code,
                'company_id': company.id, 'state': 'active'})
            salary_rule = env['hr.salary.rule'].create({
                'name': 'Net pay', 'code': 'NETPAY', 'sequence': 200,
                'category_id': category.id, 'company_id': company.id})
            env['hr.formula.rule'].create({
                'config_id': config.id, 'name': 'Net pay', 'code': 'NETPAY',
                'column_type': 'constant', 'constant_value': 5000.0,
                'appears_on_payslip': True, 'category_id': category.id,
                'salary_rule_id': salary_rule.id})

            def compute():
                slip = env['hr.payslip'].create({
                    'employee_id': emp.id, 'name': 'DEMO slip', 'contract_id': contract.id,
                    'date_from': '2026-06-01', 'date_to': '2026-06-30',
                    'company_id': company.id})
                slip.compute_sheet()
                return sorted((l.code, l.amount, l.total) for l in slip.line_ids)

            before = compute()
            self.assertTrue(before)
            emp.sudo().write({k: 'DEMO-%s' % k[:8] for k in
                              ('account_number', 'osh_worker_code', 'insurance_code')
                              if k in emp._fields})
            form_emp = emp.with_user(manager).with_context(allowed_company_ids=[company.id])
            with Form(form_emp) as form:
                form.job_title = 'DEMO slip job'
            after = compute()
            self.assertEqual(before, after, "payslip changed for %s" % code)
