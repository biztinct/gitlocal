# -*- coding: utf-8 -*-
"""NEWHIRE P7 — a bank account in its own country's format (the one
definition, `pb.bank.format`). Numbers match the P7 handover (B1, B2, B4, B5,
B6; B3 — the same definition on every screen — is in pb_new_hire's
test_p7.py, where the studio is)."""
import base64
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

_PDF = b'%PDF-1.4 a bank letter for a P7 test'


@tagged('post_install', '-at_install', 'newhire')
class TestP7BankFormats(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env['payroll.ai.config'].search([]).write({'is_active': False})
        cls.Format = cls.env['pb.bank.format']
        cls.Bank = cls.env['pb.bank.change.request']
        Emp = cls.env['hr.employee']
        cls.india = Emp.create({'name': 'DEMO P7 Priya Sharma', 'company_id': cls.company.id,
                                'payroll_country': 'IN'})
        cls.vietnam = Emp.create({'name': 'DEMO P7 Nguyen Van P', 'company_id': cls.company.id,
                                  'payroll_country': 'VN'})
        cls.nowhere = Emp.create({'name': 'DEMO P7 No Country', 'company_id': cls.company.id})

    def _request(self, emp, **vals):
        att = self.env['ir.attachment'].create({
            'name': 'l.pdf', 'datas': base64.b64encode(_PDF), 'mimetype': 'application/pdf'})
        return self.Bank.create(dict({'employee_id': emp.id, 'attachment_id': att.id,
                                      'x_account_name': emp.name}, **vals))

    # ================================================================ B1
    def test_b1_each_country_good_and_bad(self):
        cases = [
            # (format, good values, bad values, the box the bad one names)
            ('IN', {'account_number': '123456789012', 'branch_code': 'hdfc0001234'},
             {'account_number': '123456789012', 'branch_code': 'HDFC1001234'}, 'branch_code'),
            ('IN', {'account_number': '1234 5678 9012', 'branch_code': 'SBIN0000300'},
             {'account_number': '12345678', 'branch_code': 'SBIN0000300'}, 'account_number'),
            ('SG', {'account_number': '0123456789', 'bank_code': '7171', 'branch_code': '081'},
             {'account_number': '0123456789', 'bank_code': '71', 'branch_code': ''}, 'bank_code'),
            ('SG', {'account_number': '0123456789', 'bank_name': 'DBS'},
             {'account_number': '012345678901234', 'bank_name': 'DBS'}, 'account_number'),
            ('MY', {'account_number': '514012345678', 'swift': 'mbbemykl'},
             {'account_number': '514012345678', 'swift': 'MBB'}, 'swift'),
            ('ID', {'account_number': '1234567890', 'bank_name': 'BCA'},
             {'account_number': '1234567', 'bank_name': 'BCA'}, 'account_number'),
            ('VN', {'account_number': '0011001234567'},
             {'account_number': '12345'}, 'account_number'),
            ('TH', {'account_number': '1234567890', 'branch_code': '0001'},
             {'account_number': '1234567890', 'branch_code': '01'}, 'branch_code'),
            ('KH', {'account_number': '000123456'},
             {'account_number': '12345'}, 'account_number'),
            ('AU', {'account_number': '12345678', 'branch_code': '062000'},
             {'account_number': '12345678', 'branch_code': ''}, 'branch_code'),
            ('AU', {'account_number': '12345678', 'branch_code': '062-000'},
             {'account_number': '1234567890', 'branch_code': '062-000'}, 'account_number'),
            ('other', {'account_number': 'DE89 3704 0044 0532 0130 00', 'swift': 'COBADEFFXXX'},
             {'account_number': 'DE89-3704!', 'swift': ''}, 'account_number'),
        ]
        for fmt, good, bad, box in cases:
            with self.subTest(fmt=fmt, box=box):
                clean, problems = self.Format.check(fmt, good)
                self.assertFalse(problems, (fmt, good, problems))
                _clean, problems = self.Format.check(fmt, bad)
                self.assertEqual(next(iter(problems)), box, (fmt, bad, problems))
                self.assertTrue(problems[box].endswith('.'), 'a plain sentence')
        # stored shapes
        clean, _p = self.Format.check('IN', {'account_number': '1234-5678 9012', 'branch_code': ' hdfc 0001234 '})
        self.assertEqual((clean['branch_code'], clean['account_number']), ('HDFC0001234', '123456789012'))
        clean, _p = self.Format.check('AU', {'account_number': '12345678', 'branch_code': '062 000'})
        self.assertEqual(clean['branch_code'], '062-000')
        clean, _p = self.Format.check('other', {'account_number': 'de89 3704 0044 0532 0130 00'})
        self.assertEqual(clean['account_number'], 'DE89370400440532013000', 'an IBAN keeps its letters')
        # the directory fills a Singapore / Indonesian bank code; India finds the bank from the IFSC
        clean, _p = self.Format.check('SG', {'account_number': '0123456789', 'bank_name': 'DBS'})
        self.assertEqual(clean['bank_code'], '7171')
        self.assertEqual(self.Format.clearing('SG', dict(clean, branch_code='081')), '7171081')
        self.assertEqual(self.Format.bank_from_code('IN', 'HDFC0001234')['value'], 'HDFC')
        # words: each country's own label, a hint on every box
        self.assertEqual([c['label'] for c in self.Format.spec('IN')['codes']], ['IFSC code'])
        self.assertEqual([c['label'] for c in self.Format.spec('AU')['codes']], ['BSB'])
        self.assertEqual([c['label'] for c in self.Format.spec('SG')['codes']], ['Bank code', 'Branch code'])
        for code in ('VN', 'ID', 'IN', 'SG', 'MY', 'TH', 'KH', 'AU', 'other'):
            spec = self.Format.spec(code)
            self.assertTrue(spec['account']['hint'])
            for c in spec['codes']:
                self.assertTrue(c['hint'] and c['missing'] and c['bad'], (code, c))
        # the old rule: no country
        self.assertEqual(self.Format.spec('')['code'], '')
        self.assertEqual((self.Format.spec('')['account']['min'], self.Format.spec('')['account']['max']), (6, 19))

    # ================================================================ B2
    def test_b2_codes_carried_from_request_to_account(self):
        req = self._request(self.india, x_bank_name='HDFC', x_account_number='123456789012',
                            x_branch_code='hdfc 0001234')
        self.assertEqual(req.pb_bank_format, 'IN', 'follows the Country of Work')
        self.assertEqual(req.x_branch_code, 'HDFC0001234', 'stored in its shape')
        req.action_validate()
        self.assertTrue(req.v_format_ok, req.v_format_msg)
        req._apply_to_master()
        account = self.india.sudo().bank_account_ids[:1]
        self.assertEqual(account.acc_number, '123456789012')
        self.assertEqual(account.clearing_number, 'HDFC0001234', 'the IFSC is on the account')
        # Singapore: bank code + branch code; Australia: the BSB
        sg = self.env['hr.employee'].create({'name': 'DEMO P7 Tan', 'company_id': self.company.id,
                                             'payroll_country': 'SG'})
        req = self._request(sg, x_bank_name='DBS', x_account_number='0123456789', x_bank_code='7171',
                            x_branch_code='081')
        req._apply_to_master()
        self.assertEqual(sg.sudo().bank_account_ids[:1].clearing_number, '7171081')
        au = self.env['hr.employee'].create({'name': 'DEMO P7 Jack', 'company_id': self.company.id})
        req = self._request(au, pb_bank_format='AU', x_bank_name='Commonwealth Bank',
                            x_account_number='12345678', x_branch_code='062000')
        req._apply_to_master()
        self.assertEqual(au.sudo().bank_account_ids[:1].clearing_number, '062-000')

    def test_b2b_send_needs_the_country_code(self):
        req = self._request(self.india, x_bank_name='HDFC', x_account_number='123456789012')
        with self.assertRaisesRegex(UserError, 'IFSC'):
            req.action_submit()
        req.write({'x_branch_code': 'HDFC0001234'})
        # past the format gate (the route may still hold it; never the format)
        try:
            req.action_submit()
        except UserError as exc:
            self.assertNotIn('IFSC', str(exc))
        # the approval card names the country and the code
        detail = req._approval_detail(None)
        heads = [r['head'] for r in detail['rows']]
        self.assertIn('Bank account in', heads)
        self.assertIn('IFSC code', heads)

    # ================================================================ B4
    def test_b4_older_and_vietnamese_changes_unchanged(self):
        # no Country of Work: no format, the old 6-19 rule and its sentence
        req = self._request(self.nowhere, x_bank_name='Vietcombank', x_account_number='12345')
        self.assertFalse(req.pb_bank_format)
        req.action_validate()
        self.assertFalse(req.v_format_ok)
        self.assertIn('Account number must be 6-19 digits.', req.v_format_msg)
        self.assertEqual(req._pb_format_problem(), 'The account number must be 6-19 digits before approval.')
        # Vietnam: the old check exactly (same sentence), nothing new asked
        req = self._request(self.vietnam, x_bank_name='Vietcombank', x_account_number='0011001234567')
        self.assertEqual(req.pb_bank_format, 'VN')
        req.action_validate()
        self.assertEqual(req.v_format_msg, 'All format checks passed.')
        self.assertEqual(req._pb_format_problem(), '')
        # an import keeps the old rule (no country), whoever it is about
        imp = self.Bank.create({'employee_id': self.india.id, 'pb_origin': 'import',
                                'x_account_number': '12345678901'})
        self.assertFalse(imp.pb_bank_format)
        # the approval stamp of an older change is what it always was
        self.assertEqual(set(imp._chain_revision_values()),
                         {'employee', 'bank', 'branch', 'holder', 'number', 'iban', 'swift'})
        # people already on record stay payroll-ready (nothing reads the new fields)
        on_record = self.env['hr.employee'].create({
            'name': 'DEMO P7 On Record', 'company_id': self.company.id, 'payroll_country': 'IN',
            'vietnam_bank_name': 'HDFC', 'vietnam_bank_account_number': '123456789012'})
        self.assertTrue(on_record.pb_bank_on_record, 'an Indian on record without an IFSC is still on record')

    # ================================================================ B5
    def test_b5_bank_file_reads_the_ifsc(self):
        if 'pb.payment.list' not in self.env:
            self.skipTest('the payment list is not installed')
        req = self._request(self.india, x_bank_name='HDFC', x_account_number='123456789012',
                            x_branch_code='HDFC0001234')
        req._apply_to_master()
        account = self.india.sudo().bank_account_ids[:1]
        _bic, code = self.env['pb.payment.list']._pb_bank_identity(account, self.env.ref('base.in'))
        self.assertEqual(code, 'HDFC0001234')

    # ================================================================ B6
    def test_b6_the_reader_fills_the_codes(self):
        names = [f['name'] for f in self.Bank._ocr_schema()['fields']]
        self.assertIn('x_branch_code', names)
        self.assertIn('x_bank_code', names)
        req = self._request(self.india)

        def fake(this, schema, attachment_ids, post_processor=None):
            return {'provider': 'DEMO', 'raw_text': '', 'fields': {
                'x_bank_name': {'value': 'HDFC Bank', 'confidence': 0.9},
                'x_account_number': {'value': '123456789012', 'confidence': 0.9},
                'x_branch_code': {'value': 'hdfc0001234', 'confidence': 0.8}}}
        with patch.object(type(self.env['biz.doc.ocr']), '_extract', fake):
            req.action_run_ocr()
        self.assertEqual(req.x_branch_code, 'HDFC0001234')
        self.assertTrue(req.v_format_ok, req.v_format_msg)

    # ================================================================ My Payobook
    def test_p1_my_payobook_same_boxes(self):
        req = self._request(self.india, pb_origin='self_service', x_bank_name='HDFC',
                            x_account_number='123456789012')
        view = req.pb_portal_view()
        self.assertEqual(view['format_code'], 'IN')
        self.assertEqual(view['format'], self.Format.spec('IN'), 'the one definition')
        req.pb_portal_update({'x_branch_code': 'hdfc0001234', 'x_swift': ''})
        self.assertEqual(req.x_branch_code, 'HDFC0001234')
        req.pb_portal_set_format('AU')
        self.assertEqual(req.pb_bank_format, 'AU')
        req.pb_portal_set_format('nonsense')
        self.assertFalse(req.pb_bank_format)
        # cockpit: the boxes follow the country
        req.pb_portal_set_format('IN')
        defs = self.env['pb.bank.ocr']._pb_field_defs(req)
        self.assertIn('IFSC code', [d['label'] for d in defs])
