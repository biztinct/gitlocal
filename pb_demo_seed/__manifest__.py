# -*- coding: utf-8 -*-
{
    'name': 'Payobook Demo Data',
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'summary': 'Load a small, complete, believable demo world — and take it out '
               'again without leaving a trace.',
    'description': """
Demo data you can put in and take out
=====================================
Five people, named so nobody mistakes them for staff, each carrying ONE story
end to end:

* a joiner three days in, with a laptop being procured and a buddy assigned;
* somebody whose trial period ends in a fortnight, with peer feedback running;
* somebody on a performance plan, with objectives and check-ins;
* a fixed-term contract that was not extended, with an exit and a laptop still
  to come back;
* the manager they all report to, with assets, an award and a benefits package.

Around them: vendors and their agreements, a manpower and an HR operations
budget, recognition nominations and a quarter, benefit plans and enrolments, a
payroll calendar, leave, and the training that gates a probation clearance.

**Everything it creates, it remembers.** Each record is written into a register
as it is made, and "Remove demo data" walks that register backwards and takes
them out. It deletes nothing it did not create — not by matching on a name, not
by guessing, but because it wrote the list itself.

Records the PRODUCT made for a demo — the ones somebody created on a screen
while showing it off — go on a register of their own, so they can be taken out
the same way.

Nothing here is specific to one customer. The world is described by a PROFILE,
and a second tenant is a second profile rather than a second module.
""",
    'author': 'Payobook',
    'website': 'https://payobook.com',
    'license': 'LGPL-3',
    # WHAT THE WORLD IS BUILT OUT OF, and nothing else. The Vietnam payroll
    # mapping is deliberately NOT here: `seeds/people.py` writes its fields
    # only where the model actually has them (`if name in Employee._fields`),
    # so a database without it gets a demo world with no payroll facts rather
    # than no demo world at all — and this module can then be installed on a
    # database that does not carry the mapping.
    'depends': [
        'pb_settings',
        'pb_lifecycle',
        'pb_onboarding',
        'pb_probation',
        'pb_pip',
        'pb_assets',
        'pb_comp_ben',
        'pb_vendor_access',
        'pb_rnr',
        'pb_budget',
        'pb_contract_lifecycle',
        'pb_offboarding',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/demo_seed_views.xml',
        'data/demo_seed_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_demo_seed/static/src/js/demo_seed_settings.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
