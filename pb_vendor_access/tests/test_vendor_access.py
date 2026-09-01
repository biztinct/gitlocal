# -*- coding: utf-8 -*-
"""RIZE P11 — the rails that must not quietly stop working.

The live Chrome run is what proves the panels mount (W10); these are the floor.
Every one of them is written against a failure this module could have and that
nothing at runtime would report:

  * a profile pointing at the administrator permission would make "grant this
    person the role" a two-click hand-over of the whole database, and the board
    would say nothing unusual while doing it;
  * a delegation that hands over something the lender does not hold is a
    privilege ESCALATION dressed as a courtesy, and the only thing that makes it
    impossible is a server-side refusal;
  * an auto-revert that removes the profile's groups rather than the ones it
    actually added takes away permissions somebody held in their own right, once
    a fortnight, for ever;
  * an audit trail with a working `unlink` is a diary.
"""

import re
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

_RE_ADJACENT_STRINGS = re.compile(r"""["']\s*\n\s*["']""")


def _src(*parts):
    path = get_module_path('pb_vendor_access')
    with open(path + '/' + '/'.join(parts), encoding='utf-8') as fh:
        return fh.read()


@tagged('post_install', '-at_install')
class TestVendorRegister(TransactionCase):

    def setUp(self):
        super().setUp()
        self.vendor = self.env['pb.vendor'].create({
            'name': 'ZZ Test Agency %s' % fields.Datetime.now(),
            'vendor_type': 'recruitment',
            'responsible_user_id': self.env.uid,
        })

    def test_the_agreement_state_follows_the_calendar_and_is_never_typed(self):
        today = fields.Date.context_today(self.env['pb.vendor'])
        running = self.env['pb.vendor.agreement'].create({
            'vendor_id': self.vendor.id, 'name': 'Long one',
            'date_start': today - timedelta(days=30),
            'date_end': today + timedelta(days=400),
        })
        soon = self.env['pb.vendor.agreement'].create({
            'vendor_id': self.vendor.id, 'name': 'Ending one',
            'date_start': today - timedelta(days=300),
            'date_end': today + timedelta(days=20),
        })
        gone = self.env['pb.vendor.agreement'].create({
            'vendor_id': self.vendor.id, 'name': 'Old one',
            'date_start': today - timedelta(days=400),
            'date_end': today - timedelta(days=10),
        })
        self.assertEqual(running.state, 'running')
        self.assertEqual(soon.state, 'expiring')
        self.assertEqual(gone.state, 'expired')
        # A heading that asserts something the data can contradict is wrong
        # half the time (R68): the state is computed and has no setter.
        self.assertFalse(
            self.env['pb.vendor.agreement']._fields['state'].inverse,
            'the agreement state must never be writable by hand')

    def test_the_renewal_date_is_filled_in_thirty_days_before_the_end(self):
        today = fields.Date.context_today(self.env['pb.vendor'])
        a = self.env['pb.vendor.agreement'].create({
            'vendor_id': self.vendor.id, 'name': 'No renewal date given',
            'date_start': today, 'date_end': today + timedelta(days=200),
        })
        self.assertEqual(a.renewal_date, a.date_end - timedelta(days=30))

    def test_renewing_makes_a_new_row_and_keeps_the_old_one(self):
        today = fields.Date.context_today(self.env['pb.vendor'])
        old = self.env['pb.vendor.agreement'].create({
            'vendor_id': self.vendor.id, 'name': 'Terms 2025',
            'date_start': today - timedelta(days=365),
            'date_end': today + timedelta(days=10),
        })
        new = old.action_renew()
        self.assertTrue(old.is_renewed)
        self.assertEqual(old.renewed_by_id, new)
        self.assertEqual(new.renewed_from_id, old)
        self.assertEqual(old.state, 'renewed')
        # It takes over the day AFTER, not on the same day.
        self.assertEqual(new.date_start, old.date_end + timedelta(days=1))
        # And it refuses to be renewed twice rather than quietly making a
        # third row (R100).
        with self.assertRaises(UserError):
            old.action_renew()

    def test_an_agreement_cannot_end_before_it_starts(self):
        today = fields.Date.context_today(self.env['pb.vendor'])
        with self.assertRaises(ValidationError):
            self.env['pb.vendor.agreement'].create({
                'vendor_id': self.vendor.id, 'name': 'Backwards',
                'date_start': today, 'date_end': today - timedelta(days=1),
            })

    def test_the_alert_job_is_idempotent(self):
        today = fields.Date.context_today(self.env['pb.vendor'])
        self.env['pb.vendor.agreement'].create({
            'vendor_id': self.vendor.id, 'name': 'Due for renewal',
            'date_start': today - timedelta(days=300),
            'date_end': today + timedelta(days=15),
        })
        first = self.env['pb.vendor.alerts'].run(limit=None)
        second = self.env['pb.vendor.alerts'].run(limit=None)
        self.assertGreaterEqual(first['due'], 1)
        # The second pass does the work again for nothing: every row it looks
        # at was stamped today, so nothing is raised and nothing is mailed.
        self.assertEqual(second['reminded'], 0)
        self.assertEqual(second['mailed'], 0)
        self.assertGreaterEqual(second['skipped'], 1)


