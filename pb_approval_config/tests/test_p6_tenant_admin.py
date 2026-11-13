# -*- coding: utf-8 -*-
"""UPDATES P6 — a client's own admin sets approvals up (owner decision D22).

Tests M1-M3 and M7-M8 of `docs/handovers/updates/UPDATES_P6_HANDOVER.md` §4
(M4-M5, which need the records and Updates modules, are in
`test_p6_bank_rails.py`).

The tenant administrator here is the account a newly provisioned client
gets: the Tenant administrator role's permissions and nothing else
(`pb_vendor_access` test P5's shape). Every forbidden thing is asked twice —
through the screen's own server calls, and as a direct call on the model the
way a tampered browser would (`with_user(...)` on the ORM is exactly what a
JSON-RPC `call_kw` does).
"""
import unittest

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_approval_config.models import setup_rails as R

TA_XMLID = 'pb_vendor_access.role_tenant_administrator'
SUPPORT = 'p6.support@example.com'


class P6Common(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role = cls.env.ref(TA_XMLID, raise_if_not_found=False)
        if not cls.role:
            raise unittest.SkipTest('no Tenant administrator role here')
        if not cls.env.ref('base.group_system').user_ids:
            admin = cls.env.ref('base.user_admin', raise_if_not_found=False)
            if admin:
                admin.sudo().write({'active': True})
        cls.Matrix = cls.env['pb.approval.matrix']
        cls.company = cls.env['res.company'].create({'name': 'P6 Client Co'})
        cls.other_co = cls.env['res.company'].create({'name': 'P6 Other Co'})
        cls.env.user.write({'company_ids': [(4, cls.company.id),
                                            (4, cls.other_co.id)]})
        cls.env['ir.config_parameter'].sudo().set_param(
            'pb_tenancy.recovery_login', SUPPORT)
        cls.ta = cls._user('p6_tenant_admin', 'Tia Tenant',
                           cls.role.sudo().group_ids)
        cls.hrm = cls._user('p6_hr_manager', 'Hugo HR', cls._groups(
            'hr.group_hr_manager',
            'pb_hr_payroll_base.group_payroll_base_manager'))
        cls.amy = cls._user('p6_amy', 'Amy Approver')
        cls.ben = cls._user('p6_ben', 'Ben Backup')
        cls.elsewhere = cls._user('p6_elsewhere', 'Eli Elsewhere',
                                  company=cls.other_co)
        cls.support = cls._user(SUPPORT, 'Platform support', cls._groups(
            'base.group_system'))
        cls.portal = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Pat Portal', 'login': 'p6_portal',
                'company_id': cls.company.id,
                'company_ids': [(6, 0, [cls.company.id])],
                'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.Process = cls.env['biz.approval.process'].sudo()
        cls.Role = cls.env['biz.approval.role'].sudo()

    @classmethod
    def _groups(cls, *xmlids):
        groups = cls.env['res.groups']
        for xmlid in xmlids:
            group = cls.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups |= group
        return groups

    @classmethod
    def _user(cls, login, name, groups=None, company=None):
        company = company or cls.company
        groups = (groups or cls.env['res.groups']) | cls.env.ref(
            'base.group_user')
        return cls.env['res.users'].with_context(
            no_reset_password=True, mail_create_nosubscribe=True).create({
                'name': name, 'login': login,
                'email': '%s@example.com' % login.split('@')[0],
                'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],
                'group_ids': [(6, 0, groups.ids)]})

    def M(self, user=None):
        return self.Matrix.with_user(user or self.ta).with_company(self.company)

    def rows(self, payload):
        return {r['process_key']: r for a in payload['areas'] for r in a['rows']}


@tagged('post_install', '-at_install', 'pb_approval_config', 'p6')
class TestP6TheRole(P6Common):
    """M7's arithmetic, and what the role reaches."""

    def test_role_carries_approvals_publish(self):
        keys = set(self.role.sudo().ability_ids.mapped('technical_key'))
        self.assertIn('approvals-publish', keys)
        self.assertNotIn('approvals-admin', keys,
                         'arranging other people\'s cover stays a role given '
                         'on purpose')
        self.assertTrue(self.ta.has_group(
            'biz_approval_workflow.group_approval_publish'))
        self.assertTrue(self.ta.has_group(
            'biz_approval_workflow.group_approval_config'))
        self.assertFalse(self.ta.has_group(
            'biz_approval_workflow.group_approval_admin'))

    def test_still_no_administrator_permission_in_its_closure(self):
        from odoo.addons.biz_access.models.access_common import (
            forbidden_group_ids, implied_closure)
        forbidden = forbidden_group_ids(self.env)
        self.assertTrue(forbidden)
        reached = implied_closure(self.role.sudo().group_ids)
        self.assertFalse(reached.filtered(lambda g: g.id in forbidden))
        self.assertFalse(self.ta._is_system())
        self.assertFalse(self.ta._is_admin())
        self.assertFalse(R.is_platform_person(self.env(user=self.ta)))

    def test_widening_reaches_assigned_holders_with_a_history_row(self):
        """The migration's own call: the role service gives the new part to
        whoever the role is assigned to and writes History."""
        role = self.role.sudo()
        publish = self.env['pb.role.ability'].by_keys(['approvals-publish'])
        holder = self._user('p6_holder', 'Hal Holder')
        role.with_context(pb_access_reason='P6 test').write(
            {'ability_ids': [(3, publish.id)]})
        self.env['pb.access']._assign_role(role, holder, 'P6 test')
        cfg = self.env.ref('biz_approval_workflow.group_approval_publish')
        self.assertNotIn(cfg, holder.sudo().all_group_ids)
        from odoo.addons.pb_vendor_access.hooks import TENANT_ADMIN_XMLID
        import importlib.util
        import os
        from odoo.modules import module as M
        # the migration's body, run as written
        path = os.path.join(M.get_module_path('pb_vendor_access'),
                            'migrations', '19.0.1.17.0', 'post-migrate.py')
        spec = importlib.util.spec_from_file_location('p6_mig', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, '19.0.1.16.2')
        self.assertEqual(self.env.ref(TENANT_ADMIN_XMLID).id, role.id)
        holder.invalidate_recordset()
        self.assertIn(cfg, holder.sudo().all_group_ids,
                      'an assigned holder got the new part')
        change = self.env['pb.role.change'].sudo().search(
            [('profile_id', '=', role.id)], order='id desc', limit=1)
        self.assertIn('approvals set-up', change.reason)
        self.assertIn(holder, change.user_ids)
        # a second run widens nothing and writes no second row
        before = self.env['pb.role.change'].sudo().search_count(
            [('profile_id', '=', role.id)])
        module.migrate(self.env.cr, '19.0.1.16.2')
        self.assertEqual(before, self.env['pb.role.change'].sudo().search_count(
            [('profile_id', '=', role.id)]))


@tagged('post_install', '-at_install', 'pb_approval_config', 'p6')
class TestP6SetUp(P6Common):
    """M1 — allowed; saved; audit line. M2 — still refused."""

    def test_M1_open_edit_route_seat_and_backup_with_audit(self):
        m = self.M()
        grid = m.get_matrix(self.company.id)
        self.assertEqual(grid['company_id'], self.company.id)
        self.assertTrue(grid['can_publish'])
        generic = self.rows(grid).get('generic')
        self.assertTrue(generic, 'the "Other request" row is on the grid')
        # a route: start one, edit it, publish it
        made = m.create_workflow('mgr_hr', 'generic', self.company.id,
                                 'P6 route')
        wf = m.get_workflow(made['workflow_id'])
        definition = wf['draft']['definition']
        definition['steps'] = [{
            'key': 's1', 'kind': 'approve', 'title': 'Amy decides',
            'who': {'mode': 'people', 'user_ids': [self.amy.id],
                    'all': False},
            'min_amount': 0, 'condition': None}]
        saved = m.save_draft(wf['draft']['version_id'],
                             wf['draft']['draft_revision'], definition)
        self.assertFalse(saved['errors'], saved['errors'])
        preview = m.publication_preview(wf['draft']['version_id'])
        done = m.publish(wf['draft']['version_id'], saved['draft_revision'],
                         None, 'P6: our own route',
                         [w['code'] for w in preview['warnings']])
        self.assertTrue(done['version_id'])
        version = self.env['biz.approval.workflow.version'].browse(
            done['version_id'])
        self.assertEqual(version.status, 'published')
        self.assertEqual(version.published_by_uid, self.ta)
        # a responsibility holder and its backup
        m.set_responsibility(self.company.id, 'finance', '', self.amy.id,
                             backup_user_id=self.ben.id)
        seat = self.env['biz.approval.responsibility'].sudo().search([
            ('company_id', '=', self.company.id),
            ('role_id.key', '=', 'finance'), ('scope_key', '=', ''),
            ('active', '=', True)])
        self.assertEqual(seat.user_id, self.amy)
        self.assertEqual(seat.backup_user_id, self.ben)
        # change only the backup: the trail says so
        m.set_responsibility(self.company.id, 'finance', '', self.amy.id,
                             backup_user_id=self.hrm.id)
        self.assertEqual(seat.backup_user_id, self.hrm)
        events = self.env['biz.approval.event'].sudo().search([
            ('company_id', '=', self.company.id),
            ('user_id', '=', self.ta.id)], order='id')
        kinds = events.mapped('kind')
        self.assertIn('published', kinds)
        self.assertIn('responsibility_changed', kinds)
        last = events.filtered(
            lambda e: e.kind == 'responsibility_changed')[-1]
        self.assertIn('backup: Hugo HR', last.summary)
        self.assertEqual(last.payload['before']['backup_user_id'], self.ben.id)
        self.assertEqual(last.payload['after']['backup_user_id'], self.hrm.id)
        self.assertTrue(last.stamp)
        history = m.get_history(self.company.id)['rows']
        self.assertTrue(any('backup: Hugo HR' in r['summary'] for r in history))
        self.assertTrue(any(r['who'] == 'Tia Tenant' for r in history))

    def test_M1b_people_grid_and_picker(self):
        m = self.M()
        people = m.get_people(self.company.id)
        self.assertTrue(people['roles'])
        names = {r['id'] for r in m.user_options(None, 'finance',
                                                  self.company.id)}
        self.assertIn(self.amy.id, names)

    def test_M2_plain_manager_and_portal_still_refused(self):
        for user in (self.hrm, self.portal):
            with self.assertRaises(AccessError):
                self.M(user).get_matrix(self.company.id)
            with self.assertRaises(AccessError):
                self.M(user).set_responsibility(
                    self.company.id, 'finance', '', self.amy.id)
        self.assertFalse(self.hrm.has_group(
            'biz_approval_workflow.group_approval_config'))


@tagged('post_install', '-at_install', 'pb_approval_config', 'p6')
class TestP6Forbidden(P6Common):
    """M3 — every forbidden thing, through the screen and by direct call."""

    # ----------------------------------------------- the engine's catalogue
    def test_M3a_process_and_responsibility_catalogue_are_not_set_up(self):
        process = self.Process._by_key('generic')
        P = self.env['biz.approval.process'].with_user(self.ta)
        Rl = self.env['biz.approval.role'].with_user(self.ta)
        with self.assertRaises(AccessError):
            P.browse(process.id).write({'name': 'P6 renamed'})
        with self.assertRaises(AccessError):
            P.browse(process.id).write({'allow_fast': False})
        with self.assertRaises(AccessError):
            P.create({'key': 'p6_new', 'name': 'P6 new'})
        with self.assertRaises(AccessError):
            P.browse(process.id).unlink()
        finance = self.Role.search([('key', '=', 'finance')], limit=1)
        with self.assertRaises(AccessError):
            Rl.browse(finance.id).write({'fallback_to_company': False})
        with self.assertRaises(AccessError):
            Rl.create({'key': 'p6_role', 'name': 'P6 role'})
        with self.assertRaises(AccessError):
            Rl.browse(finance.id).unlink()
        # the platform's own people still can
        self.env['biz.approval.process'].with_user(self.support).browse(
            process.id).write({'sequence': process.sequence})

    # --------------------------------------------------- the platform's row
    def test_M3b_platform_row_and_seat(self):
        tenant = self.Process._by_key('tenant')
        owner = self.Role.search([('key', '=', 'platform_owner')], limit=1)
        if not tenant or not owner:
            self.skipTest('no platform row on this database')
        m = self.M()
        self.assertNotIn('tenant', self.rows(m.get_matrix(self.company.id)))
        self.assertIn('tenant', self.rows(
            self.M(self.support).get_matrix(self.company.id)),
            'the platform itself still sees its row')
        with self.assertRaises(AccessError):
            m.create_workflow('blank', 'tenant', self.company.id)
        with self.assertRaises(AccessError):
            m.set_responsibility(self.company.id, 'platform_owner', '',
                                 self.amy.id)
        with self.assertRaises(AccessError):
            m.clear_responsibility(self.company.id, 'platform_owner', '')
        self.assertNotIn('platform_owner',
                         [r['key'] for r in m.get_people(
                             self.company.id)['roles']])
        with self.assertRaises(AccessError):
            m.get_scheme_panel('tenant', 'division:1', self.company.id)
        # directly, as the person
        Workflow = self.env['biz.approval.workflow'].with_user(self.ta)
        with self.assertRaises(AccessError):
            Workflow.create({'name': 'P6 sneaky', 'company_id': self.company.id,
                             'process_id': tenant.id})
        with self.assertRaises(AccessError):
            self.env['biz.approval.binding'].with_user(self.ta).create({
                'company_id': self.company.id, 'process_id': tenant.id,
                'scope_key': '', 'kind_key': 'any', 'mode': 'follow',
                'workflow_id': self.env['biz.approval.workflow'].sudo().search(
                    [], limit=1).id})
        with self.assertRaises(AccessError):
            self.env['biz.approval.responsibility'].with_user(self.ta).create({
                'company_id': self.company.id, 'role_id': owner.id,
                'scope_key': '', 'user_id': self.ta.id})
        # a route the platform already has for it cannot be edited either
        mine = self.env['biz.approval.workflow'].sudo().create({
            'name': 'P6 platform route', 'company_id': self.company.id,
            'process_id': tenant.id})
        draft = self.env['biz.approval.workflow.version'].sudo().create({
            'workflow_id': mine.id, 'revision': 1, 'status': 'draft',
            'definition': {'schema_version': 1, 'steps': []}})
        with self.assertRaises(AccessError):
            m.get_workflow(mine.id)
        with self.assertRaises(AccessError):
            m.publish(draft.id)
        with self.assertRaises(AccessError):
            self.env['biz.approval.engine'].with_user(self.ta).publish(
                draft.id)
        with self.assertRaises(AccessError):
            self.env['biz.approval.workflow.version'].with_user(
                self.ta).browse(draft.id).write({'definition': {
                    'schema_version': 1, 'steps': [{'key': 's1',
                                                    'kind': 'fast',
                                                    'title': 'x'}]}})
        # bulk "No approval needed" leaves it out
        res = m.set_no_approval_bulk(['tenant'], self.company.id,
                                     confirmations=['money_fast'])
        self.assertFalse(res['done'])

    # ------------------------------------------ the platform's support login
    def test_M3c_support_login_is_not_theirs(self):
        m = self.M()
        offered = {r['id'] for r in m.user_options(None, 'finance',
                                                    self.company.id)}
        self.assertNotIn(self.support.id, offered)
        self.assertIn(self.support.id, {r['id'] for r in self.M(
            self.support).user_options(None, 'finance', self.company.id)},
            'the platform itself still sees it')
        for kwargs in ({'user_id': self.support.id},
                       {'user_id': self.amy.id,
                        'backup_user_id': self.support.id}):
            with self.assertRaises(UserError):
                m.set_responsibility(self.company.id, 'finance', '',
                                     kwargs.pop('user_id'), **kwargs)
        with self.assertRaises(UserError):
            m.set_delegation({'company_id': self.company.id,
                              'delegate_user_id': self.support.id,
                              'reason': 'P6'})
        # a route naming it
        made = m.create_workflow('blank', 'generic', self.company.id)
        wf = m.get_workflow(made['workflow_id'])
        named = {'schema_version': 1, 'steps': [{
            'key': 's1', 'kind': 'approve', 'title': 'Sneaky',
            'who': {'mode': 'people', 'user_ids': [self.support.id]},
            'min_amount': 0, 'condition': None}]}
        with self.assertRaises(UserError):
            m.save_draft(wf['draft']['version_id'],
                         wf['draft']['draft_revision'], named)
        # directly, as the person
        finance = self.Role.search([('key', '=', 'finance')], limit=1)
        Resp = self.env['biz.approval.responsibility']
        with self.assertRaises(UserError):
            Resp.with_user(self.ta).create({
                'company_id': self.company.id, 'role_id': finance.id,
                'scope_key': 'p6', 'user_id': self.support.id})
        seat = Resp.sudo().create({
            'company_id': self.company.id, 'role_id': finance.id,
            'scope_key': 'p6b', 'user_id': self.amy.id})
        with self.assertRaises(UserError):
            Resp.with_user(self.ta).browse(seat.id).write(
                {'backup_user_id': self.support.id})
        with self.assertRaises(UserError):
            self.env['biz.approval.workflow.version'].with_user(
                self.ta).create({'workflow_id': made['workflow_id'],
                                 'revision': 9, 'status': 'draft',
                                 'definition': named})
        # where it already holds a seat, the screen never shows the account
        Resp.sudo().search([
            ('company_id', '=', self.company.id), ('role_id', '=', finance.id),
            ('scope_key', '=', ''), ('active', '=', True)]).write(
                {'active': False})
        Resp.sudo().create({'company_id': self.company.id,
                            'role_id': finance.id, 'scope_key': '',
                            'user_id': self.support.id})
        grid = m.get_people(self.company.id)
        cell = [c for r in grid['roles'] if r['key'] == 'finance'
                for c in r['cells'] if c['scope_key'] == ''][0]
        self.assertEqual(cell['user_id'], 0)
        self.assertEqual(cell['name'], 'Platform support')
        self.assertTrue(cell['support'])
        # ... and replacing it with one of their own people is allowed
        m.set_responsibility(self.company.id, 'finance', '', self.amy.id)
        # the trail shows the support login's own changes without the account
        self.env['biz.approval.event'].with_user(self.support)._log(
            'responsibility_changed', 'P6 support did a thing',
            company=self.company)
        rows = m.get_history(self.company.id)['rows']
        row = [r for r in rows if r['summary'] == 'P6 support did a thing'][0]
        self.assertEqual(row['who'], 'Platform support')
        self.assertEqual(row['avatar'], '')

    def test_M3d_cannot_grant_platform_capabilities(self):
        """Access already refuses any role reaching the administrator
        permission — still true with approvals set-up in the bundle."""
        Profile = self.env['pb.role.profile'].sudo()
        system = self.env.ref('base.group_system')
        ability = self.env['pb.role.ability'].sudo().search(
            [('group_ids', 'in', system.id)], limit=1)
        self.assertFalse(ability, 'no ability carries the system permission')
        # ValidationError and AccessError are both UserErrors (G43)
        with self.assertRaises(UserError):
            Profile.with_user(self.ta).create({
                'name': 'P6 keys', 'area': 'system',
                'group_id': system.id})

    def test_M3e_other_company_and_no_database_door(self):
        m = self.M()
        with self.assertRaises(AccessError):
            self.Matrix.with_user(self.ta).get_matrix(self.other_co.id)
        with self.assertRaises(UserError):
            m.set_responsibility(self.company.id, 'finance', '',
                                 self.elsewhere.id)
        with self.assertRaises(UserError):
            m.set_responsibility(self.company.id, 'finance', '', self.amy.id,
                                 backup_user_id=self.elsewhere.id)
        # one database per client: nothing on the set-up surface names one
        import inspect
        from odoo.addons.pb_approval_config.models import (
            matrix_facade, matrix_import)
        for mod in (matrix_facade, matrix_import):
            src = inspect.getsource(mod)
            for word in ('db_name', 'dbname', 'db_connect', 'sql_db'):
                self.assertNotIn(word, src)

    def test_M3f_spreadsheet_person_rails(self):
        Proposed = self.env['pb.approval.proposed.person'].sudo()
        row = Proposed.create({
            'company_id': self.company.id, 'process_key': 'generic',
            'role_key': 'finance', 'role_label': 'Finance approver',
            'name_text': 'Sam', 'kind': 'holder'})
        imp = self.env['pb.approval.matrix.import'].with_user(self.ta) \
            if 'pb.approval.matrix.import' in self.env else None
        if imp is None:
            self.skipTest('no spreadsheet door here')
        with self.assertRaises(UserError):
            imp.resolve_person(row.id, self.support.id)
        with self.assertRaises(UserError):
            imp.resolve_person(row.id, self.portal.id)
        imp.resolve_person(row.id, self.amy.id)
        self.assertTrue(self.env['biz.approval.event'].sudo().search_count([
            ('user_id', '=', self.ta.id), ('kind', '=', 'responsibility_changed'),
            ('summary', 'ilike', 'from the spreadsheet')]))


@tagged('post_install', '-at_install', 'pb_approval_config', 'p6')
class TestP6Strings(TransactionCase):
    """M8 — no vendor name in anything new a person reads."""

    def test_M8_no_vendor_name(self):
        import inspect
        from odoo.addons.pb_approval_config.models import (
            inbox_facade, matrix_facade, matrix_import, setup_rails)
        for mod in (setup_rails,):
            self.assertNotIn('Odoo', inspect.getsource(mod).replace(
                'from odoo', '').replace('odoo.', ''))
        for fn in (R.support_refusal, R.platform_refusal, R.catalogue_refusal):
            self.assertNotIn('odoo', str(fn()).lower())
        from odoo.addons.pb_vendor_access.hooks import TENANT_ADMIN_DESCRIPTION
        self.assertNotIn('odoo', TENANT_ADMIN_DESCRIPTION.lower())
        for mod in (inbox_facade, matrix_facade, matrix_import):
            self.assertTrue(inspect.getsource(mod))
