# Part of biz_theme. License LGPL-3.
"""ERRORS E2-1 — the portal must reach the calm dialog, not a stock toast.

The behaviour itself lives in JavaScript and is pinned by the hoot suite in
``biz_theme/static/tests/biz_error_dialogs.test.js``. These two tests pin the
two *server-side* facts that suite cannot see and that would silently undo it:

  * the frontend bundle really does carry both files, and ours is evaluated
    AFTER core's ``error_notifications.js`` — the registry removal is a
    load-time statement, so the order is load-bearing;
  * the removal is still in the file at all.

Neither is cosmetic. When either breaks, nothing raises: the visitor simply
goes back to a toast titled with the vendor's name.
"""
import os

from odoo.tests import TransactionCase, tagged

CORE_NOTIFICATIONS = 'web/static/src/public/error_notifications.js'
OUR_DIALOGS = 'biz_theme/static/src/js/biz_error_dialogs.js'


@tagged('post_install', '-at_install')
class TestFrontendErrorRouting(TransactionCase):

    def _frontend_paths(self):
        IrAsset = self.env['ir.asset']
        params = IrAsset._get_asset_params()
        paths = IrAsset._get_asset_paths('web.assets_frontend', params)
        # (path, addon, bundle) tuples; the path is absolute on disk.
        return [str(entry[0]).replace(os.sep, '/') for entry in paths]

    def test_our_dialogs_load_after_core_notifications(self):
        paths = self._frontend_paths()
        core = [i for i, p in enumerate(paths) if p.endswith(CORE_NOTIFICATIONS)]
        ours = [i for i, p in enumerate(paths) if p.endswith(OUR_DIALOGS)]
        self.assertTrue(
            core, 'web.assets_frontend no longer carries %s — the premise of '
                  'the portal fix has changed; re-check E2-1.' % CORE_NOTIFICATIONS)
        self.assertTrue(
            ours, 'web.assets_frontend no longer carries %s, so the portal is '
                  'back on the stock error dialogs.' % OUR_DIALOGS)
        self.assertLess(
            core[-1], ours[0],
            'Core registers the error notifications AFTER we remove them, so '
            'the removal is undone on every page load. Fix the bundle order.')

    def test_the_removal_is_still_in_the_file(self):
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, 'static', 'src', 'js',
                               'biz_error_dialogs.js'), encoding='utf-8') as fh:
            source = fh.read()
        self.assertIn('errorNotificationRegistry.remove(exceptionName)', source,
                      'The notification-registry removal is gone: every calm '
                      'dialog below it is skipped on the portal.')
        self.assertIn('function bizOwnsDialog', source,
                      'The per-error rail that makes the removal '
                      'order-independent is gone.')
