# -*- coding: utf-8 -*-
"""RUNSRC Phase C — the mapping board's "From this pay run" lane.

Six cards carrying the run's real numbers, drawable and erasable like any other
wire. And the client-side vocabulary finally learning `period`: the server has
written `src='period'` since the pay period became a source, while every board
rendered the chip as **"No source"** and `srcDisagrees` reported *"Last run used
a different source: No source"* about a component that was working perfectly.

Test numbers are the handover's numbers
(docs/handovers/RUNSRC_PC_FROM_THIS_PAY_RUN.md §7).
"""
import json
import os
import re

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRunsrcPcBoardLane(TransactionCase):

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
              ('Standard working days', 'NGAYCONGCHUAN'),
              ('Basic salary', 'LUONGCOBAN')]

    def _world(self, tag):
        cfg = self.Config.create({
            'name': 'RUNSRC C %s' % tag, 'code': 'RCB%s' % tag.upper(),
            'country_code': 'VN', 'state': 'active'})
        rules = {}
        for seq, (label, code) in enumerate(self._SPECS, start=1):
            rules[code] = self.Rule.create({
                'config_id': cfg.id, 'name': label, 'code': code,
                'column_type': 'input', 'sequence': seq})
        batch = self.Batch.create({
            'name': 'RUNSRC C %s · pay data' % tag, 'source_type': 'excel',
            'formula_config_id': cfg.id,
            'date_from': '2026-08-01', 'date_to': '2026-08-31'})
        raw = self.Batch._raw_data_from_row(
            ['Employee code', 'Basic salary'], ['E1', 12500000])
        self.Line.create({'batch_id': batch.id,
                          'raw_data_json': json.dumps(raw)})
        return cfg, rules, batch

    def _board(self, cfg, batch):
        data = self.Studio.import_mapping_data(cfg.id, batch.id)
        self.assertTrue(data.get('ok'), data)
        return data

    @staticmethod
    def _run_cards(data):
        return [c for c in data['left'] if str(c['id']).startswith('p:')]

    # =====================================================================
    # 11 — the board offers six cards, with the real numbers on them
    # =====================================================================
    def test_11_six_cards_carrying_the_runs_own_numbers(self):
        """Test 11 — six `p:` cards, and standard working days reads e.g. 21."""
        cfg, rules, batch = self._world('cards')
        data = self._board(cfg, batch)
        cards = self._run_cards(data)
        self.assertEqual(
            [c['id'] for c in cards],
            ['p:PAYMONTH', 'p:PAYYEAR', 'p:PAYDAYS', 'p:STDDAYS',
             'p:STARTDAY', 'p:ENDDAY'])
        by_id = {c['id']: c for c in cards}
        self.assertEqual(by_id['p:STDDAYS']['label'], 'Standard working days',
                         "plain words on the card, never the code")
        self.assertEqual(by_id['p:STDDAYS']['sublabel'], 'e.g. 21',
                         "August 2026 is 21 Mon-Fri days — a lane that says "
                         "'Standard working days' with no value is a lane "
                         "nobody trusts enough to wire")
        self.assertEqual(by_id['p:PAYMONTH']['sublabel'], 'e.g. 8')
        self.assertEqual(by_id['p:PAYYEAR']['sublabel'], 'e.g. 2026')
        self.assertEqual(by_id['p:PAYDAYS']['sublabel'], 'e.g. 31')
        self.assertEqual(by_id['p:ENDDAY']['sublabel'], 'e.g. 31')
        self.assertEqual(len({c['group'] for c in cards}), 1,
                         "one lane, one heading")
        lane = cards[0]['group']
        self.assertIn('pay run', lane)
        self.assertIn('August 2026', lane)
        # and the number a user typed on the run is what the card shows
        batch.pb_std_work_days = 20
        by_id = {c['id']: c for c in self._run_cards(self._board(cfg, batch))}
        self.assertEqual(by_id['p:STDDAYS']['sublabel'], 'e.g. 20')

    def test_11b_no_period_means_a_meaning_and_no_number(self):
        """Test 11b (RS8) — a lane full of zeroes would state a falsehood."""
        cfg, rules, batch = self._world('nodates')
        batch.write({'date_from': False, 'date_to': False})
        cards = self._run_cards(self._board(cfg, batch))
        self.assertEqual(len(cards), 6, "the lane still appears")
        self.assertTrue(all(c['sublabel'] == 'the run has no period yet'
                            for c in cards))
        self.assertFalse(any('0' == c['sublabel'] for c in cards))

    # =====================================================================
    # 12 — drawing and erasing round-trips
    # =====================================================================
    def test_12_draw_and_erase_round_trip(self):
        """Test 12 — create with `p:STDDAYS`, see the wire, delete, it is gone."""
        cfg, rules, batch = self._world('draw')
        rule = rules['NGAYCONGCHUAN']
        res = self.Studio.import_mapping_create(
            cfg.id, batch.id, 'p:STDDAYS', rule.id)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(rule.period_key, 'STDDAYS')
        data = self._board(cfg, batch)
        wire = [w for w in data['wires'] if w['rightId'] == rule.id]
        self.assertEqual(len(wire), 1)
        self.assertEqual(wire[0]['leftId'], 'p:STDDAYS')
        self.assertEqual(wire[0]['state'], 'accepted')
        self.assertEqual(wire[0]['ref'], 'p:%s' % rule.id,
                         "the ref names WHICH wire, so cutting the run does "
                         "not take a column with it")
        # the component card says Pay period
        card = [c for c in data['right'] if c['id'] == rule.id][0]
        self.assertEqual(card['srcKind'], 'period')
        self.assertEqual([k['kind'] for k in card['srcKinds']], ['period'])
        self.assertEqual(card['srcKinds'][0]['label'],
                         'Standard working days')
        self.assertIn('Pay period', card['srcNote'])
        # and erasing it
        self.assertTrue(self.Studio.import_mapping_delete(
            'p:%s' % rule.id).get('ok'))
        rule.invalidate_recordset()
        self.assertFalse(rule.period_key)
        data = self._board(cfg, batch)
        self.assertFalse([w for w in data['wires']
                          if str(w['leftId']).startswith('p:')])

    def test_12b_a_key_the_run_cannot_answer_is_refused_by_the_board(self):
        """Test 12b — wrong-type in, refusal out; nothing is written."""
        cfg, rules, batch = self._world('refuse')
        rule = rules['NGAYCONGCHUAN']
        res = self.Studio.import_mapping_create(
            cfg.id, batch.id, 'p:BANANAS', rule.id)
        self.assertFalse(res.get('ok'))
        self.assertTrue(res.get('msg'))
        self.assertNotIn('Odoo', res['msg'])
        rule.invalidate_recordset()
        self.assertFalse(rule.period_key)

    def test_12c_cutting_the_column_leaves_the_run_reading(self):
        """Test 12c — two wires, two cuts. Neither takes the other with it."""
        cfg, rules, batch = self._world('twocut')
        rule = rules['NGAYCONGCHUAN']
        self.Studio.import_mapping_create(
            cfg.id, batch.id, 'c:Standard working days', rule.id)
        self.Studio.import_mapping_create(
            cfg.id, batch.id, 'p:STDDAYS', rule.id)
        self.Studio.import_mapping_delete(rule.id)
        rule.invalidate_recordset()
        self.assertEqual(rule.period_key, 'STDDAYS',
                         "cutting the column must not silently remove the run")
        self.assertFalse(rule.source_binding)

    # =====================================================================
    # 13 — wire integrity (Phase A's test 12, extended)
    # =====================================================================
    def test_13_every_wire_ends_on_a_card_that_exists(self):
        """Test 13 — every `leftId` is among the returned `left` ids."""
        cfg, rules, batch = self._world('integrity')
        rules['NGAYCONGCHUAN'].set_source_binding('pay_run', 'STDDAYS')
        rules['LUONGCOBAN'].set_source_binding('excel', 'Basic salary')
        data = self._board(cfg, batch)
        left_ids = {str(c['id']) for c in data['left']}
        right_ids = {c['id'] for c in data['right']}
        for wire in data['wires']:
            self.assertIn(str(wire['leftId']), left_ids,
                          "a wire whose leftId has no card is the MAPFIX-D "
                          "canvas crash: %s" % wire)
            self.assertIn(wire['rightId'], right_ids, wire)
        self.assertEqual(len(left_ids), len(data['left']), "no duplicate ids")

    # =====================================================================
    # 14 — two sources, two chips
    # =====================================================================
    def test_14_two_sources_render_two_chips(self):
        """Test 14 — a column and the run on one card, both shown, no raise."""
        cfg, rules, batch = self._world('twochips')
        rule = rules['NGAYCONGCHUAN']
        rule.set_source_binding('excel', 'Standard working days')
        rule.set_source_binding('pay_run', 'STDDAYS')
        data = self._board(cfg, batch)
        card = [c for c in data['right'] if c['id'] == rule.id][0]
        self.assertEqual([k['kind'] for k in card['srcKinds']],
                         ['excel', 'period'])
        self.assertEqual([k['rank'] for k in card['srcKinds']], [1, 2],
                         "the reader is told the ORDER this component reads in")
        self.assertIn('Spreadsheet', card['srcNote'])
        self.assertIn('Pay period', card['srcNote'])
        wires = sorted(w['leftId'] for w in data['wires']
                       if w['rightId'] == rule.id)
        self.assertEqual(wires, ['c:Standard working days', 'p:STDDAYS'])

    # =====================================================================
    # 15 — the chip says "Pay period", not "No source"
    # =====================================================================
    def test_15_the_client_vocabulary_knows_the_pay_period(self):
        """Test 15 — `source_vocab.js` learns `period`, word for word."""
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, 'static', 'src', 'js', 'source_vocab.js')
        with open(path, 'r', encoding='utf-8') as handle:
            src = handle.read()

        server = self.Studio._SOURCE_LABELS['period']
        self.assertEqual(server, "Pay period")
        self.assertIn('period: _t("%s")' % server, src,
                      "two spellings of one label is how this went wrong in "
                      "the first place")

        read_kinds = re.search(r'const READ_KINDS = \[(.*?)\];', src, re.S)
        self.assertTrue(read_kinds)
        self.assertIn('"period"', read_kinds.group(1),
                      "without it `srcDisagrees` reports a false disagreement "
                      "about a component that is working perfectly")

        sources = re.search(r'export const SOURCES = \[(.*?)\];', src, re.S)
        self.assertTrue(sources)
        self.assertIn('key: "period"', sources.group(1))
        icon = re.search(r'\{ key: "period", icon: "([a-z]+)" \}', src)
        self.assertTrue(icon, "the pay period needs a glyph of its own")

        # and the glyph is actually drawn — a key with no branch in `SrcIco`
        # falls through to the dashed "no source" circle, which is the very
        # thing this case exists to stop.
        xml_path = os.path.join(here, 'static', 'src', 'xml', 'studio.xml')
        with open(xml_path, 'r', encoding='utf-8') as handle:
            xml = handle.read()
        block = xml.split('<t t-name="pb_formula_studio.SrcIco">', 1)[1]
        block = block.split('</t>\n\n', 1)[0]
        self.assertIn("icon === '%s'" % icon.group(1), block)

        # …and it has a chip colour of its own, like every other kind.
        scss_path = os.path.join(here, 'static', 'src', 'scss', 'mapping.scss')
        with open(scss_path, 'r', encoding='utf-8') as handle:
            self.assertIn('.mc-src.s-period', handle.read())

        # every kind the server can name has a label on the client
        for kind in self.Studio._SOURCE_LABELS:
            self.assertRegex(src, r'\b%s: _t\(' % kind,
                             "a source kind must be added in BOTH halves of "
                             "the vocabulary (ledger RS6)")

    def test_15b_the_boards_read_the_vocabulary_instead_of_retyping_it(self):
        """Test 15b — no board keeps its own copy of the source labels.

        RS6 said the vocabulary was duplicated in TWO places. It was in four:
        `mapping_canvas.js` had two private copies and `journey_board.js` a
        third, and none of them knew the pay period — so a wire a person had
        just drawn rendered no chip at all (an unknown kind is dropped in
        silence) and the Journey lane printed the raw word "period". One
        register now, read by all of them.
        """
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ('mapping/mapping_canvas.js', 'mapping/journey_board.js'):
            path = os.path.join(here, 'static', 'src', 'js', *name.split('/'))
            with open(path, 'r', encoding='utf-8') as handle:
                body = handle.read()
            self.assertIn('from "../source_vocab"', body,
                          "%s must read the one register" % name)
            self.assertNotIn('excel: _t("Spreadsheet")', body,
                             "%s is keeping its own copy again" % name)
