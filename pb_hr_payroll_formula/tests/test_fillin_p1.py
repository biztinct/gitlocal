# -*- coding: utf-8 -*-
"""FILLIN P1 — a new contract starts with the paying scheme's usual answers.

T1   a draft contract gets the non-zero usual answers, marked, and logged
T2   a line passed in the create vals is kept as given (FI2)
T3   nobody pays the person → the contract saves with no lines
T4   the scope helper raising → the contract still saves, a WARNING is logged
T5   a human write clears the mark and stamps who/when
T6   "Looks right" stamps without clearing the mark; a non-manager is refused
T7   the import sync keeps a filled-in line the file says nothing about (FI1),
     and a file that states the same value confirms it
T8   copy(): no "checked" stamps travel; the import's new-contract copy is not
     filled (the sync writes every component straight after)
T9   words for each value parse, and garbage gives []
T10  "Paid by" becoming known fills the person's contracts
T11  `pb_skip_fill_in` fills nothing
T12  the seed applier is idempotent and never touches a contract line

THE FIXTURE IS A COMPANY OF ITS OWN (the `pb_scheme_map` suite's rule): two
active schemes, so "the only scheme in this company" never answers, and the
paying scheme is reached through a team map line — the shape a real tenant has.
"""

from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_hr_payroll_formula.models.contract_fill_in import (
    parse_value_labels)

LOGGER = 'odoo.addons.pb_hr_payroll_formula.models.contract_fill_in'


