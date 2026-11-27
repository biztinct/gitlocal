from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request, content_disposition
from werkzeug.exceptions import NotFound

from ..models.http import HEADERS


class JoiningFiles(http.Controller):
    @http.route('/pb_joining/file/<int:joining_id>/<int:attachment_id>', type='http', auth='user', methods=['GET'])
    def file(self, joining_id, attachment_id):
        try:
            a = request.env['pb.joining.board']._file(joining_id, attachment_id)
        except AccessError:
            raise NotFound() from None
        return request.make_response(a.raw, headers=list(HEADERS.items()) + [
            ('Content-Type',a.mimetype),('X-Content-Type-Options','nosniff'),
            ('Content-Disposition',content_disposition(a.name,disposition_type='inline')),
            ('Content-Security-Policy',"sandbox; default-src 'none'")])
