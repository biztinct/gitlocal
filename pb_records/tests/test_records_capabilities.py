from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from .test_records_r2_desk import TestRecordsR2Desk


@tagged('post_install', '-at_install', 'records_capability')
class TestRecordsCapabilities(TestRecordsR2Desk):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.viewer = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Records capability viewer', 'login':'records-capability-viewer',
            'group_ids':[(6,0,cls.env.ref('pb_records.group_records_viewer').ids)]})
        cls.editor = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name':'Records capability editor', 'login':'records-capability-editor',
            'group_ids':[(6,0,cls.env.ref('pb_records.group_records_editor').ids)]})

    def test_viewer_reads_but_cannot_edit_or_export(self):
        desk=self.Desk.with_user(self.viewer)
        data=desk.get_fields(self.cfg.id)
        self.assertFalse(data['can_write']['employee']); self.assertFalse(data['can_export'])
        result=desk.preview_changes(self.cfg.id,[{'emp_id':self.e1.id,
            'field_id':'f:hr.employee:location','value':'Viewer must not write'}])
        self.assertEqual(result['counts']['ok'],0)
        with self.assertRaises(UserError): desk.export_records(self.cfg.id)

    def test_editor_changes_mapped_field_without_native_hr_write(self):
        desk=self.Desk.with_user(self.editor)
        self.assertTrue(desk._may_write('hr.employee'))
        self.assertFalse(self.env['hr.employee'].with_user(self.editor).has_access('write'))
        result=desk.apply_changes(self.cfg.id,[{'emp_id':self.e1.id,
            'field_id':'f:hr.employee:location','value':'Capability edit'}],note='Capability test')
        self.assertEqual(result['written'],1)
        self.assertEqual(self.e1.location,'Capability edit')

    def test_editor_cannot_change_unmapped_field(self):
        desk=self.Desk.with_user(self.editor)
        with self.assertRaises(UserError):
            desk.preview_changes(self.cfg.id,[{'emp_id':self.e1.id,'field_id':'f:hr.employee:study_field','value':'Denied'}])

    def test_export_is_separate_from_edit(self):
        self.viewer.write({'group_ids':[(4,self.env.ref('pb_records.group_records_exporter').id)]})
        desk=self.Desk.with_user(self.viewer)
        self.assertTrue(desk._may_export()); self.assertFalse(desk._may_write('hr.employee'))
