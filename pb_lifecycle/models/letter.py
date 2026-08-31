# -*- coding: utf-8 -*-
"""The HR letter engine.

A letter is a BODY WITH NAMED HOLES, and the holes are filled by substitution —
never by evaluation. `string.Template` is used deliberately in place of QWeb or
`safe_eval`: a letter body is written by an HR administrator in a rich-text box,
and the worst thing an administrator can do to a `${...}` placeholder is
misspell it, which leaves the placeholder visible instead of running something.

Every value substituted is HTML-escaped first, so a person whose name contains
an angle bracket produces a letter that reads correctly rather than a letter
with a broken layout.
"""

import base64
import json
import logging
from string import Template

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .lifecycle_common import LETTER_TYPES

_logger = logging.getLogger(__name__)

#: The holes a letter body may contain. Shown to the author in the form help,
#: so the list on screen and the list the engine fills are the same list.
PLACEHOLDERS = [
    ('employee_name', 'The person\'s full name'),
    ('job_title', 'Their job title'),
    ('department', 'Their department'),
    ('company', 'The company name'),
    ('date', 'Today\'s date'),
    ('joining_date', 'The date they joined'),
    ('extra', 'Anything the letter was given when it was created'),
]

PLACEHOLDER_HELP = (
    "Write the letter as you want it read, and put a placeholder where a "
    "detail belongs:\n"
    + "\n".join("  ${%s} — %s" % (k, v) for k, v in PLACEHOLDERS)
    + "\nA placeholder that is not on this list is left on the page exactly as "
      "you typed it, so nothing is ever silently dropped."
)


class PbLetterTemplate(models.Model):
    _name = 'pb.letter.template'
    _description = 'Letter Template'
    _order = 'sequence, name, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    letter_type = fields.Selection(
        LETTER_TYPES, string='Letter type', required=True, default='custom')
    subject = fields.Char(
        string='Subject', translate=True,
        help='The heading printed on the letter and used as the email subject.')
    body_html = fields.Html(
        string='Body', translate=True, sanitize=True,
        help=PLACEHOLDER_HELP)
    vault_category_id = fields.Many2one(
        'pb.employee.document.category', string='File it under',
        help='Where the finished letter is filed in the employee\'s documents.')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.model
    def placeholder_help(self):
        return PLACEHOLDER_HELP


