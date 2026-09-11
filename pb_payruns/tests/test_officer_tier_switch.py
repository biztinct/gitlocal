# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""The Officer tier is a per-database setting, and switching it off is complete.

A tenant may run Draft → HR review → Finance approval. "Complete" is the word
that matters: it is not enough for the column to disappear. The submit has to
land on HR review, the send-back out of HR review has to reach Draft rather than
a stage nobody uses, and every surface that draws the chain — the board, the
Approvals cockpit, the form stepper — has to draw the same one. A screen that
keeps its own copy of the stage list is how a button comes to offer a stage the
model refuses.

The tests below therefore assert the DEFAULT first (every existing database is
untouched), then the switched-off behaviour, then that a run already parked at
the retired stage is still reachable — because payroll in flight when a setting
changes must never become unreachable.
"""

from datetime import date
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_payruns.models.hr_payslip_run import PB_OFFICER_PARAM


@tagged('post_install', '-at_install')
class TestOfficerTierSwitch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Run = cls.env['hr.payslip.run']
        cls.RunCls = type(cls.env['hr.payslip.run'])
        cls.d_from = date(2030, 3, 1)
        cls.d_to = date(2030, 3, 31)
        cls.employee = cls.env['hr.employee'].create({'name': 'Tier Switch Emp'})

        base_groups = ['base.group_user', 'om_hr_payroll.group_hr_payroll_manager',
                       'pb_hr_payroll_formula.group_formula_manager']

        def _user(login, groups):
            return cls.env['res.users'].create({
                'name': login, 'login': login,
                'group_ids': [(6, 0, [cls.env.ref(g).id
                                      for g in base_groups + list(groups)])],
            })

        cls.u_officer = _user('ts_officer',
                              ['pb_hr_payroll_base.group_payroll_base_officer'])
        cls.u_hr = _user('ts_hr',
                         ['pb_hr_payroll_base.group_payroll_base_manager'])

    # ------------------------------------------------------------- helpers
    def _set_officer_tier(self, on):
        self.env['ir.config_parameter'].sudo().set_param(
            PB_OFFICER_PARAM, '1' if on else '0')
        # The reader is not cached, but the fields computed from it are.
        self.env.invalidate_all()

    def _payrun(self, name='Tier Switch', with_slip=True):
        """A draft pay run. NEVER name a fixture ``run`` (C18.44)."""
        payrun = self.Run.create({
            'name': name, 'date_start': self.d_from, 'date_end': self.d_to,
        })
        if with_slip:
            self.env['hr.payslip'].create({
                'name': '%s slip' % name, 'employee_id': self.employee.id,
                'date_from': self.d_from, 'date_to': self.d_to,
                'payslip_run_id': payrun.id,
            })
        return payrun

    def _no_mail(self):
        return patch.object(self.RunCls,
                            '_notify_general_manager_for_batch_approval',
                            return_value=False)

    def _clear_parked_officer_runs(self):
        """Move any run the DATABASE already has at Officer review forward.

        A real tenant is not an empty board. The tests that assert the stage
        DISAPPEARS have to say "when nothing is sitting there", because keeping
        the column for a run that is sitting there is deliberate behaviour
        (test_07) — not something to assert away. Rolled back with the rest of
        the test.
        """
        parked = self.Run.sudo().search([('state', '=', 'level0')])
        if parked:
            parked.action_payslip_run_level0_done()
        return parked

    # ----------------------------------------------------------- 1. default
    def test_01_default_is_three_tiers(self):
        """A database that has never heard of the key keeps all three tiers."""
        self.env['ir.config_parameter'].sudo().set_param(PB_OFFICER_PARAM, False)
        self.assertTrue(self.Run._pb_officer_tier())
        self.assertEqual(self.Run._pb_chain_entry(), 'level0')
        self.assertEqual(list(self.Run._pb_board_states()),
                         ['draft', 'level0', 'level1', 'level2', 'done'])

    def test_02_only_explicit_off_switches_it_off(self):
        for value, expected in (('1', True), ('True', True), ('yes', True),
                                ('', True), ('0', False), ('false', False),
                                ('OFF', False), ('no', False)):
            self.env['ir.config_parameter'].sudo().set_param(
                PB_OFFICER_PARAM, value)
            self.assertEqual(self.Run._pb_officer_tier(), expected,
                             "parameter %r should read as %s" % (value, expected))

    # -------------------------------------------------------- 2. switched off
    def test_03_submit_lands_on_hr_review(self):
        self._set_officer_tier(False)
        payrun = self._payrun()
        payrun.with_user(self.u_officer).done_payslip_run()
        self.assertEqual(payrun.state, 'level1',
                         "with no Officer tier a submitted run goes straight "
                         "to HR review")
        self.assertFalse(payrun.slip_ids.filtered(lambda s: s.state == 'draft'),
                         "chain entry still confirms every payslip")

    def test_04_board_and_stepper_drop_the_stage(self):
        self._set_officer_tier(False)
        self.assertEqual(list(self.Run._pb_board_states()),
                         ['draft', 'level1', 'level2', 'done'])
        self.assertNotIn('level0', self.Run._pb_group_expand_state({}, []))
        payrun = self._payrun()
        self.assertNotIn('level0:', payrun.pb_stage_rail)
        self.assertIn('level1:', payrun.pb_stage_rail)
        self.assertFalse(payrun.pb_officer_tier)

    def test_05_send_back_from_hr_reaches_draft(self):
        """The stage before HR review is Draft when nothing sits between them.

        Without this the send-back would drop the run onto a stage the board no
        longer draws — payroll parked where nobody would look for it.
        """
        self._set_officer_tier(False)
        payrun = self._payrun()
        payrun.with_user(self.u_officer).done_payslip_run()
        self.assertEqual(payrun.state, 'level1')
        payrun.with_user(self.u_hr).with_context(
            pb_sendback_note='Wrong overtime').action_pb_send_back()
        self.assertEqual(payrun.state, 'draft')
        self.assertEqual(payrun.pb_sendback_from, 'level1')
        self.assertEqual(payrun.pb_sendback_note, 'Wrong overtime')

    def test_06_chain_still_completes(self):
        self._set_officer_tier(False)
        payrun = self._payrun()
        payrun.with_user(self.u_officer).done_payslip_run()
        with self._no_mail():
            payrun.with_user(self.u_hr).action_payslip_run_level1_done()
        self.assertEqual(payrun.state, 'level2',
                         "HR review still hands over to Finance approval")

    # ------------------------------------------- 3. runs already in the chain
    def test_07_a_parked_run_is_not_stranded(self):
        """Switching the tier off must not hide payroll that is already in it.

        The column is dropped from the stage LIST, so the board is asked to draw
        any stage a run actually occupies as well.
        """
        self._set_officer_tier(True)
        payrun = self._payrun(name='Parked')
        payrun.with_user(self.u_officer).done_payslip_run()
        self.assertEqual(payrun.state, 'level0')

        self._set_officer_tier(False)
        board = self.env['pb.payruns'].with_user(self.u_officer).get_board_data()
        keys = [column['key'] for column in board['columns']]
        self.assertIn('level0', keys,
                      "a run still sitting at Officer review keeps its column")
        self.assertFalse(board['officer_tier'])

        # …and it can still be moved on by the tier that owns it.
        payrun.with_user(self.u_officer).action_payslip_run_level0_done()
        self.assertEqual(payrun.state, 'level1')

    def test_08_board_without_parked_runs_drops_the_column(self):
        self._set_officer_tier(False)
        self._clear_parked_officer_runs()
        self._payrun(name='Plain draft')
        board = self.env['pb.payruns'].with_user(self.u_officer).get_board_data()
        keys = [column['key'] for column in board['columns']]
        self.assertEqual(keys, ['draft', 'level1', 'level2', 'done'])

    # ------------------------------------------------- 4. the other surfaces
    def test_09_approvals_cockpit_draws_the_same_chain(self):
        # pb_approval depends on this module, not the other way round, so the
        # cockpit may simply not be here.
        if 'pb.approval' not in self.env:
            self.skipTest('pb_approval is not installed on this database')
        self._set_officer_tier(False)
        self._clear_parked_officer_runs()
        payrun = self._payrun(name='Cockpit')
        payrun.with_user(self.u_officer).done_payslip_run()
        data = self.env['pb.approval'].with_user(self.u_hr).get_approvals()
        self.assertEqual([lane['key'] for lane in data['lanes']],
                         ['level1', 'level2'])
        self.assertFalse(data['officer_tier'])
        card = next(p for p in data['pending'] if p['id'] == payrun.id)
        self.assertEqual(card['steps'], 2,
                         "a two-tier chain must not draw a third dot")
        self.assertEqual(card['step'], 0, "HR review is now the FIRST tier")
        self.assertEqual(card['send_back_to'], 'draft')

    def test_10_the_setting_writes_the_parameter(self):
        settings = self.env['res.config.settings'].sudo().create({
            'pb_payrun_officer_review': False})
        settings.execute()
        self.assertFalse(self.Run._pb_officer_tier())
        settings = self.env['res.config.settings'].sudo().create({
            'pb_payrun_officer_review': True})
        settings.execute()
        self.assertTrue(self.Run._pb_officer_tier())
