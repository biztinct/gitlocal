# -*- coding: utf-8 -*-
"""DOCSTUDIO phase A1 — offer letters in the Document studio (numbered tests).

Run: odoo-bin -u pb_doc_studio_hiring --test-enable --test-tags /pb_doc_studio_hiring
Reports render as HTML in test mode (no PDF engine): that HTML is what is
read here; the true PDF is checked in the browser walk and the report.
"""
import base64
from datetime import timedelta
from string import Template

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_doc_studio.models.doc_common import MAIN_LANG


@tagged('post_install', '-at_install', 'pb_doc_studio_hiring')
class OfferStudioCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Lang = env['res.lang']
        for code in ('vi_VN', 'id_ID'):
            if not Lang._lang_get(code):
                Lang._activate_lang(code)
        cls.vietnam = env.ref('base.vn')
        cls.indonesia = env.ref('base.id')
        cls.company = env.company
        cls.company.country_id = cls.vietnam
        cls.company_b = env['res.company'].create({'name': 'DEMO A1 Company B'})
        env.user.company_ids = [(4, cls.company_b.id)]
        Emp = env['hr.employee']
        cls.boss = Emp.create({'name': 'DEMO A1 Boss', 'company_id': cls.company.id})
        cls.dept = env['hr.department'].create({'name': 'DEMO A1 Finance', 'company_id': cls.company.id})
        cls.ctype = env['hr.contract.type'].create({'name': 'DEMO A1 Fixed term'})
        cls.job = env['hr.job'].create({'name': 'DEMO A1 Analyst', 'company_id': cls.company.id,
                                        'department_id': cls.dept.id,
                                        'contract_type_id': cls.ctype.id})
        cls.app = env['hr.applicant'].create({
            'partner_name': 'DEMO A1 Candidate', 'email_from': 'demo.a1.candidate@example.com',
            'job_id': cls.job.id, 'company_id': cls.company.id})
        cls.req = env['pb.hiring.requisition'].sudo().create({
            'title': 'DEMO A1 Analyst', 'department_id': cls.dept.id, 'company_id': cls.company.id,
            'requested_by_id': cls.boss.id, 'reporting_manager_id': cls.boss.id, 'headcount': 1,
            'budget_cost': 100.0, 'requirements': 'Able to do the job.', 'job_id': cls.job.id,
            'opened_on': fields.Date.today() - timedelta(days=10), 'state': 'open',
            'request_state': 'agreed', 'selected_applicant_id': cls.app.id,
            'country_id': cls.vietnam.id, 'location': 'DEMO Ha Noi'})
        cls.app.sudo().write({'pb_requisition_id': cls.req.id})
        bgv = env['pb.hiring.bgv'].open_for(cls.req.id)
        bgv.item_ids.sudo().write({'result': 'ok'})
        cls.offer = env['pb.hiring.offer'].draft_for(cls.req.id)
        for name, kind, amount, period in (
                ('Basic pay', 'earning', 25000000.0, 'monthly'),
                ('Allowance', 'earning', 2000000.0, 'monthly'),
                ('Sign-on bonus', 'bonus', 10000000.0, 'one_time')):
            cls.offer.action_add_line({'name': name, 'kind': kind, 'amount': amount, 'period': period})
        cls.offer.invalidate_recordset(['monthly_total', 'annual_total'])
        cls.generic = env.ref('pb_hiring.letter_template_offer_generic')
        cls.vn_tmpl = env.ref('pb_hiring.letter_template_offer_vietnam')
        cls.Studio = env['pb.doc.studio']
        Users = env['res.users'].with_context(no_reset_password=True)
        common = {'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])]}
        cls.recruiter = Users.create(dict(common, name='DEMO A1 Recruiter', login='demo_a1_recruiter',
                                          group_ids=[(6, 0, [env.ref('base.group_user').id,
                                                             env.ref('pb_hiring.group_hiring_user').id])]))
        cls.letters_admin = Users.create(dict(common, name='DEMO A1 Letters admin', login='demo_a1_letters',
                                              group_ids=[(6, 0, [env.ref('base.group_user').id,
                                                                 env.ref('pb_lifecycle.group_lifecycle_admin').id])]))

    def offer_for(self, template):
        self.offer.sudo().write({'letter_template_id': template.id})
        return self.offer

    def save(self, template, **payload):
        return self.Studio.save(template.id, payload)

    def make_studio_copy(self, template, body, company=None, countries=None):
        res = self.Studio.copy_for(template.id, (company or self.company).id, [c.id for c in (countries or [])])
        copy = self.env['pb.letter.template'].browse(res['id'])
        self.save(copy, body=body)
        return copy


@tagged('post_install', '-at_install', 'pb_doc_studio_hiring')
class TestOfferStudio(OfferStudioCase):

    # ------------------------------------------------------------ A1-01
    def test_a1_01_install_is_silent(self):
        """Nothing written to the shipped offer letters; no job; offers keep
        their wording choice."""
        for t in (self.generic, self.vn_tmpl):
            self.assertFalse(t._pbds_is_studio(), t.name)
            self.assertFalse(t.pbds_original_json)
        self.assertFalse(self.env['ir.cron'].search([('cron_name', 'ilike', 'offer letter')]))
        self.assertTrue(self.env['ir.module.module'].search(
            [('name', '=', 'pb_doc_studio_hiring'), ('state', '=', 'installed')]))

    # ------------------------------------------------------------ A1-02
    def test_a1_02_untouched_offer_letters_are_byte_identical(self):
        """R1: both shipped offer letters print exactly as Hiring prints them
        (Hiring's own formula, Hiring's own report)."""
        for tmpl in (self.generic, self.vn_tmpl):
            with self.subTest(template=tmpl.name):
                offer = self.offer_for(tmpl)
                values = dict(offer._placeholder_values())
                values['lines'] = str(offer._lines_table())
                expected = Template(str(tmpl.body_html)).safe_substitute(values)
                offer.action_prepare_letter()
                self.assertEqual(str(offer.rendered_html), expected)
                self.assertFalse(offer.pbds_lang, 'Hiring\'s own path stores no studio language')
                html = offer.attachment_id.raw.decode('utf-8', 'ignore')
                self.assertNotIn('pbds-page', html, 'Hiring\'s own report printed it')
                self.assertIn('Signature and date', html)

    # ------------------------------------------------------------ A1-04
    def test_a1_04_edited_wording_prints_from_hiring(self):
        self.save(self.generic, body='<p>Dear ${candidate_name}, DEMO studio offer for ${job_title}.</p>'
                                     '<p>${lines}</p><p>From ${start_date}, ${monthly_total} a month.</p>')
        offer = self.offer_for(self.generic)
        offer.with_user(self.recruiter).with_context(
            allowed_company_ids=[self.company.id]).action_prepare_letter()
        html = str(offer.rendered_html)
        self.assertIn('DEMO studio offer for DEMO A1 Analyst', html)
        self.assertIn('DEMO A1 Candidate', html)
        self.assertIn('<table class="pbdh-lines"', html)
        self.assertNotIn('<p><table', html, 'the pay lines table replaces its paragraph')
        self.assertIn('Sign-on bonus', html)
        self.assertNotIn('${', html)
        pdf = offer.attachment_id.raw.decode('utf-8', 'ignore')
        self.assertIn('pbds-page', pdf)
        self.assertIn('DEMO studio offer', pdf)
        self.assertIn('Signature and date', pdf, 'the candidate still signs the copy they send back')
        self.assertEqual(offer.pbds_lang, offer._pbds_offer_lang())

    # ------------------------------------------------------------ A1-05
    def test_a1_05_rule_by_country(self):
        rules = {'r1': {'match': 'all', 'lines': [
            {'field': 'country_of_work', 'op': 'is', 'value': str(self.vietnam.id)}]}}
        self.save(self.generic, rules=rules,
                  body='<p>DEMO always.</p><div class="pbds-when pbds-r-r1"><p>DEMO only in Vietnam.</p></div>')
        self.assertEqual(self.generic.pbds_rules, rules)
        offer = self.offer_for(self.generic)
        offer.action_prepare_letter()
        self.assertIn('DEMO only in Vietnam.', str(offer.rendered_html))
        self.req.sudo().country_id = self.indonesia
        offer.action_prepare_letter()
        self.assertNotIn('DEMO only in Vietnam.', str(offer.rendered_html))
        self.assertIn('DEMO always.', str(offer.rendered_html))
        # conditions an offer can use, in the designer
        keys = [f['key'] for f in self.Studio.with_context(pbds_doc_kind='offer').condition_fields()['fields']]
        self.assertEqual(keys, ['country_of_work', 'company', 'department', 'job', 'contract_type'])
        # employment type = the job's employment type
        rules2 = {'r2': {'match': 'all', 'lines': [
            {'field': 'contract_type', 'op': 'is', 'value': str(self.ctype.id)}]}}
        self.save(self.generic, rules=rules2,
                  body='<p>x</p><div class="pbds-when pbds-r-r2"><p>DEMO fixed term clause.</p></div>')
        offer.action_prepare_letter()
        self.assertIn('DEMO fixed term clause.', str(offer.rendered_html))

    # ------------------------------------------------------------ A1-06
    def test_a1_06_offer_language(self):
        self.save(self.generic, body='<p>DEMO English ${candidate_name}</p>',
                  versions={'vi_VN': {'subject': 'DEMO Thư mời', 'body': '<p>DEMO Kính gửi ${candidate_name}</p><p>${lines}</p>'}})
        offer = self.offer_for(self.generic)
        self.app.sudo().pb_lang = 'vi_VN'
        self.assertEqual(offer._pbds_offer_lang(), 'vi_VN')
        offer.action_prepare_letter()
        self.assertIn('DEMO Kính gửi DEMO A1 Candidate', str(offer.rendered_html))
        self.assertEqual(offer.pbds_lang, 'vi_VN')
        self.assertIn('Khoản lương', str(offer.rendered_html),
                      'the pay table is written in the letter language')
        self.assertIn('DEMO Thư mời', offer.attachment_id.raw.decode('utf-8', 'ignore'))
        # language unknown -> the company's language
        self.app.sudo().pb_lang = False
        self.app.partner_id.sudo().lang = False
        self.company.partner_id.lang = 'id_ID'
        self.assertEqual(offer._pbds_offer_lang(), 'id_ID')
        offer.action_prepare_letter()
        self.assertIn('DEMO English', str(offer.rendered_html))
        self.assertEqual(offer.pbds_lang, 'id_ID')

    # ------------------------------------------------------------ A1-07
    def test_a1_07_page_design_in_the_pdf(self):
        self.save(self.generic, body='<p>DEMO page ${candidate_name}</p>',
                  page={'letterhead': False, 'margins': 'narrow', 'font': 'classic', 'size': 12,
                        'sign': 'text', 'sign_name': 'DEMO Signer', 'sign_title': 'DEMO Head of people'})
        page = self.generic.pbds_page
        report = self.Studio._pbds_report(page)
        self.assertEqual(report, self.env.ref('pb_doc_studio.action_report_doc_narrow'))
        self.assertEqual(report.paperformat_id.margin_left, 12)
        offer = self.offer_for(self.generic)
        offer.action_prepare_letter()
        pdf = offer.attachment_id.raw.decode('utf-8', 'ignore')
        self.assertIn('pbds-pdf', pdf)
        self.assertIn('DejaVu Serif', pdf)
        self.assertIn('font-size: 12px', pdf)
        self.assertIn('DEMO Signer', pdf)
        self.assertIn('DEMO Head of people', pdf)
        layout = 'o_company_%s_layout' % self.company.id
        self.assertNotIn(layout, pdf, 'no company letterhead (plain paper)')
        # one signature block of the company, then the candidate's line
        self.assertEqual(pdf.count('DEMO Signer'), 1)
        self.assertLess(pdf.index('DEMO Signer'), pdf.index('Signature and date'))
        self.assertTrue(offer.attachment_id.name.endswith('.pdf'))
        # letterhead on again -> the company's own header and footer
        self.save(self.generic, page=dict(page, letterhead=True))
        offer.action_prepare_letter()
        self.assertIn(layout, offer.attachment_id.raw.decode('utf-8', 'ignore'))

    # ------------------------------------------------------------ A1-08
    def test_a1_08_company_copy_wins_even_over_a_cost_profile(self):
        copy = self.make_studio_copy(self.generic, '<p>DEMO company copy for ${candidate_name}</p>')
        other = self.make_studio_copy(self.generic, '<p>DEMO other company</p>', company=self.company_b)
        # A country offer setup naming the ORIGINAL letter (offer_cost.py).
        config = self.env['hr.formula.config'].create({
            'name': 'DEMO A1 cost', 'code': 'DEMO_A1_COST', 'company_id': self.company.id,
            'country_code': 'VN'})
        gross = self.env['hr.formula.rule'].create({
            'config_id': config.id, 'name': 'Monthly gross', 'code': 'DEMOAONEGROSS',
            'column_type': 'input', 'sequence': 1})
        profile = self.env['pb.hiring.cost.profile'].create({
            'name': 'DEMO A1 profile', 'company_id': self.company.id, 'country_id': config.country_id.id,
            'config_id': config.id, 'gross_input_id': gross.id,
            'effective_from': fields.Date.today() - timedelta(days=1),
            'letter_template_id': self.generic.id})
        offer = self.offer
        offer.sudo().write({'letter_template_id': self.vn_tmpl.id})
        offer.action_country_offer_setup()
        self.assertEqual(offer.pb_cost_profile_id, profile)
        self.assertEqual(offer.letter_template_id, self.generic, 'the profile names the original')
        self.assertEqual(offer._pbds_offer_template(), copy)
        offer.action_prepare_letter()
        html = str(offer.rendered_html)
        self.assertIn('DEMO company copy for DEMO A1 Candidate', html)
        self.assertNotIn('DEMO other company', html)
        self.assertIn(self.company.name, offer.pbds_wording_note)
        row = self.env['pb.hiring']._offer_row(offer, full=True)
        self.assertEqual(row['template'], copy.name)
        self.assertTrue(row['template_note'])
        # the copy switched off -> the original prints again (Hiring's own path)
        copy.active = False
        offer.action_prepare_letter()
        self.assertNotIn('DEMO company copy', str(offer.rendered_html))
        self.assertIn('We are delighted to offer you', str(offer.rendered_html))
        # a copy for a country beats the original, a company+country copy beats both
        copy.active = True
        vn_copy = self.make_studio_copy(self.generic, '<p>DEMO company and Vietnam</p>',
                                        countries=[self.vietnam])
        self.assertEqual(offer._pbds_offer_template(), vn_copy)

    # ------------------------------------------------------------ A1-11
    def test_a1_11_no_hiring_access_no_offer_preview(self):
        studio = self.Studio.with_user(self.letters_admin).with_context(
            allowed_company_ids=[self.company.id])
        # The letters admin may open and change the offer letter's wording...
        doc = studio.open(self.generic.id)
        self.assertEqual(doc['preview_kind'], 'offer')
        self.assertFalse(doc['offer_access'])
        self.assertFalse(doc['person'], 'no offer to preview with')
        # ...but sees no offer, and cannot preview with one.
        self.assertEqual(studio.offers(''), [])
        with self.assertRaises(AccessError):
            studio.preview(self.generic.id, {}, self.offer.id, False)
        with self.assertRaises(AccessError):
            studio.sample_pdf(self.generic.id, {}, self.offer.id, False)
        # A recruiter without letter rights cannot use the studio at all.
        with self.assertRaises(AccessError):
            self.Studio.with_user(self.recruiter).offers('')

    # ------------------------------------------------------------ A1-13
    def test_a1_13_gallery_and_fields(self):
        board = self.Studio.board()
        self.assertEqual(board['kinds'][0]['key'], 'hiring')
        cards = {c['id']: c for c in board['cards']}
        for tmpl in (self.generic, self.vn_tmpl):
            card = cards[tmpl.id]
            self.assertEqual(card['kind'], 'hiring')
            self.assertTrue(card['prints_for'])
            self.assertEqual(card['missing'], 0)
        self.assertEqual(board['cards'][0]['kind'], 'hiring', 'the Hiring group comes first')
        before = cards[self.generic.id]['uses']           # other offers of the database
        self.offer_for(self.generic)
        cards = {c['id']: c for c in self.Studio.board()['cards']}
        self.assertEqual(cards[self.generic.id]['uses'], before + 1)
        self.assertIn(str(before + 1) if before else '1 offer', cards[self.generic.id]['uses_text'])
        doc = self.Studio.open(self.generic.id)
        keys = [f['key'] for g in doc['catalogue'] for f in g['fields']]
        self.assertEqual(keys, ['candidate_name', 'job_title', 'department', 'location', 'manager', 'company',
                                'monthly_total', 'annual_total', 'currency', 'lines', 'start_date', 'date'])
        block = [f for g in doc['catalogue'] for f in g['fields'] if f['key'] == 'lines'][0]
        self.assertTrue(block['block'])
        self.assertEqual(doc['preview_kind'], 'offer')
        self.assertEqual(doc['person']['id'], self.offer.id)
        # a letter keeps people
        exp = self.env.ref('pb_lifecycle.letter_template_experience')
        self.assertEqual(self.Studio.open(exp.id)['preview_kind'], 'person')
        # a new document under Hiring is an offer letter
        res = self.Studio.create_blank('hiring', 'DEMO A1 new offer')
        new = self.env['pb.letter.template'].browse(res['id'])
        self.assertEqual(new.letter_type, 'offer')
        self.assertEqual(new.pbds_kind, 'hiring')
        self.assertIn('${candidate_name}', new.with_context(lang=MAIN_LANG).body_html)
        self.assertIn('${candidate_name}', new.pbds_original_json['body_html']['en_US'])

    # ------------------------------------------------------------ A1-14
    def test_a1_14_preview_with_a_real_offer(self):
        draft = {'body': '<p>DEMO preview ${candidate_name} ${unknown_key}</p><p>${lines}</p>'
                         '<div class="pbds-when pbds-r-r1"><p>DEMO hidden.</p></div>',
                 'rules': {'r1': {'match': 'all', 'lines': [
                     {'field': 'country_of_work', 'op': 'is', 'value': str(self.indonesia.id)}]}}}
        res = self.Studio.preview(self.generic.id, draft, self.offer.id, 'en_US')
        self.assertIn('DEMO A1 Candidate', res['html'])
        self.assertIn('pbdh-lines', res['html'])
        self.assertEqual(res['hidden'], 1)
        self.assertIn('Signature and date', res['html'])
        self.assertEqual(res['values']['candidate_name'], 'DEMO A1 Candidate')
        self.assertEqual(res['values']['lines'], '3 lines')
        self.assertTrue(any(m['key'] == 'unknown_key' for m in res['missing']))
        self.assertNotIn('${', res['html'])
        # nothing was stored on the offer
        self.assertFalse(self.offer.rendered_html)
        pdf = self.Studio.sample_pdf(self.generic.id, draft, self.offer.id, 'en_US')
        self.assertTrue(pdf['ok'])
        self.assertIn('DEMO preview', base64.b64decode(pdf['data']).decode('utf-8', 'ignore'))
        self.assertFalse(self.offer.attachment_id)
        # the offer list for "preview with"
        rows = self.Studio.offers('DEMO A1 Cand')
        self.assertEqual([r['id'] for r in rows], [self.offer.id])
        self.assertEqual(rows[0]['kind'], 'offer')
        # an untouched offer letter keeps Hiring's own path after a preview
        self.assertFalse(self.generic._pbds_is_studio())

    # ------------------------------------------------------------ A1-15
    def test_a1_15_hostile_values_are_inert(self):
        self.app.sudo().partner_name = 'DEMO <img src=x onerror=alert(1)>'
        self.offer.invalidate_recordset(['candidate_name'])
        self.save(self.generic, body='<p>Dear ${candidate_name}</p><script>alert(2)</script>')
        self.assertNotIn('<script', self.generic.with_context(lang=MAIN_LANG).body_html)
        offer = self.offer_for(self.generic)
        offer.action_prepare_letter()
        html = str(offer.rendered_html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;img', html)
        res = self.Studio.preview(self.generic.id, {}, offer.id, 'en_US')
        self.assertNotIn('<img src=x', res['html'])

    # ------------------------------------------------------------ A1-16
    def test_a1_16_prepare_as_the_recruiter_not_sudo(self):
        """Hiring's R89: the studio PDF is rendered as the person preparing
        it. A recruiter with no letter rights prepares a studio offer."""
        self.save(self.generic, body='<p>DEMO recruiter ${candidate_name}</p>')
        offer = self.offer_for(self.generic).with_user(self.recruiter).with_context(
            allowed_company_ids=[self.company.id])
        seen = []
        Report = type(self.env['ir.actions.report'])
        orig = Report._render_qweb_pdf

        def spy(report, report_ref, res_ids=None, data=None):
            seen.append((report.env.uid, report.env.su))
            return orig(report, report_ref, res_ids=res_ids, data=data)

        Report._render_qweb_pdf = spy
        try:
            offer.action_prepare_letter()
        finally:
            Report._render_qweb_pdf = orig
        self.assertEqual(seen, [(self.recruiter.id, False)])
        self.assertIn('DEMO recruiter', str(offer.sudo().rendered_html))

    # ------------------------------------------------------------ A1-18
    def test_a1_18_language_rule(self):
        """Owner ruling: unknown → the hiring company's language (the contact
        card does not count); the recruiter's explicit choice wins."""
        self.save(self.generic, body='<p>DEMO main ${candidate_name}</p>',
                  versions={'vi_VN': {'subject': 'DEMO vi', 'body': '<p>DEMO tiếng Việt ${candidate_name}</p>'},
                            'id_ID': {'subject': 'DEMO id', 'body': '<p>DEMO bahasa ${candidate_name}</p>'}})
        offer = self.offer_for(self.generic)
        self.app.sudo().pb_lang = False
        self.app.partner_id.sudo().lang = 'id_ID'          # the contact card: ignored
        self.company.partner_id.lang = 'vi_VN'
        self.assertFalse(offer._pbds_known_lang())
        self.assertEqual(offer._pbds_offer_lang(), 'vi_VN')
        offer.action_prepare_letter()
        self.assertIn('DEMO tiếng Việt', str(offer.rendered_html))
        # the language they applied in is known
        self.app.sudo().pb_lang = 'id_ID'
        self.assertEqual(offer._pbds_offer_lang(), 'id_ID')
        # the recruiter's choice wins over both, through the board's door
        Hiring = self.env['pb.hiring'].with_user(self.recruiter).with_context(
            allowed_company_ids=[self.company.id])
        row = Hiring._offer_row(offer.with_user(self.recruiter), full=True)
        self.assertEqual(row['letter_lang'], '')
        self.assertTrue(row['letter_lang_open'])
        self.assertIn('en_US', [l['code'] for l in row['letter_langs']])
        res = Hiring.act('offer_letter_lang', {'offer_id': offer.id, 'lang': 'en_US'})
        self.assertIn('English', res['note'])
        self.assertEqual(offer.pbds_letter_lang, 'en_US')
        self.assertEqual(offer._pbds_offer_lang(), 'en_US')
        offer.action_prepare_letter()
        self.assertIn('DEMO main', str(offer.rendered_html))
        self.assertEqual(offer.pbds_lang, 'en_US')
        # back to automatic
        Hiring.act('offer_letter_lang', {'offer_id': offer.id, 'lang': False})
        self.assertEqual(offer._pbds_offer_lang(), 'id_ID')
        with self.assertRaises(UserError):
            Hiring.act('offer_letter_lang', {'offer_id': offer.id, 'lang': 'xx_XX'})
        # once the offer has gone out, the language no longer changes
        offer.sudo().state = 'sent'
        self.assertFalse(Hiring._offer_row(offer.with_user(self.recruiter), full=True)['letter_lang_open'])
        with self.assertRaises(UserError):
            Hiring.act('offer_letter_lang', {'offer_id': offer.id, 'lang': 'vi_VN'})

    def test_a1_18b_choice_on_an_untouched_letter(self):
        """No choice: Hiring's own code byte for byte (R1). A chosen language
        on an untouched letter: Hiring's own code, read in that language."""
        offer = self.offer_for(self.generic)
        offer.action_prepare_letter()
        self.assertFalse(offer.pbds_lang)
        offer.sudo().pbds_letter_lang = 'vi_VN'
        values = dict(offer.with_context(lang='vi_VN')._placeholder_values())
        values['lines'] = str(offer.with_context(lang='vi_VN')._lines_table())
        expected = Template(str(self.generic.with_context(lang='vi_VN').body_html)).safe_substitute(values)
        offer.action_prepare_letter()
        self.assertEqual(str(offer.rendered_html), expected)
        self.assertEqual(offer.pbds_lang, 'vi_VN')
        self.assertIn('thg', str(offer.rendered_html), 'dates written in Vietnamese')

    # ------------------------------------------------------------ A1-19
    def test_a1_19_pay_table_words_in_every_language(self):
        expected = {'en_US': ('Every month', 'One-off'),
                    'vi_VN': ('Hằng tháng', 'Một lần'),
                    'id_ID': ('Setiap bulan', 'Sekali saja')}
        for lang, (month, once) in expected.items():
            with self.subTest(lang=lang):
                table = str(self.offer._pbds_lines_table(lang))
                self.assertIn(month, table)
                self.assertIn(once, table)

    # ------------------------------------------------------------ CZ-1
    def test_cz_01_untouched_offer_letter_pay_words_in_its_language(self):
        """DOCSTUDIO close Z item 1: an offer letter nobody has edited
        (Hiring's own `${lines}`) writes "Every month" / "One-off" in the
        letter's language, Indonesian included."""
        expected = {'en_US': ('Every month', 'One-off'),
                    'vi_VN': ('Hằng tháng', 'Một lần'),
                    'id_ID': ('Setiap bulan', 'Sekali saja')}
        for lang, (month, once) in expected.items():
            with self.subTest(lang=lang):
                table = str(self.offer.with_context(lang=lang)._lines_table())
                self.assertIn(month, table)
                self.assertIn(once, table)
        # The real letter, written in Indonesian on Hiring's own path.
        offer = self.offer_for(self.generic)
        self.assertFalse(self.generic._pbds_is_studio())
        offer.sudo().pbds_letter_lang = 'id_ID'
        offer.action_prepare_letter()
        html = str(offer.rendered_html)
        self.assertIn('Setiap bulan', html)
        self.assertIn('Sekali saja', html)
        self.assertNotIn('Every month', html)
        # No choice and an English screen: byte for byte as before.
        offer.sudo().pbds_letter_lang = False
        offer.with_context(lang='en_US').action_prepare_letter()
        self.assertIn('Every month', str(offer.rendered_html))
