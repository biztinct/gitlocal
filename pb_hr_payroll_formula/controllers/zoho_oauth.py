# -*- coding: utf-8 -*-
"""Interactive Zoho OAuth flow for the Connection & Feed Studio."""
import hmac
import re
import secrets
import time

from markupsafe import escape

from odoo import http
from odoo.http import request


def _result_page(ok, message):
    tone = '#16794a' if ok else '#b4234d'
    title = 'Zoho connected' if ok else 'Zoho connection failed'
    event = 'success' if ok else 'error'
    safe_message = escape(message or '')
    nonce = secrets.token_urlsafe(18)
    html = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>%(title)s</title></head>
<body style="margin:0;background:#f6f7fb;font:14px system-ui;color:#17172f;display:grid;place-items:center;min-height:100vh">
<main style="width:min(420px,calc(100%% - 32px));background:white;border:1px solid #e5e7ef;border-radius:18px;padding:32px;box-shadow:0 18px 55px rgba(31,35,67,.12);text-align:center">
<div style="width:52px;height:52px;border-radius:16px;background:%(tone)s18;color:%(tone)s;display:grid;place-items:center;margin:0 auto 16px;font-size:26px">%(mark)s</div>
<h1 style="font-size:21px;margin:0 0 8px">%(title)s</h1>
<p style="color:#6b7085;line-height:1.55;margin:0 0 20px">%(message)s</p>
<button id="pb-close" style="border:0;border-radius:10px;background:#5b4fc7;color:white;padding:10px 18px;font-weight:700;cursor:pointer">Return to Payobook</button>
</main>
<script nonce="%(nonce)s">
document.getElementById('pb-close').addEventListener('click', function(){ window.close(); });
if (window.opener) {
  window.opener.postMessage({type:'pb-zoho-oauth',status:'%(event)s'}, window.location.origin);
  if ('%(event)s' === 'success') { setTimeout(function(){ window.close(); }, 900); }
}
</script></body></html>""" % {
        'title': title, 'tone': tone, 'mark': '✓' if ok else '!',
        'message': safe_message, 'event': event, 'nonce': nonce,
    }
    return request.make_response(html, headers=[
        ('Content-Type', 'text/html; charset=utf-8'),
        ('Content-Security-Policy',
         "default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-%s'" % nonce),
        ('Cache-Control', 'no-store'),
    ])


class ZohoOAuthController(http.Controller):

    @http.route('/pb/integrations/oauth/<int:connector_id>/start',
                type='http', auth='user', methods=['GET'], csrf=False)
    def start(self, connector_id, **_kw):
        if not request.env.user.has_group('base.group_system'):
            return _result_page(False, 'Only a system administrator can start OAuth.')
        connector = request.env['hr.integration.connector'].browse(connector_id)
        if (not connector.exists() or connector.connector_type != 'zoho' or
                not connector.has_access('write')):
            return _result_page(False, 'That Zoho connector is not available.')
        if not connector.client_id or not connector.client_secret:
            return _result_page(
                False, 'Save the Zoho Client ID and Client Secret first.')

        state = secrets.token_urlsafe(32)
        request.session['pb_zoho_oauth'] = {
            'state': state, 'connector_id': connector.id,
            'uid': request.env.uid, 'expires': int(time.time()) + 600,
        }
        url = connector._get_connector_instance().get_authorization_url(state=state)
        return request.redirect(url, local=False)

    @http.route('/zoho/callback', type='http', auth='user', methods=['GET'], csrf=False)
    def callback(self, code=None, state=None, error=None, **_kw):
        flow = request.session.pop('pb_zoho_oauth', None) or {}
        valid = (
            flow.get('uid') == request.env.uid and
            flow.get('expires', 0) >= int(time.time()) and
            isinstance(state, str) and isinstance(flow.get('state'), str) and
            hmac.compare_digest(state, flow['state'])
        )
        if not valid:
            return _result_page(False, 'This authorization request expired or was not started here.')
        if error or not code:
            return _result_page(False, 'Zoho did not grant access. No credentials were changed.')

        connector = request.env['hr.integration.connector'].browse(
            int(flow.get('connector_id') or 0))
        if (not connector.exists() or not connector.has_access('write') or
                connector.connector_type != 'zoho'):
            return _result_page(False, 'That Zoho connector is no longer available.')
        accounts_server = (_kw.get('accounts-server') or '').rstrip('/')
        token_url = ''
        dc_match = re.fullmatch(
            r'https://accounts\.zoho\.(com|com\.au|eu|in|jp|ca|sa)',
            accounts_server)
        if dc_match:
            token_url = accounts_server + '/oauth/v2/token'
            if not connector.oauth_token_url:
                connector.oauth_token_url = token_url
            default_api = 'https://people.zoho.com/people/api'
            if not connector.api_endpoint or connector.api_endpoint == default_api:
                connector.api_endpoint = (
                    'https://people.zoho.%s/people/api' % dc_match.group(1))
        ok = connector._get_connector_instance().exchange_code_for_tokens(
            code, token_url=token_url)
        return _result_page(
            ok,
            'Authorization is complete. This window will close automatically.'
            if ok else 'Zoho returned a response, but Payobook could not exchange it for tokens.')
