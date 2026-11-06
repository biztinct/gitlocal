# Part of Payobook. See LICENSE file for full copyright and licensing details.
"""TIERS T1 — the website's corner shortcut is not drawn for portal-only people."""
import re

from lxml import etree

from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import config

PASSWORD = 'tiers-t1-corner-probe-2026'


def _people(env, prefix, password=None):
    Users = env['res.users'].with_context(no_reset_password=True)
    internal = env.ref('base.group_user')

    def user(login, name, groups):
        vals = {'name': name, 'login': login,
                'group_ids': [(6, 0, [g.id for g in groups])]}
        if password:
            vals['password'] = password
        return Users.create(vals)

    plain = user('%s_plain' % prefix, 'T1 Corner Employee', [internal])
    env['hr.employee'].create({'name': 'T1 Corner Employee', 'user_id': plain.id,
                               'company_id': env.company.id})
    staff_groups = [internal, env.ref('hr.group_hr_user')]
    pay = env.ref('om_hr_payroll.group_hr_payroll_user', raise_if_not_found=False)
    if pay:
        staff_groups.append(pay)
    staff = user('%s_staff' % prefix, 'T1 Corner Staff', staff_groups)
    return plain, staff


@tagged('post_install', '-at_install')
class TestCornerShortcutArch(TransactionCase):

    # T1.9 (corner half)
    def test_t1_9_the_inherit_reaches_the_combined_arch(self):
        arch = etree.fromstring(
            self.env.ref('website.layout').get_combined_arch())
        divs = arch.xpath(
            "//div[contains(concat(' ', normalize-space(@class), ' '),"
            " ' o_frontend_to_backend_nav ')]")
        self.assertEqual(len(divs), 1,
                         'website.layout no longer renders exactly one backend'
                         ' shortcut — re-check the xpath in'
                         ' frontend_backend_nav.xml')
        self.assertIn('_pb_portal_only', divs[0].get('t-if') or '')


@tagged('post_install', '-at_install')
class TestCornerShortcutPage(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # dbfilter = %h on this platform (ledger T6).
        previous = config['dbfilter']
        config['dbfilter'] = '^%s$' % re.escape(cls.env.cr.dbname)
        cls.addClassCleanup(config.__setitem__, 'dbfilter', previous)
        cls.plain, cls.staff = _people(cls.env, 'test_t1_corner', password=PASSWORD)

    # T1.8 (corner half)
    def test_t1_8_corner_shortcut_only_for_staff(self):
        self.assertTrue(self.plain._pb_portal_only())
        self.authenticate(self.plain.login, PASSWORD)
        page = self.url_open('/my', timeout=30)
        self.assertEqual(page.status_code, 200)
        self.assertNotIn('o_frontend_to_backend_nav', page.text)
        self.assertNotIn('o_backend_user_dropdown_link', page.text)

        self.authenticate(self.staff.login, PASSWORD)
        page = self.url_open('/my', timeout=30)
        self.assertEqual(page.status_code, 200)
        self.assertIn('o_frontend_to_backend_nav', page.text)
        self.assertIn('o_backend_user_dropdown_link', page.text)
