# -*- coding: utf-8 -*-
"""WDGAP DM1 — demo contracts for the Contracts "Renew" screen (payobook ONLY).

Owner ruling DM1 (2026-11-18): the demo world has no contract marked
Fixed-term or Permanent, so the Renew dialog's ready-filled boxes ("Kind of
contract (Vietnam)", "Payroll treatment (Vietnam)", W3-B RN1/RN3) always read
"Open-ended / Not set". This seed ADDS six demo people in the demo Vietnam
company, each with ONE running contract, paid by the demo Retail scheme
(`DEMO_RETAIL_END`, through the scheme map — they sit in a Retail cost-centre
department like the other Retail demo people):

  name                         kind          treatment   end
  DEMO Nguyễn Thu Hà           Fixed-term    Permanent   today + 35 days
  DEMO Trần Minh Quân          Fixed-term    Permanent   today + 50 days
  DEMO Lê Ngọc Lan             Fixed-term    Probation   today + 42 days
  DEMO Phạm Quang Huy          Fixed-term    (empty)     today + 55 days
  DEMO Võ Bích Yến             Seasonal      (empty)     today + 30 days
  DEMO Hoàng Đức Bảo           Open-ended    Permanent   (none)

Renew then shows (RN1: kind carried, never a trial; RN3: treatment carried
only when Permanent): Fixed-term/Permanent, Fixed-term/Permanent,
Fixed-term/Not set, Fixed-term/Not set, Seasonal/Not set, Open-ended/Permanent.

ADD-ONLY AND IDEMPOTENT. People are found by exact name in the demo company;
a person who exists is never written again, and a contract is made only for a
person of this seed who has none. A second run creates nothing. Every record
made is put on the demo register (`pb.demo.seed.register`, "DEMO HR programme
data") so Settings › Demo data can account for it.

No login, no email address (work or private), no bank details, no payslip, no
pay run. Contract start dates are all in the past and never inside the
current month (the joiner/leaver job reads only the current month). Anything
the run would queue to send, any new payslip or login, ABORTS the run with a
rollback — nothing is kept.

Run, service UP, on payobook ONLY (the script refuses any other database
except a local test copy named wdgap_dm1*):

    sudo -u odoo /odoo/odoo-server/odoo-bin shell -c /etc/odoo-server.conf \
        -d payobook --no-http < dm1_demo_seed.py

DM1_DRY=1 in the environment = do everything, print, then roll back.
Nothing here contains a password or a real person's data.
"""
import os
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import fields

SCHEME_CODE = 'DEMO_RETAIL_END'
LABEL = 'DEMO renewal contracts (WDGAP DM1)'
DRY = bool(os.environ.get('DM1_DRY'))

# (name, sex, job title, kind, treatment, end in days or None,
#  contract length in months, wage VND, employee category name)
PEOPLE = [
    ('DEMO Nguyễn Thu Hà', 'female', 'Store Supervisor', 'definite', 'permanent', 35, 12, 14500000, 'Permanent'),
    ('DEMO Trần Minh Quân', 'male', 'Senior Sales Associate', 'definite', 'permanent', 50, 24, 11800000, 'Permanent'),
    ('DEMO Lê Ngọc Lan', 'female', 'Sales Associate', 'definite', 'probation', 42, 3, 8200000, 'Permanent'),
    ('DEMO Phạm Quang Huy', 'male', 'Visual Merchandiser', 'definite', '', 55, 12, 10500000, 'Permanent'),
    ('DEMO Võ Bích Yến', 'female', 'Seasonal Sales Assistant', 'seasonal', '', 30, 4, 7600000, 'Seasonal'),
    ('DEMO Hoàng Đức Bảo', 'male', 'Store Manager', 'indefinite', 'permanent', None, 36, 21000000, 'Permanent'),
]
CTX = {'tracking_disable': True, 'mail_create_nolog': True,
       'mail_create_nosubscribe': True, 'mail_notrack': True,
       'active_test': False}


def say(msg, *args):
    print('DM1 SEED | ' + (msg % args if args else msg))


