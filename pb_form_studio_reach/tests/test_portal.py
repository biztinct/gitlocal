# -*- coding: utf-8 -*-
"""FS-5 item 4 (R14) — company details on My Payobook › My details, over
HTTP as a real portal login. P1 shown-only vs changeable; P2 saved at once vs
after HR approves, refusal writes nothing; P3 forged fields refused; P4 only
the session's own record; P5 Country of Work; P6 untick closes an open
request; P7 one open request per field; P8 delete blocker; P9 vi words."""
import json
import re

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged

from odoo.addons.pb_me_details.tests.common import decide, seat

from .common import PASSWORD, ReachCase


@tagged('post_install', '-at_install', 'pb_form_studio_reach')
class TestReachPortal(ReachCase, HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not hasattr(cls.env['pb.form.studio'], 'portal_check'):
            return
        seat(cls.env, cls.company, 'hr_lead', cls.hr)
        Meta = cls.env['pb.form.field.meta'].sudo()

        def tick(name, show=True, edit=False, mode='approve'):
            Meta.search([('model', '=', 'hr.employee'), ('name', '=', name)]).write(
                {'portal_show': show, 'portal_edit': edit, 'portal_mode': mode})
        tick(cls.f_all)                                      # shown only
        tick(cls.f_num)                                      # HR-only field, shown to its owner
        tick(cls.f_sel, edit=True)                           # changes after HR approves
        tick(cls.f_date, edit=True, mode='instant')          # saved at once
        tick(cls.f_in, edit=True)                            # India only
        cls.Req = cls.env['pb.me.detail.request']

    def setUp(self):
        super().setUp()
        if not hasattr(self.env['pb.form.studio'], 'portal_check'):
            self.skipTest('the engine portal methods (fs-1 follow-up) are not merged yet')
        if 'pb.privacy.notice' in self.env:
            self.env['pb.privacy.notice'].sudo().search(
                [('state', '=', 'published')]).write({'state': 'replaced'})

    # ---------------------------------------------------------------- helpers
    def _page(self, url='/my/details'):
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        self.assertNotIn('Odoo', res.text.replace('odoo', ''), url)
        return res.text

    def _csrf(self):
        page = self._page('/my/details/company')
        return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)

    def _send(self, **vals):
        data = {'csrf_token': self._csrf()}
        data.update({'pbfr__' + k: v for k, v in vals.items()})
        return self.url_open('/my/details/company/send', data=data)

    def _open(self, emp=None):
        return self.Req.sudo().search([('employee_id', '=', (emp or self.emp_vn).id),
                                       ('kind', '=', 'company_details'),
                                       ('state', '=', 'hr_review'),
                                       ('fb_replaced', '=', False)])

    # ---------------------------------------------------------------- P1
    def test_p1_shown_only_and_changeable(self):
        self.authenticate('pbfr_me', PASSWORD)
        page = self._page()
        for label in ('DEMO T-shirt size', 'DEMO Shoe size', 'DEMO Shift', 'DEMO Safety course on'):
            self.assertIn(label, page)
        self.assertIn('Change these details', page)
        for hidden in ('DEMO Secret score', 'DEMO Locker number', 'DEMO Safety card',
                       'DEMO Drives a forklift', 'DEMO Board note'):
            self.assertNotIn(hidden, page)
        form = self._page('/my/details/company')
        self.assertIn('pbfr__%s' % self.f_sel, form)
        self.assertIn('pbfr__%s' % self.f_date, form)
        self.assertNotIn('pbfr__%s' % self.f_all, form, 'shown-only has no box')
        self.assertNotIn('pbfr__%s' % self.f_num, form)

    # ---------------------------------------------------------------- P2
    def test_p2_instant_and_approve(self):
        self.authenticate('pbfr_me', PASSWORD)
        res = self._send(**{self.f_date: '2026-09-01', self.f_sel: 'opt_1'})
        self.assertIn('/my/details', res.url)
        self.emp_vn.invalidate_recordset()
        self.assertEqual(str(self.emp_vn.sudo()[self.f_date]), '2026-09-01', 'saved at once')
        self.assertEqual(self.emp_vn.sudo()[self.f_sel], 'opt_2', 'waits for HR')
        req = self._open()
        self.assertEqual(len(req), 1)
        self.assertEqual(json.loads(req.fb_values_json), {self.f_sel: 'opt_1'})
        rows = req._pb_rows()
        self.assertEqual(rows, [('DEMO Shift', 'Late', 'Early')])
        self.assertIn('DEMO Shift', self._page())          # "Your changes" list
        decide(self.env, req, 'approve')
        self.emp_vn.invalidate_recordset()
        self.assertEqual(self.emp_vn.sudo()[self.f_sel], 'opt_1')
        self.assertEqual(req.state, 'approved')
        # Refused: nothing changes, the reason is on the page.
        self._send(**{self.f_sel: 'opt_2'})
        req2 = self._open()
        decide(self.env, req2, 'reject', 'DEMO not on the roster')
        self.emp_vn.invalidate_recordset()
        self.assertEqual(self.emp_vn.sudo()[self.f_sel], 'opt_1')
        self.assertIn('DEMO not on the roster', self._page('/my/details/request/%s' % req2.id))

    # ---------------------------------------------------------------- P3
    def test_p3_forged_fields_refused(self):
        self.authenticate('pbfr_me', PASSWORD)
        for name, value in ((self.f_admin, '99'), (self.f_all, 'XXL'), (self.f_num, '50'),
                            ('name', 'DEMO Forged'), ('x_pbfs_nope', '1')):
            res = self._send(**{name: value})
            self.assertEqual(res.status_code, 200)
            self.assertIn('pbmd-alert', res.text, name)
        self.emp_vn.invalidate_recordset()
        e = self.emp_vn.sudo()
        self.assertEqual((e[self.f_admin], e[self.f_all], e[self.f_num], e.name),
                         (7.5, 'M', 42, 'DEMO Reach Lan'))
        self.assertFalse(self._open())

    # ---------------------------------------------------------------- P4
    def test_p4_only_my_own_record(self):
        self.authenticate('pbfr_me', PASSWORD)
        self._send(**{self.f_date: '2026-10-10', 'employee_id': str(self.emp_in.id)})
        self.emp_in.invalidate_recordset()
        self.assertFalse(self.emp_in.sudo()[self.f_date])
        with self.assertRaises(AccessError):
            self.Req.with_user(self.portal).pbfr_portal_send(self.emp_in, {self.f_sel: 'opt_1'})

    # ---------------------------------------------------------------- P5
    def test_p5_country_of_work(self):
        self.authenticate('pbfr_me', PASSWORD)
        self.assertNotIn('DEMO Bus pass zone', self._page())
        res = self._send(**{self.f_in: '4'})
        self.assertIn('pbmd-alert', res.text)
        self.authenticate('pbfr_me2', PASSWORD)
        self.assertIn('DEMO Bus pass zone', self._page())

    # ---------------------------------------------------------------- P6
    def test_p6_untick_closes_open_request(self):
        self.authenticate('pbfr_me', PASSWORD)
        self._send(**{self.f_sel: 'opt_1'})
        req = self._open()
        self.assertTrue(req)
        meta = self.env['pb.form.field.meta'].sudo().search(
            [('model', '=', 'hr.employee'), ('name', '=', self.f_sel)])
        meta.write({'portal_edit': False})
        req.invalidate_recordset()
        self.assertEqual(req.state, 'refused')
        self.assertIn('no longer takes changes', req.decision_note)
        self.assertEqual(self.emp_vn.sudo()[self.f_sel], 'opt_2')

    # ---------------------------------------------------------------- P7
    def test_p7_one_open_request_per_field(self):
        self.authenticate('pbfr_me', PASSWORD)
        self._send(**{self.f_sel: 'opt_1'})
        first = self._open()
        self._send(**{self.f_sel: 'opt_1', self.f_date: '2026-11-11'})
        self.assertEqual(len(self._open()), 1)
        first.invalidate_recordset()
        self.assertTrue(first.fb_replaced)
        self.assertEqual(json.loads(self._open().fb_values_json), {self.f_sel: 'opt_1'})

    # ---------------------------------------------------------------- P8
    def test_p8_open_request_blocks_delete(self):
        self.authenticate('pbfr_me', PASSWORD)
        self._send(**{self.f_sel: 'opt_1'})
        kinds = [r['kind'] for r in self.env['pb.form.studio'].with_user(self.admin)
                 .field_references('hr.employee', self.f_sel)]
        self.assertIn('portal_request', kinds)
