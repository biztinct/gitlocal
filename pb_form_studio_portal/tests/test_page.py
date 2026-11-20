# -*- coding: utf-8 -*-
"""FS-12 numbered tests — the My Payobook page builder (FS11_FS12_REPORT.md).

 6  no page → My Profile byte-identical to the page without this module
 7  a section, three fields (own, standard, country-limited), order, widths,
    Publish → the page shows them in order; another country does not get the
    country-limited one
 8  on the page ⇄ "Show on My Payobook" tick, both ways
 9  "Request a change" lists exactly the changeable fields; HR approves →
    request waiting, value unchanged; saves at once → saved with history;
    a sensitive box refuses "Saves at once"
10  a locked box cannot be made changeable (page publish + direct call)
11  access: employee / HR manager / administrator / no employee link
12  banner: ok, too big, wrong kind (SVG); tint; heading in vi
13  preview is look-only and administrator-only
14  history, restore ("Undo"), "Reset to the standard page"
(15 two workers: nothing is cached in a worker — every request reads the
published row; 16 payslips and 17 words / console / phone width are run by
the report's scripts and the browser walk.)
"""
import base64
import re
import secrets
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.pb_me_details.tests.common import decide, seat

EMP = 'hr.employee'
HOST = 'employee_detail'
PAGE = 'my_profile_page'
PASSWORD = secrets.token_urlsafe(16)
#: per-request security tokens (the form's and the session script's)
CSRF = re.compile(r'[0-9a-f]{40}o[0-9]+')
PNG = base64.b64encode(b'\x89PNG\r\n\x1a\n' + b'\x00' * 64).decode()


