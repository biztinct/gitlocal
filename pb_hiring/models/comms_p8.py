# -*- coding: utf-8 -*-
"""RECRUIT P8 — every candidate email through ONE mechanism, in the
candidate's language, edited by the talent lead (G-35, G-47, G-48).

  * `pb.hiring._mail_candidate(key, applicant, values, ...)` is the ONE door:
    the company's row of `pb.hiring.message.template` for that key, the
    language (`pb_lang` → the contact's language → English, and the timeline
    says so when English stood in for a missing version), the sender
    (`_sender`, never the person who pressed), the layout (paragraphs, an
    optional button, links that are links), the note on the timeline.
  * Every place that used to send an English-only `mail.template` to a
    candidate is re-pointed here by KEY (interview invitation / day before /
    half hour / called off / video link, through to the next round, the two
    rejections, the papers ask and reminder, the offer). The panel's and the
    recruiter's copies of the interview mails stay English (R11).
  * Hiring set-up → Emails and languages: the list with "when it goes" and a
    chip per language, an editor with English / Vietnamese / Bahasa tabs, a
    live preview, "Send me a test", "Reset to the standard text". Internal
    emails are listed read-only ("English only"), with a door for the
    administrator.

Why not `mail.template` for the candidate words: `comms_i18n_p8` says (its
body is term-translated on this build, a per-language editor would corrupt
the English).
"""

import json
import logging
import re
from pathlib import Path

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_amount, format_date, format_datetime

from .comms_i18n_p8 import (
    COMMON_TOKENS, EMAIL_KEYS, EXTRA, NEW_EMAILS, NEW_I18N, OLD_I18N,
    OPTIONAL_TOKENS, SAMPLE, TOKEN_WORDS, WHEN, WORDS,
)
from .hiring_common import P_CANDIDATE_MAIL, as_id, flag, leg

_logger = logging.getLogger(__name__)

LANGS = ('en_US', 'vi_VN', 'id_ID')
TOKEN_RE = re.compile(r'{{\s*(\w+)\s*}}')
URL_RE = re.compile(r'(https?://[^\s<>"\']+)')

#: The English-only candidate mail templates P8 replaces, and the key each
#: one became. The records stay (archived) so nothing that names them breaks.
RETIRED = {
    'pb_hiring.mail_template_interview_candidate': 'interview_invite',
    'pb_hiring.mail_template_interview_tomorrow': 'interview_tomorrow',
    'pb_hiring.mail_template_interview_soon': 'interview_soon',
    'pb_hiring.mail_template_interview_off': 'interview_off',
    'pb_hiring.mail_template_interview_video_link': 'interview_video',
    'pb_hiring.mail_template_candidate_next_round': 'next_round',
    'pb_hiring.mail_template_candidate_rejected': 'interview_reject',
    'pb_hiring.mail_template_docreq_ask': 'docreq_ask',
    'pb_hiring.mail_template_docreq_remind': 'docreq_remind',
    'pb_hiring.mail_template_offer_candidate': 'offer',
}
#: The shared interview mails also go to the panel and the recruiter, so
#: they are NOT archived: only their candidate copy moved.
SHARED = {'pb_hiring.mail_template_interview_tomorrow',
          'pb_hiring.mail_template_interview_soon',
          'pb_hiring.mail_template_interview_off',
          'pb_hiring.mail_template_interview_video_link'}

#: The internal emails, listed read-only on the Emails screen (English, R11).
INTERNAL = [
    ('mail_template_requisition_recruiter', 'A role is yours to recruit'),
    ('mail_template_request_ask', 'Please complete the hiring request'),
    ('mail_template_request_sent_in', 'A hiring request was sent in'),
    ('mail_template_request_agreed', 'A hiring request is agreed'),
    ('mail_template_budget_flag', 'A request is over budget'),
    ('mail_template_referral_recruiter', 'Somebody put a name forward'),
    ('mail_template_referral_open', 'A role is open to referrals'),
    ('mail_template_panel_invite', 'You are on an interview panel'),
    ('mail_template_interview_recruiter', 'An interview is in the diary'),
    ('mail_template_feedback_ask', 'What did you think'),
    ('mail_template_feedback_urgent', 'An opinion is late'),
    ('mail_template_feedback_lead', 'An opinion is two days late (talent lead)'),
    ('mail_template_docreq_escalated', 'Papers still missing after the deadline'),
    ('mail_template_offer_answered', 'The candidate has answered the offer'),
    ('mail_template_offer_signed', 'An offer is signed'),
    ('mail_template_prejoin_buddy', 'Name a buddy for a new joiner'),
    ('mail_template_join_week', 'A week before somebody joins'),
    ('mail_template_offer_closed', 'Somebody is joining'),
    ('mail_template_share_granted', 'You were given access to a candidate'),
    ('mail_template_agency_assigned', 'A role for an agency'),
]


def _json_seed():
    path = Path(__file__).parent.parent / 'data/journey_content.json'
    return {e['key']: e for e in json.loads(path.read_text())['emails']}


def lang_installed(env):
    return [lg for lg in LANGS
            if env['res.lang'].sudo().search_count([('code', '=', lg), ('active', '=', True)])]


