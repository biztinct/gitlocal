from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError


class CandidateFile(http.Controller):
    @http.route('/hiring/candidate-file/<int:attachment_id>', type='http', auth='user', methods=['GET'])
    def file(self, attachment_id):
        attachment = request.env['ir.attachment'].sudo().browse(attachment_id).exists()
        if not attachment or attachment.res_model != 'hr.applicant':
            return request.not_found()
        facade = request.env['pb.hiring']
        try:
            app = facade._applicant(attachment.res_id)
            permitted = facade._doc_rows(app, facade._parts(app), tokenised=False)
            if attachment_id not in [r['id'] for r in permitted]:
                return request.not_found()
        except AccessError:
            return request.not_found()
        return request.make_response(attachment.raw, headers=[
            ('Content-Type', attachment.mimetype or 'application/octet-stream'),
            ('Content-Disposition', "attachment; filename=\"candidate-document\""),
            ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff')])
