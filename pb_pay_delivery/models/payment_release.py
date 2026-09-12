# -*- coding: utf-8 -*-
"""Letting the bank actually move the money — and the moment pay becomes paid.

THE GAP THIS CLOSES. Approving a pay run said the numbers were right.
Approving a bank file said the file was right. Neither of them said anybody had
agreed to send it. And afterwards nothing in the app knew a run had been paid:
"paid" existed only as a fulfilment word on an award, written when the run was
approved — which is not when the money left.

A RELEASE names the approved file it releases, the amount, and the reference
the bank gave back. When it is approved, every confirmed payslip in that run is
stamped `pb_paid_on` / `pb_paid_ref`, the awards queued into the run are marked
paid, and the run's own card can finally say Paid.

TWO SIGNATURES BY DEFAULT. The engine's "any one of a pool" closes on the first
person to answer, so a pool cannot express "two of the five". The default route
is therefore a JOINT step over two named responsibilities — Finance approver
and Country director — which is two real signatures. A pool of N where any M
must sign is a capability the engine does not have yet (ledger).
"""

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#: The catalogue key this model is approved under.
RELEASE_PROCESS_KEY = 'release'

STATES = [
    ('draft', 'Being prepared'),
    ('pending', 'Waiting for approval'),
    ('released', 'Money released'),
    ('returned', 'Sent back'),
    ('rejected', 'Turned down'),
]


