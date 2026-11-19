# -*- coding: utf-8 -*-
"""R19 (owner, 2026-11-20) — more STANDARD employee boxes may be ticked
"Show on My Payobook" / "Employee can change it". Real employee screen (no
host patched), over HTTP as a real portal login (FS_FOLLOWUP1B_REPORT.md,
tests B1–B8).

B1 the six newly openable boxes accept both ticks; the boxes that stay
   closed refuse "Employee can change it" with their plain reason
B2 nothing is ticked by default (silent): no employee sees a standard box
B3 unticked: not on My details, no box on the change form; a forged POST and
   a direct engine call are refused and nothing is written
B4 ticked + "HR approves": the change waits in the approver's inbox, the
   stored value is unchanged; approve writes, refuse leaves it
B5 ticked + "Saves at once": saved, with a history line on the record and a
   Form builder history row per box
B6 another employee can neither see nor change them
B7 the locked boxes stay refused even with a forged request (address, bank,
   tax, Country of Work, manager, children)
B8 the existing My details flows are untouched (address / emergency contact
   still answer "Already on My details")
"""
import json
import re
import secrets
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.pb_me_details.tests.common import decide, seat

HOST = 'employee_detail'
EMP = 'hr.employee'
PASSWORD = secrets.token_urlsafe(16)

#: box → (value before, value proposed). The six boxes R19 opens.
NEW_BOXES = {
    'spouse_complete_name': ('DEMO Minh Tran', 'DEMO Minh Tran Le'),
    'spouse_birthdate': ('1990-04-02', '1990-04-03'),
    'distance_home_work': (5, 12),
    'distance_home_work_unit': ('kilometers', 'miles'),
    'pb_blood_type': ('A+', 'O-'),
    'pb_religion': ('DEMO None', 'DEMO Other'),
}
#: boxes that must stay closed, whatever is posted.
LOCKED = ('private_street', 'private_street2', 'private_city', 'private_zip', 'children',
          'emergency_contact', 'bank_name', 'payroll_country', 'parent_id', 'ssnid',
          'legal_name', 'additional_note', 'tz', 'birthday', 'name')


