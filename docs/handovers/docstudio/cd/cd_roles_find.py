# DOCSTUDIO close-out D: which Access-screen roles give HR-officer level (hr.group_hr_user, implied
# included) without a payroll role, and which give contract read without document filing. Read-only.
def p(*a): print('PROBE', *a)
hr = env.ref('hr.group_hr_user'); hrm = env.ref('hr.group_hr_manager')
pay = env.ref('pb_hr_payroll_base.group_payroll_base_officer'); paym = env.ref('om_hr_payroll.group_hr_payroll_manager')
Doc = env['ir.model.access']
def closure(groups):
    return groups | groups.all_implied_ids if 'all_implied_ids' in groups._fields else groups | groups.trans_implied_ids
for pr in env['pb.role.profile'].sudo().search([('active', '=', True)], order='id'):
    g = closure(pr.group_ids)
    acc = lambda model, mode: bool(env['ir.model.access'].sudo().search_count([
        ('model_id.model', '=', model), ('active', '=', True), ('perm_' + mode, '=', True),
        '|', ('group_id', '=', False), ('group_id', 'in', (g | env.ref('base.group_user')).ids)]))
    flags = dict(hr=hr in g, hrm=hrm in g, pay=pay in g, paym=paym in g,
                 contract_read=acc('hr.contract', 'read'), doc_create=acc('pb.employee.document', 'create'))
    if flags['hr'] or flags['contract_read']:
        p(pr.id, pr.name, ' '.join('%s=%s' % kv for kv in flags.items()))
env.cr.rollback()
