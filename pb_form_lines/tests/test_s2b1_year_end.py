# -*- coding: utf-8 -*-
"""WDGAP S2-B1 — year-end paperwork: Indonesia BPA1, Vietnam 05/QTT-TNCN,
India Form 16 Part B / Form 130 Part C and Form 24Q / Form 138, Singapore
IR8A; per-person certificates and their release.

Numbered as the handover's S2-B1 test list (T1..T12; T6/T7 have an HTTP half
in pb_me_tax_cert, T10 also in `test_s2a_po_gate.py` which scans every
string of this module, T12 = S2-A's suites run unchanged).

Fixture: S2-A's (an Indonesian and a Vietnamese company, finished payslips
written directly) plus more Indonesian months, an Indian company (rupees,
scheme tax year from April) and a Singaporean company (SGD).
"""
import io
import json
import os
import re
import zipfile
from datetime import date

from lxml import etree

from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .test_s2a_form_lines import HERE, MANAGER, OFFICER, S2AFixture, file_text

Y26 = (date(2026, 1, 1), date(2026, 12, 31))


def pdf_text_and_meta(raw):
    from PyPDF2 import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    meta = {k: str(v) for k, v in (reader.metadata or {}).items()}
    return ' '.join(text.split()), meta


class S2B1Fixture(S2AFixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sgd = cls.env.ref('base.SGD')
        cls.usd = cls.env.ref('base.USD')
        (cls.sgd | cls.usd).write({'active': True})
        Company = cls.env['res.company']
        cls.co_in = Company.create({'name': 'DEMO S2B1 India', 'currency_id': cls.inr.id})
        cls.co_sg = Company.create({'name': 'DEMO S2B1 Singapore', 'currency_id': cls.sgd.id,
                                    'phone': '+65 6123 4567'})
        cls.env.user.company_ids = [(4, cls.co_in.id), (4, cls.co_sg.id)]
        for company in (cls.co_in, cls.co_sg):
            cls.env['biz.approval.seed'].sudo().set_no_approval_needed(company, 'filing')
        all_co = [(6, 0, [cls.co_id.id, cls.co_vn.id, cls.co_in.id, cls.co_sg.id])]
        cls.officer.sudo().company_ids = all_co
        cls.manager.sudo().company_ids = all_co
        cls.hr_only.sudo().company_ids = all_co

        # ------------------------------------------------ Indonesia: a year
        for month in range(1, 13):
            if month == 10:
                continue          # S2-A's October payslip is already there
            ds, de = cls._month(2026, month)
            cls._slip(cls.co_id, cls.ani, cls.cfg, {
                'BRUTO': 10_000_000, 'PAJAK': -300_000, 'BPJSEE': -100_000},
                inputs={'PTKP': 'K/1'}, ds=ds, de=de)
        cls.form_bpa1 = cls.env.ref('pb_form_lines.form_id_bpa1')

        # ------------------------------------------------ Vietnam: dependants
        cls.form_qtt = cls.env.ref('pb_form_lines.form_vn_05qtt_tt89')
        cls.form_qtt80 = cls.env.ref('pb_form_lines.form_vn_05qtt_tt80')
        cls.has_deps = 'vietnam.employee.dependent' in cls.env
        if cls.has_deps:
            Dep = cls.env['vietnam.employee.dependent'].sudo()
            Dep.create({'employee_id': cls.vy.id, 'name': 'DEMO S2B1 Child One',
                        'relationship': 'child', 'status': 'eligible',
                        'effective_from': date(2025, 3, 1), 'date_of_birth': date(2020, 5, 1),
                        'identification_number': '001220000001'})
            Dep.create({'employee_id': cls.vy.id, 'name': 'DEMO S2B1 Child Two',
                        'relationship': 'child', 'status': 'eligible',
                        'effective_from': date(2026, 4, 1), 'effective_to': date(2026, 9, 30)})
            Dep.create({'employee_id': cls.vy.id, 'name': 'DEMO S2B1 Pending',
                        'relationship': 'parent', 'status': 'pending',
                        'effective_from': date(2026, 1, 1)})
            Dep.create({'employee_id': cls.vy.id, 'name': 'DEMO S2B1 Ended',
                        'relationship': 'parent', 'status': 'eligible',
                        'effective_from': date(2024, 1, 1), 'effective_to': date(2025, 6, 30)})
        Contract = cls.env['hr.contract'].sudo()
        if 'advantages_ids' in Contract._fields:
            tmpl = cls.env['hr.contract.advantage.template'].sudo().create({
                'name': 'DEMO Registered tax dependants', 'code': 'VNREGISTER'})
            contract = Contract.search([('employee_id', '=', cls.vy.id)], limit=1)
            contract.write({'advantages_ids': [(0, 0, {'advantage_template_id': tmpl.id,
                                                       'amount': 1.0})]})

        # ------------------------------------------------ India: April year
        cls.cfg_in = cls._config(cls.co_in, 'DEMO S2B1 IN Staff', 'SBIN', 'IN')
        cls.cfg_in.sudo().write({'tax_year_start_month': '4'})
        cls.ri = {c: cls._rule(cls.cfg_in, n, c, role) for n, c, role in (
            ('Basic salary', 'BASIC', 'earning'), ('Salary TDS', 'TDS', 'deduction'),
            ('Professional tax', 'PT', 'deduction'), ('Net pay', 'NETPAY', 'net'))}
        cls.arjun = cls._person(cls.co_in, 'DEMO S2B1 Arjun', job_title='Analyst')
        cls.priya = cls._person(cls.co_in, 'DEMO S2B1 Priya', job_title='Engineer')
        cls.arjun.sudo().birthday = date(1960, 2, 1)       # 66: senior citizen
        for month in range(1, 13):
            ds, de = cls._month(2026, month)
            cls._slip(cls.co_in, cls.arjun, cls.cfg_in, {
                'BASIC': 50_000, 'TDS': -5_000, 'PT': -200}, ds=ds, de=de)
            if month in (7, 8, 9):
                cls._slip(cls.co_in, cls.priya, cls.cfg_in, {
                    'BASIC': 40_000, 'TDS': -2_000}, ds=ds, de=de)
        cls.form_16b = cls.env.ref('pb_form_lines.form_in_form16b')
        cls.form_130 = cls.env.ref('pb_form_lines.form_in_form130c')
        cls.form_24q = cls.env.ref('pb_form_lines.form_in_24q')
        cls.form_138 = cls.env.ref('pb_form_lines.form_in_form138')

        # ------------------------------------------------ Singapore
        cls.cfg_sg = cls._config(cls.co_sg, 'DEMO S2B1 SG Staff', 'SBSG', 'SG')
        cls.rs = {c: cls._rule(cls.cfg_sg, n, c, role) for n, c, role in (
            ('Basic salary', 'SAL', 'earning'), ('Bonus', 'BON', 'earning'),
            ('Transport allowance', 'TRANS', 'earning'), ('CPF employee', 'CPFEE', 'deduction'),
            ('CDAC', 'CDAC', 'deduction'), ('Housing benefit', 'BIK', 'info'),
            ('Net pay', 'NETPAY', 'net'))}
        cls.mei = cls._person(cls.co_sg, 'DEMO S2B1 Mei', identification_id='S1234567D',
                              job_title='Manager')
        cls.tan = cls._person(cls.co_sg, 'DEMO S2B1 Tan', identification_id='G1234567N',
                              job_title='Analyst')
        cls.wei = cls._person(cls.co_sg, 'DEMO S2B1 Wei')
        cls.mei.sudo().write({'birthday': date(1990, 11, 1), 'sex': 'female'})
        cls.tan.sudo().write({'birthday': date(1985, 12, 2), 'sex': 'male'})
        Contract.search([('employee_id', '=', cls.tan.id)]).write(
            {'date_start': date(2026, 7, 1), 'date_end': date(2026, 9, 30)})
        for month in range(1, 13):
            ds, de = cls._month(2026, month)
            cls._slip(cls.co_sg, cls.mei, cls.cfg_sg, dict(
                {'SAL': 5_000.50, 'TRANS': 200, 'CPFEE': -1_000.40, 'CDAC': -1},
                **({'BON': 3_000} if month == 12 else {})), ds=ds, de=de)
            cls._slip(cls.co_sg, cls.wei, cls.cfg_sg, {'SAL': 3_000}, ds=ds, de=de)
            if month in (7, 8, 9):
                cls._slip(cls.co_sg, cls.tan, cls.cfg_sg, {'SAL': 4_000, 'CPFEE': -800},
                          ds=ds, de=de)
        cls.form_ir8a = cls.env.ref('pb_form_lines.form_sg_ir8a')

    @staticmethod
    def _month(year, month):
        from calendar import monthrange
        return date(year, month, 1), date(year, month, monthrange(year, month)[1])

    # ---------------------------------------------------------- mappings
    def map_bpa1(self):
        f = self.form_bpa1
        self.put(f, '1', self.r['BRUTO'])
        self.put(f, '1', self.r2['BRUTO'])
        self.put(f, '10', self.r['BPJSEE'])
        self.put(f, '22', self.r['PAJAK'])
        self.put(f, '22', self.r2['PAJAK'])
        self.put(f, 'PTKP', self.r['PTKP'], source='computed_value')

    def map_qtt(self, form=None):
        form = form or self.form_qtt
        taxable, withheld = ('22', '33') if form == self.form_qtt else ('23', '31')
        self.put(form, taxable, self.rv['TNCT'])
        self.put(form, withheld, self.rv['PIT'])
        self.put(form, 'ASSESS', self.rv['TNTT'], source='computed_value')

    def map_in(self):
        for form in (self.form_16b, self.form_130):
            self.put(form, '1a', self.ri['BASIC'])
            self.put(form, 'TDS', self.ri['TDS'])
        self.put(self.form_130, '4a', self.ri['PT'])
        self.put(self.form_16b, '4c', self.ri['PT'])
        for form in (self.form_24q, self.form_138):
            self.put(form, 'PAID', self.ri['BASIC'])
            self.put(form, 'TDS', self.ri['TDS'])

    def map_sg(self):
        f = self.form_ir8a
        self.put(f, 'a', self.rs['SAL'])
        self.put(f, 'b', self.rs['BON'])
        self.put(f, 'd1', self.rs['TRANS'])
        self.put(f, 'CPF', self.rs['CPFEE'])
        self.put(f, 'DON', self.rs['CDAC'])

    def Filing(self, user, company):
        return self.env['pb.gov.filing'].with_user(user).with_context(allowed_company_ids=[company.id])

    def sum_lines(self, company, config_ids, codes, start, end, by_size=False):
        """Independent sum of finished payslip lines (the test's own SQL)."""
        self.env.flush_all()
        self.env.cr.execute("""
            SELECT COALESCE(SUM(%s), 0) FROM hr_payslip_line l JOIN hr_payslip s ON s.id = l.slip_id
             WHERE s.company_id = %%s AND s.formula_config_id IN %%s AND l.code IN %%s
               AND s.state IN ('done', 'paid') AND s.date_to BETWEEN %%s AND %%s
        """ % ('ABS(l.total)' if by_size else 'l.total'),
            (company.id, tuple(config_ids), tuple(codes), start, end))
        return self.env.cr.fetchone()[0]


@tagged('post_install', '-at_install', 'wdgap_s2b1')
class TestS2B1YearEnd(S2B1Fixture):

    # ================================================================ T1
    def test_t1a_indonesia_bpa1_totals_and_a_leaver(self):
        self.map_bpa1()
        data = self.Reader._pb_read(self.form_bpa1, self.co_id, *Y26)
        cfgs = [self.cfg.id, self.cfg2.id]
        self.assertEqual(data['lines']['1'], self.sum_lines(self.co_id, cfgs, ['BRUTO'], *Y26))
        self.assertEqual(data['lines']['22'], self.sum_lines(self.co_id, cfgs, ['PAJAK'], *Y26, by_size=True))
        self.assertEqual(data['lines']['8'], data['lines']['1'])
        people = {e['employee_id']: e for e in data['employees']}
        self.assertEqual(people[self.ani.id]['lines']['1'], 120_000_000)
        self.assertEqual(people[self.ani.id]['months'][0], '2026-01')
        self.assertEqual(people[self.budi.id]['date_to'], '2026-10-31')
        rows = {r['employee_id']: r for r in self.env['pb.gov.filing']._pb_bpa1_rows(
            dict(data, settings={'employer_tax_id': '0029482015507000'}))[2]}
        self.assertEqual(rows[self.ani.id]['withholding'], 'FullYear')
        self.assertEqual((rows[self.budi.id]['m_start'], rows[self.budi.id]['m_end']), (10, 10))
        self.assertEqual(rows[self.budi.id]['withholding'], 'PartialYear', "a leaver / joiner is part of the year")
        self.assertEqual(rows[self.budi.id]['date'], date(2026, 10, 31))

    def test_t1b_vietnam_qtt_totals(self):
        self.map_qtt()
        data = self.Reader._pb_read(self.form_qtt, self.co_vn, *Y26)
        t = data['lines']
        self.assertEqual(t['15'], 3)
        self.assertEqual(t['16'], 2)
        self.assertEqual((t['17'], t['18'], t['19']), (2, 1, 1))
        self.assertEqual(t['22'], self.sum_lines(self.co_vn, [self.cfg_vn.id], ['TNCT'], *Y26))
        self.assertEqual((t['23'], t['24']), (3 * 38_000_000, 3 * 50_000_000))
        self.assertEqual(t['30'], 3 * 80_000_000)
        self.assertEqual(t['33'], self.sum_lines(self.co_vn, [self.cfg_vn.id], ['PIT'], *Y26, by_size=True))
        self.assertEqual((t['34'], t['35']), (6_000_000, 30_000_000))
        self.assertEqual((t['44'], t['45']), (0, 0), "nothing settled for anyone: no balance")
        people = {e['employee_id']: e for e in data['employees']}
        self.assertEqual(people[self.vy.id]['lines']['ASSESS'], 45_000_000)

    def test_t1c_india_april_year_quarters_and_a_leaver(self):
        self.map_in()
        y26 = (date(2026, 4, 1), date(2027, 3, 31))
        data = self.Reader._pb_read(self.form_130, self.co_in, *y26)
        self.assertEqual(data['lines']['1a'], self.sum_lines(self.co_in, [self.cfg_in.id], ['BASIC'], *y26))
        self.assertEqual(data['lines']['1a'], 9 * 50_000 + 3 * 40_000)
        self.assertEqual(data['lines']['TDS'], 9 * 5_000 + 3 * 2_000)
        self.assertEqual(data['lines']['4a'], 9 * 200)
        self.assertEqual(data['lines']['6'], data['lines']['1a'] - 9 * 200)
        self.assertFalse([w for w in data['warnings'] if w['code'] == 'crosses_tax_year'])
        # the year before: January to March 2026 only
        y25 = self.Reader.period_bounds(self.form_16b, date(2026, 2, 1))
        self.assertEqual(y25, (date(2025, 4, 1), date(2026, 3, 31)))
        old = self.Reader._pb_read(self.form_16b, self.co_in, *y25)
        self.assertEqual(old['lines']['1a'], 3 * 50_000)
        # the period picker speaks the authority's year
        board = self.board(self.officer, self.co_in)
        self.assertEqual(board._bounds(self.form_130, '2026'), y26)
        self.assertEqual(board._bounds(self.form_138, '2026-Q2'), (date(2026, 7, 1), date(2026, 9, 30)))
        self.assertEqual(board._bounds(self.form_24q, '2025-Q4'), (date(2026, 1, 1), date(2026, 3, 31)))
        start = board.flow_start(self.form_130.id)
        self.assertIn('2026–27', [y['label'] for y in start['year_options']])
        self.assertEqual(start['quarter_labels'][0], 'April – June')
        with self.assertRaises(UserError):
            board._bounds(self.form_130, '2026-04')
        # the leaver: three months, her own dates
        priya = [e for e in data['employees'] if e['employee_id'] == self.priya.id][0]
        self.assertEqual((priya['date_from'], priya['date_to']), ('2026-07-01', '2026-09-30'))
        self.assertEqual(priya['lines']['1a'], 120_000)

    def test_t1d_india_quarter_files(self):
        self.map_in()
        Filing = self.Filing(self.officer, self.co_in)
        q2 = Filing.prepare(self.form_138, self.co_in, date(2026, 7, 1), date(2026, 9, 30))
        self.assertEqual(q2.sudo()._pb_totals()['PAID'], 3 * 50_000 + 3 * 40_000)
        import openpyxl
        raw = q2.sudo().file_ids.attachment_id.raw
        book = openpyxl.load_workbook(io.BytesIO(raw))
        self.assertNotIn('Annexure II', book.sheetnames, "Annexure II only with the last quarter")
        ws = book['Annexure I']
        heads = [c.value for c in ws[5]] if ws['A1'].value and 'adviser' in str(ws['A1'].value) else None
        codes_row = 5 if heads else 4
        codes = [ws.cell(row=codes_row, column=c).value for c in range(1, 16)]
        self.assertEqual(codes, list('ABCDEFGHIJKLMNO'))
        body = [r for r in ws.iter_rows(min_row=codes_row + 2, values_only=True) if r[0] and isinstance(r[0], int)]
        self.assertEqual(len(body), 6, "one row per person per month paid")
        # the January - March quarter of the old form carries Annexure II
        q4 = Filing.prepare(self.form_24q, self.co_in, date(2026, 1, 1), date(2026, 3, 31))
        book = openpyxl.load_workbook(io.BytesIO(q4.sudo().file_ids.attachment_id.raw))
        self.assertIn('Annexure II', book.sheetnames)
        text = file_text('x.xlsx', q4.sudo().file_ids.attachment_id.raw)
        self.assertIn('Senior Citizen', text)
        self.assertIn('return preparer', text)
        self.assertNotIn('odoo', text.lower())

    def test_t1e_singapore_ir8a_totals(self):
        self.map_sg()
        data = self.Reader._pb_read(self.form_ir8a, self.co_sg, *Y26)
        self.assertEqual(data['lines']['a'], self.sum_lines(self.co_sg, [self.cfg_sg.id], ['SAL'], *Y26))
        people = {e['employee_id']: e for e in data['employees']}
        self.assertAlmostEqual(people[self.mei.id]['lines']['a'], 60_006.0)
        self.assertEqual(people[self.mei.id]['lines']['TOTAL'], 60_006 + 3_000 + 2_400)
        self.assertEqual(people[self.tan.id]['date_from'], '2026-07-01')

    # ================================================================ T2
    def test_t2_bpa1_xml_validates_against_the_published_schema(self):
        self.map_bpa1()
        self.accept_settings(self.co_id, self.form_bpa1)
        filing = self.Filing(self.officer, self.co_id).prepare(self.form_bpa1, self.co_id, *Y26)
        files = filing.sudo().file_ids
        xml = files.filtered(lambda f: f.name.endswith('.xml')).attachment_id.raw
        schema = etree.XMLSchema(etree.parse(os.path.join(HERE, 'data', 'bpa1_a1bulk.xsd')))
        doc = etree.fromstring(xml)
        self.assertTrue(schema.validate(doc), schema.error_log)
        self.assertEqual(doc.tag, 'A1Bulk')
        rows = doc.findall('.//A1')
        ani = [r for r in rows if r.findtext('CounterpartTin') == '3172024806201234'][0]
        self.assertEqual([c.tag for c in ani][7:9], ['TaxExemptOpt', 'StatusOfWithholding'],
                         "the XML order, not the spreadsheet's (ledger S2B1-1)")
        self.assertEqual(ani.findtext('SalaryPensionJhtTht'), '120000000')
        self.assertEqual(ani.findtext('PensionContributionJhtThtFee'), '1200000')
        self.assertEqual(ani.findtext('Article21IncomeTax'), '0')
        self.assertEqual(ani.findtext('StatusOfWithholding'), 'FullYear')
        self.assertEqual(ani.findtext('WithholdingDate'), '2026-12-31')
        # Budi (no NIK) and Cici (no tax status) are left out and listed
        self.assertEqual(len(rows), 1)
        import openpyxl
        summary = files.filtered(lambda f: 'summary' in f.name).attachment_id.raw
        people = openpyxl.load_workbook(io.BytesIO(summary)).worksheets[1]
        listed = {people.cell(row=i, column=1).value: people.cell(row=i, column=9).value
                  for i in range(2, people.max_row + 1)}
        self.assertEqual(listed['DEMO S2A Budi'], 'No')
        # the converter's DATA sheet: C1 the number, headings on row 3
        data_x = files.filtered(lambda f: 'converter' in f.name).attachment_id.raw
        ws = openpyxl.load_workbook(io.BytesIO(data_x))['DATA']
        self.assertEqual((ws['A1'].value, ws['C1'].value), ('NPWP Pemotong', '0029482015507000'))
        self.assertEqual(ws['B3'].value, 'Pemberi Kerja Selanjutnya')
        self.assertEqual(ws['AB3'].value, 'Tanggal Pemotongan')
        self.assertEqual(ws['L3'].value, 'Status Bukti Potong')
        self.assertEqual(ws['L4'].value, 'FullYear')

    # ================================================================ T3
    def test_t3_singapore_file_keeps_the_published_layout(self):
        from ..models.render_sg import HEADER_KEYS, IMPORT_HEADS, IR8A_KEYS, PERSON_KEYS
        self.map_sg()
        self.accept_settings(self.co_sg, self.form_ir8a, tin='201912345K')
        filing = self.Filing(self.officer, self.co_sg).prepare(self.form_ir8a, self.co_sg, *Y26)
        files = filing.sudo().file_ids
        payload = json.loads(files.filtered(lambda f: f.name.endswith('.json')).attachment_id.raw)
        payload.pop('_note', None)
        head = payload['orgAndSubmissionInfo']
        self.assertEqual(list(head), HEADER_KEYS, "every header key, in order")
        records = payload['employeePersonalParticulars']
        # Wei has no ID number: left out, the header counts only the others
        self.assertEqual(head['totalNumberIR8A'], len(records))
        self.assertEqual(len(records), 2)
        self.assertEqual(head['amountTotalIncomeOfIR8A'], sum(r['ir8a']['totalIncome'] for r in records))
        self.assertEqual((head['totalNumberOfApp8A'], head['totalNumberOfApp8B']), (0, 0))
        self.assertEqual(head['incomeYear'], 2026)
        self.assertLessEqual(len(head['employerTaxRefNumber']), 25)
        date_re = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for n, rec in enumerate(records, start=1):
            self.assertEqual([k for k in rec if k not in ('ir8a', 'appendix8A', 'appendix8B')], PERSON_KEYS)
            self.assertEqual(list(rec['ir8a']), IR8A_KEYS)
            self.assertEqual(rec['recordId'], n)
            self.assertIn(rec['idType'], ('1', '2', '4', '11', '12'))
            self.assertTrue(rec['idNumber'] and len(rec['idNumber']) <= 25)
            self.assertTrue(rec['name'] and len(rec['name']) <= 100)
            self.assertLessEqual(len(rec['designation']), 30)
            self.assertIn(rec['sex'], ('M', 'F'))
            self.assertRegex(rec['dateOfBirth'], date_re)
            ir = rec['ir8a']
            for key in IR8A_KEYS:
                value = ir[key]
                if isinstance(value, int):
                    self.assertGreaterEqual(value, 0)
                    self.assertLessEqual(len(str(value)), 9, key)
            self.assertEqual(ir['othersIncome'], sum(ir[k] for k in (
                'allowances', 'grossCommission', 'gratuityNoticePayExGratiaPayment',
                'pensionRetirementBenefitsAccruedFrom1993',
                'employerContributionToPensionOrProvidentFundOutsideSg',
                'excessOrVoluntaryCpfContributionByEmployer', 'gainsAndProfitsFromSOGS101b',
                'valueOfBenefitsInKind')))
            self.assertEqual(ir['totalIncome'], ir['salary'] + ir['bonus'] + ir['directorFees'] + ir['othersIncome'])
            self.assertRegex(ir['periodPaymentFromDate'], date_re)
            self.assertTrue(ir['periodPaymentFromDate'].startswith('2026'))
        mei = [r for r in records if r['idNumber'] == 'S1234567D'][0]
        self.assertEqual(mei['idType'], '1')
        self.assertEqual(mei['ir8a']['salary'], 60_006, "income: whole dollars, rounded down")
        self.assertEqual(mei['ir8a']['cpfOrDesignatedFund'], 12_005, "deductions: rounded up")
        tan = [r for r in records if r['idNumber'] == 'G1234567N'][0]
        self.assertEqual(tan['idType'], '2')
        self.assertEqual((tan['commencementDate'], tan['cessationDate']), ('2026-07-01', '2026-09-30'))
        self.assertEqual(tan['ir8a']['periodPaymentFromDate'], '2026-07-01')
        # the myTax Portal import workbook: version cell, the 44 headings
        import openpyxl
        book = openpyxl.load_workbook(io.BytesIO(
            files.filtered(lambda f: 'import' in f.name).attachment_id.raw))
        ws = book['IR8A']
        self.assertEqual(ws['A1'].value, 'version 1.0')
        self.assertEqual([ws.cell(row=5, column=c).value for c in range(1, 45)], IMPORT_HEADS)
        self.assertEqual(ws.cell(row=6, column=2).value in ('NRIC', 'FIN'), True)
        # benefits in kind on the form: the check says Appendix 8A is needed
        self.put(self.form_ir8a, 'd8', self.rs['BIK'], source='computed_value')
        self.env['hr.payslip'].sudo().search([('employee_id', '=', self.mei.id)], limit=1).write(
            {'formula_computed_values': json.dumps({'BIK': 500})})
        data = self.Reader._pb_read(self.form_ir8a, self.co_sg, *Y26)
        self.assertTrue([w for w in data['warnings'] if w['code'] == 'appendix_8a'])

    # ================================================================ T4
    def test_t4_vietnam_dependants_mismatch_is_to_check_never_a_block(self):
        if not self.has_deps:
            self.skipTest('no dependant records on this database')
        self.map_qtt()
        data = self.Reader._pb_read(self.form_qtt, self.co_vn, *Y26)
        vy = [e for e in data['employees'] if e['employee_id'] == self.vy.id][0]
        self.assertEqual(vy['dependant_count'], 2, "eligible and valid in 2026 only")
        self.assertEqual([(d['from_month'], d['to_month']) for d in vy['dependants']], [(1, 12), (4, 9)])
        warn = [w for w in data['warnings'] if w['code'] == 'dependants_to_check']
        self.assertTrue(warn and warn[0]['level'] == 'warn' and warn[0]['employee_ids'] == [self.vy.id])
        self.assertTrue(any('To check' in c for c in vy['checks']))
        filing = self.Filing(self.officer, self.co_vn).prepare(self.form_qtt, self.co_vn, *Y26)
        import openpyxl
        book = openpyxl.load_workbook(io.BytesIO(filing.sudo().file_ids.filtered(
            lambda f: f.name.endswith('.xlsx')).attachment_id.raw))
        self.assertEqual(book.sheetnames[:4], ['05-QTT-TNCN', '05-1', '05-2', '05-3'])
        deps = [r for r in book['05-3'].iter_rows(values_only=True) if r and r[3] and str(r[3]).startswith('DEMO S2B1')]
        self.assertEqual(len(deps), 2)
        one = book['05-1']
        names = [r[1] for r in one.iter_rows(values_only=True)]
        self.assertIn('DEMO S2A Vy', names)
        self.assertNotIn('DEMO S2A Nam', names, "a non-resident is on 05-2")
        self.assertIn('DEMO S2A Nam', [r[1] for r in book['05-2'].iter_rows(values_only=True)])
        vy_row = [r for r in one.iter_rows(values_only=True) if r[1] == 'DEMO S2A Vy'][0]
        self.assertEqual(vy_row[9], 2, "column [15]: the record count")
        self.assertIn('To check', ' '.join(str(r[0]) for r in book['To check'].iter_rows(values_only=True)))
        # each layout keeps to its own years
        with self.assertRaises(UserError):
            self.Filing(self.officer, self.co_vn).prepare(self.form_qtt80, self.co_vn, *Y26)
        with self.assertRaises(UserError):
            self.Filing(self.officer, self.co_vn).prepare(self.form_qtt, self.co_vn, date(2025, 1, 1), date(2025, 12, 31))

    # ================================================================ T5
    def test_t5_personal_pdf_right_person_year_mark_and_no_vendor_name(self):
        self.map_bpa1()
        self.accept_settings(self.co_id, self.form_bpa1)
        filing = self.Filing(self.officer, self.co_id).prepare(self.form_bpa1, self.co_id, *Y26)
        certs = filing.sudo().certificate_ids
        self.assertEqual(set(certs.mapped('employee_id').ids), {self.ani.id, self.budi.id, self.cici.id, self.dodi.id})
        ani = certs.filtered(lambda c: c.employee_id == self.ani)
        text, meta = pdf_text_and_meta(ani.attachment_id.raw)
        self.assertIn('DEMO S2A Ani', text)
        self.assertNotIn('DEMO S2A Budi', text)
        self.assertIn('2026', text)
        self.assertIn('Check with your adviser before first filing', text)
        self.assertEqual(meta.get('/Producer'), 'Payobook')
        self.assertEqual(meta.get('/Creator'), 'Payobook')
        self.assertTrue(meta.get('/Title'))
        self.assertNotIn('odoo', (text + ' '.join(meta.values()) + ani.name).lower())
        self.assertNotIn(b'odoo', ani.attachment_id.raw.lower())
        # every certificate is in the zip, and the stamp covers them
        zf = filing.sudo().file_ids.filtered(lambda f: f.name.endswith('.zip'))
        self.assertEqual(len(zipfile.ZipFile(io.BytesIO(zf.attachment_id.raw)).namelist()), len(certs))
        # accepted by the authority: the next one carries no mark
        self.board(self.manager).set_accepted(self.form_bpa1.id, True)
        again = self.Filing(self.officer, self.co_id).prepare(self.form_bpa1, self.co_id, *Y26)
        ani2 = again.sudo().certificate_ids.filtered(lambda c: c.employee_id == self.ani)
        text2, _meta = pdf_text_and_meta(ani2.attachment_id.raw)
        self.assertNotIn('Check with your adviser', text2)
        # the other countries' certificates print too, one per person
        for form, company, mapper, period in (
                (self.form_qtt, self.co_vn, self.map_qtt, Y26),
                (self.form_130, self.co_in, self.map_in, (date(2026, 4, 1), date(2027, 3, 31))),
                (self.form_ir8a, self.co_sg, self.map_sg, Y26)):
            mapper()
            self.accept_settings(company, form, tin='201912345K')
            f = self.Filing(self.officer, company).prepare(form, company, *period)
            for cert in f.sudo().certificate_ids:
                text, meta = pdf_text_and_meta(cert.attachment_id.raw)
                self.assertIn(cert.employee_id.name, text, form.code)
                self.assertNotIn('odoo', (text + ' '.join(meta.values())).lower(), form.code)
                self.assertEqual(meta.get('/Producer'), 'Payobook')

    # ================================================================ T6
    def test_t6_release_after_approval_own_only_undo_and_supersede(self):
        self.map_bpa1()
        self.accept_settings(self.co_id, self.form_bpa1)
        Cert = self.env['pb.gov.filing.certificate']
        filing = self.Filing(self.officer, self.co_id).prepare(self.form_bpa1, self.co_id, *Y26)
        self.assertEqual(filing.sudo().state, 'draft')
        with self.assertRaises(UserError):
            filing.with_user(self.manager)._pb_release(True)
        self.env['biz.approval.engine'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_id.id]).submit(filing)
        self.assertEqual(filing.sudo().state, 'approved')
        self.assertFalse(Cert._pb_employee_certificates(self.ani), "nothing shows before release")
        with self.assertRaises(AccessError):
            filing.with_user(self.officer)._pb_release(True)
        out = self.board(self.manager).set_released(filing.id, True)
        self.assertTrue(out['released'])
        self.assertEqual(out['released_by'], self.manager.name)
        mine = Cert._pb_employee_certificates(self.ani)
        self.assertEqual(mine.mapped('employee_id'), self.ani, "each person sees their own only")
        name, raw = mine._pb_portal_download(self.ani)
        self.assertTrue(raw.startswith(b'%PDF'))
        with self.assertRaises(AccessError):
            mine._pb_portal_download(self.budi)
        self.assertEqual(mine.download_count, 1)
        notes = ' '.join(filing.sudo().message_ids.mapped('body'))
        self.assertIn('released', notes)
        self.assertIn('downloaded their own certificate', notes)
        self.assertNotIn('3172024806201234', notes)
        # take back: hidden again
        self.board(self.manager).set_released(filing.id, False)
        self.assertFalse(Cert._pb_employee_certificates(self.ani))
        self.board(self.manager).set_released(filing.id, True)
        self.assertTrue(Cert._pb_employee_certificates(self.ani))
        # a changed certificate breaks the stamp: hidden, refused
        cert = Cert.sudo().search([('filing_id', '=', filing.id), ('employee_id', '=', self.ani.id)])
        cert.attachment_id.sudo().write({'raw': cert.attachment_id.raw + b' '})
        self.assertFalse(Cert._pb_employee_certificates(self.ani))
        cert.attachment_id.sudo().write({'raw': cert.attachment_id.raw[:-1]})
        self.assertTrue(Cert._pb_employee_certificates(self.ani))
        # replaced by a newer filing: the old certificates disappear
        newer = self.Filing(self.officer, self.co_id).prepare(self.form_bpa1, self.co_id, *Y26)
        self.assertEqual(filing.sudo().state, 'superseded')
        self.assertFalse(Cert._pb_employee_certificates(self.ani))
        self.assertFalse(newer.sudo().pb_released)

    # ================================================================ T7 (RPC + records)
    def test_t7_access_matrix_on_the_server(self):
        self.map_bpa1()
        self.accept_settings(self.co_id, self.form_bpa1)
        out = self.board(self.officer).flow_prepare(self.form_bpa1.id, '2026')
        self.assertEqual(out['state'], 'approved')
        self.assertEqual(out['certificates'], 4)
        self.assertFalse(out['can_release'], "an officer does not release")
        self.assertTrue(self.board(self.manager).get_filing(out['id'])['can_release'])
        for user in (self.hr_only, self.portal):
            with self.assertRaises(AccessError):
                self.board(user).set_released(out['id'], True)
            self.env.flush_all()
            self.env.invalidate_all()
            with self.assertRaises(AccessError):
                self.env['pb.gov.filing.certificate'].with_user(user).with_context(
                    allowed_company_ids=[self.co_id.id]).search([]).read(['name'])
        # officers read the records of their company, never another's
        seen = self.env['pb.gov.filing.certificate'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_vn.id]).search([])
        self.assertFalse(seen.filtered(lambda c: c.company_id == self.co_id))

    # ================================================================ T8
    def test_t8_two_currencies_and_missing_identity_warn_and_add_nothing(self):
        self.map_sg()
        cfg_usd = self._config(self.co_sg, 'DEMO S2B1 SG Dollars', 'SBUSD', 'SG')
        cfg_usd.sudo().write({'currency_id': self.usd.id}) if 'currency_id' in cfg_usd._fields else None
        rule = self._rule(cfg_usd, 'Basic salary', 'SAL', 'earning')
        self.put(self.form_ir8a, 'a', rule)
        self._slip(self.co_sg, self.wei, cfg_usd, {'SAL': 1_000}, ds=date(2026, 5, 1), de=date(2026, 5, 31))
        data = self.Reader._pb_read(self.form_ir8a, self.co_sg, *Y26)
        if 'currency_id' in cfg_usd._fields:
            self.assertTrue([w for w in data['warnings'] if w['code'] == 'two_currencies'])
            self.assertFalse(data['lines'], "nothing added across two currencies")
            with self.assertRaises(UserError):
                self.Filing(self.officer, self.co_sg).prepare(self.form_ir8a, self.co_sg, *Y26)
            data = self.Reader._pb_read(self.form_ir8a, self.co_sg, *Y26, currency_id=self.sgd.id)
        ident = [w for w in data['warnings'] if w['code'] == 'identity_missing']
        self.assertEqual(ident[0]['employee_ids'], [self.wei.id])
        # India: no PAN anywhere — a warning per person, never a crash
        self.map_in()
        data = self.Reader._pb_read(self.form_130, self.co_in, date(2026, 4, 1), date(2027, 3, 31))
        self.assertTrue([w for w in data['warnings'] if w['code'] == 'identity_missing'])

    # ================================================================ T9
    def test_t9_install_is_silent(self):
        main = self.env.ref('base.main_company')
        self.assertFalse(self.env['pb.gov.filing.certificate'].sudo().search(
            [('company_id', '=', main.id)]))
        self.assertFalse(self.env['pb.gov.filing'].sudo().search(
            [('company_id', '=', main.id), ('pb_released', '=', True)]))
        for xmlid in ('form_id_bpa1', 'form_vn_05qtt_tt89', 'form_vn_05qtt_tt80', 'form_in_form16b',
                      'form_in_form130c', 'form_in_24q', 'form_in_form138', 'form_sg_ir8a'):
            form = self.env.ref('pb_form_lines.%s' % xmlid)
            self.assertEqual(form.tile_group, 'year_end')
            self.assertFalse(self.env['pb.gov.form.map'].sudo().search(
                [('form_id', '=', form.id), ('company_id', '=', main.id)]), "install maps nothing")
            self.assertTrue(form.source_note and form.source_url)
            self.assertTrue(hasattr(self.env['pb.gov.filing'], '_pb_render_%s' % form.code.lower()))
        self.assertFalse(self.env['ir.model.data'].sudo().search([
            ('module', 'in', ('pb_form_lines', 'pb_me_tax_cert')),
            ('model', 'in', ('ir.cron', 'mail.template'))]))

    # ================================================================ tiles
    def test_year_end_tiles_on_the_filings_board(self):
        Gov = self.env.get('pb.govt.reports')
        if Gov is None:
            self.skipTest('pb_govt_reports is not installed')
        data = Gov.with_user(self.officer).with_context(
            allowed_company_ids=[self.co_id.id]).get_govt_reports_data('ID')
        self.assertIn('ID_BPA1', [f['code'] for f in data['year_end_forms']])
        self.assertEqual([f['code'] for f in data['forms']], ['ID_BPMP'], "S2-A's key: tax returns only")
        sg = Gov.with_user(self.officer).with_context(
            allowed_company_ids=[self.co_sg.id]).get_govt_reports_data('SG')
        self.assertEqual([f['code'] for f in sg['year_end_forms']], ['SG_IR8A'])
        self.assertTrue(sg['available'])
        hr = Gov.with_user(self.hr_only).with_context(
            allowed_company_ids=[self.co_id.id]).get_govt_reports_data('ID')
        self.assertFalse(hr['year_end_forms'])


