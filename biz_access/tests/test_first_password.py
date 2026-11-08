"""The forced password-change page must render and keep the renewed session."""
from lxml import html

from odoo.exceptions import AccessDenied
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestFirstPassword(HttpCase):
    path = '/biz_access/first-password'
    initial = 'First-Password-Test-Only-2947'
    replacement = 'Replacement-Test-Only-8274'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.staff = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'First password test staff',
            'login': 'first-password-staff@example.invalid',
            'password': cls.initial,
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
            'pb_must_change_password': True,
        })
        cls.portal = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'First password test portal',
            'login': 'first-password-portal@example.invalid',
            'password': cls.initial,
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
            'pb_must_change_password': True,
        })

    def _open_form(self, user):
        self.authenticate(user.login, self.initial)
        page = self.url_open(self.path)
        self.assertEqual(page.status_code, 200)
        form = html.fromstring(page.content)
        self.assertTrue(form.xpath('//input[@name="new1"]'))
        self.assertTrue(form.xpath('//input[@name="new2"]'))
        self.assertIn(user.login, page.text)
        return form.xpath('//input[@name="csrf_token"]/@value')[0]

    def test_staff_and_portal_can_render_the_form(self):
        for user in (self.staff, self.portal):
            self._open_form(user)
            if 'website' in self.env:
                translations = self.url_open(
                    '/website/translations?lang=en_US', allow_redirects=False)
                self.assertEqual(translations.status_code, 200)
                self.assertIsInstance(translations.json(), dict)

    def test_mismatched_passwords_render_error_without_changing_credentials(self):
        token = self._open_form(self.staff)
        page = self.url_open(self.path, data={
            'csrf_token': token, 'new1': self.replacement, 'new2': self.initial,
        })
        self.assertEqual(page.status_code, 200)
        self.assertIn('The two passwords are not the same.', page.text)
        self.staff.invalidate_recordset()
        self.assertTrue(self.staff.pb_must_change_password)
        self.staff.with_user(self.staff)._check_credentials(
            {'type': 'password', 'password': self.initial}, {'interactive': True})

    def test_password_change_renews_session_and_clears_first_password_gate(self):
        token = self._open_form(self.staff)
        response = self.url_open(self.path, data={
            'csrf_token': token, 'new1': self.replacement, 'new2': self.replacement,
        }, allow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        self.staff.invalidate_recordset()
        self.assertFalse(self.staff.pb_must_change_password)
        self.staff.with_user(self.staff)._check_credentials(
            {'type': 'password', 'password': self.replacement}, {'interactive': True})
        with self.assertRaises(AccessDenied):
            self.staff.with_user(self.staff)._check_credentials(
                {'type': 'password', 'password': self.initial}, {'interactive': True})
        # A retained authenticated session now skips the form instead of being
        # sent to login after the password invalidated the original token.
        revisit = self.url_open(self.path, allow_redirects=False)
        self.assertIn(revisit.status_code, (302, 303))
        self.assertEqual(revisit.headers['Location'], '/odoo')