@tagged('post_install', '-at_install', 'fillin')
class TestFillInP1(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Contract = cls.env['hr.contract']
        cls.Line = cls.env['hr.contract.advantage']
        cls.Change = cls.env['hr.contract.advantage.change']
        cls.Template = cls.env['hr.contract.advantage.template']
        cls.Rule = cls.env['hr.formula.rule']
        cls.has_map = 'pb.scheme.map' in cls.env \
            and 'hr.formula.scheme.assignment' in cls.env \
            and 'pb_paid_by_id' in cls.env['hr.employee']._fields

        cls.company = cls.env['res.company'].create({
            'name': 'FI Fixture Co',
            'currency_id': cls.env.ref('base.VND').id,
        })
        cls.env.user.company_ids = [(4, cls.company.id)]
        for company in (cls.env.company, cls.company):
            try:
                cls.env['biz.approval.seed'].set_no_approval_needed(
                    company, 'schememap',
                    reason='FILLIN suite: these cases are about the fill')
            except Exception:   # noqa: BLE001 — a fixture must not die here
                pass

        Department = cls.env['hr.department']
        cls.paid_team = Department.create({'name': 'FI Paid Team',
                                           'company_id': cls.company.id})
        cls.loose_team = Department.create({'name': 'FI Nobody Team',
                                            'company_id': cls.company.id})

        Config = cls.env['hr.formula.config']
        cls.scheme = Config.create({
            'name': 'FI Scheme', 'code': 'FIP1SCHEME', 'country_code': 'ID',
            'state': 'active', 'company_id': cls.company.id})
        cls.other = Config.create({
            'name': 'FI Other', 'code': 'FIP1OTHER', 'country_code': 'ID',
            'state': 'active', 'company_id': cls.company.id})

        cls.r_flag = cls._rule('FIFLAG', default_value=1.0,
                               value_kind='integer',
                               value_labels='0=No;1=Yes')
        cls.r_mode = cls._rule(
            'FIMODE', default_value=1.0, value_kind='integer',
            value_labels='0=None;1=Insurance-premium tax only;'
                         '2=All tax (net salary)')
        cls.r_zero = cls._rule('FIZERO', default_value=0.0,
                               value_kind='integer')
        cls.r_text = cls._rule('FITEXT', default_value=0.0,
                               value_kind='text', is_text_component=True)

        cls.calendar = cls.company.resource_calendar_id or cls.env[
            'resource.calendar'].create({'name': 'FI Hours',
                                         'company_id': cls.company.id})
        cls.kind = cls.env['hr.contract.type'].search([], limit=1) or cls.env[
            'hr.contract.type'].create({'name': 'FI Kind'})

        if cls.has_map:
            cls.env['hr.formula.scheme.assignment'].create({
                'config_id': cls.scheme.id,
                'department_id': cls.paid_team.id,
                'cycle_type': 'any'})

    # ------------------------------------------------------------ fixtures
    @classmethod
    def _rule(cls, code, **extra):
        vals = {'config_id': cls.scheme.id, 'name': 'FI %s' % code,
                'code': code, 'column_type': 'input', 'sequence': 1,
                'is_contract_component': True}
        vals.update(extra)
        return cls.env['hr.formula.rule'].create(vals)

    def _person(self, name, team):
        employee = self.env['hr.employee'].create({
            'name': name, 'company_id': self.company.id})
        version = employee.current_version_id
        if version and 'department_id' in version._fields:
            version.department_id = team.id
        elif 'department_id' in employee._fields:
            employee.department_id = team.id
        self.env.flush_all()
        return employee

    def _contract(self, employee, state='draft', **extra):
        vals = {
            'name': 'FI contract %s' % employee.name,
            'employee_id': employee.id,
            'company_id': self.company.id,
            'wage': 1000000.0,
            'state': state,
            'date_start': '2026-06-01',
            'resource_calendar_id': self.calendar.id,
            'type_id': self.kind.id,
        }
        vals.update(extra)
        return self.Contract.create(vals)

    def _lines(self, contract):
        contract.invalidate_recordset()
        return {line.advantage_template_id.code: line
                for line in self.Line.search(
                    [('contract_id', '=', contract.id)])}

    def _changes(self, contract, source):
        return self.Change.search([('contract_id', '=', contract.id),
                                   ('change_source', '=', source)])

    def _require_map(self):
        if not self.has_map:
            self.skipTest('pb_scheme_map is not installed on this database')

    def _filled_contract(self, name='FI Filled'):
        self._require_map()
        return self._contract(self._person(name, self.paid_team))

    # ================================================================== T1
    def test_t1_a_new_contract_gets_the_usual_answers(self):
        contract = self._filled_contract('FI T1')
        lines = self._lines(contract)
        self.assertEqual(set(lines), {'FIFLAG', 'FIMODE'},
                         'only the non-zero numeric usual answers are filled')
        for code in ('FIFLAG', 'FIMODE'):
            self.assertEqual(lines[code].amount, 1.0)
            self.assertEqual(lines[code].pb_fill, 'auto')
            self.assertFalse(lines[code].pb_checked_at)
        rows = self._changes(contract, 'auto_default')
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows.mapped('new_amount')), {1.0})
        self.assertEqual(rows.mapped('changed_by'), self.env.user)

    # ================================================================== T2
    def test_t2_a_line_in_the_create_vals_is_kept(self):
        self._require_map()
        flag_tmpl = self.Template.template_for_rule(self.r_flag)
        contract = self._contract(
            self._person('FI T2', self.paid_team),
            advantages_ids=[(0, 0, {'advantage_template_id': flag_tmpl.id,
                                    'amount': 0.0})])
        lines = self._lines(contract)
        self.assertEqual(lines['FIFLAG'].amount, 0.0)
        self.assertFalse(lines['FIFLAG'].pb_fill)
        self.assertEqual(lines['FIMODE'].pb_fill, 'auto')
        self.assertEqual(len(self._changes(contract, 'auto_default')), 1)

    # ================================================================== T3
    def test_t3_nobody_pays_the_person(self):
        self._require_map()
        contract = self._contract(self._person('FI T3', self.loose_team))
        self.assertTrue(contract.exists())
        self.assertEqual(self._lines(contract), {})
        self.assertFalse(self._changes(contract, 'auto_default'))

    # ================================================================== T4
    def test_t4_a_broken_scope_helper_never_blocks_a_contract(self):
        self._require_map()
        employee = self._person('FI T4', self.paid_team)
        Config = type(self.env['hr.formula.config'])

        def boom(*_args, **_kwargs):
            raise RuntimeError('FI T4 scope exploded')

        with patch.object(Config, 'component_scope_for_employee', boom), \
                self.assertLogs(LOGGER, level='WARNING') as logged:
            contract = self._contract(employee)
        self.assertTrue(contract.exists())
        self.assertEqual(self._lines(contract), {})
        self.assertTrue(any('pb fill-in: contract %s' % contract.id in m
                            for m in logged.output), logged.output)

    # ================================================================== T5
    def test_t5_a_human_write_takes_the_line_over(self):
        contract = self._filled_contract('FI T5')
        line = self._lines(contract)['FIFLAG']
        line.write({'amount': 0.0})
        self.assertFalse(line.pb_fill)
        self.assertEqual(line.pb_checked_by.id, self.env.uid)
        self.assertTrue(line.pb_checked_at)
        # the other filled line is untouched
        self.assertEqual(self._lines(contract)['FIMODE'].pb_fill, 'auto')

    # ================================================================== T6
    def test_t6_looks_right(self):
        contract = self._filled_contract('FI T6')
        self.assertEqual(len(contract.pb_fillin_unchecked()), 2)

        clerk = self.env['res.users'].create({
            'name': 'FI HR Clerk', 'login': 'fi.hr.clerk@example.com',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('hr.group_hr_user').id])],
        })
        with self.assertRaises(AccessError):
            contract.with_user(clerk).pb_fillin_check()
        self.assertEqual(len(contract.pb_fillin_unchecked()), 2,
                         'a refused check must not stamp anything')

        manager = self.env['res.users'].create({
            'name': 'FI Payroll Manager', 'login': 'fi.pay.mgr@example.com',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref(
                'om_hr_payroll.group_hr_payroll_manager').id])],
        })
        stamped = contract.with_user(manager).pb_fillin_check()
        self.assertEqual(stamped, 2)
        for line in self._lines(contract).values():
            self.assertEqual(line.pb_fill, 'auto')
            self.assertEqual(line.pb_checked_by, manager)
            self.assertTrue(line.pb_checked_at)
            self.assertEqual(line.amount, 1.0)
        rows = self._changes(contract, 'checked')
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows.mapped('changed_by'), manager)
        self.assertFalse(contract.pb_fillin_unchecked())
        self.assertEqual(contract.pb_fillin_check(), 0, 'nothing left')

    def test_t6b_looks_right_on_named_lines_only(self):
        contract = self._filled_contract('FI T6b')
        flag = self._lines(contract)['FIFLAG']
        self.assertEqual(contract.pb_fillin_check(line_ids=[flag.id]), 1)
        self.assertEqual(contract.pb_fillin_unchecked().mapped(
            'advantage_template_id.code'), ['FIMODE'])

    # ================================================================== T7
    def _batch_line(self, employee, raw):
        batch = self.env['hr.payroll.import.batch'].create({
            'name': 'FI Sync', 'source_type': 'excel',
            'formula_config_id': self.scheme.id})
        line = self.env['hr.payroll.import.line'].create({
            'batch_id': batch.id, 'employee_id': employee.id,
            'raw_data_json': raw})
        return batch, line

    def test_t7_the_file_without_the_column_leaves_the_fill_alone(self):
        contract = self._filled_contract('FI T7')
        batch, line = self._batch_line(contract.employee_id,
                                       '{"Something Else": 5}')
        batch._sync_contract_components(line, contract)
        lines = self._lines(contract)
        self.assertEqual(lines['FIFLAG'].amount, 1.0)
        self.assertEqual(lines['FIFLAG'].pb_fill, 'auto')
        self.assertFalse(lines['FIFLAG'].pb_checked_at)
        self.assertEqual(lines['FIMODE'].pb_fill, 'auto')

    def test_t7b_the_file_stating_the_same_value_confirms_it(self):
        contract = self._filled_contract('FI T7b')
        self.r_flag.set_source_binding('excel', 'Flag Column')
        batch, line = self._batch_line(contract.employee_id,
                                       '{"Flag Column": 1}')
        batch._sync_contract_components(line, contract)
        lines = self._lines(contract)
        self.assertEqual(lines['FIFLAG'].amount, 1.0)
        self.assertFalse(lines['FIFLAG'].pb_fill,
                         'the file is a human source (FI1)')
        self.assertTrue(lines['FIFLAG'].pb_checked_at)
        self.assertEqual(lines['FIMODE'].pb_fill, 'auto')

    def test_t7c_the_file_with_a_different_value_replaces_it(self):
        contract = self._filled_contract('FI T7c')
        self.r_flag.set_source_binding('excel', 'Flag Column')
        batch, line = self._batch_line(contract.employee_id,
                                       '{"Flag Column": 0}')
        batch._sync_contract_components(line, contract)
        flag = self._lines(contract)['FIFLAG']
        self.assertEqual(flag.amount, 0.0)
        self.assertFalse(flag.pb_fill)

    # ================================================================== T8
    def test_t8_copy_carries_no_checked_marks(self):
        contract = self._filled_contract('FI T8')
        contract.pb_fillin_check()
        copy = contract.copy({'date_start': '2026-07-01'})
        copied = self._lines(copy)
        for line in copied.values():
            self.assertFalse(line.pb_checked_by,
                             'a "checked" stamp travelled onto the copy')
            self.assertFalse(line.pb_checked_at)
        # the original is untouched
        for line in self._lines(contract).values():
            self.assertTrue(line.pb_checked_at)

    def test_t8b_the_import_copy_is_not_filled(self):
        contract = self._filled_contract('FI T8b')
        batch, _line = self._batch_line(contract.employee_id, '{}')
        fresh = batch._create_new_contract_for_components(contract)
        self.assertNotEqual(fresh, contract)
        self.assertEqual(self._lines(fresh), {},
                         'the sync fills this copy; the fill-in must not')

    # ================================================================== T9
    def test_t9_words_for_each_value(self):
        self.assertEqual(parse_value_labels('0=No;1=Yes'),
                         [{'value': 0.0, 'label': 'No'},
                          {'value': 1.0, 'label': 'Yes'}])
        self.assertEqual(
            [o['label'] for o in self.r_mode.value_label_options()],
            ['None', 'Insurance-premium tax only', 'All tax (net salary)'])
        self.assertEqual(parse_value_labels(' 0 = No ; 1 = Yes ;'),
                         [{'value': 0.0, 'label': 'No'},
                          {'value': 1.0, 'label': 'Yes'}])
        for garbage in ('yes', '0=No;x=Yes', '0=;1=Yes', '0=No;0=Nope',
                        '=No', None, '', ';;'):
            self.assertEqual(parse_value_labels(garbage), [], garbage)
        self.assertEqual(self.r_flag.value_label_for(1.0), 'Yes')
        self.assertEqual(self.r_flag.value_label_for(0), 'No')
        self.assertEqual(self.r_flag.value_label_for(7), '')
        self.assertEqual(self.r_zero.value_label_options(), [])
        self.assertEqual(self.r_zero.value_label_for(1.0), '')
        self.assertEqual(self.r_flag.value_label_control(), 'toggle')
        self.assertEqual(self.r_mode.value_label_control(), 'select')
        self.assertEqual(self.r_zero.value_label_control(), '')

    # ================================================================= T10
    def test_t10_paid_by_becoming_known_fills_the_contract(self):
        self._require_map()
        employee = self._person('FI T10', self.loose_team)
        contract = self._contract(employee, state='open')
        self.assertEqual(self._lines(contract), {})
        self.assertFalse(employee.pb_paid_by_id)

        self.env['hr.formula.scheme.assignment'].create({
            'config_id': self.scheme.id,
            'department_id': self.loose_team.id,
            'cycle_type': 'any'})
        self.env.flush_all()
        self.env['hr.employee']._pb_recompute_paid_by(
            employee_ids=[employee.id])
        employee.invalidate_recordset()
        self.assertEqual(employee.pb_paid_by_id, self.scheme)
        lines = self._lines(contract)
        self.assertEqual(set(lines), {'FIFLAG', 'FIMODE'})
        self.assertEqual(lines['FIFLAG'].pb_fill, 'auto')

        # a second recompute is a no-op: nothing is filled twice
        self.env['hr.employee']._pb_mark_paid_by_stale(
            employee_ids=[employee.id])
        self.env['hr.employee']._pb_recompute_paid_by(
            employee_ids=[employee.id])
        self.assertEqual(len(self._changes(contract, 'auto_default')), 2)

    # ================================================================= T11
    def test_t11_skip_context(self):
        self._require_map()
        employee = self._person('FI T11', self.paid_team)
        contract = self.Contract.with_context(pb_skip_fill_in=True).create({
            'name': 'FI T11', 'employee_id': employee.id,
            'company_id': self.company.id, 'wage': 1.0, 'state': 'draft',
            'date_start': '2026-06-01',
            'resource_calendar_id': self.calendar.id,
            'type_id': self.kind.id})
        self.assertEqual(self._lines(contract), {})

    def test_t11b_a_closed_contract_is_history(self):
        self._require_map()
        contract = self._contract(self._person('FI T11b', self.paid_team),
                                  state='close',
                                  date_end='2026-06-30')
        self.assertEqual(self._lines(contract), {})

    # ================================================================= T12
    def test_t12_the_seed_applier_is_idempotent(self):
        self.Line.flush_model()
        before = self.Line.search_count([])
        spec = {
            'FIFLAG': {'default_value': 1.0, 'value_labels': '0=No;1=Yes'},
            'FIZERO': {'default_value': 0.0, 'value_labels': '0=No;1=Yes'},
            'FIMODE': {'default_value': 2.0},
            'FINOPE': {'default_value': 1.0},
        }
        first = self.scheme._pb_apply_usual_answers(spec)
        self.assertEqual(sorted(first['written']), ['FIMODE', 'FIZERO'])
        self.assertEqual(first['missing'], ['FINOPE'])
        self.assertEqual(self.r_zero.value_labels, '0=No;1=Yes')
        self.assertEqual(self.r_mode.default_value, 2.0)
        second = self.scheme._pb_apply_usual_answers(spec)
        self.assertEqual(second['written'], [], 'a second run wrote again')
        self.assertEqual(self.Line.search_count([]), before,
                         'the seed touched a contract line')
