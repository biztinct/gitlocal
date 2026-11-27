import base64
import binascii
import hashlib
import io

from PIL import Image
from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_datetime
from odoo.tools.pdf import PdfFileReader, merge_pdf
from odoo.addons.pb_new_hire.models.studio_docs import FILE_MAX

PAPER_MAX = 5 * 1024 * 1024
INK_MAX = 300 * 1024


def pdf_bytes(encoded):
    if not isinstance(encoded, str) or len(encoded) > 4 * ((PAPER_MAX + 2) // 3):
        raise UserError(_('Choose a PDF up to 5 MB.'))
    try:
        raw = base64.b64decode(encoded, validate=True)
        if (
            not raw.startswith(b'%PDF-')
            or len(raw) > PAPER_MAX
            or not PdfFileReader(io.BytesIO(raw), strict=False).getNumPages()
        ):
            raise ValueError()
    except Exception:
        raise UserError(_('Choose a readable PDF up to 5 MB.')) from None
    return raw


class Paper(models.Model):
    _name = 'pb.joining.paper'
    _description = 'Company paper to sign'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda s: s.env.company)
    country_code = fields.Char(size=2)
    attachment_id = fields.Many2one('ir.attachment', ondelete='restrict', copy=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class Signature(models.Model):
    _name = 'pb.joining.sign'
    _description = 'Joining paper signature'
    _order = 'sequence, id'

    joining_id = fields.Many2one('pb.joining', required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(related='joining_id.company_id', store=True, index=True)
    paper_id = fields.Many2one('pb.joining.paper', ondelete='restrict', required=True)
    paper_name = fields.Char(required=True)
    sequence = fields.Integer()
    original_id = fields.Many2one('ir.attachment', ondelete='restrict')
    paper_sha256 = fields.Char()
    signature = fields.Binary(attachment=True)
    signer_name = fields.Char()
    opened_at = fields.Datetime()
    signed_on = fields.Datetime()
    ip = fields.Char()
    user_agent = fields.Char()
    signed_attachment_id = fields.Many2one('ir.attachment', copy=False)
    return_note = fields.Char(size=200)
    _unique_paper = models.Constraint('UNIQUE(joining_id,paper_id)', 'This paper is already on the list.')

    def _record_open(self):
        self.joining_id._lock()
        if not self.opened_at:
            self.opened_at = fields.Datetime.now()

    def _sign(self, ink, name, agree, ip, agent):
        j = self.joining_id
        j._lock()
        self.invalidate_recordset()
        if (
            not self.original_id
            or self.signed_on
            or j.state not in ('invited', 'filling')
            or (j.submitted_at and not self.return_note)
            or j.proposal_id
        ):
            raise UserError(_('This paper is no longer waiting for a signature.'))
        name = str(name or '').strip()
        if not self.opened_at or agree != '1' or not name or len(name) > 200:
            raise UserError(_('Open the paper, agree to it and enter your name.'))
        if (
            not isinstance(ink, str)
            or not ink.startswith('data:image/png;base64,')
            or len(ink) > 4 * ((INK_MAX + 2) // 3) + 22
        ):
            raise UserError(_('Sign here with your finger.'))
        try:
            raw = base64.b64decode(ink.split(',', 1)[1], validate=True)
            img = Image.open(io.BytesIO(raw))
            if img.format != 'PNG' or len(raw) > INK_MAX or max(img.size) > 2400 or min(img.size) < 2:
                raise ValueError()
            canvas = Image.new('RGB', img.size, 'white')
            rgba = img.convert('RGBA')
            canvas.paste(rgba, mask=rgba.getchannel('A'))
            if canvas.convert('L').getextrema()[0] >= 220 or canvas.convert('L').getextrema()[1] < 220:
                raise ValueError()
            normalized = io.BytesIO()
            canvas.save(normalized, format='PNG')
        except (ValueError, OSError, Image.DecompressionBombError, binascii.Error):
            raise UserError(_('Sign here with your finger.')) from None
        original = self.original_id.raw
        self.write(
            {
                'signature': base64.b64encode(normalized.getvalue()),
                'signer_name': name,
                'signed_on': fields.Datetime.now(),
                'ip': str(ip or '')[:60],
                'user_agent': str(agent or '')[:512],
                'paper_sha256': hashlib.sha256(original).hexdigest(),
                'return_note': False,
            }
        )
        cert, fmt = (
            self.env['ir.actions.report']
            .sudo()
            .with_context(force_report_rendering=True)
            ._render_qweb_pdf('pb_joining.report_sign', res_ids=self.ids)
        )
        if fmt != 'pdf':
            raise UserError(_('The signed copy could not be made. Please try again.'))
        signed = merge_pdf([original, cert])
        if len(signed) > FILE_MAX:
            raise UserError(_('The signed copy is too large to file. Ask HR for a smaller paper.'))
        self.signed_attachment_id = (
            self.env['ir.attachment']
            .sudo()
            .create(
                {
                    'name': self.paper_name + '.pdf',
                    'raw': signed,
                    'mimetype': 'application/pdf',
                    'public': False,
                    'res_model': self._name,
                    'res_id': self.id,
                }
            )
        )
        j.review_revision += 1


class SignReport(models.AbstractModel):
    _name = 'report.pb_joining.sign_page'
    _description = 'Signing confirmation'

    @api.model
    def _get_report_values(self, docids, data=None):
        rows = self.env['pb.joining.sign'].browse(docids)
        rows.check_access('read')
        pages = []
        for r in rows:
            j = r.joining_id
            tz = j.company_id.resource_calendar_id.tz or 'UTC'
            pages.append(
                {
                    'name': r.paper_name,
                    'hash': r.paper_sha256,
                    'who': r.signer_name,
                    'when': format_datetime(self.env, r.signed_on, tz=tz) + ' (' + tz + ')',
                    'ink': 'data:image/png;base64,' + r.signature.decode(),
                    'contact': j._masked_email() or ('•••• ' + (j.phone or '')[-4:]),
                }
            )
        return {'pages': pages}


class JoiningSigns(models.Model):
    _inherit = 'pb.joining'

    sign_ids = fields.One2many('pb.joining.sign', 'joining_id')

    def _sync_signs(self):
        for j in self:
            if j.state not in ('invited', 'filling') or j.submitted_at:
                continue
            papers = (
                self.env['pb.joining.paper']
                .sudo()
                .search(
                    [
                        ('company_id', '=', j.company_id.id),
                        ('country_code', 'in', [False, j.payroll_country]),
                        ('attachment_id', '!=', False),
                    ]
                )
            )
            current = {s.paper_id.id: s for s in j.sign_ids}
            for paper in papers:
                row = current.pop(paper.id, None)
                vals = {
                    'original_id': paper.attachment_id.id,
                    'paper_name': paper.with_context(lang=j.lang or 'en_US').name,
                    'sequence': paper.sequence,
                }
                if not row:
                    self.env['pb.joining.sign'].sudo().create(dict(vals, joining_id=j.id, paper_id=paper.id))
                elif not row.signed_on:
                    if row.original_id != paper.attachment_id:
                        vals['opened_at'] = False
                    row.write(vals)
            for obsolete in current.values():
                if not obsolete.signed_on:
                    obsolete.unlink()

    @api.model_create_multi
    def create(self, vals_list):
        rows = super().create(vals_list)
        rows._sync_signs()
        return rows

    def _change_country(self, code):
        super()._change_country(code)
        self._sync_signs()

    def _section_states(self):
        result = super()._section_states()
        if self.sign_ids:
            result['sign'] = (
                'returned'
                if any(self.sign_ids.mapped('return_note'))
                else ('done' if self._paper_signing_done() else 'empty')
            )
        return result

    def _paper_signing_done(self):
        return all(s.signed_on for s in self.sign_ids)

    @api.depends('sign_ids', 'sign_ids.signed_on', 'sign_ids.return_note')
    def _compute_status(self):
        super()._compute_status()
        for j in self:
            j.sent_back_count += len(j.sign_ids.filtered('return_note'))


class BoardPapers(models.AbstractModel):
    _inherit = 'pb.joining.board'

    def _sign_rows(self, j, manage):
        return [
            {
                'id': s.id,
                'name': s.paper_name,
                'status': (_('Signed %s', format_datetime(self.env, s.signed_on)) if manage else _('Signed'))
                if s.signed_on
                else _('Read and sign'),
                'url': self._file_row(j, s.signed_attachment_id)['url']
                if manage and s.signed_attachment_id
                else '',
                'signed': bool(s.signed_on),
                'note': s.return_note if manage else '',
            }
            for s in j.sign_ids
        ]

    def _files(self, j):
        return super()._files(j) | j.sign_ids.signed_attachment_id

    @api.model
    def return_paper(self, joining_id, sign_id, note):
        j = self._mutable(joining_id)
        s = j.sign_ids.filtered(lambda r: r.id == sign_id)
        if not s or not s.signed_on or not j.submitted_at or j.state not in ('filling', 'to_check'):
            raise UserError(_('This paper is not waiting for your check.'))
        note = str(note or '').strip()
        if not note or len(note) > 200:
            raise UserError(_('Write what needs fixing in 200 characters or fewer.'))
        old = s.signed_attachment_id
        s.write(
            {
                'return_note': note,
                'signature': False,
                'signed_on': False,
                'signer_name': False,
                'ip': False,
                'user_agent': False,
                'signed_attachment_id': False,
                'opened_at': False,
            }
        )
        old.unlink()
        j.write({'state': 'filling', 'review_revision': j.review_revision + 1})
        if not j._mail('joining_back', {'notes': s.paper_name + ' — ' + note}):
            j.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=j._contact().id,
                summary=_('Pass on the request to fix details to %(name)s', name=j.name),
            )
        return self.get_one(j.id)

    @api.model
    def papers_load(self):
        self._check_manage()
        rows = (
            self.env['pb.joining.paper']
            .sudo()
            .with_context(active_test=False)
            .search([('company_id', '=', self.env.company.id)])
        )
        return {
            'countries': self.env['pb.new.hire']._countries(),
            'rows': [
                {
                    'id': r.id,
                    'name': r.name,
                    'country': r.country_code or '',
                    'file': r.attachment_id.name,
                    'on': r.active,
                    'sequence': r.sequence,
                }
                for r in rows
            ],
        }

    @api.model
    def papers_save(self, rows):
        self._check_manage()
        papers = self.env['pb.joining.paper'].sudo().with_context(active_test=False)
        countries = dict(self.env['pb.new.hire']._countries())
        if not isinstance(rows, list) or len(rows) > 100:
            raise UserError(_('Save up to 100 papers at once.'))
        for data in rows:
            country = data.get('country') or False
            name = str(data.get('name') or '').strip()[:180]
            if not name or country and country not in countries:
                raise UserError(_('Give the paper a name and choose a country of work.'))
            vals = {
                'name': name,
                'country_code': country,
                'active': bool(data.get('on')),
                'sequence': int(data.get('sequence') or 10),
            }
            if data.get('id'):
                p = papers.search(
                    [('id', '=', int(data['id'])), ('company_id', '=', self.env.company.id)], limit=1
                )
                if not p:
                    raise AccessError(_('You cannot open this file.'))
                p.write(vals)
            else:
                p = papers.create(dict(vals, company_id=self.env.company.id))
            if data.get('data'):
                raw = pdf_bytes(data['data'])
                p.attachment_id = (
                    self.env['ir.attachment']
                    .sudo()
                    .create(
                        {
                            'name': str(data.get('file') or name + '.pdf')[:200],
                            'raw': raw,
                            'mimetype': 'application/pdf',
                            'res_model': p._name,
                            'res_id': p.id,
                            'public': False,
                        }
                    )
                )
            if not p.attachment_id:
                raise UserError(_('Choose a PDF up to 5 MB.'))
        self.env['pb.joining'].sudo().search(
            [
                ('company_id', '=', self.env.company.id),
                ('state', 'in', ['invited', 'filling']),
                ('submitted_at', '=', False),
            ]
        )._sync_signs()
        return self.papers_load()

    @api.model
    def save_settings(self, settings):
        self._check_manage()
        self.settings(settings)
        return self.papers_save(settings.get('papers') or [])
