# -*- coding: utf-8 -*-
"""WDGAP S2-B2 test 6 — the Vietnamese social-insurance reports read the pay
items chosen on Form lines; with nothing chosen they are byte-identical.

GOLDEN. `data/s2b2_vn_si_parts.json` holds the sha256 of every part of the
five workbooks (except `docProps/`, whose "created" stamp is the build time —
ledger IDB1M-3) as the code on `origin/wdgap-s2a` wrote them for the fixture
below (recorded by running this file on that tree with PB_S2B2_GOLDEN_RECORD
set). With no pay item on the form `VN_SI_ITEMS`, every part must be the same.

MAPPED. Once a company puts its own pay items on the lines, the reports use
them for those lines only (a line with nothing on it keeps its fixed code) and
say under the rows which pay items they used.
"""
import hashlib
import io
import json
import os
import zipfile
from datetime import date

from odoo.tests import TransactionCase, tagged

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, 'data', 's2b2_vn_si_parts.json')

REPORTS = {
    'bhxh630': 'pb_hr_govt.bhxh630_xlsx',
    'bhxhdstk01': 'pb_hr_govt.bhxhdstk01_xlsx',
    'bangke_d01': 'pb_hr_govt.bangke_d01_xlsx',
    'giam_ld': 'pb_hr_govt.giam_ld_xlsx',
    'tang_ld': 'pb_hr_govt.tang_ld_xlsx',
}


