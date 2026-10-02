# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""Seam 6 — pictures that carry the vendor's brand, swapped at the door.

The stock careers pages (website_hr_recruitment) ship photos of the vendor's
own staff wearing its badges, and every job's default description embeds
them — so the same addresses live inside thousands of stored job texts in
every database. Rewriting stored HTML is fragile and the next "new job"
would copy the photos back; instead the static-file lookup answers those
addresses with neutral drawings from static/img/<module>/ (same file names,
same sizes; tools/make_neutral_job_images.py draws them).

Only files that exist in our folder are swapped; everything else resolves
exactly as before. Browsers that already cached a photo keep it until their
cache expires (nginx sends a 10-day expiry for static files).
"""
import os

from odoo import http

_HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'img')
_SWAP = {
    # module: the folder (inside that module's static/) whose pictures we replace
    'website_hr_recruitment': 'src/img/',
}

def _swapped(path):
    """Our neutral picture for a static URL path, or None."""
    try:
        path = path.split('?', 1)[0].split('#', 1)[0]
        if '://' in path:
            return None
        parts = path.split('/', 3)
        if len(parts) != 4 or parts[2] != 'static':
            return None
        prefix = _SWAP.get(parts[1])
        if not prefix or not parts[3].startswith(prefix):
            return None
        name = parts[3][len(prefix):]
        if not name or '/' in name or '..' in name:
            return None
        mine = os.path.join(_HERE, parts[1], name)
        return mine if os.path.isfile(mine) else None
    except Exception:   # never let the swap break static serving
        return None


_orig_get_static_file = http.Application.get_static_file
_orig_serve_static = http.Request._serve_static


def _get_static_file(self, url, host=''):
    return _swapped(url) or _orig_get_static_file(self, url, host)


def _serve_static(self):
    mine = _swapped(self.httprequest.path)
    if mine:
        res = http.Stream.from_path(mine, public=True).get_response(
            max_age=http.STATIC_CACHE, content_security_policy=None)
        http.root.set_csp(res)
        return res
    return _orig_serve_static(self)


if not getattr(http.Application.get_static_file, '_biz_swap', False):
    _get_static_file._biz_swap = True
    http.Application.get_static_file = _get_static_file
    http.Request._serve_static = _serve_static
