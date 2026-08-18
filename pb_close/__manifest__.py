# -*- coding: utf-8 -*-
{
    'name': 'Workforce Close',
    'summary': 'Day locks, the weekly Close ritual and the payroll handoff',
    'description': """
Workforce redesign P4 — the engine under Mission Control.

  * `pb.wf.lock` — one row per (company, day). A locked day is refused by EVERY
    writer that can touch the week: the punch table itself (create / write /
    unlink, both sides of a move), the Weekly-Entry grid, the bulk import (rows
    skipped with a reason, in the DRY RUN as well as the commit), an approved
    correction's apply, and all three overtime transitions. Reopening flips the
    row's state and REQUIRES a reason, which lands in the chatter — so a day's
    whole lock history survives in one place.
  * `pb.close` — the officer-gated facade behind the Close lens. It classifies
    every employee-day of a week LIVE (shifts + punches + grid entries + pending
    OT + the exception engine's missing-punch kinds) into clean / flagged /
    reviewed, and returns the payroll-handoff totals beside them.
  * `pb.close.review` — "approve as-is". A consciously waived flag, kept
    forever, never deleted by a reopen, and never writable for your own
    employee record.
  * A payroll-run ADVISORY: the run wizard's exception list gains one line per
    unclosed week in the period. It is appended after super() inside try/except
    and can never raise, never block and never skip a slip (the pb_young_worker
    cardinal rule).

WHAT A LOCK IS FOR
------------------
Not money. Nothing on the payroll path reads `hr.attendance` — OT hours are
grid-entered by design, so a punch could be rewritten a year later without
moving one payslip figure. A lock protects the AUDIT SUBSTRATE: the evidence
behind the decisions the week produced. The one exception is the overtime
guard, which IS a money path (`approved_hours` feeds the formula inputs), and it
is guarded for exactly that reason.

New code in this module NEVER reads the shift model's stored compliance-status
field (stale by construction: a stored compute over now(), no cron, and
`actual_check_*` never written by production code). Everything is derived live,
the shape `pb_today.py`:295-317 proved, and a grep gate keeps it so.
""",
    'version': '19.0.1.0.2',
    'category': 'Human Resources/Attendance',
    'license': 'LGPL-3',
    'author': 'Payobook',
    'website': 'https://www.payobook.com',
    'depends': [
        'pb_wf_kit',            # wf_context — the Close lens binds to the week
        'pb_hr_workforce',      # hr.shift.planning, the weekentry grid, OT
        'pb_attendance_flow',   # pb.attendance.rule tolerance + the exception engine
        'pb_time_hub',          # the person drawer the Close lens hands over to
        # A HARD dependency, not a soft hook: `_inherit = 'pb.payrun.wizard'`
        # is resolved when the registry is built, so a conditional import is
        # not available — the model has to exist. The advisory itself is still
        # incapable of affecting a run (see models/payrun_wizard.py).
        'pb_payrun_wizard',
        # soft-hooks (resolved via `in self.env`, never a hard dependency):
        #   pb.ot.ceiling      — the clean-batch headroom test
        #   hr.leave           — leave-day exclusion in the classifier
        #   hr.attendance.correction — the checklist's second tick
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/wf_lock_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
