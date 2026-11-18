# -*- coding: utf-8 -*-
"""WDGAP S2-B2 — fund files outside Vietnam on the S2-A engine.

Numbered as the handover's S2-B2 test list (T1..T10; T6 — the Vietnamese
social-insurance reports — lives in pb_hr_govt `test_wdgap_s2b2_items`, T11 is
the browser walk, T12 the S2-A suites).

Fixture: one Indonesian (IDR), one Indian (INR) and one Singaporean (SGD)
company, each with its own pay scheme, and finished October 2026 payslips
written directly (lines carry the pay role and the category it implies —
ledger W2B-1). Member numbers that no field holds on this database (the UAN
and ESI number come with Step 2 phase S2-D's module) are given to the probe
by patching it — the probe itself is tested on a field that exists.
"""
import io
import json
import re
from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_lines.models.fund_sg import RECORD

OCT = date(2026, 10, 1)
OCT_END = date(2026, 10, 31)
OFFICER = ('base.group_user,om_hr_payroll.group_hr_payroll_user,'
           'pb_hr_payroll_base.group_payroll_base_officer')
MANAGER = OFFICER + (',pb_hr_payroll_base.group_payroll_base_manager,'
                     'om_hr_payroll.group_hr_payroll_manager')

#: member numbers kept nowhere on this database, by employee name
FAKE_NUMBERS = {}


def xlsx_rows(raw, sheet=0):
    import openpyxl
    book = openpyxl.load_workbook(io.BytesIO(raw))
    ws = book.worksheets[sheet] if isinstance(sheet, int) else book[sheet]
    return [list(r) for r in ws.iter_rows(values_only=True)]


def xlsx_text(raw):
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(raw))
    return '\n'.join(z.read(n).decode('utf-8', 'replace') for n in z.namelist())