class PbPaymentRelease(models.Model):
    _name = 'pb.payment.release'
    _inherit = ['biz.approval.adapter.mixin', 'pb.money.approval.mixin']
    _description = 'Payment Release'
    _order = 'id desc'

    _approval_process_key = RELEASE_PROCESS_KEY

    name = fields.Char(compute='_compute_name', store=True)
    bank_file_id = fields.Many2one('pb.bank.file', string='Bank file',
                                   required=True, index=True,
                                   ondelete='cascade')
    run_id = fields.Many2one('hr.payslip.run', string='Pay run',
                             related='bank_file_id.run_id', store=True,
                             index=True)
    company_id = fields.Many2one('res.company', required=True, index=True,
                                 default=lambda s: s.env.company)
    currency_id = fields.Many2one('res.currency', string='Currency')
    amount = fields.Monetary(string='Amount', readonly=True,
                             currency_field='currency_id')
    beneficiaries = fields.Integer(string='People paid', readonly=True)

    bank_reference = fields.Char(
        string='Bank reference',
        help="What the bank called this transfer. Recorded with the release "
             "so the money can be traced back to it.")
    evidence_attachment_id = fields.Many2one(
        'ir.attachment', string='Bank confirmation', ondelete='set null',
        help="Optional: what the bank sent back.")
    released_on = fields.Datetime(readonly=True, copy=False)
    released_by = fields.Many2one('res.users', readonly=True, copy=False)

    state = fields.Selection(STATES, default='draft', required=True,
                             index=True, readonly=True, copy=False)

    seat_user_ids = fields.Many2many(
        'res.users', 'pb_payment_release_seat_rel', 'release_id', 'user_id',
        string='Asked to decide', copy=False)

    @api.depends('run_id', 'amount')
    def _compute_name(self):
        for rec in self:
            rec.name = _("Payment release · %s", rec.run_id.name or '')

    # ==================================================================
    # Preparing one
    # ==================================================================
    @api.model
    def prepare(self, bank_file, bank_reference=None):
        """Ask for the money behind an APPROVED file to be sent."""
        bank_file = bank_file if isinstance(bank_file, models.BaseModel) \
            else self.env['pb.bank.file'].browse(int(bank_file))
        if not bank_file.exists():
            raise UserError(_("That bank file no longer exists."))
        self.require_pay()
        if bank_file.state != 'approved':
            raise UserError(_(
                "The bank file has not been approved yet, so the money cannot "
                "be released. It is with %s.",
                bank_file._waiting_for() or _('its approver')))
        existing = self.sudo().search([
            ('bank_file_id', '=', bank_file.id),
            ('state', 'in', ('pending', 'released'))], limit=1)
        if existing and existing.state == 'pending':
            raise UserError(_(
                "This file has already been sent for release, and is with %s.",
                existing._waiting_for() or _('its approver')))
        if existing:
            raise UserError(_("This file has already been released."))
        company = bank_file.company_id or self.env.company
        return self.create({
            'bank_file_id': bank_file.id,
            'company_id': company.id,
            'currency_id': (bank_file.currency_id or company.currency_id).id,
            'amount': bank_file.control_total,
            'beneficiaries': bank_file.row_count,
            'bank_reference': (bank_reference or '')[:64] or False,
        })

    # ==================================================================
    # Adapter
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if self.state in ('pending', 'released'):
            raise UserError(_("This release has already been sent in."))
        if self.bank_file_id.state != 'approved':
            raise UserError(_(
                "The bank file behind this release is no longer approved, so "
                "the money cannot be sent."))
        return True

    def _file_signatories(self):
        """Everybody who signed the bank file off."""
        self.ensure_one()
        request = self.bank_file_id.approval_request_id
        if not request:
            return []
        decisions = request.sudo().decision_ids.filtered(
            lambda d: d.action == 'approve')
        return sorted({d.user_id.id for d in decisions if d.user_id})

    def _approval_context(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        currency = self.currency_id or company.currency_id
        run = self.run_id
        scope_keys, scope_label = self.scope_of_run(run)
        signatories = self._file_signatories()
        facts = {
            'amount': {'value': float(self.amount or 0.0),
                       'unit': currency.name or ''},
            'beneficiaries': {'value': self.beneficiaries, 'unit': ''},
            'bank_file_approved': {
                'value': self.bank_file_id.state == 'approved', 'unit': ''},
            # The route may ask for a different pair of eyes than the file got.
            'same_signatory_as_file': {'value': bool(signatories), 'unit': ''},
        }
        makers = set(self.run_makers(run))
        if self.bank_file_id.generated_by:
            makers.add(self.bank_file_id.generated_by.id)
        return {
            'company_id': company.id,
            'title': self.name or _('Payment release'),
            'scope_keys': scope_keys,
            'scope_label': scope_label,
            'kind_key': 'any',
            'facts': facts,
            'amount': float(self.amount or 0.0),
            'currency_id': currency.id,
            'maker_uids': sorted(u for u in makers if u),
            'submitter_uid': self.env.uid,
            'subject_uids': [],
            'source_revision': self._approval_revision_of([
                self.bank_file_id.approved_hash or '',
                round(float(self.amount or 0.0), 2), self.beneficiaries]),
            'evidence': [
                {'key': 'bank_file_approved',
                 'name': _('The bank file is approved'),
                 'ok': self.bank_file_id.state == 'approved',
                 'note': self.bank_file_id.filename or ''},
                {'key': 'bank_confirmation',
                 'name': _('The bank confirmation'),
                 'ok': bool(self.evidence_attachment_id),
                 'note': self.evidence_attachment_id.name or ''},
            ],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'amount': {'type': 'decimal', 'label': _('Amount'),
                           'unit': 'currency'},
                'beneficiaries': {'type': 'int', 'label': _('People paid')},
                'bank_file_approved': {
                    'type': 'bool', 'label': _('The bank file is approved')},
                'same_signatory_as_file': {
                    'type': 'bool',
                    'label': _('Somebody already signed the file off')},
            },
            'kinds': [],
            'evidence': [
                {'key': 'bank_file_approved',
                 'label': _('The bank file is approved')},
                {'key': 'bank_confirmation',
                 'label': _('The bank confirmation')},
            ],
            'scope_levels': [_('Pay scheme'), _('Division')],
            'manager_mode': False,
        }

    @api.model
    def _approval_scope_options(self, company):
        return self.env['pb.bank.file']._approval_scope_options(company)

    @api.model
    def _approval_coverage_scopes(self, company):
        return self.env['pb.bank.file']._approval_coverage_scopes(company)

    def _approval_card_count(self, request):
        self.ensure_one()
        if self.beneficiaries == 1:
            return _("1 person")
        return _("%s people", self.beneficiaries)

    def _approval_detail(self, request):
        self.ensure_one()
        chips = [
            {'label': _('Bank file'), 'value': self.bank_file_id.filename or ''},
            {'label': _('Pay run'), 'value': self.run_id.name or ''},
        ]
        if self.bank_reference:
            chips.append({'label': _('Bank reference'),
                          'value': self.bank_reference})
        names = self.env['res.users'].sudo().browse(
            self._file_signatories()).mapped('name')
        return {
            'title': _('What is being released'),
            'columns': [],
            'rows': [],
            'chips': chips,
            'note': (_("The bank file was signed off by %s.", ', '.join(names))
                     if names else ''),
        }

    # ------------------------------------------------------- the transitions
    def _approval_freeze(self, request):
        self.ensure_one()
        self.sudo().write({'state': 'pending'})
        return True

    def _approval_return(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'returned'})
        return True

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'state': 'rejected'})
        return True

    def _approval_apply(self, request):
        """The money is gone. Stamp everything that has to know.

        Idempotent: a release already `released` does nothing a second time,
        and the payslip stamp is only written where it is empty.
        """
        self.ensure_one()
        if self.state == 'released':
            return True
        self.require_pay(_('the payment release'))
        if self.bank_file_id.state != 'approved':
            raise UserError(_(
                "The bank file behind this release is no longer the approved "
                "one, so the money cannot be marked as sent."))
        stamp = fields.Datetime.now()
        reference = (self.bank_reference or '')[:64]
        slips = self.run_id.sudo().slip_ids.filtered(
            lambda s: s.state == 'done' and not s.pb_paid_on)
        if slips:
            slips.write({'pb_paid_on': stamp, 'pb_paid_ref': reference or False})
        # The awards queued into this run are paid when the money is paid, and
        # not a moment earlier. Soft: the awards module sits ABOVE this one.
        Feed = self.env.get('pb.oneoff.feed')
        if Feed is not None:
            try:
                Feed.mark_paid_for_run(self.run_id.id)
            except Exception:       # noqa: BLE001 — never half-release
                _logger.exception(
                    'pb_pay_delivery: could not mark awards paid for run %s',
                    self.run_id.id)
        self.sudo().write({'state': 'released', 'released_on': stamp,
                           'released_by': self.env.uid})
        self.env['biz.approval.event']._log(
            'applied',
            _("%(who)s released %(amount)s to %(n)s people%(ref)s",
              who=self.env.user.name,
              amount='{:,.0f}'.format(float(self.amount or 0.0)),
              n=self.beneficiaries,
              ref=(_(" · reference %s", reference) if reference else '')),
            company=self.company_id, request=request)
        self.audit(self, 'released_on', _('Payment released'), '',
                   '%s · %s' % ('{:,.0f}'.format(float(self.amount or 0.0)),
                                reference or _('no reference')))
        return True


