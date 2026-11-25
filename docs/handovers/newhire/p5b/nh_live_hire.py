# NEWHIRE P5b L4 on LIVE payobook ONLY (demo database; demo data welcome, name starts "DEMO"): send ONE
# hire through the studio's own server call (`pb.new.hire.send`, what "Add <name>" on step 7 calls), as the
# QA login, in the demo company, then read back what was made. The browser could not be used for this on
# payobook.com (see the report). odoo-bin shell; commits only the hire itself.
assert env.cr.dbname == 'payobook', 'payobook only'
QA = 6672
u = env['res.users'].browse(QA)
assert u.exists() and u.login.startswith('qa.'), 'not the QA login'
NAME = 'DEMO NH P5b Live Check'
assert not env['hr.employee'].sudo().with_context(active_test=False).search_count([('name', '=', NAME)]), 'already sent'
draft = {'name': NAME, 'date_start': '2026-12-01', 'department_id': 130, 'job_id': 67,
         'payroll_country': 'VN', 'wage': 12000000, 'contract_kind': 'permanent', 'trial_on': True}
Studio = env['pb.new.hire'].with_user(u).with_context(allowed_company_ids=[5], lang='en_US')
res = Studio.send(draft)
env.cr.commit()
print('PROBE send', {k: res.get(k) for k in ('ok', 'state', 'applied', 'employee_id', 'contract_id', 'message', 'reference', 'name')})
e = env['hr.employee'].sudo().browse(res.get('employee_id') or 0)
out = ['employee %s company %s country_of_work %s team %s job %s trial_end %s' % (
    e.id, e.company_id.name, e.payroll_country, e.department_id.name, e.job_id.name, e.trial_date_end)]
for c in e.contract_ids:
    out.append('contract %s state %s wage %s country %s currency %s' % (
        c.id, c.state, c.wage, c.payroll_country, c.currency_id.name if 'currency_id' in c._fields else ''))
out.append('journey cases %s' % [(x.id, x.state) for x in env['pb.journey.case'].sudo().search([('employee_id', '=', e.id)])])
docs = env['pb.employee.document'].sudo().search([('employee_id', '=', e.id)]) if 'pb.employee.document' in env else []
out.append('papers %s' % [(d.name, d.attachment_id.mimetype if 'attachment_id' in d._fields else '',
                           d.attachment_id.file_size if 'attachment_id' in d._fields else 0) for d in docs])
out.append('asks %s' % env['pb.new.hire.ask'].sudo().search_count([('employee_id', '=', e.id)]))
if 'pb.asset.request' in env:
    out.append('equipment requests %s' % env['pb.asset.request'].sudo().search_count([('employee_id', '=', e.id)]))
out.append('mail queued for the person %s' % env['mail.mail'].sudo().search_count([('state', '=', 'outgoing'), ('create_date', '>=', e.create_date)]))
print('PROBE ' + ' | '.join(out))
