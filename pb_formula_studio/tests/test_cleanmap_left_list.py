# -*- coding: utf-8 -*-
"""CLEANMAP P1 — the Spreadsheet board's left list obeys FROM.

The owner's report, on rize: *"FROM says 'Rize Vietnam Payroll · August 2026 —
pay data' but shows 180 fields. It never had so many. And I still see Salary|A,
A, Salary|B, B although you fixed that."*

Two defects that multiply:

* **CM2** — the left list was a UNION of four lanes and FROM only ever chose
  which one of them a pay run filled. The template file's columns, the run's
  columns and every key the scheme had ever been bound to were all on screen at
  once, under a header naming one pay run.
* **CM1** — `_load_multisheet_data` stores FOUR names per column (the heading,
  `Sheet|heading`, `Sheet|<letter>`, `<letter>`) and writes them in blocks, not
  interleaved. RUNSRC A1's positional walk only understood the interleaved
  shape, so it folded nothing at all on a merged workbook: 43 columns × 4 = 172
  cards, and the reader saw `Salary|A`, `A`, `Salary|B`, `B`.

Everything here is DISPLAY PATH. Nothing stored changes — the aliases stay in
`raw_data_json`, stay resolvable, stay typeable in the search box — and test 13
is the row-count proof that reading the board writes nothing.

Test numbers are the handover's numbers
(docs/handovers/CLEANMAP_P1_LEFT_LIST_HANDOVER.md §5).
"""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCleanmapLeftList(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Line = cls.env['hr.payroll.import.line']

    # ------------------------------------------------------------- fixtures
    _SPECS = [('Employee code', 'MANHANVIEN'),
              ('Employee name', 'TENNHANVIEN'),
              ('Standard working days', 'NGAYCONGCHUAN'),
              ('Basic salary', 'LUONGCOBAN')]

    def _config(self, name, specs=None):
        cfg = self.Config.create({
            'name': name,
            'code': ''.join(ch for ch in name.upper() if ch.isalnum())[:32],
            'country_code': 'VN', 'state': 'active',
        })
        for seq, (label, code) in enumerate(specs or self._SPECS, start=1):
            self.Rule.create({'config_id': cfg.id, 'name': label, 'code': code,
                              'column_type': 'input', 'sequence': seq})
        return cfg

    @staticmethod
    def _merged_keys(sheets):
        """The key order `_load_multisheet_data` really writes.

        `sheets` is `[(sheet_name, [heading…])]`, the first being the main one.
        Main sheet: every heading bare, then every `Sheet|heading`, then per
        column `Sheet|<letter>` + `<letter>`. Secondary sheets: `Sheet|heading`
        with the bare twin when the name is still free, then `Sheet|<letter>`
        only. Verified against rize batch 1128 on 2026-09-19 — 43 headings, 43
        `Salary|heading`, then 44 `Salary|<letter>` + `<letter>` pairs.
        """
        from odoo.addons.pb_hr_payroll_formula.formula_engine.column_manager \
            import index_to_letter
        out, seen = [], set()

        def put(key):
            if key not in seen:
                seen.add(key)
                out.append(key)

        main, main_headings = sheets[0]
        for h in main_headings:
            put(h)
        for h in main_headings:
            put('%s|%s' % (main, h))
        for idx in range(len(main_headings)):
            put('%s|%s' % (main, index_to_letter(idx)))
            put(index_to_letter(idx))
        for sheet, headings in sheets[1:]:
            for h in headings:
                put('%s|%s' % (sheet, h))
                put(h)
            for idx in range(len(headings)):
                put('%s|%s' % (sheet, index_to_letter(idx)))
        return out

    def _batch(self, cfg, raw, name='CLEANMAP · pay data', lines=True):
        batch = self.Batch.create({
            'name': name, 'formula_config_id': cfg.id, 'source_type': 'excel',
        })
        if lines:
            self.Line.create({'batch_id': batch.id,
                              'raw_data_json': json.dumps(raw)})
        return batch

    def _board(self, cfg, batch_id):
        data = self.Studio.import_mapping_data(cfg.id, batch_id)
        self.assertTrue(data.get('ok'), data)
        return data

    @staticmethod
    def _lane(data, title):
        return [c for c in data['left'] if c['group'] == title]

    @staticmethod
    def _lanes(data):
        out = []
        for card in data['left']:
            if card['group'] not in out:
                out.append(card['group'])
        return out

    # =====================================================================
    # 1 — the merge shape folds to one card per real column
    # =====================================================================
    def test_01_multisheet_nine_columns_yield_nine_cards(self):
        headings = ['Employee code', 'Employee name', 'Department',
                    'Standard working days', 'Actual working days',
                    'Basic salary', 'Overtime hours', 'Meal allowance',
                    'Bank account']
        keys = self._merged_keys([('Salary', headings)])
        self.assertEqual(len(keys), 9 * 4,
                         "the merge really does store four names per column")
        cards = self.Studio._column_alias_fold(keys)
        self.assertEqual([c['key'] for c in cards],
                         ['Salary|%s' % h for h in headings])
        self.assertEqual([c['letter'] for c in cards], list('ABCDEFGHI'))

    # =====================================================================
    # 2 — and every other spelling points at that column's card
    # =====================================================================
    def test_02_alias_map_folds_every_spelling(self):
        headings = ['Employee code', 'Basic salary']
        keys = self._merged_keys([('Salary', headings)])
        canon = self.Studio._column_alias_map(keys)
        for spelling in ('Employee code', 'Salary|A', 'A', 'Salary|Employee code'):
            self.assertEqual(canon.get(spelling), 'Salary|Employee code',
                             "%r is that column" % spelling)
        for spelling in ('Basic salary', 'Salary|B', 'B'):
            self.assertEqual(canon.get(spelling), 'Salary|Basic salary')

    # =====================================================================
    # 3 — the same heading on two sheets stays tellable apart
    # =====================================================================
    def test_03_same_heading_on_two_sheets_keeps_both_cards(self):
        keys = self._merged_keys([('Salary', ['Employee code', 'Total']),
                                  ('Bonus', ['Employee code', 'Total'])])
        cfg = self._config('CLEANMAP Two Sheets')
        batch = self._batch(cfg, {k: None for k in keys})
        cards = self._lane(self._board(cfg, batch.id), batch.name)
        self.assertIn('c:Salary|Total', {c['id'] for c in cards})
        self.assertIn('c:Bonus|Total', {c['id'] for c in cards})
        totals = [c['label'] for c in cards if c['id'].endswith('|Total')]
        self.assertEqual(sorted(totals), ['Bonus|Total', 'Salary|Total'],
                         "two cards that would read the same get the sheet back")

    # =====================================================================
    # 4 — a secondary sheet qualifies its letters and nothing else
    # =====================================================================
    def test_04_secondary_sheet_folds_too(self):
        keys = self._merged_keys([('Salary', ['Employee code', 'Basic salary']),
                                  ('Extra', ['Meal allowance', 'Phone'])])
        cards = self.Studio._column_alias_fold(keys)
        self.assertEqual([c['key'] for c in cards],
                         ['Salary|Employee code', 'Salary|Basic salary',
                          'Extra|Meal allowance', 'Extra|Phone'])
        canon = self.Studio._column_alias_map(keys)
        self.assertEqual(canon.get('Extra|A'), 'Extra|Meal allowance')
        self.assertEqual(canon.get('Phone'), 'Extra|Phone')

    # =====================================================================
    # 5 — the interleaved shape is untouched
    # =====================================================================
    def test_05_single_sheet_shape_is_byte_identical(self):
        """The old walk, unchanged — `test_runsrc_left_columns` 01-04 and 06-12
        are the rest of this test."""
        raw = self.Batch._raw_data_from_row(
            ['Employee code', 'Employee name', 'Basic salary'],
            ['E001', 'Nguyen Van A', 12500000])
        keys = list(raw)
        self.assertFalse(self.Studio._keys_are_multisheet_shape(keys))
        self.assertEqual(
            [c['key'] for c in self.Studio._column_alias_fold(keys)],
            ['Employee code', 'Employee name', 'Basic salary'])
        self.assertEqual(self.Studio._column_alias_map(keys).get('B'),
                         'Employee name')

    # =====================================================================
    # 6 — FROM a pay run means ONLY that pay run
    # =====================================================================
    def test_06_from_a_pay_run_draws_only_that_file(self):
        keys = self._merged_keys([('Salary', [lbl for lbl, _c in self._SPECS])])
        cfg = self._config('CLEANMAP Only This')
        # a stored template file AND a history value, both of which used to be
        # drawn beside the run's columns whatever FROM said
        cfg.write({'import_sample_filename': 'last-year.xlsx',
                   'import_sample_columns_json': json.dumps(
                       [{'key': 'Ghost heading', 'sheet': '', 'header': 'Ghost heading',
                         'letter': 'A', 'sample': '', 'preferred': True}])})
        batch = self._batch(cfg, {k: None for k in keys})
        for seq, rule in enumerate(cfg.rule_ids.sorted('sequence')):
            rule.set_source_binding('excel', 'Salary|%s' % self._SPECS[seq][0],
                                    origin='board')
        data = self._board(cfg, batch.id)
        self.assertEqual(self._lanes(data),
                         [batch.name, 'From this pay run'],
                         "one file source on screen, plus the run's own lane")
        self.assertEqual(len(self._lane(data, batch.name)), 4)
        self.assertNotIn('c:Ghost heading', {c['id'] for c in data['left']})

    # =====================================================================
    # 7 — a column the file has lost says so, once
    # =====================================================================
    def test_07_a_lost_column_gets_one_honest_card(self):
        keys = self._merged_keys([('Salary', [lbl for lbl, _c in self._SPECS])])
        cfg = self._config('CLEANMAP Ghost')
        batch = self._batch(cfg, {k: None for k in keys})
        rules = cfg.rule_ids.sorted('sequence')
        rules[0].set_source_binding('excel', 'Salary|Employee code', origin='board')
        rules[1].set_source_binding('excel', 'Ghost Column', origin='board')
        data = self._board(cfg, batch.id)
        lost = self._lane(data, 'Mapped, but not in this file')
        self.assertEqual([c['id'] for c in lost], ['c:Ghost Column'])
        self.assertEqual(lost[0]['sublabel'], 'this file has no such column')
        self.assertTrue(lost[0]['meta'].get('orphan'))
        wire = [w for w in data['wires']
                if w['kind'] == 'mapping' and w['ref'] == rules[1].id]
        self.assertEqual([w['leftId'] for w in wire], ['c:Ghost Column'])

    # =====================================================================
    # 8 — a binding written with another spelling is the same column
    # =====================================================================
    def test_08_a_bare_heading_binding_lands_on_the_sheet_card(self):
        keys = self._merged_keys([('Salary', [lbl for lbl, _c in self._SPECS])])
        cfg = self._config('CLEANMAP Bare')
        batch = self._batch(cfg, {k: None for k in keys})
        rule = cfg.rule_ids.filtered(lambda r: r.code == 'LUONGCOBAN')
        rule.set_source_binding('excel', 'Basic salary', origin='board')
        data = self._board(cfg, batch.id)
        wire = [w for w in data['wires']
                if w['kind'] == 'mapping' and w['ref'] == rule.id]
        self.assertEqual([w['leftId'] for w in wire], ['c:Salary|Basic salary'],
                         "the wire lands on the card of the column it names")
        self.assertEqual(self._lane(data, 'Mapped, but not in this file'), [])
        self.assertEqual(
            [w for w in data['wires'] if w['kind'] == 'suggestion'
             and w['leftId'] == 'c:Salary|Basic salary'], [],
            "no suggestion may be drawn on top of a column's own wire")
        # and nothing stored moved
        self.assertEqual(rule.source_binding_key, 'Basic salary')

    # =====================================================================
    # 9 — no wire without a card, on either shape and on the template file
    # =====================================================================
    def test_09_every_wire_starts_from_a_card(self):
        multi = self._merged_keys([('Salary', [lbl for lbl, _c in self._SPECS])])
        flat = self.Batch._raw_data_from_row(
            [lbl for lbl, _c in self._SPECS], ['E001', 'Nguyen Van A', 26, 12500000])
        cfg = self._config('CLEANMAP Wires')
        rules = cfg.rule_ids.sorted('sequence')
        rules[0].set_source_binding('excel', 'Employee code', origin='board')
        rules[1].set_source_binding('excel', 'B', origin='board')
        rules[2].set_source_binding('excel', 'Salary|Standard working days',
                                    origin='board')
        rules[3].data_source_field = 'Nowhere at all'
        cfg.write({
            'import_sample_filename': 'cleanmap.xlsx',
            'import_sample_columns_json': json.dumps([
                {'key': 'Salary|%s' % lbl, 'sheet': 'Salary', 'header': lbl,
                 'letter': chr(65 + i), 'sample': '', 'preferred': True}
                for i, (lbl, _c) in enumerate(self._SPECS)
            ] + [
                {'key': lbl, 'sheet': '', 'header': lbl, 'letter': chr(65 + i),
                 'sample': '', 'preferred': False}
                for i, (lbl, _c) in enumerate(self._SPECS)
            ] + [
                {'key': chr(65 + i), 'sheet': '', 'header': '',
                 'letter': chr(65 + i), 'sample': '', 'preferred': False}
                for i in range(len(self._SPECS))
            ]),
        })
        b_multi = self._batch(cfg, {k: None for k in multi}, name='CLEANMAP · merged')
        b_flat = self._batch(cfg, flat, name='CLEANMAP · flat')
        for from_id in (b_multi.id, b_flat.id, 'sample'):
            data = self._board(cfg, from_id)
            ids = {c['id'] for c in data['left']}
            for wire in data['wires']:
                self.assertIn(wire['leftId'], ids,
                              "%s has no card on FROM=%s" % (wire['leftId'], from_id))

    # =====================================================================
    # 10 — the template file is a FROM entry
    # =====================================================================
    def test_10_the_template_file_is_a_from_entry(self):
        cfg = self._config('CLEANMAP Sample FROM')
        cfg.write({
            'import_sample_filename': 'august.xlsx',
            'import_sample_columns_json': json.dumps([
                {'key': 'Employee code', 'sheet': '', 'header': 'Employee code',
                 'letter': 'A', 'sample': 'E001', 'preferred': True},
                {'key': 'A', 'sheet': '', 'header': '', 'letter': 'A',
                 'sample': 'E001', 'preferred': False},
            ]),
        })
        batch = self._batch(cfg, {'Whatever': 1}, name='CLEANMAP · a run')
        data = self._board(cfg, 'sample')       # no exception from the int cast
        self.assertEqual(data['context_id'], 'sample')
        self.assertEqual(self._lanes(data),
                         ['august.xlsx', 'From this pay run'])
        self.assertEqual([c['id'] for c in self._lane(data, 'august.xlsx')],
                         ['c:Employee code'])
        self.assertNotIn(batch.name, self._lanes(data))
        self.assertEqual(len(self._lane(data, 'From this pay run')), 6)

    # =====================================================================
    # 11 — a database with no file at all keeps J2's promise
    # =====================================================================
    def test_11_no_file_anywhere_still_shows_what_the_scheme_reads(self):
        # a load with no rows in it is "no file on this board" — and it is the
        # only way to say so on a database that already has other people's
        # batches on it (`contexts` is every batch there is, CM4)
        cfg = self._config('CLEANMAP No File')
        empty = self._batch(cfg, {}, name='CLEANMAP · nothing loaded', lines=False)
        rules = cfg.rule_ids.sorted('sequence')
        rules[0].set_source_binding('excel', 'Employee code', origin='board')
        rules[1].data_source_field = 'Employee name'
        data = self._board(cfg, empty.id)
        lanes = self._lanes(data)
        self.assertIn('Already used by this scheme', lanes)
        self.assertIn("From this scheme's history", lanes)
        ids = {c['id'] for c in data['left']}
        for wire in data['wires']:
            self.assertIn(wire['leftId'], ids)

    # =====================================================================
    # 12 — and the entry only exists when the file does
    # =====================================================================
    def test_12_the_sample_entry_appears_only_with_a_sample(self):
        cfg = self._config('CLEANMAP Contexts')
        batch = self._batch(cfg, {'Employee code': 'E001'})
        data = self._board(cfg, batch.id)
        self.assertNotEqual((data['contexts'] or [{}])[0].get('kind'), 'sample')
        cfg.write({
            'import_sample_filename': 'later.xlsx',
            'import_sample_columns_json': json.dumps(
                [{'key': 'Employee code', 'sheet': '', 'header': 'Employee code',
                  'letter': 'A', 'sample': '', 'preferred': True}]),
        })
        data = self._board(cfg, batch.id)
        self.assertEqual(data['contexts'][0]['kind'], 'sample')
        self.assertEqual(data['contexts'][0]['id'], 'sample')
        self.assertEqual(data['contexts'][0]['name'], 'later.xlsx — template file')
        self.assertTrue(all(c.get('kind') == 'batch' for c in data['contexts'][1:]))

    # =====================================================================
    # 13 — reading the board writes nothing, on every FROM
    # =====================================================================
    def test_13_the_board_writes_nothing_on_any_from(self):
        keys = self._merged_keys([('Salary', [lbl for lbl, _c in self._SPECS])])
        cfg = self._config('CLEANMAP Neutral')
        cfg.write({
            'import_sample_filename': 'neutral.xlsx',
            'import_sample_columns_json': json.dumps(
                [{'key': 'Salary|Employee code', 'sheet': 'Salary',
                  'header': 'Employee code', 'letter': 'A', 'sample': '',
                  'preferred': True}]),
        })
        batch = self._batch(cfg, {k: None for k in keys})
        cfg.rule_ids.sorted('sequence')[0].set_source_binding(
            'excel', 'Employee code', origin='board')
        self.env.flush_all()

        def census():
            self.env.flush_all()
            self.env.cr.execute("""
                SELECT (SELECT count(*) FROM hr_formula_rule),
                       (SELECT count(*) FROM hr_formula_rule_source),
                       (SELECT count(*) FROM hr_payroll_import_line),
                       (SELECT md5(coalesce(string_agg(
                            coalesce(source_binding_key, '') , '|'
                            ORDER BY id), ''))
                          FROM hr_formula_rule)
            """)
            return self.env.cr.fetchone()

        before = census()
        for from_id in (False, batch.id, 'sample', 'nonsense', 0):
            self.Studio.import_mapping_data(cfg.id, from_id)
        self.assertEqual(census(), before,
                         "reading the board changed a stored row")

    # =====================================================================
    # 14 — the six things the run knows are on every FROM
    # =====================================================================
    def test_14_the_pay_run_lane_is_on_every_from(self):
        keys = self._merged_keys([('Salary', ['Employee code'])])
        cfg = self._config('CLEANMAP Run Lane')
        cfg.write({
            'import_sample_filename': 'runlane.xlsx',
            'import_sample_columns_json': json.dumps(
                [{'key': 'Employee code', 'sheet': '', 'header': 'Employee code',
                  'letter': 'A', 'sample': '', 'preferred': True}]),
        })
        batch = self._batch(cfg, {k: None for k in keys})
        for from_id in (False, batch.id, 'sample'):
            data = self._board(cfg, from_id)
            run = [c for c in data['left'] if c['id'].startswith('p:')]
            self.assertEqual(len(run), 6,
                             "FROM=%s lost the pay-run lane" % from_id)
