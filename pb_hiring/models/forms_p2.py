# -*- coding: utf-8 -*-
"""RECRUIT P2 — application forms the talent lead builds, in three languages.

WHAT THIS FILE ADDS, in the order a candidate meets it:

  * **The form** (`pb.hiring.form` + `pb.hiring.form.field`). A template is
    what "Use this form for…" copies FROM; a role always holds its OWN copy,
    so editing a template never changes a role's page and editing a role's
    page never leaks into another role ("Presets fill in new roles" — the P1
    rule, applied to forms).
  * **Built-in questions** have a fixed key and land in the candidate's real
    fields as well as in the answers (name → partner_name, CV → a file, ...).
    Six of them are LOCKED: name, email, phone, country, CV and consent can be
    renamed but never removed or made optional.
  * **Own questions** (`q_<slug>` keys): short and long answers, choices,
    yes/no, numbers, dates, files and links.
  * **Languages are tabs, not copies.** Every candidate-facing text is a
    translated field; the builder writes one language at a time with
    `update_field_translations`. "N missing" reads the raw JSON (a language
    is missing when it has no key, not when it happens to equal English —
    "CV" is "CV" in all three).
  * **Required means required.** `_pb_check` re-validates EVERYTHING the page
    sends, files included (the portfolio hole), with the sentence in the
    candidate's language.
  * **The duplicate flag** (same email or phone in the company, last six
    months) never blocks; it is a chip and a sentence.
  * **Consent** is stored as the exact sentence the person ticked, in the
    language they read it in, with the moment they ticked it.

The seed runs on every load (`seed_journey`) and is idempotent: templates are
created once per company and then belong to the client; Vietnamese and
Indonesian are written only where the record still carries the product's
English and has no text of its own in that language.
"""

import base64
import logging
import re
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import SQL, email_normalize

from .form_seed_i18n import FORM_I18N, RECEIVED_I18N
from .hiring_common import P_CANDIDATE_MAIL, as_id, flag, leg
from .journey import AUTHORIZATION, RELOCATION, text_html

_logger = logging.getLogger(__name__)

#: The three languages a form is written in (ruling R11). English is the
#: source and always on.
FORM_LANGS = ('en_US', 'vi_VN', 'id_ID')
LANG_WORDS = {'en_US': 'English', 'vi_VN': 'Tiếng Việt', 'id_ID': 'Bahasa Indonesia'}
LANG_SHORT = {'en_US': 'EN', 'vi_VN': 'VI', 'id_ID': 'ID'}
#: A role's country picks the language a first-time visitor sees.
COUNTRY_LANG = {'VN': 'vi_VN', 'ID': 'id_ID'}

#: Candidate-facing translated columns, per model.
FIELD_TRANSLATED = ('label', 'help', 'placeholder', 'options')
FORM_TRANSLATED = ('name', 'consent_text')

CONSENT_EN = ('I agree that {brand} keeps my application for {months} months to '
              'consider me for this and similar roles.')
AUTH_OPTIONS = ('Yes, I have a valid work permit or visa\nYes, I am a citizen or '
                'permanent resident\nNo, I would need visa sponsorship\nI am not sure')
RELOC_OPTIONS = 'Yes\nNo\nIt depends on the role and terms'

#: key -> what the built-in is. `widget` is how the page draws it; `store`
#: names the applicant field it ALSO lands in.
BUILTINS = {
    'name': dict(label='Full name', widget='text', locked=True, store='partner_name'),
    'email': dict(label='Email address', widget='email', locked=True, store='email_from'),
    'phone': dict(label='Phone number', widget='tel', locked=True,
                  help='We only call about this application.', store='partner_phone'),
    'country': dict(label='Country you live in', widget='country', locked=True,
                    store='pb_country_id'),
    'city': dict(label='Where are you based right now?', widget='text',
                 help='A city or district is enough.', store='pb_location'),
    'linkedin': dict(label='LinkedIn profile', widget='url',
                     placeholder='https://www.linkedin.com/in/your-name', store='pb_linkedin'),
    'cv': dict(label='CV', widget='file', locked=True, file_kinds='pdf,doc',
               store='a file on the candidate'),
    'portfolio': dict(label='Portfolio', widget='portfolio',
                      help='Upload a file or paste a link.', file_kinds='pdf,image,zip',
                      store='pb_portfolio'),
    'expected_pay': dict(label='Expected monthly pay', widget='money',
                         help='A monthly figure before tax. Only the hiring team sees it.',
                         store='salary_expected'),
    'authorization': dict(label='Do you have the right to work in this country?',
                          widget='choice', options=AUTH_OPTIONS,
                          store='pb_work_authorization'),
    'relocation': dict(label='Are you willing to relocate for this role?', widget='choice',
                       options=RELOC_OPTIONS, store='pb_relocation'),
    'motivation': dict(label='Why would you like to join us?', widget='textarea',
                       help='Tell us what draws you to this role and what you would bring.',
                       min_words=150, max_words=250, store='pb_motivation'),
    'consent': dict(label='Your consent', widget='consent', locked=True,
                    store='pb_consent_on'),
}
LOCKED = {k for k, v in BUILTINS.items() if v.get('locked')}
#: The order built-ins are offered in "Add a built-in field".
BUILTIN_ORDER = ['name', 'email', 'phone', 'country', 'city', 'linkedin', 'cv',
                 'portfolio', 'expected_pay', 'authorization', 'relocation',
                 'motivation', 'consent']

#: kind -> (what the talent lead calls it, how the page draws it, icon)
CUSTOM_KINDS = {
    'short_text': ('Short answer', 'text', 'pencil'),
    'long_text': ('Long answer', 'textarea', 'fileText'),
    'choice': ('Choice', 'choice', 'circleDot'),
    'multi_choice': ('Several choices', 'multi', 'checkCheck'),
    'yes_no': ('Yes / No', 'yes_no', 'checkCircle'),
    'number': ('Number', 'number', 'hash'),
    'date': ('Date', 'date', 'calendar'),
    'file': ('File', 'file', 'paperclip'),
    'link': ('Link', 'url', 'link'),
}
KIND_SELECTION = ([(k, 'Built-in: ' + BUILTINS[k]['label']) for k in BUILTIN_ORDER]
                  + [(k, v[0]) for k, v in CUSTOM_KINDS.items()])

#: File kinds a question may accept: suffixes, and the word the page shows.
FILE_KINDS = {
    'pdf': (('pdf',), 'PDF'),
    'doc': (('doc', 'docx'), 'Word'),
    'image': (('jpg', 'jpeg', 'png'), 'JPG / PNG'),
    'zip': (('zip',), 'ZIP'),
}
#: What the first bytes of each suffix must be — a renamed .exe is refused.
MAGIC = {
    'pdf': (b'%PDF',), 'doc': (b'\xd0\xcf\x11\xe0',), 'docx': (b'PK',),
    'jpg': (b'\xff\xd8\xff',), 'jpeg': (b'\xff\xd8\xff',), 'png': (b'\x89PNG',),
    'zip': (b'PK',),
}
MIMETYPES = {
    'pdf': 'application/pdf', 'doc': 'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png', 'zip': 'application/zip',
}
HARD_MAX_MB = 15
TEXT_CAP = 12000
DUPLICATE_MONTHS = 6


def _std(*rows):
    return [dict(r) for r in rows]


def _b(key, **extra):
    """A built-in row for a seeded template."""
    spec = BUILTINS[key]
    row = {'kind': key, 'key': key, 'label': spec['label'],
           'help': spec.get('help', ''), 'placeholder': spec.get('placeholder', ''),
           'options': spec.get('options', ''), 'required': bool(spec.get('locked')),
           'file_kinds': spec.get('file_kinds', ''),
           'min_words': spec.get('min_words', 0), 'max_words': spec.get('max_words', 0)}
    row.update(extra)
    return row


def _q(kind, key, label, **extra):
    row = {'kind': kind, 'key': key, 'label': label, 'help': '', 'placeholder': '',
           'options': '', 'required': False, 'file_kinds': '', 'min_words': 0,
           'max_words': 0}
    row.update(extra)
    return row


