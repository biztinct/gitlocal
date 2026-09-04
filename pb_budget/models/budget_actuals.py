# -*- coding: utf-8 -*-
"""`pb.budget.actuals` — the spend, posted onto the budget rows.

THE MIRROR (this is the whole contract, and it is deliberate)

The payroll figure a budget row shows is the SAME aggregation the Analytics
Explorer's **Cost Explorer** lens draws — filter for filter — so a person who
questions a budget number can open the Explorer, pick Total cost by Department
by Month, and read the identical figure. Written out, the Explorer's cost lens is
``measure=total_cost, dimension=department_id, grain=month, filters={}``
(`pb_explorer/models/pb_explorer.py:142`), which resolves to:

    SELECT department_id, month, SUM(amount)
      FROM pb_fact_line
     WHERE run_id IN <scoped runs>
       AND company_id IN <the companies>
       AND category_type IN ('basic', 'allowance', 'employer_cost')   -- _MEASURES['total_cost']
       AND COALESCE(is_rollup, FALSE) = FALSE                         -- VALUEKIND: a dong once
     GROUP BY department_id, month

and the head count beside it is the Explorer's own headcount measure, which is
routed to the EMPLOYEE-grain table because a distinct count at component grain
double-counts people (`pb_fact.py:31`):

    SELECT department_id, month, COUNT(DISTINCT employee_id)
      FROM pb_fact_emp
     WHERE run_id IN <scoped runs> AND company_id IN <the companies>
     GROUP BY department_id, month

TWO DELIBERATE DIFFERENCES FROM THE EXPLORER, BOTH IN THE SAME DIRECTION

  1. **No 200-run cap.** The Explorer looks at the newest 200 runs because it is
     a screen and a screen has a budget (`_RUN_SCAN`). A budget year must not
     silently drop a pay run, so this reads every run in its window. R76 — a cap
     that is right for a screen is a bug in a job.
  2. **It never builds facts.** The Explorer freshens what it is about to read;
     this job runs AFTER the analytics build cron and reads what is there.
     Anything not built yet is REPORTED as pending and left out of the numbers,
     never estimated.

WHAT THIS JOB MAY WRITE, AND WHAT IT MAY NOT

It writes `actual_cost`, `actual_headcount` and `pb_actual_synced_on`, and
nothing else, ever. `forecast_cost` and `forecast_headcount` are the BUDGET and
they belong to whoever uploaded them; a job that could overwrite a budget with a
number it derived is a job that can lose a year's planning to a bad month of
facts. Rows it CREATES (a department that spent money nobody budgeted for) carry
`pb_source='auto'` and a zero budget, so they read as "nobody budgeted this".

It is idempotent because it SETS rather than adds: running it twice, or ten
times, leaves the same figures. The stamp is a courtesy for the screen, not the
thing that makes it safe to re-run.
"""

import logging

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

from .budget_common import (COST_CATEGORY_TYPES, param_int, flag, safe)

_logger = logging.getLogger(__name__)

P_LAST_RUN = 'pb_budget.actuals_last_run'
P_AUTO = 'pb_budget.auto_actuals'
P_MONTHS = 'pb_budget.actuals_months'


