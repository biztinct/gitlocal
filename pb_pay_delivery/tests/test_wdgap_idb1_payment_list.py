# -*- coding: utf-8 -*-
"""WDGAP IDB1 — the payment list (any bank), handover tests 1–6 and 8–10.

(Test 7, the Vietnamese bank file byte for byte, is `test_wdgap_idb1_vn_golden`.)

Fixture: one approved run, June 2026, two companies — "home" (the database's
own company and money) with Vietnamese people, and "IDB1 Indonesia" (IDR)
with Indonesian people whose bank details are ONLY a bank account on record
(`res.partner.bank`), never the Vietnamese bank-file fields:

  An     home  5,000,000   Vietcombank account, also in the Vietnamese fields
  Budi   ID    7,500,000   BCA 0012345678 (leading zeros), nothing else
  Citra  ID    3,000,000   no bank account at all
  Dewi   ID    2,000,000   account in another person's name
  Eka    ID    1,000,000   ┐ the same account number
  Fajar  ID    1,500,000   ┘
  Fitri  ID      900,000   holder name close to, not the same as, hers
  Gita   ID    4,000,000   approved 1111222233; a change to 4444555566 waits
  Hadi   ID            0   take-home zero; a 21-digit account number
  Ida    ID      800,000   text that would be a formula in a spreadsheet
  Joko   ID    6,000,000   pay on hold (never in the list)
"""

import csv
import io
import json
import os
import re
import secrets
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_pay_delivery.models.payment_list import safe_text