def seeded_templates():
    """The four templates the product ships (spec §2.1). Called, not a
    constant, so each seed gets fresh dicts."""
    head = [_b('name'), _b('email'), _b('phone'), _b('country'),
            _b('city', required=True)]
    tail_common = [_b('relocation', required=True), _b('consent')]
    standard = head + [
        _b('expected_pay', required=True), _b('cv'),
        _b('portfolio', required=False, portfolio_mode='link', placeholder='https://'),
        _b('linkedin'),
    ] + tail_common
    field = head + [
        _q('yes_no', 'q_licence', 'Do you hold a driving licence?', required=True),
        _q('short_text', 'q_provinces', 'Which provinces can you cover?', required=True,
           help='List the provinces or cities you could travel to regularly.'),
        _b('expected_pay', required=True), _b('cv'), _b('linkedin'),
    ] + tail_common
    senior = head + [
        _b('expected_pay', required=True), _b('cv'),
        _b('portfolio', required=False, portfolio_mode='link', placeholder='https://'),
        _b('linkedin'),
        _b('motivation', required=True),
        _q('short_text', 'q_notice', 'What is your notice period?', required=True,
           help='For example: one month, or available now.'),
    ] + tail_common
    tech = head + [
        _b('expected_pay', required=True), _b('cv'),
        _b('portfolio', label='Portfolio (file or link)', required=True,
           portfolio_mode='either'),
        _q('link', 'q_code', 'Link to code you are proud of', placeholder='https://',
           help='A repository, a project or anything you built.'),
        _b('linkedin'),
    ] + tail_common
    return [('standard', 'Standard', 10, standard),
            ('field', 'Field roles', 20, field),
            ('senior', 'Senior roles', 30, senior),
            ('tech', 'Tech roles', 40, tech)]


def lang_word(code):
    return LANG_WORDS.get(code or '', code or '')


def _slug(text):
    s = re.sub(r'[^a-z0-9]+', '_', (text or '').lower()).strip('_')
    return (s or 'question')[:30]


# =========================================================================
#  The company knob P4 builds on
# =========================================================================
class HiringCompanyRetention(models.Model):
    _inherit = 'res.company'

    pb_retention_months = fields.Integer(
        string='Months we keep an application', default=12,
        help='Shown in the consent sentence on every application form. The '
             'automatic clean-up after this many months arrives with the '
             'privacy release.')


class HiringAttachmentKey(models.Model):
    _inherit = 'ir.attachment'

    pb_form_key = fields.Char(
        string='Application question', index='btree_not_null', copy=False,
        help='The question on the application form this file answered.')


