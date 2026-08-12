# -*- coding: utf-8 -*-
"""The derived payroll fact tables (Sudima Phase N).

Why these exist
---------------
``hr.payslip.line`` prototype-inherits ``hr.salary.rule``
(``om_hr_payroll/models/hr_payslip.py:883``), so every one of the 711,150 lines
on the live demo world carries the rule's ``condition_python`` (~700 B default)
and ``amount_python_compute`` (~650 B default) columns. A full aggregate over
that table drags ~1 GB off disk and takes 11.3 s (measured, C18.82) — and no
index fixes it, because it IS a full-table aggregate.

Pre-aggregating collapses those 711,150 lines to ~6,000 rows (measured
2026-07-26: 5,971 at the T1 grain, a 119:1 compression) whose totals reconcile
to the stored ``pb_total_net`` roll-ups exactly. Interactive pivoting becomes
possible: the build costs ~18 s once per full rebuild, every query after that
answers in single-digit milliseconds.

The three tables
----------------
``pb.fact.run``   one header row per built run — dimensions, freshness token and
                  the COVERAGE counters that keep the board honest.
``pb.fact.line``  T1, the Explorer's workhorse: run x cycle x division x
                  department x category_type x component.
``pb.fact.emp``   T2, run x employee x category_type — the only correct source
                  for headcount distincts, the drill, and the matched-employee
                  set the variance waterfall reconciles against.

Grain warning (deliberate, enforced in the facade)
--------------------------------------------------
``pb.fact.line.headcount`` is a DISTINCT count *at its own grain*. Summing it
across components double-counts people. Every headcount measure in the Explorer
is therefore routed to T2, never to T1 — see ``pb_explorer._MEASURES``.

These tables are DERIVED. They are never edited by hand and never carry data
that cannot be rebuilt from payslip truth: dropping and rebuilding them is
always safe. Only ``pb.fact.builder`` writes here.
"""

from odoo import fields, models

# Basis of a fact row. 'approved' == the run reached the terminal approved state
# ('done' is the signal pb_pay_delivery and payroll analytics already read,
# pb_payruns/models/hr_payslip_run.py); anything else in flight is provisional
# and is HATCHED in the UI rather than silently mixed into approved figures.
BASIS = [('approved', 'Approved'), ('provisional', 'Provisional')]


class PbFactRun(models.Model):
    _name = 'pb.fact.run'
    _description = 'Payroll fact — run header'
    _order = 'date_end desc, id desc'
    _rec_name = 'name'

    run_id = fields.Many2one('hr.payslip.run', string='Pay Run', required=True,
                             ondelete='cascade', index=True)
    company_id = fields.Many2one('res.company', string='Company', index=True)
    name = fields.Char()
    date_start = fields.Date()
    date_end = fields.Date(index=True)

    # Time grains, materialised so the Explorer never date_truncs at read time.
    month = fields.Date(string='Month', index=True, help='First day of the run month')
    year = fields.Integer(index=True)
    quarter = fields.Char(help="e.g. '2026-Q2'")

    cycle = fields.Char(help="Formula config cycle_type: 'mid' / 'end' / ''")
    division = fields.Char(index=True)
    division_label = fields.Char()
    state = fields.Char()
    basis = fields.Selection(BASIS, index=True)

    employee_count = fields.Integer()
    net_total = fields.Float(digits=(16, 2))

    # ---- freshness (see pb.fact.builder._token) -------------------------
    token = fields.Char(help='Source fingerprint; a mismatch forces a rebuild')
    dirty = fields.Boolean(default=False, index=True,
                           help='Set by the hr.payslip.run write hook')
    built_on = fields.Datetime()
    build_ms = fields.Integer(string='Build (ms)')

    # ---- coverage: surfaced on the board, never silently swallowed ------
    source_slip_count = fields.Integer()
    source_line_count = fields.Integer()
    fact_line_count = fields.Integer()
    asof_fallback_count = fields.Integer(
        string='As-of fallbacks',
        help='Payslips whose employee had no hr.version dated on or before the '
             'period end, so the EARLIEST version was used to resolve the '
             'department instead. Surfaced on the board.')
    untyped_category_count = fields.Integer(
        string='Untyped categories',
        help="Distinct salary-rule categories with no category_type. The platform "
             "defaults that field to 'allowance' "
             "(pb_hr_payroll_base/models/hr_payroll_structure_base.py:224), so "
             "an untyped category silently reads as an allowance — the count is "
             "surfaced so the number can be trusted or questioned.")

    line_ids = fields.One2many('pb.fact.line', 'fact_run_id')
    emp_ids = fields.One2many('pb.fact.emp', 'fact_run_id')

    _sql_constraints = [
        ('run_uniq', 'unique(run_id)', 'One fact header per pay run.'),
    ]


class PbFactLine(models.Model):
    _name = 'pb.fact.line'
    _description = 'Payroll fact — component grain (T1)'
    _order = 'id'

    fact_run_id = fields.Many2one('pb.fact.run', required=True,
                                  ondelete='cascade', index=True)
    # Denormalised so a query can filter without joining the header.
    run_id = fields.Many2one('hr.payslip.run', index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', index=True)
    month = fields.Date(index=True)
    year = fields.Integer(index=True)
    quarter = fields.Char()
    cycle = fields.Char()
    division = fields.Char(index=True)
    basis = fields.Selection(BASIS, index=True)

    department_id = fields.Many2one('hr.department', index=True)
    category_id = fields.Many2one('hr.salary.rule.category')
    category_type = fields.Char(index=True)
    code = fields.Char(index=True, help='Component code — the join key to budgets')
    rule_id = fields.Many2one('hr.salary.rule',
                              help='Live rule, for the translated display label')
    component_name = fields.Char(help='Label snapshot; fallback when rule_id is gone')

    amount = fields.Float(digits=(16, 2))
    headcount = fields.Integer(
        help='DISTINCT employees AT THIS GRAIN ONLY. Never SUM this across '
             'components — use pb.fact.emp for headcount measures.')
    line_count = fields.Integer()


class PbFactEmp(models.Model):
    _name = 'pb.fact.emp'
    _description = 'Payroll fact — employee grain (T2)'
    _order = 'id'

    fact_run_id = fields.Many2one('pb.fact.run', required=True,
                                  ondelete='cascade', index=True)
    run_id = fields.Many2one('hr.payslip.run', index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', index=True)
    month = fields.Date(index=True)
    year = fields.Integer(index=True)
    quarter = fields.Char()
    cycle = fields.Char()
    division = fields.Char(index=True)
    basis = fields.Selection(BASIS, index=True)

    employee_id = fields.Many2one('hr.employee', index=True, ondelete='cascade')
    department_id = fields.Many2one('hr.department', index=True)
    job_id = fields.Many2one('hr.job', index=True)
    category_type = fields.Char(index=True)

    amount = fields.Float(digits=(16, 2))
