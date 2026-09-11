"""The three staff pages this module owns must actually open.

WHY THIS IS AN ``HttpCase`` AND NOT A UNIT TEST. The failure these guard
against did not live in any one method — every method here was correct in
isolation. It lived in the class the ROUTER builds: all ``CustomerPortal``
subclasses on the server are merged into one class, ``pb_rnr`` happened to
register after this module, and its ``_card`` (which reads a nomination)
replaced this module's ``_card`` (which reads an employee). All three pages
answered 500 with ``'hr.employee' object has no attribute 'nominee_id'`` on
every database on the platform, and nothing short of fetching the page over
HTTP would have noticed.

So: log in as an ordinary employee and ask for the pages, exactly as a member
of staff does. A 200 with the page's own marker in it is the only proof that
the merged class is still the right one.

See also ``pb_me_portal/tests/test_portal_helper_names.py``, which states the
naming rule that prevents the clash in the first place.
"""
from odoo.tests import HttpCase, tagged

#: Every page this module puts in front of staff, and a fragment of its own
#: content — a 200 carrying the wrong page would otherwise pass.
PAGES = [
    ('/my/journey', 'journey'),
    ('/my/buddy', 'buddy'),
    ('/my/orgchart', 'orgchart'),
]


@tagged('post_install', '-at_install')
class TestOnboardingPortalPages(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        internal = cls.env.ref('base.group_user')
        cls.password = 'ObPortal!2026'
        cls.user = cls.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'Onboarding Portal Tester',
                'login': 'test_ob_portal',
                'password': cls.password,
                'group_ids': [(6, 0, [internal.id])],
            })
        Emp = cls.env['hr.employee']
        cls.manager = Emp.create({
            'name': 'Ob Manager', 'company_id': cls.env.company.id})
        cls.buddy = Emp.create({
            'name': 'Ob Buddy', 'company_id': cls.env.company.id})
        # The person the pages are about: they have a manager (org chart), a
        # buddy (buddy page) and therefore a journey. Every relation the cards
        # are drawn from is populated, because an empty page would render fine
        # with the wrong helper too.
        cls.employee = Emp.create({
            'name': 'Ob Joiner',
            'user_id': cls.user.id,
            'company_id': cls.env.company.id,
            'parent_id': cls.manager.id,
            'buddy_id': cls.buddy.id,
        })

    def test_01_the_three_staff_pages_open(self):
        self.authenticate('test_ob_portal', self.password)
        for url, marker in PAGES:
            with self.subTest(url=url):
                response = self.url_open(url)
                self.assertEqual(
                    response.status_code, 200,
                    "%s answered %s (landed on %s) — a member of staff meets "
                    "a breakdown page. Body starts: %r"
                    % (url, response.status_code, response.url,
                       response.text[:400]))
                self.assertIn(
                    marker, response.url + response.text[:4000].lower(),
                    "%s answered 200 but does not look like its own page" % url)

    def test_02_no_page_leaks_a_crash_report(self):
        """A 200 is not enough: the page must not BE an error page.

        The breakdown page is served with its own status, but a page that
        swallowed an exception and rendered the stack into its body would still
        answer 200. Check for the shapes a crash leaves behind.
        """
        self.authenticate('test_ob_portal', self.password)
        for url, _marker in PAGES:
            body = self.url_open(url).text
            for leak in ('Traceback (most recent call last)',
                         'odoo-server/odoo',
                         'Internal Server Error'):
                self.assertNotIn(
                    leak, body, "%s shows a crash report to staff" % url)
