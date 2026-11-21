import base64
from unittest.mock import patch
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestBatchUpload(TransactionCase):
    def setUp(self):
        super().setUp()
        self.emp = self.env['hr.employee'].create({'name':'Batch upload test'})
        self.people = self.env['pb.people']
        self.payload = {'name':'test.pdf','mime':'application/pdf','data':base64.b64encode(b'%PDF-1.4\nTest\n%%EOF').decode()}

    def test_individual_expiry_and_atomic_validation(self):
        for xmlid in ('cat_id_document','cat_health_check','cat_work_permit'):
            category = self.env.ref('pb_employee_vault.'+xmlid)
            before = self.env['ir.attachment'].search_count([])
            with self.assertRaises(ValidationError):
                self.people.vault_upload_batch(self.emp.id, category.id,[
                    {'payload':self.payload,'expiry_date':'2028-01-01'}, {'payload':self.payload}])
            self.assertEqual(before,self.env['ir.attachment'].search_count([]))
            with patch.object(type(self.people),'get_employee_360',return_value={}):
                self.people.vault_upload_batch(self.emp.id,category.id,[
                    {'payload':self.payload,'expiry_date':'2028-01-01'},
                    {'payload':self.payload,'expiry_date':'2029-02-02'}])
            docs = self.env['pb.employee.document'].search([('employee_id','=',self.emp.id),('category_id','=',category.id)])
            self.assertEqual(len(docs),2)
            self.assertEqual(sorted(str(d.expiry_date) for d in docs),['2028-01-01','2029-02-02'])
            self.assertFalse(any(d.attachment_id.public for d in docs))
            self.assertFalse(any(d.verified for d in docs))

    def test_portal_cannot_upload_or_read_others_documents(self):
        user=self.env['res.users'].with_context(no_reset_password=True).create({'name':'Batch portal','login':'batch_portal_test','group_ids':[(6,0,[self.env.ref('base.group_portal').id])]})
        with self.assertRaises(AccessError):
            self.people.with_user(user).vault_upload_batch(self.emp.id,self.env.ref('pb_employee_vault.cat_other').id,[{'payload':self.payload}])
