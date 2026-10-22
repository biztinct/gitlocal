# -*- coding: utf-8 -*-
"""PayAI drafts a course from a document (LEARNING L7, owner decision LD9).

THE ONE WAY IN is `pb.training.draft_upload(filename, data_b64, language)`
(the "New course" drawer's upload) or `pb.training.draft_course(attachment_id,
language)` (a document the person can already read, which PayAI's chat
door pre-fills). Both run AS THE PERSON (training groups only) and never with
sudo on business data:

  1. THE FILE. At most 10 MB, refused before it is decoded when the text it
     came in is already too long. Its kind is read from its first bytes and
     its name: a PDF (`%PDF`), a Word file (a zip with `word/document.xml`) or
     a text file (words that decode). Anything else is a sentence.
  2. THE WORDS. A text file directly; a Word file through python-docx when
     it is installed, else straight from the file's own XML (the standard
     library reads it — "save it as a PDF first" is said only when neither
     can); a PDF through the PDF reader this build already has. A PDF with no
     words in it (a scan) goes to the document-reading provider when that
     provider reads PDFs itself (`accepts_pdf`, as `biz_doc_ocr._extract`
     does); otherwise a sentence says what to do.
  3. THE DRAFT. The configured PayAI provider (`payroll.ai.config`, the
     chat's own lookup: an insights row first, never the OCR engine) is asked
     for `{title, blurb, lessons: [{title, html, minutes}] (3–8),
     quiz: [{question, options: [4], correct}] (10)}` in the chosen
     language. Nothing configured → "PayAI is not set up for documents yet…"
     and nothing leaves the building.
  4. THE COURSE. An UNPUBLISHED training course, for members only and by
     invitation (the product's own defaults for a new course), with one
     reading lesson per drafted lesson and one quiz lesson holding the
     questions. It remembers the file it came from (`pb_draft_source_id`)
     and its chatter says who drafted it, from which file, with which model.
     The drawer then shows "Drafted by PayAI from <file>. Read every lesson
     before you publish." PayAI never publishes.

The model's words are text: the lesson HTML is sanitized before it is
stored, every number is clamped, and nothing it returns is used as an id
(PayAI rule PA-R3).
"""

import base64
import io
import json
import logging
import re
import zipfile
from xml.etree import ElementTree

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.mail import html_sanitize

_logger = logging.getLogger(__name__)

#: The largest file the drawer takes (owner rule: uploads are bounded).
MAX_BYTES = 10 * 1024 * 1024
#: How much of the document's text goes to the model (a long manual is cut
#: and the draft says so in its chatter line).
MAX_CHARS = 60000
#: A PDF with fewer words than this is a scan.
MIN_PDF_CHARS = 200
#: At most this many pages of a PDF are read.
MAX_PAGES = 80

KIND_PDF, KIND_DOCX, KIND_TXT = 'pdf', 'docx', 'txt'
MIMES = {KIND_PDF: 'application/pdf',
         KIND_DOCX: 'application/vnd.openxmlformats-officedocument.'
                    'wordprocessingml.document',
         KIND_TXT: 'text/plain'}
LANGS = {'en': ('English', 'en_US'), 'vi': ('Vietnamese', 'vi_VN')}

SCHEMA_HINT = json.dumps({
    'title': 'string — the course name, at most 80 characters',
    'blurb': 'string — one or two sentences on what the course teaches',
    'lessons': [{'title': 'string', 'html': 'string — the lesson as simple '
                 'HTML: <p>, <h3>, <ul>, <ol>, <li>, <strong> only',
                 'minutes': 'integer — reading time, 2 to 10'}],
    'quiz': [{'question': 'string', 'options': ['four strings'],
              'correct': 'integer — 0 to 3, the index of the right option'}],
}, indent=1)


def _decode_text(raw):
    for codec in ('utf-8-sig', 'utf-16'):
        try:
            text = raw.decode(codec)
        except UnicodeDecodeError:
            continue
        if codec == 'utf-16' and not raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
            continue
        return text
    return None


