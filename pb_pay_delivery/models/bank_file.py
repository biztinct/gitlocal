# -*- coding: utf-8 -*-
"""The file the bank pays from is a record, not a download.

WHAT WAS TRUE BEFORE. "Generate bank file" built the bytes in memory, handed
them to the browser as base64 and kept nothing. Whoever could open Pay &
Deliver could produce a payment instruction for a whole company's payroll, at
any moment, with no second person and no trace beyond an optional analytics log
row. Two people generating at different minutes got two different files and
nothing in the app could tell you which one the bank actually received.

WHAT IS TRUE NOW. Every generation writes a `pb.bank.file`: the bytes on an
attachment, a sha256 of those bytes, the control total, the row count and the
rows that were left out. The record travels the route the business published
for "Bank file creation". Downloading is refused unless the record is APPROVED
and the attachment still hashes to what was approved — so a file edited after
sign-off is not the approved file and says so. Regenerating does not overwrite:
it supersedes, and asks again.

THE HASH IS CHECKED TWICE, on purpose. The engine compares `source_revision` at
apply time, which is the same number; the sentence a person needs when it does
not match is about their bank file, not about a revision.
"""

import base64
import hashlib
import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .approval_common import PAY_GROUPS  # noqa: F401 — re-exported for tests

_logger = logging.getLogger(__name__)

#: The catalogue key this model is approved under.
BANKFILE_PROCESS_KEY = 'bankfile'

