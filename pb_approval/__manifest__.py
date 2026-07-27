# -*- coding: utf-8 -*-
{
    'name': 'Payobook Approval Cockpit',
    'summary': 'Three-tier payroll approval pipeline (Officer → HR → Finance) '
               'with model-side tier gates and reject-with-reason',
    'description': """
Sudima Phase L — the payroll approval chain as a 3-lane pipeline board.

  * Lanes: Officer review → HR review → Finance approval, per-tier KPIs and
    total net at stake; cards carry a 3-dot chain stepper.
  * Cards the current user actually owns are highlighted and carry
    Approve / Reject; the rest render read-only with a "waits on <role>" chip.
  * Reject asks for a required reason, stored on the run as testimony.

Read-and-act facade (C18.55a): every decision calls hr.payslip.run's own gated
action as the real user. Enforcement is model-side (pb_payruns
_pb_require_tier) — this module's group gate is defence in depth, never the
guard. No mail is sent from this module.
""",
    'version': '19.0.1.2.1',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_payruns owns the approval chain (the level0 tier, the tier gate and the
    # rejection fields this cockpit reads).
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_payruns', 'pb_import_kit'],
    'data': [
        'views/pb_approval_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_approval/static/src/scss/approval.scss',
            'pb_approval/static/src/js/pba_icons.js',
            'pb_approval/static/src/js/approval.js',
            'pb_approval/static/src/xml/approval.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
