# -*- coding: utf-8 -*-
"""RECORDS R4 — the defect round, on the server side.

R4 is mostly a client-side round: three of its six defects are about what the
screen does with what the server already says, and those are pinned in
`static/tests/records_grid.test.js`. Two land here.

  * **D6** — `import_probe`, the cheap first call that counts a file's rows so
    the veil can say *"Matching 4,512 rows to people…"* instead of spinning.
    What is asserted is the whole contract: it counts, it never writes, it
    refuses a bad file in the SAME sentence `import_peek` refuses it in, and it
    is fast enough on a roster-sized file to be worth doing before the peek
    rather than instead of it.
  * **the white-label rail** — extended over R4's own new source, because a
    rule that only ever reads the files of the phase that wrote it is a rule
    that decays one phase at a time.

`action_process` is never called (J3/J10), and nothing here writes a payslip.
"""
import base64
import io
import logging
import re
import time
import unittest

from unittest.mock import patch

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_records.models import pb_records_io

try:
    import openpyxl
except ImportError:             # pragma: no cover — the server has it
    openpyxl = None


_logger = logging.getLogger(__name__)


def _src(module, *parts):
    import os
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestRecordsR4Polish(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if openpyxl is None:
            raise unittest.SkipTest("openpyxl is not installed here")
        cls.Desk = cls.env['pb.records.desk']
        cls.Employee = cls.env['hr.employee']

    # ---------------------------------------------------------------- helpers
    def _b64(self, wb):
        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return base64.b64encode(out.read()).decode()

    def _book(self, rows):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = pb_records_io.SHEET
        ws.append(['Employee code', 'Name', 'Work email'])
        for i in range(rows):
            ws.append(['R4%05d' % i, 'R4 Person %d' % i,
                       'r4%d@example.test' % i])
        return wb

    # =====================================================================
    # 15 — D6: how many rows, and nothing else
    # =====================================================================
    def test_15a_the_probe_counts_the_rows_of_a_workbook(self):
        res = self.Desk.import_probe(self._b64(self._book(12)), 'r4.xlsx')
        self.assertTrue(res['ok'], res.get('msg'))
        # Twelve people, thirteen lines: the heading is not a person.
        self.assertEqual(res['rows'], 12)
        self.assertFalse(res['truncated'])

    def test_15b_the_probe_counts_a_csv_the_same_way(self):
        text = ("Employee code,Name,Work email\n"
                "R400001,R4 One,r4one@example.test\n"
                "\n"                      # a blank line is not a row
                "R400002,R4 Two,r4two@example.test\n")
        res = self.Desk.import_probe(
            base64.b64encode(text.encode('utf-8')).decode(), 'r4.csv')
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(res['rows'], 2)

    def test_15c_the_probe_creates_absolutely_nothing(self):
        before_people = self.Employee.search_count([])
        before_slips = self.env['hr.payslip'].sudo().search_count([])
        before_batches = self.env['hr.payroll.import.batch'].sudo().search_count([]) \
            if 'hr.payroll.import.batch' in self.env else 0
        self.Desk.import_probe(self._b64(self._book(30)), 'r4.xlsx')
        self.Desk.import_probe(
            base64.b64encode(b'Employee code\nR400001\n').decode(), 'r4.csv')
        self.env.flush_all()
        self.assertEqual(self.Employee.search_count([]), before_people)
        self.assertEqual(self.env['hr.payslip'].sudo().search_count([]),
                         before_slips)
        if 'hr.payroll.import.batch' in self.env:
            self.assertEqual(
                self.env['hr.payroll.import.batch'].sudo().search_count([]),
                before_batches)

    def test_15d_a_file_the_peek_refuses_the_probe_refuses_identically(self):
        """One file, one sentence — whichever call meets it first.

        The probe runs BEFORE the peek, so a refusal it invents on its own is a
        refusal the user reads twice in two different wordings. Both calls go
        through `_io_probe_guard`, and this is what holds them together.
        """
        cases = [
            ('', 'empty.xlsx'),
            (base64.b64encode(b'hello').decode(), 'letter.docx'),
        ]
        for file_b64, name in cases:
            probe = self.Desk.import_probe(file_b64, name)
            peek = self.Desk.import_peek(0, file_b64, name)
            self.assertFalse(probe['ok'])
            self.assertFalse(peek['ok'])
            self.assertEqual(probe['msg'], peek['msg'],
                             "the two calls refuse %s differently" % name)
            self.assertEqual(probe['rows'], 0)

    def test_15e_a_file_too_big_to_read_is_refused_before_it_is_parsed(self):
        big = base64.b64encode(b'x' * (pb_records_io.MAX_BYTES + 1)).decode()
        res = self.Desk.import_probe(big, 'huge.xlsx')
        self.assertFalse(res['ok'])
        self.assertIn('larger than 10 MB', res['msg'])

    def test_15f_a_roster_sized_file_is_counted_in_well_under_a_second(self):
        """The whole point of the probe is that it answers before the peek.

        4,500 rows is the reference tenant's roster. The bound asserted is a
        loose one (two seconds) because this runs on a shared box; the number
        that matters is the one in the log line, and it has been an order of
        magnitude under the bound every time.
        """
        payload = self._b64(self._book(4500))
        started = time.time()
        res = self.Desk.import_probe(payload, 'roster.xlsx')
        took = time.time() - started
        self.assertTrue(res['ok'], res.get('msg'))
        self.assertEqual(res['rows'], 4500)
        self.assertLess(took, 2.0,
                        "the probe took %.3fs on 4,500 rows" % took)
        # Logged, never printed: stdout goes to /dev/null when odoo-bin runs
        # with a --logfile (RD2), and the measured number is the report's.
        _logger.info("R4 D6: import_probe counted 4,500 rows in %.3fs", took)

    def test_15g_the_cap_is_reported_rather_than_hidden(self):
        wb = self._book(6)
        with patch.object(pb_records_io, 'MAX_ROWS', 2):
            res = self.Desk.import_probe(self._b64(wb), 'capped.xlsx')
        self.assertTrue(res['ok'])
        self.assertTrue(res['truncated'])

    # =====================================================================
    # 16 — no user-visible string in R4's own source says the wrong word
    # =====================================================================
    #: Same definition as R3's (RD5): the pictograph planes, not "every symbol".
    EMOJI = re.compile('[\U0001F000-\U0001FAFF\U00002600-\U000027BF️]')
    SAFE_SYMBOLS = set('←→↑↓·✕—–≤≥⌘⇆')

    def test_16_the_new_source_never_names_the_engine(self):
        for module, parts, is_xml in (
                ('pb_records', ('static', 'src', 'js', 'records_review.js'), False),
                ('pb_records', ('static', 'src', 'js', 'records_desk.js'), False),
                ('pb_records', ('static', 'src', 'xml', 'records_desk.xml'), True),
                ('pb_records', ('models', 'pb_records_io.py'), False)):
            body = _src(module, *parts)
            if is_xml:
                body = re.sub(r'<!--.*?-->', ' ', body, flags=re.S)
                body = re.sub(r'</?odoo>', ' ', body)
            else:
                body = '\n'.join(
                    re.sub(r'(?<!["\'])#.*$', '', line)
                    for line in body.splitlines())
                body = re.sub(r'@odoo-module|@odoo/owl|@web/[\w/.]+', ' ', body)
            self.assertNotIn('Odoo', body,
                             "user-visible string in %s" % parts[-1])
            leftover = [ch for ch in self.EMOJI.findall(body)
                        if ch not in self.SAFE_SYMBOLS]
            self.assertFalse(leftover, "emoji in %s" % parts[-1])
