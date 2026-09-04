# -*- coding: utf-8 -*-
"""A month has one payroll, and the run shows the one that exists.

ABM's June 2026 run reported **146 employees and a total net of 0.00** with no
error anywhere. Two independent causes, both silent:

  * 152 computed payslips for June already existed — an import batch had made
    them, carrying 12,160 lines — but they belonged to no pay run, because the
    batch's own run had been deleted and `payslip_run_id` is `set null`. The
    wizard's "payroll already exists for this period" guard looks only at RUNS,
    so it saw an empty June and built a second, parallel one beside the real
    one.

  * every payslip in that second June was created with no `struct_id`, so the
    standard engine had no salary rules to walk. It walked none, wrote none,
    and returned success.

The repair is stated here as two rules: **claim what the period already has**,
and **never report a payslip as computed when it produced nothing**.
"""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRunAdoptsThePeriod(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Wizard = self.env['pb.payrun.wizard']
        self.company = self.env.company
        self.employee = self.env['hr.employee'].create({
            'name': 'Adopted Person', 'company_id': self.company.id})
        # A payslip line refuses to exist without a contract (om_hr_payroll),
        # and `_eligible_employees` only sees people whose contract is running.
        self.contract = self.env['hr.contract'].create({
            'name': 'Adopted contract', 'employee_id': self.employee.id,
            'wage': 10000.0, 'state': 'open', 'date_start': '2020-01-01',
            'company_id': self.company.id,
        })
        # `hr_payslip_line` requires both a category and a salary rule. The
        # category is also what says "this line is the net pay" — deliberately
        # NOT the line's code, which is whatever the scheme's author chose.
        self.category = self.env['hr.salary.rule.category'].search(
            [('code', '=', 'NET')], limit=1) \
            or self.env['hr.salary.rule.category'].search([], limit=1)
        self.salary_rule = self.env['hr.salary.rule'].search([], limit=1)
        self.vals = {'name': 'Probe June', 'date_start': '2026-06-01',
                     'date_end': '2026-06-30'}

    def _loose_slip(self, employee=None, lines=True, **overrides):
        """A computed payslip for June that belongs to no run."""
        vals = {
            'employee_id': (employee or self.employee).id,
            'name': 'Loose June slip',
            'contract_id': self.contract.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'company_id': self.company.id,
        }
        vals.update(overrides)
        slip = self.env['hr.payslip'].create(vals)
        if lines:
            self.env['hr.payslip.line'].create({
                # NETPAY, not NET: the code is the scheme author's word.
                'slip_id': slip.id, 'name': 'Net pay', 'code': 'NETPAY',
                'amount': 1000.0, 'quantity': 1.0, 'rate': 100.0,
                'employee_id': slip.employee_id.id,
                'contract_id': slip.contract_id.id,
                'category_id': self.category.id,
                'salary_rule_id': self.salary_rule.id,
            })
        return slip

    # ------------------------------------------------------ claiming the period
    def test_an_existing_payslip_joins_the_run_instead_of_being_rebuilt(self):
        slip = self._loose_slip()
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertEqual(prep['adopted'], 1)
        self.assertEqual(slip.payslip_run_id.id, prep['run_id'])

    def test_an_adopted_employee_is_not_computed_a_second_time(self):
        """This is the pay-run shape of the duplicate: two payslips, one month."""
        self._loose_slip()
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertNotIn(self.employee.id, prep['emp_ids'])

    def test_adoption_leaves_the_numbers_exactly_as_they_were(self):
        """Adopting is not recomputing. A batch's answer is the run's answer."""
        slip = self._loose_slip()
        self.Wizard.prepare_run(dict(self.vals))
        self.assertEqual(len(slip.line_ids), 1)
        self.assertEqual(slip.line_ids.amount, 1000.0)

    # --------------------------------------------- what must NOT be swept up
    def test_a_payslip_already_in_a_run_is_left_where_it_is(self):
        other = self.env['hr.payslip.run'].create({
            'name': 'Somebody else’s June',
            'date_start': '2026-06-01', 'date_end': '2026-06-30'})
        slip = self._loose_slip(payslip_run_id=other.id)
        # That run has payslips, so the wizard asks before overwriting rather
        # than quietly taking them.
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertTrue(prep.get('needs_confirmation'))
        self.assertEqual(slip.payslip_run_id, other)

    def test_an_uncomputed_payslip_is_not_adopted(self):
        """A blank draft is somebody's work in progress, not last month's answer."""
        self._loose_slip(lines=False)
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertEqual(prep['adopted'], 0)

    def test_a_different_period_is_not_adopted(self):
        self._loose_slip(date_from='2026-05-01', date_to='2026-05-31')
        prep = self.Wizard.prepare_run(dict(self.vals))
        self.assertEqual(prep['adopted'], 0)

    # ------------------------------------------- what the run then reports
    def test_the_runs_totals_reflect_what_it_adopted(self):
        """A run created seconds ago has already totalled an empty list.

        Its KPI band is a stored computed field over `slip_ids`, so without an
        explicit "this collection changed" the pay run goes on showing the same
        0.00 that started this.
        """
        self._loose_slip()
        prep = self.Wizard.prepare_run(dict(self.vals))
        run = self.env['hr.payslip.run'].browse(prep['run_id'])
        if 'pb_total_net' not in run._fields:
            self.skipTest("pb_payruns is not installed; no KPI band to check")
        self.assertEqual(run.pb_employee_count, 1)
        self.assertEqual(run.pb_total_net, 1000.0)

    def test_net_is_read_from_the_category_not_from_the_code(self):
        """ABM's net component is called NETPAY, and it is still net pay.

        Matching on the code flagged all 152 payslips as needing review while
        the run itself totalled ₫727,655,630.
        """
        slip = self._loose_slip()
        if self.category.code != 'NET':
            self.skipTest("no NET salary-rule category in this database")
        self.assertEqual(self.Wizard._slip_net(slip), 1000.0)

    # ------------------------------------------------ a chunk retried is safe
    def test_recomputing_a_chunk_does_not_add_a_second_payslip(self):
        """The client retries a chunk on a dropped connection."""
        prep = self.Wizard.prepare_run(dict(self.vals))
        payload = {'run_id': prep['run_id'], 'name': prep['name'],
                   'date_start': prep['date_start'], 'date_end': prep['date_end'],
                   'emp_ids': [self.employee.id]}
        self.env['hr.payslip'].create({
            'employee_id': self.employee.id, 'name': 'Already there',
            'contract_id': self.contract.id,
            'date_from': '2026-06-01', 'date_to': '2026-06-30',
            'payslip_run_id': prep['run_id'], 'company_id': self.company.id,
        })
        self.Wizard.compute_batch(payload)
        slips = self.env['hr.payslip'].search([
            ('payslip_run_id', '=', prep['run_id']),
            ('employee_id', '=', self.employee.id)])
        self.assertEqual(len(slips), 1)
