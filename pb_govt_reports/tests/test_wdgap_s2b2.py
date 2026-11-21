# -*- coding: utf-8 -*-
"""WDGAP S2-B2 — the Filings board groups the form tiles: "Tax returns",
then "Fund files"; the pay items the Vietnamese social-insurance reports read
are no tile of their own; the Vietnamese social-insurance tiles keep working."""
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_govt_reports.models.pb_govt_reports import _form_groups

OFFICER = ('base.group_user,om_hr_payroll.group_hr_payroll_user,'
           'pb_hr_payroll_base.group_payroll_base_officer')


@tagged('post_install', '-at_install', 'wdgap_s2b2')
class TestS2B2FilingsGroups(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'DEMO S2B2 Board Co', 'country_id': cls.env.ref('base.vn').id,
            'currency_id': cls.env.ref('base.VND').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.officer = new_test_user(cls.env, login='s2b2_gov_off', groups=OFFICER,
                                    company_id=cls.company.id,
                                    company_ids=[(6, 0, [cls.company.id])])

    def _data(self, cc):
        return self.env['pb.govt.reports'].with_user(self.officer).with_context(
            allowed_company_ids=[self.company.id]).get_govt_reports_data(cc)

    def test_groups_in_order_and_no_tile_for_report_items(self):
        self.assertEqual([g['key'] for g in _form_groups([
            {'id': 1, 'section': 'fund'}, {'id': 2, 'section': 'tax'},
            {'id': 3, 'section': 'year_end'}, {'id': 4}])], ['tax', 'year_end', 'fund'])
        vn = self._data('VN')
        self.assertTrue(vn['groups'], "the Vietnamese social-insurance tiles keep working")
        if 'pb.gov.form' not in self.env:
            self.assertEqual(vn['form_groups'], [])
            return
        codes = {f['code'] for g in vn['form_groups'] for f in g['forms']}
        self.assertIn('VN_05KK_TT89', codes)
        self.assertNotIn('VN_SI_ITEMS', codes, "no file of its own, so no tile")
        self.assertEqual({f['code'] for f in vn['forms']},
                         {f['code'] for g in vn['form_groups'] if g['key'] == 'tax' for f in g['forms']},
                         "`forms` keeps its S2-A meaning: the tax returns")
        for cc, fund in (('ID', {'ID_BPJS_TK', 'ID_BPJS_KES'}), ('IN', {'IN_EPF_ECR', 'IN_ESI'}),
                         ('SG', {'SG_CPF_EZPAY'})):
            data = self._data(cc)
            self.assertTrue(data['available'], cc)
            groups = {g['key']: g for g in data['form_groups']}
            self.assertEqual({f['code'] for f in groups['fund']['forms']}, fund, cc)
            for f in groups['fund']['forms']:
                self.assertEqual(f['adviser_wording'], 'fund')
        # S2 merge: S2-B1's year-end forms sit in their own group, between the two
        expected = ['tax', 'year_end', 'fund'] if self.env['pb.gov.form'].sudo().search_count(
            [('country_code', '=', 'ID'), ('filing_section', '=', 'year_end')]) else ['tax', 'fund']
        self.assertEqual([g['key'] for g in self._data('ID')['form_groups']], expected)
