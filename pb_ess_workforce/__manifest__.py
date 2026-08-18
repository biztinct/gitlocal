# -*- coding: utf-8 -*-
{
    'name': 'ESS Workforce',
    'summary': 'The employee-facing workforce surface: my schedule + shift '
               'acknowledgment, my timesheet + own-punch fixes, my leave, my '
               'overtime — plus the token-URL ack and the anonymous shift pulse',
    'description': """
Workforce redesign P8 — the employee half of Mission Control.

Seven phases built the manager's surfaces. This one builds the employee's, and
in doing so closes the two P4 descopes that could not exist without it: shift
ACKNOWLEDGMENT (an employee has to have somewhere to press "got it") and the
shift PULSE (somebody has to be asked).

WHAT IS HERE
------------
  * A "My Work" section of the existing /my portal (four pages, portal-auth):
    My Schedule, My Timesheet, My Leave, My Overtime.
  * `hr.shift.planning` acknowledgment — `ack_state` / `acked_at` / `ack_token`,
    minted at publish, confirmable from the portal OR from a login-less token
    URL mailed to the employee (`/work/ack/<token>`).
  * `pb.shift.pulse` — an anonymous end-of-shift rating with NO employee link at
    all, aggregated onto the Today board above an anonymity floor.
  * Manager-side read receipts: per-person ack badges on the Schedule cockpit
    and a publish result that says how many people were actually notified.

THE SECURITY MODEL (this module's whole point — read this before editing it)
---------------------------------------------------------------------------
  1. EVERY portal read resolves the employee from the SESSION USER by explicit
     search (C18.26). No route, no facade method and no form field anywhere in
     this module accepts an employee_id — not as a parameter it validates, as
     one it never reads. A crafted id has nothing to reach.
  2. The shift / overtime reads are sudo, scoped to the resolved own employee,
     exactly as pb_me_portal reads the own profile: the ROUTE BOUNDARY is the
     gate. No ACL is widened for `hr.shift.planning` or `hr.overtime.request`,
     so a plain internal user calling those models directly over call_kw is
     still refused outright.
  3. Every MUTATION rides an existing chain AS THE REAL USER (W12): a punch fix
     is an `hr.attendance.correction` (target forced server-side — I-H3), a
     leave is a plain `hr.leave` in the normal approval flow. This module has no
     write path to a punch, a payslip or an approval state.
  4. The ack write is the ONE sudo mutation, and it writes exactly two fields
     (`ack_state`, `acked_at`) behind a module-level `object()` sentinel that
     cannot be forged over JSON-RPC (C18.24). Everything else on the shift —
     the times, the employee, the state — is frozen against it.
  5. The pulse accepts NO identity at its RPC boundary and stores none. Its
     double-submit guard is a salted daily hash, and the Today tile refuses to
     render an aggregate below the anonymity floor SERVER-side.
""",
    'version': '19.0.1.0.1',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'portal',
        'pb_me_portal',         # the /my ESS surface + its pbim frontend bundle
        'pb_hr_workforce',      # hr.shift.planning, hr.overtime.request, the grid facade
        'pb_attendance_flow',   # hr.attendance.correction — the punch-fix chain
        'pb_timeoff',           # the leave facade's vocabulary (own-scope reads)
        # WP-3/WP-4 need the two manager surfaces the handover asks us to extend.
        # They are hard deps, not soft hooks: both extensions are `_inherit` of a
        # model declared there, which the registry resolves at load time.
        'pb_time_hub',          # pb.time.hub._person_week — the person-week contract
        'pb_schedule',          # get_schedule_data — the ack badges ride its payload
        'pb_today',             # pb.today — the Team pulse tile
    ],
    'post_init_hook': 'post_init_hook',
    'data': [
        'security/ir.model.access.csv',
        'security/pb_ess_workforce_security.xml',
        'views/portal_templates.xml',
        'views/ack_templates.xml',
    ],
    'assets': {
        # The same LEAN frontend bundle pb_me_portal established: pbim tokens
        # (already contributed by pb_me_portal) + this module's portal block.
        # No backend assets at all: the manager-side ack badge and the Team
        # pulse tile are rendered by pb_schedule's and pb_today's OWN templates
        # from an ADDITIVE payload key this module contributes server-side, so
        # the markup lives beside the component that owns it and there is no
        # cross-module OWL patching (and no second file in web.assets_backend
        # that could take the whole bundle down — W74).
        'web.assets_frontend': [
            'pb_ess_workforce/static/src/scss/ess_workforce.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