@tagged('post_install', '-at_install', 'pb_form_studio_portal', 'fs12')
class TestFs12Page(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Studio = type(cls.env['pb.form.studio'])
        cls.startClassPatcher(patch.object(Studio, '_pbfs_busy', lambda s: ''))
        cls.company = cls.env.company
        cls.india = cls.env.ref('base.in')
        cls.admin = new_test_user(cls.env, 'fs12_admin', name='DEMO FS12 Admin', password=PASSWORD,
                                  groups='base.group_user,base.group_system,hr.group_hr_manager')
        cls.hr = new_test_user(cls.env, 'fs12_hr', name='DEMO FS12 HR', password=PASSWORD,
                               groups='base.group_user,hr.group_hr_user,hr.group_hr_manager')
        cls.me = new_test_user(cls.env, 'fs12_me', name='DEMO FS12 Lan', password=PASSWORD,
                               groups='base.group_portal')
        cls.other = new_test_user(cls.env, 'fs12_other', name='DEMO FS12 Arjun', password=PASSWORD,
                                  groups='base.group_portal')
        cls.nobody = new_test_user(cls.env, 'fs12_nobody', name='DEMO FS12 Visitor',
                                   password=PASSWORD, groups='base.group_portal')
        Emp = cls.env[EMP].with_context(tracking_disable=True)
        cls.emp = Emp.create({'name': 'DEMO FS12 Lan', 'company_id': cls.company.id,
                              'payroll_country': 'VN', 'user_id': cls.me.id,
                              'work_email': 'lan.demo@example.com', 'private_phone': '+84 1',
                              'pb_blood_type': 'A+'})
        cls.emp_in = Emp.create({'name': 'DEMO FS12 Arjun', 'company_id': cls.company.id,
                                 'payroll_country': 'IN', 'user_id': cls.other.id})
        cls.emp_in.sudo().pbfs_country_of_work_id = cls.india
        seat(cls.env, cls.company, 'hr_lead', cls.hr)
        S = cls.env['pb.form.studio'].with_user(cls.admin)
        cls.shirt = S.create_field(HOST, {'type': 'select', 'label': 'DEMO Shirt size',
                                          'options': ['S', 'M', 'L'], 'vis': 'hr'})['name']
        cls.pan = S.create_field(HOST, {'type': 'text', 'label': 'DEMO India badge', 'vis': 'hr',
                                        'country_ids': [cls.india.id]})['name']
        cls.emp_in.sudo().write({cls.pan: 'DEMO IN-7'})
        keys = [k for k, _l in cls.env[EMP]._fields[cls.shirt]._description_selection(cls.env)]
        cls.emp.sudo().write({cls.shirt: keys[1]})

    def setUp(self):
        super().setUp()
        if 'pb.privacy.notice' in self.env:
            self.env['pb.privacy.notice'].sudo().search(
                [('state', '=', 'published')]).write({'state': 'replaced'})

    # ---------------------------------------------------------------- utils
    def S(self, user=None):
        return self.env['pb.form.studio'].with_user(user or self.admin)

    def spec(self, fields_, cols=2, extra=()):
        return {'header': {'title': {'en_US': 'DEMO Our people', 'vi_VN': 'DEMO Người của chúng tôi'},
                           'sub': {}, 'tint': 'teal', 'banner': False, 'banner_alt': {}},
                'sections': [{'id': 's1', 'title': {'en_US': 'DEMO About you'}, 'cols': cols,
                              'fields': fields_}] + list(extra),
                'side': ['door', 'requests']}

    def publish(self, spec, updates=None, companies=None):
        data = self.S().page_studio()
        res = self.S().page_publish({'spec': spec, 'companies': companies or {},
                                     'updates': updates or {}, 'base_version': data['version'],
                                     'changes': ['DEMO change']})
        self.assertTrue(res.get('ok'), res)
        return res

    def html(self, url='/my/profile', login='fs12_me'):
        self.authenticate(login, PASSWORD)
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        return res.text

    def meta(self, name):
        return self.env['pb.form.field.meta'].sudo().search([('model', '=', EMP), ('name', '=', name)])

    # ------------------------------------------------------------------ 6
    def test_06_no_page_is_byte_identical(self):
        view = self.env.ref('pb_form_studio_portal.portal_my_profile_page')
        with_module = CSRF.sub('', self.html())
        view.sudo().active = False
        try:
            without = CSRF.sub('', self.html())
        finally:
            view.sudo().active = True
        self.assertEqual(with_module, without)
        self.assertNotIn('Edit this page', with_module, 'employees get no builder button')
        self.assertNotIn('pb_page_builder', with_module)
        # nothing was made by opening it
        self.assertFalse(self.env['pb.form.layout'].sudo().search([('host_key', '=', PAGE)]))

    # ------------------------------------------------------------------ 7
    def test_07_sections_fields_order_country(self):
        fields_ = [{'name': self.shirt, 'width': 'half'}, {'name': 'work_email', 'width': 'full'},
                   {'name': self.pan, 'width': 'half'}]
        extra = [{'id': 's2', 'title': {'en_US': 'DEMO Contact'}, 'cols': 1,
                  'fields': [{'name': 'private_phone', 'width': 'half'}]}]
        self.publish(self.spec(fields_, extra=extra))
        page = self.env['pb.form.studio'].portal_page_render(self.emp.sudo())
        self.assertEqual([s['title'] for s in page['sections']], ['DEMO About you', 'DEMO Contact'])
        self.assertEqual([f['name'] for f in page['sections'][0]['fields']], [self.shirt, 'work_email'],
                         'the India-only field is not drawn for a Vietnam employee')
        self.assertEqual(page['sections'][0]['fields'][1]['width'], 'full')
        page_in = self.env['pb.form.studio'].portal_page_render(self.emp_in.sudo())
        self.assertIn(self.pan, [f['name'] for f in page_in['sections'][0]['fields']])
        html = self.html()
        self.assertIn('DEMO About you', html)
        self.assertIn('DEMO Shirt size', html)
        self.assertLess(html.index('DEMO Shirt size'), html.index('lan.demo@example.com'))
        self.assertNotIn('DEMO India badge', html)
        self.assertIn('pbfp-tint-teal', html)
        self.assertNotIn('Odoo', html.replace('odoo', ''))
        html_in = self.html(login='fs12_other')
        self.assertIn('DEMO IN-7', html_in)

    # ------------------------------------------------------------------ 8
    def test_08_page_and_tick_are_one_fact(self):
        self.publish(self.spec([{'name': self.shirt, 'width': 'half'},
                                {'name': 'pb_blood_type', 'width': 'half'}]))
        self.assertTrue(self.meta(self.shirt).portal_show)
        self.assertTrue(self.meta('pb_blood_type').portal_show)
        self.assertFalse(self.meta('mobile_phone').portal_show)
        # the employee builder unticks one, ticks another: the page follows
        self.S().update_portal(EMP, 'pb_blood_type', {'portal_show': False})
        self.S().update_portal(EMP, 'mobile_phone', {'portal_show': True})
        page = self.env['pb.form.studio'].portal_page_render(self.emp.sudo())
        names = [f['name'] for f in page['sections'][0]['fields']]
        self.assertNotIn('pb_blood_type', names)
        self.assertEqual(names[-1], 'mobile_phone', 'a newly ticked field joins the first section')
        data = self.S().page_studio()
        self.assertIn('mobile_phone', data['ticked'])
        self.assertNotIn('pb_blood_type', data['ticked'])
        # taking it off the page unticks it
        self.publish(self.spec([{'name': self.shirt, 'width': 'half'}]))
        self.assertFalse(self.meta('mobile_phone').portal_show)

    # ------------------------------------------------------------------ 9
    def _send(self, vals):
        html = self.html()
        token = re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)
        data = dict(vals, csrf_token=token)
        return self.url_open('/my/profile/page/send', data=data)

    def test_09_request_a_change(self):
        self.publish(self.spec([{'name': 'mobile_phone', 'width': 'half'},
                                {'name': 'pb_blood_type', 'width': 'half'},
                                {'name': 'work_email', 'width': 'half'},
                                {'name': 'private_phone', 'width': 'half'}]),
                     updates={'mobile_phone': {'portal_edit': True, 'portal_mode': 'instant'},
                              'pb_blood_type': {'portal_edit': True}})
        html = self.html()
        form = html[html.index('/my/profile/page/send'):]
        boxes = re.findall(r'name="(pbfr__\w+|x_\w+)"', form)
        self.assertEqual(boxes, ['pbfr__mobile_phone', 'pbfr__pb_blood_type', 'x_phone'],
                         'exactly the changeable fields, in page order')
        audits = self.env['pb.form.audit'].sudo().search_count([('action', '=', 'portal_change')])
        res = self._send({'pbfr__mobile_phone': '+84 999', 'pbfr__pb_blood_type': 'O-'})
        self.assertIn('done=sent', res.url)
        emp = self.emp.sudo()
        emp.invalidate_recordset()
        self.assertEqual(emp.mobile_phone, '+84 999', 'saved at once')
        self.assertEqual(emp.pb_blood_type, 'A+', 'waits for HR')
        self.assertEqual(self.env['pb.form.audit'].sudo().search_count(
            [('action', '=', 'portal_change')]), audits + 1)
        req = self.env['pb.me.detail.request'].sudo().search([
            ('employee_id', '=', self.emp.id), ('kind', '=', 'company_details'),
            ('state', '=', 'hr_review')])
        self.assertEqual(len(req), 1)
        self.assertTrue(req.approval_request_id, "in the approver's inbox")
        decide(self.env, req, 'approve')
        emp.invalidate_recordset()
        self.assertEqual(emp.pb_blood_type, 'O-')
        # sensitive: never "Saves at once"
        with self.assertRaises(UserError):
            self.publish(self.spec([{'name': 'pb_blood_type', 'width': 'half'}]),
                         updates={'pb_blood_type': {'portal_edit': True, 'portal_mode': 'instant'}})
        # today's personal box goes through today's change request
        res = self._send({'x_phone': '+84 2'})
        self.assertIn('/my/profile/request/', res.url)

    # ------------------------------------------------------------------ 10
    def test_10_locked_box_never_changeable(self):
        with self.assertRaises(UserError):
            self.publish(self.spec([{'name': 'work_email', 'width': 'half'}]),
                         updates={'work_email': {'portal_edit': True}})
        with self.assertRaises(UserError):
            self.S().update_portal(EMP, 'work_email', {'portal_show': True, 'portal_edit': True})
        self.assertFalse(self.meta('work_email').portal_edit)
        # a forged POST for it is refused, nothing written
        self.publish(self.spec([{'name': 'work_email', 'width': 'half'},
                                {'name': 'mobile_phone', 'width': 'half'}]),
                     updates={'mobile_phone': {'portal_edit': True}})
        res = self._send({'pbfr__work_email': 'forged@example.com'})
        self.assertIn('pbfp-alert', res.text)
        emp = self.emp.sudo()
        emp.invalidate_recordset()
        self.assertEqual(emp.work_email, 'lan.demo@example.com')
        # a pay figure is never offered at all
        self.assertNotIn('wage', self.S().page_studio()['fields'])
        with self.assertRaises(UserError):
            self.publish(self.spec([{'name': 'wage', 'width': 'half'}]))

    # ------------------------------------------------------------------ 11
    def test_11_access(self):
        for user in (self.hr, self.me):
            with self.assertRaises(AccessError):
                self.S(user).page_studio()
            with self.assertRaises(AccessError):
                self.S(user).page_publish({'spec': self.spec([])})
            with self.assertRaises(AccessError):
                self.S(user).page_reset()
            with self.assertRaises(AccessError):
                self.S(user).page_upload_banner('a.png', PNG)
        with self.assertRaises(AccessError):         # another person's values by id
            self.S(self.me).portal_page_render(self.emp_in.id)
        self.publish(self.spec([{'name': self.shirt, 'width': 'half'}]))
        self.assertNotIn('Edit this page', self.html())
        # no employee link: the stock way, as today (back to /my)
        self.authenticate('fs12_nobody', PASSWORD)
        res = self.url_open('/my/profile', allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        # the administrator with an employee record gets the button
        self.env[EMP].sudo().create({'name': 'DEMO FS12 Admin', 'user_id': self.admin.id,
                                     'company_id': self.company.id})
        html = self.html(login='fs12_admin')
        self.assertIn('Edit this page', html)

    # ------------------------------------------------------------------ 12
    def test_12_banner_tint_words(self):
        res = self.S().page_upload_banner('banner.png', PNG)
        self.assertTrue(res['id'])
        with self.assertRaises(UserError):
            self.S().page_upload_banner('big.png', base64.b64encode(
                b'\x89PNG\r\n\x1a\n' + b'\x00' * (2 * 1024 * 1024 + 1)).decode())
        with self.assertRaises(UserError):
            self.S().page_upload_banner('evil.svg', base64.b64encode(
                b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>').decode())
        with self.assertRaises(UserError):
            self.S().page_upload_banner('fake.png', base64.b64encode(b'GIF89a....').decode())
        spec = self.spec([{'name': self.shirt, 'width': 'half'}])
        spec['header']['banner'] = res['id']
        spec['header']['banner_alt'] = {'en_US': 'DEMO Our office'}
        self.publish(spec)
        html = self.html()
        self.assertIn('/my/profile/banner/%s' % res['id'], html)
        self.assertIn('DEMO Our office', html)
        img = self.url_open('/my/profile/banner/%s' % res['id'])
        self.assertEqual(img.status_code, 200)
        self.assertEqual(img.headers.get('Content-Type'), 'image/png')
        self.authenticate(None, None)
        anon = self.url_open('/my/profile/banner/%s' % res['id'], allow_redirects=False)
        self.assertIn(anon.status_code, (302, 303, 404), 'signed-out visitors never get it')
        bad = self.spec([{'name': self.shirt, 'width': 'half'}])
        bad['header']['tint'] = 'linear-gradient(red, blue)'
        with self.assertRaises(UserError):
            self.publish(bad)
        # the heading in Vietnamese
        # the heading in the reader's language (the website picks the language)
        self.env['res.lang']._activate_lang('vi_VN')
        page = self.env['pb.form.studio'].with_context(lang='vi_VN').portal_page_render(self.emp.sudo())
        self.assertEqual(page['header']['title'], 'DEMO Người của chúng tôi')
        page = self.env['pb.form.studio'].with_context(lang='id_ID').portal_page_render(self.emp.sudo())
        self.assertEqual(page['header']['title'], 'DEMO Our people', 'no Indonesian written: English')

    # ------------------------------------------------------------------ 13
    def test_13_preview_look_only(self):
        url = '/my/profile/preview?employee_id=%s&source=live' % self.emp.id
        html = self.html(url, login='fs12_admin')
        self.assertIn('pbfp-preview', html)
        self.assertIn('DEMO FS12 Lan', html)
        self.assertIn('is-preview', html)
        self.authenticate('fs12_me', PASSWORD)
        self.assertEqual(self.url_open(url).status_code, 404)
        self.authenticate('fs12_hr', PASSWORD)
        self.assertEqual(self.url_open(url).status_code, 404)

    # ------------------------------------------------------------------ 14
    def test_14_history_restore_reset(self):
        before = self.meta('pb_blood_type').portal_show if self.meta('pb_blood_type') else False
        self.publish(self.spec([{'name': self.shirt, 'width': 'half'}]))
        self.publish(self.spec([{'name': 'pb_blood_type', 'width': 'half'}]))
        hist = self.S().page_studio()['history']
        self.assertEqual(len(hist), 2)
        old = self.S().page_version(hist[1]['id'])
        self.assertEqual(old['spec']['sections'][0]['fields'][0]['name'], self.shirt)
        self.S().page_reset()
        self.assertFalse(self.env['pb.form.layout'].sudo().search([('host_key', '=', PAGE)]))
        self.assertIsNone(self.env['pb.form.studio'].portal_page_render(self.emp.sudo()))
        self.assertEqual(bool(self.meta('pb_blood_type').portal_show), bool(before),
                         'the tick is back to before the page')
        self.assertFalse(self.meta(self.shirt).portal_show)
        html = self.html()
        self.assertNotIn('pbfp', html.replace('pbfp-edit', ''))
        self.assertIn('Request a change', html)

    # ======================================================== FS-13 fixes
    def _draft(self, spec, updates=None):
        self.S().save_draft(PAGE, {'spec': spec, 'companies': {}, 'updates': updates or {},
                                   'changes': ['DEMO change'], 'base_version': 0})

    def test_21_preview_shows_a_new_field_of_the_draft(self):
        """FS-13 item 1: the draft as Publish would make it — a field newly
        placed (not ticked yet) is drawn with the person's value or the empty
        state, with the draft's label; nothing is written; no employee sees it."""
        self.publish(self.spec([{'name': 'work_email', 'width': 'half'}]))
        self.assertFalse(self.meta(self.shirt).portal_show)
        self.assertFalse(self.meta('mobile_phone').portal_show)
        self._draft(self.spec([{'name': self.shirt, 'width': 'half'},
                               {'name': 'mobile_phone', 'width': 'half'}]),
                    updates={'mobile_phone': {'std_labels': {'en_US': 'DEMO Work cell'}}})
        audits = self.env['pb.form.audit'].sudo().search_count([])
        url = '/my/profile/preview?employee_id=%s&source=draft' % self.emp.id
        html = self.html(url, login='fs12_admin')
        self.assertIn('DEMO Shirt size', html, 'the newly placed field is drawn')
        self.assertIn('DEMO Work cell', html, "with the draft's own label")
        main = html[html.index('pbfp-person'):html.index('pbme-detail-side')]
        self.assertNotIn('lan.demo@example.com', main, 'a field taken off in the draft is left out')
        self.assertIn('<b>—</b>', main, 'an empty value shows the empty state')
        # look-only, nothing written
        self.assertFalse(self.meta(self.shirt).portal_show, 'the tick changes only at Publish')
        self.assertFalse(self.meta('mobile_phone').portal_show)
        self.assertFalse(self.meta('mobile_phone').std_labels)
        self.assertEqual(self.env['pb.form.audit'].sudo().search_count([]), audits)
        # the real employee still gets the published page only
        mine = self.html()
        self.assertNotIn('DEMO Shirt size', mine)
        self.assertNotIn('DEMO Work cell', mine)
        self.assertIn('lan.demo@example.com', mine)
        # the same through the model, and the call is the administrator's only
        page = self.S().portal_page_render(self.emp.sudo(), spec=self.spec(
            [{'name': self.shirt, 'width': 'half'}, {'name': self.pan, 'width': 'half'}]), preview={})
        self.assertEqual([f['name'] for f in page['sections'][0]['fields']], [self.shirt],
                         'Country of Work honoured: the India-only field is not drawn for Vietnam')
        with self.assertRaises(AccessError):
            self.S(self.hr).portal_page_render(self.emp.sudo(), spec=self.spec([]), preview={})

    def test_22_preview_of_the_standard_page_before_any_publish(self):
        """No page yet: the preview shows today's seven fields (none ticked)."""
        url = '/my/profile/preview?employee_id=%s&source=live' % self.emp.id
        html = self.html(url, login='fs12_admin')
        self.assertIn('lan.demo@example.com', html)
        self.assertIn('+84 1', html)
        self.assertFalse(self.env['pb.form.layout'].sudo().search([('host_key', '=', PAGE)]))

    def test_23_preview_photo(self):
        """FS-13 item 2: the preview's photo comes from its own route, which
        answers the administrator (no employee record of their own) only."""
        url = '/my/profile/preview?employee_id=%s&source=live' % self.emp.id
        html = self.html(url, login='fs12_admin')
        src = '/my/profile/preview/photo/%s' % self.emp.id
        self.assertIn('src="%s"' % src, html)
        img = self.url_open(src)
        self.assertEqual(img.status_code, 200)
        self.assertTrue(img.headers.get('Content-Type', '').startswith('image/'))
        for login in ('fs12_me', 'fs12_hr'):
            self.authenticate(login, PASSWORD)
            self.assertEqual(self.url_open(src).status_code, 404, login)
        # the employee's own page keeps its own photo route
        self.assertIn('/my/photo/%s/avatar_256' % self.emp.id, self.html())

    def test_24_page_for_offers_active_companies_only(self):
        """FS-13 item 5: archived companies are not offered; a page made for
        a company archived later is kept as it is by the next Publish."""
        Company = self.env['res.company'].sudo()
        c2 = Company.create({'name': 'DEMO FS13 Branch'})
        c3 = Company.create({'name': 'DEMO FS13 Closed'})
        self.admin.sudo().write({'company_ids': [(4, c2.id), (4, c3.id)]})
        names = [c['name'] for c in self.S().page_studio()['companies']]
        self.assertIn('DEMO FS13 Closed', names)
        own = self.spec([{'name': self.shirt, 'width': 'half'}])
        own['header']['title'] = {'en_US': 'DEMO Closed page'}
        self.publish(self.spec([{'name': 'work_email', 'width': 'half'}]), companies={str(c3.id): own})
        c3.active = False
        names = [c['name'] for c in self.S().page_studio()['companies']]
        self.assertNotIn('DEMO FS13 Closed', names)
        self.assertIn('DEMO FS13 Branch', names)
        # switched off in the company switcher: not offered either
        names = [c['name'] for c in self.S().with_context(
            allowed_company_ids=[self.company.id, c2.id]).page_studio()['companies']]
        self.assertEqual(sorted(names), sorted([self.company.name, 'DEMO FS13 Branch']))
        # the next Publish (which cannot send that company's page) keeps it
        self.publish(self.spec([{'name': 'work_email', 'width': 'half'}]))
        kept = self.S()._pbfp_published()['companies'].get(str(c3.id))
        self.assertTrue(kept)
        self.assertEqual(kept['header']['title'], {'en_US': 'DEMO Closed page'})
        self.assertTrue(self.meta(self.shirt).portal_show, 'its field stays shown')

    def test_25_administrator_without_employee_record(self):
        """FS-13 item 6: /my/profile → a short note with the way in; the
        builder's preview list offers employees with no login too."""
        html = self.html('/my/profile', login='fs12_admin')
        self.assertIn('Your login has no employee record', html)
        self.assertIn('action-pb_form_studio_portal.action_page_builder', html)
        self.assertNotIn('Odoo', html.replace('odoo', ''))
        # everybody else as before: an employee gets the page, nobody gets /my
        self.assertNotIn('Your login has no employee record', self.html())
        self.authenticate('fs12_nobody', PASSWORD)
        res = self.url_open('/my/profile', allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        # preview as anybody the administrator may see, logins first
        loose = self.env[EMP].sudo().create({'name': 'DEMO FS13 No login',
                                             'company_id': self.company.id})
        emps = self.S().page_employees('DEMO FS1')
        ids = [e['id'] for e in emps]
        self.assertIn(loose.id, ids)
        self.assertIn(self.emp.id, ids)
        self.assertLess(ids.index(self.emp.id), ids.index(loose.id), 'logins first')
        self.assertFalse(next(e for e in emps if e['id'] == loose.id)['login'])
        url = '/my/profile/preview?employee_id=%s&source=live' % loose.id
        self.assertIn('DEMO FS13 No login', self.html(url, login='fs12_admin'))
