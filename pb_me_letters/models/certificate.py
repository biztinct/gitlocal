# -*- coding: utf-8 -*-
"""A certificate an employee asks for on My Payobook (owner ruling E2).

EMPLOYMENT: no pay figures, so it is issued at once — the letter engine
prints it, files it in the person's documents and the person downloads it.

SALARY: shows the agreed monthly salary, so it waits for one HR click (the
`me_certificate` route, default "HR lead", in the one Approvals inbox). The
click issues it; the person sees "ready" on their home page.

THE LETTER ENGINE IS INHERITED, NEVER EDITED (pb_lifecycle). This module
creates an ordinary `pb.hr.letter` and calls its `action_generate()` —
which fills the placeholders, renders the PDF (`_make_pdf`) and files it
(`_file_in_vault`) — at the moment of issue only, so nothing reaches the
person's documents before HR said yes. The letter is never "sent": the
person downloads it, and no email leaves (tenant email is off on three
databases, and the work address is not always the person's).

THE FIGURES ARE THE SERVER'S. The salary is the running contract's agreed
wage in its own currency; the employee only picks a purpose and a language.
A person on pay hold, or with no running contract, gets a plain refusal.
"""

import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date, formatLang

from .letter_template import EMPLOYMENT, SALARY

_logger = logging.getLogger(__name__)

KINDS = [('employment', 'Employment certificate'),
         ('salary', 'Salary certificate')]
PURPOSES = [('bank', 'A bank or a loan'),
            ('visa', 'A visa or travel'),
            ('rental', 'Renting a home'),
            ('other', 'Something else')]
#: The languages a certificate can be printed in, when installed.
LANGS = ('en_US', 'vi_VN', 'id_ID')
#: How long a ready salary certificate stays on "Needs you".
READY_DAYS = 7


