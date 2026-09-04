# -*- coding: utf-8 -*-
"""MAPFIX Phase F3 — the create RPC applies the catalogue's own predicate.

The board has always refused to OFFER a destination that fails
`_ec_is_mappable`. It never re-checked at the point of writing, so the rule
existed on exactly one side of the browser boundary: a stale board, the search
box, or a direct RPC could still mint a wire whose import reads a column and
puts the value nowhere (MF36 (a)).

Three things have to be true at once, and the second and third are why this is
a guard rather than a filter:

  * a refused destination is refused, with a sentence naming the field, and NO
    row is written (test 1/2);
  * every `b:` bank spec still goes through untouched — the bank lane is not
    made of fields and never went through this predicate (test 3);
  * a row written BEFORE the guard existed still loads, still draws its wire and
    still carries the Phase-E `warn` note. The guard governs CREATE, never READ;
    refusing to load such a row would hide a live mapping, which is the worse
    failure and the exact opposite of the point (test 4).
"""
from odoo.tests import TransactionCase, tagged


def fld_label(env, model, name):
    """The label a refusal is expected to print — read from the registry rather
    than typed, so the assertion survives a translation or a relabelling."""
    fld = env['ir.model.fields'].sudo().search(
        [('model', '=', model), ('name', '=', name)], limit=1)
    return fld.field_description or name


