"""Use an optional, editable company template for password resets only."""
import contextlib
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class Company(models.Model):
    _inherit = 'res.company'

    pb_reset_password_template_id = fields.Many2one(
        'mail.template', string='Password reset email template', copy=False,
        domain=[('model', '=', 'res.users')], groups='base.group_system')

    @api.constrains('pb_reset_password_template_id')
    def _check_reset_template(self):
        for company in self:
            if company.pb_reset_password_template_id and company.pb_reset_password_template_id.model != 'res.users':
                raise ValidationError(_('Choose an email template for Users.'))


class Users(models.Model):
    _inherit = 'res.users'

    def _action_reset_password(self, signup_type='reset'):
        if (signup_type != 'reset' or self.env.context.get('create_user')
                or self.env.context.get('install_mode') or self.env.context.get('import_file')):
            return super()._action_reset_password(signup_type=signup_type)
        if not any(u.company_id.sudo().pb_reset_password_template_id for u in self):
            return super()._action_reset_password(signup_type=signup_type)
        if any(not u.active for u in self):
            raise UserError(_('You cannot reset the password of an archived user.'))
        for user in self:
            if not user.email:
                raise UserError(_('Cannot send email: user %s has no email address.', user.name))
        for user in self:
            template = user.company_id.sudo().pb_reset_password_template_id
            if not template:
                super(Users, user)._action_reset_password(signup_type=signup_type)
                continue
            # Native reset delivery rolls back transient mail rows, not the reset state.
            user.partner_id.signup_prepare(signup_type=signup_type)
            with contextlib.closing(self.env.cr.savepoint()):
                template.with_context(lang=user.lang or self.env.lang or 'en_US').send_mail(
                    user.id, force_send=True, raise_exception=True, email_values={
                        'email_to': user.email, 'email_cc': False, 'recipient_ids': [],
                        'partner_ids': [], 'auto_delete': True, 'scheduled_date': False,
                        'message_type': 'user_notification',
                    })
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Notification'), 'message': _('A reset password link was sent by email'),
            'sticky': False}}
