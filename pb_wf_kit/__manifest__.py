# -*- coding: utf-8 -*-
{
    'name': 'Workforce Kit',
    'summary': 'Shared Workforce UI seam — context service, context bar, drawer, ribbon',
    'description': """
Workforce redesign P0 — the kit every Workforce surface builds on (W6).

No models, no ACLs, no server logic: this module ships ONE service and THREE
OWL components, so that P1's Today board and Time hub and P3's Mission Control
shell all consume the same department/week/person selection instead of forking
their own pickers (W4).

  * `wf_context` service — reactive { departmentId, weekStart, personId, search },
    persisted to localStorage (`pbwf.ctx.v1`), with set(patch) / onChange(cb).
    All week maths is LOCAL-date; toISOString() is never used on a wall-clock
    day (it slips a day in every non-UTC timezone).
  * `<WfContextBar/>` — department dropdown, week nav, person typeahead. Each
    segment is opt-in through the `features` prop. Degrades to week-only when
    the persona cannot read hr.department / hr.employee.
  * `<WfDrawer/>`  — the right-side person-drawer chassis (ESC / backdrop close).
  * `<WfRibbon/>`  — the exception ribbon (amber / rose / green).

pbim-tokenized throughout, Lucide icons via pb_import_kit's shared ic() registry.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'web',
        'pb_theme',
        'pb_import_kit',
    ],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'pb_wf_kit/static/src/scss/wf_kit.scss',
            'pb_wf_kit/static/src/js/wf_context_service.js',
            'pb_wf_kit/static/src/js/wf_context_bar.js',
            'pb_wf_kit/static/src/js/wf_drawer.js',
            'pb_wf_kit/static/src/js/wf_ribbon.js',
            'pb_wf_kit/static/src/xml/wf_kit.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
