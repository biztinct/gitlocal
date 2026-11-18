# -*- coding: utf-8 -*-
"""WDGAP S2-A — form lines, the reader, the filing, the two first forms.

Numbered as the handover's test list (T1..T12; T9 has an HTTP half in
`test_s2a_access_http.py`, T13 in `test_s2a_po_gate.py`, T10/T11 partly in
pb_govt_reports / pb_hr_govt / pb_compliance_hub).

Fixture: an Indonesian company (IDR) with two pay schemes and a third scheme
in rupees mapped on purpose (two currencies), a Vietnamese company (VND), and
finished payslips written directly — lines carry the pay role and the matching
category a computed payslip would carry (ledger W2B-1); the reading is under
test, not the formula engine.
"""
import io
import json
import os
import re
from datetime import date

from lxml import etree

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools import mute_logger

HERE = os.path.dirname(os.path.abspath(__file__))
OCT = date(2026, 10, 1)
OCT_END = date(2026, 10, 31)

OFFICER = ('base.group_user,om_hr_payroll.group_hr_payroll_user,'
           'pb_hr_payroll_base.group_payroll_base_officer')
MANAGER = OFFICER + (',pb_hr_payroll_base.group_payroll_base_manager,'
                     'om_hr_payroll.group_hr_payroll_manager')


def file_text(name, raw):
    """Every text part of a file, an Excel workbook unzipped."""
    if name.endswith('.xlsx'):
        import zipfile
        z = zipfile.ZipFile(io.BytesIO(raw))
        return '\n'.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist())
    return raw.decode('utf-8', 'replace')


