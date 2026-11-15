# -*- coding: utf-8 -*-
"""WDGAP S5-A — the Kinds of leave screen.

S1 who may look and who may change: a plain login is refused, the Time Off
   team reads, a tenant HR manager (no system rights) writes.
S2 tenant staff can reach it: the Settings › HR door resolves for a tenant
   HR manager, the action opens, and the registry spellings match the hubs.
S3 a new kind starts switched off; switching on needs a pay decision.
S4 what cannot change: how a used kind is counted; pay under a leave policy.
S5 building up: plain refusals; "Build-up starts from" set to this month.
S6 names in Vietnamese and Indonesian go into the field's translations.
S7 the preview: rules in words, the service table, what the employee sees.
S8 the list, its steps and filters; "add the finished months now".
S9 the set-up check: kinds with no pay decision, people with no start date.
S10 white-label: no vendor name in anything this module shows.
"""
import json
import os
import re
from datetime import date
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import tagged
from odoo.tools import file_open

from .common import LeaveSetupCase

HERE = os.path.dirname(os.path.dirname(__file__))


@tagged('post_install', '-at_install', 'wdgap_s5a')
class TestSetup(LeaveSetupCase):

    def _as(self, user):
        return self.env['pb.leave.setup'].with_user(user).with_context(
            allowed_company_ids=[self.company.id])

    def _new(self, **vals):
        base = {'name': 'S5A New', 'unit': 'day', 'counted': True, 'pay': 'paid',
                'funding': 'employer', 'earning': 'none'}
        base.update(vals)
        return self._as(self.hr_user).save_kind(0, base)

    # ============================================================== S1
    def test_s1_gates(self):
        plain = self._as(self.plain)
        self.assertFalse(plain.get_board()['allowed'])
        self.assertIn('refused', plain.pbf_layout())
        with self.assertRaises(AccessError):
            plain.get_kind(self._kind('S5A Any').id)
        with self.assertRaises(AccessError):
            plain.save_kind(0, {'name': 'Nope'})
        officer = self._as(self.officer)
        board = officer.get_board()
        self.assertTrue(board['allowed'])
        self.assertFalse(board['can_write'])
        with self.assertRaises(AccessError):
            officer.save_kind(0, {'name': 'Nope'})
        with self.assertRaises(AccessError):
            officer.starter_apply('VN', self.company.id, ['VN.annual'])
        hr = self._as(self.hr_user)
        self.assertTrue(hr.get_board()['can_write'])
        k = self._new(name='S5A By tenant HR')
        self.assertTrue(k['id'])

    # ============================================================== S2
    def test_s2_tenant_staff_reach_it(self):
        self.assertFalse(self.hr_user.has_group('base.group_system'))
        action = self.env.ref('pb_leave_setup.action_pb_leave_kinds')
        # the web client loads an action under sudo (web/controllers/action.py)
        # and refuses it only for the action's own groups: there are none
        self.assertEqual(action.tag, 'pb_leave_kinds')
        for fname in ('group_ids', 'groups_id'):
            if fname in action._fields:
                self.assertFalse(action[fname])
        with file_open(os.path.join(HERE, 'static/src/js/leave_setup_palette.js')) as fh:
            palette = fh.read()
        gate = re.search(r'LEAVE_SETUP_GATE = \[(.*?)\]', palette, re.S).group(1)
        groups = re.findall(r'"([\w.]+)"', gate)
        if 'pb.settings' in self.env:
            ans = self.env['pb.settings'].with_user(self.hr_user).resolve_gates([{
                'key': 'leave_kinds', 'groups': groups,
                'cards': [{'id': 'leave_kinds', 'xmlid': 'pb_leave_setup.action_pb_leave_kinds'}]}])
            self.assertTrue(ans['categories']['leave_kinds'])
            self.assertTrue(ans['cards']['leave_kinds:leave_kinds'])
            refused = self.env['pb.settings'].with_user(self.plain).resolve_gates([{
                'key': 'leave_kinds', 'groups': groups, 'cards': []}])
            self.assertFalse(refused['categories']['leave_kinds'])
            with file_open('pb_settings/static/src/js/settings_hub.js') as fh:
                hub = fh.read()
            self.assertIn('SETTINGS_CATEGORIES = "pb_settings_category"', hub)
            self.assertIn('{ key: "hr",', hub)
        self.assertIn('registry.category("pb_settings_category").add("leave_kinds"', palette)
        self.assertIn('group: "hr"', palette)
        self.assertIn('registry.category("pb_hub_palette")', palette)
        self.assertIn('requires: "pb_leave_kinds"', palette)

    # ============================================================== S3
    def test_s3_switching_on(self):
        hr = self._as(self.hr_user)
        k = self._new(name='S5A Undecided', pay='unconfigured', funding='unconfigured')
        self.assertEqual(k['state'], 'off', 'a new kind starts switched off')
        with self.assertRaises(UserError) as caught:
            hr.set_active(k['id'], True)
        self.assertIn('paid', caught.exception.args[0])
        k = hr.save_kind(k['id'], {'pay': 'paid', 'funding': 'employer'}, switch_on=True)
        self.assertEqual(k['state'], 'on')
        k = hr.set_active(k['id'], False)
        self.assertEqual(k['state'], 'off')
        kind = self.env['hr.leave.type'].with_context(active_test=False).browse(k['id'])
        self.assertFalse(kind.active)
        # a partly paid kind from an outside fund keeps the pay rule's own check
        k2 = self._new(name='S5A Partly', pay='partial', pay_pct=75, funding='external')
        kind2 = self.env['hr.leave.type'].with_context(active_test=False).browse(k2['id'])
        self.assertEqual((kind2.pb_pay_treatment, kind2.pb_paid_fraction, kind2.pb_pay_funding),
                         ('partial', 0.75, 'external'))
        with self.assertRaises(UserError):
            self._new(name='S5A Bad', pay='paid', funding='none')

    # ============================================================== S4
    def test_s4_what_cannot_change(self):
        hr = self._as(self.hr_user)
        kind = self._kind('S5A Used', leave_validation_type='no_validation')
        emp = self._emp('S5A User of it', joined=date(2020, 1, 1))
        self._alloc(emp, kind, 5, date(2026, 1, 1))
        self._leave(emp, kind, date(2026, 12, 14), date(2026, 12, 14))
        with self.assertRaises(UserError) as caught:
            hr.save_kind(kind.id, {'unit': 'hour'})
        self.assertIn('cannot change', caught.exception.args[0])
        with self.assertRaises(UserError):
            hr.save_kind(kind.id, {'counted': False})
        self.assertTrue(hr.get_kind(kind.id)['locks']['used'])
        # the same values are fine
        hr.save_kind(kind.id, {'unit': 'day', 'counted': True, 'name': 'S5A Used'})
        # under a published leave policy the pay is the policy's
        with patch.object(type(self.env['pb.leave.setup']), '_policy_bound',
                          lambda self, k: True):
            with self.assertRaises(UserError) as caught:
                hr.save_kind(kind.id, {'pay': 'unpaid', 'funding': 'none'})
            self.assertIn('leave policy', caught.exception.args[0])
            hr.save_kind(kind.id, {'pay': kind.pb_pay_treatment, 'funding': kind.pb_pay_funding,
                                   'name': 'S5A Used'})
            with self.assertRaises(UserError):
                hr.save_kind(kind.id, {'earning': 'monthly', 'days_per_year': 12})

    # ============================================================== S5
    def test_s5_building_up(self):
        hr = self._as(self.hr_user)
        with self.assertRaises(UserError):
            self._new(name='S5A Not counted', counted=False, earning='monthly', days_per_year=12)
        with self.assertRaises(UserError):
            self._new(name='S5A Hours', unit='hour', earning='monthly', days_per_year=12)
        with self.assertRaises(UserError):
            self._new(name='S5A No days', earning='monthly', days_per_year=0)
        k = self._new(name='S5A Builds', earning='monthly', days_per_year=12,
                      steps=[{'years': 5, 'days': 1}, {'years': 10, 'days': 2}],
                      take_ahead=False, max_balance=20, expire_months=3, waiting_months=2)
        kind = self.env['hr.leave.type'].with_context(active_test=False).browse(k['id'])
        today = date.today()
        self.assertEqual(kind.pb_ls_earn_from, today.replace(day=1), 'from this month on')
        self.assertEqual([(s.after_years, s.extra_days) for s in kind.pb_ls_step_ids],
                         [(5, 1.0), (10, 2.0)])
        self.assertEqual((kind.pb_ls_max_balance, kind.pb_ls_expire_months,
                          kind.pb_ls_waiting_months), (20.0, 3, 2))
        with self.assertRaises(UserError):
            hr.save_kind(k['id'], {'steps': [{'years': 5, 'days': 1}, {'years': 5, 'days': 2}]})
        k = hr.save_kind(k['id'], {'earn_from': '2026-02-17'})
        self.assertEqual(k['earn_from'], '2026-02-01')

    # ============================================================== S6
    def test_s6_names_in_three_languages(self):
        langs = {c for c, _n in self.env['res.lang'].get_installed()}
        k = self._new(name='S5A Annual', names={'en': 'S5A Annual', 'vi': 'S5A Phép năm',
                                                 'id': 'S5A Cuti tahunan'})
        kind = self.env['hr.leave.type'].with_context(active_test=False).browse(k['id'])
        self.assertEqual(kind.with_context(lang='en_US').name, 'S5A Annual')
        if 'vi_VN' in langs:
            self.assertEqual(kind.with_context(lang='vi_VN').name, 'S5A Phép năm')
        if 'id_ID' in langs:
            self.assertEqual(kind.with_context(lang='id_ID').name, 'S5A Cuti tahunan')

    # ============================================================== S7
    def test_s7_preview(self):
        hr = self._as(self.hr_user)
        p = hr.preview({'name': 'S5A Prev', 'counted': True, 'unit': 'day', 'earning': 'monthly',
                        'days_per_year': 12, 'steps': [{'years': 5, 'days': 1}],
                        'waiting_months': 2, 'take_ahead': False, 'document': True})
        words = ' '.join(p['rules'])
        self.assertIn('12 days a year', words)
        self.assertIn('only what they have earned so far', words)
        self.assertIn('first 2 months', words)
        self.assertEqual([(r['years'], r['year'], r['month']) for r in p['table']],
                         [(0, '12', '1'), (5, '13', '1.08')])
        self.assertTrue(p['tile']['earned_label'])
        self.assertTrue(p['option']['shown'])
        self.assertTrue(p['option']['document'])
        p = hr.preview({'name': 'S5A HR only', 'counted': False, 'hr_only': True})
        self.assertIsNone(p['tile'])
        self.assertFalse(p['option']['shown'])

    # ============================================================== S8
    def test_s8_list_and_post_now(self):
        hr = self._as(self.hr_user)
        on = self._new(name='S5A Listed on')
        hr.set_active(on['id'], True)
        self._new(name='S5A Listed off')
        page = hr.get_kinds_page(filters={'state': ['off']}, search='S5A Listed')
        self.assertEqual([r['name'] for r in page['rows']], ['S5A Listed off'])
        page = hr.get_kinds_page(filters={}, search='S5A Listed')
        self.assertEqual(page['total'], 2)
        self.assertGreaterEqual(page['steps'].get('on', 0), 1)
        self.assertGreaterEqual(page['steps'].get('off', 0), 1)
        # build-up now: only for a kind that builds up
        with self.assertRaises(UserError):
            hr.post_now(on['id'])
        emp = self._emp('S5A Post now person', joined=date(2020, 1, 1))
        kind = self._kind('S5A Post now', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                          pb_ls_earn_from=date.today().replace(day=1))
        res = hr.post_now(kind.id)
        self.assertIn('msg', res)
        # this month has not ended: nothing for anybody yet
        self.assertFalse(self.Earn.search_count([('employee_id', '=', emp.id),
                                                 ('leave_type_id', '=', kind.id)]))

    # ============================================================== S9
    def test_s9_set_up_check(self):
        hr = self._as(self.hr_user)
        open_kind = self._kind('S5A Pay open', pb_pay_treatment='unconfigured',
                               pb_pay_funding='unconfigured')
        self._kind('S5A Steps', pb_ls_earning='monthly', pb_ls_days_per_year=12,
                   pb_ls_earn_from=date(2026, 1, 1), steps=[(5, 1)])
        nobody = self._emp('S5A Nobody knows when')
        board = hr.get_board()
        before = board['kpis']['pay_open']
        self.assertGreaterEqual(before, 1)
        self.assertEqual(len(board['checks']['pay_open']) + board['checks']['pay_open_more'], before)
        page = hr.get_kinds_page(filters={'pay': ['open'], 'state': ['on']}, search='S5A Pay open')
        self.assertEqual([r['id'] for r in page['rows']], [open_kind.id])
        self.assertTrue(page['rows'][0]['pay_open'])
        open_kind.write({'pb_pay_treatment': 'paid', 'pb_pay_funding': 'employer'})
        self.assertEqual(hr.get_board()['kpis']['pay_open'], before - 1)
        self.assertGreaterEqual(board['checks']['no_start']['count'], 1)
        self.assertGreaterEqual(board['kpis']['no_start'], 1)
        del nobody

    # ============================================================== S10
    def test_s10_no_vendor_name_on_screen(self):
        bad = re.compile(r'odoo', re.I)
        allowed = re.compile(r'@odoo/owl|@odoo-module|odoo-javascript|odoo-python|from odoo|</?odoo>')
        for rel in ('static/src/xml/leave_setup.xml', 'static/src/js/leave_setup.js',
                    'static/src/js/leave_setup_palette.js', 'views/portal_templates.xml',
                    'views/leave_setup_actions.xml', 'data/ir_cron.xml',
                    'i18n/vi_VN.po', 'i18n/id_ID.po'):
            with file_open(os.path.join(HERE, rel)) as fh:
                text = fh.read()
            # comments are for engineers (they keep the real name)
            if rel.endswith('.xml'):
                text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
            if rel.endswith('.js'):
                text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
                text = re.sub(r'^\s*//.*$', '', text, flags=re.M)
            for n, line in enumerate(text.splitlines(), 1):
                if rel.endswith('.po') and not line.startswith('msgstr'):
                    continue
                if bad.search(allowed.sub('', line)):
                    self.fail('%s:%s names the vendor: %s' % (rel, n, line.strip()))
        with file_open(os.path.join(HERE, 'data/starters.json')) as fh:
            text = json.dumps(json.load(fh)['countries'])
        self.assertFalse(bad.search(text))
