from odoo import _, api, fields, models
from odoo.addons.pb_hiring.models.hiring_common import P_CANDIDATE_MAIL, flag

KEYS = [('joining_link', 'Joining link'), ('joining_code', 'Joining code'),
        ('joining_reminder', 'Joining reminder'), ('joining_back', 'Joining details to fix')]


class Template(models.Model):
    _inherit = 'pb.hiring.message.template'

    key = fields.Selection(selection_add=KEYS, ondelete={k: 'cascade' for k, label in KEYS})

    @api.model
    def _joining_copy(self):
        _ = self.env._
        return {
            'joining_link': (_('Welcome to {{brand}}. A few details before you start'),
                             _('Hello {{name}},\nBefore {{first_day}} we need a few details from you. It takes about 10 minutes on your phone. You will be asked for a 6-digit code. We send it when you open the link.'),
                             _('Fill in my details')),
            'joining_code': (_('{{code}} is your code'), _('Your code for {{brand}} is {{code}}. It works for 10 minutes. If you did not ask for it, ignore this message.'), ''),
            'joining_reminder': (_('{{first_name}}, your details for {{brand}}'),
                                 _('Before you start on {{first_day}}, please finish these sections: {{sections}}.'), _('Fill in my details')),
            'joining_back': (_('One thing to fix before you start'), _('HR asked you to check these details:\n{{notes}}'), _('Check my details')),
        }

    @api.model
    def _joining_seed(self, companies=None):
        words = self.with_context(lang='en_US')._joining_copy()
        langs = [code for code, label in self.env['res.lang'].get_installed() if code in ('vi_VN', 'id_ID')]
        translations = {lg: self.with_context(lang=lg)._joining_copy() for lg in langs}
        for company in companies or self.env['res.company'].sudo().search([]):
            for key, label in KEYS:
                row = self.with_context(active_test=False).search([('key', '=', key), ('company_id', '=', company.id)], limit=1)
                if not row:
                    subject, body, button = words[key]
                    row = self.with_context(lang='en_US').create({'name': label, 'company_id': company.id,
                        'key': key, 'subject': subject, 'body': body, 'button': button, 'sequence': 95})
                for lg in langs:
                    for i, field in enumerate(('subject', 'body', 'button')):
                        term = translations[lg][key][i]
                        if term and term != words[key][i] and not row._pb_raw(field).get(lg):
                            row.update_field_translations(field, {lg: term})


class HiringMail(models.AbstractModel):
    _inherit = 'pb.hiring'

    def _pb_email_html(self, body, button='', link='', lang='en_US'):
        html = super()._pb_email_html(body, button, link, lang)
        if self.env.context.get('pb_joining_message'):
            html = html.replace('#4F46E5', '#5A4BB0')
        return html

    def _mail_candidate(self, key, applicant, values=None, attachments=None, record=None, email_to=None,
                        reply_to=None, gate=True, dry=False, lang=None):
        if key != 'joining_code' or dry:
            return super()._mail_candidate(key, applicant, values=values, attachments=attachments, record=record,
                                          email_to=email_to, reply_to=reply_to, gate=gate, dry=dry, lang=lang)
        # The ordinary sender quotes its subject in the applicant history and queues a retained copy.
        # A code must be delivered inside this transaction, without either copy.
        result = super()._mail_candidate(key, applicant, values=values, record=record, email_to=email_to,
                                         gate=gate, dry=True, lang=lang)
        if result['status'] != 'dry' or not record._can_email():
            return {'status': 'mail_off'}
        template = self._pb_template(key, record.company_id)
        msg = template._pb_render(applicant, values, result['lang'])
        mail = self.env['mail.mail'].sudo().create({
            'subject': msg['subject'], 'body_html': self._pb_email_html(msg['body'], '', '', result['lang']),
            'email_from': self._sender(record.company_id), 'email_to': record.email,
            'auto_delete': True})
        try:
            mail.send(raise_exception=True)
            sent = not mail.exists() or mail.state == 'sent'
        finally:
            mail.exists().unlink()
        return {'status': 'sent' if sent else 'mail_off'}


class JoiningMail(models.Model):
    _inherit = 'pb.joining'

    def _can_email(self):
        return bool(self.email and self.env['pb.new.hire.invite']._mail_on() and flag(self.env, P_CANDIDATE_MAIL))

    def _mail(self, key, extra=None):
        self.ensure_one()
        if not self._can_email():
            return False
        values = {'name': self.name, 'first_name': self._first(), 'brand': self.company_id.name,
                  'first_day': lambda lang: self.with_context(lang=lang)._day_label(), 'link': self._url()}
        values.update(extra or {})
        hiring = self.env['pb.hiring'].sudo().with_company(self.company_id).with_context(pb_joining_message=True)
        if not hiring._pb_template(key, self.company_id):
            self.env['pb.hiring.message.template'].sudo()._joining_seed(self.company_id)
        result = hiring._mail_candidate(key, self.applicant_id, values=values, record=self,
                                        email_to=self.email, lang=self.lang)
        return result['status'] == 'sent'
