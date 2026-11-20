from pathlib import Path
from unittest.mock import patch
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from odoo.addons.auth_signup.models.res_users import ResUsers as NativeUsers


@tagged('post_install', '-at_install')
class TestResetPasswordTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Reset template test'})
        cls.user = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Reset recipient', 'login': 'reset-test@example.invalid',
            'email': 'reset-test@example.invalid', 'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])]})
        cls.template = cls.env['mail.template'].create({
            'name': 'Company reset', 'model_id': cls.env['ir.model']._get_id('res.users'),
            'subject': 'Rize HRMS - Password reset', 'email_from': 'support@payobook.com',
            'body_html': '<p>Reset for <t t-out="object.name"/></p>'})
        cls.company.pb_reset_password_template_id = cls.template

    def test_reset_targets_only_requested_user_and_raises_delivery_errors(self):
        with patch.object(type(self.template), 'send_mail', return_value=1) as send:
            result = self.user._action_reset_password()
        self.assertEqual(result['tag'], 'display_notification')
        send.assert_called_once()
        self.assertEqual(send.call_args.args, (self.user.id,))
        self.assertTrue(send.call_args.kwargs['raise_exception'])
        self.assertTrue(send.call_args.kwargs['force_send'])
        values = send.call_args.kwargs['email_values']
        self.assertEqual(values['email_to'], self.user.email)
        self.assertFalse(values['email_cc'])
        self.assertEqual(values['recipient_ids'], [])
        self.assertEqual(values['partner_ids'], [])
        self.assertEqual(self.user.partner_id.signup_type, 'reset')

    def test_standard_reset_without_configuration(self):
        self.company.pb_reset_password_template_id = False
        with patch.object(NativeUsers, '_action_reset_password', return_value='native') as native:
            self.assertEqual(self.user._action_reset_password(), 'native')
            native.assert_called_once_with(signup_type='reset')

    def test_invitation_and_install_keep_native_behavior(self):
        for ctx, kind in [({'create_user': True}, 'signup'), ({'install_mode': True}, 'reset'), ({'import_file': True}, 'reset')]:
            with patch.object(NativeUsers, '_action_reset_password', return_value='native') as native:
                self.assertEqual(self.user.with_context(**ctx)._action_reset_password(signup_type=kind), 'native')
                native.assert_called_once_with(signup_type=kind)

    def test_archived_user_never_sends(self):
        self.user.active = False
        with patch.object(type(self.template), 'send_mail') as send:
            with self.assertRaises(UserError):
                self.user._action_reset_password()
            send.assert_not_called()

    def test_non_user_template_rejected(self):
        self.template.model_id = self.env['ir.model']._get_id('res.partner')
        with self.assertRaises(ValidationError):
            self.company._check_reset_template()
