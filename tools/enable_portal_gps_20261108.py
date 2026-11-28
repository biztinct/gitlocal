"""Apply the owner's 8 Nov 2026 GPS setting request from an Odoo shell.

Run only for payobook and rize, with PORTAL_GPS_APPLY=20261108. A dry run is
otherwise the default. The exact approved active companies are checked before
writing. The existing setting also records browser and IP information; the
owner was informed before approving these two tenants. No attendance is changed.
"""
import json
import os

TARGETS = {
    'rize': {1: 'Rize Farms'},
    'payobook': {1: 'Your Company', 2: 'Payobook',
                 5: 'Payobook Vietnam JSC', 6: 'Payobook Singapore Pte Ltd'},
}


def apply(env):
    database = env.cr.dbname
    if database not in TARGETS:
        raise ValueError('This change is approved only for payobook and rize.')
    companies = env['res.company'].sudo().search([('active', '=', True)], order='id')
    actual = {company.id: company.name for company in companies}
    if actual != TARGETS[database]:
        raise ValueError('Company scope changed; review the deployment plan first.')
    before = {company.id: bool(company.attendance_device_tracking) for company in companies}
    applied = os.environ.get('PORTAL_GPS_APPLY') == '20261108'
    if applied:
        companies.write({'attendance_device_tracking': True})
        env.cr.commit()
        companies.invalidate_recordset(['attendance_device_tracking'])
        if not all(companies.mapped('attendance_device_tracking')):
            raise RuntimeError('GPS setting verification failed.')
    result = {'database': database, 'companies': actual, 'before': before,
              'attendance_device_tracking': True, 'applied': applied}
    print('PORTAL_GPS_RESULT=' + json.dumps(result))
    return result


if 'env' in globals():
    apply(env)
