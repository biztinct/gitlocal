# -*- coding: utf-8 -*-
"""JOURNEY J6 — the four defects the owner reported against the live J4 board.

The round started with data loss: a double-click on the live `OTHRS300` wire
DELETED it (abm mapping 39). So the tests here are weighted towards the two
claims whose failure is destructive rather than merely wrong:

  * **a cut wire can be put back, exactly.** `api_mapping_cut` snapshots and
    `api_mapping_restore` recreates, and the round trip is asserted FIELD BY
    FIELD against the row that was cut — not "a wire exists again", which is the
    assertion that would have passed while silently dropping the original
    `source_field_label`, the `notes` and the transform settings. That is also
    why restore does not route through `api_mapping_create`: a create is a DRAW,
    and a draw re-derives all three.
  * **no gesture on a wire deletes.** Double-click centres; the only route to a
    delete is a labelled verb that `VERB_DY` keeps off the wire's own click
    path. Asserted against the SOURCE, because the defect was a geometry
    coincidence — the verb rendered at the Bézier midpoint, i.e. exactly where
    the click that selected the wire had just landed — and no unit test that
    mounts nothing can see a coincidence of coordinates.

The geometry claims (D1) are source assertions for the same reason MJ12 gives:
the bounding-box sweep excludes SVG nodes by construction, so a wire layer
translated 49.75px down the screen is invisible to every automated layout check
this codebase has. What CAN be pinned here is the rule that made it wrong —
that the board measures against the element the wires are PAINTED in.

MJ25's warning applies throughout: a source assertion is a parser written in a
hurry. Every anchor below is the most specific string that can occur once.
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


@tagged('post_install', '-at_install')
class TestJourneyJ6Defects(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FieldMapping = cls.env['hr.integration.field.mapping']
        cls.board_js = _strip_js_comments(_src(
            'pb_formula_studio', 'static', 'src', 'js', 'mapping',
            'transform_flow_board.js'))
        cls.board_xml = _strip_xml_comments(_src(
            'pb_formula_studio', 'static', 'src', 'xml',
            'transform_flow_board.xml'))
        cls.studio_js = _strip_js_comments(_src(
            'pb_formula_studio', 'static', 'src', 'js', 'mapping',
            'mapping_studio.js'))
        cls.board_scss = _src('pb_formula_studio', 'static', 'src', 'scss',
                              'transform_flow.scss')

    # ------------------------------------------------------------- fixtures
    def _config(self, name='J6 Scheme'):
        cfg = self.Config.create({
            'name': name, 'code': re.sub(r'\W', '', name.upper())[:32],
            'country_code': 'VN', 'state': 'active',
        })
        self.comp = self.Rule.create({
            'config_id': cfg.id, 'name': 'OT 3 Hours', 'code': 'OT3HOURS',
            'column_type': 'input', 'sequence': 1,
        })
        return cfg

    def _connector(self, name='J6 Flow'):
        return self.Connector.create({'name': name, 'connector_type': 'demo'})

    def _wire(self, conn, rule, key='OTHRS300', **extra):
        """A wire shaped like abm's real one — the row the owner lost."""
        vals = {
            'connector_id': conn.id, 'target_rule_id': rule.id,
            'source_field': key, 'active_state': 'active',
            'source_field_label': 'Overtime 300% hours',
            'source_data_type': 'float',
            'transformation_type': 'direct', 'transformation_value': 1.0,
            'notes': "ABM legacy evidence: hr_zoho_staging.py:522-530",
        }
        vals.update(extra)
        return self.FieldMapping.create(vals)

    # =====================================================================
    # 1 — D3: cut then restore is a true inverse (numbered case 6)
    # =====================================================================
    def test_01a_cut_returns_a_snapshot_and_deletes(self):
        cfg = self._config()
        conn = self._connector()
        m = self._wire(conn, self.comp)
        res = self.Studio.api_mapping_cut(m.id)
        self.assertTrue(res.get('ok'))
        self.assertTrue(res.get('snapshot'), "a cut must hand back its undo")
        self.assertFalse(m.exists(), "the wire is actually gone")
        self.assertTrue(cfg)

    def test_01b_restore_puts_every_business_field_back(self):
        """The assertion the naive version of this feature would fail."""
        self._config()
        conn = self._connector()
        m = self._wire(conn, self.comp)
        before = {f: (m[f].id if hasattr(m[f], 'id') else m[f])
                  for f in self.Studio._j6_wire_fields()}
        snap = self.Studio.api_mapping_cut(m.id)['snapshot']
        res = self.Studio.api_mapping_restore(snap)
        self.assertTrue(res.get('ok'))
        new = self.FieldMapping.browse(res['id'])
        after = {f: (new[f].id if hasattr(new[f], 'id') else new[f])
                 for f in self.Studio._j6_wire_fields()}
        self.assertEqual(before, after,
                         "an undo must be the delete's inverse, field for field")

    def test_01c_the_label_and_notes_survive_which_a_redraw_would_not(self):
        """Named separately because these two are what `api_mapping_create` loses.

        A restore routed through the DRAW path would re-derive
        `source_field_label` from the source field ("Othrs300") and carry no
        notes at all — and the round trip would still "work".
        """
        self._config()
        conn = self._connector()
        m = self._wire(conn, self.comp)
        snap = self.Studio.api_mapping_cut(m.id)['snapshot']
        new = self.FieldMapping.browse(
            self.Studio.api_mapping_restore(snap)['id'])
        self.assertEqual(new.source_field_label, 'Overtime 300% hours')
        self.assertIn('hr_zoho_staging.py:522-530', new.notes or '')
        self.assertEqual(new.transformation_type, 'direct')

    def test_01d_restore_is_idempotent(self):
        """Undo pressed twice puts back ONE wire, not two."""
        self._config()
        conn = self._connector()
        m = self._wire(conn, self.comp)
        snap = self.Studio.api_mapping_cut(m.id)['snapshot']
        first = self.Studio.api_mapping_restore(snap)
        second = self.Studio.api_mapping_restore(snap)
        self.assertTrue(second.get('ok'))
        self.assertTrue(second.get('already'))
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(self.FieldMapping.search_count(
            [('connector_id', '=', conn.id), ('source_field', '=', 'OTHRS300')]), 1)

    def test_01e_the_new_id_differs_and_that_is_recorded(self):
        self._config()
        conn = self._connector()
        m = self._wire(conn, self.comp)
        old = m.id
        snap = self.Studio.api_mapping_cut(m.id)['snapshot']
        self.assertNotEqual(self.Studio.api_mapping_restore(snap)['id'], old)

    def test_01f_snapshot_carries_the_binding_when_it_was_this_wires(self):
        """`api_mapping_delete` clears the binding; the undo has to know."""
        self._config()
        conn = self._connector()
        m = self._wire(conn, self.comp)
        self.comp.set_source_binding('rule', 'OTHRS300', origin='board')
        snap = self.Studio.api_mapping_cut(m.id)['snapshot']
        self.assertTrue(snap['binding'], "the binding was this wire's")
        self.assertEqual(snap['binding']['kind'], 'rule')
        self.assertEqual(snap['binding']['origin'], 'board')
        self.assertFalse(self.comp.source_binding, "the delete cleared it")
        self.Studio.api_mapping_restore(snap)
        self.assertEqual(self.comp.source_binding, 'rule')
        self.assertEqual(self.comp.source_binding_key, 'OTHRS300')
        self.assertEqual(self.comp.source_binding_origin, 'board')

    def test_01g_a_binding_that_was_not_this_wires_is_not_claimed(self):
        """S6's rule, still true through the undo."""
        self._config()
        conn = self._connector()
        m = self._wire(conn, self.comp)
        self.comp.set_source_binding('excel', 'SEVL|OT 3', origin='user')
        snap = self.Studio.api_mapping_cut(m.id)['snapshot']
        self.assertFalse(snap['binding'])
        self.assertEqual(self.comp.source_binding, 'excel',
                         "someone else's binding survives the cut")

    def test_01h_snapshot_carries_no_derived_fields(self):
        """Writing a computed value back is how a restore disagrees with a recompute."""
        fields = set(self.Studio._j6_wire_fields())
        for derived in ('display_name', 'is_mapped', 'target_column_letter',
                        'target_rule_code', 'connector_type',
                        'has_transform_error', 'transform_error_msg'):
            self.assertNotIn(derived, fields)

    def test_01i_restore_refuses_an_empty_or_broken_spec(self):
        self.assertFalse(self.Studio.api_mapping_restore(False).get('ok'))
        self.assertFalse(self.Studio.api_mapping_restore({}).get('ok'))
        self.assertFalse(self.Studio.api_mapping_restore(
            {'spec': {'connector_id': 0, 'target_rule_id': 0,
                      'source_field': ''}}).get('ok'))

    def test_01j_cut_delegates_to_the_one_delete(self):
        """There must not be a second way to remove a wire."""
        src = _src('pb_formula_studio', 'models', 'pb_formula_studio.py')
        body = src.split('def api_mapping_cut(')[1].split('    @api.model')[0]
        self.assertIn('self.api_mapping_delete(', body,
                      "the cut reuses the delete rather than unlinking itself")
        self.assertNotIn('.unlink()', body)

    # =====================================================================
    # 2 — D3: the host shares ONE undo (numbered case 7, grep-proof)
    # =====================================================================
    def test_02a_one_undo_helper_serves_both_boards(self):
        self.assertEqual(self.studio_js.count('async _removeWireUndoable('), 1,
                         "one implementation, not one per board")

    def test_02b_both_delete_paths_route_through_it(self):
        transform = self.studio_js.split('async removeTransformWire(')[1][:400]
        self.assertIn('_removeWireUndoable', transform)
        canvas = self.studio_js.split('async remove(wire)')[1][:600]
        self.assertIn('_removeWireUndoable', canvas)

    def test_02c_the_api_board_is_the_one_that_shares_it(self):
        """`prefix` maps both `api` and `transform` to `api` — that is the seam."""
        canvas = self.studio_js.split('async remove(wire)')[1][:600]
        self.assertIn('=== "api"', canvas)

    def test_02d_the_toast_offers_undo(self):
        # JOURNEY J8 — the cut/restore PAIR became the helper's arguments, so a
        # contract-component wire (which is cut by clearing two booleans, not by
        # unlinking a row) reaches the same toast instead of a second copy of it.
        # This test therefore anchors on the invariant rather than on the two
        # method names it used to find inline: the toast, its verb, and the fact
        # that the API board still passes ITS pair to the one helper (MJ25 — an
        # oracle that describes the implementation fails against correct code).
        body = self.studio_js.split('async _removeWireUndoable(')[1][:1200]
        self.assertIn('cutMethod', body)
        self.assertIn('_t("Wire removed")', body)
        self.assertIn('_t("Undo")', body)
        self.assertIn('this.orm.call(MODEL, restoreMethod, [snapshot])', body)
        self.assertIn('_removeWireUndoable("api_mapping_cut", "api_mapping_restore"',
                      self.studio_js)
        # ...and there is still exactly ONE of it
        self.assertEqual(self.studio_js.count('async _removeWireUndoable('), 1)

    def test_02e_the_undo_window_is_the_toast_and_is_not_sticky(self):
        body = self.studio_js.split('async _removeWireUndoable(')[1][:1200]
        self.assertIn('autocloseDelay: UNDO_MS', body)
        self.assertNotIn('sticky: true', body)
        self.assertRegex(self.studio_js, r'const UNDO_MS = \d+;')

    # =====================================================================
    # 3 — D3: no gesture on a wire deletes (numbered cases 5, 9)
    # =====================================================================
    def test_03a_double_click_centres_and_never_removes(self):
        for handler in re.findall(r't-on-dblclick="([^"]+)"', self.board_xml):
            self.assertNotIn('removeWire', handler)
            self.assertNotIn('onDelete', handler)

    def test_03b_the_wire_hit_area_double_clicks_to_centre(self):
        hit = self.board_xml.split('<path class="tfb-hit" t-att-d="g.d"')[1][:400]
        self.assertIn('t-on-dblclick="(ev) => this.centreBoth(g, ev)"', hit)
        self.assertIn('t-on-click="(ev) => this.selectWire(g, ev)"', hit)

    def test_03c_remove_is_reachable_only_from_the_labelled_verb(self):
        """`removeWire` has exactly one call site, and it is a titled button."""
        self.assertEqual(self.board_xml.count('this.removeWire('), 1)
        verb = self.board_xml.split('class="tfb-wireact__x"')[1][:300]
        self.assertIn('title="Remove this wire"', verb)
        self.assertIn('Remove', verb)

    def test_03d_the_verb_is_placed_off_the_wire(self):
        """The defect, pinned: the pill used to sit at the hub point."""
        self.assertNotIn('top:{{ selectedWire.hy }}px', self.board_xml)
        self.assertIn('top:{{ verbPos.y }}px', self.board_xml)
        body = self.board_js.split('get verbPos()')[1][:600]
        self.assertIn('VERB_DY', body)
        self.assertRegex(self.board_js, r'const VERB_DY = \d+;')

    def test_03e_the_offset_clears_the_hit_stroke(self):
        """16px transparent stroke = 8px either side; the verb must clear it."""
        dy = int(re.search(r'const VERB_DY = (\d+);', self.board_js).group(1))
        stroke = int(re.search(r'\.tfb-hit \{[^}]*stroke-width: (\d+)',
                               self.board_scss).group(1))
        self.assertGreater(dy, stroke / 2 + 12,
                           "the pill must not overlap the wire's own hit area")

    def test_03f_a_double_click_on_the_verb_is_swallowed(self):
        verb = self.board_xml.split('class="tfb-wireact')[1][:400]
        self.assertIn('t-on-dblclick.stop.prevent', verb)

    # =====================================================================
    # 4 — D1: the geometry is measured where it is painted
    # =====================================================================
    def test_04a_the_board_is_the_origin_not_the_root(self):
        body = self.board_js.split('_recompute() {')[1][:700]
        self.assertIn('const rb = board.getBoundingClientRect();', body)
        self.assertNotIn('const rb = root.getBoundingClientRect();', body)

    def test_04b_the_wire_layer_is_a_child_of_the_measured_element(self):
        """The invariant behind the defect: same element, or the wires shift."""
        self.assertIn('class="tfb-board" t-ref="board"', self.board_xml)
        board = self.board_xml.split('class="tfb-board" t-ref="board"')[1]
        self.assertIn('class="tfb-wires"', board)
        self.assertIn('tfb-wireact', board)
        self.assertIn('tfb-dock', board)

    def test_04c_the_menu_still_measures_against_the_root(self):
        """It is a SIBLING of the board, outside the clip — MJ7's arrangement."""
        for fn in ('toggleVerbs(r, ev) {', 'openLineage(r, ev) {'):
            body = self.board_js.split(fn)[1][:500]
            self.assertIn('root.getBoundingClientRect()', body)

    def test_04d_dock_chips_are_placed_against_the_lane_band(self):
        body = self.board_js.split('dockStyle(d) {')[1][:300]
        self.assertIn('this.ui.band', body)
        self.assertIn('b.top', body)
        self.assertIn('b.bot', body)
        self.assertIn('dockStyle(dk)', self.board_xml)

    def test_04d2_the_two_chips_are_placed_over_different_lane_gaps(self):
        """`left: 34%` and `right: 34%` MEET as the board narrows (1024: −32px)."""
        body = self.board_js.split('dockStyle(d) {')[1][:300]
        self.assertIn('d.side === "left" ? b.gapL : b.gapR', body)
        band = self.board_js.split('this.ui.band = lanes.length')[1][:600]
        self.assertIn('gapL', band)
        self.assertIn('gapR', band)
        self.assertNotIn('.tfb-dock.right { right: 34%; }', self.board_scss)

    def test_04d3_a_parked_end_loses_its_arrowhead(self):
        """An arrowhead means "it ends here", and a parked end does not."""
        self.assertIn("g.dockR ? 'dockend' : ''", self.board_xml)
        self.assertIn('<polygon t-if="!g.dockR" class="tfb-rh"', self.board_xml)
        self.assertIn('.tfb .tfb-w.dockend .tfb-head { opacity: 0; }',
                      self.board_scss)

    def test_04e_the_band_comes_from_the_lane_bodies(self):
        body = self.board_js.split('this.ui.band = lanes.length')[1][:300]
        self.assertIn('bandTop', body)
        self.assertIn('bandBot', body)

    def test_04f_the_chip_no_longer_pins_itself_to_the_header_row(self):
        """`bottom: 8px` of the BOARD is the header row's neighbourhood."""
        self.assertNotIn('.tfb-dock.down { bottom: 8px; }', self.board_scss)

    # =====================================================================
    # 5 — D2: double-click centres both ends (numbered cases 4, 5)
    # =====================================================================
    def test_05a_read_edges_are_double_clickable(self):
        reads = self.board_xml.split('<g class="tfb-reads">')[1][:900]
        self.assertIn('t-on-dblclick="(ev) => this.centreBoth(g, ev)"', reads)

    def test_05b_read_edges_are_still_not_editable(self):
        reads = self.board_xml.split('<g class="tfb-reads">')[1][:900]
        for verb in ('selectWire', 'removeWire', 'onDraw'):
            self.assertNotIn(verb, reads)
        self.assertIn('.tfb-hit.read { cursor: default; }', self.board_scss)

    def test_05c_centre_both_scrolls_both_ends_of_either_family(self):
        body = self.board_js.split('centreBoth(g, ev) {')[1][:1200]
        self.assertIn('"read"', body)
        self.assertIn('leftId', body)
        self.assertIn('rightId', body)
        self.assertIn('_centreLane', body)

    def test_05d_centre_both_reads_live_geometry(self):
        """The canvas' reasoning: a filter may have moved an end since the render."""
        body = self.board_js.split('centreBoth(g, ev) {')[1][:1200]
        self.assertIn('this.ui.reads', body)
        self.assertIn('this.ui.geom', body)
        self.assertIn('.find((x) => x.id === g.id)', body)

    def test_05e_a_hidden_end_gets_the_canvas_reveal_vocabulary(self):
        self.assertIn('Clear the filter and show me', self.board_xml)
        canvas_xml = _strip_xml_comments(_src(
            'pb_formula_studio', 'static', 'src', 'xml', 'mapping_canvas.xml'))
        self.assertIn('Clear the filter and show me', canvas_xml,
                      "one sentence for one gesture, on both boards")

    def test_05f_centre_both_writes_nothing(self):
        """Numbered case 4/5: the gesture is navigation, never a write."""
        body = self.board_js.split('centreBoth(g, ev) {')[1][:1200]
        for writer in ('onDraw', 'onDelete', 'removeWire', 'orm.call'):
            self.assertNotIn(writer, body)

    def test_05g_escape_dismisses_the_reveal_first(self):
        body = self.board_js.split('if (ev.key === "Escape") {')[1][:500]
        self.assertLess(body.index('this.dismissReveal()'),
                        body.index('this.cancelArm()'),
                        "most-nested rung first")

    # =====================================================================
    # 6 — D4: the draw gesture can be found (numbered cases 13, 14)
    # =====================================================================
    def test_06a_the_output_port_is_labelled_not_an_icon(self):
        """MF26: an affordance a user cannot discover does not exist."""
        port = self.board_xml.split('class="tfb-out port')[1][:600]
        self.assertIn('Wire this output to a component…', port)
        self.assertIn('tfb-out-k', port)

    def test_06b_clicking_the_port_arms_and_does_not_open_the_composer(self):
        port = self.board_xml.split('class="tfb-out port')[1][:600]
        self.assertIn('this.armOutput(r, ev)', port)
        self.assertNotIn('openRule', port)
        body = self.board_js.split('armOutput(r, ev) {')[1][:400]
        self.assertIn('ev.stopPropagation()', body)

    def test_06c_the_card_body_still_opens_the_composer(self):
        card = self.board_xml.split('data-lane="mid"')[1][:400]
        self.assertIn('this.clickRule(r, ev)', card)
        body = self.board_js.split('clickRule(r, ev) {')[1][:300]
        self.assertIn('this.openRule(', body)

    def test_06d_the_armed_banner_uses_the_canvas_sentence(self):
        self.assertIn('Click a target component to connect', self.board_xml)
        canvas_xml = _strip_xml_comments(_src(
            'pb_formula_studio', 'static', 'src', 'xml', 'mapping_canvas.xml'))
        self.assertIn('Click a target component to connect', canvas_xml)

    def test_06e_the_target_lane_lights_while_armed(self):
        self.assertIn('.tfb.is-armed .tfb-item.comp {', self.board_scss)
        armed = self.board_scss.split('.tfb.is-armed .tfb-item.comp {')[1][:260]
        self.assertIn('background:', armed)
        self.assertIn('.tfb.is-armed .tfb-item.comp.sealed {', self.board_scss)

    def test_06f_there_is_a_keyboard_path_with_the_mf33_guard(self):
        body = self.board_js.split('keyComponent(item, ev) {')[1][:500]
        self.assertIn('ev.key !== "Enter"', body)
        self.assertIn('this.clickComponent(item, ev)', body)
        self.assertIn('ev.preventDefault()', body)
        # MF33 — Enter on a BUTTON must not also reach the board's own handler
        guard = self.board_js.split('onKeydown(ev) {')[1][:500]
        self.assertIn('tag === "BUTTON"', guard)

    def test_06g_targets_are_tabbable_only_while_armed(self):
        card = self.board_xml.split('data-lane="right"')[1][:500]
        self.assertIn('t-att-tabindex="ui.armed and !isSealed(it) ? 0 : null"', card)

    def test_06h_the_draw_still_goes_through_the_existing_create(self):
        """D4 is discoverability; it must not add a second write path."""
        body = self.board_js.split('clickComponent(item, ev) {')[1][:900]
        self.assertIn('this.props.onDraw(', body)
        self.assertNotIn('orm.call', body)

    # =====================================================================
    # 7 — house rules
    # =====================================================================
    def test_07a_no_user_visible_odoo(self):
        for blob in (self.board_xml, self.board_js, self.studio_js):
            for m in re.findall(r'_t\(\s*"([^"]{0,300})"', blob):
                self.assertNotIn('Odoo', m)
        for m in re.findall(r'>([^<>{}]{4,200})</', self.board_xml):
            self.assertNotIn('Odoo', m)

    def test_07b_new_server_strings_are_translated(self):
        src = _src('pb_formula_studio', 'models', 'pb_formula_studio.py')
        body = src.split('def api_mapping_restore(')[1].split('return {')[0]
        for msg in re.findall(r"'msg': ([^,\n]+)", body):
            self.assertTrue(msg.startswith('_(') or msg.startswith('self.'),
                            "a user-visible message must be translated: %s" % msg)

    def test_07c_the_board_still_owns_no_second_delete_rpc(self):
        self.assertNotIn('api_mapping_delete', self.board_js)
        self.assertNotIn('orm.call', self.board_js)
