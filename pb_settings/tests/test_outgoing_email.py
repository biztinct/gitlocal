from ast import literal_eval
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged('post_install', '-at_install')
class TestOutgoingEmail(TransactionCase):
    def test_admin_ui_includes_inactive_and_defaults_inactive(self):
        action = self.env.ref('pb_settings.action_outgoing_email')
        context = literal_eval(action.context)
        self.assertFalse(context['active_test'])
        self.assertFalse(context['default_active'])
        server = self.env['ir.mail_server'].with_context(**context).create({
            'name':'Inactive UI test', 'smtp_host':'smtp.example.invalid'})
        self.assertFalse(server.active)
        self.assertNotIn(server, self.env['ir.mail_server'].search([]))
        self.assertIn(server, self.env['ir.mail_server'].with_context(**context).search([]))

    def test_regular_user_cannot_read_smtp_credentials(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Mail permission test','login':'mail_permission_test',
            'group_ids':[(6,0,[self.env.ref('base.group_user').id])]})
        server = self.env['ir.mail_server'].create({'name':'Restricted', 'smtp_host':'smtp.example.invalid', 'active':False})
        with self.assertRaises(AccessError):
            server.with_user(user).read(['smtp_pass'])
        result = self.env['pb.settings'].with_user(user).resolve_gates([
            {'key':'email','groups':[], 'cards':[{'id':'email','xmlid':'pb_settings.action_outgoing_email'}]}])
        self.assertFalse(result['categories']['email'])
        self.assertFalse(result['cards']['email:email'])
