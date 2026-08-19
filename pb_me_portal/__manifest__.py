# -*- coding: utf-8 -*-
{
    'name': 'Employee Self-Service Portal (ESS)',
    'summary': 'A branded /my employee hub — payslips, profile change-requests, '
               'self-upload documents and a tax sheet',
    'description': """
Sudima Phase I — ESS portal extensions (#18 ESS/MSS).

Extends the /my employee portal into a branded "My Payobook" hub and adds the
self-service pieces the stock portal lacked:

  * Profile change-request flow — an employee proposes changes to a small set of
    personal-contact fields; the change rides an Employee → HR approval chain and
    only the approved request writes the master, through ONE audited writer. ESS
    NEVER writes the employee master directly (C18.55e); the snapshot fields are
    sentinel-guarded (C18.31) and the editable set is a config whitelist.
  * Self-upload documents into the Phase-H vault (own-create record rule; HR
    still verifies — verified* stay sentinel-guarded); categories flagged
    ess_uploadable are the ones an employee may upload into.
  * A config-driven tax sheet — the PIT-relevant line codes per payslip plus a
    YTD summary, own slips only.
  * A full WOW re-skin of the whole /my surface (F–J rule): the home hub, the
    payslip list + detail, and the new pages are bespoke design-system UI. Bank
    changes stay in the Phase-D OCR flow (linked, not duplicated here).

Every route re-resolves the employee from the session user (C18.26); no route
accepts an employee_id for own-data pages (safety rail 3).
""",
    'version': '19.0.1.0.2',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'om_hr_payroll',        # payslip portal + HR payroll groups
        'pb_employee_vault',    # the document vault (self-upload target) + audit trail
        'biz_approval_chain',   # the approval-chain mixin the request rides
        'portal',
        'pb_import_kit',        # shared pbim design tokens
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_me_portal_security.xml',
        'data/pb_me_portal_data.xml',
        'views/profile_change_views.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        # a LEAN frontend bundle — pbim tokens + the .pbme components only;
        # backend assets are NOT leaked into the portal (handover §4.4).
        'web.assets_frontend': [
            'pb_import_kit/static/src/scss/import_tokens.scss',
            'pb_me_portal/static/src/scss/me_portal.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
