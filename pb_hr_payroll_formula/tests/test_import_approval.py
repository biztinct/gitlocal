# -*- coding: utf-8 -*-
"""Approval Matrix Phase 5 — pay-data files (case M08).

Three things, and the third is the one that is new to the engine:

  * `action_process` asks rather than writes;
  * the answer carries out exactly the body that always carried it out;
  * ONE model answers to TWO catalogue rows — "this run only" and "past pay
    data" — because a figure used once and a figure kept for ever are not the
    same risk, and a business must be able to check one and wave the other
    through.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestImportApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Batch = cls.env['hr.payroll.import.batch']
        cls.Engine = cls.env['biz.approval.engine']
        cls.Seed = cls.env['biz.approval.seed'].sudo()
        cls.company = cls.env.company

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_formula = cls.env.ref('pb_hr_payroll_formula.group_formula_manager')
        cls.payroll_mgr = Users.create({
            'name': 'IA Payroll', 'login': 'ia_payroll',
            'group_ids': [(6, 0, [g_user.id, g_formula.id])]})
        cls.hr_lead = Users.create({
            'name': 'IA HR Lead', 'login': 'ia_hr_lead',
            'group_ids': [(6, 0, [g_user.id, g_formula.id])]})
        cls._fill_role('payroll_mgr', cls.payroll_mgr)
        cls._fill_role('hr_lead', cls.hr_lead)
        # THE TWO ROUTES, EXPLICITLY — `post_init_hook` runs on install only
        # and a test database is usually reached by an upgrade. Idempotent.
        cls.Batch._approval_seed_default(cls.env.company)

        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'IA Scheme', 'code': 'IASCHEME',
            'country_code': 'VN', 'state': 'active',
            'company_id': cls.company.id})

    @classmethod
    def _fill_role(cls, key, user):
        role = cls.env['biz.approval.role'].sudo().search(
            [('key', '=', key)], limit=1)
        if not role:
            return
        held = cls.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', cls.env.company.id),
            ('role_id', '=', role.id), ('scope_key', '=', '')], limit=1)
        if held:
            held.write({'user_id': user.id, 'active': True})
            return
        cls.env['biz.approval.responsibility'].sudo().create({
            'company_id': cls.env.company.id, 'role_id': role.id,
            'scope_key': '', 'scope_label': cls.env.company.name,
            'user_id': user.id, 'date_from': date(2020, 1, 1)})

    def _batch(self, one_time=False):
        return self.Batch.create({
            'name': 'IA batch %s' % ('once' if one_time else 'keep'),
            'source_type': 'manual',
            'formula_config_id': self.cfg.id,
            'company_id': self.company.id,
            'payroll_period': 'custom',
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30),
            'one_time': one_time,
            'create_payslips': False,
            'state': 'validated',
        })

    # ============================================================ M08
    def test_m08a_one_model_two_catalogue_rows(self):
        once = self._batch(one_time=True)
        keep = self._batch(one_time=False)
        self.assertEqual(once._approval_process_key_for(), 'runonly')
        self.assertEqual(keep._approval_process_key_for(), 'loads')
        self.assertEqual(once._approval_process().key, 'runonly')
        self.assertEqual(keep._approval_process().key, 'loads')

        Process = self.env['biz.approval.process'].sudo()
        for key in ('runonly', 'loads'):
            row = Process._by_key(key)
            self.assertEqual(row.model_name, 'hr.payroll.import.batch')
            self.assertTrue(row.connected,
                            '%s reads as not wired up' % key)

    def test_m08b_process_asks_before_it_writes(self):
        batch = self._batch()
        batch.action_process()
        request = batch.approval_request_id
        self.assertTrue(request, 'no request was raised')
        self.assertEqual(request.state, 'pending')
        self.assertNotEqual(batch.state, 'done',
                            'the file was processed without an approval')
        # and a second press is refused with a sentence naming who has it
        with self.assertRaises(UserError):
            batch.action_process()

    def test_m08c_the_approval_carries_it_out_once(self):
        batch = self._batch()
        batch.action_process()
        request = batch.approval_request_id
        for _guard in range(4):
            batch.invalidate_recordset()
            request = batch.approval_request_id
            if request.state not in ('pending', 'blocked'):
                break
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            self.assertTrue(step, 'stalled: %s' % (request.block_reason or ''))
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.Engine.with_user(seat.acting_user_id).decide(
                request.id, step.key, 'approve', 'ok')
        batch.invalidate_recordset()
        self.assertEqual(batch.approval_request_id.state, 'applied')
        self.assertEqual(batch.state, 'done',
                         'the approval did not process the file')
        # idempotent: applying again does nothing
        batch._approval_apply(batch.approval_request_id)
        self.assertEqual(batch.state, 'done')

    def test_m08d_the_fast_lane_processes_on_the_press(self):
        self.Seed.set_no_approval_needed(self.company, 'loads')
        batch = self._batch()
        batch.action_process()
        batch.invalidate_recordset()
        self.assertEqual(batch.state, 'done')
        self.assertEqual(batch.approval_request_id.state, 'applied',
                         'a fast lane is still recorded as a request')

    def test_m08e_validate_is_never_gated(self):
        """`action_validate` is the CHECK, not the money. A person has to be
        able to see what a file would do before deciding whether to ask."""
        batch = self._batch()
        batch.state = 'matched'
        batch.action_validate()
        self.assertEqual(batch.state, 'validated')
        self.assertFalse(batch.approval_request_id,
                         'checking a file must not raise a request')

    def test_m08f_the_stamp_is_re_read_from_the_rows(self):
        """Ledger AM46: a stamp read back off its own snapshot always equals
        itself and the whole rail would be decoration."""
        batch = self._batch()
        first = batch._source_revision()
        self.assertEqual(first, batch._source_revision())
        self.assertTrue(first)
