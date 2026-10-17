# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""ADVISORY — unclosed weeks surfaced on the payroll run (P4 §3.6).

Wraps `pb.payrun.wizard`'s two seams, calls super, then APPENDS one line per
unclosed week to the `exceptions` list the Run Payroll cockpit already renders.

THE CARDINAL RULE (cloned verbatim from pb_young_worker/models/payrun_wizard.py)
--------------------------------------------------------------------------------
It NEVER raises, NEVER blocks and NEVER skips a slip. Everything after `super()`
is inside try/except, and every helper below is inside another one. A week that
was not closed is a PROCESS problem for HR to resolve; refusing to pay people
over it would be the payroll engine taking a position it has no business taking.
The worst thing this file may ever do is stay silent.

THE TWO PATHS (§2's warning, same as the young-worker gate)
-----------------------------------------------------------
`pb_demo` replaces `create_and_compute` / `compute_batch` for its DIVISION path
WITHOUT calling super, so an MRO-INNER wrapper never runs on the demo world —
and measured on the live registry this module IS inner (`pb_demo -> pb_close ->
pb_young_worker -> pb_payrun_wizard`). The generic (salary-structure and
formula-config) path always calls super and is unaffected.

The division path is covered instead by `pb_demo._pb_demo_advisories`, which
calls `_close_append_exceptions` by name — the demo depending on the product
rather than the product depending on the demo.
`test_advisory.py::test_the_advisory_reaches_the_demo_division_path` accepts
either route and reports which one it found. (That test used to be called
`test_the_advisory_is_mro_outer_of_the_demo_path`; this reference was left
pointing at the old name and was corrected in P7.)

WHY THE MESSAGE HAS TWO SHAPES
------------------------------
The exact flag count comes from `pb.close`, which reads a week's shifts, punches
and overtime. On a 200-person department that is six batched queries; on the
4 500-employee demo world, over a month, it is a quarter of a million rows —
four times, once per week — and an advisory that adds ten seconds to every
payroll run is an advisory somebody will switch off. So above
`_EXACT_FLAGS_MAX_EMPLOYEES` the line reports only facts that are exact
`search_count`s (days locked, undecided overtime, undecided corrections), and
says so. Both shapes are TRUE; neither is an estimate.
"""

import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Above this headcount the advisory reports search_count facts only — see the
# module docstring. 500 is roughly a large single site; the demo world is 4 500.
_EXACT_FLAGS_MAX_EMPLOYEES = 500
# A payroll period is a month; more than this many unclosed weeks means the
# whole period is open, and thirty identical lines help nobody.
_MAX_WEEK_ROWS = 8


class PbPayrunWizardClose(models.AbstractModel):
    _inherit = 'pb.payrun.wizard'

    # ------------------------------------------------------------- helpers
    def _close_weeks_in(self, ds, de):
        """Every Monday whose week overlaps [ds, de]."""
        d0 = fields.Date.to_date(ds)
        d1 = fields.Date.to_date(de)
        if not d0 or not d1 or d1 < d0:
            return []
        cur = d0 - timedelta(days=d0.weekday())
        out = []
        while cur <= d1:
            out.append(cur)
            cur += timedelta(days=7)
        return out

    def _close_week_status(self, week_start, ds, de, emp_ids):
        """(days_locked, days_total, detail_or_None) for one week.

        `days_total` counts only the days of the week that fall inside the
        payroll PERIOD — a week straddling the month boundary is not "3 of 7
        unlocked" when four of those days belong to the previous run.
        """
        d0 = fields.Date.to_date(ds)
        d1 = fields.Date.to_date(de)
        days = [week_start + timedelta(days=i) for i in range(7)]
        days = [d for d in days if d0 <= d <= d1]
        if not days:
            return (0, 0, None)
        Lock = self.env['pb.wf.lock']
        locked = Lock._locked_dates(self.env.company, days)
        return (len([d for d in days if d in locked]), len(days), days)

    def _close_open_flags(self, week_start, emp_ids):
        """The exact open-flag count for a week, or None when it is too
        expensive to be worth a payroll run's time (see the module docstring)."""
        if not emp_ids or len(emp_ids) > _EXACT_FLAGS_MAX_EMPLOYEES:
            return None
        emps = self.env['hr.employee'].sudo().browse(emp_ids).exists()
        if not emps:
            return None
        Close = self.env['pb.close']
        dt = week_start + timedelta(days=6)
        today = fields.Date.context_today(self)
        rows, _stats, _totals = Close._classify(
            emps, week_start, dt, [week_start + timedelta(days=i)
                                   for i in range(7)], today)
        reviewed = Close._reviews(emps, week_start, dt)
        return len([r for r in rows
                    if (r['employee_id'], r['date'], r['kind']) not in reviewed])

    def _close_cheap_counts(self, week_start, ds, de, emp_ids):
        """Exact `search_count`s that cost one query each."""
        d0 = max(fields.Date.to_date(ds), week_start)
        d1 = min(fields.Date.to_date(de), week_start + timedelta(days=6))
        dom = [('date', '>=', d0), ('date', '<=', d1),
               ('state', '=', 'submitted')]
        if emp_ids:
            dom = [('employee_id', 'in', emp_ids)] + dom
        ot = self.env['hr.overtime.request'].sudo().search_count(dom)
        corr = 0
        if 'hr.attendance.correction' in self.env:
            corr = self.env['hr.attendance.correction'].sudo().search_count(dom)
        return ot, corr

    # ------------------------------------------------------------ the append
    def _close_append_exceptions(self, exceptions, emp_ids, ds, de):
        """Append one advisory row per UNCLOSED week. Mutates `exceptions`.

        The advisory is about the PERIOD, but `compute_batch` is called once
        per chunk of employees — so a run of 36 people over two chunks listed
        every week twice, and the summary line twice with it. What the reader
        saw was five weeks reported ten times, which reads as ten problems.

        Deduplicating on the sentence is the right key here: two rows saying
        the same thing about the same week ARE the same advisory, however many
        chunks produced them.
        """
        if not ds or not de:
            return exceptions
        weeks = self._close_weeks_in(ds, de)
        if not weeks:
            return exceptions
        emp_ids = [int(e) for e in (emp_ids or [])]

        rows, unclosed = [], 0
        for week_start in weeks:
            locked, total, days = self._close_week_status(
                week_start, ds, de, emp_ids)
            if not total or locked >= total:
                continue                       # this week IS closed
            unclosed += 1
            if len(rows) >= _MAX_WEEK_ROWS:
                continue
            label = week_start.strftime('%d %b')
            flags = self._close_open_flags(week_start, emp_ids)
            if flags is None:
                ot, corr = self._close_cheap_counts(week_start, ds, de, emp_ids)
                why = _(
                    "Week of %(w)s is not closed — %(l)s of %(t)s day(s) locked, "
                    "%(ot)s overtime and %(c)s correction(s) still undecided.",
                    w=label, l=locked, t=total, ot=ot, c=corr)
            else:
                why = _(
                    "Week of %(w)s is not closed — %(f)s flag(s) open, "
                    "%(l)s of %(t)s day(s) locked.",
                    w=label, f=flags, l=locked, t=total)
            rows.append({'emp': _("Workforce close"), 'why': why})

        if not unclosed:
            return exceptions
        rows.append({
            'emp': _("Workforce close"),
            'why': _(
                "%(n)s week(s) in this period have not been closed and locked. "
                "The run still computes — this is a note, not a block.",
                n=unclosed),
        })
        seen = {(r.get('emp'), r.get('why')) for r in exceptions}
        exceptions.extend(r for r in rows
                          if (r['emp'], r['why']) not in seen)
        return exceptions

    # ------------------------------------------------------------- the seams
    @api.model
    def create_and_compute(self, vals):
        result = super().create_and_compute(vals)
        try:
            if (isinstance(result, dict) and 'exceptions' in result
                    and not result.get('needs_confirmation')):
                emp_ids = []
                run_id = result.get('run_id')
                if run_id:
                    run = self.env['hr.payslip.run'].sudo().browse(run_id)
                    emp_ids = run.slip_ids.mapped('employee_id').ids
                self._close_append_exceptions(
                    result['exceptions'], emp_ids,
                    vals.get('date_start'), vals.get('date_end'))
        except Exception:
            # The advisory may never take a payroll run down with it.
            _logger.exception("workforce close advisory: create_and_compute")
        return result

    @api.model
    def compute_batch(self, payload):
        result = super().compute_batch(payload)
        try:
            if isinstance(result, dict) and 'exceptions' in result:
                self._close_append_exceptions(
                    result['exceptions'], payload.get('emp_ids') or [],
                    payload.get('date_start'), payload.get('date_end'))
        except Exception:
            _logger.exception("workforce close advisory: compute_batch")
        return result
