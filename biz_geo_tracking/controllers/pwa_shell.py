# -*- coding: utf-8 -*-
"""GeoPwaShell — a plain mixin that serves a PWA manifest + service worker for a
named app. Cloned from website_event_track/controllers/webmanifest.py but with
NO website dependency. A consuming controller inherits it and calls the helpers
from its own routes (which own the URL + auth policy)."""
import json

from odoo.http import request
from odoo.tools.misc import file_open


class GeoPwaShell:

    def _make_manifest(self, name, short_name, scope, start_url,
                       theme_color='#0b1f3a', bg_color='#ffffff', icons=None):
        """Return a webmanifest JSON http response."""
        manifest = {
            'name': name,
            'short_name': short_name,
            'description': name,
            'scope': scope,
            'start_url': start_url,
            'display': 'standalone',
            'orientation': 'portrait',
            'background_color': bg_color,
            'theme_color': theme_color,
            'icons': icons or [],
        }
        return request.make_response(
            json.dumps(manifest),
            [('Content-Type', 'application/manifest+json')],
        )

    def _make_service_worker(self, scope, sw_path='biz_geo_tracking/static/src/js/geo_sw.js'):
        """Serve the app-shell service worker with the Service-Worker-Allowed
        header so it can control ``scope`` even though the file is served from
        /web/... . App-shell caching only — no Background Sync."""
        with file_open(sw_path, 'r') as fp:
            body = fp.read()
        return request.make_response(body, [
            ('Content-Type', 'text/javascript'),
            ('Service-Worker-Allowed', scope),
        ])
