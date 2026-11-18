# -*- coding: utf-8 -*-
"""WDGAP S2-C — bank payment files for any country (handover tests 3–11).

Test 1 (the Vietnamese bank file, byte for byte) is the IDB1 golden test,
`test_wdgap_idb1_vn_golden`, kept as it is, plus test 6 below (a copy of a
Vietnamese layout gives the same bytes). Test 2 (the general payment list,
byte for byte) is `test_wdgap_s2c_golden`.

Fixture: the IDB1 run (two companies, home money + IDR; see
`test_wdgap_idb1_payment_list`). With the shipped Indonesian layout:

  An     home money, Vietcombank   left out: another money, no Indonesian code
  Budi   BCA 014                   in the file
  Citra  no account                left out: no bank account on record
  Dewi   BCA (another's name)      in (the general list flags the name)
  Eka    Mandiri 008               in ┐ same account: flagged on the list
  Fajar  Mandiri 008               in ┘
  Fitri  BCA                       in
  Gita   BCA, change waiting       in, with the LAST APPROVED account
  Hadi   BCA, take-home 0          left out: zero or below
  Ida    bank "=SUM(A1:A9)"        left out: no code, formula signs
  Joko   on hold                   not in the list at all
"""

import base64
import csv
import importlib.util
import io
import json
import os
import re
import secrets
from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.pb_pay_delivery.tests import test_wdgap_idb1_payment_list as idb1
from odoo.addons.pb_pay_delivery.tests import test_wdgap_s2c_golden as golden

IN_FILE = ('IDB1 Budi Santoso', 'IDB1 Dewi Lestari', 'IDB1 Eka Pratama',
           'IDB1 Fajar Nugroho', 'IDB1 Fitri Handayani', 'IDB1 Gita Permata')
IN_TOTAL = 7500000 + 2000000 + 1000000 + 1500000 + 900000 + 4000000


class _S2cFixture(idb1._Idb1Fixture):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Layout = cls.env['pb.bank.file.layout']
        cls.id_layout = cls.env.ref('pb_pay_delivery.layout_id_general')
        cls.in_layout = cls.env.ref('pb_pay_delivery.layout_in_neft')
        cls.sg_layout = cls.env.ref('pb_pay_delivery.layout_sg_giro')

    def build(self, layout, **options):
        options.setdefault('payment_date', date(2026, 6, 30))
        return self.List._pb_layout_build(self.payrun, layout, options)

    def csv_of(self, result, encoding='utf-8'):
        return list(csv.reader(io.StringIO(result['payload'].decode(encoding))))

    def own_copy(self, layout, company=None, **values):
        copy = layout.pb_copy_for_company(company or self.home)
        if values:
            copy.write(values)
        return copy

    def crafted(self, code, currency, n=3, **over):
        rows = []
        for i in range(n):
            row = {
                'slip_id': i + 1, 'employee_id': i + 1,
                'employee_number': 'S2C%02d' % i, 'employee_name': 'S2C Person %s' % i,
                'holder': 'S2C Person %s' % i, 'bank': 'S2C Bank', 'branch': '',
                'account': '00%08d' % (i + 1), 'amount': 1000.5 * (i + 1),
                'currency': currency.name, 'take_home': 1000.5 * (i + 1),
                'bic': '', 'code': code, 'email': '',
            }
            row.update(over)
            rows.append(row)
        return rows


