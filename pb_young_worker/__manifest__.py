# -*- coding: utf-8 -*-
{
    'name': 'Young Worker Rules (Under-18 Compliance Guard)',
    'summary': 'Config-driven under-18 hour caps, OT/night blocks and a compliance cockpit',
    'description': """
Sudima Phase E — Young Worker Rules (#10).

Age-banded working-time compliance for under-18 employees, driven entirely by
config (Vietnam Labor Code values ship as DATA, not code):

  * Config: per-company rule with age bands (daily/weekly hour caps, absolute OT
    block, night-work block). VN defaults: <15 → 4 h/day · 20 h/week · no OT ·
    no night; 15–<18 → 8 h/day · 40 h/week · no OT · no night. Adults = no band.
  * Four enforcement gates — three HARD (raise a friendly ValidationError), one
    ADVISORY: OT requests (hard), daily attendance cap (hard), night-shift
    assignment (hard), payroll run warnings (advisory — never blocks a slip).
  * Young Worker Guard cockpit: under-18 roster with days-to-18 countdown chips
    and week-hours gauges, a 30-day violation feed, and the VN band table.

Missing birthday ≠ minor: treated as adult for the gates (no false blocks) and
surfaced in the cockpit as a data-quality task. Nothing is hardcoded — all ages
and caps are config records.
""",
    'version': '19.0.1.0.2',
    'category': 'Human Resources',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # VN Labor Code defaults are seeded per-company here (the caps are DATA, but
    # a static XML record can't target the demo company, which is not
    # base.main_company) — see hooks.py.
    'post_init_hook': 'post_init_hook',
    'depends': [
        'hr',
        'hr_attendance',
        'pb_hr_workforce',
        'pb_payrun_wizard',
        'pb_sidebar',
        'pb_import_kit',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/pb_young_worker_security.xml',
        'views/young_worker_views.xml',
        'views/young_worker_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_young_worker/static/src/scss/pb_young_worker.scss',
            'pb_young_worker/static/src/js/pbyw_icons.js',
            'pb_young_worker/static/src/js/pb_young_worker.js',
            'pb_young_worker/static/src/xml/pb_young_worker.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
