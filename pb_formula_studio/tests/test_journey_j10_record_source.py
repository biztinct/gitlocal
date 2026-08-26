# -*- coding: utf-8 -*-
"""JOURNEY J10 — the record destination is a source, and it is rank 4.

The owner's bug report, verbatim: *"Currently you are showing EMPLOYEE RECORD or
CONTRACT RECORD only if that is the only source."* It was one line —
`if out: return out` — sitting above the record tier in `_declared_sources`,
which made that tier reachable only when the list was otherwise empty. The
contract component two lines further down had been APPENDED unconditionally
since J9, and that is exactly the treatment the owner asked for here.

Ten of abm's twenty-one mappings sit on a component that already declares
something, so ten cards were silently hiding half of what they do. DESIGNATION
is the one in the screenshot: a feed key AND a `hr.contract.job_id` destination,
rendering as "Connected system" alone.

Nothing moved (J-D5). Rank 4 is where the resolver's tail has always read the
mapped record — after the spreadsheet, before the contract component — so
`_SOURCE_RANK` gained three names for a rung that already existed.
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
class TestJourneyJ10RecordSource(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Connector = cls.env['hr.integration.connector']
        cls.FM = cls.env['hr.integration.field.mapping']
        cls.Mapping = cls.env['hr.payslip.import.mapping']

    # ------------------------------------------------------------- fixtures
    def _world(self, name='J10 Display'):
        conn = self.Connector.create({'name': 'J10 Conn',
                                      'connector_type': 'demo'})
        cfg = self.Config.create({
            'name': name, 'code': name.upper().replace(' ', '')[:32],
            'country_code': 'VN', 'state': 'active',
        })
        rule = self.Rule.create({
            'config_id': cfg.id, 'name': 'Designation', 'code': 'J10DESIGNAT',
            'column_type': 'input', 'sequence': 1,
        })
        return conn, cfg, rule

    def _map_field(self, cfg, rule, model, field):
        return self.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': self.env['ir.model'].search(
                [('model', '=', model)], limit=1).id,
            'target_field_id': self.env['ir.model.fields'].search(
                [('model', '=', model), ('name', '=', field)], limit=1).id,
        })

    def _map_bank(self, cfg, rule, role='bank_name'):
        return self.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'bank_account', 'bank_role': role})

    def _declared(self, cfg, rule):
        return self.Studio._declared_sources(
            rule, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))

    # =====================================================================
    # 1 — the DESIGNATION shape: two entries, feed first, record second
    # =====================================================================
    def test_01_a_feed_source_and_a_contract_field_render_two_entries(self):
        _conn, cfg, rule = self._world('J10 Designation')
        rule.set_source_binding('feed', 'Designation')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        out = self._declared(cfg, rule)
        self.assertEqual([d['kind'] for d in out], ['feed', 'contract_field'],
                         "the owner's screenshot: Connected system¹ · Contract "
                         "record² — and until J10 the second one was invisible")
        self.assertEqual(out[0]['key'], 'Designation')
        self.assertEqual(out[1]['key'], 'job_id')
        self.assertTrue(out[1]['label'],
                        "the chip's sentence names the FIELD, not job_id")

    def test_01b_the_early_return_is_gone(self):
        """The defect was one line, and a source assertion is the only thing
        that stops it coming back by a tidy-looking refactor."""
        src = _src('pb_formula_studio', 'models', 'pb_formula_studio.py')
        body = src.split('def _declared_sources(', 1)[1] \
                  .split('\n    #: Board-chip wording', 1)[0]
        body = re.sub(r'^\s*#.*$', '', body, flags=re.M)
        self.assertNotIn('emp_dest_rule_ids', body)
        # the record entry is appended BEFORE the sort, so rank places it
        self.assertLess(body.index('record_dests'), body.index('out.sort('),
                        "the record tier must join the list before it is "
                        "ranked, not be returned instead of it")

    # =====================================================================
    # 2 — the scalar shape is unchanged; four callers depend on it
    # =====================================================================
    def test_02_the_scalar_declared_source_still_returns_the_winner(self):
        _conn, cfg, rule = self._world('J10 Scalar')
        rule.set_source_binding('feed', 'Designation')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        one = self.Studio._declared_source(
            rule, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))
        self.assertEqual(one['kind'], 'feed')
        self.assertEqual(set(one) & {'kind', 'key', 'wirable'},
                         {'kind', 'key', 'wirable'})
        # Journey bucketing reads exactly this, and it must not have moved
        counts, _ids = self.Studio._journey_scheme_lane(
            cfg, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))
        self.assertEqual(counts['wired'], 1)
        self.assertEqual(counts['people'], 0)

    def test_02b_a_record_only_component_counts_as_people_whichever_record(self):
        """The lane counts people data. A designation kept on the CONTRACT is
        people data exactly as much as one kept on the employee; before J10 the
        contract case reported `employee_field` and was counted anyway, which
        was the right total for the wrong reason."""
        _conn, cfg, rule = self._world('J10 Lane')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        counts, _ids = self.Studio._journey_scheme_lane(
            cfg, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))
        self.assertEqual(counts['people'], 1)
        self.assertEqual(counts['unfed'], 0)

    # =====================================================================
    # 3 — the three spellings
    # =====================================================================
    def test_03a_hr_employee_is_employee_field(self):
        _conn, cfg, rule = self._world('J10 Emp')
        self._map_field(cfg, rule, 'hr.employee', 'barcode')
        out = self._declared(cfg, rule)
        self.assertEqual(out[0]['kind'], 'employee_field')
        self.assertEqual(out[0]['key'], 'barcode')

    def test_03b_hr_contract_is_contract_field(self):
        _conn, cfg, rule = self._world('J10 Con')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        out = self._declared(cfg, rule)
        self.assertEqual(out[0]['kind'], 'contract_field')

    def test_03c_a_bank_row_is_bank_account_keyed_by_role(self):
        _conn, cfg, rule = self._world('J10 Bank')
        self._map_bank(cfg, rule, 'bank_name')
        out = self._declared(cfg, rule)
        self.assertEqual(out[0]['kind'], 'bank_account')
        self.assertEqual(out[0]['key'], 'bank_name')
        self.assertEqual(out[0]['label'], 'Bank name')

    def test_03d_the_labels_are_the_owners_words_and_carry_no_vendor_name(self):
        self.assertEqual(self.Studio._source_label('contract_field'),
                         "Contract record")
        self.assertEqual(self.Studio._source_label('bank_account'),
                         "Bank account")
        self.assertEqual(self.Studio._source_label('employee_field'),
                         "Employee record")
        for kind in self.Studio._SOURCE_LABELS:
            self.assertNotIn('odoo', self.Studio._source_label(kind).lower())

    # =====================================================================
    # 4 — a record-only card is exactly what it was: one chip, no superscript
    # =====================================================================
    def test_04_a_record_only_card_renders_one_unranked_chip(self):
        """J9 case 15's guarantee, and the regression this phase could most
        easily cause: a card that had one chip must still have one."""
        _conn, cfg, rule = self._world('J10 Only')
        self._map_field(cfg, rule, 'hr.employee', 'barcode')
        item = self.Studio._mc_right_item(rule, self._declared(cfg, rule))
        self.assertEqual(len(item['srcKinds']), 1)
        self.assertEqual(item['srcKinds'][0]['rank'], 0,
                         "a number that is always 1 is decoration")
        self.assertEqual(item['srcKind'], 'employee_field')

    def test_04b_two_sources_rank_one_and_two_among_this_cards_sources(self):
        _conn, cfg, rule = self._world('J10 Ranked')
        rule.set_source_binding('feed', 'Designation')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        item = self.Studio._mc_right_item(rule, self._declared(cfg, rule))
        self.assertEqual([s['rank'] for s in item['srcKinds']], [1, 2])
        self.assertEqual([s['kind'] for s in item['srcKinds']],
                         ['feed', 'contract_field'])
        self.assertIn('Tried first', item['srcKinds'][0]['note'])
        self.assertIn('nothing above', item['srcKinds'][1]['note'])

    def test_04c_the_chip_sentence_names_the_field_not_its_technical_name(self):
        _conn, cfg, rule = self._world('J10 Sentence')
        rule.set_source_binding('feed', 'Designation')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        note = self.Studio._mc_right_item(
            rule, self._declared(cfg, rule))['srcKinds'][1]['note']
        self.assertNotIn('job_id', note,
                         "the key is for comparing; the label is for reading")
        self.assertIn('Contract record', note)

    def test_04d_three_sources_read_one_two_three_in_rank_order(self):
        _conn, cfg, rule = self._world('J10 Three')
        rule.set_source_binding('feed', 'Designation')
        rule.set_source_binding('excel', 'SEVL|Designation')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        out = self._declared(cfg, rule)
        self.assertEqual([d['kind'] for d in out],
                         ['feed', 'excel', 'contract_field'])
        item = self.Studio._mc_right_item(rule, out)
        self.assertEqual([s['rank'] for s in item['srcKinds']], [1, 2, 3])

    def test_04e_the_contract_component_stays_last(self):
        _conn, cfg, rule = self._world('J10 Last')
        rule.set_source_binding('excel', 'SEVL|Gas')
        rule.is_contract_component = True
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        out = self._declared(cfg, rule)
        self.assertEqual([d['kind'] for d in out],
                         ['excel', 'contract_field', 'contract_component'])

    # =====================================================================
    # 5 — one query for the whole config
    # =====================================================================
    def test_05_source_record_dests_is_one_query_for_a_whole_config(self):
        _conn, cfg, rule = self._world('J10 Queries')
        for i in range(98):
            r = self.Rule.create({
                'config_id': cfg.id, 'name': 'Col %s' % i,
                'code': 'J10C%03d' % i, 'column_type': 'input',
                'sequence': i + 2})
            if i % 3 == 0:
                self._map_field(cfg, r, 'hr.employee', 'barcode')
        self.env.flush_all()
        cfg.invalidate_recordset()
        cfg.rule_ids.ids       # warm the o2m so the count is about the method
        self.env.invalidate_all()
        rules = cfg.rule_ids.ids
        with self.assertQueryCount(__system__=1):
            dests = self.Studio._source_record_dests(cfg.browse(cfg.id))
        self.assertGreater(len(dests), 30)
        self.assertEqual(len(rules), 99)

    # =====================================================================
    # 6 — the note states the order, with the field's human name in it
    # =====================================================================
    def test_06_the_source_note_states_the_resulting_order(self):
        _conn, cfg, rule = self._world('J10 Note')
        rule.set_source_binding('feed', 'Designation')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        note = self.Studio._source_note(
            rule, {}, self.Studio._source_record_dests(cfg),
            self.Studio._source_wire_dests(cfg))
        self.assertIn('Read in this order', note)
        self.assertIn('Contract record', note)
        self.assertNotIn('job_id', note)

    def test_06b_the_draw_dialog_describes_the_same_order_as_the_card(self):
        """The dialog and the card behind it must not disagree about how many
        sources a component has — J6's W76.3 class of defect."""
        _conn, cfg, rule = self._world('J10 Dialog')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        order = self.Studio._probe_order(rule, 'excel', 'SEVL|Designation')
        self.assertEqual([o['label'] for o in order],
                         [self.Studio._source_label('excel'),
                          self.Studio._source_label('contract_field')])

    # =====================================================================
    # 7 — the (kind, key) fold still holds, and the vocabulary is shared
    # =====================================================================
    def test_07a_a_wire_and_a_feed_source_are_still_one_entry(self):
        """T1, re-run with a record destination beside it: a fold that broke
        would show twenty-one cards with two chips instead of the real
        number, and the canvas' label dedupe would hide the evidence."""
        conn, cfg, rule = self._world('J10 Fold')
        self.FM.create({'connector_id': conn.id, 'target_rule_id': rule.id,
                        'source_field': 'Designation', 'active_state': 'active'})
        rule.set_source_binding('feed', 'Designation')
        self._map_field(cfg, rule, 'hr.contract', 'job_id')
        out = self._declared(cfg, rule)
        self.assertEqual([d['kind'] for d in out], ['feed', 'contract_field'])

    def test_07b_the_client_reads_the_same_ten_words_as_the_server(self):
        js = _strip_js_comments(_src(
            'pb_formula_studio', 'static/src/js/source_vocab.js'))
        for label in ("Contract record", "Bank account"):
            self.assertIn('_t("%s")' % label, js)
        canvas = _strip_js_comments(_src(
            'pb_formula_studio', 'static/src/js/mapping/mapping_canvas.js'))
        self.assertEqual(canvas.count('contract_field: _t("Contract record")'), 2,
                         "srcChip and srcChips both carry the vocabulary; a "
                         "kind missing from either renders NO chip at all")
        self.assertEqual(canvas.count('bank_account: _t("Bank account")'), 2)

    def test_07c_every_source_kind_has_a_glyph_and_a_chip_colour(self):
        js = _src('pb_formula_studio', 'static/src/js/source_vocab.js')
        scss = _src('pb_formula_studio', 'static/src/scss/mapping.scss')
        xml = _src('pb_formula_studio', 'static/src/xml/studio.xml')
        for kind, icon in (('contract_field', 'filetext'),
                           ('bank_account', 'bank')):
            self.assertIn('{ key: "%s", icon: "%s" }' % (kind, icon), js)
            self.assertIn('.mc-src.s-%s' % kind, scss)
            self.assertIn("icon === '%s'" % icon, xml)

    def test_07d_no_user_visible_string_added_here_says_odoo(self):
        for kind in ('contract_field', 'bank_account'):
            self.assertNotIn('odoo', self.Studio._source_label(kind).lower())
            note = self.Studio._source_rank_note(kind, 'k', 0, 2, label='L')
            self.assertNotIn('odoo', note.lower())
