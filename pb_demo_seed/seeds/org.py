# -*- coding: utf-8 -*-
"""The world the five people live in: teams, roles, suppliers, budgets, plans.

BUILT FIRST AND REMOVED LAST. Everything else points at something here, so
this has to exist before any of it and survive until all of it has gone.

FOUND BEFORE MADE. Departments, contract types and working calendars are
things a real database usually already has, and a demo that quietly adds a
second "Agronomy" beside the customer's own is a demo that has damaged the
thing it was meant to show. `find_or_create` reuses what is there and registers
only what it genuinely added — which also means the remove can never take away
a team the customer set up themselves.
"""

#: The four functions the budget is cut by, and the roles inside them.
FUNCTIONS = [
    ('Agronomy', ['Agronomist', 'Senior Agronomist']),
    ('Field Operations', ['Field Operations Supervisor', 'Field Technician']),
    ('Commercial', ['Sales Executive', 'Commercial Manager']),
    ('People & Culture', ['HR Business Partner', 'Country Manager']),
]

#: Suppliers a people team actually deals with, one of them about to run out.
#: `(name, type, contact, agreement, months until it ends, value)`
VENDORS = [
    ('Demo Talent Partners', 'recruitment', 'Ngo Thi Lan',
     'Permanent placement — agronomy and commercial roles', 2, 240000000.0),
    ('Demo Learning Collective', 'learning', 'Bui Van Khoa',
     'Leadership and field-safety training programme', 7, 180000000.0),
    ('Demo Assess', 'assessment', 'Do Minh Chau',
     'Pre-hire assessments and psychometrics', 11, 60000000.0),
    ('Demo Health Cover Brokers', 'benefits', 'Vu Thi Nga',
     'Private health insurance broking and claims support', 5, 95000000.0),
    ('Demo Workplace Committee Services', 'committee', 'Tran Quoc Dat',
     'Harassment-prevention committee and grievance support', 1, 35000000.0),
]

#: The benefit plans people are enrolled on later.
BENEFIT_PLANS = [
    ('Demo Family Health Cover', 'health', 'Demo Health Cover Brokers',
     'Inpatient and outpatient cover for the employee, spouse and children.'),
    ('Demo Personal Health Cover', 'health', 'Demo Health Cover Brokers',
     'Inpatient and outpatient cover for the employee only.'),
    ('Demo Group Life Cover', 'life', 'Demo Health Cover Brokers',
     'Twenty-four times monthly salary, payable to the named beneficiary.'),
]

#: Manpower budget by function, and what has been spent so far this year.
#: `(function, budgeted per month, people planned)`
MANPOWER_BUDGET = [
    ('Agronomy', 420000000.0, 14),
    ('Field Operations', 610000000.0, 26),
    ('Commercial', 380000000.0, 9),
    ('People & Culture', 210000000.0, 5),
]

#: HR operating spend, the second budget the requirements ask for.
HR_OPS_SPEND = [
    ('Recruitment agency fees — agronomy intake', 'Demo Talent Partners',
     -2, 84000000.0),
    ('Leadership programme, first cohort', 'Demo Learning Collective',
     -1, 62000000.0),
    ('Pre-hire assessments, quarter to date', 'Demo Assess', -1, 18000000.0),
    ('Health cover broker retainer', 'Demo Health Cover Brokers', 0, 24000000.0),
]


def build(ctx):
    _departments_and_jobs(ctx)
    _hrbp_rule(ctx)
    _contract_type_and_calendar(ctx)
    _vendors(ctx)
    _benefit_plans(ctx)
    _payroll_calendar(ctx)
    _budgets(ctx)


# ----------------------------------------------------------------------
def _departments_and_jobs(ctx):
    departments, jobs = {}, {}
    for name, titles in FUNCTIONS:
        dept = ctx.find_or_create(
            'hr.department',
            [('name', '=', name), ('company_id', '=', ctx.company.id)],
            {'name': name, 'company_id': ctx.company.id})
        departments[name] = dept
        for title in titles:
            jobs[title] = ctx.find_or_create(
                'hr.job',
                [('name', '=', title), ('company_id', '=', ctx.company.id)],
                {'name': title, 'company_id': ctx.company.id,
                 'department_id': dept.id})
    ctx.set('departments', departments)
    ctx.set('jobs', jobs)


def _hrbp_rule(ctx):
    """Somebody has to be the HR business partner, or nobody is.

    Opening a joining checklist asks `pb.hrbp.rule` who looks after this
    person, and on a database with no rules the answer is nobody: the joiner's
    dashboard then has an empty box where the requirements ask for a name and
    a way to reach them. One country-wide rule is the smallest honest fix, and
    it is created only if the customer has none of their own.
    """
    ctx.find_or_create(
        'pb.hrbp.rule',
        [('company_id', '=', ctx.company.id)],
        {'name': 'Everybody in Vietnam',
         'sequence': 100,
         'country_id': ctx.company.country_id.id,
         'hrbp_user_id': ctx.env.user.id,
         'note': 'Demo fallback rule so every joiner has an HR partner.'})


