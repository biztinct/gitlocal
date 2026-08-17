# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``hr.shift.coverage.requirement`` — the demand side of the roster.

WHY THIS MODEL HAS TO EXIST
---------------------------
P1b's audit looked for a day-grain demand signal in this codebase and found
none. `pb.workforce.demand.line` is role × MONTH (a planning artefact, useless
for "is Tuesday covered?"), and `hr.job.no_of_recruitment` is a recruiting
counter. The supply side has always been there — shift rows per day. So the
roster could show you what you had scheduled and never what you needed, which
is the difference between a calendar and an instrument.

THE RESOLUTION RULES (P2 §3.5, binding — read this before changing anything)
----------------------------------------------------------------------------
A requirement row states "this scope needs N people on this day". Four axes,
resolved in a fixed order:

  1. **Scope.** When the roster is filtered to a department, that department's
     rows are used; a company-wide row (no department) applies only when the
     department has no row of its own. Specific beats general — a department
     that has stated its own number is not also subject to the company's.
  2. **Date beats weekday.** A weekday row is the standing rule ("Saturdays
     need 4"); a date row is the exception ("this Saturday needs 9"). When both
     exist for the same key the date row wins outright — it does not add.
  3. **Template.** A row with no template states a DAY TOTAL. Rows with a
     template state per-shift requirements, and the day total is then their
     sum. A day-total row, if present, is authoritative and the per-template
     rows are reported alongside it for detail.
  4. **Supply** is the count of `draft` + `published` shifts on the day. NOT
     `completed`: coverage is a forward-looking planning instrument, and on this
     demo world pb_demo completes every past punched shift, so counting
     completed rows would turn "was last Tuesday staffed" into the question the
     Exceptions queue already answers better.

Absent rows mean absent chips. A department that has never stated a requirement
sees no coverage marks at all, rather than a wall of rose gaps against an
implied zero.

GATES
-----
Same as `pb.schedule.budget` (§3.4): officer reads, attendance manager or
payroll manager writes, enforced on the model so no facade helper can soften it.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_EDIT_GROUPS = (
    'hr_attendance.group_hr_attendance_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)

WEEKDAYS = [
    ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'), ('3', 'Thursday'),
    ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday'),
]


class ShiftCoverageRequirement(models.Model):
    _name = 'hr.shift.coverage.requirement'
    _description = 'Shift Coverage Requirement'
    _order = 'date desc, weekday, department_id'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company, ondelete='cascade')
    department_id = fields.Many2one(
        'hr.department', string='Department', index=True, ondelete='cascade',
        help='Leave empty for a company-wide requirement. A department with a '
             'requirement of its own is not also subject to the company one.')
    weekday = fields.Selection(
        WEEKDAYS, string='Weekday',
        help='The standing rule. Leave empty and set a date for a one-off.')
    date = fields.Date(
        string='Specific date',
        help='A one-off requirement. When both exist, the date wins.')
    template_id = fields.Many2one(
        'hr.shift.template', string='Shift', ondelete='cascade',
        help='Leave empty to state a requirement for the whole day.')
    required_headcount = fields.Integer(
        string='People needed', required=True, default=1)
    active = fields.Boolean(default=True)

    # W33: Odoo 19 ignores `_sql_constraints` (one registry warning, then
    # nothing). `models.Constraint` is the supported form.
    _headcount_positive = models.Constraint(
        'CHECK(required_headcount >= 0)',
        'A coverage requirement cannot be negative.',
    )

    # -------------------------------------------------------------- guards
    @api.model
    def _pb_can_edit(self):
        u = self.env.user
        return u.has_group('base.group_system') or any(
            u.has_group(g) for g in _EDIT_GROUPS)

    @api.model
    def _pb_check_edit(self):
        if not self._pb_can_edit():
            raise AccessError(_(
                "Only an attendance manager or a payroll manager can change "
                "coverage requirements."))

    # `company_id` is in the trigger list ON PURPOSE (W34): Odoo validates a
    # constraint on CREATE only when one of its fields is present in the vals
    # or has a default. A row with NEITHER weekday NOR date therefore skipped
    # this check entirely — the one case it exists to catch.
    @api.constrains('weekday', 'date', 'company_id')
    def _check_exactly_one_when(self):
        for rec in self:
            if bool(rec.weekday) == bool(rec.date):
                raise ValidationError(_(
                    "A coverage requirement needs either a weekday (the "
                    "standing rule) or a specific date (the exception) — "
                    "exactly one of them."))

    @api.constrains('company_id', 'department_id', 'weekday', 'date',
                    'template_id')
    def _check_no_duplicate_rule(self):
        """Two rows for the same key would make the answer depend on row order."""
        for rec in self:
            dupe = self.search_count([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('department_id', '=', rec.department_id.id or False),
                ('weekday', '=', rec.weekday or False),
                ('date', '=', rec.date or False),
                ('template_id', '=', rec.template_id.id or False),
            ])
            if dupe:
                raise ValidationError(_(
                    "There is already a coverage requirement for that scope, "
                    "day and shift."))

    # ---------------------------------------------------------------- CRUD
    @api.model_create_multi
    def create(self, vals_list):
        self._pb_check_edit()
        return super().create(vals_list)

    def write(self, vals):
        self._pb_check_edit()
        return super().write(vals)

    def unlink(self):
        self._pb_check_edit()
        return super().unlink()

    # ------------------------------------------------------------ display
    def _pb_label(self):
        self.ensure_one()
        when = self.date and fields.Date.to_string(self.date) or dict(
            WEEKDAYS).get(self.weekday, '')
        where = self.department_id.name or _('Company-wide')
        what = self.template_id.name or _('Whole day')
        return '%s · %s · %s' % (where, when, what)
