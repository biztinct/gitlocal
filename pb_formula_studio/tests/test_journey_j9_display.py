# -*- coding: utf-8 -*-
"""JOURNEY J9 — every source on the card, with its place in the order.

The server half of the display change, plus the three places the either/or
restriction was enforced (§4.5).

**T1 is the test that matters most here.** `api_mapping_create` writes a field
mapping AND an S3 binding in the same gesture, so all nine of abm's feed-bound
components carry a wire whose `source_field` is character-for-character the
binding key. They are ONE source recorded twice. Without the `(kind, key)` fold
every one of them would render two identical "Connected system" chips — and the
canvas' label dedupe would then hide the second, leaving the board looking right
while the reader was told the wrong thing about how many sources a component has.
A change that lights up nine cards has failed, not succeeded.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip_js_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^\s*//.*$', '', src, flags=re.M)


@tagged('post_install', '-at_install')
class TestJourneyJ9Display(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FM = cls.env['hr.integration.field.mapping']

    # ------------------------------------------------------------- fixtures
    def _world(self, name='J9 Display'):
        conn = self.Connector.create({'name': 'J9 Conn',
                                      'connector_type': 'demo'})
        cfg = self.Config.create({
            'name': name, 'code': name.upper().replace(' ', '')[:32],
            'country_code': 'VN', 'state': 'active',
        })
        rule = self.Rule.create({
            'config_id': cfg.id, 'name': 'Gas Allowance', 'code': 'J9GASALLOW',
            'column_type': 'input', 'sequence': 1,
        })
        return conn, cfg, rule

    def _declared(self, cfg, rule):
        return self.Studio._declared_sources(
            rule, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))

    # =====================================================================
    # 3 — T1 GATE. A feed source and a wire naming the same key are ONE source.
    # =====================================================================
    def test_03_a_feed_source_and_its_own_wire_fold_into_one_entry(self):
        conn, cfg, rule = self._world('J9 Fold')
        # abm's shape exactly: `api_mapping_create` wrote both of these.
        self.FM.create({'connector_id': conn.id, 'target_rule_id': rule.id,
                        'source_field': 'Bank_Name', 'active_state': 'active'})
        rule.set_source_binding('feed', 'Bank_Name', origin='board')
        declared = self._declared(cfg, rule)
        self.assertEqual(len(declared), 1,
                         "one source recorded twice is one source — nine cards "
                         "with two identical chips is the failure this fold "
                         "exists to prevent")
        self.assertEqual(declared[0]['kind'], 'feed')
        self.assertEqual(declared[0]['key'], 'Bank_Name')
        # and the card therefore carries ONE chip, with no superscript
        item = self.Studio._mc_right_item(rule, declared)
        self.assertEqual(len(item['srcKinds']), 1)
        self.assertEqual(item['srcKinds'][0]['rank'], 0)
        self.assertEqual(item['srcKind'], 'feed')

    def test_03b_a_wire_on_a_DIFFERENT_key_is_a_second_source(self):
        conn, cfg, rule = self._world('J9 NoFold')
        self.FM.create({'connector_id': conn.id, 'target_rule_id': rule.id,
                        'source_field': 'Bank_Name', 'active_state': 'active'})
        rule.set_source_binding('excel', 'SEVL|Bank', origin='board')
        declared = self._declared(cfg, rule)
        self.assertEqual([d['kind'] for d in declared], ['feed', 'excel'],
                         "ranked, not in the order they were found")

    # =====================================================================
    # `_declared_source` is `_declared_sources[0]` and its shape is unchanged
    # =====================================================================
    def test_03c_the_scalar_keeps_its_three_keys_for_its_four_callers(self):
        _conn, cfg, rule = self._world('J9 Scalar')
        rule.set_source_binding('excel', 'A Col')
        one = self.Studio._declared_source(
            rule, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))
        self.assertEqual(set(one), {'kind', 'key', 'wirable'})
        self.assertEqual(one['kind'], 'excel')
        self.assertEqual(one, self._declared(cfg, rule)[0])

    def test_03d_a_sealed_card_is_sealed_before_anything_else_is_asked(self):
        _conn, cfg, _r = self._world('J9 SealedCard')
        sealed = self.Rule.create({
            'config_id': cfg.id, 'name': 'Net', 'code': 'J9NET',
            'column_type': 'formula', 'excel_formula': '=1', 'sequence': 5})
        declared = self._declared(cfg, sealed)
        self.assertEqual([d['kind'] for d in declared], ['calculated'])
        item = self.Studio._mc_right_item(sealed, declared)
        # S6 D1 must not regress: no source chip at all, and the badge keeps it
        self.assertEqual(item['srcKind'], '')
        self.assertEqual(item['srcKinds'], [])
        self.assertFalse(item['meta']['wirable'])
        self.assertTrue(item['meta']['badge'])

    # =====================================================================
    # The card: all sources, ranked among the sources ON THIS CARD
    # =====================================================================
    def test_03e_two_sources_are_ranked_one_and_two_not_two_and_three(self):
        _conn, cfg, rule = self._world('J9 Rank')
        rule.set_source_binding('excel', 'SEVL|Gas Allowance')
        rule.is_contract_component = True
        declared = self._declared(cfg, rule)
        item = self.Studio._mc_right_item(rule, declared)
        self.assertEqual([(s['kind'], s['rank']) for s in item['srcKinds']],
                         [('excel', 1), ('contract_component', 2)],
                         "the rank is the position among the sources MAPPED ON "
                         "THIS CARD — a gap would only invite the question "
                         "'where is number one?'")
        # `srcKind` stays the winner, so a stale bundle renders one right chip
        self.assertEqual(item['srcKind'], 'excel')

    def test_03f_a_card_with_three_sources_ranks_one_two_three(self):
        conn, cfg, rule = self._world('J9 Three')
        self.FM.create({'connector_id': conn.id, 'target_rule_id': rule.id,
                        'source_field': 'Gas', 'active_state': 'active'})
        rule.set_source_binding('excel', 'SEVL|Gas')
        rule.is_contract_component = True
        item = self.Studio._mc_right_item(rule, self._declared(cfg, rule))
        self.assertEqual([(s['kind'], s['rank']) for s in item['srcKinds']],
                         [('feed', 1), ('excel', 2), ('contract_component', 3)])

    def test_03g_each_ranked_chip_carries_its_own_sentence(self):
        _conn, cfg, rule = self._world('J9 Notes')
        rule.set_source_binding('excel', 'SEVL|Gas')
        rule.is_contract_component = True
        item = self.Studio._mc_right_item(rule, self._declared(cfg, rule))
        notes = [s['note'] for s in item['srcKinds']]
        self.assertIn('SEVL|Gas', notes[0])
        self.assertTrue(all(n for n in notes), "every chip explains itself")
        self.assertNotEqual(notes[0], notes[1],
                            "the first is tried first and the second is not; "
                            "two chips with one sentence say nothing")

    def test_03h_no_ninth_term_can_reach_a_chip(self):
        """The vocabulary is closed. `_source_rank_note` composes sentences out
        of `_source_label`, which is the eight words and nothing else."""
        allowed = {self.Studio._source_label(k)
                   for k in self.Studio._SOURCE_LABELS}
        _conn, cfg, rule = self._world('J9 Vocab')
        rule.set_source_binding('feed', 'K')
        rule.is_contract_component = True
        for src in self.Studio._mc_right_item(
                rule, self._declared(cfg, rule))['srcKinds']:
            self.assertIn(self.Studio._source_label(src['kind']), allowed)

    def test_03i_the_conflict_chip_is_dropped_on_a_card_that_ranks_its_sources(self):
        """S6 D1's principle, one question later: a card already saying the
        whole thing must not be handed the same fact in weaker words."""
        conn, cfg, rule = self._world('J9 NoConflictChip')
        self.FM.create({'connector_id': conn.id, 'target_rule_id': rule.id,
                        'source_field': 'Gas', 'active_state': 'active'})
        rule.set_source_binding('excel', 'SEVL|Gas')
        # the detector still SEES it — nothing was hidden, only not repeated
        self.assertIn(rule.id, self.Studio._source_conflicts(cfg))
        col = self.Studio._mc_right_column(
            cfg, {}, self.Studio._source_record_dests(cfg),
            wire_dests=self.Studio._source_wire_dests(cfg), board='import')
        card = [c for c in col if c['id'] == rule.id][0]
        self.assertEqual(len(card['srcKinds']), 2)
        self.assertNotIn('conflict', card)

    def test_03j_a_single_source_card_still_gets_its_conflict_chip(self):
        conn, cfg, rule = self._world('J9 KeepConflictChip')
        # two connections, one key: still a genuine conflict, not a precedence
        conn2 = self.Connector.create({'name': 'J9 Conn 2',
                                       'connector_type': 'demo'})
        for c in (conn, conn2):
            self.FM.create({'connector_id': c.id, 'target_rule_id': rule.id,
                            'source_field': 'Gas', 'active_state': 'active'})
        col = self.Studio._mc_right_column(
            cfg, {}, self.Studio._source_record_dests(cfg),
            wire_dests=self.Studio._source_wire_dests(cfg), board='api')
        card = [c for c in col if c['id'] == rule.id][0]
        self.assertEqual(len(card['srcKinds']), 1)
        self.assertIn('conflict', card)

    def test_03k_the_note_states_the_order_instead_of_raising_an_alarm(self):
        _conn, cfg, rule = self._world('J9 Note')
        rule.set_source_binding('excel', 'SEVL|Gas')
        rule.is_contract_component = True
        note = self.Studio._source_note(
            rule, {}, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))
        self.assertNotIn('Already fed by', note,
                         "'already fed by' was a warning about something that "
                         "is now legal")
        self.assertIn('SEVL|Gas', note)
        # a single source keeps the original sentence: there is no order to state
        rule.is_contract_component = False
        one = self.Studio._source_note(
            rule, {}, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))
        self.assertIn('Already fed by', one)

    # =====================================================================
    # §4.5 — the three places exclusivity was enforced
    # =====================================================================
    def test_04a_promoting_to_a_contract_component_no_longer_unlinks_a_mapping(self):
        _conn, cfg, rule = self._world('J9 Promote')
        field = self.env['ir.model.fields'].search(
            [('model', '=', 'hr.employee'), ('name', '=', 'barcode')], limit=1)
        model = self.env['ir.model'].search(
            [('model', '=', 'hr.employee')], limit=1)
        mapping = self.env['hr.payslip.import.mapping'].create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'target_model_id': model.id, 'target_field_id': field.id,
            'destination_type': 'field',
        })
        res = self.Studio.employee_mapping_make_component(rule.id, 'amount')
        self.assertTrue(res.get('ok'), res)
        self.assertTrue(mapping.exists(),
                        "promoting now ADDS a destination instead of silently "
                        "replacing one — the restriction is what was removed")
        self.assertTrue(rule.is_contract_component)

    def test_04b_the_probe_states_the_resulting_order_and_offers_add_source(self):
        conn, cfg, rule = self._world('J9 Probe')
        self.FM.create({'connector_id': conn.id, 'target_rule_id': rule.id,
                        'source_field': 'Gas', 'active_state': 'active'})
        probe = self.Studio.source_conflict_probe(
            cfg.id, 'import', rule.id, key='SEVL|Gas')
        self.assertTrue(probe['ok'])
        c = probe['conflict']
        self.assertTrue(c)
        self.assertEqual([o['rank'] for o in c['order']], [1, 2])
        self.assertEqual(c['order'][0]['label'],
                         self.Studio._source_label('feed'))
        self.assertEqual(c['order'][1]['label'],
                         self.Studio._source_label('excel'))
        self.assertEqual(c['order'][1]['key'], 'SEVL|Gas')
        # Add source is the primary answer; Replace survives as the secondary
        self.assertTrue(c['keep_label'])
        self.assertTrue(c['replace_label'])
        self.assertTrue(c['cancel_label'])
        # and it WROTE NOTHING
        self.assertFalse(rule.source_ids)

    def test_04c_add_source_keeps_both_and_replace_still_removes(self):
        conn, cfg, rule = self._world('J9 Resolve')
        rule.set_source_binding('excel', 'SEVL|Gas', origin='board')
        res = self.Studio.api_mapping_create(
            cfg.id, conn.id, 'Gas', rule.id, False, resolve='keep')
        self.assertTrue(res.get('ok'), res)
        self.assertEqual({s.kind for s in rule.source_ids}, {'excel', 'feed'},
                         "Add source keeps both — that is the whole request")
        # replace is still one click away and still means what it said
        res = self.Studio.api_mapping_create(
            cfg.id, conn.id, 'Gas', rule.id, False, resolve='replace')
        self.assertTrue(res.get('ok'), res)
        self.assertEqual({s.kind for s in rule.source_ids}, {'feed'})

    def test_04d_removing_a_wire_clears_only_that_wires_kind(self):
        conn, cfg, rule = self._world('J9 CutOne')
        m = self.FM.create({'connector_id': conn.id, 'target_rule_id': rule.id,
                            'source_field': 'Gas', 'active_state': 'active'})
        rule.set_source_binding('feed', 'Gas', origin='board')
        rule.set_source_binding('excel', 'SEVL|Gas', origin='board')
        self.Studio.api_mapping_delete(m.id)
        self.assertEqual([s.kind for s in rule.source_ids], ['excel'],
                         "a component someone has since bound to a spreadsheet "
                         "column must not lose that because a feed wire was "
                         "tidied away — which is what the comment there has "
                         "always claimed and could not deliver")

    def test_04e_removing_a_spreadsheet_wire_works_when_a_feed_outranks_it(self):
        _conn, cfg, rule = self._world('J9 CutExcel')
        rule.set_source_binding('feed', 'Gas', origin='board')
        rule.set_source_binding('excel', 'SEVL|Gas', origin='board')
        # `source_binding` computes to 'feed' here, so the old guard would have
        # found no spreadsheet binding and left the component reading a column
        # the board had just removed.
        self.Studio.import_mapping_delete(rule.id)
        self.assertEqual([s.kind for s in rule.source_ids], ['feed'])

    def test_04f_the_cut_and_undo_round_trip_survives_a_second_source(self):
        conn, cfg, rule = self._world('J9 Undo')
        m = self.FM.create({'connector_id': conn.id, 'target_rule_id': rule.id,
                            'source_field': 'Gas', 'active_state': 'active'})
        rule.set_source_binding('feed', 'Gas', origin='board')
        rule.set_source_binding('excel', 'SEVL|Gas', origin='board')
        res = self.Studio.api_mapping_cut(m.id)
        self.assertTrue(res.get('ok'), res)
        self.assertEqual(res['snapshot']['binding']['kind'], 'feed',
                         "asked of the SOURCE ROW: `source_binding` reports "
                         "only the highest-ranked one, and cutting a rule wire "
                         "off a feed-reading component would have lost it")
        self.Studio.api_mapping_restore(res['snapshot'])
        self.assertEqual({s.kind for s in rule.source_ids}, {'excel', 'feed'})
        self.assertEqual(
            rule.source_ids.filtered(lambda s: s.kind == 'feed').origin, 'board')

    def test_04g_binding_replaced_is_silent_when_nothing_is_displaced(self):
        _conn, _cfg, rule = self._world('J9 Replaced')
        rule.set_source_binding('excel', 'SEVL|Gas')
        self.assertIsNone(self.Studio._binding_replaced(rule, 'feed', 'Gas'),
                          "adding a feed source beside a spreadsheet column "
                          "displaces nothing; saying it did would be the toast "
                          "and the dialog disagreeing about what happened")
        self.assertTrue(self.Studio._binding_replaced(rule, 'excel', 'Other'))

    # =====================================================================
    # The order is defined ONCE, and the boards read it
    # =====================================================================
    def test_05_the_board_reads_the_resolver_s_own_rank(self):
        self.assertEqual(self.Studio._source_rank(),
                         self.env['hr.formula.rule']._SOURCE_RANK,
                         "two implementations of an order is how the boards "
                         "started disagreeing in the first place")

    # =====================================================================
    # 6 — every board says the same thing, and none of them invents a word
    # =====================================================================
    def test_06a_the_transform_board_reads_the_shared_vocabulary(self):
        """A SIBLING of the canvas may not grow a second source vocabulary.

        `TransformFlowBoard` cannot call `itemChips` — J4 made it a sibling
        deliberately, because the canvas' two-lane contract carries five tabs
        that have nothing to do with rules. What it must share is the WORDS, so
        it imports `srcLabel` rather than writing a label map of its own.
        """
        js = _strip_js_comments(_src(
            'pb_formula_studio', 'static/src/js/mapping/transform_flow_board.js'))
        self.assertIn('import { srcLabel }', js)
        block = js.split('srcChips(item) {', 1)[1].split('\n    }', 1)[0]
        self.assertNotIn('_t("Spreadsheet")', block,
                         "a second label map is a second vocabulary")
        self.assertIn('srcLabel(', block)

    def test_06b_no_board_template_hardcodes_a_source_label(self):
        xml = _src('pb_formula_studio',
                   'static/src/xml/transform_flow_board.xml')
        self.assertNotIn('>Rule output<', xml,
                         "the hardcoded chip is gone; the loop over srcKinds "
                         "replaced it")
        self.assertIn('srcChips(it)', xml)

    def test_06c_the_superscript_is_an_element_not_a_codepoint(self):
        for path in ('static/src/xml/mapping_canvas.xml',
                     'static/src/xml/transform_flow_board.xml'):
            xml = _src('pb_formula_studio', path)
            self.assertIn('<sup t-if="ch.rank"', xml, path)
        # COMMENTS ARE EXEMPT and the exemption is the point: a prose note is
        # allowed to write "Spreadsheet\u00b9" because that is what the reader
        # sees, and a source assertion that cannot tell a comment from a string
        # fails against correct code (MJ25).
        for path in ('static/src/xml/mapping_canvas.xml',
                     'static/src/xml/transform_flow_board.xml'):
            body = re.sub(r'<!--.*?-->', '', _src('pb_formula_studio', path),
                          flags=re.S)
            for bad in ('\u00b9', '\u00b2', '\u00b3'):
                self.assertNotIn(bad, body, path)
        js = _strip_js_comments(_src(
            'pb_formula_studio', 'static/src/js/mapping/mapping_canvas.js'))
        for bad in ('\u00b9', '\u00b2', '\u00b3'):
            self.assertNotIn(bad, js,
                             "a Unicode superscript is not an element: a screen "
                             "reader skips it and half the font stack has no "
                             "glyph for it")

    def test_06d_the_word_odoo_reaches_no_string_this_phase_added(self):
        """The white-label rule, checked where this phase wrote strings.

        Technical identifiers are untouched by design — `from odoo import`,
        model ids, log messages, comments — so this reads the USER-FACING
        literals only: the ones `_()` wraps.
        """
        py = _src('pb_formula_studio', 'models/pb_formula_studio.py')
        for m in re.finditer(r'_\(\s*"((?:[^"\\]|\\.)*)"', py):
            self.assertNotIn('odoo', m.group(1).lower(),
                             "user-visible string names the engine: %r"
                             % m.group(1)[:80])
        rule_py = _src('pb_hr_payroll_formula', 'models/formula_rule_source.py')
        for m in re.finditer(r'_\(\s*"((?:[^"\\]|\\.)*)"', rule_py):
            self.assertNotIn('odoo', m.group(1).lower(), m.group(1)[:80])
