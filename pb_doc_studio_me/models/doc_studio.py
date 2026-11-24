# -*- coding: utf-8 -*-
"""Certificates in the Document studio's gallery and field list (phase A1).

Through the studio's extension points only: `_pbds_type_fields` (the
certificate's own keys under "This document") and `_pbds_card` (what it
prints for, how often it was issued).
"""
from odoo import api, models
from odoo.exceptions import AccessError
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)

#: The two certificate kinds `pb_me_letters` adds to the letter library.
EMPLOYMENT = 'employment_cert'
SALARY = 'salary_cert'
CERT_TYPES = (EMPLOYMENT, SALARY)

#: The dates a certificate prints in its own short form (the certificate's
#: `_pb_values` writes them), listed with its other fields.
_DATE_KEYS = ['date', 'joining_date']
_DATE_LABELS = [_lt('Date issued'), _lt('Joining date, as the certificate prints it')]


class PbDocStudioCertificates(models.AbstractModel):
    _inherit = 'pb.doc.studio'

    @api.model
    def _pbds_type_fields(self, letter_type, kind=None):
        rows = super()._pbds_type_fields(letter_type, kind)
        if letter_type in CERT_TYPES:
            known = {r[0] for r in rows}
            rows = rows + [(key, label, False) for key, label in zip(_DATE_KEYS, _DATE_LABELS)
                           if key not in known]
        return rows

    @api.model
    def _pbds_card(self, tmpl, flat=None):
        card = super()._pbds_card(tmpl, flat)
        if tmpl.letter_type in CERT_TYPES:
            _ = self.env._
            card['prints_for'] = _("Printed at once when an employee asks for it on My Payobook") \
                if tmpl.letter_type == EMPLOYMENT else \
                _("Printed when HR agrees an employee's request on My Payobook")
            kind = 'employment' if tmpl.letter_type == EMPLOYMENT else 'salary'
            try:
                n = self.env['pb.me.certificate'].search_count(
                    [('kind', '=', kind), ('state', '=', 'issued'),
                     ('company_id', 'in', self.env.companies.ids)])
            except AccessError:
                n = 0
            card['uses'] = n
            card['uses_text'] = _("Issued once") if n == 1 else (
                _("Issued %s times", n) if n else '')
        return card
