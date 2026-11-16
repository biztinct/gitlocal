# -*- coding: utf-8 -*-
"""Company policy files HR uploads, read into sections PayAI can search.

A file is read ONCE when it is uploaded (PDF text, Word, plain text; a scan
has no words and says so), cut into sections at its headings, and every
section keeps a folded word list for the search. Nothing is sent anywhere at
upload: the words leave the system only as the few sections that match an
employee's question, at the moment they ask (`pb.policy.answer`).

Only HR reads and changes these rows (access + company rules). Employees
never reach them directly: their page reads the published titles under sudo
after the session check.
"""
import base64
import io
import logging
import re
import unicodedata
import zipfile
from xml.etree import ElementTree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: Upload limits.
MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 200
MAX_CHARS = 400000
MAX_SECTIONS = 600
#: A section longer than this is cut at paragraph boundaries.
SECTION_CHARS = 1400

LANGS = [
    ('any', 'Any language'),
    ('en_US', 'English'),
    ('vi_VN', 'Vietnamese'),
    ('id_ID', 'Indonesian'),
]

#: Words that carry no meaning for a search (English, Vietnamese, Bahasa).
STOPWORDS = frozenset('''
a an and are as at be been but by can could do does for from had has have how i
if in into is it its me my of on or our should so than that the their them then
there these they this to us was we what when where which who why will with you
your yours am any all also about after before more most must may not no only
la va cua cho voi cac nhung mot khi thi duoc co khong la gi nao bao nhieu toi
ban em anh chi minh nay do neu thi se da dang
yang dan di ke dari untuk dengan ini itu ada apa bagaimana berapa saya kami
kita anda tidak bisa akan sudah atau juga pada dalam oleh
'''.split())


def fold(text):
    """Lower case, accents off (Vietnamese đ too): the search's one spelling."""
    text = (text or '').replace('đ', 'd').replace('Đ', 'D')
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def tokens(text):
    """The meaningful words of `text`, folded, in order, de-duplicated."""
    seen, out = set(), []
    for word in re.findall(r'[a-z0-9]+', fold(text)):
        if len(word) < 2 or word in STOPWORDS or word in seen:
            continue
        seen.add(word)
        out.append(word)
    return out


def _decode(raw):
    for enc in ('utf-8', 'utf-16', 'cp1252'):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            continue
    return ''


def _docx_text(raw):
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


def _pdf_text(raw):
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
        _logger.info('pb_me_payai: a PDF could not be read for words',
                     exc_info=True)
        return ''


def text_of(raw, filename=''):
    """The words of an uploaded file ('' when it has none we can read)."""
    if not raw:
        return ''
    name = (filename or '').lower()
    if raw[:5] == b'%PDF-':
        text = _pdf_text(raw)
    elif raw[:2] == b'PK':
        text = _docx_text(raw)
    elif name.endswith(('.txt', '.md', '.text')) or b'\x00' not in raw[:2048]:
        text = _decode(raw)
    else:
        text = ''
    return (text or '')[:MAX_CHARS]


_HEADING = re.compile(
    r'^(?:#{1,4}\s+.+|(?:\d+(?:\.\d+)*[.)]?|[IVXLC]+\.|[A-Z]\.)\s+\S.{0,90}|'
    r'(?:Article|Section|Chapter|Part|Điều|Mục|Chương|Pasal|Bab|Bagian)\s+\S.{0,90})$',
    re.IGNORECASE)


def _is_heading(line):
    line = line.strip()
    if not line or len(line) > 100:
        return False
    if _HEADING.match(line):
        return True
    letters = [c for c in line if c.isalpha()]
    if len(letters) >= 4 and all(c.isupper() for c in letters):
        return True
    return False


def split_sections(text, title=''):
    """[(heading, body)] — cut at headings, long bodies cut at paragraphs."""
    sections, heading, body = [], title or '', []

    def flush():
        words = '\n'.join(body).strip()
        if not words:
            return
        while len(words) > SECTION_CHARS:
            cut = words.rfind('\n', 0, SECTION_CHARS)
            if cut < SECTION_CHARS // 3:
                cut = words.rfind(' ', 0, SECTION_CHARS)
            if cut <= 0:
                cut = SECTION_CHARS
            sections.append((heading, words[:cut].strip()))
            words = words[cut:].strip()
        if words:
            sections.append((heading, words))

    for raw_line in (text or '').splitlines():
        line = raw_line.strip()
        if _is_heading(line):
            flush()
            heading, body = line.lstrip('#').strip()[:200], []
            continue
        body.append(line)
    flush()
    return sections[:MAX_SECTIONS]


