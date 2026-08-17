# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The punch guard — ``hr.attendance`` create / write / unlink on a locked day.

§2's measured fact: **hr.attendance has no state and no period guard anywhere**.
Core's write override only blocks moving a punch to a foreign employee, and
``pb_attendance_flow``'s own guard covers ``unlink()`` alone (the ``_CORR_TOKEN``
sentinel, hr_attendance.py:42-58) — there has never been a ``write()`` guard of
any kind. Six writers reach this table: a direct officer write, the Weekly-Entry
grid, the import wizard, an approved correction's ``_apply``, the driver PWA's
live punch, and raw ``call_kw``. Guarding each of them separately would be six
places to forget; guarding the ORM is one.

BOTH SIDES OF A MOVE ARE CHECKED
--------------------------------
A write that MOVES a punch off a locked day is exactly as destructive as one
that moves it onto a locked day — it removes the evidence from the closed week.
So a write is refused when either the record's CURRENT day or its NEW day is
locked, and the message names the day that actually stopped it.

SUDO DOES NOT OPEN THIS
-----------------------
Deliberately: the correction workflow's single writer ``_apply()`` runs sudo'd
(a line manager who may approve a report's correction has no direct
hr.attendance write right), and it must still be stopped by a lock. Only the
explicit ``wf_lock_bypass`` context UNDER ``env.su`` opens the guard — see
wf_lock.py. The result is the behaviour §3.2 asks for: an approved correction on
a locked day lands ``refused`` with ``apply_error``, because that is what
``action_approve`` already does with a ValidationError from the apply.
"""

from odoo import _, api, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    # ------------------------------------------------------------- helpers
    def _pb_lock_pairs(self, extra_check_in=None):
        """[(company_id, local_day)] for these punches.

        `extra_check_in` is the NEW check_in of a pending write, so the caller
        can ask about the destination day in the same batch as the origin one.
        """
        Lock = self.env['pb.wf.lock']
        cache = {}
        pairs = []
        for att in self:
            emp = att.employee_id
            if not emp:
                continue
            cid = emp.company_id.id
            if att.check_in:
                pairs.append((cid, Lock._local_day(emp, att.check_in, cache)))
            if extra_check_in:
                pairs.append((cid, Lock._local_day(emp, extra_check_in, cache)))
        return pairs

    @api.model
    def _pb_lock_pairs_for_vals(self, vals_list):
        """[(company_id, local_day)] for a list of create vals."""
        Lock = self.env['pb.wf.lock']
        Emp = self.env['hr.employee'].sudo()
        cache = {}
        emp_cache = {}
        pairs = []
        for vals in vals_list:
            eid = vals.get('employee_id')
            ci = vals.get('check_in')
            if not eid or not ci:
                continue
            emp = emp_cache.get(eid)
            if emp is None:
                emp = Emp.browse(int(eid)).exists()
                emp_cache[eid] = emp
            if not emp:
                continue
            ci = self._pb_as_datetime(ci)
            if not ci:
                continue
            pairs.append((emp.company_id.id, Lock._local_day(emp, ci, cache)))
        return pairs

    @api.model
    def _pb_as_datetime(self, value):
        from odoo import fields as _f
        try:
            return _f.Datetime.to_datetime(value)
        except (TypeError, ValueError):
            return False

    # ---------------------------------------------------------------- CRUD
    @api.model_create_multi
    def create(self, vals_list):
        Lock = self.env['pb.wf.lock']
        Lock._check_days_open(
            self._pb_lock_pairs_for_vals(vals_list),
            _("Adding a punch"))
        return super().create(vals_list)

    def write(self, vals):
        # Only a write that TOUCHES the punch's placement can violate a lock —
        # a `pb_entry_source` restamp or a computed field refresh must stay free,
        # or every recompute in the system starts asking the lock table.
        watched = {'check_in', 'check_out', 'employee_id'}
        if watched.intersection(vals):
            new_ci = (self._pb_as_datetime(vals['check_in'])
                      if vals.get('check_in') else None)
            self.env['pb.wf.lock']._check_days_open(
                self._pb_lock_pairs(extra_check_in=new_ci),
                _("Editing this punch"))
        return super().write(vals)

    def unlink(self):
        self.env['pb.wf.lock']._check_days_open(
            self._pb_lock_pairs(), _("Deleting this punch"))
        return super().unlink()
