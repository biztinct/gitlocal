# -*- coding: utf-8 -*-
"""Which HR person looks after which part of the company.

A rule table read TOP DOWN, first match wins, and the last row is deliberately
allowed to match everything: a joiner who falls through every rule and ends up
with nobody is the dead end this table exists to prevent. Country and department
are both optional, and an empty one means "any" — so a single row with neither
set is a working configuration for a company that has one HR person.

The rules are only ever read to FILL AN EMPTY field. A person whose HR partner
was chosen by hand keeps them, whatever the table says afterwards.
"""

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class PbHrbpRule(models.Model):
    _name = 'pb.hrbp.rule'
    _description = 'HR Partner Rule'
    _order = 'sequence, id'

    name = fields.Char(compute='_compute_name', store=True, string='Rule')
    sequence = fields.Integer(
        default=10,
        help='Rules are read from the top. The first one that fits is used.')
    country_id = fields.Many2one(
        'res.country', string='Country',
        help='Leave empty to match people in any country.')
    department_id = fields.Many2one(
        'hr.department', string='Department',
        help='Leave empty to match any team.')
    hrbp_user_id = fields.Many2one(
        'res.users', string='HR business partner', required=True,
        ondelete='cascade')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    note = fields.Char(string='Notes')

    @api.depends('country_id', 'department_id', 'hrbp_user_id')
    def _compute_name(self):
        for rec in self:
            where = ' · '.join(p for p in [
                rec.department_id.name or '',
                rec.country_id.name or '',
            ] if p) or _('Everyone else')
            rec.name = '%s → %s' % (where, rec.hrbp_user_id.name or '—')

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.name or _('HR partner rule')

    # ------------------------------------------------------------- the answer
    @api.model
    def assign_for(self, employee):
        """The HR partner this person should have, or an empty recordset.

        Never raises and never guesses: an unreadable rule table answers "no
        rule", the caller leaves the field empty, and the board shows a dash
        that somebody can click. A wrong name would be worse than none.
        """
        Users = self.env['res.users']
        if not employee:
            return Users.browse()
        try:
            company = employee.company_id or self.env.company
            country = False
            if employee.country_id:
                country = employee.country_id.id
            elif company.country_id:
                country = company.country_id.id
            dept = employee.department_id.id if employee.department_id else False
            rules = self.sudo().search([
                '|', ('company_id', '=', False),
                ('company_id', '=', company.id),
            ], order='sequence, id')
            for rule in rules:
                if rule.country_id and rule.country_id.id != country:
                    continue
                if rule.department_id and rule.department_id.id != dept:
                    continue
                if rule.hrbp_user_id and rule.hrbp_user_id.active:
                    return rule.hrbp_user_id
        except Exception:               # noqa: BLE001 — never break an arrival
            _logger.exception('pb_onboarding: HR partner rules unreadable')
        return Users.browse()

    @api.model
    def backfill(self, employees=None):
        """Fill the EMPTY HR partner of everybody the rules can answer.

        Idempotent by definition — it only ever writes a field that is empty,
        so running it twice is running it once. Per record try/except, and an
        honest count: the number returned is the number actually written.
        """
        Emp = self.env['hr.employee'].sudo()
        if employees is None or not employees:
            employees = Emp.search([
                ('active', '=', True), ('hrbp_user_id', '=', False),
                ('company_id', 'in', self.env.companies.ids
                 or [self.env.company.id]),
            ])
        touched = 0
        for emp in employees:
            try:
                if emp.hrbp_user_id:
                    continue
                user = self.assign_for(emp)
                if user:
                    emp.sudo().write({'hrbp_user_id': user.id})
                    touched += 1
            except Exception:           # noqa: BLE001 — one record, one grave
                _logger.exception('pb_onboarding: HR partner backfill for %s',
                                  emp.id)
        _logger.info('pb_onboarding: HR partner filled in for %s employee(s)',
                     touched)
        return touched
