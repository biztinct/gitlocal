# -*- coding: utf-8 -*-
{
    'name': 'Payobook Pay Runs Cockpit',
    'summary': 'Pay-run pipeline board + enhanced batch form (KPIs, approval pipeline)',
    # 19.0.1.6.0 — W105: the hr.payslip.line read ACL that had to sit beside the
    # hr.payslip one, plus tests/test_payslip_line_access.py.
    # 19.0.2.0.0 — the three-tier ladder is gone. A pay run is approved by
    # whatever route the business published for its scheme, its part of the
    # business and its kind of run (biz_approval_workflow).
    'version': '19.0.2.2.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_import_kit is DECLARED rather than relied on transitively: both JS files
    # here import its `ic()` registry, and an implicit dependency is one uninstall
    # away from a bundle that cannot resolve a module path.
    # biz_approval_workflow: the engine this run's approval is carried by.
    # pb_scheme_map / pb_group: a route is chosen per pay scheme and per
    # division, and those are the two modules that own those ideas.
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_theme',
                'pb_hr_workforce', 'pb_import_kit',
                'biz_approval_workflow', 'pb_scheme_map', 'pb_group'],
    'data': [
        # Phase L: the approval tiers live on pb_* groups, but hr.payslip.run /
        # hr.payslip carry ACLs only for om_hr_payroll.group_hr_payroll_manager —
        # so a Payroll Officer (the new level0 tier) could not even READ the
        # board its own tier owns. One row on group_payroll_base_officer covers
        # the whole ladder (manager → officer, final approver → … → officer);
        # read+write only, never create/unlink.
        'security/ir.model.access.csv',
        'views/pb_payruns_action.xml',
        'views/hr_payslip_run_kanban.xml',
        'views/hr_payslip_run_form_enhance.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'assets': {
        'web.assets_backend': [
            'pb_payruns/static/src/scss/payruns.scss',
            'pb_payruns/static/src/scss/payrun_form.scss',
            'pb_payruns/static/src/scss/payruns_kanban.scss',
            'pb_payruns/static/src/js/pipeline_field.js',
            'pb_payruns/static/src/js/payruns.js',
            'pb_payruns/static/src/js/payruns_kanban.js',
            'pb_payruns/static/src/xml/pipeline_field.xml',
            'pb_payruns/static/src/xml/payruns.xml',
            'pb_payruns/static/src/xml/payruns_kanban.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