# =========================================================================
#  The template: keys, the button, one language at a time
# =========================================================================
class HiringMessageTemplateP8(models.Model):
    _inherit = 'pb.hiring.message.template'

    key = fields.Selection(selection_add=[
        ('next_round', 'Through to the next round'),
        ('interview_invite', 'Your interview is arranged'),
        ('interview_tomorrow', 'Your interview is tomorrow'),
        ('interview_soon', 'Your interview is in half an hour'),
        ('interview_video', 'Your video link'),
        ('interview_off', 'Your interview has changed'),
        ('interview_reject', 'Not this time, after an interview'),
        ('docreq_ask', 'Please send us a few documents'),
        ('docreq_remind', 'Still waiting on a document or two'),
        ('offer', 'Our offer to you'),
    ], ondelete={k: 'cascade' for k in (
        'next_round', 'interview_invite', 'interview_tomorrow', 'interview_soon',
        'interview_video', 'interview_off', 'interview_reject', 'docreq_ask',
        'docreq_remind', 'offer')})
    button = fields.Char(string='Button words', translate=True,
                         help='The words on the button under the email, when the '
                              'email carries a link.')

    def _pb_raw(self, fname):
        from .forms_p2 import _raw
        return _raw(self, fname).get(self.id) or {}

    def _pb_has_lang(self, lang):
        """A language is THERE when it has its own subject and body (RC31:
        "missing" is no key, or an empty one — never "equals English")."""
        self.ensure_one()
        if lang == 'en_US':
            return True
        for fname in ('subject', 'body'):
            if not (self._pb_raw(fname).get(lang) or '').strip():
                return False
        return True

    def _pb_text(self, lang):
        """Subject, body and button in ONE language, with no fallback."""
        self.ensure_one()
        out = {}
        for fname in ('subject', 'body', 'button'):
            raw = self._pb_raw(fname)
            out[fname] = (raw.get(lang) if lang in raw else raw.get('en_US')) or ''
        return out

    def _pb_tokens(self, applicant, values=None, lang='en_US'):
        app = applicant.sudo() if applicant else applicant
        company = (app.company_id if app else False) or self.company_id
        recruiter = (app.pb_requisition_id.recruiter_id if app and app.pb_requisition_id
                     else False) or (app.user_id if app else False) or self.env.user
        full = (app.partner_name or '').strip() if app else ''
        role = ''
        if app:
            role = (app.pb_requisition_id.title if app.pb_requisition_id else '') \
                or app.job_id.name or ''
        tokens = {'first_name': full, 'name': full, 'role': role,
                  'brand': company._hiring_brand() if company else '',
                  'website': (company.website or '') if company else '',
                  'linkedin': (company.pb_hiring_linkedin or '') if company else '',
                  'company_intro': (company.pb_hiring_intro or '') if company else '',
                  'sender_name': recruiter.name or '', 'hr_name': recruiter.name or ''}
        for k, v in (values or {}).items():
            tokens[k] = v(lang) if callable(v) else v
        return tokens

    def _pb_render(self, applicant, values=None, lang='en_US', text=None):
        """{subject, body, button} with every token filled — or a UserError
        that names the details still missing (the editor shows it; nothing
        broken ever reaches a candidate)."""
        self.ensure_one()
        text = text or self._pb_text(lang)
        tokens = self._pb_tokens(applicant, values, lang)
        used = set(TOKEN_RE.findall((text['subject'] or '') + (text['body'] or '')))
        missing = sorted(k for k in used if not str(tokens.get(k) or '').strip()
                         and k not in OPTIONAL_TOKENS)
        if missing:
            raise UserError(_('Complete these message details first: %s', ', '.join(missing)))

        def fill(s):
            out = TOKEN_RE.sub(lambda m: str(tokens.get(m[1]) or ''), s or '')
            # "{{website}} | {{linkedin}}" with neither set leaves a lone "|"
            # (found in the P8 walk): a line of separators only goes.
            return '\n'.join(ln for ln in out.split('\n')
                             if not (ln.strip() and not ln.strip(' |·-')))
        return {'subject': fill(text['subject']).strip(), 'body': fill(text['body']).strip(),
                'button': (text.get('button') or '').strip(),
                'link': str(tokens.get('link') or tokens.get('video_link') or '').strip()}