class S2AFixture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.idr = cls.env.ref('base.IDR')
        cls.vnd = cls.env.ref('base.VND')
        cls.inr = cls.env.ref('base.INR')
        (cls.idr | cls.vnd | cls.inr).write({'active': True})
        Company = cls.env['res.company']
        cls.co_id = Company.create({'name': 'DEMO S2A Indonesia', 'currency_id': cls.idr.id,
                                    'country_id': cls.env.ref('base.id').id})
        cls.co_vn = Company.create({'name': 'DEMO S2A Vietnam', 'currency_id': cls.vnd.id,
                                    'country_id': cls.env.ref('base.vn').id,
                                    'vat': '0101234567'})
        cls.env.user.company_ids = [(4, cls.co_id.id), (4, cls.co_vn.id)]
        cls.env.user.company_id = cls.co_id
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.co_id.id],
                                       tracking_disable=True, mail_notrack=True))
        for company in (cls.co_id, cls.co_vn):
            cls.env['biz.approval.seed'].sudo().set_no_approval_needed(company, 'filing')
        both = [(6, 0, [cls.co_id.id, cls.co_vn.id])]
        cls.officer = new_test_user(cls.env, login='s2a_officer', groups=OFFICER,
                                    company_id=cls.co_id.id, company_ids=both)
        cls.manager = new_test_user(cls.env, login='s2a_manager', groups=MANAGER,
                                    company_id=cls.co_id.id, company_ids=both)
        cls.hr_only = new_test_user(cls.env, login='s2a_hr', groups='base.group_user,hr.group_hr_user',
                                    company_id=cls.co_id.id, company_ids=both)
        cls.portal = new_test_user(cls.env, login='s2a_portal', groups='base.group_portal',
                                   company_id=cls.co_id.id, company_ids=[(6, 0, [cls.co_id.id])])
        # a line manager / plain employee login: an internal user with no group
        cls.plain = new_test_user(cls.env, login='s2a_plain', groups='base.group_user',
                                  company_id=cls.co_id.id, company_ids=both)
        # WDGAP FG1: the "Government reports" permission (pb_hr_govt), whose
        # access rows ship with pb_govt_reports
        govt = cls.env.ref('pb_hr_govt.group_pb_hr_govt_user', raise_if_not_found=False)
        cls.govt_only = new_test_user(
            cls.env, login='s2a_govt', groups='base.group_user,pb_hr_govt.group_pb_hr_govt_user',
            company_id=cls.co_id.id, company_ids=both) \
            if govt and 'pb.filing.proposal' in cls.env else None

        cls.cat_by_role = {
            'earning': cls.env.ref('om_hr_payroll.BASIC'),
            'deduction': cls.env.ref('om_hr_payroll.DED'),
            'net': cls.env.ref('om_hr_payroll.NET'),
            'employer_cost': cls.env.ref('om_hr_payroll.COMP'),
            'info': cls.env.ref('om_hr_payroll.BASIC'),
        }
        cls.salary_rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'S2A Kind'})
        cls.form_id = cls.env.ref('pb_form_lines.form_id_bpmp')
        cls.form_vn = cls.env.ref('pb_form_lines.form_vn_05kk_tt89')
        cls.form_vn80 = cls.env.ref('pb_form_lines.form_vn_05kk_tt80')
        cls.Map = cls.env['pb.gov.form.map']
        cls.Reader = cls.env['pb.gov.form.reader']

        # ---------------------------------------------------------- Indonesia
        cls.cfg = cls._config(cls.co_id, 'DEMO S2A ID Staff', 'SATID', 'ID')
        cls.r = {}
        for name, code, role, extra in (
                ('Basic salary', 'GAJI', 'earning', {}),
                ('Gross income', 'BRUTO', 'earning', {}),
                ('PPh 21', 'PAJAK', 'deduction', {}),
                ('BPJS employee', 'BPJSEE', 'deduction', {}),
                ('Net pay', 'NETPAY', 'net', {}),
                ('Status PTKP', 'PTKP', 'info', {'value_kind': 'text', 'appears_on_payslip': False}),
                ('Tax base', 'DASAR', 'info', {'appears_on_payslip': False}),
        ):
            cls.r[code] = cls._rule(cls.cfg, name, code, role, **extra)
        cls.cfg2 = cls._config(cls.co_id, 'DEMO S2A ID Directors', 'SATIDB', 'ID')
        cls.r2 = {c: cls._rule(cls.cfg2, n, c, role) for n, c, role in (
            ('Gross income', 'BRUTO', 'earning'), ('PPh 21', 'PAJAK', 'deduction'),
            ('Net pay', 'NETPAY', 'net'))}
        cls.cfg_inr = cls._config(cls.co_id, 'DEMO S2A Rupee', 'SATINR', 'IN')
        cls.r_inr = cls._rule(cls.cfg_inr, 'Gross income', 'BRUTO', 'earning')

        cls.ani = cls._person(cls.co_id, 'DEMO S2A Ani', identification_id='3172024806201234',
                              job_title='Staff')
        cls.budi = cls._person(cls.co_id, 'DEMO S2A Budi', job_title='Driver')
        cls.cici = cls._person(cls.co_id, 'DEMO S2A Cici', identification_id='3172024806205678',
                               job_title='Director')
        cls.dodi = cls._person(cls.co_id, 'DEMO S2A Dodi', identification_id='3172024806209999')
        cls.slip_ani = cls._slip(cls.co_id, cls.ani, cls.cfg, {
            'GAJI': 9_000_000, 'BRUTO': 10_000_000, 'PAJAK': -300_000,
            'BPJSEE': -100_000, 'NETPAY': 9_600_000}, inputs={'PTKP': 'K/1'},
            computed={'DASAR': 9_500_000})
        cls.slip_budi = cls._slip(cls.co_id, cls.budi, cls.cfg, {
            'BRUTO': 6_000_000, 'PAJAK': 45_000, 'NETPAY': 5_955_000},
            inputs={'PTKP': 'TK/0'}, computed={'DASAR': 5_800_000})
        cls.slip_cici = cls._slip(cls.co_id, cls.cici, cls.cfg2, {
            'BRUTO': 20_000_000, 'PAJAK': -1_500_000, 'NETPAY': 18_500_000})
        # never counted: a draft in the period, a finished payslip in November
        cls.slip_draft = cls._slip(cls.co_id, cls.dodi, cls.cfg, {
            'BRUTO': 7_000_000, 'PAJAK': -70_000}, state='draft')
        cls.slip_nov = cls._slip(cls.co_id, cls.dodi, cls.cfg, {
            'BRUTO': 8_000_000, 'PAJAK': -80_000},
            ds=date(2026, 11, 1), de=date(2026, 11, 30))

        # ---------------------------------------------------------- Vietnam
        cls.cfg_vn = cls._config(cls.co_vn, 'DEMO S2A VN', 'SATVN', 'VN')
        cls.rv = {}
        for name, code, role, extra in (
                ('Thu nhập chịu thuế', 'TNCT', 'info', {}),
                ('Thu nhập tính thuế', 'TNTT', 'info', {'appears_on_payslip': False}),
                ('Thuế TNCN', 'PIT', 'deduction', {}),
                ('Net pay', 'NETPAY', 'net', {}),
        ):
            cls.rv[code] = cls._rule(cls.cfg_vn, name, code, role, **extra)
        cls.vy = cls._person(cls.co_vn, 'DEMO S2A Vy', tax_code='8012345678')
        cls.nam = cls._person(cls.co_vn, 'DEMO S2A Nam', tax_code='8098765432', resident=False)
        cls.lan = cls._person(cls.co_vn, 'DEMO S2A Lan')
        for month in (7, 8, 9):
            ds = date(2026, month, 1)
            de = date(2026, month, 30 if month == 9 else 31)
            cls._slip(cls.co_vn, cls.vy, cls.cfg_vn, {
                'TNCT': 30_000_000, 'PIT': -2_000_000, 'NETPAY': 28_000_000},
                ds=ds, de=de, computed={'TNTT': 15_000_000})
            cls._slip(cls.co_vn, cls.nam, cls.cfg_vn, {
                'TNCT': 50_000_000, 'PIT': -10_000_000, 'NETPAY': 40_000_000},
                ds=ds, de=de, computed={'TNTT': 50_000_000})
            cls._slip(cls.co_vn, cls.lan, cls.cfg_vn, {
                'TNCT': 8_000_000, 'PIT': 0, 'NETPAY': 8_000_000},
                ds=ds, de=de, computed={'TNTT': 0})

    # ------------------------------------------------------------ fixtures
    @classmethod
    def _config(cls, company, name, code, country):
        return cls.env['hr.formula.config'].sudo().create({
            'name': name, 'code': code, 'cycle_type': 'end_cycle', 'country_code': country,
            'company_id': company.id, 'state': 'active'})

    @classmethod
    def _rule(cls, cfg, name, code, role, **extra):
        vals = {'config_id': cfg.id, 'name': name, 'code': code, 'column_type': 'input',
                'sequence': 10 + len(cfg.rule_ids), 'default_value': 0.0,
                'value_kind': 'money', 'net_role': role, 'appears_on_payslip': True,
                'category_id': cls.cat_by_role['earning'].id}
        vals.update(extra)
        return cls.env['hr.formula.rule'].sudo().create(vals)

    @classmethod
    def _person(cls, company, name, identification_id=None, job_title=None, tax_code=None,
                resident=True):
        vals = {'name': name, 'company_id': company.id}
        if identification_id:
            vals['identification_id'] = identification_id
        if job_title:
            vals['job_title'] = job_title
        Emp = cls.env['hr.employee']
        if tax_code and 'vietnam_tax_code' in Emp._fields:
            vals['vietnam_tax_code'] = tax_code
        if not resident:
            if 'pb_vn_tax_resident' in Emp._fields:
                vals['pb_vn_tax_resident'] = False
            if 'vn_residency_status' in Emp._fields:
                vals['vn_residency_status'] = 'non_resident'
        emp = Emp.sudo().create(vals)
        cls.env['hr.contract'].sudo().create({
            'name': name, 'employee_id': emp.id, 'company_id': company.id,
            'wage': 1000.0, 'state': 'open', 'date_start': '2026-01-01',
            'type_id': cls.kind.id})
        return emp

    @classmethod
    def _slip(cls, company, emp, cfg, lines, state='done', ds=OCT, de=OCT_END,
              inputs=None, computed=None):
        contract = cls.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)], limit=1)
        slip = cls.env['hr.payslip'].sudo().create({
            'name': 'S2A %s %s' % (emp.name, ds), 'employee_id': emp.id,
            'contract_id': contract.id, 'date_from': ds, 'date_to': de,
            'company_id': company.id, 'formula_config_id': cfg.id})
        rules = {r.code: r for r in cfg.rule_ids}
        vals = []
        for code, amount in lines.items():
            rule = rules[code]
            vals.append({
                'slip_id': slip.id, 'salary_rule_id': cls.salary_rule.id,
                'employee_id': emp.id, 'contract_id': contract.id,
                'category_id': cls.cat_by_role[rule.net_role].id,
                'name': rule.name, 'code': code, 'amount': amount, 'quantity': 1.0,
                'rate': 100.0, 'pay_role': rule.net_role})
        cls.env['hr.payslip.line'].sudo().create(vals)
        write = {}
        if inputs:
            write['formula_input_values'] = json.dumps(inputs)
        if computed:
            write['formula_computed_values'] = json.dumps(computed)
        if state != 'draft':
            write['state'] = state
        if write:
            slip.sudo().write(write)
        return slip

    def line(self, form, code):
        return form.line_ids.filtered(lambda l: l.code == code)

    def put(self, form, code, rule, **kw):
        vals = {'line_id': self.line(form, code).id, 'rule_id': rule.id}
        vals.update(kw)
        return self.Map.create(vals)

    def map_id(self):
        self.put(self.form_id, 'GROSS', self.r['BRUTO'])
        self.put(self.form_id, 'PPH21', self.r['PAJAK'])
        self.put(self.form_id, 'PTKP', self.r['PTKP'], source='computed_value')
        self.put(self.form_id, 'GROSS', self.r2['BRUTO'])
        self.put(self.form_id, 'PPH21', self.r2['PAJAK'])

    def map_vn(self, form=None):
        form = form or self.form_vn
        taxable, withheld = ('20', '42') if form == self.form_vn else ('21', '29')
        self.put(form, taxable, self.rv['TNCT'])
        self.put(form, withheld, self.rv['PIT'])
        if form == self.form_vn:
            self.put(form, '32', self.rv['TNTT'], source='computed_value')

    def read_id(self, **kw):
        return self.Reader._pb_read(self.form_id, self.co_id, OCT, OCT_END, **kw)

    def as_user(self, user, company=None):
        return dict(allowed_company_ids=[(company or self.co_id).id])

    def board(self, user, company=None):
        return self.env['pb.gov.form.board'].with_user(user).with_context(
            allowed_company_ids=[(company or self.co_id).id])

    def accept_settings(self, company, form, tin='0029482015507000'):
        row = self.env['pb.gov.form.company']._pb_for(form, company)
        row.write({'employer_tax_id': tin})
        return row


