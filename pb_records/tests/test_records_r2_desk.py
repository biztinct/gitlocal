# -*- coding: utf-8 -*-
"""RECORDS R2 — the Records Desk, case by case.

Twelve numbered cases, and the numbers are the handover's. What they are for,
in one line each: the catalogue offers only what the scheme maps (1), the
roster answers the filters (2), a value is judged before it is written (3),
applying writes exactly the diff and nothing beside it (4), a bank account is
four columns and one record (5), a contract component is a line and an audit
row (6), an undo is honest about what changed underneath it (7), an unmapped
destination never reaches a write (8), another company's employee is invisible
(9), a quarter of a thousand people page correctly (10), no payslip is touched
(11), and no user-visible string says the wrong word (12).

`action_process` is never called (J3/J10): every record these tests read or
write was created by the transaction they run in.
"""
import hashlib
import json
import os
import re

from odoo.exceptions import UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged


def _src(module, *parts):
    with open(os.path.join(get_module_path(module), *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestRecordsR2Desk(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Desk = cls.env['pb.records.desk']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Mapping = cls.env['hr.payslip.import.mapping']
        cls.Employee = cls.env['hr.employee']
        cls.Contract = cls.env['hr.contract']
        cls.IrModel = cls.env['ir.model']
        cls.IrField = cls.env['ir.model.fields']
        cls.company = cls.env.company

        # A boolean destination that exists on THIS build. `hr.employee`'s
        # boolean set differs between deployments, so the fixture picks one from
        # the registry rather than naming one and hoping.
        cls.bool_field = next(
            (f for f in ('birthday_public_display', 'vn_hi_enrolled',
                         'manually_set_presence', 'active')
             if f in cls.Employee._fields
             and not cls.Employee._fields[f].readonly),
            'active')

        cls.cfg = cls._config('RD Scheme A')
        cls.cfg_b = cls._config('RD Scheme B')

        cls.r_loc = cls._rule(cls.cfg, 'Work location', 'RDLOCATION')
        cls.r_shui = cls._rule(cls.cfg, 'SHUI participation', 'RDSHUIPART')
        cls.r_dept = cls._rule(cls.cfg, 'Department', 'RDDEPT')
        cls.r_bool = cls._rule(cls.cfg, 'Birthday shown', 'RDBDAYFLAG')
        cls.r_accno = cls._rule(cls.cfg, 'Bank account', 'RDACCNO')
        cls.r_bank = cls._rule(cls.cfg, 'Bank name', 'RDBANKNAME')
        cls.r_bonus = cls._rule(cls.cfg, 'Site bonus', 'RDBONUS',
                                is_contract_component=True)

        cls.m_loc = cls._map_field(cls.cfg, cls.r_loc, 'hr.employee', 'location')
        cls.m_shui = cls._map_field(cls.cfg, cls.r_shui, 'hr.contract', 'shuipart')
        cls.m_dept = cls._map_field(cls.cfg, cls.r_dept, 'hr.contract',
                                    'department_id')
        cls.m_bool = cls._map_field(cls.cfg, cls.r_bool, 'hr.employee',
                                    cls.bool_field)
        cls.m_accno = cls._map_bank(cls.cfg, cls.r_accno, 'acc_number')
        cls.m_bank = cls._map_bank(cls.cfg, cls.r_bank, 'bank_name')

        # Scheme B maps ONE destination scheme A also maps, so the union in
        # case 1 has something real to de-duplicate.
        cls.r_loc_b = cls._rule(cls.cfg_b, 'Work location', 'RDBLOCATION')
        cls.r_vn_b = cls._rule(cls.cfg_b, 'Vietnamese name', 'RDBFULLNAME')
        cls._map_field(cls.cfg_b, cls.r_loc_b, 'hr.employee', 'location')
        cls._map_field(cls.cfg_b, cls.r_vn_b, 'hr.employee', 'full_name_vn')

        Dept = cls.env['hr.department']
        cls.dept_a = Dept.create({'name': 'RD Alpha', 'company_id': cls.company.id})
        cls.dept_b = Dept.create({'name': 'RD Beta', 'company_id': cls.company.id})
        cls.job_a = cls.env['hr.job'].create({'name': 'RD Operator'})

        cls.e1 = cls._employee('RD One', department_id=cls.dept_a.id,
                               job_id=cls.job_a.id, location='Operator')
        cls.e2 = cls._employee('RD Two', department_id=cls.dept_a.id,
                               location='Operator')
        cls.e3 = cls._employee('RD Three', department_id=cls.dept_b.id,
                               location='Fitter')          # no contract
        cls.e4 = cls._employee('RD Four Control', department_id=cls.dept_b.id,
                               location='Control')

        cls.c1 = cls._contract(cls.e1, department_id=cls.dept_a.id)
        cls.c2 = cls._contract(cls.e2, department_id=cls.dept_a.id)
        cls.c4 = cls._contract(cls.e4, department_id=cls.dept_b.id)

    # --------------------------------------------------------------- fixtures
    @classmethod
    def _config(cls, name):
        return cls.Config.create({
            'name': name, 'code': name.upper().replace(' ', '')[:32],
            'country_code': 'VN', 'state': 'active',
            'company_id': cls.env.company.id,
        })

    @classmethod
    def _rule(cls, cfg, name, code, **extra):
        return cls.Rule.create(dict({
            'config_id': cfg.id, 'name': name, 'code': code,
            'column_type': 'input', 'sequence': 1, 'default_value': 0.0,
        }, **extra))

    @classmethod
    def _field(cls, model, name):
        return cls.IrField.search(
            [('model', '=', model), ('name', '=', name)], limit=1)

    @classmethod
    def _model(cls, model):
        return cls.IrModel.search([('model', '=', model)], limit=1)

    @classmethod
    def _map_field(cls, cfg, rule, model, field):
        return cls.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'field',
            'target_model_id': cls._model(model).id,
            'target_field_id': cls._field(model, field).id,
        })

    @classmethod
    def _map_bank(cls, cfg, rule, role):
        return cls.Mapping.create({
            'salary_structure_id': cfg.id, 'component_id': rule.id,
            'destination_type': 'bank_account', 'bank_role': role})

    @classmethod
    def _employee(cls, name, **vals):
        return cls.Employee.create(dict(
            {'name': name, 'company_id': cls.env.company.id}, **vals))

    @classmethod
    def _contract(cls, employee, **vals):
        return cls.Contract.create(dict({
            'name': '%s contract' % employee.name,
            'employee_id': employee.id,
            'wage': 1000.0,
            'state': 'open',
            'date_start': '2026-01-01',
        }, **vals))

    # ---------------------------------------------------------------- helpers
    def _cards(self, config_id=None):
        return self.Desk.get_fields(config_id if config_id is not None else self.cfg.id)

    def _card_ids(self, data):
        return {c['id'] for g in data['groups'] for c in g['fields']}

    def _card(self, data, card_id):
        for group in data['groups']:
            for card in group['fields']:
                if card['id'] == card_id:
                    return card
        return None

    def _payslip_fingerprint(self):
        slips = self.env['hr.payslip'].sudo().search([], order='id')
        blob = '|'.join((s.formula_input_values or '') for s in slips)
        return len(slips), hashlib.md5(blob.encode('utf-8')).hexdigest()

    # =====================================================================
    # 1 — the catalogue offers what the scheme maps, and nothing else
    # =====================================================================
    def test_01a_get_fields_returns_exactly_the_mapped_destinations(self):
        data = self._cards()
        ids = self._card_ids(data)
        self.assertEqual(ids, {
            'f:hr.employee:location',
            'f:hr.contract:shuipart',
            'f:hr.contract:department_id',
            'f:hr.employee:%s' % self.bool_field,
            'b:acc_number', 'b:bank_name',
            'c:RDBONUS',
        })
        groups = {g['key'] for g in data['groups']}
        self.assertEqual(groups, {'employee', 'contract', 'bank', 'component'})

    def test_01b_a_field_the_scheme_does_not_map_is_absent(self):
        ids = self._card_ids(self._cards())
        self.assertNotIn('f:hr.employee:barcode', ids)
        self.assertNotIn('f:hr.contract:wage', ids)

    def test_01c_a_selection_card_carries_its_pairs_and_a_hint(self):
        card = self._card(self._cards(), 'f:hr.contract:shuipart')
        self.assertEqual(card['ttype'], 'selection')
        self.assertEqual({p['key'] for p in card['selection']}, {'YES', 'NO'})
        self.assertTrue(card['editable'])
        # The component the destination is wired to is named in plain words.
        self.assertIn('RDSHUIPART', card['sub'])

    def test_01d_a_many2one_card_says_whether_a_value_is_created(self):
        card = self._card(self._cards(), 'f:hr.contract:department_id')
        self.assertEqual(card['ttype'], 'many2one')
        self.assertEqual(card['m2o']['comodel'], 'hr.department')
        self.assertTrue(card['m2o']['creates_missing'])

    def test_01e_config_zero_unions_the_schemes_without_duplicates(self):
        data = self.Desk.get_fields(0)
        ids = [c['id'] for g in data['groups'] for c in g['fields']]
        self.assertEqual(len(ids), len(set(ids)), "a destination two schemes "
                                                  "share must appear once")
        self.assertIn('f:hr.employee:full_name_vn', set(ids))  # B only
        self.assertIn('f:hr.contract:shuipart', set(ids))     # A only
        self.assertIn('f:hr.employee:location', set(ids))      # both

    # =====================================================================
    # 2 — the roster answers the filters
    # =====================================================================
    def test_02a_search_returns_the_people_with_their_values(self):
        data = self.Desk.search_people(
            self.cfg.id, {'employee_ids': [self.e1.id]},
            ['f:hr.employee:location', 'f:hr.contract:shuipart',
             'f:hr.contract:department_id'])
        self.assertEqual(data['total'], 1)
        row = data['rows'][0]
        self.assertEqual(row['id'], self.e1.id)
        self.assertEqual(row['values']['f:hr.employee:location']['v'], 'Operator')
        # A selection carries the KEY to write and the LABEL to show.
        self.assertEqual(row['values']['f:hr.contract:shuipart']['v'], 'YES')
        self.assertEqual(row['values']['f:hr.contract:shuipart']['label'], 'YES')
        # A many2one carries the id and the display name.
        self.assertEqual(row['values']['f:hr.contract:department_id']['v'],
                         self.dept_a.id)
        self.assertEqual(row['values']['f:hr.contract:department_id']['label'],
                         self.dept_a.display_name)

    def test_02b_department_and_job_and_search_all_narrow_the_list(self):
        base = {'employee_ids': [self.e1.id, self.e2.id, self.e3.id, self.e4.id]}
        by_dept = self.Desk.search_people(
            self.cfg.id, dict(base, department_ids=[self.dept_a.id]), [])
        self.assertEqual({r['id'] for r in by_dept['rows']}, {self.e1.id, self.e2.id})
        by_job = self.Desk.search_people(
            self.cfg.id, dict(base, job_ids=[self.job_a.id]), [])
        self.assertEqual({r['id'] for r in by_job['rows']}, {self.e1.id})
        by_q = self.Desk.search_people(self.cfg.id, dict(base, q='RD Three'), [])
        self.assertEqual({r['id'] for r in by_q['rows']}, {self.e3.id})

    def test_02c_a_shortlist_intersects_and_never_overrides(self):
        data = self.Desk.search_people(self.cfg.id, {
            'employee_ids': [self.e1.id, self.e3.id],
            'department_ids': [self.dept_a.id],
        }, [])
        self.assertEqual({r['id'] for r in data['rows']}, {self.e1.id})

    def test_02d_contract_state_filters_and_the_contract_less_person(self):
        base = {'employee_ids': [self.e1.id, self.e3.id]}
        rows = self.Desk.search_people(self.cfg.id, base,
                                       ['f:hr.contract:shuipart'])['rows']
        by_id = {r['id']: r for r in rows}
        self.assertFalse(by_id[self.e3.id]['contract_id'])
        self.assertEqual(by_id[self.e3.id]['contract_state'], 'none')
        self.assertTrue(by_id[self.e3.id]
                        ['values']['f:hr.contract:shuipart']['missing'])
        none_only = self.Desk.search_people(
            self.cfg.id, dict(base, contract_states=['none']), [])
        self.assertEqual({r['id'] for r in none_only['rows']}, {self.e3.id})

    def test_02e_facets_count_what_they_would_add(self):
        data = self.Desk.search_people(self.cfg.id, {
            'employee_ids': [self.e1.id, self.e2.id, self.e3.id, self.e4.id]}, [])
        depts = {d['name']: d['count'] for d in data['facets']['departments']}
        self.assertEqual(depts['RD Alpha'], 2)
        self.assertEqual(depts['RD Beta'], 2)

    # =====================================================================
    # 3 — a value is judged before it is written
    # =====================================================================
    def _preview(self, changes):
        return self.Desk.preview_changes(self.cfg.id, changes)

    def test_03a_a_selection_label_becomes_its_key(self):
        res = self._preview([{'emp_id': self.e1.id,
                              'field_id': 'f:hr.contract:shuipart',
                              'value': 'NO'}])
        item = res['items'][0]
        self.assertEqual(item['status'], 'ok')
        self.assertEqual(item['old_label'], 'YES')
        self.assertEqual(item['new_label'], 'NO')
        self.assertEqual(res['counts']['ok'], 1)
        # And nothing was written by looking.
        self.assertEqual(self.c1.shuipart, 'YES')

    def test_03b_a_value_that_is_not_a_choice_is_refused_and_says_which_are(self):
        res = self._preview([{'emp_id': self.e1.id,
                              'field_id': 'f:hr.contract:shuipart',
                              'value': 'Maybe'}])
        item = res['items'][0]
        self.assertEqual(item['status'], 'refused')
        self.assertIn("'Maybe' is not one of the choices", item['why'])
        self.assertIn('YES', item['why'])
        self.assertIn('NO', item['why'])

    def test_03c_setting_a_value_to_what_it_already_is_is_not_a_change(self):
        res = self._preview([{'emp_id': self.e1.id,
                              'field_id': 'f:hr.contract:shuipart',
                              'value': 'YES'}])
        self.assertEqual(res['items'][0]['status'], 'same')
        self.assertEqual(res['counts']['ok'], 0)

    def test_03d_a_boolean_reads_yes_and_no_as_people_write_them(self):
        field_id = 'f:hr.employee:%s' % self.bool_field
        current = bool(self.e1[self.bool_field])
        word = 'No' if current else 'Yes'
        res = self._preview([{'emp_id': self.e1.id, 'field_id': field_id,
                              'value': word}])
        self.assertEqual(res['items'][0]['status'], 'ok')
        self.assertEqual(res['items'][0]['new_label'],
                         'No' if current else 'Yes')
        bad = self._preview([{'emp_id': self.e1.id, 'field_id': field_id,
                              'value': 'Perhaps'}])
        self.assertEqual(bad['items'][0]['status'], 'refused')
        self.assertIn('yes or a no', bad['items'][0]['why'])

    def test_03e_a_person_with_no_contract_is_refused_by_name(self):
        res = self._preview([{'emp_id': self.e3.id,
                              'field_id': 'f:hr.contract:shuipart',
                              'value': 'NO'}])
        self.assertEqual(res['items'][0]['status'], 'refused')
        self.assertIn('no contract', res['items'][0]['why'])

    def test_03f_a_many2one_that_does_not_exist_names_what_would_happen(self):
        res = self._preview([{'emp_id': self.e1.id,
                              'field_id': 'f:hr.contract:department_id',
                              'value': 'RD Gamma'}])
        # Departments ARE created from a mapped column (`m2o_creates_missing`),
        # so this is offered rather than refused — and it says so.
        self.assertEqual(res['items'][0]['status'], 'ok')
        self.assertIn('new', res['items'][0]['new_label'])
        self.assertFalse(self.env['hr.department'].search([('name', '=', 'RD Gamma')]),
                         "a preview must not create anything")

    # =====================================================================
    # 4 — applying writes exactly the diff
    # =====================================================================
    def test_04_apply_writes_the_diff_and_leaves_everything_else_alone(self):
        # NOT `write_date`. Odoo's `write_date` default is SQL `now()`, which in
        # PostgreSQL is the TRANSACTION timestamp — every row written anywhere in
        # one test carries the same stamp, so "did this record change" cannot be
        # asked that way inside a transaction (RD9). The VALUES are asked
        # instead, and the audit trail is asked whether it mentions them.
        self.env.flush_all()
        control_shui = self.c4.shuipart
        control_dept = self.c4.department_id

        changes = []
        for emp in (self.e1, self.e2):
            changes.append({'emp_id': emp.id,
                            'field_id': 'f:hr.employee:location',
                            'value': 'Line Lead'})
            changes.append({'emp_id': emp.id,
                            'field_id': 'f:hr.contract:shuipart',
                            'value': 'NO'})
        # A third person, one field.
        changes.append({'emp_id': self.e4.id,
                        'field_id': 'f:hr.employee:location',
                        'value': 'Line Lead'})

        res = self.Desk.apply_changes(self.cfg.id, changes, note='R2 case 4')
        self.assertTrue(res['ok'])
        self.assertEqual(res['written'], 5)
        self.assertEqual(res['people'], 3)

        self.assertEqual(self.e1.location, 'Line Lead')
        self.assertEqual(self.e2.location, 'Line Lead')
        self.assertEqual(self.c1.shuipart, 'NO')
        self.assertEqual(self.c2.shuipart, 'NO')
        # e4's location changed; its CONTRACT was never in the change set.
        self.env.flush_all()
        self.assertEqual(self.e4.location, 'Line Lead')
        self.assertEqual(self.c4.shuipart, control_shui)
        self.assertEqual(self.c4.department_id, control_dept)
        # e3 was in no change at all.
        self.assertEqual(self.e3.location, 'Fitter')

        apply_rec = self.env['pb.records.apply'].browse(res['apply_id'])
        self.assertFalse(apply_rec.change_ids.filtered(
            lambda c: c.model == 'hr.contract' and c.res_id == self.c4.id),
            "the control contract must not appear in the audit trail")
        self.assertEqual(apply_rec.count_values, 5)
        self.assertEqual(apply_rec.count_people, 3)
        self.assertEqual(apply_rec.note, 'R2 case 4')
        self.assertEqual(apply_rec.source, 'desk')
        self.assertEqual(len(apply_rec.change_ids), 5)

        row = apply_rec.change_ids.filtered(
            lambda c: c.employee_id == self.e1
            and c.field_key == 'f:hr.contract:shuipart')
        self.assertEqual(len(row), 1)
        self.assertEqual(json.loads(row.old_json), 'YES')
        self.assertEqual(json.loads(row.new_json), 'NO')
        self.assertEqual(row.model, 'hr.contract')
        self.assertEqual(row.res_id, self.c1.id)

    # =====================================================================
    # 5 — a bank account is four columns and one record
    # =====================================================================
    def test_05a_account_number_and_bank_name_make_one_account(self):
        res = self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': self.e1.id, 'field_id': 'b:acc_number',
             'value': '1234 5678 90'},
            {'emp_id': self.e1.id, 'field_id': 'b:bank_name',
             'value': 'RD Bank'},
        ])
        self.assertEqual(res['written'], 2)
        accounts = self.e1.bank_account_ids
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts.acc_number, '1234567890')
        self.assertEqual(accounts.bank_id.name, 'RD Bank')

    def test_05b_a_different_account_number_adds_and_never_replaces(self):
        self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': self.e2.id, 'field_id': 'b:acc_number', 'value': '111000'},
        ])
        first = self.e2.bank_account_ids
        self.assertEqual(len(first), 1)
        self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': self.e2.id, 'field_id': 'b:acc_number', 'value': '222000'},
        ])
        self.assertEqual(len(self.e2.bank_account_ids), 2)
        self.assertIn(first.id, self.e2.bank_account_ids.ids)

    def test_05c_a_bank_name_with_no_account_number_is_refused_in_words(self):
        res = self.Desk.preview_changes(self.cfg.id, [
            {'emp_id': self.e4.id, 'field_id': 'b:bank_name', 'value': 'RD Bank'},
        ])
        item = res['items'][0]
        self.assertEqual(item['status'], 'refused')
        self.assertIn('need an account number', item['why'])
        self.assertFalse(self.e4.bank_account_ids)

    # =====================================================================
    # 6 — a contract component is a line and an audit row
    # =====================================================================
    def test_06a_a_component_writes_its_line_and_creates_the_template(self):
        Template = self.env['hr.contract.advantage.template']
        self.assertFalse(Template.search([('code', '=', 'RDBONUS')]))
        res = self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': self.e1.id, 'field_id': 'c:RDBONUS', 'value': '250000'},
        ])
        self.assertEqual(res['written'], 1)
        template = Template.search([('code', '=', 'RDBONUS')])
        self.assertEqual(len(template), 1)
        self.assertEqual(template.value_type, 'amount')
        line = self.env['hr.contract.advantage'].search([
            ('contract_id', '=', self.c1.id),
            ('advantage_template_id', '=', template.id)])
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.amount, 250000.0, places=2)

        change = self.env['hr.contract.advantage.change'].search([
            ('contract_id', '=', self.c1.id),
            ('advantage_template_id', '=', template.id)])
        self.assertEqual(len(change), 1)
        self.assertEqual(change.change_source, 'manual')
        self.assertAlmostEqual(change.new_amount, 250000.0, places=2)
        self.assertIn('Records Desk apply', change.notes or '')

    def test_06b_an_existing_template_of_the_other_kind_is_never_flipped(self):
        # RD1: the template is created FIRST, so the contract created after it
        # already carries its (empty) line — creating one here as well would
        # give the code two lines and a silent pick between them.
        self.env['hr.contract.advantage.template'].create({
            'name': 'Text bonus', 'code': 'RDTEXTONLY',
            'lower_bound': 0.0, 'upper_bound': 0.0, 'default_value': 0.0,
            'value_type': 'text',
        })
        rule = self._rule(self.cfg, 'Text bonus', 'RDTEXTONLY',
                          is_contract_component=True)
        employee = self._employee('RD Six')
        contract = self._contract(employee)
        res = self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': employee.id, 'field_id': 'c:RDTEXTONLY', 'value': '900'},
        ])
        self.assertEqual(res['written'], 0)
        self.assertTrue(res['refused'])
        self.assertIn('already kept as', res['refused'][0]['why'])
        line = self.env['hr.contract.advantage'].search([
            ('contract_id', '=', contract.id),
            ('advantage_template_code', '=', 'RDTEXTONLY')])
        self.assertFalse(any(l.amount for l in line))
        self.assertTrue(rule)

    # =====================================================================
    # 7 — undo is honest about what changed underneath it
    # =====================================================================
    def test_07a_undo_puts_the_old_values_back(self):
        res = self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': self.e1.id, 'field_id': 'f:hr.employee:location',
             'value': 'Line Lead'},
            {'emp_id': self.e2.id, 'field_id': 'f:hr.contract:shuipart',
             'value': 'NO'},
        ])
        self.assertEqual(self.e1.location, 'Line Lead')
        undone = self.Desk.undo_apply(res['apply_id'])
        self.assertTrue(undone['ok'])
        self.assertEqual(undone['restored'], 2)
        self.assertEqual(undone['skipped_changed_since'], 0)
        self.assertEqual(self.e1.location, 'Operator')
        self.assertEqual(self.c2.shuipart, 'YES')
        self.assertTrue(self.env['pb.records.apply'].browse(res['apply_id']).undone)

    def test_07b_a_value_changed_since_is_reported_not_clobbered(self):
        res = self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': self.e1.id, 'field_id': 'f:hr.employee:location',
             'value': 'Line Lead'},
            {'emp_id': self.e2.id, 'field_id': 'f:hr.employee:location',
             'value': 'Line Lead'},
        ])
        # Somebody else moves on.
        self.e2.location = 'Shift Manager'
        undone = self.Desk.undo_apply(res['apply_id'])
        self.assertEqual(undone['restored'], 1)
        self.assertEqual(undone['skipped_changed_since'], 1)
        self.assertEqual(self.e1.location, 'Operator')
        self.assertEqual(self.e2.location, 'Shift Manager')

    def test_07c_an_undo_is_itself_an_apply_and_cannot_be_run_twice(self):
        res = self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': self.e1.id, 'field_id': 'f:hr.employee:location',
             'value': 'Line Lead'},
        ])
        first = self.Desk.undo_apply(res['apply_id'])
        self.assertTrue(first['ok'])
        undo_rec = self.env['pb.records.apply'].browse(first['apply_id'])
        self.assertEqual(undo_rec.source, 'undo')
        self.assertEqual(undo_rec.count_values, 1)
        second = self.Desk.undo_apply(res['apply_id'])
        self.assertFalse(second['ok'])
        self.assertIn('already been undone', second['msg'])

    # =====================================================================
    # 8 — an unmapped destination never reaches a write
    # =====================================================================
    def test_08_a_field_the_scheme_does_not_map_raises_before_anything(self):
        self.env.flush_all()
        applies_before = self.env['pb.records.apply'].search_count([])
        with self.assertRaises(UserError):
            self.Desk.apply_changes(self.cfg.id, [
                {'emp_id': self.e1.id, 'field_id': 'f:hr.employee:location',
                 'value': 'Line Lead'},
                {'emp_id': self.e1.id, 'field_id': 'f:hr.employee:barcode',
                 'value': 'HACK'},
            ])
        self.env.flush_all()
        # The GOOD half of the batch is not applied either: the rail raises
        # before anything is written, so there is no half-done apply and no
        # audit row to explain one.
        self.assertEqual(self.e1.location, 'Operator')
        self.assertEqual(self.env['pb.records.apply'].search_count([]),
                         applies_before)
        with self.assertRaises(UserError):
            self.Desk.preview_changes(self.cfg.id, [
                {'emp_id': self.e1.id, 'field_id': 'f:res.partner:name',
                 'value': 'X'}])

    # =====================================================================
    # 9 — another company's employee is invisible and unwritable
    # =====================================================================
    def _second_company(self):
        """Another company to be outside of — created, borrowed, or neither.

        On the golden TEMPLATE database `res.company.create` raises
        `ValidationError: You must have at least an administrator user.`: that
        database is scrubbed of its administrator by construction, so the
        constraint that counts them has nothing to count and refuses the write
        that links the new company to its creator (RD18; W159 for the same fact
        met from the other side, `res.users.create`).

        The ladder is create → borrow an existing company → skip with the
        reason. Deleting the case was never an option: company scoping is a
        SECURITY rail, and it must keep being tested on every database that can
        test it. A skip says out loud which database cannot.
        """
        Company = self.env['res.company']
        try:
            with self.env.cr.savepoint():
                company = Company.create({'name': 'RD Other Co'})
                self.env.flush_all()
                return company
        except (ValidationError, UserError) as err:
            self.env.invalidate_all()
            reason = str(err)
        existing = Company.sudo().search([('id', '!=', self.company.id)], limit=1)
        if existing:
            return existing
        self.skipTest(
            "This database refuses res.company.create (%s) and has only one "
            "company, so the company-scoping case has nothing to be outside "
            "of. Run it on a database with an active administrator." % reason)
        return Company

    def test_09_company_scoping_hides_and_refuses(self):
        other = self._second_company()
        stranger = self.Employee.create({
            'name': 'RD Stranger', 'company_id': other.id})
        # `res.company.create` LINKS the new company to whoever created it
        # (base/models/res_company.py:311), so a test about not seeing another
        # company has to stop being in it first.
        self.env.user.write({'company_ids': [(3, other.id)]})
        self.env.user.invalidate_recordset(['company_ids'])
        self.assertNotIn(other.id, self.env.companies.ids)

        listed = self.Desk.search_people(self.cfg.id, {}, [])
        self.assertNotIn(stranger.id, [r['id'] for r in listed['rows']])
        self.assertNotIn(stranger.id, self.Desk.matching_ids({}))

        res = self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': stranger.id, 'field_id': 'f:hr.employee:location',
             'value': 'Line Lead'}])
        self.assertEqual(res['written'], 0)
        self.assertIn('not in the companies', res['refused'][0]['why'])
        self.assertFalse(stranger.location)

    # =====================================================================
    # 10 — a quarter of a thousand people page correctly
    # =====================================================================
    def test_10_paging_over_250_people(self):
        crowd = self.Employee.create([
            {'name': 'RD Crowd %03d' % i, 'company_id': self.company.id,
             'department_id': self.dept_b.id}
            for i in range(250)])
        filters = {'employee_ids': crowd.ids}
        first = self.Desk.search_people(self.cfg.id, filters,
                                        ['f:hr.employee:location'], 0, 100)
        self.assertEqual(first['total'], 250)
        self.assertEqual(len(first['rows']), 100)
        second = self.Desk.search_people(self.cfg.id, filters, [], 100, 100)
        third = self.Desk.search_people(self.cfg.id, filters, [], 200, 100)
        self.assertEqual(len(second['rows']), 100)
        self.assertEqual(len(third['rows']), 50)
        seen = ([r['id'] for r in first['rows']] + [r['id'] for r in second['rows']]
                + [r['id'] for r in third['rows']])
        self.assertEqual(len(set(seen)), 250)
        # The chips are counted for the MATCH SET, not the page — so they come
        # back with the first page and are not recomputed as the window moves
        # (RD11: counting them was 99% of a 147-second page fetch on 4,533
        # people). Asking for them explicitly gives the same answer.
        self.assertIsNone(second['facets'])
        self.assertIsNone(third['facets'])
        again = self.Desk.search_people(self.cfg.id, filters, [], 200, 100,
                                        with_facets=True)
        self.assertEqual(first['facets']['departments'],
                         again['facets']['departments'])
        self.assertEqual(len(self.Desk.matching_ids(filters)), 250)

    # =====================================================================
    # 11 — no payslip is touched
    # =====================================================================
    def test_11_payslips_are_never_touched_by_the_desk(self):
        before = self._payslip_fingerprint()
        self.Desk.get_schemes()
        self.Desk.get_fields(self.cfg.id)
        self.Desk.search_people(self.cfg.id, {}, ['f:hr.contract:shuipart'])
        self.Desk.preview_changes(self.cfg.id, [
            {'emp_id': self.e1.id, 'field_id': 'f:hr.contract:shuipart',
             'value': 'NO'}])
        res = self.Desk.apply_changes(self.cfg.id, [
            {'emp_id': self.e1.id, 'field_id': 'f:hr.contract:shuipart',
             'value': 'NO'},
            {'emp_id': self.e1.id, 'field_id': 'c:RDBONUS', 'value': '1000'},
            {'emp_id': self.e1.id, 'field_id': 'b:acc_number', 'value': '99887766'},
        ])
        self.Desk.undo_apply(res['apply_id'])
        self.Desk.get_history()
        self.env.flush_all()
        self.assertEqual(self._payslip_fingerprint(), before)

    # =====================================================================
    # 12 — no user-visible string says the wrong word
    # =====================================================================
    #: The pictograph planes, plus anything explicitly presented as an emoji
    #: with a variation selector. Deliberately NOT "the whole symbol block":
    #: `✕` (U+2715) is a close button and `→` is an arrow, and a rule that
    #: fails on those only teaches the next engineer to delete the rule (RD5).
    EMOJI = re.compile(
        '[\U0001F000-\U0001FAFF\U00002600-\U000027BF️]')
    SAFE_SYMBOLS = set('←→↑↓·✕—–≤≥⌘')

    def _strings_of(self, source, is_xml):
        if is_xml:
            body = re.sub(r'<!--.*?-->', ' ', source, flags=re.S)
            body = re.sub(r'^\s*<\?xml[^>]*\?>', ' ', body)
            return body
        return '\n'.join(re.sub(r'(?<!["\'])#.*$', '', line)
                         for line in source.splitlines())

    def test_12a_no_user_visible_string_names_the_engine(self):
        for parts, is_xml in (
                (('static', 'src', 'xml', 'records_desk.xml'), True),
                (('models', 'pb_records_desk.py'), False),
                (('models', 'pb_records_change.py'), False),
                (('views', 'pb_records_action.xml'), True)):
            body = self._strings_of(_src('pb_records', *parts), is_xml)
            if is_xml:
                # `<odoo>` is the document element, not a label (RD5).
                body = re.sub(r'</?odoo>', ' ', body)
            self.assertNotIn('Odoo', body, "user-visible string in %s" % parts[-1])
            self.assertNotIn('odoo.com', body)

    def test_12b_no_emoji_anywhere_on_the_surface(self):
        for parts in (('static', 'src', 'xml', 'records_desk.xml'),
                      ('static', 'src', 'js', 'records_desk.js'),
                      ('static', 'src', 'js', 'records_grid.js'),
                      ('static', 'src', 'js', 'records_cells.js'),
                      ('models', 'pb_records_desk.py')):
            body = _src('pb_records', *parts)
            found = [ch for ch in self.EMOJI.findall(body)
                     if ch not in self.SAFE_SYMBOLS]
            self.assertFalse(found, "emoji %r in %s" % (found, parts[-1]))

    def test_12c_the_lens_icon_is_one_the_rail_knows(self):
        palette = _src('pb_records', 'static', 'src', 'js', 'records_palette.js')
        self.assertIn('icon: "database"', palette)
