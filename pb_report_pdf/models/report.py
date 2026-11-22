# -*- coding: utf-8 -*-
"""The PDF report (`pb_report_pdf.report_table`, two actions: A4 and A3).

Values come only from `data['pbrp']`, prepared by `pb.report.pdf._pbrp_pdf`
for the person printing — the report reads no record itself.

With the company letterhead on, the page header and footer are the
company's own (`web.external_layout`, the same as every other document of
the company, page numbers included). The "Printed on … by …" line is added
to THAT footer here, for this report only — the PDF engine takes one footer
per document.
"""
import logging

import lxml.html
from markupsafe import Markup

from odoo import api, models

_logger = logging.getLogger(__name__)

REPORT_NAME = 'pb_report_pdf.report_table'


class ReportPbReportPdfTable(models.AbstractModel):
    _name = 'report.pb_report_pdf.report_table'
    _description = 'Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        values = dict((data or {}).get('pbrp') or {})
        if not values.get('rp'):
            # Printed from anywhere else (never offered): an empty page.
            values = {'rp': None}
        values.update({'doc_ids': [], 'doc_model': 'pb.report.pdf.look',
                       'docs': self.env['pb.report.pdf.look']})
        return values


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _prepare_html(self, html, report_model=False):
        res = super()._prepare_html(html, report_model=report_model)
        extra = self.env.context.get('pbrp_footer')
        if not extra or not res or self.report_name != REPORT_NAME:
            return res
        bodies, res_ids, header, footer, args = res
        try:
            root = lxml.html.fromstring(str(footer))
            holder = root.get_element_by_id('minimal_layout_report_footers', None)
            target = holder[0] if holder is not None and len(holder) else holder
            if target is not None:
                for node in lxml.html.fragments_fromstring(str(extra)):
                    if isinstance(node, str):
                        continue
                    target.append(node)
                footer = Markup(lxml.html.tostring(root, encoding='unicode',
                                                   doctype='<!DOCTYPE html>'))
        except Exception:                                    # noqa: BLE001
            _logger.warning('pb_report_pdf: the printed-on line could not join the '
                            'company footer', exc_info=True)
        return bodies, res_ids, header, footer, args
