# -*- coding: utf-8 -*-
"""CLOCK-1 handover §7 cases 13–15 — the "Time-clock punches" upload mode."""
import base64
import io
from datetime import date, datetime

from odoo.tests import tagged

from .common import ClockCase

try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None


def b64(text):
    return base64.b64encode(text.encode('utf-8')).decode()


@tagged('post_install', '-at_install', 'pb_clock')
class TestClockUpload(ClockCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wiz = cls.env['pb.attendance.import.wizard'].with_company(cls.company)
        cls.Flow = cls.env['pb.attendance.flow'].with_company(cls.company)

    # ------------------------------------------------------------ modes
    def test_00_modes_offer_punches(self):
        keys = [m['key'] for m in self.Flow.import_modes()]
        self.assertEqual(keys, ['days', 'punches'])

    # ================================================================== 13
    def test_13_daily_sheet_with_legacy_headers(self):
        if not openpyxl:
            self.skipTest('openpyxl missing')
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['BAÛNG CHAÁM COÂNG'])                 # a title row above
        ws.append([])
        ws.append(['Maõ NV', 'Teân', 'Ngaøy', 'Laàn 1', 'Laàn 2'])
        ws.append(['885', 'CLK', '03/11/2026', '7:11', '16:31'])
        ws.append(['885', 'CLK', '04/11/2026', '7:05', '16:40'])
        ws.append(['227', 'CLK', '26/10/2026', '19:18', None])
        buf = io.BytesIO()
        wb.save(buf)
        data = base64.b64encode(buf.getvalue()).decode()
        parsed = self.Flow.import_parse(data, 'daily.xlsx', 'punches')
        self.assertEqual(parsed['format'], 'mitaco')
        self.assertTrue(parsed['ready'])
        self.assertEqual(parsed['preview']['punches'], 5)
        self.assertEqual(parsed['preview']['people'], 2)
        self.assertEqual(parsed['preview']['unknown_count'], 0)
        res = self.Flow.import_commit(data, 'daily.xlsx', parsed['mapping'], 'punches')
        self.assertEqual(res['created'], 5)
        rows = self.Punch.search([('company_id', '=', self.company.id)])
        self.assertEqual(set(rows.mapped('source')), {'mitaco_export'})
        self.assertEqual(sorted(rows.mapped('direction')), ['in', 'in', 'in', 'out', 'out'])
        self.run_pairing()
        days = (self.device_atts(self.e885) | self.device_atts(self.e227))
        self.assertEqual(len(days), 3)
        self.assertEqual(sorted(a._pb_local_day() for a in days),
                         [date(2026, 10, 26), date(2026, 11, 3), date(2026, 11, 4)])
        # the same file again adds nothing
        again = self.Flow.import_commit(data, 'daily.xlsx', parsed['mapping'], 'punches')
        self.assertEqual(again['created'], 0)
        self.assertEqual(again['duplicates'], 5)

    # ================================================================== 14
    def test_14_machine_log_file(self):
        # number, time, status (0 in / 1 out), verify (1 finger), work code
        text = ('     885\t2026-11-03 07:11:02\t0\t1\t0\t0\n'
                '     885\t2026-11-03 16:31:40\t1\t1\t0\t0\n'
                '     227\t2026-11-03 19:20:00\t0\t1\t0\t0\n'
                '     227\t2026-11-04 07:31:15\t1\t1\t0\t0\n')
        parsed = self.Flow.import_parse(b64(text), 'TEST-0001_attlog.dat', 'punches')
        self.assertEqual(parsed['format'], 'attlog')
        self.assertTrue(parsed['ready'])
        self.assertEqual(parsed['preview']['punches'], 4)
        res = self.Flow.import_commit(b64(text), 'TEST-0001_attlog.dat',
                                      parsed['mapping'], 'punches')
        self.assertEqual(res['created'], 4)
        rows = self.Punch.search([('company_id', '=', self.company.id)])
        self.assertEqual(rows.mapped('device_id'), self.device,
                         "the serial in the file name names the machine")
        self.assertEqual(set(rows.mapped('direction')), {'in', 'out'})
        self.assertEqual(set(rows.mapped('verify_mode')), {'1'})
        # without a serial in the name: the upload pseudo device
        text2 = '     885\t2026-11-05 07:00:00\t1\t0\t1\t0\n'
        self.Flow.import_commit(b64(text2), 'attlog.dat', {}, 'punches')
        p = self.Punch.search([('punch_local', '=', '2026-11-05 07:00:00'),
                               ('company_id', '=', self.company.id)])
        self.assertEqual(p.device_id.kind, 'upload')

    # ================================================================== 15
    def test_15_upload_cap(self):
        lines = ['code,time']
        for i in range(20001):
            lines.append('885,2026-10-%02d %02d:%02d:%02d' % (
                1 + (i // 3600) % 28, (i // 60) % 24, i % 60, i % 60))
        parsed = self.Flow.import_parse(b64('\n'.join(lines)), 'big.csv', 'punches')
        self.assertEqual(parsed['total'], 20000)
        self.assertTrue(parsed['truncated'])
        self.assertTrue(parsed['preview']['truncated'])
        # the days mode keeps its own 2 000 cap
        days = self.Flow.import_parse(b64('\n'.join(lines)), 'big.csv', 'days')
        self.assertEqual(days['max_rows'], 2000)

    # ============================================================ generic
    def test_15b_table_with_unknown_numbers(self):
        lines = ['Employee code,Date,Time,Machine']
        for code in ('885', '227'):
            for t in ('07:10', '16:35'):
                lines.append('%s,03/11/2026,%s,Factory 1' % (code, t))
        lines += ['TST-A,03/11/2026,07:00,Factory 1', 'TST-B,03/11/2026,07:02,Gate 9',
                  '885,03/11/2026,07:10,Factory 1']                    # repeat
        data = b64('\n'.join(lines))
        parsed = self.Flow.import_parse(data, 'punches.csv', 'punches')
        self.assertEqual(parsed['format'], 'table')
        m = parsed['mapping']
        self.assertEqual((m['user_code'], m['punch_date'], m['punch_time'], m['device']),
                         ('Employee code', 'Date', 'Time', 'Machine'))
        pv = parsed['preview']
        self.assertEqual(pv['punches'], 7)
        self.assertEqual(pv['unknown_count'], 2)
        self.assertEqual({u['code'] for u in pv['unknown']}, {'TST-A', 'TST-B'})
        self.assertEqual(pv['repeats'], 1)
        self.assertEqual(self.Punch.search_count([('company_id', '=', self.company.id)]), 0,
                         "the check writes nothing")
        res = self.Flow.import_commit(data, 'punches.csv', m, 'punches')
        self.assertEqual(res['created'], 6)
        self.assertEqual(res['unknown_count'], 2)
        self.assertEqual(res['new_devices'], ['Gate 9'])
        self.assertIn('6 punches added', res['message'])
        self.assertIn('2 numbers not matched', res['message'])
        self.assertTrue(res['triggered'])
        f1 = self.Punch.search([('user_code', '=', '885'),
                                ('company_id', '=', self.company.id)])
        self.assertEqual(f1.mapped('device_id'), self.device)
        # nothing was paired inline (ledger rule 12)
        self.assertEqual(set(f1.mapped('state')), {'new'})
        self.assertFalse(self.device_atts(self.e885))
