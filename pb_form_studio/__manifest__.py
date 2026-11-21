# -*- coding: utf-8 -*-
{
    'name': 'Payobook Form builder',
    'summary': 'Let the administrator add their own fields to record screens',
    'description': """
Form builder engine (FORM STUDIO programme, phase FS-1).

The tenant administrator adds real fields (text, long text, whole number,
decimal, money, yes/no, date, choice list, link to a record, file) to record
screens, places them in sections, decides who may see them and in which
countries of work they apply, and publishes the layout. Host screens register
themselves through `pb.form.studio._pbfs_hosts()` and draw the published
sections with `PbFieldGrid`; the Studio itself is `FormStudioOverlay`, opened
through `useFormStudio`. See docs/handovers/formstudio/FS1_REPORT.md, section
"THE HOST CONTRACT".

Silent install: no field, layout, job, mail or approval is created.
""",
    'version': '19.0.1.6.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # Engine only: never a screen module (pb_people, pb_contracts, …). `hr`
    # supplies the HR-staff permission and three of the link targets;
    # pb_import_kit the tokens and the button primitives.
    'depends': ['base', 'web', 'bus', 'hr', 'pb_import_kit'],
    'data': [
        'security/ir.model.access.csv',
        'security/form_studio_rules.xml',
        'views/form_studio_actions.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_form_studio/static/src/scss/form_studio.scss',
            'pb_form_studio/static/src/js/fs_icons.js',
            'pb_form_studio/static/src/js/fs_words.js',
            'pb_form_studio/static/src/js/country_picker.js',
            'pb_form_studio/static/src/js/field_grid.js',
            'pb_form_studio/static/src/js/studio_overlay.js',
            'pb_form_studio/static/src/js/use_form_studio.js',
            'pb_form_studio/static/src/js/form_studio_service.js',
            'pb_form_studio/static/src/js/field_library.js',
            'pb_form_studio/static/src/js/dev_host.js',
            'pb_form_studio/static/src/js/settings_card.js',
            'pb_form_studio/static/src/xml/field_grid.xml',
            'pb_form_studio/static/src/xml/country_picker.xml',
            'pb_form_studio/static/src/xml/studio_overlay.xml',
            'pb_form_studio/static/src/xml/field_library.xml',
            'pb_form_studio/static/src/xml/dev_host.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
