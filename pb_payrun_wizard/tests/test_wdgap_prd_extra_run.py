# -*- coding: utf-8 -*-
"""WDGAP PR-D — the third kind of pay run: an Extra run.

docs/handovers/wdgap/WDGAP_PR_D_HANDOVER.md §4, tests T1-T5, T7 and T8.

An Extra run is for the people somebody picks, for a bonus, a correction or
one extra payslip. Three rails make it safe to run more than once a month:

* it never meets another run — no "already exists", no *Clean and Run*, no
  adoption of the month's loose payslips (R2);
* it is refused without people, and refuses by name anybody the scheme does
  not pay for the period (R3);
* it needs a name, so a person can tell it from the month's regular run.
"""
import unittest

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

try:        # T7 reuses the one-off fixture of pb_updates when it is there
    from odoo.addons.pb_updates.tests.test_updates_p2d import (
        BON, P2dFixture)
except Exception:       # noqa: BLE001 — pb_updates is not a dependency
    P2dFixture = None


class _ExtraRunFixture(TransactionCase):
    """A company of its own with ONE live scheme, so the scheme map's "the
    only scheme in this company" answer covers everybody with a contract —
    the population every wizard door already uses."""

    def setUp(self):
        super().setUp()
        Run = self.env['hr.payslip.run']
        if 'pb_run_kind' not in Run._fields:
            self.skipTest('pb_payruns (the kind of run) is not installed here.')
        if 'extra' not in dict(Run._fields['pb_run_kind'].selection):
            self.skipTest('This build has no Extra run.')
        self.company = self.env['res.company'].create({'name': 'Extra run test company'})
        self.env = self.env(context=dict(self.env.context,
                                         allowed_company_ids=self.company.ids))
        self.Run = self.env['hr.payslip.run']
        self.Slip = self.env['hr.payslip']
        self.Wizard = self.env['pb.payrun.wizard']
        self.config = None
        Config = self.env.get('hr.formula.config')
        if Config is not None and 'pb_formula_config_id' in self.Run._fields:
            self.config = Config.create({
                'name': 'Extra Probe Payroll', 'code': 'XPROBE',
                'state': 'active', 'country_code': 'VN',
                'company_id': self.company.id})
            category = self.env['hr.salary.rule.category'].search([], limit=1)
            self.basic = self.env['hr.formula.rule'].create({
                'config_id': self.config.id, 'name': 'Extra Probe Basic',
                'code': 'XPBASIC', 'column_type': 'input', 'sequence': 1,
                'default_value': 0.0, 'appears_on_payslip': True,
                'category_id': category.id})
        self.ann = self._person('Extra Ann', 10000.0)
        self.bob = self._person('Extra Bob', 20000.0)
        self.cat = self._person('Extra Cat', 30000.0)
        self.vals = {'name': 'Extra run — Probe — 14 Aug 2026',
                     'date_start': '2026-08-01', 'date_end': '2026-08-31',
                     'run_kind': 'extra'}
        if self.config:
            self.vals['formula_config_id'] = self.config.id

    def _person(self, name, wage, company=None, contract=True,
                date_start='2020-01-01', date_end=False, state='open'):
        company = company or self.company
        employee = self.env['hr.employee'].create({
            'name': name, 'company_id': company.id})
        if contract:
            self.env['hr.contract'].create({
                'name': '%s contract' % name, 'employee_id': employee.id,
                'wage': wage, 'state': state, 'date_start': date_start,
                'date_end': date_end, 'company_id': company.id})
        return employee

    def _run(self, kind='regular', name='August regular', people=None,
             state=None):
        vals = {'name': name, 'date_start': '2026-08-01',
                'date_end': '2026-08-31', 'pb_run_kind': kind}
        if self.config:
            vals['pb_formula_config_id'] = self.config.id
        run = self.Run.create(vals)
        for employee in (people or self.ann):
            self._slip(employee, run)
        if state:
            run.slip_ids.write({'state': 'done'})
            # the run's own state is sealed (approvals only): set it the way a
            # finished approval leaves it, below the ORM
            self.env.flush_all()
            self.env.cr.execute(
                "UPDATE hr_payslip_run SET state = %s WHERE id = %s",
                (state, run.id))
            run.invalidate_recordset()
        return run

    def _slip(self, employee, run=None, lines=True):
        contract = self.env['hr.contract'].search(
            [('employee_id', '=', employee.id)], limit=1)
        vals = {'employee_id': employee.id, 'name': '%s August' % employee.name,
                'contract_id': contract.id,
                'payslip_run_id': run.id if run else False,
                'date_from': '2026-08-01', 'date_to': '2026-08-31',
                'company_id': employee.company_id.id}
        if self.config:
            vals['formula_config_id'] = self.config.id
        slip = self.Slip.create(vals)
        if lines:
            category = self.env['hr.salary.rule.category'].search(
                [('code', '=', 'NET')], limit=1) \
                or self.env['hr.salary.rule.category'].search([], limit=1)
            self.env['hr.payslip.line'].create({
                'slip_id': slip.id, 'name': 'Net pay', 'code': 'NETPAY',
                'amount': 1000.0, 'quantity': 1.0, 'rate': 100.0,
                'employee_id': employee.id, 'contract_id': contract.id,
                'category_id': category.id,
                'salary_rule_id': self.env['hr.salary.rule'].search([], limit=1).id})
        return slip

    def _extra(self, people, **extra):
        """prepare_run + compute_batch, the way the screen runs it."""
        vals = dict(self.vals, employee_ids=[p.id for p in people], **extra)
        prep = self.Wizard.prepare_run(vals)
        self.assertTrue(prep.get('run_id'), prep)
        self.Wizard.compute_batch(prep)
        return self.Run.browse(prep['run_id']), prep

    @staticmethod
    def _lines(run):
        return sorted((s.employee_id.id, l.code, round(l.total, 2))
                      for s in run.slip_ids for l in s.line_ids)


