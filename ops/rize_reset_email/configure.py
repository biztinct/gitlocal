"""Run in an Odoo shell on rize only; set APPLY_RIZE_RESET_EMAIL=1 to save.
Place template.html beside this file. Does not send email or alter SMTP activation.
"""
import json
import os
from pathlib import Path

assert env.cr.dbname == 'rize'
company = env['res.company'].browse(1).exists()
assert company.name == 'Rize Farms'
server = company.pb_outgoing_mail_server_id
was_active = server.active
body = Path(os.environ['RIZE_RESET_TEMPLATE_PATH']).read_text()
xmlid = 'pb_settings.rize_reset_password_email'
template = env.ref(xmlid, raise_if_not_found=False)
values = {'name': 'Rize HRMS - Password reset', 'model_id': env['ir.model']._get_id('res.users'),
          'subject': 'Rize HRMS - Password reset', 'email_from': 'support@payobook.com',
          'reply_to': 'support@payobook.com', 'body_html': body,
          'auto_delete': True, 'lang': '{{ object.lang }}'}
if template:
    template.write(values)
else:
    template = env['mail.template'].create(values)
    env['ir.model.data'].create({'module': 'pb_settings', 'name': 'rize_reset_password_email',
        'model': 'mail.template', 'res_id': template.id, 'noupdate': True})
company.write({'email': 'support@payobook.com', 'pb_reset_password_template_id': template.id})
user = env['res.users'].search([('login', '=', 'ash@biztinct.com')])
assert len(user) == 1 and user.email == 'ash@biztinct.com'
rendered = template._render_field('body_html', user.ids)[user.id]
assert 'support@payobook.com' in rendered and '#2563EB' in rendered
assert 'ash@biztinct.com' not in rendered
assert template._render_field('subject', user.ids)[user.id] == values['subject']
assert server.active == was_active
applied = os.getenv('APPLY_RIZE_RESET_EMAIL') == '1'
if applied:
    env.cr.commit()
else:
    env.cr.rollback()
print(json.dumps({'applied': applied, 'template_id': template.id, 'company_email': 'support@payobook.com',
                  'render_verified': True, 'smtp_activation_preserved': True}))
