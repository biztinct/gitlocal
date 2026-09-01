# -*- coding: utf-8 -*-
"""`pb.budget.expense` — what HR and the office actually spent.

The payroll fact tables know what people were paid, to the dong. They know
nothing whatever about a training course, a recruitment agency's fee, a leaving
gift or a new coffee machine — so an HR-operations or admin budget with no way
to record spend is a budget that can only ever read as unspent.

This is the smallest thing that closes that: a date, a department, an amount, a
supplier's name in plain text, a note and a file. It is not a purchase order, it
is not an approval flow and it is not an invoice. P11 may give the supplier a
record of its own; until then the name is a Char, because a free-text name that
somebody can type today is worth more than a relation nobody has populated.

Every expense rolls into the SPENT column of its month's budget row, through the
same writer the payroll actuals go through — one door onto `actual_cost`, so the
two can never disagree about who last wrote it.
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .budget_common import BUDGET_TYPES

_logger = logging.getLogger(__name__)

#: An expense is never a manpower cost: payroll already counts those, and letting
#: somebody type one here would double the salary bill by hand.
EXPENSE_TYPES = [(k, lbl) for k, lbl in BUDGET_TYPES if k != 'manpower']


class PbBudgetExpense(models.Model):
    _name = 'pb.budget.expense'
    _description = 'Budget expense'
    _inherit = ['mail.thread']
    _order = 'spend_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(string='What it was for', required=True, tracking=True)
    spend_date = fields.Date(
        string='Date', required=True, index=True, tracking=True,
        default=fields.Date.context_today,
        help="The month this lands in is taken from this date.")
    budget_type = fields.Selection(
        EXPENSE_TYPES, string='Budget', default='hr_ops', required=True,
        index=True, tracking=True)
    department_id = fields.Many2one(
        'hr.department', string='Department', index=True, tracking=True,
        help="Leave empty for something the whole company shares — it then "
             "counts against the company's own line rather than a team's.")
    amount = fields.Monetary(string='Amount', required=True, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', string='Money in', required=True,
        default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    supplier = fields.Char(
        string='Paid to',
        help="Who was paid. Free text for now.")
    note = fields.Text(string='Note')
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Files',
        help="The invoice, the quote, whatever there is.")

    period_month = fields.Date(
        string='Month', compute='_compute_period_month', store=True, index=True,
        help="The first of the month this expense counts in.")
    function_id = fields.Many2one(
        'hr.department', string='Function', compute='_compute_function',
        store=True, index=True, readonly=True)
    function_head_user_id = fields.Many2one(
        'res.users', string='Function head', compute='_compute_function',
        store=True, index=True, readonly=True)

    # ------------------------------------------------------------- computes
    @api.depends('spend_date')
    def _compute_period_month(self):
        for rec in self:
            rec.period_month = (rec.spend_date.replace(day=1)
                                if rec.spend_date else False)

    @api.depends('department_id')
    def _compute_function(self):
        Budget = self.env['wfp.budget.actual'].sudo()
        for rec in self:
            if not rec.department_id:
                rec.function_id = False
                rec.function_head_user_id = False
                continue
            root = Budget._root_of(rec.department_id.sudo())
            rec.function_id = root.id if root else False
            rec.function_head_user_id = (
                root.manager_id.user_id.id if root and root.manager_id else False)

    # ----------------------------------------------------------- the guards
    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount is not None and rec.amount < 0:
                raise ValidationError(_(
                    "An expense is what was spent, so it cannot be a negative "
                    "number. If money came back, record it as a separate "
                    "refund with a note saying so."))

    # --------------------------------------------------------- the roll-up
    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs._touch_budget()
        return recs

    def write(self, vals):
        # Both sides: the month it LEAVES and the month it ARRIVES in both need
        # their total re-added, or moving an expense leaves a ghost behind.
        before = self._keys()
        res = super().write(vals)
        self._touch_budget(extra_keys=before)
        return res

    def unlink(self):
        keys = self._keys()
        res = super().unlink()
        self.env['pb.budget.actuals'].sudo().sync_expense_keys(keys)
        return res

    def _keys(self):
        return {(r.company_id.id, r.department_id.id or False, r.period_month,
                 r.budget_type) for r in self if r.period_month}

    def _touch_budget(self, extra_keys=None):
        keys = self._keys() | (extra_keys or set())
        if not keys:
            return
        try:
            self.env['pb.budget.actuals'].sudo().sync_expense_keys(keys)
        except Exception as e:                 # noqa: BLE001
            # Saving an expense must never fail because the roll-up did; the
            # nightly job puts every month right anyway.
            _logger.warning('pb_budget: expense roll-up failed: %s', e)
