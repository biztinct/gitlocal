# -*- coding: utf-8 -*-
{
    'name': 'Schedule',
    'summary': 'The Workforce roster as a canvas: cost, coverage and conscience',
    'description': """
Workforce redesign P2 — the Shift Roster becomes an instrument.

The Gen-0 grid (`shift_planning_grid`) had the right skeleton — employees ×
days, coloured shift cards, open shifts, a leave overlay, copy-week, publish —
in a 2013 body, and it could not answer the three questions a scheduler
actually has:

  * **what does this week cost?**  `hr.contract._pb_hourly_rate()` (P2 §3.3) is
    the one display-math rate contract; the stats strip prints scheduled hours,
    scheduled cost and (for settled days) actual cost per day, against an
    optional `pb.schedule.budget` row;
  * **is Tuesday covered?**  `hr.shift.coverage.requirement` states the demand
    side that did not exist at day grain anywhere, and the coverage overlay
    turns it into a chip on every day header;
  * **should I really put Lan on nights?**  `check_shift()` answers before the
    save, and Copy Week revalidates every target and REFUSES the ones that
    would land on leave, on a conflict, or over a young worker's night ban.

Ceiling warnings are advisory by design (overflow becomes bonus hours); the one
hard rule surfaced pre-save is pb_young_worker's night constraint, which the
server still enforces on save — the UI only stops asking.

pbim tokens, Lucide icons via the shared `ic()` registry, flat fills, and the
shared `wf_context` for department/week/search (W4). No payroll money path is
touched: the rate helper is a READ helper for display aggregates only (W12).
""",
    'version': '19.0.1.5.3',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_wf_kit',            # wf_context + WfContextBar / WfDrawer / WfPersonWeek
        'pb_import_kit',        # pbim tokens + the shared Lucide ic() registry
        'pb_hr_workforce',      # hr.shift.planning / .template / .grid, om_hr_payroll
        'pb_time_hub',          # pb.time.hub.get_person_week — the shared person drawer
        'pb_sidebar',           # the rail entry this cockpit repoints
        # NOT pb_young_worker: its night rule is probed with `in self.env` and
        # degrades to silence. NOT hr_shift either — it declares a DIFFERENT
        # model that is also called hr.shift.planning (hr_shift/models/
        # shift_planning.py:15) and nothing here may touch it.
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/shift_template_views.xml',
        'views/pb_schedule_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_schedule/static/src/scss/pb_schedule.scss',
            'pb_schedule/static/src/js/pb_schedule.js',
            'pb_schedule/static/src/xml/pb_schedule.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
