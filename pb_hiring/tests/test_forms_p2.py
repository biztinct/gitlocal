# -*- coding: utf-8 -*-
"""RECRUIT P2 — application forms: seeds, copies, locks, languages, answers.

Numbered as in `docs/handovers/recruit/RECRUIT_P2_FORMS.md` §5 (tests 1–4,
12) plus the checks behind 6–9 that do not need a web page, and the static
gates the earlier phases taught this module (icons, :has(), white-label,
.po entries).
"""

import io
import re

from werkzeug.datastructures import FileStorage, MultiDict

from odoo.exceptions import UserError
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .test_interviews import InterviewCase
from ..models.forms_p2 import (BUILTINS, CUSTOM_KINDS, LOCKED, _builtin_icon, _raw,
                               seed_received_i18n)

PDF = b'%PDF-1.4\n% a tiny test file\n'


def _src(*parts):
    with open('%s/%s' % (get_module_path('pb_hiring'), '/'.join(parts)), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install', 'recruit_p2')
class TestRecruitForms(InterviewCase):

    def setUp(self):
        super().setUp()
        Lang = self.env['res.lang']
        for code in ('vi_VN', 'id_ID'):
            if not Lang.search_count([('code', '=', code), ('active', '=', True)]):
                Lang._activate_lang(code)
        self.Form = self.env['pb.hiring.form'].sudo()
        self.Form._ensure_templates()
        self.facade = self.env['pb.hiring']
        self.tpl = {f.template_key: f for f in self.Form.search(
            [('company_id', '=', self.company.id), ('template_key', '!=', False)])}

    def _raw(self, rec, fname):
        return _raw(rec, fname).get(rec.id) or {}

    # ------------------------------------------------------------- test 1
    def test_01_four_templates_locked_builtins_three_languages_idempotent(self):
        self.assertEqual(sorted(self.tpl), ['field', 'senior', 'standard', 'tech'])
        for key, form in self.tpl.items():
            self.assertTrue(form.is_template)
            kinds = form.field_ids.sorted('sequence').mapped('kind')
            self.assertEqual(kinds[-1], 'consent', '%s: consent is always last' % key)
            for locked in LOCKED:
                fld = form.field_ids.filtered(lambda f: f.kind == locked)
                self.assertEqual(len(fld), 1, '%s lacks %s' % (key, locked))
                self.assertTrue(fld.locked and fld.required)
            for fld in form.field_ids:
                raw = self._raw(fld, 'label')
                self.assertIn('vi_VN', raw, '%s/%s has no Vietnamese' % (key, fld.key))
                self.assertIn('id_ID', raw, '%s/%s has no Indonesian' % (key, fld.key))
                if fld.options:
                    self.assertIn('vi_VN', self._raw(fld, 'options'))
                    self.assertIn('id_ID', self._raw(fld, 'options'))
            consent = self._raw(form, 'consent_text')
            self.assertIn('{brand}', consent['vi_VN'])
            self.assertIn('{months}', consent['id_ID'])
        self.assertTrue(self.tpl['tech'].field_ids.filtered(lambda f: f.kind == 'portfolio').required)
        self.assertFalse(self.tpl['field'].field_ids.filtered(lambda f: f.kind == 'portfolio'))
        self.assertTrue(self.tpl['senior'].field_ids.filtered(lambda f: f.kind == 'motivation'))
        defaults = self.Form.search([('company_id', '=', self.company.id),
                                     ('is_template', '=', True), ('is_default', '=', True)])
        self.assertEqual(len(defaults), 1)
        n_forms = self.Form.with_context(active_test=False).search_count([])
        n_fields = self.env['pb.hiring.form.field'].sudo().search_count([])
        self.assertEqual(self.Form._ensure_templates(), 0)
        self.assertEqual(self.Form._fill_translations(), 0)
        self.assertEqual(self.Form.with_context(active_test=False).search_count([]), n_forms)
        self.assertEqual(self.env['pb.hiring.form.field'].sudo().search_count([]), n_fields)

    def test_01b_a_client_edit_survives_the_reseed(self):
        fld = self.tpl['standard'].field_ids.filtered(lambda f: f.kind == 'name')
        fld.update_field_translations('label', {'vi_VN': 'Tên đầy đủ của bạn'})
        self.Form._ensure_templates()
        self.assertEqual(self._raw(fld, 'label')['vi_VN'], 'Tên đầy đủ của bạn')

    # ------------------------------------------------------------- test 2
    def test_02_a_role_gets_its_own_copy_and_edits_never_leak(self):
        form = self.req.pb_form_id
        default = self.Form.search([('company_id', '=', self.company.id),
                                    ('is_template', '=', True), ('is_default', '=', True)])
        self.assertTrue(form)
        self.assertFalse(form.is_template)
        self.assertEqual(form.origin_template_id, default)
        self.assertEqual(form.requisition_id, self.req)
        self.assertEqual(form.field_ids.mapped('key'), default.field_ids.mapped('key'))
        name_copy = form.field_ids.filtered(lambda f: f.kind == 'name')
        name_tpl = default.field_ids.filtered(lambda f: f.kind == 'name')
        self.assertEqual(self._raw(name_copy, 'label').get('vi_VN'), self._raw(name_tpl, 'label').get('vi_VN'))
        name_copy.update_field_translations('label', {'en_US': 'Your full name'})
        self.assertEqual(name_tpl.with_context(lang='en_US').label, 'Full name')
        name_tpl.update_field_translations('label', {'en_US': 'Name on your ID'})
        self.assertEqual(name_copy.with_context(lang='en_US').label, 'Your full name')

    def test_02b_use_this_form_for_a_role_and_undo(self):
        old = self.req.pb_form_id
        res = self.facade.act('form_copy_to_role', {'template_id': self.tpl['tech'].id,
                                                    'requisition_id': self.req.id})
        self.assertEqual(self.req.pb_form_id.id, res['id'])
        self.assertEqual(self.req.pb_form_id.origin_template_id, self.tpl['tech'])
        self.assertFalse(old.active)
        self.facade.act('form_restore_role', {'requisition_id': self.req.id, 'old_id': old.id})
        self.assertEqual(self.req.pb_form_id, old)
        self.assertTrue(old.active)

    # ------------------------------------------------------------- test 3
    def test_03_locked_builtins_cannot_be_removed_or_made_optional(self):
        form = self.req.pb_form_id
        email = form.field_ids.filtered(lambda f: f.kind == 'email')
        with self.assertRaises(UserError) as caught:
            self.facade.act('form_field_remove', {'id': email.id})
        self.assertIn('always asked', str(caught.exception))
        self.assertTrue(email.exists())
        phone = form.field_ids.filtered(lambda f: f.kind == 'phone')
        with self.assertRaises(UserError):
            self.facade.act('form_field_save', {'id': phone.id, 'lang': 'en_US',
                                                'values': {'required': False}})
        self.assertTrue(phone.required)
        # an unlocked one goes, and comes back with every language
        linkedin = form.field_ids.filtered(lambda f: f.kind == 'linkedin')
        vi = self._raw(linkedin, 'label').get('vi_VN')
        res = self.facade.act('form_field_remove', {'id': linkedin.id})
        self.assertFalse(linkedin.exists())
        self.facade.act('form_field_restore', {'saved': res['saved']})
        back = form.field_ids.filtered(lambda f: f.kind == 'linkedin')
        self.assertEqual(self._raw(back, 'label').get('vi_VN'), vi)

    # ------------------------------------------------------------- test 4
    def test_04_get_form_by_language_and_saving_one_language_only(self):
        form = self.req.pb_form_id
        data = self.facade.get_form(form.id, 'vi_VN')
        by_kind = {f['kind']: f for f in data['fields']}
        self.assertEqual(by_kind['name']['label'], 'Họ và tên')
        self.assertEqual(by_kind['name']['label_en'], 'Full name')
        self.assertEqual(data['missing']['vi_VN'], 0)
        added = self.facade.act('form_field_add', {'form_id': form.id, 'kind': 'yes_no'})
        data = self.facade.get_form(form.id, 'vi_VN')
        self.assertGreaterEqual(data['missing']['vi_VN'], 1)
        self.assertGreaterEqual(data['missing']['id_ID'], 1)
        new = self.env['pb.hiring.form.field'].sudo().browse(added['id'])
        self.assertEqual(new.sequence, max(form.field_ids.filtered(lambda f: f.kind != 'consent').mapped('sequence')))
        self.facade.act('form_field_save', {'id': new.id, 'lang': 'id_ID',
                                            'values': {'label': 'Apakah Anda punya motor?'}})
        raw = self._raw(new, 'label')
        self.assertEqual(raw['id_ID'], 'Apakah Anda punya motor?')
        self.assertNotIn('vi_VN', raw)
        self.assertEqual(raw['en_US'], 'A yes or no question')
        after = self.facade.get_form(form.id, 'id_ID')
        self.assertEqual(after['missing']['id_ID'], 0)
        self.assertGreaterEqual(after['missing']['vi_VN'], 1)

    def test_04b_reorder_keeps_consent_last(self):
        form = self.req.pb_form_id
        ids = form.field_ids.sorted('sequence').ids
        consent = form.field_ids.filtered(lambda f: f.kind == 'consent').id
        self.facade.act('form_reorder', {'form_id': form.id, 'ids': [consent] + list(reversed(ids[:-1]))})
        order = form.field_ids.sorted('sequence')
        self.assertEqual(order[-1].id, consent)
        self.assertEqual(order.ids[:-1], list(reversed(ids[:-1])))

    def test_04c_writes_are_the_talent_leads(self):
        form = self.req.pb_form_id
        fld = form.field_ids.filtered(lambda f: f.kind == 'city')
        with self.assertRaises(Exception):
            self.facade.with_user(self.recruiter).act('form_field_save', {
                'id': fld.id, 'lang': 'en_US', 'values': {'label': 'Where do you live?'}})
        # the recruiter still reads the forms
        self.assertTrue(self.facade.with_user(self.recruiter).get_forms()['templates'])

    # ------------------------------------------------ the server's checks
    def _post(self, form, **over):
        data = {'name': 'Nguyễn Thị Lan', 'email': 'lan.nguyen@example.com',
                'phone': '+84 912 345 678', 'country': str(self.env.ref('base.vn').id),
                'city': 'Hà Nội', 'expected_pay': '25000000', 'relocation': '0',
                'consent': '1', 'linkedin': 'https://www.linkedin.com/in/lan'}
        data.update(over)
        return MultiDict({k: v for k, v in data.items() if v is not None})

    def _files(self, **files):
        md = MultiDict()
        for key, (name, blob) in files.items():
            md.add(key, FileStorage(stream=io.BytesIO(blob), filename=name))
        return md

    def test_06_required_means_required_files_included(self):
        tech = self.tpl['tech']
        clean, answers, uploads, errors = tech.with_context(lang='vi_VN')._pb_check(
            self._post(tech), self._files(cv=('cv.pdf', PDF)))
        self.assertIn('portfolio', errors, 'a required portfolio cannot be skipped')
        self.assertTrue(errors['portfolio'])
        self.assertNotIn('cv', errors)
        clean, answers, uploads, errors = tech._pb_check(
            self._post(tech), self._files(cv=('cv.pdf', PDF), portfolio=('work.pdf', b'MZ\x90\x00 not a pdf')))
        self.assertIn('not really a PDF', errors['portfolio'])
        big = PDF + b'0' * (6 * 1024 * 1024)
        clean, answers, uploads, errors = tech._pb_check(
            self._post(tech), self._files(cv=('cv.pdf', PDF), portfolio=('work.pdf', big)))
        self.assertIn('larger than', errors['portfolio'])
        clean, answers, uploads, errors = tech._pb_check(
            self._post(tech, portfolio_link='https://lan.example.com'), self._files(cv=('cv.pdf', PDF)))
        self.assertFalse(errors, errors)
        self.assertEqual(answers['portfolio'], {'link': 'https://lan.example.com'})
        self.assertEqual(clean['pb_portfolio'], 'https://lan.example.com')
        self.assertEqual(clean['pb_relocation'], 'yes')
        self.assertEqual(answers['relocation'], 'Yes')
        self.assertEqual(clean['salary_expected'], 25000000.0)
        self.assertTrue(clean['partner_phone'].startswith('+84'))

    def test_06b_consent_and_bad_phone_and_email(self):
        std = self.tpl['standard']
        _c, _a, _u, errors = std.with_context(lang='vi_VN')._pb_check(
            self._post(std, consent=None, phone='12', email='nope'), self._files(cv=('cv.pdf', PDF)))
        self.assertIn('consent', errors)
        self.assertIn('phone', errors)
        self.assertIn('email', errors)
        # the sentence is in the page's language
        self.assertIn('đánh dấu', errors['consent'])

    # ------------------------------------------------------ tests 8, 9, 12
    def test_12_answers_in_form_order_consent_snapshot_duplicate_and_timeline(self):
        form = self.req.pb_form_id
        page = form.with_context(lang='vi_VN')
        clean, answers, uploads, errors = page._pb_check(self._post(form), self._files(cv=('cv.pdf', PDF)))
        self.assertFalse(errors, errors)
        seed_received_i18n(self.env)
        job = self.req.job_id
        first = form._pb_make_applicant(job, self.req, clean, answers, uploads, 'vi_VN')
        self.assertEqual(first.pb_lang, 'vi_VN')
        self.assertEqual(first.pb_country_id, self.env.ref('base.vn'))
        self.assertTrue(first.pb_consent_on)
        self.assertIn('tháng', first.pb_consent_text)
        self.assertNotIn('{brand}', first.pb_consent_text)
        att = self.env['ir.attachment'].sudo().search([('res_model', '=', 'hr.applicant'),
                                                       ('res_id', '=', first.id)])
        self.assertEqual(att.pb_form_key, 'cv')
        mail = self.env['mail.mail'].sudo().search([('model', '=', 'hr.applicant'), ('res_id', '=', first.id),
                                                    ('email_to', '=', first.email_from)])
        self.assertEqual(len(mail), 1)
        self.assertIn('Chúng tôi đã nhận', mail.subject)
        # the same email again: flagged, never blocked
        second = form._pb_make_applicant(job, self.req, clean, answers, uploads, 'id_ID')
        self.assertEqual(second.pb_possible_duplicate_id, first)
        mail2 = self.env['mail.mail'].sudo().search([('model', '=', 'hr.applicant'), ('res_id', '=', second.id),
                                                     ('email_to', '=', second.email_from)])
        self.assertIn('Lamaran Anda', mail2.subject)
        # the drawer
        cand = self.facade.get_candidate(first.id)
        keys = [a['key'] for a in cand['answers']]
        order = [f.key for f in form.field_ids.sorted('sequence') if f.kind != 'consent']
        self.assertEqual(keys, order)
        self.assertEqual(cand['consent']['lang'], 'Tiếng Việt')
        cv = [a for a in cand['answers'] if a['key'] == 'cv'][0]
        self.assertEqual(len(cv['files']), 1)
        applied = [t for t in cand['timeline'] if t['kind'] == 'applied'][0]
        self.assertTrue(applied['text'].endswith('(Tiếng Việt)'), applied['text'])
        cand2 = self.facade.get_candidate(second.id)
        self.assertEqual(cand2['duplicate']['id'], first.id)
        card = self.facade._card(second, [], 0, self.req, second.create_date, second.create_date.date(), True)
        self.assertEqual(card['chips'][0]['label'], 'Possibly the same person')
        self.facade.act('same_person', {'applicant_id': second.id})
        self.assertEqual(second.pb_same_person_id, first)
        self.assertEqual(first.pb_same_person_id, second)
        self.facade.act('same_person', {'applicant_id': second.id, 'undo': True})
        self.assertFalse(first.pb_same_person_id)

    def test_12b_the_received_email_falls_back_to_english_and_says_so(self):
        form = self.req.pb_form_id
        clean, answers, uploads, errors = form._pb_check(self._post(form, email='x.fallback@example.com'),
                                                         self._files(cv=('cv.pdf', PDF)))
        tpl = self.env['pb.hiring.message.template'].sudo().search(
            [('company_id', '=', self.company.id), ('key', '=', 'received')], limit=1)
        self.assertTrue(tpl)
        self.env.cr.execute("UPDATE pb_hiring_message_template SET body = body - 'id_ID' WHERE id = %s", [tpl.id])
        tpl.invalidate_recordset()
        app = form._pb_make_applicant(self.req.job_id, self.req, clean, answers, uploads, 'id_ID')
        mail = self.env['mail.mail'].sudo().search([('model', '=', 'hr.applicant'), ('res_id', '=', app.id),
                                                    ('email_to', '=', app.email_from)])
        self.assertIn('Thanks for applying', mail.body_html)
        notes = [t['text'] for t in self.facade.get_timeline(app.id)]
        self.assertTrue(any('went out in English' in n for n in notes), notes)

    def test_12c_a_line_manager_never_sees_expected_pay_or_files(self):
        form = self.req.pb_form_id
        clean, answers, uploads, errors = form._pb_check(self._post(form, email='lm.view@example.com'),
                                                         self._files(cv=('cv.pdf', PDF)))
        app = form._pb_make_applicant(self.req.job_id, self.req, clean, answers, uploads, 'en_US')
        rows = self.facade._answers(app, can_recruit=False)
        self.assertNotIn('expected_pay', [r['key'] for r in rows])
        self.assertFalse([r for r in rows if r['files']])

    # -------------------------------------------------- set-up and the role
    def test_13_setup_card_is_live_and_the_role_shows_its_form(self):
        cards = {c['key']: c for c in self.facade.get_setup()['cards']}
        self.assertEqual(cards['forms']['action']['tag'], 'pb_hiring_forms')
        self.assertIn('templates', cards['forms']['status'])
        row = self.facade.get_requisition(self.req.id)
        self.assertEqual(row['app_form']['id'], self.req.pb_form_id.id)
        forms = self.facade.get_forms()
        self.assertEqual({lg['code'] for lg in forms['languages']}, {'en_US', 'vi_VN', 'id_ID'})
        self.assertIn(self.req.pb_form_id.id, [f['id'] for f in forms['role_forms']])

    # -------------------------------------------------------- static gates
    def test_20_every_icon_is_in_the_shared_registry(self):
        known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                               _src('..', 'pb_import_kit', 'static', 'src', 'js', 'import_icons.js'), re.M))
        self.assertGreater(len(known), 60)
        used = set()
        for parts in (('static', 'src', 'xml', 'hiring_forms.xml'),
                      ('static', 'src', 'xml', 'hiring_board_p1.xml'),
                      ('static', 'src', 'xml', 'hiring_board.xml'),
                      ('views', 'application_templates.xml')):
            used |= set(re.findall(r"ic\('([A-Za-z0-9_]+)'", _src(*parts)))
        used |= set(re.findall(r"ic\(cand\.duplicate\.same \? '(\w+)' : '(\w+)'", _src(
            'static', 'src', 'xml', 'hiring_board_p1.xml'))[0])
        used |= {v[2] for v in CUSTOM_KINDS.values()}
        used |= {_builtin_icon(k) for k in BUILTINS}
        used |= set(re.findall(r'icon:\s*"([A-Za-z0-9_]+)"', _src('static', 'src', 'js', 'hiring_palette.js')))
        self.assertFalse(sorted(used - known), 'not in the shared registry: %s' % sorted(used - known))

    def test_21_no_has_selector_no_loop_no_odoo(self):
        portal = _src('static', 'src', 'scss', 'portal_hiring.scss')
        self.assertNotIn(':has(', portal, 'the page must style in every browser')
        forms = _src('static', 'src', 'scss', 'hiring_forms.scss')
        self.assertNotIn('infinite', forms, 'nothing loops (blueprint)')
        for parts in (('views', 'application_templates.xml'),
                      ('static', 'src', 'xml', 'hiring_forms.xml'),
                      ('models', 'form_seed_i18n.py'),
                      ('i18n', 'id_ID.po')):
            src = re.sub(r'<!--.*?-->', '', _src(*parts), flags=re.S)
            self.assertNotIn('Odoo', src, '%s shows the word Odoo' % parts[-1])
        board = _src('static', 'src', 'xml', 'hiring_forms.xml') + _src('views', 'application_templates.xml')
        self.assertNotIn('phone screen', board.lower(), 'RC-D8: it is Recruiter review')

    def test_22_every_po_entry_carries_the_three_lines(self):
        for lang in ('vi_VN', 'id_ID'):
            src = _src('i18n', '%s.po' % lang)
            for block in src.split('\n\n')[1:]:
                if 'msgid "' not in block:
                    continue
                self.assertIn('#. module: pb_hiring', block)
                if '#: code:' in block:
                    # a code string needs its marker or it is dropped in silence
                    self.assertTrue('#. odoo-python' in block or '#. odoo-javascript' in block, block)
                    self.assertRegex(block, r'#: code:addons/pb_hiring/\S+:\d+', block)
                else:
                    self.assertRegex(block, r'#: model(_terms)?:', block)
        from odoo.tools.translate import PoFileReader
        for lang in ('vi_VN', 'id_ID'):
            path = '%s/i18n/%s.po' % (get_module_path('pb_hiring'), lang)
            with open(path, 'rb') as fh:
                rows = list(PoFileReader(fh))
            self.assertTrue(rows)
        # the page's chrome reaches a Vietnamese and an Indonesian page
        vi = self.env(context=dict(self.env.context, lang='vi_VN'))
        self.assertEqual(vi._('Send my application'), 'Gửi hồ sơ của tôi')
        ind = self.env(context=dict(self.env.context, lang='id_ID'))
        self.assertEqual(ind._('Send my application'), 'Kirim lamaran saya')