@tagged('post_install', '-at_install', 'wdgap_prd')
class TestExtraRun(_ExtraRunFixture):

    # ================================================================ T1
    def test_t1_an_extra_run_pays_exactly_the_people_picked(self):
        run, prep = self._extra([self.ann, self.bob])
        self.assertEqual(run.pb_run_kind, 'extra')
        self.assertEqual(sorted(prep['emp_ids']), sorted([self.ann.id, self.bob.id]))
        self.assertEqual(prep['adopted'], 0)
        self.assertEqual(len(run.slip_ids), 2)
        self.assertEqual(set(run.slip_ids.mapped('employee_id').ids),
                         {self.ann.id, self.bob.id})
        self.assertNotIn(self.cat, run.slip_ids.mapped('employee_id'))
        # the payslip says which run it is, so it cannot be mistaken for the
        # month's regular payslip (PDF file name, lists)
        for slip in run.slip_ids:
            self.assertIn(self.vals['name'], slip.name)

    def test_t1_a_retried_chunk_never_pays_twice(self):
        run, prep = self._extra([self.ann])
        self.Wizard.compute_batch(prep)
        self.assertEqual(len(run.slip_ids), 1)

    def test_t1_the_older_door_runs_an_extra_run_too(self):
        before = set(self.Run.search([]).ids)
        self.Wizard.create_and_compute(dict(self.vals, employee_ids=[self.bob.id]))
        made = self.Run.search([('id', 'not in', list(before))])
        self.assertEqual(len(made), 1)
        self.assertEqual(made.pb_run_kind, 'extra')
        self.assertEqual(made.slip_ids.mapped('employee_id'), self.bob)

    # ================================================================ T2
    def test_t2_beside_a_finished_regular_run_nothing_of_it_changes(self):
        regular = self._run(people=self.ann | self.bob | self.cat, state='done')
        before = self._lines(regular)
        slips = regular.slip_ids
        states = slips.mapped('state')
        run, _prep = self._extra([self.ann])
        self.assertNotEqual(run, regular)
        self.assertTrue(regular.exists())
        self.assertEqual(regular.state, 'done')
        self.assertEqual(regular.slip_ids, slips)
        self.assertEqual(slips.mapped('state'), states)
        self.assertEqual(slips.mapped('payslip_run_id'), regular)
        self.assertEqual(self._lines(regular), before)
        self.assertEqual(len(run.slip_ids), 1)

    def test_t2_beside_a_draft_regular_and_a_topup_nothing_is_asked(self):
        regular = self._run(people=self.ann | self.bob)
        topup = self._run('topup', 'August awards')
        plan = self.Wizard.plan_preview(dict(self.vals, employee_ids=[self.ann.id]))
        self.assertEqual(plan['existing'], [])
        self.assertEqual(plan['blockers'], [])
        self.assertEqual(plan['adopt'], 0)
        self.assertEqual(plan['total'], 1)
        prep = self.Wizard.prepare_run(dict(self.vals, employee_ids=[self.ann.id]))
        self.assertFalse(prep.get('needs_confirmation'))
        self.assertFalse(prep.get('blocked'))
        self.assertEqual(len(regular.slip_ids), 2)
        self.assertEqual(len(topup.slip_ids), 1)

    # ================================================================ T3
    def test_t3_two_extra_runs_in_one_month_are_allowed(self):
        first, _p = self._extra([self.ann])
        second, prep = self._extra(
            [self.ann], name='Extra run — Probe — 20 Aug 2026')
        self.assertFalse(prep.get('needs_confirmation'))
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists())
        self.assertEqual(len(first.slip_ids), 1)
        self.assertEqual(len(second.slip_ids), 1)
        # and they do not make a Regular or a Top-up run "already exist"
        for kind in ('regular', 'topup'):
            self.assertFalse(self.Wizard._period_runs(
                '2026-08-01', '2026-08-31', config=self.config, kind=kind), kind)

    def test_t3_an_extra_run_needs_a_name(self):
        for name in ('', '   ', None):
            vals = dict(self.vals, name=name, employee_ids=[self.ann.id])
            for door in ('prepare_run', 'create_and_compute'):
                before = self.Run.search_count([])
                with self.assertRaises(UserError) as caught:
                    getattr(self.Wizard, door)(vals)
                self.assertIn('name', str(caught.exception))
                self.assertEqual(self.Run.search_count([]), before, door)

    # ================================================================ T4
    def test_t4_an_extra_run_with_nobody_is_refused(self):
        for people in (None, []):
            vals = dict(self.vals, employee_ids=people)
            for door in ('prepare_run', 'create_and_compute', 'plan_preview'):
                before = self.Run.search_count([])
                with self.assertRaises(UserError) as caught:
                    getattr(self.Wizard, door)(vals)
                self.assertIn('Pick at least one person', str(caught.exception))
                self.assertEqual(self.Run.search_count([]), before, door)

    def test_t4_somebody_the_scheme_does_not_pay_is_refused_by_name(self):
        other = self.env['res.company'].create({'name': 'Elsewhere Co'})
        stranger = self._person('Extra Stranger', 5000.0, company=other)
        leaver = self._person('Extra Leaver', 5000.0, date_start='2020-01-01',
                              date_end='2026-06-30', state='close')
        for person in (stranger, leaver):
            before = self.Run.search_count([])
            with self.assertRaises(UserError) as caught:
                self.Wizard.prepare_run(dict(
                    self.vals, employee_ids=[self.ann.id, person.id]))
            self.assertIn(person.name, str(caught.exception))
            self.assertNotIn('Extra Ann', str(caught.exception))
            self.assertEqual(self.Run.search_count([]), before)

    def test_t4_the_employment_status_ticks_never_drop_a_pick(self):
        """The people are picked one by one; a status filter meant for the
        whole-month run does not quietly take one of them away."""
        prep = self.Wizard.prepare_run(dict(
            self.vals, employee_ids=[self.ann.id], statuses=['Nobody']))
        self.assertEqual(prep['emp_ids'], [self.ann.id])

    # ================================================================ T5
    def test_t5_clean_and_run_is_never_offered_nor_done(self):
        regular = self._run(people=self.ann | self.bob)
        topup = self._run('topup', 'August awards')
        extra = self._run('extra', 'Extra run — earlier')
        keep = {r: r.slip_ids for r in (regular, topup, extra)}
        for door in ('prepare_run', 'create_and_compute'):
            answer = getattr(self.Wizard, door)(dict(
                self.vals, employee_ids=[self.ann.id], force_clean=True))
            self.assertFalse(answer.get('needs_confirmation'), door)
            for run, slips in keep.items():
                self.assertTrue(run.exists(), door)
                self.assertEqual(run.slip_ids, slips, door)
        # the clean itself refuses to clear anything for an Extra run
        cleared = self.Wizard.sudo()._clean_period(
            (regular | topup | extra).sudo(), kind='extra')
        self.assertEqual(cleared, 0)
        for run in keep:
            self.assertTrue(run.exists())

    def test_t5_regular_and_topup_cleans_never_reach_an_extra_run(self):
        extra = self._run('extra', 'Extra run — earlier')
        slips = extra.slip_ids
        for kind in ('regular', 'topup'):
            self.Wizard.sudo()._clean_period(extra.sudo(), kind=kind)
            self.assertTrue(extra.exists(), kind)
            self.assertEqual(extra.slip_ids, slips, kind)
        for kind in (None, 'regular', 'topup'):
            vals = dict(self.vals, run_kind=kind or False, force_clean=True,
                        name='Payroll August')
            vals.pop('employee_ids', None)
            self.Wizard.prepare_run(vals)
            self.assertTrue(extra.exists(), kind)
            self.assertEqual(extra.slip_ids, slips, kind)

    def test_t5_loose_payslips_are_never_adopted(self):
        loose = self._slip(self.ann)
        run, prep = self._extra([self.bob])
        self.assertEqual(prep['adopted'], 0)
        self.assertFalse(loose.payslip_run_id)
        self.assertEqual(run.slip_ids.mapped('employee_id'), self.bob)
        # even when the loose payslip's own person is picked
        run2, prep2 = self._extra([self.ann], name='Extra run — again')
        self.assertEqual(prep2['adopted'], 0)
        self.assertFalse(loose.payslip_run_id)
        self.assertNotIn(loose, run2.slip_ids)
        plan = self.Wizard.plan_preview(dict(self.vals, employee_ids=[self.ann.id]))
        self.assertEqual(plan['adopt'], 0)

    # =============================================================== R4
    def test_r4_the_kind_only_changes_while_draft(self):
        run, _p = self._extra([self.ann])
        run.pb_run_kind = 'regular'
        run.pb_run_kind = 'extra'
        self.env.cr.execute(
            "UPDATE hr_payslip_run SET state = 'done' WHERE id = %s", (run.id,))
        run.invalidate_recordset()
        with self.assertRaises(UserError):
            run.write({'pb_run_kind': 'regular'})

    # =============================================================== R1
    def test_r1_regular_and_topup_doors_are_unchanged(self):
        """The first step still offers the choice; no kind = Regular; the
        Regular door still adopts loose payslips."""
        defaults = self.Wizard.get_defaults()
        self.assertTrue(defaults.get('run_kinds'))
        self.assertIn('extra', defaults.get('run_kind_options') or [])
        loose = self._slip(self.cat)
        vals = dict(self.vals, name='Payroll August')
        vals.pop('run_kind')
        prep = self.Wizard.prepare_run(vals)
        self.assertEqual(self.Run.browse(prep['run_id']).pb_run_kind, 'regular')
        self.assertEqual(prep['adopted'], 1)
        self.assertEqual(loose.payslip_run_id.id, prep['run_id'])
        self.assertEqual(self.Wizard._run_kind_from_vals({'run_kind': 'bonus'}),
                         'regular')

    def test_r1_a_regular_payslip_computes_the_same_beside_an_extra_run(self):
        """Golden: the same person, the same month, computed before and after
        an Extra run exists — identical lines."""
        if not self.config:
            self.skipTest('No payroll schemes on this build.')
        vals = dict(self.vals, name='Payroll August')
        vals.pop('run_kind')
        prep = self.Wizard.prepare_run(vals)
        self.Wizard.compute_batch(prep)
        regular = self.Run.browse(prep['run_id'])
        golden = self._lines(regular)
        self.assertEqual(len(regular.slip_ids), 3)
        self._extra([self.ann])
        regular.slip_ids.compute_sheet()
        self.assertEqual(self._lines(regular), golden)


