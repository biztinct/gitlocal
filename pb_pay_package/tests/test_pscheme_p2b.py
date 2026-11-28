# -*- coding: utf-8 -*-
"""PSCHEME P2b C — the hiring offer's default pay scheme follows the offer's
Country of work, the same answer Add employee gives.

T12 in every branch (the country's only scheme; several, the team's usual one;
several, nobody's; the country has none and the team is paid by another
country's; no country at all) the offer's first scheme equals Add employee's
"usual" scheme for the same team and country.
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install', 'pscheme', 'pscheme_p2b')
class TestOfferFollowsCountry(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vnd = cls.env.ref('base.VND')
        vnd.active = True
        cls.company = cls.env['res.company'].create({'name': 'DEMO PS2B Offer Co',
                                                     'currency_id': vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id]))
        Config = cls.env['hr.formula.config']

        def scheme(name, code, country):
            return Config.create({'name': name, 'code': code, 'cycle_type': 'end_cycle',
                                  'country_code': country, 'company_id': cls.company.id,
                                  'state': 'active'})
        cls.vn = scheme('DEMO PS2B Offer Vietnam', 'DEMOP2BOVN', 'VN')
        cls.id_a = scheme('DEMO PS2B Offer Indonesia A', 'DEMOP2BOIA', 'ID')
        cls.id_b = scheme('DEMO PS2B Offer Indonesia B', 'DEMOP2BOIB', 'ID')
        Dept = cls.env['hr.department']
        cls.lined = Dept.create({'name': 'DEMO PS2B Offer Lined', 'company_id': cls.company.id})
        cls.plain = Dept.create({'name': 'DEMO PS2B Offer Plain', 'company_id': cls.company.id})
        cls.env['hr.formula.scheme.assignment'].create({
            'config_id': cls.id_b.id, 'department_id': cls.lined.id, 'cycle_type': 'any',
            'company_id': cls.company.id})
        cls.job = cls.env['hr.job'].create({'name': 'DEMO PS2B Offer job',
                                            'company_id': cls.company.id})
        cls.n = 0

    def offer(self, dept, country_code):
        type(self).n += 1
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'DEMO PS2B Candidate %s' % self.n,
            'email_from': 'ps2b.candidate%s@example.com' % self.n,
            'job_id': self.job.id, 'company_id': self.company.id})
        country = self.env['res.country'].search([('code', '=', country_code)], limit=1) \
            if country_code else self.env['res.country']
        vals = {'title': 'DEMO PS2B Offer %s' % self.n, 'department_id': dept.id,
                'company_id': self.company.id, 'headcount': 1, 'budget_cost': 1.0,
                'requirements': 'Numbers.', 'job_id': self.job.id, 'state': 'open',
                'request_state': 'agreed', 'selected_applicant_id': applicant.id,
                'country_id': country.id or False}
        req = self.env['pb.hiring.requisition'].sudo().create(vals)
        return self.env['pb.hiring.offer'].sudo().create({
            'requisition_id': req.id, 'applicant_id': applicant.id, 'job_title': 'Analyst',
            'currency_id': self.company.currency_id.id,
            'start_date': fields.Date.context_today(self.env.user) + timedelta(days=30)})

    def first(self, offer):
        return self.env['pb.pay.package'].with_company(self.company)._offer_schemes(offer)[:1]

    def add_employee(self, dept, code):
        Hire = self.env['pb.new.hire'].with_company(self.company)
        return Hire._scheme_for({'department_id': dept.id, 'payroll_country': code})['usual']

    def test_t12_offer_equals_add_employee_in_every_branch(self):
        self.company.country_id = False
        cases = (
            ('only scheme of the country', self.plain, 'VN', self.vn),
            ('several, the team decides', self.lined, 'ID', self.id_b),
            ('several, first by name', self.plain, 'ID', self.id_a),
            ('none for the country, the team pays', self.lined, 'MY', self.id_b),
        )
        for label, dept, code, expected in cases:
            with self.subTest(label):
                got = self.first(self.offer(dept, code))
                self.assertEqual(got, expected, label)
                if 'pb.new.hire' in self.env:
                    self.assertEqual(got, self.add_employee(dept, code), label)
        # no country on the requisition: the company's country is the offer's
        self.company.country_id = self.env.ref('base.vn')
        self.assertEqual(self.first(self.offer(self.plain, '')), self.vn)

    def test_t12b_the_team_no_longer_beats_the_country(self):
        """Before P2b the team line won; a Vietnamese hire into the Indonesian
        team now gets the Vietnamese scheme by default."""
        self.assertEqual(self.first(self.offer(self.lined, 'VN')), self.vn)
