from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.pb_hr_payroll_formula.models.payslip_document import render_pdf


class PayslipDocumentPreview(http.Controller):
    @http.route('/pb_formula_studio/payslip_document/preview/<int:config_id>',
                type='http', auth='user', methods=['GET'])
    def preview(self, config_id, sample_id=None, **kwargs):
        data = request.env['pb.formula.studio'].payslip_studio_data(config_id, sample_id)
        if not data.get('document_pages'):
            return request.not_found()
        return request.make_response(render_pdf(data['document_pages']), headers=[
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', content_disposition('Payslip template preview.pdf')),
            ('Cache-Control', 'private, no-store'),
        ])
