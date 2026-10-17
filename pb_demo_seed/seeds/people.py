# -*- coding: utf-8 -*-
"""Five people, and everything the payroll reads off them.

WHY FIVE AND NOT FIFTY. A demo is a conversation, not a load test. Five people
can each carry one story all the way through, and a person watching can hold all
five in their head. The moment there are fifty, every screen is full and none of
them means anything.

EVERY NAME STARTS WITH "Demo". That is for the human in the room, not for the
remove — the remove works off the register (`models/demo_seed.py`) and would
work just as well if they were called anything at all. It is there so nobody
looking at a list of people has to wonder which ones are real.

THE PAYROLL FACTS ARE THE POINT OF THIS FILE. Each person is given the answers
the Vietnam pay scheme used to ask a spreadsheet for every month — local or
foreign, insured or not, union member, tax resident, dependants, grade, the
allowances that sit on their contract. After this runs, the monthly pay data
file needs their code and their hours and nothing else.
"""

import logging

_logger = logging.getLogger(__name__)

#: The cast. One dictionary per person, read top to bottom by `build`.
#:
#: `story` is not stored anywhere — it is here so that the next person to read
#: this file knows why somebody's dates look the way they do, and does not
#: "tidy" a joining date that a probation review depends on.
PEOPLE = [
    {
        'key': 'joiner',
        'code': 'DEMO001',
        'name': 'Demo Nguyen Thi Mai',
        'story': 'Three days in. Laptop being procured, buddy assigned, '
                 'orientation next week, trial period just started.',
        'sex': 'female',
        'birth_years_ago': 26,
        'department': 'Agronomy',
        'job': 'Agronomist',
        'joined_days_ago': 3,
        'wage': 18000000.0,
        'grade': 1,
        'contract_type': 'permanent',
        'bank': ('Vietcombank', '0071000512345', 'BFTVVNVX'),
        'employee_facts': {
            'pb_vn_is_local': True,
            'pb_vn_in_insurance': True,
            'pb_vn_union_member': True,
            'pb_vn_tax_resident': True,
            'pb_vn_tax_commitment': True,
        },
        'contract_facts': {
            'dependents': 0,
            'pb_vn_qual_ot_weekday': True,
            'pb_vn_qual_ot_weekend': True,
            'pb_vn_qual_ot_holiday': True,
            'pb_vn_qual_night': True,
        },
        'components': {'UNIFORM': 500000.0},
    },
    {
        'key': 'probation',
        'code': 'DEMO002',
        'name': 'Demo Tran Van Hung',
        'story': 'Trial period ends in eighteen days. Peers nominated, two of '
                 'four answers in, manager conversation still to come.',
        'sex': 'male',
        'birth_years_ago': 33,
        'department': 'Field Operations',
        'job': 'Field Operations Supervisor',
        'joined_days_ago': 72,
        'wage': 26000000.0,
        'grade': 2,
        'contract_type': 'permanent',
        'bank': ('Techcombank', '19033245678901', 'VTCBVNVX'),
        'employee_facts': {
            'pb_vn_is_local': True,
            'pb_vn_in_insurance': True,
            'pb_vn_union_member': True,
            'pb_vn_tax_resident': True,
        },
        'contract_facts': {
            'dependents': 2,
            'pb_vn_qual_ot_weekday': True,
            'pb_vn_qual_ot_weekend': True,
            'pb_vn_qual_ot_holiday': True,
            'pb_vn_qual_night': True,
            'pb_vn_qual_transport': True,
        },
        'components': {'UNIFORM': 500000.0, 'REFERINC': 3000000.0},
    },
    {
        'key': 'pip',
        'code': 'DEMO003',
        'name': 'Demo Le Thi Hoa',
        'story': 'Two years in, confirmed long ago, now six weeks into a '
                 'performance plan with one objective at risk.',
        'sex': 'female',
        'birth_years_ago': 31,
        'department': 'Commercial',
        'job': 'Sales Executive',
        'joined_days_ago': 760,
        'wage': 32000000.0,
        'grade': 2,
        'contract_type': 'permanent',
        'bank': ('BIDV', '31010000987654', 'BIDVVNVX'),
        'employee_facts': {
            'pb_vn_is_local': True,
            'pb_vn_in_insurance': True,
            'pb_vn_tax_resident': True,
            'pb_vn_enrol_private_health': True,
        },
        'contract_facts': {
            'dependents': 1,
            'pb_vn_qual_transport': True,
        },
        'components': {'HLTHEEAMT': 1200000.0, 'ADVANCE': 2000000.0},
    },
    {
        'key': 'fixed_term',
        'code': 'DEMO004',
        'name': 'Demo Pham Minh Quan',
        'story': 'Fixed-term contract ending in forty-five days. Extension '
                 'asked for and turned down; leaving checklist open and the '
                 'laptop still out.',
        'sex': 'male',
        'birth_years_ago': 23,
        'department': 'Agronomy',
        'job': 'Field Technician',
        'joined_days_ago': 320,
        'wage': 12000000.0,
        'grade': 1,
        'contract_type': 'fixed',
        'contract_ends_in_days': 45,
        'bank': ('ACB', '0123456789012', 'ASCBVNVX'),
        'employee_facts': {
            'pb_vn_is_local': True,
            'pb_vn_in_insurance': True,
            'pb_vn_union_member': True,
            'pb_vn_tax_resident': True,
            'pb_vn_tax_commitment': True,
        },
        'contract_facts': {
            'dependents': 0,
            'pb_vn_qual_ot_weekday': True,
            'pb_vn_qual_ot_weekend': True,
            'pb_vn_qual_ot_holiday': True,
        },
        'components': {'UNIFORM': 500000.0, 'AGROINC': 1500000.0},
    },
    {
        'key': 'manager',
        'code': 'DEMO005',
        'name': 'Demo Vo Thanh Son',
        'story': 'Country manager and everybody else\'s manager. Foreign hire, '
                 'so the expatriate insurance and allowance rules apply. Assets, '
                 'an award and a full benefits package.',
        'sex': 'male',
        'birth_years_ago': 45,
        'department': 'People & Culture',
        'job': 'Country Manager',
        'joined_days_ago': 1580,
        'wage': 85000000.0,
        'grade': 3,
        'contract_type': 'permanent',
        'bank': ('HSBC Vietnam', '00112233445566', 'HSBCVNVX'),
        'employee_facts': {
            # The one foreign hire, which is what puts the expatriate branches
            # of the scheme on screen — private insurance allowance, the
            # foreign statutory cover line, no union dues.
            'pb_vn_is_local': False,
            'pb_vn_in_insurance': False,
            'pb_vn_union_member': False,
            'pb_vn_tax_resident': True,
            'pb_vn_enrol_family_health': True,
            'pb_vn_enrol_private_health': True,
            'pb_vn_enrol_dep_health': True,
        },
        'contract_facts': {
            'dependents': 3,
            'pb_vn_qual_transport': True,
            'pb_vn_qual_other_exempt': True,
            'pb_vn_qual_leave_encash': True,
        },
        'components': {
            'PRIVINSAMT': 6000000.0,
            'HLTHEEAMT': 2500000.0,
            'HLTHDEPAMT': 3500000.0,
            'OTHERTAX': 5000000.0,
        },
    },
]