@tagged('post_install', '-at_install', 'wdgap_s2c')
class TestS2cLayouts(_S2cFixture):

    # ------------------------------------------------------------ test 3
    def test_s2c_3a_indonesian_layout_renders_the_run(self):
        result = self.build(self.id_layout)
        self.assertEqual(sorted(r['employee'] for r in result['included']), sorted(IN_FILE))
        self.assertEqual(result['count'], 6)
        self.assertEqual(result['total'], IN_TOTAL)
        self.assertEqual(result['currency'], 'IDR')
        rows = self.csv_of(result)
        self.assertEqual(rows[0], ['No', 'Bank code', 'Bank', 'Account number',
                                   'Account holder', 'Amount', 'Currency', 'Reference'])
        by_holder = {r[4]: r for r in rows[1:]}
        budi = by_holder['IDB1 Budi Santoso']
        self.assertEqual(budi[1], '014', 'BCA, from the bank directory')
        self.assertEqual(budi[3], '0012345678', 'leading zeros kept')
        self.assertEqual(budi[5], '7500000.00')
        self.assertEqual(budi[7], 'IDB1 June, 2026-06-01 - 2026-06-30')
        self.assertEqual(by_holder['IDB1 Eka Pratama'][1], '008', 'Mandiri')
        self.assertEqual(by_holder['Joko Widodo'][4], 'Joko Widodo',
                         "the account holder on record, never changed")
        self.assertEqual(by_holder['IDB1 Gita Permata'][3], '1111222233',
                         'a bank change waiting for approval is never used')
        self.assertEqual([r[0] for r in rows[1:]], ['1', '2', '3', '4', '5', '6'])
        self.assertEqual(len(rows), 7, 'header + 6 payments, nothing else')
        self.assertTrue(result['filename'].startswith('Indonesia'))

    def test_s2c_3b_header_trailer_counts_totals_and_formats(self):
        layout = self.own_copy(self.id_layout, header_template='H,{date},{company_account},{count},{total},{currency}',
                               trailer_template='T,{count},{total}', amount_format='implied2',
                               date_format='%d%m%Y', with_header=False)
        result = self.build(layout, company_account='0099887766')
        rows = self.csv_of(result)
        self.assertEqual(rows[0], ['H', '30062026', '0099887766', '6', '%d' % (IN_TOTAL * 100), 'IDR'])
        self.assertEqual(rows[-1], ['T', '6', '%d' % (IN_TOTAL * 100)])
        self.assertEqual(len(rows), 8, 'header line + 6 payments + trailer line')
        # amounts per format on the amount column
        amount_col = layout.column_ids.filtered(lambda c: c.source == 'net_amount')
        for fmt, expected in (('dec2', '7500000.00'), ('implied2', '750000000'),
                              ('int', '7500000'), ('int_grouped', '7,500,000')):
            amount_col.number_format = fmt
            body = {r[4]: r for r in self.csv_of(self.build(layout))[1:-1]}
            self.assertEqual(body['IDB1 Budi Santoso'][5], expected, fmt)
        # a count and a control-total column on every row
        layout.column_ids = [(0, 0, {'sequence': 200, 'header': 'Count', 'source': 'row_count'}),
                             (0, 0, {'sequence': 210, 'header': 'Total', 'source': 'control_total',
                                     'number_format': 'dec2'})]
        body = self.csv_of(self.build(layout))[1:-1]
        self.assertTrue(all(r[-2] == '6' and r[-1] == '%.2f' % IN_TOTAL for r in body))

    def test_s2c_3c_fixed_width_text_never_cuts(self):
        layout = self.own_copy(self.id_layout, file_type='txt', with_header=False,
                               trailer_template='T{count}')
        widths = {'row_number': (4, 'zero'), 'bank_clearing_code': (3, 'right'),
                  'bank_name': (20, 'right'), 'account_number': (21, 'right'),
                  'account_name': (30, 'right'), 'net_amount': (15, 'zero'),
                  'currency': (3, 'right'), 'reference': (40, 'right')}
        for col in layout.column_ids:
            col.write({'width': widths[col.source][0], 'pad': widths[col.source][1]})
        layout.column_ids.filtered(lambda c: c.source == 'net_amount').number_format = 'implied2'
        result = self.build(layout)
        lines = result['payload'].decode().split('\r\n')
        self.assertEqual(lines[-1], '', 'every line ends with CR LF')
        body = lines[:-2]
        self.assertEqual(lines[-2], 'T6')
        self.assertTrue(all(len(line) == sum(w for w, _p in widths.values()) for line in body))
        self.assertTrue(body[0].startswith('0001014'))
        self.assertIn('000000750000000', lines[0] + ''.join(body))
        # a value longer than its width leaves the person out — never cut
        layout.column_ids.filtered(lambda c: c.source == 'account_name').width = 12
        result = self.build(layout)
        names = [x['employee'] for x in result['excluded']]
        self.assertIn('IDB1 Fajar Nugroho', names)
        reasons = [x for x in result['excluded'] if x['employee'] == 'IDB1 Fajar Nugroho'][0]['reasons']
        self.assertIn('The account holder name is longer than this bank takes (12 characters)', reasons)
        self.assertNotIn(b'IDB1 Fajar N', result['payload'])

    def test_s2c_3d_india_and_singapore_layouts(self):
        inr = self.env.ref('base.INR')
        rows = self.crafted('HDFC0001234', inr)
        rows[1]['code'] = 'HDFC'               # only the bank's prefix: not an IFSC
        rows[2]['code'] = ''
        result = self.List._pb_layout_render(self.in_layout, rows, {
            'payment_date': date(2026, 6, 30), 'reference': 'S2C June'})
        out = self.csv_of(result)
        self.assertEqual(out[0], ['Beneficiary name', 'Beneficiary account number', 'IFSC',
                                  'Amount', 'Payment date', 'Remarks'])
        self.assertEqual(out[1], ['S2C Person 0', '0000000001', 'HDFC0001234', '1000.50',
                                  '30/06/2026', 'S2C June'])
        self.assertEqual(result['count'], 1)
        left = {x['employee']: x['reasons'] for x in result['excluded']}
        self.assertIn('IFSC on record (HDFC) is not in the form this bank needs', left['S2C Person 1'])
        self.assertIn('IFSC is missing', left['S2C Person 2'])
        sgd = self.env.ref('base.SGD')
        rows = self.crafted('7171005', sgd)
        rows[2]['code'] = '71710'
        result = self.List._pb_layout_render(self.sg_layout, rows, {
            'payment_date': date(2026, 6, 30), 'reference': 'S2C'})
        out = self.csv_of(result)
        self.assertEqual(out[1], ['S2C Person 0', '7171005', '0000000001', '1000.50', '20260630', 'S2C'])
        self.assertEqual(result['count'], 2)
        self.assertEqual(result['total'], 1000.5 + 2001.0)
        self.assertEqual(result['currency'], 'SGD')

    def test_s2c_3e_excel_layout_keeps_text_as_text(self):
        try:
            import openpyxl
        except ImportError:
            self.skipTest('openpyxl is not installed')
        layout = self.own_copy(self.id_layout, file_type='xlsx')
        result = self.build(layout)
        sheet = openpyxl.load_workbook(io.BytesIO(result['payload'])).active
        cells = {row[4].value: row for row in sheet.iter_rows(min_row=2)}
        budi = cells['IDB1 Budi Santoso']
        self.assertEqual(budi[3].value, '0012345678')
        self.assertEqual(budi[3].data_type, 's')
        self.assertEqual(budi[5].value, 7500000)
        for row in sheet.iter_rows():
            for cell in row:
                self.assertNotEqual(cell.data_type, 'f')

    # ------------------------------------------------------------ test 4
    def test_s2c_4_left_out_with_reasons_and_in_the_check_column(self):
        result = self.build(self.id_layout)
        left = {x['employee']: x['reasons'] for x in result['excluded']}
        self.assertEqual(set(left), {'IDB1 An Nguyen', 'IDB1 Citra Dewi',
                                     'IDB1 Hadi Susanto', 'IDB1 Ida Ayu'})
        self.assertIn('No bank account on record', left['IDB1 Citra Dewi'])
        self.assertIn('Take-home is zero or below', left['IDB1 Hadi Susanto'])
        self.assertIn('Bank code is missing', left['IDB1 Ida Ayu'])
        home = self.slip_of(self.an)._pb_slip_currency()
        if home.name != 'IDR':
            self.assertIn('Paid in %s; this bank file pays in IDR only' % home.name,
                          left['IDB1 An Nguyen'])
        # the general list prepared with the layout says who and why
        record = self.File.with_user(self.mgr).with_context(self._ctx(self.mgr)).prepare(
            self.payrun, layout=self.id_layout, payment_date=date(2026, 6, 30))
        text = base64.b64decode(record.csv_attachment_id.datas).decode('utf-8-sig')
        line = [r for r in csv.reader(io.StringIO(text)) if r and r[1] == 'IDB1 Citra Dewi'][0]
        self.assertIn('Not in the Indonesia — bank transfer list (general) file: No bank account on record', line[10])
        self.assertEqual(record.layout_excluded_count, 4)
        self.assertEqual(record.layout_row_count, 6)
        # whole amounts only: an amount with cents is left out, never rounded
        layout = self.own_copy(self.id_layout)
        layout.column_ids.filtered(lambda c: c.source == 'net_amount').number_format = 'int'
        idr = self.env.ref('base.IDR')
        out = self.List._pb_layout_render(layout, self.crafted('014', idr), {})
        self.assertEqual(out['count'], 1, '1000.50 and 3001.50 left out, 2001.00 in')
        self.assertIn(b',2001,', out['payload'])
        self.assertIn('The amount has cents, and this bank file takes whole amounts only',
                      out['excluded'][0]['reasons'])
        # plain letters only: an accent leaves the person out, never folded
        layout = self.own_copy(self.id_layout, ascii_only=True)
        rows = self.crafted('014', idr, n=2)
        rows[0]['holder'] = 'Nguyễn Văn Á'
        out = self.List._pb_layout_render(layout, rows, {})
        self.assertEqual(out['count'], 1)
        self.assertIn('The account holder name has letters this bank does not take (accents or other alphabets)',
                      out['excluded'][0]['reasons'])
        self.assertNotIn(b'Nguyen', out['payload'])
        # an account number in a form the bank does not take
        layout = self.own_copy(self.id_layout, account_pattern='^[0-9]{10}$')
        rows = self.crafted('014', idr, n=2)
        rows[1]['account'] = '12345'
        out = self.List._pb_layout_render(layout, rows, {})
        self.assertIn('The account number is not in the form this bank needs',
                      out['excluded'][0]['reasons'])

    # ------------------------------------------------------------ test 5
    def test_s2c_5_approval_hash_download_trail(self):
        record = self.File.with_user(self.mgr).with_context(self._ctx(self.mgr)).prepare(
            self.payrun, layout=self.id_layout.bank_format, payment_date='2026-06-30')
        self.Engine.with_user(self.mgr).with_context(self._ctx(self.mgr)).submit(record)
        record.invalidate_recordset()
        self.assertEqual(record.state, 'pending', 'the bank file gate asks a second person')
        List = self.as_mgr()
        with self.assertRaises(UserError):
            List._pb_download(self.payrun.id, 'bank')
        self._approve_all(record)
        record.invalidate_recordset()
        self.assertEqual(record.state, 'approved')
        self.assertEqual(record.approved_hash, record._live_hash())
        name, mime, payload = List._pb_download(self.payrun.id, 'bank')
        self.assertEqual(payload, record.layout_attachment_id.raw)
        self.assertTrue(name.endswith('.csv'))
        self.assertNotIn('odoo', name.lower())
        self.assertIn(b'0012345678', payload)
        # the Excel and CSV of the list are approved with it
        self.assertTrue(List._pb_download(self.payrun.id, 'csv')[2])
        Entry = self.env['biz.audit.entry'].sudo()
        entries = Entry.search([('model_name', '=', 'hr.payslip.run'),
                                ('res_id', '=', self.payrun.id),
                                ('field_name', '=', 'pb_payment_list')])
        text = ' '.join((e.field_label or '') + ' ' + (e.new_value or '') for e in entries)
        self.assertIn('Bank file (any bank) downloaded', text)
        self.assertIn('6 rows', text)
        self.assertFalse(re.search(r'\d{6,}', text), 'no account number in the trail')
        # the bank file's bytes changed after approval: refused
        record.layout_attachment_id.sudo().raw = payload + b'X'
        self.env.invalidate_all()
        with self.assertRaises(UserError):
            List._pb_download(self.payrun.id, 'bank')
        # the approver sees the layout and who is left out, no account number
        detail = record.sudo()._approval_detail(record.approval_request_id)
        dumped = json.dumps(detail)
        self.assertIn('Indonesia', dumped)
        self.assertIn('IDB1 Citra Dewi', dumped)
        self.assertNotIn('0012345678', dumped)

    def test_s2c_5b_no_approval_needed_route(self):
        self.env['biz.approval.seed'].sudo().set_no_approval_needed(self.home, 'bankfile')
        result = self.env['pb.pay.delivery'].with_user(self.mgr).with_context(
            self._ctx(self.mgr)).prepare_payment_list(self.payrun.id, self.id_layout.bank_format,
                                                      '2026-06-30', '')
        self.assertEqual(result['state'], 'approved', 'approved the moment it is prepared, as the bank file')
        _name, _mime, payload = self.as_mgr()._pb_download(self.payrun.id, 'bank')
        self.assertTrue(payload.startswith(b'No,Bank code'))

    def test_s2c_5c_without_a_layout_nothing_changes(self):
        record = self.prepared_list()
        self.assertFalse(record.layout_attachment_id)
        self.assertEqual(record.file_hash, record._pb_hash(
            record.xlsx_attachment_id.raw, record.csv_attachment_id.raw))
        self._approve_all(record)
        with self.assertRaises(UserError):
            self.env['pb.pay.delivery'].with_user(self.mgr).with_context(
                self._ctx(self.mgr)).payment_list_check(self.payrun.id, 'bank')

    # ------------------------------------------------------------ test 6
    def test_s2c_6_a_new_layout_key_end_to_end(self):
        # a company's copy of a Vietnamese layout: listed, accepted, same bytes
        vcb = self.env.ref('pb_pay_delivery.layout_vietcombank')
        copy = self.own_copy(vcb)
        self.assertNotEqual(copy.bank_format, 'vietcombank')
        data = self.env['pb.pay.delivery'].with_user(self.mgr).with_context(
            self._ctx(self.mgr)).get_delivery_data(self.payrun.id)
        keys = [b['key'] for b in data['banks']]
        self.assertIn(copy.bank_format, keys)
        self.assertNotIn('id_general', keys, 'payment-list layouts are not Vietnamese bank files')
        self.assertIn('id_general', [l['key'] for l in data['payment_list']['layouts']])
        Wizard = self.env['vietnam.bank.export.wizard']
        original = Wizard.create({'payslip_run_id': self.payrun.id, 'bank_format': 'vietcombank',
                                  'pb_unpaid_only': True})._generate()
        record = self.env['pb.bank.file'].with_user(self.mgr).with_context(
            self._ctx(self.mgr)).prepare(self.payrun, copy.bank_format)
        self.assertEqual(record.attachment_id.raw, base64.b64decode(original['file_b64']))
        self.assertEqual(record.layout_id, copy)
        self.assertIn(copy.name, record.name)
        # a payment-list layout is refused by the Vietnamese file, plainly
        with self.assertRaises(UserError):
            self.env['pb.bank.file'].with_user(self.mgr).with_context(
                self._ctx(self.mgr)).prepare(self.payrun, 'id_general')
        # a copy of a payment-list layout prepares the list end to end
        own = self.own_copy(self.id_layout)
        record = self.File.with_user(self.mgr).with_context(self._ctx(self.mgr)).prepare(
            self.payrun, layout=own.bank_format)
        self.assertEqual(record.layout_id, own)
        self.assertEqual(record.layout_row_count, 6)

    # ------------------------------------------------------------ test 7
    def test_s2c_7_upgrade_keeps_edits_and_rows(self):
        from odoo.modules.module import get_module_path
        from odoo.tools import convert_file
        vcb = self.env.ref('pb_pay_delivery.layout_vietcombank')
        copy = self.own_copy(vcb)
        copy.column_ids[:1].header = 'OUR HEADER'
        vcb.column_ids[:1].header = 'EDITED ON THIS DATABASE'
        vcb.note = 'corrected by the customer'
        columns_before = self.env['pb.bank.file.column'].search_count([])
        # a database installed before 19.0.1.9.0: rows not flagged, no country
        self.env.flush_all()
        self.env.cr.execute("""UPDATE ir_model_data SET noupdate = false
                                WHERE module = 'pb_pay_delivery'
                                  AND model IN ('pb.bank.file.layout', 'pb.bank.file.column')""")
        self.env.cr.execute("UPDATE pb_bank_file_layout SET country_id = NULL WHERE id = %s", (vcb.id,))
        self.env.invalidate_all()
        path = os.path.join(get_module_path('pb_pay_delivery'), 'migrations', '19.0.1.9.0',
                            'post-s2c_layouts_noupdate.py')
        spec = importlib.util.spec_from_file_location('s2c_migration', path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.migrate(self.env.cr, '19.0.1.8.1')
        self.env.invalidate_all()
        self.env.cr.execute("""SELECT count(*) FROM ir_model_data
                                WHERE module = 'pb_pay_delivery' AND noupdate IS NOT TRUE
                                  AND model IN ('pb.bank.file.layout', 'pb.bank.file.column')""")
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        self.assertEqual(vcb.country_id.code, 'VN')
        rule = self.env.ref('pb_pay_delivery.audit_rule_bank_file_layout')
        self.assertIn('header_template', rule.field_names)
        self.assertIn('max_length', self.env.ref('pb_pay_delivery.audit_rule_bank_file_column').field_names)
        # the upgrade's data load: nothing on the database is rewritten
        convert_file(self.env, 'pb_pay_delivery', 'data/bank_file_layouts.xml', {}, mode='update')
        convert_file(self.env, 'pb_pay_delivery', 'data/bank_layouts_world.xml', {}, mode='update')
        self.env.invalidate_all()
        self.assertEqual(vcb.column_ids[:1].header, 'EDITED ON THIS DATABASE')
        self.assertEqual(vcb.note, 'corrected by the customer')
        self.assertEqual(copy.column_ids[:1].header, 'OUR HEADER')
        self.assertTrue(copy.exists())
        self.assertEqual(self.env['pb.bank.file.column'].search_count([]), columns_before)
        # a second run changes nothing
        migration.migrate(self.env.cr, '19.0.1.9.0')
        self.env.invalidate_all()
        self.assertEqual(rule.field_names.count('header_template'), 1)

    # ------------------------------------------------------------ test 8
    def test_s2c_8_bank_directory_by_country(self):
        Reg = self.env['pb.bank.registry']
        self.assertFalse(Reg.match('BCA'), 'the Vietnamese match does not know BCA (ruling BG3)')
        self.assertFalse(Reg.match('Bank Central Asia'))
        self.assertEqual(Reg.match('Vietcombank'), self.env.ref('pb_bank_ocr.bank_vcb'))
        self.assertEqual(len(Reg._all_terms()), Reg.search_count(
            ['|', ('country_id', '=', False), ('country_id.code', '=', 'VN')]))
        bca = Reg.match('PT Bank Central Asia Tbk', country='ID')
        self.assertEqual((bca.short_name, bca.clearing_code), ('BCA', '014'))
        self.assertEqual(Reg.match('IDB1 Mandiri', country='ID').clearing_code, '008')
        self.assertEqual(Reg.match('HDFC Bank Ltd', country='IN').clearing_code, 'HDFC')
        self.assertEqual(Reg.match('OCBC', country=self.env.ref('base.sg')).clearing_code, '7339')
        self.assertFalse(Reg.match('Vietcombank', country='ID'))
        # the order: the account's own code, the bank record's, the directory
        account = self.budi.sudo().bank_account_ids[:1]
        self.assertEqual(self.List._pb_bank_identity(account, self.env.ref('base.id'))[1], '014')
        self.bca.pb_clearing_code = '999'
        self.assertEqual(self.List._pb_bank_identity(account, self.env.ref('base.id'))[1], '999')
        account.clearing_number = '777'
        self.assertEqual(self.List._pb_bank_identity(account, self.env.ref('base.id'))[1], '777')

    # ------------------------------------------------------------ test 9
    def test_s2c_9_access(self):
        Studio = self.env['pb.bank.layout.studio']
        board = Studio.with_user(self.mgr).with_context(self._ctx(self.mgr)).get_board()
        self.assertTrue(board['layouts'])
        self.env.flush_all()
        self.env.invalidate_all()
        for user in (self.officer, self.portal):
            for call in (lambda S: S.get_board(),
                         lambda S: S.get_layout(self.id_layout.id),
                         lambda S: S.copy_layout(self.id_layout.id),
                         lambda S: S.preview(self.id_layout.id)):
                with self.assertRaises(AccessError):
                    call(Studio.with_user(user))
            with self.assertRaises(AccessError):
                self.env['pb.pay.delivery'].with_user(user).payment_list_layout_preview(
                    self.payrun.id, 'id_general')
            with self.assertRaises(AccessError):
                self.env['pb.pay.delivery'].with_user(user).prepare_payment_list(
                    self.payrun.id, 'id_general')
        # a shipped layout cannot be changed on the screen, a copy can
        S = Studio.with_user(self.mgr).with_context(self._ctx(self.mgr))
        with self.assertRaises(UserError):
            S.save_layout(self.id_layout.id, {'name': 'X'})
        copy = S.copy_layout(self.id_layout.id)
        saved = S.save_layout(copy['id'], {'name': 'Our BCA', 'column_rows': copy['column_rows'][:3]})
        self.assertEqual(saved['name'], 'Our BCA')
        self.assertEqual(len(saved['column_rows']), 3)
        with self.assertRaises(ValidationError):
            S.save_layout(copy['id'], {'header_template': 'H,{salary}'})
        # another company cannot see, use or change the copy
        g_mgr = self.env.ref('om_hr_payroll.group_hr_payroll_manager')
        g_hr = self.env.ref('om_hr_payroll.group_hr_payroll_user')
        other = self.env['res.company'].create({'name': 'S2C Other'})
        stranger = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'S2C Other Manager', 'login': 's2c_other_mgr',
            'company_id': other.id, 'company_ids': [(6, 0, other.ids)],
            'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})
        self.env.flush_all()
        self.env.invalidate_all()
        theirs = Studio.with_user(stranger).with_context(allowed_company_ids=other.ids)
        self.assertNotIn(copy['id'], [l['id'] for l in theirs.get_board()['layouts']])
        with self.assertRaises(AccessError):
            theirs.get_layout(copy['id'])
        refused = False
        try:
            with self.env.cr.savepoint():
                self.List.with_user(stranger).with_context(
                    allowed_company_ids=other.ids)._pb_layout(saved['key'])
        except (AccessError, UserError):
            refused = True
        self.assertTrue(refused, "another company's copy is not offered to them")
        # the preview: three made-up people, nothing real
        preview = S.preview(self.id_layout.id)
        self.assertIn('DEMO Ayu Lestari', preview['text'])
        self.assertEqual(preview['count'], 3)
        self.assertNotIn('IDB1', preview['text'])

    # ------------------------------------------------------------ test 10
    def test_s2c_10_formula_signs_and_leading_zeros(self):
        result = self.build(self.id_layout)
        ida = [x for x in result['excluded'] if x['employee'] == 'IDB1 Ida Ayu'][0]['reasons']
        self.assertIn('The bank name starts with a sign a spreadsheet would run as a formula', ida)
        self.assertIn('The account holder name starts with a sign a spreadsheet would run as a formula', ida)
        self.assertNotIn(b'=SUM', result['payload'])
        self.assertNotIn(b'+IDB1', result['payload'])
        # the run's name in the reference never starts a formula either
        self.payrun.name = '=HYPERLINK("x")'
        result = self.build(self.id_layout)
        self.assertFalse(any(r[7].startswith(('=', '+', '-', '@')) for r in self.csv_of(result)[1:]))
        self.assertIn(b',0012345678,', result['payload'])
        rows = self.crafted('014', self.env.ref('base.IDR'), n=1,
                            account='000123456789012345678')
        out = self.List._pb_layout_render(self.id_layout, rows, {})
        self.assertIn(b',000123456789012345678,', out['payload'])

    # ------------------------------------------------------------ test 11
    def test_s2c_11_no_vendor_name_in_files_or_names(self):
        import zipfile
        for layout in (self.id_layout, self.own_copy(self.id_layout, file_type='xlsx'),
                       self.own_copy(self.id_layout, file_type='txt')):
            result = self.build(layout)
            self.assertNotIn('odoo', result['filename'].lower())
            if layout.file_type == 'xlsx':
                with zipfile.ZipFile(io.BytesIO(result['payload'])) as zf:
                    for member in zf.namelist():
                        self.assertNotIn(b'odoo', zf.read(member).lower(), member)
            else:
                self.assertNotIn(b'odoo', result['payload'].lower())
        for layout in self.Layout.search([('company_id', '=', False)]):
            for text in (layout.name, layout.note or ''):
                self.assertNotIn('odoo', text.lower())
        # every shipped payment-list layout says where it comes from
        for layout in self.Layout.search([('target', '=', 'payment_list'),
                                          ('company_id', '=', False)]):
            self.assertIn('Check with your bank before the first upload', layout.note)
            self.assertTrue(layout.inferred, 'no bank-confirmed layout ships yet')

    def test_s2c_golden_general_list_with_layout_file_made(self):
        """Test 2 again on the payment-list record: preparing WITH a layout
        does not touch the general list stamped without one."""
        before = golden.stable_digest(self.List._pb_build(self.payrun, 'csv')[2], 'csv')
        self.File.with_user(self.mgr).with_context(self._ctx(self.mgr)).prepare(
            self.payrun, layout=self.id_layout)
        self.assertEqual(golden.stable_digest(self.List._pb_build(self.payrun, 'csv')[2], 'csv'),
                         before)
        self.assertEqual(before, golden.GOLDEN['csv'])


@tagged('post_install', '-at_install', 'wdgap_s2c')
class TestS2cTranslations(TransactionCase):
    """Test 11: every new string has a Vietnamese and an Indonesian entry that
    loads, and no vendor name in any of them."""

    FILES_PY = (('models', 'payment_list_layout.py'), ('models', 'bank_layout_studio.py'),
                ('models', 'bank_file_layout.py'))
    FILES_JS = (('static', 'src', 'js', 'bank_layouts.js'),
                ('static', 'src', 'js', 'bank_layouts_doors.js'))

    def _path(self, *parts):
        from odoo.modules.module import get_module_path
        return os.path.join(get_module_path('pb_pay_delivery'), *parts)

    def _strings(self):
        found = set()
        for parts in self.FILES_PY:
            source = open(self._path(*parts), encoding='utf-8').read()
            found |= set(re.findall(r'_\(\s*"((?:[^"\\]|\\.)*)"', source))
        for parts in self.FILES_JS:
            source = open(self._path(*parts), encoding='utf-8').read()
            found |= set(re.findall(r'_t\(\s*"((?:[^"\\]|\\.)*)"', source))
        found = {s.replace('\\"', '"') for s in found}
        found |= {"Bank file (any bank) downloaded", "Bank layout", "In the bank file",
                  "Not in the bank file", "%(n)s payments · %(total)s %(currency)s",
                  "1 person is left out of this bank file", "%s file",
                  "Not confirmed by the bank. Check with your bank before the first upload."}
        return found

    def test_s2c_11_vi_and_id_entries_load(self):
        from odoo.tools.translate import PoFileReader
        wanted = self._strings()
        self.assertGreater(len(wanted), 60)
        for lang in ('vi_VN', 'id_ID'):
            path = self._path('i18n', '%s.po' % lang)
            with open(path, 'rb') as handle:
                rows = list(PoFileReader(handle))
            loaded = {}
            for row in rows:
                if row['value']:
                    loaded[row['src']] = row['value']
            missing = sorted(s for s in wanted if s not in loaded)
            self.assertFalse(missing, '%s: no entry for %s' % (lang, missing))
            for src, value in loaded.items():
                self.assertNotIn('odoo', value.lower(), '%s: %s' % (lang, src))

    def test_s2c_11_no_vendor_name_in_new_user_text(self):
        for parts in self.FILES_PY + self.FILES_JS + (
                ('static', 'src', 'xml', 'bank_layouts.xml'),
                ('data', 'bank_layouts_world.xml')):
            text = open(self._path(*parts), encoding='utf-8').read()
            if parts[-1].endswith('.xml'):
                text = re.sub(r'<!--.*?-->', ' ', text, flags=re.S)
                text = re.sub(r'<[^>]*>', ' ', text)
                self.assertNotIn('odoo', text.lower(), parts)
            else:
                for found in re.findall(r'_t?\(\s*"((?:[^"\\]|\\.)*)"', text):
                    self.assertNotIn('odoo', found.lower(), found)


@tagged('post_install', '-at_install', 'wdgap_s2c')
class TestS2cUrl(_S2cFixture, HttpCase):
    """Test 5/9 by the direct address."""

    def _login(self, user):
        password = secrets.token_urlsafe(18)    # made here, kept nowhere
        user.sudo().password = password
        self.authenticate(user.login, password)

    def test_s2c_url_bank_file(self):
        record = self.File.with_user(self.mgr).with_context(self._ctx(self.mgr)).prepare(
            self.payrun, layout=self.id_layout)
        self.Engine.with_user(self.mgr).with_context(self._ctx(self.mgr)).submit(record)
        url = '/pb_pay_delivery/payment_list?run_id=%s&fmt=bank' % self.payrun.id
        self._login(self.officer)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b'0012345678', response.content)
        self._login(self.mgr)
        response = self.url_open(url)
        self.assertNotEqual(response.status_code, 200, 'not approved yet')
        self._approve_all(record)
        self._login(self.mgr)
        response = self.url_open(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers.get('Content-Disposition', ''))
        self.assertIn(b'0012345678', response.content)
        self.assertNotIn('odoo', response.headers.get('Content-Disposition', '').lower())
