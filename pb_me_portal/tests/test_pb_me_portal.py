# Part of Payobook. See LICENSE file for full copyright and licensing details.
import base64

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

# a real 2×2 PNG (Pillow rejects a hand-crafted 1×1 / truncated one — C18.13)
_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP4z8AA'
    'RAwQCgAf7gP9i18U1AAAAABJRU5ErkJggg==')


@tagged('post_install', '-at_install')
class TestPbMePortal(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        Emp = cls.env['hr.employee']
        internal = cls.env.ref('base.group_user')
        hr_user_grp = cls.env.ref('hr.group_hr_user')
        pay_hr = cls.env.ref('om_hr_payroll.group_hr_payroll_user', raise_if_not_found=False)

        cls.emp_user = Users.create({
            'name': 'ESS Employee', 'login': 'test_ess_emp',
            'group_ids': [(6, 0, [internal.id])]})
        hr_gids = [internal.id, hr_user_grp.id] + ([pay_hr.id] if pay_hr else [])
        cls.hr_user = Users.create({
            'name': 'ESS HR', 'login': 'test_ess_hr',
            'group_ids': [(6, 0, hr_gids)]})

        cls.employee = Emp.create({
            'name': 'ESS Emp', 'user_id': cls.emp_user.id,
            'company_id': cls.company.id, 'private_phone': '0111'})
        cls.colleague = Emp.create({
            'name': 'Colleague', 'company_id': cls.company.id})

    # ---------------------------------------------------- profile chain
    def test_01_profile_change_flow_and_audit(self):
        Req = self.env['pb.profile.change.request']
        req = Req.with_user(self.emp_user).create({
            'employee_id': self.employee.id, 'x_phone': '0999'})
        # submit as owner
        req.with_user(self.emp_user).action_submit()
        self.assertEqual(req.state, 'hr_review')
        self.assertEqual(req.cur_phone, '0111')   # snapshot taken
        # HR approves → master written
        req.with_user(self.hr_user).action_hr_approve()
        self.assertEqual(req.state, 'approved')
        self.assertEqual(self.employee.private_phone, '0999')
        # audit entry exists with the TRUE actor (the HR approver)
        entry = self.env['biz.audit.entry'].sudo().search([
            ('model_name', '=', 'hr.employee'),
            ('res_id', '=', self.employee.id),
            ('field_name', '=', 'private_phone')], limit=1)
        self.assertTrue(entry, "an audit entry must record the master change")
        self.assertEqual(entry.user_id, self.hr_user)

    def test_02_sentinel_snapshot(self):
        req = self.env['pb.profile.change.request'].with_user(self.emp_user).create({
            'employee_id': self.employee.id, 'x_phone': '0999'})
        with self.assertRaises(AccessError):
            req.with_user(self.emp_user).write({'cur_phone': 'forged'})

    def test_03_whitelist_strips_field(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_me_portal.editable_fields', 'x_phone')
        req = self.env['pb.profile.change.request'].with_user(self.emp_user).create({
            'employee_id': self.employee.id,
            'x_phone': '0999', 'x_address': 'Somewhere St'})
        self.assertEqual(req.x_phone, '0999')
        self.assertFalse(req.x_address, "a non-whitelisted proposed field is stripped")

    # ------------------------------------------------------- documents
    def _attachment(self):
        return self.env['ir.attachment'].with_user(self.emp_user).create({
            'name': 'cert.png', 'datas': base64.b64encode(_PNG),
            'mimetype': 'image/png'})

    def test_04_document_own_upload(self):
        cat = self.env.ref('pb_employee_vault.cat_other')
        self.assertTrue(cat.ess_uploadable)
        att = self._attachment()
        doc = self.env['pb.employee.document'].with_user(self.emp_user).create({
            'employee_id': self.employee.id, 'category_id': cat.id,
            'name': 'My ID', 'attachment_id': att.id})
        self.assertTrue(doc.id)
        self.assertFalse(doc.verified)

    def test_05_document_not_for_colleague(self):
        cat = self.env.ref('pb_employee_vault.cat_other')
        att = self._attachment()
        with self.assertRaises(AccessError):
            self.env['pb.employee.document'].with_user(self.emp_user).create({
                'employee_id': self.colleague.id, 'category_id': cat.id,
                'name': 'Not mine', 'attachment_id': att.id})

    def test_06_document_cannot_self_verify(self):
        cat = self.env.ref('pb_employee_vault.cat_other')
        att = self._attachment()
        # a crafted verified=True at create is stripped (Phase-H sentinel)
        doc = self.env['pb.employee.document'].with_user(self.emp_user).create({
            'employee_id': self.employee.id, 'category_id': cat.id,
            'name': 'ID', 'attachment_id': att.id, 'verified': True})
        self.assertFalse(doc.verified)

    # -------------------------------------------------------- tax sheet
    def test_07_tax_codes_config_driven(self):
        Slip = self.env['hr.payslip']
        default_codes = Slip._ess_tax_codes()
        self.assertIn('PIT', default_codes)
        self.assertIn('GROSS', default_codes)
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_me_portal.tax_codes', 'PIT,TXBASE,PIT')
        codes = Slip._ess_tax_codes()
        self.assertEqual(codes, ['PIT', 'TXBASE'], "order-preserving + de-duplicated")
