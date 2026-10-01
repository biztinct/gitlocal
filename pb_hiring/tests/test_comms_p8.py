# -*- coding: utf-8 -*-
"""RECRUIT P8 — every candidate email in three languages, the Emails screen,
the automations, the hooks, and the four leftovers (G-44, RC80, the share
email, the agency counts).

Numbered as in `docs/handovers/recruit/RECRUIT_P8_COMMS.md` §5 (1–9; test 9
is the rest of the suite). Mails stay in the queue (cancelled at tearDown);
nothing leaves the box.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_interviews import InterviewCase
from .test_joining_p6 import JoiningCase


def _migration(name):
    import importlib.util
    from odoo.modules.module import get_module_path
    path = '%s/migrations/19.0.2.7.0/%s.py' % (get_module_path('pb_hiring'), name)
    spec = importlib.util.spec_from_file_location('pb_hiring_p8_%s' % name.replace('-', '_'), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CommsCase(InterviewCase):

    def setUp(self):
        super().setUp()
        from ..models.comms_p8 import lang_installed
        self.langs = lang_installed(self.env)
        self.facade = self.env['pb.hiring']
        self.Tpl = self.env['pb.hiring.message.template'].sudo()
        self.Rule = self.env['pb.hiring.automation.rule'].sudo()
        self.Run = self.env['pb.hiring.automation.run'].sudo()
        self.Stage = self.env['hr.recruitment.stage']
        stamp = str(fields.Datetime.now().timestamp()).replace('.', '')
        self.lead = self.env['res.users'].sudo().create({
            'name': 'RECRUIT P8 Lead', 'login': 'recruit.p8.lead.%s' % stamp,
            'email': 'recruit.p8.lead@example.com',
            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
            'group_ids': [(4, self.env.ref('base.group_user').id),
                          (4, self.env.ref('pb_hiring.group_hiring_manager').id)]})
        self.env['pb.hiring']._seed_p8()
        # This class's own rules only: the company's seeded rows stay as they
        # are, the Calendly one switched off so a move to Recruiter review is
        # quiet unless a test says otherwise.
        self.Rule.search([('company_id', '=', self.company.id),
                          ('seed_key', '=', 'calendly')]).write({'active': False})

    def _tpl(self, key):
        return self.Tpl.search([('company_id', '=', self.company.id), ('key', '=', key)], limit=1)

    def _since(self):
        return self.env['mail.mail'].sudo().search([]).ids

    def _new(self, before):
        return self.env['mail.mail'].sudo().search([('id', 'not in', before)])

    def _rule(self, **vals):
        base = {'company_id': self.company.id, 'event': 'stage_entered', 'action': 'todo',
                'recipient': 'recruiter', 'todo_text': 'RECRUIT P8 look', 'active': True}
        base.update(vals)
        return self.Rule.create(base)

    def _move(self, key, app=None):
        (app or self.applicant).sudo().write({'stage_id': self.Stage._pb_stage(key).id})


# =========================================================================
#  1 — one mechanism, three languages, the seed and the migration
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p8')
class TestRecruitCommsP8(CommsCase):

    def test_01_every_key_seeded_in_three_languages_and_the_old_templates_archived(self):
        from ..models.comms_i18n_p8 import EMAIL_KEYS, NEW_EMAILS
        for key in EMAIL_KEYS:
            self.assertTrue(self._tpl(key), 'no %s email for the company' % key)
        again = self.env['pb.hiring']._seed_p8()
        self.assertEqual((again['made'], again['filled'], again['archived']), (0, 0, 0),
                         'the seed is not idempotent')
        for key in NEW_EMAILS:
            tpl = self._tpl(key)
            for lg in self.langs:
                self.assertTrue(tpl._pb_has_lang(lg), '%s has no %s' % (key, lg))
        for xmlid in ('pb_hiring.mail_template_offer_candidate',
                      'pb_hiring.mail_template_docreq_ask',
                      'pb_hiring.mail_template_candidate_rejected'):
            self.assertFalse(self.env.ref(xmlid).active, xmlid)
        # the shared interview mails still go to the panel
        self.assertTrue(self.env.ref('pb_hiring.mail_template_interview_tomorrow').active)
        # the migration runs again harmlessly
        mod = _migration('post-10_comms')
        mod.migrate(self.env.cr, '19.0.2.6.0')

    def test_01b_the_language_is_theirs_then_their_contact_then_english(self):
        app = self.applicant.sudo()
        app.write({'pb_lang': False})
        self.assertEqual(self.facade._pb_candidate_lang(app), 'en_US')
        if 'id_ID' in self.langs:
            app.partner_id.write({'lang': 'id_ID'})
            self.assertEqual(self.facade._pb_candidate_lang(app), 'id_ID')
        if 'vi_VN' not in self.langs:
            return
        app.write({'pb_lang': 'vi_VN'})
        self.assertEqual(self.facade._pb_candidate_lang(app), 'vi_VN')
        before = self._since()
        res = self.facade._mail_candidate('next_round', app)
        self.assertEqual((res['status'], res['lang']), ('sent', 'vi_VN'))
        mail = self._new(before)
        self.assertIn('Tin vui', mail.subject)
        self.assertEqual(mail.email_to, app.email_from)
        # a missing Vietnamese version: English goes, and the timeline says so
        tpl = self._tpl('next_round')
        for fname in ('subject', 'body', 'button'):
            tpl.update_field_translations(fname, {'vi_VN': False})
        before = self._since()
        res = self.facade._mail_candidate('next_round', app)
        self.assertTrue(res['fell_back'])
        self.assertIn('Good news about', self._new(before).subject)
        note = app.message_ids.filtered(lambda m: 'English went instead' in (m.body or ''))
        self.assertTrue(note, 'the timeline does not say English stood in')

    # ------------------------------------------------------------- test 2
    def test_02_interview_mails_in_their_language_panel_in_english(self):
        if 'vi_VN' not in self.langs:
            return
        self.applicant.sudo().write({'pb_lang': 'vi_VN'})
        before = self._since()
        interview = self._schedule()
        mails = self._new(before)
        mine = mails.filtered(lambda m: m.email_to == self.applicant.email_from)
        self.assertEqual(len(mine), 1)
        self.assertIn('Lịch phỏng vấn', mine.subject)
        self.assertTrue(mine.attachment_ids, 'the calendar file is missing')
        self.assertIn('RIZE W2 A2 Room', mine.body_html)
        panel = mails - mine
        self.assertTrue(panel)
        self.assertFalse(any('Lịch' in (m.subject or '') for m in panel), 'the panel got Vietnamese')
        before = self._since()
        interview._remind('24h')
        mails = self._new(before)
        mine = mails.filtered(lambda m: m.email_to == self.applicant.email_from)
        self.assertIn('Ngày mai', mine.subject)
        self.assertTrue(any('Tomorrow' in (m.subject or '') for m in mails - mine))
        before = self._since()
        interview._tell_everybody_it_is_off()
        mine = self._new(before).filtered(lambda m: m.email_to == self.applicant.email_from)
        self.assertIn('Thay đổi', mine.subject)
        self.assertIn('liên hệ lại', mine.body_html)

    # ------------------------------------------------------------- test 3
    def test_03_switch_rejection_per_stage_and_on_hold_on_request(self):
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.candidate_mail', '0')
        before = self._since()
        res = self.facade._mail_candidate('docreq_ask', self.applicant)
        self.assertEqual(res['status'], 'mail_off')
        self.assertFalse(self._new(before))
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.candidate_mail', '1')
        self.applicant.sudo().write({'pb_lang': 'en_US'})
        rec = self.facade.with_user(self.recruiter)
        before = self._since()
        rec.act('journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'cv_reject',
                                  'send_email': True})
        self.assertIn('Your application to', self._new(before).subject)
        before = self._since()
        rec.act('journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'interview_reject',
                                  'send_email': True})
        self.assertIn('About your application for', self._new(before).subject)
        # on hold without a reason: nothing goes, and the toast says what is missing
        before = self._since()
        res = rec.act('journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'on_hold',
                                        'send_email': True})
        self.assertIn('add a reason', res['note'])
        self.assertFalse(self._new(before))
        rec.act('journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'shortlist'})
        before = self._since()
        res = rec.act('journey_stage', {
            'applicant_ids': [self.applicant.id], 'key': 'on_hold', 'send_email': True,
            'reason': 'the hiring manager is travelling',
            'hold_until': str(fields.Date.today() + timedelta(days=10))})
        self.assertIn('on-hold email went out', res['note'])
        mail = self._new(before)
        self.assertIn('honest update', mail.subject)
        self.assertIn('travelling', mail.body_html)

    # ------------------------------------------------------------- test 4
    def test_04_the_emails_screen(self):
        lead = self.facade.with_user(self.lead)
        data = lead.get_emails()
        keys = [r['key'] for r in data['rows']]
        self.assertIn('interview_invite', keys)
        self.assertIn('received', keys)
        self.assertTrue(data['can_edit'])
        self.assertTrue(data['internal'])
        row = next(r for r in data['rows'] if r['key'] == 'offer')
        self.assertEqual(row['langs']['en_US'], 'ok')
        tpl = self._tpl('offer')
        if 'id_ID' in self.langs:
            for fname in ('subject', 'body'):
                tpl.update_field_translations(fname, {'id_ID': False})
            row = next(r for r in lead.get_emails()['rows'] if r['key'] == 'offer')
            self.assertEqual(row['langs']['id_ID'], 'missing')
        # save one language, refuse an unknown detail
        lang = 'vi_VN' if 'vi_VN' in self.langs else 'en_US'
        res = lead.act('email_save', {'id': tpl.id, 'lang': lang, 'subject': 'P8 {{role}} subject',
                                      'body': 'Hello {{name}}, {{monthly}}.', 'button': 'Mở'})
        self.assertIn('before', res)
        self.assertEqual(tpl._pb_text(lang)['subject'], 'P8 {{role}} subject')
        self.assertTrue(tpl._pb_text('en_US')['subject'].startswith('Our offer'),
                        'saving one language changed English')
        with self.assertRaises(UserError):
            lead.act('email_save', {'id': tpl.id, 'lang': lang, 'subject': 'x {{salary}}',
                                    'body': 'y'})
        prev = lead.get_email_preview(tpl.id, lang)
        self.assertTrue(prev['ok'])
        self.assertIn('subject', prev['subject'])
        bad = lead.get_email_preview(tpl.id, lang, 'x {{nope}}', 'y', '')
        self.assertFalse(bad['ok'])
        # send me a test
        before = self._since()
        lead.act('email_test', {'id': tpl.id, 'lang': lang})
        mail = self._new(before)
        self.assertEqual(mail.email_to, 'recruit.p8.lead@example.com')
        # reset
        lead.act('email_reset', {'id': tpl.id})
        self.assertTrue(tpl._pb_text(lang)['subject'] != 'P8 {{role}} subject')
        for lg in self.langs:
            self.assertTrue(tpl._pb_has_lang(lg))
        # a recruiter reads but does not write
        with self.assertRaises(AccessError):
            self.facade.with_user(self.recruiter).act('email_save', {
                'id': tpl.id, 'lang': 'en_US', 'subject': 'x', 'body': 'y'})
        # the talent lead writes a hiring email and never another app's template
        other = self.env['mail.template'].sudo().search(
            [('model', 'not like', 'pb.hiring'), ('model', '!=', 'hr.applicant'),
             ('create_uid', '!=', self.lead.id)], limit=1)
        if other:
            with self.assertRaises(AccessError):
                other.with_user(self.lead).write({'subject': 'RECRUIT P8 hijack'})


# =========================================================================
#  5 — 8: the automations
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p8')
class TestRecruitAutomationsP8(CommsCase):

    def test_05a_the_seeds_and_the_match(self):
        seeds = self.Rule.with_context(active_test=False).search(
            [('company_id', '=', self.company.id), ('seed_key', '!=', False)])
        self.assertEqual(set(seeds.mapped('seed_key')),
                         {'calendly', 'assignment', 'first_look', 'buddy'})
        first = seeds.filtered(lambda r: r.seed_key == 'first_look')
        self.assertFalse(first.active)
        self.assertIn('has waited 7 days in', first.name)
        rule = self._rule(stage_id=self.Stage._pb_stage('shortlist').id)
        other_co = self._rule(stage_id=self.Stage._pb_stage('shortlist').id,
                              company_id=self.env['res.company'].sudo().create(
                                  {'name': 'RECRUIT P8 Other Co'}).id)
        self._move('shortlist')
        acts = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'hr.applicant'), ('res_id', '=', self.applicant.id),
            ('summary', 'like', 'RECRUIT P8 look')])
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts.user_id, self.recruiter)
        self.assertEqual(rule.run_count, 1)
        self.assertFalse(self.Run.search([('rule_id', '=', other_co.id)]))
        # a department filter that does not match: nothing
        dept_rule = self._rule(stage_id=self.Stage._pb_stage('assignment').id,
                               department_ids=[(6, 0, [self.env['hr.department'].create(
                                   {'name': 'RECRUIT P8 elsewhere'}).id])])
        self._move('assignment')
        self.assertFalse(self.Run.search([('rule_id', '=', dept_rule.id)]))

    def test_05b_once_per_candidate_delay_failure_waiting(self):
        sl = self.Stage._pb_stage('shortlist')
        rule = self._rule(stage_id=sl.id)
        self._move('shortlist')
        self._move('screening')
        self._move('shortlist')
        runs = self.Run.search([('rule_id', '=', rule.id)])
        self.assertEqual(sorted(runs.mapped('state')), ['done', 'skipped'])
        # a delay: queued, then the ten-minute leg runs it
        later = self._rule(stage_id=self.Stage._pb_stage('discussion_1').id, delay_hours=2,
                           todo_text='RECRUIT P8 later')
        self._move('discussion_1')
        run = self.Run.search([('rule_id', '=', later.id)])
        self.assertEqual(run.state, 'queued')
        run.write({'due_at': fields.Datetime.now() - timedelta(minutes=1)})
        self.env['pb.hiring.automation'].run_reminders()
        self.assertEqual(run.state, 'done')
        # a failing rule never stops the move
        boom = self._rule(stage_id=self.Stage._pb_stage('discussion_2').id)
        with patch.object(type(self.Rule), '_do', side_effect=RuntimeError('boom')):
            self._move('discussion_2')
        self.assertEqual(self.applicant.stage_id.pb_key, 'discussion_2')
        self.assertEqual(self.Run.search([('rule_id', '=', boom.id)]).state, 'failed')
        # has waited N days: once per stay
        wait = self._rule(event='stage_waiting', stage_id=self.Stage._pb_stage('discussion_2').id,
                          days=3, todo_text='RECRUIT P8 waited')
        self.env.flush_all()
        self.env.cr.execute("UPDATE hr_applicant SET date_last_stage_update = now() - interval '4 days' "
                            "WHERE id = %s", [self.applicant.id])
        self.applicant.invalidate_recordset()
        self.assertEqual(self.Rule._run_waiting(), 1)
        self.assertEqual(self.Rule._run_waiting(), 0)
        self.assertEqual(self.Run.search([('rule_id', '=', wait.id)]).state, 'done')

    def test_05c_builtins_map_to_the_switches_and_calendly_is_a_row(self):
        lead = self.facade.with_user(self.lead)
        lead.act('builtin_switch', {'key': 'reminders', 'on': False})
        self.assertEqual(self.env['ir.config_parameter'].sudo().get_param('pb_hiring.reminders'), '0')
        b = next(x for x in lead.get_automations()['builtins'] if x['key'] == 'reminders')
        self.assertFalse(b['on'])
        lead.act('builtin_switch', {'key': 'reminders', 'on': True})
        with self.assertRaises(UserError):
            lead.act('builtin_switch', {'key': 'invite', 'on': False})
        # the Calendly row is the P5 rule
        cal = self.Rule.with_context(active_test=False).search(
            [('company_id', '=', self.company.id), ('seed_key', '=', 'calendly')])
        self.recruiter.sudo().write({'pb_scheduling_link': 'https://calendly.com/p8/30min'})
        rec = self.facade.with_user(self.recruiter)
        res = rec.act('journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'phone'})
        self.assertNotIn('Calendly', res['note'], 'a switched-off row sent the email')
        rec.act('journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'shortlist'})
        lead.act('rule_toggle', {'id': cal.id, 'on': True})
        before = self._since()
        res = rec.act('journey_stage', {'applicant_ids': [self.applicant.id], 'key': 'phone'})
        self.assertIn('Calendly email went out', res['note'])
        self.assertIn('calendly.com/p8', self._new(before).body_html)
        # a recruiter cannot change the rules
        with self.assertRaises(AccessError):
            rec.act('rule_toggle', {'id': cal.id, 'on': False})

    def test_05d_a_rule_that_cannot_work_is_not_saved(self):
        lead = self.facade.with_user(self.lead)
        with self.assertRaises(UserError):
            lead.act('rule_save', {'event': 'stage_entered', 'action': 'todo',
                                   'recipient': 'recruiter', 'todo_text': 'x'})   # no stage
        with self.assertRaises(UserError):
            lead.act('rule_save', {'event': 'applied', 'action': 'todo', 'recipient': '',
                                   'todo_text': 'x'})                              # nobody
        with self.assertRaises(UserError):
            lead.act('rule_save', {'event': 'request_sent_in', 'action': 'send_email',
                                   'recipient': 'candidate', 'template_key': 'received'})
        res = lead.act('rule_save', {'event': 'stage_waiting', 'action': 'todo', 'days': 3,
                                     'stage_id': self.Stage._pb_stage('shortlist').id,
                                     'recipient': 'recruiter', 'todo_text': 'Give them a look'})
        rule = self.Rule.browse(res['id'])
        self.assertEqual(rule.name, 'When a candidate has waited 3 days in %s, give the recruiter '
                         'a to-do: “Give them a look”, right away.' % self.Stage._pb_stage('shortlist').name)

    # ------------------------------------------------------------- test 6
    def test_06_every_hook_fires(self):
        tag = self.env['hr.applicant.category'].sudo().create({'name': 'RECRUIT P8 hook'})

        def rule(event, **kw):
            # each rule its own tag: a tag already on the candidate is "skipped"
            own = self.env['hr.applicant.category'].sudo().create({'name': 'RECRUIT P8 %s' % event})
            vals = {'event': event, 'action': 'tag', 'tag_id': own.id, 'recipient': False,
                    'once_per_candidate': False}
            vals.update(kw)
            return self._rule(**vals)

        def ran(r):
            return self.Run.search_count([('rule_id', '=', r.id), ('state', '=', 'done')])

        applied = rule('applied')
        app = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P8 Applied', 'email_from': 'p8.applied@example.com',
            'job_id': self.req.job_id.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id})
        self.assertEqual(ran(applied), 1)
        self.assertIn(applied.tag_id, app.categ_ids)
        self.assertTrue(tag)
        entered = rule('stage_entered', stage_id=self.Stage._pb_stage('reference').id)
        self._move('reference', app)
        self.assertEqual(ran(entered), 1)
        sched = rule('interview_scheduled')
        done = rule('interview_done')
        allin = rule('opinions_all_in')
        interview = self._schedule()
        self.assertEqual(ran(sched), 1)
        interview.sudo().write({'start': fields.Datetime.now() - timedelta(hours=2),
                                'stop': fields.Datetime.now() - timedelta(hours=1)})
        interview.action_mark_done()
        self.assertEqual(ran(done), 1)
        for f in interview.feedback_ids:
            f.sudo().write({'state': 'submitted', 'decision': 'yes'})
        interview.feedback_ids[:1]._summarise_if_complete()
        self.assertEqual(ran(allin), 1)
        check = rule('check_started', action='todo', recipient='recruiter',
                     todo_text='RECRUIT P8 check', tag_id=False)
        bgv = self.env['pb.hiring.bgv'].open_for(self.req.id, self.applicant.id)
        self.assertEqual(ran(check), 1)
        # the built-in check-started to-do
        self.assertTrue(self.env['mail.activity'].sudo().search_count([
            ('res_model', '=', 'hr.applicant'), ('res_id', '=', self.applicant.id),
            ('summary', 'like', 'Background check started')]))
        self.env['pb.hiring.bgv'].open_for(self.req.id, self.applicant.id)
        self.assertEqual(ran(check), 1, 'opening the same check again fired again')
        sent_in = rule('request_sent_in', action='todo', recipient='recruiter',
                       todo_text='RECRUIT P8 request', tag_id=False)
        self.req.sudo()._request_write('sent_in')
        self.assertEqual(ran(sent_in), 1)
        self.assertTrue(bgv)
        # a referral
        ref_rule = rule('referral_received')
        self.req.sudo().write({'referral_open': True})
        referral = self.env['pb.hiring.referral'].sudo().refer(
            self.req.id, self.boss.id,
            {'name': 'RECRUIT P8 Referred', 'email': 'p8.referred@example.com',
             'phone': '+84900000008', 'consent': True, 'declaration': True,
             'nationality': 'Vietnamese', 'location': 'Hanoi', 'relationship': 'Friend',
             'linkedin': 'https://example.invalid/p8',
             'attachment': {'name': 'cv.pdf', 'datas': 'JVBERi0xLjQK',
                            'mimetype': 'application/pdf'}})
        self.assertTrue(referral.applicant_id)
        self.assertEqual(ran(ref_rule), 1)
        # an agency
        ag_rule = rule('agency_submitted')
        vendor = self.env['pb.vendor'].sudo().create({
            'name': 'RECRUIT P8 Agency', 'vendor_type': 'recruitment',
            'company_id': self.company.id, 'contact_email': 'p8.agency@example.com',
            'responsible_user_id': self.lead.id})
        self.req.sudo().write({'agency_vendor_ids': [(4, vendor.id)]})
        sub = self.env['pb.hiring.agency.submission'].sudo()._submit(
            vendor, self.req, False, {'name': 'RECRUIT P8 Agency Person',
                                      'email': 'p8.agencyperson@example.com',
                                      'phone': '+84900000009'})
        self.assertEqual(sub.state, 'accepted')
        self.assertEqual(ran(ag_rule), 1)

    # ------------------------------------------------------------- test 8
    def test_08_try_it_writes_nothing(self):
        if 'vi_VN' in self.langs:
            self.applicant.sudo().write({'pb_lang': 'vi_VN'})
        lead = self.facade.with_user(self.lead)
        before = self._since()
        acts = self.env['mail.activity'].sudo().search_count([])
        runs = self.Run.search_count([])
        res = lead.act('rule_try', {'applicant_id': self.applicant.id, 'rule': {
            'event': 'stage_entered', 'stage_id': self.Stage._pb_stage('shortlist').id,
            'action': 'send_email', 'recipient': 'candidate', 'template_key': 'next_round'}})
        text = ' '.join(ln['text'] for ln in res['lines'])
        self.assertIn('Would send', text)
        if 'vi_VN' in self.langs:
            self.assertIn('Vietnamese', text)
        res = lead.act('rule_try', {'applicant_id': self.applicant.id, 'rule': {
            'event': 'stage_entered', 'stage_id': self.Stage._pb_stage('shortlist').id,
            'action': 'todo', 'recipient': 'recruiter', 'todo_text': 'Look'}})
        self.assertIn('Would give', ' '.join(ln['text'] for ln in res['lines']))
        self.assertFalse(self._new(before))
        self.assertEqual(self.env['mail.activity'].sudo().search_count([]), acts)
        self.assertEqual(self.Run.search_count([]), runs)
        # an incomplete rule says why instead of trying
        res = lead.act('rule_try', {'applicant_id': self.applicant.id, 'rule': {
            'event': 'stage_entered', 'action': 'todo', 'recipient': 'recruiter'}})
        self.assertFalse(res['lines'][0]['ok'])
        payload = lead.get_automations()
        self.assertTrue(payload['builtins'])
        self.assertTrue(payload['events'])


# =========================================================================
#  7 and the leftovers: papers, the check, G-44, the share email
# =========================================================================
@tagged('post_install', '-at_install', 'recruit_p8')
class TestRecruitLeftoversP8(JoiningCase):

    def test_07a_rc80_papers_in_reaches_the_recruiter(self):
        offer = self._offer()
        offer.sudo().write({'state': 'hr_ok'})
        self._complete_documents(offer)
        acts = self.env['mail.activity'].sudo().search([
            ('res_model', '=', 'pb.hiring.offer'), ('res_id', '=', offer.id),
            ('user_id', '=', self.recruiter.id), ('summary', 'like', 'Papers are in')])
        self.assertEqual(len(acts), 1, 'the papers-are-in to-do did not reach the recruiter')

    def test_07b_the_chase_switch_and_the_referral_announcement_default(self):
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.auto_chase', '0')
        Auto = self.env['pb.hiring.automation']
        self.assertEqual(Auto._tell_lead_late_feedback(), 0)
        self.assertEqual(Auto._chase_late_feedback(), 0)
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.auto_chase', '1')
        from ..models.hiring_common import DEFAULTS, P_REFERRAL_ANNOUNCE
        self.assertEqual(DEFAULTS[P_REFERRAL_ANNOUNCE], '0')

    def test_g44_the_other_finalists_are_closed_when_the_role_is_full(self):
        self.req.sudo().write({'headcount': 1})
        Stage = self.env['hr.recruitment.stage']
        other = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P8 Finalist', 'email_from': 'p8.finalist@example.com',
            'job_id': self.job.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id, 'stage_id': Stage._pb_stage('discussion_2').id})
        early = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P8 Early', 'email_from': 'p8.early@example.com',
            'job_id': self.job.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id, 'stage_id': Stage._pb_stage('shortlist').id})
        before = self.env['mail.mail'].sudo().search([]).ids
        self._signed()
        self.assertEqual(other.stage_id.pb_key, 'interview_reject')
        self.assertIn('Not selected', other.pb_stage_reason or '')
        self.assertTrue(other.message_ids.filtered(lambda m: 'another finalist signed' in (m.body or '')))
        self.assertTrue(self._mails(before).filtered(lambda m: m.email_to == 'p8.finalist@example.com'))
        self.assertEqual(early.stage_id.pb_key, 'shortlist', 'a non-finalist was closed')

    def test_g44_switch_off_and_a_role_with_seats_left(self):
        Stage = self.env['hr.recruitment.stage']
        other = self.env['hr.applicant'].sudo().create({
            'partner_name': 'RECRUIT P8 Finalist 2', 'email_from': 'p8.finalist2@example.com',
            'job_id': self.job.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id, 'stage_id': Stage._pb_stage('discussion_1').id})
        # headcount 2 (the case's role): one signature leaves a seat
        self._signed()
        self.assertEqual(other.stage_id.pb_key, 'discussion_1')

    def test_share_email(self):
        Users = self.env['res.users'].sudo()
        stamp = fields.Datetime.now().timestamp()
        mgr = Users.create({'name': 'RECRUIT P8 Manager', 'login': 'recruit.p8.mgr.%s' % stamp,
                            'email': 'recruit.p8.mgr@example.com',
                            'company_ids': [(4, self.company.id)], 'company_id': self.company.id,
                            'group_ids': [(4, self.env.ref('base.group_user').id)]})
        self.applicant.sudo().write({'pb_requisition_id': self.req.id})
        before = self.env['mail.mail'].sudo().search([]).ids
        res = self.facade.act('share', {'applicant_ids': [self.applicant.id],
                                        'targets': [{'user_id': mgr.id}], 'parts': ['profile', 'cv']})
        mails = self._mails(before).filtered(lambda m: m.email_to == 'recruit.p8.mgr@example.com')
        self.assertEqual(len(mails), 1)
        self.assertIn('You were given access to', mails.subject)
        self.assertIn('email', res['note'])
        before = self.env['mail.mail'].sudo().search([]).ids
        self.facade.act('share', {'applicant_ids': [self.applicant.id],
                                  'targets': [{'user_id': mgr.id}], 'parts': ['profile']})
        self.assertFalse(self._mails(before).filtered(lambda m: m.email_to == 'recruit.p8.mgr@example.com'),
                         'changing what they see mailed them again')
        self.assertTrue(self.env.ref('pb_hiring.mail_template_share_granted'))
