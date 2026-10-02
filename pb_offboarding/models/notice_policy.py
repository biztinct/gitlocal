# -*- coding: utf-8 -*-
"""How much notice somebody has to give.

Deliberately the smallest thing that answers the question. A notice period is a
NUMBER OF DAYS that depends on where a person works, and every attempt to model
it more finely than that (contract type, seniority, probation) turns into a
table nobody maintains and an expected date nobody trusts.

So: a country, a number of days, and a first-match read. HR overrides the date
on the approval anyway — the policy exists to stop the employee guessing, not to
decide anything.
"""

import logging

from odoo import api, fields, models, _

from .offboarding_common import P_NOTICE_DAYS, number

_logger = logging.getLogger(__name__)


class PbNoticePolicy(models.Model):
    _name = 'pb.notice.policy'
    _description = 'Notice Period Policy'
    _order = 'sequence, id'

    name = fields.Char(
        string='Policy', required=True, translate=True,
        help='What to call this on screen — "Vietnam, indefinite contract".')
    sequence = fields.Integer(default=10)
    country_id = fields.Many2one(
        'res.country', string='Country',
        help='Leave empty and this applies everywhere. Set a country and it is '
             'only used for people working there.')
    days = fields.Integer(
        string='Notice (days)', default=30, required=True,
        help='How many days between handing in a resignation and the last '
             'working day.')
    note = fields.Text(string='Notes')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Notice policy')

    # ------------------------------------------------------------- the answer
    @api.model
    def _as_employee(self, employee):
        """Accept a record OR an id.

        Both public entry points here are reachable over JSON-RPC, where a
        recordset argument arrives as a plain integer — and an integer walks
        straight past `if not employee`, answers False to every `getattr`, and
        the caller silently gets the fallback notice period instead of the
        country's. Coerce once, at the door, rather than in three callers.
        """
        if isinstance(employee, int):
            return self.env['hr.employee'].sudo().browse(employee).exists()
        if isinstance(employee, (list, tuple)) and employee:
            return self.env['hr.employee'].sudo().browse(
                int(employee[0])).exists()
        return employee

    @api.model
    def policy_for(self, employee):
        """The policy that covers this person. The country's own beats the
        shared one; a company's own beats a shared one; nothing found is not an
        error — the module falls back to its own parameter."""
        employee = self._as_employee(employee)
        if not employee:
            return self.browse()
        country = self._employee_country(employee)
        company_id = (employee.company_id or self.env.company).id
        base = [('active', '=', True),
                ('company_id', 'in', [False, company_id])]
        for extra in ([('country_id', '=', country)] if country else [],
                      [('country_id', '=', False)]):
            found = self.sudo().search(base + extra, order='sequence, id',
                                       limit=1)
            if found:
                return found
        return self.browse()

    @api.model
    def days_for(self, employee):
        """The notice this person owes, in days. Never raises, never zero."""
        employee = self._as_employee(employee)
        try:
            policy = self.policy_for(employee)
            if policy and policy.days > 0:
                return policy.days
        except Exception:               # noqa: BLE001 — a date, not a crash
            _logger.exception('pb_offboarding: notice policy lookup failed')
        return max(1, number(self.env, P_NOTICE_DAYS, 30))

    @api.model
    def _employee_country(self, employee):
        """Where they work. The same probe P0 uses, so the two agree."""
        if not employee:
            return False
        addr = getattr(employee, 'address_id', False)
        if addr and getattr(addr, 'country_id', False):
            return addr.country_id.id
        country = getattr(employee, 'country_id', False)
        if country:
            return country.id
        company = employee.company_id or self.env.company
        return company.country_id.id if company.country_id else False
