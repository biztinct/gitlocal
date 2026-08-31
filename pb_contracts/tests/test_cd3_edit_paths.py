# -*- coding: utf-8 -*-
"""CD-3 — the edit boundary the drawer now writes across, case by case.

Eight numbered cases, and the numbers are the handover's. CD-1 proved the
server; these re-assert the promises the SCREEN now depends on, at the exact
boundary the editing gesture crosses: a saved term writes IN PLACE and starts
no second contract (1), what the typing preview showed is what the save does
(2), a component amount leaves exactly one audit row that says a person typed
it (3), a component a mapping keeps filling cannot be removed and says why
(4), the picker answers for the comodels the payload names and no others (5),
a lifecycle step runs only from the short list and back-fills the end date
(6), a reader is told they may not write instead of finding out afterwards
(7), and nothing a person can read anywhere in any of that says the wrong word
(8).
"""

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCd3EditPaths(TransactionCase):

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
                {'name': 'CD3 Schedule', 'company_id': cls.company.id})
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1)
        if not cls.ctype:
            cls.ctype = cls.env['hr.contract.type'].create({'name': 'CD3 Staff'})
        cls.struct = cls.env['hr.payroll.structure'].search([], limit=1)
        cls.dept = cls.env['hr.department'].create(
            {'name': 'CD3 Drawer Dept', 'company_id': cls.company.id})

        # Templates go in BEFORE the contract: `hr.contract.create` seeds one
        # advantage line per template (om_hr_payroll/models/hr_contract.py:118),
        # and that is how the fixture ends up with its rows.
        cls.t_base = cls._template('CD3BASE', 'CD3 Base Salary')
        cls.t_mapped = cls._template('CD3MAPPED', 'CD3 Mapped Allowance')

        cls.employee = cls.Employee.create(
            {'name': 'CD3 Drawer One', 'company_id': cls.company.id})
        cls.contract = cls._contract(cls.employee)
        cls.l_base = cls._line(cls.contract, 'CD3BASE')
        cls.l_mapped = cls._line(cls.contract, 'CD3MAPPED')
        cls.l_base.write({'amount': 12500000.0})

        # A second employee and contract, so the lifecycle case can end one
        # without taking the fixture every other case reads with it.
        cls.employee_b = cls.Employee.create(
            {'name': 'CD3 Drawer Two', 'company_id': cls.company.id})
        cls.contract_b = cls._contract(cls.employee_b, date_end=False)

        # The scheme side: one rule marked a contract component, which is what
        # makes CD3MAPPED un-removable.
        cls.rule_mapped = None
        if cls.Rule is not None and cls.Config is not None:
            cls.cfg = cls.Config.create({
                'name': 'CD3 Drawer Scheme', 'code': 'CD3DRAWER',
                'country_code': 'VN', 'state': 'active',
                'company_id': cls.company.id})
            cls.rule_mapped = cls.Rule.create({
                'config_id': cls.cfg.id, 'name': 'CD3 Mapped Allowance',
                'code': 'CD3MAPPED', 'column_type': 'input', 'sequence': 1,
                'default_value': 0.0, 'is_contract_component': True})

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
        `res.users.create` raises there. The ACL rails keep being tested on
        every database that CAN test them, and a skip says out loud which
        cannot (ledger CD4 — a phase with an ACL case reports BOTH runs).
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

    def _strings(self, node, out=None):
        out = [] if out is None else out
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str):
                    out.append(key)
                self._strings(value, out)
        elif isinstance(node, (list, tuple)):
            for value in node:
                self._strings(value, out)
        elif isinstance(node, str):
            out.append(node)
        return out

    # =====================================================================
    # 1 — a saved term writes IN PLACE; no second contract appears
    # =====================================================================
    def test_01_a_saved_term_writes_the_same_contract(self):
        before = self.Contract.search_count(
            [('employee_id', '=', self.employee.id)])
        result = self.Facade.save_contract_360(
            self.contract.id, terms={'wage': 13750000.0})

        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 1)
        self.assertFalse(result['refusals'])
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.wage, 13750000.0)
        self.assertEqual(
            self.Contract.search_count([('employee_id', '=', self.employee.id)]),
            before,
            "the owner's ruling is that a term is written onto the contract "
            "being looked at — a new contract or a version is a bug")
        # and the mutate hands back the whole fresh truth, not a flag
        self.assertTrue(result['detail']['ok'])
        self.assertEqual(self._field(result['detail'], 'wage')['value'],
                         13750000.0)

    # =====================================================================
    # 2 — what the typing preview shows is what the save does
    # =====================================================================
    def test_02_preview_and_save_agree_on_a_mixed_payload(self):
        terms = {
            # four the server will take
            'wage': 14100000.0,
            'date_end': '2027-03-31',
            'dependents': 2,
            'location': 'Ha Noi',
            # two it will not: a required term emptied, and a choice that is
            # not one of the choices
            'resource_calendar_id': False,
            'hirestatus': 'NOT A REAL STATUS',
        }
        preview = self.Facade.preview_contract_360(self.contract.id, terms=terms)
        saved = self.Facade.save_contract_360(self.contract.id, terms=terms)

        self.assertEqual({r['key'] for r in preview['refusals']},
                         {r['key'] for r in saved['refusals']})
        self.assertEqual({'resource_calendar_id', 'hirestatus'},
                         {r['key'] for r in saved['refusals']})
        self.assertEqual(preview['accept'], 4)
        self.assertEqual(saved['saved'], 4)
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.wage, 14100000.0)
        self.assertEqual(self.contract.resource_calendar_id, self.calendar,
                         "a refused term leaves the record exactly as it was")

    # =====================================================================
    # 3 — one component edit, one audit row, and it says a person typed it
    # =====================================================================
    def test_03_a_component_edit_files_one_manual_audit_row(self):
        if self.Change is None:
            self.skipTest("this build has no component change log")
        before = self.Change.search_count([
            ('contract_id', '=', self.contract.id),
            ('advantage_template_id', '=', self.t_base.id)])

        result = self.Facade.save_contract_360(
            self.contract.id,
            components={'edits': {self.l_base.id: {'amount': 13000000.0}}})

        self.assertTrue(result['ok'])
        self.assertEqual(result['saved'], 1)
        self.assertFalse(result['refusals'])
        rows = self.Change.search([
            ('contract_id', '=', self.contract.id),
            ('advantage_template_id', '=', self.t_base.id)],
            order='id desc')
        self.assertEqual(len(rows) - before, 1,
                         "one edit is one audit row, never two and never none")
        self.assertEqual(rows[0].change_source, 'manual')
        self.assertEqual(rows[0].old_amount, 12500000.0)
        self.assertEqual(rows[0].new_amount, 13000000.0)
        self.l_base.invalidate_recordset()
        self.assertEqual(self.l_base.amount, 13000000.0)

    # =====================================================================
    # 4 — a component a mapping keeps filling cannot be removed, and says why
    # =====================================================================
    def test_04_a_mapping_fed_component_refuses_to_be_removed(self):
        if self.rule_mapped is None:
            self.skipTest("this build has no formula rules to map from")
        line_id = self.l_mapped.id
        result = self.Facade.save_contract_360(
            self.contract.id, components={'removes': [line_id]})

        self.assertEqual(result['saved'], 0)
        self.assertEqual(len(result['refusals']), 1)
        why = result['refusals'][0]['why']
        self.assertIn('mapping', why.lower())
        self.assertTrue(why.endswith('.'), "a refusal is a sentence: %s" % why)
        self.assertTrue(self.Advantage.browse(line_id).exists(),
                        "a refused removal leaves the row on the contract")

    # =====================================================================
    # 5 — the picker answers for the payload's own comodels and no others
    # =====================================================================
    def test_05_the_picker_is_whitelisted_and_answers(self):
        whitelist = ['hr.payroll.structure', 'hr.contract.type',
                     'resource.calendar', 'hr.department', 'hr.job',
                     'res.users', 'wfp.pay.grade', 'account.journal']
        answered = []
        for comodel in whitelist:
            Model = self.env.get(comodel)
            rows = self.Facade.lookup_contract_m2o(comodel)
            self.assertIsInstance(rows, list, comodel)
            if Model is None:
                # the module that carries it is not installed on this build
                self.assertEqual(rows, [], comodel)
                continue
            for row in rows:
                self.assertEqual(set(row), {'id', 'label'}, comodel)
            if Model.sudo().search_count([]):
                self.assertTrue(rows, "%s has records but answered nothing"
                                % comodel)
                answered.append(comodel)
        self.assertTrue(answered, "no whitelisted comodel could be exercised")

        # anything the terms payload never names is an exfiltration hole
        self.assertEqual(self.Facade.lookup_contract_m2o('res.partner'), [])
        self.assertEqual(
            self.Facade.lookup_contract_m2o('res.partner', 'a'), [])

    # =====================================================================
    # 6 — a lifecycle step runs only from the short list
    # =====================================================================
    def test_06_terminate_ends_the_contract_and_nothing_else_runs(self):
        self.assertEqual(self.contract_b.state, 'open')
        self.assertFalse(self.contract_b.date_end)

        self.Facade.run_contract_action(self.contract_b.id, 'terminate')
        self.contract_b.invalidate_recordset()
        self.assertEqual(self.contract_b.state, 'close')
        self.assertEqual(self.contract_b.date_end, date.today(),
                         "ending a contract back-fills the day it ended")

        # a method name that is not one of the three changes nothing at all
        state_was, end_was = self.contract_b.state, self.contract_b.date_end
        outcome = self.Facade.run_contract_action(self.contract_b.id, 'unlink')
        self.assertTrue(outcome.get('error'))
        self.contract_b.invalidate_recordset()
        self.assertEqual(self.contract_b.state, state_was)
        self.assertEqual(self.contract_b.date_end, end_was)
        self.assertTrue(self.contract_b.exists(),
                        "no lifecycle step may ever remove a contract")

    # =====================================================================
    # 7 — a reader is told, not surprised
    # =====================================================================
    def test_07_a_reader_is_told_before_they_type(self):
        user = self._persona(
            'cd3.contract.reader',
            ['hr.group_hr_user',
             'hr_contract.group_hr_contract_employee_manager'])
        # the employee-manager record rule shows a person their own team, so
        # the fixture employee is put under this persona (ledger CD3)
        boss = self.Employee.create({'name': 'CD3 Drawer Boss',
                                     'company_id': self.company.id,
                                     'user_id': user.id})
        self.employee.write({'parent_id': boss.id})

        payload = self._payload(user=user)
        self.assertTrue(payload['ok'])
        self.assertFalse(payload['can_write'])
        for group in payload['terms']:
            for entry in group['fields']:
                self.assertFalse(entry['writable'], entry['name'])

        wage_was = self.contract.wage
        amount_was = self.l_base.amount
        result = self.Facade.with_user(user).save_contract_360(
            self.contract.id, terms={'wage': 1.0},
            components={'edits': {self.l_base.id: {'amount': 1.0}}})
        self.assertFalse(result['ok'])
        self.assertEqual(result['saved'], 0)
        self.assertIn('HR manager', result['msg'])
        self.contract.invalidate_recordset()
        self.l_base.invalidate_recordset()
        self.assertEqual(self.contract.wage, wage_was)
        self.assertEqual(self.l_base.amount, amount_was)

        # and the preview says the same thing rather than promising a save
        preview = self.Facade.with_user(user).preview_contract_360(
            self.contract.id, terms={'wage': 1.0})
        self.assertEqual(preview['accept'], 0)

    # =====================================================================
    # 8 — nothing a person reads on this path says the wrong word
    # =====================================================================
    def test_08_no_sentence_on_the_edit_path_says_the_wrong_word(self):
        """White-label: the product's name is Payobook, and the escape hatch is
        called "Full form". Every sentence the editing path can produce is
        walked, keys included."""
        spoken = []

        # every refusal shape cases 1-7 can reach
        spoken += self._strings(self.Facade.preview_contract_360(
            self.contract.id,
            terms={'wage': 'abc', 'dependents': 'two', 'hirestatus': 'NOPE',
                   'resource_calendar_id': False, 'date_start': 'yesterday',
                   'not_a_field_at_all': 1, 'compa_ratio': 3},
            components={'edits': {self.l_base.id: {'text_value': 'words'}},
                        'removes': [self.l_mapped.id, 999999999],
                        'adds': [{'template_id': 999999999}]}))
        spoken += self._strings(self.Facade.save_contract_360(
            self.contract.id, terms={'wage': 'abc'}))
        spoken += self._strings(self.Facade.save_contract_360(
            999999999, terms={'wage': 1.0}))
        spoken += self._strings(self.Facade.run_contract_action(
            self.contract.id, 'unlink'))
        spoken += self._strings(self._payload())

        offenders = [text for text in spoken if 'odoo' in (text or '').lower()]
        self.assertFalse(
            offenders,
            "a user-visible string names the product Payobook, never the "
            "framework it happens to run on: %s" % offenders[:5])