def _contract_type_and_calendar(ctx):
    """A permanent and a fixed-term type, because the stories need both.

    Matched on the NAME rather than created blind: this database ships
    seventeen contract types and adding an eighteenth called "Permanent"
    beside the existing one helps nobody.
    """
    for key, name in (('permanent', 'Permanent'), ('fixed', 'Fixed Term')):
        ctx.set('type_%s' % key, ctx.find_or_create(
            'hr.contract.type', [('name', 'ilike', name)], {'name': name}))
    calendar = ctx.company.resource_calendar_id
    if not calendar:
        calendar = ctx.env['resource.calendar'].sudo().search(
            [('company_id', 'in', (ctx.company.id, False))], limit=1)
    ctx.set('calendar', calendar)


def _vendors(ctx):
    vendors = {}
    departments = ctx.get('departments', {})
    people_team = departments.get('People & Culture')
    for name, kind, contact, agreement, months, value in VENDORS:
        vendor = ctx.create('pb.vendor', {
            'name': name,
            'vendor_type': kind,
            'contact_name': contact,
            'contact_email': '%s@example.com' % (
                contact.split()[-1].lower()),
            'contact_phone': '+84 28 3822 %04d' % (1000 + len(vendors) * 7),
            'department_id': people_team.id if people_team else False,
            'responsible_user_id': ctx.env.user.id,
            'country_id': ctx.company.country_id.id,
            'notes': 'Demo supplier. Remove with the rest of the demo data.',
        })
        vendors[name] = vendor
        ctx.create('pb.vendor.agreement', {
            'vendor_id': vendor.id,
            'name': agreement,
            'date_start': ctx.months(months - 12),
            'date_end': ctx.months(months),
            # Two months' warning is the convention the alerts use; an
            # agreement that ends in one month therefore shows as overdue
            # for the renewal conversation, which is the point of it.
            'renewal_date': ctx.months(months - 2),
            'value': value,
            'currency_id': ctx.company.currency_id.id,
            'responsible_user_id': ctx.env.user.id,
        })
    ctx.set('vendors', vendors)


def _benefit_plans(ctx):
    plans = {}
    for name, kind, provider, coverage in BENEFIT_PLANS:
        plans[name] = ctx.create('pb.benefit.plan', {
            'name': name,
            'kind': kind,
            'provider_name': provider,
            'country_id': ctx.company.country_id.id,
            'coverage_html': '<p>%s</p>' % coverage,
        })
    ctx.set('benefit_plans', plans)


def _payroll_calendar(ctx):
    """Last month closed, this month open, next month ahead.

    Three rows rather than one so the cut-off story has a before and an after:
    a closed month nobody can change, the month being worked on, and the one
    the reminders are counting down to.
    """
    for offset, state in ((-1, 'closed'), (0, 'upcoming'), (1, 'upcoming')):
        month = ctx.month_start(offset)
        ctx.create('pb.payroll.calendar', {
            'month': month,
            'cutoff_date': month.replace(day=20),
            'pay_date': month.replace(day=25),
            'country_id': ctx.company.country_id.id,
            'state': state,
            'reminder_offset_days': '5,2,0',
            'notes': 'Demo payroll month.',
        })


def _budgets(ctx):
    """A manpower budget per function per month, and the HR operating spend.

    Three months of manpower budget — the two behind us carrying what was
    actually paid, the current one still open — because a budget screen with
    one month on it cannot show the only thing a budget screen is for: whether
    the line is being held.
    """
    departments = ctx.get('departments', {})
    vendors = ctx.get('vendors', {})
    currency = ctx.company.currency_id
    for name, monthly, headcount in MANPOWER_BUDGET:
        dept = departments.get(name)
        if not dept:
            continue
        for offset in (-2, -1, 0):
            spent = 0.0
            people = 0
            if offset < 0:
                # A little under budget, never exactly on it: a demo in which
                # every number lands on the plan reads as made up, because it
                # is.
                spent = round(monthly * (0.94 if offset == -2 else 0.97))
                people = headcount - (1 if offset == -2 else 0)
            ctx.create('pb.budget.line', {
                'period_month': ctx.month_start(offset),
                'department_id': dept.id,
                'pb_function_id': dept.id,
                'pb_budget_type': 'manpower',
                'pb_source': 'upload',
                'forecast_cost': monthly,
                'actual_cost': spent,
                'forecast_headcount': headcount,
                'actual_headcount': people,
                'currency_id': currency.id,
                'pb_currency_id': currency.id,
                'pb_note': 'Demo manpower budget',
            })

    hr_dept = departments.get('People & Culture')
    for name, supplier, offset, amount in HR_OPS_SPEND:
        ctx.create('pb.budget.expense', {
            'name': name,
            'spend_date': ctx.month_start(offset).replace(day=12),
            'period_month': ctx.month_start(offset),
            'budget_type': 'hr_ops',
            'department_id': hr_dept.id if hr_dept else False,
            'function_id': hr_dept.id if hr_dept else False,
            'amount': amount,
            'currency_id': currency.id,
            'supplier': supplier,
            'vendor_id': vendors[supplier].id if supplier in vendors else False,
            'note': 'Demo HR operating spend.',
        })

    if hr_dept:
        for offset in (-2, -1, 0):
            ctx.create('pb.budget.line', {
                'period_month': ctx.month_start(offset),
                'department_id': hr_dept.id,
                'pb_function_id': hr_dept.id,
                'pb_budget_type': 'hr_ops',
                'pb_source': 'upload',
                'forecast_cost': 120000000.0,
                'actual_cost': 0.0 if offset == 0 else 84000000.0,
                'currency_id': currency.id,
                'pb_currency_id': currency.id,
                'pb_note': 'Demo HR operations budget',
            })
