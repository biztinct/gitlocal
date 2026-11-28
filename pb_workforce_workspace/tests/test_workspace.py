from odoo.tests.common import TransactionCase, new_test_user, tagged
from odoo.exceptions import AccessError, ValidationError


@tagged('post_install', '-at_install')
class TestWorkforceWorkspace(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Workspace test company'})
        cls.other = cls.env['res.company'].create({'name': 'Other workspace company'})
        cls.manager = new_test_user(cls.env, login='workspace_test_manager',
            groups='hr_attendance.group_hr_attendance_manager,hr.group_hr_manager',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id, cls.other.id])])
        cls.officer = new_test_user(cls.env, login='workspace_test_officer',
            groups='hr_attendance.group_hr_attendance_officer', company_id=cls.company.id,
            company_ids=[(6, 0, [cls.company.id])])
        cls.basic = new_test_user(cls.env, login='workspace_test_basic', groups='base.group_user',
            company_id=cls.company.id, company_ids=[(6, 0, [cls.company.id])])
        cls.shift = cls.env['hr.shift.template'].create({'name':'Workspace day','code':'WST-DAY',
            'start_hour':7.5,'end_hour':16.5,'break_duration':1,'company_id':cls.company.id})
        cls.hidden = cls.env['hr.shift.template'].create({'name':'Workspace other','code':'WST-OTHER',
            'start_hour':8,'end_hour':17,'company_id':cls.other.id})

    def facade(self, user=None):
        return self.env['pb.workforce.workspace'].with_user(user or self.manager).with_context(
            allowed_company_ids=[self.company.id, self.other.id] if not user else [self.company.id])

    def test_installation_is_opt_in(self):
        self.assertFalse(self.company.pb_workforce_workspace_enabled)
        self.assertFalse(self.facade().preferences()['enabled'])
        self.assertFalse(self.facade().preferences()['can_configure'])

    def test_current_company_scope_even_with_two_allowed(self):
        rows=self.facade().catalog('shifts')['rows']
        self.assertIn(self.shift.id,[r['id'] for r in rows])
        self.assertNotIn(self.hidden.id,[r['id'] for r in rows])

    def test_officer_reads_but_cannot_write_shift(self):
        data=self.facade(self.officer).catalog('shifts')
        self.assertFalse(data['can_create'])
        self.assertFalse(data['can_write'])
        with self.assertRaises(AccessError):
            self.shift.with_user(self.officer).write({'name':'Forbidden'})

    def test_non_attendance_user_cannot_read_catalog(self):
        with self.assertRaises(AccessError):self.facade(self.basic).catalog('people')
        self.assertIn('enabled',self.facade(self.basic).preferences())

    def test_workspace_opt_in_requires_administrator(self):
        with self.assertRaises(AccessError):
            self.company.with_user(self.manager).write({'pb_workforce_workspace_enabled':True})

    def test_no_arbitrary_model_read(self):
        with self.assertRaises(ValidationError):self.facade().catalog('res.users')

    def test_search_and_pagination(self):
        self.assertEqual(self.facade().catalog('shifts',search='Workspace day')['total'],1)
        self.assertEqual(self.facade().catalog('shifts',offset=100)['rows'],[])

    def test_readiness_does_not_activate_or_publish(self):
        before=self.env['hr.shift.planning'].search_count([('company_id','=',self.company.id)])
        data=self.facade().overview('2026-11-23')
        self.assertEqual(data['week_end'],'2026-11-29')
        self.assertEqual(len(data['steps']),6)
        self.assertEqual(before,self.env['hr.shift.planning'].search_count([('company_id','=',self.company.id)]))
        self.assertFalse(self.company.pb_workforce_workspace_enabled)
        if 'pb.attendance.policy' in self.env:self.assertEqual(data['active_policies'],0)

    def test_workplace_filter_cannot_expand_company(self):
        location=self.env['hr.work.location'].create({'name':'Other factory','company_id':self.other.id,'address_id':self.other.partner_id.id})
        employee=self.env['hr.employee'].create({'name':'Other company employee','company_id':self.other.id,'work_location_id':location.id})
        data=self.facade().catalog('people',location_id=location.id)
        self.assertNotIn(employee.id,[r['id'] for r in data['rows']])
