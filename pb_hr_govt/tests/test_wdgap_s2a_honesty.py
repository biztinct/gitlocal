# -*- coding: utf-8 -*-
"""WDGAP S2-A test 11 — the Vietnamese social-insurance reports: golden +
three honesty fixes.

GOLDEN. `data/s2a_vn_si_golden.json` holds every cell of the five workbooks as
the code on origin/19.1 wrote them for the fixture below (recorded by running
this file on that tree with PB_S2A_GOLDEN_RECORD set). With no draft payslip
and the insurance-book number filled in, the new code writes exactly the same
cells except the ones the three fixes are about, which are asserted one by one:

  1. done payslips only (a draft's sick days are not counted);
  2. the insurance-book column ("Mã sổ BHXH" / "Số sổ BHXH") is
     `vietnam_social_insurance_number`, empty when missing — never the
     national ID;
  3. placeholder literals are gone (left empty): certificate serial
     "SERIAL-001", bank account "0000000000", bank code "BANKXXX", employee
     code "EMP-CODE", the D01 document placeholders and the "(TODO replace
     with actual codes)" note.

The code→item reading (SICK, MAT, ALLOW, EXTRA) is unchanged in this phase —
a wave-2 candidate (Step 2 handover §S2-A.8).
"""
import io
import json
import os
from datetime import date

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, 'data', 's2a_vn_si_golden.json')

REPORTS = {
    'bhxh630': 'pb_hr_govt.bhxh630_xlsx',
    'bhxhdstk01': 'pb_hr_govt.bhxhdstk01_xlsx',
    'bangke_d01': 'pb_hr_govt.bangke_d01_xlsx',
    'giam_ld': 'pb_hr_govt.giam_ld_xlsx',
    'tang_ld': 'pb_hr_govt.tang_ld_xlsx',
}

#: (report, sheet, column letter) the three fixes may change, from row 7 down
FIXED_COLUMNS = {
    ('bhxh630', 'M01B-HSB-PhatSinh'): {'A', 'E', 'K', 'M', 'N'},
    ('bhxhdstk01', 'Danhsach'): {'C'},
    ('bangke_d01', 'D01-TS'): {'B', 'C', 'D', 'H', 'I'},
    ('giam_ld', 'Truong_hop_Giam'): {'B', 'M'},
    ('tang_ld', 'TangLaoDong'): {'B', 'P'},
}
FIRST_DATA_ROW = 7


