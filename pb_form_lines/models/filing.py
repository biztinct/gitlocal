# -*- coding: utf-8 -*-
"""One government filing: the files for one form, one company, one period.

A CLONE OF THE PAYMENT LIST'S FILE RECORD (`pb.payment.list.file`,
WDGAP IDB2). Preparing reads the figures (`pb.gov.form.reader`), renders the
form's files (`_pb_render_<code>`), stores them with a sha256 each and one
stamp over all of them, and replaces the previous try for the same form,
company, period and currency. Approval goes through the EXISTING catalogue row
`filing` ("Government filings") — the same published route, the same
approvers, the same independence setting as every other government filing.
No route is laid here and no second key is created: this model has no
`_approval_seed_default` (ledger IDB1-6); its capabilities are the filing
proposal's when that model is installed. On rize the `filing` route is
whatever rize has published for it.

Download: approved bytes only — the stamp is checked again on every download —
and one line in the record's history and in the platform trail (who, which
file, how many people; never a tax number).

THE ADVISER MARK (G3) is decided at prepare time: while the company has not
marked the form "Accepted by the authority", every file carries the sentence
and the record remembers that it did (`adviser_mark`).

Renderers (wave 2 adds more by inheriting this model)::

    def _pb_render_<form code in lower case>(self, data) -> [(filename, bytes, mimetype)]
"""
import hashlib
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang

_logger = logging.getLogger(__name__)

FILING_PROCESS_KEY = 'filing'

