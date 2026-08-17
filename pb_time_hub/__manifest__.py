# -*- coding: utf-8 -*-
{
    'name': 'Time Hub',
    'summary': 'One Workforce surface for time: Timeline · Week Grid · Exceptions · Import',
    'description': """
Workforce redesign P1a — the flagship Option-A merge.

Three sidebar items become one hub with lens tabs over the same attendance
dataset: Timecards (rebuilt as the Timeline lens), Weekly Entry (embedded as
the Week Grid lens) and Attendance Control (embedded twice, as the Exceptions
and Import lenses). Nothing is re-implemented — the lenses are the existing
cockpit components mounted with `embedded="true"` (W17), so there is one
component, one facade and two mount points per surface, never a fork.

  * `pb.time.hub` — the hub's own facade, officer-gated:
      - `get_hub_summary()`  the exception ribbon's sentence + lens badges,
        computed through the SAME cohort/window the Exceptions lens uses, so
        the two counts cannot disagree;
      - `get_person_week()`  the person drawer's payload — scheduled / actual /
        entered / delta per day, OT chips, compliance. The data contract lives
        in the model docstring and every later phase inherits it;
      - `get_timeline()`     the gated read-model behind the Timeline lens.
  * The person drawer — the owner's named pain point ("one employee's time as a
    table") answered from ANY avatar in ANY lens, without leaving the surface.

Department, week and person come from the shared `wf_context` (W4); the hub
ships no private pickers. pbim indigo tokens, Lucide icons, no gradients.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_wf_kit',            # wf_context + WfContextBar / WfDrawer / WfRibbon
        'pb_import_kit',        # pbim tokens + the shared Lucide ic() registry
        'pb_hr_workforce',      # hr.attendance.weekentry + the Week Grid lens
        'pb_attendance_flow',   # pb.attendance.flow + the Exceptions/Import lens
        # soft-hook (resolved via `in self.env`): pb_business_trip contributes
        # trip days to the drawer and trip bars to the Timeline read-model.
    ],
    'data': [
        'views/time_hub_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_time_hub/static/src/scss/time_hub.scss',
            'pb_time_hub/static/src/js/timeline_lens.js',
            'pb_time_hub/static/src/js/time_hub.js',
            'pb_time_hub/static/src/xml/time_hub.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