@tagged('post_install', '-at_install', 'wdgap_prd')
class TestExtraRunMonthTotals(_ExtraRunFixture):
    """T8 — a month's totals add the Extra payslip once (scope 6)."""

    def test_t8_the_explorer_counts_the_extra_payslip_once(self):
        if 'pb.fact.builder' not in self.env:
            self.skipTest('The Explorer is not installed here.')
        regular = self._run(people=self.ann)
        extra = self._run('extra', 'Extra run — bonus')
        role = 'pay_role' in self.env['hr.payslip.line']._fields
        for run, amount in ((regular, 1000.0), (extra, 250.0)):
            line = run.slip_ids.line_ids
            vals = {'amount': amount}
            if role:
                vals['pay_role'] = 'net'
            line.write(vals)
        self.env.flush_all()
        self.env['pb.fact.builder'].sudo().build_runs((regular | extra).ids)
        rows = self.env['pb.fact.emp'].sudo().search([
            ('run_id', 'in', (regular | extra).ids),
            ('employee_id', '=', self.ann.id), ('category_type', '=', 'net')])
        self.assertEqual(len(rows), 2, 'one row per run, each payslip once')
        self.assertAlmostEqual(sum(rows.mapped('amount')), 1250.0)
        self.assertEqual(set(rows.mapped('month')), {rows[:1].month})


