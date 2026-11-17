# -*- coding: utf-8 -*-
"""WDGAP IDB1 test 7 — the Vietnamese bank file is unchanged, byte for byte.

The golden stamps below were taken by running THIS file on the code of
`origin/19.1` before IDB1 (the pristine tree, `IDB1_PRINT_GOLDEN=1` logs them).
The same run, generated with the IDB1 code, must give the same bytes — and
downloading the payment list in between must not move a single byte either.

Fixture: one approved run, June 2026, Vietnamese and Indonesian people. Only
the people with Vietnamese bank details are in the Vietnamese file; the
Indonesian people are left out of it ("unknown bank" / "invalid account"),
exactly as before IDB1.
"""

import base64
import hashlib
import io
import logging
import os
import zipfile
from datetime import date

from odoo.tests import TransactionCase, tagged

_logger = logging.getLogger(__name__)

#: sha256 of each layout's bytes for the fixture run, on the pre-IDB1 code.
#: (xlsx: of the workbook's sheet and strings, without its creation time.)
#: Recorded 2026-11-18 on origin/19.1 @ 65fc59cd7 (local copy wdgap_idb1_t).
GOLDEN = {
    'vietcombank': '22c102bd2d60239ffe4eddfa1583a9fa77735a1a6767cdf675dc07e1df4c755c',
    'generic': '4facb739062aac0828e52784563ce0cea9c2cdeb4cd72b4a9ec06250d9de7429',
    'vietinbank': 'a4114599ceb2807f1d63c86d9dbd659711c83f712f2ab6f6871264582c0c3f68',
    'mb_bank': '9b33b2b738454395996774e0e7874c6cf3ddcbf85f49494ed8220ebae5a82186',
}


def _stable_digest(data, file_type):
    if file_type != 'xlsx':
        return hashlib.sha256(data).hexdigest()
    digest = hashlib.sha256()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in sorted(zf.namelist()):
            if name.startswith('docProps/'):
                continue      # creation time lives here
            digest.update(name.encode())
            digest.update(zf.read(name))
    return digest.hexdigest()


@tagged('post_install', '-at_install', 'wdgap_idb1')
class TestIdb1VnGolden(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'Std'})
        cls.net_rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.net_cat = cls.env.ref('om_hr_payroll.NET')
        cls.payrun = cls.env['hr.payslip.run'].create({
            'name': 'IDB1 Golden June',
            'date_start': date(2026, 6, 1), 'date_end': date(2026, 6, 30)})
        Emp = cls.env['hr.employee'].sudo()
        people = [
            ('IDB1G An Nguyen', 'Vietcombank', '0071000123456', 5000000),
            ('IDB1G Bao Tran', 'BIDV', '12010000456789', 4200000.5),
            ('IDB1G Chi Le', 'Techcombank', '19033344455566', 3100000),
            # Indonesian people: no Vietnamese bank details at all, or a bank
            # the Vietnamese file does not know
            ('IDB1G Dian Putri', False, False, 7500000),
            ('IDB1G Eko Saputra', 'BCA', '0012345678', 6400000),
        ]
        cls.slips = cls.env['hr.payslip']
        for name, bank, account, net in people:
            emp = Emp.create({
                'name': name, 'company_id': cls.company.id,
                'vietnam_bank_name': bank or False,
                'vietnam_bank_branch': 'Hoan Kiem' if bank else False,
                'vietnam_bank_account_number': account or False,
                'vietnam_bank_account_name': name if bank else False})
            contract = cls.env['hr.contract'].sudo().create({
                'name': 'IDB1G-%s' % emp.id, 'employee_id': emp.id,
                'wage': 1000.0, 'resource_calendar_id': cls.calendar.id,
                'type_id': cls.ctype.id, 'company_id': cls.company.id})
            slip = cls.env['hr.payslip'].sudo().create({
                'employee_id': emp.id, 'contract_id': contract.id,
                'payslip_run_id': cls.payrun.id, 'company_id': cls.company.id,
                'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
            cls.env['hr.payslip.line'].sudo().create({
                'slip_id': slip.id, 'salary_rule_id': cls.net_rule.id,
                'employee_id': emp.id, 'contract_id': contract.id,
                'category_id': cls.net_cat.id, 'name': 'Net', 'code': 'NET',
                'amount': net, 'quantity': 1.0, 'rate': 100.0})
            slip.write({'state': 'done'})
            cls.slips |= slip
        if hasattr(cls.payrun, '_pb_chain_ctx'):
            cls.payrun._pb_chain_ctx().write({'state': 'done'})
        else:
            cls.payrun.sudo().write({'state': 'done'})

    def _generate(self, bank_format):
        wizard = self.env['vietnam.bank.export.wizard'].create({
            'payslip_run_id': self.payrun.id, 'bank_format': bank_format,
            'pb_unpaid_only': True})
        result = wizard._generate()
        data = base64.b64decode(result['file_b64'])
        return _stable_digest(data, result['file_type']), result

    def test_idb1_7_vn_file_is_byte_identical(self):
        digests = {}
        for fmt in GOLDEN:
            digests[fmt], result = self._generate(fmt)
            # the Indonesian people are left out of the Vietnamese file, as before
            self.assertEqual(result['valid'], 3, fmt)
            self.assertEqual(len(result['excluded']), 2, fmt)
        if os.environ.get('IDB1_PRINT_GOLDEN'):
            _logger.warning('IDB1 GOLDEN %r', digests)
        for fmt, expected in GOLDEN.items():
            self.assertEqual(digests[fmt], expected,
                             '%s file changed under IDB1' % fmt)

        # downloading the payment list in between moves no byte of it
        if 'pb.payment.list' in self.env:
            List = self.env['pb.payment.list']
            for kind in ('xlsx', 'csv'):
                List.pb_build(self.payrun, kind)
            for fmt in GOLDEN:
                self.assertEqual(self._generate(fmt)[0], digests[fmt],
                                 '%s file moved after the payment list' % fmt)
