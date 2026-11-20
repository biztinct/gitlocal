# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""WORKFLOW-2 P6c (D36): time off "Sent back" — the mark and "Ask again".

* the mark is set when an approver sends a request back, never on a refusal
  (engine "turn down" or the cockpit's own refuse), and the status underneath
  stays "refused" (no day is held);
* the staff cockpit card, its filter values and saved views, the standard
  form's one-line note and the employee home's "My requests" row say "Sent
  back" (en / vi / id), and "Refused" counts only real refusals;
* "Ask again" (the staff "Apply for" drawer) makes a NEW request linked both
  ways, once, through the normal rules — a request over the balance is
  refused by hr_holidays itself and nothing is linked;
* the post-migration marks only requests whose approval provably was sent
  back, and is idempotent.

Run alone: ``--test-tags /pb_timeoff:TestWf2p6cSentBack``.
"""

import importlib.util
import os
from datetime import date, timedelta

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.biz_approval_workflow.tests.single_notice_common import (
    SingleNoticeMixin,
)


def _raises(case, exc, fn, *args, **kw):
    """assertRaises for one class at a time (ledger G75)."""
    try:
        with case.env.cr.savepoint():
            fn(*args, **kw)
    except exc as error:
        return error
    case.fail('%s was not raised' % exc.__name__)


@tagged('post_install', '-at_install', 'wf2p6c')
class TestWf2p6cSentBack(SingleNoticeMixin, TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        internal = cls.env.ref('base.group_user')
        officer = cls.env.ref('hr_holidays.group_hr_holidays_user')
        cls.boss_user = Users.create({
            'name': 'P6c Boss', 'login': 'p6c_leave_boss',
            'email': 'p6c_leave_boss@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        cls.staff_user = Users.create({
            'name': 'P6c Asker', 'login': 'p6c_leave_staff',
            'email': 'p6c_leave_staff@example.com',
            'group_ids': [(6, 0, [internal.id])]})
        cls.hr_user = Users.create({
            'name': 'P6c Officer', 'login': 'p6c_leave_officer',
            'email': 'p6c_leave_officer@example.com',
            'group_ids': [(6, 0, [internal.id, officer.id])]})
        Emp = cls.env['hr.employee']
        cls.boss = Emp.create({'name': 'P6c Boss', 'user_id': cls.boss_user.id,
                               'company_id': cls.company.id})
        cls.staff = Emp.create({
            'name': 'P6c Asker', 'user_id': cls.staff_user.id,
            'work_email': 'p6c.asker@example.com',
            'parent_id': cls.boss.id, 'leave_manager_id': cls.boss_user.id,
            'company_id': cls.company.id})
        cls.other = Emp.create({
            'name': 'P6c Other', 'parent_id': cls.boss.id,
            'leave_manager_id': cls.boss_user.id,
            'company_id': cls.company.id})
        Type = cls.env['hr.leave.type']
        cls.ltype = Type.create({
            'name': 'P6c manager type', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'company_id': cls.company.id})
        cls.half = Type.create({
            'name': 'P6c half days', 'requires_allocation': False,
            'leave_validation_type': 'manager', 'request_unit': 'half_day',
            'company_id': cls.company.id})
        cls.counted = Type.create({
            'name': 'P6c counted', 'requires_allocation': True,
            'leave_validation_type': 'manager', 'request_unit': 'day',
            'allocation_validation_type': 'hr', 'company_id': cls.company.id})
        alloc = cls.env['hr.leave.allocation'].sudo().create({
            'name': 'P6c grant', 'employee_id': cls.staff.id,
            'holiday_status_id': cls.counted.id, 'number_of_days': 2,
            'allocation_type': 'regular',
            'date_from': date.today() - timedelta(days=30)})
        alloc.action_approve()

    def setUp(self):
        super().setUp()
        self.sn_switch(True)
        self.sn_outbox_job(True)
        self.sn_route('leave', self.boss_user)

    # ------------------------------------------------------------- helpers
    def _monday(self, weeks):
        anchor = date.today() + timedelta(days=7 * weeks)
        return anchor - timedelta(days=anchor.weekday())

    def _leave(self, weeks=1, ltype=None, days=1, employee=None, **extra):
        start = self._monday(weeks)
        vals = {
            'holiday_status_id': (ltype or self.ltype).id,
            'employee_id': (employee or self.staff).id,
            'request_date_from': start,
            'request_date_to': start + timedelta(days=days - 1),
            'name': 'P6c time off'}
        vals.update(extra)
        leave = self.env['hr.leave'].sudo().create(vals)
        self.sn_settle()
        return leave

    def _decide(self, leave, action, reason):
        request = leave.approval_request_id
        step = request.step_ids.filtered(lambda s: s.status == 'active')
        self.env['biz.approval.engine'].with_user(self.boss_user).decide(
            request.id, step.key, action, reason=reason)
        self.env.invalidate_all()

    def _send_back(self, leave, reason='P6c: pick the week after'):
        self._decide(leave, 'return', reason)
        return leave

    def _cockpit(self, user=None, lang=None):
        TO = self.env['pb.timeoff'].with_user(user or self.hr_user)
        return TO.with_context(lang=lang) if lang else TO

    def _card(self, leave, lang=None):
        return self._cockpit(lang=lang).sudo()._leave_card(
            leave.with_context(lang=lang) if lang else leave)

    # ================================================== 1. the mark itself
    def test_01_mark_set_on_send_back_only(self):
        back = self._send_back(self._leave(weeks=1))
        self.assertEqual(back.state, 'refuse', 'still refused underneath')
        self.assertTrue(back.pb_sent_back)
        self.assertTrue(back._pb_is_sent_back())
        # turned down by the approver: a refusal, no mark
        turned = self._leave(weeks=2)
        self._decide(turned, 'reject', 'P6c: no')
        self.assertEqual(turned.state, 'refuse')
        self.assertFalse(turned.pb_sent_back)
        # refused from the cockpit (with a reason): a refusal, no mark —
        # on a request with no route, the cockpit's own stock refuse
        process = self.env['biz.approval.process']._by_key('leave')
        self.env['biz.approval.binding'].sudo().search([
            ('company_id', '=', self.company.id),
            ('process_id', '=', process.id)]).write({'active': False})
        plain = self._leave(weeks=3)
        self.assertFalse(plain.approval_request_id)
        self._cockpit().act(plain.id, 'refuse', 'P6c: busy week')
        plain.invalidate_recordset()
        self.assertEqual(plain.state, 'refuse')
        self.assertFalse(plain.pb_sent_back)
        # no day is held by a sent-back request: it is not in the queue and
        # not in the "on leave" set
        self.assertNotIn(back.id, [c['id'] for c in self._cockpit().sudo()._queue()])

    def test_02_mark_reads_only_while_refused(self):
        back = self._send_back(self._leave(weeks=4))
        back.with_context(leave_skip_state_check=True).sudo().write(
            {'state': 'confirm'})
        self.assertTrue(back.pb_sent_back, 'the mark is never cleared')
        self.assertFalse(back._pb_is_sent_back(),
                         'a request moved back to waiting reads as waiting')

    # ======================================= 2. the staff cockpit and form
    def test_03_cockpit_card_labels_en_vi_id(self):
        back = self._send_back(self._leave(weeks=5), 'P6c: half day only')
        card = self._card(back)
        self.assertTrue(card['sent_back'])
        self.assertEqual(card['state_label'], 'Sent back')
        self.assertEqual(card['sent_back_note'], 'P6c: half day only')
        self.assertTrue(card['again'], '"Ask again" is offered')
        self.assertEqual(card['again']['type_id'], self.ltype.id)
        self.assertIn('not copied', card['again']['documents_note'])
        self.assertEqual(self._card(back, 'vi_VN')['state_label'],
                         'Đã bị trả lại')
        self.assertEqual(self._card(back, 'id_ID')['state_label'],
                         'Dikembalikan')
        refused = self._leave(weeks=6)
        self._decide(refused, 'reject', 'P6c: no')
        card = self._card(refused)
        self.assertFalse(card['sent_back'])
        self.assertEqual(card['state_label'], 'Refused')
        self.assertFalse(card['again'])

    def test_04_refused_counts_exclude_sent_back(self):
        back = self._send_back(self._leave(weeks=7))
        refused = self._leave(weeks=8)
        self._decide(refused, 'reject', 'P6c: no')
        TO = self._cockpit()
        ids_refused = [c['id'] for c in TO.get_queue_page(
            filters={'status': ['refuse']}, limit=200)['cards']]
        ids_back = [c['id'] for c in TO.get_queue_page(
            filters={'status': ['sent_back']}, limit=200)['cards']]
        self.assertIn(refused.id, ids_refused)
        self.assertNotIn(back.id, ids_refused)
        self.assertIn(back.id, ids_back)
        self.assertNotIn(refused.id, ids_back)
        # the filter panel's counts follow the same two domains
        spec = [s for s in TO.sudo()._pbf_clean_spec() if s['key'] == 'status'][0]
        values = {o['value']: o for o in spec['options']}
        self.assertIn('sent_back', values)
        Leave = self.env['hr.leave'].sudo()
        base = TO.sudo()._pbf_base_domain()
        n_back = Leave.search_count(base + values['sent_back']['domain'])
        n_ref = Leave.search_count(base + values['refuse']['domain'])
        self.assertEqual(n_back + n_ref, Leave.search_count(
            base + [('state', '=', 'refuse')]))
        # the saved view beside "Refused"
        keys = [v['key'] for v in TO.sudo()._pbf_builtin_views()]
        self.assertEqual(keys[keys.index('sent_back') + 1], 'refused')

    def test_05_standard_form_note(self):
        back = self._send_back(self._leave(weeks=9), 'P6c: wrong week')
        back.invalidate_recordset()
        self.assertEqual(back.pb_sent_back_note,
                         'Sent back to the employee, not refused: P6c: wrong week')
        arch = self.env['hr.leave'].get_view(
            self.env.ref('hr_holidays.hr_leave_view_form').id, 'form')['arch']
        self.assertIn('pb_sent_back_note', arch)
        self.assertIn('pb_again_of_id', arch)
        # the status bar is untouched: still "Refused" underneath
        self.assertEqual(dict(self.env['hr.leave']._fields['state']
                              ._description_selection(self.env))['refuse'],
                         'Refused')
        refused = self._leave(weeks=10)
        self._decide(refused, 'reject', 'P6c: no')
        refused.invalidate_recordset()
        self.assertFalse(refused.pb_sent_back_note)

    def test_06_form_note_translated(self):
        back = self._send_back(self._leave(weeks=11), 'P6c: x')
        for lang, start in (('vi_VN', 'Đã bị trả lại cho nhân viên'),
                            ('id_ID', 'Dikembalikan ke karyawan')):
            leave = back.with_context(lang=lang)
            leave.invalidate_recordset(['pb_sent_back_note'])
            self.assertTrue(leave.pb_sent_back_note.startswith(start),
                            leave.pb_sent_back_note)

    # ================================= 3. the employee home's My requests
    def _my_rows(self, lang=None):
        Home = self.env['pb.me.home'].with_user(self.staff_user)
        if lang:
            Home = Home.with_context(lang=lang)
        src = [s for s in Home._my_requests_sources() if s['key'] == 'leave'][0]
        return {r['id']: r for r in Home._my_requests_rows(src, self.staff)}

    def test_07_my_requests_row(self):
        back = self._send_back(self._leave(weeks=12))
        refused = self._leave(weeks=13)
        self._decide(refused, 'reject', 'P6c: no')
        rows = self._my_rows()
        self.assertEqual(rows[back.id]['state_label'], 'Sent back — your turn')
        self.assertEqual(rows[back.id]['tone'], 'act')
        self.assertEqual(rows[back.id]['bucket'], 'act')
        self.assertEqual(rows[back.id]['url'], '/my/work/leave#pbew-lv-%s' % back.id)
        self.assertEqual(rows[refused.id]['state_label'], 'Refused')
        self.assertEqual(rows[refused.id]['bucket'], 'done')
        self.assertEqual(self._my_rows('vi_VN')[back.id]['state_label'],
                         'Đã bị trả lại — đến lượt bạn')
        self.assertEqual(self._my_rows('id_ID')[back.id]['state_label'],
                         'Dikembalikan — giliran Anda')
        # asked again: the old row is quiet
        self._cockpit().apply_on_behalf(
            self.staff.id, self.ltype.id, str(back.request_date_from),
            str(back.request_date_to), 'again', again_of=back.id)
        rows = self._my_rows()
        self.assertEqual(rows[back.id]['state_label'], 'Sent back — asked again')
        self.assertEqual(rows[back.id]['bucket'], 'done')

    # ============================================== 4. "Ask again" (staff)
    def test_08_ask_again_links_both_ways_once(self):
        back = self._send_back(self._leave(weeks=14, name='P6c my note'))
        res = self._cockpit().apply_on_behalf(
            self.staff.id, self.ltype.id, str(back.request_date_from),
            str(back.request_date_to), 'P6c my note', again_of=back.id)
        new = self.env['hr.leave'].sudo().browse(res['id'])
        self.assertEqual(new.state, 'confirm', 'waiting for approval')
        self.assertTrue(new.approval_request_id, 'it went to the route')
        self.assertEqual(new.pb_again_of_id, back)
        back.invalidate_recordset()
        self.assertEqual(back.pb_again_id, new)
        self.assertFalse(back._pb_can_ask_again())
        self.assertEqual(back.state, 'refuse', 'the old one is untouched')
        lines = new._pb_again_lines()
        self.assertTrue(lines['of']['label'].startswith(
            'Asked again after the request for'))
        self.assertEqual(lines['of']['id'], back.id)
        lines = back._pb_again_lines()
        self.assertTrue(lines['as']['label'].startswith('Asked again on'))
        card = self._card(back)
        self.assertFalse(card['again'], 'the button disappears')
        self.assertEqual(card['again_as']['id'], new.id)
        # once only — whichever door
        error = _raises(self, UserError, self._cockpit().apply_on_behalf,
                        self.staff.id, self.ltype.id,
                        str(back.request_date_from + timedelta(days=1)),
                        str(back.request_date_from + timedelta(days=1)),
                        'twice', again_of=back.id)
        self.assertIn('already asked again', str(error))

    def test_09_ask_again_refusals(self):
        refused = self._leave(weeks=15)
        self._decide(refused, 'reject', 'P6c: no')
        error = _raises(self, UserError, self._cockpit().apply_on_behalf,
                        self.staff.id, self.ltype.id,
                        str(refused.request_date_from),
                        str(refused.request_date_to), 'x',
                        again_of=refused.id)
        self.assertIn('Only a request that was sent back', str(error))
        back = self._send_back(self._leave(weeks=16))
        error = _raises(self, UserError, self._cockpit().apply_on_behalf,
                        self.other.id, self.ltype.id,
                        str(back.request_date_from),
                        str(back.request_date_to), 'x', again_of=back.id)
        self.assertIn('same person', str(error))
        self.assertTrue(back._pb_can_ask_again(), 'nothing was linked')

    def test_10_ask_again_runs_the_normal_rules(self):
        """2 days granted; the sent-back request asked for 1; asked again for
        5 days → hr_holidays' own balance rule refuses it; no link made."""
        back = self._send_back(self._leave(weeks=17, ltype=self.counted))
        start = back.request_date_from
        before = self.env['hr.leave'].sudo().search_count([
            ('employee_id', '=', self.staff.id)])
        _raises(self, ValidationError, self._cockpit().apply_on_behalf,
                self.staff.id, self.counted.id, str(start),
                str(start + timedelta(days=4)), 'too long', again_of=back.id)
        self.assertEqual(self.env['hr.leave'].sudo().search_count([
            ('employee_id', '=', self.staff.id)]), before)
        back.invalidate_recordset()
        self.assertTrue(back._pb_can_ask_again())

    def test_11_ask_again_keeps_the_half_day(self):
        back = self._send_back(self._leave(
            weeks=18, ltype=self.half, request_date_from_period='am',
            request_date_to_period='am'))
        self.assertEqual(back.number_of_days, 0.5)
        prefill = back._pb_again_prefill()
        self.assertEqual(prefill['period_from'], 'am')
        self.assertEqual(prefill['part_label'], 'Half day, morning')
        res = self._cockpit().apply_on_behalf(
            self.staff.id, self.half.id, str(back.request_date_from),
            str(back.request_date_to), 'again', again_of=back.id)
        new = self.env['hr.leave'].sudo().browse(res['id'])
        self.assertEqual(new.request_date_from_period, 'am')
        self.assertEqual(new.number_of_days, 0.5)

    # ============================================ 5. the post-migration
    def _migration(self):
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'migrations', '19.0.1.13.0', 'post-sent-back.py')
        spec = importlib.util.spec_from_file_location('pb_p6c_post', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_12_backfill_marks_only_proven_send_backs(self):
        back = self._send_back(self._leave(weeks=19))
        turned = self._leave(weeks=20)
        self._decide(turned, 'reject', 'P6c: no')
        self.env.flush_all()
        # as before the mark existed
        self.env.cr.execute("UPDATE hr_leave SET pb_sent_back = FALSE "
                            "WHERE id IN %s", ((back.id, turned.id),))
        self.env.invalidate_all()
        migrate = self._migration().migrate
        migrate(self.env.cr, '19.0.1.12.0')
        self.env.invalidate_all()
        self.assertTrue(back.pb_sent_back)
        self.assertFalse(turned.pb_sent_back)
        # idempotent: nothing left to mark
        self.env.cr.execute(self._migration()._FIND)
        self.assertFalse(self.env.cr.fetchall())
        migrate(self.env.cr, '19.0.1.12.0')
        self.env.invalidate_all()
        self.assertTrue(back.pb_sent_back)
        self.assertFalse(turned.pb_sent_back)
