# -*- coding: utf-8 -*-
"""Server tests for Phase F — Pay & Deliver (§6 cases 1–10).

Covers data-driven layout resolution, validated file generation (CSV content
with diacritics, fixed-width TXT offsets, XLSX numeric cells, VietinBank + ACB),
exclusion-not-silent-drop, batch payslip delivery (queue rows, skip-no-email,
idempotence, resend), per-employee PDF encryption round-trip, access control,
and the done-only delivery filter.
"""

import base64
import csv
import io

from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:  # pragma: no cover
    PdfReader = PdfWriter = None

_RENDER = ('odoo.addons.pb_pay_delivery.models.payslip_delivery.'
           'PbPayslipDeliveryBatch._render_pdf')


def _valid_pdf_bytes():
    """A real one-page PDF. wkhtmltopdf can't fetch report assets during a
    `--stop-after-init` test run (no HTTP server), so the two delivery tests
    mock the render with THIS valid PDF to exercise the real encryption / mail /
    idempotence path headlessly. The live wkhtmltopdf render is validated with
    the server up (Chrome-MCP, §6.11-12)."""
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


@tagged('post_install', '-at_install')
class TestPayDelivery(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_hr = cls.env.ref('om_hr_payroll.group_hr_payroll_user')
        g_mgr = cls.env.ref('om_hr_payroll.group_hr_payroll_manager')
        cls.emp_user = Users.create({'name': 'Plain', 'login': 'pd_plain',
                                     'group_ids': [(6, 0, [g_user.id])]})
        cls.mgr_user = Users.create({'name': 'Mgr', 'login': 'pd_mgr',
                                     'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'Std'})
        cls.net_rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.net_cat = cls.env.ref('om_hr_payroll.NET')

        cls.payrun = cls.env['hr.payslip.run'].create({
            'name': 'ZZ Pay & Deliver June',
            'date_start': date(2026, 6, 1), 'date_end': date(2026, 6, 30)})

    # ------------------------------------------------------------- fixtures
    @classmethod
    def _employee(cls, name, account, bank='Vietcombank', email='x@example.com',
                  holder=None):
        return cls.env['hr.employee'].create({
            'name': name, 'company_id': cls.company.id,
            'work_email': email, 'birthday': date(1990, 5, 20),
            'vietnam_bank_name': bank, 'vietnam_bank_branch': 'Hoan Kiem',
            'vietnam_bank_account_number': account,
            'vietnam_bank_account_name': holder or name})

    @classmethod
    def _contract(cls, emp):
        return cls.env['hr.contract'].create({
            'name': 'C-%s' % emp.id, 'employee_id': emp.id, 'wage': 1000.0,
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.ctype.id})

    @classmethod
    def _slip(cls, emp, net, state='done'):
        contract = cls._contract(emp)
        slip = cls.env['hr.payslip'].create({
            'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': cls.payrun.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        cls.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'salary_rule_id': cls.net_rule.id,
            'employee_id': emp.id, 'contract_id': contract.id,
            'category_id': cls.net_cat.id, 'name': 'Net', 'code': 'NET',
            'amount': net, 'quantity': 1.0, 'rate': 100.0})
        if state:
            slip.write({'state': state})
        return slip

    def _wizard(self, bank_format='vietcombank'):
        return self.env['vietnam.bank.export.wizard'].create({
            'payslip_run_id': self.payrun.id, 'bank_format': bank_format})

    def _decode(self, result, layout_format='vietcombank'):
        raw = base64.b64decode(result['file_b64'])
        layout = self.env['pb.bank.file.layout']._for_format(layout_format)
        return raw.decode(layout.encoding or 'utf-8')

    # ============================================================= §6.1
    def test_01_layout_resolution(self):
        Layout = self.env['pb.bank.file.layout']
        for key in ('vietcombank', 'bidv', 'techcombank', 'mb_bank',
                    'vietinbank', 'acb', 'generic'):
            self.assertTrue(Layout._for_format(key),
                            "no layout for %s" % key)
        # a missing layout raises a friendly UserError at generation
        Layout._for_format('generic').unlink()
        self._slip(self._employee('Gen One', '123456789012'), 5000000)
        with self.assertRaises(UserError):
            self._wizard('generic')._generate()

    # ============================================================= §6.2
    def test_02_csv_content_diacritics_and_net(self):
        emp = self._employee('Nguyễn Văn Á', '123456789012')
        self._slip(emp, 12500000)
        result = self._wizard('vietcombank')._generate()
        text = self._decode(result, 'vietcombank')
        self.assertIn('123456789012', text)
        self.assertIn('Nguyễn Văn Á', text)   # diacritics intact (utf-8-sig)
        self.assertIn('12500000', text)         # NET, integer, no separator
        # exactly one data row (+ header)
        rows = [r for r in csv.reader(io.StringIO(text)) if r]
        self.assertEqual(len(rows), 2)
        self.assertEqual(result['valid'], 1)

    # ============================================================= §6.3a TXT
    def test_03_fixed_width_txt_offsets(self):
        emp = self._employee('Le Van Bidv', '0011223344',
                             bank='VietinBank')
        self._slip(emp, 9000000)
        result = self._wizard('vietinbank')._generate()
        raw = base64.b64decode(result['file_b64']).decode('utf-8')
        line = raw.splitlines()[0]
        # account[0:19] left-justified, holder[19:51], amount[51:66] zero, bank[66:86]
        self.assertEqual(len(line), 86)
        self.assertEqual(line[0:19].strip(), '0011223344')
        self.assertEqual(line[19:51].strip(), 'Le Van Bidv')
        self.assertEqual(line[51:66], '000000009000000')  # 15-wide zero-pad
        self.assertEqual(line[66:86].strip(), 'VietinBank')

    # ============================================================= §6.3b XLSX
    def test_04_xlsx_numeric_amount(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl not available to read back the xlsx')
        emp = self._employee('Mb Earner', '555566667777', bank='MB')
        self._slip(emp, 7300000)
        result = self._wizard('mb_bank')._generate()
        self.assertEqual(result['file_type'], 'xlsx')
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(result['file_b64'])))
        ws = wb.active
        # header row 1, data row 2; amount column (D = 4th, index col 4)
        amount_cell = ws.cell(row=2, column=4)
        self.assertEqual(amount_cell.value, 7300000)
        self.assertIsInstance(amount_cell.value, (int, float))

    # ============================================================= §6.4
    def test_05_vietinbank_and_acb_nonempty(self):
        self._slip(self._employee('CTG Emp', '111122223333', bank='VietinBank'),
                   6000000)
        for fmt in ('vietinbank', 'acb'):
            result = self._wizard(fmt)._generate()
            self.assertGreater(result['byte_size'], 0)
            self.assertGreaterEqual(result['valid'], 1)

    # ============================================================= §6.5
    def test_06_validation_excludes_not_drops(self):
        good = self._employee('Good One', '123456789012')
        bad = self._employee('Bad Acct', '123')   # fails account_ok
        self._slip(good, 5000000)
        self._slip(bad, 5000000)
        result = self._wizard('vietcombank')._generate()
        self.assertEqual(result['valid'], 1)       # only the good row
        self.assertEqual(len(result['excluded']), 1)
        self.assertEqual(result['excluded'][0]['employee'], 'Bad Acct')
        self.assertTrue(any('account' in r for r in result['excluded'][0]['reasons']))
        # zero valid rows → UserError, no file
        good.write({'vietnam_bank_account_number': '99'})  # now also invalid
        with self.assertRaises(UserError):
            self._wizard('vietcombank')._generate()

    # ============================================================= §6.7
    def test_07_delivery_queue_skip_idempotent_resend(self):
        e1 = self._employee('Has Email 1', '123456789012', email='a@ex.com')
        e2 = self._employee('Has Email 2', '123456789013', email='b@ex.com')
        e3 = self._employee('No Email', '123456789014', email=False)
        for e in (e1, e2, e3):
            self._slip(e, 4000000)
        batch = self.env['pb.payslip.delivery.batch'].create({'run_id': self.payrun.id})
        before = self.env['mail.mail'].search_count([])
        with patch(_RENDER, return_value=_valid_pdf_bytes()):
            batch.action_send()
            after = self.env['mail.mail'].search_count([])
            self.assertEqual(after - before, 2)          # 2 queued, 1 skipped
            self.assertEqual(batch.sent_count, 2)
            self.assertEqual(batch.skipped_count, 1)
            # re-run: idempotent, no new mail rows
            batch.action_send()
            self.assertEqual(self.env['mail.mail'].search_count([]) - before, 2)
            # force_all: resends the sent lines
            batch.action_send(force_all=True)
            self.assertEqual(self.env['mail.mail'].search_count([]) - before, 4)

    # ============================================================= §6.8
    def test_08_pdf_encryption_roundtrip(self):
        if PdfReader is None:
            self.skipTest('PyPDF2 not installed on this runner')
        emp = self._employee('Lock Me', '123456789012', email='c@ex.com')
        slip = self._slip(emp, 8000000)
        batch = self.env['pb.payslip.delivery.batch'].create({'run_id': self.payrun.id})
        with patch(_RENDER, return_value=_valid_pdf_bytes()):
            batch.action_send()
        line = batch.line_ids.filtered(lambda l: l.slip_id == slip)
        self.assertEqual(line.state, 'sent')
        att = self.env['ir.attachment'].search(
            [('res_model', '=', 'hr.payslip'), ('res_id', '=', slip.id)], limit=1)
        pdf = base64.b64decode(att.datas)
        reader = PdfReader(io.BytesIO(pdf))
        self.assertTrue(reader.is_encrypted)
        # wrong password refused, right password opens
        bad = PdfReader(io.BytesIO(pdf))
        self.assertFalse(bad.decrypt('wrongpass'))
        good = PdfReader(io.BytesIO(pdf))
        pwd = batch._resolve_password(emp)      # {account_last4}{birth_year}
        self.assertEqual(pwd, '9012' + '1990')
        self.assertTrue(good.decrypt(pwd))

    # ============================================================= §6.9
    def test_09_access_control(self):
        self._slip(self._employee('Acc Emp', '123456789012'), 5000000)
        wiz = self._wizard('vietcombank')
        with self.assertRaises(AccessError):
            wiz.with_user(self.emp_user).action_export_file()
        # a manager may generate
        wiz.with_user(self.mgr_user).action_export_file()
        self.assertTrue(wiz.export_file)
        batch = self.env['pb.payslip.delivery.batch'].create({'run_id': self.payrun.id})
        with self.assertRaises(AccessError):
            batch.with_user(self.emp_user).action_send()

    # ============================================================= §6.10
    def test_10_draft_slips_refused(self):
        emp = self._employee('Draft Guy', '123456789012', email='d@ex.com')
        self._slip(emp, 5000000, state='draft')     # not done
        batch = self.env['pb.payslip.delivery.batch'].create({'run_id': self.payrun.id})
        with self.assertRaises(UserError):
            batch.action_send()
        # a wizard over only-draft slips also refuses (no done rows)
        with self.assertRaises(UserError):
            self._wizard('vietcombank')._generate()

    # ------------------------------------------------- facade smoke + access
    def test_11_facade_payload_and_guard(self):
        self._slip(self._employee('Facade Emp', '123456789012', email='e@ex.com'),
                   5000000)
        Facade = self.env['pb.pay.delivery']
        data = Facade.with_user(self.mgr_user).get_delivery_data(self.payrun.id)
        self.assertEqual(data['run']['id'], self.payrun.id)
        self.assertGreaterEqual(data['validation']['eligible'], 1)
        self.assertEqual(len(data['banks']), 7)
        with self.assertRaises(AccessError):
            Facade.with_user(self.emp_user).get_delivery_data(self.payrun.id)

    def test_12_password_never_stored_on_line(self):
        """Safety rail 4: no delivery-line field ever holds the password."""
        fields = self.env['pb.payslip.delivery']._fields
        joined = ' '.join(fields).lower()
        self.assertNotIn('password', joined)
        self.assertNotIn('pwd', joined)

    def test_13_underivable_password_fails_surfaced(self):
        """Rail 4 hardening: no static-fallback password — a slip whose password
        cannot be derived FAILS with a surfaced reason, never ships guessable."""
        emp = self._employee('No Secrets', '', email='f@ex.com')
        emp.write({'birthday': False, 'barcode': False, 'identification_id': False})
        slip = self._slip(emp, 5000000)
        batch = self.env['pb.payslip.delivery.batch'].create({'run_id': self.payrun.id})
        before = self.env['mail.mail'].search_count([])
        with patch(_RENDER, return_value=_valid_pdf_bytes()):
            batch.action_send()
        line = batch.line_ids.filtered(lambda l: l.slip_id == slip)
        self.assertEqual(line.state, 'failed')
        self.assertIn('password', (line.error or '').lower())
        self.assertEqual(self.env['mail.mail'].search_count([]), before)  # nothing queued
