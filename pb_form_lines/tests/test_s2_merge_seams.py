# -*- coding: utf-8 -*-
"""WDGAP Step 2 merge seams (deploy agent, 2026-11-18).

M1  The tax-detail numbers kept by Tax details on My Payobook (pb_me_tax) are
    what the filings read: filled → the person is in the file; empty → left
    out / warned with the reason (merge-time task c).
M2  One Filings gate (owner ruling FG1): every place that names who may see,
    prepare and download a filing names the same three groups; "Accepted by
    the authority" and "Release to employees" stay payroll manager only
    (merge-time task e).
M3  One tile grouping: every form's `filing_section` and `tile_group` agree.

Every part that needs a module this one does not depend on skips itself when
that module is absent.
"""
import importlib
import os
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_form_lines.models import form as form_mod
from odoo.addons.pb_form_lines.models import fund_in

ADDONS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FG1 = {'pb_hr_payroll_base.group_payroll_base_officer',
       'pb_hr_payroll_base.group_payroll_base_manager',
       'pb_hr_govt.group_pb_hr_govt_user'}


@tagged('post_install', '-at_install', 'wdgap_s2m')
class TestS2MergeSeams(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Reader = cls.env['pb.gov.form.reader']
        cls.Form = cls.env['pb.gov.form'].sudo()
        cls.emp = cls.env['hr.employee'].create({'name': 'DEMO S2M Seam'})

    def _form(self, code):
        form = self.Form.search([('code', '=', code)], limit=1)
        self.assertTrue(form, code)
        return form

    def _needs(self, *names):
        Emp = self.env['hr.employee']
        missing = [n for n in names if n not in Emp._fields]
        if missing:
            self.skipTest('Tax details on My Payobook (pb_me_tax) not installed: %s' % missing)

    # ------------------------------------------------------------------ M1
    def test_m1_india_pan_from_tax_details(self):
        self._needs('pb_in_pan_number', 'pb_in_tax_regime')
        for code in ('IN_FORM16B', 'IN_FORM130C', 'IN_24Q', 'IN_FORM138'):
            before = self.Reader._pb_identity(self._form(code), self.emp)
            self.assertTrue(before['missing'], code)
        self.emp.sudo().write({'pb_in_pan_number': 'ABCDE1234F', 'pb_in_tax_regime': 'old'})
        for code in ('IN_FORM16B', 'IN_FORM130C', 'IN_24Q', 'IN_FORM138'):
            after = self.Reader._pb_identity(self._form(code), self.emp)
            self.assertEqual(after['missing'], [], code)
            self.assertEqual((after['values']['pan'], after['values']['regime']),
                             ('ABCDE1234F', 'old'), code)

    def test_m1_indonesia_tax_status_from_tax_details(self):
        self._needs('pb_id_ptkp_status')
        self.emp.sudo().write({'identification_id': '3171234567890123'})
        for code in ('ID_BPMP', 'ID_BPA1'):
            self.assertEqual(self.Reader._pb_identity(self._form(code), self.emp)['values']['ptkp'], '', code)
        self.emp.sudo().write({'pb_id_ptkp_status': 'K/1'})
        for code in ('ID_BPMP', 'ID_BPA1'):
            ident = self.Reader._pb_identity(self._form(code), self.emp)
            self.assertEqual(ident['values']['ptkp'], 'K/1', code)
            self.assertEqual(ident['missing'], [], code)

    def test_m1_india_fund_numbers_from_tax_details(self):
        self._needs('pb_in_uan_number', 'pb_in_esi_number')
        self.assertEqual(fund_in.ESI_EMPLOYEE_FIELDS[0], 'pb_in_esi_number')
        self.assertEqual(fund_in.UAN_EMPLOYEE_FIELDS[0], 'pb_in_uan_number')
        for code in ('IN_EPF_ECR', 'IN_ESI'):
            before = self.Reader._pb_identity(self._form(code), self.emp)
            self.assertTrue(before['missing'], code)
            self.assertTrue(before['values']['leave_out'], code)
        self.emp.sudo().write({'pb_in_uan_number': '100123456789',
                               'pb_in_esi_number': '3100123457'})
        for code in ('IN_EPF_ECR', 'IN_ESI'):
            after = self.Reader._pb_identity(self._form(code), self.emp)
            self.assertEqual(after['missing'], [], code)
            self.assertFalse(after['values']['leave_out'], code)

    def test_m1_singapore_residency_from_tax_details(self):
        self._needs('pb_sg_tax_residency')
        self.emp.sudo().write({'identification_id': 'S1234567D'})
        form = self._form('SG_IR8A')
        self.assertTrue(self.Reader._pb_identity(form, self.emp)['resident'])
        self.emp.sudo().write({'pb_sg_tax_residency': 'non_resident'})
        ident = self.Reader._pb_identity(form, self.emp)
        self.assertFalse(ident['resident'])
        self.assertEqual(ident['values']['residency'], 'non_resident')

    # ------------------------------------------------------------------ M2
    def _js_groups(self, rel, const):
        path = os.path.join(ADDONS, rel)
        if not os.path.exists(path):
            self.skipTest('%s not on this tree' % rel)
        src = open(path, encoding='utf-8').read()
        match = re.search(r'%s\s*=\s*\[(.*?)\]' % const, src, re.S)
        self.assertTrue(match, '%s in %s' % (const, rel))
        return set(re.findall(r'"([a-z0-9_.]+)"', match.group(1)))

    def test_m2_one_filings_gate_everywhere(self):
        self.assertEqual(set(form_mod.OFFICER_GROUPS), FG1, 'Form lines / tax returns / year-end / fund files')
        self.assertEqual(set(form_mod.MANAGER_GROUPS),
                         {'pb_hr_payroll_base.group_payroll_base_manager'},
                         'Accepted by the authority + Release to employees')
        self.assertEqual(self._js_groups('pb_hub/static/src/js/hub_palette_entries.js', 'CMP_FILINGS'), FG1)
        self.assertEqual(self._js_groups('pb_compliance_hub/static/src/js/compliance_hub.js', 'FILINGS_GATE'), FG1)
        try:
            flow = importlib.import_module('odoo.addons.pb_govt_reports.models.pb_filing_flow')
            approval = importlib.import_module('odoo.addons.pb_govt_reports.models.filing_approval')
        except ImportError:
            self.skipTest('pb_govt_reports not on this tree')
        self.assertEqual(set(flow._FILING_GROUPS), FG1, 'VN social-insurance filing flow')
        self.assertEqual(set(approval.PbFilingProposal._proposal_gate_groups), FG1)
        try:
            amber = importlib.import_module('odoo.addons.pb_payai_actions.payai.actions_amber')
        except ImportError:
            return
        self.assertEqual(set(amber.FILING_GROUPS), FG1, 'PayAI "prepare a filing"')

    def test_m2_release_and_accept_stay_manager_only(self):
        cert = importlib.import_module('odoo.addons.pb_form_lines.models.certificate')
        src = open(cert.__file__, encoding='utf-8').read()
        self.assertIn('MANAGER_GROUPS', src, 'Release to employees reads the manager list')

    # ------------------------------------------------------------------ M3
    def test_m3_one_tile_grouping(self):
        pairs = {'tax': 'tax_return', 'year_end': 'year_end', 'fund': 'fund_file',
                 'reports': 'tax_return'}
        forms = self.Form.with_context(active_test=False).search([])
        self.assertTrue(forms)
        for form in forms:
            self.assertEqual(pairs[form.filing_section], form.tile_group, form.code)
        self.assertEqual(set(forms.filtered(lambda f: f.filing_section == 'year_end').mapped('code')),
                         {'ID_BPA1', 'VN_05QTT_TT89', 'VN_05QTT_TT80', 'IN_FORM16B',
                          'IN_FORM130C', 'IN_24Q', 'IN_FORM138', 'SG_IR8A'})
        self.assertNotEqual(self.Form._fields['tile_group'].string,
                            self.Form._fields['filing_section'].string)
