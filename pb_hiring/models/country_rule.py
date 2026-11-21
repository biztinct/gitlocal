# -*- coding: utf-8 -*-
"""Who recruits for where.

ONE SMALL TABLE, AND NOTHING IS SEEDED INTO IT. A rule that names a recruiter
is a statement about a real person on a real desk, and guessing one is worse
than admitting there is none: the request is still approved, the board says
plainly that no recruiter has been named, and the daily job nudges the hiring
administrators until somebody says who it is (R54 — a thing that is not set up
and does not SAY so is reported as broken).

A ROW WITH NO COUNTRY IS THE FALLBACK for its company, which is what makes a
single-country business a one-row table. The lookup asks for the country first
and falls back once; it never falls back to another company (R8/R16 — a scoped
answer that leaks across companies is worse than no answer).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .hiring_common import as_id

_logger = logging.getLogger(__name__)


class PbHiringCountryRule(models.Model):
    _name = 'pb.hiring.country.rule'
    _description = 'Hiring rule'
    _order = 'company_id, country_id'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    country_id = fields.Many2one(
        'res.country', string='Country', index=True,
        help='Leave this empty and the rule covers every country in the '
             'company that has no rule of its own.')
    recruiter_id = fields.Many2one(
        'res.users', string='Recruiter', required=True,
        domain="[('share', '=', False)]",
        help='Who picks a hiring request up once it has been agreed.')
    recruiter_manager_id = fields.Many2one(
        'res.users', string="Recruiter's manager",
        domain="[('share', '=', False)]",
        help='Told at the same time, so somebody senior knows the role is '
             'live even if the recruiter is away.')
    active = fields.Boolean(string='In use', default=True)
    note = fields.Text(string='Note')

    _company_country_uniq = models.Constraint(
        'unique(company_id, country_id)',
        'That company already has a hiring rule for that country.')

    @api.constrains('company_id', 'country_id', 'active')
    def _check_one_fallback(self):
        """Postgres keeps NULLs distinct, so the unique constraint above does
        NOT stop a second "everywhere else" row (R21, from the other side).
        Two fallbacks means the recruiter a request lands on depends on which
        row the search happened to read first."""
        for rec in self:
            if rec.country_id or not rec.active:
                continue
            twin = self.sudo().search_count([
                ('company_id', '=', rec.company_id.id),
                ('country_id', '=', False), ('id', '!=', rec.id)])
            if twin:
                raise ValidationError(_(
                    "%s already has a rule for every country that has no rule "
                    "of its own. Give this one a country, or change the one "
                    "that is there.", rec.company_id.name))

    def _compute_display_name(self):
        for rec in self:
            where = rec.country_id.name or _('Everywhere else')
            rec.display_name = '%s · %s' % (rec.company_id.name or '',
                                                 where)

    # ------------------------------------------------------------ the lookup
    @api.model
    def rule_for(self, company, country=None):
        """The rule that covers one company and country, or an empty one.

        Public and therefore reachable over the wire, so both arguments are
        coerced at the door (R43): a recordset does not survive the wire and
        arrives as a plain id.
        """
        company_id = as_id(company)
        country_id = as_id(country)
        if not company_id:
            return self.browse()
        rule = self.browse()
        if country_id:
            rule = self.sudo().search([('company_id', '=', company_id),
                                       ('country_id', '=', country_id)],
                                      limit=1)
        if not rule:
            rule = self.sudo().search([('company_id', '=', company_id),
                                       ('country_id', '=', False)], limit=1)
        return rule