# =========================================================================
#  The form
# =========================================================================
class PbHiringForm(models.Model):
    _name = 'pb.hiring.form'
    _description = 'Application form'
    _order = 'is_template desc, sequence, id'

    name = fields.Char(string='Name', required=True, translate=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, default=lambda self: self.env.company)
    is_template = fields.Boolean(
        string='Template', index=True,
        help='A template is what "Use this form for…" copies from. A role '
             'always gets its own copy, so editing a template never changes a '
             'role that already has a form.')
    template_key = fields.Char(
        string='Product template', copy=False, readonly=True,
        help='Set on the four templates the product ships, so a re-seed can '
             'recognise them. Empty on everything a person made.')
    origin_template_id = fields.Many2one('pb.hiring.form', string='Copied from',
                                         ondelete='set null')
    requisition_id = fields.Many2one('pb.hiring.requisition', string='Role',
                                     index=True, ondelete='set null')
    language_codes = fields.Char(
        string='Languages', default='en_US,vi_VN,id_ID',
        help='Comma list of the languages this form is offered in.')
    consent_text = fields.Text(
        string='Consent sentence', translate=True, default=CONSENT_EN,
        help='{brand} and {months} are filled in on the page.')
    field_ids = fields.One2many('pb.hiring.form.field', 'form_id', string='Questions',
                                copy=False)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    is_default = fields.Boolean(
        string='Default for new roles',
        help='New roles in this company start with a copy of this template.')

    # ------------------------------------------------------------ raw JSON
    def _pb_raw(self, fname):
        """{id: {lang: text}} straight from the column, so "missing" means
        "no key", never "equal to English"."""
        return _raw(self, fname)

    def _pb_langs(self):
        self.ensure_one()
        codes = [c.strip() for c in (self.language_codes or '').split(',') if c.strip()]
        out = ['en_US'] + [c for c in codes if c != 'en_US' and c in FORM_LANGS]
        return out

    def _pb_missing(self, langs=None):
        """{lang: [{field_id, key, what, label_en}]} — every candidate-facing
        text that has English and no text in that language."""
        self.ensure_one()
        langs = [lg for lg in (langs or self._pb_langs()) if lg != 'en_US']
        out = {lg: [] for lg in langs}
        if not langs:
            return out
        flds = self.sudo().field_ids.sorted('sequence').filtered(lambda f: f.kind != 'consent')
        raws = {f: _raw(flds, f) for f in FIELD_TRANSLATED}
        for fld in flds:
            label_en = (raws['label'].get(fld.id) or {}).get('en_US') or fld.key
            for fname in FIELD_TRANSLATED:
                raw = raws[fname].get(fld.id) or {}
                if not (raw.get('en_US') or '').strip():
                    continue
                for lg in langs:
                    if lg not in raw:
                        out[lg].append({'field_id': fld.id, 'key': fld.key, 'what': fname,
                                        'label_en': label_en})
        # The consent question's words ARE the form's sentence.
        consent = _raw(self.sudo(), 'consent_text').get(self.id) or {}
        if (consent.get('en_US') or '').strip():
            for lg in langs:
                if lg not in consent:
                    out[lg].append({'field_id': False, 'key': 'consent', 'what': 'consent_text',
                                    'label_en': 'Consent sentence'})
        return out

    # ------------------------------------------------------------ copying
    def _pb_clone(self, vals=None):
        """A full copy — every language of every text — as the system.

        Written by hand rather than `copy()`: the translated columns are
        copied as their raw JSON so no language is lost on the way.
        """
        self.ensure_one()
        src = self.sudo().with_context(lang='en_US', active_test=False)
        Form = self.env['pb.hiring.form'].sudo().with_context(lang='en_US')
        base = {
            'name': src.name, 'company_id': src.company_id.id,
            'language_codes': src.language_codes, 'consent_text': src.consent_text,
            'origin_template_id': src.id if src.is_template else (src.origin_template_id.id or src.id),
            'is_template': False, 'is_default': False, 'sequence': src.sequence,
        }
        base.update(vals or {})
        new = Form.create(base)
        _copy_raw(self.env, 'pb_hiring_form', src.id, new.id,
                  [f for f in FORM_TRANSLATED if f != 'name' or 'name' not in (vals or {})])
        Field = self.env['pb.hiring.form.field'].sudo().with_context(lang='en_US')
        for fld in src.field_ids.sorted('sequence'):
            nf = Field.create({
                'form_id': new.id, 'sequence': fld.sequence, 'kind': fld.kind,
                'key': fld.key, 'label': fld.label or '', 'required': fld.required,
                'min_words': fld.min_words, 'max_words': fld.max_words,
                'file_kinds': fld.file_kinds, 'max_mb': fld.max_mb,
                'portfolio_mode': fld.portfolio_mode,
            })
            _copy_raw(self.env, 'pb_hiring_form_field', fld.id, nf.id, FIELD_TRANSLATED)
        self.env['pb.hiring.form'].invalidate_model()
        self.env['pb.hiring.form.field'].invalidate_model()
        return new

    # ------------------------------------------------------------ seeds
    @api.model
    def _pb_installed_langs(self):
        return {code for code, _n in self.env['res.lang'].get_installed()}

    @api.model
    def _ensure_templates(self, companies=None):
        """The four product templates per company, a default, then the
        Vietnamese / Indonesian fill. Idempotent."""
        Form = self.sudo().with_context(active_test=False, lang='en_US')
        made = 0
        for company in (companies or self.env['res.company'].sudo().search([])):
            for tkey, name, seq, rows in seeded_templates():
                if Form.search_count([('company_id', '=', company.id),
                                      ('template_key', '=', tkey)]):
                    continue
                form = Form.create({'name': name, 'company_id': company.id,
                                    'is_template': True, 'template_key': tkey,
                                    'sequence': seq, 'consent_text': CONSENT_EN})
                for i, row in enumerate(rows):
                    row = dict(row, form_id=form.id, sequence=(i + 1) * 10)
                    self.env['pb.hiring.form.field'].sudo().with_context(
                        lang='en_US').create(row)
                made += 1
            if not Form.search_count([('company_id', '=', company.id),
                                      ('is_template', '=', True), ('active', '=', True),
                                      ('is_default', '=', True)]):
                std = Form.search([('company_id', '=', company.id),
                                   ('template_key', '=', 'standard'),
                                   ('active', '=', True)], limit=1) \
                    or Form.search([('company_id', '=', company.id),
                                    ('is_template', '=', True), ('active', '=', True)],
                                   limit=1)
                if std:
                    std.is_default = True
        self._fill_translations()
        return made

    @api.model
    def _fill_translations(self, forms=None):
        """Write the product's Vietnamese / Indonesian onto every form text
        that still carries the product's English and has none of its own."""
        langs = [lg for lg in ('vi_VN', 'id_ID') if lg in self._pb_installed_langs()]
        if not langs:
            return 0
        written = 0
        forms = (forms or self.sudo().with_context(active_test=False).search([])).sudo()
        for fname in FORM_TRANSLATED:
            for rid, raw in _raw(forms, fname).items():
                written += _fill_one(self.env['pb.hiring.form'].sudo().browse(rid), fname, raw, langs)
        flds = forms.with_context(active_test=False).field_ids
        for fname in FIELD_TRANSLATED:
            for rid, raw in _raw(flds, fname).items():
                written += _fill_one(self.env['pb.hiring.form.field'].sudo().browse(rid),
                                     fname, raw, langs)
        return written

    @api.model
    def _default_template(self, company):
        Form = self.sudo()
        tpl = Form.search([('company_id', '=', company.id), ('is_template', '=', True),
                           ('is_default', '=', True)], limit=1)
        if not tpl:
            self._ensure_templates(company)
            tpl = Form.search([('company_id', '=', company.id), ('is_template', '=', True),
                               ('is_default', '=', True)], limit=1)
        return tpl

    # ------------------------------------------------------------ the page
    def _pb_consent_sentence(self, company):
        self.ensure_one()
        text = self.consent_text or ''
        brand = company._hiring_brand()
        months = company.pb_retention_months or 12
        return text.replace('{brand}', brand).replace('{months}', str(months))

    def _pb_check(self, form, files, ctx=None):
        """Validate EVERYTHING a page sent against this form.

        `form` / `files` are MultiDicts (the request's, or a test's). The
        sentences come back in `self.env.lang` — the caller hands us the form
        read in the page's language.

        Returns (clean, answers, uploads, errors):
          clean   — the built-ins' values for the applicant's real fields;
          answers — {key: value} for every question, English for choices;
          uploads — [(key, filename, bytes, mimetype)];
          errors  — {key: sentence}.
        """
        self.ensure_one()
        _t = self.env._
        ctx = ctx or {}
        en = {f.id: f for f in self.sudo().with_context(lang='en_US').field_ids}
        clean, answers, uploads, errors = {}, {}, [], {}
        country = False
        # The country first: the phone is checked against it.
        for fld in self.field_ids.sorted('sequence'):
            if fld.kind == 'country':
                raw = (form.get('country') or '').strip()
                country = self.env['res.country'].sudo().browse(as_id(raw)).exists() if raw else False
        for fld in self.field_ids.sorted('sequence'):
            key, kind, label = fld.key, fld.kind, (fld.label or fld.key)
            widget = fld.widget
            opts_en = [o for o in (en[fld.id].options or '').split('\n') if o.strip()]
            need = fld.required or kind in LOCKED

            def missing(sentence=None):
                errors[key] = sentence or _t('Add your answer to “%s”.', label)

            if widget in ('text', 'email', 'tel', 'url', 'textarea', 'number', 'date', 'money'):
                value = (form.get(key) or '').strip()[:TEXT_CAP]
                if not value:
                    if need:
                        missing()
                    continue
                if widget == 'email':
                    norm = email_normalize(value)
                    if not norm:
                        errors[key] = _t('Enter an email address like name@example.com.')
                        continue
                    value = value
                elif widget == 'tel':
                    formatted = _phone(value, country)
                    if formatted is False:
                        errors[key] = (_t('This does not look like a phone number in %s. Include the country code, like +%s.',
                                          country.name, country.phone_code) if country
                                       else _t('This does not look like a phone number.'))
                        continue
                    value = formatted or value
                elif widget == 'url':
                    if not _https(value):
                        errors[key] = _t('Paste a full link that starts with https://')
                        continue
                elif widget in ('number', 'money'):
                    try:
                        num = float(value.replace(',', '').replace(' ', ''))
                        if num < 0 or num > 1e13:
                            raise ValueError
                    except ValueError:
                        errors[key] = _t('Enter a number, like 15000000.')
                        continue
                    value = num
                elif widget == 'date':
                    try:
                        value = str(fields.Date.to_date(value))
                    except (ValueError, TypeError):
                        errors[key] = _t('Choose a date.')
                        continue
                elif widget == 'textarea':
                    n = len(value.split())
                    lo, hi = fld.min_words or 0, fld.max_words or 0
                    if (lo and n < lo) or (hi and n > hi):
                        if lo and hi:
                            errors[key] = _t('Write between %(min)s and %(max)s words. You have %(n)s.',
                                             min=lo, max=hi, n=n)
                        elif lo:
                            errors[key] = _t('Write at least %(min)s words. You have %(n)s.', min=lo, n=n)
                        else:
                            errors[key] = _t('Keep it under %(max)s words. You have %(n)s.', max=hi, n=n)
                        continue
                if widget == 'money':
                    answers[key] = {'amount': value, 'currency': ctx.get('currency') or ''}
                else:
                    answers[key] = value
            elif widget == 'country':
                if not country:
                    if need:
                        missing(_t('Choose the country you live in.'))
                    continue
                answers[key] = country.id
            elif widget in ('choice', 'yes_no'):
                raw = (form.get(key) or '').strip()
                if not raw:
                    if need:
                        missing(_t('Choose an answer for “%s”.', label))
                    continue
                if widget == 'yes_no':
                    if raw not in ('yes', 'no'):
                        errors[key] = _t('Choose an answer for “%s”.', label)
                        continue
                    answers[key] = raw
                    continue
                try:
                    idx = int(raw)
                    answers[key] = opts_en[idx]
                    if kind == 'authorization' and idx < len(AUTHORIZATION):
                        clean['pb_work_authorization'] = AUTHORIZATION[idx][0]
                    if kind == 'relocation' and idx < len(RELOCATION):
                        clean['pb_relocation'] = RELOCATION[idx][0]
                except (ValueError, IndexError):
                    errors[key] = _t('Choose an answer for “%s”.', label)
            elif widget == 'multi':
                picked = []
                for raw in form.getlist(key) if hasattr(form, 'getlist') else [form.get(key)]:
                    try:
                        picked.append(opts_en[int(raw)])
                    except (ValueError, IndexError, TypeError):
                        continue
                if not picked:
                    if need:
                        missing(_t('Choose at least one answer for “%s”.', label))
                    continue
                answers[key] = picked
            elif widget == 'consent':
                if (form.get(key) or '') not in ('1', 'on', 'yes', 'true'):
                    errors[key] = _t('Tick the box to agree before you send.')
                    continue
                answers[key] = True
            elif widget in ('file', 'portfolio'):
                link = (form.get(key + '_link') or '').strip()[:2000] if widget == 'portfolio' else ''
                mode = fld.portfolio_mode if widget == 'portfolio' else 'file'
                got = [f for f in (files.getlist(key) if hasattr(files, 'getlist') else [files.get(key)])
                       if f is not None and getattr(f, 'filename', '')]
                if mode == 'link':
                    got = []
                if mode == 'file':
                    link = ''
                if link and not _https(link):
                    errors[key] = _t('Paste a full link that starts with https://')
                    continue
                if not got and not link:
                    if need:
                        missing(_t('Choose a file for “%s”.', label) if mode == 'file'
                                else _t('Paste a link for “%s”.', label) if mode == 'link'
                                else _t('Upload a file or paste a link for “%s”.', label))
                    continue
                bad = None
                names = []
                for up in got[:5]:
                    problem, blob, mime = _check_file(self.env, fld, up)
                    if problem:
                        bad = problem
                        break
                    uploads.append((key, up.filename[:200], blob, mime))
                    names.append(up.filename[:200])
                if bad:
                    errors[key] = bad
                    uploads[:] = [u for u in uploads if u[0] != key]
                    continue
                if widget == 'portfolio':
                    answers[key] = {'link': link} if link and not names else {'files': names, 'link': link or ''}
                else:
                    answers[key] = {'files': names}
            # the built-ins' real fields
            if key in answers and fld.kind in BUILTINS:
                store = BUILTINS[fld.kind]['store']
                val = answers[key]
                if fld.kind == 'expected_pay':
                    clean['salary_expected'] = val['amount']
                elif fld.kind == 'portfolio':
                    clean['pb_portfolio'] = (val.get('link') or ', '.join(val.get('files') or []))[:2000]
                elif fld.kind == 'country':
                    clean['pb_country_id'] = val
                elif fld.kind in ('authorization', 'relocation', 'cv', 'consent'):
                    pass
                elif store and not store.startswith('a '):
                    clean[store] = val
        return clean, answers, uploads, errors

    def _pb_make_applicant(self, job, req, clean, answers, uploads, lang, extra=None):
        """The candidate, as the system, in one savepoint: the real fields,
        the answers, the files with their question, the consent snapshot in
        the language they read it in, the duplicate flag, then the
        "Application received" email in that language."""
        self.ensure_one()
        form = self.sudo()
        company = job.company_id
        country = self.env['res.country'].sudo().browse(clean.get('pb_country_id') or 0).exists()
        vals = dict(clean)
        vals.update({
            'job_id': job.id, 'company_id': company.id,
            'department_id': job.department_id.id or False,
            'user_id': job.user_id.id or False,
            'pb_requisition_id': req.id or False,
            'pb_form_id': form.id, 'pb_form_answers': answers, 'pb_lang': lang,
        })
        if not vals.get('pb_location') and country:
            vals['pb_location'] = country.name
        elif vals.get('pb_location') and country:
            vals['pb_location'] = '%s, %s' % (vals['pb_location'], country.name)
        if vals.get('pb_linkedin') and 'linkedin_profile' in self.env['hr.applicant']._fields:
            vals['linkedin_profile'] = vals['pb_linkedin']
        consent = form.field_ids.filtered(lambda f: f.kind == 'consent')[:1]
        if consent and answers.get(consent.key):
            vals['pb_consent_on'] = fields.Datetime.now()
            vals['pb_consent_text'] = form.with_context(lang=lang)._pb_consent_sentence(company)
        vals.update(extra or {})
        Applicant = self.env['hr.applicant'].sudo()
        applicant = Applicant.create(vals)
        for key, name, blob, mime in uploads:
            self.env['ir.attachment'].sudo().create({
                'name': name, 'datas': base64.b64encode(blob), 'mimetype': mime,
                'res_model': 'hr.applicant', 'res_id': applicant.id, 'public': False,
                'pb_form_key': key})
        dup = applicant._pb_find_duplicate()
        if dup:
            applicant.write({'pb_possible_duplicate_id': dup.id})
        leg(self.env, 'the received email to %s' % applicant.id, applicant._pb_send_received)
        return applicant


