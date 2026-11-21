from odoo.tests import tagged
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.pb_contracts.tests.test_cd4_approval import TestCd4ContractApproval


@tagged('post_install', '-at_install', 'premium_workspace')
class TestPremiumContract(TestCd4ContractApproval):
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
