from lxml import etree
from odoo.tests import tagged
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.pb_contracts.tests.test_cd4_approval import TestCd4ContractApproval
from odoo.addons.pb_contracts.models.pb_contract_360 import _TERMS


@tagged('post_install', '-at_install', 'premium_workspace')
class TestPremiumContract(TestCd4ContractApproval):
    def test_all_native_contract_fields_have_a_premium_home(self):
        model = self.env['hr.contract'].with_user(self.hr)
        source = etree.fromstring(model.get_view(view_type='form')['arch'])
        agreement = etree.fromstring(model.get_view(view_type='form', pb_workspace_section='agreement')['arch'])
        covered = set(agreement.xpath('.//section//field[not(ancestor::field)]/@name'))
        covered.update(row[1] for row in _TERMS)
        covered.update(('advantages_ids', 'state'))  # Components and status/actions.
        visible = {n.get('name') for n in source.xpath('.//field[not(ancestor::field)]')
                   if not any(a.get('invisible') in ('1', 'True', 'true') for a in [n, *n.iterancestors()])}
        self.assertFalse({n for n in visible - covered if not n.startswith('x_pbfs_')})

    def test_native_save_holds_pay_until_the_existing_route_approves(self):
        contract = self.contract.with_user(self.hr).with_company(self.company).with_context(pb_premium_record=True)
        before = self.contract.wage
        result = contract.web_save({'wage': before + 100, 'name': 'Workspace reference'}, {'name': {}, 'wage': {}})
        self.assertEqual(result[0]['wage'], before)
        self.assertEqual(result[0]['name'], 'Workspace reference')
        proposal = self.Proposal.sudo().search([], order='id desc', limit=1)
        self.assertEqual(proposal.payload()['terms']['wage'], before + 100)
        self._approve_all(proposal.approval_request_id)
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.wage, before + 100)

    def test_invalid_component_does_not_partially_save_reference(self):
        before = self.contract.name
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.contract.with_user(self.hr).with_company(self.company).with_context(pb_premium_record=True).web_save(
                {'name': 'Must not land', 'advantages_ids': [(1, -999, {'amount': 42})]}, {'name': {}})
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.name, before)

    def test_component_cannot_be_linked_from_another_contract(self):
        with self.assertRaises(AccessError):
            self.contract._workspace_components([(4, -999)])

    def test_component_definition_change_requires_component_tool(self):
        with self.assertRaises(ValidationError):
            self.contract._workspace_components([(1, 1, {'advantage_template_id': 99})])

    def test_agreement_native_controls_and_original_form_preserved(self):
        model = self.env['hr.contract'].with_user(self.hr)
        original = model.get_view(view_type='form')['arch']
        root = etree.fromstring(model.get_view(view_type='form', pb_workspace_section='agreement')['arch'])
        self.assertFalse(root.xpath('//header | //sheet | //notebook | //chatter'))
        for name in ('name', 'employee_id', 'structure_type_id', 'notes'):
            self.assertTrue(root.xpath('.//section//field[@name=$name]', name=name), name)
        self.assertFalse(root.xpath(".//section//field[@name='wage' or @name='advantages_ids']"))
        self.assertEqual(original, model.get_view(view_type='form')['arch'])

    def test_agreement_structure_type_uses_existing_approval(self):
        contract = self.contract.with_user(self.hr).with_company(self.company).with_context(pb_premium_record=True)
        model = self.env['hr.payroll.structure.type']
        other = model.create({'name': 'Premium agreement structure type'})
        before = self.contract.structure_type_id
        contract.web_save({'structure_type_id': other.id}, {'structure_type_id': {'fields': {'display_name': {}}}})
        self.assertEqual(self.contract.structure_type_id, before)
        proposal = self.Proposal.sudo().search([], order='id desc', limit=1)
        self.assertEqual(proposal.payload()['terms']['structure_type_id'], other.id)
        self._approve_all(proposal.approval_request_id)
        self.contract.invalidate_recordset()
        self.assertEqual(self.contract.structure_type_id, other)
