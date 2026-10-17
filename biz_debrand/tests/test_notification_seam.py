# Part of biz_debrand — portable Odoo 19 white-label layer. License LGPL-3.
"""ERRORS E2-3 — raw failure text must not reach a toast.

The seam itself is JavaScript and is pinned by
``biz_debrand/static/tests/notification_debrand.test.js``. These tests pin the
two server-side facts that suite cannot see and that would silently undo it:
the wrapper is still in the file, and the file still reaches BOTH bundles — the
backend web client and the portal/website. A toast is drawn on both.
"""
import os

from odoo.tests import TransactionCase, tagged

RUNTIME = 'biz_debrand/static/src/js/biz_debrand_runtime.js'


@tagged('post_install', '-at_install')
class TestNotificationSeam(TransactionCase):

    def _runtime_source(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(here, 'static', 'src', 'js', 'biz_debrand_runtime.js')
        with open(path, encoding='utf-8') as fh:
            return fh.read()

    def test_the_seam_is_still_in_the_file(self):
        source = self._runtime_source()
        self.assertIn('patch(notificationService', source,
                      'Seam 3 is gone: every raw failure pasted into a toast '
                      'reaches the screen again.')
        self.assertIn('debrandNotificationValue', source)
        # The markup guard. Flattening a Markup message double-escapes the page.
        # Pinned on the DATA variant specifically: seam 1 carries the same line
        # with debrandText, so asserting on that spelling would pass even if
        # this seam lost its guard entirely (ERRORS E3-2).
        self.assertIn('typeof value === "string" ? debrandDataText(value) : value',
                      source,
                      'The markup guard is gone from the notification seam.')

    def test_the_runtime_reaches_both_bundles(self):
        IrAsset = self.env['ir.asset']
        params = IrAsset._get_asset_params()
        for bundle in ('web.assets_backend', 'web.assets_frontend'):
            paths = [str(entry[0]).replace(os.sep, '/')
                     for entry in IrAsset._get_asset_paths(bundle, params)]
            self.assertTrue(
                any(p.endswith(RUNTIME) for p in paths),
                '%s no longer carries %s, so nothing debrands a toast there.'
                % (bundle, RUNTIME))
