from lxml import etree
from odoo.tests import TransactionCase, tagged
from odoo.addons.pb_form_studio_people.models.premium_section import project_job_form, JOB_FIELDS


@tagged('post_install', '-at_install')
class TestPremiumJobSection(TransactionCase):
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
        self.assertEqual(set(original.xpath('.//field[not(ancestor::field)]/@name')),
                         set(compact.xpath('.//field[not(ancestor::field)]/@name')))

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