def file_kind(filename, raw):
    """'pdf' / 'docx' / 'txt', read from the bytes first (a name can lie)."""
    name = (filename or '').lower()
    if raw[:5] == b'%PDF-':
        return KIND_PDF
    if raw[:2] == b'PK':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                if 'word/document.xml' in zf.namelist():
                    return KIND_DOCX
        except zipfile.BadZipFile:
            return None
        return None
    if name.endswith(('.txt', '.md', '.text')) or not re.search(r'\.\w+$', name):
        text = _decode_text(raw)
        if text is not None and '\x00' not in text:
            return KIND_TXT
    return None


def docx_text(raw):
    """The words of a Word file: python-docx when installed, else the file's
    own XML (paragraphs in order). '' when neither can read it."""
    try:
        import docx  # noqa: F401 — optional
        doc = docx.Document(io.BytesIO(raw))
        return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        pass
    except Exception:                       # noqa: BLE001 — try the XML
        _logger.info('pb_training_payai: python-docx could not read a file',
                     exc_info=True)
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            xml = zf.read('word/document.xml')
        root = ElementTree.fromstring(xml)
    except Exception:                       # noqa: BLE001 — unreadable
        return ''
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    lines = []
    for para in root.iter(ns + 'p'):
        words = ''.join(t.text or '' for t in para.iter(ns + 't'))
        if words.strip():
            lines.append(words)
    return '\n'.join(lines)


def pdf_text(raw):
    """The words of a PDF ('' for a scan or a file the reader refuses)."""
    try:
        from odoo.tools.pdf import PdfFileReader
        reader = PdfFileReader(io.BytesIO(raw), strict=False)
        chunks = []
        for i, page in enumerate(reader.pages):
            if i >= MAX_PAGES:
                break
            chunks.append(page.extract_text() or '')
        return '\n'.join(chunks)
    except Exception:                       # noqa: BLE001 — a scan, a lock
        _logger.info('pb_training_payai: a PDF could not be read for words',
                     exc_info=True)
        return ''


class SlideChannelDraft(models.Model):
    _inherit = 'slide.channel'

    pb_draft_source_id = fields.Many2one(
        'ir.attachment', string='Drafted from', readonly=True, copy=False,
        ondelete='set null',
        help='The document PayAI drafted this course from. The course stays '
             'unpublished until a trainer publishes it.')


