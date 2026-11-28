# -*- coding: utf-8 -*-
"""A certificate's letter honours the designer's heading in its language.

`pb_me_letters` names the letter "<heading> <certificate number>" from the
template it picked, in the employee's language, BEFORE the studio swaps in a
company / country copy and BEFORE the studio reads a language version — so a
designed heading (a version's own heading, a copy's heading) was lost on the
letter and in its PDF. For a studio certificate only, the heading the studio
reads for that language is used, with the number after it, exactly as
`pb_me_letters` writes it. An untouched certificate never comes here (the
studio sends it to the letter engine unchanged, rail R1).

The preview of a certificate shows its dates as the certificate prints them
(`pb.me.certificate._pb_values`: the short date of the letter's language),
so the person checking it sees what the employee will get.
"""
import json

from markupsafe import escape

from odoo import fields, models
from odoo.tools.misc import format_date

from .doc_studio import CERT_TYPES


class PbHrLetterCertificates(models.Model):
    _inherit = 'pb.hr.letter'

    def _pbdsme_cert_no(self):
        self.ensure_one()
        try:
            extra = json.loads(self.context_json or '{}')
        except (TypeError, ValueError):
            return False
        return extra.get('certificate_no') if isinstance(extra, dict) else False

    def _pbds_generate(self):
        self.ensure_one()
        tmpl = self.template_id
        cert_no = self._pbdsme_cert_no() if tmpl.letter_type in CERT_TYPES else False
        if cert_no:
            lang = self.lang or self._pbds_default_lang(tmpl, self.employee_id)
            _body, heading, read_lang = self._pbds_source(lang)
            heading = heading or tmpl.with_context(lang=read_lang).name
            if heading:
                self.sudo().write({'subject': '%s %s' % (heading, cert_no)})
        return super()._pbds_generate()

    def _pbds_values(self, lang, keys):
        values, blocked = super()._pbds_values(lang, keys)
        tmpl = self.template_id
        if tmpl and tmpl.letter_type in CERT_TYPES and not self._origin.id \
                and not self.context_json and self.employee_id:
            # The designer's preview (an unsaved letter): the dates as the
            # certificate will print them.
            env = self.with_context(lang=lang).env
            if 'date' in keys:
                values['date'] = str(escape(format_date(env, fields.Date.context_today(self))))
            if 'joining_date' in keys:
                joining = self._joining_date(self.employee_id)
                values['joining_date'] = str(escape(format_date(env, joining))) if joining else ''
        return values, blocked
