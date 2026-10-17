# Part of biz_deroute — portable Odoo 19 white-label layer. License LGPL-3.
"""Gates for the `hr_timesheet` session_info guard (W100).

Three things have to stay true for `models/ir_http_session_guard.py` to be
both necessary and honest:

1. upstream still crashes the way we think it does — the day Odoo fixes it,
   this suite fails and the patch should be DELETED rather than kept (a patch
   that shadows a fixed upstream is how a future behaviour change disappears);
2. the guarded path renders instead of 500ing, proved through HTTP with a real
   user in the divergent state, not by calling the method;
3. an UNAFFECTED user's payload is unchanged — the guard must be invisible to
   everybody the bug does not hit.
"""
import inspect
import re

from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestSessionGuard(HttpCase):

    def setUp(self):
        super().setUp()
        installed = self.env['ir.module.module'].search([
            ('name', '=', 'hr_timesheet'), ('state', '=', 'installed'),
        ])
        if not installed:
            self.skipTest("hr_timesheet is not installed on this database")

    # ------------------------------------------------------------------ 1
    def test_01_upstream_still_has_the_unguarded_subscript(self):
        """The bug we patch must still exist upstream.

        The needle is SYNTACTIC (W114): a subscript of `allowed_companies`
        by `company.id`, which prose cannot satisfy. If Odoo ships the `.get()`
        fix, this fails — and the correct repair is to delete our patch, not to
        relax the needle.
        """
        from odoo.addons.hr_timesheet.models import ir_http as upstream
        src = inspect.getsource(upstream)
        self.assertRegex(
            src,
            r'\["allowed_companies"\]\[company\.id\]',
            "hr_timesheet.session_info no longer indexes allowed_companies by "
            "company.id — upstream may have fixed W100. Re-read "
            "biz_deroute/models/ir_http_session_guard.py and delete it if so.",
        )
        # ... and our patch must be the function actually bound to the class,
        # otherwise `_register_hook` silently did not take.
        self.assertEqual(
            upstream.IrHttp.session_info.__name__, '_guarded_session_info',
            "the biz_deroute session guard is not bound to hr_timesheet.IrHttp",
        )

    def test_01b_the_guard_is_not_imported_at_module_level(self):
        """`biz_deroute` must never import `hr_timesheet` while it is being
        loaded. It depends on `web` alone and is auto_install, so it loads
        early, and dragging another addon's `ir.http` into the class registry
        ahead of its place in the graph cost every database on the server its
        LOGIN PAGE (500, `Expected singleton: res.users()`, rendering
        `website.layout` with an empty `env.user`). The import belongs in
        `_install_session_guard()`, which `_register_hook` calls after the
        registry is up.
        """
        import inspect

        from ..models import ir_http_session_guard as guard
        src = inspect.getsource(guard)
        head = src.split('def _install_session_guard')[0]
        # Syntactic (W114): an `import` STATEMENT naming hr_timesheet, which the
        # header's prose cannot satisfy.
        self.assertNotRegex(
            head, r'(?m)^\s*(from|import)\s+odoo\.addons\.hr_timesheet',
            "hr_timesheet is imported at biz_deroute module level again",
        )

    # ------------------------------------------------------------------ 2
    def test_02_a_divergent_session_still_renders_the_backend(self):
        """The W100 persona, built the way production builds it.

        A company linked to the user from the COMPANY side leaves
        `res.users._get_company_ids()`'s ormcache stale, so `allowed_companies`
        (built from the cache) lacks an id `company_ids` (read live) has.
        Upstream answers 500 for every backend page of that user.
        """
        user = self.env['res.users'].create({
            'name': 'Guard Probe', 'login': 'guard_probe_w100',
            'password': 'guard_probe_w100',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        # The company is created BEFORE the cache is warmed on purpose:
        # `res.company.create()` clears the registry cache itself, so warming
        # first and creating after would hand this test a fresh, correct cache
        # and no divergence to guard.
        company = self.env['res.company'].create({'name': 'Guard Probe Co'})
        self.env.registry.clear_cache()
        self.assertEqual(sorted(user._get_company_ids()), user.company_ids.ids,
                         "the cache did not start out honest")

        # …and now go behind the cache's back, exactly as core does. The
        # ResCompany.write override this module ships would clear it, so the
        # divergence is created with raw SQL: this test is about the GUARD, and
        # the invalidation is asserted separately by test_04.
        self.env.cr.execute(
            "INSERT INTO res_company_users_rel (cid, user_id) VALUES (%s, %s)",
            (company.id, user.id))
        user.invalidate_recordset(['company_ids'])
        self.assertIn(company.id, user.company_ids.ids)
        self.assertNotIn(company.id, list(user._get_company_ids()),
                         "the ormcache was invalidated — the divergence this "
                         "test needs no longer exists")

        self.authenticate('guard_probe_w100', 'guard_probe_w100')
        res = self.url_open('/bizapp')
        self.assertEqual(res.status_code, 200, "W100 regression: %s" % res.status_code)

    # ------------------------------------------------------------------ 3
    def test_03_an_unaffected_user_keeps_the_timesheet_keys(self):
        """Behaviour preservation: every company of a NON-divergent user still
        gets both timesheet keys, i.e. the guard skipped nothing.
        """
        user = self.env['res.users'].create({
            'name': 'Guard Control', 'login': 'guard_control_w100',
            'password': 'guard_control_w100',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        self.env.registry.clear_cache()
        self.authenticate('guard_control_w100', 'guard_control_w100')
        res = self.url_open('/bizapp')
        self.assertEqual(res.status_code, 200)
        body = res.text
        # session_info is server-rendered into the page as odoo.__session_info__
        self.assertIn('timesheet_uom_id', body)
        self.assertIn('timesheet_uom_factor', body)
        self.assertTrue(
            re.search(r'"uom_ids"\s*:', body),
            "uom_ids missing from the rendered session_info",
        )
        self.assertEqual(user.company_ids.ids, list(user._get_company_ids()))

    # ------------------------------------------------------------------ 4
    def test_04_linking_a_user_from_the_company_side_invalidates_the_cache(self):
        """The CAUSE half: `res.company.write({'user_ids': …})` must leave
        `_get_company_ids()` agreeing with `company_ids`. Without the override
        in `models/ir_http_session_guard.py` the cached tuple is one company
        short and the next page load is the 500 test_02 reproduces.
        """
        user = self.env['res.users'].create({
            'name': 'Guard Cause', 'login': 'guard_cause_w100',
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, [self.env.company.id])],
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        self.env.registry.clear_cache()
        user._get_company_ids()                       # warm it
        company = self.env['res.company'].create({'name': 'Guard Cause Co'})
        company.write({'user_ids': [(4, user.id)]})   # the inverse write
        self.assertEqual(
            sorted(user._get_company_ids()), sorted(user.company_ids.ids),
            "res.company.write did not invalidate res.users._get_company_ids",
        )
