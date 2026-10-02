# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""Server tests for Phase H — Employee 360 (§6 cases 1–10).

The audit trail is append-only with a FORCED actor/stamp; verification is HR
testimony (sentinel-guarded); documents are PII (own-read for employees); the
timeline merges existing evidence and masks wage for non-managers.
"""

import base64
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged

_PDF = base64.b64encode(b"%PDF-1.4\n%test document\n%%EOF").decode()


@tagged('post_install', '-at_install')
class TestEmployeeVault(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Emp = cls.env['hr.employee']
        cls.Contract = cls.env['hr.contract']
        cls.Doc = cls.env['pb.employee.document']
        cls.Entry = cls.env['biz.audit.entry']
        cls.People = cls.env['pb.people']
        cls.today = date.today()

        cls.dep1 = cls.env['hr.department'].create({'name': 'Vault Dep 1'})
        cls.dep2 = cls.env['hr.department'].create({'name': 'Vault Dep 2'})

        cls.emp_a = cls.Emp.create({
            'name': 'Alice Anchor', 'company_id': cls.company.id,
            'department_id': cls.dep1.id, 'job_title': 'Analyst'})
        cls.emp_b = cls.Emp.create({
            'name': 'Bob Bystander', 'company_id': cls.company.id})

        # users: a payroll manager (unmask wage), an HR officer (masked wage),
        # a plain user linked to emp_a (own-read only).
        cls.mgr = cls._mk_user('vault_mgr', [
            'om_hr_payroll.group_hr_payroll_manager'])
        cls.hr = cls._mk_user('vault_hr', ['om_hr_payroll.group_hr_payroll_user'])
        cls.plain = cls._mk_user('vault_plain', ['base.group_user'])
        cls.emp_a.user_id = cls.plain.id

        # categories seeded by data
        cls.cat_other = cls.env.ref('pb_employee_vault.cat_other')
        cls.cat_permit = cls.env.ref('pb_employee_vault.cat_work_permit')  # requires_expiry

    @classmethod
    def _mk_user(cls, login, group_xmlids):
        gids = [cls.env.ref(x).id for x in group_xmlids]
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login,
            'group_ids': [(6, 0, gids)]})

    def _mk_attachment(self):
        return self.env['ir.attachment'].create({
            'name': 'permit.pdf', 'datas': _PDF, 'mimetype': 'application/pdf'})

    def _mk_doc(self, emp=None, cat=None, expiry=False):
        return self.Doc.create({
            'employee_id': (emp or self.emp_a).id,
            'category_id': (cat or self.cat_other).id,
            'name': 'Doc', 'attachment_id': self._mk_attachment().id,
            'expiry_date': expiry or False})

    def _emp_entries(self, emp):
        """Audit entries for an employee across hr.employee (stored fields) AND
        hr.version (department/job — non-stored related, backed by the version)."""
        vids = []
        if 'hr.version' in self.env:
            vids = self.env['hr.version'].sudo().search(
                [('employee_id', '=', emp.id)]).ids
        return self.Entry.search([
            '|',
            '&', ('model_name', '=', 'hr.employee'), ('res_id', '=', emp.id),
            '&', ('model_name', '=', 'hr.version'), ('res_id', 'in', vids or [0])])

    # ============================================================ 1. audit engine
    def test_01_position_field_audit(self):
        # department_id + job_title are version-backed — the write routes to
        # hr.version, which the mixin audits (mapped to the employee here).
        n0 = len(self._emp_entries(self.emp_a))
        self.emp_a.with_user(self.hr).write({
            'department_id': self.dep2.id, 'job_title': 'Senior Analyst'})
        new = self._emp_entries(self.emp_a).filtered(
            lambda e: e.field_name in ('department_id', 'job_title'))
        self.assertEqual(len(new), 2)
        by_field = {e.field_name: e for e in new}
        self.assertEqual(by_field['department_id'].old_value, 'Vault Dep 1')
        self.assertEqual(by_field['department_id'].new_value, 'Vault Dep 2')
        self.assertEqual(by_field['job_title'].new_value, 'Senior Analyst')
        # actor is forced to the writing user, never client-supplied
        self.assertEqual(by_field['department_id'].user_id, self.hr)
        self.assertGreater(len(self._emp_entries(self.emp_a)), n0)

    def test_01b_stored_field_audit_and_unwatched(self):
        # a stored employee field (parent_id) audits on hr.employee directly
        self.emp_a.with_user(self.hr).write({'parent_id': self.emp_b.id})
        pe = self.Entry.search([('model_name', '=', 'hr.employee'),
                                ('res_id', '=', self.emp_a.id),
                                ('field_name', '=', 'parent_id')])
        self.assertEqual(len(pe), 1)
        self.assertEqual(pe.new_value, 'Bob Bystander')
        self.assertEqual(pe.user_id, self.hr)
        # an unwatched field logs nothing
        n0 = len(self._emp_entries(self.emp_a))
        self.emp_a.write({'work_phone': '0900000000'})
        self.assertEqual(len(self._emp_entries(self.emp_a)), n0)

    # ============================================================ 2. contract audit
    def test_02_contract_wage_and_state_audit(self):
        c = self.Contract.create({
            'name': 'C-A', 'employee_id': self.emp_a.id,
            'wage': 1000.0, 'state': 'draft',
            'date_start': str(self.today)})
        c.write({'wage': 1500.0})
        c.write({'state': 'open'})
        wage_e = self.Entry.search([('model_name', '=', 'hr.contract'),
                                    ('res_id', '=', c.id), ('field_name', '=', 'wage')])
        state_e = self.Entry.search([('model_name', '=', 'hr.contract'),
                                     ('res_id', '=', c.id), ('field_name', '=', 'state')])
        self.assertEqual(len(wage_e), 1)
        self.assertEqual(wage_e.new_value, '1500.0')
        self.assertEqual(len(state_e), 1)
        # selection renders the label, not the raw key
        self.assertEqual(state_e.new_value, 'Running')

    # ============================================================ 3. rule toggle + cache
    def test_03_rule_off_no_entry_cache_invalidates(self):
        rule = self.env.ref('pb_employee_vault.audit_rule_hr_employee')
        dom = [('model_name', '=', 'hr.employee'), ('res_id', '=', self.emp_a.id)]
        rule.active = False
        n0 = self.Entry.search_count(dom)
        self.emp_a.write({'parent_id': self.emp_b.id})
        self.assertEqual(self.Entry.search_count(dom), n0,
                         "a disabled rule must log nothing")
        # re-enabling invalidates the ormcache and logging resumes
        rule.active = True
        self.emp_a.write({'parent_id': False})
        self.assertGreater(self.Entry.search_count(dom), n0)

    # ============================================================ 4. append-only + GC
    def test_04_append_only_and_vacuum(self):
        self.emp_a.write({'parent_id': self.emp_b.id})   # entry 1 (old)
        e_old = self.Entry.search([('model_name', '=', 'hr.employee'),
                                   ('res_id', '=', self.emp_a.id),
                                   ('field_name', '=', 'parent_id')], limit=1)
        self.assertTrue(e_old)
        # append-only: a non-system user can neither edit nor delete an entry
        with self.assertRaises(AccessError):
            e_old.with_user(self.hr).write({'new_value': 'forged'})
        with self.assertRaises(AccessError):
            e_old.with_user(self.hr).unlink()
        self.emp_a.write({'parent_id': False})           # entry 2 (young)
        e_young = self.Entry.search(
            [('model_name', '=', 'hr.employee'), ('res_id', '=', self.emp_a.id),
             ('field_name', '=', 'parent_id'), ('id', '!=', e_old.id)], limit=1)
        self.assertTrue(e_young)
        # GC: age the first past a 1-day window; the young one survives
        self.env.cr.execute(
            "UPDATE biz_audit_entry SET write_date = %s WHERE id = %s",
            (fields.Datetime.now() - timedelta(days=40), e_old.id))
        e_old.invalidate_recordset(['write_date'])
        self.env['ir.config_parameter'].sudo().set_param(
            'biz_audit_trail.retention_days', '1')
        self.Entry._gc_vacuum()
        self.assertFalse(e_old.exists())
        self.assertTrue(e_young.exists())

    # ============================================================ 5. failure isolation
    def test_05_audit_failure_does_not_block_write(self):
        EntryCls = type(self.env['biz.audit.entry'])
        with patch.object(EntryCls, 'create', side_effect=Exception('boom')):
            self.emp_a.write({'job_title': 'Resilient'})  # must NOT raise
        self.assertEqual(self.emp_a.job_title, 'Resilient')

    # ============================================================ 6. vault upload / PII
    def test_06_upload_order_and_pii(self):
        res = self.People.with_user(self.hr).vault_upload(
            self.emp_a.id, self.cat_other.id,
            {'name': 'passport.pdf', 'mime': 'application/pdf', 'data': _PDF})
        doc = self.Doc.browse(res['documents'][0]['id'])
        att = doc.attachment_id
        # C18.25: the attachment is bound to the document AFTER creation
        self.assertEqual(att.res_model, 'pb.employee.document')
        self.assertEqual(att.res_id, doc.id)
        # PII: emp_a's own user reads only their own; emp_b's docs are invisible
        self._mk_doc(emp=self.emp_b)
        own = self.Doc.with_user(self.plain).search([])
        self.assertTrue(all(d.employee_id == self.emp_a for d in own))
        # a plain user cannot create a document (ACL)
        with self.assertRaises(AccessError):
            self.Doc.with_user(self.plain).create({
                'employee_id': self.emp_a.id, 'category_id': self.cat_other.id,
                'name': 'x', 'attachment_id': self._mk_attachment().id})

    def test_06b_expiry_required(self):
        with self.assertRaises(ValidationError):
            self._mk_doc(cat=self.cat_permit)          # requires_expiry, none given
        # with an expiry it is fine
        self._mk_doc(cat=self.cat_permit, expiry=self.today + timedelta(days=100))

    # ============================================================ 7. verified forgery
    def test_07_verified_is_hr_testimony(self):
        doc = self._mk_doc()
        # even HR cannot DIRECT-write the flag — only action_verify may
        with self.assertRaises(AccessError):
            doc.with_user(self.hr).write({'verified': True})
        with self.assertRaises(AccessError):
            doc.with_user(self.plain).write({'verified': True})
        doc.with_user(self.hr).action_verify()
        self.assertTrue(doc.verified)
        self.assertEqual(doc.verified_by, self.hr)
        self.assertTrue(doc.verified_at)

    # ============================================================ 8. expiry cron
    def test_08_expiry_cron_idempotent(self):
        self._mk_doc(expiry=self.today + timedelta(days=10))
        made1 = self.Doc._cron_expiry_check()
        self.assertGreaterEqual(made1, 1)
        acts = self.env['mail.activity'].search([
            ('res_model', '=', 'hr.employee'), ('res_id', '=', self.emp_a.id)])
        n_after1 = len(acts)
        made2 = self.Doc._cron_expiry_check()          # re-run
        acts2 = self.env['mail.activity'].search([
            ('res_model', '=', 'hr.employee'), ('res_id', '=', self.emp_a.id)])
        self.assertEqual(len(acts2), n_after1, "expiry activity must be idempotent")

    # ============================================================ 9. timeline merge
    def test_09_timeline_merge_and_wage_mask(self):
        # dept change + wage change (always available)
        self.emp_a.write({'department_id': self.dep2.id})
        c = self.Contract.create({
            'name': 'C-TL', 'employee_id': self.emp_a.id, 'wage': 2000.0,
            'state': 'draft', 'date_start': str(self.today)})
        c.write({'wage': 2600.0})
        seeded_bank = self._maybe_seed_bank(self.emp_a)

        # payroll manager sees the wage number
        mgr_payload = self.People.with_user(self.mgr).get_employee_360(self.emp_a.id)
        mgr_tl = mgr_payload['timeline']
        titles = [it['title'] for it in mgr_tl]
        self.assertTrue(any('Department' in t for t in titles))
        wage_items = [it for it in mgr_tl if 'wage' in it['title'].lower()]
        self.assertTrue(wage_items)
        self.assertIn('2600', ' '.join(it['detail'] for it in wage_items))
        self.assertTrue(mgr_payload['unmask_wage'])
        if seeded_bank:
            self.assertTrue(any(it['kind'] == 'bank' for it in mgr_tl))

        # HR officer (not manager) gets the wage EVENT but not the number
        hr_payload = self.People.with_user(self.hr).get_employee_360(self.emp_a.id)
        hr_wage = [it for it in hr_payload['timeline'] if 'wage' in it['title'].lower()]
        self.assertTrue(hr_wage)
        self.assertNotIn('2600', ' '.join(it['detail'] for it in hr_wage))
        self.assertFalse(hr_payload['unmask_wage'])
        # and the wage is scrubbed from the profile payload itself (rail 4)
        self.assertFalse(hr_payload['profile']['contract'].get('wage'))

    def _maybe_seed_bank(self, emp):
        if 'pb.employee.bank.history' not in self.env:
            return False
        self.env['pb.employee.bank.history'].sudo().create({
            'employee_id': emp.id, 'change_source': 'manual',
            'old_account_number': '111122223333',
            'new_account_number': '444455556666'})
        return True

    # ============================================================ 10. deletion survival
    def test_10_entry_survives_record_deletion(self):
        c = self.Contract.create({
            'name': 'C-Doomed', 'employee_id': self.emp_a.id, 'wage': 900.0,
            'state': 'draft', 'date_start': str(self.today)})
        c.write({'wage': 950.0})
        entry = self.Entry.search([('model_name', '=', 'hr.contract'),
                                   ('res_id', '=', c.id), ('field_name', '=', 'wage')])
        self.assertTrue(entry)
        display = entry.res_display
        self.assertTrue(display)
        c.unlink()
        self.assertTrue(entry.exists())
        self.assertEqual(entry.res_display, display)
