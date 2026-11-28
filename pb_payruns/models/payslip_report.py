"""Batch payslips also work with wkhtmltopdf builds accepting one input file."""
from lxml import etree, html

from odoo import models


class PayslipReport(models.Model):
    _inherit = 'ir.actions.report'

    def _run_wkhtmltopdf(self, bodies, report_ref=False, **kwargs):
        bodies = list(bodies)
        report = self._get_report(report_ref) if report_ref else self
        if (self.env.context.get('pb_payrun_print') and len(bodies) > 1
                and report.report_name in (
                    'pb_hr_payroll_formula.payslip_themed',
                    'om_hr_payroll.report_payslip')):
            # Odoo normally passes one HTML input per payslip. Distribution
            # wkhtmltopdf builds without patched Qt reject multiple inputs.
            # These slips share the same report assets and paper format, so
            # retain the first head and put every document in its body. The
            # original HTML record IDs remain available to Odoo's PDF splitter.
            parser = html.HTMLParser(encoding='utf-8')
            document = html.document_fromstring(bodies[0], parser=parser)
            body = document.find('body')
            for source in bodies[1:]:
                other = html.document_fromstring(source, parser=parser).find('body')
                page = etree.SubElement(body, 'div', style='page-break-before: always;')
                page.text = other.text
                page.extend(list(other))
            bodies = [html.tostring(document, encoding='unicode')]
        return super()._run_wkhtmltopdf(bodies, report_ref=report_ref, **kwargs)
