# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""MEHOME M1 — the employee home's facts, tile registry and page.

Numbered after the handover (docs/handovers/mehome/M1_HANDOVER.md §Numbered
tests). Every fixture is seeded here: the bench clone holds a little payroll
and no workforce rows, and the tests assert on what they seed.
"""
import base64
import re
from datetime import date, datetime, timedelta
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged

from odoo.addons.pb_me_portal.models import pb_me_home

_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAEElEQVR4nGP4z8AA'
    'RAwQCgAf7gP9i18U1AAAAABJRU5ErkJggg==')


def _make_user(env, login, name, password=None):
    vals = {'name': name, 'login': login,
            'group_ids': [(6, 0, [env.ref('base.group_user').id])]}
    if password:
        vals['password'] = password
    return env['res.users'].with_context(no_reset_password=True).create(vals)


@tagged('post_install', '-at_install')
class TestMeHome(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Home = cls.env['pb.me.home']
        cls.company = cls.env.company
        cls.user = _make_user(cls.env, 'test_pbme_home', 'Home Person')
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Mitchell Admin', 'user_id': cls.user.id,
            'company_id': cls.company.id})

    def _home(self, user=None, emp=None):
        user = user or self.user
        return self.Home.with_user(user).get_home_data(emp or self.employee)

    # ------------------------------------------------------------ test 2
    def test_02_tile_meta_default_and_hidden(self):
        meta = self.Home.tile_meta('/my/unknown?x=1')
        self.assertEqual((meta['group'], meta['icon'], meta['tone']),
                         ('more', 'file', 'slate'))
        self.assertTrue(self.Home.tile_meta('/my/payslips').get('hidden'))
        self.assertTrue(self.Home.tile_meta('/my/pay').get('hidden'))
        self.assertTrue(self.Home.tile_meta('/my/work/leave').get('hidden'))
        # the path before `?` is what matches
        self.assertEqual(self.Home.tile_meta('/my/invoices?filterby=bills')['group'], 'more')
        self.assertEqual(self.Home.tile_meta('/my/documents')['group'], 'me')
        self.assertEqual(self.Home.tile_meta('/my/security')['title'],
                         'Sign-in & security')
        # registry order: Profile, Documents, Tax Sheet, My Things, Pay Package
        me = sorted((m['seq'], url) for url, m in pb_me_home.TILES.items()
                    if m['group'] == 'me' and not m.get('hidden'))
        self.assertEqual([u for _s, u in me],
                         ['/my/profile', '/my/documents', '/my/taxsheet',
                          '/my/assets', '/my/compensation'])

    # ------------------------------------------------------------ test 3
    def _render_tile(self, url, title, text='Some text'):
        return self.env['ir.qweb']._render('portal.portal_docs_entry', {
            'pbme_home': {'person': {'name': 'x'}},
            'url': url, 'title': title, 'text': text, 'config_card': True,
        })

    def test_03_tile_override_badge_group_title(self):
        out = str(self._render_tile('/my/documents', 'Documents'))
        doc = lxml_html.fromstring('<div>%s</div>' % out)
        card = doc.xpath('//div[contains(@class, "o_portal_index_card")]')
        self.assertEqual(len(card), 1)
        self.assertEqual(card[0].get('data-pbme-group'), 'me')
        badges = doc.xpath('//div[contains(@class, "pbme-badge--amber")]')
        self.assertEqual(len(badges), 1)
        self.assertEqual(len(badges[0].xpath('.//*[local-name()="svg" and '
                                             'contains(@class, "pbme-ic")]')), 1)
        self.assertEqual(len(doc.xpath('//img')), 0, "no stock picture")
        self.assertEqual(len(doc.xpath('//*[local-name()="svg"]')), 1)
        sec = str(self._render_tile('/my/security', 'Connection & Security'))
        self.assertIn('Sign-in &amp; security', sec)
        self.assertNotIn('Connection &amp; Security', sec)
        # off the employee home nothing of ours renders
        stock = str(self.env['ir.qweb']._render('portal.portal_docs_entry', {
            'url': '/my/documents', 'title': 'Documents', 'text': 't',
            'config_card': True, 'icon': '/portal/static/src/img/portal-addresses.svg'}))
        self.assertNotIn('pbme-badge', stock)
        self.assertNotIn('data-pbme-group', stock)
        self.assertIn('<img', stock)

    def test_03b_hidden_tile_is_rendered_and_marked(self):
        out = str(self._render_tile('/my/payslips', 'Payslips'))
        self.assertIn('data-pbme-hidden="1"', out)

    # ------------------------------------------------------------ test 4
    def test_04_no_employee_is_none(self):
        lone = _make_user(self.env, 'test_pbme_lone', 'Lone User')
        Home = self.Home.with_user(lone)
        self.assertIsNone(Home.get_home_data(self.env['hr.employee']))
        self.assertIsNone(Home.get_home_data(False))
        # somebody else's employee is refused (own data only, M-R4)
        self.assertIsNone(Home.get_home_data(self.employee))

    # ------------------------------------------------------------ test 5
    def test_05_optional(self):
        self.assertIsNone(self.Home.optional('pb.no.such.model', lambda M: 1))
        self.assertIsNone(self.Home.optional(
            'hr.employee', lambda M: 1, fields=('no_such_field_xyz',)))
        self.assertEqual(self.Home.optional('hr.employee', lambda M: 7), 7)

        def denied(Model):
            raise AccessError('no')
        with patch.object(pb_me_home._logger, 'debug',
                          wraps=pb_me_home._logger.debug) as dbg, \
                patch.object(pb_me_home._logger, 'warning',
                             wraps=pb_me_home._logger.warning) as warn:
            self.assertIsNone(self.Home.optional('hr.employee', denied))
            self.assertEqual(dbg.call_count, 1)
            self.assertEqual(warn.call_count, 0)

        def broken(Model):
            raise ValueError('bug')
        with patch.object(pb_me_home._logger, 'warning',
                          wraps=pb_me_home._logger.warning) as warn:
            self.assertIsNone(self.Home.optional('hr.employee', broken))
            self.assertEqual(warn.call_count, 1)
        # a failed statement does not poison the transaction
        self.assertIsNone(self.Home.optional(
            'hr.employee',
            lambda M: self.env.cr.execute('SELECT * FROM no_such_table_pbme')))
        self.assertTrue(self.env['hr.employee'].search_count([]))

    # ------------------------------------------------------------ test 6
    def _slip(self, emp, date_to, net, state='done'):
        rule = self.env['hr.salary.rule'].search([], limit=1)
        if not rule:
            self.skipTest('no salary rule on this database to hang lines off')
        contract = self.env['hr.contract'].search(
            [('employee_id', '=', emp.id)], limit=1) or \
            self.env['hr.contract'].create({
                'name': 'pbme contract', 'employee_id': emp.id, 'wage': 1000.0,
                'state': 'open', 'date_start': '2020-01-01',
                'company_id': emp.company_id.id})
        start = date_to.replace(day=1)
        slip = self.env['hr.payslip'].sudo().create({
            'employee_id': emp.id, 'name': 'pbme slip %s' % date_to,
            'contract_id': contract.id, 'date_from': start, 'date_to': date_to,
            'company_id': emp.company_id.id})
        vals = {'slip_id': slip.id, 'name': 'Net', 'code': 'NET',
                'amount': net, 'quantity': 1.0, 'rate': 100.0,
                'employee_id': emp.id, 'contract_id': contract.id,
                'salary_rule_id': rule.id}
        Line = self.env['hr.payslip.line'].sudo()
        if 'pay_role' in Line._fields:
            vals['pay_role'] = 'net'
        cat = self.env['hr.salary.rule.category'].search([('code', '=', 'NET')], limit=1)
        if cat:
            vals['category_id'] = cat.id
        Line.create(vals)
        self.env.flush_all()
        self.env.cr.execute('UPDATE hr_payslip SET state = %s WHERE id = %s',
                            (state, slip.id))
        self.env.invalidate_all()
        return slip

    def test_06_pay(self):
        self.assertEqual(self._home()['pay']['count'], 0)
        old = self._slip(self.employee, date(2031, 1, 31), 1000.0)
        new = self._slip(self.employee, date(2031, 2, 28), 1250.0)
        self._slip(self.employee, date(2031, 3, 31), 9999.0, state='cancel')
        pay = self._home()['pay']
        self.assertEqual(pay['count'], 2)
        self.assertEqual(pay['last']['id'], new.id)
        self.assertEqual(pay['last']['net'], 1250.0)
        self.assertEqual(pay['previous_net'], 1000.0)
        self.assertEqual([p['net'] for p in pay['trend']], [1000.0, 1250.0])
        self.assertEqual([p['month_date'] for p in pay['trend']],
                         [old.date_to, new.date_to])
        self.assertIn('report_type=pdf', pay['last']['pdf_url'])
        self.assertIn('download=true', pay['last']['pdf_url'])
        self.assertTrue(pay['last']['view_url'].startswith('/my/payslips/%s' % new.id))
        self.assertEqual(pay['explain_url'],
                         '/my/pay' if 'pb.pay.apply' in self.env else None)

    # ------------------------------------------------------------ test 7
    def test_07_next_pay_date(self):
        if 'pb.payroll.calendar' not in self.env:
            self.skipTest('no pay calendar on this database (pb_comp_ben absent)')
        Cal = self.env['pb.payroll.calendar'].sudo()
        # a company of its own, so the clone's own calendar rows cannot answer
        co = self.env['res.company'].create({'name': 'PBME Calendar Co'})
        user = _make_user(self.env, 'test_pbme_cal', 'Cal Person')
        user.write({'company_ids': [(4, co.id)], 'company_id': co.id})
        emp = self.env['hr.employee'].create({
            'name': 'Cal Person', 'user_id': user.id, 'company_id': co.id})
        # shared rows that would otherwise answer are closed for this test
        Cal.search([('company_id', '=', False)]).write({'state': 'closed'})
        today = fields.Date.context_today(self.Home.with_user(user))
        tomorrow = today + timedelta(days=1)
        Home = self.Home.with_user(user)

        closed = Cal.create({'month': date(2041, 1, 1), 'cutoff_date': tomorrow,
                             'pay_date': tomorrow, 'company_id': co.id,
                             'state': 'closed'})
        self.assertIsNone(Home._pbme_next_pay_date(emp, today), "closed only → None")
        shared = Cal.create({'month': date(2041, 2, 1), 'cutoff_date': today,
                             'pay_date': today, 'company_id': False,
                             'state': 'upcoming'})
        self.assertEqual(Home._pbme_next_pay_date(emp, today), today,
                         "no company row → the shared row")
        Cal.create({'month': date(2041, 3, 1), 'cutoff_date': tomorrow,
                    'pay_date': tomorrow, 'company_id': co.id,
                    'state': 'upcoming'})
        self.assertEqual(Home._pbme_next_pay_date(emp, today), tomorrow,
                         "the company's row beats an earlier shared one")
        pay = Home.get_home_data(emp)['pay']
        self.assertEqual(pay['next_pay_date'], tomorrow)
        self.assertEqual(pay['next_pay_days'], 1)
        self.assertTrue(closed and shared)

    # ------------------------------------------------------------ test 8
    def _doc(self, days, name):
        cat = self.env.ref('pb_employee_vault.cat_other')
        att = self.env['ir.attachment'].sudo().create({
            'name': '%s.png' % name, 'datas': base64.b64encode(_PNG),
            'mimetype': 'image/png'})
        return self.env['pb.employee.document'].sudo().create({
            'employee_id': self.employee.id, 'category_id': cat.id,
            'name': name, 'attachment_id': att.id,
            'expiry_date': fields.Date.context_today(self.Home) + timedelta(days=days)})

    def test_08_needs_you(self):
        self._doc(-3, 'expired permit')
        self._doc(10, 'expiring permit')
        self._doc(120, 'far permit')
        req = self.env['pb.profile.change.request'].with_user(self.user).create({
            'employee_id': self.employee.id, 'x_phone': '0999'})
        req.with_user(self.user).action_submit()
        self.assertEqual(req.state, 'hr_review')
        data = self._home()
        needs = data['needs_you']
        keys = [i['key'] for i in needs]
        mine = [k for k in keys if k in ('doc_expired', 'doc_expiring', 'profile_waiting')]
        self.assertEqual(mine, ['doc_expired', 'doc_expiring', 'profile_waiting'])
        # every key is in the fixed order, and nothing at zero is emitted
        order = list(pb_me_home.NEEDS_ORDER)
        self.assertEqual(keys, sorted(keys, key=order.index))
        self.assertTrue(all(i['n'] > 0 for i in needs))
        by_key = {i['key']: i for i in needs}
        self.assertEqual(by_key['doc_expiring']['days'], 10)
        self.assertEqual(by_key['doc_expiring']['n'], 1, "120 days out is not listed")
        self.assertEqual(by_key['doc_expired']['n'], 1)
        self.assertEqual(by_key['doc_expired']['url'], '/my/documents')
        self.assertEqual(by_key['profile_waiting']['url'], '/my/profile')
        self.assertEqual(data['docs'], {'expired': 1, 'expiring': 1, 'soonest_days': 10})

    # ------------------------------------------------------------ test 9
    def test_09_short_name_and_daypart(self):
        Home = self.Home
        self.assertEqual(Home._pbme_short_name('Nguyễn Văn An', True), 'An')
        self.assertEqual(Home._pbme_short_name('Mitchell Admin', False), 'Mitchell')
        self.assertEqual(Home._pbme_short_name('', False), '')
        # the rule that picks the order: the user's language, or a VN company
        co = self.env['res.company'].create({
            'name': 'PBME AU Co', 'country_id': self.env.ref('base.au').id})
        en = _make_user(self.env, 'test_pbme_en', 'Mitchell Admin')
        en.write({'lang': 'en_US', 'company_ids': [(4, co.id)], 'company_id': co.id})
        emp_en = self.env['hr.employee'].create({
            'name': 'Mitchell Admin', 'user_id': en.id, 'company_id': co.id})
        self.assertEqual(Home.with_user(en).get_home_data(emp_en)['person']['short_name'],
                         'Mitchell')
        if not self.env['res.lang']._lang_get('vi_VN'):
            self.env['res.lang']._activate_lang('vi_VN')
        vi = _make_user(self.env, 'test_pbme_vi', 'Nguyễn Văn An')
        vi.write({'lang': 'vi_VN', 'company_ids': [(4, co.id)], 'company_id': co.id})
        emp_vi = self.env['hr.employee'].create({
            'name': 'Nguyễn Văn An', 'user_id': vi.id, 'company_id': co.id})
        self.assertEqual(Home.with_user(vi).get_home_data(emp_vi)['person']['short_name'],
                         'An')
        # daypart on the person's own wall clock, frozen `now`
        en.write({'tz': 'Asia/Ho_Chi_Minh'})          # UTC+7
        H = Home.with_user(en)

        def part(local_h, local_m):
            utc = datetime(2031, 5, 5, local_h, local_m) - timedelta(hours=7)
            return H.get_home_data(emp_en, now=utc)['person']['daypart']
        self.assertEqual(part(11, 59), 'morning')
        self.assertEqual(part(12, 0), 'afternoon')
        self.assertEqual(part(18, 0), 'evening')
        # no user tz → the company's partner tz → UTC
        en.write({'tz': False})
        co.partner_id.write({'tz': 'Asia/Ho_Chi_Minh'})
        self.assertEqual(H._pbme_tz_name(emp_en), 'Asia/Ho_Chi_Minh')
        co.partner_id.write({'tz': False})
        self.assertEqual(H._pbme_tz_name(emp_en), 'UTC')

    # ---------------------------------------------- payload shape (facts only)
    def test_payload_shape(self):
        data = self._home()
        self.assertEqual(set(data), {'person', 'pay', 'leave', 'week',
                                     'needs_you', 'docs', 'tiles'})
        self.assertEqual(set(data['person']), {
            'name', 'short_name', 'daypart', 'job', 'company', 'avatar_url', 'date'})
        self.assertIn(data['person']['daypart'], ('morning', 'afternoon', 'evening'))
        if 'pb.ess.workforce' in self.env:
            self.assertEqual(len(data['week']['days']), 7)
            self.assertEqual(data['week']['url'], '/my/work/schedule')
            self.assertEqual(data['leave']['url'], '/my/work/leave')
            self.assertTrue(all(d['state'] in ('acked', 'pending', 'off', 'leave')
                                for d in data['week']['days']))
        urls = {t['url'] for t in data['tiles']}
        self.assertEqual(urls, set(pb_me_home.TILES))
        # no sentence in the payload: every string value is a name, a URL, a key
        for t in data['tiles']:
            self.assertIn(t['group'], pb_me_home.GROUPS)


@tagged('post_install', '-at_install')
class TestMeHomePage(HttpCase):
    """Tests 4 and 10 — the page itself, over HTTP, as the person."""

    PASSWORD = 'pbme-home-check-2026'

    def _user(self, login, name, employee=True):
        user = _make_user(self.env, login, name, password=self.PASSWORD)
        if employee:
            self.env['hr.employee'].create({
                'name': name, 'user_id': user.id,
                'company_id': self.env.company.id})
        return user

    def _get_home(self, login):
        self.authenticate(login, self.PASSWORD)
        res = self.url_open('/my')
        self.assertEqual(res.status_code, 200)
        return res.text

    def test_04_page_without_employee_is_stock(self):
        self._user('test_pbme_stock', 'Stock Person', employee=False)
        page = self._get_home('test_pbme_stock')
        self.assertIn('o_portal_my_home', page)
        self.assertNotIn('pbme-home', page)
        self.assertNotIn('data-pbme-section', page)
        self.assertIn('accountOffCanvas', page, "the stock contact column stays")
        self.assertRegex(page, r'<h3[^>]*>\s*My account')

    def test_10_page_for_an_employee(self):
        self._user('test_pbme_emp', 'Linh Tran')
        page = self._get_home('test_pbme_emp')
        self.assertIn('pbme-home', page)
        self.assertIn('class="pbme-greet"', page)
        self.assertIn('data-pbme-slot="needs"', page)
        for group in ('me', 'time', 'growth', 'people', 'more'):
            self.assertIn('data-pbme-section="%s"' % group, page)
        self.assertNotRegex(page, r'<h3[^>]*>\s*My account')
        self.assertNotIn('accountOffCanvas', page, "no contact column")
        self.assertNotIn('o_portal_content col-12 col-lg-8', page)
        # every tile carries a badge, none the stock picture
        doc = lxml_html.fromstring(page)
        cards = doc.xpath('//div[contains(@class, "o_portal_index_card")]')
        self.assertTrue(cards)
        for card in cards:
            self.assertTrue(card.get('data-pbme-group'), lxml_html.tostring(card)[:200])
            self.assertFalse(card.xpath('.//img'))
        self.assertTrue(re.search(r'Nothing needs you right now|need', page))
