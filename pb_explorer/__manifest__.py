# -*- coding: utf-8 -*-
{
    'name': 'Payobook Analytics Explorer',
    'summary': 'Interactive payroll analytics workbench over a derived fact table '
               '— compose any measure by any dimension, drill every cell, explain every delta',
    'description': """
Sudima Phase N — Analytics Explorer, Narrative & Ask.

Replaces the dead "Reports & analysis" gallery (13 cards over two legacy modules
whose KPIs were hardcoded, whose charts never rendered and whose totals could not
be non-zero) with ONE workbench backed by a derived fact table.

  * **Fact engine** — ``pb.fact.run`` / ``pb.fact.line`` / ``pb.fact.emp``,
    rebuilt from payslip truth by ``pb.fact.builder``. Measured on the live demo
    world: 711,150 payslip lines collapse to ~6,000 fact rows (119:1), so a
    pivot that took 11.3 s against ``hr_payslip_line`` answers in milliseconds.
    Totals reconcile exactly to the stored ``pb_total_net`` roll-ups.
  * **Explorer** — measure x dimension x time grain x filters, six chart forms,
    every cell drillable to the employees behind it (keyed on ID, never on the
    translated display name).
  * **Narrative** — variance waterfall over the matched-employee set, anomaly
    rail, cohort heatmap and a "why is this number what it is" trace.
  * **Ask** — a natural-language bar that compiles to a VISIBLE, editable chip
    spec, with a deterministic keyword fallback when no LLM is configured (C1).

Doctrine: ``pb.explorer`` is a read-only facade (gate on the real user, then
sudo the reads); ``pb.fact.builder`` is the only writer. All assets are local —
Chart.js comes from Odoo's own lazy ``web.chartjs_lib`` bundle, never a CDN.
""",
    # C2/C18.86: bump on EVERY asset change — the bundle URL hash is keyed on
    # module versions, so without this browsers keep serving the stale CSS/JS.
    'version': '19.0.1.0.5',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_import_kit supplies the shared --pbim-* design tokens + primitives;
    # pb_insights supplies the cockpit precedent this one is a sibling of.
    'depends': ['web', 'om_hr_payroll', 'pb_hr_payroll_base', 'pb_payruns',
                'pb_import_kit', 'pb_insights'],
    'data': [
        'security/ir.model.access.csv',
        'views/pb_explorer_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_explorer/static/src/scss/explorer.scss',
            'pb_explorer/static/src/js/pbex_icons.js',
            'pb_explorer/static/src/js/pbex_charts.js',
            'pb_explorer/static/src/js/explorer.js',
            'pb_explorer/static/src/xml/explorer.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
