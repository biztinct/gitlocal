# -*- coding: utf-8 -*-
"""WDGAP S2-A — the Filings board: the gate is the right that produces a
filing (S2F-8), the false-claim tiles are gone (S2F-4), the tax returns of
the form catalogue appear as tiles when pb_form_lines is installed."""
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

OFFICER = ('base.group_user,om_hr_payroll.group_hr_payroll_user,'
           'pb_hr_payroll_base.group_payroll_base_officer')


@tagged('post_install', '-at_install', 'wdgap_s2a')
class TestS2AFilingsBoard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'DEMO S2A Board Co', 'country_id': cls.env.ref('base.vn').id,
            'currency_id': cls.env.ref('base.VND').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        mine = [(6, 0, [cls.company.id])]
        cls.officer = new_test_user(cls.env, login='s2a_gov_off', groups=OFFICER,
                                    company_id=cls.company.id, company_ids=mine)
        cls.govt_only = new_test_user(
            cls.env, login='s2a_gov_only',
            groups='base.group_user,pb_hr_govt.group_pb_hr_govt_user',
            company_id=cls.company.id, company_ids=mine)

    def _as(self, user):
        return dict(allowed_company_ids=[self.company.id])

    def test_s2a_1_an_officer_without_the_old_group_can_produce_a_vn_report(self):
        self.assertFalse(self.officer.has_group('pb_hr_govt.group_pb_hr_govt_user'))
        Flow = self.env['pb.filing.flow'].with_user(self.officer).with_context(**self._as(self.officer))
        d = Flow.scope('VN', 'tang_ld')
        self.assertTrue(d['wizard_id'], "the wizard opens for the payroll officer (new ACL row)")

    def test_s2a_2_fg1_the_government_reports_permission_keeps_filings(self):
        """WDGAP FG1 (owner): the "Government reports" permission alone still
        opens Filings, and seeing is producing (lens = generate = download).
        Anybody with neither group is refused."""
        Flow = self.env['pb.filing.flow'].with_user(self.govt_only).with_context(**self._as(self.govt_only))
        self.assertTrue(Flow._require_officer())
        d = Flow.scope('VN', 'tang_ld')
        self.assertTrue(d['wizard_id'])
        from odoo.addons.pb_govt_reports.models.filing_approval import PbFilingProposal
        self.assertIn('pb_hr_govt.group_pb_hr_govt_user', PbFilingProposal._proposal_gate_groups)
        nobody = new_test_user(self.env, login='s2a_gov_nobody', groups='base.group_user',
                               company_id=self.company.id,
                               company_ids=[(6, 0, [self.company.id])])
        hr_only = new_test_user(self.env, login='s2a_gov_hr', groups='base.group_user,hr.group_hr_user',
                                company_id=self.company.id,
                                company_ids=[(6, 0, [self.company.id])])
        for user in (nobody, hr_only):
            with self.assertRaises(AccessError):
                self.env['pb.filing.flow'].with_user(user).with_context(**self._as(user)).generate(
                    0, 'VN', 'tang_ld', {})

    def test_s2a_3_tiles_for_the_form_catalogue(self):
        data = self.env['pb.govt.reports'].with_user(self.officer).with_context(
            **self._as(self.officer)).get_govt_reports_data('VN')
        self.assertTrue(data['groups'], "the Vietnamese social-insurance tiles keep working")
        if 'pb.gov.form' not in self.env:
            self.assertEqual(data['forms'], [])
            return
        codes = {f['code'] for f in data['forms']}
        self.assertIn('VN_05KK_TT89', codes)
        self.assertTrue(data['form_lines'])
        indonesia = self.env['pb.govt.reports'].with_user(self.officer).with_context(
            **self._as(self.officer)).get_govt_reports_data('ID')
        self.assertTrue(indonesia['available'], "Indonesia is no longer 'coming soon'")
        self.assertEqual({f['code'] for f in indonesia['forms']}, {'ID_BPMP'})
        for f in indonesia['forms']:
            self.assertFalse(f['accepted'])
        # WDGAP FG1: the "Government reports" permission sees the same tiles
        other = self.env['pb.govt.reports'].with_user(self.govt_only).with_context(
            **self._as(self.govt_only)).get_govt_reports_data('ID')
        self.assertEqual({f['code'] for f in other['forms']}, {'ID_BPMP'})
        # …and nobody with neither group gets one
        hr_only = new_test_user(self.env, login='s2a_gov_hr2', groups='base.group_user,hr.group_hr_user',
                                company_id=self.company.id,
                                company_ids=[(6, 0, [self.company.id])])
        none = self.env['pb.govt.reports'].with_user(hr_only).with_context(
            **self._as(hr_only)).get_govt_reports_data('ID')
        self.assertEqual(none['forms'], [])

    def test_s2a_4_retired_countries_say_so(self):
        for cc in ('SG', 'TH', 'KH', 'MY'):
            data = self.env['pb.govt.reports'].get_govt_reports_data(cc)
            self.assertFalse(data['groups'])
            with self.assertRaises(UserError):
                self.env['pb.filing.flow'].scope(cc, '')
