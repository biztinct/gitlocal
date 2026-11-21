# -*- coding: utf-8 -*-
"""R18 (owner, 2026-11-20) — one published layout per screen for EVERY
company (FS_FOLLOWUP1B_REPORT.md, tests E1–E6). Engine level, on the dev
host; the employee and contract screens are proved with the real hosts in
`pb_form_studio_reach/tests/test_r18_companies.py`.

E1 a layout published while working in company A is THE layout read while
   working in company B (render of a company-B record shows the field)
E2 publishing from company B updates the same layout (no second row), and
   the change is seen from company A
E3 the one-time fold: two per-company layouts become one — the newest wins,
   a field placed only in the other company's layout is carried over into
   the same section, version above both; a second run writes nothing
E4 a field placed in no layout stays off every screen after the fold
E5 a database with no layout: the fold writes and creates nothing
E6 a draft follows its administrator from company to company (one draft)
"""
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, new_test_user, tagged

HOST = 'pbfs_sample'
MODEL = 'pb.form.sample'


@tagged('post_install', '-at_install', 'pb_form_studio')
class TestR18OneLayout(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.co_a = cls.env.company
        cls.co_b = cls.env['res.company'].create({'name': 'DEMO R18 Company B'})
        both = {'company_id': cls.co_a.id, 'company_ids': [(6, 0, [cls.co_a.id, cls.co_b.id])]}
        cls.admin = new_test_user(cls.env, 'r18e_admin', groups='base.group_user,base.group_system',
                                  name='DEMO R18 Admin', **both)
        cls.reader_b = new_test_user(cls.env, 'r18e_reader', groups='base.group_user',
                                     name='DEMO R18 Reader B', company_id=cls.co_b.id,
                                     company_ids=[(6, 0, [cls.co_b.id])])
        cls.rec_b = cls.env[MODEL].create({'name': 'DEMO R18 Person B', 'company_id': cls.co_b.id})

    def setUp(self):
        super().setUp()
        self.startPatcher(patch.object(type(self.env['pb.form.studio']), '_pbfs_busy',
                                       lambda self_: ''))
        # Every case starts from no layout at all (another suite may leave none,
        # but never assume it).
        self.env['pb.form.layout'].sudo().search([('host_key', '=', HOST)]).unlink()

    def studio(self, company, user=None):
        return self.env['pb.form.studio'].with_user(user or self.admin).with_context(
            allowed_company_ids=[company.id] + [c.id for c in (self.co_a | self.co_b) if c != company])

    def make(self, label):
        return self.studio(self.co_a).create_field(HOST, {'type': 'text', 'label': label,
                                                          'vis': 'all'})['name']

    def publish(self, company, names):
        st = self.studio(company)
        out = st.publish(HOST, {'sections': [{'id': 'custom', 'fields': list(names)}],
                                'base_version': st.get_studio(HOST)['version']})
        self.assertTrue(out.get('ok'), out)
        return out

    def placed(self, data):
        return [f['name'] for s in data['sections'] for f in s['fields']]

    def layouts(self):
        return self.env['pb.form.layout'].sudo().search([('host_key', '=', HOST)])

    # ------------------------------------------------------------------ E1
    def test_e1_published_in_a_read_in_b(self):
        name = self.make('DEMO R18 Locker')
        self.publish(self.co_a, [name])
        data = self.env['pb.form.studio'].with_user(self.reader_b).render(HOST, self.rec_b.id)
        self.assertIn(name, self.placed(data), 'a reader working only in company B sees it')
        self.assertEqual(data['version'], 1)

    # ------------------------------------------------------------------ E2
    def test_e2_publish_from_b_updates_the_same_layout(self):
        one = self.make('DEMO R18 One')
        two = self.make('DEMO R18 Two')
        self.publish(self.co_a, [one])
        self.publish(self.co_b, [two, one])
        self.assertEqual(len(self.layouts()), 1, 'one row, whatever company publishes')
        self.assertEqual(self.layouts().version, 2)
        seen_a = self.studio(self.co_a).get_studio(HOST)
        custom = next(s for s in seen_a['sections'] if s['id'] == 'custom')
        self.assertEqual(custom['fields'], [two, one])

    # ------------------------------------------------------------------ E3
    def test_e3_fold_two_company_layouts(self):
        one = self.make('DEMO R18 Fold one')
        two = self.make('DEMO R18 Fold two')
        three = self.make('DEMO R18 Fold three')
        Layout = self.env['pb.form.layout'].sudo()
        old = fields.Datetime.to_datetime('2026-11-01 08:00:00')
        new = fields.Datetime.to_datetime('2026-11-10 08:00:00')
        Layout.create({'host_key': HOST, 'model': MODEL, 'company_id': self.co_a.id,
                       'version': 4, 'published_at': old,
                       'sections': [{'id': 'about', 'fields': ['name']},
                                    {'id': 'custom', 'fields': [one, two]}]})
        keep = Layout.create({'host_key': HOST, 'model': MODEL, 'company_id': self.co_b.id,
                              'version': 2, 'published_at': new,
                              'sections': [{'id': 'about', 'fields': ['name']},
                                           {'id': 'custom', 'fields': [three, one]}]})
        out = self.env['pb.form.studio']._pbfs_merge_company_layouts()
        self.assertEqual(out, {'screens': 1, 'removed': 1, 'added': 1})
        self.assertEqual(self.layouts(), keep, 'the newest published layout is kept')
        custom = next(s for s in keep.sections if s['id'] == 'custom')
        self.assertEqual(custom['fields'], [three, one, two], 'newest order, then the rest')
        self.assertEqual(keep.version, 5, 'above every folded version')
        # Both companies now read it.
        for company in (self.co_a, self.co_b):
            eff = self.env['pb.form.studio'].with_company(company)._pbfs_effective(HOST)
            self.assertEqual(next(s for s in eff if s['id'] == 'custom')['fields'], [three, one, two])
        # Idempotent.
        before = (keep.write_date, keep.version, keep.sections)
        self.assertEqual(self.env['pb.form.studio']._pbfs_merge_company_layouts(),
                         {'screens': 0, 'removed': 0, 'added': 0})
        self.assertEqual((keep.write_date, keep.version, keep.sections), before)

    # ------------------------------------------------------------------ E4
    def test_e4_unplaced_field_stays_off_screen(self):
        placed = self.make('DEMO R18 Placed')
        hidden = self.make('DEMO R18 Not on a screen')
        Layout = self.env['pb.form.layout'].sudo()
        for company in (self.co_a, self.co_b):
            Layout.create({'host_key': HOST, 'model': MODEL, 'company_id': company.id,
                           'version': 1, 'published_at': fields.Datetime.now(),
                           'sections': [{'id': 'custom', 'fields': [placed]}]})
        self.env['pb.form.studio']._pbfs_merge_company_layouts()
        data = self.env['pb.form.studio'].with_user(self.reader_b).render(HOST, self.rec_b.id)
        self.assertIn(placed, self.placed(data))
        self.assertNotIn(hidden, self.placed(data), "the administrator's choice is kept")

    # ------------------------------------------------------------------ E5
    def test_e5_nothing_to_fold_writes_nothing(self):
        counts = {m: self.env[m].sudo().search_count([]) for m in (
            'pb.form.layout', 'pb.form.layout.draft', 'pb.form.audit', 'pb.form.native.view',
            'ir.ui.view')}
        self.assertEqual(self.env['pb.form.studio']._pbfs_merge_company_layouts(),
                         {'screens': 0, 'removed': 0, 'added': 0})
        self.assertEqual(counts, {m: self.env[m].sudo().search_count([]) for m in counts})

    # ------------------------------------------------------------------ E6
    def test_e6_one_draft_across_companies(self):
        self.studio(self.co_a).save_draft(HOST, {'sections': [], 'base_version': 0, 'note': 'A'})
        got = self.studio(self.co_b).get_studio(HOST)['draft']
        self.assertTrue(got, 'the draft started in company A opens in company B')
        self.assertEqual(got['payload'].get('note'), 'A')
        self.studio(self.co_b).save_draft(HOST, {'sections': [], 'base_version': 0, 'note': 'B'})
        Draft = self.env['pb.form.layout.draft'].sudo()
        self.assertEqual(Draft.search_count([('host_key', '=', HOST),
                                             ('user_id', '=', self.admin.id)]), 1)
        self.studio(self.co_b).discard_draft(HOST)
        self.assertFalse(self.studio(self.co_a).get_studio(HOST)['draft'])
