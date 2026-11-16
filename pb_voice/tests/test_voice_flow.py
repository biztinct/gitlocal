# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""F-series: setting up and sending out, reminders with and without email,
rights as a real portal login, silent install, action plans, the library."""
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .common import VoiceCase


@tagged('post_install', '-at_install', 'pb_voice')
class TestVoiceFlow(VoiceCase):

    def _mail_off(self):
        self.env['ir.mail_server'].sudo().search([]).write({'active': False})

    def _mail_on(self):
        self.env['ir.mail_server'].sudo().create({
            'name': 'DEMO outgoing', 'smtp_host': 'localhost', 'smtp_port': 2525})

    def _voice_mails(self):
        return self.env['mail.mail'].sudo().search(
            [('email_to', 'like', 's9c_p%')])

    # ------------------------------------------------------------------ F1
    def test_F01_silent_install(self):
        """Installing creates no round, queues no email, draws nothing for an
        employee; the daily job runs on an empty table and does nothing."""
        Round = self.env['pb.voice.round'].sudo()
        self.assertFalse(Round.search([('company_id', '=', self.company.id)]))
        self.assertTrue(self.env['pb.voice.library'].sudo().search_count([]) >= 15,
                        'the library is offered')
        before = self.env['mail.mail'].sudo().search_count([])
        Round._cron_voice_daily()
        self.assertEqual(self.env['mail.mail'].sudo().search_count([]), before)
        emp = self.team_mai[0]
        Home = self.as_person(emp, self.env['pb.me.home'])
        cards = Home._pbme_extra_cards(emp)
        self.assertNotIn('voice', [c['key'] for c in cards])
        found = {}
        Home._pbme_needs_extra(emp, lambda key, n, url, **kw: n and found.setdefault(key, n))
        self.assertFalse([k for k in found if k.startswith('voice')])
        cron = self.env.ref('pb_voice.cron_voice_daily')
        self.assertEqual(cron.interval_type, 'days')
        # no demo data: library questions only, no round anywhere for this company
        self.assertFalse(self.env['pb.voice.action'].sudo().search(
            [('company_id', '=', self.company.id)]))

    # ------------------------------------------------------------------ F2
    def test_F02_send_out_rules(self):
        rnd = self.make_round()
        with self.assertRaises(ValidationError):
            rnd.floor = 3
        tiny = self.as_hr(self.Round).create({
            'name': 'DEMO tiny', 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'department_ids': [(6, 0, [self.tiny.id])]})
        self.as_hr(self.env['pb.voice.question']).create(
            {'round_id': tiny.id, 'kind': 'scale', 'text': 'Q'})
        with self.assertRaises(UserError):
            tiny.action_open()          # 2 people: below the floor
        rnd.action_open()
        self.assertEqual(rnd.state, 'open')
        self.assertEqual(rnd.invited_count, 27)
        # locked once sent out
        with self.assertRaises(UserError):
            self.as_hr(self.q_scale).write({'text': 'changed'})
        with self.assertRaises(UserError):
            self.as_hr(rnd).write({'department_ids': [(6, 0, [self.ops.id])]})
        with self.assertRaises(UserError):
            self.as_hr(rnd).unlink()
        # a plain staff login cannot send one out
        plain = new_test_user(self.env, login='s9c_plain2',
                              company_id=self.company.id, groups='base.group_user')
        draft = self.make_round()
        with self.assertRaises(AccessError):
            draft.with_user(plain).action_open()

    # ------------------------------------------------------------------ F3
    def test_F03_answer_checks(self):
        rnd = self.open_round()
        emp = self.team_mai[0]
        r = self.as_person(emp, self.Round).browse(rnd.id)
        with self.assertRaises(UserError):
            r.voice_submit(emp, {str(self.q_scale.id): 9,
                                 str(self.q_enps.id): 5}, {})
        with self.assertRaises(UserError):
            r.voice_submit(emp, {str(self.q_enps.id): 5}, {})   # rating missing
        # somebody else's employee: refused
        other = self.team_mai[1]
        with self.assertRaises(AccessError):
            r.voice_submit(other, {str(self.q_scale.id): 3,
                                   str(self.q_enps.id): 5}, {})
        # a person from another company is not asked
        stranger_co = self.env['res.company'].create({'name': 'DEMO Elsewhere'})
        su = new_test_user(self.env, login='s9c_stranger', company_id=stranger_co.id,
                           groups='base.group_portal')
        stranger = self.env['hr.employee'].create({
            'name': 'DEMO Stranger', 'company_id': stranger_co.id, 'user_id': su.id})
        with self.assertRaises(AccessError):
            rnd.with_user(su).voice_submit(stranger, {}, {})
        self.assertEqual(rnd.sudo().voice_form(stranger)['ok'], False)
        # closed: refused
        for e in self.team_mai[2:7]:
            self.answer(rnd, e)
        self.close(rnd)
        with self.assertRaises(UserError):
            self.answer(rnd, emp)
        self.assertTrue(self.as_person(emp, self.Round).browse(rnd.id)
                        .voice_form(emp).get('closed'))

    # ------------------------------------------------------------------ F4
    def test_F04_reminders_without_email_queue_nothing(self):
        self._mail_off()
        rnd = self.open_round()
        self.assertFalse(self._voice_mails(), 'no invitation queued')
        self.answer(rnd, self.team_mai[0])
        rnd.sudo().write({'last_reminded': fields.Date.today() - timedelta(days=5)})
        self.env['pb.voice.round']._cron_voice_daily()
        self.assertFalse(self._voice_mails(), 'no reminder queued')
        self.assertEqual(rnd.last_reminded, fields.Date.today())
        # the in-app reminder: the "Needs you" row, gone once answered
        waiting, done = self.team_mai[1], self.team_mai[0]
        found = {}
        self.as_person(waiting, self.env['pb.me.home'])._pbme_needs_extra(
            waiting, lambda key, n, url, **kw: found.setdefault(key, (n, url, kw)))
        self.assertIn('voice_survey', found)
        self.assertEqual(found['voice_survey'][1], '/my/voice/%s' % rnd.id)
        self.assertNotIn('Odoo', str(found['voice_survey'][2]))
        found = {}
        self.as_person(done, self.env['pb.me.home'])._pbme_needs_extra(
            done, lambda key, n, url, **kw: n and found.setdefault(key, n))
        self.assertNotIn('voice_survey', found)
        cards = self.as_person(waiting, self.env['pb.me.home'])._pbme_extra_cards(waiting)
        self.assertIn('voice', [c['key'] for c in cards])
        board = self.as_hr(self.Voice).get_round(rnd.id)
        self.assertFalse(board['who']['mail_on'])

    # ------------------------------------------------------------------ F5
    def test_F05_reminders_with_email_only_to_who_has_not_answered(self):
        self._mail_on()
        rnd = self.open_round()
        self.assertEqual(len(self._voice_mails()), 27, 'one invitation each')
        self._voice_mails().unlink()
        answered = self.team_mai[:3]
        for emp in answered:
            self.answer(rnd, emp)
        rnd.sudo().write({'last_reminded': fields.Date.today() - timedelta(days=3)})
        self.env['pb.voice.round']._cron_voice_daily()
        mails = self._voice_mails()
        self.assertEqual(len(mails), 24)
        to = set(mails.mapped('email_to'))
        for emp in answered:
            self.assertNotIn(emp.work_email, to)
        self.assertTrue(all(m.auto_delete for m in mails))
        for m in mails:
            self.assertNotIn('Odoo', m.body_html + m.subject)
        # not again tomorrow (every 3 days)
        mails.unlink()
        self.env['pb.voice.round']._cron_voice_daily()
        self.assertFalse(self._voice_mails())

    # ------------------------------------------------------------------ F6
    def test_F06_end_date_closes_the_round(self):
        rnd = self.open_round()
        for emp in self.team_mai[:5]:
            self.answer(rnd, emp)
        rnd.sudo().write({'date_end': fields.Date.today() - timedelta(days=1)})
        self.env['pb.voice.round']._cron_voice_daily()
        self.assertEqual(rnd.state, 'closed')
        self.assertEqual(rnd.result_state, 'kept')
        self.Box._voice_destroy(rnd.id)

    # ------------------------------------------------------------------ F7
    def test_F07_portal_login_has_no_model_rights(self):
        rnd = self.open_round()
        user = self.users[self.team_mai[0].id]
        self.env.flush_all()
        self.env.invalidate_all()
        for model in ('pb.voice.round', 'pb.voice.question', 'pb.voice.invite',
                      'pb.voice.group', 'pb.voice.box', 'pb.voice.action',
                      'pb.voice.library'):
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(user).check_access('read')
        with self.assertRaises(AccessError):
            self.Voice.with_user(user).get_round(rnd.id)
        self.assertFalse(self.Voice.with_user(user).get_board()['allowed'])
        # the portal methods answer only for the caller's own employee
        R = self.Round.with_user(user)
        self.assertIsNone(R.voice_my_rounds(self.team_mai[1]))
        self.assertEqual(len(R.voice_my_rounds(self.team_mai[0])), 1)

    # ------------------------------------------------------------------ F8
    def test_F08_action_plans(self):
        rnd = self.open_round()
        for emp in self.team_mai[:5]:
            self.answer(rnd, emp)
        self.close(rnd)
        owner = new_test_user(self.env, login='s9c_owner', company_id=self.company.id,
                              company_ids=[(6, 0, [self.company.id])],
                              groups='base.group_user')
        owner_emp = self.env['hr.employee'].create({
            'name': 'DEMO Owner', 'company_id': self.company.id, 'user_id': owner.id})
        V = self.as_hr(self.Voice)
        plan = V.save_action(rnd.id, {'name': 'Monthly catch-ups',
                                      'theme': 'manager', 'owner_id': owner.id,
                                      'date_due': '2030-01-31'})
        act = self.env['pb.voice.action'].browse(plan['id'])
        self.assertTrue(act.activity_ids, 'a to-do for the owner')
        self.assertEqual(act.activity_ids.user_id, owner)
        # the owner sees it on My Payobook and may move it on
        found = {}
        self.env['pb.me.home'].with_user(owner)._pbme_needs_extra(
            owner_emp, lambda key, n, url, **kw: n and found.setdefault(key, n))
        self.assertEqual(found.get('voice_actions'), 1)
        mine = act.with_user(owner).with_context(allowed_company_ids=[self.company.id])
        mine.write({'state': 'doing', 'progress': 'First one held'})
        with self.assertRaises(AccessError):
            mine.write({'name': 'renamed'})
        # somebody else cannot read it
        other = new_test_user(self.env, login='s9c_other', company_id=self.company.id,
                              groups='base.group_user')
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertFalse(self.env['pb.voice.action'].with_user(other).search(
            [('id', '=', act.id)]))
        with self.assertRaises(AccessError):
            self.env['pb.voice.action'].with_user(other).create(
                {'round_id': rnd.id, 'name': 'x', 'owner_id': other.id})
        # done: the to-do goes
        self.as_hr(act).write({'state': 'done'})
        self.assertFalse(act.activity_ids)
        # an employee (portal) login cannot own one
        with self.assertRaises(UserError):
            self.as_hr(act).write({'owner_id': self.users[self.mai.id].id})

    # ------------------------------------------------------------------ F9
    def test_F09_library_brings_every_language(self):
        rnd = self.make_round(comment=False)
        lib = self.env.ref('pb_voice.lib_proud')
        langs = [c for c, _n in self.env['res.lang'].get_installed()]
        pick = self.as_hr(self.env['pb.voice.library.pick']).create(
            {'round_id': rnd.id, 'library_ids': [(6, 0, [lib.id])]})
        pick.action_add()
        q = rnd.question_ids.filtered(lambda x: x.library_id == lib)
        self.assertEqual(len(q), 1)
        for lang in langs:
            self.assertEqual(q.with_context(lang=lang).text,
                             lib.with_context(lang=lang).text, lang)
        if 'vi_VN' in langs:
            self.assertNotEqual(q.with_context(lang='vi_VN').text, q.text)
        # adding twice does not duplicate
        pick.action_add()
        self.assertEqual(len(rnd.question_ids.filtered(lambda x: x.library_id == lib)), 1)
        # company values from Praise, when Praise is installed
        if 'pb.company.value' in self.env:
            self.env['pb.company.value'].sudo().create(
                {'name': 'DEMO Care', 'company_id': self.company.id})
            pick.action_add_values()
            self.assertTrue(rnd.question_ids.filtered(
                lambda x: x.theme == 'values' and 'DEMO Care' in x.text))

    # ----------------------------------------------------------------- F10
    def test_F10_board_and_who_can_answer(self):
        # two people lose their login: they show under "no login yet"
        for emp in self.general[:2]:
            emp.user_id.active = False
        rnd = self.make_round()
        V = self.as_hr(self.Voice)
        who = V.get_round(rnd.id)['who']
        self.assertEqual(who['asked'], 27)
        self.assertEqual(who['without_login'], 2)
        self.assertEqual({w['name'] for w in who['without_names']},
                         {e.name for e in self.general[:2]})
        board = V.get_board()
        row = [r for r in board['rounds'] if r['id'] == rnd.id][0]
        self.assertEqual(row['state'], 'draft')
        self.assertEqual(board['kpis']['draft'] >= 1, True)
        moved = V.round_move(rnd.id, 'open')
        self.assertIn('My Payobook', moved['msg'])
        copy = V.round_move(rnd.id, 'copy')
        new = self.env['pb.voice.round'].browse(copy['id'])
        type(self)._rounds.append(new.id)
        self.assertEqual(new.state, 'draft')
        self.assertEqual(len(new.question_ids), len(rnd.question_ids))
        self.assertTrue(V.round_move(new.id, 'delete')['deleted'])
