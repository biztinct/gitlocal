# -*- coding: utf-8 -*-
"""FS-10 — R27 (owner, 2026-11-20): a standard field the administrator renamed
in the Form builder shows that label on My Payobook too, in the reader's
language, wherever the Form builder shows the field to the employee.

Real employee screen (no host patched), over HTTP as a real portal login.

R1 renamed (English) + ticked: My details › the company details card and the
   "Change company details" form show the own label; the built-in label is
   gone from both
R2 the reader's language: Vietnamese label typed → a Vietnamese reader sees
   it; Indonesian not typed → an Indonesian reader sees the built-in label
R3 the change waiting for HR names the field by the own label (My requests
   title and the approver's rows)
R4 Reset in the Form builder → the built-in label is back on My Payobook
R5 silent: nothing renamed → My Payobook shows exactly the built-in labels
R6 a custom field keeps its own label (unchanged path)
P  three payslips recomputed identical after hiding 5 and renaming 5
   standard fields and after the FS-10 upgrade step
"""
import json
import re
import secrets
from unittest.mock import patch

from odoo.tests import HttpCase, new_test_user, tagged

from odoo.addons.pb_me_details.tests.common import seat

from .common import ReachCase
from .test_reach import D_FROM, D_TO

HOST = 'employee_detail'
EMP = 'hr.employee'
PASSWORD = secrets.token_urlsafe(16)
BOX = 'pb_blood_type'


@tagged('post_install', '-at_install', 'pb_form_studio_reach', 'fs10')
class TestFs10R27Labels(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ready = HOST in cls.env['pb.form.studio']._pbfs_hosts() and BOX in cls.env[EMP]._fields
        if not cls.ready:
            return
        Studio = type(cls.env['pb.form.studio'])
        cls.startClassPatcher(patch.object(Studio, '_pbfs_busy', lambda s: ''))
        cls.company = cls.env.company
        cls.admin = new_test_user(cls.env, 'r27_admin', name='DEMO R27 Admin',
                                  groups='base.group_user,base.group_system,hr.group_hr_user')
        cls.hr = new_test_user(cls.env, 'r27_hr', name='DEMO R27 HR',
                               groups='base.group_user,hr.group_hr_user,hr.group_hr_manager')
        cls.me = new_test_user(cls.env, 'r27_me', name='DEMO R27 Lan',
                               groups='base.group_portal', password=PASSWORD)
        cls.emp = cls.env[EMP].with_context(tracking_disable=True).create({
            'name': 'DEMO R27 Lan', 'company_id': cls.company.id, 'payroll_country': 'VN',
            'user_id': cls.me.id, BOX: 'A+'})
        seat(cls.env, cls.company, 'hr_lead', cls.hr)
        cls.builtin = cls.env[EMP]._fields[BOX].get_description(cls.env, ['string'])['string']

    def setUp(self):
        super().setUp()
        if not self.ready:
            self.skipTest('the employee screen or the box is not installed')
        if 'pb.privacy.notice' in self.env:
            self.env['pb.privacy.notice'].sudo().search(
                [('state', '=', 'published')]).write({'state': 'replaced'})

    def S(self):
        return self.env['pb.form.studio'].with_user(self.admin)

    def page(self, url='/my/details'):
        res = self.url_open(url)
        self.assertEqual(res.status_code, 200, url)
        self.assertNotIn('Odoo', res.text.replace('odoo', ''), url)
        return res.text

    def card(self, text):
        """The company details card(s) of My details only."""
        return ' '.join(re.findall(r'<section class="pbme-card pbmd-card pbfr-card">.*?</section>',
                                   text, re.S))

    def rename(self, labels):
        self.S().update_standard(EMP, BOX, {'std_labels': labels})

    def tick(self):
        self.S().update_portal(EMP, BOX, {'portal_show': True, 'portal_edit': True,
                                          'portal_mode': 'approve'})

    # ------------------------------------------------------------------ R5
    def test_r5_silent(self):
        self.tick()
        spec = {s['name']: s for s in self.env['pb.form.studio'].fields_for(
            EMP, 'portal', record=self.emp)}
        self.assertEqual(spec[BOX]['label'], self.builtin)
        self.authenticate('r27_me', PASSWORD)
        self.assertIn(self.builtin, self.card(self.page()))

    # --------------------------------------------------------------- R1 R4
    def test_r1_r4_own_label_then_reset(self):
        self.tick()
        self.rename({'en_US': 'DEMO Blood group'})
        self.authenticate('r27_me', PASSWORD)
        card = self.card(self.page())
        self.assertIn('DEMO Blood group', card)
        self.assertNotIn('>%s<' % self.builtin, card)
        form = self.page('/my/details/company')
        self.assertIn('DEMO Blood group', form)
        self.assertNotIn('<span>%s</span>' % self.builtin, form)
        # Reset (the Form builder's "Reset to the built-in label")
        self.rename({})
        card = self.card(self.page())
        self.assertIn(self.builtin, card)
        self.assertNotIn('DEMO Blood group', card)

    # ------------------------------------------------------------------ R2
    def test_r2_reader_language(self):
        Lang = self.env['res.lang']
        for code in ('vi_VN', 'id_ID'):
            if not Lang._lang_get(code):
                Lang._activate_lang(code)
        self.tick()
        self.rename({'en_US': 'DEMO Blood group', 'vi_VN': 'DEMO Nhom mau'})
        Studio = self.env['pb.form.studio']
        label = {lang: {s['name']: s['label'] for s in Studio.with_context(lang=lang).fields_for(
            EMP, 'portal', record=self.emp)}[BOX] for lang in ('en_US', 'vi_VN', 'id_ID')}
        self.assertEqual(label['en_US'], 'DEMO Blood group')
        self.assertEqual(label['vi_VN'], 'DEMO Nhom mau')
        builtin_id = self.env[EMP].with_context(lang='id_ID')._fields[BOX].get_description(
            self.env(context={'lang': 'id_ID'}), ['string'])['string']
        self.assertEqual(label['id_ID'], builtin_id, 'not typed: the built-in label')
        # the request title follows the reader's language too
        Req = self.env['pb.me.detail.request'].sudo()
        req = Req.new({'employee_id': self.emp.id, 'kind': 'company_details',
                       'fb_values_json': json.dumps({BOX: 'O-'})})
        self.assertIn('DEMO Nhom mau', req.with_context(lang='vi_VN')._pbfr_label(BOX))

    # ------------------------------------------------------------------ R3
    def test_r3_waiting_change_names_the_own_label(self):
        self.tick()
        self.rename({'en_US': 'DEMO Blood group'})
        self.authenticate('r27_me', PASSWORD)
        page = self.page('/my/details/company')
        token = re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)
        res = self.url_open('/my/details/company/send',
                            data={'csrf_token': token, 'pbfr__' + BOX: 'O-'})
        self.assertIn('/my/details', res.url)
        req = self.env['pb.me.detail.request'].sudo().search(
            [('employee_id', '=', self.emp.id), ('kind', '=', 'company_details'),
             ('state', '=', 'hr_review')])
        self.assertEqual(len(req), 1)
        self.assertEqual(set(json.loads(req.fb_values_json)), {BOX})
        self.assertIn('DEMO Blood group', req.pb_label())
        self.assertEqual([row[0] for row in req._pb_rows()], ['DEMO Blood group'])
        self.assertIn('DEMO Blood group', self.page('/my/details'))

    # ------------------------------------------------------------------ R6
    def test_r6_custom_field_unchanged(self):
        S = self.S()
        name = S.create_field(HOST, {'type': 'text', 'label': 'DEMO Locker', 'vis': 'all'})['name']
        S.update_portal(EMP, name, {'portal_show': True})
        spec = {s['name']: s for s in self.env['pb.form.studio'].fields_for(
            EMP, 'portal', record=self.emp)}
        self.assertEqual(spec[name]['label'], 'DEMO Locker')


