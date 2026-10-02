# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Weekly-Entry grid vs a locked day — a refusal the CELL can explain.

The hr.attendance ORM guard already stops the grid: its writers go through
``create``/``write``/``unlink`` like everybody else, and the per-cell savepoint
in ``save_week_entries`` catches the ValidationError. But it catches it as the
generic ``'exc'`` code, which the grid renders as "Could not be saved." — a
message that tells an officer nothing and sends them to a log they cannot read.

So the two cell writers are guarded HERE as well, one level up, and they return
a full sentence instead of a code. The grid's client already surfaces an
unrecognised `error` string verbatim (``attendance_weekgrid.js``:190-205 only
substitutes the codes it knows), so this needs no client change at all — and
the existing ``'locked'`` code is NOT reused, because it already means something
else on that screen ("already submitted or approved").

The ORM guard stays the backstop: this is a message, not a wall.
"""

from odoo import _, models


class AttendanceWeekEntry(models.TransientModel):
    _inherit = 'hr.attendance.weekentry'

    def _pb_day_locked(self, emp, d):
        Lock = self.env['pb.wf.lock']
        if Lock._bypass():
            return False
        return Lock._is_locked(emp.company_id or self.env.company, d)

    def _pb_locked_msg(self, d):
        return _("%s is closed for payroll — ask a manager to reopen the day.",
                 d.strftime('%d %b'))

    def _save_reg(self, emp, d, hours, token, att_map, shift_map):
        if self._pb_day_locked(emp, d):
            return False, self._pb_locked_msg(d)
        return super()._save_reg(emp, d, hours, token, att_map, shift_map)

    def _save_ot(self, emp, d, ot_type, hours, cfgs, holidays):
        if self._pb_day_locked(emp, d):
            return False, self._pb_locked_msg(d), None
        return super()._save_ot(emp, d, ot_type, hours, cfgs, holidays)
