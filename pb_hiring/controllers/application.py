"""Tenant-scoped application forms: the page is drawn from the ROLE's own form
(RECRUIT P2), in the language of the page, and the server re-checks every
answer the page sends — files included — before a candidate exists.

The page keeps a root `<main class="pb-apply">` because the Rize site frame
(`rize_website.rz_application`) replaces exactly that node with its shell.
"""
import functools
import re
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from markupsafe import Markup

from odoo import fields, http
from odoo.http import request
from odoo.modules.module import get_module_path
from odoo.exceptions import UserError
from odoo.addons.website_hr_recruitment.controllers.main import WebsiteHrRecruitment
from ..models.forms_p2 import (COUNTRY_LANG, FILE_KINDS, FORM_LANGS, LANG_WORDS,
                               _raw, lang_word)
from ..models.channels_p7 import utm_record


def clean_url(value):
    try:
        parts = urlsplit(value or '')
        if parts.scheme not in ('https', 'http'):
            return ''
        # Do not retain arbitrary URL tokens or fragments in candidate records.
        query = urlencode([(k, v[:200]) for k, v in parse_qsl(parts.query) if k.startswith('utm_')])
        return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ''))[:2000]
    except ValueError:
        return ''


@functools.lru_cache(maxsize=1)
def _icon_paths():
    """The Lucide paths of the ONE icon registry (pb_import_kit's `IC`), read
    once, so the public page draws the same icons as the product."""
    path = get_module_path('pb_import_kit')
    out = {}
    if not path:
        return out
    try:
        with open(path + '/static/src/js/import_icons.js', encoding='utf-8') as f:
            for m in re.finditer(r"^\s+(\w+):\s*'(.*)',\s*$", f.read(), re.M):
                out[m.group(1)] = m.group(2)
    except OSError:
        pass
    return out


def ic(name, size=16):
    paths = _icon_paths()
    return Markup(
        '<svg width="%s" height="%s" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">%s</svg>'
    ) % (size, size, Markup(paths.get(name) or paths.get('check') or ''))


def chrome(env):
    """Every sentence of the page that is not the talent lead's own words, in
    the page's language (`.po`: vi_VN and id_ID)."""
    _t = env._
    return {
        'back': _t('All open roles'),
        'lede': _t('A meaningful next step starts with a conversation.'),
        'progress': _t('{n} of {m} answered'),
        'required': _t('Required'),
        'optional': _t('Optional'),
        'drop': _t('Drop your file here, or choose one'),
        'drop_change': _t('Choose a different file'),
        'or': _t('or'),
        'upload_file': _t('Upload a file'),
        'paste_link': _t('Paste a link'),
        'choose_country': _t('Choose your country'),
        'choose_one': _t('Choose one'),
        'yes': _t('Yes'),
        'no': _t('No'),
        'send': _t('Send my application'),
        'sending': _t('Sending…'),
        'reassure': _t('Only the hiring team for this role sees your application.'),
        'preview_banner': _t('Preview — nothing is sent from this page.'),
        'english_mark': _t('(English)'),
        'words': _t('{n} words'),
        'phone_hint': _t('Include the country code, like +{code}.'),
        'err_email': _t('Enter an email address like name@example.com.'),
        'err_url': _t('Paste a full link that starts with https://'),
        'err_big': _t('This file is larger than {mb} MB. Choose a smaller file.'),
        'err_kind': _t('This kind of file cannot be sent here.'),
        'err_words': _t('Write between {min} and {max} words. You have {n}.'),
        'summary_one': _t('One answer needs a look before you send.'),
        'summary_many': _t('{n} answers need a look before you send.'),
        'files_again': _t('Files are not kept when a send fails — please choose them again.'),
        'done_eyebrow': _t('Application received'),
        'next_title': _t('What happens next'),
        'next_1': _t('A person on the hiring team reads every application, usually within two weeks.'),
        'next_2': _t('If your experience fits the role, they contact you to arrange a first conversation.'),
        'other_roles': _t('See other open roles'),
        'lang_label': _t('Language'),
        'form_title': _t('Your application'),
    }


