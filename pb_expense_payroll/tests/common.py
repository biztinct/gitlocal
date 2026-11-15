# -*- coding: utf-8 -*-
"""Fixtures for WDGAP S6-C (claims paid in pay).

A company of its own (VND, ₫1) with three month-end schemes and a mid-month
one, every payslip computed through the real engine (`compute_sheet`):

    S6C Classified (pay roles on every line):
        BASIC     input    earning     (the contract wage)
        TAX       formula  deduction   =BASIC*0.1   (a "tax" on pay)
        NETPAY    formula  net         =BASIC-TAX
    S6C Plain (an older scheme: NO pay roles, categories BASIC / DED / NET):
        BASIC / TAX / NET (same formulas, code NET)
    S6C Advance (mid-month): BASIC / NETPAY

Claims are made under sudo as a person's own (an employee LOGIN — a portal
user — for the page tests) and approved through the real engine with "No
approval needed" published for the company.
"""
import base64
import json
from unittest.mock import patch

from odoo.tests import TransactionCase

from odoo.addons.pb_me_portal.tests.test_portal_accounts import _make_share

PNG = base64.b64decode(
    b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==')


class ClaimsPayMixin:

    @classmethod
    def _s6c_fixture(cls):
        vnd = cls.env.ref('base.VND')
        vnd.active = True
        cls.vnd = vnd
        cls.company = cls.env['res.company'].create(
            {'name': 'S6C Claims Co', 'currency_id': vnd.id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        for process in ('expense', 'runonly', 'loads', 'records', 'schememap'):
            try:
                cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, process)
            except Exception:   # noqa: BLE001
                pass
        Cat = cls.env['hr.salary.rule.category']
        cls.cat = {code: (Cat.search([('code', '=', code)], limit=1)
                          or Cat.create({'name': code.title(), 'code': code}))
                   for code in ('BASIC', 'DED', 'NET', 'ALW', 'GROSS')}
        cls.classified = cls._scheme('S6C Classified', 'S6CCLASS', 'end_cycle', roles=True)
        cls.plain = cls._scheme('S6C Plain', 'S6CPLAIN', 'end_cycle', roles=False)
        cls.mid = cls._scheme('S6C Advance', 'S6CMID', 'mid_cycle', roles=True)
        cls.calendar = cls.company.resource_calendar_id or cls.env['resource.calendar'].create(
            {'name': 'S6C Hours', 'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'S6C Kind'})
        cls.share, cls.ann = _make_share(cls.env, 's6c_ann', 'S6C Ann Share')
        cls.ann.company_id = cls.company
        cls.bob = cls.env['hr.employee'].create({'name': 'S6C Bob', 'company_id': cls.company.id})
        cls.contracts = {e.id: cls._contract(e, 10_000_000.0) for e in (cls.ann, cls.bob)}
        Product = cls.env['product.product']
        cls.meals = Product.create({'name': 'S6C Meals', 'can_be_expensed': True,
                                    'standard_price': 0.0})
        cls.taxi = Product.create({'name': 'S6C Taxi', 'can_be_expensed': True,
                                   'standard_price': 0.0})

    # ------------------------------------------------------------ fixtures
    @classmethod
    def _scheme(cls, name, code, cycle, roles=True):
        cfg = cls.env['hr.formula.config'].create({
            'name': name, 'code': code, 'cycle_type': cycle, 'country_code': 'VN',
            'company_id': cls.company.id, 'state': 'active'})
        net_code = 'NETPAY' if roles else 'NET'
        for vals in (
                ('Basic salary', 'BASIC', 'earning', 1, 'input', None, 'BASIC'),
                ('Income tax', 'TAX', 'deduction', 5, 'formula', '=BASIC*0.1', 'DED'),
                ('Take-home', net_code, 'net', 20, 'formula', '=BASIC-TAX', 'NET')):
            rname, rcode, role, seq, kind, formula, cat = vals
            rule = {'config_id': cfg.id, 'name': rname, 'code': rcode, 'column_type': kind,
                    'sequence': seq, 'default_value': 0.0, 'value_kind': 'money',
                    'appears_on_payslip': True, 'category_id': cls.cat[cat].id}
            if roles:
                rule['net_role'] = role
            if formula:
                rule['excel_formula'] = formula
            cls.env['hr.formula.rule'].create(rule)
        if not roles:
            # an older scheme: nothing on it carries a pay role
            cfg.rule_ids.write({'net_role': False})
        return cfg

    @classmethod
    def _contract(cls, employee, wage):
        return cls.env['hr.contract'].create({
            'name': 'S6C contract %s' % employee.name, 'employee_id': employee.id,
            'company_id': cls.company.id, 'wage': wage, 'state': 'open',
            'date_start': '2026-01-01', 'resource_calendar_id': cls.calendar.id,
            'type_id': cls.kind.id})

    # ------------------------------------------------------------ helpers
    def set_route(self, route):
        self.company.pb_claims_paid_by = route

    def claim(self, employee=None, amounts=(300_000,), card=(), approve=True,
              product=None, trip=None, day='2026-03-05'):
        """A claim of `employee` with one receipt per amount (receipts whose
        index is in `card` were paid with a company card)."""
        employee = employee or self.ann
        claim = self.env['pb.expense.claim'].sudo().create(
            {'employee_id': employee.id, 'company_id': self.company.id})
        for i, amount in enumerate(amounts):
            exp = self.env['hr.expense'].sudo().with_company(self.company).create({
                'name': 'S6C receipt %s' % i, 'employee_id': employee.id,
                'company_id': self.company.id, 'product_id': (product or self.meals).id,
                'currency_id': self.vnd.id, 'total_amount_currency': amount,
                'date': day,
                'payment_mode': 'company_account' if i in card else 'own_account',
                'pb_claim_id': claim.id})
            if trip is not None:
                exp.pb_trip_id = trip.id
            att = self.env['ir.attachment'].sudo().create({
                'name': 'r.png', 'datas': base64.b64encode(PNG), 'mimetype': 'image/png',
                'res_model': 'hr.expense', 'res_id': exp.id})
            exp._message_set_main_attachment_id(att, force=True)
        if approve:
            claim.expense_ids.write({'approval_state': 'submitted', 'manager_id': False})
            claim.action_submit()
            claim.invalidate_recordset()
            self.assertEqual(claim.state, 'approved', 'no-approval route: approved at once')
            claim.sudo().write({'decided_on': '2026-03-10 09:00:00'})
        return claim

    def make_run(self, cfg=None, ds='2026-03-01', de='2026-03-31', name='S6C March',
                 kind='regular'):
        Run = self.env['hr.payslip.run']
        vals = {'name': name, 'date_start': ds, 'date_end': de,
                'pb_formula_config_id': (cfg or self.classified).id, 'pb_run_kind': kind}
        if 'company_id' in Run._fields:
            vals['company_id'] = self.company.id
        return Run.create(vals)

    def slip(self, employee=None, run=None, cfg=None, compute=True):
        employee = employee or self.ann
        run = run if run is not None else self.make_run(cfg)
        vals = {'name': 'S6C %s' % employee.name, 'employee_id': employee.id,
                'contract_id': self.contracts[employee.id].id,
                'date_from': run.date_start if run else '2026-03-01',
                'date_to': run.date_end if run else '2026-03-31',
                'company_id': self.company.id,
                'formula_config_id': (cfg or self.classified).id,
                'calculation_method': 'formula'}
        if run:
            vals['payslip_run_id'] = run.id
        slip = self.env['hr.payslip'].create(vals)
        if compute:
            slip.compute_sheet()
        return slip

    def shape(self, slip):
        """Every line of a payslip as plain data (the golden comparison)."""
        slip.invalidate_recordset()
        return sorted(
            (l.code, l.name, l.sequence, round(l.amount, 2), round(l.total, 2),
             l.category_id.code, l.pay_role or False, bool(l.component_detail))
            for l in slip.line_ids)

    def golden(self, slip):
        """The same payslip computed again with this module's step switched
        off — what the engine alone makes."""
        Slip = type(self.env['hr.payslip'])
        with patch.object(Slip, '_pb_extras_apply', lambda s: None):
            slip.compute_sheet()
        return self.shape(slip), slip.formula_computed_values, slip.formula_input_values

    def line(self, slip, code):
        return slip.line_ids.filtered(lambda l: l.code == code)

    def live(self, claim):
        return claim.pb_payline_ids.filtered(lambda l: l.state in ('reserved', 'paid'))

    def note(self, slip):
        return json.loads(slip.pb_extras_note or 'null') or {}


class ClaimsPayFixture(ClaimsPayMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._s6c_fixture()
