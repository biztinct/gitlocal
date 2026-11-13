# -*- coding: utf-8 -*-
"""MAPFIX Phase E — the two defects the owner reported against the live D board.

E1 is a rendering problem and its assertions are in
`static/tests/mapping_canvas.test.js`; the half the server owns is that a
TRUNCATED note carries the structured list to open, and a complete one does not
(test 5 here) — "clickable" and "truncated" have to be the same condition on both
sides of the wire or the board grows an affordance that does nothing.

E2 is structural, and all of it is here:

  * `_ec_is_mappable` asked whether a field was STORED. On Odoo 19 `hr.employee`
    delegates its HR data to `hr.version` (`_inherits`), so `employee_type`,
    `marital`, `sex`, `passport_id`, `job_title` and forty more are RELATED,
    non-stored — and perfectly writable. The predicate refused every one of them,
    which is why the six-value Employee Type selection was nowhere on the board
    (tests 1 and 4);
  * two construction sites built a right-hand card and only one of them passed a
    lane and a note, so a card that arrived by the other route was metadata-poor
    by accident. There is one now, and the invariant is asserted over the whole
    board rather than a sample (test 2);
  * a wire to a destination the catalogue refuses is kept — losing it would hide
    a live mapping — but it is MARKED, because the import will read that column
    and put the value nowhere (test 3).
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMappingSelectionValues(TransactionCase):

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
    def test_01_employee_type_is_a_destination_with_all_of_its_values(self):
        """The owner's exact defect.

        `hr.employee.employee_type` is a `_inherits` field (`version_id`), so it
        is not STORED on hr.employee and the old predicate refused it — while the
        form tooltip the owner read it off shows all six values, because the ORM
        resolves the delegate. Writable is the question; stored was the wrong one.
        """
        field = self.env['hr.employee']._fields.get('employee_type')
        if field is None:
            self.skipTest("this build has no hr.employee.employee_type")
        self.assertTrue(self.Studio._ec_is_mappable('hr.employee', 'employee_type'),
                        "employee_type is writable and is still being refused")
        notes = self.Studio._ec_notes_for('hr.employee')
        self.assertIn('employee_type', notes,
                      "the destination exists and says nothing about its values")
        note = notes['employee_type']
        keys = [k for k, _l in (field._description_selection(self.env) or [])]
        self.assertTrue(keys)
        printed = self._printed_keys(note)
        for key in keys:
            self.assertIn(key, printed,
                          "the stored value %r is nowhere on the card" % key)
        self.assertNotIn('Odoo', '%s %s' % (note['text'], note['title']))

        # …and it reaches the board, not just the note map
        items = {i['id']: i for i in self.Studio._ec_right_items()}
        self.assertIn('f:hr.employee:employee_type', items)

    def _printed_keys(self, note):
        """Every stored code the card puts in front of a reader — the inline text,
        the tooltip, and the structured list the popover opens."""
        blob = '%s %s' % (note.get('text') or '', note.get('title') or '')
        return blob + ' ' + ' '.join(v['key'] for v in (note.get('values') or []))

    # --------------------------------------------------------------- test 2
    def test_02_every_card_on_the_right_carries_the_same_metadata(self):
        """THE E2 INVARIANT, asserted over a live-shaped board.

        Every card the right column renders — catalogue, bank lane, or appended
        because something is wired to it — has a lane, a lane order and, when it
        is a selection or a many2one, a note. That is what the two construction
        sites used to disagree about.
        """
        cfg = self._config('MAPFIX E2 board')
        # one wire per shape the append path can meet: an ordinary catalogue
        # field, a selection, a many2one, a bank role.
        wires = (('EMPCODE', 'f:hr.employee:employee_id'),
                 ('EMPTYPE', 'f:hr.employee:employee_type'),
                 ('DEPTNAME', 'f:hr.contract:department_id'),
                 ('BANKACC', 'b:acc_number'))
        for n, (code, spec) in enumerate(wires):
            rule = self._rule(cfg, code, seq=10 + n, column_role='profile')
            res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, spec)
            self.assertTrue(res.get('ok'), '%s: %s' % (spec, res))

        data = self.Studio.employee_mapping_data(cfg.id, include_payroll=True)
        self.assertTrue(data.get('ok'), data)
        right = data['right']
        self.assertTrue(len(right) > 50, "the board looks empty — the test is moot")
        for card in right:
            meta = card.get('meta') or {}
            self.assertTrue(meta.get('lane'), "%s has no lane" % card['id'])
            self.assertIsInstance(meta.get('lane_order'), int,
                                  "%s has no lane order" % card['id'])
            self.assertTrue(card.get('group'), "%s has no group heading" % card['id'])
            if meta.get('ttype') in ('selection', 'many2one'):
                self.assertTrue(meta.get('note'),
                                "%s promises nothing about what it accepts"
                                % card['id'])

        # and the appended cards are not duplicates of catalogue ones
        ids = [c['id'] for c in right]
        self.assertEqual(len(ids), len(set(ids)), "a card was rendered twice")

    # --------------------------------------------------------------- test 3
    def test_03_a_wire_to_a_refused_destination_is_kept_and_marked(self):
        """E2 (3). `active` is stored and writable, so the mapping model accepts
        it, and it is on the catalogue's deny-list, so the board would never offer
        it — exactly the shape of an old mapping whose target the catalogue has
        since stopped believing in. Dropping the card would hide a live mapping;
        rendering it as an ordinary field would be a lie.
        """
        self.assertFalse(self.Studio._ec_is_mappable('hr.employee', 'active'))
        cfg = self._config('MAPFIX E2 refused')
        rule = self._rule(cfg, 'ARCHIVED', name='Archived', column_role='profile')
        fld = self.env['ir.model.fields'].sudo().search(
            [('model', '=', 'hr.employee'), ('name', '=', 'active')], limit=1)
        self.assertTrue(fld)
        self.env['hr.payslip.import.mapping'].sudo().create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field', 'target_model_id': fld.model_id.id,
            'target_field_id': fld.id,
        })

        data = self.Studio.employee_mapping_data(cfg.id, include_payroll=True)
        card = next((c for c in data['right']
                     if c['id'] == 'f:hr.employee:active'), None)
        self.assertTrue(card, "a live mapping's destination vanished from the board")
        note = (card.get('meta') or {}).get('note')
        self.assertTrue(note, "an unwritable destination says nothing about it")
        self.assertEqual(note.get('tone'), 'warn')
        self.assertFalse(card['meta'].get('mappable', True))
        self.assertNotIn('Odoo', '%s %s' % (note['text'], note['title']))
        self.assertTrue(card['meta'].get('lane'))
        # the wire itself survived
        self.assertEqual(len([w for w in data['wires']
                              if w['rightId'] == 'f:hr.employee:active']), 1)

    # --------------------------------------------------------------- test 4
    def test_04_the_predicate_change_is_visible_and_bounded(self):
        """What the widened predicate actually added, per model, and that it
        added it for the stated reason rather than by letting plumbing through.

        A zero gain would mean the diagnosis was wrong; an unbounded one would
        mean the deny-list stopped doing its job.
        """
        gained = {}
        for card in self.Studio._ec_right_items():
            model, fname = card['meta']['model'], card['meta']['field']
            field = self.env[model]._fields[fname]
            if not field.store:
                gained.setdefault(model, []).append(fname)
        self.assertTrue(gained, "no non-stored destination was gained — E2's "
                                "diagnosis does not hold on this build")
        for model, names in gained.items():
            for fname in names:
                field = self.env[model]._fields[fname]
                self.assertFalse(field.readonly)
                self.assertTrue(getattr(field, 'inherited', False)
                                or field.related or field.inverse,
                                "%s.%s is not writable and was offered anyway"
                                % (model, fname))
        # the delegation's own machinery stays out
        offered = {c['id'] for c in self.Studio._ec_right_items()}
        for fname in ('version_id', 'date_version',
                      'last_modified_date', 'last_modified_uid'):
            self.assertNotIn('f:hr.employee:%s' % fname, offered,
                             "%s is hr.version plumbing, not a destination" % fname)

    # --------------------------------------------------------------- test 5
    def test_05_only_a_truncated_note_carries_a_list_to_open(self):
        """E1's server half. `values` is the client's "this is clickable" signal,
        so it must appear exactly when the inline text hid something."""
        seen_short = seen_long = False
        for card in self.Studio._ec_right_items():
            if card['meta'].get('ttype') != 'selection':
                continue
            note = card['meta'].get('note')
            if not note:
                continue
            model, fname = card['meta']['model'], card['meta']['field']
            field = self.env[model]._fields[fname]
            pairs = field._description_selection(self.env) or []
            truncated = (len(pairs) > self.Studio._EC_SEL_INLINE_MAX
                         or note['text'].endswith('…'))
            if truncated:
                seen_long = True
                values = note.get('values')
                self.assertTrue(values, "%s is truncated and cannot be opened"
                                        % card['id'])
                self.assertLessEqual(len(values), self.Studio._EC_SEL_VALUES_MAX)
                self.assertEqual(note.get('total'), len(pairs))
                keys = [k for k, _l in pairs][:len(values)]
                self.assertEqual([v['key'] for v in values], keys)
                for v in values:
                    self.assertTrue(v['label'])
            else:
                seen_short = True
                self.assertNotIn('values', note,
                                 "%s shows every value and is clickable anyway"
                                 % card['id'])
        self.assertTrue(seen_long, "no truncated selection note on this board")
        self.assertTrue(seen_short, "no complete selection note on this board")

    # --------------------------------------------------------------- test 6
    def test_06_the_dropdowns_and_the_search_offer_what_the_board_offers(self):
        """E2 (4) — confirmed rather than assumed. All three surfaces read the
        same predicate through the same domain, so none of them can offer a
        destination the board would refuse, or refuse one it offers."""
        board = {c['id'] for c in self.Studio._ec_right_items()}
        for model in ('hr.employee', 'hr.contract'):
            fields = self.Studio.ec_model_fields(model)['fields']
            ids = {f['id'] for f in fields}
            self.assertEqual(ids, {i for i in board if i.startswith('f:%s:' % model)})
            for item in fields:
                meta = item['meta']
                self.assertTrue(meta.get('lane'))
                self.assertIsInstance(meta.get('lane_order'), int)
        hits = self.Studio.ec_search_fields('employee type')['fields']
        self.assertTrue(any(h['id'] == 'f:hr.employee:employee_type' for h in hits),
                        "the search cannot find the field the owner was looking for")
