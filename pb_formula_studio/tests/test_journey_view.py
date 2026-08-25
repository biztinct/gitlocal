# -*- coding: utf-8 -*-
"""JOURNEY J5 — the Journey view: five lanes, one read, no writes.

Five claims, each asserted against a different oracle because each one fails
QUIETLY if it is wrong:

  * **the via -> bucket map is exhaustive, in both directions.** This is the
    phase's one genuinely new piece of vocabulary arithmetic and it is the one
    most likely to rot: a nineteenth `via` lands in `input_provenance.VIAS`,
    nothing crashes, and its values are silently counted as "used a default"
    forever. So the map is compared to the vocabulary SET-WISE — a `via` with no
    bucket fails, and a bucket for a `via` that no longer exists fails too,
    because a stale key is how a map starts lying about what it covers.
  * **the aggregate is arithmetic, and it is tested as arithmetic.** On fixtures
    built in this file, never against a live run: the handover forbids
    `action_process` on a live database and a test that needs a processed batch
    to prove a sum is a test nobody can run.
  * **the Journey composes; it does not define.** Its conflict count is J3's
    detector, its unread count is J4's predicate, its component picture is the
    `_declared_source` family. Asserted by making the two AGREE ON A FIXTURE
    rather than by grepping for a method name — a second implementation would
    pass a grep and fail this.
  * **every pre-existing deep link still lands where it landed.** J5 changes the
    cold-start default, which is the single highest-risk edit in the phase: get
    it wrong and six doors quietly move. Each documented door is checked
    individually, from source.
  * **the Journey writes NOTHING.** Asserted here as a source property (no write
    verb anywhere in the adapter and its helpers) and live as an MF37 database
    diff, because neither check is sufficient alone: the grep cannot see an ORM
    write behind a helper, and a diff cannot prove the absence of a path nobody
    happened to walk.

Wording lives here rather than in hoot because these are server strings behind
`_()`, and because hoot cannot stringify a module-scope `_t` at all (MJ3).
"""
import json
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models import input_provenance


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip_js_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return re.sub(r'^\s*//.*$', '', src, flags=re.M)


#: Every door into the Mapping cockpit that existed before J5, and the mode it
#: has always landed on. `None` means "arrives without naming a mode", i.e. a
#: cold start — the two arrivals J5 deliberately moves onto the Journey.
PRE_J5_DOORS = {
    ('pb_integrations', 'static/src/js/integrations.js'): 'pb_mode: "api"',
    ('pb_import_advanced', 'static/src/js/connector_cockpit.js'): 'pb_mode: "api"',
    # Formula Studio's door takes the mode as an ARGUMENT and defaults it, so
    # the fact to pin is the default, not a literal key/value pair. Asserting
    # the pair would have failed against perfectly correct code — which is
    # exactly what it did on the first run.
    ('pb_formula_studio', 'static/src/js/formula_studio.js'):
        'const ctx = { pb_mode: mode || "employee" };',
    ('pb_settings', 'static/src/js/settings_hub.js'): None,
    ('pb_hub', 'static/src/js/hub_palette_entries.js'): None,
}


