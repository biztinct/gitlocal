# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""pb.attendance.rule — the late/early grace policy as DATA (Phase G §3).

Grace minutes (in / out) and the open-checkout threshold are configuration, not
constants: the shift-compliance tolerance and the exception engine both read this
rule. Resolution is company-specific ELSE global (a company_id=False fallback row
ships as data). The resolver does TWO searches — never ``order='company_id
desc'``, which returns the NULL/global row AHEAD of the company one (C18.20).
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