# =========================================================================
#  The one door, the layout, and the Emails screen
# =========================================================================
class PbHiringComms(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _seed_p8(self):
        out = seed_p8(self.env)
        out['rules'] = self.env['pb.hiring.automation.rule']._seed_all()
        return out

    # ------------------------------------------------------------ language
    @api.model
    def _pb_candidate_lang(self, applicant):
        """`pb_lang` (what they applied in) → their contact's language →
        English. Only a language this database has switched on counts."""
        installed = lang_installed(self.env)
        app = applicant.sudo() if applicant else applicant
        for lang in ((app.pb_lang if app else ''),
                     (app.partner_id.lang if app and app.partner_id else '')):
            if lang in installed:
                return lang
        return 'en_US'

    @api.model
    def _pb_template(self, key, company):
        Tpl = self.env['pb.hiring.message.template'].sudo()
        return Tpl.search([('company_id', '=', company.id), ('key', '=', key),
                           ('active', '=', True)], order='id', limit=1)

    # -------------------------------------------------------------- layout
    @api.model
    def _pb_email_html(self, body, button='', link='', lang='en_US'):
        """Paragraphs from the plain words, links that are links, and one
        button when the email carries a link and a label."""
        style = ('margin:0; padding:0; font-family:Inter,Helvetica,Arial,sans-serif; '
                 'color:#1B1733; font-size:14px; line-height:1.6;')
        paras = []
        for block in re.split(r'\n\s*\n', (body or '').strip()):
            lines = [self._pb_linkify(line) for line in block.split('\n')]
            paras.append(Markup('<p style="margin:0 0 14px 0;">%s</p>') % Markup('<br/>').join(lines))
        html = Markup('').join(paras)
        if link and button:
            words = WORDS.get(lang) or WORDS['en_US']
            html += Markup(
                '<p style="margin:20px 0;"><a href="%s" style="background:#4F46E5; '
                'color:#FFFFFF; text-decoration:none; padding:11px 20px; border-radius:9px; '
                'font-weight:600; display:inline-block;">%s</a></p>'
                '<p style="font-size:13px; color:#64748B; margin:0 0 14px 0;">%s<br/>%s</p>'
            ) % (link, button, words['paste'], link)
        return Markup('<div style="%s">%s</div>') % (style, html)

    @api.model
    def _pb_linkify(self, line):
        out, pos = Markup(''), 0
        for m in URL_RE.finditer(line or ''):
            out += escape(line[pos:m.start()])
            url = m.group(1).rstrip('.,;:)')
            tail = m.group(1)[len(url):]
            out += Markup('<a href="%s" style="color:#4F46E5;">%s</a>') % (url, url) + escape(tail)
            pos = m.end()
        return out + escape((line or '')[pos:])

    # ------------------------------------------------------------ the door
    @api.model
    def _mail_candidate(self, key, applicant, values=None, attachments=None,
                        record=None, email_to=None, reply_to=None, gate=True,
                        dry=False, lang=None):
        """Send (or, `dry`, only describe) one candidate email.

        Returns {status, mail_id, lang, fell_back, subject, missing}; status is
        one of sent / dry / mail_off / no_email / no_template / missing.
        Never raises for a missing detail: the caller decides what to say.
        """
        app = applicant.sudo() if applicant else self.env['hr.applicant']
        company = (app.company_id if app else False) or (
            record.company_id if record is not None and 'company_id' in record else False) \
            or self.env.company
        out = {'status': '', 'mail_id': False, 'lang': 'en_US', 'fell_back': False,
               'subject': '', 'missing': []}
        if gate and not dry and not flag(self.env, P_CANDIDATE_MAIL):
            return dict(out, status='mail_off')
        address = (email_to or (app.email_from if app else '') or '').strip()
        if not address and not dry:
            return dict(out, status='no_email')
        template = self._pb_template(key, company)
        if not template:
            return dict(out, status='no_template')
        wanted = lang or self._pb_candidate_lang(app)
        used = wanted if template._pb_has_lang(wanted) else 'en_US'
        out.update(lang=used, fell_back=used != wanted, wanted=wanted)
        try:
            rendered = template._pb_render(app, values, used)
        except UserError:
            text = template._pb_text(used)
            tokens = template._pb_tokens(app, values, used)
            miss = sorted(k for k in set(TOKEN_RE.findall(text['subject'] + text['body']))
                          if not str(tokens.get(k) or '').strip() and k not in OPTIONAL_TOKENS)
            return dict(out, status='missing', missing=miss)
        out['subject'] = rendered['subject']
        if dry:
            return dict(out, status='dry')
        html = self._pb_email_html(rendered['body'], rendered['button'], rendered['link'], used)
        target = record if record is not None else app
        vals = {'subject': rendered['subject'], 'body_html': html, 'email_to': address,
                'email_from': self._sender(company), 'auto_delete': False,
                'model': target._name if target else False, 'res_id': target.id if target else False}
        if reply_to:
            vals['reply_to'] = reply_to
        if attachments:
            vals['attachment_ids'] = [(6, 0, list(attachments))]
        mail = self.env['mail.mail'].sudo().create(vals)
        out.update(status='sent', mail_id=mail.id)
        if app:
            leg(self.env, 'the email note on candidate %s' % app.id,
                lambda: self._pb_note_sent(app, template, rendered['subject'], used, wanted))
        return out

    @api.model
    def _pb_note_sent(self, app, template, subject, used, wanted):
        lang_word = {'en_US': 'English', 'vi_VN': 'Vietnamese', 'id_ID': 'Bahasa Indonesia'}.get
        if used != wanted:
            text = _('The email went out in English: “%(s)s”. The “%(n)s” email has no '
                     '%(l)s version yet, so English went instead.', s=subject,
                     n=template.with_context(lang='en_US').name or '', l=lang_word(wanted))
        elif used != 'en_US':
            text = _('Email sent in %(l)s: “%(s)s”.', l=lang_word(used), s=subject)
        else:
            text = _('Email sent: “%s”.', subject)
        app.message_post(body=Markup('<p>%s</p>') % text, message_type='comment',
                         subtype_xmlid='mail.mt_note',
                         author_id=app.company_id.partner_id.id or False)

    # ---------------------------------------------------- dates and money
    @api.model
    def _pb_when(self, dt, lang, tzname=None, fmt='EEEE d MMMM, HH:mm'):
        if not dt:
            return ''
        tzname = tzname or 'UTC'
        try:
            words = format_datetime(self.env, dt, tz=tzname, dt_format=fmt, lang_code=lang)
        except Exception:               # noqa: BLE001 — a sentence never fails
            words = str(dt)
        return '%s (%s)' % (words, tzname.split('/')[-1].replace('_', ' '))

    @api.model
    def _pb_day(self, day, lang, fmt='EEEE d MMMM'):
        if not day:
            return ''
        try:
            return format_date(self.env, day, lang_code=lang, date_format=fmt)
        except Exception:               # noqa: BLE001
            return str(day)

    @api.model
    def _pb_money(self, amount, currency, lang):
        try:
            return format_amount(self.env, amount or 0.0, currency, lang_code=lang)
        except Exception:               # noqa: BLE001
            return '%s %s' % (amount or 0, currency.name or '')

    # =====================================================================
    #  The Emails and languages screen
    # =====================================================================
    @api.model
    def _pb_email_row(self, tpl, langs):
        texts = {}
        for lg in langs:
            texts[lg] = tpl._pb_text(lg) if (lg == 'en_US' or tpl._pb_has_lang(lg)) \
                else {'subject': '', 'body': '', 'button': ''}
        std = self._pb_standard(tpl.key)
        # "Your words" in ANY language — a Vietnamese-only edit must still
        # offer "Reset to the standard text" (found in the P8 walk).
        changed = bool(std) and any(
            (texts[lg].get(f) or '').strip() != ((std.get(lg) or {}).get(f) or '').strip()
            for lg in langs if lg in std for f in ('subject', 'body'))
        return {
            'id': tpl.id, 'key': tpl.key,
            'name': tpl.with_context(lang='en_US').name or '',
            'when': WHEN.get(tpl.key, ''),
            'langs': {lg: ('ok' if lg == 'en_US' or tpl._pb_has_lang(lg) else 'missing')
                      for lg in langs},
            'texts': texts,
            'tokens': [{'key': t, 'words': TOKEN_WORDS.get(t, t)}
                       for t in COMMON_TOKENS + EXTRA.get(tpl.key, [])],
            'changed': changed,
            'has_button': bool(texts['en_US'].get('button')),
        }

    @api.model
    def get_emails(self):
        """The candidate emails of the current company, in screen order, and
        the internal ones (read-only)."""
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        company = self.env.company
        langs = lang_installed(self.env)
        Tpl = self.env['pb.hiring.message.template'].sudo()
        order = {k: i for i, k in enumerate(EMAIL_KEYS)}
        rows = Tpl.search([('company_id', '=', company.id), ('active', '=', True)])
        rows = rows.sorted(lambda t: (order.get(t.key, 99), t.id))
        seen, out = set(), []
        for tpl in rows:
            if tpl.key in seen:
                continue
            seen.add(tpl.key)
            out.append(self._pb_email_row(tpl, langs))
        internal = []
        admin = self.env.user.has_group('base.group_system')
        for xmlid, words in INTERNAL:
            rec = self.env.ref('pb_hiring.' + xmlid, raise_if_not_found=False)
            if rec:
                internal.append({'id': rec.id, 'name': words, 'can_open': admin})
        missing = sum(1 for r in out for v in r['langs'].values() if v == 'missing')
        return {'rows': out, 'internal': internal, 'langs': langs,
                'lang_words': {'en_US': 'English', 'vi_VN': 'Tiếng Việt', 'id_ID': 'Bahasa Indonesia'},
                'can_edit': self._can_write(), 'missing': missing,
                'mail_on': flag(self.env, P_CANDIDATE_MAIL)}

    @api.model
    def _pb_standard(self, key):
        """The product's own words for a key, per language (for Reset and
        for "changed")."""
        if key in NEW_EMAILS:
            en = NEW_EMAILS[key]
            out = {'en_US': {'subject': en['subject'], 'body': en['body'], 'button': en['button']}}
            for lg, words in (NEW_I18N.get(key) or {}).items():
                out[lg] = dict(words)
            return out
        seed = _json_seed().get(key)
        if key == 'laptop':
            from .form_seed_i18n import LAPTOP_EMAIL
            seed = LAPTOP_EMAIL
        if not seed:
            return {}
        out = {'en_US': {'subject': seed['subject'], 'body': seed['body'], 'button': ''}}
        table = {}
        if key == 'received':
            from .form_seed_i18n import RECEIVED_I18N as table
        elif key == 'phone':
            from .form_seed_i18n import PHONE_I18N as table
        elif key == 'laptop':
            from .form_seed_i18n import LAPTOP_I18N as table
        for lg in ('vi_VN', 'id_ID'):
            if key in OLD_I18N and lg in OLD_I18N[key]:
                out[lg] = dict(OLD_I18N[key][lg], button='')
            elif table:
                subj = (table.get('subject') or {}).get(seed['subject'], {}).get(lg)
                body = (table.get('body') or {}).get(seed['body'], {}).get(lg)
                if subj and body:
                    out[lg] = {'subject': subj, 'body': body, 'button': ''}
        return out

    @api.model
    def _pb_email_tpl(self, payload):
        tpl = self.env['pb.hiring.message.template'].sudo().browse(as_id(payload.get('id'))).exists()
        if not tpl or tpl.company_id not in self.env.companies:
            raise UserError(_("That email is no longer there."))
        return tpl

    @api.model
    def _pb_check_tokens(self, tpl, subject, body):
        allowed = set(COMMON_TOKENS) | set(EXTRA.get(tpl.key, []))
        bad = sorted(set(TOKEN_RE.findall((subject or '') + (body or ''))) - allowed)
        if bad:
            raise UserError(_(
                "%(bad)s is not a detail this email can fill. Use one of the chips under "
                "the editor instead.", bad=', '.join('{{%s}}' % b for b in bad)))

    def _act_email_save(self, payload):
        """Save ONE language of one email. Empty in a language other than
        English = that language is removed (English goes instead)."""
        self._require_write()
        tpl = self._pb_email_tpl(payload)
        lang = payload.get('lang') or 'en_US'
        if lang not in lang_installed(self.env):
            raise UserError(_("That language is not switched on in this system."))
        subject = (payload.get('subject') or '').strip()
        body = (payload.get('body') or '').rstrip()
        button = (payload.get('button') or '').strip()
        before = {'subject': '', 'body': '', 'button': ''}
        if lang == 'en_US' or tpl._pb_has_lang(lang):
            before = tpl._pb_text(lang)
        if lang == 'en_US' and (not subject or not body.strip()):
            raise UserError(_("The English email needs a subject and some words. It is the "
                              "one that goes when a language is missing."))
        if len(subject) > 200:
            raise UserError(_("Keep the subject under 200 characters."))
        if len(button) > 60:
            raise UserError(_("Keep the button words short — under 60 characters."))
        if lang != 'en_US' and not subject and not body.strip():
            for fname in ('subject', 'body', 'button'):
                tpl.update_field_translations(fname, {lang: False})
            return {'note': _("Removed. English goes to these candidates until somebody writes it."),
                    'before': before, 'id': tpl.id, 'lang': lang}
        if lang != 'en_US' and (not subject or not body.strip()):
            raise UserError(_("Write both the subject and the words, or empty both to "
                              "remove this language."))
        self._pb_check_tokens(tpl, subject, body)
        _write_lang(tpl, lang, subject, body, button)
        return {'note': _("Saved. The next email goes out with these words."),
                'before': before, 'id': tpl.id, 'lang': lang}

    def _act_email_restore(self, payload):
        """Undo of a save: the texts as they were."""
        self._require_write()
        tpl = self._pb_email_tpl(payload)
        lang = payload.get('lang') or 'en_US'
        was = payload.get('before') or {}
        if lang != 'en_US' and not (was.get('subject') or was.get('body')):
            for fname in ('subject', 'body', 'button'):
                tpl.update_field_translations(fname, {lang: False})
        else:
            _write_lang(tpl, lang, was.get('subject') or '', was.get('body') or '',
                        was.get('button') or '')
        return {'note': _("Put back as it was.")}

    def _act_email_reset(self, payload):
        """The product's own words, in every language it has them."""
        self._require_write()
        tpl = self._pb_email_tpl(payload)
        std = self._pb_standard(tpl.key)
        if not std:
            raise UserError(_("This email has no standard text to go back to."))
        langs = lang_installed(self.env)
        en = std['en_US']
        _write_lang(tpl, 'en_US', en['subject'], en['body'], en.get('button') or '')
        for lg in langs:
            if lg == 'en_US':
                continue
            words = std.get(lg)
            if words:
                _write_lang(tpl, lg, words['subject'], words['body'], words.get('button') or '')
            else:
                for fname in ('subject', 'body', 'button'):
                    if tpl._pb_raw(fname).get(lg):
                        tpl.update_field_translations(fname, {lg: False})
        return {'note': _("Back to the standard text, in every language it has.")}

    @api.model
    def _pb_sample_app(self, company):
        app = self.env['hr.applicant'].sudo().search(
            [('company_id', '=', company.id), ('partner_name', '!=', False),
             ('pb_requisition_id', '!=', False)], order='id desc', limit=1)
        return app

    @api.model
    def get_email_preview(self, template_id, lang='en_US', subject=None, body=None, button=None):
        """The email drawn as a candidate would get it, with sample details —
        or the sentence that says what is wrong (never a traceback)."""
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        tpl = self._pb_email_tpl({'id': template_id})
        text = tpl._pb_text(lang)
        if subject is not None:
            text = {'subject': subject or '', 'body': body or '', 'button': button or ''}
        try:
            self._pb_check_tokens(tpl, text['subject'], text['body'])
            app = self._pb_sample_app(tpl.company_id)
            values = dict(SAMPLE)
            values['link'] = values['link'] if text.get('button') else ''
            if not app:
                values.update({'name': 'Nguyễn Thị Lan', 'first_name': 'Nguyễn Thị Lan',
                               'role': 'Territory Manager'})
            rendered = tpl._pb_render(app, values, lang, text=text)
        except UserError as exc:
            return {'ok': False, 'error': str(exc.args[0] if exc.args else exc)}
        return {'ok': True, 'subject': rendered['subject'],
                'html': str(self._pb_email_html(rendered['body'], rendered['button'],
                                                rendered['link'], lang)),
                'candidate': (app.partner_name if app else '') or 'Nguyễn Thị Lan'}

    def _act_email_test(self, payload):
        """"Send me a test": the email in that language, with sample details,
        to the person pressing."""
        if not self._can_read():
            raise AccessError(_('Hiring access is required.'))
        tpl = self._pb_email_tpl(payload)
        lang = payload.get('lang') or 'en_US'
        to = (self.env.user.email or '').strip()
        if not to:
            raise UserError(_("Your own login has no email address, so there is nowhere to "
                              "send the test. Add one in Preferences."))
        prev = self.get_email_preview(tpl.id, lang)
        if not prev['ok']:
            raise UserError(prev['error'])
        words = WORDS.get(lang) or WORDS['en_US']
        mail = self.env['mail.mail'].sudo().create({
            'subject': words['test'] + prev['subject'], 'body_html': prev['html'],
            'email_to': to, 'email_from': self._sender(tpl.company_id),
            'auto_delete': False})
        words = {'en_US': 'English', 'vi_VN': 'Vietnamese', 'id_ID': 'Bahasa Indonesia'}
        return {'note': _("A test went to %(to)s, in %(l)s. It is in the mail queue now.",
                          to=to, l=words.get(lang, lang)),
                'mail_id': mail.id}

    def _act_email_open_internal(self, payload):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Internal emails are the administrator's."))
        rec = self.env['mail.template'].browse(as_id(payload.get('id'))).exists()
        if not rec:
            raise UserError(_("That email is no longer there."))
        return {'type': 'ir.actions.act_window', 'res_model': 'mail.template', 'res_id': rec.id,
                'views': [[False, 'form']], 'view_mode': 'form', 'target': 'new',
                'name': _('Internal email (English)')}

    # ------------------------------------------------------------- set-up
    @api.model
    def get_setup(self):
        res = super().get_setup()
        emails = self._safe(self.get_emails, default=None)
        res['emails'] = emails
        for card in res.get('cards', []):
            if card['key'] == 'emails' and emails:
                n = len(emails['rows'])
                miss = emails['missing']
                card.update({
                    'status': (_("%s candidate emails in every language.", n) if not miss else
                               _("%(n)s candidate emails · %(m)s language versions missing",
                                 n=n, m=miss)) if emails['mail_on']
                    else _("Candidate emails are switched off."),
                    'inline': True, 'action': False, 'live': False})
        return res

    # ------------------------------------------- the board's message form
    def _act_message_preview(self, payload):
        applicant = self.env['hr.applicant'].with_context(active_test=False).browse(
            as_id(payload.get('applicant_id'))).exists()
        applicant.check_access('read')
        self._require_recruit(applicant.pb_requisition_id)
        tpl = self._pb_template(payload.get('key'), applicant.company_id)
        if not tpl:
            raise UserError(_('Configure this candidate email for the company first.'))
        wanted = self._pb_candidate_lang(applicant)
        lang = wanted if tpl._pb_has_lang(wanted) else 'en_US'
        rendered = tpl._pb_render(applicant, payload.get('values'), lang)
        return {'subject': rendered['subject'], 'body': rendered['body']}

    def _act_message_send(self, payload):
        self._act_message_preview(payload)
        applicant = self.env['hr.applicant'].browse(as_id(payload['applicant_id']))
        if not flag(self.env, P_CANDIDATE_MAIL):
            raise UserError(_('Candidate emails are switched off in Hiring settings.'))
        if not applicant.email_from:
            raise UserError(_('Add a candidate email address first.'))
        res = self._mail_candidate(payload.get('key'), applicant,
                                   values=payload.get('values') or {},
                                   reply_to=self.env.user.email_formatted or None)
        if res['status'] != 'sent':
            raise UserError(_('The email could not be sent: %s', res['status']))
        return {'note': _('Candidate email queued. Delivery is tracked in the mail queue.')}


# =========================================================================
#  The senders, re-pointed by KEY
# =========================================================================
class HiringApplicantComms(models.Model):
    _inherit = 'hr.applicant'

    def _pb_send_received(self):
        """P2's "Application received", now through the one door. The
        built-in switch `pb_hiring.auto_received` can stop it."""
        self.ensure_one()
        if not flag(self.env, 'pb_hiring.auto_received', '1'):
            return False
        res = self.env['pb.hiring']._mail_candidate('received', self)
        if res['status'] != 'sent':
            return False
        return self.env['mail.mail'].sudo().browse(res['mail_id'])

    def _pb_tell_candidate(self, xmlid):
        key = RETIRED.get(xmlid)
        if not key:
            return super()._pb_tell_candidate(xmlid)
        self.ensure_one()
        if key == 'interview_reject' and (self.sudo().stage_id.pb_key or '') == 'cv_reject':
            key = 'cv_reject'
        res = self.env['pb.hiring']._mail_candidate(key, self)
        if res['status'] not in ('sent',):
            _logger.info('pb_hiring: the %s email to candidate %s did not go (%s)',
                         key, self.id, res['status'])
        return res['status'] == 'sent'


class HiringInterviewComms(models.Model):
    _inherit = 'pb.hiring.interview'

    def _pb_tz(self):
        self.ensure_one()
        user = self.sudo().recruiter_id
        return user.tz or self.company_id.sudo().partner_id.tz or 'UTC'

    def _pb_values(self, which, start=None):
        """The details only the interview knows, in the email's language."""
        self.ensure_one()
        Hiring = self.env['pb.hiring']
        tz = self._pb_tz()
        join = self.sudo().pb_join_url or ''
        location = (self.sudo().location or '').strip()

        def where(lang):
            words = WORDS.get(lang) or WORDS['en_US']
            if join:
                return words['video'] % join
            return location or words['where_later']

        values = {'when': lambda lang, s=start or self.start: Hiring._pb_when(s, lang, tz),
                  'duration': str(self.duration_minutes or 45),
                  'where': where, 'video_link': join, 'link': join}
        if which == 'interview_off':
            fresh = self.sudo().rescheduled_to_id

            def nxt(lang):
                words = WORDS.get(lang) or WORDS['en_US']
                if fresh:
                    return words['moved'] % Hiring._pb_when(fresh.start, lang, tz)
                return words['later']
            values['next_step'] = nxt
        return values

    def _send(self, xmlid, to, with_ics=False, ics_name='interview.ics'):
        key = RETIRED.get(xmlid)
        cand = (self.sudo().candidate_email or '').strip().lower()
        if not key or not to or (to or '').strip().lower() != cand:
            return super()._send(xmlid, to, with_ics=with_ics, ics_name=ics_name)
        self.ensure_one()
        attachments = self._ics_attachment(ics_name).ids if with_ics else None
        res = self.env['pb.hiring']._mail_candidate(
            key, self.applicant_id, values=self._pb_values(key), attachments=attachments,
            record=self, email_to=to)
        return res['status'] == 'sent'


class HiringDocreqComms(models.Model):
    _inherit = 'pb.hiring.docreq'

    def _mail(self, xmlid):
        key = RETIRED.get(xmlid)
        if not key:
            return super()._mail(xmlid)
        self.ensure_one()
        if not self.candidate_email:
            return False
        if key == 'docreq_remind' and not flag(self.env, 'pb_hiring.auto_doc_remind', '1'):
            return False
        Hiring = self.env['pb.hiring']
        rec = self.sudo()
        values = {'deadline': lambda lang: Hiring._pb_day(rec.deadline, lang),
                  'link': rec._token_url(), 'in_count': str(rec.in_count or 0),
                  'wanted_count': str(rec.wanted_count or len(rec.item_ids) or 0)}
        res = Hiring._mail_candidate(key, rec.offer_id.applicant_id, values=values,
                                     record=rec, email_to=rec.candidate_email)
        return res['status'] == 'sent'

    # RC80: the docreq has no activity mixin, so every to-do it raises
    # (papers in, past the date, the talent lead's escalation) used to fail
    # inside a savepoint and nobody got it. Its to-dos land on the OFFER.
    def activity_schedule(self, act_type_xmlid='', date_deadline=None, summary='',
                          note='', **act_values):
        self.ensure_one()
        offer = self.sudo().offer_id
        if not offer:
            return self.env['mail.activity']
        return offer.activity_schedule(act_type_xmlid, date_deadline=date_deadline,
                                       summary=summary, note=note, **act_values)


class HiringOfferComms(models.Model):
    _inherit = 'pb.hiring.offer'

    def _mail(self, xmlid, to, with_pdf=False):
        key = RETIRED.get(xmlid)
        if not key:
            return super()._mail(xmlid, to, with_pdf=with_pdf)
        self.ensure_one()
        if not to:
            return False
        Hiring = self.env['pb.hiring']
        rec = self.sudo()
        cur = rec.currency_id or rec.company_id.currency_id
        values = {'start_date': lambda lang: Hiring._pb_day(rec.start_date, lang, 'EEEE d MMMM y'),
                  'monthly': lambda lang: Hiring._pb_money(rec.monthly_total, cur, lang),
                  'yearly': lambda lang: Hiring._pb_money(rec.annual_total, cur, lang),
                  'link': rec._token_url()}
        atts = [rec.attachment_id.id] if with_pdf and rec.attachment_id else None
        # The offer switch (`offer_mail`) already decided; the candidate-email
        # switch never stops an offer that was agreed and sent on purpose.
        res = Hiring._mail_candidate(key, rec.applicant_id, values=values,
                                     attachments=atts, record=rec, email_to=to, gate=False)
        return res['status'] == 'sent'


class HiringPrejoinComms(models.Model):
    _inherit = 'pb.hiring.prejoin'

    def _send_laptop_mail(self):
        """P6's laptop question, through the one door."""
        self.ensure_one()
        offer = self.offer_id.sudo()
        app = offer.applicant_id.sudo()
        if not offer.candidate_email:
            return 'no_email'
        if not flag(self.env, P_CANDIDATE_MAIL):
            return 'mail_off'
        Hiring = self.env['pb.hiring']
        recruiter = offer.requisition_id.recruiter_id or self.env.user
        join = offer.expected_join_date or offer.start_date
        values = {'laptop_link': self.pb_link_url,
                  'join_date': lambda lang: Hiring._pb_day(join, lang),
                  'hr_name': recruiter.name or '', 'sender_name': recruiter.name or ''}
        res = Hiring._mail_candidate('laptop', app, values=values,
                                     email_to=offer.candidate_email,
                                     reply_to=recruiter.email_formatted or None)
        if res['status'] != 'sent':
            return 'no_template' if res['status'] in ('missing', 'no_template') else res['status']
        first = not self.sent_at
        self.sudo().write({'sent_at': fields.Datetime.now()} if first
                          else {'reminded_at': fields.Datetime.now()})
        return 'sent'


class PbHiringPhoneComms(models.AbstractModel):
    _inherit = 'pb.hiring'

    @api.model
    def _pb_send_scheduling_link(self, app):
        """P5's "Let's chat", through the one door (same answers)."""
        app = app.sudo()
        req = app.pb_requisition_id
        recruiter = req.recruiter_id if req and req.recruiter_id else self.env.user
        answer = {'who': recruiter.name or '', 'user_id': recruiter.id}
        if not app.email_from:
            return dict(answer, status='no_email')
        if not flag(self.env, P_CANDIDATE_MAIL):
            return dict(answer, status='mail_off')
        link = (recruiter.sudo().pb_scheduling_link or '').strip()
        if not link:
            return dict(answer, status='no_link')
        from .hiring_common import P_PHONE_MINUTES, number
        values = {'scheduling_link': link, 'hr_name': recruiter.name or '',
                  'sender_name': recruiter.name or '',
                  'duration': str(number(self.env, P_PHONE_MINUTES, 30))}
        res = self._mail_candidate('phone', app, values=values,
                                   reply_to=recruiter.email_formatted or None)
        if res['status'] != 'sent':
            return dict(answer, status='no_template')
        app.write({'pb_scheduling_sent_at': fields.Datetime.now()})
        return dict(answer, status='sent', mail_id=res['mail_id'], lang=res['lang'])


# =========================================================================
#  The seed (every load): the new keys per company, three languages, the
#  old English-only candidate templates archived.
# =========================================================================
def seed_p8(env):
    Tpl = env['pb.hiring.message.template'].sudo().with_context(active_test=False, lang='en_US')
    langs = [lg for lg in lang_installed(env) if lg != 'en_US']
    made = 0
    for company in env['res.company'].sudo().search([]):
        for i, key in enumerate(EMAIL_KEYS):
            if key not in NEW_EMAILS:
                continue
            if Tpl.search_count([('company_id', '=', company.id), ('key', '=', key)]):
                continue
            en = NEW_EMAILS[key]
            Tpl.create({'company_id': company.id, 'key': key, 'name': en['name'],
                        'subject': en['subject'], 'body': en['body'],
                        'button': en['button'] or False, 'sequence': 100 + i * 10})
            made += 1
    # Their other languages, only where the row still carries the product's
    # English and has none of its own (P2 rule).
    filled = 0
    for key, by_lang in NEW_I18N.items():
        filled += _seed_lang(env, Tpl, key, NEW_EMAILS[key], by_lang, langs)
    seeds = _json_seed()
    for key, by_lang in OLD_I18N.items():
        if key in seeds:
            filled += _seed_lang(env, Tpl, key, seeds[key], by_lang, langs)
    archived = 0
    for xmlid in RETIRED:
        if xmlid in SHARED:
            continue
        rec = env.ref(xmlid, raise_if_not_found=False)
        if rec and rec.active:
            rec.sudo().write({'active': False})
            archived += 1
    if made or filled or archived:
        _logger.info('pb_hiring P8: %s candidate emails made, %s language versions written, '
                     '%s old English-only templates archived', made, filled, archived)
    return {'made': made, 'filled': filled, 'archived': archived}


def _write_lang(tpl, lang, subject, body, button):
    """Write ONE language of a template.

    Writing False to a translated field NULLs it for EVERY language
    (`_String.write`), so an empty button in one language is removed with
    `update_field_translations(lang: False)`, never written as False — except
    in English, where no button means no button anywhere.
    """
    tpl.with_context(lang=lang).write({'subject': subject, 'body': body})
    if button:
        tpl.with_context(lang=lang).write({'button': button})
    elif lang == 'en_US':
        if tpl.button:
            tpl.with_context(lang='en_US').write({'button': False})
    elif tpl._pb_raw('button').get(lang):
        tpl.update_field_translations('button', {lang: False})


def _seed_lang(env, Tpl, key, en, by_lang, langs):
    from .forms_p2 import _raw
    rows = Tpl.search([('key', '=', key)])
    if not rows or not langs:
        return 0
    subj, body = _raw(rows, 'subject'), _raw(rows, 'body')
    n = 0
    for row in rows:
        s, b = subj.get(row.id) or {}, body.get(row.id) or {}
        if (s.get('en_US') or '') != en['subject'] or (b.get('en_US') or '') != en['body']:
            continue
        for lg in langs:
            words = by_lang.get(lg)
            if not words or lg in s or lg in b:
                continue
            row.update_field_translations('subject', {lg: words['subject']})
            row.update_field_translations('body', {lg: words['body']})
            if words.get('button'):
                row.update_field_translations('button', {lg: words['button']})
            n += 1
    return n
