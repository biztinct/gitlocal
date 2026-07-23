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
    _description = 'Payslip Delivery Batch'
    _order = 'create_date desc'

    name = fields.Char(default=lambda self: _('Delivery'), required=True)
    run_id = fields.Many2one('hr.payslip.run', string='Pay Run',
                             required=True, ondelete='cascade', index=True)
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, index=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('sending', 'Sending'), ('done', 'Done')],
        default='draft', required=True)
    line_ids = fields.One2many(
        'pb.payslip.delivery', 'batch_id', string='Deliveries')
    sent_count = fields.Integer(compute='_compute_counts', store=True)
    failed_count = fields.Integer(compute='_compute_counts', store=True)
    skipped_count = fields.Integer(compute='_compute_counts', store=True)

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
        """Send/queue payslips for every Done slip of the run.

        Idempotent: an already-'sent' line is skipped unless force_all. Per-slip
        savepoint isolates failures. Returns the refreshed cockpit payload."""
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
