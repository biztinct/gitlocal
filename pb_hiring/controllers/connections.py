import hashlib
import hmac
import json

from odoo import http
from odoo.http import request
from ..services.docusign import valid_hmac


class HiringWebhooks(http.Controller):
    @http.route('/hiring/connect/<provider>/<key>', type='http', auth='public', methods=['GET','POST'], csrf=False, save_session=False)
    def webhook(self, provider, key, **params):
        if provider not in ('docusign', 'documenso', 'whatsapp'):
            return request.make_response('', status=404)
        conn = request.env['pb.hiring.connection'].sudo().search([
            ('provider', '=', provider), ('webhook_key', '=', key), ('enabled', '=', True)], limit=1)
        if not conn:
            return request.make_response('', status=403)
        if request.httprequest.method == 'GET':
            token = conn._secret('verify_token') if provider == 'whatsapp' else ''
            if token and params.get('hub.mode') == 'subscribe' and hmac.compare_digest(token, params.get('hub.verify_token', '')):
                return request.make_response(params.get('hub.challenge', ''))
            return request.make_response('', status=403)
        raw = request.httprequest.stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            return request.make_response('', status=413)
        if provider == 'documenso':
            expected = conn._secret('webhook_secret')
            valid = expected and hmac.compare_digest(expected, request.httprequest.headers.get('X-Documenso-Secret', ''))
        elif provider == 'docusign':
            valid = valid_hmac(conn._secret('hmac_key'), raw,
                [request.httprequest.headers.get('X-Docusign-Signature-%s' % i, '') for i in range(1, 6)])
        else:
            secret = conn._secret('app_secret')
            expected = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest() if secret else ''
            valid = expected and hmac.compare_digest(expected, request.httprequest.headers.get('X-Hub-Signature-256', ''))
        if not valid:
            return request.make_response('', status=403)
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, TypeError):
            return request.make_response('', status=400)
        if provider == 'documenso':
            payload = data.get('payload')
            envelope_id = payload.get('envelopeId') if isinstance(payload, dict) else None
            offers = request.env['pb.hiring.offer'].sudo().search([
                ('pb_sign_connection_id', '=', conn.id), ('pb_envelope_id', '=', envelope_id)]) if isinstance(envelope_id, str) else []
            # Acknowledge quickly; the scheduled job verifies over the API.
            for offer in offers:
                offer.write({'pb_sign_note': 'Provider update received; verification queued.'})
        elif provider == 'docusign':
            conn._ds_receive(data)
        else:
            conn._receive_whatsapp_status(data)
        return request.make_response('', status=200)
