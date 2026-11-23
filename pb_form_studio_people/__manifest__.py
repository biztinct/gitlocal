# -*- coding: utf-8 -*-
{
    # The opening line of this description is what the Apps list prints, so
    # it is a USER-VISIBLE string: no platform name in it.
    'name': 'Payobook Form builder: employee record',
    'summary': "The administrator's own fields on the employee side panel, full page and "
               "Full details, and as People list filters",
    'description': """
Form builder on the employee record (FORM STUDIO programme, phase FS-2).

  * The side panel gets a "Company details" tab: the published sections of the
    Form builder, editable by HR with one Save, look-only for people who may
    read but not change the employee. The administrator opens the Form builder
    from the panel header.
  * The employee full page shows the same sections, look-only.
  * Full details has a "Form builder" button in its top bar for the
    administrator (R22), next to "Set up workflow".
  * Full details gets a "Company details" page, kept in step with every
    publish by the engine.
  * The People list offers custom choice, yes/no, link and date fields as
    filters.

Bridge module: it reaches the People screens from outside (inheritance and
patches only) and creates nothing at install.
""",
    'version': '19.0.1.9.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_form_studio',      # the engine: render / write_values / overlay / grid
        'pb_people',           # the People list, the full page, the people facade
        'pb_employee_vault',   # the side panel (Employee360Drawer)
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_form_studio_people/static/src/scss/people_form.scss',
            'pb_form_studio_people/static/src/js/people_form_patches.js',
            'pb_form_studio_people/static/src/xml/people_form_patches.xml',
            'pb_form_studio_people/static/src/js/employee_workspace.js',
            'pb_form_studio_people/static/src/xml/employee_workspace.xml',
            'pb_form_studio_people/static/src/js/premium_org_chart.js',
            'pb_form_studio_people/static/src/xml/premium_org_chart.xml',
            'pb_form_studio_people/static/src/scss/premium_org_chart.scss',
            # R22: the "Form builder" button on Full details.
            'pb_form_studio_people/static/src/js/full_form_button.js',
            'pb_form_studio_people/static/src/xml/full_form_button.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
