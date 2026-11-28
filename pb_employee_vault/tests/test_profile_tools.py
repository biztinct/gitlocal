import base64
from datetime import date
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestProfileTools(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env['hr.employee'].create({'name':'Profile tools test'})
        cls.contract = cls.env['hr.contract'].with_context(pb_skip_fill_in=True).create({
            'name':'Profile salary','employee_id':cls.employee.id,
            'date_start':date(2026,1,1),'state':'open','wage':127000,'schedule_pay':'monthly'})
        cls.employee.contract_id = cls.contract
        cls.manager = cls.user('profile_tools_manager','om_hr_payroll.group_hr_payroll_manager')
        cls.officer = cls.user('profile_tools_officer','om_hr_payroll.group_hr_payroll_user')
        cls.portal = cls.user('profile_tools_portal','base.group_portal')

    @classmethod
    def user(cls, name, group):
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name':name,'login':name,'group_ids':[(6,0,[cls.env.ref(group).id])]})

    def test_salary_is_contract_backed_and_restricted(self):
        text=self.employee.with_user(self.manager).pb_profile_contract_pay
        self.assertIn('127,000',text)
        self.contract.wage=128000
        self.assertIn('128,000',self.employee.with_user(self.manager).pb_profile_contract_pay)
        for user in [self.officer,self.portal]:
            with self.assertRaises(AccessError):
                self.employee.with_user(user).read(['pb_profile_contract_pay'])

    def test_resume_upload_uses_private_vault(self):
        content=b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF'
        wizard=self.env['pb.employee.resume.upload'].with_user(self.manager).create({
            'employee_id':self.employee.id,'filename':'resume.pdf','file_data':base64.b64encode(content)})
        wizard.action_upload()
        doc=self.env['pb.employee.document'].search([('employee_id','=',self.employee.id),('category_id.code','=','RESUME')])
        self.assertEqual(len(doc),1)
        self.assertEqual(doc.attachment_id.res_model,'pb.employee.document')
        self.assertEqual(doc.attachment_id.res_id,doc.id)
        self.assertFalse(doc.attachment_id.public)
        self.assertFalse(doc.verified)
        with self.assertRaises(AccessError):
            doc.with_user(self.portal).read(['name'])

    def test_invalid_file_and_portal_upload_refused(self):
        wizard=self.env['pb.employee.resume.upload'].with_user(self.manager).create({
            'employee_id':self.employee.id,'filename':'resume.pdf','file_data':base64.b64encode(b'not a PDF')})
        with self.assertRaises(ValidationError):wizard.action_upload()
        with self.assertRaises(AccessError):self.employee.with_user(self.portal).action_upload_resume()
