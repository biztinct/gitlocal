# -*- coding: utf-8 -*-
"""An employment contract made as a letter (the Letters list, a workflow
step) prints like the one from the contract panel:

* its "Show only when" paragraphs follow the built-in rules of a shipped
  contract never saved in the studio (`_pbdc_rules`);
* its page is the contract page (`_pbdc_page`: no letter signature block —
  both parties sign in the wording);
* the employer representative reads the page design of the document being
  made: the designer's preview passes nothing else, so the letter tells the
  value resolver which page it prints on (context `pbdc_page`).
"""
import base64

from odoo import models


class PbHrLetter(models.Model):
    _inherit = 'pb.hr.letter'

    def _pbds_values(self, lang, keys):
        self.ensure_one()
        if 'pbdc_page' not in self.env.context and self.template_id:
            page = self.template_id.sudo()._pbdc_page() or {}
            return super(PbHrLetter, self.with_context(pbdc_page=page))._pbds_values(lang, keys)
        return super()._pbds_values(lang, keys)

    def _pbds_render(self, body, lang, ghost=False, missing=None, wrap=None):
        self.ensure_one()
        tmpl = self.template_id.sudo()
        if self.env.context.get('pbds_rules_override') is None and tmpl \
                and not tmpl.pbds_rules and tmpl._pbdc_rules():
            return super(PbHrLetter, self.with_context(pbds_rules_override=tmpl._pbdc_rules()))._pbds_render(
                body, lang, ghost=ghost, missing=missing, wrap=wrap)
        return super()._pbds_render(body, lang, ghost=ghost, missing=missing, wrap=wrap)

    def _pbds_pdf_page(self):
        res = super()._pbds_pdf_page()
        tmpl = self.template_id.sudo()
        if tmpl and not tmpl.pbds_page and tmpl._pbdc_is_contract():
            res['page'] = tmpl._pbdc_page()
        return res

    def _make_pdf(self):
        """A contract without a saved page still prints on the contract page
        with the studio's report (the studio sends a template without a page
        to the old letter frame)."""
        self.ensure_one()
        tmpl = self.template_id.sudo()
        if not tmpl or tmpl.pbds_page or not tmpl._pbdc_is_contract():
            return super()._make_pdf()
        report = self.env['pb.doc.studio']._pbds_report(tmpl._pbdc_page())
        pdf, _ext = report.sudo()._render_qweb_pdf(report, res_ids=self.ids)
        filename = '%s.pdf' % (self.subject or self.name or 'Contract').replace('/', '-')
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
            old.sudo().unlink()
        return att
