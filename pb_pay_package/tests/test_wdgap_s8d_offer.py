# -*- coding: utf-8 -*-
"""WDGAP S8-D (owner ruling SC3) — "Build from a total" on a Hiring offer.

O1  the India-shaped DEMO scheme (built whole in the test, PRE-2): an offer of
    ₹12,00,000 a year, basic 50% → basic 50,000, HRA 20,000, special 28,200,
    employer PF 1,800; "Use these figures" writes them as the offer's monthly
    lines (the scheme's own "Employer cost" total line NOT counted again), the
    offer totals 1,00,000 a month; a yearly bonus line stays; old monthly pay
    lines go.
O2  the offer letter's table shows basic pay and the allowances.
O3  joining: the contract starts on basic pay 50,000 and the special
    allowance 28,200 as a contract pay line (logged "From offer …", dated the
    start); HRA is worked out by the scheme, not written.
O4  an offer without it is exactly as before: the wage is the biggest monthly
    earning and no pay line is written.
O5  plain refusals: a scheme without the lines needed, an offer in another
    money, an offer already sent for sign-off; a plain user is refused.
O6  read-only: opening and working out write nothing.
"""
import re
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.sql_db import Cursor
from odoo.tests import TransactionCase, tagged


@contextmanager
def no_writes():
    seen = []
    real = Cursor.execute

    def execute(self, query, params=None, log_exceptions=True):
        text = str(query.code if hasattr(query, 'code') else query).lstrip().lower()
        if text.startswith(('insert', 'update', 'delete')):
            seen.append(text[:100])
        return real(self, query, params, log_exceptions)
    with patch.object(Cursor, 'execute', execute):
        yield seen


