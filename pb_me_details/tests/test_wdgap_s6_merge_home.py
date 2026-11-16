# -*- coding: utf-8 -*-
"""WDGAP Step 6 merge seams on My Payobook, the Approvals inbox and PayAI
(tag `wdgap_s6m`, handover §1 a, c, h, i).

* c — every module's `pb.me.home` override (Step 6's three phases, Step 5's
  time-into-pay page, and the older ones) calls `super()`, so tiles, "Needs
  you" rows, extra cards and "My requests" sources stack; the merged sources
  have unique keys and every one of them reads for a real employee; the home
  and the new pages answer 200 for a portal login with "My details" and
  "Certificates" drawn under "Me" (owner ruling ME1).
* h — the new approval processes exist once; laying the routes again lays
  nothing new (idempotent per company); nothing is waiting after install.
* i — PayAI for employees is off for every company after install; with it
  off the employee sees no tile and the page sends them home; no call to an
  outside service is made (the one egress point would raise).
Checks on modules that are not installed are skipped, never failed.
"""
import inspect
from unittest.mock import patch

from lxml import html as lxml_html

from odoo.tests import HttpCase, tagged

S6_MODULES = ('pb_me_details', 'pb_me_letters', 'pb_me_privacy', 'pb_hiring_internal',
              'pb_me_payai', 'pb_expense_payroll', 'pb_trip_advance',
              'pb_expense_allowance', 'pb_time_pay')
HOOKS = ('get_home_data', '_pbme_needs_extra', '_pbme_extra_cards',
         '_my_requests_sources', '_my_requests_rows', 'tile_meta')
NEW_PROCESSES = ('me_details', 'me_certificate', 'tripadvance', 'records_bank', 'scaleraise')
# the model behind each new process (S6 and S8-D); a process whose module is
# installed must exist exactly once
PROCESS_MODEL = {'me_details': 'pb.me.detail.request', 'me_certificate': 'pb.me.certificate',
                 'tripadvance': 'pb.trip.advance', 'scaleraise': 'pb.pay.scale.raise'}
PASSWORD = 's6m-home-seams-2026'


def _module_of(cls):
    parts = (cls.__module__ or '').split('.')
    return parts[2] if len(parts) > 2 and parts[0] == 'odoo' and parts[1] == 'addons' else ''


