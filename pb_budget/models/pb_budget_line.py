# -*- coding: utf-8 -*-
"""`pb.budget.line` — one month, one team, one kind of money. The budget row.

WHY THIS FILE EXISTS AT ALL, AND WHY IT LOOKS LIKE A MERGE
---------------------------------------------------------
This model used to be `wfp.budget.actual`, a table that belonged to the old
planning module and shipped with no writer, no view and no rows. Ruling D2 made
it the canonical budget object and this module put all three on it from the
outside. That was the right call while the planning module was staying; it is
the wrong shape now that it is going, because uninstalling a module DROPS ITS
TABLES and every budget row in the product would go with them.

So the row comes home. The fields below are the shipped model's six columns and
this module's eleven, in one place, with the three "overrides" simply written
as what they always meant. Nothing about the meaning of a column changed in the
move, and the migration beside it copies every row across and proves the totals
match before the old table is allowed to go.

WHICH COLUMN HOLDS WHAT (the answer every writer in this module obeys)

    on screen        column                 written by
    ---------------  ---------------------  -------------------------------
    Budget           forecast_cost          the upload, or a person, only
    People planned   forecast_headcount     the upload, or a person, only
    Spent            actual_cost            the actuals job, only
    People paid      actual_headcount       the actuals job, only
    Left             variance_amount        computed: budget - spent
    Left %           variance_pct           computed

THE THREE COLUMNS THAT CHANGED SHAPE WHEN THIS MODULE ADOPTED THE MODEL
  * `scenario_id` is OPTIONAL and is now a plain integer reference rather than
    a link to a model that is being retired. A budget is not a by-product of a
    pay scenario: the Marketing department has a budget for next year whether
    or not anybody ever built one.
  * `company_id` is the ROW'S OWN and required. A company-less row is visible
    to everybody (R8), which is precisely the boundary country HR relies on.
  * `currency_id` follows `pb_currency_id`, the row's own currency, so every
    Monetary column formats in the money it is actually in.
"""

import logging

from odoo import _, api, fields, models

from .budget_common import BUDGET_TYPES, SOURCES, type_label

_logger = logging.getLogger(__name__)