@tagged('post_install', '-at_install')
class TestJourneyView(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.config = cls.env['hr.formula.config'].search([], limit=1)

    # ==================================================================
    # 1. the via -> bucket contract (the phase's pinned invariant)
    # ==================================================================
    def test_01a_every_via_has_exactly_one_bucket(self):
        """Set equality with the vocabulary, both directions.

        A `via` with no bucket would be counted as `default` in silence — a
        number on the landing tab that is wrong and looks fine. A bucket for a
        `via` that no longer exists is the same disease in the other direction:
        the map claims coverage it no longer has, and the next reader trusts it.
        """
        mapped = set(self.Studio._JOURNEY_VIA_BUCKETS)
        vocab = set(input_provenance.VIAS)
        self.assertEqual(
            mapped - vocab, set(),
            "These vias are bucketed but are no longer in input_provenance.VIAS. "
            "Remove them from _JOURNEY_VIA_BUCKETS.")
        self.assertEqual(
            vocab - mapped, set(),
            "These vias have NO bucket, so the pay-run lane is silently "
            "counting them as 'default'. Add them to _JOURNEY_VIA_BUCKETS with "
            "a deliberate family.")

    def test_01b_every_bucket_is_a_declared_bucket(self):
        """No value of the map may name a family the board cannot render."""
        declared = set(self.Studio._JOURNEY_BUCKETS)
        used = set(self.Studio._JOURNEY_VIA_BUCKETS.values())
        self.assertEqual(used - declared, set(),
                         "A via is bucketed into a family _JOURNEY_BUCKETS does "
                         "not declare; the board will drop those values.")

    def test_01c_the_families_say_what_they_mean(self):
        """Spot-check the load-bearing rows, so a careless re-shuffle is caught.

        Not every row — that would just restate the dict. These five are the
        ones whose placement is a JUDGEMENT rather than an obvious reading, and
        each one is the difference between "this scheme is wired" and "this
        scheme is limping".
        """
        b = self.Studio._JOURNEY_VIA_BUCKETS
        self.assertEqual(b['binding'], 'wired')
        self.assertEqual(b['connector_mapping'], 'wired')
        # J-D4's read-back half: the row that WRITES the record on import is
        # READ BACK when the file or feed is empty, which is a fallback.
        self.assertEqual(b['employee_mapping'], 'fallback')
        self.assertEqual(b['binding_empty'], 'fallback')
        # An adjustment that INVENTED the code did not fall back and is not a
        # default; it is the fourth family, and this is the row that says so.
        self.assertEqual(b['proration'], 'computed')

    def test_01d_an_unknown_via_degrades_and_does_not_raise(self):
        """The runtime must never be the thing that takes the tab down.

        The map is pinned LOUDLY by test 01a, at the point a developer adds a
        via. At the point a USER opens the tab the only safe behaviour is to
        count it somewhere and carry on, so this asserts the degradation exists
        and lands on `default`.
        """
        self.assertEqual(self.Studio._journey_bucket_for_via('no_such_via_x'),
                         'default')
        self.assertEqual(self.Studio._journey_bucket_for_via(None), 'default')
        self.assertEqual(self.Studio._journey_bucket_for_via(''), 'default')

    # ==================================================================
    # 2. the aggregate, on fixtures (never on a live run)
    # ==================================================================
    def _blob(self, entries):
        return json.dumps({
            code: input_provenance.entry(**kw) for code, kw in entries.items()
        })

    def test_02a_aggregate_counts_values_not_payslips(self):
        blobs = [
            self._blob({
                'BASESALARY': {'src': 'excel', 'key': 'Base', 'via': 'binding'},
                'OTHOURS': {'src': 'feed', 'key': 'ot', 'via': 'connector_mapping'},
                'ALLOW': {'src': 'none', 'via': 'default'},
            }),
            self._blob({
                'BASESALARY': {'src': 'excel', 'key': 'Base', 'via': 'binding'},
                'DEPS': {'src': 'employee_field', 'via': 'employee_mapping'},
            }),
        ]
        agg = self.Studio._journey_aggregate(blobs)
        self.assertEqual(agg['slips'], 2)
        self.assertEqual(agg['values'], 5, "three plus two components")
        self.assertEqual(agg['by_src']['excel'], 2)
        self.assertEqual(agg['by_src']['feed'], 1)
        self.assertEqual(agg['by_bucket']['wired'], 3,
                         "two bindings and one connector mapping")
        self.assertEqual(agg['by_bucket']['fallback'], 1, "the employee mapping")
        self.assertEqual(agg['by_bucket']['default'], 1)
        self.assertEqual(agg['by_bucket']['computed'], 0)

    def test_02b_every_bucket_key_is_present_even_at_zero(self):
        """The board reads `by_bucket[k]`; a missing key is a rendering crash
        waiting for the first run that happens to have no fallbacks."""
        agg = self.Studio._journey_aggregate([])
        for bucket in self.Studio._JOURNEY_BUCKETS:
            self.assertIn(bucket, agg['by_bucket'])
            self.assertEqual(agg['by_bucket'][bucket], 0)
        self.assertEqual(agg['slips'], 0)
        self.assertEqual(agg['values'], 0)

    def test_02c_the_buckets_sum_to_the_values(self):
        """The arithmetic gate. Every value lands in exactly one family, so the
        four columns the board prints add up to the number beside them — which
        is the only reason a reader is entitled to trust either."""
        blobs = [self._blob({
            'A': {'src': 'excel', 'via': 'binding'},
            'B': {'src': 'excel', 'via': 'fallback', 'fell_back': True},
            'C': {'src': 'constant', 'via': 'constant'},
            'D': {'src': 'calculated', 'via': 'retro', 'adj': ['retro']},
            'E': {'src': 'employee_field', 'via': 'contract'},
        })]
        agg = self.Studio._journey_aggregate(blobs)
        self.assertEqual(sum(agg['by_bucket'].values()), agg['values'])
        self.assertEqual(sum(agg['by_src'].values()), agg['values'])
        self.assertEqual(agg['by_bucket']['computed'], 1, "the retro")
        self.assertEqual(agg['fell_back'], 1)

    def test_02d_an_unreadable_blob_is_counted_as_unreadable(self):
        """Not as a payslip with no values. The two are different facts and
        collapsing them would make a parse failure look like an empty run."""
        agg = self.Studio._journey_aggregate(['{not json', None, '[]', '{}'])
        self.assertEqual(agg['unreadable'], 3,
                         "the broken string, the None and the list")
        self.assertEqual(agg['slips'], 1, "only the empty dict is a payslip")
        self.assertEqual(agg['values'], 0)

    def test_02e_an_unknown_via_in_a_real_blob_still_totals(self):
        """The degradation of 01d, exercised through the aggregate: a blob
        written by a future resolver must not make the sums stop adding up."""
        agg = self.Studio._journey_aggregate([
            json.dumps({'A': {'src': 'excel', 'via': 'from_the_future'}})])
        self.assertEqual(agg['values'], 1)
        self.assertEqual(sum(agg['by_bucket'].values()), 1)

    # ==================================================================
    # 3. the payload composes what already existed
    # ==================================================================
    def test_03a_payload_shape(self):
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        self.assertTrue(d['ok'])
        for lane in ('systems', 'feeds', 'transforms', 'scheme', 'run'):
            self.assertIn(lane, d['lanes'], "a lane the board renders is missing")
        self.assertTrue(d['lanes']['scheme'], "the scheme lane is never empty")
        self.assertTrue(d['lanes']['run'], "the run lane always has at least a ghost")
        for key in ('components', 'wired', 'fallback', 'attention'):
            self.assertIn(key, d['header'])

    def test_03b_every_node_has_the_uniform_shape(self):
        """One template renders all five lanes, so every node owes it an id, a
        kind, a lane and a label. A node missing one renders as an empty card,
        which is indistinguishable from a bug in the data behind it."""
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        seen = set()
        for lane, nodes in d['lanes'].items():
            for n in nodes:
                for key in ('id', 'kind', 'lane', 'label'):
                    self.assertIn(key, n, "node %r in lane %s" % (n.get('id'), lane))
                self.assertEqual(n['lane'], lane,
                                 "a node's `lane` must match the lane it is in")
                self.assertNotIn(n['id'], seen,
                                 "node ids are the geometry's keys and must be "
                                 "unique across the whole board")
                seen.add(n['id'])

    def test_03c_every_edge_names_two_real_nodes(self):
        """An edge to an id no node carries draws nothing and is invisible —
        the picture would silently understate the wiring, which on this tab is
        the worst possible failure."""
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        ids = {n['id'] for nodes in d['lanes'].values() for n in nodes}
        for e in d['edges']:
            self.assertIn(e['from'], ids, "edge from an unknown node")
            self.assertIn(e['to'], ids, "edge to an unknown node")
            self.assertIn('kind', e)

    def test_03d_the_primary_connector_is_the_config_field(self):
        """J-D5 and the handover's flat instruction: the marker is
        `hr.formula.config.connector_id`, NEVER `_api_active_connector`'s
        most-mappings heuristic — which is documented picking the wrong
        connector on abm and is not what the runtime gate reads."""
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        self.assertEqual(d['primary_id'], self.config.connector_id.id or 0)
        marked = [n for n in d['lanes']['systems'] if n.get('primary')]
        if self.config.connector_id:
            self.assertEqual(len(marked), 1, "exactly one connection is primary")
            self.assertEqual(marked[0]['id'], 'c:%s' % self.config.connector_id.id)
        else:
            self.assertFalse(marked, "no connector_id means nothing is primary")

    def test_03d2_a_scheme_that_names_no_connection_says_its_wires_are_inert(self):
        """The state every live database is actually in, and the single most
        useful thing this tab says.

        No scheme on any of the four databases has `connector_id` set (SOURCING
        S20), and the resolver's pre-pass is gated on exactly that field
        (`payroll_import_batch`: `if self.source_type == 'api_data_store' and
        config.connector_id:`). So a scheme with wires and no connection has a
        pipe that is not connected at the tap — abm has 33 wires drawn into it
        and every one is inert. A Journey that drew those wires confidently and
        said nothing would be the exact opposite of this programme's point.
        """
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Journey = self.Studio.journey_data(self.config.id)
        wired_conns = [n for n in d['lanes']['systems']
                       if n['kind'] == 'connector' and n.get('wires')]
        if self.config.connector_id or not wired_conns:
            self.skipTest("this scheme names a connection, or has no wires")
        health = [n for n in d['lanes']['scheme'] if n['id'] == 'h:noprimary']
        self.assertEqual(len(health), 1,
                         "a scheme with wires and no chosen connection must "
                         "raise it — silently drawing inert wires is worse "
                         "than drawing none")
        self.assertEqual(
            health[0]['label'].split()[0],
            str(sum(n['wires'] for n in wired_conns)),
            "the health node counts the wires that are not read")
        for n in wired_conns:
            self.assertTrue(n.get('dimmed'),
                            "%s carries wires nothing reads and must be dimmed"
                            % n['id'])
            self.assertTrue(n.get('chip'), "…and must say why")

    def test_03e_conflicts_are_J3s_detector(self):
        """Agreement on a fixture, not a grep. A second implementation would
        pass a source search for `_source_conflicts` and disagree here."""
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        self.assertEqual(d['counts']['conflicts'],
                         len(self.Studio._source_conflicts(self.config)))

    def test_03f_unread_is_J4s_predicate(self):
        """Same shape, one module out: `_tf_consumers` delegates to
        `pb.integrations._rule_consumers`, which is the ONE definition."""
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        Rule = self.env.get('hr.api.transformation.rule')
        if Rule is None:
            self.skipTest("no transformation rules on this database")
        expect = 0
        for r in Rule.with_context(active_test=False).search([]):
            key = (r.output_key or '').strip()
            if key and not self.Studio._tf_consumers(r):
                expect += 1
        self.assertEqual(d['counts']['unread'], expect)

    def test_03g_the_component_picture_adds_up(self):
        """Every component lands in exactly one column of the scheme lane. If
        the six counts do not sum to the total, the bar is drawing a fiction."""
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        c = d['lanes']['scheme'][0]['counts']
        self.assertEqual(
            c['wired'] + c['calculated'] + c['constant'] + c['contract']
            + c['people'] + c['unfed'], c['total'],
            "the component picture must partition the scheme")
        self.assertEqual(c['total'], len(self.config.rule_ids))
        self.assertEqual(d['header']['components'], c['total'])
        self.assertEqual(d['header']['wired'], c['wired'])

    def test_03h_wired_is_the_declared_source_family(self):
        """The Journey's "wired" and the mapping boards' source chips must be
        the same components, or two screens describe one scheme differently."""
        if not self.config:
            self.skipTest("no formula config on this database")
        emp = self.Studio._source_employee_dest_ids(self.config)
        wires = self.Studio._source_wire_dests(self.config)
        expect = len([
            r for r in self.config.rule_ids
            if self.Studio._declared_source(r, emp, wires)['kind']
            in ('excel', 'feed', 'rule')])
        d = self.Studio.journey_data(self.config.id)
        self.assertEqual(d['header']['wired'], expect)

    def test_03i_a_bank_row_is_not_counted_as_fallback_capable(self):
        """J3 S1's exception, and the reason the fallback count has its own
        query: `get_mapped_input_value` reads employee and contract FIELDS back
        and never bank parts, so a bank row is the import half only. Counting
        it would put a number in the header sentence the resolver would never
        honour."""
        if not self.config:
            self.skipTest("no formula config on this database")
        total, read_back, bank = self.Studio._journey_people_mappings(self.config)
        Mapping = self.env['hr.payslip.import.mapping']
        rows = Mapping.sudo().search(
            [('salary_structure_id', '=', self.config.id)])
        self.assertEqual(total, len(rows))
        self.assertEqual(
            bank, len(rows.filtered(lambda m: m.destination_type == 'bank_account')))
        for rid in read_back:
            self.assertTrue(
                rows.filtered(lambda m: m.component_id.id == rid
                              and m.destination_type != 'bank_account'),
                "a read-back component must have a non-bank row")

    def test_03j_the_run_lane_is_a_ghost_when_nothing_was_processed(self):
        if not self.config:
            self.skipTest("no formula config on this database")
        done = self.env['hr.payroll.import.batch'].sudo().search_count(
            [('formula_config_id', '=', self.config.id), ('state', '=', 'done')])
        node = self.Studio.journey_data(self.config.id)['lanes']['run'][0]
        if done:
            self.assertFalse(node.get('ghost'))
            self.assertIn('agg', node)
        else:
            self.assertTrue(node.get('ghost'),
                            "no processed batch must render the honest ghost, "
                            "never an empty tally that reads as a run of zero")
            self.assertTrue(node.get('door'), "a ghost still has a door")

    def test_03k_every_ghost_has_a_door(self):
        """The empty world is the novice's first screen. A ghost that cannot be
        clicked is a dead end dressed as an invitation."""
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        for nodes in d['lanes'].values():
            for n in nodes:
                if n.get('ghost'):
                    self.assertTrue(n.get('door'),
                                    "ghost %r has no door" % n['id'])
                    self.assertTrue(n['door'].get('mode'))

    def test_03k2_an_empty_world_ghosts_every_lane_it_can(self):
        """Handover case 9, stated precisely enough to be true on any database.

        The first cut asserted all five lanes ghost on an empty scheme, and it
        failed on abm against perfectly correct code — because two of the five
        lanes describe the DATABASE, not the scheme. abm has two connectors,
        fourteen feeds and eight rules; a brand new scheme there is empty, and
        those lanes are still rightly full. Only three lanes are per-scheme
        (the file, the records, the run) and one is the scheme itself.

        So: the per-scheme lanes must ALWAYS ghost on a scheme with nothing on
        it, and the database-wide lanes must ghost exactly when the database is
        empty of that thing. That is the invariant; "all five" was a
        description of one particular database. (The genuinely empty world —
        all five ghosted — is exercised on acme, which has no connectors at
        all; see the phase report.)
        """
        cfg = self.env['hr.formula.config'].create({
            'name': 'ZZ J5 empty world (test)', 'code': 'ZZJ5T',
            'country_code': 'VN'})
        d = self.Studio.journey_data(cfg.id)
        self.assertTrue(d['ok'])
        self.assertEqual(d['header']['components'], 0)

        def ghosts(lane):
            return [n for n in d['lanes'][lane] if n.get('ghost')]

        # ---- per-SCHEME lanes: always a ghost, always with a door ----------
        self.assertTrue(ghosts('scheme'),
                        "a scheme with no columns must ghost — the real card "
                        "with an empty component bar reads as a broken chart")
        self.assertTrue(ghosts('run'), "no processed batch must ghost")
        systems = {n['id']: n for n in d['lanes']['systems']}
        self.assertTrue(systems['file'].get('ghost'), "no file read yet")
        self.assertTrue(systems['records'].get('ghost'), "nothing mapped yet")

        # ---- database-wide lanes: ghost exactly when the database is empty --
        n_conn = self.env['hr.integration.connector'].search_count([])
        Rule = self.env.get('hr.api.transformation.rule')
        n_rules = 0 if Rule is None else Rule.with_context(
            active_test=False).search_count([])
        self.assertEqual(bool(ghosts('transforms')), not n_rules,
                         "the rules lane ghosts exactly when there are none")
        if not n_conn:
            self.assertTrue(ghosts('feeds'))

        # ---- and every ghost anywhere is a door, never a dead end ----------
        for lane in d['lanes']:
            for g in ghosts(lane):
                self.assertTrue(g.get('door'), "ghost %r has no door" % g['id'])
                self.assertTrue(g['door'].get('mode'))
        cfg.unlink()

    def test_03l_every_door_names_a_mode_the_strip_carries(self):
        """A door onto a mode the MODES strip does not have is a click that
        does nothing at all — the failure that looks exactly like a dead board."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        modes = set(re.findall(r'\{\s*id:\s*"([a-z]+)"\s*,\s*icon:', js))
        self.assertIn('journey', modes)
        if not self.config:
            self.skipTest("no formula config on this database")
        d = self.Studio.journey_data(self.config.id)
        for nodes in d['lanes'].values():
            for n in nodes:
                if n.get('door'):
                    self.assertIn(n['door']['mode'], modes,
                                  "node %r opens a mode that does not exist"
                                  % n['id'])

    # ==================================================================
    # 4. the tab strip, and every door that existed before J5
    # ==================================================================
    def test_04a_journey_is_first_and_is_the_cold_start_default(self):
        js = _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js')
        stripped = _strip_js_comments(js)
        ids = re.findall(r'\{\s*id:\s*"([a-z]+)"\s*,\s*icon:', stripped)
        self.assertEqual(
            ids, ['journey', 'api', 'transform', 'import', 'employee',
                  'scheme', 'cycle'],
            "the MODES order IS the story; Journey is first of seven")
        self.assertIn('mode: askedMode || "journey"', stripped,
                      "a cold start must land on the Journey, and an explicit "
                      "pb_mode must still win")

    def test_04b_an_explicit_mode_still_wins(self):
        """The guard that keeps every pre-existing door where it was: the mode
        is taken from the context when the context names a legal one, and only
        then does the default apply."""
        stripped = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        self.assertIn(
            'const askedMode = MODES.some((m) => m.id === ctx.pb_mode) '
            '? ctx.pb_mode : "";', stripped,
            "the arrival reader must still honour an explicit pb_mode")

    def test_04c_each_pre_existing_door_is_unchanged(self):
        for (module, path), snippet in PRE_J5_DOORS.items():
            try:
                src = _strip_js_comments(_src(module, path))
            except (OSError, ValueError):
                continue                # module not installed on this database
            self.assertIn('pb_mapping_studio', src,
                          "%s no longer opens the mapping cockpit" % path)
            if snippet:
                self.assertIn(snippet, src,
                              "%s must still name its own pb_mode — J5 moved "
                              "the COLD-START default only" % path)
            else:
                self.assertNotIn('pb_mode', src,
                                 "%s is a cold-start door and must stay one "
                                 "(it is how the Journey is reached)" % path)

    def test_04d_the_journey_tab_has_a_hint_and_no_forbidden_words(self):
        js = _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js')
        self.assertIn('id: "journey"', js)
        block = js.split('id: "journey"')[1].split('{ id: "api"')[0]
        self.assertIn('hint:', block, "every tab owes the strip a tooltip")

    # ==================================================================
    # 5. the Journey never writes
    # ==================================================================
    #: Every ORM verb that can change a row. `flush` and `invalidate` are not
    #: here on purpose: they move nothing of their own.
    WRITE_VERBS = ('.write(', '.create(', '.unlink(', '.copy(',
                   '.action_process(', '.button_', '.toggle_active(')

    def test_05a_the_adapter_and_its_helpers_contain_no_write_verb(self):
        """A SOURCE assertion, and it is only half the proof.

        It cannot see a write hidden behind a helper this method calls, which is
        why the other half is an MF37 database diff across the whole live
        session. Neither check is sufficient alone and both are cheap.
        """
        py = _src('pb_formula_studio', 'models/pb_formula_studio.py')
        start = py.index('def journey_data(')
        end = py.index('# W62 — transforms on the wire', start)
        body = py[start:end]
        for verb in self.WRITE_VERBS:
            self.assertNotIn(
                verb, body,
                "journey_data or one of its helpers contains %r. The Journey "
                "reads and navigates; it writes nothing, and that is the "
                "phase's signature proof." % verb)

    def test_05b_the_board_has_no_write_callback(self):
        """The client half. `JourneyBoard`'s whole props contract is data, busy
        and ONE callback, and that callback changes which tab is on screen."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/journey_board.js'))
        props = js.split('static props = {')[1].split('};')[0]
        for banned in ('onDraw', 'onDelete', 'onAccept', 'onSave', 'onCreate',
                       'onRemove'):
            self.assertNotIn(banned, props,
                             "the Journey board must not be handed a write "
                             "callback; it cannot use one honestly")
        self.assertIn('onOpenDoor', props)
        self.assertNotIn('this.orm', js,
                         "the board makes no RPC of its own — the host owns "
                         "the one read")

    def test_05c_the_journey_calls_journey_data_and_nothing_else(self):
        """One read per tab switch. A board that fired a second RPC would be a
        second opinion about the same five lanes."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        # `case "journey":` appears in `fromSlot` too, and splitting on the
        # first one read the SENTENCE builder instead of the loader — a test
        # that failed against correct code because its anchor was ambiguous.
        loader = js.split('async load()', 1)[1]
        block = loader.split('case "journey":', 1)[1].split('break;', 1)[0]
        self.assertIn('journey_data', block)
        self.assertEqual(block.count('this.orm.call'), 1)

    # ==================================================================
    # 6. wording, white-label and translation
    # ==================================================================
    def test_06a_no_user_visible_odoo(self):
        """The white-label absolute. Technical identifiers are untouched — this
        looks at the strings a person can read."""
        for module, path in (
                ('pb_formula_studio', 'static/src/js/mapping/journey_board.js'),
                ('pb_formula_studio', 'static/src/xml/journey_board.xml'),
                ('pb_formula_studio', 'static/src/scss/journey.scss')):
            src = _src(module, path)
            self.assertNotIn('Odoo', src, "%s says Odoo to a user" % path)
            self.assertNotIn('odoo', src.replace('@odoo-module', '')
                             .replace('@odoo/owl', ''),
                             "%s says odoo outside a module marker" % path)

    def test_06b_no_emoji_in_any_new_string(self):
        """Lucide glyphs and the kit, never emoji. `⇆` and `→` are typographic
        arrows and are the vocabulary J3 and J4 already established."""
        allowed = set('⇆→←·…—“”’≥')
        for module, path in (
                ('pb_formula_studio', 'static/src/js/mapping/journey_board.js'),
                ('pb_formula_studio', 'static/src/xml/journey_board.xml')):
            # COMMENTS are not UI strings. The first cut scanned the raw file
            # and failed on the `──▶` in this board's own header diagram, which
            # no user can ever see — a rule that fires on documentation teaches
            # the next reader to delete the documentation.
            src = _src(module, path)
            src = (_strip_js_comments(src) if path.endswith('.js')
                   else re.sub(r'<!--.*?-->', '', src, flags=re.S))
            for ch in src:
                if ord(ch) > 0x2100 and ch not in allowed:
                    self.fail("%s contains %r (U+%04X) — no emoji in UI strings"
                              % (path, ch, ord(ch)))

    def test_06c_every_new_server_string_is_translatable(self):
        """A bare literal in a payload ships English forever, and it fails
        silently at the point of use (S19's family).

        The first cut of this test guessed at the first characters of the value
        and failed on `ep.name or ep.code or _("Unnamed feed")` — correct code,
        rejected by a sloppy oracle. So it asks the precise question instead:
        is any user-facing key assigned a BARE QUOTED STRING? A variable, a
        concatenation and a `_()` all pass; only a raw literal fails, which is
        the only thing that can actually ship untranslated.
        """
        py = _src('pb_formula_studio', 'models/pb_formula_studio.py')
        start = py.index('def journey_data(')
        end = py.index('# W62 — transforms on the wire', start)
        body = py[start:end]
        for key in ('label', 'sub', 'hint', 'countLabel', 'records_note'):
            for m in re.finditer(
                    r"'%s':\s*(?:_\(\s*)?('[^']*'|\"[^\"]*\")" % key, body):
                literal = m.group(1)
                if literal in ("''", '""'):
                    continue            # a deliberate empty string
                prefix = body[max(0, m.start()):m.start() + len(key) + 5]
                self.assertIn(
                    '_(', body[m.start():m.end()],
                    "a %s in journey_data is a bare literal (%s) — wrap it in "
                    "_() or gettext will never see it. Context: %r"
                    % (key, literal, prefix))

    def test_06d_the_headline_never_prints_a_bare_plural_bracket(self):
        """W80: "8 rule(s)" is a translator's problem pushed onto the reader.
        One msgid per shape, on this board as on every other."""
        js = _src('pb_formula_studio', 'static/src/js/mapping/journey_board.js')
        self.assertNotIn('(s)', js)

    # ==================================================================
    # 7. the pre-filter seam
    # ==================================================================
    def test_07a_the_canvas_gained_exactly_one_command_kind(self):
        """`search` rides the channel that already existed for host orders. The
        canvas' PROPS are byte-identical, which is what keeps the other five
        boards out of this phase entirely."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_canvas.js'))
        kinds = set(re.findall(r'cmd\.kind === "([a-zA-Z]+)"', js))
        self.assertEqual(kinds, {'pulse', 'suggested', 'armLeft', 'search'})

    def test_07b_only_search_is_replayed_at_mount(self):
        """A one-shot order replayed on every mount stops being one-shot:
        `pulse` would flash the wires each time a tab opened and `armLeft`
        would arm a card nobody clicked."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_canvas.js'))
        block = js.split('const first = this.props.command;')[1][:400]
        self.assertIn('first.kind === "search"', block)
        self.assertNotIn('pulse', block)
        self.assertNotIn('armLeft', block)

    def test_07b2_a_door_with_no_focus_clears_the_previous_ones(self):
        """The defect the live pass caught, pinned so it cannot come back.

        `command` is REPLAYED at mount — that is what makes a door land
        pre-filtered. So a door with no focus that returned early left the
        PREVIOUS door's order in the prop, and opening "Payobook records" after
        opening a feed called Employees mounted the people board filtered to
        "Employees": a board that has lost most of its cards, for a reason
        nothing on screen explains. An empty order is still an order.
        """
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        # anchor on the DEFINITION, not the call site — `_applyFocus()`
        # appears in `openDoor` first, and splitting on it read the wrong
        # block entirely (the same ambiguous-anchor mistake test_05c made)
        body = js.split('_applyFocus() {')[1].split('\n    }')[0]
        self.assertNotIn('if (!text', body,
                         "_applyFocus must not return early on an empty focus — "
                         "it has to issue the empty order")
        self.assertIn('kind: "search", text', body)
        canvas = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_canvas.js'))
        self.assertNotIn('cmd.kind === "search" && cmd.text', canvas,
                         "the canvas must honour a search order with empty "
                         "text, or the clear can never arrive")

    def test_07b3_the_prefilter_narrows_the_source_column_only(self):
        """MJ1, restated for the door protocol — and caught live.

        Every focus a Journey door carries is a SOURCE-side name (a feed, a
        sheet, a rule output). Seeding BOTH columns with it filtered the
        destination catalogue by a source's name, which MJ1 already settled is
        "not a narrowing anybody asked for": arriving from the feed "Employees"
        left the right column reading `0 of 99 · Nothing matches that`, i.e.
        the board had hidden the ninety-nine components the reader came for.
        """
        canvas = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_canvas.js'))
        block = canvas.split('cmd.kind === "search"')[1].split('} else if')[0]
        self.assertIn('this.ui.q.left = t;', block)
        self.assertIn('this.ui.q.right = "";', block,
                      "the destination column must be CLEARED by a door's "
                      "pre-filter, never filtered by a source-side name")

    def test_07c_the_focus_is_read_once_in_the_arrival_reader(self):
        """The handover's explicit instruction: wire `pb_focus` through the
        host once, not per tab. Six tabs reading a context key is six places to
        keep in step for one feature."""
        js = _strip_js_comments(
            _src('pb_formula_studio', 'static/src/js/mapping/mapping_studio.js'))
        self.assertEqual(js.count('pb_focus'), 1)
