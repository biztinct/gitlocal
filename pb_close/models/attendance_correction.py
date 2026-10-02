# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Correction workflow vs a locked day (§3.2).

Two different behaviours on purpose, because they answer two different moments:

  * **submit** — a hard, friendly refusal. Filing a correction for a day nobody
    can apply it to is a request that exists only to be rejected later, and it
    pollutes every approver's queue in the meantime. The officer is told at the
    point they can still do something about it (ask for a reopen).

  * **approve** — NO raise. The model already runs ``_apply()`` in a savepoint
    and turns a ValidationError into ``state = refused`` + ``apply_error``
    (attendance_correction.py:212-235, the young-worker precedent). A day locked
    BETWEEN submit and approve therefore lands the correction in `refused` with
    the lock message as its reason, which is exactly §3.2's requirement: the
    refusal is a fact on the record, not a traceback in the middle of an apply.

    The guard is written into ``_apply`` rather than left to the hr.attendance
    ORM guard so the reason reads as a sentence about the WEEK ("the week is
    closed for 15 Aug") rather than as a sentence about a punch — but both paths
    end in the same place, and the ORM guard remains the backstop if a future
    correction type writes through some other door.
"""

from odoo import _, models


class HrAttendanceCorrection(models.Model):
    _inherit = 'hr.attendance.correction'

    def _pb_lock_pairs(self):
        return [(rec.company_id.id or rec.employee_id.company_id.id, rec.date)
                for rec in self if rec.date]

    def action_submit(self):
        # Raised BEFORE super so nothing has advanced — the request stays in
        # draft and the officer can move the date or ask for a reopen.
        self.env['pb.wf.lock']._check_days_open(
            self._pb_lock_pairs(), _("Submitting this correction"))
        return super().action_submit()

    def _apply(self):
        # Inside the caller's savepoint. A ValidationError here is CAUGHT by
        # action_approve and recorded as `apply_error` — never re-raised.
        self.env['pb.wf.lock']._check_days_open(
            self._pb_lock_pairs(), _("Applying this correction"))
        return super()._apply()
