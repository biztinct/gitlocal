# -*- coding: utf-8 -*-
"""Batch payslip delivery — themed, password-protected PDFs, per-slip log.

Renders the themed payslip PDF (write-free), encrypts it with a per-employee
password resolved IN MEMORY (never logged, never stored — safety rail 4 /
C18.42c), attaches it to a mail template and queues it to ``mail.mail``
(force_send=False; the mail cron sends). One savepoint per slip so a single bad
payslip never kills the batch; delivery is idempotent (a 'sent' line is never
re-sent unless force_all); slips with no work_email are surfaced as
'skipped_no_email', never silently dropped.
"""

import base64
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

_THEMED_REPORT = 'pb_hr_payroll_formula.action_report_payslip_themed'
_STANDARD_REPORT = 'om_hr_payroll.action_report_payslip'
_PWD_PARAM = 'pb_pay_delivery.pdf_password_pattern'
_PWD_DEFAULT = '{account_last4}{birth_year}'

# Same access gate as the bank-file lane (safety rail 3).
_PAY_GROUPS = ('om_hr_payroll.group_hr_payroll_manager',
               'account.group_account_invoice', 'account.group_account_user')

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:  # pragma: no cover - live venv ships PyPDF2 2.12.1
    PdfReader = PdfWriter = None


