# -*- coding: utf-8 -*-
"""JOURNEY J8 — the contract component becomes a visible destination.

Two deliverables, and only one of them is a feature.

  * **D1 — a `Contract components` lane in the right column.** The board's
    single most-used destination was the only one it did not draw. A contract
    component is not a field of `hr.contract`: it is a row of
    `hr.contract.advantage` pointing at an `hr.contract.advantage.template`,
    matched by CODE, so it could never have come out of `ir.model.fields` and
    widening `_EC_TTYPES` would not have produced it either. The lane is two
    SYNTHETIC cards (`c:amount`, `c:text`) on the `b:` precedent, wired through
    the promotion RPC that already existed.
  * **D2 — the arrowhead was painted under the column's scrollbar.** A head is a
    triangle spanning `ANCHOR_GAP` (4) to `ANCHOR_GAP + HEAD` (15) from a card's
    edge, and `.mc-col-body` gave it 14px of padding. One pixel short, and the
    sixteenth pixel is the scrollbar — which belongs to `.mc-cols` (`z-index: 2`)
    and paints over `.mc-wires` (`z-index: 1`).

The ORM half is asserted against real records; the geometry half is asserted
against the SOURCE, for MJ12/MJ30's reason — the only automated check in this
codebase that measures rects is structurally blind to SVG, so the rules that
make the defect impossible are pinned where they are stated. MJ25 applies to
every anchor below: the most specific string that can occur once.
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip_scss_comments(src):
    return re.sub(r'/\*.*?\*/', '', src, flags=re.S)


def _rule_block(scss, selector):
    m = re.search(re.escape(selector) + r'\s*\{(.*?)\}', scss, flags=re.S)
    return m.group(1) if m else ''


@tagged('post_install', '-at_install')
class TestJourneyJ8Components(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.Advantage = cls.env['hr.contract.advantage']
        cls.Mapping = cls.env['hr.payslip.import.mapping']

    # ------------------------------------------------------------- fixtures
    def _config(self, name):
        return self.Config.create({
            'name': name, 'code': re.sub(r'[^A-Z0-9]', '', name.upper())[:32],
            'country_code': 'VN', 'state': 'active',
        })

    def _rule(self, cfg, code, seq=10, **kw):
        vals = {'config_id': cfg.id, 'name': kw.pop('name', code.title()),
                'code': code, 'column_type': kw.pop('column_type', 'input'),
                'sequence': seq}
        vals.update(kw)
        return self.Rule.create(vals)

    def _ids(self, items):
        return [i['id'] for i in items]

    # =================================================== D1 — the lane exists
    def test_01_the_lane_sits_between_contract_terms_and_bank(self):
        """Order is the whole of the placement: the canvas emits a group header
        whenever `group` changes between consecutive rows, so a lane in the wrong
        place is a heading in the wrong place."""
        keys = [k for k, _g in self.Studio._EC_LANES]
        self.assertIn('contract_component', keys)
        self.assertEqual(keys.index('contract_component'),
                         keys.index('contract_terms') + 1)
        self.assertEqual(keys.index('bank'),
                         keys.index('contract_component') + 1)
        # and it has a heading of its own, not the "Other fields" fallback
        self.assertNotEqual(self.Studio._ec_lane_label('contract_component'),
                            self.Studio._ec_lane_label('nonexistent-lane-key'))

    def test_02_the_right_column_carries_both_cards_in_lane_order(self):
        cfg = self._config('J8 lane order')
        col = self.Studio._ec_right_column('', cfg)
        ids = self._ids(col)
        self.assertIn('c:amount', ids)
        self.assertIn('c:text', ids)
        self.assertIn('b:acc_number', ids)
        # MAPFIX E2's whole-board invariant, with the new cards present: the
        # column reads top-to-bottom in ONE lane order.
        order = [i['meta'].get('lane_order', 99) for i in col]
        self.assertEqual(order, sorted(order),
                         "the right column is out of lane order")
        # the component cards come BEFORE the bank cards
        self.assertLess(ids.index('c:text'), ids.index('b:acc_number'))
        self.assertLess(ids.index('c:amount'), ids.index('c:text'))

    def test_02b_a_synthetic_card_carries_catalogue_metadata(self):
        """MAPFIX E2's construction invariant: a card rendered on the right has
        the metadata it would have had from the catalogue. These are not fields,
        so they get the equivalent rather than a subset."""
        cfg = self._config('J8 card meta')
        cards = [i for i in self.Studio._ec_right_column('', cfg)
                 if i['id'].startswith('c:')]
        self.assertEqual(len(cards), 2)
        group = self.Studio._ec_lane_label('contract_component')
        for card in cards:
            self.assertTrue(card['label'])
            self.assertTrue(card['sublabel'])
            self.assertEqual(card['group'], group)
            meta = card['meta']
            self.assertEqual(meta['lane'], 'contract_component')
            self.assertIsInstance(meta['lane_order'], int)
            self.assertEqual(meta['kind'], 'component')
            self.assertIn(meta['component_kind'], ('amount', 'text'))
            self.assertTrue(meta['mappable'])

    def test_02c_the_column_still_builds_without_a_config(self):
        """`_ec_right_column()` is called by the catalogue test and by anything
        that wants the destinations without a scheme in hand. The state line has
        nothing to say there; the CARDS must still be there."""
        ids = self._ids(self.Studio._ec_right_column())
        self.assertIn('c:amount', ids)
        self.assertIn('b:acc_number', ids)

    # ========================================== D1 — wires, and their identity
    def test_03_a_flagged_rule_draws_a_wire_to_the_matching_card(self):
        cfg = self._config('J8 wires')
        amount = self._rule(cfg, 'J8AMT', 10)
        text = self._rule(cfg, 'J8TXT', 20)
        plain = self._rule(cfg, 'J8PLAIN', 30)
        self.Studio.employee_mapping_make_component(amount.id, 'amount')
        self.Studio.employee_mapping_make_component(text.id, 'text')

        data = self.Studio.employee_mapping_data(cfg.id, include_payroll=True)
        comp = [w for w in data['wires'] if w['kind'] == 'component']
        self.assertEqual(len(comp), 2)
        by_left = {w['leftId']: w for w in comp}
        self.assertEqual(by_left[amount.id]['rightId'], 'c:amount')
        self.assertEqual(by_left[text.id]['rightId'], 'c:text')
        self.assertNotIn(plain.id, by_left)
        # every one of them is a settled fact, not a proposal
        self.assertEqual({w['state'] for w in comp}, {'accepted'})

    def test_03b_the_badge_and_the_wire_agree_for_every_flagged_rule(self):
        """Asserted programmatically because the badge and the wire are built by
        two different methods reading the same two booleans, and "they agree" is
        the only thing that makes the board's two statements one statement."""
        cfg = self._config('J8 agreement')
        rules = []
        for n in range(6):
            r = self._rule(cfg, 'J8AG%s' % n, 10 + n)
            self.Studio.employee_mapping_make_component(
                r.id, 'text' if n % 2 else 'amount')
            rules.append(r)
        data = self.Studio.employee_mapping_data(cfg.id, include_payroll=True)
        left = {i['id']: i for i in data['left']}
        wired = {w['leftId']: w['rightId'] for w in data['wires']
                 if w['kind'] == 'component'}
        self.assertEqual(len(wired), 6)
        for r in rules:
            badge = left[r.id]['meta'].get('badge')
            self.assertTrue(badge, "a flagged rule with no badge")
            want = 'c:text' if r.is_text_component else 'c:amount'
            self.assertEqual(wired[r.id], want,
                             "%s: badge %r and wire disagree" % (r.code, badge))

    def test_03c_a_component_wire_can_never_reach_the_mapping_delete(self):
        """The trap this id namespace exists for: `employee_mapping_delete`
        browses `hr.payslip.import.mapping`, so a rule id arriving there would
        unlink whatever row happened to carry that number."""
        cfg = self._config('J8 namespace')
        rule = self._rule(cfg, 'J8NS', 10)
        self.Studio.employee_mapping_make_component(rule.id, 'amount')
        wire = [w for w in
                self.Studio.employee_mapping_data(cfg.id, include_payroll=True)['wires']
                if w['kind'] == 'component'][0]
        self.assertTrue(wire['id'].startswith('cc'))
        self.assertFalse(wire['ref'], "a component wire must carry no mapping ref")
        self.assertEqual(wire['componentId'], rule.id)
        # ...and the client branches on `kind`, never on the shape of the id
        js = _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                  'mapping_studio.js')
        self.assertIn('wire.kind === "component"', js)

    def test_04_direction_is_two_way_for_an_amount_and_one_way_for_text(self):
        """The finding that made the two cards worth having. The resolver builds
        `contract_component_amounts` from the contract's advantage lines and
        SKIPS `value_type == 'text'` outright — letting a text component in would
        feed a permanent 0.0 into any formula naming it. So an amount is read
        back and text is not, and the board must not claim otherwise (J3's rule
        for a bank row, one destination over)."""
        cfg = self._config('J8 direction')
        amount = self._rule(cfg, 'J8DAMT', 10)
        text = self._rule(cfg, 'J8DTXT', 20)
        self.Studio.employee_mapping_make_component(amount.id, 'amount')
        self.Studio.employee_mapping_make_component(text.id, 'text')
        left = {i['id']: i for i in
                self.Studio.employee_mapping_data(cfg.id, include_payroll=True)['left']}
        self.assertEqual(left[amount.id]['meta']['direction'], 'two_way')
        self.assertEqual(left[text.id]['meta']['direction'], 'to_record')
        self.assertIn('J8DAMT', left[amount.id]['meta']['directionNote'])
        self.assertIn('J8DTXT', left[text.id]['meta']['directionNote'])
        # and the source of that asymmetry is where the test says it is
        resolver = _src('pb_hr_payroll_formula', 'models', 'payroll_import_batch.py')
        self.assertIn("template.value_type == 'text'", resolver)

    # ================================================ D1 — wiring is the reuse
    def test_05_drawing_to_the_amount_card_routes_to_the_promotion(self):
        cfg = self._config('J8 draw')
        rule = self._rule(cfg, 'J8DRAW', 10, column_role='reference')
        res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, 'c:amount')
        self.assertTrue(res.get('ok'), res)
        self.assertTrue(rule.is_contract_component)
        self.assertFalse(rule.is_text_component)
        # CR-A2 — an amount component feeds the calculation, so it takes `payroll`
        self.assertEqual(rule.column_role, 'payroll')
        self.assertEqual(rule.column_role_source, 'user')

    def test_05b_drawing_to_the_text_card_is_the_other_half(self):
        cfg = self._config('J8 draw text')
        rule = self._rule(cfg, 'J8DRAWT', 10)
        res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, 'c:text')
        self.assertTrue(res.get('ok'), res)
        self.assertTrue(rule.is_text_component)
        self.assertEqual(rule.column_role, 'contract')

    def test_05c_the_column_keeps_exactly_one_destination(self):
        """The promotion unlinks any field or bank row — one column, one home."""
        cfg = self._config('J8 one home')
        rule = self._rule(cfg, 'J8ONE', 10)
        self.Studio.employee_mapping_create(cfg.id, False, rule.id,
                                            'f:hr.employee:name')
        self.assertEqual(self.Mapping.search_count([('component_id', '=', rule.id)]), 1)
        self.Studio.employee_mapping_create(cfg.id, False, rule.id, 'c:amount')
        self.assertEqual(self.Mapping.search_count([('component_id', '=', rule.id)]), 0)
        # ...and back the other way DEMOTES rather than adding a second home
        self.Studio.employee_mapping_create(cfg.id, False, rule.id,
                                            'f:hr.employee:name')
        self.assertFalse(rule.is_contract_component)
        self.assertEqual(self.Mapping.search_count([('component_id', '=', rule.id)]), 1)

    def test_05d_an_unknown_component_suffix_is_a_refusal_not_a_traceback(self):
        cfg = self._config('J8 bad spec')
        rule = self._rule(cfg, 'J8BAD', 10)
        for spec in ('c:', 'c:money', 'c:AMOUNT', 'c:amount:extra'):
            res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, spec)
            self.assertFalse(res.get('ok'), spec)
            self.assertTrue(res.get('msg'), spec)
        self.assertFalse(rule.is_contract_component)

    def test_05e_a_calculated_column_is_still_refused(self):
        cfg = self._config('J8 calculated')
        rule = self._rule(cfg, 'J8CALC', 10, column_type='formula',
                          excel_formula='=1')
        res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, 'c:amount')
        self.assertFalse(res.get('ok'))
        self.assertFalse(rule.is_contract_component)

    # ================================================ D1 — detach, undo, refusal
    def test_06_detach_returns_a_snapshot_and_the_restore_is_its_inverse(self):
        cfg = self._config('J8 undo')
        rule = self._rule(cfg, 'J8UNDO', 10)
        self.Studio.employee_mapping_make_component(rule.id, 'text')
        before = (rule.is_contract_component, rule.is_text_component,
                  rule.column_role, rule.column_role_source)

        res = self.Studio.employee_mapping_detach_component(rule.id)
        self.assertTrue(res.get('ok'), res)
        snap = res.get('snapshot')
        self.assertTrue(snap, "a detach with no snapshot has no undo")
        self.assertFalse(rule.is_contract_component)
        self.assertFalse(rule.is_text_component)

        back = self.Studio.employee_component_restore(snap)
        self.assertTrue(back.get('ok'), back)
        self.assertEqual((rule.is_contract_component, rule.is_text_component,
                          rule.column_role, rule.column_role_source), before)
        # MJ32 — idempotent, so a double-pressed Undo restores ONE component
        self.Studio.employee_component_restore(snap)
        self.assertEqual((rule.is_contract_component, rule.is_text_component,
                          rule.column_role, rule.column_role_source), before)

    def test_06b_the_restore_is_not_a_replay_of_the_promotion(self):
        """MJ32's rule, one board over. A promotion RE-DERIVES the role from the
        value type (CR-A2); an undo has to give back the role the column actually
        had, whatever a person had set it to."""
        cfg = self._config('J8 undo role')
        rule = self._rule(cfg, 'J8UROLE', 10)
        self.Studio.employee_mapping_make_component(rule.id, 'amount')
        rule.write({'column_role': 'reference', 'column_role_source': 'auto'})
        res = self.Studio.employee_mapping_detach_component(rule.id)
        self.Studio.employee_component_restore(res['snapshot'])
        self.assertEqual(rule.column_role, 'reference',
                         "the undo re-derived the role instead of restoring it")
        self.assertEqual(rule.column_role_source, 'auto')

    def test_06c_a_malformed_snapshot_is_refused(self):
        for bad in (None, False, 'nonsense', [], {'rule_id': 0},
                    {'rule_id': 9999999999}):
            res = self.Studio.employee_component_restore(bad)
            self.assertFalse(res.get('ok'), bad)
            self.assertTrue(res.get('msg'), bad)

    def test_07_detach_is_refused_once_contracts_carry_values(self):
        """And the refusal names the door that IS open (MF-B3): re-routing keeps
        the history, detaching would orphan it."""
        cfg = self._config('J8 refusal')
        rule = self._rule(cfg, 'J8REF', 10)
        self.Studio.employee_mapping_make_component(rule.id, 'amount')
        tpl = self.Template.create({'name': 'J8 refusal', 'code': 'J8REF',
                                    'value_type': 'amount'})
        employee = self.env['hr.employee'].create({'name': 'J8 refusal subject'})
        contract = self.env['hr.contract'].create({
            'name': 'J8 refusal contract', 'employee_id': employee.id,
            'wage': 1000.0, 'state': 'draft'})
        self.Advantage.create({'contract_id': contract.id,
                               'advantage_template_id': tpl.id, 'amount': 25.0})

        res = self.Studio.employee_mapping_detach_component(rule.id)
        self.assertFalse(res.get('ok'))
        self.assertIn('J8REF', res.get('msg') or '')
        self.assertNotIn('snapshot', res)
        self.assertTrue(rule.is_contract_component, "the refusal still wrote")

        # CR18 — an EMPTY line seeded by `hr.contract.create` must not refuse it
        rule2 = self._rule(cfg, 'J8REF2', 20)
        self.Studio.employee_mapping_make_component(rule2.id, 'amount')
        tpl2 = self.Template.create({'name': 'J8 refusal 2', 'code': 'J8REF2',
                                     'value_type': 'amount'})
        self.Advantage.create({'contract_id': contract.id,
                               'advantage_template_id': tpl2.id, 'amount': 0.0})
        self.assertTrue(
            self.Studio.employee_mapping_detach_component(rule2.id).get('ok'),
            "an empty seeded line blocked a detach (CR18)")

    def test_08_a_type_clash_is_refused_at_wire_time(self):
        """`_get_or_create_advantage_template` NEVER flips an existing template's
        `value_type` — it logs a warning, server-side, where no user will see it.
        Accepting the wire would be a promise the import quietly declines."""
        cfg = self._config('J8 clash')
        rule = self._rule(cfg, 'J8CLASH', 10)
        self.Template.create({'name': 'J8 clash', 'code': 'J8CLASH',
                              'value_type': 'text'})
        res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, 'c:amount')
        self.assertFalse(res.get('ok'))
        self.assertIn('J8CLASH', res.get('msg') or '')
        self.assertFalse(rule.is_contract_component, "a refused wire still wrote")
        # the SAME type is of course fine
        self.assertTrue(
            self.Studio.employee_mapping_create(cfg.id, False, rule.id,
                                                'c:text').get('ok'))
        # and the guard lives in the promotion, so the menu verb inherits it
        rule2 = self._rule(cfg, 'J8CLASH2', 20)
        self.Template.create({'name': 'J8 clash 2', 'code': 'J8CLASH2',
                              'value_type': 'amount'})
        self.assertFalse(
            self.Studio.employee_mapping_make_component(rule2.id, 'text').get('ok'))
        # a code with NO template yet is free to be either
        rule3 = self._rule(cfg, 'J8FREE', 30)
        self.assertTrue(
            self.Studio.employee_mapping_make_component(rule3.id, 'text').get('ok'))

    # ============================================= D1 — "does this exist yet?"
    def test_09_the_state_line_answers_the_owners_question(self):
        cfg = self._config('J8 state')
        rule = self._rule(cfg, 'J8STATE', 10)
        self.Studio.employee_mapping_make_component(rule.id, 'amount')

        cards = {i['id']: i for i in self.Studio._ec_right_column('', cfg)}
        note = cards['c:amount']['meta'].get('note')
        self.assertTrue(note, "the amount card said nothing about its state")
        self.assertIn('first import', note['text'])
        self.assertNotEqual(note['tone'], 'warn',
                            "a scheme nothing has imported yet is not a fault")
        # the TEXT card has no text components, so it has nothing to report
        self.assertIsNone(cards['c:text']['meta'].get('note'))

        # ...now give it a template and a filled line
        tpl = self.Template.create({'name': 'J8 state', 'code': 'J8STATE',
                                    'value_type': 'amount'})
        employee = self.env['hr.employee'].create({'name': 'J8 state subject'})
        contract = self.env['hr.contract'].create({
            'name': 'J8 state contract', 'employee_id': employee.id,
            'wage': 1000.0, 'state': 'draft'})
        self.Advantage.create({'contract_id': contract.id,
                               'advantage_template_id': tpl.id, 'amount': 12.0})
        cards = {i['id']: i for i in self.Studio._ec_right_column('', cfg)}
        self.assertIn('1', cards['c:amount']['meta']['note']['text'])

    def test_09b_an_empty_seeded_line_is_not_a_stored_value(self):
        """CR18 again, in the counter this time: `hr.contract.create` seeds one
        empty advantage line per template on EVERY contract, so a bare line count
        would report every contract in the database as carrying a value."""
        cfg = self._config('J8 seeded')
        rule = self._rule(cfg, 'J8SEED', 10)
        self.Studio.employee_mapping_make_component(rule.id, 'amount')
        tpl = self.Template.create({'name': 'J8 seeded', 'code': 'J8SEED',
                                    'value_type': 'amount'})
        employee = self.env['hr.employee'].create({'name': 'J8 seeded subject'})
        contract = self.env['hr.contract'].create({
            'name': 'J8 seeded contract', 'employee_id': employee.id,
            'wage': 1000.0, 'state': 'draft'})
        self.Advantage.create({'contract_id': contract.id,
                               'advantage_template_id': tpl.id, 'amount': 0.0})
        state = self.Studio._ec_component_state(cfg)
        self.assertEqual(state['amount']['templates'], 1)
        self.assertEqual(state['amount']['contracts'], 0)
        note = self.Studio._ec_component_state_note('amount', state)
        self.assertIn('no values stored', note['text'].lower())

    def test_09c_one_contract_carrying_two_components_is_one_contract(self):
        """Why the count is a `count_distinct` aggregate and not a line
        `search_count`: a lane spans several codes."""
        cfg = self._config('J8 distinct')
        employee = self.env['hr.employee'].create({'name': 'J8 distinct subject'})
        contract = self.env['hr.contract'].create({
            'name': 'J8 distinct contract', 'employee_id': employee.id,
            'wage': 1000.0, 'state': 'draft'})
        for n in range(3):
            code = 'J8DIST%s' % n
            rule = self._rule(cfg, code, 10 + n)
            self.Studio.employee_mapping_make_component(rule.id, 'amount')
            tpl = self.Template.create({'name': code, 'code': code,
                                        'value_type': 'amount'})
            self.Advantage.create({'contract_id': contract.id,
                                   'advantage_template_id': tpl.id, 'amount': 5.0})
        state = self.Studio._ec_component_state(cfg)
        self.assertEqual(state['amount']['templates'], 3)
        self.assertEqual(state['amount']['contracts'], 1)

    def test_10_the_counts_and_the_unresolved_footer_still_read_correctly(self):
        """A component is resolved and never "unmapped" — visibly wiring it must
        not have changed either number, and the role chips must not double-count
        a column that now carries a wire AND a flag."""
        cfg = self._config('J8 counts')
        comp = self._rule(cfg, 'J8CNT', 10)
        stray = self._rule(cfg, 'J8STRAY', 20, column_role='profile')
        self.Studio.employee_mapping_make_component(comp.id, 'amount')

        data = self.Studio.employee_mapping_data(cfg.id, include_payroll=True)
        self.assertEqual(data['unresolved'], 1, "the stray column is the only one")
        self.assertNotIn(comp.id, self.Studio._ec_unresolved(cfg).ids)
        counts = data['counts']
        self.assertEqual(counts['payroll']['total'], 1)
        self.assertEqual(counts['payroll']['unmapped'], 0)
        self.assertEqual(counts['profile']['unmapped'], 1)
        self.assertEqual(sum(c['total'] for c in counts.values()),
                         len(cfg.rule_ids), "a column was counted twice")
        self.assertEqual(stray.column_role, 'profile')

    # ==================================================== D2 — the arrowhead
    def test_11_the_column_gutter_is_wide_enough_for_an_arrowhead(self):
        """The inequality that IS the defect. Two constants had to agree — one in
        a stylesheet, one in a pure kernel — and nothing compared them."""
        geo = _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                   'mapping_geometry.js')
        head = int(re.search(r'export const HEAD = (\d+)', geo).group(1))
        gap = int(re.search(r'export const ANCHOR_GAP = (\d+)', geo).group(1))
        self.assertIn('export const WIRE_GUTTER = ANCHOR_GAP + HEAD + 3', geo)
        gutter = gap + head + 3

        scss = _strip_scss_comments(
            _src('pb_formula_studio', 'static', 'src', 'scss', 'mapping.scss'))
        body = _rule_block(scss, '.mapping-canvas .mc-col-body')
        pad = re.search(r'padding:\s*[\d.]+px\s+([\d.]+)px', body)
        self.assertTrue(pad, "`.mc-col-body` has no horizontal padding to check")
        self.assertEqual(float(pad.group(1)), float(gutter),
                         "the stylesheet's gutter and WIRE_GUTTER disagree")
        self.assertGreaterEqual(gutter, gap + head,
                                "the arrowhead is drawn outside the padding box, "
                                "which is where the scrollbar is")

    def test_11b_the_canvas_anchors_with_the_named_constants(self):
        """The literal `+ 4` / `- 4` and the literal `14` were the same two
        numbers, spelled twice, in two files."""
        js = _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                  'mapping_canvas.js')
        self.assertIn('const sx = L.edge + ANCHOR_GAP, tx = R.edge - ANCHOR_GAP', js)
        self.assertIn('br.right - rb.left - WIRE_GUTTER', js)
        self.assertIn('br.left - rb.left + WIRE_GUTTER', js)
        self.assertNotIn('const sx = L.edge + 4', js)

    def test_11c_the_wire_layer_is_still_painted_under_the_columns(self):
        """The fix must be the GUTTER, not a z-index. Lifting `.mc-wires` over
        `.mc-cols` would have hidden this defect by painting every wire across
        the cards it runs past."""
        scss = _strip_scss_comments(
            _src('pb_formula_studio', 'static', 'src', 'scss', 'mapping.scss'))
        wires = _rule_block(scss, '.mapping-canvas .mc-wires')
        cols = _rule_block(scss, '.mapping-canvas .mc-cols')
        self.assertIn('z-index: 1', wires)
        self.assertIn('z-index: 2', cols)

    def test_12_the_sweep_measures_arrowheads_and_says_why_it_could_not(self):
        """MJ12 excludes every `SVGElement` from the bounding-box sweep, which is
        correct and is exactly why no sweep has ever measured a wire (MJ30). An
        arrowhead is content, so it is re-admitted BY NAME — never `<path>` — and
        tested against the named opaque boxes of the column layer, the scrollbar
        gutter included. A scrollbar is not an element, so no rect-versus-element
        pass could have found this."""
        sweep = _src('pb_formula_studio', 'tools', 'mapping_overlap_sweep.js')
        self.assertIn('polygon.mc-head', sweep)
        self.assertIn('scrollbar-gutter', sweep)
        self.assertIn('headOcclusions', sweep)
        self.assertIn('maxErr', sweep)
        # the MJ12 exclusion it deliberately steps around is still in force for
        # everything else
        self.assertIn('!(e instanceof SVGElement)', sweep)

    def test_12b_a_wire_names_the_cards_it_claims(self):
        """What makes the endpoint harness a committed artefact instead of a
        console snippet retyped once per phase (MJ30)."""
        xml = _src('pb_formula_studio', 'static', 'src', 'xml', 'mapping_canvas.xml')
        for attr in ('t-att-data-wire="g.id"', 't-att-data-left="g.leftId"',
                     't-att-data-right="g.rightId"', 't-att-data-dockl="g.dockL"',
                     't-att-data-dockr="g.dockR"'):
            self.assertIn(attr, xml)

    # ================================================ the traps, as invariants
    def test_13_the_promoted_card_cannot_vanish_under_its_own_wire(self):
        """`make_component('amount')` sets `column_role = 'payroll'`, and this
        board hides payroll-role cards until the chip is on. MF15 revealed the
        lane for the MENU verb; a wire is the same act by another gesture."""
        js = _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                  'mapping_studio.js')
        self.assertIn('const revealPayroll = p === "employee" && rightId === "c:amount"',
                      js)
        self.assertIn('if (revealPayroll) { this.state.empPayroll = true; }', js)
        # and a REFUSAL must not leave the board somewhere nobody asked for
        self.assertIn('if (revealPayroll) { this.state.empPayroll = false; }', js)

    def test_13b_the_undo_toast_is_one_helper_and_not_a_second_copy(self):
        """J6's grep-proof rule: two copies would drift, and the copy that
        drifted would be the one on the board nobody was testing that week."""
        js = _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                  'mapping_studio.js')
        self.assertEqual(js.count('async _removeWireUndoable('), 1)
        self.assertEqual(js.count('autocloseDelay: UNDO_MS'), 1)
        self.assertIn('_removeWireUndoable("employee_mapping_detach_component",', js)
        self.assertIn('"employee_component_restore",', js)

    def test_14_the_promotion_has_exactly_one_implementation(self):
        """The `c:` branch ROUTES; it does not repeat. A second promotion path is
        how the role rule (CR-A2) and the one-destination rule would come to
        disagree with themselves."""
        py = _src('pb_formula_studio', 'models', 'pb_formula_studio.py')
        create = py.split('def employee_mapping_create(')[1].split('\n    @api.model')[0]
        self.assertIn("return self.employee_mapping_make_component(comp.id, kind)",
                      create)
        self.assertNotIn("'is_contract_component': True", create)

    def test_15_no_user_visible_string_says_odoo(self):
        """The white-label absolute, over everything this phase added."""
        py = _src('pb_formula_studio', 'models', 'pb_formula_studio.py')
        for m in re.finditer(r'_\((.*?)\)', py, flags=re.S):
            self.assertNotIn('Odoo', m.group(1))
        js = _src('pb_formula_studio', 'static', 'src', 'js', 'mapping',
                  'mapping_studio.js')
        for m in re.finditer(r'_t\((.*?)\)', js, flags=re.S):
            self.assertNotIn('Odoo', m.group(1))
