# -*- coding: utf-8 -*-
"""DOCSTUDIO X — the fill itself (handover §6 tests 1–11).

Pure functions over bytes; the database is only the test runner's. Every
fixture is made by code in `fixtures.py` — no customer file is committed.
"""
import io
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date, datetime

from lxml import etree

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_excel_layout.models import xlsx_fill
from odoo.addons.pb_excel_layout.models.xlsx_fill import LayoutError

from . import fixtures as fx

NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def _table(n=50, cols=3):
    columns = [{'key': 'dept', 'label': 'Department', 'type': 'text'},
               {'key': 'net', 'label': 'Net pay', 'type': 'money'},
               {'key': 'paid', 'label': 'Paid on', 'type': 'date'},
               {'key': 'more', 'label': 'More', 'type': 'number'}][:cols]
    rows = []
    for i in range(n):
        row = ['Dept %02d' % (i + 1), 1000.0 * (i + 1) + 0.5,
               date(2026, 4, 1 + (i % 28)), i][:cols]
        rows.append(row)
    return {'title': 'Net by department', 'columns': columns, 'rows': rows,
            'truncated': False, 'note': ''}


def _board_pack(extra=None):
    """A finance team's board pack: a title, a note row, headings the team
    typed at B5, a formula beside the table, a second sheet that sums the
    figures, a chart on it, defined names, conditional formats."""
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Font, PatternFill
    from openpyxl.workbook.defined_name import DefinedName
    wb = Workbook()
    ws = wb.active
    ws.title = 'Data'
    ws['A1'] = 'Board pack — payroll'
    ws['A1'].font = Font(bold=True, size=16)
    ws['A2'] = 'Prepared by Finance'
    ws['A3'] = 'Do not edit below row 5'
    ws['B5'] = 'Our heading'
    ws['B5'].fill = PatternFill('solid', fgColor='DDEBF7')
    for r in range(7, 60):
        ws.cell(r, 1, 'keep %d' % r)            # left of the table
        ws.cell(r, 6, '=C%d*2' % r)             # right of the table
    summary = wb.create_sheet('Summary')
    summary['A1'] = '=SUM(Data!C:C)'
    summary['A2'] = 'Total net pay'
    chart = BarChart()
    chart.add_data(Reference(ws, min_col=3, min_row=6, max_row=60),
                   titles_from_data=True)
    summary.add_chart(chart, 'C3')
    ws.conditional_formatting.add(
        'C7:C200', CellIsRule(operator='greaterThan', formula=['100000'],
                              fill=PatternFill('solid', fgColor='FFC7CE')))
    wb.defined_names['NetPay'] = DefinedName('NetPay', attr_text='Data!$C:$C')
    if extra:
        extra(wb)
    return fx.wb_bytes(wb)


def _sheet_xml(raw, part='xl/worksheets/sheet1.xml'):
    return etree.fromstring(fx.read(raw, part))


def _cell_el(root, ref):
    found = root.xpath('//m:c[@r="%s"]' % ref, namespaces=NS)
    return found[0] if found else None


def _load(raw, data_only=False):
    from openpyxl import load_workbook
    return load_workbook(io.BytesIO(raw), data_only=data_only)


