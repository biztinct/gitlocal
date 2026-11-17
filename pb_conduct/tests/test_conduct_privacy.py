# -*- coding: utf-8 -*-
"""WDGAP S9-B — owner ruling P3, proved role by role.

Every "cannot see" below is checked through the ORM AND the board's server
calls, after `flush_all()` + `invalidate_all()` (ledger W2M-1: a rights test
that reads from the fixture's cache passes on the bug).
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged, TransactionCase

from .common import make_fixture

CONDUCT_MODELS = ('pb.conduct.case', 'pb.conduct.note', 'pb.conduct.event',
                  'pb.conduct.letter', 'pb.conduct.reason',
                  'pb.conduct.letter.template', 'pb.conduct.country.note')


@tagged('post_install', '-at_install', 'pb_conduct')
class TestConductPrivacy(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        make_fixture(cls)

    # ------------------------------------------------------------ helpers
    def _fresh(self):
        self.env.flush_all()
        self.env.invalidate_all()

    def _env(self, user, companies=None):
        companies = companies or self.company
        return self.env(user=user.id, su=False, context=dict(
            self.env.context, allowed_company_ids=companies.ids))

    def _blocked(self, fn):
        try:
            with self.env.cr.savepoint():
                fn()
        except (AccessError, UserError):
            return True
        return False

    def assertSeesNothing(self, user, who):
        """The whole closed door for one person."""
        self._fresh()
        env = self._env(user)
        # 1. no access right on any conduct model
        for model in CONDUCT_MODELS:
            self.assertFalse(env[model].has_access('read'),
                             '%s can read %s' % (who, model))
            self.assertTrue(self._blocked(lambda m=model: env[m].search([])),
                            '%s could search %s' % (who, model))
        # 2. the board: an explained refusal and no data
        F = env['pb.conduct']
        self.assertFalse(F.can_open(), who)
        board = F.get_board()
        self.assertFalse(board['allowed'], who)
        self.assertEqual(set(board), {'allowed', 'why'}, who)
        self.assertEqual(F.get_cases_page()['rows'], [], who)
        self.assertTrue(self._blocked(lambda: F.get_case(self.case.id)), who)
        self.assertTrue(self._blocked(lambda: F.employee_options('DEMO')), who)
        self.assertTrue(self._blocked(lambda: F.create_case({
            'employee_id': self.e_other.id, 'reason_id': self.reason.id,
            'summary': 'x'})), who)
        self.assertTrue(self._blocked(lambda: F.add_note(self.case.id, 'other', 'x')), who)
        self.assertTrue(self._blocked(lambda: F.issue_letter(self.draft.id)), who)
        # 3. the case's files and the letters' PDFs (attachments follow the case)
        Att = env['ir.attachment']
        for att in (self.file_att | self.decision.attachment_id):
            self.assertTrue(self._blocked(lambda a=att: Att.browse(a.id).read(['datas'])),
                            '%s read attachment %s' % (who, att.name))
        for res_model in ('pb.conduct.case', 'pb.conduct.letter'):
            found = []
            blocked = self._blocked(lambda rm=res_model: found.extend(
                Att.search([('res_model', '=', rm)]).ids))
            self.assertTrue(blocked or not found, '%s listed %s files' % (who, res_model))
        # 4. the documents vault (FACTS leak 2)
        if env['pb.employee.document'].has_access('read'):
            Doc = env['pb.employee.document']
            self.assertNotIn(self.vault_doc, Doc.search([]), who)
            self.assertTrue(self._blocked(lambda: Doc.browse(self.vault_doc.id).read(['name'])), who)
            self.assertTrue(self._blocked(lambda: Att.browse(
                self.vault_doc.attachment_id.id).read(['datas'])), who)
        # 5. the lifecycle letters (FACTS leak 1): no conduct letter is ever a pb.hr.letter
        if 'pb.hr.letter' in env and env['pb.hr.letter'].has_access('read'):
            self.assertFalse(env['pb.hr.letter'].search(
                [('employee_id', '=', self.e_subject.id)]), who)

    # ------------------------------------------------------------ 1-8: the closed door
    def test_01_general_hr_user_sees_nothing(self):
        self.assertSeesNothing(self.u_hr, 'HR officer')

    def test_01b_hr_manager_sees_nothing(self):
        self.assertSeesNothing(self.u_hr_mgr, 'HR manager')

    def test_02_lifecycle_user_sees_nothing(self):
        self.assertSeesNothing(self.u_life, 'lifecycle user/manager/admin')

    def test_03_payroll_officer_sees_nothing(self):
        self.assertSeesNothing(self.u_pay, 'payroll officer/manager')

    def test_04_line_manager_sees_nothing(self):
        self.assertSeesNothing(self.u_manager, 'line manager')

    def test_05_system_administrator_sees_nothing_until_named(self):
        self.assertSeesNothing(self.u_admin, 'system administrator')

    def test_06_tenant_administrator_sees_nothing_until_named(self):
        self.assertSeesNothing(self.u_tenant, 'tenant administrator')
        # ...but can NAME people: the conduct roles are listed to the access team
        env = self._env(self.u_tenant)
        if self.u_tenant.has_group('biz_access.group_access_manager'):
            roles = env['pb.role.profile'].search([('group_id', 'in', [
                self.env.ref('pb_conduct.group_conduct_user').id,
                self.env.ref('pb_conduct.group_conduct_head').id])])
            self.assertEqual(len(roles), 2)

    def test_07_other_employee_portal_sees_nothing(self):
        self.assertSeesNothing(self.u_other_portal, 'another employee (portal)')
        data = self.env['pb.conduct.letter'].my_letters(self.e_other)
        self.assertEqual(data['letters'], [])

    def test_08_employee_themselves_has_no_orm_access(self):
        # portal login of the person the case is about
        self.assertSeesNothing(self.u_subject_portal, 'the employee (portal)')

    def test_08b_employee_with_internal_login_sees_only_own_letter_document(self):
        # The case about Ian; issue a letter so a vault document exists.
        self.F.move(self.case3.id, 'skip_hearing', {'why': 'Minor'})
        self.F.move(self.case3.id, 'decide', {'outcome': 'verbal', 'summary': 'Verbal warning.'})
        letter = self.case3.letter_ids
        self.F.move(self.case3.id, 'ask_signoff')
        self.F2.move(self.case3.id, 'confirm_signoff')       # W3-A: second sign-off
        self.assertEqual(letter.state, 'issued')
        self._fresh()
        env = self._env(self.u_subject2_internal)
        for model in CONDUCT_MODELS:
            self.assertFalse(env[model].has_access('read'), model)
        self.assertFalse(env['pb.conduct'].can_open())
        # his own finished letter is his own document (the vault's own-read rule) ...
        Doc = env['pb.employee.document']
        self.assertIn(letter.document_id, Doc.search([]))
        # ... and nobody else's conduct letter is
        self.assertNotIn(self.vault_doc, Doc.search([]))
        self.assertTrue(self._blocked(lambda: Doc.browse(self.vault_doc.id).read(['name'])))

    # ------------------------------------------------------------ 9-12: the named people
    def test_09_named_hr_sees_the_whole_case(self):
        self._fresh()
        F = self._env(self.u_named)['pb.conduct']
        self.assertTrue(F.can_open())
        board = F.get_board()
        self.assertTrue(board['allowed'])
        ids = [r['id'] for r in F.get_cases_page()['rows']]
        self.assertIn(self.case.id, ids)
        data = F.get_case(self.case.id)
        self.assertIn('SECRET-SUMMARY', data['summary'])
        self.assertTrue(any('SECRET-NOTE' in n['body'] for n in data['notes']))
        self.assertTrue(any('SECRET-MINUTES' in n['body'] for n in data['notes']))
        self.assertEqual(len(data['files']), 1)
        self.assertEqual(len(data['letters']), 2)
        env = self._env(self.u_named)
        self.assertEqual(env['ir.attachment'].browse(self.file_att.id).read(['datas'])[0]['datas'],
                         self.file_att.datas)
        # the vault copy of the letter is readable by the named HR person
        self.assertIn(self.vault_doc, env['pb.employee.document'].search([]))

    def test_10_named_hr_never_sees_a_case_about_themselves(self):
        self._fresh()
        env = self._env(self.u_named)
        self.assertNotIn(self.case_self, env['pb.conduct.case'].search([]))
        F = env['pb.conduct']
        self.assertNotIn(self.case_self.id, [r['id'] for r in F.get_cases_page()['rows']])
        self.assertTrue(self._blocked(lambda: F.get_case(self.case_self.id)))
        self.assertFalse(env['pb.conduct.event'].search([('case_id', '=', self.case_self.id)]))
        # and cannot open one about themselves either
        self.assertTrue(self._blocked(lambda: F.create_case({
            'employee_id': self.e_named_self.id, 'reason_id': self.reason.id,
            'summary': 'x'})))
        self.assertNotIn(self.e_named_self.id, [p['id'] for p in F.employee_options('DEMO Nora')])
        # the head sees it
        Fh = self._env(self.u_head)['pb.conduct']
        self.assertEqual(Fh.get_case(self.case_self.id)['id'], self.case_self.id)

    def test_11_company_scope(self):
        self._fresh()
        env_a = self._env(self.u_named, self.company)
        self.assertNotIn(self.case_b, env_a['pb.conduct.case'].search([]))
        self.assertTrue(self._blocked(lambda: env_a['pb.conduct'].get_case(self.case_b.id)))
        env_ab = self._env(self.u_named, self.company | self.company_b)
        self.assertIn(self.case_b, env_ab['pb.conduct.case'].search([]))
        # the head works only in company A: never sees company B's case
        env_h = self._env(self.u_head, self.company)
        self.assertNotIn(self.case_b, env_h['pb.conduct.case'].search([]))

    def test_12_only_the_head_changes_the_setup(self):
        self._fresh()
        named = self._env(self.u_named)
        self.assertTrue(self._blocked(lambda: named['pb.conduct.reason'].create({'name': 'x'})))
        self.assertTrue(self._blocked(lambda: named['pb.conduct'].setup_action('reasons')))
        head = self._env(self.u_head)
        head['pb.conduct.reason'].create({'name': 'DEMO reason'})
        self.assertEqual(head['pb.conduct'].setup_action('countries')['res_model'],
                         'pb.conduct.country.note')

    # ------------------------------------------------------------ 13-15: the vault rule
    def test_13_nobody_unnamed_can_file_into_the_private_category(self):
        self._fresh()
        env = self._env(self.u_hr)
        cat = self.env.ref('pb_conduct.vault_category_conduct')
        other_cat = self.env['pb.employee.document.category'].search(
            [('code', '!=', 'pb_conduct')], limit=1)

        def file_it(category):
            att = self.env['ir.attachment'].create({'name': 'x.txt', 'raw': b'x'})
            return env['pb.employee.document'].create({
                'employee_id': self.e_other.id, 'category_id': category.id, 'name': 'x',
                'attachment_id': att.id, 'company_id': self.company.id})
        # control: the same HR officer files into an ordinary category
        self.assertFalse(self._blocked(lambda: file_it(other_cat)))
        # the private category is refused
        self.assertTrue(self._blocked(lambda: file_it(cat)))

    def test_14_other_vault_documents_are_unchanged_for_hr(self):
        """The new global rule narrows ONLY the private category."""
        self._fresh()
        other_cat = self.env['pb.employee.document.category'].search(
            [('code', '!=', 'pb_conduct')], limit=1)
        att = self.env['ir.attachment'].create({'name': 'id.txt', 'raw': b'id',
                                                'res_model': 'pb.employee.document', 'res_id': 0})
        doc = self.env['pb.employee.document'].create({
            'employee_id': self.e_other.id, 'category_id': other_cat.id, 'name': 'ID card',
            'attachment_id': att.id, 'company_id': self.company.id})
        self._fresh()
        for user in (self.u_hr, self.u_pay):
            self.assertIn(doc, self._env(user)['pb.employee.document'].search([]))

    def test_15_employee_360_drawer_does_not_list_it(self):
        P = self.env['pb.people']
        if not hasattr(P, '_documents_for'):
            self.skipTest('no document read on the 360 drawer')
        self._fresh()
        # control: the named HR person's drawer lists it
        named = self._env(self.u_named)['pb.people']._documents_for(self.e_subject)
        self.assertIn(self.vault_doc.id, [d.get('id') for d in named])
        for user in (self.u_hr, self.u_pay, self.u_life):
            self._fresh()
            rows = self._env(user)['pb.people']._documents_for(self.e_subject)
            self.assertNotIn(self.vault_doc.id, [d.get('id') for d in rows])
