from datetime import timedelta
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.biz_access.models.studio_models import STUDIO
from odoo.addons.biz_access.models.role_assignments import INTERNAL


@tagged('post_install', '-at_install', 'access_studio')
class TestAccessStudio(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.group = cls.env['res.groups'].create({'name': 'Studio test resource access'})
        cls.env['ir.model.access'].create({'name': 'Studio test employee permissions',
            'model_id': cls.env['ir.model']._get_id('hr.employee'), 'group_id': cls.group.id,
            'perm_read': True, 'perm_create': True, 'perm_write': True, 'perm_unlink': True})
        cls.ability = cls.env['pb.role.ability'].create({'name': 'Studio test capability', 'technical_key': 'studio-test',
            'area': 'people', 'group_ids': [(6, 0, cls.group.ids)]})
        cls.role = cls.env['pb.role.profile'].create({'name': 'Studio test role', 'area': 'people', 'ability_ids': [(6, 0, cls.ability.ids)]})
        base = cls.env.ref('base.group_user')
        manager = cls.env.ref('biz_access.group_access_manager')
        cls.owner, cls.reviewer, cls.person, cls.other = cls.env['res.users'].with_context(no_reset_password=True).create([
            {'name': 'Studio test ' + n, 'login': 'studio-regression-' + n,
             'company_id': cls.company.id, 'company_ids': [(6, 0, cls.company.ids)],
             'group_ids': [(6, 0, (base | manager if n in ('owner', 'reviewer') else base).ids)]}
            for n in ('owner', 'reviewer', 'person', 'other')])
        cls.access = cls.env['pb.access'].with_user(cls.owner)
        cls.review = cls.env['pb.access'].with_user(cls.reviewer)
        cls.department = cls.env['hr.department'].create({'name': 'Studio test team', 'company_id': cls.company.id})
        cls.employee = cls.env['hr.employee'].create({'name': 'Studio owned employee', 'user_id': cls.person.id,
            'company_id': cls.company.id, 'department_id': cls.department.id, 'work_email': 'private@example.invalid'})
        cls.other_employee = cls.env['hr.employee'].create({'name': 'Studio other employee', 'user_id': cls.other.id, 'company_id': cls.company.id})

    def publish_profile(self, roles=None, auto=False):
        result = self.access.studio_submit_profile('people', {'name': 'Studio profile', 'role_ids': (roles or self.role).ids,
            'owner_id': self.owner.id, 'review_date': str(fields.Date.today() + timedelta(days=90)),
            'auto_department_id': self.department.id if auto else False}, 'Approved team package')
        self.review.studio_decide('people', result['id'], True, 'Independent owner checked the package')
        return self.env['pb.access.profile'].search([('name', '=', 'Studio profile')], order='id desc', limit=1)

    def assign(self, profile, user=None):
        result = self.access.studio_submit_assignment('people', profile.id, (user or self.person).ids, False, 'Team responsibilities')
        self.review.studio_decide('people', result['id'], True, 'Reviewed assignment')
        return self.env['pb.access.membership'].search([('profile_id', '=', profile.id), ('user_id', '=', (user or self.person).id)])

    def policy(self, **updates):
        policy = {'read': 'own', 'create': 'own', 'write': 'own', 'unlink': 'none', 'fields': {'name': 'edit', 'work_email': 'hidden'},
            'create_fields': ['name', 'work_email'], 'export': False, 'archive': False, 'reassign': False,
            'approve': False, 'download': False, 'reveal': False, 'department_ids': [], 'states': [], 'write_states': [], 'match': 'all'}
        policy.update(updates)
        result = self.access.studio_submit_policy('people', self.role.id, self.role.studio_policy_revision,
                                                {'hr.employee': policy}, 'Limit access to assigned work')
        self.review.studio_decide('people', result['id'], True, 'Verified record and field restrictions')
        return policy

    def grant(self):
        self.access.with_context(biz_access_engine_apply=True).grant(self.role.id, self.person.id, 'Test role assignment')

    def test_self_approval_refused(self):
        result = self.access.studio_submit_profile('people', {'name': 'New', 'role_ids': self.role.ids,
            'owner_id': self.owner.id, 'review_date': str(fields.Date.today())}, 'Reason')
        with self.assertRaises(AccessError): self.access.studio_decide('people', result['id'], True, 'Self')
        self.assertEqual(self.env['pb.access.studio.request'].browse(result['id']).state, 'pending')

    def test_approval_required_before_grant(self):
        profile = self.publish_profile()
        result = self.access.studio_submit_assignment('people', profile.id, self.person.ids, False, 'Test')
        self.assertNotIn(self.group, self.person.all_group_ids)
        self.review.studio_decide('people', result['id'], True, 'Independent')
        self.assertIn(self.group, self.person.all_group_ids)
        with self.assertRaises(UserError): self.review.studio_decide('people', result['id'], True, 'Replay')

    def test_profile_removal_preserves_independent_role(self):
        self.grant()
        membership = self.assign(self.publish_profile())
        self.access.studio_review_assignment('people', membership.id, membership.revision, False, 'No longer needed')
        self.assertIn(self.group, self.person.all_group_ids)

    def test_profile_only_removal_revokes_its_groups(self):
        membership = self.assign(self.publish_profile())
        self.access.studio_review_assignment('people', membership.id, membership.revision, False, 'No longer needed')
        self.assertNotIn(self.group, self.person.all_group_ids)

    def test_assigned_profile_cannot_retire(self):
        profile = self.publish_profile(); self.assign(profile)
        with self.assertRaises(UserError): self.access.studio_retire_profile('people', profile.id, profile.revision, 'Retire')

    def test_stale_profile_assignment_refused(self):
        profile = self.publish_profile()
        result = self.access.studio_submit_assignment('people', profile.id, self.person.ids, False, 'Test')
        profile.with_context(_pb_studio=STUDIO).write({'revision': profile.revision + 1})
        with self.assertRaises(UserError): self.review.studio_decide('people', result['id'], True, 'Stale')
        self.assertNotIn(self.group, self.person.all_group_ids)

    def test_stale_policy_refused(self):
        result = self.access.studio_submit_policy('people', self.role.id, self.role.studio_policy_revision, {}, 'First')
        self.policy()
        with self.assertRaises(UserError): self.review.studio_decide('people', result['id'], True, 'Stale')

    def test_rpc_cannot_write_service_storage(self):
        with self.assertRaises(AccessError): self.env['pb.access.profile'].sudo().create({'name': 'Forged'})
        with self.assertRaises(AccessError): self.role.sudo().write({'studio_policy': {}})
        with self.assertRaises(AccessError): self.role.with_context(_pb_studio=True).write({'studio_policy': {}})

    def test_module_owner_ceiling_and_other_module_refused(self):
        self.access.studio_set_owner('people', self.other.id, [], True, 'Limited owner')
        scoped = self.env['pb.access'].with_user(self.other)
        with self.assertRaises(AccessError): scoped.studio_role_policy('people', self.role.id)
        with self.assertRaises(AccessError): scoped.studio_submit_profile('hiring', {}, 'Wrong module')
        self.access.studio_set_owner('people', self.other.id, self.role.ids, True, 'Approved ceiling')
        self.assertEqual(scoped.studio_role_policy('people', self.role.id)['id'], self.role.id)
        # A platform-wide role stays in System even if it includes hiring.
        from odoo.addons.biz_access.models.studio_catalogue import workspace_of
        self.role.area = 'system'
        self.ability.technical_key = 'hiring-test'
        self.assertEqual(workspace_of(self.role), 'system')

    def test_nonowner_only_sees_self(self):
        data = self.env['pb.access'].with_user(self.person).studio_data('people')
        self.assertEqual([r['id'] for r in data['people']], self.person.ids)
        with self.assertRaises(AccessError): self.env['pb.access'].with_user(self.person).studio_explain('people', self.other.id, 'hr.employee')

    def test_scope_filters_search_and_direct_read(self):
        self.grant(); self.policy()
        Employee = self.env['hr.employee'].with_user(self.person)
        self.assertIn(self.employee, Employee.search([('id', 'in', (self.employee | self.other_employee).ids)]))
        self.assertNotIn(self.other_employee, Employee.search([('id', 'in', (self.employee | self.other_employee).ids)]))
        with self.assertRaises(AccessError): Employee.browse(self.other_employee.id).read(['name'])
        with self.assertRaises(AccessError): Employee.browse(self.other_employee.id).write({'name': 'Forbidden'})

    def test_hidden_field_read_and_export_refused(self):
        self.grant(); self.policy()
        record = self.employee.with_user(self.person)
        with self.assertRaises(AccessError): record.read(['work_email'])
        with self.assertRaises(AccessError): record.export_data(['name'])
        with self.assertRaises(AccessError): record.write({'work_email': 'forbidden@example.invalid'})

    def test_facade_sudo_retains_policy(self):
        self.grant(); self.policy()
        record = self.employee.with_user(self.person).sudo()
        self.assertTrue(record.env.su)
        with self.assertRaises(AccessError): _ = record.work_email
        self.assertNotIn(self.other_employee, self.env['hr.employee'].with_user(self.person).sudo().search([('id', 'in', (self.employee | self.other_employee).ids)]))

    def test_archive_and_delete_are_separate(self):
        self.grant(); self.policy()
        with self.assertRaises(AccessError): self.employee.with_user(self.person).write({'active': False})
        with self.assertRaises(AccessError): self.employee.with_user(self.person).unlink()

    def test_field_and_scope_validation(self):
        with self.assertRaises(UserError): self.access.studio_submit_policy('people', self.role.id, 1, {'res.users': {}}, 'Unsafe model')
        with self.assertRaises(UserError): self.policy(fields={'name': 'hidden'})
        with self.assertRaises(UserError): self.policy(read='invented')

    def test_independent_native_grant_is_explained(self):
        self.grant(); self.policy()
        self.person.write({'group_ids': [(4, self.group.id)]})
        self.assertTrue(self.other_employee.with_user(self.person).has_access('read'))
        result = self.access.studio_explain('people', self.person.id, 'hr.employee', self.other_employee.id)
        self.assertTrue(result['allowed'])
        self.assertTrue(any(r['source'] == 'baseline' for r in result['sources']))

    def test_temporary_grant_expiry_preserves_profile(self):
        profile = self.publish_profile(); self.assign(profile)
        result = self.access.studio_submit_extra('people', self.person.id, self.role.id, str(fields.Date.today() + timedelta(days=1)), 'Cover')
        self.review.studio_decide('people', result['id'], True, 'Reviewed cover')
        extra = self.env['pb.access.extra'].search([('user_id', '=', self.person.id)])
        extra.with_context(_pb_studio=STUDIO).write({'date_end': fields.Date.today() - timedelta(days=1)})
        self.env['pb.access']._studio_expire()
        self.assertFalse(extra.active)
        self.assertIn(self.group, self.person.all_group_ids)

    def test_expired_profile_revokes_owned_access(self):
        membership = self.assign(self.publish_profile())
        membership.with_context(_pb_studio=STUDIO).write({'date_end': fields.Date.today() - timedelta(days=1)})
        self.env['pb.access']._studio_expire()
        self.assertFalse(membership.active)
        self.assertNotIn(self.group, self.person.all_group_ids)

    def test_lifecycle_move_removes_only_automatic(self):
        profile = self.publish_profile(auto=True)
        self.employee.write({'department_id': False})
        self.employee.write({'department_id': self.department.id})
        membership = self.env['pb.access.membership'].search([('user_id', '=', self.person.id), ('profile_id', '=', profile.id)])
        self.assertTrue(membership.active)
        self.assertEqual(membership.origin, 'automatic')
        self.employee.write({'department_id': False})
        self.assertFalse(membership.active)
        self.assertNotIn(self.group, self.person.all_group_ids)

    def test_history_immutable(self):
        self.publish_profile()
        event = self.env['pb.access.event'].search([], limit=1)
        with self.assertRaises(UserError): event.sudo().write({'reason': 'Rewrite'})
        with self.assertRaises(UserError): event.sudo().unlink()

    def test_assignment_reason_required(self):
        profile = self.publish_profile()
        with self.assertRaises(UserError): self.access.studio_submit_assignment('people', profile.id, self.person.ids, False, '  ')

    def test_profile_assignment_visible_in_passport(self):
        self.assign(self.publish_profile())
        passport = self.access.passport(self.person.id)
        self.assertIn(self.role.id, [r['profile_id'] for r in passport['roles']])
        self.assertIn(self.person, self.role._holder_users())

    def test_field_permission_is_bound_to_matching_records(self):
        second_department = self.env['hr.department'].create({'name': 'Studio second team', 'company_id': self.company.id})
        self.other_employee.write({'department_id': second_department.id, 'work_email': 'second@example.invalid'})
        second = self.env['pb.role.profile'].create({'name': 'Second scoped role', 'area': 'people', 'ability_ids': [(6, 0, self.ability.ids)]})
        self.grant(); self.policy(read='all', department_ids=self.department.ids)
        rule = {'read': 'all', 'create': 'none', 'write': 'none', 'unlink': 'none',
                'fields': {'work_email': 'view'}, 'department_ids': second_department.ids}
        request = self.access.studio_submit_policy('people', second.id, second.studio_policy_revision, {'hr.employee': rule}, 'Separate department')
        self.review.studio_decide('people', request['id'], True, 'Separate scope checked')
        self.access.with_context(biz_access_engine_apply=True).grant(second.id, self.person.id, 'Second responsibility')
        with self.assertRaises(AccessError): self.employee.with_user(self.person).read(['work_email'])
        self.assertEqual(self.other_employee.with_user(self.person).read(['work_email'])[0]['work_email'], 'second@example.invalid')
        with self.assertRaises(AccessError): _ = self.employee.with_user(self.person).sudo().work_email
        self.assertFalse(self.access.studio_explain('people', self.person.id, 'hr.employee', self.employee.id, field_name='work_email')['allowed'])
        self.assertTrue(self.access.studio_explain('people', self.person.id, 'hr.employee', self.other_employee.id, field_name='work_email')['allowed'])

    def test_team_scope_uses_reporting_hierarchy(self):
        self.other_employee.write({'parent_id': self.employee.id})
        self.grant(); self.policy(read='team')
        records = self.env['hr.employee'].with_user(self.person).search([('id', 'in', (self.employee | self.other_employee).ids)])
        self.assertEqual(set(records.ids), set((self.employee | self.other_employee).ids))

    def test_company_boundary_survives_all_scope(self):
        company = self.env['res.company'].create({'name': 'Studio second company'})
        employee = self.env['hr.employee'].create({'name': 'Outside company', 'company_id': company.id})
        self.grant(); self.policy(read='all')
        with self.assertRaises(AccessError): employee.with_user(self.person).read(['name'])
        with self.assertRaises(AccessError): _ = employee.with_user(self.person).sudo().name
        self.assertFalse(self.env['hr.employee'].with_user(self.person).search([('id', '=', employee.id)]))

    def test_reasoned_reveal_is_for_signed_in_user_and_audited(self):
        self.ability.write({'group_ids': [(4, self.env.ref('hr.group_hr_user').id)]})
        self.employee.write({'private_email': 'sensitive@example.invalid'})
        self.grant(); self.policy(fields={'name': 'edit', 'private_email': 'masked'}, reveal=True)
        record = self.employee.with_user(self.person)
        with self.assertRaises(AccessError): record.read(['private_email'])
        with self.assertRaises(AccessError): _ = record.sudo().private_email
        with self.assertRaises(UserError): self.env['pb.access'].with_user(self.person).studio_reveal('hr.employee', record.id, 'private_email', '')
        result = self.env['pb.access'].with_user(self.person).studio_reveal('hr.employee', record.id, 'private_email', 'Verify contact with employee')
        self.assertEqual(result['value'], 'sensitive@example.invalid')
        event = self.env['pb.access.event'].browse(result['receipt'])
        self.assertEqual(event.actor_id, self.person)
        self.assertNotIn('sensitive@example.invalid', str(event.details))
        with self.assertRaises(AccessError): record.read(['private_email'])

    def test_create_input_is_separate_from_edit_permission(self):
        self.ability.write({'group_ids': [(4, self.env.ref('hr.group_hr_user').id)]})
        self.employee.write({'user_id': False})
        self.grant(); self.policy(fields={'name': 'edit', 'mobile_phone': 'view'}, create_fields=['name', 'mobile_phone'])
        record = self.env['hr.employee'].with_user(self.person).create({'name': 'Created by profile', 'user_id': self.person.id,
            'company_id': self.company.id, 'mobile_phone': '0123456789'})
        self.assertEqual(record.mobile_phone, '0123456789')
        with self.assertRaises(AccessError): record.write({'mobile_phone': '999'})

    def test_attachment_download_has_its_own_control(self):
        attachment = self.env['ir.attachment'].create({'name': 'Studio evidence.txt', 'res_model': 'hr.employee',
            'res_id': self.employee.id, 'raw': b'private evidence', 'mimetype': 'text/plain'})
        self.grant(); self.policy(download=False)
        with self.assertRaises(AccessError): attachment.with_user(self.person).read(['raw'])
        self.policy(download=True)
        attachment.with_user(self.person)._studio_download_check()

    def test_owner_revoked_after_submission_cannot_apply(self):
        self.access.studio_set_owner('people', self.other.id, self.role.ids, True, 'Module owner')
        scoped = self.env['pb.access'].with_user(self.other)
        profile = self.publish_profile()
        request = scoped.studio_submit_assignment('people', profile.id, self.person.ids, False, 'Assignment')
        self.access.studio_set_owner('people', self.other.id, [], False, 'Owner removed')
        with self.assertRaises(AccessError): self.review.studio_decide('people', request['id'], True, 'No longer authorized')
        self.assertNotIn(self.group, self.person.all_group_ids)

    def test_referenced_role_change_invalidates_assignment_review(self):
        profile = self.publish_profile()
        request = self.access.studio_submit_assignment('people', profile.id, self.person.ids, False, 'Assign latest package')
        self.policy()
        with self.assertRaises(UserError): self.review.studio_decide('people', request['id'], True, 'Role changed')
        self.assertNotIn(self.group, self.person.all_group_ids)

    def test_payroll_conflict_includes_direct_baseline_grants(self):
        officer = self.env.ref('pb_hr_payroll_base.group_payroll_base_officer', raise_if_not_found=False)
        final = self.env['pb.role.profile'].search([('ability_ids.technical_key', '=', 'payroll-final-approver')], limit=1)
        if not officer or not final:
            self.skipTest('Payroll catalogue is not installed')
        self.person.write({'group_ids': [(4, officer.id)]})
        self.assertTrue(self.access._studio_conflicts(self.person, final))
