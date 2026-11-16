# -*- coding: utf-8 -*-
"""`pb.conduct.letter` — a letter of a conduct case, draft until it is issued.

NOT a `pb.hr.letter` row, on purpose (FACTS §2.4 leak 1): every lifecycle
user, manager and administrator can read `pb.hr.letter`, so a warning letter
stored there would be readable by the whole lifecycle team. This module keeps
its own letter model, with no access right for anybody but the named people,
and renders its own PDF.

ISSUING is the only moment the letter leaves the named people:
  * the PDF is made (one record per render — LEARNING LN33);
  * a copy is filed in the employee's documents under the module's own
    category — which a GLOBAL rule hides from everybody not named, except the
    person it is addressed to (FACTS §2.4 leak 2);
  * the employee can now read it on My Payobook, say they have read it, and
    reply once.

Nothing is emailed: tenant databases send no mail on purpose, and an email
would carry the letter outside the system. The employee is told through the
"Needs you" row on their home page.
"""

import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, format_datetime

from .conduct_common import LETTER_KINDS, VAULT_CODE

_logger = logging.getLogger(__name__)

REPLY_MAX = 4000


class PbConductLetter(models.Model):
    _name = 'pb.conduct.letter'
    _description = 'Conduct case letter'
    _order = 'id desc'

    case_id = fields.Many2one('pb.conduct.case', required=True, index=True,
                              ondelete='cascade')
    employee_id = fields.Many2one(related='case_id.employee_id', store=True,
                                  index=True)
    company_id = fields.Many2one(related='case_id.company_id', store=True,
                                 index=True)
    kind = fields.Selection(LETTER_KINDS, string='Letter', required=True)
    template_id = fields.Many2one('pb.conduct.letter.template', string='Wording')
    title = fields.Char(string='Title', required=True)
    body = fields.Text(string='Letter text', required=True)
    state = fields.Selection([('draft', 'Draft'), ('issued', 'Issued')],
                             default='draft', required=True, index=True)
    issued_on = fields.Date(string='Issued on', readonly=True)
    issued_by = fields.Many2one('res.users', string='Issued by', readonly=True)
    attachment_id = fields.Many2one('ir.attachment', string='PDF', readonly=True,
                                    copy=False)
    document_id = fields.Many2one('pb.employee.document', string='In documents',
                                  readonly=True, copy=False)
    read_on = fields.Datetime(string='Employee read it on', readonly=True)
    reply = fields.Text(string="Employee's reply", readonly=True)
    reply_on = fields.Datetime(string='Replied on', readonly=True)
    reply_seen = fields.Boolean(string='Reply read by HR', readonly=True)

    # ============================================================ prepare
    def _values(self, case, signer=None):
        emp = case.employee_id.sudo()
        lang = self._letter_lang(emp)
        env = self.with_context(lang=lang).env
        return {
            'employee': emp.name or '',
            'job': emp.job_title or (emp.job_id.name if emp.job_id else '') or '',
            'department': (case.department_id or emp.department_id).sudo().with_context(
                lang=lang).name or '',
            'company': case.company_id.name or '',
            'date': format_date(env, fields.Date.context_today(self)),
            'reason': case.reason_id.with_context(lang=lang).name or '',
            'incident_date': format_date(env, case.incident_date) if case.incident_date else '',
            'hearing_date': format_datetime(
                env, case.hearing_date, tz=self._tz(emp),
                dt_format='d MMMM y, HH:mm') if case.hearing_date else '',
            'hearing_place': case.hearing_place or '',
            'decision': case.decision_summary or '',
            'valid_until': format_date(env, case.valid_until) if case.valid_until else '',
            'signed_by': (signer or self.env.user).name or '',
        }

    @api.model
    def _letter_lang(self, emp):
        user = emp.user_id
        return (user.lang if user else None) or emp.company_id.partner_id.lang \
            or self.env.lang or 'en_US'

    @api.model
    def _tz(self, emp):
        return (emp.user_id.tz if emp.user_id else None) or emp.tz or \
            emp.company_id.partner_id.tz or 'UTC'

    @api.model
    def prepare(self, case, kind):
        """A DRAFT letter of `kind` for `case`, worded from the template."""
        case.ensure_one()
        template = self.env['pb.conduct.letter.template'].pick(kind, case.company_id)
        lang = self._letter_lang(case.employee_id.sudo())
        if template:
            tpl = template.with_context(lang=lang)
            values = self._values(case)
            title = tpl.render(tpl.title, values)
            body = tpl.render(tpl.body, values)
        else:
            title = dict(self._fields['kind']._description_selection(self.env)).get(kind, '')
            body = ''
        letter = self.create({
            'case_id': case.id, 'kind': kind,
            'template_id': template.id if template else False,
            'title': title or _('Letter'), 'body': body or ' ',
        })
        case._log(_('Letter prepared: %s.', letter.title))
        return letter

    def write(self, vals):
        if {'title', 'body'} & set(vals):
            for letter in self:
                if letter.state != 'draft':
                    raise UserError(_('An issued letter cannot be changed. '
                                      'Prepare a new letter instead.'))
        return super().write(vals)

    def unlink(self):
        if any(l.state != 'draft' for l in self):
            raise UserError(_('An issued letter is kept with the case. It cannot be deleted.'))
        return super().unlink()

    # ============================================================== issue
    def action_issue(self):
        """Finish the letter: PDF, file it, and the employee can read it."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('This letter has already been issued.'))
        if not (self.body or '').strip():
            raise UserError(_('The letter has no text yet.'))
        self.write({'state': 'issued',
                    'issued_on': fields.Date.context_today(self),
                    'issued_by': self.env.uid})
        self._make_pdf()
        self._file_in_vault()
        self.case_id._log(_('Letter issued: %s. The employee can now read it on '
                            'their own page.', self.title))
        case = self.case_id
        if self.kind != 'invite' and case.state == 'letter':
            case.write({'state': 'closed',
                        'closed_on': fields.Date.context_today(self)})
            case._log(_('Case closed with the decision letter.'))
        return True

    def _make_pdf(self):
        self.ensure_one()
        report = self.env.ref('pb_conduct.action_report_conduct_letter',
                              raise_if_not_found=False)
        if not report:
            _logger.warning('pb_conduct: the letter report is missing')
            return False
        try:
            content, _ext = report.sudo()._render_qweb_pdf(
                'pb_conduct.report_conduct_letter', res_ids=self.ids)
        except Exception:                       # noqa: BLE001
            _logger.exception('pb_conduct: letter %s could not be rendered', self.id)
            return False
        name = '%s.pdf' % (self.title or 'Letter').replace('/', '-')
        att = self.env['ir.attachment'].sudo().create({
            'name': name, 'type': 'binary', 'datas': base64.b64encode(content),
            'res_model': self._name, 'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        self.sudo().attachment_id = att.id
        return att

    def _file_in_vault(self):
        """A copy of the PDF in the employee's documents, private category.

        Sudo: filing is a system act, and a named HR person need not hold the
        vault's create right. The GLOBAL rule in security/ keeps it from every
        HR officer and payroll officer who is not named.
        """
        self.ensure_one()
        if not self.attachment_id or self.document_id:
            return False
        category = self.env.ref('pb_conduct.vault_category_conduct',
                                raise_if_not_found=False)
        if not category or category.code != VAULT_CODE:
            return False
        try:
            Doc = self.env['pb.employee.document'].sudo()
            copy = self.attachment_id.sudo().copy({
                'res_model': 'pb.employee.document', 'res_id': 0})
            doc = Doc.create({
                'employee_id': self.employee_id.id, 'category_id': category.id,
                'name': self.title, 'attachment_id': copy.id,
                'issue_date': self.issued_on,
                'company_id': self.company_id.id,
            })
            copy.write({'res_id': doc.id})
            self.sudo().document_id = doc.id
            return doc
        except Exception:                       # noqa: BLE001
            _logger.exception('pb_conduct: letter %s could not be filed', self.id)
            return False

    # ===================================================== employee side
    @api.model
    def _mine(self, emp):
        """The ISSUED letters addressed to `emp` (sudo; caller proved `emp`)."""
        if not emp:
            return self.sudo().browse()
        return self.sudo().search([('employee_id', 'in', emp.ids),
                                   ('state', '=', 'issued')],
                                  order='issued_on desc, id desc')

    @api.model
    def my_letters(self, emp):
        rows = []
        for letter in self._mine(emp):
            rows.append({
                'id': letter.id,
                'title': letter.title or '',
                'kind': letter.kind,
                'issued_on': format_date(self.env, letter.issued_on) if letter.issued_on else '',
                'body': letter.body or '',
                'has_pdf': bool(letter.attachment_id),
                'read': bool(letter.read_on),
                'read_on': format_date(self.env, letter.read_on.date()) if letter.read_on else '',
                'reply': letter.reply or '',
                'reply_on': format_date(self.env, letter.reply_on.date()) if letter.reply_on else '',
            })
        return {'letters': rows, 'unread': sum(1 for r in rows if not r['read'])}

    @api.model
    def _own_letter(self, emp, letter_id):
        letter = self._mine(emp).filtered(lambda l: l.id == int(letter_id or 0))
        return letter[:1]

    @api.model
    def mark_read(self, emp, letter_id):
        letter = self._own_letter(emp, letter_id)
        if not letter:
            return False
        if not letter.read_on:
            letter.sudo().write({'read_on': fields.Datetime.now()})
            letter.case_id.sudo()._log(_('The employee said they have read "%s".', letter.title))
        return True

    @api.model
    def send_reply(self, emp, letter_id, text):
        letter = self._own_letter(emp, letter_id)
        if not letter:
            return {'ok': False, 'msg': _('That letter is not one of yours.')}
        text = (text or '').strip()
        if not text:
            return {'ok': False, 'msg': _('Write your reply first.')}
        if letter.reply:
            return {'ok': False, 'msg': _('You have already replied to this letter. Ask HR if you want to add something.')}
        text = text[:REPLY_MAX]
        vals = {'reply': text, 'reply_on': fields.Datetime.now(), 'reply_seen': False}
        if not letter.read_on:
            vals['read_on'] = fields.Datetime.now()
        letter.sudo().write(vals)
        letter.case_id.sudo()._log(_('The employee replied to "%s".', letter.title))
        return {'ok': True, 'msg': _('Your reply has been sent to HR.')}
