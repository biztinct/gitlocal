# -*- coding: utf-8 -*-
{
    'name': 'Week Grid',
    'summary': 'Generic, reusable editable weekly grid OWL component (spreadsheet feel)',
    'description': """
Framework-agnostic weekly-entry grid. A single adapter-driven OWL component
(<WeekGrid/>) that renders employee/resource rows against Mon–Sun day columns
with an editable primary measure + per-type chip measures, keyboard navigation,
dirty tracking, an undo stack, per-row revert and an explicit Save that surfaces
per-cell results. No HR / Payobook / country dependencies — reuse for timesheets,
roster hours, meal counts, overtime entry. Themeable via --bwg-* CSS custom props.
""",
    'version': '19.0.1.1.0',
    'category': 'Extra Tools',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'biz_week_grid/static/src/scss/week_grid.scss',
            'biz_week_grid/static/src/js/week_grid.js',
            'biz_week_grid/static/src/xml/week_grid.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