class S2B2Fixture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cur = {c: cls.env.ref('base.%s' % c) for c in ('IDR', 'INR', 'SGD')}
        for c in cur.values():
            c.active = True
        Company = cls.env['res.company']
        cls.co_id = Company.create({'name': 'DEMO S2B2 Indonesia', 'currency_id': cur['IDR'].id})
        cls.co_in = Company.create({'name': 'DEMO S2B2 India', 'currency_id': cur['INR'].id})
        cls.co_sg = Company.create({'name': 'DEMO S2B2 Singapore', 'currency_id': cur['SGD'].id})
        cls.cos = cls.co_id | cls.co_in | cls.co_sg
        cls.env.user.company_ids = [(4, c.id) for c in cls.cos]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=cls.cos.ids,
                                       tracking_disable=True, mail_notrack=True))
        for company in cls.cos:
            cls.env['biz.approval.seed'].sudo().set_no_approval_needed(company, 'filing')
        all_cos = [(6, 0, cls.cos.ids)]
        cls.officer = new_test_user(cls.env, login='s2b2_officer', groups=OFFICER,
                                    company_id=cls.co_id.id, company_ids=all_cos)
        cls.manager = new_test_user(cls.env, login='s2b2_manager', groups=MANAGER,
                                    company_id=cls.co_id.id, company_ids=all_cos)
        cls.hr_only = new_test_user(cls.env, login='s2b2_hr', groups='base.group_user,hr.group_hr_user',
                                    company_id=cls.co_id.id, company_ids=all_cos)
        cls.portal = new_test_user(cls.env, login='s2b2_portal', groups='base.group_portal',
                                   company_id=cls.co_id.id, company_ids=[(6, 0, [cls.co_id.id])])
        cls.cat = {'earning': cls.env.ref('om_hr_payroll.BASIC'),
                   'deduction': cls.env.ref('om_hr_payroll.DED'),
                   'net': cls.env.ref('om_hr_payroll.NET'),
                   'employer_cost': cls.env.ref('om_hr_payroll.COMP'),
                   'info': cls.env.ref('om_hr_payroll.BASIC')}
        cls.salary_rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'S2B2 Kind'})
        cls.Map = cls.env['pb.gov.form.map']
        cls.forms = {code: cls.env['pb.gov.form'].search([('code', '=', code)])
                     for code in ('ID_BPJS_TK', 'ID_BPJS_KES', 'IN_EPF_ECR', 'IN_ESI',
                                  'SG_CPF_EZPAY', 'VN_SI_ITEMS')}
        Emp = cls.env['hr.employee']
        cls.has_bpjs = 'pb_bpjs_employment_number' in Emp._fields

        # ---------------------------------------------------------- Indonesia
        cls.cfg_id = cls._config(cls.co_id, 'DEMO S2B2 ID', 'SBID', 'ID')
        cls.rid = {code: cls._rule(cls.cfg_id, name, code, role) for name, code, role in (
            ('Upah BPJS', 'UPAHB', 'info'), ('JHT karyawan', 'JHTK', 'deduction'),
            ('JHT perusahaan', 'JHTP', 'employer_cost'), ('JKK', 'JKK', 'employer_cost'),
            ('JKM', 'JKM', 'employer_cost'), ('JP karyawan', 'JPK', 'deduction'),
            ('JP perusahaan', 'JPP', 'employer_cost'),
            ('BPJS Kesehatan karyawan', 'KESK', 'deduction'),
            ('BPJS Kesehatan perusahaan', 'KESP', 'employer_cost'),
            ('Net pay', 'NETPAY', 'net'))}
        ani_vals = {'identification_id': '3172024806201234', 'birthday': date(1990, 5, 4)}
        budi_vals = {'identification_id': '3172024806205678', 'birthday': date(1988, 1, 2)}
        if cls.has_bpjs:
            ani_vals.update(pb_bpjs_employment_number='20012345678',
                            pb_bpjs_health_number='0001234567890')
            budi_vals.update(pb_bpjs_health_number='0009876543210')
        cls.ani = cls._person(cls.co_id, 'DEMO S2B2 Ani', **ani_vals)
        cls.budi = cls._person(cls.co_id, 'DEMO S2B2 Budi', **budi_vals)
        for emp, wage in ((cls.ani, 10_000_000), (cls.budi, 6_000_000)):
            cls._slip(cls.co_id, emp, cls.cfg_id, {
                'UPAHB': wage, 'JHTK': -wage * 0.02, 'JHTP': wage * 0.037, 'JKK': wage * 0.0024,
                'JKM': wage * 0.003, 'JPK': -wage * 0.01, 'JPP': wage * 0.02,
                'KESK': -wage * 0.01, 'KESP': wage * 0.04, 'NETPAY': wage * 0.96})

        # ---------------------------------------------------------- India
        cls.cfg_in = cls._config(cls.co_in, 'DEMO S2B2 IN', 'SBIN', 'IN')
        cls.rin = {code: cls._rule(cls.cfg_in, name, code, role) for name, code, role in (
            ('Gross wages', 'GROSSW', 'earning'), ('PF wages', 'PFW', 'info'),
            ('EPS wages', 'EPSW', 'info'), ('EDLI wages', 'EDLIW', 'info'),
            ('PF employee', 'PFEE', 'deduction'), ('EPS employer', 'EPSER', 'employer_cost'),
            ('PF employer', 'PFER', 'employer_cost'), ('NCP days', 'NCP', 'info'),
            ('ESI wages', 'ESIW', 'info'), ('ESI employee', 'ESIEE', 'deduction'),
            ('ESI employer', 'ESIER', 'employer_cost'), ('Paid days', 'PAIDD', 'info'),
            ('Net pay', 'NETPAY', 'net'))}
        cls.arjun = cls._person(cls.co_in, 'DEMO S2B2 Arjun')
        cls.priya = cls._person(cls.co_in, 'DEMO S2B2 Priya')
        cls.dev = cls._person(cls.co_in, 'DEMO S2B2 Dev')       # no UAN, no ESI number
        FAKE_NUMBERS.update({cls.arjun.id: {'uan': '100200300400', 'esi': '3100123456'},
                             cls.priya.id: {'uan': '100200300401', 'esi': '3100123457'}})
        cls._slip(cls.co_in, cls.arjun, cls.cfg_in, {
            'GROSSW': 25_000.40, 'PFW': 15_000, 'EPSW': 15_000, 'EDLIW': 15_000,
            'PFEE': -1_800.50, 'EPSER': 1_249.50, 'PFER': 550.49, 'NCP': 2,
            'ESIW': 20_000, 'ESIEE': -150, 'ESIER': 650, 'PAIDD': 29.5, 'NETPAY': 23_000})
        cls._slip(cls.co_in, cls.priya, cls.cfg_in, {
            'GROSSW': 18_000, 'PFW': 15_000, 'EPSW': 15_000, 'EDLIW': 15_000,
            'PFEE': -1_800, 'EPSER': 1_250, 'PFER': 550, 'NCP': 0,
            'ESIW': 18_000, 'ESIEE': -135, 'ESIER': 585, 'PAIDD': 31, 'NETPAY': 16_000})
        cls._slip(cls.co_in, cls.dev, cls.cfg_in, {
            'GROSSW': 30_000, 'PFW': 15_000, 'EPSW': 15_000, 'EDLIW': 15_000,
            'PFEE': -1_800, 'EPSER': 1_250, 'PFER': 550, 'NCP': 0,
            'ESIW': 0, 'ESIEE': 0, 'ESIER': 0, 'PAIDD': 31, 'NETPAY': 28_000})

        # ---------------------------------------------------------- Singapore
        cls.cfg_sg = cls._config(cls.co_sg, 'DEMO S2B2 SG', 'SBSG', 'SG')
        cls.rsg = {code: cls._rule(cls.cfg_sg, name, code, role) for name, code, role in (
            ('Ordinary wages', 'OWG', 'earning'), ('Additional wages', 'AWG', 'earning'),
            ('CPF employee', 'CPFE', 'deduction'), ('CPF employer', 'CPFR', 'employer_cost'),
            ('SDL', 'SDLV', 'employer_cost'), ('CDAC', 'CDACF', 'deduction'),
            ('MBMF', 'MBMFF', 'deduction'), ('Net pay', 'NETPAY', 'net'))}
        cls.tan = cls._person(cls.co_sg, 'DEMO S2B2 Tan Ah Kow', identification_id='S1122334A')
        cls.siti = cls._person(cls.co_sg, 'DEMO S2B2 Siti binte Ali', identification_id='T0123456B')
        cls.raj = cls._person(cls.co_sg, 'DEMO S2B2 Raj', identification_id='G1234567X')
        cls.lim = cls._person(cls.co_sg, 'DEMO S2B2 Lim')   # pays CPF, no NRIC on record
        cls._slip(cls.co_sg, cls.tan, cls.cfg_sg, {
            'OWG': 3_000, 'AWG': 0, 'CPFE': -600, 'CPFR': 510, 'SDLV': 7.50, 'CDACF': -1.00,
            'NETPAY': 2_399})
        cls._slip(cls.co_sg, cls.siti, cls.cfg_sg, {
            'OWG': 4_000, 'AWG': 1_000, 'CPFE': -1_000, 'CPFR': 850, 'SDLV': 11.25,
            'MBMFF': -19.50, 'NETPAY': 3_980.50})
        cls._slip(cls.co_sg, cls.raj, cls.cfg_sg, {
            'OWG': 6_000, 'SDLV': 11.25, 'NETPAY': 6_000})
        cls._slip(cls.co_sg, cls.lim, cls.cfg_sg, {
            'OWG': 2_000, 'CPFE': -400, 'CPFR': 340, 'SDLV': 5.00, 'NETPAY': 1_600})
        # contract dates: Siti joined in October
        cls.env['hr.contract'].search([('employee_id', '=', cls.siti.id)]).date_start = date(2026, 10, 6)

    # ------------------------------------------------------------ fixtures
    @classmethod
    def _config(cls, company, name, code, country):
        return cls.env['hr.formula.config'].sudo().create({
            'name': name, 'code': code, 'cycle_type': 'end_cycle', 'country_code': country,
            'company_id': company.id, 'state': 'active'})

    @classmethod
    def _rule(cls, cfg, name, code, role):
        return cls.env['hr.formula.rule'].sudo().create({
            'config_id': cfg.id, 'name': name, 'code': code, 'column_type': 'input',
            'sequence': 10 + len(cfg.rule_ids), 'default_value': 0.0, 'value_kind': 'money',
            'net_role': role, 'appears_on_payslip': True,
            'category_id': cls.cat['earning'].id})

    @classmethod
    def _person(cls, company, name, **vals):
        emp = cls.env['hr.employee'].sudo().create(dict(vals, name=name, company_id=company.id))
        cls.env['hr.contract'].sudo().create({
            'name': name, 'employee_id': emp.id, 'company_id': company.id, 'wage': 1000.0,
            'state': 'open', 'date_start': '2026-01-01', 'type_id': cls.kind.id})
        return emp

    @classmethod
    def _slip(cls, company, emp, cfg, lines, state='done'):
        contract = cls.env['hr.contract'].sudo().search([('employee_id', '=', emp.id)], limit=1)
        slip = cls.env['hr.payslip'].sudo().create({
            'name': 'S2B2 %s' % emp.name, 'employee_id': emp.id, 'contract_id': contract.id,
            'date_from': OCT, 'date_to': OCT_END, 'company_id': company.id,
            'formula_config_id': cfg.id})
        rules = {r.code: r for r in cfg.rule_ids}
        cls.env['hr.payslip.line'].sudo().create([{
            'slip_id': slip.id, 'salary_rule_id': cls.salary_rule.id, 'employee_id': emp.id,
            'contract_id': contract.id, 'category_id': cls.cat[rules[code].net_role].id,
            'name': rules[code].name, 'code': code, 'amount': amount, 'quantity': 1.0,
            'rate': 100.0, 'pay_role': rules[code].net_role} for code, amount in lines.items()])
        if state != 'draft':
            slip.sudo().write({'state': state})
        return slip

    def put(self, form_code, line_code, rule, **kw):
        form = self.forms[form_code]
        line = form.line_ids.filtered(lambda l: l.code == line_code)
        return self.Map.create(dict(kw, line_id=line.id, rule_id=rule.id))

    def map_all(self):
        r = self.rid
        for line, code in (('WAGE', 'UPAHB'), ('JHT_EE', 'JHTK'), ('JHT_ER', 'JHTP'),
                           ('JKK_ER', 'JKK'), ('JKM_ER', 'JKM'), ('JP_EE', 'JPK'),
                           ('JP_ER', 'JPP')):
            self.put('ID_BPJS_TK', line, r[code])
        for line, code in (('WAGE', 'UPAHB'), ('KES_EE', 'KESK'), ('KES_ER', 'KESP')):
            self.put('ID_BPJS_KES', line, r[code])
        r = self.rin
        for line, code in (('GROSS', 'GROSSW'), ('EPF_WAGES', 'PFW'), ('EPS_WAGES', 'EPSW'),
                           ('EDLI_WAGES', 'EDLIW'), ('EPF_EE', 'PFEE'), ('EPS_ER', 'EPSER'),
                           ('DIFF_ER', 'PFER'), ('NCP_DAYS', 'NCP')):
            self.put('IN_EPF_ECR', line, r[code])
        for line, code in (('DAYS', 'PAIDD'), ('WAGES', 'ESIW'), ('ESI_EE', 'ESIEE'),
                           ('ESI_ER', 'ESIER')):
            self.put('IN_ESI', line, r[code])
        r = self.rsg
        for line, code in (('OW', 'OWG'), ('AW', 'AWG'), ('CPF_EE', 'CPFE'), ('CPF_ER', 'CPFR'),
                           ('SDL', 'SDLV'), ('CDAC', 'CDACF'), ('MBMF', 'MBMFF')):
            self.put('SG_CPF_EZPAY', line, r[code])

    def settings(self, form_code, company, number):
        row = self.env['pb.gov.form.company']._pb_for(self.forms[form_code], company)
        row.write({'employer_tax_id': number})
        return row

    def board(self, user, company):
        return self.env['pb.gov.form.board'].with_user(user).with_context(
            allowed_company_ids=[company.id])

    def prepare(self, form_code, company, user=None):
        Filing = self.env['pb.gov.filing'].with_user(user or self.officer).with_context(
            allowed_company_ids=[company.id])
        with self.india_numbers():
            return Filing.prepare(self.forms[form_code], company, OCT, OCT_END)

    def india_numbers(self):
        """The UAN / ESI number of the Indian fixture people, as a field of
        S2-D's module would give them to the probe."""
        Reader = type(self.env['pb.gov.form.reader'])
        original = Reader._pb_probe

        def probe(reader, employee, names, contract_names=()):
            nums = FAKE_NUMBERS.get(employee.id) or {}
            if 'pb_in_uan_number' in names:
                return nums.get('uan', '')
            if 'pb_in_esi_number' in names:
                return nums.get('esi', '')
            return original(reader, employee, names, contract_names)
        return patch.object(Reader, '_pb_probe', probe)

    @staticmethod
    def files(filing):
        return {f.name: f.attachment_id.raw for f in filing.sudo().file_ids}