class _Idb1Fixture(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.home = cls.env.company
        idr = cls.env.ref('base.IDR')
        if not idr.active:
            idr.active = True
        cls.idr = idr
        cls.indo = cls.env['res.company'].create({
            'name': 'IDB1 Indonesia', 'currency_id': idr.id,
            'country_id': cls.env.ref('base.id').id})
        companies = cls.home | cls.indo

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_hr = cls.env.ref('om_hr_payroll.group_hr_payroll_user')
        g_mgr = cls.env.ref('om_hr_payroll.group_hr_payroll_manager')
        common = {'company_id': cls.home.id,
                  'company_ids': [(6, 0, companies.ids)]}
        cls.mgr = Users.create(dict(common, name='IDB1 Pay Manager',
                                    login='idb1_mgr',
                                    group_ids=[(6, 0, [g_mgr.id, g_hr.id])]))
        cls.officer = Users.create(dict(common, name='IDB1 Payroll Officer',
                                        login='idb1_officer',
                                        group_ids=[(6, 0, [g_user.id, g_hr.id])]))
        cls.portal = Users.create({
            'name': 'IDB1 Portal', 'login': 'idb1_portal',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})

        cls.calendar = (cls.home.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'Std'})
        cls.net_rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.net_cat = cls.env.ref('om_hr_payroll.NET')
        Bank = cls.env['res.bank']
        cls.vcb = Bank.create({'name': 'IDB1 Vietcombank'})
        cls.bca = Bank.create({'name': 'IDB1 BCA'})
        cls.mandiri = Bank.create({'name': 'IDB1 Mandiri'})
        cls.formula_bank = Bank.create({'name': '=SUM(A1:A9)'})

        cls.payrun = cls.env['hr.payslip.run'].create({
            'name': 'IDB1 June',
            'date_start': date(2026, 6, 1), 'date_end': date(2026, 6, 30)})
        P = cls._person
        cls.an = P('IDB1 An Nguyen', cls.home, 5000000, cls.vcb, '0071000123456',
                   vn=True)
        cls.budi = P('IDB1 Budi Santoso', cls.indo, 7500000, cls.bca, '0012345678')
        cls.citra = P('IDB1 Citra Dewi', cls.indo, 3000000, None, None)
        cls.dewi = P('IDB1 Dewi Lestari', cls.indo, 2000000, cls.bca, '5550001111',
                     holder='Joko Widodo')
        cls.eka = P('IDB1 Eka Pratama', cls.indo, 1000000, cls.mandiri, '9988776655')
        cls.fajar = P('IDB1 Fajar Nugroho', cls.indo, 1500000, cls.mandiri,
                      '99-8877-6655')
        cls.fitri = P('IDB1 Fitri Handayani', cls.indo, 900000, cls.bca, '7770002222',
                      holder='Fitri Handaya')
        cls.gita = P('IDB1 Gita Permata', cls.indo, 4000000, cls.bca, '1111222233')
        cls.hadi = P('IDB1 Hadi Susanto', cls.indo, 0, cls.bca,
                     '000123456789012345678')
        cls.ida = P('IDB1 Ida Ayu', cls.indo, 800000, cls.formula_bank, '3330004444',
                    holder='+IDB1 Ida Ayu', number='@1234')
        cls.joko = P('IDB1 Joko Purnomo', cls.indo, 6000000, cls.bca, '8880009999')
        cls.slip_of(cls.joko).write({'pb_pay_hold': True,
                                     'pb_hold_reason': 'Waiting for the contract'})

        # Gita's bank change, still waiting for a second person
        Req = cls.env['pb.bank.change.request'].sudo()
        cls.gita_req = Req.create({
            'employee_id': cls.gita.id, 'company_id': cls.indo.id,
            'pb_origin': 'import', 'ocr_state': 'done', 'doc_kind': 'other',
            'x_bank_name': 'IDB1 BCA', 'x_account_name': 'IDB1 Gita Permata',
            'x_account_number': '4444555566'})
        cls.gita_req.write({'state': 'hr_review'})
        # Budi: a waiting "copy" of the account he already has (the BG1
        # kind) proposes nothing new — never a check
        Req.create({
            'employee_id': cls.budi.id, 'company_id': cls.indo.id,
            'pb_origin': 'import', 'ocr_state': 'done', 'doc_kind': 'other',
            'x_bank_name': 'IDB1 BCA', 'x_account_name': 'IDB1 Budi Santoso',
            'x_account_number': '0012345678'}).write({'state': 'hr_review'})

        if hasattr(cls.payrun, '_pb_chain_ctx'):
            cls.payrun._pb_chain_ctx().write({'state': 'done'})
        else:
            cls.payrun.sudo().write({'state': 'done'})
        cls.List = cls.env['pb.payment.list']

    @classmethod
    def _person(cls, name, company, net, bank, account, holder=None, vn=False,
                number=False):
        vals = {'name': name, 'company_id': company.id}
        if number:
            vals['employee_id'] = number
        if vn:
            vals.update({'vietnam_bank_name': 'Vietcombank',
                         'vietnam_bank_branch': 'Hoan Kiem',
                         'vietnam_bank_account_number': account,
                         'vietnam_bank_account_name': name})
        emp = cls.env['hr.employee'].sudo().create(vals)
        if account:
            acc = cls.env['res.partner.bank'].sudo().create({
                'acc_number': account, 'partner_id': emp.work_contact_id.id,
                'bank_id': bank.id if bank else False,
                'acc_holder_name': holder or name})
            emp.bank_account_ids = [(6, 0, [acc.id])]
        contract = cls.env['hr.contract'].sudo().create({
            'name': 'IDB1-%s' % emp.id, 'employee_id': emp.id, 'wage': 1000.0,
            'resource_calendar_id': cls.calendar.id, 'type_id': cls.ctype.id,
            'company_id': company.id})
        slip = cls.env['hr.payslip'].sudo().create({
            'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': cls.payrun.id, 'company_id': company.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        cls.env['hr.payslip.line'].sudo().create({
            'slip_id': slip.id, 'salary_rule_id': cls.net_rule.id,
            'employee_id': emp.id, 'contract_id': contract.id,
            'category_id': cls.net_cat.id, 'name': 'Net', 'code': 'NET',
            'amount': net, 'quantity': 1.0, 'rate': 100.0})
        slip.write({'state': 'done'})
        return emp

    @classmethod
    def slip_of(cls, emp):
        return cls.payrun.slip_ids.filtered(lambda s: s.employee_id == emp)

    def as_mgr(self):
        return self.List.with_user(self.mgr).with_context(
            allowed_company_ids=[self.home.id, self.indo.id])

    def rows(self):
        data = self.List._pb_build_rows(self.payrun)
        return data, {r['employee_id']: r for r in data['rows']}

    def csv_rows(self):
        _name, _mime, payload, _data = self.List.pb_build(self.payrun, 'csv')
        self.assertTrue(payload.startswith(b'\xef\xbb\xbf'))
        return list(csv.reader(io.StringIO(payload.decode('utf-8-sig'))))


@tagged('post_install', '-at_install', 'wdgap_idb1')
class TestIdb1PaymentList(_Idb1Fixture):

    # ------------------------------------------------------------ test 1
    def test_idb1_1_every_bank_paid_payslip_once_totals_per_currency(self):
        data, by_emp = self.rows()
        expected = (self.an | self.budi | self.citra | self.dewi | self.eka
                    | self.fajar | self.fitri | self.gita | self.hadi | self.ida)
        self.assertEqual(set(by_emp), set(expected.ids))
        self.assertEqual(len(data['rows']), len(expected), 'nobody twice')
        self.assertNotIn(self.joko.id, by_emp, 'pay on hold is never listed')
        self.assertEqual(data['left_out']['held'], 1)
        for emp_id, row in by_emp.items():
            slip = self.payrun.slip_ids.filtered(lambda s: s.employee_id.id == emp_id)
            self.assertEqual(row['amount'], slip.pb_pay_totals()['net'])
            self.assertEqual(row['amount'], slip._pb_net_amount())
        home_cur = self.slip_of(self.an)._pb_slip_currency()
        totals = {t['currency']: t for t in data['totals']}
        self.assertEqual(set(totals), {home_cur.name, 'IDR'})
        self.assertEqual(totals[home_cur.name]['amount'], 5000000)
        self.assertEqual(totals[home_cur.name]['count'], 1)
        self.assertEqual(totals['IDR']['amount'],
                         7500000 + 3000000 + 2000000 + 1000000 + 1500000
                         + 900000 + 4000000 + 0 + 800000)
        self.assertEqual(totals['IDR']['count'], 9)
        # the files: one totals row per currency, never one sum of both
        rows = self.csv_rows()
        total_rows = [r for r in rows if r and r[0].startswith('Total ')]
        self.assertEqual(sorted(r[7] for r in total_rows), sorted([home_cur.name, 'IDR']))
        self.assertIn(['Rows', '10'], rows)
        self.assertIn(['Rows with a check', str(data['check_count'])], rows)
        summary = self.List.pb_summary(self.payrun)
        self.assertEqual(summary['count'], 10)
        self.assertEqual(len(summary['totals']), 2)
        self.assertNotIn('rows', summary)

    # ------------------------------------------------------------ test 2
    def test_idb1_2_indonesian_approved_account_no_vn_fields(self):
        self.assertFalse(self.budi.vietnam_bank_account_number)
        _data, by_emp = self.rows()
        row = by_emp[self.budi.id]
        self.assertEqual(row['account'], '0012345678')
        self.assertEqual(row['bank'], 'IDB1 BCA')
        self.assertEqual(row['holder'], 'IDB1 Budi Santoso')
        self.assertEqual(row['currency'], 'IDR')
        self.assertEqual(row['checks'], [], 'a waiting copy of the same account is not a change')
        self.assertEqual(row['reference'], 'IDB1 June, 2026-06-01 - 2026-06-30')
        # the Vietnamese file leaves him out; the list does not
        excluded = self.env['vietnam.bank.export.wizard'].create({
            'payslip_run_id': self.payrun.id, 'bank_format': 'vietcombank',
            'pb_unpaid_only': True})._generate()['excluded']
        self.assertIn(self.budi.id, [x['employee_id'] for x in excluded])
        # An is in both; the list says so
        self.assertEqual(by_emp[self.an.id]['checks'], [])
        self.assertEqual(by_emp[self.an.id]['branch'], 'Hoan Kiem')
        self.assertEqual(by_emp[self.budi.id]['branch'], '')

    # ------------------------------------------------------------ test 3
    def test_idb1_3_no_account(self):
        _data, by_emp = self.rows()
        row = by_emp[self.citra.id]
        self.assertEqual((row['account'], row['bank'], row['holder']), ('', '', ''))
        self.assertIn('No bank account on record', row['checks'])
        line = [r for r in self.csv_rows() if r and r[1] == 'IDB1 Citra Dewi'][0]
        self.assertEqual(line[5], '')
        self.assertIn('No bank account on record', line[10])

    # ------------------------------------------------------------ test 4
    def test_idb1_4_holder_name_and_shared_account(self):
        _data, by_emp = self.rows()
        self.assertIn("The account is in another person's name", by_emp[self.dewi.id]['checks'])
        self.assertTrue(any('close to' in c for c in by_emp[self.fitri.id]['checks']))
        eka, fajar = by_emp[self.eka.id], by_emp[self.fajar.id]
        self.assertIn('Same account as IDB1 Fajar Nugroho in this list', eka['checks'])
        self.assertIn('Same account as IDB1 Eka Pratama in this list', fajar['checks'])
        for other in (self.budi, self.an, self.gita):
            self.assertFalse([c for c in by_emp[other.id]['checks'] if 'Same account' in c])

    # ------------------------------------------------------------ test 5
    def test_idb1_5_waiting_change_never_used_until_approved(self):
        _data, by_emp = self.rows()
        row = by_emp[self.gita.id]
        self.assertEqual(row['account'], '1111222233', 'the last APPROVED account')
        self.assertIn('A bank change is waiting for approval; this list uses the last approved account', row['checks'])
        # approved by the second person: the request's own path writes both stores
        self.gita_req._apply_to_master()
        self.gita_req.write({'state': 'approved'})
        self.env.invalidate_all()
        _data, by_emp = self.rows()
        row = by_emp[self.gita.id]
        self.assertEqual(row['account'], '4444555566')
        self.assertEqual(row['checks'], [])

    def test_idb1_5b_waiting_updates_proposal_is_flagged(self):
        Apply = self.env.get('pb.records.apply')
        if Apply is None or 'touches_bank' not in Apply._fields:
            self.skipTest('pb_records not installed')
        Apply.sudo().create({
            'name': 'IDB1 RD', 'source': 'desk', 'state': 'pending',
            'touches_bank': True, 'lane': 'bank',
            'plan_json': json.dumps([{'emp_id': self.budi.id, 'field_id': 'b:acc_number',
                                      'old': '0012345678', 'new_label': '0099'}])})
        _data, by_emp = self.rows()
        row = by_emp[self.budi.id]
        self.assertEqual(row['account'], '0012345678')
        self.assertIn('A bank change is waiting for approval; this list uses the last approved account', row['checks'])

    def test_idb1_5c_zero_take_home_and_two_readings(self):
        _data, by_emp = self.rows()
        self.assertIn('Take-home is zero or below', by_emp[self.hadi.id]['checks'])
        # a second net line: the band reading and the take-home line disagree
        slip = self.slip_of(self.budi)
        self.env['hr.payslip.line'].sudo().create({
            'slip_id': slip.id, 'salary_rule_id': self.net_rule.id,
            'employee_id': self.budi.id, 'contract_id': slip.contract_id.id,
            'category_id': self.net_cat.id, 'name': 'Net 2', 'code': 'NETTWO',
            'amount': 100.0, 'quantity': 1.0, 'rate': 100.0})
        self.env.invalidate_all()
        _data, by_emp = self.rows()
        self.assertTrue(any('two ways' in c for c in by_emp[self.budi.id]['checks']))

    # ------------------------------------------------------------ test 6
    def test_idb1_6_text_cells_leading_zeros_and_formula_escape(self):
        self.assertEqual(safe_text('=1+1'), "'=1+1")
        self.assertEqual(safe_text('+62'), "'+62")
        self.assertEqual(safe_text('-5'), "'-5")
        self.assertEqual(safe_text('@x'), "'@x")
        self.assertEqual(safe_text('0012'), '0012')
        rows = self.csv_rows()
        header = rows[0]
        self.assertEqual(header[5], 'Account number')
        by_name = {r[1]: r for r in rows[1:] if len(r) > 10}
        self.assertEqual(by_name['IDB1 Budi Santoso'][5], '0012345678')
        self.assertEqual(by_name['IDB1 Hadi Susanto'][5], '000123456789012345678')
        ida = by_name['IDB1 Ida Ayu']
        self.assertEqual(ida[0], "'@1234")
        self.assertEqual(ida[2], "'+IDB1 Ida Ayu")
        self.assertEqual(ida[3], "'=SUM(A1:A9)")
        # plain digits, the money's own decimals, no thousands separator
        self.assertEqual(by_name['IDB1 Budi Santoso'][6],
                         '%.*f' % (self.idr.decimal_places, 7500000))
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl is not installed to read the Excel file back')
        _name, _mime, payload, _data = self.List.pb_build(self.payrun, 'xlsx')
        sheet = openpyxl.load_workbook(io.BytesIO(payload)).active
        cells = {}
        for row in sheet.iter_rows(min_row=2):
            if row[1].value:
                cells[row[1].value] = row
        budi = cells['IDB1 Budi Santoso']
        self.assertEqual(budi[5].value, '0012345678')
        self.assertEqual(budi[5].data_type, 's')
        hadi = cells['IDB1 Hadi Susanto']
        self.assertEqual(hadi[5].value, '000123456789012345678')
        self.assertEqual(hadi[5].data_type, 's', 'never a number, never 1.23E+20')
        self.assertEqual(budi[6].value, 7500000)
        ida = cells['IDB1 Ida Ayu']
        self.assertEqual(ida[3].value, "'=SUM(A1:A9)")
        self.assertNotEqual(ida[3].data_type, 'f')
        for row in sheet.iter_rows():
            for cell in row:
                self.assertNotEqual(cell.data_type, 'f', 'no formula anywhere')

    # ------------------------------------------------------------ test 8
    def test_idb1_8_only_the_bank_file_people(self):
        # the pay manager (who may download the bank file) may
        name, _mime, payload, = self.as_mgr().pb_download(self.payrun.id, 'csv')
        self.assertTrue(payload)
        self.env.flush_all()
        self.env.invalidate_all()
        for user in (self.officer, self.portal):
            List = self.List.with_user(user)
            with self.assertRaises(AccessError):
                List.pb_download(self.payrun.id, 'csv')
            with self.assertRaises(AccessError):
                self.env['pb.pay.delivery'].with_user(user).payment_list_check(
                    self.payrun.id, 'xlsx')
            with self.assertRaises(AccessError):
                self.env['pb.pay.delivery'].with_user(user).get_delivery_data(self.payrun.id)

    def test_idb1_8b_run_not_approved_is_refused(self):
        run = self.env['hr.payslip.run'].create({
            'name': 'IDB1 Draft run',
            'date_start': date(2026, 7, 1), 'date_end': date(2026, 7, 31)})
        with self.assertRaises(UserError):
            self.as_mgr().pb_download(run.id, 'xlsx')
        with self.assertRaises(UserError):
            self.as_mgr().pb_download(self.payrun.id, 'pdf')

    # ------------------------------------------------------------ test 9
    def test_idb1_9_download_logged_without_account_numbers(self):
        Entry = self.env['biz.audit.entry'].sudo()
        before = Entry.search_count([('model_name', '=', 'hr.payslip.run'),
                                     ('res_id', '=', self.payrun.id)])
        self.as_mgr().pb_download(self.payrun.id, 'xlsx')
        entries = Entry.search([('model_name', '=', 'hr.payslip.run'),
                                ('res_id', '=', self.payrun.id),
                                ('field_name', '=', 'pb_payment_list')])
        self.assertEqual(len(entries), 1)
        self.assertEqual(Entry.search_count([('model_name', '=', 'hr.payslip.run'),
                                             ('res_id', '=', self.payrun.id)]), before + 1)
        text = ' '.join([entries.new_value or '', entries.old_value or '',
                         entries.field_label or '', entries.res_display or ''])
        self.assertIn('IDB1 Pay Manager', text)
        self.assertIn('10 rows', text)
        self.assertEqual(entries.create_uid, self.mgr)
        for number in ('0012345678', '1111222233', '9988776655', '5550001111',
                       '000123456789012345678', '0071000123456'):
            self.assertNotIn(number, text)
        self.assertFalse(re.search(r'\d{6,}', text), 'no account number in the log')

    # ------------------------------------------------------------ test 10
    def test_idb1_10_no_vendor_name_in_any_file(self):
        import zipfile
        for kind in ('xlsx', 'csv'):
            name, _mime, payload, _data = self.List.pb_build(self.payrun, kind)
            self.assertNotIn('odoo', name.lower())
            self.assertTrue(name.startswith('Payment list - IDB1 June - 2026-06-30'))
            if kind == 'csv':
                self.assertNotIn(b'odoo', payload.lower())
                continue
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                for member in zf.namelist():
                    self.assertNotIn(b'odoo', zf.read(member).lower(), member)
                sheet_names = zf.read('xl/workbook.xml')
                self.assertIn(b'Payment list', sheet_names)

    def test_idb1_screen_payload(self):
        data = self.env['pb.pay.delivery'].with_user(self.mgr).with_context(
            allowed_company_ids=[self.home.id, self.indo.id]).get_delivery_data(self.payrun.id)
        summary = data['payment_list']
        self.assertEqual(summary['count'], 10)
        self.assertTrue(summary['approved'])
        self.assertGreaterEqual(summary['check_count'], 6)
        self.assertNotIn('payable_slip_ids', summary)
        dumped = json.dumps(summary)
        self.assertNotIn('0012345678', dumped, 'no account number on the screen payload')
        # left out of the Vietnamese file but payable from the list: everybody
        # with an approved account except An (in the file) and Citra (none)
        self.assertEqual(data['validation']['payment_list_can_pay'], 8)


@tagged('post_install', '-at_install', 'wdgap_idb1')
class TestIdb1Translations(TransactionCase):
    """Test 10: every new string has a Vietnamese and an Indonesian entry that
    loads (the three things a PO entry needs), and no vendor name anywhere a
    person can read it."""

    def _module_path(self, *parts):
        from odoo.modules.module import get_module_path
        return os.path.join(get_module_path('pb_pay_delivery'), *parts)

    def _new_strings(self):
        """Every `_("…")` of the payment list, read from its own source."""
        source = open(self._module_path('models', 'payment_list.py'), encoding='utf-8').read()
        found = set(re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"', source))
        found |= set(re.findall(r"_\(\s*'((?:[^'\\]|\\.)*)'", source))
        found = {s.replace("\\'", "'").replace('\\"', '"') for s in found}
        found.add("People with an approved bank account at a bank this file does not know can be paid from the payment list (any bank) on Pay & deliver.")
        found |= {"Payment list (any bank)", "none need a check",
                  "Ready once the pay run is approved.",
                  "%s people left out have an approved bank account and can be paid from the payment list (any bank) below."}
        return found

    def test_idb1_10_vi_and_id_entries_load(self):
        from odoo.tools.translate import PoFileReader
        wanted = self._new_strings()
        self.assertGreater(len(wanted), 30)
        for lang in ('vi_VN', 'id_ID'):
            path = self._module_path('i18n', '%s.po' % lang)
            with open(path, 'rb') as handle:
                rows = list(PoFileReader(handle))
            loaded = {}
            for row in rows:
                if row['type'] == 'code' and row['value'] and (
                        'odoo-python' in row['comments']
                        or 'odoo-javascript' in row['comments']):
                    loaded[row['src']] = row['value']
            missing = sorted(s for s in wanted if s not in loaded)
            self.assertFalse(missing, '%s: no loadable entry for %s' % (lang, missing))
            for src, value in loaded.items():
                self.assertNotIn('odoo', value.lower(), '%s: %s' % (lang, src))
            header = open(path, encoding='utf-8').read(600)
            self.assertIn('Project-Id-Version: Payobook 19.0', header)

    def test_idb1_10_no_vendor_name_in_new_user_text(self):
        for parts in (('models', 'payment_list.py'), ('controllers', 'payment_list.py')):
            source = open(self._module_path(*parts), encoding='utf-8').read()
            for text in re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"', source):
                self.assertNotIn('odoo', text.lower(), text)
        xml = open(self._module_path('static', 'src', 'xml', 'pb_pay_delivery.xml'),
                   encoding='utf-8').read()
        card = xml[xml.index('card 1b'):xml.index('card 2')]
        self.assertNotIn('odoo', re.sub(r'<[^>]*>', ' ', card).lower())


@tagged('post_install', '-at_install', 'wdgap_idb1')
class TestIdb1PaymentListUrl(_Idb1Fixture, HttpCase):
    """Test 8 by the direct address (ledger S9A-5: the fixture's one
    setUpClass chain runs into HttpCase's)."""

    def _login(self, user):
        password = secrets.token_urlsafe(18)    # made here, kept nowhere
        user.sudo().password = password
        self.authenticate(user.login, password)

    def _get(self, fmt='csv'):
        return self.url_open('/pb_pay_delivery/payment_list?run_id=%s&fmt=%s'
                             % (self.payrun.id, fmt))

    def test_idb1_8_url_refused_for_officer_and_portal(self):
        for user in (self.officer, self.portal):
            self._login(user)
            response = self._get()
            self.assertEqual(response.status_code, 403, user.login)
            self.assertNotIn(b'0012345678', response.content)
            self.assertNotIn(b'odoo', response.content.lower())

    def test_idb1_8_url_works_for_the_pay_manager(self):
        self._login(self.mgr)
        response = self._get('csv')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
        self.assertIn(b'0012345678', response.content)
        response = self._get('xlsx')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'PK'))
