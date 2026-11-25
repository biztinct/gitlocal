# -*- coding: utf-8 -*-
"""WFSETUP P10c — two "From the clocks" labels (backlog B5 + B6).

B5: the pay data template built from a scheme marks every column the clocks
answer ("From the clocks from <date> — leave blank for those months") once the
scheme has a clock date; without one the workbook is the workbook it was
before P10c (every part of the file except its creation timestamp).

B6: the component editor's source card gets `source.clock` — the chip
"From the clocks — from <date>" — for an input the clocks answer on a scheme
with a clock date, and nothing for anything else.

Labels only: no calculation, no stored field, no source ranking is touched.
"""
import base64
import datetime
import io
import os
import re
import zipfile

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

try:
    import openpyxl
    OPENPYXL = True
except ImportError:  # pragma: no cover
    OPENPYXL = False

T_TEMPLATE = "From the clocks from %s — leave blank for those months"
T_CHIP = "From the clocks — from %s"
T_HINT = ("Answered by the clocks: %(fact)s. Pay periods from %(day)s take this value from the clocks, "
          "not the pay data file; earlier pay periods read it as before.")
DEC1 = datetime.date(2026, 12, 1)


def _zip_parts(content):
    """Every member of an xlsx except the creation/modification stamp."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        return {n: zf.read(n) for n in zf.namelist() if n != 'docProps/core.xml'}


@tagged('post_install', '-at_install')
class TestP10cClockLabels(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.env.user.lang = 'en_US'

    def _config(self, name, sheet='', keyed=True):
        cfg = self.Config.create({
            'name': name, 'code': re.sub(r'\W', '', name.upper())[:32],
            'country_code': 'VN', 'state': 'draft',
        })
        specs = [('Employee Code', 'EMPCODE', False),
                 ('Paid Days', 'PAIDDAYS', 'clock.paid_days'),
                 ('Overtime Hours', 'OVERTIMEH', 'clock.ot_hours'),
                 ('Meal Allowance', 'MEAL', False),
                 ('Sunday Hours', 'SUNHRS', 'clock.empty')]
        for seq, (label, code, _key) in enumerate(specs, start=1):
            self.Rule.create({'config_id': cfg.id, 'name': label, 'code': code,
                              'column_type': 'input', 'sequence': seq,
                              'source_sheet_name': sheet})
        self.Rule.create({'config_id': cfg.id, 'name': 'Net Pay', 'code': 'NETPAY',
                          'column_type': 'formula', 'sequence': 90,
                          'source_sheet_name': sheet})
        if keyed:
            for label, code, key in specs:
                if key:
                    cfg.rule_ids.filtered(lambda r, c=code: r.code == c).set_source_binding('clock', key)
        return cfg

    def _rule(self, cfg, code):
        return cfg.rule_ids.filtered(lambda r: r.code == code)

    def _pre_p10c_template(self, cfg):
        """What `_build_pay_data_template` produced before P10c: the same call
        without the clock notes."""
        from odoo.addons.pb_hr_payroll_formula.integrations.excel_connector import ExcelConnector
        connector = ExcelConnector(self.env['hr.integration.connector'])
        return connector.generate_template(
            cfg.rule_ids.sorted(key=lambda r: r.sequence),
            pk_header=cfg._pay_template_pk_header(), sheet_title='Pay Data')

    def _headings(self, content):
        wb = openpyxl.load_workbook(io.BytesIO(content))
        out = {}
        for ws in wb.worksheets:
            for cell in ws[1]:
                if cell.value is None:
                    continue
                out[(ws.title, cell.value)] = {
                    'note': cell.comment.text if cell.comment else '',
                    'fill': cell.fill.fgColor.rgb, 'color': cell.font.color.rgb if cell.font.color else None,
                }
        return out

    # ------------------------------------------------------------------ 1
    def test_01_clock_dated_template_marks_clock_columns_only(self):
        if not OPENPYXL:
            self.skipTest('openpyxl unavailable')
        for sheet in ('', 'SEVL'):
            cfg = self._config('P10c T1 %s' % (sheet or 'flat'), sheet=sheet)
            before = self._headings(self._pre_p10c_template(cfg))
            cfg.pb_clock_from = DEC1
            content, filename = cfg._build_pay_data_template()
            self.assertTrue(filename.endswith('_pay_data_template.xlsx'))
            after = self._headings(content)
            self.assertEqual(list(after), list(before),
                             "headings, their order and sheets never change — they are what the "
                             "resolver matches on re-import")
            want = T_TEMPLATE % cfg._pb_clock_from_label()
            self.assertIn('2026', want)
            title = sheet or 'Pay Data'
            for name in ('Paid Days', 'Overtime Hours', 'Sunday Hours'):
                cell = after[(title, name)]
                self.assertTrue(cell['note'].startswith(want + '\n\n'), cell['note'])
                self.assertTrue(cell['note'].endswith(before[(title, name)]['note']),
                                "the old note (name, code, letter) is kept under the sentence")
                self.assertEqual(cell['fill'][-6:], 'EEF0F3')
            for name in ('Employee Code', 'Meal Allowance'):
                self.assertEqual(after[(title, name)], before[(title, name)],
                                 "%s is not answered by the clocks: unchanged" % name)
            wb = openpyxl.load_workbook(io.BytesIO(content))
            self.assertEqual(wb.worksheets[0].max_row, 1, "still headings only")

    def test_01b_date_follows_the_readers_language(self):
        cfg = self._config('P10c T1b')
        cfg.pb_clock_from = DEC1
        self.env['res.lang']._activate_lang('vi_VN')
        self.env['res.lang']._activate_lang('id_ID')
        self.assertEqual(cfg.with_context(lang='vi_VN')._pb_clock_from_label(), '1 thg 12, 2026')
        self.assertEqual(cfg.with_context(lang='id_ID')._pb_clock_from_label(), '1 Des 2026')
        self.assertEqual(cfg.with_context(lang='en_US')._pb_clock_from_label(), 'Dec 1, 2026')
        notes = cfg.with_context(lang='vi_VN')._pb_clock_template_notes()
        self.assertTrue(all('1 thg 12, 2026' in t for t in notes.values()))

    # ------------------------------------------------------------------ 2
    def test_02_no_clock_date_template_is_identical(self):
        if not OPENPYXL:
            self.skipTest('openpyxl unavailable')
        for sheet in ('', 'SEVL'):
            # keyed inputs but no date, and no keys at all
            for keyed in (True, False):
                cfg = self._config('P10c T2 %s %s' % (sheet or 'flat', keyed), sheet=sheet, keyed=keyed)
                self.assertFalse(cfg.pb_clock_from)
                self.assertEqual(cfg._pb_clock_template_notes(), {})
                content, _fn = cfg._build_pay_data_template()
                self.assertEqual(_zip_parts(content), _zip_parts(self._pre_p10c_template(cfg)),
                                 "byte for byte the pre-P10c workbook (creation stamp aside)")
        # a clock date on a scheme where nothing is answered by the clocks
        cfg = self._config('P10c T2 dated unkeyed', keyed=False)
        cfg.pb_clock_from = DEC1
        content, _fn = cfg._build_pay_data_template()
        self.assertEqual(_zip_parts(content), _zip_parts(self._pre_p10c_template(cfg)))

    def test_02b_template_still_round_trips(self):
        if not OPENPYXL:
            self.skipTest('openpyxl unavailable')
        cfg = self._config('P10c T2b', sheet='SEVL')
        cfg.pb_clock_from = DEC1
        built = self.Studio.import_mapping_template(cfg.id)
        self.assertTrue(built['ok'], built.get('msg'))
        back = self.Studio.import_mapping_read_headers(cfg.id, built['file_b64'], built['filename'])
        self.assertTrue(back['ok'], back.get('msg'))
        offered = {i['id'] for i in back['left']}
        for rule in cfg.rule_ids.filtered(lambda x: x.column_type == 'input'):
            self.assertIn('c:SEVL|%s' % rule.name, offered)

    # ------------------------------------------------------------------ 3
    def _sources(self, cfg):
        data = self.Studio.get_studio_data(cfg.id)
        return {c['code']: c['source'] for c in data['components']}

    def test_03_source_card_chip(self):
        cfg = self._config('P10c T3')
        # no date yet: no chip anywhere
        self.assertFalse(any('clock' in s for s in self._sources(cfg).values()))
        cfg.pb_clock_from = DEC1
        src = self._sources(cfg)
        day = cfg._pb_clock_from_label()
        for code, key in (('PAIDDAYS', 'clock.paid_days'), ('OVERTIMEH', 'clock.ot_hours'),
                          ('SUNHRS', 'clock.empty')):
            chip = src[code].get('clock')
            self.assertTrue(chip, code)
            self.assertEqual(chip['label'], T_CHIP % day)
            self.assertEqual(chip['from'], '2026-12-01')
            self.assertEqual(chip['key'], key)
            self.assertEqual(chip['hint'], T_HINT % {'fact': cfg._pb_clock_label(key), 'day': day})
        for code in ('EMPCODE', 'MEAL', 'NETPAY'):
            self.assertNotIn('clock', src[code], code)
        # the declared source the card already shows is untouched by the clock
        unkeyed = self._config('P10c T3 plain', keyed=False)
        plain = self._sources(unkeyed)
        for code in ('PAIDDAYS', 'OVERTIMEH', 'SUNHRS'):
            self.assertEqual(src[code]['declared'], plain[code]['declared'])
        # unbinding takes the chip away
        self._rule(cfg, 'PAIDDAYS').clear_source_binding('clock')
        self.assertNotIn('clock', self._sources(cfg)['PAIDDAYS'])

    def test_03b_chip_template_is_in_both_editor_bodies(self):
        xml = open(os.path.join(get_module_path('pb_formula_studio'),
                                'static', 'src', 'xml', 'studio.xml'), encoding='utf-8').read()
        self.assertEqual(xml.count('<t t-call="pb_formula_studio.SrcClockChip"/>'), 2)
        self.assertIn('t-name="pb_formula_studio.SrcClockChip"', xml)
        self.assertIn('selected.source.clock.label', xml)

    # ------------------------------------------------------------------ 4
    def test_04_translations_and_white_label(self):
        try:
            from odoo.tools.translate import PoFileReader
        except ImportError:  # pragma: no cover
            self.skipTest('no PoFileReader')
        want = {'pb_hr_payroll_formula': [T_TEMPLATE], 'pb_formula_studio': [T_CHIP, T_HINT]}
        for module, ids in want.items():
            for lang in ('vi_VN', 'id_ID'):
                path = os.path.join(get_module_path(module), 'i18n', '%s.po' % lang)
                with open(path, 'rb') as fh:
                    rows = [r for r in PoFileReader(fh)]
                got = {r['src']: r for r in rows if r['src'] in ids}
                for msgid in ids:
                    row = got.get(msgid)
                    self.assertTrue(row and row['value'], '%s %s: %s' % (module, lang, msgid))
                    self.assertEqual(row['type'], 'code')
                    self.assertIn('odoo-python', row['comments'])
                    self.assertNotIn('odoo', row['value'].lower().replace('odoo-', ''))
                    for ph in re.findall(r'%\(\w+\)s|%s', msgid):
                        self.assertEqual(row['value'].count(ph), msgid.count(ph), (lang, msgid, ph))
        for msgid in (T_TEMPLATE, T_CHIP, T_HINT):
            self.assertNotIn('odoo', msgid.lower())
