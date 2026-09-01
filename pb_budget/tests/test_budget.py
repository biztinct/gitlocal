# -*- coding: utf-8 -*-
"""pb_budget — the rails, in code.

Half of what this module promises is a NEGATIVE and a behaviour test cannot see
the absence of a thing: that the actuals job never writes a budget column, that
the narrow record rule ships with its wide partner beside it (R60), that no
user-visible string names the platform this is built on. Those are read out of
the SOURCE, with a paragraph each saying what the grep stands in for.

The behaviour tests are the other half, and they run against whatever this
database actually holds — skipping rather than passing vacuously when it holds
nothing (W78).
"""
import os
import re

from datetime import date

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(HERE, *parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestBudgetRails(TransactionCase):

    def test_the_actuals_job_never_names_a_budget_column(self):
        """THE SAFETY RAIL OF THE WHOLE MODULE.

        `forecast_cost` and `forecast_headcount` are the BUDGET. A job that
        could write them is a job that can lose a year's planning to a bad
        month of facts, and the failure would be silent — the number would
        simply be replaced by a derived one. The writer therefore never names
        either column outside a comment.
        """
        src = _read('models', 'budget_actuals.py')
        code = '\n'.join(ln for ln in src.splitlines()
                         if not ln.strip().startswith('#'))
        # A WRITE is a dict key or an assignment. READING `rec.forecast_cost`
        # to decide whether an empty auto row is worth keeping is not a write,
        # and the two zeroes put on a row the job CREATES for spend nobody
        # budgeted are not an overwrite of anything.
        allowed = ("'forecast_cost': 0.0", "'forecast_headcount': 0")
        writes = []
        for line in code.splitlines():
            body = line.split('#')[0]
            if not body.strip():
                continue
            for col in ('forecast_cost', 'forecast_headcount'):
                if ("'%s':" % col) in body or ('%s =' % col) in body:
                    if not any(a in body for a in allowed):
                        writes.append(body.strip())
        self.assertFalse(
            writes,
            'the actuals writer must never write a budget column: %s' % writes)

    def test_the_narrow_rule_ships_with_its_wide_partner(self):
        """R60 — `ir.rule` group rules are ORed over the rules that APPLY, so a
        narrow rule shipped ALONE is a narrowing. This module adds a
        function-head rule to a model an earlier module's groups can already
        read; without an explicit "everything" rule for those tiers beside it, a
        workforce-planning user who is also given a budget group would lose
        every row they can see today."""
        xml = _read('security', 'pb_budget_security.xml')
        self.assertIn('group_wfp_user', xml,
                      'the wide rule for the existing tiers must be here')
        self.assertIn('rule_budget_viewer_own_function', xml)
        self.assertIn('rule_budget_wfp_all', xml)
        # And the wide one comes FIRST in the file, so the pair reads as a pair.
        self.assertLess(xml.index('rule_budget_wfp_all'),
                        xml.index('rule_budget_viewer_own_function'))

    def test_the_cost_mirror_is_stated_once_and_matches_the_explorer(self):
        """The payroll figure on a budget row must be the SAME aggregation the
        Cost Explorer draws, or a person who questions it and goes to check will
        find a different number and trust neither. The category list is a module
        constant so there is one place to change it deliberately."""
        from odoo.addons.pb_budget.models.budget_common import COST_CATEGORY_TYPES
        from odoo.addons.pb_explorer.models.pb_explorer import _MEASURES
        self.assertEqual(tuple(COST_CATEGORY_TYPES),
                         tuple(_MEASURES['total_cost']['types']),
                         'the mirror has drifted from the Cost Explorer')
        src = _read('models', 'budget_actuals.py')
        self.assertIn('COALESCE(is_rollup, FALSE) = FALSE', src,
                      'a money measure counts each dong once (VALUEKIND)')

    def test_no_user_visible_string_names_the_platform(self):
        """White-label. Technical identifiers are untouched; what a person can
        READ never says it."""
        bad = []
        for folder, _dirs, files in os.walk(HERE):
            if '__pycache__' in folder or '/tests' in folder:
                continue
            for name in files:
                if not name.endswith(('.py', '.xml', '.js', '.csv', '.scss')):
                    continue
                text = _read(os.path.relpath(os.path.join(folder, name), HERE))
                for m in re.finditer(r'[Oo]doo', text):
                    line = text[:m.start()].count('\n') + 1
                    src = text.splitlines()[line - 1]
                    if any(tok in src for tok in (
                            'from odoo', 'import odoo', 'odoo.addons',
                            '@odoo-module', '@odoo/', '<odoo>', '</odoo>',
                            'odoo-bin', 'Odoo 19', 'odoo/orm',
                            '# ', '//', '*')):
                        continue
                    bad.append('%s:%s %s' % (name, line, src.strip()))
        self.assertFalse(bad, 'user-visible strings must never name it: %s' % bad)

    def test_the_motion_is_entirely_inside_the_reduced_motion_block(self):
        """R85 — the opacity, the transform AND the animation all live inside
        `prefers-reduced-motion: no-preference`, so a person who has asked for
        less movement gets the finished board on the first frame rather than an
        animation that is declared and then cancelled."""
        scss = _read('static', 'src', 'scss', 'budget.scss')
        block = scss.split('@media (prefers-reduced-motion: no-preference)')[-1]
        for decl in ('opacity: 0', 'transform: translateY', 'animation: bdg-rise'):
            self.assertIn(decl, block, '%s must be inside the block' % decl)
        # And the keyframes are at the TOP level, or Sass nests them and no
        # browser plays them.
        self.assertTrue(scss.index('@keyframes bdg-rise')
                        < scss.index('.pbim.bdg'))

    def test_the_cron_is_anchored_on_a_concrete_model(self):
        """An `ir.cron` whose `model_id` points at an abstract model is a trap
        Odoo does not warn about."""
        cron = self.env.ref('pb_budget.cron_budget_actuals')
        self.assertFalse(self.env[cron.model_id.model]._abstract)

    def test_the_module_ships_no_menu(self):
        """The rail is eight items and the Budget lens is not one of them: its
        doors are the Insights mission and the command palette."""
        acts = self.env['ir.actions.act_window'].search(
            [('res_model', 'in', ('pb.budget.expense', 'wfp.budget.actual'))])
        menus = self.env['ir.ui.menu'].search(
            [('action', 'in', ['ir.actions.act_window,%s' % a.id for a in acts])])
        self.assertFalse(menus, 'pb_budget must ship no ir.ui.menu')


@tagged('post_install', '-at_install')
class TestBudgetModel(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Budget = self.env['wfp.budget.actual']
        self.company = self.env.company
        self.dept = self.env['hr.department'].search(
            [('company_id', '=', self.company.id), ('parent_id', '!=', False)],
            limit=1)

    def test_the_shipped_columns_keep_their_meaning(self):
        """`forecast_*` is the budget, `actual_*` is the spend, and the variance
        is the first minus the second — exactly as the model shipped. This test
        exists so a later phase that changes one of them has to say so out loud."""
        row = self.Budget.create({
            'company_id': self.company.id,
            'period_month': date(2026, 1, 1),
            'pb_budget_type': 'admin',
            'forecast_cost': 100.0,
            'actual_cost': 30.0,
        })
        self.assertEqual(row.variance_amount, 70.0)
        self.assertEqual(row.variance_pct, 70.0)
        self.assertFalse(row.pb_unbudgeted)

    def test_a_row_with_spend_and_no_budget_is_flagged(self):
        row = self.Budget.create({
            'company_id': self.company.id,
            'period_month': date(2026, 2, 1),
            'pb_budget_type': 'admin',
            'actual_cost': 500.0,
        })
        self.assertTrue(row.pb_unbudgeted)

    def test_a_budget_row_needs_no_scenario_and_carries_its_own_company(self):
        """The two overrides this module makes, asserted. Without the second, a
        scenario-less row would carry NO company — and a company-less row is
        visible to everybody (R8), which is the boundary country HR relies on."""
        row = self.Budget.create({
            'company_id': self.company.id,
            'period_month': date(2026, 3, 1),
        })
        self.assertFalse(row.scenario_id)
        self.assertEqual(row.company_id, self.company)
        self.assertEqual(row.pb_currency_id, self.company.currency_id)
        self.assertEqual(row.currency_id, row.pb_currency_id)

    def test_the_function_is_the_top_of_the_tree(self):
        if not self.dept:
            self.skipTest('no nested department on this database')
        root = self.dept
        while root.parent_id:
            root = root.parent_id
        row = self.Budget.create({
            'company_id': self.company.id,
            'department_id': self.dept.id,
            'period_month': date(2026, 4, 1),
        })
        self.assertEqual(row.pb_function_id, root)

    def test_an_expense_rolls_into_its_month(self):
        Expense = self.env['pb.budget.expense']
        exp = Expense.create({
            'name': 'Test course',
            'spend_date': date(2026, 5, 12),
            'budget_type': 'hr_ops',
            'amount': 1234.0,
            'company_id': self.company.id,
            'currency_id': self.company.currency_id.id,
        })
        row = self.Budget.search([
            ('company_id', '=', self.company.id),
            ('period_month', '=', date(2026, 5, 1)),
            ('pb_budget_type', '=', 'hr_ops'),
            ('department_id', '=', False),
        ], limit=1)
        self.assertTrue(row, 'the expense should have made itself a row')
        self.assertEqual(round(row.actual_cost), 1234)
        exp.write({'amount': 2000.0})
        row.invalidate_recordset()
        self.assertEqual(round(row.actual_cost), 2000)
        exp.unlink()
        self.assertFalse(row.exists(),
                         'an auto row with nothing left in it is noise')

    def test_conversion_refuses_when_nobody_has_set_a_rate(self):
        """R23 — `_convert()` with no rate returns the amount UNCHANGED. Two
        different currencies reported at the SAME rate means nobody has told
        this database what one is worth in the other, and the honest answer is
        no number at all."""
        fx = self.env['pb.budget.fx']
        cur = self.env['res.currency']
        made = cur.sudo().create({'name': 'ZZT', 'symbol': 'Z'})
        vnd = cur.sudo().search([('name', '=', 'VND')], limit=1)
        if not vnd:
            self.skipTest('no second currency on this database')
        # ZZT has no `res.currency.rate` row at all, so it silently reads as
        # 1.0 — and converting it into a currency that DOES have one produces a
        # plausible number built on nothing. That is what this refuses.
        value, known = fx.convert(1000, made, vnd)
        self.assertFalse(known)
        self.assertEqual(value, 0.0)
        # A manual rate is the row's own answer and always wins.
        value, known = fx.convert(1000, made, vnd, manual_rate=2.5)
        self.assertTrue(known)
        self.assertEqual(value, 2500.0)


@tagged('post_install', '-at_install')
class TestBudgetBoard(TransactionCase):

    def test_the_board_answers_and_says_where_the_year_is(self):
        board = self.env['pb.budget'].get_board()
        self.assertTrue(board['ok'])
        for key in ('fy', 'months', 'functions', 'kpis', 'pace', 'headline',
                    'currency'):
            self.assertIn(key, board)
        self.assertEqual(len(board['months']), 12)
        self.assertTrue(0 <= board['pace'] <= 100)

    def test_a_person_with_no_budget_group_is_told_so_in_words(self):
        user = self.env['res.users'].sudo().create({
            'name': 'Budget nobody', 'login': 'budget.nobody.test@example.com',
            'email': 'budget.nobody.test@example.com',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        with self.assertRaises(AccessError):
            self.env['pb.budget'].with_user(user).get_board()
