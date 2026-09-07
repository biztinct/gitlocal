# -*- coding: utf-8 -*-
{
    'name': 'Payobook Group',
    'summary': 'The group: its member companies, the currency the board reads '
               'in, how exchange rates are picked, and divisions that cross '
               'company lines',
    # A manifest description is shown to a person in the Apps list, so it is a
    # USER-VISIBLE string and keeps this product's own vocabulary. The
    # engineering account — model names, the platform's own field names and
    # why the branch tree is unusable — is in the module's docstrings.
    'description': """
Your group, and the money it reads in.

WHAT THIS MODULE ADDS

  * A GROUP: one record naming your member companies, the currency the board
    reads consolidated figures in, how an exchange rate is picked for a month,
    and the month your financial year starts. The group is its own record and
    the companies stay exactly as they are.
  * ONE CONVERSION SERVICE, used by every screen that shows a group figure. It
    refuses to invent a rate: where nobody has said what one currency is worth
    in another, the screen says so and the amounts stay in the money they were
    paid in.
  * DIVISIONS: the parts of the business that do not stop at a company border.
    Departments in any member company attach to a division with dates, and a
    division attached at the top of a department tree covers everything under
    it.
  * A GROUP SCREEN behind the Settings cog: your companies drawn as a tree,
    the months that already have exchange rates, and the divisions board.

WHAT IT DOES NOT CHANGE

  Nothing here changes a pay run, a payslip, an employee record or a contract.
  No amount is ever stored converted: every figure keeps the currency it was
  paid in and is converted when somebody looks at it.
""",
    'version': '19.0.1.2.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',                   # departments, and the roster the counts come from
        'mail',                 # the group's currency and policy are tracked
        'pb_hub',               # the global palette + the shared back chip
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_settings',          # the cog this screen lives behind
    ],
    'data': [
        'security/pb_group_security.xml',
        'security/ir.model.access.csv',
        'views/pb_group_views.xml',
        'views/pb_group_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_group/static/src/scss/group_room.scss',
            # the component first, then the rows that name its action
            'pb_group/static/src/js/group_room.js',
            'pb_group/static/src/js/group_palette.js',
            'pb_group/static/src/xml/group_room.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
