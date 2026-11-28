# -*- coding: utf-8 -*-
"""Contracts print at the size they had before the PDF engine changed.

The engine with patched Qt (live since DOCSTUDIO PDFFIX) honours dpi/zoom and
draws a page ~15% larger than the engine it replaced; a one-page contract with
the company letterhead then ran onto a second page. A page laid out as a
contract (this module's clause or signature tables) prints at dpi 100, which
is the old size. Letters keep the studio's size: none of the shipped letters
changed page count (DOCSTUDIO PDFFIX-2)."""
from odoo import api, models

CONTRACT_DPI = 100
CONTRACT_MARKERS = ('pbdc-bi', 'pbdc-sign')


class ReportDocLetter(models.AbstractModel):
    _inherit = 'report.pb_doc_studio.report_doc_letter'

    @api.model
    def _get_report_values(self, docids, data=None):
        values = super()._get_report_values(docids, data)
        for page in values.get('pages') or []:
            text = '%s%s' % (page.get('body') or '', page.get('body_tail') or '')
            if any(marker in text for marker in CONTRACT_MARKERS):
                values['data_report_dpi'] = CONTRACT_DPI
                break
        return values
