# -*- coding: utf-8 -*-
{
    'name': 'Payobook Organisation',
    'summary': 'Jobs with levels, cost centres, pause hiring, would-rehire',
    'description': """
WDGAP step 8, phase S8-C. One People tab, "Jobs", for how the organisation is
laid out:

  * JOB LEVELS: a named ladder set once (`pb.job.level`); every job
    (`hr.job`) carries a level and a description. The pay band and family
    are read from Pay when it is installed (probe, no dependency).
  * COST CENTRES: a proper list (`pb.cost.centre`) kept in step with the
    existing cost-centre text on contracts (`hr.contract.costcenter` stays the
    one written value everything reads). A person or a whole team is moved to
    a cost centre FROM A DATE (`pb.cost.centre.move`, applied on the day by a
    quiet daily job). History is never rewritten: a payslip that is no longer
    a draft, or whose period ended before the change, keeps the cost centre it
    was paid under — on every path that writes the text, not only this one.
  * PAUSE HIRING per company, team or role (`pb_hiring_paused` on `hr.job`,
    cross-step contract C-2): no new hiring request, no sending one in, no
    opening a role, no advert, no new open role on the org chart, and the
    careers page hides the role. Candidates and offers already in progress
    carry on, with a warning. Unpausing restores everything (nothing is
    rewritten while paused).
  * WOULD REHIRE: a mark on the leaver (HR only), asked in the Exits drawer,
    and a quiet "Worked here before" chip for HR on a matching candidate.

Nothing here changes a payslip figure. No demo data, no email, nothing on
until somebody sets it up.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'license': 'LGPL-3',
    'depends': [
        'hr',
        'om_hr_payroll',        # hr.contract.costcenter, the stored payslip-line copy
        'pb_import_kit',        # icons + quiet board pieces
        'pb_filter_kit',        # the shared filter panel
        'pb_hub',               # the palette
        'pb_people_hub',        # the People hub lens registry
        'pb_hiring',            # pause hiring: requests, adverts, careers page
        'pb_orgchart',          # pause hiring: open roles added on the org chart
        'pb_offboarding',       # would rehire: the Exits drawer
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/org_security.xml',
        'data/org_cron.xml',
        'views/org_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_org_structure/static/src/scss/org_board.scss',
            'pb_org_structure/static/src/js/org_board.js',
            'pb_org_structure/static/src/js/org_palette.js',
            'pb_org_structure/static/src/js/exits_rehire.js',
            'pb_org_structure/static/src/xml/org_board.xml',
            'pb_org_structure/static/src/xml/hiring_pause.xml',
            'pb_org_structure/static/src/xml/exits_rehire.xml',
        ],
    },
    'installable': True,
    'application': False,
}
