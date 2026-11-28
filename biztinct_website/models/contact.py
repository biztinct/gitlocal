from html import escape

from odoo import fields, models


class BiztinctContact(models.Model):
    _name = 'biztinct.contact'
    _description = 'Biztinct website enquiry'
    _order = 'create_date desc, id desc'

    name = fields.Char(required=True)
    email = fields.Char(required=True)
    company = fields.Char()
    phone = fields.Char()
    interest = fields.Char()
    message = fields.Text(required=True)
    website_id = fields.Many2one('website', required=True, ondelete='restrict')
    source_hash = fields.Char(index=True, groups='base.group_system')
    mail_id = fields.Many2one('mail.mail', readonly=True, ondelete='set null')
    notification_queued = fields.Boolean(readonly=True, default=False)
    notification_state = fields.Selection(related='mail_id.state', readonly=True)

    def _queue_notifications(self):
        """Save enquiries immediately; queue delivery only after SMTP is configured.

        A dedicated server and fixed recipient prevent visitor-supplied routing.
        The standard mail queue handles delivery independently of HTTP requests.
        Row locks prevent duplicate notifications from concurrent cron runs.
        """
        server = self.env.ref('biztinct_website.gmail_server', raise_if_not_found=False)
        if not server or not server.active or not server.smtp_pass:
            return
        self.flush(['notification_queued'])
        self.env.cr.execute(
            'SELECT id FROM biztinct_contact WHERE notification_queued = false '
            'ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED'
        )
        contacts = self.browse([row[0] for row in self.env.cr.fetchall()])
        for contact in contacts:
            details = [('Name', contact.name), ('Email', contact.email),
                       ('Company', contact.company), ('Phone', contact.phone),
                       ('Interested in', contact.interest)]
            body = '<h2>New Biztinct website enquiry</h2>' + ''.join(
                '<p><strong>%s:</strong> %s</p>' % (label, escape(value or '—'))
                for label, value in details
            )
            body += '<hr/><p>%s</p>' % escape(contact.message).replace('\n', '<br/>')
            mail = self.env['mail.mail'].sudo().create({
                'subject': 'Biztinct enquiry: %s' % contact.name.replace('\n', ' '),
                'email_from': 'Biztinct Website <ash@biztinct.com>',
                'email_to': 'ash@biztinct.com',
                'reply_to': contact.email,
                'body_html': body,
                'mail_server_id': server.id,
                'auto_delete': False,
            })
            contact.write({'mail_id': mail.id, 'notification_queued': True})

    def _process_notifications(self):
        """Deliver only this site's mail without releasing any historic backlog."""
        server = self.env.ref('biztinct_website.gmail_server', raise_if_not_found=False)
        if not server or not server.active or not server.smtp_pass:
            return
        self._queue_notifications()
        self.env['mail.mail'].sudo().search([
            ('mail_server_id', '=', server.id), ('state', '=', 'outgoing'),
        ], limit=100).send()
