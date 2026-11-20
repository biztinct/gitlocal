# -*- coding: utf-8 -*-
{
    # The name and summary are what the Apps list prints: user-visible, so
    # plain words and no vendor name.
    'name': 'Form builder in reports',
    'summary': 'Split and filter reports by the fields you added with the Form builder',
    'description': """
FORM STUDIO programme, phase FS-8 ("Reports by your own fields").

In Insights › Explorer, a field added with the Form builder on the employee
record or on the contract, and marked "Show in lists", can be used to split
a report ("By") and to filter it ("Where"), on every report counted per
person or per payslip. Example: people by shirt size.

* Kinds offered: choice list, yes / no, short text, date (by month, quarter
  or year) and link to a record. Long text, files, numbers and money are not.
* Employee fields: each person's value as it is today. Contract fields: the
  value on the contract each payslip was made with.
* Only people who may see a field are offered it — checked on the server for
  every question, not only in the picker. A field limited to some Countries
  of Work shows "—" for people elsewhere.
* A saved report view that uses a field stops the field being deleted; if a
  field becomes unavailable, the view opens without it and says so once.

Silent install: creates no field, column, job, mail or setting. Nothing new
appears in the reports until such a field exists.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_form_studio',   # the fields, who may see them, their countries (fields_for)
        'pb_explorer',      # the reports: the run-time breakdown hooks (19.0.2.8.0)
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_form_studio_explorer/static/src/xml/form_builder_wording.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
