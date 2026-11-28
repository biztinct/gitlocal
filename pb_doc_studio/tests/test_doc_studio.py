# -*- coding: utf-8 -*-
"""DOCSTUDIO phase F — numbered tests of the handover (§6).

Run: odoo-bin -u pb_doc_studio --test-enable --test-tags /pb_doc_studio
Reports render as HTML in test mode (no PDF engine), which is what is read
here; the PDF itself is checked in the browser walk and the report.
"""
import base64
import json
from string import Template

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_doc_studio.models.doc_common import MAIN_LANG

# 1x1 PNG
PNG = ('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')


def _legacy_html(letter):
    """What the letter engine itself writes (pb_lifecycle letter.py
    action_generate) — the R1 reference."""
    return str(Template(str(letter.template_id.body_html)).safe_substitute(
        letter._placeholder_values()))


@tagged('post_install', '-at_install', 'pb_doc_studio')
class DocStudioCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Lang = env['res.lang']
        for code in ('vi_VN', 'id_ID'):
            if not Lang._lang_get(code):
                Lang._activate_lang(code)
        cls.company_a = env.company
        cls.company_b = env['res.company'].create({'name': 'DEMO Doc Studio B'})
        env.user.company_ids = [(4, cls.company_b.id)]
        cls.indonesia = env.ref('base.id')
        cls.vietnam = env.ref('base.vn')
        Emp = env['hr.employee']
        cls.job = env['hr.job'].create({'name': 'DEMO Planner'})
        cls.dept = env['hr.department'].create({'name': 'DEMO Planning'})
        cls.boss = Emp.create({'name': 'DEMO Boss', 'company_id': cls.company_a.id})
        base = {'company_id': cls.company_a.id}
        cls.emp_vn = Emp.create(dict(base, name='DEMO Nguyen An', job_id=cls.job.id,
                                     job_title='DEMO Planner', department_id=cls.dept.id,
                                     parent_id=cls.boss.id, lang='vi_VN', barcode='DEMO001'))
        cls.emp_id = Emp.create(dict(base, name='DEMO Siti Rahma', job_title='DEMO Analyst',
                                     lang='id_ID'))
        cls.emp_b = Emp.create({'name': 'DEMO Budi B', 'company_id': cls.company_b.id,
                                'lang': 'en_US'})
        cls.emp_b_vn = Emp.create({'name': 'DEMO Bao B', 'company_id': cls.company_b.id,
                                   'lang': 'en_US'})
        if 'payroll_country' in Emp._fields:
            cls.emp_vn.payroll_country = 'VN'
            cls.emp_id.payroll_country = 'ID'
            cls.emp_b.payroll_country = 'ID'
            cls.emp_b_vn.payroll_country = 'VN'
        else:                                          # pragma: no cover
            cls.company_a.country_id = cls.vietnam
        cls.contract = env['hr.contract'].create({
            'name': 'DEMO contract', 'employee_id': cls.emp_vn.id, 'wage': 25000000.0,
            'state': 'open', 'date_start': '2025-03-01', 'date_end': '2027-02-28'})
        cls.Studio = env['pb.doc.studio']
        cls.Letter = env['pb.hr.letter']
        cls.Template = env['pb.letter.template']
        cls.tmpl = cls.Template.create({
            'name': 'DEMO Studio letter', 'letter_type': 'custom', 'company_id': False,
            'subject': 'DEMO heading',
            'body_html': '<p>Dear ${employee_name},</p><p>Welcome.</p>'})

    def letter(self, emp, tmpl=None, **kw):
        vals = {'employee_id': emp.id, 'template_id': (tmpl or self.tmpl).id,
                'company_id': emp.company_id.id}
        vals.update(kw)
        return self.Letter.create(vals)

    def save(self, tmpl, **payload):
        return self.Studio.save(tmpl.id, payload)


