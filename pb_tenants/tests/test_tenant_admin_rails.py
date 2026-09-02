# -*- coding: utf-8 -*-
"""ACCESS P5 — the guards on the flip, and only the guards.

WHAT CAN AND CANNOT BE TESTED HERE. The rails themselves write to ANOTHER
database — that is the whole shape of provisioning — so the part that can be
exercised in a transaction is the part that decides whether to go near one at
all. That part is also the part where a mistake is unrecoverable: demoting the
platform's own administrator would lock the owner out of the entire fleet, and
demoting the golden template's would ship the demotion to every future clone
through the back door instead of through provisioning.

So every refusal has a test, the dry run has a test, and the writing half is
proven on a throwaway clone at deploy time and reported there.
"""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_tenants.models.service import RAILS_DEFAULTS


@tagged('post_install', '-at_install')
class TestTenantAdminRailGuards(TransactionCase):

    def setUp(self):
        super().setUp()
        self.svc = self.env['pb.tenants']

    # ------------------------------------------------------------- refusals
    def test_it_refuses_the_platforms_own_database(self):
        with self.assertRaises(UserError):
            self.svc.apply_tenant_admin_rails(self.env.cr.dbname)

    def test_it_refuses_the_golden_template(self):
        with self.assertRaises(UserError):
            self.svc.apply_tenant_admin_rails(self.svc._template_db())

    def test_the_never_list_cannot_be_edited_down_to_nothing(self):
        """Emptying the parameter must not open the two that matter."""
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenants.tenant_admin_rails_never', '')
        never = self.svc._never_flip()
        self.assertIn(self.env.cr.dbname, never)
        self.assertIn(self.svc._template_db(), never)

    def test_it_refuses_something_that_is_not_a_database_name(self):
        for bad in ('', '   ', 'no spaces here', 'semi;colon', '../escape'):
            with self.assertRaises(UserError):
                self.svc.apply_tenant_admin_rails(bad)

    def test_it_refuses_a_database_that_is_not_on_this_server(self):
        with self.assertRaises(UserError):
            self.svc.apply_tenant_admin_rails('pb_no_such_database_p5')

    # -------------------------------------------------------------- switches
    def test_the_rails_are_armed_by_default_and_the_switch_stands_them_down(self):
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('pb_tenants.tenant_admin_rails', '')
        self.assertTrue(self.svc._rails_armed(),
                        'the rails must be on unless somebody says otherwise')
        for off in ('0', 'off', 'OFF', 'false', 'no'):
            icp.set_param('pb_tenants.tenant_admin_rails', off)
            self.assertFalse(self.svc._rails_armed(), off)
        for on in ('1', 'on', 'yes', 'anything else'):
            icp.set_param('pb_tenants.tenant_admin_rails', on)
            self.assertTrue(
                self.svc._rails_armed(),
                'a value nobody recognises must leave the rail ARMED: "%s"' % on)

    def test_the_owners_own_account_is_protected_out_of_the_box(self):
        self.assertIn('ash@biztinct.com', self.svc._protected_logins())
        self.assertIn(
            'ash@biztinct.com',
            RAILS_DEFAULTS['pb_tenants.tenant_admin_rails_protect'],
            'the protected list is a DEFAULT in code; a shipped record would '
            'freeze whatever a test run left behind')

    # ------------------------------------------------------- the rails, dry
    def test_a_protected_login_is_left_alone(self):
        said = []
        user = self.env['res.users'].create({
            'name': 'Protected', 'login': 'ash@biztinct.com.p5probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenants.tenant_admin_rails_protect',
            'ash@biztinct.com.p5probe')
        report = self.svc._apply_rails_to(
            self.env, user, lambda line, level='info': said.append(line))
        self.assertFalse(report['applied'])
        self.assertIn('protected', report['reason'].lower())
        self.assertEqual(
            set(user.group_ids.ids), {self.env.ref('base.group_user').id},
            'a protected account had its permissions changed')

    def test_the_switch_being_off_stops_the_rails_dead(self):
        said = []
        self.env['ir.config_parameter'].sudo().set_param(
            'pb_tenants.tenant_admin_rails', 'off')
        user = self.env['res.users'].create({
            'name': 'Untouched', 'login': 'p5_untouched',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('base.group_system').id])],
        })
        before = set(user.group_ids.ids)
        report = self.svc._apply_rails_to(
            self.env, user, lambda line, level='info': said.append(line))
        self.assertFalse(report['applied'])
        self.assertEqual(set(user.group_ids.ids), before)
        self.assertTrue(user._is_system())

    def test_a_dry_run_writes_nothing(self):
        said = []
        role = self.env.ref('pb_vendor_access.role_tenant_administrator',
                            raise_if_not_found=False)
        if not role:
            self.skipTest('the access module is not on this database')
        user = self.env['res.users'].create({
            'name': 'Dry run', 'login': 'p5_dry_run',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('base.group_system').id])],
        })
        before = set(user.group_ids.ids)
        report = self.svc._apply_rails_to(
            self.env, user, lambda line, level='info': said.append(line),
            dry_run=True)
        self.assertFalse(report['applied'])
        self.assertEqual(set(user.group_ids.ids), before,
                         'a dry run wrote to the account')
        self.assertTrue(user._is_system())
        self.assertTrue(
            report['would_remove'],
            'a dry run that names nothing it would take away is not a dry run')

    def test_the_rails_demote_and_prove_it(self):
        """The writing half, against a throwaway account in this database.

        It is the same code path provisioning runs against a fresh clone; only
        the database is different, and this one is rolled back.
        """
        role = self.env.ref('pb_vendor_access.role_tenant_administrator',
                            raise_if_not_found=False)
        if not role:
            self.skipTest('the access module is not on this database')
        said = []
        user = self.env['res.users'].create({
            'name': 'Would-be tenant admin', 'login': 'p5_flip_probe',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('base.group_system').id])],
        })
        self.assertTrue(user._is_system())
        report = self.svc._apply_rails_to(
            self.env, user, lambda line, level='info': said.append(line))
        self.assertTrue(report['applied'], report['reason'])
        user.invalidate_recordset()
        self.assertFalse(user._is_system(),
                         'the account still holds the system administrator '
                         'permission after the rails ran')
        self.assertTrue(set(role.group_ids.ids) <= set(user.all_group_ids.ids),
                        'the account was demoted without being given the role')
        self.assertIn(user, role.holders())
        self.assertNotEqual(report['before'], report['after'])

    def test_the_recovery_account_is_kept_and_cannot_be_logged_into(self):
        role = self.env.ref('pb_vendor_access.role_tenant_administrator',
                            raise_if_not_found=False)
        if not role:
            self.skipTest('the access module is not on this database')
        said = []
        user = self.env['res.users'].create({
            'name': 'Would-be tenant admin two', 'login': 'p5_flip_probe2',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('base.group_system').id])],
        })
        self.svc._apply_rails_to(
            self.env, user, lambda line, level='info': said.append(line))
        login = self.svc._rails_param('pb_tenants.break_glass_login')
        glass = self.env['res.users'].sudo().with_context(
            active_test=False).search([('login', '=', login)], limit=1)
        self.assertTrue(glass, 'no recovery account was kept')
        self.assertTrue(
            glass.active,
            'it has to be switched on: Odoo refuses to leave a database with '
            'no active administrator, and would refuse the demotion itself')
        self.assertTrue(glass.has_group('base.group_system'),
                        'a recovery account that cannot administer is not one')
        self.assertFalse(glass.partner_id.email,
                         'with an email address on it, "forgot my password" '
                         'becomes a way in')
        self.env.cr.execute(
            'SELECT password FROM res_users WHERE id = %s', (glass.id,))
        self.assertFalse(
            self.env.cr.fetchone()[0],
            'a password was set on the recovery account — there must be no '
            'secret to store, to leak or to guess')