class PbTrainingDraft(models.AbstractModel):
    _inherit = 'pb.training'

    # ================================================================ doors
    @api.model
    def draft_setup(self):
        """What the drawer says before anything is uploaded: whether a
        provider is set up, and the languages it can draft in."""
        self._require_write()
        cfg = self._draft_config()
        return {
            'ready': bool(cfg),
            'not_ready_words': '' if cfg else self._not_set_up_words(),
            'max_mb': MAX_BYTES // (1024 * 1024),
            'language': 'vi' if (self.env.lang or '') == 'vi_VN' else 'en',
            'languages': [{'key': 'en', 'label': _("English")},
                          {'key': 'vi', 'label': _("Vietnamese")}],
        }

    @api.model
    def draft_attachment_info(self, attachment_id):
        """The name of a document the person can read (the PayAI door's
        pre-filled file), or {} — read as the person."""
        self._require_write()
        att = self.env['ir.attachment'].browse(int(attachment_id or 0)).exists()
        if not att:
            return {}
        try:
            att.check_access('read')
        except AccessError:
            return {}
        return {'id': att.id, 'name': att.name or ''}

    @api.model
    def draft_upload(self, filename, data_b64, language='en'):
        """The drawer's upload: bounded, checked, kept as an attachment the
        person made, then drafted."""
        self._require_write()
        data_b64 = data_b64 or ''
        if isinstance(data_b64, bytes):
            data_b64 = data_b64.decode('ascii', 'ignore')
        # BOUNDED BEFORE IT IS DECODED: base64 is 4 characters per 3 bytes.
        if len(data_b64) > (MAX_BYTES * 4) // 3 + 8:
            raise UserError(self._too_big_words())
        try:
            raw = base64.b64decode(data_b64, validate=False)
        except Exception:                   # noqa: BLE001
            raise UserError(_("That file could not be read. Try again, or "
                              "save it as a PDF first.")) from None
        if not raw:
            raise UserError(_("That file is empty."))
        if len(raw) > MAX_BYTES:
            raise UserError(self._too_big_words())
        name = (filename or '').strip()[:200] or _("Document")
        kind = file_kind(name, raw)
        if not kind:
            raise UserError(_("PayAI can draft a course from a PDF, a Word "
                              "file or a text file. Save it as one of those "
                              "and upload it again."))
        att = self.env['ir.attachment'].create({
            'name': name,
            'datas': base64.b64encode(raw),
            'mimetype': MIMES[kind],
            'res_model': 'slide.channel',
            'res_id': 0,
        })
        return self.draft_course(att.id, language)

    @api.model
    def draft_course(self, attachment_id, language='en'):
        """Draft an UNPUBLISHED course from a document the person can read."""
        self._require_write()
        att = self.env['ir.attachment'].browse(int(attachment_id or 0)).exists()
        if not att:
            raise UserError(_("That document is not here any more."))
        # AS THE PERSON: a file they cannot read is refused here, never read
        # with sudo (`check_access` raises AccessError on its own).
        att.check_access('read')
        raw = base64.b64decode(att.datas or b'')
        if not raw:
            raise UserError(_("That file is empty."))
        if len(raw) > MAX_BYTES:
            raise UserError(self._too_big_words())
        kind = file_kind(att.name, raw)
        if not kind:
            raise UserError(_("PayAI can draft a course from a PDF, a Word "
                              "file or a text file. Save it as one of those "
                              "and upload it again."))
        lang_key = language if language in LANGS else 'en'

        cfg = self._draft_config()
        if not cfg:
            raise UserError(self._not_set_up_words())
        try:
            provider = cfg.get_provider()
        except Exception:                   # noqa: BLE001 — a bad key, a library
            _logger.warning('pb_training_payai: the PayAI provider could not '
                            'be started', exc_info=True)
            raise UserError(self._not_set_up_words()) from None

        text = self._draft_text(kind, raw)
        cut = len(text) > MAX_CHARS
        text = text[:MAX_CHARS]
        if text.strip():
            draft = self._ask_for_draft(provider, cfg, text, lang_key)
        elif kind == KIND_PDF:
            draft = self._ask_vision(raw, lang_key)
        else:
            raise UserError(_("There are no words in that file that PayAI "
                              "can read."))
        clean = self._clean_draft(draft)
        channel = self._make_draft(clean, att, lang_key, cfg, cut)
        return {
            'channel_id': channel.id,
            'name': channel.name,
            'lessons': len(clean['lessons']),
            'questions': len(clean['quiz']),
            'message': _("Drafted. Read every lesson before you publish."),
        }

    # ============================================================ helpers
    @api.model
    def _too_big_words(self):
        return _("That file is larger than 10 MB. Upload a shorter document, "
                 "or the part of it the course is about.")

    @api.model
    def _not_set_up_words(self):
        return _("PayAI is not set up for documents yet. Ask the "
                 "administrator to add a provider under Settings › PayAI.")

    @api.model
    def _draft_config(self):
        """The provider the chat uses (an insights row first, never the OCR
        engine). Infrastructure, read the product's own way."""
        if 'payroll.ai.config' not in self.env:
            return None
        cfg = self.env['payroll.ai.config'].get_active_config()
        return cfg if cfg and cfg.provider_type != 'tesseract' else None

    @api.model
    def _draft_text(self, kind, raw):
        if kind == KIND_TXT:
            return (_decode_text(raw) or '').strip()
        if kind == KIND_DOCX:
            text = docx_text(raw)
            if not text.strip():
                raise UserError(_("That Word file could not be read. Save it "
                                  "as a PDF first and upload that."))
            return text
        text = pdf_text(raw)
        return text if len(text.strip()) >= MIN_PDF_CHARS else ''

    @api.model
    def _prompt(self, lang_key):
        language = LANGS[lang_key][0]
        return (
            "You turn a company's procedure document into a short training "
            "course for its employees.\n"
            "Write everything in %(lang)s, in plain words a new employee "
            "understands. Use only what the document says; never invent a "
            "rule, a number or a name that is not in it.\n"
            "Return 3 to 8 lessons, each readable in 2 to 10 minutes, in the "
            "order a person should learn them, and exactly 10 multiple-choice "
            "questions with 4 options each, one right answer, about the most "
            "important points.\n"
            "Do not name any software product or vendor." % {'lang': language})

    @api.model
    def _ask_for_draft(self, provider, cfg, text, lang_key):
        prompt = "%s\n\nTHE DOCUMENT:\n\"\"\"\n%s\n\"\"\"" % (
            self._prompt(lang_key), text)
        try:
            return provider.generate_structured(
                prompt, schema_hint=SCHEMA_HINT,
                max_tokens=max(cfg.max_tokens or 0, 6000), temperature=0.3)
        except Exception:                   # noqa: BLE001 — never a traceback
            _logger.warning('pb_training_payai: the draft call failed',
                            exc_info=True)
            raise UserError(_("PayAI could not draft a course just now. Try "
                              "again in a minute, or start a blank course.")
                            ) from None

    @api.model
    def _ask_vision(self, raw, lang_key):
        """A PDF with no words in it: only when the document-reading provider
        reads PDFs itself (the `biz_doc_ocr._extract` rule)."""
        cfg = self.env['payroll.ai.config'].get_config_for_purpose('doc_ocr')
        provider = None
        if cfg and cfg.provider_type != 'tesseract':
            try:
                provider = cfg.get_provider()
            except Exception:               # noqa: BLE001
                provider = None
        if not provider or not provider.supports_vision() \
                or not provider.accepts_pdf():
            raise UserError(_("That PDF is a picture of the pages, with no "
                              "words in it PayAI can read. Upload the Word "
                              "file or a PDF saved from it instead."))
        prompt = "%s\n\nRespond ONLY with valid JSON matching this schema:\n%s" \
            % (self._prompt(lang_key), SCHEMA_HINT)
        try:
            out = provider.generate_vision(
                prompt, [{'mime': 'application/pdf',
                          'data_b64': base64.b64encode(raw).decode()}],
                max_tokens=6000)
            return provider._parse_json_response(out)
        except Exception:                   # noqa: BLE001
            _logger.warning('pb_training_payai: the PDF draft call failed',
                            exc_info=True)
            raise UserError(_("PayAI could not draft a course just now. Try "
                              "again in a minute, or start a blank course.")
                            ) from None

    @api.model
    def _clean_draft(self, draft):
        """The model's answer, as text we can trust the shape of."""
        if not isinstance(draft, dict):
            draft = {}

        def line(value, cap):
            value = re.sub(r'\s+', ' ', str(value or '')).strip()
            return value[:cap]

        lessons = []
        for row in (draft.get('lessons') or [])[:8]:
            if not isinstance(row, dict):
                continue
            title = line(row.get('title'), 120)
            body = html_sanitize(str(row.get('html') or ''), silent=True,
                                 sanitize_tags=True, sanitize_attributes=True,
                                 sanitize_style=True, strip_style=True,
                                 strip_classes=True) or ''
            if not title or not re.sub(r'<[^>]+>', '', str(body)).strip():
                continue
            try:
                mins = int(row.get('minutes') or 5)
            except (TypeError, ValueError):
                mins = 5
            lessons.append({'title': title, 'html': str(body)[:20000],
                            'minutes': min(max(mins, 1), 30)})
        quiz = []
        for row in (draft.get('quiz') or [])[:10]:
            if not isinstance(row, dict):
                continue
            question = line(row.get('question'), 300)
            options = [line(o, 200) for o in (row.get('options') or [])
                       if line(o, 200)][:4]
            correct = row.get('correct')
            if isinstance(correct, str) and not correct.strip().isdigit():
                correct = next((i for i, o in enumerate(options)
                                if o == line(correct, 200)), None)
            try:
                correct = int(correct)
            except (TypeError, ValueError):
                continue
            if not question or len(options) < 2 \
                    or not 0 <= correct < len(options):
                continue
            quiz.append({'question': question, 'options': options,
                         'correct': correct})
        if not lessons:
            raise UserError(_("PayAI did not return a course it could use. "
                              "Try again, or start a blank course."))
        return {'title': line(draft.get('title'), 120)
                or lessons[0]['title'],
                'blurb': line(draft.get('blurb'), 600),
                'lessons': lessons, 'quiz': quiz}

    @api.model
    def _make_draft(self, clean, att, lang_key, cfg, cut):
        """The course, as the person (their create rights, their name on it)."""
        lang = LANGS[lang_key][1]
        Channel = self.env['slide.channel'].with_context(
            lang=lang, mail_create_nosubscribe=True)
        values = {
            'name': clean['title'],
            'description': Markup('<p>%s</p>') % clean['blurb']
            if clean['blurb'] else False,
            'channel_type': 'training',
            'visibility': 'members',
            'enroll': 'invite',
            'is_published': False,
            'pb_draft_source_id': att.id,
        }
        from odoo.addons.pb_training.models.training_common import (
            P_COMPLETION_MAIL, flag)
        if not flag(self.env, P_COMPLETION_MAIL) \
                and 'completed_template_id' in Channel._fields:
            values['completed_template_id'] = False
        channel = Channel.create(values)
        # website_slides puts the responsible on their own course as a member
        # (ledger LN46): a draft is nobody's course yet.
        if channel.channel_partner_ids:
            channel._remove_membership(channel.channel_partner_ids.ids)
        Slide = self.env['slide.slide'].with_context(lang=lang)
        seq = 1
        for lesson in clean['lessons']:
            Slide.create({
                'channel_id': channel.id,
                'name': lesson['title'],
                'slide_category': 'article',
                'html_content': lesson['html'],
                'completion_time': lesson['minutes'] / 60.0,
                'sequence': seq,
                'is_published': True,
            })
            seq += 1
        if clean['quiz']:
            Slide.create({
                'channel_id': channel.id,
                'name': _("Check what you learnt"),
                'slide_category': 'quiz',
                'sequence': seq,
                'is_published': True,
                'completion_time': max(len(clean['quiz']), 5) / 60.0,
                'question_ids': [(0, 0, {
                    'question': row['question'],
                    'sequence': n,
                    'answer_ids': [(0, 0, {
                        'text_value': option,
                        'is_correct': i == row['correct'],
                        'sequence': i,
                    }) for i, option in enumerate(row['options'])],
                }) for n, row in enumerate(clean['quiz'], start=1)],
            })
        att.write({'res_id': channel.id})
        model = '%s %s' % (cfg.provider_type or '', cfg.model_name or '')
        note = _("Drafted by PayAI from %(file)s with %(model)s, for %(who)s. "
                 "It is not published: read every lesson before you publish.",
                 file=att.name or '', model=model.strip(),
                 who=self.env.user.name or '')
        if cut:
            note = '%s %s' % (note, _("The document was long, so only its "
                                      "first part was used."))
        channel.message_post(body=escape(note), message_type='comment',
                             subtype_xmlid='mail.mt_note')
        return channel

    # ======================================================== the drawer
    @api.model
    def get_course(self, channel_id):
        data = super().get_course(channel_id)
        try:
            channel = self.env['slide.channel'].sudo().browse(
                int(channel_id or 0))
            if channel.pb_draft_source_id and not channel.is_published:
                data['draft'] = {
                    'file': channel.pb_draft_source_id.name or '',
                    'words': _("Drafted by PayAI from %s. Read every lesson "
                               "before you publish.",
                               channel.pb_draft_source_id.name or ''),
                }
        except Exception:                   # noqa: BLE001 — a banner is extra
            _logger.warning('pb_training_payai: the draft banner could not be '
                            'read', exc_info=True)
        return data
