# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.close.review`` — "approve as-is": a flag somebody consciously waived.

A closed week is only defensible if the exceptions in it were LOOKED AT. The
Close board's second action therefore does not clear a flag, it RECORDS a human
deciding that the flag is acceptable — who, when, and optionally why. The board
then subtracts it from the outstanding count so the week can be locked.

THREE PROPERTIES, EACH DELIBERATE
---------------------------------
* **Kept forever.** A review is the evidence that the variance was seen. Reopening
  a week does NOT delete its reviews — the officer who reopens is adding to the
  day's history, not erasing it, and the second close should not require
  re-waiving the same seven flags.
* **Manager tier.** Waiving a flag is the act that lets a week reach payroll,
  which is the same authority as locking it. The gate is on the MODEL (W31), so
  the facade — which runs as an OFFICER — physically cannot be a softer door.
* **Never your own row.** The P1a `_ot_can_decide` spirit: an employee waiving
  the variance on their own attendance is signing off on their own payslip
  inputs. Refused even for a manager; admin excepted, because somebody has to be
  able to repair a database.

The natural key is (company, employee, date, kind) — one waiver per flag, so
clicking "approve as-is" twice is idempotent rather than double-counting. The
week is stored alongside it because that is how the board reads it back, and
because a flag's week never changes after the fact.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

# The flag kinds a review may waive. Kept as data beside the classifier that
# produces them (close.py `_KINDS`) so a typo cannot invent a waiver for a flag
# that does not exist — W29's "a door that can only produce an error".
REVIEW_KINDS = ('missing_punch', 'missing_checkout', 'variance_over',
                'unscheduled_day', 'ot_pending', 'week_variance')

_REVIEW_GROUPS = (
    'hr_attendance.group_hr_attendance_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)


class PbCloseReview(models.Model):
    _name = 'pb.close.review'
    _description = 'Close Review (flag waived as-is)'
    _order = 'week_start desc, date desc, id desc'
    _rec_name = 'date'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company, ondelete='cascade')
    week_start = fields.Date(string='Week', required=True, index=True)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade')
    date = fields.Date(string='Day', required=True, index=True)
    kind = fields.Selection(
        [(k, k.replace('_', ' ').capitalize()) for k in REVIEW_KINDS],
        string='Flag', required=True, index=True)
    note = fields.Char(string='Note')
    reviewer_id = fields.Many2one(
        'res.users', string='Reviewed by', required=True, readonly=True,
        default=lambda self: self.env.user)
    reviewed_at = fields.Datetime(
        string='Reviewed on', required=True, readonly=True,
        default=fields.Datetime.now)

    # W33: models.Constraint. One waiver per flag — a second click is a no-op,
    # not a second row that would make the board's subtraction go negative.
    _flag_uniq = models.Constraint(
        'unique(company_id, employee_id, date, kind)',
        'That flag has already been reviewed.')

    # ------------------------------------------------------------- gates
    @api.model
    def _pb_can_review(self):
        u = self.env.user
        if self.env.su or u._is_admin():
            return True
        for g in _REVIEW_GROUPS:
            try:
                if u.has_group(g):
                    return True
            except (ValueError, KeyError):
                continue
        return False

    @api.model
    def _pb_check_review(self):
        if not self._pb_can_review():
            raise AccessError(_(
                "Waiving a Close flag is restricted to attendance managers and "
                "payroll managers — it is what lets the week reach payroll."))

    def _pb_check_not_self(self):
        """No self-review. Resolved by explicit search on the session user
        (C18.26 — never `env.user.employee_id`, which is company-dependent and
        would answer False for exactly the multi-company case that matters)."""
        if self.env.su or self.env.user._is_admin():
            return
        me = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1)
        if not me:
            return
        for rec in self:
            if rec.employee_id.id == me.id:
                raise AccessError(_(
                    "You cannot waive a flag on your own attendance — that is "
                    "signing off on your own payslip inputs."))

    @api.constrains('week_start', 'date')
    def _check_day_in_week(self):
        for rec in self:
            if not rec.week_start or not rec.date:
                continue
            if not (rec.week_start <= rec.date <= rec.week_start + timedelta(days=6)):
                raise ValidationError(_(
                    "A review's day must fall inside its week."))

    # ---------------------------------------------------------------- CRUD
    @api.model
    def _monday(self, day):
        d = fields.Date.to_date(day)
        return d - timedelta(days=d.weekday())

    @api.model_create_multi
    def create(self, vals_list):
        self._pb_check_review()
        for vals in vals_list:
            if vals.get('week_start'):
                vals['week_start'] = self._monday(vals['week_start'])
            elif vals.get('date'):
                vals['week_start'] = self._monday(vals['date'])
        recs = super().create(vals_list)
        recs._pb_check_not_self()
        return recs

    def write(self, vals):
        self._pb_check_review()
        return super().write(vals)

    def unlink(self):
        self._pb_check_review()
        return super().unlink()
