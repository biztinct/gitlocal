# -*- coding: utf-8 -*-
"""MAPFIX Phase B — the catalogue, re-routing, and reconciliation.

Three promises, each of which fails silently if it breaks:

  * the field CATALOGUE is generated rather than typed. A regression here does
    not raise — it simply stops offering a destination, and the reader concludes
    Payobook cannot store a department (tests 1-4);
  * colour coding is a SUGGESTION. Wiring a contract component to a native field
    demotes it and keeps every contract value it has ever written as history
    (MF-B3). The half that has no test is the half that gets "cleaned up" by a
    later phase: tests 5-8 assert that the advantage template and its lines are
    still there afterwards, and that a column never has two destinations;
  * RECONCILIATION counts exactly what the problems rail counts. Two surfaces
    with two definitions of "unresolved" disagree within a phase and neither is
    then believed (tests 9-12).
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMappingCatalogue(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.formula.studio']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Mapping = cls.env['hr.payslip.import.mapping']
        cls.Template = cls.env['hr.contract.advantage.template']

    # ------------------------------------------------------------- fixtures
    def _config(self, name):
        # CR19 — country_code is required with no default; a bare create dies on
        # the NOT NULL constraint at INSERT time.
        return self.Config.create({
            'name': name, 'code': name.replace(' ', '_').upper()[:32],
            'country_code': 'VN', 'state': 'active',
        })

    def _rule(self, cfg, code, seq, **kw):
        vals = {'config_id': cfg.id, 'name': kw.pop('name', code.title()),
                'code': code, 'column_type': kw.pop('column_type', 'input'),
                'sequence': seq}
        vals.update(kw)
        return self.Rule.create(vals)

    def _spec(self, model, fname):
        return 'f:%s:%s' % (model, fname)

    def _ids(self, items):
        return {i['id'] for i in items}

    # ------------------------------------------------------------- test 1
    def test_01_catalogue_is_generated_complete_and_clean(self):
        items = self.Studio._ec_right_items()
        ids = self._ids(items)

        # the field whose absence started this: you could not map a name.
        self.assertIn(self._spec('hr.employee', 'name'), ids)
        # MF-B1 — the four mirror many2one fields the batch has always supported.
        # MF11: on Odoo 19 the hr.employee copies of three of them are NOT stored,
        # so the STORED destination is the contract's. The catalogue must offer
        # whichever of the two actually holds the value, and never neither.
        for fname in ('job_id', 'department_id', 'resource_calendar_id', 'company_id'):
            offered = [m for m in ('hr.employee', 'hr.contract')
                       if self._spec(m, fname) in ids]
            self.assertTrue(offered,
                            "%s is not offered as a destination on either model" % fname)
            for model in offered:
                self.assertTrue(self.env[model]._fields[fname].store)
        # at least one many2one really did widen the set
        self.assertIn(self._spec('hr.employee', 'parent_id'), ids)
        # …and the technical noise is not offered at all
        for fname in ('create_uid', 'write_date', '__last_update', 'display_name',
                      'active', 'message_follower_ids', 'message_ids'):
            self.assertNotIn(self._spec('hr.employee', fname), ids,
                             "%s leaked into the catalogue" % fname)

        # every returned field is stored, writable and of an allowed type
        for it in items:
            model, fname = it['meta']['model'], it['meta']['field']
            field = self.env[model]._fields[fname]
            self.assertTrue(field.store, "%s.%s is not stored" % (model, fname))
            self.assertFalse(field.readonly, "%s.%s is readonly" % (model, fname))
            self.assertIn(field.type, self.Studio._EC_TTYPES)
            # an unstored compute with no inverse has nowhere to put the value
            self.assertTrue(field.store or field.inverse,
                            "%s.%s cannot receive a write" % (model, fname))

        # the catalogue is a real widening, not a re-shuffle of the old 22
        self.assertGreater(len(items), 40, "the catalogue did not grow")

    # ------------------------------------------------------------- test 2
    def test_02_every_field_lands_in_exactly_one_lane(self):
        items = self.Studio._ec_right_items()
        lanes = {self.Studio._ec_lane_label(k) for k, _g in self.Studio._EC_LANES}
        seen = {}
        for it in items:
            self.assertIn(it['group'], lanes, "%s is in no known lane" % it['id'])
            self.assertNotIn(it['id'], seen, "%s appears twice" % it['id'])
            seen[it['id']] = it['group']

        # a field nobody named still appears — under "Other …", never nowhere
        other_emp = self.Studio._ec_lane_label('other_employee')
        self.assertTrue(any(g == other_emp for g in seen.values()),
                        "nothing fell through to the honest remainder")
        # curated names land where they were put
        self.assertEqual(seen[self._spec('hr.employee', 'name')],
                         self.Studio._ec_lane_label('identity'))
        self.assertEqual(seen[self._spec('hr.contract', 'department_id')],
                         self.Studio._ec_lane_label('job'))
        self.assertEqual(seen[self._spec('hr.contract', 'wage')],
                         self.Studio._ec_lane_label('contract_terms'))

        # and the right COLUMN reads in lane order, with the bank cards in place
        col = self.Studio._ec_right_column()
        order = [i['meta'].get('lane_order', 99) for i in col]
        self.assertEqual(order, sorted(order), "the right column is out of lane order")
        self.assertIn('b:acc_number', self._ids(col))

    # ------------------------------------------------------------- test 3
    def test_03_search_reaches_beyond_the_curated_lanes(self):
        curated = set()
        for _key, groups in self.Studio._EC_LANES:
            for model, names in groups:
                for n in names:
                    curated.add(self._spec(model, n))

        res = self.Studio.ec_search_fields('wage')
        self.assertTrue(res.get('ok'))
        self.assertTrue(res['fields'], "search found nothing for a field it holds")

        # Search is at least as broad as the catalogue: it must reach a field no
        # lane names by hand. Probed by technical NAME rather than by label — the
        # label is translated, and a test that only passes in English is not a test.
        uncurated = [f for f in self.Studio._ec_right_items()
                     if f['id'] not in curated]
        self.assertTrue(uncurated, "nothing outside the curated lanes")
        probe = max(uncurated, key=lambda f: len(f['meta']['field']))
        found = self.Studio.ec_search_fields(probe['meta']['field'])
        self.assertIn(probe['id'], {f['id'] for f in found['fields']},
                      "search cannot reach an uncurated field")

        # a denied field stays denied no matter how hard you look for it
        self.assertFalse([f for f in self.Studio._ec_right_items('create_uid')
                          if f['id'].endswith(':create_uid')])

    # ------------------------------------------------------------- test 4
    def test_04_many2one_resolves_and_creates(self):
        cfg = self._config('MAPFIX m2o')
        rule = self._rule(cfg, 'DEPT', 10, name='Department', column_role='contract')
        # MF11 — the STORED department is the contract's on Odoo 19.
        res = self.Studio.employee_mapping_create(
            cfg.id, False, rule.id, self._spec('hr.contract', 'department_id'))
        self.assertTrue(res.get('ok'), res)

        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'MAPFIX m2o batch', 'formula_config_id': cfg.id})
        employee = self.env['hr.employee'].create({'name': 'MAPFIX m2o subject'})
        contract = self.env['hr.contract'].create({
            'name': 'MAPFIX m2o contract', 'employee_id': employee.id,
            'wage': 1000.0, 'state': 'draft'})

        # (a) an existing department is FOUND, not duplicated
        existing = self.env['hr.department'].create({'name': 'MAPFIX Existing Dept'})
        updates = batch._get_mapping_updates(
            contract, {'Department': 'mapfix existing dept'})
        self.assertEqual(updates.get('department_id'), existing.id,
                         "an existing department was not matched by name")

        # (b) a department nobody has yet is CREATED
        before = self.env['hr.department'].search_count(
            [('name', '=', 'MAPFIX Brand New Dept')])
        self.assertEqual(before, 0)
        updates = batch._get_mapping_updates(
            contract, {'Department': 'MAPFIX Brand New Dept'})
        made = self.env['hr.department'].browse(updates['department_id'])
        self.assertEqual(made.name, 'MAPFIX Brand New Dept')

        # (c) a comodel with no name field is refused rather than guessed at
        bank_field = self.env['hr.employee']._fields.get('bank_account_id')
        if bank_field is not None and bank_field.type == 'many2one':
            self.assertIsNone(batch._coerce_mapped_value(
                employee, bank_field, 'not-an-account'))

    # ------------------------------------------------------------- test 5
    def test_05_wiring_a_component_demotes_it_and_keeps_the_history(self):
        cfg = self._config('MAPFIX demote')
        rule = self._rule(cfg, 'GRADEX', 10, name='Grade',
                          is_contract_component=True, is_text_component=True,
                          column_role='contract')
        template = self.Template.create({
            'name': 'Grade', 'code': 'GRADEX', 'lower_bound': 0.0,
            'upper_bound': 0.0, 'default_value': 0.0})
        employee = self.env['hr.employee'].create({'name': 'MAPFIX demote subject'})
        contract = self.env['hr.contract'].create({
            'name': 'MAPFIX demote contract', 'employee_id': employee.id,
            'wage': 1000.0, 'state': 'draft'})
        # CR18 — hr.contract.create seeds an EMPTY line per template, so the value
        # has to be written for this to be history rather than plumbing.
        line = self.env['hr.contract.advantage'].search([
            ('contract_id', '=', contract.id),
            ('advantage_template_id', '=', template.id)], limit=1)
        if not line:
            line = self.env['hr.contract.advantage'].create({
                'contract_id': contract.id, 'advantage_template_id': template.id})
        line.write({'amount': 7.0})

        res = self.Studio.employee_mapping_create(
            cfg.id, False, rule.id, self._spec('hr.employee', 'job_title'))
        self.assertTrue(res.get('ok'), res)
        self.assertIn('history', (res.get('msg') or '').lower(),
                      "the demotion did not say what happens to the old values")

        rule.invalidate_recordset()
        self.assertFalse(rule.is_contract_component)
        self.assertFalse(rule.is_text_component)
        self.assertEqual(rule.column_role, 'profile')
        self.assertEqual(rule.column_role_source, 'user')
        self.assertTrue(self.Mapping.search_count([
            ('salary_structure_id', '=', cfg.id), ('component_id', '=', rule.id),
            ('destination_type', '=', 'field')]))

        # MF-B3 — nothing was destroyed
        self.assertTrue(template.exists(), "the advantage template was deleted")
        line.invalidate_recordset()
        self.assertTrue(line.exists(), "the contract's advantage line was deleted")
        self.assertEqual(line.amount, 7.0, "the contract's value was rewritten")

    # ------------------------------------------------------------- test 6
    def test_06_after_demotion_the_import_writes_the_field_instead(self):
        cfg = self._config('MAPFIX after demote')
        rule = self._rule(cfg, 'TITLEX', 10, name='Job title',
                          is_contract_component=True, is_text_component=True,
                          column_role='contract')
        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'MAPFIX demote batch', 'formula_config_id': cfg.id})
        self.assertIn(rule, batch._get_contract_component_rules())

        self.Studio.employee_mapping_create(
            cfg.id, False, rule.id, self._spec('hr.employee', 'job_title'))
        cfg.invalidate_recordset()
        batch.invalidate_recordset()

        employee = self.env['hr.employee'].create({'name': 'MAPFIX after demote'})
        updates = batch._get_mapping_updates(employee, {'Job title': 'Team lead'})
        self.assertEqual(updates.get('job_title'), 'Team lead')
        self.assertNotIn(rule, batch._get_contract_component_rules(),
                         "the demoted column is still synced to the contract")

    # ------------------------------------------------------------- test 7
    def test_07_promotion_both_ways_removes_the_native_wire(self):
        cfg = self._config('MAPFIX promote')
        rule = self._rule(cfg, 'SHIFTX', 10, name='Shift', column_role='profile')
        self.Studio.employee_mapping_create(
            cfg.id, False, rule.id, self._spec('hr.employee', 'job_title'))
        self.assertTrue(self.Mapping.search_count([('component_id', '=', rule.id)]))

        res = self.Studio.employee_mapping_make_component(rule.id, 'text')
        self.assertTrue(res.get('ok'), res)
        rule.invalidate_recordset()
        self.assertTrue(rule.is_contract_component)
        self.assertTrue(rule.is_text_component)
        self.assertEqual(rule.column_role, 'contract')       # CR-A2
        self.assertEqual(rule.column_role_source, 'user')
        self.assertFalse(self.Mapping.search_count([('component_id', '=', rule.id)]),
                         "a column ended up with two destinations")

        res = self.Studio.employee_mapping_make_component(rule.id, 'amount')
        self.assertTrue(res.get('ok'), res)
        rule.invalidate_recordset()
        self.assertTrue(rule.is_contract_component)
        self.assertFalse(rule.is_text_component)
        self.assertEqual(rule.column_role, 'payroll')        # CR-A2

        # a nonsense value type writes nothing
        self.assertFalse(self.Studio.employee_mapping_make_component(
            rule.id, 'colour').get('ok'))
        # the Phase-3 name still works
        self.assertTrue(self.Studio.employee_mapping_make_text_component(
            rule.id).get('ok'))

    # ------------------------------------------------------------- test 8
    def test_08_round_trip_never_leaves_two_destinations(self):
        cfg = self._config('MAPFIX roundtrip')
        rule = self._rule(cfg, 'ROUNDX', 10, name='Round trip', column_role='profile')

        def destinations():
            rule.invalidate_recordset()
            wires = self.Mapping.search_count([
                ('salary_structure_id', '=', cfg.id), ('component_id', '=', rule.id)])
            return wires + (1 if rule.is_contract_component else 0)

        self.assertEqual(destinations(), 0)
        self.Studio.employee_mapping_make_component(rule.id, 'amount')
        self.assertEqual(destinations(), 1)
        self.Studio.employee_mapping_create(
            cfg.id, False, rule.id, self._spec('hr.employee', 'job_title'))
        self.assertEqual(destinations(), 1)
        self.Studio.employee_mapping_make_component(rule.id, 'text')
        self.assertEqual(destinations(), 1)
        self.Studio.employee_mapping_delete(
            self.Mapping.search([('component_id', '=', rule.id)]).id or 0)
        self.assertEqual(destinations(), 1)

    # ------------------------------------------------------------- test 9
    def test_09_the_unresolved_set(self):
        cfg = self._config('MAPFIX unresolved')
        stranded = self._rule(cfg, 'STRANDX', 10, name='Stranded',
                              column_role='profile')
        feeds = self._rule(cfg, 'FEEDSX', 20, name='Feeds a formula',
                           column_role='payroll', appears_on_payslip=False)
        self._rule(cfg, 'CALCX', 30, column_type='formula',
                   excel_formula='=%s2*2' % feeds.column_letter)
        self._rule(cfg, 'CONSTX', 40, column_type='constant', default_value=5.0)
        component = self._rule(cfg, 'COMPX', 50, is_contract_component=True,
                               column_role='payroll', appears_on_payslip=False)
        reference = self._rule(cfg, 'REFX', 60, column_role='reference')
        mapped = self._rule(cfg, 'MAPPEDX', 70, name='Mapped', column_role='identity')
        self.Studio.employee_mapping_create(
            cfg.id, False, mapped.id, self._spec('hr.employee', 'employee_id'))
        onslip = self._rule(cfg, 'ONSLIPX', 80, column_role='payroll',
                            appears_on_payslip=True)

        unresolved = self.Studio._ec_unresolved(cfg)
        self.assertIn(stranded, unresolved)
        for rule in (feeds, component, reference, mapped, onslip):
            self.assertNotIn(rule, unresolved,
                             "%s was called unresolved" % rule.code)
        self.assertEqual(len(unresolved), 1)
        # a calculated or constant column is produced, not received
        self.assertFalse(unresolved.filtered(
            lambda r: r.column_type in ('formula', 'constant')))

    # ------------------------------------------------------------- test 10
    def test_10_resolve_remaining_applies_both_answers(self):
        cfg = self._config('MAPFIX resolve')
        keep = self._rule(cfg, 'KEEPX', 10, name='Keep me', column_role='contract')
        drop = self._rule(cfg, 'DROPX', 20, name='Drop me', column_role='profile')

        rows = self.Studio.employee_mapping_unresolved(cfg.id)['rows']
        self.assertEqual({r['id'] for r in rows}, {keep.id, drop.id})
        for row in rows:
            self.assertIn(row['value_type'], ('amount', 'text'))

        # a payload naming a column that is not unresolved writes NOTHING
        bad = self.Studio.employee_mapping_resolve_remaining(
            cfg.id, [{'id': keep.id, 'component': True},
                     {'id': -1, 'component': True}])
        self.assertFalse(bad.get('ok'))
        keep.invalidate_recordset()
        self.assertFalse(keep.is_contract_component, "a bad payload half-applied")

        res = self.Studio.employee_mapping_resolve_remaining(
            cfg.id, [{'id': keep.id, 'component': True, 'value_type': 'text'},
                     {'id': drop.id, 'component': False}])
        self.assertTrue(res.get('ok'), res)
        keep.invalidate_recordset()
        drop.invalidate_recordset()
        self.assertTrue(keep.is_contract_component)
        self.assertTrue(keep.is_text_component)
        self.assertEqual(drop.column_role, 'reference')
        self.assertEqual(drop.column_role_source, 'user')
        self.assertEqual(res.get('unresolved'), 0,
                         "the board still reports work that is done")

    # ------------------------------------------------------------- test 11
    def test_11_reconciliation_is_idempotent(self):
        cfg = self._config('MAPFIX idempotent')
        a = self._rule(cfg, 'IDEMAX', 10, name='One', column_role='profile')
        b = self._rule(cfg, 'IDEMBX', 20, name='Two', column_role='contract')
        self.Studio.employee_mapping_resolve_remaining(
            cfg.id, [{'id': a.id, 'component': True, 'value_type': 'amount'},
                     {'id': b.id, 'component': False}])
        self.assertFalse(self.Studio.employee_mapping_unresolved(cfg.id)['rows'],
                         "running it again found work that was already done")
        again = self.Studio.employee_mapping_resolve_remaining(cfg.id, [])
        self.assertTrue(again.get('ok'))
        self.assertEqual(again.get('unresolved'), 0)

    # ------------------------------------------------------------- test 12
    def test_12_the_rail_and_the_board_agree(self):
        cfg = self._config('MAPFIX agree')
        self._rule(cfg, 'AGRIDX', 10, name='Employee code', column_role='identity',
                   appears_on_payslip=False)
        self._rule(cfg, 'AGRBNKX', 20, name='Account', column_role='bank',
                   appears_on_payslip=False)
        self._rule(cfg, 'AGRPROX', 30, name='Birthday', column_role='profile',
                   appears_on_payslip=False)

        n = len(self.Studio._ec_unresolved(cfg))
        self.assertEqual(n, 3)
        kinds = [p['kind'] for p in self.Studio.get_problems(cfg.id)['problems']]
        self.assertEqual(kinds.count('idunmapped') + kinds.count('bankunmapped'), n,
                         "the problems rail and the mapping board disagree")

        board = self.Studio.employee_mapping_data(cfg.id)
        self.assertEqual(board.get('unresolved'), n)
