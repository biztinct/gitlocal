# -*- coding: utf-8 -*-
"""`wfp.budget.actual`, extended — the canonical budget row (ruling D2).

WHICH COLUMN HOLDS WHAT (the answer the owner report needs, and the answer
every writer in this module obeys)

    on screen        column                 written by
    ---------------  ---------------------  -------------------------------
    Budget           forecast_cost          the upload, or a person, only
    People planned   forecast_headcount     the upload, or a person, only
    Spent            actual_cost            the actuals job, only
    People paid      actual_headcount       the actuals job, only
    Left             variance_amount        computed: budget - spent
    Used             variance_pct           computed, by the shipped model

`variance_amount` is `forecast_cost - actual_cost` and `variance_pct` is that
over the budget — both computed and stored by the model as it shipped
(`pb_hr_workforce_planning/models/budget_tracking.py:61`). Nothing here changes
either formula. What this file adds is the four things a budget row needs and a
forecast row did not: WHAT KIND of money it is, WHOSE function it belongs to,
WHICH CURRENCY it is in, and WHERE THE FIGURE CAME FROM.

THE THREE OVERRIDES, AND WHY EACH IS SAFE

  * `scenario_id` becomes OPTIONAL. It was required because the row began life
    as a by-product of a compensation scenario. A budget is not: the Marketing
    department has a budget for next year whether or not anybody has built a pay
    scenario. Every row this module writes carries no scenario; a row that has
    one still behaves exactly as before. `ondelete` moves from `cascade` to
    `set null` for the same reason — deleting a scenario must not delete a
    budget nobody attached to it on purpose.
  * `company_id` stops being a stored mirror of the scenario's company and
    becomes the row's own, defaulting to the active company. Without this a
    scenario-less row would carry NO company, and a company-less row is visible
    to everybody (R8) — which is precisely the boundary country HR relies on.
  * `currency_id` follows `pb_currency_id`, the row's own currency, so every
    Monetary column on the row formats in the money it is actually in. The
    default is the company's currency, which is what the scenario's currency was.

None of the three can change an existing row's meaning, because there were no
existing rows: the model shipped with no writer, no view and no data
(`SELECT count(*) FROM wfp_budget_actual` = 0 on 2026-09-01, and the only
references to it in the whole codebase were its own ACL and a one2many).

R60 — this module adds record rules to a model an EARLIER module's groups can
already read. Group rules are ORed over the rules that APPLY, so a narrow rule
shipped alone is a narrowing. The wide rule for the workforce-planning tiers
ships beside the narrow one, in `security/pb_budget_security.xml`.
"""

import logging

from odoo import _, api, fields, models

from .budget_common import BUDGET_TYPES, SOURCES, type_label

_logger = logging.getLogger(__name__)


