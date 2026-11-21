# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for Phase D — AI Bank Account Validation (§6 cases 1–10)."""

import base64
import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_payroll_ai_insights.ai_providers.base_provider import BaseAIProvider
from odoo.addons.pb_bank_ocr.models import vn_bank_dictionary as vnd

_FAKE_PDF = base64.b64encode(b'%PDF-1.4 fake bank letter').decode()


class _FakeProvider(BaseAIProvider):
    def __init__(self, raw='', vision=True, pdf=True, raise_exc=False):
        super().__init__({})
        self._raw, self._vision, self._pdf, self._raise = raw, vision, pdf, raise_exc

    def supports_vision(self):
        return self._vision

    def accepts_pdf(self):
        return self._pdf

    def is_available(self):
        return True

    def generate_text(self, *a, **k):
        return self._raw

    def generate_vision(self, prompt, images, max_tokens=1500, **k):
        if self._raise:
            raise RuntimeError("boom")
        return self._raw


_GP = 'odoo.addons.pb_payroll_ai_insights.models.payroll_ai_config.PayrollAIConfig.get_provider'


@tagged('post_install', '-at_install')
class TestBankOcr(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        g_user = cls.env.ref('base.group_user')
        g_hr = cls.env.ref('om_hr_payroll.group_hr_payroll_user')
        g_mgr = cls.env.ref('om_hr_payroll.group_hr_payroll_manager')

        cls.emp_user = Users.create({'name': 'Owner', 'login': 'bnk_owner',
                                     'group_ids': [(6, 0, [g_user.id])]})
        cls.hr_user = Users.create({'name': 'HR', 'login': 'bnk_hr',
                                    'group_ids': [(6, 0, [g_hr.id])]})
        cls.fin_user = Users.create({'name': 'Finance', 'login': 'bnk_fin',
                                     'group_ids': [(6, 0, [g_mgr.id, g_hr.id])]})
        Emp = cls.env['hr.employee']
        cls.emp = Emp.create({'name': 'Nguyễn Văn Á', 'user_id': cls.emp_user.id,
                              'company_id': cls.company.id})

        # isolate from any config already present on the live DB (rolled back)
        cls.env['payroll.ai.config'].search([]).write({'is_active': False})
        # active doc_ocr config so extract() resolves a provider (patched)
        cls.cfg = cls.env['payroll.ai.config'].create({
            'provider_type': 'openai', 'purpose': 'doc_ocr',
            'api_key': 'x', 'is_active': True, 'company_id': cls.company.id})

    # ------------------------------------------------------------ helpers
    def _attachment(self):
        return self.env['ir.attachment'].create({
            'name': 'letter.pdf', 'datas': _FAKE_PDF, 'mimetype': 'application/pdf'})

    def _request(self, **vals):
        base = {'employee_id': self.emp.id, 'attachment_id': self._attachment().id}
        base.update(vals)
        return self.env['pb.bank.change.request'].create(base)

    # ---------------------------------------------------- §6.1 resolver
    def test_01_provider_resolution_and_degrade(self):
        Cfg = self.env['payroll.ai.config']
        self.assertEqual(Cfg.get_config_for_purpose('doc_ocr'), self.cfg)
        # no purposed config → any active config
        self.cfg.purpose = 'insights'
        self.assertEqual(Cfg.get_config_for_purpose('doc_ocr'), self.cfg)
        self.cfg.purpose = 'doc_ocr'
        # None-safe: no provider at all → degraded result, no traceback
        self.cfg.is_active = False
        res = self.env['biz.doc.ocr']._extract(
            {'fields': [{'name': 'x_account_number', 'type': 'digits'}]}, [])
        self.assertEqual(res['provider'], 'none')
        self.assertTrue(res['error'])
        self.assertEqual(res['fields'], {})
        self.cfg.is_active = True

    # ---------------------------------------------------- §6.2 vision contract
    def test_02_vision_contract_and_retry(self):
        raw = ('```json\n{"doc_kind": "confirmation_letter", "fields": '
               '{"x_account_number": {"value": "123456789012", "confidence": 0.95},'
               ' "x_bank_name": {"value": "Vietcombank", "confidence": 0.9}}}\n```')
        req = self._request()
        with patch(_GP, return_value=_FakeProvider(raw=raw)):
            req.action_run_ocr()
        self.assertEqual(req.ocr_state, 'done')
        self.assertEqual(req.x_account_number, '123456789012')
        conf = json.loads(req.confidence_json)
        self.assertAlmostEqual(conf['x_account_number'], 0.95, places=2)

        # malformed JSON → failed job; cron re-attempts, capped at 3
        req2 = self._request()
        with patch(_GP, return_value=_FakeProvider(raw='not json at all')):
            req2.action_run_ocr()
            self.assertEqual(req2.ocr_state, 'failed')
            job = self.env['biz.doc.ocr.job'].search(
                [('res_model', '=', req2._name), ('res_id', '=', req2.id)], limit=1)
            self.assertEqual(job.state, 'failed')
            for _i in range(5):
                self.env['biz.doc.ocr.job'].cron_retry()
        self.assertEqual(job.attempts, 3)  # never past the cap

    # ---------------------------------------------------- §6.3 tesseract path
    def test_03_tesseract_post_processor(self):
        # exercise the deterministic post-processor over OCR-style prose (the
        # Tesseract branch leaves fields for it); no binary needed here
        result = {'fields': {}, 'doc_kind': False, 'provider': 'tesseract',
                  'raw_text': 'NGAN HANG TMCP NGOAI THUONG VN\n'
                              'So tai khoan: 0123456789\nChu tai khoan: NGUYEN VAN A',
                  'error': False}
        req = self._request()
        out = req._ocr_post_process(result)
        self.assertEqual(out['fields']['x_account_number']['value'], '0123456789')
        self.assertTrue(out.get('resolved_bank_id'))
        bank = self.env['pb.bank.registry'].browse(out['resolved_bank_id'])
        self.assertEqual(bank.short_name, 'Vietcombank')

    # ---------------------------------------------------- §6.4 deterministic
    def test_04_deterministic_layer(self):
        self.assertEqual(vnd.fold('Nguyễn Văn Á'), 'NGUYEN VAN A')
        self.assertEqual(vnd.name_similarity('Nguyễn Văn Á', 'NGUYEN VAN A'), 100.0)
        self.assertLess(vnd.name_similarity('Tran Thi Bich', 'Nguyen Van A'), 60)
        self.assertEqual(vnd.extract_account_number('ref 12 acct 0123456789 end'),
                         '0123456789')
        self.assertTrue(vnd.account_ok('123456789012'))
        self.assertFalse(vnd.account_ok('12345'))
        self.assertTrue(vnd.swift_ok('BFTVVNVX'))
        self.assertFalse(vnd.swift_ok('BFTV1234'))

    # ---------------------------------------------------- §6.5 duplicates
    def test_05_duplicate_blocks_submit(self):
        other = self.env['hr.employee'].create({
            'name': 'Someone Else', 'company_id': self.company.id,
            'vietnam_bank_name': 'Vietcombank',
            'vietnam_bank_account_number': '123456789012'})
        req = self._request()
        req.write({'x_account_name': 'Nguyễn Văn Á', 'x_bank_name': 'Vietcombank',
                   'x_account_number': '123456789012'})
        req.action_validate()
        self.assertIn(other, req.duplicate_ids)
        # submit blocked until HR acks the duplicate
        with self.assertRaises(UserError):
            req.with_user(self.emp_user).action_submit()
        req.duplicate_ack = True
        req.with_user(self.emp_user).action_submit()
        self.assertEqual(req.state, 'hr_review')

    # ---------------------------------------------------- §6.6 format
    def test_06_format_validation(self):
        req = self._request()
        req.write({'x_account_number': '12345', 'x_account_name': 'Nguyễn Văn Á'})
        req.action_validate()
        self.assertFalse(req.v_format_ok)
        req.write({'x_account_number': '123456789012', 'x_swift': 'BFTVVNVX'})
        req.action_validate()
        self.assertTrue(req.v_format_ok)
        self.assertEqual(req.name_match_band, 'green')  # holder == employee

    def test_06b_name_match_amber_band(self):
        """A close-but-not-exact holder name lands in the amber 'Review' band
        (60 ≤ score < 85) — the reviewer is nudged, not auto-passed/auto-failed."""
        req = self._request()
        # 'Nguyen Thi Anh' vs employee 'Nguyễn Văn Á' scores ~69 (amber)
        req.write({'x_account_number': '123456789012',
                   'x_account_name': 'Nguyen Thi Anh'})
        req.action_validate()
        self.assertEqual(req.name_match_band, 'amber')
        self.assertGreaterEqual(req.name_match_score, 60.0)
        self.assertLess(req.name_match_score, 85.0)

    # ---------------------------------------------------- §6.7 chain + master
    def test_07_chain_writes_master_atomically(self):
        req = self._request()
        req.write({'x_bank_name': 'Vietcombank', 'x_bank_branch': 'Hoan Kiem',
                   'x_account_name': 'Nguyễn Văn Á',
                   'x_account_number': '123456789012'})
        # draft → hr_review by the owner
        req.with_user(self.emp_user).action_submit()
        self.assertEqual(req.state, 'hr_review')
        # a random user cannot move HR→finance; HR can
        with self.assertRaises(AccessError):
            req.with_user(self.emp_user).action_hr_approve()
        req.with_user(self.hr_user).action_hr_approve()
        self.assertEqual(req.state, 'finance_review')
        # HR (no finance group) cannot finance-approve; finance can
        with self.assertRaises(AccessError):
            req.with_user(self.hr_user).action_finance_approve()
        req.with_user(self.fin_user).action_finance_approve()
        self.assertEqual(req.state, 'approved')
        # master updated + exactly ONE ocr_request history row
        self.emp.invalidate_recordset()
        self.assertEqual(self.emp.vietnam_bank_account_number, '123456789012')
        self.assertEqual(self.emp.vietnam_bank_name, 'Vietcombank')
        hist = self.env['pb.employee.bank.history'].search([
            ('request_id', '=', req.id)])
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist.change_source, 'ocr_request')

    def test_07b_refuse_leaves_master_untouched(self):
        self.emp.vietnam_bank_account_number = '999999999999'
        req = self._request()
        req.write({'x_account_name': 'Nguyễn Văn Á', 'x_account_number': '111122223333'})
        req.with_user(self.emp_user).action_submit()
        req.with_user(self.hr_user).action_refuse_chain(note='not clear')
        self.assertEqual(req.state, 'refused')
        self.emp.invalidate_recordset()
        self.assertEqual(self.emp.vietnam_bank_account_number, '999999999999')

    # ---------------------------------------------- §6.9 export wizard reads new
    def _make_done_net_slip(self, emp, net):
        """A Done payslip with a NET line for `emp`, on a fresh run (Phase F)."""
        company = self.company
        calendar = (company.resource_calendar_id
                    or self.env['resource.calendar'].search([], limit=1))
        ctype = (self.env['hr.contract.type'].search([], limit=1)
                 or self.env['hr.contract.type'].create({'name': 'Std'}))
        contract = self.env['hr.contract'].create({
            'name': 'C-%s' % emp.id, 'employee_id': emp.id, 'wage': 1000.0,
            'resource_calendar_id': calendar.id, 'type_id': ctype.id})
        run = self.env['hr.payslip.run'].create({'name': 'ZZ Bank Export'})
        slip = self.env['hr.payslip'].create({
            'employee_id': emp.id, 'contract_id': contract.id,
            'payslip_run_id': run.id})
        self.env['hr.payslip.line'].create({
            'slip_id': slip.id, 'salary_rule_id': self.env.ref('om_hr_payroll.hr_rule_net').id,
            'employee_id': emp.id, 'contract_id': contract.id,
            'category_id': self.env.ref('om_hr_payroll.NET').id,
            'name': 'Net', 'code': 'NET', 'amount': net, 'quantity': 1.0, 'rate': 100.0})
        slip.write({'state': 'done'})
        return slip

    def test_09_export_wizard_reads_new_account(self):
        """§6.9/§6.6 (Phase F) — the approved NEW account appears IN the
        generated bank-file CONTENT. This closes the Phase-D honest-scope note:
        the export is now real and data-driven, and consumes the employee master
        that the approval chain wrote."""
        if 'vietnam.bank.export.wizard' not in self.env:
            self.skipTest('pb_hr_payroll_vietnam not installed')
        # employee starts on an OLD account; the request switches it
        self.emp.write({'vietnam_bank_name': 'BIDV', 'vietnam_bank_branch': 'Hoan Kiem',
                        'vietnam_bank_account_number': '000011112222'})
        req = self._request()
        req.write({'x_bank_name': 'Vietcombank', 'x_bank_branch': 'Hoan Kiem',
                   'x_account_name': 'Nguyễn Văn Á',
                   'x_account_number': '123456789012'})
        req.with_user(self.emp_user).action_submit()
        req.with_user(self.hr_user).action_hr_approve()
        req.with_user(self.fin_user).action_finance_approve()
        self.assertEqual(req.state, 'approved')
        self.emp.invalidate_recordset()
        # the export SOURCE now carries the approved values
        self.assertEqual(self.emp.vietnam_bank_account_number, '123456789012')
        self.assertEqual(self.emp.vietnam_bank_name, 'Vietcombank')

        # Phase F: assert the NEW account is IN the generated file content.
        if 'pb.bank.file.layout' not in self.env:
            self.skipTest('pb_pay_delivery (real file generation) not installed')
        slip = self._make_done_net_slip(self.emp, 11111111)
        wiz = self.env['vietnam.bank.export.wizard'].create({
            'payslip_run_id': slip.payslip_run_id.id, 'bank_format': 'vietcombank'})
        result = wiz._generate()
        layout = self.env['pb.bank.file.layout']._for_format('vietcombank')
        text = base64.b64decode(result['file_b64']).decode(layout.encoding or 'utf-8')
        self.assertIn('123456789012', text)          # the approved NEW account
        self.assertNotIn('000011112222', text)        # never the old one
        self.assertIn('Nguyễn Văn Á', text)

    # ---------------------------------------------------- §6.8 manual audit
    def test_08_manual_edit_logged(self):
        emp = self.env['hr.employee'].create({
            'name': 'Manual Guy', 'company_id': self.company.id})
        emp.write({'vietnam_bank_account_number': '5555666677'})
        rows = self.env['pb.employee.bank.history'].search([
            ('employee_id', '=', emp.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.change_source, 'manual')
        self.assertEqual(rows.new_account_number, '5555666677')
        # a non-bank write logs nothing
        emp.write({'name': 'Renamed'})
        self.assertEqual(len(self.env['pb.employee.bank.history'].search(
            [('employee_id', '=', emp.id)])), 1)

    # ------------------------------------- review-fix guards (C18.24 rails)
    def test_11_verification_fields_forgery_locked(self):
        """readonly=True doesn't stop call_kw — the sentinel guard must."""
        from odoo.addons.pb_bank_ocr.models.pb_bank_change_request import (
            _SYS_FIELDS)
        req = self._request()
        as_owner = req.with_user(self.emp_user)
        for vals in ({'name_match_band': 'green'}, {'name_match_score': 100.0},
                     {'v_format_ok': True}, {'cur_account_number': '000'},
                     {'ocr_state': 'done'}, {'confidence_json': '{}'}):
            with self.assertRaises(AccessError):
                as_owner.write(vals)
        with self.assertRaises(AccessError):
            as_owner.write({'duplicate_ack': True})
        # forged system values in CREATE are silently stripped
        forged = self.env['pb.bank.change.request'].with_user(
            self.emp_user).create({
                'employee_id': self.emp.id,
                'attachment_id': self._attachment().id,
                'name_match_band': 'green', 'name_match_score': 100.0,
                'duplicate_ack': True})
        self.assertFalse(forged.name_match_band)
        self.assertFalse(forged.duplicate_ack)
        self.assertTrue(_SYS_FIELDS)  # import is real, not a stale symbol

    def test_12_post_submit_swap_blocked(self):
        """The TOCTOU: no owner edit of reviewed fields after submit."""
        req = self._request()
        req.write({'x_account_name': 'Nguyễn Văn Á',
                   'x_account_number': '123456789012'})
        req.with_user(self.emp_user).action_submit()
        with self.assertRaises(AccessError):
            req.with_user(self.emp_user).write(
                {'x_account_number': '999988887777'})
        with self.assertRaises(AccessError):
            req.with_user(self.emp_user).write(
                {'attachment_id': self._attachment().id})
        # HR may still correct the extraction during review
        req.with_user(self.hr_user).write({'x_bank_branch': 'Ba Dinh'})
        self.assertEqual(req.x_bank_branch, 'Ba Dinh')

    def test_13_forged_audit_context_still_logs(self):
        """A client-forged truthy from_bank_request must not skip the audit."""
        emp = self.env['hr.employee'].create({
            'name': 'Forged Ctx', 'company_id': self.company.id})
        emp.with_context(from_bank_request=True).write(
            {'vietnam_bank_account_number': '4444555566'})
        rows = self.env['pb.employee.bank.history'].search(
            [('employee_id', '=', emp.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.change_source, 'manual')

    def test_14_ocr_job_own_only(self):
        """Job results carry extracted PII — visible to their creator only."""
        Job = self.env['biz.doc.ocr.job']
        job_hr = Job.with_user(self.hr_user).create({
            'res_model': 'pb.bank.change.request', 'res_id': 1,
            'result': '{"fields": {"x_account_number": "SECRET"}}'})
        seen = Job.with_user(self.emp_user).search([('id', '=', job_hr.id)])
        self.assertFalse(seen)
        self.assertEqual(
            Job.with_user(self.hr_user).browse(job_hr.id).result,
            '{"fields": {"x_account_number": "SECRET"}}')

    def test_15_approve_revalidates_final_values(self):
        """Approval re-derives validation against the FINAL field values."""
        req = self._request()
        req.write({'x_bank_name': 'Vietcombank',
                   'x_account_name': 'Nguyễn Văn Á',
                   'x_account_number': '123456789012'})
        req.with_user(self.emp_user).action_submit()
        req.with_user(self.hr_user).action_hr_approve()
        req.write({'x_account_number': '12345'})  # admin-forced bad value
        with self.assertRaises(UserError):
            req.with_user(self.fin_user).action_finance_approve()

    def test_16_job_retention_vacuum(self):
        """Terminal jobs past the retention window are purged (their
        payload/result hold extracted PII); fresh + in-flight jobs are kept,
        and cron_retry runs the vacuum."""
        Job = self.env['biz.doc.ocr.job']
        self.env['ir.config_parameter'].sudo().set_param(
            'biz_doc_ocr.job_retention_days', '30')
        old_done = Job.create({'res_model': 'pb.bank.change.request', 'res_id': 1,
                               'state': 'done', 'result': '{"pii": "0123456789"}'})
        old_failed = Job.create({'res_model': 'pb.bank.change.request', 'res_id': 1,
                                 'state': 'failed', 'attempts': 3})
        old_pending = Job.create({'res_model': 'pb.bank.change.request', 'res_id': 1,
                                  'state': 'pending'})
        fresh_done = Job.create({'res_model': 'pb.bank.change.request', 'res_id': 1,
                                 'state': 'done'})
        # age the three rows beyond retention — the vacuum clock is write_date
        # (time since the terminal state), a magic column → SQL
        self.env.cr.execute(
            "UPDATE biz_doc_ocr_job SET write_date = "
            "(now() at time zone 'UTC') - interval '40 days' WHERE id IN %s",
            (tuple([old_done.id, old_failed.id, old_pending.id]),))
        Job.invalidate_recordset(['write_date'])
        # direct vacuum: only aged terminal rows go; aged pending + fresh stay
        Job._vacuum_jobs()
        self.assertFalse(old_done.exists())
        self.assertFalse(old_failed.exists())
        self.assertTrue(old_pending.exists())  # in-flight is never vacuumed
        self.assertTrue(fresh_done.exists())
        # a non-positive config value falls back to the 30-day default (never 0)
        self.env['ir.config_parameter'].sudo().set_param(
            'biz_doc_ocr.job_retention_days', '0')
        self.assertEqual(Job._retention_days(), Job._DEFAULT_RETENTION_DAYS)
        # wiring: cron_retry also runs the vacuum
        old_done2 = Job.create({'res_model': 'pb.bank.change.request',
                                'res_id': 1, 'state': 'done'})
        self.env.cr.execute(
            "UPDATE biz_doc_ocr_job SET write_date = "
            "(now() at time zone 'UTC') - interval '40 days' WHERE id = %s",
            (old_done2.id,))
        Job.invalidate_recordset(['write_date'])
        Job.cron_retry()
        self.assertFalse(old_done2.exists())

    # ---------------------------------------------------- §6.10 insights safe
    def test_10_insights_factory_unchanged(self):
        from odoo.addons.pb_payroll_ai_insights.ai_providers.provider_factory import (
            PROVIDER_REGISTRY, get_provider)
        from odoo.addons.pb_payroll_ai_insights.ai_providers.openai_provider import (
            OpenAIProvider)
        self.assertIs(PROVIDER_REGISTRY['openai'], OpenAIProvider)
        prov = get_provider('openai', {'api_key': 'x'})
        self.assertIsInstance(prov, OpenAIProvider)
        # the three new providers are registered and vision-capable
        for key in ('anthropic', 'ollama', 'tesseract'):
            self.assertIn(key, PROVIDER_REGISTRY)
