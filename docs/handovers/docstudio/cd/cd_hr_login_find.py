# DOCSTUDIO close-out D: existing internal logins on payobook that are HR-officer level (HR officer,
# no payroll role, not a settings administrator). Read-only. Prints ids and role flags only.
def p(*a): print('PROBE', *a)
G = {k: env.ref(x, raise_if_not_found=False) for k, x in {
    'hr_user': 'hr.group_hr_user', 'hr_manager': 'hr.group_hr_manager',
    'pay_officer': 'pb_hr_payroll_base.group_payroll_base_officer',
    'pay_manager': 'om_hr_payroll.group_hr_payroll_manager',
    'system': 'base.group_system', 'erp_manager': 'base.group_erp_manager'}.items()}
users = env['res.users'].sudo().search([('share', '=', False), ('active', '=', True), ('id', '>', 2)], order='id')
n = 0
for u in users:
    ag = u.all_group_ids
    flags = {k: bool(g and g in ag) for k, g in G.items()}
    if flags['hr_user'] and not flags['pay_officer'] and not flags['pay_manager'] and not flags['system']:
        n += 1
        if n <= 12:
            p(u.id, u.login.split('@')[-1], 'hr_manager', flags['hr_manager'], 'erp_manager', flags['erp_manager'],
              'companies', u.company_ids.ids, 'last login', bool(u.login_date), 'lang', u.lang)
p('HR-officer-level logins', n)
env.cr.rollback()
