# -*- coding: utf-8 -*-
import os

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request


class PbTenantsController(http.Controller):

    @http.route('/pb_tenants/backup/<int:backup_id>', type='http', auth='user', readonly=True)
    def download_backup(self, backup_id, **kw):
        if not request.env.user.has_group('base.group_system'):
            raise AccessError("Restricted to system administrators.")
        rec = request.env['pb.tenant.backup'].sudo().browse(backup_id).exists()
        if not rec or not rec.path or not os.path.exists(rec.path):
            return request.not_found()
        try:
            stream = http.Stream.from_path(rec.path)
            stream.download_name = rec.filename
            stream.as_attachment = True
            return stream.get_response()
        except Exception:
            with open(rec.path, 'rb') as f:
                data = f.read()
            return request.make_response(data, headers=[
                ('Content-Type', 'application/zip'),
                ('Content-Disposition', http.content_disposition(rec.filename)),
                ('Content-Length', len(data)),
            ])