def build(ctx):
    departments = ctx.get('departments', {})
    jobs = ctx.get('jobs', {})
    calendar = ctx.get('calendar')
    people = {}

    for spec in PEOPLE:
        employee = _employee(ctx, spec, departments, jobs)
        _bank_account(ctx, employee, spec)
        contract = _contract(ctx, employee, spec, calendar)
        _contract_components(ctx, contract, spec)
        people[spec['key']] = employee
        ctx.set('contract_%s' % spec['key'], contract)

    _reporting_lines(people)
    ctx.set('people', people)
    _logger.info("pb_demo_seed: %s demo people created", len(people))


# ----------------------------------------------------------------------
def _employee(ctx, spec, departments, jobs):
    department = departments.get(spec['department'])
    job = jobs.get(spec['job'])
    joined = ctx.days(-spec['joined_days_ago'])
    first = spec['name'].split()[-1].lower()

    vals = {
        'name': spec['name'],
        'employee_id': spec['code'],
        # BOTH boxes carry the code on purpose. The pay-data importer matches a
        # row on either, and a demo that works only if the importer happens to
        # prefer one of them is a demo that will fail in front of somebody.
        'identification_id': spec['code'],
        'sex': spec['sex'],
        'birthday': ctx.days(-365 * spec['birth_years_ago'] - 40),
        'department_id': department.id if department else False,
        'job_id': job.id if job else False,
        'job_title': spec['job'],
        'country_id': ctx.company.country_id.id,
        'work_email': 'demo.%s@example.com' % first,
        'work_phone': '+84 90 %07d' % (1234567 + int(spec['code'][-3:])),
        'company_id': ctx.company.id,
    }
    # Fields other Payobook modules add to the employee record. Set through a
    # membership test rather than assumed: this profile has to load on a
    # database where the Vietnam mapping module is present and on one where
    # somebody has not installed it yet, and a KeyError in the middle of a
    # build leaves half a demo behind.
    Employee = ctx.env['hr.employee']
    optional = dict(spec['employee_facts'])
    optional['date_of_joining'] = joined
    for name, value in optional.items():
        if name in Employee._fields:
            vals[name] = value

    # REUSE A DEMO PERSON WHO SURVIVED A REMOVAL, rather than mint a second one
    # with the same code.
    #
    # A remove reports what it could not delete instead of forcing, and the
    # commonest reason is real work somebody built on top: a pay run that
    # includes a demo employee holds that employee down. The rest of the world
    # goes, the person stays, and the next load would otherwise create a SECOND
    # DEMO002 — two people, one code, and an importer that has to pick.
    #
    # Matched on the employee code because that is what the pay-data file keys
    # on, and scoped to this company because two tenants in one database may
    # each have their own.
    existing = Employee.sudo().with_context(active_test=False).search([
        ('employee_id', '=', spec['code']),
        ('company_id', '=', ctx.company.id),
    ], limit=1)
    if existing:
        existing.sudo().write(dict(vals, active=True))
        employee = ctx.track(existing, label=spec['name'])
    else:
        employee = ctx.create('hr.employee', vals, label=spec['name'])

    # The private contact Odoo makes for an employee is a record in its own
    # right and does not go when the employee does, so it joins the register.
    # THE CONTACT IS REGISTERED "LAST". Odoo makes a private contact for every
    # employee, and it refuses to delete one while an employee still points at
    # it — so a contact registered in creation order would be reached BEFORE
    # its employee on the way out and refuse, every time. `last=True` moves it
    # to the end of the backwards walk, after the employee has gone.
    partner = employee.sudo().work_contact_id
    if partner:
        ctx.track(partner, label='%s — contact' % spec['name'], last=True)
    return employee


