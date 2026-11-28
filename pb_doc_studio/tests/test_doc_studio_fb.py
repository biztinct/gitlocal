# -*- coding: utf-8 -*-
"""DOCSTUDIO phase F-b — owner/orchestrator rulings of 2026-11-22, tests 19-24.

19-20  the company's / country's own copy always wins, also when somebody
       picks the original by hand on a draft letter; a switched-off copy
       gives the original back.
21-23  a person may always get their OWN pay on their OWN document; nobody
       gets anybody else's through any route.
24     the main wording says which language it is written in.
"""
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_doc_studio import DocStudioCase


@tagged('post_install', '-at_install', 'pb_doc_studio')
class TestDocStudioFb(DocStudioCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Users = cls.env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': cls.company_a.id, 'company_ids': [(6, 0, [cls.company_a.id])]}
        # An ordinary employee login (no HR, no pay rights), linked to emp_vn.
        cls.self_user = Users.create(dict(common, name='DEMO Self Service', login='demo_pbds_self',
                                          group_ids=[(6, 0, [cls.env.ref('base.group_user').id])]))
        cls.emp_vn.user_id = cls.self_user
        cls.env['hr.contract'].create({
            'name': 'DEMO colleague contract', 'employee_id': cls.emp_id.id, 'wage': 17000000.0,
            'state': 'open', 'date_start': '2025-01-01'})
        cls.builtin = cls.env.ref('pb_lifecycle.letter_template_experience')

    # ------------------------------------------------------------ 19 + 20
    def test_19_hand_picked_original_becomes_the_copy(self):
        res = self.Studio.copy_for(self.builtin.id, self.company_b.id, [])
        copy_b = self.Template.browse(res['id'])
        self.save(copy_b, body='<p>DEMO B wording ${employee_name}</p>')
        # a draft made for somebody else, then switched by hand to a company-B
        # person with the ORIGINAL picked
        letter = self.Letter.create({'employee_id': self.emp_vn.id, 'template_id': self.builtin.id,
                                     'company_id': self.company_a.id})
        self.assertEqual(letter.template_id, self.builtin)
        self.assertFalse(letter.pbds_wording_note)
        letter.write({'employee_id': self.emp_b.id, 'template_id': self.builtin.id})
        self.assertEqual(letter.template_id, copy_b)
        self.assertEqual(letter.pbds_wording_note, "Using DEMO Doc Studio B's wording")
        # picking the original again on the draft changes nothing
        letter.write({'template_id': self.builtin.id})
        self.assertEqual(letter.template_id, copy_b)
        letter.action_generate()
        self.assertIn('DEMO B wording DEMO Budi B', str(letter.rendered_html))
        # the form does it while the person picks
        draft = self.Letter.new({'employee_id': self.emp_b.id, 'template_id': self.builtin.id})
        draft._onchange_pbds_wording()
        self.assertEqual(draft.template_id.id, copy_b.id)
        # a country copy says which country
        res_c = self.Studio.copy_for(self.builtin.id, self.company_b.id, [self.indonesia.id])
        letter2 = self.Letter.create({'employee_id': self.emp_b.id, 'template_id': self.builtin.id})
        self.assertEqual(letter2.template_id.id, res_c['id'])
        self.assertEqual(letter2.pbds_wording_note,
                         "Using DEMO Doc Studio B's wording for %s" % self.indonesia.name)
        # a letter already prepared is not re-pointed by a later edit
        letter.write({'state': 'generated'})
        letter.write({'template_id': self.builtin.id})
        self.assertEqual(letter.template_id, self.builtin)

    def test_20_switched_off_copy_gives_the_original(self):
        res = self.Studio.copy_for(self.builtin.id, self.company_b.id, [])
        copy_b = self.Template.browse(res['id'])
        self.save(copy_b, body='<p>DEMO B wording</p>')
        self.Studio.set_active(copy_b.id, False)
        letter = self.Letter.create({'employee_id': self.emp_vn.id, 'template_id': self.builtin.id})
        letter.write({'employee_id': self.emp_b.id, 'template_id': self.builtin.id})
        self.assertEqual(letter.template_id, self.builtin)
        self.assertFalse(letter.pbds_wording_note)
        letter.action_generate()
        self.assertNotIn('DEMO B wording', str(letter.rendered_html))
        self.assertIn('DEMO Budi B', str(letter.rendered_html))

    # ------------------------------------------------------------ 21 - 23
    def _pay_template(self):
        self.save(self.tmpl, body='<p>Pay ${monthly_pay}</p>')
        return self.tmpl

    def test_21_own_pay_on_own_document(self):
        tmpl = self._pay_template()
        Letter = self.Letter.with_user(self.self_user).sudo()
        letter = Letter.create({'employee_id': self.emp_vn.id, 'template_id': tmpl.id})
        letter.with_user(self.self_user).sudo().action_generate()
        # the person reads Vietnamese: 25.000.000
        self.assertRegex(str(letter.rendered_html), r'25[.,]000[.,]000')
        # the same person, not sudo, still cannot read contracts at all
        with self.assertRaises(AccessError):
            self.env['hr.contract'].with_user(self.self_user).browse(self.contract.id).check_access('read')

    def test_22_never_a_colleagues_pay(self):
        tmpl = self._pay_template()
        Letter = self.Letter.with_user(self.self_user).sudo()
        other = Letter.create({'employee_id': self.emp_id.id, 'template_id': tmpl.id})
        with self.assertRaisesRegex(UserError, 'This letter shows pay'):
            other.with_user(self.self_user).sudo().action_generate()
        self.assertNotRegex(str(other.rendered_html or ''), r'17[.,]000[.,]000')
        Studio = self.Studio.with_user(self.self_user)
        with self.assertRaises(AccessError):
            Studio.preview(tmpl.id, {}, self.emp_id.id, 'en_US')
        with self.assertRaises(AccessError):
            Studio.sample_pdf(tmpl.id, {}, self.emp_id.id, 'en_US')
        # the dedicated own-pay reader refuses any record but the caller's
        with self.assertRaises(AccessError):
            Studio.sudo()._pbds_own_pay(self.emp_id, self.company_a, 'en_US')
        vals, blocked = Studio.sudo()._pbds_generic_values(self.emp_id, self.company_a, 'en_US',
                                                           ['monthly_pay'])
        self.assertIn('monthly_pay', blocked)
        self.assertEqual(vals.get('monthly_pay'), '')

    def test_23_hr_without_pay_still_refused(self):
        tmpl = self._pay_template()
        Users = self.env['res.users'].with_context(no_reset_password=True)
        hr = Users.create({'name': 'DEMO HR no pay', 'login': 'demo_pbds_hr_nopay',
                           'company_id': self.company_a.id, 'company_ids': [(6, 0, [self.company_a.id])],
                           'group_ids': [(6, 0, [self.env.ref('pb_lifecycle.group_lifecycle_admin').id,
                                                 self.env.ref('hr.group_hr_user').id])]})
        try:
            self.env['hr.contract'].with_user(hr).browse(self.contract.id).check_access('read')
            self.skipTest('this database lets HR officers read contracts')
        except AccessError:
            pass
        letter = self.Letter.with_user(hr).sudo().create({'employee_id': self.emp_vn.id,
                                                          'template_id': tmpl.id})
        with self.assertRaisesRegex(UserError, 'This letter shows pay. Ask someone who may see pay to prepare it.'):
            letter.with_user(hr).sudo().action_generate()
        pv = self.Studio.with_user(hr).preview(tmpl.id, {}, self.emp_vn.id, 'en_US')
        self.assertIn('You may not see pay', pv['html'])

    # ------------------------------------------------------------ 24
    def test_24_main_wording_in_vietnamese(self):
        self.save(self.tmpl, body='<p>Kính gửi ${employee_name}, ${today_long}</p>', main_lang='vi_VN')
        self.assertEqual(self.tmpl.pbds_main_lang, 'vi_VN')
        opened = self.Studio.open(self.tmpl.id)
        self.assertEqual(opened['main_lang'], 'vi_VN')
        vi_name = [l['name'] for l in opened['langs'] if l['code'] == 'vi_VN'][0]
        self.assertIn('Tiếng Việt', vi_name)
        vi_date = self.Studio._pbds_long_date(fields.Date.today(), 'vi_VN')
        # Indonesian and English readers have no version: the Vietnamese main
        # wording, dates in Vietnamese
        for emp in (self.emp_id, self.emp_b):
            letter = self.letter(emp)
            letter.action_generate()
            self.assertIn('Kính gửi', str(letter.rendered_html))
            self.assertIn(vi_date, str(letter.rendered_html))
            self.assertEqual(letter.lang, 'vi_VN')
        # an English version is now possible and wins for English readers
        self.save(self.tmpl, versions={'en_US': {'subject': 'EN', 'body': '<p>Dear ${employee_name}</p>'}})
        letter = self.letter(self.emp_b)
        letter.action_generate()
        self.assertIn('Dear DEMO Budi B', str(letter.rendered_html))
        # a reader of the main language uses the main wording directly
        letter = self.letter(self.emp_vn)
        letter.action_generate()
        self.assertIn('Kính gửi DEMO Nguyen An', str(letter.rendered_html))
        # preview follows the same order, and says which language it reads in
        pv = self.Studio.preview(self.tmpl.id, {}, self.emp_id.id, 'id_ID')
        self.assertEqual((pv['lang'], pv['read_lang']), ('id_ID', 'vi_VN'))
        self.assertIn(vi_date, pv['html'])
        # put back clears it
        self.Studio.reset(self.tmpl.id)
        self.assertFalse(self.tmpl.pbds_main_lang)
        self.Studio.undo_reset(self.tmpl.id)
        self.assertEqual(self.tmpl.pbds_main_lang, 'vi_VN')
