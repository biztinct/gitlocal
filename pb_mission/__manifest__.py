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

P3b adds the ambient layer on top of that shell:

  * the **Needs-you dock** — a 268px right column, mounted once beside every
    lens, showing everything awaiting this user across FOUR models with inline
    approve and refuse-with-a-required-note. It reads `pb.team.get_team_data`
    (the queue the Team Approvals cockpit has always built) and every mutation
    rides `pb.team.act`, i.e. the target model's own gated method as the real
    user. Mount hooks and the 60-second poll READ; only click handlers write
    (W21/W21.1). Collapses to a 44px badge strip, remembered in localStorage.
  * a **hovercard** on each card, built from data already in the payload — no
    RPC, no new endpoint.
  * the **shell person surface** — one shared `<WfPersonWeek/>` drawer for the
    four lenses that do not own one, so a person pinned from anywhere opens
    somewhere.
  * the **⌘K palette** — lenses, people and actions, rendered through the Odoo
    overlay service so the shell's z-discipline (W37) is untouched, and the
    `pb_cmd` protocol that carries a palette action into a lens.

P4 turns the engine on inside the same shell:

  * the **Close lens** (mockup C) — the eighth lens and the only one that is
    not an embedded cockpit, because there was no Close surface to embed. Verb
    header, Mon-Sun day-lock chips, the clean/flagged/missing stat strip, the
    flagged table with scheduled-vs-actual bars and reason chips, and the
    payroll-handoff rail with its checklist and "Lock week & send to payroll".
    Every action is a click handler; `get_close_data` has no write path in it.
    Gated to the attendance/payroll MANAGER tiers, matching the locks it sets.
  * the dock's **clean batch** — OT items the server has certified as clean
    (requested hours match the grid, ceiling headroom is there, the day is not
    locked) get a footer that approves all of them through `pb.team.act`,
    sequentially, as the real user.

Still non-goals: employee shift acknowledgment and the shift-end pulse, both
descoped from P4 for want of an employee-facing workforce surface.

Nothing is deleted — all seven client actions stay registered and reachable, and
the retired rail items move to the 900 band (W18).

pbim tokens only (the command bar is the deep-indigo `--pbim-primary-dark`, not
a new navy), Lucide icons through the shared `ic()` registry, flat fills.
""",
    # 19.0.1.6.0 — IA Cycle 6: the workspace accepts `pb_cmd` on ARRIVAL, so a
    # foreign cockpit can deep link to a lens's own sub-view (Insights' bonus
    # tile → the Overtime desk's bonus review) instead of only to the lens.
    'version': '19.0.1.7.0',
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
        'pb_close',             # P4: pb.close / pb.wf.lock behind the Close lens
        'pb_sidebar',           # the single rail entry that replaces seven
        # IA Cycle 6: the shared back chip. A cockpit that deep-links INTO this
        # workspace writes `pb_back` on the context (openHub), and until now
        # only pb_hub's own HubShell rendered it — so an Insights drill landed
        # on the Time Off lens with no way home. The chip is imported, never
        # re-implemented: two return doors that look different are two doors.
        'pb_hub',
    ],
    'data': [
        'views/mission_action.xml',
        'data/pb_sidebar.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pb_mission/static/src/scss/pb_mission.scss',
            'pb_mission/static/src/scss/pb_dock.scss',
            'pb_mission/static/src/scss/pb_close_lens.scss',
            'pb_mission/static/src/js/pb_dock.js',
            'pb_mission/static/src/js/pb_close_lens.js',
            'pb_mission/static/src/js/pb_mission.js',
            'pb_mission/static/src/xml/pb_dock.xml',
            'pb_mission/static/src/xml/pb_close_lens.xml',
            'pb_mission/static/src/xml/pb_mission.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
