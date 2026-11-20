# -*- coding: utf-8 -*-
"""WDGAP S5-A — what the employee sees on My Leave, with a REAL employee
login (portal tier) over HTTP as well as through the facade.

P1 a kind marked "Only HR can enter this" is not offered, and cannot be
   asked for by a crafted post.
P2 a kind that builds up says what was earned so far and when the next days
   come; the page shows it.
P3 the employee page never shows another person's numbers (the override reads
   only the signed-in person's own employee).
"""
from datetime import date, timedelta

from odoo.exceptions import UserError
from odoo.tests.common import HttpCase, tagged

from .common import LeaveSetupCase


@tagged('post_install', '-at_install', 'wdgap_s5a')
class TestPortalFacade(LeaveSetupCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.open_kind = cls._kind('S5A Open kind', requires_allocation=False)
        cls.hr_kind = cls._kind('S5A HR enters it', requires_allocation=False, pb_ls_hr_only=True)

    def test_p1_hr_only_not_offered(self):
        ess = self.env['pb.ess.workforce'].with_user(self.portal_user)
        names = [t['name'] for t in ess.get_my_leave()['types']]
        self.assertIn('S5A Open kind', names)
        self.assertNotIn('S5A HR enters it', names)
        day = date.today() + timedelta(days=21)
        with self.assertRaises(UserError):
            ess.apply_leave(self.hr_kind.id, day.isoformat(), day.isoformat(), 'crafted')
        # HR still enters it from the Leave Command Center
        self.assertIn(self.hr_kind.id, [t['id'] for t in self.env['pb.timeoff'].sudo()._apply_types()])

    def test_p1b_my_leave_takes_ask_again(self):
        """WF2 P6c calls get_my_leave(again=…) from the page: this override
        must pass it through (it once dropped it, and My Leave failed for
        everybody where both modules are installed)."""
        ess = self.env['pb.ess.workforce'].with_user(self.portal_user)
        plain = [t['name'] for t in ess.get_my_leave()['types']]
        self.assertEqual([t['name'] for t in ess.get_my_leave(again=None)['types']], plain)
        res = ess.get_my_leave(again='0')
        self.assertFalse(res.get('again'))

    def test_p2_earned_so_far(self):
        today = date.today()
        first = today.replace(day=1)
        start = (first - timedelta(days=1)).replace(day=1)        # last month
        kind = self._kind('S5A Builds for me', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                          pb_ls_earn_from=start)
        self.env['pb.leave.earning'].sudo()._run_kind(kind, today, employees=self.emp_portal)
        tile = next(b for b in self.env['pb.ess.workforce'].with_user(self.portal_user)
                    .get_my_leave()['balances'] if b['id'] == kind.id)
        self.assertTrue(tile['pb_earned_label'])
        self.assertTrue(tile['pb_next_label'])
        self.assertAlmostEqual(tile['pb_earned'], 1.0 if start.year == today.year else 0.0)

    def test_p3_own_numbers_only(self):
        other = self._emp('S5A Somebody else', joined=date(2020, 1, 1))
        kind = self._kind('S5A Mine only', leave_validation_type='no_validation')
        self._alloc(other, kind, 9, date.today() - timedelta(days=10))
        tiles = self.env['pb.ess.workforce'].with_user(self.portal_user).get_my_leave()['balances']
        self.assertFalse([b for b in tiles if b['id'] == kind.id])


@tagged('post_install', '-at_install', 'wdgap_s5a')
class TestPortalHttp(HttpCase):

    def test_p4_the_page(self):
        env = self.env
        company = env.company
        user = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'S5A Http Person', 'login': 's5a.http@example.invalid',
            'email': 's5a.http@example.invalid', 'password': 's5a-http-Pass-1',
            'company_id': company.id, 'company_ids': [(6, 0, [company.id])],
            'group_ids': [(6, 0, [env.ref('base.group_portal').id])]})
        emp = env['hr.employee'].create({'name': 'S5A Http Person', 'user_id': user.id,
                                         'company_id': company.id})
        if 'date_of_joining' in emp._fields:
            emp.date_of_joining = date(2020, 1, 1)
        Kind = env['hr.leave.type'].sudo()
        today = date.today()
        start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        kind = Kind.create({'name': 'S5A Http builds', 'company_id': company.id,
                            'requires_allocation': True, 'pb_pay_treatment': 'paid',
                            'pb_pay_funding': 'employer', 'pb_ls_earning': 'monthly',
                            'pb_ls_days_per_year': 12, 'pb_ls_earn_from': start})
        kind.write({'country_id': False, 'pb_policy_country_id': False})
        hidden = Kind.create({'name': 'S5A Http hidden', 'company_id': company.id,
                              'requires_allocation': False, 'pb_ls_hr_only': True,
                              'pb_pay_treatment': 'paid', 'pb_pay_funding': 'employer'})
        hidden.write({'country_id': False, 'pb_policy_country_id': False})
        env['pb.leave.earning'].sudo()._run_kind(kind, today, employees=emp)
        self.authenticate('s5a.http@example.invalid', 's5a-http-Pass-1')
        res = self.url_open('/my/work/leave')
        self.assertEqual(res.status_code, 200)
        html = res.text
        self.assertIn('S5A Http builds', html)
        self.assertIn('pblk-earn', html)
        self.assertIn('earned so far this year', html)
        self.assertNotIn('S5A Http hidden', html)
