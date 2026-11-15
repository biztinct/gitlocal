# -*- coding: utf-8 -*-
"""Two more kinds of letter in the library everybody already edits.

`selection_add` on the TEMPLATE only (pb_hiring's precedent,
`pb_hiring/models/offer.py`): `pb.hr.letter.letter_type` is a related field
and takes its list from the template; extending it there fails the registry
load. Nothing in pb_lifecycle is edited.
"""

from odoo import fields, models

EMPLOYMENT = 'employment_cert'
SALARY = 'salary_cert'


class PbLetterTemplateCertificates(models.Model):
    _inherit = 'pb.letter.template'

    letter_type = fields.Selection(
        selection_add=[(EMPLOYMENT, 'Employment certificate'),
                       (SALARY, 'Salary certificate')],
        ondelete={EMPLOYMENT: 'set default', SALARY: 'set default'})
