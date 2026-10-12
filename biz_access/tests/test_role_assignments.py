from datetime import timedelta
from unittest.mock import patch
from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.biz_access.models.role_assignments import INTERNAL


@tagged('post_install', '-at_install', 'role_assignment')
class TestRoleAssignments(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.access = cls.env['pb.access'].with_context(biz_access_engine_apply=True)
        cls.g1 = cls.env['res.groups'].create({'name': 'Assignment test read'})
        cls.g2 = cls.env['res.groups'].create({'name': 'Assignment test edit'})
        area = cls.env['pb.role.profile']._fields['area'].selection(cls.env['pb.role.profile'])[0][0]
        cls.a1 = cls.env['pb.role.ability'].create({'name':'Test read','technical_key':'assignment-test-read', 'area':area, 'group_ids':[(6,0,cls.g1.ids)]})
        cls.a2 = cls.env['pb.role.ability'].create({'name':'Test edit','technical_key':'assignment-test-edit', 'area':area, 'group_ids':[(6,0,cls.g2.ids)]})
        cls.role = cls.env['pb.role.profile'].create({'name':'Assignment test role', 'area':area, 'ability_ids':[(6,0,cls.a1.ids)]})
        cls.other = cls.env['pb.role.profile'].create({'name':'Shared assignment test role', 'area':area, 'ability_ids':[(6,0,cls.a2.ids)]})
        cls.people = cls.env['res.users'].with_context(no_reset_password=True).create([
            {'name':'Assignment user %s'%i,'login':'assignment-test-%s'%i,
             'group_ids':[(6,0,cls.env.ref('base.group_user').ids)]} for i in range(3)])

    def grant(self, role, user):
        return self.access.grant(role.id, user.id, 'Test assignment')

    def edit(self, ids, role=None, revision=None):
        role = role or self.role
        return self.access.update_role(role.id, revision or role.revision, role.name,
            role.description, role.area, ids, 'Test role change')

    def loan(self, user, lender=None):
        row = self.env['pb.access.delegation'].create({'delegator_user_id':(lender or self.people[0]).id,
            'delegate_user_id':user.id, 'profile_ids':[(6,0,self.role.ids)], 'kind':'temporary',
            'date_start':fields.Date.today(), 'date_end':fields.Date.today()+timedelta(days=3), 'reason':'Test loan'})
        row.action_activate()
        return row

    def test_every_assigned_user_follows_edit(self):
        for user in self.people: self.grant(self.role,user)
        self.edit((self.a1|self.a2).ids)
        self.assertEqual(self.role.holder_count,3)
        for user in self.people: self.assertIn(self.g2,user.all_group_ids)
        self.edit(self.a1.ids)
        for user in self.people: self.assertNotIn(self.g2,user.all_group_ids)

    def test_shared_role_retains_access(self):
        user=self.people[0]
        self.grant(self.role,user); self.grant(self.other,user)
        self.edit((self.a1|self.a2).ids); self.edit(self.a1.ids)
        self.assertIn(self.g2,user.all_group_ids)
        self.access.remove(self.other.id,user.id,'Remove shared role')
        self.assertNotIn(self.g2,user.all_group_ids)

    def test_repeated_migration_preserves_a_later_direct_grant(self):
        lender,recipient=self.people[:2]
        self.grant(self.role,lender)
        loan=self.loan(recipient,lender)
        recipient.write({'group_ids':[(4,self.g1.id)]})
        self.access._migrate_assignments(include_memberships=True)
        loan.action_revoke('End after repeat migration')
        self.assertIn(self.g1,recipient.all_group_ids)

    def test_equivalent_permission_is_not_an_assignment(self):
        self.people[0].write({'group_ids':[(4,self.g1.id)]})
        self.assertEqual(self.role.holder_count,0)
        self.assertGreaterEqual(self.role.equivalent_count,1)
        board=self.access.with_user(self.people[0]).get_board()
        row=next(r for r in board['profiles'] if r['id']==self.role.id)
        self.assertFalse(row['i_hold'])
        self.edit((self.a1|self.a2).ids)
        self.assertNotIn(self.g2,self.people[0].all_group_ids)

    def test_overlap_and_permanent_conversion(self):
        lender,recipient,second=self.people
        self.grant(self.role,lender); self.grant(self.role,second)
        one=self.loan(recipient,lender); two=self.loan(recipient,second)
        one.action_revoke('First ends')
        self.assertIn(self.g1,recipient.all_group_ids)
        self.grant(self.role,recipient)
        two.action_revoke('Second ends')
        self.assertIn(self.g1,recipient.all_group_ids)

    def test_direct_grant_during_loan_survives(self):
        self.grant(self.role,self.people[0]); loan=self.loan(self.people[1])
        self.people[1].write({'group_ids':[(4,self.g1.id)]})
        loan.action_revoke('Ends')
        self.assertIn(self.g1,self.people[1].all_group_ids)

    def test_group_side_direct_grant_during_loan_survives(self):
        self.grant(self.role,self.people[0]); loan=self.loan(self.people[1])
        self.g1.write({'user_ids':[(4,self.people[1].id)]})
        loan.action_revoke('Ends')
        self.assertIn(self.g1,self.people[1].all_group_ids)

    def test_implied_permission_removed_with_its_last_source(self):
        self.g1.write({'implied_ids':[(4,self.g2.id)]})
        self.grant(self.role,self.people[0])
        self.assertIn(self.g2,self.people[0].all_group_ids)
        self.g1.write({'implied_ids':[(3,self.g2.id)]})
        self.assertNotIn(self.g2,self.people[0].all_group_ids)

    def test_temporary_expansion_is_pinned_and_reduction_applies(self):
        self.grant(self.role,self.people[0]); loan=self.loan(self.people[1])
        self.edit((self.a1|self.a2).ids)
        self.assertNotIn(self.g2,self.people[1].all_group_ids)
        self.edit(self.a2.ids)
        self.assertNotIn(self.g1,self.people[1].all_group_ids)
        loan.action_revoke('Ends')

    def test_stale_revision_cannot_overwrite(self):
        revision=self.role.revision
        self.edit((self.a1|self.a2).ids)
        with self.assertRaises(UserError): self.edit(self.a1.ids,revision=revision)
        self.assertIn(self.a2,self.role.ability_ids)

    def test_no_reason_no_publish(self):
        with self.assertRaises(UserError):
            self.access.update_role(self.role.id,self.role.revision,self.role.name,'',self.role.area,self.a2.ids,'')

    def test_failure_rolls_back_role_and_all_users(self):
        for user in self.people: self.grant(self.role,user)
        revision=self.role.revision
        model=type(self.people)
        original=model._pb_reconcile_access
        def fail(users):
            original(users[:1])
            raise UserError('Injected reconciliation failure')
        with self.assertRaises(UserError):
            with self.env.cr.savepoint():
                with patch.object(model,'_pb_reconcile_access',fail): self.edit(self.a2.ids)
        self.assertEqual(self.role.revision,revision)
        self.assertEqual(self.role.ability_ids,self.a1)
        for user in self.people: self.assertNotIn(self.g2,user.all_group_ids)

    def test_history_is_immutable_and_restore_is_new_version(self):
        self.grant(self.role,self.people[0]); self.edit((self.a1|self.a2).ids)
        initial=self.env['pb.role.change'].search([('profile_id','=',self.role.id)],order='id',limit=1)
        self.assertEqual(initial.after['ability_ids'],self.a1.ids)
        change=self.env['pb.role.change'].search([('profile_id','=',self.role.id)],limit=1)
        with self.assertRaises(UserError): change.write({'reason':'Rewrite'})
        with self.assertRaises(UserError): change.unlink()
        self.edit(self.a1.ids)
        self.access.restore_role_version(change.id,self.role.revision,'Restore approved version')
        self.assertIn(self.a2,self.role.ability_ids)

    def test_reader_and_forged_context_cannot_write(self):
        user=self.people[0]
        with self.assertRaises(AccessError): self.access.with_user(user).role_editor(self.role.id)
        with self.assertRaises(AccessError):
            user.with_user(user).with_context(_pb_access_internal=True).write({'pb_access_baseline':[self.g2.id]})
        with self.assertRaises(AccessError):
            self.env['pb.role.assignment'].with_user(user).with_context(_pb_access_internal=True).create({'user_id':user.id,'profile_id':self.role.id})

    def test_raw_archive_and_ability_edits_have_guards(self):
        self.grant(self.role,self.people[0])
        with self.assertRaises(UserError): self.role.write({'active':False})
        with self.assertRaises(UserError): self.a1.write({'group_ids':[(6,0,self.g2.ids)]})

    def test_administrative_removal_is_not_readded(self):
        user=self.people[0]; self.grant(self.role,user)
        user.write({'group_ids':[(3,self.g1.id)]})
        self.assertNotIn(self.g1,user.all_group_ids)
        self.assertFalse(self.access._assignments(self.role,user))

    def test_unknown_preview_fails_closed(self):
        row={'key':'unknown-test','groups':['missing.role'],'action':{'tag':'missing'}}
        self.assertFalse(self.access.surface_access([row])['unknown-test']['allowed'])

    def test_inactive_user_follows_role_on_reactivation(self):
        user=self.people[0]; self.grant(self.role,user)
        user.write({'active':False}); self.edit(self.a2.ids); user.write({'active':True})
        self.assertIn(self.g2,user.all_group_ids)
        self.assertNotIn(self.g1,user.all_group_ids)

    def test_menu_override_is_preserved_on_upgrade(self):
        section=self.env['pb.sidebar.section'].create({'name':'Assignment test','technical_key':'assignment-test'})
        item=self.env['pb.sidebar.item'].create({'name':'Test gate','section_id':section.id})
        item.write({'role_ids':[(6,0,self.role.ids)],'active':False})
        item.with_context(install_mode=True).write({'role_ids':[(6,0,[])],'active':True})
        self.assertIn(self.role,item.role_ids); self.assertFalse(item.active)

    def test_demo_migration_preserves_effective_permissions_and_is_idempotent(self):
        if self.env.ref('pb_demo.group_payobook_demo',raise_if_not_found=False):
            self.skipTest('The real Demo cohort is verified in the deployment rehearsal')
        self.env['ir.model.data'].create({'module':'pb_demo','name':'group_payobook_demo',
            'model':'res.groups','res_id':self.g1.id})
        self.role.write({'group_id':self.g1.id})
        self.people[0].write({'group_ids':[(4,self.g1.id),(4,self.g2.id)]})
        self.people[1].write({'group_ids':[(4,self.g1.id)]})
        before={u.id:set(u.all_group_ids.ids) for u in self.people}
        self.access._migrate_assignments(include_memberships=True)
        markers=set(self.role.sudo().membership_group_id.ids)
        for user in self.people: self.assertEqual(before[user.id],set(user.all_group_ids.ids)-markers)
        count=len(self.access._assignments(self.role))
        self.access._migrate_assignments(include_memberships=True)
        self.assertEqual(len(self.access._assignments(self.role)),count)
        self.assertEqual(count,2)
        self.edit(self.a2.ids)
        self.assertIn(self.g2,self.people[0].all_group_ids)
        self.assertIn(self.g2,self.people[1].all_group_ids)