class PbHiringFormField(models.Model):
    _name = 'pb.hiring.form.field'
    _description = 'Application form question'
    _order = 'sequence, id'

    form_id = fields.Many2one('pb.hiring.form', string='Form', required=True,
                              ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection(KIND_SELECTION, string='Kind', required=True)
    key = fields.Char(string='Key', required=True,
                      help='Built-ins have a fixed key; own questions are q_<name>.')
    label = fields.Char(string='Question', translate=True, required=True)
    help = fields.Char(string='Help line', translate=True)
    placeholder = fields.Char(string='Example answer', translate=True)
    options = fields.Text(string='Options', translate=True, help='One per line.')
    required = fields.Boolean(string='Required')
    min_words = fields.Integer(string='At least (words)')
    max_words = fields.Integer(string='At most (words)')
    file_kinds = fields.Char(string='File kinds', help='Comma list of pdf, doc, image, zip.')
    max_mb = fields.Integer(string='Largest file (MB)', default=5)
    portfolio_mode = fields.Selection(
        [('file', 'A file'), ('link', 'A link'), ('either', 'A file or a link')],
        string='Portfolio as', default='either')
    locked = fields.Boolean(compute='_compute_facts')
    builtin = fields.Boolean(compute='_compute_facts')
    widget = fields.Char(compute='_compute_facts')
    store_to = fields.Char(string='Also saved to', compute='_compute_facts')

    _pb_key_uniq = models.Constraint('unique(form_id, key)',
                                     'Each question on a form has its own key.')

    @api.depends('kind')
    def _compute_facts(self):
        for rec in self:
            spec = BUILTINS.get(rec.kind)
            rec.builtin = bool(spec)
            rec.locked = rec.kind in LOCKED
            rec.widget = spec['widget'] if spec else (CUSTOM_KINDS.get(rec.kind, ('', 'text'))[1])
            rec.store_to = spec['store'] if spec else 'the answers'

    @api.constrains('max_mb', 'min_words', 'max_words')
    def _check_limits(self):
        for rec in self:
            if rec.max_mb and not 1 <= rec.max_mb <= HARD_MAX_MB:
                raise ValidationError(_('A file can be at most %s MB.', HARD_MAX_MB))
            if rec.min_words < 0 or rec.max_words < 0 or (
                    rec.max_words and rec.min_words > rec.max_words):
                raise ValidationError(_('The fewest words must be less than the most words.'))

    def _pb_accept(self):
        """The `accept` attribute and the suffixes allowed."""
        self.ensure_one()
        kinds = [k for k in (self.file_kinds or 'pdf,doc').split(',') if k in FILE_KINDS]
        suffixes = [s for k in kinds for s in FILE_KINDS[k][0]]
        return kinds, suffixes


# =========================================================================
#  helpers
# =========================================================================
def _raw(records, fname):
    if not records:
        return {}
    records.flush_model([fname])
    records.env.cr.execute(SQL('SELECT id, %s FROM %s WHERE id IN %s',
                               SQL.identifier(fname), SQL.identifier(records._table),
                               tuple(records.ids)))
    return {rid: (val or {}) for rid, val in records.env.cr.fetchall()}


def _copy_raw(env, table, src_id, dst_id, columns):
    for col in columns:
        env.cr.execute(SQL('UPDATE %s d SET %s = s.%s FROM %s s WHERE d.id = %s AND s.id = %s',
                           SQL.identifier(table), SQL.identifier(col), SQL.identifier(col),
                           SQL.identifier(table), dst_id, src_id))


def _fill_one(record, fname, raw, langs):
    en = raw.get('en_US') or ''
    words = FORM_I18N.get(en)
    if not en or not words:
        return 0
    todo = {lg: words[lg] for lg in langs if lg not in raw and words.get(lg)}
    if not todo:
        return 0
    record.update_field_translations(fname, todo)
    return len(todo)


def _https(value):
    return bool(re.match(r'^https?://[^\s/$.?#][^\s]*$', value or '', re.I))


def _phone(value, country):
    """The number in international format, '' when it cannot be checked,
    False when it is plainly not a phone number."""
    digits = re.sub(r'[^\d]', '', value or '')
    if len(digits) < 6 or len(digits) > 17:
        return False
    if not country:
        return ''
    try:
        from odoo.addons.phone_validation.tools import phone_validation
    except ImportError:
        return ''
    try:
        return phone_validation.phone_format(value, country.code, country.phone_code,
                                             force_format='INTERNATIONAL', raise_exception=True)
    except UserError:
        return False
    except Exception:                   # noqa: BLE001 — a missing library never refuses
        return ''


def _check_file(env, fld, upload):
    """(problem sentence or None, bytes, mimetype)."""
    _t = env._
    kinds, suffixes = fld._pb_accept()
    max_mb = min(fld.max_mb or 5, HARD_MAX_MB)
    name = upload.filename or ''
    suffix = name.lower().rsplit('.', 1)[-1] if '.' in name else ''
    data = upload.read(max_mb * 1024 * 1024 + 1)
    if len(data) > max_mb * 1024 * 1024:
        return _t('“%(name)s” is larger than %(mb)s MB. Choose a smaller file.',
                  name=name, mb=max_mb), b'', ''
    if not data:
        return _t('“%s” is empty. Choose the file again.', name), b'', ''
    if suffix not in suffixes:
        words = ', '.join(FILE_KINDS[k][1] for k in kinds)
        return _t('“%(name)s” is not a file we can take here. Use %(kinds)s.',
                  name=name, kinds=words), b'', ''
    if not any(data.startswith(m) for m in MAGIC.get(suffix, (b'',))):
        return _t('“%(name)s” is not really a %(kind)s file. Choose the original file.',
                  name=name, kind=suffix.upper()), b'', ''
    return None, data, MIMETYPES.get(suffix, 'application/octet-stream')


# =========================================================================
#  The role owns a copy; the candidate carries the answers
# =========================================================================
class HiringRequestForm(models.Model):
    _inherit = 'pb.hiring.requisition'

    pb_form_id = fields.Many2one('pb.hiring.form', string='Application form',
                                 copy=False, ondelete='set null',
                                 help="This role's own copy. Changing a template "
                                      "never changes it.")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.pb_form_id:
                leg(self.env, 'the application form for role %s' % rec.id,
                    rec._pb_ensure_form)
        return records

    def _pb_ensure_form(self):
        self.ensure_one()
        req = self.sudo()
        if req.pb_form_id:
            return req.pb_form_id
        tpl = self.env['pb.hiring.form']._default_template(req.company_id)
        if not tpl:
            return self.env['pb.hiring.form']
        form = tpl._pb_clone({'requisition_id': req.id})
        req.write({'pb_form_id': form.id})
        return form

    @api.model
    def _pb_fill_forms(self):
        """The upgrade half: every role without a form gets its own copy."""
        todo = self.sudo().with_context(active_test=False).search([('pb_form_id', '=', False)])
        n = 0
        for rec in todo:
            if leg(self.env, 'the application form for role %s' % rec.id, rec._pb_ensure_form):
                n += 1
        return n


class HiringApplicantForm(models.Model):
    _inherit = 'hr.applicant'

    pb_form_id = fields.Many2one('pb.hiring.form', string='Application form used',
                                 copy=False, ondelete='set null')
    pb_form_answers = fields.Json(string='Answers', copy=False)
    pb_country_id = fields.Many2one('res.country', string='Country they live in')
    pb_lang = fields.Char(string='Language they applied in', copy=False)
    pb_consent_on = fields.Datetime(string='Agreed on', copy=False, readonly=True)
    pb_consent_text = fields.Text(string='What they agreed to', copy=False, readonly=True)
    pb_possible_duplicate_id = fields.Many2one(
        'hr.applicant', string='Possibly the same person as', copy=False,
        ondelete='set null', index='btree_not_null')
    pb_same_person_id = fields.Many2one(
        'hr.applicant', string='The same person as', copy=False, ondelete='set null')

    def write(self, vals):
        if not self.env.su and set(vals) & {'pb_consent_on', 'pb_consent_text'}:
            raise AccessError(_('What a candidate agreed to is recorded when they apply and cannot be edited.'))
        return super().write(vals)

    def _pb_find_duplicate(self):
        """Same email or phone, same company, applied in the last six months."""
        self.ensure_one()
        app = self.sudo()
        ors = []
        if app.email_normalized:
            ors.append([('email_normalized', '=', app.email_normalized)])
        if app.partner_phone_sanitized:
            ors.append([('partner_phone_sanitized', '=', app.partner_phone_sanitized)])
        if not ors:
            return self.browse()
        dom = ors[0] if len(ors) == 1 else ['|'] + ors[0] + ors[1]
        since = fields.Datetime.now() - timedelta(days=DUPLICATE_MONTHS * 30)
        return self.sudo().with_context(active_test=False).search(
            [('id', '!=', app.id), ('company_id', '=', app.company_id.id),
             ('create_date', '>=', since)] + dom, order='create_date desc, id desc', limit=1)

    def _pb_send_received(self):
        """The "Application received" email, in the language they applied in.
        Falls back to English when that language has no text, and says so on
        the timeline."""
        self.ensure_one()
        app = self.sudo()
        if not flag(self.env, P_CANDIDATE_MAIL) or not app.email_from:
            return False
        template = self.env['pb.hiring.message.template'].sudo().search([
            ('company_id', '=', app.company_id.id), ('key', '=', 'received')], limit=1)
        if not template:
            return False
        lang = app.pb_lang or 'en_US'
        fell_back = False
        if lang != 'en_US':
            raw = _raw(template, 'body').get(template.id) or {}
            if lang not in raw or not (raw.get(lang) or '').strip():
                fell_back = True
        used = 'en_US' if fell_back else lang
        rendered = template.with_context(lang=used)._render(app)
        company = app.company_id
        mail = self.env['mail.mail'].sudo().create({
            'subject': rendered['subject'], 'body_html': text_html(rendered['body']),
            'email_to': app.email_from,
            'email_from': company.email or app.job_id.user_id.email_formatted or False,
            'model': 'hr.applicant', 'res_id': app.id, 'auto_delete': False})
        if fell_back:
            app.message_post(
                body=Markup('<p>%s</p>') % _(
                    'The confirmation email went out in English: the "Application received" '
                    'email has no %s version yet.', lang_word(lang)),
                message_type='comment', subtype_xmlid='mail.mt_note',
                author_id=company.partner_id.id)
        return mail


# =========================================================================
#  The facade: the builder's verbs, the drawer, the card, set-up
# =========================================================================
class PbHiringForms(models.AbstractModel):
    _inherit = 'pb.hiring'

    # ------------------------------------------------------------ reads
    @api.model
    def _forms_scope(self):
        return self.env.companies.ids or [self.env.company.id]

    @api.model
    def _forms_langs(self):
        installed = self.env['pb.hiring.form']._pb_installed_langs()
        on_site = set()
        try:
            for site in self.env['website'].sudo().search([('company_id', 'in', self._forms_scope())]):
                on_site |= set(site.language_ids.mapped('code'))
        except Exception:               # noqa: BLE001 — no website, no switch
            pass
        return [{'code': c, 'label': lang_word(c), 'short': LANG_SHORT[c],
                 'installed': c in installed, 'on_website': c in on_site or c == 'en_US'}
                for c in FORM_LANGS]

    @api.model
    def _form_row(self, form, missing=None):
        missing = missing if missing is not None else form._pb_missing()
        return {
            'id': form.id, 'name': form.with_context(lang='en_US').name or '',
            'is_template': bool(form.is_template), 'is_default': bool(form.is_default),
            'template_key': form.template_key or '',
            'requisition_id': form.requisition_id.id or False,
            'role': form.requisition_id.title or '',
            'role_state': form.requisition_id.state or '',
            'origin': form.origin_template_id.with_context(lang='en_US').name or '',
            'n_fields': len(form.field_ids),
            'missing': {lg: len(rows) for lg, rows in missing.items()},
            'languages': form._pb_langs(),
        }

    @api.model
    def get_forms(self):
        if not self._can_recruit():
            raise AccessError(_('Application forms are for the hiring team.'))
        Form = self.env['pb.hiring.form'].sudo()
        co = self._forms_scope()
        for company in self.env['res.company'].sudo().browse(co):
            if not Form.search_count([('company_id', '=', company.id), ('is_template', '=', True)]):
                Form._ensure_templates(company)
        templates = Form.search([('company_id', 'in', co), ('is_template', '=', True)])
        roles = Form.search([('company_id', 'in', co), ('is_template', '=', False),
                             ('requisition_id', '!=', False),
                             ('requisition_id.state', '!=', 'closed')],
                            limit=300)
        reqs = self.env['pb.hiring.requisition'].sudo().search(
            [('company_id', 'in', co), ('state', '!=', 'closed')],
            order='id desc', limit=300)
        used = {}
        for f in roles:
            if f.origin_template_id:
                used.setdefault(f.origin_template_id.id, []).append(f.requisition_id.title or '')
        return {
            'can_edit': self._can_write(),
            'templates': [dict(self._form_row(t), used_by=used.get(t.id, [])) for t in templates],
            'role_forms': [self._form_row(f) for f in roles],
            'roles': [{'id': r.id, 'title': r.title or '', 'state': r.state,
                       'form_id': r.pb_form_id.id or False,
                       'form_name': r.pb_form_id.with_context(lang='en_US').name or ''}
                      for r in reqs],
            'languages': self._forms_langs(),
            'brand': self.env.company._hiring_brand(),
            'retention_months': self.env.company.pb_retention_months or 12,
        }

    @api.model
    def _pb_form(self, form_id):
        form = self.env['pb.hiring.form'].sudo().with_context(active_test=False).browse(
            as_id(form_id)).exists()
        if not form or form.company_id.id not in self.env.user.company_ids.ids:
            raise UserError(_('That form is no longer there.'))
        return form

    @api.model
    def get_form(self, form_id, lang='en_US'):
        if not self._can_recruit():
            raise AccessError(_('Application forms are for the hiring team.'))
        lang = lang if lang in FORM_LANGS else 'en_US'
        form = self._pb_form(form_id)
        missing = form._pb_missing([c for c in FORM_LANGS if c != 'en_US'])
        miss_ids = {lg: {(m['field_id'], m['what']) for m in rows} for lg, rows in missing.items()}
        installed = self.env['pb.hiring.form']._pb_installed_langs()
        read_lang = lang if lang in installed else 'en_US'
        loc = form.with_context(lang=read_lang)
        en = form.with_context(lang='en_US')
        flds = []
        present = set()
        for f_loc, f_en in zip(loc.field_ids.sorted('sequence'), en.field_ids.sorted('sequence')):
            present.add(f_en.kind if f_en.builtin else '')
            label_icon = CUSTOM_KINDS.get(f_en.kind, (None, None, None))[2]
            flds.append({
                'id': f_en.id, 'key': f_en.key, 'kind': f_en.kind, 'widget': f_en.widget,
                'kind_label': ('Built-in' if f_en.builtin else CUSTOM_KINDS[f_en.kind][0]),
                'icon': label_icon or _builtin_icon(f_en.kind),
                'label': f_loc.label or '', 'label_en': f_en.label or '',
                'help': f_loc.help or '', 'help_en': f_en.help or '',
                'placeholder': f_loc.placeholder or '', 'placeholder_en': f_en.placeholder or '',
                'options': f_loc.options or '', 'options_en': f_en.options or '',
                'required': bool(f_en.required or f_en.locked), 'locked': bool(f_en.locked),
                'builtin': bool(f_en.builtin), 'min_words': f_en.min_words,
                'max_words': f_en.max_words, 'file_kinds': f_en.file_kinds or '',
                'max_mb': f_en.max_mb or 5, 'portfolio_mode': f_en.portfolio_mode or 'either',
                'missing': {lg: sorted(w for (fid, w) in ids if fid == f_en.id)
                            for lg, ids in miss_ids.items()},
                'store_to': f_en.store_to or '',
            })
        req = form.requisition_id
        public = ''
        if req and req.job_id and req.job_id.is_published:
            public = '/jobs/apply/%s' % self.env['ir.http']._slug(req.job_id)
        return {
            'form': {
                'id': form.id, 'name': loc.name or '', 'name_en': en.name or '',
                'is_template': bool(form.is_template), 'is_default': bool(form.is_default),
                'template_key': form.template_key or '', 'active': bool(form.active),
                'requisition_id': req.id or False, 'role': req.title or '',
                'origin': form.origin_template_id.with_context(lang='en_US').name or '',
                'languages': form._pb_langs(),
                'consent_text': loc.consent_text or '', 'consent_text_en': en.consent_text or '',
                'consent_missing': {lg: ((False, 'consent_text') in ids) for lg, ids in miss_ids.items()},
                'preview_url': '/hiring/preview/%s' % form.id,
                'public_url': public,
            },
            'lang': lang, 'read_lang': read_lang,
            'fields': flds,
            'missing': {lg: len(rows) for lg, rows in missing.items()},
            'missing_list': {lg: rows for lg, rows in missing.items()},
            'addable_builtins': [{'key': k, 'label': BUILTINS[k]['label'], 'icon': _builtin_icon(k)}
                                 for k in BUILTIN_ORDER if k not in present],
            'kinds': [{'key': k, 'label': v[0], 'icon': v[2]} for k, v in CUSTOM_KINDS.items()],
            'can_edit': self._can_write(),
        }

    # ------------------------------------------------------------ writes
    def _form_lang(self, payload):
        lang = payload.get('lang') or 'en_US'
        if lang not in FORM_LANGS:
            raise UserError(_('That language is not one a form is written in.'))
        if lang not in self.env['pb.hiring.form']._pb_installed_langs():
            raise UserError(_('%s is not installed on this system — ask your administrator to add it.',
                              lang_word(lang)))
        return lang

    def _act_form_save(self, payload):
        """{id, lang, values: {name?, consent_text?, language_codes?}}"""
        self._require_write()
        form = self._pb_form(payload.get('id'))
        lang = self._form_lang(payload)
        values = payload.get('values') or {}
        old = {}
        for fname in FORM_TRANSLATED:
            if fname in values:
                text = str(values[fname] or '').strip()
                if fname == 'name' and not text and lang == 'en_US':
                    raise UserError(_('A form needs a name.'))
                old[fname] = form.with_context(lang=lang)[fname] or ''
                form.update_field_translations(fname, {lang: text or False})
        if 'language_codes' in values:
            codes = [c for c in (values['language_codes'] or []) if c in FORM_LANGS]
            old['language_codes'] = form._pb_langs()
            form.write({'language_codes': ','.join(['en_US'] + [c for c in codes if c != 'en_US'])})
        return {'id': form.id, 'old': old, 'note': _('Saved.')}

    def _act_form_field_save(self, payload):
        """{id, lang, values: {label, help, placeholder, options, required,
        min_words, max_words, file_kinds, max_mb, portfolio_mode}}"""
        self._require_write()
        fld = self.env['pb.hiring.form.field'].sudo().browse(as_id(payload.get('id'))).exists()
        if not fld:
            raise UserError(_('That question is no longer on the form.'))
        self._pb_form(fld.form_id.id)
        lang = self._form_lang(payload)
        values = dict(payload.get('values') or {})
        loc = fld.with_context(lang=lang)
        old = {}
        if 'required' in values and not values['required'] and fld.locked:
            raise UserError(_('%s is always asked — every application needs it. You can rename it.',
                              fld.with_context(lang='en_US').label))
        for fname in FIELD_TRANSLATED:
            if fname in values:
                text = str(values[fname] or '')
                text = text.strip() if fname != 'options' else '\n'.join(
                    o.strip() for o in text.split('\n') if o.strip())
                if fname == 'label' and not text and lang == 'en_US':
                    raise UserError(_('A question needs words — write the question first.'))
                if fname == 'label' and len(text) > 200:
                    raise UserError(_('Keep a question under 200 characters.'))
                old[fname] = loc[fname] or ''
                fld.update_field_translations(fname, {lang: text or False})
        plain = {}
        for fname in ('required', 'min_words', 'max_words', 'file_kinds', 'max_mb', 'portfolio_mode'):
            if fname in values:
                old[fname] = fld[fname]
                plain[fname] = values[fname]
        if 'file_kinds' in plain:
            kinds = [k for k in (plain['file_kinds'] or []) if k in FILE_KINDS] \
                if isinstance(plain['file_kinds'], list) else \
                [k for k in str(plain['file_kinds']).split(',') if k in FILE_KINDS]
            if not kinds:
                raise UserError(_('Pick at least one kind of file.'))
            plain['file_kinds'] = ','.join(kinds)
            old['file_kinds'] = fld.file_kinds or ''
        for fname in ('min_words', 'max_words', 'max_mb'):
            if fname in plain:
                try:
                    plain[fname] = int(plain[fname] or 0)
                except (TypeError, ValueError):
                    raise UserError(_('Use a whole number.'))
        if plain:
            fld.write(plain)
        missing = fld.form_id._pb_missing([c for c in FORM_LANGS if c != 'en_US'])
        return {'id': fld.id, 'old': old,
                'missing': {lg: len(rows) for lg, rows in missing.items()},
                'note': _('Saved.')}

    def _act_form_field_add(self, payload):
        """{form_id, kind, lang?} — a new question just above the consent."""
        self._require_write()
        form = self._pb_form(payload.get('form_id'))
        kind = payload.get('kind')
        Field = self.env['pb.hiring.form.field'].sudo().with_context(lang='en_US')
        keys = set(form.field_ids.mapped('key'))
        if kind in BUILTINS:
            if kind in keys:
                raise UserError(_('%s is already on this form.', BUILTINS[kind]['label']))
            row = _b(kind)
            if kind in ('city', 'relocation', 'expected_pay'):
                row['required'] = True
        elif kind in CUSTOM_KINDS:
            label = str(payload.get('label') or '').strip() or {
                'yes_no': 'A yes or no question', 'file': 'A file we should see',
                'link': 'A link we should see', 'choice': 'Pick one',
                'multi_choice': 'Pick any that apply', 'date': 'A date',
                'number': 'A number',
            }.get(kind, 'Your question')
            base = 'q_' + _slug(label)
            key, n = base, 2
            while key in keys:
                key, n = '%s_%s' % (base, n), n + 1
            row = _q(kind, key, label)
            if kind in ('choice', 'multi_choice'):
                row['options'] = 'First option\nSecond option'
            if kind == 'file':
                row['file_kinds'] = 'pdf,doc,image'
        else:
            raise UserError(_('Pick what kind of question to add.'))
        consent = form.field_ids.filtered(lambda f: f.kind == 'consent')[:1]
        seq = (consent.sequence - 1) if consent else (max(form.field_ids.mapped('sequence') or [0]) + 10)
        row.update(form_id=form.id, sequence=seq)
        fld = Field.create(row)
        self._pb_resequence(form)
        self.env['pb.hiring.form']._fill_translations(form)
        return {'id': fld.id, 'key': fld.key, 'note': _('Question added. Write it in your words.')}

    def _act_form_field_remove(self, payload):
        self._require_write()
        fld = self.env['pb.hiring.form.field'].sudo().browse(as_id(payload.get('id'))).exists()
        if not fld:
            raise UserError(_('That question is no longer on the form.'))
        self._pb_form(fld.form_id.id)
        if fld.locked:
            raise UserError(_('%s is always asked, so it cannot be removed. You can rename it.',
                              fld.with_context(lang='en_US').label))
        saved = {'form_id': fld.form_id.id, 'sequence': fld.sequence, 'kind': fld.kind,
                 'key': fld.key, 'required': fld.required, 'min_words': fld.min_words,
                 'max_words': fld.max_words, 'file_kinds': fld.file_kinds or '',
                 'max_mb': fld.max_mb, 'portfolio_mode': fld.portfolio_mode,
                 'raw': {f: _raw(fld, f).get(fld.id) or {} for f in FIELD_TRANSLATED}}
        label = fld.with_context(lang='en_US').label
        fld.unlink()
        return {'saved': saved, 'note': _('“%s” removed. Answers people already gave are kept.', label)}

    def _act_form_field_restore(self, payload):
        """Undo a removal: the question back, every language of it."""
        self._require_write()
        saved = payload.get('saved') or {}
        form = self._pb_form(saved.get('form_id'))
        if saved.get('key') in form.field_ids.mapped('key'):
            return {'note': _('It is already back.')}
        raw = saved.get('raw') or {}
        Field = self.env['pb.hiring.form.field'].sudo().with_context(lang='en_US')
        fld = Field.create({
            'form_id': form.id, 'sequence': saved.get('sequence') or 10,
            'kind': saved['kind'], 'key': saved['key'],
            'label': (raw.get('label') or {}).get('en_US') or saved['key'],
            'required': bool(saved.get('required')), 'min_words': saved.get('min_words') or 0,
            'max_words': saved.get('max_words') or 0, 'file_kinds': saved.get('file_kinds') or '',
            'max_mb': saved.get('max_mb') or 5, 'portfolio_mode': saved.get('portfolio_mode') or 'either'})
        for fname in FIELD_TRANSLATED:
            vals = {lg: v for lg, v in (raw.get(fname) or {}).items()
                    if lg in self.env['pb.hiring.form']._pb_installed_langs()}
            if vals:
                fld.update_field_translations(fname, vals)
        return {'id': fld.id, 'note': _('Put back.')}

    @api.model
    def _pb_resequence(self, form):
        """Consent is always last; sequences are clean tens."""
        flds = form.field_ids.sorted(lambda f: (f.kind == 'consent', f.sequence, f.id))
        for i, f in enumerate(flds):
            if f.sequence != (i + 1) * 10:
                f.sequence = (i + 1) * 10

    def _act_form_reorder(self, payload):
        """{form_id, ids: [field ids in the new order]}"""
        self._require_write()
        form = self._pb_form(payload.get('form_id'))
        ids = [as_id(i) for i in payload.get('ids') or []]
        before = form.field_ids.sorted('sequence').ids
        order = {fid: i for i, fid in enumerate(ids)}
        for f in form.field_ids:
            if f.id in order:
                f.sequence = (order[f.id] + 1) * 10
        self._pb_resequence(form)
        return {'before': before, 'note': _('New order saved.')}

    def _act_form_copy_to_role(self, payload):
        """{template_id, requisition_id} — the role gets its own copy of the
        chosen form; its old form is put away, answers already given keep
        pointing at it."""
        self._require_write()
        src = self._pb_form(payload.get('template_id'))
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(payload.get('requisition_id'))).exists()
        if not req:
            raise UserError(_('Choose a role.'))
        if req.company_id != src.company_id:
            raise UserError(_('That role belongs to another company — use one of its own forms.'))
        old = req.pb_form_id
        if old:
            old.write({'active': False})
        new = src._pb_clone({'requisition_id': req.id})
        req.write({'pb_form_id': new.id})
        return {'id': new.id, 'old_id': old.id or False,
                'note': _('%(role)s now uses a copy of %(form)s. Answers already given are kept.',
                          role=req.title or '', form=src.with_context(lang='en_US').name)}

    def _act_form_restore_role(self, payload):
        """Undo "Use this form for…": the role's previous form comes back."""
        self._require_write()
        req = self.env['pb.hiring.requisition'].sudo().browse(
            as_id(payload.get('requisition_id'))).exists()
        old = self.env['pb.hiring.form'].sudo().with_context(active_test=False).browse(
            as_id(payload.get('old_id'))).exists()
        if not req or not old:
            raise UserError(_('The earlier form is no longer there.'))
        current = req.pb_form_id
        if current and current != old:
            current.write({'active': False})
        old.write({'active': True})
        req.write({'pb_form_id': old.id})
        return {'id': old.id, 'note': _('The earlier form is back on %s.', req.title or '')}

    def _act_form_set_default(self, payload):
        self._require_write()
        form = self._pb_form(payload.get('id'))
        if not form.is_template:
            raise UserError(_("Only a template can be the default. Make this one a template first."))
        before = self.env['pb.hiring.form'].sudo().search([
            ('company_id', '=', form.company_id.id), ('is_template', '=', True),
            ('is_default', '=', True)])
        before.write({'is_default': False})
        form.write({'is_default': True})
        return {'old_id': before[:1].id or False,
                'note': _('New roles start with %s from now on. Roles that already have a form keep it.',
                          form.with_context(lang='en_US').name)}

    def _act_form_new_template(self, payload):
        """{name, from_id} — a new template, copied from any form."""
        self._require_write()
        src = self._pb_form(payload.get('from_id'))
        name = str(payload.get('name') or '').strip()
        if not name:
            raise UserError(_('Name the new template.'))
        new = src._pb_clone({'name': name, 'is_template': True, 'requisition_id': False,
                             'origin_template_id': False, 'sequence': 90})
        return {'id': new.id, 'note': _('%s is a template now.', name)}

    def _act_form_archive(self, payload):
        """Retire a template nobody needs (never a role's form, never the default)."""
        self._require_write()
        form = self._pb_form(payload.get('id'))
        if not form.is_template:
            raise UserError(_("A role's form is changed from the role, not removed."))
        if form.is_default:
            raise UserError(_('This is the default for new roles. Make another template the default first.'))
        if payload.get('undo'):
            form.write({'active': True})
            return {'id': form.id, 'note': _('Template back.')}
        form.write({'active': False})
        return {'id': form.id, 'note': _('Template put away. Roles that copied it keep their own forms.')}

    # ------------------------------------------------------------ the person
    def _act_same_person(self, payload):
        """"Same person": linked both ways, no merge (a merge arrives later)."""
        app = self._applicant(payload.get('applicant_id'))
        self._require_recruit(app.pb_requisition_id)
        other = app.pb_possible_duplicate_id or app.pb_same_person_id
        if not other:
            raise UserError(_('There is no earlier record to link to.'))
        if payload.get('undo'):
            (app | other).write({'pb_same_person_id': False})
            return {'note': _('No longer marked as the same person.')}
        app.write({'pb_same_person_id': other.id})
        other.write({'pb_same_person_id': app.id})
        return {'note': _('Marked as the same person as %s. Both records stay; nothing is merged.',
                          other.partner_name or '')}

    @api.model
    def _answers(self, app, can_recruit):
        """Every question of the form they answered, in its order, with the
        English label a recruiter reads."""
        form = app.pb_form_id.sudo().with_context(lang='en_US', active_test=False)
        answers = app.pb_form_answers if isinstance(app.pb_form_answers, dict) else {}
        if not form and not answers:
            return []
        docs = self.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'hr.applicant'), ('res_id', '=', app.id),
             ('pb_form_key', '!=', False)], ['id', 'name', 'pb_form_key'])
        by_key = {}
        for d in docs:
            by_key.setdefault(d['pb_form_key'], []).append(
                {'id': d['id'], 'name': d['name'] or '', 'url': '/web/content/%s' % d['id']})
        out, seen = [], set()
        rows = [(f.key, f.label, f.widget, f.kind) for f in form.field_ids.sorted('sequence')]
        rows += [(k, k.replace('q_', '').replace('_', ' ').capitalize(), '', '')
                 for k in answers if k not in {r[0] for r in rows}]
        for key, label, widget, kind in rows:
            if key in seen or kind == 'consent':
                continue
            seen.add(key)
            val = answers.get(key)
            if kind == 'expected_pay' and not can_recruit:
                continue
            item = {'key': key, 'label': label or key, 'widget': widget, 'value': '',
                    'link': '', 'files': []}
            if isinstance(val, dict) and 'amount' in val:
                item['value'] = '{:,.0f} {}'.format(val['amount'] or 0, val.get('currency') or '').strip()
            elif isinstance(val, dict):
                item['link'] = val.get('link') or ''
                item['files'] = by_key.get(key, []) if can_recruit else []
                if not can_recruit and val.get('files'):
                    item['value'] = _('A file was sent (recruiters can open it)')
            elif isinstance(val, list):
                item['value'] = ', '.join(str(v) for v in val)
            elif kind == 'country' or widget == 'country':
                item['value'] = self.env['res.country'].sudo().browse(as_id(val)).exists().name or ''
            elif val is True:
                item['value'] = _('Yes')
            elif val in ('yes', 'no'):
                item['value'] = _('Yes') if val == 'yes' else _('No')
            elif isinstance(val, float):
                item['value'] = ('%g' % val)
            else:
                item['value'] = str(val or '')
            if widget == 'url' and item['value']:
                item['link'], item['value'] = item['value'], ''
            if widget == 'file':
                item['files'] = by_key.get(key, []) if can_recruit else []
            item['empty'] = not (item['value'] or item['link'] or item['files'])
            out.append(item)
        return out

    @api.model
    def get_candidate(self, applicant_id):
        res = super().get_candidate(applicant_id)
        app = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(res['id'])
        res['answers'] = self._safe(lambda: self._answers(app, res.get('can_recruit')), default=[])
        res['consent'] = {
            'on': str(app.pb_consent_on or ''), 'lang': lang_word(app.pb_lang),
            'text': app.pb_consent_text or '',
        } if app.pb_consent_on else None
        res['lang'] = lang_word(app.pb_lang) if app.pb_lang else ''
        res['country'] = app.pb_country_id.name or ''
        dup = app.pb_possible_duplicate_id
        same = app.pb_same_person_id
        other = same or dup
        res['duplicate'] = {
            'id': other.id, 'name': other.partner_name or other.email_from or '',
            'role': other.job_id.name or '', 'applied_on': str((other.create_date or fields.Datetime.now()).date()),
            'same': bool(same),
        } if other else None
        return res

    @api.model
    def _card(self, app, ivs, doc_count, req, now, today, can_recruit):
        card = super()._card(app, ivs, doc_count, req, now, today, can_recruit)
        if app.pb_same_person_id:
            card['chips'] = ([{'label': _('Applied before'), 'tone': 'info'}] + card['chips'])[:2]
        elif app.pb_possible_duplicate_id:
            card['chips'] = ([{'label': _('Possibly the same person'), 'tone': 'amber'}] + card['chips'])[:2]
            card['flags'] = card.get('flags', []) + ['duplicate']
        card['lang'] = LANG_SHORT.get(app.pb_lang or '', '') if app.pb_lang and app.pb_lang != 'en_US' else ''
        return card

    @api.model
    def get_timeline(self, applicant_id):
        items = super().get_timeline(applicant_id)
        app = self.env['hr.applicant'].sudo().with_context(active_test=False).browse(as_id(applicant_id))
        if app.pb_lang:
            for it in items:
                if it['kind'] == 'applied':
                    it['text'] = '%s (%s)' % (it['text'], lang_word(app.pb_lang))
        if app.pb_possible_duplicate_id:
            items.append({'at': str(app.create_date or ''), 'kind': 'note', 'by': '',
                          'text': _('Possibly the same person as %(who)s, who applied for %(job)s',
                                    who=app.pb_possible_duplicate_id.partner_name or '',
                                    job=app.pb_possible_duplicate_id.job_id.name or '')})
            items.sort(key=lambda r: r['at'], reverse=True)
        return items

    @api.model
    def get_requisition(self, requisition_id):
        row = super().get_requisition(requisition_id)
        req = self.env['pb.hiring.requisition'].sudo().browse(as_id(requisition_id))
        form = req.pb_form_id.with_context(lang='en_US')
        row['app_form'] = {
            'id': form.id, 'name': form.name or '',
            'origin': form.origin_template_id.name or '',
            'n_fields': len(form.field_ids),
            'preview_url': '/hiring/preview/%s' % form.id,
        } if form else None
        if self._can_write():
            row['form_templates'] = [{'id': t.id, 'name': t.with_context(lang='en_US').name or ''}
                                     for t in self.env['pb.hiring.form'].sudo().search(
                                         [('company_id', '=', req.company_id.id),
                                          ('is_template', '=', True)])]
        return row

    @api.model
    def get_setup(self):
        res = super().get_setup()
        status = self._safe(self._forms_status, default='')
        action = self._safe(lambda: self.env['ir.actions.actions']._for_xml_id(
            'pb_hiring.action_pb_hiring_forms'), default=False)
        for card in res.get('cards', []):
            if card['key'] == 'forms':
                card.update({'status': status or _('Templates and each role’s own form, in three languages.'),
                             'action': action, 'live': False})
        return res

    @api.model
    def _forms_status(self):
        Form = self.env['pb.hiring.form'].sudo()
        co = self._forms_scope()
        n_tpl = Form.search_count([('company_id', 'in', co), ('is_template', '=', True)])
        n_roles = Form.search_count([('company_id', 'in', co), ('is_template', '=', False),
                                     ('requisition_id.state', '!=', 'closed')])
        default = Form.search([('company_id', 'in', co), ('is_template', '=', True),
                               ('is_default', '=', True)], limit=1)
        text = _('%(t)s templates · %(r)s roles with their own form', t=n_tpl, r=n_roles)
        if default:
            text += ' · ' + _('new roles start with %s', default.with_context(lang='en_US').name)
        return text


