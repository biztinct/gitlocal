# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string: no platform name in it.
    'name': 'Payobook Form builder: My Payobook page',
    'summary': "The administrator arranges the employee's My Profile page: sections, fields "
               "from a list, headings and a banner picture",
    'description': """
Form builder for the employee's own page on My Payobook (FORM STUDIO
programme, phase FS-12, owner ruling R30).

  * "Edit this page" on My Profile (tenant administrators only) and a card
    in Settings, System, Form builder open the page builder.
  * Sections with a title per language and one or two columns; fields
    dragged in from a list, ordered, half or full width, taken off again.
  * A header: heading and sub-line per language, an optional banner picture
    (JPG, PNG or WebP, at most 2 MB) and a tint from the locked palette.
  * Draft, preview as a chosen employee (look-only), Publish, history,
    restore and "Reset to the standard page".
  * Placing a field on the page is its "Show on My Payobook" tick; values and
    changes go through the Form builder engine's own portal rules.
  * Private phone, private e-mail, address and emergency contact: an
    "Employee can change it" switch each (on by default; off = look-only,
    refused on the server too).

Bridge module: My Profile is drawn from outside (template inheritance and
the portal controller); it creates nothing at install, and without a
published page My Profile is exactly as before.
""",
    'version': '19.0.1.3.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_form_studio',           # the engine: layouts, drafts, history, portal rules
        'pb_form_studio_people',    # the employee host and its R14 locked list
        'pb_form_studio_reach',     # the My details change path (R14) and R27 labels
        'pb_me_portal',             # My Profile
        'pb_me_details',            # the "Family, ID papers…" door
    ],
    'data': [
        'security/page_builder.xml',            # P8: the HR manager role builds the page
        'views/page_builder_actions.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        # Employees download only this stylesheet: no builder code (FS-12).
        'web.assets_frontend': [
            'pb_form_studio_portal/static/src/scss/my_page.scss',
        ],
        'web.assets_backend': [
            'pb_form_studio_portal/static/src/scss/page_builder.scss',
            'pb_form_studio_portal/static/src/js/page_builder.js',
            'pb_form_studio_portal/static/src/js/settings_card.js',
            'pb_form_studio_portal/static/src/xml/page_builder.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
