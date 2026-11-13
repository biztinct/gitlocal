# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Overtime decisions vs a locked day (§3.2).

This is the ONE guard in P4 that is about money rather than about evidence.
``hr.overtime.request`` in state ``approved`` is read straight off the payroll
path — ``pb_workforce_payroll_bridge/models/hr_payslip.py``:27 pulls
``approved_hours`` / ``bonus_hours`` into the formula inputs — so a closed week
that can still grow new approved overtime is not closed at all: the payroll run
that was handed a clean week would compute a different answer if it were re-run.

All three transitions are guarded, not just approve. A submit on a closed day
would sit in the dock forever (nobody can decide it); a refuse would rewrite the
decision record of a week already handed over. Reopen the day, then decide.

The guard raises ValidationError, which ``pb.team.act`` catches and returns as
``{ok: False, error: …}`` — so in the dock this surfaces as the model's own
words on the card, and the row stays. Nothing is bypassed, nothing is silent.
"""

from odoo import _, models


class HrOvertimeRequest(models.Model):
    _inherit = 'hr.overtime.request'

    def _pb_lock_pairs(self):
        return [
            (rec.company_id.id or rec.employee_id.company_id.id, rec.date)
            for rec in self if rec.date
        ]

    def _pb_check_open(self, what):
        self.env['pb.wf.lock']._check_days_open(self._pb_lock_pairs(), what)

    def action_submit(self):
        # Only the records that would actually transition — the model itself
        # filters on state, and refusing a no-op would be a lie.
        self.filtered(lambda r: r.state == 'draft')._pb_check_open(
            _("Submitting this overtime"))
        return super().action_submit()

    def action_approve(self):
        self.filtered(lambda r: r.state == 'submitted')._pb_check_open(
            _("Approving this overtime"))
        return super().action_approve()

    def action_refuse(self):
        self.filtered(lambda r: r.state == 'submitted')._pb_check_open(
            _("Refusing this overtime"))
        return super().action_refuse()