class WfpBudgetActual(models.Model):
    _inherit = 'wfp.budget.actual'

    # ------------------------------------------------------------- overrides
    scenario_id = fields.Many2one(
        required=False, ondelete='set null',
        help="The compensation scenario this row was produced from, when it "
             "came from one. A budget entered for the year has none.")
    company_id = fields.Many2one(
        'res.company', related=False, store=True, index=True, required=True,
        string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='pb_currency_id', store=True, readonly=True,
        string='Currency')

    # Plain English on the two columns a person actually reads, and a heading
    # that no longer asserts a currency it cannot promise (the shipped string
    # was "Variance (₫)", which is wrong for every row that is not in dong).
    forecast_cost = fields.Monetary(string='Budget')
    actual_cost = fields.Monetary(string='Spent')
    forecast_headcount = fields.Integer(string='People planned')
    actual_headcount = fields.Integer(string='People paid')
    variance_amount = fields.Monetary(string='Left')
    variance_pct = fields.Float(string='Left %')

    # ------------------------------------------------------------ new fields
    pb_budget_type = fields.Selection(
        BUDGET_TYPES, string='Budget for', default='manpower', required=True,
        index=True,
        help="People — what payroll pays. HR operations — hiring, training, "
             "welfare. Admin — everything the office spends.")
    pb_source = fields.Selection(
        SOURCES, string='Budget came from', default='manual', required=True,
        help="Where the BUDGET figure came from. What was spent is always "
             "either the payroll figures or the expenses entered against it.")
    pb_currency_id = fields.Many2one(
        'res.currency', string='Money in', required=True,
        default=lambda self: self.env.company.currency_id,
        help="The currency the budget and the spend on this row are in.")
    pb_manual_rate = fields.Float(
        string='Rate to reporting currency', digits=(16, 8), default=0.0,
        help="Leave at 0 to use the exchange rate this system holds. Set it to "
             "say what this row's money is worth in the reporting currency: "
             "the reported figure is this row's amount MULTIPLIED by the rate. "
             "One dong in US dollars would be 0.000038.")

    # The function (the top-level department) and its head. Stored, because a
    # record rule needs a plain indexed column to compare against — and because
    # the heat view groups by exactly this.
    pb_function_id = fields.Many2one(
        'hr.department', string='Function', index=True, compute='_compute_pb_function',
        store=True, readonly=True,
        help="The top-level department this row rolls up into.")
    pb_function_head_user_id = fields.Many2one(
        'res.users', string='Function head', index=True,
        compute='_compute_pb_function', store=True, readonly=True,
        help="The person who leads that function, taken from the department's "
             "own manager. This is what decides who may see the row.")

    pb_unbudgeted = fields.Boolean(
        string='Nobody budgeted this', compute='_compute_pb_unbudgeted',
        store=True,
        help="Money was spent here and no budget was ever set against it.")
    pb_actual_synced_on = fields.Datetime(
        string='Spend last read', readonly=True,
        help="When the payroll figures on this row were last read from the "
             "analytics tables.")
    pb_note = fields.Char(string='Note')

    # ------------------------------------------------------------- the walk
    @api.depends('department_id')
    def _compute_pb_function(self):
        """The top-level parent, and who leads it.

        `@api.depends` cannot say "any ancestor's manager", so it says what it
        honestly can — this row's department — and the rest is kept true by
        `hr.department`'s own write hook (`hr_department_ext.py`) plus the
        nightly top-up. A stored field whose dependency chain is a lie is worse
        than one that is refreshed on purpose.
        """
        Dept = self.env['hr.department'].sudo()
        cache = {}
        for rec in self:
            dept = rec.department_id
            if not dept:
                rec.pb_function_id = False
                rec.pb_function_head_user_id = False
                continue
            key = dept.id
            if key not in cache:
                cache[key] = self._root_of(Dept.browse(key))
            root = cache[key]
            rec.pb_function_id = root.id if root else False
            rec.pb_function_head_user_id = (
                root.manager_id.user_id.id if root and root.manager_id else False)

    @api.model
    def _root_of(self, dept):
        """The top of the tree this department hangs from, or itself."""
        node = dept
        for _hop in range(20):                 # a guard, not a depth
            if not node.parent_id:
                return node
            node = node.parent_id
        return node

    @api.depends('forecast_cost', 'actual_cost')
    def _compute_pb_unbudgeted(self):
        for rec in self:
            rec.pb_unbudgeted = bool(
                not (rec.forecast_cost or 0) and (rec.actual_cost or 0))

    # ---------------------------------------------------------- the top-up
    @api.model
    def _refresh_functions(self, limit=None):
        """Recompute the function and its head on rows whose answer may have
        moved. Idempotent, cheap, and run by the nightly job — a department can
        be re-parented or given a new manager by anybody, at any time, and no
        `depends` chain can see that coming."""
        rows = self.sudo().search([('department_id', '!=', False)], limit=limit)
        if rows:
            for name in ('pb_function_id', 'pb_function_head_user_id'):
                self.env.add_to_compute(self._fields[name], rows)
            rows.flush_recordset()
        return len(rows)

    # ----------------------------------------------------------- the display
    def _compute_display_name(self):
        """Odoo 19 has no `name_get`. A budget row's title is what it is FOR,
        where, and when — in that order, because that is how somebody looking at
        a list of them is trying to read it."""
        for rec in self:
            bits = [type_label(rec.pb_budget_type, self.env)]
            if rec.department_id:
                bits.append(rec.department_id.name or '')
            if rec.period_month:
                bits.append(rec.period_month.strftime('%b %Y'))
            rec.display_name = ' — '.join([b for b in bits if b]) or _('Budget')

    # -------------------------------------------------------- reporting money
    def pb_reported(self, fx=None, presentation=None):
        """`{budget, spent, left, known}` in the reporting currency.

        Computed, never stored: an exchange rate is a fact about a DAY, and a
        stored conversion is a number that was true once. Where the rate is not
        known this answers `known: False` and zeroes — the caller shows the row
        in its own money and says why, rather than showing a number that is
        wrong by a factor of twenty-six thousand (R23).
        """
        self.ensure_one()
        fx = fx or self.env['pb.budget.fx']
        dst = presentation or fx.presentation_currency(self.company_id)
        src = self.pb_currency_id or self.company_id.currency_id
        day = self.period_month or fields.Date.context_today(self)
        budget, known = fx.convert(self.forecast_cost, src, dst, day,
                                   self.pb_manual_rate)
        spent, _k2 = fx.convert(self.actual_cost, src, dst, day,
                                self.pb_manual_rate)
        return {'budget': budget, 'spent': spent,
                'left': round(budget - spent, 2), 'known': known,
                'currency': dst.name if dst else ''}