def _builtin_icon(kind):
    return {'name': 'user', 'email': 'mail', 'phone': 'smartphone', 'country': 'globe',
            'city': 'mapPin', 'linkedin': 'link', 'cv': 'fileText', 'portfolio': 'briefcase',
            'expected_pay': 'banknote', 'authorization': 'idCard', 'relocation': 'plane',
            'motivation': 'pencil', 'consent': 'shieldCheck'}.get(kind, 'circle')


def seed_forms(env):
    """Called from `seed_journey` on every load: templates, translations,
    every role its own copy, the received email's other languages."""
    env['pb.hiring.form']._ensure_templates()
    env['pb.hiring.requisition']._pb_fill_forms()
    seed_received_i18n(env)


def seed_received_i18n(env):
    langs = [lg for lg in ('vi_VN', 'id_ID') if lg in env['pb.hiring.form']._pb_installed_langs()]
    if not langs:
        return 0
    Tpl = env['pb.hiring.message.template'].sudo().with_context(active_test=False)
    tpls = Tpl.search([('key', '=', 'received')])
    n = 0
    for fname, table in RECEIVED_I18N.items():
        for rid, raw in _raw(tpls, fname).items():
            en = raw.get('en_US') or ''
            words = table.get(en)
            if not words:
                continue
            todo = {lg: words[lg] for lg in langs if lg not in raw}
            if todo:
                Tpl.browse(rid).update_field_translations(fname, todo)
                n += len(todo)
    return n
