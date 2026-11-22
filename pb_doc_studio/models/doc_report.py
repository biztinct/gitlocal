# -*- coding: utf-8 -*-
"""Values of `pb_doc_studio.report_doc_letter` (the three margin reports).

Two callers: a real letter (`docids` = `pb.hr.letter` ids, `_make_pdf`) and
the studio's sample PDF (`data['pbds_sample']`, prepared by `sample_pdf`, no
record at all — nothing is created or filed for a sample).
"""
from odoo import api, models

from .doc_common import DEFAULT_PAGE


class ReportDocLetter(models.AbstractModel):
    _name = 'report.pb_doc_studio.report_doc_letter'
    _description = 'Document studio letter'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        pages = data.get('pbds_sample')
        if not pages:
            letters = self.env['pb.hr.letter'].browse(docids or []).exists()
            pages = [letter._pbds_pdf_page() for letter in letters]
        first = pages[0]['page'] if pages else DEFAULT_PAGE
        clean = self.env['pb.doc.studio']._pbds_clean_page(first)
        return {
            'doc_ids': docids,
            'doc_model': 'pb.hr.letter',
            'docs': self.env['pb.hr.letter'].browse(docids or []),
            'pages': pages,
            'letterhead': clean['letterhead'],
        }
