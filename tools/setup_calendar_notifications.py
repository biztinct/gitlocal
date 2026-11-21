"""Run in the payobook Odoo shell after deploying the notification addon.

Configuration is deliberately database-specific; clones must remain disabled.
This script never reads or prints OAuth credentials.
"""
import json

assert env.cr.dbname == 'payobook', 'Only payobook.com is authorized for live Google notifications'
params = env['ir.config_parameter'].sudo()
params.set_param('pb_calendar.google_push_database', 'payobook')
params.set_param('pb_calendar.google_push_origin', 'https://payobook.com')
cron = env.ref('pb_hiring.cron_google_calendar_notifications')
cron.sudo().write({'active': True, 'interval_number': 1, 'interval_type': 'minutes'})
env.cr.commit()
print('CALENDAR_PUSH_SETUP=' + json.dumps({'database': env.cr.dbname,
    'callback': env['pb.calendar.google.channel']._callback(), 'worker_minutes': 1,
    'recovery_minutes': 60, 'enabled': True}))
