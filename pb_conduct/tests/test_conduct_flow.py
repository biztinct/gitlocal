# -*- coding: utf-8 -*-
"""WDGAP S9-B — the case flow, the employee's letters and reply, silent install."""

from datetime import date

from dateutil.relativedelta import relativedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged, TransactionCase

from .common import make_fixture


@tagged('post_install', '-at_install', 'pb_conduct')
class TestConductFlow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_before = cls.env['mail.mail'].sudo().search_count([])
        cls.msg_before = cls.env['mail.message'].sudo().search_count([])
        make_fixture(cls)

    def _raises(self, fn):
        try:
            with self.env.cr.savepoint():
                fn()
        except (AccessError, UserError, ValidationError):
            return True
        return False

    # ------------------------------------------------------------ 20: the flow
    def test_20_concern_hearing_decision_letter(self):
        case = self.case
        self.assertEqual(case.state, 'closed')
        self.assertEqual(case.outcome, 'written')
        self.assertTrue(case.name.startswith('CC-'))
        self.assertEqual(case.department_id, self.dept)
        self.assertEqual(case.hearing_held_on, date(2026, 6, 10))
        # default validity: 12 months for a written warning
        self.assertEqual(case.valid_until, case.decided_on + relativedelta(months=12))
        # minutes are a note on the case, not a file anywhere
        minutes = case.note_ids.filtered(lambda n: n.kind == 'minutes')
        self.assertIn('SECRET-MINUTES', minutes.body)
        # the decision letter is worded from the template and issued
        self.assertEqual(self.decision.state, 'issued')
        self.assertIn('DEMO Sam Subject', self.decision.body)
        self.assertIn('A written warning for lateness.', self.decision.body)
        self.assertNotIn('${', self.decision.body)
        self.assertTrue(self.decision.attachment_id)
        self.assertTrue(self.decision.document_id)
        self.assertEqual(self.decision.document_id.category_id.code, 'pb_conduct')
        # the invitation carries the hearing place
        self.assertIn('Room 2', self.invite.body)
        # history: every step is in the case's own log
        texts = ' | '.join(case.event_ids.mapped('text'))
        for word in ('Case opened', 'Hearing planned', 'Hearing held', 'Decided',
                     'Letter issued', 'Case closed'):
            self.assertIn(word, texts)

    def test_21_steps_refuse_out_of_order(self):
        F = self.F
        cid = F.create_case({'employee_id': self.e_other.id, 'reason_id': self.reason.id,
                             'summary': 'x'})['id']
        self.assertTrue(self._raises(lambda: F.move(cid, 'hearing_held', {})))
        self.assertTrue(self._raises(lambda: F.move(cid, 'decide', {'outcome': 'written',
                                                                    'summary': 'x'})))
        self.assertTrue(self._raises(lambda: F.move(cid, 'close', {})))  # needs a reason
        self.assertTrue(self._raises(lambda: F.move(cid, 'skip_hearing', {'why': ''})))
        F.move(cid, 'skip_hearing', {'why': 'Clear facts'})
        self.assertTrue(self._raises(lambda: F.move(cid, 'decide', {'outcome': 'bad',
                                                                    'summary': 'x'})))
        self.assertTrue(self._raises(lambda: F.move(cid, 'decide', {
            'outcome': 'final', 'summary': 'x', 'valid_until': '2000-01-01'})))
        F.move(cid, 'decide', {'outcome': 'final', 'summary': 'Final.',
                               'valid_until': '2030-01-31'})
        case = self.env['pb.conduct.case'].browse(cid)
        self.assertEqual(case.valid_until, date(2030, 1, 31))
        self.assertEqual(case.state, 'letter')

    def test_22_no_action_and_dismissal(self):
        F = self.F
        cid = F.create_case({'employee_id': self.e_other.id, 'reason_id': self.reason.id,
                             'summary': 'x'})['id']
        F.move(cid, 'skip_hearing', {'why': 'Minor'})
        F.move(cid, 'decide', {'outcome': 'none', 'summary': 'No action.'})
        case = self.env['pb.conduct.case'].browse(cid)
        self.assertFalse(case.valid_until)
        self.assertEqual(case.letter_ids.kind, 'none')
        F.move(cid, 'close', {'why': 'Closed without a letter'})
        self.assertEqual(case.state, 'closed')
        F.move(cid, 'reopen')
        self.assertEqual(case.state, 'letter')

    def test_23_dismissal_opens_a_neutral_leaving_checklist(self):
        if 'pb.journey.case' not in self.env:
            self.skipTest('no leaving checklist here')
        F = self.F
        cid = F.create_case({'employee_id': self.e_other.id, 'reason_id': self.reason.id,
                             'summary': 'SECRET-DISMISSAL-SUMMARY'})['id']
        F.move(cid, 'skip_hearing', {'why': 'x'})
        F.move(cid, 'decide', {'outcome': 'dismissal', 'summary': 'Dismissed.'})
        self.assertTrue(F.get_case(cid)['can']['exit'])
        try:
            F.move(cid, 'exit')
        except UserError as e:          # no offboarding template on a bare copy
            self.skipTest('leaving checklist could not open here: %s' % e)
        case = self.env['pb.conduct.case'].browse(cid)
        journey = self.env['pb.journey.case'].browse(case.exit_case_id)
        self.assertTrue(journey.exists())
        bodies = ' '.join(journey.sudo().message_ids.mapped('body'))
        # (the test login's NAME lists its groups, so the word "conduct" can
        # appear as the step owner's name; the case itself must not)
        for secret in ('SECRET', 'Attendance', 'Dismissed', 'dismissal', 'warning'):
            self.assertNotIn(secret, bodies)

    def test_24_issued_letter_is_frozen(self):
        self.assertTrue(self._raises(lambda: self.decision.with_user(self.u_named).write(
            {'body': 'changed'})))
        self.assertTrue(self._raises(lambda: self.F.delete_letter(self.decision.id)))
        self.assertTrue(self._raises(lambda: self.F.save_letter(self.decision.id, 't', 'b')))
        self.F.save_letter(self.draft.id, 'New title', 'New body')
        self.assertEqual(self.draft.body, 'New body')

    def test_25_template_placeholders_are_checked(self):
        head = self.env['pb.conduct.letter.template'].with_user(self.u_head)
        self.assertTrue(self._raises(lambda: head.create({
            'name': 'x', 'kind': 'written', 'title': 'x', 'body': 'Hello ${salary}'})))
        tpl = head.create({'name': 'x', 'kind': 'written', 'title': 'x',
                           'body': 'Hello ${employee}'})
        self.assertEqual(tpl.render(tpl.body, {'employee': 'Sam'}), 'Hello Sam')

    def test_26_country_notes_show_on_the_case(self):
        country = self.company.country_id
        if not country:
            self.skipTest('company has no country')
        self.env['pb.conduct.country.note'].with_user(self.u_head).create({
            'country_id': country.id, 'step': 'decision',
            'note': 'DEMO note: warnings lapse after the period your adviser confirms.'})
        cid = self.F.create_case({'employee_id': self.e_other.id, 'reason_id': self.reason.id,
                                  'summary': 'x'})['id']
        self.F.move(cid, 'skip_hearing', {'why': 'x'})
        notes = self.F.get_case(cid)['country_notes']
        self.assertEqual([n['step'] for n in notes if n['current']], ['decision'])

    # ------------------------------------------------------------ 30: the employee
    def test_30_employee_sees_only_own_finished_letters(self):
        data = self.env['pb.conduct.letter'].my_letters(self.e_subject)
        titles = [r['title'] for r in data['letters']]
        self.assertEqual(len(titles), 2)                     # invitation + decision
        self.assertIn(self.decision.title, titles)
        self.assertNotIn('SECRET-DRAFT-TITLE', titles)       # draft never shown
        blob = repr(data)
        for secret in ('SECRET-SUMMARY', 'SECRET-NOTE', 'SECRET-MINUTES', 'SECRET-FILE',
                       'Shift lead'):
            self.assertNotIn(secret, blob)
        self.assertEqual(data['unread'], 2)
        self.assertEqual(self.env['pb.conduct.letter'].my_letters(self.e_other)['letters'], [])

    def test_31_employee_reads_and_replies_once(self):
        L = self.env['pb.conduct.letter']
        self.assertTrue(L.mark_read(self.e_subject, self.invite.id))
        self.assertTrue(self.invite.read_on)
        res = L.send_reply(self.e_subject, self.decision.id, 'I disagree: the bus was late.')
        self.assertTrue(res['ok'])
        self.assertEqual(self.decision.reply, 'I disagree: the bus was late.')
        self.assertFalse(self.decision.reply_seen)
        self.assertTrue(self.decision.read_on)               # replying counts as read
        self.assertFalse(L.send_reply(self.e_subject, self.decision.id, 'again')['ok'])
        self.assertFalse(L.send_reply(self.e_subject, self.decision.id, '  ')['ok'])
        # named HR sees the reply, and the board counts it
        board = self.F.get_board()
        self.assertEqual(board['kpis']['replies'], 1)
        self.F.reply_seen(self.decision.id)
        self.assertEqual(self.F.get_board()['kpis']['replies'], 0)

    def test_32_employee_cannot_touch_another_persons_letter(self):
        L = self.env['pb.conduct.letter']
        self.assertFalse(L.mark_read(self.e_other, self.decision.id))
        self.assertFalse(L.send_reply(self.e_other, self.decision.id, 'x')['ok'])
        self.assertFalse(L.send_reply(self.e_subject, self.draft.id, 'x')['ok'])   # draft
        self.assertFalse(self.decision.reply)

    def test_33_needs_you_row_while_unread(self):
        rows = {}

        def put(key, n, url, **kw):
            rows[key] = dict(kw, n=n, url=url)
        # as the person themselves: other modules' rows check the record is theirs
        self.env['pb.me.home'].with_user(self.u_subject_portal)._pbme_needs_extra(
            self.e_subject, put)
        self.assertEqual(rows['hr_letters']['n'], 2)
        self.assertEqual(rows['hr_letters']['url'], '/my/letters')
        label = rows['hr_letters']['label'].lower()
        for word in ('warning', 'disciplin', 'conduct'):
            self.assertNotIn(word, label)
        rows.clear()
        self.env['pb.me.home'].with_user(self.u_other_portal)._pbme_needs_extra(
            self.e_other, put)
        self.assertNotIn('hr_letters', rows)

    # ------------------------------------------------------------ 40: silent
    def test_40_silent_install_and_no_mail(self):
        env = self.env
        crons = env['ir.cron'].sudo().search([]).filtered(
            lambda c: (c.get_external_id().get(c.id) or '').startswith('pb_conduct.'))
        self.assertFalse(crons)
        # install grants nobody: not the built-in administrator, not the
        # system account, not whoever ran the install (unlike growth plans)
        for xmlid in ('pb_conduct.group_conduct_user', 'pb_conduct.group_conduct_head'):
            holders = env.ref(xmlid).all_user_ids
            for builtin in ('base.user_admin', 'base.user_root'):
                self.assertNotIn(env.ref(builtin), holders, xmlid)
            data_users = env['ir.model.data'].sudo().search([
                ('module', '=', 'pb_conduct'), ('model', '=', 'res.users')])
            self.assertFalse(data_users)
        # the whole fixture flow sent and queued nothing
        self.assertEqual(env['mail.mail'].sudo().search_count([]), self.mail_before)
        # no chatter anywhere: nothing on the cases, nothing about the case on the person
        Msg = env['mail.message'].sudo()
        self.assertFalse(Msg.search_count([('model', 'like', 'pb.conduct')]))
        self.assertFalse(Msg.search_count([('model', '=', 'hr.employee'),
                                           ('res_id', '=', self.e_subject.id),
                                           ('body', 'ilike', 'SECRET')]))
        self.assertFalse(env['mail.activity'].sudo().search_count(
            [('res_model', 'like', 'pb.conduct')]))
        # the role catalogue and the Talent entry
        role = env.ref('pb_conduct.role_conduct_hr')
        self.assertEqual(role.visible_group_id, env.ref('pb_conduct.group_conduct_head'))
        item = env.ref('pb_talent_hub.item_talent', raise_if_not_found=False)
        if item and 'role_ids' in item._fields:
            self.assertIn(role, item.sudo().role_ids)

    def test_41_groups_imply_nothing_upward(self):
        user_g = self.env.ref('pb_conduct.group_conduct_user')
        head_g = self.env.ref('pb_conduct.group_conduct_head')
        for xmlid in ('hr.group_hr_user', 'hr.group_hr_manager', 'base.group_system',
                      'pb_lifecycle.group_lifecycle_admin', 'om_hr_payroll.group_hr_payroll_manager'):
            g = self.env.ref(xmlid, raise_if_not_found=False)
            if g:
                self.assertNotIn(user_g, g.all_implied_ids, xmlid)
                self.assertNotIn(head_g, g.all_implied_ids, xmlid)