@tagged('post_install', '-at_install')
class TestMappingCreateGuard(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Mapping = cls.env['hr.payslip.import.mapping'].sudo()

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

    def _rows(self, cfg):
        return self.Mapping.search([('salary_structure_id', '=', cfg.id)])

    # --------------------------------------------------------------- test 7
    def test_01_a_refused_destination_is_refused_and_nothing_is_written(self):
        """`hr.employee.active` is stored and writable — the mapping model's own
        domain accepts it — and it is on the catalogue's deny-list as record
        plumbing. That gap is precisely what a stale board or a direct RPC could
        walk through."""
        self.assertFalse(self.Studio._ec_is_mappable('hr.employee', 'active'),
                         "the fixture's premise is gone — pick another field")
        cfg = self._config('MAPFIX F3 refuse')
        rule = self._rule(cfg, 'ARCHIVED', name='Archived', column_role='profile')

        res = self.Studio.employee_mapping_create(
            cfg.id, False, rule.id, 'f:hr.employee:active')

        self.assertFalse(res.get('ok'), "the guard let the write through")
        msg = res.get('msg') or ''
        self.assertTrue(msg, "a refusal with no sentence is a dead end")
        # names the field, says why, and offers the way out
        self.assertIn(fld_label(self.env, 'hr.employee', 'active'), msg)
        self.assertIn('is not a field an import can write', msg)
        self.assertIn('Pick a different destination', msg)
        self.assertNotIn('Odoo', msg)                     # white-label, absolute
        self.assertFalse(self._rows(cfg), "a row was written by a refused create")

    def test_02_the_refusal_reads_the_same_sentence_the_card_carries(self):
        """One vocabulary. The card's `warn` tooltip and the create refusal are
        the same fact, so they are the same sentence built in one place — two
        wordings for one rule is how a product tells a user two stories."""
        fld = self.env['ir.model.fields'].sudo().search(
            [('model', '=', 'hr.employee'), ('name', '=', 'active')], limit=1)
        self.assertTrue(fld)
        label = fld.field_description or fld.name
        shared = self.Studio._ec_unwritable_msg(label)
        cfg = self._config('MAPFIX F3 wording')
        rule = self._rule(cfg, 'ARCHIVED2', name='Archived', column_role='profile')
        res = self.Studio.employee_mapping_create(
            cfg.id, False, rule.id, 'f:hr.employee:active')
        self.assertEqual(res.get('msg'), shared)
        note = self.Studio._ec_unmappable_note(fld)
        self.assertEqual(note['tone'], 'warn')
        # the same three claims, in both places
        for claim in ('is not a field an import can write',
                      'read and then dropped'):
            self.assertIn(claim, shared)
            self.assertIn(claim, note['title'])

    # --------------------------------------------------------------- test 8
    def test_03_every_bank_spec_still_goes_through(self):
        """F3 caution 2. The four bank cards are not fields of anything — they
        are the parts of a `res.partner.bank` the import assembles — and they
        have never gone through `_ec_is_mappable`. They must not start to."""
        cfg = self._config('MAPFIX F3 bank')
        for n, role in enumerate(self.Studio._BANK_LANE_ROLES):
            rule = self._rule(cfg, 'BNK%d' % n, seq=10 + n, column_role='bank')
            res = self.Studio.employee_mapping_create(
                cfg.id, False, rule.id, 'b:%s' % role)
            self.assertTrue(res.get('ok'), '%s was refused: %s' % (role, res))
        rows = self._rows(cfg)
        self.assertEqual(len(rows), len(self.Studio._BANK_LANE_ROLES))
        self.assertEqual(set(rows.mapped('bank_role')),
                         set(self.Studio._BANK_LANE_ROLES))
        self.assertEqual(set(rows.mapped('destination_type')), {'bank_account'})
        # …and a bank role that is not one of the four is still refused, by the
        # spec guard rather than by the new one.
        rule = self._rule(cfg, 'BNKX', seq=99, column_role='bank')
        bad = self.Studio.employee_mapping_create(cfg.id, False, rule.id, 'b:iban')
        self.assertFalse(bad.get('ok'))

    def test_04_an_ordinary_destination_is_untouched(self):
        """The guard must be invisible on every wire anybody actually draws."""
        cfg = self._config('MAPFIX F3 ordinary')
        for n, spec in enumerate(('f:hr.employee:employee_id',
                                  'f:hr.contract:department_id')):
            if not self.Studio._ec_is_mappable(*spec[2:].split(':')):
                continue
            rule = self._rule(cfg, 'OK%d' % n, seq=10 + n, column_role='profile')
            res = self.Studio.employee_mapping_create(cfg.id, False, rule.id, spec)
            self.assertTrue(res.get('ok'), '%s: %s' % (spec, res))
        self.assertTrue(self._rows(cfg), "no ordinary wire could be drawn at all")

    # --------------------------------------------------------------- test 9
    def test_05_a_pre_existing_row_still_loads_and_still_warns(self):
        """F3 caution 1 — CREATE only, never READ.

        The owner has already deleted the one live instance (payobook mapping 16
        → `hr.contract.active`), so this asserts the behaviour rather than going
        looking for a subject: a row written straight into the model, the way one
        written before the guard existed would look.
        """
        cfg = self._config('MAPFIX F3 legacy')
        rule = self._rule(cfg, 'LEGACY', name='Legacy', column_role='profile')
        fld = self.env['ir.model.fields'].sudo().search(
            [('model', '=', 'hr.employee'), ('name', '=', 'active')], limit=1)
        row = self.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field', 'target_model_id': fld.model_id.id,
            'target_field_id': fld.id,
        })

        data = self.Studio.employee_mapping_data(cfg.id, include_payroll=True)
        self.assertTrue(data.get('ok'), data)
        # the row is still there — nothing about READ deletes or hides it
        self.assertTrue(row.exists())
        wires = [w for w in data['wires'] if w['rightId'] == 'f:hr.employee:active']
        self.assertEqual(len(wires), 1, "the guard swallowed a live mapping")
        card = next((c for c in data['right']
                     if c['id'] == 'f:hr.employee:active'), None)
        self.assertTrue(card, "the destination of a live mapping left the board")
        note = (card.get('meta') or {}).get('note')
        self.assertTrue(note)
        self.assertEqual(note.get('tone'), 'warn')
        self.assertFalse(card['meta'].get('mappable', True))
        self.assertNotIn('Odoo', '%s %s' % (note['text'], note['title']))
