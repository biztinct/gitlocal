# -*- coding: utf-8 -*-
"""The demo world's own chrome, moved out of pb_coach in Phase C2.

Three things pb_coach did for demo users were never about guided tours: the body
tag that keeps a trial user inside Payroll, the ephemeral-data disclaimer, and
the missing-record guard. They belong to whoever knows the demo world's records
are shared and get overwritten — which is this module.

Asserted against the SOURCE, because all three are browser behaviour the server
cannot observe. The important half of every assertion here is the COEXISTENCE
one: pb_coach still ships its copies until the deploy-time uninstall, so nothing
below may fire twice.
"""
import os

from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase, tagged


def _read(module, rel):
    base = get_module_path(module)
    if not base:
        return None
    path = os.path.join(base, rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestDemoChrome(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chrome = _read('pb_demo', 'static/src/js/demo_chrome.js')
        cls.tmpl = _read('pb_demo', 'static/src/xml/demo_chrome.xml')
        cls.scss = _read('pb_demo', 'static/src/scss/demo_chrome.scss')
        cls.guard = _read('pb_demo', 'static/src/js/demo_missing_record.js')

    def test_01_the_files_are_shipped(self):
        for name, src in (('demo_chrome.js', self.chrome),
                          ('demo_chrome.xml', self.tmpl),
                          ('demo_chrome.scss', self.scss),
                          ('demo_missing_record.js', self.guard)):
            self.assertTrue(src, "%s is missing" % name)
        manifest = _read('pb_demo', '__manifest__.py')
        for asset in ('demo_chrome.scss', 'demo_missing_record.js', 'demo_chrome.js',
                      'demo_chrome.xml', 'demo_chrome_patch.js'):
            self.assertIn(asset, manifest, "%s is not in the asset bundle" % asset)

    # -- gating ------------------------------------------------------------
    def test_02_everything_is_demo_group_gated(self):
        self.assertIn('pb_demo.group_payobook_demo', self.chrome,
                      "the demo chrome is not gated on the demo group")
        self.assertIn('pb_demo.group_payobook_demo', self.guard,
                      "the missing-record guard is not gated on the demo group")
        self.assertTrue(
            self.env.ref('pb_demo.group_payobook_demo', raise_if_not_found=False),
            "the group both of them name does not exist")

    def test_03_a_real_user_is_never_redirected(self):
        """The guard returns falsy for anybody who is not a demo user, so the
        stock handler shows the normal message. A redirect for a real user would
        hide a genuine data problem behind a friendly sentence."""
        self.assertIn('if (!isDemoUser', self.guard)
        self.assertIn('return false;', self.guard)

    # -- coexistence with pb_coach ----------------------------------------
    def test_04_the_error_handler_registration_is_idempotent(self):
        """Registry.add THROWS on a duplicate key.

        pb_coach ships an identical handler under the same name until the
        uninstall, so an unguarded second registration would not double-render —
        it would raise while the backend bundle is being evaluated and take
        every module after it down.
        """
        self.assertIn('contains("demoMissingRecordHandler")', self.guard,
                      "the second registration is unguarded")
        self.assertNotIn('force: true', self.guard,
                         "forcing makes asset load order decide which copy wins")

    def test_05_the_disclaimer_stands_down_while_pb_coach_can_draw_one(self):
        """Checked two ways, because they answer different questions: the
        SERVICE says pb_coach is installed, the DOM says it has already drawn."""
        self.assertIn('_coachPresent', self.chrome)
        self.assertIn('_coachChipInDom', self.chrome)
        self.assertIn('.pbc-disclaimer', self.chrome,
                      "the DOM check does not look for pb_coach's own chip")
        self.assertNotIn('useService("pb_coach")', self.chrome,
                         "the service hook throws when pb_coach is uninstalled")

    def test_06_the_body_class_is_the_same_contract(self):
        """`body.pb-demo-user` is CSS other things key off. The NAME does not
        change across the migration; only the module that sets it does."""
        self.assertIn('pb-demo-user', self.chrome)
        self.assertIn('body.pb-demo-user .o_navbar_apps_menu', self.scss,
                      "the rule the class exists for did not come with it")
        self.assertIn('o-mail-DiscussSystray-class', self.scss)
        self.assertIn('classList.contains("pb-demo-user")', self.chrome,
                      "the class is set without checking, which is fine today and "
                      "hides the coexistence decision from the next reader")

    def test_07_the_disclaimer_copy_is_unchanged(self):
        """Rewording during a refactor makes a behaviour change look like a
        migration. This is the sentence the demo world has been telling
        prospects, character for character."""
        for phrase in ('Shared demo', 'temporary and may be cleaned or overwritten',
                       'Want a private demo?'):
            self.assertIn(phrase, self.tmpl, "the disclaimer copy changed: %r" % phrase)
        self.assertIn('/demo/private', self.chrome,
                      "the private-demo link no longer reaches pb_demo_portal")

    def test_08_the_chip_is_dismissible_and_remembers(self):
        self.assertIn('pb_demo_disclaimer_off', self.chrome)
        self.assertIn('dismiss()', self.chrome)

    def test_09_the_mount_point_is_additive(self):
        """MainComponentsContainer, position="after" — an APPEND.

        pb_sidebar REPLACES ActionContainer and pb_learn already appends here;
        several modules adding siblings after one core node is safe, two modules
        replacing the same node is not.
        """
        self.assertIn('MainComponentsContainer', self.tmpl)
        self.assertIn('position="after"', self.tmpl)
        self.assertNotIn('position="replace"', self.tmpl)
