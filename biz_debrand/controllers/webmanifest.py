# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Brand the PWA manifest.

This is what the browser's "install this app" prompt reads. Core builds it in
``web/controllers/webmanifest.py:43`` with ``name`` defaulting to the literal
``'Odoo'``, the vendor's ``#714B67`` theme colour and ``odoo-icon-*.png``.

``_biz_debrand_apply_brand`` sets ``web.web_app_name`` so core's own default is
never reached; this override handles what core exposes no parameter for — the
colours, the icons, and the ``scope``/``start_url`` prefix, which must follow
the backend URL when a router rebrand such as ``biz_deroute`` is installed
(otherwise the installed app navigates straight out of its own scope and the
browser drops it back into a normal tab).
"""
import logging

from odoo.http import request

from odoo.addons.web.controllers.webmanifest import WebManifest

_logger = logging.getLogger(__name__)

BRAND_ICON_URL = "/biz_debrand/static/src/img/brand_icon.png"
DEFAULT_THEME_COLOR = "#1565C0"


class BizWebManifest(WebManifest):
    def _get_webmanifest(self):
        manifest = super()._get_webmanifest()
        try:
            icp = request.env["ir.config_parameter"].sudo()
            color = (icp.get_param("biz_debrand.theme_color") or DEFAULT_THEME_COLOR).strip()
            manifest["background_color"] = color
            manifest["theme_color"] = color
            manifest["icons"] = [
                {"src": BRAND_ICON_URL, "sizes": size, "type": "image/png"}
                for size in ("192x192", "512x512")
            ]
            prefix = (icp.get_param("biz_debrand.web_app_scope") or "").strip()
            if prefix:
                for key in ("scope", "start_url"):
                    manifest[key] = prefix
                for shortcut in manifest.get("shortcuts", []):
                    if isinstance(shortcut.get("url"), str):
                        shortcut["url"] = shortcut["url"].replace("/odoo", prefix, 1)
                share = manifest.get("share_target")
                if isinstance(share, dict) and isinstance(share.get("action"), str):
                    share["action"] = share["action"].replace("/odoo", prefix, 1)
        except Exception:
            _logger.warning("biz_debrand: webmanifest branding failed", exc_info=True)
        return manifest
