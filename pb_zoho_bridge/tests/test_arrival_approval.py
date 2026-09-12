# -*- coding: utf-8 -*-
"""Approval Matrix Phase 5 — arrivals from a connected system (case M09).

The rules still decide; the three decisions that WRITE wait for a person. And a
row whose person has moved since it arrived is skipped with a note rather than
overwritten, because HR's own answer wins.
"""

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestArrivalApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Pipeline = cls.env['pb.zoho.pipeline']
        cls.Batch = cls.env['pb.zoho.arrival.batch']
        cls.Engine = cls.env['biz.approval.engine']
        cls.Seed = cls.env['biz.approval.seed'].sudo()
        cls.Inbox = cls.env['pb.zoho.inbox']
        cls.company = cls.env.company

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_hr = cls.env.ref('hr.group_hr_manager')
        cls.hr_lead = Users.create({
            'name': 'AA HR Lead', 'login': 'aa_hr_lead',
            'group_ids': [(6, 0, [g_user.id, g_hr.id])]})
        cls._fill_role('hr_lead', cls.hr_lead)
        # THE ROUTE, EXPLICITLY — `post_init_hook` runs on install only and a
        # test database is usually reached by an upgrade. Idempotent, and it
        # is also what repoints the catalogue row at `pb.zoho.arrival.batch`
        # (the data file is noupdate — ledger AM45).
        cls.Batch._approval_seed_default(cls.env.company)

        cls.employee = cls.env['hr.employee'].create({
            'name': 'AA Person', 'company_id': cls.company.id,
            'work_email': 'aa.person@example.com',
            'job_title': 'Before'})

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

    def _rule(self, action, trigger='updated'):
        return self.env['pb.zoho.event.rule'].sudo().create({
            'company_id': self.company.id,
            'trigger': trigger,
            'action': action,
            'sequence': 1,
        })

    def _record(self, **extra):
        return dict({
            'Employee ID': 'AA-001',
            'Email address': 'aa.person@example.com',
            'First Name': 'AA',
            'Last Name': 'Person',
            # Deliberately NO status word: `_read_trigger` reads a status it
            # has not seen before as a STATUS CHANGE, and these cases are
            # about a plain update.
        }, **extra)

    def _latest_batch(self):
        return self.Batch.sudo().search([], order='id desc', limit=1)

    # ============================================================ M09
    def test_m09a_an_update_is_written_down_not_carried_out(self):
        self._rule('update')
        before = self.employee.job_title
        summary = self.Pipeline.sudo().process_records(
            [self._record(Designation='After')], 'webhook',
            company_id=self.company.id)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, before,
                         'the arrival was applied without anybody agreeing')
        self.assertTrue(summary.get('batch_id'), 'no batch was raised')

        batch = self.Batch.sudo().browse(summary['batch_id'])
        self.assertEqual(batch.state, 'pending')
        self.assertEqual(batch.row_count, 1)
        self.assertEqual(batch.updates, 1)
        self.assertTrue(batch.approval_request_id)
        self.assertNotEqual(batch.approval_request_id.submitter_uid.id,
                            self.env.ref('base.public_user').id,
                            'a webhook must not put a public user in the trail')

    def test_m09b_approving_carries_the_rows_out(self):
        self._rule('update')
        summary = self.Pipeline.sudo().process_records(
            [self._record(Designation='Approved title')], 'webhook',
            company_id=self.company.id)
        batch = self.Batch.sudo().browse(summary['batch_id'])
        request = batch.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        self.assertTrue(step, 'stalled: %s' % (request.block_reason or ''))
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.Engine.with_user(seat.acting_user_id).decide(
            request.id, step.key, 'approve', 'ok')
        batch.invalidate_recordset()
        self.assertEqual(batch.state, 'applied')
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'Approved title')

    def test_m09c_a_record_that_moved_in_between_is_skipped_with_a_note(self):
        self._rule('update')
        summary = self.Pipeline.sudo().process_records(
            [self._record(Designation='From the feed')], 'webhook',
            company_id=self.company.id)
        batch = self.Batch.sudo().browse(summary['batch_id'])

        # HR gets there first
        self.employee.sudo().write({'job_title': 'HR knows better'})
        self.env.flush_all()

        applied = self.Pipeline.sudo()._apply_rows(batch)
        self.assertEqual(applied['skipped'], 1)
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'HR knows better',
                         "the connected system overwrote HR's own answer")
        note = self.Inbox.sudo().search([], order='id desc', limit=1)
        self.assertEqual(note.state, 'review')

    def test_m09d_ignore_and_review_still_happen_at_once(self):
        """Neither changes a record, and a row put aside for somebody to look
        at is already waiting for a person."""
        self._rule('ignore')
        before = self.Inbox.sudo().search_count([])
        summary = self.Pipeline.sudo().process_records(
            [self._record()], 'webhook', company_id=self.company.id)
        self.assertEqual(summary['ignored'], 1)
        self.assertGreater(self.Inbox.sudo().search_count([]), before)
        self.assertFalse(summary.get('batch_id'),
                         'an ignored row must not raise a request')

    def test_m09e_the_fast_lane_applies_on_arrival(self):
        self.Seed.set_no_approval_needed(self.company, 'arrivals')
        self._rule('update')
        summary = self.Pipeline.sudo().process_records(
            [self._record(Designation='Straight through')], 'webhook',
            company_id=self.company.id)
        batch = self.Batch.sudo().browse(summary['batch_id'])
        self.assertEqual(batch.state, 'applied')
        self.employee.invalidate_recordset()
        self.assertEqual(self.employee.job_title, 'Straight through')

    def test_m09f_the_catalogue_row_points_at_the_batch(self):
        row = self.env['biz.approval.process'].sudo()._by_key('arrivals')
        self.assertEqual(row.model_name, 'pb.zoho.arrival.batch')
        self.assertTrue(row.connected)
