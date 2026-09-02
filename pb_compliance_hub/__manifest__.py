# -*- coding: utf-8 -*-
{
    'name': 'Payobook Compliance Hub',
    'summary': 'The Compliance mission — filings, bank verification, young '
               'workers and the audit trail as four lenses of one workspace',
    'description': """
IA redesign Cycle 4 — the Compliance mission.

Four surfaces that used to be four rail items become four lenses of one
workspace, in the order an obligation actually arrives:

    filings · bank · young · audit

What you owe an authority, what you owe an employee's bank account, who you may
not schedule after eight in the evening, and the trail proving all three. Every
lens is the EXISTING cockpit mounted with `embedded: true` (W17) — nothing here
reimplements a cockpit, nothing forks one, and all four standalone client
actions keep working, because the hub is ADDITIVE until the rail cutover in
Cycle 5. No menu and no `pb.sidebar.item`: the one door is a command-palette
entry, plus a per-lens sub-entry each.

**The gates are derived from what the model behind each lens actually grants**
(W95), and the four answers are all different, which is why the rule exists:

    filings  pb.govt.report.wizard   the Government Reports group
    bank     pb.bank.change.request  every internal user (an employee files
                                     their own bank change on this surface)
    young    pb.young.worker.guard   the facade's `_require_access` — HR user
                                     or attendance officer
    audit    pb.audit.console        the facade's `_require_manager` — payroll
                                     manager or system

A payroll OFFICER therefore sees three of the four lenses and the audit lens is
ABSENT rather than disabled, which is the shell's answer to a door the facade
would refuse (W29).
""",
    'version': '19.0.1.1.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_hub',                   # the shell kit + the global palette registry
        'pb_settings',              # the cog in the command bar opens this hub
        # the four surfaces this hub mounts as lenses
        'pb_govt_reports',
        'pb_bank_ocr',
        'pb_young_worker',
        'pb_audit',
    ],
    'data': [
        'views/pb_compliance_hub_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_compliance_hub/static/src/js/compliance_hub.js',
            'pb_compliance_hub/static/src/js/compliance_hub_palette.js',
            'pb_compliance_hub/static/src/xml/compliance_hub.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
