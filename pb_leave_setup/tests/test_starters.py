# -*- coding: utf-8 -*-
"""WDGAP S5-A — ready-made kinds per country (owner ruling L1).

R1 the data: seven countries, three names each, a source for every figure,
   a pay rule the pay engine accepts, never a policy code or category.
R2 nothing is created by installing the module.
R3 applying a country creates its kinds switched off, waiting for review,
   with the names translated; applying it again never makes a second copy.
R4 a kind whose pay is still to decide cannot be switched on until it is.
R5 the review list says what is already there.
"""
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.pb_timeoff.models.rize_policy import _classification
from odoo.addons.pb_leave_setup.models.starters import COUNTRIES, load_starters

from .common import LeaveSetupCase


@tagged('post_install', '-at_install', 'wdgap_s5a')
class TestStarters(LeaveSetupCase):

    def _as(self, user):
        return self.env['pb.leave.setup'].with_user(user).with_context(
            allowed_company_ids=[self.company.id])

    # ============================================================== R1
    def test_r1_the_data(self):
        data = load_starters()
        self.assertEqual(sorted(data['countries']), sorted(COUNTRIES))
        for code, block in data['countries'].items():
            keys = [k['key'] for k in block['kinds']]
            self.assertEqual(len(keys), len(set(keys)), code)
            self.assertIn('unpaid', keys, code)
            for spec in block['kinds']:
                where = '%s.%s' % (code, spec['key'])
                self.assertTrue(all(spec['name'].get(x) for x in ('en', 'vi', 'id')), where)
                self.assertTrue(spec.get('sources'), where + ' has no source')
                for note in spec['sources'].values():
                    self.assertTrue(note.get('en'), where)
                treatment, fraction, funding, employer = spec['pay']
                if treatment != 'unconfigured':
                    self.assertFalse(_classification(treatment, fraction, funding, employer)['error'],
                                     where)
                self.assertIn(spec.get('earning', 'none'), ('none', 'yearly', 'monthly'), where)
                if spec.get('earning', 'none') != 'none':
                    self.assertTrue(spec.get('counted') and spec.get('days'), where)
                    self.assertIn('days', spec['sources'], where + ': the days need a source')
                if spec.get('steps'):
                    years = [y for y, _d in spec['steps']]
                    self.assertEqual(years, sorted(years), where)
                    self.assertIn('steps', spec['sources'], where + ': the steps need a source')
                self.assertNotIn('pb_policy_code', spec)
                self.assertNotIn('pb_policy_category', spec)

    # ============================================================== R2
    def test_r2_nothing_on_install(self):
        Kind = self.env['hr.leave.type'].with_context(active_test=False)
        self.assertFalse(Kind.search_count([('pb_ls_starter_key', '!=', False)]))
        self.assertFalse(Kind.search_count([('pb_ls_earning', '!=', 'none')]))

    # ============================================================== R3
    def test_r3_apply_and_apply_again(self):
        hr = self._as(self.hr_user)
        Kind = self.env['hr.leave.type'].with_context(active_test=False)
        langs = {c for c, _n in self.env['res.lang'].get_installed()}
        for code in COUNTRIES:
            rows = hr.starter_list(code, self.company.id)['rows']
            keys = [r['key'] for r in rows]
            self.assertFalse([r for r in rows if r['made']], code)
            res = hr.starter_apply(code, self.company.id, keys)
            self.assertEqual(len(res['created']), len(keys), code)
            made = Kind.browse(res['created'])
            self.assertFalse(made.filtered('active'), code + ': created switched off')
            self.assertTrue(all(made.mapped('pb_ls_review')), code)
            self.assertFalse(made.filtered('pb_policy_code') | made.filtered('pb_policy_category'))
            self.assertEqual(set(made.mapped('pb_policy_country_id.code')), {code})
            self.assertEqual(set(made.mapped('company_id')), {self.company})
            self.assertTrue(all(made.mapped('pb_ls_sources')))
            annual = made.filtered(lambda k: k.pb_ls_starter_key.endswith('.annual'))
            if annual and 'vi_VN' in langs:
                self.assertEqual(annual.with_context(lang='vi_VN').name, 'Nghỉ phép năm')
            if annual and 'id_ID' in langs:
                self.assertEqual(annual.with_context(lang='id_ID').name, 'Cuti tahunan')
            self.assertEqual(annual.with_context(lang='en_US').name if annual else 'Annual leave',
                             'Annual leave')
            # again: nothing new
            again = hr.starter_apply(code, self.company.id, keys)
            self.assertEqual((again['created'], again['skipped']), ([], len(keys)), code)
            rows = hr.starter_list(code, self.company.id)['rows']
            self.assertTrue(all(r['made'] for r in rows), code)
        vn = Kind.search([('pb_ls_starter_key', '=', 'VN.annual'), ('company_id', '=', self.company.id)])
        self.assertEqual(len(vn), 1)
        self.assertEqual((vn.pb_ls_earning, vn.pb_ls_days_per_year), ('monthly', 12.0))
        self.assertEqual([(s.after_years, s.extra_days) for s in vn.pb_ls_step_ids][:2],
                         [(5, 1.0), (10, 2.0)])
        sick = Kind.search([('pb_ls_starter_key', '=', 'VN.sick'), ('company_id', '=', self.company.id)])
        self.assertEqual((sick.pb_pay_treatment, sick.pb_pay_funding, sick.pb_paid_fraction),
                         ('partial', 'external', 0.75), 'paid by the insurance fund, said explicitly')
        self.assertFalse(sick.requires_allocation)
        # the drawer shows each figure's source in the reader's language
        hr_vi = hr.with_context(lang='vi_VN') if 'vi_VN' in langs else hr
        k = hr_vi.get_kind(vn.id)
        self.assertTrue(k['review'])
        self.assertTrue(k['sources'].get('days'))

    # ============================================================== R4
    def test_r4_pay_first(self):
        hr = self._as(self.hr_user)
        res = hr.starter_apply('TH', self.company.id, ['TH.maternity', 'TH.annual'])
        Kind = self.env['hr.leave.type'].with_context(active_test=False)
        mat = Kind.browse(res['created']).filtered(lambda k: k.pb_ls_starter_key == 'TH.maternity')
        with self.assertRaises(UserError):
            hr.set_active(mat.id, True)
        hr.save_kind(mat.id, {'pay': 'paid', 'funding': 'mixed', 'employer_pct': 46})
        k = hr.set_active(mat.id, True)
        self.assertEqual(k['state'], 'on')
        self.assertFalse(k['review'], 'reviewed once switched on')
        annual = Kind.browse(res['created']) - mat
        self.assertEqual(hr.set_active(annual.id, True)['state'], 'on')

    # ============================================================== R5
    def test_r5_review_list_and_refusals(self):
        hr = self._as(self.hr_user)
        with self.assertRaises(UserError):
            hr.starter_list('FR', self.company.id)
        with self.assertRaises(UserError):
            hr.starter_apply('VN', self.company.id, [])
        hr.starter_apply('ID', self.company.id, ['ID.annual'])
        rows = {r['key']: r for r in hr.starter_list('ID', self.company.id)['rows']}
        self.assertTrue(rows['ID.annual']['made'])
        self.assertFalse(rows['ID.annual']['made_on'])
        self.assertFalse(rows['ID.sick']['made'])
        self.assertTrue(rows['ID.annual']['sources'])
        self.assertTrue(rows['ID.annual']['summary'])