@tagged('post_install', '-at_install', 'wdgap_s8d')
class TestS8dOfferTotal(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.inr = cls.env.ref('base.INR')
        cls.inr.active = True
        cls.company = cls.env.company
        cls.recruiter = cls.env['res.users'].create({
            'name': 'S8D Recruiter', 'login': 's8d_recruiter',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id,
                                  cls.env.ref('pb_hiring.group_hiring_user').id])]})
        cls.Package = cls.env['pb.pay.package'].with_user(cls.recruiter).with_context(
            allowed_company_ids=[cls.company.id])
        cls.cfg = cls._india(cls)
        dept = cls.env['hr.department'].create({'name': 'S8D Bengaluru',
                                                'company_id': cls.company.id})
        job = cls.env['hr.job'].create({'name': 'S8D Analyst', 'company_id': cls.company.id,
                                        'department_id': dept.id})
        cls.dept, cls.job = dept, job
        cls._n = 0

    @staticmethod
    def _india(self, with_ercost=True):
        Rule = self.env['hr.formula.rule']

        def rule(cfg, code, name, kind, formula=None, role=False, seq=10, on_slip=True):
            vals = {'config_id': cfg.id, 'code': code, 'name': name, 'column_type': kind,
                    'sequence': seq, 'appears_on_payslip': on_slip, 'net_role': role}
            if formula:
                vals['excel_formula'] = formula
            return Rule.create(vals)
        cfg = self.env['hr.formula.config'].create({
            'name': 'S8D India demo', 'code': 'SEIGHTDIN', 'country_code': 'IN',
            'state': 'active', 'company_id': self.env.company.id, 'currency_id': self.inr.id})
        b = rule(cfg, 'BASIC', 'Basic + DA', 'input', role='earning', seq=10).column_letter
        hra = rule(cfg, 'HRA', 'House rent allowance', 'formula', '=%s*0.4' % b,
                   role='earning', seq=20)
        spl = rule(cfg, 'SPECIAL', 'Special allowance', 'input', role='earning', seq=30)
        spl.is_contract_component = True
        gross = rule(cfg, 'GROSS', 'Gross pay', 'formula',
                     '=%s+%s+%s' % (b, hra.column_letter, spl.column_letter), role='info', seq=40)
        g = gross.column_letter
        base = rule(cfg, 'EPFBASE', 'PF wage', 'formula', '=MIN(%s,15000)' % b,
                    role='info', seq=50, on_slip=False)
        epf = rule(cfg, 'EPFDED', 'Provident fund', 'formula', '=%s*0.12' % base.column_letter,
                   role='deduction', seq=60)
        epfc = rule(cfg, 'EPFCOMP', 'Employer provident fund', 'formula',
                    '=%s*0.12' % base.column_letter, role='employer_cost', seq=70)
        esic = rule(cfg, 'ESICOMP', 'Employer health insurance', 'formula',
                    '=IF(%s<=21000,%s*0.0325,0)' % (g, g), role='employer_cost', seq=80)
        if with_ercost:
            rule(cfg, 'ERCOST', 'Employer cost', 'formula',
                 '=%s+%s+%s' % (g, epfc.column_letter, esic.column_letter),
                 role='employer_cost', seq=90)
        rule(cfg, 'NETPAY', 'Take-home', 'formula', '=%s-%s' % (g, epf.column_letter),
             role='net', seq=100)
        return cfg

    def _offer(self, currency=None, lines=True):
        type(self)._n += 1
        applicant = self.env['hr.applicant'].create({
            'partner_name': 'S8D Candidate %s' % self._n,
            'email_from': 's8d.candidate%s@example.com' % self._n,
            'job_id': self.job.id, 'company_id': self.company.id})
        req = self.env['pb.hiring.requisition'].sudo().create({
            'title': 'S8D Analyst %s' % self._n, 'department_id': self.dept.id,
            'company_id': self.company.id, 'headcount': 1, 'budget_cost': 1.0,
            'requirements': 'Numbers.', 'job_id': self.job.id, 'state': 'open',
            'request_state': 'agreed', 'selected_applicant_id': applicant.id,
            'recruiter_id': self.recruiter.id} if 'recruiter_id' in
            self.env['pb.hiring.requisition']._fields else {
            'title': 'S8D Analyst %s' % self._n, 'department_id': self.dept.id,
            'company_id': self.company.id, 'headcount': 1, 'budget_cost': 1.0,
            'requirements': 'Numbers.', 'job_id': self.job.id, 'state': 'open',
            'request_state': 'agreed', 'selected_applicant_id': applicant.id})
        offer = self.env['pb.hiring.offer'].sudo().create({
            'requisition_id': req.id, 'applicant_id': applicant.id,
            'job_title': 'Analyst', 'currency_id': (currency or self.inr).id,
            'start_date': fields.Date.context_today(self.env.user) + timedelta(days=30)})
        if lines:
            Line = self.env['pb.hiring.offer.line'].sudo()
            for name, kind, amount, period in (('Basic pay', 'earning', 60_000.0, 'monthly'),
                                               ('Joining bonus', 'bonus', 50_000.0, 'yearly')):
                Line.create({'offer_id': offer.id, 'name': name, 'kind': kind,
                             'amount': amount, 'period': period})
        return offer

    def _args(self, **kw):
        args = dict(total=1_200_000, period='year', basic_mode='share', basic_value=50,
                    basic_code='BASIC', balance_code='SPECIAL', config_id=self.cfg.id)
        args.update(kw)
        return args

    # ================================================================ O1
    def test_o1_split_written_as_the_offers_lines(self):
        offer = self._offer()
        ctx = self.Package.offer_open(offer.id, self.cfg.id)
        self.assertTrue(ctx.get('ok'), ctx)
        self.assertEqual((ctx['basic'], ctx['balance']), ('BASIC', 'SPECIAL'))
        out = self.Package.offer_solve(offer.id, **self._args())
        self.assertEqual(out['outcome'], 'exact', out.get('sentence'))
        self.assertAlmostEqual(out['value'], 28_200.0, delta=0.5)
        self.assertTrue(out['can_use'])
        res = self.Package.offer_use(offer.id, **self._args())
        self.assertTrue(res['ok'])
        offer.invalidate_recordset()
        lines = {l.name: l for l in offer.line_ids}
        self.assertEqual(lines['Basic + DA'].amount, 50_000.0)
        self.assertTrue(lines['Basic + DA'].pb_item_wage)
        self.assertEqual(lines['House rent allowance'].amount, 20_000.0)
        self.assertFalse(lines['House rent allowance'].pb_item_code,
                         "worked out by the scheme, never written on a contract")
        self.assertAlmostEqual(lines['Special allowance'].amount, 28_200.0, delta=0.5)
        self.assertEqual(lines['Special allowance'].pb_item_code, 'SPECIAL')
        self.assertEqual(lines['Employer provident fund'].kind, 'statutory')
        self.assertEqual(lines['Employer provident fund'].amount, 1_800.0)
        self.assertNotIn('Employer cost', lines, "the total line is not counted again")
        self.assertNotIn('Gross pay', lines)
        self.assertNotIn('Basic pay', lines, "the old monthly pay line is replaced")
        self.assertEqual(lines['Joining bonus'].amount, 50_000.0, "a yearly bonus stays")
        self.assertAlmostEqual(offer.monthly_total, 100_000.0, delta=1.0,
                               msg="a month of it = the total package a month")
        self.assertEqual(offer.pb_total_config_id, self.cfg)
        self.assertIn('12,00,000', offer.pb_total_note.replace('1,200,000', '12,00,000'))
        row = self.env['pb.hiring'].with_user(self.recruiter)._offer_row(offer, full=True)
        self.assertEqual(row['total_note'], offer.pb_total_note)

    # ================================================================ O2
    def test_o2_letter_shows_basic_and_allowances(self):
        offer = self._offer()
        self.Package.offer_use(offer.id, **self._args())
        table = str(offer._lines_table())
        for name in ('Basic + DA', 'House rent allowance', 'Special allowance',
                     'Employer provident fund'):
            self.assertIn(name, table)

    # ================================================================ O3
    def test_o3_joining_starts_the_contract_on_the_split(self):
        offer = self._offer()
        self.Package.offer_use(offer.id, **self._args())
        emp = self.env['hr.employee'].create({'name': 'S8D Joiner',
                                              'company_id': self.company.id})
        offer.sudo().write({'employee_id': emp.id})
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.create_contract', '1')
        contract = offer._ensure_contract()
        self.assertTrue(contract)
        self.assertEqual(contract.wage, 50_000.0, "the wage is the basic pay line")
        lines = {l.advantage_template_id.code: l.amount for l in
                 self.env['hr.contract.advantage'].sudo().search(
                     [('contract_id', '=', contract.id)])}
        self.assertAlmostEqual(lines.get('SPECIAL', 0.0), 28_200.0, delta=0.5)
        self.assertNotIn('HRA', lines)
        rows = self.env['hr.contract.advantage.change'].sudo().search(
            [('contract_id', '=', contract.id), ('advantage_template_code', '=', 'SPECIAL')])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.effective_date, contract.date_start)
        self.assertIn(offer.name, rows.notes or '')
        # twice is once
        self.assertEqual(offer._ensure_contract(), contract)
        self.assertEqual(len(self.env['hr.contract.advantage.change'].sudo().search(
            [('contract_id', '=', contract.id), ('advantage_template_code', '=', 'SPECIAL')])), 1)

    # ================================================================ O4
    def test_o4_an_offer_without_it_is_as_before(self):
        offer = self._offer()
        self.assertEqual(offer._basic_line().amount, 60_000.0)
        emp = self.env['hr.employee'].create({'name': 'S8D Plain joiner',
                                              'company_id': self.company.id})
        offer.sudo().write({'employee_id': emp.id})
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.create_contract', '1')
        contract = offer._ensure_contract()
        self.assertEqual(contract.wage, 60_000.0)
        self.assertFalse(self.env['hr.contract.advantage'].sudo().search(
            [('contract_id', '=', contract.id)]), "no pay line is written")
        self.assertFalse(offer.pb_total_note)

    # ================================================================ O5
    def test_o5_plain_refusals(self):
        offer = self._offer()
        thin = self.env['hr.formula.config'].create({
            'name': 'S8D thin', 'code': 'SEIGHTDTHIN', 'country_code': 'IN', 'state': 'active',
            'company_id': self.company.id, 'currency_id': self.inr.id})
        self.env['hr.formula.rule'].create({'config_id': thin.id, 'code': 'BASIC',
                                            'name': 'Basic', 'column_type': 'input',
                                            'net_role': 'earning'})
        answer = self.Package.offer_open(offer.id, thin.id)
        self.assertFalse(answer['ok'])
        self.assertIn('does not have the pay items', answer['msg'])
        dollars = self._offer(currency=self.env.ref('base.USD'))
        answer = self.Package.offer_solve(dollars.id, **self._args())
        self.assertFalse(answer['ok'])
        self.assertIn('pays in INR', answer['msg'])
        offer.sudo().state = 'submitted'
        with self.assertRaises(UserError):
            self.Package.offer_use(offer.id, **self._args())
        plain = self.env['res.users'].create({
            'name': 'S8D plain', 'login': 's8d_plain_offer', 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]})
        with self.assertRaises(AccessError):
            self.env['pb.pay.package'].with_user(plain).offer_open(offer.id, self.cfg.id)

    # ================================================================ O6
    def test_o6_open_and_solve_write_nothing(self):
        offer = self._offer()
        self.env.flush_all()
        with no_writes() as seen:
            self.Package.offer_open(offer.id, self.cfg.id)
            self.Package.offer_solve(offer.id, **self._args())
        self.assertFalse([s for s in seen if 'ir_' not in s[:40]], seen)
