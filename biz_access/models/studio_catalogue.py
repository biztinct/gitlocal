"""Explicit adapters: only installed, reviewed business resources are editable.

Profiles compose existing roles. Record policies only restrict native ACLs and
rules; they never manufacture a permission the underlying application lacks.
"""
WORKSPACES = [
    ('hiring', 'Hiring'), ('people', 'People'), ('payroll', 'Payroll'),
    ('lifecycle', 'Lifecycle'), ('money', 'Money & budgets'), ('system', 'System'),
]
# Navigation filters, never permission grants. Roles retain their canonical
# category and full ability set even when a business screen references them.
FOCUSES = {
    'hiring.recruitment': ('hiring', 'hiring', 'Recruitment', (), 'Candidates, hiring requests, interviews and offers.'),
    'people.records': ('people', 'people', 'Employees & records',
                       ('records-', 'studio-hr-', 'studio-employee', 'equipment-', 'where-they-work'),
                       'Employee records, contracts, equipment and work locations.'),
    'people.lifecycle': ('people', 'lifecycle', 'Joiners & leavers', (),
                         'Joining, probation, leaving and contract-renewal workflows.'),
    'people.planning': ('people', 'money', 'Pay & planning',
                        ('decision-room', 'pay-bands-', 'pay-review-',),
                        'Workforce planning, pay bands and pay-review decisions.'),
    'payroll.operations': ('payroll', 'payroll', 'Payroll operations', (),
                           'Pay runs, payslips, payments, formulas and payroll reporting.'),
    'payroll.budget': ('payroll', 'money', 'Budget', ('budget-',),
                       'Budget holders, budget preparation and finance review.'),
    'payroll.awards': ('payroll', 'people', 'Packages & awards', ('packages-and-awards',),
                       'Pay packages, benefits and one-off awards.'),
}


def focus_roles(roles, workspace, focus=False):
    rows = roles.filtered(lambda r: workspace_of(r) == workspace)
    prefixes = FOCUSES[focus][3] if focus else ()
    return rows.filtered(lambda r: any(k and k.startswith(prefixes)
        for k in r.ability_ids.mapped('technical_key'))) if prefixes else rows

RESOURCES = {
    'hr.applicant': {'workspace': 'hiring', 'label': 'Candidates', 'owner': 'user_id',
                     'fields': ['partner_name', 'email_from', 'partner_phone', 'salary_expected', 'salary_proposed', 'description'],
                     'sensitive': ['salary_expected', 'salary_proposed'], 'department': 'department_id'},
    'pb.hiring.requisition': {'workspace': 'hiring', 'label': 'Hiring requests', 'owner': 'recruiter_id',
                             'fields': ['title', 'location', 'requirements', 'remarks', 'budget_cost'],
                             'sensitive': ['budget_cost'], 'department': 'department_id', 'state': 'state'},
    'pb.hiring.offer': {'workspace': 'hiring', 'label': 'Offers', 'owner': 'create_uid',
                       'fields': ['name', 'start_date', 'notes'], 'state': 'state'},
    'pb.hiring.interview': {'workspace': 'hiring', 'label': 'Interviews', 'owner': 'recruiter_id',
                           'fields': ['name', 'location', 'notes'], 'state': 'state'},
    'hr.employee': {'workspace': 'people', 'label': 'Employees', 'owner': 'user_id',
                    'department': 'department_id', 'fields': ['name', 'work_email', 'work_phone', 'mobile_phone', 'private_email', 'identification_id'],
                    'sensitive': ['private_email', 'identification_id']},
    'hr.contract': {'workspace': 'people', 'label': 'Contracts', 'owner': 'employee_id.user_id',
                    'department': 'employee_id.department_id', 'fields': ['name', 'wage', 'date_start', 'date_end', 'notes'],
                    'sensitive': ['wage'], 'state': 'state'},
    'hr.payslip': {'workspace': 'payroll', 'label': 'Payslips', 'owner': 'employee_id.user_id',
                   'department': 'employee_id.department_id', 'fields': ['name', 'date_from', 'date_to', 'note'], 'state': 'state'},
    'hr.payslip.run': {'workspace': 'payroll', 'label': 'Pay runs', 'owner': 'create_uid',
                       'fields': ['name', 'date_start', 'date_end'], 'state': 'state'},
}
ACTIONS = ('read', 'create', 'write', 'unlink')
SCOPES = ('none', 'own', 'team', 'all')


def workspace_of(role):
    # Ownership follows the catalogue's capability keys, not its display name.
    if role.area == 'system':
        return 'system'
    if any(key.startswith('hiring-') for key in role.ability_ids.mapped('technical_key') if key):
        return 'hiring'
    return role.area if role.area in dict(WORKSPACES) else 'system'