class PbPayslipDeliveryBatch(models.Model):
    _name = 'pb.payslip.delivery.batch'
    _inherit = ['biz.approval.adapter.mixin', 'pb.money.approval.mixin']
    _description = 'Payslip Delivery Batch'
    _order = 'create_date desc'

    #: The catalogue key this model is approved under. The default route is
    #: the fast lane — a payslip is the employee's own document and most
    #: businesses do not check it twice — but it IS a route, so a business
    #: that wants somebody to look first can say so without a code change.
    _approval_process_key = 'payslips'

    name = fields.Char(default=lambda self: _('Delivery'), required=True)
    run_id = fields.Many2one('hr.payslip.run', string='Pay Run',
                             required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('pending', 'Waiting for approval'),
         ('returned', 'Sent back'), ('rejected', 'Turned down'),
         ('sending', 'Sending'), ('done', 'Done')],
        default='draft', required=True)
    force_all = fields.Boolean(
        string='Send to everybody again', copy=False,
        help="What the person asked for when this was sent in. Kept on the "
             "record so an approval carries out the send that was requested, "
             "not a different one.")
    line_ids = fields.One2many(
        'pb.payslip.delivery', 'batch_id', string='Deliveries')
    sent_count = fields.Integer(compute='_compute_counts', store=True)
    failed_count = fields.Integer(compute='_compute_counts', store=True)
    skipped_count = fields.Integer(compute='_compute_counts', store=True)
    #: A seat is also a read (ledger AM60).
    seat_user_ids = fields.Many2many(
        'res.users', 'pb_delivery_batch_seat_rel', 'batch_id', 'user_id',
        string='Asked to decide', copy=False)

    @api.depends('line_ids.state')
    def _compute_counts(self):
        for b in self:
            b.sent_count = len(b.line_ids.filtered(lambda l: l.state == 'sent'))
            b.failed_count = len(b.line_ids.filtered(lambda l: l.state == 'failed'))
            b.skipped_count = len(
                b.line_ids.filtered(lambda l: l.state == 'skipped_no_email'))

    # ------------------------------------------------------------- access
    def _check_pay_access(self):
        user = self.env.user
        if user._is_admin():
            return
        for g in _PAY_GROUPS:
            try:
                if user.has_group(g):
                    return
            except (ValueError, KeyError):
                continue
        raise AccessError(_(
            "You are not allowed to send payslips. This requires the Payroll "
            "Manager or a Finance role."))

    # ------------------------------------------------------------- password
    def _password_pattern(self):
        return (self.env['ir.config_parameter'].sudo().get_param(
            _PWD_PARAM) or _PWD_DEFAULT)

    def _resolve_password(self, employee):
        """Resolve the PDF password for one employee IN MEMORY.

        Placeholders: {account_last4} {birth_year} {employee_code}. The result
        is never logged, never stored on any delivery row, never returned by an
        RPC (safety rail 4)."""
        acct = ''.join(ch for ch in (employee.vietnam_bank_account_number or '')
                       if ch.isdigit())
        birth_year = str(employee.birthday.year) if employee.birthday else ''
        code = employee.barcode or employee.identification_id or ''
        pwd = self._password_pattern()
        pwd = pwd.replace('{account_last4}', acct[-4:] if len(acct) >= 4 else acct)
        pwd = pwd.replace('{birth_year}', birth_year)
        pwd = pwd.replace('{employee_code}', code)
        # Never a static fallback: an underivable password means the slip FAILS
        # (surfaced in the drawer) rather than shipping a guessably-protected PDF.
        return pwd or acct[-4:] or code

    # ------------------------------------------------------------- pdf
    def _report_ref(self):
        """The payslip report to render — prefer the themed report, fall back to
        the standard one if the themed render helper isn't deployed on this
        server (the themed report is a pb_hr_payroll_formula feature that can lag
        the repo — a deploy-drift guard, surfaced not silent)."""
        Payslip = self.env['hr.payslip']
        if hasattr(Payslip, '_themed_payslip_render') and self.env.ref(
                _THEMED_REPORT, raise_if_not_found=False):
            return _THEMED_REPORT
        _logger.info("pb_pay_delivery: themed payslip report unavailable on this "
                     "server — rendering the standard payslip PDF.")
        return _STANDARD_REPORT

    def _render_pdf(self, slip):
        """Payslip PDF bytes (write-free render, C17)."""
        pdf, _dummy = self.env['ir.actions.report']._render_qweb_pdf(
            self._report_ref(), res_ids=slip.ids)
        return pdf

    def _encrypt_pdf(self, pdf_bytes, password):
        if PdfWriter is None:
            raise UserError(_(
                "PDF encryption is unavailable on this server (PyPDF2 not "
                "installed) — payslips are never sent unprotected."))
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt(password, use_128bit=True)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    def _mail_template(self):
        tmpl = self.env.ref('pb_pay_delivery.mail_template_payslip_delivery',
                            raise_if_not_found=False)
        if not tmpl:
            raise UserError(_("The payslip delivery mail template is missing."))
        return tmpl

    # ------------------------------------------------------------- send
    def action_send(self, force_all=False):
        """Ask for the send-out, then let the answer carry it out.

        The default route for "Payslip send-out" is the fast lane, so the
        usual press still sends immediately — and now writes a request saying
        so. A business that publishes a real route gets the batch waiting
        instead, and the send happens from `_approval_apply`.

        Resending failures after an approved send is NOT a new send-out: the
        same people are getting the same document, and the ones that failed
        never left the building. That path goes straight through.
        """
        self.ensure_one()
        self._check_pay_access()
        request = self.approval_request_id
        if request and request.state == 'applied' and not force_all:
            return self._do_send(force_all=False)
        if self.state == 'pending':
            raise UserError(_(
                "These payslips are already waiting to be approved, with %s.",
                self._waiting_for() or _('their approver')))
        self.write({'force_all': bool(force_all)})
        self.env['biz.approval.engine'].submit(self)
        return True

    def _do_send(self, force_all=False):
        """Send/queue payslips for every Done slip of the run.

        Idempotent: an already-'sent' line is skipped unless force_all. Per-slip
        savepoint isolates failures."""
        self.ensure_one()
        self._check_pay_access()

        slips = self.run_id.slip_ids
        if slips and any(s.state != 'done' for s in slips):
            # done-only: never deliver drafts (safety rail 5)
            slips = slips.filtered(lambda s: s.state == 'done')
        if not slips:
            raise UserError(_(
                "No confirmed (Done) payslips in this pay run to deliver."))

        template = self._mail_template()
        self.state = 'sending'
        Line = self.env['pb.payslip.delivery']

        for slip in slips:
            line = self.line_ids.filtered(lambda l: l.slip_id == slip)[:1]
            if line and line.state == 'sent' and not force_all:
                continue  # idempotent: never double-send

            emp = slip.employee_id
            email = emp.work_email
            if not line:
                line = Line.create({
                    'batch_id': self.id, 'slip_id': slip.id,
                    'employee_id': emp.id, 'email': email or ''})

            if not email:
                line.write({'state': 'skipped_no_email',
                            'error': _('No work email on the employee record.'),
                            'mail_id': False})
                continue

            password = self._resolve_password(emp)  # in memory only
            if not password:
                line.write({'state': 'failed', 'mail_id': False, 'error': _(
                    'Cannot derive a PDF password for this employee '
                    '(no bank account, birthday or employee code on file).')})
                continue

            # One savepoint per slip — a single bad payslip never kills the run.
            try:
                with self.env.cr.savepoint():
                    pdf = self._render_pdf(slip)
                    enc = self._encrypt_pdf(pdf, password)
                    attachment = self.env['ir.attachment'].create({
                        'name': '%s.pdf' % (slip.number or slip.name or 'payslip'),
                        'type': 'binary',
                        'datas': base64.b64encode(enc),
                        'res_model': 'hr.payslip',
                        'res_id': slip.id,
                        'mimetype': 'application/pdf',
                    })
                    mail_id = template.send_mail(
                        slip.id, force_send=False,
                        email_values={'attachment_ids': [(6, 0, [attachment.id])]})
                    line.write({'state': 'sent', 'email': email,
                                'error': False, 'mail_id': mail_id})
            except (UserError, AccessError):
                raise
            except Exception as e:
                _logger.warning("pb_pay_delivery: send failed for %s: %s",
                                emp.name, e)
                line.write({'state': 'failed', 'error': str(e), 'mail_id': False})

        self.state = 'done'
        return True

    def action_resend_failures(self):
        """Resend only failed lines (idempotent over 'sent')."""
        self.ensure_one()
        return self.action_send(force_all=False)

    # ==================================================================
    # Adapter — what an approval of a send-out is about
    # ==================================================================
    def _approval_validate(self):
        self.ensure_one()
        if not self.run_id.slip_ids.filtered(lambda s: s.state == 'done'):
            raise UserError(_(
                "No confirmed payslips in this pay run to deliver."))
        return True

    def _approval_context(self):
        self.ensure_one()
        run = self.run_id
        company = self.company_id or self.env.company
        scope_keys, scope_label = self.scope_of_run(run)
        slips = run.sudo().slip_ids.filtered(lambda s: s.state == 'done')
        paid = bool(slips) and all(
            getattr(slip, 'pb_paid_on', False) for slip in slips)
        return {
            'company_id': company.id,
            'title': _("Payslips · %s", run.name or ''),
            'scope_keys': scope_keys,
            'scope_label': scope_label,
            'kind_key': 'any',
            'facts': {
                'slip_count': {'value': len(slips), 'unit': ''},
                'run_paid': {'value': paid, 'unit': ''},
            },
            'amount': 0.0,
            'currency_id': company.currency_id.id,
            'maker_uids': self.run_makers(run),
            'submitter_uid': self.env.uid,
            'subject_uids': sorted(
                set(slips.mapped('employee_id.user_id').ids)),
            'source_revision': self._approval_revision_of(
                sorted(slips.ids) + [bool(self.force_all)]),
            'evidence': [
                {'key': 'run_paid', 'name': _('The money has been sent'),
                 'ok': paid, 'note': ''},
            ],
        }

    @api.model
    def _approval_capabilities(self):
        return {
            'facts': {
                'slip_count': {'type': 'int', 'label': _('Payslips')},
                'run_paid': {'type': 'bool',
                             'label': _('The money has been sent')},
            },
            'kinds': [],
            'evidence': [{'key': 'run_paid',
                          'label': _('The money has been sent')}],
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
        count = len(self.run_id.slip_ids.filtered(lambda s: s.state == 'done'))
        if count == 1:
            return _("1 payslip")
        return _("%s payslips", count)

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
        self.ensure_one()
        self.require_pay(_('the payslip send-out'))
        self._do_send(force_all=bool(self.force_all))
        self.audit(self, 'state', _('Payslips sent'), '',
                   _("%(sent)s sent, %(failed)s failed",
                     sent=self.sent_count, failed=self.failed_count))
        return True


class PbPayslipDelivery(models.Model):
    _name = 'pb.payslip.delivery'
    _description = 'Payslip Delivery Line'
    _order = 'id'

    batch_id = fields.Many2one('pb.payslip.delivery.batch', required=True,
                               ondelete='cascade', index=True)
    slip_id = fields.Many2one('hr.payslip', string='Payslip',
                              required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee')
    email = fields.Char(string='Email')
    state = fields.Selection(
        [('sent', 'Sent'), ('failed', 'Failed'),
         ('skipped_no_email', 'Skipped (no email)')],
        required=True, default='failed')
    error = fields.Char(string='Error')
    # NOTE: the resolved PDF password is NEVER stored here (safety rail 4).
    mail_id = fields.Many2one('mail.mail', string='Queued Mail',
                              ondelete='set null')
