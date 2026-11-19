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
        Company = cls.env['res.company'].sudo()
        cls.co_vn = Company.create({'name': 'DEMO fill company VN',
                                    'country_id': cls.env.ref('base.vn').id})
        cls.co_none = Company.create({'name': 'DEMO fill company no country'})
        cls.co_none.partner_id.country_id = False
        cls.co_us = Company.create({'name': 'DEMO fill company US',
                                    'country_id': cls.env.ref('base.us').id})
        cls.companies = cls.co_vn | cls.co_none | cls.co_us
        cls.manager, cls.officer = common.make_hr_users(cls.env, 'fill')
        for user in (cls.manager, cls.officer):
            user.sudo().write({'company_ids': [(4, c.id) for c in cls.companies]})
        Emp = cls.env['hr.employee'].sudo()
        Config = cls.env['hr.formula.config'].sudo()
        cls.vn = Config.create({'name': 'DEMO fill VN', 'country_code': 'VN',
                                'company_id': cls.co_vn.id})
        cls.sg = Config.create({'name': 'DEMO fill SG', 'country_code': 'SG',
                                'company_id': cls.co_vn.id})
        cls.has_map = 'pb_paid_by_id' in Emp._fields

        def person(name, company, country=False, paid=None, advance=None, contract=True):
            emp = Emp.create({'name': name, 'company_id': company.id,
                              'payroll_country': country})
            if contract:
                cls.env['hr.contract'].sudo().create({
                    'name': name, 'employee_id': emp.id, 'wage': 100.0, 'state': 'open',
                    'date_start': '2025-01-01', 'company_id': company.id})
            if cls.has_map:
                vals = {'pb_paid_by_id': paid.id if paid else False}
                if 'pb_paid_by_advance_id' in Emp._fields:
                    vals['pb_paid_by_advance_id'] = advance.id if advance else False
                if 'pb_paid_by_stale' in Emp._fields:
                    vals['pb_paid_by_stale'] = False
                emp.write(vals)
            return emp

        # (a) decides: a contract and a "Paid by" pay set-up in Singapore,
        #     inside a company whose country is Vietnam — the pay set-up wins
        cls.by_pay = person('DEMO fill paid SG', cls.co_vn, paid=cls.sg)
        # (b) decides: no contract (so no pay set-up), company in Vietnam
        cls.by_company = person('DEMO fill no contract VN co', cls.co_vn, contract=False)
        cls.keep_id = person('DEMO fill already ID', cls.co_vn, country='ID', paid=cls.vn)
        cls.two = person('DEMO fill two countries', cls.co_vn, paid=cls.vn, advance=cls.sg)
        cls.no_country = person('DEMO fill company without country', cls.co_none, contract=False)
        cls.not_offered = person('DEMO fill company in the US', cls.co_us, contract=False)

    def _wizard(self, user=None, companies=None, **vals):
        return self.env['pb.cow.fill.wizard'].with_user(user or self.manager).with_context(
            allowed_company_ids=(companies or self.companies).ids).create(vals)

    def test_07a_preview_shows_both_sources_and_what_is_left(self):
        if not self.has_map:
            self.skipTest("the scheme map is not installed")
        wizard = self._wizard()
        preview = json.loads(wizard.preview_json)
        self.assertEqual(preview['empty'], 5)
        self.assertEqual(preview['from_pay_setup'], {'SG': 1})
        self.assertEqual(preview['from_company'], {'VN': 1})
        self.assertEqual(preview['fill'], {'SG': 1, 'VN': 1})
        self.assertEqual(preview['left'], {'two_countries': 1, 'company_no_country': 1,
                                           'company_country_not_offered': 1})
        self.assertEqual((wizard.fill_count, wizard.company_count), (2, 1))
        html = str(wizard.preview_html)
        for words in ('From pay set-up', 'From the company', 'DEMO fill two countries',
                      'has no country', 'not one of the Country of Work choices'):
            self.assertIn(words, html)
        self.assertNotIn('Odoo', html)

    def test_07b_both_sources_fill_only_empties_and_once(self):
        if not self.has_map:
            self.skipTest("the scheme map is not installed")
        res = self._wizard().action_fill()
        self.assertEqual((res['total'], res['from_company']), (2, 1))
        self.assertEqual(self.by_pay.payroll_country, 'SG', "rule (a) did not win")
        self.assertEqual(self.by_company.payroll_country, 'VN', "rule (b) did not fill")
        self.assertEqual(self.keep_id.payroll_country, 'ID', "a set Country of Work was overwritten")
        self.assertFalse(self.two.payroll_country, "a two-country person was decided")
        self.assertFalse(self.no_country.payroll_country)
        self.assertFalse(self.not_offered.payroll_country)
        log = self.env['pb.cow.fill.log'].sudo().search([], limit=1)
        self.assertEqual(log.user_id, self.manager)
        self.assertEqual((log.filled_count, log.company_count, log.left_count), (2, 1, 3))
        self.assertEqual(json.loads(log.by_country), {'SG': 1, 'VN': 1})
        # idempotent: a second run decides nothing new
        self.assertEqual(self._wizard().action_fill()['total'], 0)

    def test_07c_the_company_part_can_be_unticked(self):
        if not self.has_map:
            self.skipTest("the scheme map is not installed")
        wizard = self._wizard(use_company=False)
        preview = json.loads(wizard.preview_json)
        self.assertEqual(preview['fill'], {'SG': 1})
        self.assertEqual(preview['from_company'], {'VN': 1})
        self.assertIn('Not ticked', str(wizard.preview_html))
        res = wizard.action_fill()
        self.assertEqual((res['total'], res['from_company']), (1, 0))
        self.assertEqual(self.by_pay.payroll_country, 'SG')
        self.assertFalse(self.by_company.payroll_country, "the unticked part was filled")
        # ticked on a later run: the company part is filled then
        res = self._wizard().action_fill()
        self.assertEqual((res['total'], res['from_company']), (1, 1))
        self.assertEqual(self.by_company.payroll_country, 'VN')

    def test_07d_company_source_alone(self):
        """The live case: no pay set-up decides anybody (no contract, or a pay
        set-up linked to nobody) — the company's country decides."""
        res = self._wizard(companies=self.co_vn | self.co_none).action_fill()
        self.assertEqual(self.by_company.payroll_country, 'VN')
        self.assertGreaterEqual(res['from_company'], 1)
        self.assertFalse(self.no_country.payroll_country, "a company without a country decided")

    def test_07e_never_overwrites_even_when_set_after_the_preview(self):
        wizard = self._wizard()
        self.by_company.payroll_country = 'SG'           # someone sets it meanwhile
        wizard.action_fill()
        self.assertEqual(self.by_company.payroll_country, 'SG')

    def test_07f_hr_managers_only(self):
        with self.assertRaises(AccessError):
            self._wizard(self.officer)
        head = self.env['pb.people'].with_user(self.officer).get_roster_head()
        self.assertFalse(head['kpis']['cow_can_fill'])
        head = self.env['pb.people'].with_user(self.manager).with_context(
            allowed_company_ids=self.companies.ids).get_roster_head()
        self.assertTrue(head['kpis']['cow_can_fill'])
        self.assertGreaterEqual(head['kpis']['cow_empty'], 5)


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