@tagged('post_install', '-at_install')
class TestTheAbsolute(TransactionCase):
    """Nothing here may ever hand out the administrator permission."""

    def test_a_profile_cannot_point_at_the_system_group(self):
        with self.assertRaises(ValidationError):
            self.env['pb.role.profile'].create({
                'name': 'ZZ nope',
                'group_id': self.env.ref('base.group_system').id,
                'area': 'system',
            })

    def test_a_profile_cannot_point_at_the_erp_manager_group(self):
        group = self.env.ref('base.group_erp_manager',
                             raise_if_not_found=False)
        if not group:
            self.skipTest('base.group_erp_manager is not on this database')
        with self.assertRaises(ValidationError):
            self.env['pb.role.profile'].create({
                'name': 'ZZ nope either', 'group_id': group.id,
                'area': 'system',
            })

    def test_the_seeded_catalogue_contains_neither(self):
        from odoo.addons.pb_vendor_access.hooks import CATALOGUE
        named = {row[0] for row in CATALOGUE}
        self.assertNotIn('base.group_system', named)
        self.assertNotIn('base.group_erp_manager', named)

    def test_no_seeded_profile_points_at_a_forbidden_group(self):
        from odoo.addons.pb_vendor_access.models.vendor_common import (
            forbidden_group_ids)
        forbidden = forbidden_group_ids(self.env)
        rows = self.env['pb.role.profile'].sudo().search([])
        self.assertTrue(rows, 'the catalogue did not seed at all')
        for row in rows:
            self.assertNotIn(row.group_id.id, forbidden,
                             '%s points at an administrator group' % row.name)

    def test_every_seeded_profile_says_what_it_lets_someone_do(self):
        """The sentence is the whole point of the board. A role with an empty
        description is a permission group with a nicer name, which is the thing
        this module exists to stop being the only option."""
        for row in self.env['pb.role.profile'].sudo().search([]):
            self.assertTrue(
                (row.description or '').strip(),
                '"%s" has no description — the person granting it would have '
                'nothing to read' % row.name)


