# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""The page title of every printed report.

`web.report_layout` and `web.report_preview_layout` print
``<title t-esc="title or 'Odoo Report'"/>``: a report that does not set its
own `title` shows the platform's name in the browser tab of its web preview
and as the document title of the PDF made from the same page (WDGAP S5-F, a
payslip's preview). `views/report_title.xml` replaces that fallback with the
report's own name, handed in here as `biz_report_title`, and a neutral
"Report" (`_biz_default_title`, translated) when there is none. A report
that sets `title` keeps it.

The name is the printed name of the one document when the report says how to
name it (`print_report_name`, the same expression the download's file name
uses — "Payslip - …"), otherwise the report's own name, in the reader's
language. Working the name out never stops a print.
"""
import logging

from odoo import _, api, models
from odoo.tools.safe_eval import safe_eval, time

_logger = logging.getLogger(__name__)


class IrActionsReport(models.Model):
    _inherit = 'ir.actions.report'

    def _get_rendering_context(self, report, docids, data):
        data = super()._get_rendering_context(report, docids, data)
        if not data.get('biz_report_title'):
            try:
                data['biz_report_title'] = self._biz_report_title(report, docids)
            except Exception:       # noqa: BLE001 — a title never stops a print
                _logger.debug('biz_debrand: no report title for %s', report.report_name,
                              exc_info=True)
        return data

    @api.model
    def _biz_default_title(self):
        """The neutral page title when nothing names the page."""
        return _('Report')

    def _biz_report_title(self, report, docids):
        ids = docids if isinstance(docids, (list, tuple)) else ([docids] if docids else [])
        if report.print_report_name and len(ids) == 1 and report.model in self.env:
            record = self.env[report.model].browse(ids[0]).exists()
            if record:
                name = safe_eval(report.print_report_name, {'object': record, 'time': time})
                if name and isinstance(name, str):
                    return name
        return report.name or ''
