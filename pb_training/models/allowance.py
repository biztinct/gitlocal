# -*- coding: utf-8 -*-
"""`pb.training.allowance` — what a company will spend on training one person.

A NUMBER PER COMPANY PER YEAR, AND AN OVERRIDE PER PERSON. That is the whole
model, and the shape is deliberate: almost every company has one figure and a
handful of exceptions, so a table that made every person a row would be four
thousand rows of the same number and an exception nobody could find.

THE ANSWER IS ALWAYS ONE NUMBER. `allowance_for(employee, year)` reads the
person's own row if there is one, then the company's row for that year, then
zero — and zero is an ANSWER rather than a failure, said on the screen as "no
training allowance has been set for 2026" so nobody reports a working page as
broken (R54 from the data's side).

WHY THE YEAR IS AN INTEGER AND NOT A DATE RANGE. An allowance is what somebody
may spend "this year"; a range would let two rows overlap and then there would
be two answers to a question that must have one. The year a claim counts
against is the year it was PAID IN, which is the invoice's own date and not the
date somebody got round to claiming it.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .training_common import as_id

_logger = logging.getLogger(__name__)


class PbTrainingAllowance(models.Model):
    _name = 'pb.training.allowance'
    _description = 'Training allowance'
    _order = 'year desc, employee_id, id desc'

    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    year = fields.Integer(
        string='Year', required=True, index=True,
        default=lambda self: fields.Date.today().year,
        help='The calendar year the allowance is for. A claim counts against '
             'the year the course was PAID for, not the year it was claimed.')
    employee_id = fields.Many2one(
        'hr.employee', string='Just for', index=True, ondelete='cascade',
        help='Leave it empty and this is the figure for everybody in the '
             'company. Name somebody and it is theirs alone, and it wins over '
             'the company figure.')
    amount = fields.Monetary(
        string='Allowance', required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency', required=True,
        default=lambda self: self.env.company.currency_id)
    note = fields.Char(string='Why this figure')
    active = fields.Boolean(default=True)

    #: `_sql_constraints` IS SILENTLY IGNORED on Odoo 19 (ledger) — a
    #: `models.Constraint` class attribute is the spelling that reaches the
    #: database. IT COVERS THE NAMED-PERSON ROWS AND ONLY THOSE: Postgres keeps
    #: NULLs DISTINCT, so two company-wide rows for the same year both satisfy
    #: it. That half is guarded in Python below, which is honest for a table an
    #: administrator edits by hand a few times a year, and is said out loud
    #: here so nobody reads the index and believes it covers both.
    _uniq_allowance = models.Constraint(
        'unique (company_id, year, employee_id)',
        'There is already an allowance for that company, that year and that '
        'person. Change the one that is there rather than adding a second.')

    # =====================================================================
    #  sanity
    # =====================================================================
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError(_(
                    "An allowance cannot be less than nothing. Set it to zero "
                    "if nobody may claim."))

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year < 2000 or rec.year > 2100:
                raise ValidationError(_(
                    "%s does not look like a year.", rec.year))

    @api.constrains('company_id', 'year', 'employee_id')
    def _check_one_company_row(self):
        """The half the unique index cannot reach — see `_uniq_allowance`."""
        for rec in self:
            if rec.employee_id:
                continue
            clash = self.sudo().search([
                ('id', '!=', rec.id), ('employee_id', '=', False),
                ('company_id', '=', rec.company_id.id),
                ('year', '=', rec.year),
            ], limit=1)
            if clash:
                raise ValidationError(_(
                    "%(company)s already has an allowance for %(year)s. "
                    "Change that one rather than adding a second — two "
                    "figures for one year is two answers to one question.",
                    company=rec.company_id.name or '', year=rec.year))

    @api.constrains('employee_id', 'company_id')
    def _check_company(self):
        """A person's own allowance belongs to the company they work for."""
        for rec in self:
            emp = rec.employee_id.sudo()
            if emp and emp.company_id and emp.company_id != rec.company_id:
                raise ValidationError(_(
                    "%(who)s works for %(theirs)s, so their allowance cannot "
                    "be set under %(here)s.", who=emp.name or '',
                    theirs=emp.company_id.name or '',
                    here=rec.company_id.name or ''))

    def _compute_display_name(self):
        for rec in self:
            who = rec.employee_id.sudo().name or rec.company_id.name or ''
            rec.display_name = '%s · %s' % (who, rec.year)

    # =====================================================================
    #  the one question this table answers
    # =====================================================================
    @api.model
    def allowance_for(self, employee, year=None):
        """The allowance row that governs one person in one year, or empty.

        `employee` may be a record OR a plain id: a record argument does not
        survive JSON-RPC and arrives as an integer (R43), so it is coerced at
        the door and an in-process caller and a browser reach the same code.

        AS THE SYSTEM. The person whose allowance it is holds no training
        permission and must still be able to read their own remaining budget
        on their own page; the narrowing is the search, written out below.
        """
        emp = self.env['hr.employee'].sudo().browse(as_id(employee)).exists()
        if not emp:
            return self.sudo().browse()
        year = int(year or fields.Date.today().year)
        company = emp.company_id or self.env.company
        mine = self.sudo().search([
            ('employee_id', '=', emp.id), ('year', '=', year),
        ], limit=1)
        if mine:
            return mine
        return self.sudo().search([
            ('employee_id', '=', False), ('company_id', '=', company.id),
            ('year', '=', year),
        ], limit=1)

    @api.model
    def amount_for(self, employee, year=None):
        """(amount, currency) — zero and the company's currency when unset."""
        row = self.allowance_for(employee, year)
        if row:
            return row.amount, row.currency_id
        emp = self.env['hr.employee'].sudo().browse(as_id(employee)).exists()
        company = (emp.company_id if emp else False) or self.env.company
        return 0.0, company.currency_id
