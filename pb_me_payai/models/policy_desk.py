# -*- coding: utf-8 -*-
"""Home › Policies — where HR uploads policy files and switches PayAI on.

Gates: the HR team (`hr.group_hr_user`) manages the files; switching PayAI on
for employees and setting the daily limits is for an HR manager or an
administrator, because every question costs on the company's AI account.
Every read and write is for the reader's CURRENT company only.
"""
import base64

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import format_date

from .policy_document import LANGS, MAX_BYTES

#: File types HR may upload.
UPLOAD_OK = ('.pdf', '.docx', '.txt', '.md')


class PbPolicyDesk(models.AbstractModel):
    _name = 'pb.policy.desk'
    _description = 'Policy answers: the HR desk'

    # ------------------------------------------------------------ gates
    @api.model
    def can_open(self):
        return bool(self.env.su or self.env.user.has_group('hr.group_hr_user'))

    @api.model
    def _can_switch(self):
        user = self.env.user
        return bool(self.env.su or user.has_group('hr.group_hr_manager')
                    or user.has_group('base.group_system'))

    @api.model
    def _gate(self):
        if not self.can_open():
            raise AccessError(_("Only the HR team manages company policies."))

    # ------------------------------------------------------------ read
    @api.model
    def get_desk(self):
        self._gate()
        company = self.env.company
        Answer = self.env['pb.policy.answer']
        config = Answer._config(company)
        docs = self.env['pb.policy.document'].search(
            [('company_id', '=', company.id)])
        labels = dict(self.env['pb.policy.document']._fields['language']
                      ._description_selection(self.env))
        return {
            'company': company.name,
            'on': bool(company.pb_policy_ai_on),
            'ready': bool(config),
            'can_switch': self._can_switch(),
            'person_day': company.pb_policy_ai_person_day,
            'company_day': company.pb_policy_ai_company_day,
            'usage': Answer._usage(company),
            'published': len(docs.filtered(lambda d: d.published and d.section_ids)),
            'documents': [{
                'id': d.id, 'name': d.name, 'filename': d.filename or '',
                'language': d.language, 'language_label': labels.get(d.language, ''),
                'published': bool(d.published), 'sections': d.section_count,
                'readable': bool(d.section_ids),
                'departments': d.department_ids.mapped('name'),
                'uploaded_on': format_date(self.env, d.create_date.date(),
                                           date_format='d MMM y') if d.create_date else '',
            } for d in docs],
            'languages': [{'key': k, 'label': labels.get(k, k)} for k, _v in LANGS],
        }

    # ------------------------------------------------------------ write
    @api.model
    def set_switch(self, on):
        self._gate()
        if not self._can_switch():
            raise AccessError(_("Only an HR manager switches PayAI on for employees."))
        self.env.company.sudo().write({'pb_policy_ai_on': bool(on)})
        return self.get_desk()

    @api.model
    def set_limits(self, person_day, company_day):
        self._gate()
        if not self._can_switch():
            raise AccessError(_("Only an HR manager changes the daily limits."))
        try:
            person, whole = int(person_day), int(company_day)
        except (TypeError, ValueError):
            raise UserError(_("Type the limits as whole numbers.")) from None
        if person < 0 or whole < 0 or person > 1000 or whole > 100000:
            raise UserError(_("Choose limits between 0 and 1,000 per person and 0 and 100,000 per company."))
        self.env.company.sudo().write({'pb_policy_ai_person_day': person,
                                       'pb_policy_ai_company_day': whole})
        return self.get_desk()

    @api.model
    def upload(self, name, filename, data_b64, language='any'):
        self._gate()
        name = (name or '').strip() or (filename or '').rsplit('.', 1)[0]
        if not name:
            raise UserError(_("Give the policy a title."))
        if not (filename or '').lower().endswith(UPLOAD_OK):
            raise UserError(_("Upload a PDF, a Word file (.docx) or a text file."))
        try:
            raw = base64.b64decode(data_b64 or '', validate=False)
        except (TypeError, ValueError):
            raise UserError(_("That file could not be read. Try again.")) from None
        if not raw:
            raise UserError(_("That file is empty."))
        if len(raw) > MAX_BYTES:
            raise UserError(_("That file is bigger than 10 MB. Upload a smaller one, or split it."))
        if language not in dict(LANGS):
            language = 'any'
        doc = self.env['pb.policy.document'].create({
            'name': name[:200], 'filename': filename[:200], 'file': data_b64,
            'language': language, 'company_id': self.env.company.id,
        })
        res = self.get_desk()
        res['note'] = (_("Read %(n)s sections from %(name)s. Publish it when it is ready for employees.",
                         n=doc.section_count, name=doc.name)
                       if doc.section_ids else
                       _("No words could be read from %(name)s. A scanned file has no words: upload the original document instead.",
                         name=doc.name))
        return res

    @api.model
    def set_published(self, document_id, published):
        self._gate()
        doc = self.env['pb.policy.document'].browse(int(document_id or 0)).exists()
        if not doc or doc.company_id != self.env.company:
            raise UserError(_("That policy is not there any more."))
        if published and not doc.section_ids:
            raise UserError(_("No words could be read from this file, so it cannot be published."))
        doc.write({'published': bool(published)})
        return self.get_desk()

    @api.model
    def remove(self, document_id):
        self._gate()
        doc = self.env['pb.policy.document'].browse(int(document_id or 0)).exists()
        if not doc or doc.company_id != self.env.company:
            raise UserError(_("That policy is not there any more."))
        doc.unlink()
        return self.get_desk()
