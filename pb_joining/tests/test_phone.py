from datetime import timedelta
from unittest.mock import patch

from lxml import html

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.addons.pb_hiring.tests.test_joining_p6 import JoiningCase
from odoo.addons.pb_new_hire.models.studio_docs import FILE_MAX

TAG = ('post_install', '-at_install', 'joining')


def person(env, country='VN'):
    return env['pb.joining'].sudo().create({
        'name': 'DEMO Joiner Example', 'company_id': env.company.id, 'job_title': 'Test role',
        'payroll_country': country, 'email': 'demojoin@example.invalid', 'lang': 'en_US',
        'first_day': fields.Date.today() + timedelta(days=5)})


@tagged(*TAG)
class TestOffer(JoiningCase):
    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('pb_joining.auto_invite', '1')
        self.req.country_id = self.env.ref('base.vn')

    def test_t01_offer_signed(self):
        offer = self._signed()
        j = self.env['pb.joining'].search([('offer_id', '=', offer.id)])
        self.assertEqual(len(j), 1)
        self.assertEqual((j.name, j.first_day, j.job_title, j.payroll_country),
                         (offer.applicant_id.partner_name, offer.expected_join_date, offer.job_title, 'VN'))

    def test_t02_replay(self):
        offer = self._signed()
        offer._on_signed()
        self.assertEqual(self.env['pb.joining'].search_count([('offer_id', '=', offer.id)]), 1)

    def test_t02_quiet(self):
        other = self._offer()
        other._on_signed(quiet=True)
        self.assertFalse(self.env['pb.joining'].search_count([('offer_id', '=', other.id)]))

    def test_t03_internal(self):
        if 'pb_internal' in self.applicant._fields:
            self.applicant.pb_internal = True
            offer = self._signed()
        else:
            # The optional staff-moves module supplies this flag on installations that use it.
            with patch.object(type(self.applicant), 'pb_internal', True, create=True):
                offer = self._signed()
        self.assertFalse(self.env['pb.joining'].search([('offer_id', '=', offer.id)]))

    def test_t04_switch(self):
        self.env['ir.config_parameter'].sudo().set_param('pb_joining.auto_invite', '0')
        self.assertFalse(self.env['pb.joining'].search([('offer_id', '=', self._signed().id)]))


@tagged(*TAG)
class TestPhone(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.j = person(cls.env)
        cls.j.email = 'demojoin@example.invalid'
        cls.path = '/join/' + cls.j.token

    def _submit(self, path, values=None):
        doc = html.fromstring(self.url_open(self.path).content)
        csrf = doc.xpath('//input[@name="csrf_token"]/@value')[0]
        return self.url_open(self.path + path, data=dict(values or {}, csrf_token=csrf), allow_redirects=False)

    def _confirm(self):
        code = self.j._issue(by_hr=True)['code']
        response = self._submit('/code', {'code': code})
        self.assertEqual(response.status_code, 303)
        self.assertIn('Opened with your code', self.url_open(self.path).text)

    def test_t05_inactive(self):
        invalid = ['/join/short', '/join/' + 'x' * 32]
        for state in ('cancelled', 'past'):
            j = person(self.env)
            if state == 'cancelled':
                j.write({'state': 'cancelled', 'cancelled_at': fields.Datetime.now()-timedelta(days=31)})
            else:
                j.first_day = fields.Date.today()-timedelta(days=15)
            invalid.append('/join/' + j.token)
        for path in invalid:
            r = self.url_open(path)
            self.assertEqual(r.status_code, 200)
            self.assertIn('This link is not active', r.text)
            self.assertNotIn(self.j.email, r.text)

    def test_t06_before_code(self):
        self.j._issue(by_hr=True)
        r = self.url_open(self.path)
        self.assertIn('Enter your code', r.text)
        for private in (self.j.name, self.j.email, self.j.job_title):
            self.assertNotIn(private, r.text)
        self.assertEqual(r.headers['Cache-Control'], 'no-store')
        self.assertEqual(r.headers['Referrer-Policy'], 'no-referrer')
        self.assertEqual(r.headers['X-Robots-Tag'], 'noindex')

    def test_t07_code(self):
        self._confirm()
        self.j.invalidate_recordset()
        self.assertTrue(self.j.opened_at)
        self.assertFalse(self.j.code_hash)

    def test_t12_must_confirm(self):
        r = self.url_open(self.path+'/s/personal', allow_redirects=False)
        self.assertEqual(r.status_code, 303)
        self.assertEqual(self._submit('/start').status_code, 303)
        self.assertFalse(self.j.welcome_started)

    def test_t13_csrf(self):
        r = self.url_open(self.path + '/start', data={'csrf_token': ''}, allow_redirects=False)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.headers['Cache-Control'], 'no-store')

    def test_t14_each_person_needs_their_own_code(self):
        self._confirm()
        other = person(self.env)
        self.assertEqual(self.url_open('/join/' + other.token + '/s/day', allow_redirects=False).status_code, 303)

    def test_t18_saved_number_is_masked(self):
        self._confirm()
        row = self.j.item_ids.filtered(lambda r: r.key == 'id_number')
        row.values = {'identification_id': 'DEMO-PRIVATE-1234'}
        r = self.url_open(self.path+'/s/id_number')
        self.assertNotIn('DEMO-PRIVATE-1234', r.text)
        self.assertIn('•••• 1234', r.text)
        self.assertTrue(html.fromstring(r.content).xpath('//form//button[normalize-space(.)="Save and continue"]'))


