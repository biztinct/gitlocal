# -*- coding: utf-8 -*-
"""RUNSRC Phase A — one card per real column, and no invented 85%.

The Spreadsheet board's left column drew a card for BOTH spellings of every
column a loaded pay file carries, because `_raw_data_from_row` stores each
column twice — under its heading and under its bare column letter. A nine
column file therefore rendered eighteen cards, half of them called "A", "B",
"C". Separately, a one-character key substring-matched component codes
(`'a' in 'manhanvien'`) and strung the canvas with orange 85% suggestion wires
that were not matches at all.

Both defects are display-side. The letter aliases in the stored data are
load-bearing — the resolver's fallback reads them and compiled formulas address
components by letter — so nothing here narrows them, and `test_11_*` is the
assertion that says so.

Test numbers are the handover's numbers (docs/handovers/RUNSRC_PA_ONE_CARD_PER_COLUMN.md).
"""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRunsrcLeftColumns(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Line = cls.env['hr.payroll.import.line']

    # ------------------------------------------------------------- fixtures
    _DEFAULT_SPECS = [('Employee code', 'MANHANVIEN'),
                      ('Employee name', 'TENNHANVIEN'),
                      ('Standard working days', 'NGAYCONGCHUAN'),
                      ('Basic salary', 'LUONGCOBAN')]

    def _config(self, name, specs=None):
        cfg = self.Config.create({
            'name': name,
            'code': ''.join(ch for ch in name.upper() if ch.isalnum())[:32],
            'country_code': 'VN', 'state': 'active',
        })
        for seq, (label, code) in enumerate(specs or self._DEFAULT_SPECS, start=1):
            self.Rule.create({'config_id': cfg.id, 'name': label, 'code': code,
                              'column_type': 'input', 'sequence': seq})
        return cfg

    def _raw(self, headers, row):
        """The dict the LOADER writes — both spellings, from its own writer."""
        return self.Batch._raw_data_from_row(headers, row)

    def _batch(self, cfg, raw, name='RUNSRC A · pay data'):
        batch = self.Batch.create({
            'name': name, 'formula_config_id': cfg.id, 'source_type': 'excel',
        })
        self.Line.create({'batch_id': batch.id,
                          'raw_data_json': json.dumps(raw)})
        return batch

    def _board(self, cfg, batch):
        data = self.Studio.import_mapping_data(cfg.id, batch.id)
        self.assertTrue(data.get('ok'), data)
        return data

    def _file_cards(self, data, batch):
        return [c for c in data['left'] if c['group'] == batch.name]

    # =====================================================================
    # 1 — a nine-column file is nine cards
    # =====================================================================
    def test_01_nine_columns_yield_nine_cards(self):
        """Test 1 — a 9-column header/letter dict yields 9 cards, none a letter."""
        headers = ['Employee code', 'Employee name', 'Department',
                   'Standard working days', 'Actual working days',
                   'Basic salary', 'Overtime hours', 'Meal allowance',
                   'Bank account']
        row = ['E001', 'Nguyen Van A', 'KHOI', 26, 24,
               12500000, 8, 730000, '0123456789']
        raw = self._raw(headers, row)
        self.assertEqual(len(raw), 18,
                         "the loader still stores both spellings of every column")
        cfg = self._config('RUNSRC Nine')
        batch = self._batch(cfg, raw)
        cards = self._file_cards(self._board(cfg, batch), batch)
        self.assertEqual([c['label'] for c in cards], headers)
        self.assertEqual(len(cards), 9)
        for c in cards:
            self.assertFalse(len(c['label']) <= 3 and c['label'].isupper()
                             and c['label'].isalpha(),
                             "no card may be a bare column letter: %r" % c['label'])

    # =====================================================================
    # 2 — the aliases are still reachable
    # =====================================================================
    def test_02_aliases_stay_reachable_and_bind_to_one_card(self):
        """Test 2 — the search box still takes a letter, and binding to 'A'
        puts exactly one 'A' card back on the board."""
        cfg = self._config('RUNSRC Reach')
        raw = self._raw(['Employee code', 'Basic salary'], ['E001', 12500000])
        batch = self._batch(cfg, raw)
        data = self._board(cfg, batch)
        self.assertTrue(data['can_add'],
                        "a column that has no card is still typeable")
        self.assertNotIn('c:A', {c['id'] for c in data['left']})

        rule = cfg.rule_ids.filtered(lambda r: r.code == 'LUONGCOBAN')
        rule.set_source_binding('excel', 'A', origin='board')
        data = self._board(cfg, batch)
        a_cards = [c for c in data['left'] if c['id'] == 'c:A']
        self.assertEqual(len(a_cards), 1,
                         "the bound letter comes back, once")
        self.assertIn('c:A', {w['leftId'] for w in data['wires']
                              if w['kind'] == 'mapping'})

    # =====================================================================
    # 3 / 4 / 5 / 6 — the shapes the walk must not mistake
    # =====================================================================
    def test_03_a_genuine_A_heading_survives(self):
        """Test 3 — a file whose headings really are 'A' and 'B' keeps both."""
        raw = self._raw(['A', 'B'], [1, 2])
        self.assertEqual(list(raw), ['A', 'B'],
                         "the writer adds no second spelling for these")
        cfg = self._config('RUNSRC Literal')
        batch = self._batch(cfg, raw)
        cards = self._file_cards(self._board(cfg, batch), batch)
        self.assertEqual([c['label'] for c in cards], ['A', 'B'])

    def test_04_a_blank_heading_keeps_its_letter_card(self):
        """Test 4 — a column with no heading keeps the only name it has."""
        raw = self._raw(['Code', ''], ['E001', 12500000])
        cfg = self._config('RUNSRC Blank')
        batch = self._batch(cfg, raw)
        cards = self._file_cards(self._board(cfg, batch), batch)
        self.assertEqual([c['label'] for c in cards], ['Code', 'B'],
                         "the nameless column is still on the board, as B")

    def test_05_multisheet_dict_rows_fold_to_one_card_per_column(self):
        """Test 5 — REWRITTEN by CLEANMAP P1 (see
        docs/handovers/CLEANMAP_P1_LEFT_LIST_HANDOVER.md §4.3).

        This used to assert the opposite — "a row that arrives as a dict has no
        aliases; keep every key" — and pinned RUNSRC A's known gap on purpose.
        It was wrong about the merge: `_load_multisheet_data` writes FOUR names
        per column, and on rize that drew 174 cards for a 43-column workbook.
        A dict row with no aliases in it still keeps every key, which is what
        this fixture is; the assertion that moved is about the CARD, which is
        now the sheet-qualified spelling per real column.
        """
        raw = {'SEVL|Employee code': 'E001', 'SEVL|Basic salary': 12500000,
               'EXTRA|Meal allowance': 730000}
        self.assertEqual(self.Batch._raw_data_from_row([], raw), raw)
        cfg = self._config('RUNSRC Multi')
        batch = self._batch(cfg, raw)
        cards = self._file_cards(self._board(cfg, batch), batch)
        self.assertEqual([c['id'] for c in cards],
                         ['c:SEVL|Employee code', 'c:SEVL|Basic salary',
                          'c:EXTRA|Meal allowance'],
                         "one card per real column, keyed as the resolver reads it")
        self.assertEqual([c['label'] for c in cards],
                         ['Employee code', 'Basic salary', 'Meal allowance'])

    def test_06_sheet_qualified_aliases_are_stripped(self):
        """Test 6 — 'SEVL|Employee code' keeps a card, 'SEVL|A' does not.

        The card's KEY is the sheet-qualified one (that is what the resolver
        reads); its LABEL is the heading, because `SEVL|` in front of every
        heading is a prefix the reader has to look past 43 times — RUNSRC A1b,
        `_import_left_columns.add`. This test asserted the label and was red
        from A1b until CLEANMAP P1 spotted it; the assertion now names both.
        """
        raw = {'SEVL|Employee code': 'E001', 'SEVL|A': 'E001',
               'SEVL|Basic salary': 12500000, 'SEVL|B': 12500000}
        cfg = self._config('RUNSRC Sheeted')
        batch = self._batch(cfg, raw)
        cards = self._file_cards(self._board(cfg, batch), batch)
        self.assertEqual([c['id'] for c in cards],
                         ['c:SEVL|Employee code', 'c:SEVL|Basic salary'])
        self.assertEqual([c['label'] for c in cards],
                         ['Employee code', 'Basic salary'])
        # and the bare-letter shape the single-sheet writer produces
        raw2 = self._raw(['SEVL|Employee code', 'SEVL|Basic salary'],
                         ['E001', 12500000])
        batch2 = self._batch(cfg, raw2, name='RUNSRC A · sheet two')
        cards2 = self._file_cards(self._board(cfg, batch2), batch2)
        self.assertEqual([c['id'] for c in cards2],
                         ['c:SEVL|Employee code', 'c:SEVL|Basic salary'])
        self.assertEqual([c['label'] for c in cards2],
                         ['Employee code', 'Basic salary'])

    # =====================================================================
    # 7 — the card says what is in the column
    # =====================================================================
    def test_07_a_kept_card_carries_a_sample_value(self):
        """Test 7 — 'e.g. 12,500,000', and an empty column says so."""
        raw = self._raw(['Employee code', 'Basic salary', 'Bonus'],
                        ['E001', 12500000, None])
        cfg = self._config('RUNSRC Sample')
        batch = self._batch(cfg, raw)
        cards = {c['label']: c for c in
                 self._file_cards(self._board(cfg, batch), batch)}
        self.assertEqual(cards['Basic salary']['sublabel'], 'e.g. 12,500,000')
        self.assertEqual(cards['Basic salary']['meta']['letter'], 'B')
        self.assertEqual(cards['Bonus']['sublabel'], 'no value in the first row')
        self.assertNotIn('False', cards['Bonus']['sublabel'])

    # =====================================================================
    # 8 / 9 / 10 — the suggestion floor
    # =====================================================================
    def test_08_a_column_letter_never_suggests(self):
        """Test 8 — with a component coded MANHANVIEN, the key 'A' is silent."""
        self.assertEqual(
            self.Studio._suggest_confidence('a', 'manhanvien', 'employeecode'),
            0.0, "'a' in 'manhanvien' is arithmetic, not evidence")
        cfg = self._config('RUNSRC Floor')
        raw = self._raw(['Ma NV', 'Ho ten', 'Ngay cong'], ['E001', 'A', 26])
        batch = self._batch(cfg, raw)
        data = self._board(cfg, batch)
        letters = {'c:%s' % chr(c) for c in range(ord('A'), ord('Z') + 1)}
        bogus = [w for w in data['wires']
                 if w['kind'] == 'suggestion' and w['leftId'] in letters]
        self.assertEqual(bogus, [], "no wire may start from a bare letter")

    def test_09_a_four_character_substring_still_suggests(self):
        """Test 9 — 'Basic' onto BASICSAL still scores 0.85."""
        self.assertEqual(self.Studio._suggest_confidence('basic', 'basicsal', ''),
                         0.85)
        cfg = self._config('RUNSRC Real', specs=[('Employee code', 'EMPCODE'),
                                                 ('Basic salary', 'BASICSAL')])
        raw = self._raw(['Employee code', 'Basic'], ['E001', 12500000])
        batch = self._batch(cfg, raw)
        data = self._board(cfg, batch)
        hit = [w for w in data['wires'] if w['kind'] == 'suggestion'
               and w['leftId'] == 'c:Basic']
        self.assertEqual(len(hit), 1, data['wires'])
        self.assertEqual(hit[0]['confidence'], 0.85)

    def test_10_an_exact_one_letter_match_still_scores_one(self):
        """Test 10 — a component genuinely coded 'A', fed by a column 'A'."""
        self.assertEqual(self.Studio._suggest_confidence('a', 'a', 'anything'),
                         1.0)
        cfg = self._config('RUNSRC Exact', specs=[('Column A', 'A'),
                                                  ('Column B', 'B')])
        raw = self._raw(['A', 'B'], [1, 2])
        batch = self._batch(cfg, raw)
        data = self._board(cfg, batch)
        hit = {w['leftId']: w for w in data['wires'] if w['kind'] == 'suggestion'}
        self.assertIn('c:A', hit)
        self.assertEqual(hit['c:A']['confidence'], 1.0)

    # =====================================================================
    # 11 — pay-neutrality
    # =====================================================================
    def test_11_the_board_writes_nothing_and_the_letters_still_resolve(self):
        """Test 11 — the stored aliases, the resolver's letter lookup and every
        rule field are exactly as they were after the board has been read."""
        cfg = self._config('RUNSRC Neutral')
        raw = self._raw(['Employee code', 'Employee name',
                         'Standard working days', 'Basic salary'],
                        ['E001', 'Nguyen Van A', 26, 12500000])
        batch = self._batch(cfg, raw)
        rule = cfg.rule_ids.filtered(lambda r: r.code == 'LUONGCOBAN')
        rule.column_letter = 'D'

        before = cfg.rule_ids.read()
        stored_before = self.Line.search([('batch_id', '=', batch.id)]).raw_data_json
        value_before = batch._get_rule_raw_value(raw, rule)

        self.Studio.import_mapping_data(cfg.id, batch.id)
        self.env.flush_all()

        self.assertEqual(cfg.rule_ids.read(), before,
                         "reading the board changed a component")
        self.assertEqual(
            self.Line.search([('batch_id', '=', batch.id)]).raw_data_json,
            stored_before, "reading the board changed the stored row")
        self.assertEqual(batch._get_rule_raw_value(raw, rule), value_before)
        self.assertEqual(value_before, (12500000, True),
                         "column D still feeds the component bound to it")
        self.assertEqual(json.loads(stored_before).get('D'), 12500000,
                         "the letter alias is still in the stored data")

    # =====================================================================
    # 12 — no wire without a card
    # =====================================================================
    def test_12_every_wire_starts_from_a_card(self):
        """Test 12 — a wire whose leftId has no card is the canvas-crash shape."""
        cfg = self._config('RUNSRC Wires')
        raw = self._raw(['Employee code', 'Employee name',
                         'Standard working days', 'Basic salary'],
                        ['E001', 'Nguyen Van A', 26, 12500000])
        batch = self._batch(cfg, raw)
        rules = cfg.rule_ids.sorted('sequence')
        rules[0].set_source_binding('excel', 'Employee code', origin='board')
        rules[1].set_source_binding('excel', 'B', origin='board')
        rules[2].data_source_field = 'Standard working days'
        data = self._board(cfg, batch)
        ids = {c['id'] for c in data['left']}
        for wire in data['wires']:
            self.assertIn(wire['leftId'], ids,
                          "%s has no card on the board" % wire['leftId'])
        self.assertIn('c:B', ids, "a component bound to a letter keeps its card")
        self.assertEqual(len([c for c in data['left'] if c['id'] == 'c:B']), 1)