@tagged('post_install', '-at_install', 'wdgap_s2b2')
class TestS2B2FundFiles(S2B2Fixture):

    # ================================================================ T1
    def test_t1_totals_are_the_mapped_payslip_figures_shares_apart(self):
        if not self.has_bpjs:
            self.skipTest('pb_employee_vault (BPJS numbers) is not installed here')
        self.map_all()
        # Indonesia — BPJS Ketenagakerjaan (Budi has no KPJ number: T4)
        tk = self.prepare('ID_BPJS_TK', self.co_id)
        t = tk.sudo()._pb_totals()
        self.assertEqual(t['WAGE'], 16_000_000)
        self.assertAlmostEqual(t['EE_TOTAL'], 480_000, places=2, msg="JHT 2% + JP 1%, employee")
        self.assertAlmostEqual(t['ER_TOTAL'], 16_000_000 * (0.037 + 0.0024 + 0.003 + 0.02), places=2)
        self.assertAlmostEqual(t['TOTAL'], t['EE_TOTAL'] + t['ER_TOTAL'], places=2)
        self.assertAlmostEqual(tk.total_amount, t['TOTAL'], places=2)
        upload = [n for n in self.files(tk) if 'upah' in n][0]
        rows = xlsx_rows(self.files(tk)[upload])
        self.assertEqual(rows[0], ['NIK', 'NO KPJ', 'NAMA LENGKAP', 'TGL LAHIR', 'UPAH', 'BLN/THN'])
        self.assertEqual(rows[1], ['3172024806201234', '20012345678', 'DEMO S2B2 ANI',
                                   '04-05-1990', 10_000_000, '10-2026'])
        self.assertEqual(len(rows), 2, "only Ani: Budi has no BPJS Ketenagakerjaan number")
        # Indonesia — BPJS Kesehatan: both have a card
        kes = self.prepare('ID_BPJS_KES', self.co_id)
        t = kes.sudo()._pb_totals()
        for code, want in (('KES_EE', 160_000), ('KES_ER', 640_000), ('TOTAL', 800_000)):
            self.assertAlmostEqual(t[code], want, places=2)
        data = xlsx_rows([raw for n, raw in self.files(kes).items() if 'summary' not in n][0])
        self.assertEqual(data[1][5:], [100_000, 400_000, 500_000])
        self.assertEqual(len(data), 3)
        # India — ESI: Dev has no ESI number
        esi = self.prepare('IN_ESI', self.co_in)
        t = esi.sudo()._pb_totals()
        self.assertEqual((t['ESI_EE'], t['ESI_ER'], t['TOTAL']), (285, 1_235, 1_520))
        sheet = xlsx_rows([raw for n, raw in self.files(esi).items() if 'summary' not in n][0])
        self.assertEqual(sheet[0][0], 'IP Number (10 Digits)')
        got = {r[0]: r for r in sheet[1:]}
        self.assertEqual(got['3100123456'][2:5], [30, 20_000, 0],
                         "29.5 days paid → 30 whole days, wages as read, reason 0")
        self.assertEqual(set(got), {'3100123456', '3100123457'})
        # Singapore — CPF: employee and employer apart on the filing
        self.settings('SG_CPF_EZPAY', self.co_sg, '234567891APTE01')
        cpf = self.prepare('SG_CPF_EZPAY', self.co_sg)
        t = cpf.sudo()._pb_totals()
        for code, want in (('CPF_EE', 2_000), ('CPF_ER', 1_700), ('SDL', 35.0),
                           ('EE_TOTAL', 2_020.50), ('ER_TOTAL', 1_735.0)):
            self.assertAlmostEqual(t[code], want, places=2, msg=code)

    # ================================================================ T2
    def test_t2_epf_ecr_fields_order_separator_and_whole_rupees(self):
        self.map_all()
        ecr = self.prepare('IN_EPF_ECR', self.co_in)
        name = [n for n in self.files(ecr) if n.endswith('.txt')][0]
        text = self.files(ecr)[name].decode('ascii')
        self.assertTrue(text.endswith('\n'))
        lines = text.splitlines()
        self.assertEqual(len(lines), 2, "no header line; Dev has no UAN and is left out")
        fields_ = [l.split('#~#') for l in lines]
        for f in fields_:
            self.assertEqual(len(f), 11)
            for value in f[2:]:
                self.assertRegex(value, r'^\d+$', "whole numbers only")
        arjun = [f for f in fields_ if f[0] == '100200300400'][0]
        self.assertEqual(arjun, ['100200300400', 'DEMO S2B2 Arjun', '25000', '15000', '15000',
                                 '15000', '1801', '1250', '550', '2', '0'],
                         "UAN, name, gross, EPF, EPS, EDLI, EE, EPS, diff, NCP, refund; half up")
        self.assertFalse(re.search(r'odoo', name + text, re.I))

    # ================================================================ T3
    def test_t3_cpf_file_record_lengths_counts_and_totals(self):
        self.map_all()
        self.settings('SG_CPF_EZPAY', self.co_sg, '234567891APTE01')
        cpf = self.prepare('SG_CPF_EZPAY', self.co_sg)
        name = [n for n in self.files(cpf) if n.endswith('.DTL')][0]
        self.assertEqual(name, '234567891APTE01OCT202601.DTL')
        raw = self.files(cpf)[name]
        recs = raw.decode('ascii').split('\r\n')
        self.assertEqual(recs[-1], '', "every record ends with CR LF")
        recs = recs[:-1]
        for rec in recs:
            self.assertEqual(len(rec), RECORD)
            self.assertFalse(set(rec) & set('_+$<>:;?!=[]`^|"~'))
        head, trail = recs[0], recs[-1]
        self.assertEqual(head[:20], 'F 234567891APTE01 01')
        self.assertEqual(head[34:47], 'FTP.DTL'.ljust(13))
        self.assertRegex(head[20:34], r'^\d{14}$')
        summaries = [r for r in recs if r[1] == '0']
        self.assertEqual([r[26:28] for r in summaries], ['01', '02', '03', '04', '05', '10', '11'])
        amount = {r[26:28]: int(r[28:40]) for r in summaries}
        donors = {r[26:28]: int(r[40:47]) for r in summaries}
        # CPF = Tan 600+510 + Siti 1000+850 (Lim left out, Raj pays none)
        self.assertEqual(amount['01'], (1_110 + 1_850) * 100)
        self.assertEqual((amount['02'], donors['02']), (1_950, 1))
        self.assertEqual((amount['04'], donors['04']), (100, 1))
        self.assertEqual((amount['03'], donors['03']), (0, 0))
        self.assertEqual(amount['11'], int((7.50 + 11.25 + 11.25) * 100),
                         "SDL of everyone in the file, Raj (no CPF) included")
        details = [r for r in recs if r[1] == '1']
        self.assertEqual([(r[28:37], r[26:28]) for r in details],
                         [('S1122334A', '01'), ('S1122334A', '04'),
                          ('T0123456B', '01'), ('T0123456B', '02')],
                         "sorted by CPF account number, then payment code")
        tan = details[0]
        self.assertEqual(int(tan[37:49]), 111_000)
        self.assertEqual(int(tan[49:59]), 300_000)
        self.assertEqual(int(tan[59:69]), 0)
        self.assertEqual(tan[69], 'E')
        self.assertEqual(tan[70:136].rstrip(), 'DEMO S2B2 TAN AH KOW')
        siti = details[2]
        self.assertEqual(siti[69], 'N', "joined in October")
        self.assertEqual(int(siti[59:69]), 100_000)
        self.assertEqual(details[1][69], ' ', "a fund record has no status")
        self.assertEqual(trail[:20], 'F9234567891APTE01 01')
        self.assertEqual(int(trail[20:27]), len(recs))
        self.assertEqual(int(trail[27:42]), sum(amount.values()))
        # no submission number → plain refusal, nothing made
        self.settings('SG_CPF_EZPAY', self.co_sg, '')
        with self.assertRaises(UserError):
            self.prepare('SG_CPF_EZPAY', self.co_sg)

    # ================================================================ T4
    def test_t4_missing_member_number_left_out_with_the_reason(self):
        self.map_all()
        self.settings('SG_CPF_EZPAY', self.co_sg, '234567891APTE01')
        ecr = self.prepare('IN_EPF_ECR', self.co_in)
        t = ecr.sudo()._pb_totals()
        self.assertAlmostEqual(t['GROSS'], 73_000.40, places=2, msg="the reading keeps everyone")
        summary = [raw for n, raw in self.files(ecr).items() if 'summary' in n][0]
        rows = xlsx_rows(summary)
        flat = [str(c) for r in rows for c in r if c is not None]
        self.assertIn('1 person is left out of the file. Their figures are not in the file\'s totals.', flat)
        self.assertTrue(any('DEMO S2B2 Dev' == r[0] and 'No UAN' in (r[1] or '') for r in rows))
        gross = [r for r in rows if r[0] and str(r[0]).startswith('GROSS')][0]
        self.assertAlmostEqual(gross[1], 73_000.40, places=2)
        self.assertAlmostEqual(gross[2], 43_000.40, places=2,
                               msg="everyone read vs in the file: Dev's 30,000 left out")
        people = xlsx_rows(summary, 'People')
        dev = [r for r in people if r[0] == 'DEMO S2B2 Dev'][0]
        self.assertEqual(dev[-2], 'No')
        # the reader warns, by name count, never with a number
        self.assertTrue(any(w['code'] == 'identity_missing' for w in ecr.sudo()._pb_warnings()))
        # Singapore: Lim pays CPF but has no CPF account number
        cpf = self.prepare('SG_CPF_EZPAY', self.co_sg)
        rows = xlsx_rows([raw for n, raw in self.files(cpf).items() if n.endswith('.xlsx')][0])
        self.assertTrue(any(r[0] == 'DEMO S2B2 Lim' and 'CPF account number' in (r[1] or '')
                            for r in rows))
        self.assertFalse(any(r[0] == 'DEMO S2B2 Raj' and r[1] for r in rows if r[0]),
                         "Raj pays no CPF: not left out, nothing to say")
        # the check step says who is left out and the file's total without them
        with self.india_numbers():
            check = self.board(self.officer, self.co_in).flow_check(
                self.forms['IN_EPF_ECR'].id, '2026-10')
        left = [w for w in check['warnings'] if w['code'] == 'fund_left_out']
        self.assertEqual(len(left), 1)
        self.assertEqual(left[0]['employee_ids'], [self.dev.id])
        self.assertIn('No UAN', left[0]['message'])
        # nobody with a number → a plain refusal
        FAKE_NUMBERS_SAVED = dict(FAKE_NUMBERS)
        try:
            FAKE_NUMBERS.clear()
            with self.assertRaises(UserError), self.env.cr.savepoint():
                self.prepare('IN_EPF_ECR', self.co_in)
        finally:
            FAKE_NUMBERS.update(FAKE_NUMBERS_SAVED)

    # ================================================================ T5
    def test_t5_fund_payments_total_beside_the_file_equal_and_different(self):
        if 'pb.fund.payee' not in self.env:
            self.skipTest('pb_fund_payments is not installed')
        self.map_all()
        form = self.forms['IN_ESI']
        Payee = self.env['pb.fund.payee'].sudo()
        payee = Payee.create({'name': 'DEMO ESIC', 'company_id': self.co_in.id, 'item_ids': [
            (0, 0, {'rule_id': self.rin['ESIEE'].id, 'share': 'employee'}),
            (0, 0, {'rule_id': self.rin['ESIER'].id, 'share': 'employer'})]})
        board = self.board(self.officer, self.co_in)

        def compare():
            with self.india_numbers():
                out = board.flow_check(form.id, '2026-10')
            return [w for w in out['warnings'] if w['code'] == 'fund_payments']

        # not worked out yet: read the way Fund payments would, said so; same total
        got = compare()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]['level'], 'info')
        self.assertIn('the same as this file', got[0]['message'])
        self.assertIn('has not worked out this month yet', got[0]['message'])
        # worked out — then a pay item Fund payments counts that the file leaves out
        self.env['pb.fund.payment'].sudo().with_context(
            allowed_company_ids=[self.co_in.id]).pb_work_out(OCT, self.co_in)
        got = compare()
        self.assertNotIn('has not worked out', got[0]['message'])
        self.assertIn('the same as this file', got[0]['message'])
        payee.write({'item_ids': [(0, 0, {'rule_id': self.rin['PFEE'].id, 'share': 'employee'})]})
        self.env['pb.fund.payment'].sudo().with_context(
            allowed_company_ids=[self.co_in.id]).pb_work_out(OCT, self.co_in)
        got = compare()
        self.assertEqual(got[0]['level'], 'warn')
        self.assertIn('They differ by', got[0]['message'])
        # read only: nothing written to Fund payments by the check
        before = self.env['pb.fund.payment'].sudo().search_count([])
        compare()
        self.assertEqual(self.env['pb.fund.payment'].sudo().search_count([]), before)

    # ================================================================ T7
    def test_t7_route_approved_bytes_only_and_a_trail_without_numbers(self):
        if 'pb.filing.proposal' not in self.env:
            self.skipTest('pb_govt_reports (which lays the filing route) is not installed')
        from odoo.addons.pb_govt_reports.models.filing_approval import seed_all
        comp = self.env['res.company'].create({'name': 'DEMO S2B2 Route Co',
                                               'currency_id': self.env.ref('base.SGD').id})
        self.env.user.company_ids = [(4, comp.id)]
        officer = new_test_user(self.env, login='s2b2_route_off', groups=OFFICER,
                                company_id=comp.id, company_ids=[(6, 0, [comp.id])])
        decider = new_test_user(self.env, login='s2b2_route_dec', groups='base.group_user',
                                company_id=comp.id, company_ids=[(6, 0, [comp.id])])
        role = self.env['biz.approval.role'].sudo().search([('key', '=', 'payroll_mgr')], limit=1)
        self.env['biz.approval.responsibility'].sudo().with_context(active_test=False).search(
            [('company_id', '=', comp.id), ('role_id', '=', role.id), ('scope_key', '=', '')]).unlink()
        self.env['biz.approval.responsibility'].sudo().create({
            'company_id': comp.id, 'role_id': role.id, 'scope_key': '', 'scope_label': comp.name,
            'user_id': decider.id, 'date_from': date(2020, 1, 1)})
        seed_all(self.env)
        cfg = self._config(comp, 'DEMO S2B2 Route SG', 'SBRT', 'SG')
        ee = self._rule(cfg, 'CPF employee', 'CPFE', 'deduction')
        er = self._rule(cfg, 'CPF employer', 'CPFR', 'employer_cost')
        ow = self._rule(cfg, 'Ordinary wages', 'OWG', 'earning')
        emp = self._person(comp, 'DEMO S2B2 Wei', identification_id='S7654321Z')
        self._slip(comp, emp, cfg, {'OWG': 5_000, 'CPFE': -1_000, 'CPFR': 850})
        self.put('SG_CPF_EZPAY', 'OW', ow)
        self.put('SG_CPF_EZPAY', 'CPF_EE', ee)
        self.put('SG_CPF_EZPAY', 'CPF_ER', er)
        self.settings('SG_CPF_EZPAY', comp, '201912345KPTE01')
        board = self.board(officer, comp)
        out = board.flow_prepare(self.forms['SG_CPF_EZPAY'].id, '2026-10', [cfg.id])
        self.assertEqual(out['state'], 'pending')
        filing = self.env['pb.gov.filing'].browse(out['id'])
        request = filing.sudo().approval_request_id
        self.assertEqual(request.process_id.key, 'filing', "the existing key, no second one")
        f = filing.sudo().file_ids[:1]
        with self.assertRaises(UserError):
            filing.with_user(officer).with_context(allowed_company_ids=[comp.id])._pb_download(f.id)
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.env['biz.approval.engine'].with_user(decider).with_context(
            allowed_company_ids=[comp.id]).decide(request.id, step.key, 'approve', 'ok')
        filing.invalidate_recordset()
        self.assertEqual(filing.sudo().state, 'approved')
        name, _mime, raw = filing.with_user(officer).with_context(
            allowed_company_ids=[comp.id])._pb_download(f.id)
        self.assertEqual(raw, f.attachment_id.raw)
        notes = ' '.join(b or '' for b in filing.sudo().message_ids.mapped('body'))
        self.assertIn(name, notes)
        self.assertNotIn('S7654321Z', notes, "no member number in the trail")
        trail = self.env['biz.audit.entry'].sudo().search([('model_name', '=', 'pb.gov.filing'),
                                                           ('res_id', '=', filing.id)]) \
            if 'biz.audit.entry' in self.env else self.env['res.partner']
        for entry in trail:
            self.assertNotIn('S7654321Z', entry.new_value or '')
        f.attachment_id.sudo().write({'raw': raw + b' '})
        with self.assertRaises(UserError):
            filing.with_user(officer).with_context(allowed_company_ids=[comp.id])._pb_download(f.id)

    # ================================================================ T8 (RPC)
    def test_t8_access_officer_and_manager_yes_hr_and_portal_no(self):
        self.map_all()
        form = self.forms['SG_CPF_EZPAY']
        self.settings('SG_CPF_EZPAY', self.co_sg, '234567891APTE01')
        for user in (self.officer, self.manager):
            card = self.board(user, self.co_sg).get_form(form.id)
            self.assertEqual(card['section'], 'fund')
            self.assertEqual(card['adviser_text'], 'Check with the fund before the first upload')
        for user in (self.hr_only, self.portal):
            board = self.board(user, self.co_sg)
            for call in (lambda: board.get_forms(), lambda: board.get_form(form.id),
                         lambda: board.flow_check(form.id, '2026-10'),
                         lambda: board.flow_prepare(form.id, '2026-10')):
                with self.assertRaises(AccessError), self.env.cr.savepoint():
                    call()
        out = self.board(self.officer, self.co_sg).flow_prepare(form.id, '2026-10')
        filing = self.env['pb.gov.filing'].browse(out['id'])
        self.env.flush_all()
        self.env.invalidate_all()
        with self.assertRaises(AccessError):
            filing.with_user(self.hr_only).with_context(
                allowed_company_ids=[self.co_sg.id])._pb_download(out['files'][0]['id'])
        self.assertFalse(self.env['pb.gov.filing'].with_user(self.hr_only).with_context(
            allowed_company_ids=[self.co_sg.id]).search([('id', '=', filing.id)]))
        # the Filings board: a "Fund files" group for the officer, none for HR
        Gov = self.env.get('pb.govt.reports')
        if Gov is not None:
            data = Gov.with_user(self.officer).with_context(
                allowed_company_ids=[self.co_sg.id]).get_govt_reports_data('SG')
            groups = {g['key']: g for g in data['form_groups']}
            self.assertEqual([f['code'] for f in groups['fund']['forms']], ['SG_CPF_EZPAY'])
            self.assertTrue(groups['fund']['label'])
            other = Gov.with_user(self.hr_only).with_context(
                allowed_company_ids=[self.co_sg.id]).get_govt_reports_data('SG')
            self.assertEqual(other['form_groups'], [])

    # ================================================================ adviser
    def test_adviser_note_says_fund_until_accepted(self):
        self.map_all()
        self.settings('SG_CPF_EZPAY', self.co_sg, '234567891APTE01')
        before = self.prepare('SG_CPF_EZPAY', self.co_sg)
        self.assertTrue(before.adviser_mark)
        summary = [raw for n, raw in self.files(before).items() if n.endswith('.xlsx')][0]
        self.assertEqual(xlsx_rows(summary)[0][0], 'Check with the fund before the first upload')
        self.assertNotIn('Check with your adviser', xlsx_text(summary))
        detail = self.env['pb.gov.filing'].browse(before.id).sudo()._approval_detail(None)
        self.assertIn('Check with the fund before the first upload',
                      [c['value'] for c in detail['chips']])
        if self.has_bpjs:
            tk = self.prepare('ID_BPJS_TK', self.co_id)
            upload = [raw for n, raw in self.files(tk).items() if 'upah' in n][0]
            self.assertEqual(xlsx_rows(upload, 'Check first')[0][0],
                             'Check with the fund before the first upload')
        self.board(self.manager, self.co_sg).set_accepted(self.forms['SG_CPF_EZPAY'].id, True)
        after = self.prepare('SG_CPF_EZPAY', self.co_sg)
        self.assertFalse(after.adviser_mark)
        summary = [raw for n, raw in self.files(after).items() if n.endswith('.xlsx')][0]
        self.assertNotIn('Check with the fund', xlsx_text(summary))
        # a tax return keeps its own sentence
        bpmp = self.env.ref('pb_form_lines.form_id_bpmp')
        self.assertEqual(bpmp._pb_adviser_sentence(), 'Check with your adviser before first filing')
        self.assertEqual(self.env['pb.gov.filing']._pb_adviser_text(),
                         'Check with your adviser before first filing')

    # ================================================================ T9
    def test_t9_install_is_silent(self):
        main = self.env.ref('base.main_company')
        forms = self.env['pb.gov.form'].sudo().search([('filing_section', '=', 'fund')])
        self.assertEqual(set(forms.mapped('code')),
                         {'ID_BPJS_TK', 'ID_BPJS_KES', 'IN_EPF_ECR', 'IN_ESI', 'SG_CPF_EZPAY'})
        mine = forms | self.forms['VN_SI_ITEMS']
        self.assertFalse(self.Map.sudo().search([('form_id', 'in', mine.ids),
                                                 ('company_id', '=', main.id)]))
        # company-scoped: a local walk may have committed its own DEMO companies (ledger S8D-6)
        self.assertFalse(self.env['pb.gov.filing'].sudo().search([('form_id', 'in', mine.ids),
                                                                  ('company_id', '=', main.id)]))
        self.assertFalse(self.env['pb.gov.form.company'].sudo().search([('form_id', 'in', mine.ids),
                                                                        ('company_id', '=', main.id)]))
        data = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'pb_form_lines'), ('model', 'in', ('pb.gov.form', 'pb.gov.form.line')),
            ('res_id', 'in', mine.ids + mine.line_ids.ids)])
        self.assertTrue(data)
        self.assertTrue(all(d.noupdate for d in data))
        for form in mine:
            self.assertTrue(form.source_note and form.source_url, form.code)
            self.assertTrue(form.inferred_note, form.code)
        # every S2-A form keeps its place and its sentence
        for form in self.env['pb.gov.form'].sudo().search([('code', 'in', (
                'ID_BPMP', 'VN_05KK_TT89', 'VN_05KK_TT80'))]):
            self.assertEqual((form.filing_section, form.adviser_wording), ('tax', 'adviser'))
        # the social-insurance items form is not offered as a filing
        self.assertFalse(self.board(self.officer, self.co_id)._form_card(
            self.forms['VN_SI_ITEMS'], self.co_id)['can_prepare'])

    # ================================================================ T10
    def test_t10_no_vendor_name_in_any_file_or_name(self):
        self.map_all()
        self.settings('SG_CPF_EZPAY', self.co_sg, '234567891APTE01')
        made = []
        for code, company in (('IN_EPF_ECR', self.co_in), ('IN_ESI', self.co_in),
                              ('SG_CPF_EZPAY', self.co_sg)) + (
                (('ID_BPJS_TK', self.co_id), ('ID_BPJS_KES', self.co_id)) if self.has_bpjs else ()):
            made.append(self.prepare(code, company))
        for filing in made:
            for name, raw in self.files(filing).items():
                self.assertNotIn('odoo', name.lower())
                text = xlsx_text(raw) if name.endswith('.xlsx') else raw.decode('ascii')
                self.assertNotIn('odoo', text.lower(), name)
            self.assertFalse(re.search(r'\bodoo\b', json.dumps(filing.sudo()._pb_warnings()), re.I))

    # ================================================================ T11 (static)
    def test_t11_screen_extensions_find_their_targets(self):
        """Every xpath of the fund wording extension resolves in the S2-A
        template it extends (the browser walk caught one that did not: the
        screen then fails to open)."""
        import os
        from lxml import etree
        from odoo.modules.module import get_module_path
        root = os.path.join(get_module_path('pb_form_lines'), 'static', 'src', 'xml')
        templates = {}
        for name in ('form_lines_board.xml', 'gov_filing_flow.xml'):
            for t in etree.parse(os.path.join(root, name)).getroot().iter('t'):
                if t.get('t-name'):
                    templates[t.get('t-name')] = t
        ext = etree.parse(os.path.join(root, 'fund_files.xml')).getroot()
        checked = 0
        for inherit in ext.iter('t'):
            target = inherit.get('t-inherit')
            if not target:
                continue
            self.assertIn(target, templates)
            for xp in inherit.iter('xpath'):
                expr = re.sub(r"hasclass\('([^']+)'\)",
                              r"contains(concat(' ', normalize-space(@class), ' '), ' \1 ')",
                              xp.get('expr'))
                found = templates[target].xpath('.' + expr if expr.startswith('//') else expr)
                self.assertTrue(found, '%s: %s finds nothing' % (target, xp.get('expr')))
                checked += 1
        self.assertGreaterEqual(checked, 8)

    # ================================================================ probe
    def test_the_member_number_probe_reads_by_name(self):
        Reader = self.env['pb.gov.form.reader']
        self.assertEqual(Reader._pb_probe(self.tan, ('no_such_field', 'identification_id')),
                         'S1122334A')
        self.assertEqual(Reader._pb_probe(self.tan, ('no_such_field',), ('no_such_either',)), '')
        ident = Reader._pb_identity(self.forms['IN_EPF_ECR'], self.dev)
        self.assertEqual(ident['missing'], ['UAN (provident fund number)'])
        self.assertTrue(ident['values']['leave_out'])
        # a foreign ID is never taken for a CPF account number
        ident = Reader._pb_identity(self.forms['SG_CPF_EZPAY'], self.raj)
        self.assertEqual(ident['values']['member'], '')
