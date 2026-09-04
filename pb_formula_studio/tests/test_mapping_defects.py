# -*- coding: utf-8 -*-
"""MAPFIX Phase D — the five defects the owner reported against the live board.

Three of them are keyboard or layout defects and live in
`static/tests/mapping_canvas.test.js`, because no Python assertion can see a
button painted over a field name. What is asserted here is the half of the story
the server owns:

  * D1 — a wrong-TYPE `target_spec` is a refusal, not a traceback. The client fix
    stops it being sent; this stops it being fatal when something else sends it,
    which is the only half that protects a second caller (tests 1-3);
  * D4 — a selection destination says which values it accepts, INCLUDING the
    stored code, because the import validates against the code and stores None on
    a miss. Built once per model, not once per card, on a board that draws 193 of
    them (tests 4-6);
  * D5 — the many2one auto-create behaviour is unchanged and now VISIBLE. The
    card's promise and the batch's behaviour come from the same predicate, so
    they cannot disagree (tests 7-9).
"""
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models.payroll_import_batch import (
    m2o_creates_missing, m2o_resolution_key,
)


class _FakeM2O:
    """The two attributes `_ec_m2o_note` reads. A stub is the only way to ask the
    question about a comodel that no hr.employee field happens to point at."""

    type = 'many2one'

    def __init__(self, comodel_name):
        self.comodel_name = comodel_name


