from lxml import etree
from odoo.tests import TransactionCase, tagged, new_test_user
from odoo.exceptions import AccessError
from odoo.addons.pb_form_studio_people.models.premium_section import SECTIONS


def visible_fields(root):
    return {n.get('name') for n in root.xpath('.//field[not(ancestor::field)]')
            if not any(a.get('invisible') in ('1', 'True', 'true')
                       for a in [n, *n.iterancestors()])}


@tagged('post_install', '-at_install', 'premium_completion')
class TestWorkspaceCompletion(TransactionCase):
    def test_multi_company_employee_field_is_available(self):
        self.env.user.group_ids |= self.env.ref('base.group_multi_company')
        root = etree.fromstring(self.env['hr.employee'].get_view(view_type='form', pb_workspace_section='job')['arch'])
        self.assertIn('company_id', visible_fields(root))

    def test_settings_widget_dependencies_are_sent_to_the_browser(self):
        result = self.env['hr.employee'].get_views([(False, 'form')], {'pb_workspace_section': 'settings'})
        root = etree.fromstring(result['views']['form']['arch'])
        fields = result['models']['hr.employee']['fields']
        self.assertIn('display_name', fields)
        self.assertTrue(root.xpath("//field[@name='display_name']"))
        self.assertTrue(root.xpath("//div[@class='pb-record-report-links']//button"))
        self.assertFalse(root.xpath("//div[@name='button_box']"))

    def test_employee_field_and_action_coverage(self):
        model = self.env['hr.employee']
        native = etree.fromstring(model.get_view(view_type='form')['arch'])
        roots = [etree.fromstring(model.get_view(view_type='form', pb_workspace_section=s)['arch'])
                 for s in SECTIONS]
        covered = set().union(*(visible_fields(root) for root in roots))
        # Profile already shows the contract salary. Form-builder fields have
        # their own Company details editor and save/approval path.
        missing = {n for n in visible_fields(native) - covered
                   if n != 'pb_profile_contract_pay' and not n.startswith('x_pbfs_')}
        self.assertFalse(missing, sorted(missing))
        native_actions = set(native.xpath('.//button[not(ancestor::field)]/@name'))
        premium_actions = set().union(*(set(r.xpath('.//button[not(ancestor::field)]/@name')) for r in roots))
        self.assertFalse(native_actions - premium_actions, native_actions - premium_actions)

    def test_work_addresses_exclude_people_and_include_offices(self):
        company = self.env.company
        person = self.env['res.partner'].create({'name': 'Ordinary employee contact',
                                                'parent_id': company.partner_id.id})
        office = self.env['res.partner'].create({'name': 'Branch office', 'type': 'other',
                                                'parent_id': company.partner_id.id})
        domain = self.env['hr.employee']._pb_work_address_domain()
        allowed = self.env['res.partner'].search(domain)
        self.assertIn(company.partner_id, allowed)
        self.assertIn(office, allowed)
        self.assertNotIn(person, allowed)
        self.assertEqual(self.env['hr.employee'].fields_get(['address_id'])['address_id']['domain'], domain)

    def test_manage_users_is_admin_only_without_granting_rights(self):
        employee = self.env['hr.employee'].create({'name': 'Workspace test employee'})
        officer = new_test_user(self.env, 'premium_completion_officer', groups='base.group_user,hr.group_hr_user')
        with self.assertRaises(AccessError):
            employee.with_user(officer).action_pb_manage_hr_users()
        arch = etree.fromstring(employee.with_user(officer).get_view(view_type='form', pb_workspace_section='job')['arch'])
        self.assertFalse(arch.xpath("//button[@name='action_pb_manage_hr_users']"))
        action = employee.action_pb_manage_hr_users()
        self.assertEqual(action['res_model'], 'res.users')
        self.assertEqual(action['target'], 'current')

    def test_bank_behaviour_and_country_rules_are_preserved(self):
        model = self.env['hr.employee']
        native = etree.fromstring(model.get_view(view_type='form')['arch'])
        pay = etree.fromstring(model.get_view(view_type='form', pb_workspace_section='pay')['arch'])
        for field in pay.xpath("//section//field[@name='bank_account_ids']"):
            self.assertIn(dict(field.attrib), [dict(n.attrib) for n in native.xpath("//field[@name='bank_account_ids']")])
        for name in ('vn_payroll_insurance_summary', 'vn_payroll_tax_summary'):
            if native.xpath('//field[@name=$name]', name=name):
                node = pay.xpath('//section//field[@name=$name]', name=name)[0]
                self.assertTrue(any('VN' in (a.get('invisible') or '') for a in [node, *node.iterancestors()]))
