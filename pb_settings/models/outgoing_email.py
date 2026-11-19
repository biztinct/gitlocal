"""Tenant-owned outgoing email setup, without access to raw server credentials."""
import smtplib
import ssl
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError, UserError


def may_manage_email(env):
    if env.user.has_group('base.group_system'):
        return True
    role = env.ref('pb_vendor_access.role_tenant_administrator', raise_if_not_found=False)
    return bool(role and role.sudo().active and role.sudo().membership_group_id
                and role.sudo().membership_group_id in env.user.sudo().all_group_ids)


class Company(models.Model):
    _inherit = 'res.company'
    pb_outgoing_mail_server_id = fields.Many2one('ir.mail_server', copy=False, groups='base.group_system')


class OutgoingEmailSettings(models.TransientModel):
    _name = 'pb.company.mail.settings'
    _description = 'Your outgoing email server'

    company_name = fields.Char(readonly=True)
    name = fields.Char('Server name', required=True)
    smtp_host = fields.Char('SMTP server', required=True)
    smtp_port = fields.Integer('Port', default=465, required=True)
    smtp_encryption = fields.Selection([('ssl','SSL/TLS'),('starttls','STARTTLS')], string='Encryption', default='ssl', required=True)
    smtp_user = fields.Char('Email / username', required=True)
    smtp_pass = fields.Char('New password', help='Leave blank to keep the saved password. The saved password is never displayed.')
    password_saved = fields.Boolean(readonly=True)
    from_filter = fields.Char('Allowed sender email', required=True)
    enabled = fields.Boolean('Active — allow outgoing email', default=False)

    def _company(self):
        if not may_manage_email(self.env):
            raise AccessError(_('Only a Tenant Administrator or Platform Administrator can configure outgoing email.'))
        return self.env.user.company_id.sudo()

    @api.model
    def default_get(self, names):
        result = super().default_get(names)
        company = self._company()
        server = company.pb_outgoing_mail_server_id
        values = {'company_name':company.name, 'name':company.name+' — outgoing email', 'enabled':False}
        if server:
            values.update({key:server[key] for key in ('name','smtp_host','smtp_port','smtp_encryption','smtp_user','from_filter')})
            values.update(enabled=server.active, password_saved=bool(server.smtp_pass))
        result.update({k:v for k,v in values.items() if k in names})
        return result

    def _values(self):
        self.ensure_one()
        company = self._company()
        if not self.smtp_host or not self.smtp_user or not self.from_filter:
            raise ValidationError(_('Enter the SMTP server, username and sender email.'))
        if not 1 <= self.smtp_port <= 65535 or self.smtp_encryption not in ('ssl','starttls'):
            raise ValidationError(_('Use an encrypted SMTP connection with a valid port.'))
        password = self.smtp_pass or company.pb_outgoing_mail_server_id.smtp_pass
        if not password:
            raise ValidationError(_('Enter the email server password.'))
        return {'name':self.name, 'smtp_host':self.smtp_host.strip(), 'smtp_port':self.smtp_port,
                'smtp_encryption':self.smtp_encryption, 'smtp_authentication':'login',
                'smtp_user':self.smtp_user.strip(), 'smtp_pass':password,
                'from_filter':self.from_filter.strip(), 'active':self.enabled}

    def action_save(self):
        company = self._company()
        values = self._values()
        server = company.pb_outgoing_mail_server_id
        if server:
            server.write(values)
        else:
            server = self.env['ir.mail_server'].sudo().create(values)
            company.pb_outgoing_mail_server_id = server
        self.smtp_pass = False
        return {'type':'ir.actions.act_window_close'}

    def action_test(self):
        values = self._values()
        try:
            context = ssl.create_default_context()
            if values['smtp_encryption'] == 'ssl':
                connection = smtplib.SMTP_SSL(values['smtp_host'], values['smtp_port'], timeout=15, context=context)
            else:
                connection = smtplib.SMTP(values['smtp_host'], values['smtp_port'], timeout=15)
                connection.ehlo()
                connection.starttls(context=context)
            with connection:
                connection.ehlo()
                connection.login(values['smtp_user'], values['smtp_pass'])
        except (OSError, smtplib.SMTPException):
            raise UserError(_('Connection or sign-in failed. Check the SMTP settings and password. No email was sent.')) from None
        return {'type':'ir.actions.client','tag':'display_notification','params':{
            'title':_('Connection successful'), 'message':_('Encrypted sign-in passed. No email was sent and activation was not changed.'), 'type':'success'}}
