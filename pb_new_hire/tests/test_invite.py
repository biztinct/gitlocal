# -*- coding: utf-8 -*-
"""NEWHIRE P3b — the welcome message, its link, /my/welcome, the home row,
the checklist tick, reminders and the New joiners board. Test numbers match
the handover (V1-V12); X1-X3 are the architect's small items (a)-(c)."""
import json
import re
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, new_test_user, tagged

from .test_docs import DocsCommon
from .test_welcome import WelcomeCommon

LINK = re.compile(r'/web/signup\?|token=|reset_password\?')
PRIVATE = 'demo.nh.sari@example.net'
WORK = 'demo.nh.sari@example.com'


class InviteMixin:
    """Shared fixtures for the P3b tests."""

    @classmethod
    def _mail_server(cls):
        # an outgoing server that goes nowhere: the queue is the evidence and
        # nothing is ever sent by these tests (no cron runs, force_send=False)
        return cls.env['ir.mail_server'].sudo().create({
            'name': 'DEMO NH nowhere', 'smtp_host': '127.0.0.1', 'smtp_port': 1025,
            'smtp_encryption': 'none', 'active': True})

    def invite_draft(self, **kw):
        d = self.docs_draft(**dict({'login_mode': 'email', 'open_case': False, 'letter': False}, **kw))
        return d

    def queued(self, before):
        return self.env['mail.mail'].sudo().search([('id', 'not in', before)])

    def mail_ids(self):
        return self.env['mail.mail'].sudo().search([]).ids

    def Invite(self, user=None):
        return self.env['pb.new.hire.invite'].with_user(user or self.approver).with_context(
            allowed_company_ids=[self.company.id])

    def legs_of(self, out):
        if out.get('result') and out['result'].get('legs') is not None:
            return {leg['key']: leg for leg in out['result']['legs']}
        proposal = self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id'])
        return {leg['key']: leg for leg in (proposal.result().get('legs') or [])}