if P2dFixture is not None:
    @tagged('post_install', '-at_install', 'wdgap_prd')
    class TestExtraRunOneoffs(P2dFixture):
        """T7 — a one-off pay item is paid once, whichever run takes it.

        The observed rule (pb_updates' paid-once guard, unchanged): an item
        is taken by the FIRST payslip that computes with it for that person
        and month — Regular, Top-up or Extra alike — and no other payslip can
        read it while that payslip holds it. So an item a regular run has
        reserved or paid never reaches an Extra run, and an item still
        waiting is paid by an Extra run that runs first, once.
        """

        @classmethod
        def setUpClass(cls):
            super().setUpClass()
            Run = cls.env['hr.payslip.run']
            if 'extra' not in dict(Run._fields['pb_run_kind'].selection or []):
                raise unittest.SkipTest('This build has no Extra run.')

        def _extra(self, employee, name):
            prep = self.W.prepare_run({
                'name': name, 'date_start': '2026-11-01', 'date_end': '2026-11-30',
                'formula_config_id': self.monthly.id, 'run_kind': 'extra',
                'employee_ids': [employee.id]})
            self.W.compute_batch(prep)
            run = self.env['hr.payslip.run'].browse(prep['run_id'])
            self.assertEqual(run.slip_ids.employee_id, employee)
            return run.slip_ids

        def test_t7_an_item_a_regular_run_holds_never_reaches_an_extra_run(self):
            self.send([['Code', 'P2D Bonus'], ['P2D0001', '500']], {2: BON})
            regular = self.slip(self.ann, self.make_run())
            self.assertEqual(self.line(regular, 'P2DBON').total, 500.0)
            row = self.row(self.ann)
            self.assertEqual(row.state, 'reserved')
            extra = self._extra(self.ann, 'Extra run — Ann — reserved')
            self.assertFalse(self.line(extra, 'P2DBON').total)
            self.assertEqual(row.reserved_slip_id, regular)
            # …and once the regular payslip is paid, still never again
            regular.write({'state': 'done'})
            self.assertEqual(row.state, 'paid')
            again = self._extra(self.ann, 'Extra run — Ann — paid')
            self.assertFalse(self.line(again, 'P2DBON').total)
            self.assertEqual(row.paid_slip_id, regular)

        def test_t7_an_item_still_waiting_is_paid_once_by_an_extra_run(self):
            self.send([['Code', 'P2D Bonus'], ['P2D0002', '700']], {2: BON})
            extra = self._extra(self.amy, 'Extra run — Amy')
            self.assertEqual(self.line(extra, 'P2DBON').total, 700.0)
            row = self.row(self.amy)
            self.assertEqual(row.state, 'reserved')
            self.assertEqual(row.reserved_slip_id, extra)
            # the month's regular run, made afterwards, does not pay it again
            regular = self.slip(self.amy, self.make_run())
            self.assertFalse(self.line(regular, 'P2DBON').total)
            # and a second Extra run does not either
            second = self._extra(self.amy, 'Extra run — Amy — again')
            self.assertFalse(self.line(second, 'P2DBON').total)
            self.assertEqual(row.reserved_slip_id, extra)