env = env  # noqa: F821 — provided by `odoo-bin shell`
db = env.cr.dbname
if db != 'payobook' and not db.startswith('wdgap_dm1'):
    raise SystemExit('DM1 SEED | refused: database %r is not payobook' % db)
env = env(context=dict(env.context, **CTX))


def counts():
    q = {
        'employees': 'SELECT count(*) FROM hr_employee',
        'contracts': 'SELECT count(*) FROM hr_contract',
        'payslips': 'SELECT count(*) FROM hr_payslip',
        'payslip_runs': 'SELECT count(*) FROM hr_payslip_run',
        'users': 'SELECT count(*) FROM res_users',
        'mail_queue_outgoing': "SELECT count(*) FROM mail_mail WHERE state = 'outgoing'",
        'mail_all': 'SELECT count(*) FROM mail_mail',
        'activities': 'SELECT count(*) FROM mail_activity',
        'crons_active': 'SELECT count(*) FROM ir_cron WHERE active',
    }
    out = {}
    for key, sql in q.items():
        env.cr.execute(sql)
        out[key] = env.cr.fetchone()[0]
    return out


before = counts()
say('before %s', before)

Config = env['hr.formula.config'].sudo()
scheme = Config.search([('code', '=', SCHEME_CODE)], limit=1)
if not scheme:
    raise SystemExit('DM1 SEED | no %s scheme here — nothing done' % SCHEME_CODE)
company = scheme.company_id
Employee = env['hr.employee'].sudo().with_company(company)
Contract = env['hr.contract'].sudo().with_company(company)

# THE TEMPLATE: an existing running contract of a demo person this scheme
# pays. Read, never written: the new people take its department, calendar
# and pay frequency so they sit exactly where the other Retail demo people do.
template_emp = Employee.search([
    ('company_id', '=', company.id), ('pb_paid_by_id', '=', scheme.id),
    ('is_demo', '=', True), ('active', '=', True),
], order='id', limit=1) if 'pb_paid_by_id' in Employee._fields else Employee.browse()
template = Contract.search([
    ('employee_id', '=', template_emp.id), ('state', '=', 'open'),
], order='id', limit=1) if template_emp else Contract.browse()
if not template:
    raise SystemExit('DM1 SEED | no running demo contract paid by %s — '
                     'nothing done' % SCHEME_CODE)
dept = template_emp.department_id
calendar = template.resource_calendar_id or company.resource_calendar_id
say('company %s (%s), scheme %s (%s), department %s, template contract %s',
    company.id, company.name, scheme.id, scheme.code, dept.display_name,
    template.id)

CT = env['hr.contract.type'].sudo()
today = fields.Date.context_today(Employee)
month_start = today.replace(day=1)
vn = env.ref('base.vn', raise_if_not_found=False)
emp_fields = Employee._fields
con_fields = Contract._fields
has_kind = 'vietnam_contract_type' in con_fields
has_treat = 'pb_payroll_contract_type' in con_fields
if not (has_kind and has_treat):
    raise SystemExit('DM1 SEED | the Vietnam contract kind / payroll '
                     'treatment fields are not on this database')