@tagged('post_install', '-at_install', 'newhire')
class TestInvite(InviteMixin, DocsCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = cls._mail_server()

    # ------------------------------------------------------------ V1 sign-in
    def test_v01_login_by_personal_email(self):
        s = self.studio()
        modes = s.welcome_options(self.invite_draft(work_email=False))['login']
        email = next(m for m in modes['modes'] if m['key'] == 'email')
        self.assertTrue(email['available'], email)
        self.assertIn(PRIVATE, email['sub'], 'the sub-line names the address used')
        self.fast_lane()
        out = s.send(self.invite_draft(work_email=False))
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        self.assertEqual(emp.user_id.login, PRIVATE)
        self.assertEqual(emp.user_id.email, PRIVATE)
        self.assertTrue(emp.user_id.share, 'an employee-tier login')
        self.assertEqual(emp.pb_portal_user_id, emp.user_id)
        self.assertTrue(self.legs_of(out)['login']['ok'])

    def test_v01b_reuse_and_clash(self):
        self.fast_lane()
        portal = self.env.ref('base.group_portal')
        free = self.env['res.users'].sudo().create({
            'name': 'DEMO NH Sari portal', 'login': PRIVATE, 'email': PRIVATE,
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [portal.id])]})
        out = self.studio().send(self.invite_draft(work_email=False))
        emp = self.hires()
        self.assertEqual(emp.user_id, free, 'a free employee-tier login is reused')
        self.assertTrue(self.legs_of(out)['login']['ok'])

    def test_v01c_clash_with_someone_else(self):
        self.fast_lane()
        new_test_user(self.env, login=PRIVATE, groups='base.group_user', name='DEMO NH Staff',
                      company_id=self.company.id, company_ids=[(6, 0, [self.company.id])])
        out = self.studio().send(self.invite_draft(work_email=False))
        emp = self.hires()
        self.assertFalse(emp.user_id)
        leg = self.legs_of(out)['login']
        self.assertFalse(leg['ok'])
        self.assertIn('A sign-in with %s already exists for someone else. Create the sign-in from '
                      'Access.' % PRIVATE, leg['message'])

    def test_v01d_work_email_path_unchanged(self):
        """Both addresses: the sign-in is the work email (the bridge's own
        `_auto_create_login`); the welcome message goes to the personal one."""
        self.fast_lane()
        before = self.mail_ids()
        out = self.studio().send(self.invite_draft())
        emp = self.hires()
        self.assertEqual(emp.user_id.login, WORK)
        mails = self.queued(before)
        self.assertEqual(mails.mapped('email_to'), [PRIVATE])

    # ------------------------------------------------------------ V2 the link
    def test_v02_link(self):
        self.fast_lane()
        self.studio().send(self.invite_draft())
        emp = self.hires()
        Invite = self.env['pb.new.hire.invite']
        link = Invite._link(emp)
        self.assertIn('/web/signup?', link)
        self.assertIn('redirect=%2Fmy%2Fwelcome', link)
        token = re.search(r'token=([^&]+)', link).group(1)
        partner = emp.user_id.partner_id
        from urllib.parse import unquote
        self.assertEqual(self.env['res.partner'].sudo()._get_partner_from_token(unquote(token)), partner)
        self.assertIn('works for 6 days', Invite.expires_hint(emp))
        # after a first sign-in the old link dies and the plain page is given
        self.env['res.users'].with_user(emp.user_id)._update_last_login()
        emp.user_id.invalidate_recordset()
        partner.invalidate_recordset()
        self.assertFalse(self.env['res.partner'].sudo()._get_partner_from_token(unquote(token)))
        plain = Invite._link(emp)
        self.assertTrue(plain.endswith('/my/welcome'), plain)
        self.assertNotIn('token', plain)

    def test_v02b_validity_follows_the_setting(self):
        self.fast_lane()
        self.studio().send(self.invite_draft())
        emp = self.hires()
        self.env['ir.config_parameter'].sudo().set_param('auth_signup.signup.validity.hours', 48)
        self.assertIn('works for 2 days', self.env['pb.new.hire.invite'].expires_hint(emp))
        self.env['ir.config_parameter'].sudo().set_param('auth_signup.signup.validity.hours', 30)
        self.assertIn('works for 30 hours', self.env['pb.new.hire.invite'].expires_hint(emp))

    # ------------------------------------------------------------ V3 sending
    def test_v03_send_welcome(self):
        self.fast_lane()
        before = self.mail_ids()
        out = self.studio().send(self.invite_draft(items={'bank': 'ask', 'emergency': 'skip'}))
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        leg = self.legs_of(out)['invite']
        self.assertTrue(leg['ok'], leg)
        self.assertEqual(leg['message'], 'welcome message to %s' % PRIVATE)
        mail = self.queued(before)
        self.assertEqual(len(mail), 1, mail.mapped('subject'))
        self.assertEqual(mail.email_to, PRIVATE)
        self.assertFalse(mail.model, 'on nobody\'s chatter')
        self.assertTrue(mail.auto_delete)
        self.assertEqual(mail.subject, 'Welcome to DEMO NH Company — a few things before Monday 7 December')
        body = mail.body_html
        labels = [a.label for a in self.env['pb.new.hire.ask'].sudo().search([('employee_id', '=', emp.id)])]
        self.assertTrue(labels)
        for label in labels:
            self.assertIn(label, body)
        self.assertNotIn('Emergency contact', body, 'a skipped item is not asked')
        self.assertIn('Get started', body)
        self.assertIn('works for 6 days', body)
        self.assertIn('/web/signup?', body)
        # nothing of the vendor in what leaves: subject, body and the
        # debranded outgoing form (footer included)
        self.assertNotRegex(mail.subject, re.compile('odoo', re.I))
        self.assertNotRegex(body, re.compile('odoo', re.I))
        for email in mail._prepare_outgoing_list():
            self.assertNotRegex(email.get('body') or '', re.compile('odoo', re.I))
            self.assertNotRegex(email.get('subject') or '', re.compile('odoo', re.I))
        self.assertEqual(emp.nh_reminded_on, fields.Date.today())
        self.assertIn('Welcome message sent to %s.' % PRIVATE, ' '.join(emp.message_ids.mapped('body')))

    def test_v03b_no_mail_server(self):
        self.server.active = False
        self.fast_lane()
        before = self.mail_ids()
        out = self.studio().send(self.invite_draft())
        self.assertFalse(self.queued(before))
        leg = self.legs_of(out)['invite']
        self.assertFalse(leg['ok'])
        self.assertIn('This site does not send email. Copy the welcome link and send it to DEMO '
                      'yourself.', leg['message'])
        answer = self.env['pb.new.hire.invite'].send(self.hires())
        self.assertEqual((answer['ok'], answer['sent']), (False, False))

    def test_v03c_rows_for_code_and_none(self):
        self.approver.group_ids = [(4, self.env.ref('biz_access.group_access_manager').id)]
        before = self.mail_ids()
        out = self.studio().send(self.invite_draft(clock_on=True, clock_code='DEMO-0777',
                                                   login_mode='code', work_email=False, personal=''))
        self.approve(out)
        leg = self.legs_of(out)['invite']
        self.assertFalse(leg['ok'])
        self.assertIn('has no email sign-in. They can still finish these after signing in with the '
                      'employee number.', leg['message'])
        self.assertTrue(self.env['pb.new.hire.ask'].sudo().search_count(
            [('employee_id', '=', self.hires().id)]), 'the asks stay')
        self.assertFalse(self.queued(before))

    def test_v03d_none_and_nothing_asked(self):
        self.fast_lane()
        out = self.studio().send(self.invite_draft(login_mode='none'))
        leg = self.legs_of(out)['invite']
        self.assertFalse(leg['ok'])
        self.assertIn('has no sign-in yet. Once one is made in Access, these are waiting for them',
                      leg['message'])

    def test_v03e_nothing_asked_no_message(self):
        self.fast_lane()
        before = self.mail_ids()
        items = {k: 'skip' for k in ('personal', 'emergency', 'tax_fund', 'paper-%s' % self.cat_cert.id)}
        items.update(id_number='have', bank='have')
        out = self.studio().send(self.invite_draft(
            items=items, have={'identification_id': 'S1234567D', 'bank_name': 'DBS',
                               'account_number': '123456789'}), [self.file('id_number')])
        leg = self.legs_of(out)['invite']
        self.assertTrue(leg['ok'])
        self.assertIn('nothing to ask', leg['message'])
        self.assertFalse(self.queued(before).filtered(lambda m: 'a few things' in (m.subject or '')))

    # ------------------------------------------------------------ V4 never stored
    def test_v04_link_never_persisted(self):
        out = self.studio().send(self.invite_draft())
        self.approve(out)
        emp = self.hires()
        Invite = self.Invite()
        copied = Invite.copy_link(emp.id)
        self.assertTrue(copied['ok'], copied)
        self.assertTrue(LINK.search(copied['link']))
        queued = self.env['mail.mail'].sudo().search([('email_to', '=', PRIVATE)])
        self.assertTrue(queued, 'the welcome message waits in the queue')
        allowed = set(queued.mapped('mail_message_id').ids)
        self.env.flush_all()
        self.env.cr.execute("SELECT id, body FROM mail_message WHERE body ~* %s", [r'/web/signup\?|token='])
        stray = [row for row in self.env.cr.fetchall() if row[0] not in allowed]
        self.assertFalse(stray, 'the link appears only in the outgoing mail itself: %s' % stray)
        proposal = self.env['pb.newhire.proposal'].sudo().browse(out['proposal_id'])
        for blob in (proposal.payload_json or '', proposal.result_json or '', json.dumps(out, default=str)):
            self.assertFalse(LINK.search(blob))
        self.env.cr.execute("SELECT to_regclass('ir_logging')")
        if self.env.cr.fetchone()[0]:
            self.env.cr.execute("SELECT count(*) FROM ir_logging WHERE message ~* %s", [r'/web/signup\?|token='])
            self.assertEqual(self.env.cr.fetchone()[0], 0)
        self.assertNotIn('token=', ' '.join(emp.message_ids.mapped('body')))
        self.assertIn('copied the welcome link', ' '.join(emp.message_ids.mapped('body')))

    # ------------------------------------------------------------ V7 home row
    def test_v07_home_row(self):
        self.fast_lane()
        self.studio().send(self.invite_draft())
        emp = self.hires()
        today = fields.Date.today()
        # as the person (the home's sibling rows read the session's own employee)
        Home = self.env['pb.me.home'].with_user(emp.user_id).sudo()
        needs, _docs = Home._pbme_needs(emp, today, today - timedelta(days=today.weekday()),
                                        fields.Datetime.now())
        row = next((n for n in needs if n['key'] == 'nh_welcome'), None)
        summary = self.env['pb.new.hire.ask'].sudo().summary(emp)
        self.assertTrue(row, needs)
        self.assertEqual(row['n'], summary['open'])
        self.assertEqual(row['url'], '/my/welcome')
        self.assertEqual(row['label'], 'Finish your joining details')
        self.env['pb.new.hire.ask'].sudo().search([('employee_id', '=', emp.id)]).write({'state': 'done'})
        with patch.object(type(self.env['pb.new.hire.ask']), 'refresh', lambda self: True):
            needs, _docs = Home._pbme_needs(emp, today, today, fields.Datetime.now())
        self.assertFalse([n for n in needs if n['key'] == 'nh_welcome'], 'gone when done')

    # ------------------------------------------------------------ V8 the checklist
    def test_v08_details_step_ticks_once(self):
        self.fast_lane()
        out = self.studio().send(self.invite_draft(items={
            'personal': 'ask', 'emergency': 'skip', 'tax_fund': 'skip', 'bank': 'have',
            'paper-%s' % self.cat_cert.id: 'skip', 'id_number': 'number'},
            have={'identification_id': 'S7654321A', 'bank_name': 'DBS', 'account_number': '123456789'}))
        self.assertTrue(out.get('applied'), out)
        emp = self.hires()
        template = self.env.ref('pb_onboarding.journey_template_rize_onboarding')
        case = self.env['pb.journey.case'].sudo().create({
            'employee_id': emp.id, 'case_type': 'onboarding', 'template_id': template.id,
            'anchor_date': date(2026, 12, 7), 'company_id': self.company.id})
        case.action_open()
        step = self.env.ref('pb_onboarding.step_rize_data')
        task = case.task_ids.filtered(lambda t: t.step_id == step)
        self.assertEqual(len(task), 1)
        Ask = self.env['pb.new.hire.ask'].sudo()
        Ask.summary(emp)
        self.assertEqual(task.state, 'pending', 'not before everything is done')
        emp.sudo().write({'private_phone': '+65 2', 'private_street': '1 Orchard Road'})
        Ask.summary(emp)
        self.assertEqual(task.state, 'pending', 'the card is still missing')
        att = self.env['ir.attachment'].sudo().create({'name': 'id.pdf', 'datas': self.file('x')['data'],
                                                        'mimetype': 'application/pdf'})
        self.env['pb.employee.document'].sudo().create({
            'employee_id': emp.id, 'category_id': self.cat_id.id, 'name': 'NRIC',
            'attachment_id': att.id, 'expiry_date': '2031-01-01'})
        summary = Ask.summary(emp)
        self.assertEqual((summary['open'], summary['waiting']), (0, 0))
        self.assertEqual(task.state, 'done')
        self.assertIn('Ticked when the joining details were finished', task.payload_json)
        self.assertTrue(emp.nh_details_ticked)
        task.write({'state': 'pending'})            # HR opened it again
        Ask.summary(emp)
        self.assertEqual(task.state, 'pending', 'ticked once only')

    # ------------------------------------------------------------ V9 reminders
    def _remind_world(self):
        self.fast_lane()
        self.studio().send(self.invite_draft())
        emp = self.hires()
        self.assertTrue(emp.nh_remind)
        return emp, self.env['pb.new.hire.invite'].sudo()

    def test_v09_cadence_and_stop(self):
        emp, Invite = self._remind_world()
        day0 = date(2026, 11, 20)
        emp.nh_reminded_on = day0 - timedelta(days=2)
        before = self.mail_ids()
        self.assertEqual(Invite._nh_remind_asks(today=day0)['reminded'], 1)
        self.assertEqual(emp.nh_reminded_on, day0)
        reminder = self.queued(before)
        self.assertEqual(len(reminder), 1)
        self.assertIn('A quick reminder', reminder.body_html)
        self.assertEqual(Invite._nh_remind_asks(today=day0)['reminded'], 0, 'once')
        self.assertEqual(Invite._nh_remind_asks(today=day0 + timedelta(days=1))['reminded'], 0)
        self.assertEqual(Invite._nh_remind_asks(today=day0 + timedelta(days=2))['reminded'], 1, '2 days on')
        # everything done: it stops by itself
        self.env['pb.new.hire.ask'].sudo().search([('employee_id', '=', emp.id)]).write({'state': 'done'})
        with patch.object(type(self.env['pb.new.hire.ask']), 'refresh', lambda self: True):
            self.assertEqual(Invite._nh_remind_asks(today=day0 + timedelta(days=4)).get('reminded', 0), 0)

    def test_v09b_switches(self):
        emp, Invite = self._remind_world()
        day0 = date(2026, 11, 20)
        Param = self.env['ir.config_parameter'].sudo()
        Param.set_param('pb_new_hire.ask_reminders', '0')
        self.assertEqual(Invite._nh_remind_asks(today=day0), {'off': True})
        Param.set_param('pb_new_hire.ask_reminders', '1')
        Param.set_param('pb_lifecycle.reminders_enabled', '0')
        self.assertEqual(Invite._nh_remind_asks(today=day0), {'off': True})
        Param.set_param('pb_lifecycle.reminders_enabled', '1')
        emp.nh_remind = False
        self.assertEqual(Invite._nh_remind_asks(today=day0)['reminded'], 0)
        emp.nh_remind = True
        # the site's mail lock: nothing sent, nothing written
        self.server.active = False
        last = emp.nh_reminded_on
        self.assertEqual(Invite._nh_remind_asks(today=day0 + timedelta(days=9))['reminded'], 0)
        self.assertEqual(emp.nh_reminded_on, last)
        # and the one lifecycle job runs the piece
        self.server.active = True
        counts = self.env['pb.journey.case'].sudo()._cron_lifecycle_reminders()
        self.assertIn('new_hire_asks', counts)

    def test_v09c_hr_nudge_once(self):
        emp, Invite = self._remind_world()
        first = date(2026, 12, 7)
        acts = self.env['mail.activity'].sudo().search([]).ids
        self.assertEqual(Invite._nh_remind_asks(today=first - timedelta(days=4))['nudged'], 0, 'too early')
        self.assertEqual(Invite._nh_remind_asks(today=first - timedelta(days=3))['nudged'], 1)
        new = self.env['mail.activity'].sudo().search([('id', 'not in', acts)])
        self.assertEqual(len(new), 1)
        self.assertEqual(new.res_model, 'hr.employee')
        self.assertEqual(new.user_id, self.maker, 'the person who proposed the hire')
        self.assertRegex(new.note or '', r'DEMO NH Sari Wulandari starts on .+ and \d+ things? needed '
                                         r'for the first pay (is|are) still missing\.')
        self.assertEqual(Invite._nh_remind_asks(today=first - timedelta(days=2))['nudged'], 0, 'once')

    # ------------------------------------------------------------ V10 the board
    def test_v10_board_shape_batching_gates(self):
        self.fast_lane()
        names = ['DEMO NH Sari Wulandari', 'DEMO NH Budi One', 'DEMO NH Ani Two']
        for i, name in enumerate(names):
            self.studio().send(self.invite_draft(
                name=name, work_email='demo.nh.%s@example.com' % i,
                personal='demo.nh.p%s@example.net' % i))
        emps = [self.hires(n) for n in names]
        Invite = self.env['pb.new.hire.invite'].with_user(self.approver).with_context(
            allowed_company_ids=[self.company.id])
        Invite._board([e.id for e in emps])         # settle the states once

        def count(ids):
            self.env.invalidate_all()
            start = self.env.cr.sql_log_count
            Invite._board(ids)
            return self.env.cr.sql_log_count - start
        one, three = count([emps[0].id]), count([e.id for e in emps])
        self.assertLessEqual(three, one + 2, 'one batched read, not one per row (%s vs %s)' % (one, three))
        asked = Invite._board([emps[0].id])[emps[0].id]
        for key in ('total', 'done', 'waiting', 'open', 'items', 'can_send', 'can_copy', 'has_login', 'act', 'chip'):
            self.assertIn(key, asked)
        self.assertEqual(set(asked['items'][0]), {'key', 'label', 'state', 'need'})
        self.assertTrue(asked['can_copy'] and asked['can_send'], 'an HR manager')
        officer = new_test_user(self.env, login='nh_officer_b', groups='base.group_user,hr.group_hr_user',
                                company_id=self.company.id, company_ids=[(6, 0, [self.company.id])])
        mine = self.env['pb.new.hire.invite'].with_user(officer).with_context(
            allowed_company_ids=[self.company.id])._board([emps[0].id])[emps[0].id]
        self.assertFalse(mine['can_copy'] or mine['can_send'], 'an HR officer sees, cannot send')
        self.assertEqual(asked['chip'], '%s of %s details' % (asked['done'], asked['total']))
        # the board's own reader carries it
        self.env.ref('pb_lifecycle.group_lifecycle_manager').user_ids = [(4, self.approver.id)]
        template = self.env.ref('pb_onboarding.journey_template_rize_onboarding')
        self.env['pb.journey.case'].sudo().create({
            'employee_id': emps[0].id, 'case_type': 'onboarding', 'template_id': template.id,
            'anchor_date': date(2026, 12, 7), 'company_id': self.company.id}).action_open()
        page = self.env['pb.onboarding'].with_user(self.approver).with_context(
            allowed_company_ids=[self.company.id]).get_joiners_page()
        row = next(r for r in page['rows'] if r['employee_id'] == emps[0].id)
        self.assertTrue(row['asked'] and row['asked']['total'])

    # ------------------------------------------------------------ V11 rate limit
    def test_v11_rate_limit_and_gate(self):
        self.fast_lane()
        self.studio().send(self.invite_draft())
        emp = self.hires()
        Invite = self.Invite()
        self.assertTrue(Invite.copy_link(emp.id)['ok'])
        again = Invite.copy_link(emp.id)
        self.assertFalse(again['ok'])
        self.assertIn('less than a minute ago', again['message'])
        sent = Invite.send_again(emp.id)
        self.assertFalse(sent['ok'], 'the welcome message went less than a minute ago')
        emp.sudo().write({'nh_sent_at': fields.Datetime.now() - timedelta(minutes=2),
                          'nh_copied_at': fields.Datetime.now() - timedelta(minutes=2)})
        self.assertTrue(Invite.send_again(emp.id)['sent'])
        self.assertTrue(Invite.copy_link(emp.id)['ok'])
        with self.assertRaises(AccessError):
            self.Invite(self.maker).copy_link(emp.id)
        with self.assertRaises(AccessError):
            self.Invite(self.maker).send_again(emp.id)


