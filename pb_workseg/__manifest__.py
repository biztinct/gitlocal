# -*- coding: utf-8 -*-
{
    'name': 'Payobook People In Two Places',
    'summary': 'One person across companies, the days they spend in each, and '
               'the two ways a split month can be paid',
    # A manifest description is shown to a person in the Apps list, so it is a
    # USER-VISIBLE string and keeps this product's own vocabulary (ledger GR7).
    # The engineering account lives in the module's docstrings.
    'description': """
People who work in more than one place.

WHAT THIS MODULE ADDS

  * A PERSON. One human being, however many employments they hold. Head
    counts count people, so somebody who transferred from one company to
    another in March is one person and not two.
  * WHERE THEY WORK. A month drawn as a strip of days. Drag across the days
    somebody spent in another entity, say where and under which payroll
    scheme, and both payslips draw themselves before anything is saved.
  * TWO WAYS TO PAY A SPLIT MONTH, and you choose which. Either each entity
    pays its own days — two payslips, each in its own money — or the home
    entity pays the whole month and the other entity is charged its share as
    an internal cost line.
  * SAME PERSON? A review that lists employee records that look like one
    human, with the evidence, and joins them in one press.
  * JOINERS AND LEAVERS BY THE DAY, switched OFF, per entity. Turning it on
    pays somebody who starts mid-month for the days they worked. It changes
    what those people are paid, so nothing turns it on for you.

WHAT IT DOES NOT CHANGE

  Anyone whose month is a whole month at one employment is paid exactly what
  they were paid before this module existed — the same components, the same
  amounts, to the digit. Nothing here posts to accounting: a charge between
  entities is a report line and an export.
""",
    'version': '19.0.1.3.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'pb_hr_payroll_formula',   # the schemes, and the proration journal
        'pb_group',                # the group, divisions and the one conversion
        'pb_hub',                  # the global palette + the shared back chip
        'pb_import_kit',           # pbim tokens/primitives + the shared ic() set
        'pb_employee_vault',       # the chip registry on the person's card
        # TIDY P1 — the screen is a LENS on the People hub, so this module is
        # mounted inside it. The direction is one way: `pb_people_hub` depends
        # on pb_hub, pb_settings, pb_people and pb_contracts and reaches this
        # module through none of them, so there is no cycle to fail an install.
        'pb_people_hub',
    ],
    'data': [
        'security/pb_workseg_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/pb_workseg_views.xml',
        'views/pb_workseg_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_workseg/static/src/scss/workseg.scss',
            # the screen first, then the lens and the chip that mount it,
            # then the rows that name them
            'pb_workseg/static/src/js/assignments.js',
            'pb_workseg/static/src/js/workseg_lens.js',
            'pb_workseg/static/src/js/workseg_chip.js',
            'pb_workseg/static/src/js/workseg_palette.js',
            'pb_workseg/static/src/xml/workseg.xml',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