@tagged('post_install', '-at_install')
class TestMappingDefects(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']

    def _config(self, name):
        # CR19 — `country_code` is required with no default.
        return self.Config.create({
            'name': name, 'code': name.replace(' ', '_').upper()[:32],
            'country_code': 'VN', 'state': 'active',
        })

    def _rule(self, cfg, code, seq=10, **kw):
        vals = {'config_id': cfg.id, 'name': kw.pop('name', code.title()),
                'code': code, 'column_type': kw.pop('column_type', 'input'),
                'sequence': seq}
        vals.update(kw)
        return self.Rule.create(vals)

    # --------------------------------------------------------------- test 1
    def test_01_an_integer_target_spec_is_refused_not_raised(self):
        """The owner's crash: `'int' object has no attribute 'startswith'`.

        `spec = target_spec or ''` catches a FALSY spec and not a wrong-typed
        one — `123 or ''` is `123` — so the guard passed an integer straight into
        `.startswith`. The RPC must answer, and the answer must be a sentence the
        board can show.
        """
        cfg = self._config('MAPFIX D1')
        rule = self._rule(cfg, 'DONECODE', name='Status')

        res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, 123)
        self.assertFalse(res.get('ok'))
        self.assertTrue(res.get('msg'), "a refusal with no sentence is a dead end")
        self.assertNotIn('Odoo', res.get('msg'))       # white-label, standing rule

        # and nothing was written on the way to refusing
        self.assertEqual(self.env['hr.payslip.import.mapping'].sudo().search_count(
            [('salary_structure_id', '=', cfg.id)]), 0)

    # --------------------------------------------------------------- test 2
    def test_02_every_unusable_spec_shape_is_answered(self):
        cfg = self._config('MAPFIX D1 shapes')
        rule = self._rule(cfg, 'SHAPECODE', name='Shape')
        for spec in (123, 0, None, False, True, [], {}, 'f:', 'f:hr.employee',
                     'f:hr.employee:no_such_field_at_all', 'b:', 'b:not_a_role',
                     'x:hr.employee:name', ''):
            res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, spec)
            self.assertFalse(res.get('ok'), "%r was accepted" % (spec,))
        self.assertEqual(self.env['hr.payslip.import.mapping'].sudo().search_count(
            [('salary_structure_id', '=', cfg.id)]), 0)

    # --------------------------------------------------------------- test 3
    def test_03_a_wrong_typed_component_id_is_refused_too(self):
        """The mirror of test 1 — the other id on the same call comes from the
        same browser and can be wrong in the same way."""
        cfg = self._config('MAPFIX D1 comp')
        res = self.Studio.employee_mapping_create(
            cfg.id, False, 'f:hr.employee:name', 'f:hr.employee:name')
        self.assertFalse(res.get('ok'))
        # the siblings on the same board
        self.assertTrue(self.Studio.employee_mapping_delete('not-an-id').get('ok'))
        self.assertFalse(
            self.Studio.employee_mapping_make_component('nope').get('ok'))
        self.assertFalse(
            self.Studio.employee_mapping_detach_component('nope').get('ok'))

    # --------------------------------------------------------------- test 4
    def test_04_a_selection_card_lists_its_values_with_the_stored_code(self):
        """Asserted over EVERY selection destination the catalogue offers, not
        against one field name.

        The first cut named `hr.employee.marital` — which on a Vietnamese database
        is **not stored** (the localisation's `vietnam_marital_status` is), so the
        catalogue rightly excludes it and the test failed on a build that was
        working. MF11's lesson again: a field's presence is a property of the
        database, the note is a property of the rule.
        """
        sel_cards = [i for i in self.Studio._ec_right_items()
                     if i['meta'].get('ttype') == 'selection']
        self.assertTrue(sel_cards, "no selection destination on the board at all")
        checked = 0
        for card in sel_cards:
            _f, model, fname = card['id'].split(':', 2)
            field = self.env[model]._fields[fname]
            keys = [k for k, _l in (field._description_selection(self.env) or [])]
            if not keys:
                continue                    # nothing to promise, nothing to check
            note = card['meta'].get('note')
            self.assertTrue(note, "%s says nothing about its values" % card['id'])
            blob = '%s %s' % (note['text'], note['title'])
            # MAPFIX E1 — the tooltip is no longer the only place the values are.
            # A truncated note carries the structured list the popover opens, and
            # both it and the tooltip are capped at `_EC_SEL_VALUES_MAX`, because
            # one field with 430 timezones would otherwise be 26 KB of payload for
            # one card out of 240. What is promised is that every value the card
            # SHOWS is printed with its stored code, and that the cap is said out
            # loud rather than silently swallowing the tail.
            values = note.get('values') or []
            printed = blob + ' ' + ' '.join(v['key'] for v in values)
            if len(keys) > self.Studio._EC_SEL_VALUES_MAX:
                self.assertEqual(note.get('total'), len(keys))
                keys = keys[:self.Studio._EC_SEL_VALUES_MAX]
            for key in keys:
                self.assertIn(key, printed,
                              "%s: the stored value %r is nowhere on the card"
                              % (card['id'], key))
            self.assertNotIn('Odoo', blob)
            checked += 1
        self.assertTrue(checked, "every selection field came back empty")

    # --------------------------------------------------------------- test 5
    def test_05_a_non_selection_card_is_unchanged(self):
        items = {i['id']: i for i in self.Studio._ec_right_items()}
        plain = items.get('f:hr.employee:name')
        self.assertTrue(plain)
        self.assertNotIn('note', plain['meta'])
        self.assertEqual(plain['label'],
                         self.env['ir.model.fields'].sudo().search(
                             [('model', '=', 'hr.employee'), ('name', '=', 'name')],
                             limit=1).field_description)

    # --------------------------------------------------------------- test 6
    def test_06_notes_are_built_once_per_model_not_once_per_field(self):
        """The board draws 193 cards. A registry walk per card is the difference
        between a board and a wait, and nothing about the payload's SHAPE would
        show that it had happened."""
        Studio = type(self.Studio)
        real = Studio._ec_notes_for
        calls = []

        def counting(self_, model):
            calls.append(model)
            return real(self_, model)

        with patch.object(Studio, '_ec_notes_for', counting):
            items = self.Studio._ec_right_items()
        self.assertTrue(len(items) > 50, "the catalogue looks empty — test is moot")
        self.assertEqual(sorted(calls), ['hr.contract', 'hr.employee'],
                         "the note map was rebuilt per field, not per model")

    # --------------------------------------------------------------- test 7
    def test_07_the_m2o_card_says_what_the_import_will_do(self):
        """D5 (c) — the UI flag and the engine's behaviour come from ONE
        predicate, so a future edit cannot make the card lie."""
        items = {i['id']: i for i in self.Studio._ec_right_items()}
        dept = (items.get('f:hr.contract:department_id')
                or items.get('f:hr.employee:department_id'))
        self.assertTrue(dept, "department is not offered as a destination (MF11)")
        note = dept['meta'].get('note')
        self.assertTrue(note, "a many2one card says nothing about creation")
        self.assertEqual(note.get('tone'), '')
        self.assertTrue(m2o_creates_missing(self.env['hr.department']))

        # …and a comodel with no `name` is the other sentence, in the caution tone
        self.assertFalse(m2o_creates_missing(self.env['res.partner.bank']))
        self.assertEqual(m2o_resolution_key(self.env['res.partner.bank']),
                         self.env['res.partner.bank']._rec_name)
        caution = self.Studio._ec_m2o_note(_FakeM2O('res.partner.bank'))
        self.assertEqual(caution['tone'], 'warn')
        self.assertNotIn('Odoo', '%s %s' % (caution['text'], caution['title']))

    # --------------------------------------------------------------- test 8
    def test_08_the_engine_still_creates_and_still_refuses(self):
        """D5 says DO NOT change the behaviour — so it is asserted, not assumed.
        (a) an unseen department is created and linked; (b) a comodel with no
        `name` creates nothing and the column is left unset."""
        cfg = self._config('MAPFIX D5')
        rule = self._rule(cfg, 'DEPTD', name='Department', column_role='contract')
        res = self.Studio.employee_mapping_create(
            cfg.id, False, rule.id, 'f:hr.contract:department_id')
        self.assertTrue(res.get('ok'), res)

        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'MAPFIX D5 batch', 'formula_config_id': cfg.id})
        employee = self.env['hr.employee'].create({'name': 'MAPFIX D5 subject'})
        contract = self.env['hr.contract'].create({
            'name': 'MAPFIX D5 contract', 'employee_id': employee.id,
            'wage': 1000.0, 'state': 'draft'})

        self.assertEqual(self.env['hr.department'].search_count(
            [('name', '=', 'MAPFIX D5 Unseen Dept')]), 0)
        updates = batch._get_mapping_updates(
            contract, {'Department': 'MAPFIX D5 Unseen Dept'})
        made = self.env['hr.department'].browse(updates['department_id'])
        self.assertEqual(made.name, 'MAPFIX D5 Unseen Dept')

        # (b) nothing is minted for a comodel the import cannot name
        before = self.env['res.partner.bank'].sudo().search_count([])
        stub = _FakeM2O('res.partner.bank')
        stub.name = 'acc'
        self.assertIsNone(batch._coerce_mapped_value(
            employee, stub, 'MAPFIX-D5-NO-SUCH-ACCOUNT'))
        self.assertEqual(self.env['res.partner.bank'].sudo().search_count([]), before)

    # --------------------------------------------------------------- test 9
    def test_09_every_verb_on_a_card_carries_a_sentence(self):
        """D3 moved the verbs into a menu, where a row has room to say what it
        does. A verb with no hint is a menu row that reads like a guess."""
        cfg = self._config('MAPFIX D3 verbs')
        comp = self._rule(cfg, 'GRADED', name='Grade',
                          is_contract_component=True, is_text_component=True)
        plain = self._rule(cfg, 'PLAIND', seq=20, name='Shift code')
        for rule, is_comp in ((comp, True), (plain, False)):
            acts = self.Studio._ec_left_actions(rule, is_comp)
            self.assertTrue(acts)
            for act in acts:
                self.assertTrue(act.get('label'))
                self.assertTrue(act.get('hint'), "%s has no hint" % act['key'])
                self.assertNotIn('Odoo', '%s %s' % (act['label'], act['hint']))
