# -*- coding: utf-8 -*-
"""R14 — fields on My Payobook, chosen per field (FS-1 follow-up, tests 25-33)."""
from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.pb_form_studio.models import form_studio as fs

HOST = 'pbfs_sample'
MODEL = 'pb.form.sample'


@tagged('post_install', '-at_install', 'pb_form_studio')
class TestPortalR14(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Studio = cls.env['pb.form.studio']
        cls.vn = cls.env.ref('base.vn')
        cls.india = cls.env.ref('base.in')
        cls.admin = new_test_user(cls.env, 'pbfs_padmin', groups='base.group_user,base.group_system',
                                  name='DEMO Portal Admin')
        cls.hr = new_test_user(cls.env, 'pbfs_phr', groups='base.group_user,hr.group_hr_user',
                               name='DEMO Portal HR')
        cls.portal = new_test_user(cls.env, 'pbfs_pportal', groups='base.group_portal',
                                   name='DEMO Portal Employee')
        cls.rec = cls.env[MODEL].create({'name': 'DEMO Own', 'country_id': cls.vn.id,
                                         'email': 'own@example.com', 'city': 'Hue'})
        cls.other = cls.env[MODEL].create({'name': 'DEMO Other person', 'country_id': cls.india.id})

    def S(self, user=None):
        return self.Studio.with_user(user or self.admin)

    def make(self, kind, label, **kw):
        return self.S().create_field(HOST, dict({'type': kind, 'label': label, 'vis': 'hr'}, **kw))['name']

    # 25 ------------------------------------------------------------------
    def test_25_flags_on_custom_and_standard_fields(self):
        n = self.make('text', 'DEMO Shirt colour', portal_show=True, portal_edit=True)
        meta = self.Studio._pbfs_meta(MODEL, [n])[n]
        self.assertTrue(meta.portal_show and meta.portal_edit)
        self.assertEqual(meta.portal_mode, 'approve', 'HR approves is the default')
        fields_before = self.env['ir.model.fields'].search_count([('model', '=', MODEL)])
        d = self.S().update_portal(MODEL, 'city', {'portal_show': True, 'portal_edit': True,
                                                   'portal_mode': 'instant'})
        self.assertEqual(self.env['ir.model.fields'].search_count([('model', '=', MODEL)]), fields_before,
                         'a standard field gets a settings row, never a new field')
        std = self.Studio._pbfs_meta(MODEL, ['city'])['city']
        self.assertFalse(std.custom)
        self.assertEqual((d['portal']['show'], d['portal']['edit'], d['portal']['mode']),
                         (True, True, 'instant'))
        self.assertNotIn('city', self.Studio._pbfs_custom_names(MODEL))
        # "can change" implies "shown"; unticking "shown" clears "can change"
        self.S().update_portal(MODEL, 'city', {'portal_show': False})
        self.assertFalse(std.portal_edit)
        # a standard field still cannot be renamed / deleted through the Studio
        with self.assertRaises(UserError):
            self.S().update_field(MODEL, 'city', {'label': 'x'})
        # administrator only
        for user in (self.hr, self.portal):
            with self.assertRaises(AccessError):
                self.S(user).update_portal(MODEL, 'email', {'portal_show': True})

    # 26 ------------------------------------------------------------------
    def test_26_hooks_and_safe_types_refused_server_side(self):
        # locked (dev host: Country of Work) → may be shown, never changed
        self.S().update_portal(MODEL, 'country_id', {'portal_show': True})
        with self.assertRaisesRegex(UserError, 'Country of Work'):
            self.S().update_portal(MODEL, 'country_id', {'portal_edit': True})
        # hidden → never shown, and the panel says why
        with patch.object(type(self.Studio), '_pbfs_portal_hidden',
                          lambda s, m: {'phone': 'Pay figures are never shown.'}):
            with self.assertRaisesRegex(UserError, 'never shown'):
                self.S().update_portal(MODEL, 'phone', {'portal_show': True})
            desc = self.S().get_studio(HOST)['fields']['phone']['portal']
            self.assertFalse(desc['can_show'])
            self.assertEqual(desc['show_reason'], 'Pay figures are never shown.')
        # money and files: shown only
        money = self.make('money', 'DEMO Allowance')
        with self.assertRaises(UserError):
            self.S().update_field(MODEL, money, {'portal_edit': True})
        self.S().update_field(MODEL, money, {'portal_show': True})
        self.assertFalse(self.S().get_studio(HOST)['fields'][money]['portal']['can_edit'])
        # a standard field the host does not offer
        with self.assertRaises(UserError):
            self.S().update_portal(MODEL, 'company_id', {'portal_show': True})
        # a host without a self-service page
        with patch.object(type(self.Studio), '_pbfs_portal_host', lambda s, m: (None, None)):
            with self.assertRaises(UserError):
                self.S().update_portal(MODEL, 'email', {'portal_show': True})
            self.assertIsNone(self.S().get_studio(HOST)['fields']['email']['portal'])

    # 27 ------------------------------------------------------------------
    def test_27_fields_for_portal(self):
        self.env['res.lang']._activate_lang('vi_VN')
        admin_only = self.make('text', 'DEMO Locker', vis='admin', portal_show=True,
                               labels={'vi_VN': 'Tủ đồ'})
        india = self.make('text', 'DEMO PAN', country_ids=[self.india.id], portal_show=True,
                          portal_edit=True)
        not_ticked = self.make('text', 'DEMO Internal note')
        self.S().update_portal(MODEL, 'email', {'portal_show': True, 'portal_edit': True,
                                                'portal_mode': 'instant'})
        st = self.S().get_studio(HOST)
        self.S().publish(HOST, {'base_version': st['version'], 'sections': [
            {'id': 'about', 'fields': ['name', 'email', 'phone']},
            {'id': 'custom', 'fields': [india, admin_only, not_ticked]}]})
        P = self.Studio.with_user(self.portal)            # the self-service caller
        specs = P.fields_for(MODEL, 'portal', record=self.rec)
        names = [s['name'] for s in specs]
        self.assertEqual(names, ['email', admin_only],
                         'layout order; India-only field absent for a Vietnam record')
        self.assertNotIn(not_ticked, names)
        email = specs[0]
        self.assertEqual((email['edit'], email['mode'], email['section']), (True, 'instant', 'about'))
        # "who can see it" does not decide: an Administrators-only field is shown because ticked
        self.assertFalse(specs[1]['edit'])
        self.assertEqual(specs[1]['section'], 'custom')
        self.assertTrue(specs[1]['section_title'])
        self.assertIn(india, [s['name'] for s in P.fields_for(MODEL, 'portal', record=self.other)])
        vi = P.with_context(lang='vi_VN').fields_for(MODEL, 'portal', record=self.rec)
        self.assertEqual([s['label'] for s in vi if s['name'] == admin_only], ['Tủ đồ'])

    # 28 ------------------------------------------------------------------
    def test_28_portal_values_only_ticked_and_id_guard(self):
        n = self.make('text', 'DEMO Badge', portal_show=True)
        secret = self.make('text', 'DEMO Secret', vis='admin')
        self.rec.write({n: 'B-1', secret: 'S3CRET'})
        P = self.Studio.with_user(self.portal)
        vals = P.portal_values(MODEL, self.rec.sudo())
        self.assertEqual(vals[n]['display'], 'B-1')
        self.assertNotIn(secret, vals)
        self.assertNotIn('S3CRET', str(vals))
        # over the wire (an id), the caller must be able to read the record
        with self.assertRaises(AccessError):
            P.portal_values(MODEL, self.rec.id)
        self.assertIn(n, self.Studio.with_user(self.hr).portal_values(MODEL, self.rec.id))

    # 29 ------------------------------------------------------------------
    def test_29_portal_check(self):
        quick = self.make('text', 'DEMO Nickname', portal_show=True, portal_edit=True,
                          portal_mode='instant')
        slow = self.make('date', 'DEMO Passport expiry', portal_show=True, portal_edit=True)
        shown = self.make('text', 'DEMO Shown only', portal_show=True)
        must = self.make('text', 'DEMO Must', portal_show=True, portal_edit=True, is_required=True)
        india = self.make('text', 'DEMO PAN 2', country_ids=[self.india.id], portal_show=True,
                          portal_edit=True)
        self.rec.write({quick: 'Lan'})
        res = self.Studio.with_user(self.portal).portal_check(MODEL, self.rec.sudo(), {
            quick: 'Lanny', slow: '2030-01-31', shown: 'x', must: '', india: 'ABC',
            'name': 'Forged', 'country_id': self.india.id, 'x_pbfs_nope': 1})
        self.assertEqual(res['instant'], {quick: 'Lanny'})
        self.assertEqual(str(res['approve'][slow]), '2030-01-31')
        self.assertEqual(set(res['errors']), {shown, must, india, 'name', 'country_id', 'x_pbfs_nope'})
        same = self.Studio.portal_check(MODEL, self.rec.sudo(), {quick: 'Lan'})
        self.assertEqual((same['instant'], same['approve'], same['errors']), ({}, {}, {}),
                         'an unchanged value is dropped')
        bad = self.Studio.portal_check(MODEL, self.rec.sudo(), {slow: 'soon'})
        self.assertIn(slow, bad['errors'])

    # 30 ------------------------------------------------------------------
    def test_30_portal_apply_single_write_path_with_history(self):
        n = self.make('text', 'DEMO Nickname 2', portal_show=True, portal_edit=True)
        other_f = self.make('text', 'DEMO Untouched', portal_show=True, portal_edit=True)
        self.rec.write({n: 'old', other_f: 'keep'})
        city_before, email_before = self.rec.city, self.rec.email
        res = self.Studio.with_user(self.portal).portal_apply(
            MODEL, self.rec.sudo(), {n: 'new'},
            origin={'proposed_by': self.portal.id, 'approved_by': self.hr.id})
        self.assertEqual(res['values'][n]['display'], 'new')
        self.assertEqual(set(res['values']), {n}, 'nothing else is handed back')
        self.assertEqual((self.rec[n], self.rec[other_f], self.rec.city, self.rec.email),
                         ('new', 'keep', city_before, email_before))
        line = self.env['pb.form.audit'].search([('action', '=', 'portal_change'),
                                                 ('field_name', '=', n)])
        self.assertEqual(line.res_id, self.rec.id)
        self.assertIn('old → new', line.summary)
        self.assertIn('DEMO Portal Employee', line.summary)
        self.assertIn('approved by DEMO Portal HR', line.summary)
        self.Studio.portal_apply(MODEL, self.rec.sudo(), {n: 'newer'},
                                 origin={'proposed_by': self.portal.id})
        latest = self.env['pb.form.audit'].search([('action', '=', 'portal_change'),
                                                   ('field_name', '=', n)], order='id desc', limit=1)
        self.assertIn('saved at once', latest.summary)
        # unticked while a request was open → refused, nothing written
        self.S().update_field(MODEL, n, {'portal_edit': False})
        with self.assertRaises(UserError):
            self.Studio.portal_apply(MODEL, self.rec.sudo(), {n: 'late'})
        self.assertEqual(self.rec[n], 'newer')
        # over the wire, the caller must be allowed to WRITE the record
        with self.assertRaises(AccessError):
            self.Studio.with_user(self.portal).portal_apply(MODEL, self.rec.id, {other_f: 'x'})

    # 31 ------------------------------------------------------------------
    def test_31_busy_signal_is_database_wide_and_bounded(self):
        self.assertLessEqual(fs.BUSY_LOCK_MINUTES, 15)
        self.assertLessEqual(fs.BUSY_PRACTICE_MINUTES, 15)
        if 'hr.payslip.run' not in self.env:
            self.skipTest('payroll is not installed')
        other_co = self.env['res.company'].create({'name': 'DEMO Other Co'})
        emp = self.env['hr.employee'].create({'name': 'DEMO Payee', 'company_id': other_co.id})
        run = self.env['hr.payslip.run'].create({'name': 'DEMO run', 'date_start': '2026-11-01',
                                                 'date_end': '2026-11-30'})
        try:
            with self.env.cr.savepoint():
                slip = self.env['hr.payslip'].create({
                    'name': 'DEMO slip', 'employee_id': emp.id, 'payslip_run_id': run.id,
                    'date_from': '2026-11-01', 'date_to': '2026-11-30'})
        except Exception:                               # noqa: BLE001
            self.skipTest('a payslip cannot be made without a contract on this database')
        self.env.flush_all()
        msg = 'A pay run is being worked out right now. Try again in a few minutes.'
        self.assertEqual(self.Studio._pbfs_busy(), msg, "another company's run blocks too")
        self.assertTrue(slip)
        # The same payslip, seen from a moment just past the window: stale.
        later = fs.fields.Datetime.now() + timedelta(minutes=fs.BUSY_MINUTES + 1)
        with patch.object(fs.fields.Datetime, 'now', staticmethod(lambda *a, **k: later)):
            self.assertEqual(self.Studio._pbfs_busy(), '',
                             'a stale signal stops counting after its window')

    # 32 ------------------------------------------------------------------
    def test_32_everyone_alias_removed(self):
        self.make('text', 'DEMO Everyone field', vis='all')
        self.make('text', 'DEMO HR field', vis='hr')
        self.assertEqual(self.Studio.fields_for(MODEL, 'everyone'), [])
        self.assertEqual(self.Studio.values_for(MODEL, [], 'everyone'), {})

    # 33 ------------------------------------------------------------------
    def test_33_publish_routes_standard_ticks(self):
        st = self.S().get_studio(HOST)
        self.assertTrue(st['host']['portal'])
        self.assertIn('portal', st['fields']['email'])
        self.S().publish(HOST, {'base_version': st['version'],
                                'sections': [{'id': 'about', 'fields': ['name', 'email']}],
                                'updates': {'email': {'portal_show': True}},
                                'creates': [{'tmp': '1', 'type': 'bool', 'label': 'DEMO Vegetarian',
                                             'portal_show': True, 'portal_edit': True,
                                             'portal_mode': 'instant'}]})
        st2 = self.S().get_studio(HOST)
        self.assertTrue(st2['fields']['email']['portal']['show'])
        veg = [f for f in st2['fields'].values() if f['label'] == 'DEMO Vegetarian'][0]
        self.assertEqual((veg['portal']['show'], veg['portal']['edit'], veg['portal']['mode']),
                         (True, True, 'instant'))
