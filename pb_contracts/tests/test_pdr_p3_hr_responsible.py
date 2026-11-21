# -*- coding: utf-8 -*-
"""PDR P3 F1 — HR Responsible is no longer required on the full contract form.

The standard contract form wrote `required="1"` on `hr_responsible_id`; the
field itself is optional. Every rize Indonesia contract lacks it, so every
save from the full form was refused ("Complete the required fields: HR
Responsible"). The field stays on the form, optional.
"""

from lxml import etree

from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install', 'pdr_p3')
class TestPdrP3HrResponsible(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.view = cls.env.ref('hr_contract.hr_contract_view_form')
        cls.Contract = cls.env['hr.contract']
        cls.company = cls.env.company
        cls.employee = cls.env['hr.employee'].create(
            {'name': 'PDR P3 No HR Responsible', 'company_id': cls.company.id})

    def _field_node(self):
        arch = self.Contract.get_view(self.view.id, 'form')['arch']
        nodes = etree.fromstring(arch).xpath("//field[@name='hr_responsible_id']")
        self.assertTrue(nodes, 'HR Responsible must stay on the form')
        return nodes[0]

    def test_p3_f1_field_shown_and_not_required(self):
        node = self._field_node()
        self.assertNotIn(node.get('required'), ('1', 'True', 'true'),
                         'the full contract form still demands HR Responsible')
        self.assertNotIn(node.get('invisible'), ('1', 'True', 'true'))
        self.assertFalse(self.Contract._fields['hr_responsible_id'].required)

    def test_p3_f1_new_contract_saves_without_hr_responsible(self):
        with Form(self.Contract, view=self.view) as form:
            form.name = 'PDR P3 F1 new'
            form.employee_id = self.employee
            form.wage = 1500.0
            form.hr_responsible_id = self.env['res.users']
        contract = form.record
        self.assertTrue(contract.id)
        self.assertFalse(contract.hr_responsible_id)

    def test_p3_f1_existing_contract_edits_without_hr_responsible(self):
        contract = self.Contract.create({
            'name': 'PDR P3 F1 existing', 'employee_id': self.employee.id,
            'wage': 1000.0, 'company_id': self.company.id})
        contract.hr_responsible_id = False
        with Form(contract, view=self.view) as form:
            form.wage = 2000.0
        self.assertEqual(contract.wage, 2000.0)
        self.assertFalse(contract.hr_responsible_id)