@tagged('post_install', '-at_install', 'newhire')
class TestSmallItems(InviteMixin, DocsCommon):
    """The architect's answers to P3a's open questions (a)-(c)."""

    def test_x01_number_only_card_rows(self):
        items, _out = self.items('SG')
        self.assertTrue(items['id_number']['can_number'])
        self.assertFalse(items['personal']['can_number'])
        self.assertEqual(items['id_number']['card_url'], '/my/documents')
        s = self.studio()
        refused = s.send(self.docs_draft(items={'id_number': 'number'}))
        self.assertEqual(refused['field'], 'have-identification_id')
        self.fast_lane()
        out = s.send(self.docs_draft(items={'id_number': 'number', 'personal': 'number'},
                                     have={'identification_id': 'S7654321A'}))
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        self.assertEqual(emp.identification_id, 'S7654321A', 'the number is saved')
        Ask = self.env['pb.new.hire.ask'].sudo()
        card = Ask.search([('employee_id', '=', emp.id), ('key', '=', 'id_number')])
        self.assertEqual(card.label, 'NRIC or work pass', 'the card is asked')
        self.assertEqual(card.url, '/my/documents')
        self.assertEqual(card.state, 'open')
        self.assertTrue(Ask.search_count([('employee_id', '=', emp.id), ('key', '=', 'personal')]),
                        '"number" on a row without a card falls back to its default (ask)')
        self.assertFalse(self.env['pb.employee.document'].sudo().search_count([('employee_id', '=', emp.id)]))

    def test_x01b_tax_card_number_only(self):
        """Indonesia's NPWP: number saved, the card asked on the tax page."""
        items, _out = self.items('ID')
        self.assertTrue(items['tax_number']['can_number'])
        self.assertEqual(items['tax_number']['card_url'], '/my/tax/change/tax_number')

    def test_x02_contract_copies_of_hr_kept_numbers(self):
        contract_fields = self.env['hr.contract']._fields
        if 'vietnam_social_insurance_number' not in contract_fields:
            self.skipTest('the Vietnam payroll fields are not installed here')
        self.fast_lane()
        out = self.studio().send(self.docs_draft(
            department_id=self.ops.id, job_id=self.agronomist.id, payroll_country='VN',
            items={'insurance': 'have', 'tax_number': 'have'},
            have={'vietnam_social_insurance_number': '7912345678', 'vietnam_tax_code': '0312345678'}))
        self.assertTrue(out['applied'], out)
        emp = self.hires()
        contract = self.env['hr.contract'].sudo().browse(out['contract_id'])
        self.assertEqual(emp.vietnam_social_insurance_number, '7912345678')
        self.assertEqual(contract.vietnam_social_insurance_number, '7912345678')
        self.assertEqual(contract.vietnam_tax_code, '0312345678')

    def test_x03_every_paper_row_has_a_plain_label(self):
        Paper = self.env['pb.new.hire.paper']
        stock = {'Degree / Certificate', 'ID Document'}
        for code in ('ID', 'VN', 'IN', 'SG', 'MY'):
            for row in Paper.for_country(code, self.company):
                self.assertTrue(row.label, '%s %s has its own label' % (code, row.category_id.name))
                self.assertNotIn(row.display_label(), stock)
        # a paper a company adds without a word gets a plain name too
        self.assertEqual(Paper.plain_name(self.cat_permit), 'Work permit')
        self.assertEqual(Paper.plain_name(self.cat_cert), 'Highest certificate')
        rows = self.env['pb.new.hire'].with_user(self.approver).with_context(
            allowed_company_ids=[self.company.id]).papers_edit_load('SG')
        names = [r['name'] for r in rows['rows']] + [o['name'] for o in rows['others']]
        self.assertFalse(stock & set(names), names)