STATES = [
    ('draft', 'Being prepared'),
    ('pending', 'Waiting for approval'),
    ('approved', 'Approved'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
    ('superseded', 'Replaced by a newer file'),
]


def sha256_of(data):
    return hashlib.sha256(data or b'').hexdigest()


class PbBankFile(models.Model):
    _name = 'pb.bank.file'
    _inherit = ['biz.approval.adapter.mixin', 'pb.money.approval.mixin']
    _description = 'Bank Payment File'
    _order = 'id desc'

    _approval_process_key = BANKFILE_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    run_id = fields.Many2one('hr.payslip.run', string='Pay run', required=True,
                             index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency')
    layout_id = fields.Many2one('pb.bank.file.layout', string='Bank layout',
                                ondelete='set null')
    bank_format = fields.Char(string='Bank', readonly=True)
    company_account = fields.Char(string='Company debit account',
                                  readonly=True)

    attachment_id = fields.Many2one('ir.attachment', string='The file',
                                    readonly=True, ondelete='restrict',
                                    copy=False)
    filename = fields.Char(readonly=True)
    file_hash = fields.Char(string='File stamp', readonly=True, copy=False)
    approved_hash = fields.Char(string='Approved stamp', readonly=True,
                                copy=False)
    byte_size = fields.Integer(readonly=True)

    control_total = fields.Monetary(string='Control total', readonly=True,
                                    currency_field='currency_id')
    row_count = fields.Integer(string='Rows', readonly=True)
    excluded_json = fields.Text(string='Left out (JSON)', readonly=True)
    excluded_count = fields.Integer(readonly=True)

    generated_by = fields.Many2one('res.users', string='Prepared by',
                                   readonly=True,
                                   default=lambda s: s.env.user)
    generated_at = fields.Datetime(readonly=True,
                                   default=fields.Datetime.now)
    superseded_by_id = fields.Many2one('pb.bank.file', string='Replaced by',
                                       readonly=True, ondelete='set null')
    downloaded_at = fields.Datetime(readonly=True)
    downloaded_by = fields.Many2one('res.users', readonly=True)

    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False)

    #: A seat is also a read (ledger AM60).
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_bank_file_seat_rel', 'file_id', 'user_id',
        string='Asked to decide', copy=False)

    @api.depends('run_id', 'bank_format', 'generated_at')
    def _compute_name(self):
        for rec in self:
            rec.name = _("Bank file · %(bank)s · %(run)s",
                         bank=(rec.bank_format or '').title() or _('bank'),
                         run=rec.run_id.name or '')

    def excluded(self):
        self.ensure_one()
        try:
            rows = json.loads(self.excluded_json or '[]')
        except (TypeError, ValueError):
            return []
        return rows if isinstance(rows, list) else []

    # ==================================================================
    # Preparing one
    # ==================================================================
    @api.model
    def prepare(self, run, bank_format, company_account=None):
        """Generate the bytes, store them, supersede the last try, ask.

        The only way a bank file comes into existence. Returns the new record;
        the caller sends it in.
        """
        run = run if isinstance(run, models.BaseModel) \
            else self.env['hr.payslip.run'].browse(int(run))
        if not run.exists():
            raise UserError(_("That pay run no longer exists."))
        self.require_pay()
        if (run.state or '') != 'done':
            raise UserError(_(
                "“%s” has not been approved yet, so a bank file cannot be "
                "prepared from it. Send the pay run in for approval first.",
                run.name or ''))

        wizard = self.env['vietnam.bank.export.wizard'].create({
            'payslip_run_id': run.id, 'bank_format': bank_format,
            'company_account_number': company_account or False,
        })
        result = wizard._generate()
        data = base64.b64decode(result['file_b64'])

        attachment = self.env['ir.attachment'].sudo().create({
            'name': result['filename'],
            'type': 'binary',
            'datas': result['file_b64'],
            'res_model': self._name,
            'res_id': 0,
            'mimetype': 'application/octet-stream',
        })
        company = getattr(run, 'company_id', False) or self.env.company
        record = self.create({
            'run_id': run.id,
            'company_id': company.id,
            'currency_id': company.currency_id.id,
            'layout_id': self.env['pb.bank.file.layout']._for_format(
                bank_format).id or False,
            'bank_format': bank_format,
            'company_account': company_account or False,
            'attachment_id': attachment.id,
            'filename': result['filename'],
            'file_hash': result['file_hash'],
            'byte_size': result['byte_size'],
            'control_total': result['total_amount'],
            'row_count': result['valid'],
            'excluded_json': json.dumps(result['excluded']),
            'excluded_count': len(result['excluded']),
            'generated_by': self.env.uid,
            'generated_at': fields.Datetime.now(),
        })
        attachment.write({'res_id': record.id})
        record._supersede_earlier()
        return record

    def _supersede_earlier(self):
        """The previous try for this run is no longer the file to pay from.

        Its open request is withdrawn in the same breath: leaving it in
        somebody's queue would be asking them to sign off a file that has been
        replaced.
        """
        self.ensure_one()
        earlier = self.sudo().search([
            ('run_id', '=', self.run_id.id), ('id', '!=', self.id),
            ('state', 'not in', ('superseded', 'rejected')),
        ])
        engine = self.env['biz.approval.engine']
        for old in earlier:
            request = old.approval_request_id
            if request and request.state in ('pending', 'blocked'):
                try:
                    engine.sudo().cancel(
                        request, _("A newer bank file replaced this one."))
                except Exception:   # noqa: BLE001 — never stop the new file
                    _logger.warning('pb_pay_delivery: could not withdraw the '
                                    'request on bank file %s', old.id)
            old.write({'state': 'superseded', 'superseded_by_id': self.id,
                       'approved_hash': False})
        return True

    # ==================================================================
    # Adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state in ('pending', 'approved'):
            raise UserError(_("This bank file has already been sent in."))
        if self.state == 'superseded':
            raise UserError(_(
                "A newer bank file has replaced this one. Send that one in "
                "instead."))
        if not self.attachment_id:
            raise UserError(_("There is no file to approve."))
        return True

    def _live_hash(self):
        """The stamp of the bytes as they are RIGHT NOW.

        Read from the attachment every time and never from `file_hash`: a
        stamp read back off the thing it stamped always equals itself and the
        whole rail would be decoration (ledger AM46).
        """
        self.ensure_one()
        attachment = self.attachment_id.sudo()
        return sha256_of(attachment.raw or b'') if attachment else ''

    def _control_total_matches_run(self):
        """Does the file add up to what the run pays?"""
        self.ensure_one()
        slips = self.run_id.sudo().slip_ids.filtered(
            lambda s: s.state == 'done')
        Wizard = self.env['vietnam.bank.export.wizard']
        total = sum(Wizard._slip_net(slip) for slip in slips)
        difference = abs(float(total) - float(self.control_total or 0.0))
        return difference < 0.01, total

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        run = self.run_id
        scope_keys, scope_label = self.scope_of_run(run)
        first = not bool(self.sudo().search_count([
            ('run_id', '=', run.id), ('id', '!=', self.id),
            ('state', '=', 'approved')]))
        matches, run_total = self._control_total_matches_run()
        facts = {
            'control_total': {'value': float(self.control_total or 0.0),
                              'unit': currency.name or ''},
            'row_count': {'value': self.row_count, 'unit': ''},
            'excluded_count': {'value': self.excluded_count, 'unit': ''},
            'run_approved': {'value': self.run_is_approved(run), 'unit': ''},
            'first_file_for_run': {'value': first, 'unit': ''},
        }
        makers = set(self.run_makers(run))
        if self.generated_by:
            makers.add(self.generated_by.id)
        return {
            'company_id': company.id,
            'title': self.name or _('Bank file'),
            'scope_keys': scope_keys,
            'scope_label': scope_label,
            'kind_key': self.bank_format or 'any',
            'facts': facts,
            'amount': float(self.control_total or 0.0),
            'currency_id': currency.id,
            'maker_uids': sorted(u for u in makers if u),
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._live_hash(),
            'evidence': [
                {'key': 'run_approved', 'name': _('The pay run is approved'),
                 'ok': self.run_is_approved(run), 'note': run.name or ''},
                {'key': 'control_total_matches_run',
                 'name': _('The total matches the pay run'),
                 'ok': matches,
                 'note': ('' if matches else _(
                     "The pay run pays %(run)s and the file carries %(file)s.",
                     run='{:,.0f}'.format(run_total),
                     file='{:,.0f}'.format(self.control_total or 0.0)))},
            ],
        }

    @api.model
    def _approval_capabilities(self):
        layouts = self.env['pb.bank.file.layout'].sudo().search([])
        return {
            'facts': {
                'control_total': {'type': 'decimal',
                                  'label': _('Control total'),
                                  'unit': 'currency'},
                'row_count': {'type': 'int', 'label': _('Rows in the file')},
                'excluded_count': {'type': 'int',
                                   'label': _('People left out')},
                'run_approved': {'type': 'bool',
                                 'label': _('The pay run is approved')},
                'first_file_for_run': {
                    'type': 'bool',
                    'label': _('The first file for this pay run')},
            },
            'kinds': [{'key': layout.bank_format, 'label': layout.name or ''}
                      for layout in layouts],
            'evidence': [
                {'key': 'run_approved', 'label': _('The pay run is approved')},
                {'key': 'control_total_matches_run',
                 'label': _('The total matches the pay run')},
            ],
            'scope_levels': [_('Pay scheme'), _('Division')],
            'manager_mode': False,
        }

    @api.model
    def _approval_scope_options(self, company):
        Run = self.env.get('hr.payslip.run')
        if Run is None or not hasattr(Run, '_approval_scope_options'):
            return []
        return Run._approval_scope_options(company)

    @api.model
    def _approval_coverage_scopes(self, company):
        Run = self.env.get('hr.payslip.run')
        if Run is None or not hasattr(Run, '_approval_coverage_scopes'):
            return [{'scope_key': '', 'scope_keys': [''],
                     'label': company.name, 'headcount': 0,
                     'kind_key': 'any', 'facts': {}}]
        rows = Run._approval_coverage_scopes(company)
        # the pay run's own kinds are cycle types; a bank file's kind is a bank
        for row in rows:
            row['kind_key'] = 'any'
        return rows

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.row_count == 1:
            return _("1 payment")
        return _("%s payments", self.row_count)

    def _approval_detail(self, request):
        """Who is NOT in this file, and why — the question an approver asks."""
        self.ensure_one()
        rows = []
        for row in self.excluded()[:40]:
            if not isinstance(row, dict):
                continue
            rows.append({
                'head': str(row.get('employee') or '')[:40],
                'sub': '',
                'cells': [' · '.join(row.get('reasons') or [])[:80]],
                'tone': 'off',
            })
        chips = [
            {'label': _('Bank'), 'value': (self.bank_format or '').title()},
            {'label': _('File'), 'value': self.filename or ''},
        ]
        if not rows:
            return {
                'title': _('Everybody in this pay run is in the file'),
                'columns': [], 'rows': [], 'chips': chips, 'note': ''}
        return {
            'title': _('Left out of the file'),
            'columns': [_('Why')],
            'rows': rows,
            'chips': chips,
            'note': _("These people are not paid by this file. Fix their bank "
                      "details and prepare it again if they should be."),
        }

    # ------------------------------------------------------- the transitions
    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending'})
        return True

    def _approval_return(self, request, reason):
        """Sent back: this file is not the one to pay from any more."""
        self.ensure_one()
        self.sudo().write({'state': 'returned', 'approved_hash': False})
        return True

    def _approval_apply(self, request):
        """Approved: THIS set of bytes, and nothing else, may be downloaded."""
        self.ensure_one()
        if self.state == 'approved' and self.approved_hash:
            return True
        self.require_pay(_('the bank file'))
        live = self._live_hash()
        if not live:
            raise UserError(_("The file is missing, so it cannot be approved."))
        if self.file_hash and live != self.file_hash:
            raise UserError(_(
                "The file changed after it was sent in, so this approval no "
                "longer covers it. Prepare it again."))
        self.sudo().write({'state': 'approved', 'approved_hash': live})
        self.env['biz.approval.event']._log(
            'applied',
            _("%(who)s approved the bank file %(name)s (%(rows)s payments)",
              who=self.env.user.name, name=self.filename or '',
              rows=self.row_count),
            company=self.company_id, request=request)
        self.audit(self, 'state', _('Bank file'), _('Waiting for approval'),
                   _('Approved'))
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'rejected', 'approved_hash': False})
        return True

    # ==================================================================
    # Downloading
    # ==================================================================
    def action_download(self):
        """The one door out. Refuses anything but the approved bytes."""
        self.ensure_one()
        self.require_pay(_('the bank file'))
        if self.state != 'approved' or not self.approved_hash:
            raise UserError(_(
                "This file has not been approved yet, so it cannot be "
                "downloaded. It is with %s.",
                self._waiting_for() or _('its approver')))
        live = self._live_hash()
        if live != self.approved_hash:
            raise UserError(_(
                "This is not the approved file — what is stored no longer "
                "matches what was signed off. Prepare it again."))
        attachment = self.attachment_id.sudo()
        if not attachment.access_token:
            attachment.generate_access_token()
        self.sudo().write({'downloaded_at': fields.Datetime.now(),
                           'downloaded_by': self.env.uid})
        self.audit(self, 'downloaded_at', _('Bank file downloaded'), '',
                   self.env.user.name)
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true&access_token=%s' % (
                attachment.id, attachment.access_token),
            'target': 'self',
        }