def _bank_account(ctx, employee, spec):
    """Where this person's salary is paid.

    Registered in three pieces because that is what it is: the bank itself may
    already be on the database and is reused, the contact is the employee's,
    and only the ACCOUNT is genuinely new.
    """
    bank_name, number, bic = spec['bank']
    bank = ctx.find_or_create(
        'res.bank', ['|', ('name', '=ilike', bank_name), ('bic', '=', bic)],
        {'name': bank_name, 'bic': bic,
         'country': ctx.company.country_id.id})

    partner = employee.sudo().work_contact_id
    if not partner:
        partner = ctx.env['res.partner'].sudo().create({
            'name': spec['name'],
            'type': 'private',
            'company_id': ctx.company.id,
        })
        ctx.track(partner, label='%s — contact' % spec['name'], last=True)
        employee.sudo().work_contact_id = partner.id

    # A BANK ACCOUNT IS ARCHIVED, NOT DELETED. Odoo keeps the row — an account
    # number is evidence of where money went — so a removal leaves it behind
    # archived, and a second load asking for the same number is refused outright
    # with "already exists but is archived". Unarchiving what is there is both
    # what Odoo asks for and what a person would do.
    values = {
        'acc_number': number,
        'partner_id': partner.id,
        'bank_id': bank.id,
        'acc_holder_name': spec['name'],
        'company_id': ctx.company.id,
    }
    label = '%s — %s' % (spec['name'], bank_name)
    existing = ctx.env['res.partner.bank'].sudo().with_context(
        active_test=False).search([
            ('partner_id', '=', partner.id),
            ('acc_number', '=', number),
        ], limit=1)
    if existing:
        existing.sudo().write(dict(values, active=True))
        account = ctx.track(existing, label=label)
    else:
        account = ctx.create('res.partner.bank', values, label=label)

    if 'bank_account_ids' in employee._fields:
        employee.sudo().bank_account_ids = [(4, account.id)]
    return account


