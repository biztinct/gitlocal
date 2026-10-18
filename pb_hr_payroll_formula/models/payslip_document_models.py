"""Visual document storage and native PDF routing for the themed payslip."""
import copy
import io

from markupsafe import Markup
from odoo import api, fields, models
from odoo.exceptions import ValidationError
from . import payslip_document as document_tools


class FormulaConfig(models.Model):
    _inherit = 'hr.formula.config'

    payslip_document = fields.Json(
        string='Visual Payslip Document', copy=False,
        help='Imported page artwork and reviewed live fields, in PDF points.')

    def copy(self, default=None):
        self.ensure_one()
        result = super().copy(default=default)
        if self.payslip_document and 'payslip_document' not in (default or {}):
            document = copy.deepcopy(self.payslip_document)
            by_code = {rule.code: rule.id for rule in result.rule_ids}
            remap = {rule.id: by_code.get(rule.code) for rule in self.rule_ids}
            for page in document['pages']:
                for field in page['fields']:
                    if field['binding'] == 'component':
                        field['rule_id'] = remap.get(field['rule_id'])
                        if not field['rule_id']:
                            field['binding'] = 'blank'
                    field['rate_rule_id'] = remap.get(field['rate_rule_id']) or False
            result.payslip_document = document
        return result

    @api.constrains('payslip_document')
    def _check_payslip_document(self):
        for config in self.filtered('payslip_document'):
            try:
                document_tools.validate_document(config.payslip_document, set(config.rule_ids.ids), config.PAYSLIP_META_KEYS)
            except (ValueError, TypeError, OverflowError) as error:
                raise ValidationError(str(error)) from error

    def _payslip_document_render(self, values_by_rule=None, currency='', meta=None):
        self.ensure_one()
        if not self.payslip_document:
            return []
        # Revalidate stored bindings: components may have been deleted since save.
        rules = {rule.id: rule for rule in self.rule_ids}
        return document_tools.render_pages(
            self.payslip_document, rules, values_by_rule or {}, currency,
            meta or {}, self._payslip_token_value)

    def _payslip_document_html(self, pages):
        return Markup(document_tools.render_html(pages))


class PayslipDocumentReport(models.Model):
    _inherit = 'ir.actions.report'

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        ids = [res_ids] if isinstance(res_ids, int) else (res_ids or [])
        if (report.report_name != 'pb_hr_payroll_formula.payslip_themed'
                or not ids or self.env.context.get('pb_payslip_legacy_pdf')):
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        slips = self.env['hr.payslip'].browse(ids)
        slips.check_access('read')
        if not any(slip.formula_config_id.payslip_document for slip in slips):
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        rendered = [slip._themed_payslip_render() for slip in slips]
        if not any(item.get('document_pages') for item in rendered):
            return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
        streams = []
        for slip, payload in zip(slips, rendered):
            if payload.get('document_pages'):
                pdf = document_tools.render_pdf(payload['document_pages'])
            else:
                pdf, _ = self.with_context(pb_payslip_legacy_pdf=True)._render_qweb_pdf(
                    report_ref, res_ids=[slip.id], data=data)
            streams.append(io.BytesIO(pdf))
        try:
            if len(streams) == 1:
                return streams[0].getvalue(), 'pdf'
            with self._merge_pdfs(streams) as merged:
                return merged.getvalue(), 'pdf'
        finally:
            for stream in streams:
                stream.close()