STATES = [
    ('draft', 'Prepared'),
    ('pending', 'Waiting for approval'),
    ('approved', 'Approved'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('superseded', 'Replaced'),
]

ADVISER_MARK = "Check with your adviser before first filing"


def _safe_name(text):
    text = re.sub(r'[^\w\-]+', '_', text or '', flags=re.UNICODE).strip('_')
    return text[:60] or 'company'


class PbGovFiling(models.Model):
    _name = 'pb.gov.filing'
    _description = 'Government filing'
    _inherit = ['mail.thread', 'biz.approval.adapter.mixin']
    _order = 'id desc'

    _approval_process_key = FILING_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    form_id = fields.Many2one('pb.gov.form', required=True, index=True,
                              ondelete='restrict', readonly=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 readonly=True)
    period_start = fields.Date(required=True, readonly=True)
    period_end = fields.Date(required=True, readonly=True)
    period_label = fields.Char(readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    scheme_ids = fields.Many2many('hr.formula.config', 'pb_gov_filing_scheme_rel',
                                  'filing_id', 'config_id', string='Pay schemes',
                                  readonly=True)
    state = fields.Selection(STATES, default='draft', required=True, index=True,
                             readonly=True, copy=False)
    file_ids = fields.One2many('pb.gov.filing.file', 'filing_id', readonly=True)
    file_hash = fields.Char(string='File stamp', readonly=True, copy=False)
    approved_hash = fields.Char(string='Approved stamp', readonly=True, copy=False)
    row_count = fields.Integer(string='People', readonly=True)
    total_amount = fields.Monetary(string='Total', readonly=True,
                                   currency_field='currency_id')
    totals_json = fields.Text(readonly=True)
    warnings_json = fields.Text(readonly=True)
    warning_count = fields.Integer(readonly=True)
    payslip_ids = fields.Many2many('hr.payslip', 'pb_gov_filing_slip_rel',
                                   'filing_id', 'slip_id', readonly=True, copy=False)
    adviser_mark = fields.Boolean(
        string='Says "check with your adviser"', readonly=True,
        help="The files carry the adviser sentence: the company had not marked "
             "this form accepted by the authority when they were prepared.")
    generated_by = fields.Many2one('res.users', string='Prepared by', readonly=True)
    generated_at = fields.Datetime(string='Prepared on', readonly=True)
    superseded_by_id = fields.Many2one('pb.gov.filing', string='Replaced by',
                                       readonly=True, ondelete='set null')
    downloaded_at = fields.Datetime(readonly=True)
    downloaded_by = fields.Many2one('res.users', readonly=True)
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_gov_filing_seat_rel', 'filing_id', 'user_id',
        string='Asked to decide', copy=False)

    @api.model
    def _pb_adviser_text(self):
        """The G3 sentence, in the reader's language (one literal so the
        terms export sees it)."""
        return _("Check with your adviser before first filing")

    @api.depends('form_id.name', 'period_label')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s · %s' % (rec.form_id.name or '', rec.period_label or '')

    # ============================================================== reading
    def _pb_json(self, field):
        self.ensure_one()
        try:
            data = json.loads(self[field] or 'null')
        except (TypeError, ValueError):
            data = None
        return data

    def _pb_totals(self):
        return self._pb_json('totals_json') or {}

    def _pb_warnings(self):
        return self._pb_json('warnings_json') or []

    def _state_label(self):
        self.ensure_one()
        return dict(self._fields['state']._description_selection(self.env)).get(self.state, '')

    def _money(self, value):
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        return formatLang(self.env, float(value or 0.0), currency_obj=currency)

    @api.model
    def _pb_period_label(self, form, start, end):
        start = fields.Date.to_date(start)
        end = fields.Date.to_date(end)
        if form.period_kind == 'month':
            return format_date(self.env, start, date_format='MMMM y')
        return '%s – %s' % (format_date(self.env, start, date_format='MMM y'),
                            format_date(self.env, end, date_format='MMM y'))

    @api.model
    def _pb_latest(self, form, company, start, end, currency=None):
        domain = [('form_id', '=', form.id), ('company_id', '=', company.id),
                  ('period_start', '=', start), ('period_end', '=', end),
                  ('state', '!=', 'superseded')]
        if currency:
            domain.append(('currency_id', '=', currency.id))
        return self.search(domain, order='id desc', limit=1)

    # ============================================================ preparing
    @api.model
    def prepare(self, form, company, start, end, scheme_ids=None, currency_id=None):
        """Read, render, store, replace the last try. Nothing is sent in here
        (the screen sends the record with `biz.approval.engine.submit`)."""
        self.env['pb.gov.form.rights']._pb_require_officer()
        Reader = self.env['pb.gov.form.reader']
        form = Reader._pb_form(form)
        company = Reader._pb_company_rec(company)
        if company not in self.env.user.company_ids and not self.env.su:
            raise AccessError(_("Switch to that company first."))
        start = fields.Date.to_date(start)
        end = fields.Date.to_date(end)
        if not form._pb_valid_for(start) or not form._pb_valid_for(end):
            raise UserError(_("This layout of “%s” is not the one for that period.", form.name))
        data = Reader._pb_read(form, company, start, end, scheme_ids=scheme_ids,
                               currency_id=currency_id)
        blocks = [w for w in data['warnings'] if w.get('level') == 'block']
        if blocks:
            raise UserError(blocks[0]['message'])
        if not data['employees']:
            raise UserError(_("Nobody is in this filing, so there is nothing to prepare."))
        settings = self.env['pb.gov.form.company']._pb_for(form, company)
        mark = not settings.accepted
        data['adviser_mark'] = mark
        data['adviser_text'] = self._pb_adviser_text() if mark else ''
        data['settings'] = {'employer_tax_id': settings.employer_tax_id or '',
                            'place_of_business': settings.place_of_business or ''}
        data['company_name'] = company.name or ''
        data['period_label'] = self._pb_period_label(form, start, end)
        record = self.sudo().create({
            'form_id': form.id, 'company_id': company.id,
            'period_start': start, 'period_end': end,
            'period_label': data['period_label'],
            'currency_id': data['currency_id'] or company.currency_id.id,
            'scheme_ids': [(6, 0, [s['id'] for s in data['schemes']])],
            'row_count': len(data['employees']),
            'total_amount': float((data['lines'] or {}).get(form.total_line_code) or 0.0),
            'totals_json': json.dumps(data['lines']),
            'warnings_json': json.dumps(data['warnings']),
            'warning_count': len([w for w in data['warnings'] if w.get('level') != 'info']),
            'payslip_ids': [(6, 0, data['payslip_ids'])],
            'adviser_mark': mark,
            'generated_by': self.env.uid,
            'generated_at': fields.Datetime.now(),
        })
        files = record._pb_render(data)
        File = self.env['pb.gov.filing.file'].sudo()
        Attachment = self.env['ir.attachment'].sudo()
        for seq, (filename, payload, mimetype) in enumerate(files, start=1):
            attachment = Attachment.create({
                'name': filename, 'type': 'binary', 'raw': payload,
                'res_model': self._name, 'res_id': record.id, 'mimetype': mimetype,
            })
            File.create({'filing_id': record.id, 'sequence': seq, 'name': filename,
                         'mimetype': mimetype, 'attachment_id': attachment.id,
                         'sha256': hashlib.sha256(payload or b'').hexdigest(),
                         'size': len(payload or b'')})
        record.sudo().write({'file_hash': record._live_hash()})
        record._supersede_earlier()
        record._log(_("Prepared by %(who)s from %(n)s finished payslips: %(people)s people, %(files)s files.",
                      who=self.env.user.name, n=len(data['payslip_ids']),
                      people=record.row_count, files=len(files)))
        return record.with_env(self.env)

    def _pb_render(self, data):
        """The form's renderer, by its code — a method name made only of
        letters, digits and underscores, starting `_pb_render_`."""
        self.ensure_one()
        code = (self.form_id.code or '').lower()
        if not re.fullmatch(r'[a-z0-9_]+', code):
            raise UserError(_("This form has no file layout yet."))
        renderer = getattr(self, '_pb_render_%s' % code, None)
        if renderer is None:
            raise UserError(_("This form has no file layout yet."))
        files = renderer(data) or []
        if not files:
            raise UserError(_("The file could not be made."))
        return files

    @api.model
    def _pb_filename(self, data, stem, ext):
        start = (data.get('period_start') or '')[:7]
        end = (data.get('period_end') or '')[:7]
        if start and end and start != end:
            period = '%s-%s' % (start.replace('-', ''), end.replace('-', ''))
        else:
            period = start.replace('-', '')
        return '%s_%s_%s.%s' % (stem, _safe_name(data.get('company_name')), period, ext)

    def _live_hash(self):
        """One stamp over every file, read from the attachments each time."""
        self.ensure_one()
        parts = []
        for f in self.sudo().file_ids.sorted('sequence'):
            raw = f.attachment_id.raw if f.attachment_id else None
            if raw is None:
                return ''
            parts.append(hashlib.sha256(raw).hexdigest())
        if not parts:
            return ''
        return hashlib.sha256(''.join(parts).encode()).hexdigest()

    def _supersede_earlier(self):
        self.ensure_one()
        earlier = self.sudo().search([
            ('form_id', '=', self.form_id.id), ('company_id', '=', self.company_id.id),
            ('period_start', '=', self.period_start), ('period_end', '=', self.period_end),
            ('currency_id', '=', self.currency_id.id),
            ('id', '!=', self.id), ('state', 'not in', ('superseded', 'rejected'))])
        engine = self.env['biz.approval.engine']
        for old in earlier:
            request = old.approval_request_id
            if request and request.state in ('pending', 'blocked'):
                try:
                    with self.env.cr.savepoint():
                        engine.sudo().cancel(request, _("A newer filing replaced this one."))
                except Exception:   # noqa: BLE001 — never stop the new filing
                    _logger.warning('pb_form_lines: could not withdraw the request on filing %s', old.id)
            old.sudo().write({'state': 'superseded', 'superseded_by_id': self.id,
                              'approved_hash': False})
            old._log(_("Replaced by a newer filing."))
        return True

    def _log(self, body):
        for rec in self:
            rec.sudo().message_post(body=body, subtype_xmlid='mail.mt_note')

    def _audit(self, label, value):
        Entry = self.env.get('biz.audit.entry')
        if Entry is None:
            return False
        try:
            with self.env.cr.savepoint():
                Entry.sudo().create({
                    'model_name': self._name, 'res_id': self.id,
                    'res_display': self.display_name or '', 'field_name': 'pb_gov_filing',
                    'field_label': label, 'old_value': '', 'new_value': (value or '')[:256],
                    'company_id': self.company_id.id,
                })
        except Exception:       # noqa: BLE001 — a trail line never blocks a download
            _logger.exception('pb_form_lines: audit entry failed for %s', self)
        return True

    # ============================================================== adapter
    def _approval_validate(self):
        self.ensure_one()
        if self.state in ('pending', 'approved'):
            raise UserError(_("This filing has already been sent in."))
        if self.state == 'superseded':
            raise UserError(_("A newer filing has replaced this one. Send that one in instead."))
        if self.state == 'rejected':
            raise UserError(_("This filing was turned down. Prepare it again."))
        if not self.file_ids:
            raise UserError(_("There is no file to approve."))
        return True

    def _approval_context(self):
        self.ensure_one()
        rec = self.sudo()
        currency = rec.currency_id or rec.company_id.currency_id
        totals = rec._pb_totals()
        return {
            'company_id': rec.company_id.id,
            'title': rec.name or _("Government filing"),
            'scope_keys': [''],
            'scope_label': rec.company_id.name,
            'kind_key': 'any',
            # the filing proposal's own facts, so a route that tests them
            # reads them for this record too
            'facts': {
                'country': {'value': rec.form_id.country_code or '', 'unit': ''},
                'filing_key': {'value': rec.form_id.code or '', 'unit': ''},
                'period': {'value': rec.period_label or '', 'unit': ''},
                'row_count': {'value': rec.row_count, 'unit': ''},
                'control_total': {'value': float(rec.total_amount or 0.0),
                                  'unit': currency.name or ''},
            },
            'amount': float(rec.total_amount or 0.0),
            'currency_id': currency.id,
            'maker_uids': [u for u in [rec.generated_by.id] if u],
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': rec._live_hash(),
            'evidence': [
                {'key': 'figures', 'name': _("Read from finished payslips"), 'ok': True,
                 'note': _("%s payslips", len(rec.payslip_ids))},
                {'key': 'warnings', 'name': _("Points to check"),
                 'ok': not rec.warning_count, 'note': str(rec.warning_count)},
                {'key': 'adviser', 'name': _("Accepted by the authority before"),
                 'ok': not rec.adviser_mark,
                 'note': self._pb_adviser_text() if rec.adviser_mark else ''},
            ],
        }

    @api.model
    def _approval_capabilities(self):
        if 'pb.filing.proposal' in self.env:
            return self.env['pb.filing.proposal']._approval_capabilities()
        return {
            'facts': {'country': {'type': 'char', 'label': _('Country')},
                      'filing_key': {'type': 'char', 'label': _('Which filing')},
                      'period': {'type': 'char', 'label': _('Period')}},
            'kinds': [], 'evidence': [], 'scope_levels': [_('Whole company')],
            'manager_mode': False,
        }

    @api.model
    def _approval_coverage_scopes(self, company):
        if 'pb.filing.proposal' in self.env:
            return self.env['pb.filing.proposal']._approval_coverage_scopes(company)
        return [{'scope_key': '', 'scope_keys': [''], 'label': company.name,
                 'headcount': 0, 'kind_key': 'any', 'facts': {}}]

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.row_count == 1:
            return _("1 person")
        return _("%s people", self.row_count)

    def _approval_detail(self, request):
        """What an approver reads: the form's totals in the form's order, and
        the points to check. Names only — never a tax number."""
        self.ensure_one()
        rec = self.sudo()
        chips = [{'label': _("Form"), 'value': rec.form_id.name or ''},
                 {'label': _("Period"), 'value': rec.period_label or ''},
                 {'label': _("People"), 'value': str(rec.row_count)}]
        if rec.adviser_mark:
            chips.append({'label': _("Note"), 'value': self._pb_adviser_text()})
        totals = rec._pb_totals()
        rows = []
        for line in rec.form_id._pb_ordered_lines():
            if line.code not in totals:
                continue
            value = totals[line.code]
            text = str(value) if line.kind == 'count' else '{:,.2f}'.format(float(value or 0.0))
            rows.append({'head': '[%s] %s' % (line.code, line.label), 'sub': '',
                         'cells': [text], 'tone': ''})
        for warn in rec._pb_warnings()[:20]:
            rows.append({'head': _("To check"), 'sub': '', 'cells': [warn.get('message') or ''],
                         'tone': 'off'})
        return {'title': _("What this filing says"), 'columns': [_("Amount")],
                'rows': rows, 'chips': chips, 'note': ''}

    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending'})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned', 'approved_hash': False})
        self._log(_("Sent back: %s", reason or ''))
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'rejected', 'approved_hash': False})
        self._log(_("Turned down: %s", reason or ''))
        return True

    def _approval_withdraw(self, request, reason):
        self.ensure_one()
        if self.state == 'pending':
            self.sudo().write({'state': 'draft'})
        return True

    def _approval_apply(self, request):
        """Approved: THESE bytes, and nothing else, may be downloaded. Runs
        as the decider, who may hold no payroll right (ledger W2B-2): every
        read and write here is under sudo."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state == 'approved' and rec.approved_hash:
            return True
        live = rec._live_hash()
        if not live:
            raise UserError(_("The file is missing, so it cannot be approved."))
        if rec.file_hash and live != rec.file_hash:
            raise UserError(_("The filing changed after it was sent in, so this approval no longer covers it. Prepare it again."))
        rec.write({'state': 'approved', 'approved_hash': live})
        rec._log(_("Approved by %s.", self.env.user.name))
        self.env['biz.approval.event']._log(
            'applied', _("%(who)s approved the filing %(name)s (%(n)s people)",
                         who=self.env.user.name, name=rec.name or '', n=rec.row_count),
            company=rec.company_id, request=request)
        return True

    # ============================================================ the way out
    def _pb_download(self, file_id):
        """Approved bytes only; one history line and one trail line."""
        self.ensure_one()
        self.env['pb.gov.form.rights']._pb_require_officer()
        rec = self.sudo()
        if rec.state == 'superseded':
            raise UserError(_("A newer filing has replaced this one. Download that one instead."))
        if rec.state != 'approved' or not rec.approved_hash:
            raise UserError(_("This filing has not been approved yet, so it cannot be downloaded."))
        if rec._live_hash() != rec.approved_hash:
            raise UserError(_("This is not the approved filing — what is stored no longer matches what was signed off. Prepare it again."))
        try:
            fid = int(file_id)
        except (TypeError, ValueError):
            fid = 0
        f = rec.file_ids.filtered(lambda x: x.id == fid)[:1]
        if not f:
            raise UserError(_("That file is not part of this filing."))
        raw = f.attachment_id.raw or b''
        if hashlib.sha256(raw).hexdigest() != f.sha256:
            raise UserError(_("This is not the approved filing — what is stored no longer matches what was signed off. Prepare it again."))
        rec.write({'downloaded_at': fields.Datetime.now(), 'downloaded_by': self.env.uid})
        rec._log(_("%(who)s downloaded %(file)s (%(n)s people).",
                   who=self.env.user.name, file=f.name, n=rec.row_count))
        rec._audit(_("Government filing downloaded"),
                   _("%(who)s · %(file)s · %(n)s people", who=self.env.user.name,
                     file=f.name, n=rec.row_count))
        return f.name, f.mimetype or 'application/octet-stream', raw


class PbGovFilingFile(models.Model):
    _name = 'pb.gov.filing.file'
    _description = 'File of a government filing'
    _order = 'filing_id, sequence, id'

    filing_id = fields.Many2one('pb.gov.filing', required=True, index=True,
                                ondelete='cascade')
    company_id = fields.Many2one(related='filing_id.company_id', store=True, index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    mimetype = fields.Char()
    attachment_id = fields.Many2one('ir.attachment', required=True, ondelete='restrict')
    sha256 = fields.Char(readonly=True)
    size = fields.Integer(readonly=True)


class BizApprovalRequestSeatFiling(models.Model):
    """A seat on a filing is also a read of it (ledger AM60, W2B-3: this
    module's model is not in pb_pay_delivery's fixed SEATED_MODELS)."""
    _inherit = 'biz.approval.request.seat'

    @api.model_create_multi
    def create(self, vals_list):
        seats = super().create(vals_list)
        for seat in seats:
            request = seat.step_id.request_id
            if request.res_model != 'pb.gov.filing' or not request.res_id:
                continue
            record = self.env['pb.gov.filing'].sudo().browse(request.res_id).exists()
            people = {seat.acting_user_id.id, seat.user_id.id}
            people.discard(False)
            if record and people:
                record.write({'seat_user_ids': [(4, uid) for uid in sorted(people)]})
        return seats
