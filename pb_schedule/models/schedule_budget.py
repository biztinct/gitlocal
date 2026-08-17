# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""``pb.schedule.budget`` — one optional labour-cost budget per scope per week.

WHY A MODEL AND NOT A SETTING
-----------------------------
A budget is a number an operations manager changes every few weeks, per
department, and wants to see against the roster they are building. A config
parameter cannot be scoped or dated; a field on hr.department cannot be dated
either. So: a tiny table keyed on (company, department, week).

DELIBERATELY OPTIONAL
---------------------
No row means the strip shows scheduled and actual cost and NOTHING else. It
does not show "0 / 0" or a full red bar. A fabricated zero budget would make
every unbudgeted department look catastrophically overspent, which is how a
useful instrument becomes an ignored one.

THE NULL-DEPARTMENT TRAP (W30)
------------------------------
The natural uniqueness rule is `unique(company_id, department_id, week_start)`,
and in PostgreSQL that constraint does NOT stop two company-wide rows: NULLs are
distinct under a plain UNIQUE index, so `(1, NULL, 2026-03-02)` can be inserted
any number of times and the "unique" constraint reports nothing. The SQL
constraint is kept (it is the cheap guard for the department-scoped rows) and a
Python `@api.constrains` covers the company-wide case it structurally cannot.

GATES (P2 §3.4)
---------------
Read: attendance officer and up — the same tier that may read the roster the
budget is about. Write: attendance MANAGER or payroll MANAGER. Enforced twice on
purpose: `ir.model.access` keeps the ORM honest for any generic caller, and
`_pb_check_edit` keeps it honest for the cockpit's own facade, which runs as the
officer and must not be able to talk its way past the ACL through a helper.
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_EDIT_GROUPS = (
    'hr_attendance.group_hr_attendance_manager',
    'om_hr_payroll.group_hr_payroll_manager',
)


class PbScheduleBudget(models.Model):
    _name = 'pb.schedule.budget'
    _description = 'Schedule Labour Budget'
    _order = 'week_start desc, department_id'
    _rec_name = 'week_start'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company, ondelete='cascade')
    department_id = fields.Many2one(
        'hr.department', string='Department', index=True, ondelete='cascade',
        help='Leave empty for a company-wide budget.')
    week_start = fields.Date(
        string='Week', required=True, index=True,
        help='The Monday of the budgeted week. Normalized on write.')
    amount = fields.Monetary(
        string='Labour budget', required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        related='company_id.currency_id', string='Currency', readonly=True)

    _sql_constraints = [
        ('scope_week_uniq', 'unique(company_id, department_id, week_start)',
         'There is already a labour budget for that department and week.'),
    ]

    # ------------------------------------------------------------- guards
    @api.model
    def _pb_can_edit(self):
        u = self.env.user
        return u.has_group('base.group_system') or any(
            u.has_group(g) for g in _EDIT_GROUPS)

    @api.model
    def _pb_check_edit(self):
        if not self._pb_can_edit():
            raise AccessError(_(
                "Only an attendance manager or a payroll manager can set a "
                "labour budget."))

    @api.constrains('company_id', 'department_id', 'week_start')
    def _check_company_wide_uniqueness(self):
        """W30: a plain SQL UNIQUE lets NULL department_id repeat forever."""
        for rec in self:
            if rec.department_id:
                continue
            dupe = self.search_count([
                ('id', '!=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('department_id', '=', False),
                ('week_start', '=', rec.week_start),
            ])
            if dupe:
                raise ValidationError(_(
                    "There is already a company-wide labour budget for the "
                    "week of %s.", rec.week_start))

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_("A labour budget cannot be negative."))

    # --------------------------------------------------------- normalizing
    @api.model
    def _monday(self, day):
        """Snap any day to the Monday of its week.

        The cockpit always sends a Monday (wf_context normalizes), but a budget
        row created from the native form or an import would otherwise land on a
        Wednesday and silently never match the strip's lookup.
        """
        d = fields.Date.to_date(day)
        return d - timedelta(days=d.weekday())

    # ---------------------------------------------------------------- CRUD
    @api.model_create_multi
    def create(self, vals_list):
        self._pb_check_edit()
        for vals in vals_list:
            if vals.get('week_start'):
                vals['week_start'] = self._monday(vals['week_start'])
        return super().create(vals_list)

    def write(self, vals):
        self._pb_check_edit()
        if vals.get('week_start'):
            vals['week_start'] = self._monday(vals['week_start'])
        return super().write(vals)

    def unlink(self):
        self._pb_check_edit()
        return super().unlink()
