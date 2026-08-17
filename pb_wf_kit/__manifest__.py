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

  * `wf_context` service — reactive { departmentId, weekStart, personId, search,
    day }, persisted to localStorage (`pbwf.ctx.v1`), with set(patch) /
    onChange(cb). `set()` is the ONLY write door (W16) — it normalizes, keeps
    `day` inside the week (same weekday when the week moves), persists, and
    notifies. All week maths is LOCAL-date; toISOString() is never used on a
    wall-clock day (it slips a day in every non-UTC timezone).
  * `<WfContextBar/>` — department dropdown, week nav, day pill, person
    typeahead. Each segment is opt-in through the `features` prop. Degrades to
    week-only when the persona cannot read hr.department / hr.employee.
  * `<WfDrawer/>`  — the right-side person-drawer chassis (ESC / backdrop close).
  * `<WfPersonWeek/>` — the drawer BODY: one employee's week as a table
    (scheduled / actual / entered / Δ), OT chips, compliance, and the doors
    onwards. Lifted out of pb_time_hub in P1b so the Today board mounts the same
    panel instead of forking it (W6). Pure presentation — the host fetches
    `pb.time.hub.get_person_week` and owns both actions, because filing a
    correction WRITES and writes belong to event handlers (W21).
  * `<WfRibbon/>`  — the exception ribbon (amber / rose / green).
  * `<WfCommandPalette/>` — P3b's Command-K: lenses, people and actions in one
    input. The host mounts it through the Odoo OVERLAY service, so it lives in
    `.o-overlay-container` and paints above a lens's modals without the shell
    stacking any chrome of its own (W37). The people group runs the same
    debounced `hr.employee.name_search` as the context bar — one person-search
    behaviour in Workforce, not two — and its empty state names the fact that
    this database has no `unaccent` (W40).
  * `WF_ROW_CAP`   — the one row budget every Workforce read-model shares
    (§2.6); the capping facades mirror it and pb_today's static test asserts
    they all still agree.

pbim-tokenized throughout, Lucide icons via pb_import_kit's shared ic() registry.
""",
    'version': '19.0.1.5.1',
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
            'pb_wf_kit/static/src/js/wf_rows.js',
            'pb_wf_kit/static/src/js/wf_context_service.js',
            'pb_wf_kit/static/src/js/wf_context_bar.js',
            'pb_wf_kit/static/src/js/wf_drawer.js',
            'pb_wf_kit/static/src/js/wf_person_week.js',
            'pb_wf_kit/static/src/js/wf_ribbon.js',
            'pb_wf_kit/static/src/js/wf_command_palette.js',
            'pb_wf_kit/static/src/xml/wf_kit.xml',
        ],
        # Loaded only by /web/tests — never part of the backend bundle.
        'web.assets_unit_tests': [
            'pb_wf_kit/static/tests/**/*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