@tagged('post_install', '-at_install', 'wdgap_s2a')
class TestS2AFormLines(S2AFixture):

    # ================================================================ T1
    def test_t1_mapping_crud_two_lines_and_company_isolation(self):
        # one item on two lines of one form, and on a line of another form
        a = self.put(self.form_id, 'GROSS', self.r['BRUTO'])
        b = self.put(self.form_id, 'RATE', self.r['BRUTO'])
        self.assertEqual(a.company_id, self.co_id)
        self.assertEqual(a.config_id, self.cfg)
        self.assertEqual(b.form_id, self.form_id)
        # never twice on the same line
        with mute_logger('odoo.sql_db'), self.assertRaises(Exception), self.env.cr.savepoint():
            self.put(self.form_id, 'GROSS', self.r['BRUTO'])
        # a line worked out from another takes nothing
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.put(self.form_vn, '21', self.rv['TNCT'])
        # a line may take several items, through the board, as the officer
        board = self.board(self.officer)
        form = board.save_line(self.form_id.id, self.line(self.form_id, 'GROSS').id, [
            {'rule_id': self.r['BRUTO'].id, 'source': 'payslip_line'},
            {'rule_id': self.r['GAJI'].id, 'sign': 'subtract', 'share_pct': 50}])
        gross = [l for l in form['lines'] if l['code'] == 'GROSS'][0]
        self.assertEqual(sorted(i['code'] for i in gross['items']), ['BRUTO', 'GAJI'])
        gaji = [i for i in gross['items'] if i['code'] == 'GAJI'][0]
        self.assertEqual((gaji['sign'], gaji['share_pct']), ('subtract', 50))
        # update + remove
        form = board.save_line(self.form_id.id, self.line(self.form_id, 'GROSS').id,
                               [{'rule_id': self.r['BRUTO'].id}])
        gross = [l for l in form['lines'] if l['code'] == 'GROSS'][0]
        self.assertEqual([i['code'] for i in gross['items']], ['BRUTO'])
        # a pay item of another company is refused
        with self.assertRaises(UserError):
            board.save_line(self.form_id.id, self.line(self.form_id, 'PPH21').id,
                            [{'rule_id': self.rv['PIT'].id}])
        # the Vietnamese company's officer view sees none of the Indonesian rows
        self.put(self.form_vn, '42', self.rv['PIT'])
        seen = self.Map.with_user(self.officer).with_context(
            allowed_company_ids=[self.co_vn.id]).search([])
        self.assertTrue(seen)
        self.assertFalse(seen.filtered(lambda m: m.company_id == self.co_id))
        # the item is not printed → the source is the worked-out value
        self.assertEqual(self.Map._pb_default_source(self.r['DASAR']), 'computed_value')
        self.assertEqual(self.Map._pb_default_source(self.r['BRUTO']), 'payslip_line')

    # ================================================================ T2
    def test_t2_suggest_proposes_and_saves_nothing(self):
        before = self.Map.search_count([])
        props = self.board(self.officer).suggest(self.form_id.id)
        self.assertEqual(self.Map.search_count([]), before, "Suggest never saves")
        got = {(p['line_code'], p['code'], p['scheme']) for p in props}
        self.assertIn(('GROSS', 'BRUTO', self.cfg.name), got)
        self.assertIn(('PPH21', 'PAJAK', self.cfg.name), got)
        self.assertIn(('PTKP', 'PTKP', self.cfg.name), got)
        self.assertIn(('GROSS', 'BRUTO', self.cfg2.name), got)
        ptkp = [p for p in props if p['line_code'] == 'PTKP'][0]
        self.assertEqual(ptkp['source'], 'computed_value')
        # a deduction is never proposed for the gross line
        self.assertFalse([p for p in props if p['line_code'] == 'GROSS' and p['code'] == 'PAJAK'])
        # accepting saves only what was ticked
        rows = [dict(p, on=(p['line_code'] == 'PPH21')) for p in props]
        res = self.board(self.officer).accept_suggestions(self.form_id.id, rows)
        self.assertEqual(res['made'], 2)
        self.assertEqual(set(self.Map.search([('form_id', '=', self.form_id.id),
                                              ('company_id', '=', self.co_id.id)]).mapped(
            'line_id.code')), {'PPH21'})
        # Vietnam: taxable income, assessable income, tax withheld
        vn = {(p['line_code'], p['code']) for p in self.board(
            self.officer, self.co_vn).suggest(self.form_vn.id)}
        self.assertIn(('20', 'TNCT'), vn)
        self.assertIn(('42', 'PIT'), vn)
        self.assertIn(('32', 'TNTT'), vn)

    # ================================================================ T3
    def test_t3a_done_only_two_schemes_computed_value_and_sign(self):
        self.map_id()
        data = self.read_id()
        self.assertEqual(data['currency'], 'IDR')
        self.assertEqual(sorted(data['payslip_ids']),
                         sorted((self.slip_ani | self.slip_budi | self.slip_cici).ids),
                         "finished payslips of the period only — no draft, no November")
        self.assertEqual({s['id'] for s in data['schemes']}, {self.cfg.id, self.cfg2.id})
        self.assertTrue(any(w['code'] == 'unfinished' for w in data['warnings']))
        people = {e['employee_id']: e for e in data['employees']}
        self.assertEqual(set(people), {self.ani.id, self.budi.id, self.cici.id})
        # deduction counted by size: Budi's tax was written +45,000, Ani's −300,000
        self.assertEqual(people[self.ani.id]['lines']['PPH21'], 300_000)
        self.assertEqual(people[self.budi.id]['lines']['PPH21'], 45_000)
        self.assertEqual(data['lines']['PPH21'], 300_000 + 45_000 + 1_500_000)
        self.assertEqual(data['lines']['GROSS'], 10_000_000 + 6_000_000 + 20_000_000)
        # worked-out value source, text kind
        self.assertEqual(people[self.ani.id]['lines']['PTKP'], 'K/1')
        self.assertEqual(people[self.cici.id]['lines']['PTKP'], '')
        # the rate is worked out per person and from the totals
        self.assertEqual(people[self.ani.id]['lines']['RATE'], 3.0)
        self.assertEqual(data['lines']['PEOPLE'], 3)
        # a computed-value money source with a share and a sign
        self.put(self.form_id, 'GROSS', self.r['DASAR'], source='computed_value',
                 sign='subtract', share_pct=10)
        again = {e['employee_id']: e for e in self.read_id()['employees']}
        self.assertEqual(again[self.ani.id]['lines']['GROSS'], 10_000_000 - 950_000)
        # one scheme only
        only = self.read_id(scheme_ids=[self.cfg2.id])
        self.assertEqual([e['employee_id'] for e in only['employees']], [self.cici.id])
        # a scheme of the country with finished payslips and nothing mapped is named
        self.Map.search([('config_id', '=', self.cfg2.id)]).unlink()
        loose = self.read_id()
        self.assertTrue(any(w['code'] == 'scheme_not_mapped' for w in loose['warnings']))

    def test_t3b_back_pay_line_counts_by_what_it_does(self):
        Line = self.env['hr.payslip.line']
        if 'pb_backpay_band_amount' not in Line._fields:
            self.skipTest('pb_retro is not installed here')
        self.map_id()
        contract = self.slip_ani.contract_id
        # a refund of tax as back pay: printed +50,000, lowers the tax by 50,000
        Line.sudo().create({
            'slip_id': self.slip_ani.id, 'salary_rule_id': self.salary_rule.id,
            'employee_id': self.ani.id, 'contract_id': contract.id,
            'category_id': self.cat_by_role['deduction'].id, 'name': 'PPh 21 (back pay)',
            'code': 'PAJAK', 'amount': 50_000, 'quantity': 1.0, 'rate': 100.0,
            'pay_role': 'deduction', 'pb_backpay': True, 'pb_backpay_band_amount': -50_000})
        people = {e['employee_id']: e for e in self.read_id()['employees']}
        self.assertEqual(people[self.ani.id]['lines']['PPH21'], 250_000,
                         "one pay-band rule: a back-pay line counts by what it does to its total")

    def test_t3c_tax_year_boundary_for_an_april_scheme(self):
        self.cfg2.sudo().write({'tax_year_start_month': '4'})
        self.map_id()
        march = self.Reader._pb_read(self.form_id, self.co_id, date(2026, 3, 1),
                                     date(2026, 4, 30))
        self.assertEqual(march['tax_years'][self.cfg2.id]['key'], 2025)
        self.assertEqual(march['tax_years'][self.cfg.id]['key'], 2026)
        self.assertTrue(any(w['code'] == 'crosses_tax_year' for w in march['warnings']))
        april = self.Reader._pb_read(self.form_id, self.co_id, date(2026, 4, 1),
                                     date(2026, 4, 30))
        self.assertEqual(april['tax_years'][self.cfg2.id]['key'], 2026)
        self.assertEqual(april['tax_years'][self.cfg2.id]['label'], '2026–27')
        self.assertFalse(any(w['code'] == 'crosses_tax_year' for w in april['warnings']))
        # period bounds follow the scheme's tax year
        self.assertEqual(self.Reader.period_bounds(self.form_vn, date(2026, 5, 9), self.cfg2),
                         (date(2026, 4, 1), date(2026, 6, 30)))
        self.assertEqual(self.Reader.period_bounds(self.form_id, date(2026, 2, 9)),
                         (date(2026, 2, 1), date(2026, 2, 28)))

    def test_t3d_two_currencies_are_refused_or_split(self):
        self.map_id()
        self.put(self.form_id, 'GROSS', self.r_inr)
        self._slip(self.co_id, self.dodi, self.cfg_inr, {'BRUTO': 90_000})
        data = self.read_id()
        self.assertTrue(any(w['code'] == 'two_currencies' and w['level'] == 'block'
                            for w in data['warnings']))
        self.assertFalse(data['lines'], "nothing is added up across two currencies")
        self.assertEqual(sorted(data['currencies']), ['IDR', 'INR'])
        idr = self.read_id(currency_id=self.idr.id)
        self.assertEqual(idr['lines']['GROSS'], 36_000_000)
        inr = self.read_id(currency_id=self.inr.id)
        self.assertEqual(inr['lines']['GROSS'], 90_000)
        self.assertEqual([e['employee_id'] for e in inr['employees']], [self.dodi.id])
        with self.assertRaises(UserError):
            self.env['pb.gov.filing'].with_user(self.officer).with_context(
                allowed_company_ids=[self.co_id.id]).prepare(
                self.form_id, self.co_id, OCT, OCT_END)

    def test_t3e_the_contract_shape(self):
        self.map_id()
        data = self.Reader.with_user(self.officer).with_context(
            allowed_company_ids=[self.co_id.id]).read(self.form_id, self.co_id, OCT, OCT_END)
        for key in ('lines', 'employees', 'payslip_ids', 'warnings'):
            self.assertIn(key, data)
        emp = data['employees'][0]
        for key in ('employee_id', 'lines', 'identity'):
            self.assertIn(key, emp)
        for warn in data['warnings']:
            self.assertEqual(set(warn) & {'code', 'level', 'message', 'employee_ids'},
                             {'code', 'level', 'message', 'employee_ids'})
        # same answer under the other name and by form code
        self.assertEqual(self.Reader.read_form('ID_BPMP', self.co_id.id, OCT, OCT_END)['lines'],
                         data['lines'])
        with self.assertRaises(AccessError):
            self.Reader.with_user(self.hr_only).read(self.form_id, self.co_id, OCT, OCT_END)

    # ================================================================ T4
    def test_t4_indonesia_return_totals_identity_and_the_published_schema(self):
        self.map_id()
        self.accept_settings(self.co_id, self.form_id)
        filing = self.env['pb.gov.filing'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_id.id]).prepare(self.form_id, self.co_id, OCT, OCT_END)
        totals = filing.sudo()._pb_totals()
        # totals = the sum of the mapped payslip figures
        self.assertEqual(totals['GROSS'], 36_000_000)
        self.assertEqual(totals['PPH21'], 1_845_000)
        self.assertEqual(filing.row_count, 3)
        self.assertEqual(filing.total_amount, 1_845_000)
        warnings = filing.sudo()._pb_warnings()
        ident = [w for w in warnings if w['code'] == 'identity_missing']
        self.assertEqual(ident and ident[0]['employee_ids'], [self.budi.id])
        for w in warnings:
            self.assertNotIn('3172024806201234', w['message'], "no tax number in a warning")
        names = [f.name for f in filing.sudo().file_ids]
        self.assertFalse([n for n in names if 'odoo' in n.lower()])
        for f in filing.sudo().file_ids:
            self.assertNotIn('odoo', file_text(f.name, f.attachment_id.raw).lower(),
                             "white-label: %s" % f.name)
        self.assertEqual(len(names), 3)
        xml_file = filing.sudo().file_ids.filtered(lambda f: f.name.endswith('.xml'))
        xml = xml_file.attachment_id.raw
        schema = etree.XMLSchema(etree.parse(os.path.join(HERE, 'data', 'bpmp_monthlypayroll.xsd')))
        doc = etree.fromstring(xml)
        self.assertTrue(schema.validate(doc), schema.error_log)
        rows = doc.findall('.//MmPayroll')
        # Budi has no NIK and no passport, Cici's scheme carries no tax status:
        # both left out of the import file and listed on the summary
        self.assertEqual(len(rows), 1)
        ani = [r for r in rows if r.findtext('CounterpartTin') == '3172024806201234'][0]
        self.assertEqual(ani.findtext('Gross'), '10000000')
        self.assertEqual(ani.findtext('Rate'), '3')
        self.assertEqual(ani.findtext('StatusTaxExemption'), 'K/1')
        self.assertEqual(ani.findtext('Position'), 'Staff')
        self.assertEqual(ani.findtext('TaxPeriodMonth'), '10')
        self.assertEqual(ani.findtext('WithholdingDate'), '2026-10-31')
        self.assertEqual(ani.findtext('IDPlaceOfBusinessActivity'), '0029482015507000000000')
        self.assertEqual(doc.findtext('TIN'), '0029482015507000')
        # Cici has no tax status anywhere: left out too
        self.assertFalse([r for r in rows if r.findtext('CounterpartTin') == '3172024806205678'])
        # the summary workbook lists everyone with the reason
        import openpyxl
        summary = filing.sudo().file_ids.filtered(lambda f: 'summary' in f.name).attachment_id.raw
        book = openpyxl.load_workbook(io.BytesIO(summary))
        people = book.worksheets[1]
        listed = {people.cell(row=i, column=1).value: people.cell(row=i, column=9).value
                  for i in range(2, people.max_row + 1)}
        self.assertEqual(listed['DEMO S2A Budi'], 'No')
        self.assertEqual(listed['DEMO S2A Ani'], 'Yes')
        # the converter's DATA sheet, cell for cell where the tax office puts them
        data_x = filing.sudo().file_ids.filtered(lambda f: 'converter' in f.name).attachment_id.raw
        ws = openpyxl.load_workbook(io.BytesIO(data_x))['DATA']
        self.assertEqual(ws['A1'].value, 'NPWP Pemotong')
        self.assertEqual(ws['B1'].value, '0029482015507000')
        self.assertEqual([ws.cell(row=4, column=c).value for c in range(2, 15)],
                         ['Masa Pajak', 'Tahun Pajak', 'Status Pegawai', 'NPWP/NIK/TIN',
                          'Nomor Passport', 'Status', 'Posisi', 'Sertifikat/Fasilitas',
                          'Kode Objek Pajak', 'Penghasilan Kotor', 'Tarif', 'ID TKU',
                          'Tgl Pemotongan'])
        # no employer tax number → a plain refusal, nothing made
        self.env['pb.gov.form.company']._pb_for(self.form_id, self.co_id).write(
            {'employer_tax_id': ''})
        with self.assertRaises(UserError):
            self.env['pb.gov.filing'].with_user(self.officer).with_context(
                allowed_company_ids=[self.co_id.id]).prepare(self.form_id, self.co_id, OCT, OCT_END)

    # ================================================================ T5
    def test_t5_vietnam_return_totals_residents_and_counts(self):
        self.map_vn()
        q3 = (date(2026, 7, 1), date(2026, 9, 30))
        filing = self.env['pb.gov.filing'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_vn.id]).prepare(self.form_vn, self.co_vn, *q3)
        t = filing.sudo()._pb_totals()
        self.assertEqual(t['15'], 3)
        self.assertEqual(t['16'], 2)
        self.assertEqual(t['17'], 2, "Lan had no tax withheld")
        self.assertEqual((t['18'], t['19']), (1, 1))
        self.assertEqual(t['20'], 3 * (30_000_000 + 50_000_000 + 8_000_000))
        self.assertEqual(t['21'], 3 * (30_000_000 + 8_000_000))
        self.assertEqual(t['22'], 3 * 50_000_000)
        self.assertEqual(t['29'], 3 * (30_000_000 + 50_000_000))
        self.assertEqual((t['30'], t['31']), (90_000_000, 150_000_000))
        self.assertEqual(t['32'], 3 * (15_000_000 + 50_000_000))
        self.assertEqual(t['42'], 3 * (2_000_000 + 10_000_000))
        self.assertEqual((t['43'], t['44']), (6_000_000, 30_000_000))
        self.assertEqual(t['24'], 0)
        self.assertEqual(t['45'], 0)
        self.assertEqual(filing.total_amount, 36_000_000)
        warnings = filing.sudo()._pb_warnings()
        ident = [w for w in warnings if w['code'] == 'identity_missing']
        self.assertEqual(ident[0]['employee_ids'], [self.lan.id])
        import openpyxl
        raw = filing.sudo().file_ids.attachment_id.raw
        self.assertNotIn('odoo', file_text('x.xlsx', raw).lower(), "white-label")
        book = openpyxl.load_workbook(io.BytesIO(raw))
        ws = book.worksheets[0]
        cells = [ws.cell(row=r, column=c).value for r in range(1, ws.max_row + 1)
                 for c in range(1, 6)]
        self.assertIn('[42]', cells)
        row42 = [r for r in range(1, ws.max_row + 1) if ws.cell(row=r, column=3).value == '[42]'][0]
        self.assertEqual(ws.cell(row=row42, column=5).value, 36_000_000)
        self.assertIn('Quý 3 năm 2026', cells)
        self.assertIn('0101234567', cells)
        # the old layout for an older month, and each layout keeps to its own periods
        self.map_vn(self.form_vn80)
        Filing = self.env['pb.gov.filing'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_vn.id])
        with self.assertRaises(UserError):
            Filing.prepare(self.form_vn80, self.co_vn, *q3)
        with self.assertRaises(UserError):
            Filing.prepare(self.form_vn, self.co_vn, date(2026, 6, 1), date(2026, 6, 30))
        self._slip(self.co_vn, self.vy, self.cfg_vn, {'TNCT': 30_000_000, 'PIT': -2_000_000},
                   ds=date(2026, 6, 1), de=date(2026, 6, 30))
        june = Filing.prepare(self.form_vn80, self.co_vn, date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(june.sudo()._pb_totals()['29'], 2_000_000)
        self.assertEqual(june.sudo()._pb_totals()['18'], 1)

    # ================================================================ T6
    def test_t6_approval_route_decider_without_payroll_and_the_hash(self):
        if 'pb.filing.proposal' not in self.env:
            self.skipTest('pb_govt_reports (which lays the filing route) is not installed')
        from odoo.addons.pb_govt_reports.models.filing_approval import seed_all
        comp = self.env['res.company'].create({'name': 'DEMO S2A Route Co',
                                               'currency_id': self.vnd.id})
        self.env.user.company_ids = [(4, comp.id)]
        officer = new_test_user(self.env, login='s2a_route_off', groups=OFFICER,
                                company_id=comp.id, company_ids=[(6, 0, [comp.id])])
        decider = new_test_user(self.env, login='s2a_route_dec', groups='base.group_user',
                                company_id=comp.id, company_ids=[(6, 0, [comp.id])])
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'payroll_mgr')], limit=1)
        held = self.env['biz.approval.responsibility'].sudo().with_context(
            active_test=False).search([('company_id', '=', comp.id), ('role_id', '=', role.id),
                                       ('scope_key', '=', '')])
        held.unlink()
        self.env['biz.approval.responsibility'].sudo().create({
            'company_id': comp.id, 'role_id': role.id, 'scope_key': '',
            'scope_label': comp.name, 'user_id': decider.id, 'date_from': date(2020, 1, 1)})
        seed_all(self.env)
        cfg = self._config(comp, 'DEMO S2A Route VN', 'SATRT', 'VN')
        pit = self._rule(cfg, 'Thuế TNCN', 'PIT', 'deduction')
        tnct = self._rule(cfg, 'Thu nhập chịu thuế', 'TNCT', 'info')
        emp = self._person(comp, 'DEMO S2A Gil', tax_code='8011112222')
        self._slip(comp, emp, cfg, {'TNCT': 20_000_000, 'PIT': -700_000},
                   ds=date(2026, 7, 1), de=date(2026, 7, 31))
        self.put(self.form_vn, '20', tnct)
        self.put(self.form_vn, '42', pit)
        Board = self.env['pb.gov.form.board'].with_user(officer).with_context(
            allowed_company_ids=[comp.id])
        out = Board.flow_prepare(self.form_vn.id, '2026-Q3', [cfg.id])
        self.assertEqual(out['state'], 'pending', "the published route waits for its approver")
        self.assertFalse(out['downloadable'])
        filing = self.env['pb.gov.filing'].browse(out['id'])
        request = filing.sudo().approval_request_id
        self.assertEqual(request.process_id.key, 'filing', "the existing key, no second one")
        self.assertEqual(request.submitter_uid.id, officer.id)
        with self.assertRaises(UserError):
            filing.with_user(officer)._pb_download(filing.sudo().file_ids[:1].id)
        # the decider holds no payroll right and still decides (ledger W2B-2)
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.assertEqual(seat.acting_user_id, decider)
        self.assertIn(decider, filing.sudo().seat_user_ids)
        self.assertEqual(self.env['pb.gov.filing'].with_user(decider).with_context(
            allowed_company_ids=[comp.id]).search([]), filing, "a seat is also a read")
        self.env['biz.approval.engine'].with_user(decider).with_context(
            allowed_company_ids=[comp.id]).decide(request.id, step.key, 'approve', 'ok')
        filing.invalidate_recordset()
        self.assertEqual(filing.sudo().state, 'approved')
        # the decider may not download (no payroll right)
        with self.assertRaises(AccessError):
            filing.with_user(decider).with_context(allowed_company_ids=[comp.id])._pb_download(
                filing.sudo().file_ids[:1].id)
        # the officer downloads the approved bytes; the trail names the file, no tax number
        f = filing.sudo().file_ids[:1]
        name, mimetype, raw = filing.with_user(officer).with_context(
            allowed_company_ids=[comp.id])._pb_download(f.id)
        self.assertEqual(raw, f.attachment_id.raw)
        self.assertEqual(filing.sudo().downloaded_by, officer)
        notes = filing.sudo().message_ids.mapped('body')
        self.assertTrue(any(name in (b or '') for b in notes))
        self.assertFalse(any('8011112222' in (b or '') for b in notes))
        # a changed file is refused
        f.attachment_id.sudo().write({'raw': raw + b' '})
        with self.assertRaises(UserError):
            filing.with_user(officer).with_context(allowed_company_ids=[comp.id])._pb_download(f.id)
        with self.assertRaises(UserError):
            Board.download_check(filing.id, f.id)

    def test_t6b_fast_lane_prepare_approve_download(self):
        self.map_id()
        self.accept_settings(self.co_id, self.form_id)
        out = self.board(self.officer).flow_prepare(self.form_id.id, '2026-10')
        self.assertEqual(out['state'], 'approved', "'No approval needed' approves at once")
        self.assertTrue(out['downloadable'])
        self.assertEqual(len(out['files']), 3)
        self.assertTrue(self.board(self.officer).download_check(out['id'], out['files'][0]['id']))

    # ================================================================ T7
    def test_t7_prepare_again_replaces_the_previous_try(self):
        self.map_id()
        self.accept_settings(self.co_id, self.form_id)
        Filing = self.env['pb.gov.filing'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_id.id])
        first = Filing.prepare(self.form_id, self.co_id, OCT, OCT_END)
        self.env['biz.approval.engine'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_id.id]).submit(first)
        self.assertEqual(first.sudo().state, 'approved')
        second = Filing.prepare(self.form_id, self.co_id, OCT, OCT_END)
        first.invalidate_recordset()
        self.assertEqual(first.sudo().state, 'superseded')
        self.assertEqual(first.sudo().superseded_by_id, second)
        self.assertFalse(first.sudo().approved_hash)
        with self.assertRaises(UserError):
            first.with_user(self.officer)._pb_download(first.sudo().file_ids[:1].id)
        with self.assertRaises(UserError):
            self.env['biz.approval.engine'].with_user(self.officer).with_context(
                allowed_company_ids=[self.co_id.id]).submit(first)
        # another period is its own filing
        self._slip(self.co_id, self.ani, self.cfg, {'BRUTO': 10_000_000, 'PAJAK': -300_000},
                   inputs={'PTKP': 'K/1'}, ds=date(2026, 9, 1), de=date(2026, 9, 30))
        sept = Filing.prepare(self.form_id, self.co_id, date(2026, 9, 1), date(2026, 9, 30))
        second.invalidate_recordset()
        self.assertEqual(second.sudo().state, 'draft')
        self.assertNotEqual(sept, second)

    # ================================================================ T8
    def test_t8_adviser_mark_until_accepted_by_the_authority(self):
        self.map_id()
        self.accept_settings(self.co_id, self.form_id)
        Filing = self.env['pb.gov.filing'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_id.id])
        before = Filing.prepare(self.form_id, self.co_id, OCT, OCT_END)
        self.assertTrue(before.adviser_mark)
        mark = 'Check with your adviser before first filing'
        for f in before.sudo().file_ids:
            raw = f.attachment_id.raw
            text = raw.decode('utf-8') if f.name.endswith('.xml') else self._xlsx_text(raw)
            self.assertIn(mark, text, f.name)
        self.assertTrue(self.board(self.officer).get_forms()['forms'])
        card = [c for c in self.board(self.officer).get_forms()['forms']
                if c['id'] == self.form_id.id][0]
        self.assertFalse(card['accepted'])
        # an officer may not say "accepted"; a manager may, who and when kept
        with self.assertRaises(AccessError):
            self.board(self.officer).set_accepted(self.form_id.id, True)
        if self.govt_only:
            # FG1: "Accepted by the authority" stays payroll manager only
            with self.assertRaises(AccessError):
                self.board(self.govt_only).set_accepted(self.form_id.id, True)
        card = self.board(self.manager).set_accepted(self.form_id.id, True)
        self.assertTrue(card['accepted'])
        self.assertEqual(card['accepted_by'], self.manager.name)
        row = self.env['pb.gov.form.company']._pb_for(self.form_id, self.co_id)
        self.assertEqual(row.accepted_by, self.manager)
        self.assertTrue(row.accepted_on)
        after = Filing.prepare(self.form_id, self.co_id, OCT, OCT_END)
        self.assertFalse(after.adviser_mark)
        for f in after.sudo().file_ids:
            raw = f.attachment_id.raw
            text = raw.decode('utf-8') if f.name.endswith('.xml') else self._xlsx_text(raw)
            self.assertNotIn(mark, text, f.name)
        # the Vietnamese company is a company of its own: still marked
        self.assertFalse(self.env['pb.gov.form.company']._pb_is_accepted(self.form_id, self.co_vn))
        # unticking is allowed and written down
        self.board(self.manager).set_accepted(self.form_id.id, False)
        self.assertFalse(row.accepted)
        self.assertFalse(row.accepted_by)
        self.assertTrue(any('took back' in (b or '') for b in row.message_ids.mapped('body')))

    @staticmethod
    def _xlsx_text(raw):
        import openpyxl
        book = openpyxl.load_workbook(io.BytesIO(raw))
        out = []
        for ws in book.worksheets:
            for row in ws.iter_rows(values_only=True):
                out.extend(str(v) for v in row if v is not None)
        return '\n'.join(out)

    # ================================================================ T9 (RPC)
    def test_t9_access_officer_and_manager_yes_hr_and_portal_no(self):
        """The access matrix. Yes: payroll officer, payroll manager and (WDGAP
        FG1) the Government reports permission. No: HR without either,
        a plain internal login (line manager), portal."""
        self.map_id()
        allowed = [self.officer, self.manager] + ([self.govt_only] if self.govt_only else [])
        for user in allowed:
            self.assertTrue(self.board(user).get_forms()['forms'], user.login)
            self.board(user).get_form(self.form_id.id)
            self.board(user).flow_check(self.form_id.id, '2026-10')
            self.assertTrue(self.Reader.with_user(user).with_context(
                allowed_company_ids=[self.co_id.id]).read(self.form_id, self.co_id, OCT, OCT_END))
        for user in (self.hr_only, self.portal, self.plain):
            board = self.board(user)
            for call in (lambda: board.get_forms(),
                         lambda: board.get_form(self.form_id.id),
                         lambda: board.suggest(self.form_id.id),
                         lambda: board.flow_check(self.form_id.id, '2026-10'),
                         lambda: board.flow_prepare(self.form_id.id, '2026-10')):
                with self.assertRaises(AccessError), self.env.cr.savepoint():
                    call()
            self.env.flush_all()
            self.env.invalidate_all()
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                self.env['pb.gov.form.map'].with_user(user).with_context(
                    allowed_company_ids=[self.co_id.id]).search([]).read(['rule_id'])
        # a filing is out of reach for HR without payroll
        self.accept_settings(self.co_id, self.form_id)
        out = self.board(self.officer).flow_prepare(self.form_id.id, '2026-10')
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertFalse(self.env['pb.gov.filing'].with_user(self.hr_only).with_context(
            allowed_company_ids=[self.co_id.id]).search([('id', '=', out['id'])]))
        filing = self.env['pb.gov.filing'].browse(out['id'])
        for user in (self.hr_only, self.plain):
            with self.assertRaises(AccessError):
                filing.with_user(user)._pb_download(out['files'][0]['id'])
        if self.govt_only:
            # FG1: download follows the lens — the approved bytes, logged
            Filing = self.env['pb.gov.filing'].with_user(self.govt_only).with_context(
                allowed_company_ids=[self.co_id.id])
            self.assertEqual(Filing.search([('id', '=', out['id'])]).id, out['id'])
            name, _mime, raw = Filing.browse(out['id'])._pb_download(out['files'][0]['id'])
            self.assertTrue(raw)
            # …and may prepare one too (generate = lens)
            again = self.board(self.govt_only).flow_prepare(self.form_id.id, '2026-10')
            self.assertEqual(again['state'], 'approved')
        # the Filings board shows the tiles to the officer only
        Gov = self.env.get('pb.govt.reports')
        if Gov is not None:
            data = Gov.with_user(self.officer).with_context(
                allowed_company_ids=[self.co_id.id]).get_govt_reports_data('ID')
            self.assertTrue(data['forms'])
            self.assertTrue(data['available'])

    # ================================================================ T12
    def test_t12_install_is_silent(self):
        mod = self.env['ir.module.module'].search([('name', '=', 'pb_form_lines')])
        self.assertEqual(mod.state, 'installed')
        # the company the database started with (a local walk may have added
        # its own DEMO companies and filings since — ledger S8D-6)
        main = self.env.ref('base.main_company')
        self.assertFalse(self.env['pb.gov.form.map'].sudo().search(
            [('company_id', '=', main.id)]), "install maps nothing")
        self.assertFalse(self.env['pb.gov.filing'].sudo().search(
            [('company_id', '=', main.id)]), "install files nothing")
        self.assertFalse(self.env['pb.gov.form.company'].sudo().search(
            [('company_id', '=', main.id)]), "no company setting is made by install")
        self.assertFalse(self.env['biz.approval.request'].sudo().search(
            [('res_model', '=', 'pb.gov.filing'), ('company_id', '=', main.id)]),
            "nothing in the Approvals inbox")
        crons = self.env['ir.cron'].sudo().with_context(active_test=False).search([])
        ours = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'pb_form_lines'), ('model', '=', 'ir.cron')])
        self.assertFalse(ours, "no scheduled job")
        self.assertFalse(crons.filtered(lambda c: c.model_id.model and c.model_id.model.startswith('pb.gov.')))
        templates = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'pb_form_lines'), ('model', 'in', ('mail.template', 'ir.cron'))])
        self.assertFalse(templates, "nothing that sends")
        # the catalogue is data, kept on upgrade
        data = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'pb_form_lines'), ('model', 'in', ('pb.gov.form', 'pb.gov.form.line'))])
        self.assertTrue(data)
        self.assertTrue(all(d.noupdate for d in data))

    # ================================================================ sources
    def test_every_form_names_its_source(self):
        for form in self.env['pb.gov.form'].sudo().search([]):
            self.assertTrue(form.source_note and form.source_url, form.code)
            if form.inferred:
                self.assertTrue(form.inferred_note, form.code)
            self.assertTrue(hasattr(self.env['pb.gov.filing'],
                                    '_pb_render_%s' % form.code.lower()), form.code)