@tagged('post_install', '-at_install', 'docstudio_x')
class TestLayoutFill(TransactionCase):

    # ------------------------------------------------------------- T1
    def test_t01_ds2_openpyxl_loses_what_zip_surgery_keeps(self):
        """Ledger DS-2, measured: a board pack with an Excel-made chart (chart
        style + colour parts) and a text box, round-tripped through openpyxl,
        loses those parts; through `fill` every one is byte-identical."""
        from openpyxl import Workbook, load_workbook
        from openpyxl.chart import BarChart, Reference
        wb = Workbook()
        ws = wb.active
        ws.title = 'Data'
        for i in range(1, 11):
            ws.cell(i, 1, i)
            ws.cell(i, 2, i * 2)
        chart = BarChart()
        chart.add_data(Reference(ws, min_col=2, min_row=1, max_row=10))
        ws.add_chart(chart, 'D2')
        raw = fx.excel_like_chart(fx.wb_bytes(wb))
        before = fx.members(raw)

        buf = io.BytesIO()
        load_workbook(io.BytesIO(raw)).save(buf)
        via_openpyxl = fx.members(buf.getvalue())
        lost = sorted(set(before) - set(via_openpyxl))
        self.assertIn('xl/charts/style1.xml', lost)
        self.assertIn('xl/charts/colors1.xml', lost)
        self.assertNotIn(b'Board note', fx.read(buf.getvalue(),
                                                'xl/drawings/drawing1.xml'),
                         'openpyxl drops the text box')

        out, _notes = xlsx_fill.fill(raw, 'Data', 'A12', True,
                                     _table(5, 2), 'pack.xlsx')
        after = fx.members(out)
        self.assertEqual(list(after), list(before), 'same members, same order')
        changed = sorted(n for n in before if before[n] != after[n])
        self.assertEqual(changed, ['xl/workbook.xml',
                                   'xl/worksheets/sheet1.xml'])
        self.assertIn(b'Board note', fx.read(out, 'xl/drawings/drawing1.xml'))

    # ------------------------------------------------------------- T2
    def test_t02_basic_fill_at_b6(self):
        raw = _board_pack()
        before = _sheet_xml(raw)
        out, notes = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(50),
                                    'pack.xlsx')
        ws = _load(out)['Data']
        self.assertEqual([ws['B6'].value, ws['C6'].value, ws['D6'].value],
                         ['Department', 'Net pay', 'Paid on'])
        self.assertEqual(ws['B7'].value, 'Dept 01')
        self.assertEqual(ws['C7'].value, 1000.5)
        self.assertEqual(ws['B56'].value, 'Dept 50')
        self.assertEqual(ws['C56'].value, 50000.5)
        self.assertIsNone(ws['B57'].value)
        self.assertIsInstance(ws['C30'].value, float)
        # no date style on the template row: the date stays readable text
        self.assertEqual(ws['D7'].value, '2026-04-01')
        # rows above the start are untouched, byte for byte
        after = _sheet_xml(out)
        for r in range(1, 6):
            old = before.xpath('//m:row[@r="%d"]' % r, namespaces=NS)
            new = after.xpath('//m:row[@r="%d"]' % r, namespaces=NS)
            self.assertEqual([etree.tostring(e) for e in old],
                             [etree.tostring(e) for e in new], 'row %d' % r)
        # beside the table: kept
        self.assertEqual(ws['A30'].value, 'keep 30')
        self.assertEqual(ws['F30'].value, '=C30*2')
        self.assertEqual(after.find('m:dimension', NS).get('ref'), 'A1:F59')
        self.assertFalse(notes['table_left'])

    # ------------------------------------------------------------- T3
    def test_t03_every_row_follows_the_first(self):
        from openpyxl.styles import Font

        def styled(wb):
            ws = wb['Data']
            ws['B7'].font = Font(bold=True)
            ws['C7'].number_format = '#,##0.00'
            ws['D7'].number_format = 'dd/mm/yyyy'
        raw = _board_pack(styled)
        tpl = _sheet_xml(raw)
        style = {c: _cell_el(tpl, '%s7' % c).get('s') for c in 'BCD'}
        out, _notes = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(50),
                                     'pack.xlsx')
        root = _sheet_xml(out)
        for r in range(7, 57):
            for c in 'BCD':
                self.assertEqual(_cell_el(root, '%s%d' % (c, r)).get('s'),
                                 style[c], '%s%d' % (c, r))
        ws = _load(out)['Data']
        self.assertTrue(ws['B40'].font.b)
        self.assertEqual(ws['C40'].number_format, '#,##0.00')
        self.assertIsInstance(ws['D40'].value, datetime, 'a real date')
        self.assertEqual(ws['D40'].value.date(), date(2026, 4, 6))

    # ------------------------------------------------------------- T4
    def test_t04_a_shorter_result_leaves_nothing_stale(self):
        raw = _board_pack()
        first, _n = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(50),
                                   'pack.xlsx')
        second, _n = xlsx_fill.fill(first, 'Data', 'B6', True, _table(10),
                                    'pack.xlsx')
        ws = _load(second)['Data']
        self.assertEqual(ws['B16'].value, 'Dept 10')
        for r in range(17, 60):
            for c in 'BCD':
                self.assertIsNone(ws['%s%d' % (c, r)].value, '%s%d' % (c, r))
            self.assertEqual(ws['A%d' % r].value, 'keep %d' % r)
            self.assertEqual(ws['F%d' % r].value, '=C%d*2' % r)
        # no result at all: only the headings stay
        third, _n = xlsx_fill.fill(second, 'Data', 'B6', True, _table(0),
                                   'pack.xlsx')
        ws = _load(third)['Data']
        self.assertEqual(ws['B6'].value, 'Department')
        self.assertIsNone(ws['B7'].value)

    # ------------------------------------------------------------- T5
    def test_t05_formulas_recalculate_and_the_chain_goes(self):
        raw = fx.with_calc_chain(_board_pack(), cells=('A1',))
        # As Excel saves it: a stale cached result (999) and no instruction
        # to recalculate (openpyxl itself writes fullCalcOnLoad; Excel not).
        raw = fx.rezip(raw, replace={
            'xl/worksheets/sheet2.xml': lambda x: x.replace(
                b'<f>SUM(Data!C:C)</f><v></v>',
                b'<f>SUM(Data!C:C)</f><v>999</v>'),
            'xl/workbook.xml': lambda x: x.replace(b' fullCalcOnLoad="1"', b'')})
        self.assertIn(b'<v>999</v>', fx.read(raw, 'xl/worksheets/sheet2.xml'))
        self.assertNotIn(b'fullCalcOnLoad', fx.read(raw, 'xl/workbook.xml'))
        out, _n = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(10),
                                 'pack.xlsx')
        names = fx.members(out)
        self.assertNotIn('xl/calcChain.xml', names)
        self.assertNotIn(b'calcChain', fx.read(out, '[Content_Types].xml'))
        self.assertNotIn(b'calcChain', fx.read(out, 'xl/_rels/workbook.xml.rels'))
        wb = etree.fromstring(fx.read(out, 'xl/workbook.xml'))
        self.assertEqual(wb.find('m:calcPr', NS).get('fullCalcOnLoad'), '1')
        self.assertEqual(wb.find('m:calcPr', NS).get('calcId'), '124519')
        _load(out)                                   # opens cleanly
        # a workbook with no <calcPr> at all gets one, in schema order
        bare = fx.rezip(raw, replace={'xl/workbook.xml': lambda x: re.sub(
            rb'<calcPr[^>]*/>', b'', x)})
        out2, _n = xlsx_fill.fill(bare, 'Data', 'B6', True, _table(3),
                                  'pack.xlsx')
        wb2 = etree.fromstring(fx.read(out2, 'xl/workbook.xml'))
        self.assertEqual(etree.QName(wb2[-1]).localname, 'calcPr')
        self.assertEqual(wb2[-1].get('fullCalcOnLoad'), '1')
        expected = sum(1000.0 * i + 0.5 for i in range(1, 11))
        soffice = shutil.which('soffice') or shutil.which('libreoffice')
        if not soffice:
            return
        # Recalculated by a real spreadsheet program, not only checked.
        # LibreOffice IGNORES fullCalcOnLoad: its own default for Excel files
        # is "never recalculate on load" (OOXMLRecalcMode 1), so the stale 999
        # would stay. Set its throwaway profile to "always" (0): this proves
        # the figures are real numbers the customer's formulas pick up. That
        # Excel honours the flag is recorded in the report (ledger DS-5).
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, 'profile', 'user'))
            with open(os.path.join(tmp, 'profile', 'user',
                                   'registrymodifications.xcu'), 'w') as fh:
                fh.write(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<oor:items xmlns:oor="http://openoffice.org/2001/registry" '
                    'xmlns:xs="http://www.w3.org/2001/XMLSchema" '
                    'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
                    '<item oor:path="/org.openoffice.Office.Calc/Formula/Load">'
                    '<prop oor:name="OOXMLRecalcMode" oor:op="fuse">'
                    '<value>0</value></prop></item></oor:items>')
            src = os.path.join(tmp, 'filled.xlsx')
            with open(src, 'wb') as fh:
                fh.write(out)
            outdir = os.path.join(tmp, 'out')
            subprocess.run(
                [soffice, '-env:UserInstallation=file://%s/profile' % tmp,
                 '--headless', '--convert-to', 'xlsx', '--outdir', outdir, src],
                check=True, timeout=180, capture_output=True)
            with open(os.path.join(outdir, 'filled.xlsx'), 'rb') as fh:
                again = fh.read()
        value = _load(again, data_only=True)['Summary']['A1'].value
        self.assertAlmostEqual(value, expected, places=2,
                               msg='recalculated on open, not the stale 999')

    # ------------------------------------------------------------- T6
    def test_t06_an_excel_table_grows_with_the_rows(self):
        from openpyxl.worksheet.table import Table

        def table(cols):
            def add(wb):
                ws = wb['Data']
                for j, name in enumerate(('Dept', 'Net', 'Paid', 'Extra')[:cols]):
                    ws.cell(6, 2 + j, name)
                    ws.cell(7, 2 + j, 'x')
                ws.add_table(Table(displayName='Pay', ref='B6:%s7' % 'BCDE'[cols - 1]))
            return add
        raw = _board_pack(table(3))
        out, notes = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(20),
                                    'pack.xlsx')
        self.assertEqual(notes['table_resized'], ['Pay'])
        troot = etree.fromstring(fx.read(out, 'xl/tables/table1.xml'))
        self.assertEqual(troot.get('ref'), 'B6:D26')
        self.assertEqual(troot.find('m:autoFilter', NS).get('ref'), 'B6:D26')
        self.assertEqual([c.get('name') for c in troot.iter(
            '{%s}tableColumn' % NS['m'])], ['Department', 'Net pay', 'Paid on'])
        tables = _load(out)['Data'].tables
        self.assertEqual(tables['Pay'].ref, 'B6:D26')

        # four columns in the table, three in the result: left alone + note
        raw = _board_pack(table(4))
        out, notes = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(20),
                                    'pack.xlsx')
        self.assertEqual(notes['table_left'], ['Pay'])
        troot = etree.fromstring(fx.read(out, 'xl/tables/table1.xml'))
        self.assertEqual(troot.get('ref'), 'B6:E7')
        names = [c.get('name') for c in troot.iter('{%s}tableColumn' % NS['m'])]
        self.assertEqual(names, ['Department', 'Net pay', 'Paid on', 'Extra'],
                         'names follow the headings written over them')
        _load(out)

        # a table whose headings sit INSIDE the area is refused plainly
        with self.assertRaises(LayoutError) as caught:
            xlsx_fill.fill(raw, 'Data', 'B5', True, _table(20), 'pack.xlsx')
        self.assertEqual(caught.exception.code, 'table_in_way')

    # ------------------------------------------------------------- T7
    def test_t07_pivot_caches_refresh_on_open(self):
        raw = fx.with_pivot_cache(_board_pack())
        out, _n = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(5),
                                 'pack.xlsx')
        cache = etree.fromstring(fx.read(
            out, 'xl/pivotCache/pivotCacheDefinition1.xml'))
        self.assertEqual(cache.get('refreshOnLoad'), '1')
        self.assertEqual(cache.get('refreshedBy'), 'Finance', 'nothing else')

    # ------------------------------------------------------------- T8
    def test_t08_macros_are_carried_never_run(self):
        raw, blob = fx.with_macros(_board_pack())
        desc = xlsx_fill.describe(raw, 'pack.xlsm')
        self.assertTrue(desc['has_macros'])
        self.assertEqual(desc['ext'], '.xlsm')
        out, _n = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(5),
                                 'pack.xlsm')
        self.assertEqual(fx.read(out, 'xl/vbaProject.bin'), blob)
        self.assertEqual(fx.members(out)['xl/vbaProject.bin'],
                         fx.members(raw)['xl/vbaProject.bin'])
        self.assertEqual(xlsx_fill.mimetype('.xlsm'),
                         'application/vnd.ms-excel.sheet.macroEnabled.12')
        note = self.env['pb.excel.layout.board'].with_context(
            lang='en_US')._pbxl_file_answer(raw, 'pack.xlsm')['macro_note']
        self.assertIn('does not run or change them', note)
        self.assertNotIn('Odoo', note)

    # ------------------------------------------------------------- T9
    def test_t09_everything_else_is_byte_identical(self):
        """Rail R1 over a rich workbook: charts (Excel-made), a picture,
        defined names, conditional formats, a pivot cache, a calculation
        chain, macros. Only the documented parts change."""
        from openpyxl.drawing.image import Image
        from PIL import Image as PImage

        def picture(wb):
            png = io.BytesIO()
            PImage.new('RGB', (24, 24), (90, 75, 176)).save(png, 'PNG')
            png.seek(0)
            wb['Summary'].add_image(Image(png), 'J2')
        raw = fx.excel_like_chart(_board_pack(picture))
        raw = fx.with_pivot_cache(fx.with_calc_chain(raw))
        raw, _blob = fx.with_macros(raw)
        before = fx.members(raw)
        out, _n = xlsx_fill.fill(raw, 'Data', 'B6', True, _table(30),
                                 'pack.xlsm')
        after = fx.members(out)
        self.assertEqual(list(after),
                         [n for n in before if n != 'xl/calcChain.xml'])
        changed = sorted(n for n in after if after[n] != before[n])
        self.assertEqual(changed, sorted([
            '[Content_Types].xml', 'xl/_rels/workbook.xml.rels',
            'xl/pivotCache/pivotCacheDefinition1.xml', 'xl/workbook.xml',
            'xl/worksheets/sheet1.xml']))
        import zipfile
        with zipfile.ZipFile(io.BytesIO(raw)) as a, \
                zipfile.ZipFile(io.BytesIO(out)) as b:
            for info in b.infolist():
                old = a.getinfo(info.filename)
                self.assertEqual(info.compress_type, old.compress_type)
                self.assertEqual(info.date_time, old.date_time)
        # the parts that change change only where documented
        ct_old = fx.read(raw, '[Content_Types].xml').replace(
            b'<Override PartName="/xl/calcChain.xml" ContentType="application/'
            b'vnd.openxmlformats-officedocument.spreadsheetml.calcChain+xml"/>',
            b'')
        self.assertEqual(etree.tostring(etree.fromstring(ct_old)),
                         etree.tostring(etree.fromstring(
                             fx.read(out, '[Content_Types].xml'))))
        wb = _load(out)
        self.assertIn('NetPay', wb.defined_names)
        self.assertTrue(wb['Data'].conditional_formatting)

    # ------------------------------------------------------------ T10
    def test_t10_hostile_files_are_refused_plainly(self):
        raw = _board_pack()
        old_xls = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\0' * 2048
        cases = [
            (fx.zip_bomb(), 'bomb.xlsx', 'unzipped_too_big'),
            (fx.billion_laughs(raw), 'laughs.xlsx', 'unsafe_xml'),
            (fx.traversal(raw), 'walk.xlsx', 'bad_name'),
            (fx.big_file(raw), 'big.xlsx', 'too_big'),
            (fx.encrypted(), 'locked.xlsx', 'password'),
            (old_xls, 'old.xls', 'old_xls'),
            (b'Name,Net\nA,1\n', 'renamed.xlsx', 'not_excel'),
            (raw, 'pack.csv', 'wrong_ext'),
        ]
        board = self.env['pb.excel.layout.board'].with_context(lang='en_US')
        import base64
        for blob, name, code in cases:
            with self.assertRaises(LayoutError, msg=name) as caught:
                xlsx_fill.describe(blob, name)
            self.assertEqual(caught.exception.code, code, name)
            # through the facade: a plain sentence, never a traceback
            if len(blob) < 12 * 1024 * 1024:
                answer = board.inspect(base64.b64encode(blob).decode(), name)
                self.assertFalse(answer['ok'], name)
                self.assertTrue(answer['msg'], name)
                for word in ('Traceback', 'Odoo', 'Error', 'zip'):
                    self.assertNotIn(word, answer['msg'], name)
        self.assertIn('password', board.inspect(
            base64.b64encode(fx.encrypted()).decode(), 'locked.xlsx')['msg'])
        # 11 MB as base64 never even reaches the server code
        big = base64.b64encode(fx.big_file(raw)).decode()
        self.assertEqual(board.inspect(big, 'big.xlsx')['code'], 'too_big')

    # ------------------------------------------------------------ T11
    def test_t11_special_values(self):
        long_text = 'x' * 40000
        table = {'columns': [{'key': 'a', 'label': 'Value', 'type': 'text'},
                             {'key': 'b', 'label': 'Other', 'type': 'number'}],
                 'rows': [['=1+1', 1], ['+44 20 7946', 2], ['-5 days', None],
                          ['@SUM(A1)', True], ['Lương thực nhận — Hà Nội', 3.25],
                          ['Party 🎉 time', datetime(2026, 4, 30, 17, 30)],
                          ['bell\x07tab\tnew\nline\x00end', float('nan')],
                          [None, 0], [long_text, -1]],
                 'truncated': False, 'note': ''}
        raw = _board_pack()
        out, notes = xlsx_fill.fill(raw, 'Data', 'B6', True, table, 'p.xlsx')
        root = _sheet_xml(out)
        for ref in ('B7', 'B8', 'B9', 'B10'):
            cell = _cell_el(root, ref)
            self.assertEqual(cell.get('t'), 'inlineStr', ref)
            self.assertIsNone(cell.find('m:f', NS), '%s is not a formula' % ref)
        ws = _load(out)['Data']
        self.assertEqual(ws['B7'].value, '=1+1')
        self.assertEqual(ws['B7'].data_type, 's')
        self.assertEqual(ws['B11'].value, 'Lương thực nhận — Hà Nội')
        self.assertEqual(ws['B12'].value, 'Party 🎉 time')
        self.assertEqual(ws['B13'].value, 'belltab\tnew\nlineend')
        self.assertIsNone(ws['C9'].value)
        self.assertIs(ws['C10'].value, True)
        self.assertIsNone(ws['C13'].value, 'NaN is not written')
        self.assertIsNone(ws['B14'].value)
        self.assertEqual(ws['C14'].value, 0)
        self.assertEqual(len(ws['B15'].value), xlsx_fill.TEXT_MAX)
        self.assertEqual(notes['text_cut'], 1)
        # a datetime with no date style is readable text
        self.assertEqual(ws['C12'].value, '2026-04-30 17:30')

    # ------------------------------------------------------- set-up states
    def test_t11b_the_set_up_screen_reads_the_sheet(self):
        from openpyxl.worksheet.table import Table

        def more(wb):
            wb['Data'].merge_cells('B30:C30')
            ws = wb.create_sheet('Pivot ready')
            ws['C3'] = 'Dept'
            ws['D3'] = 'Net'
            ws['C4'] = 'a'
            ws['D4'] = 1
            ws.add_table(Table(displayName='Ready', ref='C3:D4'))
        raw = _board_pack(more)
        desc = xlsx_fill.describe(raw, 'pack.xlsx')
        names = [s['name'] for s in desc['sheets']]
        self.assertEqual(names, ['Data', 'Summary', 'Pivot ready'])
        data = desc['sheets'][0]
        self.assertEqual(len(data['grid']), 20)
        self.assertEqual(len(data['grid'][0]), 12)
        self.assertEqual(data['grid'][0][0], 'Board pack — payroll')
        self.assertEqual(data['looks'][0][0], {'b': 1})
        self.assertIn('B30:C30', data['merged'])
        self.assertEqual(data['suggested']['cell'], 'A4')
        self.assertEqual(desc['sheets'][2]['suggested'],
                         {'cell': 'C3', 'headers': True, 'why': 'table',
                          'table': 'Ready'})
        # merged cells in the way: refused at set-up, with the range
        with self.assertRaises(LayoutError) as caught:
            xlsx_fill.fill(raw, 'Data', 'B6', True, _table(5), 'pack.xlsx')
        self.assertEqual(caught.exception.code, 'merged')
        self.assertEqual(caught.exception.params['ref'], 'B30:C30')
        # a chart sheet, a missing sheet, a cell that is not one
        for sheet, cell, code in (('Nope', 'B6', 'sheet_missing'),
                                  ('Summary', 'ZZZZ1', 'bad_cell'),
                                  ('Summary', 'XFD1', 'too_wide')):
            with self.assertRaises(LayoutError) as caught:
                xlsx_fill.fill(raw, sheet, cell, True, _table(5), 'pack.xlsx')
            self.assertEqual(caught.exception.code, code)
        # an empty sheet starts at A1
        from openpyxl import Workbook
        empty = fx.wb_bytes(Workbook())
        self.assertEqual(xlsx_fill.describe(empty)['sheets'][0]['suggested']
                         ['cell'], 'A1')

    def test_t11c_the_1904_calendar_and_implied_cells(self):
        """Dates honour a workbook on the 1904 calendar; a sheet written by
        a tool that leaves out row and cell numbers is still filled right."""
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.title = 'Data'
        wb.active['D2'].number_format = 'yyyy-mm-dd'
        raw = fx.wb_bytes(wb)
        raw = fx.rezip(raw, replace={'xl/workbook.xml': lambda x: re.sub(
            rb'<workbookPr(\s[^>]*)?/>', rb'<workbookPr\1 date1904="1"/>', x,
            count=1)})
        self.assertIn(b'date1904="1"', fx.read(raw, 'xl/workbook.xml'))
        table = {'columns': [{'label': 'A'}, {'label': 'B'}, {'label': 'C'},
                             {'label': 'When', 'type': 'date'}],
                 'rows': [['x', 1, 2, date(2026, 4, 1)]]}
        out, _n = xlsx_fill.fill(raw, 'Data', 'A1', True, table)
        cell = _cell_el(_sheet_xml(out), 'D2')
        self.assertEqual(cell.find('m:v', NS).text,
                         str((date(2026, 4, 1) - date(1904, 1, 1)).days))
        # rows and cells with no numbers (legal; some tools write them)
        bare = fx.rezip(fx.wb_bytes(Workbook()), replace={
            'xl/worksheets/sheet1.xml': lambda x: re.sub(
                rb'<sheetData\s*/>|<sheetData>.*</sheetData>',
                b'<sheetData><row><c t="inlineStr"><is><t>Title</t></is></c>'
                b'</row><row><c/><c t="inlineStr"><is><t>B2</t></is></c>'
                b'</row></sheetData>', x, flags=re.S)})
        out, _n = xlsx_fill.fill(bare, 'Sheet', 'A4', False,
                                 {'columns': [{'label': 'v'}], 'rows': [[7]]})
        ws = _load(out)['Sheet']
        self.assertEqual((ws['A1'].value, ws['B2'].value, ws['A4'].value),
                         ('Title', 'B2', 7))