@tagged('post_install', '-at_install', 'pb_doc_studio')
class TestDocStudio(DocStudioCase):

    # ------------------------------------------------------------ 1 + 2
    def test_01_install_is_silent(self):
        """No shipped template carries studio data after install."""
        shipped = self.Template.with_context(active_test=False).search([('id', '!=', self.tmpl.id)])
        for t in shipped:
            self.assertFalse(t.pbds_edited or t.pbds_page or t.pbds_rules
                             or t.pbds_version_ids or t.pbds_original_json, t.name)
        self.assertFalse(self.env['ir.cron'].search([('cron_name', 'ilike', 'document studio')]))

    def test_02_untouched_templates_render_byte_identical(self):
        refs = ['pb_lifecycle.letter_template_experience',
                'pb_lifecycle.letter_template_probation_pass',
                'pb_lifecycle.letter_template_incentive',
                'pb_probation.letter_template_probation_extend']
        for xmlid in refs:
            tmpl = self.env.ref(xmlid, raise_if_not_found=False)
            if not tmpl:
                continue
            with self.subTest(xmlid=xmlid):
                self.assertFalse(tmpl._pbds_is_studio())
                letter = self.letter(self.emp_vn, tmpl, context_json=json.dumps({'extra': 'DEMO extra'}))
                expected = _legacy_html(letter)
                letter.action_generate()
                self.assertEqual(str(letter.rendered_html), expected)
                self.assertEqual(letter.state, 'generated')
                self.assertTrue(letter.attachment_id)

    # ------------------------------------------------------------ 3
    def test_03_edited_wording_prints(self):
        self.save(self.tmpl, body='<p>Dear ${employee_name}, DEMO new wording.</p>')
        self.assertTrue(self.tmpl.pbds_edited)
        self.assertTrue(self.tmpl.pbds_page)
        letter = self.letter(self.emp_vn)
        letter.action_generate()
        self.assertIn('DEMO new wording', str(letter.rendered_html))
        self.assertIn('DEMO Nguyen An', str(letter.rendered_html))
        pdf = base64.b64decode(letter.attachment_id.datas).decode('utf-8', 'ignore')
        self.assertIn('DEMO new wording', pdf)
        self.assertIn('pbds-page', pdf)
        self.assertTrue(letter.document_id, 'the letter is filed as before')

    # ------------------------------------------------------------ 4
    def test_04_every_generic_field(self):
        body = ''.join('<p>%s=${%s}</p>' % (k, k) for k in (
            'employee_code', 'legal_name', 'work_email', 'manager_name', 'work_location',
            'country_of_work', 'contract_start', 'contract_end', 'contract_type', 'monthly_pay',
            'company_address', 'today_long', 'joining_date_long'))
        self.save(self.tmpl, body=body)
        letter = self.letter(self.emp_vn, lang='en_US')
        letter.action_generate()
        html = str(letter.rendered_html)
        self.assertIn('employee_code=DEMO001', html)
        self.assertIn('legal_name=DEMO Nguyen An', html)
        self.assertIn('manager_name=DEMO Boss', html)
        self.assertIn('country_of_work=Vietnam', html)
        self.assertIn('contract_start=March 1, 2025', html)
        self.assertIn('contract_end=February 28, 2027', html)
        self.assertIn('25,000,000', html)
        self.assertIn('today_long=%s' % self.Studio._pbds_long_date(fields.Date.today(), 'en_US'), html)
        self.assertNotIn('${', html)
        # a missing value prints nothing; the preview shows an amber chip
        letter2 = self.letter(self.emp_id, lang='en_US')
        letter2.action_generate()
        html2 = str(letter2.rendered_html)
        self.assertIn('<p>manager_name=</p>', html2)
        self.assertIn('<p>contract_start=</p>', html2)
        pv = self.Studio.preview(self.tmpl.id, {'body': body}, self.emp_id.id, 'en_US')
        self.assertIn('pbds-miss', pv['html'])
        self.assertIn('No manager on this person', pv['html'])

    # ------------------------------------------------------------ 5
    def test_05_show_only_when_country(self):
        body = ('<p>All</p><div class="pbds-when pbds-r-r1"><p>DEMO only ID</p></div>'
                '<div class="pbds-when pbds-r-r7"><p>DEMO unknown rule</p></div>')
        rules = {'r1': {'match': 'all', 'lines': [
            {'field': 'country_of_work', 'op': 'is', 'value': str(self.indonesia.id)}]}}
        self.save(self.tmpl, body=body, rules=rules)
        self.assertEqual(set(self.tmpl.pbds_rules), {'r1'})
        l_id = self.letter(self.emp_id)
        l_vn = self.letter(self.emp_vn)
        (l_id | l_vn).action_generate()
        self.assertIn('DEMO only ID', str(l_id.rendered_html))
        self.assertNotIn('DEMO only ID', str(l_vn.rendered_html))
        for letter in (l_id, l_vn):
            self.assertIn('DEMO unknown rule', str(letter.rendered_html))
            self.assertNotIn('pbds-when', str(letter.rendered_html))
        pv = self.Studio.preview(self.tmpl.id, {'body': body, 'rules': rules}, self.emp_vn.id, 'en_US')
        self.assertEqual(pv['hidden'], 1)
        self.assertIn('pbds-ghost', pv['html'])
        sentence = self.Studio._pbds_rule_sentence(rules['r1'])
        self.assertEqual(sentence, 'Only when Country of work is %s' % self.indonesia.name)

    def test_05b_incomplete_rule_refused(self):
        with self.assertRaises(UserError):
            self.save(self.tmpl, body='<div class="pbds-when pbds-r-r1"><p>x</p></div>',
                      rules={'r1': {'match': 'all', 'lines': [{'field': 'country_of_work', 'op': 'is'}]}})
        with self.assertRaises(UserError):
            self.save(self.tmpl, body='<div class="pbds-when pbds-r-r1"><p>x</p></div>',
                      rules={'r1': {'match': 'all', 'lines': [{'field': 'nope', 'op': 'is', 'value': 1}]}})

    # ------------------------------------------------------------ 7
    def test_07_language_versions(self):
        self.save(self.tmpl, body='<p>EN ${employee_name} ${today_long}</p>', versions={
            'vi_VN': {'subject': 'DEMO tiêu đề', 'body': '<p>VI ${employee_name} ${today_long}</p>'}})
        self.assertEqual(self.tmpl.pbds_version_ids.lang, 'vi_VN')
        l_vn = self.letter(self.emp_vn, subject=self.tmpl.subject)
        self.assertEqual(l_vn.lang, 'vi_VN')
        l_vn.action_generate()
        html = str(l_vn.rendered_html)
        self.assertIn('VI DEMO Nguyen An', html)
        self.assertIn(self.Studio._pbds_long_date(fields.Date.today(), 'vi_VN'), html)
        self.assertIn('tháng', html)
        self.assertEqual(l_vn.subject, 'DEMO tiêu đề')
        l_id = self.letter(self.emp_id)
        self.assertEqual(l_id.lang, 'id_ID')
        l_id.action_generate()
        self.assertIn('EN DEMO Siti Rahma', str(l_id.rendered_html))
        # removing a version
        self.save(self.tmpl, versions={'vi_VN': None})
        self.assertFalse(self.tmpl.pbds_version_ids)

    # ------------------------------------------------------------ 8
    def test_08_company_and_country_copies(self):
        builtin = self.env.ref('pb_lifecycle.letter_template_experience')
        res = self.Studio.copy_for(builtin.id, self.company_b.id, [])
        copy_b = self.Template.browse(res['id'])
        self.save(copy_b, body='<p>DEMO company B wording ${employee_name}</p>')
        # a fixed-xmlid caller (probation, contract lifecycle, PIP)
        l_b = self.Letter.sudo().create({'employee_id': self.emp_b.id, 'template_id': builtin.id})
        self.assertEqual(l_b.template_id, copy_b)
        l_a = self.Letter.sudo().create({'employee_id': self.emp_vn.id, 'template_id': builtin.id})
        self.assertEqual(l_a.template_id, builtin)
        l_b.action_generate()
        self.assertIn('DEMO company B wording', str(l_b.rendered_html))
        # a type-only caller (pb_pay `_letter_template`): the search finds the
        # built-in one, the letter becomes the copy for company B
        if 'pb.pay.apply' in self.env and hasattr(self.env['pb.pay.apply'], '_letter_template'):
            picked = self.env['pb.pay.apply']._letter_template('pay_review')
            if picked:
                res_r = self.Studio.copy_for(picked.id, self.company_b.id, [])
                l_r = self.Letter.sudo().create({'employee_id': self.emp_b.id, 'template_id': picked.id})
                self.assertEqual(l_r.template_id.id, res_r['id'])
        # company + country beats company only; country only beats nothing
        res2 = self.Studio.copy_for(builtin.id, self.company_b.id, [self.indonesia.id])
        res3 = self.Studio.copy_for(builtin.id, False, [self.vietnam.id])
        l_b2 = self.Letter.sudo().create({'employee_id': self.emp_b.id, 'template_id': builtin.id})
        self.assertEqual(l_b2.template_id.id, res2['id'])
        l_b3 = self.Letter.sudo().create({'employee_id': self.emp_b_vn.id, 'template_id': builtin.id})
        self.assertEqual(l_b3.template_id, copy_b, 'company copy beats a country-only copy')
        l_a2 = self.Letter.sudo().create({'employee_id': self.emp_vn.id, 'template_id': builtin.id})
        self.assertEqual(l_a2.template_id.id, res3['id'])
        # a copy handed to somebody it is not for falls back to the original
        l_x = self.Letter.sudo().create({'employee_id': self.emp_id.id, 'template_id': copy_b.id})
        self.assertEqual(l_x.template_id, builtin)
        # the same copy twice is refused (opens the existing one)
        again = self.Studio.copy_for(builtin.id, self.company_b.id, [])
        self.assertTrue(again['existing'])
        self.assertEqual(again['id'], copy_b.id)
        # switched off copies are not used
        copy_b.active = False
        Template = self.Template.with_context(active_test=False)
        Template.browse(res2['id']).active = False
        l_b4 = self.Letter.sudo().create({'employee_id': self.emp_b.id, 'template_id': builtin.id})
        self.assertEqual(l_b4.template_id, builtin)

    def test_08b_one_search_per_batch(self):
        builtin = self.env.ref('pb_lifecycle.letter_template_experience')
        self.Studio.copy_for(builtin.id, self.company_b.id, [])
        vals = [{'employee_id': e.id, 'template_id': builtin.id}
                for e in (self.emp_b, self.emp_vn, self.emp_id, self.emp_b_vn)]
        Model = type(self.Template)
        seen = []
        original = Model.search

        def spy(recs, domain, *args, **kwargs):
            if any(isinstance(t, (list, tuple)) and t and t[0] == 'pbds_replaces_id' for t in domain):
                seen.append(domain)
            return original(recs, domain, *args, **kwargs)

        from unittest.mock import patch
        with patch.object(Model, 'search', spy):
            letters = self.Letter.sudo().create(vals)
        self.assertEqual(len(letters), 4)
        self.assertEqual(len(seen), 1, 'one search for copies per batch, not per letter')
        self.assertEqual(letters[0].template_id.company_id, self.company_b)

    # ------------------------------------------------------------ 9
    def test_09_page_design(self):
        self.save(self.tmpl, body='<p>DEMO page</p>', page={
            'letterhead': False, 'margins': 'narrow', 'font': 'classic', 'size': 12,
            'sign': 'image', 'sign_name': 'DEMO Signer', 'sign_title': 'DEMO Director'},
            sign_image={'mime': 'image/png', 'data': PNG})
        self.assertTrue(self.tmpl.pbds_sign_image)
        report = self.Studio._pbds_report(self.tmpl.pbds_page)
        self.assertEqual(report, self.env.ref('pb_doc_studio.action_report_doc_narrow'))
        self.assertEqual(report.paperformat_id.margin_left, 12)
        letter = self.letter(self.emp_vn)
        letter.action_generate()
        html = base64.b64decode(letter.attachment_id.datas).decode('utf-8', 'ignore')
        self.assertIn('DEMO page', html)
        self.assertIn('DejaVu Serif', html)
        self.assertIn('font-size: 12px', html)
        self.assertIn('DEMO Signer', html)
        self.assertIn('DEMO Director', html)
        self.assertIn('data:image/png;base64', html)
        self.assertNotIn('o_report_layout', html, 'no letterhead')
        self.assertNotIn('data-report-margin-top', html, 'plain paper keeps the paper format')
        # with a letterhead the company layout is used
        self.save(self.tmpl, page=dict(self.tmpl.pbds_page, letterhead=True, sign='text'))
        letter2 = self.letter(self.emp_vn)
        letter2.action_generate()
        html2 = base64.b64decode(letter2.attachment_id.datas).decode('utf-8', 'ignore')
        self.assertIn('header', html2)
        # ... with room above the letter for the company header (PDFFIX):
        # narrow 32 mm + 12 mm, header spacing the same
        self.assertIn('data-report-margin-top="44"', html2)
        # PDFFIX-2: the last paragraph and the signatory print in one box;
        # a letter keeps the studio's size (no dpi of its own)
        self.assertIn('class="pbds-keep"', html2)
        tail = html2[html2.index('class="pbds-keep"'):]
        self.assertLess(tail.index('DEMO page'), tail.index('pbds-sign'))
        self.assertNotIn('data-report-dpi', html2)
        self.assertIn('data-report-header-spacing="44"', html2)
        for margins, top in (('normal', 52), ('wide', 58)):
            self.save(self.tmpl, page=dict(self.tmpl.pbds_page, margins=margins))
            res = self.Studio.sample_pdf(self.tmpl.id, {}, self.emp_vn.id, 'en_US')
            self.assertTrue(res['ok'], res)
            sample = base64.b64decode(res['data']).decode('utf-8', 'ignore')
            self.assertIn('data-report-margin-top="%d"' % top, sample, margins)
            self.assertIn('data-report-header-spacing="%d"' % top, sample, margins)
        # contract C3
        styles = {s['key'] for s in self.Studio.page_styles()}
        self.assertEqual(styles, {'letterhead', 'margins', 'font', 'size', 'sign', 'sign_name', 'sign_title'})
        bad = self.Studio._pbds_clean_page({'margins': 'huge', 'font': '<x>', 'size': 99, 'sign': 'x'})
        self.assertEqual((bad['margins'], bad['font'], bad['size'], bad['sign']), ('normal', 'clean', 13, 'text'))

    def test_09b_sample_pdf_files_nothing(self):
        before = self.Letter.search_count([])
        docs = self.env['pb.employee.document'].search_count([])
        res = self.Studio.sample_pdf(self.tmpl.id, {'body': '<p>DEMO sample ${employee_name}</p>'},
                                     self.emp_vn.id, 'en_US')
        self.assertTrue(res['ok'], res)
        self.assertIn('DEMO sample DEMO Nguyen An', base64.b64decode(res['data']).decode('utf-8', 'ignore'))
        self.assertEqual(self.Letter.search_count([]), before)
        self.assertEqual(self.env['pb.employee.document'].search_count([]), docs)

    # ------------------------------------------------------------ 10 + 15
    def test_10_15_own_field_prints_then_is_removed(self):
        if 'pb.form.studio' not in self.env or 'employee_detail' not in self.env['pb.form.studio']._pbfs_hosts():
            self.skipTest('Form builder employee host is not installed')
        FS = self.env['pb.form.studio']
        made = FS.create_field('employee_detail', {'type': 'text', 'label': 'DEMO Shirt size', 'vis': 'hr'})
        name = made['name']
        self.assertTrue(name.startswith('x_'))
        self.emp_vn.invalidate_recordset()
        self.emp_vn.write({name: 'DEMO XL'})
        groups = self.Studio.catalogue(self.tmpl.id)
        own = [g for g in groups if g['key'] == 'own']
        self.assertTrue(own and any(f['key'] == name for f in own[0]['fields']))
        self.save(self.tmpl, body='<p>Size ${%s}.</p>' % name)
        letter = self.letter(self.emp_vn)
        letter.action_generate()
        self.assertIn('Size DEMO XL.', str(letter.rendered_html))
        # rules can use it
        cond = {f['key'] for f in self.Studio.condition_fields()['fields']}
        self.assertIn(name, cond)
        # 15: the field is deleted
        FS.delete_field('hr.employee', name, confirm='DEMO Shirt size')
        self.assertNotIn(name, self.env['hr.employee']._fields)
        card = [c for c in self.Studio.board()['cards'] if c['id'] == self.tmpl.id][0]
        self.assertEqual(card['missing'], 1)
        opened = self.Studio.open(self.tmpl.id)
        self.assertEqual(opened['missing'], [name])
        letter2 = self.letter(self.emp_vn)
        letter2.action_generate()
        self.assertIn('<p>Size .</p>', str(letter2.rendered_html))
        pv = self.Studio.preview(self.tmpl.id, {}, self.emp_vn.id, 'en_US')
        self.assertIn('A field that no longer exists', pv['html'])

    # ------------------------------------------------------------ 11
    def test_11_pay_rail(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': self.company_a.id, 'company_ids': [(6, 0, [self.company_a.id])]}
        writer = Users.create(dict(common, name='DEMO Letters only', login='demo_pbds_letters',
                                   group_ids=[(6, 0, [self.env.ref('pb_lifecycle.group_lifecycle_admin').id,
                                                      self.env.ref('hr.group_hr_user').id])]))
        self.save(self.tmpl, body='<p>Pay ${monthly_pay}</p>')
        # The writer may change letters but may not read contracts (an HR
        # officer without contract rights). Should a module on this database
        # grant it, a rule only the writer carries takes it away again.
        try:
            self.env['hr.contract'].with_user(writer).browse(self.contract.id).check_access('read')
            readable = True
        except AccessError:
            readable = False
        if readable:
            group = self.env['res.groups'].create({'name': 'DEMO no contracts'})
            writer.group_ids = [(4, group.id)]
            self.env['ir.rule'].create({
                'name': 'DEMO no contracts', 'model_id': self.env['ir.model']._get_id('hr.contract'),
                'domain_force': "[(0, '=', 1)]", 'group_ids': [(6, 0, [group.id])]})
            self.env.invalidate_all()
        Studio = self.Studio.with_user(writer)
        pv = Studio.preview(self.tmpl.id, {}, self.emp_vn.id, 'en_US')
        self.assertIn('You may not see pay', pv['html'])
        self.assertNotIn('25,000,000', pv['html'])
        letter = self.Letter.with_user(writer).sudo().create({
            'employee_id': self.emp_vn.id, 'template_id': self.tmpl.id})
        with self.assertRaisesRegex(UserError, 'This letter shows pay'):
            letter.with_user(writer).sudo().action_generate()
        res = Studio.sample_pdf(self.tmpl.id, {}, self.emp_vn.id, 'en_US')
        self.assertFalse(res['ok'])
        # somebody who may see pay gets the figure
        pv2 = self.Studio.preview(self.tmpl.id, {}, self.emp_vn.id, 'en_US')
        self.assertIn('25,000,000', pv2['html'])

    # ------------------------------------------------------------ 12
    def test_12_reset_and_undo(self):
        tmpl = self.env.ref('pb_lifecycle.letter_template_experience')
        before = self.letter(self.emp_vn, tmpl)
        before.action_generate()
        golden = str(before.rendered_html)
        self.env.cr.execute('SELECT body_html::text, subject::text FROM pb_letter_template WHERE id=%s', (tmpl.id,))
        raw_before = self.env.cr.fetchone()
        self.save(tmpl, body='<p>DEMO changed</p>', page={'margins': 'wide'},
                  versions={'vi_VN': {'subject': 'x', 'body': '<p>VI</p>'}})
        self.assertTrue(tmpl.pbds_edited)
        self.Studio.reset(tmpl.id)
        self.assertFalse(tmpl._pbds_is_studio())
        self.env.cr.execute('SELECT body_html::text, subject::text FROM pb_letter_template WHERE id=%s', (tmpl.id,))
        self.assertEqual(self.env.cr.fetchone(), raw_before)
        after = self.letter(self.emp_vn, tmpl)
        after.action_generate()
        self.assertEqual(str(after.rendered_html), golden)
        # one step of undo
        self.Studio.undo_reset(tmpl.id)
        self.assertTrue(tmpl.pbds_edited)
        self.assertIn('DEMO changed', str(tmpl.with_context(lang=MAIN_LANG).body_html))
        self.assertEqual(tmpl.pbds_version_ids.lang, 'vi_VN')
        self.assertEqual(tmpl.pbds_page['margins'], 'wide')
        with self.assertRaises(UserError):
            self.Studio.undo_reset(tmpl.id)

    # ------------------------------------------------------------ 13
    def test_13_refused_without_the_right(self):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': self.company_a.id, 'company_ids': [(6, 0, [self.company_a.id])]}
        manager = Users.create(dict(common, name='DEMO Letter maker', login='demo_pbds_mgr',
                                    group_ids=[(6, 0, [self.env.ref('pb_lifecycle.group_lifecycle_manager').id,
                                                       self.env.ref('hr.group_hr_user').id])]))
        S = self.Studio.with_user(manager)
        calls = [
            lambda: S.board(), lambda: S.open(self.tmpl.id), lambda: S.save(self.tmpl.id, {}),
            lambda: S.copy_for(self.tmpl.id, False, [self.vietnam.id]), lambda: S.reset(self.tmpl.id),
            lambda: S.undo_reset(self.tmpl.id), lambda: S.set_active(self.tmpl.id, False),
            lambda: S.create_blank('other'), lambda: S.preview(self.tmpl.id, {}, self.emp_vn.id),
            lambda: S.sample_pdf(self.tmpl.id, {}, self.emp_vn.id), lambda: S.people(''),
            lambda: S.catalogue(self.tmpl.id), lambda: S.condition_fields(),
            lambda: S.upload_image(self.tmpl.id, {'mime': 'image/png', 'data': PNG}),
        ]
        for i, call in enumerate(calls):
            with self.subTest(call=i), self.assertRaises(AccessError):
                call()
        # the administrator gets in
        self.assertTrue(self.Studio.board()['cards'])
        # the Settings card asks for exactly these permissions
        from odoo.modules.module import get_module_path
        import os
        src = open(os.path.join(get_module_path('pb_doc_studio'), 'static/src/js/settings_card.js')).read()
        self.assertIn('"pb_lifecycle.group_lifecycle_admin"', src)
        gates = self.env['pb.settings'].with_user(manager).resolve_gates([
            {'key': 'documents', 'groups': ['pb_lifecycle.group_lifecycle_admin', 'base.group_system'],
             'cards': [{'id': 'doc_studio', 'tag': 'pb_doc_studio'}]}])
        self.assertFalse(gates['categories']['documents'])

    # ------------------------------------------------------------ 14
    def test_14_scripts_are_inert(self):
        self.emp_vn.name = 'DEMO <img src=x onerror=alert(1)> An'
        body = ('<p>Hi ${employee_name}</p><script>alert(1)</script>'
                '<img src="x" onerror="alert(2)"><p onclick="alert(3)">x</p>')
        self.save(self.tmpl, body=body)
        stored = str(self.tmpl.with_context(lang=MAIN_LANG).body_html)
        for bad in ('<script', 'onerror', 'onclick'):
            self.assertNotIn(bad, stored)
        letter = self.letter(self.emp_vn)
        letter.action_generate()
        html = str(letter.rendered_html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;img src=x onerror=alert(1)&gt;', html)
        pv = self.Studio.preview(self.tmpl.id, {'body': body}, self.emp_vn.id, 'en_US')
        self.assertNotIn('<script', pv['html'].split('<style>')[0] + pv['html'].split('</style>')[-1])
        self.assertNotRegex(pv['html'], r'<[^>]*\bon(error|click)=')
        self.assertNotIn('<img src=x', pv['html'])

    # ------------------------------------------------------------ misc rails
    def test_r7_pictures_are_files(self):
        res = self.Studio.upload_image(self.tmpl.id, {'name': 'a.png', 'mime': 'image/png', 'data': PNG})
        self.assertTrue(res['ok'])
        self.assertIn('/web/image/ir.attachment/', res['url'])
        bad = self.Studio.upload_image(self.tmpl.id, {'name': 'a.png', 'mime': 'image/png',
                                                      'data': base64.b64encode(b'GIF89a....').decode()})
        self.assertFalse(bad['ok'])
        # a pasted picture becomes a file too
        self.save(self.tmpl, body='<p><img src="data:image/png;base64,%s"></p>' % PNG)
        stored = str(self.tmpl.with_context(lang=MAIN_LANG).body_html)
        self.assertNotIn('data:image', stored)
        self.assertIn('/web/image/ir.attachment/', stored)
        # and the PDF carries it inline (the PDF engine fetches nothing)
        letter = self.letter(self.emp_vn)
        letter.action_generate()
        html = base64.b64decode(letter.attachment_id.datas).decode('utf-8', 'ignore')
        self.assertIn('data:image/png;base64', html)

    def test_r7_large_body_saves_fast(self):
        import time
        para = '<p>%s ${employee_name}</p>' % ('Lorem ipsum dolor sit amet. ' * 6)
        body = para * 1100
        self.assertGreater(len(body), 190 * 1024)
        self.save(self.tmpl, body='<p>warm</p>')       # first save writes the snapshot
        start = time.time()
        self.save(self.tmpl, body=body)
        self.assertLess(time.time() - start, 1.0)

    def test_board_open_and_new(self):
        board = self.Studio.board()
        kinds = {c['kind'] for c in board['cards']}
        self.assertTrue(kinds <= {k['key'] for k in board['kinds']})
        # Offer letters: out of the gallery, or (phase A1 bridge) only under "Hiring".
        self.assertFalse([c for c in board['cards'] if c['type_label'] == 'Offer letter' and c['kind'] != 'hiring'])
        made = self.Studio.create_blank('joining', 'DEMO Welcome')
        opened = self.Studio.open(made['id'])
        self.assertEqual(opened['kind'], 'joining')
        self.assertIn('${employee_name}', opened['body'])
        self.assertTrue(opened['person'])
        keys = {f['key'] for g in opened['catalogue'] for f in g['fields']}
        self.assertTrue({'employee_name', 'monthly_pay', 'today_long', 'company_address'} <= keys)
        self.Studio.set_active(made['id'], False)
        self.assertFalse(self.Template.browse(made['id']).active)
        people = self.Studio.people('DEMO Nguyen')
        self.assertEqual([p['id'] for p in people], [self.emp_vn.id])

    def test_certificates_keep_their_language(self):
        tmpl = self.env.ref('pb_me_letters.letter_template_employment_cert', raise_if_not_found=False)
        if not tmpl:
            self.skipTest('certificates not installed')
        letter = self.Letter.sudo().with_context(lang='id_ID').create({
            'employee_id': self.emp_vn.id, 'template_id': tmpl.id})
        self.assertEqual(letter.lang, 'id_ID')

    # ------------------------------------------------------------ CZ-3
    def test_cz_03_name_box_follows_the_screen_language(self):
        """DOCSTUDIO close Z item 3: the designer's name box shows the name
        in the screen's language, like the gallery card; saving with the box
        untouched writes no name; a new name lands in the language it was
        typed in when the document has a name of its own there."""
        tmpl = self.Template.create({
            'name': 'DEMO CZ name', 'letter_type': 'custom', 'company_id': False,
            'body_html': '<p>DEMO ${employee_name}</p>'})
        tmpl.with_context(lang='vi_VN').name = 'DEMO CZ tên'
        Vi = self.Studio.with_context(lang='vi_VN')
        opened = Vi.open(tmpl.id)
        self.assertEqual(opened['name'], 'DEMO CZ tên')
        card = Vi._pbds_card(tmpl.with_context(lang='vi_VN'))
        self.assertEqual(card['name'], opened['name'])
        # untouched box: nothing written in either language
        saved = Vi.save(tmpl.id, {'name': opened['name'], 'body': opened['body']})
        self.assertEqual(saved['name'], 'DEMO CZ tên')
        tmpl.invalidate_recordset(['name'])
        self.assertEqual(tmpl.with_context(lang='en_US').name, 'DEMO CZ name')
        self.assertEqual(tmpl.with_context(lang='vi_VN').name, 'DEMO CZ tên')
        # renamed on a Vietnamese screen: only the Vietnamese name changes
        Vi.save(tmpl.id, {'name': 'DEMO CZ tên mới', 'body': opened['body']})
        tmpl.invalidate_recordset(['name'])
        self.assertEqual(tmpl.with_context(lang='vi_VN').name, 'DEMO CZ tên mới')
        self.assertEqual(tmpl.with_context(lang='en_US').name, 'DEMO CZ name')
        # renamed on an English screen: the main name, as before
        self.Studio.with_context(lang='en_US').save(tmpl.id, {'name': 'DEMO CZ new', 'body': opened['body']})
        tmpl.invalidate_recordset(['name'])
        self.assertEqual(tmpl.with_context(lang='en_US').name, 'DEMO CZ new')
        self.assertEqual(tmpl.with_context(lang='vi_VN').name, 'DEMO CZ tên mới')
        # no name of its own in Indonesian: a rename there renames the main name
        Id = self.Studio.with_context(lang='id_ID')
        self.assertEqual(Id.open(tmpl.id)['name'], 'DEMO CZ new')
        Id.save(tmpl.id, {'name': 'DEMO CZ renamed', 'body': opened['body']})
        tmpl.invalidate_recordset(['name'])
        self.assertEqual(tmpl.with_context(lang='en_US').name, 'DEMO CZ renamed')
        self.assertEqual(tmpl.with_context(lang='id_ID').name, 'DEMO CZ renamed')
        # "Put back the built-in wording" still restores every language
        self.Studio.reset(tmpl.id)
        tmpl.invalidate_recordset(['name'])
        self.assertEqual(tmpl.with_context(lang='en_US').name, 'DEMO CZ name')
        self.assertEqual(tmpl.with_context(lang='vi_VN').name, 'DEMO CZ tên')
