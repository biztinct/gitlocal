# -*- coding: utf-8 -*-
"""UPDATES P4b — HR officers may SEND a leave opening balances sheet (owner
D23, 2026-11-13); the approval route still decides; undo stays with Time Off
administrators.

The P4 fixture (`test_updates_p4.P4Fixture`): a company of its own, an absence
policy with three confirmed people, plain people, seven leave types. The HR
officer (`hr.group_hr_user`, no Time Off right of any kind) sends; the
balances must really be written — through the policy layer for a policy
person, as one validated allocation for a plain person — and named after the
officer (the P3a class of bug: a sender or approver without rights wrote
nothing while the screen said done).
"""
import os

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from . import test_updates_p4 as p4
from .test_updates_p4 import CUT, L, P4Fixture, csv_b64

MANAGER = 'hr_holidays.group_hr_holidays_manager'


class _Senders:
    """Shared helpers: the logins that must NOT be able to send."""

    def _try_send(self, user, rows, used):
        """`(answer or None, error or None)` of a send by `user`, the way the
        screen calls it (review, then apply)."""
        try:
            rv = self.U(user).review(csv_b64(rows), 'p4.csv', self.cols(used), kind='leave',
                                     cutover=CUT)
            changes = rv.get('changes') or [{'emp_id': self.na.id, 'field_id': L(self.days),
                                             'value': '12'}]
            res = self.U(user).apply(name='DEMO P4b no', file_b64=csv_b64(rows),
                                     filename='p4.csv', columns=self.cols(used),
                                     changes=changes, kind='leave', cutover=CUT)
            return res, None
        except (AccessError, UserError) as error:
            return None, error

    def _nothing_written(self, before):
        Line = self.env['pb.updates.leave.line'].sudo()
        Alloc = self.env['hr.leave.allocation'].sudo()
        self.assertEqual((Line.search_count([]), Alloc.search_count([])), before)

    def _counts_now(self):
        return (self.env['pb.updates.leave.line'].sudo().search_count([]),
                self.env['hr.leave.allocation'].sudo().search_count([]))


