from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase
from unittest.mock import patch


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

    def test_public_cannot_create_enquiries_directly(self):
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            self.env['biztinct.contact'].with_user(public).create({
                'name': 'Blocked', 'email': 'website-qa@example.invalid',
                'message': 'Blocked', 'website_id': self.contact.website_id.id,
            })
