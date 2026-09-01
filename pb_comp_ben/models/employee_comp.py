# -*- coding: utf-8 -*-
"""`pb.employee.comp` — what somebody is paid, written down once, on a date.

THERE IS NO CTC MODEL ANYWHERE IN THIS PRODUCT, and that is the gap this closes.
A contract carries a wage and a list of components; a payslip carries what
happened one month. Neither answers "what is my package", which is the question
an employee asks and the one an offer letter answers.

So a package is a VERSIONED SNAPSHOT: a dated list of lines, one of which is
current. Bootstrapping it reads the contract, and after that the two are
independent — a package is a statement the company makes, not a view over a
table, and a view over a table cannot be corrected without correcting the
contract underneath somebody's payslip.

SUPERSEDING IS THE WHOLE STATE MACHINE. Activating a package retires the one
before it; nothing is deleted, so "what did we tell her in March" still has an
answer in September.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .comp_common import (
    COMP_KINDS, COMP_PERIODS, PERIOD_MULTIPLIER,
)

_logger = logging.getLogger(__name__)


class PbEmployeeComp(models.Model):
    _name = 'pb.employee.comp'
    _description = 'Pay package'
    _inherit = ['mail.thread']
    _order = 'effective_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Reference')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade', tracking=True)
    effective_date = fields.Date(
        string='In force from', required=True, tracking=True,
        default=fields.Date.context_today,
        help='The date this package starts applying. It is what the person is '
             'told, not what payroll calculates from.')
    state = fields.Selection(
        [('draft', 'Being prepared'),
         ('active', 'Current'),
         ('superseded', 'Replaced')],
        default='draft', required=True, tracking=True, string='Status')
    line_ids = fields.One2many('pb.employee.comp.line', 'comp_id',
                               string='What it is made of')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    annual_total = fields.Monetary(
        compute='_compute_annual_total', store=True, currency_field='currency_id',
        string='A year of this')
    monthly_total = fields.Monetary(
        compute='_compute_annual_total', store=True, currency_field='currency_id',
        string='A month of this')
    note = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)
    superseded_by_id = fields.Many2one(
        'pb.employee.comp', string='Replaced by', readonly=True,
        ondelete='set null', copy=False)

    @api.depends('employee_id', 'effective_date')
    def _compute_name(self):
        for rec in self:
            who = rec._person().name or _('Package')
            rec.name = '%s — %s' % (
                who, fields.Date.to_string(rec.effective_date) or _('undated'))

    @api.depends('line_ids.annual_amount', 'line_ids.amount', 'line_ids.period')
    def _compute_annual_total(self):
        for rec in self:
            year = sum(rec.line_ids.mapped('annual_amount'))
            rec.annual_total = year
            rec.monthly_total = year / 12.0 if year else 0.0

    # ------------------------------------------------------------------ R56
    def _person(self):
        """The employee on this package, read as the system.

        NOT A HOLE IN ANY GATE — whoever got here was already proved entitled to
        the package by the record rule on the way in. This is R56: reading ONE
        field of an `hr.employee` prefetches EVERY stored field, and this build's
        employee carries some forty behind `groups=` (payroll country, insurance
        code, union fee, tham_gia_bhxh…). A compensation officer who does not
        also hold the payroll groups would otherwise get an AccessError naming
        forty fields nobody asked for, in the middle of printing a name.
        """
        self.ensure_one()
        return self.employee_id.sudo()

    # ------------------------------------------------------------- the moves
    def action_activate(self):
        """Make this the current package, and retire the one it replaces."""
        for rec in self:
            if rec.state == 'active':
                continue
            if rec.state == 'superseded':
                raise UserError(_(
                    "This package has already been replaced by a later one, so "
                    "it cannot be made current again."))
            if not rec.line_ids:
                raise UserError(_(
                    "There is nothing in this package yet. Add what it is made "
                    "of, or press “Build from the contract”."))
            previous = self.search([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'active'),
                ('id', '!=', rec.id),
            ])
            if previous:
                previous.write({'state': 'superseded',
                                'superseded_by_id': rec.id})
                for old in previous:
                    old.message_post(body=_(
                        "Replaced by the package in force from %s.",
                        fields.Date.to_string(rec.effective_date) or ''))
            rec.state = 'active'
            rec.message_post(body=_("This is now the current package."))
        return True

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'superseded':
                raise UserError(_(
                    "A replaced package is history and stays as it is."))
            rec.state = 'draft'
        return True

    # -------------------------------------------------------- the bootstrap
    def action_bootstrap(self):
        """Fill an empty package from the contract that is running today.

        The wage becomes 'Base salary'; every contract component becomes its own
        line. Amounts a component holds as TEXT (COLROLES typed values — a job
        grade, a cost centre) are skipped: they are not money and a package that
        prints "Grade: 0" is a package nobody trusts again.

        It is EDITABLE afterwards, and that is the point. This is a starting
        position, not a link.
        """
        made = 0
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_(
                    "Only a package that is still being prepared can be built "
                    "from the contract."))
            contract = rec._current_contract()
            if not contract:
                raise UserError(_(
                    "%s has no running contract to build a package from.",
                    rec._person().name or _('This employee')))
            rec.line_ids.unlink()
            vals = rec._lines_from_contract(contract)
            if not vals:
                raise UserError(_(
                    "That contract carries no wage and no components, so there "
                    "is nothing to build a package from."))
            rec.write({'line_ids': [(0, 0, v) for v in vals]})
            if contract.currency_id:
                rec.currency_id = contract.currency_id.id
            rec.message_post(body=_(
                "Built from the contract running on %s — %s.",
                fields.Date.to_string(rec.effective_date) or '',
                _('%s lines') % len(vals)))
            made += len(vals)
        return made

    def _current_contract(self):
        """The contract in force on the package's date, else the latest open one."""
        self.ensure_one()
        Contract = self.env['hr.contract'].sudo()
        emp = self.employee_id
        day = self.effective_date or fields.Date.context_today(self)
        found = Contract.search([
            ('employee_id', '=', emp.id),
            ('date_start', '<=', day),
            '|', ('date_end', '=', False), ('date_end', '>=', day),
        ], order='date_start desc, id desc', limit=1)
        if found:
            return found
        return Contract.search([('employee_id', '=', emp.id)],
                               order='date_start desc, id desc', limit=1)

    def _lines_from_contract(self, contract):
        """The package lines a contract implies. Pure read — writes nothing."""
        self.ensure_one()
        vals = []
        seq = 10
        wage = contract.wage or 0.0
        if wage:
            vals.append({
                'name': _('Base salary'), 'kind': 'earning',
                'amount': wage, 'period': 'monthly', 'sequence': seq,
                'note': _('From the contract.'),
            })
            seq += 10
        for adv in contract.advantages_ids:
            template = adv.advantage_template_id
            # A text-typed component is a label, not money (COLROLES).
            if getattr(adv, 'value_type', 'amount') == 'text':
                continue
            amount = adv.amount or 0.0
            if not amount:
                continue
            vals.append({
                'name': (template.name if template else '') or _('Component'),
                'kind': 'earning',
                'amount': amount,
                'period': 'monthly',
                'sequence': seq,
                'note': _('Contract component %s.',
                          (template.code if template else '') or ''),
            })
            seq += 10
        return vals

    # ------------------------------------------------------------ the reads
    @api.model
    def active_for_employee(self, employee_id):
        """The current package for one person, or an empty recordset.

        R43/R52 — a public helper reached over JSON-RPC gets an INTEGER where the
        caller wrote a record. Coerce at the door rather than letting an int walk
        past every `getattr` and answer the fallback.
        """
        emp_id = employee_id.id if hasattr(employee_id, 'id') else int(
            employee_id or 0)
        if not emp_id:
            return self.browse()
        return self.search([('employee_id', '=', emp_id),
                            ('state', '=', 'active')],
                           order='effective_date desc, id desc', limit=1)


class PbEmployeeCompLine(models.Model):
    _name = 'pb.employee.comp.line'
    _description = 'Pay package line'
    _order = 'sequence, id'

    comp_id = fields.Many2one('pb.employee.comp', string='Package',
                              required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string='What it is', required=True)
    kind = fields.Selection(COMP_KINDS, string='Kind', default='earning',
                            required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    period = fields.Selection(COMP_PERIODS, string='How often',
                              default='monthly', required=True)
    annual_amount = fields.Monetary(
        compute='_compute_annual', store=True, currency_field='currency_id',
        string='A year of it')
    currency_id = fields.Many2one(related='comp_id.currency_id', store=True,
                                  readonly=True)
    company_id = fields.Many2one(related='comp_id.company_id', store=True,
                                 index=True, readonly=True)
    note = fields.Char(string='Note')

    @api.depends('amount', 'period')
    def _compute_annual(self):
        for line in self:
            line.annual_amount = (line.amount or 0.0) * PERIOD_MULTIPLIER.get(
                line.period or 'monthly', 12.0)
