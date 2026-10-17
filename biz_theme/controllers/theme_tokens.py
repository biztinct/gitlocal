from odoo import http
from odoo.http import request


class BizThemeTokens(http.Controller):
    @http.route("/biz_theme/tokens.css", type="http", auth="public", readonly=True)
    def tokens_css(self, v=None, **kwargs):
        """Serve the published theme as a tiny CSS custom-property block.

        The block is injected after the compiled asset bundles, so its :root
        overrides win the cascade over the SCSS-emitted defaults. If anything
        goes wrong (no theme, bad JSON), the app simply renders with the
        compiled defaults — this route can tint, never break.
        ETag = published version, so browsers revalidate cheaply (304) and a
        publish invalidates instantly without needing a versioned URL.
        """
        version = request.env["biz.theme"].sudo()._current_version()
        etag = f'"biz-theme-{version}"'
        if request.httprequest.headers.get("If-None-Match") == etag:
            return request.make_response("", status=304, headers=[("ETag", etag)])
        try:
            css = request.env["biz.theme"].sudo()._published_css()
        except Exception:
            css = "/* biz_theme: error — defaults apply */\n"
        return request.make_response(
            css,
            headers=[
                ("Content-Type", "text/css; charset=utf-8"),
                ("Cache-Control", "public, max-age=0, must-revalidate"),
                ("ETag", etag),
            ],
        )
