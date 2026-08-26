# -*- coding: utf-8 -*-
"""JOURNEY J3 — the UI half: two-way ⇆, and the source-conflict guardrail.

Two claims, each of which fails silently if it is wrong:

  * **the direction sentences are ADDITIVE** (owner decision J-D4). The Employee
    & contract board grew `meta.direction` / `meta.directionNote`; if it dropped or
    renamed anything a pre-J3 client reads, the board keeps rendering and simply
    stops saying things. `test_01_*` asserts the recorded pre-J3 shape key by key,
    which is the only check that can catch a REMOVAL.
  * **the conflict probe writes nothing** (J-D3, and the cancel path of the
    dialog). A probe that quietly created the mapping it was asked about would
    still return the right answer, so the assertion has to be a DB count around
    it, not the return value — MF37's lesson, applied before it can cost anything.

The wording is asserted here rather than in hoot because these are server strings
behind `_()`, and because hoot cannot stringify a module-scope `_t` at all (MJ3).
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


def _strip_xml_comments(src):
    return re.sub(r'<!--.*?-->', '', src, flags=re.S)


#: The keys `employee_mapping_data` returned BEFORE J3, recorded so that an
#: additive change can be proved additive. A new key here is fine; a missing one
#: is a client that silently stops rendering something.
PRE_J3_TOP_LEVEL = {
    'ok', 'left', 'right', 'wires', 'left_title', 'right_title', 'subtitle',
    'supports_suggest', 'contexts', 'context_id', 'include_payroll', 'counts',
    'lanes', 'can_edit', 'unresolved',
}
PRE_J3_LEFT_ITEM = {'id', 'label', 'sublabel', 'meta', 'group'}
PRE_J3_LEFT_META = {'col', 'type', 'group', 'role', 'isComponent', 'actions'}


@tagged('post_install', '-at_install')
class TestJourneyGuardrails(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FieldMapping = cls.env['hr.integration.field.mapping']
        cls.PeopleMap = cls.env['hr.payslip.import.mapping']

    # ------------------------------------------------------------- fixtures
    def _config(self, name):
        cfg = self.Config.create({
            'name': name, 'code': re.sub(r'\W', '', name.upper())[:32],
            'country_code': 'VN', 'state': 'active',
        })
        self.basic = self.Rule.create({
            'config_id': cfg.id, 'name': 'Basic Salary', 'code': 'BASIC',
            'column_type': 'input', 'sequence': 1,
        })
        self.jobcol = self.Rule.create({
            'config_id': cfg.id, 'name': 'Job Title', 'code': 'JOBTITLE',
            'column_type': 'input', 'sequence': 2, 'column_role': 'profile',
        })
        self.bankcol = self.Rule.create({
            'config_id': cfg.id, 'name': 'Bank Number', 'code': 'BANKNUM',
            'column_type': 'input', 'sequence': 3, 'column_role': 'bank',
        })
        return cfg

    def _field_mapping(self, cfg, rule, model_name, field_name):
        model = self.env['ir.model']._get(model_name)
        field = self.env['ir.model.fields'].search(
            [('model', '=', model_name), ('name', '=', field_name)], limit=1)
        if not field:
            self.skipTest('%s.%s is not in this build' % (model_name, field_name))
        return self.PeopleMap.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': model.id, 'target_field_id': field.id,
        })

    def _bank_mapping(self, cfg, rule, role='acc_number'):
        return self.PeopleMap.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'bank_account', 'bank_role': role,
        })

    def _connector(self, name='J3 Guard'):
        return self.Connector.create({'name': name, 'connector_type': 'demo'})

    def _wire(self, conn, rule, key):
        return self.FieldMapping.create({
            'connector_id': conn.id, 'target_rule_id': rule.id,
            'source_field': key, 'active_state': 'active'})

    def _fm_count(self):
        return self.FieldMapping.search_count([])

    # =====================================================================
    # 1 — the direction payload is additive (test case 3)
    # =====================================================================
    def test_01a_every_pre_j3_key_survives(self):
        cfg = self._config('J3 Shape')
        self._field_mapping(cfg, self.jobcol, 'hr.employee', 'job_title')
        data = self.Studio.employee_mapping_data(cfg.id, False, True)
        self.assertTrue(data['ok'])
        missing = PRE_J3_TOP_LEVEL - set(data)
        self.assertFalse(missing, "employee_mapping_data lost keys: %s" % missing)
        card = next(i for i in data['left'] if i['id'] == self.jobcol.id)
        self.assertFalse(PRE_J3_LEFT_ITEM - set(card),
                         "a left card lost keys: %s" % (PRE_J3_LEFT_ITEM - set(card)))
        self.assertFalse(
            PRE_J3_LEFT_META - set(card['meta']),
            "a left card's meta lost keys: %s"
            % (PRE_J3_LEFT_META - set(card['meta'])))

    def test_01b_the_board_declares_itself_two_way(self):
        cfg = self._config('J3 Bidi')
        data = self.Studio.employee_mapping_data(cfg.id, False, False)
        self.assertIs(data['bidirectional'], True)
        # …and no other board does
        conn = self._connector()
        api = self.Studio.api_mapping_data(cfg.id, conn.id, False)
        self.assertNotIn('bidirectional', api,
                         "⇆ is a capability of THIS adapter, not a global change")
        imp = self.Studio.import_mapping_data(cfg.id, False)
        self.assertNotIn('bidirectional', imp)

    def test_01c_a_field_row_says_both_halves(self):
        cfg = self._config('J3 FieldDir')
        self._field_mapping(cfg, self.jobcol, 'hr.employee', 'job_title')
        data = self.Studio.employee_mapping_data(cfg.id, False, True)
        card = next(i for i in data['left'] if i['id'] == self.jobcol.id)
        self.assertEqual(card['meta']['direction'], 'two_way')
        note = card['meta']['directionNote']
        self.assertIn('On import:', note)
        self.assertIn('On pay run:', note)
        self.assertIn('Job Title', note, "it names the DESTINATION, not the column")

    def test_01d_a_bank_row_says_only_the_import_half(self):
        """The resolver never reads a bank part back. Saying it would be a lie."""
        cfg = self._config('J3 BankDir')
        self._bank_mapping(cfg, self.bankcol)
        data = self.Studio.employee_mapping_data(cfg.id, False, True)
        card = next(i for i in data['left'] if i['id'] == self.bankcol.id)
        self.assertEqual(card['meta']['direction'], 'to_record')
        note = card['meta']['directionNote']
        self.assertIn('On import:', note)
        self.assertNotIn('On pay run:', note)
        # and the code backs the claim: the read-back covers employee/contract only
        src = _src('pb_formula_studio', 'models/pb_formula_studio.py')
        body = src.split('def _ec_direction', 1)[1].split('\n    @api.model', 1)[0]
        self.assertIn("destination_type == 'bank_account'", body)

    def test_01e_an_unmapped_card_carries_no_direction(self):
        cfg = self._config('J3 Unmapped')
        data = self.Studio.employee_mapping_data(cfg.id, False, True)
        card = next(i for i in data['left'] if i['id'] == self.basic.id)
        self.assertNotIn('direction', card['meta'],
                         "a row that does not exist has no direction")

    def test_01f_the_canvas_renders_the_second_head_only_when_asked(self):
        geom = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_geometry.js'))
        self.assertIn('bidi = false', geom, "opt-in, defaulted off")
        self.assertIn('out.headBack', geom)
        tpl = _strip_xml_comments(
            _src('pb_formula_studio', 'static/src/xml/mapping_canvas.xml'))
        self.assertIn('t-if="g.headBack"', tpl,
                      "the back head is conditional, so every other board is "
                      "byte-identical")
        host = _strip_xml_comments(
            _src('pb_formula_studio', 'static/src/xml/mapping_studio.xml'))
        self.assertIn('bidirectional="isBidirectional"', host)
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        self.assertIn('this.state.data.bidirectional', js,
                      "read from the PAYLOAD, never from the mode id")
        self.assertNotIn('mode === "employee" ? true', js)

    def test_01g_the_tab_label_carries_the_glyph(self):
        js = _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js')
        modes = js.split('export const MODES = [', 1)[1].split('\n];', 1)[0]
        self.assertIn('_t("Employee & contract ⇆")', modes)

    # =====================================================================
    # 2 — conflict DETECTION, one helper, both boards (test cases 5 & 7)
    # =====================================================================
    def test_02a_an_excel_binding_under_a_live_wire_is_a_conflict(self):
        cfg = self._config('J3 Dual')
        conn = self._connector()
        self._wire(conn, self.basic, 'Base')
        self.basic.set_source_binding('excel', 'Basic Salary', origin='board')
        conflicts = self.Studio._source_conflicts(cfg)
        self.assertIn(self.basic.id, conflicts)
        c = conflicts[self.basic.id]
        self.assertEqual(c['shape'], 'excel_vs_feed')
        self.assertEqual(c['primary'], 'feed',
                         "J-D5 — the feed outranks the binding and J3 did not "
                         "reorder it. Any wording built from this must agree.")

    def test_02b_two_connections_on_one_component_is_a_conflict(self):
        cfg = self._config('J3 TwoConn')
        a, b = self._connector('J3 A'), self._connector('J3 B')
        self._wire(a, self.basic, 'Base')
        self._wire(b, self.basic, 'BaseSalary')
        conflicts = self.Studio._source_conflicts(cfg)
        self.assertEqual(conflicts[self.basic.id]['shape'], 'two_feeds')

    def test_02c_one_source_is_never_a_conflict(self):
        cfg = self._config('J3 Single')
        conn = self._connector()
        self._wire(conn, self.basic, 'Base')
        self.assertEqual(self.Studio._source_conflicts(cfg), {})
        self.basic.set_source_binding(False, False)
        self.jobcol.set_source_binding('excel', 'Job', origin='board')
        self.assertEqual(self.Studio._source_conflicts(cfg), {})

    def test_02d_a_half_set_binding_is_not_a_source(self):
        """A defensive guard, tested against the data it defends against.

        `_check_source_binding` (S3) refuses a half-set binding on WRITE, so this
        row cannot be made through the ORM — which is exactly why the detector
        still has to handle it. The constraint arrived after the field did; a
        database that predates it can hold such a row, and a conflict chip
        invented out of one would send a reader hunting for a source that is not
        there. Written in SQL for that reason, not to dodge the constraint.
        """
        cfg = self._config('J3 Half')
        conn = self._connector()
        self._wire(conn, self.basic, 'Base')
        self.env.cr.execute(
            "UPDATE hr_formula_rule SET source_binding = 'excel', "
            "source_binding_key = '  ' WHERE id = %s", (self.basic.id,))
        self.basic.invalidate_recordset()
        self.assertEqual(self.Studio._source_conflicts(cfg), {},
                         "a partially-filled form may not invent a conflict")

    def test_02e_both_boards_show_the_same_ranked_sources(self):
        """JOURNEY J9 — this test used to demand a CONFLICT chip here.

        It asserted, correctly for J3, that a component holding a spreadsheet
        binding while a live wire targets it wears "Spreadsheet fallback" on one
        board and "Feed wins" on the other. The owner has since withdrawn the
        either/or restriction: two sources on one component is legal, so the
        board states the ORDER instead of raising an alarm about it, and the
        conflict chip is dropped from a card that is already saying the whole
        thing (S6 D1's principle, one question later).

        The DETECTOR is untouched and is still asserted — nothing was hidden,
        only not repeated. Both boards show the same two ranked chips, which is
        the standing complaint this programme exists to close: screens that each
        tell part of the truth.
        """
        cfg = self._config('J3 Chips')
        conn = self._connector('Zoho-ish')
        self._wire(conn, self.basic, 'Base')
        self.basic.set_source_binding('excel', 'Basic Salary', origin='board')
        self.assertIn(self.basic.id, self.Studio._source_conflicts(cfg),
                      "the detector still sees it; the card simply stops "
                      "saying the same fact twice")
        expected = [('feed', 1, 'Base'), ('excel', 2, 'Basic Salary')]
        api = self.Studio.api_mapping_data(cfg.id, conn.id, False)
        card = next(i for i in api['right'] if i['id'] == self.basic.id)
        self.assertNotIn('conflict', card)
        self.assertEqual([(s['kind'], s['rank'], s['key'])
                          for s in card['srcKinds']], expected)
        imp = self.Studio.import_mapping_data(cfg.id, False)
        card = next(i for i in imp['right'] if i['id'] == self.basic.id)
        self.assertNotIn('conflict', card)
        self.assertEqual([(s['kind'], s['rank'], s['key'])
                          for s in card['srcKinds']], expected,
                         "both boards say the same thing, in the same order")
        self.assertIn('Basic Salary', card['srcKinds'][1]['note'],
                      "the tooltip names the column the chip has no room for")

    def test_02f_a_pre_existing_dual_state_chips_on_load(self):
        """No dialog involved: the state may predate the guardrail entirely."""
        cfg = self._config('J3 Legacy')
        a, b = self._connector('Legacy A'), self._connector('Legacy B')
        self._wire(a, self.basic, 'Base')
        self._wire(b, self.basic, 'Base2')
        imp = self.Studio.import_mapping_data(cfg.id, False)
        card = next(i for i in imp['right'] if i['id'] == self.basic.id)
        self.assertIn('conflict', card)
        self.assertEqual(card['conflict']['label'], 'Wired twice')
        self.assertIn('Legacy A', card['conflict']['hint'])
        self.assertIn('Legacy B', card['conflict']['hint'])

    # =====================================================================
    # 3 — the probe: three answers, ZERO writes (test cases 4 & 6)
    # =====================================================================
    def test_03a_the_probe_writes_nothing_ever(self):
        """MF37 — the oracle is the DATABASE, not the return value."""
        cfg = self._config('J3 Probe')
        conn = self._connector()
        self._wire(conn, self.basic, 'Base')
        before_fm = self._fm_count()
        before_binding = (self.basic.source_binding, self.basic.source_binding_key)
        r = self.Studio.source_conflict_probe(
            cfg.id, 'import', self.basic.id, 'Basic Salary')
        self.assertTrue(r['conflict'], "there IS a conflict to report")
        self.assertEqual(self._fm_count(), before_fm)
        self.basic.invalidate_recordset()
        self.assertEqual(
            (self.basic.source_binding, self.basic.source_binding_key),
            before_binding,
            "the probe is the cancel path's whole safety: it must not write")

    def test_03b_a_clean_draw_probes_clean(self):
        cfg = self._config('J3 Clean')
        conn = self._connector()
        self.assertFalse(self.Studio.source_conflict_probe(
            cfg.id, 'import', self.basic.id, 'Basic Salary')['conflict'])
        self.assertFalse(self.Studio.source_conflict_probe(
            cfg.id, 'api', self.basic.id, 'Base', conn.id)['conflict'])

    def test_03c_a_same_source_redraw_is_not_a_conflict(self):
        """Silent swap + toast survives — nothing that was one gesture became two."""
        cfg = self._config('J3 Redraw')
        conn = self._connector()
        self.basic.set_source_binding('excel', 'Old Column', origin='board')
        self.assertFalse(
            self.Studio.source_conflict_probe(
                cfg.id, 'import', self.basic.id, 'New Column')['conflict'],
            "excel -> excel is today's swap, not a conflict")
        self._wire(conn, self.jobcol, 'JobA')
        self.assertFalse(
            self.Studio.source_conflict_probe(
                cfg.id, 'api', self.jobcol.id, 'JobB', conn.id)['conflict'],
            "a rewire on the SAME connection is today's swap")

    def test_03d_replace_removes_the_other_source(self):
        cfg = self._config('J3 Replace')
        conn = self._connector()
        wire = self._wire(conn, self.basic, 'Base')
        r = self.Studio.import_mapping_create(
            cfg.id, False, 'Basic Salary', self.basic.id, resolve='replace')
        self.assertTrue(r['ok'])
        self.assertFalse(wire.exists(), "replace unlinks the wire")
        self.basic.invalidate_recordset()
        self.assertEqual(self.basic.source_binding, 'excel')
        self.assertEqual(self.basic.source_binding_key, 'Basic Salary')
        self.assertEqual(self.Studio._source_conflicts(cfg), {},
                         "and the conflict is gone with it")

    def test_03e_keep_leaves_both_and_the_spreadsheet_stays_the_fallback(self):
        """JOURNEY J9 — "keep as fallback" became "Add source", and the
        difference is that the FEED is now declared too.

        J3 could only keep the spreadsheet binding by NOT writing the feed one,
        because there was room for exactly one. So `source_binding` read `excel`
        and the feed was a wire nothing on the component named. With the binding
        plural both are declared, both are visible, and the order between them is
        stated rather than inferred — the feed is rank 1 because that is where
        the resolver has always read it, and the spreadsheet column is still the
        fallback it was.
        """
        cfg = self._config('J3 Keep')
        conn = self._connector()
        self.basic.set_source_binding('excel', 'Basic Salary', origin='board')
        r = self.Studio.api_mapping_create(
            cfg.id, conn.id, 'Base', self.basic.id, resolve='keep')
        self.assertTrue(r['ok'])
        self.env.invalidate_all()
        self.assertEqual(
            [(d['kind'], d['key']) for d in self.basic.declared_sources()],
            [('feed', 'Base'), ('excel', 'Basic Salary')],
            "the spreadsheet declaration SURVIVES — without it the resolver has "
            "nothing to fall back TO — and the feed is now declared beside it")
        self.assertEqual(self.basic.source_binding, 'feed',
                         "the head of the plural binding is the highest-ranked "
                         "source, which is where a run reads first")
        self.assertTrue(self.FieldMapping.search_count(
            [('target_rule_id', '=', self.basic.id)]),
            "and the wire is drawn")
        self.assertIn(self.basic.id, self.Studio._source_conflicts(cfg),
                      "both live, and the detector still says so")

    def test_03f_replace_reaches_across_connections(self):
        cfg = self._config('J3 CrossConn')
        a, b = self._connector('Cross A'), self._connector('Cross B')
        old = self._wire(a, self.basic, 'Base')
        self.Studio.api_mapping_create(
            cfg.id, b.id, 'Base2', self.basic.id, resolve='replace')
        self.assertFalse(
            old.exists(),
            "the pre-J3 tidy-up only ever searched within ONE connector, which "
            "is exactly why two-connection wiring could exist at all")

    def test_03g_no_resolve_is_exactly_todays_behaviour(self):
        """The additive proof: every existing caller and test is unchanged."""
        cfg = self._config('J3 Default')
        conn = self._connector()
        wire = self._wire(conn, self.basic, 'Base')
        self.Studio.import_mapping_create(
            cfg.id, False, 'Basic Salary', self.basic.id)
        self.assertTrue(wire.exists(),
                        "without an answer, nothing else is removed")
        self.basic.invalidate_recordset()
        self.assertEqual(self.basic.source_binding, 'excel')

    # =====================================================================
    # 4 — the dialog itself
    # =====================================================================
    def test_04a_the_server_writes_the_sentences(self):
        cfg = self._config('J3 Words')
        conn = self._connector('Darwin-ish')
        self._wire(conn, self.basic, 'Base')
        c = self.Studio.source_conflict_probe(
            cfg.id, 'import', self.basic.id, 'Basic Salary')['conflict']
        for key in ('title', 'body', 'existing', 'incoming', 'replace_label',
                    'replace_note', 'keep_label', 'keep_note', 'cancel_label'):
            self.assertTrue(c.get(key), "the dialog needs %s" % key)
        # JOURNEY J9 — the body states the resulting ORDER rather than naming
        # the connection, because the connection is on screen twice already (the
        # "Reads now" side, and the ranked list below it) and the thing a reader
        # cannot work out for themselves is which source wins.
        self.assertIn('Darwin-ish', c['existing']['key'])
        self.assertEqual([o['rank'] for o in c['order']], [1, 2])
        self.assertIn('in that order', c['body'])
        self.assertIn('add', c['keep_label'].lower(),
                      "the primary action is to keep both, which is what the "
                      "owner asked for")

    def test_04b_the_dialog_never_composes_precedence_itself(self):
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        block = js.split('async draw(', 1)[1].split('async _commitDraw', 1)[0]
        self.assertIn('source_conflict_probe', block)
        # cancel is not an RPC and not a rollback
        cancel = js.split('cancelConflict()', 1)[1].split('\n    }', 1)[0]
        self.assertNotIn('orm.call', cancel,
                         "cancel must make NO call — there is nothing to undo "
                         "because nothing was sent")
        tpl = _strip_xml_comments(
            _src('pb_formula_studio', 'static/src/xml/mapping_studio.xml'))
        block = tpl.split('state.conflict', 1)[1].split('MAPFIX B3', 1)[0]
        # every visible string comes off the payload
        self.assertIn('t-esc="state.conflict.title"', block)
        self.assertIn('t-esc="state.conflict.keep_note"', block)
        self.assertIn('aria-modal="true"', block)
        self.assertIn("ev.key === 'Escape'", block, "Escape cancels")

    def test_04c_the_three_verbs_are_all_reachable(self):
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        self.assertIn("this.resolveConflict('replace')", _strip_xml_comments(
            _src('pb_formula_studio', 'static/src/xml/mapping_studio.xml')))
        self.assertIn("this.resolveConflict('keep')", _strip_xml_comments(
            _src('pb_formula_studio', 'static/src/xml/mapping_studio.xml')))
        self.assertIn('cancelConflict()', js)