def _contract(ctx, employee, spec, calendar):
    joined = ctx.days(-spec['joined_days_ago'])
    contract_type = ctx.get('type_%s' % spec['contract_type'])
    vals = {
        'name': 'Contract — %s' % spec['name'],
        'employee_id': employee.id,
        'company_id': ctx.company.id,
        'wage': spec['wage'],
        'struct_id': False,
        'date_start': joined,
        'state': 'open',
        'schedule_pay': 'monthly',
        'type_id': contract_type.id if contract_type else False,
        'resource_calendar_id': calendar.id if calendar else False,
    }
    if spec.get('contract_ends_in_days'):
        vals['date_end'] = ctx.days(spec['contract_ends_in_days'])

    Contract = ctx.env['hr.contract']
    facts = dict(spec['contract_facts'])
    facts.setdefault('pb_vn_pay_grade', spec['grade'])
    facts.setdefault('pb_vn_hours_per_day', 8.0)
    facts.setdefault('pb_vn_annual_days', 260)
    for name, value in facts.items():
        if name in Contract._fields:
            vals[name] = value

    return ctx.create('hr.contract', vals,
                      label='Contract — %s' % spec['name'])


def _contract_components(ctx, contract, spec):
    """Fill in the steady amounts that live on the contract.

    The LINES already exist — `hr.contract.create` gives a new contract one per
    advantage template — so this writes an amount onto a line rather than
    creating one, and nothing is added to the register: the lines belong to the
    contract and go when it does.
    """
    wanted = spec.get('components') or {}
    if not wanted:
        return
    seen = set()
    for advantage in contract.sudo().advantages_ids:
        code = (advantage.advantage_template_code
                or advantage.advantage_template_id.code or '').upper()
        seen.add(code)
        if code in wanted:
            advantage.sudo().amount = wanted[code]

    # A LINE THE CONTRACT NEVER GOT. `hr.contract.create` gives a new contract
    # one line per template that existed AT THAT MOMENT, so a component added to
    # the profile later leaves every earlier contract without anywhere to put
    # the amount. Creating the missing line is what a person would do, and it
    # keeps the seeder working whichever order the two modules were installed in.
    Template = ctx.env['hr.contract.advantage.template'].sudo()
    for code, amount in wanted.items():
        if code in seen:
            continue
        template = Template.search([('code', '=', code)], limit=1)
        if not template:
            continue
        ctx.env['hr.contract.advantage'].sudo().create({
            'contract_id': contract.id,
            'advantage_template_id': template.id,
            'amount': amount,
        })


def _reporting_lines(people):
    """Everybody reports to the country manager, and he reports to nobody.

    Done last, in one pass, because a manager cannot be set before the manager
    exists and threading that through the creation loop would mean ordering the
    cast list by seniority instead of by story.
    """
    manager = people.get('manager')
    if not manager:
        return
    for key, employee in people.items():
        if key == 'manager':
            continue
        employee.sudo().write({'parent_id': manager.id,
                               'coach_id': manager.id})
