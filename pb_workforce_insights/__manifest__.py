# -*- coding: utf-8 -*-
{
    'name': 'Payobook Workforce Insights',
    'summary': 'Workforce analytics cockpit — attendance, overtime, leave and '
               'cost per head, on real data, with filters and drill-through',
    'description': """
Sudima Phase O — the Workforce Analytics cockpit.

Replaces the placeholder that used to occupy this slot: a 45-line component
living in the DEMO module, injected into the sidebar imperatively and with no
group restriction at all, drawing nine CSS-div bars with no filters, no hover,
no drill and no export — and whose every query was filtered ``is_demo = true``,
so on a real customer database it rendered completely empty.

This cockpit reads real operational data:

  * **Headcount & movement** — who was actually paid, joiners and leavers on a
    payroll basis, from the derived fact tables (``pb.fact.emp``).
  * **Attendance exceptions** — trend by week and by kind, worst departments,
    from ``pb.attendance.exception.engine`` (the same engine the Insights pulse
    uses, so the two surfaces cannot disagree).
  * **Overtime & bonus load** — hours by type and week, ceiling utilisation
    against ``pb.ot.ceiling``, and the overflow that became bonus hours.
  * **Leave** — who is away, what is awaiting approval, absence by month.
  * **Cost per head** — read from ``pb.fact.line`` so it matches the Analytics
    Explorer to the cent (asserted by a cross-surface parity test).

Every section is filterable (period · division · department), every figure
drills to the people behind it, and every soft dependency is probed so a
missing phase degrades to an honest "not installed" tile instead of a crash.
""",
    # C2/C18.86: bump on EVERY asset change — the bundle URL hash is keyed on
    # module versions, so without this browsers keep serving the stale CSS/JS.
    'version': '19.0.1.0.2',
    'category': 'Human Resources/Payroll',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    # pb_explorer supplies the fact tables + the shared chart geometry;
    # pb_import_kit the --pbim-* design tokens. Attendance, overtime and leave
    # are SOFT dependencies, probed at runtime.
    'depends': ['web', 'pb_hr_payroll_base', 'pb_import_kit', 'pb_explorer'],
    'data': [
        'views/pb_workforce_insights_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_workforce_insights/static/src/scss/workforce_insights.scss',
            'pb_workforce_insights/static/src/js/workforce_insights.js',
            'pb_workforce_insights/static/src/xml/workforce_insights.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
