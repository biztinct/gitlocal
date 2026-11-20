from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install')
class TestOutgoingEmail(TransactionCase):
    def test_tenant_can_configure_own_server_without_raw_access(self):
        role = self.env.ref('pb_vendor_access.role_tenant_administrator', raise_if_not_found=False)
        if not role:
            self.skipTest('Tenant role module not installed')
        company = self.env['res.company'].create({'name':'Email tenant test'})
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Tenant mail test','login':'tenant_mail_test','company_id':company.id,
            'company_ids':[(6,0,[company.id,self.env.company.id])],
            'group_ids':[(6,0,[self.env.ref('base.group_user').id])]})
        self.env['pb.role.assignment'].create({'user_id':user.id,'profile_id':role.id})
        model = self.env['pb.company.mail.settings'].with_user(user).with_context(allowed_company_ids=[self.env.company.id])
        defaults = model.default_get(['company_name','enabled','smtp_pass'])
        self.assertEqual(defaults['company_name'],company.name)
        self.assertFalse(defaults['enabled'])
        wizard = model.create({'name':'Tenant SMTP','smtp_host':'smtp.example.invalid','smtp_port':465,
            'smtp_encryption':'ssl','smtp_user':'support@example.invalid','smtp_pass':'test-only',
            'from_filter':'support@example.invalid'})
        wizard.action_save()
        server = company.pb_outgoing_mail_server_id
        self.assertTrue(server)
        self.assertFalse(server.active)
        self.assertFalse(wizard.smtp_pass)
        mail_model = self.env['ir.mail_server'].with_company(company)
        selected, sender = mail_model._find_mail_server('person@different.example', mail_servers=server)
        self.assertFalse(selected)  # Inactive stays excluded from delivery.
        server.active = True
        selected, sender = mail_model._find_mail_server('person@different.example', mail_servers=server)
        self.assertEqual(selected, server)
        self.assertEqual(sender, 'support@example.invalid')
        server.active = False
        self.assertFalse(model.default_get(['smtp_pass']).get('smtp_pass'))
        self.assertTrue(model.default_get(['password_saved'])['password_saved'])
        with self.assertRaises(AccessError):
            server.with_user(user).read(['smtp_pass'])
        gate = self.env['pb.settings'].with_user(user).resolve_gates([
            {'key':'email','groups':['base.group_system'],'cards':[{'id':'email','xmlid':'pb_settings.action_outgoing_email'}]}])
        self.assertTrue(gate['categories']['email'])
        self.assertTrue(gate['cards']['email:email'])

    def test_regular_user_and_forged_payload_cannot_configure_mail(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Mail permission test','login':'mail_permission_test',
            'group_ids':[(6,0,[self.env.ref('base.group_user').id])]})
        model = self.env['pb.company.mail.settings'].with_user(user)
        with self.assertRaises(AccessError):
            model.default_get(['smtp_host'])
        wizard = model.browse(1)  # A forged RPC target must fail before reading or writing it.
        with self.assertRaises(AccessError):
            wizard.action_save()
        with self.assertRaises(AccessError):
            wizard.action_test()
        result = self.env['pb.settings'].with_user(user).resolve_gates([
            {'key':'email','groups':[], 'cards':[{'id':'email','xmlid':'pb_settings.action_outgoing_email'}]}])
        self.assertFalse(result['categories']['email'])
        self.assertFalse(result['cards']['email:email'])
