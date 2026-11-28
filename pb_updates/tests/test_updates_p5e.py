# -*- coding: utf-8 -*-
"""UPDATES P5e — owner decision of 2026-11-14 (ledger D33).

On the EMPLOYEE'S OWN tax summary (`/my/taxsheet`) only: a mid-month advance
whose month-end payslip is not finished yet IS counted in the year's totals
until that month-end payslip is finished; from then on it is not added (each
month once, as P5d). Everywhere else (year-to-date view, both downloads, the
popover, a mapped pay run) such an advance is still not added and its month
still stops a pay run — exactly as P5c/P5d.

Every expected number is worked out BY HAND next to it. P5d's fixture world
(its own company, schemes, link advance -> month-end) is reused by subclassing;
the Odoo test loader runs only the methods a class defines itself, so P5d's own
cases still run once, in their own class.
"""
import base64
import io

from . import test_updates_p5d as p5d

try:
    import openpyxl
except ImportError:            # pragma: no cover
    openpyxl = None

from odoo.tests import tagged

ADV = {'GROSS': 100000.0, 'PIT': -10000.0, 'SIEMP': -8000.0, 'ADV': 60000.0}
COUNTED_NOW = 'Mid-month advance · counted until the month-end payslip is finished'


@tagged('post_install', '-at_install', 'pb_updates', 'pb_updates_p5e')
class TestUpdatesP5e(p5d.TestUpdatesP5d):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        P, M, A, L = cls.people, cls.monthly, cls.advance, cls.loose
        for code in ('QUA', 'RIA'):
            cls.people[code] = cls._person('DEMO P5e %s' % code.title(), 'P5E' + code)
        # QUA — April and May: linked advance + month-end; June: the linked
        # advance only (its month-end payslip is not finished yet).
        for m in (4, 5):
            cls._finished(P['QUA'], A, m, dict(ADV))
            cls._finished(P['QUA'], M, m, dict(p5d.MONTH_END))
        cls.qua_june = cls._finished(P['QUA'], A, 6, dict(ADV))
        # RIA — July month-end, August: an advance of a scheme linked to NOTHING
        # and no month-end payslip (truly unmatched).
        cls._finished(P['RIA'], M, 7, dict(p5d.MONTH_END))
        cls.ria_aug = cls._finished(P['RIA'], L, 8, {'GROSS': 70000.0, 'ADV': 40000.0})

    # ================================================================ A1
    def test_A1_unfinished_month_end_advance_counted_on_the_page(self):
        page, qc = self.summary(self.people['QUA'])
        # The page alone: 2 x (advance + month-end) + the June advance = 5 x 100,000.
        self.assertEqual(page['ytd']['GROSS'], 500000.0)
        # Now: April + May month-end (200,000) + the June advance until its
        # month-end payslip is finished (100,000) = 300,000; tax 3 x 10,000;
        # contributions 3 x 8,000 — in the page's own (negative) sign.
        self.assertEqual(qc['ytd']['GROSS'], 300000.0)
        self.assertEqual(qc['ytd']['PIT'], -30000.0)
        self.assertEqual(qc['ytd']['SIEMP'], -24000.0)
        june = self.qua_june.id
        self.assertEqual(qc['ytd_not_added'][june], COUNTED_NOW)
        self.assertEqual(qc['ytd_counted_for_now'], [june])
        others = [w for sid, w in qc['ytd_not_added'].items() if sid != june]
        self.assertEqual(others, ['Mid-month advance · not added'] * 2)
        self.assertIn('Until that month-end payslip is finished', qc['ytd_advance_note'])
        self.assertEqual(qc['rows'], page['rows'], 'the rows never change')
        self.assertFalse(qc['ytd_advance_apart'])

    # ================================================================ A2
    def test_A2_month_end_finished_then_advance_not_added(self):
        self._finished(self.people['QUA'], self.monthly, 6, dict(p5d.MONTH_END))
        _page, qc = self.summary(self.people['QUA'])
        # April, May, June month-end only: 3 x 100,000; the June advance is not added.
        self.assertEqual(qc['ytd']['GROSS'], 300000.0)
        self.assertEqual(qc['ytd']['PIT'], -30000.0)
        self.assertEqual(qc['ytd_not_added'][self.qua_june.id], 'Mid-month advance · not added')
        self.assertFalse(qc['ytd_counted_for_now'])
        self.assertNotIn('Until that month-end payslip', qc['ytd_advance_note'])
        # Equal to the year-to-date view (month counted once).
        cells = self.view()[self.people['QUA'].id]['cells']
        self.assertEqual(qc['ytd']['GROSS'], cells['gross']['paid'])
        self.assertEqual(-qc['ytd']['PIT'], cells['tax']['paid'])
        self.assertEqual(-qc['ytd']['SIEMP'], cells['ee_social']['paid'])
        self.assertEqual(cells['months']['paid'], 3.0)

    # ================================================================ A3
    def test_A3_everything_else_unchanged_for_the_A1_person(self):
        qua = self.people['QUA']
        # The helper's default is P5d's behaviour.
        ledger = self.Line._ledger([qua.id], p5d.date(2026, 1, 1), p5d.date(2026, 12, 31),
                                   ['GROSS'])
        default = self.Line._person_window(ledger, qua.id)
        state = {r['id']: r['state'] for r in default['rows']}
        self.assertEqual(state[self.qua_june.id], 'advance_only')
        self.assertNotIn(self.qua_june.id, [r['id'] for r in default['counted']])
        # Year-to-date view and popover: April + May only; June not counted.
        cells = self.view()[qua.id]['cells']
        self.assertEqual(cells['gross']['paid'], 200000.0)
        self.assertEqual(cells['tax']['paid'], 20000.0)
        self.assertEqual(cells['months']['paid'], 2.0)
        d = self.Upd.get_ytd_cell_detail(2026, qua.id, 'gross')
        self.assertTrue(d['ok'], d.get('msg'))
        self.assertEqual(len(d['counted']), 2)
        self.assertNotIn(self.qua_june.id, [c.get('id') for c in d['counted']])
        # Figures before Payobook up to 31 March, a mapping, a July pay period:
        # June has only the advance, so the pay run stops for her (no silent number).
        self.load([['Code', 'Gross pay'], ['P5EQUA', '300000']], {2: 'y:gross'},
                  covers='2026-03-31', name='P5e Qua')
        self.mapping('GROSSYTD', 'gross')
        plan = self.plan('QUA', '2026-07-01', '2026-07-31')
        self.assertTrue(self.Line._plan_blocked(plan['GROSSYTD']))
        # "Download for the pay run": no value for her.
        dl = self.Upd.download_for_payrun(self.monthly.id, '2026-07-01')
        self.assertTrue(dl['ok'], dl.get('msg'))
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(dl['file_b64'])))
        ws = wb.worksheets[0]
        heads = [c.value for c in ws[1]]
        col = next(i for i, h in enumerate(heads) if h and '(GROSSYTD)' in h)
        line = next(r for r in ws.iter_rows(min_row=2, values_only=True) if r[0] == 'P5EQUA')
        self.assertIn(line[col], (None, ''))
        adj = [r[0] for r in wb.worksheets[1].iter_rows(min_row=2, values_only=True)]
        self.assertNotIn(qua.id, adj)
        # The view's own download: the June advance is not in her total.
        cells = self.view()[qua.id]['cells']
        self.assertEqual(cells['gross']['paid'], 200000.0)

    # ================================================================ A4
    def test_A4_no_advance_and_truly_unmatched_stay_as_p5d(self):
        # No advance at all: not one value of the page changes (YAN, as Z2a).
        page, qc = self.summary(self.people['YAN'])
        self.assertEqual(qc, page)
        # RIA: the August advance's scheme is linked to no month-end scheme —
        # not counted, P5d's words, nothing "counted for now".
        page, qc = self.summary(self.people['RIA'])
        self.assertEqual(page['ytd']['GROSS'], 170000.0, 'the page alone adds both')
        self.assertEqual(qc['ytd']['GROSS'], 100000.0, 'the July month-end only')
        self.assertEqual(qc['ytd_not_added'][self.ria_aug.id],
                         'Mid-month advance · waits for month end')
        self.assertFalse(qc['ytd_counted_for_now'])
        # ZOE (every advance has its month-end) and WES (linked to nothing, with
        # a month-end) are exactly as P5d: Z1 / Z2c of the parent class.
        _page, qc = self.summary(self.people['ZOE'])
        self.assertEqual(qc['ytd']['GROSS'], 300000.0)
        self.assertFalse(qc['ytd_counted_for_now'])
        _page, qc = self.summary(self.people['WES'])
        self.assertEqual(qc['ytd']['GROSS'], 100000.0)
        self.assertEqual(qc['ytd_advance_apart'], {'GROSS': 70000.0})

    def test_A5_no_vendor_name_in_new_strings(self):
        _page, qc = self.summary(self.people['QUA'])
        texts = list(qc['ytd_not_added'].values()) + [qc['ytd_advance_note']]
        self.assertFalse([t for t in texts if 'odoo' in t.lower()])
        arch = self.env.ref('pb_updates.portal_my_taxsheet_ytd').arch
        self.assertIn('ytd_counted_for_now', arch)
