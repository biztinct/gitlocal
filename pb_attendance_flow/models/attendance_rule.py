# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.attendance.rule — the late/early grace policy as DATA (Phase G §3).

Grace minutes (in / out) and the open-checkout threshold are configuration, not
constants: the shift-compliance tolerance and the exception engine both read this
rule. Resolution is company-specific ELSE global (a company_id=False fallback row
ships as data). The resolver does TWO searches — never ``order='company_id
desc'``, which returns the NULL/global row AHEAD of the company one (C18.20).

Workforce P4 §3.1 extends the SAME row with the CLOSE tolerance — the threshold
that decides whether an employee-day is "clean" (auto-approved by the Close
ritual) or "flagged for review":

  * ``variance_minutes``    — per-punch tolerance against the scheduled shift;
  * ``variance_hours_week`` — per-week tolerance on Σ|actual − scheduled|.

They live HERE, not in a parallel config model, because grace and tolerance are
one policy answering one question ("how close to the plan is close enough?") and
two tables would drift the moment somebody tuned one of them. Resolution is the
same two-search company-else-global; the reader is
``pb.close._tolerance_for_company`` via ``_variance_for_company`` below.

Grace ≠ tolerance, deliberately: grace decides whether an arrival is called
LATE (a behavioural fact, 15 min by default), tolerance decides whether the DAY
needs a human before payroll sees it (10 min by default). A 12-minute late
arrival is late AND flagged; a 12-minute early finish is within grace and still
flagged. Merging them would force one number to answer both questions.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PbAttendanceRule(models.Model):
    _name = 'pb.attendance.rule'
    _description = 'Attendance Grace / Late Policy'
    _order = 'company_id, id'

    name = fields.Char(
        string='Name', required=True,
        default=lambda self: _('Attendance Rules'))
    # company_id may be False → the GLOBAL fallback used by every company that
    # has no rule of its own. A payroll-manager can add a per-company override.
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        help='Leave empty for the global default applied to every company that '
             'has no rule of its own.')
    active = fields.Boolean(default=True)

    grace_in_minutes = fields.Integer(
        string='Late Grace (min)', default=15,
        help='A check-in later than the shift start by more than this many '
             'minutes counts as late.')
    grace_out_minutes = fields.Integer(
        string='Early-Leave Grace (min)', default=15,
        help='A check-out earlier than the shift end by more than this many '
             'minutes counts as an early departure.')
    open_checkout_hours = fields.Integer(
        string='Open Check-out Threshold (h)', default=16,
        help='An attendance still open (no check-out) this many hours after '
             'check-in is flagged as a missing check-out.')
    # ------------------------------------------------- P4: close tolerance
    # The clean/flagged threshold the Close ritual classifies on. NOT the same
    # dimension as grace (see the module docstring): grace answers "is this
    # person late", tolerance answers "does this day need a human".
    variance_minutes = fields.Integer(
        string='Close Tolerance (min)', default=10,
        help='A punch within this many minutes of its scheduled shift start '
             'and end is CLEAN for the weekly Close — no review needed. '
             'Anything beyond it is flagged for a human.')
    variance_hours_week = fields.Float(
        string='Close Tolerance (h / week)', default=0.5, digits=(4, 2),
        help='Total scheduled-vs-actual difference an employee may accumulate '
             'over a week and still be CLEAN, even when every individual day '
             'is within the per-punch tolerance.')

    # Present in config, UNUSED in Phase G (report-only world): future payroll
    # wiring for turning a late count into a deduction. Documented as a non-goal.
    count_late_as = fields.Selection(
        [('report_only', 'Report only'),
         ('deduct_flag', 'Flag for deduction (future)')],
        string='Late Counting', default='report_only', required=True,
        help='Phase G only REPORTS late/early. The deduction flag is reserved '
             'for future payroll wiring and is currently unused.')

    _grace_in_bounds = models.Constraint(
        'CHECK(grace_in_minutes >= 0 AND grace_in_minutes <= 120)',
        'Late grace must be between 0 and 120 minutes.')
    _grace_out_bounds = models.Constraint(
        'CHECK(grace_out_minutes >= 0 AND grace_out_minutes <= 120)',
        'Early-leave grace must be between 0 and 120 minutes.')
    _open_checkout_bounds = models.Constraint(
        'CHECK(open_checkout_hours >= 1 AND open_checkout_hours <= 72)',
        'The open-checkout threshold must be between 1 and 72 hours.')
    # W33: `models.Constraint`, never `_sql_constraints = [...]` — Odoo 19 logs
    # one warning and then ignores the list, so the CHECK silently would not
    # exist in PostgreSQL at all.
    _variance_minutes_bounds = models.Constraint(
        'CHECK(variance_minutes >= 0 AND variance_minutes <= 240)',
        'The close tolerance must be between 0 and 240 minutes.')
    _variance_week_bounds = models.Constraint(
        'CHECK(variance_hours_week >= 0 AND variance_hours_week <= 40)',
        'The weekly close tolerance must be between 0 and 40 hours.')

    @api.constrains('company_id', 'active')
    def _check_single_active(self):
        """At most one active rule per scope (per company, and one global)."""
        for rule in self:
            if not rule.active:
                continue
            dom = [('id', '!=', rule.id), ('active', '=', True),
                   ('company_id', '=', rule.company_id.id or False)]
            if self.sudo().search_count(dom):
                raise ValidationError(_(
                    "There is already an active attendance rule for this scope "
                    "(%s). Deactivate it first.",
                    rule.company_id.name or _('Global')))

    # ---------------------------------------------------------- resolver
    @api.model
    def _for_company(self, company):
        """The active rule for `company`, else the global (company_id=False)
        fallback, else an empty recordset. TWO searches — a single ordered
        search would return the global row first on DESC (C18.20)."""
        company = company or self.env.company
        Rule = self.sudo()
        rule = Rule.search(
            [('active', '=', True), ('company_id', '=', company.id)], limit=1)
        if not rule:
            rule = Rule.search(
                [('active', '=', True), ('company_id', '=', False)], limit=1)
        return rule

    @api.model
    def _grace_for_company(self, company):
        """(grace_in_min, grace_out_min, open_checkout_h) — falling back to the
        Phase-B defaults (15 / 15 / 16) when no rule exists at all, so behaviour
        is identical to the pre-Phase-G hardcode when the module is bare."""
        rule = self._for_company(company)
        if rule:
            return (rule.grace_in_minutes, rule.grace_out_minutes,
                    rule.open_checkout_hours)
        return (15, 15, 16)

    @api.model
    def _variance_for_company(self, company):
        """(variance_minutes, variance_hours_week) for the Close ritual.

        Same company-else-global resolution as `_grace_for_company`, and the
        same "behave like the hardcode when the module is bare" fallback: P4's
        defaults are 10 min / 0.5 h. A rule row that exists but has never been
        migrated cannot answer 0 by accident — a stored 0 is a legitimate
        "everything must be exact" policy, so only the ABSENCE of a rule falls
        back.
        """
        rule = self._for_company(company)
        if rule:
            return (rule.variance_minutes, rule.variance_hours_week)
        return (10, 0.5)
