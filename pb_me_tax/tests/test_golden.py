# -*- coding: utf-8 -*-
"""WDGAP S2-D T8b — a payslip computes byte-identically with and without
this module's two engine hooks (the application-source catalogue and its
domain values), on a plain scheme and on one that reads employee-record
sources in application-data mode. The before/after-INSTALL golden (fields
and all) is the script run recorded in the S2-D report."""
import json
from datetime import date
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.pb_me_tax.models.formula_sources import HrFormulaConfigTaxSources

from .common import TaxCase

D_FROM = date(2026, 6, 1)
D_TO = date(2026, 6, 30)


def _catalogue_without(self):
    return super(HrFormulaConfigTaxSources, self)._application_source_catalogue()


def _values_without(self, employee, contract, date_from, date_to):
    return super(HrFormulaConfigTaxSources, self)._application_domain_values(
        employee, contract, date_from, date_to)


@tagged('post_install', '-at_install', 'wdgap_s2d')
class TestS2dGolden(TaxCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['hr.salary.rule.category'].search([], limit=1)
        cls.contract = cls.env['hr.contract'].sudo().create({
            'name': 'DEMO S2D golden contract', 'employee_id': cls.emp.id,
            'company_id': cls.company.id, 'wage': 12_000_000.0,
            'state': 'open', 'date_start': '2026-01-01'})
        cls.emp.sudo().write({'vietnam_tax_code': '0312345678',
                              'pb_id_ptkp_status': 'K/1'})

    def _scheme(self, code, app_data=False):
        cfg = self.env['hr.formula.config'].sudo().create({
            'name': 'DEMO S2D golden %s' % code, 'code': code,
            'cycle_type': 'end_cycle', 'country_code': 'VN', 'state': 'active',
            'company_id': self.company.id})
        Rule = self.env['hr.formula.rule'].sudo()
        base = {'config_id': cfg.id, 'default_value': 0.0,
                'appears_on_payslip': True, 'category_id': self.category.id}
        Rule.create(dict(base, name='Basic', code='BASIC', column_type='input',
                         sequence=1, value_kind='money', net_role='earning'))
        Rule.create(dict(base, name='Allowance', code='GOLDALLOW',
                         column_type='input', sequence=2, value_kind='money',
                         net_role='earning', default_value=500_000.0))
        Rule.create(dict(base, name='Tax code', code='GOLDTAXID',
                         column_type='input', sequence=3, value_kind='identifier',
                         net_role='info', appears_on_payslip=False,
                         application_source_key='employee.vietnam_tax_code'
                         if app_data else False))
        Rule.create(dict(base, name='Net', code='GOLDNET', column_type='formula',
                         sequence=10, value_kind='money', net_role='net',
                         excel_formula='=BASIC+GOLDALLOW'))
        if app_data:
            cfg.write({'application_data_enabled': True,
                       'application_effective_from': '2026-01-01'})
        return cfg

    def _snapshot(self, slip):
        slip.invalidate_recordset()
        return {
            'inputs': json.loads(slip.formula_input_values or '{}'),
            'sources': json.loads(slip.formula_input_sources or '{}'),
            'computed': json.loads(slip.formula_computed_values or '{}'),
            'lines': sorted((l.code, l.amount, l.total) for l in slip.line_ids),
        }

    def test_t8b_payslip_identical_without_the_hooks(self):
        cfg = self._scheme('GOLDPLAIN')
        slip = self.env['hr.payslip'].sudo().create({
            'name': 'DEMO S2D golden', 'employee_id': self.emp.id,
            'contract_id': self.contract.id, 'date_from': D_FROM,
            'date_to': D_TO, 'company_id': self.company.id,
            'formula_config_id': cfg.id, 'calculation_method': 'formula'})
        slip.compute_sheet()
        with_hooks = self._snapshot(slip)
        self.assertTrue(with_hooks['lines'], 'the fixture really computes')
        with patch.object(HrFormulaConfigTaxSources, '_application_source_catalogue',
                          _catalogue_without), \
                patch.object(HrFormulaConfigTaxSources, '_application_domain_values',
                             _values_without):
            slip.compute_sheet()
            without = self._snapshot(slip)
        self.assertEqual(json.dumps(with_hooks, sort_keys=True, default=str),
                         json.dumps(without, sort_keys=True, default=str))

    def test_t8c_application_inputs_identical_without_the_hooks(self):
        cfg = self._scheme('GOLDAPP', app_data=True)
        cert = {'channels': {'leave': True, 'overtime': True, 'adjustments': True}}
        got = cfg._application_employee_inputs(self.emp, D_FROM, D_TO, cert)
        with patch.object(HrFormulaConfigTaxSources, '_application_source_catalogue',
                          _catalogue_without), \
                patch.object(HrFormulaConfigTaxSources, '_application_domain_values',
                             _values_without):
            cfg.invalidate_recordset()
            base = cfg._application_employee_inputs(self.emp, D_FROM, D_TO, cert)
        self.assertEqual(json.dumps(got, sort_keys=True, default=str),
                         json.dumps(base, sort_keys=True, default=str))
        rows = {r['code']: r for r in got['inputs']}
        self.assertEqual(rows['GOLDTAXID']['value'], '0312345678',
                         'the fixture really reads an employee-record source')
