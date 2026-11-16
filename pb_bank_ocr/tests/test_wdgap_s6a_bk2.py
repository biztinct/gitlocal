# -*- coding: utf-8 -*-
"""WDGAP S6-A follow-up BK2 (owner ruling 2026-11-16 evening): bank details
arriving by an import wait for one second person.

M-numbers match the phase report. Both import routes: a pay data file
(`hr.payroll.import.batch.action_process`) and the old Vietnam employee
import (`vietnam.employee.import.wizard`).
"""
import json

from lxml import etree

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_bank_ocr.models.pb_bank_import_hold import hold_scope


@tagged('post_install', '-at_install')
class TestS6aBk2(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.has_records = 'pb.records.apply' in cls.env
        cls.company = cls.env.company
        cls.env['payroll.ai.config'].search([]).write({'is_active': False})
        # The LOAD itself is not what these cases are about (ledger PRE-1): a
        # pay data file is processed at once, as "No approval needed" says.
        cls.env['biz.approval.seed'].sudo().set_no_approval_needed(cls.company, 'loads')
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': cls.company.id,
                  'company_ids': [(6, 0, [cls.company.id])]}
        cls.importer = Users.create(dict(common, name='BK2 Importer', login='bk2_imp',
                                         group_ids=[(6, 0, [
                                             cls.env.ref('base.group_user').id,
                                             cls.env.ref('om_hr_payroll.group_hr_payroll_manager').id])]))
        if cls.has_records:
            from odoo.addons.pb_records.tests.bank_second import ensure_second_person
            cls.second = ensure_second_person(cls.env, cls.company)
        cls.cfg = cls.env['hr.formula.config'].create({
            'name': 'BK2 Scheme', 'code': 'BK2SCHEME', 'country_code': 'VN',
            'company_id': cls.company.id})

        def rule(name, code, role):
            return cls.env['hr.formula.rule'].create({
                'config_id': cls.cfg.id, 'name': name, 'code': code,
                'column_type': 'input', 'column_role': role,
                'appears_on_payslip': False})
        Mapping = cls.env['hr.payslip.import.mapping']
        for name, code, role in (('Account Number', 'BKACCNO', 'acc_number'),
                                 ('Bank Name', 'BKBANK', 'bank_name'),
                                 ('Account Holder Name', 'BKHOLDER', 'acc_holder_name')):
            Mapping.create({'salary_structure_id': cls.cfg.id,
                            'component_id': rule(name, code, 'bank').id,
                            'destination_type': 'bank_account', 'bank_role': role})
        Emp = cls.env['hr.employee']
        cls.known = Emp.create({
            'name': 'BK2 Known', 'company_id': cls.company.id,
            'identification_id': 'BK2-KNOWN',
            'vietnam_bank_name': 'BIDV', 'vietnam_bank_branch': 'Hoan Kiem',
            'vietnam_bank_account_number': '000011112222',
            'vietnam_bank_account_name': 'BK2 KNOWN'})
        cls.fresh = Emp.create({'name': 'BK2 Fresh', 'company_id': cls.company.id,
                                'identification_id': 'BK2-FRESH'})

    # ------------------------------------------------------------ helpers
    def _batch(self, rows, user=None):
        Batch = self.env['hr.payroll.import.batch']
        if user:
            # made BY the importer (sudo keeps the user: create_uid is theirs)
            Batch = Batch.with_user(user).with_context(
                allowed_company_ids=[self.company.id]).sudo()
        batch = Batch.create({
            'name': 'BK2 file', 'source_type': 'excel',
            'formula_config_id': self.cfg.id, 'payroll_period': 'custom',
            'date_from': '2026-10-01', 'date_to': '2026-10-31',
            'create_payslips': False,
        }).sudo()
        for i, (emp, row) in enumerate(rows, start=1):
            self.env['hr.payroll.import.line'].sudo().create({
                'batch_id': batch.id, 'sequence': i,
                'raw_data_json': json.dumps(row),
                'employee_code': emp.identification_id,
                'employee_name': emp.name, 'employee_id': emp.id,
                'state': 'validated'})
        batch.sudo().state = 'validated'
        return batch

    def _process(self, batch):
        batch.sudo().action_process()
        self.env.invalidate_all()

    def _row(self, number, bank='Vietcombank', holder='BK2 HOLDER'):
        return {'Account Number': number, 'Bank Name': bank,
                'Account Holder Name': holder}

    def _waiting(self, emp):
        return self.env['pb.bank.change.request'].sudo().search(
            [('employee_id', '=', emp.id), ('pb_origin', '=', 'import')])

    def _stores(self, emp):
        self.env.invalidate_all()
        emp = emp.sudo()
        return (emp.vietnam_bank_account_number or False,
                tuple(sorted(emp.bank_account_ids.mapped('acc_number'))))

    # M1 — a new person with bank details: held, neither store written
    def test_m1_new_person_bank_details_wait(self):
        before = self._stores(self.fresh)
        batch = self._batch([(self.fresh, self._row('123456789012'))])
        self._process(batch)
        self.assertEqual(self._stores(self.fresh), before)
        req = self._waiting(self.fresh)
        self.assertEqual(len(req), 1)
        self.assertEqual(req.x_account_number, '123456789012')
        self.assertEqual(req.pb_import_key, 'hr.payroll.import.batch,%s' % batch.id)
        self.assertIn('waiting for approval', batch.processing_log or '')
        self.assertIn('waiting for approval', batch.pb_bank_waiting_note)
        if self.has_records:
            self.assertEqual(req.state, 'hr_review')
            self.assertEqual(req.approval_request_id.process_id.key, 'records_bank')

    # M2 — changed details: held; the old ones stay in both stores
    def test_m2_changed_details_wait(self):
        before = self._stores(self.known)
        self._process(self._batch([(self.known, self._row('999988887777'))]))
        self.assertEqual(self._stores(self.known), before)
        self.assertEqual(len(self._waiting(self.known)), 1)

    # M3 — identical details create nothing (and write what they always did)
    def test_m3_identical_details_create_nothing(self):
        stamp = self.known.sudo().write_date
        n_accounts = self.env['res.partner.bank'].sudo().search_count([])
        self._process(self._batch([(self.known, self._row(
            '000011112222', bank='BIDV', holder='BK2 KNOWN'))]))
        self.assertFalse(self._waiting(self.known))
        self.assertEqual(self.known.sudo().vietnam_bank_account_number, '000011112222')
        self.assertFalse(self.env['pb.employee.bank.history'].search(
            [('employee_id', '=', self.known.id)]))
        # exactly today's behaviour: the import may add the matching account
        # to the accounts store (it always did), never a held change
        self.assertLessEqual(self.env['res.partner.bank'].sudo().search_count([]),
                             n_accounts + 1)
        self.assertTrue(stamp)

    # M4 — re-importing the same file never makes a second waiting change
    def test_m4_reimport_does_not_duplicate(self):
        self._process(self._batch([(self.fresh, self._row('123456789012'))]))
        self._process(self._batch([(self.fresh, self._row('123456789012'))]))
        self.assertEqual(len(self._waiting(self.fresh)), 1)

    # M5 — approver is never the importer; approve-all; both stores on approval
    def test_m5_approve_all_never_the_importer(self):
        if not self.has_records:
            self.skipTest('pb_records is not installed')
        batch = self._batch([(self.fresh, self._row('123456789012')),
                             (self.known, self._row('999988887777'))],
                            user=self.importer)
        self._process(batch)
        reqs = self.env['pb.bank.change.request'].sudo().search(
            [('pb_import_key', '=', 'hr.payroll.import.batch,%s' % batch.id)])
        self.assertEqual(len(reqs), 2)
        self.assertTrue(all(r.proposed_by_id == self.importer for r in reqs))
        for r in reqs:
            seats = r.approval_request_id.step_ids.seat_ids
            self.assertNotIn(self.importer, seats.acting_user_id)
        Req = self.env['pb.bank.change.request']
        mine = Req.with_user(self.importer).with_context(
            allowed_company_ids=[self.company.id]).pb_approve_import(reqs[0].pb_import_key)
        self.assertEqual(mine['approved'], 0)
        self.assertEqual(mine['yours'], 2)
        approver = reqs[0].approval_request_id.step_ids.filtered(
            lambda s: s.status == 'active').seat_ids.filtered(
            lambda s: s.status == 'open')[:1].acting_user_id
        groups = Req.with_user(approver)._pb_import_groups()
        self.assertEqual(groups[0]['count'], 2)
        out = Req.with_user(approver).with_context(
            allowed_company_ids=[self.company.id]).pb_approve_import(reqs[0].pb_import_key)
        self.assertEqual(out['approved'], 2)
        self.assertEqual(self._stores(self.fresh), ('123456789012', ('123456789012',)))
        self.assertEqual(self.known.sudo().vietnam_bank_account_number, '999988887777')
        self.assertEqual(self.known.sudo().bank_account_ids[:1].acc_number, '999988887777')

    # M6 — send back one row: the old details stay
    def test_m6_send_back_keeps_old_details(self):
        if not self.has_records:
            self.skipTest('pb_records is not installed')
        before = self._stores(self.known)
        self._process(self._batch([(self.known, self._row('999988887777'))]))
        req = self._waiting(self.known)
        request = req.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')[:1]
        seat = step.seat_ids.filtered(lambda s: s.status == 'open')[:1]
        self.env['biz.approval.engine'].with_user(seat.acting_user_id).with_context(
            allowed_company_ids=[self.company.id]).decide(
                request.id, step.key, 'return', 'Not this account')
        self.env.invalidate_all()
        self.assertEqual(req.state, 'draft')
        self.assertEqual(self._stores(self.known), before)

    # M7 — a column mapped straight onto the bank file's fields is held too,
    # while every other field in the same write is written
    def test_m7_direct_field_write_is_held_rest_written(self):
        with hold_scope(self.env, 'bk2-test', 'BK2 test', self.importer):
            self.known.sudo().write({'vietnam_bank_account_number': '555566667777',
                                     'job_title': 'BK2 Planner'})
        self.env.invalidate_all()
        self.assertEqual(self.known.sudo().job_title, 'BK2 Planner')
        self.assertEqual(self.known.sudo().vietnam_bank_account_number, '000011112222')
        self.assertEqual(len(self._waiting(self.known)), 1)
        # outside an import, nothing is held (today's behaviour)
        self.known.sudo().write({'vietnam_bank_branch': 'Ba Dinh'})
        self.assertEqual(self.known.sudo().vietnam_bank_branch, 'Ba Dinh')

    # M8 — golden: an import with no bank column writes what it always wrote
    def test_m8_golden_no_bank_change(self):
        n_req = self.env['pb.bank.change.request'].sudo().search_count([])
        n_hist = self.env['pb.employee.bank.history'].sudo().search_count([])
        before = (self._stores(self.known), self._stores(self.fresh))
        self._process(self._batch([(self.known, {'Something Else': '1'}),
                                   (self.fresh, {'Something Else': '2'})]))
        self.assertEqual((self._stores(self.known), self._stores(self.fresh)), before)
        self.assertEqual(self.env['pb.bank.change.request'].sudo().search_count([]), n_req)
        self.assertEqual(self.env['pb.employee.bank.history'].sudo().search_count([]), n_hist)

    # M9 — the old Vietnam employee import: new person, re-import, unchanged
    def test_m9_vietnam_employee_import(self):
        if 'vietnam.employee.import.wizard' not in self.env:
            self.skipTest('the Vietnam employee import is not installed')
        Wizard = self.env['vietnam.employee.import.wizard'].with_user(self.importer).with_context(
            allowed_company_ids=[self.company.id])

        def run():
            wiz = Wizard.sudo().create({'zoho_api_url': 'https://example.invalid',
                                 'zoho_access_token': 'not-a-real-token',
                                 'import_mode': 'create_and_update',
                                 'import_contracts': False})
            wiz.sudo().action_import_employees()
            return wiz
        wiz = run()
        emp = self.env['hr.employee'].sudo().search([('vietnam_employee_id', '=', 'VN001')],
                                                    limit=1)
        self.assertTrue(emp, wiz.import_summary)
        self.assertFalse(emp.vietnam_bank_account_number)       # held, not written
        req = self._waiting(emp)
        self.assertEqual(len(req), 1)
        self.assertEqual(req.proposed_by_id, self.importer)
        self.assertIn('waiting for approval', wiz.import_summary or '')
        run()                                                    # re-import
        self.assertEqual(len(self._waiting(emp)), 1)
        # once the details are on record, the same import changes nothing
        req.sudo()._apply_to_master()
        self.env.invalidate_all()
        n = self.env['pb.bank.change.request'].sudo().search_count([])
        run()
        self.assertEqual(self.env['pb.bank.change.request'].sudo().search_count([]), n)

    # M10 — the standard employee form's "Bank accounts" field is read-only
    def test_m10_employee_form_bank_accounts_read_only(self):
        arch = self.env['hr.employee'].get_view(
            self.env.ref('hr.view_employee_form').id, 'form')['arch']
        doc = etree.fromstring(arch)
        nodes = doc.xpath("//field[@name='bank_account_ids']")
        self.assertTrue(nodes)
        for node in nodes:
            self.assertIn(node.get('readonly'), ('1', 'True', 'true'))
        self.assertIn('pb-bank-ro-note', arch)
