# -*- coding: utf-8 -*-
"""How long a trial period is, and how the review around it is run.

Deliberately the same shape as `pb.notice.policy`: a country, a handful of
numbers, and a FIRST-MATCH read. Every attempt to model a probation period more
finely than that — by contract type, by seniority, by job family — turns into a
table nobody maintains and an end date nobody trusts.

Nothing found is not an error. The module falls back to its own parameters, so
a tenant that has never opened this screen still gets a working trial period.
"""

import logging

from odoo import api, fields, models, _

from .probation_common import (
    P_DURATION_MONTHS, P_EXTENSION_MONTHS, P_FEEDBACK_DAYS, P_GRACE_DAYS,
    P_LEAD_DAYS, add_months, number,
)

_logger = logging.getLogger(__name__)


class PbProbationPolicy(models.Model):
    _name = 'pb.probation.policy'
    _description = 'Probation Policy'
    _order = 'sequence, id'

    name = fields.Char(
        string='Policy', required=True, translate=True,
        help='What to call this on screen — "Vietnam — two months".')
    sequence = fields.Integer(default=10)
    country_id = fields.Many2one(
        'res.country', string='Country',
        help='Leave empty and this applies everywhere. Set a country and it is '
             'only used for people working there.')
    duration_months = fields.Integer(
        string='Trial period (months)', default=2, required=True,
        help='How long the trial period lasts, counted from the joining date.')
    evaluation_lead_days = fields.Integer(
        string='Start the review this many days early', default=21,
        required=True,
        help='How far before the end of the trial the review opens. Three '
             'weeks leaves room to ask colleagues, read the answers and have '
             'the conversation without rushing the decision.')
    feedback_window_days = fields.Integer(
        string='Colleagues have (days)', default=3, required=True,
        help='How long a colleague has to answer before their link closes.')
    extension_grace_days = fields.Integer(
        string='A deadline may be stretched by (days)', default=1,
        required=True,
        help='How much extra time the "give them another day" button adds. It '
             'can only be used once per review.')
    default_extension_months = fields.Integer(
        string='An extension adds (months)', default=1, required=True,
        help='How much longer a trial period runs when it is extended. The '
             'person deciding can still change it.')
    note = fields.Text(string='Notes')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('Probation policy')

    # ------------------------------------------------------------- the answer
    @api.model
    def _as_employee(self, employee):
        """Accept a record OR an id.

        Every public entry point here is reachable over JSON-RPC, where a
        recordset argument arrives as a plain integer — and an integer walks
        straight past `if not employee`, answers False to every `getattr`, and
        the caller silently gets the fallback duration instead of the country's
        (R43). Coerce once, at the door.
        """
        if isinstance(employee, int):
            return self.env['hr.employee'].sudo().browse(employee).exists()
        if isinstance(employee, (list, tuple)) and employee:
            return self.env['hr.employee'].sudo().browse(
                int(employee[0])).exists()
        return employee

    @api.model
    def _employee_country(self, employee):
        """Where they work. The same probe P0 and P4 use, so all three agree."""
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

    @api.model
    def policy_for(self, employee):
        """The policy that covers this person, or an empty recordset."""
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
    def settings_for(self, employee):
        """Every number this person's review needs, always answered.

        A dict rather than a record, because the caller wants five numbers and
        must not have to know whether a policy row exists. Never raises.
        """
        values = {
            'policy_id': 0,
            'policy_name': '',
            'duration_months': number(self.env, P_DURATION_MONTHS, 2),
            'evaluation_lead_days': number(self.env, P_LEAD_DAYS, 21),
            'feedback_window_days': number(self.env, P_FEEDBACK_DAYS, 3),
            'extension_grace_days': number(self.env, P_GRACE_DAYS, 1),
            'default_extension_months': number(self.env, P_EXTENSION_MONTHS, 1),
        }
        try:
            policy = self.policy_for(employee)
        except Exception:               # noqa: BLE001 — numbers, not a crash
            _logger.exception('pb_probation: policy lookup failed')
            policy = self.browse()
        if policy:
            values.update({
                'policy_id': policy.id,
                'policy_name': policy.name or '',
                'duration_months': policy.duration_months
                or values['duration_months'],
                'evaluation_lead_days': policy.evaluation_lead_days
                if policy.evaluation_lead_days > 0
                else values['evaluation_lead_days'],
                'feedback_window_days': max(1, policy.feedback_window_days)
                if policy.feedback_window_days
                else values['feedback_window_days'],
                'extension_grace_days': max(1, policy.extension_grace_days)
                if policy.extension_grace_days
                else values['extension_grace_days'],
                'default_extension_months': max(
                    1, policy.default_extension_months)
                if policy.default_extension_months
                else values['default_extension_months'],
            })
        return values

    @api.model
    def trial_end_for(self, employee, joined_on=None):
        """The day this person's trial period ends. Never raises.

        The joining date wins over anything derived: whoever opened the journey
        knew something the record did not (a re-hire, a transfer, a start not
        contracted yet), which is P0's ruling and this follows it.
        """
        employee = self._as_employee(employee)
        if not employee:
            return False
        start = joined_on
        if not start:
            try:
                start = employee._pb_join_date()
            except Exception:           # noqa: BLE001
                start = False
        if not start:
            return False
        months = self.settings_for(employee)['duration_months']
        if months <= 0:
            return False
        return add_months(start, months)
