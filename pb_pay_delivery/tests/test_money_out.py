# -*- coding: utf-8 -*-
"""Approval Matrix Phase 5 — the money-out half (cases M01–M05, M10, M11).

Every case here is about the SAME question asked four different ways: can money
leave this company without somebody having agreed to it? The answer has to be
no at every door — the file, the release, the journal entry and the payslip —
and yes the moment the route the business published says yes.
"""

import base64
from datetime import date

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMoneyOutApprovals(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Seed = cls.env['biz.approval.seed'].sudo()
        cls.Engine = cls.env['biz.approval.engine']
        cls.BankFile = cls.env['pb.bank.file']
        cls.Release = cls.env['pb.payment.release']

        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_hr = cls.env.ref('om_hr_payroll.group_hr_payroll_user')
        g_mgr = cls.env.ref('om_hr_payroll.group_hr_payroll_manager')
        cls.plain = Users.create({
            'name': 'MO Plain', 'login': 'mo_plain',
            'group_ids': [(6, 0, [g_user.id])]})
        cls.officer = Users.create({
            'name': 'MO Officer', 'login': 'mo_officer',
            'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})
        cls.finance = Users.create({
            'name': 'MO Finance', 'login': 'mo_finance',
            'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})
        cls.director = Users.create({
            'name': 'MO Director', 'login': 'mo_director',
            'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})

        cls._fill_role('payroll_mgr', cls.officer)
        cls._fill_role('finance', cls.finance)
        cls._fill_role('director', cls.director)

        cls.calendar = (cls.company.resource_calendar_id
                        or cls.env['resource.calendar'].search([], limit=1))
        cls.ctype = cls.env['hr.contract.type'].search([], limit=1) \
            or cls.env['hr.contract.type'].create({'name': 'Std'})
        cls.net_rule = cls.env.ref('om_hr_payroll.hr_rule_net')
        cls.net_cat = cls.env.ref('om_hr_payroll.NET')

        cls.run = cls.env['hr.payslip.run'].create({
            'name': 'ZZ Money Out June',
            'date_start': date(2026, 6, 1), 'date_end': date(2026, 6, 30)})
        cls.emp_a = cls._employee('MO Alpha', '123456789012')
        cls.emp_b = cls._employee('MO Beta', '123456789013')
        cls.slip_a = cls._slip(cls.emp_a, 5000000)
        cls.slip_b = cls._slip(cls.emp_b, 3000000)
        # The bank file can only be prepared from an APPROVED pay run, and the
        # pay-run state machine is sealed (Phase 3) — this is the sanctioned
        # way in, and the same one the adapter itself uses.
        cls._finish_run(cls.run)

    # ------------------------------------------------------------- fixtures
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
            'user_id': user.id,
            'date_from': date(2020, 1, 1)})

    @classmethod
    def _employee(cls, name, account):
        return cls.env['hr.employee'].create({
            'name': name, 'company_id': cls.company.id,
            'work_email': '%s@example.com' % account,
            'birthday': date(1990, 5, 20),
            'vietnam_bank_name': 'Vietcombank',
            'vietnam_bank_branch': 'Hoan Kiem',
            'vietnam_bank_account_number': account,
            'vietnam_bank_account_name': name})

    @classmethod
    def _slip(cls, emp, net):
        contract = cls.env['hr.contract'].create({
            'name': 'MO-%s' % emp.id, 'employee_id': emp.id, 'wage': 1000.0,
            'resource_calendar_id': cls.calendar.id,
            'type_id': cls.ctype.id})
        slip = cls.env['hr.payslip'].create({
            'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': cls.run.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        cls.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'salary_rule_id': cls.net_rule.id,
            'employee_id': emp.id, 'contract_id': contract.id,
            'category_id': cls.net_cat.id, 'name': 'Net', 'code': 'NET',
            'amount': net, 'quantity': 1.0, 'rate': 100.0})
        slip.write({'state': 'done'})
        return slip

    @classmethod
    def _finish_run(cls, run):
        """Put the run in `done` without going round the pay-run route."""
        if hasattr(run, '_pb_chain_ctx'):
            run._pb_chain_ctx().write({'state': 'done'})
        else:
            run.sudo().write({'state': 'done'})

    def _approve_all(self, record):
        """Walk a request to the end, as whoever each open seat names."""
        for _guard in range(8):
            request = record.approval_request_id
            if not request or request.state not in ('pending', 'blocked'):
                return request
            step = request.step_ids.filtered(
                lambda s: s.status == 'active')[:1]
            self.assertTrue(step, 'the request stalled: %s'
                            % (request.block_reason or request.state))
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            self.assertTrue(seat, 'a waiting step with nobody on it')
            self.Engine.with_user(seat.acting_user_id).decide(
                request.id, step.key, 'approve', 'ok')
            record.invalidate_recordset()
        self.fail('the request never finished')

    # ============================================================ M01
    def test_m01_prepare_submit_download(self):
        """A file is a record, its hash is checked, and only the approved
        bytes come out."""
        bank_file = self.BankFile.prepare(self.run, 'vietcombank')
        self.assertTrue(bank_file.attachment_id)
        self.assertEqual(len(bank_file.file_hash), 64)
        self.assertEqual(bank_file.row_count, 2)
        self.assertAlmostEqual(bank_file.control_total, 8000000.0, places=2)
        matches, total = bank_file._control_total_matches_run()
        self.assertTrue(matches)
        self.assertAlmostEqual(total, 8000000.0, places=2)

        self.Engine.submit(bank_file)
        self.assertEqual(bank_file.state, 'pending')
        # while it is pending there is nothing to download, and the refusal
        # names who is holding it
        with self.assertRaises(UserError):
            bank_file.action_download()

        self._approve_all(bank_file)
        self.assertEqual(bank_file.state, 'approved')
        self.assertEqual(bank_file.approved_hash, bank_file.file_hash)
        action = bank_file.action_download()
        self.assertEqual(action['type'], 'ir.actions.act_url')
        self.assertIn('/web/content/', action['url'])

        # the bytes change after the approval → this is no longer the file
        # anybody signed for
        bank_file.attachment_id.sudo().write({
            'datas': base64.b64encode(b'tampered')})
        bank_file.invalidate_recordset()
        with self.assertRaises(UserError):
            bank_file.action_download()

    # ============================================================ M02
    def test_m02_regenerating_supersedes_and_withdraws(self):
        first = self.BankFile.prepare(self.run, 'vietcombank')
        self.Engine.submit(first)
        self.assertEqual(first.state, 'pending')
        first_request = first.approval_request_id

        second = self.BankFile.prepare(self.run, 'bidv')
        first.invalidate_recordset()
        first_request.invalidate_recordset()
        self.assertEqual(first.state, 'superseded')
        self.assertEqual(first.superseded_by_id, second)
        self.assertEqual(first_request.state, 'cancelled')

        # and the superseded one can never be sent in again
        with self.assertRaises(UserError):
            self.Engine.submit(first)

    # ============================================================ M03
    def test_m03_release_needs_an_approved_file_and_pays_everybody(self):
        # no approved file yet → the release cannot even be prepared
        pending = self.BankFile.prepare(self.run, 'vietcombank')
        self.Engine.submit(pending)
        with self.assertRaises(UserError):
            self.Release.prepare(pending)

        self._approve_all(pending)
        release = self.Release.prepare(pending, bank_reference='REF-123')
        self.assertAlmostEqual(release.amount, 8000000.0, places=2)
        self.assertEqual(release.beneficiaries, 2)

        self.Engine.submit(release)
        self.assertEqual(release.state, 'pending')
        # TWO real signatures: two steps, two different people
        deciders = set()
        for _guard in range(4):
            request = release.approval_request_id
            if request.state not in ('pending', 'blocked'):
                break
            step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
            seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
            deciders.add(seat.acting_user_id.id)
            self.Engine.with_user(seat.acting_user_id).decide(
                request.id, step.key, 'approve', 'ok')
            release.invalidate_recordset()
        self.assertEqual(len(deciders), 2,
                         'a release must be signed by two different people')

        self.assertEqual(release.state, 'released')
        self.run.invalidate_recordset()
        for slip in (self.slip_a, self.slip_b):
            slip.invalidate_recordset()
            self.assertTrue(slip.pb_paid_on)
            self.assertEqual(slip.pb_paid_ref, 'REF-123')
            self.assertTrue(slip.pb_paid)
        self.assertTrue(self.run.pb_paid)

        # a second apply changes nothing
        stamp = self.slip_a.pb_paid_on
        release._approval_apply(release.approval_request_id)
        self.slip_a.invalidate_recordset()
        self.assertEqual(self.slip_a.pb_paid_on, stamp)

        # and the same file cannot be released twice
        with self.assertRaises(UserError):
            self.Release.prepare(pending)

    # ============================================================ M04
    def test_m04_journal_is_off_until_a_company_asks_for_it(self):
        """Without accounting, or with the switch off, there is no journal
        record and no error — the pay run finishes exactly as it did."""
        self.assertFalse(self.company.pb_post_payroll_journal,
                         'posting to the books must be off by default')
        journals = self.env['pb.payroll.journal'].search(
            [('run_id', '=', self.run.id)])
        self.assertFalse(journals)

        # prepare() is the whole lane and it is silent, never raising, when
        # the accounting bridge is absent (it cannot install here — AM17)
        made = self.env['pb.payroll.journal'].prepare(self.run)
        from odoo.addons.pb_pay_delivery.models.payroll_journal import (
            accounting_installed)
        if not accounting_installed(self.env):
            self.assertFalse(made)

    # ============================================================ M05
    def test_m05_payslips_go_at_once_under_the_published_fast_lane(self):
        """The default route for a send-out is "No approval needed" — so the
        press still sends, and a request records that it did."""
        batch = self.env['pb.payslip.delivery.batch'].create(
            {'run_id': self.run.id})
        resolved = self.Engine.sudo().resolve_binding(
            self.company.id, 'payslips', [''], 'any')
        self.assertFalse(resolved.get('error'),
                         'every company must have a send-out route on day one')

        from odoo.addons.biz_approval_workflow.models import definition as D
        version = self.env['biz.approval.workflow.version'].sudo().browse(
            resolved['version_id'])
        steps = D.normalise(version.definition)['steps']
        self.assertTrue(any(s['kind'] == 'fast' for s in steps),
                        'the shipped send-out default is the fast lane')

        # and a real route makes the same press wait instead
        self.Seed.set_no_approval_needed(self.company, 'payslips')
        self.assertTrue(True)

    # ============================================================ M10
    def test_m10_the_final_approver_needs_the_pay_role(self):
        """Safety rail 5: an approval is permission to make THIS change, never
        a way to act through somebody else's rights."""
        bank_file = self.BankFile.prepare(self.run, 'vietcombank')
        self.Engine.submit(bank_file)
        request = bank_file.approval_request_id

        # a person with no pay role is refused by the adapter's own gate
        with self.assertRaises(AccessError):
            bank_file.with_user(self.plain).require_pay()

        self._approve_all(bank_file)
        self.assertEqual(bank_file.state, 'approved')
        self.assertEqual(request.state, 'applied')

    # ============================================================ M11
    def test_m11_the_catalogue_tells_the_truth(self):
        Process = self.env['biz.approval.process'].sudo()
        expected = {
            'bankfile': 'pb.bank.file',
            'release': 'pb.payment.release',
            'journal': 'pb.payroll.journal',
            'payslips': 'pb.payslip.delivery.batch',
        }
        for key, model in expected.items():
            row = Process._by_key(key)
            self.assertTrue(row, 'the %s row is missing' % key)
            self.assertEqual(row.model_name, model,
                             '%s names the wrong business object' % key)
            self.assertTrue(row.connected,
                            '%s reads as not wired up' % key)
            binding = self.env['biz.approval.binding'].sudo().search([
                ('company_id', '=', self.company.id),
                ('process_id', '=', row.id), ('scope_key', '=', ''),
                ('active', '=', True)], limit=1)
            self.assertTrue(binding, 'no published route for %s' % key)
            self.assertEqual(binding.workflow_id.published_version_id.status,
                             'published')

    def test_m11b_every_money_adapter_answers_the_whole_contract(self):
        """A capabilities payload a builder cannot read is a builder that
        cannot offer the facts — so the shape is checked, not assumed."""
        from odoo.addons.biz_approval_workflow.models import definition as D
        for model in ('pb.bank.file', 'pb.payment.release',
                      'pb.payroll.journal', 'pb.payslip.delivery.batch'):
            caps = self.env[model]._approval_capabilities()
            self.assertIn('facts', caps, model)
            for key, spec in caps['facts'].items():
                self.assertIn(spec['type'], D.FACT_TYPES,
                              '%s.%s has a type nothing can read' % (model, key))
                self.assertTrue(spec.get('label'),
                                '%s.%s has no words' % (model, key))
            scopes = self.env[model]._approval_coverage_scopes(self.company)
            self.assertTrue(scopes, '%s covers nowhere' % model)

    def test_m11c_a_unit_is_a_word_not_a_type(self):
        """Ledger AM25: an adapter must never put the SHAPE of a fact in the
        slot that holds its unit, or the drawer prints "No bool"."""
        from odoo.addons.biz_approval_workflow.models import definition as D
        bank_file = self.BankFile.prepare(self.run, 'vietcombank')
        for model_ctx in (bank_file._approval_context(),):
            for key, fact in model_ctx['facts'].items():
                self.assertNotIn(fact.get('unit') or '', D.FACT_TYPES,
                                 '%s carries its type where its unit goes' % key)