@tagged('post_install', '-at_install', 'wdgap_s2b2')
class TestS2B2VnSocialInsuranceItems(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Emp = cls.env['hr.employee']
        cls.skip_all = 'vietnam_social_insurance_number' not in Emp._fields
        if cls.skip_all:
            return
        cls.company = cls.env['res.company'].create({
            'name': 'DEMO S2B2 SI Co', 'currency_id': cls.env.ref('base.VND').id,
            'country_id': cls.env.ref('base.vn').id})
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env = cls.env(context=dict(cls.env.context, allowed_company_ids=[cls.company.id],
                                       tracking_disable=True, mail_notrack=True))
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'S2B2 SI Kind'})
        cls.rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.cat = cls.env.ref('om_hr_payroll.BASIC')
        cls.cfg = cls.env['hr.formula.config'].sudo().create({
            'name': 'DEMO S2B2 SI Scheme', 'code': 'SBSI', 'cycle_type': 'end_cycle',
            'country_code': 'VN', 'company_id': cls.company.id, 'state': 'active'})
        cls.items = {}
        for name, code, role in (('Ngày nghỉ ốm (chấm công)', 'NGAYOM', 'info'),
                                 ('Phụ cấp ăn trưa', 'PCAN', 'earning')):
            cls.items[code] = cls.env['hr.formula.rule'].sudo().create({
                'config_id': cls.cfg.id, 'name': name, 'code': code, 'column_type': 'input',
                'default_value': 0.0, 'value_kind': 'money', 'net_role': role,
                'appears_on_payslip': True, 'category_id': cls.cat.id})
        cls.mai = cls._person('DEMO S2B2 Mai', '079190000011', '7912300011', 'S2B201',
                              'female', date(1990, 5, 4))
        cls.tuan = cls._person('DEMO S2B2 Tuan', '079190000012', '7912300012', 'S2B202',
                               'male', date(1985, 11, 20))
        for emp, sick, own_sick, own_allow in ((cls.mai, 2.0, 3.0, 1_200_000.0),
                                               (cls.tuan, 1.0, 1.5, 800_000.0)):
            cls._slip(emp, {'SICK': sick, 'MAT': 0.0, 'ALLOW': 1_000_000.0, 'EXTRA': 500_000.0,
                            'NGAYOM': own_sick, 'PCAN': own_allow})

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
    def _slip(cls, emp, lines):
        contract = cls.env['hr.contract'].search([('employee_id', '=', emp.id)], limit=1)
        slip = cls.env['hr.payslip'].create({
            'name': 'S2B2 SI %s' % emp.name, 'employee_id': emp.id, 'contract_id': contract.id,
            'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 31),
            'company_id': cls.company.id, 'formula_config_id': cls.cfg.id})
        cls.env['hr.payslip.line'].create([{
            'slip_id': slip.id, 'salary_rule_id': cls.rule.id, 'employee_id': emp.id,
            'contract_id': contract.id, 'category_id': cls.cat.id, 'name': code,
            'code': code, 'amount': amount, 'quantity': 1.0, 'rate': 100.0}
            for code, amount in lines.items()])
        slip.write({'state': 'done'})
        return slip

    def setUp(self):
        super().setUp()
        if self.skip_all:
            self.skipTest('the Vietnam employee master is not installed')

    def _raw(self, key):
        wizard = self.env['pb.govt.report.wizard'].create({
            'company_id': self.company.id, 'report_type': key,
            'date_from': date(2026, 10, 1), 'date_to': date(2026, 10, 31),
            'employee_ids': [(6, 0, (self.mai | self.tuan).ids)]})
        content, _ext = self.env['ir.actions.report']._render(REPORTS[key], wizard.ids, {})
        return content

    @staticmethod
    def _parts(raw):
        z = zipfile.ZipFile(io.BytesIO(raw))
        return {n: hashlib.sha256(z.read(n)).hexdigest() for n in sorted(z.namelist())
                if not n.startswith('docProps/')}

    @staticmethod
    def _cells(raw, sheet):
        import openpyxl
        ws = openpyxl.load_workbook(io.BytesIO(raw))[sheet]
        return {c.coordinate: c.value for row in ws.iter_rows() for c in row
                if c.value not in (None, '')}

    def test_s2b2_6a_nothing_mapped_byte_identical(self):
        dump = {key: self._parts(self._raw(key)) for key in REPORTS}
        if os.environ.get('PB_S2B2_GOLDEN_RECORD'):
            os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
            with open(GOLDEN, 'w', encoding='utf-8') as fh:
                json.dump(dump, fh, indent=1, sort_keys=True)
            return
        with open(GOLDEN, encoding='utf-8') as fh:
            golden = json.load(fh)
        self.assertEqual(dump, golden, "with nothing on Form lines the reports are unchanged")

    def test_s2b2_6b_mapped_items_are_used_and_named(self):
        if 'pb.gov.form.map' not in self.env:
            self.skipTest('pb_form_lines is not installed')
        form = self.env['pb.gov.form'].search([('code', '=', 'VN_SI_ITEMS')])
        self.assertTrue(form)
        Map = self.env['pb.gov.form.map']
        line = {l.code: l for l in form.line_ids}
        Map.create({'line_id': line['SICK'].id, 'rule_id': self.items['NGAYOM'].id})
        Map.create({'line_id': line['ALLOW'].id, 'rule_id': self.items['PCAN'].id})
        # BHXH630: sick days from the company's own item, maternity still MAT
        cells = self._cells(self._raw('bhxh630'), 'M01B-HSB-PhatSinh')
        rows = {v: c[1:] for c, v in cells.items() if c.startswith('B') and str(v).startswith('DEMO')}
        self.assertEqual(cells['H' + rows['DEMO S2B2 Mai']], 3)
        self.assertEqual(cells['H' + rows['DEMO S2B2 Tuan']], 1.5)
        notes = [v for v in cells.values() if isinstance(v, str) and v.startswith('Lấy từ')]
        self.assertEqual(len(notes), 1)
        self.assertIn('Ngày nghỉ ốm (chấm công)', notes[0])
        self.assertNotIn('Ngày nghỉ thai sản', notes[0], "maternity is still the fixed code")
        # Headcount increase / decrease: allowances from the item, additions from EXTRA
        for key, sheet, allow_col, extra_col in (('tang_ld', 'TangLaoDong', 'I', 'J'),
                                                 ('giam_ld', 'Truong_hop_Giam', 'H', 'I')):
            cells = self._cells(self._raw(key), sheet)
            rows = {v: c[1:] for c, v in cells.items() if c.startswith('A') and str(v).startswith('DEMO')}
            self.assertEqual(cells[allow_col + rows['DEMO S2B2 Mai']], 1_200_000, key)
            self.assertEqual(cells[allow_col + rows['DEMO S2B2 Tuan']], 800_000, key)
            self.assertEqual(cells[extra_col + rows['DEMO S2B2 Mai']], 500_000, key)
            notes = [v for v in cells.values() if isinstance(v, str) and v.startswith('Lấy từ')]
            self.assertEqual(len(notes), 1, key)
            self.assertIn('Phụ cấp ăn trưa', notes[0])
        # another company's choice changes nothing here
        Map.search([('form_id', '=', form.id)]).unlink()
        self.assertEqual(self._parts(self._raw('tang_ld')),
                         self._parts(self._raw('tang_ld')))
        cells = self._cells(self._raw('tang_ld'), 'TangLaoDong')
        self.assertFalse([v for v in cells.values() if isinstance(v, str) and v.startswith('Lấy từ')])
