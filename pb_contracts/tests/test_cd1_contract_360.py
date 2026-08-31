# -*- coding: utf-8 -*-
"""CD-1 — the contract drawer's server side, case by case.

Twenty-six numbered cases, and the numbers are the handover's. What they are
for, in one line each: the drawer opens on one payload (1), the terms arrive
grouped and ordered (2) and every entry is complete (3), the components are
sorted and typed (4) and only what is missing can be added (5), the wage is
masked in the payload itself and not on screen (6), a contract that is gone is
a sentence (7), a save writes the SAME contract (8), a key that was never
offered is refused rather than dropped (9), a required term cannot be emptied
(10), a bad number is a sentence (11), a half-good payload half-saves (12), a
component change is audited into the right pair of columns (13, 14), a text row
refuses an amount (15), a window is enforced before the model raises (16),
components can be added (17) and removed unless a mapping fills them (18), a
preview writes nothing (19) and agrees with the save (20), a reader can read
and not write (21), the picker is whitelisted (22), the history merges three
sources (23) and survives having none (24), a save hands back the fresh truth
(25), and no user-visible string says the wrong word (26).
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCd1Contract360(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Facade = cls.env['pb.contracts']
        cls.Contract = cls.env['hr.contract']
        cls.Employee = cls.env['hr.employee']
        cls.Advantage = cls.env['hr.contract.advantage']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.Change = cls.env.get('hr.contract.advantage.change')
        cls.Rule = cls.env.get('hr.formula.rule')
        cls.Config = cls.env.get('hr.formula.config')
        cls.company = cls.env.company
        cls.typed = 'value_type' in cls.Advantage._fields

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search(
                            [('company_id', 'in', (cls.company.id, False))],
                            limit=1))
        if not cls.calendar:
            cls.calendar = cls.env['resource.calendar'].create(
                {'name': 'CD Schedule', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1)
        if not cls.ctype:
            cls.ctype = cls.env['hr.contract.type'].create({'name': 'CD Staff'})
        cls.struct = cls.env['hr.payroll.structure'].search([], limit=1)
        cls.dept = cls.env['hr.department'].create(
            {'name': 'CD Drawer Dept', 'company_id': cls.company.id})

        # Templates go in BEFORE the contract: `hr.contract.create` auto-creates
        # one advantage line per template (om_hr_payroll/models/hr_contract.py
        # :118), so this is how the fixture ends up with its three lines.
        cls.t_base = cls._template('CDQBASE', 'CD Base Salary')
        cls.t_bound = cls._template('CDQBOUND', 'CD Site Bonus',
                                    lower=100.0, upper=1000.0, default=500.0)
        cls.t_text = cls._template('CDQTEXT', 'CD Grade Letter',
                                   value_type='text')
        cls.t_mapped = cls._template('CDQMAPPED', 'CD Mapped Allowance')

        cls.employee = cls.Employee.create(
            {'name': 'CD Drawer One', 'company_id': cls.company.id})
        cls.contract = cls._contract(cls.employee)

        cls.l_base = cls._line(cls.contract, 'CDQBASE')
        cls.l_bound = cls._line(cls.contract, 'CDQBOUND')
        cls.l_text = cls._line(cls.contract, 'CDQTEXT')
        cls.l_mapped = cls._line(cls.contract, 'CDQMAPPED')
        cls.l_base.write({'amount': 12500000.0})
        cls.l_bound.write({'amount': 500.0})
        if cls.typed:
            cls.l_text.write({'text_value': 'Grade A'})

        # created AFTER the contract, so it is the one thing `addable` can offer
        cls.t_extra = cls._template('CDQEXTRA', 'CD Other Allowance',
                                    default=750.0)

        # the scheme side: one rule that types a component, one that says a
        # mapping fills it
        cls.rule_base = cls.rule_mapped = None
        if cls.Rule is not None and cls.Config is not None:
            cls.cfg = cls.Config.create({
                'name': 'CD Drawer Scheme', 'code': 'CDDRAWER',
                'country_code': 'VN', 'state': 'active',
                'company_id': cls.company.id})
            cls.rule_base = cls._rule('CDQBASE', 'CD Base Salary',
                                      requires_new_contract=True)
            cls.rule_mapped = cls._rule('CDQMAPPED', 'CD Mapped Allowance',
                                        is_contract_component=True)

    # --------------------------------------------------------------- fixtures
    @classmethod
    def _template(cls, code, name, lower=0.0, upper=0.0, default=0.0,
                  value_type='amount'):
        vals = {'name': name, 'code': code, 'lower_bound': lower,
                'upper_bound': upper, 'default_value': default}
        if 'value_type' in cls.Template._fields:
            vals['value_type'] = value_type
        return cls.Template.create(vals)

    @classmethod
    def _rule(cls, code, name, **extra):
        return cls.Rule.create(dict({
            'config_id': cls.cfg.id, 'name': name, 'code': code,
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
        }, **extra))

    @classmethod
    def _contract(cls, employee, **vals):
        base = {
            'name': '%s - 2026-06-01' % employee.name,
            'employee_id': employee.id,
            'wage': 12500000.0,
            'state': 'open',
            'date_start': '2026-06-01',
            'resource_calendar_id': cls.calendar.id,
            'type_id': cls.ctype.id,
        }
        if cls.struct:
            base['struct_id'] = cls.struct.id
        base.update(vals)
        return cls.Contract.create(base)

    @classmethod
    def _line(cls, contract, code):
        return cls.Advantage.search([('contract_id', '=', contract.id),
                                     ('advantage_template_code', '=', code)],
                                    limit=1)

    # ---------------------------------------------------------------- helpers
    def _payload(self, contract_id=None, user=None):
        facade = self.Facade.with_user(user) if user else self.Facade
        return facade.get_contract_360(
            contract_id if contract_id is not None else self.contract.id)

    def _field(self, payload, name):
        for group in payload['terms']:
            for entry in group['fields']:
                if entry['name'] == name:
                    return entry
        return None

    def _row(self, payload, code):
        for row in payload['components']['rows']:
            if row['code'] == code:
                return row
        return None

    def _persona(self, login, xmlids):
        """A test user, or a skip that says which database cannot make one.

        W159: a golden TEMPLATE database is scrubbed of its administrator, so
        `res.users.create` raises there for a brand-new user that adds nobody
        and removes nobody. The ACL rails must keep being tested on every
        database that CAN test them, and a skip says out loud which cannot.
        """
        groups = []
        for xmlid in ['base.group_user'] + list(xmlids):
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups.append(group.id)
        try:
            with self.env.cr.savepoint():
                return self.env['res.users'].create({
                    'name': login, 'login': login,
                    'company_id': self.company.id,
                    'company_ids': [(6, 0, [self.company.id])],
                    'group_ids': [(6, 0, groups)],
                })
        except Exception as error:      # noqa: BLE001
            self.skipTest("this database cannot create a persona user: %s"
                          % error)

    def _walk_strings(self, node):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from self._walk_strings(key)
                yield from self._walk_strings(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                yield from self._walk_strings(item)
        elif isinstance(node, str):
            yield node

    # =====================================================================
    # 1 — one call, every key the drawer needs
    # =====================================================================
    def test_01_payload_carries_every_top_level_key(self):
        payload = self._payload()
        self.assertTrue(payload['ok'])
        self.assertFalse(payload['error'])
        self.assertEqual(
            set(payload),
            {'ok', 'error', 'currency', 'can_write', 'unmask_wage', 'header',
             'terms', 'readiness', 'components', 'history'})
        self.assertEqual(
            set(payload['header']),
            {'contract_id', 'reference', 'employee', 'employee_id', 'initials',
             'avatar', 'job', 'dept', 'state', 'state_label', 'wage',
             'wage_masked', 'ends_label', 'ends_tone', 'pipeline',
             'next_actions'})
        self.assertEqual(payload['header']['contract_id'], self.contract.id)
        # `explainer` joined the contract in CD-2: the calm sentence above a
        # grid of zeroes is composed server-side so there is one author of it.
        self.assertEqual(set(payload['components']),
                         {'rows', 'count', 'total', 'explainer', 'addable'})
        self.assertEqual(set(payload['history']), {'rows', 'total', 'shown'})

    # =====================================================================
    # 2 — the terms are grouped and ordered
    # =====================================================================
    def test_02_terms_are_grouped_in_the_declared_order(self):
        payload = self._payload()
        self.assertEqual([g['key'] for g in payload['terms']],
                         ['money', 'dates', 'place', 'rules'])
        money = payload['terms'][0]
        self.assertEqual(money['fields'][0]['name'], 'wage')
        for group in payload['terms']:
            self.assertTrue(group['label'])
            self.assertNotIn('_', group['label'])

    # =====================================================================
    # 3 — every field entry is complete and speaks screen words
    # =====================================================================
    def test_03_every_field_entry_is_complete(self):
        payload = self._payload()
        seen = 0
        for group in payload['terms']:
            for entry in group['fields']:
                seen += 1
                for key in ('name', 'label', 'kind', 'value', 'display',
                            'writable'):
                    self.assertIn(key, entry,
                                  "%s is missing %s" % (entry.get('name'), key))
                self.assertNotIn('_', entry['label'], entry['name'])
                self.assertNotEqual(entry['label'], entry['name'])
                if entry['kind'] in ('select', 'toggle'):
                    self.assertTrue(entry['options'])
                if entry['kind'] == 'm2o':
                    self.assertTrue(entry['comodel'])
                    self.assertIn('value_label', entry)
        self.assertGreaterEqual(seen, 15)

    # =====================================================================
    # 4 — components come back sorted, typed and bounded
    # =====================================================================
    def test_04_components_are_sorted_by_code_and_typed(self):
        payload = self._payload()
        codes = [r['code'] for r in payload['components']['rows']]
        self.assertEqual(codes, sorted(codes, key=lambda c: (c or '').upper()))

        base = self._row(payload, 'CDQBASE')
        bound = self._row(payload, 'CDQBOUND')
        text = self._row(payload, 'CDQTEXT')
        self.assertEqual(base['value_type'], 'amount')
        self.assertFalse(base['bounded'])
        self.assertFalse(base['bounds_hint'])
        self.assertTrue(bound['bounded'])
        self.assertTrue(isinstance(bound['bounds_hint'], str)
                        and bound['bounds_hint'].endswith('.'))
        if self.typed:
            self.assertEqual(text['value_type'], 'text')
            self.assertEqual(text['text_value'], 'Grade A')
            self.assertEqual(text['amount'], 0.0)
            self.assertFalse(text['bounds_hint'])
        if self.rule_base is not None:
            self.assertTrue(base['requires_new_contract'])
            self.assertEqual(base['value_kind'], 'money')

    # =====================================================================
    # 5 — `addable` is what is NOT already on the contract
    # =====================================================================
    def test_05_addable_excludes_what_the_contract_already_has(self):
        payload = self._payload()
        addable = {a['code'] for a in payload['components']['addable']}
        self.assertIn('CDQEXTRA', addable)
        for code in ('CDQBASE', 'CDQBOUND', 'CDQTEXT', 'CDQMAPPED'):
            self.assertNotIn(code, addable)

    # =====================================================================
    # 6 — the wage is scrubbed from the payload, not hidden on screen
    # =====================================================================
    def test_06_wage_is_masked_for_someone_who_may_not_see_it(self):
        user = self._persona('cd.contract.mgr',
                             ['hr.group_hr_user',
                              'hr_contract.group_hr_contract_manager'])
        payload = self._payload(user=user)
        self.assertTrue(payload['ok'])
        self.assertFalse(payload['unmask_wage'])
        self.assertIs(payload['header']['wage'], False)
        self.assertIs(payload['header']['wage_masked'], True)
        self.assertFalse(self._field(payload, 'wage')['writable'])
        self.assertIs(payload['components']['total'], False)

    # =====================================================================
    # 7 — a contract that is gone is a sentence, never a traceback
    # =====================================================================
    def test_07_a_missing_contract_is_a_plain_sentence(self):
        payload = self._payload(0)
        self.assertFalse(payload['ok'])
        self.assertTrue(payload['error'])
        self.assertNotIn('hr.contract', payload['error'])
        self.assertIn('contract', payload['error'].lower())

    # =====================================================================
    # 8 — a save writes IN PLACE (owner ruling: no new contract version)
    # =====================================================================
    def test_08_save_writes_the_same_contract(self):
        before = self.Contract.search_count(
            [('employee_id', '=', self.employee.id)])
        result = self.Facade.save_contract_360(
            self.contract.id, terms={'wage': 13000000.0})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 1)
        self.assertEqual(self.contract.wage, 13000000.0)
        self.assertEqual(
            self.Contract.search_count(
                [('employee_id', '=', self.employee.id)]), before)
        self.assertEqual(result['detail']['header']['contract_id'],
                         self.contract.id)

    # =====================================================================
    # 9 — a key the payload never offered is refused, not dropped
    # =====================================================================
    def test_09_an_unoffered_key_is_refused(self):
        result = self.Facade.save_contract_360(
            self.contract.id, terms={'active': False, 'location': 'CD Site'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 1)
        keys = {r['key'] for r in result['refusals']}
        self.assertEqual(keys, {'active'})
        self.assertTrue(self.contract.active)
        self.assertEqual(self.contract.location, 'CD Site')

    # =====================================================================
    # 10 — a required term cannot be emptied
    # =====================================================================
    def test_10_a_required_term_cannot_be_emptied(self):
        result = self.Facade.save_contract_360(
            self.contract.id, terms={'resource_calendar_id': False})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 0)
        self.assertEqual(len(result['refusals']), 1)
        why = result['refusals'][0]['why']
        self.assertIn('working schedule', why)
        self.assertNotIn('resource_calendar_id', why)
        self.assertTrue(self.contract.resource_calendar_id)

    # =====================================================================
    # 11 — a bad number is a sentence, not an exception
    # =====================================================================
    def test_11_a_bad_number_is_a_sentence(self):
        was = self.contract.wage
        result = self.Facade.save_contract_360(
            self.contract.id, terms={'wage': 'abc'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 0)
        self.assertEqual(len(result['refusals']), 1)
        self.assertIn('not a number', result['refusals'][0]['why'])
        self.assertEqual(self.contract.wage, was)

    # =====================================================================
    # 12 — partial success is the normal case
    # =====================================================================
    def test_12_a_half_good_payload_half_saves(self):
        result = self.Facade.save_contract_360(
            self.contract.id,
            terms={'costcenter': 'CD-CC-1', 'dependents': 'two'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 1)
        self.assertEqual(len(result['refusals']), 1)
        self.assertEqual(self.contract.costcenter, 'CD-CC-1')
        self.assertIn('1 change saved', result['msg'])
        self.assertIn('left alone', result['msg'])

    # =====================================================================
    # 13 — an amount change files one audit row, in the amount columns
    # =====================================================================
    def test_13_a_component_amount_change_is_audited(self):
        if self.Change is None:
            self.skipTest("the component-change trail is not installed here")
        before = self.Change.search_count(
            [('contract_id', '=', self.contract.id),
             ('advantage_template_id', '=', self.t_base.id)])
        result = self.Facade.save_contract_360(
            self.contract.id,
            components={'edits': {self.l_base.id: {'amount': 13500000.0}}})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 1)
        self.assertEqual(self.l_base.amount, 13500000.0)
        rows = self.Change.search(
            [('contract_id', '=', self.contract.id),
             ('advantage_template_id', '=', self.t_base.id)],
            order='id desc')
        self.assertEqual(len(rows) - before, 1)
        row = rows[0]
        self.assertEqual(row.change_source, 'manual')
        self.assertEqual(row.old_amount, 12500000.0)
        self.assertEqual(row.new_amount, 13500000.0)
        self.assertEqual(row.changed_by, self.env.user)

    # =====================================================================
    # 14 — a text change files into the TEXT columns
    # =====================================================================
    def test_14_a_text_component_change_is_audited_as_text(self):
        if self.Change is None or not self.typed:
            self.skipTest("text-typed components are not installed here")
        result = self.Facade.save_contract_360(
            self.contract.id,
            components={'edits': {self.l_text.id: {'text_value': 'Grade B'}}})
        self.assertTrue(result['ok'])
        self.assertEqual(self.l_text.text_value, 'Grade B')
        row = self.Change.search(
            [('contract_id', '=', self.contract.id),
             ('advantage_template_id', '=', self.t_text.id)],
            order='id desc', limit=1)
        self.assertTrue(row)
        self.assertEqual(row.old_text_value, 'Grade A')
        self.assertEqual(row.new_text_value, 'Grade B')
        self.assertEqual(row.old_amount, 0.0)
        self.assertEqual(row.new_amount, 0.0)

    # =====================================================================
    # 15 — an amount on a text row is refused, never coerced
    # =====================================================================
    def test_15_an_amount_on_a_text_row_is_refused(self):
        if not self.typed:
            self.skipTest("text-typed components are not installed here")
        result = self.Facade.save_contract_360(
            self.contract.id,
            components={'edits': {self.l_text.id: {'amount': 900.0}}})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 0)
        self.assertEqual(len(result['refusals']), 1)
        self.assertIn('holds text', result['refusals'][0]['why'])
        self.assertEqual(self.l_text.amount, 0.0)

    # =====================================================================
    # 16 — the window is enforced BEFORE the model raises
    # =====================================================================
    def test_16_an_out_of_window_amount_is_refused_with_the_window(self):
        was = self.l_bound.amount
        result = self.Facade.save_contract_360(
            self.contract.id,
            components={'edits': {self.l_bound.id: {'amount': 5000.0}}})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 0)
        why = result['refusals'][0]['why']
        self.assertIn('CD Site Bonus', why)
        self.assertIn('100', why)
        self.assertIn('1,000', why)
        self.assertEqual(self.l_bound.amount, was)

    # =====================================================================
    # 17 — adding a component, and refusing a second copy of one
    # =====================================================================
    def test_17_a_component_can_be_added_once(self):
        result = self.Facade.save_contract_360(
            self.contract.id,
            components={'adds': [{'template_id': self.t_extra.id}]})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 1)
        line = self._line(self.contract, 'CDQEXTRA')
        self.assertTrue(line)
        self.assertEqual(line.amount, 750.0)

        again = self.Facade.save_contract_360(
            self.contract.id,
            components={'adds': [{'template_id': self.t_extra.id}]})
        self.assertEqual(again['saved'], 0)
        self.assertIn('CD Other Allowance', again['refusals'][0]['why'])

    # =====================================================================
    # 18 — a component a mapping fills cannot be removed here
    # =====================================================================
    def test_18_removing_a_component_and_refusing_a_mapped_one(self):
        removable = self.l_bound.id
        result = self.Facade.save_contract_360(
            self.contract.id, components={'removes': [removable]})
        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 1)
        self.assertFalse(self.Advantage.browse(removable).exists())

        if self.rule_mapped is None:
            self.skipTest("the scheme rules are not installed here")
        blocked = self.Facade.save_contract_360(
            self.contract.id, components={'removes': [self.l_mapped.id]})
        self.assertEqual(blocked['saved'], 0)
        why = blocked['refusals'][0]['why']
        self.assertIn('CD Mapped Allowance', why)
        self.assertIn('mapping', why)
        self.assertTrue(self.l_mapped.exists())

    # =====================================================================
    # 19 — a preview writes nothing
    # =====================================================================
    def test_19_preview_writes_nothing(self):
        was_wage = self.contract.wage
        was_amount = self.l_base.amount
        preview = self.Facade.preview_contract_360(
            self.contract.id, terms={'wage': 'abc'})
        self.assertTrue(preview['ok'])
        self.assertEqual(preview['accept'], 0)
        self.assertEqual(len(preview['refusals']), 1)
        self.assertIn('not a number', preview['refusals'][0]['why'])
        self.assertEqual(self.contract.wage, was_wage)
        self.assertEqual(self.l_base.amount, was_amount)

    # =====================================================================
    # 20 — preview and save are the same judgement (the shared-helper pin)
    # =====================================================================
    def test_20_preview_and_save_refuse_the_same_things(self):
        payload = {'terms': {'wage': 'abc', 'active': False,
                             'resource_calendar_id': False,
                             'costcenter': 'CD-CC-2'},
                   'components': {'edits': {self.l_bound.id: {'amount': 9999.0}}}}
        preview = self.Facade.preview_contract_360(
            self.contract.id, terms=payload['terms'],
            components=payload['components'])
        saved = self.Facade.save_contract_360(
            self.contract.id, terms=payload['terms'],
            components=payload['components'])
        self.assertEqual({r['key'] for r in preview['refusals']},
                         {r['key'] for r in saved['refusals']})
        self.assertEqual(preview['accept'], saved['saved'])

    # =====================================================================
    # 21 — a reader reads, and is told they may not write
    # =====================================================================
    def test_21_a_reader_can_read_and_cannot_write(self):
        user = self._persona(
            'cd.contract.reader',
            ['hr.group_hr_user',
             'hr_contract.group_hr_contract_employee_manager'])
        # the employee-manager record rule shows a person their own team, so
        # the fixture employee is put under this persona
        boss = self.Employee.create({'name': 'CD Drawer Boss',
                                     'company_id': self.company.id,
                                     'user_id': user.id})
        self.employee.write({'parent_id': boss.id})

        payload = self._payload(user=user)
        self.assertTrue(payload['ok'])
        self.assertFalse(payload['can_write'])
        for group in payload['terms']:
            for entry in group['fields']:
                self.assertFalse(entry['writable'], entry['name'])

        was = self.contract.wage
        result = self.Facade.with_user(user).save_contract_360(
            self.contract.id, terms={'wage': 999.0})
        self.assertFalse(result['ok'])
        self.assertEqual(result['saved'], 0)
        self.assertIn('HR manager', result['msg'])
        self.assertEqual(self.contract.wage, was)

    # =====================================================================
    # 22 — the picker only answers for the comodels the terms name
    # =====================================================================
    def test_22_the_picker_is_whitelisted(self):
        rows = self.Facade.lookup_contract_m2o('hr.department', 'CD Drawer')
        self.assertTrue(rows)
        self.assertEqual(set(rows[0]), {'id', 'label'})
        self.assertEqual(self.Facade.lookup_contract_m2o('res.partner'), [])
        self.assertEqual(self.Facade.lookup_contract_m2o('ir.config_parameter'),
                         [])

    # =====================================================================
    # 23 — one merged, newest-first history over three sources
    # =====================================================================
    def test_23_history_merges_three_sources_newest_first(self):
        self.Facade.save_contract_360(
            self.contract.id, terms={'wage': 14000000.0},
            components={'edits': {self.l_base.id: {'amount': 14000000.0}}})
        Retro = self.env.get('hr.payroll.retro.adjustment')
        if Retro is not None and self.rule_base is not None:
            Retro.create({
                'formula_config_id': self.cfg.id,
                'employee_id': self.employee.id,
                'contract_id': self.contract.id,
                'component_id': self.rule_base.id,
                'period_from': '2026-05-01', 'period_to': '2026-05-31',
                'old_amount': 100.0, 'new_amount': 200.0,
                'delta_amount': 100.0})

        history = self._payload()['history']
        self.assertTrue(history['rows'])
        kinds = {row['kind'] for row in history['rows']}
        self.assertIn('component', kinds)
        for row in history['rows']:
            for key in ('kind', 'when', 'when_label', 'title', 'from', 'to',
                        'source', 'actor', 'tone'):
                self.assertIn(key, row)
        stamps = [row['when'] for row in history['rows']]
        self.assertEqual(stamps, sorted(stamps, reverse=True))
        manual = [r for r in history['rows'] if r['kind'] == 'component']
        self.assertEqual(manual[0]['source'], 'Typed in Payobook')
        self.assertLessEqual(history['shown'], 120)
        self.assertGreaterEqual(history['total'], history['shown'])
        if self.env.get('biz.audit.entry') is not None:
            self.assertIn('field', kinds)
            wage_rows = [r for r in history['rows']
                         if r['kind'] == 'field' and r['title'] == 'Monthly wage']
            self.assertTrue(wage_rows, "a wage change is a history row titled "
                                       "in the drawer's own words")
            # the trail stores str(value); money is formatted server-side
            self.assertNotIn('.0', wage_rows[0]['to'])
            self.assertIn(',', wage_rows[0]['to'])

    # =====================================================================
    # 24 — a contract with no history has no history, and does not blow up
    # =====================================================================
    def test_24_history_degrades_to_nothing(self):
        fresh_emp = self.Employee.create({'name': 'CD Drawer Two',
                                          'company_id': self.company.id})
        fresh = self._contract(fresh_emp)
        payload = self.Facade.get_contract_360(fresh.id)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['history']['rows'], [])
        self.assertEqual(payload['history']['total'], 0)
        self.assertEqual(payload['history']['shown'], 0)

    # =====================================================================
    # 25 — a save hands back the whole fresh truth
    # =====================================================================
    def test_25_save_returns_the_fresh_payload(self):
        result = self.Facade.save_contract_360(
            self.contract.id, terms={'wage': 15500000.0})
        detail = result['detail']
        self.assertTrue(detail['ok'])
        self.assertEqual(detail['header']['wage'], 15500000.0)
        self.assertEqual(self._field(detail, 'wage')['value'], 15500000.0)

    # =====================================================================
    # 26 — no user-visible string says the wrong word
    # =====================================================================
    def test_26_nothing_a_person_reads_says_the_wrong_word(self):
        payload = self._payload()
        for text in self._walk_strings(payload):
            self.assertNotIn('odoo', text.lower(), text)

        refusals = []
        refusals += self.Facade.save_contract_360(
            self.contract.id,
            terms={'wage': 'abc', 'resource_calendar_id': False,
                   'active': False},
            components={'edits': {self.l_bound.id: {'amount': 8888.0}},
                        'adds': [{'template_id': self.t_base.id}],
                        'removes': [self.l_mapped.id]})['refusals']
        refusals += self.Facade.preview_contract_360(
            self.contract.id, terms={'dependents': 'two'})['refusals']
        self.assertTrue(refusals)
        for refusal in refusals:
            self.assertNotIn('odoo', refusal['why'].lower(), refusal['why'])
            self.assertNotIn('_id', refusal['why'])
