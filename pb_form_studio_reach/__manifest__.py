# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Form builder everywhere',
    'summary': 'Fields added with the Form builder reach pay formulas, Records and '
               'Updates sheets, Mapping, My Payobook, Access and the timeline',
    'description': """
FORM STUDIO programme, phase FS-5 ("Reach everywhere").

Custom fields made with the Form builder on the employee and the contract
reach the rest of the product, always through the engine's own helpers so
"who can see it" and "Country of Work" are respected on every surface:

* Pay formulas: fields marked "Use in pay formulas" are offered as payroll
  sources ("Company details: ..."); a formula or a mapping that uses a field
  stops it being deleted.
* Records (Master records) and therefore the Updates sheets.
* Mapping: a "Company details" lane on the board.
* My Payobook > My details: fields whose visibility is "Everyone", see only.
* Access: custom fields listed under their record type.
* Timeline: changes to custom fields, old to new (files: name only).

Silent install: creates no field, layout, job, mail or approval. Nothing
reaches anything until a custom field exists on a record type a screen has
registered with the Form builder.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_form_studio',          # the engine (fields_for, values, meta, finders)
        'pb_hr_payroll_formula',   # payroll sources (formula inputs), import mappings
        'pb_formula_studio',       # the Mapping board
        'pb_records',              # Master records (and so the Updates sheets)
        'pb_me_details',           # My Payobook > My details
        'biz_access',              # the Access catalogue hook
        'pb_employee_vault',       # audit wiring of employee + contract, timeline
        'pb_contracts',            # the contract drawer's History tab
    ],
    'data': [
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