@tagged('post_install', '-at_install', 'pb_form_studio_reach')
class TestR19StandardBoxes(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ready = HOST in cls.env['pb.form.studio']._pbfs_hosts() and all(
            n in cls.env[EMP]._fields for n in NEW_BOXES)
        if not cls.ready:
            return
        Studio = type(cls.env['pb.form.studio'])
        cls.startClassPatcher(patch.object(Studio, '_pbfs_busy', lambda s: ''))
        cls.company = cls.env.company
        cls.ticked_before = cls.env['pb.form.field.meta'].sudo().search_count(
            [('model', '=', EMP), ('custom', '=', False), ('portal_show', '=', True)])
        cls.admin = new_test_user(cls.env, 'r19_admin', name='DEMO R19 Admin',
                                  groups='base.group_user,base.group_system,hr.group_hr_user')
        cls.hr = new_test_user(cls.env, 'r19_hr', name='DEMO R19 HR',
                               groups='base.group_user,hr.group_hr_user,hr.group_hr_manager')
        cls.me = new_test_user(cls.env, 'r19_me', name='DEMO R19 Lan',
                               groups='base.group_portal', password=PASSWORD)
        cls.other = new_test_user(cls.env, 'r19_other', name='DEMO R19 Arjun',
                                  groups='base.group_portal', password=PASSWORD)
        Emp = cls.env[EMP].with_context(tracking_disable=True)
        cls.emp = Emp.create({'name': 'DEMO R19 Lan', 'company_id': cls.company.id,
                              'payroll_country': 'VN', 'user_id': cls.me.id,
                              'private_street': 'DEMO 1 Street'})
        cls.emp_other = Emp.create({'name': 'DEMO R19 Arjun', 'company_id': cls.company.id,
                                    'payroll_country': 'IN', 'user_id': cls.other.id})
        cls.emp.sudo().write({n: v[0] for n, v in NEW_BOXES.items()})
        cls.emp_other.sudo().write({'spouse_complete_name': 'DEMO Hoa Pham',
                                    'pb_blood_type': 'B+'})
        seat(cls.env, cls.company, 'hr_lead', cls.hr)
        cls.Req = cls.env['pb.me.detail.request']

    def setUp(self):
        super().setUp()
        if not self.ready:
            self.skipTest('the employee screen or one of its boxes is not installed')
        if 'pb.privacy.notice' in self.env:
            self.env['pb.privacy.notice'].sudo().search(
                [('state', '=', 'published')]).write({'state': 'replaced'})

    # ---------------------------------------------------------------- utils
    def S(self):
        return self.env['pb.form.studio'].with_user(self.admin)

    def tick(self, names, edit=True, mode='approve'):
        for name in names:
            self.S().update_portal(EMP, name, {'portal_show': True, 'portal_edit': edit,
                                               'portal_mode': mode})

    def label(self, name):
        return self.env[EMP]._fields[name].get_description(self.env, ['string'])['string']

    def page(self, url='/my/details'):
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        self.assertNotIn('Odoo', res.text.replace('odoo', ''), url)
        return res.text

    def send(self, vals):
        page = self.page('/my/details/company')
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        data = {'csrf_token': token}
        data.update({'pbfr__' + k: str(v) for k, v in vals.items()})
        return self.url_open('/my/details/company/send', data=data)

    def values(self, emp=None):
        rec = (emp or self.emp).sudo()
        rec.invalidate_recordset()
        out = {}
        for name in NEW_BOXES:
            v = rec[name]
            out[name] = str(v) if name == 'spouse_birthdate' else v
        return out

    def before(self):
        return {n: v[0] for n, v in NEW_BOXES.items()}

    def proposed(self):
        return {n: v[1] for n, v in NEW_BOXES.items()}

    def open_request(self):
        return self.Req.sudo().search([('employee_id', '=', self.emp.id),
                                       ('kind', '=', 'company_details'),
                                       ('state', '=', 'hr_review'),
                                       ('fb_replaced', '=', False)])

    # ------------------------------------------------------------------ B1
    def test_b1_which_boxes_open(self):
        S = self.S()
        for name in NEW_BOXES:
            rules = S._pbfs_portal_rules(EMP, name)
            self.assertTrue(rules['can_show'] and rules['can_edit'], (name, rules))
            desc = S.update_portal(EMP, name, {'portal_show': True, 'portal_edit': True})
            self.assertTrue(desc['portal']['edit'], name)
            self.assertEqual(desc['portal']['mode'], 'approve', 'default: HR approves')
        for name in LOCKED:
            if name not in self.env[EMP]._fields:
                continue
            rules = S._pbfs_portal_rules(EMP, name)
            self.assertFalse(rules['can_edit'], name)
            self.assertTrue(rules['edit_reason'], name)
            self.assertNotIn('Odoo', rules['edit_reason'])
            with self.assertRaises(UserError, msg=name):
                S.update_portal(EMP, name, {'portal_show': True, 'portal_edit': True})
        # The wage is never even shown.
        with self.assertRaises(UserError):
            S.update_portal(EMP, 'wage', {'portal_show': True})

    # ------------------------------------------------------------------ B2
    def test_b2_nothing_ticked_by_default(self):
        self.assertEqual(self.ticked_before, 0)
        self.assertEqual(self.env['pb.form.studio'].fields_for(EMP, 'portal', record=self.emp), [])
        self.authenticate('r19_me', PASSWORD)
        page = self.page()
        for name in NEW_BOXES:
            self.assertNotIn(self.label(name), page, name)

    # ------------------------------------------------------------------ B3
    def test_b3_unticked_refused(self):
        # One OTHER box is changeable, so the change form (and its token) exists.
        self.tick(['mobile_phone'])
        self.authenticate('r19_me', PASSWORD)
        form = self.page('/my/details/company')
        for name in NEW_BOXES:
            self.assertNotIn('pbfr__%s' % name, form)
        res = self.send(self.proposed())
        self.assertIn('pbmd-alert', res.text)
        self.assertEqual(self.values(), self.before(), 'nothing written')
        self.assertFalse(self.open_request())
        Studio = self.env['pb.form.studio']
        with self.assertRaises(UserError):
            Studio.with_user(self.me).portal_apply(EMP, self.emp.sudo(), self.proposed())
        with self.assertRaises(AccessError):         # not its own record by id
            Studio.with_user(self.me).portal_apply(EMP, self.emp.id, self.proposed())
        self.assertEqual(self.values(), self.before())

    # ------------------------------------------------------------------ B4
    def test_b4_hr_approves(self):
        self.tick(NEW_BOXES)
        self.authenticate('r19_me', PASSWORD)
        page = self.page()
        for name in NEW_BOXES:
            self.assertIn(self.label(name), page, name)
        form = self.page('/my/details/company')
        for name in NEW_BOXES:
            self.assertIn('pbfr__%s' % name, form, name)
        res = self.send(self.proposed())
        self.assertIn('/my/details', res.url)
        self.assertEqual(self.values(), self.before(), 'waits for HR')
        req = self.open_request()
        self.assertEqual(len(req), 1)
        self.assertEqual(set(json.loads(req.fb_values_json)), set(NEW_BOXES))
        labels = [row[0] for row in req._pb_rows()]
        for name in NEW_BOXES:
            self.assertIn(self.label(name), labels)
        self.assertTrue(req.approval_request_id, "it is in the approver's inbox")
        decide(self.env, req, 'approve')
        self.assertEqual(self.values(), self.proposed(), 'approve writes')
        # Refused: nothing changes.
        self.send(self.before())
        req2 = self.open_request()
        self.assertTrue(req2)
        decide(self.env, req2, 'reject', 'DEMO not now')
        self.assertEqual(self.values(), self.proposed(), 'refuse leaves it')

    # ------------------------------------------------------------------ B5
    def test_b5_saves_at_once_with_history(self):
        self.tick(NEW_BOXES, mode='instant')
        audits = self.env['pb.form.audit'].sudo().search_count([('action', '=', 'portal_change')])
        msgs = len(self.emp.sudo().message_ids)
        self.authenticate('r19_me', PASSWORD)
        res = self.send(self.proposed())
        self.assertIn('done=saved', res.url)
        self.assertEqual(self.values(), self.proposed(), 'saved at once')
        self.assertFalse(self.open_request())
        rows = self.env['pb.form.audit'].sudo().search(
            [('action', '=', 'portal_change'), ('res_id', '=', self.emp.id)])
        self.assertEqual(len(rows), self.env['pb.form.audit'].sudo().search_count(
            [('action', '=', 'portal_change')]) - audits, 'one history row per box, this record')
        self.assertEqual(set(rows.mapped('field_name')), set(NEW_BOXES))
        self.emp.invalidate_recordset()
        self.assertGreater(len(self.emp.sudo().message_ids), msgs, 'history line on the record')
        self.assertTrue(any('saved at once' in (m.body or '') for m in self.emp.sudo().message_ids))

    # ------------------------------------------------------------------ B6
    def test_b6_another_employee(self):
        self.tick(NEW_BOXES, mode='instant')
        self.authenticate('r19_other', PASSWORD)
        page = self.page()
        self.assertIn('DEMO Hoa Pham', page, 'their own value')
        self.assertNotIn(NEW_BOXES['spouse_complete_name'][0], page, "never Lan's")
        # Their own record shows THEIR values only; a forged employee id is ignored.
        self.send(dict(self.proposed(), employee_id=str(self.emp.id)))
        self.assertEqual(self.values(self.emp), self.before(), "Lan's record untouched")
        Studio = self.env['pb.form.studio'].with_user(self.other)
        with self.assertRaises(AccessError):
            Studio.portal_values(EMP, self.emp.id)
        with self.assertRaises(AccessError):
            Studio.portal_apply(EMP, self.emp.id, self.proposed())
        with self.assertRaises(AccessError):
            self.Req.with_user(self.other).pbfr_portal_send(self.emp, self.proposed())
        self.assertEqual(self.values(self.emp), self.before())

    # ------------------------------------------------------------------ B7
    def test_b7_locked_boxes_refused_when_forged(self):
        self.tick(NEW_BOXES)
        # Even "shown" ticks on a locked box never make it changeable.
        for name in ('private_city', 'children', 'emergency_contact'):
            self.S().update_portal(EMP, name, {'portal_show': True})
        self.authenticate('r19_me', PASSWORD)
        snap = {n: self.emp.sudo()[n] for n in LOCKED if n in self.env[EMP]._fields}
        for name in snap:
            res = self.send({name: 'DEMO Forged 1'})
            self.assertEqual(res.status_code, 200, name)
            self.assertIn('pbmd-alert', res.text, name)
        self.emp.invalidate_recordset()
        self.assertEqual({n: self.emp.sudo()[n] for n in snap}, snap)
        self.assertFalse(self.open_request())
        with self.assertRaises(UserError):
            self.env['pb.form.studio'].with_user(self.me).portal_apply(
                EMP, self.emp.sudo(), {'private_city': 'DEMO Forged'})

    # ------------------------------------------------------------------ B8
    def test_b8_my_details_flows_untouched(self):
        rules = self.S()._pbfs_portal_rules(EMP, 'private_street')
        if 'pb.profile.change.request' in self.env:
            self.assertEqual(rules['edit_reason'],
                             'Already on My details: the employee changes it there.')
        for name in ('emergency_contact', 'emergency_phone', 'private_phone', 'private_email'):
            self.assertFalse(self.S()._pbfs_portal_rules(EMP, name)['can_edit'], name)
        for name in ('identification_id', 'passport_id', 'marital'):
            self.assertFalse(self.S()._pbfs_portal_rules(EMP, name)['can_edit'], name)