class HrPayslipPaid(models.Model):
    """When this payslip's money actually left the company.

    Written only by an approved payment release. Deliberately NOT a state: a
    payslip's state is about payroll, and `done` already means "confirmed".
    Paid is about the bank.
    """
    _inherit = 'hr.payslip'

    pb_paid_on = fields.Datetime(string='Paid on', readonly=True, copy=False,
                                 index=True)
    pb_paid_ref = fields.Char(string='Bank reference', readonly=True,
                              copy=False)
    pb_paid = fields.Boolean(string='Paid', compute='_compute_pb_paid',
                             store=True)

    @api.depends('pb_paid_on')
    def _compute_pb_paid(self):
        for slip in self:
            slip.pb_paid = bool(slip.pb_paid_on)


class HrPayslipRunPaid(models.Model):
    """The run's own answer to "has this been paid?"."""
    _inherit = 'hr.payslip.run'

    pb_paid = fields.Boolean(string='Paid', compute='_compute_pb_paid')
    pb_paid_on = fields.Datetime(string='Paid on', compute='_compute_pb_paid')

    @api.depends('slip_ids.pb_paid_on')
    def _compute_pb_paid(self):
        for run in self:
            slips = run.slip_ids.filtered(lambda s: s.state == 'done')
            stamps = [s.pb_paid_on for s in slips if s.pb_paid_on]
            run.pb_paid = bool(slips) and len(stamps) == len(slips)
            run.pb_paid_on = max(stamps) if stamps else False
