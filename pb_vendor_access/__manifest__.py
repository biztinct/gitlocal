# -*- coding: utf-8 -*-
{
    'name': 'Payobook Vendors & Access',
    'summary': 'The suppliers HR deals with and when their agreements run out '
               '— and the Payobook role catalogue the Access home reads',
    'description': """
RIZE phase P11, and the Payobook half of ACCESS P6.

WHAT THIS MODULE IS

  * **A vendor register that tells you before it is too late.** Agencies,
    training providers, insurers, software suppliers — who they are, who here
    owns the relationship, and what has been agreed with them. Every agreement
    carries its dates and its files, and its state is COMPUTED from the calendar
    rather than typed, so it can never say "Running" about something that ended
    last March. A nightly job tells the owner while there is still time to do
    something, and escalates to HR once it has run out.
  * **Renewal is a new record, never an edit.** What was agreed last year is a
    fact about last year. Renewing prefills a fresh agreement from the old one,
    marks the old one replaced and keeps both.
  * **THE PAYOBOOK WORDS ON THE ACCESS HOME.** The Access home itself — roles,
    abilities, hand-overs, the People passport, the Screens lens and the role
    builder — is `biz_access`, and it belongs to no product. This module is what
    makes it say Payobook: the areas roles are grouped under (Payroll, People,
    Lifecycle, Money & budgets, System), the catalogue of roles and the
    abilities they are built from, which roles open which entry on the left
    menu, the Tenant administrator bundle, and the fact that a lifecycle
    administrator here also manages access. Every one of those is a
    REGISTRATION rather than an edit: the generic module is told, and never
    made to know.
  * **A role for the person who runs a customer's own application.** On a
    platform where one database belongs to one customer, "administrator" has
    meant the system administrator permission — the view editor, every model's
    raw table, the module list, the switch that turns developer mode on. That
    is the platform's, not the customer's. So "Tenant administrator" is a role
    like any other: the administrator tier of pay, people, joining and leaving,
    budgets, reporting, the connected systems, the calculation rules, the
    supplier register, the audit trail, and who here can do what — and nothing
    at all outside the application. Growth plans are deliberately left out of
    it; they are given separately, on purpose.

THE ONE ABSOLUTE. Nothing here can ever hand out the system administrator
permission (`base.group_system` / `base.group_erp_manager`). It is excluded from
the seeded catalogue, and there is a test that walks the whole implied closure of
every ability this module seeds and fails if one of them reaches it.

WHAT IT DELIBERATELY IS NOT. No supplier invoicing, no purchase orders, no
approval chain on a hand-over (notifications are the requirement and they are
enough), and no new permission system. `vendor_license_core` — the product's own
self-licensing — shares a word with this module and nothing else; it is not
touched, referenced or imported.

pbim tokens only, `.pbva-*` class names, Lucide icons through the shared `ic()`
registry, flat fills, one accent. No emoji.
""",
    'version': '19.0.1.6.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'base',
        'hr',
        'mail',
        'biz_access',           # the Access home this module puts Payobook's
                                # own words on — models, facade, cockpit, the
                                # sidebar role lane and the forbidden-group
                                # rails all live there now
        'pb_lifecycle',         # the reminder/letter patterns + the HR tiers
                                # the vendor rules and the ACL name directly
        'pb_employee_vault',    # the attachment + expiry-cron canon
        'pb_import_kit',        # pbim tokens/primitives + the shared ic() set
        'pb_hub',               # HubShell's back chip, openHub, the ⌘K registry
        'pb_settings',          # the cog this module's two panels bolt onto
        'pb_sidebar',           # the left menu this module puts its role gates
                                # on. Already here through pb_settings; named
                                # because this module writes to the MODEL, not
                                # just to whatever happens to be installed
                                # alongside.
        'pb_assets',            # `pb.asset` — the vendor_id link
        'pb_budget',            # `pb.budget.expense` — the optional vendor link
    ],
    'data': [
        'security/pb_vendor_access_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'data/mail_template_data.xml',
        'views/vendor_access_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_vendor_access/static/src/scss/vendors.scss',
            # the leaf component first, then the file that names its doors
            'pb_vendor_access/static/src/js/vendors_board.js',
            'pb_vendor_access/static/src/js/vendor_palette.js',
            'pb_vendor_access/static/src/xml/vendors_board.xml',
        ],
    },
    # R84 — this fires on INSTALL only, never on `-u`. `ensure_catalogue()` is
    # public so it can be run again by hand or from a later migration.
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
}