@tagged('post_install', '-at_install', 'pb_form_studio_reach', 'fs10')
class TestFs10Payslips(ReachCase):
    """P — three payslips (two schemes, two people; one formula reads Place
    of Birth) recomputed identical after hiding 5 standard fields, renaming
    5, and after the FS-10 upgrade step."""

    def test_p_three_payslips_identical(self):
        Std = self.env['pb.form.studio']
        if 'employee_detail' not in Std._pbfs_hosts():
            self.skipTest('the employee screen is not installed')
        gold = self.scheme('FBP1')
        born = self.scheme('FBP2', rules=[('FBBORN', 'employee.place_of_birth', 'text')])
        self.emp_vn.sudo().write({'place_of_birth': 'DEMO Hue'})
        Slip = self.env['hr.payslip'].sudo()
        slips = Slip
        for emp, con, cfg in ((self.emp_vn, self.con_vn, gold), (self.emp_in, self.con_in, gold),
                              (self.emp_vn, self.con_vn, born)):
            slips |= Slip.create({'name': 'DEMO FS10 slip', 'employee_id': emp.id,
                                  'contract_id': con.id, 'date_from': D_FROM, 'date_to': D_TO,
                                  'company_id': self.company.id, 'formula_config_id': cfg.id,
                                  'calculation_method': 'formula'})

        def snap():
            out = []
            for slip in slips:
                slip.compute_sheet()
                slip.invalidate_recordset()
                out.append({
                    'inputs': json.loads(slip.formula_input_values or '{}'),
                    'computed': json.loads(slip.formula_computed_values or '{}'),
                    'lines': sorted((l.code, l.amount, l.total) for l in slip.line_ids),
                })
            return json.dumps(out, sort_keys=True, default=str)

        before = snap()
        self.assertIn('BASIC', before)
        S = Std.with_user(self.admin)
        free = [n for n in ('pb_blood_type', 'pb_religion', 'visa_no', 'coach_id', 'additional_note')
                if n in self.env['hr.employee']._fields and S._pbfs_std_is_box('hr.employee', n)
                and n not in S._pbfs_standard_locked('hr.employee')]
        for name in free:
            S.update_standard('hr.employee', name, {'std_hidden': True})
        for name in ('place_of_birth', 'department_id', 'job_title', 'wage', 'work_email'):
            if S._pbfs_std_is_box('hr.employee', name):
                S.update_standard('hr.employee', name, {'std_labels': {'en_US': 'DEMO %s' % name}})
        self.assertTrue(free)
        after = snap()
        self.assertEqual(before, after)
        Std._pbfs_std_unhide_locked('hr.employee', 'FS-10.')
        Std._pbfs_std_unhide_locked('hr.contract', 'FS-10.')
        self.assertEqual(before, snap())
