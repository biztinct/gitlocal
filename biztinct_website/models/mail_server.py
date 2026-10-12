import smtplib
import ssl
import threading

from odoo import _, api, fields, models
from odoo.addons.base.models.ir_mail_server import SMTP_TIMEOUT
from odoo.exceptions import UserError


class IrMailServer(models.Model):
    _inherit = 'ir.mail_server'

    biztinct_contact_only = fields.Boolean(
        string='Only for Biztinct contact enquiries', default=False,
        help='Excluded from automatic default-server selection. Website enquiries '
             'explicitly select this server, so existing mail is not sent through it.')

    def _get_test_email_addresses(self):
        self.ensure_one()
        if self.biztinct_contact_only:
            # The existing admin profile still contains a placeholder email.
            # Probe the actual mailbox instead; no message is sent by the test.
            return 'ash@biztinct.com', 'ash@biztinct.com'
        return super()._get_test_email_addresses()

    def write(self, values):
        result = super().write(values)
        connection_fields = {'smtp_pass', 'smtp_user', 'smtp_host', 'smtp_port', 'smtp_encryption'}
        if connection_fields.intersection(values) or values.get('active'):
            ready = self.filtered(lambda server: server.biztinct_contact_only
                                  and server.active and server.smtp_pass)
            if ready:
                # Retry only saved website notifications after a configuration
                # correction, never the unrelated historical mail backlog.
                contacts = self.env['biztinct.contact'].sudo().search([
                    ('mail_id.mail_server_id', 'in', ready.ids),
                    ('mail_id.state', '=', 'exception'),
                ])
                contacts.mapped('mail_id').write({'state': 'outgoing', 'failure_reason': False})
        return result

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False,
                access_rights_uid=None):
        if self.env.context.get('biztinct_smtp_default'):
            args = list(args) + [('biztinct_contact_only', '=', False)]
        return super()._search(args, offset=offset, limit=limit, order=order,
                               count=count, access_rights_uid=access_rights_uid)

    def connect(self, host=None, port=None, user=None, password=None, encryption=None,
                smtp_debug=False, mail_server_id=None):
        if getattr(threading.current_thread(), 'testing', False):
            return None
        server = self.sudo().browse(mail_server_id).exists() if mail_server_id else self.browse()
        if server and server.biztinct_contact_only and server.smtp_host.lower() == 'smtp.gmail.com':
            return server._connect_biztinct_gmail()
        if not mail_server_id and not host:
            self = self.with_context(biztinct_smtp_default=True)
        return super(IrMailServer, self).connect(
            host=host, port=port, user=user, password=password, encryption=encryption,
            smtp_debug=smtp_debug, mail_server_id=mail_server_id)

    def _connect_biztinct_gmail(self):
        """Keep Google's authentication error instead of retrying another mechanism.

        Python's generic login retries LOGIN after a rejected PLAIN exchange.
        Gmail may close that session, masking the original credential rejection.
        One LOGIN exchange preserves the result and does not log credentials.
        """
        self.ensure_one()
        context = ssl.create_default_context()
        connection = None
        try:
            if self.smtp_encryption == 'ssl':
                connection = smtplib.SMTP_SSL(
                    self.smtp_host, self.smtp_port, timeout=SMTP_TIMEOUT,
                    local_hostname='biztinct.com', context=context)
            elif self.smtp_encryption == 'starttls':
                connection = smtplib.SMTP(
                    self.smtp_host, self.smtp_port, timeout=SMTP_TIMEOUT,
                    local_hostname='biztinct.com')
                connection.starttls(context=context)
            else:
                raise UserError(_('For Gmail, select TLS (STARTTLS) on port 587 '
                                  'or SSL/TLS on port 465.'))
            connection.ehlo_or_helo_if_needed()
            connection.user = self.smtp_user
            connection.password = self.smtp_pass or ''
            connection.auth('LOGIN', connection.auth_login, initial_response_ok=False)
            return connection
        except smtplib.SMTPAuthenticationError as error:
            if connection:
                connection.close()
            raise UserError(_(
                'Gmail rejected the saved username or password (SMTP %(code)s). '
                'Enter a new 16-letter Google App Password generated while signed '
                'into ash@biztinct.com, then save and test again. Your normal '
                'Gmail password will not work. If ash@biztinct.com is an alias, '
                'use the primary Google account address as the SMTP username.'
            ) % {'code': error.smtp_code}) from error
        except Exception:
            if connection:
                connection.close()
            raise