@tagged('post_install', '-at_install', 'newhire')
class TestStudioInviteCard(InviteMixin, WelcomeCommon):
    """Step 5's card reads `load().mail_on`; the done card reads `card`."""

    def test_v12_load_and_card(self):
        self.assertIn('mail_on', self.studio().load())
        self.assertFalse(self.studio().load()['mail_on'] and not self.env['ir.mail_server'].sudo().search_count(
            [('active', '=', True)]))
        self._mail_server()
        self.assertTrue(self.studio().load()['mail_on'])
        self.fast_lane()
        out = self.studio().send(self.welcome_draft(open_case=False))
        card = self.env['pb.new.hire.invite'].with_user(self.maker).with_context(
            allowed_company_ids=[self.company.id]).card(out['employee_id'])
        self.assertTrue(card['asked']['total'])
        self.assertFalse(card['asked']['can_copy'], 'the maker is an HR officer here')


@tagged('post_install', '-at_install', 'newhire')
class TestWelcomePage(HttpCase):
    """V5 / V6: /my/welcome over HTTP, as the person."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.company = env.company
        portal = env.ref('base.group_portal')
        Users = env['res.users'].sudo().with_context(no_reset_password=True)

        def person(login, name):
            user = Users.create({'name': name, 'login': login, 'email': login, 'password': login,
                                 'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
                                 'group_ids': [(6, 0, [portal.id])]})
            emp = env['hr.employee'].sudo().create({'name': name, 'company_id': cls.company.id,
                                                    'user_id': user.id, 'date_of_joining': date(2026, 12, 7)})
            return user, emp
        cls.sari_user, cls.sari = person('demo.nh.web.sari@example.com', 'DEMO NH Web Sari')
        cls.budi_user, cls.budi = person('demo.nh.web.budi@example.com', 'DEMO NH Web Budi')
        Ask = env['pb.new.hire.ask'].sudo()
        cert = env.ref('pb_employee_vault.cat_certificate')
        for emp, rows in ((cls.sari, [('personal', 'Personal details', '/my/profile', False),
                                       ('bank', 'Bank account', '/my/details/bank', False),
                                       ('paper-%s' % cert.id, 'Highest certificate', '/my/documents', cert.id)]),
                          (cls.budi, [('emergency', 'DEMO Budi emergency', '/my/profile', False)])):
            for n, (key, label, url, cat) in enumerate(rows):
                Ask.create({'employee_id': emp.id, 'key': key, 'label': label, 'url': url,
                            'need': 'first_pay' if key == 'bank' else 'optional', 'sequence': n,
                            'category_id': cat, 'company_id': cls.company.id})

    def test_v05_own_asks_states_and_finish(self):
        self.authenticate(self.sari_user.login, self.sari_user.login)
        res = self.url_open('/my/welcome')
        self.assertEqual(res.status_code, 200)
        page = res.text
        self.assertIn('Welcome, DEMO', page)
        for label in ('Personal details', 'Bank account', 'Highest certificate'):
            self.assertIn(label, page)
        self.assertNotIn('DEMO Budi emergency', page, "another person's asks are never shown")
        self.assertIn('Needed for your first pay', page)
        self.assertIn('href="/my/details/bank"', page)
        self.assertIn('To do', page)
        # waiting, then done
        self.env['pb.profile.change.request'].sudo().create(
            {'employee_id': self.sari.id, 'state': 'hr_review', 'x_phone': '+65 1'})
        self.assertIn('Sent, waiting for HR', self.url_open('/my/welcome').text)
        Ask = self.env['pb.new.hire.ask'].sudo()
        Ask.search([('employee_id', '=', self.sari.id)]).write({'state': 'done'})
        with patch.object(type(Ask), 'refresh', lambda self: True):
            done = self.url_open('/my/welcome').text
        self.assertIn('That is everything. See you on Mon 7 Dec.', done)
        self.assertIn('Go to your home page', done)

    def test_v05b_no_asks_goes_home(self):
        user = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'DEMO NH Web Nobody', 'login': 'demo.nh.web.nobody@example.com',
            'password': 'demo.nh.web.nobody@example.com', 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        self.env['hr.employee'].sudo().create({'name': 'DEMO NH Web Nobody', 'company_id': self.company.id,
                                               'user_id': user.id})
        self.authenticate(user.login, user.login)
        res = self.url_open('/my/welcome', allow_redirects=False)
        self.assertIn(res.status_code, (301, 302, 303))
        self.assertTrue(res.headers['Location'].rstrip('/').endswith('/my'), res.headers['Location'])

    def test_v06_first_visit_keeps_next(self):
        if 'pb.privacy.notice' not in self.env:
            self.skipTest('the privacy notice module is not installed here')
        notice = self.env['pb.privacy.notice'].sudo().create({'name': 'DEMO NH notice',
                                                             'company_id': self.company.id})
        notice.action_publish()
        user = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'DEMO NH Web Wulan', 'login': 'demo.nh.web.wulan@example.com',
            'email': 'demo.nh.web.wulan@example.com', 'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        emp = self.env['hr.employee'].sudo().create({'name': 'DEMO NH Web Wulan', 'company_id': self.company.id,
                                                     'user_id': user.id, 'date_of_joining': date(2026, 12, 7)})
        self.env['pb.new.hire.ask'].sudo().create({'employee_id': emp.id, 'key': 'personal',
                                                   'label': 'Personal details', 'url': '/my/profile',
                                                   'company_id': self.company.id})
        link = self.env['pb.new.hire.invite']._link(emp)
        self.assertIn('/web/signup?', link)
        path = link[link.index('/web/signup'):]
        form = self.url_open(path)
        self.assertEqual(form.status_code, 200)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', form.text).group(1)
        token = re.search(r'name="token" value="([^"]+)"', form.text).group(1)
        res = self.url_open('/web/signup', data={
            'csrf_token': csrf, 'token': token, 'login': user.login, 'name': user.name,
            'password': 'DEMO-nh-Pass-2026', 'confirm_password': 'DEMO-nh-Pass-2026',
            'redirect': '/my/welcome'})
        self.assertIn('/my/privacy/notice', res.url)
        self.assertIn('next=%2Fmy%2Fwelcome', res.url)
        csrf = re.search(r'name="csrf_token" value="([^"]+)"', res.text).group(1)
        answered = self.url_open('/my/privacy/answer', data={
            'csrf_token': csrf, 'notice_id': notice.id, 'answer': 'agree', 'next': '/my/welcome'})
        self.assertTrue(answered.url.endswith('/my/welcome'), answered.url)
        self.assertIn('Welcome, DEMO', answered.text)

    def test_v08b_employee_number_person_sees_the_page(self):
        """F8's server half: a login by employee number reaches the same page."""
        user = self.env['res.users'].sudo().with_context(no_reset_password=True).create({
            'name': 'DEMO NH Web Clock', 'login': 'DEMO-0888', 'password': 'DEMO-0888-pass',
            'company_id': self.company.id, 'company_ids': [(6, 0, [self.company.id])],
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])]})
        emp = self.env['hr.employee'].sudo().create({'name': 'DEMO NH Web Clock', 'company_id': self.company.id,
                                                     'user_id': user.id})
        self.env['pb.new.hire.ask'].sudo().create({'employee_id': emp.id, 'key': 'bank', 'label': 'Bank account',
                                                   'url': '/my/details/bank', 'need': 'first_pay',
                                                   'company_id': self.company.id})
        self.assertFalse(self.env['pb.new.hire.invite']._link(emp), 'no welcome link to give')
        self.authenticate('DEMO-0888', 'DEMO-0888-pass')
        self.assertIn('Bank account', self.url_open('/my/welcome').text)