class PbBudgetActuals(models.AbstractModel):
    _name = 'pb.budget.actuals'
    _description = 'Budget actuals writer'

    # ================================================================= entry
    @api.model
    def cron_sync(self):
        """What the night does."""
        report = self.sync()
        _logger.info(
            'pb_budget: actuals — %s month rows written, %s created, '
            '%s pay runs not summarised yet, %s rows skipped for an unknown '
            'exchange rate',
            report.get('written', 0), report.get('created', 0),
            report.get('pending_runs', 0), report.get('skipped_fx', 0))
        return report

    @api.model
    def run_now(self):
        """What the button does — EXACTLY what the night does (R53).

        A "run it now" that does four of the five things the cron does produces
        a number nobody can compare with the morning's log.
        """
        return self.cron_sync()

    # ================================================================== work
    @api.model
    def sync(self, months=None, company_ids=None):
        """Re-read the spend for a window of months.

        `months=None` means the configured window (a job); a caller may pass a
        smaller number, and the cap is a PARAMETER rather than a constant for
        exactly the reason R76 records.
        """
        if not flag(self.env, P_AUTO):
            # Off, and it SAYS so with a real number rather than going quiet
            # (R54). Nothing is written; everything else is counted.
            preview = safe(lambda: self._window_summary(months, company_ids), {},
                           'the actuals preview')
            _logger.info('pb_budget: automatic actuals are switched off — '
                         '%s department-months would have been written',
                         (preview or {}).get('would_write', 0))
            out = {'ok': True, 'off': True, 'written': 0, 'created': 0,
                   'skipped_fx': 0, 'pending_runs': 0}
            out.update(preview or {})
            return out

        date_from, date_to = self._window(months)
        companies = self._companies(company_ids)
        report = {'ok': True, 'off': False, 'written': 0, 'created': 0,
                  'zeroed': 0, 'skipped_fx': 0, 'pending_runs': 0,
                  'date_from': str(date_from), 'date_to': str(date_to),
                  'companies': companies}
        if not companies:
            return report

        pay = safe(lambda: self._payroll(date_from, date_to, companies),
                   {'written': 0, 'created': 0, 'zeroed': 0, 'skipped_fx': 0,
                    'pending_runs': 0}, 'the payroll actuals')
        for key in ('written', 'created', 'zeroed', 'skipped_fx', 'pending_runs'):
            report[key] += (pay or {}).get(key, 0)

        exp = safe(lambda: self._expenses(date_from, date_to, companies),
                   {'written': 0, 'created': 0, 'skipped_fx': 0},
                   'the expense roll-up')
        for key in ('written', 'created', 'skipped_fx'):
            report[key] += (exp or {}).get(key, 0)

        safe(lambda: self.env['wfp.budget.actual']._refresh_functions(), 0,
             'the function top-up')

        self.env['ir.config_parameter'].sudo().set_param(
            P_LAST_RUN, fields.Datetime.to_string(fields.Datetime.now()))
        return report

    # ------------------------------------------------------------- the window
    @api.model
    def _window(self, months=None):
        """`(first day of the earliest month, last day of the latest)`.

        The window ENDS at the latest month the facts hold, not at today: a
        demo world (and a payroll that runs ahead) can carry runs dated into
        next year, and a window that stopped at today would leave them out
        without saying so.
        """
        span = months if months is not None else param_int(self.env, P_MONTHS, 18)
        span = max(1, min(int(span or 18), 120))
        self.env.cr.execute("SELECT MAX(month) FROM pb_fact_line")
        row = self.env.cr.fetchone()
        end = (row and row[0]) or fields.Date.context_today(self)
        end = end.replace(day=1)
        start = end - relativedelta(months=span - 1)
        # The window is inclusive of the end month, so the "to" is that month's
        # first day — every comparison below is on `month`, never on a day.
        return start, end

    @api.model
    def _companies(self, company_ids=None):
        if company_ids:
            return [int(c) for c in company_ids]
        self.env.cr.execute(
            "SELECT DISTINCT company_id FROM pb_fact_line WHERE company_id IS NOT NULL")
        ids = {r[0] for r in self.env.cr.fetchall()}
        self.env.cr.execute(
            "SELECT DISTINCT company_id FROM pb_budget_expense WHERE company_id IS NOT NULL")
        ids |= {r[0] for r in self.env.cr.fetchall()}
        return sorted(ids)

    @api.model
    def _window_summary(self, months=None, company_ids=None):
        """How much the job WOULD write. Used when it is switched off."""
        date_from, date_to = self._window(months)
        companies = self._companies(company_ids)
        if not companies:
            return {'would_write': 0}
        runs = self._run_ids(date_from, date_to)
        if not runs:
            return {'would_write': 0}
        self.env.cr.execute(
            """SELECT COUNT(*) FROM (
                 SELECT company_id, department_id, month FROM pb_fact_line
                  WHERE run_id IN %s AND company_id IN %s
                    AND category_type IN %s
                    AND COALESCE(is_rollup, FALSE) = FALSE
                  GROUP BY 1, 2, 3) g""",
            (tuple(runs), tuple(companies), COST_CATEGORY_TYPES))
        return {'would_write': self.env.cr.fetchone()[0] or 0}

    # -------------------------------------------------------------- the runs
    @api.model
    def _run_ids(self, date_from, date_to):
        """Every BUILT, non-cancelled run whose month is in the window.

        Built is the whole test: the facts are what this job reads, so a run
        with no facts is simply not here yet, and is reported rather than
        guessed at.
        """
        self.env.cr.execute(
            """SELECT fr.run_id
                 FROM pb_fact_run fr
                 JOIN hr_payslip_run r ON r.id = fr.run_id
                WHERE fr.month >= %s AND fr.month <= %s
                  AND COALESCE(r.state, '') != 'cancel'""",
            (date_from, date_to))
        return [r[0] for r in self.env.cr.fetchall()]

    @api.model
    def _pending_runs(self, date_from, date_to):
        """Runs inside the window that the analytics job has not summarised."""
        self.env.cr.execute(
            """SELECT COUNT(*)
                 FROM hr_payslip_run r
            LEFT JOIN pb_fact_run fr ON fr.run_id = r.id
                WHERE fr.id IS NULL
                  AND COALESCE(r.state, '') != 'cancel'
                  AND r.date_end >= %s""",
            (date_from,))
        return self.env.cr.fetchone()[0] or 0

    # ----------------------------------------------------------- the payroll
    @api.model
    def _payroll(self, date_from, date_to, companies):
        out = {'written': 0, 'created': 0, 'zeroed': 0, 'skipped_fx': 0,
               'pending_runs': self._pending_runs(date_from, date_to)}
        runs = self._run_ids(date_from, date_to)
        if not runs:
            return out

        # THE MIRROR. Every clause here is the Cost Explorer's, and the module
        # constant naming the category types says so in one place.
        self.env.cr.execute(
            """SELECT company_id, department_id, month, SUM(amount)
                 FROM pb_fact_line
                WHERE run_id IN %s AND company_id IN %s
                  AND category_type IN %s
                  AND COALESCE(is_rollup, FALSE) = FALSE
                GROUP BY 1, 2, 3""",
            (tuple(runs), tuple(companies), COST_CATEGORY_TYPES))
        cost = {(c, d or False, m): float(v or 0.0)
                for c, d, m, v in self.env.cr.fetchall()}

        self.env.cr.execute(
            """SELECT company_id, department_id, month, COUNT(DISTINCT employee_id)
                 FROM pb_fact_emp
                WHERE run_id IN %s AND company_id IN %s
                GROUP BY 1, 2, 3""",
            (tuple(runs), tuple(companies)))
        heads = {(c, d or False, m): int(n or 0)
                 for c, d, m, n in self.env.cr.fetchall()}

        Budget = self.env['wfp.budget.actual'].sudo()
        existing = Budget.search([
            ('pb_budget_type', '=', 'manpower'),
            ('company_id', 'in', companies),
            ('period_month', '>=', date_from),
            ('period_month', '<=', date_to),
        ])
        by_key = {}
        for rec in existing:
            by_key.setdefault(
                (rec.company_id.id, rec.department_id.id or False,
                 rec.period_month), rec)

        for key, amount in cost.items():
            rec = by_key.get(key)
            written = self._post(rec, key, 'manpower', amount,
                                 heads.get(key, 0), out)
            if written is not None:
                by_key[key] = written

        # A month that used to have spend and no longer does (a run cancelled,
        # a fact table rebuilt) must go back to zero, or the screen keeps
        # showing money nobody spent. Only rows this job has written before —
        # a row with no stamp was put there by a person.
        for key, rec in by_key.items():
            if key in cost or not rec.pb_actual_synced_on:
                continue
            if rec.actual_cost or rec.actual_headcount:
                rec.write({'actual_cost': 0.0, 'actual_headcount': 0,
                           'pb_actual_synced_on': fields.Datetime.now()})
                out['zeroed'] += 1
        return out

    # ---------------------------------------------------------- the expenses
    @api.model
    def _expenses(self, date_from, date_to, companies):
        out = {'written': 0, 'created': 0, 'skipped_fx': 0}
        Expense = self.env['pb.budget.expense'].sudo()
        rows = Expense.search([
            ('company_id', 'in', companies),
            ('period_month', '>=', date_from),
            ('period_month', '<=', date_to),
        ])
        keys = {(r.company_id.id, r.department_id.id or False, r.period_month,
                 r.budget_type) for r in rows}
        # Every key that ALREADY has a row is re-totalled too, so deleting the
        # last expense of a month puts its total back to zero rather than
        # leaving the previous figure standing.
        touched = self.env['wfp.budget.actual'].sudo().search([
            ('pb_budget_type', 'in', ('hr_ops', 'admin')),
            ('company_id', 'in', companies),
            ('period_month', '>=', date_from),
            ('period_month', '<=', date_to),
        ])
        keys |= {(r.company_id.id, r.department_id.id or False, r.period_month,
                  r.pb_budget_type) for r in touched}
        res = self.sync_expense_keys(keys)
        for k in out:
            out[k] += res.get(k, 0)
        return out

    @api.model
    def sync_expense_keys(self, keys):
        """Re-total exactly these (company, department, month, type) keys.

        Called by the expense model on every create, write and delete, and by
        the nightly job over its whole window. Idempotent both ways.
        """
        out = {'written': 0, 'created': 0, 'skipped_fx': 0, 'removed': 0}
        Expense = self.env['pb.budget.expense'].sudo()
        Budget = self.env['wfp.budget.actual'].sudo()
        for key in list(keys or ()):
            company_id, dept_id, month, btype = key
            if not month or btype not in ('hr_ops', 'admin'):
                continue
            dom = [('company_id', '=', company_id),
                   ('period_month', '=', month),
                   ('budget_type', '=', btype)]
            dom += ([('department_id', '=', dept_id)] if dept_id
                    else [('department_id', '=', False)])
            rows = Expense.search(dom)
            rec = Budget.search([
                ('company_id', '=', company_id),
                ('period_month', '=', month),
                ('pb_budget_type', '=', btype),
                ('department_id', '=', dept_id or False),
            ], limit=1)
            total, skipped = self._expense_total(rows, rec, company_id)
            out['skipped_fx'] += skipped
            if not rows and rec and rec.pb_source == 'auto' \
                    and not rec.forecast_cost:
                # An auto row that exists only because of an expense that has
                # since been deleted is noise, and noise on a budget board is
                # read as a mistake.
                rec.unlink()
                out['removed'] += 1
                continue
            posted = self._post(rec, (company_id, dept_id or False, month),
                                btype, total, None, out)
            if posted is None and not rec:
                continue
        return out

    @api.model
    def _expense_total(self, rows, rec, company_id):
        """Expenses summed INTO THE BUDGET ROW'S OWN CURRENCY.

        An expense in dollars against a budget in dong is a real thing and a
        number that ignores the difference is a lie by whatever the rate is. So
        each one is converted, and any that cannot be — no rate anywhere for
        that pair — is LEFT OUT and counted, never added at one for one (R23).
        """
        fx = self.env['pb.budget.fx']
        company = self.env['res.company'].sudo().browse(company_id)
        target = (rec.pb_currency_id if rec and rec.pb_currency_id
                  else company.currency_id)
        total, skipped = 0.0, 0
        for row in rows:
            src = row.currency_id or company.currency_id
            value, known = fx.convert(row.amount, src, target, row.spend_date)
            if not known:
                skipped += 1
                continue
            total += value
        return (target.round(total) if target else round(total, 2)), skipped

    # ------------------------------------------------------------- the write
    @api.model
    def _post(self, rec, key, btype, amount, heads, out):
        """Write the SPEND columns, and only ever those.

        `forecast_cost` and `forecast_headcount` are never named here. That is
        the safety rail this whole file is built around, and it is asserted by
        `tests/test_budget.py`.
        """
        company_id, dept_id, month = key
        Budget = self.env['wfp.budget.actual'].sudo()
        fx = self.env['pb.budget.fx']
        company = self.env['res.company'].sudo().browse(company_id)

        if rec:
            # The facts are in the company's own money; the row may not be.
            src = company.currency_id
            target = rec.pb_currency_id or src
            value, known = fx.convert(amount, src, target, month)
            if not known:
                out['skipped_fx'] = out.get('skipped_fx', 0) + 1
                return rec
            # ROUNDED TO THE ROW'S OWN CURRENCY BEFORE IT IS COMPARED, because
            # that is what the column will hold. A Monetary in dong keeps no
            # cents, so an unrounded 103,634,883.44 was written, read back as
            # 103,634,883 and found "changed" on the next run — for ever. The
            # figures were identical every time; only the count lied, which is
            # the kind of number somebody eventually acts on.
            value = target.round(value) if target else value
            vals = {'actual_cost': value,
                    'pb_actual_synced_on': fields.Datetime.now()}
            if heads is not None:
                vals['actual_headcount'] = heads
            changed = (abs((rec.actual_cost or 0.0) - value) > 0.005
                       or (heads is not None
                           and (rec.actual_headcount or 0) != heads))
            rec.write(vals)
            if changed:
                out['written'] = out.get('written', 0) + 1
            return rec

        if not amount and not (heads or 0):
            return None
        vals = {
            'company_id': company_id,
            'department_id': dept_id or False,
            'period_month': month,
            'pb_budget_type': btype,
            'pb_source': 'auto',
            'pb_currency_id': company.currency_id.id,
            'forecast_cost': 0.0,
            'forecast_headcount': 0,
            'actual_cost': (company.currency_id.round(amount)
                            if company.currency_id else amount),
            'actual_headcount': heads or 0,
            'pb_actual_synced_on': fields.Datetime.now(),
            'pb_note': _('Spend with no budget set against it.'),
        }
        rec = Budget.create(vals)
        out['created'] = out.get('created', 0) + 1
        return rec