@tagged('post_install', '-at_install', 'pb_updates_p4b')
class TestUpdatesP4b(P4Fixture, _Senders):
    """"No approval needed" in the fixture's company: an HR officer's sheet
    goes in at once (the route decides)."""

    def test_B1_officer_sends_policy_and_plain_written(self):
        self.assertFalse(self.officer.has_group(MANAGER), 'fixture: the officer has no Time Off right')
        self.assertFalse(self.officer.has_group('hr_holidays.group_hr_holidays_user'))
        home = self.U(self.officer).get_home()['leave']
        self.assertTrue(home['may_set'], 'the Start screen lets an HR officer send')
        rows = [['Code', 'Annual', 'Annual carried', 'Annual taken', 'Days'],
                ['P4PA', '12', '3', '2', ''],
                ['P4NA', '', '', '', '9']]
        used = {2: L(self.annual), 3: L(self.annual, 'carry'), 4: L(self.annual, 'taken'),
                5: L(self.days)}
        _rv, res = self.send(rows, used, user=self.officer)
        self.assertFalse(res['pending'], res)
        self.assertEqual(res['written'], 2, res)
        lines = self.lines(res)
        self.assertEqual(set(lines.mapped('state')), {'set'}, lines.mapped('reason'))
        # Policy person: through the policy layer, named after the officer.
        pol = lines.filtered(lambda r: r.employee_id == self.pa)
        self.assertEqual(pol.way, 'policy')
        posting = self.env['pb.leave.policy.posting'].sudo().browse(pol.posting_ref)
        self.assertTrue(posting.exists())
        self.assertEqual((posting.kind, posting.days, posting.opening_carried_days,
                          posting.opening_taken_days), ('opening', 12, 3, 2))
        self.assertEqual(posting.create_uid, self.officer)
        self.assertEqual(posting.allocation_id.state, 'validate')
        self.assertEqual(pol.allocation_id, posting.allocation_id)
        # Plain person: ONE validated allocation (the type asks a Time Off
        # officer to approve), created and approved as the officer.
        plain = lines.filtered(lambda r: r.employee_id == self.na)
        alloc = plain.allocation_id
        self.assertEqual((plain.way, alloc.state, alloc.number_of_days), ('allocation', 'validate', 9))
        self.assertEqual(alloc.create_uid, self.officer)
        self.assertEqual(alloc.pb_updates_leave_line_id, plain)
        # The Time Off screen shows them.
        self.assertAlmostEqual(self.balance(self.na, self.days), 9)
        self.assertAlmostEqual(self.balance(self.pa, self.annual), 12)

    def test_B2_officer_cannot_undo_admin_can(self):
        _rv, res = self.send([['Code', 'Days'], ['P4NA', '6']], {2: L(self.days)},
                             user=self.officer)
        line = self.lines(res)
        self.assertEqual(line.state, 'set')
        row = [b for b in self.U(self.officer).get_history(10)['batches']
               if b['id'] == res['batch_id']][0]
        self.assertFalse(row['can_undo'], 'no Undo button for an HR officer')
        answer = self.U(self.officer).undo(batch_id=res['batch_id'])
        self.assertFalse(answer['ok'])
        self.assertIn('Time Off administrator', answer['msg'])
        records = self.env['pb.records.desk'].with_user(self.officer).with_context(
            allowed_company_ids=[self.company.id])
        answer = records.undo_apply(res['apply_id'])
        self.assertFalse(answer['ok'], 'the Records screen refuses it too')
        self.assertIn('Time Off administrator', answer['msg'])
        self.assertEqual((line.state, line.allocation_id.state), ('set', 'validate'))
        # A Time Off administrator still can.
        row = [b for b in self.U().get_history(10)['batches'] if b['id'] == res['batch_id']][0]
        self.assertTrue(row['can_undo'])
        answer = self.U().undo(batch_id=res['batch_id'])
        self.assertTrue(answer['ok'], answer)
        self.assertEqual((line.state, line.allocation_id.state), ('undone', 'refuse'))

    def test_B3_employee_login_and_plain_manager_cannot_send(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        portal = Users.create({
            'name': 'DEMO P4b Employee', 'login': 'p4b_employee',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
            'company_ids': [(6, 0, [self.company.id])], 'company_id': self.company.id})
        manager = Users.create({
            'name': 'DEMO P4b Manager', 'login': 'p4b_manager',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
            'company_ids': [(6, 0, [self.company.id])], 'company_id': self.company.id})
        boss = self.env['hr.employee'].sudo().create({
            'name': 'DEMO P4b Manager', 'company_id': self.company.id, 'user_id': manager.id})
        self.na.sudo().parent_id = boss
        rows = [['Code', 'Days'], ['P4NA', '12']]
        for user in (portal, manager):
            before = self._counts_now()
            res, error = self._try_send(user, rows, {2: L(self.days)})
            self.assertTrue(error is not None or not res.get('ok'), (user.name, res))
            self._nothing_written(before)
            if res is not None:
                self.assertFalse(self.U(user).get_home()['leave']['may_set'])

    def test_B4_checker_without_hr_officer_role_cannot_send(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        viewer = Users.create({
            'name': 'DEMO P4b Records viewer', 'login': 'p4b_viewer',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id,
                                  self.env.ref('pb_records.group_records_viewer').id])],
            'company_ids': [(6, 0, [self.company.id])], 'company_id': self.company.id})
        self.assertFalse(viewer.has_group('hr.group_hr_user'))
        before = self._counts_now()
        rv = self.review([['Code', 'Days'], ['P4NA', '12']], {2: L(self.days)}, user=viewer)
        self.assertEqual(len(rv['changes']), 1, 'they can still check a sheet')
        res = self.U(viewer).apply(name='DEMO P4b no', file_b64=csv_b64([['Code', 'Days'], ['P4NA', '12']]),
                                   filename='p4.csv', columns=self.cols({2: L(self.days)}),
                                   changes=rv['changes'], kind='leave', cutover=CUT)
        self.assertFalse(res['ok'])
        self.assertIn('HR officer role', res['msg'])
        self.assertNotIn('Time Off administrator', res['msg'])
        self.assertFalse(self.U(viewer).get_home()['leave']['may_set'])
        self._nothing_written(before)

    def test_B5_officer_never_sets_their_own_balance(self):
        me = self.env['hr.employee'].sudo().create({
            'name': 'DEMO P4b Officer self', 'barcode': 'P4BME', 'company_id': self.company.id,
            'resource_calendar_id': self.calendar.id, 'user_id': self.officer.id})
        rv = self.review([['Code', 'Days'], ['P4BME', '12'], ['P4NB', '4']], {2: L(self.days)},
                         user=self.officer)
        own = self.cell(rv, me, L(self.days))
        self.assertEqual(own['status'], 'refused')
        self.assertIn('cannot set their own leave balance', own['why'])
        self.assertEqual(len(rv['changes']), 1, 'only the other person goes')
        # Sent past the screen straight to apply: refused by the server too.
        _rv, res = self.send([['Code', 'Days'], ['P4BME', '12'], ['P4NB', '4']], {2: L(self.days)},
                             user=self.officer,
                             changes=[{'emp_id': me.id, 'field_id': L(self.days), 'value': '12'},
                                      {'emp_id': self.nb.id, 'field_id': L(self.days), 'value': '4'}])
        self.assertEqual(set(self.lines(res).mapped('employee_id').ids), {self.nb.id})
        self.assertIn('cannot set their own leave balance', ' '.join(r['why'] for r in res['refused']))
        # A Time Off administrator may set it.
        _rv, res = self.send([['Code', 'Days'], ['P4BME', '12']], {2: L(self.days)},
                             name='DEMO P4b by admin')
        self.assertEqual(self.lines(res).state, 'set')

    def test_B6_wording(self):
        root = os.path.dirname(os.path.dirname(__file__))
        with open(os.path.join(root, 'static/src/xml/updates_desk.xml')) as handle:
            xml = handle.read()
        with open(os.path.join(root, 'models/updates_leave_desk.py')) as handle:
            desk = handle.read()
        for old in ('Setting them needs the Time Off administrator role',
                    'setting balances needs the Time Off administrator role',
                    'setting them needs the Time Off administrator role'):
            self.assertNotIn(old, xml)
        self.assertNotIn('Setting leave balances needs the Time Off administrator role', desk)
        self.assertIn('Setting them needs the HR officer role', xml)
        for rel in ('models/updates_leave.py', 'models/updates_leave_desk.py',
                    'static/src/xml/updates_desk.xml'):
            with open(os.path.join(root, rel)) as handle:
                self.assertNotIn('Odoo', handle.read(), rel)


