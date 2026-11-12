"""Authenticated desktop collection API. Data issues are handled after intake."""
import json
import hashlib
from pathlib import Path

from odoo import SUPERUSER_ID, http
from odoo.http import request, Response, content_disposition
from odoo.modules.module import get_module_path

MAX_BODY = 2 * 1024 * 1024


def response(data, status=200):
    return Response(json.dumps(data), status=status, content_type='application/json', headers={'Cache-Control': 'no-store'})


class ClockBridge(http.Controller):
    @http.route('/clock-bridge/v1/<string:operation>', type='http', auth='none', methods=['POST'],
                csrf=False, readonly=False, save_session=False)
    def api(self, operation, **kw):
        hr = request.httprequest
        if hr.scheme != 'https':
            return response({'error': 'HTTPS required'}, 400)
        if (hr.content_length or 0) > MAX_BODY:
            return response({'error': 'Batch too large'}, 413)
        hr.max_content_length = MAX_BODY
        data = hr.get_data(cache=True)
        if len(data) > MAX_BODY:
            return response({'error': 'Batch too large'}, 413)
        try:
            payload = json.loads(data)
            if not isinstance(payload, dict):
                raise ValueError()
        except (ValueError, UnicodeDecodeError):
            return response({'error': 'Expected a JSON object'}, 400)
        env = request.env(user=SUPERUSER_ID, su=True)
        Connector = env['pb.clock.connector']
        if operation == 'pair':
            code, installation = payload.get('code'), payload.get('installation_id')
            if not isinstance(code, str) or not 20 <= len(code) <= 100 or not isinstance(installation, str) or not 16 <= len(installation) <= 100:
                return response({'error': 'Invalid pairing details'}, 400)
            result = Connector._pair(code, installation)
            return response(result or {'error': 'Pairing code expired or already used'}, 200 if result else 401)
        if operation != 'sync':
            return response({'error': 'Unknown operation'}, 404)
        auth = hr.headers.get('Authorization', '')
        connector = Connector._authenticate(auth[7:] if auth.startswith('Bearer ') and len(auth) < 200 else '')
        if not connector:
            return response({'error': 'Installation access is not valid. Re-pair from Payobook.'}, 401)
        env.cr.execute('SELECT id FROM pb_clock_connector WHERE id=%s FOR UPDATE', [connector.id])
        connector.invalidate_recordset()
        if connector.state != 'connected' or connector.token_hash != hashlib.sha256(auth[7:].encode()).hexdigest():
            return response({'error': 'Installation access revoked'}, 401)
        rows = payload.get('rows')
        status = payload.get('status', {})
        if not isinstance(rows, list) or len(rows) > 500 or not isinstance(status, dict):
            return response({'error': 'Expected at most 500 rows and a status object'}, 400)
        # Malformed business rows still land in the review inbox. Only wire-level
        # constraints fail a request; the supplied client always respects these.
        if any(len(json.dumps(row, ensure_ascii=False)) > 8192 for row in rows):
            return response({'error': 'A source row exceeds 8192 characters'}, 400)
        for key in ('pending', 'source_rows'):
            if key in status and (not isinstance(status[key], int) or isinstance(status[key], bool)):
                return response({'error': 'Invalid status counters'}, 400)
        result = connector._receive(payload)
        # The framework commits the HTTP request before sending the response. No early ack.
        return response(result)

    @http.route('/clock-bridge/download', type='http', auth='user', methods=['GET'])
    def download(self, **kw):
        if not request.env.user.has_group('hr_attendance.group_hr_attendance_manager'):
            return Response('Attendance manager access required.', status=403)
        package = Path(get_module_path('pb_clock')) / 'releases' / 'PayobookAttendanceConnector.zip'
        if not package.is_file():
            return Response('The Windows package is not installed on this server yet.', status=503)
        return Response(package.read_bytes(), content_type='application/zip', headers=[
            ('Content-Disposition', content_disposition(package.name)), ('Cache-Control', 'private, no-store')])
