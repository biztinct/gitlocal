# -*- coding: utf-8 -*-
"""WDGAP W3-A — owner ruling CD1: a second named person signs off every
decision whose letter carries a consequence (warnings and dismissal) before
the letter is issued and before the employee can see anything.

Every "cannot" is proved after `flush_all()` + `invalidate_all()` (ledger
W2M-1), through the board's server calls AND the model methods.
"""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged, TransactionCase

from .common import make_fixture

NEUTRAL_BANNED = ('warning', 'disciplin', 'conduct', 'dismiss', 'hearing', 'DEMO')
CONDUCT_MODELS = ('pb.conduct.case', 'pb.conduct.note', 'pb.conduct.event',
                  'pb.conduct.letter')


@tagged('post_install', '-at_install', 'pb_conduct')
class TestConductSignoff(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mail_before = cls.env['mail.mail'].sudo().search_count([])
        make_fixture(cls)

    # ------------------------------------------------------------ helpers
    def _fresh(self):
        self.env.flush_all()
        self.env.invalidate_all()

    def _env(self, user, companies=None):
        companies = companies or self.company
        return self.env(user=user.id, su=False, context=dict(
            self.env.context, allowed_company_ids=companies.ids))

    def _F(self, user, companies=None):
        return self._env(user, companies)['pb.conduct']

    def _blocked(self, fn):
        try:
            with self.env.cr.savepoint():
                fn()
        except (AccessError, UserError, ValidationError):
            return True
        return False

    def _decided(self, outcome='written', who=None, emp=None, summary='SECRET-DECISION text'):
        """A new case, decided by `who` (first named person), not yet asked."""
        F = self._F(who or self.u_named)
        cid = F.create_case({'employee_id': (emp or self.e_other).id,
                             'reason_id': self.reason.id, 'summary': 'SECRET-CASE'})['id']
        F.move(cid, 'skip_hearing', {'why': 'Clear facts'})
        F.move(cid, 'decide', {'outcome': outcome, 'summary': summary})
        return self.env['pb.conduct.case'].browse(cid)

    def _waiting(self, outcome='written', who=None, emp=None):
        case = self._decided(outcome, who, emp)
        self._F(who or self.u_named).move(case.id, 'ask_signoff')
        return case

    def _rows(self, user, emp=None):
        """The "Needs you" rows `user` gets: the whole hook chain when `emp`
        is their own record, else just this module's sign-off row."""
        rows = {}

        def put(key, n, url, **kw):
            if n:
                rows[key] = dict(kw, n=n, url=url)
        Home = self.env['pb.me.home'].with_user(user)
        if emp:
            Home._pbme_needs_extra(emp, put)
        else:
            Home._pbme_conduct_signoff(put)
        return rows

    # ------------------------------------------------------------ 100: which decisions
    def test_100_which_decisions_need_a_second_sign_off(self):
        """Warnings of every kind and dismissal: yes. No action: no."""
        for outcome in ('verbal', 'written', 'final', 'dismissal'):
            case = self._decided(outcome)
            self.assertTrue(case.signoff_required, outcome)
            self.assertEqual(case.state, 'letter')
            letter = case.letter_ids.filtered(lambda l: l.kind == outcome)
            self.assertTrue(self._blocked(lambda: self.F.issue_letter(letter.id)), outcome)
            self.assertTrue(self._blocked(lambda: letter.with_user(self.u_named).action_issue()))
            self.assertEqual(letter.state, 'draft')
        none = self._decided('none')
        self.assertFalse(none.signoff_required)
        self.F.issue_letter(none.letter_ids.id)               # issued directly, as before
        self.assertEqual(none.state, 'closed')

    def test_101_until_confirmed_the_employee_sees_nothing(self):
        case = self._waiting(emp=self.e_subject)
        letter = case.letter_ids
        self.assertFalse(letter.attachment_id)
        self.assertFalse(letter.document_id)
        mine = self.env['pb.conduct.letter'].my_letters(self.e_subject)
        self.assertNotIn(letter.id, [r['id'] for r in mine['letters']])
        self.assertNotIn('SECRET-DECISION', repr(mine))
        Doc = self.env['pb.employee.document'].sudo()
        self.assertFalse(Doc.search([('employee_id', '=', self.e_subject.id),
                                     ('name', '=', letter.title),
                                     ('id', '!=', self.vault_doc.id)]))
        # the employee's home shows only the letters already issued (fixture: 2)
        rows = self._rows(self.u_subject_portal, self.e_subject)
        self.assertEqual(rows['hr_letters']['n'], 2)
        self.assertNotIn('hr_signoff', rows)

    # ------------------------------------------------------------ 102-104: the flow
    def test_102_waiting_letter_is_frozen_and_the_first_person_cannot_sign(self):
        case = self._waiting()
        self.assertEqual(case.state, 'signoff')
        self.assertEqual(case.signoff_state, 'waiting')
        self.assertEqual(case.signoff_asked_by, self.u_named)
        letter = case.letter_ids
        F = self.F
        self.assertTrue(self._blocked(lambda: F.save_letter(letter.id, 't', 'b')))
        self.assertTrue(self._blocked(lambda: F.delete_letter(letter.id)))
        self.assertTrue(self._blocked(lambda: F.issue_letter(letter.id)))
        self.assertTrue(self._blocked(lambda: F.move(case.id, 'confirm_signoff')))
        self.assertTrue(self._blocked(lambda: F.move(case.id, 'send_back', {'why': 'x'})))
        self.assertTrue(self._blocked(lambda: F.move(case.id, 'close', {'why': 'x'})))
        data = F.get_case(case.id)
        self.assertFalse(data['can']['confirm_signoff'])
        self.assertTrue(data['can']['withdraw_signoff'])
        self.assertFalse(data['letters'][0]['can_issue'])
        self.assertFalse(data['letters'][0]['can_edit'])
        # the second person sees the buttons
        data2 = self.F2.get_case(case.id)
        self.assertTrue(data2['can']['confirm_signoff'])
        self.assertTrue(data2['signoff']['can_sign'])
        self.assertFalse(data2['signoff']['blocker'])

    def test_102b_the_person_who_asked_cannot_sign_either(self):
        """Decided by one named person, sent by another: neither may sign."""
        case = self._decided()
        # the board counts it as "to send for a second sign-off", not "to issue"
        kpis = self.F.get_board()['kpis']
        self.assertEqual((kpis['to_ask'], kpis['letters']), (1, 0))
        self.F2.move(case.id, 'ask_signoff')
        self.assertEqual(self.F.get_board()['kpis']['signoff'], 1)
        self.assertEqual(case.signoff_asked_by, self.u_named2)
        self.assertTrue(self._blocked(lambda: self.F2.move(case.id, 'confirm_signoff')))
        self.assertTrue(self._blocked(lambda: self.F.move(case.id, 'confirm_signoff')))
        # a third named person (the head) can
        self._F(self.u_head).move(case.id, 'confirm_signoff')
        self.assertEqual(case.state, 'closed')
        self.assertEqual(case.signoff_by, self.u_head)

    def test_103_confirm_issues_the_letter_and_the_employee_sees_it(self):
        case = self._waiting(emp=self.e_subject)
        letter = case.letter_ids
        self.F2.move(case.id, 'confirm_signoff')
        self.assertEqual(case.signoff_state, 'confirmed')
        self.assertEqual(case.signoff_by, self.u_named2)
        self.assertTrue(case.signoff_on)
        self.assertEqual(letter.state, 'issued')
        self.assertTrue(letter.document_id)
        self.assertEqual(case.state, 'closed')
        mine = self.env['pb.conduct.letter'].my_letters(self.e_subject)
        self.assertIn(letter.id, [r['id'] for r in mine['letters']])
        texts = ' | '.join(case.event_ids.mapped('text'))
        for word in ('Sent for a second sign-off', 'Decision confirmed by a second named person',
                     'Letter issued', 'Case closed'):
            self.assertIn(word, texts)
        # confirmed once: no second confirm, no send back
        self.assertTrue(self._blocked(lambda: self.F2.move(case.id, 'confirm_signoff')))

    def test_104_sent_back_with_a_reason_returns_to_the_first_person(self):
        case = self._waiting(emp=self.e_subject)
        self.assertTrue(self._blocked(lambda: self.F2.move(case.id, 'send_back', {'why': ' '})))
        self.F2.move(case.id, 'send_back', {'why': 'Name the dates in the letter.'})
        self.assertEqual(case.state, 'letter')
        self.assertEqual(case.signoff_state, 'sent_back')
        self.assertEqual(case.signoff_note, 'Name the dates in the letter.')
        data = self.F.get_case(case.id)
        self.assertEqual(data['signoff']['note'], 'Name the dates in the letter.')
        self.assertTrue(data['can']['ask_signoff'])
        self.assertTrue(data['letters'][0]['can_edit'])
        self.assertFalse(data['letters'][0]['can_issue'])
        self.assertIn('Sent back', self.F.get_cases_page()['rows'][0]['next'])
        # still nothing for the employee
        self.assertEqual(case.letter_ids.state, 'draft')
        # the first person fixes the wording and asks again; the second confirms
        letter = case.letter_ids
        self.F.save_letter(letter.id, letter.title, letter.body + '\nDates: 3, 5 and 9 May.')
        self.F.move(case.id, 'ask_signoff')
        self.assertFalse(case.signoff_note)
        self.F2.move(case.id, 'confirm_signoff')
        self.assertEqual(letter.state, 'issued')
        self.assertIn('Dates: 3, 5 and 9 May.', letter.body)

    # ------------------------------------------------------------ 105-107: who can never sign
    def test_105_one_named_person_only_cannot_confirm(self):
        co = self.env['res.company'].create({'name': 'DEMO Conduct Solo Co'})
        solo = new_test_user(self.env, login='w3a_solo', groups='base.group_user,'
                             'pb_conduct.group_conduct_user', company_id=co.id,
                             company_ids=[(6, 0, co.ids)])
        emp = self.env['hr.employee'].create({'name': 'DEMO Solo Staff', 'company_id': co.id})
        F = self._F(solo, co)
        cid = F.create_case({'employee_id': emp.id, 'reason_id': self.reason.id,
                             'summary': 'x'})['id']
        F.move(cid, 'skip_hearing', {'why': 'x'})
        F.move(cid, 'decide', {'outcome': 'final', 'summary': 'Final.'})
        before = F.get_case(cid)['signoff']
        self.assertIn('Access screen', before['blocker'])
        self.assertIn('second person', before['blocker'])
        F.move(cid, 'ask_signoff')
        case = self.env['pb.conduct.case'].browse(cid)
        self.assertFalse(case._signers())
        data = F.get_case(cid)
        self.assertIn('Access screen', data['signoff']['blocker'])
        self.assertTrue(self._blocked(lambda: F.move(cid, 'confirm_signoff')))
        # the system itself is not a second person either
        self.assertTrue(self._blocked(lambda: case.sudo().action_confirm_signoff()))
        self.assertEqual(case.letter_ids.state, 'draft')
        # name a second person: the case can now be confirmed by them
        second = new_test_user(self.env, login='w3a_solo2', groups='base.group_user,'
                               'pb_conduct.group_conduct_user', company_id=co.id,
                               company_ids=[(6, 0, co.ids)])
        self._fresh()
        self.assertFalse(F.get_case(cid)['signoff']['blocker'])
        self._F(second, co).move(cid, 'confirm_signoff')
        self.assertEqual(case.letter_ids.state, 'issued')

    def test_106_a_named_person_who_is_the_subject_never_signs(self):
        """The head decides a case ABOUT the first named person: that person
        cannot see it, count it, or sign it; the second named person can."""
        case = self._waiting('written', who=self.u_head, emp=self.e_named_self)
        self._fresh()
        F = self.F
        self.assertNotIn(self.u_named, case._signers())
        self.assertTrue(self._blocked(lambda: F.get_case(case.id)))
        self.assertTrue(self._blocked(lambda: F.move(case.id, 'confirm_signoff')))
        self.assertTrue(self._blocked(lambda: case.with_user(self.u_named).with_context(
            allowed_company_ids=self.company.ids).action_confirm_signoff()))
        self.assertEqual(F.get_board()['kpis']['to_sign'], 0)
        self.assertFalse(self._rows(self.u_named, self.e_named_self).get('hr_signoff'))
        self.assertEqual(self.F2.get_board()['kpis']['to_sign'], 1)
        self.F2.move(case.id, 'confirm_signoff')
        self.assertEqual(case.state, 'closed')

    def test_107_the_employee_is_never_a_signer(self):
        """Even an employee who IS named is taken off their own case's list."""
        case = self._waiting('verbal', emp=self.e_named2)
        self.assertNotIn(self.u_named2, case._signers())
        self.assertIn(self.u_head, case._signers())
        self.assertTrue(self._blocked(lambda: self.F2.move(case.id, 'confirm_signoff')))
        # the portal employee: no right at all
        self.assertTrue(self._blocked(lambda: self._F(self.u_subject_portal).move(
            self.case.id, 'confirm_signoff')))

    def test_108_nobody_unnamed_can_ask_confirm_or_send_back(self):
        case = self._waiting()
        sent = self._decided()
        for user in (self.u_hr, self.u_hr_mgr, self.u_life, self.u_pay, self.u_manager,
                     self.u_admin, self.u_tenant, self.u_other_portal, self.u_subject_portal,
                     self.u_subject2_internal):
            self._fresh()
            F = self._F(user)
            for verb, args in (('confirm_signoff', {}), ('send_back', {'why': 'x'}),
                               ('withdraw_signoff', {})):
                self.assertTrue(self._blocked(lambda v=verb, a=args: F.move(case.id, v, a)),
                                (user.login, verb))
            self.assertTrue(self._blocked(lambda: F.move(sent.id, 'ask_signoff')), user.login)
            self.assertTrue(self._blocked(lambda: case.with_user(user).action_confirm_signoff()),
                            user.login)
            self.assertFalse(self._rows(user).get('hr_signoff'), user.login)
        self.assertEqual(case.state, 'signoff')

    # ------------------------------------------------------------ 109-112: edges
    def test_109_cases_decided_before_this_change_stay_as_they_are(self):
        """A case decided before the second sign-off existed (no flag) still
        issues its letter directly."""
        case = self._decided('written')
        case.sudo().write({'signoff_required': False})       # as every older case reads
        self._fresh()
        data = self.F.get_case(case.id)
        self.assertFalse(data['signoff']['required'])
        self.assertFalse(data['can']['ask_signoff'])
        self.assertTrue(data['letters'][0]['can_issue'])
        self.F.issue_letter(case.letter_ids.id)
        self.assertEqual(case.state, 'closed')

    def test_110_closing_without_the_sign_off_drops_the_decision(self):
        case = self._decided('final')
        live_before = self.F.get_board()['kpis']['live']
        self.assertTrue(self._blocked(lambda: self.F.move(case.id, 'close', {})))
        self.F.move(case.id, 'close', {'why': 'The employee resigned.'})
        self.assertEqual(case.state, 'closed')
        self.assertFalse(case.outcome)
        self.assertFalse(case.valid_until)
        self.assertFalse(case.letter_ids)
        self.assertIn('does not count', ' '.join(case.event_ids.mapped('text')))
        # the closed, unconfirmed "final warning" is NOT a warning still valid
        self.assertEqual(self.F.get_board()['kpis']['live'], live_before)
        self.F.move(case.id, 'reopen')
        self.assertEqual(case.state, 'concern')

    def test_111_change_the_decision(self):
        case = self._decided('dismissal')
        self.F.move(case.id, 'change_decision')
        self.assertEqual(case.state, 'decision')
        self.assertFalse(case.outcome)
        self.assertFalse(case.letter_ids)
        self.assertEqual(case.decision_summary, 'SECRET-DECISION text')   # kept to start from
        self.F.move(case.id, 'decide', {'outcome': 'written', 'summary': 'A warning instead.'})
        self.assertTrue(case.signoff_required)
        # once the decision letter is issued, the decision is fixed — even
        # with the case opened again
        self.F.move(self.case.id, 'reopen')
        self.assertEqual(self.case.state, 'letter')
        self.assertFalse(self.F.get_case(self.case.id)['can']['change_decision'])
        self.assertTrue(self._blocked(lambda: self.F.move(self.case.id, 'change_decision')))

    def test_112_taking_it_back(self):
        case = self._waiting()
        self.F.move(case.id, 'withdraw_signoff')
        self.assertEqual(case.state, 'letter')
        self.assertFalse(case.signoff_state)
        self.assertFalse(case.signoff_asked_by)
        self.F.save_letter(case.letter_ids.id, 'New title', 'New text')

    # ------------------------------------------------------------ 113: needs you
    def test_113_needs_you_for_the_second_person_only(self):
        case = self._waiting()
        self._fresh()
        # the board: a glance figure and a filter, for the second person only
        self.assertEqual(self.F2.get_board()['kpis']['to_sign'], 1)
        self.assertEqual(self.F.get_board()['kpis']['to_sign'], 0)
        page = self.F2.get_cases_page(filters={'mine': ['to_sign']})
        self.assertEqual([r['id'] for r in page['rows']], [case.id])
        self.assertTrue(page['rows'][0]['to_sign'])
        self.assertEqual(self.F.get_cases_page(filters={'mine': ['to_sign']})['rows'], [])
        # My Payobook: one neutral row that opens the board
        rows = self._rows(self.u_named2, self.e_named2)
        row = rows['hr_signoff']
        self.assertEqual(row['n'], 1)
        self.assertIn('action_pb_conduct_board', row['url'])
        words = ' '.join(str(row.get(k) or '') for k in ('label', 'sub', 'sentence'))
        for banned in NEUTRAL_BANNED:
            self.assertNotIn(banned.lower(), words.lower(), banned)
        self.assertNotIn(self.e_other.name, words)
        self.assertNotIn('hr_signoff', self._rows(self.u_named, self.e_named_self))
        # once confirmed, the row goes away
        self.F2.move(case.id, 'confirm_signoff')
        self.assertNotIn('hr_signoff', self._rows(self.u_named2, self.e_named2))

    # ------------------------------------------------------------ 114: no inbox, no mail
    def test_114_kept_out_of_the_approvals_inbox_and_nothing_sent(self):
        case = self._waiting()
        self.F2.move(case.id, 'send_back', {'why': 'x'})
        self.F.move(case.id, 'ask_signoff')
        self.F2.move(case.id, 'confirm_signoff')
        env = self.env
        for model in ('biz.approval.request', 'biz.approval.event'):
            if model in env:
                self.assertFalse(env[model].sudo().search_count(
                    [('res_model', 'like', 'pb.conduct')]), model)
        self.assertEqual(env['mail.mail'].sudo().search_count([]), self.mail_before)
        self.assertFalse(env['mail.message'].sudo().search_count([('model', 'like', 'pb.conduct')]))
        self.assertFalse(env['mail.activity'].sudo().search_count(
            [('res_model', 'like', 'pb.conduct')]))

    # ------------------------------------------------------------ 115: the matrix
    def test_115_privacy_matrix_with_the_new_steps(self):
        """Every role, against a case WAITING for the sign-off and one SENT
        BACK: the closed door stays closed; only the named people see it;
        the second person signs; the subject sees nothing."""
        waiting = self._waiting(emp=self.e_subject)
        sent = self._waiting(emp=self.e_subject)
        self.F2.move(sent.id, 'send_back', {'why': 'SECRET-SEND-BACK-REASON'})
        held = (waiting | sent).letter_ids
        self._fresh()
        closed_door = {
            'general HR': self.u_hr, 'HR manager': self.u_hr_mgr,
            'lifecycle user': self.u_life, 'payroll officer': self.u_pay,
            'line manager': self.u_manager, 'un-named administrator': self.u_admin,
            'tenant administrator': self.u_tenant, 'another employee': self.u_other_portal,
            'the employee': self.u_subject_portal,
        }
        for who, user in closed_door.items():
            env = self._env(user)
            for model in CONDUCT_MODELS:
                self.assertFalse(env[model].has_access('read'), (who, model))
            F = env['pb.conduct']
            self.assertEqual(set(F.get_board()), {'allowed', 'why'}, who)
            for case in (waiting, sent):
                self.assertTrue(self._blocked(lambda c=case: F.get_case(c.id)), who)
                self.assertTrue(self._blocked(lambda c=case: env['pb.conduct.case'].browse(
                    c.id).read(['signoff_note', 'decision_summary'])), who)
            self.assertFalse(self._rows(user).get('hr_signoff'), who)
        # the employee: the held letters are nowhere for them
        mine = self.env['pb.conduct.letter'].my_letters(self.e_subject)
        self.assertFalse(set(held.ids) & {r['id'] for r in mine['letters']})
        self.assertNotIn('SECRET', repr(mine))
        # first named person: sees both, signs neither
        d = self.F.get_case(waiting.id)
        self.assertIn('SECRET-DECISION', d['decision_summary'])
        self.assertFalse(d['can']['confirm_signoff'])
        self.assertEqual(self.F.get_case(sent.id)['signoff']['note'], 'SECRET-SEND-BACK-REASON')
        # second named person: sees and can sign the waiting one
        self.assertTrue(self.F2.get_case(waiting.id)['can']['confirm_signoff'])
        # the head works in this company too: also a possible second person
        self.assertTrue(self._F(self.u_head).get_case(waiting.id)['can']['confirm_signoff'])
        # a named person who IS a case subject: covered by test_106 (sees nothing)