class PbHrLetter(models.Model):
    _name = 'pb.hr.letter'
    _description = 'Employee Letter'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True, string='Reference')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True,
        ondelete='cascade', tracking=True)
    template_id = fields.Many2one(
        'pb.letter.template', string='Letter template', required=True)
    letter_type = fields.Selection(
        LETTER_TYPES, string='Letter type', related='template_id.letter_type',
        store=True, readonly=True)
    case_id = fields.Many2one(
        'pb.journey.case', string='Journey', index=True, ondelete='set null')
    subject = fields.Char(string='Subject')
    rendered_html = fields.Html(string='Letter', sanitize=False, readonly=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('generated', 'Ready'), ('sent', 'Sent')],
        default='draft', tracking=True, string='Status')
    attachment_id = fields.Many2one(
        'ir.attachment', string='PDF', readonly=True, copy=False)
    document_id = fields.Many2one(
        'pb.employee.document', string='Filed as', readonly=True, copy=False,
        ondelete='set null')
    context_json = fields.Text(
        string='Extra details',
        help='Extra placeholder values for this one letter, as JSON.')
    generated_at = fields.Datetime(string='Prepared on', readonly=True)
    generated_by = fields.Many2one('res.users', string='Prepared by',
                                   readonly=True)
    company_id = fields.Many2one(
        'res.company', string='Company', index=True,
        default=lambda self: self.env.company)

    @api.depends('employee_id', 'template_id')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s — %s' % (rec.employee_id.name or _('Employee'),
                                    rec.template_id.name or _('Letter'))

    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id and not self.subject:
            self.subject = self.template_id.subject or self.template_id.name

    # ------------------------------------------------------------ rendering
    def _placeholder_values(self):
        """What each hole is filled with, escaped for HTML."""
        self.ensure_one()
        emp = self.employee_id
        company = self.company_id or emp.company_id or self.env.company
        joining = self._joining_date(emp)
        values = {
            'employee_name': emp.name or '',
            'job_title': emp.job_title or (emp.job_id.name if emp.job_id else '') or '',
            'department': emp.department_id.name if emp.department_id else '',
            'company': company.name or '',
            'date': fields.Date.to_string(fields.Date.context_today(self)),
            'joining_date': fields.Date.to_string(joining) if joining else '',
            'extra': '',
        }
        extra = {}
        if self.context_json:
            try:
                loaded = json.loads(self.context_json)
                if isinstance(loaded, dict):
                    extra = loaded
            except Exception:
                _logger.warning(
                    'pb.hr.letter %s: extra details are not readable JSON',
                    self.id)
        for key, val in extra.items():
            values[str(key)] = '' if val is None else str(val)
        return {k: str(escape(v)) for k, v in values.items()}

    @staticmethod
    def _joining_date(employee):
        d = getattr(employee, 'first_contract_date', False)
        if not d:
            starts = [c.date_start for c in getattr(employee, 'contract_ids', [])
                      if getattr(c, 'date_start', False)]
            d = min(starts) if starts else False
        return d

    def action_generate(self):
        """Fill the holes, render the PDF, attach it, file it in the vault."""
        for rec in self:
            if not rec.template_id.body_html:
                raise UserError(_(
                    "'%s' has no letter body yet, so there is nothing to "
                    "print.", rec.template_id.name))
            body = Template(str(rec.template_id.body_html)).safe_substitute(
                rec._placeholder_values())
            rec.write({
                'rendered_html': Markup(body),
                'subject': rec.subject or rec.template_id.subject
                or rec.template_id.name,
                'state': 'generated',
                'generated_at': fields.Datetime.now(),
                'generated_by': self.env.uid,
            })
            rec._make_pdf()
            rec._file_in_vault()
            rec.message_post(body=_("Letter prepared."))
        return True

    def _make_pdf(self):
        self.ensure_one()
        report = self.env.ref('pb_lifecycle.action_report_hr_letter',
                              raise_if_not_found=False)
        if not report:
            _logger.warning('pb.hr.letter: the letter report is missing')
            return False
        pdf, _ext = report.sudo()._render_qweb_pdf(
            'pb_lifecycle.report_hr_letter_document', res_ids=self.ids)
        filename = '%s.pdf' % (self.subject or self.name or 'Letter').replace(
            '/', '-')
        att = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf),
            'res_model': 'pb.hr.letter',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        old = self.attachment_id
        self.attachment_id = att.id
        if old:
            # The previous PDF is superseded, not history: a letter re-prepared
            # after a correction must not leave the wrong file downloadable.
            old.sudo().unlink()
        return att

    def _file_in_vault(self):
        """Put the finished letter in the person's documents.

        Sudo, and on purpose: filing is a system act on behalf of the company,
        and the person preparing a letter is not necessarily the person the
        vault grants create to. Nothing here writes a verification field, which
        is the vault's one guarded surface.
        """
        self.ensure_one()
        if not self.attachment_id or self.document_id:
            return False
        Doc = self.env['pb.employee.document'].sudo()
        category = self.template_id.vault_category_id or self.env.ref(
            'pb_employee_vault.cat_other', raise_if_not_found=False)
        if not category:
            _logger.info('pb.hr.letter %s: no document category — not filed',
                         self.id)
            return False
        try:
            copy = self.attachment_id.sudo().copy({
                'res_model': 'pb.employee.document', 'res_id': 0})
            doc = Doc.create({
                'employee_id': self.employee_id.id,
                'category_id': category.id,
                'name': self.subject or self.name,
                'attachment_id': copy.id,
                'issue_date': fields.Date.context_today(self),
                'company_id': self.company_id.id or self.env.company.id,
            })
            copy.write({'res_id': doc.id})
            self.document_id = doc.id
            return doc
        except Exception:
            _logger.exception('pb.hr.letter %s: could not file the letter',
                              self.id)
            return False

    def action_send(self):
        """Email the letter with the PDF attached."""
        template = self.env.ref('pb_lifecycle.mail_template_letter_delivery',
                                raise_if_not_found=False)
        if not template:
            raise UserError(_("The letter email is not set up yet."))
        sent = 0
        for rec in self:
            if rec.state == 'draft':
                rec.action_generate()
            to = rec.employee_id.work_email or rec.employee_id.private_email
            if not to:
                rec.message_post(body=_(
                    "No work email on this record, so the letter was not "
                    "sent."))
                continue
            try:
                # `email_to` is passed EXPLICITLY and not left to the template's
                # own rendered field. On this build a template-rendered
                # `email_to` reaches `mail.mail` empty — the message is created,
                # queued and addressed to nobody, with no error anywhere — while
                # the same address handed over in `email_values` lands. Proven
                # side by side on 2026-08-31: the feedback invite (explicit)
                # carried its address, this letter (template) did not.
                values = {'email_to': to}
                if rec.attachment_id:
                    values['attachment_ids'] = [(4, rec.attachment_id.id)]
                template.send_mail(rec.id, force_send=False,
                                   email_values=values)
                rec.state = 'sent'
                rec.message_post(body=_("Letter emailed to %s.", to))
                sent += 1
            except Exception:
                _logger.exception('pb.hr.letter %s: sending failed', rec.id)
        _logger.info('pb.hr.letter: queued %s letter email(s)', sent)
        return sent

    def action_open_pdf(self):
        self.ensure_one()
        if not self.attachment_id:
            self.action_generate()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % self.attachment_id.id,
            'target': 'new',
        }
