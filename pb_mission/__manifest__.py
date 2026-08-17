# -*- coding: utf-8 -*-
{
    'name': 'Mission Control',
    'summary': 'The Workforce workspace: one command bar, one lens rail, seven cockpits',
    'description': """
Workforce redesign P3a — "stop navigating; stay in the room".

Seven rail items become ONE. Workforce is now a single full-height workspace: a
command bar carrying the shared context, a left rail of seven lenses, and a
full-bleed canvas that hosts the existing cockpits as embedded guests.

  * `pb_workforce` — the shell's client action. It is the only thing this module
    ships: no models, no ACLs, no server logic, no new RPC. Every call the
    lenses make already existed.
  * The seven lenses are the EXISTING components mounted with `embedded="true"`
    (W17): Today · Schedule · Time · Time Off · Overtime · Trips · Approvals.
    Nothing is re-implemented and nothing is forked — `embedded` suppresses only
    the title/hero chrome the shell itself now carries.
  * ONE `<WfContextBar/>`, in the command bar, with a per-lens feature map
    (W4): the department, week and day segments appear for the lenses that
    actually scope by them, and the person typeahead is always there because it
    is the command bar's search. Switching lens PRESERVES the context — that is
    the whole point of the shell.
  * Arrival routing reuses the hub deep-link protocol rather than inventing a
    second one (W26): `context.pb_shell_lens` names the lens to open, and
    `pb_lens` / `pb_focus` are forwarded to the Time hub as a synthetic action
    context. Today's "File correction" therefore stays INSIDE the workspace —
    it becomes a lens switch, not a doAction to another screen.
  * Each lens sits in a definite-height flex box (W20), because five of the
    seven scroll themselves and three of those pin sticky chrome to their own
    root.

Binding non-goals for this phase: no Needs-you dock, no person popover, no
Command-K palette (all P3b); no engine work (P4). Nothing is deleted — all seven
client actions stay registered and reachable, and the retired rail items move to
the 900 band (W18).

pbim tokens only (the command bar is the deep-indigo `--pbim-primary-dark`, not
a new navy), Lucide icons through the shared `ic()` registry, flat fills.
""",
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_wf_kit',            # wf_context + the ONE WfContextBar
        'pb_import_kit',        # pbim tokens + the shared Lucide ic() registry
        'pb_today',             # Today lens
        'pb_schedule',          # Schedule lens
        'pb_time_hub',          # Time lens (and the W26 arrival protocol)
        'pb_timeoff',           # Time Off lens
        'pb_hr_workforce',      # Overtime lens
        'pb_business_trip',     # Trips lens
        'pb_team',              # Approvals lens
        'pb_sidebar',           # the single rail entry that replaces seven
    ],
    'data': [
        'views/mission_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_mission/static/src/scss/pb_mission.scss',
            'pb_mission/static/src/js/pb_mission.js',
            'pb_mission/static/src/xml/pb_mission.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