@tagged('post_install', '-at_install', 'pb_updates_p4b')
class TestUpdatesP4bRoute(P4Fixture, _Senders):
    """A real records route: the HR lead (an HR officer, no Time Off right)
    approves an HR officer's sheet."""

    _approvals = classmethod(p4.TestUpdatesP4Route._approvals.__func__)
    decide = p4.TestUpdatesP4Route.decide

    def _officer_sends(self):
        alloc_before = self.env['hr.leave.allocation'].sudo().search_count([])
        _rv, res = self.send([['Code', 'Days', 'Annual'], ['P4NA', '12', ''], ['P4PA', '', '10']],
                             {2: L(self.days), 3: L(self.annual)}, user=self.officer)
        self.assertTrue(res['pending'], res)
        self.assertIn('DEMO P4 HR Lead', res['with_whom'])
        apply_rec = self.env['pb.records.apply'].browse(res['apply_id'])
        lines = apply_rec.leave_line_ids
        self.assertEqual(set(lines.mapped('state')), {'waiting'})
        self.assertEqual(self.env['hr.leave.allocation'].sudo().search_count([]), alloc_before,
                         'nothing written before approval')
        return res, apply_rec, lines

    def test_R1_approval_writes_officers_balances(self):
        self.assertFalse(self.hr_lead.has_group(MANAGER), 'fixture: the approver has no Time Off right')
        _res, apply_rec, lines = self._officer_sends()
        self.decide(apply_rec, 'approve')
        self.assertTrue(apply_rec.applied)
        self.assertEqual(set(lines.mapped('state')), {'set'}, lines.mapped('reason'))
        plain = lines.filtered(lambda r: r.employee_id == self.na)
        self.assertEqual(plain.allocation_id.state, 'validate')
        self.assertEqual(plain.allocation_id.create_uid, self.officer, 'written as the proposer')
        self.assertAlmostEqual(self.balance(self.na, self.days), 12)
        pol = lines.filtered(lambda r: r.employee_id == self.pa)
        posting = self.env['pb.leave.policy.posting'].sudo().browse(pol.posting_ref)
        self.assertEqual((pol.way, posting.kind, posting.days), ('policy', 'opening', 10))
        self.assertEqual(posting.create_uid, self.officer)
        self.assertAlmostEqual(self.balance(self.pa, self.annual), 10)
        self.assertFalse(apply_rec.block_note)

    def test_R2_officer_lost_the_role_before_approval(self):
        _res, apply_rec, lines = self._officer_sends()
        before = self.env['hr.leave.allocation'].sudo().search_count([])
        self.officer.sudo().group_ids = [(6, 0, [self.env.ref('base.group_user').id])]
        self.assertFalse(self.officer.has_group('hr.group_hr_user'))
        self.decide(apply_rec, 'approve')
        self.assertEqual(set(lines.mapped('state')), {'refused'})
        self.assertIn('no longer has the HR officer role', lines[:1].reason)
        self.assertEqual(self.env['hr.leave.allocation'].sudo().search_count([]), before)

    def test_R3_officer_left_the_company_before_approval(self):
        _res, apply_rec, lines = self._officer_sends()
        before = self.env['hr.leave.allocation'].sudo().search_count([])
        self.officer.sudo().write({'company_ids': [(6, 0, [self.other_co.id])],
                                   'company_id': self.other_co.id})
        self.decide(apply_rec, 'approve')
        self.assertEqual(set(lines.mapped('state')), {'refused'}, lines.mapped('reason'))
        self.assertIn('no longer works in', lines[:1].reason)
        self.assertEqual(self.env['hr.leave.allocation'].sudo().search_count([]), before)

    def test_R4_time_off_admin_unchanged(self):
        """P4's own path: a Time Off administrator's sheet is written with
        their own rights, exactly as before."""
        _rv, res = self.send([['Code', 'Days'], ['P4NB', '5']], {2: L(self.days)})
        apply_rec = self.env['pb.records.apply'].browse(res['apply_id'])
        self.decide(apply_rec, 'approve')
        line = apply_rec.leave_line_ids
        self.assertEqual(line.state, 'set')
        self.assertEqual(line.allocation_id.create_uid, self.admin_to)
