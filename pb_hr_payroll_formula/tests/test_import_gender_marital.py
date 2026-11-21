# -*- coding: utf-8 -*-
"""IMPORT-GENDER — a Gender or Marital Status cell must never fail the row.

`_coerce_mapped_value`'s selection branch called `field.selection(record.env)`.
On Odoo 19 `hr.employee.sex` / `hr.employee.marital` live on the version and
are RELATED fields, whose selection is `lambda model: …`; handed an
Environment it raised "'Environment' object has no attribute 'env'" and the
line loop failed the WHOLE row — payslip included. Rize's current schemes map
both columns, so every updating import of their Vietnam and India files would
have failed (found by MANAGERCOL, ledger G43).

Pinned here: the coercion itself (Rize's own spellings, case, an unknown word,
the model-fields row shape, a method-name selection, a Vietnamese label), and
a full `action_process` on a scheme shaped like Rize's — file first, records
second — that must process every row, make the payslip and set the boxes.
Everything runs on records this transaction creates.
"""
import json

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestImportGenderMarital(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Config = cls.env['hr.formula.config']
        cls.Rule = cls.env['hr.formula.rule']
        cls.Mapping = cls.env['hr.payslip.import.mapping']
        cls.Employee = cls.env['hr.employee']
        cls.Contract = cls.env['hr.contract']
        # Same reason as RECORDS R1: these cases are about what processing a
        # file DOES, so the fixture publishes "No approval needed".
        for key in ('runonly', 'loads'):
            cls.env['biz.approval.seed'].sudo().set_no_approval_needed(
                cls.env.company, key)

    # ------------------------------------------------------------ helpers
    def _f(self, model, name):
        # Fetched through a method: a Field bound to a class attribute is a
        # descriptor and would hand back a VALUE, not the field.
        return self.env[model]._fields[name]

    def _row(self, model, name):
        return self.env['ir.model.fields'].search(
            [('model', '=', model), ('name', '=', name)], limit=1)

    def _coerce(self, record, field, value):
        return self.Batch._coerce_mapped_value(record, field, value)

    # =====================================================================
    # Coercion
    # =====================================================================
    def test_01_rize_spellings_coerce_on_the_employee(self):
        emp = self.Employee.create({'name': 'IG Coerce'})
        sex = self._f('hr.employee', 'sex')
        marital = self._f('hr.employee', 'marital')
        self.assertTrue(callable(sex.selection),
                        "precondition: the employee's Gender is a related "
                        "selection on this build")
        self.assertEqual(self._coerce(emp, sex, 'Male'), 'male')
        self.assertEqual(self._coerce(emp, sex, 'Female'), 'female')
        self.assertEqual(self._coerce(emp, sex, '  FEMALE '), 'female')
        self.assertEqual(self._coerce(emp, marital, 'Single'), 'single')
        self.assertEqual(self._coerce(emp, marital, 'Married'), 'married')
        self.assertEqual(self._coerce(emp, marital, 'married'), 'married')

    def test_02_unknown_word_is_refused_not_raised(self):
        emp = self.Employee.create({'name': 'IG Unknown'})
        self.assertIsNone(self._coerce(emp, self._f('hr.employee', 'sex'), 'Prefer not'))
        self.assertIsNone(self._coerce(emp, self._f('hr.employee', 'marital'), 'Engaged'))

    def test_03_model_fields_row_shape(self):
        """`_get_mapping_updates` hands over an `ir.model.fields` row."""
        emp = self.Employee.create({'name': 'IG Row'})
        self.assertEqual(self._coerce(emp, self._row('hr.employee', 'sex'), 'Female'), 'female')
        self.assertEqual(self._coerce(emp, self._row('hr.employee', 'marital'), 'Married'), 'married')

    def test_04_method_name_selection(self):
        """`hr.version.marital` itself is declared by method NAME (a str)."""
        version = self.Employee.create({'name': 'IG Version'}).version_id
        field = self._f('hr.version', 'marital')
        self.assertIsInstance(field.selection, str,
                              "precondition: hr.version.marital is a method name")
        self.assertEqual(self._coerce(version, field, 'Married'), 'married')

    def test_05_vietnamese_label_while_working_in_english(self):
        emp = self.Employee.create({'name': 'IG Viet'}).with_context(lang='en_US')
        sex = self._f('hr.employee', 'sex')
        installed = dict(self.env['res.lang'].get_installed())
        if 'vi_VN' not in installed:
            self.skipTest("Vietnamese is not switched on in this database")
        vi = dict(sex._description_selection(emp.with_context(lang='vi_VN').env))
        if vi.get('female') == 'Female':
            self.skipTest("Gender labels are not translated into Vietnamese here")
        self.assertEqual(self._coerce(emp, sex, vi['female']), 'female')
        self.assertEqual(self._coerce(emp, sex, vi['male'].upper()), 'male')

    # =====================================================================
    # A whole import, shaped like Rize's current schemes
    # =====================================================================
    def _scheme(self):
        cfg = self.Config.create({
            'name': 'IG Scheme', 'code': 'IGSCHEME', 'country_code': 'VN',
            'state': 'active',
            # Rize Vietnam's order (India's is excel,records,api): the FILE
            # outranks the record, so the cell is what gets written.
            'source_priority': 'api,excel,records',
        })
        rules = {}
        for seq, (code, name, header, field) in enumerate((
                ('IGGENDER', 'Gender', 'Gender', 'sex'),
                ('IGMARITAL', 'Marital Status', 'Marital Status', 'marital'),
        ), start=1):
            rule = self.Rule.create({
                'config_id': cfg.id, 'name': name, 'code': code,
                'column_type': 'input', 'sequence': seq, 'default_value': 0.0,
                'value_kind': 'text', 'appears_on_payslip': False,
            })
            self.env['hr.formula.rule.source'].create({
                'rule_id': rule.id, 'kind': 'excel', 'key': header,
                'origin': 'user'})
            self.Mapping.create({
                'salary_structure_id': cfg.id, 'component_id': rule.id,
                'destination_type': 'field',
                'target_model_id': self.env['ir.model']._get('hr.employee').id,
                'target_field_id': self._row('hr.employee', field).id,
            })
            rules[field] = rule
        wage = self.Rule.create({
            'config_id': cfg.id, 'name': 'Basic pay', 'code': 'IGBASIC',
            'column_type': 'input', 'sequence': 3, 'default_value': 0.0})
        self.env['hr.formula.rule.source'].create({
            'rule_id': wage.id, 'kind': 'excel', 'key': 'Basic Pay',
            'origin': 'user'})
        return cfg

    def _person(self, code):
        emp = self.Employee.create({'name': 'IG %s' % code,
                                    'identification_id': code})
        ctype = self.env['hr.contract.type'].search([], limit=1) \
            or self.env['hr.contract.type'].create({'name': 'IG Type'})
        self.Contract.create({
            'name': 'IG %s Contract' % code, 'employee_id': emp.id,
            'wage': 1000.0, 'state': 'open', 'date_start': '2026-01-01',
            'type_id': ctype.id,
            'resource_calendar_id': (emp.resource_calendar_id.id
                                     or self.env.company.resource_calendar_id.id),
        })
        return emp

    def test_06_full_import_rows_succeed_and_set_the_boxes(self):
        cfg = self._scheme()
        cases = [
            # (code, Gender cell, Marital Status cell, expected sex, expected marital)
            ('IGA001', 'Female', 'Married', 'female', 'married'),
            ('IGA002', 'Male', 'Single', 'male', 'single'),
            ('IGA003', 'Female', None, 'female', 'single'),   # blank keeps the record
            ('IGA004', 'male', 'MARRIED', 'male', 'married'),
        ]
        people = {}
        for code, *_rest in cases:
            people[code] = self._person(code)
        self.assertFalse(any(p.sex for p in people.values()),
                         "precondition: nobody has a Gender yet")
        batch = self.Batch.create({
            'name': 'IG batch', 'source_type': 'excel',
            'formula_config_id': cfg.id, 'payroll_period': 'custom',
            'date_from': '2026-03-01', 'date_to': '2026-03-31',
            'create_payslips': True, 'payslip_state': 'draft',
            'one_time': False,
        })
        for i, (code, gender, marital, _s, _m) in enumerate(cases, start=1):
            row = {'Employee Code': code, 'Employee Name': people[code].name,
                   'Gender': gender, 'Marital Status': marital,
                   'Basic Pay': 1000.0}
            self.env['hr.payroll.import.line'].create({
                'batch_id': batch.id, 'sequence': i,
                'raw_data_json': json.dumps(row),
                'employee_code': code, 'employee_name': people[code].name,
                'state': 'validated',
            })
        batch.state = 'validated'
        batch.action_process()
        self.env.flush_all()

        errors = batch.import_line_ids.filtered(lambda l: l.state != 'processed')
        self.assertFalse(
            errors, "rows failed: %s" % errors.mapped('error_message'))
        for code, _g, _m, sex, marital in cases:
            line = batch.import_line_ids.filtered(lambda l: l.employee_code == code)
            self.assertEqual(line.employee_id, people[code],
                             "%s matched the wrong person" % code)
            self.assertTrue(line.payslip_id, "%s got no payslip" % code)
            people[code].invalidate_recordset()
            self.assertEqual(people[code].sex, sex, "%s Gender" % code)
            self.assertEqual(people[code].marital, marital, "%s Marital" % code)