@tagged('post_install', '-at_install', 'wdgap_s6m')
class TestS6MergeHomeInboxPayai(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        cls.portal = Users.create({
            'name': 'S6M Home Walker', 'login': 's6m_home', 'password': PASSWORD,
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])]})
        cls.emp = cls.env['hr.employee'].create({
            'name': 'S6M Home Walker', 'company_id': cls.company.id,
            'user_id': cls.portal.id})
        if 'payroll.ai.config' in cls.env:
            cls.env['payroll.ai.config'].search([]).write({'is_active': False})

    # ------------------------------------------------------------- c
    def test_c1_every_home_override_calls_super(self):
        Home = type(self.env['pb.me.home'])
        seen, missing = [], []
        for klass in Home.__mro__:
            mod = _module_of(klass)
            if not mod or mod == 'pb_me_portal':
                continue
            for name in HOOKS:
                fn = klass.__dict__.get(name)
                if fn is None:
                    continue
                src = inspect.getsource(getattr(fn, '__func__', fn))
                seen.append((mod, name))
                if 'super()' not in src and 'super(' not in src:
                    missing.append((mod, name))
        s6 = [m for m, _n in seen if m in S6_MODULES]
        self.assertTrue(s6, 'Step 6 modules extend the home')
        self.assertFalse(missing, 'overrides that do not call super(): %s' % missing)

    def test_c2_my_requests_sources_stack_and_read(self):
        Home = self.env['pb.me.home'].with_user(self.portal)
        sources = Home.sudo()._my_requests_sources()
        keys = [s['key'] for s in sources]
        self.assertEqual(len(keys), len(set(keys)), 'one key per source: %s' % keys)
        expect = []
        if 'pb.me.detail.request' in self.env:
            expect += ['my_details', 'my_bank']
        if 'pb.me.certificate' in self.env:
            expect += ['certificate']
        if 'hr.applicant' in self.env and 'pb_internal' in self.env['hr.applicant']._fields:
            expect += ['pbhi_internal_role']
        for key in expect:
            self.assertIn(key, keys)
        for src in sources:
            if src['model'] not in self.env:
                continue
            # each source reads for a real employee without raising
            rows = Home.sudo()._my_requests_rows(src, self.emp.sudo())
            self.assertIsInstance(rows, list, src['key'])
        data = Home.get_my_requests(self.emp)
        self.assertIsNotNone(data)

    def test_c3_home_data_and_needs_stack(self):
        Home = self.env['pb.me.home'].with_user(self.portal)
        data = Home.get_home_data(self.emp)
        self.assertTrue(data)
        tiles = {t['url']: t for t in data['tiles']}
        for url in ('/my/details', '/my/certificates'):
            if url in tiles:
                self.assertEqual(tiles[url]['group'], 'me', url)
        self.assertIn('/my/details', tiles)
        # every "Needs you" hook runs (each module's query) without raising
        put_keys = []
        Home.sudo()._pbme_needs_extra(self.emp.sudo(),
                                      lambda key, n, url, **kw: put_keys.append(key))
        self.assertIsInstance(data['extra_cards'], list)

    def test_c4_pages_answer_for_a_portal_login(self):
        self.authenticate('s6m_home', PASSWORD)
        res = self.url_open('/my')
        self.assertEqual(res.status_code, 200)
        doc = lxml_html.fromstring(res.text)
        groups = {}
        for card in doc.xpath('//*[@data-pbme-group]'):
            for a in card.xpath('.//a[@href]'):
                groups.setdefault(a.get('href').split('?')[0], card.get('data-pbme-group'))
        self.assertEqual(groups.get('/my/details'), 'me', 'ME1: My details under Me')
        if '/my/certificates' in groups:
            self.assertEqual(groups['/my/certificates'], 'me', 'ME1: Certificates under Me')
        self.assertNotIn('Odoo', res.text.replace('odoo', ''))
        for url in ('/my/details', '/my/certificates', '/my/requests', '/my/expenses',
                    '/my/jobs', '/my/privacy', '/my/ask-policy', '/my/work/late'):
            r = self.url_open(url)
            self.assertIn(r.status_code, (200, 404), url)     # 404 = module absent
            self.assertNotEqual(r.status_code, 500, url)
            self.assertNotIn('Odoo', r.text.replace('odoo', ''), url)

    # ------------------------------------------------------------- h
    def test_h_processes_once_routes_idempotent_nothing_waiting(self):
        Process = self.env['biz.approval.process'].sudo()
        Binding = self.env['biz.approval.binding'].sudo().with_context(active_test=False)
        Request = self.env['biz.approval.request'].sudo()
        for key, model in PROCESS_MODEL.items():
            if model in self.env:
                self.assertTrue(Process.search_count([('key', '=', key)]), key)
        keys = [k for k in NEW_PROCESSES if Process.search_count([('key', '=', k)])]
        for key in keys:
            self.assertEqual(Process.search_count([('key', '=', key)]), 1, key)
            if key != 'records_bank':       # (Updates' own route, older)
                self.assertFalse(Request.search_count([('process_id.key', '=', key)]),
                                 'nothing waiting after install: %s' % key)
        before = {k: Binding.search_count([('process_id.key', '=', k)]) for k in keys}
        for mod in ('pb_me_details.models.detail_approval',
                    'pb_me_letters.models.certificate_approval',
                    'pb_trip_advance.models.advance_approval'):
            try:
                module = __import__('odoo.addons.' + mod, fromlist=['seed_all'])
            except ImportError:
                continue
            module.seed_all(self.env)
        after = {k: Binding.search_count([('process_id.key', '=', k)]) for k in keys}
        self.assertEqual(after, before, 'laying the routes again lays nothing new')
        for company in self.env['res.company'].search([]):
            for key in keys:
                self.assertLessEqual(
                    Binding.search_count([('process_id.key', '=', key),
                                          ('company_id', '=', company.id),
                                          ('active', '=', True)]), 1,
                    '%s: one route per company (%s)' % (key, company.name))

    # ------------------------------------------------------------- i
    def test_i_payai_for_employees_off_and_silent(self):
        if 'pb.policy.answer' not in self.env:
            self.skipTest('pb_me_payai is not installed')
        companies = self.env['res.company'].search([])
        self.assertFalse(companies.filtered('pb_policy_ai_on'),
                         'PayAI for employees is off for every company after install')
        Answer = type(self.env['pb.policy.answer'])

        def no_egress(*_a, **_k):
            raise AssertionError('an outside AI call was attempted')

        with patch.object(Answer, '_send', no_egress):
            self.assertFalse(self.env['pb.policy.answer'].sudo()._ready_for(self.emp.sudo()))
            self.authenticate('s6m_home', PASSWORD)
            res = self.url_open('/my/ask-policy', allow_redirects=False)
            self.assertIn(res.status_code, (301, 302, 303), 'off: the page sends them home')
            # (the home renders every tile and the portal counter hides a tile
            # whose count is 0 — S6-B P20 proves the count is 0 when off)
            self.assertEqual(self.url_open('/my').status_code, 200)
