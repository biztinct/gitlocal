# -*- coding: utf-8 -*-
"""RECRUIT P7 — channels with tracked links, the agency portal, the 6-month rule.

Numbered as in `docs/handovers/recruit/RECRUIT_P7_CHANNELS.md` §5 (1–11;
test 12 is the rest of the suite, with the single-agency tests rewritten in
`test_offer.TestTheAgency`). Nothing leaves the box: the board connector's
HTTP is mocked, mails stay in the queue.
"""

import re
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import urlsplit

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, TransactionCase, tagged

from ..models.channels_p7 import merge_duplicate_sources, utm_record

PDF = b'%PDF-1.4\n% a tiny test CV\n'
PASSWORD = 'RecruitP7!agency'


def _migration(name):
    import importlib.util
    from odoo.modules.module import get_module_path
    path = '%s/migrations/19.0.2.6.0/%s.py' % (get_module_path('pb_hiring'), name)
    spec = importlib.util.spec_from_file_location('pb_hiring_p7_%s' % name.replace('-', '_'), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ChannelCase(TransactionCase):
    """One company, one open Vietnamese role, a recruiter and a talent lead."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        stamp = str(fields.Datetime.now().timestamp()).replace('.', '')
        Users = self.env['res.users'].sudo()

        def user(name, group):
            return Users.create({
                'name': name, 'login': 'recruit.p7.%s.%s' % (name.split()[-1].lower(), stamp),
                'email': 'recruit.p7.%s@example.com' % name.split()[-1].lower(),
                'password': PASSWORD,
                'company_id': self.company.id, 'company_ids': [(4, self.company.id)],
                'group_ids': [(4, self.env.ref('base.group_user').id),
                              (4, self.env.ref(group).id)]})
        self.recruiter = user('DEMO P7 Recruiter', 'pb_hiring.group_hiring_user')
        self.lead = user('DEMO P7 Lead', 'pb_hiring.group_hiring_manager')
        Employee = self.env['hr.employee'].sudo()
        self.boss = Employee.create({'name': 'DEMO P7 Boss', 'company_id': self.company.id,
                                     'work_email': 'demo.p7.boss@example.com'})
        self.head = Employee.create({'name': 'DEMO P7 Head', 'company_id': self.company.id,
                                     'parent_id': self.boss.id})
        self.dept = self.env['hr.department'].sudo().create({
            'name': 'DEMO P7 Field Sales', 'company_id': self.company.id,
            'manager_id': self.head.id})
        self.vn = self.env.ref('base.vn')
        self.id_ = self.env.ref('base.id')
        self.req = self._role('DEMO P7 Territory Manager', self.vn)
        self.Channel = self.env['pb.hiring.channel'].sudo()
        self.Channel._ensure_for(self.company)
        self.facade = self.env['pb.hiring'].with_user(self.recruiter)
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.closure_mail', '1')
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.notify_mail', '1')

    def _role(self, title, country, **extra):
        vals = {'title': title, 'department_id': self.dept.id, 'company_id': self.company.id,
                'requested_by_id': self.head.id, 'reporting_manager_id': self.boss.id,
                'headcount': 1, 'budget_cost': 123456789.0,
                'requirements': 'Sells to farms.', 'country_id': country.id}
        vals.update(extra)
        req = self.env['pb.hiring.requisition'].sudo().create(vals)
        req._chain_state_write('open')
        req._on_opened()
        req.sudo().write({'recruiter_id': self.recruiter.id})
        return req

    def _channel(self, key):
        return self.Channel.search([('company_id', '=', self.company.id), ('key', '=', key)])

    def _rows(self, req):
        return {r['key']: r for r in self.facade.get_publish_panel(req.id)['rows']}

    def _vendor(self, name='DEMO P7 Talent Bridge', email='hello@talentbridge.example.com'):
        return self.env['pb.vendor'].sudo().create({
            'name': name, 'vendor_type': 'recruitment', 'contact_email': email,
            'contact_name': 'Lan', 'responsible_user_id': self.lead.id,
            'company_id': self.company.id})

    def _mails(self, before):
        return self.env['mail.mail'].sudo().search([('id', 'not in', before)])

    def tearDown(self):
        try:
            self.env['mail.mail'].sudo().search([('state', '=', 'outgoing')]).write({'state': 'cancel'})
        except Exception:               # noqa: BLE001 — never fail a teardown
            pass
        super().tearDown()


@tagged('post_install', '-at_install', 'recruit_p7')
class TestRecruitChannels(ChannelCase):

    # ------------------------------------------------------------- test 1
    def test_01_seeds_six_channels_and_the_sources_once(self):
        self.Channel._seed_all()
        self.Channel._seed_all()
        keys = self.Channel.with_context(active_test=False).search(
            [('company_id', '=', self.company.id)]).mapped('key')
        for key in ('careers', 'linkedin', 'jobstreet', 'vietnamworks', 'referral', 'agency'):
            self.assertEqual(keys.count(key), 1, key)
        Source = self.env['utm.source'].sudo()
        for name in ('JobStreet', 'VietnamWorks', 'Careers page', 'Agency', 'LinkedIn', 'Referral'):
            self.assertEqual(Source.search_count([('name', '=ilike', name)]), 1, name)
        self.assertEqual(self._channel('jobstreet').country_ids, self.id_)
        self.assertEqual(self._channel('vietnamworks').country_ids, self.vn)
        self.assertTrue(self._channel('linkedin').every_country, 'LinkedIn is everywhere')

    # ------------------------------------------------------------- test 2 (model half)
    def test_02_rows_follow_the_country_and_each_link_is_a_stock_tracker(self):
        rows = self._rows(self.req)
        self.assertIn('vietnamworks', rows)
        self.assertNotIn('jobstreet', rows, 'JobStreet is for Indonesia')
        indo = self._role('DEMO P7 Junior Agronomist', self.id_)
        rows_id = self._rows(indo)
        self.assertIn('jobstreet', rows_id)
        self.assertNotIn('vietnamworks', rows_id)
        # the second open makes nothing new
        n = self.env['pb.hiring.role.channel'].sudo().search_count([('requisition_id', '=', self.req.id)])
        self._rows(self.req)
        self.assertEqual(self.env['pb.hiring.role.channel'].sudo().search_count(
            [('requisition_id', '=', self.req.id)]), n)
        rc = self.env['pb.hiring.role.channel'].sudo().search(
            [('requisition_id', '=', self.req.id), ('channel_id.key', '=', 'linkedin')])
        self.assertTrue(rc.source_id, 'a stock job tracker backs the link')
        self.assertEqual(rc.source_id._name, 'hr.recruitment.source')
        self.assertEqual(rc.source_id.job_id, self.req.job_id)
        self.assertIn('utm_source=LinkedIn', rows['linkedin']['link'])
        self.assertIn('/jobs/', rows['linkedin']['link'])
        self.assertIn('/my/refer?role=%s' % self.req.id, rows['referral']['link'])
        self.assertFalse(rows['agency']['link'])
        # the stock Trackers tab sees it (one, not two)
        self.assertEqual(self.req.job_id.job_source_ids.filtered(
            lambda s: s.source_id.name == 'LinkedIn'), rc.source_id)

    # ------------------------------------------------------------- test 3
    def test_03_utm_names_match_case_insensitively(self):
        seeded = self.env.ref('utm.utm_source_linkedin')
        for name in ('linkedin', 'LinkedIn', 'LINKEDIN', ' LinkedIn '):
            self.assertEqual(utm_record(self.env, 'utm.source', name), seeded, name)
        # a duplicate that already exists is merged into the seeded / oldest row
        Source = self.env['utm.source'].sudo()
        first = Source.create({'name': 'Pbseven Board'})
        dup = Source.create({'name': 'PBSEVEN BOARD'})
        app = self.env['hr.applicant'].sudo().create({
            'partner_name': 'DEMO P7 Dup', 'job_id': self.req.job_id.id,
            'company_id': self.company.id, 'source_id': dup.id})
        merged = merge_duplicate_sources(self.env)
        self.assertGreaterEqual(merged, 1)
        self.assertFalse(dup.exists())
        self.assertEqual(app.source_id, first)

    # ------------------------------------------------------------- test 4
    def test_04_mark_posted_close_send_and_count(self):
        rows = self._rows(self.req)
        li = rows['linkedin']
        self.facade.act('p7_mark_posted', {'role_channel_id': li['id'],
                                           'external_url': 'https://www.linkedin.com/jobs/view/1'})
        rows = self._rows(self.req)
        self.assertEqual(rows['linkedin']['state'], 'posted')
        self.assertEqual(rows['linkedin']['posted_by'], self.recruiter.name)
        with self.assertRaises(UserError):
            self.facade.act('p7_mark_posted', {'role_channel_id': li['id'], 'external_url': 'not a link'})
        self.facade.act('p7_close', {'role_channel_id': li['id']})
        self.assertEqual(self._rows(self.req)['linkedin']['state'], 'closed')
        # Send the advert: needs a contact AND the switch
        vw = rows['vietnamworks']
        with self.assertRaises(UserError):
            self.facade.act('p7_send_pack', {'role_channel_id': vw['id']})
        self.env['pb.hiring'].with_user(self.lead).act(
            'p7_channel_save', {'id': self._channel('vietnamworks').id,
                                'contact_email': 'jobs@vietnamworks.example.com'})
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.platform_mail', '0')
        with self.assertRaises(UserError):
            self.facade.act('p7_send_pack', {'role_channel_id': vw['id']})
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.platform_mail', '1')
        before = self.env['mail.mail'].sudo().search([]).ids
        self.facade.act('p7_send_pack', {'role_channel_id': vw['id']})
        mail = self._mails(before).filtered(lambda m: 'vietnamworks.example.com' in (m.email_to or ''))
        self.assertEqual(len(mail), 1)
        self.assertIn('utm_source=VietnamWorks', mail.body_html)
        self.assertTrue(self._rows(self.req)['vietnamworks']['sent_on'])
        # applications are counted per channel
        self.env['hr.applicant'].sudo().create({
            'partner_name': 'DEMO P7 Through LinkedIn', 'job_id': self.req.job_id.id,
            'company_id': self.company.id, 'pb_requisition_id': self.req.id,
            'source_id': self.env.ref('utm.utm_source_linkedin').id})
        panel = self.facade.get_publish_panel(self.req.id)
        rows = {r['key']: r for r in panel['rows']}
        self.assertEqual(rows['linkedin']['apps'], 1)
        self.assertEqual(rows['vietnamworks']['apps'], 0)
        self.assertGreaterEqual(panel['apps'], 1)
        app = self.env['hr.applicant'].sudo().search([('partner_name', '=', 'DEMO P7 Through LinkedIn')])
        self.assertEqual(app.pb_channel_id, self._channel('linkedin'), 'tagged with the channel')

    # ------------------------------------------------------------- test 5
    def test_05_the_connector_seam(self):
        Conn = self.env['pb.hiring.channel.connector']
        self.assertEqual(set(Conn._registry()), {'manual', 'email_pack'})
        self.assertEqual(Conn._get('manual')._name, 'pb.hiring.connector.manual')
        self.assertEqual(Conn._get('email_pack')._name, 'pb.hiring.connector.email_pack')
        with self.assertRaisesRegex(UserError, 'by hand'):
            Conn._get('jobstreet_api', 'JobStreet')
        rc = self.env['pb.hiring.role.channel'].sudo().browse(self._rows(self.req)['linkedin']['id'])
        self.assertEqual(Conn._get('manual').status(rc)['state'], 'not_posted')
        import requests
        with patch.object(requests, 'request', side_effect=requests.ConnectionError('down')):
            with self.assertRaisesRegex(UserError, 'Could not reach JobStreet — nothing was posted'):
                Conn._http('POST', 'https://api.example.com/post', 'JobStreet')

    # ------------------------------------------------------------- test 6
    def test_06_inviting_an_agency_makes_a_portal_login(self):
        vendor = self._vendor()
        with self.assertRaises(AccessError):
            self.facade.act('p7_agency_invite', {'vendor_id': vendor.id})
        before = self.env['mail.mail'].sudo().search([]).ids
        res = self.env['pb.hiring'].with_user(self.lead).act(
            'p7_agency_invite', {'vendor_id': vendor.id, 'email': 'Lan@TalentBridge.example.com'})
        user = self.env['res.users'].sudo().browse(res['user_id'])
        self.assertTrue(res['made'])
        self.assertTrue(user.share)
        self.assertTrue(user.has_group('base.group_portal'))
        self.assertFalse(user.has_group('base.group_user'))
        self.assertIn(user, vendor.portal_user_ids)
        self.assertEqual(user.partner_id.parent_id, vendor.partner_id)
        mail = self._mails(before).filtered(lambda m: m.email_to == user.email)
        self.assertEqual(len(mail), 1)
        self.assertIn('/my/agency', mail.body_html)
        self.assertIn(self.env['pb.hiring']._sender(self.company).split('<')[-1].rstrip('>'),
                      mail.email_from)
        self.assertNotIn('Odoo', mail.body_html)
        # a second invitation links the same person
        res2 = self.env['pb.hiring'].with_user(self.lead).act(
            'p7_agency_invite', {'vendor_id': vendor.id, 'email': 'lan@talentbridge.example.com'})
        self.assertEqual(res2['user_id'], user.id)
        self.assertFalse(res2['made'])
        # an internal sign-in is never an agency's
        with self.assertRaises(UserError):
            self.env['pb.hiring'].with_user(self.lead).act(
                'p7_agency_invite', {'vendor_id': vendor.id, 'email': self.recruiter.email})
        # taking the access away switches the login off
        self.env['pb.hiring'].with_user(self.lead).act(
            'p7_agency_unlink', {'vendor_id': vendor.id, 'user_id': user.id})
        self.assertNotIn(user, vendor.portal_user_ids)
        self.assertFalse(user.active)

    # ------------------------------------------------------------- test 7
    def test_07_several_agencies_and_the_migration(self):
        one, two = self._vendor(), self._vendor('DEMO P7 Second Agency', 'jobs@second.example.com')
        one._pb_portal_login('lan@talentbridge.example.com')
        before = self.env['mail.mail'].sudo().search([]).ids
        self.facade.act('p7_agency_add', {'requisition_id': self.req.id, 'vendor_id': one.id})
        self.facade.act('p7_agency_add', {'requisition_id': self.req.id, 'vendor_id': two.id})
        self.facade.act('p7_agency_add', {'requisition_id': self.req.id, 'vendor_id': two.id})
        self.assertEqual(self.req.agency_vendor_ids, one | two)
        self.assertEqual(self.req.agency_vendor_id, one, 'the old pointer reads the first')
        mails = self._mails(before)
        boss = mails.filtered(lambda m: m.email_to == 'demo.p7.boss@example.com')
        self.assertEqual(len(boss), 2, 'once per agency added, never twice')
        self.assertTrue(any('DEMO P7 Second Agency' in (m.body_html or '') for m in boss))
        to_one = mails.filtered(lambda m: m.email_to == 'lan@talentbridge.example.com')
        self.assertEqual(len(to_one), 1, 'the agency gets the role on its portal')
        self.assertIn('/my/agency/role/%s' % self.req.id, to_one.body_html)
        to_two = mails.filtered(lambda m: m.email_to == 'jobs@second.example.com')
        self.assertEqual(len(to_two), 1, 'no sign-in yet: its contact email')
        for m in to_one | to_two:
            self.assertNotIn('123456789', m.body_html or '', 'never the budget')
            self.assertNotIn('DEMO P7 Head', m.body_html or '', 'never the requester')
        # the migration copies the old single column into the set
        cr = self.env.cr
        cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name='pb_hiring_requisition' "
                   "AND column_name='agency_vendor_id'")
        if not cr.fetchone():
            cr.execute("ALTER TABLE pb_hiring_requisition ADD COLUMN agency_vendor_id integer")
        other = self._role('DEMO P7 Plant Lead', self.vn)
        cr.execute("UPDATE pb_hiring_requisition SET agency_vendor_id=%s WHERE id=%s", (two.id, other.id))
        mod = _migration('post-10_channels')
        self.assertGreaterEqual(mod._copy_agencies(cr), 1)
        self.assertEqual(mod._copy_agencies(cr), 0, 'a second run copies nothing')
        other.invalidate_recordset()
        self.assertEqual(other.agency_vendor_ids, two)

    # ------------------------------------------------------------- test 9 (the rule)
    def test_09_the_six_month_rule(self):
        vendor = self._vendor()
        self.req.sudo().write({'agency_vendor_ids': [(4, vendor.id)]})
        Sub = self.env['pb.hiring.agency.submission'].sudo()
        portal_user, _made = vendor._pb_portal_login('lan@talentbridge.example.com')
        # an active candidate on ANOTHER role of the company
        elsewhere = self._role('DEMO P7 Other Role', self.vn)
        self.env['hr.applicant'].sudo().create({
            'partner_name': 'DEMO P7 Active', 'email_from': 'active.p7@example.com',
            'job_id': elsewhere.job_id.id, 'company_id': self.company.id,
            'pb_requisition_id': elsewhere.id})
        n_apps = self.env['hr.applicant'].sudo().with_context(active_test=False).search_count([])
        sub = Sub._submit(vendor, self.req, portal_user, {
            'name': 'DEMO P7 Active', 'email': 'ACTIVE.p7@example.com', 'phone': '+84 912 000 001'})
        self.assertEqual(sub.state, 'refused_rule')
        self.assertFalse(sub.applicant_id)
        self.assertIn('already a candidate with us', sub.refusal_reason)
        self.assertIn('6-month rule', sub.refusal_reason)
        self.assertNotIn('DEMO P7 Other Role', sub.refusal_reason, 'only the date')
        self.assertEqual(self.env['hr.applicant'].sudo().with_context(active_test=False).search_count([]),
                         n_apps, 'no candidate made')

        def past(email, days):
            app = self.env['hr.applicant'].sudo().create({
                'partner_name': 'DEMO P7 Past %s' % days, 'email_from': email,
                'job_id': elsewhere.job_id.id, 'company_id': self.company.id, 'active': False})
            self.env.cr.execute("UPDATE hr_applicant SET create_date = now() - interval '%s days' "
                                "WHERE id = %%s" % days, (app.id,))
            app.invalidate_recordset()
            return app
        past('five.p7@example.com', 150)
        past('seven.p7@example.com', 215)
        five = Sub._submit(vendor, self.req, portal_user, {
            'name': 'DEMO P7 Five', 'email': 'five.p7@example.com', 'phone': '+84 912 000 005'})
        self.assertEqual(five.state, 'refused_rule')
        self.assertIn('applied to us on', five.refusal_reason)
        when = (fields.Date.context_today(self.env.user) - timedelta(days=150))
        self.assertIn(when.strftime('%b %Y'), five.refusal_reason)
        seven = Sub._submit(vendor, self.req, portal_user, {
            'name': 'DEMO P7 Seven', 'email': 'seven.p7@example.com', 'phone': '+84 912 000 007'})
        self.assertEqual(seven.state, 'accepted')
        # the window is a parameter
        self.env['ir.config_parameter'].sudo().set_param('pb_hiring.agency_cooling_months', '3')
        again = Sub._submit(vendor, self.req, portal_user, {
            'name': 'DEMO P7 Five', 'email': 'five.p7@example.com', 'phone': '+84 912 000 005'})
        self.assertEqual(again.state, 'accepted')
        # and the same phone (another email) is the same person
        phone = Sub._submit(vendor, self.req, portal_user, {
            'name': 'DEMO P7 Seven Again', 'email': 'seven.other@example.com', 'phone': '+84 912 000 007'})
        self.assertEqual(phone.state, 'refused_rule')
        # every attempt is logged
        self.assertEqual(Sub.search_count([('vendor_id', '=', vendor.id)]), 5)

    # ------------------------------------------------------------- test 10
    def test_10_coarse_stages_follow_the_candidate(self):
        vendor = self._vendor()
        self.req.sudo().write({'agency_vendor_ids': [(4, vendor.id)]})
        user, _m = vendor._pb_portal_login('lan@talentbridge.example.com')
        Sub = self.env['pb.hiring.agency.submission'].sudo()
        sub = Sub._submit(vendor, self.req, user, {
            'name': 'DEMO P7 Coarse', 'email': 'coarse.p7@example.com', 'phone': '+84 912 000 010'})
        app = sub.applicant_id
        self.assertEqual(app.stage_id.pb_key, 'screening')
        self.assertEqual(sub.coarse_stage, 'in_review')
        Stage = self.env['hr.recruitment.stage']
        for key, coarse in (('phone', 'interviewing'), ('discussion_1', 'interviewing'),
                            ('offer', 'offer'), ('cv_reject', 'not_selected')):
            app.write({'stage_id': Stage._pb_stage(key).id})
            sub.invalidate_recordset(['coarse_stage', 'coarse_label'])
            self.assertEqual(sub.coarse_stage, coarse, key)
        refused = Sub._submit(vendor, self.req, user, {
            'name': 'DEMO P7 Coarse', 'email': 'coarse.p7@example.com', 'phone': '+84 912 000 010'})
        self.assertEqual(refused.coarse_label, 'Not accepted (6-month rule)')

    # ------------------------------------------------------------- test 11
    def test_11_figures_per_agency(self):
        vendor = self._vendor()
        self.req.sudo().write({'agency_vendor_ids': [(4, vendor.id)]})
        user, _m = vendor._pb_portal_login('lan@talentbridge.example.com')
        Sub = self.env['pb.hiring.agency.submission'].sudo()
        a = Sub._submit(vendor, self.req, user, {'name': 'DEMO P7 A', 'email': 'a.p7@example.com',
                                                 'phone': '+84 912 000 021'})
        Sub._submit(vendor, self.req, user, {'name': 'DEMO P7 B', 'email': 'b.p7@example.com',
                                             'phone': '+84 912 000 022'})
        Sub._submit(vendor, self.req, user, {'name': 'DEMO P7 A', 'email': 'a.p7@example.com',
                                             'phone': '+84 912 000 021'})
        a.applicant_id.write({'stage_id': self.env['hr.recruitment.stage']._pb_stage('discussion_1').id})
        vendor.invalidate_recordset()
        # RECRUIT P8: "put forward" counts accepted people; the refusal is its own figure.
        self.assertEqual(vendor.hiring_submitted, 2)
        self.assertEqual(vendor.hiring_refused, 1)
        self.assertEqual(vendor.hiring_interviewed, 1)
        self.assertEqual(vendor.hiring_open_count, 1)
        action = vendor.action_open_submissions()
        self.assertIn('views', action)
        rows = self.env['pb.hiring.analytics'].with_user(self.lead)._agency_rows()
        row = next(r for r in rows if r['id'] == vendor.id)
        self.assertEqual((row['submitted'], row['refused'], row['interviewed']), (2, 1, 1))
        board = self.env['pb.hiring.analytics'].with_user(self.lead).get_board()
        self.assertIn('agencies', board)
        out = self.env['pb.hiring.analytics'].with_user(self.lead).export_xlsx(kind='agency')
        self.assertTrue(out['ok'])
        import base64
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(base64.b64decode(out['file_b64'])))
        self.assertIn('Agencies', wb.sheetnames)
        # set-up shows the agency with its figures and the live channels
        setup = self.env['pb.hiring'].with_user(self.lead).get_setup()
        self.assertIn('channels', [c['key'] for c in setup['cards']])
        self.assertIn('agencies', [c['key'] for c in setup['cards']])
        ag = next(r for r in setup['agencies']['rows'] if r['id'] == vendor.id)
        self.assertEqual(ag['figures']['submitted'], 2)

    def test_11b_channel_grid_and_the_header_count(self):
        lead = self.env['pb.hiring'].with_user(self.lead)
        vw = self._channel('vietnamworks')
        # VietnamWorks off for Vietnam: the Vietnamese role no longer offers it
        lead.act('p7_channel_country', {'id': vw.id, 'country_id': self.vn.id, 'on': False})
        self.assertNotIn('vietnamworks', self._rows(self.req))
        # and on for Indonesia: an Indonesian role does
        lead.act('p7_channel_country', {'id': vw.id, 'country_id': self.id_.id, 'on': True})
        indo = self._role('DEMO P7 Field Agronomist ID', self.id_)
        self.assertIn('vietnamworks', self._rows(indo))
        # a recruiter cannot change channels
        with self.assertRaises(AccessError):
            self.facade.act('p7_channel_save', {'id': vw.id, 'name': 'Nope'})
        # LinkedIn "everywhere" switched off for Indonesia keeps the rest of the grid
        li = self._channel('linkedin')
        lead.act('p7_channel_country', {'id': li.id, 'country_id': self.id_.id, 'on': False})
        self.assertFalse(li.every_country)
        self.assertNotIn(self.id_, li.country_ids)
        self.assertIn(self.vn, li.country_ids)
        # VietnamWorks with no country left is offered nowhere (never "everywhere")
        lead.act('p7_channel_country', {'id': vw.id, 'country_id': self.id_.id, 'on': False})
        self.assertFalse(vw.every_country or vw.country_ids)
        self.assertNotIn('vietnamworks', self._rows(indo))
        # the header pill: careers + LinkedIn posted
        self.facade.act('p7_publish', {'requisition_id': self.req.id})
        rows = self._rows(self.req)
        self.facade.act('p7_mark_posted', {'role_channel_id': rows['linkedin']['id']})
        live = self.facade.get_requisition(self.req.id)['p7_live']
        self.assertGreaterEqual(live, 2)


@tagged('post_install', '-at_install', 'recruit_p7')
class TestRecruitChannelsHttp(HttpCase, ChannelCase):
    """Over HTTP: the tracked link tags the application; the agency portal."""

    def _public_job(self, req):
        website = self.env['website'].search([], order='id', limit=1)
        req.sudo().write({'company_id': website.company_id.id})
        req.job_id.sudo().write({'is_published': True, 'website_id': False,
                                 'company_id': website.company_id.id})
        Form = self.env['pb.hiring.form'].sudo()
        from ..models.forms_p2 import BUILTINS
        from ..models.forms_p2 import CONSENT_EN
        form = Form.create({'name': 'DEMO P7 short form', 'company_id': website.company_id.id,
                            'consent_text': CONSENT_EN})
        for i, key in enumerate(('name', 'email', 'consent')):
            spec = BUILTINS[key]
            self.env['pb.hiring.form.field'].sudo().create({
                'form_id': form.id, 'kind': key, 'key': key, 'label': spec['label'],
                'required': True, 'sequence': (i + 1) * 10})
        req.sudo().write({'pb_form_id': form.id})
        self.Channel._ensure_for(website.company_id)
        return website

    # ------------------------------------------------------------- test 2 (HTTP half)
    def test_02_applying_through_the_linkedin_link_tags_the_candidate(self):
        website = self._public_job(self.req)
        self.env['pb.hiring'].sudo()._p7_rows(self.req)
        rc = self.env['pb.hiring.role.channel'].sudo().search([
            ('requisition_id', '=', self.req.id), ('channel_id.key', '=', 'linkedin')])
        self.assertEqual(len(rc), 1)
        link = rc._link()
        parts = urlsplit(link)
        self.authenticate(None, None)
        self.opener.cookies.set('frontend_lang', 'en_US')
        res = self.url_open('%s?%s' % (parts.path, parts.query))
        self.assertEqual(res.status_code, 200, link)
        slug = self.env['ir.http']._slug(self.req.job_id)
        page = self.url_open('/jobs/apply/%s' % slug)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        res = self.url_open('/hiring/apply/%s' % self.req.job_id.id, data={
            'csrf_token': token, 'name': 'Nguyen Thi Lan P7', 'email': 'lan.p7.apply@example.com',
            'consent': '1'})
        self.assertEqual(res.status_code, 200)
        app = self.env['hr.applicant'].sudo().search([('email_from', '=', 'lan.p7.apply@example.com')])
        self.assertEqual(len(app), 1, res.text[:500] if not app else '')
        self.assertEqual(app.source_id, self.env.ref('utm.utm_source_linkedin'))
        self.assertEqual(app.pb_channel_id.key, 'linkedin')
        rows = {r['key']: r for r in self.env['pb.hiring'].sudo().get_publish_panel(self.req.id)['rows']}
        self.assertEqual(rows['linkedin']['apps'], 1)

    # ------------------------------------------------------------- tests 8, 9, 10 over HTTP
    def test_08_09_10_the_agency_portal(self):
        vendor = self._vendor()
        other_vendor = self._vendor('DEMO P7 Rival Agency', 'jobs@rival.example.com')
        user, _m = vendor._pb_portal_login('lan@talentbridge.example.com')
        user.sudo().write({'password': PASSWORD})
        jd = self.env['pb.hiring.jd'].sudo().create({
            'requisition_id': self.req.id, 'body': '<p>Visit farms in the Mekong delta every week.</p>',
            'summary': 'Grow our farm accounts.'})
        jd.action_make_final()
        self.req.sudo().write({'agency_vendor_ids': [(4, vendor.id)],
                               'pb_target_close_date': fields.Date.today() + timedelta(days=30)})
        rival = self._role('DEMO P7 Rival Role', self.vn)
        rival.sudo().write({'agency_vendor_ids': [(4, other_vendor.id)]})
        # an internal recruiter's candidate + note on the role: never on the portal
        self.env['hr.applicant'].sudo().create({
            'partner_name': 'DEMO P7 Secret Candidate', 'email_from': 'secret.p7@example.com',
            'job_id': self.req.job_id.id, 'company_id': self.company.id,
            'pb_requisition_id': self.req.id, 'applicant_notes': 'DEMO P7 private note'})
        # an internal user is sent to the board
        self.authenticate(self.recruiter.login, PASSWORD)
        res = self.url_open('/my/agency', allow_redirects=False)
        self.assertIn(res.status_code, (301, 302, 303))
        self.assertIn('action_pb_hiring_board', res.headers.get('Location', ''))
        # the agency
        self.authenticate(user.login, PASSWORD)
        home = self.url_open('/my/agency')
        self.assertEqual(home.status_code, 200)
        self.assertIn('DEMO P7 Territory Manager', home.text)
        self.assertNotIn('DEMO P7 Rival Role', home.text)
        res = self.url_open('/my', allow_redirects=False)
        self.assertIn('/my/agency', res.headers.get('Location', ''))
        self.assertEqual(self.url_open('/my/agency/role/%s' % rival.id).status_code, 404)
        page = self.url_open('/my/agency/role/%s' % self.req.id)
        self.assertEqual(page.status_code, 200)
        self.assertIn('Mekong delta', page.text)
        body = page.text[page.text.index('pbme pbag'):]
        body = body[:body.index('<footer')] if '<footer' in body else body
        for secret in ('DEMO P7 Head', 'DEMO P7 Boss', 'DEMO P7 Recruiter', '123456789', '123,456,789',
                       'DEMO P7 Secret Candidate', 'DEMO P7 private note', 'Sells to farms'):
            self.assertNotIn(secret, body, secret)
        self.assertNotIn('Odoo', body)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        url = '/my/agency/role/%s/submit' % self.req.id
        good = {'csrf_token': token, 'name': 'DEMO P7 Pham Van An', 'email': 'an.p7@example.com',
                'phone': '+84 912 345 678', 'location': 'Can Tho', 'agreed': '1',
                'note': 'Ten years selling seed.'}
        Sub = self.env['pb.hiring.agency.submission'].sudo()
        # missing CV → re-rendered with the sentence, nothing logged
        res = self.url_open(url, data=good)
        self.assertIn("Attach the person", res.text)
        self.assertEqual(Sub.search_count([('vendor_id', '=', vendor.id)]), 0)
        # a renamed program → refused
        res = self.url_open(url, data=good, files={'cv': ('cv.pdf', b'MZ\x90\x00 program', 'application/pdf')})
        self.assertIn('not really a PDF', res.text)
        # valid → accepted, a candidate on the role, Agency source, the recruiter's to-do
        res = self.url_open(url, data=good, files={'cv': ('cv.pdf', PDF, 'application/pdf')})
        self.assertEqual(res.status_code, 200)
        self.assertIn('is with the recruiter', res.text)
        sub = Sub.search([('vendor_id', '=', vendor.id)])
        self.assertEqual(sub.state, 'accepted')
        app = sub.applicant_id
        self.assertEqual(app.pb_requisition_id, self.req)
        self.assertEqual(app.stage_id.pb_key, 'screening')
        self.assertEqual(app.source_id.name, 'Agency')
        self.assertEqual(app.pb_agency_vendor_id, vendor)
        self.assertEqual(app.pb_channel_id.key, 'agency')
        self.assertTrue(self.env['ir.attachment'].sudo().search_count(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id)]))
        self.assertTrue(self.env['mail.activity'].sudo().search_count(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id),
             ('user_id', '=', self.recruiter.id)]))
        card = next(c for c in self.env['pb.hiring'].with_user(self.recruiter)._candidates(self.req)
                    if c['id'] == app.id)
        self.assertEqual(card['agency'], vendor.name)
        # the same email again → the refusal sentence, logged, nothing made
        page = self.url_open('/my/agency/role/%s' % self.req.id)
        token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
        res = self.url_open(url, data=dict(good, csrf_token=token, name='DEMO P7 An again'),
                            files={'cv': ('cv.pdf', PDF, 'application/pdf')})
        self.assertIn('already a candidate with us', res.text)
        self.assertIn('Nothing was sent', res.text)
        self.assertEqual(Sub.search_count([('vendor_id', '=', vendor.id)]), 2)
        # test 10: people page, coarse stages
        app.write({'stage_id': self.env['hr.recruitment.stage']._pb_stage('discussion_1').id})
        people = self.url_open('/my/agency/people')
        self.assertIn('Interviewing', people.text)
        self.assertIn('Not accepted (6-month rule)', people.text)
        self.assertNotIn('DEMO P7 Secret Candidate', people.text)