class PbPolicyDocument(models.Model):
    _name = 'pb.policy.document'
    _description = 'Company policy file'
    _order = 'published desc, name, id'

    name = fields.Char(string='Title', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 index=True, default=lambda s: s.env.company)
    file = fields.Binary(string='File', attachment=True, required=True)
    filename = fields.Char(string='File name')
    language = fields.Selection(LANGS, string='Language', default='any',
                                required=True)
    published = fields.Boolean(
        string='Employees can ask about it', default=False,
        help='Only published files are searched for an employee question.')
    department_ids = fields.Many2many(
        'hr.department', string='Only for these departments',
        help='Leave empty for everyone in the company.')
    text = fields.Text(string='The words read from the file', readonly=True)
    section_ids = fields.One2many('pb.policy.section', 'document_id',
                                  string='Sections')
    section_count = fields.Integer(compute='_compute_section_count',
                                   string='Number of sections')
    active = fields.Boolean(default=True)

    @api.depends('section_ids')
    def _compute_section_count(self):
        for rec in self:
            rec.section_count = len(rec.section_ids)

    # ---------------------------------------------------------------- read
    def _pbpa_read(self):
        """Read the file into words and sections. Called on create and on a
        new file. Never sends anything anywhere."""
        Section = self.env['pb.policy.section'].sudo()
        for doc in self.sudo():
            raw = base64.b64decode(doc.file or b'') if doc.file else b''
            if len(raw) > MAX_BYTES:
                raise UserError(_("That file is bigger than 10 MB. Upload a "
                                  "smaller one, or split it."))
            text = text_of(raw, doc.filename)
            doc.section_ids.unlink()
            rows = []
            for seq, (heading, body) in enumerate(split_sections(text, doc.name)):
                rows.append({
                    'document_id': doc.id, 'sequence': seq * 10,
                    'heading': heading or doc.name, 'body': body,
                    'keys': ' '.join(tokens(heading + ' ' + body)),
                    'heading_keys': ' '.join(tokens(heading)),
                })
            if rows:
                Section.create(rows)
            super(PbPolicyDocument, doc).write({'text': text})

    @api.model_create_multi
    def create(self, vals_list):
        docs = super().create(vals_list)
        docs._pbpa_read()
        return docs

    def write(self, vals):
        res = super().write(vals)
        if 'file' in vals:
            self._pbpa_read()
        return res


class PbPolicySection(models.Model):
    _name = 'pb.policy.section'
    _description = 'Section of a company policy file'
    _order = 'document_id, sequence, id'

    document_id = fields.Many2one('pb.policy.document', required=True,
                                  ondelete='cascade', index=True)
    company_id = fields.Many2one(related='document_id.company_id', store=True,
                                 index=True)
    sequence = fields.Integer(default=10)
    heading = fields.Char(string='Section')
    body = fields.Text(string='Words')
    keys = fields.Text(string='Search words')
    heading_keys = fields.Char(string='Heading search words')


class PbPolicyQuestion(models.Model):
    """One question asked — WITHOUT the person (owner ruling PA1, 2026-11-16).

    Kept: the question AFTER the name / phone / email / amount scrub (the
    copy that may leave the system — never the typed original), the policy
    and section used, the outcome, whether it used the AI account, and the
    DAY. NOT kept, anywhere on the row: the employee, the login, a session,
    an address, a time of day. `_log_access = False` removes the ORM's own
    stamps (create_uid / write_uid / create_date / write_date) from the
    table altogether, so nothing records who wrote the row or when.

    The per-person daily limit is counted in `pb.policy.quota`, which shares
    no id, no order and no timestamp with these rows (see there).

    Nobody reads this table directly except an administrator: HR reads it
    only through `pb.policy.desk`, which shows numbers only when the company
    has fewer than five people who could ask."""
    _name = 'pb.policy.question'
    _description = 'Policy question asked by an employee'
    _order = 'day desc, id desc'
    _log_access = False

    company_id = fields.Many2one('res.company', required=True, index=True)
    day = fields.Date(required=True, index=True,
                      default=fields.Date.context_today)
    question = fields.Text(string='Question (names taken out)')
    outcome = fields.Selection([
        ('answered', 'Answered from a policy'),
        ('not_found', 'Not in the policies'),
        ('limit', 'Daily limit reached'),
        ('failed', 'Could not answer just then'),
    ], required=True)
    called_ai = fields.Boolean(string='Used the AI account')
    document_ids = fields.Many2many('pb.policy.document',
                                    string='Policies used')
    section_id = fields.Many2one('pb.policy.section', string='Section used',
                                 ondelete='set null')


class PbPolicyQuota(models.Model):
    """The per-person daily limit counter, kept apart from the questions.

    One row per person per DAY, keyed by a one-way code (HMAC of the
    employee and the day with this database's own secret): no employee
    field, no login, no ORM stamps (`_log_access = False`). Rows of earlier
    days are deleted on the next question, so no history of who asked how
    much is ever kept. Nothing on a question row points here, and nothing
    here points at a question: a question cannot be joined to a person.
    Readable by an administrator only."""
    _name = 'pb.policy.quota'
    _description = 'Policy questions: daily count per person'
    _log_access = False

    key = fields.Char(required=True, index=True)
    day = fields.Date(required=True, index=True)
    count = fields.Integer(default=0)