@tagged('post_install', '-at_install')
class TestDelegation(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Users = self.env['res.users'].with_context(no_reset_password=True)
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        self.lender = self.Users.create({
            'name': 'ZZ Lender', 'login': 'zz.lender.%s@example.com' % stamp,
            'email': 'zz.lender.%s@example.com' % stamp,
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        self.borrower = self.Users.create({
            'name': 'ZZ Borrower',
            'login': 'zz.borrower.%s@example.com' % stamp,
            'email': 'zz.borrower.%s@example.com' % stamp,
            'group_ids': [(4, self.env.ref('base.group_user').id)],
        })
        self.profile = self.env['pb.role.profile'].sudo().search(
            [('group_id', '=',
              self.env.ref('pb_vendor_access.group_vendor_user').id)], limit=1)
        self.assertTrue(self.profile, 'the vendor-owner profile did not seed')

    def _hand(self, days=2, started=0):
        """`started` days ago, so a window that is genuinely in the PAST can be
        built without asking the model to accept an end before its start —
        `_check_window` refuses that, correctly, and a test that fought it
        would be testing the wrong thing."""
        today = fields.Date.context_today(self.env['pb.vendor'])
        start = today - timedelta(days=started)
        return self.env['pb.access.delegation'].create({
            'delegator_user_id': self.lender.id,
            'delegate_user_id': self.borrower.id,
            'profile_ids': [(6, 0, [self.profile.id])],
            'kind': 'temporary',
            'date_start': start,
            'date_end': start + timedelta(days=days),
        })

    def test_you_cannot_lend_what_you_do_not_hold(self):
        rec = self._hand()
        with self.assertRaises(UserError):
            rec.action_activate()
        self.assertEqual(rec.state, 'draft')
        self.assertFalse(self.profile.group_id.id
                         in set(self.borrower.all_group_ids.ids))

    def test_activating_adds_exactly_what_it_records(self):
        self.lender.sudo().write(
            {'group_ids': [(4, self.profile.group_id.id)]})
        rec = self._hand()
        rec.action_activate()
        self.assertEqual(rec.state, 'active')
        self.assertIn(self.profile.group_id.id,
                      set(self.borrower.all_group_ids.ids))
        # The SNAPSHOT is the difference the activation actually made, so
        # every id on it is one the borrower now holds directly.
        self.assertTrue(rec.applied_group_ids)
        held = set(self.borrower.group_ids.ids)
        for group in rec.applied_group_ids:
            self.assertIn(group.id, held)

    def test_the_revert_removes_only_what_it_added(self):
        """The borrower already holds one of the groups in their own right.

        Removing "the profile's groups" would take it away permanently because
        a two-week loan ended — the exact over-removal the snapshot exists to
        prevent.
        """
        group = self.profile.group_id
        self.lender.sudo().write({'group_ids': [(4, group.id)]})
        self.borrower.sudo().write({'group_ids': [(4, group.id)]})
        rec = self._hand()
        rec.action_activate()
        # Nothing was added, because they already had it.
        self.assertFalse(rec.applied_group_ids)
        rec.action_revoke()
        self.assertEqual(rec.state, 'revoked')
        # And they still have it.
        self.assertIn(group.id, set(self.borrower.group_ids.ids))

    def test_the_nightly_revert_is_idempotent_and_exact(self):
        group = self.profile.group_id
        self.lender.sudo().write({'group_ids': [(4, group.id)]})
        # R36 — the date comes from the SERVER, and the whole window is in the
        # past rather than the end date alone: `_check_window` refuses an end
        # before its start, which is right, so the fixture is a hand-over that
        # ran last week and finished yesterday.
        rec = self._hand(days=6, started=7)
        rec.action_activate()
        self.assertIn(group.id, set(self.borrower.group_ids.ids))

        first = self.env['pb.access.delegation'].run_auto_revert(limit=None)
        self.assertGreaterEqual(first['ended'], 1)
        self.borrower.invalidate_recordset(['group_ids'])
        self.assertNotIn(group.id, set(self.borrower.group_ids.ids))
        self.assertEqual(rec.state, 'expired')

        # Run it again: the row is no longer `active`, so there is nothing to
        # find and nothing to do. The record still exists, still says expired,
        # and the borrower's permissions are unchanged by the second pass.
        before = set(self.borrower.group_ids.ids)
        self.env['pb.access.delegation'].run_auto_revert(limit=None)
        self.borrower.invalidate_recordset(['group_ids'])
        self.assertEqual(rec.state, 'expired')
        self.assertTrue(rec.exists())
        self.assertEqual(before, set(self.borrower.group_ids.ids))

    def test_a_temporary_hand_over_needs_an_end_date(self):
        today = fields.Date.context_today(self.env['pb.vendor'])
        with self.assertRaises(ValidationError):
            self.env['pb.access.delegation'].create({
                'delegator_user_id': self.lender.id,
                'delegate_user_id': self.borrower.id,
                'kind': 'temporary', 'date_start': today,
            })

    def test_you_cannot_hand_your_access_to_yourself(self):
        today = fields.Date.context_today(self.env['pb.vendor'])
        with self.assertRaises(ValidationError):
            self.env['pb.access.delegation'].create({
                'delegator_user_id': self.lender.id,
                'delegate_user_id': self.lender.id,
                'kind': 'permanent', 'date_start': today,
            })

    def test_history_can_never_be_deleted(self):
        """Not by a user, and not by an administrator either."""
        rec = self._hand()
        with self.assertRaises(UserError):
            rec.unlink()
        with self.assertRaises(UserError):
            rec.sudo().unlink()

    def test_the_acl_grants_unlink_to_nobody(self):
        path = get_module_path('pb_vendor_access')
        with open(path + '/security/ir.model.access.csv', encoding='utf-8') as fh:
            lines = [ln for ln in fh.read().splitlines()
                     if 'model_pb_access_delegation' in ln]
        self.assertTrue(lines)
        for line in lines:
            self.assertTrue(
                line.rstrip().endswith(',0'),
                'an audit trail with a delete button is a diary: %s' % line)


@tagged('post_install', '-at_install')
class TestFacadeRefusals(TransactionCase):

    def test_the_facade_refuses_a_profile_on_an_admin_group(self):
        """Belt AND braces: the model already refuses, so this proves the
        facade's own check by pointing an EXISTING profile at the system group
        through raw SQL — the one route that gets past the constraint."""
        profile = self.env['pb.role.profile'].sudo().search([], limit=1)
        self.assertTrue(profile)
        system = self.env.ref('base.group_system')
        self.env.cr.execute(
            'UPDATE pb_role_profile SET group_id = %s WHERE id = %s',
            (system.id, profile.id))
        profile.invalidate_recordset(['group_id'])
        with self.assertRaises(UserError):
            self.env['pb.access']._safe_profile(profile.id)

    def test_the_vendor_board_refuses_somebody_holding_nothing(self):
        stamp = str(fields.Datetime.now()).replace(' ', '').replace(':', '')
        plain = self.env['res.users'].with_context(
            no_reset_password=True).create({
                'name': 'ZZ Plain', 'login': 'zz.plain.%s@example.com' % stamp,
                'group_ids': [(4, self.env.ref('base.group_user').id)],
            })
        with self.assertRaises(AccessError):
            self.env['pb.vendors'].with_user(plain)._require()


@tagged('post_install', '-at_install')
class TestSourceGates(TransactionCase):
    """Two whole classes of defect that are invisible at runtime."""

    def test_no_python_style_implicit_string_concatenation(self):
        """A Python habit here is a JS SyntaxError, and Odoo's asset pipeline
        concatenates without ever parsing — so one of these blanks
        `web.assets_backend` for every user with a clean server log (R2)."""
        for fname in ('vendors_board.js', 'access_board.js',
                      'vendor_palette.js'):
            src = _src('static', 'src', 'js', fname)
            self.assertFalse(
                _RE_ADJACENT_STRINGS.search(src),
                '%s has two adjacent string literals across a newline' % fname)

    def test_no_reserved_owl_name_is_used_as_a_loop_variable(self):
        """`t-as="lt"` compiles the loop variable into the generated function
        as a bare `<` and the whole template dies, pointing at the template and
        never at the loop (R1)."""
        reserved = {'lt', 'gt', 'lte', 'gte', 'and', 'or', 'not', 'in'}
        for fname in ('vendors_board.xml', 'access_board.xml'):
            src = _src('static', 'src', 'xml', fname)
            for name in re.findall(r't-as="(\w+)"', src):
                self.assertNotIn(name, reserved,
                                 '%s uses the reserved name %s' % (fname, name))

    def test_every_icon_name_is_in_the_shared_registry(self):
        """`ic()` falls back to a checkmark for an unknown name, so a typo is a
        wrong icon rather than an error (W2 — never a per-module icon file)."""
        path = get_module_path('pb_import_kit')
        with open(path + '/static/src/js/import_icons.js',
                  encoding='utf-8') as fh:
            known = set(re.findall(r"^\s{4}([A-Za-z][A-Za-z0-9]*):\s*'",
                                   fh.read(), re.M))
        self.assertIn('briefcase', known, 'the icon registry did not parse')
        used = set()
        for fname in ('vendors_board.xml', 'access_board.xml'):
            used |= set(re.findall(r"ic\('([A-Za-z0-9_]+)'",
                                   _src('static', 'src', 'xml', fname)))
        used |= set(re.findall(r'icon:\s*"([A-Za-z0-9_]+)"',
                               _src('static', 'src', 'js',
                                    'vendor_palette.js')))
        for name in used:
            self.assertIn(name, known,
                          "icon '%s' is not in the shared ic() registry" % name)

    def test_the_word_odoo_appears_in_no_user_visible_string(self):
        """The white-label rule, and only where it actually binds.

        It covers user-visible STRINGS. Engineering comments MUST be able to
        say the real name — "`<act_window>` is gone from the Odoo 19 data-file
        RNG" is the sentence that stops the next contributor reintroducing the
        bug, and a gate that forbade it would push a real warning out of the
        file. So the comments are stripped and everything that is left is
        checked, which is the half a person can read.
        """
        for parts in (('static', 'src', 'xml', 'vendors_board.xml'),
                      ('static', 'src', 'xml', 'access_board.xml'),
                      ('data', 'mail_template_data.xml'),
                      ('views', 'vendor_access_views.xml')):
            src = re.sub(r'<!--.*?-->', '', _src(*parts), flags=re.S)
            self.assertNotIn(
                'Odoo', src,
                '%s shows the word Odoo to a user' % parts[-1])
            self.assertNotIn('odoo.com', src.lower())

    def test_no_bracketed_plurals(self):
        """"1 agreement(s)" is how a screen announces it was written by a
        programme rather than by a person (R46)."""
        for parts in (('models', 'vendor_alerts.py'),
                      ('models', 'pb_access_delegation.py'),
                      ('models', 'pb_vendors_facade.py'),
                      ('models', 'pb_access_facade.py'),
                      ('static', 'src', 'xml', 'vendors_board.xml'),
                      ('static', 'src', 'xml', 'access_board.xml')):
            src = _src(*parts)
            self.assertFalse(
                re.search(r'\w\(s\)', src),
                '%s has a bracketed plural' % parts[-1])

    def test_the_delegation_snapshot_is_measured_and_not_predicted(self):
        """The single most important line in the module: what was ADDED is read
        back off the user, never computed from the profiles."""
        src = _src('models', 'pb_access_delegation.py')
        block = src.split('def _activate_one', 1)[1].split('def _groups_to_hand',
                                                           1)[0]
        self.assertIn('before = set(delegate.group_ids.ids)', block)
        self.assertIn("invalidate_recordset(['group_ids'])", block)
        self.assertIn('added = sorted(after - before)', block)

    def test_the_revert_only_removes_what_is_still_there(self):
        src = _src('models', 'pb_access_delegation.py')
        block = src.split('def _end(', 1)[1].split('def _mail(', 1)[0]
        self.assertIn('still = applied.filtered', block)
        self.assertIn('gone = applied - still', block)


@tagged('post_install', '-at_install')
class TestTheDoors(TransactionCase):

    def test_the_two_client_actions_exist_and_carry_a_name(self):
        """A bare tag reaches the action service with no NAME and the
        breadcrumb reads "Unnamed"."""
        for xmlid, tag, name in (
                ('pb_vendor_access.action_pb_vendors_board',
                 'pb_vendors_board', 'Vendors'),
                ('pb_vendor_access.action_pb_access_board',
                 'pb_access_board', 'Access & delegation')):
            act = self.env.ref(xmlid)
            self.assertEqual(act.tag, tag)
            self.assertEqual(act.name, name)

    def test_the_palette_and_the_settings_panels_name_real_actions(self):
        src = _src('static', 'src', 'js', 'vendor_palette.js')
        for xmlid in set(re.findall(r'xmlid:\s*"([\w.]+)"', src)):
            self.assertTrue(
                self.env.ref(xmlid, raise_if_not_found=False),
                'the palette points at %s, which does not resolve — the row '
                'would render and open nothing (W79)' % xmlid)

    def test_the_palette_takes_the_3200_block(self):
        src = _src('static', 'src', 'js', 'vendor_palette.js')
        seqs = sorted(int(n) for n in re.findall(r'sequence:\s*(3\d{3})', src))
        self.assertTrue(seqs)
        self.assertGreaterEqual(seqs[0], 3200)
        self.assertLess(seqs[-1], 3300,
                        'P11 owns the 3200 block; P12 would start at 3300')

    def test_this_module_ships_no_menu_and_no_rail_item(self):
        """Its doors are the two Settings panels and the palette."""
        for tag in ('pb_vendors_board', 'pb_access_board'):
            act = self.env['ir.actions.client'].sudo().search(
                [('tag', '=', tag)], limit=1)
            menus = self.env['ir.ui.menu'].sudo().with_context(
                active_test=False).search([('action', '!=', False)])
            hits = [m.complete_name for m in menus
                    if m.action._name == 'ir.actions.client'
                    and m.action.id == act.id]
            self.assertFalse(hits, '%s must not be on a menu: %s' % (tag, hits))
        if 'pb.sidebar.item' in self.env:
            items = self.env['pb.sidebar.item'].sudo().with_context(
                active_test=False).search(
                    [('action_tag', 'in',
                      ['pb_vendors_board', 'pb_access_board'])])
            self.assertFalse(items, 'this module claims no rail item')

    def test_the_asset_link_exists_on_both_models(self):
        self.assertIn('vendor_id', self.env['pb.asset']._fields)
        # And the free-text column it stands beside still works.
        self.assertIn('supplier_note', self.env['pb.asset']._fields)
        if 'pb.budget.expense' in self.env:
            self.assertIn('vendor_id', self.env['pb.budget.expense']._fields)
            self.assertIn('supplier', self.env['pb.budget.expense']._fields)