class PbBudgetLine(models.Model):
    _name = 'pb.budget.line'
    _description = 'Budget row'
    _order = 'period_month desc, department_id'

    # ------------------------------------------------------ what it is about
    period_month = fields.Date(
        string='Period (1st of Month)', required=True, index=True,
        help='First day of the month this row covers.')
    department_id = fields.Many2one(
        'hr.department', string='Department', index=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True, index=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='pb_currency_id', store=True, readonly=True,
        string='Currency')

    # The scenario this row came out of, on the databases where one did. Kept
    # as a NUMBER on purpose: the model it pointed at is being retired, and a
    # link to a table that is about to be dropped is a link that takes the
    # budget with it.
    scenario_ref = fields.Integer(
        string='Came from scenario', index=True,
        help='The old planning scenario this row was produced from, where it '
             'came from one. A budget entered for the year has none.')

    # ------------------------------------------------------------- the money
    forecast_cost = fields.Monetary(string='Budget')
    actual_cost = fields.Monetary(string='Spent')
    forecast_headcount = fields.Integer(string='People planned')
    actual_headcount = fields.Integer(string='People paid')
    variance_amount = fields.Monetary(
        string='Left', compute='_compute_variance', store=True)
    variance_pct = fields.Float(
        string='Left %', compute='_compute_variance', store=True,
        digits=(5, 2))

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
        'hr.department', string='Function', index=True,
        compute='_compute_pb_function', store=True, readonly=True,
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

    # ---------------------------------------------------------- the computes
    @api.depends('forecast_cost', 'actual_cost')
    def _compute_variance(self):
        """Unchanged, to the digit, from the shipped model's own formula.

        `variance_amount` is budget minus spent and `variance_pct` is that
        over the budget. The migration beside this file asserts both come out
        the same on every row it moves, because a re-home that quietly
        recalculates a number is a re-home nobody can check.
        """
        for rec in self:
            rec.variance_amount = (rec.forecast_cost or 0) \
                - (rec.actual_cost or 0)
            if rec.forecast_cost:
                rec.variance_pct = (
                    rec.variance_amount / rec.forecast_cost) * 100
            else:
                rec.variance_pct = 0.0

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
                root.manager_id.user_id.id
                if root and root.manager_id else False)

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
        rows = self.sudo().search([('department_id', '!=', False)],
                                  limit=limit)
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
            rec.display_name = ' — '.join([b for b in bits if b]) \
                or _('Budget')

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

    # ============================================================ the move
    @api.model
    def migrate_from_planning(self):
        """Copy every old budget row into this table. Idempotent.

        Run before the old planning module is removed, and again by the
        pre-flight gate's own arithmetic: the row count and the sum of what
        was spent have to match on both sides or nothing is uninstalled.

        A row is matched by the four things that identify it — company, team,
        month and kind — so running this twice moves nothing twice.
        """
        report = {'found': 0, 'made': 0, 'skipped': 0,
                  'old_sum': 0.0, 'new_sum': 0.0, 'moved_sum': 0.0}
        cr = self.env.cr
        # `new_sum` is reported even when there is nothing to move. A report
        # that answers zero for "what is on the new table" the day after the
        # old one was removed is a report that reads like the data went with
        # it.
        cr.execute('SELECT COALESCE(SUM(actual_cost), 0) FROM pb_budget_line')
        report['new_sum'] = float(cr.fetchone()[0] or 0.0)
        if 'wfp.budget.actual' not in self.env:
            return report
        cr.execute("SELECT to_regclass('wfp_budget_actual')")
        if not cr.fetchone()[0]:
            return report
        # READ ONLY WHAT IS THERE. Eleven of the columns on the old table were
        # added from OUTSIDE it by this module, so a database where the two
        # modules were installed in the other order — or where the budget
        # module was never installed at all — has the six shipped columns and
        # nothing else. Naming a column that is not there turns a migration
        # into a crash, which is the one thing a migration may never be.
        cr.execute("""
            SELECT column_name FROM information_schema.columns
             WHERE table_name = 'wfp_budget_actual'
        """)
        have = {row[0] for row in cr.fetchall()}
        wanted = ['id', 'scenario_id', 'company_id', 'period_month',
                  'department_id', 'forecast_headcount', 'forecast_cost',
                  'actual_headcount', 'actual_cost', 'pb_budget_type',
                  'pb_source', 'pb_currency_id', 'pb_manual_rate',
                  'pb_actual_synced_on', 'pb_note']
        select = ', '.join(
            name if name in have else 'NULL AS %s' % name for name in wanted)
        cr.execute('SELECT ' + select
                   + ' FROM wfp_budget_actual ORDER BY id')
        rows = cr.fetchall()
        report['found'] = len(rows)
        if not rows:
            return report
        cr.execute('SELECT COALESCE(SUM(actual_cost), 0) '
                   'FROM wfp_budget_actual')
        report['old_sum'] = float(cr.fetchone()[0] or 0.0)

        # TWO sets of keys, because the old table may no longer be able to say
        # what KIND of budget a row is. The eleven columns this module added
        # to it were removed with the code that declared them, and a removed
        # field takes its column with it — so on a database that has already
        # been through this upgrade the old rows read `NULL` for the kind and
        # would not match the rows they were copied into. Matched on the full
        # key where the old row knows its kind, and on company, team and month
        # alone where it does not.
        existing, loose = set(), set()
        for line in self.sudo().search_read(
                [], ['company_id', 'department_id', 'period_month',
                     'pb_budget_type']):
            base = ((line['company_id'] or [0])[0],
                    (line['department_id'] or [0])[0],
                    str(line['period_month'] or ''))
            existing.add(base + (line['pb_budget_type'],))
            loose.add(base)

        # A required column may be empty on the old table (it was added from
        # the outside and back-filled), and a create that trips over one
        # stops the whole move. Fall back to the company's own money.
        cr.execute('SELECT id, currency_id FROM res_company')
        company_currency = dict(cr.fetchall())

        made = []
        for (old_id, scenario_id, company_id, month, dept_id, plan_heads,
             plan_cost, paid_heads, paid_cost, btype, source, currency_id,
             rate, synced, note) in rows:
            base = (company_id or 0, dept_id or 0, str(month or ''))
            already = (base + (btype,)) in existing if btype \
                else base in loose
            if already:
                report['skipped'] += 1
                continue
            existing.add(base + (btype or 'manpower',))
            loose.add(base)
            made.append({
                'scenario_ref': scenario_id or 0,
                'company_id': company_id,
                'period_month': month,
                'department_id': dept_id or False,
                'forecast_headcount': plan_heads or 0,
                'forecast_cost': plan_cost or 0.0,
                'actual_headcount': paid_heads or 0,
                'actual_cost': paid_cost or 0.0,
                'pb_budget_type': btype or 'manpower',
                'pb_source': source or 'manual',
                'pb_currency_id': currency_id
                or company_currency.get(company_id),
                'pb_manual_rate': rate or 0.0,
                'pb_actual_synced_on': synced or False,
                'pb_note': note or False,
            })
        if made:
            self.sudo().create(made)
            report['made'] = len(made)
            report['moved_sum'] = sum(float(row['actual_cost'] or 0.0)
                                      for row in made)
        cr.execute('SELECT COALESCE(SUM(actual_cost), 0) FROM pb_budget_line')
        report['new_sum'] = float(cr.fetchone()[0] or 0.0)
        _logger.info('pb_budget: budget rows moved %s', report)
        return report