@tagged(*TAG)
class TestSections(TransactionCase):
    def setUp(self):
        super().setUp()
        self.j = person(self.env)

    def _item(self, key, j=None):
        j = j or self.j
        return j.item_ids.filtered(lambda r: r.key == key), next(i for i in j._catalogue() if i['key'] == key)

    def test_t08_lock(self):
        code = self.j._issue(by_hr=True)['code']
        wrong = str((int(code)+1) % 10**6).zfill(6)
        self.assertEqual([self.j._verify(wrong) for _i in range(5)], ['wrong']*4+['locked'])
        self.assertEqual(self.j._verify(code), 'locked')
        self.assertEqual(self.j._issue(by_hr=True)['status'], 'locked')
        self.assertGreater(self.j.code_locked_until, fields.Datetime.now()+timedelta(minutes=14))
        self.j.code_locked_until = fields.Datetime.now()-timedelta(seconds=1)
        self.assertEqual(self.j._verify(self.j._issue(by_hr=True)['code']), 'ok')

    def test_t09_expired(self):
        code = self.j._issue(by_hr=True)['code']
        self.j.code_until = fields.Datetime.now()-timedelta(seconds=1)
        self.assertEqual(self.j._verify(code), 'expired')

    def test_t10_rolling_limits(self):
        now = fields.Datetime.now()
        with patch.object(type(self.j), '_mail', return_value=True), patch.object(type(self.j), '_can_email', return_value=True):
            for i in range(5):
                with patch.object(fields.Datetime, 'now', return_value=now+timedelta(minutes=i)):
                    self.assertEqual(self.j._issue()['status'], 'issued')
                    self.assertEqual(self.j._issue()['status'], 'wait')
                    self.assertEqual(self.j._issue(automatic=True)['status'], 'live')
            with patch.object(fields.Datetime, 'now', return_value=now+timedelta(minutes=59)):
                self.assertEqual(self.j._issue()['status'], 'wait')
            with patch.object(fields.Datetime, 'now', return_value=now+timedelta(minutes=60)):
                self.assertEqual(self.j._issue()['status'], 'issued')

    def test_t11_hr_code(self):
        with patch.object(type(self.j), '_mail', return_value=True), patch.object(type(self.j), '_can_email', return_value=True):
            self.j._issue()
        old = self.j.code_hash
        code = self.j._issue(by_hr=True)['code']
        self.assertNotEqual(old, self.j.code_hash)
        self.assertGreater(self.j.code_until, fields.Datetime.now()+timedelta(hours=47))
        self.assertTrue(self.j.code_by_hr)
        self.assertNotIn(code, ' '.join(str(m.body) for m in self.j.message_ids))
        self.assertEqual(self.j._verify(code), 'ok')
        self.assertEqual(self.j._verify(code), 'expired')

    def test_t15_catalogue_round_trip(self):
        tax = {'VN': '0123456789', 'ID': '012345678901234', 'IN': 'ABCDE1234F'}
        for country in ('VN', 'ID', 'IN', 'SG'):
            j = person(self.env, country)
            studio = self.env['pb.new.hire'].sudo().with_company(j.company_id)
            source = studio._detail_items(country, j._first())
            self.assertEqual([s['fields'] for s in j._catalogue()], [s['fields'] for s in source])
            for spec in source:
                key = spec['key']
                row = j.item_ids.filtered(lambda r: r.key == key)
                values = {}
                for box in spec['fields']:
                    if box['options'] and box['kind'] in ('select', 'bank'):
                        values[box['name']] = box['options'][0]['value']
                    elif box['kind'] == 'date':
                        values[box['name']] = '2000-01-02'
                    else:
                        values[box['name']] = '2025550119'
                if key == 'tax_number':
                    values[spec['fields'][0]['name']] = tax[country]
                if key == 'bank':
                    values.update(bank_format=country, bank_name='DEMO Bank', account_number='12345678901',
                                  account_holder=j.name, bank_code={'IN':'ABCD0123456','SG':'1234','ID':'123'}.get(country,''))
                    if country == 'IN':
                        values['branch_code'] = 'ABCD0123456'
                    else:
                        values.pop('branch_code', None)
                files = []
                if spec['upload']:
                    row._upload(spec, 'demo.pdf', b'%PDF-1.4\n1 0 obj\n<< >>\nendobj\n%%EOF')
                    values['expiry_date'] = '2035-01-01'
                    files.append({'key': key, 'name': 'demo.pdf', 'data': 'JVBERi0xLjQ=', 'mime': 'application/pdf', 'expiry_date': '2035-01-01'})
                row._save(spec, values)
                self.assertEqual(row.state, 'saved')
                refused = studio._validate_docs({'name': j.name, 'payroll_country': country,
                    'have': row.values, 'items': {key:'have'}}, files)
                self.assertFalse(refused, (country, key, refused))

    def test_t16_invalid(self):
        for key, values in [('tax_number', {'vietnam_tax_code': 'bad'}), ('bank', {'bank_name':'DEMO Bank','account_number':'x'})]:
            row, spec = self._item(key)
            with self.assertRaises(UserError):
                row._save(spec, values)
            self.assertFalse(row.values)
            self.assertEqual(row.state, 'empty')

    def test_t17_outside_tax_catalogue(self):
        j = person(self.env, 'MY')
        self.assertNotIn('tax', j._section_states())
        self.assertEqual(self._item('bank', j)[1]['bank']['default'], 'MY')

    def test_t19_bank_later(self):
        row, spec = self._item('bank')
        row._save(spec, {}, later=True)
        self.assertEqual(row.state, 'later')
        self.assertTrue(self.j.bank_later)

    def test_t20_upload(self):
        row, spec = self._item('id_number')
        for raw in (b'hello world', b'%PDF-1.4' + b'x' * FILE_MAX):
            with self.assertRaises(UserError):
                row._upload(spec, 'demo.pdf', raw)
        old = row._upload(spec, 'a.pdf', b'%PDF-1.4\n%%EOF')
        new = row._upload(spec, 'b.pdf', b'%PDF-1.4\n%%EOF', old.id)
        self.assertFalse(old.exists())
        self.assertEqual(row.attachment_ids, new)
        self.assertFalse(new.public or new.access_token)

    def test_t21_hiring_file(self):
        studio = self.env['pb.new.hire']
        with patch.object(type(studio), '_received_for', return_value={'identity':{'on': '2026-01-01','label':'DEMO ID'}}):
            j = person(self.env)
            row, spec = self._item('id_number', j)
            self.assertTrue(row.from_hiring)
            self.assertFalse(spec['upload'])
            row._save(spec, {'identification_id': '123456789012', 'no_expiry': True})

    def test_t22_send(self):
        with self.assertRaises(UserError):
            self.j._send_to_hr()
        self.j.item_ids.write({'state': 'saved'})
        bank, spec = self._item('bank')
        bank._save(spec, {}, later=True)
        self.j.day_opened = True
        self.j._send_to_hr()
        self.assertEqual(self.j.state, 'to_check')
        self.assertTrue(bank._editable())
        self.assertFalse((self.j.item_ids-bank).filtered(lambda r: r._editable()))

    def test_session_timeout_and_short_values(self):
        from ..models.items import masked
        session = {}
        self.j._remember(session)
        self.assertTrue(self.j._remembered(session))
        session['pbj'][str(self.j.id)] = 1
        self.assertFalse(self.j._remembered(session))
        self.assertNotIn('123', masked('123'))

    def test_mail_off_and_delivery_failure_issue_nothing(self):
        with patch.object(type(self.j), '_can_email', return_value=False):
            self.assertEqual(self.j._issue()['status'], 'pass_on')
        with patch.object(type(self.j), '_can_email', return_value=True), patch.object(type(self.j), '_mail', return_value=False):
            self.assertEqual(self.j._issue()['status'], 'pass_on')
        self.assertFalse(self.j.code_hash)

    def test_rate_windows(self):
        from ..controllers.joining import limited
        from unittest.mock import patch
        key = ('test', self.j.id)
        with patch('odoo.addons.pb_joining.controllers.joining.monotonic', return_value=100):
            self.assertFalse(limited(key, 2, 10, False))
            self.assertFalse(limited(key, 2, 10))
            self.assertFalse(limited(key, 2, 10))
            self.assertTrue(limited(key, 2, 10))
        with patch('odoo.addons.pb_joining.controllers.joining.monotonic', return_value=110):
            self.assertFalse(limited(key, 2, 10))

    def test_limits_on_files_and_closed_state(self):
        row, spec = self._item('id_number')
        for i in range(12):
            row._upload(spec, 'demo-%d.pdf' % i, b'%PDF-1.4\n%%EOF')
        with self.assertRaises(UserError):
            row._upload(spec, 'another.pdf', b'%PDF-1.4\n%%EOF')
        self.j._cancel('DEMO cancelled')
        self.assertEqual(self.j._for_token(self.j.token)[1], 'closed')
        with self.assertRaises(UserError):
            row._upload(spec, 'closed.pdf', b'%PDF-1.4\n%%EOF')

    def test_device_confirmation_preserves_original_expiry(self):
        import time
        until = int(time.time()) + 7 * 86400
        j = self.j
        cookie = j._device_cookie(until)
        session = {}
        self.assertTrue(j._restore_device(session, cookie))
        self.assertEqual(session['pbj'][str(j.id)], until)
        self.assertFalse(person(self.env)._restore_device({}, cookie))
        for invalid in (None, 'invalid', cookie[:-1]+'X', j._device_cookie(1), j._device_cookie(until+15*86400)):
            self.assertFalse(j._restore_device({}, invalid))

    def test_back_keeps_private_draft_until_validated(self):
        row, spec = self._item('tax_number')
        field = spec['fields'][0]
        row._draft(spec, {field['name']: '0123456789'}, [])
        self.assertFalse(row.values)
        self.assertEqual(row.state, 'empty')
        self.assertNotIn('0123456789', row._display(field))
        row._save(spec, {})
        self.assertEqual(row.values[field['name']], '0123456789')
        self.assertFalse(row.draft)
