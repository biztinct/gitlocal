# -*- coding: utf-8 -*-
"""WDGAP S5-F — Kinds of leave shows the customer's countries (owner rulings
LV1, LV2, 2026-11-16).

C1 the customer's countries: every company's country is one of them (and the
   countries people are paid in).
C2 the list, its steps and its "of N" hold only the home countries' kinds and
   the kinds for every country; the others are counted for the toggle.
C3 "Pay to decide" (glance and set-up check) does not count the hidden kinds.
C4 the toggle shows them all; a hidden kind still opens in the drawer.
C5 hide only: nothing archived, deleted or written by reading the screen.
C6 a policy country wins over the stock country (the offer rule's order).
C7 no company says where it is -> nothing is hidden.
C8 ready-made countries: home ones flagged, the default is a home country.
W1 India's ready-made set and each India kind carry the state warning; other
   countries carry none.
"""
from unittest.mock import patch

from odoo.fields import Domain
from odoo.tests.common import tagged

from odoo.addons.pb_leave_setup.models.leave_setup import OPEN_PAY, PbLeaveSetup

from .common import LeaveSetupCase

WARN = 'Figures differ by state — check yours before switching on'


@tagged('post_install', '-at_install', 'wdgap_s5f')
class TestHomeCountries(LeaveSetupCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Country = cls.env['res.country']
        cls.vn = Country.search([('code', '=', 'VN')], limit=1)
        cls.idn = Country.search([('code', '=', 'ID')], limit=1)
        cls.ind = Country.search([('code', '=', 'IN')], limit=1)
        Kind = cls.env['hr.leave.type'].sudo()

        def kind(name, country=False, policy=False, **kw):
            k = cls._kind(name, **kw)
            k.write({'country_id': country.id if country else False})
            k.write({'pb_policy_country_id': policy.id if policy else False})
            return k
        cls.k_vn = kind('S5F VN kind', cls.vn, pb_pay_treatment='unconfigured',
                        pb_pay_funding='unconfigured')
        cls.k_any = kind('S5F Every country kind')
        cls.k_id = kind('S5F ID kind', cls.idn, pb_pay_treatment='unconfigured',
                        pb_pay_funding='unconfigured')
        cls.k_in = kind('S5F IN kind', cls.ind)
        # stock country VN, but the policy says Indonesia: Indonesia wins
        cls.k_pol = kind('S5F VN stock, ID policy', cls.vn, cls.idn)
        cls.Kind = Kind

    def _as(self, user=None, other=False):
        env = self.env['pb.leave.setup'].with_user(user or self.hr_user).with_context(
            allowed_company_ids=[self.company.id])
        if other:
            env = env.with_context(pbf_ctx={'other': True})
        return env

    def _home(self, codes):
        return patch.object(PbLeaveSetup, '_home_countries', lambda self: set(codes))

    def _ids(self, setup, **kw):
        page = setup.get_kinds_page(search='S5F', limit=200, **kw)
        return {r['id'] for r in page['rows']}, page

    # ============================================================== C1
    def test_c1_every_company_country_is_home(self):
        home = self.env['pb.leave.setup']._home_countries()
        for company in self.env['res.company'].sudo().search([]):
            if company.country_id:
                self.assertIn(company.country_id.code, home, company.name)
        self.assertNotIn('', home)
        self.assertNotIn(False, home)

    # ============================================================== C2
    def test_c2_list_holds_home_and_every_country(self):
        with self._home({'VN'}):
            ids, page = self._ids(self._as())
            self.assertEqual(ids, {self.k_vn.id, self.k_any.id})
            self.assertEqual(page['total'], 2)
            # the toggle counts every hidden kind of the companies
            board = self._as().get_board()
            full = self.Kind.with_context(active_test=False).search_count(
                self._as()._scope())
            self.assertEqual(board['other_count'], full - board['total'])
            self.assertGreaterEqual(board['other_count'], 3)
            self.assertFalse(board['other'])
            self.assertEqual(board['home_countries'], ['VN'])
            # the filter panel's base list follows (its "of N")
            layout = self._as().pbf_layout()
            self.assertEqual(layout.get('total'), board['total'])

    # ============================================================== C3
    def test_c3_pay_to_decide_ignores_hidden_kinds(self):
        with self._home({'VN'}):
            board = self._as().get_board()
            chips = {c['id'] for c in board['checks']['pay_open']}
            self.assertNotIn(self.k_id.id, chips)
            wide = self._as().get_board(other=True)
            setup = self._as()
            hidden_open = self.Kind.with_context(active_test=False).search_count(
                Domain.AND([setup._scope(), [('active', '=', True),
                                             ('pb_policy_category', '=', False)],
                            OPEN_PAY, ~Domain(setup._home_domain())]))
            self.assertGreaterEqual(hidden_open, 1, 'the Indonesian kind at least')
            self.assertEqual(wide['kpis']['pay_open'], board['kpis']['pay_open'] + hidden_open,
                             'the amber count leaves out exactly the hidden kinds')
            page = self._as().get_kinds_page(filters={'pay': ['open'], 'state': ['on']},
                                             search='S5F')
            self.assertEqual([r['id'] for r in page['rows']], [self.k_vn.id])

    # ============================================================== C4
    def test_c4_toggle_shows_them_all_and_drawer_opens(self):
        with self._home({'VN'}):
            ids, page = self._ids(self._as(other=True))
            self.assertEqual(ids, {self.k_vn.id, self.k_any.id, self.k_id.id,
                                   self.k_in.id, self.k_pol.id})
            self.assertTrue(self._as().get_board(other=True)['other'])
            drawer = self._as().get_kind(self.k_id.id)
            self.assertEqual(drawer['id'], self.k_id.id)
            self.assertFalse(drawer['home'])
            self.assertTrue(self._as().get_kind(self.k_vn.id)['home'])

    # ============================================================== C5
    def test_c5_hide_only_nothing_written(self):
        kinds = self.k_vn | self.k_any | self.k_id | self.k_in | self.k_pol
        self.env.flush_all()
        before = [(k.id, k.active, k.country_id.id, k.pb_policy_country_id.id, k.write_date)
                  for k in kinds]
        with self._home({'VN'}):
            setup = self._as()
            setup.get_board()
            setup.get_board(other=True)
            self._ids(setup)
            self._ids(self._as(other=True))
            setup.get_kind(self.k_id.id)
        self.env.flush_all()
        kinds.invalidate_recordset()
        after = [(k.id, k.active, k.country_id.id, k.pb_policy_country_id.id, k.write_date)
                 for k in kinds]
        self.assertEqual(before, after)
        self.assertEqual(self.Kind.with_context(active_test=False).search_count(
            [('id', 'in', kinds.ids)]), 5)

    # ============================================================== C6
    def test_c6_policy_country_wins(self):
        with self._home({'ID'}):
            ids, _page = self._ids(self._as())
            self.assertIn(self.k_pol.id, ids)
            self.assertIn(self.k_id.id, ids)
            self.assertNotIn(self.k_vn.id, ids)
        with self._home({'VN'}):
            ids, _page = self._ids(self._as())
            self.assertNotIn(self.k_pol.id, ids)

    # ============================================================== C7
    def test_c7_no_country_hides_nothing(self):
        with self._home(set()):
            ids, _page = self._ids(self._as())
            self.assertEqual(len(ids), 5)
            self.assertEqual(self._as().get_board()['other_count'], 0)

    # ============================================================== C8
    def test_c8_ready_made_home_first(self):
        with self._home({'ID', 'AU'}):
            board = self._as().get_board()
            flags = {c['code']: c['home'] for c in board['options']['countries']}
            self.assertTrue(flags['ID'])
            self.assertFalse(flags['VN'])
            self.assertFalse(flags['IN'])
            if (self.env.company.country_id.code or '') not in flags:
                self.assertEqual(board['default_country'], 'ID')

    # ============================================================== W1
    def test_w1_india_warning(self):
        setup = self._as()
        self.assertEqual(setup.starter_list('IN', self.company.id)['warning'], WARN)
        for code in ('VN', 'ID', 'SG', 'TH', 'KH', 'MY'):
            self.assertFalse(setup.starter_list(code, self.company.id)['warning'], code)
        res = setup.starter_apply('IN', self.company.id, ['IN.earned', 'IN.casual'])
        for kind_id in res['created']:
            drawer = setup.get_kind(kind_id)
            self.assertEqual(drawer['warning'], WARN)
            self.assertEqual(drawer['state'], 'review', 'made switched off, waiting for review')
        self.assertFalse(setup.get_kind(self.k_in.id)['warning'],
                         'a kind HR made by hand is not a ready-made India kind')
        made = setup.starter_apply('VN', self.company.id, ['VN.annual'])['created']
        if made:
            self.assertFalse(setup.get_kind(made[0])['warning'])
