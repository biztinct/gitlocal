from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase
from unittest.mock import patch
import smtplib
import ssl

from odoo.exceptions import UserError


class TestContactNotifications(TransactionCase):
    def setUp(self):
        super().setUp()
        self.server = self.env.ref('biztinct_website.gmail_server')
        self.server.write({'active': False, 'smtp_pass': False})
        self.contact = self.env['biztinct.contact'].create({
            'name': 'Website QA <name>',
            'email': 'website-qa@example.invalid',
            'message': '<script>alert(1)</script>\nA test enquiry.',
            'company': '<b>Example</b>',
            'interest': 'Custom software',
            'website_id': self.env['website'].search([], limit=1).id,
        })

    def test_unconfigured_server_keeps_enquiry(self):
        self.env['biztinct.contact']._queue_notifications()
        self.assertTrue(self.contact.exists())
        self.assertFalse(self.contact.mail_id)
        self.assertFalse(self.contact.notification_queued)

    def test_password_without_activation_does_not_queue(self):
        self.server.smtp_pass = 'qa-placeholder-never-transmitted'
        self.env['biztinct.contact']._queue_notifications()
        self.assertFalse(self.contact.notification_queued)

    def test_activation_without_password_does_not_queue(self):
        self.server.active = True
        self.env['biztinct.contact']._queue_notifications()
        self.assertFalse(self.contact.notification_queued)

    def test_notification_has_fixed_destination_and_safe_content(self):
        self.server.write({'active': True, 'smtp_pass': 'qa-placeholder-never-transmitted'})
        self.env['biztinct.contact']._queue_notifications()
        mail = self.contact.mail_id
        self.assertTrue(mail)
        self.assertEqual(mail.email_to, 'ash@biztinct.com')
        self.assertEqual(mail.email_from, 'Biztinct Website <ash@biztinct.com>')
        self.assertEqual(mail.reply_to, 'website-qa@example.invalid')
        self.assertEqual(mail.mail_server_id, self.server)
        self.assertIn('&lt;script&gt;', mail.body_html)
        self.assertNotIn('<script>', mail.body_html)
        self.assertIn('&lt;b&gt;Example&lt;/b&gt;', mail.body_html)
        self.assertTrue(self.contact.notification_queued)

    def test_notification_is_queued_once(self):
        self.server.write({'active': True, 'smtp_pass': 'qa-placeholder-never-transmitted'})
        self.env['biztinct.contact']._queue_notifications()
        first = self.contact.mail_id
        self.env['biztinct.contact']._queue_notifications()
        self.assertEqual(self.contact.mail_id, first)

    def test_public_cannot_read_enquiries(self):
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            self.contact.with_user(public).read(['name', 'email', 'message'])

    def test_contact_server_is_excluded_from_default_selection(self):
        self.server.active = True
        servers = self.env['ir.mail_server'].with_context(biztinct_smtp_default=True)
        self.assertFalse(servers.search([('id', '=', self.server.id)]))
        self.assertEqual(self.env['ir.mail_server'].search([('id', '=', self.server.id)]),
                         self.server)

    def test_delivery_manager_only_sends_website_notifications(self):
        self.server.write({'active': True, 'smtp_pass': 'qa-placeholder-never-transmitted'})
        unrelated = self.env['mail.mail'].create({
            'subject': 'Unrelated QA message', 'email_from': 'qa@example.invalid',
            'email_to': 'unrelated@example.invalid', 'body_html': '<p>Not website mail</p>',
        })
        with patch.object(type(self.env['mail.mail']), 'send', autospec=True) as send:
            self.env['biztinct.contact']._process_notifications()
            records = send.call_args[0][0]
            self.assertIn(self.contact.mail_id, records)
            self.assertNotIn(unrelated, records)

    def test_connection_probe_uses_the_actual_mailbox(self):
        self.assertEqual(self.server._get_test_email_addresses(),
                         ('ash@biztinct.com', 'ash@biztinct.com'))

    def test_other_servers_keep_the_standard_connection_probe(self):
        other = self.env['ir.mail_server'].create({
            'name': 'QA unrelated SMTP', 'smtp_host': 'localhost', 'active': False,
        })
        admin = self.env.ref('base.user_admin')
        self.assertEqual(other.with_user(admin)._get_test_email_addresses(),
                         (admin.email, 'noreply@odoo.com'))

    def test_public_cannot_create_enquiries_directly(self):
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            self.env['biztinct.contact'].with_user(public).create({
                'name': 'Blocked', 'email': 'website-qa@example.invalid',
                'message': 'Blocked', 'website_id': self.contact.website_id.id,
            })

    def test_gmail_uses_one_login_exchange_with_verified_starttls(self):
        self.server.write({'smtp_pass': 'qa-placeholder-never-transmitted',
                           'smtp_encryption': 'starttls', 'smtp_port': 587})
        with patch('odoo.addons.biztinct_website.models.mail_server.smtplib.SMTP') as factory:
            connection = factory.return_value
            result = self.server._connect_biztinct_gmail()
            self.assertIs(result, connection)
            context = connection.starttls.call_args[1]['context']
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            connection.auth.assert_called_once_with(
                'LOGIN', connection.auth_login, initial_response_ok=False)
            connection.login.assert_not_called()
            connection.set_debuglevel.assert_not_called()
            self.assertEqual(connection.user, 'ash@biztinct.com')
            connection.close.assert_not_called()

    def test_gmail_ssl_verifies_the_server_certificate(self):
        self.server.write({'smtp_pass': 'qa-placeholder-never-transmitted',
                           'smtp_encryption': 'ssl', 'smtp_port': 465})
        with patch('odoo.addons.biztinct_website.models.mail_server.smtplib.SMTP_SSL') as factory:
            connection = self.server._connect_biztinct_gmail()
            self.assertIs(connection, factory.return_value)
            context = factory.call_args[1]['context']
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
            connection.starttls.assert_not_called()

    def test_gmail_rejection_explains_app_password_without_exposing_it(self):
        self.server.smtp_pass = 'qa-placeholder-never-transmitted'
        with patch('odoo.addons.biztinct_website.models.mail_server.smtplib.SMTP') as factory:
            factory.return_value.auth.side_effect = smtplib.SMTPAuthenticationError(
                535, b'Username and Password not accepted')
            with self.assertRaises(UserError) as caught:
                self.server._connect_biztinct_gmail()
            self.assertIn('SMTP 535', str(caught.exception))
            self.assertIn('Google App Password', str(caught.exception))
            self.assertNotIn(self.server.smtp_pass, str(caught.exception))
            factory.return_value.auth.assert_called_once()
            factory.return_value.close.assert_called_once()

    def test_gmail_connection_failure_is_preserved_and_closed(self):
        with patch('odoo.addons.biztinct_website.models.mail_server.smtplib.SMTP') as factory:
            factory.return_value.starttls.side_effect = smtplib.SMTPServerDisconnected('Closed')
            with self.assertRaises(smtplib.SMTPServerDisconnected):
                self.server._connect_biztinct_gmail()
            factory.return_value.close.assert_called_once()
            factory.return_value.auth.assert_not_called()

    def test_gmail_requires_encryption(self):
        self.server.smtp_encryption = 'none'
        with patch('odoo.addons.biztinct_website.models.mail_server.smtplib.SMTP') as factory:
            with self.assertRaises(UserError):
                self.server._connect_biztinct_gmail()
            factory.assert_not_called()

    def test_credential_correction_retries_only_failed_website_mail(self):
        self.server.write({'active': True, 'smtp_pass': 'qa-placeholder-never-transmitted'})
        self.env['biztinct.contact']._queue_notifications()
        mail = self.contact.mail_id
        mail.write({'state': 'exception', 'failure_reason': 'Test authentication failure'})
        unrelated = self.env['mail.mail'].create({
            'subject': 'Unrelated QA failed mail', 'email_from': 'qa@example.invalid',
            'email_to': 'unrelated@example.invalid', 'body_html': '<p>Unrelated</p>',
            'state': 'exception', 'mail_server_id': self.server.id,
        })
        self.server.write({'smtp_pass': 'qa-corrected-placeholder-never-transmitted'})
        self.assertEqual(mail.state, 'outgoing')
        self.assertFalse(mail.failure_reason)
        self.assertEqual(unrelated.state, 'exception')
        self.assertEqual(self.contact.mail_id, mail)

    def test_unrelated_server_edit_does_not_retry_failed_mail(self):
        self.server.write({'active': True, 'smtp_pass': 'qa-placeholder-never-transmitted'})
        self.env['biztinct.contact']._queue_notifications()
        self.contact.mail_id.state = 'exception'
        self.server.write({'sequence': 20})
        self.assertEqual(self.contact.mail_id.state, 'exception')