@tagged('post_install', '-at_install', 'wdgap_s2a')
class TestS2AVnSocialInsuranceHonesty(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Emp = cls.env['hr.employee']
        if 'vietnam_social_insurance_number' not in Emp._fields:
            cls.skip_all = True
            return
        cls.skip_all = False
        cls.company = cls.env['res.company'].create({
            'name': 'DEMO S2A SI Co', 'currency_id': cls.env.ref('base.VND').id,
            'country_id': cls.env.ref('base.vn').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'S2A SI Kind'})
        cls.rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.cat = cls.env.ref('om_hr_payroll.BASIC')
        cls.mai = cls._person('DEMO S2A Mai', '079190000001', '7912345678', 'S2A001',
                              'female', date(1990, 5, 4))
        cls.tuan = cls._person('DEMO S2A Tuan', '079190000002', '7998765432', 'S2A002',
                               'male', date(1985, 11, 20))
        for emp, sick in ((cls.mai, 2.0), (cls.tuan, 1.0)):
            cls._slip(emp, {'SICK': sick, 'MAT': 0.0, 'ALLOW': 1_000_000.0,
                            'EXTRA': 500_000.0}, 'done')

    @classmethod
    def _person(cls, name, national, book, code, sex, birthday):
        vals = {'name': name, 'company_id': cls.company.id, 'identification_id': national,
                'barcode': code, 'birthday': birthday,
                'vietnam_social_insurance_number': book}
        if 'sex' in cls.env['hr.employee']._fields:
            vals['sex'] = sex
        emp = cls.env['hr.employee'].create(vals)
        cls.env['hr.contract'].create({
            'name': name, 'employee_id': emp.id, 'company_id': cls.company.id,
            'wage': 15_000_000.0, 'state': 'open', 'date_start': '2026-01-01',
            'type_id': cls.kind.id})
        return emp

    @classmethod
    def _slip(cls, emp, lines, state):
        contract = cls.env['hr.contract'].search([('employee_id', '=', emp.id)], limit=1)
        slip = cls.env['hr.payslip'].create({
            'name': 'S2A SI %s' % emp.name, 'employee_id': emp.id, 'contract_id': contract.id,
            'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 31),
            'company_id': cls.company.id})
        cls.env['hr.payslip.line'].create([{
            'slip_id': slip.id, 'salary_rule_id': cls.rule.id, 'employee_id': emp.id,
            'contract_id': contract.id, 'category_id': cls.cat.id, 'name': code,
            'code': code, 'amount': amount, 'quantity': 1.0, 'rate': 100.0}
            for code, amount in lines.items()])
        if state != 'draft':
            slip.write({'state': state})
        return slip

    def setUp(self):
        super().setUp()
        if self.skip_all:
            self.skipTest('the Vietnam employee master is not installed')

    def _render(self, key):
        import openpyxl
        wizard = self.env['pb.govt.report.wizard'].create({
            'company_id': self.company.id, 'report_type': key,
            'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 31),
            'employee_ids': [(6, 0, (self.mai | self.tuan).ids)]})
        content, _ext = self.env['ir.actions.report']._render(REPORTS[key], wizard.ids, {})
        book = openpyxl.load_workbook(io.BytesIO(content))
        out = {}
        for ws in book.worksheets:
            cells = {}
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value not in (None, ''):
                        value = cell.value
                        if hasattr(value, 'isoformat'):
                            value = value.isoformat()
                        cells[cell.coordinate] = value
            out[ws.title] = cells
        return out

    def _dump(self):
        return {key: self._render(key) for key in REPORTS}

    def test_s2a_11a_golden_except_the_three_fixes(self):
        dump = self._dump()
        if os.environ.get('PB_S2A_GOLDEN_RECORD'):
            os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
            with open(GOLDEN, 'w', encoding='utf-8') as fh:
                json.dump(dump, fh, ensure_ascii=False, indent=1, sort_keys=True)
            return
        with open(GOLDEN, encoding='utf-8') as fh:
            golden = json.load(fh)
        self.assertEqual(sorted(golden), sorted(dump))
        for key in REPORTS:
            self.assertEqual(sorted(golden[key]), sorted(dump[key]), key)
            for sheet, cells in golden[key].items():
                fixed = FIXED_COLUMNS.get((key, sheet), set())
                now = dump[key][sheet]
                for coord in sorted(set(cells) | set(now)):
                    col = ''.join(ch for ch in coord if ch.isalpha())
                    row = int(''.join(ch for ch in coord if ch.isdigit()))
                    if col in fixed and row >= FIRST_DATA_ROW:
                        continue
                    self.assertEqual(now.get(coord), cells.get(coord),
                                     '%s/%s/%s changed' % (key, sheet, coord))

    def test_s2a_11b_insurance_book_number_never_the_national_id(self):
        dump = self._dump()
        books = {'7912345678', '7998765432'}
        nationals = {'079190000001', '079190000002'}
        for key, sheet, col in (('bhxh630', 'M01B-HSB-PhatSinh', 'A'),
                                ('bhxhdstk01', 'Danhsach', 'C'),
                                ('bangke_d01', 'D01-TS', 'B'),
                                ('giam_ld', 'Truong_hop_Giam', 'B'),
                                ('tang_ld', 'TangLaoDong', 'B')):
            cells = dump[key][sheet]
            got = {str(v) for c, v in cells.items()
                   if c.rstrip('0123456789') == col and int(c[len(col):]) >= FIRST_DATA_ROW}
            self.assertEqual(got, books, '%s: %s' % (key, got))
            self.assertFalse(got & nationals)
        # a person with no insurance-book number: the cell is empty
        self.tuan.vietnam_social_insurance_number = False
        dump = self._dump()
        cells = dump['bhxhdstk01']['Danhsach']
        got = {str(v) for c, v in cells.items()
               if c.rstrip('0123456789') == 'C' and int(c[1:]) >= FIRST_DATA_ROW}
        self.assertEqual(got, {'7912345678'})

    def test_s2a_11c_no_placeholder_literals(self):
        dump = self._dump()
        text = json.dumps(dump, ensure_ascii=False)
        for literal in ('SERIAL-001', '0000000000', 'BANKXXX', 'EMP-CODE', 'Văn bản mẫu',
                        'Số VB-001', 'Trích yếu nội dung', 'Nội dung thẩm định', 'TODO'):
            self.assertNotIn(literal, text, literal)

    def test_s2a_11d_done_payslips_only(self):
        base = self.env['pb.govt.report.base']
        self._slip(self.mai, {'SICK': 9.0}, 'draft')
        self._slip(self.mai, {'SICK': 9.0}, 'verify')
        slips = base._get_payslips_in_range(self.company, date(2026, 10, 1), date(2026, 10, 31))
        self.assertEqual(set(slips.mapped('state')), {'done'})
        days = base._payslip_lines_map(slips)[self.mai.id]['SICK']
        self.assertEqual(days, 2.0, "a draft's or a waiting payslip's sick days are not counted")
        cells = self._dump()['bhxh630']['M01B-HSB-PhatSinh']
        mai_row = [c for c, v in cells.items() if v == 'DEMO S2A Mai'][0][1:]
        self.assertEqual(cells.get('H' + mai_row), 2)
