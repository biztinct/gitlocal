from lxml import etree
from odoo.tests import TransactionCase, tagged, new_test_user, Form
from odoo.addons.pb_form_studio_people.models.premium_section import project_job_form, project_section_form, JOB_FIELDS, SECTIONS


@tagged('post_install', '-at_install')
class TestPremiumJobSection(TransactionCase):
    def test_chart_uses_premium_navigation_only_in_job_workspace(self):
        model = self.env['hr.employee']
        original = model.get_view(view_type='form')['arch']
        native = etree.fromstring(original).xpath("//field[@name='child_ids'][@widget='hr_org_chart']")
        if not native:
            self.skipTest('Native organisation chart is not installed')
        premium = etree.fromstring(model.get_view(view_type='form', pb_workspace_section='job')['arch'])
        chart = premium.xpath("//section//field[@name='child_ids']")
        self.assertEqual(len(chart), 1)
        self.assertEqual(chart[0].get('widget'), 'pb_premium_org_chart')
        self.assertEqual({k: v for k, v in chart[0].attrib.items() if k != 'widget'},
                         {k: v for k, v in native[0].attrib.items() if k != 'widget'})
        self.assertEqual(model.get_view(view_type='form')['arch'], original)

    def test_live_arch_preserves_field_behaviour_and_full_details(self):
        model = self.env['hr.employee']
        normal = model.get_view(view_type='form')['arch']
        section = model.get_view(view_type='form', pb_workspace_section='job')['arch']
        original, compact = etree.fromstring(normal), etree.fromstring(section)
        self.assertFalse(compact.xpath('//header | //sheet | //notebook | //chatter'))
        for name in JOB_FIELDS:
            candidates = original.xpath(".//field[@name=$name][not(ancestor::field)]", name=name)
            projected = compact.xpath(".//section//field[@name=$name]", name=name)
            if candidates:
                self.assertEqual(len(projected), 1, name)
                attrs = dict(projected[0].attrib); attrs.pop('id', None)
                self.assertIn(attrs, [{k:v for k,v in n.attrib.items() if k != 'id'} for n in candidates])
            else:
                self.assertFalse(projected)
        self.assertEqual(model.get_view(view_type='form')['arch'], normal)
        self.assertTrue(set(compact.xpath('.//field/@name')) <=
                        set(original.xpath('.//field[not(ancestor::field)]/@name')))
        self.assertFalse(compact.xpath("//field[@name='vn_dependent_ids']"))
        self.assertTrue(compact.xpath("//field[@name='company_id']"))

    def test_ancestor_visibility_and_renamed_label(self):
        xml = '''<form js_class="hr_employee_form"><field name="company_id" invisible="1"/>
          <group invisible="not company_id" groups="hr.group_hr_user"><field name="department_id"
          string="Team" domain="[('company_id', '=', company_id)]" context="{'default_company_id': company_id}"
          readonly="not active" required="active" options="{'no_create': True}"/></group>
          <field name="active" invisible="1"/></form>'''
        root = etree.fromstring(project_job_form(xml, ('Role', 'Workplace')))
        field = root.xpath("//section//field[@name='department_id']")[0]
        self.assertEqual(field.get('readonly'), 'not active')
        self.assertEqual(field.get('required'), 'active')
        self.assertEqual(field.get('context'), "{'default_company_id': company_id}")
        self.assertEqual(field.get('domain'), "[('company_id', '=', company_id)]")
        self.assertTrue(field.xpath("ancestor::div[@invisible='not company_id'][@groups='hr.group_hr_user']"))
        self.assertEqual(root.xpath('//label/@string'), ['Team'])
        self.assertFalse(root.xpath("//field[@name='job_id']"))

    def test_hr_without_payroll_can_read_change_and_save_job(self):
        hr = new_test_user(self.env, 'premium_job_hr',
                           groups='base.group_user,hr.group_hr_manager')
        employee = self.env['hr.employee'].create({'name': 'Premium job regression'})
        model = self.env['hr.employee'].with_user(hr)
        arch = model.get_view(view_type='form', pb_workspace_section='job')['arch']
        names = set(etree.fromstring(arch).xpath('//field/@name'))
        self.assertNotIn('vn_dependent_ids', names)
        record = employee.with_user(hr)
        self.assertTrue(record.web_read({name: {} for name in names}))
        view = self.env['ir.ui.view'].create({'name': 'Premium job regression section',
                                             'model': 'hr.employee', 'arch': arch})
        job = self.env['hr.job'].create({'name': 'Premium job test role'})
        with Form(record, view=view) as form:
            form.job_id = job
            self.assertEqual(form.job_title, job.name)
            form.job_title = 'Premium custom title'
        self.assertEqual(employee.job_title, 'Premium custom title')
        self.assertEqual(employee.job_id, job)

    def test_personal_keeps_native_rules_and_upload_filename_dependency(self):
        model = self.env['hr.employee']
        original = etree.fromstring(model.get_view(view_type='form')['arch'])
        root = etree.fromstring(model.get_view(view_type='form', pb_workspace_section='personal')['arch'])
        self.assertFalse(root.xpath('//header | //sheet | //notebook | //chatter'))
        for name in ('private_state_id', 'private_country_id', 'marital', 'spouse_complete_name', 'passport_expiration_date', 'has_work_permit'):
            native = original.xpath('.//field[@name=$name][not(ancestor::field)]', name=name)
            projected = root.xpath('.//section//field[@name=$name]', name=name)
            if native:
                self.assertEqual(len(projected), 1, name)
                attrs = dict(projected[0].attrib); attrs.pop('id', None)
                self.assertIn(attrs, [{k:v for k,v in n.attrib.items() if k != 'id'} for n in native])
        if root.xpath("//field[@name='has_work_permit']"):
            self.assertTrue(root.xpath("//field[@name='work_permit_name']"))
        self.assertFalse(root.xpath("//field[@name='bank_account_ids' or @name='vn_dependent_ids']"))

    def test_personal_hr_save_and_cancel_use_employee_record(self):
        hr = new_test_user(self.env, 'premium_personal_hr', groups='base.group_user,hr.group_hr_manager')
        employee = self.env['hr.employee'].create({'name': 'Premium personal regression'})
        model = self.env['hr.employee'].with_user(hr)
        arch = model.get_view(view_type='form', pb_workspace_section='personal')['arch']
        names = set(etree.fromstring(arch).xpath('//field[not(ancestor::field)]/@name'))
        self.assertTrue(employee.with_user(hr).web_read({name: {} for name in names}))
        view = self.env['ir.ui.view'].create({'name': 'Premium personal regression section', 'model': 'hr.employee', 'arch': arch})
        with Form(employee.with_user(hr), view=view) as form:
            form.private_email = 'premium-test@example.invalid'
            form.emergency_contact = 'Emergency test contact'
        self.assertEqual(employee.private_email, 'premium-test@example.invalid')
        self.assertEqual(employee.emergency_contact, 'Emergency test contact')
        form = Form(employee.with_user(hr), view=view)
        form.private_email = 'discarded@example.invalid'
        # Form edits are virtual until save, like the native relational model.
        self.assertEqual(employee.private_email, 'premium-test@example.invalid')

    def test_missing_cards_and_forbidden_sections_are_not_synthesised(self):
        root = etree.fromstring(project_section_form('<form><field name="private_email"/></form>', SECTIONS['personal']))
        self.assertEqual(len(root.xpath('//section')), 1)
        self.assertEqual(root.xpath('//section//field/@name'), ['private_email'])
        model = self.env['hr.employee']
        self.assertEqual(model.get_view(view_type='form', pb_workspace_section='unknown')['arch'], model.get_view(view_type='form')['arch'])

    def test_pay_keeps_available_fields_without_loading_forbidden_collections(self):
        hr = new_test_user(self.env, 'premium_pay_hr', groups='base.group_user,hr.group_hr_manager')
        model = self.env['hr.employee'].with_user(hr)
        root = etree.fromstring(model.get_view(view_type='form', pb_workspace_section='pay')['arch'])
        for name in root.xpath('.//field[not(ancestor::field)]/@name'):
            field = model._fields[name]
            if field.type in ('one2many', 'many2many'):
                self.assertTrue(model.env[field.comodel_name].has_access('read'), name)
        self.assertTrue(root.xpath(".//section//field[@name='payroll_country']"))
        self.assertFalse(root.xpath(".//field[@name='bank_account_ids']"))
