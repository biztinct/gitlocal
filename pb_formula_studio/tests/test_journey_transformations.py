# -*- coding: utf-8 -*-
"""JOURNEY J4 — the Transformations tab: fields → rule → output → component.

Four claims, each of which fails quietly if it is wrong, which is why each one is
asserted against a DIFFERENT oracle:

  * **the payload is composed, not invented.** Every lane of `transform_flow_data`
    has to agree with the model it came from — the wires with
    `hr.integration.field.mapping` ROWS and `('rule', key)` bindings, the reads
    with `_consumed_field_names()`, the components with `_mc_right_column`. A board
    that computed its own answer would look perfect and drift the first time
    anything upstream moved. Counted against the ORM, never against a literal.
  * **"unread" has exactly one definition.** `pb.integrations._rule_consumers` owns
    it. The test asserts the two agree ON THE SAME FIXTURE, which is the only check
    that catches a second definition being introduced later — a source grep for
    the string would pass happily while the two answered differently.
  * **the write path is the EXISTING one.** J4 draws through `api_mapping_create`
    and cuts through `api_mapping_delete`; the round trip must leave the database
    byte-identical, and the wire it makes must classify as kind `rule` (i.e. bind
    the component to the rule, not to a feed).
  * **nothing that already worked stopped working.** The adapters J4 reads from are
    asserted additive: a key REMOVED from `api_mapping_data` is a client that keeps
    rendering and silently stops saying things (J3's lesson, one phase on).

Wording lives here rather than in hoot because these are server strings behind
`_()`, and because hoot cannot stringify a module-scope `_t` at all (MJ3).
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


#: The top-level keys `api_mapping_data` returned BEFORE J4. J4 reads that
#: adapter's helpers and must not have narrowed its payload on the way past.
PRE_J4_API_TOP_LEVEL = {
    'ok', 'left', 'right', 'wires', 'contexts', 'context_id', 'can_edit',
}


@tagged('post_install', '-at_install')
class TestJourneyTransformations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FieldMapping = cls.env['hr.integration.field.mapping']
        cls.TRule = cls.env['hr.api.transformation.rule']

    # ------------------------------------------------------------- fixtures
    def _config(self, name):
        cfg = self.Config.create({
            'name': name, 'code': re.sub(r'\W', '', name.upper())[:32],
            'country_code': 'VN', 'state': 'active',
        })
        self.ot15 = self.Rule.create({
            'config_id': cfg.id, 'name': 'Overtime 150 Hours', 'code': 'OTHOURS15',
            'column_type': 'input', 'sequence': 1,
        })
        self.deps = self.Rule.create({
            'config_id': cfg.id, 'name': 'Dependants', 'code': 'DEPS',
            'column_type': 'input', 'sequence': 2,
        })
        self.spare = self.Rule.create({
            'config_id': cfg.id, 'name': 'Spare Input', 'code': 'SPARE',
            'column_type': 'input', 'sequence': 3,
        })
        return cfg

    def _connector(self, name='J4 Flow'):
        return self.Connector.create({'name': name, 'connector_type': 'demo'})

    def _trule(self, conn, key, name=None, **extra):
        vals = {'connector_id': conn.id, 'name': name or ('Rule %s' % key),
                'output_key': key, 'rule_type': 'sum',
                'builder_mode': 'guided', 'source_data_type': 'custom'}
        vals.update(extra)
        return self.TRule.create(vals)

    def _wire(self, conn, rule, key):
        return self.FieldMapping.create({
            'connector_id': conn.id, 'target_rule_id': rule.id,
            'source_field': key, 'active_state': 'active'})

    def _flow(self, cfg, conn):
        return self.Studio.transform_flow_data(cfg.id, conn.id)

    # =====================================================================
    # 1 — the middle lane IS the rule table (numbered case 2)
    # =====================================================================
    def test_01a_every_rule_gets_exactly_one_card(self):
        cfg = self._config('J4 Cards')
        conn = self._connector()
        keys = ['OTHRSA', 'OTHRSB', 'DEPCNT']
        for k in keys:
            self._trule(conn, k)
        d = self._flow(cfg, conn)
        self.assertTrue(d['ok'], d)
        self.assertEqual(len(d['rules']), 3, "one card per rule, no more and no fewer")
        self.assertEqual(sorted(r['key'] for r in d['rules']), sorted(keys))
        self.assertEqual(d['counts']['rules'], 3)

    def test_01b_a_card_carries_name_summary_and_key(self):
        cfg = self._config('J4 Card Shape')
        conn = self._connector()
        r = self._trule(conn, 'WORKEDHRS', name='Actual working hours',
                        aggregate_field='totalWorkedHours')
        card = self._flow(cfg, conn)['rules'][0]
        self.assertEqual(card['id'], r.id)
        self.assertEqual(card['label'], 'Actual working hours')
        self.assertEqual(card['key'], 'WORKEDHRS')
        # the summary is the MODEL's, not a second sentence written here
        self.assertEqual(card['summary'], r.plain_summary or '')
        self.assertTrue(card['active'])
        for k in ('reads', 'feeds', 'health', 'lineage'):
            self.assertIn(k, card)

    def test_01c_an_archived_rule_still_renders(self):
        """A rule switched off whose output a component still reads is exactly
        the state a person needs to SEE; filtering it out would leave the wire
        into that component pointing at nothing."""
        cfg = self._config('J4 Archived')
        conn = self._connector()
        r = self._trule(conn, 'OLDKEY')
        self._wire(conn, self.ot15, 'OLDKEY')
        r.active = False
        d = self._flow(cfg, conn)
        card = next(c for c in d['rules'] if c['key'] == 'OLDKEY')
        self.assertFalse(card['active'], "and it says so, rather than vanishing")
        self.assertTrue(any(w['ruleId'] == r.id for w in d['wires']))

    # =====================================================================
    # 2 — the READ lane is the rules' own consumed fields (case 2 / case 8)
    # =====================================================================
    def test_02a_left_lane_is_exactly_what_the_rules_read(self):
        cfg = self._config('J4 Reads')
        conn = self._connector()
        a = self._trule(conn, 'AAA', filter_conditions={
            'join': 'all', 'rows': [{'field': 'OT_Type', 'op': '=', 'value': '1'}]})
        b = self._trule(conn, 'BBB', filter_conditions={
            'join': 'all', 'rows': [{'field': 'OT_Type', 'op': '=', 'value': '2'}]},
            value_steps=[{'field': 'Actual_Pay_Hour'}])
        d = self._flow(cfg, conn)
        want = set(a._consumed_field_names()) | set(b._consumed_field_names())
        got = {f['sublabel'] for f in d['left']}
        self.assertEqual(got, want,
                         "the lane is the union of the rules' own consumed paths")
        # ONE card per field however many rules read it — the lane is the
        # connector's fields, not a per-rule list glued end to end
        self.assertEqual(len(d['left']), len(want))
        ot = next(f for f in d['left'] if f['sublabel'] == 'OT_Type')
        self.assertEqual(ot['readers'], 2, "and it says how many rules read it")

    def test_02b_read_edges_are_one_per_rule_field_pair(self):
        cfg = self._config('J4 Edges')
        conn = self._connector()
        a = self._trule(conn, 'AAA', filter_conditions={
            'join': 'all', 'rows': [{'field': 'OT_Type', 'op': '=', 'value': '1'}]})
        b = self._trule(conn, 'BBB', filter_conditions={
            'join': 'all', 'rows': [{'field': 'OT_Type', 'op': '=', 'value': '2'}]})
        d = self._flow(cfg, conn)
        pairs = {(e['ruleId'], e['leftId']) for e in d['reads']}
        self.assertEqual(pairs, {(a.id, 'f:OT_Type'), (b.id, 'f:OT_Type')})
        self.assertEqual(len(d['reads']), len(pairs), "no duplicate edges")

    def test_02c_the_board_offers_no_way_to_write_a_read_edge(self):
        """Numbered case 8, asserted at the SOURCE because it is a claim about
        what does not exist. A gesture that could create a field→rule edge would
        have to call something; there is nothing for it to call, and the board's
        own markup gives the read lane no click handler at all."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                 'transform_flow_board.js'))
        xml = _strip_xml_comments(
            _src('pb_formula_studio', 'static', 'src', 'xml',
                 'transform_flow_board.xml'))
        # the only write callbacks the board declares
        self.assertIn('onDraw', js)
        self.assertIn('onDelete', js)
        # ...and the left lane's card carries no click/dblclick/drag handler
        lane = xml.split('data-lane="left"')[1].split('</div>')[0]
        for evt in ('t-on-click', 't-on-dblclick', 't-on-dragstart', 't-on-drop'):
            self.assertNotIn(evt, lane,
                             "the read lane must offer no gesture that writes")
        # and it says where inputs ARE edited
        self.assertIn('readsHint', xml)
        self.assertIn('open the rule to change it', js)

    # =====================================================================
    # 3 — wire truth: every feed edge is a real row or a real binding (case 3)
    # =====================================================================
    def test_03a_a_wire_edge_matches_a_mapping_row(self):
        cfg = self._config('J4 Wire Truth')
        conn = self._connector()
        r = self._trule(conn, 'OTHRSX')
        m = self._wire(conn, self.ot15, 'OTHRSX')
        d = self._flow(cfg, conn)
        edges = [w for w in d['wires'] if not w['bind']]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]['ref'], m.id)
        self.assertEqual(edges[0]['ruleId'], r.id)
        self.assertEqual(edges[0]['rightId'], self.ot15.id)

    def test_03b_a_binding_with_no_wire_is_an_edge_too(self):
        """The resolver reads an explicit `('rule', key)` binding at rung 1; a
        component fed that way is fed as truly as one behind a wire, and a board
        that drew only the wires would report it as unread."""
        cfg = self._config('J4 Binding')
        conn = self._connector()
        r = self._trule(conn, 'DEPCNT')
        self.deps.set_source_binding('rule', 'DEPCNT', origin='board')
        d = self._flow(cfg, conn)
        binds = [w for w in d['wires'] if w['bind']]
        self.assertEqual(len(binds), 1)
        self.assertEqual(binds[0]['ruleId'], r.id)
        self.assertEqual(binds[0]['rightId'], self.deps.id)
        self.assertEqual(binds[0]['ref'], 0, "a binding is not a deletable row")

    def test_03c_a_wire_and_a_binding_to_one_target_is_one_edge(self):
        cfg = self._config('J4 No Double')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        self._wire(conn, self.ot15, 'OTHRSX')
        self.ot15.set_source_binding('rule', 'OTHRSX', origin='board')
        d = self._flow(cfg, conn)
        to_ot = [w for w in d['wires'] if w['rightId'] == self.ot15.id]
        self.assertEqual(len(to_ot), 1, "one relationship, one line on the board")
        self.assertFalse(to_ot[0]['bind'], "and the ROW wins, because it is deletable")

    def test_03d_a_wire_into_another_scheme_is_not_this_board_s(self):
        cfg = self._config('J4 Scope A')
        other = self._config('J4 Scope B')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        self._wire(conn, other.rule_ids[0], 'OTHRSX')
        d = self._flow(cfg, conn)
        self.assertEqual([w for w in d['wires'] if not w['bind']], [],
                         "a board scoped to one scheme shows that scheme's wires")

    # =====================================================================
    # 4 — health, and the ONE definition of unread (case 7)
    # =====================================================================
    def test_04a_a_rule_nothing_reads_is_amber(self):
        cfg = self._config('J4 Unread')
        conn = self._connector()
        self._trule(conn, 'LONELY')
        d = self._flow(cfg, conn)
        card = d['rules'][0]
        self.assertEqual(card['health'], 'unread')
        self.assertEqual(card['feeds'], [])
        self.assertEqual(d['counts']['unread'], 1)

    def test_04b_wiring_it_clears_the_state(self):
        cfg = self._config('J4 Unread Clears')
        conn = self._connector()
        self._trule(conn, 'LONELY')
        self.assertEqual(self._flow(cfg, conn)['counts']['unread'], 1)
        self._wire(conn, self.ot15, 'LONELY')
        d = self._flow(cfg, conn)
        self.assertEqual(d['counts']['unread'], 0)
        self.assertEqual(d['rules'][0]['health'], 'ok')
        self.assertTrue(d['rules'][0]['feeds'], "and it names what reads it")

    def test_04c_unread_has_exactly_one_definition(self):
        """The board and the Integrations cockpit must not be able to disagree.
        Asserted by AGREEMENT on a live fixture rather than by grepping for a
        method name — a second definition would pass a grep and fail here."""
        Itg = self.env.get('pb.integrations')
        if Itg is None:
            self.skipTest('pb_integrations is not installed on this build')
        cfg = self._config('J4 One Truth')
        conn = self._connector()
        lonely = self._trule(conn, 'LONELY')
        fed = self._trule(conn, 'FEDKEY')
        self._wire(conn, self.ot15, 'FEDKEY')
        d = self._flow(cfg, conn)
        by_id = {c['id']: c for c in d['rules']}
        self.assertEqual(by_id[lonely.id]['feeds'], Itg._rule_consumers(lonely))
        self.assertEqual(by_id[fed.id]['feeds'], Itg._rule_consumers(fed))
        self.assertEqual(by_id[lonely.id]['feeds'], [])
        self.assertTrue(by_id[fed.id]['feeds'])
        # and the board CALLS it rather than restating it
        py = _src('pb_formula_studio', 'models', 'pb_formula_studio.py')
        self.assertIn('_rule_consumers', py)

    def test_04d_env_get_is_tested_against_none_not_truthiness(self):
        """MJ16, verbatim, and the reason it gets its own test: an empty
        recordset is FALSY, so `if Model:` takes the fallback branch on every
        call — the board would report every output unread, forever, silently,
        while returning a well-formed successful payload."""
        py = _src('pb_formula_studio', 'models', 'pb_formula_studio.py')
        body = py.split('def _tf_consumers')[1].split('@api.model')[0]
        self.assertIn('is None', body)
        self.assertNotRegex(body, r'if\s+Itg\s*:')

    def test_04e_a_severed_wire_renders_the_severed_state(self):
        cfg = self._config('J4 Severed')
        conn = self._connector()
        r = self._trule(conn, 'OTHRSX')
        m = self._wire(conn, self.ot15, 'OTHRSX')
        m.is_severed = True
        d = self._flow(cfg, conn)
        card = next(c for c in d['rules'] if c['id'] == r.id)
        self.assertEqual(card['health'], 'severed')
        self.assertEqual(d['counts']['severed'], 1)
        self.assertTrue(next(w for w in d['wires'] if w['ref'] == m.id)['severed'])

    def test_04f_severed_outranks_unread(self):
        """A rule can be several things at once and the card shows ONE. The
        order is worst-first: a lost target is a broken thing, an unread output
        is an idle one."""
        cfg = self._config('J4 Precedence')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        m = self._wire(conn, self.ot15, 'OTHRSX')
        m.is_severed = True
        self.assertEqual(self._flow(cfg, conn)['rules'][0]['health'], 'severed')

    def test_04g_counts_are_what_the_header_sentence_says(self):
        cfg = self._config('J4 Counts')
        conn = self._connector()
        self._trule(conn, 'LONELY')
        self._trule(conn, 'FEDKEY')
        self._wire(conn, self.ot15, 'FEDKEY')
        c = self._flow(cfg, conn)['counts']
        self.assertEqual(c['rules'], 2)
        self.assertEqual(c['unread'], 1)
        self.assertEqual(c['fed'], 1)
        for k in ('rules', 'unread', 'drift', 'severed', 'fed'):
            self.assertIsInstance(c[k], int)

    # =====================================================================
    # 5 — the right lane is the API board's right lane (case 2 / case 5)
    # =====================================================================
    def test_05a_components_come_from_the_shared_builder(self):
        cfg = self._config('J4 Right')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        d = self._flow(cfg, conn)
        api = self.Studio.api_mapping_data(cfg.id, conn.id)
        self.assertEqual([i['id'] for i in d['right']],
                         [i['id'] for i in api['right']],
                         "one component vocabulary, or the two boards disagree")

    def test_05b_the_conflict_probe_reaches_this_board_unchanged(self):
        """J4 draws through the `api` prefix, so J3's guardrail fires here for
        the same reason it fires there — not because a second implementation
        remembered to."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                 'mapping_studio.js'))
        self.assertRegex(js, r'transform:\s*"api"',
                         "the transform board must route through the api adapter")
        # exactly one probe call site in the host
        self.assertEqual(js.count('source_conflict_probe'), 1)

    def test_05c_probe_answers_for_a_rule_key_target(self):
        cfg = self._config('J4 Probe')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        before = self.FieldMapping.search_count([])
        r = self.Studio.source_conflict_probe(cfg.id, 'api', self.ot15.id,
                                              'OTHRSX', conn.id)
        self.assertTrue(r['ok'])
        self.assertEqual(self.FieldMapping.search_count([]), before,
                         "the probe writes nothing — MF37's oracle, in a test")

    # =====================================================================
    # 6 — the write path is the EXISTING one (case 4)
    # =====================================================================
    def test_06a_draw_then_cut_leaves_the_database_as_found(self):
        cfg = self._config('J4 Round Trip')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        before = self.FieldMapping.search_count([])
        before_bind = (self.ot15.source_binding, self.ot15.source_binding_key)
        r = self.Studio.api_mapping_create(cfg.id, conn.id, 'OTHRSX',
                                           self.ot15.id, False)
        self.assertTrue(r.get('ok'))
        self.assertEqual(self.FieldMapping.search_count([]), before + 1)
        m = self.FieldMapping.search([('connector_id', '=', conn.id),
                                      ('source_field', '=', 'OTHRSX')], limit=1)
        self.assertTrue(m)
        self.Studio.api_mapping_delete(m.id)
        self.assertEqual(self.FieldMapping.search_count([]), before)
        self.assertEqual((self.ot15.source_binding, self.ot15.source_binding_key),
                         before_bind, "and the binding it set is put back")

    def test_06b_a_drawn_wire_classifies_as_kind_rule(self):
        """The whole reason J4 needed no new adapter: an output key is already a
        legal `source_field` and `api_mapping_create` already recognises one."""
        cfg = self._config('J4 Kind')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        self.Studio.api_mapping_create(cfg.id, conn.id, 'OTHRSX',
                                       self.ot15.id, False)
        self.assertEqual(self.ot15.source_binding, 'rule')
        self.assertEqual(self.ot15.source_binding_key, 'OTHRSX')

    def test_06c_a_plain_feed_field_still_binds_as_feed(self):
        """The other half of the same claim — the classification is a real test
        of the key, not a constant this board turned on."""
        cfg = self._config('J4 Kind Feed')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        self.Studio.api_mapping_create(cfg.id, conn.id, 'Basic_Salary',
                                       self.deps.id, False)
        self.assertEqual(self.deps.source_binding, 'feed')

    # =====================================================================
    # 7 — empty states, and the payload contract (cases 9, 11)
    # =====================================================================
    def test_07a_a_connector_with_no_rules_says_so_and_is_not_an_error(self):
        cfg = self._config('J4 No Rules')
        conn = self._connector()
        d = self._flow(cfg, conn)
        self.assertFalse(d['ok'])
        self.assertEqual(d['reason'], 'no_rules')
        self.assertIn('can_edit', d, "the empty state offers a verb, so it needs the right")
        self.assertEqual(d['connector']['id'], conn.id)

    def test_07a2_the_board_opens_on_a_connector_that_HAS_rules(self):
        """abm's live defect, turned into a test. The API heuristic answers the
        connector the scheme's WIRES point at; this board asks a different
        question, and opening it on the one connector with no transformations
        shows an empty state over a database with eight rules in it."""
        cfg = self._config('J4 Default Connector')
        bare = self._connector('J4 Bare')
        rich = self._connector('J4 Rich')
        self._trule(rich, 'OTHRSX')
        picked = self.Studio._tf_active_connector(cfg, None)
        self.assertEqual(picked.id, rich.id,
                         "a rule-less connector is not this board's default")
        self.assertNotEqual(picked.id, bare.id)

    def test_07a3_an_explicit_choice_is_never_second_guessed(self):
        cfg = self._config('J4 Explicit')
        bare = self._connector('J4 Bare 2')
        rich = self._connector('J4 Rich 2')
        self._trule(rich, 'OTHRSX')
        self.assertEqual(self.Studio._tf_active_connector(cfg, bare.id).id, bare.id,
                         "the picker and the deep link always win")
        d = self.Studio.transform_flow_data(cfg.id, bare.id)
        self.assertEqual(d.get('reason'), 'no_rules',
                         "and the empty state is the honest answer for THAT choice")

    def test_07a4_the_api_heuristic_is_not_modified(self):
        """A shared helper changed under four other callers to suit one board is
        exactly the fork this phase exists to avoid."""
        py = _src('pb_formula_studio', 'models', 'pb_formula_studio.py')
        body = py.split('def _tf_active_connector')[1].split('def transform_flow_data')[0]
        self.assertIn('_api_active_connector', body,
                      "the new default DELEGATES to the old heuristic")

    def test_07b_no_connector_is_its_own_reason(self):
        """And an ARCHIVED connector is not a default. A rule outlives its
        connector being archived, so without that guard the board would open on
        a system somebody deliberately retired and `no_connector` would be
        unreachable on any database that had ever held a rule."""
        cfg = self._config('J4 No Connector')
        self.Connector.search([]).write({'active': False})
        self.assertFalse(self.Studio._tf_active_connector(cfg, None))
        d = self.Studio.transform_flow_data(cfg.id, False)
        self.assertFalse(d['ok'])
        self.assertEqual(d['reason'], 'no_connector')

    def test_07c_the_payload_shape_is_stable(self):
        cfg = self._config('J4 Shape')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        d = self._flow(cfg, conn)
        for k in ('ok', 'can_edit', 'context_id', 'contexts', 'connector',
                  'left', 'rules', 'right', 'reads', 'wires', 'counts'):
            self.assertIn(k, d)
        self.assertIsInstance(d['left'], list)
        self.assertIsInstance(d['rules'], list)
        self.assertIsInstance(d['wires'], list)

    def test_07d_the_rpc_writes_nothing(self):
        cfg = self._config('J4 Read Only')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        self._wire(conn, self.ot15, 'OTHRSX')
        before = (self.FieldMapping.search_count([]),
                  self.TRule.search_count([]),
                  self.ot15.source_binding, self.ot15.source_binding_key)
        for _ in range(3):
            self._flow(cfg, conn)
        self.assertEqual((self.FieldMapping.search_count([]),
                          self.TRule.search_count([]),
                          self.ot15.source_binding, self.ot15.source_binding_key),
                         before, "reading the board may never move a row")

    def test_07e_api_mapping_data_is_still_additive(self):
        cfg = self._config('J4 Additive')
        conn = self._connector()
        self._trule(conn, 'OTHRSX')
        d = self.Studio.api_mapping_data(cfg.id, conn.id)
        missing = PRE_J4_API_TOP_LEVEL - set(d)
        self.assertFalse(missing, "J4 removed keys the client reads: %s" % missing)

    # =====================================================================
    # 8 — the tab, the composer reuse, and the white-label absolute
    # =====================================================================
    def test_08a_the_tab_sits_between_api_and_spreadsheet(self):
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                 'mapping_studio.js'))
        block = js.split('export const MODES')[1].split('];')[0]
        ids = re.findall(r'id:\s*"([a-z]+)"', block)
        # J5 put the Journey in front of the strip, so an ABSOLUTE slice is the
        # wrong assertion — it pins where the tab happens to sit rather than
        # what J4 actually claimed, which is that a transformation reads what
        # the system sent (the tab to its LEFT) and feeds a component (the tab
        # to its RIGHT). Stated relatively, that claim survives any number of
        # tabs being added anywhere else.
        self.assertEqual(ids.index('transform'), ids.index('api') + 1,
                         "Transformations must sit immediately after the "
                         "System fields tab it reads from")
        self.assertEqual(ids.index('import'), ids.index('transform') + 1,
                         "…and immediately before the Spreadsheet tab")
        self.assertIn('Transformations', block)

    def test_08a2_an_unchosen_connector_is_re_derived_per_board(self):
        """The five boards ask different questions of one connector list and
        their heuristics honestly disagree. A user's CHOICE must survive a tab
        switch; a default must not, or switching to this tab lands on the one
        system with no transformations."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                 'mapping_studio.js'))
        self.assertIn('connectorPicked', js)
        # the picker sets it, and a deep link that NAMES one counts as a choice
        self.assertIn('this.state.connectorPicked = true;', js)
        # …and the transform load respects it
        call = js.split('"transform_flow_data",', 1)[1].split('break;', 1)[0]
        self.assertIn('connectorPicked', call)

    def test_08a3_the_header_never_names_a_connector_it_is_not_showing(self):
        """W76.3/W117's bug class: a header that names one system while the
        lanes show another looks right and describes the wrong thing."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                 'mapping_studio.js'))
        adopt = js.split('this.state.mode === "transform" && r && r.context_id')[1] \
                  .split('}')[0]
        self.assertIn('this.state.connectorId = r.context_id', adopt)

    def test_08b_the_composer_is_imported_not_rebuilt(self):
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                 'mapping_studio.js'))
        self.assertIn('@pb_integrations/js/rule_composer', js,
                      "J4 opens the existing composer; it does not grow a second one")
        self.assertIn('RuleComposer', js)
        # and the board itself authors nothing
        board = _strip_js_comments(
            _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                 'transform_flow_board.js'))
        for forbidden in ('rule_save', 'rule_propose', 'rule_preview'):
            self.assertNotIn(forbidden, board,
                             "the board must never author a rule itself")

    def test_08c_the_hard_dependency_is_declared(self):
        """An undeclared cross-module import is a dead import on the first
        database that installs one module and not the other, and it takes the
        whole backend bundle with it."""
        manifest = _src('pb_formula_studio', '__manifest__.py')
        depends = manifest.split("'depends'")[1].split(']')[0]
        self.assertIn('pb_integrations', depends)

    def test_08d_no_user_visible_odoo(self):
        """The white-label absolute, over every string J4 added."""
        for parts in (('static', 'src', 'js', 'mapping', 'transform_flow_board.js'),
                      ('static', 'src', 'xml', 'transform_flow_board.xml'),
                      ('static', 'src', 'scss', 'transform_flow.scss')):
            src = _src('pb_formula_studio', *parts)
            body = (_strip_js_comments(src) if parts[-1].endswith('.js')
                    else _strip_xml_comments(src))
            # the module pragma is a technical identifier, not a user string
            body = body.replace('/** @odoo-module **/', '')
            body = re.sub(r'@odoo/owl', '', body)
            self.assertNotIn('Odoo', body, 'user-visible "Odoo" in %s' % parts[-1])
            self.assertNotIn('odoo', body.replace('@odoo', ''),
                             'user-visible "odoo" in %s' % parts[-1])

    def test_08e_the_enter_on_button_guard_is_present(self):
        """MF33 — a root-level keydown handler steals Enter from every button
        inside it, and on this board the fall-through would DRAW A WIRE."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                 'transform_flow_board.js'))
        body = js.split('onKeydown(ev)')[1].split('\n    }')[0]
        # the Enter/Space guard is the FIRST branch, and it must return before
        # anything else can run
        guard = body.split('if (ev.key === "/"')[0]
        self.assertIn('BUTTON', guard)
        self.assertIn('return', guard)
        self.assertNotIn('INPUT', guard,
                         "INPUT is deliberately NOT guarded here — Enter in the "
                         "search box is the board's own promise (MF33)")
        # …and the guard really is first: nothing that writes precedes it
        self.assertNotIn('onDraw', guard)

    def test_08f_the_geometry_kernel_is_reused_not_forked(self):
        js = _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                  'transform_flow_board.js')
        self.assertIn('from "./mapping_geometry"', js)
        for fn in ('wireGeometry', 'clampY', 'aggregateDocks', 'spreadHubs',
                   'itemMatches'):
            self.assertIn(fn, js)
        # and MappingCanvas is NOT touched by this phase
        self.assertNotIn('mapping_canvas', js)