@tagged('post_install', '-at_install', 'wdgap_s2b1')
class TestS2B1FollowUpYE(S2B1Fixture):
    """Owner rulings YE1-YE3 (2026-11-18): Vietnam "Asked us to settle
    year-end tax" per person per tax year; Vietnam and India certificates are
    information copies."""

    def _vn_filing(self):
        return self.Filing(self.officer, self.co_vn).prepare(self.form_qtt, self.co_vn, *Y26)

    # ================================================================ YE1-1
    def test_ye1_1_officer_ticks_per_year_who_and_when_kept_others_refused(self):
        self.map_qtt()
        board = self.board(self.officer, self.co_vn)
        check = board.flow_check(self.form_qtt.id, '2026')
        self.assertEqual(check['settle']['year'], 2026)
        self.assertFalse([p for p in check['settle']['people'] if p['asked']])
        check = board.set_settle(self.form_qtt.id, '2026', self.vy.id, True)
        vy = [p for p in check['settle']['people'] if p['employee_id'] == self.vy.id][0]
        self.assertTrue(vy['asked'])
        self.assertEqual(vy['by'], self.officer.name)
        row = self.env['pb.gov.year.settlement'].sudo().search([('employee_id', '=', self.vy.id)])
        self.assertEqual((row.tax_year, row.country_code, row.marked_by), (2026, 'VN', self.officer))
        self.assertTrue(row.marked_on)
        # another tax year is its own answer
        self.assertFalse(self.env['pb.gov.year.settlement']._pb_asked([self.vy.id], 'VN', 2025))
        # nobody else may tick or read it: HR without payroll, an employee login
        for user in (self.hr_only, self.portal):
            with self.assertRaises(AccessError):
                self.board(user, self.co_vn).set_settle(self.form_qtt.id, '2026', self.vy.id, False)
            self.env.flush_all()
            self.env.invalidate_all()
            with self.assertRaises(AccessError):
                self.env['pb.gov.year.settlement'].with_user(user).with_context(
                    allowed_company_ids=[self.co_vn.id]).search([]).read(['asked'])
        # a form without the choice refuses it
        with self.assertRaises(UserError):
            self.board(self.officer).set_settle(self.form_bpa1.id, '2026', self.ani.id, True)

    # ================================================================ YE1-2
    def test_ye1_2_ticked_person_no_certificate_figures_stay_part_two_counts(self):
        self.map_qtt()
        before = self.Reader._pb_read(self.form_qtt, self.co_vn, *Y26)['lines']
        self.board(self.officer, self.co_vn).set_settle(self.form_qtt.id, '2026', self.vy.id, True)
        data = self.Reader._pb_read(self.form_qtt, self.co_vn, *Y26)
        t = data['lines']
        for code in ('15', '16', '17', '22', '23', '30', '33', '34'):
            self.assertEqual(t[code], before[code], "the declaration figures stay: [%s]" % code)
        self.assertEqual(t['37'], 1)
        self.assertEqual(t['38'], 3 * 2_000_000, "Part II: tax withheld from those who asked")
        self.assertEqual((t['44'], t['45']), (0, 0), "no tax due from the scheme: no balance made up")
        codes = {w['code'] for w in data['warnings']}
        self.assertIn('asked_to_settle', codes)
        self.assertIn('settle_without_tax_due', codes)
        filing = self._vn_filing()
        certs = filing.sudo().certificate_ids
        self.assertNotIn(self.vy, certs.mapped('employee_id'), "no certificate made for that year")
        self.assertIn(self.nam, certs.mapped('employee_id'))
        import openpyxl
        book = openpyxl.load_workbook(io.BytesIO(filing.sudo().file_ids.filtered(
            lambda f: f.name.endswith('.xlsx')).attachment_id.raw))
        vy_row = [r for r in book['05-1'].iter_rows(values_only=True) if r[1] == 'DEMO S2A Vy'][0]
        self.assertEqual(vy_row[4], 'X', "05-1 column [10]: asked us to settle")
        lan_row = [r for r in book['05-1'].iter_rows(values_only=True) if r[1] == 'DEMO S2A Lan'][0]
        self.assertFalse(lan_row[4])
        listed = ' '.join(str(r[0]) for r in book['To check'].iter_rows(values_only=True))
        self.assertIn('asked us to settle', listed.lower())
        # with the year's tax due from the scheme, the balance follows
        tax_due = self._rule(self.cfg_vn, 'Thuế phải nộp cả năm', 'TAXDUE', 'info',
                             appears_on_payslip=False)
        self.put(self.form_qtt, '40', tax_due, source='computed_value')
        slip = self.env['hr.payslip'].sudo().search(
            [('employee_id', '=', self.vy.id)], order='date_to desc', limit=1)
        slip.write({'formula_computed_values': json.dumps({'TAXDUE': 5_000_000})})
        t = self.Reader._pb_read(self.form_qtt, self.co_vn, *Y26)['lines']
        self.assertEqual((t['44'], t['45']), (0, 1_000_000), "withheld 6,000,000 against 5,000,000 due")

    # ================================================================ YE1-3
    def test_ye1_3_after_release_tick_hides_untick_never_brings_it_back_silently(self):
        from odoo import fields as F
        self.map_qtt()
        Cert = self.env['pb.gov.filing.certificate']
        filing = self._vn_filing()
        self.env['biz.approval.engine'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_vn.id]).submit(filing)
        self.board(self.manager, self.co_vn).set_released(filing.id, True)
        self.assertTrue(Cert._pb_employee_certificates(self.vy))
        filing.sudo().generated_at = F.Datetime.to_datetime('2026-11-01 08:00:00')
        board = self.board(self.officer, self.co_vn)
        board.set_settle(self.form_qtt.id, '2026', self.vy.id, True)
        self.assertFalse(Cert._pb_employee_certificates(self.vy), "ticked: hidden at once")
        self.assertTrue(Cert._pb_employee_certificates(self.nam), "nobody else changes")
        board.set_settle(self.form_qtt.id, '2026', self.vy.id, False)
        self.assertFalse(Cert._pb_employee_certificates(self.vy), "unticked: not back by itself")
        # HR prepares and releases again: the certificate is made and shown
        again = self._vn_filing()
        self.env['biz.approval.engine'].with_user(self.officer).with_context(
            allowed_company_ids=[self.co_vn.id]).submit(again)
        self.board(self.manager, self.co_vn).set_released(again.id, True)
        self.assertEqual(Cert._pb_employee_certificates(self.vy).filing_id, again)

    # ================================================================ YE2
    def test_ye2_vietnam_certificate_is_an_information_copy_without_a_series(self):
        self.map_qtt()
        filing = self._vn_filing()
        cert = filing.sudo().certificate_ids.filtered(lambda c: c.employee_id == self.vy)
        text, meta = pdf_text_and_meta(cert.attachment_id.raw)
        for words in ('Information copy', 'Bản sao thông tin', 'Salinan informasi'):
            self.assertIn(words, text)
        for words in ('Ký hiệu', 'Số chứng từ'):
            self.assertNotIn(words, text, "no official series or number field")
        self.assertEqual(cert.list_note, 'Information copy')
        self.assertNotIn('odoo', (text + ' '.join(meta.values())).lower())

    # ================================================================ YE3
    def test_ye3_india_certificate_says_the_official_one_comes_from_the_tax_department(self):
        self.map_in()
        filing = self.Filing(self.officer, self.co_in).prepare(
            self.form_130, self.co_in, date(2026, 4, 1), date(2027, 3, 31))
        cert = filing.sudo().certificate_ids.filtered(lambda c: c.employee_id == self.arjun)
        text, meta = pdf_text_and_meta(cert.attachment_id.raw)
        self.assertIn('Information copy', text)
        self.assertIn('your official certificate comes from the tax department', text)
        self.assertEqual(cert.list_note,
                         'Information copy — your official certificate comes from the tax department')
        self.assertNotIn('odoo', (text + ' '.join(meta.values())).lower())