class PbMeCertificate(models.Model):
    _name = 'pb.me.certificate'
    _description = 'Certificate asked for on My Payobook'
    _inherit = ['mail.thread', 'biz.approval.chain.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Number', required=True, readonly=True, copy=False,
                       default=lambda self: _('New'), index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  readonly=True, index=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', required=True,
                                 readonly=True, index=True)
    kind = fields.Selection(KINDS, string='Certificate', required=True,
                            readonly=True)
    purpose = fields.Selection(PURPOSES, string='What it is for', required=True,
                               readonly=True, default='other')
    purpose_note = fields.Char(string='Details', readonly=True)
    lang = fields.Char(string='Language', readonly=True)
    state = fields.Selection([
        ('draft', 'Asked'),
        ('hr_review', 'Waiting for HR'),
        ('issued', 'Ready'),
        ('refused', 'Turned down'),
    ], string='Status', default='draft', readonly=True, index=True, copy=False,
        tracking=True)
    letter_id = fields.Many2one('pb.hr.letter', string='Letter', readonly=True,
                                copy=False, ondelete='set null')
    document_id = fields.Many2one('pb.employee.document', string='Filed as',
                                  readonly=True, copy=False, ondelete='set null')
    issued_on = fields.Datetime(string='Issued on', readonly=True, copy=False)
    issued_by = fields.Many2one('res.users', string='Issued by', readonly=True,
                                copy=False)
    decision_note = fields.Text(string='Reason given', readonly=True, copy=False)
    downloaded_on = fields.Datetime(string='First downloaded', readonly=True,
                                    copy=False)

    _approval_transitions = {
        ('draft', 'hr_review'): None,
        ('hr_review', 'issued'): 'hr.group_hr_user',
    }

    # ---------------------------------------------------------------- rules
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_("Certificates are asked for on My Payobook."))
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == _('New'):
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'pb.me.certificate') or _('New')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and not self._chain_write_allowed() \
                and set(vals) - {'message_main_attachment_id'}:
            raise AccessError(_("A certificate cannot be edited here."))
        return super().write(vals)

    # ------------------------------------------------------------ the portal
    @api.model
    def _pb_langs(self):
        installed = dict(self.env['res.lang'].get_installed())
        return [(code, installed[code]) for code in LANGS if code in installed]

    @api.model
    def pb_portal_request(self, employee, kind, purpose, lang=None, note=None):
        """Ask for a certificate for the caller's OWN employee. Employment:
        issued at once. Salary: sent to HR."""
        employee = employee.sudo()
        if not employee or employee.user_id != self.env.user:
            raise AccessError(_("You can only ask for your own certificate."))
        if kind not in dict(KINDS):
            raise UserError(_("Choose which certificate you need."))
        if purpose not in dict(PURPOSES):
            purpose = 'other'
        langs = dict(self._pb_langs())
        if lang not in langs:
            lang = self.env.lang if self.env.lang in langs else 'en_US'
        if kind == 'salary':
            self._pb_check_salary(employee)
            waiting = self.sudo().search_count([
                ('employee_id', '=', employee.id), ('kind', '=', 'salary'),
                ('state', '=', 'hr_review')])
            if waiting:
                raise UserError(_("A salary certificate is already waiting for "
                                  "HR. You will see it here when it is ready."))
        cert = self.sudo().create({
            'employee_id': employee.id,
            'company_id': employee.company_id.id,
            'kind': kind,
            'purpose': purpose,
            'purpose_note': (note or '').strip()[:80] or False,
            'lang': lang,
        })
        if kind == 'employment':
            cert._pb_issue()
        else:
            cert._pb_send()
        return cert

    def _pb_send(self):
        self.ensure_one()
        rec = self.sudo()
        if not rec._engine_managed():
            try:
                with self.env.cr.savepoint():
                    rec._approval_seed_default(rec.company_id)
            except Exception:               # noqa: BLE001 — never block a send
                _logger.warning('pb_me_letters: no route could be laid for %s',
                                rec.company_id.name, exc_info=True)
        rec._advance_state('hr_review')
        rec.invalidate_recordset()
        return rec

    # ----------------------------------------------------------- the figures
    @api.model
    def _pb_running_contract(self, employee):
        today = fields.Date.context_today(self)
        contracts = employee.sudo().contract_ids.filtered(
            lambda c: c.state == 'open'
            and (not c.date_start or c.date_start <= today)
            and (not c.date_end or c.date_end >= today))
        return contracts.sorted(lambda c: c.date_start or fields.Date.today(),
                                reverse=True)[:1]

    @api.model
    def _pb_check_salary(self, employee):
        contract = self._pb_running_contract(employee)
        if not contract or not contract.wage:
            raise UserError(_("A salary certificate needs a running contract "
                              "with a salary on it. Ask HR."))
        Slip = self.env['hr.payslip'].sudo()
        if 'pb_pay_hold' in Slip._fields and Slip.search_count([
                ('employee_id', '=', employee.id), ('pb_pay_hold', '=', True)]):
            raise UserError(_("A salary certificate cannot be issued while your "
                              "pay is on hold. Ask HR."))
        return contract

    def _pb_values(self):
        """The placeholders this certificate adds, in its own language."""
        self.ensure_one()
        env = self.env(context=dict(self.env.context, lang=self.lang or 'en_US'))
        rec = self.with_env(env).sudo()
        purposes = dict(rec._fields['purpose']._description_selection(env))
        purpose = purposes.get(rec.purpose, '')
        if rec.purpose == 'other' and rec.purpose_note:
            purpose = rec.purpose_note
        elif rec.purpose_note:
            purpose = '%s (%s)' % (purpose, rec.purpose_note)
        values = {
            'certificate_no': rec.name,
            'purpose': purpose,
            'date': format_date(env, fields.Date.context_today(rec)),
        }
        joining = env['pb.hr.letter']._joining_date(rec.employee_id)
        values['joining_date'] = format_date(env, joining) if joining else ''
        if rec.kind == 'salary':
            contract = rec._pb_check_salary(rec.employee_id)
            currency = contract.currency_id if 'currency_id' in contract._fields \
                and contract.currency_id else rec.company_id.currency_id
            values['salary'] = formatLang(env, contract.wage,
                                          currency_obj=currency)
        return values

    def _pb_template(self):
        """The company's own active wording for this kind, else ours."""
        self.ensure_one()
        letter_type = SALARY if self.kind == 'salary' else EMPLOYMENT
        Template = self.env['pb.letter.template'].sudo()
        own = Template.search([('letter_type', '=', letter_type),
                               ('company_id', '=', self.company_id.id)],
                              order='sequence, id', limit=1)
        if own:
            return own
        shipped = self.env.ref(
            'pb_me_letters.letter_template_%s' % letter_type,
            raise_if_not_found=False)
        if shipped and shipped.active:
            return shipped.sudo()
        return Template.search([('letter_type', '=', letter_type),
                                ('company_id', '=', False)],
                               order='sequence, id', limit=1)

    def _pb_issue(self):
        """Print, file and log the certificate. Runs as the person who
        issued it (the employee for an employment certificate, HR's approver
        for a salary one) under sudo; `sudo()` keeps the uid."""
        self.ensure_one()
        rec = self.sudo()
        template = rec._pb_template()
        if not template:
            raise UserError(_("No certificate wording is set up yet. Ask HR."))
        values = rec._pb_values()
        letter = self.env['pb.hr.letter'].sudo().with_context(
            lang=rec.lang or 'en_US').create({
                'employee_id': rec.employee_id.id,
                'template_id': template.id,
                'company_id': rec.company_id.id,
                'context_json': json.dumps(values),
            })
        letter.subject = '%s %s' % (template.with_context(
            lang=rec.lang or 'en_US').subject or template.name, rec.name)
        letter.with_context(lang=rec.lang or 'en_US').action_generate()
        if not letter.attachment_id:
            raise UserError(_("The certificate could not be printed. Try again "
                              "in a moment."))
        now = fields.Datetime.now()
        rec.write({
            'letter_id': letter.id,
            'document_id': letter.document_id.id or False,
            'issued_on': now,
            'issued_by': self.env.uid,
        })
        if rec.state != 'issued':
            rec._chain_state_write('issued')
        rec.message_post(body=_("Certificate %s issued.", rec.name))
        return letter

    # -------------------------------------------------------- chain hooks
    def _after_approval_transition(self, to_state):
        res = super()._after_approval_transition(to_state)
        if to_state == 'issued':
            for rec in self:
                if not rec.letter_id:
                    rec._pb_issue()
        return res

    def _approval_apply(self, request):
        self.ensure_one()
        return super(PbMeCertificate, self.sudo())._approval_apply(request)

    def _approval_reject(self, request, reason):
        self.ensure_one()
        self.sudo().write({'decision_note': reason or False})
        return super(PbMeCertificate, self.sudo())._approval_reject(request, reason)

    def _approval_return(self, request, reason):
        """Sent back: for a certificate there is nothing to change, so it is
        turned down with the reason, and the person may ask again."""
        self.ensure_one()
        self.sudo().write({'decision_note': reason or False})
        res = super(PbMeCertificate, self.sudo())._approval_return(request, reason)
        rec = self.sudo()
        if rec.state == 'draft':
            rec._chain_state_write('refused')
        return res

    def _approval_withdraw(self, request, reason):
        self.ensure_one()
        rec = self.sudo()
        with self.env.cr.savepoint():
            if rec.state == 'hr_review':
                rec._chain_engine_write('refused')
                rec.write({'decision_note': reason or _("Taken back")})
        return True

    # ----------------------------------------------------- the download
    def pb_portal_pdf(self):
        """`(bytes, filename)` of the issued PDF for the owner's download."""
        self.ensure_one()
        rec = self.sudo()
        if rec.state != 'issued' or not rec.letter_id.attachment_id:
            raise UserError(_("This certificate is not ready yet."))
        att = rec.letter_id.attachment_id.sudo()
        if not rec.downloaded_on:
            rec.write({'downloaded_on': fields.Datetime.now()})
        return att.raw, att.name or '%s.pdf' % rec.name
