from odoo import api, fields, models


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

    @api.model
    def _search(self, args, offset=0, limit=None, order=None, count=False,
                access_rights_uid=None):
        if self.env.context.get('biztinct_smtp_default'):
            args = list(args) + [('biztinct_contact_only', '=', False)]
        return super()._search(args, offset=offset, limit=limit, order=order,
                               count=count, access_rights_uid=access_rights_uid)

    def connect(self, host=None, port=None, user=None, password=None, encryption=None,
                smtp_debug=False, mail_server_id=None):
        if not mail_server_id and not host:
            self = self.with_context(biztinct_smtp_default=True)
        return super(IrMailServer, self).connect(
            host=host, port=port, user=user, password=password, encryption=encryption,
            smtp_debug=smtp_debug, mail_server_id=mail_server_id)