class HiringApplications(WebsiteHrRecruitment):
    def _pb_hiring_public_job(self, job):
        # The rule lives on hr.job so the careers page can ask it too.
        job = job.sudo().exists()
        return job if job.pb_hiring_accepts_applications(request.website) else None

    def _pb_hiring_touch(self, kwargs):
        touch = {key: str(kwargs.get('utm_' + key) or '')[:200] for key in ('source', 'medium', 'campaign', 'term', 'content')}
        touch.update({'referrer': clean_url(request.httprequest.referrer),
                      'landing_url': clean_url(request.httprequest.url),
                      'at': fields.Datetime.to_string(fields.Datetime.now())})
        stored = request.session.get('pb_hiring_attribution') or {}
        if not stored:
            stored['first'] = touch
        if any(touch[k] for k in ('source', 'medium', 'campaign')) or not stored.get('latest'):
            stored['latest'] = touch
        request.session['pb_hiring_attribution'] = stored
        return stored

    @http.route()
    def jobs(self, **kwargs):
        self._pb_hiring_touch(kwargs)
        return super().jobs(**kwargs)

    @http.route()
    def job(self, job, **kwargs):
        self._pb_hiring_touch(kwargs)
        return super().job(job, **kwargs)

    # ------------------------------------------------------------ the form
    def _pb_role_and_form(self, job):
        req = request.env['pb.hiring.requisition'].sudo().search(
            [('job_id', '=', job.id)], order='id desc', limit=1)
        form = req.pb_form_id if req else False
        if req and not form:
            form = req._pb_ensure_form()
        if not form:
            form = request.env['pb.hiring.form'].sudo()._default_template(job.company_id)
        return req, form

    def _pb_role_country(self, job, req):
        return (req.country_id if req else False) or job.address_id.country_id or job.company_id.country_id

    # ------------------------------------------------------------ languages
    def _pb_frontend_langs(self):
        try:
            return {lg.code: lg for lg in request.website.language_ids}
        except Exception:               # noqa: BLE001 — no website, one language
            return {}

    def _pb_bare_path(self):
        path = request.httprequest.path
        codes = {lg.url_code for lg in request.env['res.lang'].sudo().search([('active', '=', True)])}
        parts = path.split('/')
        if len(parts) > 2 and parts[1] in codes:
            parts.pop(1)
        return '/'.join(parts) or '/'

    def _pb_lang_url(self, code, path=None):
        path = path or self._pb_bare_path()
        default = request.website.default_lang_id.code if request.website else 'en_US'
        if code == default:
            return path
        lang = request.env['res.lang'].sudo().search([('code', '=', code)], limit=1)
        return '/%s%s' % (lang.url_code or code, path)

    def _pb_pills(self, form):
        site = self._pb_frontend_langs()
        cur = request.env.lang
        out = []
        for code in form._pb_langs():
            if code in site:
                qs = request.httprequest.query_string.decode()
                url = self._pb_lang_url(code) + ('?' + qs if qs else '')
                out.append({'code': code, 'label': LANG_WORDS.get(code, code),
                            'url': url, 'on': code == cur})
        return out if len(out) > 1 else []

    # ------------------------------------------------------------ the GET
    @http.route()
    def jobs_apply(self, job, **kwargs):
        job = self._pb_hiring_public_job(job)
        if not job:
            return request.not_found()
        req, form = self._pb_role_and_form(job)
        # First visit, no language chosen yet: the role's market picks it.
        if not request.httprequest.cookies.get('frontend_lang') and request.website:
            default = request.website.default_lang_id.code
            country = self._pb_role_country(job, req)
            want = COUNTRY_LANG.get(country.code if country else '')
            if want and request.env.lang == default and want != default \
                    and want in self._pb_frontend_langs() and form and want in form._pb_langs():
                qs = request.httprequest.query_string.decode()
                return request.redirect(self._pb_lang_url(want) + ('?' + qs if qs else ''), code=302, local=True)
        self._pb_hiring_touch(kwargs)
        request.session['pb_application_opened'] = time.time()
        return self._pb_hiring_render(job, req, form)

    def _pb_fields(self, form, values, errors, preview, tx, currency, role_country):
        env = request.env
        _t = env._
        lang = env.lang
        missing = set()
        if preview and lang != 'en_US':
            for fname in ('label', 'help', 'placeholder', 'options'):
                for rid, raw in _raw(form.field_ids, fname).items():
                    if (raw.get('en_US') or '').strip() and lang not in raw:
                        missing.add((rid, fname))
        rows = []
        for fld in form.with_context(lang=lang).field_ids.sorted('sequence'):
            w = fld.widget
            need = bool(fld.required or fld.locked)
            label = fld.label or fld.key
            row = {
                'id': fld.id, 'key': fld.key, 'kind': fld.kind, 'widget': w,
                'label': label, 'help': fld.help or '', 'placeholder': fld.placeholder or '',
                'required': need, 'error': (errors or {}).get(fld.key) or '',
                'english': (fld.id, 'label') in missing,
                'value': (values or {}).get(fld.key, ''),
                'options': [(str(i), o) for i, o in enumerate(
                    [o for o in (fld.options or '').split('\n') if o.strip()])],
                'min_words': fld.min_words or 0, 'max_words': fld.max_words or 0,
            }
            if w in ('text', 'email', 'tel', 'url', 'textarea', 'number', 'date', 'money'):
                row['err_required'] = _t('Add your answer to “%s”.', label)
            elif w == 'country':
                row['err_required'] = _t('Choose the country you live in.')
            elif w in ('choice', 'yes_no'):
                row['err_required'] = _t('Choose an answer for “%s”.', label)
            elif w == 'multi':
                row['err_required'] = _t('Choose at least one answer for “%s”.', label)
                row['value'] = (values or {}).get(fld.key + '[]') or []
            elif w == 'consent':
                row['err_required'] = _t('Tick the box to agree before you send.')
                row['sentence'] = form.with_context(lang=lang)._pb_consent_sentence(form.company_id)
                row['english'] = preview and lang != 'en_US' and lang not in (
                    _raw(form, 'consent_text').get(form.id) or {})
            elif w in ('file', 'portfolio'):
                kinds, suffixes = fld._pb_accept()
                mb = min(fld.max_mb or 5, 15)
                row.update({
                    'accept': ','.join('.' + s for s in suffixes),
                    'suffixes': ','.join(suffixes), 'max_mb': mb,
                    'hint': _t('%(kinds)s · up to %(mb)s MB',
                               kinds=', '.join(FILE_KINDS[k][1] for k in kinds), mb=mb),
                    'mode': fld.portfolio_mode if w == 'portfolio' else 'file',
                    'link': (values or {}).get(fld.key + '_link', ''),
                })
                row['err_required'] = (_t('Choose a file for “%s”.', label) if row['mode'] == 'file'
                                       else _t('Paste a link for “%s”.', label) if row['mode'] == 'link'
                                       else _t('Upload a file or paste a link for “%s”.', label))
            if w == 'money':
                row['currency'] = currency
                row['suffix'] = _t('%s per month', currency) if currency else ''
            if w == 'textarea' and (row['min_words'] or row['max_words']):
                lo, hi = row['min_words'], row['max_words']
                row['words_hint'] = (_t('Between %(min)s and %(max)s words', min=lo, max=hi) if lo and hi
                                     else _t('At least %s words', lo) if lo else _t('At most %s words', hi))
            if w == 'country' and not row['value'] and role_country:
                row['value'] = str(role_country.id)
            rows.append(row)
        return rows

    def _pb_hiring_render(self, job, req=None, form=None, values=None, errors=None, done=False,
                          preview=False, applicant=None, top_error=None):
        if form is None:
            req, form = self._pb_role_and_form(job)
        env = request.env
        lang = env.lang
        company = form.company_id if form else job.company_id
        role_country = self._pb_role_country(job, req) if job.id else (req.country_id if req else False)
        currency = ((req.country_id.currency_id if req and req.country_id else False)
                    or (role_country.currency_id if role_country else False)
                    or company.currency_id).name or ''
        tx = chrome(env)
        countries = env['res.country'].sudo().with_context(lang=lang).search([])
        countries = sorted(countries, key=lambda c: (c.name or '').lower())
        fields_ = self._pb_fields(form, values, errors, preview, tx, currency, role_country) if form else []
        n_errors = len([f for f in fields_ if f['error']])
        has_files = any(f['widget'] in ('file', 'portfolio') for f in fields_)
        action = '/hiring/apply/%s' % job.id if job.id else '#'
        if lang != (request.website.default_lang_id.code if request.website else 'en_US') and job.id:
            action = self._pb_lang_url(lang, action)
        summary = ''
        if n_errors:
            summary = tx['summary_one'] if n_errors == 1 else tx['summary_many'].replace('{n}', str(n_errors))
        done_title = done_line = next_3 = ''
        if done:
            # The whole name: the first word is the FAMILY name in Vietnamese
            # ("Cảm ơn bạn, Phạm." read as rude on the live page).
            who = ((applicant.partner_name if applicant else '') or '').strip()
            done_title = env._('Thank you, %s.', who) if who else env._('Thank you.')
            done_line = env._('Your application for %(role)s is with the %(brand)s hiring team.',
                              role=job.name or '', brand=company._hiring_brand())
            next_3 = (env._('Either way, you will hear from us. A confirmation is on its way to %s.',
                            applicant.email_from) if applicant and applicant.email_from
                      else env._('Either way, you will hear from us.'))
        return request.render('pb_hiring.application_journey', {
            'job': job, 'req': req, 'form': form, 'brand': company._hiring_brand(),
            'intro': tx['lede'],
            'values': values or {}, 'error': top_error, 'errors': errors or {},
            'summary': summary, 'files_again': tx['files_again'] if (n_errors and has_files) else '',
            'fields_': fields_, 'n_questions': len([f for f in fields_ if f['widget'] != 'consent']),
            'done': done, 'done_title': done_title, 'done_line': done_line, 'next_3': next_3,
            'preview': preview, 'pills': self._pb_pills(form) if form and not done else [],
            'tx': tx, 'ic': ic, 'countries': countries, 'currency': currency,
            'action': action, 'lang': lang, 'lang_word': lang_word(lang),
            'draft_key': 'pb_apply_%s_%s' % (job.id or 'preview', form.id if form else 0),
        })

    # ------------------------------------------------------------ the POST
    @http.route('/hiring/apply/<int:job_id>', type='http', auth='public', website=True, methods=['POST'])
    def pb_hiring_apply_submit(self, job_id, **post):
        job = self._pb_hiring_public_job(request.env['hr.job'].browse(job_id))
        if not job:
            return request.not_found()
        req, form = self._pb_role_and_form(job)
        if not form:
            return request.not_found()
        httpreq = request.httprequest
        values = httpreq.form.to_dict(flat=True)
        for key in list(httpreq.form.keys()):
            if len(httpreq.form.getlist(key)) > 1:
                values[key + '[]'] = httpreq.form.getlist(key)
        for fld in form.field_ids:
            if fld.widget == 'multi':
                values[fld.key + '[]'] = httpreq.form.getlist(fld.key)
        lang = request.env.lang if request.env.lang in FORM_LANGS else 'en_US'
        try:
            if post.get('company_website') or not request.session.get('pb_application_opened'):
                raise UserError(request.env._('Please open the application form and try again.'))
            if time.time() - request.session.get('pb_application_last', 0) < 30:
                raise UserError(request.env._('Your application is being processed. Please wait a moment before trying again.'))
        except UserError as err:
            return self._pb_hiring_render(job, req, form, values, top_error=str(err))
        currency = ((req.country_id.currency_id if req and req.country_id else False)
                    or job.company_id.currency_id).name or ''
        page_form = form.with_context(lang=lang)
        clean, answers, uploads, errors = page_form._pb_check(httpreq.form, httpreq.files,
                                                              {'currency': currency})
        if errors:
            return self._pb_hiring_render(job, req, form, values, errors=errors)
        attribution = request.session.get('pb_hiring_attribution') or {}
        extra = {'pb_first_touch': attribution.get('first', {}),
                 'pb_application_touch': attribution.get('latest', {})}
        for key in ('source', 'medium', 'campaign'):
            name = attribution.get('latest', {}).get(key)
            if name:
                # RECRUIT P7: case-insensitive, the seeded row first — never a
                # second `linkedin` beside `LinkedIn`.
                rec = utm_record(request.env, 'utm.' + key, name)
                if rec:
                    extra[key + '_id'] = rec.id
        if extra.get('source_id'):
            channel = request.env['pb.hiring.channel'].sudo()._for_source(
                job.company_id, request.env['utm.source'].sudo().browse(extra['source_id']))
            if channel:
                extra['pb_channel_id'] = channel.id
        with request.env.cr.savepoint():
            applicant = form._pb_make_applicant(job, req, clean, answers, uploads, lang, extra)
        request.session['pb_application_last'] = time.time()
        return self._pb_hiring_render(job, req, form, done=True, applicant=applicant)

    # ------------------------------------------------------------ preview
    @http.route('/hiring/preview/<int:form_id>', type='http', auth='user', website=True,
                methods=['GET'], multilang=False, sitemap=False)
    def pb_hiring_preview(self, form_id, lang=None, **kw):
        """The builder's live preview: the real page, in the language being
        edited, with sending switched off. For the hiring team only."""
        if not request.env['pb.hiring']._can_recruit():
            return request.not_found()
        form = request.env['pb.hiring.form'].sudo().with_context(active_test=False).browse(form_id).exists()
        if not form or form.company_id.id not in request.env.user.company_ids.ids:
            return request.not_found()
        installed = request.env['pb.hiring.form']._pb_installed_langs()
        if lang in FORM_LANGS and lang in installed:
            request.update_context(lang=lang)
        req = form.requisition_id
        job = req.job_id if req and req.job_id else request.env['hr.job'].sudo().new(
            {'name': req.title if req else form.with_context(lang=request.env.lang).name,
             'company_id': form.company_id.id})
        return self._pb_hiring_render(job, req, form, preview=True)