made_emp, made_con = Employee.browse(), Contract.browse()
for (name, sex, title, kind, treat, end_days, months, wage, cat_name) in PEOPLE:
    emp = Employee.search([('name', '=', name), ('company_id', '=', company.id)], limit=1)
    if not emp:
        vals = {'name': name, 'company_id': company.id,
                'department_id': dept.id, 'job_title': title}
        optional = {'sex': sex, 'country_id': vn.id if vn else False,
                    'is_demo': True, 'division': 'retail',
                    'subject_to_pit': 'YES',
                    'birthday': today - relativedelta(years=24 + len(name) % 17, days=40 * len(title))}
        for key, value in optional.items():
            if key in emp_fields and value:
                vals[key] = value
        emp = Employee.create(vals)
        made_emp |= emp
        say('person %s made: %s', emp.id, name)
    if Contract.search_count([('employee_id', '=', emp.id)]):
        continue
    if end_days is None:
        start = (today - relativedelta(months=months)).replace(day=1)
        end = False
    else:
        end = today + timedelta(days=end_days)
        start = end - relativedelta(months=months) + timedelta(days=1)
    if start >= month_start:          # never a joiner of the current month
        start = month_start - relativedelta(months=1)
    if 'date_of_joining' in emp_fields and not emp.date_of_joining:
        emp.write({'date_of_joining': start})
    category = CT.search([('name', '=', cat_name)], limit=1) or template.type_id
    cvals = {
        'name': 'Contract - %s' % name, 'employee_id': emp.id,
        'company_id': company.id, 'wage': wage, 'date_start': start,
        'date_end': end, 'state': 'open',
        'resource_calendar_id': calendar.id if calendar else False,
        'type_id': category.id if category else False,
        'vietnam_contract_type': kind,
        'pb_payroll_contract_type': treat or False,
    }
    for key in ('struct_id', 'structure_type_id', 'schedule_pay', 'costcenter'):
        if key in con_fields:
            value = template[key]
            cvals[key] = value.id if hasattr(value, 'id') else value
    if 'pb_trial_date_start' in con_fields and treat == 'probation':
        cvals['pb_trial_date_start'] = start
    con = Contract.create(cvals)
    made_con |= con
    say('contract %s made: %s | %s | %s → %s | kind %s | treatment %s',
        con.id, name, wage, start, end or 'no end', kind, treat or '(empty)')

# "Paid by" for the new people only (the scheme map's own bulk door).
if made_emp and hasattr(Employee, '_pb_recompute_paid_by'):
    Employee._pb_recompute_paid_by(employee_ids=made_emp.ids)

# Onto the demo register, so the demo-data panel accounts for them. People
# first, contracts after: the removal walks the register backwards, so a
# contract goes before the person it belongs to.
Seed = env.get('pb.demo.seed')
if Seed is not None and (made_emp or made_con):
    Seed.register(made_emp, LABEL)
    Seed.register(made_con, LABEL)

env.flush_all()
after = counts()
say('after  %s', after)

# THE RAILS: nothing sent, no payslip, no pay run, no login, no job switched.
problems = []
for key in ('payslips', 'payslip_runs', 'users', 'mail_all', 'crons_active'):
    if after[key] != before[key]:
        problems.append('%s %s -> %s' % (key, before[key], after[key]))
if after['employees'] - before['employees'] != len(made_emp):
    problems.append('employees moved by more than the seed made')
if after['contracts'] - before['contracts'] != len(made_con):
    problems.append('contracts moved by more than the seed made')
new_emp_ids = Employee.search([('name', 'in', [p[0] for p in PEOPLE]),
                               ('company_id', '=', company.id)]).ids
for emp in Employee.browse(new_emp_ids):
    for key in ('work_email', 'private_email', 'user_id', 'account_number'):
        if key in emp_fields and emp[key]:
            problems.append('%s has %s' % (emp.name, key))

# What the Renew dialog will show for each seeded contract.
Wizard = env['pb.people.contract.wizard'].sudo() \
    if 'pb.people.contract.wizard' in env else None
for con in Contract.search([('employee_id', 'in', new_emp_ids)], order='id'):
    line = '%s | %s | kind %s | treatment %s | ends %s | paid by %s' % (
        con.id, con.employee_id.name, con.vietnam_contract_type,
        con.pb_payroll_contract_type or '(empty)', con.date_end or '-',
        con.employee_id.pb_paid_by_id.code if 'pb_paid_by_id' in emp_fields else '?')
    if Wizard is not None:
        d = Wizard.get_defaults(con.employee_id.id, con.id).get('prefill') or {}
        line += ' || Renew shows kind=%r (%s) treatment=%r (%s)' % (
            d.get('vn_kind'), 'shown' if d.get('vn_kind_show') else 'hidden',
            d.get('pay_treatment'), 'shown' if d.get('pay_treatment_show') else 'hidden')
    say(line)

say('made %s people, %s contracts', len(made_emp), len(made_con))
if problems:
    env.cr.rollback()
    say('ABORTED, rolled back: %s', '; '.join(problems))
elif DRY:
    env.cr.rollback()
    say('DRY RUN — rolled back')
else:
    env.cr.commit()
    say('COMMITTED')
