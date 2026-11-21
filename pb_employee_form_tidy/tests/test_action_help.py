# -*- coding: utf-8 -*-
"""FS-14b test C: the Employees action no longer sends pictures of apps that
are not on this server (the seven 404s of the employee record page)."""
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons.pb_employee_form_tidy.models.action_help import (
    _app_on_server, strip_missing_app_pictures)

SRC = re.compile(r'src="/([a-z0-9_]+)/static/', re.I)


@tagged('post_install', '-at_install', 'pb_employee_form_tidy', 'fs14b')
class TestActionHelpPictures(TransactionCase):

    def test_c1_employees_action_sends_no_missing_app_picture(self):
        action = self.env.ref('hr.open_view_employee_list_my')
        stored = SRC.findall(str(action.help or ''))
        self.assertTrue(stored, 'the standard advert has app pictures')
        sent = SRC.findall(str(action._get_action_dict().get('help') or ''))
        missing = [m for m in stored if not _app_on_server(m)]
        for name in missing:
            self.assertNotIn(name, sent, '%s is not on this server: its picture is left out' % name)
        for name in stored:
            if _app_on_server(name):
                self.assertIn(name, sent, 'pictures of apps that exist stay')
        # nothing stored changed
        self.assertEqual(SRC.findall(str(action.help or '')), stored)

    def test_c2_helper(self):
        html = ('<p>x</p><img src="/no_such_app_fs14/static/description/icon.png" width="60"/>'
                '<img src="/hr/static/description/icon.png"/>')
        out = strip_missing_app_pictures(html)
        self.assertNotIn('no_such_app_fs14', out)
        self.assertIn('/hr/static/description/icon.png', out)
        self.assertEqual(strip_missing_app_pictures(''), '')
        self.assertIsNone(strip_missing_app_pictures(None))
